"""Sayım testlerinin ortak kurgusu (toplanmaz: `test_` yok).

Bütün kişi adları UYDURMADIR (CLAUDE.md §2-12): "Deneme …" kalıbı.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.utils import timezone

from apps.kutuphane.models import Copy, StockTake, StockTakeItem, StockTakeStatus
from apps.kutuphane.services import stocktake, tmy_kapisi
from apps.kutuphane.services.stocktake import ApproveResult, ScanResult


def kapi_kaydi(sorulan: list[str]) -> Callable[[str], None]:
    """`tmy_kapisi.ensure_open` yerine takılan kaydedici (hangi işlem kapıyı sordu?).

    F9'dan beri edinim ve yeni nüsha da kapıdan geçer (`EDINIM`; programa aktarım
    ediniminde `PROGRAMA_AKTARIM` — K4): test kurgusunun açtığı nüshaların soruları kayda
    girmez, yalnız sınanan işlemin soruları kalır.
    """

    def kaydet(islem: str) -> None:
        if islem not in (tmy_kapisi.EDINIM, tmy_kapisi.PROGRAMA_AKTARIM):
            sorulan.append(islem)

    return kaydet


#: Uydurma sayım kurulu (TMY 32/2: başkan + taşınır kayıt yetkilisi + en az bir üye).
KURUL: dict[str, str] = {
    "committee_chair": "Deneme Kurulbaşkanı",
    "committee_property_officer": "Deneme Taşınırkayıt",
    "committee_members": "Deneme Kurulüyesi",
}
#: Uydurma harcama yetkilisi.
HARCAMA_YETKILISI = "Deneme Sayımharcama"


def taslak(**alanlar: Any) -> StockTake:
    for ad, deger in KURUL.items():
        alanlar.setdefault(ad, deger)
    return stocktake.create_stocktake(**alanlar)


def durdurma_alanlari() -> dict[str, Any]:
    """TMY 32/3 durdurmasının zorunlu alanları (kurulun talebi + harcama yetkilisi)."""
    bugun = timezone.localdate()
    return {
        "tmy_stop": True,
        "tmy_stop_requested_on": bugun,
        "tmy_stop_by_name": HARCAMA_YETKILISI,
        "tmy_stop_on": bugun,
    }


def baslat(**alanlar: Any) -> StockTake:
    return stocktake.start_stocktake(taslak(**alanlar))


def okut(sayim: StockTake, *nushalar: Copy) -> list[ScanResult]:
    return stocktake.scan_many(sayim, [n.barcode for n in nushalar])


def tamamla(sayim: StockTake) -> StockTake:
    """Sayımı tamamlar (noksan varsa ikinci sayımdan da geçer)."""
    sonuc = stocktake.complete_stocktake(sayim)
    if sonuc.second_round:
        sonuc = stocktake.complete_stocktake(sayim)
    assert sonuc.stocktake.status == StockTakeStatus.COMPLETED
    return sonuc.stocktake


def onayla(sayim: StockTake, **alanlar: Any) -> ApproveResult:
    alanlar.setdefault("approved_by_name", HARCAMA_YETKILISI)
    alanlar.setdefault("approved_on", timezone.localdate())
    return stocktake.approve_stocktake(sayim, **alanlar)


def kalem(sayim: StockTake, copy: Copy) -> StockTakeItem:
    bulunan: StockTakeItem = StockTakeItem.objects.get(stocktake=sayim, copy=copy)
    return bulunan


def tazele_sayim(sayim: StockTake) -> StockTake:
    guncel: StockTake = StockTake.all_objects.get(pk=sayim.pk)
    return guncel
