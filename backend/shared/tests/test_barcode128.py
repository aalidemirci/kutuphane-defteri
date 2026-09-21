"""Code128-C üreteci (`shared/barcode128.py`) — tasarım T8, §7.1-7.2.

Beklenen desenler standart tablonun **bit gösterimiyle** yazılır (1 = bar
modülü, 0 = boşluk modülü). Modül tablosu genişlik gösterimini kullandığı için
bu ikinci gösterim, tablodaki bir yazım hatasını modülün kendi verisine
dayanmadan yakalar.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest

from shared import barcode128 as bc

SVG_NS = "{http://www.w3.org/2000/svg}"

#: Code128 standart tablosundan seçilmiş semboller: değer → bit deseni.
STANDART_DESENLER: dict[int, str] = {
    0: "11011001100",
    1: "11001101100",
    12: "10110011100",
    20: "11001001110",
    23: "11101101110",
    26: "11100100110",
    90: "11011110110",
    99: "10111011110",  # CODE C
    100: "10111101110",  # CODE B / FNC4
    101: "11101011110",  # CODE A
    102: "11110101110",  # FNC1
    103: "11010000100",  # START A
    104: "11010010000",  # START B
    105: "11010011100",  # START C
    106: "1100011101011",  # STOP
}


def _bitler(genislikler: str) -> str:
    """Genişlik gösterimini bit gösterimine çevirir (bar ile başlar)."""
    return "".join(
        ("1" if sira % 2 == 0 else "0") * int(genislik) for sira, genislik in enumerate(genislikler)
    )


def _svg_koku(metin: str) -> ET.Element:
    # Girdi bu modülün kendi çıktısıdır (dış veri değil); S314 burada geçersiz.
    return ET.fromstring(metin)  # noqa: S314


def _mm_degeri(ozellik: str) -> float:
    assert ozellik.endswith("mm"), ozellik
    return float(ozellik.removesuffix("mm"))


# ---------------------------------------------------------------------------
# Desen tablosu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("deger", "beklenen"), sorted(STANDART_DESENLER.items()))
def test_standart_tablodaki_sembol_deseni(deger: int, beklenen: str) -> None:
    assert _bitler(bc.PATTERNS[deger]) == beklenen


def test_desen_tablosu_butunlugu() -> None:
    """107 sembol; her biri 11 modül (STOP 13), bar modül sayısı çift, hepsi farklı.

    Çift bar modülü Code128'in sembol içi eşlik (parity) özelliğidir: tek bir
    genişlik yanlış yazılırsa ya toplam 11'den sapar ya eşlik bozulur.
    """
    assert len(bc.PATTERNS) == 107
    assert len(set(bc.PATTERNS)) == 107
    for deger, desen in enumerate(bc.PATTERNS):
        beklenen_eleman = 7 if deger == bc.STOP else 6
        assert len(desen) == beklenen_eleman, deger
        assert set(desen) <= set("1234"), deger
        genislikler = [int(harf) for harf in desen]
        assert sum(genislikler) == (13 if deger == bc.STOP else 11), deger
        assert sum(genislikler[0::2]) % 2 == 0, deger


# ---------------------------------------------------------------------------
# Sağlama ve sembol dizisi
# ---------------------------------------------------------------------------


def test_nusha_barkodunun_saglamasi_elle_hesaplanan_ornek() -> None:
    """2026000123 (tasarım §7.1'deki örnek nüsha barkodu), elle hesap:

    çiftler 20, 26, 00, 01, 23 →
    105 + 1·20 + 2·26 + 3·0 + 4·1 + 5·23 = 105 + 20 + 52 + 0 + 4 + 115 = 296;
    296 = 2·103 + 90 → sağlama **90**.
    """
    assert bc.encode_values("2026000123") == (105, 20, 26, 0, 1, 23, 90, 106)


def test_kart_numarasinin_saglamasi_elle_hesaplanan_ornek() -> None:
    """94718263 (tasarım §7.1'deki örnek kart no), elle hesap:

    çiftler 94, 71, 82, 63 →
    105 + 1·94 + 2·71 + 3·82 + 4·63 = 105 + 94 + 142 + 246 + 252 = 839;
    839 = 8·103 + 15 → sağlama **15**.
    """
    assert bc.encode_values("94718263") == (105, 94, 71, 82, 63, 15, 106)


def test_saglama_mod_103_sinirlari() -> None:
    # "00": 105 + 0 = 105 = 103 + 2 → 2.
    assert bc.checksum([0]) == 2
    # "0150": 105 + 1·1 + 2·50 = 206 = 2·103 → 0 (kalan sıfır da geçerli sembol).
    assert bc.encode_values("0150") == (105, 1, 50, 0, 106)
    # "98": 105 + 98 = 203 = 103 + 100 → 100 (veri alanı dışındaki değerler de çıkar).
    assert bc.checksum([98]) == 100


def test_tam_sembol_bit_dizisi_standart_gosterimle_uyusur() -> None:
    s = STANDART_DESENLER
    beklenen = s[105] + s[20] + s[26] + s[0] + s[1] + s[23] + s[90] + s[106]
    assert bc.module_pattern("2026000123") == beklenen
    # En kısa geçerli girdi: START-C + "00" + sağlama 2 + STOP.
    assert bc.module_pattern("00") == s[105] + s[0] + _bitler(bc.PATTERNS[2]) + s[106]


def test_eleman_dizisi_bar_ile_baslar_bar_ile_biter() -> None:
    genislikler = bc.element_widths("2026000123")
    # START (6) + 5 çift (30) + sağlama (6) + STOP (7) = 49 eleman; tek sayı → bar ile biter.
    assert len(genislikler) == 49
    assert sum(genislikler) == bc.module_count("2026000123", quiet_zone=False)
    desen = bc.module_pattern("2026000123")
    assert desen.startswith("1")
    assert desen.endswith("11")  # STOP'un son barı 2 modül


# ---------------------------------------------------------------------------
# Modül sayıları (tasarım §7.2)
# ---------------------------------------------------------------------------


def test_nusha_barkodu_90_modul_sessiz_bolgeyle_110() -> None:
    assert bc.module_count("2026000123", quiet_zone=False) == 90
    assert bc.module_count("2026000123") == 110
    assert len(bc.module_pattern("2026000123")) == 90


def test_kart_numarasi_79_modul_sessiz_bolgeyle_99() -> None:
    assert bc.module_count("94718263", quiet_zone=False) == 79
    assert bc.module_count("94718263") == 99


@pytest.mark.parametrize("hane", [2, 4, 6, 8, 10, 12, 20])
def test_modul_sayisi_genel_formul(hane: int) -> None:
    # 11 (START) + 11·(n/2) + 11 (sağlama) + 13 (STOP)
    assert bc.module_count("7" * hane, quiet_zone=False) == 11 * (hane // 2) + 35


def test_bar_konumlari_sessiz_bolge_kadar_kayar() -> None:
    barlar = bc.bar_spans("2026000123")
    assert barlar[0] == (10, 2)  # START-C'nin ilk barı 10X sessiz bölgeden sonra
    son_bas, son_genislik = barlar[-1]
    assert son_bas + son_genislik == 110 - 10
    assert bc.bar_spans("2026000123", quiet_zone_modules=12)[0] == (12, 2)


# ---------------------------------------------------------------------------
# Girdi reddi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("girdi", ["1", "123", "202600012", "947182635"])
def test_tek_uzunluk_reddedilir(girdi: str) -> None:
    with pytest.raises(ValueError, match="çift sayıda rakam"):
        bc.encode_values(girdi)


@pytest.mark.parametrize(
    "girdi",
    [
        "",
        "2026-000123",  # basılı biçim; okuyucu girdisi önce normalize edilir
        "12a4",
        " 1234",
        "1234\n",
        "²²",  # üst simge — str.isdigit() bunu kabul ederdi
        "١٢",  # Arap-Hint rakamları
        "１２",  # tam genişlik rakamlar
    ],
)
def test_rakam_disi_ya_da_bos_girdi_reddedilir(girdi: str) -> None:
    with pytest.raises(ValueError):
        bc.encode_values(girdi)
    with pytest.raises(ValueError):
        bc.svg(girdi)


def test_hata_iletisi_girdiyi_basmaz() -> None:
    """Kart no şifreli alandır (§6.3); istisna iletisi günlüğe düşebilir."""
    for girdi in ("947182635", "9471-8263"):
        with pytest.raises(ValueError) as hata:
            bc.encode_values(girdi)
        assert girdi not in str(hata.value)
        assert "94718263" not in str(hata.value)


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------


def test_svg_gecerli_xml_ve_genislik_mm_hesabiyla_uyusur() -> None:
    kok = _svg_koku(bc.svg("2026000123"))
    assert kok.tag == f"{SVG_NS}svg"
    # 110 modül × 0,254 mm = 27,94 mm (tasarım §7.2: "sessiz bölgelerle 27,9 mm").
    assert math.isclose(_mm_degeri(kok.attrib["width"]), 110 * 0.254)
    assert kok.attrib["width"] == "27.94mm"
    assert kok.attrib["height"] == "8mm"
    # Kullanıcı birimi mm: viewBox genişliği mm genişliğiyle aynı sayıdır.
    assert kok.attrib["viewBox"] == "0 0 27.94 8"

    kart = _svg_koku(bc.svg("94718263"))
    assert kart.attrib["width"] == "25.146mm"  # 99 × 0,254


def test_svg_modul_ve_yukseklik_parametreleri() -> None:
    kok = _svg_koku(bc.svg("2026000123", module_mm=0.508, height_mm=12.5))
    assert kok.attrib["width"] == "55.88mm"  # 110 × 0,508 (600 dpi'de 12 nokta)
    assert kok.attrib["height"] == "12.5mm"
    assert kok.attrib["viewBox"] == "0 0 55.88 12.5"
    genis = _svg_koku(bc.svg("2026000123", quiet_zone_modules=15))
    assert math.isclose(_mm_degeri(genis.attrib["width"]), (90 + 30) * 0.254)


@pytest.mark.parametrize("modul_mm", [0.254, 0.338, 0.508])
def test_svg_barlari_modul_dizisini_birebir_verir(modul_mm: float) -> None:
    """SVG'deki dikdörtgenlerden modül dizisi geri kurulur; sessiz bölge boş kalır."""
    kok = _svg_koku(bc.svg("2026000123", module_mm=modul_mm))
    grup = kok.find(f"{SVG_NS}g")
    assert grup is not None
    assert grup.attrib["fill"] == "#000"
    toplam = round(_mm_degeri(kok.attrib["width"]) / modul_mm)
    assert toplam == 110
    moduller = ["0"] * toplam
    for bar in grup.findall(f"{SVG_NS}rect"):
        bas = float(bar.attrib["x"]) / modul_mm
        genislik = float(bar.attrib["width"]) / modul_mm
        # Konum ve genişlik modülün tam katıdır (yazıcı noktasına hizalama).
        assert math.isclose(bas, round(bas), abs_tol=1e-3)
        assert math.isclose(genislik, round(genislik), abs_tol=1e-3)
        for sira in range(round(bas), round(bas) + round(genislik)):
            assert moduller[sira] == "0", "barlar üst üste binmemeli"
            moduller[sira] = "1"
    assert "".join(moduller) == "0" * 10 + bc.module_pattern("2026000123") + "0" * 10


def test_svg_arka_plani_tum_alani_beyaz_kaplar() -> None:
    kok = _svg_koku(bc.svg("94718263"))
    arka = kok.find(f"{SVG_NS}rect")
    assert arka is not None
    assert arka.attrib == {"width": "25.146", "height": "8", "fill": "#fff"}


@pytest.mark.parametrize(
    ("modul_mm", "yukseklik_mm"),
    [
        (0.0, 8.0),
        (-0.254, 8.0),
        (math.nan, 8.0),
        (math.inf, 8.0),
        (0.254, 0.0),
        (0.254, -1.0),
        (0.254, math.nan),
    ],
)
def test_svg_gecersiz_olcu_reddedilir(modul_mm: float, yukseklik_mm: float) -> None:
    with pytest.raises(ValueError, match="sıfırdan büyük"):
        bc.svg("2026000123", module_mm=modul_mm, height_mm=yukseklik_mm)


def test_dar_sessiz_bolge_reddedilir() -> None:
    with pytest.raises(ValueError, match="Sessiz bölge en az 10"):
        bc.svg("2026000123", quiet_zone_modules=9)
    with pytest.raises(ValueError, match="Sessiz bölge en az 10"):
        bc.bar_spans("2026000123", quiet_zone_modules=0)
