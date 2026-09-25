"""Sayım — TMY 32 (F9 kod kapısı; tasarım §9-10, §9-11, §14.1 F9, D1/D4/D16/D17/D18).

Kapı maddeleri ve karşılıkları:

- 32/3 durdurması açıkken edinim, kayıttan düşme, devir ve dosya çözümü kapalı,
  ödünç açık; programa aktarım kapalı ama iletisi TMY'siz (K4); kayıp dosyasında bulunma
  açık (K1) → `TestTmyDurdurmasi`;
- hizmet arası açıkken yeni ödünç ve yeni teslim kapalı (madde 27) → `TestHizmetArasi`;
- onarımdaki nüsha için kurulun seçimi (K2), sınıf kitaplığında kayda göre alma yok
  (K3) → `TestTamamlama`;
- iade hiçbir durumda kapanmaz → `test_iade_hicbir_durumda_kilitlenmez`;
- onayda durumu değişen kalem düşülmez (D17) → `TestOnay`;
- 32/7 noksan düşümü, hasar düşümü 27/1 + 10/1-e, LOST uzlaştırma → `TestOnay`;
- anlık görüntü sayım sırasındaki değişikliklerden etkilenmez → `TestAnlikGoruntu`;
- D16 (sayım fazlasının kodu raf alanına yazılmaz) → `TestOkutma`, `TestOnay`;
- 34/1 dört büyüklük (A8) → `TestTmy341`.

Uç testleri `test_sayim_uclari.py`'dedir. Bütün kişi adları uydurmadır.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import (
    AcquisitionMethod,
    CaseResolution,
    CopyRepair,
    CopyStatus,
    CountBasis,
    Delivery,
    DeliveryStatus,
    StockTake,
    StockTakeFoundVia,
    StockTakeItem,
    StockTakeOutcome,
    StockTakeResult,
    StockTakeStatus,
    StockTakeWriteOffPath,
)
from apps.kutuphane.services import (
    barcode_reservations,
    catalog,
    circulation,
    deliveries,
    import_service,
    loss_damage,
    stocktake,
    tmy_kapisi,
    weeding,
)
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.ayiklama_ortak import (
    DEVRALAN_OKUL,
    kalem_ekle,
    onaya_kadar,
    raftaki,
    teklif,
)
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.ortak import edinim, eser, nusha
from apps.kutuphane.tests.sayim_ortak import (
    HARCAMA_YETKILISI,
    KURUL,
    baslat,
    durdurma_alanlari,
    kalem,
    okut,
    onayla,
    tamamla,
    taslak,
    tazele_sayim,
)
from apps.kutuphane.tests.teslim_ortak import (
    kademe_yaz,
    ogretmen,
    sube,
    tazele_dosya,
    tazele_nusha,
    teslim_et,
)
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db


def _durdurma_reddi(exc: pytest.ExceptionInfo[ValidationError]) -> bool:
    return "TMY 32/3 durdurması" in str(exc.value) and exc.value.code == tmy_kapisi.RED_KODU


def _aktarim_reddi(exc: pytest.ExceptionInfo[ValidationError]) -> bool:
    """K4 (b): programa aktarım durdurma süresince kapalı, ileti TMY'ye DAYANMAZ."""
    ileti = str(exc.value)
    return (
        tmy_kapisi.PROGRAMA_AKTARIM_MESSAGE in ileti
        and "TMY" not in ileti
        and "32/3" not in ileti
        and exc.value.code == tmy_kapisi.RED_KODU_AKTARIM
    )


def _gercek_edinim(**alanlar: Any) -> Any:
    """Gerçek taşınır girişi (Md. 10/5 yolu) — iletisi TMY 32/3'e dayanır."""
    return edinim(method=AcquisitionMethod.MINISTRY, **alanlar)


# ============================================================ taslak, kurul, başlatma


class TestTaslakVeBaslatma:
    def test_ayni_anda_tek_canli_sayim(self) -> None:
        taslak()
        with pytest.raises(ValidationError, match="Onaylanmamış bir sayım var"):
            taslak()

    def test_iptal_ya_da_onaydan_sonra_yeni_sayim_acilir(self) -> None:
        stocktake.cancel_stocktake(taslak())
        sayim = baslat()
        onayla(tamamla(sayim))
        assert taslak().status == StockTakeStatus.DRAFT

    @pytest.mark.parametrize(
        ("kurul", "alan"),
        [
            ({"committee_chair": ""}, "committee_chair"),
            ({"committee_property_officer": ""}, "committee_property_officer"),
            ({"committee_members": ""}, "committee_members"),
            # Aynı kişi iki kez yazılırsa bir sayılır (TR katlamalı).
            ({"committee_members": "DENEME KURULBAŞKANI"}, "committee_members"),
        ],
    )
    def test_kurul_en_az_uc_farkli_kisidir(self, kurul: dict[str, str], alan: str) -> None:
        with pytest.raises(ValidationError) as exc:
            baslat(**kurul)
        assert alan in exc.value.message_dict
        assert "32/2" in " ".join(exc.value.message_dict[alan])

    def test_kurul_ve_harcama_yetkilisi_adlari_sifreli_saklanir(self) -> None:
        sayim = baslat(**durdurma_alanlari())
        with connection.cursor() as imlec:
            imlec.execute(
                "SELECT committee_chair, committee_property_officer, committee_members, "
                "tmy_stop_by_name FROM kutuphane_stocktake WHERE id = %s",
                [sayim.pk],
            )
            ham = " ".join(imlec.fetchone())
        assert "Deneme" not in ham
        guncel = tazele_sayim(sayim)
        assert guncel.committee_chair == KURUL["committee_chair"]
        assert guncel.tmy_stop_by_name == HARCAMA_YETKILISI

    @pytest.mark.parametrize("eksik", ["tmy_stop_requested_on", "tmy_stop_by_name", "tmy_stop_on"])
    def test_durdurmada_kurul_talebi_ve_harcama_yetkilisi_zorunludur(self, eksik: str) -> None:
        alanlar = durdurma_alanlari()
        alanlar[eksik] = "" if eksik == "tmy_stop_by_name" else None
        with pytest.raises(ValidationError) as exc:
            baslat(**alanlar)
        assert eksik in exc.value.message_dict

    def test_durdurma_tarihi_talepten_once_ve_gelecekte_olamaz(self) -> None:
        bugun = timezone.localdate()
        alanlar = {**durdurma_alanlari(), "tmy_stop_on": bugun - timedelta(days=1)}
        with pytest.raises(ValidationError, match="talebinden önce olamaz"):
            baslat(**alanlar)
        stocktake.cancel_stocktake(StockTake.objects.get())
        with pytest.raises(ValidationError, match="bugünden sonra"):
            taslak(**{**durdurma_alanlari(), "tmy_stop_on": bugun + timedelta(days=1)})

    def test_durdurma_secilmezse_alanlari_bosalir_ve_istege_baglidir(self) -> None:
        sayim = taslak(**durdurma_alanlari())
        sayim = stocktake.update_stocktake(sayim, tmy_stop=False)
        assert (sayim.tmy_stop_requested_on, sayim.tmy_stop_by_name, sayim.tmy_stop_on) == (
            None,
            "",
            None,
        )
        assert stocktake.start_stocktake(sayim).status == StockTakeStatus.IN_PROGRESS

    def test_secenekler_ve_kurul_basladiktan_sonra_degismez(self) -> None:
        sayim = baslat()
        with pytest.raises(ValidationError, match="yalnız taslak"):
            stocktake.update_stocktake(sayim, service_pause=True)
        with pytest.raises(ValidationError, match="yalnız taslak"):
            stocktake.delete_stocktake(sayim)

    @pytest.mark.parametrize(
        ("alan", "deger"),
        [
            ("loan_basis", CountBasis.IN_PLACE),
            ("teacher_delivery_basis", CountBasis.IN_PLACE),
            ("section_delivery_basis", CountBasis.LIBRARY),
            # K3 (25.09.2026): sınıf kitaplığında "Kayda göre alınır" YOK.
            ("section_delivery_basis", CountBasis.BY_RECORD),
            # K2: onarımda yalnız "Sayımdan önce geri alınır" ya da "Kayda göre alınır".
            ("repair_basis", CountBasis.IN_PLACE),
            ("repair_basis", CountBasis.LIBRARY),
        ],
    )
    def test_kurul_secimi_kategoriye_gore(self, alan: str, deger: str) -> None:
        with pytest.raises(ValidationError) as exc:
            taslak(**{alan: deger})
        assert alan in exc.value.message_dict

    def test_mali_yil_baslangic_yilidir(self) -> None:
        assert baslat().fiscal_year == timezone.localdate().year


