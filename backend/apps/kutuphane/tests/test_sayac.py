"""Nüsha numarası sayacı: yıl dönümü, yeniden kullanmama, yarış (D6, F2 kapısı)."""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from apps.kutuphane import barcode
from apps.kutuphane.models import CopyCounter
from apps.kutuphane.services import numbering
from apps.kutuphane.tests.ortak import edinim, eser, nusha


@pytest.mark.django_db
class TestSayac:
    def test_numaralar_birden_baslar_ve_artar(self) -> None:
        assert numbering.next_copy_identity()[1].endswith("000001")
        assert numbering.next_copy_identity()[1].endswith("000002")

    def test_ayni_numara_iki_kez_verilmez(self) -> None:
        uretilenler = [numbering.next_copy_identity()[1] for _ in range(50)]
        assert len(set(uretilenler)) == 50

    def test_kayit_no_barkodun_sayi_halidir(self) -> None:
        accession_no, kod = numbering.next_copy_identity()
        assert accession_no == int(kod)

    def test_silinen_nushanin_numarasi_yeniden_dagitilmaz(self) -> None:
        work = eser()
        acquisition = edinim()
        birinci = nusha(work, acquisition)
        birinci.delete()
        assert nusha(work, acquisition).barcode != birinci.barcode
        # Katı silme de sayacı geri almaz.
        ikinci = nusha(work, acquisition)
        eski_kod = ikinci.barcode
        ikinci.hard_delete()
        assert nusha(work, acquisition).barcode != eski_kod

    def test_yil_yerel_gunden_alinir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D6: `timezone.now()` UTC'dir; 1 Ocak gece yarısı yıl bir eksik çıkardı.

        Yerel gün 01.01.2027, UTC anı ise hâlâ 31.12.2026 22:00'dir; barkod yerel
        güne göre 2027 ile başlamalıdır.
        """
        yerel_gun = dt.date(2027, 1, 1)
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: yerel_gun)
        assert numbering.next_copy_identity()[1].startswith("2027")

    def test_yil_donumunde_sayac_yeniden_baslar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eski_yil_gunu = dt.date(2026, 12, 31)
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: eski_yil_gunu)
        numbering.next_copy_identity()
        numbering.next_copy_identity()
        yeni_yil_gunu = dt.date(2027, 1, 1)
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: yeni_yil_gunu)
        _no, kod = numbering.next_copy_identity()
        assert kod == "2027000001"
        assert CopyCounter.objects.get(year=2026).last_no == 2

    def test_sayac_dolunca_numara_uretilmez_ve_sayac_ilerlemez(self) -> None:
        yil = timezone.localdate().year
        CopyCounter.objects.create(year=yil, last_no=barcode.MAX_SEQUENCE)
        with pytest.raises(barcode.BarcodeRangeError):
            numbering.next_copy_identity()
        assert CopyCounter.objects.get(year=yil).last_no == barcode.MAX_SEQUENCE

    def test_sonraki_numara_gosterimi_sayaci_ilerletmez(self) -> None:
        assert numbering.peek_next_sequence() == 1
        numbering.next_copy_identity()
        assert numbering.peek_next_sequence() == 2
        assert numbering.peek_next_sequence() == 2
