"""Sayım serializer'ları (F9) — gövde biçimi burada, kural serviste (`services.stocktake`).

`serializers.py`'nin üç kuralı burada da geçerlidir: iş kuralı TEKRARLANMAZ (kurul,
durdurma, sınıflandırma, onay `services.stocktake`'tedir), durum alanları salt
okunurdur (geçişler kendi uçlarından yapılır), şifreli alanlar olağan metin gibi
görünür — kurul adları ve harcama yetkilileri YALNIZ sayım AYRINTISINDA; listede
yoktur.

**Kişisel veri.** Sayım kalemi kişisizdir: kalem yanıtında ödünç alanın, teslim alan
öğretmenin ya da kayıp/hasar dosyası sorumlusunun kimliği YOKTUR (E10: fazla/noksan
sayfaları VİF'e bağlanıp muhasebe birimine gider — TMY 10/1-g, 32/8). Dosyadan
yalnız türü (kayıp/hasar) ve çözümü gelir. Alan listeleri anlık görüntüyle sınanır.
Görevli kipinde okutma yanıtı ayrıca daralır: yalnız sonuç, ileti, barkod ve eser adı
(`STAFF_SCAN_FIELDS`, madde 24).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import (
    LOAN_BASIS_CHOICES,
    REPAIR_BASIS_CHOICES,
    SECTION_DELIVERY_BASIS_CHOICES,
    TEACHER_DELIVERY_BASIS_CHOICES,
    StockTake,
    StockTakeItem,
    Work,
)
from apps.kutuphane.serializers_ayiklama import _GerekceEslemesi
from apps.kutuphane.services.stocktake import (
    MAX_SCANS_PER_REQUEST,
    MEMBERS_MAX,
    NAME_MAX,
    NOTES_MAX,
    TEXT_MAX,
)

_ZORUNLU: dict[str, Any] = {
    "blank": "Bu alan boş bırakılamaz.",
    "required": "Bu alan zorunludur.",
    "null": "Bu alan zorunludur.",
}
_TARIH: dict[str, Any] = {"invalid": "Geçerli bir tarih girin."}
_SECIM: dict[str, Any] = {"invalid_choice": "Geçerli bir seçenek seçin."}
#: Sayım kodu: okuyucu girdisi (rakamların dışındaki karakterleri servis atar).
SCAN_CODE_MAX = 64
#: Kurulun her kategoride seçebildikleri (tek kaynak `models`; alan adı → değerler).
BASIS_CHOICES_BY_FIELD: dict[str, tuple[str, ...]] = {
    "loan_basis": LOAN_BASIS_CHOICES,
    "section_delivery_basis": SECTION_DELIVERY_BASIS_CHOICES,
    "teacher_delivery_basis": TEACHER_DELIVERY_BASIS_CHOICES,
    "repair_basis": REPAIR_BASIS_CHOICES,
}
#: Okutma sonucunun GÖREVLİ KİPİNDEKİ alanları (madde 24, 25.09.2026 kullanıcı kararı):
#: yalnız okutma sonucu, barkod ve eser adı — kalem, özet, kayda göre durum ve kişi YOK.
#: Anlık görüntüyle sınanır (T13; `tests/test_sayim_uclari.py`).
STAFF_SCAN_FIELDS: tuple[str, ...] = ("code", "message", "barcode", "barcode_display", "work_title")


def _secenekler(degerler: tuple[str, ...], kategori: str = "") -> list[tuple[str, str]]:
    return [(deger, selectors_sayim.basis_label(kategori, deger)) for deger in degerler]


def staff_scan_result(sonuc: Any) -> dict[str, str]:
    """Görevli kipinde okutma sonucunun daralmış gövdesi (`STAFF_SCAN_FIELDS`).

    Eser adı yalnız anlık görüntüdeki nüshanın eseridir; sayım fazlasında boştur (kod ve
    ileti yeter). Nüshanın kayda göre durumu ve kimde olduğu YAZILMAZ.
    """
    kalem = sonuc.item
    nusha = kalem.copy if kalem is not None else None
    barkod = nusha.barcode if nusha is not None else str(sonuc.barcode or "")
    veri = {
        "code": str(sonuc.code),
        "message": str(sonuc.message),
        "barcode": barkod,
        "barcode_display": barcode_module.format_barcode(barkod) if barkod else "",
        "work_title": nusha.work.title if nusha is not None else "",
    }
    return {alan: veri[alan] for alan in STAFF_SCAN_FIELDS}


# ---------------------------------------------------------------------------
# Sayım
# ---------------------------------------------------------------------------
class StockTakeListSerializer(serializers.ModelSerializer[StockTake]):
    """Liste satırı — kişi adı YOK."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = StockTake
        fields = [
            "id",
            "status",
            "status_display",
            "fiscal_year",
            "round",
            "tmy_stop",
            "service_pause",
            "created_at",
            "started_at",
            "completed_at",
            "approved_on",
            "cancelled_at",
        ]
        read_only_fields = fields


