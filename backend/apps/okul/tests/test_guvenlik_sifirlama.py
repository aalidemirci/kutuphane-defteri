"""Kayıp ekranındaki "güvenlik dosyasını sıfırla ve kuruluma dön" yolu (F1-E; GA-2 eki).

Yol YALNIZ şu dört koşul birlikteyken açıktır (`app_password.state_reset_available`):
güvenlik dosyası var ama kullanılamıyor · DB'de anahtar parmak izi boş · şifreli
alan taşıyan bütün tablolar (silinmişler dahil) boş · yedek klasöründe (parola
kurulurken alınan geçiş yedeği dışında) yedek yok. Korunan veri yoktur; bozuk
dosya SİLİNMEZ, arşivlenir ve program ilk açılış hâline döner. Aksi hâlde yol
görünmez (`reset_available: false`) ve uç 409 `sifirlama_uygun_degil` döner.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from desktop.backup_crypto import config_path, ensure_public_config
from rest_framework.test import APIClient

from apps.okul.models import Student
from apps.okul.services import app_password
from conftest import TEST_DEK
from shared import crypto

URL = "/api/v1/security/state/reset/"
BOZUK = b"{bozuk"

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def bozuk_ilk_kurulum(parolasiz: Path) -> Path:
    """Parola kurulumu yarıda kalmış ilk açılış: dosya bozuk, parmak izi boş, kişi yok."""
    app_password.state_path().write_bytes(BOZUK)
    ensure_public_config(parolasiz, TEST_DEK, replace=True)
    return parolasiz


def test_kosullar_saglaninca_yol_gorunur_ve_dosya_arsivlenir(
    client: APIClient, bozuk_ilk_kurulum: Path
) -> None:
    durum = client.get("/api/v1/security/status/").json()
    assert durum["security_file_missing"] is True
    assert durum["reset_available"] is True
    # Kayıp kilidi yürürlükte; sıfırlama ucu buna rağmen erişilebilir.
    assert client.get("/api/v1/students/").json()["code"] == "guvenlik_dosyasi_kayip"

    yanit = client.post(URL)

    assert yanit.status_code == 200, yanit.json()
    veri = yanit.json()
    assert veri["archived_as"].startswith("guvenlik-arsiv-")
    assert (bozuk_ilk_kurulum / veri["archived_as"]).read_bytes() == BOZUK
    assert not app_password.state_path().exists()
    assert not config_path(bozuk_ilk_kurulum).exists()
    assert list(bozuk_ilk_kurulum.glob("yedekleme-arsiv-*.json"))
    assert veri["password_set"] is False
    assert veri["security_file_missing"] is False
    assert veri["reset_available"] is False


def test_sifirlama_sonrasi_sihirbaz_parola_adimindan_baslar_ve_parola_kurulur(
    client: APIClient, bozuk_ilk_kurulum: Path
) -> None:
    assert client.post(URL).status_code == 200

    durum = client.get("/api/v1/setup/status/").json()
    assert durum["password_set"] is False
    assert durum["missing_steps"][0] == "password"
    kurma = client.post("/api/v1/security/enable/", {"password": "Yeni-Parola-42"}, format="json")
    assert kurma.status_code == 201, kurma.json()
    assert kurma.json()["recovery_key"]


def test_parmak_izi_doluysa_409_ve_dosyaya_dokunulmaz(
    client: APIClient, parmak_izi_yazili: str
) -> None:
    app_password.state_path().write_bytes(BOZUK)
    crypto.unload_key()

    assert client.get("/api/v1/security/status/").json()["reset_available"] is False
    yanit = client.post(URL)
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "sifirlama_uygun_degil"
    assert app_password.state_path().read_bytes() == BOZUK


def test_silinmis_bile_olsa_kisi_kaydi_varsa_409(client: APIClient) -> None:
    ogrenci = Student.objects.create(first_name="DENEME", last_name="ÖĞRENCİ", class_level=9)
    ogrenci.delete()  # yumuşak silme: satır tabloda kalır
    app_password.state_path().write_bytes(BOZUK)
    crypto.unload_key()

    yanit = client.post(URL)
    assert yanit.status_code == 409
    assert app_password.state_path().read_bytes() == BOZUK


@pytest.mark.parametrize(
    "yedek_adi",
    ["gunluk-2026-09-01.kdbak", "pre-migrate-2026.9.0-2026-09-01.kdbak", "elle-alinan.kdbak"],
)
def test_yedek_klasorunde_veri_yedegi_varsa_409(
    client: APIClient, bozuk_ilk_kurulum: Path, yedek_adi: str
) -> None:
    """Veritabanı kaybolup boş yeniden oluştuysa eski kayıtlar yedeklerde durur.

    Sıfırlama yeni anahtarla yeni yedek zinciri başlatır ve 14 günlük rotasyon
    eski anahtarlı günlük yedekleri silerdi: yol kapalıdır, doğru çıkış yedekten
    geri yüklemedir.
    """
    dizin = app_password.backup_dir()
    dizin.mkdir(parents=True, exist_ok=True)
    (dizin / yedek_adi).write_bytes(b"KDBAK\x02" + b"\x00" * 64)

    assert client.get("/api/v1/security/status/").json()["reset_available"] is False
    yanit = client.post(URL)
    assert yanit.status_code == 409
    assert app_password.state_path().read_bytes() == BOZUK


def test_parola_kurulurken_alinan_gecis_yedegi_yolu_kapatmaz(
    client: APIClient, bozuk_ilk_kurulum: Path
) -> None:
    """`pre-parola-acilis-*` kişi tabloları boşken alınır; korunan veri taşımaz."""
    dizin = app_password.backup_dir()
    dizin.mkdir(parents=True, exist_ok=True)
    (dizin / "pre-parola-acilis-2026-09-22-101500.kdbak").write_bytes(b"KDBAK\x02")

    assert client.get("/api/v1/security/status/").json()["reset_available"] is True


def test_saglam_dosyada_409(client: APIClient) -> None:
    yanit = client.post(URL)
    assert yanit.status_code == 409
    assert yanit.json()["code"] == "sifirlama_uygun_degil"
    assert app_password.read_state() is not None


def test_dosya_hic_yokken_409(client: APIClient, parolasiz: Path) -> None:
    assert client.post(URL).status_code == 409


def test_servis_kosulsuz_cagrida_reddeder() -> None:
    """Savunma derinliği: görünüm atlansa da servis kendi koşulunu denetler."""
    with pytest.raises(app_password.StateResetNotAllowed):
        app_password.reset_unusable_state()
