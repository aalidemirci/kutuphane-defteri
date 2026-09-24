"""Nüsha numarası üretimi — barkod ve kayıt no TEK sayaçtan (tasarım §7.1, D6).

Numara asla yeniden kullanılmaz: sayaç yalnız ileri gider, nüsha silinse
(yumuşak ya da katı) bile geri alınmaz. `Copy.barcode` ve `Copy.accession_no`
DÜZ `unique`'tir (kısmi değil), yani veritabanı da aynı şeyi söyler.

**Boş barkod aralığı da AYNI sayaçtan beslenir** (F4, yöntem B — §8.1):
`reserve_identities` ardışık numaraları tek işlemde ayırır ve sayacı onların
ötesine geçirir. Ayrılmış bir numara bu yüzden hiçbir yoldan başka bir nüshaya
verilemez; kullanılmayan numara iptal edilir, sayaca GERİ DÖNMEZ. İkinci bir
sayaç (ör. "etiket sayacı") açılmadı: iki sayaç aynı barkod uzayını paylaşsaydı
çakışmayı yalnız teklik kısıtı yakalardı, o da kullanıcıya bir sunucu hatası
olarak yansırdı.

**Yıl `timezone.localdate()` ile alınır** (D6). OYS `timezone.now().year`
kullanıyordu: `USE_TZ=True` ile `now()` UTC'dir, 1 Ocak gece yarısı ile 03:00
arasında Türkiye'de açılan bir nüsha bir önceki yılın numarasını alırdı. Ayrılmış
aralık tek işlemde ve tek `localdate()` okumasıyla ayrıldığı için yıl dönümünü
BÖLMEZ: aralığın bütün numaraları aynı yıla aittir.

**Yarış.** `select_for_update()` SQLite'ta etkisizdir (CLAUDE.md §4 "bulgu
değil" tablosu); yine de niyeti belgelediği ve ileride başka bir motora
taşınırsa çalıştığı için bırakıldı. Gerçek güvence üç katmanlıdır: program tek
yazarlıdır (tek masaüstü süreci), `transaction_mode=IMMEDIATE` yazma işlemini
en baştan yazma kilidiyle açar (sayacı okuyan iki işlem aynı anda var olamaz)
ve `barcode` teklik kısıtları (`Copy`, `ReservedBarcode`) son savunmadır.
Koruma testi: `tests/test_bos_barkod_sayac.py`.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import CopyCounter


def _take(count: int) -> list[tuple[int, str]]:
    """Sayaçtan ardışık `count` numara alır (çağıranın işleminin İÇİNDE).

    Taşma önce denetlenir: son numara şemaya sığmıyorsa `BarcodeRangeError`
    yükselir ve sayaç İLERLEMEZ (satır hiç yazılmaz). Kısmi ayırma yoktur —
    "istediğim 300 numaranın 120'si verildi" gibi bir sonuç kullanıcıya
    anlatılamazdı.
    """
    if count < 1:
        raise ValueError("Ayrılacak numara sayısı en az 1 olmalıdır.")
    year = timezone.localdate().year
    counter, _created = CopyCounter.objects.select_for_update().get_or_create(
        year=year, defaults={"last_no": 0}
    )
    first = counter.last_no + 1
    last = counter.last_no + count
    # Son numara şemaya sığıyorsa aradakiler de sığar; tek denetim yeter.
    barcode_module.build_barcode(year, last)
    barcodes = [barcode_module.build_barcode(year, sequence) for sequence in range(first, last + 1)]
    counter.last_no = last
    counter.save(update_fields=["last_no"])
    return [(barcode_module.accession_no_of(kod), kod) for kod in barcodes]


@transaction.atomic
def next_copy_identity() -> tuple[int, str]:
    """Sıradaki (kayıt no, barkod) ikilisini üretir ve sayacı ilerletir.

    Sayaç yıl bazlıdır: her yıl 1'den başlar, barkodun ilk dört hanesi yıldır.
    Sıra 999999'u aşarsa `BarcodeRangeError` yükselir ve işlem geri alınır —
    sayaç da ilerlemez (aynı işlem içindedir).
    """
    return _take(1)[0]


@transaction.atomic
def reserve_identities(count: int) -> list[tuple[int, str]]:
    """Boş barkod aralığı için ardışık `count` (kayıt no, barkod) ikilisi ayırır.

    Numaralar AYNI sayaçtan gelir ve sayaç onların ötesine geçer: ayrılan hiçbir
    numara `next_copy_identity` ile bir daha üretilmez. Sayaç dolacaksa hiçbir
    numara ayrılmaz (`BarcodeRangeError`, sayaç yerinde kalır).
    """
    return _take(count)


def peek_next_sequence(year: int | None = None) -> int:
    """Sayacın bir sonraki sıra numarası (yalnız gösterim; sayacı İLERLETMEZ)."""
    target = year if year is not None else timezone.localdate().year
    counter = CopyCounter.objects.filter(year=target).first()
    return (counter.last_no if counter is not None else 0) + 1
