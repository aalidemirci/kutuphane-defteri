"""Katalog sütun sözlüğü (tasarım §8.1 "F1'de sabitlenir") — sözleşme testleri.

Sözlük sahayla yapılmış bir sözleşmedir: okul katalog ekranları gelmeden Excel'i
bu başlıklarla doldurur, F3 içe aktarımı AYNI sözlüğü okur. Anlık görüntü testi
anahtar/başlık/zorunluluk/tür değişikliğini bilinçli bir karara bağlar: değiştiren
kişi doldurulmuş dosyaların bozulup bozulmadığını düşünmek ve burayı güncellemek
zorundadır. Başlık silmek ya da anlamını değiştirmek yerine eşanlam eklenir.
"""

from __future__ import annotations

import re

import pytest

from apps.kutuphane import import_schema
from apps.kutuphane.import_schema import (
    COLUMNS,
    COLUMNS_BY_KEY,
    DEFAULT_COPIES,
    DEFAULT_RESOURCE_TYPE,
    MAX_COPIES_PER_ROW,
    REQUIRED_KEYS,
    RESOURCE_TYPE_CHOICES,
    RESOURCE_TYPE_CODES,
    TEXTBOOK,
    CatalogColumn,
    CatalogValueError,
    ColumnKind,
    build_header_index,
    defaults_to_reference,
    match_header,
    resource_type_value,
    yes_no_value,
)

#: (anahtar, başlık, zorunlu mu, tür) — sıra şablondaki sütun sırasıdır.
SOZLUK_ANLIK_GORUNTUSU: list[tuple[str, str, bool, str]] = [
    ("title", "Eser Adı", True, "text"),
    ("authors", "Yazar", False, "text"),
    ("translator", "Çevirmen", False, "text"),
    ("publisher", "Yayınevi", False, "text"),
    ("edition", "Baskı", False, "text"),
    ("publish_year", "Yayın Yılı", False, "year"),
    ("isbn", "ISBN", False, "isbn"),
    ("subjects", "Konu", False, "text"),
    ("classification_code", "Sınıflama Kodu", False, "text"),
    ("language", "Dil", False, "text"),
    ("resource_type", "Kaynak Türü", False, "choice"),
    ("copies", "Nüsha Sayısı", False, "integer"),
    ("shelf_location", "Bölüm", False, "text"),
    ("old_register_no", "Eski Kayıt No", False, "text"),
    ("is_bound_periodical", "Ciltli Süreli Yayın", False, "yes_no"),
    ("is_reference", "Danışma Kaynağı", False, "yes_no"),
]

#: OYS JSON şeması v1 öğe alanları (AI köprüsü, §8.2) — sözlük anahtarları bunları korur.
OYS_V1_ALANLARI = frozenset(
    {
        "title",
        "authors",
        "translator",
        "publisher",
        "edition",
        "publish_year",
        "isbn",
        "subjects",
        "classification_code",
        "language",
        "resource_type",
        "copies",
        "shelf_location",
    }
)

#: Kullanıcı metninde geçmeyecek iç kodlar (docs/sozluk.md §2).
_IC_KOD = re.compile(r"\b[UTAFSDE]\d{1,2}\b|\b(?:GA|KM|UY|SU|EK|AT|V2)-\d")
#: Sözlüğün "Kullanılmaz" sütunundan bu metinlerde geçebilecek olanlar.
_YASAK_SOZCUKLER = (
    "şifre",
    "kopya",
    "demirbaş",
    "dewey numarası",
    "ddc",
    "referans",
    "lokasyon",
    "raf kodu",
    "okuduğu",
)


def test_sozluk_anlik_goruntusu() -> None:
    gercek = [(c.key, c.header, c.required, c.kind.value) for c in COLUMNS]
    assert gercek == SOZLUK_ANLIK_GORUNTUSU


def test_anahtarlar_oys_json_v1_oge_alanlarini_korur() -> None:
    """AI köprüsü (§8.2) OYS şemasını korur; Excel sözlüğü aynı adları kullanır."""
    assert set(COLUMNS_BY_KEY) >= OYS_V1_ALANLARI
    # Yeni anahtarlar §6.2 Copy alan adlarıdır.
    assert set(COLUMNS_BY_KEY) - OYS_V1_ALANLARI == {
        "old_register_no",
        "is_bound_periodical",
        "is_reference",
    }


def test_yalniz_eser_adi_zorunludur() -> None:
    assert REQUIRED_KEYS == ("title",)
    assert COLUMNS_BY_KEY["title"].blank_rule == "Boş bırakılamaz"


def test_nusha_sutunu_bir_ile_elli_arasindadir() -> None:
    """§8.1: satır başına en çok 50 nüsha; boş hücre 1 nüsha."""
    nusha = COLUMNS_BY_KEY["copies"]
    assert MAX_COPIES_PER_ROW == 50
    assert (nusha.min_value, nusha.max_value) == (1, MAX_COPIES_PER_ROW)
    assert DEFAULT_COPIES == 1
    assert f"en çok {MAX_COPIES_PER_ROW} nüsha" in nusha.description
    assert nusha.accepted_values == "1–50 arası tam sayı"
    assert nusha.blank_rule == "1 sayılır"


