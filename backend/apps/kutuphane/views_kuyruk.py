"""Etiket kuyruğu, basım kaydı, doğrulama okutması ve boş barkod aralığı uçları (F4-Q).

Görünümler İNCEDİR (`views.py` ile aynı düzen): kurallar `services.label_queue`
ve `services.barcode_reservations`'tadır, sorgular `selectors_kuyruk`'tadır.

**Kapılar burada tekrarlanmaz:** kilitliyken 423, görevli kipinde 403
`kip_yetkisiz`. Görevli kipi izin listesinde bu dosyadan YALNIZ
`library-label-verify` POST vardır (doğrulama okutması; kullanıcı kararı
24.09.2026): masadaki görevli yapıştırılan etiketi okutabilir, yanıt görevli
kipinde yalnız barkod ve eser adını taşır. Gerisi kapalıdır ve kapalı kalmalıdır
(CLAUDE.md §2-4): etiket basmak, basım işaretini yazmak ya da geri almak,
doğrulanmamışlar listesi, numara ayırmak ve iptal etmek yönetici işidir.

**PDF uçları işaretlere DOKUNMAZ** (D10): partinin ve aralığın PDF'i istenildiği
kadar yeniden alınabilir; "basıldı" işareti yalnız onay ucuyla yazılır. Etiket
motoru yüklenemezse PDF uçları 503 `etiket_motoru_yok` döner, geri kalan akış
(kuyruk, parti, onay, geri alma, ayırma, bağlama) motorsuz çalışır.
"""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any, cast

from django.http import FileResponse
from rest_framework import generics, serializers, status
from rest_framework.exceptions import APIException
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.models import (
    BarcodeReservation,
    LabelOrder,
    LabelPrintBatch,
    LabelPrintKind,
)
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers import CopyReadSerializer
from apps.kutuphane.serializers_kuyruk import (
    BarcodeReservationCreateSerializer,
    BarcodeReservationDetailSerializer,
    BarcodeReservationSerializer,
    CopyFromLabelSerializer,
    LabelBatchCreateSerializer,
    LabelBatchDetailSerializer,
    LabelBatchReprintSerializer,
    LabelBatchSerializer,
    LabelQueueCopySerializer,
    LabelVerifySerializer,
    ReservationCancelSerializer,
    ReservationPdfParamsSerializer,
)
from apps.kutuphane.services import barcode_reservations as reservation_service
from apps.kutuphane.services import label_queue as queue_service
from apps.kutuphane.services import label_render
from apps.kutuphane.views import _choice_param, _int_param
from apps.okul.kip import KIP

PDF_CONTENT_TYPE = "application/pdf"


