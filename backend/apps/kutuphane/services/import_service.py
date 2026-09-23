"""Toplu katalog aktarımı — önizleme ve uygulama AYNI kodu koşar (tasarım §8.1, D5).

OYS'nin (Okul Yönetim Sistemi) `apps/kutuphane/import_service.py` dosyasından
UYARLA (tasarım §12). Devralınan kusur D5'in üç maddesi de burada kapanır:
`shelf_location` kaybolmaz, fikirdeşlik (idempotency) vardır, önizleme
uygulamayla eşleşir.

**Önizleme = uygulama.** Tek bir yazma yolu vardır (`_ingest`); önizleme onu
`transaction.atomic()` içinde koşar ve `transaction.set_rollback(True)` ile geri
sarar (F1'in `apps/okul/services/imports.py` deseni). Yani önizlemede gördüğünüz
sayı, uygulamanın gerçekten yazacağı sayıdır: "kaç eser açılacak" sorusu ikinci
bir tahmin koduyla DEĞİL, işin kendisiyle cevaplanır.

**Tek sapma bir REDDİR, sonuç değil.** Uygulama yazmaya başlamadan önce üç kapı
işletir (`_require_ready`): şüpheli satırların kararı verilmiş olmalı, eşleşmeyen
bölüm değerleri karşılanmış olmalı, aynı dosya daha önce uygulanmamış olmalı.
Önizleme aynı planı çıkarır ve eksikleri RAPORLAR (`pending_decisions`,
`unknown_sections`, `already_applied`) ama reddetmez — ekranın işi zaten o
eksikleri toplamaktır. Kapılar geçildiğinde koşan kod birebir aynıdır.

**Plan yazmadan önce çıkarılır** (`_plan`). Eşleşme kovalarının (yeni / mevcut /
şüpheli) hesabı, bu dosyada AÇILACAK eserleri de görür: künyesi aynı iki satır
tek esere bağlanır (`import_schema`'nın nüsha kipi kararı). Bu yüzden plan, henüz
var olmayan eserleri "bu dosyanın n. satırında açılacak" diye tutar; yazma geçişi
onları gerçek kayda çevirir.

**Eşleşme ölçütü sırayla** (§8.1): ISBN-13, sonra Türkçe katlanmış eser adı +
yazar. ISBN tutup eser adı tutmayan satır MEVCUT sayılmaz, ŞÜPHELİ olur: sahada
ISBN'ler yanlış yazılır ve tek haneli bir hata, nüshaları başka bir kitabın
altına eklerdi.

**Satır hatası partiyi düşürmez.** Her satır kendi savepoint'inde yazılır; nüsha
kurallarına takılan bir satır (ciltsiz süreli yayın gibi) rapora düşer, öbür
satırlar yazılmaya devam eder.

**Dış istek YOKTUR.** Toplu aktarım hiçbir koşulda ağa çıkmaz (§8.5 kural 2);
koruma testi `tests/test_ice_aktarma_dis_istek.py` bunu hem kaynak taramasıyla
hem çalışma anında sabitler. ISBN ile künye getirme yalnız kullanıcının tek tek
başlattığı bir işlemdir ve bu hattın parçası değildir.

**Toplu yazma kestirmesi kullanılmaz.** `bulk_create` `save()`'i atlar ve Türkçe
arama/sıralama anahtarları boş kalırdı (CLAUDE.md §2-8, `Work.save`); bu yüzden
her eser `services.catalog.create_work`, her nüsha `create_copies` üzerinden
açılır — kurallar (dijital kaynak, ciltli süreli yayın, eski kayıt no, barkod
sayacı) tek yerdedir ve aktarım onları delemez.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any
from zipfile import BadZipFile

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl.utils.exceptions import InvalidFileException

from apps.kutuphane import ai_bridge, import_schema, keys
from apps.kutuphane import isbn as isbn_module
from apps.kutuphane.import_schema import (
    CATALOG_SHEET,
    DEFAULT_COPIES,
    MAX_COPIES_PER_ROW,
    RESOURCE_TYPE_CODES,
    CatalogValueError,
)
from apps.kutuphane.models import (
    PUBLISH_YEAR_MAX,
    PUBLISH_YEAR_MIN,
    Acquisition,
    AcquisitionMethod,
    CatalogImportRun,
    CatalogImportSource,
    CatalogImportStatus,
    ClassificationSource,
    CommissionDecision,
    Section,
    Work,
)
from apps.kutuphane.services import catalog as catalog_service
from apps.okul.excel_ogrenci import ParserError, read_sheet

logger = logging.getLogger("kutuphane_defteri.kutuphane")

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
#: Eşleşme kovaları (§8.1). Kullanıcı metni ön yüzdedir; bunlar kodlardır.
BUCKET_NEW = "new"
BUCKET_EXISTING = "existing"
BUCKET_SUSPECT = "suspect"
BUCKET_SKIPPED = "skipped"

#: Şüpheli satırda kullanıcının verebileceği kararlar: yeni eser aç ya da
#: gösterilen esere nüsha ekle.
DECISION_NEW = "new"
DECISION_ATTACH = "attach"
DECISIONS: tuple[str, ...] = (DECISION_NEW, DECISION_ATTACH)

#: Başlık satırı bu kadar satır içinde aranır (dosyanın başında kurum başlığı,
#: boş satır ya da açıklama olabilir).
HEADER_SCAN_LIMIT = 15
#: Başlık satırı sayılmak için en az bu kadar sütun tanınmalıdır.
HEADER_MIN_MATCHES = 2

#: API yanıtındaki satır raporu tavanı. 10.000 satırlık bir dosyanın tamamını
#: göndermek ne ekrana sığar ne de anlamlıdır; sorunlu satırlar DAİMA girer,
#: kalan yer satır sırasıyla doldurulur ve `rows_truncated` doğruyu söyler.
MAX_REPORT_ROWS = 500
#: Kalıcı `CatalogImportRun.report` tavanı (yalnız sorunlu satırlar yazılır).
MAX_PERSISTED_ROWS = 200
#: Bilinmeyen bölüm değerinde önizlemeye taşınan örnek satır sayısı.
MAX_SECTION_SAMPLE_ROWS = 10
#: Şüpheli satırda listelenen en çok aday (§8.5'in mükerrer kayıt kuralıyla aynı
#: mantık: "ilk birkaç aday listelenir"). Okul kütüphanesinde aynı katlanmış ada
#: sahip yüzlerce eser olağandır ("Matematik", ders kitabı serileri); tavansız
#: liste hem yanıtı hem karar ekranındaki seçiciyi kullanılamaz hâle getirirdi.
MAX_CANDIDATES = 10

#: Aktarımın varsayılan edinim yolu: mevcut koleksiyonun programa ilk aktarımı.
DEFAULT_METHOD = AcquisitionMethod.EXISTING_STOCK


# ---------------------------------------------------------------------------
# Ayrıştırılmış satır
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CatalogRow:
    """Dosyadan okunmuş tek satır (Excel ya da yapay zekâ köprüsü — aynı biçim).

    `row_number` KULLANICININ gördüğü satır numarasıdır (Excel'de sayfa satırı,
    köprüde öğe sırası): önizlemedeki her sorun onunla söylenir.
    """

    row_number: int
    title: str = ""
    authors: str = ""
    translator: str = ""
    publisher: str = ""
    edition: str = ""
    publish_year: int | None = None
    isbn: str = ""
    subjects: str = ""
    classification_code: str = ""
    classification_source: str = ClassificationSource.MANUAL
    language: str = ""
    resource_type: str = "BOOK"
    copies: int = DEFAULT_COPIES
    shelf_location: str = ""
    old_register_no: str = ""
    is_bound_periodical: bool = False
    is_reference: bool = False
    #: Danışma bayrağı "ders kitabı" kuralından geldi (önizlemede gösterilir).
    reference_by_textbook: bool = False
    corrections: list[dict[str, str]] = field(default_factory=list)
    #: Satırı içe aktarmayı ENGELLEYEN sorunlar (kullanıcı iletisi).
    errors: list[str] = field(default_factory=list)
    #: Aktarımı engellemeyen uyarılar (ISBN sağlaması, çözülemeyen yıl…).
    warnings: list[str] = field(default_factory=list)

    @property
    def importable(self) -> bool:
        return not self.errors and bool(self.title)


# ---------------------------------------------------------------------------
# Excel okuma ve ayrıştırma
# ---------------------------------------------------------------------------
def read_catalog_grid(file_bytes: bytes) -> list[list[Any]]:
    """Excel baytlarını satır matrisine çevirir — YALNIZ "Katalog" sayfası (§8.1).

    Şablonun "Sütunlar" ve "Örnek" sayfaları içe aktarılmaz: örnek satırlar kitap
    sanılırdı. Sayfa adı bulunamazsa (okulun kendi hazırladığı dosya) etkin/ilk
    sayfa okunur.
    """
    try:
        return read_sheet(file_bytes, sheet_name=CATALOG_SHEET)
    except (BadZipFile, InvalidFileException) as exc:
        raise ParserError(
            "Dosya Excel olarak okunamadı. Desteklenen biçimler: .xlsx ve Excel 97-2003 "
            "(.xls). CSV ve PDF desteklenmez; katalog şablonunu indirip onu doldurun."
        ) from exc


def _cell_text(value: object) -> str:
    """Hücreyi metne çevirir: tam sayı gösteren ondalık ve tarih hücreleri düzeltilir.

    Excel sayı biçimindeki bir ISBN hücresini `9786051234567.0` diye verir; çıplak
    `str()` sondaki ".0" ile numarayı bozardı.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return import_schema.YES if value else import_schema.NO
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime | date):
        return f"{value:%d.%m.%Y}"
    return str(value).strip()


