"""hiddenimports zincirinin otomatik kapısı: spec ↔ backend/requirements.txt.

Backend pakete KAYNAK olarak kopyalanır; PyInstaller statik çözümleyicisi orayı
taramaz (spec docstring'i). Yeni bir üçüncü taraf bağımlılık spec'e elle
eklenmek ZORUNDADIR — unutulursa paket geliştirmede çalışır, sahada çöker
(hiddenimports tuzağı). Bu test unutmayı kapıya bağlar (KS'den devralındı).

İkinci zincir masaüstüdür (tasarım §4.5, denetim UY-6): yalnız kabuğun
gerektirdiği Windows paketleri `packaging/requirements-paketleme.txt`'te
`sys_platform == "win32"` işaretiyle durur, spec'in `if WINDOWS:` bloğunda
toplanır ve `giris.py::DESKTOP_RUNTIME_MODULES` ile paketli ikilide import
edilir. Testler iki listeyi platform işaretine göre eşitler.

Ayrıca `giris.py` teşhis kipinin sözleşmesi sabitlenir: bayrak adı, çıkış kodu
(desktop/errors.py ile ikiz) ve hedef dosya ayrıştırması — üç paket betiği
(build.ps1, build.sh, kap-ici-test.sh) bu sözleşmeye dışarıdan bağlıdır.
"""

from __future__ import annotations

import ast
import re
import runpy
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "packaging" / "pyinstaller" / "kutuphane_defteri.spec"
REQUIREMENTS = REPO / "backend" / "requirements.txt"
PAKETLEME_REQUIREMENTS = REPO / "packaging" / "requirements-paketleme.txt"

#: PyPI dağıtım adı → import (modül) adı. Yeni bağımlılıkta buraya satır eklenir;
#: eşleme yoksa test bilinçli KIRILIR (sessiz kapsam kaybındansa gürültü iyidir).
DAGITIM_IMPORT_ESLEME = {
    "django": "django",
    "djangorestframework": "rest_framework",
    "argon2-cffi": "argon2",
    "cryptography": "cryptography",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "pillow": "PIL",
    "weasyprint": "weasyprint",
    "pypdf": "pypdf",
    "whitenoise": "whitenoise",
    "waitress": "waitress",
    "segno": "segno",
}

_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==", re.MULTILINE)


def _gereksinimler() -> list[str]:
    return [ad.casefold() for ad in _PIN.findall(REQUIREMENTS.read_text(encoding="utf-8"))]


def test_her_backend_bagimliligi_spec_kapsaminda() -> None:
    spec_metni = SPEC.read_text(encoding="utf-8")
    eksik: list[str] = []
    for dagitim in _gereksinimler():
        modul = DAGITIM_IMPORT_ESLEME.get(dagitim)
        assert modul is not None, (
            f"requirements.txt'e yeni bağımlılık girmiş: {dagitim!r}. "
            "Önce DAGITIM_IMPORT_ESLEME'ye eşlemesini, sonra spec hiddenimports'a "
            "modülünü ekleyin (hiddenimports zinciri)."
        )
        kapsandi = f'collect_submodules("{modul}")' in spec_metni or f'"{modul}"' in spec_metni
        if not kapsandi:
            eksik.append(f"{dagitim} → {modul}")
    assert eksik == [], f"spec hiddenimports şu bağımlılıkları kapsamıyor: {eksik}"


def test_spec_yalniz_var_olan_kaynak_agaclarini_paketler() -> None:
    """spec'teki her `Tree(REPO / ...)` kaynağı depoda bulunmalı.

    Silinen bir veri ağacı spec'te kalırsa PyInstaller derlemesi Windows/Linux
    koşusunda ancak dakikalar sonra düşer; bu kapı aynı hatayı saniyede verir.
    `frontend/dist` derleme çıktısıdır, depoda tutulmaz — muaf.
    """
    spec_metni = SPEC.read_text(encoding="utf-8")
    agaclar = re.findall(r'Tree\(\s*str\(REPO((?:\s*/\s*"[^"]+")+)\)', spec_metni)
    assert agaclar, "spec'te Tree kaynağı bulunamadı (desen değişti mi?)"
    eksik: list[str] = []
    for ham in agaclar:
        goreli = "/".join(re.findall(r'"([^"]+)"', ham))
        if goreli == "frontend/dist":
            continue
        if not (REPO / goreli).is_dir():
            eksik.append(goreli)
    assert eksik == [], f"spec depoda olmayan kaynak ağaçlarını paketliyor: {eksik}"


