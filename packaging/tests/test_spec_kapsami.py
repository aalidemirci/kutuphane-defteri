"""hiddenimports zincirinin otomatik kapısı: spec ↔ backend/requirements.txt.

Backend pakete KAYNAK olarak kopyalanır; PyInstaller statik çözümleyicisi orayı
taramaz (spec docstring'i). Yeni bir üçüncü taraf bağımlılık spec'e elle
eklenmek ZORUNDADIR — unutulursa paket geliştirmede çalışır, sahada çöker
(hiddenimports tuzağı). Bu test unutmayı kapıya bağlar (KS'den devralındı).

Ayrıca `giris.py` teşhis kipinin sözleşmesi sabitlenir: bayrak adı, çıkış kodu
(desktop/errors.py ile ikiz) ve hedef dosya ayrıştırması — üç paket betiği
(build.ps1, build.sh, kap-ici-test.sh) bu sözleşmeye dışarıdan bağlıdır.
"""

from __future__ import annotations

import re
import runpy
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "packaging" / "pyinstaller" / "kutuphane_defteri.spec"
REQUIREMENTS = REPO / "backend" / "requirements.txt"

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


def test_pdf_duman_hedef_dosya_ayristirmasi() -> None:
    smoke_target = _GIRIS["_smoke_target"]
    assert smoke_target(["--pdf-duman", "cikti.pdf"]) == Path("cikti.pdf")
    # Dosya verilmezse (veya sonraki öğe başka bayraksa) geçici dizine düşer.
    varsayilan = smoke_target(["--pdf-duman"])
    assert varsayilan == Path(tempfile.gettempdir()) / "kutuphane-defteri-pdf-duman.pdf"
    assert smoke_target(["--pdf-duman", "--autotest"]) == varsayilan
