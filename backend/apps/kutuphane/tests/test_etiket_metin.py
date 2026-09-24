"""Etiket metni: genişlik tablosu, Türkçe güvenli kırpma, yer numarası satırları, iç düzen.

`labels/metrics.py`'deki DejaVu genişlik tablosu gerçek yazı tipi dosyasıyla
karşılaştırılır (konteynerde `fonts-dejavu-core`; dosya yoksa test atlanır).
İç düzen testleri PDF'siz koşar: her kutunun hücrenin içinde kaldığı ve her
metnin kutusuna sığdığı, EN UZUN gerçek veriyle sınanır (CLAUDE.md §3: kısa
fixture yanlış yeşil verir). PDF'in kendisinden yapılan ölçüm `test_etiket_pdf.py`'dedir.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest
import segno

from apps.kutuphane.labels import metrics
from apps.kutuphane.labels.content import (
    MISSING_CALL_NUMBER,
    LabelContent,
    LabelItem,
    items_from_barcodes,
    split_call_number,
    validate_items,
)
from apps.kutuphane.labels.geometry import CellBox, LabelError, SheetGeometry
from apps.kutuphane.labels.layout import (
    FIT_SAFETY_MM,
    GraphicBox,
    LabelLayout,
    TextBox,
    barcode_block_width,
    label_layout,
    qr_svg,
    supports,
)
from apps.kutuphane.models import Work

FONT_KLASORU = Path("/usr/share/fonts/truetype/dejavu")

#: Modeldeki en uzun değerler (Work.title 500, Work.call_number 80,
#: SchoolConfig.kisa_ad 24) — hepsi uydurmadır.
EN_UZUN_AD = ("Şu Çılgın Türkler: İstiklâl Harbi'nin Işığında Ğ Ü Ş İ Ö Ç " * 20)[:500]
EN_UZUN_YER = ("894.35133 ÖZDEMİRCİOĞLU 12.CİLT " * 5)[:80]
EN_GENIS_YER = "W" * 80
EN_UZUN_OKUL = "W" * 24
TURKCE_OKUL = "Çığlıköy Şehit Öğ. İHO"

TABAKALAR = {
    "65": SheetGeometry(10.7, 4.75, 38.1, 21.2, 13, 5, gutter_x=2.5),
    "44": SheetGeometry(8.8, 8.0, 48.5, 25.4, 11, 4),
    "40": SheetGeometry(0.0, 0.0, 52.5, 29.7, 10, 4),
}


def test_model_sinirlari_testteki_en_uzun_verilerle_ayni() -> None:
    """Model sınırı büyürse en uzun veri testleri de büyümeli (yanlış yeşil olmasın)."""
    from apps.okul.models import SchoolConfig

    assert Work._meta.get_field("title").max_length == len(EN_UZUN_AD)
    assert Work._meta.get_field("call_number").max_length == len(EN_UZUN_YER) == len(EN_GENIS_YER)
    assert SchoolConfig._meta.get_field("kisa_ad").max_length == len(EN_UZUN_OKUL)


# ============================================================ Genişlik tablosu
@pytest.mark.parametrize(
    ("dosya", "tablo"),
    [("DejaVuSans.ttf", metrics.REGULAR_WIDTHS), ("DejaVuSans-Bold.ttf", metrics.BOLD_WIDTHS)],
)
def test_genislik_tablosu_gercek_yazi_tipiyle_ayni(dosya: str, tablo: dict[int, int]) -> None:
    yol = FONT_KLASORU / dosya
    if not yol.is_file():
        pytest.skip(f"{yol} yok (DejaVu yalnız konteyner imajında kurulu)")
    from PIL import ImageFont

    yazi_tipi = ImageFont.truetype(str(yol), metrics.UNITS_PER_EM)
    farkli = [
        f"U+{kod:04X}"
        for kod, genislik in tablo.items()
        if kod != 0xAD and abs(yazi_tipi.getlength(chr(kod)) - genislik) > 0.01
    ]
    assert farkli == []
    assert len(tablo) >= 320


def test_turk_alfabesinin_butun_harfleri_tabloda() -> None:
    harfler = "abcçdefgğhıijklmnoöprsştuüvyzâîûABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZÂÎÛqwxQWX"
    for tablo in (metrics.REGULAR_WIDTHS, metrics.BOLD_WIDTHS):
        assert [h for h in harfler if ord(h) not in tablo] == []


def test_tabloda_olmayan_karakter_ihtiyatli_birlesen_isaret_sifir() -> None:
    assert metrics.char_units("漢") == metrics.UNITS_PER_EM
    assert metrics.char_units("̇") == 0
    genislik = metrics.text_width_mm("ABC", 10)
    assert genislik == pytest.approx((1401 + 1405 + 1430) / 2048 * 10 * 25.4 / 72)


# ============================================================ Temizleme ve kırpma
class TestTurkceGuvenliKirpma:
    def test_metin_temizlenir(self) -> None:
        assert metrics.clean_text("  Kürk­mantolu\n\tMadonna​ ") == "Kürkmantolu Madonna"
        # NFC: ayrışık "ü" (u + U+0308) tek karaktere birleşir.
        assert metrics.clean_text("Kürk") == "Kürk"
        assert metrics.clean_text(None) == ""

    def test_sigan_metne_dokunulmaz(self) -> None:
        assert metrics.fit_text("İnce Memed", 50, 6) == "İnce Memed"

    def test_sigmayan_metin_sozcuk_sinirindan_uc_noktayla_kisalir(self) -> None:
        sonuc = metrics.fit_text("Şu Çılgın Türkler: İstiklâl Harbi'nin Işığında", 25, 6)
        assert sonuc.endswith(metrics.ELLIPSIS)
        govde = sonuc.removesuffix(metrics.ELLIPSIS)
        assert "Şu Çılgın Türkler: İstiklâl Harbi'nin Işığında".startswith(govde)
        assert not govde.endswith((" ", ":", ","))
        assert metrics.text_width_mm(sonuc, 6) <= 25

    def test_harf_buyuklugu_degismez(self) -> None:
        """Çıplak `.upper()` 'i'yi 'I' basardı; kırpma yalnız karakter atar."""
        sonuc = metrics.fit_text("ışık ılık iğne İzmir " * 10, 30, 6)
        assert "I" not in sonuc and "i" in sonuc

    def test_birlesen_isaret_tabanindan_ayrilmaz(self) -> None:
        """'i̇' (i + U+0307) NFC'de de iki kod noktasıdır; kesme ikisinin arasına düşmez."""
        metin = "i̇" * 60
        for genislik in (3.0, 4.0, 5.1, 7.3):
            sonuc = metrics.fit_text(metin, genislik, 6)
            govde = sonuc.removesuffix(metrics.ELLIPSIS)
            assert govde == "" or not unicodedata.combining(govde[0])
            assert len(govde) % 2 == 0, "taban harf ile birleşen nokta ayrıldı"

    @pytest.mark.parametrize("genislik", [0.5, 2.0, 10.0, 25.0, 36.0])
    @pytest.mark.parametrize("kalin", [False, True])
    def test_sonuc_hic_bir_zaman_genisligi_asmaz(self, genislik: float, kalin: bool) -> None:
        for metin in (EN_UZUN_AD, EN_UZUN_YER, EN_GENIS_YER, EN_UZUN_OKUL, "漢字" * 40):
            sonuc = metrics.fit_text(metin, genislik, 6, bold=kalin)
            assert metrics.text_width_mm(sonuc, 6, bold=kalin) <= genislik + 1e-9

    def test_hic_sigmayan_genislikte_bos_ya_da_uc_nokta(self) -> None:
        assert metrics.fit_text("Kitap", 0.1, 6) == ""
        assert metrics.fit_text("WWWW", metrics.text_width_mm("…", 6) + 0.01, 6) == "…"


