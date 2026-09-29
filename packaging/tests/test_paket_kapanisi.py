"""Windows paketinin STATİK DLL kapanışı (`packaging/windows/paket_kapanisi.py`).

29.09.2026 doğrulama turu: duman testleri koşucunun PATH'iyle koşuyordu (mingw64\\bin,
Python, JDK); paketten eksik bir WeasyPrint DLL'i `find_library` üzerinden oradan bulunabilir,
test yeşil kalırdı. Kapanış artık dosyalar üzerinden, çalışma anından bağımsız sınanır ve
Universal CRT kararı (pakette yok; Windows 10/11'in bileşeni) dosya düzeyinde kilitlenir.
Burada PE okuyucusu sahte PE dosyalarıyla sınanır; gerçek ikililerle (yerel CPython 3.12,
Windows tekerlekleri, 30 MSYS2 DLL'i — 88 dosya) doğrulama tasarım §14.1 "F12 ekleri — ilk
CI Windows koşusu"ndadır.
"""

from __future__ import annotations

import ast
import importlib.util
import struct
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
BETIK = REPO / "packaging" / "windows" / "paket_kapanisi.py"
BUILD_PS1 = REPO / "packaging" / "windows" / "build.ps1"


def _yukle() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kd_paket_kapanisi", BETIK)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules["kd_paket_kapanisi"] = modul
    spec.loader.exec_module(modul)
    return modul


K: Any = _yukle()


def _sahte_pe(
    ithal: list[str],
    gecikmeli: tuple[str, ...] = (),
    *,
    pe32: bool = False,
    eski_gecikmeli: bool = False,
) -> bytes:
    """Tek bölümlü (.idata) en küçük PE: içe aktarma + gecikmeli içe aktarma tabloları."""
    va, ham = 0x1000, 0x400
    goruntu_tabani = 0x400000 if pe32 else 0x140000000
    govde = bytearray(0x1000)
    gecik_of = 20 * (len(ithal) + 1)
    ad_of = gecik_of + 32 * (len(gecikmeli) + 1)

    def ad_yaz(ad: str) -> int:
        nonlocal ad_of
        rva = va + ad_of
        govde[ad_of : ad_of + len(ad) + 1] = ad.encode("ascii") + b"\0"
        ad_of += len(ad) + 1
        return rva

    for i, ad in enumerate(ithal):
        struct.pack_into("<IIIII", govde, 20 * i, 0, 0, 0, ad_yaz(ad), 0)
    for i, ad in enumerate(gecikmeli):
        rva = ad_yaz(ad)
        if eski_gecikmeli:  # Attributes=0: ad sanal adresle (görüntü tabanı dahil) verilir
            struct.pack_into("<II", govde, gecik_of + 32 * i, 0, rva + goruntu_tabani)
        else:
            struct.pack_into("<II", govde, gecik_of + 32 * i, 1, rva)
    opt_boy = 224 if pe32 else 240
    baslik = bytearray(ham)
    baslik[0:2] = b"MZ"
    struct.pack_into("<I", baslik, 0x3C, 0x40)
    baslik[0x40:0x44] = b"PE\0\0"
    makine = 0x14C if pe32 else 0x8664
    struct.pack_into("<HHIIIHH", baslik, 0x44, makine, 1, 0, 0, 0, opt_boy, 0x2022)
    opt = 0x58
    struct.pack_into("<H", baslik, opt, 0x10B if pe32 else 0x20B)
    if pe32:
        struct.pack_into("<I", baslik, opt + 28, goruntu_tabani)
        dd = opt + 96
    else:
        struct.pack_into("<Q", baslik, opt + 24, goruntu_tabani)
        dd = opt + 112
    struct.pack_into("<I", baslik, dd - 4, 16)
    if ithal:
        struct.pack_into("<II", baslik, dd + 8, va, 20 * (len(ithal) + 1))
    if gecikmeli:
        struct.pack_into("<II", baslik, dd + 13 * 8, va + gecik_of, 32 * (len(gecikmeli) + 1))
    bolum = opt + opt_boy
    baslik[bolum : bolum + 8] = b".idata\0\0"
    struct.pack_into("<IIII", baslik, bolum + 8, len(govde), va, len(govde), ham)
    return bytes(baslik + govde)


# ------------------------------------------------------------------ PE okuyucusu


