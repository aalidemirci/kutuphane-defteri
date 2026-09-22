"""Kurtarma anahtarının saklandığının doğrulanması (F1 eki, 22.09.2026 kullanıcı kararı 2-2).

Kanıtlanan maddeler:

* kurulum, kurtarma anahtarı doğrulanmadan tamamlanmaz: `setup/complete/` damgasız
  kurulumu 400 `kurulum_eksik` ("kurtarma anahtarı doğrulanmadı") ile reddeder,
  `setup/status/` 1. adımı eksik sayar;
* `POST security/recovery-key/confirm/` yanlış anahtarı (kademeli gecikmeyle)
  reddeder, doğru anahtarı `guvenlik.json`'un kurtarma bölümüne damgalar;
  damga DB'de değil dosyadadır ve parola değişiminden sonra da kalır;
* başka kurulumun güvenlik dosyasıyla damga yazılmaz; kilitliyken 423, görevli
  kipinde 403, parola kurulmadan 400;
* kurulumu önceden (damgasız) tamamlanmış program kilitlenmez; durum uçları
  uyarı için `recovery_key_confirmed: false` söyler;
* anahtar hiçbir günlüğe ve hata gövdesine düşmez.

Varsayılan test ortamı (kök `conftest.py`) damgasızdır: parola kurulu, kilit
açık, anahtar doğrulanmamış.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.models import SchoolConfig, SchoolLevel
from apps.okul.services import app_password
from apps.okul.services import school_year as school_year_service
from apps.okul.services import setup as setup_service
from apps.okul.services import terms as term_service
from conftest import TEST_KURTARMA_ANAHTARI, TEST_PAROLA

URL = "/api/v1/security/recovery-key/confirm/"
KANONIK = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM"
YANLIS = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLN"

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _iste(client: APIClient, anahtar: str) -> Any:
    return client.post(URL, {"recovery_key": anahtar}, format="json")


def _durum_dosyasi() -> dict[str, Any]:
    veri: dict[str, Any] = json.loads(app_password.state_path().read_text(encoding="utf-8"))
    return veri


def _kurulum_hazir() -> None:
    """2. ve 3. adımlar tamam (okul bilgileri + dönemli aktif ders yılı)."""
    setup_service.update_school_config(
        fields={
            "school_name": "Örnek Anadolu Lisesi",
            "kademe": SchoolLevel.ORTAOGRETIM,
            "kisa_ad": "Örnek AL",
            "demirbas_onayi": True,
        }
    )
    yil = school_year_service.create_school_year(
        name="2026-2027", start_date=date(2026, 9, 7), end_date=date(2027, 6, 25), activate=True
    )
    term_service.configure_terms(yil, first_end=date(2027, 1, 22), second_start=date(2027, 2, 8))


# ============================================================ kurulum kapısı


class TestKurulumKapisi:
    def test_varsayilan_ortam_damgasizdir(self, client: APIClient) -> None:
        assert app_password.recovery_key_confirmed() is False
        assert client.get("/api/v1/security/status/").json()["recovery_key_confirmed"] is False
        veri = client.get("/api/v1/setup/status/").json()
        assert veri["password_set"] is True
        assert veri["recovery_key_confirmed"] is False
        # Parola kurulu ama anahtar doğrulanmamış: 1. adım eksik sayılır.
        assert veri["missing_steps"][0] == "password"

    def test_damgasiz_kurulum_tamamlanmaz(self, client: APIClient) -> None:
        _kurulum_hazir()
        yanit = client.post("/api/v1/setup/complete/")
        assert yanit.status_code == 400
        govde = yanit.json()
        assert govde["code"] == "kurulum_eksik"
        assert "1. adım (yönetici parolası): kurtarma anahtarı doğrulanmadı." in govde["message"]
        assert "2. adım" not in govde["message"] and "3. adım" not in govde["message"]
        assert SchoolConfig.load().setup_completed is False

    def test_dogrulaninca_kurulum_tamamlanir(self, client: APIClient) -> None:
        _kurulum_hazir()
        assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
        veri = client.get("/api/v1/setup/status/").json()
        assert veri["recovery_key_confirmed"] is True
        assert veri["missing_steps"] == []
        assert client.post("/api/v1/setup/complete/").status_code == 200

    def test_parolasizken_ileti_parolayi_soyler(self, client: APIClient, parolasiz: Path) -> None:
        _kurulum_hazir()
        mesaj = client.post("/api/v1/setup/complete/").json()["message"]
        assert "yönetici parolası kurulmadı" in mesaj
        assert "kurtarma anahtarı doğrulanmadı" not in mesaj

    def test_onceden_tamamlanmis_damgasiz_kurulum_kilitlenmez(self, client: APIClient) -> None:
        """Karardan önce tamamlanmış kurulum: program çalışır, durum uçları uyarı verir."""
        config = SchoolConfig.load()
        config.setup_completed = True
        config.save()

        assert client.get("/api/v1/grade-levels/").status_code == 200
        assert client.get("/api/v1/students/").status_code == 200
        veri = client.get("/api/v1/setup/status/").json()
        assert veri["setup_completed"] is True
        assert veri["recovery_key_confirmed"] is False


# ============================================================ doğrulama ucu


class TestDogrulamaUcu:
    def test_dogru_anahtar_damgalanir(self, client: APIClient) -> None:
        once = datetime.now().astimezone().replace(microsecond=0)
        yanit = _iste(client, TEST_KURTARMA_ANAHTARI)

        assert yanit.status_code == 200
        assert yanit.json()["recovery_key_confirmed"] is True
        kurtarma = _durum_dosyasi()["kurtarma"]
        damga = datetime.fromisoformat(kurtarma[app_password.RECOVERY_CONFIRMED_FIELD])
        assert damga >= once
        # Sarmal ve tuz değişmez: damga yalnız eklenir, dosya kullanılabilir kalır.
        assert {"salt", "sarmal"} <= set(kurtarma)
        assert app_password.security_file_missing() is False
        assert app_password.recovery_key_confirmed() is True

    @pytest.mark.parametrize(
        "yazim",
        [KANONIK.replace("-", "").lower(), " ".join(KANONIK.split("-")), KANONIK.replace("I", "İ")],
        ids=["kucuk_tiresiz", "bosluklu", "turkce_buyuk_i"],
    )
    def test_yazim_bicimi_onemsizdir(self, client: APIClient, yazim: str) -> None:
        assert _iste(client, yazim).status_code == 200
        assert app_password.recovery_key_confirmed() is True

    def test_yanlis_anahtar_reddedilir_damga_yazilmaz(self, client: APIClient) -> None:
        once = app_password.state_path().read_bytes()
        yanit = _iste(client, YANLIS)

        assert yanit.status_code == 400
        assert yanit.json()["message"].startswith("Kurtarma anahtarı hatalı.")
        assert YANLIS not in yanit.content.decode("utf-8")
        assert app_password.state_path().read_bytes() == once
        assert app_password.recovery_key_confirmed() is False

    def test_yanlis_anahtarda_kademeli_gecikme(
        self, client: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        uyumalar: list[float] = []
        monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 3.0))
        monkeypatch.setattr(time, "sleep", uyumalar.append)
        _iste(client, YANLIS)
        _iste(client, YANLIS)
        assert uyumalar == [3.0]

    def test_baska_kurulumun_dosyasiyla_damga_yazilmaz(self, client: APIClient) -> None:
        """Sarmal açılsa bile DEK bellekteki anahtar değilse (başka kurulum) damga yok."""
        baska = app_password._build_state(
            bytes(range(1, 33)), password="Baska-Parola-9", recovery_key=TEST_KURTARMA_ANAHTARI
        )
        baska["gecis"] = app_password.TRANSITION_DONE
        app_password._write_state(baska)

        assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 400
        assert app_password.recovery_key_confirmed() is False

    def test_damga_fikirdestir(self, client: APIClient) -> None:
        assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
        assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
        assert app_password.recovery_key_confirmed() is True

    def test_damga_parola_degisiminden_sonra_kalir(self) -> None:
        app_password.confirm_recovery_key(TEST_KURTARMA_ANAHTARI)
        app_password.change_password(current_password=TEST_PAROLA, new_password="Yeni-Parola-42")
        assert app_password.recovery_key_confirmed() is True

    def test_damga_kurtarmayla_parola_yenilemeden_sonra_kalir(self, kilitli: Path) -> None:
        app_password.unlock(password=TEST_PAROLA)
        app_password.confirm_recovery_key(TEST_KURTARMA_ANAHTARI)
        app_password.lock()
        app_password.unlock_with_recovery(
            recovery_key=TEST_KURTARMA_ANAHTARI, new_password="Yeni-Parola-42"
        )
        assert app_password.recovery_key_confirmed() is True

    def test_bos_ya_da_asiri_uzun_anahtar_reddedilir(self, client: APIClient) -> None:
        assert client.post(URL, {}, format="json").status_code == 400
        assert _iste(client, "").status_code == 400
        uzun = _iste(client, "A" * 129)
        assert uzun.status_code == 400
        assert "A" * 129 not in uzun.content.decode("utf-8")

    def test_kilitliyken_kilit_kapisi_keser(self, client: APIClient, kilitli: Path) -> None:
        yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
        assert yanit.status_code == 423
        assert yanit.json()["code"] == "locked"

    def test_servis_kilitliyken_dogrulamaz(self, kilitli: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="kilitli"):
            app_password.confirm_recovery_key(TEST_KURTARMA_ANAHTARI)
        assert app_password.recovery_key_confirmed() is False

    def test_gorevli_kipinde_kapali(self, client: APIClient) -> None:
        KIP.gorevliye_gec()
        yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"

    def test_guvenlik_dosyasi_kayipken_kapali(
        self, client: APIClient, parmak_izi_yazili: str
    ) -> None:
        app_password.state_path().unlink()
        yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
        assert yanit.status_code == 423
        assert yanit.json()["code"] == "guvenlik_dosyasi_kayip"

    def test_parola_kurulmadan_calismaz(self, client: APIClient, parolasiz: Path) -> None:
        yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
        assert yanit.status_code == 400
        assert yanit.json()["message"] == "Yönetici parolası kurulu değil."
        assert app_password.recovery_key_confirmed() is False

    def test_bozuk_dosyada_damga_okunamaz_hata_yukseltmez(self) -> None:
        app_password.state_path().write_text("{bozuk", encoding="utf-8")
        assert app_password.recovery_key_confirmed() is False


def test_anahtar_hicbir_gunluge_dusmez(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
    assert _iste(client, YANLIS).status_code == 400
    yasak = {TEST_KURTARMA_ANAHTARI, KANONIK.replace("-", ""), YANLIS, YANLIS.replace("-", "")}
    for kayit in caplog.records:
        for sir in yasak:
            assert sir not in kayit.getMessage(), kayit.name
            assert sir not in repr(kayit.args), kayit.name
    for sir in yasak:
        assert sir not in caplog.text
