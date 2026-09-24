"""Etiket metninin genişlik ölçümü ve Türkçe güvenli kırpma (tasarım §7.2, F4).

**Neden Python'da ölçülüyor.** Etiketteki her metin satırı TEK satırdır ve
hücreden taşmamalıdır (eser adı, yer numarası, kısa okul adı). WeasyPrint'in
`overflow: hidden` kırpması son güvencedir, ama kırpılmış bir metin yarım harfle
biter ve kullanıcı "…" görmeden bilginin kesildiğini anlamaz. Bu yüzden metin
ŞABLONA girmeden önce burada ölçülür, gerekirse yazı boyu küçültülür ve en son
çare olarak sözcük sınırından "…" ile kısaltılır.

**Ölçü kaynağı.** Aşağıdaki tablolar DejaVu Sans ve DejaVu Sans Bold 2.37
yazı tiplerinin `hmtx` ilerleme genişlikleridir (font birimi; 2048 = 1 em).
Evrakın tek yazı tipi gömülü DejaVu'dur (CLAUDE.md §1, `shared/pdf.py`);
etiket şablonu çekirdek aralığı (`font-kerning: none`,
`font-variant-ligatures: none`) kapatır, yani PDF'teki satır genişliği tam
olarak ilerleme genişliklerinin toplamıdır. Tablo `fontTools` ile
`/usr/share/fonts/truetype/dejavu/` dosyalarından üretildi; koruma testi
(`tests/test_etiket_metin.py`) her değeri gerçek yazı tipi dosyasıyla
karşılaştırır, PDF testi (`tests/test_etiket_pdf.py`) basılı satırların hücre
içinde kaldığını PDF'in kendi genişlik tablosundan ölçer.

Kapsam: ASCII, Latin-1 eki ve Latin Genişletilmiş-A (Türkçenin bütün harfleri,
düzeltme işaretli â/î/û dahil) + tipografik tırnak, tire, madde imi ve üç nokta.
Tabloda olmayan karakter 1 em sayılır (DejaVu'daki en geniş harfler 1 em'e
yakındır; ihtiyatlı taraf), birleşen işaretler (U+0300…) sıfır sayılır.

**Türkçe güvenli kırpma** (`fit_text`):

- Metin NFC'ye çevrilir; denetim ve görünmez biçim karakterleri (yumuşak tire,
  sıfır genişlikli boşluk) atılır, boşluklar teke indirilir.
- Kesme noktası birleşen bir işaretin önüne düşmez: "i̇" gibi taban harf +
  birleşen nokta çifti bölünmez.
- Harf büyüklüğü DEĞİŞMEZ (çıplak `.upper()` 'i'yi 'I' basardı — CLAUDE.md
  §2-9); kırpma yalnız karakter atar.
- Kesme, sığan kısmın son %40'ı içinde bir boşluk varsa sözcük sınırından
  yapılır; sondaki boşluk ve noktalama atılır, "…" eklenir.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

#: DejaVu Sans'ın em karesi (font birimi).
UNITS_PER_EM = 2048
#: DejaVu Sans `hhea` yükseklikleri (font birimi): taban çizgisinin üstü ve altı.
ASCENDER = 1901
DESCENDER = 483
#: Tipografik nokta → mm (1 pt = 1/72 inç).
MM_PER_PT = 25.4 / 72
#: Kırpmada eklenen işaret (U+2026, tek karakter).
ELLIPSIS = "…"
#: Sözcük sınırından kesme için sığan kısmın ne kadarının korunacağı.
WORD_BOUNDARY_KEEP = 0.6
#: Kırpılmış metnin sonundan atılan işaretler ("Kitap, …" değil "Kitap…").
_TRAILING_STRIP = " ,;:.-–—/(‘“"
#: Tabloda olmayan karakterin ihtiyatlı genişliği (1 em).
_FALLBACK_WIDTH = UNITS_PER_EM

# DejaVu Sans 2.37 ilerleme genişlikleri (font birimi) — (aralık başı, genişlikler).
# Yumuşak tire (U+00AD) sıfırdır: `clean_text` onu zaten atar, Pango da çizmez.
_REGULAR: tuple[tuple[int, tuple[int, ...]], ...] = (
    (
        0x0020,
        (
            651, 821, 942, 1716, 1303, 1946, 1597, 563, 799, 799, 1024, 1716, 651, 739, 651, 690,
            1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 1303, 690, 690, 1716, 1716, 1716,
            1087, 2048, 1401, 1405, 1430, 1577, 1294, 1178, 1587, 1540, 604, 604, 1343, 1141, 1767,
            1532, 1612, 1235, 1612, 1423, 1300, 1251, 1499, 1401, 2025, 1403, 1251, 1403, 799, 690,
            799, 1716, 1024, 1024, 1255, 1300, 1126, 1300, 1260, 721, 1300, 1298, 569, 569, 1186, 569,
            1995, 1298, 1253, 1300, 1300, 842, 1067, 803, 1298, 1212, 1675, 1212, 1212, 1075, 1303,
            690, 1303, 1716,
        ),
    ),
    (
        0x00A0,
        (
            651, 821, 1303, 1303, 1303, 1303, 690, 1024, 1024, 2048, 965, 1253, 1716, 0, 2048, 1024,
            1024, 1716, 821, 821, 1024, 1303, 1303, 651, 1024, 821, 965, 1253, 1985, 1985, 1985, 1087,
            1401, 1401, 1401, 1401, 1401, 1401, 1995, 1430, 1294, 1294, 1294, 1294, 604, 604, 604,
            604, 1587, 1532, 1612, 1612, 1612, 1612, 1612, 1716, 1612, 1499, 1499, 1499, 1499, 1251,
            1239, 1290, 1255, 1255, 1255, 1255, 1255, 1255, 2011, 1126, 1260, 1260, 1260, 1260, 569,
            569, 569, 569, 1253, 1298, 1253, 1253, 1253, 1253, 1253, 1716, 1253, 1298, 1298, 1298,
            1298, 1212, 1300, 1212, 1401, 1255, 1401, 1255, 1401, 1255, 1430, 1126, 1430, 1126, 1430,
            1126, 1430, 1126, 1577, 1300, 1587, 1300, 1294, 1260, 1294, 1260, 1294, 1260, 1294, 1260,
            1294, 1260, 1587, 1300, 1587, 1300, 1587, 1300, 1587, 1300, 1540, 1298, 1876, 1423, 604,
            569, 604, 569, 604, 569, 604, 569, 604, 569, 1208, 1138, 604, 569, 1343, 1186, 1186, 1141,
            569, 1141, 569, 1141, 768, 1141, 700, 1151, 582, 1532, 1298, 1532, 1298, 1532, 1298, 1666,
            1532, 1298, 1612, 1253, 1612, 1253, 1612, 1253, 2191, 2095, 1423, 842, 1423, 842, 1423,
            842, 1300, 1067, 1300, 1067, 1300, 1067, 1300, 1067, 1251, 803, 1251, 803, 1251, 803,
            1499, 1298, 1499, 1298, 1499, 1298, 1499, 1298, 1499, 1298, 1499, 1298, 2025, 1675, 1251,
            1212, 1251, 1403, 1075, 1403, 1075, 1403, 1075, 721,
        ),
    ),
    (
        0x2013,
        (
            1024, 2048,
        ),
    ),
    (
        0x2018,
        (
            651, 651,
        ),
    ),
    (
        0x201C,
        (
            1061, 1061,
        ),
    ),
    (
        0x2022,
        (
            1208,
        ),
    ),
    (
        0x2026,
        (
            2048,
        ),
    ),
)  # fmt: skip
_BOLD: tuple[tuple[int, tuple[int, ...]], ...] = (
    (
        0x0020,
        (
            713, 934, 1067, 1716, 1425, 2052, 1786, 627, 936, 936, 1071, 1716, 778, 850, 778, 748,
            1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 1425, 819, 819, 1716, 1716, 1716,
            1188, 2048, 1585, 1561, 1503, 1700, 1399, 1399, 1681, 1714, 762, 762, 1587, 1305, 2038,
            1714, 1741, 1501, 1741, 1577, 1475, 1397, 1663, 1585, 2259, 1579, 1483, 1485, 936, 748,
            936, 1716, 1024, 1024, 1382, 1466, 1214, 1466, 1389, 891, 1466, 1458, 702, 702, 1362, 702,
            2134, 1458, 1407, 1466, 1466, 1010, 1219, 979, 1458, 1335, 1892, 1321, 1335, 1192, 1458,
            748, 1458, 1716,
        ),
    ),
    (
        0x00A0,
        (
            713, 934, 1425, 1425, 1303, 1425, 748, 1024, 1024, 2048, 1155, 1323, 1716, 0, 2048, 1024,
            1024, 1716, 897, 897, 1024, 1507, 1303, 778, 1024, 897, 1155, 1323, 2120, 2120, 2120,
            1188, 1585, 1585, 1585, 1585, 1585, 1585, 2222, 1503, 1399, 1399, 1399, 1399, 762, 762,
            762, 762, 1716, 1714, 1741, 1741, 1741, 1741, 1741, 1716, 1741, 1663, 1663, 1663, 1663,
            1483, 1511, 1473, 1382, 1382, 1382, 1382, 1382, 1382, 2146, 1214, 1389, 1389, 1389, 1389,
            702, 702, 702, 702, 1407, 1458, 1407, 1407, 1407, 1407, 1407, 1716, 1407, 1458, 1458,
            1458, 1458, 1335, 1466, 1335, 1585, 1382, 1585, 1382, 1585, 1382, 1503, 1214, 1503, 1214,
            1503, 1214, 1503, 1214, 1700, 1466, 1716, 1466, 1399, 1389, 1399, 1389, 1399, 1389, 1399,
            1389, 1399, 1389, 1681, 1466, 1681, 1466, 1681, 1466, 1681, 1466, 1714, 1458, 1994, 1618,
            762, 702, 762, 702, 762, 702, 762, 702, 762, 702, 1524, 1404, 762, 702, 1587, 1362, 1362,
            1305, 702, 1305, 702, 1305, 982, 1305, 1140, 1315, 760, 1714, 1458, 1714, 1458, 1714,
            1458, 2013, 1714, 1458, 1741, 1407, 1741, 1407, 1741, 1407, 2390, 2241, 1577, 1010, 1577,
            1010, 1577, 1010, 1475, 1219, 1475, 1219, 1475, 1219, 1475, 1219, 1397, 979, 1397, 979,
            1397, 979, 1663, 1458, 1663, 1458, 1663, 1458, 1663, 1458, 1663, 1458, 1663, 1458, 2259,
            1892, 1483, 1335, 1483, 1485, 1192, 1485, 1192, 1485, 1192, 891,
        ),
    ),
    (
        0x2013,
        (
            1024, 2048,
        ),
    ),
    (
        0x2018,
        (
            778, 778,
        ),
    ),
    (
        0x201C,
        (
            1346, 1346,
        ),
    ),
    (
        0x2022,
        (
            1309,
        ),
    ),
    (
        0x2026,
        (
            2048,
        ),
    ),
)  # fmt: skip


def _build_table(ranges: tuple[tuple[int, tuple[int, ...]], ...]) -> dict[int, int]:
    return {start + i: width for start, widths in ranges for i, width in enumerate(widths)}


REGULAR_WIDTHS: dict[int, int] = _build_table(_REGULAR)
BOLD_WIDTHS: dict[int, int] = _build_table(_BOLD)


def clean_text(value: object) -> str:
    """Etikete girecek metni sadeleştirir (NFC, görünmez karakter yok, tek boşluk).

    Denetim (Cc) ve biçim (Cf) karakterleri atılır: yumuşak tire (U+00AD),
    sıfır genişlikli boşluk ve yön işaretleri PDF'te ya görünmez ya da ölçüyü
    bozar. Satır sonu, sekme ve bölünmez boşluk sıradan boşluğa döner.
    """
    metin = unicodedata.normalize("NFC", "" if value is None else str(value))
    parcalar: list[str] = []
    for ch in metin:
        if ch.isspace():
            parcalar.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            continue
        else:
            parcalar.append(ch)
    return " ".join("".join(parcalar).split())


def char_units(ch: str, *, bold: bool = False) -> int:
    """Tek karakterin ilerleme genişliği (font birimi)."""
    tablo = BOLD_WIDTHS if bold else REGULAR_WIDTHS
    genislik = tablo.get(ord(ch))
    if genislik is not None:
        return genislik
    if unicodedata.combining(ch):
        return 0
    return _FALLBACK_WIDTH


@lru_cache(maxsize=4096)
def _text_units(text: str, bold: bool) -> int:
    return sum(char_units(ch, bold=bold) for ch in text)


def text_width_mm(text: str, size_pt: float, *, bold: bool = False) -> float:
    """Metnin basılı genişliği (mm) — çekirdek aralığı kapalıyken tam değer."""
    return _text_units(text, bold) / UNITS_PER_EM * size_pt * MM_PER_PT


def fits(text: str, max_width_mm: float, size_pt: float, *, bold: bool = False) -> bool:
    return text_width_mm(text, size_pt, bold=bold) <= max_width_mm


def _safe_cut(text: str, cut: int) -> int:
    """Kesme noktasını birleşen işaretin önünden geri çeker ("i̇" bölünmez)."""
    while 0 < cut < len(text) and unicodedata.combining(text[cut]):
        cut -= 1
    return cut


def fit_text(value: object, max_width_mm: float, size_pt: float, *, bold: bool = False) -> str:
    """Metni tek satıra sığdırır; sığmıyorsa Türkçe güvenli biçimde "…" ile kısaltır.

    Dönen metin `max_width_mm` genişliğini AŞMAZ (üç nokta dahil). Hiçbir
    karakter sığmıyorsa yalnız "…" döner; o da sığmıyorsa boş dize.
    """
    metin = clean_text(value)
    if fits(metin, max_width_mm, size_pt, bold=bold):
        return metin
    ucnokta = text_width_mm(ELLIPSIS, size_pt, bold=bold)
    if ucnokta > max_width_mm:
        return ""
    butce = max_width_mm - ucnokta
    kesme = 0
    toplam = 0.0
    birim = size_pt * MM_PER_PT / UNITS_PER_EM
    for sira, ch in enumerate(metin):
        toplam += char_units(ch, bold=bold) * birim
        if toplam > butce:
            break
        kesme = sira + 1
    kesme = _safe_cut(metin, kesme)
    onek = metin[:kesme]
    bosluk = onek.rfind(" ")
    if bosluk > 0 and bosluk >= int(len(onek) * WORD_BOUNDARY_KEEP):
        onek = onek[:bosluk]
    onek = onek.rstrip(_TRAILING_STRIP)
    return f"{onek}{ELLIPSIS}"


def largest_fitting_size(
    lines: list[str],
    max_width_mm: float,
    sizes_pt: tuple[float, ...],
    *,
    bold: bool = False,
) -> float | None:
    """Bütün satırların sığdığı en büyük yazı boyu (`sizes_pt` büyükten küçüğe); yoksa None."""
    for boy in sizes_pt:
        if all(fits(satir, max_width_mm, boy, bold=bold) for satir in lines):
            return boy
    return None
