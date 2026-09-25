"""§5.10-8 (F6 dolu) — görevli kipinde AÇIK her kütüphane ucunun yanıt alan listesi.

Görevli kipinin izin listesi (`apps/okul/kip_izinleri.py`) hangi uçların açık
olduğunu söyler; bu dosya o uçların görevliye NE GÖSTERDİĞİNİ sabitler. Her
açık (uç, yöntem) çifti gerçek veriyle görevli kipinde çağrılır ve yanıtın alan
ağacı (noktalı yollar; listelerde `[]`) anlık görüntüyle karşılaştırılır:

* kartla üye çözme YALNIZ ad + kalan hak (sınıf, okul no, kart no, açık ödünç YOK);
* iadede ödünç alanın kimliği ve gecikme günü YOK;
* nüsha durum sorgusunda ödünç kimde YOK;
* teslimden geri alma okutmasında (F7) teslim alanın kimliği YOK;
* katalog okuma Ağ Kataloğunun alan listesine denk (edinim, fiyat, bağışçı, TKYS,
  etiket damgaları YOK).

Listeye yeni bir kütüphane ucu eklenirse `test_her_acik_ucun_anlik_goruntusu_var`
düşer: görevli yüzeyine giren her uç burada bilinçli olarak tarif edilir. Genel
dolaşma (izin listesi dışı her uç 403) `apps/okul/tests/test_kip_koruma.py`'dedir.
Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.kutuphane.tests import ortak
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import teslim_et
from apps.okul.kip import KIP
from apps.okul.kip_izinleri import IZIN_LISTESI
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import DOGRU_PAROLA, sahte_dogrulayici

pytestmark = pytest.mark.django_db

AD, SOYAD, OKUL_NO = "Yuzey", "Uydurmaoglu", "700555"

SAYFA = {"count", "next", "previous"}
ESER = {
    "id",
    "title",
    "authors",
    "translator",
    "edition",
    "publisher",
    "publish_year",
    "isbn",
    "subjects",
    "language",
    "resource_type",
    "resource_type_display",
    "classification_code",
    "call_number",
    "section_name",
    "copy_count",
    "available_copy_count",
}
KATALOG_NUSHASI = {
    "id",
    "work",
    "work_title",
    "call_number",
    "section_name",
    "status",
    "status_display",
    "is_loanable",
    "not_loanable_reason",
}
NUSHA_OZETI = {"copy.barcode", "copy.barcode_display", "copy.work_title"}

#: (URL adı, yöntem) → görevli kipindeki yanıtın alan ağacı. BİLİNÇLİ DEĞİŞİR.
GOREVLI_YANITLARI: dict[tuple[str, str], set[str]] = {
    ("library-desk-member", "POST"): {
        "state",
        "message",
        "member.full_name",
        "member.remaining_quota",
    },
    ("library-checkout", "POST"): {
        "message",
        "due_date",
        "warnings",
        "member.full_name",
        "member.remaining_quota",
        *NUSHA_OZETI,
    },
    ("library-return", "POST"): {"result", "kind", "message", *NUSHA_OZETI},
    ("library-desk-copy-status", "GET"): {
        "kind",
        "message",
        *NUSHA_OZETI,
        "copy.status",
        "copy.status_display",
        "copy.is_loanable",
        "copy.not_loanable_reason",
    },
    ("library-desk-card-unlock", "POST"): {"message"},
    ("library-work-list", "GET"): {*SAYFA, *{f"results[].{a}" for a in ESER}},
    ("library-work-detail", "GET"): ESER,
    ("library-copy-list", "GET"): {*SAYFA, *{f"results[].{a}" for a in KATALOG_NUSHASI}},
    ("library-label-verify", "POST"): {"result", "kind", "message", *NUSHA_OZETI},
    # F7: teslimden geri alma okutması — teslim alanın kimliği (şube, öğretmen), belge
    # no ve tarihler YOK (§4.4).
    ("library-delivery-take-back", "POST"): {"result", "kind", "message", *NUSHA_OZETI},
}


def _alan_agaci(deger: Any, onek: str = "") -> set[str]:
    """Yanıtın noktalı alan yolları; listede ilk öğe örnek alınır (`[]`)."""
    if isinstance(deger, dict):
        yollar: set[str] = set()
        for anahtar, alt in deger.items():
            yol = f"{onek}{anahtar}"
            alt_yollar = _alan_agaci(alt, f"{yol}.")
            yollar |= alt_yollar or {yol}
        return yollar
    if isinstance(deger, list) and deger and isinstance(deger[0], dict):
        return _alan_agaci(deger[0], f"{onek[:-1]}[].")
    return set()


@pytest.fixture
def veri(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Yönetici kipinde kurulan uydurma veri; sonra görevli kipine geçilir."""
    monkeypatch.setattr(app_password, "verify_password", sahte_dogrulayici([]))
    uyelik = uye(ogrenci(first_name=AD, last_name=SOYAD, student_number=OKUL_NO))
    oduncte = odunc_ver(uyelik, odunc_nushasi(title="Yüzey Eseri"))
    rafta = odunc_nushasi(title="Raftaki Eser")
    # F7: 9/A sınıf kitaplığına teslim (şube etiketi görevli yanıtında geçmemeli).
    teslimde = teslim_et([odunc_nushasi(title="Teslimdeki Eser")]).deliveries[0]
    KIP.gorevliye_gec()
    return {
        "uyelik": uyelik,
        "oduncte": oduncte,
        "rafta": rafta,
        "teslimde": teslimde,
        "eser": ortak.eser(title="Katalogdaki Eser"),
    }


