"""Üçüncü taraf lisansları: THIRD_PARTY_LICENSES üretimi ve paket denetimi (F12, TB28).

Kütüphane Defteri'nin kendi kodu PolyForm Noncommercial'dır (`LICENSE`); pakete
giren her üçüncü taraf bileşenin adı, sürümü, lisansı ve lisans METNİ depo
kökündeki `THIRD_PARTY_LICENSES/` dizininde durur ve kurulum paketine girer.
Dizin ELLE yazılmaz; bu betik üretir. Üç alt komut:

``uret``
    Depodaki `THIRD_PARTY_LICENSES/` dizinini üretir. Geliştirme kabında koşar
    (backend imajı) ve ağ ister: yalnız paket ortamında kurulan dağıtımların
    (pywebview, pystray, pythonnet, PySide6 …) üstverisi PyPI'dan, lisans
    dosyaları tekerlek ya da kaynak arşivinden okunur. Ön yüz girdisi
    `on_yuz_paketleri.mjs`'nin JSON çıktısıdır. Sarmalayıcı: `uret.sh`.

``paket``
    Derlenmiş paketin GERÇEKTEN içerdiği bileşenleri denetler ve lisans dizinini
    pakete koyar. Derleme ortamında, PyInstaller'dan hemen sonra koşar (yalnız
    standart kitaplık): PyInstaller'ın ara çıktısındaki TOC dosyalarından pakete
    giren her dosyanın kaynağı okunur ve sınıflandırılır — kurulu bir Python
    dağıtımı (RECORD), Python'un kendisi, depo dosyası, Windows'ta MSYS2 paketi
    (pacman yerel veritabanı), Linux'ta Debian paketi (dpkg). Listede olmayan
    dağıtım, sahibi bilinmeyen dosya, yalnız GPL'li yerel kütüphane (bilinen ad
    listesi; MSYS2'de paketin SPDX lisansı) ya da Qt'nin yalnız GPL'li bir modülü
    (dosya düzeyinde: kitaplık, bağlayıcı, QML dizini ve onlara bağlanan her ELF)
    derlemeyi DURDURUR. Çağıran: build.ps1, build.sh.

``kisitlar``
    Paket ortamının pip kısıt dosyasını (`-c`) listedeki sürümlerden yazar: pakete
    giren geçişli bağımlılıklar listedeki sürümle kurulur, `BENIOKU.txt` ile
    `paket-icerigi.txt` aynı sürümü söyler (build.ps1, build.sh).

``npm-denetle``
    `on_yuz_paketleri.mjs` çıktısını (Vite çıktısına GERÇEKTEN giren npm paketleri)
    listedeki npm kayıtlarıyla ad ve sürüm düzeyinde karşılaştırır (scripts/gates.sh).

``deb-copyright``
    `.deb` için DEP-5 biçimli `copyright` dosyasını yazar (build.sh).

Kapı testi: `packaging/tests/test_lisans_kapisi.py` (her bağımlılık listede mi,
yalnız GPL'li bileşen var mı, dosyalar eksiksiz mi).
"""

from __future__ import annotations

import argparse
import ast
import email
import email.message
import importlib.metadata as im
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LISANS_DIZINI = REPO / "THIRD_PARTY_LICENSES"
DIZIN_DOSYASI = "bilesenler.json"
BENIOKU_ADI = "BENIOKU.txt"
PAKET_ICERIGI_ADI = "paket-icerigi.txt"
YEREL_DIZIN_ADI = "yerel-kutuphaneler"
PLATFORMLAR = ("linux", "windows")

BACKEND_GEREKSINIMLERI = REPO / "backend" / "requirements.txt"
PAKETLEME_GEREKSINIMLERI = REPO / "packaging" / "requirements-paketleme.txt"

UST_BILGI = (
    "Kütüphane Defteri ile dağıtılan üçüncü taraf bileşenler. Üretildi: "
    "packaging/lisanslar/uret.sh — elle düzenlenmez."
)


# =============================================================================
# Ortak yardımcılar
# =============================================================================


def normal_ad(ad: str) -> str:
    """PEP 503 ad normalleştirmesi (`Foo_Bar.baz` → `foo-bar-baz`)."""
    return re.sub(r"[-_.]+", "-", ad).lower()


def yaz(metin: str) -> None:
    """Konsol kodlamasına dayanıklı yazdırma (Windows koşucusu CP1252 olabilir)."""
    kodlama = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(metin.encode(kodlama, errors="backslashreplace").decode(kodlama), flush=True)


def uyar(metin: str) -> None:
    """Derleme uyarısı; GitHub Actions'ta açıklama satırı olarak görünür."""
    onek = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "UYARI: "
    yaz(onek + metin)


# ----------------------------------------------------------------- SPDX / GPL

_SPDX_ATOM = re.compile(r"\(|\)|[A-Za-z0-9.+:-]+")
_GUCLU_COPYLEFT = re.compile(r"^(A?GPL)-\d", re.IGNORECASE)


class SpdxHatasi(ValueError):
    """Lisans ifadesi ayrıştırılamadı."""


def _spdx_parcala(ifade: str) -> list[str]:
    parcalar = _SPDX_ATOM.findall(ifade)
    if "".join(parcalar) != re.sub(r"\s+", "", ifade):
        raise SpdxHatasi(f"lisans ifadesi ayrıştırılamadı: {ifade!r}")
    return parcalar


def gpl_yalniz_mi(ifade: str) -> bool:
    """SPDX ifadesi yalnız güçlü copyleft (GPL/AGPL, istisnasız) seçenek mi bırakıyor?

    Kural: `A OR B` → ikisi de GPL ise GPL; `A AND B` → biri GPL ise GPL;
    `X WITH istisna` → GPL SAYILMAZ (PyInstaller önyükleyicisi, GCC çalışma anı
    istisnası bu yüzden izinlidir); LGPL ve MPL copyleft'tir ama "GPL" değildir.
    Ürün PolyForm Noncommercial'dır ve GPLv3 dağıtılan bütüne ek kısıtlamayı
    yasakladığı için yalnız GPL'li bir bileşen pakete GİREMEZ.
    """
    jetonlar = _spdx_parcala(ifade)
    konum = 0

    def ifade_oku() -> bool:
        nonlocal konum
        sonuc = ve_oku()
        while konum < len(jetonlar) and jetonlar[konum].upper() == "OR":
            konum += 1
            sag = ve_oku()
            sonuc = sonuc and sag
        return sonuc

    def ve_oku() -> bool:
        nonlocal konum
        sonuc = terim_oku()
        while konum < len(jetonlar) and jetonlar[konum].upper() == "AND":
            konum += 1
            sag = terim_oku()
            sonuc = sonuc or sag
        return sonuc

    def terim_oku() -> bool:
        nonlocal konum
        if konum >= len(jetonlar):
            raise SpdxHatasi(f"eksik lisans ifadesi: {ifade!r}")
        jeton = jetonlar[konum]
        konum += 1
        if jeton == "(":
            ic = ifade_oku()
            if konum >= len(jetonlar) or jetonlar[konum] != ")":
                raise SpdxHatasi(f"kapanmayan parantez: {ifade!r}")
            konum += 1
            return ic
        if jeton.upper() in {"AND", "OR", "WITH", ")"}:
            raise SpdxHatasi(f"beklenmeyen {jeton!r}: {ifade!r}")
        if konum < len(jetonlar) and jetonlar[konum].upper() == "WITH":
            konum += 2  # istisna adı
            return False
        return bool(_GUCLU_COPYLEFT.match(jeton))

    sonuc = ifade_oku()
    if konum != len(jetonlar):
        raise SpdxHatasi(f"fazla jeton: {ifade!r}")
    return sonuc


def secenekler(ifade: str) -> list[str]:
    """Üst düzey `OR` seçenekleri (parantez içindekiler bölünmez)."""
    derinlik = 0
    parcalar: list[list[str]] = [[]]
    for jeton in _spdx_parcala(ifade):
        if jeton == "(":
            derinlik += 1
        elif jeton == ")":
            derinlik -= 1
        if derinlik == 0 and jeton.upper() == "OR":
            parcalar.append([])
            continue
        parcalar[-1].append(jeton)
    return [" ".join(p).replace("( ", "(").replace(" )", ")") for p in parcalar]


# -------------------------------------------------------------- dizin kayıtları


@dataclass
class Bilesen:
    """`bilesenler.json`'daki bir kayıt."""

    ad: str
    surum: str
    tur: str  # python | npm | calisma-zamani | yazi-tipi | ikili
    platformlar: list[str]
    lisans: str  # SPDX ifadesi
    dosyalar: list[str]
    kaynak: str = ""
    secilen: str = ""  # çok lisanslı bileşende seçilen seçenek
    aciklama: str = ""
    kaynagi_pakette: bool = False  # LGPL: kaynak kodu pakete kaynak dosya olarak girer

    @property
    def etkin_lisans(self) -> str:
        return self.secilen or self.lisans

    def sozluk(self) -> dict[str, Any]:
        veri: dict[str, Any] = {
            "ad": self.ad,
            "surum": self.surum,
            "tur": self.tur,
            "platformlar": sorted(self.platformlar),
            "lisans": self.lisans,
            "dosyalar": self.dosyalar,
        }
        for anahtar in ("secilen", "kaynak", "aciklama"):
            deger = getattr(self, anahtar)
            if deger:
                veri[anahtar] = deger
        if self.kaynagi_pakette:
            veri["kaynagi_pakette"] = True
        return veri


def bilesenleri_oku(dizin: Path = LISANS_DIZINI) -> list[Bilesen]:
    """`bilesenler.json`'u okur."""
    veri = json.loads((dizin / DIZIN_DOSYASI).read_text(encoding="utf-8"))
    return [
        Bilesen(
            ad=k["ad"],
            surum=k["surum"],
            tur=k["tur"],
            platformlar=list(k["platformlar"]),
            lisans=k["lisans"],
            dosyalar=list(k["dosyalar"]),
            kaynak=k.get("kaynak", ""),
            secilen=k.get("secilen", ""),
            aciklama=k.get("aciklama", ""),
            kaynagi_pakette=bool(k.get("kaynagi_pakette", False)),
        )
        for k in veri["bilesenler"]
    ]


_PIN = re.compile(
    r'^\s*([A-Za-z0-9_.\-]+)==(\S+?)\s*(?:;\s*sys_platform\s*==\s*"([^"]+)")?\s*(?:#.*)?$'
)
_ISARET_PLATFORM = {"win32": "windows", "linux": "linux"}


def pinler(dosya: Path) -> list[tuple[str, str, tuple[str, ...]]]:
    """Gereksinim dosyasındaki pinler: (ad, sürüm, platformlar)."""
    sonuc: list[tuple[str, str, tuple[str, ...]]] = []
    for satir in dosya.read_text(encoding="utf-8").splitlines():
        if not satir.strip() or satir.lstrip().startswith("#"):
            continue
        eslesme = _PIN.match(satir)
        if eslesme is None:
            raise ValueError(f"{dosya.name}: anlaşılamayan satır: {satir!r}")
        ad, surum, isaret = eslesme.groups()
        platformlar = (_ISARET_PLATFORM[isaret],) if isaret else PLATFORMLAR
        sonuc.append((ad, surum, platformlar))
    return sonuc


def _guvenli_ad(metin: str) -> str:
    return re.sub(r"[^A-Za-z0-9.+_-]+", "-", metin).strip("-")


def _metin_coz(veri: bytes) -> str:
    try:
        metin = veri.decode("utf-8")
    except UnicodeDecodeError:
        metin = veri.decode("latin-1")
    metin = metin.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    return metin if metin.endswith("\n") else metin + "\n"


# =============================================================================
# uret — depodaki THIRD_PARTY_LICENSES/ dizini
# =============================================================================

#: Üstverisinde SPDX `License-Expression` taşımayan dağıtımların lisansı. Her
#: satır lisans DOSYASI okunarak yazıldı (27.09.2026); üstveri SPDX ifadesi
#: taşıyorsa bu tablo kullanılmaz. Eksik kalan dağıtımda üretici DURUR.
LISANS_DUZELTMELERI: dict[str, str] = {
    "cssselect2": "BSD-3-Clause",
    "djangorestframework": "BSD-3-Clause",
    "et-xmlfile": "MIT",
    "fonttools": "MIT",
    "brotli": "MIT",
    "openpyxl": "MIT",
    "pydyf": "BSD-3-Clause",
    "pyphen": "GPL-2.0-or-later OR LGPL-2.1-or-later OR MPL-1.1",
    "segno": "BSD-3-Clause",
    "sqlparse": "BSD-3-Clause",
    "tinycss2": "BSD-3-Clause",
    "tinyhtml5": "MIT",
    "waitress": "ZPL-2.1",
    "weasyprint": "BSD-3-Clause",
    "webencodings": "BSD-3-Clause",
    "xlrd": "BSD-3-Clause",
    "zopfli": "Apache-2.0",
    "asgiref": "BSD-3-Clause",
    # --- yalnız paket ortamında kurulanlar ---
    "pywebview": "BSD-3-Clause",
    "bottle": "MIT",
    "proxy-tools": "MIT",
    "pythonnet": "MIT",
    "clr-loader": "MIT",
    "pystray": "LGPL-3.0-or-later",
    "six": "MIT",
    "qtpy": "MIT",
    "tzdata": "Apache-2.0",
    "setuptools": "MIT",
    # Pakete YALNIZ önyükleyici + loader (Bootloader Exception) ve çalışma anı
    # kancaları + fake-modules (Apache-2.0) girer; derleme kodu girmez
    # (IZINLI_ALT_YOLLAR, derleme sonrası denetim).
    "pyinstaller": "GPL-2.0-or-later WITH Bootloader-exception AND Apache-2.0",
    # Yalnız rthooks/ (Apache-2.0) girer; standart kancalar GPL-2.0+'dır, girmez.
    "pyinstaller-hooks-contrib": "Apache-2.0",
    "pyside6": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
    "pyside6-essentials": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
    "pyside6-addons": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
    "shiboken6": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
}

