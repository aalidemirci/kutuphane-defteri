"""Kaynak 2 — Open Library (yedek; §8.5). HTTPS + JSON, kimlik gerekmez.

**Türkçe verisi kusurludur ve kusurları ÖLÇÜLMÜŞTÜR** (23.09.2026, tasarım
§8.5 ve TB21). Bu modül ölçülen her kusura karşı bir davranış tanımlar:

| Ölçülen kusur | Buradaki karşılığı |
|---|---|
| Harf düşmesi ("Yap Kredi Yaynlar") | Düzeltilemez; öneri "doğrulayın" rozetiyle gelir, kullanıcı görür |
| Ham HTML varlığı (`Do&#x11F;an Kitap`) | `temizlik.metin_temizle` varlıkları çözer |
| Ayrışık (NFD) kod noktaları ("İletişim") | `temizlik` NFC uygular — yoksa katalog araması kendi kitabını bulamaz (§5.10-19d) |
| Çevirmen yazar sayılmış | Çevirmen alanı ASLA doldurulmaz; yazar alanı uyarıyla gelir (§8.5-5) |
| Amazon kaynaklı uydurma tarihler ("13 Nisan") | Yıl yalnız dört haneli değerden okunur; yoksa alan boş kalır |

**Tek istek.** Arama ucu (`search.json`) tek yanıtta eser adı, yazar, yayınevi,
yıl, dil, sayfa ve konuyu verir; `/isbn/<isbn>.json` ucu bunların bir kısmını
verip yazar için ikinci istek gerektirirdi (hız sınırı: tanıtılmamış istemci
1 istek/sn). O ucun 302'si yine de tanımlıdır: yönlendirme kuralı `istemci`de
uygulanır ve testlidir.

**Kayıt baskı birleştirir:** `search.json` bir eserin bütün baskılarını
birleştirir; yayınevi ve yıl sorulan baskıya ait olmayabilir. Öneri bunu uyarı
satırıyla söyler.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from apps.kutuphane.kunye import temizlik
from apps.kutuphane.kunye.istemci import OPENLIBRARY_HOST, Acici, KunyeAgHatasi, getir
from apps.kutuphane.kunye.oneri import (
    ALAN_TAVANLARI,
    UYARI_CEVIRMEN,
    UYARI_YAZAR,
    KunyeOnerisi,
    dil_adi,
    gecerli_yil,
)

ARAMA_ADRESI = f"https://{OPENLIBRARY_HOST}/search.json"
KABUL = "application/json"
#: Yanıtı daraltan alan listesi (sabit; kullanıcı verisi taşımaz).
ALANLAR = (
    "title,author_name,publisher,publish_year,first_publish_year,"
    "number_of_pages_median,language,subject"
)
MAX_KONU = 8
MAX_LISTE = 50

UYARI_BASKI = (
    "Open Library kaydı bir eserin bütün baskılarını birleştirir; yayınevi ve "
    "yıl bu baskıya ait olmayabilir."
)


def sorgu_adresi(isbn13: str) -> str:
    """Giden adres — dışarı **yalnız normalize ISBN** gider (§8.5-3)."""
    parametreler = urlencode({"q": f"isbn:{isbn13}", "fields": ALANLAR, "limit": "1"})
    return f"{ARAMA_ADRESI}?{parametreler}"


def _metin(deger: Any, *, tavan: int) -> str:
    """Listeyse ilk öğe, değilse kendisi — temizlenmiş."""
    if isinstance(deger, list | tuple):
        deger = next((oge for oge in deger[:MAX_LISTE] if str(oge or "").strip()), "")
    return temizlik.metin_temizle(deger, tavan=tavan)


def _liste(deger: Any) -> list[str]:
    if isinstance(deger, list | tuple):
        return [str(oge) for oge in deger[:MAX_LISTE]]
    if deger in (None, ""):
        return []
    return [str(deger)]


def govdeden_oneri(govde: bytes, *, isbn13: str) -> tuple[KunyeOnerisi | None, int]:
    """JSON gövdesinden öneri ve bulunan kayıt sayısı; gövde bozuksa `KunyeAgHatasi`."""
    try:
        veri: Any = json.loads(govde.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise KunyeAgHatasi("Open Library yanıtı okunamadı.") from exc
    if not isinstance(veri, dict):
        raise KunyeAgHatasi("Open Library yanıtı beklenen biçimde değil.")

    sayi = veri.get("numFound")
    kayit_sayisi = int(sayi) if isinstance(sayi, int) and sayi >= 0 else 0
    kayitlar = veri.get("docs")
    if not isinstance(kayitlar, list) or not kayitlar:
        return None, kayit_sayisi
    kayit = kayitlar[0]
    if not isinstance(kayit, dict):
        return None, kayit_sayisi

    tavan = ALAN_TAVANLARI
    yazarlar = [
        ad
        for ham in _liste(kayit.get("author_name"))
        if (ad := temizlik.metin_temizle(ham, tavan=120))
    ]
    konular = [
        konu
        for ham in _liste(kayit.get("subject"))[:MAX_KONU]
        if (konu := temizlik.metin_temizle(ham, tavan=120))
    ]
    yillar = [yil for ham in _liste(kayit.get("publish_year")) if (yil := temizlik.yil_ayikla(ham))]
    if not yillar:
        yillar = [
            yil
            for ham in _liste(kayit.get("first_publish_year"))
            if (yil := temizlik.yil_ayikla(ham))
        ]

    oneri = KunyeOnerisi(
        isbn=isbn13,
        title=_metin(kayit.get("title"), tavan=tavan["title"]),
        authors=", ".join(dict.fromkeys(yazarlar))[: tavan["authors"]].strip(", "),
        publisher=_metin(kayit.get("publisher"), tavan=tavan["publisher"]),
        publish_year=gecerli_yil(min(yillar)) if yillar else None,
        subjects=", ".join(dict.fromkeys(konular))[: tavan["subjects"]].strip(", "),
        language=dil_adi(_metin(kayit.get("language"), tavan=8))[: tavan["language"]],
        pages=temizlik.sayi_ayikla(kayit.get("number_of_pages_median")),
        uyarilar=(UYARI_CEVIRMEN, UYARI_BASKI),
    )
    if oneri.bos_mu:
        return None, kayit_sayisi
    if oneri.authors:
        oneri = oneri.uyarili(UYARI_YAZAR)
    return oneri, kayit_sayisi


def sorgula(isbn13: str, *, acici: Acici | None = None) -> tuple[KunyeOnerisi | None, int]:
    """ISBN'i sorar; (öneri, bulunan kayıt sayısı). Hatayı servis yakalar (fail-open)."""
    yanit = getir(sorgu_adresi(isbn13), kabul=KABUL, acici=acici)
    if not yanit.govde:
        raise KunyeAgHatasi("Open Library boş yanıt verdi.")
    return govdeden_oneri(yanit.govde, isbn13=isbn13)
