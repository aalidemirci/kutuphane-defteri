"""Kalibrasyon sayfası (E1) — şablonun hücre çerçeveleri, merkez artıları, mm cetvelleri.

Kullanım (kılavuz F4 bölümü ayrıntılı anlatır):

1. Sayfa, seçilen şablon ve yazıcı için **o anki kalibrasyon kaymasıyla**
   basılır (ilk seferde kayma sıfırdır). Gerçek boyutta (%100) basılmalıdır;
   ortadaki 100 mm'lik çizgi bunu denetletir.
2. Çıktı etiket tabakasının üstüne konup ışığa tutulur (ya da doğrudan bir
   tabakaya basılır). Dört köşe etiketinde, çerçevenin bir dikey ve bir yatay
   kenarını dik kesen milimetre cetvelleri vardır: 0 çizgisi basılı çerçevedir;
   etiketin GERÇEK kenarının (kesim çizgisinin) düştüğü değer okunur.
3. Okunan değer mevcut kaymaya eklenir: gerçek kenar +1'de ise çıktı 1 mm
   solda kalmıştır ve X kayması 1 mm artırılır (pozitif X sağa, pozitif Y aşağı
   kaydırır — `LabelCalibration`). Sayfa yeniden basılıp doğrulanır.

**Cetvel hangi kenarda** (`measured_edges`). Cetvel önce tabakanın dışına bakan
kenara konur: iç kenar komşu etiketle ortaktır. Ama yazıcı sayfa kenarından
birkaç milimetreyi basamaz (`geometry.PRINT_SAFE_MARGIN_MM`); dış kenarın
cetveli bu paya düşüyorsa (kenarsız 40'lı tabaka, kenar boşluğu dar 65'li ve
44'lü tabaka) cetvel aynı etiketin İÇ kenarına, komşu etiketle arasındaki kesime
taşınır. Okuma kuralı ve işaret değişmez: sağ ve alt taraf artıdır. Etiketler
arasında boşluk olan tabakada iç kenarın cetvelinde komşunun kesimi de görünür;
cetvelin 0 çizgisindeki çerçeveye ait kesim okunur (kılavuz).

Dört köşeyi ayrı ayrı ölçmek, yazıcının kâğıdı ölçekleyip ölçeklemediğini de
gösterir: kayma dört köşede aynı değilse sorun kalibrasyon değil ölçektir.

Sayfa tek SVG'dir (kullanıcı birimi mm, `viewBox` A4): çizgiler yazıcıya
ölçeklemesiz gider. Açıklama kutusu sayfanın ortasındadır; kenarsız
tabakalarda (40'lı) kenar boşluğu olmadığı için bütün şablonlarda aynı yerdedir.
Ölçüm köşe etiketlerinde yapıldığı için ortadaki hücrelerin örtülmesi ölçümü
etkilemez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.template.loader import render_to_string

from apps.kutuphane.labels.geometry import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    PRINT_SAFE_MARGIN_MM,
    CalibrationOffset,
    CellBox,
    LabelError,
    SheetGeometry,
    mm_text,
)
from apps.kutuphane.labels.metrics import clean_text
from shared.pdf import html_to_pdf

if TYPE_CHECKING:
    from apps.kutuphane.models import LabelCalibration, LabelSheetTemplate

TEMPLATE_NAME = "documents/etiket_kalibrasyon.html"
#: Belge adı (sözlük §2: E1).
DOCUMENT_NAME = "Kalibrasyon Sayfası"

#: Çizgi kalınlıkları ve ölçüler (mm).
FRAME_STROKE = 0.2
CROSS_STROKE = 0.15
CROSS_ARM = 3.0
TICK_STROKE = 0.1
#: Köşe cetvelinin kenarın iki yanına uzanımı (mm) ve çentik boyları.
SCALE_REACH = 4
TICK_SHORT = 0.8
TICK_LONG = 1.4
SCALE_TEXT_MM = 1.1
CELL_NUMBER_TEXT_MM = 2.0
#: Açıklama kutusu (mm) ve ölçek denetim çizgisi.
INFO_WIDTH = 124.0
INFO_HEIGHT = 40.0
CHECK_BAR_MM = 100.0


@dataclass(frozen=True)
class CalibrationSheet:
    """Kalibrasyon sayfasının bağlamı (test için PDF'siz de kurulabilir)."""

    context: dict[str, Any]
    cells: tuple[CellBox, ...]


def signed_mm(value: float) -> str:
    """Kullanıcı metni için işaretli mm: +0,50 · −0,25 · 0,00 (virgül ondalık)."""
    if abs(value) < 0.005:
        return "0,00"
    isaret = "+" if value > 0 else "−"
    return f"{isaret}{abs(value):.2f}".replace(".", ",")


def _corner_indices(geometry: SheetGeometry) -> set[int]:
    son = geometry.capacity - 1
    return {0, geometry.cols - 1, son - (geometry.cols - 1), son}


def _ruler_printable(edge: float, page: float) -> bool:
    """Kenarın cetveli (kenar ± SCALE_REACH) yazıcının basabildiği alanda mı?"""
    pay = PRINT_SAFE_MARGIN_MM
    return edge - SCALE_REACH >= pay - 1e-9 and edge + SCALE_REACH <= page - pay + 1e-9


def _choose_edges(outer: list[float], pair: tuple[float, float], page: float) -> list[float]:
    """Cetvelli kenarlar: basılabiliyorsa dış kenar, basılamıyorsa aynı etiketin öteki kenarı.

    Öteki kenar da basılamıyorsa (tek sütunlu dar sayfa gibi) dış kenarda kalınır.
    """
    secilen: list[float] = []
    for kenar in outer:
        aday = kenar
        if not _ruler_printable(kenar, page):
            oteki = pair[1] if kenar == pair[0] else pair[0]
            if _ruler_printable(oteki, page):
                aday = oteki
        if aday not in secilen:
            secilen.append(aday)
    return secilen


def measured_edges(cell: CellBox, geometry: SheetGeometry) -> tuple[list[float], list[float]]:
    """Köşe hücresinin cetvelli kenarları: (dikey kenarların x'leri, yatay kenarların y'leri).

    Tabakanın dışına bakan kenar (1. hücrede sol ve üst, son hücrede sağ ve alt)
    cetveli yazıcının basabildiği alana düşüyorsa seçilir; düşmüyorsa cetvel aynı
    etiketin iç kenarına taşınır (modül başlığı).
    """
    dikey = _choose_edges(
        [
            kenar
            for kenar, dis in (
                (cell.left, cell.col == 0),
                (cell.right, cell.col == geometry.cols - 1),
            )
            if dis
        ],
        (cell.left, cell.right),
        A4_WIDTH_MM,
    )
    yatay = _choose_edges(
        [
            kenar
            for kenar, dis in (
                (cell.top, cell.row == 0),
                (cell.bottom, cell.row == geometry.rows - 1),
            )
            if dis
        ],
        (cell.top, cell.bottom),
        A4_HEIGHT_MM,
    )
    return dikey, yatay


def _scale_marks(cell: CellBox, geometry: SheetGeometry) -> tuple[list[str], list[str]]:
    """Köşe hücresinin kenarlarını dik kesen mm cetvelleri (0 = basılı çerçeve).

    Dönen: (çizgiler, yazılar). Kenarlar `measured_edges`'ten gelir. Değerler
    kaymaya EKLENECEK düzeltmedir: dikey kenarda sağ taraf artı (X), yatay
    kenarda alt taraf artı (Y) — kenar dış ya da iç olsun, kural aynıdır.
    Çentik her 1 mm'de, uzun çentik ve değer her 2 mm'dedir.
    """
    cx, cy = cell.center
    cizgiler: list[str] = []
    yazilar: list[str] = []
    dikey_kenarlar, yatay_kenarlar = measured_edges(cell, geometry)
    for kenar_x in dikey_kenarlar:
        for k in range(-SCALE_REACH, SCALE_REACH + 1):
            x = kenar_x + k
            boy = TICK_LONG if k % 2 == 0 else TICK_SHORT
            cizgiler.append(
                f'<line x1="{mm_text(x)}" y1="{mm_text(cy - boy / 2)}" '
                f'x2="{mm_text(x)}" y2="{mm_text(cy + boy / 2)}"/>'
            )
            if k and k % 2 == 0:
                yazilar.append(
                    f'<text x="{mm_text(x)}" y="{mm_text(cy + boy / 2 + SCALE_TEXT_MM)}" '
                    f'text-anchor="middle">{k:+d}</text>'
                )
        cizgiler.append(
            f'<line x1="{mm_text(kenar_x - SCALE_REACH)}" y1="{mm_text(cy)}" '
            f'x2="{mm_text(kenar_x + SCALE_REACH)}" y2="{mm_text(cy)}"/>'
        )
    for kenar_y in yatay_kenarlar:
        for k in range(-SCALE_REACH, SCALE_REACH + 1):
            y = kenar_y + k
            boy = TICK_LONG if k % 2 == 0 else TICK_SHORT
            cizgiler.append(
                f'<line x1="{mm_text(cx - boy / 2)}" y1="{mm_text(y)}" '
                f'x2="{mm_text(cx + boy / 2)}" y2="{mm_text(y)}"/>'
            )
            if k and k % 2 == 0:
                yazilar.append(
                    f'<text x="{mm_text(cx + boy / 2 + 0.4)}" '
                    f'y="{mm_text(y + SCALE_TEXT_MM / 3)}">{k:+d}</text>'
                )
        cizgiler.append(
            f'<line x1="{mm_text(cx)}" y1="{mm_text(kenar_y - SCALE_REACH)}" '
            f'x2="{mm_text(cx)}" y2="{mm_text(kenar_y + SCALE_REACH)}"/>'
        )
    return cizgiler, yazilar


def page_svg(geometry: SheetGeometry, offset: CalibrationOffset) -> tuple[str, tuple[CellBox, ...]]:
    """Sayfanın tamamı tek SVG (mm): çerçeveler, artılar, hücre numaraları, köşe cetvelleri."""
    hucreler = geometry.cells(offset)
    koseler = _corner_indices(geometry)
    cerceveler: list[str] = []
    artilar: list[str] = []
    numaralar: list[str] = []
    cetveller: list[str] = []
    cetvel_yazilari: list[str] = []
    yaricap = mm_text(
        min(geometry.corner_radius, geometry.label_width / 2, geometry.label_height / 2)
    )
    for hucre in hucreler:
        cerceveler.append(
            f'<rect x="{mm_text(hucre.left)}" y="{mm_text(hucre.top)}" '
            f'width="{mm_text(hucre.width)}" height="{mm_text(hucre.height)}" rx="{yaricap}"/>'
        )
        cx, cy = hucre.center
        artilar.append(
            f"M{mm_text(cx - CROSS_ARM)} {mm_text(cy)}H{mm_text(cx + CROSS_ARM)}"
            f"M{mm_text(cx)} {mm_text(cy - CROSS_ARM)}V{mm_text(cy + CROSS_ARM)}"
        )
        # Hücre numarası sol üst köşededir; kenarsız tabakada yazıcının
        # basabildiği alana alınır.
        numara_x = max(hucre.left + 0.8, PRINT_SAFE_MARGIN_MM)
        numara_y = max(hucre.top + 0.8, PRINT_SAFE_MARGIN_MM) + CELL_NUMBER_TEXT_MM
        numaralar.append(
            f'<text x="{mm_text(numara_x)}" y="{mm_text(numara_y)}">{hucre.number}</text>'
        )
        if hucre.index in koseler:
            cizgiler, yazilar = _scale_marks(hucre, geometry)
            cetveller.extend(cizgiler)
            cetvel_yazilari.extend(yazilar)
    genislik = mm_text(A4_WIDTH_MM)
    yukseklik = mm_text(A4_HEIGHT_MM)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{genislik}mm" height="{yukseklik}mm" '
        f'viewBox="0 0 {genislik} {yukseklik}" font-family="DejaVu Sans">'
        f'<g fill="none" stroke="#000" stroke-width="{FRAME_STROKE}">{"".join(cerceveler)}</g>'
        f'<path fill="none" stroke="#000" stroke-width="{CROSS_STROKE}" d="{"".join(artilar)}"/>'
        f'<g fill="#555" font-size="{CELL_NUMBER_TEXT_MM}">{"".join(numaralar)}</g>'
        f'<g stroke="#000" stroke-width="{TICK_STROKE}">{"".join(cetveller)}</g>'
        f'<g fill="#000" font-size="{SCALE_TEXT_MM}">{"".join(cetvel_yazilari)}</g>'
        "</svg>"
    )
    return svg, hucreler


