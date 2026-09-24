"""Ağ Kataloğunun paket tarafı (tasarım §4.5, §5.7): kurucu görevleri, Pardus dosyaları.

Inno betiği Docker'da derlenemez (ISCC yerelde ve CI'ın Windows koşusunda
derler); burada metin düzeyinde sabitlenen kurallar:

* güvenlik duvarı görevi: İLK kurulumda eski gelen kuralları silip izin kuralını
  ekler; kural VARSA (güncelleme kipi) ikisini de atlar; kaldırmada siler;
  port HKLM'den okunur ve güncellemede HKLM değeri korunur;
* netsh ÇIKTISI ayrıştırılmaz (yalnız çıkış kodu);
* otomatik başlatma görevi `runasoriginaluser` ile masa hesabına yazılır,
  tetik yalnız o hesabın oturum açılışıdır;
* kimlik sabitleri programla birebir aynıdır (§2.3);
* Pardus paketi ufw uygulama profilini ve firewalld servis tanımını bırakır,
  kuralı açmaz.
"""

from __future__ import annotations

import configparser
import re
import xml.etree.ElementTree as ET  # noqa: S405 — depodaki sabit dosya okunur
from pathlib import Path

from desktop import guvenlik_duvari
from desktop.katalog_server import DEFAULT_PORT

PAKET = Path(__file__).resolve().parents[1]
ISS = (PAKET / "windows" / "kutuphane-defteri.iss").read_text(encoding="utf-8")
GOREV = PAKET / "windows" / "gorev-kur.ps1"
UFW = PAKET / "linux" / "ufw-kutuphane-defteri"
FIREWALLD = PAKET / "linux" / "firewalld-kutuphane-defteri.xml"
BUILD_SH = (PAKET / "linux" / "build.sh").read_text(encoding="utf-8")


def _kod_bolumu() -> str:
    return ISS.split("[Code]", 1)[1]


def _islev(ad: str) -> str:
    kod = _kod_bolumu()
    bas = kod.index(f"procedure {ad}")
    son = kod.index("\nend;", bas)
    return kod[bas:son]


# ------------------------------------------------------------ kimlik sabitleri


def test_kurucu_kimlik_sabitleri_programla_ayni() -> None:
    assert f'#define KuralAdi "{guvenlik_duvari.KURAL_ADI}"' in ISS
    assert f'#define HklmAnahtari "{guvenlik_duvari.HKLM_ANAHTARI}"' in ISS
    assert f'#define HklmPortDegeri "{guvenlik_duvari.HKLM_PORT_DEGERI}"' in ISS
    assert f'#define VarsayilanKatalogPortu "{DEFAULT_PORT}"' in ISS


# ---------------------------------------------------------- güvenlik duvarı


def test_guvenlik_duvari_gorevi_sunulur() -> None:
    assert re.search(
        r'Name: "katalogizni"; Description: "Yerel ağdan katalog taramasına izin ver', ISS
    )


def test_ilk_kurulumda_eski_kurallar_silinir_sonra_izin_eklenir() -> None:
    kur = _islev("GuvenlikDuvariKuraliniKur")

    sil = kur.index("delete rule name=all dir=in program=")
    ekle = kur.index("add rule name=")
    assert sil < ekle
    assert "action=allow" in kur
    assert "protocol=TCP localport=' + IntToStr(KatalogPortu)" in kur
    assert "remoteip=LocalSubnet profile=domain,private,public enable=yes" in kur


def test_guncelleme_kipinde_kurala_dokunulmaz() -> None:
    """EK-29: kural varsa silme ve ekleme ATLANIR (değiştirilmiş port, BTR blokları)."""
    kur = _islev("GuvenlikDuvariKuraliniKur")

    denetim = kur.index("if KatalogKuraliVar then")
    assert denetim < kur.index("delete rule")
    assert "Exit;" in kur[denetim : kur.index("delete rule")]


def test_netsh_ciktisi_ayristirilmaz() -> None:
    """GA-5: yalnız çıkış kodu okunur; netsh'in metin çıktısı hiç yakalanmaz."""
    kod = _kod_bolumu()

    assert "ExecAndCaptureOutput" not in kod
    assert "show rule" in kod
    assert re.search(r"KatalogKuraliVar: Boolean;\s*begin\s*Result := Netsh\(.*\) = 0;", kod)


def test_port_hklmden_okunur_ve_guncellemede_korunur() -> None:
    assert "RegQueryDWordValue(HKLM, '{#HklmAnahtari}', '{#HklmPortDegeri}', Deger)" in ISS
    kayit = next(satir for satir in ISS.splitlines() if satir.startswith("Root: HKLM"))
    assert "createvalueifdoesntexist" in kayit
    assert "uninsdeletekey" in kayit


def test_kaldirmada_kural_silinir() -> None:
    kaldir = _islev("CurUninstallStepChanged")

    assert "usUninstall" in kaldir
    assert 'delete rule name="{#KuralAdi}"' in kaldir


def _bolumler() -> dict[str, list[str]]:
    """.iss'i bölümlere ayırır; ön işlemci (`#if/#else/#endif`) dalları ayrı değil.

    İki dalın satırları da bulunduğu bölüme sayılır: `#if FileExists(...)` doğru
    çıktığında (sürüm derlemesi WebView2 kurucusunu indirir) satır hangi başlığın
    altındaysa ISCC onu o bölümde okur.
    """
    bolumler: dict[str, list[str]] = {}
    gecerli = ""
    for satir in _iss_kod_oncesi().splitlines():
        basi = re.fullmatch(r"\[(\w+)\]", satir.strip())
        if basi:
            gecerli = basi.group(1)
            bolumler.setdefault(gecerli, [])
            continue
        bolumler.setdefault(gecerli, []).append(satir)
    return bolumler


