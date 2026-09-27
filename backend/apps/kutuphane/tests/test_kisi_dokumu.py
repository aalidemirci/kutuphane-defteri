"""Kişi dökümü (KVKK md. 11) — tasarım §8.4; F10 kod kapısı "kişi dökümü yalnız yönetici
kipinde".

Sabitlenenler: okul no ile kör indeksten TAM eşleşme (yazım farkı erir, ön ek aranmaz) ·
aynı numaralı ayrılmış ve aktif öğrenci ayrı aday · döküm YALNIZ seçilen kişinin kayıtlarını
taşır · görevli kipinde servis ve uç reddeder · indirme adında kişi adı yok · KVKK alıntıları
depodaki metinle birebir.

Bütün kişi verileri uydurmadır (CLAUDE.md §2-12).
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.kutuphane import kisi_dokumu as kd
from apps.kutuphane.models import CaseResolution
from apps.kutuphane.services import loss_damage, yonetici_kipi
from apps.kutuphane.tests.disa_aktarim_ortak import madde, pdf_metni
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, personel, uye
from apps.kutuphane.tests.teslim_ortak import teslim_et
from apps.okul.kip import KIP
from apps.okul.models import StudentStatus

pytestmark = pytest.mark.django_db

_KVKK = "6698-kvkk.md"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


class TestAdaylar:
    def test_okul_no_kor_indeksle_tam_eslesir(self) -> None:
        kisi = ogrenci(first_name="Deneme", last_name="Arananoğlu", student_number="700123")
        ogrenci(first_name="Deneme", last_name="Başkaoğlu", student_number="7001234")
        (aday,) = kd.person_candidates(school_no="0700123")
        assert (aday["kind"], aday["id"]) == ("student", kisi.pk)
        assert kd.person_candidates(school_no="7001") == []  # ön ek araması yok

    def test_ayni_numarali_ayrilmis_ve_aktif_ayri_adaydir(self) -> None:
        eski = ogrenci(first_name="Deneme", last_name="Eskioğlu", student_number="700555")
        eski.status = StudentStatus.LEFT
        eski.save()
        yeni = ogrenci(first_name="Deneme", last_name="Yenioğlu", student_number="700555")
        adaylar = kd.person_candidates(school_no="700555")
        assert {a["id"] for a in adaylar} == {eski.pk, yeni.pk}
        assert {a["status_display"] for a in adaylar} == {"Aktif", "Ayrıldı"}

    def test_ad_aramasi_ogrenci_ve_personel(self) -> None:
        ogrenci(first_name="Denemeortak", last_name="Öğrencioğlu")
        personel(first_name="Denemeortak", last_name="Personeloğlu")
        adaylar = kd.person_candidates(name="denemeortak")
        assert {a["kind"] for a in adaylar} == {"student", "personnel"}

    def test_bos_arama_reddedilir(self) -> None:
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            kd.person_candidates()


class TestDokum:
    def test_yalniz_secilen_kisinin_kayitlari(self) -> None:
        kisi = ogrenci(first_name="Denemebir", last_name="Secilenoğlu", student_number="700777")
        baska = ogrenci(first_name="Denemeiki", last_name="Baskaoğlu", student_number="700778")
        uyelik = uye(kisi)
        odunc_ver(uyelik, odunc_nushasi(title="Seçilenin Kitabı"))
        kayip_odunc = odunc_ver(uyelik, odunc_nushasi(title="Seçilenin Kayıp Kitabı"))
        loss_damage.report_lost(copy=kayip_odunc.copy)
        odunc_ver(uye(baska), odunc_nushasi(title="Başkasının Kitabı"))
        metin = pdf_metni(kd.person_record_pdf(kd.KIND_STUDENT, kisi.pk))
        assert "KİŞİ DÖKÜMÜ" in metin
        assert "Denemebir Secilenoğlu" in metin and "700777" in metin
        assert "Seçilenin Kitabı" in metin and "Seçilenin Kayıp Kitabı" in metin
        assert uyelik.card_no in metin
        assert "Başkasının Kitabı" not in metin and "Baskaoğlu" not in metin
        assert str(CaseResolution.PENDING.label) in metin

    def test_personelde_teslim_kayitlari(self) -> None:
        ogretmen = personel(first_name="Denemeteslim", last_name="Öğretmenoğlu")
        teslim_et([odunc_nushasi(title="Teslim Edilen Kitap")], personnel=ogretmen)
        metin = pdf_metni(kd.person_record_pdf(kd.KIND_PERSONNEL, ogretmen.pk))
        assert "ÖĞRETMENE TESLİM" in metin and "Teslim Edilen Kitap" in metin

    def test_ogrencinin_uyeligiyle_acilan_teslim_dosyasi_ogretmenin_dokumune_girmez(
        self,
    ) -> None:
        """F10 düzeltme turu: tek kural (önce üyelik) — başkasının dosyası ve notu verilmez.

        Teslimdeki kitabı öğrenci kaybeder, dosya öğrencinin üyeliğiyle açılır: dosyada hem
        üyelik hem teslim durur. Dosya öğrencinindir; öğretmenin dökümüne girmez.
        """
        ogretmen = personel(first_name="Denemeteslim", last_name="Öğretmenoğlu")
        ogr = ogrenci(first_name="Denemeöğrenci", last_name="Kaybedenoğlu", student_number="700991")
        ogr_uyelik = uye(ogr)
        nusha = odunc_nushasi(title="Sınıftaki Kitap")
        teslim_et([nusha], personnel=ogretmen)
        dosya = loss_damage.report_lost(
            copy=nusha, membership=ogr_uyelik, responsible_note="Öğrencinotu kaybettiğini söyledi"
        )
        assert dosya.membership_id == ogr_uyelik.pk and dosya.delivery_id is not None
        ogretmen_metni = pdf_metni(kd.person_record_pdf(kd.KIND_PERSONNEL, ogretmen.pk))
        assert "Öğrencinotu" not in ogretmen_metni
        assert "Kayıp ya da hasar dosyası yok." in ogretmen_metni
        # Teslim kaydı öğretmenindir ve dökümünde kalır.
        assert "Sınıftaki Kitap" in ogretmen_metni
        ogrenci_metni = pdf_metni(kd.person_record_pdf(kd.KIND_STUDENT, ogr.pk))
        assert "Öğrencinotu" in ogrenci_metni

    def test_uyeliksiz_teslim_dosyasi_ogretmenin_dokumune_girer(self) -> None:
        ogretmen = personel(first_name="Denemeteslim", last_name="Sorumluoğlu")
        nusha = odunc_nushasi(title="Öğretmendeki Kitap")
        teslim_et([nusha], personnel=ogretmen)
        loss_damage.report_lost(copy=nusha, responsible_note="Öğretmennotu dolapta bulunamadı")
        metin = pdf_metni(kd.person_record_pdf(kd.KIND_PERSONNEL, ogretmen.pk))
        assert "Öğretmennotu" in metin

    def test_kapsam_notu_serbest_metnin_aranmadigini_soyler(self) -> None:
        kisi = ogrenci()
        baglam = kd.person_record_context(kd.KIND_STUDENT, kisi.pk)
        assert kd.KAPSAM_NOTU in baglam["notes"]
        assert "aranmaz" in kd.KAPSAM_NOTU and "sorumlu notu" in kd.KAPSAM_NOTU

    def test_tarih_ve_bedel_bolunmeden_basilir(self) -> None:
        """Gerçek uzunlukta veriyle (CLAUDE.md §3): %10'luk sütun tarihi, %9'luk sütun
        beş haneli bedeli sözcük ortasından bölüyordu."""
        from decimal import Decimal

        from django.template.loader import render_to_string

        from apps.kutuphane.tests.disa_aktarim_ortak import hucre_satirlari, yatay_tasmalar
        from apps.kutuphane.tests.teslim_ortak import kademe_yaz
        from apps.okul.models import SchoolLevel

        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        kisi = ogrenci(first_name="Deneme", last_name="Tarihoğlu", student_number="700992")
        uyelik = uye(kisi)
        odunc = odunc_ver(uyelik, odunc_nushasi(title="Kısa Ad"))
        kayip = odunc_ver(uyelik, odunc_nushasi(title="Kısa Kayıp"))
        dosya = loss_damage.report_lost(copy=kayip.copy)
        loss_damage.resolve_case(
            dosya, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("12345.50")
        )
        html = render_to_string(kd.SABLON, kd.person_record_context(kd.KIND_STUDENT, kisi.pk))
        assert yatay_tasmalar(html) == []
        sozcukler = {s for satir in hucre_satirlari(html) for s in satir.split()}
        for deger in (f"{odunc.due_date:%d.%m.%Y}", f"{dosya.reported_on:%d.%m.%Y}", "12.345,50"):
            assert deger in sozcukler, (deger, sorted(sozcukler))

    def test_gorevli_kipinde_servis_reddeder(self) -> None:
        kisi = ogrenci()
        KIP.gorevliye_gec()
        with pytest.raises(yonetici_kipi.KipYetkisiz):
            kd.person_record_context(kd.KIND_STUDENT, kisi.pk)
        with pytest.raises(yonetici_kipi.KipYetkisiz):
            kd.person_candidates(school_no="1")

    def test_indirme_adinda_kisi_adi_yok(self) -> None:
        assert kd.person_record_filename().startswith("Kişi-dökümü_")

    def test_kvkk_alintilari_depodaki_metinle_birebir(self) -> None:
        on_bir = madde(_KVKK, 11)
        assert f"a) {kd.KVKK_11_A}" in on_bir and f"b) {kd.KVKK_11_B}" in on_bir
        assert kd.KVKK_13_2 in madde(_KVKK, 13)


class TestUclar:
    def test_arama_govdede_ve_dokum_pdf(self, istemci: APIClient) -> None:
        kisi = ogrenci(first_name="Denemeuc", last_name="Aramaoğlu", student_number="700999")
        yanit = istemci.post(
            reverse("library-report-person-record-search"), {"school_no": "700999"}, format="json"
        )
        assert yanit.status_code == 200
        (aday,) = yanit.json()["results"]
        pdf = istemci.get(
            reverse("library-report-person-record", kwargs={"tur": aday["kind"], "pk": aday["id"]})
        )
        assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
        assert pdf["Cache-Control"] == "no-store"
        assert "Aramaoğlu" not in pdf["Content-Disposition"]
        del kisi

    def test_gorevli_kipinde_403(self, istemci: APIClient) -> None:
        kisi = ogrenci()
        KIP.gorevliye_gec()
        yanit = istemci.get(
            reverse("library-report-person-record", kwargs={"tur": "student", "pk": kisi.pk})
        )
        assert yanit.status_code == 403 and yanit.json()["code"] == "kip_yetkisiz"
        yanit = istemci.post(
            reverse("library-report-person-record-search"), {"school_no": "1"}, format="json"
        )
        assert yanit.status_code == 403

    def test_tanimsiz_tur_404_bulunamayan_kisi_400(self, istemci: APIClient) -> None:
        assert (
            istemci.get(
                reverse("library-report-person-record", kwargs={"tur": "veli", "pk": 1})
            ).status_code
            == 404
        )
        yanit = istemci.get(
            reverse("library-report-person-record", kwargs={"tur": "student", "pk": 999999})
        )
        assert yanit.status_code == 400
