"""Etiket PDF'i — PDF'İN KENDİSİNDEN ölçülen kod kapısı (F4 sözleşmesi L).

Ölçüler `etiket_olcum.py` yorumlayıcısıyla, üretilen PDF'in içerik akışından
okunur (HTML'den ya da programın kendi hesabından DEĞİL):

- **Code128 test vektörleri**: bilinen girdilerin modül dizisi standart tablonun
  bit gösterimiyle karşılaştırılır.
- **Modül genişliği toleransı**: PDF'teki her barın ve boşluğun genişliği
  X = 0,254 mm'nin beklenen katıdır (± `TOLERANS_MM`, yazıcıdan bağımsız
  sayısal tolerans); barkodun sol kenarı yazıcı nokta ızgarasındadır; iki
  yanda 10X sessiz bölge boştur ve etiketin içindedir.
- **Sayfa bütçesi** EN UZUN gerçek veriyle: 65 etiket tek sayfa, 66. ikinci
  sayfa (65'li A4); QR'lı 44'lüde 44 / 45.
- **Başlangıç hücresi**, **kalibrasyon kayması**, **sırt ve barkodun aynı sıra
  ve hücre düzeni**, **taşma yok** (her metin koşusu PDF'in kendi genişlik
  tablosuyla ölçülür ve kendi hücresinin içinde kalır).
- **Yazıcının basamadığı kenar payı**: bar, QR modülü, yazı ve kalibrasyon
  cetveli sayfa kenarından en az `PRINT_SAFE_MARGIN_MM` içeridedir (kenarsız
  40'lı tabaka dahil).

Veritabanı gerekmez: şablon `SheetGeometry` ile, kısa okul adı parametreyle
verilir. Bütün veriler uydurmadır.
"""

from __future__ import annotations

from functools import cache

import pytest

from apps.kutuphane.labels import (
    CalibrationOffset,
    LabelItem,
    SheetGeometry,
    build_parts,
    items_from_barcodes,
    render_calibration_sheet,
    render_labels,
)
from apps.kutuphane.labels.geometry import PRINT_SAFE_MARGIN_MM, CellBox
from apps.kutuphane.tests import etiket_olcum as olcum
from shared import barcode128

X = barcode128.DEFAULT_MODULE_MM
#: Modül genişliği toleransı (mm). PDF sayıları 6 ondalıklı px'tir (~1e-6 mm);
#: konumlar HTML'de 0,001 mm'ye yuvarlanır. Yazıcının nokta hatası kapsam dışıdır.
TOLERANS_MM = 0.002
#: Metin koşusunun ilerleme genişliği için tolerans (mm): kutu kenarına yaslanan
#: yazıda konum yuvarlaması (0,001 mm) ve Pango'nun alt piksel yerleşimi birkaç
#: binde bir mm fark verir. Güvenli basım payı (5 mm) yanında önemsizdir.
METIN_TOLERANS_MM = 0.01
#: Bar sayılacak en küçük dolgu yüksekliği (mm) — QR modülleri ve çizgiler elenir.
BAR_MIN_YUKSEKLIK = 5.0

TABAKA_65 = SheetGeometry(10.7, 4.75, 38.1, 21.2, 13, 5, gutter_x=2.5)
TABAKA_44 = SheetGeometry(8.8, 8.0, 48.5, 25.4, 11, 4)

EN_UZUN_AD = ("Şu Çılgın Türkler: İstiklâl Harbi'nin Işığında Ğ Ü Ş İ Ö Ç " * 20)[:500]
EN_UZUN_YER = ("894.35133 ÖZDEMİRCİOĞLU 12.CİLT " * 5)[:80]
EN_UZUN_OKUL = "W" * 24

