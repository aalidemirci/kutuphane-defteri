"""Etiket uçları — şablon, yazıcı kalibrasyonu, kalibrasyon sayfası ve PDF önizleme.

| Uç | Ad | İş |
|---|---|---|
| `GET/POST library/label-templates/` | `library-label-template-list` | Şablon listesi (ilk açılışta hazır şablonlar yazılır) ve yeni şablon |
| `GET/PUT/PATCH/DELETE library/label-templates/<pk>/` | `library-label-template-detail` | Şablon düzenleme, varsayılan yapma, silme |
| `GET/POST library/label-calibrations/` | `library-label-calibration-list` | Yazıcı kalibrasyonları (`?template=` süzgeci) |
| `GET/PUT/PATCH/DELETE library/label-calibrations/<pk>/` | `library-label-calibration-detail` | Ölçülen kaymanın kaydı |
| `POST library/labels/calibration/` | `library-label-calibration` | Kalibrasyon sayfası PDF'i (E1) |
| `POST library/labels/preview/` | `library-label-preview` | Etiket PDF'i — **hiçbir kayıt yazmaz** |

URL önekleri OYS'den korunur (`library/label-templates`, `library/labels/calibration`).
OYS'nin `labels/print/` ucu PDF üretirken nüshaları "basıldı" işaretliyordu; burada
PDF üretmek basım kaydı DEĞİLDİR (D10). Basım partisi, kuyruk ve "Basıldı olarak
işaretle" basım kuyruğu kolunun uçlarıdır; bu uçlar onlarla ad paylaşmaz.

Kapılar başka katmandadır: kilitliyken 423, görevli kipinde 403 `kip_yetkisiz`
(hiçbiri izin listesinde değildir — etiket basmak yönetici işidir). Kişisel veri
yoktur: etiket kitap künyesi, numara ve kısa okul adı taşır.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from django.db.models import QuerySet
from django.http import FileResponse
from django.utils import timezone
from rest_framework import generics
from rest_framework import serializers as drf_serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.labels import seed
from apps.kutuphane.labels import services as label_services
from apps.kutuphane.labels.calibration import DOCUMENT_NAME as CALIBRATION_DOCUMENT_NAME
from apps.kutuphane.labels.calibration import render_calibration_sheet
from apps.kutuphane.labels.content import (
    LabelItem,
    LabelSelection,
    items_from_barcodes,
    items_from_copies,
)
from apps.kutuphane.labels.render import DOCUMENT_NAMES, build_parts, render_labels
from apps.kutuphane.labels.serializers import (
    CalibrationSheetRequestSerializer,
    LabelCalibrationSerializer,
    LabelPreviewRequestSerializer,
    LabelSheetTemplateSerializer,
)
from apps.kutuphane.models import Copy, LabelCalibration, LabelKind, LabelSheetTemplate
from apps.kutuphane.pagination import ListeSayfalama
from apps.kutuphane.services import barcode_reservations

PDF_CONTENT_TYPE = "application/pdf"
#: Yanıtta basımın tabaka sayısı (parça başına) — ön yüz "N tabaka" diyebilsin.
SHEETS_HEADER = "X-KD-Tabaka-Sayisi"


def pdf_filename(
    document_name: str, today: date | None = None, *, scope: tuple[str, ...] = ()
) -> str:
    """İndirme adı: belge adı + kapsam + yerel tarih (sözlük §3, `lib/download.ts::dosyaAdi`).

    'Sırt-Etiketi_24.09.2026.pdf'; boş barkod etiketinde kapsam basılan numaraların
    aralığıdır: 'Boş-Barkod-Etiketi_2026-000101_2026-000103_24.09.2026.pdf' (aralığın
    PDF'iyle aynı biçim — `barcode_reservations.pdf_filename`). İç kimlik geçmez.
    """
    gun = today or timezone.localdate()
    parcalar = [document_name.replace(" ", "-"), *scope, f"{gun:%d.%m.%Y}"]
    return "_".join(parcalar) + ".pdf"


def _pdf_response(icerik: bytes, filename: str) -> FileResponse:
    yanit = FileResponse(
        BytesIO(icerik), as_attachment=False, filename=filename, content_type=PDF_CONTENT_TYPE
    )
    yanit["Cache-Control"] = "no-store"
    return yanit


# ---------------------------------------------------------------------------
# Şablonlar
# ---------------------------------------------------------------------------
class LabelTemplateListCreateView(generics.ListCreateAPIView[LabelSheetTemplate]):
    """`GET/POST library/label-templates/` — tür, sonra Türkçe ad sırası (`?kind=`)."""

    serializer_class = LabelSheetTemplateSerializer
    pagination_class = ListeSayfalama

    def get_queryset(self) -> QuerySet[LabelSheetTemplate]:
        qs = LabelSheetTemplate.objects.all()
        tur = str(self.request.query_params.get("kind", "")).strip()
        if tur:
            if tur not in (LabelKind.BARCODE, LabelKind.SPINE):
                raise drf_serializers.ValidationError({"kind": "Geçerli bir şablon türü seçin."})
            qs = qs.filter(kind=tur)
        else:
            # Üye kartı şablonu (F6, `labels/card.py`) bu ekranda düzenlenmez;
            # kart basımı ekranı onu `library/member-cards/template/` ile okur.
            qs = qs.exclude(kind=LabelKind.CARD)
        return qs.order_by("kind", "name_sort_key", "pk")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Any:
        # Hazır şablonlar ilk kullanımda yazılır (migration yok — seed.py).
        seed.ensure_default_templates()
        return super().list(request, *args, **kwargs)

    def perform_create(
        self, serializer: drf_serializers.BaseSerializer[LabelSheetTemplate]
    ) -> None:
        serializer.instance = label_services.create_template(**dict(serializer.validated_data))


class LabelTemplateDetailView(generics.RetrieveUpdateDestroyAPIView[LabelSheetTemplate]):
    """`GET/PUT/PATCH/DELETE library/label-templates/<pk>/` — silme yumuşaktır."""

    serializer_class = LabelSheetTemplateSerializer
    queryset = LabelSheetTemplate.objects.all()

    def perform_update(
        self, serializer: drf_serializers.BaseSerializer[LabelSheetTemplate]
    ) -> None:
        assert serializer.instance is not None
        serializer.instance = label_services.update_template(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: LabelSheetTemplate) -> None:
        label_services.delete_template(instance)


# ---------------------------------------------------------------------------
# Yazıcı kalibrasyonları
# ---------------------------------------------------------------------------
class LabelCalibrationListCreateView(generics.ListCreateAPIView[LabelCalibration]):
    """`GET/POST library/label-calibrations/` — `?template=<id>` süzgeci; Türkçe yazıcı adı sırası."""

    serializer_class = LabelCalibrationSerializer
    pagination_class = ListeSayfalama

    def get_queryset(self) -> QuerySet[LabelCalibration]:
        qs = LabelCalibration.objects.select_related("template").filter(
            template__deleted_at__isnull=True
        )
        ham = str(self.request.query_params.get("template", "")).strip()
        if ham:
            try:
                qs = qs.filter(template_id=int(ham))
            except ValueError as exc:
                raise drf_serializers.ValidationError(
                    {"template": "Şablon kimliği sayısal olmalıdır."}
                ) from exc
        return qs.order_by("template_id", "printer_name_sort_key", "pk")

    def perform_create(self, serializer: drf_serializers.BaseSerializer[LabelCalibration]) -> None:
        serializer.instance = label_services.create_calibration(**dict(serializer.validated_data))


class LabelCalibrationDetailView(generics.RetrieveUpdateDestroyAPIView[LabelCalibration]):
    """`GET/PUT/PATCH/DELETE library/label-calibrations/<pk>/`."""

    serializer_class = LabelCalibrationSerializer

    def get_queryset(self) -> QuerySet[LabelCalibration]:
        return LabelCalibration.objects.select_related("template").filter(
            template__deleted_at__isnull=True
        )

    def perform_update(self, serializer: drf_serializers.BaseSerializer[LabelCalibration]) -> None:
        assert serializer.instance is not None
        serializer.instance = label_services.update_calibration(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: LabelCalibration) -> None:
        label_services.delete_calibration(instance)


# ---------------------------------------------------------------------------
# PDF'ler
# ---------------------------------------------------------------------------
class LabelCalibrationSheetView(APIView):
    """`POST library/labels/calibration/` `{template, calibration?}` — kalibrasyon sayfası PDF'i."""

    def post(self, request: Request) -> FileResponse:
        istek = CalibrationSheetRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        veri = istek.validated_data
        pdf = render_calibration_sheet(veri["template"], veri.get("calibration"))
        return _pdf_response(pdf, pdf_filename(CALIBRATION_DOCUMENT_NAME))


def copies_in_order(copy_ids: list[int]) -> list[Copy]:
    """İstenen nüshalar, İSTENEN SIRADA (basım sırası çağıranındır — D20).

    Silinmiş ya da bulunamayan kimlik 400 verir: listeden sessizce düşen bir
    nüsha, kullanıcının saydığı etiketle basılanı ayırır.
    """
    bulunan = {n.pk: n for n in Copy.objects.select_related("work").filter(pk__in=copy_ids)}
    if any(pk not in bulunan for pk in copy_ids):
        raise drf_serializers.ValidationError(
            {"copy_ids": "Seçilen nüshalardan bazıları bulunamadı."}
        )
    return [bulunan[pk] for pk in copy_ids]


class LabelPreviewView(APIView):
    """`POST library/labels/preview/` — etiket PDF'i; nüshalara "basıldı" YAZMAZ (D10)."""

    def post(self, request: Request) -> FileResponse:
        istek = LabelPreviewRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        veri = istek.validated_data
        secim = LabelSelection(veri["content"])
        kalemler: list[LabelItem]
        if secim == LabelSelection.BLANK_BARCODE:
            # Yalnız açık ayrılmış numaralar: iptal edilmiş, bağlı ya da sayacın
            # henüz vermediği numaraya boş etiket basılmaz (aralığın PDF'iyle aynı kural).
            kalemler = items_from_barcodes(barcode_reservations.open_numbers(veri["barcodes"]))
        else:
            kalemler = items_from_copies(copies_in_order(veri["copy_ids"]))
        parcalar = build_parts(
            secim,
            template=veri["template"],
            calibration=veri.get("calibration"),
            spine_template=veri.get("spine_template"),
            spine_calibration=veri.get("spine_calibration"),
        )
        belge = DOCUMENT_NAMES[secim]
        sonuc = render_labels(
            kalemler,
            parcalar,
            start_cell=veri["start_cell"],
            include_qr=veri["include_qr"],
            title=belge,
        )
        kapsam: tuple[str, ...] = ()
        if secim == LabelSelection.BLANK_BARCODE:
            # Numaralar sabit uzunlukta rakamdır: metin sırası sayı sırasıdır.
            numaralar = sorted(kalem.barcode for kalem in kalemler)
            kapsam = tuple(
                barcode_module.format_barcode(kod) for kod in (numaralar[0], numaralar[-1])
            )
        yanit = _pdf_response(sonuc.pdf, pdf_filename(belge, scope=kapsam))
        yanit[SHEETS_HEADER] = str(sonuc.sheets_per_part)
        return yanit
