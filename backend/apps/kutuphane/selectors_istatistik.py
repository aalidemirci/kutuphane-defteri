"""Kütüphane istatistiği ve Md. 7 bilgi kartı — KİŞİSİZ, k eşikli (F10; tasarım §14.1 F10).

Raporlar ekranının istatistik bölümü şu soruları cevaplar: koleksiyon (eser ve
nüsha; kaynak türüne ve bölüme göre; elde bulunan), edinim (yola göre), dolaşım
(toplam ödünç, iade, gecikme; üye türüne ve sınıf düzeyine göre), teslim,
kayıp/hasar ve ayıklama/devir. Sayılar seçilen DÖNEMİN işlemleridir; koleksiyon
ve "şu an" sayıları rapor anınındır.

**Profil yasağı** (CLAUDE.md §2-5, tasarım §3; F10 kod kapısı —
`tests/test_profil_yasagi.py`):

- Bu modül hiçbir kişinin adını, okul no'sunu, kart no'sunu, üyelik ya da kişi
  kimliğini OKUMAZ ve DÖNDÜRMEZ; farklı üye sayıları veritabanında sayılır.
- **Üye bazında konu ya da sınıf dağılımı yoktur**; dolaşım kırılımları yalnız üye
  türü ve sınıf düzeyidir. **Şube × konu kırılımı yoktur** (konu ekseni dolaşımda
  hiç kullanılmaz).
- Üye türü ve sınıf düzeyi kırılımında grupta k FARKLI üyeden azı varsa sayı
  gösterilmez (k = `LibraryPolicy.popular_min_members`) ve toplamdan geri
  hesaplanamasın diye **tamamlayıcı gizleme** yapılır. Hesap yıl sonu raporunun
  (E9) hesabıdır — TEK KAYNAK: `selectors_yil_raporu._dolasim` ve `_gizlenenler`
  (F8 ekleri 30; türetme testi E9'unkiyle aynı kurguda buradan da koşar).
- **Tamamlayıcı gizleme TEK sorgunun içindedir:** örtüşen iki dönemin farkı gizlenen bir
  hücreyi geri hesaplatabilir; kısa dönemde toplamlar eşiksizdir. Ekran yalnız yönetici
  kipindedir ve çıktısı yoktur (kalan risk TB38 — F10 düzeltme turu; 27.09.2026 kullanıcı
  kararıyla kabul, F10 ekleri K2).
- **Aktif üye sayısı eşiksizdir** (`active_members`, E9'unkiyle aynı): üyelik sayısı ödünç
  verisi değildir, profil yasağının konusu sayılmaz (27.09.2026 kullanıcı kararı, F10 ekleri
  K1). Eşik ve tamamlayıcı gizleme yalnız ödünçten türeyen sayılara uygulanır.
- Adlı sıralama yoktur. Okuma ödülü iç çıktısı (E20) ayrı modüldedir ve bu modül
  onu içe aktarmaz (kaynak taraması ad alanlarını da arar).

**Md. 7/1 bilgi kartı** (`kitap_esigi`): "Kitap sayısı 10.000'i aşan okul
kütüphanelerine bir kütüphaneci atanır." Yönetmelik "kitap"ı tanımlamaz; sayım kuralı
PROGRAMINDIR (mevzuat yorumu diye sunulmaz — F10 düzeltme turu): kaynak türü "Kitap" olan
eserlerin kayıttan düşülmemiş ve devredilmemiş nüshaları sayılır. Danışma kitapları
dahildir; süreli yayın, görsel-işitsel materyal ve dijital kaynak sayılmaz. Kayıp
bildirilmiş ama henüz kayıttan düşülmemiş nüsha kayıtta durduğu için sayılır ve kart
sayısını ayrıca yazar (27.09.2026 kullanıcı kararı, F10 ekleri K3). Kart yalnız BİLGİ verir;
hüküm yorumlamaz (kütüphaneci ataması okulun işi değildir).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone

from apps.kutuphane import selectors_dolasim, selectors_yil_raporu
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    Copy,
    CopyStatus,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    Loan,
    LoanStatus,
    ResourceType,
    Work,
)
from apps.kutuphane.selectors_yil_raporu import _anlar
from apps.okul.models import SchoolYear

#: Çıktı şemasının sürümü (ön yüz tipleri buna göre yazılır).
SCHEMA_VERSION: Final = 1

#: Okul Kütüphaneleri Yönetmeliği Md. 7/1: "Kitap sayısı 10.000'i aşan okul
#: kütüphanelerine bir kütüphaneci atanır." (docs/mevzuat ile BİREBİR — test sınar.)
MD7_ESIGI: Final = 10_000
MD7_1_METNI: Final = "Kitap sayısı 10.000'i aşan okul kütüphanelerine bir kütüphaneci atanır."

TARIH_EKSIK: Final = "Başlangıç ve bitiş tarihini birlikte seçin."
TARIH_SIRASI: Final = "Başlangıç tarihi bitiş tarihinden sonra olamaz."


# ---------------------------------------------------------------------------
# Md. 7/1
# ---------------------------------------------------------------------------
def _elde_kitaplar() -> Any:
    return Copy.objects.exclude(status__in=TERMINAL_COPY_STATUSES).filter(
        work__deleted_at__isnull=True, work__resource_type=ResourceType.BOOK
    )


def elde_kitap_sayisi() -> int:
    """Elde bulunan kitap nüshası: kaynak türü Kitap, terminal olmayan durum, canlı eser."""
    return int(_elde_kitaplar().count())


def kitap_esigi() -> dict[str, Any]:
    """Genel Bakış'ın Md. 7/1 bilgi kartı: sayı, eşik ve eşiğin aşılıp aşılmadığı.

    `lost_books`: sayıya dahil olan, kayıp bildirilmiş ama henüz kayıttan düşülmemiş kitap
    nüshası — kart bunu açıkça yazar (F10 düzeltme turu; sayıda kalması 27.09.2026 kullanıcı
    kararıdır, F10 ekleri K3).
    """
    sayi = elde_kitap_sayisi()
    return {
        "threshold": MD7_ESIGI,
        "in_stock_books": sayi,
        "lost_books": int(_elde_kitaplar().filter(status=CopyStatus.LOST).count()),
        "exceeded": sayi > MD7_ESIGI,
    }


# ---------------------------------------------------------------------------
# Dönem
# ---------------------------------------------------------------------------
def istatistik_donemi(
    *,
    school_year: SchoolYear | None = None,
    bas: date | None = None,
    son: date | None = None,
    bugun: date | None = None,
) -> tuple[date, date]:
    """İstatistiğin dönemi (ikisi de dahil).

    Tarih aralığı verilirse o; ders yılı verilirse yıl sonu raporunun dönemi
    (ders yılı başından sonraki ders yılının başına dek — E9 ile aynı kural);
    hiçbiri verilmezse etkin ders yılının dönemi, etkin yıl yoksa takvim yılının
    başından bugüne.
    """
    gun = bugun or timezone.localdate()
    if bas is not None or son is not None:
        if bas is None or son is None:
            raise ValidationError(TARIH_EKSIK)
        if bas > son:
            raise ValidationError(TARIH_SIRASI)
        return bas, son
    yil = school_year or SchoolYear.objects.filter(is_active=True).first()
    if yil is not None:
        return selectors_yil_raporu.report_period(yil, today=gun)
    return date(gun.year, 1, 1), gun


# ---------------------------------------------------------------------------
# Bölümler
# ---------------------------------------------------------------------------
def _koleksiyon() -> dict[str, Any]:
    """Koleksiyon (rapor anı): E9'un özeti + kaynak türüne göre eser sayısı ve raftaki nüsha."""
    ozet = selectors_yil_raporu._koleksiyon()
    eserler = {
        satir["resource_type"]: satir["adet"]
        for satir in Work.objects.values("resource_type").annotate(adet=Count("pk"))
    }
    ozet["works_by_resource_type"] = {tur: eserler.get(tur, 0) for tur in ResourceType.values}
    ozet["available_count"] = ozet["status_counts"].get(CopyStatus.AVAILABLE, 0)
    return ozet


