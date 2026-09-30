"""Beta sürüm yolu (F12, kullanıcı kararı 3 — 27.09.2026).

İlk sürüm bir BETA etiketidir (`v2026.10.0-beta.1`); etiketi ana oturum kullanıcı
onayıyla atar, bu dal yalnız hazırlar. Burada sabitlenenler:

* `VERSION` CalVer + ön-sürüm ekidir ve paket adlarına doğru dönüşür (.deb `~`,
  Windows sürüm kaynağı yalnız sayı, güncelleme denetiminin kurucu deseni);
* `paketleme.yml` yayın işinin ADIMLARI gerçekten koşturulur (sahte `gh` ve
  `npx` ile): etiket ↔ VERSION kapısı, `~` → `.` yeniden adlandırması,
  ön-sürüm etiketinin Release'te "pre-release" işaretlenmesi, R2 secret'ları
  yokken UYARIYLA atlanması ve varken doğru adlarla yüklenmesi;
* R2 yüklemesi TEK betiktedir (`packaging/r2-yukle.sh`, 30.09.2026): yayın işi
  ve var olan Release'i sonradan yükleyen `r2-yukle.yml` aynı betiği çağırır ve
  aynı Release için AYNI kova yollarını üretir; `r2-yukle.yml`'de kimlik
  zorunludur; betik yüklemeden önce SHA256SUMS'u doğrular, bir şey tutmazsa hiçbir
  dosya yüklemez.

Yayın işi yalnız `v*` etiketinde, `r2-yukle.yml` yalnız elle koştuğu için PR
kapıları onları hiç çalıştırmaz (KS'nin ilk etiket koşusu tam böyle bir satırdan
kırıldı); bu test o boşluğu kapatır. Güncelleme denetiminin kararlı kullanıcıya
beta önermemesi `backend/apps/okul/tests/test_updates.py`'dedir (iki
`version_key` kopyası dahil).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
IS_AKISI = (REPO / ".github" / "workflows" / "paketleme.yml").read_text(encoding="utf-8")
R2_IS_AKISI = (REPO / ".github" / "workflows" / "r2-yukle.yml").read_text(encoding="utf-8")
R2_BETIGI = REPO / "packaging" / "r2-yukle.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _adim(ad: str, *, sira: int = 0, is_akisi: str = IS_AKISI) -> tuple[str, dict[str, str]]:
    """İş akışındaki `- name: <ad>` adımının `run` betiği ve düz `env` değerleri."""
    satirlar = is_akisi.splitlines()
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
            # YAML'da tırnaklı düz değer (`"1"`) ortama tırnaksız geçer.
            ortam[eslesme.group(1)] = eslesme.group(2).strip('"')
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
    """Paket işlerinin artefaktları indirilmiş hâli (`.deb` adında `~`, duman PDF'i var)."""
    yayin = kok / "yayin"
    yayin.mkdir(parents=True)
    for ad in (
        f"kutuphane-defteri_{VERSION.replace('-', '~')}_amd64.deb",
        f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz",
        f"kutuphane-defteri-{VERSION}-win64-setup.exe",
        f"kutuphane-defteri-{VERSION}-win64-portable.zip",
        "pdf-duman.pdf",
    ):
        # İçerikler ayrı: özet denetimi bir dosyanın bozulmasını ayırt edebilsin.
        (yayin / ad).write_bytes(ad.encode())
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


# ------------------------------------------------------------ R2 yüklemesi
#
# Yükleme mantığı TEK betiktedir (`packaging/r2-yukle.sh`); iki iş akışı onu
# çağırır. Aşağıdaki testler iş akışı adımlarını betiğin gerçek kopyasıyla ve
# sahte `gh`/`npx` ile koşturur. Kimlik değerleri sahtedir: sahte `npx` hiçbir
# yere bağlanmaz.

SAHTE_KIMLIK = {"CLOUDFLARE_API_TOKEN": "sahte-belirtec", "CLOUDFLARE_ACCOUNT_ID": "sahte-hesap"}
BOS_KIMLIK = {"CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""}
R2_ADIMI = "İndirme alanına yükle (R2)"

#: Aynı Release için kovada beklenen yollar ve içerik türleri. Beta `.deb`'i
#: Release'teki `.`li adla gider (`~` yayın işinin SHA256SUMS adımında `.` olur);
#: özet SÜRÜMLÜ adla yazılır.
BEKLENEN_YUKLEMELER = {
    f"okulapp-indirme/kutuphane-defteri/{ad}": tur
    for ad, tur in (
        (
            f"kutuphane-defteri_{VERSION.replace('-', '.')}_amd64.deb",
            "application/vnd.debian.binary-package",
        ),
        (f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz", "application/gzip"),
        (
            f"kutuphane-defteri-{VERSION}-win64-setup.exe",
            "application/vnd.microsoft.portable-executable",
        ),
        (f"kutuphane-defteri-{VERSION}-win64-portable.zip", "application/zip"),
        (f"SHA256SUMS-{VERSION}.txt", "text/plain; charset=utf-8"),
    )
}


def _release_dizini(kok: Path) -> Path:
    """Release'e giden dizin: `_yayin_dizini` üzerinde yayın işinin "SHA256SUMS.txt"
    adımı koşmuş hâli (`.deb` adında `.`, duman PDF'i yok, özet var)."""
    yayin = _yayin_dizini(kok)
    betik, _ = _adim("SHA256SUMS.txt")
    sonuc = _kos(betik, yayin, {})
    assert sonuc.returncode == 0, sonuc.stderr
    return yayin


def _betigi_yerlestir(kok: Path) -> None:
    """İş akışı adımları betiği depo kökünden göreli çağırır; geçici köke kopyalanır."""
    (kok / "packaging").mkdir(parents=True, exist_ok=True)
    shutil.copy2(R2_BETIGI, kok / "packaging" / "r2-yukle.sh")


def _yuklemeler(kutuk: Path) -> list[tuple[str, str, str]]:
    """Sahte `npx` kütüğünden (kova yolu, `--file`, `--content-type`), çağrı sırasıyla."""
    sonuc: list[tuple[str, str, str]] = []
    for satir in kutuk.read_text(encoding="utf-8").splitlines():
        arg = satir.split("\t")
        assert arg[:5] == ["--yes", "wrangler@4", "r2", "object", "put"], arg
        assert arg[-1] == "--remote", arg
        secenek: dict[str, str] = {}
        for oge in arg[6:-1]:
            anahtar, _, deger = oge.removeprefix("--").partition("=")
            secenek[anahtar] = deger
        sonuc.append((arg[5], secenek["file"], secenek["content-type"]))
    return sonuc


def _sahte_gh_release(dizin: Path, release: Path) -> Path:
    """`gh release download … --dir D` çağrısında Release dosyalarını D'ye koyan sahte gh."""
    dizin.mkdir(exist_ok=True)
    kutuk = dizin / "gh.log"
    arac = dizin / "gh"
    arac.write_text(
        "#!/usr/bin/env bash\n"
        f'( IFS=$\'\\t\'; echo "$*" ) >> "{kutuk}"\n'
        'if [ "$1 $2" = "release download" ]; then\n'
        '  while [ "$#" -gt 0 ]; do [ "$1" = "--dir" ] && hedef="$2"; shift; done\n'
        f'  mkdir -p "$hedef" && cp -- "{release}"/* "$hedef"/\n'
        "fi\n",
        encoding="utf-8",
    )
    arac.chmod(0o755)
    return kutuk


def test_r2_yuklemesi_tek_betikte() -> None:
    """İki iş akışı da aynı betiği çağırır; kova, önek ve wrangler çağrısı yalnız betikte."""
    betik, ortam = _adim(R2_ADIMI)
    assert betik == 'bash packaging/r2-yukle.sh yayin "${GITHUB_REF_NAME#v}"\n'
    assert ortam == {}  # yayın işinde kimlik yoksa uyarıyla atlanır
    betik, ortam = _adim(R2_ADIMI, is_akisi=R2_IS_AKISI)
    assert betik == 'bash packaging/r2-yukle.sh yayin "${ETIKET#v}"\n'
    assert ortam == {"R2_KIMLIK_ZORUNLU": "1"}
    for metin in (IS_AKISI, R2_IS_AKISI):
        assert "r2 object put" not in metin and "okulapp-indirme" not in metin
        for secret in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
            assert metin.count(f"{secret}: ${{{{ secrets.{secret} }}}}") == 1
    kaynak = R2_BETIGI.read_text(encoding="utf-8")
    assert 'R2_KOVA="okulapp-indirme"' in kaynak and 'R2_ONEK="kutuphane-defteri"' in kaynak


def test_r2_izni_admin_read_write_yazilir() -> None:
    """Object Read & Write YETMEZ (wrangler REST API; DD hattı, 28.09.2026): yorum ve
    belgeler doğru izni söyler, yanlış izni gerekli diye önermez."""
    for yol in (
        R2_BETIGI,
        REPO / ".github" / "workflows" / "paketleme.yml",
        REPO / "packaging" / "README.md",
    ):
        metin = " ".join(yol.read_text(encoding="utf-8").replace("*", "").split())
        assert "Admin Read & Write" in metin, yol
        assert "Object Read & Write YETMEZ" in metin, yol
        assert "R2 Object Read & Write" not in metin, yol  # eski, yanlış öneri


def test_r2_adimi_secret_yoksa_uyariyla_atlanir(tmp_path: Path) -> None:
    _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik, ortam = _adim(R2_ADIMI)
    sonuc = _kos(
        betik,
        tmp_path,
        {**ortam, "GITHUB_REF_NAME": f"v{VERSION}", **BOS_KIMLIK},
        tmp_path / "bin",
    )
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    assert "::warning::" in sonuc.stdout and "R2 yüklemesi atlandı" in sonuc.stdout
    # Uyarı sonradan yükleme yolunu söyler.
    assert f"etiket = v{VERSION}" in sonuc.stdout
    assert not kutuk.exists()


def test_yayin_isi_release_adlariyla_ve_ozeti_en_son_yukler(tmp_path: Path) -> None:
    """Yayın işinin iki adımı art arda: SHA256SUMS (`~` → `.`) → R2."""
    yayin = _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik, ortam = _adim(R2_ADIMI)
    sonuc = _kos(
        betik,
        tmp_path,
        {**ortam, "GITHUB_REF_NAME": f"v{VERSION}", **SAHTE_KIMLIK},
        tmp_path / "bin",
    )
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    yuklemeler = _yuklemeler(kutuk)
    assert {hedef: tur for hedef, _, tur in yuklemeler} == BEKLENEN_YUKLEMELER
    assert len(yuklemeler) == len(BEKLENEN_YUKLEMELER)  # her dosya bir kez
    assert not any("~" in hedef for hedef, _, _ in yuklemeler)
    # Paketler Release'teki adlarıyla gider; özet EN SON, sürümlü adla.
    for hedef, dosya, _ in yuklemeler[:-1]:
        assert hedef == f"okulapp-indirme/kutuphane-defteri/{dosya}"
        assert (yayin / dosya).is_file()
    assert yuklemeler[-1][:2] == (
        f"okulapp-indirme/kutuphane-defteri/SHA256SUMS-{VERSION}.txt",
        "SHA256SUMS.txt",
    )
    assert "::notice::" in sonuc.stdout and "src/data/kd-release.json" in sonuc.stdout


def test_r2_yukle_is_akisi_releasei_indirip_ayni_yollara_yukler(tmp_path: Path) -> None:
    """Sonradan yükleme: etiket denetimi → `gh release download` → aynı betik. Yayın
    işiyle AYNI kova yolları ve içerik türleri çıkar."""
    release = _release_dizini(tmp_path / "release")
    is_dizini = tmp_path / "is"
    _betigi_yerlestir(is_dizini)
    gh_kutuk = _sahte_gh_release(tmp_path / "bin", release)
    npx_kutuk = _sahte_arac(tmp_path / "bin", "npx")
    ortak = {"ETIKET": f"v{VERSION}", "GITHUB_REPOSITORY": "ornek/kutuphane-defteri"}
    for ad in ("Etiket denetimi", "Release dosyalarını indir", R2_ADIMI):
        betik, ortam = _adim(ad, is_akisi=R2_IS_AKISI)
        sonuc = _kos(betik, is_dizini, {**ortam, **ortak, **SAHTE_KIMLIK}, tmp_path / "bin")
        assert sonuc.returncode == 0, (ad, sonuc.stdout, sonuc.stderr)
    assert gh_kutuk.read_text(encoding="utf-8").splitlines() == [
        "\t".join(
            ["release", "download", f"v{VERSION}", "--repo", "ornek/kutuphane-defteri"]
            + ["--dir", "yayin"]
        )
    ]
    yuklemeler = _yuklemeler(npx_kutuk)
    assert {hedef: tur for hedef, _, tur in yuklemeler} == BEKLENEN_YUKLEMELER
    assert len(yuklemeler) == len(BEKLENEN_YUKLEMELER)
    assert yuklemeler[-1][1] == "SHA256SUMS.txt"


def test_r2_yukle_is_akisinda_kimlik_zorunlu(tmp_path: Path) -> None:
    """Elle başlatılan yükleme hiçbir şey yüklemeden YEŞİL bitmez."""
    _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik, ortam = _adim(R2_ADIMI, is_akisi=R2_IS_AKISI)
    sonuc = _kos(
        betik, tmp_path, {**ortam, "ETIKET": f"v{VERSION}", **BOS_KIMLIK}, tmp_path / "bin"
    )
    assert sonuc.returncode == 1
    assert "::error::" in sonuc.stdout and "hiçbir dosya yüklenmedi" in sonuc.stdout
    assert "R2 secret'ları" in sonuc.stdout  # README bölümüne yönlendirir
    assert not kutuk.exists()


@pytest.mark.parametrize("etiket", ["2026.10.0-beta.1", "V2026.10.0-beta.1", "", "vson"])
def test_r2_yukle_etiket_denetimi_v_onekini_ister(tmp_path: Path, etiket: str) -> None:
    betik, _ = _adim("Etiket denetimi", is_akisi=R2_IS_AKISI)
    sonuc = _kos(betik, tmp_path, {"ETIKET": etiket})
    assert sonuc.returncode != 0 and "::error::" in sonuc.stdout


def test_r2_yukle_is_akisi_yalniz_elle_ve_salt_okur_izinle() -> None:
    tetik = R2_IS_AKISI.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert tetik.strip().startswith("workflow_dispatch:")
    for olay in ("push", "pull_request", "schedule", "tags"):
        assert olay not in tetik, olay
    assert "required: true" in tetik
    assert "\npermissions:\n  contents: read\n" in R2_IS_AKISI
    assert "contents: write" not in R2_IS_AKISI
    assert "sparse-checkout: packaging/r2-yukle.sh" in R2_IS_AKISI


def _ozete_ekle(yayin: Path, ad: str) -> None:
    ozet = hashlib.sha256((yayin / ad).read_bytes()).hexdigest()
    with (yayin / "SHA256SUMS.txt").open("a", encoding="utf-8") as dosya:
        dosya.write(f"{ozet}  {ad}\n")


def _bozuk(yayin: Path) -> None:
    (yayin / f"kutuphane-defteri-{VERSION}-win64-setup.exe").write_bytes(b"bozuk")


def _eksik(yayin: Path) -> None:
    (yayin / f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz").unlink()


def _ozetsiz_tildeli_deb(yayin: Path) -> None:
    # `~` → `.` adımı atlanmış paket: özette `.`li ad var, bu ad yok.
    (yayin / f"kutuphane-defteri_{VERSION.replace('-', '~')}_amd64.deb").write_bytes(b"deb")


def _turu_bilinmeyen(yayin: Path) -> None:
    (yayin / "notlar.md").write_text("not\n", encoding="utf-8")
    _ozete_ekle(yayin, "notlar.md")  # özet tutar; yalnız tür bilinmiyor


def _ozet_yok(yayin: Path) -> None:
    (yayin / "SHA256SUMS.txt").unlink()


@pytest.mark.parametrize("boz", [_bozuk, _eksik, _ozetsiz_tildeli_deb, _turu_bilinmeyen, _ozet_yok])
def test_r2_betigi_denetim_tutmazsa_hicbir_dosya_yuklemez(
    tmp_path: Path, boz: Callable[[Path], None]
) -> None:
    yayin = _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    boz(yayin)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    sonuc = _kos(
        f'bash packaging/r2-yukle.sh yayin "{VERSION}"\n', tmp_path, SAHTE_KIMLIK, tmp_path / "bin"
    )
    assert sonuc.returncode == 1, sonuc.stdout + sonuc.stderr
    assert "::error::" in sonuc.stdout and "hiçbir dosya yüklenmedi" in sonuc.stdout
    assert not kutuk.exists()


@pytest.mark.parametrize(("fazla", "gecer"), [(0, True), (1, False)])
def test_r2_betigi_wrangler_tek_parca_sinirini_denetler(
    tmp_path: Path, fazla: int, gecer: bool
) -> None:
    """wrangler tek parçada en çok 300 MiB yükler (Cloudflare: "up to 315 MB"); sınırı
    aşan paket varken hiçbir dosya yüklenmez. Sınırın kendisi geçer."""
    yayin = _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    with (yayin / f"kutuphane-defteri-{VERSION}-linux-x64.tar.gz").open("wb") as arsiv:
        arsiv.truncate(300 * 1024 * 1024 + fazla)  # seyrek dosya: diskte yer tutmaz
    ozet = _kos("rm -f SHA256SUMS.txt\nsha256sum -- * > SHA256SUMS.txt\n", yayin, {})
    assert ozet.returncode == 0, ozet.stderr
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    sonuc = _kos(
        f'bash packaging/r2-yukle.sh yayin "{VERSION}"\n', tmp_path, SAHTE_KIMLIK, tmp_path / "bin"
    )
    if gecer:
        assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
        assert len(_yuklemeler(kutuk)) == len(BEKLENEN_YUKLEMELER)
    else:
        assert sonuc.returncode == 1 and "300 MiB" in sonuc.stdout
        assert "hiçbir dosya yüklenmedi" in sonuc.stdout
        assert not kutuk.exists()


@pytest.mark.parametrize("surum", [f"v{VERSION}", "2026.10.0-dev.1", "son", ""])
def test_r2_betigi_surum_bicimini_denetler(tmp_path: Path, surum: str) -> None:
    _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    sonuc = _kos(
        f'bash packaging/r2-yukle.sh yayin "{surum}"\n', tmp_path, SAHTE_KIMLIK, tmp_path / "bin"
    )
    assert sonuc.returncode == 1 and "Sürüm biçimi tanınmadı" in sonuc.stdout
    assert not kutuk.exists()
    eksik = _kos("bash packaging/r2-yukle.sh yayin\n", tmp_path, SAHTE_KIMLIK, tmp_path / "bin")
    assert eksik.returncode == 2 and "Kullanım:" in eksik.stderr


@pytest.mark.parametrize("surum", ["2026.10.0-dev.1", f"v{VERSION}"])
def test_r2_betigi_kimlik_yokken_surumu_denetlemeden_atlar(tmp_path: Path, surum: str) -> None:
    """Kimlik yokken yayın işi, satır içi eski adım gibi yalnız uyarıyla sürer: sürüm
    biçimi (ör. `paketleme.yml`'nin ön sürüm saydığı `-dev` eki) yalnız yükleme yolunda
    denetlenir. Zorunlu kipte (`r2-yukle.yml`) kimlik hatası yine önce gelir."""
    _release_dizini(tmp_path)
    _betigi_yerlestir(tmp_path)
    kutuk = _sahte_arac(tmp_path / "bin", "npx")
    betik = f'bash packaging/r2-yukle.sh yayin "{surum}"\n'
    sonuc = _kos(betik, tmp_path, BOS_KIMLIK, tmp_path / "bin")
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    assert "::warning::" in sonuc.stdout and "R2 yüklemesi atlandı" in sonuc.stdout
    assert "Sürüm biçimi" not in sonuc.stdout
    zorunlu = _kos(betik, tmp_path, {**BOS_KIMLIK, "R2_KIMLIK_ZORUNLU": "1"}, tmp_path / "bin")
    assert zorunlu.returncode == 1 and "secret'ları tanımlı değil" in zorunlu.stdout
    assert not kutuk.exists()


def test_yayin_isi_yalniz_etikette_ve_paket_islerinden_sonra_kosar() -> None:
    blok = IS_AKISI.split("\n  yayin:", 1)[1]
    assert "if: startsWith(github.ref, 'refs/tags/v')" in blok
    assert "needs: [linux-kurulum, windows]" in blok
    assert "contents: write" in blok
    # Etiket tetiği `v*`: beta etiketi de yayın yolunu açar.
    assert re.search(r'tags:\n\s+- "v\*"', IS_AKISI)
    assert os.path.basename(str(REPO / "VERSION")) in IS_AKISI
