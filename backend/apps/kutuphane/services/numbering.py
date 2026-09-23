"""Nüsha numarası üretimi — barkod ve kayıt no TEK sayaçtan (tasarım §7.1, D6).

Numara asla yeniden kullanılmaz: sayaç yalnız ileri gider, nüsha silinse
(yumuşak ya da katı) bile geri alınmaz. `Copy.barcode` ve `Copy.accession_no`
DÜZ `unique`'tir (kısmi değil), yani veritabanı da aynı şeyi söyler.

**Yıl `timezone.localdate()` ile alınır** (D6). OYS `timezone.now().year`
kullanıyordu: `USE_TZ=True` ile `now()` UTC'dir, 1 Ocak gece yarısı ile 03:00
arasında Türkiye'de açılan bir nüsha bir önceki yılın numarasını alırdı.

**Yarış.** `select_for_update()` SQLite'ta etkisizdir (CLAUDE.md §4 "bulgu
değil" tablosu); yine de niyeti belgelediği ve ileride başka bir motora
taşınırsa çalıştığı için bırakıldı. Gerçek güvence üç katmanlıdır: program tek
yazarlıdır (tek masaüstü süreci), `transaction_mode=IMMEDIATE` yazma işlemini
en baştan yazma kilidiyle açar ve `barcode` teklik kısıtı son savunmadır.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import CopyCounter


@transaction.atomic
def next_copy_identity() -> tuple[int, str]:
    """Sıradaki (kayıt no, barkod) ikilisini üretir ve sayacı ilerletir.

    Sayaç yıl bazlıdır: her yıl 1'den başlar, barkodun ilk dört hanesi yıldır.
    Sıra 999999'u aşarsa `BarcodeRangeError` yükselir ve işlem geri alınır —
    sayaç da ilerlemez (aynı işlem içindedir).
    """
    year = timezone.localdate().year
    counter, _created = CopyCounter.objects.select_for_update().get_or_create(
        year=year, defaults={"last_no": 0}
    )
    counter.last_no += 1
    barcode = barcode_module.build_barcode(year, counter.last_no)
    counter.save(update_fields=["last_no"])
    return barcode_module.accession_no_of(barcode), barcode


def peek_next_sequence(year: int | None = None) -> int:
    """Sayacın bir sonraki sıra numarası (yalnız gösterim; sayacı İLERLETMEZ)."""
    target = year if year is not None else timezone.localdate().year
    counter = CopyCounter.objects.filter(year=target).first()
    return (counter.last_no if counter is not None else 0) + 1
