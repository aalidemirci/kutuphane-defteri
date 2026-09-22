"""Katalog Excel sütun sözlüğü — TEK kaynak (tasarım §8.1, SU-10, SU-11, SU-24).

Tasarım §8.1: "Şablon ve sütun sözlüğü F1'de sabitlenir." Okul, katalog ekranları
gelmeden kitap listesini bu sözlüğe göre Excel'de hazırlamaya başlar; F3 içe
aktarımı AYNI sözlüğü okur. Bu yüzden buradaki anahtar, başlık, zorunluluk ve
değer kuralları sahayla yapılmış bir sözleşmedir: değişiklik, doldurulmuş
dosyaları bozmayacak biçimde yapılır (eşanlam ya da yeni isteğe bağlı sütun
eklenir; başlık silinmez, anlamı değişmez). Kim okur:

- `excel_template.py`: şablonun "Katalog", "Sütunlar" ve "Örnek" sayfaları;
- F3 içe aktarımı: başlık eşlemesi (`match_header`), değer kuralları
  (`yes_no_value`, `resource_type_value`, `defaults_to_reference`), varsayılanlar;
- `docs/katalog-excel-sablonu.md`: test, belgedeki sütun başlıklarının buradaki
  listeyle sırası ve zorunluluğuyla birebir aynı olduğunu denetler.

OYS `apps/kutuphane/import_schema.py`'den UYARLA (tasarım §12):

- OYS'nin 10 sütunluk `TEMPLATE_COLUMNS` ikilisi §8.1'in 16 sütunluk sözlüğüne
  genişledi: sınıflama kodu, dil, kaynak türü, eski kayıt no, ciltli süreli
  yayın, danışma kaynağı.
- Anahtarlar OYS JSON şeması v1 öğe alanlarıyla AYNIDIR (`title`, `authors`, …,
  `copies`, `shelf_location`) — AI köprüsü (§8.2) aynı adları kullanır. Yeni
  anahtarlar §6.2 `Copy` alan adlarını izler: `old_register_no`,
  `is_bound_periodical`, `is_reference`.
- Başlık eşlemesi TR katlamalıdır. OYS `normalize_text` yalnız `.lower()`
  yapıyordu: "KİTAP ADI" → "ki̇tap adi" (i + birleşik nokta) hiçbir şeyle
  eşleşmezdi (D2 sınıfı kusur). Katlama KS'nin sütun eşlemesiyle aynıdır
  (`apps.okul.excel_ogrenci.normalize_header`; §8.1 "KS'nin TR sütun
  eşlemesiyle"); ayrı bir katlama yazılmadı.
- Satır başına en çok 50 nüsha, ders kitabı → danışma varsayılanı, ciltli
  süreli yayın.
- OYS'nin AI JSON doğrulaması (`SCHEMA_VERSION`, `AI_PROMPT_V1`,
  `validate_payload`) F3'te (§8.2) bu modüle gelir; F1'de yalnız Excel sözlüğü var.

**Başlık eşleme kuralı: TAM eşleşme.** Katlanmış başlık, sözlükteki başlık ya da
eşanlamlılardan biriyle birebir aynı olmalıdır; alt dize eşlemesi YOKTUR. KS'nin
öğrenci ayrıştırıcısı alt dizeyle eşler ve sıra hassasiyeti taşır ("soyadi"
"adi"yi içerir). Katalogda "yayın" sözcüğü beş ayrı sütunun başlığında ya da
eşanlamında geçer ("Yayın Evi", "Yayın Yılı", "Yayın Dili", "Yayın Türü", "Ciltli
Süreli Yayın"); alt dize eşlemesi değeri sessizce yanlış sütuna yazardı.
Katlanmış hâlleri çakışan iki sütun modül yüklenirken `ValueError` verir; koruma
testi de sabitler.

**Nüsha kipi kararı** (§8.1 "nüsha sayısı ya da satır başına tek nüsha kipi",
SU-11): dosya düzeyinde ayrı bir kip anahtarı YOKTUR; kip satırdan okunur.

- *Toplu satır:* "Nüsha Sayısı" N (1-50) → aynı künye, aynı bölüm ve aynı
  bayraklarla N nüsha.
- *Tek nüsha satırı:* "Nüsha Sayısı" boş ya da 1 → bir nüsha. Aynı eserin her
  nüshası ayrı satıra yazılabilir; künyesi aynı satırlar içe aktarımda tek esere
  bağlanır (eşleşme kovaları, §8.1).
- "Eski Kayıt No" tek nüshaya aittir: dolu olduğu satırda nüsha sayısı 1'den
  büyükse satır önizlemede hatalı gösterilir ("her nüsha için ayrı satır").

Gerekçe: aynı dosyada iki yol karışabilir (eski numarası olan kitaplar tek tek,
numarasızlar toplu). Dosya düzeyi bir anahtar bunu yasaklardı; unutulduğunda da
bütün dosyayı yanlış yorumlatırdı.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from apps.okul.excel_ogrenci import normalize_header

#: Şablonun sayfa adları. İçe aktarım (F3) YALNIZ `CATALOG_SHEET`'i okur.
CATALOG_SHEET = "Katalog"
COLUMNS_SHEET = "Sütunlar"
EXAMPLE_SHEET = "Örnek"

#: Bir satırdan açılabilecek en çok nüsha (§8.1). Aşan satır önizlemede hatalıdır.
MAX_COPIES_PER_ROW = 50
#: "Nüsha Sayısı" boşsa bu kadar nüsha açılır.
DEFAULT_COPIES = 1

#: Evet/hayır sütunlarının şablondaki geçerli değerleri (veri doğrulama listesi).
YES = "Evet"
NO = "Hayır"
YES_NO_CHOICES: tuple[str, str] = (YES, NO)
#: İçe aktarımda tanınan evet/hayır yazımları (katlanmış). Excel'in DOĞRU/YANLIŞ
#: değerleri openpyxl'den `bool` gelir; `yes_no_value` onları da kabul eder.
_YES_TOKENS = frozenset({"evet", "e", "x", "var", "1"})
_NO_TOKENS = frozenset({"hayir", "h", "yok", "0"})

#: "Kaynak Türü" değerleri. "Ders kitabı" ayrı bir kaynak türü DEĞİLDİR (kitaptır);
#: danışma varsayılanını açmak için listede durur (§8.1, SU-24; Md. 14/1-a).
TEXTBOOK = "Ders kitabı"
DEFAULT_RESOURCE_TYPE = "Kitap"
RESOURCE_TYPE_CHOICES: tuple[str, ...] = (
    DEFAULT_RESOURCE_TYPE,
    TEXTBOOK,
    "Süreli yayın",
    "Görsel-işitsel materyal",
)
#: Seçenek → kaynak türü kodu (OYS `ResourceType`; F2 modeli aynı kodları taşır).
RESOURCE_TYPE_CODES: dict[str, str] = {
    DEFAULT_RESOURCE_TYPE: "BOOK",
    TEXTBOOK: "BOOK",
    "Süreli yayın": "PERIODICAL",
    "Görsel-işitsel materyal": "AV_MATERIAL",
}
#: Seçeneklerin yanında tanınan gündelik yazımlar (katlanmış anahtar → seçenek).
_RESOURCE_TYPE_ALIASES: dict[str, str] = {
    "dergi": "Süreli yayın",
    "gazete": "Süreli yayın",
    "cd": "Görsel-işitsel materyal",
    "dvd": "Görsel-işitsel materyal",
    "gorsel isitsel": "Görsel-işitsel materyal",
}

#: "Konu" sütununda birden çok konuyu ayıran işaretler.
_SUBJECT_SEPARATORS = re.compile(r"[,;]")


class ColumnKind(StrEnum):
    """Sütunun değer türü (İngilizce kod; kullanıcıya `accepted_values` metni gösterilir)."""

    TEXT = "text"
    INTEGER = "integer"
    YEAR = "year"
    ISBN = "isbn"
    YES_NO = "yes_no"
    CHOICE = "choice"


@dataclass(frozen=True, slots=True)
class CatalogColumn:
    """Sözlüğün bir sütunu. Kullanıcıya görünen metinler docs/sozluk.md'ye uyar."""

    #: İngilizce tanımlayıcı (OYS JSON v1 alanı ya da §6.2 model alanı).
    key: str
    #: Şablonda yazan başlık.
    header: str
    kind: ColumnKind
    #: "Ne yazılır?" — kullanıcı dilinde, tam cümle(ler).
    description: str
    #: Örnek değer ("Sütunlar" sayfası); boşsa "—" gösterilir.
    example: str = ""
    required: bool = False
    #: Kabul edilen başka başlıklar (TR katlamalı TAM eşleşir).
    synonyms: tuple[str, ...] = ()
    #: Boş hücrenin anlamı (kullanıcı metni); boşsa genel ifade kullanılır.
    when_blank: str = ""
    #: `CHOICE` sütunlarının geçerli değerleri.
    choices: tuple[str, ...] = ()
    #: `INTEGER` sütunlarının sınırları.
    min_value: int | None = None
    max_value: int | None = None

    @property
    def accepted_values(self) -> str:
        """Sütunlar sayfasındaki "Kabul edilen değerler" hücresi (kullanıcı metni)."""
        if self.kind is ColumnKind.YES_NO:
            return " / ".join(YES_NO_CHOICES)
        if self.kind is ColumnKind.CHOICE:
            return " / ".join(self.choices)
        if self.kind is ColumnKind.INTEGER:
            return f"{self.min_value}–{self.max_value} arası tam sayı"
        if self.kind is ColumnKind.YEAR:
            return "Dört haneli yıl"
        if self.kind is ColumnKind.ISBN:
            return "10 ya da 13 haneli numara"
        return "Serbest metin"

    @property
    def blank_rule(self) -> str:
        """Sütunlar sayfasındaki "Boş bırakılırsa" hücresi (kullanıcı metni)."""
        if self.required:
            return "Boş bırakılamaz"
        return self.when_blank or "Boş bırakılabilir"

    @property
    def is_text_formatted(self) -> bool:
        """Excel'de metin biçimli mi? ISBN bilimsel gösterime, "001.4" 1.4'e dönmesin."""
        return self.kind in (ColumnKind.TEXT, ColumnKind.ISBN)


