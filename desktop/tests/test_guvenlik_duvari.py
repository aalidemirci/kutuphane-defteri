"""Güvenlik duvarı: beş maddelik denetim, kural yazma ve UAC yardımcısı (tasarım §5.7).

Denetim YAPILANDIRILMIŞ veriyle yapılır (`Get-NetFirewallRule -PolicyStore
ActiveStore` + filtreler → JSON); netsh ayrıştırılmaz. PowerShell Docker'da
yoktur: çıktı TAKLİT edilir (§5.10-10 "denetim çıktısı taklit edilir"). Katalog
sunucusunun bu sonuca göre okul ağında DİNLEMEDİĞİ `test_katalog_kontrol.py`
ve `test_katalog_server.py`'dedir.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from desktop import guvenlik_duvari as gd
from desktop import powershell

EXE = r"C:\Program Files\Kütüphane Defteri\kutuphane-defteri.exe"
PORT = 8765


def _kural(**degisiklik: Any) -> dict[str, Any]:
    kural: dict[str, Any] = {
        "ad": gd.KURAL_ADI,
        "etkin": True,
        "eylem": "Allow",
        "yon": "Inbound",
        "profil": "Domain, Private, Public",
        "program": EXE,
        "protokol": "TCP",
        "yerel_port": ["8765"],
        "uzak_adres": ["LocalSubnet"],
    }
    kural.update(degisiklik)
    return kural


def _veri(*kurallar: dict[str, Any], profiller: Sequence[str] = ("Public",)) -> dict[str, Any]:
    return {
        "kurallar": list(kurallar),
        "ag_profilleri": list(profiller),
        "duvar_profilleri": [{"ad": "Public", "etkin": True}],
    }


def _durumlar(denetim: gd.GuvenlikDuvariDenetimi) -> dict[str, str]:
    return {m.kod: m.durum for m in denetim.maddeler}


# ------------------------------------------------------------------ beş madde


def test_bes_madde_gecince_dinlemeye_izin_var() -> None:
    denetim = gd.degerlendir(_veri(_kural()), exe_yolu=EXE, port=PORT)

    assert [m.kod for m in denetim.maddeler] == [
        "etkin",
        "program",
        "port",
        "kapsam",
        "engelleme",
    ]
    assert set(_durumlar(denetim).values()) == {gd.GECTI}
    assert denetim.dinlemeye_izin is True
    assert denetim.kural is not None
    assert denetim.kural["uzak_adres"] == ["LocalSubnet"]
    assert "yerel alt ağ" in denetim.maddeler[3].aciklama


def test_kural_yoksa_dinlemez() -> None:
    denetim = gd.degerlendir(_veri(), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["etkin"] == gd.KALDI
    assert "Kuralı ekle" in denetim.maddeler[0].aciklama
    assert denetim.dinlemeye_izin is False
    assert denetim.kural is None


def test_kural_devre_disiysa_dinlemez() -> None:
    denetim = gd.degerlendir(_veri(_kural(etkin=False)), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["etkin"] == gd.KALDI
    assert "devre dışı" in denetim.maddeler[0].aciklama
    assert denetim.dinlemeye_izin is False


def test_program_yolu_farkliysa_dinlemez() -> None:
    """Taşınabilir paket ya da taşınmış kurulum: kural başka yola yazılmış (GA-5)."""
    denetim = gd.degerlendir(
        _veri(_kural(program=r"D:\eski\kutuphane-defteri.exe")), exe_yolu=EXE, port=PORT
    )

    assert _durumlar(denetim)["etkin"] == gd.GECTI
    assert _durumlar(denetim)["program"] == gd.KALDI
    assert r"D:\eski" in denetim.maddeler[1].aciklama
    assert denetim.dinlemeye_izin is False


def test_program_yolu_karsilastirmasi_buyuk_kucuk_harf_ve_tirnaktan_bagimsiz() -> None:
    denetim = gd.degerlendir(
        _veri(_kural(program='"' + EXE.upper() + '"')), exe_yolu=EXE, port=PORT
    )

    assert _durumlar(denetim)["program"] == gd.GECTI


def test_port_ayarla_ayni_degilse_dinlemez() -> None:
    denetim = gd.degerlendir(_veri(_kural(yerel_port=["9000"])), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["port"] == gd.KALDI
    assert "9000" in denetim.maddeler[2].aciklama and "8765" in denetim.maddeler[2].aciklama
    assert denetim.dinlemeye_izin is False


@pytest.mark.parametrize("portlar", [["8765"], ["80", "8765"], ["8000-9000"], ["Any"]])
def test_port_kapsama_bicimleri(portlar: list[str]) -> None:
    denetim = gd.degerlendir(_veri(_kural(yerel_port=portlar)), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["port"] == gd.GECTI


def test_udp_kurali_tcp_portunu_kapsamaz() -> None:
    denetim = gd.degerlendir(_veri(_kural(protokol="UDP")), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["port"] == gd.KALDI


def test_profil_etkin_agi_kapsamiyorsa_dinlemez() -> None:
    """Okul ağları çoğu zaman "Genel" görünür (§5.7): yalnız Özel profilli kural yetmez."""
    denetim = gd.degerlendir(
        _veri(_kural(profil="Private"), profiller=("Public",)), exe_yolu=EXE, port=PORT
    )

    assert _durumlar(denetim)["kapsam"] == gd.KALDI
    assert "Genel" in denetim.maddeler[3].aciklama
    assert denetim.dinlemeye_izin is False


@pytest.mark.parametrize("profil", ["Any", "Domain, Private, Public"])
def test_tum_profiller_her_agi_kapsar(profil: str) -> None:
    denetim = gd.degerlendir(
        _veri(_kural(profil=profil), profiller=("DomainAuthenticated", "Public")),
        exe_yolu=EXE,
        port=PORT,
    )

    assert _durumlar(denetim)["kapsam"] == gd.GECTI
    assert denetim.ag_profilleri == ("Domain", "Public")


def test_uzak_adres_her_yer_ise_uyari_ama_dinlemeyi_engellemez() -> None:
    denetim = gd.degerlendir(_veri(_kural(uzak_adres=["Any"])), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["kapsam"] == gd.UYARI
    assert denetim.dinlemeye_izin is True


def test_tahta_agi_blogu_kapsamda_gosterilir() -> None:
    denetim = gd.degerlendir(
        _veri(_kural(uzak_adres=["LocalSubnet", "10.20.30.0/255.255.254.0"])),
        exe_yolu=EXE,
        port=PORT,
    )

    assert _durumlar(denetim)["kapsam"] == gd.GECTI
    assert "10.20.30.0/255.255.254.0" in denetim.maddeler[3].aciklama


def test_engelleme_kurali_varsa_dinlemez() -> None:
    """Eski iletişim kutusunun bıraktığı "engelle" kuralı izinden önce gelir (§5.7)."""
    engel = _kural(ad="kutuphane-defteri.exe", eylem="Block", profil="Public")

    denetim = gd.degerlendir(_veri(_kural(), engel), exe_yolu=EXE, port=PORT)

    assert _durumlar(denetim)["engelleme"] == gd.KALDI
    assert denetim.dinlemeye_izin is False


def test_devre_disi_ya_da_giden_engelleme_kurali_sayilmaz() -> None:
    kapali_engel = _kural(ad="x", eylem="Block", etkin=False)
    giden_engel = _kural(ad="y", eylem="Block", yon="Outbound")

    denetim = gd.degerlendir(_veri(_kural(), kapali_engel, giden_engel), exe_yolu=EXE, port=PORT)

    assert denetim.dinlemeye_izin is True


def test_btr_nin_baska_adla_ekledigi_program_kurali_da_kabul_edilir() -> None:
    denetim = gd.degerlendir(_veri(_kural(ad="Okul Katalog İzni")), exe_yolu=EXE, port=PORT)

    assert denetim.dinlemeye_izin is True


# ------------------------------------------- birden çok izin kuralı (F5 düzeltmesi)

_DAR = _kural()
_GENIS = _kural(ad="kutuphane-defteri.exe", yerel_port=["Any"], uzak_adres=["Any"], profil="Any")


def _iki_sirada(*kurallar: dict[str, Any], **kw: Any) -> list[gd.GuvenlikDuvariDenetimi]:
    """PowerShell kuralları hashtable'dan toplar: sıra belirsizdir. İki sırayı da dener."""
    return [
        gd.degerlendir(_veri(*sira, **kw), exe_yolu=EXE, port=PORT)
        for sira in (kurallar, tuple(reversed(kurallar)))
    ]


