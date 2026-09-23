"""Edinim, komisyon kararı ve bağış ön kaydı uçları (F2 sözleşmesi §4).

Kapsam: liste / oluştur / güncelle / sil, doğrulama hataları, Md. 10/3 bağış
kuralı, D7 karar türü denetimi ve bağış kararının tek işlemde uygulanması
(SU-23).

Komisyon başkanı ve bağışçı adları UYDURMADIR (CLAUDE.md §2-12) ve şifreli
alanlara yazılır; parolasız ortamın kapısı `test_uc_kapilari.py`'dedir.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    DonationIntake,
    DonationIntakeStatus,
    DonationItemDecision,
    Work,
)
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

KARARLAR = "/api/v1/library/commission-decisions/"
EDINIMLER = "/api/v1/library/acquisitions/"
BAGISLAR = "/api/v1/library/donation-intakes/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


def _sonuclar(yanit: Any) -> list[dict[str, Any]]:
    govde: dict[str, Any] = yanit.json()
    return list(govde["results"])


def _on_kayit(istemci: APIClient, **kalemler: Any) -> dict[str, Any]:
    """İki kalemli bir bağış ön kaydı açar ve yanıt gövdesini döndürür."""
    yanit = istemci.post(
        BAGISLAR,
        {
            "donor_name": "Selma Yücel",
            "received_date": "2026-09-01",
            "items": [
                {"title": "Bağış Kitabı", "authors": "Deniz Aksoy", "copies": 2},
                {"title": "İkinci Kitap"},
            ],
            **kalemler,
        },
        format="json",
    )
    govde: dict[str, Any] = yanit.json()
    assert yanit.status_code == 201, govde
    return govde


# ============================================================ Komisyon kararları
class TestKomisyonKarariUclari:
    def test_karar_acilir_ve_listelenir(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            KARARLAR,
            {
                "decision_type": CommissionDecisionType.DONATION_REVIEW,
                "decision_date": "2026-09-01",
                "decision_no": "2026/7",
                "chair_name": "Deniz Korkmaz",
                "chair_title": "Şube Müdürü",
                "participants_text": "Ayşe Yıldız\nMehmet Duran",
            },
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert govde["chair_name"] == "Deniz Korkmaz"
        assert govde["decision_type_display"] == "Bağış değerlendirme"
        assert govde["in_use"] is False
        assert len(_sonuclar(istemci.get(KARARLAR))) == 1

    def test_baskan_adi_zorunludur(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            KARARLAR,
            {"decision_type": CommissionDecisionType.WEEDING, "decision_date": "2026-09-01"},
            format="json",
        )

        assert yanit.status_code == 400
        assert "chair_name" in yanit.json()["fields"]

    def test_karar_turu_suzgeci(self, istemci: APIClient) -> None:
        ortak.karar(decision_type=CommissionDecisionType.DONATION_REVIEW)
        ortak.karar(decision_type=CommissionDecisionType.WEEDING)

        suzulmus = _sonuclar(
            istemci.get(KARARLAR, {"decision_type": CommissionDecisionType.WEEDING})
        )

        assert [satir["decision_type"] for satir in suzulmus] == [CommissionDecisionType.WEEDING]

    def test_taninmayan_karar_turu_suzgeci_400(self, istemci: APIClient) -> None:
        yanit = istemci.get(KARARLAR, {"decision_type": "AYIKLAMA"})

        assert yanit.status_code == 400
        assert "decision_type" in yanit.json()["fields"]

    def test_kullanilmis_kararin_turu_degistirilemez(self, istemci: APIClient) -> None:
        """D7: tür denetimini geriye dönük boşa çıkarırdı."""
        karar = ortak.karar()
        ortak.edinim(
            method=AcquisitionMethod.DONATION, commission_decision=karar, source_note="Bağış"
        )

        yanit = istemci.patch(
            f"{KARARLAR}{karar.pk}/",
            {"decision_type": CommissionDecisionType.WEEDING},
            format="json",
        )

        assert yanit.status_code == 400
        assert "decision_type" in yanit.json()["fields"]
        assert istemci.get(f"{KARARLAR}{karar.pk}/").json()["in_use"] is True

    def test_kullanilmis_karar_silinemez_kullanilmayan_silinir(self, istemci: APIClient) -> None:
        bagli = ortak.karar()
        ortak.edinim(method=AcquisitionMethod.DONATION, commission_decision=bagli)
        bos = ortak.karar(decision_no="2026/8")

        assert istemci.delete(f"{KARARLAR}{bagli.pk}/").status_code == 400
        assert istemci.delete(f"{KARARLAR}{bos.pk}/").status_code == 204
        assert CommissionDecision.objects.filter(pk=bagli.pk).exists()
        assert not CommissionDecision.objects.filter(pk=bos.pk).exists()


# ============================================================ Edinimler
class TestEdinimUclari:
    def test_kayit_ici_giris_komisyon_karari_istemez(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.EXISTING_STOCK,
                "date": "2026-09-01",
                "notes": "Mevcut koleksiyonun ilk aktarımı",
            },
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert govde["method_display"] == "Mevcut koleksiyon (programa aktarım)"
        assert govde["copy_count"] == 0

    def test_eksi_birim_fiyat_reddedilir(self, istemci: APIClient) -> None:
        """TMY Md. 13/2 değer alanı: eksi işaretli yazım hatası F10 toplamını bozar.

        Bedelsiz giriş (bağış, Bakanlık gönderimi) SIFIRDIR, eksi değil.
        """
        yanit = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.EXISTING_STOCK,
                "date": "2026-09-01",
                "unit_price": "-100.00",
            },
            format="json",
        )

        assert yanit.status_code == 400, yanit.json()
        assert "unit_price" in yanit.json()["fields"]
        assert not Acquisition.objects.exists()

    def test_sifir_birim_fiyat_kabul_edilir(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.EXISTING_STOCK,
                "date": "2026-09-01",
                "unit_price": "0.00",
            },
            format="json",
        )

        assert yanit.status_code == 201, yanit.json()

    def test_bagista_komisyon_karari_zorunludur(self, istemci: APIClient) -> None:
        """Md. 10/3 — servis reddeder, ileti alan adıyla döner."""
        yanit = istemci.post(
            EDINIMLER,
            {"method": AcquisitionMethod.DONATION, "date": "2026-09-01"},
            format="json",
        )

        assert yanit.status_code == 400
        assert "commission_decision" in yanit.json()["fields"]
        assert not Acquisition.objects.exists()

    def test_bagista_kararin_turu_denetlenir(self, istemci: APIClient) -> None:
        """D7: ayıklama kararı bağış edinimine bağlanamaz."""
        ayiklama = ortak.karar(decision_type=CommissionDecisionType.WEEDING)

        yanit = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.DONATION,
                "date": "2026-09-01",
                "commission_decision": ayiklama.pk,
            },
            format="json",
        )

        assert yanit.status_code == 400
        assert "commission_decision" in yanit.json()["fields"]

    def test_ayiklama_karari_hicbir_edinime_baglanamaz(self, istemci: APIClient) -> None:
        ayiklama = ortak.karar(decision_type=CommissionDecisionType.WEEDING)

        yanit = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.PURCHASE,
                "date": "2026-09-01",
                "commission_decision": ayiklama.pk,
            },
            format="json",
        )

        assert yanit.status_code == 400

    def test_bagisci_notu_sifreli_alandir_ve_duz_okunur(self, istemci: APIClient) -> None:
        karar = ortak.karar()

        govde = istemci.post(
            EDINIMLER,
            {
                "method": AcquisitionMethod.DONATION,
                "date": "2026-09-01",
                "source_note": "Selma Yücel",
                "commission_decision": karar.pk,
            },
            format="json",
        ).json()

        # Uç düz metin döndürür (anahtar bellekte); diske şifreli yazıldığının
        # kanıtı `test_sifreli_alanlar.py`'dedir — burada ham satır yalnız
        # teyit edilir (ORM okurken çözer, ORM üzerinden bakmak kanıt olmaz).
        assert govde["source_note"] == "Selma Yücel"
        with connection.cursor() as imlec:
            imlec.execute(
                "SELECT source_note FROM kutuphane_acquisition WHERE id = %s", [govde["id"]]
            )
            ham = str(imlec.fetchone()[0])
        assert "Yücel" not in ham

    def test_edinim_yolu_suzgeci_ve_gecersiz_deger(self, istemci: APIClient) -> None:
        ortak.edinim(method=AcquisitionMethod.PURCHASE)
        ortak.edinim(method=AcquisitionMethod.EXISTING_STOCK)

        assert len(_sonuclar(istemci.get(EDINIMLER, {"method": AcquisitionMethod.PURCHASE}))) == 1
        assert istemci.get(EDINIMLER, {"method": "HEDIYE"}).status_code == 400

    def test_nushasi_olan_edinim_silinemez(self, istemci: APIClient) -> None:
        edinim = ortak.edinim()
        ortak.nusha(acquisition=edinim)

        yanit = istemci.delete(f"{EDINIMLER}{edinim.pk}/")

        assert yanit.status_code == 400
        assert istemci.get(f"{EDINIMLER}{edinim.pk}/").json()["copy_count"] == 1

    def test_bos_edinim_silinir(self, istemci: APIClient) -> None:
        edinim = ortak.edinim()

        assert istemci.delete(f"{EDINIMLER}{edinim.pk}/").status_code == 204
        assert not Acquisition.objects.filter(pk=edinim.pk).exists()


# ============================================================ Bağış ön kaydı (SU-23)
class TestBagisOnKaydiUclari:
    def test_on_kayit_kalemleriyle_acilir_nusha_acilmaz(self, istemci: APIClient) -> None:
        govde = _on_kayit(istemci)

        assert govde["status"] == DonationIntakeStatus.PENDING
        assert govde["item_count"] == 2
        assert govde["donor_name"] == "Selma Yücel"
        assert Work.objects.count() == 0
        assert Copy.objects.count() == 0

    def test_kalem_eklenir_guncellenir_silinir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        kalemler_yolu = f"{BAGISLAR}{kayit['id']}/items/"

        eklenen = istemci.post(kalemler_yolu, {"title": "Üçüncü Kitap"}, format="json")
        assert eklenen.status_code == 201, eklenen.json()
        kalem_id = eklenen.json()["id"]

        guncel = istemci.patch(
            f"{kalemler_yolu}{kalem_id}/", {"copies": 4, "isbn": "978-0-306-40615-7"}, format="json"
        )
        assert guncel.status_code == 200, guncel.json()
        assert guncel.json()["copies"] == 4

        assert istemci.delete(f"{kalemler_yolu}{kalem_id}/").status_code == 204
        assert istemci.get(f"{BAGISLAR}{kayit['id']}/").json()["item_count"] == 2

    def test_baska_on_kaydin_kalemi_404(self, istemci: APIClient) -> None:
        birinci = _on_kayit(istemci)
        ikinci = _on_kayit(istemci)
        yabanci_kalem = ikinci["items"][0]["id"]

        yanit = istemci.delete(f"{BAGISLAR}{birinci['id']}/items/{yabanci_kalem}/")

        assert yanit.status_code == 404

    def test_karar_kabul_ve_reddi_tek_islemde_uygular(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()
        kabul, ret = kayit["items"][0]["id"], kayit["items"][1]["id"]
        bolum = ortak.bolum(name="Edebiyat")

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {
                "commission_decision": karar.pk,
                "accepted_ids": [kabul],
                "rejected": {str(ret): "Ders düzeyinin çok üstünde."},
                "section": bolum.pk,
            },
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 200, govde
        assert govde["accepted"] == 1
        assert govde["rejected"] == 1
        assert govde["work_count"] == 1
        assert govde["copy_count"] == 2
        assert govde["acquisition"] is not None
        assert govde["intake"]["status"] == DonationIntakeStatus.DECIDED
        kalemler = {satir["id"]: satir for satir in govde["intake"]["items"]}
        assert kalemler[kabul]["decision"] == DonationItemDecision.ACCEPTED
        assert kalemler[kabul]["work_title"] == "Bağış Kitabı"
        assert kalemler[ret]["reject_reason"] == "Ders düzeyinin çok üstünde."
        assert Copy.objects.filter(section=bolum).count() == 2

    def test_eksik_karar_butun_islemi_reddeder(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {"commission_decision": karar.pk, "accepted_ids": [kayit["items"][0]["id"]]},
            format="json",
        )

        assert yanit.status_code == 400
        assert "items" in yanit.json()["fields"]
        assert Work.objects.count() == 0
        assert not Acquisition.objects.exists()

    def test_bos_ret_gerekcesi_reddedilir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()
        ilk, ikinci = (satir["id"] for satir in kayit["items"])

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {
                "commission_decision": karar.pk,
                "accepted_ids": [ilk],
                "rejected": {str(ikinci): "   "},
            },
            format="json",
        )

        assert yanit.status_code == 400

    def test_sayisal_olmayan_kalem_anahtari_reddedilir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {"commission_decision": karar.pk, "rejected": {"bir": "gerekçe"}},
            format="json",
        )

        assert yanit.status_code == 400
        assert "rejected" in yanit.json()["fields"]

    def test_bagis_degerlendirme_disi_karar_reddedilir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        ayiklama = ortak.karar(decision_type=CommissionDecisionType.WEEDING)

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {
                "commission_decision": ayiklama.pk,
                "accepted_ids": [satir["id"] for satir in kayit["items"]],
            },
            format="json",
        )

        assert yanit.status_code == 400
        assert "commission_decision" in yanit.json()["fields"]

    def test_hepsi_reddedilirse_edinim_acilmaz(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {
                "commission_decision": karar.pk,
                "rejected": {
                    str(satir["id"]): "Kütüphane düzeyine uygun değil." for satir in kayit["items"]
                },
            },
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 200, govde
        assert govde["acquisition"] is None
        assert govde["intake"]["status"] == DonationIntakeStatus.DECIDED
        assert not Acquisition.objects.exists()
        assert Work.objects.count() == 0

    def test_karardan_sonra_kalem_eklenemez_ve_kayit_silinemez(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        karar = ortak.karar()
        istemci.post(
            f"{BAGISLAR}{kayit['id']}/decision/",
            {
                "commission_decision": karar.pk,
                "accepted_ids": [satir["id"] for satir in kayit["items"]],
            },
            format="json",
        )

        ekleme = istemci.post(f"{BAGISLAR}{kayit['id']}/items/", {"title": "Geç"}, format="json")
        silme = istemci.delete(f"{BAGISLAR}{kayit['id']}/")

        assert ekleme.status_code == 400
        assert silme.status_code == 400
        assert DonationIntake.objects.filter(pk=kayit["id"]).exists()

    def test_on_kayit_iptal_edilir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)

        yanit = istemci.post(
            f"{BAGISLAR}{kayit['id']}/cancel/", {"reason": "Bağış geri verildi."}, format="json"
        )

        govde = yanit.json()
        assert yanit.status_code == 200, govde
        assert govde["status"] == DonationIntakeStatus.CANCELLED
        assert "Bağış geri verildi." in govde["notes"]

    def test_karar_beklerken_kunye_guncellenir_ve_kayit_silinir(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)

        guncel = istemci.patch(
            f"{BAGISLAR}{kayit['id']}/", {"donor_name": "Selma Yücel Demir"}, format="json"
        )
        assert guncel.status_code == 200, guncel.json()
        assert guncel.json()["donor_name"] == "Selma Yücel Demir"

        assert istemci.delete(f"{BAGISLAR}{kayit['id']}/").status_code == 204
        assert not DonationIntake.objects.filter(pk=kayit["id"]).exists()

    def test_durum_suzgeci_ve_gecersiz_deger(self, istemci: APIClient) -> None:
        kayit = _on_kayit(istemci)
        istemci.post(f"{BAGISLAR}{kayit['id']}/cancel/", {}, format="json")
        _on_kayit(istemci)

        bekleyen = _sonuclar(istemci.get(BAGISLAR, {"status": DonationIntakeStatus.PENDING}))
        assert len(bekleyen) == 1
        assert istemci.get(BAGISLAR, {"status": "BEKLIYOR"}).status_code == 400
