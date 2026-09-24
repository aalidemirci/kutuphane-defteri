"""Ağ Kataloğu denetçisi (T16) — ayar, güvenlik duvarı, dinleme, bakım, IP ve uyku.

§5.10-10: güvenlik duvarı kuralı yoksa ya da tutmuyorsa katalog okul ağında
DİNLEMEZ. Denetim çıktısı TAKLİT edilir (PowerShell JSON'u, `guvenlik_duvari.
degerlendir`) ve sonucun gerçek bir sokete yansıdığı sınanır: kural tutmazsa
port hiç açılmaz; tutarsa gerçek waitress tüm arayüzlerde dinler ve öz
sınamadan geçer. Kod kapısının "geri yüklemede katalog durur ve yeniden
açılışta kalkar" maddesi de buradadır.

Docker kabında tüm arayüz dinleyicisi gerçekten açılır; seçili IP dalı kabın
kendi adresiyle (varsa) sınanır. Adresler testte uydurmadır (TB25).
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from desktop import ag
from desktop import guvenlik_duvari as gd
from desktop import katalog_kontrol as kk
from desktop.katalog_server import (
    DINLEME_SECILI,
    DINLEME_TUM,
    CatalogApp,
    KatalogServer,
    load_catalog,
)
from desktop.server import find_free_port

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
EXE = r"C:\Program Files\Kütüphane Defteri\kutuphane-defteri.exe"
IMZA = b'<meta name="kd-katalog" content="1">'
AFIS_IP = "192.168.10.5"
TAHTA_IP = "10.20.30.40"


def _kural(port: int, **degisiklik: Any) -> dict[str, Any]:
    kural: dict[str, Any] = {
        "ad": gd.KURAL_ADI,
        "etkin": True,
        "eylem": "Allow",
        "yon": "Inbound",
        "profil": "Any",
        "program": EXE,
        "protokol": "TCP",
        "yerel_port": [str(port)],
        "uzak_adres": ["LocalSubnet"],
    }
    kural.update(degisiklik)
    return kural


class _Ayar:
    """Değiştirilebilir ayar kaynağı (`KatalogAyari` yerine)."""

    def __init__(self, **alanlar: Any) -> None:
        self.deger = kk.yapilandirma(**alanlar)
        self.yazilan: list[dict[str, Any]] = []
        self.yazma_hatasi: Exception | None = None

    def oku(self) -> kk.KatalogYapilandirmasi:
        return self.deger

    def yaz(self, **alanlar: Any) -> None:
        if self.yazma_hatasi is not None:
            raise self.yazma_hatasi
        self.yazilan.append(alanlar)
        self.deger = kk.yapilandirma(**{**self.deger.__dict__, **alanlar})


class _Kapi:
    """Ortak bakım kapısı taklidi (`katalog.bakim.KAPI`)."""

    def __init__(self) -> None:
        self.cagrilar: list[str] = []

    def bakima_al(self, *, bekleme_sn: float = 10.0) -> bool:
        self.cagrilar.append("bakima_al")
        return True

    def bakimdan_cik(self) -> None:
        self.cagrilar.append("bakimdan_cik")


def _ag(*ipler: str, varsayilan: str | None = None) -> ag.AgDurumu:
    varsayilan = varsayilan if varsayilan is not None else (ipler[0] if ipler else None)
    return ag.AgDurumu(
        arayuzler=tuple(
            ag.Arayuz(ad=f"ag{i}", ip=ip, onek=24, varsayilan_rota=ip == varsayilan)
            for i, ip in enumerate(ipler)
        ),
        kaynak="test",
    )


@pytest.fixture
def katalog(monkeypatch: pytest.MonkeyPatch) -> CatalogApp:
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    return load_catalog()


@pytest.fixture
def kurulan() -> Iterator[list[KatalogServer]]:
    """Denetçinin kurduğu sunucular; test sonunda hepsi kapatılır."""
    liste: list[KatalogServer] = []
    yield liste
    for sunucu in liste:
        sunucu.stop()


def _kontrol(
    ayar: _Ayar,
    katalog: CatalogApp,
    kurulan: list[KatalogServer],
    *,
    platform: str = "win32",
    duvar_verisi: Callable[[int], dict[str, Any]] | None = None,
    ag_durumu: Callable[[], ag.AgDurumu] | None = None,
    kapi: _Kapi | None = None,
    **kw: Any,
) -> kk.KatalogKontrol:
    def kurucu(*args: Any, **kwargs: Any) -> KatalogServer:
        sunucu = KatalogServer(*args, **kwargs)
        kurulan.append(sunucu)
        return sunucu

    def duvar(*, port: int, exe_yolu: str) -> gd.GuvenlikDuvariDenetimi:
        if platform != "win32":
            return gd.GuvenlikDuvariDenetimi(platform="linux")
        veri = (duvar_verisi or (lambda p: {"kurallar": [_kural(p)], "ag_profilleri": ["Public"]}))(
            port
        )
        return gd.degerlendir(veri, exe_yolu=exe_yolu, port=port)

    return kk.KatalogKontrol(
        ayar_okuyucu=ayar.oku,
        ayar_yazici=ayar.yaz,
        yukleyici=lambda: katalog,
        ag_saglayici=ag_durumu or (lambda: _ag(AFIS_IP)),
        duvar_denetleyici=duvar,
        sunucu_kurucu=kurucu,
        bakim_kapisi=kapi or _Kapi(),
        platform=platform,
        exe_yolu=EXE,
        **kw,
    )


def _baglanilabilir(port: int, host: str = "127.0.0.1") -> bool:
    try:
        socket.create_connection((host, port), timeout=1.0).close()
    except OSError:
        return False
    return True


def _govde(port: int, host: str = "127.0.0.1") -> bytes:
    with urllib.request.urlopen(f"http://{host}:{port}/", timeout=5) as yanit:  # noqa: S310
        return bytes(yanit.read())


# --------------------------------------------------------- ayar kapalı


def test_ayar_kapaliyken_hic_dinlemez(katalog: CatalogApp, kurulan: list[KatalogServer]) -> None:
    kontrol = _kontrol(_Ayar(acik=False), katalog, kurulan)

    kontrol.acilista_baslat()

    assert kontrol.durum()["durum"] == kk.KAPALI
    assert kurulan == []
    assert kontrol.tepsi_satiri() == "Ağ Kataloğu: kapalı"


# ------------------------------------------------------------ §5.10-10


@pytest.mark.parametrize(
    "duvar_verisi",
    [
        pytest.param(lambda p: {"kurallar": [], "ag_profilleri": ["Public"]}, id="kural-yok"),
        pytest.param(
            lambda p: {"kurallar": [_kural(p, etkin=False)], "ag_profilleri": ["Public"]},
            id="kural-devre-disi",
        ),
        pytest.param(
            lambda p: {"kurallar": [_kural(p, program=r"D:\x.exe")], "ag_profilleri": ["Public"]},
            id="program-farkli",
        ),
        pytest.param(
            lambda p: {"kurallar": [_kural(p + 1)], "ag_profilleri": ["Public"]},
            id="port-farkli",
        ),
        pytest.param(
            lambda p: {"kurallar": [_kural(p, profil="Private")], "ag_profilleri": ["Public"]},
            id="profil-kapsamiyor",
        ),
        pytest.param(
            lambda p: {
                "kurallar": [_kural(p), _kural(p, ad="engel", eylem="Block")],
                "ag_profilleri": ["Public"],
            },
            id="engelleme-kurali",
        ),
        pytest.param(lambda p: "netsh ciktisi", id="okunamadi"),
    ],
)
def test_guvenlik_duvari_tutmazsa_okul_aginda_dinlemez(
    duvar_verisi: Callable[[int], Any], katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """§5.10-10: denetim çıktısı taklit edilir; port HİÇ açılmaz."""
    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan, duvar_verisi=duvar_verisi)

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.ENGELLENDI
    assert "güvenlik duvarı denetimi geçmedi" in durum["son_hata"]
    assert durum["guvenlik_duvari"]["dinlemeye_izin"] is False
    assert durum["adres"] is None
    assert kurulan == []  # sunucu hiç kurulmadı
    assert not _baglanilabilir(port)
    assert not _baglanilabilir(port, host=ag.yedek_varsayilan_ip() or "127.0.0.1")
    assert kontrol.tepsi_satiri() == "Ağ Kataloğu: güvenlik duvarı izni yok"
    assert kontrol.uyku_gerekli() is False


def test_guvenlik_duvari_gecince_tum_arayuzlerde_dinler_ve_oz_sinamadan_gecer(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan)

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.ACIK, durum
    assert durum["tum_arayuzler"] is True
    assert durum["adres"] == f"http://{AFIS_IP}:{port}/"
    assert durum["son_hata"] is None
    (sunucu,) = kurulan
    assert sunucu.tum_arayuzler is True
    assert IMZA in _govde(port)
    kabin_ip = ag.yedek_varsayilan_ip()
    if kabin_ip:  # tüm arayüzlerde: kabın kendi adresinden de ulaşılır
        assert IMZA in _govde(port, host=kabin_ip)
    assert kontrol.tepsi_satiri() == f"Ağ Kataloğu: açık — http://{AFIS_IP}:{port}/"

    kontrol.kapanis()
    assert not _baglanilabilir(port)


def test_linuxta_denetim_bilgidir_ve_dinlemeyi_engellemez(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan, platform="linux")

    kontrol.acilista_baslat()

    assert kontrol.durum()["durum"] == kk.ACIK
    kontrol.kapanis()


def test_durum_yonetim_portunu_ve_kisisel_veriyi_icermez(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan)
    kontrol.acilista_baslat()

    durum = kontrol.durum()

    assert set(durum) == {
        "durum",
        "ayar_acik",
        "dinleme_kipi",
        "tum_arayuzler",
        "dinleme_ip",
        "port",
        "adres",
        "guncel_ip",
        "son_afis_ip",
        "ip_degisti",
        "son_hata",
        "uyarilar",
        "guvenlik_duvari",
        "reddedilen_baglanti",
        "uyku_engelli",
    }
    kontrol.kapanis()


# ------------------------------------------------------------ seçili IP


@pytest.fixture
def kabin_ip() -> str:
    ip = ag.yedek_varsayilan_ip()
    if ip is None:
        pytest.skip("kapta varsayılan rota yok")
    return ip


def test_secili_ipde_yalniz_o_adreste_dinler(
    katalog: CatalogApp, kurulan: list[KatalogServer], kabin_ip: str
) -> None:
    port = find_free_port()
    kontrol = _kontrol(
        _Ayar(acik=True, port=port, dinleme_kipi=DINLEME_SECILI, secili_ip=kabin_ip),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(kabin_ip, TAHTA_IP),
    )

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.ACIK, durum
    assert durum["dinleme_ip"] == kabin_ip
    assert durum["adres"] == f"http://{kabin_ip}:{port}/"
    assert IMZA in _govde(port, host=kabin_ip)
    assert not _baglanilabilir(port)  # loopback'te dinlemiyor
    kontrol.kapanis()


def test_secili_ip_kaybolduysa_tek_aday_varsa_yeni_adreste_acilir_ve_uyarir(
    katalog: CatalogApp, kurulan: list[KatalogServer], kabin_ip: str
) -> None:
    port = find_free_port()
    kontrol = _kontrol(
        _Ayar(acik=True, port=port, dinleme_kipi=DINLEME_SECILI, secili_ip="192.168.77.7"),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(kabin_ip),
    )

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.ACIK
    assert durum["dinleme_ip"] == kabin_ip
    assert any("artık yok" in u and "Afişi yeniden basın" in u for u in durum["uyarilar"])
    kontrol.kapanis()


def test_secili_ip_kaybolduysa_birden_cok_aday_varken_acilmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Hangi ağın istendiği bilinemez: öğrenci erişimli ağa sessizce açılmasın."""
    kontrol = _kontrol(
        _Ayar(
            acik=True, port=find_free_port(), dinleme_kipi=DINLEME_SECILI, secili_ip="192.168.77.7"
        ),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(AFIS_IP, TAHTA_IP),
    )

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.HATA
    assert "seçili IP adresi bu bilgisayarda artık yok" in durum["son_hata"]
    assert kurulan == []


