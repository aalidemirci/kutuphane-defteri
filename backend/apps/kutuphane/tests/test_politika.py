"""Kütüphane politikası — tek satır, mevzuat sınırları, müdürlük kararı şartı (AT-4)."""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.kutuphane.models import LibraryPolicy
from apps.kutuphane.services import policy as policy_service


@pytest.mark.django_db
class TestPolitika:
    def test_ilk_kayitta_varsayilanlar_yazilir(self) -> None:
        policy = policy_service.update_policy(max_loans_student=2)
        assert policy.pk == LibraryPolicy.SINGLETON_PK
        assert policy.max_loans_student == 2
        assert policy.max_loans_teacher == 5
        assert LibraryPolicy.objects.count() == 1

    def test_ikinci_kayit_ayni_satiri_gunceller(self) -> None:
        policy_service.update_policy(max_loans_student=2)
        policy_service.update_policy(max_loans_teacher=4)
        assert LibraryPolicy.objects.count() == 1
        policy = policy_service.load_policy()
        assert (policy.max_loans_student, policy.max_loans_teacher) == (2, 4)

    def test_gonderilmeyen_alana_dokunulmaz(self) -> None:
        policy_service.update_policy(block_loan_if_overdue=False)
        policy_service.update_policy(popular_min_members=8)
        policy = policy_service.load_policy()
        assert policy.block_loan_if_overdue is False
        assert policy.popular_min_members == 8

    def test_ogrenci_siniri_ucu_asamaz(self) -> None:
        """Md. 18 üst sınırı: validator ile zorlanır."""
        with pytest.raises(ValidationError) as hata:
            policy_service.update_policy(max_loans_student=4)
        assert "max_loans_student" in hata.value.message_dict

    def test_ogretmen_siniri_besi_asamaz(self) -> None:
        with pytest.raises(ValidationError):
            policy_service.update_policy(max_loans_teacher=6)

    def test_odunc_suresi_sabittir(self) -> None:
        assert policy_service.LOAN_PERIOD_DAYS == 15

    def test_personel_odunc_secenegi_karar_bilgisi_ister(self) -> None:
        with pytest.raises(ValidationError) as hata:
            policy_service.update_policy(staff_loans_enabled=True)
        alanlar = hata.value.message_dict
        assert "staff_loans_decision_date" in alanlar
        assert "staff_loans_decision_no" in alanlar

    def test_personel_odunc_secenegi_kararla_acilir(self) -> None:
        policy = policy_service.update_policy(
            staff_loans_enabled=True,
            staff_loans_decision_date=date(2026, 9, 15),
            staff_loans_decision_no="2026/41",
        )
        assert policy.staff_loans_enabled is True

    def test_secenek_kapaninca_karar_bilgisi_temizlenir(self) -> None:
        policy_service.update_policy(
            staff_loans_enabled=True,
            staff_loans_decision_date=date(2026, 9, 15),
            staff_loans_decision_no="2026/41",
        )
        policy = policy_service.update_policy(staff_loans_enabled=False)
        assert policy.staff_loans_decision_date is None
        assert policy.staff_loans_decision_no == ""

    def test_kapali_gun_kaydirmasi_varsayilan_aciktir(self) -> None:
        """Ara tatil ve yarıyıl kaydırması okulun tercihidir; ayarla kapatılabilir."""
        policy = policy_service.load_policy()
        assert policy.shift_due_date_on_school_break is True
        kapali = policy_service.update_policy(shift_due_date_on_school_break=False)
        assert kapali.shift_due_date_on_school_break is False

    def test_kip_sureleri_politikada_tutulur(self) -> None:
        policy = policy_service.update_policy(idle_minutes=5, admin_max_minutes=45)
        assert (policy.idle_minutes, policy.admin_max_minutes) == (5, 45)

    def test_cok_okunanlar_esigi_en_az_ikidir(self) -> None:
        """Profil yasağı (tasarım §3): eşik tek üyeye indirilemez."""
        with pytest.raises(ValidationError):
            policy_service.update_policy(popular_min_members=1)
