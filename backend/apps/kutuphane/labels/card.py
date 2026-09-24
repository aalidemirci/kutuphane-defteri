"""Üye kartı (E2) — etiket motorunun kart türü (tasarım §7.1-7.2, §10 E2; D8).

**Kartta ne var** (§7.2, KM-24): okulun adı · "ÜYE KARTI" · üyenin adı · üye
türü (öğrenci / öğretmen / diğer personel) · Code128 kart no ve okunur numara ·
konum kalıbı (sözlük "Kart"). **Sınıf YAZILMAZ**: sınıf her yıl değişir ve
kartta gereksiz veridir. Şube tabakasında sınıf yalnız SIRALAMA içindir
(`services.member_cards.memberships_for_print`). OYS'de kartta okul adı boş
kalıyordu ve kartlar tek tek basılıyordu (D8): burada okul adı
`SchoolConfig.school_name`'den gelir, kartlar tabakaya (A4'e 10) basılır.

**Motorla ortak olan** (F4): tabaka ızgarası ve başlangıç hücresi
(`geometry.plan_placements`), yazıcı kalibrasyonu (`LabelCalibration`, şablon +
yazıcı çifti; kart şablonunun kalibrasyonu da aynı uçlardan yazılır), DejaVu
genişlik ölçümü (`metrics`) ve mutlak konumlu kutu şablonu
(`documents/etiket_tabakasi.html`). PDF yalnız `shared.pdf.html_to_pdf`
kapısından üretilir. Motor veritabanına YAZMAZ: PDF üretmek "basıldı" demek
değildir (D10); "Basıldı olarak işaretle" `services.member_cards`'tadır.

**Kart şablonu** kod içi tohumdur (`ensure_card_template`, göç yok): 85 × 54 mm,
2 sütun × 5 satır, A4'te simetrik (sol kenar (210 − 2 × 85) / 2 = 20 mm, üst
kenar (297 − 5 × 54) / 2 = 13,5 mm, aralık yok). Düz kâğıda ya da kartona basılıp
kesilmek içindir: her kartın çevresine ince bir **kesim çizgisi** çizilir
(önceden kesilmiş kart tabakasında kapatılabilir). Kart şablonu etiket
şablonları ekranında görünmez ve oradan düzenlenmez (F4 `labels/services.py`);
kaydırma yazıcı kalibrasyonuyla düzeltilir.

**Barkod.** Kart no 8 hanedir: Code128-C 79 modül, sessiz bölgelerle 99 (§7.2).
Kartta yer bol olduğu için modül etiketlerdeki 0,254 mm (3 nokta) yerine
**4/300 inç ≈ 0,339 mm**'dir: 300 dpi'de 4, 600 dpi'de 8 yazıcı noktası, yani
yine nokta ızgarasına hizalı; barkod sessiz bölgeleriyle 33,5 mm eder ve masadaki
okuyucu kartı daha uzaktan ve eğik tutulunca da okur. Barkodun sayfadaki sol
kenarı kalibrasyon kaymasından SONRA modülün katına çekilir (`snap_to_module`).

**Düzen** Python'da hesaplanır (etiket düzeninin kuralı): her satır tek satırlık
kutudur; okul adı ve üye adı en çok iki satıra bölünür, en küçük boyda da
sığmazsa son satır "…" ile kısalır. Üst blok (okul, başlık, ad, tür) yukarıdan,
alt blok (barkod, numara, konum kalıbı) aşağıdan dizilir; ikisi çakışırsa
`LabelError` (85 × 54 mm'de en uzun veriyle de çakışmadığı testle sabittir).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.template.loader import render_to_string

from apps.kutuphane import card_numbers
from apps.kutuphane.labels.geometry import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    PRINT_SAFE_MARGIN_MM,
    CalibrationOffset,
    CellBox,
    LabelError,
    Placement,
    SheetGeometry,
    mm_text,
    plan_placements,
    sheet_count,
    snap_to_module,
)
from apps.kutuphane.labels.layout import FIT_SAFETY_MM, GraphicBox, LabelLayout, TextBox
from apps.kutuphane.labels.layout import line_height as _line_height
from apps.kutuphane.labels.metrics import clean_text, fit_text, fits
from shared import barcode128
from shared.pdf import html_to_pdf
from shared.text import tr_upper

if TYPE_CHECKING:
    from apps.kutuphane.models import LabelCalibration, LabelSheetTemplate

TEMPLATE_NAME = "documents/etiket_tabakasi.html"
#: Belge adı (sözlük §2: E2 "Üye kartı") — PDF başlığı ve indirme adı.
DOCUMENT_NAME = "Üye Kartı"
#: Kart şablonunun (tohum) adı — ölçü milimetreyle, kâğıt boyunun kısa adı YOK.
CARD_TEMPLATE_NAME = "Üye kartı — 85 × 54 mm, 10'lu"
#: Kartın ölçüsü (mm; §7.2) ve tohum tabakanın ızgarası.
CARD_WIDTH_MM = 85.0
CARD_HEIGHT_MM = 54.0
CARD_ROWS = 5
CARD_COLS = 2
#: Tek belgede en çok kart (20 tam tabaka). Bir okulun bütün üyeleri tek istekte
#: basılmaz; şube şube ya da sayfa sayfa basılır.
MAX_CARDS_PER_DOCUMENT = 200
#: Kart barkodunun modül genişliği: 4/300 inç (modül belgesi).
CARD_MODULE_MM = 25.4 * 4 / 300
#: Barkodun çubuk yüksekliği (mm).
CARD_BAR_HEIGHT_MM = 9.0

#: İç boşluklar (mm): kesim çizgisinden içeri.
PAD_X = 3.5
PAD_Y = 3.0
#: Satır blokları arasındaki boşluklar (mm).
GAP = 0.8
RULE_GAP = 1.0
RULE_HEIGHT = 0.3
TYPE_GAP = 0.5
#: Üst ve alt blok arasında en az bırakılacak boşluk (mm).
MIN_BLOCK_GAP = 1.0
#: Yazı boyları (pt), büyükten küçüğe.
SCHOOL_SIZES = (7.5, 7.0, 6.5, 6.0)
TITLE_SIZE = 9.0
NAME_SIZES = (11.0, 10.0, 9.0, 8.0)
TYPE_SIZE = 8.0
NUMBER_SIZE = 9.0
NOTE_SIZES = (5.0, 4.6)
#: Kartın başlığı — doğrudan büyük harfle (evrakta `text-transform` yok).
CARD_TITLE = "ÜYE KARTI"
#: Konum kalıbı (sözlük "Kart"; tasarım §3, §10 E2): kart Md. 20'deki kullanıcı
#: kartının yerel karşılığıdır, Bakanlık sistemindeki kaydın yerine geçmez. YALNIZ
#: öğrenci ve öğretmen kartına basılır: Md. 20/1 kullanıcı kartını "öğretmen ve
#: öğrenci"ye öngörür.
POSITION_NOTE = (
    "Okul Kütüphaneleri Yönetmeliği Md. 20'de öngörülen kullanıcı kartının okulca "
    "düzenlenen yerel karşılığıdır; Bakanlık otomasyon sistemindeki kaydın yerine geçmez."
)
#: Diğer personelin kartındaki not — madde atfı YOK. Diğer personele ödünç
#: Yönetmelikte ayrıca düzenlenmemiştir; programın kuralıdır ve müdürlük kararıyla
#: açılır (tasarım §9-1, sözlük "Kart").
STAFF_POSITION_NOTE = (
    "Okulca düzenlenen yerel üye kartıdır; diğer personele ödünç okul müdürlüğü "
    "kararıyla verilir."
)
#: Kesim çizgisinin kalınlığı (mm) ve rengi (açık gri: kesilince kaybolur).
CUT_STROKE_MM = 0.1
CUT_COLOR = "#9a9a9a"


# ---------------------------------------------------------------------------
# Metin sarma
# ---------------------------------------------------------------------------
def _greedy_lines(words: Sequence[str], width: float, size: float, *, bold: bool) -> list[str]:
    satirlar: list[str] = []
    mevcut = ""
    for kelime in words:
        aday = f"{mevcut} {kelime}" if mevcut else kelime
        if fits(aday, width, size, bold=bold):
            mevcut = aday
            continue
        if mevcut:
            satirlar.append(mevcut)
        mevcut = kelime
    if mevcut:
        satirlar.append(mevcut)
    return satirlar


def wrap_text(
    value: object,
    width_mm: float,
    sizes_pt: tuple[float, ...],
    *,
    bold: bool = False,
    max_lines: int = 2,
) -> tuple[list[str], float]:
    """Metni en büyük uygun boyla en çok `max_lines` satıra böler: (satırlar, boy).

    Sözcük sınırından bölünür. Hiçbir boyda sığmazsa en küçük boy kullanılır:
    satıra sığmayan tek sözcük ve son satır "…" ile kısalır (`metrics.fit_text`,
    Türkçe güvenli). Dönen her satır `width_mm`'yi AŞMAZ. Boş metin → ([], ilk boy).
    """
    metin = clean_text(value)
    if not metin:
        return [], sizes_pt[0]
    kelimeler = metin.split(" ")
    for boy in sizes_pt:
        satirlar = _greedy_lines(kelimeler, width_mm, boy, bold=bold)
        if len(satirlar) <= max_lines and all(fits(s, width_mm, boy, bold=bold) for s in satirlar):
            return satirlar, boy
    boy = sizes_pt[-1]
    satirlar = _greedy_lines(kelimeler, width_mm, boy, bold=bold)
    basta = [fit_text(s, width_mm, boy, bold=bold) for s in satirlar[: max_lines - 1]]
    kalan = " ".join(satirlar[max_lines - 1 :])
    return [*basta, fit_text(kalan, width_mm, boy, bold=bold)], boy


def line_height(size_pt: float) -> float:
    """Tek satırlık kutunun yüksekliği (mm) — etiket düzeniyle aynı oran."""
    return _line_height(size_pt)


# ---------------------------------------------------------------------------
# Kart kalemi
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CardItem:
    """Basılacak tek kartın verisi: kart no, ad, üye türü (görünen metin). Sınıf YOK.

    `note`: kartın altındaki not — öğrenci ve öğretmende konum kalıbı
    (`POSITION_NOTE`), diğer personelde atıfsız not (`STAFF_POSITION_NOTE`); seçimi
    `services.member_cards.card_items` yapar.
    """

    card_no: str
    full_name: str
    member_type: str
    note: str = POSITION_NOTE


def member_type_text(label: str) -> str:
    """'öğrenci' → 'Öğrenci' (yalnız ilk harf büyür; Türkçe güvenli)."""
    metin = clean_text(label)
    return f"{tr_upper(metin[:1])}{metin[1:]}" if metin else ""


def validate_card_items(items: Sequence[CardItem]) -> list[CardItem]:
    """Boş, çok uzun, sağlaması tutmayan ya da yinelenen kart no'lu listeyi reddeder.

    Hata iletisi kart numarasını BASMAZ (kart no şifreli alandır, ileti günlüğe
    düşebilir — `shared/barcode128.py` ile aynı ilke).
    """
    liste = list(items)
    if not liste:
        raise LabelError("Basılacak kart yok.", field="membership_ids")
    if len(liste) > MAX_CARDS_PER_DOCUMENT:
        raise LabelError(
            f"Tek seferde en çok {MAX_CARDS_PER_DOCUMENT} kart basılabilir; listeyi şube şube "
            "ya da parça parça basın.",
            field="membership_ids",
        )
    gorulen: set[str] = set()
    for kalem in liste:
        if not card_numbers.is_valid_card_no(kalem.card_no):
            raise LabelError("Kart numarası geçersiz; kart basılamaz.", field="membership_ids")
        if kalem.card_no in gorulen:
            raise LabelError("Aynı kart listede iki kez var.", field="membership_ids")
        gorulen.add(kalem.card_no)
    return liste


# ---------------------------------------------------------------------------
# Düzen
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Insets:
    left: float
    top: float
    right: float
    bottom: float


def _insets(cell: CellBox) -> _Insets:
    """İç boşluk ya da yazıcının basamadığı kenar payı, hangisi büyükse (etiketle aynı kural)."""
    pay = PRINT_SAFE_MARGIN_MM
    return _Insets(
        left=max(PAD_X, pay - cell.left),
        top=max(PAD_Y, pay - cell.top),
        right=max(PAD_X, cell.right - (A4_WIDTH_MM - pay)),
        bottom=max(PAD_Y, cell.bottom - (A4_HEIGHT_MM - pay)),
    )


def _rect_svg(width_mm: float, height_mm: float, *, stroke: float = 0.0) -> str:
    """Dolu (çizgi) ya da çerçeve (kesim çizgisi) dikdörtgeni — mm ölçülü bağımsız SVG."""
    gen, yuk = f"{width_mm:.3f}", f"{height_mm:.3f}"
    if stroke > 0:
        yari = stroke / 2
        govde = (
            f'<rect x="{yari:.3f}" y="{yari:.3f}" width="{width_mm - stroke:.3f}" '
            f'height="{height_mm - stroke:.3f}" fill="none" stroke="{CUT_COLOR}" '
            f'stroke-width="{stroke:.3f}"/>'
        )
    else:
        govde = f'<rect width="{gen}" height="{yuk}" fill="#000"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{gen}mm" height="{yuk}mm" '
        f'viewBox="0 0 {gen} {yuk}">{govde}</svg>'
    )


def card_barcode_width() -> float:
    """8 haneli kart no'nun sessiz bölgeli barkod genişliği: 99 × 4/300 inç ≈ 33,53 mm."""
    return barcode128.module_count("90000000") * CARD_MODULE_MM


