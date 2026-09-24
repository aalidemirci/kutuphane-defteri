"""Evrak ve pano uçları (E4, E13, E19, T15, A11) — yalnız yönetici kipi, alan listeleri, PDF'ler.

Kart basımı uçları `test_uye_karti.py`'dedir. Görevli kipinde bu dosyadaki her
uç 403 `kip_yetkisiz` döner (izin listesinde değildirler; genel dolaşma
`apps/okul/tests/test_kip_koruma.py`). Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane import pano
from apps.kutuphane.models import Loan
from apps.kutuphane.serializers_evrak import OverdueLoanRowSerializer, RecentTransactionSerializer
from apps.kutuphane.services import circulation
from apps.kutuphane.tests.dolasim_ortak import gecikmeli_yap, odunc_ver, ogrenci, personel, uye
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db

KOK = "/api/v1/library/"
UCLAR: tuple[tuple[str, str], ...] = (
    ("get", "member-cards/"),
    ("get", "member-cards/template/"),
    ("post", "member-cards/pdf/"),
    ("post", "member-cards/confirm-print/"),
    ("post", "member-cards/revert-print/"),
    ("get", "overdue-loans/"),
    ("get", "overdue-loans/pdf/"),
    ("post", "overdue-loans/slips/"),
    ("post", "documents/privacy-notice/"),
    ("get", "documents/desk-card/"),
    ("get", "dashboard/circulation/"),
    ("post", "dashboard/circulation/"),
    ("get", "dashboard/recent-transactions/"),
)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _pano_sifirla() -> None:
    pano.reset_for_tests()


def _pdf(yanit: object) -> bytes:
    return b"".join(yanit.streaming_content)  # type: ignore[attr-defined]


# ============================================================ kip kapısı


def test_gorevli_kipinde_evrak_ve_pano_uclarinin_hepsi_403(client: APIClient) -> None:
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
    assert not {a for a in adlar if a.startswith(("library-member-card", "library-overdue"))}
    assert not adlar & {
        "library-privacy-notice-pdf",
        "library-desk-card-pdf",
        "library-dashboard-circulation",
        "library-dashboard-recent-transactions",
    }


# ============================================================ alan listeleri


def test_gecikmis_odunc_satirinin_alan_listesi_sabittir() -> None:
    assert OverdueLoanRowSerializer.Meta.fields == [
        "id",
        "membership_id",
        "full_name",
        "person_label",
        "is_student",
        "barcode",
        "barcode_display",
        "work_title",
        "loaned_at",
        "due_date",
        "overdue_days",
    ]


def test_son_islem_satirinin_alan_listesi_sabittir() -> None:
    assert list(RecentTransactionSerializer().fields) == [
        "kind",
        "kind_display",
        "at",
        "loan_id",
        "barcode_display",
        "work_title",
        "full_name",
        "person_label",
    ]


# ============================================================ gecikmiş ödünçler


def test_gecikmis_liste_ucu_kisi_sirasi_ve_suzgec(client: APIClient) -> None:
    a = gecikmeli_yap(odunc_ver(uye(ogrenci(class_level=10, class_section="A"))), gun=3)
    b = gecikmeli_yap(odunc_ver(uye(ogrenci(class_level=9, class_section="B"))), gun=8)
    c = gecikmeli_yap(odunc_ver(uye(personel(first_name="Ayla", last_name="Deneme"))), gun=1)
    odunc_ver(uye())  # gecikmemiş

    govde = client.get(f"{KOK}overdue-loans/").json()

    assert govde["count"] == 3
    assert [s["id"] for s in govde["results"]] == [b.pk, a.pk, c.pk]
    ilk = govde["results"][0]
    assert ilk["person_label"] == "9/B" and ilk["overdue_days"] == 8 and ilk["is_student"] is True
    assert govde["results"][2]["person_label"] == "Öğretmen"
    suzulen = client.get(f"{KOK}overdue-loans/", {"class_level": 10}).json()
    assert [s["id"] for s in suzulen["results"]] == [a.pk]
    assert client.get(f"{KOK}overdue-loans/", {"class_level": "x"}).status_code == 400


def test_gecikmis_liste_pdf_ucu(client: APIClient) -> None:
    gecikmeli_yap(odunc_ver(uye(ogrenci(class_level=9, class_section="A"))))

    yanit = client.get(f"{KOK}overdue-loans/pdf/", {"class_level": "9", "class_section": "A"})

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Cache-Control"] == "no-store"
    assert _pdf(yanit).startswith(b"%PDF")


def test_pusula_ucu_secilen_kisi_ve_bos_secim(client: APIClient) -> None:
    uyelik = uye()
    gecikmeli_yap(odunc_ver(uyelik))

    yanit = client.post(
        f"{KOK}overdue-loans/slips/", {"membership_ids": [uyelik.pk]}, format="json"
    )
    assert yanit.status_code == 200
    assert _pdf(yanit).startswith(b"%PDF")

    bos = client.post(f"{KOK}overdue-loans/slips/", {"class_level": 12}, format="json")
    assert bos.status_code == 400
    assert bos.json()["message"] == "Bu seçimde gecikmiş ödünç yok."


def test_pusula_ucu_ust_siniri(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.kutuphane import dolasim_belgeleri

    monkeypatch.setattr(dolasim_belgeleri, "MAX_SLIPS_PER_DOCUMENT", 1)
    for _ in range(2):
        gecikmeli_yap(odunc_ver(uye()))

    yanit = client.post(f"{KOK}overdue-loans/slips/", {}, format="json")

    assert yanit.status_code == 400
    assert "şube şube" in yanit.json()["message"]


# ============================================================ E13, E19


def test_aydinlatma_metni_ucu_bilgileri_saklamaz(client: APIClient) -> None:
    from apps.okul.models import SchoolConfig

    once = SchoolConfig.load().updated_at
    yanit = client.post(
        f"{KOK}documents/privacy-notice/",
        {"basvuru_adresi": "Örnek Mahallesi", "iletisim": "ornek@example.org"},
        format="json",
    )

    assert yanit.status_code == 200
    assert _pdf(yanit).startswith(b"%PDF")
    assert SchoolConfig.load().updated_at == once
    uzun = client.post(
        f"{KOK}documents/privacy-notice/", {"basvuru_adresi": "x" * 301}, format="json"
    )
    assert uzun.status_code == 400


def test_masa_karti_ucu(client: APIClient) -> None:
    yanit = client.get(f"{KOK}documents/desk-card/")
    assert yanit.status_code == 200
    assert _pdf(yanit).startswith(b"%PDF")


# ============================================================ pano (A11, T15)


def test_pano_ozeti_yalniz_sayi_tasir(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KD_ONCEKI_OTURUM", raising=False)
    gecikmeli_yap(odunc_ver(uye(ogrenci(first_name="Deneme", last_name="Gizli"))))

    govde = client.get(f"{KOK}dashboard/circulation/").json()

    assert govde == {"overdue_count": 1, "unexpected_shutdown": False}


def test_beklenmedik_kapanis_karti_ve_kontrol_ettim(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KD_ONCEKI_OTURUM", "beklenmedik")

    assert client.get(f"{KOK}dashboard/circulation/").json()["unexpected_shutdown"] is True
    onay = client.post(f"{KOK}dashboard/circulation/", {}, format="json")
    assert onay.status_code == 200 and onay.json()["unexpected_shutdown"] is False
    assert client.get(f"{KOK}dashboard/circulation/").json()["unexpected_shutdown"] is False


def test_temiz_kapanista_kart_yok(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KD_ONCEKI_OTURUM", "temiz")
    assert client.get(f"{KOK}dashboard/circulation/").json()["unexpected_shutdown"] is False


def test_son_islemler_ucu(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.kutuphane import selectors_dolasim

    verilen = odunc_ver(uye(ogrenci(first_name="Deneme", last_name="Son", class_level=9)))
    circulation.return_copy(copy=verilen.copy)
    monkeypatch.setattr(
        selectors_dolasim, "_surec_baslangici", timezone.now() + timedelta(minutes=1)
    )

    govde = client.get(f"{KOK}dashboard/recent-transactions/").json()

    assert [s["kind"] for s in govde] == ["RETURN", "LOAN"]
    assert govde[0]["kind_display"] == "İade alındı"
    assert govde[0]["full_name"] == "Deneme Son"
    assert govde[0]["person_label"] == "9/A"
    assert govde[0]["loan_id"] == verilen.pk
    assert Loan.objects.count() == 1


# ============================================================ ön yüz sabitleri


def _uyelik_api_kaynagi() -> str:
    """`frontend/src/modules/uyelik/api.ts` — yerelde depo kökü, konteynerde /repo."""
    from pathlib import Path

    goreli = Path("frontend") / "src" / "modules" / "uyelik" / "api.ts"
    for kok in (Path(__file__).resolve().parents[4], Path("/repo")):
        if (kok / goreli).is_file():
            return (kok / goreli).read_text(encoding="utf-8")
    pytest.fail(f"{goreli} bulunamadı.")


def test_on_yuzdeki_belge_adlari_ve_dipnot_backendle_ayni() -> None:
    """İndirme adları ve dipnot iki katmanda aynıdır (sözlük §2-§3, §5)."""
    import re

    from apps.kutuphane import dolasim_belgeleri
    from apps.kutuphane.labels import card

    kaynak = _uyelik_api_kaynagi()
    beklenen = {
        "UYE_KARTI_ADI": card.DOCUMENT_NAME,
        "PUSULA_ADI": dolasim_belgeleri.PUSULA_ADI,
        "GECIKME_LISTESI_ADI": dolasim_belgeleri.LISTE_ADI,
        "AYDINLATMA_ADI": dolasim_belgeleri.AYDINLATMA_ADI,
        "MASA_KARTI_ADI": dolasim_belgeleri.MASA_KARTI_ADI,
        "LISTE_DIPNOTU": dolasim_belgeleri.LISTE_DIPNOTU,
    }
    for ad, deger in beklenen.items():
        eslesme = re.search(rf'^export const {ad} = "(.+)";$', kaynak, flags=re.MULTILINE)
        assert eslesme is not None, ad
        assert eslesme.group(1) == deger, ad
