"""Kurulum sihirbazı uçları + kurulum durumu + Başlangıç Yol Haritası (F1-E).

`setup/status/` alan kümesi hem arayüz kurulum kapısının hem masaüstü sağlık
denetiminin sözleşmesidir — küme değişirse FE `SetupStatus` tipi ve
`desktop/server.py` birlikte gözden geçirilir.

Kod kapısı (tasarım §14.1 F1, sözleşme E): sihirbaz parola adımı olmadan
ilerlemez ve `setup/complete/` eksik adımda Türkçe 400 (`kurulum_eksik`) ile
HANGİ adımın eksik olduğunu söyler — her dal ayrı testtedir.

Bu dosyada kurtarma anahtarı DOĞRULANMIŞ başlanır (`anahtar_dogrulanmis`,
otomatik): 1. adımın ikinci koşulu (F1 eki, karar 2) ve damgasız kurulumun
reddi `test_kurtarma_dogrulama.py`'dedir.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.models import Holiday, HolidayKind, SchoolConfig, SchoolLevel, Student
from apps.okul.services import app_password
from apps.okul.services import school_year as school_year_service
from apps.okul.services import setup as setup_service
from apps.okul.services import terms as term_service
from apps.okul.tests.kip_ortak import SahteSaat
from conftest import TEST_KURTARMA_ANAHTARI, TEST_PAROLA

DURUM_ALANLARI = {
    "setup_completed",
    "password_set",
    "recovery_key_confirmed",
    "school_name",
    "school_info_complete",
    "has_active_school_year",
    "active_school_year",
    "missing_steps",
    "student_count",
    "personnel_count",
    "class_section_count",
    "school_break_count",
    "roadmap",
}

TAM_OKUL = {
    "school_name": "Örnek Anadolu Lisesi",
    "province": "İstanbul",
    "district": "Örnek",
    "kademe": SchoolLevel.ORTAOGRETIM,
    "kisa_ad": "Örnek AL",
    "demirbas_onayi": True,
    "demirbas_no": "BLG-2026-017",
}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def anahtar_dogrulanmis(guvenlik_ortami: Path) -> None:
    """Varsayılan ortamın kurtarma anahtarı saklandı olarak damgalanır (modül başlığı)."""
    app_password.confirm_recovery_key(TEST_KURTARMA_ANAHTARI)


def _okul_bilgileri(**degisiklik: Any) -> None:
    setup_service.update_school_config(fields={**TAM_OKUL, **degisiklik})


def _aktif_yil(*, donemler: bool = True) -> int:
    yil = school_year_service.create_school_year(
        name="2026-2027", start_date=date(2026, 9, 7), end_date=date(2027, 6, 25), activate=True
    )
    if donemler:
        term_service.configure_terms(
            yil, first_end=date(2027, 1, 22), second_start=date(2027, 2, 8)
        )
    return yil.pk


def _tamamla(client: APIClient) -> Any:
    return client.post("/api/v1/setup/complete/")


@pytest.mark.django_db
class TestSetupStatus:
    def test_alan_kumesi_ve_bos_kurulum(self, client: APIClient) -> None:
        yanit = client.get("/api/v1/setup/status/")
        assert yanit.status_code == 200
        veri = yanit.json()
        assert set(veri.keys()) == DURUM_ALANLARI
        assert veri["setup_completed"] is False
        # Varsayılan test ortamı: parola kurulu (anahtar doğrulanmış); okul ve takvim eksik.
        assert veri["password_set"] is True
        assert veri["recovery_key_confirmed"] is True
        assert veri["missing_steps"] == ["school", "calendar"]
        assert veri["active_school_year"] is None
        assert veri["school_break_count"] == 0
        assert veri["roadmap"] == {"marks": {}, "hidden": False}

    def test_parolasizken_ilk_eksik_adim_parola(self, client: APIClient, parolasiz: Path) -> None:
        veri = client.get("/api/v1/setup/status/").json()
        assert veri["password_set"] is False
        assert veri["recovery_key_confirmed"] is False
        assert veri["missing_steps"] == ["password", "school", "calendar"]

    def test_kurulum_sonrasi_sayimlar_ve_aktif_yil(self, client: APIClient) -> None:
        _okul_bilgileri()
        yil_id = _aktif_yil()
        assert _tamamla(client).status_code == 200

        veri = client.get("/api/v1/setup/status/").json()
        assert veri["setup_completed"] is True
        assert veri["school_name"] == "Örnek Anadolu Lisesi"
        assert veri["school_info_complete"] is True
        assert veri["has_active_school_year"] is True
        assert veri["missing_steps"] == []
        assert veri["active_school_year"] == {
            "id": yil_id,
            "name": "2026-2027",
            "start_date": "2026-09-07",
            "end_date": "2027-06-25",
            "terms_ready": True,
        }

    def test_ogrenciye_kapali_gun_sayisi_aktif_yil_araligiyla_ve_turuyle_sinirli(
        self, client: APIClient
    ) -> None:
        _aktif_yil()
        Holiday.objects.create(
            name="Yarıyıl",
            start_date=date(2027, 1, 25),
            end_date=date(2027, 2, 5),
            kind=HolidayKind.SCHOOL_BREAK,
        )
        # Yıl başlamadan önceki ara tatil ve resmî tatil sayılmaz.
        Holiday.objects.create(
            name="Eski ara tatil",
            start_date=date(2026, 4, 13),
            end_date=date(2026, 4, 17),
            kind=HolidayKind.SCHOOL_BREAK,
        )
        Holiday.objects.create(
            name="Cumhuriyet Bayramı",
            start_date=date(2026, 10, 29),
            end_date=date(2026, 10, 29),
            kind=HolidayKind.OFFICIAL,
        )
        assert client.get("/api/v1/setup/status/").json()["school_break_count"] == 1

    def test_durum_kisisel_veri_icermez(self, client: APIClient) -> None:
        """Sağlık denetimi ucu da olduğu için yanıtta kişi adı ve okul no geçmez."""
        Student.objects.create(
            first_name="ZEYNEP",
            last_name="KARADUMAN",
            student_number="4817",
            class_level=9,
            class_section="A",
        )
        metin = client.get("/api/v1/setup/status/").content.decode("utf-8")
        for parca in ("ZEYNEP", "KARADUMAN", "4817"):
            assert parca not in metin
        assert client.get("/api/v1/setup/status/").json()["student_count"] == 1


@pytest.mark.django_db
class TestSetupComplete:
    """`setup/complete/` kapısı — eksik her adım ayrı dal (kod kapısı maddesi)."""

    def test_uc_adim_tamamsa_tamamlar(self, client: APIClient) -> None:
        _okul_bilgileri()
        _aktif_yil()
        yanit = _tamamla(client)
        assert yanit.status_code == 200
        assert yanit.json() == {"setup_completed": True}
        assert SchoolConfig.load().setup_completed is True

    def test_parola_adimi_olmadan_tamamlanmaz(self, client: APIClient, parolasiz: Path) -> None:
        _okul_bilgileri()
        _aktif_yil()
        yanit = _tamamla(client)
        assert yanit.status_code == 400
        govde = yanit.json()
        assert govde["code"] == "kurulum_eksik"
        assert "1. adım (yönetici parolası)" in govde["message"]
        assert "2. adım" not in govde["message"] and "3. adım" not in govde["message"]
        assert SchoolConfig.load().setup_completed is False

    @pytest.mark.parametrize(
        ("degisiklik", "beklenen"),
        [
            ({"school_name": ""}, "okul adı"),
            ({"kademe": ""}, "kademe"),
            ({"kisa_ad": "  "}, "kısa ad"),
            ({"demirbas_onayi": False}, "“Bu bilgisayar okul demirbaşıdır” onayı"),
        ],
        ids=["okul_adi", "kademe", "kisa_ad", "demirbas_onayi"],
    )
    def test_okul_bilgisi_eksikse_hangi_alan_oldugunu_soyler(
        self, client: APIClient, degisiklik: dict[str, Any], beklenen: str
    ) -> None:
        _okul_bilgileri(**degisiklik)
        _aktif_yil()
        yanit = _tamamla(client)
        assert yanit.status_code == 400
        mesaj = yanit.json()["message"]
        assert "2. adım (okul bilgileri)" in mesaj
        assert f"{beklenen} eksik." in mesaj
        assert SchoolConfig.load().setup_completed is False

    def test_kurulum_suresince_sure_islemez_tamamlaninca_sayaclar_sifirdan_baslar(
        self, client: APIClient
    ) -> None:
        """Karar 2-1: sihirbazda geçen süre yönetici kipini düşürmez; bitince tam süre."""
        saat = SahteSaat()
        KIP._reset_for_tests(saat=saat)
        assert KIP.durum() == "yonetici"
        _okul_bilgileri()
        _aktif_yil()
        saat.ilerlet(45 * 60)  # sihirbazda 45 dk (boşta ve mutlak süreden uzun)
        assert KIP.durum() == "yonetici"
        saat.ilerlet(170)

        assert _tamamla(client).status_code == 200

        ozet = KIP.ozet()
        assert ozet["durum"] == "yonetici"
        assert ozet["bosta_kalan_sn"] == 180
        assert ozet["mutlak_kalan_sn"] == 1800
        saat.ilerlet(180)
        assert KIP.durum() == "gorevli"

    def test_demirbas_no_istege_baglidir(self, client: APIClient) -> None:
        _okul_bilgileri(demirbas_no="")
        _aktif_yil()
        assert _tamamla(client).status_code == 200

    def test_aktif_ders_yili_yoksa_reddeder(self, client: APIClient) -> None:
        _okul_bilgileri()
        yanit = _tamamla(client)
        assert yanit.status_code == 400
        assert "3. adım (ders yılı)" in yanit.json()["message"]

    def test_donemleri_tanimlanmamis_aktif_yil_yetmez(self, client: APIClient) -> None:
        _okul_bilgileri()
        _aktif_yil(donemler=False)
        veri = client.get("/api/v1/setup/status/").json()
        assert veri["active_school_year"]["terms_ready"] is False
        assert veri["missing_steps"] == ["calendar"]
        yanit = _tamamla(client)
        assert yanit.status_code == 400
        assert "iki dönemin tarihleri" in yanit.json()["message"]

    def test_birden_cok_eksik_adim_sirayla_listelenir(
        self, client: APIClient, parolasiz: Path
    ) -> None:
        mesaj = _tamamla(client).json()["message"]
        assert mesaj.startswith("Kurulum tamamlanamadı. ")
        assert mesaj.index("1. adım") < mesaj.index("2. adım") < mesaj.index("3. adım")
        # İç kodlar kullanıcı metnine girmez (sözlük §2).
        for kod in ("password", "calendar", "F1", "E14"):
            assert kod not in mesaj


@pytest.mark.django_db
class TestSchoolConfigApi:
    def test_kunye_ve_hazirlik_guncellenir(self, client: APIClient) -> None:
        yanit = client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "Örnek Okul", "has_prep_class": True},
            format="json",
        )
        assert yanit.status_code == 200
        assert yanit.json()["has_prep_class"] is True
        assert SchoolConfig.load().grade_levels == (0, *range(1, 13))

    def test_kademe_kisa_ad_ve_demirbas_alanlari_yazilir_ve_okunur(self, client: APIClient) -> None:
        yanit = client.put("/api/v1/setup/school-config/", TAM_OKUL, format="json")
        assert yanit.status_code == 200, yanit.json()
        veri = client.get("/api/v1/setup/school-config/").json()
        assert veri["kademe"] == "ORTAOGRETIM"
        assert veri["kisa_ad"] == "Örnek AL"
        assert veri["demirbas_onayi"] is True
        assert veri["demirbas_no"] == "BLG-2026-017"

    def test_kismi_put_diger_alanlari_silmez(self, client: APIClient) -> None:
        client.put("/api/v1/setup/school-config/", TAM_OKUL, format="json")
        client.put("/api/v1/setup/school-config/", {"demirbas_no": "YENİ-1"}, format="json")
        config = SchoolConfig.load()
        assert config.kademe == "ORTAOGRETIM"
        assert config.demirbas_onayi is True
        assert config.demirbas_no == "YENİ-1"

    @pytest.mark.parametrize(
        ("alan", "bos_deger", "ileti"),
        [
            ("school_name", "  ", "Okul adı zorunludur."),
            ("kademe", "", "Kademe seçin."),
            ("kisa_ad", " ", "Kısa ad zorunludur."),
            (
                "demirbas_onayi",
                False,
                "Program yalnız okul demirbaşı bilgisayara kurulur; onay zorunludur.",
            ),
        ],
    )
    def test_zorunlu_alan_gonderilirse_bosaltilamaz(
        self, client: APIClient, alan: str, bos_deger: object, ileti: str
    ) -> None:
        """KORUMA: kurulum bittikten sonra Okul Bilgileri'nden zorunlu alan geri alınamaz.

        Kısmi PUT gönderilmeyen alana dokunmaz; ama gönderilen zorunlu alan boş
        olamaz — aksi hâlde "tamamlanmış ama okul adımı eksik" kurulum doğar.
        """
        client.put("/api/v1/setup/school-config/", TAM_OKUL, format="json")

        yanit = client.put(
            "/api/v1/setup/school-config/", {**TAM_OKUL, alan: bos_deger}, format="json"
        )

        assert yanit.status_code == 400
        assert yanit.json()["fields"][alan] == [ileti]
        assert setup_service.missing_school_fields(SchoolConfig.load()) == []

    def test_kademe_kademe_disi_deger_turkce_reddedilir(self, client: APIClient) -> None:
        yanit = client.put("/api/v1/setup/school-config/", {"kademe": "UNIVERSITE"}, format="json")
        assert yanit.status_code == 400
        assert yanit.json()["fields"]["kademe"] == ["Geçerli bir kademe seçin."]

    def test_kisa_ad_24_karakteri_asamaz(self, client: APIClient) -> None:
        yanit = client.put("/api/v1/setup/school-config/", {"kisa_ad": "Ç" * 25}, format="json")
        assert yanit.status_code == 400
        assert yanit.json()["fields"]["kisa_ad"] == ["Kısa ad en çok 24 karakter olabilir."]

    def test_setup_completed_put_ile_degistirilemez(self, client: APIClient) -> None:
        """Kapı alanı yalnız `setup/complete/` ucuyla açılır (read-only)."""
        client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "X", "setup_completed": True},
            format="json",
        )
        assert SchoolConfig.load().setup_completed is False

    def test_gecersiz_hazirlik_bayragi_reddedilir(self, client: APIClient) -> None:
        yanit = client.put(
            "/api/v1/setup/school-config/",
            {"school_name": "X", "has_prep_class": "belki"},
            format="json",
        )
        assert yanit.status_code == 400
        assert "has_prep_class" in yanit.json()["fields"]

    def test_yol_haritasi_school_config_uzerinden_yazilamaz(self, client: APIClient) -> None:
        client.put(
            "/api/v1/setup/school-config/",
            {"yol_haritasi": {"isaretler": {"kurtarma_zarfi": "2026-09-22"}}},
            format="json",
        )
        assert SchoolConfig.load().yol_haritasi == {}


@pytest.mark.django_db
class TestYolHaritasi:
    """Başlangıç Yol Haritası — kullanıcı işaretleri `SchoolConfig.yol_haritasi`'nda."""

    def _isaretle(self, client: APIClient, madde: str, done: bool = True) -> Any:
        return client.post("/api/v1/setup/roadmap/", {"item": madde, "done": done}, format="json")

    def test_madde_isaretlenir_ve_durumda_gorunur(self, client: APIClient) -> None:
        yanit = self._isaretle(client, "kurtarma_zarfi")
        assert yanit.status_code == 200
        bugun = timezone.localdate().isoformat()
        assert yanit.json() == {"marks": {"kurtarma_zarfi": bugun}, "hidden": False}
        durum = client.get("/api/v1/setup/status/").json()
        assert durum["roadmap"]["marks"] == {"kurtarma_zarfi": bugun}

    def test_isaret_kaldirilir(self, client: APIClient) -> None:
        self._isaretle(client, "parola_paylasimi")
        yanit = self._isaretle(client, "parola_paylasimi", done=False)
        assert yanit.json()["marks"] == {}

    def test_kendiliginden_tespit_edilen_madde_elle_isaretlenemez(self, client: APIClient) -> None:
        yanit = self._isaretle(client, "ogrenci_aktarimi")
        assert yanit.status_code == 400
        assert yanit.json()["message"] == "Bu madde elle işaretlenemez."

    def test_govde_madde_ya_da_gizleme_olmali(self, client: APIClient) -> None:
        for govde in ({}, {"item": "kurtarma_zarfi"}, {"hidden": True, "item": "x", "done": True}):
            yanit = client.post("/api/v1/setup/roadmap/", govde, format="json")
            assert yanit.status_code == 400, govde

    def test_eksik_madde_varken_gizlenemez(self, client: APIClient) -> None:
        for madde in setup_service.ROADMAP_MANUAL_ITEMS:
            self._isaretle(client, madde)
        # Öğrenci/personel aktarılmadı, öğrenciye kapalı gün yok.
        yanit = client.post("/api/v1/setup/roadmap/", {"hidden": True}, format="json")
        assert yanit.status_code == 400
        assert "bütün maddeler tamamlanınca" in yanit.json()["message"]
        assert SchoolConfig.load().yol_haritasi.get("gizli") is not True

    def test_butun_maddeler_tamamken_gizlenir_isaret_kalkinca_yeniden_gorunur(
        self, client: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for madde in setup_service.ROADMAP_MANUAL_ITEMS:
            self._isaretle(client, madde)
        gercek = setup_service.setup_status

        def dolu_durum() -> dict[str, Any]:
            return {**gercek(), "student_count": 3, "personnel_count": 2, "school_break_count": 1}

        monkeypatch.setattr(setup_service, "setup_status", dolu_durum)
        yanit = client.post("/api/v1/setup/roadmap/", {"hidden": True}, format="json")
        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["hidden"] is True

        yanit = self._isaretle(client, "btr_gorusmesi", done=False)
        assert yanit.json()["hidden"] is False

    def _hepsi_tamam(self, client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Yol haritasının bütün maddelerini tamamlar (gizlemenin ön koşulu)."""
        for madde in setup_service.ROADMAP_MANUAL_ITEMS:
            self._isaretle(client, madde)
        gercek = setup_service.setup_status

        def dolu_durum() -> dict[str, Any]:
            return {**gercek(), "student_count": 3, "personnel_count": 2, "school_break_count": 1}

        monkeypatch.setattr(setup_service, "setup_status", dolu_durum)

    def test_kurtarma_anahtari_damgasizken_kart_gizli_kalmaz(
        self, client: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """KORUMA: "kurtarma anahtarı doğrulanmadı" uyarısı kartın İÇİNDEDİR.

        Kart gizliyken uyarı da basılmazdı ve kartı geri getirecek bir arayüz
        yolu yoktur (işaret kutuları ve gizleme düğmesi kartın içinde). Damgasız
        kurulumda kart görünür kalır; SAKLANAN gizleme tercihi silinmez.
        """
        self._hepsi_tamam(client, monkeypatch)
        assert (
            client.post("/api/v1/setup/roadmap/", {"hidden": True}, format="json").json()["hidden"]
            is True
        )

        yeni_anahtar = app_password.renew_recovery_key(password=TEST_PAROLA)  # damga silinir

        durum = client.get("/api/v1/setup/status/").json()
        assert durum["recovery_key_confirmed"] is False
        assert durum["roadmap"]["hidden"] is False
        assert SchoolConfig.load().yol_haritasi["gizli"] is True  # tercih duruyor

        app_password.confirm_recovery_key(yeni_anahtar)
        assert client.get("/api/v1/setup/status/").json()["roadmap"]["hidden"] is True

    def test_kurtarma_anahtari_damgasizken_gizlenemez(
        self, client: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._hepsi_tamam(client, monkeypatch)
        app_password.renew_recovery_key(password=TEST_PAROLA)

        yanit = client.post("/api/v1/setup/roadmap/", {"hidden": True}, format="json")

        assert yanit.status_code == 400
        assert "doğrulanmadan" in yanit.json()["message"]
        assert SchoolConfig.load().yol_haritasi.get("gizli") is not True

    def test_damgasizken_isaretleme_saklanan_gizleme_tercihini_silmez(
        self, client: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Yazma yolu SAKLANAN durumu okur: kapı tercihi sessizce sıfırlamaz."""
        self._hepsi_tamam(client, monkeypatch)
        client.post("/api/v1/setup/roadmap/", {"hidden": True}, format="json")
        yeni_anahtar = app_password.renew_recovery_key(password=TEST_PAROLA)

        yanit = self._isaretle(client, "btr_gorusmesi")

        assert yanit.json()["hidden"] is False  # arayüz: kart görünür
        assert SchoolConfig.load().yol_haritasi["gizli"] is True  # saklanan: gizli
        app_password.confirm_recovery_key(yeni_anahtar)
        assert client.get("/api/v1/setup/status/").json()["roadmap"]["hidden"] is True

    def test_bozuk_ya_da_bilinmeyen_kayit_disari_sizmaz(self) -> None:
        config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
        config.yol_haritasi = {
            "isaretler": {"kurtarma_zarfi": "2026-09-22", "bilinmeyen": "x", "btr_gorusmesi": 5},
            "gizli": "evet",
        }
        config.save()
        assert setup_service.roadmap_state(SchoolConfig.load()) == {
            "marks": {"kurtarma_zarfi": "2026-09-22"},
            "hidden": True,
        }
        config.yol_haritasi = ["liste"]
        config.save()
        assert setup_service.roadmap_state(SchoolConfig.load()) == {"marks": {}, "hidden": False}


@pytest.mark.django_db
class TestGradeLevelsApi:
    def test_seviyeler_okul_ici_sabitten_gelir(self, client: APIClient) -> None:
        veri = client.get("/api/v1/grade-levels/").json()
        assert [x["value"] for x in veri["levels"]] == list(range(1, 13))
        assert veri["levels"][0] == {"value": 1, "label": "1"}
        assert veri["prep_enabled"] is False

    def test_hazirlik_acilinca_listeye_girer(self, client: APIClient) -> None:
        setup_service.update_school_config(fields={"has_prep_class": True})
        veri = client.get("/api/v1/grade-levels/").json()
        assert veri["levels"][0] == {"value": 0, "label": "Hazırlık"}
        assert veri["prep_enabled"] is True

    def test_kademe_seviyeleri_kisitlamaz(self, client: APIClient) -> None:
        """F1'de kademe yalnız saklanır; Md. 19 ve sınıf kitaplığı kuralları F6/F7'de."""
        setup_service.update_school_config(fields={"kademe": SchoolLevel.ILKOKUL})
        veri = client.get("/api/v1/grade-levels/").json()
        assert [x["value"] for x in veri["levels"]] == list(range(1, 13))


@pytest.mark.django_db
class TestSchoolYearTerms:
    def test_donem_yapilandirma(self, client: APIClient) -> None:
        yil = client.post(
            "/api/v1/school-years/",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-30"},
            format="json",
        ).json()
        yanit = client.put(
            f"/api/v1/school-years/{yil['id']}/terms/",
            {"first_term_end": "2027-01-16", "second_term_start": "2027-02-01"},
            format="json",
        )
        assert yanit.status_code == 200
        donemler = yanit.json()
        assert [d["sequence"] for d in donemler] == [1, 2]
        assert donemler[0]["start_date"] == "2026-09-01"
        assert donemler[1]["end_date"] == "2027-06-30"

    def test_ters_donem_tarihleri_reddedilir(self, client: APIClient) -> None:
        yil = client.post(
            "/api/v1/school-years/",
            {"name": "2026-2027", "start_date": "2026-09-01", "end_date": "2027-06-30"},
            format="json",
        ).json()
        yanit = client.put(
            f"/api/v1/school-years/{yil['id']}/terms/",
            {"first_term_end": "2027-02-01", "second_term_start": "2027-01-16"},
            format="json",
        )
        assert yanit.status_code == 400


def test_spa_catchall_arayuz_derlenmemisken_503_ve_turkce_yonerge() -> None:
    """SPA catch-all, dist yokken beyaz ekran yerine Türkçe yönerge döndürür."""
    yanit = APIClient().get("/olmayan-bir-rota")
    assert yanit.status_code in (200, 503)  # dist derlenmişse 200, temiz depoda 503
    if yanit.status_code == 503:
        assert "Arayüz derlenmemiş".encode() in yanit.content


@pytest.mark.django_db
def test_update_school_config_whitelist_disi_alan_yazmaz() -> None:
    setup_service.update_school_config(
        fields={"school_name": "X", "app_password_hash": "hack", "setup_completed": True}
    )
    config = SchoolConfig.load()
    assert config.app_password_hash == ""
    assert config.setup_completed is False


@pytest.mark.django_db
def test_letterhead_identity_bos_okul_adi_yer_tutucuya_duser() -> None:
    assert setup_service.get_letterhead_identity()["school_name"] == "Okul"