def _lines(
    rol: str,
    satirlar: list[str],
    boy: float,
    *,
    left: float,
    top: float,
    width: float,
    bold: bool,
) -> tuple[list[TextBox], float]:
    """Satır kutuları + bloğun yüksekliği. Kutunun yüksekliği KULLANILAN boydan gelir."""
    yuk = line_height(boy)
    kutular = [
        TextBox(rol, satir, left, top + sira * yuk, width, yuk, boy, bold=bold)
        for sira, satir in enumerate(satirlar)
    ]
    return kutular, yuk * len(satirlar)


def card_layout(item: CardItem, cell: CellBox, *, school: str, cut_guides: bool) -> LabelLayout:
    """Tek kartın iç düzeni (mm, hücrenin sol üst köşesine göre)."""
    ins = _insets(cell)
    sol = ins.left
    gen = cell.width - ins.left - ins.right
    olcu = gen - FIT_SAFETY_MM
    blok = card_barcode_width()
    if olcu <= 0 or blok > gen:
        raise LabelError("Kart şablonu üye kartına küçük.", field="template")

    metinler: list[TextBox] = []
    grafikler: list[GraphicBox] = []
    if cut_guides:
        grafikler.append(
            GraphicBox(
                "cut",
                _rect_svg(cell.width, cell.height, stroke=CUT_STROKE_MM),
                0.0,
                0.0,
                cell.width,
                cell.height,
            )
        )

    # Üst blok: okul · başlık + çizgi · ad · üye türü
    y = ins.top
    okul_satirlari, okul_boy = wrap_text(school, olcu, SCHOOL_SIZES, bold=True, max_lines=2)
    kutular, yuk = _lines("school", okul_satirlari, okul_boy, left=sol, top=y, width=gen, bold=True)
    metinler += kutular
    y += yuk + (GAP if kutular else 0.0)

    baslik_yuk = line_height(TITLE_SIZE)
    metinler.append(TextBox("title", CARD_TITLE, sol, y, gen, baslik_yuk, TITLE_SIZE, bold=True))
    y += baslik_yuk
    grafikler.append(
        GraphicBox("rule", _rect_svg(gen, RULE_HEIGHT), sol, y + RULE_GAP / 2, gen, RULE_HEIGHT)
    )
    y += RULE_GAP + RULE_HEIGHT + GAP

    ad_satirlari, ad_boy = wrap_text(item.full_name, olcu, NAME_SIZES, bold=True, max_lines=2)
    kutular, yuk = _lines("name", ad_satirlari, ad_boy, left=sol, top=y, width=gen, bold=True)
    metinler += kutular
    y += yuk + TYPE_GAP

    tur = fit_text(item.member_type, olcu, TYPE_SIZE)
    if tur:
        tur_yuk = line_height(TYPE_SIZE)
        metinler.append(TextBox("type", tur, sol, y, gen, tur_yuk, TYPE_SIZE))
        y += tur_yuk
    ust_son = y

    # Alt blok (aşağıdan yukarı): konum kalıbı · okunur numara · barkod
    alt = cell.height - ins.bottom
    not_satirlari, not_boy = wrap_text(item.note, olcu, NOTE_SIZES, max_lines=3)
    not_yuk = line_height(not_boy) * len(not_satirlari)
    kutular, _ = _lines(
        "note", not_satirlari, not_boy, left=sol, top=alt - not_yuk, width=gen, bold=False
    )
    metinler += kutular
    alt -= not_yuk + GAP

    numara_yuk = line_height(NUMBER_SIZE)
    alt -= numara_yuk
    metinler.append(
        TextBox("number", item.card_no, sol, alt, gen, numara_yuk, NUMBER_SIZE, bold=True)
    )
    alt -= CARD_BAR_HEIGHT_MM
    ideal = sol + (gen - blok) / 2
    bar_sol = snap_to_module(cell.left + ideal, CARD_MODULE_MM) - cell.left
    grafikler.append(
        GraphicBox(
            "barcode",
            barcode128.svg(item.card_no, module_mm=CARD_MODULE_MM, height_mm=CARD_BAR_HEIGHT_MM),
            bar_sol,
            alt,
            blok,
            CARD_BAR_HEIGHT_MM,
        )
    )
    if ust_son + MIN_BLOCK_GAP > alt:
        raise LabelError(
            "Kart şablonunun yüksekliği kartın satırlarına yetmiyor.", field="template"
        )
    return LabelLayout(texts=tuple(metinler), graphics=tuple(grafikler))