# ============================================================ anlık görüntü


class TestAnlikGoruntu:
    def test_kayitli_nushalari_ve_kurul_secimini_alir(self) -> None:
        rafta = odunc_nushasi(title="Raftaki")
        oduncte = odunc_ver(uye()).copy
        sinifta = (
            teslim_et([odunc_nushasi(title="Sınıftaki")], section=sube(10, "B")).deliveries[0].copy
        )
        ogretmende = teslim_et([odunc_nushasi(title="Öğretmendeki")], personnel=ogretmen())
        ogretmen_nushasi = ogretmende.deliveries[0].copy
        dusulen = raftaki("Ayıklanmış")
        batch = teklif()
        kalem_ekle(batch, dusulen)
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        silinen = odunc_nushasi(title="Yanlış Kayıt")
        catalog.delete_copy(silinen)

        sayim = baslat(loan_basis=CountBasis.COLLECT)

        kopyalar = set(StockTakeItem.objects.filter(stocktake=sayim).values_list("copy", flat=True))
        assert {rafta.pk, oduncte.pk, sinifta.pk, ogretmen_nushasi.pk} <= kopyalar
        assert dusulen.pk not in kopyalar and silinen.pk not in kopyalar
        assert kalem(sayim, rafta).basis == CountBasis.LIBRARY
        assert kalem(sayim, oduncte).basis == CountBasis.COLLECT
        sinif_kalemi = kalem(sayim, sinifta)
        assert (sinif_kalemi.basis, sinif_kalemi.delivery_kind) == (CountBasis.IN_PLACE, "SECTION")
        assert sinif_kalemi.class_section is not None
        assert sinif_kalemi.class_section.class_label == "10/B"
        assert kalem(sayim, ogretmen_nushasi).basis == CountBasis.BY_RECORD

    def test_sayim_sirasindaki_degisiklikler_anlik_goruntuyu_degistirmez(self) -> None:
        rafta = odunc_nushasi(title="Sonradan Ödünç")
        sayim = baslat()
        odunc_ver(uye(), rafta)
        yeni = odunc_nushasi(title="Sayımda Açılan")
        assert kalem(sayim, rafta).expected_status == CopyStatus.AVAILABLE
        assert not StockTakeItem.objects.filter(stocktake=sayim, copy=yeni).exists()
        sonuc = okut(sayim, yeni)[0]
        assert sonuc.code == stocktake.OKUTMA_KAPSAM_DISI
        assert not StockTakeItem.objects.filter(stocktake=sayim, copy__isnull=True).exists()


# ============================================================ TMY 32/3 durdurması (D4, D18)


