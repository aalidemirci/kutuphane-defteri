"""Code128-C barkod üreteci — bağımlılıksız (tasarım T8, §7.1-7.2).

Neden yalnız C alt kümesi: barkod şeması salt rakamdır (nüsha 10 hane, üye kartı
8 hane; §7.1). TR-Q klavyede okuyucunun "-" karakteri "*" olur ve harfli
kodlarda ı/i karışır; rakam bu iki sorunu ortadan kaldırır (T8). Code128-C her
iki rakamı tek sembolde (00-99) kodlar; bu yüzden **çift uzunluk şarttır**. Tek
uzunluk A/B alt kümesine geçiş isterdi ve şemamızda yoktur → `ValueError`.

Sembol dizisi: START-C (105) + rakam çiftleri + sağlama + STOP (106).

- Sağlama: ``(105 + Σ i·v_i) mod 103``; ``i`` birden başlayan konum, ``v_i``
  i'nci çiftin değeridir (ISO/IEC 15417 ağırlıklı mod-103).
- Her sembol 11 modüldür (3 bar + 3 boşluk); STOP 13 modüldür (4 bar + 3 boşluk).
  Modül sayısı: ``11 + 11·(n/2) + 11 + 13``. 10 hane → **90**, 8 hane → **79**.
- Sessiz bölge her iki yanda **10X**: 10 hane 110, 8 hane 99 modül (§7.2).

Modül genişliği varsayılanı **X = 0,254 mm**: yazıcı noktasına hizalıdır (300
dpi'de 3 nokta, 600 dpi'de 6; CLAUDE.md "WeasyPrint ölçü tuzakları"). 10 haneli
nüsha barkodu sessiz bölgelerle 27,94 mm eder.

Bütün fonksiyonlar saftır: girdi dışında hiçbir şeye bakmaz, yan etkisi yoktur.
Hata iletileri girdinin kendisini BASMAZ: kart no şifreli alandır (§6.3) ve bir
istisna iletisi günlüğe düşebilir.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

START_C = 105
STOP = 106
CHECKSUM_MODULUS = 103
#: Standardın asgari sessiz bölgesi (her iki yanda, modül cinsinden).
QUIET_ZONE_MODULES = 10
#: Yazıcı noktasına hizalı modül genişliği (tasarım §7.2).
DEFAULT_MODULE_MM = 0.254
#: Çubuk yüksekliği varsayılanı. Etiket düzeni (F4) kendi ölçüsünü verir; bu
#: değer yalnız ölçü verilmeyen çağrılar içindir.
DEFAULT_HEIGHT_MM = 8.0

#: Code128 desen tablosu: değer → eleman genişlikleri (bar, boşluk, bar, ...;
#: modül cinsinden). 0-102 veri/komut sembolleri, 103-105 START-A/B/C, 106 STOP.
#: Tablonun bütünlüğü (toplam 11 modül, çift bar modülü, teklik) testte sabitlenir.
PATTERNS: tuple[str, ...] = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112",
    "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412",
    "211214", "211232", "2331112",
)  # fmt: skip

# `[0-9]` bilinçli: `str.isdigit()` "²" ve Arap-Hint rakamlarını da kabul ederdi.
_DIGITS = re.compile(r"[0-9]+")


def _validate_digits(digits: str) -> None:
    """Girdi Code128-C ile kodlanabilir mi; değilse `ValueError` (değeri basmadan)."""
    if not digits:
        raise ValueError("Barkod boş olamaz.")
    if _DIGITS.fullmatch(digits) is None:
        raise ValueError("Code128-C yalnız rakam (0-9) kodlar; barkodda başka karakter var.")
    if len(digits) % 2:
        raise ValueError(f"Code128-C çift sayıda rakam ister; verilen barkod {len(digits)} haneli.")


def checksum(data_values: Sequence[int]) -> int:
    """Ağırlıklı mod-103 sağlaması: START-C değeri + Σ konum × değer."""
    total = START_C + sum(position * value for position, value in enumerate(data_values, 1))
    return total % CHECKSUM_MODULUS


def encode_values(digits: str) -> tuple[int, ...]:
    """Sembol değerleri: (START-C, çiftler..., sağlama, STOP)."""
    _validate_digits(digits)
    data = [int(digits[index : index + 2]) for index in range(0, len(digits), 2)]
    return (START_C, *data, checksum(data), STOP)


def element_widths(digits: str) -> tuple[int, ...]:
    """Bar/boşluk genişlik dizisi (modül cinsinden, sessiz bölgesiz).

    Dizi bar ile başlar ve bar ile biter; çift indeksler bar, tek indeksler
    boşluktur. Her 11 modüllük sembol boşlukla bittiği için sıra semboller
    arasında da korunur.
    """
    return tuple(int(width) for value in encode_values(digits) for width in PATTERNS[value])


def module_pattern(digits: str) -> str:
    """Modül dizisi: bar ``1``, boşluk ``0`` (sessiz bölgesiz; test ve teşhis içindir)."""
    return "".join(
        ("1" if index % 2 == 0 else "0") * width
        for index, width in enumerate(element_widths(digits))
    )


def module_count(digits: str, *, quiet_zone: bool = True) -> int:
    """Toplam modül sayısı; `quiet_zone` iken iki yandaki 10X sessiz bölge dahil."""
    symbol = sum(element_widths(digits))
    return symbol + 2 * QUIET_ZONE_MODULES if quiet_zone else symbol


def bar_spans(
    digits: str, *, quiet_zone_modules: int = QUIET_ZONE_MODULES
) -> tuple[tuple[int, int], ...]:
    """Barların (başlangıç modülü, genişlik) listesi; konumlar sessiz bölge dahil."""
    _validate_quiet_zone(quiet_zone_modules)
    spans: list[tuple[int, int]] = []
    cursor = quiet_zone_modules
    for index, width in enumerate(element_widths(digits)):
        if index % 2 == 0:
            spans.append((cursor, width))
        cursor += width
    return tuple(spans)


def _validate_quiet_zone(quiet_zone_modules: int) -> None:
    if quiet_zone_modules < QUIET_ZONE_MODULES:
        raise ValueError(
            f"Sessiz bölge en az {QUIET_ZONE_MODULES} modül olmalı "
            f"(verilen: {quiet_zone_modules}); dar sessiz bölgede okuyucu barkodu bulamaz."
        )


def _validate_length_mm(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} sıfırdan büyük bir sayı olmalı (verilen: {value!r}).")


def _mm(value: float) -> str:
    """SVG sayısı: dört ondalığa yuvarlanır, gereksiz sıfırlar atılır (27.9400 → 27.94)."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def svg(
    digits: str,
    *,
    module_mm: float = DEFAULT_MODULE_MM,
    height_mm: float = DEFAULT_HEIGHT_MM,
    quiet_zone_modules: int = QUIET_ZONE_MODULES,
) -> str:
    """Barkodu mm ölçülü, bağımsız bir SVG belgesi olarak döndürür.

    Kullanıcı birimi milimetredir (`viewBox` genişliği = `width` mm): basımda
    her bar ``genişlik × module_mm`` olur, ölçekleme yoktur. Arka plan beyaz
    dikdörtgendir; sessiz bölgenin açık renkte kalmasını belge düzeninden
    bağımsız kılar. Okunur metin SVG'ye girmez, etiket şablonunun işidir.
    """
    _validate_length_mm("Modül genişliği", module_mm)
    _validate_length_mm("Yükseklik", height_mm)
    spans = bar_spans(digits, quiet_zone_modules=quiet_zone_modules)
    total_modules = sum(element_widths(digits)) + 2 * quiet_zone_modules
    width = _mm(total_modules * module_mm)
    height = _mm(height_mm)
    bars = "".join(
        f'<rect x="{_mm(start * module_mm)}" width="{_mm(span * module_mm)}" height="{height}"/>'
        for start, span in spans
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {height}" shape-rendering="crispEdges">'
        f'<rect width="{width}" height="{height}" fill="#fff"/>'
        f'<g fill="#000">{bars}</g>'
        "</svg>"
    )
