"""Yıl sonu ve yıl başı akışlarının durum özetleri (F7 — tasarım §8.3; SU-8, EK-22).

- Tarih pencereleri: yıl sonu 1 Mayıs - 30 Haziran (ders yılı daha geç biterse
  bitişten iki hafta sonrasına dek); yıl başı 15 Ağustos - 31 Ekim ya da ders yılı
  başlangıcının çevresi.
- Eski yılın son ödünç tarihi yeni yılda "uygulanmıyor" diye işaretlenir.
- Adımların "tamam" işaretleri sayılardan türer; sayılar kişisizdir.
- `year_rollover` YOKTUR (§8.3): özet hiçbir kayıt yazmaz.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from apps.kutuphane.services import yil_akislari
from apps.kutuphane.tests.dolasim_ortak import ders_yili, odunc_ver, ogrenci, politika, uye
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, nushalar, sube, teslim_et
from apps.okul.models import (
    Holiday,
    HolidayKind,
    ImportRun,
    ImportSourceType,
    ImportStatus,
    SchoolLevel,
    SchoolYear,
    Student,
)
from apps.okul.services import persons

pytestmark = pytest.mark.django_db


def _yil(baslangic: date = date(2026, 9, 7), bitis: date = date(2027, 6, 25)) -> SchoolYear:
    return ders_yili(
        baslangic=baslangic,
        birinci_bitis=baslangic + timedelta(days=130),
        ikinci_baslangic=baslangic + timedelta(days=150),
        bitis=bitis,
    )


# ============================================================ pencereler


@pytest.mark.parametrize(
    ("gun", "beklenen"),
    [
        (date(2027, 4, 30), False),
        (date(2027, 5, 1), True),
        (date(2027, 6, 30), True),
        (date(2027, 7, 9), True),  # ders yılı 25.06'da bitti: iki hafta süre
        (date(2027, 7, 10), False),
        (date(2027, 9, 20), False),
    ],
)
def test_yil_sonu_penceresi(gun: date, beklenen: bool) -> None:
    yil = _yil()
    assert yil_akislari.year_end_window(gun, yil) is beklenen


def test_yil_sonu_penceresi_ders_yili_yokken_haziran_sonunda_kapanir() -> None:
    assert yil_akislari.year_end_window(date(2027, 6, 30), None)
    assert not yil_akislari.year_end_window(date(2027, 7, 1), None)


@pytest.mark.parametrize(
    ("gun", "beklenen"),
    [
        (date(2026, 8, 14), False),
        (date(2026, 8, 15), True),
        (date(2026, 10, 31), True),
        (date(2026, 11, 1), False),
        (date(2027, 5, 15), False),
    ],
)
def test_yil_basi_penceresi(gun: date, beklenen: bool) -> None:
    assert yil_akislari.year_start_window(gun, None) is beklenen


def test_yil_basi_penceresi_olagandisi_baslangicta_da_acilir() -> None:
    yil = _yil(baslangic=date(2027, 1, 11), bitis=date(2027, 12, 17))
    assert yil_akislari.year_start_window(date(2026, 12, 25), yil)
    assert yil_akislari.year_start_window(date(2027, 2, 20), yil)
    assert not yil_akislari.year_start_window(date(2027, 3, 1), yil)


# ============================================================ yıl sonu özeti


class TestYilSonuOzeti:
    def test_tarihler_ve_eski_yil_isareti(self) -> None:
        _yil()
        politika(last_loan_date=date(2026, 6, 1), last_loan_date_graduating=date(2027, 5, 20))

        ozet = yil_akislari.year_end_summary(on=date(2027, 5, 10))

        assert ozet.in_window
        assert ozet.last_loan_date_stale is True
        assert ozet.last_loan_date_graduating_stale is False
        assert ozet.steps["dates"] is False

    def test_sayilar_ve_adimlar(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        _yil()
        politika(last_loan_date=date(2027, 6, 4))
        son = uye(ogrenci(class_level=12))
        odunc_ver(son)
        ogrenci(class_level=12)  # açık işi olmayan son sınıf öğrencisi
        teslim_et(nushalar(2), section=sube(12, "A"))

        ozet = yil_akislari.year_end_summary()

        assert ozet.graduating_level == 12
        assert ozet.graduating_students == 2
        assert ozet.graduating_clear_students == 1
        assert ozet.counts.graduating_open_loans == 1
        assert ozet.counts.graduating_section_deliveries == 2
        assert ozet.steps == {
            "dates": True,
            "collection": False,
            "graduating": False,
            "clearance": False,
        }

    def test_her_sey_toplaninca_adimlar_tamam(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        _yil()
        politika(last_loan_date=date(2027, 6, 4))
        ozet = yil_akislari.year_end_summary()
        assert all(ozet.steps.values())

    def test_kademe_yoksa_son_sinif_sayilmaz(self) -> None:
        kademe_yaz("")
        ogrenci(class_level=12)
        ozet = yil_akislari.year_end_summary()
        assert ozet.graduating_level is None and ozet.graduating_students == 0

    def test_havuzdaki_son_sinif_ogrencisi_son_sinif_sayisinda_yok(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        giden = ogrenci(class_level=12)
        persons.add_to_leave_pool(giden, run=None)
        assert yil_akislari.year_end_summary().graduating_students == 0


# ============================================================ yıl başı özeti


def _aktarim(tur: str, gun: date) -> ImportRun:
    an = timezone.make_aware(datetime(gun.year, gun.month, gun.day, 10, 0))
    kosu: ImportRun = ImportRun.objects.create(
        source_type=tur,
        file_hash=f"{tur}-{gun.isoformat()}",
        status=ImportStatus.COMPLETED,
        started_at=an,
        finished_at=an,
    )
    return kosu


class TestYilBasiOzeti:
    def test_ders_yili_yoksa_hicbir_adim_tamam_degil(self) -> None:
        ozet = yil_akislari.year_start_summary(on=date(2026, 9, 1))
        assert ozet.school_year is None and not any(ozet.steps.values())
        assert ozet.in_window

    def test_bitmis_ders_yili_hazir_sayilmaz(self) -> None:
        _yil(baslangic=date(2025, 9, 8), bitis=date(2026, 6, 26))
        ozet = yil_akislari.year_start_summary(on=date(2026, 9, 1))
        assert ozet.school_year is not None and not ozet.school_year_ready

    def test_adimlar_sirayla_tamamlanir(self) -> None:
        yil = _yil()
        gun = date(2026, 9, 20)
        ozet = yil_akislari.year_start_summary(on=gun)
        assert ozet.steps == {
            "school_year": True,
            "import": False,
            "leave_pool": False,
            "closed_days": False,
        }

        _aktarim(ImportSourceType.STUDENTS, date(2026, 8, 28))
        _aktarim(ImportSourceType.PERSONNEL, date(2025, 9, 15))  # geçen yılın listesi
        havuzdaki = ogrenci()
        persons.add_to_leave_pool(havuzdaki, run=None)
        ozet = yil_akislari.year_start_summary(on=gun)
        assert ozet.student_import_fresh and not ozet.personnel_import_fresh
        assert ozet.last_student_import == date(2026, 8, 28)
        assert ozet.leave_pool_students == 1
        assert ozet.steps["import"] and not ozet.steps["leave_pool"]

        persons.leave_student(Student.objects.get(pk=havuzdaki.pk))
        for y in (2026, 2027):
            Holiday.objects.create(
                name="Resmî",
                start_date=date(y, 5, 19),
                end_date=date(y, 5, 19),
                kind=HolidayKind.OFFICIAL,
            )
            Holiday.objects.create(
                name="Bayram",
                start_date=date(y, 3, 20),
                end_date=date(y, 3, 22),
                kind=HolidayKind.RELIGIOUS,
            )
        ozet = yil_akislari.year_start_summary(on=gun)
        assert ozet.holidays_missing_years == ()
        assert ozet.steps["leave_pool"] and not ozet.steps["closed_days"]  # ara tatil yok

        Holiday.objects.create(
            name="Yarıyıl",
            start_date=yil.start_date + timedelta(days=131),
            end_date=yil.start_date + timedelta(days=149),
            kind=HolidayKind.SCHOOL_BREAK,
        )
        ozet = yil_akislari.year_start_summary(on=gun)
        assert all(ozet.steps.values())

    def test_eksik_tatil_yillari_ve_eski_son_odunc_tarihi(self) -> None:
        _yil()
        politika(last_loan_date=date(2026, 6, 5))
        ozet = yil_akislari.year_start_summary(on=date(2026, 9, 20))
        assert ozet.holidays_missing_years == (2026, 2027)
        assert ozet.stale_last_loan_dates is True
