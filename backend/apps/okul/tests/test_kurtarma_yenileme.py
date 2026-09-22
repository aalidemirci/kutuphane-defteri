"""Kurtarma anahtarını yenileme (F1 eki, 22.09.2026 kullanıcı kararı 2-3).

`POST security/recovery-key/renew/ {password}`. Kanıtlanan maddeler:

* yanlış parola reddedilir (kademeli gecikme), hiçbir dosya değişmez;
* yeni anahtar yanıtla BİR KEZ döner (`Cache-Control: no-store`); eski anahtar
  artık bu kurulumun kilidini açmaz, yeni anahtar açar;
* DEK ve kör indeks DEĞİŞMEZ: kayıtlar yenilemeden sonra da okunur, parola ve
  yedek anahtarı aynen çalışır;
* doğrulama damgası silinir (yeni anahtar yeniden doğrulanmalı), önceki
  `guvenlik.json` `guvenlik-arsiv-<damga>.json` olarak saklanır;
* yedekler: yenilemeden SONRA alınan yedek yeni başlığı taşır; ÖNCE alınmış yedek
  güncel güvenlik dosyası yokken yalnız eski anahtarla açılır, bu bilgisayarda
  (güncel dosya yerindeyken) yeni anahtarla da açılır — kılavuz ve
  `docs/kurulum.md` bu davranışı anlatır;
* anahtar hiçbir günlüğe düşmez; görevli kipinde 403, kilitliyken 423.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from desktop.backup import daily_backup
from desktop.backup_crypto import config_path, decrypt_bytes, embedded_recovery_metadata
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.models import Student
from apps.okul.services import app_password, backup_restore
from conftest import TEST_DEK, TEST_KURTARMA_ANAHTARI, TEST_PAROLA
from shared import crypto

URL = "/api/v1/security/recovery-key/renew/"
ANAHTAR_BICIMI = re.compile(r"^[A-Z2-7]{4}(-[A-Z2-7]{4}){7}$")

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _yenile(client: APIClient, parola: str = TEST_PAROLA) -> Any:
    return client.post(URL, {"password": parola}, format="json")


def _arsivler(dizin: Path) -> list[Path]:
    return sorted(dizin.glob(f"{app_password.STATE_ARCHIVE_PREFIX}*.json"))


def _veritabani(dizin: Path) -> Path:
    """Güvenlik dizininde küçük bir SQLite dosyası (günlük yedeğin kaynağı).

    `desktop.backup` veri dizinini kaynak dosyanın klasöründen okur; yedek anahtarı
    (`yedekleme.json`) ve kurtarma başlığı (`guvenlik.json`) orada durur.
    """
    yol = dizin / "db.sqlite3"
    baglanti = sqlite3.connect(yol)
    try:
        baglanti.execute("CREATE TABLE IF NOT EXISTS deneme (deger TEXT)")
        baglanti.execute("INSERT INTO deneme VALUES ('uydurma')")
        baglanti.commit()
    finally:
        baglanti.close()
    return yol


def _yedek_al(guvenlik_dizini: Path, yedek_dizini: Path, gun: date) -> Path:
    yedek = daily_backup(_veritabani(guvenlik_dizini), yedek_dizini, today=gun)
    assert yedek is not None
    return Path(yedek)


def _baslik(yedek: Path) -> dict[str, Any]:
    veri: dict[str, Any] = json.loads(embedded_recovery_metadata(yedek.read_bytes()))
    return veri


# ============================================================ temel akış


def test_yeni_anahtar_bir_kez_doner_ve_onbellege_alinmaz(client: APIClient) -> None:
    yanit = _yenile(client)

    assert yanit.status_code == 200
    assert yanit["Cache-Control"] == "no-store"
    govde = yanit.json()
    assert ANAHTAR_BICIMI.match(govde["recovery_key"])
    assert app_password.normalize_recovery_key(govde["recovery_key"]) != (
        app_password.normalize_recovery_key(TEST_KURTARMA_ANAHTARI)
    )
    # Yeni anahtar doğrulanana dek damga yoktur.
    assert govde["recovery_key_confirmed"] is False
    assert govde["locked"] is False


def test_yeni_anahtar_acar_eski_anahtar_acmaz(client: APIClient) -> None:
    yeni = _yenile(client).json()["recovery_key"]

    assert app_password.verify_recovery_key(yeni)
    with pytest.raises(app_password.AppPasswordError, match="Kurtarma anahtarı hatalı"):
        app_password.verify_recovery_key(TEST_KURTARMA_ANAHTARI)

    app_password.lock()
    with pytest.raises(app_password.AppPasswordError):
        app_password.unlock_with_recovery(
            recovery_key=TEST_KURTARMA_ANAHTARI, new_password="Yeni-Parola-42"
        )
    app_password.unlock_with_recovery(recovery_key=yeni, new_password="Yeni-Parola-42")
    assert crypto.is_unlocked()


def test_dek_ve_kor_indeks_degismez_kayitlar_okunur(client: APIClient) -> None:
    ogrenci = Student.objects.create(
        first_name="DENEME",
        last_name="ÖĞRENCİ",
        student_number="4711",
        class_level=9,
        class_section="A",
    )
    indeks_once = ogrenci.student_number_index
    yedek_ayari_once = config_path(app_password.state_path().parent).read_bytes()

    yeni = _yenile(client).json()["recovery_key"]

    # Kurtarma anahtarıyla yeniden açılış aynı DEK'i verir: kayıt okunur.
    app_password.lock()
    app_password.unlock_with_recovery(recovery_key=yeni, new_password="Yeni-Parola-42")
    assert crypto.active_fingerprint() == crypto.key_fingerprint(TEST_DEK)
    okunan = Student.objects.get(pk=ogrenci.pk)
    assert (okunan.first_name, okunan.last_name, okunan.student_number) == (
        "DENEME",
        "ÖĞRENCİ",
        "4711",
    )
    assert okunan.student_number_index == indeks_once
    # Yedek anahtarı (DEK'ten türer) değişmez.
    assert config_path(app_password.state_path().parent).read_bytes() == yedek_ayari_once


def test_parola_ve_kdf_bolumleri_aynen_kalir(client: APIClient) -> None:
    once = json.loads(app_password.state_path().read_text(encoding="utf-8"))
    _yenile(client)
    sonra = json.loads(app_password.state_path().read_text(encoding="utf-8"))

    assert sonra["parola"] == once["parola"]
    assert sonra["kdf"] == once["kdf"]
    assert sonra["gecis"] == once["gecis"]
    assert sonra["kurtarma"]["salt"] != once["kurtarma"]["salt"]
    assert sonra["kurtarma"]["sarmal"] != once["kurtarma"]["sarmal"]
    # Parola aynen çalışır.
    app_password.verify_password(TEST_PAROLA)


def test_damga_silinir_yeni_anahtarla_yeniden_dogrulanir(client: APIClient) -> None:
    app_password.confirm_recovery_key(TEST_KURTARMA_ANAHTARI)
    assert app_password.recovery_key_confirmed() is True

    yeni = _yenile(client).json()["recovery_key"]

    assert app_password.recovery_key_confirmed() is False
    assert client.get("/api/v1/setup/status/").json()["recovery_key_confirmed"] is False
    eski = client.post(
        "/api/v1/security/recovery-key/confirm/",
        {"recovery_key": TEST_KURTARMA_ANAHTARI},
        format="json",
    )
    assert eski.status_code == 400
    dogru = client.post(
        "/api/v1/security/recovery-key/confirm/", {"recovery_key": yeni}, format="json"
    )
    assert dogru.status_code == 200
    assert app_password.recovery_key_confirmed() is True


def test_eski_guvenlik_dosyasi_arsivlenir_silinmez(
    client: APIClient, guvenlik_ortami: Path
) -> None:
    once = app_password.state_path().read_bytes()
    assert _arsivler(guvenlik_ortami) == []

    _yenile(client)
    _yenile(client)  # aynı saniyede ikinci yenileme ilk arşivi ezmez

    arsivler = _arsivler(guvenlik_ortami)
    assert len(arsivler) == 2
    assert arsivler[0].read_bytes() == once or arsivler[1].read_bytes() == once
    # Arşiv eski anahtarı hâlâ açar (silinmedi; ele geçmiş anahtara karşı koruma değildir).
    eski_durum = json.loads(next(a for a in arsivler if a.read_bytes() == once).read_text("utf-8"))
    assert app_password._unwrap_with_recovery(eski_durum, TEST_KURTARMA_ANAHTARI) == TEST_DEK
    # Yarım dosya kalmaz.
    assert not list(guvenlik_ortami.glob("*.tmp"))


def test_kip_etkilenmez(client: APIClient) -> None:
    """DEK yeniden yüklenmez: kilit açılışı (anahtar dönemi) değişmez."""
    donem = crypto.key_epoch()
    assert KIP.durum() == "yonetici"
    _yenile(client)
    assert crypto.key_epoch() == donem
    assert KIP.durum() == "yonetici"


# ============================================================ retler


def test_yanlis_parola_reddedilir_hicbir_dosya_degismez(
    client: APIClient, guvenlik_ortami: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uyumalar: list[float] = []
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 3.0))
    monkeypatch.setattr(time, "sleep", uyumalar.append)
    once = app_password.state_path().read_bytes()

    yanit = _yenile(client, "Yanlis-Parola-9")
    _yenile(client, "Yanlis-Parola-9")

    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Parola hatalı."
    assert "recovery_key" not in yanit.json()
    assert uyumalar == [3.0]
    assert app_password.state_path().read_bytes() == once
    assert _arsivler(guvenlik_ortami) == []


def test_baska_kurulumun_dosyasiyla_yenilenemez(client: APIClient) -> None:
    """Parolası bilinen yabancı bir `guvenlik.json` ile bellekteki DEK yeniden sarmalanamaz."""
    baska = app_password._build_state(
        bytes(range(1, 33)), password="Baska-Parola-9", recovery_key=TEST_KURTARMA_ANAHTARI
    )
    baska["gecis"] = app_password.TRANSITION_DONE
    app_password._write_state(baska)

    yanit = _yenile(client, "Baska-Parola-9")
    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Parola hatalı."


def test_bos_parola_reddedilir(client: APIClient) -> None:
    assert client.post(URL, {}, format="json").status_code == 400


def test_gorevli_kipinde_kapali(client: APIClient) -> None:
    KIP.gorevliye_gec()
    yanit = _yenile(client)
    assert yanit.status_code == 403
    assert yanit.json()["code"] == "kip_yetkisiz"


def test_kilitliyken_kilit_kapisi_keser(client: APIClient, kilitli: Path) -> None:
    once = app_password.state_path().read_bytes()
    yanit = _yenile(client)
    assert yanit.status_code == 423
    assert yanit.json()["code"] == "locked"
    assert app_password.state_path().read_bytes() == once


def test_servis_kilitliyken_yenilemez(kilitli: Path) -> None:
    with pytest.raises(app_password.AppPasswordError, match="kilitli"):
        app_password.renew_recovery_key(password=TEST_PAROLA)


def test_guvenlik_dosyasi_kayipken_kapali(client: APIClient, parmak_izi_yazili: str) -> None:
    app_password.state_path().unlink()
    yanit = _yenile(client)
    assert yanit.status_code == 423
    assert yanit.json()["code"] == "guvenlik_dosyasi_kayip"


def test_parola_kurulmadan_calismaz(client: APIClient, parolasiz: Path) -> None:
    yanit = _yenile(client)
    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Yönetici parolası kurulu değil."


def test_anahtar_hicbir_gunluge_dusmez(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    yeni = _yenile(client).json()["recovery_key"]
    assert _yenile(client, "Yanlis-Parola-9").status_code == 400
    yeni2 = _yenile(client).json()["recovery_key"]

    yasak = {yeni, yeni.replace("-", ""), yeni2, yeni2.replace("-", ""), TEST_PAROLA}
    for kayit in caplog.records:
        for sir in yasak:
            assert sir not in kayit.getMessage(), kayit.name
            assert sir not in repr(kayit.args), kayit.name
    for sir in yasak:
        assert sir not in caplog.text


# ============================================================ yedekler


class TestYedekler:
    """Kılavuzdaki "eski yedekler" metninin kanıtı (kaynak `backup_restore`)."""

    @pytest.fixture
    def yedek_dizini(self, tmp_path: Path) -> Path:
        dizin = tmp_path / "yedekler"
        dizin.mkdir()
        return dizin

    def test_yenilemeden_sonra_alinan_yedek_yeni_basligi_tasir(
        self, client: APIClient, guvenlik_ortami: Path, yedek_dizini: Path
    ) -> None:
        eski_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 21))
        yeni = _yenile(client).json()["recovery_key"]
        yeni_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 22))

        eski_baslik = _baslik(eski_yedek)
        yeni_baslik = _baslik(yeni_yedek)
        # Eski yedeğin başlığı yalnız eski anahtarla, yenisininki yalnız yeni anahtarla açılır.
        assert app_password._unwrap_with_recovery(eski_baslik, TEST_KURTARMA_ANAHTARI) == TEST_DEK
        assert app_password._unwrap_with_recovery(yeni_baslik, yeni) == TEST_DEK
        with pytest.raises(app_password.AppPasswordError):
            app_password._unwrap_with_recovery(yeni_baslik, TEST_KURTARMA_ANAHTARI)
        with pytest.raises(app_password.AppPasswordError):
            app_password._unwrap_with_recovery(eski_baslik, yeni)
        # İçerik aynı DEK'le şifreli (yedek anahtarı değişmedi).
        assert decrypt_bytes(yeni_yedek.read_bytes(), TEST_DEK).startswith(b"SQLite format 3")

    def test_eski_yedek_bu_bilgisayarda_yeni_anahtarla_da_acilir(
        self, client: APIClient, guvenlik_ortami: Path, yedek_dizini: Path, tmp_path: Path
    ) -> None:
        eski_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 21))
        yeni = _yenile(client).json()["recovery_key"]

        sonuc = backup_restore.restore_database(
            eski_yedek, tmp_path / "hedef.sqlite3", recovery_key=yeni
        )
        # Güncel güvenlik dosyası kullanıldı: dosyaya dokunulmadı.
        assert sonuc.state_written is False
        assert app_password.verify_recovery_key(yeni)

    def test_eski_yedek_guvenlik_dosyasi_yokken_yalniz_eski_anahtarla_acilir(
        self, client: APIClient, guvenlik_ortami: Path, yedek_dizini: Path, tmp_path: Path
    ) -> None:
        eski_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 21))
        yeni = _yenile(client).json()["recovery_key"]
        # Başka bilgisayar / kayıp güvenlik dosyası: yalnız yedeğin gömülü başlığı kalır.
        app_password.state_path().unlink()

        with pytest.raises(backup_restore.BackupRestoreError):
            backup_restore.restore_database(
                eski_yedek, tmp_path / "hedef.sqlite3", recovery_key=yeni
            )
        sonuc = backup_restore.restore_database(
            eski_yedek, tmp_path / "hedef.sqlite3", recovery_key=TEST_KURTARMA_ANAHTARI
        )
        assert sonuc.state_written is True

    def test_yeni_yedek_guvenlik_dosyasi_yokken_yeni_anahtarla_acilir(
        self, client: APIClient, guvenlik_ortami: Path, yedek_dizini: Path, tmp_path: Path
    ) -> None:
        yeni = _yenile(client).json()["recovery_key"]
        yeni_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 22))
        app_password.state_path().unlink()

        with pytest.raises(backup_restore.BackupRestoreError):
            backup_restore.restore_database(
                yeni_yedek, tmp_path / "hedef.sqlite3", recovery_key=TEST_KURTARMA_ANAHTARI
            )
        sonuc = backup_restore.restore_database(
            yeni_yedek, tmp_path / "hedef.sqlite3", recovery_key=yeni
        )
        assert sonuc.state_written is True

    def test_eski_anahtarla_geri_yukleme_guvenlik_dosyasini_yedegin_donemine_dondurur(
        self, client: APIClient, guvenlik_ortami: Path, yedek_dizini: Path, tmp_path: Path
    ) -> None:
        """Kılavuzun uyarısı: bu bilgisayarda eski anahtarla geri yükleme yenilemeyi geri alır."""
        eski_yedek = _yedek_al(guvenlik_ortami, yedek_dizini, date(2026, 9, 21))
        yeni = _yenile(client).json()["recovery_key"]

        sonuc = backup_restore.restore_database(
            eski_yedek, tmp_path / "hedef.sqlite3", recovery_key=TEST_KURTARMA_ANAHTARI
        )

        assert sonuc.state_written is True
        assert app_password.verify_recovery_key(TEST_KURTARMA_ANAHTARI)
        with pytest.raises(app_password.AppPasswordError):
            app_password.verify_recovery_key(yeni)
