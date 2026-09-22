"""e-Okul mutabakatı — öğrenci (EK-21) ve personel (EK-20); tasarım §8.3, F1 kod kapısı.

Öğrenci mutabakatının koruma testleri (kod kapısı):

- **Tek şubelik dosya diğer şubeleri LEFT yapmaz**; `full_list` onayıyla yapar.
- Şube değiştiren öğrenci ayrılmaz, "güncellendi" sayılır.
- Aynı dosyanın ikinci uygulaması değişiklik üretmez.
- Ayrılacaklar ayrılış yolundan geçer (kancalar + katı silme kararı).
- Önizleme ve uygulama aynı sonucu verir; önizleme hiçbir şeyi değiştirmez.

Personel mutabakatı: listede olmayanlar (`missing`) yalnız seçilince ayrılır,
"olası aynı kişi" çiftleri, görev metninden üye türü sınıflaması.

KİŞİSEL VERİ: ayrılacakların ve listede olmayanların adları yalnız API
yanıtındadır; `ImportRun.report`'ta ve günlükte ad, okul no ve görev metni
bulunmaz (sentetik, ayırt edici adlarla aranır).

Bütün ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.models import (
    ImportRun,
    ImportStatus,
    MemberKind,
    Personnel,
    SchoolYear,
    Student,
    StudentStatus,
)
from apps.okul.services import imports as import_service
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

OGRENCI_BASLIK = "Sınıf\tOkul No\tAdı Soyadı"
PERSONEL_BASLIK = "Adı\tSoyadı\tGörevi\tBranşı"

#: Ayırt edici sentetik değerler — raporda/günlükte aranırlar.
SENTETIK_AD = "ZEYNEPSENTETİK"
SENTETIK_SOYAD = "ÖRNEKOĞLU"
SENTETIK_NO = "98765"


def _ogrenci_metni(*satirlar: str) -> str:
    return "\n".join([OGRENCI_BASLIK, *satirlar])


def _personel_metni(*satirlar: str) -> str:
    return "\n".join([PERSONEL_BASLIK, *satirlar])


def _ogrenci(numara: str, sinif: int, sube: str, ad: str = "DENEME") -> Student:
    ogrenci: Student = Student.objects.create(
        first_name=ad,
        last_name="ÖĞRENCİ",
        student_number=numara,
        class_level=sinif,
        class_section=sube,
    )
    return ogrenci


def _personel(ad: str, soyad: str, **alanlar: Any) -> Personnel:
    kisi: Personnel = Personnel.objects.create(first_name=ad, last_name=soyad, **alanlar)
    return kisi


def _aktif_mi(numara: str) -> bool:
    return selectors.find_student_by_number(numara) is not None


@pytest.fixture(autouse=True)
def aktif_yil() -> SchoolYear:
    yil: SchoolYear = SchoolYear.objects.create(
        name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_active=True
    )
    return yil


@pytest.fixture(autouse=True)
def bos_kayit_defterleri(monkeypatch: pytest.MonkeyPatch) -> None:
    for ad in ("_obligation_checks", "_membership_checks", "_leave_hooks", "_merge_hooks"):
        monkeypatch.setattr(persons, ad, [])


@pytest.fixture
def herkes_uye() -> Iterator[None]:
    """Sahte üyelik denetimi: herkes "hiç üye olmuş" sayılır → ayrılışta kayıt KALIR."""
    persons.register_membership_check(lambda _kisi: True)
    yield


# ---------------------------------------------------------------------------
# Öğrenci mutabakatı — kapsam (kod kapısı)
# ---------------------------------------------------------------------------


class TestOgrenciKapsami:
    def test_tek_subelik_dosya_diger_subeleri_left_yapmaz(self) -> None:
        """KORUMA TESTİ (F1 kod kapısı): yalnız 10/A'yı taşıyan dosya 10/B'ye dokunmaz."""
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("201", 10, "B")
        _ogrenci("301", 11, "Ç")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")
        )

        assert rapor.full_list is False
        assert rapor.leaving_students == 1  # yalnız dosyadaki şubede olmayan 102
        assert not _aktif_mi("102")
        assert _aktif_mi("201") and _aktif_mi("301")
        assert Student.objects.filter(status=StudentStatus.ACTIVE).count() == 3

    def test_tam_liste_onayiyla_dosyada_olmayan_subeler_de_ayrilir(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("201", 10, "B")
        sinifsiz = Student.objects.create(first_name="NAKİL", last_name="ÖĞRENCİ")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"), full_list=True
        )

        assert rapor.full_list is True
        assert rapor.leaving_students == 2  # 10/B ve sınıfsız öğrenci
        assert not _aktif_mi("201")
        assert not Student.objects.filter(pk=sinifsiz.pk).exists()
        assert _aktif_mi("101")

    def test_sube_degistiren_ogrenci_ayrilmaz_guncellenir(self) -> None:
        """10/A'dan 11/B'ye geçen öğrenci 10/A kapsamdayken bile ayrılmış sayılmaz."""
        gecen = _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t102\tDENEME ÖĞRENCİ", "11/B\t101\tDENEME ÖĞRENCİ")
        )

        assert (rapor.updated_students, rapor.unchanged_students) == (1, 1)
        assert rapor.leaving_students == 0
        gecen.refresh_from_db()
        assert (gecen.status, gecen.class_label) == (StudentStatus.ACTIVE, "11/B")

    def test_ayni_dosyanin_ikinci_uygulamasi_degisiklik_uretmez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("999", 10, "A")  # ilk uygulamada ayrılır
        metin = _ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10/A\t102\tYENİ ÖĞRENCİ")

        ilk = import_service.commit_students_text(text=metin)
        assert (ilk.created_students, ilk.leaving_students) == (1, 1)
        oncesi = {s.pk: (s.updated_at, s.status) for s in Student.all_objects.all()}

        ikinci = import_service.commit_students_text(text=metin)

        assert ikinci.already_imported is True
        assert (
            ikinci.created_students,
            ikinci.updated_students,
            ikinci.unchanged_students,
            ikinci.leaving_students,
        ) == (0, 0, 2, 0)
        assert {s.pk: (s.updated_at, s.status) for s in Student.all_objects.all()} == oncesi

    def test_numara_yazim_farki_ayni_ogrenciye_eslesir_ve_ayrilis_uretmez(self) -> None:
        """Kör indeks: e-Okul '0101' yazsa da kayıttaki '101' aynı öğrencidir."""
        ogrenci = _ogrenci("101", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t0101\tDENEME ÖĞRENCİ")
        )

        assert (rapor.unchanged_students, rapor.leaving_students) == (1, 0)
        ogrenci.refresh_from_db()
        assert ogrenci.student_number == "101"  # yazım farkı kaydı değiştirmez

    def test_dosyada_iki_kez_gecen_numara_ikinci_satirda_atlanir(self) -> None:
        rapor = import_service.commit_students_text(
            text=_ogrenci_metni(
                f"10/A\t{SENTETIK_NO}\tİLK ÖĞRENCİ", f"10/B\t0{SENTETIK_NO}\tİKİNCİ"
            )
        )

        assert rapor.created_students == 1
        assert [(s.row_number, s.field) for s in rapor.skipped] == [(3, "number")]
        assert SENTETIK_NO not in json.dumps(rapor.to_dict()["skipped"], ensure_ascii=False)


# ---------------------------------------------------------------------------
# Öğrenci mutabakatı — ayrılış yolu, rapor, önizleme
# ---------------------------------------------------------------------------


class TestOgrenciAyrilisVeRapor:
    def test_ayrilacaklar_ayrilis_yolundan_gecer_uye_kaydi_kalir(self, herkes_uye: None) -> None:
        kancaya_gelen: list[int] = []
        persons.register_leave_hook(lambda kisi: kancaya_gelen.append(kisi.pk))
        _ogrenci("101", 10, "A")
        ayrilan = _ogrenci("102", 10, "A")

        import_service.commit_students_text(text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"))

        assert kancaya_gelen == [ayrilan.pk]
        ayrilan.refresh_from_db()
        assert ayrilan.status == StudentStatus.LEFT
        assert ayrilan.left_at is not None

    def test_hic_uye_olmamis_ayrilan_kati_silinir(self) -> None:
        ayrilan = _ogrenci("102", 10, "A")
        _ogrenci("101", 10, "A")

        import_service.commit_students_text(text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"))

        assert not Student.all_objects.filter(pk=ayrilan.pk).exists()

    def test_sube_bazli_rapor_ve_toplamlar(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("103", 10, "Ç", ad="ESKİ")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni(
                "10/A\t101\tDENEME ÖĞRENCİ",
                "10/Ç\t103\tYENİ AD",
                "10/Ç\t104\tYENİ ÖĞRENCİ",
                "9/Z\t105\tYENİ ÖĞRENCİ",
            )
        )

        tablo = [
            (c.class_label, c.created, c.updated, c.unchanged, c.leaving) for c in rapor.classes
        ]
        # Şubeler sınıf, sonra Türk alfabesiyle sıralanır ('C' < 'Ç' < 'Z').
        assert tablo == [
            ("9/Z", 1, 0, 0, 0),
            ("10/A", 0, 0, 1, 1),
            ("10/Ç", 1, 1, 0, 0),
        ]
        assert (
            rapor.created_students,
            rapor.updated_students,
            rapor.unchanged_students,
            rapor.leaving_students,
        ) == (2, 1, 1, 1)

    def test_onizleme_uygulamayla_ayni_sonucu_verir_ve_hicbir_sey_degistirmez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("201", 10, "B")
        metin = _ogrenci_metni("10/A\t101\tDEĞİŞEN AD", "10/B\t202\tYENİ ÖĞRENCİ")
        oncesi = sorted(Student.all_objects.values_list("pk", "status", "updated_at"))

        onizleme = import_service.preview_students_text(text=metin, full_list=True)

        assert sorted(Student.all_objects.values_list("pk", "status", "updated_at")) == oncesi
        uygulama = import_service.commit_students_text(text=metin, full_list=True)
        onizleme_sozlugu = {**onizleme.to_dict(), "dry_run": False}
        assert onizleme_sozlugu == uygulama.to_dict() | {"already_imported": False}
        assert onizleme.dry_run is True
        assert onizleme.leaving_students == 2

    def test_api_yanitinda_ayrilacaklarin_adi_var_kalici_raporda_yok(self) -> None:
        """Önizleme yönetim yüzeyinde ad gösterir; ImportRun.report yalnız sayı tutar."""
        _ogrenci("101", 10, "A")
        Student.objects.create(
            first_name=SENTETIK_AD,
            last_name=SENTETIK_SOYAD,
            student_number=SENTETIK_NO,
            class_level=10,
            class_section="A",
        )
        metin = _ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")

        yanit = APIClient().post(
            "/api/v1/imports/students/preview/", {"text": metin}, format="json"
        )
        assert yanit.status_code == 200
        ayrilacak = yanit.json()["leaving"]
        assert [(a["full_name"], a["student_number"], a["class_label"]) for a in ayrilacak] == [
            (f"{SENTETIK_AD} {SENTETIK_SOYAD}", SENTETIK_NO, "10/A")
        ]
        import_service.commit_students_text(text=metin)

        raporlar = json.dumps([r.report for r in ImportRun.objects.all()], ensure_ascii=False)
        assert ImportRun.objects.filter(status=ImportStatus.PREVIEWED).exists()
        assert ImportRun.objects.filter(status=ImportStatus.COMPLETED).exists()
        for iz in (SENTETIK_AD, SENTETIK_SOYAD, SENTETIK_NO, 'leaving": ['):
            assert iz not in raporlar, iz
        assert '"leaving_students": 1' in raporlar

    def test_gunlukte_ad_ve_numara_yok(self, caplog: pytest.LogCaptureFixture) -> None:
        Student.objects.create(
            first_name=SENTETIK_AD,
            last_name=SENTETIK_SOYAD,
            student_number=SENTETIK_NO,
            class_level=10,
            class_section="A",
        )
        with caplog.at_level(logging.DEBUG):
            import_service.commit_students_text(
                text=_ogrenci_metni(f"10/A\t101\t{SENTETIK_AD} YENİ", "10/A\t102\tDİĞER ÖĞRENCİ")
            )

        assert caplog.records, "aktarım günlüğe sayısal özet yazmalı"
        for iz in (SENTETIK_AD, SENTETIK_SOYAD, SENTETIK_NO, "DİĞER"):
            assert iz not in caplog.text, iz

    def test_api_tam_liste_onayi_cok_parcali_ve_json_govdede_alinir(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("201", 10, "B")
        metin = _ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")
        client = APIClient()

        kapsamli = client.post(
            "/api/v1/imports/students/preview/",
            {"text": metin, "full_list": "true"},
            format="multipart",
        )
        varsayilan = client.post(
            "/api/v1/imports/students/preview/", {"text": metin}, format="json"
        )

        assert kapsamli.json()["full_list"] is True
        assert kapsamli.json()["leaving_students"] == 1
        assert varsayilan.json()["full_list"] is False
        assert varsayilan.json()["leaving_students"] == 0
        assert _aktif_mi("201")  # önizleme yazmaz


# ---------------------------------------------------------------------------
# Personel mutabakatı
# ---------------------------------------------------------------------------


class TestPersonelMutabakati:
    def test_listede_olmayanlar_doner_varsayilan_hicbiri_ayrilmaz(self) -> None:
        _personel("AYŞE", "KAYA")
        eksik = _personel("MEHMET", "DEMİR")

        onizleme = import_service.preview_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik")
        )
        assert [(m.id, m.full_name) for m in onizleme.missing] == [(eksik.pk, "MEHMET DEMİR")]
        assert onizleme.missing_count == 1

        uygulama = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik")
        )
        assert uygulama.left_personnel == 0
        eksik.refresh_from_db()
        assert eksik.is_active is True

    def test_yalniz_secilenler_ayrilir(self, herkes_uye: None) -> None:
        kalan = _personel("AYŞE", "KAYA")
        secilen = _personel("MEHMET", "DEMİR")
        secilmeyen = _personel("ZEHRA", "ÇELİK")

        rapor = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\t"),
            # Listede OLAN kişinin kimliği yok sayılır (yalnız `missing` kümesi ayrılabilir).
            mark_left_ids=[secilen.pk, kalan.pk],
        )

        assert rapor.left_personnel == 1
        secilen.refresh_from_db()
        assert (secilen.is_active, secilen.left_at) == (False, timezone.localdate())
        for kisi in (kalan, secilmeyen):
            kisi.refresh_from_db()
            assert kisi.is_active is True

    def test_secilen_hic_uye_olmamis_personel_kati_silinir(self) -> None:
        _personel("AYŞE", "KAYA")
        secilen = _personel("MEHMET", "DEMİR")

        import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\t\t"), mark_left_ids=[secilen.pk]
        )

        assert not Personnel.all_objects.filter(pk=secilen.pk).exists()

    def test_ayrilmis_personel_listede_gorulunce_yeniden_aktiflesir(self, herkes_uye: None) -> None:
        kisi = _personel("AYŞE", "KAYA")
        persons.leave_personnel(kisi)

        rapor = import_service.commit_personnel_text(text=_personel_metni("AYŞE\tKAYA\tÖğretmen\t"))

        assert (rapor.created_personnel, rapor.reactivated_personnel) == (0, 1)
        kisi.refresh_from_db()
        assert (kisi.is_active, kisi.left_at) == (True, None)

    def test_adaslar_ayri_ayri_eslesir(self) -> None:
        """Aynı adı taşıyan iki personel, iki satırla iki ayrı kayda eşleşir."""
        _personel("AYŞE", "KAYA")
        _personel("AYŞE", "KAYA")

        rapor = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\t", "AYŞE\tKAYA\tÖğretmen\t")
        )

        assert (rapor.created_personnel, rapor.unchanged_personnel, rapor.missing_count) == (
            0,
            2,
            0,
        )

    def test_olasi_ayni_kisi_ad_ayni_soyad_farkli(self) -> None:
        """Soyadı değişimi: yeni satır 'AYŞE BEYAZ' ↔ listede olmayan 'AYŞE KARA'."""
        eski = _personel("AYŞE", "KARA")
        _personel("ALİ", "VELİ")
        metin = _personel_metni("ALİ\tVELİ\t\t", "AYŞE\tBEYAZ\tÖğretmen\t")

        onizleme = import_service.preview_personnel_text(text=metin)
        assert [
            (c.row_number, c.row_name, c.existing_id, c.existing_name, c.new_id)
            for c in onizleme.similar_pairs
        ] == [(3, "AYŞE BEYAZ", eski.pk, "AYŞE KARA", None)]

        uygulama = import_service.commit_personnel_text(text=metin)
        (cift,) = uygulama.similar_pairs
        yeni = Personnel.objects.get(pk=cift.new_id)
        assert yeni.full_name == "AYŞE BEYAZ"

        # Birleştir: eski kayıt (kaynak) yeni kayda (hedef) katılır, eski silinir.
        yanit = APIClient().post(
            f"/api/v1/personnel/{cift.existing_id}/merge/", {"into_id": cift.new_id}, format="json"
        )
        assert yanit.status_code == 200
        assert not Personnel.all_objects.filter(pk=eski.pk).exists()

    def test_olasi_ayni_kisi_kucuk_yazim_farki(self) -> None:
        eski = _personel("SELİN", "ÖZTÜRK")

        rapor = import_service.preview_personnel_text(
            text=_personel_metni("SELİM\tÖZTÜRK\tÖğretmen\t")
        )

        assert [c.existing_id for c in rapor.similar_pairs] == [eski.pk]

    def test_benzemeyen_kisiler_cift_olusturmaz_ve_ayrilacak_isaretli_kisi_cift_olmaz(
        self,
    ) -> None:
        benzer = _personel("AYŞE", "KARA")
        _personel("MEHMET", "DEMİR")

        rapor = import_service.preview_personnel_text(
            text=_personel_metni("ZEYNEP\tKAYA\t\t", "AYŞE\tBEYAZ\t\t"),
            mark_left_ids=[benzer.pk],
        )

        assert rapor.similar_pairs == []
        assert rapor.missing_count == 2

    def test_kalici_raporda_ad_yok_api_yanitinda_var(self) -> None:
        _personel(SENTETIK_AD, SENTETIK_SOYAD)
        metin = _personel_metni(f"{SENTETIK_AD}\tYENİSOYAD\tÖğretmen\t")

        yanit = APIClient().post(
            "/api/v1/imports/personnel/commit/", {"text": metin}, format="json"
        )

        assert yanit.status_code == 200
        assert yanit.json()["missing"][0]["full_name"] == f"{SENTETIK_AD} {SENTETIK_SOYAD}"
        assert yanit.json()["similar_pairs"][0]["row_name"] == f"{SENTETIK_AD} YENİSOYAD"
        run = ImportRun.objects.get(status=ImportStatus.COMPLETED)
        kalici = json.dumps(run.report, ensure_ascii=False)
        for iz in (SENTETIK_AD, SENTETIK_SOYAD, "YENİSOYAD"):
            assert iz not in kalici, iz
        assert (run.report["missing_count"], run.report["similar_pair_count"]) == (1, 1)
        assert "missing" not in run.report and "similar_pairs" not in run.report

    def test_api_ayrilacaklar_cok_parcali_govdede_tekrarlanan_alanla_gelir(self) -> None:
        _personel("AYŞE", "KAYA")
        bir = _personel("MEHMET", "DEMİR")
        iki = _personel("ZEHRA", "ÇELİK")

        yanit = APIClient().post(
            "/api/v1/imports/personnel/commit/",
            {"text": _personel_metni("AYŞE\tKAYA\t\t"), "mark_left_ids": [bir.pk, iki.pk]},
            format="multipart",
        )

        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["left_personnel"] == 2


# ---------------------------------------------------------------------------
# Görev metninden üye türü — metin hiçbir yerde saklanmaz
# ---------------------------------------------------------------------------


class TestUyeTuruSiniflamasi:
    GOREVLI_LISTE = _personel_metni(
        "ALİ\tBİR\tMüdür Yardımcısı\tTarih",
        "AYŞE\tİKİ\tSözleşmeli Öğretmen(657 S.K. 4/B)\tİngilizce",
        "CEM\tÜÇ\tMemur\t",
        "DENİZ\tDÖRT\tYardımcı Hizmetli\t",
        "EMEL\tBEŞ\tUzman Kaptan\t",
        "FATİH\tALTI\t\t",
    )

    def test_gorev_uye_turune_cevrilir_taninmayan_ogretmen_ve_uyari(self) -> None:
        rapor = import_service.commit_personnel_text(text=self.GOREVLI_LISTE)

        turler = {p.first_name: p.member_kind for p in Personnel.objects.all()}
        assert turler == {
            "ALİ": MemberKind.TEACHER,
            "AYŞE": MemberKind.TEACHER,
            "CEM": MemberKind.STAFF,
            "DENİZ": MemberKind.STAFF,
            "EMEL": MemberKind.TEACHER,  # tanınmadı → öğretmen + uyarı
            "FATİH": MemberKind.TEACHER,  # boş görev → öğretmen + uyarı
        }
        uyarilar = [(u.row_number, u.field, u.raw_value) for u in rapor.warnings]
        assert uyarilar == [(6, "member_kind", ""), (7, "member_kind", "")]
        assert all("Üye türünü denetleyin" in u.issue for u in rapor.warnings)

    def test_gorev_sutunu_yoksa_ogretmen_uyarisiz(self) -> None:
        rapor = import_service.commit_personnel_text(text="Adı\tSoyadı\nALİ\tBİR")

        assert Personnel.objects.get().member_kind == MemberKind.TEACHER
        assert rapor.warnings == []

    def test_gorev_ve_brans_metni_hicbir_yerde_saklanmaz(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            yanit = APIClient().post(
                "/api/v1/imports/personnel/commit/", {"text": self.GOREVLI_LISTE}, format="json"
            )
        assert yanit.status_code == 200

        izler = {
            "API yanıtı": json.dumps(yanit.json(), ensure_ascii=False),
            "ImportRun.report": json.dumps(
                [r.report for r in ImportRun.objects.all()], ensure_ascii=False
            ),
            "günlük": caplog.text,
        }
        for yer, metin in izler.items():
            for gorev in ("Sözleşmeli", "Memur", "Kaptan", "Hizmetli", "Tarih", "İngilizce"):
                assert gorev not in metin, (yer, gorev)
        # Model de bu veriyi tutacak alan taşımaz.
        assert not hasattr(Personnel.objects.first(), "title")
        assert not hasattr(Personnel.objects.first(), "branch")
