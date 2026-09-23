"""Katalog servisleri: nüsha kuralları, komisyon karar türü (D7), bağış ön kaydı.

F2 kod kapısının servis tarafı (sözleşme §5): dijital kaynakta nüsha açılmaz,
süreli yayın yalnız ciltliyse kayda girer, bağışta komisyon kararı ve türü
denetlenir, bağış ön kaydından toplu kataloglama tek işlemdir.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.kutuphane.models import (
    AcquisitionMethod,
    CommissionDecisionType,
    Copy,
    CopyStatus,
    DonationIntake,
    DonationIntakeStatus,
    DonationItemDecision,
    ResourceType,
    Work,
)
from apps.kutuphane.services import catalog, donations
from apps.kutuphane.tests.ortak import VARSAYILAN_TARIH, bolum, edinim, eser, karar, nusha


@pytest.mark.django_db
class TestNushaKurallari:
    def test_dijital_kaynakta_nusha_acilmaz(self) -> None:
        kitap = eser(title="E-Kitap Örneği", resource_type=ResourceType.EBOOK)
        with pytest.raises(ValidationError) as hata:
            catalog.create_copy(work=kitap, acquisition=edinim())
        assert "work" in hata.value.message_dict

    def test_e_veri_tabaninda_nusha_acilmaz(self) -> None:
        kaynak = eser(title="E-Veri Tabanı", resource_type=ResourceType.EDATABASE)
        with pytest.raises(ValidationError):
            catalog.create_copy(work=kaynak, acquisition=edinim())

    def test_ciltsiz_sureli_yayinda_nusha_acilmaz(self) -> None:
        dergi = eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        with pytest.raises(ValidationError) as hata:
            catalog.create_copy(work=dergi, acquisition=edinim())
        assert "is_bound_periodical" in hata.value.message_dict

    def test_ciltli_sureli_yayinda_nusha_acilir(self) -> None:
        dergi = eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        copy = catalog.create_copy(work=dergi, acquisition=edinim(), is_bound_periodical=True)
        assert copy.status == CopyStatus.AVAILABLE

    def test_kitap_turunde_ciltli_sureli_nusha_acilmaz(self) -> None:
        """Ters yön: işaret yalnız süreli yayında kullanılır (Md. 16/1-c kaçağı).

        F3'ün Excel şemasında "Kaynak Türü" ile "Ciltli Süreli Yayın" AYRI
        sütunlardır; denetim olmadan "Kitap" + "Evet" diyen bir satır sessizce
        ÖDÜNÇ VERİLEBİLİR cilt nüshaları doğururdu.
        """
        kitap = eser(title="Roman", resource_type=ResourceType.BOOK)
        with pytest.raises(ValidationError) as hata:
            catalog.create_copy(work=kitap, acquisition=edinim(), is_bound_periodical=True)
        assert "is_bound_periodical" in hata.value.message_dict

    def test_yeni_nusha_rafta_dogar(self) -> None:
        assert nusha().status == CopyStatus.AVAILABLE

    def test_barkod_disaridan_verilemez(self) -> None:
        with pytest.raises(ValidationError) as hata:
            catalog.create_copy(work=eser(), acquisition=edinim(), barcode="2026000001")
        assert "barcode" in hata.value.message_dict

    def test_durum_katalog_servisinden_yazilamaz(self) -> None:
        copy = nusha()
        with pytest.raises(ValidationError) as hata:
            catalog.update_copy(copy, status=CopyStatus.LOST)
        assert "status" in hata.value.message_dict

    def test_silinmis_eser_icin_nusha_acilmaz(self) -> None:
        """Yumuşak silme ileri FK'da süzmez (CLAUDE.md §3) — denetim elle yapılır."""
        work = eser()
        work.delete()
        with pytest.raises(ValidationError) as hata:
            catalog.create_copy(work=work, acquisition=edinim())
        assert "work" in hata.value.message_dict

    def test_toplu_nusha_acilir(self) -> None:
        work = eser()
        nushalar = catalog.create_copies(work=work, acquisition=edinim(), count=3)
        assert len({c.barcode for c in nushalar}) == 3
        assert Copy.objects.filter(work=work).count() == 3

    def test_eski_kayit_no_tek_nushaya_aittir(self) -> None:
        with pytest.raises(ValidationError) as hata:
            catalog.create_copies(
                work=eser(), acquisition=edinim(), count=2, old_register_no="1452"
            )
        assert "old_register_no" in hata.value.message_dict