# ---------------------------------------------------------------------------
# Sözlük (sıra = şablondaki sütun sırası = §8.1 sırası)
# ---------------------------------------------------------------------------
COLUMNS: tuple[CatalogColumn, ...] = (
    CatalogColumn(
        key="title",
        header="Eser Adı",
        kind=ColumnKind.TEXT,
        required=True,
        description=(
            "Eserin kapakta ya da iç kapakta yazan adı. Her satırda dolu olmalıdır; "
            "eser adı boş olan satır içe aktarılmaz."
        ),
        example="Kürk Mantolu Madonna",
        synonyms=(
            "Eserin Adı",
            "Eser",
            "Eser İsmi",
            "Kitap Adı",
            "Kitabın Adı",
            "Kitap İsmi",
            "Kitap",
            "Kaynak Adı",
            "Başlık",
            "Başlığı",
        ),
    ),
    CatalogColumn(
        key="authors",
        header="Yazar",
        kind=ColumnKind.TEXT,
        description=(
            "Yazarın adı ve soyadı, bu sırayla (ör. Sabahattin Ali). Birden çok yazar "
            "varsa adlarını virgülle ayırın. Yazarı belli olmayan eserde boş bırakın."
        ),
        example="Sabahattin Ali",
        synonyms=(
            "Yazarı",
            "Yazarlar",
            "Yazar(lar)",
            "Yazar Adı",
            "Yazarın Adı",
            "Yazar Adı Soyadı",
            "Yazarın Adı Soyadı",
            "Yazar Ad Soyad",
        ),
    ),
    CatalogColumn(
        key="translator",
        header="Çevirmen",
        kind=ColumnKind.TEXT,
        description=(
            "Çeviri eserde çevirmenin adı ve soyadı. Birden çok çevirmen varsa "
            "virgülle ayırın. Çeviri değilse boş bırakın."
        ),
        example="Yusuf Kâmil Paşa",
        synonyms=(
            "Çeviren",
            "Çevirenler",
            "Çevirmeni",
            "Çevirmenler",
            "Mütercim",
            "Tercüme Eden",
        ),
    ),
    CatalogColumn(
        key="publisher",
        header="Yayınevi",
        kind=ColumnKind.TEXT,
        description="Eseri yayımlayan yayınevinin adı.",
        example="Örnek Yayınevi",
        synonyms=("Yayın Evi", "Yayınevi Adı", "Yayıncı", "Yayımcı"),
    ),
    CatalogColumn(
        key="edition",
        header="Baskı",
        kind=ColumnKind.TEXT,
        description=(
            "Kaçıncı baskı olduğu (ör. 5. baskı). Künye sayfasında yazar; "
            "bilinmiyorsa boş bırakın."
        ),
        example="5. baskı",
        synonyms=("Baskı No", "Baskı Sayısı", "Baskısı", "Kaçıncı Baskı"),
    ),
    CatalogColumn(
        key="publish_year",
        header="Yayın Yılı",
        kind=ColumnKind.YEAR,
        description=(
            "Bu baskının yayımlandığı yıl, dört haneyle (ör. 2020). Bilinmiyorsa boş bırakın."
        ),
        example="2020",
        synonyms=(
            "Yıl",
            "Yayım Yılı",
            "Basım Yılı",
            "Baskı Yılı",
            "Yayın Tarihi",
            "Basım Tarihi",
        ),
    ),
    CatalogColumn(
        key="isbn",
        header="ISBN",
        kind=ColumnKind.ISBN,
        description=(
            "Kitabın arka kapağında ya da künye sayfasında yazan 10 ya da 13 haneli "
            "numara; tireli ya da tiresiz yazılabilir. Eski kitapların çoğunda "
            "yoktur; o zaman boş bırakın."
        ),
        synonyms=("ISBN No", "ISBN Numarası", "ISBN-13", "ISBN-10"),
    ),
    CatalogColumn(
        key="subjects",
        header="Konu",
        kind=ColumnKind.TEXT,
        description=(
            "Eserin konusu; birden çok konuyu virgülle ayırın (ör. Türk edebiyatı, "
            "roman). Roman, öykü, şiir gibi edebî türler de buraya yazılır. Konusu "
            f"“{TEXTBOOK}” olan eser danışma kaynağı sayılır."
        ),
        example="Türk edebiyatı, roman",
        synonyms=("Konusu", "Konular", "Konu(lar)", "Konu Başlığı", "Konu Başlıkları"),
    ),
    CatalogColumn(
        key="classification_code",
        header="Sınıflama Kodu",
        kind=ColumnKind.TEXT,
        description=(
            "Eserin sınıflama kodu; okul kütüphanelerinde genellikle Dewey Onlu "
            "Sınıflama (DOS) kodu kullanılır (ör. 894.353). Bilmiyorsanız boş "
            "bırakın; kod sonradan eklenebilir."
        ),
        example="894.353",
        synonyms=(
            "Sınıflama",
            "Sınıflama No",
            "Sınıflama Numarası",
            "Tasnif",
            "Tasnif No",
            "Tasnif Kodu",
            "DOS",
            "DOS Kodu",
            "DOS No",
            "Dewey",
            "Dewey No",
            "Dewey Kodu",
        ),
    ),
    CatalogColumn(
        key="language",
        header="Dil",
        kind=ColumnKind.TEXT,
        description=(
            "Eserin dili (ör. Türkçe, İngilizce, Osmanlı Türkçesi). Çeviri eserde "
            "çevrildiği dil yazılır."
        ),
        example="Türkçe",
        synonyms=("Dili", "Yayın Dili", "Eserin Dili"),
    ),
    CatalogColumn(
        key="resource_type",
        header="Kaynak Türü",
        kind=ColumnKind.CHOICE,
        choices=RESOURCE_TYPE_CHOICES,
        when_blank=f"“{DEFAULT_RESOURCE_TYPE}” sayılır",
        description=(
            "Dergi ve gazete “Süreli yayın”, CD ve DVD gibi kaynaklar “Görsel-işitsel "
            "materyal”dir; süreli yayınlar ödünç verilmez. “Ders kitabı” yazılan eser "
            "danışma kaynağı sayılır. Roman, şiir gibi edebî türler bu sütuna değil "
            "“Konu” sütununa yazılır."
        ),
        example=DEFAULT_RESOURCE_TYPE,
        synonyms=(
            "Tür",
            "Türü",
            "Kaynak Tipi",
            "Kaynağın Türü",
            "Materyal Türü",
            "Yayın Türü",
        ),
    ),
    CatalogColumn(
        key="copies",
        header="Nüsha Sayısı",
        kind=ColumnKind.INTEGER,
        min_value=1,
        max_value=MAX_COPIES_PER_ROW,
        when_blank=f"{DEFAULT_COPIES} sayılır",
        description=(
            "Bu satırdaki eserden kütüphanede kaç nüsha bulunduğu. Bir satırda en çok "
            f"{MAX_COPIES_PER_ROW} nüsha açılır; daha fazlası varsa eseri birkaç "
            "satıra bölün. “Eski Kayıt No” yazdığınız satırda nüsha sayısı 1 olmalıdır."
        ),
        example="3",
        synonyms=(
            "Nüsha",
            "Nüsha Adedi",
            "Adet",
            "Adedi",
            "Miktar",
            "Kitap Sayısı",
            "Kitap Adedi",
        ),
    ),
    CatalogColumn(
        key="shelf_location",
        header="Bölüm",
        kind=ColumnKind.TEXT,
        description=(
            "Nüshanın kütüphanede durduğu bölümün adı (ör. Edebiyat, Tarih, Danışma). "
            "Program bu adları kendi bölüm listesiyle eşleştirir; listede bulunmayan "
            "ad, içe aktarmadan önceki önizlemede size sorulur."
        ),
        example="Edebiyat",
        synonyms=(
            "Bölümü",
            "Kütüphane Bölümü",
            "Bölüm/Raf",
            "Raf",
            "Raf No",
            "Raf Numarası",
            "Raf Konumu",
            "Raf Yeri",
        ),
    ),
    CatalogColumn(
        key="old_register_no",
        header="Eski Kayıt No",
        kind=ColumnKind.TEXT,
        description=(
            "Kitapta damgalı ya da elle yazılmış eski kayıt numarası ya da eski "
            "kütüphane defterindeki sıra numarası; isteğe bağlıdır. Bir eski kayıt no "
            "tek nüshaya aittir: bu sütunu doldurduğunuz satırda nüsha sayısı 1 "
            "olmalıdır, aynı eserin öbür nüshaları için ayrı satır açın."
        ),
        example="1452",
        synonyms=(
            "Eski Kayıt Numarası",
            "Eski No",
            "Eski Numara",
            "Eski Demirbaş No",
            "Demirbaş No",
            "Demirbaş Numarası",
            "Envanter No",
            "Defter No",
            "Defter Sıra No",
        ),
    ),
    CatalogColumn(
        key="is_bound_periodical",
        header="Ciltli Süreli Yayın",
        kind=ColumnKind.YES_NO,
        when_blank=f"“{NO}” sayılır",
        description=(
            "Yalnız kaynak türü “Süreli yayın” olan satırda kullanılır. Dergi ya da "
            "gazete sayıları ciltletilip tek cilt olarak duruyorsa “Evet” yazın. "
            "Ciltletilmemiş süreli yayın taşınır kaydına alınmaz (Taşınır Mal "
            "Yönetmeliği Md. 15/4)."
        ),
        example=YES,
        synonyms=("Ciltli", "Ciltli mi", "Ciltli Dergi", "Ciltli Yayın"),
    ),
    CatalogColumn(
        key="is_reference",
        header="Danışma Kaynağı",
        kind=ColumnKind.YES_NO,
        when_blank=f"“{NO}” sayılır; kaynak türü ya da konusu “{TEXTBOOK}” ise “{YES}” sayılır",
        description=(
            "“Evet” yazılan nüsha ödünç verilmez, kütüphanede okunur. Ders kitapları, "
            "ansiklopediler, sözlükler, atlaslar, yıllıklar ve rehberler danışma "
            "kaynağıdır (Okul Kütüphaneleri Yönetmeliği Md. 14/1-a, 16/1-a). Kaynak "
            f"türü ya da konusu “{TEXTBOOK}” olan satırda bu sütun boşsa “Evet” sayılır "
            "ve içe aktarmadan önceki önizlemede gösterilir."
        ),
        example=YES,
        synonyms=("Danışma", "Danışma Kaynağı mı", "Danışma Dermesi", "Ödünç Verilmez"),
    ),
)

