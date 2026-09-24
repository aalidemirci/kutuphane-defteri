"""Güvenlik duvarı: beş maddelik denetim, kural yazma ve UAC yardımcısı (tasarım §5.7).

**Denetim (Windows).** Ağ Kataloğu okul ağında (tüm arayüzlerde ya da seçili
IP'de) YALNIZ bu denetimin beş maddesi tutarsa dinler; biri tutmazsa dinlemez
ve Ağ Doktoru düzeltme adımını gösterir (§5.10-10). Veri yapılandırılmıştır:
`Get-NetFirewallRule -PolicyStore ActiveStore` ve ona bağlı uygulama, port ve
adres filtreleri (`desktop/powershell.py`, JSON). netsh çıktısı yerelleştirilmiş
geldiği için AYRIŞTIRILMAZ (GA-5). Maddeler:

1. **etkin** — bu programa ait bir gelen izin kuralı var ve etkin mi;
2. **program** — kuraldaki program yolu `sys.executable` ile aynı mı;
3. **port** — kuralın TCP yerel portu ayardaki portu kapsıyor mu;
4. **kapsam** — kuralın profili bu bilgisayarın etkin ağ profilini (Genel,
   Özel, Etki alanı) kapsıyor mu; uzak adresler ne (`LocalSubnet` + BTR'nin
   doğruladığı tahta ağı blokları). Uzak adres "her yer" ise madde UYARI verir
   ama dinlemeyi engellemez: kural BTR'nin kararıyla genişletilmiş olabilir.
   Programa ait BİRDEN ÇOK izin kuralı varsa Windows herhangi birine uyan
   bağlantıyı kabul eder: madde bütün kuralların BİRLEŞİMİYLE değerlendirilir
   (profillerin birleşimi; etkin profile uyan kuralların uzak adreslerinin
   birleşimi; biri "her yer" ise UYARI). Kurallar belirli bir sırayla
   değerlendirilir (PowerShell'in döndürdüğü sıra belirsizdir); sonuç sıradan
   bağımsızdır;
5. **engelleme** — bu program için etkin bir gelen ENGELLEME kuralı var mı
   (eski "Windows Güvenlik Uyarısı" iletişim kutusunun bıraktığı "engelle"
   kuralları izin kurallarından önce gelir).

Denetim çalışmazsa (PowerShell yok, zaman aşımı, yetki) sonuç "bilinmiyor"dur
ve katalog DİNLEMEZ (fail-closed). Taşınabilir pakette kural kurulum
dizinindeki programa yazıldığı için 2. madde tutmaz: taşınabilir pakette Ağ
Kataloğu sunulmaz (§5.2, GA-5). Denetimin yönetici olmayan hesapta çalıştığı
sahada doğrulanır (§5.10-15, F12).

**Linux (Pardus).** Program kural açmaz. ufw ya da firewalld'nin durumu
okunur ve Ağ Doktoru'na çalıştırılacak komut verilir; paket ufw uygulama
profilini ve firewalld servis tanımını bırakır (`packaging/linux/`). Komut
KAYNAK SINIRLIDIR (`linux_komutu`): Windows kuralındaki `LocalSubnet` + tahta
ağı blokları kapsamının karşılığı olarak her blok için ayrı satır; tanım
dosyası yoksa (taşınabilir arşiv) ya da port değiştiyse port temelli. Denetim
dinlemeyi engellemez.

**Kural yazma** yönetici yetkisi ister. Program kendini UAC ile yükseltilmiş
olarak `--guvenlik-duvari-kurali` kipinde yeniden çalıştırır (`kural_guncelle_uac`);
o kip kuralı siler + yeniden ekler, program için gelen engelleme kurallarını
kaldırır ve portu HKLM kayıt defterine yazar (kurucu portu oradan okur, §5.7).
Kip pencere, kilit, veri dizini ve günlük AÇMAZ: yükseltilmiş süreç BTR'nin
hesabında koşabilir, o hesabın profiline hiçbir şey yazılmamalıdır.
"""

from __future__ import annotations

import ipaddress
import logging
import ntpath
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from desktop import powershell

logger = logging.getLogger("kutuphane_defteri.guvenlik_duvari")

#: Kural adı (ASCII; tasarım §2.3 kimlik sabitleri). Kurucu da bu adı kullanır.
KURAL_ADI: Final = "Kutuphane Defteri Katalog"
#: Kurucunun portu okuduğu HKLM anahtarı ve değeri (§5.7). DWORD.
HKLM_ANAHTARI: Final = r"SOFTWARE\KutuphaneDefteri"
HKLM_PORT_DEGERI: Final = "KatalogPortu"
#: Kuralın varsayılan uzak adres kapsamı: yalnız yerel alt ağ (GA-6: RFC1918'in tamamı açılmaz).
YEREL_ALT_AG: Final = "LocalSubnet"

