"""Ayıklama servisleri (F8 — Md. 12/1, D7, D14, D15; tasarım §10 E7, §14.1 F8 kod kapısı).

Kod kapısı maddeleri bu dosyadadır:

- **TMY yol eşlemesi testi (tablonun her satırı)** — `TestE7Tablosu`: servis VE DB
  kısıtı 4 gerekçe × 4 yolun her birleşimini sınar.
- **Devir yalnız düzeye uygunsuzlukla, düzeye uygunsuzluk yalnız devirle** ve
  **10/1-b gerekçeli kalem 28 yoluna gidemez** — `TestE7Tablosu`.
- **Nadir eser ayıklanamaz** (D14) ve **açık ödünç/teslim/dosyalı nüsha
  ayıklanamaz** — `TestAyiklamaEngelleri` (ekleme anında ve uygulamada yeniden).
- **D15** (kalem silme, teklifi geri çekme) ve **D7** (karar türü) — `TestDurumMakinesi`.

Nüsha durumunun katalogdaki karşılığı (§5.10-4/5 — kayıttan düşülmüş ve
devredilmiş nüsha görünmez) `katalog/tests/`'tedir.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.models import (
    WEEDING_PATHS,
    CommissionDecisionType,
    CopyStatus,
    WeedingBatch,
    WeedingBatchStatus,
    WeedingItem,
    WeedingItemState,
)
from apps.kutuphane.services import (
    catalog,
    commissions,
    loss_damage,
    tmy_kapisi,
    weeding,
)
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.ayiklama_ortak import (
    DEVRALAN_OKUL,
    HARCAMA_YETKILISI,
    TMY_KOMISYONU,
    ayiklama_karari,
    kalem_ekle,
    onaya_kadar,
    raftaki,
    tazele,
    teklif,
)
from apps.kutuphane.tests.dolasim_ortak import odunc_ver, uye
from apps.kutuphane.tests.ortak import karar
from apps.kutuphane.tests.sayim_ortak import kapi_kaydi
from apps.kutuphane.tests.teslim_ortak import teslim_et
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db

GEREKCELER = ("WORN", "OBSOLETE", "LEVEL_MISMATCH", "CRITERIA_MISMATCH")
YOLLAR = ("TMY_27", "TMY_28", "TMY_24_2", "TMY_31")
#: Tasarım §10 E7 tablosu — elle yazılmış beklenti (model sabitinden TÜRETİLMEZ).
E7_BEKLENEN: dict[str, set[str]] = {
    "WORN": {"TMY_27", "TMY_28"},
    "OBSOLETE": {"TMY_28"},
    "LEVEL_MISMATCH": {"TMY_24_2", "TMY_31"},
    "CRITERIA_MISMATCH": {"TMY_28"},
}
BIRLESIMLER = [(g, y) for g in GEREKCELER for y in YOLLAR]


def _alanlar(gerekce: str, yol: str) -> dict[str, Any]:
    """Birleşimin geçerli olabilmesi için gereken yan alanlar (ölçüt, kurum)."""
    alanlar: dict[str, Any] = {"reason": gerekce, "tmy_path": yol}
    if gerekce == "CRITERIA_MISMATCH":
        alanlar["criterion"] = "10_1_A"
    if yol in ("TMY_24_2", "TMY_31"):
        alanlar["transfer_target"] = DEVRALAN_OKUL
    return alanlar


# ================================================================ E7 tablosu (kod kapısı)


class TestE7Tablosu:
    def test_tablo_tasarimdaki_e7_tablosuyla_birebir(self) -> None:
        assert {g: set(y) for g, y in WEEDING_PATHS.items()} == E7_BEKLENEN
        # Devir yolları YALNIZ düzeye uygunsuzlukta, düzeye uygunsuzluk YALNIZ devirde.
        devir = {"TMY_24_2", "TMY_31"}
        for gerekce, yollar in E7_BEKLENEN.items():
            if gerekce == "LEVEL_MISMATCH":
                assert yollar == devir
            else:
                assert not (yollar & devir)

    @pytest.mark.parametrize(("gerekce", "yol"), BIRLESIMLER)
    def test_servis_her_birlesimi_tabloya_gore_kabul_ya_da_reddeder(
        self, gerekce: str, yol: str
    ) -> None:
        batch = teklif()
        kitap = raftaki()
        if yol in E7_BEKLENEN[gerekce]:
            kalem = weeding.add_items(batch, copy_ids=[kitap.pk], **_alanlar(gerekce, yol))[0]
            assert (kalem.reason, kalem.tmy_path) == (gerekce, yol)
        else:
            with pytest.raises(ValidationError) as hata:
                weeding.add_items(batch, copy_ids=[kitap.pk], **_alanlar(gerekce, yol))
            assert "tmy_path" in hata.value.message_dict
            assert not WeedingItem.objects.exists()

    @pytest.mark.parametrize(("gerekce", "yol"), BIRLESIMLER)
    def test_db_kisiti_her_birlesimi_tabloya_gore_kabul_ya_da_reddeder(
        self, gerekce: str, yol: str
    ) -> None:
        """Servis atlansa da (ham `create`) tablo dışı çift yazılamaz."""
        batch = teklif()
        kitap = raftaki()
        alanlar = _alanlar(gerekce, yol)
        if yol in E7_BEKLENEN[gerekce]:
            WeedingItem.objects.create(batch=batch, copy=kitap, **alanlar)
        else:
            with pytest.raises(IntegrityError), transaction.atomic():
                WeedingItem.objects.create(batch=batch, copy=kitap, **alanlar)

    def test_10_1_b_gerekceli_kalem_28_yoluna_gidemez(self) -> None:
        batch = teklif()
        kitap = raftaki()
        # (a) Düzeye uygunsuzluk (12/1-c + 10/1-b) hurdaya ayırma yoluna gidemez.
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(
                batch, copy_ids=[kitap.pk], reason="LEVEL_MISMATCH", tmy_path="TMY_28"
            )
        assert weeding.LEVEL_ONLY_TRANSFER_MESSAGE in hata.value.message_dict["tmy_path"]
        # (b) 10/1-b "10. madde ölçütü" gerekçesiyle de 28'e sokulamaz.
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(
                batch,
                copy_ids=[kitap.pk],
                reason="CRITERIA_MISMATCH",
                criterion="10_1_B",
                tmy_path="TMY_28",
            )
        assert weeding.CRITERION_AGE_LEVEL_MESSAGE in hata.value.message_dict["criterion"]
        # (c) DB kısıtı da iki yolu keser.
        for alanlar in (
            {"reason": "LEVEL_MISMATCH", "tmy_path": "TMY_28"},
            {"reason": "CRITERIA_MISMATCH", "criterion": "10_1_B", "tmy_path": "TMY_28"},
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                WeedingItem.objects.create(batch=batch, copy=kitap, **alanlar)
        assert not WeedingItem.objects.exists()

    def test_varsayilan_yol_tablonun_ilk_yoludur(self) -> None:
        batch = teklif()
        yipranmis = kalem_ekle(batch, raftaki("Yıpranmış"), "WORN")
        duzey = kalem_ekle(
            batch, raftaki("Düzeye Uygun Değil"), "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL
        )
        eski = kalem_ekle(batch, raftaki("Eskimiş Bilgi"), "OBSOLETE")
        assert (yipranmis.tmy_path, duzey.tmy_path, eski.tmy_path) == (
            "TMY_27",
            "TMY_24_2",
            "TMY_28",
        )

    def test_devir_yalniz_duzeye_uygunsuzlukla(self) -> None:
        batch = teklif()
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(batch, copy_ids=[raftaki().pk], reason="WORN", tmy_path="TMY_31")
        assert weeding.TRANSFER_ONLY_LEVEL_MESSAGE in hata.value.message_dict["tmy_path"]

    def test_olcut_yalniz_12_1_ch_kaleminde_ve_zorunlu(self) -> None:
        batch = teklif()
        with pytest.raises(ValidationError, match="Ölçüt yalnız"):
            weeding.add_items(batch, copy_ids=[raftaki().pk], reason="WORN", criterion="10_1_A")
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(batch, copy_ids=[raftaki().pk], reason="CRITERIA_MISMATCH")
        assert "criterion" in hata.value.message_dict
        kalem = kalem_ekle(batch, raftaki(), "CRITERIA_MISMATCH", criterion="10_4")
        assert (kalem.criterion, kalem.tmy_path) == ("10_4", "TMY_28")

    def test_devralacak_kurum_yalniz_devirde(self) -> None:
        batch = teklif()
        with pytest.raises(ValidationError, match="yalnız devirde"):
            weeding.add_items(
                batch, copy_ids=[raftaki().pk], reason="WORN", transfer_target=DEVRALAN_OKUL
            )

    def test_gerekce_degisince_uymayan_yol_varsayilana_doner_kurum_temizlenir(self) -> None:
        batch = teklif()
        kalem = kalem_ekle(batch, raftaki(), "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)
        guncel = weeding.update_item(kalem, reason="WORN")
        assert (guncel.tmy_path, guncel.transfer_target) == ("TMY_27", "")
        guncel = weeding.update_item(guncel, tmy_path="TMY_28")
        assert guncel.tmy_path == "TMY_28"
        with pytest.raises(ValidationError):
            weeding.update_item(guncel, tmy_path="TMY_24_2")


# ============================================================ engeller (D14 + açık kayıt)


class TestAyiklamaEngelleri:
    def _engel(self, kitap: Any) -> str:
        batch = teklif()
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(batch, copy_ids=[kitap.pk], reason="WORN")
        (ileti,) = hata.value.message_dict["barcodes"]
        return ileti

    def test_nadir_eser_ayiklanamaz(self) -> None:
        kitap = raftaki(is_rare_or_manuscript=True)
        assert weeding.RARE_MESSAGE in self._engel(kitap)
        assert tazele(kitap).status == CopyStatus.AVAILABLE

    def test_teklif_surerken_nadir_isaretlenen_nusha_uygulanmaz(self) -> None:
        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap)
        onaya_kadar(batch)
        catalog.update_copy(tazele(kitap), is_rare_or_manuscript=True)

        with pytest.raises(ValidationError) as hata:
            weeding.apply_batch(batch)
        assert weeding.RARE_MESSAGE in hata.value.message_dict["items"][0]
        assert tazele(kitap).status == CopyStatus.AVAILABLE
        assert WeedingBatch.objects.get(pk=batch.pk).status == WeedingBatchStatus.APPROVED

    def test_oduncteki_nusha_ayiklanamaz(self) -> None:
        kitap = odunc_ver(uye()).copy
        assert weeding.ON_LOAN_MESSAGE in self._engel(kitap)

    def test_teslimdeki_nusha_ayiklanamaz(self) -> None:
        kitap = raftaki()
        teslim_et([kitap])
        assert weeding.DELIVERED_MESSAGE in self._engel(tazele(kitap))

    def test_cozulmemis_dosyali_nusha_ayiklanamaz(self) -> None:
        kitap = raftaki()
        loss_damage.open_damage_case(copy=kitap)
        assert tazele(kitap).status == CopyStatus.AVAILABLE  # dosya dolaşımdan çıkarmaz
        assert weeding.OPEN_CASE_MESSAGE in self._engel(tazele(kitap))

    def test_onarimdaki_nusha_once_onarimdan_doner(self) -> None:
        kitap = raftaki()
        loss_damage.send_to_repair(kitap)
        assert weeding.IN_REPAIR_MESSAGE in self._engel(tazele(kitap))

    def test_kayip_nusha_ayiklamaya_konmaz(self) -> None:
        kitap = raftaki()
        loss_damage.report_lost(copy=kitap)
        assert weeding.LOST_MESSAGE in self._engel(tazele(kitap))

    def test_baska_suren_teklifteki_nusha_eklenemez_iptalden_sonra_eklenir(self) -> None:
        kitap = raftaki()
        ilk = teklif()
        kalem_ekle(ilk, kitap)
        assert weeding.OTHER_BATCH_MESSAGE in self._engel(kitap)

        weeding.cancel_batch(ilk, reason="Yanlış liste")
        ikinci = teklif()
        assert kalem_ekle(ikinci, kitap).batch_id == ikinci.pk

    def test_ayni_teklife_iki_kez_eklenemez(self) -> None:
        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap)
        with pytest.raises(ValidationError, match="zaten var"):
            kalem_ekle(batch, kitap)

    def test_toplu_ekleme_tek_islemdir(self) -> None:
        batch = teklif()
        iyi = [raftaki(f"İyi {i}") for i in range(3)]
        kotu = raftaki("Nadir", is_rare_or_manuscript=True)
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(batch, copy_ids=[c.pk for c in [*iyi, kotu]], reason="WORN")
        assert len(hata.value.message_dict["barcodes"]) == 1
        assert not WeedingItem.objects.filter(batch=batch).exists()

    def test_okutmayla_ekleme_ham_kodu_yankilamaz(self) -> None:
        batch = teklif()
        kitap = raftaki()
        eklenen = weeding.add_items(batch, barcodes=[kitap.barcode, kitap.barcode], reason="WORN")
        assert len(eklenen) == 1  # tekrar okutma bir kez sayılır
        with pytest.raises(ValidationError) as hata:
            weeding.add_items(batch, barcodes=["12345678"], reason="WORN")
        assert "12345678" not in str(hata.value)

    def test_onaydan_sonra_odunc_verilen_nusha_uygulamayi_durdurur_hicbiri_dusulmez(
        self,
    ) -> None:
        """Teklif ≠ onay: nüsha uygulamaya dek rafta ve ödünç verilebilir kalır."""
        batch = teklif()
        kitaplar = [raftaki(f"Eser {i}") for i in range(3)]
        weeding.add_items(batch, copy_ids=[c.pk for c in kitaplar], reason="WORN")
        onaya_kadar(batch)
        odunc_ver(uye(), tazele(kitaplar[1]))

        with pytest.raises(ValidationError) as hata:
            weeding.apply_batch(batch)
        assert weeding.ON_LOAN_MESSAGE in hata.value.message_dict["items"][0]
        durumlar = [tazele(c).status for c in kitaplar]
        assert durumlar == [CopyStatus.AVAILABLE, CopyStatus.ON_LOAN, CopyStatus.AVAILABLE]


# ================================================================ durum makinesi (D15)


class TestDurumMakinesi:
    def test_tam_akis_kayittan_dusme_ve_devir(self) -> None:
        batch = teklif(notes="Ağustos ayıklaması")
        yipranmis = raftaki("Yıpranmış")
        duzey = raftaki("Düzeye Uygun Değil")
        kalem_ekle(batch, yipranmis, "WORN")
        kalem_ekle(batch, duzey, "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)

        weeding.submit_batch(batch)
        assert tazele(yipranmis).status == CopyStatus.AVAILABLE
        weeding.bind_decision(batch, commission_decision=ayiklama_karari())
        weeding.approve_batch(
            batch, approved_by_name=HARCAMA_YETKILISI, approved_on=timezone.localdate()
        )
        assert tazele(yipranmis).status == CopyStatus.AVAILABLE  # teklif ≠ onay
        sonuc = weeding.apply_batch(batch)

        assert (sonuc.withdrawn, sonuc.transferred) == (1, 1)
        assert tazele(yipranmis).status == CopyStatus.WITHDRAWN_WEEDED
        assert tazele(duzey).status == CopyStatus.TRANSFERRED
        guncel = WeedingBatch.objects.get(pk=batch.pk)
        assert guncel.status == WeedingBatchStatus.APPLIED and guncel.applied_at is not None
        assert set(guncel.items.values_list("state", flat=True)) == {WeedingItemState.APPLIED}
        # Terminal durumlar yumuşak silme DEĞİLDİR: nüsha kayıt defterinde kalır.
        assert tazele(yipranmis).deleted_at is None

    def test_kalem_silme_yalniz_taslakta(self) -> None:
        batch = teklif()
        silinecek = kalem_ekle(batch, raftaki("Silinecek"))
        kalan = kalem_ekle(batch, raftaki("Kalan"))
        weeding.remove_item(silinecek)
        assert list(selectors_ayiklama.batch_items(batch)) == [kalan]
        assert WeedingItem.all_objects.get(pk=silinecek.pk).deleted_at is not None

        weeding.submit_batch(batch)
        with pytest.raises(ValidationError, match="yalnız taslak"):
            weeding.remove_item(kalan)

    def test_teklifi_geri_cekmek_taslaga_ve_temiz_hale_dondurur(self) -> None:
        batch = teklif()
        birinci = kalem_ekle(batch, raftaki("Birinci"))
        ikinci = kalem_ekle(batch, raftaki("İkinci"))
        weeding.submit_batch(batch)
        weeding.bind_decision(
            batch,
            commission_decision=ayiklama_karari(),
            kept={ikinci.pk: "Komisyon onarılmasına karar verdi."},
        )
        weeding.approve_batch(
            batch,
            approved_by_name=HARCAMA_YETKILISI,
            approved_on=timezone.localdate(),
            tmy_commission_members=TMY_KOMISYONU,
        )

        geri = weeding.withdraw_batch(batch)

        assert geri.status == WeedingBatchStatus.DRAFT
        assert geri.commission_decision_id is None and geri.submitted_at is None
        assert (geri.approved_by_name, geri.tmy_commission_members) == ("", "")
        assert geri.approved_on is None and not geri.destruction_decided
        durumlar = {k.pk: (k.state, k.exclusion_reason) for k in WeedingItem.objects.all()}
        assert durumlar == {
            birinci.pk: (WeedingItemState.PROPOSED, ""),
            ikinci.pk: (WeedingItemState.PROPOSED, ""),
        }
        weeding.remove_item(ikinci)  # taslakta kalem silinir (D15)

    def test_yalniz_sunulmus_kararli_ya_da_onayli_teklif_geri_cekilir(self) -> None:
        batch = teklif()
        with pytest.raises(ValidationError, match="geri çekilir"):
            weeding.withdraw_batch(batch)

    def test_karar_turu_ayiklama_olmali_d7(self) -> None:
        batch = teklif()
        kalem_ekle(batch, raftaki())
        weeding.submit_batch(batch)
        with pytest.raises(ValidationError) as hata:
            weeding.bind_decision(
                batch,
                commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
            )
        assert "commission_decision" in hata.value.message_dict

    def test_komisyonun_ayiklamadigi_kalem_uygulanmaz_ve_kayitta_kalir(self) -> None:
        batch = teklif()
        ayiklanan = raftaki("Ayıklanan")
        kalan = raftaki("Rafta Kalan")
        kalem_ekle(batch, ayiklanan)
        kalan_kalem = kalem_ekle(batch, kalan)
        weeding.submit_batch(batch)
        weeding.bind_decision(
            batch, commission_decision=ayiklama_karari(), kept={kalan_kalem.pk: "Onarılacak."}
        )
        weeding.approve_batch(
            batch, approved_by_name=HARCAMA_YETKILISI, approved_on=timezone.localdate()
        )
        weeding.apply_batch(batch)

        assert tazele(ayiklanan).status == CopyStatus.WITHDRAWN_WEEDED
        assert tazele(kalan).status == CopyStatus.AVAILABLE
        kalem = WeedingItem.objects.get(pk=kalan_kalem.pk)
        assert (kalem.state, kalem.exclusion_reason) == (
            WeedingItemState.KEPT_BY_COMMISSION,
            "Onarılacak.",
        )

    def test_disarida_birakmanin_gerekcesi_zorunlu_hepsi_disarida_kalamaz(self) -> None:
        batch = teklif()
        kalem = kalem_ekle(batch, raftaki())
        weeding.submit_batch(batch)
        with pytest.raises(ValidationError, match="gerekçesi"):
            weeding.bind_decision(
                batch, commission_decision=ayiklama_karari(), kept={kalem.pk: "  "}
            )
        with pytest.raises(ValidationError, match="kalem kalmadı"):
            weeding.bind_decision(
                batch, commission_decision=ayiklama_karari(), kept={kalem.pk: "Kalsın."}
            )
        assert WeedingItem.objects.get(pk=kalem.pk).state == WeedingItemState.PROPOSED

    def test_bos_teklif_sunulamaz(self) -> None:
        with pytest.raises(ValidationError, match="en az bir kalem"):
            weeding.submit_batch(teklif())

    def test_sunulmus_teklife_kalem_eklenmez_kurum_onaydan_once_degisir(self) -> None:
        batch = teklif()
        kalem = kalem_ekle(batch, raftaki(), "LEVEL_MISMATCH")
        weeding.submit_batch(batch)
        with pytest.raises(ValidationError, match="yalnız taslak"):
            kalem_ekle(batch, raftaki("Yeni"))
        with pytest.raises(ValidationError, match="yalnız taslak"):
            weeding.update_item(kalem, reason="WORN")
        assert weeding.update_item(kalem, transfer_target=DEVRALAN_OKUL).transfer_target == (
            DEVRALAN_OKUL
        )

    def test_uygulanmis_teklif_iptal_edilemez_taslak_silinir(self) -> None:
        batch = teklif()
        kalem_ekle(batch, raftaki())
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        with pytest.raises(ValidationError, match="iptal edilemez"):
            weeding.cancel_batch(batch)

        taslak = teklif()
        kalem_ekle(taslak, raftaki("Taslakta"))
        weeding.delete_batch(taslak)
        assert not WeedingBatch.objects.filter(pk=taslak.pk).exists()
        assert not WeedingItem.objects.filter(batch_id=taslak.pk).exists()

    def test_iptal_nushalara_dokunmaz_kayit_kalir(self) -> None:
        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap)
        onaya_kadar(batch)
        iptal = weeding.cancel_batch(batch, reason="Harcama yetkilisi vazgeçti.")
        assert iptal.status == WeedingBatchStatus.CANCELLED and iptal.cancelled_at is not None
        assert tazele(kitap).status == CopyStatus.AVAILABLE
        with pytest.raises(ValidationError):
            weeding.apply_batch(batch)
        with pytest.raises(ValidationError, match="silinmez|yalnız taslak"):
            weeding.delete_batch(batch)


# ============================================================ onay (TMY 10/1-e, 28)


class TestOnay:
    def _karari_bagli(self, *gerekceler: str) -> WeedingBatch:
        batch = teklif()
        for sira, gerekce in enumerate(gerekceler):
            ek: dict[str, Any] = {}
            if gerekce == "LEVEL_MISMATCH":
                ek["transfer_target"] = DEVRALAN_OKUL
            kalem_ekle(batch, raftaki(f"Eser {sira}"), gerekce, **ek)
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=ayiklama_karari())
        return batch

    def test_harcama_yetkilisi_adi_ve_tarih_zorunlu(self) -> None:
        batch = self._karari_bagli("WORN")
        bugun = timezone.localdate()
        with pytest.raises(ValidationError) as hata:
            weeding.approve_batch(batch, approved_by_name="  ", approved_on=bugun)
        assert "approved_by_name" in hata.value.message_dict
        with pytest.raises(ValidationError) as hata:
            weeding.approve_batch(batch, approved_by_name=HARCAMA_YETKILISI, approved_on=None)
        assert "approved_on" in hata.value.message_dict
        with pytest.raises(ValidationError, match="bugünden sonra"):
            weeding.approve_batch(
                batch, approved_by_name=HARCAMA_YETKILISI, approved_on=bugun + timedelta(days=1)
            )

    def test_onay_komisyon_kararindan_once_olamaz(self) -> None:
        batch = self._karari_bagli("WORN")
        with pytest.raises(ValidationError, match="komisyon kararının tarihinden önce"):
            weeding.approve_batch(
                batch,
                approved_by_name=HARCAMA_YETKILISI,
                approved_on=timezone.localdate() - timedelta(days=1),
            )

    def test_hurdaya_ayirmada_en_az_uc_kisilik_komisyon_zorunlu(self) -> None:
        batch = self._karari_bagli("OBSOLETE")
        bugun = timezone.localdate()
        with pytest.raises(ValidationError, match="TMY 28/1"):
            weeding.approve_batch(batch, approved_by_name=HARCAMA_YETKILISI, approved_on=bugun)
        with pytest.raises(ValidationError, match="en az 3 kişiden"):
            weeding.approve_batch(
                batch,
                approved_by_name=HARCAMA_YETKILISI,
                approved_on=bugun,
                tmy_commission_members="Deneme Bir\nDeneme İki",
            )
        onayli = weeding.approve_batch(
            batch,
            approved_by_name=HARCAMA_YETKILISI,
            approved_on=bugun,
            tmy_commission_members=f"\n{TMY_KOMISYONU}\n\n",
        )
        assert onayli.tmy_commission_members == TMY_KOMISYONU

    def test_27_yolunda_komisyon_istege_bagli(self) -> None:
        """10/1-e: durumu belgeleyen tutanak varsa komisyonsuz harcama yetkilisi onayı."""
        batch = self._karari_bagli("WORN")
        onayli = weeding.approve_batch(
            batch, approved_by_name=HARCAMA_YETKILISI, approved_on=timezone.localdate()
        )
        assert onayli.status == WeedingBatchStatus.APPROVED

    def test_imha_karari_yalniz_hurdaya_ayirmada(self) -> None:
        batch = self._karari_bagli("WORN", "LEVEL_MISMATCH")
        with pytest.raises(ValidationError, match="TMY 28/5"):
            weeding.approve_batch(
                batch,
                approved_by_name=HARCAMA_YETKILISI,
                approved_on=timezone.localdate(),
                destruction_decided=True,
            )

    def test_imha_karari_hurda_kaleminde_kaydedilir(self) -> None:
        batch = teklif()
        kalem_ekle(batch, raftaki(), "CRITERIA_MISMATCH", criterion="10_4")
        onayli = onaya_kadar(batch, destruction_decided=True)
        assert onayli.destruction_decided

    def test_devirde_devralacak_kurum_onaydan_once_zorunlu(self) -> None:
        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap, "LEVEL_MISMATCH")
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=ayiklama_karari())
        with pytest.raises(ValidationError) as hata:
            weeding.approve_batch(
                batch, approved_by_name=HARCAMA_YETKILISI, approved_on=timezone.localdate()
            )
        assert "transfer_target" in hata.value.message_dict

    def test_onaylanmayan_kalem_uygulanmaz(self) -> None:
        batch = self._karari_bagli("WORN", "WORN")
        birinci, ikinci = list(selectors_ayiklama.batch_items(batch))
        weeding.approve_batch(
            batch,
            approved_by_name=HARCAMA_YETKILISI,
            approved_on=timezone.localdate(),
            not_approved={ikinci.pk: "Kullanılabilir durumda."},
        )
        weeding.apply_batch(batch)
        assert tazele(birinci.copy).status == CopyStatus.WITHDRAWN_WEEDED
        assert tazele(ikinci.copy).status == CopyStatus.AVAILABLE
        assert WeedingItem.objects.get(pk=ikinci.pk).state == WeedingItemState.NOT_APPROVED

    def test_onay_adlari_diske_sifreli_yazilir(self) -> None:
        batch = teklif()
        kalem_ekle(batch, raftaki(), "OBSOLETE")
        onaya_kadar(batch)
        with connection.cursor() as imlec:
            imlec.execute(
                "SELECT approved_by_name, tmy_commission_members FROM kutuphane_weedingbatch "
                "WHERE id = %s",
                [batch.pk],
            )
            ad, uyeler = imlec.fetchone()
        assert ad.startswith("gAAAAA") and "Harcamayetkilisi" not in ad
        assert uyeler.startswith("gAAAAA") and "Birinciüye" not in uyeler
        assert WeedingBatch.objects.get(pk=batch.pk).approved_by_name == HARCAMA_YETKILISI

    def test_db_kisiti_onaysiz_onayli_durumu_reddeder(self) -> None:
        batch = teklif()
        with pytest.raises(IntegrityError), transaction.atomic():
            WeedingBatch.objects.filter(pk=batch.pk).update(
                status=WeedingBatchStatus.APPROVED, submitted_at=timezone.now()
            )


# ============================================================ TMY 32/3 kapısı ve kip


class TestKapilar:
    def test_uygulama_tmy_kapisini_kayittan_dusme_ve_devir_icin_sorar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sorulan: list[str] = []
        monkeypatch.setattr(tmy_kapisi, "ensure_open", kapi_kaydi(sorulan))
        batch = teklif()
        kalem_ekle(batch, raftaki("Düşülecek"), "WORN")
        kalem_ekle(batch, raftaki("Devredilecek"), "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)
        onaya_kadar(batch)
        weeding.apply_batch(batch)
        assert sorulan == [tmy_kapisi.KAYITTAN_DUSME, tmy_kapisi.DEVIR]

    def test_kapi_kapaliysa_hicbir_nusha_dusulmez(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def kapali(islem: str) -> None:
            raise ValidationError("Sayım sürüyor: TMY 32/3 durdurması.")

        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap)
        onaya_kadar(batch)
        monkeypatch.setattr(tmy_kapisi, "ensure_open", kapali)
        with pytest.raises(ValidationError, match="32/3"):
            weeding.apply_batch(batch)
        assert tazele(kitap).status == CopyStatus.AVAILABLE

    def test_gorevli_kipinde_ayiklama_yapilamaz(self) -> None:
        batch = teklif()
        KIP.gorevliye_gec()
        with pytest.raises(KipYetkisiz):
            weeding.create_batch()
        with pytest.raises(KipYetkisiz):
            weeding.add_items(batch, copy_ids=[raftaki().pk], reason="WORN")
        with pytest.raises(KipYetkisiz):
            weeding.apply_batch(batch)


# ============================================================ F7 kayıttan düşme önerisi


class TestKayittanDusmeOnerisi:
    """25.09.2026 kullanıcı kararı (F8 ekleri 34): kayıp ve hasar dosyasının kayıttan düşme
    önerisi ayıklamaya konmaz — Md. 12/1'in bentleri kaybı ve hasarı saymaz; sayımda TMY
    27/1 yolundan, kayıp/hasar tutanağıyla komisyonsuz düşülür (F9)."""

    def test_hasar_dosyasinin_onerisi_aday_degildir_ve_teklife_eklenemez(self) -> None:
        sade = raftaki("Aaa Sade Aday")
        hasarli = raftaki("Zzz Hasarlı")
        dosya = loss_damage.open_damage_case(copy=hasarli)
        loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")

        assert [c.pk for c in selectors_ayiklama.weeding_candidates()] == [sade.pk]
        assert [c.pk for c in selectors_ayiklama.damage_write_off_proposals()] == [hasarli.pk]
        assert list(selectors_ayiklama.lost_write_off_proposals()) == []
        assert weeding.ayiklama_engeli(tazele(hasarli)) == weeding.DAMAGE_PROPOSAL_MESSAGE
        with pytest.raises(ValidationError, match="sayımda kayıttan düşülür"):
            kalem_ekle(teklif(), tazele(hasarli))
        # Kalemin dosyaya bağı yoktur (F8 ekleri 34 — ara belge düzeltmesi kalktı).
        assert not hasattr(WeedingItem, "loss_damage_case")

    def test_hasar_onerisi_oduncteki_nushada_da_ayri_listede(self) -> None:
        """Hasar dosyası nüshayı dolaşımdan çıkarmaz: öneriden sonra ödünç verilen kitap
        da ayrı listede görünür (aday listesinde değil)."""
        kitap = raftaki("Hasarlı Ödünçte")
        dosya = loss_damage.open_damage_case(copy=kitap)
        loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")
        odunc_ver(uye(), tazele(kitap))

        assert tazele(kitap).status == CopyStatus.ON_LOAN
        assert [c.pk for c in selectors_ayiklama.damage_write_off_proposals()] == [kitap.pk]

    def test_teklif_surerken_yazilan_hasar_onerisi_uygulamayi_durdurmaz(self) -> None:
        """Hasar önerisi yalnız eklemede engeldir: komisyonun Md. 12/1 kararı düşmez."""
        batch = teklif()
        kitap = raftaki()
        kalem_ekle(batch, kitap)
        dosya = loss_damage.open_damage_case(copy=tazele(kitap))
        loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")
        onaya_kadar(batch)

        weeding.apply_batch(batch)

        assert tazele(kitap).status == CopyStatus.WITHDRAWN_WEEDED
        assert list(selectors_ayiklama.damage_write_off_proposals()) == []

    def test_kayip_onerisi_ayri_listede_ayiklamaya_konmaz(self) -> None:
        kitap = raftaki()
        dosya = loss_damage.report_lost(copy=kitap)
        loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")

        assert kitap.pk not in {c.pk for c in selectors_ayiklama.weeding_candidates()}
        assert [c.pk for c in selectors_ayiklama.lost_write_off_proposals()] == [kitap.pk]
        with pytest.raises(ValidationError, match="sayımda"):
            kalem_ekle(teklif(), tazele(kitap))

    def test_aday_listesi_engelli_nushalari_almaz(self) -> None:
        nadir = raftaki("Nadir", is_rare_or_manuscript=True)
        oduncte = odunc_ver(uye()).copy
        dosyali = raftaki("Dosyalı")
        loss_damage.open_damage_case(copy=dosyali)
        teklifte = raftaki("Teklifte")
        kalem_ekle(teklif(), teklifte)
        aday = raftaki("Aday")

        kimlikler = {c.pk for c in selectors_ayiklama.weeding_candidates()}
        assert aday.pk in kimlikler
        assert not ({nadir.pk, oduncte.pk, dosyali.pk, teklifte.pk} & kimlikler)

    def test_aday_aramasi_turkce_katlamali(self) -> None:
        raftaki("Şiir Defteri")
        raftaki("Başka")
        assert [c.work.title for c in selectors_ayiklama.weeding_candidates(q="ŞİİR")] == [
            "Şiir Defteri"
        ]


def test_ayiklama_karari_kullanimdayken_turu_degismez_ve_silinmez() -> None:
    """D7: karar kullanımı ayıklama teklifini de kapsar (`decision_in_use`)."""
    decision = ayiklama_karari()
    batch = teklif()
    kalem_ekle(batch, raftaki())
    weeding.submit_batch(batch)
    weeding.bind_decision(batch, commission_decision=decision)

    assert commissions.decision_in_use(decision)
    assert selectors_ayiklama.decision_usage(decision)["weeding_batches"] == 1
    with pytest.raises(ValidationError, match="türü değiştirilemez"):
        commissions.update_commission_decision(
            decision, decision_type=CommissionDecisionType.SELECTION
        )
    with pytest.raises(ValidationError, match="silinemez"):
        commissions.delete_commission_decision(decision)


# ============================================================ F8 düzeltme turu (25.09.2026)


class TestTeklifKaydininKorunmasi:
    """Bir teklife girmiş nüsha "yanlış açılmış kayıt" yoluyla silinemez (kök neden:
    `catalog.delete_copy` F8 ilişkilerini saymıyordu)."""

    def test_onayli_teklifteki_nusha_silinemez(self) -> None:
        kitap = raftaki("Onaylı Teklifte")
        batch = teklif()
        kalem_ekle(batch, kitap, "OBSOLETE")
        onaya_kadar(batch)
        with pytest.raises(ValidationError, match="Ayıklama teklifine girmiş nüsha silinemez"):
            catalog.delete_copy(tazele(kitap))
        assert tazele(kitap).deleted_at is None
        assert weeding.apply_batch(batch).withdrawn == 1  # teklif bozulmadı

    def test_iptal_edilmis_teklifteki_nusha_da_silinemez(self) -> None:
        kitap = raftaki("İptal Edilen Teklifte")
        batch = teklif()
        kalem_ekle(batch, kitap)
        weeding.submit_batch(batch)
        weeding.cancel_batch(batch)
        with pytest.raises(ValidationError, match="Ayıklama teklifine girmiş"):
            catalog.delete_copy(tazele(kitap))

    def test_taslaktaki_kalem_cikarilinca_nusha_silinir(self) -> None:
        kitap = raftaki("Yanlış Açılmış")
        batch = teklif()
        kalem = kalem_ekle(batch, kitap)
        with pytest.raises(ValidationError, match="önce kalemi çıkarın"):
            catalog.delete_copy(tazele(kitap))
        weeding.remove_item(kalem)
        catalog.delete_copy(tazele(kitap))
        assert tazele(kitap).deleted_at is not None


class TestAyniKararinYenidenBaglanmasi:
    """Geri çekilen teklife AYNI karar yalnız kararın kapsadığı kalemlerle bağlanır."""

    def test_devir_karari_gerekcesi_degisen_kaleme_baglanamaz(self) -> None:
        kitap = raftaki("Düzeye Uygun Değil")
        batch = teklif()
        kalem = kalem_ekle(batch, kitap, "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)
        decision = ayiklama_karari()
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=decision)  # "devredilsin"
        weeding.withdraw_batch(batch)
        weeding.update_item(kalem, reason="OBSOLETE")  # 28 yoluna çevrildi
        weeding.submit_batch(batch)

        with pytest.raises(ValidationError) as hata:
            weeding.bind_decision(batch, commission_decision=decision)
        ileti = hata.value.message_dict["commission_decision"][0]
        assert "yeni bir komisyon kararı gerekir" in ileti
        assert barcode_module.format_barcode(kitap.barcode) in ileti
        assert WeedingBatch.objects.get(pk=batch.pk).status == WeedingBatchStatus.SUBMITTED
        # Yeni karar bağlanabilir.
        yeni = weeding.bind_decision(batch, commission_decision=ayiklama_karari(decision_no="2"))
        assert yeni.status == WeedingBatchStatus.DECIDED

    def test_komisyonun_ayiklamadigi_kalem_ayni_kararla_ayiklanamaz(self) -> None:
        batch = teklif()
        kalan = kalem_ekle(batch, raftaki("Rafta Kalsın"))
        kalem_ekle(batch, raftaki("Ayıklansın"))
        decision = ayiklama_karari()
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=decision, kept={kalan.pk: "Onarılacak."})
        weeding.withdraw_batch(batch)
        weeding.submit_batch(batch)
        with pytest.raises(ValidationError, match="yeni bir komisyon kararı gerekir"):
            weeding.bind_decision(batch, commission_decision=decision)
        # Komisyonun kararı aynen işlenirse (aynı kalem yine ayıklanmıyor) bağlanır.
        bagli = weeding.bind_decision(
            batch, commission_decision=decision, kept={kalan.pk: "Onarılacak."}
        )
        assert bagli.status == WeedingBatchStatus.DECIDED

    def test_kalem_cikarilan_teklife_ayni_karar_baglanir(self) -> None:
        """Alt küme kararın kapsamındadır (ör. teklifi bölmek); devralacak kurum ize girmez."""
        batch = teklif()
        birinci = kalem_ekle(batch, raftaki("Birinci"), "LEVEL_MISMATCH")
        ikinci = kalem_ekle(batch, raftaki("İkinci"))
        decision = ayiklama_karari()
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=decision)
        weeding.withdraw_batch(batch)
        weeding.remove_item(ikinci)
        weeding.update_item(birinci, transfer_target=DEVRALAN_OKUL)
        weeding.submit_batch(batch)
        assert (
            weeding.bind_decision(batch, commission_decision=decision).status
            == WeedingBatchStatus.DECIDED
        )

    def test_yeni_kalem_eklenen_teklife_ayni_karar_baglanamaz(self) -> None:
        batch = teklif()
        kalem_ekle(batch, raftaki("Eski"))
        decision = ayiklama_karari()
        onaya_kadar(batch, decision=decision)
        weeding.withdraw_batch(batch)
        kalem_ekle(batch, raftaki("Sonradan Eklenen"))
        weeding.submit_batch(batch)
        with pytest.raises(ValidationError, match="yeni bir komisyon kararı gerekir"):
            weeding.bind_decision(batch, commission_decision=decision)


def test_suren_teklifte_nadir_isaretlenen_nusha_karar_baglanirken_reddedilir() -> None:
    """Md. 12/2 tespitini komisyon yapar: karar bağlanırken nadir eser ayıklanamaz."""
    kitap = raftaki("Sonradan Nadir Anlaşılan")
    batch = teklif()
    kalem = kalem_ekle(batch, kitap)
    kalem_ekle(batch, raftaki("Sade"))
    weeding.submit_batch(batch)
    catalog.update_copy(tazele(kitap), is_rare_or_manuscript=True)

    with pytest.raises(ValidationError) as hata:
        weeding.bind_decision(batch, commission_decision=ayiklama_karari())
    assert "nadir eser" in hata.value.message_dict["items"][0]
    # Komisyon o kalemi ayıklamadıysa karar bağlanır.
    bagli = weeding.bind_decision(
        batch, commission_decision=ayiklama_karari(), kept={kalem.pk: "Nadir eser."}
    )
    assert bagli.status == WeedingBatchStatus.DECIDED
    nadirler = {
        k.copy_id for k in selectors_ayiklama.batch_items(bagli) if k.copy.is_rare_or_manuscript
    }
    assert nadirler == {kitap.pk}


class TestImhaKarariKalemDuzeyinde:
    def _iki_hurda(self) -> tuple[WeedingBatch, WeedingItem, WeedingItem]:
        batch = teklif()
        birinci = kalem_ekle(batch, raftaki("Hurda Bir"), "OBSOLETE")
        ikinci = kalem_ekle(batch, raftaki("Hurda İki"), "OBSOLETE")
        kalem_ekle(batch, raftaki("Yıpranan"), "WORN")
        weeding.submit_batch(batch)
        weeding.bind_decision(batch, commission_decision=ayiklama_karari())
        return batch, birinci, ikinci

    def _onay(self, batch: WeedingBatch, **ek: Any) -> WeedingBatch:
        return weeding.approve_batch(
            batch,
            approved_by_name=HARCAMA_YETKILISI,
            approved_on=timezone.localdate(),
            tmy_commission_members=TMY_KOMISYONU,
            **ek,
        )

    def test_verilmezse_butun_hurda_kalemleri(self) -> None:
        batch, birinci, ikinci = self._iki_hurda()
        self._onay(batch, destruction_decided=True)
        isaretli = set(
            WeedingItem.objects.filter(destruction_decided=True).values_list("pk", flat=True)
        )
        assert isaretli == {birinci.pk, ikinci.pk}

    def test_secilen_kalemler_ve_gecersiz_secim(self) -> None:
        batch, birinci, ikinci = self._iki_hurda()
        yipranan = WeedingItem.objects.get(batch=batch, reason="WORN")
        with pytest.raises(ValidationError, match="yalnız onaylanan hurdaya ayırma"):
            self._onay(batch, destruction_decided=True, destruction_items=[yipranan.pk])
        with pytest.raises(ValidationError, match="en az bir kalem"):
            self._onay(batch, destruction_decided=True, destruction_items=[])
        with pytest.raises(ValidationError, match="İmha kararı işaretlenmeden"):
            self._onay(batch, destruction_items=[birinci.pk])
        self._onay(batch, destruction_decided=True, destruction_items=[birinci.pk])
        assert list(
            WeedingItem.objects.filter(destruction_decided=True).values_list("pk", flat=True)
        ) == [birinci.pk]

    def test_onaylanmayan_kalem_imha_kapsamina_giremez(self) -> None:
        batch, _, ikinci = self._iki_hurda()
        with pytest.raises(ValidationError, match="yalnız onaylanan hurdaya ayırma"):
            self._onay(
                batch,
                destruction_decided=True,
                destruction_items=[ikinci.pk],
                not_approved={ikinci.pk: "Ekonomik değeri var."},
            )
        # Tek işlem: dışarıda bırakma da geri sarıldı.
        assert WeedingItem.objects.get(pk=ikinci.pk).state == WeedingItemState.PROPOSED

    def test_geri_cekme_imha_isaretlerini_temizler(self) -> None:
        batch, _, _ = self._iki_hurda()
        self._onay(batch, destruction_decided=True)
        weeding.withdraw_batch(batch)
        assert not WeedingItem.objects.filter(destruction_decided=True).exists()

    def test_db_kisiti_imha_yalniz_hurda_kaleminde(self) -> None:
        batch = teklif()
        kalem = kalem_ekle(batch, raftaki(), "WORN")
        with pytest.raises(IntegrityError), transaction.atomic():
            WeedingItem.objects.filter(pk=kalem.pk).update(destruction_decided=True)


def test_iletiler_ayarlar_sekmesinin_adini_birebir_yazar() -> None:
    """Sözlük §4.3: sekmenin adı "Ders Yılları"dır."""
    from apps.kutuphane.services import annual_review, rare_works

    for ileti in (
        weeding.NO_SCHOOL_YEAR_MESSAGE,
        rare_works.NO_SCHOOL_YEAR_MESSAGE,
        annual_review.NO_SCHOOL_YEAR_MESSAGE,
    ):
        assert "(Ayarlar → Ders Yılları)" in ileti


def test_iletiler_yonetmelige_metinde_olmayan_hukum_yuklemez() -> None:
    """Md. 12/1 devri 10/1-b için ister; "yalnız" ve düzeye uygunsuzluğun devri programındır.
    Md. 12/2 ayıklama yasağı koymaz; yasak programın kuralıdır."""
    assert "program düzeye uygunsuzluğu yalnız devir yoluna bağlar" in (
        weeding.LEVEL_ONLY_TRANSFER_MESSAGE
    )
    assert weeding.TRANSFER_ONLY_LEVEL_MESSAGE.startswith("Programda devir yalnız")
    assert "(Md. 10/1-b)" in weeding.TRANSFER_ONLY_LEVEL_MESSAGE
    assert weeding.RARE_MESSAGE.endswith("listesi Genel Müdürlüğe gönderilir (Md. 12/2).")
    assert "ayıklanamaz (Md. 12/2)" not in weeding.RARE_MESSAGE
