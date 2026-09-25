"""Yıl sonu ve yıl başı akışlarının durum özetleri (F7 — tasarım §8.3; SU-8, EK-22).

İki akış da ADIM ADIM bir ekrandır (Genel Bakış'tan açılır; tarih penceresinde
kart çıkar). Bu modül ekranların her adımı için durum ve SAYI üretir; kayıt
YAZMAZ. Adımların işleri mevcut uçlardadır (Kütüphane Politikası, e-Okul
aktarımı, Ayrılış Havuzu, Kapalı Günler, ilişik ve pusula uçları).

**Yıl sonu** (Mayıs-Haziran — mezunlar Haziran'da ayrılır, Eylül'de kitap
toplamak fiilen imkânsızdır):

1. Son ödünç tarihleri (`LibraryPolicy.last_loan_date`, son sınıflar için
   `last_loan_date_graduating` — ikisi de F6'dan). Tarih yalnız YENİ ödüncü
   durdurur; iade sürer. Eski yılın tarihi yeni yılda uygulanmaz
   (`circulation.effective_last_loan_date`); ekran bunu "uygulanmıyor" diye söyler.
2. Toplama: açık ödünç ve teslimler, son sınıflar önce; iade hatırlatma pusulası.
3. Son sınıflar ve ayrılanlar için açık ödünç ve teslim listesi (ilişik listesi
   kapsamlı çıktısı) ve son sınıf şubelerinin sınıf kitaplıkları.
4. Mezuniyetten önce ilişik listesi ve "Kütüphaneden ilişiği yoktur" belgeleri.
   Belge karne ya da diplomanın ön koşulu diye SUNULMAZ (dayanağı yok; Md. 18
   yalnız "iadesi sağlanır" der).

**Yıl başı**: ders yılı → yeni e-Okul listeleri → mutabakat (Ayrılış Havuzu) →
kapalı günler (ara tatil, yarıyıl; resmî ve dini tatiller). `year_rollover`
YOKTUR (§8.3): sınıf atlama ve mezunların ayrılışı aktarım ve mutabakatla olur.

Bütün sayılar kişisizdir (Genel Bakış kartı da bu özeti okur).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

from django.utils import timezone

from apps.kutuphane import selectors_ilisik
from apps.kutuphane.models import AnnualLibraryReview, LibraryPolicy
from apps.okul import selectors as okul_selectors
from apps.okul.models import (
    Holiday,
    HolidayKind,
    ImportRun,
    ImportSourceType,
    ImportStatus,
    SchoolConfig,
    SchoolYear,
    Student,
)

#: Yıl sonu penceresi: 1 Mayıs'tan 30 Haziran'a (ders yılı daha geç biterse bitişten
#: iki hafta sonrasına) kadar Genel Bakış'ta "Yıl Sonu" kartı görünür.
YEAR_END_START: Final = (5, 1)
YEAR_END_END: Final = (6, 30)
YEAR_END_GRACE_DAYS: Final = 14
#: Yıl başı penceresi: 15 Ağustos - 31 Ekim; ders yılı başlangıcı buna uymazsa
#: başlangıçtan üç hafta önce ile altı hafta sonrası.
YEAR_START_START: Final = (8, 15)
YEAR_START_END: Final = (10, 31)
YEAR_START_BEFORE_DAYS: Final = 21
YEAR_START_AFTER_DAYS: Final = 42
#: Ders yılı başlangıcından en çok bu kadar gün önce yapılmış aktarım "bu yılın
#: listesi" sayılır (listeler Ağustos sonunda hazırlanabilir).
IMPORT_FRESH_DAYS: Final = 45


def _gun(on: date | None) -> date:
    return on or timezone.localdate()


def year_end_window(today: date, year: SchoolYear | None) -> bool:
    """Genel Bakış'ta "Yıl Sonu" kartının görüneceği tarih penceresi."""
    bas = date(today.year, *YEAR_END_START)
    son = date(today.year, *YEAR_END_END)
    if year is not None and year.end_date.year == today.year:
        son = max(son, year.end_date + timedelta(days=YEAR_END_GRACE_DAYS))
    return bas <= today <= son


