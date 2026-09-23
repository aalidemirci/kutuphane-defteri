"""Kütüphane politikası ve koleksiyon özeti uçları (F2 sözleşmesi §4).

Politikanın iki kuralı burada uçtan uca sınanır: **ödünç süresi ayar DEĞİLDİR**
(D19, Md. 18 "on beş gün") ve **PUT kısmidir** — bir sekmeden yapılan kayıt öbür
sekmenin ayarlarını varsayılana döndürmez.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane.models import CopyStatus, LibraryPolicy
from apps.kutuphane.services import policy as policy_service
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

POLITIKA = "/api/v1/library/policy/"
OZET = "/api/v1/library/stats/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


class TestPolitikaUcu:
    def test_satir_yokken_varsayilanlar_doner_ve_yazilmaz(self, istemci: APIClient) -> None:
        yanit = istemci.get(POLITIKA)

        govde: dict[str, Any] = yanit.json()
        assert yanit.status_code == 200
        assert govde["max_loans_student"] == 3
        assert govde["max_loans_teacher"] == 5
        assert govde["staff_loans_enabled"] is False
        assert not LibraryPolicy.objects.exists(), "okuma satır yazmamalı"

    def test_odunc_suresi_salt_okunur_ve_on_bes_gundur(self, istemci: APIClient) -> None:
        """D19: Md. 18 süreyi sabitler; gövdede gönderilen değer yok sayılır."""
        yanit = istemci.put(POLITIKA, {"loan_period_days": 30}, format="json")

        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["loan_period_days"] == policy_service.LOAN_PERIOD_DAYS == 15
        assert not hasattr(LibraryPolicy.load(), "loan_period_days")

    def test_mevzuat_ust_siniri_asilamaz(self, istemci: APIClient) -> None:
        yanit = istemci.put(POLITIKA, {"max_loans_student": 4}, format="json")

        assert yanit.status_code == 400
        assert "max_loans_student" in yanit.json()["fields"]

    def test_put_kismidir_gonderilmeyen_alana_dokunulmaz(self, istemci: APIClient) -> None:
        istemci.put(POLITIKA, {"max_loans_student": 2, "popular_min_members": 8}, format="json")

        govde = istemci.put(POLITIKA, {"idle_minutes": 5}, format="json").json()

        assert govde["idle_minutes"] == 5
        assert govde["max_loans_student"] == 2
        assert govde["popular_min_members"] == 8

    def test_digerlerine_odunc_mudurluk_karari_ister(self, istemci: APIClient) -> None:
        """AT-4: seçenek okul müdürlüğü kararıyla açılır; tarih ve sayı zorunludur."""
        yanit = istemci.put(POLITIKA, {"staff_loans_enabled": True}, format="json")

        alanlar = yanit.json()["fields"]
        assert yanit.status_code == 400
        assert "staff_loans_decision_date" in alanlar
        assert "staff_loans_decision_no" in alanlar

    def test_karar_bilgisiyle_acilir_kapaninca_temizlenir(self, istemci: APIClient) -> None:
        acik = istemci.put(
            POLITIKA,
            {
                "staff_loans_enabled": True,
                "staff_loans_decision_date": "2026-09-01",
                "staff_loans_decision_no": "2026/14",
            },
            format="json",
        )
        assert acik.status_code == 200, acik.json()
        assert acik.json()["staff_loans_decision_no"] == "2026/14"

        kapali = istemci.put(POLITIKA, {"staff_loans_enabled": False}, format="json").json()

        assert kapali["staff_loans_decision_date"] is None
        assert kapali["staff_loans_decision_no"] == ""

    def test_iade_kaydirma_ayari_ve_son_odunc_tarihleri_yazilir(self, istemci: APIClient) -> None:
        govde = istemci.put(
            POLITIKA,
            {
                "shift_due_date_on_school_break": False,
                "last_loan_date": "2027-06-10",
                "last_loan_date_graduating": "2027-05-20",
            },
            format="json",
        ).json()

        assert govde["shift_due_date_on_school_break"] is False
        assert govde["last_loan_date"] == "2027-06-10"
        assert govde["last_loan_date_graduating"] == "2027-05-20"

    def test_uc_yalniz_get_ve_put_kabul_eder(self, istemci: APIClient) -> None:
        assert istemci.post(POLITIKA, {}, format="json").status_code == 405
        assert istemci.delete(POLITIKA).status_code == 405


class TestOzetUcu:
    def test_bos_programda_sifirlar(self, istemci: APIClient) -> None:
        govde: dict[str, Any] = istemci.get(OZET).json()

        assert govde["work_count"] == 0
        assert govde["copy_count"] == 0
        assert govde["section_count"] == 0
        assert govde["status_counts"][CopyStatus.AVAILABLE] == 0

    def test_sayaclar_ve_siradaki_numara(self, istemci: APIClient) -> None:
        ortak.bolum(name="Edebiyat")
        eser = ortak.eser()
        edinim = ortak.edinim()
        ortak.nusha(eser, edinim)
        oduncteki = ortak.nusha(eser, edinim)
        type(oduncteki).objects.filter(pk=oduncteki.pk).update(status=CopyStatus.ON_LOAN)

        govde: dict[str, Any] = istemci.get(OZET).json()

        assert govde["work_count"] == 1
        assert govde["copy_count"] == 2
        assert govde["available_count"] == 1
        assert govde["section_count"] == 1
        assert govde["status_counts"][CopyStatus.ON_LOAN] == 1
        # Basılı biçim (sözlük): 'YYYY-NNNNNN'. Sayacı İLERLETMEZ.
        assert govde["next_barcode"].endswith("-000003")
        assert istemci.get(OZET).json()["next_barcode"] == govde["next_barcode"]

    def test_ozet_kisisel_veri_tasimaz(self, istemci: APIClient) -> None:
        """Pano kartı ve Md. 7 eşiği için; ad, numara ya da üye bilgisi YOKTUR."""
        ortak.nusha()

        govde: dict[str, Any] = istemci.get(OZET).json()

        assert set(govde) == {
            "work_count",
            "copy_count",
            "in_stock_count",
            "available_count",
            "status_counts",
            "section_count",
            "next_barcode",
        }