#: Yükseltilmiş yardımcı kipin bayrağı (desktop/main.py bunu erkenden yakalar).
UAC_BAYRAGI: Final = "--guvenlik-duvari-kurali"

GECTI: Final = "gecti"
KALDI: Final = "kaldi"
UYARI: Final = "uyari"
BILINMIYOR: Final = "bilinmiyor"

MADDE_BASLIKLARI: Final = {
    "etkin": "Kural var ve etkin",
    "program": "Kuraldaki program bu program",
    "port": "Kuraldaki port ayardaki portla aynı",
    "kapsam": "Kural bu ağ profilini kapsıyor",
    "engelleme": "Bu program için engelleme kuralı yok",
}
_MADDE_SIRASI: Final = ("etkin", "program", "port", "kapsam", "engelleme")
_TUM_PROFILLER: Final = frozenset({"Domain", "Private", "Public"})
_HER_YER: Final = frozenset({"any", "*"})

_WINDOWS_BETIGI: Final = r"""
$ad = __KURAL_ADI__
function Normal([string]$yol) {
  if (-not $yol) { return '' }
  return [Environment]::ExpandEnvironmentVariables($yol).Trim().Trim('"').ToLowerInvariant()
}
$hedef = Normal __EXE__
$bulunan = @{}
foreach ($f in @(Get-NetFirewallApplicationFilter -PolicyStore ActiveStore -ErrorAction SilentlyContinue)) {
  if ((Normal ([string]$f.Program)) -eq $hedef) {
    foreach ($k in @($f | Get-NetFirewallRule -ErrorAction SilentlyContinue)) { $bulunan[[string]$k.Name] = $k }
  }
}
foreach ($k in @(Get-NetFirewallRule -PolicyStore ActiveStore -DisplayName $ad -ErrorAction SilentlyContinue)) {
  $bulunan[[string]$k.Name] = $k
}
$kurallar = @($bulunan.Values | ForEach-Object {
  $k = $_
  $p = $k | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  $a = $k | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue
  $u = $k | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
  [pscustomobject]@{
    ad = [string]$k.DisplayName; etkin = ([string]$k.Enabled -eq 'True');
    eylem = [string]$k.Action; yon = [string]$k.Direction; profil = [string]$k.Profile;
    program = [Environment]::ExpandEnvironmentVariables([string]$u.Program);
    protokol = [string]$p.Protocol;
    yerel_port = @($p.LocalPort | ForEach-Object { [string]$_ });
    uzak_adres = @($a.RemoteAddress | ForEach-Object { [string]$_ })
  }
})
$profiller = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue | ForEach-Object { [string]$_.NetworkCategory })
$duvar = @(Get-NetFirewallProfile -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
  ForEach-Object { [pscustomobject]@{ ad = [string]$_.Name; etkin = ([string]$_.Enabled -eq 'True') } })
[pscustomobject]@{ kurallar = $kurallar; ag_profilleri = $profiller; duvar_profilleri = $duvar } |
  ConvertTo-Json -Depth 5 -Compress
"""

_KURAL_YAZ_BETIGI: Final = r"""
$ad = __KURAL_ADI__
$exe = __EXE__
$port = __PORT__
$uzak = @(__UZAK__)
function Normal([string]$yol) {
  if (-not $yol) { return '' }
  return [Environment]::ExpandEnvironmentVariables($yol).Trim().Trim('"').ToLowerInvariant()
}
$hedef = Normal $exe
Get-NetFirewallRule -PolicyStore PersistentStore -DisplayName $ad -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule -ErrorAction Stop
foreach ($f in @(Get-NetFirewallApplicationFilter -PolicyStore PersistentStore -ErrorAction SilentlyContinue)) {
  if ((Normal ([string]$f.Program)) -eq $hedef) {
    $f | Get-NetFirewallRule -ErrorAction SilentlyContinue |
      Where-Object { [string]$_.Direction -eq 'Inbound' -and [string]$_.Action -eq 'Block' } |
      Remove-NetFirewallRule -ErrorAction Stop
  }
}
New-NetFirewallRule -DisplayName $ad -Direction Inbound -Action Allow -Program $exe `
  -Protocol TCP -LocalPort $port -RemoteAddress $uzak -Profile Any -Enabled True | Out-Null
$anahtar = 'HKLM:\__HKLM__'
if (-not (Test-Path $anahtar)) { New-Item -Path $anahtar -Force | Out-Null }
New-ItemProperty -Path $anahtar -Name __DEGER__ -PropertyType DWord -Value $port -Force | Out-Null
'{"tamam": true}'
"""


