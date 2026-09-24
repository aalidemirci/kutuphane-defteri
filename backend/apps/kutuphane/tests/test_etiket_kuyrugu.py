"""Etiket kuyruğu: üyelik, süzgeçler ve seçilebilir basım sırası (D20, tasarım §7.2).

Kuyruk üç tanedir, işaret iki tanedir (`selectors_kuyruk` başlığındaki tablo):
barkod kuyruğu `label_printed_at` boş, sırt kuyruğu `spine_label_printed_at`
boş, "ikisi birden" kuyruğu İKİSİ de boş nüshalardır. Bütün veriler uydurmadır.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.models import Copy, CopyStatus, LabelOrder, LabelPrintKind
from apps.kutuphane.selectors_kuyruk import QueueFilters, call_number_sort_key, ordered_copy_ids
from apps.kutuphane.services import barcode_reservations as rezervasyon
from apps.kutuphane.services import label_queue
from apps.kutuphane.tests import kuyruk_ortak, ortak

pytestmark = pytest.mark.django_db


def _kuyruk(kind: str, filters: QueueFilters | None = None) -> set[int]:
    return set(selectors_kuyruk.label_queue(kind, filters).values_list("pk", flat=True))


# ============================================================ Üyelik
class TestKuyrukUyeligi:
    def test_yeni_nusha_uc_kuyrukta_da_vardir(self) -> None:
        nusha = ortak.nusha()
        for kind in LabelPrintKind.values:
            assert nusha.pk in _kuyruk(kind), kind

    def test_barkodu_basilmis_nusha_yalniz_sirt_kuyrugundadir(self) -> None:
        """Yöntem B: önceden basılmış barkod etiketi bağlanan kitaba İKİNCİ barkod basılmaz."""
        nusha = ortak.nusha()
        Copy.objects.filter(pk=nusha.pk).update(label_printed_at=timezone.now())

        assert nusha.pk in _kuyruk(LabelPrintKind.SPINE)
        assert nusha.pk not in _kuyruk(LabelPrintKind.BARCODE)
        assert nusha.pk not in _kuyruk(LabelPrintKind.BOTH)

    def test_sirti_basilmis_nusha_yalniz_barkod_kuyrugundadir(self) -> None:
        nusha = ortak.nusha()
        Copy.objects.filter(pk=nusha.pk).update(spine_label_printed_at=timezone.now())

        assert nusha.pk in _kuyruk(LabelPrintKind.BARCODE)
        assert nusha.pk not in _kuyruk(LabelPrintKind.SPINE)
        assert nusha.pk not in _kuyruk(LabelPrintKind.BOTH)

    def test_bos_etiketi_baglanan_nusha_sirt_kuyruguna_girer(self) -> None:
        aralik = rezervasyon.reserve(1)
        nusha = rezervasyon.bind_label(
            label=aralik.first_barcode, work=ortak.eser(), acquisition=ortak.edinim()
        )
        assert nusha.pk in _kuyruk(LabelPrintKind.SPINE)
        assert nusha.pk not in _kuyruk(LabelPrintKind.BOTH)

    def test_kayittan_dusulmus_ve_silinmis_nusha_kuyruga_girmez(self) -> None:
        dusen, silinen, kalan = kuyruk_ortak.nushalar(3)
        Copy.objects.filter(pk=dusen.pk).update(status=CopyStatus.WITHDRAWN_WEEDED)
        silinen.delete()

        assert _kuyruk(LabelPrintKind.BOTH) == {kalan.pk}

    def test_dogrulanmamislar_basilmis_ama_okutulmamis_nushalardir(self) -> None:
        basilmamis, dogrulanmamis, dogrulanmis = kuyruk_ortak.nushalar(3)
        simdi = timezone.now()
        Copy.objects.filter(pk=dogrulanmamis.pk).update(label_printed_at=simdi)
        Copy.objects.filter(pk=dogrulanmis.pk).update(
            label_printed_at=simdi, label_verified_at=simdi
        )

        kume = set(selectors_kuyruk.unverified_labels().values_list("pk", flat=True))
        assert kume == {dogrulanmamis.pk}
        assert basilmamis.pk not in kume


# ============================================================ Süzgeçler
class TestSuzgecler:
    def test_bolum_edinim_ve_aralik_suzgeci(self) -> None:
        edebiyat = ortak.bolum(name="Edebiyat")
        tarih = ortak.bolum(name="Tarih")
        parti = ortak.edinim()
        a = ortak.nusha(section=edebiyat, acquisition=parti)
        b = ortak.nusha(section=tarih)
        aralik = rezervasyon.reserve(1)
        c = rezervasyon.bind_label(
            label=aralik.first_barcode, work=ortak.eser(), acquisition=ortak.edinim()
        )

        assert _kuyruk(LabelPrintKind.BOTH, QueueFilters(section_id=edebiyat.pk)) == {a.pk}
        assert _kuyruk(LabelPrintKind.BOTH, QueueFilters(section_id=tarih.pk)) == {b.pk}
        assert _kuyruk(LabelPrintKind.BOTH, QueueFilters(acquisition_id=parti.pk)) == {a.pk}
        assert _kuyruk(LabelPrintKind.SPINE, QueueFilters(reservation_id=aralik.pk)) == {c.pk}

    def test_kayit_tarihi_suzgeci_yerel_gune_bakar(self) -> None:
        eski, yeni = kuyruk_ortak.nushalar(2)
        # 15.09.2026 00:30 İstanbul = 14.09.2026 21:30 UTC: yerel gün 15'idir.
        yerel = timezone.make_aware(dt.datetime(2026, 9, 15, 0, 30))
        Copy.objects.filter(pk=eski.pk).update(created_at=yerel)
        Copy.objects.filter(pk=yeni.pk).update(
            created_at=timezone.make_aware(dt.datetime(2026, 9, 20, 12, 0))
        )

        gun = dt.date(2026, 9, 15)
        assert _kuyruk(LabelPrintKind.BOTH, QueueFilters(created_from=gun, created_to=gun)) == {
            eski.pk
        }
        assert _kuyruk(LabelPrintKind.BOTH, QueueFilters(created_from=dt.date(2026, 9, 16))) == {
            yeni.pk
        }


# ============================================================ Sıra (D20)
class TestYerNumarasiSiralamaAnahtari:
    def test_dewey_sayisi_sayi_gibi_ondalik_kismi_rakam_dizisi_gibi(self) -> None:
        sira = sorted(["813.6", "92", "813.54", "100", "813", "813,5"], key=call_number_sort_key)
        assert sira == ["92", "100", "813", "813,5", "813.54", "813.6"]

    def test_yazar_kodu_turk_alfabesiyle_cilt_sayiyla(self) -> None:
        sira = sorted(
            ["813 DAR", "813 ÇAK", "813 CAN", "813 ÇAK c.10", "813 ÇAK c.2"],
            key=call_number_sort_key,
        )
        assert sira == ["813 CAN", "813 ÇAK", "813 ÇAK c.2", "813 ÇAK c.10", "813 DAR"]

    def test_onekli_yer_numarasinda_dewey_ondaligi_da_rakam_dizisidir(self) -> None:
        """Denetim bulgusu (24.09.2026): 'Ç 813.6' raf sırasında 'Ç 813.54'ten önce geliyordu."""
        assert call_number_sort_key("Ç 813.54 ABC") < call_number_sort_key("Ç 813.6 ABC")
        assert call_number_sort_key("R 920.05") < call_number_sort_key("R 920.1")
        assert call_number_sort_key("R 920,05") < call_number_sort_key("R 920,1")
        sira = sorted(
            ["Ç 813.6 ABC", "Ç 813 ABC", "Ç 813.54 ABC", "Ç 92 ABC", "Ç 813.54 ABC c.10"],
            key=call_number_sort_key,
        )
        assert sira == ["Ç 92 ABC", "Ç 813 ABC", "Ç 813.54 ABC", "Ç 813.54 ABC c.10", "Ç 813.6 ABC"]
        # Öneksiz hâl değişmez; cilt eki ('c.2' < 'c.10') ondalık sayılmaz.
        assert call_number_sort_key("813.54 ÇAK c.2") < call_number_sort_key("813.54 ÇAK c.10")

    def test_onekli_yer_numarasi_kuyrukta_raf_sirasiyla_basilir(self) -> None:
        yeni = ortak.nusha(ortak.eser(title="Yeni", call_number="Ç 813.6"))
        eski = ortak.nusha(ortak.eser(title="Eski", call_number="Ç 813.54"))
        sira = ordered_copy_ids(
            Copy.objects.filter(pk__in=[yeni.pk, eski.pk]), LabelOrder.CALL_NUMBER
        )
        assert sira == [eski.pk, yeni.pk]

    def test_sayisiz_yer_numarasi_sonra_bos_olan_en_sona(self) -> None:
        sira = sorted(["", "R 920", "900 ÖZT", "Ç 813"], key=call_number_sort_key)
        assert sira == ["900 ÖZT", "Ç 813", "R 920", ""]

    def test_kucuk_harf_buyuk_harf_ayni_sirada(self) -> None:
        assert call_number_sort_key("813 çak") == call_number_sort_key("813 ÇAK")


class TestBasimSirasi:
    def test_uc_sira_birbirinden_ayrilir(self) -> None:
        """Yöntem B'de barkod sırası, kayıt sırası ve raf sırası ayrı düşer."""
        aralik = rezervasyon.reserve(2)
        kucuk_numara, buyuk_numara = aralik.numbers.order_by("accession_no")
        edinim = ortak.edinim()
        # Kayıt sırası: önce BÜYÜK numaralı etiket bağlanır, sonra sayaçlı nüsha,
        # en son KÜÇÜK numaralı etiket.
        z = rezervasyon.bind_label(
            label=buyuk_numara.barcode,
            work=ortak.eser(title="Zeytin", classification_code="900", authors="Ali Can"),
            acquisition=edinim,
        )
        m = ortak.nusha(
            ortak.eser(title="Martı", classification_code="813", authors="Ayşe Dar"), edinim
        )
        a = rezervasyon.bind_label(
            label=kucuk_numara.barcode,
            work=ortak.eser(title="Ağaç", classification_code="100", authors="Ece Çakır"),
            acquisition=edinim,
        )
        qs = Copy.objects.filter(pk__in=[z.pk, m.pk, a.pk])

        assert selectors_kuyruk.ordered_copy_ids(qs, LabelOrder.CALL_NUMBER) == [a.pk, m.pk, z.pk]
        assert selectors_kuyruk.ordered_copy_ids(qs, LabelOrder.IMPORT_ROW) == [z.pk, m.pk, a.pk]
        assert selectors_kuyruk.ordered_copy_ids(qs, LabelOrder.BARCODE) == [a.pk, z.pk, m.pk]

    def test_ayni_yer_numarasinda_eser_adi_sonra_kayit_no(self) -> None:
        birinci = ortak.eser(title="Çalıkuşu", classification_code="813", authors="Reşat Nuri")
        ikinci = ortak.eser(title="Acımak", classification_code="813", authors="Reşat Nuri")
        c1 = ortak.nusha(birinci)
        a1 = ortak.nusha(ikinci)
        c2 = ortak.nusha(birinci)
        qs = Copy.objects.filter(pk__in=[c1.pk, a1.pk, c2.pk])

        assert selectors_kuyruk.ordered_copy_ids(qs, LabelOrder.CALL_NUMBER) == [
            a1.pk,
            c1.pk,
            c2.pk,
        ]

    def test_ice_aktarma_sirasi_aktarim_satir_sirasidir(self) -> None:
        """Aktarım satırları sırayla işlenir: bir partinin içinde kayıt sırası = satır sırası."""
        parti = ortak.edinim()
        satirlar = [
            ortak.eser(title="Yaban", classification_code="813"),
            ortak.eser(title="Ateşten Gömlek", classification_code="813"),
            ortak.eser(title="Kiralık Konak", classification_code="813"),
        ]
        acilan = [ortak.nusha(eser, parti).pk for eser in satirlar]

        kume = selectors_kuyruk.label_queue(
            LabelPrintKind.BOTH, QueueFilters(acquisition_id=parti.pk)
        )
        assert selectors_kuyruk.ordered_copy_ids(kume, LabelOrder.IMPORT_ROW) == acilan

    def test_kuyruktan_bas_ilk_n_nushayi_secilen_sirada_alir(self) -> None:
        nushalar = [
            ortak.nusha(ortak.eser(title=f"Eser {sira}", classification_code=kod))
            for sira, kod in enumerate(["900", "100", "500"])
        ]
        ilk_iki = label_queue.queue_copy_ids(
            kind=LabelPrintKind.BOTH, order=LabelOrder.CALL_NUMBER, limit=2
        )
        assert ilk_iki == [nushalar[1].pk, nushalar[2].pk]


# ============================================================ Özet
def test_ozet_sayaclari() -> None:
    a, b, _c = kuyruk_ortak.nushalar(3)
    simdi = timezone.now()
    Copy.objects.filter(pk=a.pk).update(label_printed_at=simdi)
    Copy.objects.filter(pk=b.pk).update(spine_label_printed_at=simdi)
    aralik = rezervasyon.reserve(4)
    kodlar = list(aralik.numbers.order_by("accession_no").values_list("barcode", flat=True))
    rezervasyon.bind_label(label=kodlar[0], work=ortak.eser(), acquisition=ortak.edinim())
    rezervasyon.cancel_numbers(aralik, barcodes=[kodlar[1]])

    ozet = selectors_kuyruk.label_summary()

    # a: yalnız sırt eksik · b: yalnız barkod eksik · c: ikisi · bağlanan: yalnız sırt
    assert ozet["queue"] == {"SPINE": 3, "BARCODE": 2, "BOTH": 1}
    assert ozet["unverified"] == 1  # a (bağlanan nüsha bağlanırken doğrulandı)
    assert ozet["pending_batches"] == 0
    assert ozet["reservations"] == {"reserved": 4, "bound": 1, "cancelled": 1, "open": 2}
