"""Beta sürüm yolu (F12, kullanıcı kararı 3 — 27.09.2026).

İlk sürüm bir BETA etiketidir (`v2026.10.0-beta.1`); etiketi ana oturum kullanıcı
onayıyla atar, bu dal yalnız hazırlar. Burada sabitlenenler:

* `VERSION` CalVer + ön-sürüm ekidir ve paket adlarına doğru dönüşür (.deb `~`,
  Windows sürüm kaynağı yalnız sayı, güncelleme denetiminin kurucu deseni);
* `paketleme.yml` yayın işinin ADIMLARI gerçekten koşturulur (sahte `gh` ve
  `npx` ile): etiket ↔ VERSION kapısı, `~` → `.` yeniden adlandırması,
  ön-sürüm etiketinin Release'te "pre-release" işaretlenmesi, R2 secret'ları
  yokken UYARIYLA atlanması ve varken doğru adlarla yüklenmesi.

Yayın işi yalnız `v*` etiketinde koştuğu için PR kapıları onu hiç çalıştırmaz
(KS'nin ilk etiket koşusu tam böyle bir satırdan kırıldı); bu test o boşluğu
kapatır. Güncelleme denetiminin kararlı kullanıcıya beta önermemesi
`backend/apps/okul/tests/test_updates.py`'dedir (iki `version_key` kopyası dahil).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
IS_AKISI = (REPO / ".github" / "workflows" / "paketleme.yml").read_text(encoding="utf-8")
BASH = shutil.which("bash") or "/bin/bash"


def _adim(ad: str, *, sira: int = 0) -> tuple[str, dict[str, str]]:
    """İş akışındaki `- name: <ad>` adımının `run` betiği ve düz `env` değerleri."""
    satirlar = IS_AKISI.splitlines()
    baslar = [i for i, s in enumerate(satirlar) if s.strip() == f"- name: {ad}"]
    assert len(baslar) > sira, f"adım bulunamadı: {ad}"
    i = baslar[sira]
    girinti = len(satirlar[i]) - len(satirlar[i].lstrip())
    ortam: dict[str, str] = {}
    betik: list[str] = []
    j = i + 1
    while j < len(satirlar):
        satir = satirlar[j]
        if satir.strip() and len(satir) - len(satir.lstrip()) <= girinti:
            break
        durum = satir.strip()
        if durum.startswith("run: |"):
            anahtar_girinti = len(satir) - len(satir.lstrip())
            j += 1
            govde: list[str] = []
            while j < len(satirlar) and (
                not satirlar[j].strip()
                or len(satirlar[j]) - len(satirlar[j].lstrip()) > anahtar_girinti
            ):
                govde.append(satirlar[j])
                j += 1
            kesim = min(len(s) - len(s.lstrip()) for s in govde if s.strip())
            betik = [s[kesim:] for s in govde]
            continue
        if durum.startswith("run: "):
            betik = [durum.removeprefix("run: ")]
        eslesme = re.match(r"^([A-Z0-9_]+): (\S.*)$", durum)
        if eslesme and "${{" not in eslesme.group(2):
            ortam[eslesme.group(1)] = eslesme.group(2)
        j += 1
    assert betik, f"{ad}: run bulunamadı"
    return "\n".join(betik) + "\n", ortam


def _kos(
    betik: str, calisma: Path, ortam: dict[str, str], yol: Path | None = None
) -> subprocess.CompletedProcess[str]:
    path = f"{yol}:/usr/bin:/bin" if yol else "/usr/bin:/bin"
    # S603: betik iş akışının kendi satırlarıdır, dış girdi yok.
    return subprocess.run(  # noqa: S603
        [BASH, "-e", "-c", betik],
        cwd=calisma,
        env={"PATH": path, "HOME": str(calisma), **ortam},
        capture_output=True,
        text=True,
        check=False,
    )


def _sahte_arac(dizin: Path, ad: str) -> Path:
    """Argümanlarını kütüğe (her çağrı bir satır, argümanlar sekmeyle) yazan sahte araç."""
    dizin.mkdir(exist_ok=True)
    kutuk = dizin / f"{ad}.log"
    arac = dizin / ad
    arac.write_text(
        f'#!/usr/bin/env bash\n( IFS=$\'\\t\'; echo "$*" ) >> "{kutuk}"\n', encoding="utf-8"
    )
    arac.chmod(0o755)
    return kutuk


# ------------------------------------------------------------------ VERSION


def test_version_calver_ve_on_surum_eki() -> None:
    """VERSION CalVer'dır; ek yalnız alpha/beta/rc + numara (README "Sürüm").

    Sabit değere KİLİTLENMEZ (F12 düzeltme turu): her sürüm artırımında kapı kırmızı
    olurdu. İlk betanın `2026.10.0-beta.1` olduğu tasarım §14.1 "F12 ekleri"ndedir.
    """
    assert re.fullmatch(r"20\d\d\.(1[0-2]|[1-9])\.\d+(-(alpha|beta|rc)\.\d+)?", VERSION), VERSION


def test_deb_ve_windows_surum_donusumleri() -> None:
    build_sh = (REPO / "packaging" / "linux" / "build.sh").read_text(encoding="utf-8")
    satir = next(s for s in build_sh.splitlines() if s.startswith("DEB_SURUM="))
    sonuc = _kos(f'SURUM="{VERSION}"\n{satir}\necho "$DEB_SURUM"\n', REPO, {})
    assert sonuc.stdout.strip() == "2026.10.0~beta.1"
    # Windows sürüm kaynağı yalnız sayıdır: build.ps1 eki atar ve dörde tamamlar.
    build_ps1 = (REPO / "packaging" / "windows" / "build.ps1").read_text(encoding="utf-8-sig")
    assert '$NumericVersion = ($Version -split "-")[0]' in build_ps1
    sayisal = VERSION.split("-")[0].split(".")
    sayisal += ["0"] * (4 - len(sayisal))
    assert ".".join(sayisal) == "2026.10.0.0"
    assert all(0 <= int(p) <= 65535 for p in sayisal)  # VERSIONINFO sınırı


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="dpkg yok")
def test_debian_siralamasi_alfa_beta_rc_kesin() -> None:
    """`~` kesin sürümden önce gelir: beta paketi alfanın güncellemesidir, kesin sürüm
    betanın güncellemesidir (dpkg'nin kendi karşılaştırması)."""
    sira = [
        "2026.9.0~alpha.0",
        "2026.10.0~beta.1",
        "2026.10.0~beta.10",
        "2026.10.0~rc.1",
        "2026.10.0",
    ]
    for once, sonra in zip(sira, sira[1:], strict=False):
        # S603/S607: sabit araç ve argümanlar.
        sonuc = subprocess.run(  # noqa: S603
            ["dpkg", "--compare-versions", once, "lt", sonra],  # noqa: S607
            check=False,
        )
        assert sonuc.returncode == 0, (once, sonra)


def test_inno_appid_degismez() -> None:
    """AppId değişirse beta → kararlı yükseltme yerinde yapılmaz, yan yana kurulur
    (tasarım §2.3). Değer kardeş kurucuların hiçbiriyle aynı değildir (27.09.2026)."""
    iss = (REPO / "packaging" / "windows" / "kutuphane-defteri.iss").read_text(encoding="utf-8")
    assert re.findall(r"^AppId=(.+)$", iss, flags=re.MULTILINE) == [
        "{{6EA9384D-3BC5-4D2F-9025-ADB60E01897C}"
    ]
    # Kurucu adı sürümü taşır; güncelleme denetimi bu desenle arar.
    assert "OutputBaseFilename=kutuphane-defteri-{#AppVersion}-win64-setup" in iss


def test_guncelleme_denetimi_beta_kurucusunu_tanir() -> None:
    import sys

    sys.path.insert(0, str(REPO / "backend"))
    try:
        from apps.okul.services import updates
    finally:
        sys.path.remove(str(REPO / "backend"))
    assert updates.INSTALLER_PATTERN.fullmatch(f"kutuphane-defteri-{VERSION}-win64-setup.exe")
    assert updates.is_prerelease(VERSION)


# ------------------------------------------------------------ yayın adımları


def test_etiket_version_kapisi_beta_etiketini_gecirir() -> None:
    for sira in (0, 1):  # linux ve windows işlerinde aynı satır
        betik, _ = _adim("Sürüm etiketi ↔ VERSION kapısı", sira=sira)
        assert _kos(betik, REPO, {"GITHUB_REF_NAME": f"v{VERSION}"}).returncode == 0
        assert _kos(betik, REPO, {"GITHUB_REF_NAME": "v2026.10.0-beta.2"}).returncode != 0


def _yayin_dizini(kok: Path) -> Path:
    yayin = kok / "yayin"
    yayin.mkdir()
    for ad in (
        f"kutuphane-defteri_{VERSION.replace('-', '~')}_amd64.deb",
        f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz",
        f"kutuphane-defteri-{VERSION}-win64-setup.exe",
        f"kutuphane-defteri-{VERSION}-win64-portable.zip",
        "pdf-duman.pdf",
    ):
        (yayin / ad).write_bytes(b"x")
    return yayin


def test_sha256sums_adimi_tildeyi_nokta_yapar_ve_duman_pdfini_atar(tmp_path: Path) -> None:
    yayin = _yayin_dizini(tmp_path)
    betik, _ = _adim("SHA256SUMS.txt")
    sonuc = _kos(betik, yayin, {})
    assert sonuc.returncode == 0, sonuc.stderr
    adlar = sorted(p.name for p in yayin.iterdir())
    assert "pdf-duman.pdf" not in adlar
    assert f"kutuphane-defteri_{VERSION.replace('-', '.')}_amd64.deb" in adlar
    ozet = (yayin / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert len(ozet) == 4


@pytest.mark.parametrize(
    ("etiket", "on_surum"),
    [(f"v{VERSION}", True), ("v2026.10.0-rc.1", True), ("v2026.10.0", False)],
)
def test_release_on_surum_etiketini_pre_release_isaretler(
    tmp_path: Path, etiket: str, on_surum: bool
) -> None:
    _yayin_dizini(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "gh")
    betik, _ = _adim("Release")
    sonuc = _kos(
        betik,
        tmp_path,
        {"GITHUB_REF_NAME": etiket, "GITHUB_REPOSITORY": "ornek/kutuphane-defteri"},
        tmp_path / "bin",
    )
    assert sonuc.returncode == 0, sonuc.stderr
    argumanlar = kutuk.read_text(encoding="utf-8").strip().split("\t")
    assert argumanlar[:3] == ["release", "create", etiket]
    assert ("--prerelease" in argumanlar) is on_surum
    notlar = argumanlar[argumanlar.index("--notes") + 1]
    assert notlar.startswith("Ön sürümdür. ") is on_surum
    # KB-1 düzeltme turu (29.09.2026): ağdan dağıtımda LGPL-3.0 bileşenleri için GPL-3.0
    # md. 6(d) — nesne kodunun yanında kaynağa açık yönlendirme. Qt/PySide6 sürümü lisans
    # listesindekiyle aynı olmalı (sürüm yükselince not da güncellenir).
    bilesenler = json.loads(
        (REPO / "THIRD_PARTY_LICENSES" / "bilesenler.json").read_text(encoding="utf-8")
    )["bilesenler"]
    qt = next(b["surum"] for b in bilesenler if b["ad"] == "PySide6")
    assert "THIRD_PARTY_LICENSES/BENIOKU.txt" in notlar and "yazılı teklif" in notlar
    assert f"Qt ve PySide6 {qt}'ün kaynağı" in notlar
    assert f"https://download.qt.io/archive/qt/{qt.rsplit('.', 1)[0]}/{qt}/single/" in notlar
    assert f"pyside6/PySide6-{qt}-src/" in notlar


def test_r2_adimi_secret_yoksa_uyariyla_atlanir(tmp_path: Path) -> None:
    yayin = _yayin_dizini(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik, ortam = _adim("İndirme alanına yükle (R2)")
    sonuc = _kos(
        betik,
        yayin,
        {
            **ortam,
            "GITHUB_REF_NAME": f"v{VERSION}",
            "CLOUDFLARE_API_TOKEN": "",
            "CLOUDFLARE_ACCOUNT_ID": "",
        },
        tmp_path / "bin",
    )
    assert sonuc.returncode == 0, sonuc.stderr
    assert "::warning::" in sonuc.stdout and "R2 yüklemesi atlandı" in sonuc.stdout
    assert not kutuk.exists()


def test_r2_adimi_secret_varken_surumlu_adlarla_yukler(tmp_path: Path) -> None:
    yayin = _yayin_dizini(tmp_path)
    (yayin / "pdf-duman.pdf").unlink()
    (yayin / "SHA256SUMS.txt").write_text("x\n", encoding="utf-8")
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik, ortam = _adim("İndirme alanına yükle (R2)")
    assert ortam == {"R2_KOVA": "okulapp-indirme", "R2_ONEK": "kutuphane-defteri"}
    sonuc = _kos(
        betik,
        yayin,
        {
            **ortam,
            "GITHUB_REF_NAME": f"v{VERSION}",
            # Sahte değerler: sahte `npx` hiçbir yere bağlanmaz.
            "CLOUDFLARE_API_TOKEN": "sahte-belirtec",
            "CLOUDFLARE_ACCOUNT_ID": "sahte-hesap",
        },
        tmp_path / "bin",
    )
    assert sonuc.returncode == 0, sonuc.stderr
    hedefler = sorted(
        satir.split("\t")[5] for satir in kutuk.read_text(encoding="utf-8").splitlines()
    )
    assert hedefler == sorted(
        f"okulapp-indirme/kutuphane-defteri/{ad}"
        for ad in (
            f"SHA256SUMS-{VERSION}.txt",
            f"kutuphane-defteri_{VERSION.replace('-', '~')}_amd64.deb",
            f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz",
            f"kutuphane-defteri-{VERSION}-win64-setup.exe",
            f"kutuphane-defteri-{VERSION}-win64-portable.zip",
        )
    )


def test_yayin_isi_yalniz_etikette_ve_paket_islerinden_sonra_kosar() -> None:
    blok = IS_AKISI.split("\n  yayin:", 1)[1]
    assert "if: startsWith(github.ref, 'refs/tags/v')" in blok
    assert "needs: [linux-kurulum, windows]" in blok
    assert "contents: write" in blok
    # Etiket tetiği `v*`: beta etiketi de yayın yolunu açar.
    assert re.search(r'tags:\n\s+- "v\*"', IS_AKISI)
    assert os.path.basename(str(REPO / "VERSION")) in IS_AKISI
