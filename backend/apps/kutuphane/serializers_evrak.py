"""Evrak ve pano uçlarının serializer'ları — YALNIZ yönetici kipi yüzeyi (E2, E4, E13, E19, T15).

Buradaki yanıtlar kişi verisi taşır (ad, sınıf, okul no, kart no) ve yalnız
görevli kipi izin listesinde OLMAYAN uçlardan çıkar (CLAUDE.md §2-4).

**Profil yasağı** (§3): gecikmiş ödünç ve son işlemler satırları konu,
sınıflama ya da bölüm alanı TAŞIMAZ; alan listeleri anlık görüntüyle sabittir
(`tests/test_evrak_uclari.py`). İş kuralı serializer'da tekrarlanmaz: servis ve
belge modülleri Django `ValidationError` yükseltir, `kd_exception_handler` 400'e
çevirir.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import dolasim_belgeleri as belgeler
from apps.kutuphane.dolasim_belgeleri import MAX_ADRES, MAX_ILETISIM
from apps.kutuphane.labels.card import MAX_CARDS_PER_DOCUMENT
from apps.kutuphane.models import (
    LabelCalibration,
    LabelKind,
    LabelSheetTemplate,
    Loan,
    Membership,
)
from apps.kutuphane.selectors_dolasim import RecentTransaction

#: Tek istekte istenebilecek en çok pusula kişisi.
MAX_SLIP_SELECTION = 500


class MemberCardRowSerializer(serializers.ModelSerializer[Membership]):
    """Kart basımı kuyruğunun satırı: kim, hangi kart, basıldı mı. Sınıf yalnız bilgi ve sıradır."""

    full_name = serializers.CharField(read_only=True)
    member_type = serializers.CharField(read_only=True)
    member_type_display = serializers.CharField(source="get_member_type_display", read_only=True)
    class_label = serializers.SerializerMethodField()
    student_number = serializers.SerializerMethodField()
    card_no = serializers.CharField(read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "full_name",
            "member_type",
            "member_type_display",
            "class_label",
            "student_number",
            "card_no",
            "card_printed_at",
            "started_at",
        ]
        read_only_fields = fields

    def get_class_label(self, obj: Membership) -> str:
        return obj.student.class_label if obj.student is not None else ""

    def get_student_number(self, obj: Membership) -> str:
        return str(obj.student.student_number) if obj.student is not None else ""


class MemberCardSelectionSerializer(serializers.Serializer[Any]):
    """Seçilen üyelikler (kart basımı, işaretleme ve geri alma)."""

    membership_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=MAX_CARDS_PER_DOCUMENT,
        error_messages={
            "min_length": "Kart seçilmedi.",
            "max_length": f"Tek seferde en çok {MAX_CARDS_PER_DOCUMENT} kart seçilebilir.",
        },
    )


class MemberCardPdfRequestSerializer(MemberCardSelectionSerializer):
    """`POST library/member-cards/pdf/` — kart PDF'i; hiçbir işarete dokunmaz (D10).

    `template` verilmezse kart şablonu (tohum) kullanılır; `calibration` o
    şablonun yazıcı kalibrasyonudur. `cut_guides`: kartın çevresindeki kesim
    çizgisi (önceden kesilmiş kart tabakasında kapatılır).
    """

    template = serializers.PrimaryKeyRelatedField(
        queryset=LabelSheetTemplate.objects.filter(kind=LabelKind.CARD),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Kart şablonu bulunamadı."},
    )
    calibration = serializers.PrimaryKeyRelatedField(
        queryset=LabelCalibration.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Kalibrasyon kaydı bulunamadı."},
    )
    start_cell = serializers.IntegerField(min_value=1, required=False, default=1)
    cut_guides = serializers.BooleanField(required=False, default=True)


class OverdueLoanRowSerializer(serializers.ModelSerializer[Loan]):
    """Gecikmiş ödünç satırı (yönetici kipi). Konu/sınıflama alanı YOKTUR (profil yasağı)."""

    membership_id = serializers.IntegerField(read_only=True)
    full_name = serializers.SerializerMethodField()
    person_label = serializers.SerializerMethodField()
    is_student = serializers.SerializerMethodField()
    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    overdue_days = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "membership_id",
            "full_name",
            "person_label",
            "is_student",
            "barcode",
            "barcode_display",
            "work_title",
            "loaned_at",
            "due_date",
            "overdue_days",
        ]
        read_only_fields = fields

    def _uyelik(self, obj: Loan) -> Membership:
        if obj.membership is None:  # overdue_rows kişisiz ödüncü zaten süzer; savunma
            raise serializers.ValidationError("Ödüncün üyelik bağı yok.")
        return obj.membership

    def get_full_name(self, obj: Loan) -> str:
        return belgeler.person_name(self._uyelik(obj))

    def get_person_label(self, obj: Loan) -> str:
        return belgeler.person_label(self._uyelik(obj))

    def get_is_student(self, obj: Loan) -> bool:
        return self._uyelik(obj).student_id is not None

    def get_barcode_display(self, obj: Loan) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)

    def get_overdue_days(self, obj: Loan) -> int:
        return obj.overdue_days()


class OverdueScopeSerializer(serializers.Serializer[Any]):
    """Gecikmiş ödünç kapsamı: bütün okul, bir sınıf ya da şube (öğrenciler)."""

    class_level = serializers.IntegerField(
        min_value=0, max_value=12, required=False, allow_null=True
    )
    class_section = serializers.CharField(
        max_length=8, required=False, allow_blank=True, default="", trim_whitespace=True
    )


class OverdueSlipRequestSerializer(OverdueScopeSerializer):
    """`POST library/overdue-loans/slips/` — seçilen kişilerin (ya da kapsamın) pusulaları."""

    membership_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_SLIP_SELECTION,
    )


class PrivacyNoticeRequestSerializer(serializers.Serializer[Any]):
    """`POST library/documents/privacy-notice/` — başvuru bilgileri (saklanmaz, yalnız basılır)."""

    basvuru_adresi = serializers.CharField(
        max_length=MAX_ADRES, required=False, allow_blank=True, default=""
    )
    iletisim = serializers.CharField(
        max_length=MAX_ILETISIM, required=False, allow_blank=True, default=""
    )


class RecentTransactionSerializer(serializers.Serializer[Any]):
    """Son oturumdan bir ödünç ya da iade (T15; yönetici kipi). Konu/sınıflama YOK."""

    kind = serializers.CharField(read_only=True)
    kind_display = serializers.CharField(source="label", read_only=True)
    at = serializers.DateTimeField(read_only=True)
    loan_id = serializers.IntegerField(source="loan.pk", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="loan.copy.work.title", read_only=True)
    full_name = serializers.SerializerMethodField()
    person_label = serializers.SerializerMethodField()

    def get_barcode_display(self, obj: RecentTransaction) -> str:
        return barcode_module.format_barcode(obj.loan.copy.barcode)

    def get_full_name(self, obj: RecentTransaction) -> str:
        uyelik = obj.loan.membership
        return belgeler.person_name(uyelik) if uyelik is not None else ""

    def get_person_label(self, obj: RecentTransaction) -> str:
        uyelik = obj.loan.membership
        return belgeler.person_label(uyelik) if uyelik is not None else ""