# ---------------------------------------------------------------------------
# Şablon (kod içi tohum) ve doğrulama
# ---------------------------------------------------------------------------
CARD_TEMPLATE_SEED: dict[str, Any] = {
    "name": CARD_TEMPLATE_NAME,
    "page_margin_top": Decimal("13.50"),
    "page_margin_left": Decimal("20.00"),
    "label_width": Decimal("85.00"),
    "label_height": Decimal("54.00"),
    "rows": CARD_ROWS,
    "cols": CARD_COLS,
    "gutter_x": Decimal("0"),
    "gutter_y": Decimal("0"),
    "is_default": True,
}


def ensure_card_template() -> LabelSheetTemplate:
    """Canlı kart şablonunu döndürür; yoksa tohumdan yazar (göç GEREKMEZ).

    Varsayılan kart şablonu önce gelir. İşlem `transaction_mode=IMMEDIATE`
    altında yazma kilidiyle başlar: aynı anda gelen iki istekten ikincisi
    birincinin yazdığını görür (çift tohum olmaz).
    """
    from apps.kutuphane.models import LabelKind, LabelSheetTemplate

    with transaction.atomic():
        mevcut: LabelSheetTemplate | None = (
            LabelSheetTemplate.objects.filter(kind=LabelKind.CARD)
            .order_by("-is_default", "pk")
            .first()
        )
        if mevcut is not None:
            return mevcut
        yeni: LabelSheetTemplate = LabelSheetTemplate.objects.create(
            kind=LabelKind.CARD, **CARD_TEMPLATE_SEED
        )
        return yeni


