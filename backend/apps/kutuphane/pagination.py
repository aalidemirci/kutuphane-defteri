"""Katalog listelerinin sayfalaması (D9).

Sayfalama ZORUNLUDUR: bir okulun kataloğu on binlerce satır olabilir ve
sayfalamasız bir liste ucu, masaüstü penceresini tek istekte kilitler. Biçim
projede tektir — DRF `LimitOffsetPagination` (`config/settings.py`
`DEFAULT_PAGINATION_CLASS`), yani yanıt `{count, next, previous, results}` ve
istek `?limit=&offset=` alır; ön yüz `lib/pagination.ts` bu biçimi çözer.

Buradaki iki sınıf yalnız SINIRLARI değiştirir:

* `KatalogSayfalama` — üst sınır (`max_limit`) koyar. DRF'in varsayılanı
  sınırsızdır: `?limit=1000000` bütün kataloğu tek yanıtta serileştirmeye
  kalkardı. Sayfa boyutunu kullanıcı seçer, üst sınırı program koyar.
* `ListeSayfalama` — kontrollü listeler (bölümler) için daha büyük varsayılan.
  Bir seçim kutusunu dolduran istek varsayılan 25'te kesilirse kullanıcı
  listedeki bölümü bulamaz; kesilme sessizdir, bu yüzden varsayılan yükseltilir.
"""

from __future__ import annotations

from rest_framework.pagination import LimitOffsetPagination


class KatalogSayfalama(LimitOffsetPagination):
    """Eser, nüsha, edinim ve karar listeleri: varsayılan 25, en çok 200."""

    default_limit = 25
    max_limit = 200


class ListeSayfalama(KatalogSayfalama):
    """Kontrollü listeler (bölümler): varsayılan 100, en çok 200."""

    default_limit = 100