def _year_value(value: object) -> tuple[int | None, str]:
    """Yayın yılı hücresi → (yıl, uyarı). Çözülemeyen ya da aralık dışı yıl boş kalır.

    Yıl bulunamadığında satır DÜŞMEZ: eksik yıl künyeyi değersizleştirmez, ama
    sessizce yanlış bir yıl yazmak kataloğu bozar — bu yüzden uyarı verilir.
    """
    if value is None or _cell_text(value) == "":
        return None, ""
    if isinstance(value, datetime | date):
        return value.year, ""
    ham = _cell_text(value)
    rakamlar = "".join(ch for ch in ham if ch.isdigit())
    if not rakamlar:
        return None, f"Yayın yılı okunamadı (“{ham}”); boş bırakıldı."
    yil = int(rakamlar[:4])
    if not PUBLISH_YEAR_MIN <= yil <= PUBLISH_YEAR_MAX:
        return None, f"Yayın yılı “{ham}” dört haneli bir yıl değil; boş bırakıldı."
    return yil, ""


def _copies_value(value: object) -> tuple[int, str]:
    """Nüsha sayısı hücresi → (sayı, hata). Boş hücre sözlüğün varsayılanını uygular.

    Hücre YALNIZ rakamlardan oluşmalıdır. Rakamları hücreden kazımak ("2-3" →
    23, "1,5" → 15, "3 ya da 4" → 34) sözlüğün "1-50 arası tam sayı" sözünü
    tutmaz ve sessizce onlarca nüsha açardı: açılan her nüsha TMY defterine
    kalıcı bir kayıt numarası yazar ve numara asla yeniden kullanılmaz
    (`services/numbering.py`), yani yanlış açılan nüshayı silmek defterde
    izahı olmayan bir boşluk bırakırdı. Belirsiz hücre satırı düşürür.
    """
    ham = _cell_text(value)
    if not ham:
        return DEFAULT_COPIES, ""
    rakamlar = ham.strip()
    # `isascii` şart: "²" ve Arapça-Hint rakamları `isdigit()`e evet der ama
    # `int()` ya patlar ya da beklenmedik bir sayı üretir.
    if not (rakamlar.isascii() and rakamlar.isdigit()):
        return 0, f"Nüsha sayısı “{ham}” sayı değil; satır içe aktarılmadı."
    adet = int(rakamlar)
    if adet < 1 or adet > MAX_COPIES_PER_ROW:
        return 0, (
            f"Nüsha sayısı 1 ile {MAX_COPIES_PER_ROW} arasında olmalıdır (“{ham}”); "
            "daha fazla nüsha için eseri birkaç satıra bölün."
        )
    return adet, ""


@dataclass(slots=True)
class ParsedFile:
    """Ayrıştırma sonucu: satırlar + başlık eşlemesinin anlattıkları."""

    rows: list[CatalogRow]
    header_row: int = 0
    #: Tanınmayan başlıklar (içe aktarılmaz; önizlemede söylenir).
    unknown_headers: list[str] = field(default_factory=list)
    #: Sözlükte olup dosyada bulunmayan sütunlar (yalnız bilgi).
    missing_columns: list[str] = field(default_factory=list)


def _find_header(grid: Sequence[Sequence[Any]]) -> tuple[int, dict[str, int], list[str]]:
    """Başlık satırını bulur → (satır indisi, sütun anahtarı → sütun indisi, tanınmayanlar).

    Tanınmayan başlık dosyayı geçersiz kılmaz: okulun listesinde programın
    bilmediği sütunlar (fiyat, not, açıklama) olabilir; onlar okunmaz ve
    önizlemede sayılır.
    """
    en_iyi: tuple[int, dict[str, int], list[str]] | None = None
    for indis, satir in enumerate(grid[:HEADER_SCAN_LIMIT]):
        eslesen: dict[str, int] = {}
        taninmayan: list[str] = []
        for sutun, hucre in enumerate(satir):
            anahtar = import_schema.match_header(hucre)
            if anahtar is None:
                metin = _cell_text(hucre)
                if metin:
                    taninmayan.append(metin)
            elif anahtar not in eslesen:  # aynı başlık iki kez yazılmışsa ilki geçerli
                eslesen[anahtar] = sutun
        if "title" in eslesen and len(eslesen) >= HEADER_MIN_MATCHES:
            if en_iyi is None or len(eslesen) > len(en_iyi[1]):
                en_iyi = (indis, eslesen, taninmayan)
    if en_iyi is None:
        raise ParserError(
            "Başlık satırı bulunamadı. Dosyanın bir satırında “Eser Adı” sütunu ve en az bir "
            "künye sütunu daha bulunmalıdır; katalog şablonunu indirip onun başlıklarını "
            "kullanın."
        )
    return en_iyi