#: Code128 standart tablosunun bit gösterimi (1 bar, 0 boşluk) — modülün kendi
#: genişlik tablosundan bağımsız kaynak.
STANDART: dict[int, str] = {
    0: "11011001100",
    1: "11001101100",
    12: "10110011100",
    20: "11001001110",
    23: "11101101110",
    26: "11100100110",
    90: "11011110110",
    102: "11110101110",
    105: "11010011100",  # START C
    106: "1100011101011",  # STOP
}

#: (girdi, sembol değerleri: START-C, çiftler, sağlama, STOP). Sağlamalar elle:
#: 2026000123 → 105+20+52+0+4+115 = 296 ≡ 90; 2026120001 → 105+20+52+36+0+5 = 218 ≡ 12;
#: 2026002626 → 105+20+52+0+104+130 = 411 ≡ 102 (mod 103).
VEKTORLER = (
    ("2026000123", (105, 20, 26, 0, 1, 23, 90, 106)),
    ("2026120001", (105, 20, 26, 12, 0, 1, 12, 106)),
    ("2026002626", (105, 20, 26, 0, 26, 26, 102, 106)),
)


def _kalemler(
    adet: int, *, ad: str = EN_UZUN_AD, yer: str = EN_UZUN_YER, bas: int = 1
) -> list[LabelItem]:
    return [LabelItem(f"2026{sira:06d}", ad, yer) for sira in range(bas, bas + adet)]


@cache
def _pdf(
    secim: str,
    adet: int,
    *,
    tabaka: SheetGeometry = TABAKA_65,
    baslangic: int = 1,
    kayma: CalibrationOffset | None = None,
    qr: bool = False,
    uzun: bool = True,
    okul: str = EN_UZUN_OKUL,
) -> bytes:
    """Aynı PDF'i testler arasında bir kez üretir (WeasyPrint yavaştır)."""
    if secim in ("BLANK", "BLANK_BARCODE"):
        kalemler = items_from_barcodes([f"2026{sira:06d}" for sira in range(1, adet + 1)])
    elif uzun:
        kalemler = _kalemler(adet)
    else:
        kalemler = [
            LabelItem(f"2026{s:06d}", f"Eser {s}", f"80{s % 10}.{s} Y{s}")
            for s in range(1, adet + 1)
        ]
    sonuc = render_labels(
        kalemler,
        build_parts(secim, template=tabaka, calibration=kayma),
        start_cell=baslangic,
        school_short_name=okul,
        include_qr=qr,
    )
    return sonuc.pdf


def _barlar(sayfa: olcum.SayfaOlcumu, hucre: CellBox) -> list[olcum.Dolgu]:
    return [
        d
        for d in olcum.barlar_hucrede(sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom)
        if d.yukseklik >= BAR_MIN_YUKSEKLIK
    ]


def _dolu_hucreler(
    sayfa: olcum.SayfaOlcumu, tabaka: SheetGeometry, kayma: CalibrationOffset | None = None
) -> list[int]:
    """Barkod barı taşıyan hücrelerin numaraları (1 tabanlı)."""
    return [h.number for h in tabaka.cells(kayma) if _barlar(sayfa, h)]


# ============================================================ Test vektörleri
@pytest.mark.parametrize(("girdi", "degerler"), VEKTORLER)
def test_code128_test_vektorleri_modul_dizisi(girdi: str, degerler: tuple[int, ...]) -> None:
    assert barcode128.encode_values(girdi) == degerler
    assert barcode128.module_pattern(girdi) == "".join(STANDART[d] for d in degerler)
    assert len(barcode128.module_pattern(girdi)) == 90


