"""Bu bilgisayarın ağ arayüzleri ve Ağ Kataloğu IP adayları (tasarım §5.2, §5.6, §5.8).

Katalog adresi (afiş, yer imi, program içi bağlantılar) bir LAN IP'sidir; mDNS,
NetBIOS adı ve dış DNS kullanılmaz (§5.6). Bu modül adayları çıkarır:

* **Varsayılan rotanın arayüzü seçilir** (en düşük metrikli varsayılan rota).
  Ağ Doktoru aday listesini sunar, seçim `KatalogAyari`'nda hatırlanır.
* **127/8 ve 169.254/16 atılır**; çok noktaya yayın, yayın ve belirsiz adres de.
* **Varsayılan rota dışındaki etkin arayüzler** uyarıyla listelenir: katalog
  tüm arayüzlerde dinlerken "bu ağlarda da erişilebilir" (§5.2, EK-30).
* **IP yönlendirme** (§5.8 ikinci ağ kartı yedek yolu): Windows'ta
  `Get-NetIPInterface` Forwarding ve `IPEnableRouter`, Linux'ta
  `/proc/sys/net/ipv4/conf/<arayüz>/forwarding`. Açıksa iki ağ arasında trafik
  geçebilir; Ağ Doktoru uyarır.
* **Ağ profili** (Windows: Genel/Özel/Etki alanı) güvenlik duvarı denetiminin
  4. maddesine girdi olur.

Veri yapılandırılmış kaynaklardan okunur: Windows'ta PowerShell nesneleri
(`desktop/powershell.py`, JSON), Linux'ta `ip -j`. İkisi de yoksa YEDEK yol
yalnız varsayılan IP'yi bulur: UDP soketi bir belge adresine (RFC 5737
TEST-NET-1) `connect` edilir ve çekirdeğin seçtiği kaynak adres okunur.
UDP'de `connect` paket GÖNDERMEZ; yalnız rota tablosuna bakılır (açılışta ağ
yok ilkesi — T11 — bozulmaz).

Bu modül bilgisayarın KENDİ adreslerini okur; istemci IP'si hiçbir yere
yazılmaz (§5.5).
"""

from __future__ import annotations

import ipaddress
import json
import logging
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from desktop import powershell

logger = logging.getLogger("kutuphane_defteri.ag")

#: Yedek yolun rota sorgusu için belge adresi (RFC 5737; hiçbir yere yönlendirilmez).
_BELGE_ADRESI: Final = "192.0.2.1"
_IP_KOMUT_ZAMAN_ASIMI: Final = 5.0

#: Windows ağ profili adları → güvenlik duvarı profil adı.
PROFIL_ESLEME: Final = {
    "Public": "Public",
    "Private": "Private",
    "DomainAuthenticated": "Domain",
    "Domain": "Domain",
}

_WINDOWS_BETIGI: Final = r"""
$adresler = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { [string]$_.AddressState -eq 'Preferred' } |
  ForEach-Object { [pscustomobject]@{
    ad = [string]$_.InterfaceAlias; indeks = [int]$_.InterfaceIndex;
    ip = [string]$_.IPAddress; onek = [int]$_.PrefixLength } })
$rotalar = @(Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { ([string]$_.DestinationPrefix).EndsWith('/0') } |
  ForEach-Object { [pscustomobject]@{
    indeks = [int]$_.InterfaceIndex; metrik = [int]$_.RouteMetric } })
$arayuzler = @(Get-NetIPInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{
    indeks = [int]$_.InterfaceIndex;
    metrik = [int]$_.InterfaceMetric;
    yonlendirme = ([string]$_.Forwarding -eq 'Enabled');
    bagli = ([string]$_.ConnectionState -eq 'Connected') } })
$profiller = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{
    indeks = [int]$_.InterfaceIndex; kategori = [string]$_.NetworkCategory } })
$yonlendirici = 0
try {
  $deger = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters' -Name IPEnableRouter -ErrorAction Stop
  $yonlendirici = [int]$deger.IPEnableRouter
} catch { $yonlendirici = 0 }
[pscustomobject]@{
  adresler = $adresler; rotalar = $rotalar; arayuzler = $arayuzler;
  profiller = $profiller; ip_enable_router = $yonlendirici
} | ConvertTo-Json -Depth 4 -Compress
"""

