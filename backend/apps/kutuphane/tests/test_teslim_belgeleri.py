"""Teslim ve kayıp/hasar belgeleri (E15, E6 — tasarım §9-9, §9-11, §10).

- Teslim listesi: bir belge no'nun bütün satırları ya da bir şubenin/öğretmenin
  şu an teslimdeki nüshaları; şube tesliminde Dayanıklı Taşınırlar Listesi
  işlevi TMY 23/6'ya KIYASEN yazılır (madde metni depodan doğrulanır); teslim
  ödünç değildir; "zimmet"/"emanet" dili yoktur.
- Geri alma dökümü: geri alınan, teslimde kalan ve kayba dönüşen satırlar.
- Kayıp/hasar tutanağı: kişi adı şifreli alandan çözülür; Md. 19 alıntısı ve bedel
  YALNIZ ortaöğretimde (alıntı depodaki metinle birebir); tahsilat yapılmaz;
  "zayi", "telef", "borç", "ceza" ve disiplin dili yoktur; en uzun veride tek sayfa.

Sayfa bütçesi testleri gerçek uzunlukta veriyle koşar. Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

import inspect
import io
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import teslim_belgeleri as belgeler
from apps.kutuphane.models import CaseResolution, CaseType, LossDamageCase
from apps.kutuphane.services import deliveries, loss_damage
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.ortak import eser, nusha
from apps.kutuphane.tests.teslim_ortak import (
    kademe_yaz,
    nushalar,
    ogretmen,
    sube,
    teslim_et,
)
from apps.okul.models import SchoolConfig, SchoolLevel

pytestmark = pytest.mark.django_db

EN_UZUN_OKUL = ("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3)[:255]
EN_UZUN_AD = "Mümtazhan Gülşehriye Şükriyenur Ümmügülsüm"
EN_UZUN_SOYAD = "Büyükçekmeceoğulları Karamehmetoğlu Şahinbeyoğlu"
EN_UZUN_ESER = (
    "Uzun Adlı Örnek Kaynak: Çağdaş Türk Şiirinde Doğa, Şehir ve İnsan Üzerine "
    "Karşılaştırmalı Bir İnceleme — Birinci Cilt, Genişletilmiş Üçüncü Baskı"
)
#: Çeviri ve derleme künyeli gerçekçi uzun yazar alanı.
UZUN_YAZAR = (
    "Deneme Yazaroğlu; Hazırlayan: Örnek Derleyicioğlu, İkinci Hazırlayıcı; "
    "Çeviren: Üçüncü Çevirmenoğlu ve Dördüncü Çevirmen; Resimleyen: Beşinci Çizeroğlu"
)
#: Satır satır yazılmış, üst sınırdaki (500 karakter) sorumlu notu.
SATIRLI_NOT = "\n".join(["Kitap servis aracında unutuldu, aranıyor."] * 12)[:500]
YASAK_TESLIM = ("zimmet", "emanet", "ödünç verildi")
YASAK_TUTANAK = ("zayi", "telef", "borç", "ceza", "disiplin", "tahsil edil")

_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")


def _metin(icerik: bytes) -> str:
    ham = "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)
    return " ".join(_T_ARALIGI.sub("T", ham).split())


def _sayfa_sayisi(icerik: bytes) -> int:
    return len(PdfReader(io.BytesIO(icerik)).pages)


def _mevzuat(dosya: str) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / dosya
        if yol.is_file():
            return " ".join(yol.read_text(encoding="utf-8").split())
    pytest.fail(f"{dosya} bulunamadı.")


@pytest.fixture(autouse=True)
def okul() -> SchoolConfig:
    config = kademe_yaz(SchoolLevel.ORTAOGRETIM)
    config.school_name = "Örnek Anadolu Lisesi"
    config.district = "Örnek İlçe"
    config.principal_name = "Örnek Müdür"
    config.save()
    return config


# ============================================================ E15 teslim listesi


class TestTeslimListesi:
    def test_sube_teslim_listesi_dtl_islevi_kiyasen(self) -> None:
        sonuc = teslim_et(nushalar(3), section=sube(9, "A"))
        satirlar = belgeler.delivery_list_rows(document_no=sonuc.document_no)

        metin = _metin(belgeler.delivery_list_pdf(satirlar))

        assert "TESLİM LİSTESİ" in metin
        assert sonuc.document_no in metin
        assert "9/A sınıf kitaplığı" in metin
        assert "md. 23/6'ya kıyasen" in metin and "Dayanıklı Taşınırlar Listesinin" in metin
        assert "Teslim ödünç değildir." in metin
        assert "Sınıf kitaplığı sorumlusu" in metin
        for c in (d.copy for d in satirlar):
            assert barcode_module.format_barcode(c.barcode) in metin
        for sozcuk in YASAK_TESLIM:
            assert sozcuk not in metin.lower()

    def test_tmy_23_6_ortak_kullanim_alani_hukmu_depoda(self) -> None:
        tmy = _mevzuat("tasinir-mal-yonetmeligi.md")
        assert "ortak kullanım alanlarına Dayanıklı Taşınırlar Listesi düzenlenmek" in tmy

    def test_ogretmen_teslim_listesinde_ad_imzada(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Teslimalan")
        sonuc = teslim_et(nushalar(2), personnel=hoca)
        metin = _metin(
            belgeler.delivery_list_pdf(belgeler.delivery_list_rows(document_no=sonuc.document_no))
        )
        assert "Deneme Teslimalan" in metin
        assert "Teslim alan — Öğretmen" in metin
        assert "Dayanıklı Taşınırlar" not in metin

    def test_belge_no_geri_alinan_satirlari_da_kapsar_sube_yalniz_acik(self) -> None:
        kitaplar = nushalar(3)
        sonuc = teslim_et(kitaplar, section=sube(9, "A"))
        deliveries.take_back(kitaplar[0])

        belge = belgeler.delivery_list_rows(document_no=sonuc.document_no)
        acik = belgeler.delivery_list_rows(section=sube(9, "A"))

        assert len(belge) == 3
        assert {d.copy_id for d in acik} == {kitaplar[1].pk, kitaplar[2].pk}

    def test_birden_cok_belge_no_sutunu_ve_bos_secim(self) -> None:
        hoca = ogretmen()
        teslim_et(nushalar(1), personnel=hoca)
        teslim_et(nushalar(1), personnel=hoca)
        satirlar = belgeler.delivery_list_rows(personnel=hoca)
        baglam = belgeler.delivery_list_context(satirlar)

        assert baglam["show_document_column"] is True
        with pytest.raises(ValidationError, match="teslim kaydı yok"):
            belgeler.delivery_list_rows(section=sube(10, "B"))
        with pytest.raises(ValidationError, match="Belge no, şube ya da öğretmen"):
            belgeler.delivery_list_rows()

    def test_uzun_liste_sayfaya_bolunur_basliklar_yinelenir(self, okul: SchoolConfig) -> None:
        okul.school_name = EN_UZUN_OKUL
        okul.save()
        kitaplar = [odunc_nushasi(title=f"{EN_UZUN_ESER} {i}") for i in range(60)]
        sonuc = teslim_et(kitaplar, section=sube(12, "Ş"))
        pdf = belgeler.delivery_list_pdf(belgeler.delivery_list_rows(document_no=sonuc.document_no))

        sayfalar = [s.extract_text() or "" for s in PdfReader(io.BytesIO(pdf)).pages]
        assert len(sayfalar) >= 3
        barkodlar = [barcode_module.format_barcode(c.barcode) for c in kitaplar]
        tablolu = [s for s in sayfalar if any(b in s for b in barkodlar)]
        assert len(tablolu) >= 3
        for sayfa in tablolu:
            assert "Kaynak adı" in sayfa  # başlık satırı tablonun sürdüğü her sayfada
        assert all(any(b in s for s in sayfalar) for b in barkodlar)  # satır kaybolmaz
        assert "eslim eden" in sayfalar[-1]


# ============================================================ E15 geri alma dökümü


class TestGeriAlmaDokumu:
    def test_durumlar_ve_ozet(self) -> None:
        kitaplar = nushalar(3)
        sonuc = teslim_et(kitaplar, section=sube(9, "A"))
        deliveries.take_back(kitaplar[0])
        loss_damage.report_lost(copy=kitaplar[1])

        satirlar = belgeler.take_back_rows(document_no=sonuc.document_no)
        metin = _metin(belgeler.take_back_pdf(satirlar, document_no=sonuc.document_no))
        bugun = f"{timezone.localdate():%d.%m.%Y}"

        assert "GERİ ALMA DÖKÜMÜ" in metin
        assert f"Geri alındı · {bugun}" in metin
        assert f"Kayba dönüştü · {bugun}" in metin
        assert "Teslimde" in metin
        assert "1 kitap geri alındı · 1 kitap teslimde · 1 kitap kayba dönüştü" in metin

    def test_okutma_oturumunun_teslimleri(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Geriveren")
        kitaplar = nushalar(2)
        teslim_et(kitaplar, personnel=hoca)
        kapanan = [deliveries.take_back(c) for c in kitaplar]

        satirlar = belgeler.take_back_rows(delivery_ids=[d.pk for d in kapanan if d is not None])
        metin = _metin(belgeler.take_back_pdf(satirlar))

        assert "Geri alınan kitaplar" in metin
        assert "Deneme Geriveren" in metin and "Geri veren — Öğretmen" in metin
        with pytest.raises(ValidationError):
            belgeler.take_back_rows()


# ============================================================ E6 kayıp/hasar tutanağı


def _kayip_dosyasi(**alanlar: object) -> LossDamageCase:
    kisi = ogrenci(
        first_name=alanlar.pop("first_name", "Deneme"),
        last_name=alanlar.pop("last_name", "Kaybeden"),
        class_level=11,
        class_section="C",
    )
    uyelik = uye(kisi)
    return loss_damage.report_lost(
        copy=odunc_ver(
            uyelik, odunc_nushasi(title=str(alanlar.pop("title", "Deneme Kaynağı")))
        ).copy,
        membership=uyelik,
        responsible_note=str(alanlar.pop("note", "")),
    )


class TestKayipHasarTutanagi:
    def test_ortaogretimde_md19_ve_bedel_kaydi(self) -> None:
        dosya = _kayip_dosyasi(note="Kitap servis aracında unutuldu.")
        loss_damage.resolve_case(
            dosya, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("1234.5")
        )
        dosya.refresh_from_db()

        metin = _metin(belgeler.case_report_pdf(dosya))

        assert "KAYIP/HASAR TUTANAĞI" in metin
        assert "kaybolduğu" in metin
        assert "Deneme Kaybeden" in metin and "11/C" in metin
        assert "Kitap servis aracında unutuldu." in metin
        assert "Bedel belirlendi" in metin
        assert "1.234,50 TL (kayıt)" in metin
        bugun = f"{timezone.localdate():%d.%m.%Y}"
        assert f"{bugun} tarihinde belirlendi" in metin
        assert "teslim alındı" not in metin
        assert belgeler.MD19_ALINTI in metin
        assert belgeler.TAHSILAT_NOTU in metin
        assert "Okul müdürü" in metin and "Örnek Müdür" in metin
        for sozcuk in YASAK_TUTANAK:
            assert sozcuk not in metin.lower(), sozcuk

    def test_iki_bedel_adiminin_tarihleri_basilir(self) -> None:
        """25.09.2026 kararı: "Bedel belirlendi" ve "Bedel teslim alındı" ayrı tarihlidir."""
        dosya = _kayip_dosyasi()
        loss_damage.resolve_case(
            dosya, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("150")
        )
        LossDamageCase.objects.filter(pk=dosya.pk).update(
            price_determined_at=timezone.make_aware(datetime(2026, 9, 12, 10, 0))
        )
        loss_damage.resolve_case(dosya, resolution=CaseResolution.PRICE_RECEIVED)
        dosya.refresh_from_db()

        baglam = belgeler.case_report_context(dosya)
        satirlar = {r["label"]: r["value"] for r in baglam["resolution"]}
        bugun = f"{timezone.localdate():%d.%m.%Y}"
        assert satirlar["Durum"] == "Bedel teslim alındı"
        assert satirlar["Piyasa bedeli"] == (
            f"150,00 TL (kayıt); 12.09.2026 tarihinde belirlendi, {bugun} tarihinde teslim alındı"
        )
        assert "Çözüm tarihi" not in satirlar  # dosya okul için açık

        loss_damage.resolve_case(dosya, resolution=CaseResolution.CLOSED_SAME_REPURCHASED)
        dosya.refresh_from_db()
        metin = _metin(belgeler.case_report_pdf(dosya))
        assert "Bedelle aynısı alındı" in metin
        assert "12.09.2026 tarihinde belirlendi" in metin
        assert f"{bugun} tarihinde teslim alındı" in metin
        assert belgeler.TAHSILAT_NOTU in metin
        for sozcuk in YASAK_TUTANAK:
            assert sozcuk not in metin.lower(), sozcuk

    def test_md19_alintisi_depodaki_metinle_birebir(self) -> None:
        assert belgeler.MD19_ALINTI in _mevzuat("meb-okul-kutuphaneleri-yonetmeligi.md")

    @pytest.mark.parametrize("kademe", [SchoolLevel.ILKOKUL, SchoolLevel.ORTAOKUL, ""])
    def test_ilkokul_ve_ortaokulda_md19_ve_bedel_basilmaz(
        self, okul: SchoolConfig, kademe: str
    ) -> None:
        dosya = _kayip_dosyasi()
        okul.kademe = kademe
        okul.save()
        metin = _metin(belgeler.case_report_pdf(dosya))
        assert "Md. 19" not in metin
        assert "bedel" not in metin.lower()
        assert "tahsilat" not in metin.lower()

    def test_hasar_dosyasi_teslimden_ve_onarim_onerisi(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Sorumluhoca")
        kitap = odunc_nushasi(title="Deneme Hasarlı")
        teslim = teslim_et([kitap], personnel=hoca).deliveries[0]
        deliveries.take_back(kitap)
        teslim.refresh_from_db()
        dosya = loss_damage.open_damage_case(copy=kitap, delivery=teslim)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        dosya.refresh_from_db()

        metin = _metin(belgeler.case_report_pdf(dosya))

        assert dosya.case_type == CaseType.DAMAGED
        assert "hasar gördüğü" in metin
        assert "Deneme Sorumluhoca" in metin and teslim.document_no in metin
        assert "Kayıttan düşme" in metin and "önerildi" in metin

    def test_kisisiz_dosyada_ilgili_kisi_belirlenmedi(self) -> None:
        kitap = odunc_nushasi()
        dosya = loss_damage.open_damage_case(copy=kitap)
        metin = _metin(belgeler.case_report_pdf(dosya))
        assert "İlgili kişi Belirlenmedi" in metin

    @pytest.mark.parametrize("yol", ["odunc", "ogretmen_teslimi"])
    @pytest.mark.parametrize(
        "not_",
        [
            pytest.param("Açıklama " * 55, id="tek_satir_500"),
            # MetinAlani satır sonuna izin verir: 500 karakterlik satır satır not.
            pytest.param(SATIRLI_NOT, id="satirli_500"),
            pytest.param("\n".join(["a"] * 250), id="250_satir"),
        ],
    )
    @pytest.mark.parametrize("kademe", [SchoolLevel.ORTAOGRETIM, SchoolLevel.ILKOKUL])
    def test_gercek_uzunlukta_veride_tek_sayfa(
        self, okul: SchoolConfig, yol: str, not_: str, kademe: str
    ) -> None:
        """Sayfa bütçesi (CLAUDE.md §3): en uzun okul, kişi, kaynak adı, çeviri künyeli yazar,
        64 karakterlik TKYS kodu, 40 karakterlik belge no ve 500 karakterlik not."""
        okul.school_name = EN_UZUN_OKUL
        okul.principal_name = f"{EN_UZUN_AD} {EN_UZUN_SOYAD}"
        okul.kademe = kademe
        okul.save()
        kitap = nusha(eser(title=EN_UZUN_ESER, authors=UZUN_YAZAR), external_asset_ref="T" * 64)
        if yol == "odunc":
            kisi = ogrenci(
                first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD, class_level=11, class_section="C"
            )
            uyelik = uye(kisi)
            odunc_ver(uyelik, kitap)
            dosya = loss_damage.report_lost(copy=kitap, membership=uyelik, responsible_note=not_)
        else:
            hoca = ogretmen(first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD)
            teslim_et([kitap], personnel=hoca, document_no="B" * 40)
            dosya = loss_damage.report_lost(copy=kitap, responsible_note=not_)
        if kademe == SchoolLevel.ORTAOGRETIM:
            loss_damage.resolve_case(
                dosya,
                resolution=CaseResolution.PRICE_DETERMINED,
                market_price=Decimal("99999999.99"),
            )
            loss_damage.resolve_case(dosya, resolution=CaseResolution.PRICE_RECEIVED)
            # "Bedelle başka eser alındı" yalnız bedel teslim alındıktan sonra; en uzun çözüm
            # satırları (bedel satırı iki adımın tarihini taşır).
            loss_damage.resolve_case(dosya, resolution=CaseResolution.CLOSED_OTHER_REPURCHASED)
        else:
            loss_damage.resolve_case(dosya, resolution=CaseResolution.WRITE_OFF_PROPOSED)
        dosya.refresh_from_db()

        assert _sayfa_sayisi(belgeler.case_report_pdf(dosya)) == 1

    def test_notun_satir_sonlari_tutanakta_bosluga_iner(self) -> None:
        dosya = _kayip_dosyasi(note="Birinci satır.\n\nİkinci   satır.")
        baglam = belgeler.case_report_context(dosya)
        aciklama = [r["value"] for r in baglam["person"] if r["label"] == "Açıklama"]
        assert aciklama == ["Birinci satır. İkinci satır."]

    def test_alan_sinirindaki_veride_imzalar_cozumden_ayrilmaz(self, okul: SchoolConfig) -> None:
        """500 karakterlik kaynak adı ve yazarda tutanak taşabilir; ÇÖZÜM bölümü, Md. 19
        alıntısı ve imzalar tek bölünmez kutudadır — imzalar tek başına bir sayfaya düşmez."""
        okul.school_name = EN_UZUN_OKUL
        okul.principal_name = f"{EN_UZUN_AD} {EN_UZUN_SOYAD}"
        okul.save()
        kitap = nusha(
            eser(
                title=("Uzun Adlı Örnek Kaynak " * 25)[:500], authors=("Deneme Yazar; " * 40)[:500]
            ),
            external_asset_ref="T" * 64,
        )
        hoca = ogretmen(first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD)
        teslim_et([kitap], personnel=hoca, document_no="B" * 40)
        dosya = loss_damage.report_lost(copy=kitap, responsible_note=SATIRLI_NOT)
        loss_damage.resolve_case(
            dosya, resolution=CaseResolution.PRICE_DETERMINED, market_price=Decimal("99999999.99")
        )
        loss_damage.resolve_case(dosya, resolution=CaseResolution.PRICE_RECEIVED)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.CLOSED_OTHER_REPURCHASED)
        dosya.refresh_from_db()

        sayfalar = PdfReader(io.BytesIO(belgeler.case_report_pdf(dosya))).pages
        for sayfa in sayfalar:
            metin = " ".join((sayfa.extract_text() or "").split())
            if "Okul müdürü" in metin:
                assert "ÇÖZÜM" in metin and "Bedelle başka eser alındı" in metin


def test_turkce_para_bicimi() -> None:
    assert belgeler.turkish_money(Decimal("1234.5")) == "1.234,50 TL"
    assert belgeler.turkish_money(Decimal("12")) == "12,00 TL"


def test_profil_yasagi_belge_modulu_konu_ve_siniflamaya_dokunmaz() -> None:
    kod = inspect.getsource(belgeler)
    for kelime in ("subject", "classification", "dewey", "work__section", "copy__section"):
        assert kelime not in kod
