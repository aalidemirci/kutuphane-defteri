"""Windows paketinin STATİK DLL kapanışı: her PE dosyasının bağımlılığı karşılanıyor mu?

Yalnız standart kitaplık (derleme ortamında, PyInstaller'dan sonra koşar; build.ps1).

--------------------------------------------------------------------------
Neden gerekli? (29.09.2026 doğrulama turu)
--------------------------------------------------------------------------
Duman testleri (`--bagimlilik-duman`, `--pdf-duman`, `--autotest`) paketin ÇALIŞTIĞINI
gösterir, ama koşucunun PATH'i açıktaysa bir DLL'in PAKETTE olduğunu kanıtlamaz: WeasyPrint
kütüphaneyi adıyla yükleyemeyince cffi `ctypes.util.find_library`'ye düşer, PyInstaller'ın
dondurulmuş sürümü de `sys._MEIPASS` + PATH'e bakar; koşucudaki mingw64\\bin kopyası eksik
bir DLL'i gizler. Bu betik çalışma anından bağımsızdır: paketteki her `.exe`, `.dll` ve
`.pyd` dosyasının içe aktarma tablosunu (gecikmeli içe aktarma dahil) okur ve her adın

* pakette (herhangi bir dizinde, aynı adla — PyInstaller bağımlılıkları `_internal`'a
  toplar; kesin arama sırası duman testlerinde sınanır) ya da
* Windows 10/11'in bileşeni — API kümesi (`api-ms-win-*`, `ext-ms-win-*`) ya da
  `WINDOWS_SISTEM_DLL`

olduğunu doğrular. Universal CRT (`ucrtbase.dll`, `api-ms-win-crt-*`) pakette YOKTUR ve
Windows 10/11'in bileşenidir (Microsoft Learn, "Universal CRT deployment";
`packaging/lisanslar/lisanslar.py::UCRT_DLL`): bu betik o kararı dosya düzeyinde kilitler.
Visual C++ çalışma zamanı (`vcruntime140*.dll`, `msvcp140*.dll`) işletim sisteminin parçası
DEĞİLDİR; pakette bulunmalıdır.

`WINDOWS_SISTEM_DLL` gözleme dayanır: yerel CPython 3.12, paketin Windows tekerlekleri
(cffi, cryptography, Pillow, fontTools, argon2, brotli, zopfli, pythonnet, clr_loader,
pywebview, PyInstaller önyükleyicisi) ve DLL kapanışının 30 MSYS2 DLL'i — 89 PE dosyası —
okunarak çıkarıldı; yanına yaygın Windows 10 sistem DLL'lerinden küçük bir pay eklendi.
Listede olmayan bir ad derlemeyi DURDURUR: DLL kapanışı eksiktir ya da ad, Windows 10'un her
sürümünde System32'de bulunduğu doğrulanarak gerekçesiyle eklenir.

Kullanım:
    python packaging/windows/paket_kapanisi.py <paket dizini>
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PE_UZANTILARI = frozenset({".exe", ".dll", ".pyd"})

#: Windows 10/11'in System32'sinde bulunan ve paketteki ikililerin içe aktardığı DLL'ler
#: (küçük harf). Gözlenenler (29.09.2026, 89 PE dosyası) + yaygın pay. `ucrtbase.dll`
#: Windows 10 ve sonrasında işletim sisteminin bileşenidir (Universal CRT); paket onu taşımaz.
WINDOWS_SISTEM_DLL = frozenset(
    {
        # --- gözlenen
        "advapi32.dll",
        "bcrypt.dll",
        "bcryptprimitives.dll",
        "comctl32.dll",
        "crypt32.dll",
        "dnsapi.dll",
        "dwrite.dll",
        "gdi32.dll",
        "iphlpapi.dll",
        "kernel32.dll",
        "mscoree.dll",
        "msvcrt.dll",
        "ntdll.dll",
        "ole32.dll",
        "oleaut32.dll",
        "propsys.dll",
        "psapi.dll",
        "rpcrt4.dll",
        "shell32.dll",
        "shlwapi.dll",
        "user32.dll",
        "usp10.dll",
        "version.dll",
        "winmm.dll",
        "ws2_32.dll",
        # --- Universal CRT (Windows 10+ bileşeni; paket taşımaz)
        "ucrtbase.dll",
        # --- pay: Windows 10'un her masaüstü sürümünde bulunan çekirdek DLL'ler
        "cfgmgr32.dll",
        "comdlg32.dll",
        "dwmapi.dll",
        "imm32.dll",
        "mswsock.dll",
        "ncrypt.dll",
        "netapi32.dll",
        "normaliz.dll",
        "powrprof.dll",
        "secur32.dll",
        "setupapi.dll",
        "shcore.dll",
        "sspicli.dll",
        "userenv.dll",
        "uxtheme.dll",
        "winhttp.dll",
        "wininet.dll",
        "wintrust.dll",
        "wtsapi32.dll",
    }
)

#: API kümesi adları: yükleyici bunları dosya olarak değil, işletim sisteminin API kümesi
#: şemasıyla çözer (Windows 10+).
API_KUMESI_ONEKLERI = ("api-ms-win-", "ext-ms-win-")

_EN_COK_TANIMLAYICI = 4096


def _bolumler(veri: bytes, opt: int, opt_boy: int, sayi: int) -> list[tuple[int, int, int, int]]:
    bolumler: list[tuple[int, int, int, int]] = []
    for i in range(sayi):
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", veri, opt + opt_boy + i * 40 + 8)
        bolumler.append((va, vsize, raw_ptr, raw_size))
    return bolumler


def _ofset(bolumler: list[tuple[int, int, int, int]], rva: int) -> int:
    for va, vsize, raw_ptr, raw_size in bolumler:
        if va <= rva < va + max(vsize, raw_size):
            return rva - va + raw_ptr
    raise ValueError(f"RVA bir bölüme düşmüyor: {rva:#x}")


def _cstr(veri: bytes, ofset: int) -> str:
    son = veri.index(b"\0", ofset)
    return veri[ofset:son].decode("ascii")


def pe_ithalleri(veri: bytes) -> list[str] | None:
    """PE dosyasının içe aktarma ve gecikmeli içe aktarma tablolarındaki DLL adları.

    PE değilse None; tablo bozuksa `ValueError`. .NET derlemeleri yalnız `mscoree.dll`'i
    içe aktarır; önyükleyici ve statik bağlı ikililer yalnız sistem DLL'lerini.
    """
    if veri[:2] != b"MZ" or len(veri) < 0x40:
        return None
    pe = struct.unpack_from("<I", veri, 0x3C)[0]
    if veri[pe : pe + 4] != b"PE\0\0":
        return None
    try:
        bolum_sayisi = struct.unpack_from("<H", veri, pe + 6)[0]
        opt_boy = struct.unpack_from("<H", veri, pe + 20)[0]
        opt = pe + 24
        sihir = struct.unpack_from("<H", veri, opt)[0]
        if sihir == 0x20B:  # PE32+
            goruntu_tabani = struct.unpack_from("<Q", veri, opt + 24)[0]
            dd = opt + 112
        elif sihir == 0x10B:  # PE32
            goruntu_tabani = struct.unpack_from("<I", veri, opt + 28)[0]
            dd = opt + 96
        else:
            raise ValueError(f"bilinmeyen isteğe bağlı başlık: {sihir:#x}")
        dd_sayisi = struct.unpack_from("<I", veri, dd - 4)[0]
        bolumler = _bolumler(veri, opt, opt_boy, bolum_sayisi)

        def dizin(sira: int) -> int:
            return struct.unpack_from("<I", veri, dd + sira * 8)[0] if sira < dd_sayisi else 0

        adlar: list[str] = []
        ithal = dizin(1)
        if ithal:
            of = _ofset(bolumler, ithal)
            for _ in range(_EN_COK_TANIMLAYICI):
                ad_rva = struct.unpack_from("<I", veri, of + 12)[0]
                if ad_rva == 0:
                    break
                adlar.append(_cstr(veri, _ofset(bolumler, ad_rva)))
                of += 20
        gecikmeli = dizin(13)
        if gecikmeli:
            of = _ofset(bolumler, gecikmeli)
            for _ in range(_EN_COK_TANIMLAYICI):
                oznitelik, ad_rva = struct.unpack_from("<II", veri, of)
                if ad_rva == 0:
                    break
                if not oznitelik & 1:  # eski biçim: RVA yerine sanal adres
                    ad_rva -= goruntu_tabani
                adlar.append(_cstr(veri, _ofset(bolumler, ad_rva)))
                of += 32
    except (struct.error, IndexError, UnicodeDecodeError) as hata:
        raise ValueError(str(hata)) from hata
    return adlar


def sistem_dll_mi(ad: str) -> bool:
    """Windows 10/11'in bileşeni mi (API kümesi ya da `WINDOWS_SISTEM_DLL`)?"""
    kucuk = ad.lower()
    return kucuk.startswith(API_KUMESI_ONEKLERI) or kucuk in WINDOWS_SISTEM_DLL