KomutCalistirici = Callable[[Sequence[str]], str | None]
DosyaOkuyucu = Callable[[Path], str | None]


@dataclass(frozen=True)
class Arayuz:
    """IPv4 adresi olan bir ağ arayüzü (katalog adayı)."""

    ad: str
    ip: str
    onek: int
    varsayilan_rota: bool = False
    #: Güvenlik duvarı profil adı: "Domain" / "Private" / "Public"; bilinmiyorsa None.
    ag_profili: str | None = None
    #: Bu arayüzde IP yönlendirme açık mı; bilinmiyorsa None.
    yonlendirme: bool | None = None

    def sozluk(self) -> dict[str, Any]:
        return {
            "ad": self.ad,
            "ip": self.ip,
            "onek": self.onek,
            "varsayilan_rota": self.varsayilan_rota,
            "ag_profili": self.ag_profili,
            "yonlendirme": self.yonlendirme,
        }


@dataclass(frozen=True)
class AgDurumu:
    """Aday arayüzler (127/8 ve 169.254/16 atılmış), varsayılan IP ve uyarılar."""

    arayuzler: tuple[Arayuz, ...] = ()
    kaynak: str = "yok"
    #: Sistem genelinde IP yönlendirme (Windows `IPEnableRouter`); bilinmiyorsa None.
    sistem_yonlendirme: bool | None = None
    hatalar: tuple[str, ...] = field(default_factory=tuple)

    @property
    def varsayilan(self) -> Arayuz | None:
        for arayuz in self.arayuzler:
            if arayuz.varsayilan_rota:
                return arayuz
        return None

    @property
    def varsayilan_ip(self) -> str | None:
        arayuz = self.varsayilan
        return arayuz.ip if arayuz is not None else None

    def ip_var_mi(self, ip: str) -> bool:
        return any(arayuz.ip == ip for arayuz in self.arayuzler)

    def arayuz(self, ip: str) -> Arayuz | None:
        for aday in self.arayuzler:
            if aday.ip == ip:
                return aday
        return None

    def varsayilan_disindakiler(self) -> tuple[Arayuz, ...]:
        return tuple(arayuz for arayuz in self.arayuzler if not arayuz.varsayilan_rota)

    def yonlendirme_acik(self) -> bool:
        return bool(self.sistem_yonlendirme) or any(a.yonlendirme for a in self.arayuzler)

    def tahta_agindakiler(self, tahta_bloklari: Sequence[str]) -> tuple[tuple[Arayuz, str], ...]:
        """Adresi Ayarlar'daki tahta ağı bloklarından birinin içinde olan arayüzler (§5.8)."""
        aglar: list[ipaddress.IPv4Network] = []
        for blok in tahta_bloklari:
            try:
                aglar.append(ipaddress.IPv4Network(str(blok).strip(), strict=False))
            except ValueError:
                continue
        sonuc: list[tuple[Arayuz, str]] = []
        for arayuz in self.arayuzler:
            try:
                adres = ipaddress.IPv4Address(arayuz.ip)
            except ValueError:
                continue
            ag = next((a for a in aglar if adres in a), None)
            if ag is not None:
                sonuc.append((arayuz, str(ag)))
        return tuple(sonuc)

    def uyarilar(self, *, tum_arayuzler: bool, tahta_bloklari: Sequence[str] = ()) -> list[str]:
        """Ağ Doktoru'nun gösterdiği uyarılar (Türkçe, kişisel veri yok).

        `tahta_bloklari`: Ayarlar → Ağ Kataloğu'ndaki tahta ağı blokları. Bu
        bilgisayarın bir adresi o blokların içindeyse bilgisayar öğrenci erişimli
        ağdadır (§5.8 yedek yol 1, KM-19): Ağ Doktoru bunu açıkça söyler.
        """
        sonuc: list[str] = []
        for arayuz, blok in self.tahta_agindakiler(tahta_bloklari):
            sonuc.append(
                f"Bu bilgisayar öğrenci erişimli ağda: {arayuz.ad} ({arayuz.ip}) tahta ağı "
                f"bloğunun ({blok}) içinde. Bu bilgisayarda kişisel veri var: kütüphane masası "
                "hesabında kişisel oturum açmayın, bilgisayardan ayrılırken programı kilitleyin. "
                "Bu bağlantı yalnız ilçe sistem yöneticisinin uygun görüşüyle kullanılır."
            )
        if not self.arayuzler:
            sonuc.append(
                "Bu bilgisayarda okul ağına bağlı bir IP adresi bulunamadı. Ağ kablosunu "
                "ya da kablosuz bağlantıyı denetleyin."
            )
        elif self.varsayilan is None:
            sonuc.append("Varsayılan ağ geçidi bulunamadı; katalog adresini listeden elle seçin.")
        if tum_arayuzler:
            for arayuz in self.varsayilan_disindakiler():
                sonuc.append(
                    f"Ağ Kataloğu bu ağda da erişilebilir: {arayuz.ad} ({arayuz.ip}). "
                    "İstemiyorsanız Ayarlar → Ağ Kataloğu → Dinleme bölümünde "
                    "“Yalnız seçili IP adresinde” seçeneğini kullanın."
                )
        if self.yonlendirme_acik():
            sonuc.append(
                "Bu bilgisayarda IP yönlendirme açık: iki ağ arasında trafik geçebilir. "
                "İkinci ağ kartı kullanıyorsanız okulun BTR'siyle birlikte "
                "yönlendirmeyi kapatın."
            )
        return sonuc

    def sozluk(self, *, tum_arayuzler: bool, tahta_bloklari: Sequence[str] = ()) -> dict[str, Any]:
        tahtadakiler = {arayuz.ip for arayuz, _ in self.tahta_agindakiler(tahta_bloklari)}
        return {
            "arayuzler": [
                {**arayuz.sozluk(), "tahta_agi": arayuz.ip in tahtadakiler}
                for arayuz in self.arayuzler
            ],
            "varsayilan_ip": self.varsayilan_ip,
            "yonlendirme_acik": self.yonlendirme_acik(),
            "uyarilar": self.uyarilar(tum_arayuzler=tum_arayuzler, tahta_bloklari=tahta_bloklari),
            "kaynak": self.kaynak,
            "okunamadi": self.okunamadi,
        }

    @property
    def okunamadi(self) -> bool:
        """Arayüz listesi okunamadı (yedek yol): liste eksik olabilir, karar verilmez."""
        return self.kaynak == "yedek" or bool(self.hatalar)


