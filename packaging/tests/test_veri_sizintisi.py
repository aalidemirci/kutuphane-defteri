from __future__ import annotations

import io
import re
import runpy
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

BETIK = Path(__file__).parents[1] / "veri_sizintisi.py"
MODUL = runpy.run_path(str(BETIK))
YASAK_DOSYALARI_BUL = cast(
    Callable[[Path], list[Path]],
    MODUL["yasak_dosyalari_bul"],
)
GUVENLI_METIN = cast(Callable[[str, str | None], str], MODUL["guvenli_metin"])


def test_temiz_paket_kabul_edilir(tmp_path: Path) -> None:
    """Meşru paket içeriği (evrak şablonları dahil) yasak kurallara TAKILMAMALI."""
    for dosya in (
        tmp_path / "_internal" / "templates" / "bos-form.pdf",
        tmp_path / "_internal" / "backend" / "templates" / "documents" / "base.html",
    ):
        dosya.parent.mkdir(parents=True)
        dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == []


def test_backend_veritabani_reddedilir(tmp_path: Path) -> None:
    dosya = tmp_path / "_internal" / "backend" / "data" / "db.sqlite3"
    dosya.parent.mkdir(parents=True)
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("_internal/backend/data/db.sqlite3")]


def test_excel_dosyasi_reddedilir(tmp_path: Path) -> None:
    dosya = tmp_path / "yanlislikla-eklenen-liste.xlsx"
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("yanlislikla-eklenen-liste.xlsx")]


def test_medya_klasoru_reddedilir(tmp_path: Path) -> None:
    # MEDIA_ROOT = DATA_DIR/media → paket içi yol backend/data/media/...
    dosya = tmp_path / "_internal" / "backend" / "data" / "media" / "ek.pdf"
    dosya.parent.mkdir(parents=True)
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("_internal/backend/data/media/ek.pdf")]


def test_kdbak_yedegi_reddedilir(tmp_path: Path) -> None:
    """Parolasız kurulumda `.kdbak` DÜZ SQLite baytlarıdır — pakete asla giremez."""
    dosya = tmp_path / "gunluk-2026-08-30.kdbak"
    dosya.touch()

    assert YASAK_DOSYALARI_BUL(tmp_path) == [Path("gunluk-2026-08-30.kdbak")]


def test_kullanici_durum_dosyalari_reddedilir(tmp_path: Path) -> None:
    """guvenlik.json parola sarmalı taşır; arşiv kopyaları ve damgalar da yasak."""
    for ad in ("guvenlik.json", "yedekleme.json", "surum.json", "guvenlik-arsiv-2026.json"):
        (tmp_path / ad).touch()

    bulunan = {yol.name for yol in YASAK_DOSYALARI_BUL(tmp_path)}
    assert bulunan == {
        "guvenlik.json",
        "yedekleme.json",
        "surum.json",
        "guvenlik-arsiv-2026.json",
    }


def test_paket_kapisi_depo_kapisinin_riskli_uzantilarini_kapsar() -> None:
    """F12 düzeltme turu: paket kapısı .csv, .db ve .xlsm'yi geçiriyordu."""
    depo = runpy.run_path(str(Path(__file__).parents[1] / "depo_sizintisi.py"))
    assert MODUL["YASAK_UZANTILAR"] == depo["RISKLI_UZANTILAR"]


def test_csv_db_ve_xlsm_reddedilir(tmp_path: Path) -> None:
    for ad in ("ogrenciler.csv", "eski.db", "liste.XLSM"):
        dosya = tmp_path / "_internal" / "backend" / "apps" / "okul" / ad
        dosya.parent.mkdir(parents=True, exist_ok=True)
        dosya.touch()

    assert {yol.name for yol in YASAK_DOSYALARI_BUL(tmp_path)} == {
        "ogrenciler.csv",
        "eski.db",
        "liste.XLSM",
    }


