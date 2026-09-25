"""Teslim, kayıp/hasar ve onarım uçları (F7) — gövde sözleşmesi, kip ve alan listeleri.

Servis kuralları `test_teslim.py`, `test_kayip_hasar.py` ve
`test_teslim_tek_acik_kayit.py`'dedir; burada uçların sözleşmesi sınanır: durum
kodları, hata gövdeleri (`{code, message, fields}`), görevli kipinde yalnız geri
alma okutmasının açık olması ve serializer alan listelerinin anlık görüntüsü
(T13 — tipler elle yazılır, alanlar testle sabittir).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.kutuphane.models import CaseResolution, CopyStatus, DeliveryStatus
from apps.kutuphane.serializers_teslim import (
    ADMIN_TAKE_BACK_FIELDS,
    CASE_FIELDS,
    DELIVERY_FIELDS,
    REPAIR_FIELDS,
    STAFF_TAKE_BACK_FIELDS,
    TAKE_BACK_DELIVERY_FIELDS,
)
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, uye
from apps.kutuphane.tests.teslim_ortak import (
    kademe_yaz,
    nushalar,
    ogretmen,
    sube,
    tazele_nusha,
    teslim_et,
)
from apps.okul.kip import KIP
from apps.okul.models import SchoolLevel

pytestmark = pytest.mark.django_db

TESLIM = "/api/v1/library/deliveries/"
KONTROL = "/api/v1/library/deliveries/check/"
GERI_AL = "/api/v1/library/deliveries/take-back/"
DOSYA = "/api/v1/library/loss-damage-cases/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


# ============================================================ alan listeleri (T13)


def test_alan_listeleri_anlik_goruntusu() -> None:
    assert STAFF_TAKE_BACK_FIELDS == ("result", "kind", "message", "copy")
    assert ADMIN_TAKE_BACK_FIELDS == (*STAFF_TAKE_BACK_FIELDS, "delivery")
    assert TAKE_BACK_DELIVERY_FIELDS == (
        "id",
        "recipient_kind",
        "recipient_kind_display",
        "recipient_label",
        "delivered_on",
        "expected_return",
        "document_no",
        "returned_at",
    )
    assert DELIVERY_FIELDS == (
        "id",
        "copy",
        "barcode",
        "barcode_display",
        "work_title",
        "call_number",
        "recipient_kind",
        "recipient_kind_display",
        "section",
        "personnel",
        "recipient_label",
        "delivered_on",
        "expected_return",
        "expected_return_passed",
        "document_no",
        "status",
        "status_display",
        "returned_at",
        "lost_at",
    )
    assert CASE_FIELDS == (
        "id",
        "copy",
        "barcode",
        "barcode_display",
        "work_title",
        "copy_status",
        "copy_status_display",
        "case_type",
        "case_type_display",
        "membership",
        "loan",
        "delivery",
        "responsible_name",
        "responsible_class_label",
        "responsible_note",
        "reported_on",
        "market_price",
        "price_determined_at",
        "price_received_at",
        "resolution",
        "resolution_display",
        "is_open",
        "is_person_open_work",
        "resolved_at",
        "write_off_proposed_at",
        "allowed_resolutions",
        "price_options_available",
        "created_at",
    )
    assert REPAIR_FIELDS == (
        "id",
        "copy",
        "barcode",
        "barcode_display",
        "work_title",
        "case",
        "sent_on",
        "returned_on",
    )


def test_profil_yasagi_konu_ve_siniflama_alani_yok() -> None:
    """CLAUDE.md §2-5: teslim ve dosya satırları konu, sınıflama ya da bölüm taşımaz."""
    for alanlar in (DELIVERY_FIELDS, CASE_FIELDS, REPAIR_FIELDS, TAKE_BACK_DELIVERY_FIELDS):
        for yasak in ("subject", "classification", "section_name", "dewey"):
            assert not any(yasak in alan for alan in alanlar), (yasak, alanlar)


# ============================================================ teslim


class TestTeslimUclari:
    def test_toplu_teslim_201_ve_liste(self, istemci: APIClient) -> None:
        kitaplar = nushalar(3)
        sinif = sube(10, "B")

        yanit = istemci.post(
            TESLIM,
            {"section_id": sinif.pk, "barcodes": [k.barcode for k in kitaplar]},
            format="json",
        )

        assert yanit.status_code == 201, yanit.json()
        govde = yanit.json()
        assert govde["count"] == 3 and govde["recipient_label"] == "10/B"
        assert govde["recipient_kind"] == "SECTION"
        assert tuple(govde["deliveries"][0]) == DELIVERY_FIELDS
        liste = istemci.get(TESLIM, {"document_no": govde["document_no"]}).json()
        assert liste["count"] == 3
        assert {s["status_display"] for s in liste["results"]} == {"Teslimde"}

    def test_teslim_edilemeyen_kitap_varsa_400_ve_gerekce_listesi(self, istemci: APIClient) -> None:
        oduncte = odunc_ver(uye()).copy
        yanit = istemci.post(
            TESLIM,
            {"personnel_id": ogretmen().pk, "barcodes": [odunc_nushasi().barcode, oduncte.barcode]},
            format="json",
        )
        assert yanit.status_code == 400
        assert any("Ödünçte" in g for g in yanit.json()["fields"]["barcodes"])

    def test_alan_secilmezse_400(self, istemci: APIClient) -> None:
        yanit = istemci.post(TESLIM, {"barcodes": ["2026000001"]}, format="json")
        assert yanit.status_code == 400

    def test_teslim_listesine_okutma_on_denetimi_yazmaz(self, istemci: APIClient) -> None:
        kitap = odunc_nushasi()
        yanit = istemci.post(KONTROL, {"barcode": kitap.barcode}, format="json").json()
        assert yanit["result"] == "deliverable"
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE

        oduncte = odunc_ver(uye()).copy
        ret = istemci.post(KONTROL, {"barcode": oduncte.barcode}, format="json").json()
        assert ret["result"] == "rejected" and "teslim edilemez" in ret["message"]

    def test_geri_alma_yonetici_kipinde_teslim_ayrintisini_verir(self, istemci: APIClient) -> None:
        teslim = teslim_et(nushalar(1)).deliveries[0]
        yanit = istemci.post(GERI_AL, {"barcode": teslim.copy.barcode}, format="json").json()
        assert yanit["result"] == "returned"
        assert tuple(yanit["delivery"]) == TAKE_BACK_DELIVERY_FIELDS
        assert yanit["delivery"]["recipient_label"] == "9/A"

    def test_geri_alma_okuyucu_kuyrugu(self, istemci: APIClient) -> None:
        teslimler = teslim_et(nushalar(2)).deliveries
        yanit = istemci.post(
            GERI_AL, {"barcodes": [t.copy.barcode for t in teslimler]}, format="json"
        ).json()
        assert [s["result"] for s in yanit["results"]] == ["returned", "returned"]

    def test_gorevli_kipinde_yalniz_geri_alma_acik_yanit_daralir(self, istemci: APIClient) -> None:
        hoca = ogretmen(last_name="Gizlisoyad")
        teslim = teslim_et(nushalar(1), personnel=hoca).deliveries[0]
        kitap = odunc_nushasi()
        KIP.gorevliye_gec()

        verme = istemci.post(
            TESLIM, {"section_id": sube().pk, "barcodes": [kitap.barcode]}, format="json"
        )
        liste = istemci.get(TESLIM)
        kontrol = istemci.post(KONTROL, {"barcode": kitap.barcode}, format="json")
        geri = istemci.post(GERI_AL, {"barcode": teslim.copy.barcode}, format="json")

        assert [verme.status_code, liste.status_code, kontrol.status_code] == [403, 403, 403]
        assert verme.json()["code"] == "kip_yetkisiz"
        assert geri.status_code == 200
        assert tuple(geri.json()) == STAFF_TAKE_BACK_FIELDS
        assert "Gizlisoyad" not in geri.content.decode()
        assert teslim.copy.barcode in geri.content.decode()


# ============================================================ kayıp / hasar / onarım


class TestDosyaUclari:
    def test_kayip_bildirimi_okutmayla_201_ve_alan_listesi(self, istemci: APIClient) -> None:
        loan = odunc_ver(uye())
        yanit = istemci.post(
            DOSYA, {"case_type": "LOST", "barcode": loan.copy.barcode}, format="json"
        )
        assert yanit.status_code == 201, yanit.json()
        govde = yanit.json()
        assert tuple(govde) == CASE_FIELDS
        assert govde["copy_status"] == CopyStatus.LOST
        assert govde["loan"] == loan.pk and govde["is_open"] is True
        assert govde["responsible_name"] == "Deneme Öğrenci"

    def test_ilkokulda_bedel_cozumu_400_ve_secenek_listesinde_yok(self, istemci: APIClient) -> None:
        kademe_yaz(SchoolLevel.ILKOKUL)
        dosya = istemci.post(
            DOSYA, {"case_type": "LOST", "copy_id": odunc_nushasi().pk}, format="json"
        ).json()
        secenekler = {s["value"] for s in dosya["allowed_resolutions"]}
        assert dosya["price_options_available"] is False
        assert CaseResolution.PRICE_DETERMINED not in secenekler
        assert CaseResolution.PRICE_RECEIVED not in secenekler

        for govde in (
            {"resolution": "PRICE_DETERMINED", "market_price": "150.00"},
            {"resolution": "PRICE_RECEIVED"},
        ):
            yanit = istemci.post(f"{DOSYA}{dosya['id']}/resolve/", govde, format="json")
            assert yanit.status_code == 400
            assert "yalnız ortaöğretim" in yanit.json()["message"]

    def test_ortaogretimde_bedel_iki_adimda_kaydedilir(self, istemci: APIClient) -> None:
        kademe_yaz(SchoolLevel.ORTAOGRETIM)
        dosya = istemci.post(
            DOSYA, {"case_type": "LOST", "copy_id": odunc_nushasi().pk}, format="json"
        ).json()
        assert dosya["is_person_open_work"] is True
        yanit = istemci.post(
            f"{DOSYA}{dosya['id']}/resolve/",
            {"resolution": "PRICE_DETERMINED", "market_price": "150.00"},
            format="json",
        )
        assert yanit.status_code == 200, yanit.json()
        belirlendi = yanit.json()
        assert belirlendi["market_price"] == "150.00"
        assert belirlendi["resolution_display"] == "Bedel belirlendi"
        assert belirlendi["price_determined_at"] is not None
        assert belirlendi["price_received_at"] is None
        assert belirlendi["is_open"] is True and belirlendi["is_person_open_work"] is True
        assert "PRICE_RECEIVED" in {s["value"] for s in belirlendi["allowed_resolutions"]}

        yanit = istemci.post(
            f"{DOSYA}{dosya['id']}/resolve/", {"resolution": "PRICE_RECEIVED"}, format="json"
        )
        assert yanit.status_code == 200, yanit.json()
        alindi = yanit.json()
        assert alindi["resolution_display"] == "Bedel teslim alındı"
        assert alindi["price_received_at"] is not None
        # Okulun açık işi: dosya açık, kişinin açık işi değil; yalnız iki kapanış yolu.
        assert alindi["is_open"] is True and alindi["is_person_open_work"] is False
        assert [s["label"] for s in alindi["allowed_resolutions"]] == [
            "Bedelle aynısı alındı",
            "Bedelle başka eser alındı",
        ]
        acik = istemci.get(DOSYA, {"open": "1"}).json()
        assert [d["id"] for d in acik["results"]] == [dosya["id"]]

    def test_hasar_dosyasi_not_duzeltme_ve_liste_suzgeci(self, istemci: APIClient) -> None:
        kitap = odunc_nushasi()
        dosya = istemci.post(
            DOSYA,
            {"case_type": "DAMAGED", "copy_id": kitap.pk, "send_to_repair": True},
            format="json",
        ).json()
        assert dosya["copy_status"] == CopyStatus.IN_REPAIR

        duzeltme = istemci.patch(
            f"{DOSYA}{dosya['id']}/", {"responsible_note": "Kapak yırtık."}, format="json"
        )
        assert duzeltme.status_code == 200
        assert duzeltme.json()["responsible_note"] == "Kapak yırtık."
        assert istemci.get(DOSYA, {"open": "1", "case_type": "DAMAGED"}).json()["count"] == 1
        assert istemci.get(DOSYA, {"case_type": "LOST"}).json()["count"] == 0

    @pytest.mark.parametrize(
        ("kademe", "beklenen"),
        [(SchoolLevel.ORTAOGRETIM, True), (SchoolLevel.ORTAOKUL, False), ("", False)],
    )
    def test_liste_yaniti_kademe_kapisini_bos_listede_de_tasir(
        self, istemci: APIClient, kademe: str, beklenen: bool
    ) -> None:
        """Ekran "Çözüm" süzgecindeki bedel yollarını bu alana göre kurar (Md. 19)."""
        kademe_yaz(kademe)
        govde = istemci.get(DOSYA).json()
        assert govde["count"] == 0
        assert govde["price_options_available"] is beklenen
        assert set(govde) == {"count", "next", "previous", "results", "price_options_available"}

    def test_oneriyle_kapanan_kayip_dosyasi_ucla_bulundu_olur(self, istemci: APIClient) -> None:
        dosya = istemci.post(
            DOSYA, {"case_type": "LOST", "copy_id": odunc_nushasi().pk}, format="json"
        ).json()
        kapanan = istemci.post(
            f"{DOSYA}{dosya['id']}/resolve/", {"resolution": "WRITE_OFF_PROPOSED"}, format="json"
        ).json()
        assert kapanan["is_open"] is False
        assert [s["value"] for s in kapanan["allowed_resolutions"]] == ["FOUND_RETURNED"]

        yanit = istemci.post(
            f"{DOSYA}{dosya['id']}/resolve/", {"resolution": "FOUND_RETURNED"}, format="json"
        )
        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["copy_status"] == CopyStatus.AVAILABLE
        assert yanit.json()["write_off_proposed_at"] is None
        assert yanit.json()["allowed_resolutions"] == []

    def test_nusha_yoksa_ve_gecersiz_cozumde_400(self, istemci: APIClient) -> None:
        assert (
            istemci.post(DOSYA, {"case_type": "LOST", "copy_id": 999999}, format="json").status_code
            == 400
        )
        dosya = istemci.post(
            DOSYA, {"case_type": "LOST", "copy_id": odunc_nushasi().pk}, format="json"
        ).json()
        yanit = istemci.post(
            f"{DOSYA}{dosya['id']}/resolve/", {"resolution": "PENDING"}, format="json"
        )
        assert yanit.status_code == 400

    def test_onarim_uclari(self, istemci: APIClient) -> None:
        kitap = odunc_nushasi()
        gonder = istemci.post(reverse("library-copy-send-to-repair", args=[kitap.pk]))
        assert gonder.status_code == 201
        assert tuple(gonder.json()["repair"]) == REPAIR_FIELDS
        assert tazele_nusha(kitap).status == CopyStatus.IN_REPAIR

        don = istemci.post(reverse("library-copy-return-from-repair", args=[kitap.pk]))
        assert don.status_code == 200
        assert don.json()["repair"]["returned_on"] is not None
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE
        assert (
            istemci.post(reverse("library-copy-return-from-repair", args=[kitap.pk])).status_code
            == 400
        )

    def test_gorevli_kipinde_dosya_ve_onarim_uclari_kapali(self, istemci: APIClient) -> None:
        kitap = odunc_nushasi()
        KIP.gorevliye_gec()
        yanitlar: list[Any] = [
            istemci.get(DOSYA),
            istemci.post(DOSYA, {"case_type": "LOST", "copy_id": kitap.pk}, format="json"),
            istemci.post(reverse("library-copy-send-to-repair", args=[kitap.pk])),
        ]
        assert {y.status_code for y in yanitlar} == {403}
        assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE


def test_teslim_kaydinin_durumlari_sozlukle_ayni_etiketleri_tasir() -> None:
    """Sözlük: "teslim", "geri alma" — "ödünç", "emanet", "zimmet" değil."""
    etiketler = [str(etiket) for _, etiket in DeliveryStatus.choices]
    assert etiketler == ["Teslimde", "Geri alındı", "Kayba dönüştü"]
    for etiket in etiketler:
        for yasak in ("ödünç", "emanet", "zimmet"):
            assert yasak not in etiket.casefold()
