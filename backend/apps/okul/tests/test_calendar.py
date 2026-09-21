"""Kapalı günler — model kısıtları, tohumlama fikirdeşliği ve DB'den kapalı gün kaynağı.

Sabitlenen sözleşmeler (tasarım §6.1 Holiday, §9-5):

- Kayıt kısıtları DB'dedir: bitiş başlangıçtan önce olamaz, tür listedendir,
  "tahmini" yalnız dini bayramda olur, (ad, başlangıç) canlı kayıtta tekildir.
- Tohumlama TAKVİM YILINA göredir, yılın yedi sabit resmî tatilini (yaz dahil) ve
  gömülü tablodaki dini bayramları yazar; 2027 ve sonrası bayramlar tahminidir.
- Tohumlama fikirdeştir; tahmini bayramı silip doğru tarihle elle giren kullanıcı
  ikinci tohumlamada kopya görmez.
- Arife günleri tohumlanmaz (açık gün kararı, `services/calendar.py` yorumu).
- `shared.working_days` sözleşme işlevleri dönem verilmeyince canlı kayıtları okur;
  silinmiş kayıt kapalı gün sayılmaz.

Tarihler sabittir; kişisel veri yoktur.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.okul.models import Holiday, HolidayKind
from apps.okul.services import calendar as calendar_service
from shared.working_days import is_closed_day, next_open_day

pytestmark = pytest.mark.django_db


def _kayit(
    ad: str,
    bas: date,
    bit: date | None = None,
    tur: str = HolidayKind.OFFICIAL,
    tahmini: bool = False,
) -> Holiday:
    kayit: Holiday = Holiday.objects.create(
        name=ad, start_date=bas, end_date=bit or bas, kind=tur, is_estimated=tahmini
    )
    return kayit


# ---------------------------------------------------------------------------
# Model kısıtları
# ---------------------------------------------------------------------------


class TestModelKisitlari:
    def test_bitis_baslangictan_once_olamaz(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            _kayit("Ters", date(2026, 11, 13), date(2026, 11, 9))

    def test_tur_listeden_olmalidir(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            _kayit("Bilinmeyen", date(2026, 11, 9), tur="SUMMER")

    @pytest.mark.parametrize(
        "tur", [HolidayKind.OFFICIAL, HolidayKind.SCHOOL_BREAK, HolidayKind.OTHER]
    )
    def test_tahmini_yalniz_dini_bayramda_olur(self, tur: str) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            _kayit("Tahmini olamaz", date(2026, 11, 9), tur=tur, tahmini=True)

    def test_tahmini_dini_bayram_kabul_edilir(self) -> None:
        kayit = _kayit(
            "Ramazan Bayramı",
            date(2027, 3, 9),
            date(2027, 3, 11),
            tur=HolidayKind.RELIGIOUS,
            tahmini=True,
        )
        assert kayit.is_estimated is True

    def test_ayni_ad_ve_baslangic_canli_kayitta_tekil(self) -> None:
        _kayit("Ara tatil", date(2026, 11, 9), date(2026, 11, 13), tur=HolidayKind.SCHOOL_BREAK)
        with pytest.raises(IntegrityError), transaction.atomic():
            _kayit("Ara tatil", date(2026, 11, 9), date(2026, 11, 10), tur=HolidayKind.SCHOOL_BREAK)

    def test_silinen_kaydin_yerine_ayni_kayit_acilabilir(self) -> None:
        eski = _kayit("Ara tatil", date(2026, 11, 9), tur=HolidayKind.SCHOOL_BREAK)
        eski.delete()
        yeni = _kayit("Ara tatil", date(2026, 11, 9), tur=HolidayKind.SCHOOL_BREAK)
        assert Holiday.all_objects.filter(name="Ara tatil").count() == 2
        assert list(Holiday.objects.all()) == [yeni]

    def test_ogrenciye_kapali_gun_turunun_etiketi_sozluge_uyar(self) -> None:
        assert HolidayKind.SCHOOL_BREAK.label == "Öğrenciye kapalı gün"
        assert HolidayKind.OFFICIAL.label == "Resmî tatil"


# ---------------------------------------------------------------------------
# Tohumlama
# ---------------------------------------------------------------------------


class TestTohumlama:
    def test_yilin_yedi_resmi_tatili_ve_kesin_bayramlari_eklenir(self) -> None:
        sonuc = calendar_service.seed_holidays(2026)

        assert (sonuc.year, sonuc.created, sonuc.skipped) == (2026, 9, 0)
        assert sonuc.religious_available is True
        resmi = Holiday.objects.filter(kind=HolidayKind.OFFICIAL)
        assert resmi.count() == 7
        # Yaz tatilleri de yazılır (DD ders yılı dışını atlıyordu; iade tarihi yazın da hesaplanır).
        assert set(resmi.values_list("start_date", flat=True)) >= {
            date(2026, 7, 15),
            date(2026, 8, 30),
        }
        assert all(h.start_date == h.end_date for h in resmi)
        dini = Holiday.objects.filter(kind=HolidayKind.RELIGIOUS).order_by("start_date")
        assert [(h.name, h.start_date, h.end_date, h.is_estimated) for h in dini] == [
            ("Ramazan Bayramı", date(2026, 3, 20), date(2026, 3, 22), False),
            ("Kurban Bayramı", date(2026, 5, 27), date(2026, 5, 30), False),
        ]

    def test_2027_ve_sonrasi_bayramlar_tahminidir(self) -> None:
        for yil in (2027, 2028, 2029):
            calendar_service.seed_holidays(yil)
        dini = Holiday.objects.filter(kind=HolidayKind.RELIGIOUS)
        assert dini.count() == 6
        assert set(dini.values_list("is_estimated", flat=True)) == {True}
        assert not Holiday.objects.filter(kind=HolidayKind.OFFICIAL, is_estimated=True).exists()

    def test_ikinci_tohumlama_kopya_uretmez(self) -> None:
        calendar_service.seed_holidays(2027)
        sonuc = calendar_service.seed_holidays(2027)
        assert (sonuc.created, sonuc.skipped) == (0, 9)
        assert Holiday.objects.count() == 9

    def test_elle_duzeltilen_tahmini_bayram_yeniden_eklenmez(self) -> None:
        calendar_service.seed_holidays(2027)
        tahmini = Holiday.objects.get(name="Ramazan Bayramı", start_date=date(2027, 3, 9))
        calendar_service.delete_holiday(tahmini)
        calendar_service.create_holiday(
            name="Ramazan Bayramı",
            start_date=date(2027, 3, 10),
            end_date=date(2027, 3, 12),
            kind=HolidayKind.RELIGIOUS,
        )

        sonuc = calendar_service.seed_holidays(2027)

        assert sonuc.created == 0
        ramazan = Holiday.objects.get(name="Ramazan Bayramı")
        assert (ramazan.start_date, ramazan.is_estimated) == (date(2027, 3, 10), False)

    def test_elle_girilmis_resmi_tatil_farkli_adla_da_atlanir(self) -> None:
        _kayit("29 Ekim", date(2026, 10, 29))
        sonuc = calendar_service.seed_holidays(2026)
        assert sonuc.skipped == 1
        assert Holiday.objects.filter(start_date=date(2026, 10, 29)).count() == 1

    def test_ayni_gune_dusen_ogrenciye_kapali_gun_resmi_tatili_engellemez(self) -> None:
        _kayit(
            "Yıl sonu ara tatili",
            date(2026, 12, 28),
            date(2027, 1, 1),
            tur=HolidayKind.SCHOOL_BREAK,
        )
        calendar_service.seed_holidays(2027)
        assert Holiday.objects.filter(
            kind=HolidayKind.OFFICIAL, start_date=date(2027, 1, 1)
        ).exists()

    def test_arife_gunleri_tohumlanmaz(self) -> None:
        calendar_service.seed_holidays(2026)
        for arife in (date(2026, 10, 28), date(2026, 3, 19), date(2026, 5, 26)):
            assert not Holiday.objects.filter(
                start_date__lte=arife, end_date__gte=arife
            ).exists(), arife

    def test_tablo_disi_yilda_dini_bayram_yok_ve_yanit_bunu_soyler(self) -> None:
        sonuc = calendar_service.seed_holidays(2031)
        assert (sonuc.created, sonuc.religious_available) == (7, False)
        assert not Holiday.objects.filter(kind=HolidayKind.RELIGIOUS).exists()

    @pytest.mark.parametrize("yil", [1999, 2101])
    def test_aralik_disi_yil_reddedilir(self, yil: int) -> None:
        with pytest.raises(ValueError, match="arasında olmalıdır"):
            calendar_service.seed_holidays(yil)


# ---------------------------------------------------------------------------
# Elle ekleme (servis sözleşmesi)
# ---------------------------------------------------------------------------


class TestElleEkleme:
    def test_elle_girilen_kayit_kesin_tarihtir_ve_ad_kirpilir(self) -> None:
        kayit = calendar_service.create_holiday(
            name="  Yarıyıl tatili ",
            start_date=date(2027, 1, 25),
            end_date=date(2027, 2, 5),
            kind=HolidayKind.SCHOOL_BREAK,
        )
        assert (kayit.name, kayit.is_estimated) == ("Yarıyıl tatili", False)

    @pytest.mark.parametrize(
        ("alanlar", "alan", "parca"),
        [
            ({"name": "  "}, "name", "Ad yazılmalıdır"),
            ({"kind": "SUMMER"}, "kind", "Geçerli bir tür"),
            ({"end_date": date(2027, 1, 20)}, "end_date", "başlangıçtan önce"),
            ({"end_date": date(2027, 6, 1)}, "end_date", "en çok 120 gün"),
        ],
    )
    def test_gecersiz_girdi_turkce_reddedilir(
        self, alanlar: dict[str, object], alan: str, parca: str
    ) -> None:
        girdi: dict[str, object] = {
            "name": "Yarıyıl tatili",
            "start_date": date(2027, 1, 25),
            "end_date": date(2027, 2, 5),
            "kind": HolidayKind.SCHOOL_BREAK,
        }
        girdi.update(alanlar)
        with pytest.raises(ValidationError) as hata:
            calendar_service.create_holiday(**girdi)  # type: ignore[arg-type]
        assert parca in " ".join(hata.value.message_dict[alan])

    def test_ayni_ad_ve_baslangic_turkce_reddedilir(self) -> None:
        girdi = {
            "name": "Yarıyıl tatili",
            "start_date": date(2027, 1, 25),
            "end_date": date(2027, 2, 5),
            "kind": HolidayKind.SCHOOL_BREAK,
        }
        calendar_service.create_holiday(**girdi)  # type: ignore[arg-type]
        with pytest.raises(ValidationError) as hata:
            calendar_service.create_holiday(**girdi)  # type: ignore[arg-type]
        assert hata.value.message_dict["name"] == [calendar_service.DUPLICATE_MESSAGE]

    def test_yarista_teklik_kisiti_ayni_turkce_rede_cevrilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ön denetimden sonra araya giren kayıt: DB kısıtı IntegrityError → Türkçe ret."""

        def yarisan_kayit(**_: object) -> Holiday:
            raise IntegrityError("UNIQUE constraint failed")

        monkeypatch.setattr(Holiday.objects, "create", yarisan_kayit)
        with pytest.raises(ValidationError) as hata:
            calendar_service.create_holiday(
                name="Yarıyıl tatili",
                start_date=date(2027, 1, 25),
                end_date=date(2027, 2, 5),
                kind=HolidayKind.SCHOOL_BREAK,
            )
        assert hata.value.message_dict["name"] == [calendar_service.DUPLICATE_MESSAGE]