# ============================================================ Modül genişliği (PDF)
@pytest.mark.parametrize(("girdi", "degerler"), VEKTORLER)
def test_pdfteki_barlar_modul_katidir_ve_modul_dizisini_verir(
    girdi: str, degerler: tuple[int, ...]
) -> None:
    """Kesirli bir kalibrasyon kayması ve başlangıç hücresiyle bile barlar X'in tam katıdır."""
    kayma = CalibrationOffset(0.37, -0.21)
    pdf = render_labels(
        [LabelItem(girdi, "Deneme", "813.54 ALİ")],
        build_parts("BARCODE", template=TABAKA_65, calibration=kayma),
        start_cell=7,
        school_short_name="Örnek AL",
    ).pdf
    sayfa = olcum.sayfalar(pdf)[0]
    hucre = TABAKA_65.cell(6, kayma)
    barlar = _barlar(sayfa, hucre)
    assert len(barlar) == 25  # START 3 + 5 çift × 3 + sağlama 3 + STOP 4

    moduller: list[str] = []
    for sira, bar in enumerate(barlar):
        kat = bar.genislik / X
        assert abs(bar.genislik - round(kat) * X) <= TOLERANS_MM, (sira, bar.genislik)
        assert 1 <= round(kat) <= 4
        moduller.append("1" * round(kat))
        if sira + 1 < len(barlar):
            bosluk = barlar[sira + 1].x0 - bar.x1
            assert abs(bosluk - round(bosluk / X) * X) <= TOLERANS_MM, (sira, bosluk)
            moduller.append("0" * round(bosluk / X))
    assert "".join(moduller) == "".join(STANDART[d] for d in degerler)

    # Sembol 90X; sol kenar yazıcı nokta ızgarasında (sayfa kökenine göre X'in katı).
    assert barlar[-1].x1 - barlar[0].x0 == pytest.approx(90 * X, abs=TOLERANS_MM)
    assert abs(barlar[0].x0 - round(barlar[0].x0 / X) * X) <= TOLERANS_MM

    # Sessiz bölge: iki yanda 10X boyunca siyah yok ve bölge etiketin içinde.
    sol_bolge = (barlar[0].x0 - 10 * X, barlar[0].x0)
    sag_bolge = (barlar[-1].x1, barlar[-1].x1 + 10 * X)
    assert sol_bolge[0] >= hucre.left and sag_bolge[1] <= hucre.right
    for d in sayfa.siyah_dolgular():
        if d.y1 <= barlar[0].y0 or d.y0 >= barlar[0].y1:
            continue
        for bas, son in (sol_bolge, sag_bolge):
            assert d.x1 <= bas + 1e-6 or d.x0 >= son - 1e-6, "sessiz bölgede siyah var"
    # Barkodun beyaz zemini 110X genişliğindedir (sessiz bölge dahil).
    zeminler = [
        d
        for d in sayfa.dolgular
        if not d.siyah and abs(d.genislik - 110 * X) <= TOLERANS_MM and d.x0 >= hucre.left
    ]
    assert len(zeminler) == 1
    assert zeminler[0].x0 == pytest.approx(sol_bolge[0], abs=TOLERANS_MM)


def test_bar_yuksekligi_ve_okunur_numara_barkodun_altinda() -> None:
    sayfa = olcum.sayfalar(_pdf("BARCODE", 3, uzun=False))[0]
    for sira, hucre in enumerate(TABAKA_65.cells()[:3], start=1):
        barlar = _barlar(sayfa, hucre)
        assert {round(b.yukseklik, 3) for b in barlar} == {round(barlar[0].yukseklik, 3)}
        assert 6.35 <= barlar[0].yukseklik <= 12.0
        numara = [
            y
            for y in olcum.yazilar_hucrede(sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom)
            if y.metin == f"2026-{sira:06d}"
        ]
        assert len(numara) == 1
        assert numara[0].taban > barlar[0].y1


# ============================================================ Sayfa bütçesi (en uzun veri)
@pytest.mark.parametrize(
    ("secim", "adet", "sayfa_sayisi"),
    [
        ("BARCODE", 65, 1),
        ("BARCODE", 66, 2),
        ("SPINE", 65, 1),
        ("SPINE", 66, 2),
        ("BOTH", 65, 2),
        ("BOTH", 66, 4),
        ("BLANK", 65, 1),
        ("BLANK", 66, 2),
    ],
)
def test_65_etiket_tek_sayfaya_66_ikinci_sayfaya(secim: str, adet: int, sayfa_sayisi: int) -> None:
    pdf = _pdf(secim, adet)
    assert olcum.sayfa_sayisi(pdf) == sayfa_sayisi


