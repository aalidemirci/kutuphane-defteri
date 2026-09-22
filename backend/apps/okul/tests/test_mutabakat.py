"""e-Okul mutabakatı — öğrenci (EK-21) ve personel (EK-20); tasarım §8.3, F1 kod kapısı.

F1 eki 7 (kullanıcı kararı 22.09.2026): **aktarım hiç kimseyi ayırmaz ve hiç
kimseyi silmez.** Listede bulunmayan aktif kişi AYRILIŞ HAVUZUNA girer, durumu
aktif kalır; dosyada bulunan havuzdaki kişi havuzdan kendiliğinden çıkar. Karar
havuzda verilir (`test_ayrilis_havuzu.py`).

Öğrenci mutabakatının koruma testleri (kod kapısı):

- **Tek şubelik dosya hiç kimseyi LEFT yapmaz** (diğer şubelere hiç dokunmaz);
  `full_list` onayıyla da kimse ayrılmaz, dosyada olmayan şubeler havuza girer.
- Şube değiştiren öğrenci havuza girmez, "güncellendi" sayılır; havuzdaysa çıkar
  (9/A dosyası havuza atar, 9/B dosyası bulup çıkarır).
- Aynı dosyanın ikinci uygulaması değişiklik üretmez.
- Önizleme ve uygulama aynı sonucu verir; önizleme hiçbir şeyi değiştirmez.
- Import silmez ilkesi (havuza ekleme yalnız kanıtla): atlanan satırdaki
  numaranın öğrencisi havuza girmez; numarası boş öğrenci satırı havuza eklemeyi
  durdurur; hiç satır işlenemeyen dosya kimseyi havuza eklemez.
- Okul no yeniden kullanımı: ayrılmış kayıt yalnız aynı adla yeniden aktifleşir.

Personel mutabakatı: listede olmayanlar havuza girer (eski `mark_left_ids`
seçimi kalktı, gönderilse de yok sayılır), "olası aynı kişi" çiftleri, görev
metninden üye türü sınıflaması.

KİŞİSEL VERİ: havuza eklenecek kişilerin adları yalnız API yanıtındadır;
`ImportRun.report`'ta ve günlükte ad, okul no ve görev metni bulunmaz
(sentetik, ayırt edici adlarla aranır).

Bütün ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
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


def _havuzda_mi(kayit: Student | Personnel) -> bool:
    kayit.refresh_from_db()
    return kayit.leave_candidate_since is not None


def _havuzdaki_numaralar() -> list[str]:
    return [s.student_number for s in selectors.leave_pool_students()]


def _hic_kimse_ayrilmadi() -> bool:
    return not Student.all_objects.filter(status=StudentStatus.LEFT).exists()


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


# ---------------------------------------------------------------------------
# Öğrenci mutabakatı — kapsam (kod kapısı)
# ---------------------------------------------------------------------------


class TestOgrenciKapsami:
    def test_tek_subelik_dosya_hic_kimseyi_left_yapmaz_eksigi_havuza_ekler(self) -> None:
        """KORUMA TESTİ (F1 kod kapısı): yalnız 10/A'yı taşıyan dosya 10/B'ye dokunmaz;
        10/A'da eksik olan öğrenci de AYRILMAZ, ayrılış havuzuna girer."""
        _ogrenci("101", 10, "A")
        eksik = _ogrenci("102", 10, "A")
        diger = _ogrenci("201", 10, "B")
        ucuncu = _ogrenci("301", 11, "Ç")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")
        )

        assert rapor.full_list is False
        assert (rapor.pool_added_students, rapor.pool_removed_students) == (1, 0)
        assert _hic_kimse_ayrilmadi()
        assert Student.objects.filter(status=StudentStatus.ACTIVE).count() == 4
        assert _havuzda_mi(eksik) and _aktif_mi("102")
        assert not _havuzda_mi(diger) and not _havuzda_mi(ucuncu)

    def test_tam_liste_onayiyla_dosyada_olmayan_subeler_havuza_girer_kimse_ayrilmaz(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("201", 10, "B")
        sinifsiz = Student.objects.create(first_name="NAKİL", last_name="ÖĞRENCİ")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"), full_list=True
        )

        assert rapor.full_list is True
        assert rapor.pool_added_students == 2  # 10/B ve sınıfsız öğrenci
        assert _hic_kimse_ayrilmadi()
        assert _aktif_mi("201") and _aktif_mi("101")
        assert _havuzda_mi(sinifsiz)
        assert Student.all_objects.count() == 3  # kimse silinmedi

    def test_sube_degistiren_ogrenci_havuza_girmez_guncellenir(self) -> None:
        """10/A'dan 11/B'ye geçen öğrenci 10/A kapsamdayken bile eksik sayılmaz."""
        gecen = _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t102\tDENEME ÖĞRENCİ", "11/B\t101\tDENEME ÖĞRENCİ")
        )

        assert (rapor.updated_students, rapor.unchanged_students) == (1, 1)
        assert rapor.pool_added_students == 0
        gecen.refresh_from_db()
        assert (gecen.status, gecen.class_label) == (StudentStatus.ACTIVE, "11/B")
        assert gecen.leave_candidate_since is None

    def test_ayni_dosyanin_ikinci_uygulamasi_degisiklik_uretmez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("999", 10, "A")  # ilk uygulamada havuza girer
        metin = _ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10/A\t102\tYENİ ÖĞRENCİ")

        ilk = import_service.commit_students_text(text=metin)
        assert (ilk.created_students, ilk.pool_added_students) == (1, 1)

        def durum() -> dict[int, Any]:
            return {
                s.pk: (s.updated_at, s.status, s.leave_candidate_since, s.leave_candidate_run_id)
                for s in Student.all_objects.all()
            }

        oncesi = durum()
        ikinci = import_service.commit_students_text(text=metin)

        assert ikinci.already_imported is True
        assert (
            ikinci.created_students,
            ikinci.updated_students,
            ikinci.unchanged_students,
            ikinci.pool_added_students,
            ikinci.pool_removed_students,
        ) == (0, 0, 2, 0, 0)
        assert durum() == oncesi

    def test_numara_yazim_farki_ayni_ogrenciye_eslesir_ve_havuza_eklemez(self) -> None:
        """Kör indeks: e-Okul '0101' yazsa da kayıttaki '101' aynı öğrencidir."""
        ogrenci = _ogrenci("101", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t0101\tDENEME ÖĞRENCİ")
        )

        assert (rapor.unchanged_students, rapor.pool_added_students) == (1, 0)
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
# Öğrenci mutabakatı — ayrılış havuzu, rapor, önizleme
# ---------------------------------------------------------------------------


