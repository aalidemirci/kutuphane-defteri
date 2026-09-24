"""Hız sınırı, bakım kapısı, istek çözümü ve sayaçlar — birim testleri (tasarım §5.3, §5.5).

Veritabanı istemez. Hız sınırının uygulamadaki etkisi (429, `Retry-After`,
`X-Forwarded-For`'un yok sayılması) kurulumsuz bir katalog örneğiyle sınanır.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import pytest

from katalog.app import create_app
from katalog.bakim import KAPI, BakimKapisi
from katalog.istek import (
    EN_UZUN_SORGU_DIZESI,
    AdresCokUzun,
    GecersizIstek,
    Istek,
    sorgu_dizesini_coz,
    yolu_coz,
    yuzde_coz,
    yuzde_kodla,
)
from katalog.sayac import OLAYLAR, SAKLANAN_GUN, GunlukSayaclar
from katalog.sinir import HizSiniri
from katalog.tests.conftest import cagir, ortam_kur


class _Saat:
    def __init__(self) -> None:
        self.an = 1000.0

    def __call__(self) -> float:
        return self.an


# =================================================================== hız sınırı


def test_kova_kapasite_kadar_istege_izin_verir_sonra_reddeder() -> None:
    saat = _Saat()
    sinir = HizSiniri(kapasite=3, dolum_hizi=1, saat=saat)

    assert [sinir.izin_ver("10.0.0.1")[0] for _ in range(4)] == [True, True, True, False]
    assert sinir.izin_ver("10.0.0.1") == (False, 1)


def test_kova_zamanla_dolar_ama_kapasiteyi_asmaz() -> None:
    saat = _Saat()
    sinir = HizSiniri(kapasite=2, dolum_hizi=0.5, saat=saat)
    sinir.izin_ver("a")
    sinir.izin_ver("a")
    assert sinir.izin_ver("a") == (False, 2)  # bir jeton için 2 sn

    saat.an += 2
    assert sinir.izin_ver("a")[0] is True
    saat.an += 1000
    assert [sinir.izin_ver("a")[0] for _ in range(3)] == [True, True, False]


def test_adresler_ayri_kovalardadir() -> None:
    sinir = HizSiniri(kapasite=1, dolum_hizi=0.001, saat=_Saat())

    assert sinir.izin_ver("10.0.0.1")[0] is True
    assert sinir.izin_ver("10.0.0.1")[0] is False
    assert sinir.izin_ver("10.0.0.2")[0] is True


def test_kova_tablosu_sinirli_kalir() -> None:
    sinir = HizSiniri(kapasite=1, dolum_hizi=1, en_cok_adres=3, saat=_Saat())
    for i in range(10):
        sinir.izin_ver(f"10.0.0.{i}")

    assert sinir.adres_sayisi == 3


@pytest.mark.parametrize("degerler", [{"kapasite": 0}, {"dolum_hizi": 0}, {"en_cok_adres": 0}])
def test_gecersiz_hiz_siniri_reddedilir(degerler: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        HizSiniri(**degerler)  # type: ignore[arg-type]


def test_uygulama_429_ve_turkce_sayfa_doner_x_forwarded_for_okunmaz() -> None:
    uygulama = create_app(
        None,
        bakim_kapisi=BakimKapisi(),
        hiz_siniri=HizSiniri(kapasite=2, dolum_hizi=0.01, saat=_Saat()),
    )
    ortam = ortam_kur("/saglik", istemci="10.1.1.1")

    assert cagir(uygulama, dict(ortam)).code == 200
    assert cagir(uygulama, dict(ortam)).code == 200
    # Başlıkla "başka biri" olmaya çalışmak sınırı aşmaz.
    sahte = dict(ortam, HTTP_X_FORWARDED_FOR="10.9.9.9", HTTP_X_REAL_IP="10.9.9.9")
    yanit = cagir(uygulama, sahte)

    assert yanit.code == 429
    assert "Çok sık istek gönderildi" in yanit.text
    assert int(yanit.header("Retry-After") or "0") >= 1
    assert uygulama.sayaclar.gun()["hiz_siniri"] == 1
    # Başka bir istemci adresi etkilenmez.
    assert cagir(uygulama, ortam_kur("/saglik", istemci="10.1.1.2")).code == 200


def test_hiz_siniri_varsayilanlari_ogrenci_gezinmesini_bogmaz() -> None:
    """Bir sayfa + stil = iki istek; bir dakikada 30 sayfa gezen öğrenci takılmaz."""
    saat = _Saat()
    sinir = HizSiniri(saat=saat)
    for _ in range(30):
        assert sinir.izin_ver("10.0.0.5")[0]
        assert sinir.izin_ver("10.0.0.5")[0]
        saat.an += 2.0


# ================================================================= bakım kapısı


def test_bakim_kapisi_giris_cikis_sayar() -> None:
    kapi = BakimKapisi()
    with kapi.is_() as izin:
        assert izin is True
        assert kapi.ucusta == 1
    assert kapi.ucusta == 0


def test_bakimdayken_is_baslamaz_ve_sayac_degismez() -> None:
    kapi = BakimKapisi()
    assert kapi.bakima_al(bekleme_sn=0.01) is True
    with kapi.is_() as izin:
        assert izin is False
        assert kapi.ucusta == 0
    assert kapi.bakimda
    kapi.bakimdan_cik()
    assert kapi.gir() is True
    kapi.cik()


def test_bakim_ucustaki_isi_bekler_ve_sure_dolunca_kapali_kalir() -> None:
    kapi = BakimKapisi()
    kapi.gir()
    assert kapi.bakima_al(bekleme_sn=0.01) is False
    assert kapi.bakimda  # süre dolsa da kapı kapalı kalır

    bitti = threading.Event()

    def bekle() -> None:
        assert kapi.bakima_al(bekleme_sn=5)
        bitti.set()

    is_parcacigi = threading.Thread(target=bekle, daemon=True)
    is_parcacigi.start()
    kapi.cik()
    is_parcacigi.join(5)
    assert bitti.is_set()


def test_girissiz_cikis_hata_verir() -> None:
    with pytest.raises(RuntimeError):
        BakimKapisi().cik()


def test_surec_ici_kapi_tektir() -> None:
    from katalog import bakim

    assert bakim.KAPI is KAPI
    assert isinstance(KAPI, BakimKapisi)


# ================================================================ istek çözümü


@pytest.mark.parametrize("metin", ["şiir", "İnce Memed", "a&b=c", "100% doğru", "ç/ğ?#"])
def test_yuzde_kodlama_gidis_donus(metin: str) -> None:
    kodlu = yuzde_kodla(metin)

    assert kodlu.isascii()
    assert yuzde_coz(kodlu.encode("ascii"), arti_bosluktur=True) == metin


def test_yol_kodlamasi_egik_cizgiyi_korur() -> None:
    assert yuzde_kodla("/eserler/Ç", guvenli="/") == "/eserler/%C3%87"


@pytest.mark.parametrize("ham", [b"%", b"%G1", b"%C3", b"a%0Ab", b"%7F"])
def test_bozuk_yuzde_kodlamasi_reddedilir(ham: bytes) -> None:
    with pytest.raises(GecersizIstek):
        yuzde_coz(ham, arti_bosluktur=True)


def test_sorgu_dizesi_ilk_deger_gecerli_arti_bosluktur() -> None:
    assert sorgu_dizesini_coz("q=kurk+mantolu&q=baska&&tur=kitap&=x&bos") == {
        "q": "kurk mantolu",
        "tur": "kitap",
        "bos": "",
    }


def test_sorgu_dizesi_uzunluk_siniri() -> None:
    assert sorgu_dizesini_coz("q=" + "a" * (EN_UZUN_SORGU_DIZESI - 2))
    with pytest.raises(AdresCokUzun):
        sorgu_dizesini_coz("q=" + "a" * EN_UZUN_SORGU_DIZESI)


def test_yol_utf8_olarak_cozulur() -> None:
    assert yolu_coz("/eserler/Ç".encode().decode("latin-1")) == "/eserler/Ç"
    assert yolu_coz("") == "/"
    with pytest.raises(GecersizIstek):
        yolu_coz("/\xff")
    with pytest.raises(GecersizIstek):
        yolu_coz("/a\x00b")


def test_baglanti_tahta_kipini_korur_ve_bos_parametreyi_yazmaz() -> None:
    duz = Istek("/", {})
    tahta = Istek("/", {"tahta": "1"})

    assert duz.bag("/ara", q="şiir", tur=None, sayfa="") == "/ara?q=%C5%9Fiir"
    assert tahta.bag("/eser/5") == "/eser/5?tahta=1"
    assert tahta.bag("/ara", q="a b") == "/ara?q=a%20b&tahta=1"
    assert Istek("/", {"tahta": "0"}).tahta is False


@pytest.mark.parametrize("yol", ["http://baska", "//baska.sunucu/", "ara"])
def test_baglanti_yalniz_koke_goreli_olabilir(yol: str) -> None:
    with pytest.raises(ValueError):
        Istek("/", {}).bag(yol)


# =================================================================== sayaçlar


def test_sayaclar_gun_basina_tutulur_ve_eski_gunler_duser() -> None:
    gun = [date(2026, 9, 1)]
    sayaclar = GunlukSayaclar(bugun=lambda: gun[0])
    sayaclar.say("sayfa")
    sayaclar.say("sayfa")
    sayaclar.say("arama")

    assert sayaclar.gun()["sayfa"] == 2
    assert set(sayaclar.gun()) == set(OLAYLAR)
    for i in range(1, SAKLANAN_GUN + 3):
        gun[0] = date(2026, 9, 1) + timedelta(days=i)
        sayaclar.say("sayfa")

    ozet = sayaclar.ozet()
    assert len(ozet) == SAKLANAN_GUN
    assert "2026-09-01" not in ozet
    assert sayaclar.gun(date(2026, 9, 1))["sayfa"] == 0


def test_bilinmeyen_sayac_reddedilir() -> None:
    with pytest.raises(ValueError):
        GunlukSayaclar(bugun=lambda: date(2026, 9, 1)).say("ip_adresi")


def test_son_hata_zaman_ve_sabit_iletidir() -> None:
    an = datetime(2026, 9, 24, 10, 0).astimezone()
    sayaclar = GunlukSayaclar(bugun=lambda: date(2026, 9, 24), simdi=lambda: an)
    assert sayaclar.son_hata is None

    sayaclar.hata_kaydet("Ağ Kataloğu veritabanına ulaşamadı.")

    assert sayaclar.son_hata is not None
    assert sayaclar.son_hata.zaman == an
    assert sayaclar.son_hata.ileti == "Ağ Kataloğu veritabanına ulaşamadı."


def test_varsayilan_gun_yerel_gundur() -> None:
    from django.utils import timezone

    sayaclar = GunlukSayaclar()
    sayaclar.say("sayfa")

    assert sayaclar.ozet() == {
        timezone.localdate().isoformat(): {olay: int(olay == "sayfa") for olay in OLAYLAR}
    }