def card_geometry(
    template: LabelSheetTemplate | SheetGeometry, calibration: LabelCalibration | None
) -> SheetGeometry:
    """Kart şablonunu ve kalibrasyonunu doğrular; ızgarayı döndürür."""
    from apps.kutuphane.models import LabelKind, LabelSheetTemplate

    if isinstance(template, LabelSheetTemplate):
        if template.deleted_at is not None:
            raise LabelError("Kart şablonu silinmiş.")
        if template.kind != LabelKind.CARD:
            raise LabelError("Üye kartı yalnız kart şablonuna basılır.")
        geometri = SheetGeometry.from_template(template)
    else:
        geometri = template
    if calibration is not None:
        if calibration.deleted_at is not None:
            raise LabelError("Kalibrasyon kaydı silinmiş.", field="calibration")
        if isinstance(template, LabelSheetTemplate) and calibration.template_id != template.pk:
            raise LabelError("Seçilen kalibrasyon kart şablonuna ait değil.", field="calibration")
    geometri.validate()
    return geometri


def _school_name(value: str | None) -> str:
    if value is not None:
        return value
    from apps.okul.models import SchoolConfig

    ayar = SchoolConfig.load()
    return " ".join((ayar.school_name or ayar.kisa_ad or "").split())


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _text_context(box: TextBox) -> dict[str, str]:
    css = "c b" if box.bold else "c"
    return {
        "css": css,
        "text": box.text,
        "left": mm_text(box.left),
        "top": mm_text(box.top),
        "width": mm_text(box.width),
        "height": mm_text(box.height),
        "size": f"{box.size_pt:.2f}",
    }


