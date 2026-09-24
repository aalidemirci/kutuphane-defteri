"""Tek etiketin iç düzeni: metin satırları, barkod ve QR kutuları (mm, hücreye göre).

Bütün kutular burada, Python'da hesaplanır; şablon yalnız mutlak konumlu
kutuları basar. Böylece (1) sayfa bütçesi yazı tipi davranışına bağlı kalmaz,
(2) her satırın hücreye sığdığı basımdan ÖNCE bilinir ve test edilebilir
(CLAUDE.md §3 "WeasyPrint ölçü tuzakları": tablo ve akış düzeni yerine
mutlak konum; `text-transform` yok).

**Satır kutusu.** Her metin satırı tek satırdır (`white-space: nowrap`) ve
kutusunun yüksekliği yazı boyunun 1,2 katıdır: DejaVu Sans'ın yükselen + inen
toplamı 1,164 em'dir, 1,2 em kutu harfleri kırpmadan taşır. Genişlik
`metrics.fit_text` ile kutuya sığdırılır; `overflow: hidden` yalnız son güvencedir.

**Barkod etiketi** (§7.2): yukarıdan aşağı kısaltılmış eser adı · Code128-C
barkod · okunur numara (`2026-000123`) · alt satırda solda yer numarası, sağda
kısa okul adı. **Boş barkod etiketi** (yöntem B): kısa okul adı · barkod ·
okunur numara; künye yoktur. **QR** (varsayılan kapalı) etiketin sağına konur;
içeriği rakamdır, URL değildir ve 48,5 × 25,4 mm ya da daha büyük etiket ister.

**Sırt etiketi** (§7.2): yer numarası 1-3 satır (büyük, kalın, ortalı) + altta
kısa okul adı. Yazı boyu bütün satırlar sığacak biçimde büyükten küçüğe denenir;
en küçük boyda da sığmayan satır "…" ile kısaltılır — taşma olmaz.

**Yazıcının basamadığı kenar payı** (`geometry.PRINT_SAFE_MARGIN_MM`). Hücre
sayfa kenarına yakınsa (kenarsız 40'lı tabakanın dış sütun ve satırları) bar,
QR modülü ve yazı sayfa kenarından en az 5 mm içeride tutulur; barkodun ve QR'ın
sessiz bölgesi bu paya taşabilir. İçerik yalnız o kenardan içeri kayar
(`ink_insets`). Kalibrasyon kayması hücreyi sayfadan taşıracak kadar büyükse ve
güvenli düzen sığmıyorsa olağan düzen basılır (en iyi çaba — basım reddedilmez).
"""

from __future__ import annotations

from dataclasses import dataclass

import segno

from apps.kutuphane.labels.content import (
    MISSING_CALL_NUMBER,
    LabelContent,
    LabelItem,
    split_call_number,
)
from apps.kutuphane.labels.geometry import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    PRINT_SAFE_MARGIN_MM,
    CellBox,
    LabelError,
    snap_to_module,
)
from apps.kutuphane.labels.metrics import MM_PER_PT, fit_text, largest_fitting_size, text_width_mm
from shared import barcode128