@pytest.mark.django_db
class TestKaynakTuruDegisimi:
    """Nüsha kuralları ESER GÜNCELLENİRKEN de korunur (`ensure_work_type_change`).

    Kapı olmadan kural güncelleme yolundan delinirdi: nüshası olan kitap
    e-kitaba çevrilebiliyor, e-kitabın kayıt defterinde nüshası oluyor, o nüsha
    ödünç verilebilir görünüyor ve BİR DAHA DÜZENLENEMİYORDU (her `update_copy`
    kendi kapısına takılırdı; tek çıkış eseri geri çevirmekti).
    """

    def test_nushasi_olan_eser_e_kitaba_cevrilemez(self) -> None:
        kitap = eser(title="Roman")
        nusha(kitap)
        with pytest.raises(ValidationError) as hata:
            catalog.update_work(kitap, resource_type=ResourceType.EBOOK)
        assert "resource_type" in hata.value.message_dict

    def test_nushasi_olan_eser_e_veri_tabanina_cevrilemez(self) -> None:
        kitap = eser(title="Roman")
        nusha(kitap)
        with pytest.raises(ValidationError):
            catalog.update_work(kitap, resource_type=ResourceType.EDATABASE)

    def test_nushasiz_eser_e_kitaba_cevrilebilir(self) -> None:
        kitap = eser(title="Roman")
        guncel = catalog.update_work(kitap, resource_type=ResourceType.EBOOK)
        assert guncel.is_digital is True

    def test_ciltsiz_nushasi_olan_eser_sureli_yayina_cevrilemez(self) -> None:
        """TMY Md. 15/4: süreli yayın yalnız ciltletildiğinde kayda girer."""
        kitap = eser(title="Dergi Olacak")
        nusha(kitap)
        with pytest.raises(ValidationError) as hata:
            catalog.update_work(kitap, resource_type=ResourceType.PERIODICAL)
        assert "resource_type" in hata.value.message_dict

    def test_ciltli_nushasi_olan_eser_sureli_yayindan_cikarilamaz(self) -> None:
        """Ters yön: çıkarılsaydı nüsha `update_copy`'de kalıcı olarak kilitlenirdi."""
        dergi = eser(title="Bilim ve Teknik", resource_type=ResourceType.PERIODICAL)
        catalog.create_copy(work=dergi, acquisition=edinim(), is_bound_periodical=True)
        with pytest.raises(ValidationError) as hata:
            catalog.update_work(dergi, resource_type=ResourceType.BOOK)
        assert "resource_type" in hata.value.message_dict

    def test_silinmis_nusha_tur_degisimini_engellemez(self) -> None:
        """Yanlış açılıp silinmiş nüsha kuralı kilitlememelidir (CLAUDE.md §3)."""
        kitap = eser(title="Roman")
        yanlis = nusha(kitap)
        catalog.delete_copy(yanlis)
        guncel = catalog.update_work(kitap, resource_type=ResourceType.EBOOK)
        assert guncel.is_digital is True

    def test_tur_disi_guncelleme_nusha_varken_de_calisir(self) -> None:
        kitap = eser(title="Roman")
        nusha(kitap)
        guncel = catalog.update_work(kitap, publisher="Deneme Yayınları")
        assert guncel.publisher == "Deneme Yayınları"


