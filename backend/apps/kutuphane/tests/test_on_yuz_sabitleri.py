"""Ön yüzde ELLE KOPYALANMIŞ backend sabitleri — iki kopyayı eşitleyen kapı.

CLAUDE.md §3 aynı sınıfı `version_key` için kayda geçiriyor: "iki kopyadır ve
aynı kalmalıdır". Sabit ayrışırsa iki katman aynı kural için farklı davranır —
sınır düşerse kullanıcı formun kabul ettiği bir sayıyla sunucudan ret alır,
yükselirse ön yüz geçerli bir sayıyı kendi engeller — ve iki katman farklı
ileti verir.

Test ön yüz kaynağını METİN olarak okur: Node çalıştırmadan (host'ta Node
yoktur) iki sayının eşitliğini sabitlemenin en ucuz yolu budur. Sabit taşınırsa
ya da adı değişirse test "bulunamadı" diyerek düşer, sessizce yeşil kalmaz.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from apps.kutuphane.import_schema import MAX_COPIES_PER_ROW
from apps.kutuphane.serializers import CopyBulkCreateSerializer

_KAYNAK = Path("frontend") / "src" / "modules" / "kutuphane" / "EserDetayPage.tsx"
_SABIT = re.compile(r"^const EN_COK_NUSHA = (\d+);$", flags=re.MULTILINE)


def _on_yuz_kaynagi() -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        yol = kok / _KAYNAK
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{_KAYNAK} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def test_on_yuzdeki_toplu_nusha_siniri_backendle_aynidir() -> None:
    eslesme = _SABIT.search(_on_yuz_kaynagi())
    assert eslesme is not None, f"{_KAYNAK} içinde `const EN_COK_NUSHA = <sayı>;` yok."
    assert int(eslesme.group(1)) == MAX_COPIES_PER_ROW


def test_toplu_nusha_ucunun_ust_siniri_ayni_kaynaktan_gelir() -> None:
    """Serializer sınırı da aynı sabittir; üçüncü bir kopya doğmasın."""
    alan: Any = CopyBulkCreateSerializer().fields["count"]
    assert alan.max_value == MAX_COPIES_PER_ROW