#: Satır kutusunun yazı boyuna oranı (DejaVu yükselen + inen = 1,164 em).
LINE_FACTOR = 1.2
#: Hücre iç boşlukları (mm).
PAD_X = 1.0
PAD_Y = 0.8
#: Satırlar arası boşluk (mm).
GAP = 0.3
#: Metni sığdırırken bırakılan pay (mm): Pango'nun konum yuvarlamasına karşı.
FIT_SAFETY_MM = 0.15
#: Code128 barkod yüksekliği sınırları (mm). Alt sınır uygulamada yaygın
#: kabul edilen en küçük yüksekliktir (0,25 inç); üst sınır küçük tabakalarda
#: metne yer bırakır.
MIN_BAR_HEIGHT_MM = 6.35
MAX_BAR_HEIGHT_MM = 12.0
#: Barkod bloğunun iki yanında hücre kenarına en az bırakılacak pay (mm).
MIN_BARCODE_SIDE_MM = 0.5
#: QR: en küçük etiket (§7.2 — 48,5 × 25,4 ya da 52,5 × 29,7 mm şablonu),
#: kenar sınırları ve standart sessiz bölge (4 modül).
QR_MIN_LABEL_MM = (48.5, 25.4)
QR_MIN_SIDE_MM = 12.0
QR_MAX_SIDE_MM = 20.0
QR_QUIET_MODULES = 4
#: Güvenli basım payı QR'ı sıkıştırırsa kenar bu adımlarla küçültülür (mm).
QR_SIDE_STEP_MM = 0.25
#: Barkodun sessiz bölgesi (10X = 2,54 mm): basılmayan kenar payına taşabilir.
BARCODE_QUIET_MM = barcode128.QUIET_ZONE_MODULES * barcode128.DEFAULT_MODULE_MM
_EPS = 1e-9
#: Etiket ölçüsüne göre büyütülen yazı boylarının dayanağı (65'li tabaka yüksekliği).
BASE_LABEL_HEIGHT_MM = 21.2
MAX_TEXT_SCALE = 1.3

#: Yazı boyları (pt), 21,2 mm yüksekliğinde etiket için.
TITLE_SIZE = 5.5
NUMBER_SIZE = 7.5
BLANK_NUMBER_SIZE = 8.0
CALL_SIZES = (6.5, 6.0, 5.5, 5.0)
SCHOOL_SIZES = (5.5, 5.0, 4.5)
BLANK_SCHOOL_SIZE = 6.0
SPINE_SIZES = (12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.5, 6.0)
SPINE_SCHOOL_SIZES = (5.5, 5.0, 4.5)
#: Alt satırda kısa okul adının alabileceği en çok pay (gerisi yer numarasının).
SCHOOL_SHARE = 0.45
#: Alt satırdaki iki kutu arasındaki boşluk (mm).
BOTTOM_GAP = 1.0
#: Sırtta satır bloğu ile okul adı arasındaki boşluk (mm).
SPINE_SCHOOL_GAP = 0.5


@dataclass(frozen=True)
class TextBox:
    """Hücre içinde tek satırlık metin kutusu (mm, hücrenin sol üst köşesine göre)."""

    role: str  # title | number | call | school | spine
    text: str
    left: float
    top: float
    width: float
    height: float
    size_pt: float
    bold: bool = False
    align: str = "center"


@dataclass(frozen=True)
class GraphicBox:
    """Hücre içinde SVG çizim kutusu (barkod ya da QR)."""

    role: str  # barcode | qr
    svg: str
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True)
class LabelLayout:
    texts: tuple[TextBox, ...]
    graphics: tuple[GraphicBox, ...]


@dataclass(frozen=True)
class Insets:
    """Mürekkebin hücre kenarlarından en az uzaklığı (mm)."""

    left: float
    top: float
    right: float
    bottom: float


#: Olağan iç boşluk: hücre sayfa kenarından yeterince uzaksa.
PAD_INSETS = Insets(PAD_X, PAD_Y, PAD_X, PAD_Y)


def ink_insets(cell: CellBox) -> Insets:
    """Hücrenin mürekkep payları: iç boşluk ya da sayfanın basılabilir alanı, hangisi büyükse.

    Hücrenin sayfadaki konumu (kalibrasyon kayması dahil) kullanılır: yazıcının
    basamadığı pay sayfanın kenarından ölçülür.
    """
    pay = PRINT_SAFE_MARGIN_MM
    return Insets(
        left=max(PAD_X, pay - cell.left),
        top=max(PAD_Y, pay - cell.top),
        right=max(PAD_X, cell.right - (A4_WIDTH_MM - pay)),
        bottom=max(PAD_Y, cell.bottom - (A4_HEIGHT_MM - pay)),
    )