@pytest.mark.django_db
class TestNushaSilme:
    """Silme YALNIZ veri giriş hatası içindir: kural "yalnız Rafta" biçimindedir.

    Durum listesi saymak yerine tek koşul yazılması bilinçlidir: F7 (kayıp ve
    hasar) ile F8-F9 (kayıttan düşme, devir) yeni bir hâl eklediğinde kapı
    kendiliğinden kapsar. Sayılan listeye eklemeyi unutmak sessiz bir açık
    bırakırdı — `LOST` ve `IN_REPAIR` tam olarak böyle atlanmıştı.
    """

    def test_rafta_duran_nusha_silinir(self) -> None:
        copy = nusha()
        catalog.delete_copy(copy)
        assert Copy.objects.filter(pk=copy.pk).count() == 0

    # Küme `CopyStatus`tan TÜRETİLİR: yeni bir hâl eklendiğinde test onu
    # kendiliğinden sınar (elle yazılan liste eskirdi).
    @pytest.mark.parametrize("durum", [d for d in CopyStatus.values if d != CopyStatus.AVAILABLE])
    def test_rafta_olmayan_nusha_silinemez(self, durum: str) -> None:
        copy = nusha()
        Copy.objects.filter(pk=copy.pk).update(status=durum)
        copy.refresh_from_db()
        with pytest.raises(ValidationError) as hata:
            catalog.delete_copy(copy)
        assert "status" in hata.value.message_dict

    def test_kayip_nusha_iletisi_dogru_yolu_gosterir(self) -> None:
        copy = nusha()
        Copy.objects.filter(pk=copy.pk).update(status=CopyStatus.LOST)
        copy.refresh_from_db()
        with pytest.raises(ValidationError) as hata:
            catalog.delete_copy(copy)
        ileti = " ".join(hata.value.message_dict["status"])
        assert "kayıttan düşme" in ileti


@pytest.mark.django_db
class TestBolumServisi:
    def test_dolu_bolum_silinemez(self) -> None:
        section = bolum(name="Tarih")
        eser(title="Nutuk", section=section)
        with pytest.raises(ValidationError) as hata:
            catalog.delete_section(section)
        assert "section" in hata.value.message_dict

    def test_bos_bolum_silinir(self) -> None:
        section = bolum(name="Coğrafya")
        catalog.delete_section(section)
        section.refresh_from_db()
        assert section.deleted_at is not None


@pytest.mark.django_db
class TestKomisyonKararTuru:
    def test_bagista_komisyon_karari_zorunludur(self) -> None:
        with pytest.raises(ValidationError) as hata:
            catalog.create_acquisition(method=AcquisitionMethod.DONATION, date=VARSAYILAN_TARIH)
        assert "commission_decision" in hata.value.message_dict

    def test_bagista_ayiklama_karari_kabul_edilmez(self) -> None:
        """D7: karar türü denetlenir."""
        with pytest.raises(ValidationError) as hata:
            catalog.create_acquisition(
                method=AcquisitionMethod.DONATION,
                date=VARSAYILAN_TARIH,
                commission_decision=karar(decision_type=CommissionDecisionType.WEEDING),
            )
        assert "commission_decision" in hata.value.message_dict

    def test_satin_almaya_ayiklama_karari_baglanamaz(self) -> None:
        with pytest.raises(ValidationError):
            catalog.create_acquisition(
                method=AcquisitionMethod.PURCHASE,
                date=VARSAYILAN_TARIH,
                commission_decision=karar(decision_type=CommissionDecisionType.WEEDING),
            )

    def test_satin_almaya_secim_karari_baglanabilir(self) -> None:
        acquisition = catalog.create_acquisition(
            method=AcquisitionMethod.PURCHASE,
            date=VARSAYILAN_TARIH,
            commission_decision=karar(decision_type=CommissionDecisionType.SELECTION),
        )
        assert acquisition.pk is not None

    def test_kullanilmis_kararin_turu_degistirilemez(self) -> None:
        from apps.kutuphane.services import commissions

        decision = karar(decision_type=CommissionDecisionType.DONATION_REVIEW)
        catalog.create_acquisition(
            method=AcquisitionMethod.DONATION,
            date=VARSAYILAN_TARIH,
            commission_decision=decision,
        )
        with pytest.raises(ValidationError) as hata:
            commissions.update_commission_decision(
                decision, decision_type=CommissionDecisionType.WEEDING
            )
        assert "decision_type" in hata.value.message_dict