@dataclass(frozen=True)
class Madde:
    """Beş maddeden biri: kod, başlık, durum (gecti/kaldi/uyari/bilinmiyor), açıklama."""

    kod: str
    durum: str
    aciklama: str

    @property
    def baslik(self) -> str:
        return MADDE_BASLIKLARI[self.kod]

    def sozluk(self) -> dict[str, str]:
        return {
            "kod": self.kod,
            "baslik": self.baslik,
            "durum": self.durum,
            "aciklama": self.aciklama,
        }


@dataclass(frozen=True)
class GuvenlikDuvariDenetimi:
    """Denetimin sonucu. `dinlemeye_izin` katalog sunucusunun okul ağına açılma iznidir."""

    platform: str
    maddeler: tuple[Madde, ...] = ()
    #: Eşleşen ilk izin kuralının gerçek değerleri (programın kendi adlı kuralı öncelikli).
    kural: dict[str, Any] | None = None
    #: Katalog portunu kapsayan BÜTÜN izin kuralları (yoksa programa ait bütün izin
    #: kuralları); BTR notu ve Ağ Doktoru hepsini listeler. İlki `kural`dır.
    kurallar: tuple[dict[str, Any], ...] = ()
    ag_profilleri: tuple[str, ...] = ()
    hata: str | None = None
    #: Linux: "ufw" / "firewalld" / None; etkin mi; çalıştırılacak komut.
    linux: dict[str, Any] = field(default_factory=dict)

    @property
    def windows_mu(self) -> bool:
        return self.platform == "win32"

    @property
    def dinlemeye_izin(self) -> bool:
        """Windows'ta beş madde tutmalı (uyarı engellemez); diğer platformlarda denetim bilgidir."""
        if not self.windows_mu:
            return True
        return (
            self.hata is None
            and tuple(m.kod for m in self.maddeler) == _MADDE_SIRASI
            and all(m.durum in (GECTI, UYARI) for m in self.maddeler)
        )

    def sozluk(self) -> dict[str, Any]:
        return {
            "platform": "windows" if self.windows_mu else "linux",
            "dinlemeye_izin": self.dinlemeye_izin,
            "maddeler": [madde.sozluk() for madde in self.maddeler],
            "kural": self.kural,
            "kurallar": list(self.kurallar),
            "ag_profilleri": list(self.ag_profilleri),
            "hata": self.hata,
            "linux": self.linux,
        }


# ------------------------------------------------------------ yardımcılar


def program_yolu_normal(yol: str) -> str:
    """Windows yol karşılaştırması: ortam değişkeni, tırnak, büyük/küçük harf, ayraç."""
    genis = os.path.expandvars(yol.strip().strip('"'))
    return ntpath.normcase(ntpath.normpath(genis)) if genis else ""


def _profiller(metin: str) -> frozenset[str]:
    """`Profile` alanı: "Any" ya da "Domain, Private" gibi virgüllü liste."""
    parcalar = {p.strip() for p in metin.replace(";", ",").split(",") if p.strip()}
    if not parcalar or "Any" in parcalar:
        return _TUM_PROFILLER
    return frozenset(parcalar & _TUM_PROFILLER)


def _port_kapsar(portlar: Sequence[str], port: int) -> bool:
    for deger in portlar:
        deger = deger.strip()
        if deger.lower() == "any":
            return True
        if "-" in deger:
            alt, _, ust = deger.partition("-")
            if alt.isdigit() and ust.isdigit() and int(alt) <= port <= int(ust):
                return True
        elif deger.isdigit() and int(deger) == port:
            return True
    return False


def _protokol_tcp(protokol: str) -> bool:
    return protokol.strip().upper() in {"TCP", "6", "ANY"}


def _uzak_adresler(kural: Mapping[str, Any]) -> list[str]:
    return [str(a) for a in powershell.liste(kural.get("uzak_adres"))]


def _her_yere_acik(kural: Mapping[str, Any]) -> bool:
    uzak = _uzak_adresler(kural)
    return not uzak or any(a.strip().lower() in _HER_YER for a in uzak)


def _kural_sirasi(kural: Mapping[str, Any]) -> tuple[bool, str, str, tuple[str, ...], str]:
    """Belirli sıra: programın kendi adlı kuralı önce, sonra ada ve değerlere göre."""
    ad = str(kural.get("ad") or "")
    return (
        ad != KURAL_ADI,
        ad.lower(),
        str(kural.get("program") or "").lower(),
        tuple(sorted(a.lower() for a in _uzak_adresler(kural))),
        str(kural.get("profil") or ""),
    )


