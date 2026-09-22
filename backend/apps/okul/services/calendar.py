"""Kapalı günler — tohumlama, elle ekleme/silme ve kapalı dönem kaynağı (tasarım §6.1, §9-5).

DD'nin `services/calendar.py`'sinden UYARLANDI (tasarım §12):

- Tohumlama DD'de DERS YILINA göreydi ve ders yılı dışındaki tatiller (15 Temmuz,
  30 Ağustos) yazılmıyordu. Burada TAKVİM YILINA göredir ve yılın bütün sabit
  resmî tatilleri yazılır: iade tarihi yaz başında da hesaplanabilir, kapalı gün
  kaynağının boşluğu sessiz yanlış tarih üretir.
- DD'nin `is_working_day`'i (iş günü sayımı, disiplin süreleri) ALINMADI; yerini
  `shared.working_days.next_open_day` aldı. Bu modül ona kapalı dönemleri verir
  (`closed_periods_from`).
- Fikirdeşlik: DD yalnız (ad, başlangıç) eşleşmesine bakıyordu. Tahmini bir bayramı
  silip doğru tarihle elle giren kullanıcı ikinci tohumlamada aynı bayramı iki kez
  görürdü; burada aynı türden kayıt o tarihi (dini bayramda ±15 günlük pencereyi)
  zaten kapsıyorsa satır ATLANIR.

Dini bayram verisi (DD tasarım §7 kararı AYNEN): `holidays` pip paketi yok — hicri
hesap Diyanet takviminden ±1 gün sapabilir. Gömülü tablo: Diyanet takviminde
kesinleşmiş yıllar kesin (`is_estimated=False`), 2027 ve sonrası TAHMİNİ bayraklıdır;
arayüz "tahmini" rozetini ve "Diyanet takvimi kesinleşince kontrol edin" notunu
gösterir. Tablonun kapsamadığı yılda dini bayram eklenmez ve yanıt bunu söyler
(`religious_available=False`); kullanıcı elle girer.

ARİFE KARARI: arife günleri (28 Ekim ile Ramazan ve Kurban Bayramı arifeleri)
öğleden sonra yarım gün tatildir (2429 sayılı Kanun; metni `docs/mevzuat/`'ta
yoktur, bu not atıf değil bağlamdır — kullanıcı metnine girmez). DD arifeyi iş günü
sayıyordu; kütüphane için de arife AÇIK GÜNDÜR ve tohumlanmaz:
  1. Günün ilk yarısı mesai ve ders sürer; öğrenci okuldadır, iade fiilen alınabilir.
  2. Kaydırmanın kıyas dayanağı TBK md. 93 "tatil olarak kabul edilen bir gün"den
     söz eder; yarım günlük tatil bütün günü tatil yapmaz.
  3. Kapalı gün kaydı gün birimlidir (yarım gün tutulamaz); arifeyi kapalı saymak
     bayramdan önceki günü de kaydırıp iade tarihini gereksiz uzatırdı.
  Okul arife günü kütüphaneyi kapatıyorsa o günü elle "İdari izin / diğer" ya da
  "öğrenciye kapalı gün" olarak ekler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.okul.models import Holiday, HolidayKind
from shared.working_days import ClosedPeriod

# Tohumlanabilen takvim yılı aralığı (uç ve servis aynı sınırı kullanır).
MIN_YEAR: Final = 2000
MAX_YEAR: Final = 2100

# Bir kaydın kapsayabileceği en uzun süre. Yaz tatili (≈ 80 gün) sığar; yıl hanesi
# yanlış yazılmış bitiş tarihi (2027 yerine 2072) bütün iade tarihlerini on yıllarca
# kaydırmasın diye üst sınır vardır.
MAX_SPAN_DAYS: Final = 120

# Ulusal bayram ve genel tatillerin SABİT tarihli olanları (DD/OYS
# `FIXED_OFFICIAL_HOLIDAYS` AYNEN). Dini bayramlar hicri takvime göre kaydığından
# aşağıdaki ayrı tablodadır.
FIXED_OFFICIAL_HOLIDAYS: Final[tuple[tuple[int, int, str], ...]] = (
    (1, 1, "Yılbaşı"),
    (4, 23, "Ulusal Egemenlik ve Çocuk Bayramı"),
    (5, 1, "Emek ve Dayanışma Günü"),
    (5, 19, "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    (7, 15, "Demokrasi ve Millî Birlik Günü"),
    (8, 30, "Zafer Bayramı"),
    (10, 29, "Cumhuriyet Bayramı"),
)

# Dini bayramlar: (ad, başlangıç, bitiş, tahmini_mi) — DD tablosu AYNEN.
# 2026 Diyanet takviminde yayımlı → kesin. 2027 ve sonrası astronomik hesapla
# TAHMİNİ; Diyanet takvimi kesinleşince kullanıcı kontrol eder ve gerekirse
# kaydı silip doğru tarihle yeniden girer.
RELIGIOUS_HOLIDAYS: Final[tuple[tuple[str, date, date, bool], ...]] = (
    ("Ramazan Bayramı", date(2026, 3, 20), date(2026, 3, 22), False),
    ("Kurban Bayramı", date(2026, 5, 27), date(2026, 5, 30), False),
    ("Ramazan Bayramı", date(2027, 3, 9), date(2027, 3, 11), True),
    ("Kurban Bayramı", date(2027, 5, 16), date(2027, 5, 19), True),
    ("Ramazan Bayramı", date(2028, 2, 26), date(2028, 2, 28), True),
    ("Kurban Bayramı", date(2028, 5, 5), date(2028, 5, 8), True),
    ("Ramazan Bayramı", date(2029, 2, 14), date(2029, 2, 16), True),
    ("Kurban Bayramı", date(2029, 4, 24), date(2029, 4, 27), True),
)

# Tahmini bayram ile elle düzeltilmiş kaydı "aynı bayram" saymak için pencere.
# Hicri sapma ±1-2 gündür; Ramazan ile Kurban arası ≈ 70 gün, aynı bayramın iki
# yılı arası ≈ 354 gün — pencere hiçbirini karıştırmaz.
_RELIGIOUS_MATCH_WINDOW: Final = timedelta(days=15)

DUPLICATE_MESSAGE: Final = "Bu adla aynı günde başlayan bir kayıt zaten var."


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Tohumlama sonucu — `created` yeni, `skipped` zaten var olan kayıt sayısı."""

    year: int
    created: int
    skipped: int
    # Gömülü tabloda bu yılın dini bayramları var mı? Yoksa arayüz elle girişi ister.
    religious_available: bool