def test_pe32_arti_ithal_ve_gecikmeli_ithal_okunur() -> None:
    veri = _sahte_pe(["KERNEL32.dll", "python312.dll"], ("ole32.dll",))
    assert K.pe_ithalleri(veri) == ["KERNEL32.dll", "python312.dll", "ole32.dll"]


def test_pe32_ve_eski_bicim_gecikmeli_ithal_okunur() -> None:
    """WebView2Loader'ın x86 kopyası PE32'dir; eski biçim gecikmeli tanımlayıcı sanal adres taşır."""
    veri = _sahte_pe(["KERNEL32.dll"], ("ADVAPI32.dll",), pe32=True, eski_gecikmeli=True)
    assert K.pe_ithalleri(veri) == ["KERNEL32.dll", "ADVAPI32.dll"]


def test_ithalsiz_pe_bos_liste_pe_olmayan_none_bozuk_hata() -> None:
    assert K.pe_ithalleri(_sahte_pe([])) == []
    assert K.pe_ithalleri(b"\x7fELF" + bytes(100)) is None
    assert K.pe_ithalleri(b"MZ") is None
    bozuk = bytearray(_sahte_pe(["KERNEL32.dll"]))
    struct.pack_into("<I", bozuk, 0x400 + 12, 0x7FFF0000)  # ad RVA'sı hiçbir bölüme düşmüyor
    with pytest.raises(ValueError):
        K.pe_ithalleri(bytes(bozuk))


# --------------------------------------------------------------- kapanış kuralı


def _paket(tmp_path: Path, dosyalar: dict[str, bytes]) -> Path:
    paket = tmp_path / "kutuphane-defteri"
    for goreli, veri in dosyalar.items():
        (paket / goreli).parent.mkdir(parents=True, exist_ok=True)
        (paket / goreli).write_bytes(veri)
    return paket


def test_pakette_ya_da_windowsta_olan_bagimlilik_gecer(tmp_path: Path) -> None:
    paket = _paket(
        tmp_path,
        {
            "kutuphane-defteri.exe": _sahte_pe(["KERNEL32.dll", "USER32.dll", "COMCTL32.dll"]),
            "_internal/python312.dll": _sahte_pe(
                ["VCRUNTIME140.dll", "api-ms-win-crt-runtime-l1-1-0.dll", "KERNEL32.dll"]
            ),
            "_internal/VCRUNTIME140.dll": _sahte_pe(["api-ms-win-crt-heap-l1-1-0.dll"]),
            "_internal/libpango-1.0-0.dll": _sahte_pe(["libglib-2.0-0.dll", "msvcrt.dll"]),
            "_internal/libglib-2.0-0.dll": _sahte_pe(["ws2_32.dll", "ext-ms-win-x-l1-1-0.dll"]),
            # Paket içinde başka bir dizindeki DLL de karşılar (PyInstaller _internal'a toplar).
            "_internal/cryptography/hazmat/bindings/_rust.pyd": _sahte_pe(
                ["python3.dll", "bcryptprimitives.dll"]
            ),
            "_internal/python3.dll": _sahte_pe(["python312.dll"]),
            # .NET derlemesi yalnız mscoree.dll'i içe aktarır.
            "_internal/pythonnet/runtime/Python.Runtime.dll": _sahte_pe(["mscoree.dll"]),
        },
    )
    assert K.kapanis_denetimi(paket) == []
    assert K.main([str(paket)]) == 0


def test_eksik_dll_ve_visual_cpp_calisma_zamani_derlemeyi_durdurur(tmp_path: Path) -> None:
    """Pakette olmayan MSYS2 DLL'i ve Visual C++ çalışma zamanı (işletim sisteminin parçası
    DEĞİL) yakalanır; aynı ad birden çok dosyada tek hatadır."""
    paket = _paket(
        tmp_path,
        {
            "_internal/libfontconfig-1.dll": _sahte_pe(["libintl-8.dll", "KERNEL32.dll"]),
            "_internal/libglib-2.0-0.dll": _sahte_pe(["libintl-8.dll"]),
            "_internal/_wmi.pyd": _sahte_pe(["VCRUNTIME140_1.dll"]),
        },
    )
    hatalar = K.kapanis_denetimi(paket)
    assert [h.split(":", 1)[0] for h in hatalar] == ["libintl-8.dll", "vcruntime140_1.dll"]
    assert "(2 dosya içe aktarıyor" in hatalar[0]
    assert K.main([str(paket)]) == 1


