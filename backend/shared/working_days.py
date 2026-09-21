"""Kapalı gün aritmetiği — iade tarihi kaydırmasının tek kaynağı (tasarım §6.1, §9-5).

DD'nin `shared/working_days.py` + `services/calendar.py::is_working_day` ikilisinden
UYARLANDI (tasarım §12: `SCHOOL_BREAK`, `next_open_day`). DD'de soru "disiplin
süresi hangi gün dolar?" idi ve iş günü sayılıyordu; burada soru "iade tarihi hangi
güne düşer?" dir ve yalnız KAPALI GÜNÜN ATLANMASI gerekir (süre gün olarak işler,
Md. 18: "on beş gündür"; kaydırma yalnız son güne uygulanır).

İKİ AYRI KURAL, İKİ AYRI DAYANAK (AT-3; bu ayrım kullanıcı metnine de yansır):

1. **Hafta sonu, resmî tatil, dini bayram, idari izin — her zaman kapalı.** Okul
   Kütüphaneleri Yönetmeliği son günün tatile rastlamasını düzenlemez. Program,
   TBK md. 93'teki genel ilkeye ("sürenin son günü, kanunlarda tatil olarak kabul
   edilen bir güne rastlarsa, kendiliğinden bu günü izleyen ve tatil olmayan ilk
   güne geçer") KIYASEN iade tarihini izleyen ilk açık güne kaydırır. Öğrencinin
   lehine bir uygulamadır; doğrudan uygulama değil kıyastır. Metin:
   `docs/mevzuat/6098-turk-borclar-kanunu-md92-93.md#madde-93`.
   İdari izin (`OTHER`) kanunen tatil sayılmaz ama o gün personel izinlidir,
   kütüphane kapalıdır; iade fiilen alınamadığı için aynı kurala bağlandı.
2. **Öğrenciye kapalı gün (ara tatil, yarıyıl — `SCHOOL_BREAK`) — bayrakla.** Bu
   günler kanunen tatil DEĞİLDİR, mesai sürer; kaydırmanın mevzuat dayanağı YOKTUR.
   Okulun tercihidir: öğrenci okulda değilken sahte gecikme doğmasın diye iade
   tarihi derslerin başladığı ilk güne kayar (UY-13, SU-6). Ayarla kapatılır
   (`include_school_breaks=False`); ayar F6'da `LibraryPolicy`'ye bağlanır.

Kaydırılmış tarih kullanıcıya hiçbir yerde "Md. 18 gereği" diye SUNULMAZ
(tasarım §9-5, sözlük "İade tarihi").

Katman: çekirdek (`*_in` işlevleri) ORM'sizdir, kapalı dönemleri parametre alır ve
saf birim testiyle sınanır. Sözleşme işlevleri (`is_closed_day`, `next_open_day`)
dönem verilmezse `apps.okul.services.calendar.closed_periods_from` ile DB'den okur;
içe aktarma TEMBELDİR — `shared` açılışta `apps`'e bağlanmaz (katalog uygulaması bu
modülü hiç import etmez).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

# 5=Cumartesi, 6=Pazar (`date.weekday()`).
_WEEKEND = frozenset({5, 6})
_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class ClosedPeriod:
    """Kapsayıcı kapalı dönem [start, end]; `school_break` → öğrenciye kapalı gün."""

    start: date
    end: date
    school_break: bool = False

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


def is_weekend(day: date) -> bool:
    return day.weekday() in _WEEKEND


def _applicable(
    periods: Iterable[ClosedPeriod], *, include_school_breaks: bool
) -> list[ClosedPeriod]:
    """Kurala giren dönemler: öğrenciye kapalı günler yalnız bayrak açıkken."""
    return [p for p in periods if include_school_breaks or not p.school_break]


def is_closed_day_in(
    day: date, periods: Iterable[ClosedPeriod], *, include_school_breaks: bool
) -> bool:
    """Saf çekirdek: `day` hafta sonu mu ya da kurala giren bir dönemin içinde mi?"""
    if is_weekend(day):
        return True
    return any(
        p.covers(day) for p in _applicable(periods, include_school_breaks=include_school_breaks)
    )


def next_open_day_in(
    day: date, periods: Iterable[ClosedPeriod], *, include_school_breaks: bool = True
) -> date:
    """Saf çekirdek: `day` açıksa kendisi, değilse izleyen ilk açık gün.

    Kapalı aralıklar gün gün değil, kapsayan dönemlerin en geç bitişinin ertesine
    atlanarak geçilir. Dönem kümesi sonlu olduğundan döngü biter: her adım tarihi
    ileri taşır ve son dönemin bitişinden sonra yalnız hafta sonları kalır.
    """
    applicable = _applicable(periods, include_school_breaks=include_school_breaks)
    current = day
    while True:
        if is_weekend(current):
            current += _ONE_DAY
            continue
        covering = [p.end for p in applicable if p.covers(current)]
        if not covering:
            return current
        current = max(covering) + _ONE_DAY


def _periods_from_db(day: date) -> list[ClosedPeriod]:
    # Tembel içe aktarma: bkz. modül yorumu (katman).
    from apps.okul.services.calendar import closed_periods_from

    return closed_periods_from(day)


def is_closed_day(
    day: date,
    *,
    include_school_breaks: bool,
    periods: Iterable[ClosedPeriod] | None = None,
) -> bool:
    """`day` kapalı gün mü? Hafta sonu + resmî/dini tatil + idari izin daima;
    öğrenciye kapalı gün yalnız `include_school_breaks` ile.

    `periods` verilmezse canlı kapalı gün kayıtları DB'den okunur.
    """
    source = _periods_from_db(day) if periods is None else periods
    return is_closed_day_in(day, source, include_school_breaks=include_school_breaks)


def next_open_day(
    day: date,
    *,
    include_school_breaks: bool = True,
    periods: Iterable[ClosedPeriod] | None = None,
) -> date:
    """`day` açıksa kendisi; değilse izleyen ilk açık gün (TBK 93'e kıyasen).

    Kullanım (F6): iade tarihi = `next_open_day(bugün + 15, include_school_breaks=…)`.
    `periods` verilmezse canlı kapalı gün kayıtları DB'den okunur.
    """
    source = _periods_from_db(day) if periods is None else periods
    return next_open_day_in(day, source, include_school_breaks=include_school_breaks)
