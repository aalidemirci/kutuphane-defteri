"""Hız sınırı — `REMOTE_ADDR` başına bellekte token-bucket (tasarım §5.5, TB2).

Ağ Kataloğu okul ağına açıktır; bir tahtanın ya da laboratuvar bilgisayarının
takılı kalmış bir sayfası (ya da kötü niyetli bir betik) saniyede yüzlerce
istekle hem kataloğu hem, aynı süreçte çalıştığı için, yönetim arayüzünü
yavaşlatabilir. Her istemci adresine bir "kova" düşer: kova `kapasite` kadar
jeton alır ve saniyede `dolum_hizi` kadar dolar; her istek bir jeton harcar,
kova boşsa istek 429 alır.

- Adres YALNIZ `REMOTE_ADDR`'dır. `X-Forwarded-For` OKUNMAZ: istemcinin kendi
  yazdığı bir başlık onu başka biri gibi gösterirdi (sunucu da güvenilmeyen
  vekil başlıklarını temizler — `clear_untrusted_proxy_headers`).
- Adresler günlüğe YAZILMAZ ve kalıcı saklanmaz (§5.5 erişim günlüğü yok).
  Bellekteki tablo en çok `en_cok_adres` kova tutar; dolunca en uzun süredir
  görülmeyen kova düşer (LRU). Bir adresin kovası düşerse o adres dolu kovayla
  yeniden başlar — sınır gevşer ama bellek sınırsız büyümez.
- Kabul anındaki IP başına eşzamanlı BAĞLANTI sınırı ayrı bir katmandır
  (masaüstü kolu, dispatcher alt sınıfı); bu modül İSTEK hızını sınırlar.

Varsayılanlar bir öğrencinin gezinmesine hiç dokunmaz (sayfa başına bir ya da
iki istek) ama tek adresten sürekli akışı saniyede birkaç isteğe indirir.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

VARSAYILAN_KAPASITE: Final = 40.0
VARSAYILAN_DOLUM_HIZI: Final = 4.0
VARSAYILAN_EN_COK_ADRES: Final = 4096


@dataclass
class _Kova:
    jeton: float
    son: float


class HizSiniri:
    """Adres başına token-bucket (iş parçacığı güvenli)."""

    def __init__(
        self,
        *,
        kapasite: float = VARSAYILAN_KAPASITE,
        dolum_hizi: float = VARSAYILAN_DOLUM_HIZI,
        en_cok_adres: int = VARSAYILAN_EN_COK_ADRES,
        saat: Callable[[], float] = time.monotonic,
    ) -> None:
        if kapasite < 1 or dolum_hizi <= 0 or en_cok_adres < 1:
            raise ValueError("Hız sınırı değerleri pozitif olmalıdır.")
        self.kapasite = float(kapasite)
        self.dolum_hizi = float(dolum_hizi)
        self._en_cok = en_cok_adres
        self._saat = saat
        self._kovalar: OrderedDict[str, _Kova] = OrderedDict()
        self._kilit = threading.Lock()

    def izin_ver(self, adres: str) -> tuple[bool, int]:
        """İstek geçer mi? `(izin, yeniden_dene_sn)` — izin varken ikinci değer 0'dır."""
        simdi = self._saat()
        with self._kilit:
            kova = self._kovalar.get(adres)
            if kova is None:
                kova = _Kova(jeton=self.kapasite, son=simdi)
                self._kovalar[adres] = kova
                if len(self._kovalar) > self._en_cok:
                    self._kovalar.popitem(last=False)
            else:
                self._kovalar.move_to_end(adres)
                gecen = max(0.0, simdi - kova.son)
                kova.jeton = min(self.kapasite, kova.jeton + gecen * self.dolum_hizi)
                kova.son = simdi
            if kova.jeton >= 1.0:
                kova.jeton -= 1.0
                return True, 0
            eksik = 1.0 - kova.jeton
            return False, max(1, math.ceil(eksik / self.dolum_hizi))

    @property
    def adres_sayisi(self) -> int:
        """Bellekteki kova sayısı (adreslerin kendisi dışarı verilmez)."""
        with self._kilit:
            return len(self._kovalar)
