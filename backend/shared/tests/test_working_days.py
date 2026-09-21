"""`shared.working_days` saf çekirdeği — kapalı gün atlama (tasarım §9-5).

DB'siz: kapalı dönemler `periods=` ile verilir. Sabitlenen sözleşmeler:

- Açık gün kendisini döndürür (kaydırma yalnız kapalı güne uygulanır).
- Hafta sonu, resmî/dini tatil ve idari izin HER ZAMAN kapalıdır (TBK 93'e kıyasen).
- Öğrenciye kapalı gün (ara tatil, yarıyıl) YALNIZ bayrak açıkken kapalıdır.
- Arka arkaya kapalı günler ve yıl sonu geçişi tek seferde atlanır.

Bütün tarihler sabittir (gece yarısı tuzağı yok); haftanın günleri yorumda yazılı.
"""

from __future__ import annotations

from datetime import date

import pytest

from shared.working_days import (
    ClosedPeriod,
    is_closed_day,
    is_closed_day_in,
    is_weekend,
    next_open_day,
    next_open_day_in,
)

CUMHURIYET = ClosedPeriod(date(2026, 10, 29), date(2026, 10, 29))  # Perşembe
YILBASI_2027 = ClosedPeriod(date(2027, 1, 1), date(2027, 1, 1))  # Cuma
KURBAN_2027 = ClosedPeriod(date(2027, 5, 16), date(2027, 5, 19))  # Pazar-Çarşamba
YARIYIL = ClosedPeriod(date(2027, 1, 25), date(2027, 2, 5), school_break=True)  # Pzt-Cuma


def test_hafta_sonu_kapalidir() -> None:
    assert is_weekend(date(2026, 10, 31))  # Cumartesi
    assert is_weekend(date(2026, 11, 1))  # Pazar
    assert not is_weekend(date(2026, 11, 2))  # Pazartesi
    # Hafta sonu bayraktan ve kayıttan bağımsız kapalıdır.
    assert is_closed_day_in(date(2026, 10, 31), [], include_school_breaks=False)
    assert not is_closed_day_in(date(2026, 11, 2), [], include_school_breaks=False)


def test_acik_gun_kendisini_dondurur() -> None:
    assert next_open_day_in(date(2026, 11, 2), [CUMHURIYET]) == date(2026, 11, 2)


def test_hafta_sonu_pazartesiye_kayar() -> None:
    assert next_open_day_in(date(2026, 10, 31), []) == date(2026, 11, 2)
    assert next_open_day_in(date(2026, 11, 1), []) == date(2026, 11, 2)


def test_resmi_tatil_izleyen_is_gunune_kayar() -> None:
    assert next_open_day_in(date(2026, 10, 29), [CUMHURIYET]) == date(2026, 10, 30)


def test_bayram_araliginin_icinden_bitisinin_ertesine_kayar() -> None:
    assert next_open_day_in(date(2027, 5, 17), [KURBAN_2027]) == date(2027, 5, 20)


@pytest.mark.parametrize(
    ("bayrak", "beklenen"),
    [(True, date(2027, 2, 8)), (False, date(2027, 1, 27))],
)
def test_ogrenciye_kapali_gun_yalniz_bayrakla_kapalidir(bayrak: bool, beklenen: date) -> None:
    gun = date(2027, 1, 27)  # Çarşamba, yarıyıl içinde
    assert next_open_day_in(gun, [YARIYIL], include_school_breaks=bayrak) == beklenen
    assert is_closed_day_in(gun, [YARIYIL], include_school_breaks=bayrak) is bayrak


def test_resmi_tatil_bayraktan_bagimsiz_kapalidir() -> None:
    gun = date(2026, 10, 29)
    assert is_closed_day_in(gun, [CUMHURIYET], include_school_breaks=False)
    assert next_open_day_in(gun, [CUMHURIYET], include_school_breaks=False) == date(2026, 10, 30)


def test_arka_arkaya_kapali_gunler_tek_seferde_atlanir() -> None:
    """23 Nisan (Cuma) + hafta sonu + ara tatil (Pzt-Cuma) + 1 Mayıs (Cumartesi) + Pazar."""
    donemler = [
        ClosedPeriod(date(2027, 4, 23), date(2027, 4, 23)),
        ClosedPeriod(date(2027, 4, 26), date(2027, 4, 30), school_break=True),
        ClosedPeriod(date(2027, 5, 1), date(2027, 5, 1)),
    ]
    assert next_open_day_in(date(2027, 4, 23), donemler) == date(2027, 5, 3)
    # Bayraksız: ara tatil açık sayılır → hafta sonundan sonraki Pazartesi.
    assert next_open_day_in(date(2027, 4, 23), donemler, include_school_breaks=False) == date(
        2027, 4, 26
    )


def test_ic_ice_ve_ortusen_donemler() -> None:
    """Örtüşen aralıklarda en geç bitiş esas alınır; iç içe kısa dönem atlamayı kısaltmaz."""
    donemler = [
        ClosedPeriod(date(2027, 1, 25), date(2027, 1, 27)),
        ClosedPeriod(date(2027, 1, 26), date(2027, 2, 3), school_break=True),
        ClosedPeriod(date(2027, 1, 28), date(2027, 1, 28)),
    ]
    assert next_open_day_in(date(2027, 1, 25), donemler) == date(2027, 2, 4)
    assert next_open_day_in(date(2027, 1, 25), donemler, include_school_breaks=False) == date(
        2027, 1, 29
    )


def test_yil_sonu_gecisi() -> None:
    """Aralık sonu öğrenciye kapalı (Pzt-Per) + Yılbaşı (Cuma) + hafta sonu → 4 Ocak Pazartesi."""
    donemler = [
        ClosedPeriod(date(2026, 12, 28), date(2026, 12, 31), school_break=True),
        YILBASI_2027,
    ]
    assert next_open_day_in(date(2026, 12, 28), donemler) == date(2027, 1, 4)
    assert next_open_day_in(date(2026, 12, 31), donemler, include_school_breaks=False) == date(
        2026, 12, 31
    )


def test_sozlesme_islevleri_verilen_donemlerle_db_ye_gitmez() -> None:
    """`periods=` verilince DB okunmaz (bu test django_db işareti taşımaz)."""
    assert is_closed_day(date(2026, 10, 29), include_school_breaks=True, periods=[CUMHURIYET])
    assert next_open_day(date(2026, 10, 29), periods=[CUMHURIYET]) == date(2026, 10, 30)


def test_varsayilan_bayrak_ogrenciye_kapali_gunu_de_atlar() -> None:
    assert next_open_day(date(2027, 1, 27), periods=[YARIYIL]) == date(2027, 2, 8)