def test_eski_kayit_no_tek_nushaya_aittir_kurali_iki_sutunda_da_yazar() -> None:
    """Nüsha kipi kararı (modül başlığı): eski kayıt no dolu satırda nüsha sayısı 1."""
    assert "nüsha sayısı 1" in COLUMNS_BY_KEY["old_register_no"].description
    assert "nüsha sayısı 1" in COLUMNS_BY_KEY["copies"].description


def test_kaynak_turu_secenekleri_ve_kodlari() -> None:
    kolon = COLUMNS_BY_KEY["resource_type"]
    assert kolon.choices == RESOURCE_TYPE_CHOICES
    assert set(RESOURCE_TYPE_CODES) == set(RESOURCE_TYPE_CHOICES)
    # "Ders kitabı" ayrı bir kaynak türü değildir; kitaptır ve danışma varsayılanını açar.
    assert RESOURCE_TYPE_CODES[TEXTBOOK] == "BOOK"
    assert DEFAULT_RESOURCE_TYPE in RESOURCE_TYPE_CHOICES
    assert kolon.blank_rule == "“Kitap” sayılır"


# ---------------------------------------------------------------------------
# Başlık eşlemesi
# ---------------------------------------------------------------------------
def test_basliklar_ve_esanlamlilar_tr_katlamali_sutunlar_arasinda_cakismaz() -> None:
    """Koruma testi: iki AYRI sütunun katlanmış başlığı aynı olamaz.

    Dizin modül yüklenirken de aynı denetimle kurulur; bu test çakışmayı
    dizinden bağımsız olarak yeniden hesaplar.
    """
    sahip: dict[str, str] = {}
    for kolon in COLUMNS:
        for etiket in (kolon.header, *kolon.synonyms):
            katli = import_schema.fold(etiket)
            assert katli, etiket
            onceki = sahip.setdefault(katli, kolon.key)
            assert onceki == kolon.key, f"{etiket!r}: {onceki} ile {kolon.key} çakışıyor"


def test_katlama_turkce_harfleri_ayni_bicime_indirir() -> None:
    fold = import_schema.fold
    assert fold("KİTAP ADI") == fold("kitap adı") == fold("Kitap  Adı ") == "kitap adi"
    assert fold("ŞİİR") == fold("şiir") == "siir"
    assert fold("ILIK") == fold("ılık") == "ilik"


def test_cakisma_denetimi_iki_sutunu_ayni_basliga_baglamayi_reddeder() -> None:
    a = CatalogColumn(key="a", header="Kitap Adı", kind=ColumnKind.TEXT, description="A.")
    b = CatalogColumn(
        key="b", header="Yazar", kind=ColumnKind.TEXT, description="B.", synonyms=("KİTAP ADI",)
    )
    with pytest.raises(ValueError, match="hem 'a' hem 'b'"):
        build_header_index([a, b])


def test_ayni_sutunun_iki_yazimi_catismaz() -> None:
    a = CatalogColumn(
        key="a", header="Nüsha", kind=ColumnKind.TEXT, description="A.", synonyms=("NÜSHA",)
    )
    assert build_header_index([a]) == {"nusha": "a"}


def test_yinelenen_anahtar_reddedilir() -> None:
    a = CatalogColumn(key="a", header="Bir", kind=ColumnKind.TEXT, description="A.")
    b = CatalogColumn(key="a", header="İki", kind=ColumnKind.TEXT, description="B.")
    with pytest.raises(ValueError, match="yinelenen anahtar"):
        build_header_index([a, b])


def test_sablondaki_her_baslik_kendi_anahtarina_eslenir() -> None:
    for kolon in COLUMNS:
        assert match_header(kolon.header) == kolon.key
        for esanlam in kolon.synonyms:
            assert match_header(esanlam) == kolon.key, esanlam


@pytest.mark.parametrize(
    ("baslik", "anahtar"),
    [
        ("ESER ADI", "title"),
        ("eser adı", "title"),
        ("  Eser   Adı  ", "title"),
        ("KİTAP ADI", "title"),
        ("Kitabın Adı", "title"),
        ("YAZARI", "authors"),
        ("Yazar(lar)", "authors"),
        ("ÇEVİREN", "translator"),
        ("Yayın Evi", "publisher"),
        ("BASIM YILI", "publish_year"),
        ("isbn", "isbn"),
        ("ISBN-13", "isbn"),
        ("Konu(lar)", "subjects"),
        ("SINIFLAMA KODU", "classification_code"),
        ("DİLİ", "language"),
        ("Tür", "resource_type"),
        ("ADET", "copies"),
        ("Nüsha Sayısı", "copies"),
        ("RAF", "shelf_location"),
        ("Bölüm/Raf", "shelf_location"),
        ("ESKİ KAYIT NO", "old_register_no"),
        ("Ciltli mi?", "is_bound_periodical"),
        ("DANIŞMA", "is_reference"),
    ],
)
def test_baslik_eslemesi_tr_katlamali_ve_buyuk_kucuk_harfe_duyarsiz(
    baslik: str, anahtar: str
) -> None:
    assert match_header(baslik) == anahtar


