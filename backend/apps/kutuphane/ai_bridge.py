"""Yapay zekâ köprüsü — JSON şeması v1, komut metni ve arayüz uyarıları (tasarım §8.2).

**Program hiçbir yapay zekâ servisine BAĞLANMAZ.** Köprü bir *metin* köprüsüdür:
kullanıcı komut metnini panodan kendi aracına yapıştırır, dönen JSON'u programa
yükler. Bu modülde ağ çağrısı yoktur ve olmayacaktır; koruma testi
(`tests/test_ice_aktarma_dis_istek.py`) içe aktarma hattının tamamında dış
bağlantı aranmadığını sabitler (§8.5 kural 2, §5.10-19-a).

OYS'nin (Okul Yönetim Sistemi) `apps/kutuphane/import_schema.py` dosyasındaki
`SCHEMA_VERSION`, `AI_PROMPT_V1` ve `validate_payload` bölümünden UYARLA
(tasarım §12); Excel sütun sözlüğü F1'de `import_schema.py`'ye ayrıldığı için
köprü kendi modülünde durur. Uyarlamalar:

- **"Dewey" ifadesi genelleştirildi** (§8.2): komut "sınıflama kodu (tahmini)"
  der. OYS komutu aracı "Milli Kütüphane, TO-KAT" adreslerinde araştırmaya
  yönlendiriyordu; TO-KAT `robots.txt` ile kazımayı tümden yasaklar (§8.5) ve
  programın komutu bir aracı oraya yönlendiremez.
- **Komuta yalnız künye alanları girer** (§8.2): demirbaş no / eski kayıt no,
  edinim ve bağışçı bilgisi komutta GEÇMEZ. Dönen JSON'da yine de bulunurlarsa
  `validate_payload` onları YOK SAYAR ve satır uyarısı yazar — kullanıcı neyin
  alınmadığını görür (sessiz düşürme, sessiz yazmadan daha az kötü ama yine de
  söylenmelidir).
- **Şema sürümü korunur (`v1`)**: alan eklendiğinde sürüm yükseltilir ve eski
  koşular `CatalogImportRun.schema_version` ile izlenir.
- Satır düzeyi sorunlar HATA DEĞİLDİR: `issues` listesine yazılır, parti düşmez.
  Şema uyumsuzluğu (sürüm, `items` yok) `AiBridgeError`'dır.

`classification_source` alanı kataloğa aynen geçer: `ESTIMATED` kodlar arayüzde
"tahmini" rozetiyle görünür (§8.2, `models.ClassificationSource`).
"""

from __future__ import annotations

from typing import Any

from apps.kutuphane.import_schema import COLUMNS_BY_KEY, MAX_COPIES_PER_ROW

#: Şema sürümü (OYS v1 ile aynı alan kümesi). Alan değişirse yükseltilir.
SCHEMA_VERSION = "v1"

#: Köprünün kabul ettiği kaynak türü kodları (dijital kaynak köprüden gelmez:
#: e-kitap ve e-veri tabanının nüshası açılamaz, toplu aktarım nüsha açar).
VALID_RESOURCE_TYPES: frozenset[str] = frozenset({"BOOK", "PERIODICAL", "AV_MATERIAL"})
DEFAULT_RESOURCE_TYPE = "BOOK"

#: Sınıflama kodunun kaynağı (`models.ClassificationSource` ile aynı kodlar).
VALID_CLASSIFICATION_SOURCES: frozenset[str] = frozenset({"CATALOG", "ESTIMATED", "MANUAL"})
DEFAULT_CLASSIFICATION_SOURCE = "MANUAL"

#: Köprüden gelen künye alanları (Excel sözlüğünün künye sütunlarıyla AYNI adlar).
ITEM_KEYS: tuple[str, ...] = (
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
)

#: Komuta girmeyen, dönen JSON'da bulunsa da YOK SAYILAN alanlar (§8.2).
#: Anahtar → kullanıcıya gösterilecek ad (satır uyarısında geçer).
IGNORED_KEYS: dict[str, str] = {
    "old_register_no": "Eski Kayıt No",
    "accession_no": "kayıt no",
    "barcode": "barkod",
    "external_asset_ref": "TKYS kodu",
    "donor_name": "bağışçı",
    "acquisition": "edinim",
    "unit_price": "birim fiyat",
    "price": "fiyat",
}

