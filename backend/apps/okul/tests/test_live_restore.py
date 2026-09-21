"""Çalışan program içinden geri yükleme (services.live_restore + API uçları).

Çekirdek senaryolar `test_backup_restore.py`'dedir; burada API ayağına özgü
davranışlar sınanır: yedek listesi, ad/yükleme kaynak seçimi, yol ayracı
reddi, bağlantı kapatma ve "yeniden başlat" kapısının (restart_gate) yalnız
BAŞARIDA kurulması. Çekirdek gibi bu testler de ORM'e dokunmaz (`django_db`
işareti bilinçli olarak yoktur); hedef veritabanı geçici bir dosyadır.

Veri dizini `backend/conftest.py`'nin güvenlik dizinidir (geçerli bir
`guvenlik.json` içerir; kilit kapısı böylece DB'ye sormadan geçer). Yedekler
başka bir DEK'le alınır: güncel dosya o yedeği açamaz, gömülü başlık açar ve
`guvenlik.json` olarak yazılır. Güvenlik dosyası KAYIPKEN geri yükleme
`test_app_password.py::TestGuvenlikDosyasiKayip`'tadır.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest
from desktop.backup_crypto import encrypt_bytes, private_key_from_data_key
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from rest_framework.test import APIClient

from apps.okul import restart_gate
from apps.okul.services import app_password, live_restore
from conftest import TEST_PAROLA
from shared import crypto

PAROLA = "Deneme-Parola-1"
LISTE_URL = "/api/v1/backups/"
GERI_YUKLE_URL = "/api/v1/backups/restore/"


@pytest.fixture(autouse=True)
def ortam(
    guvenlik_ortami: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Path]]:
    """Veri dizini conftest'inki; hedef veritabanı geçici dosya; kapı bayrağı temiz."""
    yedekler = app_password.backup_dir()
    yedekler.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "canli" / "db.sqlite3"
    db.parent.mkdir()
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(db))
    yield {"veri": guvenlik_ortami, "yedekler": yedekler, "db": db}


def _sqlite_baytlari(dizin: Path, isaret: str) -> bytes:
    yol = dizin / f"kaynak-{isaret}.sqlite3"
    with closing(sqlite3.connect(yol)) as baglanti:
        baglanti.execute("CREATE TABLE kayit (deger TEXT)")
        baglanti.execute("INSERT INTO kayit VALUES (?)", (isaret,))
        baglanti.commit()
    return yol.read_bytes()


def _sifreli_kapsayici(icerik: bytes) -> tuple[bytes, dict[str, Any]]:
    """Gömülü başlıklı şifreli `.kdbak`; PAROLA ile açılır."""
    dek = crypto.new_data_key()
    durum = app_password._build_state(
        dek, password=PAROLA, recovery_key=app_password.generate_recovery_key()
    )
    durum["gecis"] = app_password.TRANSITION_DONE
    baslik = json.dumps(durum, ensure_ascii=False).encode("utf-8")
    acik = private_key_from_data_key(dek).public_key()
    return cast("bytes", encrypt_bytes(icerik, acik, recovery_header=baslik)), durum


# ---------------------------------------------------------------------------
# Yedek listesi
# ---------------------------------------------------------------------------
def test_yedek_listesi_en_yeniden_eskiye(tmp_path: Path, ortam: dict[str, Path]) -> None:
    eski = ortam["yedekler"] / "gunluk-2026-08-01.kdbak"
    eski.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "eski"))[0])
    os.utime(eski, (1_000_000_000, 1_000_000_000))
    yeni = ortam["yedekler"] / "gunluk-2026-08-02.kdbak"
    yeni.write_bytes(_sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"))[0])
    os.utime(yeni, (2_000_000_000, 2_000_000_000))
    # Uzantısı farklı dosyalar listeye girmez.
    (ortam["yedekler"] / "not.txt").write_text("ilgisiz", encoding="utf-8")

    yanit = APIClient().get(LISTE_URL)

    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["backup_dir"] == str(ortam["yedekler"])
    adlar = [satir["name"] for satir in veri["backups"]]
    assert adlar == ["gunluk-2026-08-02.kdbak", "gunluk-2026-08-01.kdbak"]
    # Yedekler daima şifrelidir; "şifreli mi" alanı artık yok (§6.3-6).
    assert set(veri["backups"][0]) == {"name", "size", "modified_at"}
    assert all(satir["size"] > 0 and satir["modified_at"] for satir in veri["backups"])


def test_yedek_listesi_dizin_yokken_bos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ortam: dict[str, Path]
) -> None:
    monkeypatch.setenv(app_password.ENV_BACKUP_DIR, str(tmp_path / "yok"))

    yanit = APIClient().get(LISTE_URL)

    assert yanit.status_code == 200
    assert yanit.json()["backups"] == []


# ---------------------------------------------------------------------------
# Geri yükleme — ad ile (yedek klasöründen)
# ---------------------------------------------------------------------------
def test_addan_geri_yukleme_kapiyi_kurar(tmp_path: Path, ortam: dict[str, Path]) -> None:
    ortam["db"].write_bytes(_sqlite_baytlari(tmp_path, "eski"))
    yeni = _sqlite_baytlari(tmp_path, "yeni")
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(_sifreli_kapsayici(yeni)[0])

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": PAROLA}, format="json"
    )

    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["restart_required"] is True
    assert "encrypted" not in veri
    assert veri["old_db_name"].startswith("db-onceki-")
    assert ortam["db"].read_bytes() == yeni
    # Kapı kuruldu: bundan sonraki HER API isteği 503 restart_required döner.
    sonraki = APIClient().get(LISTE_URL)
    assert sonraki.status_code == 503
    assert sonraki.json()["code"] == "restart_required"
    # Bellekteki DEK eski veritabanına aitti; düşürüldü.
    assert crypto.is_unlocked() is False


