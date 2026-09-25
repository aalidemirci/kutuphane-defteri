"""Tek açık kayıt kuralı — ödünç ile teslim arasında (§9-7, F7 kod kapısı).

"Bir nüsha aynı anda yalnız bir açık ödünçte ya da teslimde olabilir." Aynı
tablodaki ikinci açık kaydı kısmi teklik kısıtları keser; iki tablo arasındaki
yarışı nüsha durumunun koşullu geçişi keser (`services.nusha_durumu`). Sınananlar:

1. Olağan yol: ödünçteki nüsha teslim edilmez, teslimdeki nüsha ödünç verilmez.
2. **Bayat ön denetim** (yarışın belirleyici taklidi): servislerin ön denetimi
   "rafta" diye geçse bile (ör. iki işlem aynı anı okudu), koşullu geçiş ikinciyi
   durdurur ve onun kaydı geri sarılır.
3. **Gerçek eşzamanlılık**: iki iş parçacığı aynı nüshayı aynı anda biri ödünç,
   öbürü teslim etmeye çalışır; yalnız biri kazanır, açık kayıt tektir.
4. DB kısıtı: aynı nüshaya ikinci açık teslim satırı yazılamaz.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection

from apps.kutuphane.models import Copy, CopyStatus, Delivery, DeliveryStatus, Loan, LoanStatus
from apps.kutuphane.services import circulation, deliveries
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, uye
from apps.kutuphane.tests.teslim_ortak import sube, tazele_nusha, teslim_et


def _acik_kayit_sayisi(copy: Copy) -> int:
    return (
        Loan.objects.filter(copy=copy, status=LoanStatus.OPEN).count()
        + Delivery.objects.filter(copy=copy, status=DeliveryStatus.OPEN).count()
    )


@pytest.mark.django_db
class TestOlaganYol:
    def test_oduncteki_nusha_teslim_edilmez(self) -> None:
        loan = odunc_ver(uye())
        with pytest.raises(ValidationError):
            teslim_et([loan.copy])
        assert _acik_kayit_sayisi(loan.copy) == 1

    def test_teslimdeki_nusha_odunc_verilmez(self) -> None:
        kitap = teslim_et([odunc_nushasi()]).deliveries[0].copy
        with pytest.raises(DolasimReddi):
            odunc_ver(uye(), tazele_nusha(kitap))
        assert _acik_kayit_sayisi(kitap) == 1


@pytest.mark.django_db
class TestBayatOnDenetim:
    """Ön denetim atlatılır (yarışın penceresi); koşullu geçiş kuralı yine tutar."""

    def test_once_teslim_sonra_bayat_odunc_geri_sarilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kitap = odunc_nushasi()
        bayat = Copy.objects.select_related("work").get(pk=kitap.pk)  # "Rafta" okunmuş kopya
        uyelik = uye()
        teslim_et([kitap])
        # Ödüncün ön denetimleri "rafta" diye geçsin (bayat okuma):
        monkeypatch.setattr(circulation, "_ensure_copy_loanable", lambda *a, **k: None)

        with pytest.raises(DolasimReddi) as ret:
            circulation.checkout(copy=bayat, membership=uyelik)

        assert ret.value.code == circulation.RED_ODUNC_VERILMEZ
        assert not Loan.objects.filter(copy=kitap).exists()  # ödünç geri sarıldı
        assert tazele_nusha(kitap).status == CopyStatus.DELIVERED
        assert _acik_kayit_sayisi(kitap) == 1

    def test_once_odunc_sonra_bayat_teslim_geri_sarilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rafta = odunc_nushasi(title="Rafta Kalan")
        kitap = odunc_nushasi(title="Yarışılan")
        odunc_ver(uye(), kitap)
        # Teslimin ön denetimi "rafta" diye geçsin (bayat okuma):
        monkeypatch.setattr(deliveries, "delivery_obstacle", lambda copy: "")

        with pytest.raises(ValidationError) as hata:
            teslim_et([rafta, kitap])

        assert "raftan çıktı" in " ".join(hata.value.message_dict["barcodes"])
        # Toplu teslim TEK işlemdir: öndeki kitabın teslimi de geri sarıldı.
        assert not Delivery.objects.exists()
        assert tazele_nusha(rafta).status == CopyStatus.AVAILABLE
        assert tazele_nusha(kitap).status == CopyStatus.ON_LOAN
        assert _acik_kayit_sayisi(kitap) == 1


@pytest.mark.django_db
def test_ayni_nushaya_ikinci_acik_teslim_db_kisitiyla_yazilamaz() -> None:
    teslim = teslim_et([odunc_nushasi()]).deliveries[0]
    with pytest.raises(IntegrityError):
        Delivery.objects.create(
            copy=teslim.copy,
            recipient_kind=teslim.recipient_kind,
            section=teslim.section,
            document_no="elle",
        )


@pytest.mark.django_db(transaction=True)
def test_es_zamanli_odunc_ve_teslimden_yalniz_biri_kazanir() -> None:
    """İki iş parçacığı aynı anda: biri ödünç verir, öbürü teslim eder (dosya tabanlı DB).

    SQLite tek yazar + `IMMEDIATE` işlemleri sıralar; hangisinin önce gireceği
    belirsizdir. Sonuç her sırada aynı olmalıdır: tam olarak BİR işlem kazanır,
    nüshanın tek açık kaydı vardır ve durumu kazananınkiyle eşleşir.
    """
    kitap = odunc_nushasi()
    uyelik = uye()
    sinif = sube()
    baslat = threading.Barrier(2)
    sonuclar: dict[str, Any] = {}

    def odunc() -> None:
        try:
            baslat.wait()
            circulation.checkout(copy=kitap, membership=uyelik)
            sonuclar["odunc"] = "kazandi"
        except (DolasimReddi, ValidationError) as exc:
            sonuclar["odunc"] = exc
        finally:
            connection.close()

    def teslim() -> None:
        try:
            baslat.wait()
            deliveries.deliver(barcodes=[kitap.barcode], section=sinif)
            sonuclar["teslim"] = "kazandi"
        except (DolasimReddi, ValidationError) as exc:
            sonuclar["teslim"] = exc
        finally:
            connection.close()

    isler = [threading.Thread(target=odunc), threading.Thread(target=teslim)]
    for is_ in isler:
        is_.start()
    for is_ in isler:
        is_.join(timeout=30)

    kazananlar = [ad for ad, sonuc in sonuclar.items() if sonuc == "kazandi"]
    assert len(sonuclar) == 2, sonuclar
    assert len(kazananlar) == 1, sonuclar
    assert _acik_kayit_sayisi(kitap) == 1
    beklenen = CopyStatus.ON_LOAN if kazananlar == ["odunc"] else CopyStatus.DELIVERED
    assert tazele_nusha(kitap).status == beklenen