def test_ikinci_genis_kural_sira_ne_olursa_olsun_uyari_verir() -> None:
    """Windows herhangi bir izin kuralına uyan bağlantıyı kabul eder: 4. madde birleşimdir.

    Eskiden yalnız ilk kurala bakılırdı; dar kural önce gelirse "Geçti — yerel alt
    ağ" yazılırdı, oysa katalog her adrese açıktı. Sonuç kural sırasına bağlıydı.
    """
    birinci, ikinci = _iki_sirada(_DAR, _GENIS)

    for denetim in (birinci, ikinci):
        kapsam = denetim.maddeler[3]
        assert kapsam.durum == gd.UYARI
        assert "2 izin kuralı var" in kapsam.aciklama
        assert "“kutuphane-defteri.exe”" in kapsam.aciklama
        assert "Kuralı ekle/güncelle” yalnız programın kendi kuralını yazar" in kapsam.aciklama
        assert denetim.dinlemeye_izin is True
    assert birinci.maddeler == ikinci.maddeler
    assert birinci.kurallar == ikinci.kurallar
    assert [k["uzak_adres"] for k in birinci.kurallar] == [["LocalSubnet"], ["Any"]]
    # Programın kendi adlı kuralı ilk sıradadır.
    assert birinci.kural is not None and birinci.kural["ad"] == gd.KURAL_ADI
    assert birinci.sozluk()["kurallar"] == list(birinci.kurallar)


