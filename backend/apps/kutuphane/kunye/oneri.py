"""Künye önerisinin ortak biçimi — iki kaynak da BUNU üretir (§8.5).

Öneri `Work` satırının yerine geçmez: kullanıcı onaylamadan hiçbir alan
yazılmaz (§8.5-5). Bu modül yalnız "hangi alan, hangi değer, hangi tavan"
sorusunu yanıtlar; yazma kullanıcının kendi `library/works/` isteğiyle olur.

**Çevirmen alanı burada YOKTUR ve olmayacaktır** (§8.5-5): iki kaynak da
çevirmeni yazardan ayırmıyor (Open Library'nin ölçülen kusuru: Orhan Pamuk
kitaplarına Kazak ve İspanyol çevirmenler yazar olarak eklenmiş). Çevirmeni
kullanıcı kendisi yazar; öneri bunu uyarı satırıyla söyler.

**Alan tavanları modelden okunur** (`Work._meta`): öneri kullanıcı onayladığı
anda kaydedilebilmelidir. Tavan koda ikinci kez yazılsaydı model alanı
daraldığında sessizce ayrışırdı.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from apps.kutuphane.models import PUBLISH_YEAR_MAX, PUBLISH_YEAR_MIN, Work

#: Önerinin `Work` alanlarına eşlenen anahtarları (sıra = ekrandaki sıra).
WORK_ALANLARI: tuple[str, ...] = (
    "title",
    "authors",
    "publisher",
    "edition",
    "publish_year",
    "isbn",
    "subjects",
    "classification_code",
    "call_number",
    "language",
)


def _tavan(alan: str) -> int:
    # `getattr` ile okunur: `_meta.get_field` ilişki alanlarını da döndürebildiği
    # için birleşim tipi `max_length` taşımıyor (django-stubs).
    uzunluk = getattr(Work._meta.get_field(alan), "max_length", 0)
    return int(uzunluk) if uzunluk else 1000


def _etiket(alan: str) -> str:
    return str(getattr(Work._meta.get_field(alan), "verbose_name", alan))


#: Metin alanlarının uzunluk tavanı (model `max_length` değerleri).
ALAN_TAVANLARI: dict[str, int] = {
    ad: _tavan(ad) for ad in WORK_ALANLARI if ad not in {"publish_year"}
}

#: Alan etiketleri kullanıcı metnidir ve modelin `verbose_name`'inden gelir
#: (docs/sozluk.md: "kaynak adı", "yer numarası", "bölüm"…).
ALAN_ETIKETLERI: dict[str, str] = {ad: _etiket(ad) for ad in WORK_ALANLARI}

#: ISO 639-2 dil kodu → Türkçe ad. Kaynaklar dili kodla verir (MARC 041,
#: Open Library `language`); katalogda okunur ad durur. Listede olmayan kod
#: OLDUĞU GİBİ geçer: yanlış ad uydurmaktansa kodu göstermek yeğdir.
DIL_ADLARI: dict[str, str] = {
    "tur": "Türkçe",
    "ota": "Osmanlı Türkçesi",
    "eng": "İngilizce",
    "ger": "Almanca",
    "deu": "Almanca",
    "fre": "Fransızca",
    "fra": "Fransızca",
    "ara": "Arapça",
    "per": "Farsça",
    "fas": "Farsça",
    "rus": "Rusça",
    "spa": "İspanyolca",
    "ita": "İtalyanca",
    "grc": "Eski Yunanca",
    "gre": "Yunanca",
    "ell": "Yunanca",
    "lat": "Latince",
    "jpn": "Japonca",
    "chi": "Çince",
    "zho": "Çince",
    "kur": "Kürtçe",
    "aze": "Azerbaycan Türkçesi",
}

#: Yazar alanı doldurulduğunda eklenen uyarı (Open Library ölçümü, TB21).
UYARI_YAZAR = (
    "Yazar listesine çevirmen ya da editör karışmış olabilir; adları kitabın "
    "künye sayfasından doğrulayın."
)
#: Her öneride görünen uyarı: çevirmen dışarıdan doldurulmaz (§8.5-5).
UYARI_CEVIRMEN = "Çevirmen bilgisi dış kaynaktan alınmaz; çeviri eserde elle yazın."


@dataclass(frozen=True, slots=True)
class KunyeOnerisi:
    """Tek bir kitabın dış kaynaktan gelen, TEMİZLENMİŞ künye önerisi."""

    isbn: str = ""
    title: str = ""
    authors: str = ""
    publisher: str = ""
    edition: str = ""
    publish_year: int | None = None
    subjects: str = ""
    classification_code: str = ""
    call_number: str = ""
    language: str = ""
    #: `Work`'te karşılığı olmayan, yalnız ekranda gösterilen bilgiler.
    pages: int | None = None
    place: str = ""
    uyarilar: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bos_mu(self) -> bool:
        """Kayda değer hiçbir alan gelmedi mi? (eser adı yoksa öneri işe yaramaz)"""
        return not self.title.strip()

    def zenginlik(self) -> tuple[int, int, int, int]:
        """Mükerrer kayıt kuralının sıralama anahtarı (§8.5: en zengin kayıt).

        Sıra tasarımdakiyle aynıdır: önce **082 ve 090** (sınıflama kodu ve yer
        numarası) taşıyan kayıt, sonra **300 ve 650** (sayfa ve konu) dolu
        olan, sonra dolu alan sayısı. Eşitlikte kaynağın verdiği sıra korunur
        (çağıran kararlı sıralama kullanır).
        """
        kod = int(bool(self.classification_code)) + int(bool(self.call_number))
        icerik = int(self.pages is not None) + int(bool(self.subjects))
        dolu = sum(1 for deger in self.alan_sozlugu().values() if deger not in ("", None))
        return (kod, icerik, dolu, int(bool(self.publisher)))

    def alan_sozlugu(self) -> dict[str, Any]:
        """`Work` alanı → önerilen değer (boş alanlar da yer alır, sıra sabittir)."""
        ham = asdict(self)
        return {ad: ham[ad] for ad in WORK_ALANLARI}

    def uyarili(self, *uyarilar: str) -> KunyeOnerisi:
        """Uyarı ekleyerek yeni öneri döndürür (tekrarlar elenir, sıra korunur)."""
        birlesik = list(self.uyarilar) + [u for u in uyarilar if u]
        return replace(self, uyarilar=tuple(dict.fromkeys(birlesik)))

    def payload(self) -> dict[str, Any]:
        """Önbelleğe yazılabilir sözlük (JSON alanı)."""
        ham = asdict(self)
        ham["uyarilar"] = list(self.uyarilar)
        return ham

    @classmethod
    def payloaddan(cls, veri: Any) -> KunyeOnerisi:
        """Önbellekteki sözlükten öneri kurar; tanınmayan anahtarları yok sayar.

        Önbellek satırı ESKİ bir sürümde yazılmış olabilir: alan eklenip
        çıkarıldığında `KunyeOnerisi(**satir)` `TypeError` verirdi ve önbellek
        okuması programı düşürürdü.
        """
        if not isinstance(veri, dict):
            return cls()
        bilinen = {alan.name for alan in cls.__dataclass_fields__.values()}
        temiz = {ad: deger for ad, deger in veri.items() if ad in bilinen}
        uyarilar = temiz.pop("uyarilar", ())
        if not isinstance(uyarilar, list | tuple):
            uyarilar = ()
        yil = temiz.get("publish_year")
        temiz["publish_year"] = yil if isinstance(yil, int) else None
        sayfa = temiz.get("pages")
        temiz["pages"] = sayfa if isinstance(sayfa, int) else None
        metinler = {
            ad: str(deger or "")
            for ad, deger in temiz.items()
            if ad not in {"publish_year", "pages"}
        }
        return cls(
            **metinler,
            publish_year=temiz["publish_year"],
            pages=temiz["pages"],
            uyarilar=tuple(str(u) for u in uyarilar),
        )


def dil_adi(kod: object) -> str:
    """ISO dil kodunu Türkçe ada çevirir; tanınmayan kod olduğu gibi döner."""
    ham = str(kod or "").strip().lower()
    if not ham:
        return ""
    return DIL_ADLARI.get(ham, ham)


def gecerli_yil(deger: object) -> int | None:
    """Makul aralıktaki (model validator'ıyla aynı) yılı döndürür, değilse `None`."""
    if not isinstance(deger, int):
        return None
    return deger if PUBLISH_YEAR_MIN <= deger <= PUBLISH_YEAR_MAX else None