# ---------------------------------------------------------------------------
# giris.py teşhis kipi sözleşmesi
# ---------------------------------------------------------------------------
_GIRIS = runpy.run_path(str(REPO / "packaging" / "pyinstaller" / "giris.py"))
_ERRORS = runpy.run_path(str(REPO / "desktop" / "errors.py"))


def test_pdf_duman_bayragi_ve_cikis_kodu_sozlesmesi() -> None:
    assert _GIRIS["PDF_SMOKE_FLAG"] == "--pdf-duman"  # build.ps1 / build.sh / kap-ici-test
    assert _GIRIS["EXIT_PDF_SMOKE_FAILED"] == _ERRORS["EXIT_PDF_SMOKE_FAILED"] == 8


def test_bagimlilik_duman_bayragi_ve_cikis_kodu_sozlesmesi() -> None:
    assert _GIRIS["IMPORT_SMOKE_FLAG"] == "--bagimlilik-duman"
    assert _GIRIS["EXIT_IMPORT_SMOKE_FAILED"] == _ERRORS["EXIT_IMPORT_SMOKE_FAILED"] == 10


def test_bagimlilik_duman_eksik_modulu_yakalar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kapının GERÇEKTEN kapandığı sabitlenir: eksik modül → sıfır olmayan çıkış.

    `runpy.run_path` sözlüğün KOPYASINI döndürür; fonksiyonun kendi globals'ı
    yamalanır (yoksa liste değişimi fonksiyona ulaşmaz ve test hep yeşil kalır).
    """
    fn = _GIRIS["run_import_smoke"]
    monkeypatch.setitem(fn.__globals__, "RUNTIME_MODULES", ("json", "kd_olmayan_modul"))
    assert fn() == 10


def test_bagimlilik_duman_var_olan_modulde_gecer(monkeypatch: pytest.MonkeyPatch) -> None:
    fn = _GIRIS["run_import_smoke"]
    monkeypatch.setitem(fn.__globals__, "RUNTIME_MODULES", ("json",))
    assert fn() == 0


def test_pdf_duman_uctan_uca_taban_sablon_turkce_ve_font(tmp_path: Path) -> None:
    """Sağlıklı kurulumda (backend kabı: WeasyPrint + DejaVu) duman kipi geçer.

    Belge `documents/base.html`'den üretilir: antet ve sayfa altlığı PDF'te
    görünmeli, fontlar gömülü DejaVu olmalı.
    """
    hedef = tmp_path / "duman.pdf"
    assert _GIRIS["run_pdf_smoke"](hedef) == 0
    metin = _GIRIS["_pdf_text"](hedef)
    assert "ÖRNEK İLÇE KAYMAKAMLIĞI" in metin  # antet bloğu taban şablondan
    assert "Sayfa 1 / 1" in metin  # `@page` altlığı taban şablondan
    assert all("DejaVu" in ad for ad in _GIRIS["_pdf_fonts"](hedef))


def test_pdf_duman_sablon_yoksa_kapanir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kapının GERÇEKTEN kapandığı: şablon ağacı pakette yoksa 8 döner, PDF üretilmez.

    spec'teki `backend/templates` Tree yolu bozulursa program açılır ama ilk
    evrak basımında düşerdi; duman kipi bunu derleme sırasında yakalamalı.
    """
    fn = _GIRIS["run_pdf_smoke"]
    monkeypatch.setitem(fn.__globals__, "_templates_dir", lambda: tmp_path / "yok")
    hedef = tmp_path / "duman.pdf"
    assert fn(hedef) == 8
    assert not hedef.exists()


def test_runtime_modules_requirements_ile_senkron() -> None:
    """hiddenimports zincirinin son halkası: her bağımlılık pakette RUNTIME'da da sınanır.

    `test_her_backend_bagimliligi_spec_kapsaminda` yalnız spec metnine bakar —
    statiktir, modülün pakete gerçekten girdiğini kanıtlamaz. `--bagimlilik-duman`
    kipi bunu paketlenmiş ikilide import ederek kanıtlar; bu test de listenin
    requirements.txt ile birlikte büyümesini zorunlu kılar (KS'de `xlrd`
    eklendiğinde onu paket içinde sınayan hiçbir kapı yoktu).
    """
    beklenen = {DAGITIM_IMPORT_ESLEME[d] for d in _gereksinimler()}
    mevcut = set(_GIRIS["RUNTIME_MODULES"])
    assert mevcut == beklenen, (
        "giris.py RUNTIME_MODULES ile requirements.txt ayrıştı — "
        f"eksik: {sorted(beklenen - mevcut)}, fazla: {sorted(mevcut - beklenen)}"
    )