class EtiketMotoruYok(APIException):
    """Etiket motoru PDF kapısına bağlı değil (`label_render.LabelRendererUnavailable`)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "etiket_motoru_yok"
    default_detail = "Etiket basım motoru yüklenemedi. Programı yeniden kurun."


def _pdf_response(icerik_uret: Any, dosya_adi: str) -> FileResponse:
    try:
        icerik: bytes = icerik_uret()
    except label_render.LabelRendererUnavailable as exc:
        raise EtiketMotoruYok(str(exc)) from exc
    return FileResponse(
        BytesIO(icerik), as_attachment=True, filename=dosya_adi, content_type=PDF_CONTENT_TYPE
    )


# ---------------------------------------------------------------------------
# Sorgu parametreleri
# ---------------------------------------------------------------------------
def _date_param(params: Mapping[str, str], ad: str, etiket: str) -> Any:
    ham = str(params.get(ad, "")).strip()
    if not ham:
        return None
    alan = serializers.DateField()
    try:
        return alan.to_internal_value(ham)
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({ad: f"{etiket} geçerli bir tarih olmalıdır."}) from exc


def _body_filters(veri: Mapping[str, Any]) -> selectors_kuyruk.QueueFilters:
    """Kuyruk süzgeçleri — parti açma gövdesinden (serializer türleri çözmüştür)."""
    return selectors_kuyruk.QueueFilters(
        section_id=veri.get("section"),
        acquisition_id=veri.get("acquisition"),
        reservation_id=veri.get("reservation"),
        created_from=veri.get("created_from"),
        created_to=veri.get("created_to"),
    )


def _filters(params: Mapping[str, str]) -> selectors_kuyruk.QueueFilters:
    """Kuyruk süzgeçleri — sorgu dizesinden."""
    return selectors_kuyruk.QueueFilters(
        section_id=_int_param(params, "section", "Bölüm kimliği"),
        acquisition_id=_int_param(params, "acquisition", "Edinim kimliği"),
        reservation_id=_int_param(params, "reservation", "Aralık kimliği"),
        created_from=_date_param(params, "created_from", "Başlangıç tarihi"),
        created_to=_date_param(params, "created_to", "Bitiş tarihi"),
    )


def _kind_param(params: Mapping[str, str]) -> str:
    return (
        _choice_param(params, "kind", LabelPrintKind.values, "etiket içeriği")
        or LabelPrintKind.BOTH
    )


def _order_param(params: Mapping[str, str]) -> str:
    return (
        _choice_param(params, "order", LabelOrder.values, "basım sırası") or LabelOrder.CALL_NUMBER
    )


class _SiraliNushaListesi(APIView):
    """Sıralı nüsha listesi: kimlikler sıralanır, nesneler SAYFA SAYFA getirilir."""

    pagination_class = KatalogSayfalama

    def _queryset(self, params: Mapping[str, str]) -> Any:  # pragma: no cover - soyut
        raise NotImplementedError

    def get(self, request: Request) -> Response:
        params = request.query_params
        kimlikler = selectors_kuyruk.ordered_copy_ids(self._queryset(params), _order_param(params))
        sayfalayici = self.pagination_class()
        # Sayfalayıcı listeyle de çalışır (DRF `LimitOffsetPagination` dilimler); stub yalnız
        # QuerySet tanır.
        sayfa: list[int] = (
            sayfalayici.paginate_queryset(cast("Any", kimlikler), request, view=self) or []
        )
        nushalar = selectors_kuyruk.copies_by_ids(sayfa)
        baglam = {"pending_batches": selectors_kuyruk.pending_batch_ids(sayfa)}
        veri = LabelQueueCopySerializer(nushalar, many=True, context=baglam).data
        return sayfalayici.get_paginated_response(veri)


class LabelQueueView(_SiraliNushaListesi):
    """`GET library/labels/queue/` — etiketi basılmamış nüshalar, seçilen sırada (D20).

    Parametreler: `kind` (`BOTH` varsayılan · `BARCODE` · `SPINE`), `order`
    (`CALL_NUMBER` varsayılan · `IMPORT_ROW` · `BARCODE`), süzgeçler `section`,
    `acquisition` (F3'ün "bu partinin etiketlerini bas" kısayolu buraya
    bağlanır), `reservation`, `created_from`, `created_to`.
    """

    def _queryset(self, params: Mapping[str, str]) -> Any:
        return selectors_kuyruk.label_queue(_kind_param(params), _filters(params))


class LabelUnverifiedView(_SiraliNushaListesi):
    """`GET library/labels/unverified/` — basılmış ama okutularak doğrulanmamış nüshalar."""

    def _queryset(self, params: Mapping[str, str]) -> Any:
        return selectors_kuyruk.unverified_labels(_filters(params))


class LabelSummaryView(APIView):
    """`GET library/labels/summary/` — kuyruk, doğrulanmamış ve aralık sayaçları (kişisiz)."""

    def get(self, request: Request) -> Response:
        return Response(selectors_kuyruk.label_summary())


class LabelVerifyView(APIView):
    """`POST library/labels/verify/` — doğrulama okutması; sonuç HER ZAMAN 200 gövdedir.

    `result`: `verified` · `already_verified` · `rejected` (yanlış kod türü,
    bağlanmamış boş etiket, basılmamış ya da kayıttan düşülmüş nüsha). Okutma
    bir olaydır, hata değil: tarama ekranı iletiyi gösterir ve sıradakine geçer.

    Görevli kipinde AÇIK tek etiket ucudur (`apps/okul/kip_izinleri.py`, kullanıcı
    kararı 24.09.2026). Görevli kipinde nüsha özeti daralır: yalnız barkod ve eser
    adı (`label_queue.STAFF_COPY_FIELDS`). Kip, ara katmanla aynı süreç içi
    nesneden okunur; kip arada yöneticiden görevliye inmişse yanıt daralmış döner
    (güvenli yön).
    """

    def post(self, request: Request) -> Response:
        gonderi = LabelVerifySerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        return Response(
            queue_service.verify_scan(gonderi.validated_data["code"], staff=KIP.gorevli_mi())
        )


# ---------------------------------------------------------------------------
# Basım partileri
# ---------------------------------------------------------------------------
class LabelBatchListCreateView(generics.ListCreateAPIView[LabelPrintBatch]):
    """`GET/POST library/labels/batches/` — basım geçmişi ve parti açma.

    Parti açmak "basıldı" DEMEK DEĞİLDİR (D10): parti "basım onayı bekliyor"
    hâlinde açılır, PDF'i `…/pdf/`'ten alınır, işaret `…/confirm/` ile yazılır.
    Liste süzgeci: `status` (`PENDING` · `CONFIRMED` · `REVERTED` · `DISCARDED`).
    """

    serializer_class = LabelBatchSerializer
    pagination_class = KatalogSayfalama

    def get_queryset(self) -> Any:
        return selectors_kuyruk.label_batches(
            status=_choice_param(
                self.request.query_params,
                "status",
                list(selectors_kuyruk.BATCH_STATUS_CONDITIONS),
                "parti durumu",
            )
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gonderi = LabelBatchCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        if veri["from_queue"]:
            kimlikler = queue_service.queue_copy_ids(
                kind=veri["kind"],
                order=veri["order"],
                filters=_body_filters(veri),
                limit=veri["limit"],
            )
        else:
            kimlikler = veri["copies"]
        parti = queue_service.create_batch(
            kind=veri["kind"],
            template=veri["template"],
            calibration=veri.get("calibration"),
            spine_template=veri.get("spine_template"),
            spine_calibration=veri.get("spine_calibration"),
            include_qr=veri["include_qr"],
            order=veri["order"],
            start_cell=veri["start_cell"],
            copy_ids=kimlikler,
        )
        return Response(LabelBatchDetailSerializer(parti).data, status=status.HTTP_201_CREATED)


class _BatchView(APIView):
    def _batch(self, pk: int) -> LabelPrintBatch:
        parti: LabelPrintBatch = get_object_or_404(selectors_kuyruk.label_batches(), pk=pk)
        return parti


class LabelBatchDetailView(_BatchView):
    """`GET library/labels/batches/<pk>/` — parti ve nüshaları basım sırasında."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(LabelBatchDetailSerializer(self._batch(pk)).data)


