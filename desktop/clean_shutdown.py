"""Temiz kapanış işareti (tasarım T15, §4.2-6).

WAL kipinde elektrik kesintisi ya da zorla sonlandırma son işlemleri
kaybettirebilir; dolaşımda bu sessiz kayıp demektir. Program bu yüzden düzenli
çıkışta veri dizinine bir işaret yazar ve açılışta onu **okuyup siler**:

- işaret VAR → önceki oturum düzenli kapandı (`temiz`);
- işaret YOK, veritabanı VAR → önceki oturum beklenmedik biçimde kapandı
  (`beklenmedik`): günlüğe uyarı düşer, pano kartı F6'da gelir;
- işaret YOK, veritabanı YOK → ilk açılış (`ilk`): alarm verilmez.

Açılışta silinen işaret yalnız düzenli çıkışta (pencere kapandı, iki sunucu
durdu) yeniden yazılır; süreç öldürülürse eksik kalır. Açılış bir
`StartupError` ile durursa (bozuk veritabanı, WebView2 yok…) bu oturumda işlem
yapılmamıştır: önceki oturumun durumu korunur (`restore_after_failed_startup`).

Sonuç süreç içinde `KD_ONCEKI_OTURUM` ortam değişkeniyle backend'e taşınır;
okuma yardımcısı `previous_session_from_env`. Değişken Django ayarlarından
ÖNCE yazılır, çünkü backend aynı süreçte koşar.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping, MutableMapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

logger = logging.getLogger("kutuphane_defteri.kapanis")

MARKER_FILE_NAME: Final = "temiz-kapanis.json"
ENV_PREVIOUS_SESSION: Final = "KD_ONCEKI_OTURUM"

_UNEXPECTED_LOG = (
    "Önceki oturum beklenmedik biçimde kapandı (temiz kapanış işareti yok). "
    "Son oturumdaki ödünç ve iade işlemlerini kontrol edin."
)


class PreviousSession(StrEnum):
    """Önceki oturumun nasıl bittiği."""

    FIRST_RUN = "ilk"
    CLEAN = "temiz"
    UNEXPECTED = "beklenmedik"


def marker_path(data_dir: Path) -> Path:
    return data_dir / MARKER_FILE_NAME


def consume_marker(data_dir: Path, db_path: Path) -> PreviousSession:
    """Açılışta işareti okur ve SİLER; önceki oturumun durumunu döndürür.

    Tek kopya kilidi alındıktan sonra, veritabanına dokunan ilk adımdan ÖNCE
    çağrılır: göç veritabanını oluşturduktan sonra "ilk açılış" ayırt edilemezdi.
    İşaretin içeriği yalnız bilgidir; VARLIĞI yeter (bozuk içerik de temizdir,
    çünkü dosya ancak düzenli çıkışın son adımında yazılır).
    """
    marker = marker_path(data_dir)
    if marker.is_file():
        try:
            marker.unlink()
        except OSError:
            logger.warning("Temiz kapanış işareti silinemedi: %s", marker, exc_info=True)
        logger.info("Önceki oturum düzenli kapanmış.")
        return PreviousSession.CLEAN
    if not db_path.exists():
        logger.info("İlk açılış: temiz kapanış denetimi atlandı.")
        return PreviousSession.FIRST_RUN
    logger.warning("%s", _UNEXPECTED_LOG)
    return PreviousSession.UNEXPECTED


def write_marker(
    data_dir: Path,
    app_version: str,
    *,
    now: Callable[[], datetime] | None = None,
) -> Path:
    """Düzenli çıkışta işareti yazar (geçici dosya + fsync + atomik değişim)."""
    marker = marker_path(data_dir)
    stamp = (now or datetime.now)().astimezone().isoformat(timespec="seconds")
    payload = json.dumps({"surum": app_version, "zaman": stamp}, ensure_ascii=False)
    temp = marker.with_name(marker.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, marker)
    return marker


def write_marker_quietly(data_dir: Path, app_version: str) -> None:
    """`write_marker`; hata çıkışı durdurmaz (yalnız günlüğe düşer)."""
    try:
        write_marker(data_dir, app_version)
    except OSError:
        logger.warning("Temiz kapanış işareti yazılamadı.", exc_info=True)
    else:
        logger.info("Temiz kapanış işareti yazıldı.")


def restore_after_failed_startup(
    previous: PreviousSession, data_dir: Path, app_version: str
) -> None:
    """Açılış işlem yapılmadan durdu: önceki oturumun durumunu geri koyar.

    `beklenmedik` alarmı sürer (işaret yazılmaz); `temiz` ve `ilk` açılışta
    işaret yeniden yazılır, çünkü bu oturum veriye işlem yazmadı.
    """
    if previous is PreviousSession.UNEXPECTED:
        return
    write_marker_quietly(data_dir, app_version)


def publish(previous: PreviousSession, environ: MutableMapping[str, str] | None = None) -> None:
    """Durumu süreç içindeki backend'e taşır (`KD_ONCEKI_OTURUM`)."""
    (os.environ if environ is None else environ)[ENV_PREVIOUS_SESSION] = previous.value


def previous_session_from_env(environ: Mapping[str, str] | None = None) -> PreviousSession | None:
    """Backend'in okuma yardımcısı: değişken yoksa ya da tanınmıyorsa `None`.

    `None` "bilinmiyor" demektir (ör. geliştirme sunucusu, testler); pano kartı
    yalnız `beklenmedik` için gösterilir.
    """
    raw = (os.environ if environ is None else environ).get(ENV_PREVIOUS_SESSION, "")
    try:
        return PreviousSession(raw)
    except ValueError:
        return None
