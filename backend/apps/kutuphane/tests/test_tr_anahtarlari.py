"""Türkçe arama ve üç eksenli sıralama — F2 kod kapısı (T7, D2).

Kapı üç çiftle sınanır: "şiir"/"ŞİİR", "ılık"/"ILIK", "İnce"/"ince". Üçü de
SQLite'ın `LIKE`'ında ve BINARY sıralamasında yanlış davranır; bu yüzden hem
arama hem sıralama `Work`'ün anahtar alanlarıyla yapılır.

Ayrıca: anahtarlar `save()`'de türetilir → `bulk_create`/`bulk_update`/
`QuerySet.update()` onları ATLAR. Koruma testi kaynak ağacında böyle bir yol
olmadığını sabitler (F3 içe aktarımı toplu yazarsa anahtarları elle doldurmak
zorundadır).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

from apps.kutuphane import keys, selectors
from apps.kutuphane.models import Work
from apps.kutuphane.tests.ortak import eser

#: Anahtarların KAYNAĞI olan alanlar; toplu yazımda anahtar bayatlar.
ANAHTAR_KAYNAKLARI = ("title", "authors", "subjects", "isbn")


def _adlari(rows: Iterable[Work]) -> list[str]:
    return [work.title for work in rows]


@pytest.mark.django_db
class TestArama:
    def test_kucuk_ve_buyuk_harfli_sorgu_ayni_eseri_bulur(self) -> None:
        eser(title="Şiir Kitabı", authors="Behçet Necatigil")
        assert _adlari(selectors.works(q="şiir")) == ["Şiir Kitabı"]
        assert _adlari(selectors.works(q="ŞİİR")) == ["Şiir Kitabı"]

    def test_noktasiz_i_ile_noktali_i_karismaz(self) -> None:
        """'ılık' ile 'ilik' AYRI sözcüklerdir; katlama ikisini birleştirmez."""
        eser(title="Ilık Sular", authors="Nehir Aksoy")
        eser(title="İlik Nakli", authors="Deniz Korkmaz")
        assert _adlari(selectors.works(q="ılık")) == ["Ilık Sular"]
        assert _adlari(selectors.works(q="ILIK")) == ["Ilık Sular"]
        assert _adlari(selectors.works(q="ilik")) == ["İlik Nakli"]

    def test_bas_harfi_buyuk_yazilan_i_bulunur(self) -> None:
        eser(title="İnce Memed", authors="Yaşar Kemal")
        assert _adlari(selectors.works(q="ince")) == ["İnce Memed"]
        assert _adlari(selectors.works(q="İnce")) == ["İnce Memed"]

    def test_yazar_ve_konu_da_aranir(self) -> None:
        eser(title="Sinekli Bakkal", authors="Halide Edip Adıvar", subjects="Türk edebiyatı, roman")
        assert _adlari(selectors.works(q="adıvar")) == ["Sinekli Bakkal"]
        assert _adlari(selectors.works(q="ROMAN")) == ["Sinekli Bakkal"]

    def test_sozcukler_ayri_ayri_aranir(self) -> None:
        """Kullanıcı sözcük sırasını hatırlamak zorunda değildir."""
        eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")
        assert _adlari(selectors.works(q="madonna kürk")) == ["Kürk Mantolu Madonna"]

    def test_noktalama_aramayi_bozmaz(self) -> None:
        eser(title="Tutunamayanlar", authors="Oğuz Atay")
        assert _adlari(selectors.works(q="tutunamayanlar,")) == ["Tutunamayanlar"]

    def test_isbn_ile_aranir(self) -> None:
        eser(title="Saatleri Ayarlama Enstitüsü", isbn="978-975-08-0000-0")
        bulunanlar = _adlari(selectors.works(q="978-975-08-0000-0"))
        assert bulunanlar == ["Saatleri Ayarlama Enstitüsü"]
        # Tiresiz yazım da aynı kayda gider.
        assert _adlari(selectors.works(q="9789750800000")) == ["Saatleri Ayarlama Enstitüsü"]

    def test_on_haneli_isbn_ile_de_aranir(self) -> None:
        """Okulun elindeki eski numara 10 hanelidir; kayıt 13 haneye çevrilmiştir."""
        eser(title="Beyaz Gemi", isbn="0-306-40615-2")
        assert _adlari(selectors.works(q="0306406152")) == ["Beyaz Gemi"]
        assert _adlari(selectors.works(q="9780306406157")) == ["Beyaz Gemi"]

    def test_eslesmeyen_sorgu_bos_doner(self) -> None:
        eser(title="Çalıkuşu")
        assert list(selectors.works(q="zeytin")) == []

    def test_duzeltme_isareti_ayirt_edilmez(self) -> None:
        """Klavyede 'â' zahmetlidir: kullanıcı "rüzgar" yazar, künye "Rüzgâr" girilmiştir.

        Katlama olmadan kayıt aramayla HİÇ bulunmaz ve kullanıcı aynı eseri
        ikinci kez kataloglar.
        """
        eser(title="Rüzgâr Gibi Geçti", authors="Kâmil Aydın")
        assert _adlari(selectors.works(q="rüzgar")) == ["Rüzgâr Gibi Geçti"]
        assert _adlari(selectors.works(q="RÜZGÂR")) == ["Rüzgâr Gibi Geçti"]
        assert _adlari(selectors.works(q="kamil")) == ["Rüzgâr Gibi Geçti"]


@pytest.mark.django_db
class TestSiralama:
    def test_ad_ekseni_turk_alfabesi_sirasindadir(self) -> None:
        for ad in ("Zeytin", "Çınar", "Iğdır", "İnci", "Armut"):
            eser(title=ad)
        assert _adlari(selectors.works(order="title")) == [
            "Armut",
            "Çınar",
            "Iğdır",
            "İnci",
            "Zeytin",
        ]

    def test_yazar_ekseni_soyada_gore_ve_turkcedir(self) -> None:
        eser(title="A", authors="Sabahattin Ali")
        eser(title="B", authors="Çetin Altan")
        eser(title="C", authors="Yaşar Kemal")
        eser(title="D", authors="Ahmet Ümit")
        assert _adlari(selectors.works(order="author")) == ["A", "B", "C", "D"]

    def test_konu_ekseni_turk_alfabesi_sirasindadir(self) -> None:
        eser(title="A", subjects="Şiir")
        eser(title="B", subjects="Coğrafya")
        eser(title="C", subjects="Iğdır tarihi")
        eser(title="D", subjects="İnceleme")
        assert _adlari(selectors.works(order="subject")) == ["B", "C", "D", "A"]

    def test_turk_alfabesinde_olmayan_harfler_listenin_basina_dusmez(self) -> None:
        """Q/W/X okul kütüphanesinde sıradandır (İngilizce bölümü, yabancı yazarlar).

        Alfabe dışı sayılsalardı 0 önceliğine düşer ve 'A'dan da önce, listenin
        EN ÜSTÜNDE görünürlerdi.
        """
        for ad in ("Zeytin", "Quo Vadis", "Ada", "Wuthering Heights", "Çınar"):
            eser(title=ad)
        assert _adlari(selectors.works(order="title")) == [
            "Ada",
            "Çınar",
            "Quo Vadis",
            "Wuthering Heights",
            "Zeytin",
        ]

    def test_yabanci_soyadi_yazar_ekseninde_yerine_gelir(self) -> None:
        eser(title="A", authors="Sabahattin Ali")
        eser(title="B", authors="Ahmet Ümit")
        eser(title="C", authors="Virginia Woolf")
        assert _adlari(selectors.works(order="author")) == ["A", "B", "C"]

    def test_duzeltme_isaretli_harf_duz_harfle_ayni_yere_dusler(self) -> None:
        """'Kâmil' 'Kamil'in yanındadır; alfabe dışı sayılsaydı listenin başına düşerdi.

        İki anahtar EŞİTTİR; sıra `pk` ile kararlıdır (sayfalama kuralı).
        """
        for ad in ("Kanat", "Kâmil", "Kamil", "Kabak"):
            eser(title=ad)
        assert _adlari(selectors.works(order="title")) == ["Kabak", "Kâmil", "Kamil", "Kanat"]

    def test_esit_anahtarda_sira_kararlidir(self) -> None:
        """Sayfalama için: aynı adlı eserler sayfalar arasında yer değiştirmez."""
        birinci = eser(title="Aynı Ad")
        ikinci = eser(title="Aynı Ad")
        assert [w.pk for w in selectors.works()] == [birinci.pk, ikinci.pk]

    def test_binary_siralama_kullanilmadigi_gorulur(self) -> None:
        """Ham `title` sıralaması Ç'yi Z'den sonraya atar; anahtar atmaz."""
        eser(title="Çınar")
        eser(title="Zeytin")
        ham = [w.title for w in Work.objects.order_by("title")]
        assert ham == ["Zeytin", "Çınar"]
        assert _adlari(selectors.works()) == ["Çınar", "Zeytin"]


class TestKatlama:
    """Aksan katlaması (DB istemez) — Türk alfabesinin harflerine DOKUNMAZ."""

    def test_aksanli_harf_duz_karsiligina_iner(self) -> None:
        assert keys.fold_search("Kâmil") == keys.fold_search("Kamil")
        assert keys.fold_search("Rüzgâr") == keys.fold_search("rüzgar")
        assert keys.fold_search("Émile") == keys.fold_search("Emile")

    def test_duzeltme_isaretli_i_noktali_kalir(self) -> None:
        """'millî' noktalı i'dir; NFD ayrışması onu NOKTASIZ 'I'ya indirirdi."""
        assert keys.fold_search("millî") == keys.fold_search("milli")
        assert keys.fold_search("millî") != keys.fold_search("millı")

    def test_turk_harfleri_katlanmaz(self) -> None:
        """'ı' ile 'i', 'c' ile 'ç' AYRI kalır (T7) — katlama onları birleştirmez."""
        assert keys.fold_search("ılık") != keys.fold_search("ilik")
        assert keys.fold_search("Çınar") != keys.fold_search("Cinar")
        assert keys.fold_search("Şiir") != keys.fold_search("Siir")

    def test_siralama_anahtari_girdiyle_ayni_uzunluktadir(self) -> None:
        """Anahtar alanı girdiyle aynı boyda saklanır (`Work.sort_key` 500 hane)."""
        for metin in ("Kâmil", "Çınar", "Ø Æ Œ", "한국어", "🙂"):
            assert len(keys.tr_collation_key(metin)) == len(metin)


