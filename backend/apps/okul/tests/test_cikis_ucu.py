"""`POST app/quit/` — arayüzden düzenli çıkış (tasarım §4.2-4, §5.10-18, TB13).

§5.10-18: görevli kipinde parolasız `app/quit/` 403 döner, parolalı istek
düzenli kapanışı başlatır. Kapanışın kendisi masaüstü kancasıdır
(`masaustu_kanca.cikis_iste`); burada kancanın çağrılıp çağrılmadığı sınanır.
Pencere, tepsi, iki sunucu ve WAL checkpoint sırası masaüstü testlerindedir
(`desktop/tests/test_main.py`). İstekler tam ara katman zincirinden geçer
(oturum → yeniden başlat → kilit → kip).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul import masaustu_kanca, restart_gate
from apps.okul.kip import KIP
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import (
    DOGRU_PAROLA,
    YANLIS_PAROLA,
    kurulum_durumunu_yaz,
    sahte_dogrulayici,
)
from conftest import TEST_PAROLA  # kök conftest: varsayılan ortamın yönetici parolası

pytestmark = pytest.mark.django_db

CIK = "/api/v1/app/quit/"


@pytest.fixture(autouse=True)
def kancalar(db: None) -> Iterator[list[str]]:
    """Çıkış kancası yerine sayaç; test sonunda kayıt temizlenir."""
    kurulum_durumunu_yaz(tamam=True)
    cagrilar: list[str] = []
    masaustu_kanca._reset_for_tests()
    masaustu_kanca.kaydet(cikis=lambda: cagrilar.append("cik"))
    yield cagrilar
    masaustu_kanca._reset_for_tests()


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


# ------------------------------------------------------------ §5.10-18


def test_gorevli_kipinde_parolasiz_cikis_403_ve_kapanis_baslamaz(
    client: APIClient, kancalar: list[str]
) -> None:
    KIP.gorevliye_gec()

    for govde in ({}, {"password": ""}):
        resp = client.post(CIK, govde, format="json")
        assert resp.status_code == 403
        assert _govde(resp)["code"] == "cikis_parolasi_gerekli"
        assert "yönetici parolası" in _govde(resp)["message"]
    assert kancalar == []


def test_gorevli_kipinde_parolali_istek_duzenli_kapanisi_baslatir(
    client: APIClient, kancalar: list[str], dogrulama_cagrilari: list[str]
) -> None:
    KIP.gorevliye_gec()

    resp = client.post(CIK, {"password": DOGRU_PAROLA}, format="json")

    assert resp.status_code == 202
    assert _govde(resp) == {"durum": "kapaniyor"}
    assert kancalar == ["cik"]
    assert dogrulama_cagrilari == [DOGRU_PAROLA]


def test_gorevli_kipinde_yanlis_parola_400_ve_kapanis_baslamaz(
    client: APIClient, kancalar: list[str], dogrulama_cagrilari: list[str]
) -> None:
    KIP.gorevliye_gec()

    resp = client.post(CIK, {"password": YANLIS_PAROLA}, format="json")

    assert resp.status_code == 400
    assert "Parola hatalı." in resp.content.decode("utf-8")
    assert YANLIS_PAROLA not in resp.content.decode("utf-8")  # parola yankılanmaz
    assert kancalar == []


def test_gercek_parola_dogrulamasiyla_gorevli_kipinden_cikis(
    client: APIClient, kancalar: list[str]
) -> None:
    KIP.gorevliye_gec()

    assert client.post(CIK, {"password": "yanlis-parola"}, format="json").status_code == 400
    assert kancalar == []
    assert client.post(CIK, {"password": TEST_PAROLA}, format="json").status_code == 202
    assert kancalar == ["cik"]


def test_gorevli_kipinde_kip_kapisi_cikis_ucunu_yalniz_postta_gecirir(
    client: APIClient, kancalar: list[str]
) -> None:
    KIP.gorevliye_gec()

    for yontem in ("get", "put", "patch", "delete"):
        resp = getattr(client, yontem)(CIK)
        assert resp.status_code == 403
        assert _govde(resp)["code"] == "kip_yetkisiz"
    assert kancalar == []


# ------------------------------------------------------------ parolasız durumlar


def test_yonetici_kipinde_cikis_parolasizdir(
    client: APIClient, kancalar: list[str], dogrulama_cagrilari: list[str]
) -> None:
    assert KIP.durum() == "yonetici"

    resp = client.post(CIK, {}, format="json")

    assert resp.status_code == 202
    assert kancalar == ["cik"]
    assert dogrulama_cagrilari == []  # parola sorulmadı


def test_kilitliyken_cikis_parolasizdir(
    kilitli: None, client: APIClient, kancalar: list[str]
) -> None:
    assert KIP.durum() == "kilitli"

    resp = client.post(CIK, {}, format="json")

    assert resp.status_code == 202
    assert kancalar == ["cik"]


def test_kilitliyken_cikis_disindaki_uclar_yine_423(
    kilitli: None, client: APIClient, kancalar: list[str]
) -> None:
    """Muafiyet tam yoldur: `app/` altındaki başka bir yol kilit kapısını aşamaz."""
    assert client.get("/api/v1/grade-levels/").status_code == 423
    assert client.post("/api/v1/app/quit/baska/", {}, format="json").status_code == 423


def test_parola_kurulmadan_cikis_parolasizdir(
    parolasiz: None, client: APIClient, kancalar: list[str]
) -> None:
    assert client.post(CIK, {}, format="json").status_code == 202
    assert kancalar == ["cik"]


def test_guvenlik_dosyasi_kayipken_cikis_parolasizdir(
    parmak_izi_yazili: str, client: APIClient, kancalar: list[str]
) -> None:
    app_password.state_path().unlink()
    assert client.get("/api/v1/grade-levels/").status_code == 423

    assert client.post(CIK, {}, format="json").status_code == 202
    assert kancalar == ["cik"]


def test_yeniden_baslat_gerektiginde_cikis_parolasizdir(
    client: APIClient, kancalar: list[str]
) -> None:
    """Geri yüklemeden sonra bütün API 503'tür; kapının tek çıkışı programı kapatmaktır."""
    KIP.gorevliye_gec()
    restart_gate.mark_restart_required()

    assert client.get("/api/v1/security/mode/").status_code == 503
    resp = client.post(CIK, {}, format="json")

    assert resp.status_code == 202
    assert kancalar == ["cik"]