#: Çok lisanslı bileşende bu ürünün kullandığı seçenek (yalnız GPL olmayan).
SECILEN_LISANSLAR: dict[str, str] = {
    "pyphen": "MPL-1.1",
    "pyside6": "LGPL-3.0-only",
    "pyside6-essentials": "LGPL-3.0-only",
    "pyside6-addons": "LGPL-3.0-only",
    "shiboken6": "LGPL-3.0-only",
    "cryptography": "Apache-2.0",
}

#: Tekerleği yüzlerce MB olan (Qt ikilileri) ve lisans METNİ taşımayan dağıtımlar:
#: üstveri PyPI JSON'undan okunur, metin ortak LGPL/GPL dosyalarından verilir
#: (packaging/README.md "Lisans: PySide6 LGPLv3").
BUYUK_DAGITIMLAR = frozenset({"pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"})

#: Lisans metni dağıtımda bulunmayan ya da ortak metinle verilen dağıtımlar.
ORTAK_METIN = {
    "pystray": ("LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"),
    "pyside6": ("LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"),
    "pyside6-essentials": ("LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"),
    "pyside6-addons": ("LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"),
    "shiboken6": ("LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"),
}

#: Lisansı üstveride bildirilen ama dağıtımında lisans dosyası OLMAYANLAR: metin
#: standart şablondan, telif satırı üstverideki yazardan üretilir.
URETILEN_LISANS: dict[str, tuple[str, str]] = {
    "proxy-tools": ("MIT", "Copyright (c) Jonathan Tushman"),
}

#: Pakete kendisi girer ama bağımlılıkları GİRMEZ (derleme araçları).
OZYINELENMEYEN = frozenset({"pyinstaller", "pyinstaller-hooks-contrib", "setuptools"})

#: Pinlenmemiş ama pakete giren dağıtımlar (ad, platformlar, gerekçe).
EK_KOKLER: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "pyinstaller-hooks-contrib",
        PLATFORMLAR,
        "PyInstaller'ın çalışma anı kancaları (ör. pythonnet) pakete girer",
    ),
    (
        "setuptools",
        PLATFORMLAR,
        "cffi'nin derleme yardımcısı (`cffi._shimmed_dist_utils`) üzerinden pakete girer",
    ),
)

#: Lisans adı taşımayan ama lisans bildirimi olan, pakete giren dosyalar. pyphen'in
#: heceleme sözlükleri tek tek lisanslıdır (bir kısmı yalnız GPL); spec yalnız
#: en_US sözlüğünü paketler, onun bildirimi README'dedir.
EK_LISANS_DOSYALARI: dict[str, tuple[str, ...]] = {
    "pyphen": ("pyphen/dictionaries/README_hyph_en_US.txt",),
}

#: Kaynak kodu pakete KAYNAK DOSYA olarak giren LGPL dağıtımları (spec
#: `module_collection_mode`): kullanıcı kütüphaneyi değiştirebilir (LGPLv3 §4).
KAYNAGI_PAKETTE = frozenset({"pystray"})

ACIKLAMALAR: dict[str, str] = {
    "django": "Uygulama çatısı",
    "djangorestframework": "Yönetim API'si",
    "weasyprint": "Evrak (PDF) üretimi",
    "openpyxl": "Excel içe/dışa aktarma",
    "xlrd": "e-Okul .xls okuma",
    "cryptography": "Alan şifrelemesi, şifreli yedek",
    "argon2-cffi": "Yönetici parolası (Argon2id)",
    "waitress": "Yerel sunucular",
    "segno": "Etiketteki QR",
    "pywebview": "Program penceresi",
    "pythonnet": "Windows pencere motoru köprüsü (WebView2)",
    "pystray": "Windows sistem tepsisi",
    "pyside6": "Linux penceresi ve tepsisi (Qt 6)",
    "pyside6-essentials": "Qt 6 kitaplıkları",
    "pyside6-addons": "Qt 6 WebEngine",
    "shiboken6": "Qt 6 Python bağlayıcısı",
    "qtpy": "Qt bağlayıcı katmanı",
    "pyinstaller": (
        "Paketleyici; yalnız önyükleyici, loader ve çalışma anı kancaları pakete girer "
        "(derleme kodu girmez)"
    ),
    "pyinstaller-hooks-contrib": (
        "Yalnız çalışma anı kancaları (rthooks, Apache-2.0) pakete girer; "
        "standart kancalar (GPL-2.0+) girmez"
    ),
    "setuptools": "cffi derleme yardımcısı (çalışma anında kullanılmaz)",
    "pillow": "Görüntü işleme",
    "pypdf": "PDF okuma/birleştirme",
    "fonttools": "PDF yazı tipi alt kümeleme",
    "pyphen": "Heceleme (yalnız en_US sözlüğü paketlenir)",
    "tzdata": "Windows'ta saat dilimi verisi",
}

_ORTAMLAR: dict[str, dict[str, str]] = {
    "linux": {
        "sys_platform": "linux",
        "platform_system": "Linux",
        "os_name": "posix",
        "platform_machine": "x86_64",
    },
    "windows": {
        "sys_platform": "win32",
        "platform_system": "Windows",
        "os_name": "nt",
        "platform_machine": "AMD64",
    },
}
_ORTAK_ORTAM = {
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "python_version": "3.12",
    "python_full_version": "3.12.10",
    "implementation_version": "3.12.10",
    "platform_release": "",
    "platform_version": "",
}
_PIP_PLATFORM = {
    "windows": ("win_amd64",),
    "linux": ("manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64"),
}
_LISANS_ADI = re.compile(r"^(licen[cs]e|copying|notice|copyright)([._-].*)?$", re.IGNORECASE)
_KOD_UZANTILARI = frozenset({".py", ".pyc", ".pyi", ".so", ".pyd", ".dll", ".js", ".json"})

MIT_METNI = """\
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def lisans_dosyasi_mi(goreli: str) -> bool:
    """Arşiv/dağıtım içi yol bir lisans ya da bildirim dosyası mı?"""
    yol = PurePosixPath(goreli)
    if "__pycache__" in yol.parts or yol.suffix.lower() in _KOD_UZANTILARI:
        return False
    return bool(_LISANS_ADI.match(yol.name))


def _dosya_etiketi(goreli: str) -> str:
    """Dağıtım içi yoldan okunur dosya etiketi.

    Yalnız KÖKTEKİ `*.dist-info/` (ve altındaki `licenses/`) öneki atılır; paketin
    içine gömülmüş başka dağıtımların (ör. setuptools/_vendor/…dist-info) yolu
    korunur, yoksa hepsi "LICENSE" adında çakışırdı.
    """
    parcalar = list(PurePosixPath(goreli).parts)
    if parcalar and parcalar[0].endswith((".dist-info", ".egg-info")):
        parcalar = parcalar[1:]
        if len(parcalar) > 1 and parcalar[0] == "licenses":
            parcalar = parcalar[1:]
    return _guvenli_ad("_".join(parcalar))


def _txt(ad: str) -> str:
    return ad if ad.lower().endswith(".txt") else ad + ".txt"


@dataclass
class _DagitimBilgisi:
    ad: str
    surum: str
    gereksinimler: list[str]
    lisans_ifadesi: str
    yazar: str
    dosyalar: list[tuple[str, bytes]]


@dataclass
class _Cozulen:
    bilgi: _DagitimBilgisi
    platformlar: set[str] = field(default_factory=set)


class Uretici:
    """Python dağıtımlarını çözer ve lisans dosyalarını toplar (ağ gerekir)."""

    def __init__(self, on_bellek: Path) -> None:
        self.on_bellek = on_bellek
        self._bilgiler: dict[tuple[str, str], _DagitimBilgisi] = {}
        self._surumler: dict[str, list[str]] = {}

    # ----------------------------------------------------------- ağ yardımcıları
    @staticmethod
    def _json(adres: str) -> Any:
        istek = urllib.request.Request(  # noqa: S310 — yalnız sabit https://pypi.org adresleri
            adres, headers={"User-Agent": "kd-lisans-uretici"}
        )
        with urllib.request.urlopen(istek, timeout=60) as yanit:  # noqa: S310 — sabit PyPI adresi
            return json.loads(yanit.read().decode("utf-8"))

    def _pip_indir(self, ad: str, surum: str, platform: str, *, kaynak: bool) -> Path | None:
        """Tekerleği (kaynak=False) ya da kaynak arşivini (kaynak=True) indirir."""
        hedef = Path(tempfile.mkdtemp(dir=self.on_bellek))
        komut = [sys.executable, "-m", "pip", "download", "--no-deps", "-q"]
        komut += ["--disable-pip-version-check", "-d", str(hedef), f"{ad}=={surum}"]
        if kaynak:
            komut += ["--no-binary=:all:"]
        else:
            komut += ["--only-binary=:all:", "--python-version", "3.12", "--implementation", "cp"]
            for etiket in _PIP_PLATFORM[platform]:
                komut += ["--platform", etiket]
        sonuc = subprocess.run(komut, capture_output=True, text=True, check=False)  # noqa: S603
        arsivler = sorted(hedef.iterdir())
        return arsivler[0] if sonuc.returncode == 0 and arsivler else None

    # ------------------------------------------------------------- üstveri
    def surum_sec(self, ad: str, belirtec: Any) -> str:
        """Pinlenmemiş dağıtımda sürüm: kurulu sürüm uyuyorsa o, yoksa PyPI'daki en yeni."""
        from packaging.version import InvalidVersion, Version

        try:
            kurulu = im.distribution(ad).version
        except im.PackageNotFoundError:
            kurulu = None
        if kurulu is not None and belirtec.contains(kurulu, prereleases=True):
            return kurulu
        n = normal_ad(ad)
        if n not in self._surumler:
            veri = self._json(f"https://pypi.org/pypi/{ad}/json")
            uygun: list[str] = []
            for surum, dosyalar in veri["releases"].items():
                if not dosyalar or all(d.get("yanked") for d in dosyalar):
                    continue
                try:
                    if Version(surum).is_prerelease:
                        continue
                except InvalidVersion:
                    continue
                uygun.append(surum)
            self._surumler[n] = uygun
        adaylar = [s for s in self._surumler[n] if belirtec.contains(s)]
        if not adaylar:
            raise SystemExit(f"HATA: {ad} için {belirtec} koşulunu karşılayan sürüm yok.")
        return str(max(adaylar, key=Version))

    def bilgi(self, ad: str, surum: str, platform: str) -> _DagitimBilgisi:
        anahtar = (normal_ad(ad), surum)
        if anahtar not in self._bilgiler:
            self._bilgiler[anahtar] = self._bilgi_bul(ad, surum, platform)
        return self._bilgiler[anahtar]

    def _bilgi_bul(self, ad: str, surum: str, platform: str) -> _DagitimBilgisi:
        n = normal_ad(ad)
        try:
            kurulu: im.Distribution | None = im.distribution(ad)
        except im.PackageNotFoundError:
            kurulu = None
        if kurulu is not None and kurulu.version == surum:
            md = kurulu.metadata
            ekler = EK_LISANS_DOSYALARI.get(n, ())
            dosyalar = [
                (str(dosya), Path(dosya.locate()).read_bytes())
                for dosya in kurulu.files or []
                if (lisans_dosyasi_mi(str(dosya)) or str(dosya) in ekler)
                and Path(dosya.locate()).is_file()
            ]
            if ekler and not {str(d) for d in kurulu.files or []} >= set(ekler):
                raise SystemExit(f"HATA: {ad} {surum} içinde beklenen dosya yok: {ekler}")
            return _DagitimBilgisi(
                ad=md["Name"],
                surum=surum,
                gereksinimler=list(md.get_all("Requires-Dist") or []),
                lisans_ifadesi=md.get("License-Expression") or "",
                yazar=md.get("Author") or "",
                dosyalar=sorted(dosyalar),
            )
        if n in BUYUK_DAGITIMLAR:
            pypi = self._json(f"https://pypi.org/pypi/{ad}/{surum}/json")["info"]
            return _DagitimBilgisi(
                ad=str(pypi["name"]),
                surum=surum,
                gereksinimler=[str(g) for g in pypi.get("requires_dist") or []],
                lisans_ifadesi=str(pypi.get("license_expression") or ""),
                yazar=str(pypi.get("author") or ""),
                dosyalar=[],
            )
        arsiv = self._pip_indir(ad, surum, platform, kaynak=False) or self._pip_indir(
            ad, surum, platform, kaynak=True
        )
        if arsiv is None:
            raise SystemExit(f"HATA: {ad}=={surum} indirilemedi (ağ?).")
        bilgi = _arsivden_bilgi(arsiv, surum)
        if not bilgi.dosyalar and arsiv.suffix == ".whl":
            # Bazı tekerlekler (pythonnet, clr_loader) lisans dosyasını taşımaz;
            # aynı sürümün kaynak arşivi taşır.
            kaynak = self._pip_indir(ad, surum, platform, kaynak=True)
            if kaynak is not None:
                bilgi.dosyalar = _arsivden_bilgi(kaynak, surum).dosyalar
        return bilgi

    # -------------------------------------------------------------- çözüm
    def coz(self) -> dict[str, _Cozulen]:
        """Backend + paketleme pinlerinden iki platformun bağımlılık kapanışı."""
        from packaging.requirements import Requirement
        from packaging.specifiers import SpecifierSet

        kuyruk: list[tuple[str, Any, frozenset[str], str, bool]] = []
        for dosya in (BACKEND_GEREKSINIMLERI, PAKETLEME_GEREKSINIMLERI):
            for ad, surum, platformlar in pinler(dosya):
                for platform in platformlar:
                    kuyruk.append((ad, SpecifierSet(f"=={surum}"), frozenset(), platform, True))
        for ad, platformlar, _gerekce in EK_KOKLER:
            for platform in platformlar:
                kuyruk.append((ad, SpecifierSet(), frozenset(), platform, False))

        secilen: dict[str, str] = {}
        sonuc: dict[str, _Cozulen] = {}
        islenen: set[tuple[str, str, frozenset[str]]] = set()
        while kuyruk:
            ad, belirtec, ekler, platform, ozyinele = kuyruk.pop(0)
            n = normal_ad(ad)
            secili = secilen.get(n)
            if secili is None:
                secili = self.surum_sec(ad, belirtec)
                secilen[n] = secili
            elif not belirtec.contains(secili, prereleases=True):
                raise SystemExit(
                    f"HATA: sürüm çakışması: {ad} {secili} seçildi, {belirtec} isteniyor."
                )
            bilgi = self.bilgi(ad, secili, platform)
            kayit = sonuc.setdefault(n, _Cozulen(bilgi=bilgi))
            kayit.platformlar.add(platform)
            anahtar = (n, platform, ekler)
            if anahtar in islenen or not ozyinele or n in OZYINELENMEYEN:
                continue
            islenen.add(anahtar)
            ortam = {**_ORTAK_ORTAM, **_ORTAMLAR[platform]}
            for ham in bilgi.gereksinimler:
                istek = Requirement(ham)
                if istek.marker is not None and not any(
                    istek.marker.evaluate({**ortam, "extra": ek}) for ek in (ekler or {""})
                ):
                    continue
                kuyruk.append(
                    (istek.name, istek.specifier, frozenset(istek.extras), platform, True)
                )
        return sonuc


