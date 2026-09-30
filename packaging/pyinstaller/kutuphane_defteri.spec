# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Kütüphane Defteri (Windows + Linux ORTAK).

Kullanım (depo kökünden; Windows'ta ÖNCE `python packaging/windows/dll_kapanisi.py`
koşmuş olmalı — DLL klasörü üretilen çıktıdır, depoda tutulmaz):

    pyinstaller --noconfirm --clean packaging/pyinstaller/kutuphane_defteri.spec

Ortam değişkenleri:
    KD_WITH_QT=0   → PySide6/QtWebEngine paketlenmez (yalnız `--autotest`/CI
                     doğrulaması için küçük ve hızlı derleme; pencere AÇILMAZ).
    KD_DLL_DIR     → (Windows) `dll_kapanisi.py` ile üretilmiş DLL klasörü.

--------------------------------------------------------------------------
BİLİNÇLİ SEÇİM — backend KAYNAK OLARAK paketlenir
--------------------------------------------------------------------------
Alışılmış yol `collect_submodules('apps')` ile Django uygulamalarını donmuş
arşive gömmektir. BURADA BAŞKA YOL SEÇİLDİ (KS'den devralındı): `backend/`
ağacı KAYNAK DOSYA olarak pakete kopyalanır, çalışma anında
`desktop.django_bootstrap` `sys.path`'e ekler. Gerekçeler:

1. `desktop/paths.py::resolve_backend_dir()` paketin içinde gerçek bir
   `backend/config/settings.py` DOSYASI arar ve bulamazsa açılışı durdurur.
   Donmuş arşive gömülen modüller diskte dosya olarak görünmez; kabuk yeniden
   yazılmadan donmuş yol çalışmaz.
2. Django'nun göç yükleyicisi, şablon yükleyicisi ve uygulama keşfi dosya
   sistemine dayanır; kaynak ağaç bu üç mekanizmayı da tuzaksız çalıştırır
   ("migrations dinamik import tuzağı" bu yolda hiç doğmaz).
3. Sahada teşhis kolaylaşır: bir şablonun içeriği okunabilir/düzeltilebilir.

BEDELİ: diskteki kaynak kodu PyInstaller'ın statik çözümleyicisi TARAMAZ.
Dolayısıyla backend'in kullandığı ÜÇÜNCÜ TARAF paketler bu dosyada AÇIKÇA
`hiddenimports` olarak sayılmak ZORUNDADIR. Backend'e yeni bir üçüncü taraf
bağımlılık eklenirse buraya da eklenmelidir; unutulursa paket "geliştirmede
çalışıyor, kurulumda çöküyor" hatası verir. Zincirin dört halkası:
`backend/requirements.txt` → `packaging/tests/test_spec_kapsami.py` eşlemesi →
bu dosyadaki `hiddenimports` → `giris.py::RUNTIME_MODULES`. Paketlenmiş ikilide
`--bagimlilik-duman` her modülü gerçekten import eder; `--pdf-duman` evrak
şablonlarını ve WeasyPrint zincirini her derlemede sınar.

Yalnız masaüstünde gereken Windows paketleri (pystray, six, pythonnet) ayrı
zincirdedir: `packaging/requirements-paketleme.txt` (`sys_platform == "win32"`)
→ aşağıdaki `if WINDOWS:` bloğu → `giris.py::DESKTOP_RUNTIME_MODULES`.
`test_spec_kapsami.py` iki zinciri de platform işaretine göre denetler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# `SPECPATH` PyInstaller tarafından tanımlanır (spec dosyasının bulunduğu dizin).
REPO = Path(SPECPATH).resolve().parents[1]  # noqa: F821 — PyInstaller global'i

WINDOWS = sys.platform.startswith("win")
WITH_QT = os.environ.get("KD_WITH_QT", "1").strip() not in {"0", "false", "no"}

DIST_NAME = "kutuphane-defteri"
ENTRY = REPO / "packaging" / "pyinstaller" / "giris.py"
RUNTIME_HOOK = REPO / "packaging" / "pyinstaller" / "rthook_kd.py"
ICON = REPO / "packaging" / "ikonlar" / "kutuphane-defteri.ico"

# ---------------------------------------------------------------------------
# Kaynak ağaçları (kaynak dosya olarak kopyalanır)
# ---------------------------------------------------------------------------
_TREE_EXCLUDES = ["__pycache__", "tests", "*.pyc", "*.pyo", ".pytest_cache", ".mypy_cache"]

trees = [
    Tree(str(REPO / "backend" / "config"), prefix="backend/config", excludes=_TREE_EXCLUDES),
    Tree(str(REPO / "backend" / "apps"), prefix="backend/apps", excludes=_TREE_EXCLUDES),
    Tree(str(REPO / "backend" / "shared"), prefix="backend/shared", excludes=_TREE_EXCLUDES),
    # Ağ Kataloğu WSGI (tasarım §4.1): Django uygulaması değildir, apps/ altında
    # olmadığı için ayrı ağaç. Eksik kalırsa paketli exe'de katalog açılmaz
    # (--autotest bunu 6 koduyla yakalar).
    Tree(str(REPO / "backend" / "katalog"), prefix="backend/katalog", excludes=_TREE_EXCLUDES),
    # Evrak şablonları — `--pdf-duman` taban şablonu buradan işleyerek sınar.
    Tree(str(REPO / "backend" / "templates"), prefix="backend/templates", excludes=_TREE_EXCLUDES),
    # Derlenmiş SPA — `frontend/dist` boşsa paket açılır ama beyaz ekran verir;
    # `packaging/linux/build.sh` bunu derleme öncesi denetler.
    Tree(str(REPO / "frontend" / "dist"), prefix="frontend/dist", excludes=_TREE_EXCLUDES),
]

datas: list[tuple[str, str]] = [
    # Sürüm damgası — `desktop/version.py` paket kökünde arar.
    (str(REPO / "VERSION"), "."),
    # Kullanıcıya dağıtılan her kopyada bağlayıcı lisans metni bulunur.
    (str(REPO / "LICENSE"), "."),
    # WinForms pencere ikonu çalışma anında `desktop/window.py` tarafından atanır.
    (str(ICON), "."),
]

# ---------------------------------------------------------------------------
# Fontlar + Windows font yapılandırması
# ---------------------------------------------------------------------------
# "fontconfig tuzağı": Windows'ta YALNIZ gömülü DejaVu kullanılır. Linux'ta sistem
# fontu (.deb bağımlılığı `fonts-dejavu-core`) kullanılır; yine de fontlar
# pakete konur ki taşınabilir `.tar.gz` kurulumunda font eksikse metin
# bozulmasın — Linux'ta `FONTCONFIG_FILE` AYARLANMAZ, bu kopya atıl durur.
for ttf in sorted((REPO / "packaging" / "fontlar").glob("*.ttf")):
    datas.append((str(ttf), "fonts"))
datas.append((str(REPO / "packaging" / "fontlar" / "DejaVu-LISANS.txt"), "fonts"))
datas.append((str(REPO / "packaging" / "pyinstaller" / "fonts.conf.tmpl"), "."))

# ---------------------------------------------------------------------------
# Üçüncü taraf paket verileri
# ---------------------------------------------------------------------------
datas += collect_data_files("django")  # tr yerelleştirmesi, şablonlar, .mo dosyaları
datas += collect_data_files("rest_framework")
datas += collect_data_files("weasyprint")  # gömülü CSS'ler (html5_ua.css …)
datas += collect_data_files("pyphen")  # heceleme sözlükleri
datas += collect_data_files("tinyhtml5")
datas += collect_data_files("webview")  # js/ (her platform) + Windows: WebView2 DLL'leri

# ---------------------------------------------------------------------------
# Windows DLL kapanışı (ntldd/objdump ile üretilir — elle liste YOK)
# ---------------------------------------------------------------------------
binaries: list[tuple[str, str]] = []
binaries += collect_dynamic_libs("webview")


# LİSANS BEYANI (F12 düzeltme turu, 27.09.2026 Qt'li Linux derlemesi): pywebview
# `webview/lib/` altında Microsoft'un WebView2 SDK DLL'lerini ve bir Android arşivini
# (`pywebview-android.jar`) taşır. SDK yalnız Windows'ta kullanılır (lisans listesi onu
# "yalnız Windows" diye bildirir); Android arşivi hiçbir pakette kullanılmaz. Süzgeçsiz
# `collect_*` ikisini de Linux paketine koyuyordu. Derleme sonrası denetim
# (`lisanslar.py paket`) bu dosyaları pakette görürse derlemeyi durdurur.
#
# Süzgeç İKİ yerde uygulanır: burada (spec'in kendi `collect_*` girdileri; Linux'ta PE
# DLL'leri bağımlılık çözümlemesine hiç girmesin) ve Analysis'ten SONRA (aşağıda).
# pywebview kendi PyInstaller kancasını taşır (`webview/__pyinstaller/hook-webview.py`,
# `pyinstaller40` giriş noktası) ve Windows'ta `collect_data_files('webview',
# subdir='lib')` ile Android arşivini de Analysis SIRASINDA ekler — 29.09.2026 CI Windows
# koşusunda yalnız girdi süzgeci olduğu için arşiv pakete girdi. `lib/runtimes/win-arm64`
# ve `win-x86` Windows'ta KALIR: `webview/platforms/edgechromium.py` üç dizini de
# `interop_dll_path` ile PATH'e ekler ve bulamadığında FileNotFoundError verir.
def _webview_platform_disi(hedef: str) -> bool:
    """Paket içi hedef yol (ör. `webview/lib/pywebview-android.jar`) bu platformda yersiz mi?"""
    yol = hedef.replace("\\", "/")
    if yol.rsplit("/", 1)[-1].casefold() == "pywebview-android.jar":
        return True
    return not WINDOWS and yol.startswith("webview/lib/")


def _girdi_hedefi(oge: tuple[str, str]) -> str:
    """spec girdisi (kaynak, hedef dizin) → paket içi hedef yol."""
    return oge[1].replace("\\", "/").rstrip("/") + "/" + Path(oge[0]).name


datas = [oge for oge in datas if not _webview_platform_disi(_girdi_hedefi(oge))]
binaries = [oge for oge in binaries if not _webview_platform_disi(_girdi_hedefi(oge))]

if WINDOWS:
    dll_dir = Path(os.environ.get("KD_DLL_DIR", str(REPO / "packaging" / "windows" / "dll")))
    if not dll_dir.is_dir():
        raise SystemExit(
            f"DLL klasörü yok: {dll_dir}. Önce `python packaging/windows/dll_kapanisi.py` "
            "çalıştırın."
        )
    dll_files = sorted(dll_dir.glob("*.dll"))
    if not dll_files:
        raise SystemExit(f"DLL klasörü boş: {dll_dir}.")
    for dll in dll_files:
        # Paket köküne konur; `rthook_kd.py` WEASYPRINT_DLL_DIRECTORIES ile gösterir.
        binaries.append((str(dll), "."))

# ---------------------------------------------------------------------------
# Gizli import'lar — diskteki backend kodunun ihtiyaç duyduğu her paket
# ---------------------------------------------------------------------------
hiddenimports: list[str] = []
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("rest_framework")
hiddenimports += collect_submodules("whitenoise")
hiddenimports += collect_submodules("waitress")
hiddenimports += collect_submodules("weasyprint")
hiddenimports += collect_submodules("fontTools")
hiddenimports += collect_submodules("openpyxl")
# e-Okul .xls (BIFF) okuyucusu — `excel_ogrenci._read_xls` içinde YEREL import
# edilir; PyInstaller'ın statik çözümleyicisi fonksiyon içi importu görse de
# xlrd alt modüllerini (biffh, compdoc, formula…) kendiliğinden toplamaz.
hiddenimports += collect_submodules("xlrd")
hiddenimports += collect_submodules("pypdf")
# Etiketteki isteğe bağlı QR (tasarım §7.2). Backend kaynak olarak paketlendiği
# için segno'yu statik çözümleyici görmez; `segno.helpers` gibi paketin kendi
# `__init__`'inin import etmediği alt modüller de ancak böyle toplanır.
hiddenimports += collect_submodules("segno")
# LİSANS KAPISI (F12, 27.09.2026 yerel derlemesi): pywebview kendi PyInstaller
# kancasını (`webview.__pyinstaller.hook-webview`) paketinin İÇİNDE taşır; süzgeçsiz
# `collect_submodules` onu da toplar, kanca `PyInstaller.utils.hooks`'u import
# ettiği için PyInstaller'ın derleme kodu (GPL-2.0+, önyükleyici istisnası DIŞINDA)
# ve altgraph pakete sürüklenirdi. Kanca yalnız derleme anında kullanılır.
hiddenimports += collect_submodules(
    "webview", filter=lambda ad: not ad.startswith("webview.__pyinstaller")
)
if WINDOWS:
    # pywebview edgechromium arka ucu .NET köprüsünü `import clr` ile açar;
    # pythonnet zinciri eksik paketlenirse pencere HİÇ açılmaz ve ne --autotest
    # ne --pdf-duman bunu yakalar (NOTLAR.md W9 — açık sigorta). `clr`
    # `giris.py::DESKTOP_RUNTIME_MODULES`'ta; `--bagimlilik-duman` onu da açar.
    hiddenimports += ["clr", "pythonnet"]
    # Masaüstü zinciri: Windows tepsisi (tasarım §4.5, denetim UY-6; okulzili
    # `okul-zili.spec` emsali). Paketler `requirements-paketleme.txt`'te
    # `sys_platform == "win32"` işaretiyle durur; çalışma anı kapısı
    # `giris.py::DESKTOP_RUNTIME_MODULES`.
    # - pystray arka ucunu `import pystray` anında `importlib` ile seçer
    #   (`pystray._win32`); statik çözümleyici bunu göremez → bütün alt modüller.
    #   Linux/macOS arka uçları (`_xorg`, `_gtk`, `_darwin`, `_appindicator`)
    #   Windows'ta çözülemez; PyInstaller bunları yalnız uyarı olarak yazar.
    # - `six.moves` çalışma anında üretilen sanal modüldür; pystray `_base` ve
    #   `_win32` onu import eder.
    # - `PIL.ImageDraw` tepsi simgesi çizimi; `PIL.IcoImagePlugin` pystray'in
    #   Windows'ta simgeyi geçici ICO dosyasına yazması (`serialized_image`) için.
    hiddenimports += collect_submodules("pystray")
    hiddenimports += ["six", "six.moves", "PIL.ImageDraw", "PIL.IcoImagePlugin"]
hiddenimports += [
    # WeasyPrint zinciri
    "pydyf",
    "tinycss2",
    "cssselect2",
    "tinyhtml5",
    "pyphen",
    # WeasyPrint evraktaki raster görselleri Pillow ile çözer; Pillow biçim
    # eklentilerini çalışma anında dizeyle yüklediği için açıkça sayılır.
    "PIL",
    "PIL.Image",
    "PIL.JpegImagePlugin",
    "PIL.PngImagePlugin",
    "brotli",
    "zopfli",
    # Yönetici parolası (Argon2id) + alan şifrelemesi (Fernet): cffi ikilisi
    # `argon2` ile otomatik toplanmayabilir; eksikse kilit HİÇ açılmaz ve
    # `--pdf-duman` bunu yakalamaz (ayrı zincir — `--bagimlilik-duman` yakalar).
    "argon2",
    "argon2.low_level",
    "_argon2_cffi_bindings",
    "cryptography",
    "cryptography.fernet",
    # Backend yardımcıları
    "sqlparse",
    # Django SQLite arka ucu (dizeyle import edilir)
    "django.db.backends.sqlite3",
    "django.db.backends.sqlite3.base",
]

if WITH_QT:
    # Linux/Pardus penceresi ve tepsisi: PySide6 (LGPLv3 — GPLv3'lü PyQt5'ten
    # 23.09.2026'da bu yüzden çıkıldı; requirements-paketleme.txt başlığı).
    # PyInstaller'ın PySide6 kancaları QtWebEngineProcess yardımcı sürecini,
    # Qt eklentilerini, kaynak dosyalarını ve çevirileri bu import'lar
    # üzerinden toplar.
    #
    # qtpy AYRICA sayılır: pywebview'ın Qt arka ucu bağlayıcıya doğrudan değil
    # qtpy üzerinden ulaşır (`webview/platforms/qt.py`). Statik çözümleyici
    # `webview.platforms.qt`'yi bu listeden tanıdığı için qtpy modüllerini de
    # izler; liste yine de açık tutulur (halkanın gözle görünür olması).
    #
    # `QtPrintSupport` BİLEREK YOK: evrak WeasyPrint'ten basılır, Qt'nin
    # yazdırma eklentisi hiç kullanılmaz (eklenseydi sistemden `libcups2`
    # bağımlılığı doğardı). QtWebEngineWidgets'ın bağlandığı
    # `libQt6PrintSupport.so.6` paylaşılan kütüphane olarak zaten gelir.
    hiddenimports += [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "qtpy",
        "qtpy.QtCore",
        "qtpy.QtGui",
        "qtpy.QtWidgets",
        "qtpy.QtNetwork",
        "qtpy.QtWebChannel",
        "qtpy.QtWebEngineWidgets",
        "webview.platforms.qt",
    ]

# ---------------------------------------------------------------------------
# Dışlananlar — paket boyutu + AV yanlış-pozitif yüzeyi
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "pytest",
    "_pytest",
    "factory",
    "faker",
    "coverage",
    "mypy",
    "ruff",
    "django_stubs_ext",
    "IPython",
    "numpy",
    "matplotlib",
    "psycopg",
    "psycopg2",
    "redis",
    "celery",
    # Qt bağlayıcılarından pakete YALNIZ PySide6 girer. İkisi birden kurulu
    # olsaydı qtpy `QT_API` verilmediğinde ilk bulduğunu seçerdi; dahası PyQt
    # GPLv3'tür ve bu ürünün lisansıyla birlikte dağıtılamaz (LİSANS KAPISI —
    # packaging/tests/test_lisans_kapisi.py).
    "PyQt5",
    "PyQt6",
    "PySide2",
    # LİSANS KAPISI (F12, 27.09.2026 yerel Linux derlemesi): stdlib `readline`
    # eklentisi Linux'ta GNU readline'a (libreadline.so.8, GPL-3.0) bağlıdır ve
    # Django `shell`, pdb, cmd ile code'un KOŞULLU import'u yüzünden pakete
    # giriyordu. Program etkileşimli kabuk açmaz; o import'ların hepsi
    # `except ImportError` ile korunur. Derleme sonrası denetim
    # (packaging/lisanslar/lisanslar.py `paket`) GPL'li yerel kütüphaneyi
    # yakalarsa derlemeyi durdurur.
    "readline",
]
if not WITH_QT:
    excludes += ["PySide6", "qtpy"]