def test_qrli_44luk_tabakada_44_tek_sayfa_45_iki_sayfa() -> None:
    assert olcum.sayfa_sayisi(_pdf("BARCODE", 44, tabaka=TABAKA_44, qr=True)) == 1
    assert olcum.sayfa_sayisi(_pdf("BARCODE", 45, tabaka=TABAKA_44, qr=True)) == 2


def test_tam_tabakada_her_hucrede_bir_barkod() -> None:
    sayfalar = olcum.sayfalar(_pdf("BARCODE", 66))
    assert _dolu_hucreler(sayfalar[0], TABAKA_65) == list(range(1, 66))
    assert _dolu_hucreler(sayfalar[1], TABAKA_65) == [1]


# ============================================================ Taşma yok
def _hucresi(yazi: olcum.Yazi, hucreler: tuple[CellBox, ...]) -> list[CellBox]:
    """Metin koşusunu tamamen içeren hücreler (tam olarak bir tane olmalı)."""
    return [
        h
        for h in hucreler
        if h.left - 1e-3 <= yazi.x0
        and yazi.x1 <= h.right + 1e-3
        and h.top <= yazi.taban - yazi.boy_mm * 0.75
        and yazi.taban + yazi.boy_mm * 0.25 <= h.bottom
    ]


@pytest.mark.parametrize(
    ("secim", "tabaka", "qr"),
    [
        ("BARCODE", TABAKA_65, False),
        ("SPINE", TABAKA_65, False),
        ("BLANK", TABAKA_65, False),
        ("BARCODE", TABAKA_44, True),
    ],
)
def test_en_uzun_veriyle_hicbir_metin_hucresinden_tasmaz(
    secim: str, tabaka: SheetGeometry, qr: bool
) -> None:
    """Her metin koşusu PDF'in kendi genişlik tablosuyla ölçülür; tek bir hücrenin içindedir."""
    sayfa = olcum.sayfalar(_pdf(secim, tabaka.capacity, tabaka=tabaka, qr=qr))[0]
    hucreler = tabaka.cells()
    assert sayfa.yazilar, "PDF'te metin yok"
    tasan = [
        (y.metin, round(y.x0, 2), round(y.x1, 2))
        for y in sayfa.yazilar
        if len(_hucresi(y, hucreler)) != 1
    ]
    assert tasan == []
    # Kırpılan uzun ad ve yer numarası "…" ile biter; kısa okul adı da kırpılmıştır.
    if secim == "BARCODE":
        assert any(y.metin.endswith("…") and y.metin.startswith("Şu Çılgın") for y in sayfa.yazilar)
    if secim == "BLANK":
        assert not any("Çılgın" in y.metin or "ÖZDEM" in y.metin for y in sayfa.yazilar)


def test_pdfteki_metin_genisligi_programin_olcusuyle_ayni() -> None:
    """Python'daki DejaVu tablosu ile PDF'in `/W` tablosu aynı genişliği verir (çekirdek aralığı kapalı)."""
    from apps.kutuphane.labels import metrics

    sayfa = olcum.sayfalar(_pdf("SPINE", 3, uzun=False))[0]
    olculen = 0
    for yazi in sayfa.yazilar:
        if not yazi.metin.strip():
            continue
        boy_pt = yazi.boy_mm / metrics.MM_PER_PT
        tahmin = metrics.text_width_mm(yazi.metin, boy_pt, bold=yazi.kalin)
        # /W tablosu 1/1000 em'e yuvarlanır: karakter başına ≤ 0,0005 em.
        pay = len(yazi.metin) * 0.0005 * yazi.boy_mm + 0.005
        assert abs((yazi.x1 - yazi.x0) - tahmin) <= pay, yazi
        olculen += 1
    assert olculen >= 6