def test_secili_ip_bu_bilgisayarda_baglanamiyorsa_hata(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Ağ listesinde görünen ama bağlanılamayan adres: soket hatası Türkçe iletiyle."""
    kontrol = _kontrol(
        _Ayar(
            acik=True, port=find_free_port(), dinleme_kipi=DINLEME_SECILI, secili_ip="192.0.2.77"
        ),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag("192.0.2.77", TAHTA_IP),
    )

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.HATA
    assert "artık yok" in durum["son_hata"]


# --------------------------------------------------------------- port dolu


def test_port_doluysa_bekler_ve_bosalinca_kendiliginden_acilir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    dolu = socket.socket()
    dolu.bind(("0.0.0.0", 0))  # noqa: S104 — portu dolu göstermek için
    dolu.listen(1)
    port = dolu.getsockname()[1]
    kontrol = _kontrol(
        _Ayar(acik=True, port=port), katalog, kurulan, yeniden_deneme_araligi_sn=0.05
    )

    kontrol.acilista_baslat()
    assert kontrol.durum()["durum"] == kk.BEKLIYOR
    assert "kullanılıyor" in kontrol.durum()["son_hata"]
    assert kontrol.tepsi_satiri() == "Ağ Kataloğu: port bekleniyor"

    dolu.close()
    son = time.monotonic() + 10
    while kontrol.durum()["durum"] != kk.ACIK and time.monotonic() < son:
        time.sleep(0.05)

    assert kontrol.durum()["durum"] == kk.ACIK
    kontrol.kapanis()


def test_port_bekleme_suresi_dolunca_hataya_duser(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    dolu = socket.socket()
    dolu.bind(("0.0.0.0", 0))  # noqa: S104
    dolu.listen(1)
    saat = [0.0]
    try:
        kontrol = _kontrol(
            _Ayar(acik=True, port=dolu.getsockname()[1]),
            katalog,
            kurulan,
            yeniden_deneme_araligi_sn=60.0,
            yeniden_deneme_suresi_sn=100.0,
            saat=lambda: saat[0],
        )
        kontrol.acilista_baslat()
        assert kontrol.durum()["durum"] == kk.BEKLIYOR
        saat[0] = 101.0
        kontrol._yeniden_dene()  # zamanlayıcının yapacağı deneme, süre dolmuşken
        assert kontrol.durum()["durum"] == kk.HATA
        kontrol.kapanis()
    finally:
        dolu.close()


# ------------------------------------------------------ aç / kapat / ayar


def test_ac_ve_kapat_ayari_yazar(katalog: CatalogApp, kurulan: list[KatalogServer]) -> None:
    ayar = _Ayar(acik=False, port=find_free_port())
    kontrol = _kontrol(ayar, katalog, kurulan)

    assert kontrol.ac()["durum"] == kk.ACIK
    assert kontrol.acik_mi() is True
    assert kontrol.kapat()["durum"] == kk.KAPALI
    assert ayar.yazilan == [{"acik": True}, {"acik": False}]
    assert kontrol.acik_mi() is False


def test_ayar_yazilamazsa_katalog_acilmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Görevli kipinde servis yazmayı reddeder (`AyarYetkisiz`): tepsi eski menüden de açamaz."""
    ayar = _Ayar(acik=False, port=find_free_port())
    ayar.yazma_hatasi = PermissionError(
        "Ağ Kataloğu ayarları yalnız yönetici kipinde değiştirilir."
    )
    kontrol = _kontrol(ayar, katalog, kurulan)

    durum = kontrol.ac()

    assert durum["durum"] == kk.KAPALI
    assert durum["son_hata"] == "Ağ Kataloğu ayarı kaydedilemedi."
    assert kurulan == []


def test_kapat_ayar_yazilamazsa_katalogu_acik_birakir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    ayar = _Ayar(acik=True, port=port)
    kontrol = _kontrol(ayar, katalog, kurulan)
    kontrol.acilista_baslat()
    ayar.yazma_hatasi = PermissionError("yalnız yönetici kipinde")

    durum = kontrol.kapat()

    assert durum["durum"] == kk.ACIK
    assert durum["son_hata"] == "Ağ Kataloğu ayarı kaydedilemedi."
    assert _baglanilabilir(port)
    kontrol.kapanis()


def test_ayar_degisince_port_degistiyse_yeniden_kurulur_uyku_degistiyse_kurulmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    ilk, ikinci = find_free_port(), find_free_port()
    ayar = _Ayar(acik=True, port=ilk)
    kontrol = _kontrol(ayar, katalog, kurulan)
    kontrol.acilista_baslat()

    ayar.deger = kk.yapilandirma(**{**ayar.deger.__dict__, "uyku_engelleme": False})
    kontrol._ayar_degisti()
    assert len(kurulan) == 1  # yalnız uyku değişti: dinleyici aynı
    assert kontrol.uyku_gerekli() is False

    ayar.deger = kk.yapilandirma(**{**ayar.deger.__dict__, "port": ikinci})
    kontrol._ayar_degisti()
    assert len(kurulan) == 2
    assert kontrol.durum()["port"] == ikinci
    assert _baglanilabilir(ikinci) and not _baglanilabilir(ilk)
    kontrol.kapanis()


def test_ayar_degisince_is_ayri_is_parcaciginda_yapilir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    kontrol = _kontrol(_Ayar(acik=False), katalog, kurulan)
    goruldu: list[str] = []
    kontrol._ayar_degisti = lambda: goruldu.append(threading.current_thread().name)  # type: ignore[method-assign]

    kontrol.ayar_degisince()
    son = time.monotonic() + 5
    while not goruldu and time.monotonic() < son:
        time.sleep(0.01)

    assert goruldu == ["kd-katalog-ayar"]


# --------------------------------------------------- geri yükleme (bakım)


def test_geri_yuklemede_katalog_durur_ve_yeniden_acilista_kalkar(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Kod kapısı (§14.1 F5): bakım → kapalı; program yeniden açılınca kalkar."""
    port = find_free_port()
    ayar = _Ayar(acik=True, port=port)
    kapi = _Kapi()
    kontrol = _kontrol(ayar, katalog, kurulan, kapi=kapi)
    kontrol.acilista_baslat()
    assert _baglanilabilir(port)

    kontrol.bakima_al()

    assert kapi.cagrilar == ["bakima_al"]  # önce kapı (503 + uçuştakiler), sonra dinleyici
    assert kontrol.durum()["durum"] == kk.BAKIM
    assert not _baglanilabilir(port)
    assert kontrol.uyku_gerekli() is False
    # Program yeniden açılana dek kapalı kalır: aç ve yeniden başlat etkisiz.
    assert kontrol.ac()["durum"] == kk.BAKIM
    assert kontrol.yeniden_baslat()["durum"] == kk.BAKIM
    assert not _baglanilabilir(port)
    assert kontrol.tepsi_satiri() == "Ağ Kataloğu: geri yükleme nedeniyle kapalı"
    kontrol.kapanis()

    # Program yeniden açıldı: yeni süreç, yeni denetçi.
    yeni = _kontrol(ayar, katalog, kurulan)
    yeni.acilista_baslat()
    assert yeni.durum()["durum"] == kk.ACIK
    assert _baglanilabilir(port)
    yeni.kapanis()


def test_basarisiz_geri_yuklemede_katalog_eski_haline_doner(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kapi = _Kapi()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan, kapi=kapi)
    kontrol.acilista_baslat()

    kontrol.bakima_al()
    kontrol.bakimdan_cik()

    assert kapi.cagrilar == ["bakima_al", "bakimdan_cik"]
    assert kontrol.durum()["durum"] == kk.ACIK
    assert _baglanilabilir(port)
    kontrol.kapanis()


def test_gercek_bakim_kapisi_bakimda_yeni_isi_durdurur(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ortak kapı katalog paketindedir (`katalog.bakim.KAPI`); denetçi onu kullanır."""
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    from katalog.bakim import BakimKapisi

    kapi = BakimKapisi()
    kontrol = kk.KatalogKontrol(
        ayar_okuyucu=lambda: kk.yapilandirma(acik=False),
        ayar_yazici=None,
        bakim_kapisi=kapi,
        ag_saglayici=lambda: _ag(AFIS_IP),
    )

    kontrol.bakima_al()
    with kapi.is_() as izin:
        assert izin is False
    kontrol.bakimdan_cik()
    with kapi.is_() as izin:
        assert izin is True


# ------------------------------------------------------------ IP denetimi


def test_ip_degisince_afis_ve_yer_imi_uyarisi(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    agdaki = [AFIS_IP]
    ayar = _Ayar(acik=False, son_afis_ip=AFIS_IP)
    kontrol = _kontrol(ayar, katalog, kurulan, ag_durumu=lambda: _ag(agdaki[0]))

    assert kontrol.ip_denetle() is True
    assert kontrol.durum()["ip_degisti"] is False
    assert not any("IP adresi değişti" in u for u in kontrol.durum()["uyarilar"])

    agdaki[0] = "192.168.10.99"
    kontrol.ip_denetle()

    durum = kontrol.durum()
    assert durum["ip_degisti"] is True
    assert durum["guncel_ip"] == "192.168.10.99"
    uyari = next(u for u in durum["uyarilar"] if "IP adresi değişti" in u)
    assert "Afişi yeniden basın, yer imlerini güncelleyin." in uyari

    # Afiş yeni adresle basıldı: uyarı kalkar.
    ayar.deger = kk.yapilandirma(**{**ayar.deger.__dict__, "son_afis_ip": "192.168.10.99"})
    kontrol.ip_denetle()
    assert kontrol.durum()["ip_degisti"] is False
    assert not any("IP adresi değişti" in u for u in kontrol.durum()["uyarilar"])


def test_afis_hic_basilmadiysa_onceki_denetimle_karsilastirilir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    agdaki = [AFIS_IP]
    kontrol = _kontrol(_Ayar(acik=False), katalog, kurulan, ag_durumu=lambda: _ag(agdaki[0]))

    kontrol.ip_denetle()
    agdaki[0] = TAHTA_IP
    kontrol.ip_denetle()

    assert any(AFIS_IP in u and TAHTA_IP in u for u in kontrol.durum()["uyarilar"])


def test_secili_ip_kipinde_ip_kaybolunca_dinleyici_yeniden_kurulur(
    katalog: CatalogApp, kurulan: list[KatalogServer], kabin_ip: str
) -> None:
    port = find_free_port()
    agdaki: list[tuple[str, ...]] = [(kabin_ip, TAHTA_IP)]
    kontrol = _kontrol(
        _Ayar(acik=True, port=port, dinleme_kipi=DINLEME_SECILI, secili_ip=kabin_ip),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(*agdaki[0]),
    )
    kontrol.acilista_baslat()
    assert kontrol.durum()["durum"] == kk.ACIK

    agdaki[0] = (TAHTA_IP, "192.168.10.99")  # seçili adres gitti, iki aday var
    kontrol.ip_denetle()

    assert kontrol.durum()["durum"] == kk.HATA
    assert not _baglanilabilir(port, host=kabin_ip)
    kontrol.kapanis()


# ------------------------------------------------------------------ uyku


def test_uyku_yalniz_katalog_acikken_ve_ayar_izin_verirse_engellenir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    ayar = _Ayar(acik=True, port=find_free_port(), uyku_engelleme=True)
    kontrol = _kontrol(ayar, katalog, kurulan)
    bildirimler: list[bool] = []
    kontrol.uyku_dinleyicisi_ekle(lambda: bildirimler.append(kontrol.uyku_gerekli()))

    kontrol.acilista_baslat()
    assert kontrol.uyku_gerekli() is True
    assert kontrol.durum()["uyku_engelli"] is True
    kontrol.kapat()
    assert kontrol.uyku_gerekli() is False

    assert bildirimler[0] is True and bildirimler[-1] is False


def test_kapanista_uyku_birakilir_ve_katalog_yeniden_acilmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan)
    kontrol.acilista_baslat()

    kontrol.kapanis()
    kontrol.yeniden_baslat()

    assert kontrol.uyku_gerekli() is False
    assert not _baglanilabilir(port)


# ------------------------------------------------------------ Ağ Doktoru


def test_dinleyici_sinamasi_uyari_ve_test_netconnection_komutu_verir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    port = find_free_port()
    kontrol = _kontrol(
        _Ayar(acik=True, port=port),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag("127.0.0.1", "192.0.2.77"),  # ilki kapta ulaşılabilir
    )
    kontrol.acilista_baslat()

    sonuc = kontrol.dinleyici_sinamasi()

    assert sonuc["acik"] is True
    assert "güvenlik duvarını ya da VLAN'ı kanıtlamaz" in sonuc["uyari"]
    assert "Başka bir bilgisayardan deneyin." in sonuc["uyari"]
    assert sonuc["sonuclar"][0]["ayakta"] is True
    assert sonuc["sonuclar"][0]["komut"] == f"Test-NetConnection 127.0.0.1 -Port {port}"
    assert sonuc["sonuclar"][1]["ayakta"] is False
    kontrol.kapanis()


def test_guvenlik_duvari_ve_ip_adaylari_sorgulari(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    kontrol = _kontrol(_Ayar(acik=False, port=8765), katalog, kurulan)

    duvar = kontrol.guvenlik_duvari()
    adaylar = kontrol.ip_adaylari()

    assert duvar["dinlemeye_izin"] is True
    assert [m["kod"] for m in duvar["maddeler"]][0] == "etkin"
    assert adaylar["varsayilan_ip"] == AFIS_IP


def test_kural_guncelleme_basariliysa_katalog_yeniden_kurulur(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    cagrilar: list[dict[str, Any]] = []

    def yazici(**kw: Any) -> tuple[bool, str]:
        cagrilar.append(kw)
        return True, "Güvenlik duvarı kuralı güncellendi."

    port = find_free_port()
    kontrol = _kontrol(_Ayar(acik=True, port=port), katalog, kurulan, kural_yazici=yazici)

    sonuc = kontrol.kural_guncelle(port=port, uzak_adresler=["10.20.30.0/23"])

    assert sonuc["tamam"] is True
    assert cagrilar == [{"port": port, "uzak_adresler": ["10.20.30.0/23"]}]
    assert sonuc["durum"]["durum"] == kk.ACIK
    kontrol.kapanis()


def test_kural_guncelleme_reddedilirse_ileti_doner(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    kontrol = _kontrol(
        _Ayar(acik=False),
        katalog,
        kurulan,
        kural_yazici=lambda **kw: (False, "Yönetici izni verilmedi; kural değiştirilmedi."),
    )

    sonuc = kontrol.kural_guncelle(port=8765, uzak_adresler=[])

    assert sonuc == {
        "tamam": False,
        "ileti": "Yönetici izni verilmedi; kural değiştirilmedi.",
        "durum": kontrol.durum(),
    }


def test_yapilandirma_model_nesnesinden_kopyalanir() -> None:
    class _Model:
        acik = True
        port = 9100
        dinleme_kipi = DINLEME_TUM
        secili_ip = ""
        son_afis_ip = AFIS_IP
        uyku_engelleme = False
        tahta_cidrleri = ["10.20.30.0/23", 5]

    ayar = kk.yapilandirma_nesneden(_Model())

    assert ayar == kk.KatalogYapilandirmasi(
        acik=True,
        port=9100,
        dinleme_kipi=DINLEME_TUM,
        son_afis_ip=AFIS_IP,
        uyku_engelleme=False,
        tahta_cidrleri=("10.20.30.0/23",),
    )


def test_uzak_adres_yardimcisi() -> None:
    assert kk.ip_listesi(["10.20.30.0/23"]) == ["LocalSubnet", "10.20.30.0/23"]


# ================================================ F5 düzeltmeleri (bulgu doğrulaması)


def _bekle(kosul: Callable[[], bool], sure: float = 10.0) -> bool:
    son = time.monotonic() + sure
    while not kosul() and time.monotonic() < son:
        time.sleep(0.05)
    return kosul()


def test_saatlik_tikte_gun_icinde_kaybolan_secili_ip_yakalanir(
    katalog: CatalogApp, kurulan: list[KatalogServer], kabin_ip: str, tmp_path: Path
) -> None:
    """Bulgu: `ip_denetle` günlük damgalıdır; DHCP gün içinde adres değiştirirse katalog
    ertesi güne dek kaybolan adreste "açık" görünürdü. Saatlik damgasız iş yakalar."""
    from contextlib import nullcontext
    from datetime import date

    from desktop import gunluk

    port = find_free_port()
    agdaki: list[tuple[str, ...]] = [(kabin_ip, TAHTA_IP)]
    kontrol = _kontrol(
        _Ayar(acik=True, port=port, dinleme_kipi=DINLEME_SECILI, secili_ip=kabin_ip),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(*agdaki[0]),
    )
    kapi = gunluk.GunDegisimiKapisi(
        damga_yolu=tmp_path / "gun-kapisi.json",
        bugun=lambda: date(2026, 9, 24),
        bakim_girisi=lambda: nullcontext(True),
        baglanti_kapatici=lambda: None,
    )
    kapi.kaydet("ip-denetimi", kontrol.ip_denetle)
    kapi.saatlik_kaydet("katalog-saatlik", kontrol.saatlik_denetle)
    kontrol.acilista_baslat()
    kapi.tik()  # açılış: günlük iş damgalanır
    assert kontrol.durum()["durum"] == kk.ACIK

    agdaki[0] = (TAHTA_IP, "192.168.10.99")  # aynı gün adres gitti, iki aday var
    assert kapi.tik() == []  # günlük iş bugün yapıldı; saatlik iş yine koşar

    durum = kontrol.durum()
    assert durum["durum"] == kk.HATA
    assert durum["adres"] is None
    assert not kontrol.tepsi_satiri().startswith("Ağ Kataloğu: açık")
    assert not _baglanilabilir(port, host=kabin_ip)
    kontrol.kapanis()


def test_saatlik_denetim_ag_okunamazsa_calisan_dinleyiciyi_kapatmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer], kabin_ip: str
) -> None:
    port = find_free_port()
    durumlar: list[ag.AgDurumu] = [_ag(kabin_ip, TAHTA_IP)]
    kontrol = _kontrol(
        _Ayar(acik=True, port=port, dinleme_kipi=DINLEME_SECILI, secili_ip=kabin_ip),
        katalog,
        kurulan,
        ag_durumu=lambda: durumlar[0],
    )
    kontrol.acilista_baslat()
    assert kontrol.durum()["durum"] == kk.ACIK

    durumlar[0] = ag.AgDurumu(
        arayuzler=(ag.Arayuz("Varsayılan bağlantı", "10.9.9.9", 0, True),),
        kaynak="yedek",
        hatalar=("Ağ arayüzlerinin listesi okunamadı.",),
    )
    kontrol.saatlik_denetle()
    kontrol.ip_denetle()

    assert kontrol.durum()["durum"] == kk.ACIK
    assert IMZA in _govde(port, host=kabin_ip)
    kontrol.kapanis()


def test_ag_listesi_okunamazsa_tek_aday_kurali_uygulanmaz(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Bulgu: yedek yol yalnız varsayılan adresi bilir; seçili IP belki hâlâ buradadır.

    Eskiden "tek aday" sayılıp katalog seçilmemiş ağda açılıyordu ve ileti yanlış
    ("Seçili IP bu bilgisayarda artık yok") diyordu. Artık açılmaz, kendiliğinden
    yeniden denenir.
    """
    kontrol = _kontrol(
        _Ayar(acik=True, port=find_free_port(), dinleme_kipi=DINLEME_SECILI, secili_ip=TAHTA_IP),
        katalog,
        kurulan,
        ag_durumu=lambda: ag.AgDurumu(
            arayuzler=(ag.Arayuz("Varsayılan bağlantı", AFIS_IP, 0, True),),
            kaynak="yedek",
            hatalar=("Ağ arayüzlerinin listesi okunamadı.",),
        ),
        gecici_deneme_araligi_sn=60.0,
    )

    kontrol.acilista_baslat()

    durum = kontrol.durum()
    assert durum["durum"] == kk.HATA
    assert "ağ bağlantıları okunamadı" in durum["son_hata"]
    assert "yeniden denenecek" in durum["son_hata"]
    assert not any("artık yok" in u for u in durum["uyarilar"])
    assert kurulan == []
    kontrol.kapanis()


def test_guvenlik_duvari_okunamazsa_kendiliginden_yeniden_denenir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Bulgu: oturum açılışının yükünde PowerShell zaman aşımı → katalog o gün kapalı kalırdı.

    Fail-closed korunur (okunamayınca dinlemez) ama kısa aralıkla yeniden denenir.
    """
    cagrilar: list[int] = []

    def duvar_verisi(port: int) -> Any:
        cagrilar.append(port)
        if len(cagrilar) == 1:
            return None  # okunamadı → "bilinmiyor"
        return {"kurallar": [_kural(port)], "ag_profilleri": ["Public"]}

    kontrol = _kontrol(
        _Ayar(acik=True, port=find_free_port()),
        katalog,
        kurulan,
        duvar_verisi=duvar_verisi,
        gecici_deneme_araligi_sn=0.05,
    )

    kontrol.acilista_baslat()
    ilk = kontrol.durum()
    assert ilk["durum"] == kk.ENGELLENDI
    assert "yeniden denenecek" in ilk["son_hata"]

    assert _bekle(lambda: kontrol.durum()["durum"] == kk.ACIK)
    assert len(cagrilar) == 2
    kontrol.kapanis()


def test_kural_tutmuyorsa_yeniden_denenmez(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    cagrilar: list[int] = []

    def duvar_verisi(port: int) -> Any:
        cagrilar.append(port)
        return {"kurallar": [], "ag_profilleri": ["Public"]}

    kontrol = _kontrol(
        _Ayar(acik=True, port=find_free_port()),
        katalog,
        kurulan,
        duvar_verisi=duvar_verisi,
        gecici_deneme_araligi_sn=0.05,
    )

    kontrol.acilista_baslat()
    time.sleep(0.3)
    kontrol.saatlik_denetle()

    assert kontrol.durum()["durum"] == kk.ENGELLENDI
    assert "yeniden denenecek" not in kontrol.durum()["son_hata"]
    assert len(cagrilar) == 1
    kontrol.kapanis()


def test_gecici_denemeler_bitince_saatlik_tikte_bir_kez_yeniden_denenir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    okunur = [False]

    def duvar_verisi(port: int) -> Any:
        return {"kurallar": [_kural(port)], "ag_profilleri": ["Public"]} if okunur[0] else None

    kontrol = _kontrol(
        _Ayar(acik=True, port=find_free_port()),
        katalog,
        kurulan,
        duvar_verisi=duvar_verisi,
        gecici_deneme_sayisi=0,
    )
    kontrol.acilista_baslat()
    assert kontrol.durum()["durum"] == kk.ENGELLENDI
    assert "Saatte bir" in kontrol.durum()["son_hata"]

    kontrol.saatlik_denetle()  # hâlâ okunamıyor: bir sonraki saate kalır
    assert kontrol.durum()["durum"] == kk.ENGELLENDI

    okunur[0] = True
    kontrol.saatlik_denetle()
    assert kontrol.durum()["durum"] == kk.ACIK
    kontrol.kapanis()


def test_ayar_acik_ama_acilamadiysa_kapatilabilir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Bulgu: "Güvenlik duvarı izni yok"ta hiçbir yüzey "kapat" sunmuyordu."""
    ayar = _Ayar(acik=True, port=find_free_port())
    kontrol = _kontrol(
        ayar,
        katalog,
        kurulan,
        duvar_verisi=lambda p: {"kurallar": [], "ag_profilleri": ["Public"]},
    )
    kontrol.acilista_baslat()
    assert kontrol.durum()["durum"] == kk.ENGELLENDI
    assert kontrol.acik_mi() is False
    assert kontrol.kapatilabilir_mi() is True

    kontrol.kapat()

    assert ayar.deger.acik is False
    assert kontrol.kapatilabilir_mi() is False
    assert kontrol.durum()["son_hata"] is None


def test_linuxta_varsayilan_denetim_komutun_kaynak_bloklarini_verir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Bulgu: Pardus komutu kaynaksızdı (MEB WAN'ına açardı). Kaynak = yerel alt ağlar + tahta."""
    kontrol = kk.KatalogKontrol(
        ayar_okuyucu=lambda: kk.yapilandirma(tahta_cidrleri=("10.60.0.0/22",)),
        ayar_yazici=None,
        yukleyici=lambda: katalog,
        ag_saglayici=lambda: _ag(AFIS_IP, TAHTA_IP),
        platform="linux",
    )

    denetim = kontrol.guvenlik_duvari()

    assert denetim["linux"]["bloklar"] == ["192.168.10.0/24", "10.20.30.0/24", "10.60.0.0/22"]


def test_tahta_agindaki_bilgisayar_ogrenci_erisimli_ag_uyarisi_alir(
    katalog: CatalogApp, kurulan: list[KatalogServer]
) -> None:
    """Bulgu: §5.8 "bu bilgisayar öğrenci erişimli ağda" uyarısı Ağ Doktoru'nda yoktu."""
    kontrol = _kontrol(
        _Ayar(acik=True, port=find_free_port(), tahta_cidrleri=("10.20.30.0/23",)),
        katalog,
        kurulan,
        ag_durumu=lambda: _ag(AFIS_IP, TAHTA_IP),
    )

    kontrol.acilista_baslat()

    assert any("öğrenci erişimli ağda" in u for u in kontrol.durum()["uyarilar"])
    adaylar = kontrol.ip_adaylari()
    assert any("öğrenci erişimli ağda" in u for u in adaylar["uyarilar"])
    assert [a["tahta_agi"] for a in adaylar["arayuzler"]] == [False, True]
    kontrol.kapanis()
