"""`kutuphane` API uçları — İNCE görünümler (View → Service → Model; ORM selectors'ta).

OYS'nin (Okul Yönetim Sistemi) `apps/kutuphane/views.py` dosyasından UYARLA
(tasarım §12): URL ön eki (`library/`), uç adları (`library-…`) ve alan adları
korundu; rol/izin dalları ve `created_by` düştü (yönetim yüzeyi hesapsızdır —
CLAUDE.md §4, tasarım §4.3). OYS `DefaultRouter` + `ModelViewSet` kullanıyordu;
burada `apps/okul` ile aynı düzen uygulanır: açık `path()` girdileri, ad alanı
yok, düz URL adları — kip izin listesi ve URL'leri dolaşan koruma testleri
(§5.10-8) bunlara dayanır.

**Görünümler iş kuralı YAZMAZ.** Katalog kuralları (nüsha açma, komisyon kararı
türü, bağış kararının kapsamı, politikanın müdürlük kararı şartı) servistedir ve
Django `ValidationError` yükseltir; `shared.exceptions.kd_exception_handler` onu
alan adlarıyla 400'e çevirir (`{code, message, fields}`). Burada yalnız sorgu
parametreleri çözülür ve servisin döndürdüğü nesne serileştirilir.

**Kapılar** (hiçbiri bu dosyada tekrarlanmaz):

* Kilitli ya da güvenlik dosyası kayıpken bütün `/api/` uçları 423 döner
  (`apps.okul.lock_middleware`) — şifreli alan taşıyan uçlar dahil.
* Görevli kipinde izin listesi dışındaki her uç 403 `kip_yetkisiz` döner
  (`apps.okul.kip_middleware`). Buradan izin listesinde YALNIZ katalog okuma
  vardır (F6, §4.4): `library-work-list`, `library-work-detail` ve
  `library-copy-list` GET — sorgu parametresi kuralıyla; görevli kipinde yanıt
  Ağ Kataloğunun alan listesine denk serializer'la daralır
  (`serializers_masa.GorevliEserSerializer`/`GorevliNushaSerializer`). Katalog
  DÜZENLEMEK masa işi değildir; yazma yöntemleri kapalıdır (CLAUDE.md §2-4).
* Yönetici parolası kurulmadan şifreli alana (bağışçı, komisyon adları) yazan
  istek `KeyMissingError` ile durur ve 409 `parola_gerekli` döner (§6.3-3).

**Sayfalama ZORUNLUDUR** (D9): liste uçları `apps.kutuphane.pagination`
sınıflarını kullanır, yanıt `{count, next, previous, results}`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from io import BytesIO
from typing import Any

from django.http import FileResponse
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import excel_template, selectors
from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    CopyStatus,
    DonationIntake,
    DonationIntakeItem,
    DonationIntakeStatus,
    LibraryPolicy,
    ResourceType,
    Section,
    Work,
)
from apps.kutuphane.pagination import KatalogSayfalama, ListeSayfalama
from apps.kutuphane.serializers import (
    AcquisitionSerializer,
    CommissionDecisionSerializer,
    CopyBulkCreateSerializer,
    CopyReadSerializer,
    CopyUpdateSerializer,
    CopyWriteSerializer,
    DonationCancelSerializer,
    DonationDecisionSerializer,
    DonationIntakeCreateSerializer,
    DonationIntakeItemSerializer,
    DonationIntakeSerializer,
    LibraryPolicySerializer,
    SectionSerializer,
    WorkSerializer,
)
from apps.kutuphane.serializers_masa import GorevliEserSerializer, GorevliNushaSerializer
from apps.kutuphane.services import catalog as catalog_service
from apps.kutuphane.services import commissions as commission_service
from apps.kutuphane.services import donations as donation_service
from apps.kutuphane.services import numbering as numbering_service
from apps.kutuphane.services import policy as policy_service
from apps.okul.kip import KIP

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: Boolean sorgu parametresinde "açık" sayılan değerler (`apps/okul/views.py` ile aynı).
TRUE_VALUES = frozenset({"true", "1"})


# ---------------------------------------------------------------------------
# Sorgu parametresi çözücüleri
# ---------------------------------------------------------------------------
def _int_param(params: Mapping[str, str], ad: str, etiket: str) -> int | None:
    """Sayısal süzgeç; boşsa `None`, sayısal değilse sözleşmeli 400.

    `isdigit()` KULLANILMAZ: Unicode basamaklarda ('²') doğru döner ve `int()`
    sonra patlar (`apps/okul/views.py` aynı dersi taşır). Sayısal olmayan değeri
    sessizce yutmak da yanlıştır — kullanıcı süzgecin çalıştığını sanır.
    """
    ham = str(params.get(ad, "")).strip()
    if not ham:
        return None
    try:
        return int(ham)
    except ValueError as exc:
        raise serializers.ValidationError({ad: f"{etiket} sayısal olmalıdır."}) from exc


def _bool_param(params: Mapping[str, str], ad: str) -> bool:
    return str(params.get(ad, "")).strip().lower() in TRUE_VALUES


def _choice_param(params: Mapping[str, str], ad: str, gecerli: Sequence[str], etiket: str) -> str:
    """Seçenek süzgeci; boşsa '', tanınmayan değerde sözleşmeli 400.

    Tanınmayan bir değeri boş liste ile karşılamak, kullanıcıya "kayıt yok"
    dedirtir; oysa süzgeç hatalıdır.
    """
    ham = str(params.get(ad, "")).strip()
    if not ham:
        return ""
    if ham not in gecerli:
        raise serializers.ValidationError({ad: f"Geçerli bir {etiket} seçin."})
    return ham


def _order_param(params: Mapping[str, str]) -> str:
    """Eser listesinin sıralama ekseni (`title` / `author` / `subject` / `newest`)."""
    ham = str(params.get("order", "")).strip()
    if not ham:
        return selectors.DEFAULT_WORK_ORDERING
    if ham not in selectors.WORK_ORDERINGS:
        eksenler = ", ".join(selectors.WORK_ORDERINGS)
        raise serializers.ValidationError(
            {"order": f"Sıralama şunlardan biri olmalıdır: {eksenler}."}
        )
    return ham


@contextmanager
def _sayac_hatalari() -> Iterator[None]:
    """Nüsha sayacının taşmasını sözleşmeli 400'e çevirir (Türkçe ileti korunur).

    `BarcodeRangeError` bir `ValueError`'dır; çevrilmezse sunucu hatası olurdu.
    Yılda 999999 nüsha bir okul için erişilmez bir sınırdır, ama sessiz çakışma
    yerine açık hata verme kuralı (bkz. `barcode.build_barcode`) uçta da sürer.
    """
    try:
        yield
    except barcode_module.BarcodeRangeError as exc:
        raise serializers.ValidationError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Katalog Excel şablonu (F1'den; tasarım §8.1)
# ---------------------------------------------------------------------------
class CatalogImportTemplateView(APIView):
    """GET → boş katalog Excel şablonu (Katalog + Sütunlar + Örnek sayfaları).

    Veritabanına dokunmaz: kurulum bitmeden, boş programda da indirilebilir.
    """

    def get(self, request: Request) -> FileResponse:
        return FileResponse(
            BytesIO(excel_template.build_catalog_template()),
            as_attachment=True,
            filename=excel_template.template_filename(),
            content_type=XLSX_CONTENT_TYPE,
        )


# ---------------------------------------------------------------------------
# Kütüphane politikası (tek satır)
# ---------------------------------------------------------------------------
class LibraryPolicyView(APIView):
    """`GET/PUT library/policy/` — kütüphane politikası (singleton).

    **PUT KISMİDİR** (OYS'den korunan davranış): gövdede gönderilmeyen alana
    dokunulmaz. Ayarlar ekranının bir sekmesinden yapılan kayıt, öbür sekmedeki
    ayarları varsayılana döndürmemelidir (`services.policy.update_policy`).
    Satır hiç yoksa GET kaydedilmemiş varsayılanları döndürür (okuma yazmaz).
    """

    def get(self, request: Request) -> Response:
        return Response(LibraryPolicySerializer(policy_service.load_policy()).data)

    def put(self, request: Request) -> Response:
        gonderi = LibraryPolicySerializer(data=request.data, partial=True)
        gonderi.is_valid(raise_exception=True)
        kayit: LibraryPolicy = policy_service.update_policy(**dict(gonderi.validated_data))
        return Response(LibraryPolicySerializer(kayit).data)


# ---------------------------------------------------------------------------
# Bölümler (kontrollü liste)
# ---------------------------------------------------------------------------
class SectionListCreateView(generics.ListCreateAPIView[Section]):
    """`GET/POST library/sections/` — bölüm listesi (sıra, sonra Türkçe ad)."""

    serializer_class = SectionSerializer
    pagination_class = ListeSayfalama

    def get_queryset(self) -> Any:
        return selectors.sections()

    def perform_create(self, serializer: serializers.BaseSerializer[Section]) -> None:
        serializer.instance = catalog_service.create_section(**dict(serializer.validated_data))


class SectionDetailView(generics.RetrieveUpdateDestroyAPIView[Section]):
    """`library/sections/<pk>/` — bölümü okur, günceller, yumuşak siler."""

    serializer_class = SectionSerializer

    def get_queryset(self) -> Any:
        return selectors.sections()

    def perform_update(self, serializer: serializers.BaseSerializer[Section]) -> None:
        assert serializer.instance is not None
        serializer.instance = catalog_service.update_section(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: Section) -> None:
        catalog_service.delete_section(instance)


# ---------------------------------------------------------------------------
# Eserler
# ---------------------------------------------------------------------------
class WorkListCreateView(generics.ListCreateAPIView[Work]):
    """`GET/POST library/works/` — Türkçe arama, üç eksenli sıralama, sayfalama.

    Sorgu parametreleri: `q` (serbest arama — ad, yazar, konu, ISBN),
    `section`, `resource_type`, `order` (`title`/`author`/`subject`/`newest`).
    Arama ham alanlarda DEĞİL `search_key` üzerinde yapılır ve sorgu da aynı
    katlamadan geçer (T7, D2); "şiir" ile "ŞİİR" aynı sonucu verir.
    """

    serializer_class = WorkSerializer
    pagination_class = KatalogSayfalama

    def get_serializer_class(self) -> Any:
        # F6: görevli kipinde katalog okuma açıktır, yanıt daralır (§4.4).
        return GorevliEserSerializer if KIP.gorevli_mi() else WorkSerializer

    def get_queryset(self) -> Any:
        params = self.request.query_params
        return selectors.works_with_copy_counts(
            q=params.get("q", ""),
            section_id=_int_param(params, "section", "Bölüm kimliği"),
            resource_type=_choice_param(
                params, "resource_type", ResourceType.values, "kaynak türü"
            ),
            order=_order_param(params),
        )

    def perform_create(self, serializer: serializers.BaseSerializer[Work]) -> None:
        serializer.instance = catalog_service.create_work(**dict(serializer.validated_data))


class WorkDetailView(generics.RetrieveUpdateDestroyAPIView[Work]):
    """`library/works/<pk>/` — eseri okur, günceller, yumuşak siler.

    Canlı nüshası olan eser silinemez (servis reddeder): önce nüshalar kayıttan
    düşülür ya da silinir.
    """

    serializer_class = WorkSerializer

    def get_serializer_class(self) -> Any:
        # F6: görevli kipinde yalnız GET açıktır ve yanıt daralır (§4.4).
        return GorevliEserSerializer if KIP.gorevli_mi() else WorkSerializer

    def get_queryset(self) -> Any:
        return selectors.works_with_copy_counts()

    def perform_update(self, serializer: serializers.BaseSerializer[Work]) -> None:
        assert serializer.instance is not None
        serializer.instance = catalog_service.update_work(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: Work) -> None:
        catalog_service.delete_work(instance)


# ---------------------------------------------------------------------------
# Nüshalar
# ---------------------------------------------------------------------------
def _copy_queryset(params: Mapping[str, str]) -> Any:
    """Nüsha listesinin ortak süzgeç çözümü (liste ve ayrıntı aynı kümeyi görür)."""
    return selectors.copies(
        work_id=_int_param(params, "work", "Eser kimliği"),
        section_id=_int_param(params, "section", "Bölüm kimliği"),
        # Parti süzgeci: toplu aktarımdan sonraki "bu partinin etiketlerini bas"
        # kısayolunun (§8.1, F4) bağlanacağı yer (`label_batch.acquisition`).
        acquisition_id=_int_param(params, "acquisition", "Edinim kimliği"),
        status=_choice_param(params, "status", CopyStatus.values, "durum"),
        barcode=params.get("barcode", ""),
        old_register_no=params.get("old_register_no", ""),
        only_loanable=_bool_param(params, "only_loanable"),
        only_unlabeled=_bool_param(params, "only_unlabeled"),
        include_terminal=not _bool_param(params, "exclude_terminal"),
    )


class CopyListCreateView(generics.ListCreateAPIView[Copy]):
    """`GET/POST library/copies/` — nüsha listesi ve tek nüsha açma.

    Sorgu parametreleri: `work`, `section`, `acquisition` (edinim partisi),
    `status`, `barcode` (okutulan ya da basılı biçim; TAM eşleşme),
    `old_register_no`, `only_loanable`, `only_unlabeled`, `exclude_terminal`.

    Yaratımda barkod ve kayıt no SAYAÇTAN gelir; gövdede gönderilirse servis
    reddeder. Aynı künyeden birden çok nüsha için `library/copies/bulk/`.
    """

    serializer_class = CopyReadSerializer
    pagination_class = KatalogSayfalama

    def get_serializer_class(self) -> Any:
        # F6: görevli kipinde katalog okuma açıktır, yanıt daralır (§4.4).
        return GorevliNushaSerializer if KIP.gorevli_mi() else CopyReadSerializer

    def get_queryset(self) -> Any:
        if KIP.gorevli_mi():
            # Görevliye Ağ Kataloğu gibi yalnız elde bulunan nüshalar (kayıttan
            # düşülen ve devredilen yok); süzgeçler izin listesinde sınırlıdır.
            params = self.request.query_params
            return selectors.copies(
                work_id=_int_param(params, "work", "Eser kimliği"),
                section_id=_int_param(params, "section", "Bölüm kimliği"),
                status=_choice_param(params, "status", CopyStatus.values, "durum"),
                only_loanable=_bool_param(params, "only_loanable"),
                include_terminal=False,
            ).select_related("work__section")
        return _copy_queryset(self.request.query_params)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gonderi = CopyWriteSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        with _sayac_hatalari():
            nusha = catalog_service.create_copy(
                work=veri.pop("work"), acquisition=veri.pop("acquisition"), **veri
            )
        return Response(CopyReadSerializer(nusha).data, status=status.HTTP_201_CREATED)


class CopyBulkCreateView(APIView):
    """`POST library/copies/bulk/` — aynı künyeden `count` nüsha (Excel "Nüsha Sayısı").

    Yanıt `{count, results}`: her nüsha AYRI bir numara alır ve numara asla
    yeniden kullanılmaz. Eski kayıt no tek nüshaya aittir; `count > 1` iken
    doluysa servis reddeder (§8.1).
    """

    def post(self, request: Request) -> Response:
        gonderi = CopyBulkCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        adet = int(veri.pop("count", 1))
        with _sayac_hatalari():
            nushalar = catalog_service.create_copies(
                work=veri.pop("work"),
                acquisition=veri.pop("acquisition"),
                count=adet,
                **veri,
            )
        return Response(
            {"count": len(nushalar), "results": CopyReadSerializer(nushalar, many=True).data},
            status=status.HTTP_201_CREATED,
        )


class CopyDetailView(generics.RetrieveUpdateDestroyAPIView[Copy]):
    """`library/copies/<pk>/` — nüshayı okur, betimsel alanlarını günceller, siler.

    Eser, edinim, barkod, kayıt no ve durum güncellemeyle DEĞİŞMEZ. Silme yalnız
    veri giriş hatası içindir ve numarayı serbest bırakmaz (servis).
    """

    serializer_class = CopyReadSerializer

    def get_queryset(self) -> Any:
        return selectors.copies()

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kismi = bool(kwargs.pop("partial", False))
        nusha = self.get_object()
        gonderi = CopyUpdateSerializer(nusha, data=request.data, partial=kismi)
        gonderi.is_valid(raise_exception=True)
        guncel = catalog_service.update_copy(nusha, **dict(gonderi.validated_data))
        return Response(CopyReadSerializer(guncel).data)

    def perform_destroy(self, instance: Copy) -> None:
        catalog_service.delete_copy(instance)


# ---------------------------------------------------------------------------
# Komisyon kararları
# ---------------------------------------------------------------------------
class CommissionDecisionListCreateView(generics.ListCreateAPIView[CommissionDecision]):
    """`GET/POST library/commission-decisions/` — Seçim ve Ayıklama Komisyonu kararları.

    Sorgu parametresi: `decision_type`. Başkan adı ve katılımcılar ŞİFRELİDİR:
    parola kurulmadan yazan istek 409 `parola_gerekli` alır.
    """

    serializer_class = CommissionDecisionSerializer
    pagination_class = KatalogSayfalama

    def get_queryset(self) -> Any:
        return selectors.commission_decisions(
            decision_type=_choice_param(
                self.request.query_params,
                "decision_type",
                CommissionDecisionType.values,
                "karar türü",
            )
        )

    def perform_create(self, serializer: serializers.BaseSerializer[CommissionDecision]) -> None:
        serializer.instance = commission_service.create_commission_decision(
            **dict(serializer.validated_data)
        )


class CommissionDecisionDetailView(generics.RetrieveUpdateDestroyAPIView[CommissionDecision]):
    """`library/commission-decisions/<pk>/` — kullanılmış kararın TÜRÜ değiştirilemez (D7)."""

    serializer_class = CommissionDecisionSerializer

    def get_queryset(self) -> Any:
        return selectors.commission_decisions()

    def perform_update(self, serializer: serializers.BaseSerializer[CommissionDecision]) -> None:
        assert serializer.instance is not None
        serializer.instance = commission_service.update_commission_decision(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: CommissionDecision) -> None:
        commission_service.delete_commission_decision(instance)


# ---------------------------------------------------------------------------
# Edinimler
# ---------------------------------------------------------------------------
class AcquisitionListCreateView(generics.ListCreateAPIView[Acquisition]):
    """`GET/POST library/acquisitions/` — edinim partileri (Md. 10/5 + kayıt-içi girişler).

    Sorgu parametresi: `method`. Bağışta komisyon kararı zorunludur ve türü
    denetlenir (Md. 10/3, D7 — serviste). `source_note` (bağışçı) ŞİFRELİDİR.
    """

    serializer_class = AcquisitionSerializer
    pagination_class = KatalogSayfalama

    def get_queryset(self) -> Any:
        return selectors.acquisitions(
            method=_choice_param(
                self.request.query_params, "method", AcquisitionMethod.values, "edinim yolu"
            )
        )

    def perform_create(self, serializer: serializers.BaseSerializer[Acquisition]) -> None:
        serializer.instance = catalog_service.create_acquisition(**dict(serializer.validated_data))


class AcquisitionDetailView(generics.RetrieveUpdateDestroyAPIView[Acquisition]):
    """`library/acquisitions/<pk>/` — nüshası olan edinim silinemez (servis)."""

    serializer_class = AcquisitionSerializer

    def get_queryset(self) -> Any:
        return selectors.acquisitions()

    def perform_update(self, serializer: serializers.BaseSerializer[Acquisition]) -> None:
        assert serializer.instance is not None
        serializer.instance = catalog_service.update_acquisition(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: Acquisition) -> None:
        catalog_service.delete_acquisition(instance)


# ---------------------------------------------------------------------------
# Bağış ön kaydı (SU-23, Md. 10/3)
# ---------------------------------------------------------------------------
class DonationIntakeListCreateView(generics.ListCreateAPIView[DonationIntake]):
    """`GET/POST library/donation-intakes/` — komisyon kararına kadar NÜSHA AÇILMAZ.

    Sorgu parametresi: `status`. Yaratımda kalemler (`items`) aynı istekte
    gönderilebilir; bağışçı adı ŞİFRELİDİR.
    """

    serializer_class = DonationIntakeSerializer
    pagination_class = KatalogSayfalama

    def get_queryset(self) -> Any:
        return selectors.donation_intakes(
            status=_choice_param(
                self.request.query_params, "status", DonationIntakeStatus.values, "durum"
            )
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        gonderi = DonationIntakeCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = dict(gonderi.validated_data)
        kalemler = [dict(kalem) for kalem in veri.pop("items", [])]
        kayit = donation_service.create_intake(items=kalemler, **veri)
        return Response(DonationIntakeSerializer(kayit).data, status=status.HTTP_201_CREATED)


class DonationIntakeDetailView(generics.RetrieveUpdateDestroyAPIView[DonationIntake]):
    """`library/donation-intakes/<pk>/` — karar işlendikten sonra değiştirilemez (servis)."""

    serializer_class = DonationIntakeSerializer

    def get_queryset(self) -> Any:
        return selectors.donation_intakes()

    def perform_update(self, serializer: serializers.BaseSerializer[DonationIntake]) -> None:
        assert serializer.instance is not None
        serializer.instance = donation_service.update_intake(
            serializer.instance, **dict(serializer.validated_data)
        )

    def perform_destroy(self, instance: DonationIntake) -> None:
        donation_service.delete_intake(instance)


class _IntakeChildView(APIView):
    """Ön kaydın alt kaynaklarının ortak kayıt çözümü (404 Türkçedir)."""

    def _intake(self, pk: int) -> DonationIntake:
        kayit: DonationIntake = get_object_or_404(selectors.donation_intakes(), pk=pk)
        return kayit

    def _item(self, pk: int, item_pk: int) -> DonationIntakeItem:
        kalem: DonationIntakeItem = get_object_or_404(self._intake(pk).items, pk=item_pk)
        return kalem


class DonationIntakeItemCreateView(_IntakeChildView):
    """`POST library/donation-intakes/<pk>/items/` — ön kayda kalem ekler.

    Bağış listesi günler içinde tamamlanır; karar işlendikten sonra kalem
    eklenemez (servis).
    """

    def post(self, request: Request, pk: int) -> Response:
        gonderi = DonationIntakeItemSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        kalem = donation_service.add_item(self._intake(pk), **dict(gonderi.validated_data))
        return Response(DonationIntakeItemSerializer(kalem).data, status=status.HTTP_201_CREATED)


class DonationIntakeItemDetailView(_IntakeChildView):
    """`library/donation-intakes/<pk>/items/<item_pk>/` — kalemi günceller ya da siler."""

    def put(self, request: Request, pk: int, item_pk: int) -> Response:
        return self._guncelle(request, pk, item_pk, kismi=False)

    def patch(self, request: Request, pk: int, item_pk: int) -> Response:
        return self._guncelle(request, pk, item_pk, kismi=True)

    def delete(self, request: Request, pk: int, item_pk: int) -> Response:
        donation_service.remove_item(self._item(pk, item_pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _guncelle(self, request: Request, pk: int, item_pk: int, *, kismi: bool) -> Response:
        kalem = self._item(pk, item_pk)
        gonderi = DonationIntakeItemSerializer(kalem, data=request.data, partial=kismi)
        gonderi.is_valid(raise_exception=True)
        guncel = donation_service.update_item(kalem, **dict(gonderi.validated_data))
        return Response(DonationIntakeItemSerializer(guncel).data)


class DonationIntakeDecisionView(_IntakeChildView):
    """`POST library/donation-intakes/<pk>/decision/` — komisyon kararını uygular.

    Kabul edilen kalemler TEK İŞLEMDE kataloglanır (edinim + eser + nüshalar),
    reddedilenler gerekçesiyle işaretlenir ve kayıtta kalır. Her kalem tam
    olarak bir kez kararlanmalıdır; eksik karar bütün işlemi reddeder (servis).
    Hepsi reddedilirse edinim AÇILMAZ, ön kayıt yine "Karar işlendi" olur.
    """

    def post(self, request: Request, pk: int) -> Response:
        gonderi = DonationDecisionSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        kayit = self._intake(pk)
        sonuc = donation_service.apply_decision(kayit, **dict(gonderi.validated_data))
        edinim = sonuc["acquisition"]
        return Response(
            {
                "intake": DonationIntakeSerializer(kayit).data,
                "accepted": sonuc["accepted"],
                "rejected": sonuc["rejected"],
                "acquisition": edinim.pk if edinim is not None else None,
                "work_count": len(sonuc["works"]),
                # F8: nüshaları katalogdaki var olan esere eklenen kalemler.
                "linked_work_count": len(sonuc["linked_works"]),
                "copy_count": len(sonuc["copies"]),
            }
        )


class DonationIntakeMatchesView(_IntakeChildView):
    """`GET library/donation-intakes/<pk>/matches/` — kalemlerin katalogdaki karşılığı (F8).

    Kararı uygulamadan önce ekran her kalem için birebir eşleşmeyi (nüshalar o
    esere eklenecek) ve şüpheli adayları (kendiliğinden bağlanmaz; kullanıcı
    `work_links` ile seçer) gösterir. Kayıt yazmaz; kişisel veri yok.
    """

    def get(self, request: Request, pk: int) -> Response:
        kayit = self._intake(pk)

        def _eser(work: Work) -> dict[str, Any]:
            return {
                "id": work.pk,
                "title": work.title,
                "authors": work.authors,
                "publisher": work.publisher,
                "publish_year": work.publish_year,
                "isbn13": work.isbn13,
            }

        sonuclar = []
        for kalem in kayit.items.all().order_by("pk"):
            eslesme = donation_service.item_matches(kalem)
            sonuclar.append(
                {
                    "item": kalem.pk,
                    "exact": _eser(eslesme.exact) if eslesme.exact is not None else None,
                    "suspects": [_eser(w) for w in eslesme.suspects],
                }
            )
        return Response({"results": sonuclar})


class DonationIntakeCancelView(_IntakeChildView):
    """`POST library/donation-intakes/<pk>/cancel/` — bağış geri verildi, liste yanlış girildi…"""

    def post(self, request: Request, pk: int) -> Response:
        gonderi = DonationCancelSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        kayit = donation_service.cancel_intake(
            self._intake(pk), reason=gonderi.validated_data["reason"]
        )
        return Response(DonationIntakeSerializer(kayit).data)


# ---------------------------------------------------------------------------
# Koleksiyon özeti ve sayaç
# ---------------------------------------------------------------------------
class LibraryStatsView(APIView):
    """`GET library/stats/` — kişisiz koleksiyon özeti (pano kartı, Md. 7 eşiği).

    KİŞİSEL VERİ İÇERMEZ: yalnız eser ve nüsha sayıları, durum kırılımı, bölüm
    sayısı ve sıradaki nüsha numarası. `next_barcode` yalnız GÖSTERİMDİR, sayacı
    ilerletmez; sayaç dolduysa `null` döner.

    Md. 7/1 eşiği (`in_stock_count`) ELDE BULUNAN nüshadır; `copy_count` kayıt
    defterinin toplamıdır ve kayıttan düşülenleri de sayar (bkz.
    `selectors.collection_summary`).
    """

    def get(self, request: Request) -> Response:
        ozet = dict(selectors.collection_summary())
        ozet["next_barcode"] = self._siradaki_barkod()
        return Response(ozet)

    @staticmethod
    def _siradaki_barkod() -> str | None:
        yil = timezone.localdate().year
        try:
            ham = barcode_module.build_barcode(yil, numbering_service.peek_next_sequence(yil))
        except barcode_module.BarcodeRangeError:
            return None
        return barcode_module.format_barcode(ham)