def kapanis_denetimi(paket_dizini: Path) -> list[str]:
    """Paketteki her PE dosyasının içe aktardığı her DLL pakette ya da Windows 10/11'de mi?"""
    pe_dosyalari = sorted(
        p for p in paket_dizini.rglob("*") if p.is_file() and p.suffix.lower() in PE_UZANTILARI
    )
    if not pe_dosyalari:
        return [f"pakette PE dosyası yok: {paket_dizini}"]
    paketteki = {p.name.lower() for p in pe_dosyalari}
    eksik: dict[str, list[str]] = {}
    hatalar: list[str] = []
    for dosya in pe_dosyalari:
        goreli = dosya.relative_to(paket_dizini).as_posix()
        try:
            adlar = pe_ithalleri(dosya.read_bytes())
        except ValueError as hata:
            hatalar.append(f"PE içe aktarma tablosu okunamadı: {goreli} ({hata})")
            continue
        if adlar is None:
            hatalar.append(f"PE dosyası değil: {goreli}")
            continue
        for ad in adlar:
            if ad.lower() in paketteki or sistem_dll_mi(ad):
                continue
            eksik.setdefault(ad.lower(), []).append(goreli)
    for ad, kullananlar in sorted(eksik.items()):
        hatalar.append(
            f"{ad}: ne pakette ne Windows 10/11'in bileşeni ({len(kullananlar)} dosya içe "
            f"aktarıyor, ör. {kullananlar[0]}) — DLL kapanışı eksik ya da ad, Windows 10'da "
            "System32'de bulunduğu doğrulanarak `WINDOWS_SISTEM_DLL`'e gerekçesiyle eklenir"
        )
    return hatalar


def yaz(metin: str) -> None:
    """Konsol kodlamasına dayanıklı yazdırma (Windows koşucusu CP1252 olabilir; "ı" yok)."""
    kodlama = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(metin.encode(kodlama, errors="backslashreplace").decode(kodlama), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows paketinin statik DLL kapanışı.")
    parser.add_argument("paket", type=Path, help="paket dizini (onedir kökü)")
    args = parser.parse_args(argv)
    if not args.paket.is_dir():
        yaz(f"HATA: paket dizini yok: {args.paket}")
        return 2
    hatalar = kapanis_denetimi(args.paket)
    if hatalar:
        yaz("HATA: paketin DLL kapanışı eksik:")
        for hata in hatalar:
            yaz(f"  - {hata}")
        return 1
    sayi = sum(
        1 for p in args.paket.rglob("*") if p.is_file() and p.suffix.lower() in PE_UZANTILARI
    )
    yaz(f"Paketin DLL kapanışı tam: {sayi} PE dosyası.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
