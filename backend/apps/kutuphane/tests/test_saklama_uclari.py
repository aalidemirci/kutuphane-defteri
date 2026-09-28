"""Saklama uçları (F11 — tasarım §6.4; `views_saklama.py`).

- Uçların HEPSİ yönetici kipindedir: görevli kipinde 403 `kip_yetkisiz`; izin listesine
  girmezler (`apps/okul/kip_izinleri.py` değişmez — kod kapısı "görevli izin listesi
  değişmez").
- Tetik gövdede yönetici parolasını ister (yanlışsa 400, hiçbir şey değişmez) ve kişi
  kaydı yazar (`RequiresAdminPassword` — parola kurulmamışsa 409).
- Durum ve pano yanıtları kişisizdir (ad yok); adlar yalnız `persons/` ucundadır.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.kutuphane.models import RetentionRun
from apps.kutuphane.services import saklama
from apps.kutuphane.tests.dolasim_ortak import ogrenci
from apps.okul import kip_izinleri
from apps.okul.kip import KIP
from apps.okul.models import Student
from apps.okul.services import persons
from conftest import TEST_PAROLA

pytestmark = pytest.mark.django_db

UCLAR = (
    ("get", "library-retention"),
    ("get", "library-retention-persons"),
    ("get", "library-retention-price-reminders"),
    ("post", "library-retention-apply"),
    ("get", "library-dashboard-retention"),
)
GUN = date(2026, 9, 24)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _aday(**alanlar: Any) -> Student:
    kisi = ogrenci(**alanlar)
    persons.leave_student(kisi)
    Student.all_objects.filter(pk=kisi.pk).update(left_at=date(2020, 1, 10))
    return kisi


def test_uclar_izin_listesinde_yok() -> None:
    adlar = {ad for _yontem, ad in UCLAR}
    assert not adlar & {kural.uc for kural in kip_izinleri.IZIN_LISTESI}


@pytest.mark.parametrize(("yontem", "ad"), UCLAR)
def test_gorevli_kipinde_403(client: APIClient, yontem: str, ad: str) -> None:
    KIP.gorevliye_gec()
    yanit = getattr(client, yontem)(reverse(ad), {}, format="json")
    assert yanit.status_code == 403
    assert yanit.json()["code"] == "kip_yetkisiz"


def test_durum_kisisiz_ve_on_izleme(client: APIClient) -> None:
    _aday(first_name="Deneme", last_name="Gizlisoyad")
    yanit = client.get(reverse("library-retention"))
    assert yanit.status_code == 200
    assert yanit["Cache-Control"] == "no-store"
    veri = yanit.json()
    assert "Gizlisoyad" not in yanit.content.decode("utf-8")
    assert veri["candidates"]["students"] == 1
    assert len(veri["digest"]) == 64
    assert veri["max_wait_months"] == saklama.AZAMI_BEKLEME_AY
    assert veri["policy"]["left_person_years"] == 2
    assert set(veri["residue"]) == {
        "pre_migrate",
        "pre_anonim",
        "old_databases",
        "old_databases_expired",
    }


def test_silinecek_kisiler_adlari_yalniz_bu_uctan(client: APIClient) -> None:
    _aday(first_name="Zeynep", last_name="Deneme")
    _aday(first_name="Ali", last_name="Deneme")
    veri = client.get(reverse("library-retention-persons")).json()
    assert [s["full_name"] for s in veri] == ["Ali Deneme", "Zeynep Deneme"]
    assert set(veri[0]) == {
        "kind",
        "person_id",
        "full_name",
        "person_label",
        "left_at",
        "scope",
        "terminated_at",
    }
    assert {s["scope"] for s in veri} == {saklama.KAPSAM_KISI}


def test_bedel_listesi_alanlari(client: APIClient) -> None:
    assert client.get(reverse("library-retention-price-reminders")).json() == []


def test_tetik_yanlis_parolada_400_hicbir_sey_degismez(client: APIClient) -> None:
    kisi = _aday()
    ozet = client.get(reverse("library-retention")).json()
    yanit = client.post(
        reverse("library-retention-apply"),
        {"password": "yanlis-parola", "digest": ozet["digest"]},
        format="json",
    )
    assert yanit.status_code == 400
    assert Student.all_objects.filter(pk=kisi.pk).exists()
    assert not RetentionRun.objects.exists()


def test_tetik_dogru_parolayla_uygulanir(client: APIClient) -> None:
    kisi = _aday()
    ozet = client.get(reverse("library-retention")).json()
    yanit = client.post(
        reverse("library-retention-apply"),
        {"password": TEST_PAROLA, "digest": ozet["digest"]},
        format="json",
    )
    assert yanit.status_code == 200, yanit.content
    veri = yanit.json()
    assert veri["summary"]["students"] == 1
    assert veri["backup_name"].startswith("pre-anonim-")
    assert set(veri) == {
        "ran_at",
        "backup_name",
        "summary",
        "pre_migrate_removed",
        "old_db_removed",
        "wal_truncated",
    }
    assert not Student.all_objects.filter(pk=kisi.pk).exists()
    # Liste artık boş; pano kartı kalkar.
    pano = client.get(reverse("library-dashboard-retention")).json()
    assert pano["candidates"] == 0 and pano["overdue"] is False


def test_tetik_bayat_listede_409(client: APIClient) -> None:
    _aday()
    ozet = client.get(reverse("library-retention")).json()
    _aday()
    yanit = client.post(
        reverse("library-retention-apply"),
        {"password": TEST_PAROLA, "digest": ozet["digest"]},
        format="json",
    )
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "saklama_listesi_degisti"


@pytest.mark.usefixtures("parolasiz")
def test_parola_kurulmadan_tetik_409(client: APIClient) -> None:
    yanit = client.post(
        reverse("library-retention-apply"), {"password": "x", "digest": "0" * 64}, format="json"
    )
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "parola_gerekli"


def test_pano_ozeti_alanlari(client: APIClient) -> None:
    veri = client.get(reverse("library-dashboard-retention")).json()
    assert set(veri) == {
        "candidates",
        "pending_since",
        "approval_deadline",
        "overdue",
        "price_reminders",
    }