class LabelBatchPdfView(_BatchView):
    """`GET library/labels/batches/<pk>/pdf/` — partinin PDF'i; İŞARETE DOKUNMAZ (D10)."""

    def get(self, request: Request, pk: int) -> FileResponse:
        parti = self._batch(pk)
        return _pdf_response(
            lambda: queue_service.render_batch_pdf(parti),
            queue_service.batch_pdf_filename(parti),
        )


class LabelBatchConfirmView(_BatchView):
    """`POST library/labels/batches/<pk>/confirm/` — "Basıldı olarak işaretle"."""

    def post(self, request: Request, pk: int) -> Response:
        parti = queue_service.confirm_batch(self._batch(pk))
        return Response(LabelBatchSerializer(parti).data)


class LabelBatchRevertView(_BatchView):
    """`POST library/labels/batches/<pk>/revert/` — basım işaretini geri alır.

    Yanıt: `{batch, restored, requeued, kept_verified}` — işareti önceki hâline
    dönen, bunlardan kuyruğa dönen ve barkodu okutularak doğrulandığı için
    işaretlerine (barkod ve sırt) dokunulmayan nüsha sayıları
    (`label_queue.revert_batch`).
    """

    def post(self, request: Request, pk: int) -> Response:
        sonuc = queue_service.revert_batch(self._batch(pk))
        return Response(
            {
                "batch": LabelBatchSerializer(sonuc["batch"]).data,
                "restored": sonuc["restored"],
                "requeued": sonuc["requeued"],
                "kept_verified": sonuc["kept_verified"],
            }
        )


class LabelBatchDiscardView(_BatchView):
    """`POST library/labels/batches/<pk>/discard/` — onaylanmamış partiden vazgeçer."""

    def post(self, request: Request, pk: int) -> Response:
        return Response(LabelBatchSerializer(queue_service.discard_batch(self._batch(pk))).data)


