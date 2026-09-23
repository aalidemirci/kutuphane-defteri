"""ISBN normalleştirme, ISBN-10 → 13 çevrimi ve sağlama uyarısı (F2 kod kapısı).

DB istemez: `apps.kutuphane.isbn` saf fonksiyonlardan oluşur.
"""

from __future__ import annotations

import pytest

from apps.kutuphane import isbn


class TestNormalize:
    @pytest.mark.parametrize(
        ("ham", "beklenen"),
        [
            ("978-605-332-124-5", "9786053321245"),
            ("978 605 332 124 5", "9786053321245"),
            ("ISBN: 978-605-332-124-5", "9786053321245"),
            ("975-07-0405-x", "975070405X"),
            ("975-07-0405-X", "975070405X"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_tire_bosluk_ve_on_ek_atilir(self, ham: object, beklenen: str) -> None:
        assert isbn.normalize_isbn(ham) == beklenen


class TestCevrim:
    def test_isbn10_13e_cevrilir(self) -> None:
        # 0-306-40615-2 → 978-0-306-40615-7 (standardın örneği).
        assert isbn.isbn10_to_13("0306406152") == "9780306406157"

    def test_cevrim_978_on_ekiyle_baslar(self) -> None:
        assert isbn.to_isbn13("975-07-0405-1").startswith("978")

    def test_13_hane_oldugu_gibi_kalir(self) -> None:
        assert isbn.to_isbn13("9786053321245") == "9786053321245"

    def test_cozulemeyen_uzunluk_bos_doner(self) -> None:
        assert isbn.to_isbn13("12345") == ""

    def test_bozuk_saglamali_isbn10_de_cevrilir(self) -> None:
        """Sağlama hatası çevrimi durdurmaz — uyarı ayrı kanaldır."""
        assert isbn.to_isbn13("0306406150") == "9780306406157"

    def test_x_ile_biten_isbn10_cevrilir(self) -> None:
        """Sağlama hanesi 'X' olan numaralar ISBN-10'ların yaklaşık on birde biridir.

        Eski kitaplarda sıktır; çevrim 'X'i atıp ilk dokuz rakamı kullanır.
        """
        assert isbn.to_isbn13("0-9752298-0-X") == "9780975229804"
        assert isbn.isbn10_to_13("097522980X") == "9780975229804"


class TestSaglamaHanesi:
    """`isbn10_check_digit`'in 'X' dalı (kalan 10) — kapının sınanmamış yarısıydı."""

    def test_kalan_on_olunca_saglama_hanesi_x_basilir(self) -> None:
        assert isbn.isbn10_check_digit("097522980") == "X"

    def test_x_ile_biten_isbn10_gecerlidir(self) -> None:
        assert isbn.is_valid_isbn10("097522980X") is True

    def test_x_ile_biten_isbn10_uyari_vermez(self) -> None:
        assert isbn.isbn_warning("0-9752298-0-X") == ""

    def test_kucuk_x_de_ayni_numaradir(self) -> None:
        assert isbn.isbn_warning("0-9752298-0-x") == ""


class TestSaglama:
    def test_dogru_isbn13_uyari_vermez(self) -> None:
        assert isbn.isbn_warning("978-0-306-40615-7") == ""

    def test_dogru_isbn10_uyari_vermez(self) -> None:
        assert isbn.isbn_warning("0-306-40615-2") == ""

    def test_bozuk_saglama_uyari_verir(self) -> None:
        assert isbn.isbn_warning("978-0-306-40615-9") == isbn.WARNING_CHECKSUM

    def test_yanlis_uzunluk_uyari_verir(self) -> None:
        assert isbn.isbn_warning("1234567") == isbn.WARNING_LENGTH

    def test_978_979_disi_on_ek_uyari_verir(self) -> None:
        assert isbn.isbn_warning("1234567890123") == isbn.WARNING_PREFIX

    def test_bos_deger_uyari_vermez(self) -> None:
        assert isbn.isbn_warning("") == ""

    def test_x_yanlis_yerdeyse_gerekce_saglama_degil_bicimdir(self) -> None:
        """'X' ortada olan numaranın sağlaması HESAPLANAMAZ; "son hane tutmuyor" yanıltır.

        Kullanıcıya ayrıca numaranın 13 haneli biçime çevrilemediği söylenir:
        `isbn13` boş kalır ve eser 13 haneli numarayla aranamaz.
        """
        assert isbn.isbn_warning("0-3064-061X-2") == isbn.WARNING_X_PLACEMENT
        assert isbn.to_isbn13("0-3064-061X-2") == ""

    def test_on_uc_hanenin_icindeki_x_de_bicim_uyarisi_verir(self) -> None:
        """Uzunluk doğru ama biçim değil — "10 ya da 13 haneli olmalıdır" yanıltırdı."""
        assert isbn.isbn_warning("978030640615X") == isbn.WARNING_X_PLACEMENT

    def test_bicim_uyarisi_on_uc_haneyle_aranamayacagini_soyler(self) -> None:
        assert "13 haneli" in isbn.WARNING_X_PLACEMENT


class TestBarkodAyrimi:
    def test_978_ile_baslayan_13_hane_isbn_barkodudur(self) -> None:
        assert isbn.is_isbn_barcode("9786053321245") is True

    def test_979_ile_baslayan_13_hane_isbn_barkodudur(self) -> None:
        assert isbn.is_isbn_barcode("9791234567896") is True

    def test_kutuphane_etiketi_isbn_barkodu_degildir(self) -> None:
        """10 haneli kütüphane barkodu (2026000123) ISBN sanılmaz."""
        assert isbn.is_isbn_barcode("2026000123") is False

    def test_bozuk_saglamali_isbn_barkodu_yine_isbndir(self) -> None:
        assert isbn.is_isbn_barcode("9786053321249") is True
