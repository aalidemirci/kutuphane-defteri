"""Üyelik uçlarının serializer'ları — YALNIZ yönetici kipi yüzeyi (tasarım §4.4, §6.2).

Buradaki hiçbir serializer görevli kipinde kullanılmaz: görevli kipinde kartla
üye çözme yalnız ad ve kalan hakkı döndürür ve o daraltılmış yanıt masa
uçlarının işidir (M kolu). Bu dosyanın yanıtları kişi verisi taşır (ad, okul
no, kart no, sınıf) ve yalnız yönetici kipindeki uçlardan çıkar.

Kurallar (`serializers.py` ile aynı):

* İş kuralı serializer'da TEKRARLANMAZ; servis (`services.memberships`)
  Django `ValidationError` yükseltir, `kd_exception_handler` 400'e çevirir.
* Kart no, durum ve tarihler salt okunurdur: kart no yalnız servisten
  (`issue_card_number`) gelir, durum yalnız sonlandırma/ayrılış yolundan değişir.
* Sayılar KİŞİ bazındadır (`selectors_dolasim` modül başlığı) ve liste için
  TEK sorguyla hesaplanıp bağlamla (`context["sayilar"]`) verilir.

**Profil yasağı** (§3): ödünç geçmişi serializer'ı konu, sınıflama ya da bölüm
alanı TAŞIMAZ; alan listesi anlık görüntüyle sabittir
(`tests/test_uyelik_uclari.py`).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import (
    MANUAL_TERMINATION_REASONS,
    CardlessReason,
    LibraryPolicy,
    Loan,
    Membership,
    OverrideReason,
    TerminationReason,
)
from apps.kutuphane.selectors_dolasim import MembershipRequestRow

#: Tek istekte istek listesinden açılabilecek en çok üyelik (bir şube ≤ ~40; sigorta).
MAX_REQUEST_BATCH = 2000


class MembershipSerializer(serializers.ModelSerializer[Membership]):
    """Üyelik (yönetici kipi): kişi, tür, kart, durum ve kişi bazında sayılar."""

    member_type = serializers.CharField(read_only=True)
    member_type_display = serializers.CharField(source="get_member_type_display", read_only=True)
    full_name = serializers.CharField(read_only=True)
    class_label = serializers.SerializerMethodField()
    student_number = serializers.SerializerMethodField()
    card_no = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    termination_reason_display = serializers.CharField(
        source="get_termination_reason_display", read_only=True
    )
    open_loan_count = serializers.SerializerMethodField()
    overdue_loan_count = serializers.SerializerMethodField()
    loan_limit = serializers.SerializerMethodField()
    remaining_quota = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "student",
            "personnel",
            "member_type",
            "member_type_display",
            "full_name",
            "class_label",
            "student_number",
            "card_no",
            "card_printed_at",
            "status",
            "status_display",
            "requested_at",
            "started_at",
            "terminated_at",
            "termination_reason",
            "termination_reason_display",
            "open_loan_count",
            "overdue_loan_count",
            "loan_limit",
            "remaining_quota",
        ]
        read_only_fields = fields

    def _policy(self) -> LibraryPolicy:
        kural = self.context.get("policy")
        if not isinstance(kural, LibraryPolicy):
            kural = LibraryPolicy.load()
            self.context["policy"] = kural
        return kural

    def _sayilar(self, obj: Membership) -> tuple[int, int]:
        """(açık, gecikmiş) — listede bağlamdan, tekil yanıtta sorgudan."""
        sayilar = self.context.get("sayilar")
        if isinstance(sayilar, dict):
            deger: tuple[int, int] = sayilar.get(selectors_dolasim.person_key(obj), (0, 0))
            return deger
        return (
            selectors_dolasim.open_loan_count(obj),
            selectors_dolasim.overdue_loan_count(obj),
        )

    def get_class_label(self, obj: Membership) -> str:
        return obj.student.class_label if obj.student is not None else ""

    def get_student_number(self, obj: Membership) -> str:
        return str(obj.student.student_number) if obj.student is not None else ""

    def get_open_loan_count(self, obj: Membership) -> int:
        return self._sayilar(obj)[0]

    def get_overdue_loan_count(self, obj: Membership) -> int:
        return self._sayilar(obj)[1]

    def get_loan_limit(self, obj: Membership) -> int:
        return selectors_dolasim.loan_limit(obj, policy=self._policy())

    def get_remaining_quota(self, obj: Membership) -> int:
        if not obj.is_active or not obj.person_is_active:
            return 0
        return max(0, self.get_loan_limit(obj) - self.get_open_loan_count(obj))


class MembershipCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/memberships/` — tek kişiye üyelik: öğrenci YA DA personel."""

    student_id = serializers.IntegerField(required=False, min_value=1)
    personnel_id = serializers.IntegerField(required=False, min_value=1)
    requested_at = serializers.DateField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if ("student_id" in attrs) == ("personnel_id" in attrs):
            raise serializers.ValidationError("Üyelik için bir öğrenci ya da bir personel seçin.")
        return attrs


class MembershipTerminateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/memberships/<pk>/terminate/` — neden KAPALI LİSTEDEN (D12)."""

    reason = serializers.ChoiceField(
        choices=[(kod, TerminationReason(kod).label) for kod in MANUAL_TERMINATION_REASONS],
        error_messages={
            "invalid_choice": "Sonlandırma nedenini listeden seçin.",
            "required": "Sonlandırma nedeni zorunludur.",
            "blank": "Sonlandırma nedeni zorunludur.",
        },
    )


class MembershipRequestQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """`GET library/membership-requests/?class_level=&class_section=` — şube seçimi."""

    class_level = serializers.IntegerField(min_value=0, max_value=12)
    class_section = serializers.CharField(max_length=8, trim_whitespace=True)


class MembershipRequestApplySerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/membership-requests/` — seçilen öğrencilere toplu üyelik (§9-2)."""

    student_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=MAX_REQUEST_BATCH,
        error_messages={"min_length": "Üye yapılacak öğrenci seçilmedi."},
    )
    requested_at = serializers.DateField(required=False)


class MembershipRequestRowSerializer(serializers.Serializer[Any]):
    """İstek listesi satırı: şubedeki aktif öğrenci ve üyelik durumu."""

    student_id = serializers.IntegerField(source="student.pk", read_only=True)
    full_name = serializers.CharField(source="student.full_name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)
    class_label = serializers.CharField(source="student.class_label", read_only=True)
    is_member = serializers.SerializerMethodField()
    membership_id = serializers.SerializerMethodField()

    def get_is_member(self, obj: MembershipRequestRow) -> bool:
        return obj.membership is not None

    def get_membership_id(self, obj: MembershipRequestRow) -> int | None:
        return obj.membership.pk if obj.membership is not None else None


class MemberLoanSerializer(serializers.ModelSerializer[Loan]):
    """Üyenin ödünç kaydı satırı (YALNIZ yönetici kipi).

    Konu, sınıflama ve bölüm alanı YOKTUR (profil yasağı, §3). İstisna ve
    kartsız ödüncün yalnız gerekçe ETİKETİ gösterilir; istisna açıklaması
    (serbest metin) bu listeye çıkmaz.
    """

    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    overdue_days = serializers.SerializerMethodField()
    has_override = serializers.BooleanField(read_only=True)
    override_reason_display = serializers.SerializerMethodField()
    cardless_reason_display = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "barcode",
            "barcode_display",
            "work_title",
            "loaned_at",
            "due_date",
            "returned_at",
            "status",
            "status_display",
            "overdue_days",
            "has_override",
            "override_reason_display",
            "cardless",
            "cardless_reason_display",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: Loan) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)

    def get_overdue_days(self, obj: Loan) -> int:
        return obj.overdue_days()

    def get_override_reason_display(self, obj: Loan) -> str:
        kod = str(obj.override_reason or "")
        return str(OverrideReason(kod).label) if kod in OverrideReason.values else ""

    def get_cardless_reason_display(self, obj: Loan) -> str:
        kod = str(obj.cardless_reason or "")
        return str(CardlessReason(kod).label) if kod in CardlessReason.values else ""