def _istekler(veri: dict[str, Any]) -> dict[tuple[str, str], Callable[[APIClient], Any]]:
    uyelik = veri["uyelik"]
    rafta = veri["rafta"]
    oduncte = veri["oduncte"]

    def json_post(ad: str, govde: dict[str, Any]) -> Callable[[APIClient], Any]:
        return lambda c: c.post(reverse(ad), govde, format="json")

    return {
        ("library-desk-member", "POST"): json_post(
            "library-desk-member", {"card_no": uyelik.card_no}
        ),
        ("library-checkout", "POST"): json_post(
            "library-checkout", {"card_no": uyelik.card_no, "barcode": rafta.barcode}
        ),
        ("library-return", "POST"): json_post("library-return", {"barcode": oduncte.copy.barcode}),
        ("library-desk-copy-status", "GET"): lambda c: c.get(
            reverse("library-desk-copy-status"), {"barcode": oduncte.copy.barcode}
        ),
        ("library-desk-card-unlock", "POST"): json_post(
            "library-desk-card-unlock", {"password": DOGRU_PAROLA}
        ),
        ("library-work-list", "GET"): lambda c: c.get(reverse("library-work-list"), {"q": "eser"}),
        ("library-work-detail", "GET"): lambda c: c.get(
            reverse("library-work-detail", args=[rafta.work_id])
        ),
        ("library-copy-list", "GET"): lambda c: c.get(
            reverse("library-copy-list"), {"work": rafta.work_id}
        ),
        ("library-delivery-take-back", "POST"): json_post(
            "library-delivery-take-back", {"barcode": veri["teslimde"].copy.barcode}
        ),
        ("library-label-verify", "POST"): json_post(
            "library-label-verify", {"code": rafta.barcode}
        ),
    }


def test_her_acik_ucun_anlik_goruntusu_var() -> None:
    """İzin listesindeki her kütüphane (uç, yöntem) çifti burada tarif edilir."""
    acik = {(k.uc, k.yontem) for k in IZIN_LISTESI if k.uc.startswith("library-")}
    assert acik == set(GOREVLI_YANITLARI)


def test_gorevli_yanitlarinin_alan_listesi_anlik_goruntuyle_aynidir(
    veri: dict[str, Any],
) -> None:
    istemci = APIClient()
    farklar: dict[str, Any] = {}
    for cift, istek in _istekler(veri).items():
        yanit = istek(istemci)
        assert yanit.status_code in (200, 201), (cift, yanit.status_code, yanit.content)
        agac = _alan_agaci(yanit.json())
        # Doğrulama okutmasında nüsha basılmamışsa `copy` yine dolu döner; boş
        # dönerse yol listesi eksik kalır — sınama gerçek veriyle yapılmalıdır.
        if agac != GOREVLI_YANITLARI[cift]:
            farklar[f"{cift[1]} {cift[0]}"] = {
                "fazla": sorted(agac - GOREVLI_YANITLARI[cift]),
                "eksik": sorted(GOREVLI_YANITLARI[cift] - agac),
            }
    assert farklar == {}
    assert KIP.durum() == "gorevli"


def test_gorevli_yanitlarinda_okul_no_sinif_ve_kart_no_gecmez(veri: dict[str, Any]) -> None:
    """Ad yalnız kartla üye çözme ve ödünç yanıtında (masadaki kişinin kendisi) geçer."""
    istemci = APIClient()
    uyelik = veri["uyelik"]
    for cift, istek in _istekler(veri).items():
        metin = istek(istemci).content.decode()
        assert OKUL_NO not in metin, cift
        assert "9/A" not in metin, cift
        assert uyelik.card_no not in metin, cift
        if cift not in {("library-desk-member", "POST"), ("library-checkout", "POST")}:
            assert AD not in metin and SOYAD not in metin, cift


def test_yonetici_kipinde_ayni_uclar_tam_yanit_verir(veri: dict[str, Any]) -> None:
    """Daralma kipe bağlıdır: yönetici kipinde katalog ve masa yanıtları geniştir."""
    KIP._reset_for_tests()
    istemci = APIClient()
    istekler = _istekler(veri)

    eser = _alan_agaci(istekler[("library-work-detail", "GET")](istemci).json())
    uye_yaniti = _alan_agaci(istekler[("library-desk-member", "POST")](istemci).json())

    assert {"created_at", "isbn13", "classification_source"} <= eser
    assert {"member.class_label", "member.membership_id"} <= uye_yaniti
