"""Sayım uçları (F9) — gövde sözleşmesi, kip, parola ve alan listeleri.

Servis kuralları `test_sayim.py`'dedir. Burada: uçtan uca API akışı, hata gövdeleri
(`{code, message, fields}`), görevli kipinde YALNIZ okutmanın açık olması ve yanıtının
daralması (madde 24, 25.09.2026 kullanıcı kararı), masanın kişisiz durumu (madde 26),
hizmet arasında teslim reddi (madde 27), parola kurulmadan şifreli ada yazan isteğin
409'u, yanıtlarda ödünç alanın kimliğinin bulunmaması ve serializer alan listelerinin
anlık görüntüsü (T13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.urls import URLPattern, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane.models import CopyStatus
from apps.kutuphane.serializers_sayim import (
    STAFF_SCAN_FIELDS,
    StockTakeDetailSerializer,
    StockTakeItemSerializer,
    StockTakeListSerializer,
)
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.sayim_ortak import HARCAMA_YETKILISI, KURUL
from apps.kutuphane.tests.teslim_ortak import tazele_nusha
from apps.kutuphane.urls import urlpatterns
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import IZIN_LISTESI

pytestmark = pytest.mark.django_db

SAYIM = "/api/v1/library/stocktakes/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


def _yol(ad: str, *args: int) -> str:
    return reverse(ad, args=list(args))


def _sayim_uclari() -> list[str]:
    return [
        str(desen.name)
        for desen in urlpatterns
        if isinstance(desen, URLPattern) and str(desen.name).startswith("library-stocktake")
    ]


# ============================================================ uçtan uca akış


def test_sayim_api_uctan_uca(istemci: APIClient) -> None:
    bulunan = odunc_nushasi(title="Bulunan Kitap")
    noksan = odunc_nushasi(title="Bulunamayan Kitap")
    uyelik = uye(ogrenci(first_name="Denemeapisayim", last_name="Oduncalan"))
    oduncte = odunc_ver(uyelik)

    olustur = istemci.post(
        SAYIM, {**KURUL, "service_pause": True, "loan_basis": "BY_RECORD"}, format="json"
    )
    assert olustur.status_code == 201, olustur.json()
    govde = olustur.json()
    pk = govde["id"]
    assert govde["status"] == "DRAFT" and govde["committee_chair"] == KURUL["committee_chair"]
    assert [s["key"] for s in govde["options"]] == ["tmy_32_3", "service_pause", "return"]
    assert {s["value"] for s in govde["basis_choices"]["loan_basis"]} == {"COLLECT", "BY_RECORD"}

    duzelt = istemci.patch(_yol("library-stocktake-detail", pk), {"notes": "Aralık"}, format="json")
    assert duzelt.status_code == 200 and duzelt.json()["notes"] == "Aralık"

    basla = istemci.post(_yol("library-stocktake-start", pk), format="json")
    assert basla.status_code == 200, basla.json()
    assert basla.json()["status"] == "IN_PROGRESS" and basla.json()["locks_active"] is True

    durum = istemci.get(_yol("library-stocktake-state")).json()
    assert durum["live"]["id"] == pk and durum["service_pause_active"] is True
    assert durum["tmy_stop_active"] is False and durum["returns_open"] is True

    okut = istemci.post(
        _yol("library-stocktake-scan", pk),
        {"barcodes": [bulunan.barcode, bulunan.barcode, "9786050000009"]},
        format="json",
    )
    assert okut.status_code == 200, okut.json()
    assert [s["code"] for s in okut.json()["results"]] == ["bulundu", "zaten_okutuldu", "gecersiz"]
    assert okut.json()["results"][2]["item"] is None
    assert okut.json()["summary"]["results"]["FOUND"] == 1

    tek = istemci.post(_yol("library-stocktake-scan", pk), {"barcode": "4455"}, format="json")
    assert tek.json()["results"][0]["code"] == "fazla"
    fazla_pk = tek.json()["results"][0]["item"]["id"]
    haric = istemci.patch(
        _yol("library-stocktake-item-detail", pk, fazla_pk),
        {"excluded": True, "note": "Yanlış okutma değil; kişisel kitap"},
        format="json",
    )
    assert haric.status_code == 200 and haric.json()["surplus_excluded"] is True

    ilerleme = istemci.get(_yol("library-stocktake-progress", pk)).json()
    assert ilerleme["physical_expected"] == 2 and ilerleme["physical_found"] == 1

    tamam = istemci.post(_yol("library-stocktake-complete", pk), format="json")
    assert tamam.json()["second_round"] is True  # TMY 32/6
    tamam = istemci.post(_yol("library-stocktake-complete", pk), format="json")
    assert tamam.json()["second_round"] is False
    assert tamam.json()["stocktake"]["status"] == "COMPLETED"

    kalemler = istemci.get(_yol("library-stocktake-items", pk), {"result": "MISSING"}).json()
    assert kalemler["count"] == 1 and kalemler["results"][0]["copy"] == noksan.pk
    assert kalemler["results"][0]["barcode_display"].count("-") == 1

    onay = istemci.post(
        _yol("library-stocktake-approve", pk),
        {"approved_by_name": HARCAMA_YETKILISI, "approved_on": timezone.localdate().isoformat()},
        format="json",
    )
    assert onay.status_code == 200, onay.json()
    assert (onay.json()["written_off"], onay.json()["surplus_excluded"]) == (1, 1)
    assert onay.json()["stocktake"]["status"] == "APPROVED"
    assert tazele_nusha(noksan).status == CopyStatus.WITHDRAWN_MISSING
    assert tazele_nusha(oduncte.copy).status == CopyStatus.ON_LOAN

    sayilar = istemci.get(_yol("library-stocktake-tmy-34-1", pk)).json()
    assert sayilar["next_year_carryover"] == 2  # bulunan + ödünçteki (kayda göre)
    assert "Taşınır Sayım ve Döküm Cetveli değildir" in sayilar["note"]

    # Ödünç alanın kimliği sayım yanıtlarının hiçbirinde yok (E10 dayanağı: 10/1-g, 32/8).
    butun = str(
        [
            istemci.get(_yol("library-stocktake-items", pk), {"limit": 200}).json(),
            istemci.get(_yol("library-stocktake-detail", pk)).json(),
            sayilar,
        ]
    )
    for yasak in ("Denemeapisayim", "Oduncalan", uyelik.card_no):
        assert yasak not in butun


def test_hizmet_arasinda_masa_odunc_reddi_kodludur(istemci: APIClient) -> None:
    uyelik = uye()
    kitap = odunc_nushasi()
    pk = istemci.post(SAYIM, {**KURUL, "service_pause": True}, format="json").json()["id"]
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    ret = istemci.post(
        "/api/v1/library/checkout/",
        {"barcode": kitap.barcode, "card_no": uyelik.card_no},
        format="json",
    )
    assert ret.status_code == 400
    assert ret.json()["code"] == "sayim_hizmet_arasi"
    assert "hizmet arası" in ret.json()["message"]


def test_durdurma_reddi_400_ve_turkce_ileti(istemci: APIClient) -> None:
    bugun = timezone.localdate().isoformat()
    pk = istemci.post(
        SAYIM,
        {
            **KURUL,
            "tmy_stop": True,
            "tmy_stop_requested_on": bugun,
            "tmy_stop_by_name": HARCAMA_YETKILISI,
            "tmy_stop_on": bugun,
        },
        format="json",
    ).json()["id"]
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    ret = istemci.post(
        "/api/v1/library/acquisitions/",
        {"method": "PURCHASE", "date": bugun},
        format="json",
    )
    assert ret.status_code == 400
    assert "TMY 32/3 durdurması süresince edinim" in ret.json()["message"]


def test_hata_govdeleri_sozlesme_bicimindedir(istemci: APIClient) -> None:
    pk = istemci.post(SAYIM, {**KURUL, "committee_members": ""}, format="json").json()["id"]
    basla = istemci.post(_yol("library-stocktake-start", pk), format="json")
    assert basla.status_code == 400
    assert basla.json()["code"] == "validation_error"
    assert "32/2" in basla.json()["message"]
    assert "committee_members" in basla.json()["fields"]
    ikinci = istemci.post(SAYIM, {}, format="json")
    assert ikinci.status_code == 400 and "Onaylanmamış bir sayım var" in ikinci.json()["message"]
    fazla = istemci.post(
        _yol("library-stocktake-scan", pk), {"barcodes": ["1"] * 201}, format="json"
    )
    assert fazla.status_code == 400
    iki = istemci.post(
        _yol("library-stocktake-scan", pk), {"barcode": "1", "barcodes": ["2"]}, format="json"
    )
    assert iki.status_code == 400
    assert istemci.get(_yol("library-stocktake-detail", 999999)).status_code == 404


# ============================================================ kip ve parola


def test_sayim_uclarindan_yalniz_okutma_izin_listesindedir() -> None:
    """Madde 24 (25.09.2026 kullanıcı kararı): izin listesine YALNIZ okutma POST girer."""
    uclar = set(_sayim_uclari())
    # 13 sayım ucu + 2 sayım tutanağı ucu (E10 — `views_sayim_belgeleri.py`).
    assert len(uclar) == 15
    assert {(k.uc, k.yontem) for k in IZIN_LISTESI if k.uc in uclar} == {
        ("library-stocktake-scan", "POST")
    }


def test_gorevli_kipinde_okutma_200_obur_sayim_uclari_403(istemci: APIClient) -> None:
    """Madde 24: görevli kipinde okutma açık ve yanıt daralır; öbür sayım uçları 403."""
    kitap = odunc_nushasi(title="Görevli Okutması")
    pk = istemci.post(SAYIM, KURUL, format="json").json()["id"]
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    fazla = istemci.post(_yol("library-stocktake-scan", pk), {"barcode": "4455"}, format="json")
    kalem_pk = fazla.json()["results"][0]["item"]["id"]
    KIP.gorevliye_gec()

    okut = istemci.post(
        _yol("library-stocktake-scan", pk),
        {"barcodes": [kitap.barcode, "9786050000009"]},
        format="json",
    )
    assert okut.status_code == 200, okut.json()
    assert set(okut.json()) == {"results"}  # özet YOK
    bulundu, isbn = okut.json()["results"]
    assert list(bulundu) == list(STAFF_SCAN_FIELDS)
    assert (bulundu["code"], bulundu["barcode"], bulundu["work_title"]) == (
        "bulundu",
        kitap.barcode,
        "Görevli Okutması",
    )
    assert bulundu["barcode_display"].count("-") == 1
    assert isbn["code"] == "gecersiz" and isbn["work_title"] == ""

    for yol, yontem in (
        (SAYIM, "get"),
        (SAYIM, "post"),
        (_yol("library-stocktake-state"), "get"),
        (_yol("library-stocktake-detail", pk), "get"),
        (_yol("library-stocktake-detail", pk), "patch"),
        (_yol("library-stocktake-start", pk), "post"),
        (_yol("library-stocktake-items", pk), "get"),
        (_yol("library-stocktake-item-detail", pk, kalem_pk), "patch"),
        (_yol("library-stocktake-item-detail", pk, kalem_pk), "delete"),
        (_yol("library-stocktake-surplus", pk), "post"),
        (_yol("library-stocktake-progress", pk), "get"),
        (_yol("library-stocktake-complete", pk), "post"),
        (_yol("library-stocktake-approve", pk), "post"),
        (_yol("library-stocktake-cancel", pk), "post"),
        (_yol("library-stocktake-tmy-34-1", pk), "get"),
        (_yol("library-stocktake-documents", pk), "get"),
    ):
        yanit = getattr(istemci, yontem)(yol, {}, format="json")
        assert yanit.status_code == 403, (yontem, yol)
        assert yanit.json()["code"] == "kip_yetkisiz"


def test_gorevli_okutma_yaniti_kisisiz_ve_kayda_gore_durumsuz(istemci: APIClient) -> None:
    """Görevli yanıtında kalem, özet, kayda göre durum ve ödünç alanın kimliği yoktur."""
    uyelik = uye(ogrenci(first_name="Denemegorevlisayim", last_name="Oduncalan"))
    oduncte = odunc_ver(uyelik)
    pk = istemci.post(SAYIM, KURUL, format="json").json()["id"]
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    KIP.gorevliye_gec()
    yanit = istemci.post(
        _yol("library-stocktake-scan", pk), {"barcode": oduncte.copy.barcode}, format="json"
    ).json()
    metin = str(yanit)
    for yasak in ("Denemegorevlisayim", "Oduncalan", uyelik.card_no, "expected_status", "item"):
        assert yasak not in metin, yasak
    assert yanit["results"][0]["code"] == "bulundu"


def test_masa_durumu_hizmet_arasini_ve_sureni_sayimi_kisisiz_verir(istemci: APIClient) -> None:
    """Madde 26: görevli kipinde masa hizmet arasını açılışta öğrenir; madde 24: süren
    sayımın okutması görevli ekranından açılır. Yanıt kişisiz ve iki kipte aynıdır."""
    durum_yolu = _yol("library-desk-state")
    assert istemci.get(durum_yolu).json() == {"service_pause": False, "stocktake_scan": None}
    pk = istemci.post(SAYIM, {**KURUL, "service_pause": True}, format="json").json()["id"]
    # Taslakta okutma yok, hizmet arası başlamadı.
    assert istemci.get(durum_yolu).json() == {"service_pause": False, "stocktake_scan": None}
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    KIP.gorevliye_gec()
    yanit = istemci.get(durum_yolu)
    assert yanit.status_code == 200
    assert yanit.json() == {"service_pause": True, "stocktake_scan": {"id": pk, "round": 1}}
    assert istemci.get(durum_yolu + "?x=1").status_code == 403  # sorgu dizesi yok


def test_hizmet_arasinda_teslim_reddi_kodludur(istemci: APIClient) -> None:
    """Madde 27: toplu teslim ve teslim ön denetimi ödünç reddiyle aynı kod ve iletiyle."""
    from apps.kutuphane.services.circulation import SERVICE_PAUSE_MESSAGE
    from apps.kutuphane.tests.teslim_ortak import sube

    kitap = odunc_nushasi(title="Teslim Edilmeyecek")
    sinif = sube(9, "E")
    pk = istemci.post(SAYIM, {**KURUL, "service_pause": True}, format="json").json()["id"]
    istemci.post(_yol("library-stocktake-start", pk), format="json")
    denetim = istemci.post(
        "/api/v1/library/deliveries/check/", {"barcode": kitap.barcode}, format="json"
    ).json()
    assert (denetim["result"], denetim["message"]) == ("rejected", SERVICE_PAUSE_MESSAGE)
    ret = istemci.post(
        "/api/v1/library/deliveries/",
        {"section_id": sinif.pk, "barcodes": [kitap.barcode]},
        format="json",
    )
    assert ret.status_code == 400
    assert ret.json()["code"] == "sayim_hizmet_arasi"
    assert ret.json()["message"] == SERVICE_PAUSE_MESSAGE
    assert tazele_nusha(kitap).status == CopyStatus.AVAILABLE


def test_parola_kurulmadan_kurul_adi_yazan_istek_409(istemci: APIClient, parolasiz: Path) -> None:
    yanit = istemci.post(SAYIM, KURUL, format="json")
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "parola_gerekli"


# ============================================================ alan listeleri (T13)


ALANLAR: dict[Any, list[str]] = {
    StockTakeListSerializer: [
        "id",
        "status",
        "status_display",
        "fiscal_year",
        "round",
        "tmy_stop",
        "service_pause",
        "created_at",
        "started_at",
        "completed_at",
        "approved_on",
        "cancelled_at",
    ],
    StockTakeDetailSerializer: [
        "id",
        "status",
        "status_display",
        "fiscal_year",
        "round",
        "committee_chair",
        "committee_property_officer",
        "committee_members",
        "tmy_stop",
        "tmy_stop_requested_on",
        "tmy_stop_by_name",
        "tmy_stop_on",
        "service_pause",
        "service_pause_decision",
        "loan_basis",
        "loan_basis_display",
        "section_delivery_basis",
        "section_delivery_basis_display",
        "teacher_delivery_basis",
        "teacher_delivery_basis_display",
        "repair_basis",
        "repair_basis_display",
        "notes",
        "created_at",
        "started_at",
        "round2_started_at",
        "completed_at",
        "approved_by_name",
        "approved_on",
        "approved_at",
        "surplus_acquisition",
        "cancelled_at",
        "cancel_reason",
        "locks_active",
        "options",
        "basis_lines",
        "basis_choices",
        "summary",
    ],
    StockTakeItemSerializer: [
        "id",
        "copy",
        "barcode",
        "barcode_display",
        "work",
        "work_title",
        "work_authors",
        "call_number",
        "section",
        "section_name",
        "class_library",
        "copy_status",
        "copy_status_display",
        "expected_status",
        "expected_status_display",
        "delivery_kind",
        "basis",
        "basis_display",
        "basis_fallback",
        "result",
        "result_display",
        "found_in_round",
        "found_via",
        "found_via_display",
        "scanned_at",
        "status_at_completion",
        "damage_write_off",
        "case",
        "case_type",
        "case_resolution_display",
        "outcome",
        "outcome_display",
        "write_off_path",
        "write_off_path_display",
        "outcome_note",
        "is_surplus",
        "surplus_barcode",
        "surplus_barcode_display",
        "surplus_copy",
        "surplus_work",
        "surplus_work_title",
        "surplus_note",
        "surplus_excluded",
        "created_copy",
        "created_copy_barcode",
        "surplus_bound_barcode",
    ],
}


@pytest.mark.parametrize("serializer", list(ALANLAR))
def test_serializer_alan_listesi_anlik_goruntusu(serializer: Any) -> None:
    assert list(serializer.Meta.fields) == ALANLAR[serializer]


def test_gorevli_okutma_ve_masa_durumu_alan_listesi_anlik_goruntusu() -> None:
    """Madde 24, 26: görevli yanıtlarının alanları bilinçli değişir (T13)."""
    from apps.kutuphane.serializers_masa import DESK_STATE_FIELDS, DESK_STOCKTAKE_FIELDS

    assert STAFF_SCAN_FIELDS == ("code", "message", "barcode", "barcode_display", "work_title")
    assert DESK_STATE_FIELDS == ("service_pause", "stocktake_scan")
    assert DESK_STOCKTAKE_FIELDS == ("id", "round")


def test_onarim_secenekleri_kararin_sozcukleriyle(istemci: APIClient) -> None:
    """K2: onarımdaki nüsha için "Sayımdan önce geri alınır" · "Kayda göre alınır — onarımda";
    K3: sınıf kitaplığında "Kayda göre alınır" yok."""
    govde = istemci.post(SAYIM, {**KURUL, "repair_basis": "COLLECT"}, format="json").json()
    assert govde["basis_choices"]["repair_basis"] == [
        {"value": "COLLECT", "label": "Sayımdan önce geri alınır"},
        {"value": "BY_RECORD", "label": "Kayda göre alınır — onarımda"},
    ]
    assert [s["value"] for s in govde["basis_choices"]["section_delivery_basis"]] == [
        "IN_PLACE",
        "COLLECT",
    ]
    assert (govde["repair_basis"], govde["repair_basis_display"]) == (
        "COLLECT",
        "Sayımdan önce geri alınır",
    )
    assert [s["category"] for s in govde["basis_lines"]] == [
        "loan",
        "section_delivery",
        "teacher_delivery",
        "repair",
    ]
    ret = istemci.patch(
        _yol("library-stocktake-detail", govde["id"]),
        {"section_delivery_basis": "BY_RECORD"},
        format="json",
    )
    assert ret.status_code == 400 and "section_delivery_basis" in ret.json()["fields"]


def test_kalem_ve_liste_kisi_alani_tasimaz() -> None:
    """Kişi ya da kimlik taşıyan alan adı sayım kaleminde ve listede yoktur."""
    yasak = ("member", "membership", "student", "personnel", "person", "responsible", "loan")
    for serializer in (StockTakeItemSerializer, StockTakeListSerializer):
        for alan in serializer.Meta.fields:
            assert not any(parca in alan for parca in yasak), alan