def _arsivden_bilgi(arsiv: Path, surum: str) -> _DagitimBilgisi:
    """Tekerlek (.whl) ya da kaynak arşivinden (.tar.gz/.zip) üstveri + lisans dosyaları."""
    uyeler: dict[str, bytes] = {}
    if arsiv.suffix == ".whl" or arsiv.suffix == ".zip":
        with zipfile.ZipFile(arsiv) as z:
            for ad in z.namelist():
                if not ad.endswith("/"):
                    uyeler[ad] = z.read(ad)
    else:
        with tarfile.open(arsiv, "r:*") as t:
            for uye in t.getmembers():
                akis = t.extractfile(uye) if uye.isfile() else None
                if akis is not None:
                    uyeler[uye.name] = akis.read()
    if arsiv.suffix == ".whl":
        ust_ad = next(a for a in uyeler if a.endswith(".dist-info/METADATA"))
        lisanslar = [(a, v) for a, v in uyeler.items() if lisans_dosyasi_mi(a)]
    else:
        ust_ad = min((a for a in uyeler if a.endswith("/PKG-INFO")), key=len)
        kok = ust_ad.rsplit("/", 1)[0] + "/"

        def kok_lisansi(ad: str) -> bool:
            # Kaynak arşivinde yalnız kök dizindeki ya da LICENSES/ altındaki
            # dosyalar sayılır (testlerin ve belgelerin örnek lisansları değil).
            parcalar = ad[len(kok) :].split("/")
            return len(parcalar) == 1 or (len(parcalar) == 2 and parcalar[0].upper() == "LICENSES")

        lisanslar = [
            (a[len(kok) :], v)
            for a, v in uyeler.items()
            if a.startswith(kok) and kok_lisansi(a) and lisans_dosyasi_mi(a)
        ]
    md = email.message_from_bytes(uyeler[ust_ad])
    return _DagitimBilgisi(
        ad=str(md["Name"]),
        surum=surum,
        gereksinimler=[str(g) for g in md.get_all("Requires-Dist") or []],
        lisans_ifadesi=str(md.get("License-Expression") or ""),
        yazar=str(md.get("Author") or ""),
        dosyalar=sorted(lisanslar),
    )


def _npm_bilesenleri(on_yuz: dict[str, Any]) -> list[tuple[Bilesen, list[tuple[str, str]]]]:
    sonuc: list[tuple[Bilesen, list[tuple[str, str]]]] = []
    for paket in on_yuz["paketler"]:
        etiket = _guvenli_ad(paket["ad"].lstrip("@").replace("/", "-"))
        metinler = [(_txt(f"npm-{etiket}-{d['ad']}"), d["metin"]) for d in paket["dosyalar"]]
        if not metinler:
            raise SystemExit(f"HATA: npm paketi {paket['ad']} lisans dosyası taşımıyor.")
        nedenler = paket.get("nedenler", [])
        aciklama = {
            "vite-yardimcisi": "Derleyicinin çıktıya kattığı çalışma anı yardımcıları",
            "css-uretimi": "Çıktıdaki üretilmiş CSS (preflight)",
        }.get(nedenler[0] if nedenler else "", "")
        if "varlik" in nedenler and not aciklama:
            aciklama = "Arayüz simgeleri (yazı tipi)"
        sonuc.append(
            (
                Bilesen(
                    ad=paket["ad"],
                    surum=paket["surum"],
                    tur="npm",
                    platformlar=list(PLATFORMLAR),
                    lisans=paket["lisans"],
                    dosyalar=[ad for ad, _ in metinler],
                    kaynak=f"https://www.npmjs.com/package/{paket['ad']}/v/{paket['surum']}",
                    aciklama=aciklama,
                ),
                metinler,
            )
        )
    return sonuc


def _indir_bayt(adres: str) -> bytes:
    istek = urllib.request.Request(  # noqa: S310 — yalnız sabit https://www.nuget.org adresi
        adres, headers={"User-Agent": "kd-lisans-uretici"}
    )
    with urllib.request.urlopen(istek, timeout=120) as yanit:  # noqa: S310 — sabit adres
        veri: bytes = yanit.read()
        return veri


#: pywebview 5.3.2'nin `webview/lib/` altında taşıdığı WebView2 SDK DLL'lerinin
#: sürümü (Microsoft.Web.WebView2.Core.dll sürüm kaynağından okundu, 27.09.2026).
WEBVIEW2_SDK_SURUMU = "1.0.2045.28"

WEBVIEW2_NOTU = """\
Microsoft Edge WebView2 Evergreen önyükleyicisi (MicrosoftEdgeWebView2Setup.exe)
================================================================================

Windows kurulum dosyası, bilgisayarda Microsoft Edge WebView2 Çalışma Zamanı
yoksa onu kurmak için Microsoft'un Evergreen önyükleyicisini içerir. Dosya
derleme sırasında Microsoft'un sunucusundan olduğu gibi alınır ve değiştirilmez.
Önyükleyici çalışma zamanını Microsoft'tan indirir; kurulan WebView2 Çalışma
Zamanı Microsoft'un kendi lisans koşullarına tabidir.

Microsoft, uygulamaların Evergreen önyükleyicisini kendi kurulum dosyalarıyla
birlikte dağıtmasına izin verir:
  https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
  https://developer.microsoft.com/en-us/microsoft-edge/webview2/

Bu bileşen yalnız Windows kurulum dosyasında (setup.exe) bulunur; taşınabilir
.zip ve Linux paketlerinde yoktur.
"""

VC_NOTU = """\
Microsoft Visual C++ ve Universal C çalışma zamanı
===================================================

Windows paketi, Python'un ve derlenmiş eklentilerin çalışması için Microsoft'un
yeniden dağıtılabilir C/C++ çalışma zamanı dosyalarını (vcruntime140*.dll,
msvcp140*.dll; gerekirse ucrtbase.dll ve api-ms-win-crt-*.dll) taşıyabilir. Bu
dosyalar Microsoft'un Visual Studio lisansındaki "Distributable Code" koşullarıyla
dağıtılır; değiştirilmez. Python'un Windows sürümünün lisans metni
(yerel-kutuphaneler/ altındaki python-LICENSE.txt) aynı koşulları anlatır.

Hangi dosyaların pakette bulunduğu paket-icerigi.txt'de yazılıdır.
"""

#: PySide6 6.8.3 tekerleğinin Linux'ta AYRI kitaplık dosyaları olarak taşıdığı ICU
#: (`PySide6/Qt/lib/libicu{data,i18n,uc}.so.73`). Sürüm kitaplığın içindeki sürüm
#: dizesinden okundu (F12 düzeltme turu, 28.09.2026); lisans metni aynı sürümün
#: etiketinden alınır (ICU lisansı telif ve izin metninin kopyalarla verilmesini ister).
ICU_SURUMU = "73.2"
ICU_LISANS_ADRESI = "https://raw.githubusercontent.com/unicode-org/icu/release-73-2/icu4c/LICENSE"
ICU_DOSYASI = "ICU-73-LICENSE.txt"

QT_UCUNCU_TARAF_DOSYASI = "Qt-6.8.3-ucuncu-taraf-NOT.txt"
QT_UCUNCU_TARAF_NOTU = f"""\
Qt 6.8.3 kitaplıklarının içerdiği üçüncü taraf bileşenler (yalnız Linux paketi)
==============================================================================

Linux paketindeki Qt 6 kitaplıkları PySide6 6.8.3 tekerleklerinden değiştirilmeden
alınır (_internal/PySide6/Qt/). The Qt Company bu kitaplıkları Qt'nin kaynak
ağacına gömülü üçüncü taraf kodla derler:

* ICU (International Components for Unicode) {ICU_SURUMU} ayrı kitaplık dosyalarıdır
  (libicudata, libicui18n ve libicuuc .so.73); lisans metni bu klasördeki
  {ICU_DOSYASI} dosyasındadır.
* Qt WebEngine, Chromium'u ve onun üçüncü taraf bileşenlerini içerir
  (libQt6WebEngineCore, QtWebEngineProcess ve resources/ altındaki .pak dosyaları).
* Qt Core, Qt Gui ve öbür modüller kendi kaynak ağaçlarındaki üçüncü taraf
  bileşenleri içerebilir.

Bu bileşenlerin tam listesi, telif bildirimleri ve lisans metinleri Qt'nin
belgelerinde ve kaynak arşivinde (her bileşenin qt_attribution.json dosyası)
yayımlanır:
  https://doc.qt.io/qt-6.8/licenses-used-in-qt.html
  https://doc.qt.io/qt-6.8/qtwebengine-licensing.html
  https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz

Qt'nin yalnız GPL-3.0 ile sunulan modülleri (Charts, Data Visualization, Graphs,
Quick 3D, Quick Timeline, Virtual Keyboard, Wayland Compositor ve öbürleri) pakete
GİRMEZ: derleme onları ayıklar ve lisans denetimi dosya düzeyinde sınar.
"""


def _elle_bilesenler() -> list[tuple[Bilesen, list[tuple[str, str]]]]:
    """Python/npm dışı bileşenler: çalışma zamanı, yazı tipi, Microsoft ikilileri."""
    sonuc: list[tuple[Bilesen, list[tuple[str, str]]]] = []
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    python_lisansi = (stdlib / "LICENSE.txt").read_text(encoding="utf-8")
    surum = f"{sys.version_info.major}.{sys.version_info.minor}"
    sonuc.append(
        (
            Bilesen(
                ad="Python (CPython)",
                surum=surum,
                tur="calisma-zamani",
                platformlar=list(PLATFORMLAR),
                lisans="PSF-2.0",
                dosyalar=["cpython-LICENSE.txt"],
                kaynak="https://www.python.org/downloads/source/",
                aciklama="Programın çalışma zamanı ve standart kitaplığı",
            ),
            [("cpython-LICENSE.txt", python_lisansi)],
        )
    )
    dejavu = (REPO / "packaging" / "fontlar" / "DejaVu-LISANS.txt").read_text(encoding="utf-8")
    sonuc.append(
        (
            Bilesen(
                ad="DejaVu Sans",
                surum="2.37",
                tur="yazi-tipi",
                platformlar=list(PLATFORMLAR),
                lisans="Bitstream-Vera",
                dosyalar=["DejaVu-LISANS.txt"],
                kaynak="https://dejavu-fonts.github.io/",
                aciklama="Evrakta gömülü yazı tipi (4 kesim)",
            ),
            [("DejaVu-LISANS.txt", dejavu)],
        )
    )
    nupkg = _indir_bayt(
        f"https://www.nuget.org/api/v2/package/Microsoft.Web.WebView2/{WEBVIEW2_SDK_SURUMU}"
    )
    with zipfile.ZipFile(io.BytesIO(nupkg)) as z:
        wv2 = [
            (f"Microsoft-WebView2-SDK-{ad}", _metin_coz(z.read(ad)))
            for ad in ("LICENSE.txt", "NOTICE.txt")
        ]
    sonuc.append(
        (
            Bilesen(
                ad="Microsoft Edge WebView2 SDK",
                surum=WEBVIEW2_SDK_SURUMU,
                tur="ikili",
                platformlar=["windows"],
                lisans="BSD-3-Clause",
                dosyalar=[ad for ad, _ in wv2],
                kaynak="https://www.nuget.org/packages/Microsoft.Web.WebView2/",
                aciklama="pywebview ile gelen WebView2 DLL'leri (webview/lib)",
            ),
            wv2,
        )
    )
    sonuc.append(
        (
            Bilesen(
                ad="Microsoft Edge WebView2 Evergreen önyükleyicisi",
                surum="derlemede indirilen güncel sürüm",
                tur="ikili",
                platformlar=["windows"],
                lisans="LicenseRef-Microsoft-WebView2-Runtime",
                dosyalar=["Microsoft-WebView2-Evergreen-NOT.txt"],
                kaynak="https://developer.microsoft.com/en-us/microsoft-edge/webview2/",
                aciklama="Yalnız setup.exe: WebView2 yoksa kurar",
            ),
            [("Microsoft-WebView2-Evergreen-NOT.txt", WEBVIEW2_NOTU)],
        )
    )
    sonuc.append(
        (
            Bilesen(
                ad="Microsoft Visual C++ / Universal C çalışma zamanı",
                surum="derleme ortamındaki sürüm",
                tur="ikili",
                platformlar=["windows"],
                lisans="LicenseRef-Microsoft-Distributable-Code",
                dosyalar=["Microsoft-VC-calisma-zamani-NOT.txt"],
                aciklama="Python ve eklentilerin C/C++ çalışma zamanı",
            ),
            [("Microsoft-VC-calisma-zamani-NOT.txt", VC_NOTU)],
        )
    )
    icu = _metin_coz(_indir_bayt(ICU_LISANS_ADRESI))
    if "UNICODE" not in icu.upper() or "ICU" not in icu:
        raise SystemExit(f"HATA: ICU lisans metni beklenen biçimde değil: {ICU_LISANS_ADRESI}")
    sonuc.append(
        (
            Bilesen(
                ad="ICU (International Components for Unicode)",
                surum=ICU_SURUMU,
                tur="ikili",
                platformlar=["linux"],
                lisans="Unicode-DFS-2016 AND ICU AND BSD-3-Clause AND NAIST-2003",
                dosyalar=[ICU_DOSYASI],
                kaynak="https://github.com/unicode-org/icu/releases/tag/release-73-2",
                aciklama="Qt 6 ile gelen Unicode kitaplıkları (libicu*.so.73)",
            ),
            [(ICU_DOSYASI, icu)],
        )
    )
    sonuc.append(
        (
            Bilesen(
                ad="Qt 6 içindeki üçüncü taraf kod (Chromium dahil)",
                surum="6.8.3",
                tur="ikili",
                platformlar=["linux"],
                lisans="LicenseRef-Qt-ucuncu-taraf",
                dosyalar=[QT_UCUNCU_TARAF_DOSYASI],
                kaynak="https://doc.qt.io/qt-6.8/licenses-used-in-qt.html",
                aciklama="Qt kitaplıklarına derlenmiş bileşenlerin bildirim adresleri",
            ),
            [(QT_UCUNCU_TARAF_DOSYASI, QT_UCUNCU_TARAF_NOTU)],
        )
    )
    return sonuc