def _kural_ozeti(kural: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ad": str(kural.get("ad") or ""),
        "program": str(kural.get("program") or ""),
        "yerel_port": [str(p) for p in powershell.liste(kural.get("yerel_port"))],
        "uzak_adres": [str(a) for a in powershell.liste(kural.get("uzak_adres"))],
        "profil": str(kural.get("profil") or ""),
        "etkin": bool(kural.get("etkin")),
    }


# ------------------------------------------------------ Windows: değerlendirme


def degerlendir(
    veri: Any,
    *,
    exe_yolu: str,
    port: int,
    ag_profilleri: Sequence[str] | None = None,
) -> GuvenlikDuvariDenetimi:
    """PowerShell çıktısını beş maddeye çevirir (saf işlev; testte çıktı taklit edilir).

    `ag_profilleri` verilmezse çıktıdaki etkin bağlantı profilleri kullanılır.
    Değerler "Public"/"Private"/"DomainAuthenticated" (Windows adları) ya da
    güvenlik duvarı adları ("Domain") olabilir.
    """
    if not isinstance(veri, dict):
        return _bilinmiyor("Güvenlik duvarı bilgisi beklenen biçimde değil.")
    # PowerShell betiği kuralları hashtable'dan toplar: sıra belirsizdir. Sonuç ve
    # açıklamalar sıradan bağımsız olsun diye kurallar önce sabit sıraya dizilir.
    kurallar = sorted(
        (k for k in powershell.liste(veri.get("kurallar")) if isinstance(k, dict)),
        key=_kural_sirasi,
    )
    ham_profiller = (
        list(ag_profilleri)
        if ag_profilleri is not None
        else [str(p) for p in powershell.liste(veri.get("ag_profilleri"))]
    )
    etkin_profiller = (
        frozenset({"DomainAuthenticated": "Domain"}.get(p, p) for p in ham_profiller if p)
        & _TUM_PROFILLER
    )
    hedef = program_yolu_normal(exe_yolu)

    def gelen(k: Mapping[str, Any]) -> bool:
        return str(k.get("yon") or "").lower() == "inbound"

    def bu_program(k: Mapping[str, Any]) -> bool:
        return bool(hedef) and program_yolu_normal(str(k.get("program") or "")) == hedef

    izinler = [
        k
        for k in kurallar
        if gelen(k)
        and str(k.get("eylem") or "").lower() == "allow"
        and (str(k.get("ad") or "") == KURAL_ADI or bu_program(k))
    ]
    etkin_izinler = [k for k in izinler if k.get("etkin")]
    programli = [k for k in etkin_izinler if bu_program(k)]
    portlu = [
        k
        for k in programli
        if _protokol_tcp(str(k.get("protokol") or ""))
        and _port_kapsar([str(p) for p in powershell.liste(k.get("yerel_port"))], port)
    ]
    engellemeler = [
        k
        for k in kurallar
        if gelen(k)
        and k.get("etkin")
        and str(k.get("eylem") or "").lower() == "block"
        and bu_program(k)
    ]

    maddeler: list[Madde] = []
    # 1 — etkin
    if etkin_izinler:
        maddeler.append(Madde("etkin", GECTI, "Gelen bağlantılara izin veren kural etkin."))
    elif izinler:
        maddeler.append(Madde("etkin", KALDI, "Kural var ama devre dışı. Kuralı güncelleyin."))
    else:
        maddeler.append(
            Madde(
                "etkin",
                KALDI,
                "Bu program için güvenlik duvarı kuralı yok. “Kuralı ekle/güncelle” "
                "düğmesiyle ekleyin (yönetici izni ister).",
            )
        )
    # 2 — program
    if programli:
        maddeler.append(Madde("program", GECTI, "Kural bu programa yazılmış."))
    elif etkin_izinler:
        yol = str(etkin_izinler[0].get("program") or "(yok)")
        maddeler.append(
            Madde(
                "program",
                KALDI,
                f"Kural başka bir program yoluna yazılmış: {yol}. Program taşındıysa ya da "
                "taşınabilir paketten çalışıyorsa kural işlemez.",
            )
        )
    else:
        maddeler.append(Madde("program", KALDI, "Denetlenecek etkin kural yok."))
    # 3 — port
    if portlu:
        maddeler.append(Madde("port", GECTI, f"Kural {port} numaralı TCP portunu kapsıyor."))
    elif programli:
        portlar = (
            ", ".join(str(p) for p in powershell.liste(programli[0].get("yerel_port"))) or "(yok)"
        )
        maddeler.append(
            Madde(
                "port",
                KALDI,
                f"Kuraldaki port ({portlar}) ayardaki portla ({port}) aynı değil. "
                "Kuralı güncelleyin.",
            )
        )
    else:
        maddeler.append(Madde("port", KALDI, "Denetlenecek etkin kural yok."))
    # 4 — kapsam (profil + uzak adres). Windows'ta herhangi bir izin kuralına uyan
    # bağlantı kabul edilir: madde portu kapsayan BÜTÜN kuralların birleşimiyle
    # değerlendirilir (ilk kurala bakmak sonucu kural sırasına bağlardı ve geniş
    # bir ikinci kuralı gizlerdi).
    if not portlu:
        maddeler.append(Madde("kapsam", KALDI, "Denetlenecek etkin kural yok."))
    else:
        maddeler.append(_kapsam_maddesi(portlu, etkin_profiller))
    # 5 — engelleme
    if engellemeler:
        maddeler.append(
            Madde(
                "engelleme",
                KALDI,
                "Bu program için etkin bir engelleme kuralı var; izin kuralından önce gelir. "
                "“Kuralı ekle/güncelle” engelleme kuralını kaldırır.",
            )
        )
    else:
        maddeler.append(Madde("engelleme", GECTI, "Engelleme kuralı yok."))

    gosterilen = portlu or etkin_izinler or izinler
    ozetler = tuple(_kural_ozeti(k) for k in gosterilen)
    return GuvenlikDuvariDenetimi(
        platform="win32",
        maddeler=tuple(maddeler),
        kural=ozetler[0] if ozetler else None,
        kurallar=ozetler,
        ag_profilleri=tuple(sorted(etkin_profiller)),
    )