class StockTakeDetailSerializer(serializers.ModelSerializer[StockTake]):
    """Sayım ayrıntısı: kurul ve harcama yetkilileri (şifreli alanlardan), iki seçenek AYRI
    satırda, kurulun seçimleri ve kişisiz sayılar."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    loan_basis_display = serializers.CharField(source="get_loan_basis_display", read_only=True)
    section_delivery_basis_display = serializers.CharField(
        source="get_section_delivery_basis_display", read_only=True
    )
    teacher_delivery_basis_display = serializers.CharField(
        source="get_teacher_delivery_basis_display", read_only=True
    )
    repair_basis_display = serializers.SerializerMethodField()
    locks_active = serializers.BooleanField(read_only=True)
    options = serializers.SerializerMethodField()
    basis_lines = serializers.SerializerMethodField()
    basis_choices = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = StockTake
        fields = [
            "id",
            "status",
            "status_display",
            "fiscal_year",
            "round",
            "committee_chair",
            "committee_property_officer",
            "committee_members",
            "tmy_stop",
            "tmy_stop_requested_on",
            "tmy_stop_by_name",
            "tmy_stop_on",
            "service_pause",
            "service_pause_decision",
            "loan_basis",
            "loan_basis_display",
            "section_delivery_basis",
            "section_delivery_basis_display",
            "teacher_delivery_basis",
            "teacher_delivery_basis_display",
            "repair_basis",
            "repair_basis_display",
            "notes",
            "created_at",
            "started_at",
            "round2_started_at",
            "completed_at",
            "approved_by_name",
            "approved_on",
            "approved_at",
            "surplus_acquisition",
            "cancelled_at",
            "cancel_reason",
            "locks_active",
            "options",
            "basis_lines",
            "basis_choices",
            "summary",
        ]
        read_only_fields = fields

    def get_options(self, obj: StockTake) -> list[dict[str, Any]]:
        return selectors_sayim.options_lines(obj)

    def get_basis_lines(self, obj: StockTake) -> list[dict[str, Any]]:
        return selectors_sayim.basis_lines(obj)

    def get_repair_basis_display(self, obj: StockTake) -> str:
        """Onarım seçeneğinin adı kararın sözcükleriyle (K2 — `REPAIR_BASIS_LABELS`)."""
        return selectors_sayim.basis_label("repair", obj.repair_basis)

    def get_basis_choices(self, obj: StockTake) -> dict[str, list[dict[str, str]]]:
        """Kurulun her kategori için seçebildikleri (kural sunucudadır; ekran kopyalamaz)."""
        kategoriler = {alan: k for k, alan in selectors_sayim.BASIS_CATEGORY_FIELDS.items()}
        return {
            alan: [
                {"value": d, "label": selectors_sayim.basis_label(kategoriler[alan], d)}
                for d in degerler
            ]
            for alan, degerler in BASIS_CHOICES_BY_FIELD.items()
        }

    def get_summary(self, obj: StockTake) -> dict[str, Any]:
        return selectors_sayim.summary(obj)


class StockTakeWriteSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/stocktakes/` ve taslakta `PATCH` — biçim; kurallar serviste."""

    fiscal_year = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=2000,
        max_value=2999,
        error_messages={
            "invalid": "Mali yıl sayı olmalıdır.",
            "min_value": "Mali yıl dört haneli bir yıl olmalıdır.",
            "max_value": "Mali yıl dört haneli bir yıl olmalıdır.",
        },
    )
    committee_chair = serializers.CharField(max_length=NAME_MAX, required=False, allow_blank=True)
    committee_property_officer = serializers.CharField(
        max_length=NAME_MAX, required=False, allow_blank=True
    )
    committee_members = serializers.CharField(
        max_length=MEMBERS_MAX, required=False, allow_blank=True, trim_whitespace=False
    )
    tmy_stop = serializers.BooleanField(required=False)
    tmy_stop_requested_on = serializers.DateField(
        required=False, allow_null=True, error_messages=_TARIH
    )
    tmy_stop_by_name = serializers.CharField(max_length=NAME_MAX, required=False, allow_blank=True)
    tmy_stop_on = serializers.DateField(required=False, allow_null=True, error_messages=_TARIH)
    service_pause = serializers.BooleanField(required=False)
    service_pause_decision = serializers.CharField(
        max_length=NAME_MAX, required=False, allow_blank=True
    )
    loan_basis = serializers.ChoiceField(
        choices=_secenekler(LOAN_BASIS_CHOICES), required=False, error_messages=_SECIM
    )
    section_delivery_basis = serializers.ChoiceField(
        choices=_secenekler(SECTION_DELIVERY_BASIS_CHOICES), required=False, error_messages=_SECIM
    )
    teacher_delivery_basis = serializers.ChoiceField(
        choices=_secenekler(TEACHER_DELIVERY_BASIS_CHOICES), required=False, error_messages=_SECIM
    )
    repair_basis = serializers.ChoiceField(
        choices=_secenekler(REPAIR_BASIS_CHOICES, "repair"), required=False, error_messages=_SECIM
    )
    notes = serializers.CharField(max_length=NOTES_MAX, required=False, allow_blank=True)


class StockTakeApproveSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST …/approve/` — harcama yetkilisinin onayı (ad ŞİFRELİ saklanır)."""

    approved_by_name = serializers.CharField(max_length=NAME_MAX, error_messages=_ZORUNLU)
    approved_on = serializers.DateField(error_messages={**_TARIH, **_ZORUNLU})
    #: Onaylanmayan noksan ya da hasar önerisi kalemleri → gerekçe.
    not_approved = _GerekceEslemesi()


class StockTakeCancelSerializer(serializers.Serializer[dict[str, Any]]):
    reason = serializers.CharField(
        max_length=TEXT_MAX, required=False, allow_blank=True, default="", trim_whitespace=True
    )


# ---------------------------------------------------------------------------
# Okutma ve sayım fazlası
# ---------------------------------------------------------------------------
class StockTakeScanSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST …/scan/` — tek okutma `{barcode}` ya da okuyucu kuyruğu `{barcodes}`."""

    barcode = serializers.CharField(
        max_length=SCAN_CODE_MAX, required=False, allow_blank=True, trim_whitespace=True
    )
    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=SCAN_CODE_MAX, allow_blank=True),
        required=False,
        max_length=MAX_SCANS_PER_REQUEST,
        error_messages={
            "not_a_list": "Kodlar liste olarak gönderilmelidir.",
            "max_length": f"Bir istekte en çok {MAX_SCANS_PER_REQUEST} kod okutulur.",
        },
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        tek = "barcode" in attrs
        coklu = "barcodes" in attrs
        if tek == coklu:
            raise serializers.ValidationError(
                "Okutulan kodu (`barcode`) ya da kod listesini (`barcodes`) gönderin."
            )
        attrs["values"] = [attrs["barcode"]] if tek else list(attrs["barcodes"])
        return attrs


class StockTakeSurplusCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST …/surplus/` — etiketsiz ya da okutulamayan kitap (kodsuz sayım fazlası)."""

    note = serializers.CharField(max_length=TEXT_MAX, error_messages=_ZORUNLU)
    work = serializers.PrimaryKeyRelatedField(
        queryset=Work.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages={"does_not_exist": "Seçilen eser bulunamadı."},
    )


class StockTakeSurplusUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """`PATCH …/items/<item_pk>/` — fazlanın eseri, açıklaması, "kayda alınmayacak" işareti."""

    note = serializers.CharField(max_length=TEXT_MAX, required=False, allow_blank=True)
    work = serializers.PrimaryKeyRelatedField(
        queryset=Work.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Seçilen eser bulunamadı."},
    )
    excluded = serializers.BooleanField(required=False)