# ---------------------------------------------------------------------------
# LGPL kaynağı pakette (F12, TB28): pystray LGPLv3'tür. Modülleri PYZ arşivine
# bayt kodu olarak değil, `_internal/pystray/` altına KAYNAK DOSYA (.py) olarak
# konur: kullanıcı kütüphaneyi değiştirip programı onunla çalıştırabilir
# (LGPLv3 §4) ve kaynak pakettedir (CLAUDE.md §2-10). Derleme sonrası denetim
# `pystray/__init__.py` dosyasını arar, yoksa derlemeyi durdurur.
# ---------------------------------------------------------------------------
module_collection_mode = {"pystray": "py"} if WINDOWS else {}

a = Analysis(  # noqa: F821 — PyInstaller global'i
    [str(ENTRY)],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(RUNTIME_HOOK)],
    excludes=excludes,
    noarchive=False,
    module_collection_mode=module_collection_mode,
    optimize=0,
)

# ---------------------------------------------------------------------------
# pyphen heceleme sözlükleri (LİSANS KAPISI, F12): pyinstaller-hooks-contrib'in
# `hook-pyphen` kancası pyphen'in BÜTÜN veri dosyalarını toplar. Sözlükler
# LibreOffice'ten gelir ve tek tek lisanslıdır; bir kısmı yalnız GPL'dir (gl,
# pt_PT, ro_RO). Evrak Türkçedir, şablonlar `hyphens: auto` kullanmaz ve
# pyphen'de Türkçe sözlük yoktur — sözlükler hiç kullanılmaz. Dizin BOŞ
# kalamaz (pyphen import anında listeler), bu yüzden yalnız izinli lisanslı
# en_US sözlüğü ve bildirimi kalır.
# ---------------------------------------------------------------------------
PYPHEN_KALAN = {"hyph_en_US.dic", "README_hyph_en_US.txt"}