class TestOgrenciHavuzu:
    def test_havuza_giren_aktif_kalir_tarih_ve_aktarim_yazilir_kanca_cagrilmaz(self) -> None:
        """Havuza girmek ayrılış DEĞİLDİR: ayrılış kancası (F6 üyelik sonu) koşmaz."""
        kancaya_gelen: list[int] = []
        persons.register_leave_hook(lambda kisi: kancaya_gelen.append(kisi.pk))
        _ogrenci("101", 10, "A")
        eksik = _ogrenci("102", 10, "A")

        import_service.commit_students_text(text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"))

        assert kancaya_gelen == []
        eksik.refresh_from_db()
        assert (eksik.status, eksik.left_at) == (StudentStatus.ACTIVE, None)
        assert eksik.leave_candidate_since == timezone.localdate()
        kosu = ImportRun.objects.get(status=ImportStatus.COMPLETED)
        assert eksik.leave_candidate_run_id == kosu.pk

    def test_aktarim_uye_olmayan_eksigi_de_silmez(self) -> None:
        """Eski kural (hiç üye olmamış ayrılan katı silinir) KALKTI: aktarım kimseyi silmez."""
        eksik = _ogrenci("102", 10, "A")
        _ogrenci("101", 10, "A")

        import_service.commit_students_text(text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"))

        assert Student.all_objects.filter(pk=eksik.pk, deleted_at__isnull=True).exists()

    def test_sube_degisimi_9a_dosyasi_havuza_atar_9b_dosyasi_cikarir(self) -> None:
        """Şube değişimi senaryosu: 9/A'dan 9/B'ye geçen öğrenci şube şube yüklemede
        önce havuza düşer, kendi şubesinin dosyası gelince havuzdan kendiliğinden çıkar."""
        gecen = _ogrenci("101", 9, "A")
        _ogrenci("102", 9, "A")
        _ogrenci("201", 9, "B")

        dokuz_a = import_service.commit_students_text(
            text=_ogrenci_metni("9/A\t102\tDENEME ÖĞRENCİ")
        )
        assert dokuz_a.pool_added_students == 1
        assert [p.id for p in dokuz_a.pool_added] == [gecen.pk]
        assert _havuzda_mi(gecen)

        dokuz_b = import_service.commit_students_text(
            text=_ogrenci_metni("9/B\t201\tDENEME ÖĞRENCİ", "9/B\t101\tDENEME ÖĞRENCİ")
        )

        assert (dokuz_b.updated_students, dokuz_b.pool_removed_students) == (1, 1)
        assert dokuz_b.pool_added_students == 0
        gecen.refresh_from_db()
        assert (gecen.status, gecen.class_label) == (StudentStatus.ACTIVE, "9/B")
        assert (gecen.leave_candidate_since, gecen.leave_candidate_run_id) == (None, None)
        assert _havuzdaki_numaralar() == []

    def test_havuzdaki_ogrenci_ayni_subede_gorulunce_cikar_degismeyen_sayilir(self) -> None:
        ogrenci = _ogrenci("101", 10, "A")
        persons.add_to_leave_pool(ogrenci, run=None)

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")
        )

        assert (rapor.unchanged_students, rapor.pool_removed_students) == (1, 1)
        assert not _havuzda_mi(ogrenci)

    def test_havuzda_bekleyen_yeniden_eksik_kalirsa_ilk_giris_ve_aktarim_korunur(self) -> None:
        _ogrenci("101", 10, "A")
        bekleyen = _ogrenci("102", 10, "A")
        import_service.commit_students_text(text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ"))
        ilk_kosu = ImportRun.objects.get(status=ImportStatus.COMPLETED)
        gecmis = timezone.localdate() - timedelta(days=20)
        Student.objects.filter(pk=bekleyen.pk).update(leave_candidate_since=gecmis)

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10/A\t103\tYENİ ÖĞRENCİ")
        )

        assert rapor.pool_added_students == 0
        assert rapor.pool_added == []
        bekleyen.refresh_from_db()
        assert (bekleyen.leave_candidate_since, bekleyen.leave_candidate_run_id) == (
            gecmis,
            ilk_kosu.pk,
        )

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
            (c.class_label, c.created, c.updated, c.unchanged, c.to_pool) for c in rapor.classes
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
            rapor.pool_added_students,
        ) == (2, 1, 1, 1)

    def test_onizleme_uygulamayla_ayni_sonucu_verir_ve_hicbir_sey_degistirmez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("201", 10, "B")
        metin = _ogrenci_metni("10/A\t101\tDEĞİŞEN AD", "10/B\t202\tYENİ ÖĞRENCİ")

        def durum() -> list[Any]:
            return sorted(
                Student.all_objects.values_list(
                    "pk", "status", "updated_at", "leave_candidate_since", "leave_candidate_run"
                )
            )

        oncesi = durum()
        onizleme = import_service.preview_students_text(text=metin, full_list=True)

        assert durum() == oncesi
        uygulama = import_service.commit_students_text(text=metin, full_list=True)
        onizleme_sozlugu = {**onizleme.to_dict(), "dry_run": False}
        assert onizleme_sozlugu == uygulama.to_dict() | {"already_imported": False}
        assert onizleme.dry_run is True
        assert onizleme.pool_added_students == 2

    def test_api_yanitinda_havuza_eklenecek_adlar_var_kalici_raporda_yok(self) -> None:
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
        eklenecek = yanit.json()["pool_added"]
        assert [(a["full_name"], a["student_number"], a["class_label"]) for a in eklenecek] == [
            (f"{SENTETIK_AD} {SENTETIK_SOYAD}", SENTETIK_NO, "10/A")
        ]
        assert yanit.json()["pool_added_students"] == 1
        import_service.commit_students_text(text=metin)

        raporlar = json.dumps([r.report for r in ImportRun.objects.all()], ensure_ascii=False)
        assert ImportRun.objects.filter(status=ImportStatus.PREVIEWED).exists()
        assert ImportRun.objects.filter(status=ImportStatus.COMPLETED).exists()
        for iz in (SENTETIK_AD, SENTETIK_SOYAD, SENTETIK_NO, 'pool_added": ['):
            assert iz not in raporlar, iz
        assert '"pool_added_students": 1' in raporlar

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
        assert "ayrılış havuzuna 1 eklendi" in caplog.text
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
        assert kapsamli.json()["pool_added_students"] == 1
        assert varsayilan.json()["full_list"] is False
        assert varsayilan.json()["pool_added_students"] == 0
        assert _havuzdaki_numaralar() == []  # önizleme yazmaz


