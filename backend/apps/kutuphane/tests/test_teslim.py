"""Toplu teslim ve geri alma servisleri (F7 — U11, tasarım §9-11, §4.4, §6.2, §6.4).

Kod kapısı maddeleri: **teslimde sayı sınırı yok, ödünçte var**; teslim verme yalnız
yönetici kipinde; geri alma okutmayla ve görevli kipinde de; nüsha durumu
"Sınıf kitaplığında"; açık teslim açık yükümlülüktür (kişi silinemez), şube
silinemez; birleştirmede teslimler taşınır. Tek açık kayıt kuralının yarış
testleri `test_teslim_tek_acik_kayit.py`'dedir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.kutuphane import selectors_dolasim, selectors_teslim
from apps.kutuphane.models import (
    CopyStatus,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    LoanStatus,
)
from apps.kutuphane.serializers_teslim import ADMIN_TAKE_BACK_FIELDS, STAFF_TAKE_BACK_FIELDS
from apps.kutuphane.services import circulation, deliveries, masa, memberships
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import (
    etkin_yil,
    nushalar,
    ogretmen,
    sube,
    tazele_nusha,
    tazele_teslim,
    teslim_et,
)
from apps.okul.kip import KIP
from apps.okul.models import MemberKind, SchoolYear
from apps.okul.services import persons, sections

pytestmark = pytest.mark.django_db


# ============================================================ teslim — alan ve kurallar


class TestTeslimAlani:
    def test_sube_teslimi_nushayi_sinif_kitapliginda_yapar(self) -> None:
        kitaplar = nushalar(3)
        sonuc = teslim_et(kitaplar, section=sube(9, "B"))

        assert sonuc.recipient_kind == DeliveryRecipientKind.SECTION
        assert len(sonuc.deliveries) == 3
        assert {tazele_nusha(c).status for c in kitaplar} == {CopyStatus.DELIVERED}
        assert {t.document_no for t in sonuc.deliveries} == {sonuc.document_no}
        assert selectors_teslim.delivery_recipient_label(sonuc.deliveries[0]) == "9/B"

    def test_ogretmene_teslim(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Sınıföğretmeni")
        sonuc = teslim_et(nushalar(2), personnel=hoca)

        assert sonuc.recipient_kind == DeliveryRecipientKind.TEACHER
        assert all(t.personnel_id == hoca.pk and t.section_id is None for t in sonuc.deliveries)
        assert "Sınıföğretmeni" in selectors_teslim.delivery_recipient_label(sonuc.deliveries[0])

    def test_alan_ikisi_birden_ya_da_hicbiri_olamaz(self) -> None:
        with pytest.raises(ValidationError, match="şube ya da bir öğretmen"):
            teslim_et(nushalar(1), section=sube(), personnel=ogretmen())
        with pytest.raises(ValidationError, match="şube ya da bir öğretmen"):
            deliveries.deliver(barcodes=[odunc_nushasi().barcode])

    def test_diger_personele_ve_ayrilmis_ogretmene_teslim_yapilmaz(self) -> None:
        memur = ogretmen(member_kind=MemberKind.STAFF)
        with pytest.raises(ValidationError, match="diğer personele teslim yapılmaz"):
            teslim_et(nushalar(1), personnel=memur)

        ayrilan = ogretmen()
        persons.leave_personnel(ayrilan)
        with pytest.raises(ValidationError, match="Ayrılmış personele"):
            teslim_et(nushalar(1), personnel=ayrilan)

    def test_gecen_yilin_subesine_teslim_yapilmaz(self) -> None:
        etkin_yil()
        eski_yil = SchoolYear.objects.create(
            name="2025-2026", start_date=date(2025, 9, 8), end_date=date(2026, 6, 26)
        )
        with pytest.raises(ValidationError, match="etkin ders yılının şubesine"):
            teslim_et(nushalar(1), section=sube(yil=eski_yil))


class TestSayiSiniriYok:
    """Kod kapısı: teslimde sayı sınırı yok, ödünçte var (§9-11, Md. 18)."""

    def test_ogretmene_bes_kitaptan_fazlasi_teslim_edilir_ve_odunc_hakki_eksilmez(self) -> None:
        hoca = ogretmen()
        uyelik = uye(hoca)
        once = selectors_dolasim.remaining_quota(uyelik)

        sonuc = teslim_et(nushalar(12), personnel=hoca)

        assert len(sonuc.deliveries) == 12
        assert selectors_dolasim.remaining_quota(uyelik) == once == 5
        # Ödünçte sınır işler: beşinciden sonrası reddedilir.
        for _ in range(5):
            odunc_ver(uyelik)
        with pytest.raises(DolasimReddi) as ret:
            odunc_ver(uyelik)
        assert ret.value.code == circulation.RED_SINIR

    def test_subeye_yuzlerce_kitap_tek_islemde_teslim_edilir(self) -> None:
        sonuc = teslim_et(nushalar(40))
        assert len(sonuc.deliveries) == 40

    def test_tek_teslimin_ust_siniri_bir_islem_sigortasidir(self) -> None:
        with pytest.raises(ValidationError, match="en çok"):
            deliveries.deliver(
                barcodes=["2026000001"] * (deliveries.MAX_DELIVERY_BATCH + 1), section=sube()
            )


class TestTopluTeslimTekIslem:
    def test_teslim_edilemeyen_kitap_varsa_hicbiri_teslim_edilmez(self) -> None:
        rafta = nushalar(2)
        oduncte = odunc_ver(uye()).copy

        with pytest.raises(ValidationError) as hata:
            teslim_et([*rafta, oduncte])

        gerekceler = hata.value.message_dict["barcodes"]
        assert any("Ödünçte — teslim edilemez." in g for g in gerekceler)
        assert not Delivery.objects.exists()
        assert {tazele_nusha(c).status for c in rafta} == {CopyStatus.AVAILABLE}

    @pytest.mark.parametrize(
        "durum",
        [CopyStatus.IN_REPAIR, CopyStatus.LOST, CopyStatus.WITHDRAWN_WEEDED],
    )
    def test_rafta_olmayan_nusha_teslim_edilmez(self, durum: str) -> None:
        kitap = odunc_nushasi()
        type(kitap).objects.filter(pk=kitap.pk).update(status=durum)
        with pytest.raises(ValidationError) as hata:
            teslim_et([kitap])
        assert "teslim edilemez" in " ".join(hata.value.message_dict["barcodes"])

    def test_danisma_kaynagi_teslim_edilebilir_cunku_teslim_odunc_degildir(self) -> None:
        danisma = odunc_nushasi(is_reference=True)
        sonuc = teslim_et([danisma])
        assert tazele_nusha(danisma).status == CopyStatus.DELIVERED
        assert len(sonuc.deliveries) == 1

    def test_tekrar_okutulan_kitap_bir_kez_sayilir(self) -> None:
        kitap = odunc_nushasi()
        sonuc = deliveries.deliver(
            barcodes=[kitap.barcode, f"{kitap.barcode[:4]}-{kitap.barcode[4:]}", kitap.barcode],
            section=sube(),
        )
        assert len(sonuc.deliveries) == 1

    def test_nusha_olmayan_okutma_ham_kodu_yankilamaz(self) -> None:
        kart = memberships.issue_card_number()
        with pytest.raises(ValidationError) as hata:
            deliveries.deliver(barcodes=[odunc_nushasi().barcode, kart], section=sube())
        metin = " ".join(hata.value.message_dict["barcodes"])
        assert "2. okutma" in metin
        assert kart not in metin


class TestBelgeNoVeTarihler:
    def test_belge_no_yil_sirasiyla_verilir_ve_tekrar_verilmez(self) -> None:
        bugun = timezone.localdate()
        ilk = teslim_et(nushalar(1))
        ikinci = teslim_et(nushalar(1))
        assert ilk.document_no == f"{bugun.year}/1"
        assert ikinci.document_no == f"{bugun.year}/2"

    def test_elle_yazilan_belge_no_tekrar_kullanilamaz(self) -> None:
        teslim_et(nushalar(1), document_no="E-2026/15")
        with pytest.raises(ValidationError, match="başka bir teslimde kullanılmış"):
            teslim_et(nushalar(1), document_no="E-2026/15")

    def test_elle_yazilan_kaliptaki_numara_sayaci_ileri_goturur(self) -> None:
        yil = timezone.localdate().year
        teslim_et(nushalar(1), document_no=f"{yil}/9")
        assert teslim_et(nushalar(1)).document_no == f"{yil}/10"

    def test_beklenen_donus_varsayilani_ders_yili_sonudur(self) -> None:
        yil = etkin_yil()
        sonuc = teslim_et(nushalar(1))
        assert sonuc.expected_return == yil.end_date

    def test_beklenen_donus_teslimden_once_olamaz_ve_teslim_ileri_tarihli_olamaz(self) -> None:
        bugun = timezone.localdate()
        with pytest.raises(ValidationError, match="Beklenen dönüş"):
            teslim_et(nushalar(1), expected_return=bugun - timedelta(days=1))
        with pytest.raises(ValidationError, match="bugünden sonra"):
            teslim_et(nushalar(1), delivered_on=bugun + timedelta(days=1))

    def test_db_kisitlari_alan_ve_kapanis_zamanlarini_tutar(self) -> None:
        teslim = teslim_et(nushalar(1)).deliveries[0]
        with pytest.raises(IntegrityError):
            Delivery.objects.filter(pk=teslim.pk).update(section=None)


# ============================================================ kip


def test_teslim_verme_gorevli_kipinde_yapilamaz() -> None:
    kitap = odunc_nushasi()
    sube_ = sube()
    KIP.gorevliye_gec()
    with pytest.raises(KipYetkisiz):
        deliveries.deliver(barcodes=[kitap.barcode], section=sube_)
    with pytest.raises(KipYetkisiz):
        deliveries.delivery_check_scan(kitap.barcode)


# ============================================================ geri alma


class TestGeriAlma:
    def test_geri_alma_okutmasi_teslimi_kapatir_nushayi_rafa_dondurur(self) -> None:
        teslim = teslim_et(nushalar(1)).deliveries[0]

        sonuc = deliveries.take_back_scan(teslim.copy.barcode, staff=False)

        assert sonuc["result"] == deliveries.GERI_ALINDI
        assert sonuc["message"] == "Geri alındı."
        assert sonuc["delivery"]["recipient_label"] == "9/A"
        guncel = tazele_teslim(teslim)
        assert guncel.status == DeliveryStatus.RETURNED and guncel.returned_at is not None
        assert tazele_nusha(teslim.copy).status == CopyStatus.AVAILABLE

    def test_gorevli_kipinde_yanit_daralir_teslim_alanin_kimligi_yok(self) -> None:
        hoca = ogretmen(last_name="Gizliöğretmenadı")
        teslim = teslim_et(nushalar(1), personnel=hoca).deliveries[0]
        KIP.gorevliye_gec()

        sonuc = deliveries.take_back_scan(teslim.copy.barcode, staff=True)

        assert tuple(sonuc) == STAFF_TAKE_BACK_FIELDS
        assert tuple(sonuc["copy"]) == ("barcode", "barcode_display", "work_title")
        assert "Gizliöğretmenadı" not in str(sonuc)
        assert tazele_teslim(teslim).status == DeliveryStatus.RETURNED

    def test_yonetici_yaniti_alan_listesi(self) -> None:
        teslim = teslim_et(nushalar(1)).deliveries[0]
        sonuc = deliveries.take_back_scan(teslim.copy.barcode, staff=False)
        assert tuple(sonuc) == ADMIN_TAKE_BACK_FIELDS

    def test_teslimde_olmayan_kitap_okutulunca_durum_iletisi(self) -> None:
        rafta = odunc_nushasi()
        oduncte = odunc_ver(uye()).copy

        raf = deliveries.take_back_scan(rafta.barcode, staff=True)
        odunc = deliveries.take_back_scan(oduncte.barcode, staff=True)

        assert raf["result"] == deliveries.TESLIMDE_DEGIL
        assert raf["message"] == "Bu kitap teslimde değil (Rafta)."
        assert odunc["message"].startswith("Bu kitap teslimde değil (Ödünçte).")
        assert tazele_nusha(oduncte).status == CopyStatus.ON_LOAN

    def test_nusha_olmayan_kod_reddedilir(self) -> None:
        sonuc = deliveries.take_back_scan("9786050000001", staff=True)
        assert sonuc["result"] == deliveries.REDDEDILDI
        assert sonuc["copy"] is None

    def test_toplu_geri_alma_okuyucu_kuyrugu_sirayla(self) -> None:
        teslimler = teslim_et(nushalar(3)).deliveries
        kodlar = [t.copy.barcode for t in teslimler] + ["bozuk"]

        sonuclar = deliveries.take_back_scans(kodlar, staff=False)

        assert [s["result"] for s in sonuclar] == ["returned"] * 3 + ["rejected"]
        assert not Delivery.objects.filter(status=DeliveryStatus.OPEN).exists()

    def test_geri_alinan_nusha_yeniden_teslim_ve_odunc_verilebilir(self) -> None:
        kitap = odunc_nushasi()
        teslim_et([kitap])
        deliveries.take_back(kitap)
        teslim_et([kitap])
        deliveries.take_back(kitap)
        loan = odunc_ver(uye(), tazele_nusha(kitap))
        assert loan.status == LoanStatus.OPEN
        assert Delivery.objects.filter(copy=kitap).count() == 2


# ============================================================ masa (§7.3)


class TestMasa:
    def test_masada_teslimdeki_nusha_okutulunca_sinif_kitapliginda_iletisi(self) -> None:
        kitap = teslim_et(nushalar(1)).deliveries[0].copy

        iade = masa.iade_okut(kitap.barcode, staff=True)
        durum = masa.durum_sorgula(kitap.barcode, staff=True)

        assert iade["result"] == masa.ODUNCTE_DEGIL
        assert iade["message"] == "Sınıf kitaplığında."
        assert durum["message"] == "Sınıf kitaplığında."
        assert tazele_nusha(kitap).status == CopyStatus.DELIVERED

    def test_teslimdeki_nusha_odunc_verilmez(self) -> None:
        kitap = teslim_et(nushalar(1)).deliveries[0].copy
        with pytest.raises(DolasimReddi) as ret:
            odunc_ver(uye(), tazele_nusha(kitap))
        assert ret.value.code == circulation.RED_ODUNC_VERILMEZ
        assert "Sınıf kitaplığında" in ret.value.message


# ============================================================ yükümlülük (§6.4)


class TestYukumluluk:
    def test_acik_teslimi_olan_ogretmen_silinemez_ve_yukumluluk_listelenir(self) -> None:
        hoca = ogretmen()
        teslim_et(nushalar(2), personnel=hoca)

        assert persons.open_obligations(hoca) == ["2 açık teslim var."]
        with pytest.raises(ValidationError, match="açık teslim"):
            persons.delete_personnel(hoca)

    def test_kapanmis_teslim_de_kullanici_silmesini_engeller(self) -> None:
        hoca = ogretmen()
        teslim = teslim_et(nushalar(1), personnel=hoca).deliveries[0]
        deliveries.take_back(teslim.copy)

        assert persons.open_obligations(hoca) == []
        with pytest.raises(ValidationError, match="teslim yapılmış"):
            persons.delete_personnel(hoca)

    def test_ayrilan_ogretmenin_acik_teslimi_yukumluluk_olarak_kalir(self) -> None:
        hoca = ogretmen()
        teslim_et(nushalar(1), personnel=hoca)
        persons.leave_personnel(hoca)

        assert persons.open_obligations(hoca) == ["1 açık teslim var."]
        assert Delivery.objects.filter(personnel=hoca, status=DeliveryStatus.OPEN).count() == 1

    def test_ogrencinin_teslim_yukumlulugu_olmaz(self) -> None:
        teslim_et(nushalar(1))
        assert selectors_teslim.open_deliveries_for_person(ogrenci()).count() == 0

    def test_birlestirmede_teslimler_hedefe_tasinir(self) -> None:
        eski = ogretmen(last_name="Eskisoyadı")
        yeni = ogretmen(last_name="Yenisoyadı")
        teslim_et(nushalar(2), personnel=eski)
        kapanan = teslim_et(nushalar(1), personnel=eski).deliveries[0]
        deliveries.take_back(kapanan.copy)

        persons.merge_personnel(eski, yeni)

        assert Delivery.objects.filter(personnel=yeni).count() == 3
        assert persons.open_obligations(yeni) == ["2 açık teslim var."]

    def test_acik_teslimi_olan_sube_silinemez_geri_alininca_silinir(self) -> None:
        sinif = sube(10, "C")
        teslim = teslim_et(nushalar(1), section=sinif).deliveries[0]

        with pytest.raises(ValidationError, match="açık teslim"):
            sections.delete_class_section(sinif)
        deliveries.take_back(teslim.copy)
        sections.delete_class_section(sinif)
        sinif.refresh_from_db()
        assert sinif.deleted_at is not None

    def test_sube_tesliminden_dogan_cozulmemis_dosya_subeyi_silinmekten_korur(self) -> None:
        """F7 düzeltme turu: şube teslimi kayba dönüştüyse dosya şubenin açık işidir."""
        from apps.kutuphane import selectors_ilisik
        from apps.kutuphane.models import CaseResolution
        from apps.kutuphane.services import loss_damage

        sinif = sube(10, "Q")
        teslim = teslim_et(nushalar(1), section=sinif).deliveries[0]
        dosya = loss_damage.report_lost(copy=teslim.copy)

        assert [s.label for s in selectors_ilisik.section_delivery_rows()] == ["10/Q"]
        with pytest.raises(ValidationError, match="1 çözülmemiş kayıp/hasar dosyası"):
            sections.delete_class_section(sinif)
        sinif.refresh_from_db()
        assert sinif.deleted_at is None

        loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)
        sections.delete_class_section(sinif)
        sinif.refresh_from_db()
        assert sinif.deleted_at is not None

    def test_sube_tesliminde_uyeye_baglanan_dosya_subeyi_tutmaz(self) -> None:
        """Dosyada üyelik varsa dosya o üyenindir (tek kişi bağı kuralı); şube serbesttir."""
        from apps.kutuphane.services import loss_damage

        sinif = sube(10, "R")
        teslim = teslim_et(nushalar(1), section=sinif).deliveries[0]
        uyelik = uye(ogrenci())
        loss_damage.report_lost(copy=teslim.copy, membership=uyelik)

        assert persons.open_obligations(uyelik.person) == ["1 çözülmemiş kayıp/hasar dosyası var."]
        sections.delete_class_section(sinif)

    def test_acik_teslim_birlestirmede_diger_personele_gecmez(self) -> None:
        """F7 düzeltme turu: kural 1 birleştirmede de geçerlidir; ret tek işlemdir."""
        from apps.kutuphane.tests.dolasim_ortak import personel

        eski = ogretmen(last_name="Eskisoyadı")
        memur = personel(last_name="Memursoyadı", member_kind=MemberKind.STAFF)
        teslim_et(nushalar(2), personnel=eski)

        with pytest.raises(ValidationError, match="2 açık teslimi var") as hata:
            persons.merge_personnel(eski, memur)
        assert "Eskisoyadı" not in str(hata.value) and "Memursoyadı" not in str(hata.value)
        # Hiçbir bağ taşınmadı; kaynak kayıt duruyor.
        assert Delivery.objects.filter(personnel=eski, status=DeliveryStatus.OPEN).count() == 2
        assert Delivery.objects.filter(personnel=memur).count() == 0
        eski.refresh_from_db()
        assert eski.deleted_at is None

        yeni = ogretmen(last_name="Yenisoyadı")
        persons.merge_personnel(eski, yeni)
        assert persons.open_obligations(yeni) == ["2 açık teslim var."]

    def test_kapanmis_teslim_birlestirmede_diger_personele_tasinir(self) -> None:
        from apps.kutuphane.tests.dolasim_ortak import personel

        eski = ogretmen(last_name="Eskisoyadı")
        memur = personel(last_name="Memursoyadı", member_kind=MemberKind.STAFF)
        kapanan = teslim_et(nushalar(1), personnel=eski).deliveries[0]
        deliveries.take_back(kapanan.copy)

        persons.merge_personnel(eski, memur)

        teslim = tazele_teslim(kapanan)
        assert teslim.personnel_id == memur.pk
        assert teslim.recipient_kind == DeliveryRecipientKind.TEACHER