# ============================================================ Yer numarası satırları
@pytest.mark.parametrize(
    ("yer", "satirlar"),
    [
        ("813.54 STE", ["813.54", "STE"]),
        ("894.3533 ALİ 2. cilt", ["894.3533", "ALİ", "2. cilt"]),
        ("REF 030 ANA", ["REF", "030", "ANA"]),
        ("813.54", ["813.54"]),
        ("813/.54 STE", ["813/.54", "STE"]),  # Dewey bölümleme işareti satır bölmez
        ("  813.54\n  STE  ", ["813.54", "STE"]),
        ("", []),
    ],
)
def test_yer_numarasi_bosluktan_bolunur(yer: str, satirlar: list[str]) -> None:
    assert split_call_number(yer) == satirlar


def test_yer_numarasi_en_cok_uc_satir() -> None:
    assert split_call_number("398.2 GRİ 1 C. 3 N.") == ["398.2", "GRİ", "1 C. 3 N."]


# ============================================================ Kalemler
class TestKalemler:
    def test_numara_listesi_dogrulanir(self) -> None:
        kalemler = items_from_barcodes(["2026000123", "2026000124"])
        assert [k.printed_number for k in kalemler] == ["2026-000123", "2026-000124"]
        assert all(k.title == "" and k.call_number == "" for k in kalemler)

    @pytest.mark.parametrize(
        "numara", ["2026-000123", "202600012", "9780306406157", "94718263", "0975123456"]
    )
    def test_nusha_barkodu_olmayan_numara_reddedilir(self, numara: str) -> None:
        with pytest.raises(LabelError) as hata:
            items_from_barcodes([numara])
        assert hata.value.field == "barcodes"

    def test_ayni_numara_iki_kez_basilmaz(self) -> None:
        with pytest.raises(LabelError, match="iki kez"):
            validate_items(items_from_barcodes(["2026000123", "2026000123"]))

    def test_bos_liste_ve_ust_sinir(self) -> None:
        from apps.kutuphane.labels.geometry import MAX_LABELS_PER_DOCUMENT

        with pytest.raises(LabelError, match="Basılacak etiket yok"):
            validate_items([])
        cok = [LabelItem(f"2026{i:06d}") for i in range(1, MAX_LABELS_PER_DOCUMENT + 2)]
        with pytest.raises(LabelError, match="en çok"):
            validate_items(cok)


