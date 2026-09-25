"""İlişik ve yıl sonu belgeleri (E5; E4'ün yıl sonu biçimi — tasarım §3, §8.3, §10).

- "Kütüphaneden ilişiği yoktur" belgesi: kişi başına tam bir sayfa (en uzun
  veriyle de), resmî antet her sayfada; yalnız açık işi olmayan kişiye basılır;
  madde atfı konum kalıbıyla ve Md. 18 alıntısı depodaki metinle BİREBİR; belge
  karne ya da diplomanın ön koşulu diye sunulmaz (sözcükler hiç geçmez), borç
  ve "ilişik kesme" dili yoktur.
- İlişik listesi: her sayfada dipnot; kaynak adı ve okul no basılmaz; şube
  teslimleri ayrı tabloda.
- Yıl sonu pusulası: kişinin BÜTÜN açık ödünçleri (gecikmemişler dahil); E4
  geometrisi; en uzun veride taşmaz; dış yüz kütüphaneyi anmaz.

Sayfa bütçesi testleri GERÇEK UZUNLUKTA veriyle koşar (CLAUDE.md §3). Bütün kişi
verileri uydurmadır.
"""

from __future__ import annotations

import inspect
import io
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import dolasim_belgeleri as e4
from apps.kutuphane import ilisik_belgeleri as belgeler
from apps.kutuphane import selectors_ilisik as ilisik
from apps.kutuphane.models import Loan
from apps.kutuphane.services import loss_damage
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    politika,
    uye,
)
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, nushalar, ogretmen, sube, teslim_et
from apps.okul.models import Personnel, SchoolConfig, SchoolLevel, Student
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

