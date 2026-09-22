"""Kör indeks eşleşmesi ve şifreli kipte selector'lar (F1 kod kapısı; tasarım §6.3, T14).

Kod kapısının iki maddesi burada kanıtlanır:

- **Kör indeks eşleşmesi:** aynı okul no farklı biçimde yazılınca ('0123',
  ' 1 23 ') aynı öğrenciye iner; farklı veri anahtarıyla (DEK) üretilen indeks
  eşleşmez (başka kurulumun indeksi bu kurulumda kimseyi bulmaz). Parola
  değişimi indeksi bozmaz (anahtar DEK'ten türer, parola sarmalı değişir).
- **Şifreli kipte ad selector'ları:** ad araması ve kullanıcıya gösterilen
  bütün sıralamalar Python'dadır ve Türk alfabesine uyar (DB filtresi şifreli
  sütunda çalışmaz, BINARY sıra 'Ç/İ/Ş'yi 'Z'den sonraya atar).

Bütün ad ve numaralar uydurmadır (KVKK).
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.models import Personnel, Student, StudentStatus, student_number_blind_index
from apps.okul.services import app_password
from conftest import TEST_DEK, TEST_PAROLA
from shared import crypto

pytestmark = pytest.mark.django_db

BASKA_DEK = bytes(range(100, 132))


def _ogrenci(**alanlar: Any) -> Student:
    varsayilan: dict[str, Any] = {
        "first_name": "DENEME",
        "last_name": "ÖĞRENCİ",
        "student_number": "123",
        "class_level": 9,
        "class_section": "A",
    }
    varsayilan.update(alanlar)
    ogrenci: Student = Student.objects.create(**varsayilan)
    return ogrenci


# ---------------------------------------------------------------------------
# Kör indeks eşleşmesi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("yazim", ["123", "0123", " 1 23 ", "00123", "\t123\n"])
def test_ayni_numara_farkli_yazimla_eslesir(yazim: str) -> None:
    ogrenci = _ogrenci(student_number="123")

    bulunan = selectors.find_student_by_number(yazim)

    assert bulunan is not None and bulunan.pk == ogrenci.pk


def test_farkli_numara_eslesmez_ve_bos_numara_aranmaz() -> None:
    _ogrenci(student_number="123")

    assert selectors.find_student_by_number("1234") is None
    assert selectors.find_student_by_number("12") is None
    assert selectors.find_student_by_number("") is None


def test_ayrilmis_ogrenci_aktif_aramada_bulunmaz_ama_ayrilmis_aramada_bulunur() -> None:
    ogrenci = _ogrenci(student_number="555")
    Student.objects.filter(pk=ogrenci.pk).update(status=StudentStatus.LEFT)

    assert selectors.find_student_by_number("555") is None
    ayrilmis = selectors.find_left_student_by_number("0555")
    assert ayrilmis is not None and ayrilmis.pk == ogrenci.pk


def test_farkli_dek_ile_uretilen_indeks_eslesmez() -> None:
    """Başka bir kurulumun (farklı DEK) indeksi bu kurulumda kimseyi bulmaz."""
    ogrenci = _ogrenci(student_number="123")
    bu_kurulum = student_number_blind_index("123")

    crypto.load_key(BASKA_DEK)
    try:
        baska_kurulum = student_number_blind_index("123")
        assert baska_kurulum != bu_kurulum
        assert selectors.find_student_by_number("123") is None
        assert not Student.objects.filter(student_number_index=baska_kurulum).exists()
    finally:
        crypto.load_key(TEST_DEK)

    bulunan = selectors.find_student_by_number("123")
    assert bulunan is not None and bulunan.pk == ogrenci.pk


def test_parola_degisimi_indeksi_bozmaz() -> None:
    """Anahtar DEK'ten türer; parola değişimi yalnız sarmalı yeniler (§6.3)."""
    ogrenci = _ogrenci(student_number="321")

    app_password.change_password(current_password=TEST_PAROLA, new_password="Yeni-Parola-99")

    bulunan = selectors.find_student_by_number("321")
    assert bulunan is not None and bulunan.pk == ogrenci.pk