def test_iki_dar_kuralin_uzak_adresleri_birlesir() -> None:
    tahta = _kural(ad="Okul Tahta İzni", uzak_adres=["10.20.30.0/255.255.254.0"])

    birinci, ikinci = _iki_sirada(_DAR, tahta)

    assert birinci.maddeler == ikinci.maddeler
    kapsam = birinci.maddeler[3]
    assert kapsam.durum == gd.GECTI
    assert "yerel alt ağ" in kapsam.aciklama and "10.20.30.0/255.255.254.0" in kapsam.aciklama
    assert len(birinci.kurallar) == 2


def test_profil_kapsami_kurallarin_birlesimiyle_olculur() -> None:
    """Etkin profil Genel: yalnız Özel kapsayan kural + Genel kapsayan kural → geçer."""
    ozel = _kural(profil="Private")
    genel = _kural(ad="Okul Genel İzni", profil="Public", uzak_adres=["10.20.30.0/24"])

    for denetim in _iki_sirada(ozel, genel, profiller=("Public",)):
        kapsam = denetim.maddeler[3]
        assert kapsam.durum == gd.GECTI
        # Etkin profile uymayan kuralın uzak adresi "izin verilen" diye yazılmaz.
        assert "10.20.30.0/24" in kapsam.aciklama and "yerel alt ağ" not in kapsam.aciklama


def test_etkin_profile_uymayan_genis_kural_uyari_vermez() -> None:
    """Geniş kural yalnız Özel profilde ve bilgisayar Genel ağdaysa o kural işlemez."""
    genis_ozel = _kural(ad="Özel Ağ İzni", uzak_adres=["Any"], profil="Private")

    for denetim in _iki_sirada(_DAR, genis_ozel, profiller=("Public",)):
        assert denetim.maddeler[3].durum == gd.GECTI


@pytest.mark.parametrize("veri", [None, [], "metin"])
def test_bozuk_veri_bilinmiyor_ve_dinlemez(veri: Any) -> None:
    denetim = gd.degerlendir(veri, exe_yolu=EXE, port=PORT)

    assert set(_durumlar(denetim).values()) == {gd.BILINMIYOR}
    assert denetim.dinlemeye_izin is False


# ------------------------------------------------------- PowerShell çalıştırma


def _betik(argv: Sequence[str]) -> str:
    kodlu = argv[list(argv).index("-EncodedCommand") + 1]
    return base64.b64decode(kodlu).decode("utf-16-le")