class TestTmyDurdurmasi:
    def test_edinim_yeni_nusha_ve_bos_etiket_baglama_reddedilir(self) -> None:
        mevcut_edinim = _gercek_edinim()
        mevcut_eser = eser(title="Durdurmada Eser")
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        baslat(**durdurma_alanlari())

        with pytest.raises(ValidationError) as exc:
            _gercek_edinim()
        assert _durdurma_reddi(exc)
        assert "edinim ve yeni nüsha kaydı yapılamaz" in str(exc.value)
        with pytest.raises(ValidationError) as exc:
            catalog.create_copy(work=mevcut_eser, acquisition=mevcut_edinim)
        assert _durdurma_reddi(exc)
        with pytest.raises(ValidationError) as exc:
            barcode_reservations.bind_label(
                label=etiket, work=mevcut_eser, acquisition=mevcut_edinim
            )
        assert _durdurma_reddi(exc)

    def test_programa_aktarim_kapali_ama_iletisi_tmyye_dayanmaz(self) -> None:
        """K4 (b), 25.09.2026 ana oturum kararı: mevcut koleksiyonun programa aktarımı taşınır
        girişi değildir; durdurma süresince kapalı kalır, ileti TMY'ye dayandırılmaz."""
        aktarim_edinimi = edinim()  # "Mevcut koleksiyon (programa aktarım)"
        mevcut_eser = eser(title="Aktarımda Eser")
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        baslat(**durdurma_alanlari())

        with pytest.raises(ValidationError) as exc:
            edinim()
        assert _aktarim_reddi(exc)
        with pytest.raises(ValidationError) as exc:
            catalog.create_copy(work=mevcut_eser, acquisition=aktarim_edinimi)
        assert _aktarim_reddi(exc)
        with pytest.raises(ValidationError) as exc:
            barcode_reservations.bind_label(
                label=etiket, work=mevcut_eser, acquisition=aktarim_edinimi
            )
        assert _aktarim_reddi(exc)
        assert tmy_kapisi.PROGRAMA_AKTARIM_MESSAGE == (
            "Sayım sürerken programa aktarım yapılamaz; sayım bitince aktarın."
        )

    def test_ice_aktarim_bastan_reddedilir(self) -> None:
        """Programa aktarım (varsayılan yol) TMY'siz iletiyle, Md. 10/5 yolu TMY iletisiyle."""
        baslat(**durdurma_alanlari())
        bos = import_service.ParsedFile(rows=[])
        for islev in (import_service.preview_import, import_service.apply_import):
            with pytest.raises(ValidationError) as exc:
                islev(bos, payload_sha256="0" * 64)
            assert _aktarim_reddi(exc)
            with pytest.raises(ValidationError) as exc:
                islev(
                    bos,
                    payload_sha256="0" * 64,
                    spec=import_service.AcquisitionSpec(method=AcquisitionMethod.MINISTRY),
                )
            assert _durdurma_reddi(exc)

    def test_kayittan_dusme_ve_devir_uygulanamaz(self) -> None:
        batch = teklif()
        kitap = raftaki("Düşülecek")
        kalem_ekle(batch, kitap)
        onaya_kadar(batch)
        devir = teklif()
        devredilecek = raftaki("Devredilecek")
        kalem_ekle(devir, devredilecek, "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)
        onaya_kadar(devir)
        baslat(**durdurma_alanlari())
        with pytest.raises(ValidationError, match="kayıttan düşme yapılamaz"):
            weeding.apply_batch(batch)
        with pytest.raises(ValidationError, match="devir yapılamaz"):
            weeding.apply_batch(devir)
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE

    def test_kayip_bildirimi_ve_dosya_cozumu_kapali_bedel_onarim_ve_bulunma_acik(self) -> None:
        kademe_yaz("ORTAOGRETIM")
        kayip = loss_damage.report_lost(copy=odunc_nushasi(title="Kayıp"))
        temin = loss_damage.report_lost(copy=odunc_nushasi(title="Temin Edilecek"))
        bulunan_kitap = odunc_nushasi(title="Bulunan")
        bulunan = loss_damage.report_lost(copy=bulunan_kitap)
        hasarli = odunc_nushasi(title="Hasarlı")
        hasar = loss_damage.open_damage_case(copy=hasarli, send_to_repair=True)
        yeni_kayip = odunc_nushasi(title="Yeni Kayıp")
        baslat(**durdurma_alanlari())

        with pytest.raises(ValidationError) as exc:
            loss_damage.report_lost(copy=yeni_kayip)
        assert _durdurma_reddi(exc)
        with pytest.raises(ValidationError, match="kayıp/hasar dosyası çözümü"):
            loss_damage.resolve_case(temin, resolution=CaseResolution.REPLACED_SAME)
        with pytest.raises(ValidationError, match="32/3"):
            loss_damage.resolve_case(kayip, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        with pytest.raises(ValidationError, match="32/3"):
            loss_damage.resolve_case(hasar, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        # Kapsam dışı: bedel adımları ve onarım (F7 ekleri 17, 26) ve kayıp dosyasında kitabın
        # bulunması (K1 — rafa dönüş taşınır giriş-çıkışı değildir; nüsha kayıtta vardır).
        loss_damage.resolve_case(
            kayip, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("50")
        )
        loss_damage.resolve_case(hasar, resolution=CaseResolution.REPAIRED)
        assert tazele_nusha(hasarli).status == CopyStatus.AVAILABLE
        loss_damage.resolve_case(bulunan, resolution=CaseResolution.FOUND_RETURNED)
        assert tazele_nusha(bulunan_kitap).status == CopyStatus.AVAILABLE

    def test_odunc_ve_iade_acik(self) -> None:
        kitap, uyelik = odunc_nushasi(), uye()
        baslat(**durdurma_alanlari())
        odunc = odunc_ver(uyelik, kitap)
        circulation.return_copy(copy=odunc.copy)
        assert tazele_nusha(odunc.copy).status == CopyStatus.AVAILABLE

    def test_durdurma_secilmediyse_girisler_acik(self) -> None:
        baslat(service_pause=True)
        assert selectors_sayim.tmy_stop_active() is False
        nusha(eser(title="Açık Edinim"))

    def test_kilit_tamamlandida_surer_onayla_ve_iptalle_kalkar(self) -> None:
        """D17: "Tamamlandı" ile "Onaylandı" arasında boşluk yok."""
        sayim = baslat(**durdurma_alanlari())
        tamamla(sayim)
        with pytest.raises(ValidationError, match="32/3"):
            _gercek_edinim()
        with pytest.raises(ValidationError, match="programa aktarım"):
            edinim()
        onayla(sayim)
        _gercek_edinim()
        edinim()
        ikinci = baslat(**durdurma_alanlari())
        with pytest.raises(ValidationError, match="32/3"):
            _gercek_edinim()
        stocktake.cancel_stocktake(ikinci)
        _gercek_edinim()

    def test_taslakta_kilit_yoktur(self) -> None:
        taslak(**durdurma_alanlari(), service_pause=True)
        edinim()
        odunc_ver(uye())


# ============================================================ sayım için hizmet arası


class TestHizmetArasi:
    def test_yeni_odunc_ve_teslimi_durdurur(self) -> None:
        """Madde 27 (25.09.2026 kullanıcı kararı): hizmet arası yeni teslimi de durdurur;
        iade ve teslimden geri alma açık, edinim açık (hizmet arası TMY'ye dayanmaz)."""
        oduncteki = odunc_ver(uye())
        teslimdeki = teslim_et([odunc_nushasi(title="Sınıfta")]).deliveries[0]
        teslim_edilecek = odunc_nushasi(title="Yeni Teslim")
        baslat(service_pause=True)
        with pytest.raises(DolasimReddi) as exc:
            odunc_ver(uye())
        assert exc.value.code == circulation.RED_HIZMET_ARASI
        assert exc.value.message == (
            "Sayım için hizmet arası — yeni ödünç ve teslim yapılamıyor. İade ve teslimden "
            "geri alma açık."
        )
        with pytest.raises(DolasimReddi) as exc:
            teslim_et([teslim_edilecek])
        assert exc.value.code == circulation.RED_HIZMET_ARASI
        assert exc.value.message == circulation.SERVICE_PAUSE_MESSAGE
        assert tazele_nusha(teslim_edilecek).status == CopyStatus.AVAILABLE
        denetim = deliveries.delivery_check_scan(teslim_edilecek.barcode)
        assert denetim["result"] == deliveries.REDDEDILDI
        assert denetim["message"] == circulation.SERVICE_PAUSE_MESSAGE
        circulation.return_copy(copy=oduncteki.copy)
        deliveries.take_back(teslimdeki.copy)
        assert tazele_nusha(teslimdeki.copy).status == CopyStatus.AVAILABLE
        nusha(eser(title="Edinim Açık"))

    def test_gorevli_kipinde_de_anlasilir_ileti(self) -> None:
        uyelik = uye()
        kitap = odunc_nushasi()
        baslat(service_pause=True)
        KIP.gorevliye_gec()
        with pytest.raises(DolasimReddi) as exc:
            circulation.checkout(copy=kitap, membership=uyelik)
        assert exc.value.message == circulation.SERVICE_PAUSE_MESSAGE

    def test_tamamlandida_surer_onayla_kalkar(self) -> None:
        kitap = odunc_nushasi(title="Onaydan Sonra Teslim")
        sayim = baslat(service_pause=True)
        okut(sayim, kitap)
        tamamla(sayim)
        with pytest.raises(DolasimReddi):
            odunc_ver(uye())
        with pytest.raises(DolasimReddi):
            teslim_et([kitap])
        onayla(sayim)
        odunc_ver(uye())
        teslim_et([kitap])


@pytest.mark.parametrize("secenekler", [{}, {"service_pause": True}, "durdurma+ara"])
@pytest.mark.parametrize("asama", ["IN_PROGRESS", "COMPLETED"])
def test_iade_hicbir_durumda_kilitlenmez(secenekler: Any, asama: str) -> None:
    """Md. 23/1-c; D18: hiçbir seçenekte ve hiçbir aşamada iade ve geri alma durmaz."""
    alanlar: dict[str, Any] = (
        {**durdurma_alanlari(), "service_pause": True}
        if secenekler == "durdurma+ara"
        else secenekler
    )
    oduncler = [odunc_ver(uye()) for _ in range(2)]
    teslim = teslim_et([odunc_nushasi(title="Teslimde")]).deliveries[0]
    sayim = baslat(**alanlar)
    if asama == "COMPLETED":
        tamamla(sayim)
    circulation.return_copy(copy=oduncler[0].copy)
    circulation.return_loan(loan=oduncler[1])
    deliveries.take_back(teslim.copy)
    assert {tazele_nusha(o.copy).status for o in oduncler} == {CopyStatus.AVAILABLE}
    assert tazele_nusha(teslim.copy).status == CopyStatus.AVAILABLE


# ============================================================ okutma ve sayım fazlası


class TestOkutma:
    def test_bulundu_ve_ikinci_okutma_zararsizdir(self) -> None:
        kitap = odunc_nushasi()
        sayim = baslat()
        ilk, ikinci = stocktake.scan_many(
            sayim, [kitap.barcode, f"{kitap.barcode[:4]}-{kitap.barcode[4:]}"]
        )
        assert (ilk.code, ikinci.code) == (stocktake.OKUTMA_BULUNDU, stocktake.OKUTMA_ZATEN)
        bulunan = kalem(sayim, kitap)
        assert (bulunan.result, bulunan.found_via, bulunan.found_in_round) == (
            StockTakeResult.FOUND,
            StockTakeFoundVia.SCAN,
            1,
        )
        assert bulunan.scanned_at is not None

    def test_isbn_ve_uye_karti_reddedilir_kaydedilmez(self) -> None:
        uyelik = uye()
        sayim = baslat()
        isbn, kart, bos = stocktake.scan_many(sayim, ["9786050000009", uyelik.card_no, "  "])
        assert {isbn.code, kart.code, bos.code} == {stocktake.OKUTMA_GECERSIZ}
        assert kart.barcode == ""
        assert not StockTakeItem.objects.filter(stocktake=sayim, copy__isnull=True).exists()

    def test_sayim_fazlasi_kodu_yalniz_kalemde_durur(self) -> None:
        """D16: okutulan kod `surplus_barcode`'dadır; hiçbir nüsha alanına yazılmaz."""
        eski = raftaki("Ayıklanıp Rafta Kalan")
        batch = teklif()
        kalem_ekle(batch, eski)
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        aralik = barcode_reservations.reserve(2)
        bos, iptal = aralik.numbers.order_by("barcode")
        barcode_reservations.cancel_numbers(aralik, barcodes=[iptal.barcode])
        sayim = baslat()

        sonuclar = stocktake.scan_many(
            sayim, [eski.barcode, bos.barcode, iptal.barcode, "123456", "123456"]
        )
        assert [s.code for s in sonuclar] == [
            stocktake.OKUTMA_FAZLA,
            stocktake.OKUTMA_FAZLA,
            stocktake.OKUTMA_FAZLA,
            stocktake.OKUTMA_FAZLA,
            stocktake.OKUTMA_FAZLA_TEKRAR,
        ]
        fazla = sonuclar[0].item
        assert fazla is not None
        assert (fazla.surplus_barcode, fazla.surplus_copy_id, fazla.surplus_work_id) == (
            eski.barcode,
            eski.pk,
            eski.work_id,
        )
        assert sonuclar[3].item is not None and sonuclar[3].item.surplus_work is None
        assert "biçiminde değil" in sonuclar[3].message

    def test_kuyruk_en_cok_200_kod(self) -> None:
        sayim = baslat()
        with pytest.raises(ValidationError, match="en çok 200"):
            stocktake.scan_many(sayim, ["1"] * 201)

    def test_okutma_yalniz_suren_sayimda(self) -> None:
        sayim = taslak()
        with pytest.raises(ValidationError, match="yalnız süren sayımda"):
            okut(sayim, odunc_nushasi())

    def test_fazla_elle_eklenir_duzenlenir_ve_cikarilir(self) -> None:
        sayim = baslat()
        hedef = eser(title="Fazlanın Eseri")
        fazla = stocktake.add_surplus(sayim, note="Etiketsiz roman, 3. raf")
        assert fazla.result == StockTakeResult.SURPLUS and fazla.surplus_barcode == ""
        fazla = stocktake.update_surplus(fazla, work=hedef)
        assert fazla.surplus_work == hedef
        with pytest.raises(ValidationError, match="ikisi birden"):
            stocktake.update_surplus(fazla, work=hedef, excluded=True)
        fazla = stocktake.update_surplus(fazla, excluded=True, note="Öğretmenin kendi kitabı")
        assert (fazla.surplus_work, fazla.surplus_excluded) == (None, True)
        with pytest.raises(ValidationError, match="gerekçesini"):
            stocktake.update_surplus(fazla, note="")
        stocktake.remove_surplus(fazla)
        assert not StockTakeItem.objects.filter(stocktake=sayim, copy__isnull=True).exists()

    def test_dijital_eser_fazlaya_secilemez(self) -> None:
        sayim = baslat()
        fazla = stocktake.add_surplus(sayim, note="Bir kitap")
        with pytest.raises(ValidationError, match="nüsha açılamaz"):
            stocktake.update_surplus(fazla, work=eser(title="E", resource_type="EBOOK"))


# ============================================================ tamamlama (32/5, 32/6)


class TestTamamlama:
    def test_sayim_sirasinda_iade_edilen_nusha_bulundu_sayilir(self) -> None:
        odunc = odunc_ver(uye())
        teslim = teslim_et([odunc_nushasi(title="Geri Alınan")], personnel=ogretmen())
        sayim = baslat()
        circulation.return_copy(copy=odunc.copy)
        deliveries.take_back(teslim.deliveries[0].copy)
        ilerleme = selectors_sayim.progress(sayim)
        assert ilerleme["by_record_basis"] == 2  # kurul seçimi (kayda göre) anlık görüntüde
        tamamla(sayim)
        for kopya in (odunc.copy, teslim.deliveries[0].copy):
            bulunan = kalem(sayim, kopya)
            assert (bulunan.result, bulunan.found_via) == (
                StockTakeResult.FOUND,
                StockTakeFoundVia.RETURN,
            )

    def test_oduncteki_nusha_kayda_gore_toplanamayan_isaretlidir(self) -> None:
        kayda_gore = odunc_ver(uye())
        sayim_ = baslat()
        tamamla(sayim_)
        k = kalem(sayim_, kayda_gore.copy)
        assert (k.result, k.basis_fallback) == (StockTakeResult.BY_RECORD, False)
        onayla(sayim_)
        toplanamayan = odunc_ver(uye())
        ikinci = baslat(loan_basis=CountBasis.COLLECT)
        tamamla(ikinci)
        k = kalem(ikinci, toplanamayan.copy)
        assert (k.result, k.basis_fallback) == (StockTakeResult.BY_RECORD, True)

    def test_yerinde_sayilan_sinif_kitapligi_bulunmazsa_noksandir(self) -> None:
        sinifta, bulunan = teslim_et(
            [odunc_nushasi(title="Sınıfta Yok"), odunc_nushasi(title="Sınıfta Var")],
            section=sube(9, "C"),
        ).deliveries
        sayim = baslat()
        okut(sayim, bulunan.copy)
        ilerleme = selectors_sayim.progress(sayim)
        assert ilerleme["class_libraries"] == [
            {"class_section": sinifta.section_id, "label": "9/C", "expected": 2, "found": 1}
        ]
        tamamla(sayim)
        assert kalem(sayim, sinifta.copy).result == StockTakeResult.MISSING
        assert kalem(sayim, bulunan.copy).result == StockTakeResult.FOUND

    def test_sinif_kitapligi_toplanamayan_yerinde_aranir_bulunmazsa_noksandir(self) -> None:
        """K3 (25.09.2026): şubede "Kayda göre alınır" YOK; "Sayımdan önce toplanır"da geri
        alınamayan nüsha yerinde aranır — okutulmazsa noksandır (32/5 birinci cümle)."""
        geri_alinan, yerinde_bulunan, bulunmayan = teslim_et(
            [odunc_nushasi(title=ad) for ad in ("Geri Alınan", "Yerinde Bulunan", "Bulunmayan")],
            section=sube(11, "A"),
        ).deliveries
        sayim = baslat(section_delivery_basis=CountBasis.COLLECT)
        assert kalem(sayim, bulunmayan.copy).basis == CountBasis.COLLECT
        deliveries.take_back(geri_alinan.copy)
        okut(sayim, yerinde_bulunan.copy)
        tamamla(sayim)
        assert kalem(sayim, geri_alinan.copy).result == StockTakeResult.FOUND
        assert kalem(sayim, yerinde_bulunan.copy).result == StockTakeResult.FOUND
        k = kalem(sayim, bulunmayan.copy)
        assert (k.result, k.basis_fallback) == (StockTakeResult.MISSING, False)
        onayla(sayim)
        assert tazele_nusha(bulunmayan.copy).status == CopyStatus.WITHDRAWN_MISSING
        assert Delivery.objects.get(pk=bulunmayan.pk).status == DeliveryStatus.LOST_CONVERTED
        satir = next(
            s for s in selectors_sayim.basis_lines(sayim) if s["category"] == "section_delivery"
        )
        assert "yerinde aranır" in satir["dayanak"] and "kayda göre" not in satir["dayanak"]

    @pytest.mark.parametrize(
        ("secim", "etiket", "isaret"),
        [
            (CountBasis.BY_RECORD, "Kayda göre alınır — onarımda", False),
            (CountBasis.COLLECT, "Sayımdan önce geri alınır", True),
        ],
    )
    def test_onarimdaki_nusha_kurulun_secimiyle_kayda_gore_alinir(
        self, secim: str, etiket: str, isaret: bool
    ) -> None:
        """K2 (25.09.2026): okutulmayan onarımdaki nüsha noksan sayılmaz; "Sayımdan önce geri
        alınır"da geri alınamadığı işaretlenir. Sayım sırasında dönen bulunmuş sayılır."""
        onarimci, donen = odunc_nushasi(title="Onarımcıda"), odunc_nushasi(title="Dönen")
        for kopya in (onarimci, donen):
            loss_damage.send_to_repair(kopya)
        sayim = baslat(repair_basis=secim)
        assert kalem(sayim, onarimci).basis == secim
        loss_damage.return_from_repair(donen)
        tamamla(sayim)
        k = kalem(sayim, onarimci)
        assert (k.result, k.basis_fallback) == (StockTakeResult.BY_RECORD, isaret)
        assert kalem(sayim, donen).result == StockTakeResult.FOUND
        sonuc = onayla(sayim)
        assert sonuc.written_off == 0
        assert tazele_nusha(onarimci).status == CopyStatus.IN_REPAIR
        satir = next(s for s in selectors_sayim.category_lines(sayim) if s["category"] == "repair")
        assert (satir["label"], satir["basis_display"], satir["count"]) == (
            "Onarımdaki nüsha",
            etiket,
            2,
        )
        assert satir["results"][StockTakeResult.BY_RECORD] == 1
        assert satir["fallback"] == (1 if isaret else 0)
        assert "doğrudan hüküm yoktur" in satir["dayanak"] and "32/5" not in satir["dayanak"]

    def test_ilk_turda_noksan_varsa_ikinci_sayima_gecilir(self) -> None:
        """TMY 32/6: farklı çıkanların sayımı bir kez daha tekrarlanır."""
        bulunacak = odunc_nushasi(title="İkinci Turda Bulunan")
        kayip = odunc_nushasi(title="Bulunamayan")
        sayim = baslat()
        sonuc = stocktake.complete_stocktake(sayim)
        assert (sonuc.second_round, sonuc.missing) == (True, 2)
        guncel = tazele_sayim(sayim)
        assert (guncel.status, guncel.round) == (StockTakeStatus.IN_PROGRESS, 2)
        assert okut(guncel, bulunacak)[0].message == stocktake.SCAN_FOUND_ROUND2
        son = stocktake.complete_stocktake(guncel)
        assert (son.second_round, son.missing) == (False, 1)
        assert son.stocktake.status == StockTakeStatus.COMPLETED
        assert kalem(sayim, bulunacak).found_in_round == 2
        assert kalem(sayim, kayip).result == StockTakeResult.MISSING
        assert kalem(sayim, kayip).status_at_completion == CopyStatus.AVAILABLE

    def test_noksan_yoksa_dogrudan_tamamlanir(self) -> None:
        kitap = odunc_nushasi()
        sayim = baslat()
        okut(sayim, kitap)
        sonuc = stocktake.complete_stocktake(sayim)
        assert sonuc.second_round is False
        assert sonuc.stocktake.status == StockTakeStatus.COMPLETED

    def test_sayim_sirasinda_kayittan_cikan_ne_bulunan_ne_noksandir(self) -> None:
        kitap = raftaki("Sayımda Ayıklanan")
        batch = teklif()
        kalem_ekle(batch, kitap)
        onaya_kadar(batch)
        sayim = baslat()  # durdurma yok: ayıklama uygulanabilir
        weeding.apply_batch(batch)
        assert okut(sayim, kitap)[0].code == stocktake.OKUTMA_KAPSAM_DISI
        tamamla(sayim)
        assert kalem(sayim, kitap).result == StockTakeResult.EXITED


# ============================================================ onay (D17, 32/7, 27/1, TMY 17)


class TestOnay:
    def test_noksan_32_7_ile_kayittan_dusulur(self) -> None:
        noksan = odunc_nushasi(title="Noksan")
        onarimda = odunc_nushasi(title="Onarımda Noksan")
        sayim = baslat()
        # Sayım SIRASINDA onarıma gönderilen (anlık görüntüde rafta) ve okutulmayan nüsha
        # noksandır; onarımdaki nüshanın kurul seçimi yalnız anlık görüntüdekine uygulanır.
        loss_damage.send_to_repair(onarimda)
        sayim = tamamla(sayim)
        sonuc = onayla(sayim)
        assert sonuc.written_off == 2
        for kopya in (noksan, onarimda):
            k = kalem(sayim, kopya)
            assert (k.outcome, k.write_off_path) == (
                StockTakeOutcome.WRITTEN_OFF,
                StockTakeWriteOffPath.MISSING_32_7,
            )
            assert tazele_nusha(kopya).status == CopyStatus.WITHDRAWN_MISSING
        assert not CopyRepair.objects.filter(copy=onarimda, returned_on__isnull=True).exists()
        assert "32/7" in StockTakeWriteOffPath.MISSING_32_7.label

    def test_onayda_durumu_degisen_kalem_dusulmez(self) -> None:
        """D17: tamamlandıktan sonra bulunan ya da ödünç verilen nüsha noksan diye düşülmez."""
        kayip = odunc_nushasi(title="Sonradan Bulunan")
        dosya = loss_damage.report_lost(copy=kayip)
        rafta = odunc_nushasi(title="Sonradan Ödünç Verilen")
        sayim = tamamla(baslat())  # durdurma ve hizmet arası yok
        assert kalem(sayim, kayip).result == StockTakeResult.MISSING
        assert kalem(sayim, rafta).result == StockTakeResult.MISSING
        loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        odunc_ver(uye(), rafta)
        sonuc = onayla(sayim)
        assert (sonuc.state_changed, sonuc.written_off) == (2, 0)
        bulunan, oduncte = kalem(sayim, kayip), kalem(sayim, rafta)
        assert (bulunan.outcome, bulunan.result, bulunan.found_via) == (
            StockTakeOutcome.STATE_CHANGED,
            StockTakeResult.FOUND,
            StockTakeFoundVia.RETURN,
        )
        assert bulunan.outcome_note == "Onayda durumu: Rafta."
        assert (oduncte.outcome, oduncte.result) == (
            StockTakeOutcome.STATE_CHANGED,
            StockTakeResult.BY_RECORD,
        )
        assert tazele_nusha(kayip).status == CopyStatus.AVAILABLE
        assert tazele_nusha(rafta).status == CopyStatus.ON_LOAN

    def test_harcama_yetkilisinin_onaylamadigi_kalem_kayitta_kalir(self) -> None:
        kitap = odunc_nushasi(title="Onaylanmayan")
        sayim = tamamla(baslat())
        k = kalem(sayim, kitap)
        with pytest.raises(ValidationError, match="gerekçesini"):
            onayla(sayim, not_approved={k.pk: " "})
        with pytest.raises(ValidationError, match="yalnız noksan"):
            onayla(sayim, not_approved={999999: "x"})
        sonuc = onayla(sayim, not_approved={str(k.pk): "Ciltçide; dönüşü bekleniyor"})
        assert sonuc.not_approved == 1
        k = kalem(sayim, kitap)
        assert (k.outcome, k.outcome_note) == (
            StockTakeOutcome.NOT_APPROVED,
            "Ciltçide; dönüşü bekleniyor",
        )
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE

    def test_kayiptaki_nusha_bulunmazsa_kayip_olarak_dusulur_dosya_acik_kalir(self) -> None:
        kitap = odunc_nushasi(title="Kayıpta Kalan")
        dosya = loss_damage.report_lost(copy=kitap)
        sayim = tamamla(baslat())
        assert kalem(sayim, kitap).case_id == dosya.pk
        onayla(sayim)
        assert tazele_nusha(kitap).status == CopyStatus.WITHDRAWN_LOST
        dosya = tazele_dosya(dosya)
        assert dosya.is_open  # Md. 19 yükümlülüğü sürer
        izinli = loss_damage.allowed_resolutions(dosya)
        assert CaseResolution.FOUND_RETURNED not in izinli
        loss_damage.resolve_case(dosya, resolution=CaseResolution.REPLACED_SAME)
        assert tazele_nusha(kitap).status == CopyStatus.WITHDRAWN_LOST  # eski kayıt terminal

    def test_kayip_onerisi_noksanla_baglanir(self) -> None:
        """F8 ekleri 34: kayıp önerisi 32/7 noksan düşüm teklifine bağlanır."""
        kitap = odunc_nushasi(title="Kayıp Önerili")
        dosya = loss_damage.report_lost(copy=kitap)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        sayim = tamamla(baslat())
        k = kalem(sayim, kitap)
        assert (k.result, k.case_id) == (StockTakeResult.MISSING, dosya.pk)
        onayla(sayim)
        assert tazele_nusha(kitap).status == CopyStatus.WITHDRAWN_LOST
        assert loss_damage.oneri_geri_alinabilir(tazele_dosya(dosya)) is False

    def test_kayipta_gorunup_bulunan_nusha_uzlastirilir(self) -> None:
        """LOST uzlaştırma: okutulan kayıp nüshanın dosyası "Bulundu" ile kapanır."""
        uyelik = uye(ogrenci(first_name="Denemekayipsayim"))
        acik = odunc_ver(uyelik)
        acik_dosya = loss_damage.report_lost(copy=acik.copy)
        onerili = odunc_nushasi(title="Önerisi Olan")
        onerili_dosya = loss_damage.report_lost(copy=onerili)
        loss_damage.resolve_case(onerili_dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        sayim = baslat(**durdurma_alanlari())
        sonuclar = okut(sayim, acik.copy, onerili)
        assert {s.message for s in sonuclar} == {stocktake.SCAN_FOUND_LOST}
        sonuc = onayla(tamamla(sayim))
        assert sonuc.reconciled == 2
        for kopya, dosya in ((acik.copy, acik_dosya), (onerili, onerili_dosya)):
            assert tazele_nusha(kopya).status == CopyStatus.AVAILABLE
            assert tazele_dosya(dosya).resolution == CaseResolution.FOUND_RETURNED
            assert kalem(sayim, kopya).outcome == StockTakeOutcome.RECONCILED

    def test_hasar_onerisi_27_1_ile_komisyonsuz_dusulur(self) -> None:
        rafta = odunc_nushasi(title="Hasarlı Rafta")
        onarimda = odunc_nushasi(title="Hasarlı Onarımda")
        for kopya, onarim in ((rafta, False), (onarimda, True)):
            dosya = loss_damage.open_damage_case(copy=kopya, send_to_repair=onarim)
            loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        sayim = baslat()
        okut(sayim, rafta, onarimda)
        tamamla(sayim)
        assert kalem(sayim, rafta).damage_write_off and kalem(sayim, onarimda).damage_write_off
        sonuc = onayla(sayim)
        assert sonuc.damage_written_off == 2
        for kopya in (rafta, onarimda):
            k = kalem(sayim, kopya)
            assert (k.outcome, k.write_off_path) == (
                StockTakeOutcome.WRITTEN_OFF,
                StockTakeWriteOffPath.DAMAGE_27_1,
            )
            assert tazele_nusha(kopya).status == CopyStatus.WITHDRAWN_DAMAGED
        assert not CopyRepair.objects.filter(copy=onarimda, returned_on__isnull=True).exists()
        assert "27/1" in StockTakeWriteOffPath.DAMAGE_27_1.label
        assert "10/1-e" in StockTakeWriteOffPath.DAMAGE_27_1.label

    def test_hasar_onerisi_onayda_oduncteyse_dusulmez(self) -> None:
        kitap = odunc_nushasi(title="Hasarlı Ödünç")
        dosya = loss_damage.open_damage_case(copy=kitap)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        sayim = baslat()
        okut(sayim, kitap)
        tamamla(sayim)
        odunc_ver(uye(), kitap)  # hizmet arası yok: ödünç açık
        sonuc = onayla(sayim)
        assert (sonuc.damage_written_off, sonuc.state_changed) == (0, 1)
        assert tazele_nusha(kitap).status == CopyStatus.ON_LOAN

    def test_sayim_fazlasi_yeni_numarayla_kayda_girer(self) -> None:
        """TMY 17 + D16: fazla yeni numarayla girer, eski kod hiçbir alana yazılmaz."""
        eski = raftaki("Kayıttan Düşülüp Bulunan")
        batch = teklif()
        kalem_ekle(batch, eski)
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        sayim = baslat(**durdurma_alanlari())
        fazla = okut(sayim, eski)[0].item
        assert fazla is not None
        onay_gunu = timezone.localdate()
        sonuc = onayla(tamamla(sayim), approved_on=onay_gunu)
        assert sonuc.surplus_entered == 1
        fazla.refresh_from_db()
        yeni = fazla.created_copy
        assert yeni is not None and yeni.work_id == eski.work_id
        assert yeni.barcode != eski.barcode
        for alan in ("old_register_no", "external_asset_ref"):
            assert eski.barcode not in getattr(yeni, alan)
        assert yeni.acquisition.method == AcquisitionMethod.INVENTORY_FOUND
        assert yeni.acquisition.date == onay_gunu
        assert tazele_sayim(sayim).surplus_acquisition_id == yeni.acquisition_id
        assert tazele_nusha(eski).status == CopyStatus.WITHDRAWN_WEEDED  # eski kayıt terminal

    def test_bos_etiket_fazlasi_kendi_numarasiyla_baglanir(self) -> None:
        aralik = barcode_reservations.reserve(1)
        etiket = aralik.numbers.get().barcode
        hedef = eser(title="Etiketli Ama Kayıtsız")
        sayim = baslat()
        fazla = okut_kod(sayim, etiket)
        stocktake.update_surplus(fazla, work=hedef)
        onayla(tamamla(sayim))
        fazla.refresh_from_db()
        assert fazla.created_copy is not None and fazla.created_copy.barcode == etiket

    def test_cozulmemis_fazla_onayi_durdurur_kayda_alinmayan_gerekceli(self) -> None:
        sayim = baslat()
        fazla = stocktake.add_surplus(sayim, note="Kime ait olduğu belirsiz kitap")
        tamamla(sayim)
        with pytest.raises(ValidationError, match="1 sayım fazlası"):
            onayla(sayim)
        stocktake.update_surplus(fazla, excluded=True)
        sonuc = onayla(sayim)
        assert (sonuc.surplus_entered, sonuc.surplus_excluded) == (0, 1)
        assert tazele_sayim(sayim).surplus_acquisition is None

    def test_onay_harcama_yetkilisi_ve_tarih_kurallari(self) -> None:
        sayim = tamamla(baslat())
        bugun = timezone.localdate()
        with pytest.raises(ValidationError, match="10/1-e"):
            onayla(sayim, approved_by_name="  ")
        with pytest.raises(ValidationError, match="bugünden sonra"):
            onayla(sayim, approved_on=bugun + timedelta(days=1))
        with pytest.raises(ValidationError, match="10/1-a"):
            onayla(sayim, approved_on=bugun - timedelta(days=1))
        onayla(sayim)
        guncel = tazele_sayim(sayim)
        assert guncel.status == StockTakeStatus.APPROVED and guncel.open_slot is None
        with pytest.raises(ValidationError, match="Yalnız tamamlanmış"):
            onayla(sayim)

    def test_suren_sayimdaki_ve_fazladan_acilan_nusha_silinemez(self) -> None:
        kitap = odunc_nushasi(title="Sayılan")
        sayim = baslat()
        with pytest.raises(ValidationError, match="Süren sayımda"):
            catalog.delete_copy(kitap)
        fazla = stocktake.add_surplus(sayim, note="Etiketsiz", work=eser(title="Fazla Eser"))
        okut(sayim, kitap)
        onayla(tamamla(sayim))
        fazla.refresh_from_db()
        assert fazla.created_copy is not None
        with pytest.raises(ValidationError, match="sayım fazlası olarak kayda alındı"):
            catalog.delete_copy(fazla.created_copy)
        catalog.delete_copy(tazele_nusha(kitap))  # onaydan sonra silinebilir


# ============================================================ iptal


class TestIptal:
    def test_iptal_kilitleri_kaldirir_anlik_goruntu_kalir(self) -> None:
        kitap = odunc_nushasi()
        sayim = baslat(**durdurma_alanlari(), service_pause=True)
        okut(sayim, kitap)
        iptal = stocktake.cancel_stocktake(sayim, reason="Kurul değişti")
        assert (iptal.status, iptal.open_slot, iptal.cancel_reason) == (
            StockTakeStatus.CANCELLED,
            None,
            "Kurul değişti",
        )
        assert kalem(sayim, kitap).result == StockTakeResult.FOUND
        edinim()
        odunc_ver(uye())
        with pytest.raises(ValidationError, match="iptal edilemez"):
            stocktake.cancel_stocktake(sayim)


# ============================================================ kip


def test_gorevli_kipinde_yalniz_okutma_yapilir() -> None:
    """Madde 24 (25.09.2026 kullanıcı kararı): görevli kipinde okutma açık; başlatma,
    tamamlama, onay, iptal ve fazla işleri yönetici kipinde kalır."""
    kitap = odunc_nushasi(title="Görevlinin Okuttuğu")
    sayim = baslat()
    KIP.gorevliye_gec()
    sonuc = stocktake.scan_many(sayim, [kitap.barcode])[0]
    assert sonuc.code == stocktake.OKUTMA_BULUNDU
    assert kalem(sayim, kitap).found_via == StockTakeFoundVia.SCAN
    for cagri in (
        lambda: stocktake.create_stocktake(),
        lambda: stocktake.update_stocktake(sayim, notes="x"),
        lambda: stocktake.start_stocktake(sayim),
        lambda: stocktake.add_surplus(sayim, note="Etiketsiz"),
        lambda: stocktake.complete_stocktake(sayim),
        lambda: stocktake.approve_stocktake(sayim, approved_by_name="x", approved_on=None),
        lambda: stocktake.cancel_stocktake(sayim),
    ):
        with pytest.raises(KipYetkisiz):
            cagri()


# ============================================================ TMY 34/1 (A8 kararı)


class TestTmy341:
    def test_dort_buyukluk_ve_gelecek_yila_devir_sayimda_bulunandir(self) -> None:
        yil = timezone.localdate().year
        onceki = date(yil - 1, 5, 1)
        eski_parti = edinim(date=onceki)  # mevcut koleksiyon, önceki yılda programda
        devir_bulunan = nusha(eser(title="Devir Bulunan"), eski_parti)
        devir_noksan = nusha(eser(title="Devir Noksan"), eski_parti)
        ayiklanan = nusha(eser(title="Devir Ayıklanan"), eski_parti)
        aktarim = nusha(eser(title="Aktarım"), edinim(date=date(yil, 1, 15)))
        satin = nusha(
            eser(title="Satın Alma"),
            edinim(method=AcquisitionMethod.PURCHASE, date=date(yil, 2, 1)),
        )
        batch = teklif()
        kalem_ekle(batch, ayiklanan)
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        sayim = baslat()
        okut(sayim, devir_bulunan, aktarim, satin)
        fazla = stocktake.add_surplus(sayim, note="Etiketsiz", work=eser(title="Fazla"))
        assert fazla is not None
        oncesi = selectors_sayim.tmy_34_1(sayim)
        assert oncesi["next_year_carryover"] is None and oncesi["count_final"] is False
        onayla(tamamla(sayim))

        sayilar = selectors_sayim.tmy_34_1(tazele_sayim(sayim))
        assert sayilar["fiscal_year"] == yil
        assert sayilar["previous_year_carryover"] == 3  # bulunan + noksan + ayıklanan
        assert sayilar["program_transfer"] == 1
        assert sayilar["entered_by_method"][AcquisitionMethod.PURCHASE] == 1
        assert sayilar["entered_by_method"][AcquisitionMethod.INVENTORY_FOUND] == 1
        assert sayilar["entered"] == 2
        assert sayilar["exited_by_status"][CopyStatus.WITHDRAWN_WEEDED] == 1
        assert sayilar["exited_by_status"][CopyStatus.WITHDRAWN_MISSING] == 1
        assert sayilar["exited"] == 2
        # Kayda göre yıl sonu = devir + aktarım + giren − çıkan; sayımda bulunana eşit (10/1-ğ).
        assert sayilar["year_end_by_record"] == 3 + 1 + 2 - 2 == 4
        assert sayilar["next_year_carryover"] == 4
        assert sayilar["difference"] == 0
        assert (sayilar["surplus"], sayilar["missing"], sayilar["missing_written_off"]) == (1, 1, 1)
        assert "Taşınır Sayım ve Döküm Cetveli değildir" in sayilar["note"]
        assert devir_noksan.pk in {
            k.copy_id for k in StockTakeItem.objects.filter(result=StockTakeResult.MISSING)
        }

    def test_odunc_ve_teslim_sayilisi_ayri_satirlarda(self) -> None:
        odunc_ver(uye())
        teslim_et([odunc_nushasi(title="Şubede")], section=sube(9, "D"))
        teslim_et([odunc_nushasi(title="Öğretmende")], personnel=ogretmen())
        sayim = baslat()
        satirlar = {s["category"]: s for s in selectors_sayim.category_lines(sayim)}
        assert {k: s["count"] for k, s in satirlar.items()} == {
            "loan": 1,
            "section_delivery": 1,
            "teacher_delivery": 1,
            "repair": 0,
        }
        assert "32/5'e kıyasen; 23/4" in satirlar["loan"]["dayanak"]
        assert "32/5 birinci cümleye kıyasen" in satirlar["section_delivery"]["dayanak"]
        assert "32/5 ikinci cümle" in satirlar["teacher_delivery"]["dayanak"]
        assert "doğrudan hüküm yoktur" in satirlar["repair"]["dayanak"]

    def test_gelecek_yila_devirden_onayda_27_1_ile_dusulen_cikarilir(self) -> None:
        """Madde 25 (a), 25.09.2026: sayımda bulunup onayda hasar nedeniyle (27/1) düşülen
        nüsha gelecek yıla devirden çıkarılır ve ayrı satırda gösterilir; sayımda bulunan
        miktar değişmez. Onaylanmayan noksan kayıtta kalır (fark +1)."""
        yil = timezone.localdate().year
        eski_parti = edinim(date=date(yil - 1, 5, 1))
        bulunan = nusha(eser(title="Devir Bulunan"), eski_parti)
        hasarli = nusha(eser(title="Devir Hasarlı"), eski_parti)
        noksan = nusha(eser(title="Devir Noksan"), eski_parti)
        dosya = loss_damage.open_damage_case(copy=hasarli)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        sayim = baslat()
        okut(sayim, bulunan, hasarli)
        sayim = tamamla(sayim)
        # Onaydan önce: sayımda bulunan kesin, devir hasar önerisi onaylanınca yazılır.
        oncesi = selectors_sayim.tmy_34_1(sayim)
        assert (oncesi["found_quantity"], oncesi["damage_pending"]) == (2, 1)
        assert oncesi["carryover_final"] is False and oncesi["next_year_carryover"] is None
        noksan_kalemi = kalem(sayim, noksan)
        onayla(sayim, not_approved={noksan_kalemi.pk: "Kitap okulda aranıyor."})

        sayilar = selectors_sayim.tmy_34_1(tazele_sayim(sayim))
        assert tazele_nusha(hasarli).status == CopyStatus.WITHDRAWN_DAMAGED
        assert sayilar["found_quantity"] == 2  # sayımda bulunan miktar değişmez
        assert sayilar["damage_written_off"] == 1
        assert sayilar["next_year_carryover"] == 2 - 1
        assert sayilar["year_end_by_record"] == 3 - 1  # hasarlı çıktı, noksan kayıtta
        assert sayilar["difference"] == 1  # yalnız onaylanmayan noksan


# ============================================================ tutanak satırları (E10 verisi)


def test_iki_secenek_ve_iade_ayri_satirlarda() -> None:
    sayim = taslak(**durdurma_alanlari(), service_pause=True, service_pause_decision="2026/15")
    satirlar = selectors_sayim.options_lines(sayim)
    assert [s["key"] for s in satirlar] == ["tmy_32_3", "service_pause", "return"]
    durdurma, hizmet, iade = satirlar
    assert durdurma["basis"] == "TMY 32/3" and "edinim" in durdurma["text"]
    assert "TMY 32/3 ikinci cümle" in hizmet["basis"] and "2026/15" in hizmet["text"]
    # Madde 27: tutanağın seçenek satırı teslimi de söyler.
    assert "yeni ödünç ve teslim durdurulur" in hizmet["text"]
    assert "teslimden geri alma açıktır" in hizmet["text"]
    assert "23/1-c" in iade["basis"]
    # Kişi adı satırlara girmez.
    assert all(HARCAMA_YETKILISI not in s["text"] for s in satirlar)


def test_kalem_verisinde_odunc_alanin_kimligi_yoktur() -> None:
    from apps.kutuphane.serializers_sayim import StockTakeItemSerializer

    uyelik = uye(ogrenci(first_name="Denemesayimodunc", last_name="Kimlikyok"))
    odunc = odunc_ver(uyelik)
    teslim_et([odunc_nushasi(title="Öğretmende")], personnel=ogretmen(first_name="Denemeogrt"))
    sayim = tamamla(baslat())
    metin = str(
        StockTakeItemSerializer(StockTakeItem.objects.filter(stocktake=sayim), many=True).data
    ) + str(selectors_sayim.tmy_34_1(sayim))
    for yasak in ("Denemesayimodunc", "Kimlikyok", "Denemeogrt", uyelik.card_no):
        assert yasak not in metin
    assert kalem(sayim, odunc.copy).result == StockTakeResult.BY_RECORD


# ---------------------------------------------------------------------------
# Küçük yardımcılar
# ---------------------------------------------------------------------------
def okut_kod(sayim: StockTake, kod: str) -> StockTakeItem:
    sonuc = stocktake.scan_many(sayim, [kod])[0]
    assert sonuc.item is not None, sonuc.message
    return sonuc.item