def aday_mi(ip: str) -> bool:
    """Katalog adresi olabilir mi? 127/8, 169.254/16, çok noktaya yayın vb. atılır."""
    try:
        adres = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (
        adres.is_loopback
        or adres.is_link_local
        or adres.is_multicast
        or adres.is_unspecified
        or adres.is_reserved
        or int(adres) == 0xFFFFFFFF
    )


# ------------------------------------------------------------------ Windows


def windows_durumu_ayristir(veri: Any) -> AgDurumu:
    """PowerShell betiğinin JSON'unu `AgDurumu`'na çevirir (testte taklit edilir)."""
    if not isinstance(veri, dict):
        raise ValueError("Beklenmeyen ağ verisi.")
    rotalar = [r for r in powershell.liste(veri.get("rotalar")) if isinstance(r, dict)]
    arayuz_bilgisi = {
        int(a.get("indeks") or -1): a
        for a in powershell.liste(veri.get("arayuzler"))
        if isinstance(a, dict)
    }
    varsayilan_indeks: int | None = None
    if rotalar:
        # Windows rotayı RouteMetric + InterfaceMetric TOPLAMIYLA seçer: DHCP'nin
        # varsayılan rotaları çoğu zaman RouteMetric=0'dır, tercih (kablolu > Wi-Fi,
        # birinci kart > ikinci kart) arayüz metriğindedir. Eşitlikte küçük indeks.
        def etkin_metrik(rota: dict[str, Any]) -> tuple[int, int]:
            indeks = int(rota.get("indeks") or -1)
            arayuz_metrigi = int(arayuz_bilgisi.get(indeks, {}).get("metrik") or 0)
            return int(rota.get("metrik") or 0) + arayuz_metrigi, indeks

        varsayilan_indeks = int(min(rotalar, key=etkin_metrik).get("indeks") or -1)
    profiller = {
        int(p.get("indeks") or -1): PROFIL_ESLEME.get(str(p.get("kategori") or ""))
        for p in powershell.liste(veri.get("profiller"))
        if isinstance(p, dict)
    }
    arayuzler: list[Arayuz] = []
    varsayilan_verildi = False
    for adres in powershell.liste(veri.get("adresler")):
        if not isinstance(adres, dict):
            continue
        ip = str(adres.get("ip") or "")
        if not aday_mi(ip):
            continue
        indeks = int(adres.get("indeks") or -1)
        bilgi = arayuz_bilgisi.get(indeks, {})
        if bilgi and bilgi.get("bagli") is False:
            continue
        varsayilan = indeks == varsayilan_indeks and not varsayilan_verildi
        varsayilan_verildi = varsayilan_verildi or varsayilan
        yonlendirme = bilgi.get("yonlendirme")
        arayuzler.append(
            Arayuz(
                ad=str(adres.get("ad") or f"Arayüz {indeks}"),
                ip=ip,
                onek=int(adres.get("onek") or 0),
                varsayilan_rota=varsayilan,
                ag_profili=profiller.get(indeks),
                yonlendirme=bool(yonlendirme) if yonlendirme is not None else None,
            )
        )
    arayuzler.sort(key=lambda a: (not a.varsayilan_rota, a.ad, a.ip))
    return AgDurumu(
        arayuzler=tuple(arayuzler),
        kaynak="powershell",
        sistem_yonlendirme=bool(int(veri.get("ip_enable_router") or 0)),
    )