#: Programın herkese açık deposu. LGPL kaynağı için yazılı teklifin iletişim yolu bu
#: deponun Issues sayfasıdır (KB-1, 28.09.2026 kullanıcı kararı: teklifte e-posta, kişi
#: adı, unvan ve kurum adı YAZILMAZ). Güncelleme denetiminin varsayılan deposuyla aynıdır
#: (`backend/apps/okul/services/updates.py::GITHUB_REPOSITORY`; kapı testi eşitler).
DEPO_ADRESI = "https://github.com/aalidemirci/kutuphane-defteri"
KAYNAK_TEKLIF_ADRESI = f"{DEPO_ADRESI}/issues"
TEKLIF_BASLIGI = "LGPL BİLEŞENLERİNİN KAYNAK KODU İÇİN YAZILI TEKLİF"


def _platform_etiketi(bilesen: Bilesen) -> str:
    if len(bilesen.platformlar) == 2:
        return "Windows + Linux"
    return {"windows": "yalnız Windows", "linux": "yalnız Linux"}[bilesen.platformlar[0]]


def _yazili_teklif(bilesenler: list[Bilesen]) -> list[str]:
    """LGPL kaynağı için yazılı teklif (KB-1, 28.09.2026 kullanıcı kararı — beta için).

    LGPL-2.1 madde 6(c) ve LGPL-3.0'ın nesne kodu için uyguladığı GPL-3.0 madde 6: en az
    üç yıl geçerli teklif; kaynak ücretsiz ağ sunucusundan, fiziksel taşıyıcıyla istenirse
    en çok gönderim maliyetine. GPL-3.0 md. 6(b) (yazılı teklif) yalnız FİZİKSEL ürünle
    dağıtımı kapsar; program ağdan dağıtıldığı için LGPL-3.0 bileşenlerinde md. 6(d)
    geçerlidir: kaynağa aynı yerden ya da nesne kodunun yanındaki açık yönlendirmeyle
    erişim (Release notu — `.github/workflows/paketleme.yml`; KB-1 düzeltme turu,
    29.09.2026). Bileşen listesi `bilesenler.json`'dan türer: pakete yeni bir LGPL bileşen
    girerse teklife kendiliğinden girer. Kararlı sürümden önce Windows'un MSYS2 kaynak
    arşivleri ayrıca Release'e konur (KB-1 (b), tasarım §14.1 F12 ekleri).
    """
    lgpl = [b for b in bilesenler if b.tur == "python" and "LGPL" in b.etkin_lisans]
    satirlar = [
        TEKLIF_BASLIGI,
        "-" * len(TEKLIF_BASLIGI),
        "Yukarıdaki adreslerden bağımsız olarak Kütüphane Defteri'nin geliştiricisi,",
        "programın bu dizinle birlikte dağıtılan bir sürümünü edinmiş HERKESE, o",
        "sürümün paketine giren LGPL lisanslı bileşenlerin tam ve karşılık gelen",
        "kaynak kodunu vermeyi yazılı olarak teklif eder (LGPL-2.1 madde 6(c);",
        "LGPL-3.0 bileşenleri fiziksel bir taşıyıcıyla dağıtılırsa GPL-3.0 madde",
        "6(b)). Teklif şunları kapsar:",
        "",
    ]
    for b in lgpl:
        yer = (
            "Windows ve Linux paketleri"
            if len(b.platformlar) == 2
            else f"yalnız {b.platformlar[0].capitalize()} paketi"
        )
        satirlar.append(f"  - {benioku_basligi(b)} ({yer})")
    pyside = next((b for b in lgpl if normal_ad(b.ad) == "pyside6"), None)
    if pyside is not None:
        satirlar += [
            f"  - PySide6 tekerleklerinin taşıdığı Qt {pyside.surum} kitaplıkları",
            "    (yalnız Linux paketi)",
        ]
    satirlar += [
        "  - paketle gelen LGPL lisanslı sistem kütüphaneleri (Windows'ta MSYS2,",
        "    Linux'ta Debian paketleri; adları ve sürümleri paketteki",
        f"    {PAKET_ICERIGI_ADI} ve {YEREL_DIZIN_ADI}/ dizinindedir)",
        "",
        "Kaynak, istenen program sürümünün paketindeki bileşen sürümleriyle birebir",
        "verilir. Nasıl istenir: programın GitHub deposundaki Issues (sorun kayıtları)",
        "sayfasında bir kayıt açın:",
        f"    {KAYNAK_TEKLIF_ADRESI}",
        "Kayda programın sürümünü (Hakkında ekranında yazar), platformu (Windows ya",
        "da Linux) ve istediğiniz bileşeni yazın. Kayıtlar herkese açıktır: kişisel",
        "veri ve okul bilgisi yazmayın.",
        "",
        "Kaynak ücretsiz verilir: bir ağ sunucusunda (ör. programın GitHub Releases",
        "sayfasında) indirilebilir olarak sunulur ve adresi kayda yazılır. Kaynağın",
        "fiziksel bir taşıyıcıyla gönderilmesi istenirse alınacak ücret bu gönderimin",
        "maliyetini aşmaz.",
        "",
        "Program ağ üzerinden (GitHub Releases ve indir.okulapp.org) dağıtılır. Ağdan",
        "dağıtımda LGPL-3.0 bileşenleri için GPL-3.0 madde 6(d) geçerlidir: kaynağa",
        "nesne koduyla aynı yerden ya da nesne kodunun yanındaki açık bir",
        "yönlendirmeyle başka bir sunucudan erişilebilmelidir. Kaynak adresleri",
        "yukarıdadır; her sürümün Release notu bu dosyaya ve kaynak adreslerine",
        "yönlendirir.",
        "",
        "Bu teklif programın her sürümü (beta sürümleri dahil) için, o sürümün",
        "yayımlandığı tarihten başlayarak EN AZ ÜÇ YIL ve o sürüm için destek",
        "verildiği sürece geçerlidir.",
        "",
    ]
    return satirlar


def benioku_basligi(bilesen: Bilesen) -> str:
    """BENIOKU'daki bileşen satırı: ad ve sürüm.

    Sürüm numarayla başlamıyorsa (ör. "derlemede indirilen güncel sürüm") ada
    yapışıp bozuk bir cümle gibi okunmasın diye parantez içinde yazılır.
    """
    if bilesen.surum[:1].isdigit():
        return f"{bilesen.ad} {bilesen.surum}"
    return f"{bilesen.ad} (sürüm: {bilesen.surum})"


def benioku_metni(bilesenler: list[Bilesen]) -> str:
    """`BENIOKU.txt`'nin metni; yalnız `bilesenler.json`'daki kayıtlara bağlıdır (kapı
    testi depodaki dosyanın bu çıktıyla birebir aynı olduğunu sınar — elle düzenlenmez)."""
    satirlar = [
        "KÜTÜPHANE DEFTERİ — ÜÇÜNCÜ TARAF BİLEŞENLER VE LİSANSLARI",
        "=========================================================",
        "",
        "Kütüphane Defteri'nin kendi kodu PolyForm Noncommercial 1.0.0 lisanslıdır",
        "(programın kurulduğu klasördeki LICENSE.txt). Program aşağıdaki üçüncü taraf",
        "bileşenleri kendi lisanslarıyla birlikte dağıtır. Her bileşenin lisans metni",
        "bu klasörde, tabloda adı geçen dosyadadır. Makine okunur liste: bilesenler.json.",
        "",
        "Bu klasör üretilmiştir (packaging/lisanslar/uret.sh); elle düzenlenmez.",
        "Kurulum paketindeki kopyaya derleme sırasında iki ek girer:",
        f"  {PAKET_ICERIGI_ADI:<24} bu pakette gerçekten bulunan bileşenler ve sürümleri",
        f"  {YEREL_DIZIN_ADI + '/':<24} paketle gelen sistem kütüphanelerinin (Windows'ta",
        "                           MSYS2, Linux'ta Debian paketleri) lisans ve telif",
        "                           dosyaları, kaynak kod adresleriyle",
        "",
        "LGPL LİSANSLI BİLEŞENLER VE KAYNAK KOD",
        "--------------------------------------",
        "* pystray (yalnız Windows, sistem tepsisi) — LGPL-3.0. Kaynak kodu pakete",
        "  kaynak dosya olarak girer: kurulum klasöründe _internal\\pystray\\",
        "  altındadır; kütüphane bu dosyalar değiştirilerek yeniden kullanılabilir.",
        "  Aynı sürümün kaynak arşivi: https://pypi.org/project/pystray/0.19.5/#files",
        "* Qt 6 ve PySide6 (yalnız Linux, pencere ve tepsi) — pakete giren Qt",
        "  modülleri için The Qt Company'nin sunduğu LGPL-3.0 / GPL-2.0 / GPL-3.0",
        "  seçeneklerinden LGPL-3.0 kullanılır. Qt'nin YALNIZ GPL-3.0 ile sunulan",
        "  modülleri (Charts, Data Visualization, Graphs, Quick 3D, Quick Timeline,",
        "  Virtual Keyboard, Wayland Compositor ve öbürleri) pakete girmez: derleme",
        "  onları ayıklar, lisans denetimi dosya düzeyinde sınar. Kitaplıklar",
        "  değiştirilmeden, ayrı dosyalar olarak dağıtılır (_internal/PySide6/Qt/lib/)",
        "  ve çalışma anında bağlanır; aynı ABI'li kendi derlediğiniz sürümle",
        "  değiştirilebilir. Kullanılan sürümün (6.8.3) tam kaynak kodu:",
        "    Qt: https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz",
        "    PySide6/shiboken6: https://download.qt.io/official_releases/QtForPython/pyside6/"
        "PySide6-6.8.3-src/pyside-setup-everywhere-src-6.8.3.tar.xz",
        f"  Qt ile gelen ICU'nun lisans metni {ICU_DOSYASI}; Qt kitaplıklarına derlenmiş",
        "  üçüncü taraf kodun (Qt WebEngine'deki Chromium dahil) bildirimleri için",
        f"  {QT_UCUNCU_TARAF_DOSYASI}.",
        "* Paketle gelen sistem kütüphanelerinden LGPL lisanslı olanlar (glib, pango,",
        "  fribidi, libthai, libdatrie …) ve kaynak kod adresleri paketteki",
        f"  {YEREL_DIZIN_ADI}/ dizininde, her kütüphanenin kendi dosyasındadır.",
        "",
    ]
    satirlar += _yazili_teklif(bilesenler)
    satirlar += [
        "Ortak metinler: LGPL-3.0-metni.txt ve GPL-3.0-metni.txt (LGPL-3.0, GPL-3.0",
        "metnine atıf yaptığı için ikisi birlikte verilir).",
        "",
        "Programın simgeleri projenin kendi üretimidir (packaging/ikonlar); arayüz",
        "simgeleri Material Symbols yazı tipindendir (aşağıdaki tabloda).",
        "",
        "BİLEŞENLER",
        "----------",
    ]
    turler = [
        ("calisma-zamani", "Çalışma zamanı"),
        ("python", "Python kitaplıkları"),
        ("npm", "Arayüz (npm) kitaplıkları"),
        ("yazi-tipi", "Yazı tipleri"),
        ("ikili", "Diğer ikili bileşenler"),
    ]
    for tur, baslik in turler:
        grup = [b for b in bilesenler if b.tur == tur]
        if not grup:
            continue
        satirlar += ["", f"{baslik}:", ""]
        for b in grup:
            platform = _platform_etiketi(b)
            lisans = b.lisans + (f"  (kullanılan: {b.secilen})" if b.secilen else "")
            satirlar.append(f"  {benioku_basligi(b)}")
            satirlar.append(f"      {'Lisans':<9}: {lisans}")
            satirlar.append(f"      {'Platform':<9}: {platform}")
            if b.aciklama:
                satirlar.append(f"      {'Kullanım':<9}: {b.aciklama}")
            if b.kaynak:
                satirlar.append(f"      {'Kaynak':<9}: {b.kaynak}")
            for i, dosya in enumerate(b.dosyalar):
                satirlar.append(
                    f"      {'Dosyalar' if i == 0 else '':<9}{':' if i == 0 else ' '} {dosya}"
                )
    return "\n".join(satirlar) + "\n"


