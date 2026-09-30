"""Dağıtım paketinde kullanıcı verisi bulunmadığını doğrula.

Bu denetim dosya içeriklerini okumadan yalnızca yolları inceler. Böylece hata
çıktısı da kişisel veri içermez.

İki katmanda koşar ve iki platformda KAPSAMI AYNIDIR (F12, `veri_sizintisi` ×2):

1. **Paket dizini** — PyInstaller çıktısı (lisans dosyaları kopyalandıktan
   sonra): `build.ps1` ve `build.sh` aynı dizini denetler.
2. **Son arşivler** — kullanıcıya giden dosyanın kendisi: Windows'ta taşınabilir
   `.zip`, Linux'ta `.deb` ve `.tar.gz`. Arşivin İÇİNE sonradan eklenenler (ör.
   `.deb`'deki `/usr/share/doc` ya da `.tar.gz`'deki `kur.sh`) ancak bu katmanda
   görünür. Arşiv içeriği açılmaz; yalnız üye ADLARI okunur. Inno kurulum dosyası
   (`setup.exe`) sıkıştırılmış biçimi yüzünden listelenemez: içeriği paket dizini
   ile `.iss` `[Files]` bölümündeki üç sabit depo dosyasıdır ve bu küme
   `packaging/tests/test_veri_sizintisi.py` ile sabitlenir.

Kullanım:

    python packaging/veri_sizintisi.py <paket-dizini> [arşiv.zip|.tar.gz|.deb ...]
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import BinaryIO

# .kdbak: programın yedek kapsayıcısı (parolasız kurulumda DÜZ SQLite baytları taşır).
# Küme depo kapısının `depo_sizintisi.RISKLI_UZANTILAR` kümesiyle AYNIDIR (F12 düzeltme
# turu: paket kapısı .csv, .db ve .xlsm'yi geçiriyordu — e-Okul ya da kişi dökümü
# CSV'si backend/apps altına düşse pakete girerdi). Eşitliği test sınar; meşru bir
# paket içeriği bu uzantıyı taşırsa ADIYLA muaf tutulur (joker yok).
YASAK_UZANTILAR = frozenset(
    {".sqlite", ".sqlite3", ".db", ".xls", ".xlsx", ".xlsm", ".csv", ".kdbak"}
)
# Medya DATA_DIR altındadır (paket içi yolu backend/data/media/...): ("data","media")
# çifti onu, ("backend","data") çifti geliştirme veri dizininin tamamını yakalar.
YASAK_DIZIN_CIFTLERI = frozenset(
    {
        ("backend", "data"),
        ("data", "media"),
    }
)
YASAK_SONLAR = (".sqlite3-shm", ".sqlite3-wal")
# Kullanıcı kurulumuna ait durum dosyaları — pakete girmeleri, geliştirme veri
# dizininin yanlışlıkla paketlendiğinin kanıtıdır (guvenlik.json parola sarmalı
# taşır; evrak şablonları gibi meşru paket içeriğini uzantı/çift kuralları zaten
# serbest bırakır).
YASAK_ADLAR = frozenset({"guvenlik.json", "yedekleme.json", "surum.json"})


def guvenli_metin(metin: str, encoding: str | None = None) -> str:
    """Konsolun kodlayamadığı karakterleri kaçış dizisine çevirir.

    GitHub Windows runner'ı stdout için CP1252 kullanabilir; bu kodlama Türkçe
    ``ş`` harfini içermez. Denetim başarıyla bittiği hâlde yalnız mesaj yazımı
    yüzünden derlemenin kırılmasını önler.
    """
    hedef = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return metin.encode(hedef, errors="backslashreplace").decode(hedef)


def yaz(metin: str) -> None:
    print(guvenli_metin(metin))


def yol_yasak_mi(goreli_yol: Path) -> bool:
    """Bir paket içi yolun kullanıcı verisi olma ihtimalini sınar."""
    parcalar = tuple(parca.casefold() for parca in goreli_yol.parts)
    ciftler = set(zip(parcalar, parcalar[1:], strict=False))
    ad = goreli_yol.name.casefold()

    return (
        bool(ciftler & YASAK_DIZIN_CIFTLERI)
        or goreli_yol.suffix.casefold() in YASAK_UZANTILAR
        or ad.endswith(YASAK_SONLAR)
        or ad in YASAK_ADLAR
        # Geri yüklemede kenara alınan güvenlik dosyası (backup_restore) — sarmal taşır.
        or ad.startswith("guvenlik-arsiv-")
    )


def yasak_dosyalari_bul(kok: Path) -> list[Path]:
    """Kök altındaki şüpheli veri dosyalarını göreli yollarıyla döndürür."""
    return sorted(
        (
            yol.relative_to(kok)
            for yol in kok.rglob("*")
            if yol.is_file() and yol_yasak_mi(yol.relative_to(kok))
        ),
        key=lambda yol: str(yol).casefold(),
    )


class ArsivHatasi(ValueError):
    """Arşiv okunamadı ya da biçimi tanınmadı (denetim fail-closed biter)."""


ARSIV_UZANTILARI = (".zip", ".tar.gz", ".tgz", ".deb")


def arsiv_mi(yol: Path) -> bool:
    """Yol, üye adları okunabilen bir paket arşivi mi (uzantıya göre)?"""
    return yol.name.casefold().endswith(ARSIV_UZANTILARI)


class _SinirliOkuyucu:
    """`ar` üyesini diske açmadan tarfile'a akış olarak veren okuyucu."""

    def __init__(self, kaynak: BinaryIO, boyut: int) -> None:
        self._kaynak = kaynak
        self._kalan = boyut

    def read(self, n: int = -1) -> bytes:
        if self._kalan <= 0:
            return b""
        if n < 0 or n > self._kalan:
            n = self._kalan
        veri = self._kaynak.read(n)
        self._kalan -= len(veri)
        return veri