def parse_catalog_grid(grid: Sequence[Sequence[Any]]) -> ParsedFile:
    """Satır matrisini `CatalogRow` listesine çevirir (değer kuralları sözlükten).

    Hücre değeri sözlüğün kabul ettiklerinden biri değilse satır İÇE AKTARILMAZ
    ve gerekçesi satır numarasıyla rapora girer: "Süreli yayın" yerine tanınmayan
    bir tür yazmak ya da "Danışma Kaynağı" sütununa serbest metin yazmak ödünç
    verilebilirliği değiştirir, sessizce varsayılana düşürülemez.
    """
    header_row, sutunlar, taninmayan = _find_header(grid)
    eksik = [sutun.header for sutun in import_schema.COLUMNS if sutun.key not in sutunlar]
    satirlar: list[CatalogRow] = []
    for indis in range(header_row + 1, len(grid)):
        ham = grid[indis]
        if all(_cell_text(hucre) == "" for hucre in ham):
            continue
        satirlar.append(_parse_row(indis + 1, ham, sutunlar))
    return ParsedFile(
        rows=satirlar,
        header_row=header_row + 1,
        unknown_headers=list(dict.fromkeys(taninmayan)),
        missing_columns=eksik,
    )


def _hucre(ham: Sequence[Any], sutunlar: Mapping[str, int], anahtar: str) -> Any:
    indis = sutunlar.get(anahtar)
    if indis is None or indis >= len(ham):
        return None
    return ham[indis]


def _parse_row(  # noqa: C901 — sözlüğün 16 sütunu tek yerde çözülür
    row_number: int, ham: Sequence[Any], sutunlar: Mapping[str, int]
) -> CatalogRow:
    """Tek satırı sözlüğün değer kurallarıyla çözer."""
    satir = CatalogRow(row_number=row_number)
    satir.title = _cell_text(_hucre(ham, sutunlar, "title"))
    if not satir.title:
        satir.errors.append("Eser adı boş; satır içe aktarılmadı.")

    satir.authors = _cell_text(_hucre(ham, sutunlar, "authors"))
    satir.translator = _cell_text(_hucre(ham, sutunlar, "translator"))
    satir.publisher = _cell_text(_hucre(ham, sutunlar, "publisher"))
    satir.edition = _cell_text(_hucre(ham, sutunlar, "edition"))
    satir.isbn = _cell_text(_hucre(ham, sutunlar, "isbn"))
    satir.subjects = _cell_text(_hucre(ham, sutunlar, "subjects"))
    satir.classification_code = _cell_text(_hucre(ham, sutunlar, "classification_code"))
    satir.language = _cell_text(_hucre(ham, sutunlar, "language"))
    satir.shelf_location = _cell_text(_hucre(ham, sutunlar, "shelf_location"))
    satir.old_register_no = _cell_text(_hucre(ham, sutunlar, "old_register_no"))

    satir.publish_year, yil_uyarisi = _year_value(_hucre(ham, sutunlar, "publish_year"))
    if yil_uyarisi:
        satir.warnings.append(yil_uyarisi)

    satir.copies, adet_hatasi = _copies_value(_hucre(ham, sutunlar, "copies"))
    if adet_hatasi:
        satir.errors.append(adet_hatasi)

    ham_tur = _hucre(ham, sutunlar, "resource_type")
    try:
        satir.resource_type = RESOURCE_TYPE_CODES[import_schema.resource_type_value(ham_tur)]
    except CatalogValueError as exc:
        satir.errors.append(f"“Kaynak Türü” sütunu: {exc}")

    try:
        satir.is_bound_periodical = bool(
            import_schema.yes_no_value(_hucre(ham, sutunlar, "is_bound_periodical"))
        )
    except CatalogValueError as exc:
        satir.errors.append(f"“Ciltli Süreli Yayın” sütunu: {exc}")

    try:
        danisma = import_schema.yes_no_value(_hucre(ham, sutunlar, "is_reference"))
    except CatalogValueError as exc:
        satir.errors.append(f"“Danışma Kaynağı” sütunu: {exc}")
    else:
        if danisma is None:
            # Ders kitabı varsayılanı (Md. 14/1-a, 16/1-a; SU-24): boş hücrede açık.
            satir.reference_by_textbook = import_schema.defaults_to_reference(
                ham_tur, satir.subjects
            )
            satir.is_reference = satir.reference_by_textbook
        else:
            satir.is_reference = danisma

    if satir.old_register_no and satir.copies > 1:
        satir.errors.append(
            "Bir eski kayıt no tek nüshaya aittir: bu satırda nüsha sayısı 1 olmalıdır. "
            "Aynı eserin öbür nüshaları için ayrı satır açın."
        )

    uyari = isbn_module.isbn_warning(satir.isbn)
    if uyari:
        satir.warnings.append(uyari)
    return satir


def rows_from_ai_items(items: Iterable[Mapping[str, Any]]) -> list[CatalogRow]:
    """Köprüden gelen öğeleri Excel satırlarıyla AYNI biçime çevirir (§8.2).

    Köprüde "Ders kitabı" diye bir kaynak türü yoktur (kod listesi BOOK /
    PERIODICAL / AV_MATERIAL); danışma varsayılanı bu yüzden yalnız KONU
    üzerinden işler — Excel yolundaki kuralın aynısıdır.
    """
    satirlar: list[CatalogRow] = []
    for sira, oge in enumerate(items, start=1):
        satir = CatalogRow(row_number=sira)
        satir.title = str(oge.get("title") or "")
        satir.authors = str(oge.get("authors") or "")
        satir.translator = str(oge.get("translator") or "")
        satir.publisher = str(oge.get("publisher") or "")
        satir.edition = str(oge.get("edition") or "")
        satir.isbn = str(oge.get("isbn") or "")
        satir.subjects = str(oge.get("subjects") or "")
        satir.classification_code = str(oge.get("classification_code") or "")
        satir.classification_source = str(
            oge.get("classification_source") or ClassificationSource.MANUAL
        )
        satir.language = str(oge.get("language") or "")
        satir.resource_type = str(oge.get("resource_type") or "BOOK")
        satir.shelf_location = str(oge.get("shelf_location") or "")
        satir.corrections = list(oge.get("corrections") or [])
        satir.warnings = list(oge.get("issues") or [])
        satir.reference_by_textbook = import_schema.defaults_to_reference("", satir.subjects)
        satir.is_reference = satir.reference_by_textbook

        adet = int(oge.get("copies") or 0)
        satir.copies = adet if adet >= 1 else DEFAULT_COPIES
        if adet < 1:
            satir.errors.append("Nüsha sayısı geçersiz; satır içe aktarılmadı.")
        if not satir.title:
            satir.errors.append("Eser adı boş; satır içe aktarılmadı.")
        yil = oge.get("publish_year")
        if yil is not None and PUBLISH_YEAR_MIN <= int(yil) <= PUBLISH_YEAR_MAX:
            satir.publish_year = int(yil)
        elif yil is not None:
            satir.warnings.append("Yayın yılı dört haneli bir yıl değil; boş bırakıldı.")
        uyari = isbn_module.isbn_warning(satir.isbn)
        if uyari:
            satir.warnings.append(uyari)
        satirlar.append(satir)
    return satirlar


# ---------------------------------------------------------------------------
# İçerik özeti (fikirdeşlik anahtarı)
# ---------------------------------------------------------------------------
#: Fikirdeşlik özetine giren alanlar: satırın KATALOG içeriği. Türetilmiş
#: alanlar (hata, uyarı, "ders kitabı" bayrağı) ve satır numarası dışarıdadır —
#: aynı liste araya boş satır girdi diye ikinci kez uygulanabilir olmamalıdır.
HASH_FIELDS: tuple[str, ...] = (
    "title",
    "authors",
    "translator",
    "publisher",
    "edition",
    "publish_year",
    "isbn",
    "subjects",
    "classification_code",
    "classification_source",
    "language",
    "resource_type",
    "copies",
    "shelf_location",
    "old_register_no",
    "is_bound_periodical",
    "is_reference",
)