def test_windows_cp1252_konsolunda_turkce_mesaj_derlemeyi_kirmaz() -> None:
    sonuc = GUVENLI_METIN("Denetim başarılı.", "cp1252")

    assert sonuc == r"Denetim ba\u015far\u0131l\u0131."


# ---------------------------------------------------------------------------
# F12 — son arşivler ve iki platformun eşit kapsamı (`veri_sizintisi` ×2)
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
ARSIVDEKI_YASAKLAR = cast(Callable[[Path], list[str]], MODUL["arsivdeki_yasak_dosyalar"])
MAIN = cast(Callable[[list[str]], int], MODUL["main"])


def _tar(uyeler: dict[str, bytes], kip: str) -> bytes:
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode=kip) as tar:
        for ad, icerik in uyeler.items():
            bilgi = tarfile.TarInfo(ad)
            bilgi.size = len(icerik)
            tar.addfile(bilgi, io.BytesIO(icerik))
    return tampon.getvalue()


def _ar(uyeler: list[tuple[str, bytes]]) -> bytes:
    """Debian `.deb` kabı: ar imzası + her üyede 60 baytlık başlık."""
    veri = b"!<arch>\n"
    for ad, icerik in uyeler:
        baslik = f"{ad:<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(icerik):<10}`\n".encode()
        assert len(baslik) == 60
        veri += baslik + icerik + (b"\n" if len(icerik) % 2 else b"")
    return veri


def _deb(tmp_path: Path, veri_uyeleri: dict[str, bytes], *, sikistirma: str = "xz") -> Path:
    yol = tmp_path / "kutuphane-defteri_2026.10.0~beta.1_amd64.deb"
    yol.write_bytes(
        _ar(
            [
                ("debian-binary", b"2.0\n"),
                ("control.tar.xz", _tar({"./control": b"Package: x\n"}, "w:xz")),
                (f"data.tar.{sikistirma}", _tar(veri_uyeleri, f"w:{sikistirma}")),
            ]
        )
    )
    return yol


def test_zip_arsivindeki_veri_dosyasi_bulunur(tmp_path: Path) -> None:
    arsiv = tmp_path / "kutuphane-defteri-2026.10.0-beta.1-win64-portable.zip"
    with zipfile.ZipFile(arsiv, "w") as z:
        z.writestr("_internal/backend/templates/documents/base.html", "x")
        z.writestr("_internal/backend/data/db.sqlite3", "x")
        z.writestr("THIRD_PARTY_LICENSES/BENIOKU.txt", "x")

    assert ARSIVDEKI_YASAKLAR(arsiv) == ["_internal/backend/data/db.sqlite3"]


def test_tar_gz_arsivindeki_kullanici_durum_dosyasi_bulunur(tmp_path: Path) -> None:
    arsiv = tmp_path / "kutuphane-defteri-2026.10.0-beta.1-linux-x64.tar.gz"
    arsiv.write_bytes(
        _tar(
            {
                "kutuphane-defteri-2026.10.0-beta.1/kur.sh": b"#!/bin/sh\n",
                "kutuphane-defteri-2026.10.0-beta.1/uygulama/guvenlik.json": b"{}",
            },
            "w:gz",
        )
    )

    assert ARSIVDEKI_YASAKLAR(arsiv) == [
        "kutuphane-defteri-2026.10.0-beta.1/uygulama/guvenlik.json"
    ]


def test_deb_kabindaki_veri_arsivi_okunur(tmp_path: Path) -> None:
    """`.deb` bir ar kabıdır; kurulacak yollar data.tar.* içindedir (içerik açılmaz)."""
    temiz = _deb(tmp_path, {"./opt/kutuphane-defteri/LICENSE.txt": b"x"})
    assert ARSIVDEKI_YASAKLAR(temiz) == []

    kirli = _deb(
        tmp_path,
        {
            "./opt/kutuphane-defteri/LICENSE.txt": b"x",
            "./opt/kutuphane-defteri/_internal/gunluk-2026-09-27.kdbak": b"x",
        },
    )
    assert ARSIVDEKI_YASAKLAR(kirli) == [
        "data.tar.xz/opt/kutuphane-defteri/_internal/gunluk-2026-09-27.kdbak"
    ]


