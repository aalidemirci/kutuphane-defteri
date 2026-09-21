"""Kip uçları (`security/mode/*`) — uçtan uca davranış (U5, tasarım §4.4).

İstekler tam ara katman zincirinden geçer (restart → kilit → kip). Kip tekili
her testte sıfırlanır (kök `conftest.py`).
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import DOGRU_PAROLA, YANLIS_PAROLA, sahte_dogrulayici
from conftest import TEST_PAROLA  # kök conftest: varsayılan ortamın yönetici parolası

pytestmark = pytest.mark.django_db

MOD = "/api/v1/security/mode/"
GOREVLI = "/api/v1/security/mode/staff/"
YONETICI = "/api/v1/security/mode/admin/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def dogrulama_cagrilari(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    cagrilar: list[str] = []
    monkeypatch.setattr(app_password, "verify_password", sahte_dogrulayici(cagrilar))
    return cagrilar


def _govde(resp: Any) -> dict[str, Any]:
    veri: dict[str, Any] = resp.json()
    return veri


def test_durum_ucu_yonetici_kipini_ve_kalan_sureleri_doner(client: APIClient) -> None:
    resp = client.get(MOD)

    assert resp.status_code == 200
    govde = _govde(resp)
    assert govde["durum"] == "yonetici"
    assert govde["bosta_dk"] == 3
    assert govde["mutlak_dk"] == 30
    assert 0 < govde["bosta_kalan_sn"] <= 180
    assert 0 < govde["mutlak_kalan_sn"] <= 1800


def test_gorevli_kipine_gecis_parolasizdir(client: APIClient) -> None:
    resp = client.post(GOREVLI)

    assert resp.status_code == 200
    assert _govde(resp)["durum"] == "gorevli"
    assert _govde(client.get(MOD))["durum"] == "gorevli"
    assert KIP.durum() == "gorevli"


def test_gorevli_kipinde_gorevli_ucuna_istek_kip_yetkisiz_alir(client: APIClient) -> None:
    client.post(GOREVLI)

    resp = client.post(GOREVLI)

    assert resp.status_code == 403
    assert _govde(resp)["code"] == "kip_yetkisiz"


def test_yanlis_parola_400_ve_parola_hatali_iletisi(
    client: APIClient, dogrulama_cagrilari: list[str]
) -> None:
    client.post(GOREVLI)

    resp = client.post(YONETICI, {"password": YANLIS_PAROLA}, format="json")

    assert resp.status_code == 400
    govde = _govde(resp)
    assert govde["code"] == "validation_error"
    assert govde["message"] == "Parola hatalı."
    assert YANLIS_PAROLA not in resp.content.decode("utf-8")
    assert KIP.durum() == "gorevli"


def test_dogru_parola_yonetici_kipine_gecirir(
    client: APIClient, dogrulama_cagrilari: list[str]
) -> None:
    client.post(GOREVLI)

    resp = client.post(YONETICI, {"password": DOGRU_PAROLA}, format="json")

    assert resp.status_code == 200
    assert _govde(resp)["durum"] == "yonetici"
    assert _govde(resp)["bosta_kalan_sn"] == 180
    assert dogrulama_cagrilari == [DOGRU_PAROLA]


def test_parolasiz_yukseltme_istegi_400(client: APIClient, dogrulama_cagrilari: list[str]) -> None:
    client.post(GOREVLI)

    resp = client.post(YONETICI, {}, format="json")

    assert resp.status_code == 400
    assert dogrulama_cagrilari == []
    assert KIP.durum() == "gorevli"


def test_gercek_parola_dogrulamasiyla_yukseltme(client: APIClient) -> None:
    """Taklitsiz: kök conftest'in kurduğu güvenlik dosyası ve parolasıyla."""
    client.post(GOREVLI)
    yanlis = client.post(YONETICI, {"password": YANLIS_PAROLA}, format="json")
    assert yanlis.status_code == 400
    assert _govde(yanlis)["message"] == "Parola hatalı."
    assert KIP.durum() == "gorevli"

    dogru = client.post(YONETICI, {"password": TEST_PAROLA}, format="json")
    assert dogru.status_code == 200
    assert _govde(dogru)["durum"] == "yonetici"


def test_kilitle_gorevli_kipinde_de_calisir(client: APIClient) -> None:
    client.post(GOREVLI)

    resp = client.post("/api/v1/security/lock/")

    assert resp.status_code == 200
    assert _govde(client.get(MOD))["durum"] == "kilitli"


class TestKilitKapaliyken:
    def test_kilitliyken_durum_ucu_kilitli_der(self, kilitli: None, client: APIClient) -> None:
        resp = client.get(MOD)

        assert resp.status_code == 200
        assert _govde(resp)["durum"] == "kilitli"
        assert _govde(resp)["bosta_kalan_sn"] is None

    def test_parola_kurulmadan_durum_ucu_kurulum_der(
        self, parolasiz: None, client: APIClient
    ) -> None:
        assert _govde(client.get(MOD))["durum"] == "kurulum"

    @pytest.mark.parametrize(
        ("yol", "govde"),
        [(GOREVLI, None), (YONETICI, {"password": DOGRU_PAROLA})],
    )
    def test_kilitliyken_kip_gecisi_409(
        self,
        kilitli: None,
        client: APIClient,
        dogrulama_cagrilari: list[str],
        yol: str,
        govde: dict[str, str] | None,
    ) -> None:
        resp = client.post(yol, govde, format="json")

        assert resp.status_code == 409
        assert _govde(resp)["code"] == "kip_gecisi_gecersiz"
        assert "kilidi açın" in _govde(resp)["message"]
        assert dogrulama_cagrilari == []

    def test_parola_kurulmadan_kip_gecisi_409(self, parolasiz: None, client: APIClient) -> None:
        resp = client.post(GOREVLI)

        assert resp.status_code == 409
        assert _govde(resp)["code"] == "kip_gecisi_gecersiz"
