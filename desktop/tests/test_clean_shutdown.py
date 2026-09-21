"""Temiz kapanış işareti testleri (tasarım T15, §4.2-6)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from desktop.clean_shutdown import (
    ENV_PREVIOUS_SESSION,
    MARKER_FILE_NAME,
    PreviousSession,
    consume_marker,
    marker_path,
    previous_session_from_env,
    publish,
    restore_after_failed_startup,
    write_marker,
    write_marker_quietly,
)


def _veri(tmp_path: Path, *, db: bool) -> tuple[Path, Path]:
    veri = tmp_path / "data"
    veri.mkdir()
    db_yolu = veri / "db.sqlite3"
    if db:
        db_yolu.write_bytes(b"SQLite format 3\x00")
    return veri, db_yolu


def test_duzenli_cikis_isareti_yazar(tmp_path: Path) -> None:
    veri, _ = _veri(tmp_path, db=True)
    sabit = datetime(2026, 9, 21, 16, 30, tzinfo=UTC)

    yol = write_marker(veri, "2026.9.0", now=lambda: sabit)

    assert yol == veri / MARKER_FILE_NAME
    icerik = json.loads(yol.read_text(encoding="utf-8"))
    assert icerik["surum"] == "2026.9.0"
    assert icerik["zaman"].startswith("2026-09-21")
    assert not (veri / (MARKER_FILE_NAME + ".tmp")).exists()


def test_isaret_varsa_temiz_ve_acilista_silinir(tmp_path: Path) -> None:
    veri, db_yolu = _veri(tmp_path, db=True)
    write_marker(veri, "2026.9.0")

    assert consume_marker(veri, db_yolu) is PreviousSession.CLEAN
    # Silindi: bu oturum zorla sonlandırılırsa sonraki açılış alarm verir.
    assert not marker_path(veri).exists()
    assert consume_marker(veri, db_yolu) is PreviousSession.UNEXPECTED


def test_isaret_yokken_beklenmedik_kapanma_bilgisi_uretir(
    tmp_path: Path, kd_gunlugu: list[logging.LogRecord]
) -> None:
    veri, db_yolu = _veri(tmp_path, db=True)

    sonuc = consume_marker(veri, db_yolu)

    assert sonuc is PreviousSession.UNEXPECTED
    uyarilar = [k.getMessage() for k in kd_gunlugu if k.levelno >= logging.WARNING]
    assert len(uyarilar) == 1
    assert "beklenmedik" in uyarilar[0]
    assert "ödünç ve iade" in uyarilar[0]


def test_ilk_kurulumda_yanlis_alarm_vermez(
    tmp_path: Path, kd_gunlugu: list[logging.LogRecord]
) -> None:
    veri, db_yolu = _veri(tmp_path, db=False)

    sonuc = consume_marker(veri, db_yolu)

    assert sonuc is PreviousSession.FIRST_RUN
    assert [k for k in kd_gunlugu if k.levelno >= logging.WARNING] == []


def test_bozuk_icerikli_isaret_de_temizdir(tmp_path: Path) -> None:
    """Dosya yalnız düzenli çıkışın son adımında yazılır: varlığı yeter."""
    veri, db_yolu = _veri(tmp_path, db=True)
    marker_path(veri).write_bytes(b"\x00bozuk")

    assert consume_marker(veri, db_yolu) is PreviousSession.CLEAN


def test_isaret_eskisinin_uzerine_atomik_yazilir(tmp_path: Path) -> None:
    veri, _ = _veri(tmp_path, db=True)
    write_marker(veri, "2026.9.0")
    write_marker(veri, "2026.9.1")

    assert json.loads(marker_path(veri).read_text(encoding="utf-8"))["surum"] == "2026.9.1"


def test_yazma_hatasi_cikisi_durdurmaz(tmp_path: Path, kd_gunlugu: list[logging.LogRecord]) -> None:
    yok = tmp_path / "olmayan" / "dizin"

    write_marker_quietly(yok, "2026.9.0")

    assert any("yazılamadı" in k.getMessage() for k in kd_gunlugu)
    assert not marker_path(yok).exists()


@pytest.mark.parametrize(
    ("onceki", "isaret_yazilir"),
    [
        (PreviousSession.CLEAN, True),
        (PreviousSession.FIRST_RUN, True),
        (PreviousSession.UNEXPECTED, False),
    ],
)
def test_acilis_hatasinda_onceki_durum_korunur(
    tmp_path: Path, onceki: PreviousSession, isaret_yazilir: bool
) -> None:
    veri, _ = _veri(tmp_path, db=True)

    restore_after_failed_startup(onceki, veri, "2026.9.0")

    assert marker_path(veri).exists() is isaret_yazilir


def test_durum_ortam_degiskeniyle_backende_tasinir() -> None:
    ortam: dict[str, str] = {}

    publish(PreviousSession.UNEXPECTED, ortam)

    assert ortam == {ENV_PREVIOUS_SESSION: "beklenmedik"}
    assert ENV_PREVIOUS_SESSION == "KD_ONCEKI_OTURUM"
    assert previous_session_from_env(ortam) is PreviousSession.UNEXPECTED


def test_ortam_degiskeni_yoksa_ya_da_tanimsizsa_bilinmiyor() -> None:
    assert previous_session_from_env({}) is None
    assert previous_session_from_env({ENV_PREVIOUS_SESSION: "başka"}) is None
    assert previous_session_from_env({ENV_PREVIOUS_SESSION: "temiz"}) is PreviousSession.CLEAN