def line_height(size_pt: float) -> float:
    """Tek satırlık kutunun yüksekliği (mm)."""
    return size_pt * MM_PER_PT * LINE_FACTOR


def text_scale(label_height_mm: float) -> float:
    """Büyük etikette yazı boyu büyür (en çok 1,3 kat), küçükte küçülmez."""
    return min(MAX_TEXT_SCALE, max(1.0, label_height_mm / BASE_LABEL_HEIGHT_MM))


def barcode_block_width(module_mm: float = barcode128.DEFAULT_MODULE_MM) -> float:
    """10 haneli nüsha barkodunun sessiz bölgeli genişliği: 110 × X = 27,94 mm."""
    return barcode128.module_count("2026000000") * module_mm


def _fit_box_text(
    text: str, width: float, sizes: tuple[float, ...], *, bold: bool
) -> tuple[str, float]:
    """Metni kutuya en büyük uygun boyla sığdırır; hiçbirinde sığmıyorsa en küçükte kırpar."""
    boy = largest_fitting_size([text], width - FIT_SAFETY_MM, sizes, bold=bold)
    if boy is not None:
        return text, boy
    en_kucuk = sizes[-1]
    return fit_text(text, width - FIT_SAFETY_MM, en_kucuk, bold=bold), en_kucuk


def qr_svg(digits: str, side_mm: float) -> str:
    """Rakam içerikli QR (URL değil — §7.2); mm ölçülü bağımsız SVG, 4 modül sessiz bölge.

    `make_qr` mikro QR'ı dışlar (telefon ve masa okuyucularının çoğu mikro QR
    okumaz); 10 rakam sürüm 1'e sığar.
    """
    kod = segno.make_qr(digits, error="m")
    matris = kod.matrix
    boyut = len(matris)
    toplam = boyut + 2 * QR_QUIET_MODULES
    parcalar: list[str] = []
    for satir_no, satir in enumerate(matris):
        sutun = 0
        while sutun < boyut:
            if satir[sutun]:
                bas = sutun
                while sutun < boyut and satir[sutun]:
                    sutun += 1
                parcalar.append(
                    f'<rect x="{bas + QR_QUIET_MODULES}" y="{satir_no + QR_QUIET_MODULES}" '
                    f'width="{sutun - bas}" height="1"/>'
                )
            else:
                sutun += 1
    kenar = f"{side_mm:.3f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{kenar}mm" height="{kenar}mm" '
        f'viewBox="0 0 {toplam} {toplam}" shape-rendering="crispEdges">'
        f'<rect width="{toplam}" height="{toplam}" fill="#fff"/>'
        f'<g fill="#000">{"".join(parcalar)}</g></svg>'
    )


def _require_qr_label(cell: CellBox) -> None:
    """Etiket QR'a küçükse `LabelError` (§7.2: 48,5 × 25,4 mm ve üstü)."""
    min_w, min_h = QR_MIN_LABEL_MM
    if cell.width < min_w - 0.05 or cell.height < min_h - 0.05:
        raise LabelError(
            "QR kodu için 48,5 × 25,4 mm ya da 52,5 × 29,7 mm şablonu seçin; "
            "bu etiket QR'a küçük.",
            field="include_qr",
        )


def _qr_quiet_fraction(digits: str) -> float:
    """QR kutusunda sessiz bölgenin kenara oranı (sürüm 1'de 4 / 29)."""
    boyut = len(segno.make_qr(digits, error="m").matrix)
    return QR_QUIET_MODULES / (boyut + 2 * QR_QUIET_MODULES)


@dataclass(frozen=True)
class _QrBox:
    left: float
    top: float
    side: float