def _kapsam_maddesi(portlu: Sequence[Mapping[str, Any]], etkin_profiller: frozenset[str]) -> Madde:
    """4. madde: portu kapsayan kuralların BİRLEŞİMİ (profil ve uzak adres)."""
    birlesik_profiller: frozenset[str] = frozenset().union(
        *(_profiller(str(k.get("profil") or "")) for k in portlu)
    )
    eksik = etkin_profiller - birlesik_profiller
    coklu = (
        f"Bu program için {len(portlu)} izin kuralı var; Windows herhangi birine uyan "
        "bağlantıyı kabul eder. "
        if len(portlu) > 1
        else ""
    )
    if eksik:
        return Madde(
            "kapsam",
            KALDI,
            coklu
            + "Kural bu bilgisayarın bağlı olduğu ağ profilini kapsamıyor ("
            + ", ".join(sorted(_profil_adi(p) for p in eksik))
            + "). Kuralı güncelleyin.",
        )
    # Etkin profil okunamadıysa (boş küme) bütün kurallar sayılır: tutucu yön.
    etkili = [
        k
        for k in portlu
        if not etkin_profiller or _profiller(str(k.get("profil") or "")) & etkin_profiller
    ]
    genis = [k for k in etkili if _her_yere_acik(k)]
    if genis:
        adlar = ", ".join(f"“{str(k.get('ad') or '(adsız)')}”" for k in genis)
        aciklama = (
            "Kural bütün uzak adreslere açık."
            if len(portlu) == 1
            else f"Şu kural bütün uzak adreslere açık: {adlar}."
        )
        aciklama = (
            coklu + aciklama + " Yerel alt ağ ve BTR'nin doğruladığı tahta ağı blokları önerilir."
        )
        if any(str(k.get("ad") or "") != KURAL_ADI for k in genis):
            aciklama += (
                " “Kuralı ekle/güncelle” yalnız programın kendi kuralını yazar; bu kuralı "
                "BTR Windows güvenlik duvarı ayarlarından daraltır ya da kaldırır."
            )
        return Madde("kapsam", UYARI, aciklama)
    uzak = list(dict.fromkeys(a for k in etkili for a in _uzak_adresler(k)))
    return Madde(
        "kapsam",
        GECTI,
        coklu + "İzin verilen uzak adresler: " + ", ".join(_adres_adi(a) for a in uzak) + ".",
    )


def _profil_adi(profil: str) -> str:
    return {"Domain": "Etki alanı", "Private": "Özel", "Public": "Genel"}.get(profil, profil)


def _adres_adi(adres: str) -> str:
    return "yerel alt ağ" if adres.strip().lower() == "localsubnet" else adres


def _bilinmiyor(hata: str) -> GuvenlikDuvariDenetimi:
    return GuvenlikDuvariDenetimi(
        platform="win32",
        maddeler=tuple(Madde(kod, BILINMIYOR, "Denetlenemedi.") for kod in _MADDE_SIRASI),
        hata=hata,
    )