def uret(on_yuz_json: Path, hedef: Path = LISANS_DIZINI) -> list[Bilesen]:
    """Depodaki THIRD_PARTY_LICENSES/ dizinini baştan üretir."""
    on_yuz = json.loads(on_yuz_json.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="kd-lisans-") as gecici:
        uretici = Uretici(Path(gecici))
        cozulen = uretici.coz()

    dosyalar: dict[str, str] = {}
    bilesenler: list[Bilesen] = []
    eksik: list[str] = []

    pystray = cozulen.get("pystray")
    if pystray is None:
        raise SystemExit("HATA: pystray çözümde yok; ortak LGPL/GPL metni üretilemez.")
    pystray_dosyalari = {PurePosixPath(a).name: v for a, v in pystray.bilgi.dosyalar}
    dosyalar["LGPL-3.0-metni.txt"] = _metin_coz(pystray_dosyalari["COPYING.LGPL"])
    dosyalar["GPL-3.0-metni.txt"] = _metin_coz(pystray_dosyalari["COPYING"])

    for n, kayit in sorted(cozulen.items()):
        bilgi = kayit.bilgi
        lisans = LISANS_DUZELTMELERI.get(n) or bilgi.lisans_ifadesi
        if not lisans:
            eksik.append(f"{bilgi.ad} {bilgi.surum}")
            continue
        adlar: list[str]
        if n in ORTAK_METIN:
            adlar = list(ORTAK_METIN[n])
        elif bilgi.dosyalar:
            adlar = []
            for goreli, veri in bilgi.dosyalar:
                ad = _txt(f"python-{_guvenli_ad(bilgi.ad)}-{_dosya_etiketi(goreli)}")
                metin = _metin_coz(veri)
                if dosyalar.get(ad, metin) != metin:
                    raise SystemExit(f"HATA: lisans dosyası adı çakışıyor: {ad}")
                dosyalar[ad] = metin
                adlar.append(ad)
        elif n in URETILEN_LISANS:
            tur, telif = URETILEN_LISANS[n]
            ad = f"python-{_guvenli_ad(bilgi.ad)}-LICENSE-uretildi.txt"
            dosyalar[ad] = (
                f"{bilgi.ad} {bilgi.surum} — {tur} lisansı\n\n"
                "Dağıtım lisansını üstverisinde bildirir ama lisans dosyası taşımaz;\n"
                "bu metin standart şablondan üretildi (packaging/lisanslar/lisanslar.py).\n\n"
                f"{telif}\n\n{MIT_METNI}"
            )
            adlar = [ad]
        else:
            eksik.append(f"{bilgi.ad} {bilgi.surum} (lisans dosyası yok)")
            continue
        bilesenler.append(
            Bilesen(
                ad=bilgi.ad,
                surum=bilgi.surum,
                tur="python",
                platformlar=sorted(kayit.platformlar),
                lisans=lisans,
                dosyalar=sorted(set(adlar)),
                kaynak=f"https://pypi.org/project/{bilgi.ad}/{bilgi.surum}/",
                secilen=SECILEN_LISANSLAR.get(n, ""),
                aciklama=ACIKLAMALAR.get(n, ""),
                kaynagi_pakette=n in KAYNAGI_PAKETTE,
            )
        )
    if eksik:
        raise SystemExit(
            "HATA: lisansı belirlenemeyen dağıtımlar (LISANS_DUZELTMELERI'ne ekleyin):\n  "
            + "\n  ".join(eksik)
        )

    for bilesen, metinler in _npm_bilesenleri(on_yuz) + _elle_bilesenler():
        for ad, metin in metinler:
            dosyalar[ad] = _metin_coz(metin.encode("utf-8"))
        bilesenler.append(bilesen)

    sira = {"calisma-zamani": 0, "python": 1, "npm": 2, "yazi-tipi": 3, "ikili": 4}
    bilesenler.sort(key=lambda b: (sira[b.tur], b.ad.casefold()))

    if hedef.exists():
        shutil.rmtree(hedef)
    hedef.mkdir(parents=True)
    for ad, metin in sorted(dosyalar.items()):
        (hedef / ad).write_text(metin, encoding="utf-8", newline="\n")
    dizin = {"aciklama": UST_BILGI, "bilesenler": [b.sozluk() for b in bilesenler]}
    (hedef / DIZIN_DOSYASI).write_text(
        json.dumps(dizin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (hedef / BENIOKU_ADI).write_text(benioku_metni(bilesenler), encoding="utf-8", newline="\n")
    yaz(f"{len(bilesenler)} bileşen, {len(dosyalar)} lisans dosyası → {hedef}")
    return bilesenler


# =============================================================================
# paket — derlenmiş paketin denetimi (derleme ortamı, yalnız standart kitaplık)
# =============================================================================

#: Yalnız GPL lisanslı olduğu bilinen yerel kütüphaneler (DOSYA ADIYLA, iki platformda):
#: pakete girerse bütün dağıtım GPL'e bağlanırdı (PolyForm ile bağdaşmaz). readline,
#: Django `shell` ve pdb'nin koşullu import'u yüzünden Linux paketine sızıyordu
#: (27.09.2026 yerel derleme; spec `excludes`'a alındı). Debian paketlerinin lisansı
#: makine okunur biçimde güvenilir değildir (copyright dosyalarının çoğu DEP-5 değil,
#: DEP-5 olanlarda da test ve araç dosyalarının GPL'i kitaplığınkiyle karışır); bu
#: yüzden Linux'ta kural BİLİNEN ad listesidir (F12 düzeltme turu). Liste, bir Python
#: eklentisi, görüntü/PDF ya da ortam kitaplığı zinciri üzerinden sızabilecek, lisansı
#: yalnız GPL (ya da AGPL) olan Debian kitaplıklarıdır: readline/history, gdbm,
#: fftw3, gsl, poppler, ghostscript (libgs), jbig2dec, x264, x265, postproc
#: (FFmpeg'in GPL parçası), mad, faad, cdio, dvdcss, xvidcore, mpeg2, pci, iw,
#: parted. Windows'ta MSYS2 paketinin SPDX lisansı ayrıca değerlendirilir
#: (`msys2_lisans_denetimi`).
YASAK_YEREL = re.compile(
    r"^(lib)?(readline|history|gdbm|gdbm_compat)\b"
    # Kısa adlar yalnız `lib` önekiyle (Python ve veri dosyalarıyla karışmasın).
    r"|^lib(fftw3[flq]?(_threads|_omp)?|gsl|gslcblas|poppler|gs|jbig2dec|x264|x265"
    r"|postproc|mad|faad|cdio|dvdcss|xvidcore|mpeg2|pci|iw|parted)\b",
    re.IGNORECASE,
)

# ------------------------------------------------------------ Qt: yalnız GPL modüller

#: Qt 6'nın açık kaynak sürümünde LGPL-3.0 ile SUNULMAYAN, yalnız GPL-3.0 (+ ticari)
#: lisanslı modüllerinin dosya adındaki kökü (https://doc.qt.io/qt-6.8/licensing.html,
#: 28.09.2026: Charts, CoAP, Data Visualization, Graphs, GRPC, HTTP Server, Lottie
#: Animation — kitaplık adı Bodymovin —, MQTT, Network Authorization, Qml Compiler,
#: Quick 3D, Quick 3D Physics, Quick Timeline, Virtual Keyboard, Wayland Compositor).
#: PySide6_Addons bu modüllerin kitaplıklarını da taşır ve dağıtımın lisansı TEK
#: ifadedir ("LGPL-3.0-only OR GPL-…"): dağıtım etiketine güvenmek yetmez (F12
#: düzeltme turu — 27.09.2026 Qt'li Linux derlemesinde 22 kitaplık, QML eklentileri ve
#: `QtDataVisualization` bağlayıcısı pakete girmişti). Kural DOSYA düzeyindedir:
#: kitaplık, Python bağlayıcısı, QML modül dizini ve bunlara bağlanan (DT_NEEDED) her
#: ELF (ör. Quick 3D'nin `assetimporters` eklentisi, Virtual Keyboard'un giriş eklentisi).
QT_YALNIZ_GPL_MODULLER = (
    "Bodymovin",
    "Charts",
    "Coap",
    "DataVisualization",
    "Graphs",
    "Grpc",
    "HttpServer",
    "Mqtt",
    "NetworkAuth",
    "QmlCompiler",
    "Quick3D",
    "QuickTimeline",
    "VirtualKeyboard",
    "WaylandCompositor",
)
_QT_GPL_KOKLERI = "|".join(QT_YALNIZ_GPL_MODULLER)
#: `libQt6Charts.so.6`, `libQt6Quick3DXr.so.6`, Windows'ta `Qt6Charts.dll`.
QT_GPL_KITAPLIK = re.compile(rf"^(lib)?Qt6({_QT_GPL_KOKLERI})")
#: PySide6 bağlayıcıları: `QtDataVisualization.abi3.so`, `QtCharts.pyi`, `QtGraphs.pyd`.
QT_GPL_BAGLAYICI = re.compile(rf"^Qt({_QT_GPL_KOKLERI})\w*\.(abi3\.so|so|pyd|pyi)$")
#: QML modül dizinleri (`…/qml/` altındaki göreli yol öneki).
QT_GPL_QML_ONEKLERI = (
    "Qt/labs/lottieqt",
    "QtCharts",
    "QtCoap",
    "QtDataVisualization",
    "QtGraphs",
    "QtGrpc",
    "QtHttpServer",
    "QtMqtt",
    "QtNetworkAuth",
    "QtQuick/Timeline",
    "QtQuick/VirtualKeyboard",
    "QtQuick3D",
    "QtWayland/Compositor",
)


def qt_yalniz_gpl_mi(goreli: str | os.PathLike[str]) -> bool:
    """Paket içi yol (hedef adı) Qt'nin yalnız GPL'li bir modülüne mi ait (ada göre)?"""
    parcalar = PurePosixPath(str(goreli).replace("\\", "/")).parts
    if not parcalar:
        return False
    ad = parcalar[-1]
    if QT_GPL_KITAPLIK.match(ad) or QT_GPL_BAGLAYICI.match(ad):
        return True
    if "qml" in parcalar:
        konum = len(parcalar) - 1 - parcalar[::-1].index("qml")
        kalan = "/".join(parcalar[konum + 1 :])
        return any(kalan == onek or kalan.startswith(onek + "/") for onek in QT_GPL_QML_ONEKLERI)
    return False


def elf_gereksinimleri(yol: str | os.PathLike[str]) -> list[str] | None:
    """64 bit little-endian ELF'in DT_NEEDED listesi; ELF değilse ya da okunamazsa None.

    Yalnız başlık, bölüm tablosu, `.dynamic` ve `.dynstr` okunur (dosyanın tamamı
    değil: QtWebEngineCore yüzlerce MB'tır). Standart kitaplıkla; derleme ortamında
    ve spec'te koşar.
    """
    try:
        with open(yol, "rb") as dosya:
            baslik = dosya.read(64)
            if len(baslik) < 64 or baslik[:4] != b"\x7fELF" or baslik[4] != 2 or baslik[5] != 1:
                return None
            bolum_konumu = struct.unpack_from("<Q", baslik, 0x28)[0]
            bolum_boyu, bolum_sayisi = struct.unpack_from("<HH", baslik, 0x3A)
            if not bolum_konumu or not bolum_sayisi:
                return []
            dosya.seek(bolum_konumu)
            tablo = dosya.read(bolum_boyu * bolum_sayisi)
            bolumler = [
                struct.unpack_from("<IIQQQQIIQQ", tablo, i * bolum_boyu)
                for i in range(bolum_sayisi)
            ]
            dinamikler = [b for b in bolumler if b[1] == 6]  # SHT_DYNAMIC
            if not dinamikler:
                return []
            dinamik = dinamikler[0]
            dizgeler = bolumler[dinamik[6]]
            dosya.seek(dinamik[4])
            girdiler = dosya.read(dinamik[5])
            dosya.seek(dizgeler[4])
            dizge = dosya.read(dizgeler[5])
    except (OSError, struct.error, IndexError):
        return None
    gerekenler: list[str] = []
    for konum in range(0, len(girdiler) - 15, 16):
        etiket, deger = struct.unpack_from("<qQ", girdiler, konum)
        if etiket == 0:  # DT_NULL
            break
        if etiket == 1:  # DT_NEEDED
            son = dizge.find(b"\0", deger)
            gerekenler.append(dizge[deger : son if son >= 0 else None].decode("utf-8", "replace"))
    return gerekenler


def _toc_adi(hedef: str) -> str:
    return PurePosixPath(hedef.replace("\\", "/")).name


def _yasakliya_bagli(gerekenler: set[str], yasak_adlar: set[str]) -> bool:
    """ELF, ayıklanan bir dosyaya ya da (pakette olmasa da) yalnız GPL'li bir Qt
    kitaplığına mı bağlanıyor?"""
    return bool(gerekenler & yasak_adlar) or any(QT_GPL_KITAPLIK.match(g) for g in gerekenler)


def qt_gpl_suz(
    binaries: Sequence[tuple[str, str, str]], datas: Sequence[tuple[str, str, str]]
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]], list[str]]:
    """spec için: Qt'nin yalnız GPL'li modüllerini PyInstaller TOC'larından ayıklar.

    Önce ada göre (`qt_yalniz_gpl_mi`), sonra ayıklanan bir kitaplığa DT_NEEDED ile
    bağlanan her ikili (kapanış, sabit noktaya dek). Döner: (binaries, datas,
    ayıklanan hedef adları). Paket denetimi (`paket_dizini_denetimi`) aynı kuralı
    paketin diskteki hâlinde yeniden sınar.
    """
    atilan: list[str] = []
    atilan_adlar: set[str] = set()
    kalan: list[tuple[str, str, str]] = []
    for oge in binaries:
        if qt_yalniz_gpl_mi(oge[0]):
            atilan.append(oge[0])
            atilan_adlar.add(_toc_adi(oge[0]))
        else:
            kalan.append(oge)
    gerekenler = {oge[0]: set(elf_gereksinimleri(oge[1]) or ()) for oge in kalan}
    degisti = True
    while degisti:
        degisti = False
        yeni: list[tuple[str, str, str]] = []
        for oge in kalan:
            if _yasakliya_bagli(gerekenler[oge[0]], atilan_adlar):
                atilan.append(oge[0])
                atilan_adlar.add(_toc_adi(oge[0]))
                degisti = True
            else:
                yeni.append(oge)
        kalan = yeni
    kalan_veri = [oge for oge in datas if not qt_yalniz_gpl_mi(oge[0])]
    atilan += [oge[0] for oge in datas if qt_yalniz_gpl_mi(oge[0])]
    return kalan, kalan_veri, atilan