def _qr_box(cell: CellBox, ins: Insets, *, block_left_min: float, quiet: float) -> _QrBox:
    """QR kutusu (sessiz bölge dahil): etiketin sağında, barkod bloğuna yer bırakarak.

    Kutu hücrenin iç boşluğunda kalır; KOYU modüller mürekkep paylarının
    (`ins`) içinde kalır, sessiz bölge paya taşabilir. Olağan paylarda kenar
    `min(yükseklik − 2 × iç boşluk, genişlik − barkod − 3 × iç boşluk, 20)`'dir
    ve kutu dikeyde ortalanır; güvenli basım payı sığmazsa kenar adım adım
    küçülür (en az 12 mm), o da sığmazsa `LabelError`.
    """
    blok = barcode_block_width()
    genislik, yukseklik = cell.width, cell.height
    kenar = min(
        yukseklik - 2 * PAD_Y,
        genislik - blok - block_left_min - 2 * PAD_X,
        QR_MAX_SIDE_MM,
    )
    while kenar >= QR_MIN_SIDE_MM - _EPS:
        pay = kenar * quiet
        sag = min(genislik - PAD_X, genislik - ins.right + pay)
        sol = sag - kenar
        ust_en_az = max(PAD_Y, ins.top - pay)
        ust_en_cok = min(yukseklik - PAD_Y, yukseklik - ins.bottom + pay) - kenar
        if sol - PAD_X - blok >= block_left_min - _EPS and ust_en_az <= ust_en_cok + _EPS:
            ust = min(max((yukseklik - kenar) / 2, ust_en_az), ust_en_cok)
            return _QrBox(left=sol, top=ust, side=kenar)
        kenar -= QR_SIDE_STEP_MM
    raise LabelError("Bu etikette barkodun yanında QR koduna yer kalmıyor.", field="include_qr")


def _barcode_left(cell: CellBox, ideal: float, low: float, high: float) -> float:
    """Barkod bloğunun hücreye göre sol kenarı: sayfada modül katına (yazıcı noktasına) çekilir.

    `ideal` önce [low, high] aralığına sıkıştırılır; nokta hizası en çok X/2
    kaydırır ve aralığın dışına düşerse bir modül öteki yana alınır.
    """
    hedef = min(max(ideal, low), high)
    hizali = snap_to_module(cell.left + hedef) - cell.left
    for aday in (
        hizali,
        hizali + barcode128.DEFAULT_MODULE_MM,
        hizali - barcode128.DEFAULT_MODULE_MM,
    ):
        if low - _EPS <= aday <= high + _EPS:
            return aday
    return hizali


def barcode_layout(
    item: LabelItem,
    cell: CellBox,
    *,
    content: LabelContent,
    school: str,
    include_qr: bool = False,
) -> LabelLayout:
    """Barkod etiketi ya da boş barkod etiketi düzeni.

    Hücre sayfa kenarına yakınsa önce güvenli basım paylarıyla (`ink_insets`)
    kurulur; sığmazsa olağan düzen basılır (modül başlığı).
    """
    if include_qr:
        _require_qr_label(cell)
    guvenli = ink_insets(cell)
    if guvenli != PAD_INSETS:
        try:
            return _barcode_layout(
                item, cell, content=content, school=school, include_qr=include_qr, ins=guvenli
            )
        except LabelError:
            pass  # güvenli pay bu hücrede yer bırakmıyor: olağan düzen (en iyi çaba)
    return _barcode_layout(
        item, cell, content=content, school=school, include_qr=include_qr, ins=PAD_INSETS
    )


