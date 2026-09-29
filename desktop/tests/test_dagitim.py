"""Dağıtım türü (KB-2, 28.09.2026): kurulu `.deb` mi, taşınabilir arşiv mi, kaynak ağaç mı.

Ölçüt: çalışan program dosyası dpkg'nin `kutuphane-defteri` paketine yazdığı
dosyalardan biri mi (`desktop/dagitim.py` modül belgesi). dpkg dizini ve program
yolları testte geçici dizindedir; karşılaştırma dosya kimliğiyledir, bu yüzden
bağlantılar ve bağlantılı dizinler gerçekten kurulur.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop import dagitim

REPO = Path(__file__).resolve().parents[2]
PROGRAM = "kutuphane-defteri"


def _program(yol: Path) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(b"\x7fELF")
    return yol


def _dpkg(kok: Path, *yollar: Path, ad: str = "kutuphane-defteri.list") -> Path:
    """dpkg bilgi dizini: listede dizinler ve dosyalar alt alta (dpkg -L biçimi)."""
    bilgi = kok / "dpkg-info"
    bilgi.mkdir(parents=True, exist_ok=True)
    satirlar = ["/.", "/opt", *(str(y) for y in yollar), "/usr/share/doc/kutuphane-defteri"]
    (bilgi / ad).write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return bilgi


@pytest.fixture
def deb(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`.deb` yerleşimi: /opt'taki program + /usr/bin bağlantısı, ikisi de listede."""
    program = _program(tmp_path / "opt" / PROGRAM / PROGRAM)
    baglanti = tmp_path / "usr" / "bin" / PROGRAM
    baglanti.parent.mkdir(parents=True)
    baglanti.symlink_to(program)
    return program, baglanti, _dpkg(tmp_path, program.parent, program, baglanti)


def _tur(exe: Path, bilgi: Path, *, deb_program_yolu: Path | None = None) -> str:
    return dagitim.linux_dagitim_turu(
        exe_yolu=str(exe),
        paketli=True,
        bilgi_dizini=bilgi,
        # Gerçek /opt yolu kabın kendisinde yoktur; verilmezse var olmayan bir yol.
        deb_program_yolu=deb_program_yolu or bilgi / "yok" / PROGRAM,
    )


# ------------------------------------------------------------- kurulu paket


def test_deb_ile_kurulu_program_kurulu_sayilir(deb: tuple[Path, Path, Path]) -> None:
    program, baglanti, bilgi = deb

    assert _tur(program, bilgi) == dagitim.KURULU
    # Program /usr/bin bağlantısından açılsa da (sys.executable bağlantıyı taşıyabilir).
    assert _tur(baglanti, bilgi) == dagitim.KURULU


def test_bagli_opt_dizini_uzerinden_de_kurulu_sayilir(tmp_path: Path) -> None:
    """/opt bağlantılı bir dizinse yol metni tutmaz; dosya kimliği tutar."""
    gercek = _program(tmp_path / "var-opt" / PROGRAM / PROGRAM)
    (tmp_path / "opt").symlink_to(tmp_path / "var-opt", target_is_directory=True)
    listelenen = tmp_path / "opt" / PROGRAM / PROGRAM
    bilgi = _dpkg(tmp_path, listelenen)

    assert _tur(gercek, bilgi) == dagitim.KURULU


def test_cok_mimarili_liste_adi_da_okunur(tmp_path: Path) -> None:
    program = _program(tmp_path / "opt" / PROGRAM / PROGRAM)
    bilgi = _dpkg(tmp_path, program, ad="kutuphane-defteri:amd64.list")

    assert _tur(program, bilgi) == dagitim.KURULU


def test_liste_okunamazsa_deb_program_yoluyla_karsilastirilir(tmp_path: Path) -> None:
    """Kurulu paket bir okuma aksaklığı yüzünden taşınabilir sayılmasın."""
    program = _program(tmp_path / "opt" / PROGRAM / PROGRAM)
    bilgi = tmp_path / "dpkg-info"
    (bilgi / "kutuphane-defteri.list").mkdir(parents=True)  # okunamaz: dizin

    assert _tur(program, bilgi, deb_program_yolu=program) == dagitim.KURULU
    baska = _program(tmp_path / "ev" / ".local" / "opt" / PROGRAM / PROGRAM)
    assert _tur(baska, bilgi, deb_program_yolu=program) == dagitim.TASINABILIR


# -------------------------------------------------------- taşınabilir arşiv


def test_kur_sh_kopyasi_deb_kuruluyken_de_tasinabilir_sayilir(
    tmp_path: Path, deb: tuple[Path, Path, Path]
) -> None:
    """Aynı adlı dosya, ama dpkg'nin yazdığı dosya değil (kur.sh → ~/.local/opt)."""
    _program_yolu, _baglanti, bilgi = deb
    kopya = _program(tmp_path / "ev" / ".local" / "opt" / PROGRAM / PROGRAM)

    assert _tur(kopya, bilgi) == dagitim.TASINABILIR


def test_arsivden_dogrudan_calisan_program_tasinabilir(tmp_path: Path) -> None:
    arsiv = _program(
        tmp_path / "indirilenler" / "kutuphane-defteri-2026.10.0" / "uygulama" / PROGRAM
    )

    # dpkg listesi hiç yok: paket kurulu değil.
    assert _tur(arsiv, tmp_path / "dpkg-info-yok") == dagitim.TASINABILIR