def content_hash(rows: Sequence[CatalogRow]) -> str:
    """Ayrıştırılmış satırların SHA256 özeti — fikirdeşlik anahtarı (§8.1, D5).

    Özet ham BAYTTAN değil İÇERİKTEN alınır. Sahadaki olağan akış — önizle,
    raporda görünen satırları Excel'de düzelt, kaydet, yeniden uygula —
    dosyanın baytlarını her kaydedişte değiştirir; dosya adı, sayfa sırası,
    hücre biçimi ve kenar boşluğu farkları da öyle. Bayt özeti bu yüzden
    "aynı dosya" sorusuna değil "aynı dosya, aynı baytlarla" sorusuna cevap
    verirdi ve tek boşluk farkı olan bir kopya bütün satırları İKİNCİ KEZ
    nüsha açardı. Köprü (JSON) yolu bu tuzağı ilk günden biliyordu (anahtar
    sırasını normalleştiriyordu); asıl yol olan Excel de aynı ölçüyü kullanır.
    """
    kanonik = [[getattr(satir, alan) for alan in HASH_FIELDS] for satir in rows]
    metin = json.dumps(kanonik, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ImportRowReport:
    """Bir satırın önizleme/uygulama sonucu — API yanıtının (geçici) biçimi.

    `title` ve `issues` dosyadan gelen HAM hücre metnini taşır: ekranın işi
    kullanıcıya kendi dosyasını göstermektir. Kalıcı kütüğe giden biçim ayrıdır
    (`to_run_dict`) ve ham metin içermez.
    """

    row: int
    title: str
    bucket: str
    #: Eşleşen ya da açılan eserin kimliği. Önizlemede AÇILACAK eserlerde boştur
    #: (geri sarılan işlemde üretilen kimlik anlamsızdır), eşleşen eserde doludur.
    work: int | None = None
    #: Bu dosyada açılacak bir esere bağlanıyorsa o satırın numarası.
    work_row: int | None = None
    copies: int = 0
    copies_created: int = 0
    section: str = ""
    shelf_location: str = ""
    is_reference: bool = False
    reference_by_textbook: bool = False
    classification_source: str = ClassificationSource.MANUAL
    needs_decision: bool = False
    decision: str = ""
    #: En çok `MAX_CANDIDATES` aday; toplamı `candidate_count` söyler.
    candidates: list[dict[str, Any]] = field(default_factory=list)
    candidate_count: int = 0
    candidates_truncated: bool = False
    corrections: list[dict[str, str]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def has_problem(self) -> bool:
        return bool(self.issues) or self.bucket in (BUCKET_SKIPPED, BUCKET_SUSPECT)

    def to_run_dict(self) -> dict[str, Any]:
        """Kalıcı kütüğe giren biçim: **ham hücre metni YOKTUR**.

        `title` dosyadaki ham "Eser Adı" hücresidir ve `issues` iletileri ham
        hücre değerlerini gömer ("Nüsha sayısı “iki tane” sayı değil…").
        Sütunu kaymış bir okul listesinde o metin bir kişi adı olabilir ve
        `CatalogImportRun` kalıcıdır — koşu satırının silme ucu yoktur. Bu
        yüzden kütüğe yalnız satır numarası, kova ve sayılar yazılır; ham
        metin API yanıtında (geçici, ekranda) kalır. "Neden aktarılmadı?"
        sorusunun cevabı kullanıcının elindeki dosyayı yeniden önizlemektir.
        """
        return {
            "row": self.row,
            "bucket": self.bucket,
            "work": self.work,
            "copies": self.copies,
            "copies_created": self.copies_created,
            "needs_decision": self.needs_decision,
            "issue_count": len(self.issues),
        }


@dataclass(slots=True)
class CatalogImportReport:
    """Önizleme ve uygulamanın ORTAK raporu (ön yüz tek biçim bekler)."""

    payload_sha256: str
    source: str
    schema_version: str
    file_name: str = ""
    dry_run: bool = False
    #: Aynı içerik daha önce UYGULANMIŞ (önizlemede uyarı, uygulamada engel).
    already_applied: bool = False
    applied_at: str = ""
    stats: dict[str, int] = field(default_factory=dict)
    rows: list[ImportRowReport] = field(default_factory=list)
    rows_truncated: bool = False
    #: Bölüm listesinde bulunmayan "Bölüm" değerleri (önizlemede sorulur — D5).
    unknown_sections: list[dict[str, Any]] = field(default_factory=list)
    unknown_headers: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    #: Kullanıcı kararı bekleyen şüpheli satırların numaraları.
    pending_decisions: list[int] = field(default_factory=list)
    #: F4 etiket kısayolunun bağlanacağı parti: edinim kimliği ve barkod aralığı.
    label_batch: dict[str, Any] | None = None
    run_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """API yanıtı (satır raporu tavana kadar).

        `asdict` ÖZYİNELEMELİDİR: doğrudan `self` üzerinde çağrılsaydı 10.000
        satırın tamamı (ve içlerindeki aday/uyarı/düzeltme listeleri) sözlüğe
        çevrilip hemen ardından tavana inmiş listeyle ezilirdi — isteğin en
        büyük bellek sıçraması boşa üretilen kopyalardı. Satırlar bu yüzden
        geçici olarak boşaltılır; yalnız tavana giren satırlar çevrilir.
        """
        secilen = self._capped_rows(MAX_REPORT_ROWS)
        satirlar = self.rows
        self.rows = []
        try:
            veri = asdict(self)
        finally:
            self.rows = satirlar
        veri["rows"] = [asdict(satir) for satir in secilen]
        veri["rows_truncated"] = len(secilen) < len(self.rows)
        return veri

    def to_run_dict(self) -> dict[str, Any]:
        """Kalıcı `CatalogImportRun.report`: yalnız SORUNLU satırlar ve dosya bilgisi.

        10.000 satırlık bir dosyanın tamamını JSON alanına yazmak veritabanını
        şişirir ve hiçbir soruya cevap vermez; kütükte kalması gereken, neyin
        aktarılamadığıdır.

        Satırlar `ImportRowReport.to_run_dict` ile yazılır: ham eser adı ve ham
        hücre değeri gömen hata iletileri kütüğe GİRMEZ (gerekçe orada).
        """
        sorunlu = self._problem_rows()
        return {
            "rows": [satir.to_run_dict() for satir in sorunlu[:MAX_PERSISTED_ROWS]],
            "rows_truncated": len(sorunlu) > MAX_PERSISTED_ROWS,
            "unknown_sections": self.unknown_sections,
            "unknown_headers": self.unknown_headers,
            "missing_columns": self.missing_columns,
            "pending_decisions": self.pending_decisions,
            "label_batch": self.label_batch,
        }

    def _problem_rows(self) -> list[ImportRowReport]:
        return [satir for satir in self.rows if satir.has_problem]

    def _capped_rows(self, limit: int) -> list[ImportRowReport]:
        """Sorunlu satırlar DAİMA girer; kalan yer satır sırasıyla doldurulur."""
        if len(self.rows) <= limit:
            return list(self.rows)
        secilen = {satir.row for satir in self._problem_rows()[:limit]}
        for satir in self.rows:
            if len(secilen) >= limit:
                break
            secilen.add(satir.row)
        return [satir for satir in self.rows if satir.row in secilen]


# ---------------------------------------------------------------------------
# Eşleştirme dizini
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class _Aday:
    """Eşleşme adayı: ya var olan bir eser (`pk`) ya bu dosyada açılacak satır (`row`)."""

    pk: int | None
    row: int | None
    title: str
    authors: str
    folded_title: str = ""
    folded_authors: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"work": self.pk, "row": self.row, "title": self.title, "authors": self.authors}


class _WorkIndex:
    """Eser eşleştirme dizini — DB'den bir kez okunur, dosyadakilerle büyür.

    Satır başına sorgu atmak 10.000 satırlık bir dosyada 10.000 sorgu demekti;
    dizin tek `values_list` ile kurulur. Aynı künyeli iki satırın tek esere
    bağlanması da buradan gelir: plan sırasında açılacak eserler dizine satır
    numarasıyla yazılır.
    """

    def __init__(self) -> None:
        self._by_isbn13: dict[str, list[_Aday]] = {}
        self._by_title: dict[str, list[_Aday]] = {}
        for pk, title, authors, isbn13 in Work.objects.values_list(
            "pk", "title", "authors", "isbn13"
        ):
            self.add(_Aday(pk=pk, row=None, title=title, authors=authors), isbn13)

    def add(self, aday: _Aday, isbn13: str) -> None:
        aday.folded_title = keys.fold_search(aday.title)
        aday.folded_authors = keys.fold_search(aday.authors)
        if isbn13:
            self._by_isbn13.setdefault(isbn13, []).append(aday)
        if aday.folded_title:
            self._by_title.setdefault(aday.folded_title, []).append(aday)

    def match(self, row: CatalogRow) -> tuple[str, _Aday | None, list[_Aday]]:
        """(kova, eşleşen aday, şüpheli adaylar) — ölçüt sırayla ISBN-13, sonra ad+yazar."""
        katlanmis_ad = keys.fold_search(row.title)
        katlanmis_yazar = keys.fold_search(row.authors)
        isbn13 = isbn_module.to_isbn13(row.isbn)

        isbn_adaylari: list[_Aday] = []
        if isbn13:
            for aday in self._by_isbn13.get(isbn13, []):
                if aday.folded_title == katlanmis_ad:
                    return BUCKET_EXISTING, aday, []
                isbn_adaylari.append(aday)

        ad_adaylari = self._by_title.get(katlanmis_ad, []) if katlanmis_ad else []
        for aday in ad_adaylari:
            if aday.folded_authors == katlanmis_yazar:
                return BUCKET_EXISTING, aday, []

        supheliler = [*isbn_adaylari, *ad_adaylari]
        if supheliler:
            return BUCKET_SUSPECT, None, supheliler
        return BUCKET_NEW, None, []


# ---------------------------------------------------------------------------
# Plan (yazmadan önce)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class _PlanRow:
    row: CatalogRow
    report: ImportRowReport
    #: Bağlanılacak var olan eserin kimliği.
    work_pk: int | None = None
    #: Bu dosyanın şu satırında açılacak esere bağlanır.
    work_row: int | None = None
    #: Bu satır yeni eser açar.
    creates_work: bool = False
    section_pk: int | None = None
    #: Yeni açılacak bölümün adı (henüz kimliği yok).
    section_name: str = ""


@dataclass(slots=True)
class _Plan:
    rows: list[_PlanRow]
    unknown_sections: list[dict[str, Any]]
    pending_decisions: list[int]
    new_section_names: list[str]
    sections_by_pk: dict[int, Section]


def _section_index() -> dict[str, Section]:
    """Katlanmış bölüm adı → bölüm (kontrollü liste; "Edebiyat" ≡ "edebiyat ")."""
    dizin: dict[str, Section] = {}
    for bolum in Section.objects.all():
        anahtar = keys.fold_search(bolum.name) or bolum.name.strip()
        dizin.setdefault(anahtar, bolum)
    return dizin


def _normalize_decisions(
    decisions: Mapping[Any, Mapping[str, Any]] | None,
) -> dict[int, dict[str, Any]]:
    """Kararları satır numarasına indeksler; biçim hatası sözleşmeli 400 olur."""
    sonuc: dict[int, dict[str, Any]] = {}
    for ham_satir, ham_karar in (decisions or {}).items():
        try:
            satir_no = int(ham_satir)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"decisions": "Karar verilen satır numarası sayısal olmalıdır."}
            ) from exc
        if not isinstance(ham_karar, Mapping):
            raise ValidationError({"decisions": f"{satir_no}. satırın kararı okunamadı."})
        eylem = str(ham_karar.get("action") or "").strip()
        if eylem not in DECISIONS:
            raise ValidationError(
                {
                    "decisions": (
                        f"{satir_no}. satırın kararı “yeni eser aç” ya da “nüsha ekle” "
                        "olmalıdır."
                    )
                }
            )
        sonuc[satir_no] = {
            "action": eylem,
            "work": ham_karar.get("work"),
            "row": ham_karar.get("row"),
        }
    return sonuc


