"""Barkod biçimi ve okutulan kodun tür ayrımı (tasarım §7.1). DB istemez."""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.kutuphane import barcode
from shared import barcode128


class TestBicim:
    def test_barkod_on_hane_yil_ve_sira(self) -> None:
        assert barcode.build_barcode(2026, 123) == "2026000123"

    def test_basili_bicim_tireyle_gosterilir(self) -> None:
        assert barcode.format_barcode("2026000123") == "2026-000123"

    def test_kayit_no_barkodun_sayi_halidir(self) -> None:
        assert barcode.accession_no_of("2026000123") == 2026000123

    def test_sira_tukenince_hata_verir(self) -> None:
        with pytest.raises(barcode.BarcodeRangeError):
            barcode.build_barcode(2026, barcode.MAX_SEQUENCE + 1)

    def test_sifir_sira_uretilemez(self) -> None:
        with pytest.raises(barcode.BarcodeRangeError):
            barcode.build_barcode(2026, 0)

    def test_barkod_code128c_ile_basilabilir(self) -> None:
        """10 hane çift uzunluktur; Code128-C çift uzunluk ister (§7.2)."""
        kod = barcode.build_barcode(2026, 123)
        assert barcode128.module_count(kod, quiet_zone=False) == 90


class TestOkutma:
    @pytest.mark.parametrize(
        "ham", ["2026000123", "2026-000123", " 2026 000123 ", "2026000123\r\n"]
    )
    def test_okuyucu_girdisi_sadelesir(self, ham: str) -> None:
        assert barcode.normalize_scan(ham) == "2026000123"

    def test_on_haneli_kod_nusha_barkodudur(self) -> None:
        assert barcode.classify_scan("2026-000123") is barcode.ScanKind.COPY

    def test_sekiz_haneli_dokuzla_baslayan_kod_uye_kartidir(self) -> None:
        assert barcode.classify_scan("94718263") is barcode.ScanKind.MEMBER_CARD

    def test_isbn_barkodu_ayri_taninir(self) -> None:
        assert barcode.classify_scan("978-605-332-124-5") is barcode.ScanKind.ISBN

    def test_taninmayan_uzunluk_bilinmiyor_doner(self) -> None:
        assert barcode.classify_scan("12345") is barcode.ScanKind.UNKNOWN

    def test_isbn_iletisi_kullaniciya_ne_yapacagini_soyler(self) -> None:
        assert "kütüphane etiketini okutun" in barcode.ISBN_SCAN_MESSAGE

    def test_elle_yazilan_on_haneli_isbn10_nusha_sanilmaz(self) -> None:
        """Künye sayfasındaki eski ISBN-10 da 10 hanedir; ayrım YIL ön ekiyledir.

        Ayrım olmadan ekran "nüsha bulunamadı" derdi ve kullanıcı kitabın
        kayıtlı olmadığını sanırdı; oysa doğru ileti `ISBN_SCAN_MESSAGE`'dır.
        """
        assert barcode.classify_scan("0-306-40615-2") is barcode.ScanKind.ISBN
        assert barcode.classify_scan("0-13-110362-8") is barcode.ScanKind.ISBN

    def test_yil_on_ekli_on_hane_nusha_barkodu_kalir(self) -> None:
        assert barcode.classify_scan("2000000001") is barcode.ScanKind.COPY
        assert barcode.classify_scan("2999999999") is barcode.ScanKind.COPY

    def test_yil_gibi_olmayan_ve_saglamasi_tutmayan_on_hane_bilinmiyor_doner(self) -> None:
        assert barcode.classify_scan("1234567890") is barcode.ScanKind.UNKNOWN

    def test_yil_on_eki_uretilen_her_barkodu_kapsar(self) -> None:
        """`SCAN_YEAR_*` aralığı sayacın ürettiği yılları içermelidir (D6)."""
        for yil in (timezone.localdate().year, timezone.localdate().year + 50):
            kod = barcode.build_barcode(yil, 1)
            assert barcode.classify_scan(kod) is barcode.ScanKind.COPY