class LabelBatchReprintView(_BatchView):
    """`POST library/labels/batches/<pk>/reprint/` — aynı nüshalar, aynı sıra, yeni parti."""

    def post(self, request: Request, pk: int) -> Response:
        gonderi = LabelBatchReprintSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        yeni = queue_service.reprint_batch(
            self._batch(pk),
            kind=veri.get("kind"),
            template=veri.get("template"),
            # `null` açıkça "kalibrasyonsuz" demektir; alan hiç yoksa eski taşınır.
            calibration=veri["calibration"] if "calibration" in veri else queue_service.UNSET,
            start_cell=veri.get("start_cell"),
        )
        return Response(LabelBatchDetailSerializer(yeni).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Boş barkod aralıkları (yöntem B)
# ---------------------------------------------------------------------------
class BarcodeReservationListCreateView(generics.ListCreateAPIView[BarcodeReservation]):
    """`GET/POST library/barcode-reservations/` — aralık raporu ve numara ayırma.

    Numaralar nüsha sayacından alınır; ayrılan numara başka nüshaya asla
    verilmez, kullanılmayan numara iptal edilir (sayaca dönmez).
    """

    serializer_class = BarcodeReservationSerializer
    pagination_class = KatalogSayfalama

    def get_queryset(self) -> Any:
        return selectors_kuyruk.barcode_reservations()

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gonderi = BarcodeReservationCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        aralik = reservation_service.reserve(
            gonderi.validated_data["count"], note=gonderi.validated_data["note"]
        )
        return Response(
            BarcodeReservationDetailSerializer(aralik).data, status=status.HTTP_201_CREATED
        )


class BarcodeReservationCheckView(APIView):
    """`GET library/barcode-reservations/check/?code=` — hızlı kayıt ön denetimi (yazma YOK).

    Ön yüz eseri açmadan önce sorar: bağlanamayacak bir etiket için eser açılıp
    nüshasız kalmasın. Yanıt her zaman 200: `{bindable, kind, message, …}`.
    """

    def get(self, request: Request) -> Response:
        return Response(reservation_service.check_label(request.query_params.get("code", "")))


class _ReservationView(APIView):
    def _reservation(self, pk: int) -> BarcodeReservation:
        aralik: BarcodeReservation = get_object_or_404(
            selectors_kuyruk.barcode_reservations(), pk=pk
        )
        return aralik


class BarcodeReservationDetailView(_ReservationView):
    """`GET library/barcode-reservations/<pk>/` — aralık ve numaralarının durumu."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(BarcodeReservationDetailSerializer(self._reservation(pk)).data)


class BarcodeReservationPdfView(_ReservationView):
    """`GET library/barcode-reservations/<pk>/pdf/` — boş barkod etiketleri; İŞARETE DOKUNMAZ.

    Parametreler: `template` (zorunlu), `calibration`, `start_cell`, `barcodes`
    (virgülle ayrılmış; bozulan etiketin yeniden basımı — yalnız açık numaralar).
    """

    def get(self, request: Request, pk: int) -> FileResponse:
        aralik = self._reservation(pk)
        gonderi = ReservationPdfParamsSerializer(data=request.query_params)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        ham = str(veri.get("barcodes") or "").strip()
        numaralar = [parca for parca in ham.split(",") if parca.strip()] if ham else None
        return _pdf_response(
            lambda: reservation_service.render_pdf(
                aralik,
                template=veri["template"],
                calibration=veri.get("calibration"),
                start_cell=veri["start_cell"],
                barcodes=numaralar,
                include_qr=veri["include_qr"],
            ),
            reservation_service.pdf_filename(aralik),
        )


class BarcodeReservationConfirmPrintView(_ReservationView):
    """`POST library/barcode-reservations/<pk>/confirm-print/` — "Basıldı olarak işaretle"."""

    def post(self, request: Request, pk: int) -> Response:
        aralik = reservation_service.confirm_print(self._reservation(pk))
        return Response(BarcodeReservationSerializer(aralik).data)


class BarcodeReservationRevertPrintView(_ReservationView):
    """`POST library/barcode-reservations/<pk>/revert-print/` — basım işaretini geri alır."""

    def post(self, request: Request, pk: int) -> Response:
        aralik = reservation_service.revert_print(self._reservation(pk))
        return Response(BarcodeReservationSerializer(aralik).data)


class BarcodeReservationCancelView(_ReservationView):
    """`POST library/barcode-reservations/<pk>/cancel/` — kullanılmayan numaraları iptal eder.

    Gövde `{barcodes?, reason?}`; `barcodes` verilmezse aralığın bütün açık
    numaraları. İptal geri alınmaz, numara sayaca dönmez. Yanıt `{cancelled,
    reservation}`.
    """

    def post(self, request: Request, pk: int) -> Response:
        aralik = self._reservation(pk)
        gonderi = ReservationCancelSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        adet = reservation_service.cancel_numbers(
            aralik, barcodes=veri.get("barcodes"), reason=veri["reason"]
        )
        guncel = self._reservation(pk)
        return Response(
            {"cancelled": adet, "reservation": BarcodeReservationDetailSerializer(guncel).data}
        )


class CopyFromLabelView(APIView):
    """`POST library/copies/from-label/` — hızlı kayıtta önceden basılmış etiketi bağlar.

    Gövde nüsha alanları (`library/copies/` ile aynı) + `label_code` (kitaptaki
    etiketin okutulan kodu). Nüsha O numarayla açılır; etiket ayrılmış değilse,
    başka nüshaya bağlıysa ya da iptal edildiyse Türkçe ret (`fields.label_code`).
    Etiketsiz kitap için bugünkü yol geçerlidir (`library/copies/`).
    """

    def post(self, request: Request) -> Response:
        gonderi = CopyFromLabelSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        nusha = reservation_service.bind_label(
            label=veri.pop("label_code"),
            work=veri.pop("work"),
            acquisition=veri.pop("acquisition"),
            **veri,
        )
        return Response(CopyReadSerializer(nusha).data, status=status.HTTP_201_CREATED)