def year_start_window(today: date, year: SchoolYear | None) -> bool:
    """Genel Bakış'ta "Yıl Başı" kartının görüneceği tarih penceresi."""
    if date(today.year, *YEAR_START_START) <= today <= date(today.year, *YEAR_START_END):
        return True
    if year is None:
        return False
    return (
        year.start_date - timedelta(days=YEAR_START_BEFORE_DAYS)
        <= today
        <= year.start_date + timedelta(days=YEAR_START_AFTER_DAYS)
    )


def _yil(year: SchoolYear | None) -> dict[str, Any] | None:
    if year is None:
        return None
    return {"name": year.name, "start_date": year.start_date, "end_date": year.end_date}


def _eski_mi(tarih: date | None, year: SchoolYear | None) -> bool:
    """Tarih etkin ders yılı başlamadan önceyse yeni yılda UYGULANMAZ (F6 ekleri 4)."""
    return tarih is not None and year is not None and tarih < year.start_date


# ---------------------------------------------------------------------------
# Yıl sonu
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class YearEndSummary:
    today: date
    in_window: bool
    school_year: dict[str, Any] | None
    graduating_level: int | None
    last_loan_date: date | None
    last_loan_date_graduating: date | None
    last_loan_date_stale: bool
    last_loan_date_graduating_stale: bool
    graduating_students: int
    graduating_clear_students: int
    counts: selectors_ilisik.ClearanceCounts
    #: F8: etkin ders yılının yıl sonu kütüphane raporu (Md. 12/1, E9) — `{id,
    #: is_finalized}` ya da henüz açılmadıysa None. Adım rayına bilinçli olarak
    #: GİRMEZ (`steps` değişmedi); Genel Bakış kartı ve Yıl Sonu ekranı okur.
    annual_review: dict[str, Any] | None = None

    @property
    def steps(self) -> dict[str, bool]:
        """Adımların "tamam" işaretleri (ekrandaki onay simgesi)."""
        c = self.counts
        return {
            "dates": self.last_loan_date is not None and not self.last_loan_date_stale,
            "collection": c.open_loans == 0
            and c.teacher_deliveries == 0
            and c.section_deliveries == 0,
            "graduating": c.graduating_persons == 0
            and c.leaving_persons == 0
            and c.graduating_section_deliveries == 0,
            "clearance": c.persons == 0,
        }


def year_end_summary(*, on: date | None = None) -> YearEndSummary:
    bugun = _gun(on)
    yil = okul_selectors.active_school_year()
    politika = LibraryPolicy.load()
    seviye = selectors_ilisik.graduating_level()
    sayilar = selectors_ilisik.clearance_counts()
    son_sinif = (
        Student.objects.filter(selectors_ilisik.graduating_students_q(seviye)).count()
        if seviye is not None
        else 0
    )
    return YearEndSummary(
        today=bugun,
        in_window=year_end_window(bugun, yil),
        school_year=_yil(yil),
        graduating_level=seviye,
        last_loan_date=politika.last_loan_date,
        last_loan_date_graduating=politika.last_loan_date_graduating,
        last_loan_date_stale=_eski_mi(politika.last_loan_date, yil),
        last_loan_date_graduating_stale=_eski_mi(politika.last_loan_date_graduating, yil),
        graduating_students=son_sinif,
        # Havuzdaki son sınıf öğrencisi "ayrılan" grubundadır; son sınıf sayısında da yoktur.
        graduating_clear_students=max(0, son_sinif - sayilar.graduating_persons),
        counts=sayilar,
        annual_review=_yil_sonu_raporu(yil),
    )


