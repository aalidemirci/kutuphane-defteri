"""docs/sozluk.md ↔ kod eşleşmesi (sözlük BAĞLAYICIDIR — CLAUDE.md §2).

Sözlük "tek kaynak"tır: Ağ Kataloğu metinleri (F5), tutanak metinleri (F8-F9)
ve masa ekranı (F6) hangi sözcüğün kullanılacağını oradan okur. Kod bir etiket
ekleyip sözlük eskidiğinde bu işlev sessizce kırılır — F2, `CopyStatus`'a dört
terminal hâl getirdiğinde tam olarak bu oldu.

Test satırı ÜRETMEZ, KARŞILAŞTIRIR: sözlük metni insan için yazılır (not
sütunu, vurgular), üretilmiş bir liste onu okunmaz kılardı.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.db import models

from apps.kutuphane.models import (
    CopyStatus,
    LabelOrder,
    LabelPrintBatchStatus,
    LabelPrintKind,
    ReservedBarcodeState,
)
from apps.kutuphane.services.barcode_reservations import NEW_NUMBER_HINT

_BELGE = Path("docs") / "sozluk.md"
#: Sözlük satırının etiketleri: kalın yazılır ve " · " ile ayrılır.
_ETIKET = re.compile(r"\*\*(.+?)\*\*")


def _belge_metni() -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        yol = kok / _BELGE
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{_BELGE} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _satir(baslangic: str) -> str:
    for ham in _belge_metni().splitlines():
        if ham.startswith(baslangic):
            return ham
    pytest.fail(f"Sözlükte “{baslangic}…” satırı yok.")


def test_nusha_durumlari_satiri_copystatus_ile_birebir() -> None:
    """Sözlüğün saydığı etiketler `CopyStatus.choices` etiketleridir (sıra dahil)."""
    hucreler = _satir("| Nüsha durumları").split("|")
    etiketler = _ETIKET.findall(hucreler[2])
    assert etiketler == [etiket for _kod, etiket in CopyStatus.choices]


def test_durum_olmayan_ifadeler_not_sutununda_ayrilir() -> None:
    """ "Ödünç verilmez — kütüphanede okunur" bir durum değil, `is_reference` türetimidir."""
    satir = _satir("| Nüsha durumları")
    hucreler = satir.split("|")
    assert "Ödünç verilmez" not in hucreler[2]
    assert "is_reference" in hucreler[4]


# ---------------------------------------------------------------------------
# Etiketler (F4): sözlüğün saydığı seçenek adları kodun seçenekleriyle birebir
# ---------------------------------------------------------------------------
def _kalin_dizi(etiketler: list[str]) -> str:
    """Sözlükteki yazım: kalın etiketler, sırasıyla, " · " ile ayrılır."""
    return " · ".join(f"**{etiket}**" for etiket in etiketler)


@pytest.mark.parametrize(
    ("baslangic", "secenekler"),
    [
        ("| Basım kaydı", LabelPrintBatchStatus),
        ("| Basım sırası", LabelOrder),
        ("| Boş barkod aralığı", ReservedBarcodeState),
    ],
)
def test_etiket_satirlari_kodun_secenekleriyle_birebir(
    baslangic: str, secenekler: type[models.TextChoices]
) -> None:
    """Parti durumları, basım sırası ve numara durumları sözlükte SIRASIYLA ve eksiksiz geçer.

    Kılavuz ve ekran bu adları kullanır; kod bir seçenek ekler ya da adını
    değiştirirse sözlük satırı da değişmek zorunda kalır.
    """
    hucre = _satir(baslangic).split("|")[2]
    assert _kalin_dizi([etiket for _kod, etiket in secenekler.choices]) in hucre


def test_etiket_turleri_satiri_parti_iceriklerini_sayar() -> None:
    """`LabelPrintKind` etiketleri (sırt · barkod · ikisi birden) sözlükte kalın geçer."""
    hucre = _satir("| Etiket türleri").split("|")[2]
    for _kod, etiket in LabelPrintKind.choices:
        # Sözlükte kavram adı cümle içinde küçük harfle başlar ("**sırt etiketi**").
        assert f"**{etiket[0].lower()}{etiket[1:]}**" in hucre, etiket


def test_hizli_kayit_etiket_ipucu_sozlukte_birebir() -> None:
    """Etiket reddedilince sunucunun verdiği ipucu sözlük §4.7'de aynı metinle yazılıdır."""
    metin = re.sub(r"\s+", " ", _belge_metni())
    assert NEW_NUMBER_HINT in metin