def test_okunamayan_arsiv_denetimi_durdurur(tmp_path: Path) -> None:
    """Fail-closed: zstd'li `.deb` ya da bozuk arşiv "temiz" sayılmaz, çıkış 2."""
    zstd = tmp_path / "zstd.deb"
    zstd.write_bytes(_ar([("debian-binary", b"2.0\n"), ("data.tar.zst", b"\x28\xb5\x2f\xfd")]))
    bozuk = tmp_path / "bozuk.zip"
    bozuk.write_bytes(b"zip degil")

    assert MAIN([str(zstd)]) == 2
    assert MAIN([str(bozuk)]) == 2


def test_komut_satiri_dizin_ve_arsivleri_birlikte_denetler(tmp_path: Path) -> None:
    paket = tmp_path / "kutuphane-defteri"
    (paket / "_internal").mkdir(parents=True)
    arsiv = tmp_path / "paket.zip"
    with zipfile.ZipFile(arsiv, "w") as z:
        z.writestr("_internal/VERSION", "x")

    assert MAIN([str(paket), str(arsiv)]) == 0
    with zipfile.ZipFile(arsiv, "a") as z:
        z.writestr("liste.xlsx", "x")
    assert MAIN([str(paket), str(arsiv)]) == 1
    assert MAIN([str(tmp_path / "yok")]) == 2


def _denetim_hedefleri(betik: str) -> list[str]:
    """Betikteki `veri_sizintisi.py` çağrılarının argümanları (satır sırasıyla, yorumlar hariç)."""
    hedefler: list[str] = []
    for satir in betik.splitlines():
        if satir.lstrip().startswith("#"):
            continue
        eslesme = re.search(r'veri_sizintisi\.py"?\)?\s+(.+)$', satir)
        if eslesme:
            hedefler.append(eslesme.group(1).strip())
    return hedefler


def test_iki_platform_esit_kapsamla_denetlenir() -> None:
    """Windows ve Linux: (1) PyInstaller paket dizini, (2) kullanıcıya giden son arşiv(ler).

    Yayın işi de iki platformun bütün son paketlerini AYNI betikle denetler.
    """
    linux = _denetim_hedefleri((REPO / "packaging/linux/build.sh").read_text(encoding="utf-8"))
    windows = _denetim_hedefleri(
        (REPO / "packaging/windows/build.ps1").read_text(encoding="utf-8-sig")
    )
    assert linux == ['"$PAKET_KOKU/kutuphane-defteri"', '"$CIKTI/$DEB_ADI" "$CIKTI/$TAR_ADI"']
    assert windows == ["$AppDir", "$zip"]
    yayin = (REPO / ".github/workflows/paketleme.yml").read_text(encoding="utf-8")
    assert "python3 packaging/veri_sizintisi.py yayin/*.deb yayin/*.tar.gz yayin/*.zip" in yayin


def test_setup_exe_icerigi_paket_dizini_ve_sabit_uc_dosyadir() -> None:
    """Inno arşivi listelenemez; içeriği `[Files]` kaynaklarıyla sınırlı kalmalı:
    denetlenmiş paket dizini + depodaki ikon, görev betiği ve WebView2 önyükleyicisi."""
    iss = (REPO / "packaging/windows/kutuphane-defteri.iss").read_text(encoding="utf-8")
    dosyalar = iss.split("[Files]", 1)[1].split("\n[", 1)[0]
    kaynaklar = set(re.findall(r'^Source: "([^"]+)"', dosyalar, flags=re.MULTILINE))
    assert kaynaklar == {
        r"{#SourceDir}\*",
        "{#AppIconSource}",
        "gorev-kur.ps1",
        "{#WebView2Setup}",
    }