def _yil_sonu_raporu(yil: SchoolYear | None) -> dict[str, Any] | None:
    """Etkin yılın yıl sonu kütüphane raporunun kişisiz durumu (F8)."""
    if yil is None:
        return None
    rapor: AnnualLibraryReview | None = AnnualLibraryReview.objects.filter(school_year=yil).first()
    if rapor is None:
        return None
    return {"id": rapor.pk, "is_finalized": rapor.is_finalized}


# ---------------------------------------------------------------------------
# Yıl başı
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class YearStartSummary:
    today: date
    in_window: bool
    school_year: dict[str, Any] | None
    school_year_ready: bool
    kademe_missing: bool
    last_student_import: date | None
    last_personnel_import: date | None
    student_import_fresh: bool
    personnel_import_fresh: bool
    leave_pool_students: int
    leave_pool_personnel: int
    school_break_count: int
    holidays_missing_years: tuple[int, ...]
    stale_last_loan_dates: bool

    @property
    def steps(self) -> dict[str, bool]:
        return {
            "school_year": self.school_year_ready,
            "import": self.school_year_ready and self.student_import_fresh,
            "leave_pool": self.school_year_ready
            and self.student_import_fresh
            and self.leave_pool_students == 0
            and self.leave_pool_personnel == 0,
            "closed_days": self.school_year_ready
            and not self.holidays_missing_years
            and self.school_break_count > 0,
        }


def _son_aktarim(tur: str) -> date | None:
    kosu: ImportRun | None = ImportRun.objects.filter(
        source_type=tur, status=ImportStatus.COMPLETED
    ).first()
    if kosu is None:
        return None
    return timezone.localdate(kosu.finished_at or kosu.started_at)


def _taze(aktarim: date | None, yil: SchoolYear | None) -> bool:
    if aktarim is None or yil is None:
        return False
    return aktarim >= yil.start_date - timedelta(days=IMPORT_FRESH_DAYS)


def missing_holiday_years(year: SchoolYear | None) -> tuple[int, ...]:
    """Ders yılının takvim yıllarından resmî tatil YA DA dini bayram kaydı eksik olanlar.

    İade tarihi kaydırması Kapalı Günler'e bakar (`circulation.holidays_missing_warning`
    ile aynı ölçüt): her yılda en az bir resmî tatil ve bir dini bayram beklenir.
    """
    if year is None:
        return ()
    eksik: list[int] = []
    for yil in range(year.start_date.year, year.end_date.year + 1):
        resmi = Holiday.objects.filter(kind=HolidayKind.OFFICIAL, start_date__year=yil).exists()
        dini = Holiday.objects.filter(kind=HolidayKind.RELIGIOUS, start_date__year=yil).exists()
        if not (resmi and dini):
            eksik.append(yil)
    return tuple(eksik)


def year_start_summary(*, on: date | None = None) -> YearStartSummary:
    bugun = _gun(on)
    yil = okul_selectors.active_school_year()
    hazir = yil is not None and yil.end_date >= bugun
    ogrenci = _son_aktarim(ImportSourceType.STUDENTS)
    personel = _son_aktarim(ImportSourceType.PERSONNEL)
    havuz = okul_selectors.leave_pool_counts()
    politika = LibraryPolicy.load()
    return YearStartSummary(
        today=bugun,
        in_window=year_start_window(bugun, yil),
        school_year=_yil(yil),
        school_year_ready=hazir,
        kademe_missing=not SchoolConfig.load().kademe,
        last_student_import=ogrenci,
        last_personnel_import=personel,
        student_import_fresh=hazir and _taze(ogrenci, yil),
        personnel_import_fresh=hazir and _taze(personel, yil),
        leave_pool_students=int(havuz["student_count"]),
        leave_pool_personnel=int(havuz["personnel_count"]),
        school_break_count=(
            okul_selectors.school_break_count(start=yil.start_date, end=yil.end_date)
            if yil is not None
            else 0
        ),
        holidays_missing_years=missing_holiday_years(yil) if hazir else (),
        stale_last_loan_dates=_eski_mi(politika.last_loan_date, yil)
        or _eski_mi(politika.last_loan_date_graduating, yil),
    )