# ============================================================ İç düzen
def _hucre(tabaka: SheetGeometry, sira: int = 0) -> CellBox:
    return tabaka.cell(sira)


def _kose_listesi(duzen: LabelLayout) -> list[tuple[float, float, float, float]]:
    """Bütün kutular: (sol, üst, sağ, alt) — hücreye göre mm."""
    kutular: list[TextBox | GraphicBox] = [*duzen.texts, *duzen.graphics]
    return [(k.left, k.top, k.left + k.width, k.top + k.height) for k in kutular]


def _kutular_hucrede(duzen: LabelLayout, hucre: CellBox) -> None:
    for sol, ust, sag, alt in _kose_listesi(duzen):
        assert sol >= -1e-9 and ust >= -1e-9, (sol, ust)
        assert sag <= hucre.width + 1e-9, (sag, hucre.width)
        assert alt <= hucre.height + 1e-9, (alt, hucre.height)
    for metin in duzen.texts:
        genislik = metrics.text_width_mm(metin.text, metin.size_pt, bold=metin.bold)
        assert genislik <= metin.width - FIT_SAFETY_MM + 1e-9, metin


def _ust_uste_binmez(duzen: LabelLayout) -> None:
    kutular = _kose_listesi(duzen)
    for i, a in enumerate(kutular):
        for b in kutular[i + 1 :]:
            kesisim_x = min(a[2], b[2]) - max(a[0], b[0])
            kesisim_y = min(a[3], b[3]) - max(a[1], b[1])
            assert kesisim_x <= 1e-6 or kesisim_y <= 1e-6, (a, b)


@pytest.mark.parametrize("tabaka_adi", ["65", "44", "40"])
@pytest.mark.parametrize("yer", [EN_UZUN_YER, EN_GENIS_YER, "813.54 ALİ", ""])
@pytest.mark.parametrize("okul", [EN_UZUN_OKUL, TURKCE_OKUL, ""])
def test_barkod_etiketi_en_uzun_veriyle_hucreden_tasmaz(
    tabaka_adi: str, yer: str, okul: str
) -> None:
    hucre = _hucre(TABAKALAR[tabaka_adi], 7)
    kalem = LabelItem("2026000123", EN_UZUN_AD, yer)
    for qr in (False, True) if tabaka_adi != "65" else (False,):
        duzen = label_layout(kalem, hucre, content=LabelContent.BARCODE, school=okul, include_qr=qr)
        _kutular_hucrede(duzen, hucre)
        _ust_uste_binmez(duzen)
        roller = [k.role for k in duzen.texts]
        assert roller[:2] == ["title", "number"]
        assert [g.role for g in duzen.graphics] == (["barcode", "qr"] if qr else ["barcode"])


@pytest.mark.parametrize("tabaka_adi", ["65", "44", "40"])
@pytest.mark.parametrize(
    "yer", [EN_UZUN_YER, EN_GENIS_YER, "813.54 ALİ", "894.3533 KEM 2. cilt", ""]
)
@pytest.mark.parametrize("okul", [EN_UZUN_OKUL, TURKCE_OKUL, ""])
def test_sirt_etiketi_en_uzun_veriyle_hucreden_tasmaz(tabaka_adi: str, yer: str, okul: str) -> None:
    hucre = _hucre(TABAKALAR[tabaka_adi], 3)
    duzen = label_layout(
        LabelItem("2026000123", EN_UZUN_AD, yer), hucre, content=LabelContent.SPINE, school=okul
    )
    _kutular_hucrede(duzen, hucre)
    _ust_uste_binmez(duzen)
    satirlar = [k.text for k in duzen.texts if k.role == "spine"]
    assert 1 <= len(satirlar) <= 3
    if not yer:
        assert satirlar == [MISSING_CALL_NUMBER]
    assert duzen.graphics == ()