def _barcode_layout(
    item: LabelItem,
    cell: CellBox,
    *,
    content: LabelContent,
    school: str,
    include_qr: bool,
    ins: Insets,
) -> LabelLayout:
    blok = barcode_block_width()
    olcek = text_scale(cell.height)
    # Barkod bloğunun sol kenarı en az: QR'lı etikette iç boşluk, QR'sızda hücre
    # kenarına MIN_BARCODE_SIDE_MM (blok iç boşluğa taşabilir). İki durumda da
    # BARLAR mürekkep payının içindedir; yalnız sessiz bölge paya taşar.
    blok_sol_en_az = max(PAD_X if include_qr else MIN_BARCODE_SIDE_MM, ins.left - BARCODE_QUIET_MM)
    qr: _QrBox | None = None
    if include_qr:
        qr = _qr_box(
            cell, ins, block_left_min=blok_sol_en_az, quiet=_qr_quiet_fraction(item.barcode)
        )
        sutun_sol = ins.left
        sutun_sag = qr.left - PAD_X
        blok_sol_en_cok = sutun_sag - blok
    else:
        sutun_sol = ins.left
        sutun_sag = cell.width - ins.right
        blok_sol_en_cok = (
            min(cell.width - MIN_BARCODE_SIDE_MM, cell.width - ins.right + BARCODE_QUIET_MM) - blok
        )
    sutun_gen = sutun_sag - sutun_sol
    if blok_sol_en_cok + _EPS < blok_sol_en_az or sutun_gen + _EPS < blok - 2 * BARCODE_QUIET_MM:
        raise LabelError(
            f"Etiket genişliği barkoda yetmiyor: barkod sessiz bölgeleriyle {blok:.2f} mm'dir, "
            f"en az {blok + 2 * MIN_BARCODE_SIDE_MM:.1f} mm genişlikte etiket seçin.",
            field="template",
        )

    bos = content == LabelContent.BLANK_BARCODE
    okul = school.strip()
    ust_boy = (BLANK_SCHOOL_SIZE if bos else TITLE_SIZE) * olcek
    numara_boy = (BLANK_NUMBER_SIZE if bos else NUMBER_SIZE) * olcek
    alt_boy = max(CALL_SIZES) * olcek

    # Dikey yığın: [üst satır] · barkod · numara · [alt satır]
    ust_var = bool(okul) if bos else True
    alt_var = not bos
    metin_yuk = line_height(numara_boy)
    satir_sayisi = 2
    if ust_var:
        metin_yuk += line_height(ust_boy)
        satir_sayisi += 1
    if alt_var:
        metin_yuk += line_height(alt_boy)
        satir_sayisi += 1
    ham_bar = cell.height - ins.top - ins.bottom - metin_yuk - GAP * (satir_sayisi - 1)
    if ham_bar < MIN_BAR_HEIGHT_MM:
        raise LabelError(
            "Etiket yüksekliği barkoda yetmiyor: barkodun kendisi en az "
            f"{MIN_BAR_HEIGHT_MM:.2f} mm yükseklik ister.",
            field="template",
        )
    bar_yuk = min(ham_bar, MAX_BAR_HEIGHT_MM)
    y = ins.top + (ham_bar - bar_yuk) / 2

    # Satır kutularının yüksekliği AYRILAN boydan gelir; sığdırmak için küçülen
    # yazı kutuda dikey ortalanır (line-height = kutu yüksekliği), yığın kaymaz.
    metinler: list[TextBox] = []
    if ust_var:
        ust_yuk = line_height(ust_boy)
        if bos:
            okul_boylari = tuple(b * olcek for b in (BLANK_SCHOOL_SIZE, *SCHOOL_SIZES))
            ust_metin, yazi_boy = _fit_box_text(okul, sutun_gen, okul_boylari, bold=False)
            rol = "school"
        else:
            ust_metin, yazi_boy = fit_text(item.title, sutun_gen - FIT_SAFETY_MM, ust_boy), ust_boy
            rol = "title"
        metinler.append(TextBox(rol, ust_metin, sutun_sol, y, sutun_gen, ust_yuk, yazi_boy))
        y += ust_yuk + GAP

    # Barkod: sütunda ortalanır, sayfadaki sol kenarı modül katına (yazıcı
    # noktasına) çekilir.
    bar_sol = _barcode_left(
        cell, sutun_sol + (sutun_gen - blok) / 2, blok_sol_en_az, blok_sol_en_cok
    )
    grafikler = [
        GraphicBox(
            "barcode",
            barcode128.svg(item.barcode, height_mm=bar_yuk),
            bar_sol,
            y,
            blok,
            bar_yuk,
        )
    ]
    y += bar_yuk + GAP

    numara_yuk = line_height(numara_boy)
    numara_metin, yazi_boy = _fit_box_text(
        item.printed_number, sutun_gen, (numara_boy, numara_boy * 0.9, numara_boy * 0.8), bold=True
    )
    metinler.append(
        TextBox("number", numara_metin, sutun_sol, y, sutun_gen, numara_yuk, yazi_boy, bold=True)
    )
    y += numara_yuk + GAP

    if alt_var:
        metinler.extend(_bottom_row(item.call_number, okul, sutun_sol, y, sutun_gen, olcek))

    if qr is not None:
        grafikler.append(
            GraphicBox("qr", qr_svg(item.barcode, qr.side), qr.left, qr.top, qr.side, qr.side)
        )
    return LabelLayout(texts=tuple(metinler), graphics=tuple(grafikler))


