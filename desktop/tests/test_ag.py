"""Ağ arayüzleri ve Ağ Kataloğu IP adayları (tasarım §5.2, §5.6, §5.8).

Windows'ta veri PowerShell nesnelerinden (JSON), Linux'ta `ip -j`'den gelir;
ikisi de burada ÇIKTI TAKLİDİYLE sınanır (adresler RFC 5737 belge
aralıklarından ve özel aralıklardan uydurmadır; okul ağı bilgisi değildir,
TB25). Gerçek komutlar Docker'da yoktur.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from desktop import ag, powershell

# ------------------------------------------------------------------ adaylar


@pytest.mark.parametrize(
    ("ip", "beklenen"),
    [
        ("192.168.10.5", True),
        ("10.20.30.40", True),
        ("172.16.0.9", True),
        ("127.0.0.1", False),  # 127/8 atılır
        ("127.5.5.5", False),
        ("169.254.12.1", False),  # 169.254/16 atılır
        ("224.0.0.251", False),
        ("0.0.0.0", False),  # noqa: S104 — belirsiz adres aday değildir
        ("255.255.255.255", False),
        ("240.0.0.1", False),
        ("fe80::1", False),  # IPv4 dışı
        ("", False),
        ("abc", False),
    ],
)
def test_aday_kurali(ip: str, beklenen: bool) -> None:
    assert ag.aday_mi(ip) is beklenen


# ------------------------------------------------------------------ Windows


def _windows_verisi(**degisiklik: Any) -> dict[str, Any]:
    veri: dict[str, Any] = {
        "adresler": [
            {"ad": "Ethernet", "indeks": 7, "ip": "192.168.10.5", "onek": 24},
            {"ad": "Tahta Ağı", "indeks": 9, "ip": "10.20.30.40", "onek": 23},
            {"ad": "Loopback Pseudo-Interface 1", "indeks": 1, "ip": "127.0.0.1", "onek": 8},
            {"ad": "Ethernet 3", "indeks": 12, "ip": "169.254.3.3", "onek": 16},
            {"ad": "Kapalı", "indeks": 15, "ip": "192.168.50.2", "onek": 24},
        ],
        "rotalar": [{"indeks": 9, "metrik": 50}, {"indeks": 7, "metrik": 0}],
        "arayuzler": [
            {"indeks": 7, "yonlendirme": False, "bagli": True},
            {"indeks": 9, "yonlendirme": False, "bagli": True},
            {"indeks": 15, "yonlendirme": False, "bagli": False},
        ],
        "profiller": [
            {"indeks": 7, "kategori": "DomainAuthenticated"},
            {"indeks": 9, "kategori": "Public"},
        ],
        "ip_enable_router": 0,
    }
    veri.update(degisiklik)
    return veri


def test_windows_varsayilan_rota_en_dusuk_metrikli_arayuzdur() -> None:
    durum = ag.windows_durumu_ayristir(_windows_verisi())

    assert durum.varsayilan_ip == "192.168.10.5"
    assert [a.ip for a in durum.arayuzler] == ["192.168.10.5", "10.20.30.40"]
    assert durum.arayuzler[0].ag_profili == "Domain"
    assert durum.arayuzler[1].ag_profili == "Public"
    assert durum.kaynak == "powershell"


def test_windows_varsayilan_rota_arayuz_metrigini_de_sayar() -> None:
    """F5 düzeltmesi: Windows rotayı RouteMetric + InterfaceMetric toplamıyla seçer.

    DHCP'nin iki varsayılan rotası da RouteMetric=0 olabilir; tercih (kablolu >
    Wi-Fi) arayüz metriğindedir. Eskiden listede ilk gelen seçilirdi.
    """
    arayuzler = [
        {"indeks": 7, "metrik": 35, "yonlendirme": False, "bagli": True},
        {"indeks": 9, "metrik": 25, "yonlendirme": False, "bagli": True},
    ]
    for rotalar in (
        [{"indeks": 7, "metrik": 0}, {"indeks": 9, "metrik": 0}],
        [{"indeks": 9, "metrik": 0}, {"indeks": 7, "metrik": 0}],
    ):
        durum = ag.windows_durumu_ayristir(_windows_verisi(rotalar=rotalar, arayuzler=arayuzler))
        assert durum.varsayilan_ip == "10.20.30.40"
    # Toplam eşitse küçük indeks (sıradan bağımsız, belirli).
    esit = [
        {"indeks": 7, "metrik": 25, "yonlendirme": False, "bagli": True},
        {"indeks": 9, "metrik": 25, "yonlendirme": False, "bagli": True},
    ]
    durum = ag.windows_durumu_ayristir(
        _windows_verisi(
            rotalar=[{"indeks": 9, "metrik": 0}, {"indeks": 7, "metrik": 0}], arayuzler=esit
        )
    )
    assert durum.varsayilan_ip == "192.168.10.5"


def test_windows_betigi_arayuz_metrigini_toplar() -> None:
    assert "metrik = [int]$_.InterfaceMetric" in ag._WINDOWS_BETIGI


def test_tahta_agindaki_adres_ogrenci_erisimli_ag_uyarisi_verir() -> None:
    """§5.8 yedek yol 1 (KM-19): bilgisayar tahta VLAN'ına bağlıysa Ağ Doktoru uyarır."""
    durum = ag.windows_durumu_ayristir(_windows_verisi())

    uyarilar = durum.uyarilar(tum_arayuzler=False, tahta_bloklari=["10.20.30.0/23", "bozuk"])
    bos = durum.uyarilar(tum_arayuzler=False, tahta_bloklari=["10.99.0.0/24"])
    sozluk = durum.sozluk(tum_arayuzler=False, tahta_bloklari=["10.20.30.0/23"])

    assert any(
        "öğrenci erişimli ağda" in u and "10.20.30.40" in u and "10.20.30.0/23" in u
        for u in uyarilar
    )
    assert not any("öğrenci erişimli" in u for u in bos)
    assert [a["tahta_agi"] for a in sozluk["arayuzler"]] == [False, True]
    assert any("öğrenci erişimli" in u for u in sozluk["uyarilar"])