def windows_denetle(
    *,
    exe_yolu: str,
    port: int,
    calistirici: powershell.Calistirici | None = None,
) -> GuvenlikDuvariDenetimi:
    """Beş maddeyi Windows'ta okur ve değerlendirir. Okunamazsa fail-closed."""
    betik = _WINDOWS_BETIGI.replace("__KURAL_ADI__", powershell.ps_dizesi(KURAL_ADI)).replace(
        "__EXE__", powershell.ps_dizesi(exe_yolu)
    )
    try:
        veri = powershell.json_calistir(betik, calistirici=calistirici)
    except powershell.PowerShellHatasi as exc:
        logger.warning("Güvenlik duvarı denetimi çalışmadı: %s", exc)
        return _bilinmiyor("Güvenlik duvarı kuralları okunamadı; Ağ Kataloğu okul ağına açılmadı.")
    return degerlendir(veri, exe_yolu=exe_yolu, port=port)


# ---------------------------------------------------------------- Linux


#: `.deb` paketinin bıraktığı tanımlar (packaging/linux/). Taşınabilir arşivde yoktur.
UFW_PROFIL_ADI: Final = "Kutuphane Defteri"
UFW_PROFILI: Final = Path("/etc/ufw/applications.d/kutuphane-defteri")
FIREWALLD_SERVIS_ADI: Final = "kutuphane-defteri"
FIREWALLD_SERVISLERI: Final = (
    Path("/usr/lib/firewalld/services/kutuphane-defteri.xml"),
    Path("/etc/firewalld/services/kutuphane-defteri.xml"),
)
#: Kaynak bloğu bilinmiyorsa komutta BTR'nin dolduracağı yer tutucu.
KAYNAK_YER_TUTUCU: Final = "<okul-agi-blogu>"


def kaynak_bloklari(bloklar: Sequence[str]) -> list[str]:
    """Linux komutunun kaynak blokları: geçerli IPv4 ağları, sırası korunur, tekrarsız.

    Windows kuralının `LocalSubnet` + tahta ağı bloklarının karşılığıdır; "her
    yer" ve /16'dan geniş blok komuta girmez (GA-6: RFC1918'in tamamı açılmaz).
    """
    sonuc: list[str] = []
    for ham in bloklar:
        try:
            ag = ipaddress.IPv4Network(str(ham).strip(), strict=False)
        except ValueError:
            continue
        if ag.prefixlen < 16 or str(ag) in sonuc:
            continue
        sonuc.append(str(ag))
    return sonuc


def linux_komutu(arac: str, *, port: int, bloklar: Sequence[str], tanim_var: bool) -> str:
    """BTR'nin çalıştıracağı KAYNAK SINIRLI komut (her blok ayrı satır).

    Kapsamsız `ufw allow <profil>` ya da `--add-service` katalogu her kaynağa
    (MEB WAN'ındaki başka kurumlar dahil) açardı; Windows kuralı gibi yalnız
    yerel alt ağ ve BTR'nin doğruladığı tahta ağı blokları açılır. Paketin
    tanımı yoksa (taşınabilir arşiv) ya da port değiştiyse port temelli yazılır.
    """
    kaynaklar = list(bloklar) or [KAYNAK_YER_TUTUCU]
    if arac == "ufw":
        hedef = f"app '{UFW_PROFIL_ADI}'" if tanim_var else f"port {int(port)} proto tcp"
        return "\n".join(f"sudo ufw allow from {b} to any {hedef}" for b in kaynaklar)
    hizmet = (
        f'service name="{FIREWALLD_SERVIS_ADI}"'
        if tanim_var
        else f'port port="{int(port)}" protocol="tcp"'
    )
    satirlar = [
        "sudo firewall-cmd --permanent --add-rich-rule="
        f'\'rule family="ipv4" source address="{b}" {hizmet} accept\''
        for b in kaynaklar
    ]
    satirlar.append("sudo firewall-cmd --reload")
    return "\n".join(satirlar)