def test_windows_denetimi_yapilandirilmis_cmdletleri_kullanir_netsh_kullanmaz() -> None:
    goruldu: list[str] = []

    def calistirici(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        goruldu.append(_betik(argv))
        return 0, json.dumps(_veri(_kural())).encode("utf-8")

    denetim = gd.windows_denetle(exe_yolu=EXE, port=PORT, calistirici=calistirici)

    assert denetim.dinlemeye_izin is True
    (betik,) = goruldu
    assert "Get-NetFirewallRule -PolicyStore ActiveStore" in betik
    assert "Get-NetFirewallApplicationFilter" in betik
    assert "Get-NetFirewallPortFilter" in betik
    assert "Get-NetFirewallAddressFilter" in betik
    assert "ConvertTo-Json" in betik
    assert "netsh" not in betik.lower()
    # Türkçe karakterli program yolu betiğe bozulmadan ve tek tırnak içinde gömülür.
    assert "'" + EXE + "'" in betik


def test_powershell_calismazsa_fail_closed() -> None:
    def calistirici(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        return 1, b""

    denetim = gd.windows_denetle(exe_yolu=EXE, port=PORT, calistirici=calistirici)

    assert denetim.dinlemeye_izin is False
    assert denetim.hata is not None and "okunamadı" in denetim.hata


def test_powershell_json_olmayan_cikti_fail_closed() -> None:
    def calistirici(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        return 0, "Kural Adı: Kutuphane Defteri Katalog".encode()  # yerelleştirilmiş netsh

    assert (
        gd.windows_denetle(exe_yolu=EXE, port=PORT, calistirici=calistirici).dinlemeye_izin is False
    )


def test_ps_dizesi_tek_tirnagi_ikiler() -> None:
    assert powershell.ps_dizesi("O'Neil") == "'O''Neil'"
    betik = gd.kural_yaz_betigi(exe_yolu=r"C:\a'b\x.exe", port=8765, uzak_adresler=[])
    assert r"'C:\a''b\x.exe'" in betik


@pytest.mark.parametrize("tirnak", ["\u2018", "\u2019", "\u201a", "\u201b"])
def test_ps_dizesi_unicode_tek_tirnaklari_da_ikiler(tirnak: str) -> None:
    """F5 düzeltmesi: PowerShell ‘ ’ ‚ ‛ karakterlerini de dize sınırlayıcısı sayar.

    Yalnız ASCII tırnak ikilenirse "C:\\Okul’un…" yolu dizeyi kapatır ve kalanı
    (UAC ile yükseltilmiş kural yazma betiğinde dahil) komut olarak çalışırdı.
    Beklenen çıktı PowerShell'in kendi `EscapeSingleQuotedStringContent` kuralıdır.
    """
    yol = f"C:\\Okul{tirnak}; Write-Output ENJ; {tirnak}\\k.exe"

    assert (
        powershell.ps_dizesi(yol)
        == f"'C:\\Okul{tirnak * 2}; Write-Output ENJ; {tirnak * 2}\\k.exe'"
    )
    betik = gd.kural_yaz_betigi(exe_yolu=yol, port=8765, uzak_adresler=[])
    assert f"$exe = {powershell.ps_dizesi(yol)}" in betik
    # Dizenin içinde tek (ikilenmemiş) tırnak kalmaz: her tırnak çiftlerle gelir.
    ic = powershell.ps_dizesi(yol)[1:-1]
    for parca in re.findall("['\u2018\u2019\u201a\u201b]+", ic):
        assert len(parca) % 2 == 0


def test_powershell_mutlak_yoldan_calistirilir() -> None:
    yol = powershell.powershell_yolu({"SystemRoot": r"C:\Windows"})

    assert yol.replace("\\", "/").endswith("System32/WindowsPowerShell/v1.0/powershell.exe")


def test_powershell_liste_yardimcisi() -> None:
    assert powershell.liste(None) == []
    assert powershell.liste({"a": 1}) == [{"a": 1}]
    assert powershell.liste([1, 2]) == [1, 2]


def test_gercek_calistirici_yoksa_hata_sonuca_doner() -> None:
    """Docker'da powershell.exe yok: çalıştırılamadı hatası istisna değil sınıflı hatadır."""
    with pytest.raises(powershell.PowerShellHatasi):
        powershell.json_calistir("Write-Output 1", zaman_asimi=2.0)


# ------------------------------------------------------------------- Linux


def test_linux_ufw_durumu_bilgidir_ve_dinlemeyi_engellemez(tmp_path: Path) -> None:
    conf = tmp_path / "ufw.conf"
    conf.write_text("ENABLED=yes\nLOGLEVEL=low\n", encoding="utf-8")
    profil = tmp_path / "kutuphane-defteri"
    profil.write_text("[Kutuphane Defteri]\n", encoding="utf-8")

    denetim = gd.linux_durumu(
        port=8765,
        bloklar=["192.168.10.0/24", "10.20.30.0/23"],
        ufw_conf=conf,
        ufw_profili=profil,
        which=lambda ad: f"/usr/sbin/{ad}",
    )

    assert denetim.dinlemeye_izin is True
    assert denetim.maddeler == ()
    assert denetim.linux == {
        "arac": "ufw",
        "etkin": True,
        "komut": "sudo ufw allow from 192.168.10.0/24 to any app 'Kutuphane Defteri'\n"
        "sudo ufw allow from 10.20.30.0/23 to any app 'Kutuphane Defteri'",
        "bloklar": ["192.168.10.0/24", "10.20.30.0/23"],
        "tanim_var": True,
    }


def test_linux_komutu_kaynak_sinirsiz_olmaz(tmp_path: Path) -> None:
    """F5 düzeltmesi: kapsamsız `ufw allow <profil>` katalogu MEB WAN'ına da açardı (GA-6).

    Her satır bir `from <blok>` taşır; blok bilinmiyorsa BTR'nin dolduracağı yer
    tutucu yazılır, kaynaksız komut hiç üretilmez. Geniş ya da geçersiz blok atılır.
    """

    def yalniz(arac: str) -> Callable[[str], str | None]:
        return lambda ad: f"/usr/sbin/{ad}" if ad == arac else None

    for bloklar in ([], ["0.0.0.0/0", "10.0.0.0/8", "abc"], ["192.168.10.7/24"]):
        for arac in ("ufw", "firewall-cmd"):
            denetim = gd.linux_durumu(
                port=8765,
                bloklar=bloklar,
                ufw_conf=tmp_path / "yok.conf",
                ufw_profili=tmp_path / "yok",
                firewalld_servisleri=(),
                which=yalniz(arac),
                firewalld_etkin=lambda: True,
            )
            komutlar = [k for k in denetim.linux["komut"].splitlines() if "--reload" not in k]
            assert komutlar
            for komut in komutlar:
                assert "from " in komut or "source address=" in komut, komut
                assert "0.0.0.0/0" not in komut and "10.0.0.0/8" not in komut
            if bloklar == ["192.168.10.7/24"]:
                assert "192.168.10.0/24" in denetim.linux["komut"]
            elif not denetim.linux["bloklar"]:
                assert gd.KAYNAK_YER_TUTUCU in denetim.linux["komut"]


def test_linux_port_degisince_ya_da_profil_yokken_port_temelli_komut(tmp_path: Path) -> None:
    """Taşınabilir arşivde ufw profili yoktur: profil adlı komut "profile not found" verirdi."""
    profil = tmp_path / "kutuphane-defteri"
    profil.write_text("[Kutuphane Defteri]\n", encoding="utf-8")
    ortak: dict[str, Any] = {
        "bloklar": ["192.168.10.0/24"],
        "ufw_conf": tmp_path / "yok.conf",
        "which": lambda ad: "/usr/sbin/ufw",
    }

    port_degisti = gd.linux_durumu(port=9100, ufw_profili=profil, **ortak)
    profil_yok = gd.linux_durumu(port=8765, ufw_profili=tmp_path / "yok", **ortak)

    assert port_degisti.linux["komut"] == (
        "sudo ufw allow from 192.168.10.0/24 to any port 9100 proto tcp"
    )
    assert port_degisti.linux["etkin"] is None
    assert profil_yok.linux["komut"] == (
        "sudo ufw allow from 192.168.10.0/24 to any port 8765 proto tcp"
    )
    assert profil_yok.linux["tanim_var"] is False


def test_linux_firewalld_zengin_kural_kaynakla(tmp_path: Path) -> None:
    servis = tmp_path / "kutuphane-defteri.xml"
    servis.write_text("<service/>", encoding="utf-8")
    ortak: dict[str, Any] = {
        "bloklar": ["192.168.10.0/24"],
        "which": lambda ad: "/usr/bin/firewall-cmd" if ad == "firewall-cmd" else None,
        "firewalld_etkin": lambda: True,
    }

    tanimli = gd.linux_durumu(port=8765, firewalld_servisleri=(servis,), **ortak)
    tanimsiz = gd.linux_durumu(port=8765, firewalld_servisleri=(tmp_path / "yok",), **ortak)

    assert tanimli.linux["arac"] == "firewalld"
    assert tanimli.linux["komut"].splitlines() == [
        'sudo firewall-cmd --permanent --add-rich-rule=\'rule family="ipv4" source '
        'address="192.168.10.0/24" service name="kutuphane-defteri" accept\'',
        "sudo firewall-cmd --reload",
    ]
    assert 'port port="8765" protocol="tcp"' in tanimsiz.linux["komut"]
    assert "--add-service" not in tanimli.linux["komut"]
    assert tanimli.dinlemeye_izin is True


def test_linux_arac_yoksa_bilgi_bos() -> None:
    denetim = gd.linux_durumu(port=8765, which=lambda ad: None)

    assert denetim.linux["arac"] is None
    assert denetim.linux["komut"] == ""


def test_platform_secimi() -> None:
    windows = gd.denetle(
        port=PORT,
        exe_yolu=EXE,
        platform="win32",
        windows=lambda **kw: gd.degerlendir(_veri(), **kw),
    )
    linux = gd.denetle(
        port=PORT, platform="linux", linux=lambda **kw: gd.GuvenlikDuvariDenetimi("linux")
    )

    assert windows.dinlemeye_izin is False
    assert linux.dinlemeye_izin is True


def test_sozluk_bicimi() -> None:
    sozluk = gd.degerlendir(_veri(_kural()), exe_yolu=EXE, port=PORT).sozluk()

    assert sozluk["platform"] == "windows"
    assert sozluk["dinlemeye_izin"] is True
    assert [m["kod"] for m in sozluk["maddeler"]] == [
        "etkin",
        "program",
        "port",
        "kapsam",
        "engelleme",
    ]
    assert sozluk["maddeler"][0]["baslik"] == "Kural var ve etkin"


# ------------------------------------------------------------ kural yazma


def test_uzak_adresler_yerel_alt_ag_ile_baslar_ve_dogrulanir() -> None:
    assert gd.uzak_adresleri_dogrula([]) == ["LocalSubnet"]
    assert gd.uzak_adresleri_dogrula(["10.20.30.0/23", " 10.20.30.0/23 ", "LocalSubnet"]) == [
        "LocalSubnet",
        "10.20.30.0/23",
    ]


@pytest.mark.parametrize("blok", ["10.0.0.0/8", "0.0.0.0/0", "172.16.0.0/12", "abc", "10.1.2.3/40"])
def test_genis_ya_da_gecersiz_blok_reddedilir(blok: str) -> None:
    """GA-6: RFC1918'in tamamı açılmaz; "her yer" hiç açılmaz."""
    with pytest.raises(ValueError):
        gd.uzak_adresleri_dogrula([blok])


def test_kural_yazma_betigi_kuralı_yeniden_yazar_engellemeyi_kaldirir_hklm_portu_yazar() -> None:
    betik = gd.kural_yaz_betigi(exe_yolu=EXE, port=9100, uzak_adresler=["10.20.30.0/23"])

    assert "Remove-NetFirewallRule" in betik
    assert "New-NetFirewallRule -DisplayName $ad -Direction Inbound -Action Allow" in betik
    assert "-Protocol TCP -LocalPort $port" in betik
    assert "$port = 9100" in betik
    assert "@('LocalSubnet','10.20.30.0/23')" in betik
    assert "[string]$_.Action -eq 'Block'" in betik
    assert r"HKLM:\SOFTWARE\KutuphaneDefteri" in betik
    assert "KatalogPortu" in betik
    assert "-Profile Any" in betik


@pytest.mark.parametrize("port", [0, 70000])
def test_kural_yazma_gecersiz_portu_reddeder(port: int) -> None:
    with pytest.raises(ValueError):
        gd.kural_yaz_betigi(exe_yolu=EXE, port=port, uzak_adresler=[])


def test_kural_yaz_sonucu() -> None:
    def tamam(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        return 0, b'{"tamam": true}'

    def hata(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
        return 1, b""

    assert gd.kural_yaz(exe_yolu=EXE, port=PORT, uzak_adresler=[], calistirici=tamam) is True
    assert gd.kural_yaz(exe_yolu=EXE, port=PORT, uzak_adresler=[], calistirici=hata) is False


def test_uac_argumanlari() -> None:
    assert gd.uac_argumanlari(port=9100, uzak_adresler=["10.20.30.0/23"]) == [
        "--guvenlik-duvari-kurali",
        "--port",
        "9100",
        "--uzak-adres",
        "10.20.30.0/23",
    ]


def test_uac_ile_guncelleme_dallari() -> None:
    cagrilar: list[tuple[str, list[str]]] = []

    def calistir(kod: int | None) -> Any:
        def c(exe: str, argumanlar: Sequence[str]) -> int | None:
            cagrilar.append((exe, list(argumanlar)))
            return kod

        return c

    ortak: dict[str, Any] = {
        "port": PORT,
        "uzak_adresler": [],
        "platform": "win32",
        "exe_yolu": EXE,
    }
    assert gd.kural_guncelle_uac(**ortak, paketli=True, calistirici=calistir(0)) == (
        True,
        "Güvenlik duvarı kuralı güncellendi.",
    )
    reddedildi = gd.kural_guncelle_uac(**ortak, paketli=True, calistirici=calistir(None))
    assert reddedildi[0] is False and "Yönetici izni verilmedi" in reddedildi[1]
    basarisiz = gd.kural_guncelle_uac(**ortak, paketli=True, calistirici=calistir(1))
    assert basarisiz[0] is False and "yazılamadı" in basarisiz[1]
    assert cagrilar[0] == (EXE, ["--guvenlik-duvari-kurali", "--port", "8765"])

    gelistirme = gd.kural_guncelle_uac(**ortak, paketli=False, calistirici=calistir(0))
    assert gelistirme[0] is False and "kurulu programdan" in gelistirme[1]
    linux = gd.kural_guncelle_uac(port=PORT, uzak_adresler=[], platform="linux")
    assert linux[0] is False
    genis = gd.kural_guncelle_uac(
        port=PORT,
        uzak_adresler=["10.0.0.0/8"],
        platform="win32",
        paketli=True,
        calistirici=calistir(0),
    )
    assert genis[0] is False and "çok geniş" in genis[1]
    assert len(cagrilar) == 3  # geliştirme, Linux ve geniş blok hiç yükseltilmedi


def test_yukseltilmis_kip_argumanlari(monkeypatch: pytest.MonkeyPatch) -> None:
    yazilan: list[dict[str, Any]] = []

    def kural_yaz(**kw: Any) -> bool:
        yazilan.append(kw)
        return True

    monkeypatch.setattr(gd, "kural_yaz", kural_yaz)

    assert (
        gd.yukseltilmis_kip(
            ["--guvenlik-duvari-kurali", "--port", "9100", "--uzak-adres", "10.20.30.0/23"],
            exe_yolu=EXE,
        )
        == 0
    )
    assert yazilan == [{"exe_yolu": EXE, "port": 9100, "uzak_adresler": ["10.20.30.0/23"]}]
    for bozuk in (
        ["--guvenlik-duvari-kurali"],
        ["--guvenlik-duvari-kurali", "--port"],
        ["--guvenlik-duvari-kurali", "--port", "abc"],
        ["--guvenlik-duvari-kurali", "--port", "80", "--bilinmeyen"],
    ):
        assert gd.yukseltilmis_kip(bozuk, exe_yolu=EXE) == 1


def test_yukseltilmis_kip_hatali_blokta_1() -> None:
    assert (
        gd.yukseltilmis_kip(
            ["--guvenlik-duvari-kurali", "--port", "80", "--uzak-adres", "10.0.0.0/8"],
            exe_yolu=EXE,
        )
        == 1
    )


def test_kural_adi_ve_hklm_kimlik_sabitleri() -> None:
    """Tasarım §2.3: kural adı ASCII; kurucu aynı adı ve HKLM değerini kullanır."""
    assert gd.KURAL_ADI == "Kutuphane Defteri Katalog"
    assert gd.KURAL_ADI.isascii()
    iss = (
        Path(__file__).resolve().parents[2] / "packaging" / "windows" / "kutuphane-defteri.iss"
    ).read_text(encoding="utf-8")
    assert gd.KURAL_ADI in iss
    assert gd.HKLM_ANAHTARI in iss
    assert gd.HKLM_PORT_DEGERI in iss
