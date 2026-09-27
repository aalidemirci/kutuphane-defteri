"""Saklama tetiğinin yedek kuralları (F11 — tasarım §6.4 "Çalışma biçimi" ve "Yedeklerdeki kalıntı").

- `pre-anonim-<tarih>-<saat>.kdbak` tetikten ÖNCE alınır, şifrelidir ve rotasyonda
  günlük yedekler gibi **14 gün** tutulur; aynı gün ikinci tetik ayrı dosya alır.
- Tetik, tetik anından ESKİ `pre-migrate` yedeklerini siler (yazılma zamanına göre);
  sonra alınanlar ve başka önekli dosyalar kalır.
- Anahtar yoksa yedek alınmaz (`None`) — çağıran tetiği çalıştırmaz.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from desktop.backup import (
    PRE_ANONIM_PREFIX,
    pre_anonim_backup,
    pre_migrate_before,
    remove_pre_migrate_before,
    remove_pre_migrate_named,
    rotate_backups,
)
from desktop.backup_crypto import MAGIC
from desktop.tests.test_backup import _db_olustur


def test_pre_anonim_yedegi_sifreli_ve_saatli(tmp_path: Path) -> None:
    db = tmp_path / "veri" / "db.sqlite3"
    _db_olustur(db)
    dizin = tmp_path / "yedekler"

    birinci = pre_anonim_backup(db, dizin, now=datetime(2028, 9, 24, 10, 15, 30))
    ikinci = pre_anonim_backup(db, dizin, now=datetime(2028, 9, 24, 10, 15, 30))

    assert birinci is not None and ikinci is not None
    assert birinci.name == f"{PRE_ANONIM_PREFIX}-2028-09-24-101530.kdbak"
    assert ikinci != birinci and ikinci.name.startswith(f"{PRE_ANONIM_PREFIX}-2028-09-24-")
    assert birinci.read_bytes()[: len(MAGIC)] == MAGIC


def test_anahtar_yoksa_pre_anonim_yedegi_alinmaz(tmp_path: Path) -> None:
    db = tmp_path / "veri" / "db.sqlite3"
    _db_olustur(db, parola_kurulu=False)
    assert pre_anonim_backup(db, tmp_path / "yedekler") is None
    assert not list((tmp_path / "yedekler").glob("*"))


def test_anahtar_dizini_ayri_verilebilir(tmp_path: Path) -> None:
    """Çalışan programın backend'i güvenlik dizinini ayrıca verir (`data_dir`)."""
    anahtarlar = tmp_path / "anahtar"
    _db_olustur(anahtarlar / "db.sqlite3")
    db = tmp_path / "baska" / "db.sqlite3"
    _db_olustur(db, parola_kurulu=False)
    assert pre_anonim_backup(db, tmp_path / "yedekler", data_dir=anahtarlar) is not None


def test_pre_anonim_rotasyonda_on_dort_gun(tmp_path: Path) -> None:
    for ad in (
        "pre-anonim-2026-09-01-090000.kdbak",
        "pre-anonim-2026-09-20-090000.kdbak",
        "gunluk-2026-09-01.kdbak",
        "elle-konmus-pre-anonim.kdbak",
    ):
        (tmp_path / ad).write_bytes(b"x")

    silinen = rotate_backups(tmp_path, today=date(2026, 9, 27))

    assert sorted(p.name for p in silinen) == [
        "gunluk-2026-09-01.kdbak",
        "pre-anonim-2026-09-01-090000.kdbak",
    ]
    assert (tmp_path / "pre-anonim-2026-09-20-090000.kdbak").exists()
    assert (tmp_path / "elle-konmus-pre-anonim.kdbak").exists()


def test_tetik_anindan_eski_pre_migrate_silinir(tmp_path: Path) -> None:
    an = datetime(2028, 9, 24, 12, 0, 0)
    eski = tmp_path / "pre-migrate-2026.9.0-2026-09-01.kdbak"
    ayni_gun_sonra = tmp_path / "pre-migrate-2028.9.0-2028-09-24.kdbak"
    gunluk = tmp_path / "gunluk-2026-09-01.kdbak"
    for yol in (eski, ayni_gun_sonra, gunluk):
        yol.write_bytes(b"x")
    os.utime(eski, (an.timestamp() - 86400, an.timestamp() - 86400))
    os.utime(ayni_gun_sonra, (an.timestamp() + 60, an.timestamp() + 60))
    os.utime(gunluk, (an.timestamp() - 86400, an.timestamp() - 86400))

    silinen = remove_pre_migrate_before(tmp_path, an)

    assert silinen == [eski]
    assert ayni_gun_sonra.exists() and gunluk.exists()
    assert remove_pre_migrate_before(tmp_path / "yok", an) == []


def test_ada_gore_silme_yalniz_pre_migrate_adlarina_dokunur(tmp_path: Path) -> None:
    """F11 düzeltme turu: gün değişimi kapısı silinemeyenleri ADIYLA yeniden dener.

    Dosya zamanına bakılmaz; yol ayırıcısı taşıyan ya da `pre-migrate-*.kdbak` biçiminde
    olmayan ada dokunulmaz; klasörde olmayan ad beklemede kalmaz.
    """
    hedef = tmp_path / "pre-migrate-2026.9.0-2026-09-01.kdbak"
    gunluk = tmp_path / "gunluk-2026-09-01.kdbak"
    for yol in (hedef, gunluk):
        yol.write_bytes(b"x")
    ust = tmp_path.parent / "pre-migrate-disarida.kdbak"
    ust.write_bytes(b"x")

    silinen, kalan = remove_pre_migrate_named(
        tmp_path,
        [
            hedef.name,
            gunluk.name,
            "../pre-migrate-disarida.kdbak",
            "pre-migrate-olmayan.kdbak",
        ],
    )

    assert silinen == [hedef] and kalan == []
    assert gunluk.exists() and ust.exists()
    ust.unlink()


def test_pre_migrate_before_silmez_yalniz_listeler(tmp_path: Path) -> None:
    an = datetime(2028, 9, 24, 12, 0, 0)
    eski = tmp_path / "pre-migrate-2026.9.0-2026-09-01.kdbak"
    eski.write_bytes(b"x")
    os.utime(eski, (an.timestamp() - 60, an.timestamp() - 60))

    assert pre_migrate_before(tmp_path, an) == [eski]
    assert eski.exists()