def _normalize_section_map(section_map: Mapping[Any, Any]) -> dict[str, int]:
    """Bölüm eşlemesini katlanmış değer → bölüm kimliğine çevirir.

    Sayısal olmayan kimlik sözleşmeli 400 olur (`_normalize_decisions`in aynı
    deseni): sarmalanmayan bir `int()` `ValueError` yükseltirdi ve
    `kd_exception_handler` Django `ValidationError`ını tanıdığı için onu
    çeviremeyip 500 döndürürdü — kullanıcı "sunucu hatası" görürdü.
    """
    sonuc: dict[str, int] = {}
    for deger, pk in section_map.items():
        anahtar = keys.fold_search(str(deger)) or str(deger).strip()
        try:
            sonuc[anahtar] = int(pk)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"section_map": f"“{deger}” için seçilen bölüm kimliği sayısal olmalıdır."}
            ) from exc
    return sonuc


def _decision_target(row_number: int, karar: Mapping[str, Any]) -> _Aday:
    """ "Şu esere nüsha ekle" kararını adaya çevirir (eser kimliği ya da dosya satırı)."""
    eser_pk = karar.get("work")
    satir_no = karar.get("row")
    if eser_pk is not None:
        try:
            pk = int(eser_pk)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"decisions": f"{row_number}. satırda seçilen eser kimliği sayısal olmalıdır."}
            ) from exc
        if not Work.objects.filter(pk=pk).exists():
            raise ValidationError({"decisions": f"{row_number}. satırda seçilen eser bulunamadı."})
        return _Aday(pk=pk, row=None, title="", authors="")
    if satir_no is not None:
        try:
            return _Aday(pk=None, row=int(satir_no), title="", authors="")
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"decisions": f"{row_number}. satırda seçilen satır numarası sayısal olmalıdır."}
            ) from exc
    raise ValidationError({"decisions": f"{row_number}. satırda nüsha eklenecek eser seçilmemiş."})