def _pyphen_sozlugu_atilir(hedef: str) -> bool:
    yol = hedef.replace("\\", "/")
    return yol.startswith("pyphen/dictionaries/") and yol.rsplit("/", 1)[-1] not in PYPHEN_KALAN


a.datas = [oge for oge in a.datas if not _pyphen_sozlugu_atilir(oge[0])]

# ---------------------------------------------------------------------------
# Analysis SONRASI lisans süzgeçleri. PyInstaller'ın kancaları ve ikili bağımlılık
# çözümlemesi dosyaları Analysis SIRASINDA ekler; spec girdisini süzmek onları görmez.
# Kurallar TEK kaynaktadır (`packaging/lisanslar/lisanslar.py`, yalnız standart
# kitaplık). Derleme sonrası denetim (`lisanslar.py paket`) paketin SON TOC'larını
# (COLLECT/PYZ/PKG/EXE) ve diskteki hâlini aynı kurallarla yeniden sınar.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(REPO / "packaging" / "lisanslar"))
import lisanslar as _lisanslar  # noqa: E402 — yalnız standart kitaplık

a.datas = [oge for oge in a.datas if not _webview_platform_disi(oge[0])]
a.binaries = [oge for oge in a.binaries if not _webview_platform_disi(oge[0])]

# Universal CRT (LİSANS KAPISI, 29.09.2026 CI Windows koşusu): PyInstaller 6.11
# `ucrtbase.dll` ve `api-ms-win-*.dll`'i `_win_includes` listesinde tutar ve python312.dll'in
# bağımlılığını PATH'te bulduğu ilk kopyadan toplar — koşucuda Temurin JDK'nın `bin`
# klasöründen 43 sahipsiz dosya girdi. UCRT Windows 10/11'de işletim sisteminin
# bileşenidir; uygulama klasöründeki kopya kullanılmaz (Microsoft Learn, "Universal CRT
# deployment" → "Local deployment"). Program yalnız Windows 10/11'i hedefler (Inno
# `MinVersion=10.0`). Kural ve gerekçe: `lisanslar.UCRT_DLL`.
a.binaries, _ucrt_ayiklanan = _lisanslar.ucrt_suz(a.binaries)
a.datas, _ucrt_veri = _lisanslar.ucrt_suz(a.datas)
if _ucrt_ayiklanan or _ucrt_veri:
    _lisanslar.yaz(
        f"LİSANS: Universal CRT'den {len(_ucrt_ayiklanan) + len(_ucrt_veri)} dosya ayıklandı "
        "(Windows 10/11 sistemdekini kullanır)."
    )

