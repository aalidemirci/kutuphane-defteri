"""Ayıklama, nadir eser ve yıl sonu raporu uçları (F8) — gövde sözleşmesi, kip ve alan listeleri.

Servis kuralları `test_ayiklama.py`, `test_nadir_eser.py` ve
`test_yil_sonu_raporu.py`'dedir. Burada: uçtan uca API akışı, hata gövdeleri
(`{code, message, fields}`), görevli kipinde BÜTÜN F8 uçlarının kapalı olması,
parola kurulmadan şifreli ada yazan onayın 409'u ve serializer alan listelerinin
anlık görüntüsü (T13 — ön yüz tipleri elle yazılır).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.urls import URLPattern, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane.models import CommissionDecision, CopyStatus, WeedingBatch
from apps.kutuphane.serializers_ayiklama import (
    AnnualLibraryReviewListSerializer,
    AnnualLibraryReviewSerializer,
    RareCopySerializer,
    RareWorksItemSerializer,
    RareWorksSubmissionDetailSerializer,
    WeedingBatchDetailSerializer,
    WeedingBatchSerializer,
    WeedingCandidateSerializer,
    WeedingItemSerializer,
)
from apps.kutuphane.services import loss_damage, weeding
from apps.kutuphane.tests.ayiklama_ortak import (
    DEVRALAN_OKUL,
    HARCAMA_YETKILISI,
    TMY_KOMISYONU,
    ayiklama_karari,
    kalem_ekle,
    raftaki,
    tazele,
    teklif,
)
from apps.kutuphane.tests.teslim_ortak import etkin_yil
from apps.kutuphane.urls import urlpatterns
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db

TEKLIF = "/api/v1/library/weeding-batches/"
F8_ONEKLERI = (
    "library-weeding-",
    "library-rare-",
    "library-annual-review-",
)


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


def _yol(ad: str, *args: int) -> str:
    return reverse(ad, args=list(args))


# ============================================================ uçtan uca akış


def test_ayiklama_api_uctan_uca(istemci: APIClient) -> None:
    etkin_yil()
    yipranmis = raftaki("Yıpranmış")
    duzey = raftaki("Düzeye Uygun Değil")
    karar = ayiklama_karari()

    olustur = istemci.post(TEKLIF, {"notes": "Ağustos"}, format="json")
    assert olustur.status_code == 201, olustur.json()
    pk = olustur.json()["id"]
    assert olustur.json()["status"] == "DRAFT" and olustur.json()["items"] == []

    ekle = istemci.post(
        _yol("library-weeding-batch-items", pk),
        {"barcodes": [yipranmis.barcode], "reason": "WORN"},
        format="json",
    )
    assert ekle.status_code == 201, ekle.json()
    assert ekle.json()["added"][0]["tmy_path"] == "TMY_27"
    ekle = istemci.post(
        _yol("library-weeding-batch-items", pk),
        {"copies": [duzey.pk], "reason": "LEVEL_MISMATCH", "tmy_path": "TMY_31"},
        format="json",
    )
    assert ekle.status_code == 201
    devir_kalemi = ekle.json()["added"][0]["id"]

    assert istemci.post(_yol("library-weeding-batch-submit", pk)).status_code == 200
    karar_yaniti = istemci.post(
        _yol("library-weeding-batch-decision", pk),
        {"commission_decision": karar.pk},
        format="json",
    )
    assert karar_yaniti.json()["status"] == "DECIDED"
    # Komisyon "devredilsin" dedikten sonra okul bulunur: kurum onaydan önce yazılır.
    kurum = istemci.patch(
        _yol("library-weeding-batch-item-detail", pk, devir_kalemi),
        {"transfer_target": DEVRALAN_OKUL},
        format="json",
    )
    assert kurum.status_code == 200 and kurum.json()["transfer_target"] == DEVRALAN_OKUL
    onay = istemci.post(
        _yol("library-weeding-batch-approve", pk),
        {
            "approved_by_name": HARCAMA_YETKILISI,
            "approved_on": timezone.localdate().isoformat(),
            "tmy_commission_members": TMY_KOMISYONU,
        },
        format="json",
    )
    assert onay.status_code == 200, onay.json()
    assert onay.json()["approved_by_name"] == HARCAMA_YETKILISI
    uygula = istemci.post(_yol("library-weeding-batch-apply", pk))
    assert uygula.status_code == 200
    assert (uygula.json()["withdrawn"], uygula.json()["transferred"]) == (1, 1)
    assert tazele(yipranmis).status == CopyStatus.WITHDRAWN_WEEDED
    assert tazele(duzey).status == CopyStatus.TRANSFERRED

    liste = istemci.get(TEKLIF)
    (satir,) = liste.json()["results"]
    assert satir["counts"] == {
        "items": 2,
        "proposed": 0,
        "excluded": 0,
        "applied": 2,
        "write_off": 1,
        "transfer": 1,
    }
    # Liste satırı şifreli adları TAŞIMAZ (yalnız ayrıntıda).
    assert "approved_by_name" not in satir and "tmy_commission_members" not in satir


def test_e7_hatasi_400_ve_alan_adi(istemci: APIClient) -> None:
    batch = teklif()
    yanit = istemci.post(
        _yol("library-weeding-batch-items", batch.pk),
        {"copies": [raftaki().pk], "reason": "LEVEL_MISMATCH", "tmy_path": "TMY_28"},
        format="json",
    )
    assert yanit.status_code == 400
    assert "tmy_path" in yanit.json()["fields"]
    assert "devir yoluna" in yanit.json()["message"]


def test_engelli_nusha_400_ve_gerekce_listesi(istemci: APIClient) -> None:
    batch = teklif()
    yanit = istemci.post(
        _yol("library-weeding-batch-items", batch.pk),
        {"copies": [raftaki(is_rare_or_manuscript=True).pk], "reason": "WORN"},
        format="json",
    )
    assert yanit.status_code == 400
    assert "Md. 12/2" in yanit.json()["fields"]["barcodes"][0]


def test_kurallar_ucu_e7_tablosunu_verir(istemci: APIClient) -> None:
    govde = istemci.get(_yol("library-weeding-rules")).json()
    yollar = {s["value"]: set(s["paths"]) for s in govde["reasons"]}
    assert yollar == {
        "WORN": {"TMY_27", "TMY_28"},
        "OBSOLETE": {"TMY_28"},
        "LEVEL_MISMATCH": {"TMY_24_2", "TMY_31"},
        "CRITERIA_MISMATCH": {"TMY_28"},
    }
    assert "10_1_B" not in {o["value"] for o in govde["criteria"]}
    assert {y["value"] for y in govde["paths"] if y["is_transfer"]} == {"TMY_24_2", "TMY_31"}


def test_aday_ucu_kayip_ve_hasar_onerilerini_ayri_verir(istemci: APIClient) -> None:
    """25.09.2026 kullanıcı kararı (F8 ekleri 34): iki öneri de aday değildir, sayımda düşülür."""
    aday = raftaki("Aday")
    kayip = raftaki("Kayıp")
    dosya = loss_damage.report_lost(copy=kayip)
    loss_damage.resolve_case(dosya, resolution="WRITE_OFF_PROPOSED")
    hasarli = raftaki("Hasarlı")
    hasar = loss_damage.open_damage_case(copy=hasarli)
    loss_damage.resolve_case(hasar, resolution="WRITE_OFF_PROPOSED")

    govde = istemci.get(_yol("library-weeding-candidates")).json()
    assert [s["id"] for s in govde["results"]] == [aday.pk]
    assert "write_off_proposed" not in govde["results"][0]
    (satir,) = govde["lost_proposals"]
    assert satir["id"] == kayip.pk and "sayımda" in satir["blocker"]
    (satir,) = govde["damage_proposals"]
    assert satir["id"] == hasarli.pk and satir["status"] == "AVAILABLE"
    assert satir["blocker"] == weeding.DAMAGE_PROPOSAL_MESSAGE
    assert "sayımda kayıttan düşülür" in satir["blocker"]
    # `proposals` süzgeci kalktı: bilinmeyen parametre yok sayılır, liste aynıdır.
    yanit = istemci.get(_yol("library-weeding-candidates") + "?proposals=1").json()
    assert [s["id"] for s in yanit["results"]] == [aday.pk]


def test_nadir_eser_ve_yil_sonu_uclari(istemci: APIClient) -> None:
    etkin_yil()
    nadir = raftaki("Yazma", is_rare_or_manuscript=True)
    liste = istemci.post(
        "/api/v1/library/rare-works-submissions/",
        {"commission_decision": ayiklama_karari().pk},
        format="json",
    )
    assert liste.status_code == 201, liste.json()
    lpk = liste.json()["id"]
    assert (
        istemci.post(
            _yol("library-rare-works-submission-items", lpk), {"copies": [nadir.pk]}, format="json"
        ).status_code
        == 201
    )
    gonder = istemci.post(
        _yol("library-rare-works-submission-send", lpk),
        {"sent_on": timezone.localdate().isoformat()},
        format="json",
    )
    assert gonder.status_code == 200 and gonder.json()["status"] == "SENT"
    kopyalar = istemci.get(_yol("library-rare-copy-list")).json()["results"]
    assert [(k["id"], k["sent"]) for k in kopyalar] == [(nadir.pk, True)]

    rapor = istemci.post("/api/v1/library/annual-reviews/", {}, format="json")
    assert rapor.status_code == 201
    rpk = rapor.json()["id"]
    assert rapor.json()["stats"]["schema"] == 2
    guncel = istemci.patch(
        _yol("library-annual-review-detail", rpk),
        {"findings": "Raflar düzenlendi.", "document_no": "E-42"},
        format="json",
    )
    assert guncel.json()["findings"] == "Raflar düzenlendi."
    son = istemci.post(_yol("library-annual-review-finalize", rpk))
    assert son.json()["is_finalized"] is True
    assert "stats" not in istemci.get("/api/v1/library/annual-reviews/").json()["results"][0]


# ============================================================ kapılar


def _f8_uclari() -> list[tuple[str, str]]:
    sonuc = []
    for desen in urlpatterns:
        assert isinstance(desen, URLPattern) and desen.name
        if desen.name.startswith(F8_ONEKLERI) or desen.name in (
            "library-donation-intake-matches",
            "library-donation-intake-pdf",
            "library-donation-intake-result-pdf",
        ):
            ornek = reverse(desen.name, kwargs={ad: 1 for ad in desen.pattern.converters})
            sonuc.append((desen.name, ornek))
    return sonuc


def test_f8_uclari_eksiksiz_dolasilir() -> None:
    # 23 çekirdek ucu + 6 belge ucu (E7 listesi ve belgesi, E8, E9, E16 ve bağış
    # değerlendirme sonucu — F8 ekleri 13).
    assert len(_f8_uclari()) == 29


@pytest.mark.parametrize("yontem", ["get", "post", "patch", "delete"])
def test_gorevli_kipinde_butun_f8_uclari_403(istemci: APIClient, yontem: str) -> None:
    KIP.gorevliye_gec()
    for ad, yol in _f8_uclari():
        yanit = getattr(istemci, yontem)(yol, {}, format="json")
        assert yanit.status_code == 403, (ad, yontem, yanit.status_code)
        assert yanit.json()["code"] == "kip_yetkisiz"


def test_parola_kurulmadan_harcama_yetkilisi_adi_yazilamaz(parolasiz: Path) -> None:
    etkin_yil()
    kitap = raftaki()
    batch = WeedingBatch.objects.create(school_year=etkin_yil())
    kalem_ekle(batch, kitap)
    weeding.submit_batch(batch)
    # Kurulum bitmeden karar kaydı açılamaz (başkan adı şifreli); ham kayıt boş adla.
    karar = CommissionDecision.objects.create(
        decision_type="WEEDING", decision_date=timezone.localdate(), chair_name=""
    )
    weeding.bind_decision(batch, commission_decision=karar)

    yanit = APIClient().post(
        _yol("library-weeding-batch-approve", batch.pk),
        {"approved_by_name": HARCAMA_YETKILISI, "approved_on": timezone.localdate().isoformat()},
        format="json",
    )
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "parola_gerekli"


# ============================================================ alan listeleri (T13)


ALANLAR: dict[str, list[str]] = {
    "WeedingItemSerializer": [
        "id",
        "copy",
        "barcode",
        "barcode_display",
        "work",
        "work_title",
        "work_authors",
        "call_number",
        "copy_status",
        "copy_status_display",
        "reason",
        "reason_display",
        "criterion",
        "criterion_display",
        "tmy_path",
        "tmy_path_display",
        "is_transfer",
        "transfer_target",
        "state",
        "state_display",
        "exclusion_reason",
        "copy_is_rare",
        "destruction_decided",
    ],
    "WeedingBatchSerializer": [
        "id",
        "school_year",
        "school_year_name",
        "status",
        "status_display",
        "commission_decision",
        "decision",
        "submitted_at",
        "decided_at",
        "approved_on",
        "approved_at",
        "destruction_decided",
        "applied_at",
        "cancelled_at",
        "cancel_reason",
        "notes",
        "counts",
        "created_at",
    ],
    "WeedingCandidateSerializer": [
        "id",
        "barcode",
        "barcode_display",
        "work",
        "work_title",
        "work_authors",
        "call_number",
        "section_name",
        "status",
        "status_display",
    ],
    "RareWorksItemSerializer": [
        "id",
        "copy",
        "barcode_display",
        "work_title",
        "work_authors",
        "publisher",
        "publish_year",
        "call_number",
        "copy_status_display",
    ],
    "RareCopySerializer": [
        "id",
        "barcode_display",
        "work",
        "work_title",
        "work_authors",
        "status",
        "status_display",
        "sent",
    ],
    "AnnualLibraryReviewListSerializer": [
        "id",
        "school_year",
        "school_year_name",
        "document_date",
        "document_no",
        "findings",
        "is_finalized",
        "finalized_at",
        "created_at",
    ],
}
SINIFLAR: dict[str, Any] = {
    "WeedingItemSerializer": WeedingItemSerializer,
    "WeedingBatchSerializer": WeedingBatchSerializer,
    "WeedingCandidateSerializer": WeedingCandidateSerializer,
    "RareWorksItemSerializer": RareWorksItemSerializer,
    "RareCopySerializer": RareCopySerializer,
    "AnnualLibraryReviewListSerializer": AnnualLibraryReviewListSerializer,
}


@pytest.mark.parametrize("ad", sorted(ALANLAR))
def test_alan_listesi_anlik_goruntuyle_sabit(ad: str) -> None:
    assert list(SINIFLAR[ad]().fields) == ALANLAR[ad]
    assert all(alan.read_only for alan in SINIFLAR[ad]().fields.values())


def test_ayrinti_serializerlari_listeye_yalniz_ek_yapar() -> None:
    assert list(WeedingBatchDetailSerializer().fields) == [
        *ALANLAR["WeedingBatchSerializer"],
        "approved_by_name",
        "tmy_commission_members",
        "items",
    ]
    assert list(AnnualLibraryReviewSerializer().fields) == [
        *ALANLAR["AnnualLibraryReviewListSerializer"],
        "stats",
    ]
    assert list(RareWorksSubmissionDetailSerializer().fields)[-1] == "items"


def test_kalem_yaniti_kisisizdir(istemci: APIClient) -> None:
    """Kalem, aday ve nadir eser satırında kişi alanı yoktur (T13 + KVKK)."""
    for ad in ("WeedingItemSerializer", "WeedingCandidateSerializer", "RareWorksItemSerializer"):
        for alan in ALANLAR[ad]:
            for yasak in ("member", "student", "personnel", "responsible", "loan_"):
                assert yasak not in alan, (ad, alan)
    batch = teklif()
    kalem_ekle(batch, raftaki(), "LEVEL_MISMATCH", transfer_target=DEVRALAN_OKUL)
    govde: dict[str, Any] = istemci.get(_yol("library-weeding-batch-detail", batch.pk)).json()
    assert govde["items"][0]["transfer_target"] == DEVRALAN_OKUL


def test_geri_cekme_iptal_silme_ve_kalem_uclari(istemci: APIClient) -> None:
    """D15 uçları: kalem silme (taslakta), teklifi geri çekme, iptal, taslağı silme."""
    batch = teklif()
    birinci = kalem_ekle(batch, raftaki("Birinci"))
    ikinci = kalem_ekle(batch, raftaki("İkinci"))

    notlar = istemci.patch(_yol("library-weeding-batch-detail", batch.pk), {"notes": "Not"})
    assert notlar.status_code == 200 and notlar.json()["notes"] == "Not"
    assert (
        istemci.delete(_yol("library-weeding-batch-item-detail", batch.pk, ikinci.pk)).status_code
        == 204
    )
    assert istemci.post(_yol("library-weeding-batch-submit", batch.pk)).status_code == 200
    silinemez = istemci.delete(_yol("library-weeding-batch-item-detail", batch.pk, birinci.pk))
    assert silinemez.status_code == 400 and "taslak" in silinemez.json()["message"]
    geri = istemci.post(_yol("library-weeding-batch-withdraw", batch.pk))
    assert geri.status_code == 200 and geri.json()["status"] == "DRAFT"
    iptal = istemci.post(
        _yol("library-weeding-batch-cancel", batch.pk), {"reason": "Vazgeçildi"}, format="json"
    )
    assert iptal.json()["status"] == "CANCELLED" and iptal.json()["cancel_reason"] == "Vazgeçildi"
    assert istemci.get(TEKLIF, {"status": "CANCELLED"}).json()["count"] == 1
    assert istemci.get(TEKLIF, {"status": "YOK"}).status_code == 400

    taslak = teklif()
    assert istemci.delete(_yol("library-weeding-batch-detail", taslak.pk)).status_code == 204
    assert istemci.get(_yol("library-weeding-batch-detail", taslak.pk)).status_code == 404
    assert (
        istemci.delete(_yol("library-weeding-batch-item-detail", batch.pk, 999999)).status_code
        == 404
    )


def test_nadir_eser_listesi_duzenleme_ve_silme_uclari(istemci: APIClient) -> None:
    etkin_yil()
    liste = istemci.post("/api/v1/library/rare-works-submissions/", {}, format="json").json()
    lpk = liste["id"]
    nadir = raftaki("Yazma", is_rare_or_manuscript=True)
    eklenen = istemci.post(
        _yol("library-rare-works-submission-items", lpk),
        {"barcodes": [nadir.barcode]},
        format="json",
    ).json()["added"][0]
    karar = ayiklama_karari()
    duzen = istemci.patch(
        _yol("library-rare-works-submission-detail", lpk),
        {"commission_decision": karar.pk, "notes": "Eski baskılar"},
        format="json",
    )
    assert duzen.status_code == 200
    assert duzen.json()["decision"]["id"] == karar.pk and duzen.json()["notes"] == "Eski baskılar"
    assert (
        istemci.delete(
            _yol("library-rare-works-submission-item-detail", lpk, eklenen["id"])
        ).status_code
        == 204
    )
    assert istemci.get("/api/v1/library/rare-works-submissions/").json()["count"] == 1
    assert istemci.get(_yol("library-rare-copy-list"), {"unsent": "1"}).json()["count"] == 1
    assert istemci.delete(_yol("library-rare-works-submission-detail", lpk)).status_code == 204


def test_yil_sonu_raporu_geri_alma_ve_tekil_rapor(istemci: APIClient) -> None:
    etkin_yil()
    rpk = istemci.post("/api/v1/library/annual-reviews/", {}, format="json").json()["id"]
    ikinci = istemci.post("/api/v1/library/annual-reviews/", {}, format="json")
    assert ikinci.status_code == 400 and "school_year" in ikinci.json()["fields"]
    istemci.post(_yol("library-annual-review-finalize", rpk))
    kilitli = istemci.patch(
        _yol("library-annual-review-detail", rpk), {"findings": "X"}, format="json"
    )
    assert kilitli.status_code == 400
    acik = istemci.post(_yol("library-annual-review-reopen", rpk))
    assert acik.status_code == 200 and acik.json()["is_finalized"] is False
    assert istemci.get(_yol("library-annual-review-detail", 999999)).status_code == 404


# ============================================================ F8 düzeltme turu (25.09.2026)


def test_onay_ucu_imha_kararini_kalem_duzeyinde_alir(istemci: APIClient) -> None:
    """`destruction_items`: imha kararının kapsadığı kalemler (TMY 28/5); yanlış kalem 400."""
    batch = teklif()
    imha = kalem_ekle(batch, raftaki("İmha Edilecek"), "OBSOLETE")
    kalan = kalem_ekle(batch, raftaki("Ekonomik Değeri Olan"), "OBSOLETE")
    weeding.submit_batch(batch)
    weeding.bind_decision(batch, commission_decision=ayiklama_karari())
    govde: dict[str, Any] = {
        "approved_by_name": HARCAMA_YETKILISI,
        "approved_on": timezone.localdate().isoformat(),
        "tmy_commission_members": TMY_KOMISYONU,
        "destruction_decided": True,
    }
    yol = _yol("library-weeding-batch-approve", batch.pk)
    hatali = istemci.post(yol, {**govde, "destruction_items": [999999]}, format="json")
    assert hatali.status_code == 400
    assert "destruction_items" in hatali.json()["fields"]

    yanit = istemci.post(yol, {**govde, "destruction_items": [imha.pk]}, format="json")
    assert yanit.status_code == 200, yanit.json()
    kalemler = {k["id"]: k for k in yanit.json()["items"]}
    assert kalemler[imha.pk]["destruction_decided"] is True
    assert kalemler[kalan.pk]["destruction_decided"] is False


def test_teklifteki_nushanin_silme_ucu_400_gerekceyle(istemci: APIClient) -> None:
    """Nüsha silme ucu (F2) teklife girmiş nüshayı reddeder (F8 düzeltme turu)."""
    kitap = raftaki("Teklifteki Kitap")
    kalem_ekle(teklif(), kitap)
    yanit = istemci.delete(f"/api/v1/library/copies/{kitap.pk}/")
    assert yanit.status_code == 400
    assert "Ayıklama teklifine girmiş nüsha silinemez" in yanit.json()["message"]
    assert tazele(kitap).deleted_at is None