@pytest.mark.django_db
class TestAnahtarTuretme:
    def test_anahtarlar_kayitta_turetilir(self) -> None:
        work = eser(title="Şiir Kitabı", authors="Behçet Necatigil", subjects="Şiir")
        assert work.search_key == keys.work_search_key(
            title=work.title,
            authors=work.authors,
            subjects=work.subjects,
            isbn=work.isbn,
            isbn13=work.isbn13,
        )
        assert work.sort_key == keys.tr_collation_key("Şiir Kitabı")
        assert work.author_sort_key == keys.tr_collation_key("Necatigil Behçet")
        assert work.subject_sort_key == keys.tr_collation_key("Şiir")

    def test_alan_guncellemesi_anahtari_da_tazeler(self) -> None:
        work = eser(title="Eski Ad")
        work.title = "Yeni Ad"
        work.save(update_fields=["title"])
        work.refresh_from_db()
        assert work.sort_key == keys.tr_collation_key("Yeni Ad")
        assert _adlari(selectors.works(q="yeni")) == ["Yeni Ad"]

    def test_isbn13_kayitta_turetilir(self) -> None:
        work = eser(isbn="0-306-40615-2")
        assert work.isbn13 == "9780306406157"

    def test_anahtar_alanlari_toplu_yazimla_atlanmaz(self) -> None:
        """`bulk_create`/`bulk_update`/`update()` `save()`'i atlar, anahtar bayatlar.

        Kaynak ağacında eser künyesini toplu yazan bir yol YOKTUR. F3 içe
        aktarımı toplu yazacaksa anahtarları elle doldurmalı ve bu testi kendi
        gerekçesiyle güncellemelidir.
        """
        kok = Path(__file__).resolve().parent.parent
        bulgular: list[str] = []
        for dosya in sorted(kok.rglob("*.py")):
            if "tests" in dosya.parts:
                continue
            for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
                if not isinstance(dugum, ast.Call) or not isinstance(dugum.func, ast.Attribute):
                    continue
                kaynak = ast.unparse(dugum)
                if dugum.func.attr == "bulk_create" and "Work" in ast.unparse(dugum.func.value):
                    bulgular.append(f"{dosya.name}:{dugum.lineno}")
                elif dugum.func.attr in ("update", "bulk_update") and any(
                    alan in kaynak for alan in ANAHTAR_KAYNAKLARI
                ):
                    bulgular.append(f"{dosya.name}:{dugum.lineno}")
        assert bulgular == [], f"Anahtarları atlayan toplu yazım: {bulgular}"
