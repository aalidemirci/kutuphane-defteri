"""Katalog güncelleme yolları ve tekil seçiciler (API katmanının çağıracağı yüzey).

Yazma servisleri `create_*` kadar `update_*` da taşır; güncellemede Türkçe
anahtarların tazelenmesi, kuralların yeniden denetlenmesi ve korunan alanların
kapalı kalması burada sabitlenir.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.kutuphane import keys, selectors
from apps.kutuphane.models import (
    AcquisitionMethod,
    CommissionDecisionType,
    DonationIntakeStatus,
    ResourceType,
)
from apps.kutuphane.services import catalog, commissions, donations
from apps.kutuphane.tests.ortak import VARSAYILAN_TARIH, bolum, edinim, eser, karar, nusha


@pytest.mark.django_db
class TestBolumGuncelleme:
    def test_ad_degisince_siralama_anahtari_tazelenir(self) -> None:
        section = bolum(name="Tarih")
        catalog.update_section(section, name="Çocuk")
        section.refresh_from_db()
        assert section.name_sort_key == keys.tr_collation_key("Çocuk")

    def test_bolumler_turkce_sirada_doner(self) -> None:
        bolum(name="Zooloji")
        bolum(name="Çocuk")
        bolum(name="Iğdır Yerel")
        assert [s.name for s in selectors.sections()] == ["Çocuk", "Iğdır Yerel", "Zooloji"]

    def test_tek_bolum_getirilir(self) -> None:
        section = bolum(name="Danışma")
        assert selectors.get_section(section.pk) == section
        assert selectors.get_section(section.pk + 999) is None


@pytest.mark.django_db
class TestEserGuncelleme:
    def test_kunye_degisince_anahtarlar_tazelenir(self) -> None:
        work = eser(title="Eski Ad", authors="Sabahattin Ali", subjects="Roman")
        catalog.update_work(work, title="Şiir Kitabı", authors="Behçet Necatigil", subjects="Şiir")
        work.refresh_from_db()
        assert work.sort_key == keys.tr_collation_key("Şiir Kitabı")
        assert work.author_sort_key == keys.tr_collation_key("Necatigil Behçet")
        assert [w.title for w in selectors.works(q="ŞİİR")] == ["Şiir Kitabı"]

    def test_yer_numarasi_bosaltilirsa_yeniden_uretilir(self) -> None:
        work = eser(authors="Sabahattin Ali", classification_code="813.54", call_number="ELLE 1")
        catalog.update_work(work, call_number="")
        assert work.call_number == "813.54 ALİ"

    def test_silinmis_bolum_esere_baglanmaz(self) -> None:
        section = bolum(name="Geçici")
        section.delete()
        with pytest.raises(ValidationError) as hata:
            catalog.create_work(title="Deneme", section=section)
        assert "section" in hata.value.message_dict

    def test_nushali_eser_silinemez(self) -> None:
        work = eser()
        nusha(work)
        with pytest.raises(ValidationError) as hata:
            catalog.delete_work(work)
        assert "work" in hata.value.message_dict

    def test_nushasiz_eser_silinir(self) -> None:
        work = eser(title="Yanlış Kayıt")
        catalog.delete_work(work)
        work.refresh_from_db()
        assert work.deleted_at is not None

    def test_tek_eser_getirilir(self) -> None:
        work = eser()
        assert selectors.get_work(work.pk) == work
        assert selectors.get_work(work.pk + 999) is None


@pytest.mark.django_db
class TestNushaGuncelleme:
    def test_katalog_alanlari_guncellenir(self) -> None:
        section = bolum(name="Edebiyat")
        copy = nusha()
        catalog.update_copy(copy, section=section, is_reference=True, external_asset_ref="TKYS-42")
        copy.refresh_from_db()
        assert copy.section_id == section.pk
        assert copy.is_reference is True
        assert copy.external_asset_ref == "TKYS-42"
        assert copy.is_loanable is False

    def test_kayit_no_elle_degistirilemez(self) -> None:
        copy = nusha()
        with pytest.raises(ValidationError) as hata:
            catalog.update_copy(copy, accession_no=1)
        assert "accession_no" in hata.value.message_dict

    def test_sureli_yayin_cilt_isareti_kaldirilamaz(self) -> None:
        """Ciltsiz süreli yayın kayda giremez (TMY Md. 15/4) — güncellemede de."""
        dergi = eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        copy = nusha(dergi, is_bound_periodical=True)
        with pytest.raises(ValidationError) as hata:
            catalog.update_copy(copy, is_bound_periodical=False)
        assert "is_bound_periodical" in hata.value.message_dict

    def test_tek_nusha_getirilir(self) -> None:
        copy = nusha()
        assert selectors.get_copy(copy.pk) == copy
        assert selectors.get_copy(copy.pk + 999) is None

    def test_esere_gore_nushalar_suzulur(self) -> None:
        birinci = eser(title="Birinci")
        ikinci = eser(title="İkinci")
        acquisition = edinim()
        nusha(birinci, acquisition)
        hedef = nusha(ikinci, acquisition)
        assert [c.pk for c in selectors.copies(work_id=ikinci.pk)] == [hedef.pk]

    def test_bolume_ve_duruma_gore_nushalar_suzulur(self) -> None:
        section = bolum(name="Edebiyat")
        work = eser()
        acquisition = edinim()
        hedef = nusha(work, acquisition, section=section)
        nusha(work, acquisition)
        assert [c.pk for c in selectors.copies(section_id=section.pk)] == [hedef.pk]
        assert len(selectors.copies(status="AVAILABLE")) == 2


@pytest.mark.django_db
class TestEdinimGuncelleme:
    def test_yontem_bagisa_cevrilince_karar_istenir(self) -> None:
        acquisition = edinim(method=AcquisitionMethod.PURCHASE)
        with pytest.raises(ValidationError) as hata:
            catalog.update_acquisition(acquisition, method=AcquisitionMethod.DONATION)
        assert "commission_decision" in hata.value.message_dict

    def test_kaynak_notu_guncellenir(self) -> None:
        acquisition = edinim()
        catalog.update_acquisition(acquisition, source_note="Kitap Fuarı partisi")
        acquisition.refresh_from_db()
        assert acquisition.source_note == "Kitap Fuarı partisi"

    def test_tek_edinim_getirilir(self) -> None:
        acquisition = edinim()
        assert selectors.get_acquisition(acquisition.pk) == acquisition
        assert selectors.get_acquisition(acquisition.pk + 999) is None


@pytest.mark.django_db
class TestKomisyonKarariGuncelleme:
    def test_karar_servisle_acilir(self) -> None:
        decision = commissions.create_commission_decision(
            decision_type=CommissionDecisionType.SELECTION,
            decision_date=VARSAYILAN_TARIH,
            chair_name="Deniz Korkmaz",
            chair_title="Şube Müdürü",
        )
        assert decision.pk is not None
        assert selectors.get_commission_decision(decision.pk) == decision

    def test_kullanilmamis_kararin_turu_degistirilebilir(self) -> None:
        decision = karar(decision_type=CommissionDecisionType.SELECTION)
        commissions.update_commission_decision(
            decision, decision_type=CommissionDecisionType.WEEDING, decision_no="2026/9"
        )
        decision.refresh_from_db()
        assert decision.decision_type == CommissionDecisionType.WEEDING
        assert decision.decision_no == "2026/9"


@pytest.mark.django_db
class TestBagisOnKaydiDuzenleme:
    def test_kalem_eklenir_guncellenir_silinir(self) -> None:
        intake = donations.create_intake(
            donor_name="Ayşe Yıldırım", received_date=date(2026, 9, 10)
        )
        kalem = donations.add_item(intake, title="Çalıkuşu", copies=1)
        donations.update_item(kalem, copies=3)
        kalem.refresh_from_db()
        assert kalem.copies == 3
        donations.remove_item(kalem)
        assert intake.items.count() == 0

    def test_iptal_edilen_on_kayda_kalem_eklenmez(self) -> None:
        intake = donations.create_intake(received_date=date(2026, 9, 10))
        donations.cancel_intake(intake, reason="Bağış geri alındı.")
        intake.refresh_from_db()
        assert intake.status == DonationIntakeStatus.CANCELLED
        assert "geri alındı" in intake.notes
        with pytest.raises(ValidationError):
            donations.add_item(intake, title="Yeni Kitap")

    def test_on_kayitlar_duruma_gore_suzulur(self) -> None:
        bekleyen = donations.create_intake(received_date=date(2026, 9, 10))
        iptal = donations.create_intake(received_date=date(2026, 9, 11))
        donations.cancel_intake(iptal)
        bekleyenler = selectors.donation_intakes(status=DonationIntakeStatus.PENDING)
        assert [i.pk for i in bekleyenler] == [bekleyen.pk]
        assert selectors.get_donation_intake(bekleyen.pk) == bekleyen
        assert selectors.get_donation_intake(bekleyen.pk + 999) is None