def qt_gpl_paket_denetimi(paket_dizini: Path) -> list[str]:
    """Paketin DİSKTEKİ hâlinde Qt'nin yalnız GPL'li modülünden kalan dosya var mı?

    Ada göre (sembolik bağlar dahil) ve DT_NEEDED kapanışıyla: yalnız GPL'li bir
    kitaplığa bağlanan her ELF de o modülün parçasıdır.
    """
    adla: list[str] = []
    elfler: dict[str, set[str]] = {}
    for kok, _dizinler, dosyalar in os.walk(paket_dizini):
        for ad in dosyalar:
            yol = Path(kok) / ad
            goreli = yol.relative_to(paket_dizini).as_posix()
            if qt_yalniz_gpl_mi(goreli):
                adla.append(goreli)
            elif not yol.is_symlink():
                okunan = elf_gereksinimleri(yol)
                if okunan:
                    elfler[goreli] = set(okunan)
    yasak_adlar = {PurePosixPath(g).name for g in adla}
    bagli: list[str] = []
    degisti = True
    while degisti:
        degisti = False
        for goreli, bagimliliklar in elfler.items():
            if goreli not in bagli and _yasakliya_bagli(bagimliliklar, yasak_adlar):
                bagli.append(goreli)
                yasak_adlar.add(PurePosixPath(goreli).name)
                degisti = True
    hatalar: list[str] = []
    if adla:
        hatalar.append(
            f"Qt'nin yalnız GPL lisanslı modül dosyaları pakette ({len(adla)} dosya, ör. "
            f"{sorted(adla)[0]}) — spec `qt_gpl_suz` süzgeci uygulanmamış"
        )
    if bagli:
        hatalar.append(
            f"yalnız GPL lisanslı Qt kitaplığına bağlanan dosyalar pakette ({len(bagli)} "
            f"dosya, ör. {sorted(bagli)[0]})"
        )
    return hatalar


#: pyphen sözlüklerinden pakette kalmasına izin verilenler (spec `PYPHEN_KALAN` ile
#: aynı; eşitliği kapı testi denetler). Öbürleri tek tek lisanslıdır, bir kısmı
#: yalnız GPL'dir.
PYPHEN_IZINLI = frozenset({"hyph_en_US.dic", "README_hyph_en_US.txt"})

#: Windows'ta sistem dizininden gelmesine izin verilen Microsoft çalışma zamanı.
_MS_CALISMA_ZAMANI = re.compile(
    r"^(vcruntime140(_1)?|msvcp140(_\d+)?|concrt140|vcomp140|ucrtbase|api-ms-win-crt-.+)\.dll$",
    re.IGNORECASE,
)

_TOC_KODLARI = frozenset({"PYMODULE", "PYSOURCE", "EXTENSION", "BINARY", "DATA"})


def toc_kaynaklari(calisma: Path) -> set[str]:
    """PyInstaller ara çıktısındaki TOC dosyalarından pakete giren kaynak yollar."""
    kaynaklar: set[str] = set()
    tocs = sorted(calisma.glob("*.toc"))
    if not tocs:
        raise SystemExit(f"HATA: {calisma} içinde PyInstaller TOC dosyası yok.")

    def dolas(oge: object) -> None:
        if isinstance(oge, list | tuple):
            if (
                len(oge) == 3
                and isinstance(oge[1], str)
                and isinstance(oge[2], str)
                and oge[2] in _TOC_KODLARI
            ):
                if os.path.isabs(oge[1]):
                    kaynaklar.add(oge[1])
                return
            for alt in oge:
                dolas(alt)
        elif isinstance(oge, dict):
            for alt in oge.values():
                dolas(alt)

    for toc in tocs:
        try:
            dolas(ast.literal_eval(toc.read_text(encoding="utf-8")))
        except (ValueError, SyntaxError) as exc:
            raise SystemExit(f"HATA: {toc.name} okunamadı: {exc}") from exc
    return kaynaklar


def _normal_yol(yol: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(yol)))


def _altinda_mi(yol: str, kok: str) -> bool:
    kok = kok.rstrip("\\/") + os.sep
    return yol.startswith(kok)


def dagitim_haritasi(
    dagitimlar: Iterable[im.Distribution] | None = None,
) -> dict[str, tuple[str, str, str]]:
    """Kurulu dağıtımların RECORD'undaki her dosya → (ad, sürüm, RECORD'daki göreli yol)."""
    harita: dict[str, tuple[str, str, str]] = {}
    for dagitim in dagitimlar if dagitimlar is not None else im.distributions():
        ad = dagitim.metadata["Name"]
        for dosya in dagitim.files or []:
            harita[_normal_yol(Path(dosya.locate()))] = (ad, dagitim.version, str(dosya))
    return harita


#: Dağıtımın YALNIZ bu alt yolları pakete girebilir: geri kalanı başka (GPL)
#: lisanslıdır. PyInstaller'ın önyükleyicisi ve `loader/` dosyaları GPL-2.0+
#: "Bootloader Exception" ile, çalışma anı kancaları ve `fake-modules/` Apache-2.0
#: ile gömülür; derleme kodu (`building`, `depend`, `utils.hooks`, modulegraph …)
#: istisnasız GPL-2.0+'dır. pyinstaller-hooks-contrib'de yalnız `rthooks/`
#: Apache-2.0'dır, standart kancalar GPL-2.0+'dır. 27.09.2026 yerel derlemesinde
#: pywebview'ın kendi PyInstaller kancası (`webview.__pyinstaller`) `collect_submodules`
#: ile toplanıp PyInstaller'ın derleme kodunu ve altgraph'ı pakete sürüklüyordu.
IZINLI_ALT_YOLLAR: dict[str, tuple[str, ...]] = {
    "pyinstaller": (
        "PyInstaller/bootloader/",
        "PyInstaller/loader/",
        "PyInstaller/hooks/rthooks/",
        "PyInstaller/fake-modules/",
    ),
    "pyinstaller-hooks-contrib": ("_pyinstaller_hooks_contrib/rthooks/",),
}


@dataclass
class YerelPaket:
    """Paketle gelen bir sistem kütüphanesinin sahibi (MSYS2 ya da Debian paketi)."""

    ad: str
    surum: str
    lisans: str
    kaynak: str
    lisans_dosyalari: list[Path]
    dosyalar: set[str] = field(default_factory=set)
    #: MSYS2: pacman'ın %LICENSE% satırları (değerlendirilir); Debian: boş (lisans
    #: makine okunur değildir, kural `YASAK_YEREL` ad listesidir).
    lisans_satirlari: tuple[str, ...] = ()


#: Lisans alanı yalnız GPL görünen ama pakete giren DLL'leri GPL OLMAYAN MSYS2 paketleri:
#: paket adı → (izinli DLL'ler, gerekçe). İzin DLL düzeyindedir: aynı paketten başka bir
#: dosya pakete girerse derleme yine durur. pacman'ın %LICENSE% dizisi bileşenlerin
#: lisanslarını ayrı satırlarda sayar; denetim bunları temkinle "AND" ile birleştirir.
MSYS2_GPL_IZINLERI: dict[str, tuple[frozenset[str], str]] = {
    "mingw-w64-x86_64-gcc-libs": (
        frozenset(
            {
                "libgcc_s_seh-1.dll",
                "libstdc++-6.dll",
                "libgomp-1.dll",
                "libquadmath-0.dll",
                "libatomic-1.dll",
            }
        ),
        "GCC çalışma anı kitaplıkları GCC Runtime Library Exception 3.1 ile dağıtılır "
        "(istisna ayrı %LICENSE% satırında yazılabilir)",
    ),
    "mingw-w64-x86_64-gettext-runtime": (
        frozenset({"libintl-8.dll", "libasprintf-0.dll"}),
        "libintl ve libasprintf LGPL-2.1-or-later'dır; paketin GPL-3.0 kısmı araçlardır "
        "(msgfmt …) ve pakete girmez",
    ),
    "mingw-w64-x86_64-gettext": (
        frozenset({"libintl-8.dll", "libasprintf-0.dll"}),
        "eski bölünmemiş paket: libintl ve libasprintf LGPL-2.1-or-later'dır",
    ),
    "mingw-w64-x86_64-libiconv": (
        frozenset({"libiconv-2.dll", "libcharset-1.dll"}),
        "libiconv ve libcharset LGPL-2.1-or-later'dır; GPL-3.0 kısmı `iconv` aracıdır ve "
        "pakete girmez",
    ),
}

#: SPDX öneki taşımayan eski pacman lisans adları → değerlendirme için SPDX karşılığı.
_ESKI_PACMAN_LISANSI = (
    (re.compile(r"^A?GPL\d*$", re.IGNORECASE), "GPL-3.0-only"),
    (re.compile(r"^LGPL\d*(\.\d+)?$", re.IGNORECASE), "LGPL-2.1-or-later"),
)


def msys2_lisans_ifadesi(satirlar: Sequence[str]) -> str:
    """pacman %LICENSE% satırları → değerlendirilecek tek SPDX ifadesi (AND ile)."""
    parcalar: list[str] = []
    for satir in satirlar:
        if satir.startswith("spdx:"):
            parcalar.append(satir.removeprefix("spdx:").strip())
            continue
        karsilik = next((spdx for desen, spdx in _ESKI_PACMAN_LISANSI if desen.match(satir)), None)
        parcalar.append(karsilik or "LicenseRef-" + _guvenli_ad(satir))
    if len(parcalar) == 1:
        return parcalar[0]
    return " AND ".join(f"({p})" for p in parcalar)


def msys2_lisans_denetimi(paket: YerelPaket) -> tuple[str | None, str | None]:
    """MSYS2 paketi yalnız GPL mi? → (hata, uyarı); ikisi de None ise geçer."""
    if not paket.lisans_satirlari:
        return None, None
    ifade = msys2_lisans_ifadesi(paket.lisans_satirlari)
    try:
        gpl = gpl_yalniz_mi(ifade)
    except SpdxHatasi:
        return None, (
            f"{paket.ad}: MSYS2 lisans alanı ayrıştırılamadı ({ifade!r}); lisansı elle "
            "doğrulayın"
        )
    if not gpl:
        return None, None
    izin = MSYS2_GPL_IZINLERI.get(paket.ad)
    if izin is not None and paket.dosyalar <= izin[0]:
        return None, None
    return (
        f"yalnız GPL lisanslı MSYS2 paketi pakete girmiş: {paket.ad} ({ifade}; "
        f"{', '.join(sorted(paket.dosyalar))}) — DLL'in kendi lisansını doğrulayıp "
        "MSYS2_GPL_IZINLERI'ne gerekçeyle ekleyin ya da onu çeken bağımlılığı kapanıştan "
        "çıkarın"
    ), None


def msys2_veritabani(kok: Path) -> dict[str, YerelPaket]:
    """pacman yerel veritabanı → {`mingw64/bin/x.dll` (küçük harf): paket}.

    Her paket `var/lib/pacman/local/<ad>-<sürüm>/` altında `desc` (%NAME%,
    %VERSION%, %BASE%, %LICENSE%) ve `files` (%FILES%, köke göreli) taşır; lisans
    dosyaları paketin kendi `files` listesindeki `…/share/licenses/…` yollarıdır.
    """
    yerel = kok / "var" / "lib" / "pacman" / "local"
    if not yerel.is_dir():
        raise SystemExit(f"HATA: MSYS2 paket veritabanı yok: {yerel}")
    sonuc: dict[str, YerelPaket] = {}
    for paket_dizini in sorted(p for p in yerel.iterdir() if p.is_dir()):
        desc = _pacman_bolumleri((paket_dizini / "desc").read_text(encoding="utf-8"))
        files = _pacman_bolumleri(
            (paket_dizini / "files").read_text(encoding="utf-8")
            if (paket_dizini / "files").is_file()
            else ""
        )
        ad = desc.get("NAME", [paket_dizini.name])[0]
        surum = desc.get("VERSION", [""])[0]
        taban = desc.get("BASE", [re.sub(r"^mingw-w64-x86_64-", "mingw-w64-", ad)])[0]
        dosya_listesi = files.get("FILES", [])
        paket = YerelPaket(
            ad=ad,
            surum=surum,
            lisans=" AND ".join(lic.removeprefix("spdx:") for lic in desc.get("LICENSE", [])),
            lisans_satirlari=tuple(desc.get("LICENSE", [])),
            kaynak=f"https://repo.msys2.org/mingw/sources/{taban}-{surum}.src.tar.zst",
            lisans_dosyalari=[
                kok / d
                for d in dosya_listesi
                if "/share/licenses/" in d and not d.endswith("/") and (kok / d).is_file()
            ],
        )
        for dosya in dosya_listesi:
            if dosya.lower().endswith(".dll"):
                sonuc[dosya.lower()] = paket
    return sonuc


