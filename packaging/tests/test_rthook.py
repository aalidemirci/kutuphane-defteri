"""PyInstaller çalışma zamanı kancası: yükseltilmiş yardımcı kipte diske yazılmaz.

Ağ Doktoru'nun "Kuralı ekle/güncelle" düğmesi programı `--guvenlik-duvari-kurali`
ile UAC üzerinden yeniden başlatır; süreç BTR'nin hesabında koşabilir. Kanca
giriş betiğinden ÖNCE her çağrıda çalıştığı için `desktop.main.run`'un
"veri dizini ve günlük açmaz" testi onu kapsamaz; bu dosya kapsar.

Kanca içe aktarılınca `setup()` modül düzeyinde koşar: ortam değişkenlerine
dokunduğu için `os.environ` testte kopyayla değiştirilir.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from desktop import guvenlik_duvari

KANCA = Path(__file__).resolve().parents[1] / "pyinstaller" / "rthook_kd.py"


def _kanca(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(os, "environ", dict(os.environ))
    tanim = importlib.util.spec_from_file_location("rthook_kd_sinama", KANCA)
    assert tanim is not None and tanim.loader is not None
    modul = importlib.util.module_from_spec(tanim)
    tanim.loader.exec_module(modul)
    return modul


def test_uac_bayragi_programla_ayni(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _kanca(monkeypatch).UAC_BAYRAGI == guvenlik_duvari.UAC_BAYRAGI


@pytest.mark.parametrize(
    ("argv", "yazar"),
    [
        (["kutuphane-defteri.exe"], True),
        (["kutuphane-defteri.exe", "--tepside"], True),
        (["kutuphane-defteri.exe", guvenlik_duvari.UAC_BAYRAGI, "--port", "9100"], False),
    ],
)
def test_yukseltilmis_yardimci_kipte_font_onbellegi_yazilmaz(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str], yazar: bool
) -> None:
    """F5 düzeltmesi: kanca BTR'nin profiline `%LOCALAPPDATA%\\KutuphaneDefteri` açardı."""
    kanca = _kanca(monkeypatch)
    cagrilar: list[Any] = []
    monkeypatch.setattr(kanca.sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(kanca, "_bundle_root", lambda: tmp_path)
    monkeypatch.setattr(kanca, "setup_fontconfig", lambda *a: cagrilar.append(a))
    monkeypatch.setattr(kanca, "_cache_root", lambda: tmp_path / "onbellek")

    kanca.setup()

    assert bool(cagrilar) is yazar
    assert not (tmp_path / "onbellek").exists()
