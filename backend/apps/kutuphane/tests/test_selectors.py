"""Katalog seçicileri: süzgeçler, sayaçlar, barkodla arama, sayfalamaya uygun sıra."""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.kutuphane import selectors
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    AcquisitionMethod,
    Copy,
    CopyStatus,
    ResourceType,
)
from apps.kutuphane.tests.ortak import bolum, edinim, eser, karar, nusha, nusha_sayaclari


@pytest.mark.django_db
class TestEserSuzgecleri:
    def test_bolume_gore_suzulur(self) -> None:
        edebiyat = bolum(name="Edebiyat")
        tarih = bolum(name="Tarih")
        eser(title="Çalıkuşu", section=edebiyat)
        eser(title="Nutuk", section=tarih)
        assert [w.title for w in selectors.works(section_id=tarih.pk)] == ["Nutuk"]

    def test_kaynak_turune_gore_suzulur(self) -> None:
        eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        eser(title="Çalıkuşu")
        sonuc = selectors.works(resource_type=ResourceType.PERIODICAL)
        assert [w.title for w in sonuc] == ["Bilim ve Teknik"]

    def test_taninmayan_siralama_ad_eksenine_duser(self) -> None:
        assert selectors.work_ordering("bilinmeyen") == selectors.WORK_ORDERINGS["title"]
        assert selectors.work_ordering(None) == selectors.WORK_ORDERINGS["title"]

    def test_sayfalama_kararlidir(self) -> None:
        """D9: aynı sorgunun iki sayfası aynı kaydı iki kez göstermez."""
        for ad in ("Armut", "Çınar", "Dut", "Elma", "Fındık"):
            eser(title=ad)
        qs = selectors.works()
        ilk_sayfa = [w.title for w in qs[:2]]
        ikinci_sayfa = [w.title for w in qs[2:4]]
        assert ilk_sayfa == ["Armut", "Çınar"]
        assert ikinci_sayfa == ["Dut", "Elma"]


@pytest.mark.django_db
class TestNushaSuzgecleri:
    def test_barkodla_bulunur_ve_basili_bicim_de_calisir(self) -> None:
        copy = nusha()
        assert selectors.find_copy_by_barcode(copy.barcode) == copy
        basili = f"{copy.barcode[:4]}-{copy.barcode[4:]}"
        assert selectors.find_copy_by_barcode(basili) == copy

    def test_yanlis_uzunluktaki_kod_bos_doner(self) -> None:
        nusha()
        assert selectors.find_copy_by_barcode("12345") is None

    def test_eski_kayit_no_ile_bulunur(self) -> None:
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition, old_register_no="1452")
        nusha(work, acquisition)
        bulunanlar = selectors.find_copies_by_old_register_no("1452")
        assert [c.old_register_no for c in bulunanlar] == ["1452"]
        assert list(selectors.find_copies_by_old_register_no("")) == []

    def test_yalniz_odunc_verilebilirler_suzulur(self) -> None:
        work = eser()
        acquisition = edinim()
        rafta = nusha(work, acquisition)
        nusha(work, acquisition, is_reference=True)
        assert [c.pk for c in selectors.copies(only_loanable=True)] == [rafta.pk]

    def test_kayittan_dusulenler_elenebilir(self) -> None:
        work = eser()
        acquisition = edinim()
        kalan = nusha(work, acquisition)
        dusulen = nusha(work, acquisition)
        dusulen.status = CopyStatus.WITHDRAWN_WEEDED
        dusulen.save(update_fields=["status"])
        assert [c.pk for c in selectors.copies(include_terminal=False)] == [kalan.pk]
        assert len(selectors.copies()) == 2

    def test_etiketlenmemis_kuyrugu_suzulur(self) -> None:
        work = eser()
        acquisition = edinim()
        etiketsiz = nusha(work, acquisition)
        etiketli = nusha(work, acquisition)
        etiketli.label_printed_at = timezone.now()
        etiketli.save(update_fields=["label_printed_at"])
        assert [c.pk for c in selectors.copies(only_unlabeled=True)] == [etiketsiz.pk]


@pytest.mark.django_db
class TestOzetler:
    def test_koleksiyon_ozeti_kisisiz_sayilar_doner(self) -> None:
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition)
        oduncteki = nusha(work, acquisition)
        oduncteki.status = CopyStatus.ON_LOAN
        oduncteki.save(update_fields=["status"])
        ozet = selectors.collection_summary()
        assert ozet["work_count"] == 1
        assert ozet["copy_count"] == 2
        assert ozet["available_count"] == 1
        assert ozet["status_counts"][CopyStatus.ON_LOAN] == 1

    def test_nusha_sayaclari_esere_eklenir(self) -> None:
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition)
        nusha(work, acquisition)
        satir = nusha_sayaclari(work.pk)
        assert satir["copy_count"] == 2
        assert satir["available_copy_count"] == 2

    def test_kayittan_dusulen_nusha_elde_bulunanda_sayilmaz(self) -> None:
        """Md. 7/1 eşiği ELDE BULUNAN dermedir; defterden düşmüş kayıt oraya girmez.

        `copy_count` kayıt defterinin toplamıdır (TMY dökümünün baktığı sayı),
        `in_stock_count` elde bulunandır, `available_count` rafta olandır.
        """
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition)
        dusulen = nusha(work, acquisition)
        Copy.objects.filter(pk=dusulen.pk).update(status=CopyStatus.WITHDRAWN_WEEDED)

        ozet = selectors.collection_summary()
        assert ozet["copy_count"] == 2
        assert ozet["in_stock_count"] == 1
        assert ozet["available_count"] == 1
        assert ozet["copy_count"] - ozet["in_stock_count"] == sum(
            ozet["status_counts"][durum] for durum in TERMINAL_COPY_STATUSES
        )

    def test_kayittan_dusulen_nusha_katalog_sutununda_sayilmaz(self) -> None:
        """Katalog listesinin "Nüsha" sütunu elde bulunanı sayar (kayıt defterini değil)."""
        work = eser()
        acquisition = edinim()
        nusha(work, acquisition)
        devredilen = nusha(work, acquisition)
        Copy.objects.filter(pk=devredilen.pk).update(status=CopyStatus.TRANSFERRED)

        satir = nusha_sayaclari(work.pk)
        assert satir["copy_count"] == 1
        assert satir["available_copy_count"] == 1


@pytest.mark.django_db
class TestEdinimVeKarar:
    def test_edinimler_yonteme_gore_suzulur(self) -> None:
        edinim(method=AcquisitionMethod.PURCHASE)
        edinim(method=AcquisitionMethod.EXISTING_STOCK)
        sonuc = selectors.acquisitions(method=AcquisitionMethod.PURCHASE)
        assert [a.method for a in sonuc] == [AcquisitionMethod.PURCHASE]

    def test_kararlar_ture_gore_suzulur(self) -> None:
        karar(decision_type="DONATION_REVIEW")
        karar(decision_type="WEEDING")
        sonuc = selectors.commission_decisions(decision_type="WEEDING")
        assert [d.decision_type for d in sonuc] == ["WEEDING"]
