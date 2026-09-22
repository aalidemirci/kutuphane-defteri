"""Backend test altyapısı — varsayılan güvenlik ortamı (F1, sözleşme §3).

Yönetici parolası zorunludur ve şifreli alan anahtarsız yazmaz (fail-closed,
tasarım §6.3). Bu yüzden her test, gerçek programın olağan çalışma hâlinde
başlar: **parola kurulu + kilit açık**.

OTOMATİK FİXTÜR `guvenlik_ortami` (her teste uygulanır, DB İSTEMEZ):

* Ucuz Argon2 profili (`crypto.DEFAULT_KDF` = t=1, 8 KiB, p=1). Yalnız maliyet
  parametresidir; algoritma, zarf yapısı ve dosya biçimi üretimdekiyle aynıdır.
* Geçici `KD_SECURITY_DIR` (güvenlik dosyası + `yedekleme.json`) ve
  `KD_BACKUP_DIR`; testin kendi `tmp_path`'inden AYRI dizinlerdir.
* Sabit test DEK'i (`TEST_DEK`) için GEÇERLİ bir `guvenlik.json` (gecis=TAMAM;
  parola `TEST_PAROLA`, kurtarma anahtarı `TEST_KURTARMA_ANAHTARI`) ve buna
  eşlik eden `yedekleme.json` (yedek açık anahtarı).
* Anahtar yüklüdür (`crypto.load_key(TEST_DEK)`); test sonunda düşürülür.
* Kademeli yanlış parola gecikmesi sıfırlanır ve `FAILURE_DELAYS=(0.0,)`
  (gerçek `sleep` yok; davranışı ayrı test kendisi kurar).
* "Yeniden başlat" kapısı (`restart_gate`) sıfırlanır.

DB'deki parmak izi (`SchoolConfig.app_password_hash`) bu fixtürce YAZILMAZ
(DB istemez): varsayılan ortam "dosya var, parmak izi boş" hâlidir. İlk kilit
açılışı parmak izini `resume_pending` ile yazar. Parmak izine dayanan testler
`parmak_izi_yazili` fixtürünü ister (DB gerekir).

EK FİXTÜRLER (testin istemesi gerekir):

* `parolasiz` — güvenlik dosyası ve `yedekleme.json` YOK, anahtar YOK: parola hiç
  kurulmamış ilk açılış ("kurulum" durumu). Kişi yazan uçlar 409 döner,
  `Student.save()` `KeyMissingError` yükseltir.
* `kilitli` — güvenlik dosyası VAR, anahtar YOK (program kilitli). Açmak için
  `app_password.unlock(password=TEST_PAROLA)`.
* `parmak_izi_yazili` — DB'ye `TEST_DEK`'in parmak izini yazar (DB gerekir);
  "güvenlik dosyası kayıp" senaryosu bunun üstüne dosyayı siler.

Kip durumu (B kolu, `apps/okul/kip.py`) da her testte sıfırlanır; sıfırlayıcı
`_kip_sifirla` içinde tek satırdır.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# Sabit test veri anahtarı (32 bayt). Gerçek bir sır DEĞİLDİR; yalnız testlerde.
TEST_DEK = bytes(range(32))
TEST_PAROLA = "Test-Yonetici-Parolasi-1"
TEST_KURTARMA_ANAHTARI = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM"

_UCUZ_KDF: dict[str, int] = {"time_cost": 1, "memory_cost": 8, "parallelism": 1}

# Durum dosyası içeriği oturum boyunca bir kez üretilir (Argon2 ucuz olsa da
# her teste tuz/sarmal üretmek gereksiz). Yalnız okunur; her test kendi
# dizinine yazar.
_durum_onbellegi: dict[str, Any] = {}


def _test_durumu() -> dict[str, Any]:
    """`TEST_DEK`'i `TEST_PAROLA` ve `TEST_KURTARMA_ANAHTARI` ile sarmalayan durum."""
    if not _durum_onbellegi:
        from apps.okul.services import app_password
        from shared import crypto

        onceki = crypto.DEFAULT_KDF
        crypto.DEFAULT_KDF = crypto.KdfParams.from_dict(_UCUZ_KDF)
        try:
            durum = app_password._build_state(
                TEST_DEK, password=TEST_PAROLA, recovery_key=TEST_KURTARMA_ANAHTARI
            )
        finally:
            crypto.DEFAULT_KDF = onceki
        durum["gecis"] = app_password.TRANSITION_DONE
        _durum_onbellegi.update(durum)
    kopya: dict[str, Any] = json.loads(json.dumps(_durum_onbellegi))  # derin kopya
    return kopya


def _kip_sifirla() -> None:
    """Kip durumunu (B kolu) sıfırlar; modül henüz yoksa sessizce geçer."""
    try:
        from apps.okul import kip
    except ImportError:
        return
    sifirla = getattr(getattr(kip, "KIP", None), "_reset_for_tests", None) or getattr(
        kip, "_reset_for_tests", None
    )
    if callable(sifirla):
        sifirla()


@pytest.fixture(autouse=True)
def guvenlik_ortami(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Varsayılan test ortamı: parola kurulu + kilit açık (modül başlığına bakın).

    Güvenlik dizininin yolunu döndürür (`guvenlik.json` ve `yedekleme.json` orada).
    """
    from desktop.backup_crypto import ensure_public_config

    from apps.okul import restart_gate
    from apps.okul.services import app_password
    from shared import crypto

    guvenlik_dizini = tmp_path_factory.mktemp("kd-guvenlik")
    yedek_dizini = tmp_path_factory.mktemp("kd-yedek")
    monkeypatch.setenv(app_password.ENV_SECURITY_DIR, str(guvenlik_dizini))
    monkeypatch.setenv(app_password.ENV_BACKUP_DIR, str(yedek_dizini))
    monkeypatch.setattr(crypto, "DEFAULT_KDF", crypto.KdfParams.from_dict(_UCUZ_KDF))
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0,))

    (guvenlik_dizini / app_password.STATE_FILE_NAME).write_text(
        json.dumps(_test_durumu(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ensure_public_config(guvenlik_dizini, TEST_DEK, replace=True)
    app_password._reset_failures()
    restart_gate._reset_for_tests()
    _kip_sifirla()
    crypto.load_key(TEST_DEK)
    yield guvenlik_dizini
    crypto.unload_key()
    app_password._reset_failures()
    restart_gate._reset_for_tests()
    _kip_sifirla()


@pytest.fixture
def parolasiz(guvenlik_ortami: Path) -> Path:
    """Parola hiç kurulmamış ilk açılış: güvenlik dosyası ve yedek anahtarı yok, anahtar yok."""
    from desktop.backup_crypto import config_path

    from apps.okul.services import app_password
    from shared import crypto

    crypto.unload_key()
    app_password.state_path().unlink(missing_ok=True)
    config_path(guvenlik_ortami).unlink(missing_ok=True)
    return guvenlik_ortami


@pytest.fixture
def kilitli(guvenlik_ortami: Path) -> Path:
    """Program kilitli: güvenlik dosyası var, anahtar bellekte değil."""
    from shared import crypto

    crypto.unload_key()
    return guvenlik_ortami


@pytest.fixture
def parmak_izi_yazili(guvenlik_ortami: Path, db: None) -> str:
    """DB'ye `TEST_DEK`'in parmak izini yazar; parmak izini döndürür."""
    from apps.okul.models import SchoolConfig
    from shared import crypto

    parmak = crypto.key_fingerprint(TEST_DEK)
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.app_password_hash = parmak
    config.save(update_fields=["app_password_hash", "updated_at"])
    return parmak