def windows_durumu(*, calistirici: powershell.Calistirici | None = None) -> AgDurumu:
    return windows_durumu_ayristir(
        powershell.json_calistir(_WINDOWS_BETIGI, calistirici=calistirici)
    )


# -------------------------------------------------------------------- Linux


def _komut(argv: Sequence[str]) -> str | None:
    yol = shutil.which(argv[0])
    if yol is None:
        return None
    try:
        sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
            [yol, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=_IP_KOMUT_ZAMAN_ASIMI,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sonuc.stdout if sonuc.returncode == 0 else None


def _dosya_oku(yol: Path) -> str | None:
    try:
        return yol.read_text(encoding="ascii").strip()
    except OSError:
        return None


def linux_durumu_ayristir(
    adres_json: str, rota_json: str, *, dosya_okuyucu: DosyaOkuyucu = _dosya_oku
) -> AgDurumu:
    """`ip -j -4 addr show` ve `ip -j -4 route show default` çıktılarını çevirir."""
    adresler = json.loads(adres_json or "[]")
    rotalar = json.loads(rota_json or "[]")
    varsayilan_ad: str | None = None
    rota_listesi = [r for r in rotalar if isinstance(r, dict) and r.get("dev")]
    if rota_listesi:
        varsayilan_ad = str(min(rota_listesi, key=lambda r: int(r.get("metric") or 0))["dev"])
    arayuzler: list[Arayuz] = []
    varsayilan_verildi = False
    for kayit in adresler:
        if not isinstance(kayit, dict):
            continue
        ad = str(kayit.get("ifname") or "")
        bayraklar = kayit.get("flags") or []
        if "UP" not in bayraklar:
            continue
        yonlendirme_metni = dosya_okuyucu(Path(f"/proc/sys/net/ipv4/conf/{ad}/forwarding"))
        yonlendirme = None if yonlendirme_metni is None else yonlendirme_metni == "1"
        for bilgi in kayit.get("addr_info") or []:
            if not isinstance(bilgi, dict) or bilgi.get("family") != "inet":
                continue
            ip = str(bilgi.get("local") or "")
            if not aday_mi(ip):
                continue
            varsayilan = ad == varsayilan_ad and not varsayilan_verildi
            varsayilan_verildi = varsayilan_verildi or varsayilan
            arayuzler.append(
                Arayuz(
                    ad=ad,
                    ip=ip,
                    onek=int(bilgi.get("prefixlen") or 0),
                    varsayilan_rota=varsayilan,
                    yonlendirme=yonlendirme,
                )
            )
    arayuzler.sort(key=lambda a: (not a.varsayilan_rota, a.ad, a.ip))
    return AgDurumu(arayuzler=tuple(arayuzler), kaynak="ip")


def linux_durumu(
    *, komut: KomutCalistirici = _komut, dosya_okuyucu: DosyaOkuyucu = _dosya_oku
) -> AgDurumu:
    adres = komut(["ip", "-j", "-4", "addr", "show"])
    rota = komut(["ip", "-j", "-4", "route", "show", "default"])
    if adres is None or rota is None:
        raise OSError("ip komutu çalışmadı.")
    return linux_durumu_ayristir(adres, rota, dosya_okuyucu=dosya_okuyucu)


# ---------------------------------------------------------------------- yedek


def yedek_varsayilan_ip(*, soket_kurucu: Callable[[], socket.socket] | None = None) -> str | None:
    """Çekirdeğin varsayılan rota için seçtiği kaynak adres (paket göndermez)."""
    kurucu = soket_kurucu or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    try:
        with kurucu() as sock:
            sock.connect((_BELGE_ADRESI, 9))
            ip = str(sock.getsockname()[0])
    except OSError:
        return None
    return ip if aday_mi(ip) else None


def yedek_durum(*, soket_kurucu: Callable[[], socket.socket] | None = None) -> AgDurumu:
    ip = yedek_varsayilan_ip(soket_kurucu=soket_kurucu)
    if ip is None:
        return AgDurumu(kaynak="yedek")
    return AgDurumu(
        arayuzler=(Arayuz(ad="Varsayılan bağlantı", ip=ip, onek=0, varsayilan_rota=True),),
        kaynak="yedek",
    )


# ------------------------------------------------------------------- giriş


def ag_durumu(
    *,
    platform: str = sys.platform,
    windows: Callable[[], AgDurumu] | None = None,
    linux: Callable[[], AgDurumu] | None = None,
    yedek: Callable[[], AgDurumu] | None = None,
) -> AgDurumu:
    """Platforma uygun kaynaktan ağ durumunu okur; olmazsa yedek yola düşer."""
    birincil: Callable[[], AgDurumu] | None = None
    if platform == "win32":
        birincil = windows or windows_durumu
    elif platform.startswith("linux"):
        birincil = linux or linux_durumu
    hata: str | None = None
    if birincil is not None:
        try:
            return birincil()
        except (OSError, ValueError, powershell.PowerShellHatasi) as exc:
            logger.warning("Ağ arayüzleri okunamadı; yedek yola geçildi (%s).", exc)
            hata = "Ağ arayüzlerinin listesi okunamadı; yalnız varsayılan adres gösteriliyor."
    durum = (yedek or yedek_durum)()
    if hata:
        return AgDurumu(
            arayuzler=durum.arayuzler,
            kaynak=durum.kaynak,
            sistem_yonlendirme=durum.sistem_yonlendirme,
            hatalar=(*durum.hatalar, hata),
        )
    return durum


def katalog_adresi(ip: str, port: int) -> str:
    """Afişte ve yer imlerinde kullanılan katalog adresi."""
    return f"http://{ip}:{port}/"