#: Kullanıcıya gösterilen uyarı maddeleri — §8.2'nin dört maddesi, aynen ve bu
#: sırayla. Ekran metni bu listeden gelir (tek kaynak; ön yüz kopya yazmaz).
UI_NOTES: tuple[str, ...] = (
    "Listede kişisel veri bulunmamalıdır: öğrenci, veli, personel ya da bağışçı adı "
    "yazılmaz. Köprüye yalnız kitapların künye bilgileri girer.",
    "Listeyi dış hizmete programa değil, kullanıcı kendisi taşır: komut metnini "
    "kopyalayıp aracınıza yapıştırırsınız, dönen JSON'u buraya yüklersiniz.",
    "Program hiçbir yapay zekâ servisine bağlanmaz; internet bağlantısı kurmaz.",
    "Bu adım okulun kitap listesinin dışarıya çıkması demektir ve MEB Bilgi ve Sistem "
    "Güvenliği Yönergesi'nin 11/23 ile 11/3-h ve 11/3-ı maddeleriyle çatışabilir. "
    "Asıl yol Excel ile içe aktarmadır; künye eksiğini kapatmak için ISBN ile künye "
    "getirme daha güvenlidir (dışarıya yalnız kitabın arka kapağındaki numara çıkar).",
)


def _header(key: str) -> str:
    """Sütunun Excel sözlüğündeki Türkçe başlığı (komut metni sözlükten beslenir)."""
    return COLUMNS_BY_KEY[key].header


def build_prompt() -> str:
    """Panoya kopyalanan komut metni (kullanıcı Excel tablosunu altına yapıştırır).

    Metin sözlükten beslenir: sütun başlıkları `import_schema.COLUMNS`'tan gelir,
    nüsha sınırı tek sabittendir. Komutta demirbaş no, edinim ve bağışçı GEÇMEZ.
    """
    return f"""Aşağıdaki tabloda bir okul kütüphanesinin kitap listesi var. Bu listeyi \
kütüphane programının toplu katalog aktarımı için JSON'a dönüştür. KURALLAR:

1) Çıktı YALNIZCA şu biçimde geçerli bir JSON olsun (açıklama, markdown, kod
   çerçevesi ekleme):
   {{"schema_version": "{SCHEMA_VERSION}", "items": [ ... ]}}
   Her öğe şu alanları taşır:
   title (zorunlu — {_header("title")}), authors ({_header("authors")}),
   translator ({_header("translator")}), publisher ({_header("publisher")}),
   edition ({_header("edition")}), publish_year (dört haneli sayı ya da null),
   isbn ({_header("isbn")}), subjects ({_header("subjects")}),
   classification_code ({_header("classification_code")}),
   classification_source ("CATALOG" | "ESTIMATED"),
   language ({_header("language")}),
   resource_type ("BOOK" | "PERIODICAL" | "AV_MATERIAL"; varsayılan "BOOK"),
   copies (nüsha sayısı, 1-{MAX_COPIES_PER_ROW} arası sayı),
   shelf_location ({_header("shelf_location")}),
   corrections (liste), issues (liste).

2) Yanlış yazılmış eser ve yazar adlarını düzelt. HER düzeltmeyi corrections
   listesine {{"field": "...", "original": "...", "corrected": "..."}} biçiminde
   yaz. Sessiz düzeltme YAPMA: düzeltmeyi mutlaka corrections'a ekle.

3) Sınıflama kodunu (okul kütüphanelerinde genellikle Dewey Onlu Sınıflama kodu)
   güvenilir bir kütüphane kataloğunda bulabilirsen yaz ve
   classification_source: "CATALOG" işaretle. Bulamazsan en yakın kategoriden
   TAHMİN ver ve classification_source: "ESTIMATED" işaretle; tahmini kodlar
   programda "tahmini" rozetiyle görünecek ve kullanıcı onları denetleyecek.

4) Belirsiz ya da eksik satırları issues listesine yaz. Bilgi UYDURMA: emin
   değilsen alanı boş bırak ve issues'a not düş.

5) Listeye kişisel veri yazma; demirbaş numarası, edinim bilgisi ve bağışçı adı
   bu JSON'a GİRMEZ.

Tablo:
"""


#: Ön yüzün panoya kopyaladığı hazır komut (tek kaynak).
AI_PROMPT = build_prompt()


