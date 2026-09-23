"""Kaynak 1 — Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğu (KYGM, SRU).

Ölçüm 23.09.2026 (tasarım §8.5): Türkçe karakterler tam doğru (UTF-8), 5 örnek
ISBN'in 4'ü bulundu, yanıt ~0,3 sn, kimlik ve anahtar gerekmez. **TLS yoktur**
ve uç standart dışı 210 portunda çalışır; ikisi de kabul edilmiş risktir (TB20)
ve özelliğin varsayılan kapalı olmasının gerekçelerindendir.

Konum dili (§3, §8.5-10): bu uç "Bakanlık kataloğu"dur; program "resmî künye"
ya da "Bakanlık sistemi" izlenimi vermez, öneri "doğrulayın" rozetiyle gelir.

**Toplu indirme yapılmaz** (§8.5 lisans notu): tek tek sorgu ile okulun kendi
kataloğunu doldurmak ile kayıtları toplu indirip dağıtmak aynı şey değildir;
ikincisi yapılmaz. `maximumRecords` bu yüzden 5'tir.
"""

from __future__ import annotations

from urllib.parse import urlencode

from apps.kutuphane.kunye import marc
from apps.kutuphane.kunye.istemci import BAKANLIK_HOST, Acici, KunyeAgHatasi, getir
from apps.kutuphane.kunye.oneri import KunyeOnerisi

#: SRU 1.1 ucu (düz HTTP, port 210 — §8.5'te ölçülen adres).
SRU_ADRESI = f"http://{BAKANLIK_HOST}:210/biblios"
#: Mükerrer kayıt kuralı için getirilen aday sayısı (§8.5: en zengin kayıt seçilir).
MAX_KAYIT = 5
KABUL = "application/xml"


def sorgu_adresi(isbn13: str) -> str:
    """Giden adres — dışarı **yalnız normalize ISBN** gider (§8.5-3).

    Sorgu dizesindeki başka her değer sabittir (SRU protokolü). Okul adı,
    demirbaş no, kart no, barkod ve kullanıcı adı burada YOKTUR; koruma testi
    adresin tamamını dolaşır.
    """
    parametreler = urlencode(
        {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": f"bath.isbn={isbn13}",
            "maximumRecords": str(MAX_KAYIT),
            "recordSchema": "marcxml",
        }
    )
    return f"{SRU_ADRESI}?{parametreler}"


def sorgula(isbn13: str, *, acici: Acici | None = None) -> tuple[KunyeOnerisi | None, int]:
    """ISBN'i sorar; (öneri, kaynaktaki kayıt sayısı) döndürür.

    Hata yükseltmez mi? Yükseltir: ağ hatası `KunyeAgHatasi`, bozuk gövde
    `marc.MarcHatasi`. İkisini de servis yakalar ve fail-open davranır (§8.5-9).
    """
    yanit = getir(sorgu_adresi(isbn13), kabul=KABUL, acici=acici)
    if not yanit.govde:
        raise KunyeAgHatasi("Bakanlık kataloğu boş yanıt verdi.")
    return marc.govdeden_oneri(yanit.govde, isbn13=isbn13)