def _tar_uyeleri(tar: tarfile.TarFile) -> Iterator[str]:
    for uye in tar:
        if not uye.isdir():
            yield uye.name


def _deb_uyeleri(yol: Path) -> Iterator[str]:
    """`.deb` (ar kabı) içindeki `data.tar.*` ve `control.tar.*` üyelerinin adları.

    Standart kitaplıkta `ar` okuyucu yoktur; biçim sabittir (8 baytlık imza, her
    üyede 60 baytlık başlık, tek boyutlu üyeler bir baytla hizalanır). Sıkıştırma
    xz/gz/bz2 olabilir; zstd tanınmaz ve denetim DURUR (sessizce geçilmez).
    """
    with yol.open("rb") as akis:
        if akis.read(8) != b"!<arch>\n":
            raise ArsivHatasi(f"{yol.name}: .deb (ar) imzası yok")
        while True:
            baslik = akis.read(60)
            if len(baslik) < 60:
                return
            ad = baslik[:16].decode("ascii", errors="replace").strip().rstrip("/")
            try:
                boyut = int(baslik[48:58].decode("ascii").strip())
            except ValueError as exc:
                raise ArsivHatasi(f"{yol.name}: bozuk ar başlığı") from exc
            baslangic = akis.tell()
            if ad.startswith(("data.tar", "control.tar")):
                if ad.endswith(".zst"):
                    raise ArsivHatasi(f"{yol.name}: {ad} zstd ile sıkıştırılmış; denetlenemiyor")
                okuyucu = _SinirliOkuyucu(akis, boyut)
                with tarfile.open(fileobj=okuyucu, mode="r|*") as tar:  # type: ignore[call-overload]
                    for uye_adi in _tar_uyeleri(tar):
                        yield f"{ad}/{uye_adi}"
            akis.seek(baslangic + boyut + (boyut % 2))


def arsiv_uyeleri(yol: Path) -> Iterator[str]:
    """Arşivdeki dosya üyelerinin adları (dizin girdileri hariç, içerik okunmaz)."""
    ad = yol.name.casefold()
    try:
        if ad.endswith(".zip"):
            with zipfile.ZipFile(yol) as arsiv:
                yield from (uye for uye in arsiv.namelist() if not uye.endswith("/"))
        elif ad.endswith((".tar.gz", ".tgz")):
            with tarfile.open(yol, mode="r:*") as tar:
                yield from _tar_uyeleri(tar)
        elif ad.endswith(".deb"):
            yield from _deb_uyeleri(yol)
        else:
            raise ArsivHatasi(f"{yol.name}: tanınmayan arşiv türü")
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise ArsivHatasi(f"{yol.name}: arşiv okunamadı ({type(exc).__name__})") from exc


def arsivdeki_yasak_dosyalar(yol: Path) -> list[str]:
    """Arşivdeki şüpheli veri dosyalarının arşiv içi yolları (POSIX, sıralı)."""
    bulunan: set[str] = set()
    for uye in arsiv_uyeleri(yol):
        goreli = uye.removeprefix("./")
        # `.deb` üyesi "data.tar.xz/./opt/..." biçimindedir: kap adı yolun parçası
        # sayılmaz, yalnız paketin kuracağı yol denetlenir.
        if "/" in goreli and goreli.split("/", 1)[0].startswith(("data.tar", "control.tar")):
            kap, ic = goreli.split("/", 1)
            ic = ic.removeprefix("./")
            if ic and yol_yasak_mi(Path(ic)):
                bulunan.add(f"{kap}/{ic}")
            continue
        if goreli and yol_yasak_mi(Path(goreli)):
            bulunan.add(goreli)
    return sorted(bulunan, key=str.casefold)


def argumanlari_ayristir(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Komut satırı argümanlarını ayrıştırır."""
    parser = argparse.ArgumentParser(
        description="Dağıtım paketinde kullanıcı verisi bulunmadığını denetler."
    )
    parser.add_argument(
        "hedefler",
        type=Path,
        nargs="+",
        help="Denetlenecek paket dizini ve/veya arşivler (.zip, .tar.gz, .deb)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Komut satırı giriş noktası."""
    args = argumanlari_ayristir(argv)
    hedefler: list[Path] = args.hedefler

    bulgular: list[tuple[Path, list[str]]] = []
    for hedef in hedefler:
        if hedef.is_dir():
            bulgular.append((hedef, [yol.as_posix() for yol in yasak_dosyalari_bul(hedef)]))
        elif hedef.is_file() and arsiv_mi(hedef):
            try:
                bulgular.append((hedef, arsivdeki_yasak_dosyalar(hedef)))
            except ArsivHatasi as exc:
                yaz(f"HATA: {exc}")
                return 2
        else:
            yaz(f"HATA: paket dizini ya da arşivi bulunamadı: {hedef}")
            return 2

    kirli = [(hedef, yollar) for hedef, yollar in bulgular if yollar]
    if kirli:
        yaz("HATA: pakette kullanıcı verisi olabilecek dosyalar bulundu:")
        for hedef, yollar in kirli:
            for yol in yollar:
                yaz(f"  - {hedef.name}: {yol}")
        return 1

    adlar = ", ".join(hedef.name for hedef in hedefler)
    yaz(f"Paket veri denetimi başarılı ({adlar}): kullanıcı veri dosyası bulunmadı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