@pytest.mark.parametrize(
    "baslik",
    [
        # Programın kendi "kayıt no"su (barkodun sayı hâli) ile karışmasın diye TANINMAZ.
        "Kayıt No",
        # Dergide "sayı" dergi sayısıdır, nüsha sayısı değil.
        "Sayı",
        # Tek başına "Adı" yazar adı da olabilir.
        "Adı",
        # Yer numarası sınıflama kodu + yazar kodudur, yalnız sınıflama kodu değil.
        "Yer Numarası",
        # Alt dize eşlemesi YOK.
        "Eser Adı ve Yazarı",
        "",
        None,
    ],
)
def test_taninmayan_baslik_eslenmez(baslik: str | None) -> None:
    assert match_header(baslik) is None


# ---------------------------------------------------------------------------
# Değer kuralları
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("deger", "beklenen"),
    [
        ("Evet", True),
        ("EVET", True),
        ("e", True),
        ("X", True),
        ("Hayır", False),
        ("HAYIR", False),
        ("hayir", False),
        ("H", False),
        ("yok", False),
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_evet_hayir_degeri(deger: object, beklenen: bool | None) -> None:
    assert yes_no_value(deger) is beklenen


def test_taninmayan_evet_hayir_degeri_kullanici_iletisiyle_reddedilir() -> None:
    with pytest.raises(CatalogValueError, match="“Evet” ya da “Hayır” yazın"):
        yes_no_value("belki")


@pytest.mark.parametrize(
    ("deger", "beklenen"),
    [
        (None, "Kitap"),
        ("", "Kitap"),
        ("kitap", "Kitap"),
        ("DERS KİTABI", "Ders kitabı"),
        ("Süreli Yayın", "Süreli yayın"),
        ("dergi", "Süreli yayın"),
        ("GAZETE", "Süreli yayın"),
        ("Görsel işitsel materyal", "Görsel-işitsel materyal"),
        ("DVD", "Görsel-işitsel materyal"),
    ],
)
def test_kaynak_turu_degeri(deger: object, beklenen: str) -> None:
    assert resource_type_value(deger) == beklenen


def test_edebi_tur_kaynak_turu_sayilmaz() -> None:
    """Tür sütununa yazılmış "Roman" sessizce kitaba çevrilmez; önizleme sorar."""
    with pytest.raises(CatalogValueError, match="kaynak türü olarak tanınmadı"):
        resource_type_value("Roman")


@pytest.mark.parametrize(
    ("kaynak_turu", "konu", "beklenen"),
    [
        ("Ders kitabı", "", True),
        ("DERS KİTABI", None, True),
        ("Kitap", "Matematik, ders kitabı", True),
        ("", "Ders Kitabı; Fizik", True),
        ("Kitap", "Türk edebiyatı, roman", False),
        # Eşleşme tamdır: "ders kitapları" üzerine bir inceleme danışma değildir.
        ("Kitap", "Ders kitapları üzerine inceleme", False),
        (None, None, False),
    ],
)
def test_ders_kitabi_danisma_varsayilanini_acar(
    kaynak_turu: object, konu: object, beklenen: bool
) -> None:
    """§8.1, SU-24: tür ya da konu "ders kitabı" ise danışma varsayılan olarak açık."""
    assert defaults_to_reference(kaynak_turu, konu) is beklenen


def test_danisma_sutunu_ders_kitabi_kuralini_soyler() -> None:
    danisma = COLUMNS_BY_KEY["is_reference"]
    assert "Ders kitabı" in danisma.blank_rule
    assert "Md. 14/1-a, 16/1-a" in danisma.description
    assert "önizlemede" in danisma.description


# ---------------------------------------------------------------------------
# Kullanıcı metni
# ---------------------------------------------------------------------------
def _kullanici_metinleri(kolon: CatalogColumn) -> list[str]:
    return [
        kolon.header,
        kolon.description,
        kolon.accepted_values,
        kolon.blank_rule,
        kolon.example,
    ]


def test_aciklamalar_tam_cumledir() -> None:
    for kolon in COLUMNS:
        assert kolon.description.strip(), kolon.key
        assert kolon.description.endswith("."), kolon.key


def test_kullanici_metni_ic_kod_ve_sozlukte_yasak_sozcuk_tasimaz() -> None:
    """docs/sozluk.md §1-2: iç kodlar ve "Kullanılmaz" sütunu yüzeye çıkmaz.

    Eşanlamlılar kullanıcıya gösterilmez (yalnız okulun eski listesini tanır);
    "Demirbaş No" gibi bir eşanlam bu yüzden serbesttir, kapsam dışıdır.
    """
    for kolon in COLUMNS:
        for metin in _kullanici_metinleri(kolon):
            assert not _IC_KOD.search(metin), (kolon.key, metin)
            kucuk = metin.casefold()
            for yasak in _YASAK_SOZCUKLER:
                assert yasak not in kucuk, (kolon.key, yasak)