# ============================================================ Başlangıç hücresi
def test_baslangic_hucresi_pdfte_uygulanir() -> None:
    sayfalar = olcum.sayfalar(_pdf("BARCODE", 8, baslangic=60, uzun=False))
    assert len(sayfalar) == 2
    assert _dolu_hucreler(sayfalar[0], TABAKA_65) == [60, 61, 62, 63, 64, 65]
    assert _dolu_hucreler(sayfalar[1], TABAKA_65) == [1, 2]
    # İlk etiket 60. hücrededir.
    hucre = TABAKA_65.cell(59)
    metinler = [
        y.metin
        for y in olcum.yazilar_hucrede(
            sayfalar[0], hucre.left, hucre.top, hucre.right, hucre.bottom
        )
    ]
    assert "2026-000001" in metinler


# ============================================================ Kalibrasyon kayması
def test_kalibrasyon_kaymasi_pdf_konumlarina_yansir() -> None:
    """Hücre ve içeriği kaymanın kendisi kadar kayar.

    İstisna yazıcının basamadığı kenar payıdır (`PRINT_SAFE_MARGIN_MM`): kayma
    bir hücreyi sayfa kenarına 5 mm'den çok yaklaştırırsa (burada +1,5 mm ile 5.
    sütun) o hücrenin mürekkebi paya taşmaz, hücrenin içinde içeri kayar.
    """
    from apps.kutuphane.labels.layout import PAD_INSETS, ink_insets

    kayma = CalibrationOffset(1.5, -0.75)
    duz = olcum.sayfalar(_pdf("BARCODE", 5, uzun=False))[0]
    kaymali = olcum.sayfalar(_pdf("BARCODE", 5, uzun=False, kayma=kayma))[0]
    assert len(duz.yazilar) == len(kaymali.yazilar)
    kenar_hucresi = 0
    for hucre_duz, hucre_kaymali in zip(
        TABAKA_65.cells()[:5], TABAKA_65.cells(kayma)[:5], strict=True
    ):
        yazilar_duz = olcum.yazilar_hucrede(
            duz, hucre_duz.left, hucre_duz.top, hucre_duz.right, hucre_duz.bottom
        )
        yazilar_kay = olcum.yazilar_hucrede(
            kaymali,
            hucre_kaymali.left,
            hucre_kaymali.top,
            hucre_kaymali.right,
            hucre_kaymali.bottom,
        )
        assert [y.metin for y in yazilar_duz] == [y.metin for y in yazilar_kay]
        bar_duz = _barlar(duz, hucre_duz)[0]
        bar_kay = _barlar(kaymali, hucre_kaymali)[0]
        # Barkod dikeyde aynen kayar, sol kenarı yazıcı noktasına hizalıdır.
        assert bar_kay.y0 - bar_duz.y0 == pytest.approx(-0.75, abs=TOLERANS_MM)
        assert abs(bar_kay.x0 - round(bar_kay.x0 / X) * X) <= TOLERANS_MM
        for a, b in zip(yazilar_duz, yazilar_kay, strict=True):
            assert b.taban - a.taban == pytest.approx(-0.75, abs=TOLERANS_MM)
        if ink_insets(hucre_kaymali) == PAD_INSETS:
            # Metin koşuları kaymanın kendisi kadar; barkod en çok X farkla kayar.
            for a, b in zip(yazilar_duz, yazilar_kay, strict=True):
                assert b.x0 - a.x0 == pytest.approx(1.5, abs=TOLERANS_MM)
            assert abs((bar_kay.x0 - bar_duz.x0) - 1.5) <= X + TOLERANS_MM
        else:
            kenar_hucresi += 1
            for b in yazilar_kay:
                assert hucre_kaymali.left <= b.x0
                assert b.x1 <= 210 - PRINT_SAFE_MARGIN_MM + METIN_TOLERANS_MM
            assert _barlar(kaymali, hucre_kaymali)[-1].x1 <= 210 - PRINT_SAFE_MARGIN_MM + 1e-3
    assert kenar_hucresi == 1  # yalnız 5. sütun sayfa kenarına 5 mm'den çok yaklaştı
    # Kaymasız basımda barkod içermeyen kaymalı hücre kalmaz.
    assert _dolu_hucreler(kaymali, TABAKA_65, kayma) == [1, 2, 3, 4, 5]


