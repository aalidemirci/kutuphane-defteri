"""İlişik listesi, yıl akışları ve F7 evrak uçlarının serializer'ları — YALNIZ yönetici kipi.

Yanıtlar kişi verisi taşır (ad, sınıf, okul no) ve yalnız görevli kipi izin
listesinde OLMAYAN uçlardan çıkar (§4.4 "ilişik" kapalı). Alan listeleri modül
sabitleridir ve anlık görüntüyle sınanır (`tests/test_ilisik_uclari.py`, T13).

**Profil yasağı** (CLAUDE.md §2-5): satırlarda konu, sınıflama ya da bölüm alanı
YOKTUR; açık işler yalnız nüsha, kaynak adı, tarih ve durum taşır. İş kuralı
burada tekrarlanmaz: belge ve seçici modülleri Django `ValidationError` yükseltir,
`kd_exception_handler` 400'e çevirir.
"""

from __future__ import annotations

from typing import Any, Final

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ilisik as ilisik
from apps.kutuphane.ilisik_belgeleri import MAX_CERTIFICATES
from apps.kutuphane.models import Delivery, Loan, LossDamageCase
from apps.kutuphane.teslim_belgeleri import MAX_ROWS

#: Tek istekte en çok yıl sonu pusulası kişisi (E4 sınırıyla aynı ölçek).
MAX_SLIP_PERSONS: Final = 500

CLEARANCE_ROW_FIELDS: Final = (
    "person_type",
    "person_id",
    "full_name",
    "person_label",
    "student_number",
    "group",
    "is_graduating",
    "status_text",
    "left_at",
    "in_leave_pool",
    "is_clear",
    "open_loan_count",
    "overdue_loan_count",
    "open_delivery_count",
    "open_case_count",
    "loans",
    "deliveries",
    "cases",
)
CLEARANCE_LOAN_FIELDS: Final = (
    "id",
    "barcode",
    "barcode_display",
    "work_title",
    "loaned_at",
    "due_date",
    "overdue_days",
)
CLEARANCE_DELIVERY_FIELDS: Final = (
    "id",
    "barcode",
    "barcode_display",
    "work_title",
    "delivered_on",
    "expected_return",
    "document_no",
)
CLEARANCE_CASE_FIELDS: Final = (
    "id",
    "case_type",
    "case_type_display",
    "resolution",
    "resolution_display",
    "barcode",
    "barcode_display",
    "work_title",
    "reported_on",
)
SECTION_ROW_FIELDS: Final = (
    "section_id",
    "section_label",
    "school_year_name",
    "is_graduating",
    "is_active_year",
    "delivery_count",
    "document_numbers",
    "open_case_count",
)


def _barkod(obj: Any) -> str:
    return barcode_module.format_barcode(obj.copy.barcode)


class ClearanceLoanSerializer(serializers.ModelSerializer[Loan]):
    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    overdue_days = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = list(CLEARANCE_LOAN_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: Loan) -> str:
        return _barkod(obj)

    def get_overdue_days(self, obj: Loan) -> int:
        return obj.overdue_days()


class ClearanceDeliverySerializer(serializers.ModelSerializer[Delivery]):
    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)

    class Meta:
        model = Delivery
        fields = list(CLEARANCE_DELIVERY_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: Delivery) -> str:
        return _barkod(obj)


class ClearanceCaseSerializer(serializers.ModelSerializer[LossDamageCase]):
    case_type_display = serializers.CharField(source="get_case_type_display", read_only=True)
    resolution_display = serializers.CharField(source="get_resolution_display", read_only=True)
    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)

    class Meta:
        model = LossDamageCase
        fields = list(CLEARANCE_CASE_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: LossDamageCase) -> str:
        return _barkod(obj)


class ClearanceRowSerializer(serializers.Serializer[Any]):
    """İlişik listesinin satırı (`selectors_ilisik.ClearanceRow`)."""

    person_type = serializers.CharField(read_only=True)
    person_id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    person_label = serializers.CharField(read_only=True)
    student_number = serializers.CharField(read_only=True)
    group = serializers.CharField(read_only=True)
    is_graduating = serializers.BooleanField(read_only=True)
    status_text = serializers.CharField(read_only=True)
    left_at = serializers.DateField(read_only=True)
    in_leave_pool = serializers.BooleanField(read_only=True)
    is_clear = serializers.BooleanField(read_only=True)
    open_loan_count = serializers.SerializerMethodField()
    overdue_loan_count = serializers.SerializerMethodField()
    open_delivery_count = serializers.SerializerMethodField()
    open_case_count = serializers.SerializerMethodField()
    loans = ClearanceLoanSerializer(many=True, read_only=True)
    deliveries = ClearanceDeliverySerializer(many=True, read_only=True)
    cases = ClearanceCaseSerializer(many=True, read_only=True)

    def get_open_loan_count(self, obj: ilisik.ClearanceRow) -> int:
        return len(obj.loans)

    def get_overdue_loan_count(self, obj: ilisik.ClearanceRow) -> int:
        return obj.overdue_count()

    def get_open_delivery_count(self, obj: ilisik.ClearanceRow) -> int:
        return len(obj.deliveries)

    def get_open_case_count(self, obj: ilisik.ClearanceRow) -> int:
        return len(obj.cases)


