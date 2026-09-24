"""Etiket tabakasının yerleşim hesabı: hücre konumları, kalibrasyon, başlangıç hücresi.

Saf hesaptır: veritabanına, şablon motoruna ya da WeasyPrint'e dokunmaz. Model
nesneleri (`LabelSheetTemplate`, `LabelCalibration`) yalnız `from_template` /
`from_calibration` üzerinden sayıya çevrilir; bütün ölçüler milimetredir ve
sayfa A4'tür (210 × 297 mm — şablon modelinde sayfa ölçüsü alanı yoktur).

**Hücre sırası.** Hücreler satır önceliklidir: soldan sağa, yukarıdan aşağı
(1. hücre sol üst köşe). Etiket rafa yapıştırılırken okunduğu sıra budur; sırt
ve barkod etiketleri aynı sırayla ve aynı hücrelere yerleştirilir (§7.2,
`plan_placements` ikisi için TEK plan üretir).

**Başlangıç hücresi.** Kısmen kullanılmış tabaka boşa gitmesin diye ilk tabaka
kullanıcının seçtiği hücreden başlar (1 tabanlı); sonraki tabakalar 1. hücreden.

**Kalibrasyon.** Yazıcı sapması şablonda değil şablon × yazıcı çiftindedir
(`LabelCalibration`). Kayma bütün hücrelere aynen eklenir; pozitif X sağa,
pozitif Y aşağı kaydırır.

**Barkodun yazıcı noktasına hizalanması.** Code128 modülü X = 0,254 mm'dir
(300 dpi'de 3, 600 dpi'de 6 nokta — `shared/barcode128.py`). Modül genişliğinin
nokta katı olması yetmez: barın SOL KENARI da nokta ızgarasına düşmezse her kenar
ayrı yuvarlanır ve bar ±1 nokta şişer ya da incelir. `snap_to_module` barkod
bloğunun sayfadaki sol kenarını X'in katına çeker (en çok X/2 = 0,127 mm kayma);
sayfanın sol üst köşesi yazıcının nokta ızgarasının başlangıcıdır (gerçek boyutta,
yani %100 basımda).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from django.core.exceptions import ValidationError

from shared import barcode128

#: A4 sayfa ölçüsü (mm). Etiket tabakaları A4'tür (§7.2).
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
#: Izgaranın sayfaya sığma denetiminde yuvarlama payı (mm).
FIT_TOLERANCE_MM = 0.05
#: Kalibrasyon kaymasının üst sınırı (mm). Daha büyük bir sapma yazıcı ayarı
#: (sayfaya sığdır, yanlış kâğıt boyu) sorunudur, kalibrasyonla giderilmez.
MAX_OFFSET_MM = 10.0
#: Tek belgede basılabilecek en çok etiket (= 20 tam tabaka 65'li; 1300 / 65).
MAX_LABELS_PER_DOCUMENT = 1300
#: Yazıcının basamadığı kenar payına karşı güvenli basım payı (mm). Yaygın lazer
#: yazıcılarda donanım payı 4,23 mm'dir (1/6 inç), bazılarında 5 mm. Etiketin
#: mürekkebi (bar, QR modülü, yazı, kalibrasyon cetveli) sayfa kenarından en az bu
#: kadar içeride tutulur; barkodun ve QR'ın sessiz bölgesi bu paya taşabilir,
#: çünkü basılmayan kâğıt zaten beyazdır. Kenar boşluğu ile etiketin iç
#: boşluğu birlikte bu payı karşılayan tabakalarda (65'li, 44'lü) düzen
#: değişmez; kenarsız tabakada (40'lı) dış sütun ve satırların içeriği içeri
#: kayar (`layout.ink_insets`).
PRINT_SAFE_MARGIN_MM = 5.0


class LabelError(ValidationError):
    """Etiket basımı reddi — Django `ValidationError`'ıdır, uçta 400'e çevrilir.

    `shared.exceptions.kd_exception_handler` alan sözlüğünü `{fields}`'e,
    iletiyi `message`'a yazar; motoru çağıran başka bir uç (basım partisi, boş
    barkod aralığı) ek çeviri yazmak zorunda kalmaz.
    """

    def __init__(self, message: str, *, field: str = "template") -> None:
        super().__init__({field: [message]})
        self.field = field
        self.text = message


class _TemplateLike(Protocol):
    page_margin_top: Any
    page_margin_left: Any
    label_width: Any
    label_height: Any
    rows: Any
    cols: Any
    gutter_x: Any
    gutter_y: Any
    corner_radius: Any


class _CalibrationLike(Protocol):
    offset_x: Any
    offset_y: Any


def _num(value: Decimal | float | int | None) -> float:
    return float(value) if value is not None else 0.0


def mm_text(value: float) -> str:
    """CSS/SVG için mm sayısı: üç ondalık, '-0.000' yok."""
    metin = f"{value:.3f}"
    return "0.000" if metin == "-0.000" else metin


@dataclass(frozen=True)
class CalibrationOffset:
    """Yazıcı sapması düzeltmesi (mm). Pozitif X sağa, pozitif Y aşağı."""

    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_calibration(cls, calibration: _CalibrationLike | None) -> CalibrationOffset:
        if calibration is None:
            return cls()
        return cls(x=_num(calibration.offset_x), y=_num(calibration.offset_y))

    def validate(self) -> None:
        for ad, deger in (("offset_x", self.x), ("offset_y", self.y)):
            if not math.isfinite(deger) or abs(deger) > MAX_OFFSET_MM:
                raise LabelError(
                    f"Kalibrasyon kayması en çok ±{MAX_OFFSET_MM:.0f} mm olabilir. Daha "
                    "büyük bir sapmada yazıcı ayarını denetleyin (ölçek %100, kâğıt "
                    "210 × 297 mm).",
                    field=ad,
                )


@dataclass(frozen=True)
class CellBox:
    """Bir hücrenin sayfadaki kutusu (mm, sol üst köşe kökenli)."""

    index: int  # 0 tabanlı, satır öncelikli
    row: int
    col: int
    left: float
    top: float
    width: float
    height: float

    @property
    def number(self) -> int:
        """Kullanıcının gördüğü hücre numarası (1 tabanlı)."""
        return self.index + 1

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center(self) -> tuple[float, float]:
        return self.left + self.width / 2, self.top + self.height / 2


@dataclass(frozen=True)
class SheetGeometry:
    """Tabaka ızgarası (mm). `LabelSheetTemplate`'in sayısal karşılığı."""

    margin_top: float
    margin_left: float
    label_width: float
    label_height: float
    rows: int
    cols: int
    gutter_x: float = 0.0
    gutter_y: float = 0.0
    corner_radius: float = 0.0
    page_width: float = A4_WIDTH_MM
    page_height: float = A4_HEIGHT_MM

    @classmethod
    def from_template(cls, template: _TemplateLike) -> SheetGeometry:
        return cls(
            margin_top=_num(template.page_margin_top),
            margin_left=_num(template.page_margin_left),
            label_width=_num(template.label_width),
            label_height=_num(template.label_height),
            rows=int(template.rows or 0),
            cols=int(template.cols or 0),
            gutter_x=_num(template.gutter_x),
            gutter_y=_num(template.gutter_y),
            corner_radius=_num(template.corner_radius),
        )

    @property
    def capacity(self) -> int:
        """Tabakadaki etiket sayısı."""
        return self.rows * self.cols

    @property
    def grid_width(self) -> float:
        return self.cols * self.label_width + (self.cols - 1) * self.gutter_x

    @property
    def grid_height(self) -> float:
        return self.rows * self.label_height + (self.rows - 1) * self.gutter_y

    @property
    def same_grid_key(self) -> tuple[int, int]:
        """Sırt ve barkodun aynı hücre düzeninde basılabilmesinin ölçütü."""
        return (self.rows, self.cols)

    def validate(self) -> None:
        """Izgara anlamlı ve A4'e sığıyor mu; değilse alan adlı `LabelError`."""
        if self.rows < 1:
            raise LabelError("Satır sayısı en az 1 olmalıdır.", field="rows")
        if self.cols < 1:
            raise LabelError("Sütun sayısı en az 1 olmalıdır.", field="cols")
        for ad, deger, etiket in (
            ("label_width", self.label_width, "Etiket genişliği"),
            ("label_height", self.label_height, "Etiket yüksekliği"),
        ):
            if not math.isfinite(deger) or deger <= 0:
                raise LabelError(f"{etiket} sıfırdan büyük olmalıdır.", field=ad)
        for ad, deger, etiket in (
            ("page_margin_top", self.margin_top, "Üst kenar boşluğu"),
            ("page_margin_left", self.margin_left, "Sol kenar boşluğu"),
            ("gutter_x", self.gutter_x, "Yatay boşluk"),
            ("gutter_y", self.gutter_y, "Dikey boşluk"),
            ("corner_radius", self.corner_radius, "Köşe yarıçapı"),
        ):
            if not math.isfinite(deger) or deger < 0:
                raise LabelError(f"{etiket} eksi olamaz.", field=ad)
        if self.margin_left + self.grid_width > self.page_width + FIT_TOLERANCE_MM:
            raise LabelError(
                "Etiketler sayfanın genişliğine sığmıyor: sol kenar boşluğu + sütun sayısı × "
                f"etiket genişliği + aradaki boşluklar {self.page_width:.0f} mm'yi aşıyor.",
                field="cols",
            )
        if self.margin_top + self.grid_height > self.page_height + FIT_TOLERANCE_MM:
            raise LabelError(
                "Etiketler sayfanın yüksekliğine sığmıyor: üst kenar boşluğu + satır sayısı × "
                f"etiket yüksekliği + aradaki boşluklar {self.page_height:.0f} mm'yi aşıyor.",
                field="rows",
            )

    def cell(self, index: int, offset: CalibrationOffset | None = None) -> CellBox:
        """0 tabanlı hücrenin kutusu; kalibrasyon kayması eklenmiş olarak."""
        if not 0 <= index < self.capacity:
            raise LabelError(
                f"Hücre numarası 1 ile {self.capacity} arasında olmalıdır.", field="start_cell"
            )
        kayma = offset or CalibrationOffset()
        satir, sutun = divmod(index, self.cols)
        return CellBox(
            index=index,
            row=satir,
            col=sutun,
            left=self.margin_left + sutun * (self.label_width + self.gutter_x) + kayma.x,
            top=self.margin_top + satir * (self.label_height + self.gutter_y) + kayma.y,
            width=self.label_width,
            height=self.label_height,
        )

    def cells(self, offset: CalibrationOffset | None = None) -> tuple[CellBox, ...]:
        return tuple(self.cell(sira, offset) for sira in range(self.capacity))