def _plan(
    rows: Sequence[CatalogRow],
    *,
    decisions: Mapping[int, Mapping[str, Any]],
    section_map: Mapping[Any, Any],
    new_sections: Sequence[str],
) -> _Plan:
    """Yazmadan önce ne olacağını çıkarır (kovalar, bölümler, kararlar).

    Planın yazmadan ayrı durması iki işe yarar: uygulama yazmaya BAŞLAMADAN
    eksikleri reddedebilir ve önizleme aynı planı kullanıcıya gösterebilir.
    """
    dizin = _WorkIndex()
    bolumler = _section_index()
    eslenen_bolumler = _normalize_section_map(section_map)
    yeni_bolum_adlari = {
        keys.fold_search(ad) or str(ad).strip(): str(ad).strip() for ad in new_sections
    }
    bolum_pkleri = {bolum.pk: bolum for bolum in bolumler.values()}

    plan_satirlari: list[_PlanRow] = []
    bilinmeyen: dict[str, dict[str, Any]] = {}
    bekleyen: list[int] = []

    for satir in rows:
        rapor = ImportRowReport(
            row=satir.row_number,
            title=satir.title,
            bucket=BUCKET_SKIPPED,
            copies=satir.copies,
            shelf_location=satir.shelf_location,
            is_reference=satir.is_reference,
            reference_by_textbook=satir.reference_by_textbook,
            classification_source=satir.classification_source,
            corrections=list(satir.corrections),
            issues=[*satir.errors, *satir.warnings],
        )
        plan = _PlanRow(row=satir, report=rapor)
        plan_satirlari.append(plan)
        if not satir.importable:
            continue

        kova, aday, supheliler = dizin.match(satir)
        # Aday listesi tavanlıdır: ekranda seçilebilecek kadarı gösterilir,
        # toplam sayı ayrı alanda söylenir (MAX_CANDIDATES gerekçesi).
        rapor.candidate_count = len(supheliler)
        rapor.candidates = [oge.as_dict() for oge in supheliler[:MAX_CANDIDATES]]
        rapor.candidates_truncated = len(supheliler) > MAX_CANDIDATES
        karar = decisions.get(satir.row_number)
        if karar is not None:
            rapor.decision = str(karar["action"])
            if karar["action"] == DECISION_ATTACH:
                kova, aday = BUCKET_EXISTING, _decision_target(satir.row_number, karar)
            else:
                kova, aday = BUCKET_NEW, None
        elif kova == BUCKET_SUSPECT:
            bekleyen.append(satir.row_number)
            rapor.needs_decision = True

        rapor.bucket = kova
        if kova == BUCKET_EXISTING and aday is not None:
            plan.work_pk = aday.pk
            plan.work_row = aday.row
            rapor.work = aday.pk
            rapor.work_row = aday.row
        elif kova == BUCKET_NEW:
            plan.creates_work = True
            dizin.add(
                _Aday(pk=None, row=satir.row_number, title=satir.title, authors=satir.authors),
                isbn_module.to_isbn13(satir.isbn),
            )

        _plan_section(
            plan,
            bolumler=bolumler,
            eslenen=eslenen_bolumler,
            yeni_adlar=yeni_bolum_adlari,
            bilinmeyen=bilinmeyen,
            bolum_pkleri=bolum_pkleri,
        )

    return _Plan(
        rows=plan_satirlari,
        unknown_sections=sorted(bilinmeyen.values(), key=lambda kayit: str(kayit["value"])),
        pending_decisions=bekleyen,
        new_section_names=[
            ad for anahtar, ad in yeni_bolum_adlari.items() if anahtar not in bolumler
        ],
        sections_by_pk=bolum_pkleri,
    )


def _plan_section(
    plan: _PlanRow,
    *,
    bolumler: Mapping[str, Section],
    eslenen: Mapping[str, int],
    yeni_adlar: Mapping[str, str],
    bilinmeyen: dict[str, dict[str, Any]],
    bolum_pkleri: Mapping[int, Section],
) -> None:
    """Satırın "Bölüm" değerini kontrollü listeyle eşler (D5: değer kaybolmaz).

    Eşleşmeyen değer SESSİZCE DÜŞÜRÜLMEZ: önizlemede sorulur, uygulama karşılığı
    verilmeden yazmaz. Devralınan kusurda (D5) bu değer kayboluyordu ve nüshanın
    rafta nerede durduğu bilgisi aktarımdan sonra bulunamıyordu.
    """
    ham = plan.row.shelf_location
    if not ham:
        return
    anahtar = keys.fold_search(ham) or ham.strip()
    bolum = bolumler.get(anahtar)
    if bolum is not None:
        plan.section_pk = bolum.pk
        plan.report.section = bolum.name
        return
    if anahtar in eslenen:
        secilen = eslenen[anahtar]
        hedef = bolum_pkleri.get(secilen)
        if hedef is None:
            raise ValidationError({"section_map": f"“{ham}” için seçilen bölüm bulunamadı."})
        plan.section_pk = hedef.pk
        plan.report.section = hedef.name
        return
    if anahtar in yeni_adlar:
        plan.section_name = yeni_adlar[anahtar]
        plan.report.section = plan.section_name
        return
    kayit = bilinmeyen.setdefault(anahtar, {"value": ham.strip(), "rows": [], "count": 0})
    kayit["count"] = int(kayit["count"]) + 1
    if len(kayit["rows"]) < MAX_SECTION_SAMPLE_ROWS:
        kayit["rows"].append(plan.row.row_number)


# ---------------------------------------------------------------------------
# Uygulama kapıları
# ---------------------------------------------------------------------------
def applied_run(payload_sha256: str) -> CatalogImportRun | None:
    """Aynı içerikle UYGULANMIŞ koşu (fikirdeşlik anahtarı — §8.1, D5).

    Yumuşak silinmiş koşular da sayılır (`all_objects`): kütükten düşen bir satır
    kitapları kayıttan düşürmez, dosya yine ikinci kez uygulanmamalıdır.
    """
    if not payload_sha256:
        return None
    return (
        CatalogImportRun.all_objects.filter(
            payload_sha256=payload_sha256, status=CatalogImportStatus.APPLIED
        )
        .order_by("-created_at")
        .first()
    )


def _require_ready(plan: _Plan, *, payload_sha256: str) -> None:
    """Uygulama yazmaya BAŞLAMADAN önceki üç kapı (önizlemede rapor, burada engel)."""
    onceki = applied_run(payload_sha256)
    if onceki is not None:
        gun = timezone.localtime(onceki.created_at).strftime("%d.%m.%Y")
        raise ValidationError(
            {
                "file": (
                    f"Bu dosya {gun} tarihinde zaten içe aktarıldı; aynı dosya ikinci kez "
                    "uygulanamaz — kitaplar kayda iki kez girerdi. Yeni kitaplar için yalnız "
                    "onları içeren bir dosya hazırlayın."
                )
            }
        )
    if plan.pending_decisions:
        satirlar = ", ".join(str(no) for no in plan.pending_decisions[:10])
        devami = " …" if len(plan.pending_decisions) > 10 else ""
        raise ValidationError(
            {
                "decisions": (
                    f"{len(plan.pending_decisions)} satır karar bekliyor (satır {satirlar}"
                    f"{devami}): her biri için yeni eser açın ya da nüsha eklenecek eseri seçin."
                )
            }
        )
    if plan.unknown_sections:
        degerler = ", ".join(f"“{kayit['value']}”" for kayit in plan.unknown_sections[:10])
        devami = " …" if len(plan.unknown_sections) > 10 else ""
        raise ValidationError(
            {
                "section_map": (
                    f"Bölüm listesinde bulunmayan değerler var: {degerler}{devami}. Her biri "
                    "için var olan bir bölüm seçin ya da yeni bölüm açın."
                )
            }
        )


# ---------------------------------------------------------------------------
# Yazma (önizleme de aynı yoldan geçer)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class AcquisitionSpec:
    """Aktarımın açacağı edinim partisi (Md. 10/5 + kayıt-içi girişler).

    Bağışta komisyon kararı zorunludur ve türü denetlenir; denetim servistedir
    (`services.catalog.ensure_acquisition_decision`), burada tekrarlanmaz.
    """

    method: str = DEFAULT_METHOD
    date: date | None = None
    source_note: str = ""
    unit_price: Any = None
    commission_decision: CommissionDecision | None = None
    notes: str = ""