def _bottom_row(
    call_number: str, school: str, left: float, top: float, width: float, scale: float
) -> list[TextBox]:
    """Barkod etiketinin alt satırı: solda yer numarası, sağda kısa okul adı."""
    yer_boylari = tuple(b * scale for b in CALL_SIZES)
    okul_boylari = tuple(b * scale for b in SCHOOL_SIZES)
    satir_yuk = line_height(max(yer_boylari))
    kutular: list[TextBox] = []
    yer = call_number.strip()
    if yer and school:
        okul_metin, okul_boy = _fit_box_text(school, width * SCHOOL_SHARE, okul_boylari, bold=False)
        okul_gen = min(width * SCHOOL_SHARE, text_width_mm(okul_metin, okul_boy) + FIT_SAFETY_MM)
        yer_gen = width - okul_gen - BOTTOM_GAP
        yer_metin, yer_boy = _fit_box_text(yer, yer_gen, yer_boylari, bold=True)
        kutular.append(
            TextBox(
                "call", yer_metin, left, top, yer_gen, satir_yuk, yer_boy, bold=True, align="left"
            )
        )
        kutular.append(
            TextBox(
                "school",
                okul_metin,
                left + width - okul_gen,
                top,
                okul_gen,
                satir_yuk,
                okul_boy,
                align="right",
            )
        )
    elif yer:
        yer_metin, yer_boy = _fit_box_text(yer, width, yer_boylari, bold=True)
        kutular.append(TextBox("call", yer_metin, left, top, width, satir_yuk, yer_boy, bold=True))
    elif school:
        okul_metin, okul_boy = _fit_box_text(school, width, okul_boylari, bold=False)
        kutular.append(TextBox("school", okul_metin, left, top, width, satir_yuk, okul_boy))
    return kutular


def spine_layout(item: LabelItem, cell: CellBox, *, school: str) -> LabelLayout:
    """Sırt etiketi: yer numarası satırları + kısa okul adı.

    Hücre sayfa kenarına yakınsa önce güvenli basım paylarıyla kurulur (yatay
    pay iki yana EŞİT verilir: sırt yazısı etiketin ortasında kalır); sığmazsa
    olağan düzen basılır.
    """
    guvenli = ink_insets(cell)
    if guvenli != PAD_INSETS:
        yatay = max(guvenli.left, guvenli.right)
        try:
            return _spine_layout(
                item, cell, school=school, ins=Insets(yatay, guvenli.top, yatay, guvenli.bottom)
            )
        except LabelError:
            pass  # güvenli pay bu hücrede yer bırakmıyor: olağan düzen (en iyi çaba)
    return _spine_layout(item, cell, school=school, ins=PAD_INSETS)