# ---------------------------------------------------------------------------
# Öğrenci mutabakatı — import silmez ilkesi (havuza ekleme yalnız kanıtla)
# ---------------------------------------------------------------------------


def _satir_uyarilari(rapor: import_service.StudentImportReport) -> list[tuple[int, str]]:
    return [(u.row_number, u.issue) for u in rapor.warnings]


class TestImportSilmezIlkesi:
    """KORUMA: atlanan ya da tanınamayan satır mevcut öğrenciyi havuza düşürmez."""

    def test_adi_bos_satirdaki_ogrenci_havuza_girmez(self) -> None:
        _ogrenci("101", 10, "A")
        korunan = _ogrenci("102", 10, "A", ad="KORUNAN")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10/A\t102\t")
        )

        assert [(s.row_number, s.field) for s in rapor.skipped] == [(3, "student_name")]
        assert rapor.pool_added_students == 0
        assert not _havuzda_mi(korunan)
        assert (korunan.status, korunan.first_name) == (StudentStatus.ACTIVE, "KORUNAN")
        assert _satir_uyarilari(rapor) == [(3, import_service.KEPT_ROW_MESSAGE)]

    def test_sinifi_cozulemeyen_satirdaki_ogrenci_havuza_girmez(self) -> None:
        _ogrenci("101", 10, "A")
        korunan = _ogrenci("102", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10\t0102\tDENEME ÖĞRENCİ")
        )

        assert [(s.row_number, s.field) for s in rapor.skipped] == [(3, "class")]
        assert rapor.pool_added_students == 0
        assert not _havuzda_mi(korunan)
        assert korunan.class_label == "10/A"

    def test_tam_listede_sinifi_cozulemeyen_satirdaki_ogrenci_havuza_girmez(self) -> None:
        _ogrenci("101", 10, "A")
        korunan = _ogrenci("201", 11, "B")
        _ogrenci("301", 12, "C")  # dosyada hiç yok → tam listede havuza girer

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "XX\t201\tDENEME ÖĞRENCİ"),
            full_list=True,
        )

        assert rapor.pool_added_students == 1
        assert [a.student_number for a in rapor.pool_added] == ["301"]
        assert not _havuzda_mi(korunan)

    def test_numarasi_bos_ogrenci_satiri_o_subede_havuza_eklemeyi_durdurur(self) -> None:
        """Kim olduğu bilinmeyen satır o şubedeki herhangi bir öğrenci olabilir."""
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("201", 10, "B")
        _ogrenci("202", 10, "B")  # 10/B'de dosyada yok → havuza girer

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni(
                "10/A\t101\tDENEME ÖĞRENCİ", "10/A\t\tNUMARASIZ ÖĞRENCİ", "10/B\t201\tDENEME"
            )
        )

        assert [a.student_number for a in rapor.pool_added] == ["202"]
        assert _havuzdaki_numaralar() == ["202"]
        assert [(s.row_number, s.issue) for s in rapor.skipped] == [
            (3, import_service.UNIDENTIFIED_ROW_MESSAGE)
        ]

    def test_numarasi_ve_sinifi_bos_ogrenci_satiri_hic_havuza_ekleme_uretmez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("301", 12, "C")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "\t\tKİMLİKSİZ ÖĞRENCİ"),
            full_list=True,
        )

        assert rapor.pool_added_students == 0
        assert _havuzdaki_numaralar() == []
        assert [s.issue for s in rapor.skipped] == [import_service.UNIDENTIFIED_ROW_ALL_MESSAGE]

    def test_numara_ve_adi_olmayan_not_satiri_havuza_eklemeyi_durdurmaz(self) -> None:
        """Yalnız sınıf hücresi dolu satır (not, sayaç artığı) öğrenci satırı sayılmaz."""
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ", "10/A\t\t")
        )

        assert [a.student_number for a in rapor.pool_added] == ["102"]
        assert [s.issue for s in rapor.skipped] == [import_service.NUMBER_MISSING_MESSAGE]

    def test_hic_satir_islenemeyen_dosya_kimseyi_havuza_eklemez(self) -> None:
        _ogrenci("101", 10, "A")
        _ogrenci("201", 11, "B")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t999\t", "11/B\t998\t"), full_list=True
        )

        assert (rapor.processed, rapor.pool_added_students) == (0, 0)
        assert _havuzdaki_numaralar() == []
        assert _satir_uyarilari(rapor) == [(1, import_service.NOTHING_PROCESSED_MESSAGE)]
        assert rapor.warnings[0].field == import_service.POOL_FIELD

    def test_kalici_raporda_ham_hucre_degeri_yok(self) -> None:
        """Kaymış sütunda sınıf hücresi kişi verisi taşıyabilir: yalnız API yanıtında kalır."""
        metin = _ogrenci_metni(f"{SENTETIK_AD}\t101\tDENEME ÖĞRENCİ")

        onizleme = import_service.preview_students_text(text=metin)
        import_service.commit_students_text(text=metin)

        assert [s.raw_value for s in onizleme.skipped] == [SENTETIK_AD]
        raporlar = json.dumps([r.report for r in ImportRun.objects.all()], ensure_ascii=False)
        assert ImportRun.objects.filter(status=ImportStatus.PREVIEWED).exists()
        assert SENTETIK_AD not in raporlar
        assert "raw_value" not in raporlar

    def test_onizleme_gunluge_bir_sey_yazmaz_ve_havuzu_degistirmez(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Önizleme geri sarılır: günlükte olmamış bir aktarım ya da ayrılış görünmemeli."""
        _ogrenci("101", 10, "A")
        _ogrenci("102", 10, "A")
        _ogrenci("103", 10, "A")

        with caplog.at_level(logging.DEBUG, logger="kutuphane_defteri.okul"):
            rapor = import_service.preview_students_text(
                text=_ogrenci_metni("10/A\t101\tDENEME ÖĞRENCİ")
            )

        assert rapor.pool_added_students == 2
        assert _havuzdaki_numaralar() == []
        assert "uygulandı" not in caplog.text
        assert "ayrılışı işlendi" not in caplog.text
        assert "silindi" not in caplog.text


class TestOkulNoYenidenKullanimi:
    """Okul no ayrılan öğrenciden sonra başka öğrenciye verilebilir (model teklik kısıtı)."""

    def test_ayrilmis_kayit_baska_adla_aktiflesmez_yeni_kayit_acilir(self) -> None:
        mezun = _ogrenci("777", 12, "A", ad=SENTETIK_AD)
        persons.leave_student(mezun)  # ayrılış kaydı silmez

        rapor = import_service.commit_students_text(text=_ogrenci_metni("9/C\t777\tBAŞKA YENİ"))

        assert (rapor.created_students, rapor.updated_students, rapor.reactivated_students) == (
            1,
            0,
            0,
        )
        mezun.refresh_from_db()
        assert (mezun.status, mezun.first_name, mezun.class_label) == (
            StudentStatus.LEFT,
            SENTETIK_AD,
            "12/A",
        )
        yeni = selectors.find_student_by_number("777")
        assert yeni is not None and yeni.pk != mezun.pk
        assert _satir_uyarilari(rapor) == [(2, import_service.REUSED_NUMBER_MESSAGE)]
        # Uyarı kişi adı ve numara taşımaz.
        assert "777" not in json.dumps(rapor.to_dict()["warnings"], ensure_ascii=False)

    def test_ayni_adla_donen_ogrenci_yazim_farkina_ragmen_aktiflesir(self) -> None:
        donen = _ogrenci("555", 11, "B", ad="ŞÜKRÜ")
        persons.leave_student(donen)

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("11/B\t0555\tŞükrü Öğrenci")
        )

        assert (rapor.created_students, rapor.reactivated_students) == (0, 1)
        assert rapor.warnings == []
        donen.refresh_from_db()
        assert (donen.status, donen.left_at, donen.leave_candidate_since) == (
            StudentStatus.ACTIVE,
            None,
            None,
        )

    def test_ayni_numarada_birden_cok_ayrilmis_kayittan_adi_tutan_secilir(self) -> None:
        eski = _ogrenci("888", 12, "A", ad="ESKİMEZUN")
        persons.leave_student(eski)
        donen = _ogrenci("888", 9, "A", ad="DÖNEN")
        persons.leave_student(donen)

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("10/A\t888\tESKİMEZUN ÖĞRENCİ")
        )

        assert rapor.reactivated_students == 1
        eski.refresh_from_db()
        donen.refresh_from_db()
        assert (eski.status, donen.status) == (StudentStatus.ACTIVE, StudentStatus.LEFT)


class TestYilAkislari:
    """Yıl başında öğrenciler üst sınıfa geçer; yıl sonunda mezunlar havuzdan toplu ayrılır."""

    def test_tam_liste_tek_dosyada_sinif_atlayanlar_guncellenir_mezun_havuza_girer(self) -> None:
        onuncu = _ogrenci("101", 10, "A")
        dokuzuncu = _ogrenci("050", 9, "A")
        mezun = _ogrenci("301", 12, "A")

        rapor = import_service.commit_students_text(
            text=_ogrenci_metni("11/A\t101\tDENEME ÖĞRENCİ", "10/A\t050\tDENEME ÖĞRENCİ"),
            full_list=True,
        )

        assert (rapor.updated_students, rapor.created_students) == (2, 0)
        assert [a.id for a in rapor.pool_added] == [mezun.pk]
        for ogrenci, sinif in ((onuncu, "11/A"), (dokuzuncu, "10/A")):
            ogrenci.refresh_from_db()
            assert (ogrenci.status, ogrenci.class_label) == (StudentStatus.ACTIVE, sinif)
        mezun.refresh_from_db()
        assert (mezun.status, mezun.leave_candidate_since) == (
            StudentStatus.ACTIVE,
            timezone.localdate(),
        )

    def test_sube_sube_yuklemede_ust_sinifa_gecen_gecici_olarak_havuza_duser(self) -> None:
        """BİLİNEN SINIR (kılavuz ve önizleme söyler): yeni 10/A listesi, geçen yıl
        10/A'da olup bu yıl 11'e geçen öğrenciyi havuza ekler. Kimse ayrılmaz; 11/A
        dosyası gelince çıkar. Önerilen yol bütün şubeleri içeren tek dosyadır."""
        _ogrenci("101", 10, "A")
        _ogrenci("050", 9, "A")

        onizleme = import_service.preview_students_text(
            text=_ogrenci_metni("10/A\t050\tDENEME ÖĞRENCİ")
        )

        assert [a.student_number for a in onizleme.pool_added] == ["101"]
        assert _aktif_mi("101") and _havuzdaki_numaralar() == []  # önizleme yazmaz

    def test_yil_sonu_mezunlar_havuzdan_toplu_ayrilir_kayitlar_kalir(self) -> None:
        mezunlar = [_ogrenci(f"30{i}", 12, "A") for i in range(3)]
        _ogrenci("101", 11, "A")

        import_service.commit_students_text(
            text=_ogrenci_metni("12/A\t101\tDENEME ÖĞRENCİ"), full_list=True
        )
        assert sorted(_havuzdaki_numaralar()) == ["300", "301", "302"]

        persons.resolve_leave_pool(
            students=persons.PoolDecision(leave=tuple(m.pk for m in mezunlar))
        )

        for mezun in mezunlar:
            mezun.refresh_from_db()
            assert (mezun.status, mezun.left_at, mezun.leave_candidate_since) == (
                StudentStatus.LEFT,
                timezone.localdate(),
                None,
            )
        assert Student.all_objects.count() == 4
        assert _havuzdaki_numaralar() == []


# ---------------------------------------------------------------------------
# Personel mutabakatı
# ---------------------------------------------------------------------------


class TestPersonelMutabakati:
    def test_listede_olmayan_personel_havuza_girer_aktif_kalir_kimse_ayrilmaz(self) -> None:
        _personel("AYŞE", "KAYA")
        eksik = _personel("MEHMET", "DEMİR")

        onizleme = import_service.preview_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik")
        )
        assert [(m.id, m.full_name) for m in onizleme.pool_added] == [(eksik.pk, "MEHMET DEMİR")]
        assert onizleme.pool_added_personnel == 1
        assert not _havuzda_mi(eksik)  # önizleme yazmaz

        uygulama = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik")
        )
        assert uygulama.pool_added_personnel == 1
        eksik.refresh_from_db()
        assert (eksik.is_active, eksik.left_at) == (True, None)
        assert eksik.leave_candidate_since == timezone.localdate()
        assert not Personnel.all_objects.filter(is_active=False).exists()

    def test_eski_mark_left_ids_alani_yok_sayilir_kimse_ayrilmaz(self) -> None:
        """Eski kural (işaretlenenler ayrılır) KALKTI: seçim gönderilse de karar havuzdadır."""
        _personel("AYŞE", "KAYA")
        bir = _personel("MEHMET", "DEMİR")
        iki = _personel("ZEHRA", "ÇELİK")

        yanit = APIClient().post(
            "/api/v1/imports/personnel/commit/",
            {"text": _personel_metni("AYŞE\tKAYA\t\t"), "mark_left_ids": [bir.pk, iki.pk]},
            format="multipart",
        )

        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["pool_added_personnel"] == 2
        assert "left_personnel" not in yanit.json()
        for kisi in (bir, iki):
            kisi.refresh_from_db()
            assert (kisi.is_active, kisi.left_at) == (True, None)
            assert kisi.leave_candidate_since is not None
        assert Personnel.all_objects.count() == 3

    def test_havuzdaki_personel_listede_gorulunce_havuzdan_cikar(self) -> None:
        kisi = _personel("AYŞE", "KAYA")
        persons.add_to_leave_pool(kisi, run=None)

        rapor = import_service.commit_personnel_text(text=_personel_metni("AYŞE\tKAYA\t\t"))

        assert (rapor.unchanged_personnel, rapor.pool_removed_personnel) == (1, 1)
        assert not _havuzda_mi(kisi)

    def test_ayrilmis_personel_listede_gorulunce_yeniden_aktiflesir(self) -> None:
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

        assert (rapor.created_personnel, rapor.unchanged_personnel, rapor.pool_added_personnel) == (
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
        assert _havuzda_mi(eski)  # listede olmayan eski kayıt karar bekler

        # Birleştir: eski kayıt (kaynak) yeni kayda (hedef) katılır, eski silinir.
        yanit = APIClient().post(
            f"/api/v1/personnel/{cift.existing_id}/merge/", {"into_id": cift.new_id}, format="json"
        )
        assert yanit.status_code == 200
        assert not Personnel.all_objects.filter(pk=eski.pk).exists()
        assert selectors.leave_pool_personnel() == []

    def test_olasi_ayni_kisi_kucuk_yazim_farki(self) -> None:
        eski = _personel("SELİN", "ÖZTÜRK")

        rapor = import_service.preview_personnel_text(
            text=_personel_metni("SELİM\tÖZTÜRK\tÖğretmen\t")
        )

        assert [c.existing_id for c in rapor.similar_pairs] == [eski.pk]

    def test_benzemeyen_kisiler_cift_olusturmaz(self) -> None:
        _personel("AYŞE", "KARA")
        _personel("MEHMET", "DEMİR")

        rapor = import_service.preview_personnel_text(
            text=_personel_metni("ZEYNEP\tKAYA\t\t", "CEM\tBEYAZ\t\t")
        )

        assert rapor.similar_pairs == []
        assert rapor.pool_added_personnel == 2

    def test_kalici_raporda_ad_yok_api_yanitinda_var(self) -> None:
        _personel(SENTETIK_AD, SENTETIK_SOYAD)
        metin = _personel_metni(f"{SENTETIK_AD}\tYENİSOYAD\tÖğretmen\t")

        yanit = APIClient().post(
            "/api/v1/imports/personnel/commit/", {"text": metin}, format="json"
        )

        assert yanit.status_code == 200
        assert yanit.json()["pool_added"][0]["full_name"] == f"{SENTETIK_AD} {SENTETIK_SOYAD}"
        assert yanit.json()["similar_pairs"][0]["row_name"] == f"{SENTETIK_AD} YENİSOYAD"
        run = ImportRun.objects.get(status=ImportStatus.COMPLETED)
        kalici = json.dumps(run.report, ensure_ascii=False)
        for iz in (SENTETIK_AD, SENTETIK_SOYAD, "YENİSOYAD"):
            assert iz not in kalici, iz
        assert (run.report["pool_added_personnel"], run.report["similar_pair_count"]) == (1, 1)
        assert "pool_added" not in run.report and "similar_pairs" not in run.report


class TestPersonelImportSilmezIlkesi:
    """KORUMA: tanınamayan personel satırı okulun bütün personelini havuza atamaz.

    Personelde kimlik anahtarı ad-soyaddır (okul no yok): sütunları kaymış ya da
    ad hücresi boş bir dosya listedeki HERKESİ "yok" gösterir. Öğrencideki
    "yalnız o şube" dalının karşılığı yoktur; kapı hiç kimsedir.
    """

    def test_hic_satiri_islenemeyen_dosya_kimseyi_havuza_eklemez(self) -> None:
        bir = _personel("AYŞE", "KAYA")
        iki = _personel("MEHMET", "DEMİR")

        rapor = import_service.commit_personnel_text(
            text=_personel_metni("\t\tÖğretmen\tFizik", "\t\tMemur\t")
        )

        assert (rapor.processed, rapor.pool_added_personnel) == (0, 0)
        assert rapor.pool_added == []
        assert [(u.row_number, u.field, u.issue) for u in rapor.warnings] == [
            (1, import_service.POOL_FIELD, import_service.PERSONNEL_NOTHING_PROCESSED_MESSAGE)
        ]
        for kisi in (bir, iki):
            assert not _havuzda_mi(kisi)
            assert kisi.is_active is True
        assert not Personnel.all_objects.filter(is_active=False).exists()

    def test_adi_bos_satir_hic_kimseyi_havuza_eklemez(self) -> None:
        """Tek satırı kaymış dosya: işlenen satırlar yazılır, havuza ekleme durur."""
        gorulen = _personel("AYŞE", "KAYA")
        korunan = _personel("MEHMET", "DEMİR")

        rapor = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik", "\t\tMemur\t")
        )

        assert (rapor.processed, rapor.pool_added_personnel) == (1, 0)
        assert [(s.row_number, s.field, s.issue) for s in rapor.skipped] == [
            (3, "full_name", import_service.PERSONNEL_UNIDENTIFIED_ROW_MESSAGE)
        ]
        assert not _havuzda_mi(korunan)
        assert not _havuzda_mi(gorulen)
        assert not Personnel.all_objects.filter(is_active=False).exists()

    def test_kapi_kalkinca_ayni_dosya_havuza_ekler(self) -> None:
        """Karşı kanıt: kapıyı açan tek fark tanınamayan satırdır."""
        korunan = _personel("MEHMET", "DEMİR")
        _personel("AYŞE", "KAYA")

        rapor = import_service.commit_personnel_text(
            text=_personel_metni("AYŞE\tKAYA\tÖğretmen\tFizik")
        )

        assert rapor.pool_added_personnel == 1
        assert _havuzda_mi(korunan)

    def test_zaten_havuzdaki_kisi_taninamayan_satirda_havuzda_kalir(self) -> None:
        """Kapı yalnız YENİ eklemeyi durdurur; bekleyen karar silinmez."""
        bekleyen = _personel("MEHMET", "DEMİR")
        persons.add_to_leave_pool(bekleyen, run=None)

        rapor = import_service.commit_personnel_text(text=_personel_metni("\t\tÖğretmen\t"))

        assert rapor.pool_added_personnel == 0
        assert _havuzda_mi(bekleyen)

    def test_kalici_raporda_havuz_uyarisi_var_ad_yok(self) -> None:
        _personel(SENTETIK_AD, SENTETIK_SOYAD)

        import_service.commit_personnel_text(text=_personel_metni(f"\t\t{SENTETIK_AD}\t"))

        run = ImportRun.objects.get(status=ImportStatus.COMPLETED)
        kalici = json.dumps(run.report, ensure_ascii=False)
        assert run.report["pool_added_personnel"] == 0
        assert import_service.PERSONNEL_NOTHING_PROCESSED_MESSAGE in kalici
        assert SENTETIK_AD not in kalici and SENTETIK_SOYAD not in kalici


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