def test_yedek_yol_okunamadi_sayilir() -> None:
    assert ag.AgDurumu(kaynak="yedek").okunamadi is True
    assert ag.AgDurumu(kaynak="powershell", hatalar=("x",)).okunamadi is True
    assert ag.AgDurumu(kaynak="powershell").okunamadi is False


def test_windows_loopback_baglanti_yerel_ve_bagli_olmayan_atilir() -> None:
    durum = ag.windows_durumu_ayristir(_windows_verisi())

    ipler = {a.ip for a in durum.arayuzler}
    assert "127.0.0.1" not in ipler
    assert "169.254.3.3" not in ipler
    assert "192.168.50.2" not in ipler  # arayüz bağlı değil


def test_windows_convertto_json_tek_oge_ve_bos_dizi_tuhafligi() -> None:
    """PowerShell 5.1: tek öğeli dizi nesneye, boş dizi `null`a dönebilir."""
    veri = _windows_verisi(
        adresler={"ad": "Ethernet", "indeks": 7, "ip": "192.168.10.5", "onek": 24},
        rotalar={"indeks": 7, "metrik": 0},
        arayuzler=None,
        profiller=None,
    )

    durum = ag.windows_durumu_ayristir(veri)

    assert [a.ip for a in durum.arayuzler] == ["192.168.10.5"]
    assert durum.varsayilan_ip == "192.168.10.5"
    assert durum.arayuzler[0].ag_profili is None


def test_windows_varsayilan_rota_yoksa_uyari() -> None:
    durum = ag.windows_durumu_ayristir(_windows_verisi(rotalar=[]))

    assert durum.varsayilan_ip is None
    assert any("ağ geçidi" in u for u in durum.uyarilar(tum_arayuzler=True))


def test_varsayilan_rota_disindaki_arayuzler_tum_arayuz_kipinde_uyarilir() -> None:
    """§5.2, EK-30: "katalog bu ağlarda da erişilebilir"."""
    durum = ag.windows_durumu_ayristir(_windows_verisi())

    tum = durum.uyarilar(tum_arayuzler=True)
    secili = durum.uyarilar(tum_arayuzler=False)

    assert any("bu ağda da erişilebilir" in u and "10.20.30.40" in u for u in tum)
    assert not any("erişilebilir" in u for u in secili)


