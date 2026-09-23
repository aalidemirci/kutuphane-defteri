"""Dışarıdan gelen metnin temizliği — güvenilmeyen girdi kapısı (§8.5-4, §5.10-19d).

Saf fonksiyonlardır (Django'suz, DB'siz): hem ağdan gelen yanıtlar hem de
çevrimdışı yoldan gelen dosya bu kapıdan geçer.

**NFC neden ZORUNLU** (§5.10-19d, tasarım §8.5). Open Library'nin Türkçe
kayıtlarında ayrışık (NFD) kod noktaları ölçüldü: "İletişim" orada "I" +
U+0307 (birleşen nokta) olarak gelir. Katalog araması `keys.fold_search`'ten
geçer; o da `tr_upper` + `fold_diacritics` uygular ve birleşen noktayı harf
saymaz, boşluğa çevirir. Yani NFC'ye çevrilmemiş bir künye kataloğa girdiğinde
kullanıcı **kendi kitabını aramada bulamaz** — üstelik bu **sessizce** olur.
Koruma testi hem dönüşümü hem de katlamanın eşleştiğini kanıtlar.

**Denetim karakteri.** Yanıt metni evraka (WeasyPrint), etikete ve arama
anahtarına basılır. Görünmez yön değiştirme işaretleri (U+202E) ve sıfır
genişlikli karakterler ekranda bir şey, kayıtta başka bir şey gösterir; satır
sonları da tek satırlık künye alanlarını bozar. Hepsi elenir, boşluğa dönüşür.

**HTML varlıkları.** Ölçülen kusur: Open Library "Doğan Kitap" yerine
`Do&#x11F;an Kitap` döndürüyor. Varlıklar **bir kez** çözülür; ikinci geçiş
`&amp;lt;` gibi değerleri sessizce etikete çevirirdi.

**Uzunluk tavanı** çağıranın işidir (`oneri.ALAN_TAVANLARI` model alanlarının
`max_length` değerlerinden okur): öneri kullanıcı onayladığında doğrudan
kaydedilebilmelidir, tavanı aşan bir değer kaydetme anında patlardı.
"""

from __future__ import annotations

import html
import re
import unicodedata

#: Bir alanın hiçbir koşulda aşamayacağı mutlak tavan (model alanları daha
#: dardır; bu, tavanı verilmeyen çağrılar için son emniyettir).
MUTLAK_TAVAN = 1000

#: MARC alt alanlarının sonundaki ISBD noktalaması ("Madonna /", "İletişim,").
_ISBD_SON = " /:;,=."

#: Boşluk sayılan ama `str.split()`in görmediği karakterler (NBSP, ince boşluk…).
_BOSLUK_KARAKTERLERI = "               　"

_BOSLUK_DESENI = re.compile(r"\s+")
#: Dört haneli yıl (1000-2999 aralığı `oneri` tarafında denetlenir).
_YIL_DESENI = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_SAYI_DESENI = re.compile(r"(?<!\d)(\d{1,6})(?!\d)")


def _denetim_karakterlerini_ele(metin: str) -> str:
    """Yazdırılamayan karakterleri boşluğa çevirir (satır sonu dahil).

    Kategori denetimi kod noktası listesinden güvenlidir: yeni Unicode
    sürümlerinde eklenen biçim karakterleri de (Cf) elenir. Vekil ve
    atanmamış kod noktaları (Cs, Cn) da buraya düşer.
    """
    return "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Cs", "Co", "Cn"} else ch for ch in metin
    )


def metin_temizle(ham: object, *, tavan: int = MUTLAK_TAVAN) -> str:
    """Dış metni güvenli, NFC ve tek satır hâline getirir; tavana kısaltır.

    Sıra bilinçlidir: önce varlıklar çözülür (çözülen metin denetim karakteri
    taşıyabilir: `&#x202E;`), sonra denetim karakterleri elenir, sonra NFC
    uygulanır (birleşen işaretler harflerine oturur), en sonunda boşluk
    sadeleşir ve tavan uygulanır.
    """
    if ham is None:
        return ""
    metin = str(ham)
    if not metin:
        return ""
    metin = html.unescape(metin)  # BİR kez: ikinci geçiş `&amp;lt;`i etikete çevirirdi
    metin = _denetim_karakterlerini_ele(metin)
    metin = unicodedata.normalize("NFC", metin)
    for bosluk in _BOSLUK_KARAKTERLERI:
        metin = metin.replace(bosluk, " ")
    metin = _BOSLUK_DESENI.sub(" ", metin).strip()
    if len(metin) > max(0, tavan):
        metin = metin[: max(0, tavan)].strip()
    return metin


def marc_temizle(ham: object, *, tavan: int = MUTLAK_TAVAN) -> str:
    """`metin_temizle` + MARC alt alanının sonundaki ISBD noktalamasının kırpılması.

    MARC kayıtlarında 245$a "Kürk mantolu Madonna /", 260$b "İletişim," diye
    biter; bu işaretler bir sonraki alt alana geçişi gösterir, künyenin parçası
    değildir. Baştaki köşeli ayraç da ("[2015]") kırpılır.
    """
    metin = metin_temizle(ham, tavan=tavan)
    return metin.strip("[]").strip(_ISBD_SON).strip()


def yil_ayikla(ham: object) -> int | None:
    """Metindeki ilk dört haneli yılı döndürür; yoksa `None`.

    Kaynaklar yılı "2015.", "c2015", "[2015]", "13 Nisan 2015" gibi yazar.
    Open Library'nin Amazon kaynaklı **uydurma tarihleri** ("13 Nisan") yıl
    taşımaz; o durumda alan boş kalır — yanlış yıl yazmaktansa boş bırakmak
    kullanıcıyı daha az yanıltır (TB21).
    """
    eslesme = _YIL_DESENI.search(metin_temizle(ham))
    return int(eslesme.group(1)) if eslesme else None


def sayi_ayikla(ham: object) -> int | None:
    """Metindeki ilk sayıyı döndürür ("328 s." → 328); yoksa `None`."""
    eslesme = _SAYI_DESENI.search(metin_temizle(ham))
    return int(eslesme.group(1)) if eslesme else None
