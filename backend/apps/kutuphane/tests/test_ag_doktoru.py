"""Ağ Doktoru uçları (F5-D, tasarım §5.9, T16).

Katalog denetçisi masaüstündedir; burada `SahteDenetci` masaüstü kancasına
kaydedilir (`apps.okul.masaustu_kanca.kaydet`) ve uçların onu doğru çağırdığı,
denetçi yokken 503 `masaustu_yok` döndüğü, port değişikliğinin Windows'ta UAC
adımından geçmeden YAZILMADIĞI ve bütün uçların yalnız yönetici kipinde açık
olduğu sınanır.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps as django_apps
from django.urls import reverse
from rest_framework.test import APIClient

from apps.kutuphane.models import DinlemeKipi, KatalogAyari
from apps.kutuphane.services import ag_doktoru, populer
from apps.kutuphane.services import katalog_ayari as ayar_servisi
from apps.okul import masaustu_kanca
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import IZIN_LISTESI
from katalog import app as katalog_app
from katalog.sayac import OLAYLAR

pytestmark = pytest.mark.django_db

KOK = "/api/v1/library/network-catalog/"

#: Bu kolun eklediği uçlar (ad, yöntem, yol).
UCLAR: tuple[tuple[str, str, str], ...] = (
    ("library-network-catalog-status", "get", "status/"),
    ("library-network-catalog-control", "post", "control/"),
    ("library-network-catalog-firewall", "get", "firewall/"),
    ("library-network-catalog-firewall-rule", "post", "firewall-rule/"),
    ("library-network-catalog-interfaces", "get", "interfaces/"),
    ("library-network-catalog-listener-test", "post", "listener-test/"),
    ("library-network-catalog-port", "post", "port/"),
    ("library-network-catalog-poster", "post", "poster/"),
    ("library-network-catalog-info-note", "get", "info-note/"),
    ("library-network-catalog-bookmarks", "get", "bookmarks/"),
    ("library-network-catalog-pys-text", "get", "pys-text/"),
)

ADAY_1 = "10.20.30.40"
ADAY_2 = "10.99.0.7"


class SahteDenetci:
    """`KatalogKontrolu` sözleşmesinin taklidi; çağrıları kaydeder."""

    def __init__(self) -> None:
        self.cagrilar: list[tuple[str, dict[str, Any]]] = []
        self.durum_adi = "kapali"
        self.kural_sonucu: tuple[bool, str] = (True, "Güvenlik duvarı kuralı güncellendi.")

    def _kaydet(self, ad: str, **kw: Any) -> None:
        self.cagrilar.append((ad, kw))

    def durum(self) -> dict[str, Any]:
        acik = self.durum_adi == "acik"
        return {
            "durum": self.durum_adi,
            "ayar_acik": acik,
            "dinleme_kipi": "ALL",
            "tum_arayuzler": acik,
            "dinleme_ip": None,
            "port": 8765,
            "adres": f"http://{ADAY_1}:8765/" if acik else None,
            "guncel_ip": ADAY_1,
            "son_afis_ip": None,
            "ip_degisti": False,
            "son_hata": None,
            "uyarilar": [],
            "guvenlik_duvari": None,
            "reddedilen_baglanti": 0,
            "uyku_engelli": acik,
        }

    def ac(self) -> dict[str, Any]:
        self._kaydet("ac")
        self.durum_adi = "acik"
        return self.durum()

    def kapat(self) -> dict[str, Any]:
        self._kaydet("kapat")
        self.durum_adi = "kapali"
        return self.durum()

    def yeniden_baslat(self) -> dict[str, Any]:
        self._kaydet("yeniden_baslat")
        return self.durum()

    def guvenlik_duvari(self) -> dict[str, Any]:
        self._kaydet("guvenlik_duvari")
        return {"platform": "windows", "dinlemeye_izin": True, "maddeler": [], "kural": None}

    def ip_adaylari(self) -> dict[str, Any]:
        self._kaydet("ip_adaylari")
        return {
            "arayuzler": [
                {"ad": "Ethernet", "ip": ADAY_1, "onek": 24, "varsayilan_rota": True},
                {"ad": "Ethernet 2", "ip": ADAY_2, "onek": 24, "varsayilan_rota": False},
            ],
            "varsayilan_ip": ADAY_1,
            "yonlendirme_acik": False,
            "uyarilar": [],
            "kaynak": "sahte",
        }

    def dinleyici_sinamasi(self) -> dict[str, Any]:
        self._kaydet("dinleyici_sinamasi")
        return {
            "acik": True,
            "port": 8765,
            "sonuclar": [
                {
                    "ip": ADAY_1,
                    "ad": "Ethernet",
                    "ayakta": True,
                    "komut": f"Test-NetConnection {ADAY_1} -Port 8765",
                }
            ],
            "uyari": "Bu sınama güvenlik duvarını ya da VLAN'ı kanıtlamaz.",
        }

    def kural_guncelle(self, *, port: int, uzak_adresler: list[str]) -> dict[str, Any]:
        self._kaydet("kural_guncelle", port=port, uzak_adresler=list(uzak_adresler))
        tamam, ileti = self.kural_sonucu
        return {"tamam": tamam, "ileti": ileti, "durum": self.durum()}

    def bakima_al(self) -> None:
        self._kaydet("bakima_al")

    def bakimdan_cik(self) -> None:
        self._kaydet("bakimdan_cik")


@pytest.fixture
def denetci() -> Iterator[SahteDenetci]:
    sahte = SahteDenetci()
    masaustu_kanca.kaydet(katalog=sahte)
    yield sahte
    masaustu_kanca.kaldir()


@pytest.fixture(autouse=True)
def _kanca_temiz() -> Iterator[None]:
    masaustu_kanca.kaldir()
    yield
    masaustu_kanca.kaldir()


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ag_doktoru, "windows_mu", lambda: True)


@pytest.fixture
def linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ag_doktoru, "windows_mu", lambda: False)


# ====================================================================== durum


def test_masaustu_yokken_durum_okunur_eylem_503_doner() -> None:
    istemci = APIClient()

    durum = istemci.get(KOK + "status/")
    assert durum.status_code == 200
    govde = durum.json()
    assert govde["masaustu"] is False
    assert govde["katalog"] is None and govde["qr"] is None
    assert set(govde["sayaclar"]["bugun"]) == set(OLAYLAR)

    for yol, veri in (("control/", {"eylem": "ac"}), ("firewall-rule/", {})):
        yanit = istemci.post(KOK + yol, veri, format="json")
        assert yanit.status_code == 503
        assert yanit.json()["code"] == "masaustu_yok"
        assert "masaüstü programında" in yanit.json()["message"]
    for yol in ("firewall/", "interfaces/"):
        assert istemci.get(KOK + yol).status_code == 503


def test_durum_denetciyi_sayaclari_ve_qr_kodunu_tasir(denetci: SahteDenetci) -> None:
    denetci.durum_adi = "acik"
    sayaclar = katalog_app.application.sayaclar
    once = sayaclar.gun()["arama"]
    sayaclar.say("arama")
    sayaclar.hata_kaydet("Veritabanı açılamadı.")

    govde = APIClient().get(KOK + "status/").json()

    assert set(govde) == {"masaustu", "platform", "katalog", "qr", "sayaclar"}
    assert govde["masaustu"] is True
    assert govde["platform"] in {"windows", "linux", "diger"}
    assert govde["katalog"]["adres"] == f"http://{ADAY_1}:8765/"
    assert govde["sayaclar"]["bugun"]["arama"] == once + 1
    assert govde["sayaclar"]["son_hata"]["ileti"] == "Veritabanı açılamadı."
    # QR kare bir matristir ve adresin kendisini kodlar (çözümlemeyi segno sınar).
    qr = govde["qr"]
    assert len(qr) >= 21 and all(len(satir) == len(qr) for satir in qr)
    assert set("".join(qr)) <= {"0", "1"}


def test_kapaliyken_qr_yok(denetci: SahteDenetci) -> None:
    assert APIClient().get(KOK + "status/").json()["qr"] is None


# ===================================================================== eylemler


@pytest.mark.parametrize("eylem", ["ac", "kapat", "yeniden_baslat"])
def test_eylem_denetciye_gider(denetci: SahteDenetci, eylem: str) -> None:
    yanit = APIClient().post(KOK + "control/", {"eylem": eylem}, format="json")

    assert yanit.status_code == 200
    assert [ad for ad, _ in denetci.cagrilar] == [eylem]
    assert yanit.json()["katalog"]["durum"] == denetci.durum_adi


def test_bilinmeyen_eylem_400(denetci: SahteDenetci) -> None:
    yanit = APIClient().post(KOK + "control/", {"eylem": "sil"}, format="json")

    assert yanit.status_code == 400
    assert denetci.cagrilar == []


def test_denetim_adaylar_ve_oz_sinama(denetci: SahteDenetci) -> None:
    istemci = APIClient()

    assert istemci.get(KOK + "firewall/").json()["platform"] == "windows"
    assert istemci.get(KOK + "interfaces/").json()["varsayilan_ip"] == ADAY_1
    sinama = istemci.post(KOK + "listener-test/").json()
    assert "kanıtlamaz" in sinama["uyari"]
    assert sinama["sonuclar"][0]["komut"] == f"Test-NetConnection {ADAY_1} -Port 8765"


def test_kural_guncelleme_kayitli_port_ve_tahta_bloklariyla(denetci: SahteDenetci) -> None:
    ayar_servisi.update_katalog_ayari(port=9100, tahta_cidrleri=["10.50.0.0/24"])

    govde = APIClient().post(KOK + "firewall-rule/").json()

    assert govde["tamam"] is True
    assert denetci.cagrilar[-1] == (
        "kural_guncelle",
        {"port": 9100, "uzak_adresler": ["10.50.0.0/24"]},
    )
    assert govde["durum"]["masaustu"] is True


# ========================================================================= port


def test_linuxta_port_dogrudan_yazilir_ve_katalog_yeniden_kurulur(
    denetci: SahteDenetci, linux: None
) -> None:
    yanit = APIClient().post(KOK + "port/", {"port": 9200}, format="json")

    assert yanit.status_code == 200, yanit.json()
    assert ayar_servisi.katalog_ayari().port == 9200
    assert [ad for ad, _ in denetci.cagrilar] == ["yeniden_baslat"]


def test_windowsta_port_once_uac_ile_kural_sonra_ayar(denetci: SahteDenetci, windows: None) -> None:
    yanit = APIClient().post(KOK + "port/", {"port": 9300}, format="json")

    assert yanit.status_code == 200, yanit.json()
    assert "güvenlik duvarı kuralı" in yanit.json()["ileti"]
    assert denetci.cagrilar[0] == ("kural_guncelle", {"port": 9300, "uzak_adresler": []})
    assert ayar_servisi.katalog_ayari().port == 9300


def test_windowsta_uac_reddedilirse_port_degismez(denetci: SahteDenetci, windows: None) -> None:
    denetci.kural_sonucu = (False, "Yönetici izni verilmedi; kural değiştirilmedi.")

    yanit = APIClient().post(KOK + "port/", {"port": 9400}, format="json")

    assert yanit.status_code == 409
    assert yanit.json()["code"] == "kural_yazilamadi"
    assert "Port değiştirilmedi" in yanit.json()["message"]
    assert ayar_servisi.katalog_ayari().port == 8765


def test_windowsta_masaustu_yokken_port_503(windows: None) -> None:
    yanit = APIClient().post(KOK + "port/", {"port": 9500}, format="json")

    assert yanit.status_code == 503
    assert not KatalogAyari.objects.exists()


def test_port_araligi_dogrulanir(denetci: SahteDenetci, linux: None) -> None:
    yanit = APIClient().post(KOK + "port/", {"port": 80}, format="json")

    assert yanit.status_code == 400
    assert "port" in yanit.json()["fields"]


def test_ayar_ucu_windowsta_portu_degistirmez(windows: None) -> None:
    uc = KOK + "settings/"
    istemci = APIClient()

    ret = istemci.put(uc, {"port": 9600}, format="json")
    assert ret.status_code == 400
    assert "Portu değiştir" in ret.json()["fields"]["port"][0]

    ayni = istemci.put(uc, {"port": 8765, "vitrin_acik": False}, format="json")
    assert ayni.status_code == 200
    assert ayni.json()["vitrin_acik"] is False


# ======================================================================== adres


def test_yayin_adresi_katalogun_adresidir(denetci: SahteDenetci) -> None:
    assert ag_doktoru.yayin_ip() == ADAY_1


def test_istenen_adres_aday_degilse_reddedilir(denetci: SahteDenetci) -> None:
    yanit = APIClient().get(KOK + "pys-text/", {"ip": "10.1.1.1"})

    assert yanit.status_code == 400
    assert "ip" in yanit.json()["fields"]
    assert APIClient().get(KOK + "pys-text/", {"ip": ADAY_2}).status_code == 200


def test_masaustu_yokken_adres_ayardan_yoksa_409() -> None:
    yanit = APIClient().get(KOK + "bookmarks/")
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "adres_yok"

    ayar_servisi.update_katalog_ayari(dinleme_kipi=DinlemeKipi.SELECTED, secili_ip="10.7.7.7")
    assert ag_doktoru.yayin_ip() == "10.7.7.7"


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.1.1", "abc", "0.0.0.0"])  # noqa: S104
def test_gecersiz_istenen_adres(ip: str) -> None:
    yanit = APIClient().get(KOK + "pys-text/", {"ip": ip})

    assert yanit.status_code == 400


# ==================================================================== kip kapısı


def test_uclar_gorevli_kipinde_403_ve_izin_listesinde_degil() -> None:
    izinli = {kural.uc for kural in IZIN_LISTESI}
    KIP.gorevliye_gec()
    istemci = APIClient()

    for ad, yontem, yol in UCLAR:
        assert reverse(ad) == KOK + yol
        assert ad not in izinli
        yanit = getattr(istemci, yontem)(KOK + yol, {}, format="json")
        assert yanit.status_code == 403, ad
        assert yanit.json()["code"] == "kip_yetkisiz"


def test_kilitliyken_uclar_423(kilitli: object) -> None:
    for _ad, yontem, yol in UCLAR:
        yanit = getattr(APIClient(), yontem)(KOK + yol, {}, format="json")
        assert yanit.status_code == 423, yol


# ==================================================== gün değişimi kapısı (T9)


def test_cok_okunanlar_gun_degisimi_kapisina_kayitlidir() -> None:
    django_apps.get_app_config("kutuphane").ready()

    kayitlar = {is_.ad: is_ for is_ in masaustu_kanca.gunluk_isler()}
    assert populer.GUNLUK_IS_ADI in kayitlar
    assert kayitlar[populer.GUNLUK_IS_ADI].calistir() is True


def test_kapi_isi_bakimda_yeniden_denenir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(populer, "gunluk_is", lambda _gun: "bakimda")

    assert populer.kapi_isi() is False