EN_UZUN_OKUL = ("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3)[:255]
EN_UZUN_ILCE = "Örnek Büyükçekmeceköyüzeri"
EN_UZUN_AD = "Mümtazhan Gülşehriye Şükriyenur Ümmügülsüm"
EN_UZUN_SOYAD = "Büyükçekmeceoğulları Karamehmetoğlu Şahinbeyoğlu"
EN_UZUN_ESER = (
    "Uzun Adlı Örnek Kaynak: Çağdaş Türk Şiirinde Doğa, Şehir ve İnsan Üzerine "
    "Karşılaştırmalı Bir İnceleme — Birinci Cilt, Genişletilmiş Üçüncü Baskı"
)
#: Belgede HİÇ geçmeyecek sözcükler (sözlük "İlişik"; §8.3).
YASAK_SOZCUKLER = ("karne", "diploma", "borç", "ilişik kesme", "ceza", "zimmet")

_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")


def _metin(icerik: bytes) -> str:
    ham = "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)
    return " ".join(_T_ARALIGI.sub("T", ham).split())


def _sayfa_metinleri(icerik: bytes) -> list[str]:
    return [
        " ".join(_T_ARALIGI.sub("T", s.extract_text() or "").split())
        for s in PdfReader(io.BytesIO(icerik)).pages
    ]


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
    config: SchoolConfig
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.school_name = "Örnek Anadolu Lisesi"
    config.district = "Örnek İlçe"
    config.province = "Örnek İl"
    config.principal_name = "Örnek Müdür"
    config.kademe = SchoolLevel.ORTAOGRETIM
    config.save()
    return config


def _uzun_okul(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.district = EN_UZUN_ILCE
    okul.principal_name = f"{EN_UZUN_AD} {EN_UZUN_SOYAD}"
    okul.save()


def _belge_satirlari(*kisiler: Student | Personnel) -> list[ilisik.ClearanceRow]:
    ogrenci_ids = [k.pk for k in kisiler if isinstance(k, Student)]
    personel_ids = [k.pk for k in kisiler if isinstance(k, Personnel)]
    rows, eksik = ilisik.persons_for_certificate(
        student_ids=ogrenci_ids, personnel_ids=personel_ids
    )
    belgeler.ensure_certifiable(rows, eksik)
    return rows


# ============================================================ E5 belge


class TestIlisigiYokturBelgesi:
    def test_ogrenci_belgesi_hukum_ve_kunye(self) -> None:
        kisi = ogrenci(
            first_name="Deneme",
            last_name="Mezun",
            class_level=12,
            class_section="B",
            student_number="1453",
        )
        metin = _metin(belgeler.certificate_pdf(_belge_satirlari(kisi)))

        assert belgeler.BELGE_BASLIGI in metin
        assert "Deneme Mezun" in metin and "1453" in metin and "12/B" in metin
        assert "Son sınıf" in metin
        # Bedeli teslim alınmış dosya okul için açık kalır (25.09.2026 kararı): hüküm
        # "çözülmemiş kayıt" demez, kişiden beklenen bir işlem olmadığını söyler.
        assert (
            "iade edilmemiş ödünç kaynağı ve kayıp ya da hasar nedeniyle kendisinden beklenen "
            "bir işlem bulunmamaktadır"
        ) in metin
        assert "çözülmemiş" not in metin
        assert "Kütüphaneden ilişiği yoktur." in metin
        assert "Örnek Anadolu Lisesi Müdürlüğü" in metin and "ÖRNEK İLÇE KAYMAKAMLIĞI" in metin
        assert "Örnek Müdür" in metin and "Kütüphane yöneticisi" in metin
        assert f"Tarih: {timezone.localdate():%d.%m.%Y}" in metin

    def test_personel_belgesinde_teslim_de_sayilir(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Hocahanım")
        metin = _metin(belgeler.certificate_pdf(_belge_satirlari(hoca)))
        assert "geri alınmamış teslimi" in metin
        assert "Görevi Öğretmen" in metin

    def test_konum_kalibi_ve_md18_alintisi_depodaki_metinle_birebir(self) -> None:
        yonetmelik = _mevzuat("meb-okul-kutuphaneleri-yonetmeligi.md")
        assert belgeler.MD18_ALINTI in yonetmelik
        assert "yerel araç" in belgeler.KONUM_KALIBI
        assert "Bakanlık otomasyon sistemindeki kaydın yerine geçmez" in belgeler.KONUM_KALIBI
        metin = _metin(belgeler.certificate_pdf(_belge_satirlari(ogrenci())))
        assert belgeler.MD18_ALINTI in metin
        assert "yerine geçmez" in metin

    def test_karne_diploma_ve_borc_dili_yoktur(self) -> None:
        metin = _metin(belgeler.certificate_pdf(_belge_satirlari(ogrenci(), ogretmen()))).lower()
        for sozcuk in YASAK_SOZCUKLER:
            assert sozcuk not in metin, sozcuk
        # Kullanıcıya giden sabitlerde de geçmez (modül yalnız yasağı anlatırken anar).
        for sabit in (belgeler.KONUM_KALIBI, belgeler.NOT_CLEAR_MESSAGE, belgeler.BELGE_BASLIGI):
            for sozcuk in YASAK_SOZCUKLER:
                assert sozcuk not in sabit.lower()

    def test_ayrilmis_kisiye_belge_basilir_durum_yazilir(self) -> None:
        kisi = ogrenci(first_name="Deneme", last_name="Nakilgiden")
        persons.leave_student(kisi)
        metin = _metin(belgeler.certificate_pdf(_belge_satirlari(kisi)))
        assert f"Ayrıldı · {timezone.localdate():%d.%m.%Y}" in metin

    def test_acik_isi_olana_belge_basilmaz_ad_yazilmaz(self) -> None:
        temiz = ogrenci()
        odunclu = ogrenci(first_name="Deneme", last_name="Gizliad")
        odunc_ver(uye(odunclu))
        rows, eksik = ilisik.persons_for_certificate(student_ids=[temiz.pk, odunclu.pk])

        with pytest.raises(ValidationError) as hata:
            belgeler.ensure_certifiable(rows, eksik)
        ileti = " ".join(hata.value.messages)
        assert "1 kişinin" in ileti and "Gizliad" not in ileti

    def test_teslimi_ya_da_dosyasi_olana_da_basilmaz(self) -> None:
        hoca = ogretmen()
        teslim_et(nushalar(1), personnel=hoca)
        dosyali = ogrenci()
        uyelik = uye(dosyali)
        loss_damage.report_lost(copy=odunc_ver(uyelik).copy, membership=uyelik)
        for kisi in (hoca, dosyali):
            rows, eksik = ilisik.persons_for_certificate(
                student_ids=[kisi.pk] if kisi is dosyali else [],
                personnel_ids=[kisi.pk] if kisi is hoca else [],
            )
            with pytest.raises(ValidationError):
                belgeler.ensure_certifiable(rows, eksik)

    def test_bos_ve_bulunamayan_secim_reddedilir(self) -> None:
        with pytest.raises(ValidationError, match="seçilmedi"):
            belgeler.ensure_certifiable([], [])
        with pytest.raises(ValidationError, match="bulunamadı"):
            belgeler.ensure_certifiable([], ["Öğrenci bulunamadı."])

    def test_en_uzun_veride_kisi_basina_tam_bir_sayfa(self, okul: SchoolConfig) -> None:
        _uzun_okul(okul)
        kisiler = [
            ogrenci(
                first_name=EN_UZUN_AD,
                last_name=EN_UZUN_SOYAD,
                class_level=12,
                class_section="ŞB",
                student_number=f"12345678901{sira}",
            )
            for sira in range(3)
        ]
        hoca = ogretmen(first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD)
        pdf = belgeler.certificate_pdf(_belge_satirlari(*kisiler, hoca))

        sayfalar = _sayfa_metinleri(pdf)
        assert len(sayfalar) == 4
        for sayfa in sayfalar:
            # Her sayfa kendi antedini, başlığını, hükmünü ve imzasını taşır.
            assert "KAYMAKAMLIĞI" in sayfa
            assert belgeler.BELGE_BASLIGI in sayfa
            assert "Kütüphaneden ilişiği yoktur." in sayfa
            assert "Okul müdürü" in sayfa
            assert "yerine geçmez" in sayfa


# ============================================================ E5 ilişik listesi


class TestIlisikListesi:
    def test_her_sayfada_dipnot_kaynak_adi_ve_okul_no_yok(self, okul: SchoolConfig) -> None:
        _uzun_okul(okul)
        politika(max_loans_student=3)
        for sira in range(45):
            uyelik = uye(
                ogrenci(
                    first_name=EN_UZUN_AD,
                    last_name=f"{EN_UZUN_SOYAD} {sira}",
                    class_level=12 if sira % 3 == 0 else 10,
                    student_number=str(880000 + sira),
                )
            )
            # Önce üçü de verilir, sonra geciktirilir (gecikme engeli yeni ödüncü keser).
            verilen = [odunc_ver(uyelik, odunc_nushasi(title=EN_UZUN_ESER)) for _ in range(3)]
            for loan in verilen:
                gecikmeli_yap(loan, gun=20)
        teslim_et(nushalar(4), section=sube(12, "A"))
        filtre = ilisik.ClearanceFilter()

        pdf = belgeler.clearance_list_pdf(
            ilisik.clearance_rows(filtre), ilisik.section_delivery_rows(), filtre=filtre
        )

        sayfalar = _sayfa_metinleri(pdf)
        assert len(sayfalar) >= 3
        for sayfa in sayfalar:
            assert belgeler.LISTE_DIPNOTU in sayfa
        metin = " ".join(sayfalar)
        assert "Uzun Adlı Örnek Kaynak" not in metin
        assert "880001" not in metin
        assert "iade " in metin and "gün gecikti" in metin
        assert "SINIF KİTAPLIKLARINDAKİ AÇIK TESLİMLER" in metin and "12/A" in metin
        assert "45 kişi" in metin

    def test_satir_icerigi_teslim_ve_dosya(self) -> None:
        hoca = ogretmen(first_name="Deneme", last_name="Teslimli")
        sonuc = teslim_et(nushalar(2), personnel=hoca)
        uyelik = uye(ogrenci())
        dosya = loss_damage.report_lost(copy=odunc_ver(uyelik).copy, membership=uyelik)
        gun = timezone.localdate()
        satirlar = {r.full_name: r for r in ilisik.clearance_rows()}

        teslim_metni = belgeler.obligations_text(satirlar["Deneme Teslimli"], gun)
        dosya_metni = belgeler.obligations_text(satirlar["Deneme Öğrenci"], gun)

        assert teslim_metni == f"Teslim: belge no {sonuc.document_no} (2 kitap)"
        assert "Kayıp/hasar dosyası: " in dosya_metni and "(Kayıp, Çözüm bekliyor)" in dosya_metni
        assert barcode_module.format_barcode(dosya.copy.barcode) in dosya_metni

    def test_bos_liste_ve_kapsam_metinleri(self) -> None:
        filtre = ilisik.ClearanceFilter(group=ilisik.GROUP_PRIORITY)
        metin = _metin(belgeler.clearance_list_pdf([], [], filtre=filtre))
        assert "Bu kapsamda kütüphaneyle açık işi olan kişi yok." in metin
        assert "Son sınıflar ve okuldan ayrılanlar" in metin
        assert belgeler.scope_text(ilisik.ClearanceFilter()) == "Bütün kişiler"
        assert (
            belgeler.scope_text(ilisik.ClearanceFilter(class_level=12, class_section="a"))
            == "12/A şubesi"
        )
        assert belgeler.scope_slug(ilisik.ClearanceFilter(group=ilisik.GROUP_GRADUATING)) == (
            "Son-Sınıflar",
        )
        assert belgeler.scope_slug(ilisik.ClearanceFilter(class_level=12, class_section="a")) == (
            "12-A",
        )


# ============================================================ yıl sonu pusulası


def _en_uzun_grup(kaynak: int = 6) -> belgeler.CollectionGroup:
    politika(max_loans_teacher=5)
    uyelik = uye(personel(first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD))
    verilen = [
        odunc_ver(uyelik, odunc_nushasi(title=f"{EN_UZUN_ESER} {sira}"))
        for sira in range(min(kaynak, 5))
    ]
    gecikmeli_yap(verilen[0], gun=120)
    for sira in range(5, kaynak):  # sınırı aşan eski ödünç (kişi bazında sayılır)
        Loan.objects.create(
            copy=odunc_nushasi(title=f"{EN_UZUN_ESER} {sira}"),
            membership=uyelik,
            due_date=timezone.localdate() - timedelta(days=150 + sira),
        )
    return belgeler.collection_groups(ilisik.clearance_rows())[0]


class TestYilSonuPusulasi:
    def test_gecikmemis_oduncler_de_pusulaya_girer(self) -> None:
        uyelik = uye(ogrenci(first_name="Deneme", last_name="Mezunaday", class_level=12))
        odunc_ver(uyelik, odunc_nushasi(title="Deneme Kaynağı Bir"))
        gecikmeli_yap(odunc_ver(uyelik, odunc_nushasi(title="Deneme Kaynağı İki")), gun=4)

        gruplar = belgeler.collection_groups(ilisik.clearance_rows())
        kutular = belgeler.year_end_slip_context(gruplar)["pages"][0]["slips"][0]["texts"]
        sag = " ".join(k["text"] for k in kutular if float(k["left"]) >= e4.FOLD_X)
        ic = " ".join(k["text"] for k in kutular if e4.STRIP_WIDTH <= float(k["left"]) < e4.FOLD_X)
        serit = " ".join(k["text"] for k in kutular if float(k["left"]) < e4.STRIP_WIDTH)

        assert "Deneme Kaynağı Bir" in sag and "Deneme Kaynağı İki" in sag
        assert "4 gün gecikti" in sag
        assert belgeler.YIL_SONU_ITEMS_TITLE in sag
        assert "Ders yılı sona eriyor." in ic and "ders yılı bitmeden" in ic
        assert "kütüphane" not in serit.lower()
        assert serit.startswith(f"{e4.SLIP_OUTSIDE_TITLE} Deneme Mezunaday 12/A")

    def test_son_getirme_gunu_basilir_saklanmaz(self) -> None:
        odunc_ver(uye())
        gruplar = belgeler.collection_groups(ilisik.clearance_rows())
        kutular = belgeler.year_end_slip_context(gruplar, return_by=date(2027, 6, 11))
        metin = " ".join(k["text"] for k in kutular["pages"][0]["slips"][0]["texts"])
        assert "en geç 11.06.2027 tarihine kadar" in metin

    def test_yalniz_odunc_olanlar_pusula_alir(self) -> None:
        teslim_et(nushalar(1), personnel=ogretmen())
        assert belgeler.collection_groups(ilisik.clearance_rows()) == []
        with pytest.raises(ValidationError, match="iade edilecek ödünç yok"):
            belgeler.year_end_slip_context([])

    def test_en_uzun_veride_hicbir_bolum_tasmaz(self, okul: SchoolConfig) -> None:
        _uzun_okul(okul)
        grup = _en_uzun_grup(kaynak=6)

        baglam = belgeler.year_end_slip_context([grup] * 4, return_by=date(2027, 6, 11))

        assert baglam["overflow_count"] == 0
        assert len(baglam["pages"]) == 2
        metinler = [k["text"] for k in baglam["pages"][0]["slips"][0]["texts"]]
        assert "ve 1 kaynak daha — kütüphane yöneticisine sorun." in metinler

    def test_pdf_sayfada_uc_pusula_ve_yasakli_dil_yok(self) -> None:
        for sira in range(4):
            odunc_ver(uye(ogrenci(first_name="Deneme", last_name=f"Kişi{sira}", class_level=12)))
        gruplar = belgeler.collection_groups(ilisik.clearance_rows())

        pdf = belgeler.year_end_slips_pdf(gruplar)

        assert _sayfa_sayisi(pdf) == 2
        metin = _metin(pdf).lower()
        for sozcuk in (*YASAK_SOZCUKLER, "gereği", "harç", "uzat"):
            assert sozcuk not in metin, sozcuk


def test_profil_yasagi_belge_modulu_konu_ve_siniflamaya_dokunmaz() -> None:
    kod = inspect.getsource(belgeler)
    for kelime in ("subject", "classification", "dewey", "work__section", "copy__section"):
        assert kelime not in kod


def test_kademe_yaz_yardimcisi_lise_icin_12() -> None:
    kademe_yaz(SchoolLevel.ORTAOGRETIM)
    assert ilisik.graduating_level() == 12
