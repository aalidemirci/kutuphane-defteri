"""Windows PowerShell'den YAPILANDIRILMIŞ veri okuma (tasarım §5.7, GA-5).

`netsh` çıktısı Windows'un diline göre yerelleştirilir ("Kural Adı:" /
"Rule Name:") ve sürümden sürüme biçim değiştirir; ayrıştırılamaz. Güvenlik
duvarı denetimi ve ağ arayüzü listesi bu yüzden PowerShell cmdlet'lerinin
nesne çıktısını `ConvertTo-Json` ile alır: alan adları dile bağlı değildir.

Kurallar:

* Betik `-EncodedCommand` ile (UTF-16LE + base64) verilir: program yolu gibi
  Türkçe karakterli değerler ("Kütüphane Defteri") komut satırı tırnaklamasına
  ve kod sayfasına takılmaz. Değerler betiğe ayrıca `ps_dizesi` ile tek
  tırnaklı PowerShell dizesi olarak gömülür (enjeksiyon yok).
* Çıktı UTF-8'e zorlanır ve tek bir JSON değeri beklenir.
* PowerShell yolu `%SystemRoot%` altından mutlak verilir (PATH'teki başka bir
  `powershell.exe` çalıştırılmaz); pencere açılmaz (`CREATE_NO_WINDOW`).
* Hata istisna değil sonuçtur: çağıranlar `PowerShellHatasi`'nı yakalayıp
  "bilinmiyor" (fail-closed) durumuna düşer.

Bu modül yalnız OKUR; güvenlik duvarı kuralını yazan yol yönetici yetkisiyle
çalışan ayrı yardımcıdadır (`desktop/guvenlik_duvari.py::kural_yaz`).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

#: Pencere açmadan süreç başlatma (Windows `CREATE_NO_WINDOW`).
_CREATE_NO_WINDOW: Final = 0x08000000
VARSAYILAN_ZAMAN_ASIMI: Final = 30.0

_ONSOZ: Final = (
    "$ErrorActionPreference = 'Stop'\n"
    "$ProgressPreference = 'SilentlyContinue'\n"
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
)

#: Test ve teşhis için enjekte edilebilen çalıştırıcı: (argv, zaman aşımı) → (çıkış kodu, stdout).
Calistirici = Callable[[Sequence[str], float], tuple[int, bytes]]


class PowerShellHatasi(RuntimeError):
    """PowerShell çalışmadı ya da beklenen JSON'u üretmedi (ayrıntı günlük içindir)."""


def powershell_yolu(environ: dict[str, str] | None = None) -> str:
    """Sistem PowerShell'inin mutlak yolu (PATH'e güvenilmez)."""
    env = os.environ if environ is None else environ
    kok = env.get("SystemRoot") or env.get("SYSTEMROOT") or r"C:\Windows"
    return str(Path(kok) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


#: PowerShell'in TEK TIRNAK saydığı karakterler: ASCII `'` ve U+2018, U+2019,
#: U+201A, U+201B. Yalnız ASCII ikilenirse "Okul’un" gibi bir yol dizeyi kapatır ve
#: kalanı komut olarak çalışır (yükseltilmiş `kural_yaz` betiği dahil).
_TEK_TIRNAKLAR: Final = ("'", "‘", "’", "‚", "‛")


def ps_dizesi(deger: str) -> str:
    """Değeri tek tırnaklı PowerShell dizesine çevirir.

    Beş tek tırnak karakterinin her biri kendisiyle ikilenir; kural
    `[System.Management.Automation.Language.CodeGeneration]::EscapeSingleQuotedStringContent`
    ile aynıdır (Windows PowerShell 5.1'de denendi: değer harfi harfine döner).
    """
    kacisli = "".join(c + c if c in _TEK_TIRNAKLAR else c for c in deger)
    return "'" + kacisli + "'"


def kodla(betik: str) -> str:
    """`-EncodedCommand` biçimi: UTF-16LE baytların base64'ü."""
    return base64.b64encode((_ONSOZ + betik).encode("utf-16-le")).decode("ascii")


def _gercek_calistirici(argv: Sequence[str], zaman_asimi: float) -> tuple[int, bytes]:
    bayraklar = _CREATE_NO_WINDOW if os.name == "nt" else 0
    sonuc = subprocess.run(  # noqa: S603 — mutlak yol, kabuk yok, betik base64
        list(argv),
        capture_output=True,
        timeout=zaman_asimi,
        check=False,
        creationflags=bayraklar,
    )
    return sonuc.returncode, sonuc.stdout


def json_calistir(
    betik: str,
    *,
    calistirici: Calistirici | None = None,
    zaman_asimi: float = VARSAYILAN_ZAMAN_ASIMI,
) -> Any:
    """Betiği çalıştırır ve standart çıktısındaki JSON değerini döndürür."""
    argv = [
        powershell_yolu(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        kodla(betik),
    ]
    try:
        kod, cikti = (calistirici or _gercek_calistirici)(argv, zaman_asimi)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PowerShellHatasi("PowerShell çalıştırılamadı.") from exc
    if kod != 0:
        raise PowerShellHatasi(f"PowerShell {kod} koduyla bitti.")
    metin = cikti.decode("utf-8-sig", errors="replace").strip()
    if not metin:
        raise PowerShellHatasi("PowerShell çıktı üretmedi.")
    try:
        return json.loads(metin)
    except ValueError as exc:
        raise PowerShellHatasi("PowerShell çıktısı JSON değil.") from exc


def liste(deger: Any) -> list[Any]:
    """`ConvertTo-Json` tuhaflığı: tek öğeli dizi nesneye, boş dizi `null`a dönebilir."""
    if deger is None:
        return []
    if isinstance(deger, list):
        return deger
    return [deger]
