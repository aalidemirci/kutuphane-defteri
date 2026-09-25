"""İlişik listesi seçicileri (F7 — tasarım §8.3, §9-8, §10 E5).

- Liste açık ödünç, öğretmene açık teslim ve çözülmemiş kayıp/hasar dosyası olan
  kişilerdir; okuldan AYRILMIŞ kişiler de listededir.
- Sıra: son sınıflar, sonra ayrılanlar (ayrılmış ya da havuzda), sonra öbürleri;
  grup içinde öğrenciler sınıf → şube → okul no, sonra personel ada göre.
- Şube (sınıf kitaplığı) teslimleri kişisizdir ve ayrı listelenir; son sınıf
  şubeleri önce.
- Kademe seçilmemişse kimse son sınıf sayılmaz.
- Profil yasağı: modül konu, sınıflama ya da bölüm alanına dokunmaz.

Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

import inspect
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.kutuphane import selectors_ilisik as ilisik
from apps.kutuphane.models import CaseResolution
from apps.kutuphane.services import circulation, deliveries, loss_damage
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    uye,
)
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, nushalar, ogretmen, sube, teslim_et
from apps.okul.models import SchoolLevel
from apps.okul.services import persons

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def lise() -> None:
    kademe_yaz(SchoolLevel.ORTAOGRETIM)


def _adlar(rows: list[ilisik.ClearanceRow]) -> list[str]:
    return [r.full_name for r in rows]


# ============================================================ kapsam


class TestKapsam:
    def test_acik_isi_olmayan_kisi_ilisik_listesinde_yok(self) -> None:
        ogrenci(first_name="Deneme", last_name="Temiz")
        uye(ogrenci(first_name="Deneme", last_name="Üyetemiz"))
        assert ilisik.clearance_rows() == []

    def test_acik_odunc_teslim_ve_dosya_listeye_girer(self) -> None:
        odunclu = uye(ogrenci(first_name="Deneme", last_name="Ödünçlü"))
        odunc_ver(odunclu)
        hoca = ogretmen(first_name="Deneme", last_name="Teslimli")
        teslim_et(nushalar(2), personnel=hoca)
        dosyali = uye(ogrenci(first_name="Deneme", last_name="Dosyalı"))
        loss_damage.report_lost(copy=odunc_ver(dosyali).copy, membership=dosyali)

        rows = {r.full_name: r for r in ilisik.clearance_rows()}

        assert len(rows["Deneme Ödünçlü"].loans) == 1
        assert len(rows["Deneme Teslimli"].deliveries) == 2
        dosya_satiri = rows["Deneme Dosyalı"]
        # Kayıp bildirimi ödüncü "Kayba dönüştü" ile kapattı; yükümlülük dosyadır.
        assert dosya_satiri.loans == () and len(dosya_satiri.cases) == 1
        assert all(not r.is_clear for r in rows.values())

    def test_cozulen_dosya_ve_iade_edilen_odunc_listeden_cikar(self) -> None:
        uyelik = uye()
        loan = odunc_ver(uyelik)
        dosya = loss_damage.report_lost(copy=odunc_ver(uyelik).copy, membership=uyelik)
        assert len(ilisik.clearance_rows()) == 1

        circulation.return_copy(copy=loan.copy)
        loss_damage.resolve_case(dosya, resolution=CaseResolution.FOUND_RETURNED)

        assert ilisik.clearance_rows() == []

    def test_ayrilmis_kisinin_acik_isi_listede_kalir(self) -> None:
        kisi = ogrenci(first_name="Deneme", last_name="Ayrılan")
        odunc_ver(uye(kisi))
        persons.leave_student(kisi)

        rows = ilisik.clearance_rows()

        assert _adlar(rows) == ["Deneme Ayrılan"]
        assert rows[0].group == ilisik.GROUP_LEAVING
        assert rows[0].status_text.startswith("Ayrıldı · ")

    def test_sube_teslimi_kisi_listesine_girmez_ayri_listelenir(self) -> None:
        teslim_et(nushalar(3), section=sube(12, "A"))
        teslim_et(nushalar(1), section=sube(9, "B"))

        assert ilisik.clearance_rows() == []
        subeler = ilisik.section_delivery_rows()
        assert [(s.label, len(s.deliveries), s.is_graduating) for s in subeler] == [
            ("12/A", 3, True),
            ("9/B", 1, False),
        ]
        assert [s.label for s in ilisik.section_delivery_rows(graduating_only=True)] == ["12/A"]

    def test_geri_alinan_sube_teslimi_listeden_cikar(self) -> None:
        sonuc = teslim_et(nushalar(1), section=sube(12, "A"))
        deliveries.take_back(sonuc.deliveries[0].copy)
        assert ilisik.section_delivery_rows() == []


# ============================================================ sıra


class TestSira:
    def test_son_siniflar_sonra_ayrilanlar_sonra_obürleri(self) -> None:
        dokuz = uye(ogrenci(first_name="Deneme", last_name="Dokuz", class_level=9))
        on_iki_b = uye(
            ogrenci(first_name="Deneme", last_name="OnİkiB", class_level=12, class_section="B")
        )
        on_iki_a = uye(
            ogrenci(first_name="Deneme", last_name="OnİkiA", class_level=12, class_section="A")
        )
        havuzdaki = ogrenci(first_name="Deneme", last_name="Havuzda", class_level=10)
        ayrilan_hoca = personel(first_name="Deneme", last_name="Nakilhoca")
        for u in (dokuz, on_iki_b, on_iki_a, uye(havuzdaki), uye(ayrilan_hoca)):
            odunc_ver(u)
        persons.add_to_leave_pool(havuzdaki, run=None)
        persons.leave_personnel(ayrilan_hoca)

        rows = ilisik.clearance_rows()

        assert _adlar(rows) == [
            "Deneme OnİkiA",
            "Deneme OnİkiB",
            "Deneme Havuzda",
            "Deneme Nakilhoca",
            "Deneme Dokuz",
        ]
        assert [r.group for r in rows] == [
            ilisik.GROUP_GRADUATING,
            ilisik.GROUP_GRADUATING,
            ilisik.GROUP_LEAVING,
            ilisik.GROUP_LEAVING,
            ilisik.GROUP_OTHER,
        ]
        assert rows[0].status_text == "Son sınıf"
        assert rows[2].status_text == "Ayrılış kararı bekliyor"

    def test_kademe_secilmemisse_son_sinif_yoktur(self) -> None:
        kademe_yaz("")
        odunc_ver(uye(ogrenci(class_level=12)))
        rows = ilisik.clearance_rows()
        assert [r.group for r in rows] == [ilisik.GROUP_OTHER]
        assert ilisik.graduating_level() is None

    def test_ortaokulda_son_sinif_sekizdir(self) -> None:
        kademe_yaz(SchoolLevel.ORTAOKUL)
        odunc_ver(uye(ogrenci(class_level=8)))
        odunc_ver(uye(ogrenci(class_level=12)))
        assert [
            (getattr(r.person, "class_level", None), r.group) for r in ilisik.clearance_rows()
        ] == [
            (8, ilisik.GROUP_GRADUATING),
            (12, ilisik.GROUP_OTHER),
        ]

    def test_kisi_icinde_oduncler_iade_tarihine_gore(self) -> None:
        uyelik = uye()
        ilk, ikinci = odunc_ver(uyelik), odunc_ver(uyelik)
        gecikmeli_yap(ikinci, gun=3)
        rows = ilisik.clearance_rows()
        assert [lo.pk for lo in rows[0].loans] == [ikinci.pk, ilk.pk]
        assert rows[0].overdue_count() == 1


# ============================================================ süzgeçler


class TestSuzgecler:
    def test_grup_ve_oncelikli_kapsam(self) -> None:
        son = uye(ogrenci(first_name="Deneme", last_name="Son", class_level=12))
        diger = uye(ogrenci(first_name="Deneme", last_name="Diğer", class_level=10))
        ayrilan = ogrenci(first_name="Deneme", last_name="Giden", class_level=11)
        for u in (son, diger, uye(ayrilan)):
            odunc_ver(u)
        persons.leave_student(ayrilan)

        def adlar(grup: str) -> list[str]:
            return _adlar(ilisik.clearance_rows(ilisik.ClearanceFilter(group=grup)))

        assert adlar(ilisik.GROUP_GRADUATING) == ["Deneme Son"]
        assert adlar(ilisik.GROUP_LEAVING) == ["Deneme Giden"]
        assert adlar(ilisik.GROUP_OTHER) == ["Deneme Diğer"]
        assert adlar(ilisik.GROUP_PRIORITY) == ["Deneme Son", "Deneme Giden"]

    def test_sube_suzgeci_personeli_disarida_birakir(self) -> None:
        odunc_ver(uye(ogrenci(class_level=12, class_section="Ç")))
        odunc_ver(uye(ogrenci(class_level=12, class_section="C")))
        odunc_ver(uye(personel()))

        rows = ilisik.clearance_rows(ilisik.ClearanceFilter(class_level=12, class_section="ç"))

        assert [getattr(r.person, "class_section", "") for r in rows] == ["Ç"]

    def test_ad_ve_okul_no_aramasi(self) -> None:
        odunc_ver(uye(ogrenci(first_name="Şükrü", last_name="Deneme", student_number="4321")))
        odunc_ver(uye(ogrenci(first_name="Ayşe", last_name="Deneme", student_number="1234")))

        ad = ilisik.clearance_rows(ilisik.ClearanceFilter(search="şükrü"))
        numara = ilisik.clearance_rows(ilisik.ClearanceFilter(search="1234"))
        on_ek = ilisik.clearance_rows(ilisik.ClearanceFilter(search="12"))

        assert _adlar(ad) == ["Şükrü Deneme"]
        assert _adlar(numara) == ["Ayşe Deneme"]
        assert on_ek == []  # okul no kör indeksle TAM eşleşir

    def test_toplama_suzgeci_yalniz_odunc_ve_teslim(self) -> None:
        dosyali = uye(ogrenci(first_name="Deneme", last_name="Dosyalı"))
        loss_damage.report_lost(copy=odunc_ver(dosyali).copy, membership=dosyali)
        odunc_ver(uye(ogrenci(first_name="Deneme", last_name="Ödünçlü")))
        teslim_et(nushalar(1), personnel=ogretmen(first_name="Deneme", last_name="Teslimli"))

        rows = ilisik.clearance_rows(ilisik.ClearanceFilter(obligation=ilisik.OBLIGATION_COLLECT))

        assert sorted(_adlar(rows)) == ["Deneme Teslimli", "Deneme Ödünçlü"]

    def test_acik_isi_olmayanlar_ve_hepsi(self) -> None:
        temiz = ogrenci(first_name="Deneme", last_name="Temiz", class_level=12)
        odunclu = uye(ogrenci(first_name="Deneme", last_name="Açıkişli", class_level=12))
        odunc_ver(odunclu)
        personel(first_name="Deneme", last_name="Hoca")

        temizler = ilisik.clearance_rows(
            ilisik.ClearanceFilter(state=ilisik.STATE_CLEAR, group=ilisik.GROUP_GRADUATING)
        )
        hepsi = ilisik.clearance_rows(ilisik.ClearanceFilter(state=ilisik.STATE_ALL))

        assert [r.person.pk for r in temizler] == [temiz.pk]
        assert temizler[0].is_clear
        assert len(hepsi) == 3
        assert {r.full_name: r.is_clear for r in hepsi}["Deneme Açıkişli"] is False


# ============================================================ belge adayları ve sayılar


class TestBelgeVeSayilar:
    def test_belge_adaylari_eksik_kimligi_bildirir(self) -> None:
        kisi = ogrenci()
        rows, eksik = ilisik.persons_for_certificate(student_ids=[kisi.pk, 999_999])
        assert [r.person.pk for r in rows] == [kisi.pk]
        assert eksik == ["Öğrenci bulunamadı."]

    def test_sayilar_kisisiz_ve_gruplu(self) -> None:
        son = uye(ogrenci(class_level=12))
        odunc_ver(son)
        odunc_ver(son)
        giden = ogrenci(class_level=10)
        odunc_ver(uye(giden))
        persons.add_to_leave_pool(giden, run=None)
        teslim_et(nushalar(2), section=sube(12, "A"))
        teslim_et(nushalar(1), personnel=ogretmen())

        sayilar = ilisik.clearance_counts()

        assert sayilar.persons == 3
        assert sayilar.graduating_persons == 1
        assert sayilar.graduating_open_loans == 2
        assert sayilar.leaving_persons == 1
        assert sayilar.leaving_open_loans == 1
        assert sayilar.open_loans == 3
        assert sayilar.teacher_deliveries == 1
        assert sayilar.section_deliveries == 2
        assert sayilar.graduating_section_deliveries == 2

    def test_eski_yilin_subesindeki_acik_teslim_de_listelenir(self) -> None:
        eski = sube(12, "A")
        teslim_et(nushalar(1), section=eski)
        yil = eski.school_year
        yil.is_active = False
        yil.save()
        from apps.kutuphane.tests.dolasim_ortak import ders_yili

        ders_yili(
            baslangic=yil.start_date + timedelta(days=366),
            birinci_bitis=yil.start_date + timedelta(days=500),
            ikinci_baslangic=yil.start_date + timedelta(days=510),
            bitis=yil.end_date + timedelta(days=366),
        )

        satir = ilisik.section_delivery_rows()[0]

        assert not satir.is_active_year and not satir.is_graduating

    def test_teslimdeki_nushanin_kaybinda_sube_dosyasi_sayilir(self) -> None:
        sonuc = teslim_et([odunc_nushasi()], section=sube(9, "A"))
        loss_damage.report_lost(copy=sonuc.deliveries[0].copy)

        satirlar = ilisik.section_delivery_rows()

        assert len(satirlar) == 1 and len(satirlar[0].cases) == 1
        assert satirlar[0].deliveries == ()


def test_profil_yasagi_modul_konu_ve_siniflamaya_dokunmaz() -> None:
    kod = inspect.getsource(ilisik)
    for kelime in ("subject", "classification", "dewey", "work__section", "copy__section"):
        assert kelime not in kod


def test_bugunun_tarihi_gecikme_sayisinda_kullanilir() -> None:
    uyelik = uye()
    loan = odunc_ver(uyelik)
    satir = ilisik.clearance_rows()[0]
    assert satir.overdue_count(loan.due_date + timedelta(days=1)) == 1
    assert satir.overdue_count(timezone.localdate()) == 0