def closed_periods_from(day: date) -> list[ClosedPeriod]:
    """`day` ve sonrasını etkileyen canlı kapalı gün kayıtları (`shared.working_days` kaynağı)."""
    rows = Holiday.objects.filter(end_date__gte=day).values_list("start_date", "end_date", "kind")
    return [
        ClosedPeriod(start=start, end=end, school_break=kind == HolidayKind.SCHOOL_BREAK)
        for start, end, kind in rows
    ]


def _check_year(year: int) -> None:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Yıl {MIN_YEAR} ile {MAX_YEAR} arasında olmalıdır.")


def _official_exists(name: str, day: date) -> bool:
    return Holiday.objects.filter(
        Q(name=name, start_date=day)
        | Q(kind=HolidayKind.OFFICIAL, start_date__lte=day, end_date__gte=day)
    ).exists()


def _religious_exists(name: str, start: date, end: date) -> bool:
    return Holiday.objects.filter(
        Q(name=name, start_date=start)
        | Q(
            kind=HolidayKind.RELIGIOUS,
            start_date__lte=end + _RELIGIOUS_MATCH_WINDOW,
            end_date__gte=start - _RELIGIOUS_MATCH_WINDOW,
        )
    ).exists()


def religious_rows_for(year: int) -> list[tuple[str, date, date, bool]]:
    """Gömülü tablonun `year` takvim yılıyla kesişen dini bayram satırları."""
    return [row for row in RELIGIOUS_HOLIDAYS if row[1].year <= year <= row[2].year]


@transaction.atomic
def seed_holidays(year: int) -> SeedResult:
    """`year` takvim yılının sabit resmî tatillerini ve dini bayramlarını ekler.

    Fikirdeştir: ikinci çağrı kopya üretmez (atlananlar `skipped`'e sayılır).
    Arife günleri eklenmez (modül yorumu, "ARİFE KARARI").
    """
    _check_year(year)
    created = 0
    skipped = 0
    for month, day_of_month, name in FIXED_OFFICIAL_HOLIDAYS:
        day = date(year, month, day_of_month)
        if _official_exists(name, day):
            skipped += 1
            continue
        Holiday.objects.create(name=name, start_date=day, end_date=day, kind=HolidayKind.OFFICIAL)
        created += 1

    religious = religious_rows_for(year)
    for name, start, end, is_estimated in religious:
        if _religious_exists(name, start, end):
            skipped += 1
            continue
        Holiday.objects.create(
            name=name,
            start_date=start,
            end_date=end,
            kind=HolidayKind.RELIGIOUS,
            is_estimated=is_estimated,
        )
        created += 1
    return SeedResult(
        year=year, created=created, skipped=skipped, religious_available=bool(religious)
    )


def span_message() -> str:
    """Süre sınırı reddinin metni (serializer ve servis aynı cümleyi kullanır)."""
    return f"Bir kayıt en çok {MAX_SPAN_DAYS} günü kapsayabilir; tarihleri kontrol edin."


def create_holiday(*, name: str, start_date: date, end_date: date, kind: str) -> Holiday:
    """Elle kapalı gün ekler (öğrenciye kapalı gün, idari izin, düzeltilmiş bayram).

    Elle girilen kayıt kesin tarih sayılır (`is_estimated=False`). Tarih sırası ve
    süre sınırı serializer'da da denetlenir; burada servis sözleşmesi olarak
    yinelenir (başka çağıran — ör. sihirbaz servisi — serializer'dan geçmeyebilir).
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError({"name": ["Ad yazılmalıdır."]})
    if kind not in HolidayKind.values:
        raise ValidationError({"kind": ["Geçerli bir tür seçin."]})
    if end_date < start_date:
        raise ValidationError({"end_date": ["Bitiş tarihi başlangıçtan önce olamaz."]})
    if (end_date - start_date).days + 1 > MAX_SPAN_DAYS:
        raise ValidationError({"end_date": [span_message()]})
    if Holiday.objects.filter(name=clean_name, start_date=start_date).exists():
        raise ValidationError({"name": [DUPLICATE_MESSAGE]})
    try:
        with transaction.atomic():
            holiday: Holiday = Holiday.objects.create(
                name=clean_name,
                start_date=start_date,
                end_date=end_date,
                kind=kind,
                is_estimated=False,
            )
    except IntegrityError as exc:  # yarışta teklik kısıtı — aynı Türkçe ret
        raise ValidationError({"name": [DUPLICATE_MESSAGE]}) from exc
    return holiday


def delete_holiday(holiday: Holiday) -> None:
    """Kaydı kaldırır (yumuşak silme — BaseModel); kapalı gün kaynağından düşer."""
    holiday.delete()