def _cell_context(cell: CellBox, layout: LabelLayout) -> dict[str, Any]:
    return {
        "left": mm_text(cell.left),
        "top": mm_text(cell.top),
        "width": mm_text(cell.width),
        "height": mm_text(cell.height),
        "texts": [_text_context(kutu) for kutu in layout.texts],
        "graphics": [
            {
                "svg": g.svg,
                "left": mm_text(g.left),
                "top": mm_text(g.top),
                "width": mm_text(g.width),
                "height": mm_text(g.height),
            }
            for g in layout.graphics
        ],
    }


@dataclass(frozen=True)
class RenderedCards:
    pdf: bytes
    placements: tuple[Placement, ...]
    sheet_count: int


def build_card_context(
    items: Sequence[CardItem],
    *,
    template: LabelSheetTemplate | SheetGeometry,
    calibration: LabelCalibration | CalibrationOffset | None = None,
    start_cell: int = 1,
    school_name: str | None = None,
    cut_guides: bool = True,
) -> tuple[dict[str, Any], tuple[Placement, ...], int]:
    """Şablon bağlamı + yerleşim planı + tabaka sayısı (PDF'siz; test edilebilir)."""
    kalemler = validate_card_items(items)
    if isinstance(calibration, CalibrationOffset):
        geometri = card_geometry(template, None)
        kayma = calibration
    else:
        geometri = card_geometry(template, calibration)
        kayma = CalibrationOffset.from_calibration(calibration)
    kayma.validate()
    plan = plan_placements(len(kalemler), capacity=geometri.capacity, start_cell=start_cell)
    tabaka_sayisi = sheet_count(len(kalemler), capacity=geometri.capacity, start_cell=start_cell)
    okul = _school_name(school_name)
    hucreler: list[list[dict[str, Any]]] = [[] for _ in range(tabaka_sayisi)]
    for yer in plan:
        hucre = geometri.cell(yer.cell_index, kayma)
        duzen = card_layout(kalemler[yer.item_index], hucre, school=okul, cut_guides=cut_guides)
        hucreler[yer.sheet].append(_cell_context(hucre, duzen))
    baglam = {
        "document_title": DOCUMENT_NAME,
        "sheets": [
            {"content": "CARD", "number": sira + 1, "cells": tabaka}
            for sira, tabaka in enumerate(hucreler)
        ],
    }
    return baglam, plan, tabaka_sayisi


def render_member_cards(
    items: Sequence[CardItem],
    *,
    template: LabelSheetTemplate | SheetGeometry,
    calibration: LabelCalibration | CalibrationOffset | None = None,
    start_cell: int = 1,
    school_name: str | None = None,
    cut_guides: bool = True,
) -> RenderedCards:
    """Üye kartı PDF'i. Ret durumunda `LabelError` (uçta 400). Veritabanına YAZMAZ."""
    baglam, plan, tabaka_sayisi = build_card_context(
        items,
        template=template,
        calibration=calibration,
        start_cell=start_cell,
        school_name=school_name,
        cut_guides=cut_guides,
    )
    pdf = html_to_pdf(render_to_string(TEMPLATE_NAME, baglam))
    return RenderedCards(pdf=pdf, placements=plan, sheet_count=tabaka_sayisi)