def test_okul_no_aramasi_kor_indeksle_tam_eslesmedir() -> None:
    """Liste araması: rakam metni okul no'dur ve TAM eşleşir ('10' yazan '101'i bulmaz)."""
    hedef = _ogrenci(student_number="101", first_name="ALİ")
    _ogrenci(student_number="1010", first_name="VELİ")

    assert [s.pk for s in selectors.student_list(search="101")] == [hedef.pk]
    assert [s.pk for s in selectors.student_list(search="0101")] == [hedef.pk]
    assert selectors.student_list(search="10") == []


# ---------------------------------------------------------------------------
# Şifreli kipte ad selector'ları
# ---------------------------------------------------------------------------


def test_ad_aramasi_python_da_turkce_katlamali() -> None:
    isil = _ogrenci(student_number="1", first_name="IŞIL", last_name="ÇAĞLAR")
    _ogrenci(student_number="2", first_name="EMRE", last_name="KAYA")

    # DB filtresi şifreli sütunda hiçbir şey bulamaz — arama bu yüzden Python'dadır.
    assert not Student.objects.filter(first_name="IŞIL").exists()
    assert [s.pk for s in selectors.student_list(search="isil")] == [isil.pk]
    assert [s.pk for s in selectors.student_list(search="çağlar")] == [isil.pk]
    assert [s.pk for s in selectors.student_list(search="CAGLAR")] == [isil.pk]


def test_ogrenci_sirasi_sinif_sube_tr_ve_okul_no_dogal() -> None:
    """Sınıf → şube (Türk alfabesi) → okul no (doğal: 9 < 10 < 100) → sınıfsız sonda."""
    _ogrenci(student_number="100", class_level=10, class_section="A", first_name="C")
    _ogrenci(student_number="9", class_level=10, class_section="A", first_name="A")
    _ogrenci(student_number="10", class_level=10, class_section="A", first_name="B")
    _ogrenci(student_number="1", class_level=10, class_section="Ç", first_name="E")
    _ogrenci(student_number="2", class_level=10, class_section="C", first_name="D")
    _ogrenci(student_number="3", class_level=10, class_section="İ", first_name="G")
    _ogrenci(student_number="4", class_level=10, class_section="I", first_name="F")
    _ogrenci(student_number="5", class_level=9, class_section="Z", first_name="0")
    _ogrenci(student_number="6", class_level=None, class_section="", first_name="SINIFSIZ")

    sira = [s.first_name for s in selectors.students_sorted()]

    assert sira == ["0", "A", "B", "C", "D", "E", "F", "G", "SINIFSIZ"]


def test_personel_ad_sirasi_turk_alfabesiyle() -> None:
    for ad in ("DENİZ", "ÇAĞLA", "CEM", "İLKAY", "IŞIK", "ZEHRA", "ŞULE", "SELİN"):
        Personnel.objects.create(first_name=ad, last_name="ÖRNEK")

    sira = [p.first_name for p in selectors.personnel_sorted()]

    assert sira == ["CEM", "ÇAĞLA", "DENİZ", "IŞIK", "İLKAY", "SELİN", "ŞULE", "ZEHRA"]


def test_api_ogrenci_listesi_sirali_doner() -> None:
    """Uç da aynı Python sırasını kullanır (DB'nin BINARY sırası 'Ç'yi sona atardı)."""
    _ogrenci(student_number="1", class_level=10, class_section="Ç", first_name="İKİNCİ")
    _ogrenci(student_number="2", class_level=10, class_section="Z", first_name="ÜÇÜNCÜ")
    _ogrenci(student_number="3", class_level=10, class_section="C", first_name="BİRİNCİ")

    veri = APIClient().get("/api/v1/students/").json()
    satirlar = veri["results"] if isinstance(veri, dict) else veri

    assert [s["first_name"] for s in satirlar] == ["BİRİNCİ", "İKİNCİ", "ÜÇÜNCÜ"]


def test_api_personel_aramasi_yalniz_adda_ve_sirali() -> None:
    Personnel.objects.create(first_name="ÇAĞLA", last_name="ÖRNEK")
    Personnel.objects.create(first_name="CANAN", last_name="ÖRNEK")
    Personnel.objects.create(first_name="DENEME", last_name="KİŞİ")

    veri = APIClient().get("/api/v1/personnel/", {"search": "ornek"}).json()
    satirlar = veri["results"] if isinstance(veri, dict) else veri

    assert [p["first_name"] for p in satirlar] == ["CANAN", "ÇAĞLA"]