def test_okunamayan_pe_ve_bos_paket_hatadir(tmp_path: Path) -> None:
    paket = _paket(tmp_path, {"_internal/sahte.pyd": b"PK\x03\x04 zip degil"})
    hatalar = K.kapanis_denetimi(paket)
    assert hatalar == ["PE dosyası değil: _internal/sahte.pyd"]
    bos = tmp_path / "bos"
    bos.mkdir()
    assert K.kapanis_denetimi(bos)[0].startswith("pakette PE dosyası yok")
    assert K.main([str(tmp_path / "yok")]) == 2


def test_universal_crt_windowsun_visual_cpp_paketin() -> None:
    """UCRT (`ucrtbase.dll`, `api-ms-win-*`) Windows 10/11'in bileşenidir ve pakette yoktur
    (`lisanslar.UCRT_DLL`); Visual C++ çalışma zamanı ve Python'un kendisi işletim sisteminin
    parçası değildir, pakette bulunmalıdır."""
    for ad in ("ucrtbase.dll", "UCRTBASE.DLL", "api-ms-win-crt-stdio-l1-1-0.dll", "KERNEL32.dll"):
        assert K.sistem_dll_mi(ad), ad
    for ad in (
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "python312.dll",
        "python3.dll",
        "libffi-8.dll",
        "zlib1.dll",
        "tcl86t.dll",
    ):
        assert not K.sistem_dll_mi(ad), ad
    assert all(ad == ad.lower() and ad.endswith(".dll") for ad in K.WINDOWS_SISTEM_DLL)


# ------------------------------------------------------------------ build.ps1


def test_build_ps1_kapanisi_pyinstallerdan_sonra_duman_testlerinden_once_sinar() -> None:
    ps1 = BUILD_PS1.read_text(encoding="utf-8-sig")
    cagri = '& $PythonExe (Join-Path $Repo "packaging\\windows\\paket_kapanisi.py") $AppDir'
    assert cagri in ps1
    assert 'throw "Paketin DLL kapanışı eksik."' in ps1
    assert (
        ps1.index("-m PyInstaller")
        < ps1.index(cagri)
        < ps1.index('Invoke-Uygulama $AppExe @("--bagimlilik-duman")')
    )


def test_duman_testleri_windowsun_sistem_pathiyle_kosar() -> None:
    """Koşucunun PATH'i (mingw64\\bin, Python, JDK) paketten eksik bir DLL'i gizlemesin:
    `Invoke-Uygulama` her çağrıda PATH'i Windows'un varsayılan sistem PATH'ine çevirir ve
    sonra geri yükler."""
    ps1 = BUILD_PS1.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    bas = ps1.index("function Get-SistemPath")
    sistem = ps1[bas : ps1.index("\n}\n", bas)]
    assert '(Join-Path $env:SystemRoot "System32")' in sistem
    for yabanci in ("Mingw", "Venv", "Python", "PATH"):
        assert yabanci not in sistem, yabanci
    uygulama = ps1[ps1.index("function Invoke-Uygulama") : ps1.index("# --- 1. Ön koşullar")]
    assert '$tumOrtam = @{ "PATH" = (Get-SistemPath) }' in uygulama
    assert "[Environment]::SetEnvironmentVariable($anahtar, $eski[$anahtar])" in uygulama
    assert "} finally {" in uygulama
    # Her duman testi bu yardımcıdan geçer (pencereli exe doğrudan çağrılmaz).
    assert ps1.count("Invoke-Uygulama $AppExe") == 3
    assert "& $AppExe" not in ps1


def test_betik_yalniz_standart_kitaplik_ister() -> None:
    """Derleme ortamında (sanal ortam) koşar: modül düzeyinde üçüncü taraf import YOK."""
    agac = ast.parse(BETIK.read_text("utf-8"))
    ust_duzey: set[str] = set()
    for dugum in agac.body:
        if isinstance(dugum, ast.Import):
            ust_duzey |= {a.name.split(".")[0] for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module and dugum.level == 0:
            ust_duzey.add(dugum.module.split(".")[0])
    assert ust_duzey - {"__future__"} <= set(sys.stdlib_module_names), ust_duzey