def _ingest(
    parsed: ParsedFile,
    *,
    plan: _Plan,
    spec: AcquisitionSpec,
    payload_sha256: str,
    source: str,
    file_name: str,
) -> tuple[CatalogImportReport, Acquisition | None]:
    """Planı YAZAR. Önizleme de burayı koşar ve sonucu geri sarar (tek yazma yolu).

    Edinim partisi TEMBEL açılır **ve satırın savepoint'i içinde** açılır:
    hiçbir satırı aktarılamayan bir dosya kayıt defterinde boş bir parti
    bırakmaz. Parti savepoint'in dışında açılsaydı, yalnız ciltsiz süreli yayın
    satırlarından oluşan bir dosya (hepsi Md. 15/4'e takılır) 0 nüsha yazar ama
    nüshasız bir `Acquisition` bırakırdı.
    """
    yeni_bolumler = _create_sections(plan.new_section_names)
    bolum_onbellegi = dict(plan.sections_by_pk)
    edinim: Acquisition | None = None
    acilan_eserler: dict[int, Work] = {}
    mevcut_eserler: dict[int, Work] = {}
    # Nüsha NESNELERİ biriktirilmez: `_label_batch` yalnız sayıyı ve barkod
    # aralığını ister; 10.000 satır × 50 nüsha sınırında liste 500.000 nesne
    # tutardı (bellek sıçraması, hiçbir soruya cevap vermeden).
    nusha_sayisi = 0
    ilk_barkod = ""
    son_barkod = ""
    sayaclar = dict.fromkeys(
        (
            "new_works",
            "existing_matches",
            "suspect",
            "skipped_rows",
            "error_rows",
            "copies_created",
            "reference_defaults",
            "estimated_codes",
            "corrections",
        ),
        0,
    )

    for plan_satiri in plan.rows:
        rapor = plan_satiri.report
        if rapor.bucket == BUCKET_SKIPPED:
            sayaclar["skipped_rows"] += 1
            continue
        if rapor.needs_decision:
            sayaclar["suspect"] += 1
            continue

        try:
            with transaction.atomic():
                # Parti savepoint'in İÇİNDE açılır: satır düşerse parti de geri
                # sarılır ve bir sonraki satır yeniden açar.
                parti = edinim if edinim is not None else _create_acquisition(spec)
                eser = _resolve_work(
                    plan_satiri,
                    acilan=acilan_eserler,
                    mevcut=mevcut_eserler,
                    bolum=_resolve_section(plan_satiri, bolum_onbellegi, yeni_bolumler),
                )
                yeni_nushalar = catalog_service.create_copies(
                    work=eser,
                    acquisition=parti,
                    count=plan_satiri.row.copies,
                    section=_resolve_section(plan_satiri, bolum_onbellegi, yeni_bolumler),
                    is_reference=plan_satiri.row.is_reference,
                    is_bound_periodical=plan_satiri.row.is_bound_periodical,
                    old_register_no=plan_satiri.row.old_register_no,
                )
                if plan_satiri.creates_work:
                    acilan_eserler[plan_satiri.row.row_number] = eser
                rapor.work = eser.pk
                rapor.copies_created = len(yeni_nushalar)
        except ValidationError as exc:
            rapor.issues.extend(_hata_iletileri(exc))
            sayaclar["error_rows"] += 1
            continue

        edinim = parti
        # Buradan sonrası YAZILAN satırın sayaçlarıdır: "ders kitabı
        # varsayılanı N satırda uygulandı" cümlesi, aktarılmayan satırları
        # saysaydı önizleme kullanıcıya olmayan bir kararı anlatırdı.
        if rapor.reference_by_textbook:
            sayaclar["reference_defaults"] += 1
        if rapor.classification_source == ClassificationSource.ESTIMATED:
            sayaclar["estimated_codes"] += 1
        sayaclar["corrections"] += len(rapor.corrections)
        sayaclar["new_works" if plan_satiri.creates_work else "existing_matches"] += 1
        sayaclar["copies_created"] += len(yeni_nushalar)
        for nusha in yeni_nushalar:
            nusha_sayisi += 1
            if not ilk_barkod or nusha.barcode < ilk_barkod:
                ilk_barkod = nusha.barcode
            if nusha.barcode > son_barkod:
                son_barkod = nusha.barcode

    rapor_nesnesi = CatalogImportReport(
        payload_sha256=payload_sha256,
        source=source,
        schema_version=ai_bridge.SCHEMA_VERSION,
        file_name=file_name,
        rows=[plan_satiri.report for plan_satiri in plan.rows],
        unknown_sections=plan.unknown_sections,
        unknown_headers=parsed.unknown_headers,
        missing_columns=parsed.missing_columns,
        pending_decisions=plan.pending_decisions,
        label_batch=_label_batch(edinim, nusha_sayisi, ilk_barkod, son_barkod),
    )
    rapor_nesnesi.stats = {
        "total_rows": len(plan.rows),
        "imported_rows": sayaclar["new_works"] + sayaclar["existing_matches"],
        "sections_created": len(yeni_bolumler),
        **sayaclar,
    }
    return rapor_nesnesi, edinim


def _create_sections(names: Sequence[str]) -> dict[str, Section]:
    """Önizlemede sorulan "yeni bölüm aç" kararlarını uygular (katlanmış ad → bölüm)."""
    sonuc: dict[str, Section] = {}
    for ad in names:
        bolum = catalog_service.create_section(name=ad)
        sonuc[keys.fold_search(ad) or ad.strip()] = bolum
    return sonuc


def _create_acquisition(spec: AcquisitionSpec) -> Acquisition:
    return catalog_service.create_acquisition(
        method=spec.method,
        date=spec.date or timezone.localdate(),
        source_note=spec.source_note,
        unit_price=spec.unit_price,
        commission_decision=spec.commission_decision,
        notes=spec.notes,
    )


def _resolve_work(
    plan_satiri: _PlanRow,
    *,
    acilan: dict[int, Work],
    mevcut: dict[int, Work],
    bolum: Section | None,
) -> Work:
    """Satırın eserini bulur ya da açar (plan ne dediyse o).

    Mevcut esere bağlanan satır ESERİ GÜNCELLEMEZ: aktarım var olan künyenin
    üzerine yazmaz (F1'in "import silmez/üzerine yazmaz" ilkesi), yalnız nüsha
    ekler.
    """
    if plan_satiri.work_pk is not None:
        eser = (
            mevcut.get(plan_satiri.work_pk) or Work.objects.filter(pk=plan_satiri.work_pk).first()
        )
        if eser is None:
            raise ValidationError({"work": "Nüsha eklenecek eser bulunamadı."})
        mevcut[plan_satiri.work_pk] = eser
        return eser
    if plan_satiri.work_row is not None:
        eser = acilan.get(plan_satiri.work_row)
        if eser is None:
            raise ValidationError(
                {"work": f"{plan_satiri.work_row}. satırdaki eser açılamadığı için bağlanamadı."}
            )
        return eser
    satir = plan_satiri.row
    return catalog_service.create_work(
        title=satir.title,
        authors=satir.authors,
        translator=satir.translator,
        publisher=satir.publisher,
        edition=satir.edition,
        publish_year=satir.publish_year,
        isbn=satir.isbn,
        subjects=satir.subjects,
        classification_code=satir.classification_code,
        classification_source=satir.classification_source,
        resource_type=satir.resource_type,
        language=satir.language,
        section=bolum,
    )