def test_bagimlilik_duman_gercek_listeyle_gelistirme_kabinda_gecer() -> None:
    """Gerçek `RUNTIME_MODULES` (segno dahil) bayrak yoluyla import edilir → 0.

    Geliştirme kabı backend/requirements.txt'i kurar; burada düşen bir modül
    paketli ikilide de düşerdi. Masaüstü modülleri yalnız Windows paket
    ortamında kuruludur, bu yüzden test Windows'ta koşmaz (kapı Docker'dadır).
    """
    if sys.platform == _GIRIS["DESKTOP_PLATFORM"]:
        pytest.skip("masaüstü modülleri yalnız paket ortamında kurulu")
    assert "segno" in _GIRIS["RUNTIME_MODULES"]
    assert _GIRIS["run"](["--bagimlilik-duman"]) == 0


# ---------------------------------------------------------------------------
# Masaüstü zinciri: requirements-paketleme.txt ↔ spec ↔ DESKTOP_RUNTIME_MODULES
# ---------------------------------------------------------------------------

#: Windows işaretli paketleme dağıtımı → paketli ikilide import edilecek modül.
#: Yeni win32 satırında buraya eşleme eklenir; yoksa test bilinçli KIRILIR.
PAKETLEME_IMPORT_ESLEME = {
    "pystray": "pystray",
    "six": "six",
    # pywebview'ın WebView2 köprüsü `import clr` ile açılır (NOTLAR.md W9).
    "pythonnet": "clr",
}

#: Linux işaretli paketler masaüstü duman listesine BİLEREK girmez: hızlı
#: doğrulama derlemesi (`KD_WITH_QT=0`, packaging/linux/build.sh) Qt'yi hiç
#: kurmaz ve paketten dışlar; listeye girselerdi o derlemenin dumanı düşerdi.
#: Yeni bir Linux işaretli paket bu kümeyi bozar ve bilinçli karar ister.
LINUX_DUMAN_DISI = {"pyqt5", "pyqtwebengine"}

_PAKET_SATIRI = re.compile(
    r'^([A-Za-z0-9_.\-]+)==(\S+?)\s*(?:;\s*sys_platform\s*==\s*"([^"]+)")?\s*$'
)


def _paketleme_gereksinimleri() -> dict[str, set[str]]:
    """requirements-paketleme.txt → {platform işareti ("" = işaretsiz): {dağıtım}}."""
    platformlar: dict[str, set[str]] = {}
    for satir in PAKETLEME_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        eslesme = _PAKET_SATIRI.match(satir)
        assert eslesme is not None, (
            f"requirements-paketleme.txt satırı anlaşılamadı: {satir!r}. Her satır "
            '`ad==sürüm` ya da `ad==sürüm ; sys_platform == "..."` olmalı.'
        )
        dagitim, _surum, platform = eslesme.groups()
        platformlar.setdefault(platform or "", set()).add(dagitim.casefold())
    return platformlar


def _spec_windows_blogu_dizeleri() -> set[str]:
    """spec'teki bütün `if WINDOWS:` bloklarında geçen dize sabitleri."""
    agac = ast.parse(SPEC.read_text(encoding="utf-8"))
    dizeler: set[str] = set()
    for dugum in ast.walk(agac):
        if not (
            isinstance(dugum, ast.If)
            and isinstance(dugum.test, ast.Name)
            and dugum.test.id == "WINDOWS"
        ):
            continue
        for ifade in dugum.body:
            for alt in ast.walk(ifade):
                if isinstance(alt, ast.Constant) and isinstance(alt.value, str):
                    dizeler.add(alt.value)
    return dizeler