def test_duz_sqlite_yedegi_400_ile_reddedilir(tmp_path: Path, ortam: dict[str, Path]) -> None:
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(_sqlite_baytlari(tmp_path, "duz"))

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": TEST_PAROLA}, format="json"
    )

    assert yanit.status_code == 400
    assert "şifrelenmemiş" in yanit.json()["message"]
    assert not ortam["db"].exists()
    assert restart_gate.restart_required() is False


def test_sirsiz_istek_400_ile_reddedilir(tmp_path: Path, ortam: dict[str, Path]) -> None:
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(
        _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "yeni"))[0]
    )

    yanit = APIClient().post(GERI_YUKLE_URL, {"name": "gunluk.kdbak"}, format="json")

    assert yanit.status_code == 400
    assert "yönetici parolası ya da kurtarma anahtarı" in yanit.json()["message"]


def test_yol_ayracli_ad_reddedilir(tmp_path: Path, ortam: dict[str, Path]) -> None:
    gizli = ortam["yedekler"].parent / "disarida.kdbak"
    gizli.write_bytes(_sqlite_baytlari(tmp_path, "disarida"))

    for ad in ("../disarida.kdbak", "..\\disarida.kdbak", "alt/dosya.kdbak", "duz-ad"):
        yanit = APIClient().post(GERI_YUKLE_URL, {"name": ad}, format="json")
        assert yanit.status_code == 400, ad
        assert "Geçerli bir yedek dosyası adı" in yanit.json()["message"]
    assert not ortam["db"].exists()


def test_olmayan_ad_turkce_hata_verir(ortam: dict[str, Path]) -> None:
    yanit = APIClient().post(GERI_YUKLE_URL, {"name": "yok.kdbak"}, format="json")

    assert yanit.status_code == 400
    assert "böyle bir dosya yok" in yanit.json()["message"]


# ---------------------------------------------------------------------------
# Geri yükleme — dosya yükleyerek
# ---------------------------------------------------------------------------
def test_yuklenen_sifreli_dosya_parola_ile_geri_yuklenir(
    tmp_path: Path, ortam: dict[str, Path]
) -> None:
    icerik = _sqlite_baytlari(tmp_path, "gizli")
    kapsayici, durum = _sifreli_kapsayici(icerik)

    yanit = APIClient().post(
        GERI_YUKLE_URL,
        {"file": SimpleUploadedFile("elden.kdbak", kapsayici), "password": PAROLA},
        format="multipart",
    )

    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["state_written"] is True
    assert ortam["db"].read_bytes() == icerik
    # guvenlik.json gömülü başlıktan onarıldı; geçici yükleme dosyası kalmadı.
    yazilan = json.loads((ortam["veri"] / "guvenlik.json").read_text(encoding="utf-8"))
    assert yazilan["parola"] == durum["parola"]
    assert not list(ortam["yedekler"].glob(".yukleme-*"))


def test_yanlis_parola_400_kapi_kurulmaz(tmp_path: Path, ortam: dict[str, Path]) -> None:
    orijinal = _sqlite_baytlari(tmp_path, "orijinal")
    ortam["db"].write_bytes(orijinal)
    kapsayici, _durum = _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "gizli"))
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(kapsayici)

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": "Yanlis-Parola-9"}, format="json"
    )

    assert yanit.status_code == 400
    assert "açılamadı" in yanit.json()["message"]
    assert ortam["db"].read_bytes() == orijinal
    # Kapı KURULMADI: kullanıcı yeniden deneyebilir.
    assert APIClient().get(LISTE_URL).status_code == 200
    # Başarısız denemenin geçici yükleme dosyası da kalmaz.
    assert not list(ortam["yedekler"].glob(".yukleme-*"))


# ---------------------------------------------------------------------------
# İstek doğrulama + tesisat
# ---------------------------------------------------------------------------
def test_ad_ve_dosya_birlikte_veya_hic_verilmezse_400(
    tmp_path: Path, ortam: dict[str, Path]
) -> None:
    icerik = _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "yeni"))[0]
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(icerik)

    ikisi = APIClient().post(
        GERI_YUKLE_URL,
        {"name": "gunluk.kdbak", "file": SimpleUploadedFile("elden.kdbak", icerik)},
        format="multipart",
    )
    hicbiri = APIClient().post(GERI_YUKLE_URL, {}, format="json")

    assert ikisi.status_code == 400
    assert hicbiri.status_code == 400
    assert not ortam["db"].exists()


def test_bellek_ici_veritabani_reddedilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ortam: dict[str, Path]
) -> None:
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", ":memory:")
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(
        _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "yeni"))[0]
    )

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": PAROLA}, format="json"
    )

    assert yanit.status_code == 400
    assert "dosya tabanlı değil" in yanit.json()["message"]


def test_takas_oncesi_baglantilar_kapatilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ortam: dict[str, Path]
) -> None:
    """Windows'ta açık SQLite tanıtıcısı `os.replace`'i düşürür; sıra sözleşmedir."""
    cagrildi: list[str] = []
    monkeypatch.setattr(connections, "close_all", lambda: cagrildi.append("kapat"))
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(
        _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "yeni"))[0]
    )

    sonuc = live_restore.restore_and_require_restart(name="gunluk.kdbak", password=PAROLA)

    assert cagrildi == ["kapat"]
    assert sonuc["restart_required"] is True
    assert restart_gate.restart_required() is True