def _resolve_section(
    plan_satiri: _PlanRow,
    onbellek: Mapping[int, Section],
    yeni_bolumler: Mapping[str, Section],
) -> Section | None:
    """Satırın bölümü (önbellekten; satır başına sorgu atılmaz)."""
    if plan_satiri.section_pk is not None:
        return onbellek.get(plan_satiri.section_pk)
    if plan_satiri.section_name:
        anahtar = keys.fold_search(plan_satiri.section_name) or plan_satiri.section_name
        return yeni_bolumler.get(anahtar)
    return None


def _hata_iletileri(exc: ValidationError) -> list[str]:
    """Servis reddini kullanıcı iletilerine çevirir (alan kodları rapora girmez)."""
    if hasattr(exc, "error_dict"):
        return [ileti for iletiler in exc.message_dict.values() for ileti in iletiler]
    return list(exc.messages)


def _label_batch(
    edinim: Acquisition | None, nusha_sayisi: int, ilk_barkod: str, son_barkod: str
) -> dict[str, Any] | None:
    """F4'ün "bu partinin etiketlerini bas" kısayolunun bağlanacağı parti kimliği.

    Nüshaların kimlikleri DEĞİL, partinin kimliği verilir: etiket kuyruğu
    `library/copies/?acquisition=<id>&only_unlabeled=true` ile alınır ve 10.000
    nüshalık bir yanıt taşınmaz. Çağıran da nüsha nesnelerini biriktirmez;
    sayaç ile en küçük/en büyük barkodu taşır.
    """
    if edinim is None or nusha_sayisi == 0:
        return None
    return {
        "acquisition": edinim.pk,
        "copy_count": nusha_sayisi,
        "first_barcode": ilk_barkod,
        "last_barcode": son_barkod,
    }


# ---------------------------------------------------------------------------
# Kamu API — dosyadan satırlara, önizleme ve uygulama
# ---------------------------------------------------------------------------
def rows_from_file(file_bytes: bytes, *, source: str) -> tuple[ParsedFile, str]:
    """Yüklenen dosyayı satırlara çevirir → (ayrıştırma sonucu, içerik özeti)."""
    if source == CatalogImportSource.AI_JSON:
        return _parsed_from_json(file_bytes)
    parsed = parse_catalog_grid(read_catalog_grid(file_bytes))
    return parsed, content_hash(parsed.rows)


def _parsed_from_json(file_bytes: bytes) -> tuple[ParsedFile, str]:
    try:
        payload = json.loads(file_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParserError(
            "Dosya JSON olarak okunamadı. Yapay zekâ aracının verdiği metnin tamamını "
            "(süslü parantezle başlayıp biten bölümü) kaydedip yeniden deneyin."
        ) from exc
    parsed = rows_from_payload(payload)
    return parsed, content_hash(parsed.rows)


def rows_from_payload(payload: Any) -> ParsedFile:
    """Köprü JSON'unu ayrıştırma sonucuna çevirir (şema hatası `ParserError` olur)."""
    try:
        items = ai_bridge.validate_payload(payload)
    except ai_bridge.AiBridgeError as exc:
        raise ParserError(" ".join(exc.errors)) from exc
    return ParsedFile(rows=rows_from_ai_items(items))


def preview_import(
    parsed: ParsedFile,
    *,
    payload_sha256: str,
    source: str = CatalogImportSource.EXCEL,
    file_name: str = "",
    decisions: Mapping[Any, Mapping[str, Any]] | None = None,
    section_map: Mapping[Any, Any] | None = None,
    new_sections: Sequence[str] | None = None,
    spec: AcquisitionSpec | None = None,
) -> CatalogImportReport:
    """Yazmadan önizler: gerçek yazma koşulur ve geri sarılır (%100 sonuç paritesi).

    Kalıcı iz (DRY_RUN koşusu) geri sarmanın DIŞINDA yazılır: geçmiş görünümü boş
    kalmasın ve aynı dosyanın daha önce uygulanıp uygulanmadığı görünsün.
    """
    plan = _plan(
        parsed.rows,
        decisions=_normalize_decisions(decisions),
        section_map=section_map or {},
        new_sections=new_sections or [],
    )
    with transaction.atomic():
        rapor, _edinim = _ingest(
            parsed,
            plan=plan,
            spec=spec or AcquisitionSpec(),
            payload_sha256=payload_sha256,
            source=source,
            file_name=file_name,
        )
        transaction.set_rollback(True)
    rapor.dry_run = True
    # Geri sarılan işlemde AÇILAN kayıtların kimlikleri anlamsızdır; eşleşen
    # (zaten var olan) eserin kimliği ise geçerlidir ve ekranda gösterilir.
    for plan_satiri in plan.rows:
        if plan_satiri.creates_work:
            plan_satiri.report.work = None
    rapor.label_batch = None
    onceki = applied_run(payload_sha256)
    if onceki is not None:
        rapor.already_applied = True
        rapor.applied_at = timezone.localtime(onceki.created_at).strftime("%d.%m.%Y")
    rapor.run_id = _record_run(rapor, status=CatalogImportStatus.DRY_RUN, acquisition=None)
    return rapor


@transaction.atomic
def apply_import(
    parsed: ParsedFile,
    *,
    payload_sha256: str,
    source: str = CatalogImportSource.EXCEL,
    file_name: str = "",
    decisions: Mapping[Any, Mapping[str, Any]] | None = None,
    section_map: Mapping[Any, Any] | None = None,
    new_sections: Sequence[str] | None = None,
    spec: AcquisitionSpec | None = None,
) -> CatalogImportReport:
    """Onaylanan aktarımı uygular (tek işlem; satır hatası partiyi düşürmez)."""
    plan = _plan(
        parsed.rows,
        decisions=_normalize_decisions(decisions),
        section_map=section_map or {},
        new_sections=new_sections or [],
    )
    _require_ready(plan, payload_sha256=payload_sha256)
    rapor, edinim = _ingest(
        parsed,
        plan=plan,
        spec=spec or AcquisitionSpec(),
        payload_sha256=payload_sha256,
        source=source,
        file_name=file_name,
    )
    rapor.run_id = _record_run(rapor, status=CatalogImportStatus.APPLIED, acquisition=edinim)
    logger.info(
        "Katalog aktarımı uygulandı: %d satır, %d yeni eser, %d mevcut eser, %d nüsha.",
        rapor.stats["total_rows"],
        rapor.stats["new_works"],
        rapor.stats["existing_matches"],
        rapor.stats["copies_created"],
    )
    return rapor


def _record_run(rapor: CatalogImportReport, *, status: str, acquisition: Acquisition | None) -> int:
    """Kalıcı koşu izi (önizleme: DRY_RUN, uygulama: APPLIED). Kişisel veri taşımaz."""
    kayit = CatalogImportRun.objects.create(
        uploaded_file_name=rapor.file_name[:255],
        source=rapor.source,
        payload_sha256=rapor.payload_sha256,
        schema_version=rapor.schema_version,
        status=status,
        acquisition=acquisition,
        stats=rapor.stats,
        report=rapor.to_run_dict(),
    )
    return int(kayit.pk)


def discard_run(run: CatalogImportRun) -> CatalogImportRun:
    """Önizlemeden vazgeçildi: koşu "İptal edildi" olur (yeniden deneme yolu açık)."""
    if run.status != CatalogImportStatus.DRY_RUN:
        raise ValidationError(
            {
                "status": (
                    "Yalnız önizleme koşusu iptal edilebilir; uygulanmış aktarım kayıtta kalır."
                )
            }
        )
    run.status = CatalogImportStatus.DISCARDED
    run.save(update_fields=["status", "updated_at"])
    return run
