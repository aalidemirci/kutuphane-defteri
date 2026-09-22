"""Personel Excel'ini okuma: başlık tespiti, esnek sütun eşleme, satır ayrıştırma.

OYS `apps/core/excel_personel.py` dosyasından SADELEŞTİRİLEREK alındı: e-posta ve
Rol/Kapsam çiftleri KALDIRILDI — programda personel hesabı yoktur. Fuzzy başlık
eşleme kalıbı (excel_ogrenci deseni) aynen korunur.

UNVAN VE BRANŞ SAKLANMAZ (tasarım §6.1, V2-01): bir branşta çoğu zaman 1-3
öğretmen olduğundan branş, öğretmenin okuma geçmişini kişiye bağlar. Bu yüzden:

- **Branş sütunu hiç okunmaz** — eşleme sözlüğünde karşılığı yoktur.
- **"Görevi/Unvan" sütunu** (ya da şablondaki "Üye Türü") YALNIZ üye türünü
  (öğretmen / diğer personel) seçmek için satır ayrıştırılırken geçici okunur.
  Metin `ParsedPersonnelRow`'a GİRMEZ; yalnız sınıflama sonucu girer, dolayısıyla
  rapora, `ImportRun.report`'a ve günlüğe de ulaşamaz. (Tasarım §6.1'in "bu
  sütunları okumaz" ifadesinden bilinçli, küçük sapma: saklanan veri aynıdır —
  F1 eki.)

Şablon: | Adı | Soyadı | Üye Türü |. e-Okul OOK01001R1: | ADI SOYADI | GÖREVİ | … |.
Eski birleşik ``Ad Soyad`` biçimi de geriye uyum için kabul edilir.
DB yazımı `services/imports.py`'dadır (saf modül — DB'siz, test edilebilir).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.okul import normalize
from apps.okul.excel_ogrenci import ParserError, normalize_header, read_sheet

#: `models.MemberKind` değerleri (modül Django'suz kalsın diye düz metin; eşitliği
#: `tests/test_excel_personel_parser.py` sabitler).
KIND_TEACHER = "TEACHER"
KIND_STAFF = "STAFF"

# Mantıksal alan → normalize edilmiş başlık anahtar kelimeleri (ilk eşleşen kazanır).
# "role" sütununun METNİ saklanmaz; yalnız `classify_member_kind` sonucuna dönüşür.
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "full_name": ["ad soyad", "adi soyadi", "ad ve soyad", "adsoyad", "ad soyadi", "isim"],
    "last_name": ["personel soyadi", "soyadi"],
    "first_name": ["personel adi", "adi"],
    "role": ["uye turu", "unvan", "gorev", "gorevi"],
}

#: Öğretmen sayılan görevler (kelime başı eşleşmesi; ASCII'ye katlanmış metinde).
#: Okul yöneticileri (müdür, müdür yardımcısı) öğretmen kökenlidir; rehberlik
#: servisi (rehber öğretmen, psikolojik danışman) ve usta öğretici de öğretmendir.
_TEACHER_KEYWORDS: tuple[str, ...] = (
    "ogretmen",
    "ogretici",
    "mudur",
    "rehber",
    "danisman",
)

#: Diğer personel sayılan görevler.
_STAFF_KEYWORDS: tuple[str, ...] = (
    "memur",
    "hizmetli",
    "teknisyen",
    "tekniker",
    "asci",
    "bekci",
    "sef",
    "sekreter",
    "sofor",
    "isci",
    "kalorifer",
    "temizlik",
    "guvenlik",
    "muhasebe",
    "ambar",
    "laborant",
    "isletmen",
    "personel",
    "diger",
)


def classify_member_kind(value: Any) -> str | None:
    """Görev metninden üye türü: `KIND_TEACHER`, `KIND_STAFF` ya da tanınmadıysa None.

    Anahtar kelimeler kelime BAŞINDAN eşleşir ("müdürü", "memuru" de tanınır).
    Öğretmen anahtarı önceliklidir ("Rehber Öğretmen", "Müdür Yardımcısı").
    Boş ya da tanınmayan metin None döner — çağıran öğretmen varsayar ve
    önizlemede "Üye türünü denetleyin" uyarısı verir. Metnin kendisi hiçbir yere
    yazılmaz.
    """
    kelimeler = normalize_header(value).split()
    if not kelimeler:
        return None

    def _var(anahtarlar: tuple[str, ...]) -> bool:
        return any(k.startswith(a) for k in kelimeler for a in anahtarlar)

    if _var(_TEACHER_KEYWORDS):
        return KIND_TEACHER
    if _var(_STAFF_KEYWORDS):
        return KIND_STAFF
    return None


@dataclass
class PersonnelColumnMapping:
    """Tespit edilen başlık satırı ve alan → kolon indeksi eşlemesi."""

    header_row: int
    fields: dict[str, int] = field(default_factory=dict)
    matched_headers: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def missing_critical(self) -> list[str]:
        has_combined_name = "full_name" in self.fields
        has_split_name = "first_name" in self.fields and "last_name" in self.fields
        return (
            [] if has_combined_name or has_split_name else ["full_name veya first_name+last_name"]
        )

    @property
    def is_usable(self) -> bool:
        return not self.missing_critical


@dataclass
class ParsedPersonnelRow:
    """Bir personel satırının çözümlenmiş hâli. Görev METNİ BURADA YOKTUR."""

    row_number: int  # 1-tabanlı Excel satır no
    raw_full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    #: Görev sütunundan çıkarılan üye türü; sütun yoksa ya da tanınmadıysa None.
    member_kind: str | None = None
    #: Görev sütunu VAR ama bu satırın görevi tanınmadı (boş hücre dahil).
    member_kind_unrecognized: bool = False


def _str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _match_field_for_header(norm: str) -> str | None:
    for fieldname, keywords in COLUMN_SYNONYMS.items():
        for kw in keywords:
            if kw == norm or kw in norm:
                return fieldname
    return None


def _map_header_row(cells: list[Any]) -> tuple[dict[str, int], dict[str, str], list[str]]:
    fields: dict[str, int] = {}
    matched: dict[str, str] = {}
    warnings: list[str] = []
    for idx, cell in enumerate(cells):
        norm = normalize_header(cell)
        if not norm:
            continue
        fieldname = _match_field_for_header(norm)
        if fieldname is None:
            continue
        if fieldname in fields:
            warnings.append(
                f"'{cell}' sütunu '{fieldname}' için yinelenen eşleşme; ilki kullanıldı."
            )
            continue
        fields[fieldname] = idx
        matched[fieldname] = str(cell).strip()
    return fields, matched, warnings


def detect_columns(rows: list[list[Any]], scan_limit: int = 10) -> PersonnelColumnMapping:
    """İlk satırlar içinde en iyi başlık satırını bulur ve sütunları eşler."""
    best: PersonnelColumnMapping | None = None
    for r in range(min(scan_limit, len(rows))):
        cells = rows[r]
        if all(c is None or str(c).strip() == "" for c in cells):
            continue
        fields, matched, warnings = _map_header_row(cells)
        if not fields:
            continue
        candidate = PersonnelColumnMapping(
            header_row=r, fields=fields, matched_headers=matched, warnings=warnings
        )
        if best is None or (candidate.is_usable, len(candidate.fields)) > (
            best.is_usable,
            len(best.fields),
        ):
            best = candidate
        if best.is_usable and best.header_row == r:
            break
    return best or PersonnelColumnMapping(header_row=0)


def _cell(cells: list[Any], idx: int | None) -> Any:
    if idx is None or idx >= len(cells):
        return None
    return cells[idx]


def parse_rows(rows: list[list[Any]], mapping: PersonnelColumnMapping) -> list[ParsedPersonnelRow]:
    """Başlık satırından sonraki veri satırlarını çözümler (boş satırlar atlanır)."""
    f = mapping.fields
    has_role = "role" in f
    parsed: list[ParsedPersonnelRow] = []
    for r in range(mapping.header_row + 1, len(rows)):
        cells = rows[r]
        if all(c is None or str(c).strip() == "" for c in cells):
            continue

        raw_name = _str(_cell(cells, f.get("full_name")))
        if raw_name:
            first, last = normalize.split_full_name(raw_name)
        else:
            first = _str(_cell(cells, f.get("first_name")))
            last = _str(_cell(cells, f.get("last_name")))
            raw_name = f"{first} {last}".strip()
        # Görev metni yalnız bu satırda, sınıflama için okunur; değişkene bile alınmaz.
        kind = classify_member_kind(_cell(cells, f.get("role"))) if has_role else None
        parsed.append(
            ParsedPersonnelRow(
                row_number=r + 1,
                raw_full_name=raw_name,
                first_name=first,
                last_name=last,
                member_kind=kind,
                member_kind_unrecognized=has_role and kind is None,
            )
        )
    return parsed


def parse_workbook(file_bytes: bytes) -> tuple[PersonnelColumnMapping, list[ParsedPersonnelRow]]:
    """Baytlardan (mapping, satırlar) üretir; kritik sütun yoksa ParserError."""
    grid = read_sheet(file_bytes)
    mapping = detect_columns(grid)
    if not mapping.is_usable:
        eksik = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {eksik}.")
    return mapping, parse_rows(grid, mapping)


# read_sheet excel_ogrenci'den yeniden kullanılır (etkin sayfa, salt-okunur).
__all__ = [
    "KIND_STAFF",
    "KIND_TEACHER",
    "ParsedPersonnelRow",
    "PersonnelColumnMapping",
    "classify_member_kind",
    "detect_columns",
    "parse_rows",
    "parse_workbook",
    "read_sheet",
]