# ---------------------------------------------------------------------------
# DB'den kapalı gün kaynağı (`shared.working_days` sözleşme işlevleri)
# ---------------------------------------------------------------------------


class TestKapaliGunKaynagi:
    def test_tohumlanan_bayram_iade_tarihini_kaydirir(self) -> None:
        calendar_service.seed_holidays(2026)
        # Kurban Bayramı 27-30 Mayıs 2026 (Çarşamba-Cumartesi) → 1 Haziran Pazartesi.
        assert next_open_day(date(2026, 5, 27)) == date(2026, 6, 1)
        # Cumhuriyet Bayramı Perşembe → Cuma.
        assert next_open_day(date(2026, 10, 29)) == date(2026, 10, 30)

    def test_ogrenciye_kapali_gun_bayrakla_calisir(self) -> None:
        _kayit(
            "1. dönem ara tatili",
            date(2026, 11, 9),
            date(2026, 11, 13),
            tur=HolidayKind.SCHOOL_BREAK,
        )
        gun = date(2026, 11, 11)  # Çarşamba
        assert is_closed_day(gun, include_school_breaks=True)
        assert not is_closed_day(gun, include_school_breaks=False)
        assert next_open_day(gun) == date(2026, 11, 16)
        assert next_open_day(gun, include_school_breaks=False) == gun

    def test_idari_izin_her_zaman_kapalidir(self) -> None:
        _kayit("İdari izin", date(2026, 12, 31), tur=HolidayKind.OTHER)  # Perşembe
        assert is_closed_day(date(2026, 12, 31), include_school_breaks=False)
        assert next_open_day(date(2026, 12, 31), include_school_breaks=False) == date(2027, 1, 1)

    def test_silinen_kayit_kapali_gun_sayilmaz(self) -> None:
        kayit = _kayit("Cumhuriyet Bayramı", date(2026, 10, 29))
        calendar_service.delete_holiday(kayit)
        assert next_open_day(date(2026, 10, 29)) == date(2026, 10, 29)

    def test_kaynak_yalniz_gunu_etkileyen_kayitlari_okur(self) -> None:
        _kayit("Geçmiş", date(2026, 3, 2))
        _kayit("Kapsayan", date(2026, 10, 26), date(2026, 10, 30), tur=HolidayKind.SCHOOL_BREAK)
        _kayit("Gelecek", date(2027, 1, 1))
        donemler = calendar_service.closed_periods_from(date(2026, 10, 28))
        assert sorted((p.start, p.school_break) for p in donemler) == [
            (date(2026, 10, 26), True),
            (date(2027, 1, 1), False),
        ]
