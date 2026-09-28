"""Eski program yeni veriyi AÇMAZ (tasarım §4.2; F11 kod kapısı) — uçtan uca.

İki hat:

1. **Sürüm damgası** (`data/surum.json`): her başarılı göçten sonra yazılır; damgadaki
   sürüm çalışan programdan yeniyse açılış 4 koduyla (`SchemaTooNewError`) durur —
   bütünlük denetiminden, yedekten ve göçten ÖNCE; damga ezilmez.
2. **Veritabanının göç kaydı**: damga yoksa (geri yükleme onu siler) programın
   tanımadığı uygulanmış göç aynı kodla durdurur. Geri yükleme yolunun kendisi
   `test_geri_yukleme_provasi.py::test_yeni_surumun_yedegi_eski_programda_acilmaz`'dadır.

Uçtan uca testler GERÇEK süreçtir (`python -m desktop.main --autotest`); birim testleri
iletiyi ve yanlış alarm vermeyen kuralları sabitler.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from desktop.errors import EXIT_OK, EXIT_SCHEMA_TOO_NEW, SchemaTooNewError
from desktop.tests.alt_surec import gunluk, program
from desktop.version import ensure_no_unknown_migrations

# ------------------------------------------------------------------ birim


def test_taninmayan_goc_yoksa_gecer() -> None:
    ensure_no_unknown_migrations([], "2026.9.0")


def test_taninmayan_goc_acilisi_durdurur_ve_iletisi_turkcedir(
    kd_gunlugu: list[logging.LogRecord],
) -> None:
    """27.09.2026 ana oturum kararı: göç adları kullanıcı iletisine GİRMEZ (sözlük §2 iç
    kimlikler; "Eski program, yeni veri" satırı — kullanıcı metninde göç/migration geçmez),
    yalnız günlüğe yazılır; ileti sade Türkçedir ve günlük dosyasını anar."""
    with pytest.raises(SchemaTooNewError) as hata:
        ensure_no_unknown_migrations(["okul.9999_gelecek_surum"], "2026.9.0")

    assert hata.value.exit_code == EXIT_SCHEMA_TOO_NEW
    assert hata.value.title == "Program sürümü eski"
    metin = hata.value.full_message
    assert "daha yeni bir sürümüyle" in metin
    assert "2026.9.0" in metin
    assert "tanımadığı değişiklikler var." in metin
    assert "güncel sürüme yükseltip" in metin
    assert "yedeği eski programa geri yükleyince" in metin
    assert "logs/uygulama.log" in metin
    assert "9999_gelecek_surum" not in metin
    assert not re.search(r"migration|göç|şema", metin, flags=re.IGNORECASE)

    gunluk = " ".join(kayit.getMessage() for kayit in kd_gunlugu)
    assert "okul.9999_gelecek_surum" in gunluk
    assert "2026.9.0" in gunluk


def test_cok_sayida_taninmayan_goc_iletiyi_tasirmaz_gunluge_hepsi_yazilir(
    kd_gunlugu: list[logging.LogRecord],
) -> None:
    adlar = [f"kutuphane.{9000 + i}_gelecek" for i in range(12)]
    with pytest.raises(SchemaTooNewError) as hata:
        ensure_no_unknown_migrations(adlar, "2026.9.0")

    assert not any(ad in hata.value.full_message for ad in adlar)
    gunluk = " ".join(kayit.getMessage() for kayit in kd_gunlugu)
    assert all(ad in gunluk for ad in adlar)
    assert "12 göç" in gunluk


# ------------------------------------------------------------------ uçtan uca


def _acilis(kok: Path, surum: str | None = None) -> int:
    ortam = {"KD_APP_VERSION": surum} if surum else None
    return program("--autotest", "--data-dir", str(kok), ortam=ortam).returncode


@pytest.mark.slow
def test_yeni_surumun_damgasi_eski_programi_durdurur(tmp_path: Path) -> None:
    assert _acilis(tmp_path, "2099.1.0") == EXIT_OK
    damga = tmp_path / "data" / "surum.json"
    assert json.loads(damga.read_text(encoding="utf-8"))["app_version"] == "2099.1.0"
    once = damga.read_bytes()

    kod = _acilis(tmp_path, "2026.9.0")

    assert kod == EXIT_SCHEMA_TOO_NEW
    kayit = gunluk(tmp_path)
    assert "Program sürümü eski" in kayit
    assert "daha yeni bir sürümüyle (2099.1.0)" in kayit
    assert damga.read_bytes() == once, "eski program damgayı ezdi"
    assert not list((tmp_path / "backups").glob("pre-migrate-*"))


@pytest.mark.slow
def test_damga_yokken_yeni_sema_eski_programi_durdurur(tmp_path: Path) -> None:
    """Geri yüklemenin bıraktığı hâl: damga yok, veritabanı daha yeni bir sürümün."""
    assert _acilis(tmp_path) == EXIT_OK
    db = tmp_path / "data" / "db.sqlite3"
    with closing(sqlite3.connect(db)) as baglanti:
        baglanti.execute(
            "INSERT INTO django_migrations (app, name, applied) "
            "VALUES ('okul', '9999_gelecek_surum', '2099-01-01 00:00:00')"
        )
        baglanti.commit()
    (tmp_path / "data" / "surum.json").unlink()

    assert _acilis(tmp_path) == EXIT_SCHEMA_TOO_NEW
    kayit = gunluk(tmp_path)
    assert "tanımadığı değişiklikler" in kayit
    assert "okul.9999_gelecek_surum" in kayit
    assert not (tmp_path / "data" / "surum.json").exists()

    # Kapı kalıcı değildir: veri programla uyumlu hâle gelince açılış sürer.
    with closing(sqlite3.connect(db)) as baglanti:
        baglanti.execute("DELETE FROM django_migrations WHERE name = '9999_gelecek_surum'")
        baglanti.commit()
    assert _acilis(tmp_path) == EXIT_OK
    assert (tmp_path / "data" / "surum.json").is_file()


@pytest.mark.slow
def test_programin_tanimadigi_uygulamanin_eski_kaydi_alarm_vermez(
    tmp_path: Path,
) -> None:
    """Yanlış alarm yok: kaldırılmış bir uygulamanın göç kaydı eski programı durdurmaz."""
    assert _acilis(tmp_path) == EXIT_OK
    db = tmp_path / "data" / "db.sqlite3"
    with closing(sqlite3.connect(db)) as baglanti:
        baglanti.execute(
            "INSERT INTO django_migrations (app, name, applied) "
            "VALUES ('kaldirilmis_uygulama', '0001_initial', '2026-01-01 00:00:00')"
        )
        baglanti.commit()
    (tmp_path / "data" / "surum.json").unlink()

    assert _acilis(tmp_path) == EXIT_OK