@pytest.mark.django_db
class TestBagisOnKaydi:
    def _on_kayit(self) -> tuple[DonationIntake, list[int]]:
        intake = donations.create_intake(
            donor_name="Ayşe Yıldırım",
            received_date=date(2026, 9, 10),
            items=[
                {"title": "Çalıkuşu", "authors": "Reşat Nuri Güntekin", "copies": 2},
                {"title": "Eski Ansiklopedi", "authors": "Bilinmiyor", "copies": 1},
            ],
        )
        return intake, list(intake.items.values_list("pk", flat=True))

    def test_on_kayitta_nusha_acilmaz(self) -> None:
        self._on_kayit()
        assert Copy.objects.count() == 0
        assert Work.objects.count() == 0

    def test_karar_kabul_edilenleri_kataloglar_reddedilenleri_isaretler(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        sonuc = donations.apply_decision(
            intake,
            commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
            accepted_ids=[kalem_pkleri[0]],
            rejected={kalem_pkleri[1]: "Bilimsel değeri kalmamış."},
        )
        assert sonuc["accepted"] == 1
        assert sonuc["rejected"] == 1
        assert Work.objects.count() == 1
        assert Copy.objects.count() == 2  # "Nüsha Sayısı" 2
        ilk_nusha = Copy.objects.first()
        assert ilk_nusha is not None
        assert ilk_nusha.acquisition.method == AcquisitionMethod.DONATION

        intake.refresh_from_db()
        assert intake.status == DonationIntakeStatus.DECIDED
        kalemler = {k.pk: k for k in intake.items.all()}
        assert kalemler[kalem_pkleri[0]].decision == DonationItemDecision.ACCEPTED
        assert kalemler[kalem_pkleri[0]].work_id is not None
        assert kalemler[kalem_pkleri[1]].decision == DonationItemDecision.REJECTED
        assert kalemler[kalem_pkleri[1]].reject_reason == "Bilimsel değeri kalmamış."

    def test_karari_islenen_on_kayit_yeniden_kararlanmaz(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        decision = karar(decision_type=CommissionDecisionType.DONATION_REVIEW)
        donations.apply_decision(
            intake,
            commission_decision=decision,
            accepted_ids=kalem_pkleri,
        )
        with pytest.raises(ValidationError):
            donations.apply_decision(
                intake,
                commission_decision=decision,
                accepted_ids=kalem_pkleri,
            )

    def test_eksik_karar_butun_islemi_reddeder(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        with pytest.raises(ValidationError) as hata:
            donations.apply_decision(
                intake,
                commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
                accepted_ids=[kalem_pkleri[0]],
            )
        assert "items" in hata.value.message_dict
        assert Work.objects.count() == 0, "Eksik kararda hiçbir şey yazılmamalı"

    def test_ret_gerekcesi_zorunludur(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        with pytest.raises(ValidationError) as hata:
            donations.apply_decision(
                intake,
                commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
                accepted_ids=[kalem_pkleri[0]],
                rejected={kalem_pkleri[1]: "   "},
            )
        assert "rejected" in hata.value.message_dict

    def test_bagis_karari_disinda_bir_kararla_kataloglanmaz(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        with pytest.raises(ValidationError) as hata:
            donations.apply_decision(
                intake,
                commission_decision=karar(decision_type=CommissionDecisionType.SELECTION),
                accepted_ids=kalem_pkleri,
            )
        assert "commission_decision" in hata.value.message_dict

    def test_hepsi_reddedilirse_edinim_acilmaz(self) -> None:
        intake, kalem_pkleri = self._on_kayit()
        sonuc = donations.apply_decision(
            intake,
            commission_decision=karar(decision_type=CommissionDecisionType.DONATION_REVIEW),
            rejected={pk: "Kurum düzeyine uygun değil." for pk in kalem_pkleri},
        )
        assert sonuc["acquisition"] is None
        assert Copy.objects.count() == 0
