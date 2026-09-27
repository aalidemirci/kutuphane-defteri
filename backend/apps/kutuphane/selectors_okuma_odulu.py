"""Okuma ödülü iç çıktısının adayları (E20) — ADLI, YALNIZ YÖNETİCİ KİPİ (F10).

Uygulama Kılavuzu 7 bir ÖNERİ yapar: "En çok kitap okuyan öğrenciler
ödüllendirilerek teşvik sistemi kurulabilir." Bağlayıcı değildir; program
yalnız okulun bu öneriyi uygulamak isterse karar verebilmesi için bir İÇ ÇIKTI
hazırlar. Programda adlı sıralamanın geçtiği TEK yer burasıdır; profil yasağı
(CLAUDE.md §2-5, tasarım §3) onu şu sınırlara bağlar:

- **Yalnız yönetici kipinde** (`require_admin_mode` — ara katmana ek savunma).
- Çıktı **"İç kullanım"** ibarelidir; ağa (Ağ Kataloğu), panoya (Genel Bakış ve
  "Ayın Kitapları" afişi), yıl sonu raporuna (E9) ve velilerle paylaşılabilecek
  çıktılara GİRMEZ. Bu modülü içe aktaran tek yer E20 belgesidir
  (`okuma_odulu_belgesi`); kaynak taraması `tests/test_profil_yasagi.py`'dedir.
- **Sayı basılmaz**: adayın kaç ödünç aldığı ya da kaç farklı eser aldığı çıktıda
  YOKTUR, yalnız sıra (eşitler aynı sırada). Öğrenci bazlı ödünç sayısı öğretmene
  ya da e-Okul'a aktarılmaz (tasarım §3 "Ödünç ≠ okuduğu kitap"); iç çıktı ödül
  kurulunda öğretmenlerin önüne gelebilir.
- **Konu, sınıflama ve bölüm hiç okunmaz** (üye bazında konu dağılımı yok); not
  ya da başarı verisi programda yoktur.
- Ölçüt: dönem içinde ödünç alınıp **iade edilmiş** FARKLI eser sayısı. Aynı eserin
  yeniden alınması bir kez sayılır (sıra ödünç sayısıyla şişirilemez); iade
  edilmemiş ya da kayba dönüşmüş ödünç sayılmaz. Ödünç kaydı okunan kitabı
  göstermez: çıktı bunu söyler.
- Yalnız ÖĞRENCİLER (Kılavuz 7 "öğrenciler" der); kaydı canlı ve okulda olanlar
  (ayrılmış ya da silinmiş öğrencinin adı basılmaz). Okul no basılmaz (ad ve sınıf
  yeter — veri en aza indirme).

Ad ve sınıf şifreli/kişi alanlarındadır: sıralama veritabanında (öğrenci kimliği
ve ölçüt), ad çözümü ve eşitlerin ad sırası Python'dadır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from django.core.exceptions import ValidationError
from django.db.models import Count

from apps.kutuphane.models import Loan, LoanStatus
from apps.kutuphane.selectors_yil_raporu import _anlar
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import normalize
from apps.okul.models import Student, StudentStatus

#: Varsayılan ve en çok sıra sayısı (eşitler sıranın içindeyse hepsi girer).
VARSAYILAN_SIRA: Final = 10
EN_COK_SIRA: Final = 50
SIRA_SINIRI_ILETISI: Final = f"Sıra sayısı 1 ile {EN_COK_SIRA} arasında olmalıdır."


@dataclass(frozen=True)
class OdulAdayi:
    """İç çıktının bir satırı: sıra (eşitler aynı sırada), ad ve sınıf/şube."""

    sira: int
    ad: str
    sinif: str


def adaylar(
    bas: date,
    son: date,
    *,
    class_level: int | None = None,
    sira_sayisi: int = VARSAYILAN_SIRA,
) -> list[OdulAdayi]:
    """Dönemin adayları: sırası `sira_sayisi`'ni aşmayan bütün öğrenciler (eşitler dahil).

    Sıra yarışma sıralamasıdır (1, 2, 2, 4): sınırdaki eşitlerden biri keyfî olarak
    dışarıda kalmaz. Yalnız yönetici kipinde çağrılabilir.
    """
    require_admin_mode()
    if not 1 <= sira_sayisi <= EN_COK_SIRA:
        raise ValidationError(SIRA_SINIRI_ILETISI)
    ilk, sonraki = _anlar(bas, son)
    oduncler = Loan.objects.filter(
        loaned_at__gte=ilk,
        loaned_at__lt=sonraki,
        status=LoanStatus.RETURNED,
        membership__student__isnull=False,
        membership__student__deleted_at__isnull=True,
        membership__student__status=StudentStatus.ACTIVE,
    )
    if class_level is not None:
        oduncler = oduncler.filter(membership__student__class_level=class_level)
    olcutler = [
        (int(satir["membership__student_id"]), int(satir["eser"]))
        for satir in oduncler.values("membership__student_id")
        .annotate(eser=Count("copy__work_id", distinct=True))
        .order_by("-eser", "membership__student_id")
    ]
    secilen: list[tuple[int, int]] = []  # (sıra, öğrenci kimliği)
    onceki: int | None = None
    sira = 0
    for konum, (ogrenci_id, deger) in enumerate(olcutler, start=1):
        if deger != onceki:
            sira, onceki = konum, deger
        if sira > sira_sayisi:
            break
        secilen.append((sira, ogrenci_id))
    ogrenciler = Student.objects.in_bulk([ogrenci_id for _, ogrenci_id in secilen])
    satirlar = [
        OdulAdayi(sira=s, ad=ogrenciler[o].full_name, sinif=ogrenciler[o].class_label)
        for s, o in secilen
        if o in ogrenciler
    ]
    return sorted(satirlar, key=lambda a: (a.sira, normalize.tr_sort_key(a.ad)))