def test_arsiv_opt_altina_acilsa_da_listede_yoksa_tasinabilir(tmp_path: Path) -> None:
    """Yol öneki ölçüt değildir: arşiv `sudo` ile /opt/kutuphane-defteri'ye açılabilir."""
    acilan = _program(tmp_path / "opt" / PROGRAM / PROGRAM)
    bilgi = tmp_path / "dpkg-info"
    bilgi.mkdir()
    (bilgi / "baska-paket.list").write_text(f"{acilan}\n", encoding="utf-8")

    assert _tur(acilan, bilgi) == dagitim.TASINABILIR


def test_deb_paketi_kurulu_mu_programin_diskte_durmasina_bakar(
    tmp_path: Path, deb: tuple[Path, Path, Path]
) -> None:
    """KB-2 düzeltme turu (29.09.2026): taşınabilir sürüm açıkken `.deb` de kurulu mu?

    `kur.sh`'in menü kaydı ve `~/.local/bin` bağlantısı `.deb`'inkini gölgeler; paket
    kuruluysa ileti "kaldir.sh ile kaldırıp menüden açın" der (katalog_kontrol).
    """
    program, _baglanti, bilgi = deb
    yok = tmp_path / "yok" / PROGRAM

    assert dagitim.deb_paketi_kurulu(bilgi_dizini=bilgi, deb_program_yolu=yok) is True
    # dpkg listesi hiç yok: paket kurulu değil.
    assert (
        dagitim.deb_paketi_kurulu(bilgi_dizini=tmp_path / "dpkg-info-yok", deb_program_yolu=yok)
        is False
    )
    # Liste var ama program diskte yok (kaldırılmış paketin kalıntı listesi).
    program.unlink()
    (tmp_path / "usr" / "bin" / PROGRAM).unlink()
    assert dagitim.deb_paketi_kurulu(bilgi_dizini=bilgi, deb_program_yolu=yok) is False


def test_deb_paketi_kurulu_liste_okunamazsa_sabit_yola_bakar(tmp_path: Path) -> None:
    program = _program(tmp_path / "opt" / PROGRAM / PROGRAM)
    bilgi = tmp_path / "dpkg-info"
    (bilgi / "kutuphane-defteri.list").mkdir(parents=True)  # okunamaz: dizin

    assert dagitim.deb_paketi_kurulu(bilgi_dizini=bilgi, deb_program_yolu=program) is True
    assert (
        dagitim.deb_paketi_kurulu(bilgi_dizini=bilgi, deb_program_yolu=tmp_path / "yok" / PROGRAM)
        is False
    )


def test_tasinabilir_arsivde_katalog_sunulmaz() -> None:
    assert dagitim.katalog_sunulur(dagitim.TASINABILIR) is False
    for tur in (dagitim.KURULU, dagitim.KAYNAK, dagitim.PAKET):
        assert dagitim.katalog_sunulur(tur) is True


# ------------------------------------------------- kaynak ağaç ve Windows


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_paketsiz_calisma_kaynak_sayilir(platform: str, tmp_path: Path) -> None:
    """Geliştirme ortamı, Docker'daki testler ve ağ kataloğu provası etkilenmez."""
    assert (
        dagitim.dagitim_turu(platform=platform, paketli=False, bilgi_dizini=tmp_path)
        == dagitim.KAYNAK
    )


def test_bu_test_sureci_paketsizdir() -> None:
    """Varsayılan (sys.frozen yok) → KAYNAK: kapı testleri ve provayı kesmez."""
    assert dagitim.dagitim_turu(platform="linux") == dagitim.KAYNAK


def test_windows_bu_katmanda_ayrilmaz(tmp_path: Path) -> None:
    """Windows'un taşınabilir paketini güvenlik duvarının 2. maddesi durdurur (değişmedi)."""
    tur = dagitim.dagitim_turu(
        platform="win32", paketli=True, exe_yolu=r"C:\x\kutuphane-defteri.exe"
    )

    assert tur == dagitim.PAKET
    assert dagitim.katalog_sunulur(tur) is True


def test_linux_paketli_varsayilan_giris_dpkg_listesine_bakar(
    deb: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    program, _baglanti, bilgi = deb
    kopya = _program(tmp_path / "ev" / PROGRAM)

    assert (
        dagitim.dagitim_turu(
            platform="linux", paketli=True, exe_yolu=str(program), bilgi_dizini=bilgi
        )
        == dagitim.KURULU
    )
    assert (
        dagitim.dagitim_turu(
            platform="linux", paketli=True, exe_yolu=str(kopya), bilgi_dizini=bilgi
        )
        == dagitim.TASINABILIR
    )


# ------------------------------------- sabitler paketleme hattıyla aynı


def test_sabitler_paketleme_hattiyla_ayni() -> None:
    """Paket adı, program yolu ve taşınabilir kurulumun hedefi değişirse ölçüt de değişmeli."""
    kontrol = (REPO / "packaging" / "linux" / "debian-control.tmpl").read_text(encoding="utf-8")
    derleme = (REPO / "packaging" / "linux" / "build.sh").read_text(encoding="utf-8")
    kur = (REPO / "packaging" / "linux" / "kur.sh").read_text(encoding="utf-8")

    assert f"Package: {dagitim.DEB_PAKET_ADI}\n" in kontrol
    assert "Multi-Arch" not in kontrol  # liste adı <paket>.list (çok mimarili ad da okunur)
    assert f"ln -sf {dagitim.DEB_PROGRAM_YOLU} " in derleme
    assert dagitim.DPKG_BILGI_DIZINI == Path("/var/lib/dpkg/info")
    # Taşınabilir kurulum ev dizinine kopyalar; dpkg'ye hiçbir şey yazmaz.
    assert 'HEDEF="$HOME/.local/opt/kutuphane-defteri"' in kur
    assert "dpkg" not in kur