def _spine_layout(item: LabelItem, cell: CellBox, *, school: str, ins: Insets) -> LabelLayout:
    genislik = cell.width - ins.left - ins.right
    if genislik <= FIT_SAFETY_MM:
        raise LabelError("Etiket genişliği sırt etiketine yetmiyor.", field="template")
    satirlar = split_call_number(item.call_number) or [MISSING_CALL_NUMBER]
    okul = school.strip()
    metinler: list[TextBox] = []

    alt = cell.height - ins.bottom
    if okul:
        okul_metin, okul_boy = _fit_box_text(okul, genislik, SPINE_SCHOOL_SIZES, bold=False)
        okul_yuk = line_height(SPINE_SCHOOL_SIZES[0])
        alt -= okul_yuk
        metinler.append(TextBox("school", okul_metin, ins.left, alt, genislik, okul_yuk, okul_boy))
        alt -= SPINE_SCHOOL_GAP
    alan = alt - ins.top

    yukseklige_uyan = [b for b in SPINE_SIZES if len(satirlar) * line_height(b) <= alan]
    if not yukseklige_uyan:
        raise LabelError(
            "Etiket yüksekliği yer numarasının satırlarına yetmiyor; daha büyük bir sırt "
            "etiketi şablonu seçin.",
            field="template",
        )
    # Kutular yüksekliğe uyan en büyük boyla eşit aralıklı dizilir. Satırlar
    # hep birlikte sığıyorsa aynı boyda basılır; sığmayan satır YALNIZ KENDİSİ
    # küçülür (kısa sınıflama kodu, uzun bir yazar kodu yüzünden okunmaz
    # hâle gelmesin), en küçük boyda da sığmazsa "…" ile kısaltılır.
    satir_yuk = line_height(yukseklige_uyan[0])
    y = ins.top + (alan - len(satirlar) * satir_yuk) / 2
    for satir in satirlar:
        metin, boy = _fit_box_text(satir, genislik, tuple(yukseklige_uyan), bold=True)
        metinler.append(TextBox("spine", metin, ins.left, y, genislik, satir_yuk, boy, bold=True))
        y += satir_yuk
    return LabelLayout(texts=tuple(metinler), graphics=())


def label_layout(
    item: LabelItem,
    cell: CellBox,
    *,
    content: LabelContent,
    school: str,
    include_qr: bool = False,
) -> LabelLayout:
    """İçerik türüne göre düzen. QR yalnız barkod etiketlerine basılır."""
    if content == LabelContent.SPINE:
        return spine_layout(item, cell, school=school)
    return barcode_layout(item, cell, content=content, school=school, include_qr=include_qr)


#: Etiket ölçüsünün bir içeriğe yetip yetmediğini sınamak için örnek kalem.
_SAMPLE_ITEM = LabelItem(barcode="2026000001", title="Örnek", call_number="000 ÖRN")


def supports(
    width_mm: float, height_mm: float, *, content: LabelContent, include_qr: bool = False
) -> bool:
    """Bu ölçüdeki etiket verilen içeriği (ve istenirse QR'ı) taşıyabilir mi?

    Şablon listesindeki "QR'a uygun" / "barkoda uygun" işaretleri buradan gelir;
    ölçüt basımın kendisiyle aynıdır (aynı düzen işlevi). Örnek hücre sayfanın
    içindedir (olağan düzen); sayfa kenarındaki hücrede içerik güvenli basım
    payına göre içeri kayar, sığmazsa yine olağan düzen basılır.
    """
    kenar = PRINT_SAFE_MARGIN_MM
    hucre = CellBox(index=0, row=0, col=0, left=kenar, top=kenar, width=width_mm, height=height_mm)
    try:
        label_layout(_SAMPLE_ITEM, hucre, content=content, school="", include_qr=include_qr)
    except LabelError:
        return False
    return True