class SectionDeliveryRowSerializer(serializers.Serializer[Any]):
    """Şubenin (sınıf kitaplığının) açık teslimleri — kişisiz."""

    section_id = serializers.IntegerField(source="section.pk", read_only=True)
    section_label = serializers.CharField(source="label", read_only=True)
    school_year_name = serializers.CharField(read_only=True)
    is_graduating = serializers.BooleanField(read_only=True)
    is_active_year = serializers.BooleanField(read_only=True)
    delivery_count = serializers.SerializerMethodField()
    document_numbers = serializers.ListField(child=serializers.CharField(), read_only=True)
    open_case_count = serializers.SerializerMethodField()

    def get_delivery_count(self, obj: ilisik.SectionDeliveryRow) -> int:
        return len(obj.deliveries)

    def get_open_case_count(self, obj: ilisik.SectionDeliveryRow) -> int:
        return len(obj.cases)


# ---------------------------------------------------------------------------
# İstekler
# ---------------------------------------------------------------------------
class ClearanceQuerySerializer(serializers.Serializer[Any]):
    """İlişik listesi süzgeci (sorgu dizesi)."""

    state = serializers.ChoiceField(
        choices=list(ilisik.STATES),
        required=False,
        default=ilisik.STATE_OPEN,
        error_messages={"invalid_choice": "Geçerli bir liste durumu seçin."},
    )
    group = serializers.ChoiceField(
        choices=list(ilisik.GROUP_FILTERS),
        required=False,
        allow_blank=True,
        default="",
        error_messages={"invalid_choice": "Geçerli bir kapsam seçin."},
    )
    person_type = serializers.ChoiceField(
        choices=["student", "personnel"],
        required=False,
        allow_blank=True,
        default="",
        error_messages={"invalid_choice": "Geçerli bir kişi türü seçin."},
    )
    obligation = serializers.ChoiceField(
        choices=list(ilisik.OBLIGATIONS),
        required=False,
        default=ilisik.OBLIGATION_ALL,
        error_messages={"invalid_choice": "Geçerli bir iş türü seçin."},
    )
    class_level = serializers.IntegerField(
        min_value=0, max_value=12, required=False, allow_null=True
    )
    class_section = serializers.CharField(
        max_length=8, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    search = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default="", trim_whitespace=True
    )

    def filtre(self) -> ilisik.ClearanceFilter:
        veri = self.validated_data
        seviye = veri.get("class_level")
        return ilisik.ClearanceFilter(
            state=str(veri.get("state") or ilisik.STATE_OPEN),
            group=str(veri.get("group") or ""),
            class_level=int(seviye) if seviye is not None else None,
            class_section=str(veri.get("class_section") or ""),
            search=str(veri.get("search") or ""),
            obligation=str(veri.get("obligation") or ilisik.OBLIGATION_ALL),
            person_type=str(veri.get("person_type") or ""),
        )


def _kimlikler(max_length: int, mesaj: str) -> serializers.ListField:
    return serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        max_length=max_length,
        error_messages={"max_length": mesaj},
    )


class CertificateRequestSerializer(serializers.Serializer[Any]):
    """`POST library/clearance/certificates/` — belge istenen kişiler."""

    student_ids = _kimlikler(
        MAX_CERTIFICATES, f"Tek seferde en çok {MAX_CERTIFICATES} kişinin belgesi basılabilir."
    )
    personnel_ids = _kimlikler(
        MAX_CERTIFICATES, f"Tek seferde en çok {MAX_CERTIFICATES} kişinin belgesi basılabilir."
    )


class YearEndSlipRequestSerializer(serializers.Serializer[Any]):
    """`POST library/year-end/slips/` — yıl sonu pusulaları: seçilen kişiler ya da kapsam.

    `return_by` pusulaya "en geç … tarihine kadar" diye basılır; SAKLANMAZ.
    """

    student_ids = _kimlikler(MAX_SLIP_PERSONS, "Seçim çok büyük; şube şube basın.")
    personnel_ids = _kimlikler(MAX_SLIP_PERSONS, "Seçim çok büyük; şube şube basın.")
    group = serializers.ChoiceField(
        choices=list(ilisik.GROUP_FILTERS),
        required=False,
        allow_blank=True,
        default="",
        error_messages={"invalid_choice": "Geçerli bir kapsam seçin."},
    )
    class_level = serializers.IntegerField(
        min_value=0, max_value=12, required=False, allow_null=True
    )
    class_section = serializers.CharField(
        max_length=8, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    return_by = serializers.DateField(required=False, allow_null=True)


class DeliveryListQuerySerializer(serializers.Serializer[Any]):
    """`GET library/deliveries/pdf/` — belge no YA DA şube YA DA öğretmen."""

    document_no = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    section = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    personnel = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class TakeBackReportRequestSerializer(serializers.Serializer[Any]):
    """`POST library/deliveries/take-back-report/` — `{delivery_ids}` ya da `{document_no}`."""

    delivery_ids = _kimlikler(MAX_ROWS, f"Tek dökümde en çok {MAX_ROWS} satır olabilir.")
    document_no = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default="", trim_whitespace=True
    )
