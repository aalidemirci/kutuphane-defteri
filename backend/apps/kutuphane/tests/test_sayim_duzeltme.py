"""Sayım — F9 düzeltme turu (25.09.2026) bulgularını kilitleyen testler.

Her test bir denetim bulgusunun senaryosunu yeniden kurar; düzeltmeden önce kırmızıydı:

- onarımdan AYNI GÜN sayım başlamadan önce dönen ve okutulmayan nüsha "bulundu" sayılıyordu
  (dönüş gün düzeyinde karşılaştırılıyordu);
- kayıp dosyasında "Aynısı temin edildi" ile rafa dönen nüsha dönüş sayılmıyor, kitap
  kütüphanede dururken 32/7 ile düşülüyordu;
- sayım fazlası olarak okutulan boş etiket sayım sırasında Hızlı Kayıt'ta bağlanınca onay
  aynı kitabı ikinci kez kayda alıyordu (D17'nin yeniden doğrulaması fazlaya uygulanmıyordu);
- harfli iki ayrı eski etiket rakamlarına indirgenip tek fazlada birleşiyordu;
- kararı bekleyen fazla varken tamamlanmış sayımın sayıları "kesin" sayılıyordu;
- iki seçenek birlikte seçilince durdurma satırı "Ödünç ve iade açıktır" diyordu;
- durdurma sürerken Hızlı Kayıt'ın etiket ön denetimi kapıyı sormuyordu;
- onay penceresinin uyarısı için kayıtta kayıp ve onarımda görünen noksanlar sayılır;
- sayım fazlası ediniminin notu iç kimlik taşıyordu.

Bütün adlar ve numaralar uydurmadır.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import (
    Acquisition,
    CaseResolution,
    Copy,
    CopyStatus,
    CountBasis,
    StockTakeFoundVia,
    StockTakeItem,
    StockTakeOutcome,
    StockTakeResult,
)
from apps.kutuphane.services import barcode_reservations, loss_damage, stocktake, tmy_kapisi
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, uye
from apps.kutuphane.tests.ortak import edinim, eser, nusha
from apps.kutuphane.tests.sayim_ortak import (
    baslat,
    durdurma_alanlari,
    kalem,
    okut,
    onayla,
    tamamla,
    taslak,
    tazele_sayim,
)
from apps.kutuphane.tests.teslim_ortak import tazele_nusha

pytestmark = pytest.mark.django_db


# ============================================================ sayım sırasında dönüş


class TestDonus:
    def test_sayim_baslamadan_ayni_gun_onarimdan_donen_okutulmayan_nusha_noksandir(self) -> None:
        kitap = nusha(eser(title="Aynı Gün Onarımdan Dönen"))
        loss_damage.send_to_repair(kitap)
        loss_damage.return_from_repair(kitap)
        sayim = baslat()
        assert kalem(sayim, kitap).expected_status == CopyStatus.AVAILABLE

        assert selectors_sayim.progress(sayim)["physical_found"] == 0
        tamamla(sayim)
        assert kalem(sayim, kitap).result == StockTakeResult.MISSING

    def test_sayim_sirasinda_onarimdan_donen_nusha_bulundu_sayilir(self) -> None:
        kitap = nusha(eser(title="Sayımda Onarımdan Dönen"))
        loss_damage.send_to_repair(kitap)
        # K2: "Sayımdan önce geri alınır" — onarımdaki nüsha fiziki ilerlemeye girer.
        sayim = baslat(repair_basis=CountBasis.COLLECT)
        loss_damage.return_from_repair(kitap)

        assert selectors_sayim.progress(sayim)["physical_found"] == 1
        tamamla(sayim)
        sonuc = kalem(sayim, kitap)
        assert (sonuc.result, sonuc.found_via) == (
            StockTakeResult.FOUND,
            StockTakeFoundVia.RETURN,
        )

    def test_kayip_dosyasinda_aynisinin_temini_donus_sayilir_dusulmez(self) -> None:
        kitap = odunc_nushasi(title="Temin Edilen")
        dosya = loss_damage.report_lost(copy=kitap)
        sayim = baslat()  # TMY 32/3 durdurması YOK: temin açıktır
        loss_damage.resolve_case(dosya, resolution=CaseResolution.REPLACED_SAME)
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE

        tamamla(sayim)
        sonuc = kalem(sayim, kitap)
        assert (sonuc.result, sonuc.found_via) == (
            StockTakeResult.FOUND,
            StockTakeFoundVia.RETURN,
        )
        onay = onayla(tazele_sayim(sayim))
        assert onay.written_off == 0
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE

    def test_raftaki_nushaya_donus_cozumleri_tek_kaynaktan(self) -> None:
        """`resolve_case` ile sayımın dönüş sorgusu aynı kümeyi kullanır."""
        from apps.kutuphane.models import SHELF_RETURN_RESOLUTIONS

        assert set(SHELF_RETURN_RESOLUTIONS) == {
            CaseResolution.FOUND_RETURNED,
            CaseResolution.FOUND_AFTER_PRICE,
            CaseResolution.REPLACED_SAME,
            CaseResolution.CLOSED_SAME_REPURCHASED,
        }


# ============================================================ sayım fazlası


class TestFazla:
    def test_bos_etiket_fazlasi_sayimda_baglanirsa_onay_ikinci_nusha_acmaz(self) -> None:
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        hedef = eser(title="Sayımda Bağlanan Boş Etiket")
        sayim = baslat()  # durdurma yok: hızlı kayıt açık
        sonuc = stocktake.scan_many(sayim, [etiket])[0]
        assert sonuc.code == stocktake.OKUTMA_FAZLA and sonuc.item is not None
        stocktake.update_surplus(sonuc.item, work=hedef)
        bagli = barcode_reservations.bind_label(label=etiket, work=hedef, acquisition=edinim())

        # Kalem yanıtı ve ekran kararı: kitap sayım sırasında kayda girdi.
        ozet = selectors_sayim.summary(sayim)
        assert ozet["surplus_bound"] == 1 and ozet["surplus_unresolved"] == 0
        tamamla(sayim)
        onay = onayla(tazele_sayim(sayim))

        assert onay.surplus_entered == 0
        assert list(Copy.objects.filter(work=hedef).values_list("pk", flat=True)) == [bagli.pk]
        fazla = StockTakeItem.objects.get(pk=sonuc.item.pk)
        assert fazla.outcome == StockTakeOutcome.NOT_ENTERED and fazla.created_copy is None
        assert "sayım sırasında" in fazla.outcome_note
        assert tazele_sayim(sayim).surplus_acquisition is None

    def test_bagli_fazla_karar_beklemeden_onayi_durdurmaz(self) -> None:
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        hedef = eser(title="Kararsız Bağlanan")
        sayim = baslat()
        stocktake.scan_many(sayim, [etiket])
        barcode_reservations.bind_label(label=etiket, work=hedef, acquisition=edinim())
        bekleyen = selectors_sayim.items(sayim, surplus=True, undecided=True)
        assert bekleyen.count() == 0
        onayla(tamamla(sayim))
        assert Copy.objects.filter(work=hedef).count() == 1

    def test_karar_bekleyen_suzgeci_yalniz_kararsiz_fazlayi_verir(self) -> None:
        sayim = baslat()
        kararsiz = stocktake.add_surplus(sayim, note="Etiketsiz bir")
        secilmis = stocktake.add_surplus(sayim, note="Etiketsiz iki", work=eser(title="Seçilmiş"))
        haric = stocktake.add_surplus(sayim, note="Etiketsiz üç")
        stocktake.update_surplus(haric, excluded=True, note="Kütüphaneye ait değil")
        assert [k.pk for k in selectors_sayim.items(sayim, surplus=True, undecided=True)] == [
            kararsiz.pk
        ]
        assert {k.pk for k in selectors_sayim.items(sayim, surplus=True, undecided=False)} == {
            secilmis.pk,
            haric.pk,
        }

    def test_harfli_eski_etiketler_birlesmez_yazilmaz(self) -> None:
        sayim = baslat()
        birinci, ikinci, yalniz_harf = stocktake.scan_many(
            sayim, ["KTP-A00123", "KTP-B00123", "KTP"]
        )
        for sonuc in (birinci, ikinci, yalniz_harf):
            assert sonuc.code == stocktake.OKUTMA_GECERSIZ
            assert sonuc.message == stocktake.SCAN_LETTERS
        assert not StockTakeItem.objects.filter(stocktake=sayim, copy__isnull=True).exists()

    def test_fazla_ediniminin_notu_ic_kimlik_tasimaz(self) -> None:
        sayim = baslat()
        stocktake.add_surplus(sayim, note="Etiketsiz", work=eser(title="Kayda Alınan Fazla"))
        onayla(tamamla(sayim))
        guncel = tazele_sayim(sayim)
        assert guncel.surplus_acquisition is not None
        edinim_kaydi = Acquisition.objects.get(pk=guncel.surplus_acquisition.pk)
        assert "#" not in edinim_kaydi.notes
        assert stocktake.sayim_adi(guncel) in edinim_kaydi.notes
        baslangic = timezone.localtime(guncel.started_at)
        assert stocktake.sayim_adi(guncel) == (
            f"Sayım · {guncel.fiscal_year} · {baslangic:%d.%m.%Y}"
        )


# ============================================================ kesinlik ve uyarılar


class TestKesinlikVeUyarilar:
    def test_karar_bekleyen_fazla_varken_tamamlanmis_sayim_kesin_degildir(self) -> None:
        nusha(eser(title="Rafta"))
        sayim = baslat()
        okut(sayim, *Copy.objects.all())
        fazla = stocktake.add_surplus(sayim, note="Etiketsiz")
        tamamla(sayim)
        bulunan = selectors_sayim.found_quantity(tazele_sayim(sayim))
        assert (bulunan["final"], bulunan["surplus_unresolved"]) == (False, 1)
        assert selectors_sayim.tmy_34_1(tazele_sayim(sayim))["next_year_carryover"] is None

        stocktake.update_surplus(fazla, excluded=True, note="Kütüphaneye ait değil")
        bulunan = selectors_sayim.found_quantity(tazele_sayim(sayim))
        assert (bulunan["final"], bulunan["found"]) == (True, 1)

    def test_onay_uyarisi_icin_kayip_ve_onarimdaki_noksan_sayilir(self) -> None:
        kayip = odunc_nushasi(title="Kayıpta")
        loss_damage.report_lost(copy=kayip)
        onarimda = nusha(eser(title="Ciltçide"))
        kayda_gore = nusha(eser(title="Sayımdan Önce Ciltçide"))
        loss_damage.send_to_repair(kayda_gore)
        nusha(eser(title="Raftan Kaybolan"))
        sayim = baslat(**durdurma_alanlari())
        # K2: sayımdan önce onarımda olan nüsha kurulun seçimiyle kayda göre alınır; noksanda
        # "Onarımda" görünen yalnız sayım SIRASINDA onarıma gönderilendir.
        loss_damage.send_to_repair(onarimda)
        sayim = tamamla(sayim)
        ozet = selectors_sayim.summary(sayim)
        assert ozet["results"][StockTakeResult.MISSING] == 3
        assert (ozet["missing_recorded_lost"], ozet["missing_in_repair"]) == (1, 1)
        assert kalem(sayim, kayda_gore).result == StockTakeResult.BY_RECORD


# ============================================================ seçenek metinleri ve kapı


class TestSecenekMetinleri:
    def test_iki_secenek_birlikte_secilince_odunc_acik_denmez(self) -> None:
        sayim = taslak(**durdurma_alanlari(), service_pause=True)
        durdurma = selectors_sayim.options_lines(sayim)[0]
        assert "Ödünç ve iade açıktır" not in durdurma["text"]
        assert selectors_sayim.TMY_STOP_NOT_COVERED_TEXT in durdurma["text"]
        assert "açıktır" not in tmy_kapisi.STOP_MESSAGE
        assert tmy_kapisi.STOP_MESSAGE.endswith(selectors_sayim.TMY_STOP_NOT_COVERED_TEXT)

    def test_durdurma_kapsam_metni_kapinin_kapsamiyla_yazilir(self) -> None:
        """K1 (25.09.2026): kayıp dosyasında bulunma da kapsam dışıdır."""
        metin = selectors_sayim.TMY_STOP_SCOPE_TEXT
        assert "kayıp dosyasının bulunma ve bedel adımları dışındaki çözümü" in metin
        assert "hasar dosyasında kayıttan düşme önerisi" in metin
        assert "kayıp/hasar dosyası çözümü" not in metin
        for bulunma in (CaseResolution.FOUND_RETURNED, CaseResolution.FOUND_AFTER_PRICE):
            assert not tmy_kapisi.dosya_cozumu_kapsamda_mi("LOST", bulunma)

    def test_sinif_kitapliginda_kayda_gore_alma_yoktur(self) -> None:
        """K3 (25.09.2026): seçenek kalktı; toplanamayan şube nüshası yerinde aranır."""
        from apps.kutuphane.models import SECTION_DELIVERY_BASIS_CHOICES

        assert CountBasis.BY_RECORD not in SECTION_DELIVERY_BASIS_CHOICES
        assert ("section_delivery", CountBasis.BY_RECORD) not in selectors_sayim.BASIS_DAYANAK
        for secim in SECTION_DELIVERY_BASIS_CHOICES:
            dayanak = selectors_sayim.BASIS_DAYANAK[("section_delivery", secim)]
            assert "32/5 birinci cümleye kıyasen" in dayanak, secim
            assert "kayda göre" not in dayanak, secim
        assert (
            "yerinde aranır, bulunmazsa noksandır"
            in (selectors_sayim.BASIS_DAYANAK[("section_delivery", CountBasis.COLLECT)])
        )

    def test_onarimdaki_nushanin_dayanagi_uydurulmaz(self) -> None:
        """K2: TMY'de onarıma gönderilmiş taşınırın sayımına ilişkin hüküm yok — 32/5 anılmaz."""
        from apps.kutuphane.models import REPAIR_BASIS_CHOICES

        for secim in REPAIR_BASIS_CHOICES:
            dayanak = selectors_sayim.BASIS_DAYANAK[("repair", secim)]
            assert "sayım kurulunun kararıdır" in dayanak, secim
            assert "doğrudan hüküm yoktur" in dayanak, secim
            assert "32/5" not in dayanak, secim

    def test_durdurmada_hizli_kayit_etiketi_bastan_reddedilir(self) -> None:
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        assert barcode_reservations.check_label(etiket)["bindable"] is True
        sayim = baslat(**durdurma_alanlari())
        yanit = barcode_reservations.check_label(etiket)
        assert yanit["bindable"] is False
        assert "TMY 32/3 durdurması" in yanit["message"] and yanit["hint"] == ""
        stocktake.cancel_stocktake(sayim)
        assert barcode_reservations.check_label(etiket)["bindable"] is True

    def test_durdurma_oduncu_kapsamaz_hizmet_arasi_kapatir(self) -> None:
        """Metin kapsamı söyler; hizmet arası seçilmemişse ödünç gerçekten açıktır."""
        kitap, uyelik = odunc_nushasi(title="Durdurmada Ödünç"), uye()
        baslat(**durdurma_alanlari())
        odunc_ver(uyelik, kitap)
        assert tazele_nusha(kitap).status == CopyStatus.ON_LOAN