# ============================================================ Sırt ve barkod aynı düzende
def test_sirt_ve_barkod_ayni_sira_ve_hucre_duzeninde() -> None:
    """İkisi birden: n. sırt tabakasının k. hücresi ile n. barkod tabakasının k. hücresi aynı kitabındır."""
    adet = 70
    kalemler = [
        LabelItem(f"2026{s:06d}", f"Eser {s}", f"8{s:02d}.1 Y{s:02d}") for s in range(1, adet + 1)
    ]
    sonuc = render_labels(
        kalemler, build_parts("BOTH", template=TABAKA_65), start_cell=10, school_short_name=""
    )
    sayfalar = olcum.sayfalar(sonuc.pdf)
    assert sonuc.sheets_per_part == 2 and len(sayfalar) == 4
    sirt_sayfalari, barkod_sayfalari = sayfalar[:2], sayfalar[2:]
    for yer in sonuc.placements:
        kalem = kalemler[yer.item_index]
        hucre = TABAKA_65.cell(yer.cell_index)
        kutu = (hucre.left, hucre.top, hucre.right, hucre.bottom)
        sirt = [y.metin for y in olcum.yazilar_hucrede(sirt_sayfalari[yer.sheet], *kutu)]
        barkod = [y.metin for y in olcum.yazilar_hucrede(barkod_sayfalari[yer.sheet], *kutu)]
        assert sirt == kalem.call_number.split(), (yer, sirt)
        assert kalem.printed_number in barkod, (yer, barkod)
        assert _barlar(barkod_sayfalari[yer.sheet], hucre), yer
        assert not _barlar(sirt_sayfalari[yer.sheet], hucre), "sırt etiketinde barkod olmaz"


# ============================================================ Boş barkod etiketi
def test_bos_barkod_etiketi_yalniz_okul_barkod_ve_numara() -> None:
    sayfa = olcum.sayfalar(_pdf("BLANK", 3, okul="Örnek AL"))[0]
    for sira, hucre in enumerate(TABAKA_65.cells()[:3], start=1):
        metinler = [
            y.metin
            for y in olcum.yazilar_hucrede(sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom)
        ]
        assert metinler == ["Örnek AL", f"2026-{sira:06d}"]
        assert len(_barlar(sayfa, hucre)) == 25


# ============================================================ Kalibrasyon sayfası
def test_kalibrasyon_sayfasi_hucre_cercevelerini_kaymayla_basar() -> None:
    kayma = CalibrationOffset(0.5, -0.25)
    pdf = render_calibration_sheet(
        TABAKA_65, kayma, template_name="Deneme 65'li", printer_name="Deneme Yazıcı"
    )
    sayfalar = olcum.sayfalar(pdf)
    assert len(sayfalar) == 1
    sayfa = sayfalar[0]
    cerceveler = [
        c
        for c in sayfa.cizgiler
        if abs((c.x1 - c.x0) - 38.1) < 0.3 and abs((c.y1 - c.y0) - 21.2) < 0.3
    ]
    assert len(cerceveler) == 65
    # Çerçevenin yolu hücre kenarındadır (çizgi kalınlığı iki yana taşar); konumlar
    # kaymayı taşır. Her hücre için tam bir çerçeve bulunur.
    for hucre in TABAKA_65.cells(kayma):
        eslesen = [
            c
            for c in cerceveler
            if abs(c.x0 - hucre.left) <= TOLERANS_MM and abs(c.y0 - hucre.top) <= TOLERANS_MM
        ]
        assert len(eslesen) == 1, hucre
    metin = " ".join(sayfa.metinler())
    for parca in (
        "Kalibrasyon sayfası",
        "Deneme 65'li",
        "Deneme Yazıcı",
        "+0,50",
        "−0,25",
        "100 mm",
    ):
        assert parca in metin, parca


