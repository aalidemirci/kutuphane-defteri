"""Şifreli katalog alanları: bağışçı ve komisyon adları (§6.3).

İki şeyi sabitler:

1. Şifrelenen alanlar veritabanında DÜZ METİN DEĞİL, Fernet token'ıdır (ham SQL
   ile okunur — ORM okurken çözer, bu yüzden ORM üzerinden bakmak kanıt olmaz).
2. Katalog alanları (eser adı, yazar, barkod, bölüm) ŞİFRELENMEZ (T6): şifreli
   alanda DB araması yapılamaz ve Ağ Kataloğu program kilitliyken de çalışmalıdır.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.kutuphane.models import (
    Acquisition,
    CommissionDecision,
    DonationIntake,
    Work,
)
from apps.kutuphane.tests.ortak import edinim, eser
from shared.crypto import EncryptedTextField, encrypted_fields_of

#: Fernet token'ının başı (sürüm baytı 0x80 + base64) — düz metin böyle başlamaz.
TOKEN_ONEKI = "gAAAAA"


def _ham_deger(tablo: str, sutun: str, pk: int) -> str:
    """Alanın DB'deki ham hâli (ORM çözmeden)."""
    with connection.cursor() as imlec:
        imlec.execute(f"SELECT {sutun} FROM {tablo} WHERE id = %s", [pk])  # noqa: S608
        satir = imlec.fetchone()
    return str(satir[0])


@pytest.mark.django_db
class TestSifrelenenler:
    def test_bagisci_notu_diske_sifreli_yazilir(self) -> None:
        acquisition = edinim(source_note="Bağışçı: Ayşe Yıldırım")
        ham = _ham_deger("kutuphane_acquisition", "source_note", acquisition.pk)
        assert ham.startswith(TOKEN_ONEKI)
        assert "Yıldırım" not in ham
        # ORM okurken çözer.
        assert Acquisition.objects.get(pk=acquisition.pk).source_note == "Bağışçı: Ayşe Yıldırım"

    def test_komisyon_baskani_ve_katilimcilari_sifrelidir(self) -> None:
        decision = CommissionDecision.objects.create(
            decision_type="DONATION_REVIEW",
            decision_date="2026-09-01",
            chair_name="Deniz Korkmaz",
            participants_text="Elif Aydın\nMert Şahin",
        )
        for sutun, gizli in (("chair_name", "Korkmaz"), ("participants_text", "Aydın")):
            ham = _ham_deger("kutuphane_commissiondecision", sutun, decision.pk)
            assert ham.startswith(TOKEN_ONEKI)
            assert gizli not in ham

    def test_bagis_on_kaydinda_bagisci_sifrelidir(self) -> None:
        intake = DonationIntake.objects.create(
            donor_name="Ayşe Yıldırım", received_date="2026-09-10"
        )
        ham = _ham_deger("kutuphane_donationintake", "donor_name", intake.pk)
        assert ham.startswith(TOKEN_ONEKI)

    def test_bos_deger_sifrelenmez(self) -> None:
        """Boş dize DB'de de boş görünür (kısmi kısıtlar buna dayanır)."""
        acquisition = edinim()
        assert _ham_deger("kutuphane_acquisition", "source_note", acquisition.pk) == ""


@pytest.mark.django_db
class TestSifrelenmeyenler:
    def test_katalog_alanlari_duz_yazilir(self) -> None:
        """T6: katalog alanları asla şifrelenmez — arama ve Ağ Kataloğu buna dayanır."""
        work = eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")
        assert _ham_deger("kutuphane_work", "title", work.pk) == "Kürk Mantolu Madonna"
        assert _ham_deger("kutuphane_work", "authors", work.pk) == "Sabahattin Ali"

    def test_eserde_sifreli_alan_yoktur(self) -> None:
        assert encrypted_fields_of(Work) == ()

    def test_sifreli_alanlarin_kaydi_koddan_okunur(self) -> None:
        """Kayıt defteri elle tutulmaz; beklenen küme burada sabitlenir (§6.3)."""
        beklenen = {
            "Acquisition": {"source_note"},
            "CommissionDecision": {"chair_name", "participants_text"},
            "DonationIntake": {"donor_name"},
        }
        gercek = {
            model.__name__: {f.name for f in encrypted_fields_of(model)}
            for model in (Acquisition, CommissionDecision, DonationIntake)
        }
        assert gercek == beklenen
        assert all(
            isinstance(f, EncryptedTextField) for f in encrypted_fields_of(CommissionDecision)
        )