class AiBridgeError(ValueError):
    """Yüklenen JSON şemaya uymuyor — Türkçe açıklamalar `errors` listesindedir."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(" ".join(errors[:5]))
        self.errors = errors


def _text(value: Any) -> str:
    """Metin alanı: `None` boş dizeye iner, kenar boşlukları kırpılır."""
    if value is None or isinstance(value, bool):
        return ""
    return str(value).strip()


def _int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    """`issues` gibi serbest listeler: öğeler metne indirilir, boşlar atılır."""
    if not isinstance(value, list):
        return []
    return [metin for metin in (_text(oge) for oge in value) if metin]


def _corrections(value: Any) -> list[dict[str, str]]:
    """Düzeltme listesi: yalnız `field`/`original`/`corrected` alanları alınır."""
    if not isinstance(value, list):
        return []
    sonuc: list[dict[str, str]] = []
    for oge in value:
        if not isinstance(oge, dict):
            continue
        duzeltme = {
            "field": _text(oge.get("field")),
            "original": _text(oge.get("original")),
            "corrected": _text(oge.get("corrected")),
        }
        if duzeltme["field"] or duzeltme["corrected"]:
            sonuc.append(duzeltme)
    return sonuc


def _clean_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Bir öğeyi temizler; satır düzeyi sorunlar `issues`'a yazılır (parti düşmez)."""
    issues = _string_list(raw.get("issues"))

    for anahtar, ad in IGNORED_KEYS.items():
        if _text(raw.get(anahtar)):
            issues.append(
                f"“{ad}” bilgisi yapay zekâ köprüsüyle alınmaz; yok sayıldı. "
                "Bu bilgiyi programda elle girin."
            )

    resource_type = _text(raw.get("resource_type")) or DEFAULT_RESOURCE_TYPE
    # ASCII kod: çıplak `.upper()` Türkçe metne uygulanmaz (CLAUDE.md §2-9);
    # burada değer bir kod olduğu için ASCII karşılığıyla karşılaştırılır.
    resource_type = resource_type.translate(str.maketrans("ıİşŞğĞüÜöÖçÇ", "iISsgGuUoOcC")).upper()
    if resource_type not in VALID_RESOURCE_TYPES:
        issues.append(f"“{_text(raw.get('resource_type'))}” kaynak türü tanınmadı; kitap sayıldı.")
        resource_type = DEFAULT_RESOURCE_TYPE

    source = _text(raw.get("classification_source")).upper() or DEFAULT_CLASSIFICATION_SOURCE
    if source not in VALID_CLASSIFICATION_SOURCES:
        source = DEFAULT_CLASSIFICATION_SOURCE

    copies = _int_or_none(raw.get("copies"))
    if copies is None:
        copies = 1
    elif copies < 1 or copies > MAX_COPIES_PER_ROW:
        issues.append(
            f"Nüsha sayısı 1 ile {MAX_COPIES_PER_ROW} arasında olmalıdır; "
            f"“{raw.get('copies')}” alınmadı."
        )
        # 0 sayısı "geçersiz" demektir: `import_service` satırı hatalı sayar ve
        # içe aktarmaz (Excel yolundaki sınır aşımıyla aynı sonuç).
        copies = 0

    return {
        "title": _text(raw.get("title")),
        "authors": _text(raw.get("authors")),
        "translator": _text(raw.get("translator")),
        "publisher": _text(raw.get("publisher")),
        "edition": _text(raw.get("edition")),
        "publish_year": _int_or_none(raw.get("publish_year")),
        "isbn": _text(raw.get("isbn")),
        "subjects": _text(raw.get("subjects")),
        "classification_code": _text(raw.get("classification_code")),
        "classification_source": source,
        "language": _text(raw.get("language")),
        "resource_type": resource_type,
        "copies": copies,
        "shelf_location": _text(raw.get("shelf_location")),
        "corrections": _corrections(raw.get("corrections")),
        "issues": issues,
    }


def validate_payload(payload: Any) -> list[dict[str, Any]]:
    """Yüklenen JSON'u doğrular ve temizlenmiş öğe listesi döndürür.

    Şema uyumsuzluğunda `AiBridgeError`. Satır düzeyi sorunlar (başlık boş,
    tanınmayan kaynak türü, yok sayılan alan) öğenin `issues` listesine yazılır
    ve parti düşmez — sorunlu satır önizlemede satır numarasıyla görünür.
    """
    if not isinstance(payload, dict):
        raise AiBridgeError(["Dosya bir JSON nesnesiyle başlamalıdır ({ … })."])

    errors: list[str] = []
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(
            f"Şema sürümü “{SCHEMA_VERSION}” olmalıdır (gelen: “{_text(version) or '—'}”). "
            "Komut metnini programdan yeniden kopyalayın."
        )
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        errors.append("“items” boş olmayan bir liste olmalıdır.")
    if errors:
        raise AiBridgeError(errors)

    assert isinstance(items, list)  # yukarıda doğrulandı (mypy daraltması)
    temiz: list[dict[str, Any]] = []
    for sira, ham in enumerate(items, start=1):
        if not isinstance(ham, dict):
            errors.append(f"{sira}. öğe bir nesne değil.")
            continue
        temiz.append(_clean_item(ham))
    if errors:
        raise AiBridgeError(errors)
    return temiz