def test_ip_yonlendirme_acikken_uyarilir() -> None:
    """§5.8 ikinci ağ kartı: Forwarding ya da IPEnableRouter açıksa uyarı."""
    arayuz_acik = ag.windows_durumu_ayristir(
        _windows_verisi(
            arayuzler=[
                {"indeks": 7, "yonlendirme": True, "bagli": True},
                {"indeks": 9, "yonlendirme": False, "bagli": True},
            ]
        )
    )
    sistem_acik = ag.windows_durumu_ayristir(_windows_verisi(ip_enable_router=1))
    kapali = ag.windows_durumu_ayristir(_windows_verisi())

    for durum in (arayuz_acik, sistem_acik):
        assert durum.yonlendirme_acik() is True
        assert any("yönlendirme" in u for u in durum.uyarilar(tum_arayuzler=False))
    assert kapali.yonlendirme_acik() is False


def test_windows_betigi_powershell_ile_json_uretir() -> None:
    """Betik `-EncodedCommand` ile gider; çıktı JSON'dur (çalıştırıcı taklit)."""
    cagrilar: list[Sequence[str]] = []

    def calistirici(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        cagrilar.append(argv)
        return 0, json.dumps(_windows_verisi()).encode("utf-8")

    durum = ag.windows_durumu(calistirici=calistirici)

    assert durum.varsayilan_ip == "192.168.10.5"
    (argv,) = cagrilar
    assert argv[0].endswith("powershell.exe")
    assert "-EncodedCommand" in argv and "-NonInteractive" in argv


def test_windows_arayuzu_bozuk_veriyi_reddeder() -> None:
    with pytest.raises(ValueError):
        ag.windows_durumu_ayristir(["liste"])


# -------------------------------------------------------------------- Linux

_IP_ADDR = json.dumps(
    [
        {
            "ifname": "lo",
            "flags": ["LOOPBACK", "UP"],
            "addr_info": [{"family": "inet", "local": "127.0.0.1", "prefixlen": 8}],
        },
        {
            "ifname": "enp3s0",
            "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
            "addr_info": [{"family": "inet", "local": "192.168.10.5", "prefixlen": 24}],
        },
        {
            "ifname": "wlp2s0",
            "flags": ["BROADCAST", "MULTICAST", "UP"],
            "addr_info": [{"family": "inet", "local": "10.20.30.40", "prefixlen": 23}],
        },
        {
            "ifname": "enx0",
            "flags": ["BROADCAST", "MULTICAST"],
            "addr_info": [{"family": "inet", "local": "192.168.99.1", "prefixlen": 24}],
        },
    ]
)
_IP_ROUTE = json.dumps([{"dst": "default", "gateway": "192.168.10.1", "dev": "enp3s0"}])


def test_linux_ip_j_ciktisi_cozulur() -> None:
    okunan: list[Path] = []

    def dosya(yol: Path) -> str | None:
        okunan.append(yol)
        return "1" if "wlp2s0" in str(yol) else "0"

    durum = ag.linux_durumu_ayristir(_IP_ADDR, _IP_ROUTE, dosya_okuyucu=dosya)

    assert durum.varsayilan_ip == "192.168.10.5"
    assert [a.ip for a in durum.arayuzler] == ["192.168.10.5", "10.20.30.40"]  # lo ve DOWN atıldı
    assert durum.arayuz("10.20.30.40") is not None
    assert durum.arayuz("10.20.30.40").yonlendirme is True  # type: ignore[union-attr]
    assert durum.yonlendirme_acik() is True
    assert Path("/proc/sys/net/ipv4/conf/enp3s0/forwarding") in okunan


def test_linux_komutu_yoksa_hata_yukseltir() -> None:
    with pytest.raises(OSError):
        ag.linux_durumu(komut=lambda argv: None)


def test_linux_komut_ciktisi_uctan_uca() -> None:
    def komut(argv: Sequence[str]) -> str | None:
        return _IP_ADDR if "addr" in argv else _IP_ROUTE

    durum = ag.linux_durumu(komut=komut, dosya_okuyucu=lambda yol: None)

    assert durum.varsayilan_ip == "192.168.10.5"
    assert durum.arayuzler[0].yonlendirme is None  # okunamadı: bilinmiyor


# --------------------------------------------------------------------- yedek


class _SahteUdp:
    def __init__(self, ip: str | None) -> None:
        self.ip = ip
        self.baglanilan: tuple[str, int] | None = None

    def __enter__(self) -> _SahteUdp:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def connect(self, adres: tuple[str, int]) -> None:
        self.baglanilan = adres
        if self.ip is None:
            raise OSError("Ağa ulaşılamıyor")

    def getsockname(self) -> tuple[str, int]:
        assert self.ip is not None
        return (self.ip, 50000)


def test_yedek_yol_belge_adresine_udp_connect_ile_kaynak_adresi_bulur() -> None:
    """UDP `connect` paket göndermez; yalnız rota tablosu okunur (T11: açılışta ağ yok)."""
    sahte = _SahteUdp("192.168.10.5")

    durum = ag.yedek_durum(soket_kurucu=lambda: sahte)  # type: ignore[arg-type,return-value]

    assert durum.varsayilan_ip == "192.168.10.5"
    assert sahte.baglanilan == ("192.0.2.1", 9)  # RFC 5737 TEST-NET-1


@pytest.mark.parametrize("ip", [None, "127.0.0.1"])
def test_yedek_yol_ag_yoksa_bos(ip: str | None) -> None:
    durum = ag.yedek_durum(soket_kurucu=lambda: _SahteUdp(ip))  # type: ignore[arg-type,return-value]

    assert durum.arayuzler == ()
    assert any("IP adresi bulunamadı" in u for u in durum.uyarilar(tum_arayuzler=True))


def test_gercek_yedek_yol_ag_disina_paket_gondermeden_calisir() -> None:
    """Docker kabında da çalışır: sonuç ya geçerli bir aday ya da yok."""
    ip = ag.yedek_varsayilan_ip()

    assert ip is None or ag.aday_mi(ip)


def test_birincil_kaynak_hata_verirse_yedege_duser() -> None:
    def patlayan() -> ag.AgDurumu:
        raise powershell.PowerShellHatasi("yok")

    durum = ag.ag_durumu(
        platform="win32",
        windows=patlayan,
        yedek=lambda: ag.AgDurumu(
            arayuzler=(ag.Arayuz("Varsayılan bağlantı", "192.168.10.5", 0, True),),
            kaynak="yedek",
        ),
    )

    assert durum.kaynak == "yedek"
    assert durum.varsayilan_ip == "192.168.10.5"
    assert any("okunamadı" in h for h in durum.hatalar)


def test_platform_secimi() -> None:
    win = ag.AgDurumu(kaynak="powershell")
    lin = ag.AgDurumu(kaynak="ip")
    yed = ag.AgDurumu(kaynak="yedek")

    assert ag.ag_durumu(platform="win32", windows=lambda: win, yedek=lambda: yed) is win
    assert ag.ag_durumu(platform="linux", linux=lambda: lin, yedek=lambda: yed) is lin
    assert ag.ag_durumu(platform="darwin", yedek=lambda: yed) is yed


def test_sozluk_kisisel_veri_ve_yonetim_portu_icermez() -> None:
    durum = ag.windows_durumu_ayristir(_windows_verisi())

    sozluk = durum.sozluk(tum_arayuzler=True)

    assert set(sozluk) == {
        "arayuzler",
        "varsayilan_ip",
        "yonlendirme_acik",
        "uyarilar",
        "kaynak",
        "okunamadi",
    }
    assert set(sozluk["arayuzler"][0]) == {
        "ad",
        "ip",
        "onek",
        "varsayilan_rota",
        "ag_profili",
        "yonlendirme",
        "tahta_agi",
    }
    assert sozluk["okunamadi"] is False


def test_katalog_adresi() -> None:
    assert ag.katalog_adresi("192.168.10.5", 8765) == "http://192.168.10.5:8765/"


def test_modul_giden_baglanti_acmaz() -> None:
    """Yedek yol UDP'dir; TCP ile dışarı bağlanan bir çağrı modülde yoktur (T11)."""
    kaynak = Path(ag.__file__).read_text(encoding="utf-8")

    assert "create_connection" not in kaynak
    assert "urllib" not in kaynak
    assert "SOCK_DGRAM" in kaynak
    assert socket.SOCK_DGRAM  # yalnız sabitin varlığı