@dataclass(frozen=True)
class Placement:
    """Bir etiketin tabakadaki yeri. Sırt ve barkod için AYNI plan kullanılır."""

    item_index: int  # girdi listesindeki sıra (0 tabanlı)
    sheet: int  # 0 tabanlı tabaka
    cell_index: int  # 0 tabanlı hücre (satır öncelikli)

    @property
    def cell_number(self) -> int:
        return self.cell_index + 1


def validate_start_cell(start_cell: int, capacity: int) -> None:
    if isinstance(start_cell, bool) or not isinstance(start_cell, int):
        raise LabelError("Başlangıç hücresi bir sayı olmalıdır.", field="start_cell")
    if not 1 <= start_cell <= capacity:
        raise LabelError(
            f"Başlangıç hücresi 1 ile {capacity} arasında olmalıdır.", field="start_cell"
        )


def plan_placements(count: int, *, capacity: int, start_cell: int = 1) -> tuple[Placement, ...]:
    """`count` etiketin tabaka ve hücreleri: ilk tabaka `start_cell`'den başlar.

    Örnek (65'li tabaka, başlangıç 60): 1.-6. etiket 1. tabakanın 60.-65.
    hücresine, 7. etiket 2. tabakanın 1. hücresine düşer.
    """
    validate_start_cell(start_cell, capacity)
    ilk = start_cell - 1
    return tuple(
        Placement(
            item_index=sira, sheet=(ilk + sira) // capacity, cell_index=(ilk + sira) % capacity
        )
        for sira in range(count)
    )


def sheet_count(count: int, *, capacity: int, start_cell: int = 1) -> int:
    """Basım için gereken tabaka sayısı (etiket yoksa 0)."""
    if count <= 0:
        return 0
    validate_start_cell(start_cell, capacity)
    return (start_cell - 1 + count - 1) // capacity + 1


def snap_to_module(value_mm: float, module_mm: float = barcode128.DEFAULT_MODULE_MM) -> float:
    """Sayfadaki konumu en yakın modül katına çeker (yazıcı nokta ızgarası)."""
    return round(value_mm / module_mm) * module_mm