def test_sirt_satirlari_sigiyorsa_ayni_boyda_sigmayan_yalniz_kendisi_kuculur() -> None:
    hucre = _hucre(TABAKALAR["65"])
    kisa = label_layout(
        LabelItem("2026000123", "x", "813.54 ALİ 2. cilt"),
        hucre,
        content=LabelContent.SPINE,
        school="",
    )
    assert len({k.size_pt for k in kisa.texts}) == 1
    uzun = label_layout(
        LabelItem("2026000123", "x", "813.54 ÖZDEMİRCİOĞLUGİLLERDEN"),
        hucre,
        content=LabelContent.SPINE,
        school="",
    )
    boylar = [k.size_pt for k in uzun.texts]
    assert boylar[0] > boylar[1], "kısa sınıflama kodu uzun yazar kodu yüzünden küçüldü"


def test_bos_barkod_etiketi_kunye_tasimaz() -> None:
    hucre = _hucre(TABAKALAR["65"])
    duzen = label_layout(
        LabelItem("2026000123"), hucre, content=LabelContent.BLANK_BARCODE, school=TURKCE_OKUL
    )
    assert [(k.role, k.text) for k in duzen.texts] == [
        ("school", TURKCE_OKUL),
        ("number", "2026-000123"),
    ]
    _kutular_hucrede(duzen, hucre)
    okulsuz = label_layout(
        LabelItem("2026000123"), hucre, content=LabelContent.BLANK_BARCODE, school=""
    )
    assert [k.role for k in okulsuz.texts] == ["number"]


def test_barkod_bloku_110_modul_ve_hucrede_ortali() -> None:
    assert barcode_block_width() == pytest.approx(110 * 0.254) == pytest.approx(27.94)
    hucre = _hucre(TABAKALAR["65"], 12)
    duzen = label_layout(
        LabelItem("2026000123", "Kitap", "813 ALİ"), hucre, content=LabelContent.BARCODE, school=""
    )
    bar = duzen.graphics[0]
    assert bar.width == pytest.approx(27.94)
    sol, sag = bar.left, hucre.width - bar.left - bar.width
    assert abs(sol - sag) <= 0.254 + 1e-9  # yazıcı noktasına hizalama en çok X kaydırır
    assert ((hucre.left + bar.left) / 0.254) == pytest.approx(
        round((hucre.left + bar.left) / 0.254)
    )
    assert 6.35 <= bar.height <= 12.0


class TestSablonUygunlugu:
    def test_qr_yalniz_48_5x25_4_ve_ustu(self) -> None:
        assert not supports(38.1, 21.2, content=LabelContent.BARCODE, include_qr=True)
        assert supports(48.5, 25.4, content=LabelContent.BARCODE, include_qr=True)
        assert supports(52.5, 29.7, content=LabelContent.BARCODE, include_qr=True)

    def test_dar_ya_da_alcak_etiket_barkod_tasimaz(self) -> None:
        assert supports(38.1, 21.2, content=LabelContent.BARCODE)
        assert not supports(25.4, 21.2, content=LabelContent.BARCODE)
        assert not supports(38.1, 12.0, content=LabelContent.BARCODE)
        with pytest.raises(LabelError, match="genişliği barkoda yetmiyor"):
            label_layout(
                LabelItem("2026000123"),
                CellBox(0, 0, 0, 0, 0, 25.0, 30.0),
                content=LabelContent.BARCODE,
                school="",
            )

    def test_qr_kucuk_etikette_acikca_reddedilir(self) -> None:
        with pytest.raises(LabelError) as hata:
            label_layout(
                LabelItem("2026000123"),
                _hucre(TABAKALAR["65"]),
                content=LabelContent.BARCODE,
                school="",
                include_qr=True,
            )
        assert hata.value.field == "include_qr"
        assert "48,5 × 25,4" in hata.value.text


def test_qr_icerigi_rakamdir_ve_modul_matrisini_birebir_basar() -> None:
    """QR URL taşımaz (§7.2); SVG'deki koyu modüller segno'nun matrisiyle aynıdır."""
    kod = segno.make_qr("2026000123", error="m")
    assert kod.mode == "numeric"
    assert not kod.is_micro
    svg = qr_svg("2026000123", 17.0)
    assert "http" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
    import re

    koyu: set[tuple[int, int]] = set()
    for x, y, w in re.findall(r'<rect x="(\d+)" y="(\d+)" width="(\d+)" height="1"/>', svg):
        for sutun in range(int(x), int(x) + int(w)):
            koyu.add((sutun - 4, int(y) - 4))
    beklenen = {
        (s, r) for r, satir in enumerate(kod.matrix) for s, deger in enumerate(satir) if deger
    }
    assert koyu == beklenen
    assert 'width="17.000mm"' in svg