def linux_durumu(
    *,
    port: int,
    bloklar: Sequence[str] = (),
    ufw_conf: Path = Path("/etc/ufw/ufw.conf"),
    ufw_profili: Path = UFW_PROFILI,
    firewalld_servisleri: Sequence[Path] = FIREWALLD_SERVISLERI,
    which: Callable[[str], str | None] = shutil.which,
    firewalld_etkin: Callable[[], bool | None] | None = None,
) -> GuvenlikDuvariDenetimi:
    """ufw / firewalld durumu (yalnız bilgi; kural açılmaz, dinleme engellenmez).

    `bloklar`: bu bilgisayarın yerel alt ağları + tahta ağı blokları (çağıran
    verir); komut yalnız bunlara izin verir.
    """
    varsayilan = port == 8765
    kaynaklar = kaynak_bloklari(bloklar)
    if which("ufw") is not None:
        etkin: bool | None = None
        try:
            for satir in ufw_conf.read_text(encoding="utf-8").splitlines():
                if satir.strip().upper().startswith("ENABLED="):
                    etkin = satir.split("=", 1)[1].strip().strip('"').lower() == "yes"
        except OSError:
            etkin = None
        tanim = varsayilan and ufw_profili.is_file()
        return GuvenlikDuvariDenetimi(
            platform="linux",
            linux={
                "arac": "ufw",
                "etkin": etkin,
                "komut": linux_komutu("ufw", port=port, bloklar=kaynaklar, tanim_var=tanim),
                "bloklar": kaynaklar,
                "tanim_var": ufw_profili.is_file(),
            },
        )
    if which("firewall-cmd") is not None:
        etkin = (firewalld_etkin or _firewalld_etkin)()
        servis_var = any(yol.is_file() for yol in firewalld_servisleri)
        return GuvenlikDuvariDenetimi(
            platform="linux",
            linux={
                "arac": "firewalld",
                "etkin": etkin,
                "komut": linux_komutu(
                    "firewalld", port=port, bloklar=kaynaklar, tanim_var=varsayilan and servis_var
                ),
                "bloklar": kaynaklar,
                "tanim_var": servis_var,
            },
        )
    return GuvenlikDuvariDenetimi(
        platform="linux",
        linux={"arac": None, "etkin": None, "komut": "", "bloklar": kaynaklar, "tanim_var": False},
    )


def _firewalld_etkin() -> bool | None:
    yol = shutil.which("systemctl")
    if yol is None:
        return None
    try:
        sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar
            [yol, "is-active", "--quiet", "firewalld"], capture_output=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sonuc.returncode == 0


# ------------------------------------------------------------------ giriş


def denetle(
    *,
    port: int,
    exe_yolu: str | None = None,
    bloklar: Sequence[str] = (),
    platform: str = sys.platform,
    windows: Callable[..., GuvenlikDuvariDenetimi] | None = None,
    linux: Callable[..., GuvenlikDuvariDenetimi] | None = None,
) -> GuvenlikDuvariDenetimi:
    """Platforma göre denetim. Windows dışında sonuç bilgidir (`dinlemeye_izin` doğru).

    `bloklar` yalnız Linux komutunun kaynaklarıdır (Windows'ta kural `LocalSubnet`
    ve kuraldaki bloklarla kendisi sınırlıdır).
    """
    if platform == "win32":
        return (windows or windows_denetle)(exe_yolu=exe_yolu or sys.executable, port=port)
    if platform.startswith("linux"):
        return (linux or linux_durumu)(port=port, bloklar=bloklar)
    return GuvenlikDuvariDenetimi(platform=platform)


# --------------------------------------------------------- kural yazma (UAC)


def uzak_adresleri_dogrula(adresler: Sequence[str]) -> list[str]:
    """Kurala girecek uzak adresler: `LocalSubnet` + geçerli IPv4 blokları.

    "Her yer" (`Any`, `0/0`) ve yerel alt ağdan geniş RFC1918 blokları KABUL
    EDİLMEZ (GA-6: MEB WAN'ındaki başka kurum adresleri de özel aralıktadır).
    Geçersiz değer `ValueError` yükseltir.
    """
    sonuc = [YEREL_ALT_AG]
    for ham in adresler:
        deger = ham.strip()
        if not deger or deger.lower() == YEREL_ALT_AG.lower():
            continue
        try:
            ag = ipaddress.IPv4Network(deger, strict=False)
        except ValueError as exc:
            raise ValueError(f"Geçersiz ağ bloğu: {deger}") from exc
        if ag.prefixlen < 16:
            raise ValueError(
                f"Ağ bloğu çok geniş: {deger}. Yalnız okulun BTR'sinin doğruladığı "
                "dar bloklar (en geniş /16) eklenir."
            )
        if str(ag) not in sonuc:
            sonuc.append(str(ag))
    return sonuc


def kural_yaz_betigi(*, exe_yolu: str, port: int, uzak_adresler: Sequence[str]) -> str:
    """Yükseltilmiş kipte koşan PowerShell betiği (değerler güvenli gömülür)."""
    if not 1 <= port <= 65535:
        raise ValueError(f"Geçersiz port: {port}")
    uzak = ",".join(powershell.ps_dizesi(a) for a in uzak_adresleri_dogrula(uzak_adresler))
    return (
        _KURAL_YAZ_BETIGI.replace("__KURAL_ADI__", powershell.ps_dizesi(KURAL_ADI))
        .replace("__EXE__", powershell.ps_dizesi(exe_yolu))
        .replace("__PORT__", str(int(port)))
        .replace("__UZAK__", uzak)
        .replace("__HKLM__", HKLM_ANAHTARI)
        .replace("__DEGER__", HKLM_PORT_DEGERI)
    )