# Paket içi fontconfig yapılandırması (Windows; 29.09.2026 doğrulama turu). hooks-contrib
# `hook-weasyprint` MSYS2'nin `etc/fonts` ağacını (fonts.conf + conf.d) toplar; Windows'ta
# libfontconfig yapılandırmayı DLL'in yanındaki `etc/fonts/fonts.conf`'tan okur ve
# `FONTCONFIG_FILE`'ı dinlemez. MSYS2 varsayılanı Windows font dizinini tarar (evrak
# sistem fontuyla dizilir); bu yüzden o dosya projenin `fonts.paket.conf`'udur. Değiştirme
# TOC'ta yapılır: önceden build.ps1 dosyayı lisans denetiminden SONRA eziyordu ve
# `paket-icerigi.txt` pakette olmayan MSYS2 dosyasını anlatıyordu. conf.d pakete girmez:
# projenin fonts.conf'u `<include>` taşımadığı için hiç yüklenmiyordu. `lisanslar.py paket`
# diskte yalnız bu dosyayı kabul eder; `--pdf-duman` PDF'in DejaVu ile dizildiğini sınar.
if WINDOWS:
    a.datas, _fontconfig_ayiklanan = _lisanslar.fontconfig_yerlestir(a.datas)
    _lisanslar.yaz(
        f"fontconfig: MSYS2'nin etc/fonts ağacından {len(_fontconfig_ayiklanan)} dosya "
        "ayıklandı; etc/fonts/fonts.conf = packaging/pyinstaller/fonts.paket.conf."
    )

