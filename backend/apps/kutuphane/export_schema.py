"""Dışa aktarım şeması — TEK kaynak (tasarım §8.4, U1; `docs/disa-aktarim.md`).

Dışa aktarım birinci sınıf bir özelliktir (tasarım §3 "Program nasıl konumlanır" 2):
okul, kataloğunu programın dışına her zaman bu dosyayla çıkarabilir (çıkış planı —
Bakanlık otomasyon sistemine ya da başka bir araca geçiş) ve aynı dosyayla boş bir
kuruluma geri yükleyebilir. Şema **tek ve sürümlüdür**: sütunların sırası, başlığı ve
değer kuralları burada tanımlanır; `disa_aktarim.py` dosyayı üretir,
`services.export_import` okur, `docs/disa-aktarim.md` kullanıcıya anlatır ve test üçünün
birebir aynı olduğunu denetler.

**İçe aktarım sözlüğünün ÜST KÜMESİDİR** (§8.4): "Katalog" sayfasının ilk sütunları
`import_schema.COLUMNS`'un aynı başlıklarla, aynı sırayla yazılmış hâlidir (başka bir araç
dosyayı içe aktarım sözlüğüyle okuyabilir). Programın kendi olağan "Excel listesi" yolu ise
dosyayı "Bilgi" sayfasından TANIR ve reddeder (F10 düzeltme turu): numaralar yeniden
verilir, eski etiket başka kitabı açar, kayıttan çıkmış nüsha "Rafta" açılırdı — geri
yükleme yalnız "dışa aktarım dosyası" kipindedir (`services.export_import`). Ek sütunlar
(`EXTRA_COLUMNS`): eser no, barkod, kayıt no, TKYS kodu, durum, edinim yolu ve tarihi,
birim fiyat, komisyon kararının tarihi ve sayısı, kayıttan çıkış tarihi, bütün
bayraklar, sınıflama kaynağı, yer numarası, eserin bölümü ve etiket işaretleri. Çevirmen,
baskı ve bölüm içe aktarım sözlüğünde zaten vardır.

**Satır düzeni:** her nüsha bir satırdır ("satır başına tek nüsha" kipi — §8.1);
nüshası olmayan eser (e-kitap, e-veri tabanı ya da bütün nüshaları silinmiş eser)
barkodu boş TEK satırla yazılır ("Nüsha Sayısı" 0). Aynı "Eser No"yu taşıyan satırlar
aynı eserin nüshalarıdır; "Eser No" dosya içi sıra numarasıdır, programın iç kimliği
DEĞİLDİR (sözlük §2: iç kimlik yüzeye çıkmaz).

**Kişisel veri YOKTUR** (CLAUDE.md §2-12): üye, ödünç, teslim, kayıp/hasar dosyası,
bağışçı (`Acquisition.source_note`, şifreli) ve komisyon üyelerinin adları dosyaya
girmez. Komisyon kararının yalnız TARİHİ ve SAYISI yazılır (kişi değildir); bağışın
kararı içe aktarımda bu ikisiyle yeniden kurulur.

**Sürüm:** `EXPORT_SCHEMA_VERSION`. Sütun eklenir ya da anlamı değişirse sürüm
yükselir; içe aktarıcı yalnız tanıdığı sürümü okur (`SUPPORTED_VERSIONS`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from apps.kutuphane import import_schema
from apps.kutuphane.import_schema import CatalogColumn
from apps.kutuphane.models import (
    AcquisitionMethod,
    ClassificationSource,
    CopyStatus,
    ResourceType,
)

#: Şema sürümü (dosyanın "Bilgi" sayfasında yazar; `CatalogImportRun.schema_version`).
EXPORT_SCHEMA_VERSION: Final = "v1"
#: İçe aktarıcının okuduğu sürümler.
SUPPORTED_VERSIONS: Final[tuple[str, ...]] = (EXPORT_SCHEMA_VERSION,)
#: "Bilgi" sayfasındaki dosya türü — içe aktarıcı dosyayı bununla tanır.
EXPORT_FILE_KIND: Final = "Kütüphane Defteri dışa aktarım dosyası"
#: Belgenin adı (ekran kartı ve indirilen dosyanın adı — sözlük §3).
EXPORT_DOCUMENT_NAME: Final = "Katalog dışa aktarımı"

# ---------------------------------------------------------------------------
# Sayfalar
# ---------------------------------------------------------------------------
INFO_SHEET: Final = "Bilgi"
#: Olağan içe aktarımın okuduğu adla AYNIDIR (üst küme ilkesi; olağan yol dosyayı yine de
#: "Bilgi" sayfasından tanıyıp reddeder — F10 düzeltme turu).
CATALOG_SHEET: Final = import_schema.CATALOG_SHEET
SECTIONS_SHEET: Final = "Bölümler"
COUNTERS_SHEET: Final = "Numara Sayaçları"
MEMBER_SUMMARY_SHEET: Final = "Üye Özeti"
SHEETS: Final[tuple[str, ...]] = (
    INFO_SHEET,
    CATALOG_SHEET,
    SECTIONS_SHEET,
    COUNTERS_SHEET,
    MEMBER_SUMMARY_SHEET,
)

#: "Bilgi" sayfasının etiketleri (A sütunu) — içe aktarıcı bunlarla okur.
INFO_KIND: Final = "Dosya türü"
INFO_VERSION: Final = "Şema sürümü"
INFO_DATE: Final = "Dışa aktarım tarihi"
INFO_SCHOOL: Final = "Okul"
INFO_WORKS: Final = "Eser"
INFO_COPIES: Final = "Nüsha (kayıtta)"
INFO_EXITED: Final = "Nüsha (kayıttan düşülmüş ya da devredilmiş)"

#: "Bilgi" sayfasının açıklama satırları (kullanıcı metni — sözlüğe uyar).
INFO_NOTES: Final[tuple[str, ...]] = (
    "Bu dosya kişisel veri içermez: üye, ödünç, teslim ve kayıp/hasar kayıtları, bağışçı ve "
    "komisyon üyelerinin adları dışa aktarıma girmez.",
    "Her nüsha bir satırdır; aynı “Eser No”yu taşıyan satırlar aynı eserin nüshalarıdır. "
    "Nüshası olmayan eser barkodu boş tek satırla yazılır.",
    "Dosyayı boş bir kuruluma geri yüklemek için: Katalog → İçe Aktarma → “Dışa aktarım "
    "dosyası”. Barkod ve kayıt no korunur, numara sayaçları ilerletilir; hiçbir numara "
    "yeniden kullanılmaz.",
    "“Excel listesi” olarak içe aktarılmaz: program dosyayı bu sayfadan tanır ve “Dışa "
    "aktarım dosyası”nın seçilmesini ister (numaralar yeniden verilir, etiketler başka "
    "kayıtları gösterirdi). Geri yükleme yalnız boş bir kataloga ve bütün satırlarla yapılır.",
)

#: "Bölümler" sayfasının başlıkları (sıra sabittir).
SECTION_HEADERS: Final[tuple[str, ...]] = (
    "Ad",
    "DOS Aralığı Başı",
    "DOS Aralığı Sonu",
    "Kısa Tarif",
    "Sıra",
)
#: "Numara Sayaçları" sayfasının başlıkları.
COUNTER_HEADERS: Final[tuple[str, ...]] = ("Yıl", "Son Numara")


# ---------------------------------------------------------------------------
# Ek sütunlar
# ---------------------------------------------------------------------------
class ExportKind(StrEnum):
    """Ek sütunun değer türü (İngilizce kod; kullanıcıya `accepted_values` gösterilir)."""

    TEXT = "text"
    INTEGER = "integer"
    DATE = "date"
    DECIMAL = "decimal"
    YES_NO = "yes_no"
    CHOICE = "choice"
    BARCODE = "barcode"


@dataclass(frozen=True, slots=True)
class ExportColumn:
    """Ek sütun (içe aktarım sözlüğünde olmayan). Başlık TAM eşleşir, eşanlam yoktur."""

    key: str
    header: str
    kind: ExportKind
    description: str
    choices: tuple[str, ...] = ()

    @property
    def accepted_values(self) -> str:
        if self.kind is ExportKind.YES_NO:
            return " / ".join(import_schema.YES_NO_CHOICES)
        if self.kind is ExportKind.CHOICE:
            return " / ".join(self.choices)
        if self.kind is ExportKind.DATE:
            return "Tarih (gg.aa.yyyy)"
        if self.kind is ExportKind.DECIMAL:
            return "Sayı (kuruşlu)"
        if self.kind is ExportKind.INTEGER:
            return "Tam sayı"
        if self.kind is ExportKind.BARCODE:
            return "10 haneli numara"
        return "Serbest metin"


def _etiketler(secenekler: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    return tuple(str(etiket) for _kod, etiket in secenekler)


#: Kaynak türü: dışa aktarım dijital kaynakları da yazar (içe aktarım sözlüğünün
#: seçenekleri + E-kitap, E-veri tabanı). Model etiketleriyle BİREBİR (sözlük §1).
RESOURCE_TYPE_LABELS: Final[tuple[str, ...]] = _etiketler(ResourceType.choices)
STATUS_LABELS: Final[tuple[str, ...]] = _etiketler(CopyStatus.choices)
METHOD_LABELS: Final[tuple[str, ...]] = _etiketler(AcquisitionMethod.choices)
CLASSIFICATION_SOURCE_LABELS: Final[tuple[str, ...]] = _etiketler(ClassificationSource.choices)

EXTRA_COLUMNS: Final[tuple[ExportColumn, ...]] = (
    ExportColumn(
        "work_no",
        "Eser No",
        ExportKind.INTEGER,
        "Dosya içindeki eser numarası: aynı numarayı taşıyan satırlar aynı eserin "
        "nüshalarıdır. Programın iç kimliği değildir.",
    ),
    ExportColumn(
        "barcode",
        "Barkod",
        ExportKind.BARCODE,
        "Nüshanın 10 haneli barkodu (yıl + altı hane sıra). Nüshası olmayan eserin satırında "
        "boştur. İçe aktarımda korunur; hiçbir numara yeniden kullanılmaz.",
    ),
    ExportColumn(
        "accession_no",
        "Kayıt No",
        ExportKind.INTEGER,
        "Barkodun sayı hâli; Taşınır Kütüphane Defteri dökümünün sıra numarası.",
    ),
    ExportColumn(
        "external_asset_ref",
        "TKYS Kodu",
        ExportKind.TEXT,
        "Taşınır Kayıt ve Yönetim Sistemi'ndeki (TKYS) karşılığı; program doğrulamaz.",
    ),
    ExportColumn(
        "status",
        "Durum",
        ExportKind.CHOICE,
        "Nüshanın durumu. İçe aktarımda “Ödünçte” ve “Sınıf kitaplığında” nüsha “Rafta” "
        "açılır: ödünç ve teslim kayıtları kişisel veri taşıdığı için dosyaya girmez.",
        STATUS_LABELS,
    ),
    ExportColumn(
        "acquisition_method",
        "Edinim Yolu",
        ExportKind.CHOICE,
        "Nüshanın geldiği edinimin yolu.",
        METHOD_LABELS,
    ),
    ExportColumn(
        "acquisition_date",
        "Edinim Tarihi",
        ExportKind.DATE,
        "Edinimin tarihi (giriş tarihi).",
    ),
    ExportColumn(
        "unit_price",
        "Birim Fiyat",
        ExportKind.DECIMAL,
        "Edinimin birim fiyatı (TL); bilinmiyorsa boş. Bedelsiz girişte 0.",
    ),
    ExportColumn(
        "decision_date",
        "Komisyon Kararı Tarihi",
        ExportKind.DATE,
        "Edinim bir Seçim ve Ayıklama Komisyonu kararına bağlıysa kararın tarihi. Bağışta "
        "zorunludur (Okul Kütüphaneleri Yönetmeliği Md. 10/3).",
    ),
    ExportColumn(
        "decision_no",
        "Komisyon Kararı Sayısı",
        ExportKind.TEXT,
        "Aynı kararın sayısı. Komisyon üyelerinin adları dosyaya girmez.",
    ),
    ExportColumn(
        "exit_date",
        "Kayıttan Çıkış Tarihi",
        ExportKind.DATE,
        "Kayıttan düşülmüş ya da devredilmiş nüshada harcama yetkilisinin onay tarihi; "
        "öbür nüshalarda boş.",
    ),
    ExportColumn(
        "is_out_of_print",
        "Piyasada Mevcudu Yok",
        ExportKind.YES_NO,
        "“Evet” yazılan nüsha ödünç verilmez (Okul Kütüphaneleri Yönetmeliği Md. 16/1-b).",
    ),
    ExportColumn(
        "is_rare_or_manuscript",
        "El Yazması / Nadir Eser",
        ExportKind.YES_NO,
        "Nüshanın el yazması ya da nadir eser işareti (Md. 12/2).",
    ),
    ExportColumn(
        "classification_source",
        "Sınıflama Kaynağı",
        ExportKind.CHOICE,
        "Sınıflama kodunun nereden geldiği.",
        CLASSIFICATION_SOURCE_LABELS,
    ),
    ExportColumn(
        "call_number",
        "Yer Numarası",
        ExportKind.TEXT,
        "Sırt etiketindeki yer numarası.",
    ),
    ExportColumn(
        "work_section",
        "Eser Bölümü",
        ExportKind.TEXT,
        "Eserin kendi bölümü; “Bölüm” sütunu nüshanın durduğu bölümdür.",
    ),
    ExportColumn(
        "label_printed",
        "Barkod Etiketi Basıldı",
        ExportKind.YES_NO,
        "Barkod etiketinin basım işareti; “Evet” yazılan nüsha basım kuyruğuna girmez.",
    ),
    ExportColumn(
        "spine_label_printed",
        "Sırt Etiketi Basıldı",
        ExportKind.YES_NO,
        "Sırt etiketinin basım işareti.",
    ),
    ExportColumn(
        "label_verified",
        "Etiket Doğrulandı",
        ExportKind.YES_NO,
        "Yapıştırılan barkod etiketi doğrulama okutmasından geçti mi.",
    ),
)
EXTRA_COLUMNS_BY_KEY: Final[dict[str, ExportColumn]] = {s.key: s for s in EXTRA_COLUMNS}

#: "Katalog" sayfasının bütün başlıkları, sırasıyla: içe aktarım sözlüğü + ek sütunlar.
BASE_COLUMNS: Final[tuple[CatalogColumn, ...]] = import_schema.COLUMNS
HEADERS: Final[tuple[str, ...]] = (
    *(s.header for s in BASE_COLUMNS),
    *(s.header for s in EXTRA_COLUMNS),
)
KEYS: Final[tuple[str, ...]] = (
    *(s.key for s in BASE_COLUMNS),
    *(s.key for s in EXTRA_COLUMNS),
)
#: İçe aktarıcının dosyada aradığı ZORUNLU ek sütunlar (yoksa dosya bu kipte okunmaz).
REQUIRED_EXTRA_KEYS: Final[tuple[str, ...]] = ("work_no", "barcode", "status")


def _ek_basliklar() -> dict[str, str]:
    """Ek sütunların katlanmış başlığı → anahtar. İçe aktarım sözlüğüyle çakışma yasaktır.

    Ek başlık olağan içe aktarımda "tanınmayan başlık" kalmalıdır: sözlükteki bir
    başlık ya da eşanlamla aynı katlanmış biçime düşseydi değeri sessizce bir künye
    sütununa yazılırdı (ör. "Kayıt No" ↔ "Eski Kayıt No" eşanlamları).
    """
    dizin: dict[str, str] = {}
    for sutun in EXTRA_COLUMNS:
        katlanmis = import_schema.fold(sutun.header)
        if import_schema.match_header(sutun.header) is not None:
            raise ValueError(f"Ek başlık içe aktarım sözlüğüyle çakışıyor: {sutun.header!r}")
        if dizin.setdefault(katlanmis, sutun.key) != sutun.key:
            raise ValueError(f"Yinelenen ek başlık: {sutun.header!r}")
    return dizin


_EXTRA_HEADER_INDEX: Final[dict[str, str]] = _ek_basliklar()


def match_extra_header(cell: object) -> str | None:
    """Başlık hücresini ek sütun anahtarına eşler (TR katlamalı TAM eşleşme)."""
    return _EXTRA_HEADER_INDEX.get(import_schema.fold(cell))


def label_to_code(choices: Iterable[tuple[str, str]], value: object) -> str | None:
    """Etiket (ya da kod) → kod; TR katlamalı. Tanınmazsa `None`."""
    katlanmis = import_schema.fold(value)
    if not katlanmis:
        return None
    for kod, etiket in choices:
        if import_schema.fold(etiket) == katlanmis or import_schema.fold(kod) == katlanmis:
            return str(kod)
    return None