def kural_yaz(
    *,
    exe_yolu: str,
    port: int,
    uzak_adresler: Sequence[str],
    calistirici: powershell.Calistirici | None = None,
) -> bool:
    """YÜKSELTİLMİŞ süreçte: kuralı yeniden yazar, engellemeleri kaldırır, HKLM portu yazar."""
    betik = kural_yaz_betigi(exe_yolu=exe_yolu, port=port, uzak_adresler=uzak_adresler)
    try:
        sonuc = powershell.json_calistir(betik, calistirici=calistirici)
    except powershell.PowerShellHatasi:
        return False
    return isinstance(sonuc, dict) and sonuc.get("tamam") is True


def uac_argumanlari(*, port: int, uzak_adresler: Sequence[str]) -> list[str]:
    """Yükseltilmiş kipin komut satırı (UAC isteminde görünür; kişisel veri yok)."""
    argumanlar = [UAC_BAYRAGI, "--port", str(int(port))]
    for adres in uzak_adresleri_dogrula(uzak_adresler)[1:]:
        argumanlar += ["--uzak-adres", adres]
    return argumanlar


YukseltilmisCalistirici = Callable[[str, Sequence[str]], int | None]


def _shell_execute_runas(exe: str, argumanlar: Sequence[str]) -> int | None:
    """ShellExecuteExW "runas" + bekleme; çıkış kodu, reddedilirse `None`."""
    import ctypes
    from ctypes import wintypes

    class _ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    see_mask_nocloseprocess = 0x00000040
    bilgi = _ShellExecuteInfo()
    bilgi.cbSize = ctypes.sizeof(bilgi)
    bilgi.fMask = see_mask_nocloseprocess
    bilgi.lpVerb = "runas"
    bilgi.lpFile = exe
    bilgi.lpParameters = subprocess.list2cmdline(list(argumanlar))
    bilgi.nShow = 0
    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if not shell32.ShellExecuteExW(ctypes.byref(bilgi)):
        return None  # kullanıcı UAC'yi reddetti ya da başlatılamadı
    try:
        kernel32.WaitForSingleObject(bilgi.hProcess, 120_000)
        kod = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(bilgi.hProcess, ctypes.byref(kod)):
            return None
        return int(kod.value)
    finally:
        kernel32.CloseHandle(bilgi.hProcess)


def kural_guncelle_uac(
    *,
    port: int,
    uzak_adresler: Sequence[str],
    platform: str = sys.platform,
    paketli: bool | None = None,
    exe_yolu: str | None = None,
    calistirici: YukseltilmisCalistirici | None = None,
) -> tuple[bool, str]:
    """Kuralı UAC ile günceller: (başarılı mı, Türkçe ileti)."""
    if platform != "win32":
        return False, "Güvenlik duvarı kuralı yalnız Windows'ta programdan yazılır."
    if not (getattr(sys, "frozen", False) if paketli is None else paketli):
        return False, "Kural yalnız kurulu programdan yazılır (geliştirme ortamı)."
    try:
        argumanlar = uac_argumanlari(port=port, uzak_adresler=uzak_adresler)
    except ValueError as exc:
        return False, str(exc)
    kod = (calistirici or _shell_execute_runas)(exe_yolu or sys.executable, argumanlar)
    if kod is None:
        return False, "Yönetici izni verilmedi; kural değiştirilmedi."
    if kod != 0:
        return False, "Kural yazılamadı. Okulun BTR'sinden yardım isteyin."
    return True, "Güvenlik duvarı kuralı güncellendi."


def yukseltilmis_kip(argv: Sequence[str], *, exe_yolu: str | None = None) -> int:
    """`--guvenlik-duvari-kurali --port N [--uzak-adres CIDR]...` — 0 başarı, 1 hata.

    Pencere, kilit, veri dizini ve günlük AÇMAZ (modül başlığı).
    """
    port: int | None = None
    uzak: list[str] = []
    kalan = list(argv)
    try:
        while kalan:
            bayrak = kalan.pop(0)
            if bayrak == UAC_BAYRAGI:
                continue
            if bayrak == "--port":
                port = int(kalan.pop(0))
            elif bayrak == "--uzak-adres":
                uzak.append(kalan.pop(0))
            else:
                return 1
    except (IndexError, ValueError):
        return 1
    if port is None:
        return 1
    try:
        return (
            0
            if kural_yaz(exe_yolu=exe_yolu or sys.executable, port=port, uzak_adresler=uzak)
            else 1
        )
    except ValueError:
        return 1