class StockTakeItemSerializer(serializers.ModelSerializer[StockTakeItem]):
    """Sayım kalemi — KİŞİSİZ (modül belgesi). Fazlada nüsha alanları boştur."""

    barcode = serializers.SerializerMethodField()
    barcode_display = serializers.SerializerMethodField()
    work = serializers.SerializerMethodField()
    work_title = serializers.SerializerMethodField()
    work_authors = serializers.SerializerMethodField()
    call_number = serializers.SerializerMethodField()
    section_name = serializers.SerializerMethodField()
    class_library = serializers.SerializerMethodField()
    copy_status = serializers.SerializerMethodField()
    copy_status_display = serializers.SerializerMethodField()
    expected_status_display = serializers.CharField(
        source="get_expected_status_display", read_only=True
    )
    basis_display = serializers.SerializerMethodField()
    result_display = serializers.CharField(source="get_result_display", read_only=True)
    found_via_display = serializers.CharField(source="get_found_via_display", read_only=True)
    outcome_display = serializers.CharField(source="get_outcome_display", read_only=True)
    write_off_path_display = serializers.CharField(
        source="get_write_off_path_display", read_only=True
    )
    case_type = serializers.SerializerMethodField()
    case_resolution_display = serializers.SerializerMethodField()
    is_surplus = serializers.BooleanField(read_only=True)
    surplus_barcode_display = serializers.SerializerMethodField()
    surplus_work_title = serializers.SerializerMethodField()
    created_copy_barcode = serializers.SerializerMethodField()
    surplus_bound_barcode = serializers.SerializerMethodField()

    class Meta:
        model = StockTakeItem
        fields = [
            "id",
            "copy",
            "barcode",
            "barcode_display",
            "work",
            "work_title",
            "work_authors",
            "call_number",
            "section",
            "section_name",
            "class_library",
            "copy_status",
            "copy_status_display",
            "expected_status",
            "expected_status_display",
            "delivery_kind",
            "basis",
            "basis_display",
            "basis_fallback",
            "result",
            "result_display",
            "found_in_round",
            "found_via",
            "found_via_display",
            "scanned_at",
            "status_at_completion",
            "damage_write_off",
            "case",
            "case_type",
            "case_resolution_display",
            "outcome",
            "outcome_display",
            "write_off_path",
            "write_off_path_display",
            "outcome_note",
            "is_surplus",
            "surplus_barcode",
            "surplus_barcode_display",
            "surplus_copy",
            "surplus_work",
            "surplus_work_title",
            "surplus_note",
            "surplus_excluded",
            "created_copy",
            "created_copy_barcode",
            "surplus_bound_barcode",
        ]
        read_only_fields = fields

    def get_barcode(self, obj: StockTakeItem) -> str:
        return obj.copy.barcode if obj.copy is not None else ""

    def get_barcode_display(self, obj: StockTakeItem) -> str:
        return barcode_module.format_barcode(obj.copy.barcode) if obj.copy is not None else ""

    def get_work(self, obj: StockTakeItem) -> int | None:
        return obj.copy.work_id if obj.copy is not None else None

    def get_work_title(self, obj: StockTakeItem) -> str:
        return obj.copy.work.title if obj.copy is not None else ""

    def get_work_authors(self, obj: StockTakeItem) -> str:
        return obj.copy.work.authors if obj.copy is not None else ""

    def get_call_number(self, obj: StockTakeItem) -> str:
        return obj.copy.work.call_number if obj.copy is not None else ""

    def get_section_name(self, obj: StockTakeItem) -> str:
        return obj.section.name if obj.section is not None else ""

    def get_basis_display(self, obj: StockTakeItem) -> str:
        """Onarımdaki nüshada onarım seçeneğinin adı (K2), öbürlerinde `CountBasis` adı."""
        return selectors_sayim.item_basis_label(obj)

    def get_class_library(self, obj: StockTakeItem) -> str:
        """Yerinde sayılan sınıf kitaplığının etiketi (şube kişisel veri değildir)."""
        return obj.class_section.class_label if obj.class_section is not None else ""

    def get_copy_status(self, obj: StockTakeItem) -> str:
        return obj.copy.status if obj.copy is not None else ""

    def get_copy_status_display(self, obj: StockTakeItem) -> str:
        return obj.copy.get_status_display() if obj.copy is not None else ""

    def get_case_type(self, obj: StockTakeItem) -> str:
        return obj.case.case_type if obj.case is not None else ""

    def get_case_resolution_display(self, obj: StockTakeItem) -> str:
        return obj.case.get_resolution_display() if obj.case is not None else ""

    def get_surplus_barcode_display(self, obj: StockTakeItem) -> str:
        return barcode_module.format_barcode(obj.surplus_barcode) if obj.surplus_barcode else ""

    def get_surplus_work_title(self, obj: StockTakeItem) -> str:
        return obj.surplus_work.title if obj.surplus_work is not None else ""

    def get_created_copy_barcode(self, obj: StockTakeItem) -> str:
        return obj.created_copy.barcode if obj.created_copy is not None else ""

    def get_surplus_bound_barcode(self, obj: StockTakeItem) -> str:
        """Etiketi sayım SIRASINDA bir nüshaya bağlanan fazlanın nüshası (basılı barkod).

        Kitap o nüshayla kayda girmiştir; onay onu ikinci kez kayda almaz (F9 düzeltme turu).
        Yalnız karar verilmemiş (onaylanmamış) fazla için sorulur.
        """
        if not obj.is_surplus or not obj.surplus_barcode or obj.outcome:
            return ""
        nusha = selectors_sayim.bound_surplus_copy(obj)
        return barcode_module.format_barcode(nusha.barcode) if nusha is not None else ""