# ---------------------------------------------------------------------------
# Qt'nin yalnız GPL'li modülleri (LİSANS KAPISI, F12 düzeltme turu): PyInstaller'ın
# PySide6 kancaları QtWebEngine'in Quick/Qml bağımlılığı üzerinden BÜTÜN QML
# modüllerini ve eklentilerini toplar; aralarında Qt'nin açık kaynak sürümünde yalnız
# GPL-3.0 ile sunulan modüller vardır (Charts, Data Visualization, Graphs, Quick 3D,
# Quick Timeline, Virtual Keyboard, Wayland Compositor …). Program bunların hiçbirini
# kullanmaz (pencere QtWebEngineWidgets'tır, QML yüklemez). Liste ve kural TEK
# kaynaktadır (`packaging/lisanslar/lisanslar.py::QT_YALNIZ_GPL_MODULLER`): ada göre
# ayıklanır, sonra ayıklanan kitaplığa bağlanan (DT_NEEDED) her ikili de çıkar.
# Derleme sonrası denetim aynı kuralı paketin diskteki hâlinde sınar.
# ---------------------------------------------------------------------------
if WITH_QT and not WINDOWS:
    a.binaries, a.datas, _qt_gpl_ayiklanan = _lisanslar.qt_gpl_suz(a.binaries, a.datas)
    # `yaz` konsolun kodlayamadığı harfi kaçışa çevirir (CI konsolu CP1252 olabilir).
    _lisanslar.yaz(
        f"LİSANS: Qt'nin yalnız GPL'li modüllerinden {len(_qt_gpl_ayiklanan)} dosya ayıklandı."
    )

pyz = PYZ(a.pure)  # noqa: F821 — PyInstaller global'i

exe = EXE(  # noqa: F821 — PyInstaller global'i
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=DIST_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX KAPALI: sıkıştırılmış çalıştırılabilirler antivirüs yanlış-pozitifinin
    # başlıca kaynağıdır.
    upx=False,
    # Windows'ta konsol penceresi açılmaz. Teşhis çıktısı günlük dosyasına ve
    # süreç çıkış koduna düşer (`--autotest`, `--pdf-duman`).
    console=not WINDOWS,
    disable_windowed_traceback=False,
    icon=str(ICON) if (WINDOWS and ICON.is_file()) else None,
)

coll = COLLECT(  # noqa: F821 — PyInstaller global'i
    exe,
    a.binaries,
    a.datas,
    *trees,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=DIST_NAME,
)