# ------------------------------------------------------------ masaüstü dışında


def test_masaustu_kancasi_yoksa_503(client: APIClient) -> None:
    masaustu_kanca._reset_for_tests()

    resp = client.post(CIK, {}, format="json")

    assert resp.status_code == 503
    assert _govde(resp)["code"] == "cikis_kullanilamiyor"


# ------------------------------------------------------------ kanca kaydı


def test_kanca_kaydi_verilmeyeni_degistirmez_ve_kaldirilir() -> None:
    masaustu_kanca._reset_for_tests()
    cagrilar: list[str] = []

    masaustu_kanca.kaydet(cikis=lambda: cagrilar.append("bir"))
    masaustu_kanca.kaydet(katalog=None)  # çıkış kancası yerinde kalır
    assert masaustu_kanca.cikis_iste() is True
    masaustu_kanca.kaldir()

    assert masaustu_kanca.cikis_iste() is False
    assert masaustu_kanca.katalog_kontrolu() is None
    assert cagrilar == ["bir"]


def test_katalog_bakim_cagrilari_kanca_yokken_etkisizdir() -> None:
    masaustu_kanca._reset_for_tests()

    masaustu_kanca.katalog_bakima_al()
    masaustu_kanca.katalog_bakimdan_cik()


def test_gunluk_is_kaydi_ad_ile_tekildir() -> None:
    masaustu_kanca._reset_for_tests()

    masaustu_kanca.gunluk_is_kaydet("cok-okunanlar", lambda: True)
    masaustu_kanca.gunluk_is_kaydet("cok-okunanlar", lambda: None)
    masaustu_kanca.gunluk_is_kaydet("saklama", lambda: False)

    assert [is_.ad for is_ in masaustu_kanca.gunluk_isler()] == ["cok-okunanlar", "saklama"]
    with pytest.raises(ValueError):
        masaustu_kanca.gunluk_is_kaydet("çok-okunanlar", lambda: True)
    with pytest.raises(ValueError):
        masaustu_kanca.gunluk_is_kaydet("", lambda: True)