def _iss_kod_oncesi() -> str:
    return ISS.split("\n[Code]\n", 1)[0]


def test_iss_her_satir_kendi_bolumunde() -> None:
    """F5 düzeltmesi: [Registry] WebView2 `Source:` satırının önüne girmişti.

    `#if FileExists(...)` doğru çıkınca `Source:` satırı [Registry]'ye düşer ve
    ISCC derlemeyi kırar; dosya yoksa derleme geçer, hata sürüm derlemesinde
    patlar. Bu yüzden iki dalın satırları da doğru bölümde olmalıdır.
    """
    bolumler = _bolumler()
    for bolum, satirlar in bolumler.items():
        for satir in satirlar:
            s = satir.strip()
            if s.startswith("Source:"):
                assert bolum == "Files", f"`Source:` satırı [{bolum}] altında: {s}"
            if s.startswith("Root:"):
                assert bolum == "Registry", f"`Root:` satırı [{bolum}] altında: {s}"
    assert any("{#WebView2Setup}" in s for s in bolumler["Files"])
    assert any(s.startswith("Root: HKLM") for s in bolumler["Registry"])


def test_kurucu_appmutex_kullanmaz() -> None:
    assert not any(satir.strip().startswith("AppMutex") for satir in ISS.splitlines())


# -------------------------------------------------------- otomatik başlatma


def test_otomatik_baslatma_gorevi_masa_hesabina_yazilir() -> None:
    run = ISS.split("\n[Run]\n", 1)[1].split("\n[UninstallRun]\n", 1)[0]
    girdiler = [g for g in re.split(r"\n(?=Filename:)", run) if "gorev-kur.ps1" in g]

    assert len(girdiler) == 2
    assert all("runasoriginaluser" in g for g in girdiler)
    assert "Tasks: otobaslat and not otobaslat\\tepside" in girdiler[0]
    assert '-Tepside"' in girdiler[1] and "Tasks: otobaslat\\tepside" in girdiler[1]
    assert 'Source: "gorev-kur.ps1"' in ISS
    assert '/Delete /TN ""{#GorevAdi}"" /F' in ISS  # kaldırmada görev silinir


def test_gorev_betigi_yalniz_bu_hesabin_oturum_acilisinda_tetiklenir() -> None:
    metin = GOREV.read_text(encoding="utf-8")

    assert "New-ScheduledTaskTrigger -AtLogOn -User $kullanici" in metin
    assert "-RunLevel Limited" in metin
    assert "--tepside" in metin
    assert "RestartCount" not in metin  # Çık ile kapanan program geri açılmaz
    assert GOREV.read_bytes().isascii()


# ------------------------------------------------------------------ Pardus


def test_ufw_uygulama_profili() -> None:
    profil = configparser.ConfigParser()
    profil.read(UFW, encoding="utf-8")

    assert profil.sections() == ["Kutuphane Defteri"]
    assert profil["Kutuphane Defteri"]["ports"] == f"{DEFAULT_PORT}/tcp"
    assert UFW.read_bytes().isascii()
    assert profil.sections()[0] == guvenlik_duvari.UFW_PROFIL_ADI
    # Ağ Doktoru'nun gösterdiği komut bu profil adını KAYNAK SINIRIYLA kullanır.
    denetim = guvenlik_duvari.linux_durumu(
        port=DEFAULT_PORT,
        bloklar=["192.168.10.0/24"],
        ufw_profili=UFW,
        which=lambda ad: "/usr/sbin/ufw",
    )
    assert denetim.linux["komut"] == (
        "sudo ufw allow from 192.168.10.0/24 to any app 'Kutuphane Defteri'"
    )
    # Profil açıklaması da kaynaksız komut önermez (GA-6).
    aciklama = profil["Kutuphane Defteri"]["description"]
    assert "from" in aciklama and "ufw allow 'Kutuphane Defteri'" not in aciklama


def test_firewalld_servis_tanimi() -> None:
    kok = ET.parse(FIREWALLD).getroot()  # noqa: S314 — depodaki sabit dosya

    assert kok.tag == "service"
    (port,) = kok.findall("port")
    assert port.attrib == {"protocol": "tcp", "port": str(DEFAULT_PORT)}
    assert FIREWALLD.read_bytes().isascii()
    # Paket dosyayı `kutuphane-defteri.xml` adıyla kurar; servis adı dosya adıdır.
    assert guvenlik_duvari.FIREWALLD_SERVISLERI[0].stem == guvenlik_duvari.FIREWALLD_SERVIS_ADI
    denetim = guvenlik_duvari.linux_durumu(
        port=DEFAULT_PORT,
        bloklar=["192.168.10.0/24"],
        firewalld_servisleri=(FIREWALLD,),
        which=lambda ad: "/usr/bin/firewall-cmd" if ad == "firewall-cmd" else None,
        firewalld_etkin=lambda: True,
    )
    assert (
        'source address="192.168.10.0/24" service name="kutuphane-defteri"'
        in (denetim.linux["komut"])
    )


def test_deb_paketi_iki_dosyayi_birakir_ama_kural_acmaz() -> None:
    assert '"$DEB_AGACI/etc/ufw/applications.d/kutuphane-defteri"' in BUILD_SH
    assert '"$DEB_AGACI/usr/lib/firewalld/services/kutuphane-defteri.xml"' in BUILD_SH
    bakim = (PAKET / "linux" / "postinst").read_text(encoding="utf-8")
    assert "ufw allow" not in bakim and "firewall-cmd" not in bakim