def build_calibration_sheet(
    template: LabelSheetTemplate | SheetGeometry,
    calibration: LabelCalibration | CalibrationOffset | None = None,
    *,
    template_name: str | None = None,
    printer_name: str | None = None,
) -> CalibrationSheet:
    """Kalibrasyon sayfasının bağlamı (PDF'siz)."""
    from apps.kutuphane.models import LabelCalibration, LabelSheetTemplate

    if isinstance(template, LabelSheetTemplate):
        geometri = SheetGeometry.from_template(template)
        ad = template_name if template_name is not None else template.name
    else:
        geometri = template
        ad = template_name or ""
    if isinstance(calibration, LabelCalibration):
        if isinstance(template, LabelSheetTemplate) and calibration.template_id != template.pk:
            raise LabelError(
                "Seçilen kalibrasyon bu etiket şablonuna ait değil.", field="calibration"
            )
        yazici = printer_name if printer_name is not None else calibration.printer_name
        kayma = CalibrationOffset.from_calibration(calibration)
    else:
        yazici = printer_name or ""
        kayma = calibration or CalibrationOffset()
    geometri.validate()
    kayma.validate()
    svg, hucreler = page_svg(geometri, kayma)
    baglam = {
        "document_title": DOCUMENT_NAME,
        "page_svg": svg,
        "template_name": clean_text(ad) or "Adsız şablon",
        "printer_name": clean_text(yazici),
        "offset_x": signed_mm(kayma.x),
        "offset_y": signed_mm(kayma.y),
        "labels_per_sheet": geometri.capacity,
        "info": {
            "left": mm_text((A4_WIDTH_MM - INFO_WIDTH) / 2),
            "top": mm_text((A4_HEIGHT_MM - INFO_HEIGHT) / 2),
            "width": mm_text(INFO_WIDTH),
            "height": mm_text(INFO_HEIGHT),
        },
        "check_bar_mm": mm_text(CHECK_BAR_MM),
        "check_bar_ticks": [mm_text(k * 10.0) for k in range(11)],
    }
    return CalibrationSheet(context=baglam, cells=hucreler)


def render_calibration_sheet(
    template: LabelSheetTemplate | SheetGeometry,
    calibration: LabelCalibration | CalibrationOffset | None = None,
    *,
    template_name: str | None = None,
    printer_name: str | None = None,
) -> bytes:
    """Kalibrasyon sayfası PDF'i (tek sayfa). Veritabanına yazmaz."""
    sayfa = build_calibration_sheet(
        template, calibration, template_name=template_name, printer_name=printer_name
    )
    return html_to_pdf(render_to_string(TEMPLATE_NAME, sayfa.context))