# ============================================================ Yazıcının basamadığı kenar payı
#: Kenarsız 40'lı tabaka (4 × 52,5 = 210, 10 × 29,7 = 297).
TABAKA_40 = SheetGeometry(0.0, 0.0, 52.5, 29.7, 10, 4)
PAY = PRINT_SAFE_MARGIN_MM
#: DejaVu Sans yükselen ve inen (em) — yazı mürekkebinin dikey sınırı.
YUKSELEN, INEN = 0.93, 0.24


def _murekkep_basilabilir_alanda(sayfa: olcum.SayfaOlcumu) -> None:
    """Bar, QR modülü ve yazı sayfa kenarından en az PAY mm içeride mi?"""
    for d in sayfa.siyah_dolgular():
        assert d.x0 >= PAY - 1e-3 and d.x1 <= 210 - PAY + 1e-3, d
        assert d.y0 >= PAY - 1e-3 and d.y1 <= 297 - PAY + 1e-3, d
    for y in sayfa.yazilar:
        if not y.metin.strip():
            continue
        assert y.x0 >= PAY - METIN_TOLERANS_MM and y.x1 <= 210 - PAY + METIN_TOLERANS_MM, y
        assert y.taban - YUKSELEN * y.boy_mm >= PAY - METIN_TOLERANS_MM, y
        assert y.taban + INEN * y.boy_mm <= 297 - PAY + METIN_TOLERANS_MM, y


@pytest.mark.parametrize(
    ("tabaka", "secim", "qr"),
    [
        (TABAKA_40, "BARCODE", True),
        (TABAKA_40, "BARCODE", False),
        (TABAKA_40, "SPINE", False),
        (TABAKA_40, "BLANK", True),
        (TABAKA_44, "BARCODE", True),
        (TABAKA_65, "BARCODE", False),
        (TABAKA_65, "SPINE", False),
    ],
)
def test_murekkep_yazicinin_basabildigi_alanda_kalir(
    tabaka: SheetGeometry, secim: str, qr: bool
) -> None:
    """Denetim bulgusu (24.09.2026): kenarsız 40'lı tabakada 4. sütunun QR modülleri
    ve (5 mm paylı yazıcıda) 1. sütunun START barları basılamayan paya düşüyordu.

    EN UZUN veriyle, tabakanın bütün hücreleri dolu; ölçü PDF'in kendisinden.
    """
    pdf = _pdf(secim, tabaka.capacity, tabaka=tabaka, qr=qr)
    sayfalar = olcum.sayfalar(pdf)
    assert len(sayfalar) == 1
    _murekkep_basilabilir_alanda(sayfalar[0])
    if secim != "SPINE":
        # Her hücrede barkod hâlâ tam: 25 bar, sessiz bölgesi etiketin içinde.
        for hucre in tabaka.cells():
            barlar = _barlar(sayfalar[0], hucre)
            assert len(barlar) == 25, hucre
            assert barlar[0].x0 - 10 * X >= hucre.left - 1e-6
            assert barlar[-1].x1 + 10 * X <= hucre.right + 1e-6