def _pacman_bolumleri(metin: str) -> dict[str, list[str]]:
    bolumler: dict[str, list[str]] = {}
    anahtar = ""
    for satir in metin.splitlines():
        if satir.startswith("%") and satir.endswith("%"):
            anahtar = satir.strip("%")
            bolumler[anahtar] = []
        elif satir and anahtar:
            bolumler[anahtar].append(satir)
    return bolumler


_DPKG_SAHIP = re.compile(r"^([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9]+)?: (/.*)$")


def debian_sahibi(yol: str, onbellek: dict[str, YerelPaket]) -> YerelPaket | None:
    """Dosyanın Debian paketi (dpkg); dpkg yoksa ya da dosya sahipsizse None."""
    dpkg_query = shutil.which("dpkg-query")
    if dpkg_query is None:
        return None
    for aday in dict.fromkeys((yol, os.path.realpath(yol))):
        sonuc = subprocess.run(  # noqa: S603 — sabit araç, kabuk yok
            [dpkg_query, "-S", aday], capture_output=True, text=True, check=False
        )
        for satir in sonuc.stdout.splitlines():
            eslesme = _DPKG_SAHIP.match(satir)
            if eslesme is None:
                continue
            ad = eslesme.group(1)
            if ad not in onbellek:
                bilgi = subprocess.run(  # noqa: S603
                    [
                        dpkg_query,
                        "-W",
                        "-f=${Version}\t${source:Package}\t${source:Version}",
                        ad,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.split("\t")
                surum = bilgi[0] if bilgi else ""
                kaynak_ad = bilgi[1] if len(bilgi) > 1 and bilgi[1] else ad
                kaynak_surum = bilgi[2] if len(bilgi) > 2 and bilgi[2] else surum
                copyright_ = Path("/usr/share/doc") / ad / "copyright"
                onbellek[ad] = YerelPaket(
                    ad=ad,
                    surum=surum,
                    lisans="Debian copyright dosyasına bakın",
                    kaynak=(
                        f"https://snapshot.debian.org/package/{kaynak_ad}/"
                        f"{kaynak_surum.replace('+', '%2B')}/"
                    ),
                    lisans_dosyalari=[copyright_] if copyright_.is_file() else [],
                )
            return onbellek[ad]
    return None


@dataclass
class DenetimSonucu:
    python: dict[str, tuple[str, str]] = field(default_factory=dict)  # normal ad → (ad, sürüm)
    yerel: dict[str, YerelPaket] = field(default_factory=dict)
    cpython: set[str] = field(default_factory=set)
    microsoft: set[str] = field(default_factory=set)
    proje: int = 0
    hatalar: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)


def paketi_denetle(
    *,
    kaynaklar: Iterable[str],
    bilesenler: Sequence[Bilesen],
    platform: str,
    calisma: Path,
    harita: dict[str, tuple[str, str, str]],
    dll_dizini: Path | None = None,
    msys2: dict[str, YerelPaket] | None = None,
    msys2_kok: Path | None = None,
    debian: bool = False,
    python_kokleri: Sequence[str] = (),
    site_dizinleri: Sequence[str] = (),
    sistem_dizini: str | None = None,
) -> DenetimSonucu:
    """Kaynak yolları sınıflandırır; listede olmayanı ve yasaklıyı hata sayar.

    Sıra önemlidir: PyInstaller ara çıktısı ve MSYS2 DLL dizini depo İÇİNDEDİR
    (dist/, packaging/windows/dll), site-packages Python kökünün İÇİNDEDİR; önce
    dar olan sınanır. site-packages'ta olup hiçbir RECORD'da görünmeyen dosya
    "Python'un kendisi" sayılmaz, hatadır.
    """
    sonuc = DenetimSonucu()
    liste = {normal_ad(b.ad): b for b in bilesenler if b.tur == "python"}
    calisma_n = _normal_yol(calisma)
    repo_n = _normal_yol(REPO)
    dll_n = _normal_yol(dll_dizini) if dll_dizini else None
    msys2_n = _normal_yol(msys2_kok) if msys2_kok else None
    kokler = [_normal_yol(k) for k in python_kokleri]
    siteler = [_normal_yol(k) for k in site_dizinleri]
    sistem_n = _normal_yol(sistem_dizini) if sistem_dizini else None
    debian_onbellek: dict[str, YerelPaket] = {}

    for kaynak in sorted(kaynaklar):
        yol = _normal_yol(kaynak)
        ad = os.path.basename(kaynak)
        if YASAK_YEREL.match(ad) and not ad.endswith(".py"):
            sonuc.hatalar.append(
                f"yalnız GPL lisanslı yerel kütüphane pakete girmiş: {ad} ({kaynak}) — "
                "spec `excludes`'a ekleyin"
            )
            continue
        if _altinda_mi(yol, calisma_n):
            sonuc.cpython.add(ad)  # PyInstaller ara çıktısı (base_library.zip, pyimod*)
            continue
        if yol in harita:
            dagitim, surum, goreli = harita[yol]
            izinli = IZINLI_ALT_YOLLAR.get(normal_ad(dagitim))
            if izinli is not None and not goreli.replace("\\", "/").startswith(izinli):
                sonuc.hatalar.append(
                    f"{dagitim}'in pakete gömülemeyen (GPL) dosyası pakete girmiş: {goreli} — "
                    "onu import eden modülü spec'te süzün"
                )
                continue
            sonuc.python[normal_ad(dagitim)] = (dagitim, surum)
            continue
        if dll_n and _altinda_mi(yol, dll_n):
            paket = (msys2 or {}).get(f"mingw64/bin/{ad}".lower())
            if paket is None:
                sonuc.hatalar.append(f"MSYS2 sahibi bulunamayan DLL: {ad}")
            else:
                sonuc.yerel.setdefault(paket.ad, paket).dosyalar.add(ad)
            continue
        if msys2_n and _altinda_mi(yol, msys2_n):
            # DLL kapanışı dışından, MSYS2 ağacından doğrudan toplanan dosya
            # (build.ps1 mingw64\bin'i PATH'e ekler): sahibi yine pacman'dan.
            goreli_msys2 = os.path.relpath(yol, msys2_n).replace("\\", "/").lower()
            paket = (msys2 or {}).get(goreli_msys2)
            if paket is None:
                sonuc.hatalar.append(f"MSYS2 sahibi bulunamayan dosya: {kaynak}")
            else:
                sonuc.yerel.setdefault(paket.ad, paket).dosyalar.add(ad)
            continue
        if _altinda_mi(yol, repo_n):
            sonuc.proje += 1
            continue
        if any(_altinda_mi(yol, s) for s in siteler):
            sonuc.hatalar.append(
                f"site-packages'ta olup hiçbir dağıtımın RECORD'unda bulunmayan dosya: {kaynak}"
            )
            continue
        if any(_altinda_mi(yol, k) for k in kokler):
            sonuc.cpython.add(ad)
            continue
        if sistem_n and _altinda_mi(yol, sistem_n) and _MS_CALISMA_ZAMANI.match(ad):
            sonuc.microsoft.add(ad)
            continue
        if debian:
            paket = debian_sahibi(kaynak, debian_onbellek)
            if paket is not None:
                sonuc.yerel.setdefault(paket.ad, paket).dosyalar.add(ad)
                continue
        sonuc.hatalar.append(f"sahibi ve lisansı belirlenemeyen dosya: {kaynak}")

    for n, (dagitim, surum) in sorted(sonuc.python.items()):
        kayit = liste.get(n)
        if kayit is None:
            sonuc.hatalar.append(
                f"THIRD_PARTY_LICENSES'ta olmayan Python dağıtımı pakete girmiş: "
                f"{dagitim} {surum} — `bash packaging/lisanslar/uret.sh` koşun"
            )
        elif platform not in kayit.platformlar:
            # Lisans metni pakette zaten var (dizin iki platformda aynıdır); işaret
            # yalnız bilgi amaçlıdır. Liste tazelenmeli ama derleme durmaz.
            sonuc.uyarilar.append(
                f"{dagitim} pakete girmiş ama THIRD_PARTY_LICENSES'ta {platform} için "
                "işaretli değil (listeyi tazeleyin)"
            )
        elif kayit.surum != surum:
            sonuc.uyarilar.append(
                f"{dagitim}: pakette {surum}, lisans listesinde {kayit.surum} "
                "(lisans metni aynı sürüm ailesinden; listeyi tazeleyin)"
            )
    for paket in sonuc.yerel.values():
        if not paket.lisans_dosyalari:
            sonuc.hatalar.append(f"{paket.ad}: lisans/telif dosyası bulunamadı")
        hata, uyari = msys2_lisans_denetimi(paket)
        if hata:
            sonuc.hatalar.append(hata)
        if uyari:
            sonuc.uyarilar.append(uyari)
    return sonuc


def _paket_icerigi(
    sonuc: DenetimSonucu, bilesenler: Sequence[Bilesen], platform: str, surum: str
) -> str:
    liste = {normal_ad(b.ad): b for b in bilesenler}
    satirlar = [
        f"KÜTÜPHANE DEFTERİ {surum} — BU PAKETTEKİ ÜÇÜNCÜ TARAF BİLEŞENLER ({platform})",
        "=" * 72,
        "",
        "Derleme sırasında, paketin gerçekten içerdiği dosyalardan üretildi",
        "(packaging/lisanslar/lisanslar.py paket). Lisans metinleri için BENIOKU.txt'ye",
        f"ve {YEREL_DIZIN_ADI}/ dizinine bakın.",
        "",
        f"Python {sys.version.split()[0]} (CPython) çalışma zamanı ve standart kitaplığı",
        "",
        "Python dağıtımları:",
    ]
    for n, (ad, surum_) in sorted(sonuc.python.items()):
        kayit = liste.get(n)
        lisans = kayit.etkin_lisans if kayit else "?"
        satirlar.append(f"  {ad} {surum_} — {lisans}")
    satirlar += ["", "Arayüz (npm) paketleri: BENIOKU.txt'deki tabloya bakın.", ""]
    if sonuc.yerel:
        satirlar.append("Sistem kütüphaneleri (paketle gelen):")
        for paket in sorted(sonuc.yerel.values(), key=lambda p: p.ad):
            satirlar.append(f"  {paket.ad} {paket.surum} — {paket.lisans}")
            satirlar.append(f"      Dosyalar: {', '.join(sorted(paket.dosyalar))}")
            satirlar.append(f"      Kaynak  : {paket.kaynak}")
        satirlar.append("")
    if sonuc.microsoft:
        satirlar.append("Microsoft çalışma zamanı dosyaları (Microsoft-VC-calisma-zamani-NOT.txt):")
        satirlar.append("  " + ", ".join(sorted(sonuc.microsoft)))
        satirlar.append("")
    return "\n".join(satirlar) + "\n"


def paket_dizini_denetimi(
    paket_dizini: Path, bilesenler: Sequence[Bilesen], platform: str
) -> list[str]:
    """Paketin DİSKTEKİ hâli: LGPL kaynağı var mı, yasak sözlük, Qt'nin yalnız GPL'li
    modülü ya da bu platformda yersiz pywebview dosyası kalmış mı?

    TOC dosyaları Analysis anını yansıtır; spec'in sonradan süzdüğü dosyalar (pyphen
    sözlükleri, `qt_gpl_suz`, `_webview_platform_disi`) orada hâlâ görünür. Bu yüzden
    bu kurallar paketin kendisinde denetlenir.
    """
    hatalar: list[str] = []
    for bilesen in bilesenler:
        if bilesen.kaynagi_pakette and platform in bilesen.platformlar:
            ust = normal_ad(bilesen.ad).replace("-", "_")
            if not any(paket_dizini.rglob(f"{ust}/__init__.py")):
                hatalar.append(
                    f"{bilesen.ad} LGPL'dir ve kaynağı pakete girmeli; `{ust}/__init__.py` "
                    "pakette yok (spec `module_collection_mode`)"
                )
    for sozluk_dizini in paket_dizini.rglob("pyphen/dictionaries"):
        fazla = sorted(p.name for p in sozluk_dizini.iterdir() if p.name not in PYPHEN_IZINLI)
        if fazla:
            hatalar.append(
                f"pyphen sözlükleri süzülmemiş ({len(fazla)} dosya, ör. {fazla[0]}); bir kısmı "
                "yalnız GPL'dir — spec `PYPHEN_KALAN`"
            )
    hatalar += qt_gpl_paket_denetimi(paket_dizini)
    # WebView2 SDK DLL'leri yalnız Windows'ta gerekir (lisans listesi SDK'yı "yalnız
    # Windows" diye bildirir); pywebview'ın Android arşivi hiçbir pakette gerekmez.
    yersiz_uzantilar = {".jar"} if platform == "windows" else {".jar", ".dll"}
    yersiz = sorted(
        p.relative_to(paket_dizini).as_posix()
        for p in paket_dizini.rglob("*")
        if p.is_file() and p.suffix.lower() in yersiz_uzantilar and "webview" in p.parts
    )
    if yersiz:
        hatalar.append(
            f"bu platformda gereksiz pywebview dosyaları pakette ({len(yersiz)} dosya, ör. "
            f"{yersiz[0]}) — spec `_webview_platform_disi` süzgeci"
        )
    return hatalar


def paket_komutu(args: argparse.Namespace) -> int:
    """`paket` alt komutu: lisansları pakete koy, içeriği denetle."""
    paket_dizini: Path = args.paket
    calisma: Path = args.calisma
    platform: str = args.platform
    if not paket_dizini.is_dir():
        yaz(f"HATA: paket dizini yok: {paket_dizini}")
        return 2
    bilesenler = bilesenleri_oku(args.lisanslar)

    hedef = paket_dizini / LISANS_DIZINI.name
    if hedef.exists():
        shutil.rmtree(hedef)
    shutil.copytree(args.lisanslar, hedef)
    lisans_metni = (REPO / "LICENSE").read_text(encoding="utf-8")
    # Inno `LicenseFile` UTF-8 metni ancak BOM'la tanır (yoksa ANSI okur, "İ" bozulur).
    (paket_dizini / "LICENSE.txt").write_text(
        lisans_metni,
        encoding="utf-8-sig" if platform == "windows" else "utf-8",
        newline="\r\n" if platform == "windows" else "\n",
    )

    msys2 = msys2_veritabani(args.msys2_kok) if args.msys2_kok else None
    yollar = sysconfig.get_paths()
    python_kokleri = sorted({sys.base_prefix, sys.prefix, yollar["stdlib"]}, key=len, reverse=True)
    sonuc = paketi_denetle(
        kaynaklar=toc_kaynaklari(calisma),
        bilesenler=bilesenler,
        platform=platform,
        calisma=calisma,
        harita=dagitim_haritasi(),
        dll_dizini=args.dll_dizini,
        msys2=msys2,
        msys2_kok=args.msys2_kok,
        debian=platform == "linux",
        python_kokleri=python_kokleri,
        site_dizinleri=sorted({yollar["purelib"], yollar["platlib"]}),
        sistem_dizini=os.environ.get("SystemRoot") if platform == "windows" else None,
    )

    sonuc.hatalar += paket_dizini_denetimi(paket_dizini, bilesenler, platform)

    yerel_hedef = hedef / YEREL_DIZIN_ADI
    yerel_hedef.mkdir(exist_ok=True)
    python_lisansi = Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
    if not python_lisansi.is_file():
        python_lisansi = Path(sys.base_prefix) / "LICENSE.txt"
    if python_lisansi.is_file():
        shutil.copyfile(python_lisansi, yerel_hedef / "python-LICENSE.txt")
    else:
        sonuc.hatalar.append("derleme ortamındaki Python'un LICENSE.txt dosyası bulunamadı")
    for paket in sonuc.yerel.values():
        for dosya in paket.lisans_dosyalari:
            # MSYS2: share/licenses/<paket>/… altındaki göreli yol (aynı adlı iki
            # dosya çakışmasın); Debian: "copyright".
            posix = dosya.as_posix()
            ek = (
                posix.split("/share/licenses/", 1)[1] if "/share/licenses/" in posix else dosya.name
            )
            (yerel_hedef / _txt(f"{_guvenli_ad(paket.ad)}-{_guvenli_ad(ek)}")).write_bytes(
                dosya.read_bytes()
            )
    surum = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    (hedef / PAKET_ICERIGI_ADI).write_text(
        _paket_icerigi(sonuc, bilesenler, platform, surum), encoding="utf-8"
    )

    for uyari in sonuc.uyarilar:
        uyar(uyari)
    if sonuc.hatalar:
        yaz("HATA: lisans denetimi başarısız:")
        for hata in sonuc.hatalar:
            yaz(f"  - {hata}")
        return 1
    yaz(
        f"Lisans denetimi başarılı: {len(sonuc.python)} Python dağıtımı, "
        f"{len(sonuc.yerel)} sistem kütüphanesi paketi, {sonuc.proje} proje dosyası; "
        f"lisanslar → {hedef}"
    )
    return 0


# =============================================================================
# kisitlar — paket ortamının pip kısıt dosyası
# =============================================================================


def kisitlar_metni(bilesenler: Sequence[Bilesen], platform: str) -> str:
    """Listedeki Python dağıtımlarının sürümleri, pip `-c` biçiminde.

    Geçişli bağımlılıklar gereksinim dosyalarında pinli değildir (dört halka kuralı
    yalnız doğrudan bağımlılıkları pinler); kısıt dosyası paket ortamını listenin
    üretildiği sürümlere bağlar. Böylece pakete giren sürüm `BENIOKU.txt` ve
    `bilesenler.json`'dakiyle aynıdır (F12 düzeltme turu: 27.09.2026 Linux derlemesinde
    `paket-icerigi.txt` fonttools 4.66.0, liste 4.65.0 diyordu). Kısıt yalnız kurulan
    dağıtıma uygulanır; listede olup kurulmayan (ör. `KD_WITH_QT=0`'da PySide6) kurulmaz.
    """
    satirlar = [
        "# Üretildi: packaging/lisanslar/lisanslar.py kisitlar — THIRD_PARTY_LICENSES/",
        f"# bilesenler.json'daki sürümler ({platform}). Elle düzenlenmez.",
    ]
    satirlar += sorted(
        (
            f"{b.ad}=={b.surum}"
            for b in bilesenler
            if b.tur == "python" and platform in b.platformlar
        ),
        key=str.casefold,
    )
    return "\n".join(satirlar) + "\n"


# =============================================================================
# npm-denetle — Vite çıktısındaki npm paketleri listeyle aynı mı?
# =============================================================================


def npm_farki(on_yuz: dict[str, Any], bilesenler: Sequence[Bilesen]) -> list[str]:
    """`on_yuz_paketleri.mjs` çıktısı ile listedeki npm kayıtları (ad, sürüm) farkı.

    Depo testi yalnız `package.json` `dependencies` kayıtlarına bakar; bir sürüm
    yükseltmesiyle çıktıya yeni bir GEÇİŞLİ npm paketi girerse ya da yalnız tip olarak
    kullanılan bir paket (`PAKETLENMEYEN_NPM`) çalışma anında import edilmeye başlarsa
    bunu ancak bu karşılaştırma görür (F12 düzeltme turu; scripts/gates.sh).
    """
    cikti = {(str(p["ad"]), str(p["surum"])) for p in on_yuz["paketler"]}
    liste = {(b.ad, b.surum) for b in bilesenler if b.tur == "npm"}
    hatalar = [
        f"ön yüz çıktısında olup THIRD_PARTY_LICENSES'ta olmayan npm paketi: {ad} {surum}"
        for ad, surum in sorted(cikti - liste)
    ]
    hatalar += [
        f"THIRD_PARTY_LICENSES'ta olup ön yüz çıktısında olmayan npm paketi: {ad} {surum}"
        for ad, surum in sorted(liste - cikti)
    ]
    return hatalar


# =============================================================================
# deb-copyright — DEP-5 (Debian makine okunur telif biçimi 1.0)
# =============================================================================

TELIF = "2026 Ahmet Ali DEMİRCİ <aalidemirci@gmail.com>"
LISANS_KISA_ADI = "LicenseRef-PolyForm-Noncommercial-1.0.0"


def deb_copyright(lisans_metni: str) -> str:
    """`/usr/share/doc/kutuphane-defteri/copyright` içeriği (DEP-5)."""
    govde = []
    for satir in lisans_metni.rstrip("\n").splitlines():
        govde.append(" ." if not satir.strip() else " " + satir.rstrip())
    return (
        "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"
        "Upstream-Name: kutuphane-defteri\n"
        f"Upstream-Contact: {KAYNAK_TEKLIF_ADRESI}\n"
        f"Source: {DEPO_ADRESI}\n"
        "Comment: Programın kendi kodu PolyForm Noncommercial 1.0.0 lisanslıdır.\n"
        " Paketle dağıtılan üçüncü taraf bileşenlerin (Python ve arayüz kitaplıkları,\n"
        " Qt 6 / PySide6, yazı tipleri, sistem kütüphaneleri) adları, sürümleri,\n"
        " lisansları ve lisans metinleri\n"
        " /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/ dizinindedir (BENIOKU.txt,\n"
        " bilesenler.json, paket-icerigi.txt, yerel-kutuphaneler/). LGPL\n"
        " bileşenlerinin kaynak kodu için yazılı teklif BENIOKU.txt'dedir.\n"
        "\n"
        "Files: *\n"
        f"Copyright: {TELIF}\n"
        f"License: {LISANS_KISA_ADI}\n"
        "\n"
        "Files: opt/kutuphane-defteri/_internal/*\n"
        "Copyright: Üçüncü taraf bileşenlerin kendi telif sahipleri\n"
        "License: LicenseRef-ucuncu-taraf\n"
        "Comment: Bu dizindeki proje dışı dosyaların lisansları\n"
        " /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/ altında, bileşen bileşen\n"
        " verilir. Programın kendi kaynak ağacı (_internal/backend, _internal/frontend)\n"
        f" {LISANS_KISA_ADI} lisanslıdır.\n"
        "\n"
        "Files: opt/kutuphane-defteri/kutuphane-defteri\n"
        f"Copyright: {TELIF}\n"
        " PyInstaller Development Team\n"
        " Üçüncü taraf Python kitaplıklarının kendi telif sahipleri\n"
        "License: LicenseRef-ucuncu-taraf\n"
        "Comment: Çalıştırılabilir dosya PyInstaller'ın önyükleyicisini\n"
        " (GPL-2.0-or-later WITH Bootloader-exception) ve gömülü bir arşivde programın\n"
        f" masaüstü kodunu ({LISANS_KISA_ADI}) ile üçüncü taraf Python kitaplıklarının\n"
        " bayt kodunu taşır. Bileşen başına lisans:\n"
        " /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/BENIOKU.txt\n"
        "\n"
        "Files: opt/kutuphane-defteri/THIRD_PARTY_LICENSES/*\n"
        "Copyright: Üçüncü taraf bileşenlerin kendi telif sahipleri\n"
        "License: LicenseRef-ucuncu-taraf\n"
        "Comment: Üçüncü taraf bileşenlerin lisans metinleri ve bildirimleri.\n"
        "\n"
        f"License: {LISANS_KISA_ADI}\n" + "\n".join(govde) + "\n"
        "\n"
        "License: LicenseRef-ucuncu-taraf\n"
        " Bileşen başına lisans: /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/BENIOKU.txt\n"
    )


# =============================================================================
# Komut satırı
# =============================================================================


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Üçüncü taraf lisansları (THIRD_PARTY_LICENSES).")
    alt = parser.add_subparsers(dest="komut", required=True)

    p_uret = alt.add_parser("uret", help="Depodaki THIRD_PARTY_LICENSES/ dizinini üretir.")
    p_uret.add_argument("--on-yuz", type=Path, required=True, help="on_yuz_paketleri.mjs çıktısı")
    p_uret.add_argument("--hedef", type=Path, default=LISANS_DIZINI)

    p_paket = alt.add_parser("paket", help="Paketi denetler, lisansları pakete koyar.")
    p_paket.add_argument("--paket", type=Path, required=True, help="PyInstaller çıktı dizini")
    p_paket.add_argument("--calisma", type=Path, required=True, help="PyInstaller workpath/<spec>")
    p_paket.add_argument(
        "--platform",
        choices=PLATFORMLAR,
        default="windows" if sys.platform.startswith("win") else "linux",
    )
    p_paket.add_argument("--lisanslar", type=Path, default=LISANS_DIZINI)
    p_paket.add_argument("--dll-dizini", type=Path, default=None, help="(Windows) KD_DLL_DIR")
    p_paket.add_argument("--msys2-kok", type=Path, default=None, help="(Windows) msys64 kökü")

    p_kisit = alt.add_parser("kisitlar", help="Paket ortamının pip kısıt dosyasını yazar.")
    p_kisit.add_argument("--platform", choices=PLATFORMLAR, required=True)
    p_kisit.add_argument("--lisanslar", type=Path, default=LISANS_DIZINI)
    p_kisit.add_argument("--cikti", type=Path, required=True, help="yazılacak kısıt dosyası")

    p_npm = alt.add_parser("npm-denetle", help="Vite çıktısındaki npm paketleri listede mi?")
    p_npm.add_argument("--on-yuz", type=Path, required=True, help="on_yuz_paketleri.mjs çıktısı")
    p_npm.add_argument("--lisanslar", type=Path, default=LISANS_DIZINI)

    p_deb = alt.add_parser("deb-copyright", help=".deb için DEP-5 copyright dosyası yazar.")
    p_deb.add_argument("cikti", type=Path)

    args = parser.parse_args(argv)
    if args.komut == "uret":
        uret(args.on_yuz, args.hedef)
        return 0
    if args.komut == "paket":
        return paket_komutu(args)
    if args.komut == "kisitlar":
        # Dosyaya yazılır (PowerShell 5.1'in `>` yönlendirmesi UTF-16 yazar, pip okuyamaz).
        args.cikti.parent.mkdir(parents=True, exist_ok=True)
        args.cikti.write_text(
            kisitlar_metni(bilesenleri_oku(args.lisanslar), args.platform), encoding="utf-8"
        )
        return 0
    if args.komut == "npm-denetle":
        on_yuz = json.loads(args.on_yuz.read_text(encoding="utf-8"))
        hatalar = npm_farki(on_yuz, bilesenleri_oku(args.lisanslar))
        if hatalar:
            yaz(
                "HATA: ön yüz lisans listesi Vite çıktısıyla ayrıştı "
                "(`bash packaging/lisanslar/uret.sh`):"
            )
            for hata in hatalar:
                yaz(f"  - {hata}")
            return 1
        yaz(f"Ön yüz lisans listesi güncel: {len(on_yuz['paketler'])} npm paketi.")
        return 0
    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    args.cikti.write_text(
        deb_copyright((REPO / "LICENSE").read_text(encoding="utf-8")), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
