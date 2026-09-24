"""Ağ Kataloğu ayarı — servis, uç ve çok okunanlar yazıcısı (F5, tasarım §5.2, §5.3, §6.2).

`KatalogAyari` port ve IP'nin tek kaynağıdır; yazma yalnız yönetici kipindedir
ve uç görevli kipi izin listesinde DEĞİLDİR (CLAUDE.md §2-4).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.kutuphane.models import (
    KATALOG_VARSAYILAN_PORT,
    DinlemeKipi,
    KatalogAyari,
    KatalogPopuler,
    PopulerPencereTuru,
)
from apps.kutuphane.serializers_katalog import KATALOG_AYARI_ALANLARI
from apps.kutuphane.services import katalog_ayari as servis
from apps.kutuphane.services import populer
from apps.kutuphane.tests.ortak import eser
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import IZIN_LISTESI
from apps.okul.models import SchoolConfig
from katalog.bakim import BakimKapisi

UC = "/api/v1/library/network-catalog/settings/"

pytestmark = pytest.mark.django_db


# ====================================================================== servis


def test_satir_yokken_okuma_varsayilanlari_dondurur_ve_yazmaz() -> None:
    ayar = servis.katalog_ayari()

    assert ayar.acik is False  # varsayılan KAPALI (§5.2)
    assert ayar.port == KATALOG_VARSAYILAN_PORT == 8765
    assert ayar.dinleme_kipi == DinlemeKipi.ALL
    assert ayar.uyku_engelleme is True
    assert ayar.vitrin_acik is True and ayar.konular_acik is True
    assert ayar.tahta_cidrleri == []
    assert not KatalogAyari.objects.exists()


def test_guncelleme_kismidir() -> None:
    servis.update_katalog_ayari(acik=True, port=9000)
    servis.update_katalog_ayari(vitrin_acik=False)

    ayar = servis.katalog_ayari()
    assert (ayar.acik, ayar.port, ayar.vitrin_acik) == (True, 9000, False)


@pytest.mark.parametrize(
    ("alanlar", "hatali_alan"),
    [
        ({"port": 80}, "port"),
        ({"port": 70000}, "port"),
        ({"dinleme_kipi": DinlemeKipi.SELECTED}, "secili_ip"),
        ({"dinleme_kipi": "HEPSI"}, "dinleme_kipi"),
        ({"secili_ip": "999.1.1.1"}, "secili_ip"),
        ({"secili_ip": "127.0.0.1"}, "secili_ip"),
        ({"secili_ip": "169.254.3.4"}, "secili_ip"),
        ({"secili_ip": "0.0.0.0"}, "secili_ip"),  # noqa: S104 — reddedildiği sınanıyor
        ({"secili_ip": "fe80::1"}, "secili_ip"),
        ({"son_afis_ip": "abc"}, "son_afis_ip"),
        ({"tahta_cidrleri": ["10.0.0.0/8"]}, "tahta_cidrleri"),  # özel aralığın tamamı
        ({"tahta_cidrleri": ["192.168.0.0/16", "172.16.0.0/12"]}, "tahta_cidrleri"),
        ({"tahta_cidrleri": ["8.8.8.0/24"]}, "tahta_cidrleri"),  # genel adres
        ({"tahta_cidrleri": ["10.1.2.3/24"]}, "tahta_cidrleri"),  # konak bitleri dolu
        ({"tahta_cidrleri": ["yanlis"]}, "tahta_cidrleri"),
        ({"tahta_cidrleri": "10.1.2.0/24"}, "tahta_cidrleri"),  # liste değil
        ({"tahta_cidrleri": [f"10.{i}.0.0/24" for i in range(17)]}, "tahta_cidrleri"),
        ({"kutuphane_saatleri": "x" * 501}, "kutuphane_saatleri"),
        ({"bilinmeyen": 1}, "bilinmeyen"),
    ],
)
def test_gecersiz_ayar_turkce_iletiyle_reddedilir_ve_yazilmaz(
    alanlar: dict[str, Any], hatali_alan: str
) -> None:
    with pytest.raises(ValidationError) as hata:
        servis.update_katalog_ayari(**alanlar)

    assert hatali_alan in hata.value.message_dict
    assert all(m for m in hata.value.messages)
    assert not KatalogAyari.objects.exists() or servis.katalog_ayari().port == 8765


def test_secili_ip_ve_tahta_bloklari_normallesir() -> None:
    ayar = servis.update_katalog_ayari(
        dinleme_kipi=DinlemeKipi.SELECTED,
        secili_ip=" 10.20.30.40 ",
        tahta_cidrleri=["10.50.0.0/22", " 10.50.0.0/22", "172.20.4.0/24"],
    )

    assert ayar.secili_ip == "10.20.30.40"
    assert ayar.tahta_cidrleri == ["10.50.0.0/22", "172.20.4.0/24"]


def test_secili_ip_kipinde_bos_ip_db_kisitiyla_da_reddedilir() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        KatalogAyari.objects.create(pk=1, dinleme_kipi=DinlemeKipi.SELECTED, secili_ip="")


def test_kutuphane_saatleri_okul_satirina_yazilir() -> None:
    servis.update_katalog_ayari(kutuphane_saatleri="  Hafta içi 08.30-16.30 ")

    assert SchoolConfig.load().kutuphane_saatleri == "Hafta içi 08.30-16.30"
    assert servis.kutuphane_saatleri() == "Hafta içi 08.30-16.30"


def test_bos_saat_icin_okul_satiri_acilmaz() -> None:
    servis.update_katalog_ayari(kutuphane_saatleri="")

    assert not SchoolConfig.objects.exists()


def test_gorevli_kipinde_yazma_reddedilir_sistem_yazimi_gecer() -> None:
    KIP.gorevliye_gec()

    with pytest.raises(servis.AyarYetkisiz):
        servis.update_katalog_ayari(acik=True)
    assert not KatalogAyari.objects.exists()

    servis.update_katalog_ayari(son_afis_ip="10.1.1.1", sistem_yazimi=True)
    assert servis.katalog_ayari().son_afis_ip == "10.1.1.1"


def test_kilitliyken_yazma_reddedilir(kilitli: Path) -> None:
    with pytest.raises(servis.AyarYetkisiz):
        servis.update_katalog_ayari(acik=True)


@pytest.mark.django_db(transaction=True)
def test_dinleyici_kayit_kalicilasinca_cagrilir_ve_hatasi_kaydi_geri_almaz() -> None:
    gorulen: list[tuple[bool, int]] = []

    def dinleyici(ayar: KatalogAyari) -> None:
        gorulen.append((ayar.acik, ayar.port))

    def patlayan(ayar: KatalogAyari) -> None:
        raise RuntimeError("dinleyici hatası")

    sil_1 = servis.ayar_degisince(patlayan)
    sil_2 = servis.ayar_degisince(dinleyici)
    try:
        servis.update_katalog_ayari(acik=True, port=8800)
        with pytest.raises(ValidationError):
            servis.update_katalog_ayari(port=1)  # geçersiz: dinleyici çağrılmaz
    finally:
        sil_1()
        sil_2()
    servis.update_katalog_ayari(port=8801)  # kayıt silindi: çağrılmaz

    assert gorulen == [(True, 8800)]
    assert servis.katalog_ayari().port == 8801


# ========================================================================= uç


def test_uc_satir_yokken_varsayilanlari_ve_alan_listesini_doner() -> None:
    yanit = APIClient().get(UC)

    assert yanit.status_code == 200
    assert list(yanit.json()) == list(KATALOG_AYARI_ALANLARI)
    assert yanit.json() == {
        "acik": False,
        "port": 8765,
        "dinleme_kipi": "ALL",
        "secili_ip": "",
        "son_afis_ip": "",
        "uyku_engelleme": True,
        "vitrin_acik": True,
        "konular_acik": True,
        "tahta_cidrleri": [],
        "kutuphane_saatleri": "",
    }


def test_alan_listesi_anlik_goruntusu() -> None:
    assert KATALOG_AYARI_ALANLARI == (
        "acik",
        "port",
        "dinleme_kipi",
        "secili_ip",
        "son_afis_ip",
        "uyku_engelleme",
        "vitrin_acik",
        "konular_acik",
        "tahta_cidrleri",
        "kutuphane_saatleri",
    )


def test_uc_kismi_put_yazar_ve_saatleri_dondurur() -> None:
    istemci = APIClient()
    istemci.put(UC, {"acik": True}, format="json")
    yanit = istemci.put(
        UC, {"kutuphane_saatleri": "08.30-16.30", "tahta_cidrleri": ["10.9.0.0/24"]}, format="json"
    )

    assert yanit.status_code == 200, yanit.json()
    assert yanit.json()["acik"] is True
    assert yanit.json()["kutuphane_saatleri"] == "08.30-16.30"
    assert yanit.json()["tahta_cidrleri"] == ["10.9.0.0/24"]


def test_uc_gecersiz_degerde_400_ve_alan_hatasi() -> None:
    yanit = APIClient().put(UC, {"port": 80}, format="json")

    assert yanit.status_code == 400
    govde = yanit.json()
    assert govde["code"] == "validation_error"
    assert "port" in govde["fields"]
    assert "1024" in govde["message"]


def test_uc_gorevli_kipinde_her_yontemde_403_kip_yetkisiz() -> None:
    KIP.gorevliye_gec()
    istemci = APIClient()

    for yanit in (istemci.get(UC), istemci.put(UC, {"acik": True}, format="json")):
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"
    assert not KatalogAyari.objects.exists()


def test_uc_gorevli_kipi_izin_listesinde_degil() -> None:
    assert "library-network-catalog-settings" not in {kural.uc for kural in IZIN_LISTESI}


def test_uc_kurulum_durumunda_servis_kapisi_403_doner(parolasiz: Path) -> None:
    """Parola kurulmadan (kip "kurulum") ara katman geçirir; servis yazmayı keser."""
    yanit = APIClient().put(UC, {"acik": True}, format="json")

    assert yanit.status_code == 403
    assert yanit.json()["code"] == "kip_yetkisiz"
    assert "yönetici kipinde" in yanit.json()["message"]


# ======================================================= çok okunanlar yazıcısı


@pytest.fixture
def uc_eser() -> list[int]:
    return [eser(title=f"Popüler {i}").pk for i in range(3)]


def test_pencere_sirasi_yazilir_tekrarsiz_ve_sayisiz(uc_eser: list[int]) -> None:
    yazilan = populer.pencereyi_yaz(
        PopulerPencereTuru.DONEM,
        "2026-2027/1",
        [uc_eser[2], uc_eser[0], uc_eser[2], 999_999],
        hesaplanma=date(2026, 9, 24),
    )

    satirlar = list(
        KatalogPopuler.objects.filter(pencere="2026-2027/1").values_list("sira", "eser_id")
    )
    assert yazilan == 2
    assert satirlar == [(1, uc_eser[2]), (2, uc_eser[0])]
    alanlar = {f.name for f in KatalogPopuler._meta.get_fields()}
    assert not alanlar & {"sayi", "adet", "odunc_sayisi", "uye_sayisi"}


def test_pencere_yeniden_yazilir_dondurulunca_yazilmaz(uc_eser: list[int]) -> None:
    populer.pencereyi_yaz("AY", "2026-09", uc_eser, hesaplanma=date(2026, 9, 24))
    populer.pencereyi_yaz("AY", "2026-09", uc_eser[:1], hesaplanma=date(2026, 9, 25))
    assert KatalogPopuler.objects.filter(pencere="2026-09").count() == 1

    assert populer.pencereyi_dondur("AY", "2026-09") == 1
    with pytest.raises(populer.PencereDonduruldu):
        populer.pencereyi_yaz("AY", "2026-09", uc_eser, hesaplanma=date(2026, 10, 1))
    assert KatalogPopuler.objects.filter(pencere="2026-09").count() == 1


def test_pencere_en_cok_on_eser_tutar() -> None:
    idler = [eser(title=f"Eser {i:02d}").pk for i in range(15)]

    assert populer.pencereyi_yaz("DONEM", "x", idler, hesaplanma=date(2026, 9, 24)) == 10


def test_bilinmeyen_pencere_turu_reddedilir() -> None:
    with pytest.raises(ValueError):
        populer.pencereyi_yaz("YIL", "2026", [], hesaplanma=date(2026, 9, 24))


def test_gunluk_is_bakim_kapisindan_gecer() -> None:
    kapi = BakimKapisi()
    assert populer.gunluk_is(date(2026, 9, 24), kapi=kapi) == "tamam"
    assert kapi.ucusta == 0

    kapi.bakima_al(bekleme_sn=0.01)
    assert populer.gunluk_is(date(2026, 9, 24), kapi=kapi) == "bakimda"


def test_gunluk_is_hatayi_yutar(monkeypatch: pytest.MonkeyPatch) -> None:
    def patlayan(bugun: date) -> Iterator[Any]:
        raise RuntimeError("hesap hatası")

    monkeypatch.setattr(populer, "_siralama_hesapla", patlayan)

    assert populer.gunluk_is(date(2026, 9, 24), kapi=BakimKapisi()) == "hata"