def test_kenara_yakin_olmayan_hucrenin_duzeni_degismez() -> None:
    """Güvenli pay yalnız sayfa kenarındaki hücreyi etkiler: 65'li tabakanın iç
    hücresi ile 40'lı tabakanın iç hücresinde düzen olağan iç boşlukladır."""
    from apps.kutuphane.labels.content import LabelContent
    from apps.kutuphane.labels.layout import PAD_INSETS, ink_insets, label_layout

    for tabaka, sira in ((TABAKA_65, 12), (TABAKA_40, 5)):
        hucre = tabaka.cell(sira)
        assert ink_insets(hucre) == PAD_INSETS
    # 40'lı tabakanın köşe hücresinde içerik kenardan içeri kayar.
    kose = TABAKA_40.cell(0)
    duzen = label_layout(
        LabelItem("2026000123", "Deneme", "813.54 ALİ"),
        kose,
        content=LabelContent.BARCODE,
        school="Örnek AL",
        include_qr=True,
    )
    assert min(k.left for k in duzen.texts) >= PAY - kose.left - 1e-9
    assert min(k.top for k in duzen.texts) >= PAY - kose.top - 1e-9


@pytest.mark.parametrize("tabaka", [TABAKA_65, TABAKA_44, TABAKA_40])
def test_kalibrasyon_cetvelleri_basilabilir_alanda(tabaka: SheetGeometry) -> None:
    """Denetim bulgusu (24.09.2026): 40'lı tabakada hiçbir cetvel çentiği, 65'li
    tabakada X cetvellerinin yarısı yazıcının basamadığı paya düşüyordu.

    Dört köşe hücresinin her birinde bir dikey ve bir yatay cetvel (9'ar çentik)
    vardır; çentiklerin hepsi basılabilir alandadır ve her cetvelin 0 çentiği bir
    hücre kenarının (kesim çizgisinin) üstündedir.
    """
    kayma = CalibrationOffset(0.5, -0.25)
    sayfa = olcum.sayfalar(render_calibration_sheet(tabaka, kayma, template_name="Deneme"))[0]
    centikler = [
        c
        for c in sayfa.cizgiler
        if max(c.x1 - c.x0, c.y1 - c.y0) <= 1.5 and min(c.x1 - c.x0, c.y1 - c.y0) < 1e-3
    ]
    dikey = [c for c in centikler if (c.y1 - c.y0) > (c.x1 - c.x0)]  # X cetveli
    yatay = [c for c in centikler if (c.x1 - c.x0) > (c.y1 - c.y0)]  # Y cetveli
    assert len(dikey) == len(yatay) == 4 * 9
    for c in centikler:
        assert PAY - 1e-3 <= c.x0 and c.x1 <= 210 - PAY + 1e-3, c
        assert PAY - 1e-3 <= c.y0 and c.y1 <= 297 - PAY + 1e-3, c
    hucreler = tabaka.cells(kayma)
    x_kenarlari = [k for h in hucreler for k in (h.left, h.right)]
    y_kenarlari = [k for h in hucreler for k in (h.top, h.bottom)]

    def _kenarda(deger: float, kenarlar: list[float]) -> bool:
        return any(abs(deger - k) <= TOLERANS_MM for k in kenarlar)

    x_sifirlar = {
        round(c.x0, 2) for c in dikey if (c.y1 - c.y0) > 1.0 and _kenarda(c.x0, x_kenarlari)
    }
    y_sifirlar = {
        round(c.y0, 2) for c in yatay if (c.x1 - c.x0) > 1.0 and _kenarda(c.y0, y_kenarlari)
    }
    # Sol ve sağ (üst ve alt) köşelerin cetvelleri ayrı kenarlardadır.
    assert len(x_sifirlar) >= 2 and len(y_sifirlar) >= 2
    # Cetvel yazıları ve hücre numaraları da basılabilir alanda.
    for y in sayfa.yazilar:
        if y.metin.strip():
            assert y.x0 >= PAY - METIN_TOLERANS_MM and y.x1 <= 210 - PAY + METIN_TOLERANS_MM, y
            assert y.taban - YUKSELEN * y.boy_mm >= PAY - METIN_TOLERANS_MM, y