COLUMNS_BY_KEY: dict[str, CatalogColumn] = {column.key: column for column in COLUMNS}
REQUIRED_KEYS: tuple[str, ...] = tuple(column.key for column in COLUMNS if column.required)


# ---------------------------------------------------------------------------
# Başlık eşlemesi (TR katlamalı, TAM eşleşme)
# ---------------------------------------------------------------------------
def fold(value: object) -> str:
    """TR katlama: Türkçe harf → ASCII küçük harf, harf/rakam dışı → tek boşluk.

    KS sütun eşlemesinin katlamasıdır ('Kitabın Adı' → 'kitabin adi',
    'KİTAP ADI' → 'kitap adi'); başlıkta da değerde de aynı kural geçer.
    """
    return normalize_header(value)


def build_header_index(columns: Iterable[CatalogColumn]) -> dict[str, str]:
    """Katlanmış başlık/eşanlam → sütun anahtarı dizini; çakışmada `ValueError`.

    Aynı sütunun iki yazımının aynı katlanmış biçime düşmesi zararsızdır; iki
    AYRI sütunun düşmesi, dosyadaki bir sütunun hangi alana yazılacağını belirsiz
    bırakır ve modül yüklenirken reddedilir.
    """
    index: dict[str, str] = {}
    keys: set[str] = set()
    for column in columns:
        if column.key in keys:
            raise ValueError(f"Sözlükte yinelenen anahtar: {column.key!r}")
        keys.add(column.key)
        for label in (column.header, *column.synonyms):
            folded = fold(label)
            if not folded:
                raise ValueError(f"{column.key!r} sütununda boş başlık: {label!r}")
            owner = index.setdefault(folded, column.key)
            if owner != column.key:
                raise ValueError(
                    f"{label!r} başlığı hem {owner!r} hem {column.key!r} sütununa eşleniyor "
                    f"(katlanmış hâli {folded!r})."
                )
    return index


