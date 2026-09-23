"""Dış metnin temizliği: NFC, denetim karakteri, HTML varlığı, tavan (§5.10-19d).

**Bu dosyanın asıl kanıtı NFC'dir.** Tasarım §8.5 ölçümü: Open Library Türkçe
kayıtlarda ayrışık (NFD) kod noktası döndürüyor. NFC uygulanmazsa katalog
araması kendi kitabını bulamaz ve bu **sessizce** olur — testler hem
dönüşümü hem de katlamanın eşleştiğini kanıtlar.

Veriler uydurmadır (CLAUDE.md §2-12); kitap künyesi kişisel veri değildir.
"""

from __future__ import annotations

import unicodedata

import pytest

from apps.kutuphane import keys
from apps.kutuphane.kunye import temizlik

# "İletişim" — NFC (tek kod noktası) ve NFD (I + birleşen nokta) hâlleri.
NFC_YAYINEVI = "İletişim"
NFD_YAYINEVI = unicodedata.normalize("NFD", NFC_YAYINEVI)


class TestNfc:
    def test_ayrisik_girdi_katlamayi_bozar_kanit(self) -> None:
        """Sorunun kendisi: NFD girdi katalog aramasıyla EŞLEŞMEZ (ölçülen kusur)."""
        assert NFD_YAYINEVI != NFC_YAYINEVI
        assert keys.fold_search(NFD_YAYINEVI) != keys.fold_search(NFC_YAYINEVI)

    def test_temizlik_nfcye_cevirir(self) -> None:
        temiz = temizlik.metin_temizle(NFD_YAYINEVI)

        assert temiz == NFC_YAYINEVI
        assert unicodedata.is_normalized("NFC", temiz)

    def test_temizlenen_metin_katalog_aramasiyla_eslesir(self) -> None:
        """Kapı: temizlenmiş künye, kullanıcının kataloğunda aranınca bulunur."""
        temiz = temizlik.metin_temizle(NFD_YAYINEVI)

        assert keys.fold_search(temiz) == keys.fold_search(NFC_YAYINEVI)

    @pytest.mark.parametrize(
        "metin",
        ["Kürk Mantolu Madonna", "Şiir Defteri", "Ilık Rüzgâr", "İnce Memed", "Doğan Kitap"],
    )
    def test_turkce_metinler_bozulmadan_gecer(self, metin: str) -> None:
        assert temizlik.metin_temizle(unicodedata.normalize("NFD", metin)) == metin


class TestGuvenilmeyenGirdi:
    def test_html_varligi_cozulur(self) -> None:
        """Ölçülen kusur: Open Library `Do&#x11F;an Kitap` döndürüyor."""
        assert temizlik.metin_temizle("Do&#x11F;an Kitap") == "Doğan Kitap"

    def test_varlik_yalniz_bir_kez_cozulur(self) -> None:
        """İkinci geçiş `&amp;lt;`i etikete çevirirdi (çift çözme tuzağı)."""
        assert temizlik.metin_temizle("Ka&amp;lt;mil") == "Ka&lt;mil"

    # Karakterler `chr()` ile kurulur: yön değiştirme işareti (U+202E) kaynak
    # koda DÜZ YAZILIRSA düzenleyicide satırın görünen sırasını tersine çevirir
    # (biçimlendirici kaçış dizisini çözebiliyor, bu yüzden dizgede tutulmuyor).
    @pytest.mark.parametrize(
        "ayirici",
        [
            chr(0x202E),  # yön değiştirme: ekranda başka, kayıtta başka
            chr(0x200B),  # sıfır genişlikli boşluk
            "\x00",  # NUL
            "\t",
            "\r\n",
        ],
    )
    def test_denetim_karakterleri_elenir(self, ayirici: str) -> None:
        temiz = temizlik.metin_temizle(f"Kürk{ayirici}Mantolu")

        assert temiz == "Kürk Mantolu"
        assert all(unicodedata.category(ch) not in {"Cc", "Cf"} for ch in temiz)

    def test_bosluklar_sadelesir(self) -> None:
        nbsp = chr(0x00A0)  # bölünmez boşluk: gözle ayırt edilmez, `strip()` görmez
        assert temizlik.metin_temizle(f"  Kürk{nbsp} Mantolu   Madonna ") == "Kürk Mantolu Madonna"

    def test_tavan_uygulanir(self) -> None:
        assert temizlik.metin_temizle("A" * 900, tavan=500) == "A" * 500

    def test_bos_ve_none_bos_doner(self) -> None:
        assert temizlik.metin_temizle(None) == ""
        assert temizlik.metin_temizle("") == ""


class TestMarcTemizligi:
    @pytest.mark.parametrize(
        ("ham", "beklenen"),
        [
            ("Kürk mantolu Madonna /", "Kürk mantolu Madonna"),
            ("Kürk mantolu Madonna :", "Kürk mantolu Madonna"),
            ("İletişim,", "İletişim"),
            ("[2015]", "2015"),
            ("Ankara ;", "Ankara"),
        ],
    )
    def test_isbd_noktalamasi_kirpilir(self, ham: str, beklenen: str) -> None:
        assert temizlik.marc_temizle(ham) == beklenen


class TestSayiVeYil:
    @pytest.mark.parametrize(
        ("ham", "beklenen"),
        [("2015.", 2015), ("c2015", 2015), ("[2015]", 2015), ("13 Nisan 2015", 2015)],
    )
    def test_yil_okunur(self, ham: str, beklenen: int) -> None:
        assert temizlik.yil_ayikla(ham) == beklenen

    @pytest.mark.parametrize("ham", ["13 Nisan", "28 Ekim", "", "bilinmiyor"])
    def test_yil_yoksa_bos_kalir(self, ham: str) -> None:
        """Open Library'nin Amazon kaynaklı uydurma tarihleri (TB21): yıl yazılmaz."""
        assert temizlik.yil_ayikla(ham) is None

    def test_sayfa_sayisi_okunur(self) -> None:
        assert temizlik.sayi_ayikla("328 s. ; 20 cm") == 328
        assert temizlik.sayi_ayikla("sayfa yok") is None