def _dolasim(bas: date, son: date, k: int, bugun: date) -> dict[str, Any]:
    """Dolaşım: E9'un kişisiz ve eşikli hesabı + gecikme ve "şu an" sayıları."""
    dolasim = selectors_yil_raporu._dolasim(bas, son, k)
    dolasim.pop("deliveries", None)  # teslim kendi bölümündedir
    ilk, sonraki = _anlar(bas, son)
    iadeler = Loan.objects.filter(returned_at__gte=ilk, returned_at__lt=sonraki).values_list(
        "returned_at", "due_date"
    )
    dolasim.update(
        {
            # İade tarihinden SONRA iade edilen (yerel gün): gecikmeyle dönen ödünç.
            "returned_late": sum(
                1 for an, iade_tarihi in iadeler if timezone.localdate(an) > iade_tarihi
            ),
            "lost_converted": Loan.objects.filter(lost_at__gte=ilk, lost_at__lt=sonraki).count(),
            "open_now": Loan.objects.filter(status=LoanStatus.OPEN).count(),
            "overdue_now": selectors_dolasim.overdue_count(on=bugun),
        }
    )
    return dolasim


def _teslimler(bas: date, son: date) -> dict[str, Any]:
    """Sınıf kitaplığına ve öğretmene teslim (U11) — yalnız sayılar."""
    ilk, sonraki = _anlar(bas, son)
    verilen = Delivery.objects.filter(delivered_on__gte=bas, delivered_on__lte=son)
    acik = Delivery.objects.filter(status=DeliveryStatus.OPEN)

    def turlere(qs: Any) -> dict[str, int]:
        return {
            "section": qs.filter(recipient_kind=DeliveryRecipientKind.SECTION).count(),
            "teacher": qs.filter(recipient_kind=DeliveryRecipientKind.TEACHER).count(),
        }

    return {
        "delivered": turlere(verilen),
        "returned": Delivery.objects.filter(returned_at__gte=ilk, returned_at__lt=sonraki).count(),
        "lost": Delivery.objects.filter(lost_at__gte=ilk, lost_at__lt=sonraki).count(),
        "open_now": turlere(acik),
    }


def istatistik(bas: date, son: date, *, bugun: date | None = None) -> dict[str, Any]:
    """İstatistik ekranının bütün sayıları — KİŞİSİZ, JSON'a yazılabilir."""
    gun = bugun or timezone.localdate()
    k = selectors_yil_raporu._esik()
    return {
        "schema": SCHEMA_VERSION,
        "generated_on": gun.isoformat(),
        "period": {"start": bas.isoformat(), "end": son.isoformat()},
        "k_threshold": k,
        "collection": _koleksiyon(),
        "book_threshold": kitap_esigi(),
        "acquisitions": selectors_yil_raporu._kazandirilanlar(bas, son),
        "circulation": _dolasim(bas, son, k, gun),
        "deliveries": _teslimler(bas, son),
        "loss_damage": selectors_yil_raporu._tespitler(bas, son),
        "weeding": selectors_yil_raporu._ayiklanan(bas, son),
    }
