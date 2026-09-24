"""Kişisiz günlük sayaçlar ve Ağ Doktoru'nun son hatası (tasarım §5.5).

Ağ Kataloğunda ERİŞİM GÜNLÜĞÜ YOKTUR: istemci adresi, istenen yol ve arama
terimi hiçbir yere yazılmaz (KVKK; §4 "bulgu değil" tablosu). Ağ Doktoru'nun
"katalog çalışıyor mu, kullanılıyor mu" sorusuna cevap veren tek şey burada
tutulan GÜN BAŞINA SAYILARDIR: kaç sayfa gösterildi, kaç arama yapıldı, kaç
istek sınıra takıldı. Sayılar bellektedir, program kapanınca silinir ve kişiye
bağlanamaz.

Son hata da kişisizdir: yalnız zaman ve sabit bir ileti (ör. "veritabanı
açılamadı") tutulur; hatanın metni, yol ya da sorgu saklanmaz.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

#: Sayılan olaylar (Ağ Doktoru bu adları gösterir; yeni olay buraya eklenir).
OLAYLAR: Final[tuple[str, ...]] = (
    "sayfa",  # 200 dönen HTML sayfası
    "arama",  # /ara isteği (terim SAYILMAZ, yalnız istek)
    "bulunamadi",  # 404
    "reddedildi",  # 400, 405, 413 ve benzeri istek hataları
    "hiz_siniri",  # 429
    "bakim",  # bakım kapısında 503
    "veri_hatasi",  # veritabanına ulaşılamadı ya da sorgu kesildi (503)
    "sunucu_hatasi",  # beklenmeyen hata (500)
)

#: Bellekte tutulan gün sayısı (bugün dahil).
SAKLANAN_GUN: Final = 14


def _yerel_bugun() -> date:
    """Yerel gün (Europe/Istanbul) — UTC'den gün türetilmez (CLAUDE.md §2-9)."""
    from django.utils import timezone

    return timezone.localdate()


@dataclass(frozen=True)
class SonHata:
    """Ağ Doktoru'nun gösterdiği son hata: zaman ve sabit ileti (kişisiz)."""

    zaman: datetime
    ileti: str


class GunlukSayaclar:
    """Gün başına olay sayıları + son hata (iş parçacığı güvenli)."""

    def __init__(
        self,
        *,
        bugun: Callable[[], date] = _yerel_bugun,
        simdi: Callable[[], datetime] | None = None,
    ) -> None:
        self._bugun = bugun
        self._simdi = simdi or (lambda: datetime.now().astimezone())
        self._gunler: dict[date, Counter[str]] = {}
        self._son_hata: SonHata | None = None
        self._kilit = threading.Lock()

    def say(self, olay: str) -> None:
        if olay not in OLAYLAR:
            raise ValueError(f"Bilinmeyen sayaç: {olay}")
        gun = self._bugun()
        with self._kilit:
            self._gunler.setdefault(gun, Counter())[olay] += 1
            if len(self._gunler) > SAKLANAN_GUN:
                for eski in sorted(self._gunler)[: len(self._gunler) - SAKLANAN_GUN]:
                    del self._gunler[eski]

    def hata_kaydet(self, ileti: str) -> None:
        """Son hatayı yazar. `ileti` modülün SABİT metinlerinden biridir, istisna metni değil."""
        with self._kilit:
            self._son_hata = SonHata(zaman=self._simdi(), ileti=ileti)

    def gun(self, gun: date | None = None) -> dict[str, int]:
        """Bir günün sayıları (varsayılan bugün); sayılmamış olay 0 döner."""
        hedef = gun or self._bugun()
        with self._kilit:
            sayim = self._gunler.get(hedef, Counter())
            return {olay: int(sayim[olay]) for olay in OLAYLAR}

    def ozet(self) -> dict[str, dict[str, int]]:
        """Bellekteki bütün günler, ISO tarih anahtarıyla (yeniden eskiye)."""
        with self._kilit:
            return {
                gun.isoformat(): {olay: int(sayim[olay]) for olay in OLAYLAR}
                for gun, sayim in sorted(self._gunler.items(), reverse=True)
            }

    @property
    def son_hata(self) -> SonHata | None:
        with self._kilit:
            return self._son_hata
