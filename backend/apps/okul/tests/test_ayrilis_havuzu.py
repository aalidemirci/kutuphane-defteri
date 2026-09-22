"""Ayrılış havuzu — uçlar, toplu karar, olası aynı kişi (F1 eki 7; tasarım §6.1, §8.3).

Kullanıcı kararı (22.09.2026): e-Okul aktarımı kimseyi ayırmaz ve silmez;
listede bulunmayan aktif kişi havuza girer, karar burada verilir:

- `GET leave-pool/` öğrenci ve personeli AYRI listeler, TR sıralı; havuza giriş
  tarihi ve hangi aktarımla; `?summary=true` yalnız sayılar (Genel Bakış).
- `POST leave-pool/resolve/` toplu karar: "Ayrıldı olarak işaretle" (LEFT +
  tarih, kancalar; KAYIT SİLİNMEZ) ve "Aktif kalsın" (yalnız havuzdan çıkar).
  Tek işlemdir: seçilenlerden biri havuzda değilse hiçbir karar uygulanmaz.
- Karar ucu kişi yazar: parola kurulmadan 409; iki uç da görevli kipinde 403.
- Havuzdaki personel için "olası aynı kişi" adayları (eşleşme GEREKÇESİYLE —
  TB18) ve havuzdan birleştirme.
- Günlüğe ad yazılmaz.

Bütün ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul import name_match, selectors
from apps.okul.kip import KIP
from apps.okul.models import (
    ImportRun,
    ImportStatus,
    Personnel,
    SchoolYear,
    Student,
    StudentStatus,
)
from apps.okul.services import imports as import_service
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

HAVUZ_URL = "/api/v1/leave-pool/"
KARAR_URL = "/api/v1/leave-pool/resolve/"
OGRENCI_BASLIK = "Sınıf\tOkul No\tAdı Soyadı"
PERSONEL_BASLIK = "Adı\tSoyadı\tGörevi\tBranşı"
SENTETIK_AD = "HAVUZSENTETİK"


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
def client() -> APIClient:
    return APIClient()


def _ogrenci(numara: str, sinif: int, sube: str, ad: str = "DENEME") -> Student:
    ogrenci: Student = Student.objects.create(
        first_name=ad,
        last_name="ÖĞRENCİ",
        student_number=numara,
        class_level=sinif,
        class_section=sube,
    )
    return ogrenci


def _personel(ad: str, soyad: str) -> Personnel:
    kisi: Personnel = Personnel.objects.create(first_name=ad, last_name=soyad)
    return kisi


def _havuza(*kayitlar: Student | Personnel) -> None:
    for kayit in kayitlar:
        persons.add_to_leave_pool(kayit, run=None)


def _karar(client: APIClient, govde: dict[str, Any]) -> Any:
    return client.post(KARAR_URL, govde, format="json")


# ---------------------------------------------------------------------------
# Havuz listesi
# ---------------------------------------------------------------------------


def test_havuz_listesi_ogrenci_ve_personel_ayri_tr_sirali_giris_ve_aktarimla(
    client: APIClient,
) -> None:
    for numara, sinif, sube in (("12", 10, "Ç"), ("9", 10, "Ç"), ("31", 10, "C"), ("40", 9, "A")):
        _ogrenci(numara, sinif, sube)
    for ad in ("ZEHRA", "ÇAĞLA", "CEM"):
        _personel(ad, "ÖRNEK")
    import_service.commit_students_text(
        text="\n".join([OGRENCI_BASLIK, "12/Z\t999\tYENİ ÖĞRENCİ"]), full_list=True
    )
    import_service.commit_personnel_text(text="\n".join([PERSONEL_BASLIK, "ALİ\tYENİ\t\t"]))
    ogrenci_kosusu = ImportRun.objects.get(status=ImportStatus.COMPLETED, source_type="STUDENTS")

    yanit = client.get(HAVUZ_URL)

    assert yanit.status_code == 200
    veri = yanit.json()
    assert (veri["student_count"], veri["personnel_count"]) == (4, 3)
    # Sınıf → şube (TR: C < Ç) → okul no (doğal: 9 < 12).
    assert [(s["class_label"], s["student_number"]) for s in veri["students"]] == [
        ("9/A", "40"),
        ("10/C", "31"),
        ("10/Ç", "9"),
        ("10/Ç", "12"),
    ]
    assert [p["full_name"] for p in veri["personnel"]] == [
        "CEM ÖRNEK",
        "ÇAĞLA ÖRNEK",
        "ZEHRA ÖRNEK",
    ]
    bugun = timezone.localdate().isoformat()
    ilk = veri["students"][0]
    assert ilk["leave_candidate_since"] == bugun
    assert ilk["run"] == {"id": ogrenci_kosusu.pk, "file_name": "", "date": bugun}
    assert set(ilk) == {
        "id",
        "full_name",
        "student_number",
        "class_label",
        "leave_candidate_since",
        "run",
    }
    assert set(veri["personnel"][0]) == {
        "id",
        "full_name",
        "member_kind",
        "leave_candidate_since",
        "run",
        "similar",
    }


def test_havuz_ozeti_yalniz_sayilari_doner(client: APIClient) -> None:
    ogrenci = _ogrenci("101", 10, "A", ad=SENTETIK_AD)
    kisi = _personel(SENTETIK_AD, "ÖRNEK")
    _havuza(ogrenci, kisi)
    _ogrenci("102", 10, "A")  # havuzda değil

    yanit = client.get(HAVUZ_URL, {"summary": "true"})

    assert yanit.status_code == 200
    assert yanit.json() == {"student_count": 1, "personnel_count": 1}
    assert SENTETIK_AD not in yanit.content.decode()


def test_havuz_bosken_bos_listeler(client: APIClient) -> None:
    _ogrenci("101", 10, "A")

    veri = client.get(HAVUZ_URL).json()

    assert veri == {"student_count": 0, "personnel_count": 0, "students": [], "personnel": []}


# ---------------------------------------------------------------------------
# Toplu karar
# ---------------------------------------------------------------------------


def test_toplu_karar_ayrilanlar_left_kalanlar_havuzdan_cikar_kayit_silinmez(
    client: APIClient,
) -> None:
    giden, kalan = _ogrenci("101", 12, "A"), _ogrenci("102", 12, "A")
    giden_personel, kalan_personel = _personel("MEHMET", "DEMİR"), _personel("ZEHRA", "ÇELİK")
    _havuza(giden, kalan, giden_personel, kalan_personel)

    yanit = _karar(
        client,
        {
            "students": {"leave": [giden.pk], "keep": [kalan.pk]},
            "personnel": {"leave": [giden_personel.pk], "keep": [kalan_personel.pk]},
        },
    )

    assert yanit.status_code == 200, yanit.json()
    assert yanit.json() == {
        "students_left": 1,
        "students_kept": 1,
        "personnel_left": 1,
        "personnel_kept": 1,
        "student_count": 0,
        "personnel_count": 0,
    }
    bugun = timezone.localdate()
    for kayit in (giden, kalan, giden_personel, kalan_personel):
        kayit.refresh_from_db()
        assert kayit.deleted_at is None
        assert kayit.leave_candidate_since is None
    assert (giden.status, giden.left_at) == (StudentStatus.LEFT, bugun)
    assert (kalan.status, kalan.left_at) == (StudentStatus.ACTIVE, None)
    assert (giden_personel.is_active, giden_personel.left_at) == (False, bugun)
    assert (kalan_personel.is_active, kalan_personel.left_at) == (True, None)
    assert Student.all_objects.count() == 2 and Personnel.all_objects.count() == 2


def test_karar_ayrilis_kancasini_yalniz_ayrilanlar_icin_cagirir(client: APIClient) -> None:
    gelen: list[tuple[str, int]] = []
    persons.register_leave_hook(lambda kisi: gelen.append((type(kisi).__name__, kisi.pk)))
    giden, kalan = _ogrenci("101", 12, "A"), _ogrenci("102", 12, "A")
    _havuza(giden, kalan)

    _karar(client, {"students": {"leave": [giden.pk], "keep": [kalan.pk]}})

    assert gelen == [("Student", giden.pk)]


def test_tek_kisilik_karar_ve_yinelenen_kimlik_tekillesir(client: APIClient) -> None:
    ogrenci = _ogrenci("101", 12, "A")
    _havuza(ogrenci)

    yanit = _karar(client, {"students": {"leave": [ogrenci.pk, ogrenci.pk]}})

    assert yanit.status_code == 200
    assert yanit.json()["students_left"] == 1


def test_ayni_kisi_iki_listede_reddedilir(client: APIClient) -> None:
    ogrenci = _ogrenci("101", 12, "A")
    _havuza(ogrenci)

    yanit = _karar(client, {"students": {"leave": [ogrenci.pk], "keep": [ogrenci.pk]}})

    assert yanit.status_code == 400
    assert yanit.json()["message"] == persons.POOL_CONFLICT_MESSAGE
    ogrenci.refresh_from_db()
    assert (ogrenci.status, ogrenci.leave_candidate_since) == (
        StudentStatus.ACTIVE,
        timezone.localdate(),
    )


def test_havuzda_olmayan_kisi_varsa_hicbir_karar_uygulanmaz(client: APIClient) -> None:
    """Tek işlem: geçerli seçim de geri sarılır; kullanıcı listeyi yeniler."""
    havuzdaki = _ogrenci("101", 12, "A")
    havuzda_olmayan = _ogrenci("102", 12, "A")
    ayrilmis = _personel("MEHMET", "DEMİR")
    _havuza(havuzdaki)
    persons.leave_personnel(ayrilmis)

    for govde in (
        {"students": {"leave": [havuzdaki.pk, havuzda_olmayan.pk]}},
        {"students": {"leave": [havuzdaki.pk]}, "personnel": {"keep": [ayrilmis.pk]}},
        {"students": {"leave": [havuzdaki.pk, 99999]}},
    ):
        yanit = _karar(client, govde)
        assert yanit.status_code == 400, govde
        assert yanit.json()["message"] == persons.POOL_STALE_MESSAGE

    havuzdaki.refresh_from_db()
    assert (havuzdaki.status, havuzdaki.leave_candidate_since) == (
        StudentStatus.ACTIVE,
        timezone.localdate(),
    )


def test_bos_karar_ve_bozuk_govde_reddedilir(client: APIClient) -> None:
    bos = _karar(client, {})
    assert bos.status_code == 400
    assert bos.json()["message"] == persons.POOL_EMPTY_MESSAGE

    bozuk = _karar(client, {"students": {"leave": ["abc"]}})
    assert bozuk.status_code == 400
    assert bozuk.json()["code"] == "validation_error"


def test_havuzdaki_kisi_aktif_olmalidir_db_kisiti() -> None:
    """Son savunma: ayrılmış kişi havuzda bekleyemez (ayrılış yolu havuzu temizler)."""
    ogrenci = _ogrenci("101", 12, "A")
    kisi = _personel("AYŞE", "KAYA")
    persons.leave_student(ogrenci)
    persons.leave_personnel(kisi)

    with pytest.raises(IntegrityError), transaction.atomic():
        Student.objects.filter(pk=ogrenci.pk).update(leave_candidate_since=timezone.localdate())
    with pytest.raises(IntegrityError), transaction.atomic():
        Personnel.objects.filter(pk=kisi.pk).update(leave_candidate_since=timezone.localdate())


def test_ayrilmis_kisi_servisle_havuza_eklenemez() -> None:
    ogrenci = _ogrenci("101", 12, "A")
    persons.leave_student(ogrenci)

    with pytest.raises(Exception, match="zaten ayrıldı"):
        persons.add_to_leave_pool(ogrenci, run=None)


def test_karar_gunlukte_ad_birakmaz(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    ogrenci = _ogrenci("98765", 12, "A", ad=SENTETIK_AD)
    kisi = _personel(SENTETIK_AD, "ÖRNEK")
    _havuza(ogrenci, kisi)

    with caplog.at_level(logging.DEBUG):
        _karar(client, {"students": {"leave": [ogrenci.pk]}, "personnel": {"keep": [kisi.pk]}})

    assert "Ayrılış havuzu kararı: 1 öğrenci ayrıldı" in caplog.text
    for iz in (SENTETIK_AD, "98765"):
        assert iz not in caplog.text


# ---------------------------------------------------------------------------
# Parola ve kip kapıları
# ---------------------------------------------------------------------------


def test_parolasizken_karar_ucu_409_liste_acik(parolasiz: Path, client: APIClient) -> None:
    yanit = _karar(client, {"students": {"leave": [1]}})

    assert yanit.status_code == 409
    assert yanit.json()["code"] == "parola_gerekli"
    assert client.get(HAVUZ_URL).status_code == 200


def test_gorevli_kipinde_havuz_uclari_403(client: APIClient) -> None:
    ogrenci = _ogrenci("101", 12, "A")
    _havuza(ogrenci)
    KIP.gorevliye_gec()

    for yanit in (
        client.get(HAVUZ_URL),
        client.get(HAVUZ_URL, {"summary": "true"}),
        _karar(client, {"students": {"leave": [ogrenci.pk]}}),
    ):
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"
    ogrenci.refresh_from_db()
    assert ogrenci.status == StudentStatus.ACTIVE


# ---------------------------------------------------------------------------
# Olası aynı kişi ve havuzdan birleştirme
# ---------------------------------------------------------------------------


def test_havuzdaki_personel_icin_olasi_ayni_kisi_ve_havuzdan_birlestirme(
    client: APIClient,
) -> None:
    """Soyadı değişimi: listede 'AYŞE BEYAZ' var, kayıttaki 'AYŞE KARA' havuza düşer."""
    eski = _personel("AYŞE", "KARA")
    _personel("ALİ", "VELİ")
    import_service.commit_personnel_text(
        text="\n".join([PERSONEL_BASLIK, "ALİ\tVELİ\t\t", "AYŞE\tBEYAZ\tÖğretmen\t"])
    )
    # Ad şifreli: DB'de aranmaz, Python'da süzülür.
    yeni = next(p for p in Personnel.objects.all() if p.full_name == "AYŞE BEYAZ")

    veri = client.get(HAVUZ_URL).json()

    # Aday satırı NEDEN aday olduğunu ve ayırt edici bilgisini taşır (TB18).
    assert [(p["id"], p["similar"]) for p in veri["personnel"]] == [
        (
            eski.pk,
            [
                {
                    "id": yeni.pk,
                    "full_name": "AYŞE BEYAZ",
                    "member_kind": "TEACHER",
                    "created_on": timezone.localdate().isoformat(),
                    "reason": "ad_ayni_soyad_farkli",
                }
            ],
        )
    ]
    birlestir = client.post(
        f"/api/v1/personnel/{eski.pk}/merge/", {"into_id": yeni.pk}, format="json"
    )
    assert birlestir.status_code == 200
    assert not Personnel.all_objects.filter(pk=eski.pk).exists()
    assert client.get(HAVUZ_URL, {"summary": "true"}).json()["personnel_count"] == 0


def test_olasi_ayni_kisi_havuza_giristen_once_acilmis_kayitlarda_aranmaz() -> None:
    """Okulda aynı adı taşıyan eski öğretmen her havuz kişisine "benzer" görünmesin."""
    eski_ayse = _personel("AYŞE", "DEMİR")
    Personnel.objects.filter(pk=eski_ayse.pk).update(
        created_at=timezone.now() - timedelta(days=400)
    )
    havuzdaki = _personel("AYŞE", "KARA")
    yeni_ayse = _personel("AYŞE", "BEYAZ")
    _havuza(havuzdaki)

    adaylar = selectors.leave_pool_similar_personnel(selectors.leave_pool_personnel())

    assert [a.person.pk for a in adaylar[havuzdaki.pk]] == [yeni_ayse.pk]


def test_aday_gerekcesi_ucta_dondurulur(client: APIClient) -> None:
    """Her aday satırı neden aday olduğunu söyler: ad eşitliği mi, yazım farkı mı (TB18)."""
    havuzdaki = _personel("SELİN", "ÖZTÜRK")
    ad_ayni = _personel("SELİN", "BEYAZ")
    yazim = _personel("SELİM", "ÖZTÜRK")
    _havuza(havuzdaki)

    (kisi,) = client.get(HAVUZ_URL).json()["personnel"]

    assert {a["id"]: a["reason"] for a in kisi["similar"]} == {
        ad_ayni.pk: "ad_ayni_soyad_farkli",
        yazim.pk: "yazim_farki",
    }


def test_ayni_ad_soyad_adayi_ad_ayni_soyad_farkli_diye_sunulmaz() -> None:
    """Birebir aynı ad-soyad taşıyan aday kendi gerekçesiyle gelir (yanıltmasın)."""
    havuzdaki = _personel("DENİZ", "YILDIZ")
    adas = _personel("DENİZ", "YILDIZ")
    _havuza(havuzdaki)

    adaylar = selectors.leave_pool_similar_personnel(selectors.leave_pool_personnel())

    assert [(a.person.pk, a.reason) for a in adaylar[havuzdaki.pk]] == [
        (adas.pk, name_match.MatchReason.SAME_FULL_NAME)
    ]
