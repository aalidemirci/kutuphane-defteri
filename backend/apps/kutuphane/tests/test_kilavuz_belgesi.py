"""docs/katalog-excel-sablonu.md ↔ sütun sözlüğü eşleşmesi.

Kılavuz okulun elindeki tek basılı anlatımdır; sözlükle çelişirse okul yanlış
başlıkla dosya hazırlar. Test, "## Sütunlar" bölümündeki `###` başlıklarının
sözlükle SIRASI ve ZORUNLULUĞUYLA birebir aynı olduğunu, sabit kuralların (50
nüsha, sayfa adları) belgede geçtiğini ve iç kod taşımadığını denetler.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane.import_schema import (
    CATALOG_SHEET,
    COLUMNS,
    COLUMNS_SHEET,
    EXAMPLE_SHEET,
    MAX_COPIES_PER_ROW,
    RESOURCE_TYPE_CHOICES,
)

_BELGE = Path("docs") / "katalog-excel-sablonu.md"
_IC_KOD = re.compile(r"\b[UTAFSDE]\d{1,2}\b|\b(?:GA|KM|UY|SU|EK|AT|V2)-\d")
_ZORUNLU = " (zorunlu)"


def _belge_metni() -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        yol = kok / _BELGE
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{_BELGE} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _sutun_basliklari(metin: str) -> list[str]:
    bolum = re.search(r"^## Sütunlar\n(.*?)(?=^## )", metin, flags=re.MULTILINE | re.DOTALL)
    assert bolum is not None, "belgede '## Sütunlar' bölümü yok"
    return re.findall(r"^### (.+?)\s*$", bolum.group(1), flags=re.MULTILINE)


def test_belgedeki_sutunlar_sozlukle_sirasi_ve_zorunluluguyla_ayni() -> None:
    beklenen = [kolon.header + (_ZORUNLU if kolon.required else "") for kolon in COLUMNS]
    assert _sutun_basliklari(_belge_metni()) == beklenen


def test_belge_sabit_kurallari_ve_sayfa_adlarini_soyler() -> None:
    metin = _belge_metni()
    assert f"en çok {MAX_COPIES_PER_ROW} nüsha" in metin
    for sayfa in (CATALOG_SHEET, COLUMNS_SHEET, EXAMPLE_SHEET):
        assert f"**{sayfa}**" in metin, sayfa
    for secenek in RESOURCE_TYPE_CHOICES:
        assert f"**{secenek}**" in metin, secenek
    assert "Kişisel veri yazmayın" in metin


def test_belge_ic_kod_tasimaz() -> None:
    """docs/sozluk.md §2: kullanıcıya giden metinde karar/faz/bulgu kodu geçmez."""
    for numara, satir in enumerate(_belge_metni().splitlines(), start=1):
        assert not _IC_KOD.search(satir), f"{numara}: {satir}"
