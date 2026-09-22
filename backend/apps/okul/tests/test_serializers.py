"""`okul` serializer doğrulamalarının başka dosyada sınanmayan dalları.

Kişi/şube doğrulamaları kendi test dosyalarındadır (`test_persons`,
`test_class_sections`). Burada kalanlar:

- Serializer alan kümeleri — ön yüz tiplerinin sözleşmesi (anlık görüntü, T13).
  Kaldırılan KS alanlarının (zil, vardiya, şube kümesi, zümre, cinsiyet, okul
  türü/çizelge) geri sızması burada yakalanır.
- `SchoolYearSerializer` — tarih sırası ve ad tekliği.
- `ImportRequestSerializer` — dosya ile pano metni BİRBİRİNİ DIŞLAR.

Kişisel veri yoktur.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.okul.models import ImportRun, SchoolConfig, SchoolYear
from apps.okul.serializers import (
    ClassSectionSerializer,
    ImportRequestSerializer,
    PersonnelSerializer,
    SchoolConfigSerializer,
    StudentSerializer,
)

pytestmark = pytest.mark.django_db

AYAR_URL = "/api/v1/setup/school-config/"
YIL_URL = "/api/v1/school-years/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# Alan kümeleri (ön yüz sözleşmesi)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("serializer", "alanlar"),
    [
        (
            SchoolConfigSerializer,
            {
                "school_name",
                "province",
                "district",
                "principal_name",
                "has_prep_class",
                "kademe",
                "kisa_ad",
                "demirbas_onayi",
                "demirbas_no",
                "setup_completed",
            },
        ),
        (
            StudentSerializer,
            {
                "id",
                "first_name",
                "last_name",
                "full_name",
                "student_number",
                "class_level",
                "class_section",
                "class_label",
                "status",
                "left_at",
            },
        ),
        (
            PersonnelSerializer,
            {"id", "first_name", "last_name", "full_name", "member_kind", "is_active", "left_at"},
        ),
        (
            ClassSectionSerializer,
            {
                "id",
                "school_year",
                "school_year_name",
                "class_level",
                "class_section",
                "class_label",
            },
        ),
    ],
)
def test_serializer_alan_kumesi_sabittir(serializer: Any, alanlar: set[str]) -> None:
    assert set(serializer().fields) == alanlar


def test_okul_ayarinda_kaldirilan_alanlar_yok_sayilir(client: APIClient) -> None:
    """Eski ön yüzün gönderebileceği KS alanları 400 üretmez, hiçbir yere de yazılmaz."""
    yanit = client.put(
        AYAR_URL,
        {
            "school_name": "Örnek Okul",
            "has_prep_class": True,
            "school_type": "ANADOLU_LISESI",
            "bell_schedule": [],
            "default_separation_mode": "ROOM",
        },
        format="json",
    )

    assert yanit.status_code == 200
    assert set(yanit.json()) == set(SchoolConfigSerializer().fields)
    ayar = SchoolConfig.load()
    assert (ayar.school_name, ayar.has_prep_class) == ("Örnek Okul", True)


# ---------------------------------------------------------------------------
# Ders yılı
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bitis", ["2026-09-01", "2026-06-30"])
def test_ders_yili_bitisi_baslangictan_sonra_olmalidir(client: APIClient, bitis: str) -> None:
    """Aynı gün de reddedilir — sıfır günlük ders yılına dönem kurulamaz."""
    yanit = client.post(
        YIL_URL, {"name": "2026-2027", "start_date": "2026-09-01", "end_date": bitis}, format="json"
    )

    assert yanit.status_code == 400
    assert "başlangıçtan sonra" in str(yanit.json()["fields"]["end_date"])
    assert not SchoolYear.objects.exists()


def test_ders_yili_adi_tekildir_ve_yeni_yil_pasif_acilir(client: APIClient) -> None:
    """Çakışma 500 (IntegrityError) DEĞİL 400'dür. Aktiflik yalnız `activate/` ucundan
    değişir — gövdeyle gönderilen `is_active` yok sayılır (tek-aktif kuralı serviste)."""
    govde = {
        "name": "2026-2027",
        "start_date": "2026-09-01",
        "end_date": "2027-06-30",
        "is_active": True,
    }

    ilk = client.post(YIL_URL, govde, format="json")
    assert ilk.status_code == 201 and ilk.json()["is_active"] is False

    tekrar = client.post(YIL_URL, govde, format="json")
    assert tekrar.status_code == 400
    assert "name" in tekrar.json()["fields"]
    assert SchoolYear.objects.count() == 1


# ---------------------------------------------------------------------------
# İçe aktarma girdisi: dosya YA DA metin
# ---------------------------------------------------------------------------


def _dosya() -> SimpleUploadedFile:
    return SimpleUploadedFile("liste.xlsx", b"icerik", content_type="application/octet-stream")


@pytest.mark.parametrize(
    "govde",
    [
        {},
        {"text": "   \n "},  # yalnız boşluk = metin yok
    ],
)
def test_ice_aktarma_girdisi_bos_olamaz(govde: dict[str, Any]) -> None:
    serializer = ImportRequestSerializer(data=govde)

    assert not serializer.is_valid()
    assert "tam olarak biri" in str(serializer.errors)


def test_ice_aktarma_girdisi_dosya_ve_metni_birlikte_kabul_etmez(client: APIClient) -> None:
    """İkisi birden gelirse hangisinin işleneceği belirsizdir — sessiz tercih yerine ret.

    Ret ayrıştırmadan ÖNCEDİR: geçmişe FAILED/PREVIEWED izi de düşmez.
    """
    yanit = client.post(
        "/api/v1/imports/students/preview/",
        {"file": _dosya(), "text": "Sınıf\tOkul No\tAdı Soyadı\n9/A\t101\tDENEME ÖĞRENCİ"},
        format="multipart",
    )

    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"
    assert "tam olarak biri" in str(yanit.json()["fields"]["non_field_errors"])
    assert not ImportRun.objects.exists()


def test_ice_aktarma_metni_bosluklari_kirpilmadan_tasinir() -> None:
    """Pano metninde baştaki sekme BOŞ HÜCREDİR; kırpılırsa sütunlar bir sola kayar."""
    metin = "\tOkul No\tAdı Soyadı\n"

    serializer = ImportRequestSerializer(data={"text": metin})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["text"] == metin
