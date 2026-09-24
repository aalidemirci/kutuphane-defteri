"""Tek sayaç: boş barkod aralığı ile nüsha numarası aynı sayacı paylaşır (F4 kod kapısı).

- **Yarış** — aynı anda numara ayıran ve nüsha açan iş parçacıkları hiçbir
  numarayı iki kez almaz; sayaç verilen numaraların toplamı kadar ilerler.
  Güvence `transaction_mode=IMMEDIATE`'tir (yazma kilidi işlemin başında
  alınır, sayacı okuyan iki işlem aynı anda var olamaz) ve teklik kısıtlarıdır.
  Test veritabanı SQLite'ın paylaşımlı bellek içi veritabanıdır: orada kilide
  takılan istek beklemek yerine hemen "kilitli" hatası alır, bu yüzden iş
  parçacıkları kilit hatasında YENİDEN DENER (masaüstünde `busy_timeout`
  aynı işi bekleyerek yapar). Yeniden deneme çakışmayı gizlemez: çakışma olsa
  teklik kısıtı ya da numara kümesi denetimi düşerdi.
- **Yıl dönümü** — yıl `timezone.localdate()` ile alınır (D6); bir aralık tek
  okumayla ayrıldığı için yıl dönümünü BÖLMEZ.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from django.db import OperationalError, connection
from django.utils import timezone

from apps.kutuphane.models import Copy, CopyCounter, ReservedBarcode
from apps.kutuphane.services import barcode_reservations as rezervasyon
from apps.kutuphane.services import catalog, numbering
from apps.kutuphane.tests import ortak

IS_PARCACIGI = 4
ADIM = 6
ARALIK_ADEDI = 3


def _yeniden_dene(islem: Callable[[], Any]) -> Any:
    """Paylaşımlı bellek içi SQLite'ın anlık kilit hatasında işlemi yeniden dener."""
    son_hata: OperationalError | None = None
    for _ in range(400):
        try:
            return islem()
        except OperationalError as exc:
            if "locked" not in str(exc):
                raise
            son_hata = exc
            time.sleep(0.005)
    raise AssertionError(f"Kilit çözülmedi: {son_hata}")


@pytest.mark.django_db(transaction=True)
def test_sayac_yarisinda_numara_cakismaz() -> None:
    work = ortak.eser()
    acquisition = ortak.edinim()
    hatalar: list[BaseException] = []

    def calis(sira: int) -> None:
        try:
            for adim in range(ADIM):
                if (sira + adim) % 2:
                    _yeniden_dene(lambda: catalog.create_copy(work=work, acquisition=acquisition))
                else:
                    _yeniden_dene(lambda: rezervasyon.reserve(ARALIK_ADEDI))
        except BaseException as exc:  # iş parçacığındaki hata ana teste taşınır
            hatalar.append(exc)
        finally:
            connection.close()

    parcaciklar = [threading.Thread(target=calis, args=(i,)) for i in range(IS_PARCACIGI)]
    for parcacik in parcaciklar:
        parcacik.start()
    for parcacik in parcaciklar:
        parcacik.join(timeout=120)

    assert not hatalar, hatalar
    nusha_numaralari = list(Copy.all_objects.values_list("barcode", flat=True))
    ayrilan_numaralar = list(ReservedBarcode.objects.values_list("barcode", flat=True))
    butun = nusha_numaralari + ayrilan_numaralar

    toplam_islem = IS_PARCACIGI * ADIM
    beklenen = (toplam_islem // 2) * 1 + (toplam_islem // 2) * ARALIK_ADEDI
    assert len(butun) == beklenen
    assert len(set(butun)) == beklenen, "aynı numara iki kez verildi"
    yil = timezone.localdate().year
    assert CopyCounter.objects.get(year=yil).last_no == beklenen
    # Numaralar boşluksuz: sayaç yalnız verdiği kadar ilerledi.
    assert sorted(int(kod[4:]) for kod in butun) == list(range(1, beklenen + 1))


@pytest.mark.django_db
class TestYilDonumu:
    def test_aralik_yerel_gunun_yilini_alir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """UTC anı 31.12.2026 22:00 iken yerel gün 01.01.2027'dir; aralık 2027'den başlar."""
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2027, 1, 1))
        aralik = rezervasyon.reserve(2)
        assert aralik.year == 2027
        assert aralik.first_barcode == "2027000001"

    def test_aralik_yil_donumunu_bolmez(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """İşlemin ortasında gün dönse bile aralığın bütün numaraları tek yıla aittir."""
        gunler = iter([dt.date(2026, 12, 31)] + [dt.date(2027, 1, 1)] * 10)
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: next(gunler))

        aralik = rezervasyon.reserve(4)

        yillar = {kod[:4] for kod in aralik.numbers.values_list("barcode", flat=True)}
        assert yillar == {"2026"} and aralik.year == 2026

    def test_yeni_yilda_sayac_birden_baslar_eski_aralik_gecerli_kalir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2026, 12, 31))
        eski = rezervasyon.reserve(3)
        numbering.next_copy_identity()

        monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2027, 1, 1))
        yeni = rezervasyon.reserve(1)
        assert yeni.first_barcode == "2027000001"
        assert CopyCounter.objects.get(year=2026).last_no == 4

        # 2026'da ayrılıp 2027'de bağlanan etiket kendi numarasını korur.
        nusha = rezervasyon.bind_label(
            label=eski.first_barcode, work=ortak.eser(), acquisition=ortak.edinim()
        )
        assert nusha.barcode == "2026000001"
        assert numbering.next_copy_identity()[1] == "2027000002"
