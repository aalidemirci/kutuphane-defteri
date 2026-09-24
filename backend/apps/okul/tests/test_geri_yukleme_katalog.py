"""Geri yüklemede Ağ Kataloğu (tasarım §5.3 "Geri yükleme", GA-4, UY-8).

Çalışan program içinden geri yükleme takastan ÖNCE katalogu bakım kapısına
alır (yeni istekler DB'ye dokunmadan 503; uçuştaki istekler biter; dinleyici
ve kanallar kapanır). Başarıda katalog program yeniden açılana dek kapalı
kalır; takas başarısızsa (yanlış parola) katalog eski hâline döner. Kapının
kendisi masaüstü tarafındadır (`desktop/katalog_kontrol.py`, testleri
`desktop/tests/test_katalog_kontrol.py`); burada backend'in kancayı doğru
anda çağırdığı sınanır. Test veritabanı `test_live_restore.py`'deki gibi
geçici bir dosyadır (ORM'e dokunulmaz).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.okul import masaustu_kanca
from apps.okul.services import app_password
from apps.okul.tests.test_live_restore import PAROLA, _sifreli_kapsayici, _sqlite_baytlari

GERI_YUKLE_URL = "/api/v1/backups/restore/"


class _SahteKatalog:
    """`KatalogKontrolu` yerine geçer; çağrıları ve o andaki DB içeriğini kaydeder."""

    def __init__(self, db: Path) -> None:
        self.db = db
        self.cagrilar: list[str] = []

    def bakima_al(self) -> None:
        # Takastan ÖNCE mi çağrıldı? O an DB hâlâ eski içeriği taşımalı.
        self.cagrilar.append(f"bakim:{b'eski' in self.db.read_bytes()}")

    def bakimdan_cik(self) -> None:
        self.cagrilar.append("bakimdan-cik")

    def __getattr__(self, ad: str) -> Any:  # yüzeyin geri kalanı bu testte kullanılmaz
        raise AttributeError(ad)


@pytest.fixture
def ortam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    yedekler = app_password.backup_dir()
    yedekler.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "canli" / "db.sqlite3"
    db.parent.mkdir()
    db.write_bytes(_sqlite_baytlari(tmp_path, "eski"))
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(db))
    katalog = _SahteKatalog(db)
    masaustu_kanca._reset_for_tests()
    masaustu_kanca.kaydet(katalog=katalog)
    yield {"yedekler": yedekler, "db": db, "katalog": katalog}
    masaustu_kanca._reset_for_tests()


def test_geri_yukleme_katalogu_takastan_once_bakima_alir_ve_kapali_birakir(
    tmp_path: Path, ortam: dict[str, Any]
) -> None:
    yeni = _sqlite_baytlari(tmp_path, "yeni")
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(_sifreli_kapsayici(yeni)[0])

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": PAROLA}, format="json"
    )

    assert yanit.status_code == 200
    assert ortam["db"].read_bytes() == yeni
    # Bakım kapısı takastan önce (DB eskiyken) kuruldu; başarıda kaldırılmadı.
    assert ortam["katalog"].cagrilar == ["bakim:True"]


def test_basarisiz_geri_yuklemede_katalog_eski_haline_doner(
    tmp_path: Path, ortam: dict[str, Any]
) -> None:
    (ortam["yedekler"] / "gunluk.kdbak").write_bytes(
        _sifreli_kapsayici(_sqlite_baytlari(tmp_path, "yeni"))[0]
    )

    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "gunluk.kdbak", "password": "yanlis-parola"}, format="json"
    )

    assert yanit.status_code == 400
    assert b"eski" in ortam["db"].read_bytes()  # hedefe dokunulmadı
    assert ortam["katalog"].cagrilar == ["bakim:True", "bakimdan-cik"]


def test_yedek_adi_gecersizse_katalog_hic_bakima_alinmaz(ortam: dict[str, Any]) -> None:
    """Ad doğrulaması kapıdan önce: yanlış tıklama katalogu kapatmaz."""
    yanit = APIClient().post(
        GERI_YUKLE_URL, {"name": "../disari.kdbak", "password": PAROLA}, format="json"
    )

    assert yanit.status_code == 400
    assert ortam["katalog"].cagrilar == []