def test_masaustu_modulleri_win32_isaretli_paketlerle_senkron() -> None:
    """UY-6: `DESKTOP_RUNTIME_MODULES` = win32 işaretli paketlerin modülleri."""
    win32 = _paketleme_gereksinimleri().get(_GIRIS["DESKTOP_PLATFORM"], set())
    assert {"pystray", "six"} <= win32, "tepsi zinciri requirements-paketleme.txt'te yok"
    esleme_eksik = sorted(win32 - PAKETLEME_IMPORT_ESLEME.keys())
    assert esleme_eksik == [], (
        f"requirements-paketleme.txt'e yeni win32 paketi girmiş: {esleme_eksik}. "
        "Önce PAKETLEME_IMPORT_ESLEME'ye, sonra spec `if WINDOWS:` bloğuna ve "
        "giris.py DESKTOP_RUNTIME_MODULES'a ekleyin (masaüstü zinciri)."
    )
    beklenen = {PAKETLEME_IMPORT_ESLEME[d] for d in win32}
    mevcut = set(_GIRIS["DESKTOP_RUNTIME_MODULES"])
    assert mevcut == beklenen, (
        "giris.py DESKTOP_RUNTIME_MODULES ile requirements-paketleme.txt (win32) ayrıştı — "
        f"eksik: {sorted(beklenen - mevcut)}, fazla: {sorted(mevcut - beklenen)}"
    )


def test_paketleme_platform_isaretleri_bilinen_kumede() -> None:
    """Yalnız win32 ve linux işareti; linux işaretliler bilinen Qt kümesi."""
    platformlar = _paketleme_gereksinimleri()
    assert set(platformlar) <= {"", "win32", "linux"}, sorted(platformlar)
    assert platformlar.get("linux", set()) == LINUX_DUMAN_DISI
    # Masaüstü modülleri backend listesine sızmaz (iki zincir ayrı kalır).
    assert not set(_GIRIS["DESKTOP_RUNTIME_MODULES"]) & set(_GIRIS["RUNTIME_MODULES"])


def test_masaustu_modulleri_spec_windows_blogunda_toplanir() -> None:
    """Her masaüstü modülü spec'in `if WINDOWS:` bloğunda; pystray'in gizli yükleri de.

    pystray arka ucunu import anında dinamik seçer ve `six.moves` çalışma
    anında üretilen sanal modüldür; ikisi de statik çözümleyiciden kaçar
    (okulzili `okul-zili.spec` emsali).
    """
    dizeler = _spec_windows_blogu_dizeleri()
    eksik = sorted(set(_GIRIS["DESKTOP_RUNTIME_MODULES"]) - dizeler)
    assert eksik == [], f"spec `if WINDOWS:` bloğu şu masaüstü modüllerini toplamıyor: {eksik}"
    spec_metni = SPEC.read_text(encoding="utf-8")
    assert 'collect_submodules("pystray")' in spec_metni
    assert {"six.moves", "PIL.ImageDraw", "PIL.IcoImagePlugin"} <= dizeler


def test_duman_modul_listesi_platforma_gore() -> None:
    smoke_modules = _GIRIS["smoke_modules"]
    runtime, masaustu = _GIRIS["RUNTIME_MODULES"], _GIRIS["DESKTOP_RUNTIME_MODULES"]
    assert smoke_modules("win32") == runtime + masaustu
    assert smoke_modules("linux") == runtime


def test_bagimlilik_duman_masaustu_modullerini_yalniz_windowsta_acar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kapının Windows'ta GERÇEKTEN kapandığı: eksik masaüstü modülü → 10."""
    fn = _GIRIS["run_import_smoke"]
    monkeypatch.setitem(fn.__globals__, "RUNTIME_MODULES", ("json",))
    monkeypatch.setitem(fn.__globals__, "DESKTOP_RUNTIME_MODULES", ("kd_olmayan_tepsi_modulu",))
    assert fn(platform="win32") == 10
    assert fn(platform="linux") == 0


def test_pdf_duman_hedef_dosya_ayristirmasi() -> None:
    smoke_target = _GIRIS["_smoke_target"]
    assert smoke_target(["--pdf-duman", "cikti.pdf"]) == Path("cikti.pdf")
    # Dosya verilmezse (veya sonraki öğe başka bayraksa) geçici dizine düşer.
    varsayilan = smoke_target(["--pdf-duman"])
    assert varsayilan == Path(tempfile.gettempdir()) / "kutuphane-defteri-pdf-duman.pdf"
    assert smoke_target(["--pdf-duman", "--autotest"]) == varsayilan
