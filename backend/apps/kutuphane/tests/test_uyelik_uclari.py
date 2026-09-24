"""Üyelik yönetim uçları — yönetici kipi, kişi yazan uç kapısı, yanıt alan listeleri (T13).

Uçlar görevli kipi izin listesinde DEĞİLDİR (§4.4; dolaşan koruma testi
`apps/okul/tests/test_kip_koruma.py` bunu bütün uçlar için sabitler, burada
ayrıca açıkça sınanır). Kişi yazan uçlar parola kurulmadan 409 döner
(`apps/okul/tests/test_kisi_yazan_uclar.py`). Dolaşım retlerinin gövdesi
`{code, message, fields}` sözleşmesindedir ve `code` kararlıdır (masa ekranı
iletisini ona göre seçer). Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane import card_numbers
from apps.kutuphane.models import (
    CardlessReason,
    Loan,
    Membership,
    OverrideReason,
    TerminationReason,
)
from apps.kutuphane.serializers_uyelik import MemberLoanSerializer, MembershipSerializer
from apps.kutuphane.services import circulation
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.services.yonetici_kipi import KipYetkisiz
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_ver,
    ogrenci,
    personel,
    uye,
)
from apps.okul.kip import KIP
from apps.okul.services import app_password
from shared.crypto import EncryptedTextField, encrypted_fields_of
from shared.exceptions import kd_exception_handler

pytestmark = pytest.mark.django_db

UYELIKLER = "/api/v1/library/memberships/"
ISTEKLER = "/api/v1/library/membership-requests/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


# ============================================================ alan listeleri (T13)


def test_uyelik_yanitinin_alan_listesi_sabittir() -> None:
    assert MembershipSerializer.Meta.fields == [
        "id",
        "student",
        "personnel",
        "member_type",
        "member_type_display",
        "full_name",
        "class_label",
        "student_number",
        "card_no",
        "card_printed_at",
        "status",
        "status_display",
        "requested_at",
        "started_at",
        "terminated_at",
        "termination_reason",
        "termination_reason_display",
        "open_loan_count",
        "overdue_loan_count",
        "loan_limit",
        "remaining_quota",
    ]
    assert set(MembershipSerializer.Meta.read_only_fields) == set(MembershipSerializer.Meta.fields)


def test_odunc_kaydi_yanitinin_alan_listesi_sabittir() -> None:
    """Profil yasağı: konu, sınıflama, bölüm YOK; istisna açıklaması (serbest metin) YOK."""
    assert MemberLoanSerializer.Meta.fields == [
        "id",
        "barcode",
        "barcode_display",
        "work_title",
        "loaned_at",
        "due_date",
        "returned_at",
        "status",
        "status_display",
        "overdue_days",
        "has_override",
        "override_reason_display",
        "cardless",
        "cardless_reason_display",
    ]


def test_sifreli_alanlar_kart_no_ve_gerekcelerdir() -> None:
    """§6.3: kart no, istisna gerekçesi/açıklaması ve kartsız gerekçesi şifreli."""
    assert {f.name for f in encrypted_fields_of(Membership)} == {"card_no"}
    assert {f.name for f in encrypted_fields_of(Loan)} == {
        "override_reason",
        "override_note",
        "cardless_reason",
    }
    assert all(isinstance(f, EncryptedTextField) for f in encrypted_fields_of(Loan))
    etiketler = app_password.protected_field_labels()
    assert {"kart no", "istisna gerekçesi", "istisna açıklaması", "kartsız ödünç gerekçesi"} <= set(
        etiketler
    )
    assert "kart no kör indeksi" not in etiketler


def test_kapali_listeler_ve_kullanici_etiketleri() -> None:
    """Masa ve yönetim ekranlarının sözleşmesi: kodlar sabit, etiketler Türkçe."""
    assert OverrideReason.values == ["COURSE_NEED", "EXCUSED_DELAY", "RETURN_ARRANGED", "OTHER"]
    assert CardlessReason.values == [
        "CARD_NOT_WITH_MEMBER",
        "CARD_LOST",
        "CARD_NOT_PRINTED",
        "CARD_UNREADABLE",
    ]
    assert TerminationReason.values == ["LEFT_SCHOOL", "MEMBER_REQUEST", "RECORD_ERROR", "MERGED"]


# ============================================================ hata gövdeleri


def test_dolasim_reddi_govdesi_kararli_kod_tasir() -> None:
    yanit = kd_exception_handler(
        DolasimReddi("Ödünç sınırı dolu (en çok 3 kitap).", code="sinir_dolu"), {}
    )
    assert yanit is not None and yanit.status_code == 400
    assert yanit.data == {
        "code": "sinir_dolu",
        "message": "Ödünç sınırı dolu (en çok 3 kitap).",
        "fields": {},
    }


def test_kip_yetkisiz_govdesi_ara_katmanla_aynidir() -> None:
    yanit = kd_exception_handler(KipYetkisiz(), {})
    assert yanit is not None and yanit.status_code == 403
    assert yanit.data == {
        "code": "kip_yetkisiz",
        "message": "Bu işlem görevli kipinde yapılamaz. Yönetici kipine geçin.",
        "fields": {},
    }


def test_servis_reddi_kodu_ornege_ozgudur() -> None:
    """Örnek özniteliği sınıfı kirletmez: bir retin kodu ötekine sızmaz."""
    DolasimReddi("x", code="sinir_dolu")
    assert DolasimReddi("y", code="gecikme_engeli").code == "gecikme_engeli"
    assert DolasimReddi.default_code == "dolasim_reddi"


# ============================================================ liste ve açma


def test_ogrenciye_ve_personele_uyelik_acilir(client: APIClient) -> None:
    kisi = ogrenci(first_name="Deneme", last_name="Uç")
    yanit = client.post(UYELIKLER, {"student_id": kisi.pk}, format="json")
    assert yanit.status_code == 201, yanit.json()
    govde = yanit.json()
    assert card_numbers.is_valid_card_no(govde["card_no"])
    assert govde["member_type"] == "STUDENT" and govde["member_type_display"] == "öğrenci"
    assert govde["full_name"] == "Deneme Uç"
    assert govde["class_label"] == "9/A"
    assert govde["remaining_quota"] == 3

    yanit = client.post(UYELIKLER, {"personnel_id": personel().pk}, format="json")
    assert yanit.status_code == 201
    assert yanit.json()["loan_limit"] == 5


@pytest.mark.parametrize(
    "govde",
    [{}, {"student_id": 1, "personnel_id": 1}, {"student_id": 999_999}, {"personnel_id": 999_999}],
)
def test_gecersiz_acma_govdesi_400(client: APIClient, govde: dict[str, Any]) -> None:
    yanit = client.post(UYELIKLER, govde, format="json")
    assert yanit.status_code == 400
    assert yanit.json()["code"] == "validation_error"


def test_zaten_uye_olana_ikinci_uyelik_400_ve_ad_yankilanmaz(client: APIClient) -> None:
    kisi = ogrenci(first_name="Yankilanmayanad")
    uye(kisi)
    yanit = client.post(UYELIKLER, {"student_id": kisi.pk}, format="json")
    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Bu kişinin aktif üyeliği var."
    assert "Yankilanmayanad" not in yanit.content.decode()


def test_liste_sayfali_sirali_ve_kisi_bazinda_sayilarla(client: APIClient) -> None:
    a = uye(ogrenci(student_number="2"))
    b = uye(ogrenci(student_number="10"))
    odunc_ver(b)
    gecikmeli_yap(odunc_ver(b))
    uye(personel())

    yanit = client.get(UYELIKLER, {"limit": 2})

    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["count"] == 3
    assert [s["id"] for s in govde["results"]] == [a.pk, b.pk]
    assert govde["results"][1]["open_loan_count"] == 2
    assert govde["results"][1]["overdue_loan_count"] == 1
    assert govde["results"][1]["remaining_quota"] == 1
    assert govde["next"]


def test_liste_suzgeci_gecersiz_degerde_400(client: APIClient) -> None:
    assert client.get(UYELIKLER, {"status": "ASKIDA"}).status_code == 400
    assert client.get(UYELIKLER, {"member_type": "VELI"}).status_code == 400
    assert client.get(UYELIKLER, {"class_level": "on"}).status_code == 400


def test_arama_kart_no_ile(client: APIClient) -> None:
    hedef = uye()
    uye()
    yanit = client.get(UYELIKLER, {"search": hedef.card_no})
    assert [s["id"] for s in yanit.json()["results"]] == [hedef.pk]


# ============================================================ ayrıntı, silme, yenile, sonlandır


def test_ayrinti_ve_yanlis_uyeligin_silinmesi(client: APIClient) -> None:
    uyelik = uye()
    assert client.get(f"{UYELIKLER}{uyelik.pk}/").json()["id"] == uyelik.pk
    assert client.delete(f"{UYELIKLER}{uyelik.pk}/").status_code == 204
    assert client.get(f"{UYELIKLER}{uyelik.pk}/").status_code == 404


def test_odunc_kaydi_olan_uyelik_silinmez(client: APIClient) -> None:
    uyelik = uye()
    odunc_ver(uyelik)
    yanit = client.delete(f"{UYELIKLER}{uyelik.pk}/")
    assert yanit.status_code == 400
    assert Membership.objects.filter(pk=uyelik.pk).exists()


def test_karti_yenile(client: APIClient) -> None:
    uyelik = uye()
    eski = uyelik.card_no
    yanit = client.post(f"{UYELIKLER}{uyelik.pk}/renew-card/")
    assert yanit.status_code == 200
    assert yanit.json()["card_no"] != eski
    assert yanit.json()["card_printed_at"] is None


@pytest.mark.parametrize(
    ("govde", "ileti"),
    [
        ({}, "Sonlandırma nedeni zorunludur."),
        ({"reason": "LEFT_SCHOOL"}, "Sonlandırma nedenini listeden seçin."),
        ({"reason": "keyfi"}, "Sonlandırma nedenini listeden seçin."),
    ],
)
def test_sonlandirma_nedeni_zorunlu_ve_kapali_liste(
    client: APIClient, govde: dict[str, str], ileti: str
) -> None:
    """D12 — serializer katmanı (servis ve DB kısıtı ayrıca sınanır)."""
    uyelik = uye()
    yanit = client.post(f"{UYELIKLER}{uyelik.pk}/terminate/", govde, format="json")
    assert yanit.status_code == 400
    assert yanit.json()["fields"]["reason"] == [ileti]
    uyelik.refresh_from_db()
    assert uyelik.is_active


def test_sonlandirma(client: APIClient) -> None:
    uyelik = uye()
    yanit = client.post(
        f"{UYELIKLER}{uyelik.pk}/terminate/", {"reason": "MEMBER_REQUEST"}, format="json"
    )
    assert yanit.status_code == 200
    assert yanit.json()["status"] == "TERMINATED"
    assert yanit.json()["termination_reason_display"] == "Üyenin isteği"
    assert yanit.json()["remaining_quota"] == 0


def test_odunc_kaydi_sayfali_en_yeni_once(client: APIClient) -> None:
    uyelik = uye()
    ilk = odunc_ver(uyelik)
    circulation.return_copy(copy=ilk.copy)
    ikinci = odunc_ver(uyelik, cardless_reason="CARD_LOST")

    yanit = client.get(f"{UYELIKLER}{uyelik.pk}/loans/")

    assert yanit.status_code == 200
    satirlar = yanit.json()["results"]
    assert [s["id"] for s in satirlar] == [ikinci.pk, ilk.pk]
    assert satirlar[0]["cardless"] is True
    assert satirlar[0]["cardless_reason_display"] == "Kart kayıp — yenilenecek"
    assert satirlar[1]["status"] == "RETURNED"
    assert "-" in satirlar[0]["barcode_display"]


# ============================================================ istek listesi


def test_istek_listesi_ve_toplu_uyelik(client: APIClient) -> None:
    a = ogrenci(class_section="Ş", student_number="5")
    b = ogrenci(class_section="Ş", student_number="6")
    ogrenci(class_section="B")

    liste = client.get(ISTEKLER, {"class_level": "9", "class_section": "ş"})

    assert liste.status_code == 200
    assert [s["student_id"] for s in liste.json()] == [a.pk, b.pk]
    assert liste.json()[0]["is_member"] is False
    assert liste.json()[0]["class_label"] == "9/Ş"

    acma = client.post(ISTEKLER, {"student_ids": [b.pk]}, format="json")

    assert acma.status_code == 201
    assert [s["student"] for s in acma.json()] == [b.pk]
    liste = client.get(ISTEKLER, {"class_level": "9", "class_section": "Ş"})
    assert [s["is_member"] for s in liste.json()] == [False, True]

    bayat = client.post(ISTEKLER, {"student_ids": [a.pk, b.pk]}, format="json")
    assert bayat.status_code == 400
    assert Membership.objects.count() == 1


def test_istek_listesi_sube_secimi_zorunlu(client: APIClient) -> None:
    assert client.get(ISTEKLER).status_code == 400
    assert client.post(ISTEKLER, {"student_ids": []}, format="json").status_code == 400


# ============================================================ görevli kipi (§4.4)


def test_gorevli_kipinde_butun_uyelik_uclari_403(client: APIClient) -> None:
    uyelik = uye()
    KIP.gorevliye_gec()
    istekler = [
        ("get", UYELIKLER),
        ("post", UYELIKLER),
        ("get", f"{UYELIKLER}{uyelik.pk}/"),
        ("delete", f"{UYELIKLER}{uyelik.pk}/"),
        ("post", f"{UYELIKLER}{uyelik.pk}/renew-card/"),
        ("post", f"{UYELIKLER}{uyelik.pk}/terminate/"),
        ("get", f"{UYELIKLER}{uyelik.pk}/loans/"),
        ("get", ISTEKLER),
        ("post", ISTEKLER),
    ]
    for yontem, yol in istekler:
        yanit = getattr(client, yontem)(yol, {}, format="json")
        assert yanit.status_code == 403, (yontem, yol)
        assert yanit.json()["code"] == "kip_yetkisiz"
    uyelik.refresh_from_db()
    assert uyelik.is_active