_HEADER_INDEX = build_header_index(COLUMNS)


def match_header(cell: object) -> str | None:
    """Başlık hücresini sütun anahtarına eşler; tanınmayan başlıkta `None`."""
    return _HEADER_INDEX.get(fold(cell))


# ---------------------------------------------------------------------------
# Değer kuralları (şablonun ve kılavuzun söz verdiği yorum — F3 bunları kullanır)
# ---------------------------------------------------------------------------
class CatalogValueError(ValueError):
    """Hücre değeri sütunun kabul ettiği değerlerden biri değil (kullanıcı iletisi)."""


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def yes_no_value(value: object) -> bool | None:
    """Evet/hayır hücresi → `True`/`False`; boş hücre → `None` (varsayılan uygulanır)."""
    if isinstance(value, bool):  # Excel DOĞRU/YANLIŞ
        return value
    if _is_blank(value):
        return None
    folded = fold(value)
    if folded in _YES_TOKENS:
        return True
    if folded in _NO_TOKENS:
        return False
    raise CatalogValueError(f"“{value}” tanınmadı; “{YES}” ya da “{NO}” yazın.")


def resource_type_value(value: object) -> str:
    """Kaynak türü hücresi → `RESOURCE_TYPE_CHOICES`'tan biri; boşsa varsayılan."""
    if _is_blank(value):
        return DEFAULT_RESOURCE_TYPE
    folded = fold(value)
    for choice in RESOURCE_TYPE_CHOICES:
        if fold(choice) == folded:
            return choice
    alias = _RESOURCE_TYPE_ALIASES.get(folded)
    if alias is not None:
        return alias
    raise CatalogValueError(
        f"“{value}” kaynak türü olarak tanınmadı; şunlardan birini yazın: "
        + ", ".join(RESOURCE_TYPE_CHOICES)
        + "."
    )


def defaults_to_reference(resource_type: object, subjects: object) -> bool:
    """Kaynak türü ya da konulardan biri "Ders kitabı" mı? (§8.1, SU-24; Md. 14/1-a)

    Doğruysa "Danışma Kaynağı" boş hücrede "Evet" sayılır. Konu virgül ya da
    noktalı virgülle ayrılmış liste olarak okunur; eşleşme TAMDIR ("Ders
    kitapları üzerine inceleme" konusu danışma varsayılanını açmaz).
    """
    target = fold(TEXTBOOK)
    if fold(resource_type) == target:
        return True
    text = "" if subjects is None else str(subjects)
    return any(fold(part) == target for part in _SUBJECT_SEPARATORS.split(text))
