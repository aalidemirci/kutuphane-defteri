"""Ağ Kataloğu masaüstü modüllerinin kullanıcıya giden metinleri sözlüğe uyar (docs/sozluk.md).

Bu modüllerin iletileri Ağ Doktoru'na, Ayarlar → Ağ Kataloğu'na, tepsiye ve
imzalanacak Ağ Hizmeti Bilgi Notu'na çıkar (güvenlik duvarı madde açıklamaları,
"Son hata", uyarılar). Tarama dize sabitleri üzerindedir; belge metinleri
(docstring) ve günlük çağrıları (`logger.*`) kapsam dışıdır.

Sözlük:
* Ağ Kataloğu bağlamında "sunucu" kullanılmaz;
* BTR için "BT sorumlusu" / "bilişim sorumlusu" kullanılmaz;
* düğmenin adı birebir "Kuralı ekle/güncelle"dir (tek başına "Kuralı ekle" ya da
  "Kuralı güncelle" ekranda olmayan bir düğmeyi gösterir).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

DESKTOP = Path(__file__).resolve().parents[1]
MODULLER = ("katalog_server.py", "katalog_kontrol.py", "guvenlik_duvari.py", "ag.py", "gunluk.py")

YASAK = (
    re.compile(r"\bsunucu", re.IGNORECASE),
    re.compile(r"bilişim sorumlusu", re.IGNORECASE),
    re.compile(r"\bBT sorumlusu", re.IGNORECASE),
    # "\b": "Kuralı güncelleyin" gibi fiil çekimleri düğme adı değildir.
    re.compile(r"Kuralı ekle\b(?!/güncelle)"),
    re.compile(r"(?<!ekle/)Kuralı güncelle\b"),
)


def _kullanici_dizeleri(dosya: Path) -> list[tuple[int, str]]:
    agac = ast.parse(dosya.read_text(encoding="utf-8"))
    haric: set[int] = set()
    for dugum in ast.walk(agac):
        if (
            isinstance(dugum, ast.Module | ast.ClassDef | ast.FunctionDef)
            and dugum.body
            and isinstance(dugum.body[0], ast.Expr)
            and isinstance(dugum.body[0].value, ast.Constant)
        ):
            haric.add(id(dugum.body[0].value))
        if (
            isinstance(dugum, ast.Call)
            and isinstance(dugum.func, ast.Attribute)
            and isinstance(dugum.func.value, ast.Name)
            and dugum.func.value.id == "logger"
        ):
            haric.update(id(alt) for alt in ast.walk(dugum))
    return [
        (dugum.lineno, dugum.value)
        for dugum in ast.walk(agac)
        if isinstance(dugum, ast.Constant)
        and isinstance(dugum.value, str)
        and id(dugum) not in haric
    ]


@pytest.mark.parametrize("modul", MODULLER)
def test_kullanici_metinleri_sozluge_uyar(modul: str) -> None:
    for satir, dize in _kullanici_dizeleri(DESKTOP / modul):
        for kalip in YASAK:
            assert not kalip.search(dize), f"{modul}:{satir}: {dize!r}"


def test_tarama_gercek_iletileri_gorur() -> None:
    """Tarama boş dönmesin: bilinen iletiler kümede olmalı."""
    dizeler = " ".join(d for _, d in _kullanici_dizeleri(DESKTOP / "katalog_server.py"))

    assert "Ağ Kataloğu açılamadı: dinleyici kurulamadı." in dizeler
