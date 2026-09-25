"""İlişik, yıl akışı ve F7 evrak uçları — yalnız yönetici kipi, alan listeleri, PDF'ler.

Görevli kipinde bu dosyadaki her uç 403 `kip_yetkisiz` döner (izin listesinde
değildirler — §4.4 "ilişik", "kayıp dosyaları", "raporlar" kapalı; genel dolaşma
`apps/okul/tests/test_kip_koruma.py`). Uçlar kayıt yazmaz. Bütün kişi verileri
uydurmadır.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import unquote

import pytest
from rest_framework.test import APIClient

from apps.kutuphane import serializers_ilisik
from apps.kutuphane.services import deliveries, loss_damage
from apps.kutuphane.tests.dolasim_ortak import odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, nushalar, ogretmen, sube, teslim_et
from apps.kutuphane.views_ilisik import YEAR_FLOWS_FIELDS
from apps.okul.kip import KIP
from apps.okul.models import SchoolLevel

pytestmark = pytest.mark.django_db

KOK = "/api/v1/library/"
UCLAR: tuple[tuple[str, str], ...] = (
    ("get", "clearance/"),
    ("get", "clearance/pdf/"),
    ("get", "clearance/sections/"),
    ("post", "clearance/certificates/"),
    ("post", "year-end/slips/"),
    ("get", "year-flows/"),
    ("get", "loss-damage-cases/1/pdf/"),
    ("get", "deliveries/pdf/"),
    ("post", "deliveries/take-back-report/"),
)
AD_ALANLARI = ("Gizliad", "Gizlisoyad")


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def lise() -> None:
    kademe_yaz(SchoolLevel.ORTAOGRETIM)


def _pdf(yanit: Any) -> bytes:
    return b"".join(yanit.streaming_content)


def _pdf_yaniti_dogru(yanit: Any, ad_parcasi: str) -> None:
    assert yanit.status_code == 200, getattr(yanit, "content", b"")[:300]
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Cache-Control"] == "no-store"
    baslik = unquote(yanit["Content-Disposition"])
    assert ad_parcasi in baslik, baslik
    for ad in AD_ALANLARI:
        assert ad not in baslik
    assert _pdf(yanit).startswith(b"%PDF")


# ============================================================ kip kapısı


def test_gorevli_kipinde_her_uc_403(client: APIClient) -> None:
    KIP.gorevliye_gec()
    kesilmeyen = []
    for yontem, yol in UCLAR:
        yanit = getattr(client, yontem)(f"{KOK}{yol}", {}, format="json")
        if yanit.status_code != 403 or yanit.json()["code"] != "kip_yetkisiz":
            kesilmeyen.append(f"{yontem} {yol} → {yanit.status_code}")
    assert kesilmeyen == []


def test_hicbiri_gorevli_izin_listesinde_degil() -> None:
    from apps.okul.kip_izinleri import IZIN_LISTESI

    adlar = {kural.uc for kural in IZIN_LISTESI}
    assert not {a for a in adlar if a.startswith(("library-clearance", "library-year"))}
    assert not adlar & {
        "library-loss-damage-case-pdf",
        "library-delivery-pdf",
        "library-delivery-take-back-report",
    }


def test_gorunum_de_yonetici_kipini_ister() -> None:
    """Savunma derinliği: ara katman olmadan da görünüm 403 verir."""
    from rest_framework.test import APIRequestFactory

    from apps.kutuphane.views_ilisik import ClearanceListView

    KIP.gorevliye_gec()
    istek = APIRequestFactory().get("/x/")
    yanit = ClearanceListView.as_view()(istek)
    assert yanit.status_code == 403


# ============================================================ alan listeleri


def test_alan_listeleri_anlik_goruntuyle_sabit() -> None:
    assert tuple(serializers_ilisik.ClearanceRowSerializer().fields) == (
        serializers_ilisik.CLEARANCE_ROW_FIELDS
    )
    assert serializers_ilisik.CLEARANCE_ROW_FIELDS == (
        "person_type",
        "person_id",
        "full_name",
        "person_label",
        "student_number",
        "group",
        "is_graduating",
        "status_text",
        "left_at",
        "in_leave_pool",
        "is_clear",
        "open_loan_count",
        "overdue_loan_count",
        "open_delivery_count",
        "open_case_count",
        "loans",
        "deliveries",
        "cases",
    )
    assert serializers_ilisik.CLEARANCE_LOAN_FIELDS == (
        "id",
        "barcode",
        "barcode_display",
        "work_title",
        "loaned_at",
        "due_date",
        "overdue_days",
    )
    assert tuple(serializers_ilisik.SectionDeliveryRowSerializer().fields) == (
        serializers_ilisik.SECTION_ROW_FIELDS
    )
    for alanlar in (
        serializers_ilisik.CLEARANCE_ROW_FIELDS,
        serializers_ilisik.CLEARANCE_LOAN_FIELDS,
        serializers_ilisik.CLEARANCE_DELIVERY_FIELDS,
        serializers_ilisik.CLEARANCE_CASE_FIELDS,
        serializers_ilisik.SECTION_ROW_FIELDS,
    ):
        # Profil yasağı: konu, sınıflama ya da bölüm alanı yok.
        assert not {a for a in alanlar if "subject" in a or "classification" in a}
        assert "call_number" not in alanlar


# ============================================================ ilişik listesi


def test_ilisik_listesi_ucu_sira_suzgec_ve_sayfalama(client: APIClient) -> None:
    dokuz = uye(ogrenci(first_name="Deneme", last_name="Dokuz", class_level=9))
    son = uye(ogrenci(first_name="Deneme", last_name="Sonsınıf", class_level=12))
    odunc_ver(dokuz)
    odunc_ver(son)
    hoca = ogretmen(first_name="Deneme", last_name="Teslimli")
    teslim_et(nushalar(2), personnel=hoca)

    govde = client.get(f"{KOK}clearance/").json()

    assert govde["count"] == 3
    assert [s["full_name"] for s in govde["results"]] == [
        "Deneme Sonsınıf",
        "Deneme Dokuz",
        "Deneme Teslimli",
    ]
    ilk = govde["results"][0]
    assert ilk["group"] == "graduating" and ilk["status_text"] == "Son sınıf"
    assert ilk["open_loan_count"] == 1 and ilk["loans"][0]["work_title"] == "Deneme Eseri"
    assert govde["results"][2]["open_delivery_count"] == 2
    assert govde["results"][2]["person_label"] == "Öğretmen"
    sayfa = client.get(f"{KOK}clearance/", {"limit": 1, "offset": 1}).json()
    assert [s["full_name"] for s in sayfa["results"]] == ["Deneme Dokuz"]
    son_siniflar = client.get(f"{KOK}clearance/", {"group": "graduating"}).json()
    assert son_siniflar["count"] == 1
    temizler = client.get(f"{KOK}clearance/", {"state": "clear", "person_type": "student"}).json()
    assert temizler["count"] == 0
    assert client.get(f"{KOK}clearance/", {"group": "x"}).status_code == 400
    assert client.get(f"{KOK}clearance/", {"class_level": "x"}).status_code == 400


def test_ilisik_listesi_pdf_ve_sube_uclari(client: APIClient) -> None:
    odunc_ver(uye(ogrenci(first_name="Gizliad", last_name="Gizlisoyad", class_level=12)))
    teslim_et(nushalar(2), section=sube(12, "A"))

    _pdf_yaniti_dogru(client.get(f"{KOK}clearance/pdf/"), "İlişik-Listesi")
    _pdf_yaniti_dogru(
        client.get(f"{KOK}clearance/pdf/", {"group": "priority"}), "Son-Sınıflar-ve-Ayrılanlar"
    )
    subeler = client.get(f"{KOK}clearance/sections/").json()
    assert [(s["section_label"], s["delivery_count"], s["is_graduating"]) for s in subeler] == [
        ("12/A", 2, True)
    ]
    assert client.get(f"{KOK}clearance/sections/", {"graduating": "1"}).json() == subeler


# ============================================================ E5 belgesi


def test_ilisik_belgesi_ucu(client: APIClient) -> None:
    temiz = ogrenci(first_name="Gizliad", last_name="Gizlisoyad")
    odunclu = ogrenci()
    odunc_ver(uye(odunclu))

    yanit = client.post(f"{KOK}clearance/certificates/", {"student_ids": [temiz.pk]}, format="json")
    _pdf_yaniti_dogru(yanit, "Kütüphaneden-İlişiği-Yoktur-Belgesi")

    red = client.post(
        f"{KOK}clearance/certificates/", {"student_ids": [temiz.pk, odunclu.pk]}, format="json"
    )
    assert red.status_code == 400
    assert "1 kişinin" in red.json()["message"]
    bos = client.post(f"{KOK}clearance/certificates/", {}, format="json")
    assert bos.status_code == 400
    yok = client.post(f"{KOK}clearance/certificates/", {"personnel_ids": [99999]}, format="json")
    assert yok.status_code == 400 and "bulunamadı" in yok.json()["message"]


def test_bedel_adimlarinin_ilisik_ve_e5_uzerindeki_etkisi(client: APIClient) -> None:
    """25.09.2026 kararı: "Bedel belirlendi" kişiyi listede tutar ve E5'i reddettirir;
    "Bedel teslim alındı" kişiyi listeden çıkarır ve E5 basılır (dosya okul için açık)."""
    kisi = ogrenci(class_level=12)
    uyelik = uye(kisi)
    dosya = loss_damage.report_lost(copy=odunc_ver(uyelik).copy, membership=uyelik)
    govde = {"student_ids": [kisi.pk]}

    loss_damage.resolve_case(dosya, resolution="PRICE_DETERMINED", market_price=Decimal("90"))
    assert client.get(f"{KOK}clearance/", {"group": "graduating"}).json()["count"] == 1
    red = client.post(f"{KOK}clearance/certificates/", govde, format="json")
    assert red.status_code == 400 and "1 kişinin" in red.json()["message"]

    loss_damage.resolve_case(dosya, resolution="PRICE_RECEIVED")
    assert client.get(f"{KOK}clearance/", {"group": "graduating"}).json()["count"] == 0
    yanit = client.post(f"{KOK}clearance/certificates/", govde, format="json")
    _pdf_yaniti_dogru(yanit, "Kütüphaneden-İlişiği-Yoktur-Belgesi")
    dosya.refresh_from_db()
    assert dosya.is_open


# ============================================================ yıl sonu pusulası ve özet


def test_yil_sonu_pusulasi_ucu(client: APIClient) -> None:
    son = uye(ogrenci(class_level=12))
    odunc_ver(son)
    diger = uye(ogrenci(class_level=9))
    odunc_ver(diger)

    hepsi = client.post(f"{KOK}year-end/slips/", {}, format="json")
    _pdf_yaniti_dogru(hepsi, "Yıl-Sonu")
    secili = client.post(
        f"{KOK}year-end/slips/",
        {"student_ids": [son.student_id], "return_by": "2027-06-11"},
        format="json",
    )
    assert secili.status_code == 200
    bos = client.post(f"{KOK}year-end/slips/", {"class_level": 10}, format="json")
    assert bos.status_code == 400 and "iade edilecek ödünç yok" in bos.json()["message"]


def test_yil_akislari_ucu_kisisiz(client: APIClient) -> None:
    odunc_ver(uye(ogrenci(first_name="Gizliad", last_name="Gizlisoyad", class_level=12)))

    yanit = client.get(f"{KOK}year-flows/")

    assert yanit.status_code == 200
    govde = yanit.json()
    assert tuple(govde) == YEAR_FLOWS_FIELDS
    assert govde["year_end"]["counts"]["graduating_persons"] == 1
    assert set(govde["year_end"]["steps"]) == {"dates", "collection", "graduating", "clearance"}
    assert set(govde["year_start"]["steps"]) == {
        "school_year",
        "import",
        "leave_pool",
        "closed_days",
    }
    for ad in AD_ALANLARI:
        assert ad not in yanit.content.decode("utf-8")


# ============================================================ E6 ve E15


def test_tutanak_ucu(client: APIClient) -> None:
    uyelik = uye(ogrenci(first_name="Gizliad", last_name="Gizlisoyad"))
    dosya = loss_damage.report_lost(copy=odunc_ver(uyelik).copy, membership=uyelik)

    _pdf_yaniti_dogru(client.get(f"{KOK}loss-damage-cases/{dosya.pk}/pdf/"), "Kayıp-Hasar-Tutanağı")
    assert client.get(f"{KOK}loss-damage-cases/99999/pdf/").status_code == 404


def test_teslim_listesi_ve_geri_alma_dokumu_uclari(client: APIClient) -> None:
    hoca = ogretmen(first_name="Gizliad", last_name="Gizlisoyad")
    kitaplar = nushalar(2)
    sonuc = teslim_et(kitaplar, personnel=hoca)
    sube_sonuc = teslim_et(nushalar(1), section=sube(9, "A"))

    _pdf_yaniti_dogru(
        client.get(f"{KOK}deliveries/pdf/", {"document_no": sonuc.document_no}), "Teslim-Listesi"
    )
    _pdf_yaniti_dogru(
        client.get(f"{KOK}deliveries/pdf/", {"section": sube_sonuc.section.pk}),  # type: ignore[union-attr]
        "9-A",
    )
    _pdf_yaniti_dogru(client.get(f"{KOK}deliveries/pdf/", {"personnel": hoca.pk}), "Teslim-Listesi")
    assert client.get(f"{KOK}deliveries/pdf/").status_code == 400
    assert client.get(f"{KOK}deliveries/pdf/", {"section": 99999}).status_code == 400

    kapanan = deliveries.take_back(kitaplar[0])
    assert kapanan is not None
    _pdf_yaniti_dogru(
        client.post(
            f"{KOK}deliveries/take-back-report/", {"delivery_ids": [kapanan.pk]}, format="json"
        ),
        "Geri-Alma-Dökümü",
    )
    _pdf_yaniti_dogru(
        client.post(
            f"{KOK}deliveries/take-back-report/",
            {"document_no": sonuc.document_no},
            format="json",
        ),
        "Geri-Alma-Dökümü",
    )
    assert client.post(f"{KOK}deliveries/take-back-report/", {}, format="json").status_code == 400
