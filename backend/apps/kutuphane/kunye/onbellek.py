"""Künye önbelleği (§8.5-6): aynı ISBN ikinci kez sorulmaz.

Önbellek satırı kişisel veri taşımaz: kitabın künyesi, kaynağı ve getirilme
tarihidir; kimin sorduğu ve ne aradığı YAZILMAZ.

Tarih `timezone.localdate()` ile alınır (CLAUDE.md §2-9, D6): UTC'den tarih
türetmek 1 Ocak gece yarısı kaynak etiketine bir önceki yılı yazardı.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.kutuphane.kunye.oneri import KunyeOnerisi
from apps.kutuphane.models import MetadataLookupCache


@dataclass(frozen=True, slots=True)
class OnbellekKaydi:
    """Önbellekten okunan künye (model satırının sade karşılığı)."""

    isbn13: str
    kaynak: str
    kayit_sayisi: int
    tarih: date
    oneri: KunyeOnerisi | None


def oku(isbn13: str) -> OnbellekKaydi | None:
    """Önbellekteki kaydı döndürür; yoksa `None`.

    Bulunamamış numara da önbellektedir (`kaynak=""`, `oneri=None`): kaynakta
    olmayan bir ISBN'i her denemede yeniden sormak hız sınırını sessizce
    tüketirdi. Kullanıcı "yeniden getir" derse servis önbelleği atlar.
    """
    satir = MetadataLookupCache.objects.filter(isbn13=isbn13).first()
    if satir is None:
        return None
    oneri = KunyeOnerisi.payloaddan(satir.payload) if satir.payload else None
    return OnbellekKaydi(
        isbn13=satir.isbn13,
        kaynak=satir.source,
        kayit_sayisi=int(satir.record_count),
        tarih=satir.fetched_on,
        oneri=oneri if oneri is not None and not oneri.bos_mu else None,
    )


@transaction.atomic
def yaz(
    isbn13: str,
    *,
    kaynak: str,
    oneri: KunyeOnerisi | None,
    kayit_sayisi: int,
) -> OnbellekKaydi:
    """Künyeyi önbelleğe yazar (aynı ISBN'in eski satırı güncellenir)."""
    bugun = timezone.localdate()
    MetadataLookupCache.objects.update_or_create(
        isbn13=isbn13,
        defaults={
            "source": kaynak,
            "record_count": max(0, int(kayit_sayisi)),
            "fetched_on": bugun,
            "payload": oneri.payload() if oneri is not None else {},
        },
    )
    return OnbellekKaydi(
        isbn13=isbn13,
        kaynak=kaynak,
        kayit_sayisi=max(0, int(kayit_sayisi)),
        tarih=bugun,
        oneri=oneri,
    )


def temizle(isbn13: str = "") -> int:
    """Önbelleği (ya da tek bir ISBN'i) siler; silinen satır sayısını döndürür.

    Gerçek silmedir: önbellek satırı bir kayıt değil, bir sorunun yanıtıdır
    (model `BaseModel` değildir — yumuşak silme teklik kısıtını bozardı).
    """
    sorgu = MetadataLookupCache.objects.all()
    if isbn13:
        sorgu = sorgu.filter(isbn13=isbn13)
    silinen, _ = sorgu.delete()
    return int(silinen)
