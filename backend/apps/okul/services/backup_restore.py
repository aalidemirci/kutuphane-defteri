"""Yedekten geri yükleme — yalnız şifreli `.kdbak` (tasarım §4.3, §6.3).

Yönetici parolası zorunludur ve bütün yedekler X25519 + AES-256-GCM
kapsayıcısıdır; KS'deki düz SQLite yedek dalı F1'de söküldü (§6.3-6). Düz bir
SQLite dosyası "yedek" olarak verilirse açık bir Türkçe hatayla reddedilir:
şifresiz bir kopyayı geri yüklemek, kişi alanları düz metin olan ve parmak
izi taşımayan bir veritabanı getirirdi. Bu çekirdek üç giriş kapısından
çağrılır:

    * son kullanıcı: `kutuphane-defteri --geri-yukle` (desktop/restore.py)
    * çalışan program: Güvenlik sekmesi (`live_restore`, `POST backups/restore/`)
    * destek/geliştirme: `python manage.py restore_backup`

VERİTABANINA HİÇ DOKUNULMAZ: geri yüklemenin varlık sebebi bozuk bir
db.sqlite3'tür; bu modülde ORM importu ve sorgusu yoktur. Django'dan yalnız
ayarlar (`settings.DATA_DIR`, `app_password` yol çözümü üzerinden) ve saat
dilimi kullanılır.

DEK NEREDEN GELİR: şifreli kapsayıcının başlığına, yedek alınırken geçerli
olan `guvenlik.json` gömülüdür (`backup_crypto.recovery_metadata`). Çözerken
İKİ aday durum dosyası sırayla denenir:

    1. Veri dizinindeki GÜNCEL guvenlik.json — parola yedekten sonra
       değiştiyse kullanıcının bildiği parola bu dosyayı açar (DEK parola
       değişiminde DEĞİŞMEZ, yalnız sarmal yenilenir).
    2. Yedeğe GÖMÜLÜ başlık — güncel dosya kayıpsa ya da başka kuruluma
       aitse yedek kendini tarif eder (o dönemki parola veya kurtarma
       anahtarı ile açılır).

AES-GCM kimlik doğrulaması nihai hakemdir: yanlış DEK açık hata verir,
sessizce bozuk çıktı üretilemez.

GÜVENLİK DOSYASI KAYIP KİLİDİNDEN ÇIKIŞ (GA-2): güncel `guvenlik.json` yoksa
aday listesinde yalnız gömülü başlık kalır; çözüm onunla başarılırsa başlık
`guvenlik.json` olarak YAZILIR (`_ensure_state_file`). Böylece geri yüklemeden
çıkan (veritabanı, durum dosyası) çifti aynı DEK'i anlatır ve program yeniden
açıldığında olağan kilit ekranına döner.

KVKK: çözülen içerik diske YALNIZ hedef veritabanı dosyası olarak yazılır
(aynı dizinde .tmp → atomik yer değiştirme; hata hâlinde .tmp silinir).
Ayrı bir düz kopya bırakılmaz. Mevcut (bozuk) veritabanı da SİLİNMEZ:
`db-onceki-<damga>.sqlite3` adıyla kenara alınır — veri kurtarma denemesi
için tek nüsha oydu.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from desktop.backup_crypto import (
    MAGIC,
    BackupCryptoError,
    decrypt_bytes,
    embedded_recovery_metadata,
    ensure_public_config,
    is_usable_security_state,
    parse_security_state,
)
from desktop.paths import VERSION_STAMP_FILE_NAME
from django.utils import timezone

from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.restore")

SQLITE_MAGIC = b"SQLite format 3\x00"
# Kenara alınan eski veritabanının ad öneki (integrity ipucu bu adı anar).
OLD_DB_PREFIX = "db-onceki"

_SOURCE_CURRENT = "guncel"
_SOURCE_EMBEDDED = "gomulu"


class BackupRestoreError(ValueError):
    """Kullanıcıya gösterilecek Türkçe geri yükleme hatası."""


@dataclass(frozen=True)
class BackupInfo:
    """`.kdbak` kapsayıcısının gömülü kurtarma başlığı (varsa)."""

    embedded_state: dict[str, Any] | None = None
    embedded_raw: bytes = field(default=b"", repr=False)


@dataclass(frozen=True)
class RestoreResult:
    db_path: Path
    # Kenara alınan önceki veritabanı (hedef yoksa None).
    old_db_path: Path | None
    # guvenlik.json gömülü başlıktan (yeniden) yazıldı mı?
    state_written: bool


def inspect_backup(container: bytes) -> BackupInfo:
    """Dosyanın şifreli yedek kapsayıcısı olduğunu doğrular, gömülü başlığı çıkarır."""
    if container.startswith(MAGIC):
        try:
            ham = embedded_recovery_metadata(container)
        except BackupCryptoError as exc:
            raise BackupRestoreError(str(exc)) from exc
        return BackupInfo(embedded_state=_parse_state(ham), embedded_raw=ham)
    # Kullanıcı metni: dosya uzantısı ve kapsayıcı gibi teknik adlar geçmez
    # (docs/sozluk.md "Yedek" satırı — teknik adlar yalnız Hakkında sayfasında).
    if container.startswith(SQLITE_MAGIC):
        raise BackupRestoreError(
            "Bu dosya şifrelenmemiş bir veritabanı kopyası. Kütüphane Defteri yalnız "
            "kendi şifreli yedeklerini geri yükler."
        )
    raise BackupRestoreError(
        "Dosya geçerli bir Kütüphane Defteri yedeği değil (şifreli yedek dosyası bekleniyordu)."
    )


def restore_database(
    backup_path: Path,
    db_path: Path,
    *,
    password: str | None = None,
    recovery_key: str | None = None,
) -> RestoreResult:
    """Yedeği hedef veritabanının yerine koyar; eski dosyayı KENARA ALIR (silmez)."""
    parola = password or None
    anahtar = recovery_key or None
    try:
        container = backup_path.read_bytes()
    except OSError as exc:
        raise BackupRestoreError(f"Yedek dosyası okunamadı: {backup_path}") from exc

    info = inspect_backup(container)
    if not parola and not anahtar:
        raise BackupRestoreError(
            "Bu yedek şifreli; açmak için yönetici parolası ya da kurtarma anahtarı gerekli."
        )
    icerik, kaynak, dek = _decrypt_container(container, info, password=parola, recovery_key=anahtar)
    if not icerik.startswith(SQLITE_MAGIC):
        raise BackupRestoreError(
            "Yedek çözüldü ama içeriği SQLite veritabanı çıkmadı; dosya bozulmuş olabilir."
        )

    eski = _swap_database_files(db_path, icerik)
    yazildi = _ensure_state_file(info, kaynak)
    # KARDEŞ DOSYA da eşitlenir (birleşme incelemesi bulgusu): yedekleme.json
    # bayat kalırsa (a) `_adopt_key` her kilit açılışında "anahtar eşleşmiyor"
    # hatası verir; (b) daha kötüsü, açılıştaki günlük yedek İÇERİĞİ eski açık
    # anahtarla mühürleyip başlığına yeni guvenlik.json'ı gömer — o yedek
    # hiçbir adayla açılamaz ve rotasyon sağlam eskileri süpürür. replace=True
    # güvenli: DEK az önce AES-GCM doğrulamasıyla bu veriye ait olduğunu kanıtladı.
    ensure_public_config(app_password.state_path().parent, dek, replace=True)
    # Sürüm damgası artık geri yüklenen veriyi tarif etmiyor (yedeğin hangi
    # sürümle yazıldığı bilinmez). Eksik damga açılışa engel DEĞİLDİR
    # (desktop/version.py); ilk başarılı migrate damgayı yeniden yazar.
    (db_path.parent / VERSION_STAMP_FILE_NAME).unlink(missing_ok=True)
    logger.info("Yedekten geri yükleme tamamlandı: %s.", backup_path.name)
    return RestoreResult(
        db_path=db_path,
        old_db_path=eski,
        state_written=yazildi,
    )


# ---------------------------------------------------------------------------
# İç yardımcılar
# ---------------------------------------------------------------------------
def _parse_state(raw: bytes) -> dict[str, Any] | None:
    """Gömülü başlığı ayrıştırır; kullanılamazsa None (aday listesinden düşer, hata değil).

    Kural tektir (`backup_crypto.is_usable_security_state`): günlük yedek aynı
    kuralla başlık gömer, kayıp kilidi aynı kuralla dosyayı "kayıp" sayar.
    """
    if not raw:
        return None
    return cast("dict[str, Any] | None", parse_security_state(raw))


def _candidate_states(info: BackupInfo) -> list[tuple[str, dict[str, Any]]]:
    """Denenecek durum dosyaları: önce güncel guvenlik.json, sonra gömülü başlık."""
    adaylar: list[tuple[str, dict[str, Any]]] = []
    try:
        guncel = app_password.read_state()
    except app_password.AppPasswordError:
        guncel = None  # bozuk güncel dosya gömülü başlıkla çözümü engellemesin
    if guncel is not None and not is_usable_security_state(guncel):
        guncel = None  # bölümleri eksik dosya aday değildir (kayıp kilidiyle aynı kural)
    if guncel is not None:
        adaylar.append((_SOURCE_CURRENT, guncel))
    if info.embedded_state is not None and info.embedded_state != guncel:
        adaylar.append((_SOURCE_EMBEDDED, info.embedded_state))
    return adaylar


def _decrypt_container(
    container: bytes,
    info: BackupInfo,
    *,
    password: str | None,
    recovery_key: str | None,
) -> tuple[bytes, str, bytes]:
    """Kapsayıcıyı çözer; (düz içerik, DEK kaynağı, DEK) döndürür."""
    adaylar = _candidate_states(info)
    if not adaylar:
        raise BackupRestoreError(
            "Yedeğin kurtarma başlığı yok ve veri klasöründe guvenlik.json bulunamadı. "
            "Kurtarma başlığı taşıyan başka bir yedek seçin ya da yedeğin alındığı "
            "dönemin guvenlik.json (veya guvenlik-arsiv-*.json) dosyasını veri klasörüne "
            "koyup yeniden deneyin."
        )
    for kaynak, durum in adaylar:
        try:
            if password:
                dek = app_password._unwrap_with_password(durum, password)
            else:
                dek = app_password._unwrap_with_recovery(durum, recovery_key or "")
        except app_password.AppPasswordError:
            continue  # bu durum dosyası bu sırla açılmadı; diğer adaya geç
        try:
            return decrypt_bytes(container, dek), kaynak, dek
        except BackupCryptoError:
            continue  # sarmal açıldı ama DEK bu yedeğe ait değil (başka kurulum)
    raise BackupRestoreError(
        "Yedek açılamadı: yönetici parolası ya da kurtarma anahtarı hatalı veya yedek "
        "bu kuruluma ait değil. Parola sonradan değiştiyse yedeğin alındığı dönemdeki "
        "parolayı da deneyin."
    )


def _swap_database_files(db_path: Path, content: bytes) -> Path | None:
    """Yeni içeriği atomik yerleştirir; eskiyi ve WAL/SHM kalıntılarını kenara alır.

    Sıra bilinçli: önce .tmp TAM yazılır (hata hâlinde hedefe dokunulmamış olur),
    sonra eski dosya kenara alınır, en son .tmp yerine konur. Eski veritabanının
    `-wal`/`-shm` dosyaları YENİ dosyaya uygulanmamalıdır — silinmez, kenara
    alınan dosyanın adıyla yanına taşınır (SQLite eşleşmeyi dosya adından yapar;
    veri kurtarma denemesinde birlikte açılabilirler).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp = db_path.with_name(db_path.name + ".yeni.tmp")
    temp.unlink(missing_ok=True)
    try:
        temp.write_bytes(content)
        eski_hedef: Path | None = None
        if db_path.exists():
            damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
            eski_hedef = db_path.with_name(f"{OLD_DB_PREFIX}-{damga}.sqlite3")
            db_path.replace(eski_hedef)
            for ek in ("-wal", "-shm"):
                kalinti = db_path.with_name(db_path.name + ek)
                if kalinti.exists():
                    kalinti.replace(eski_hedef.with_name(eski_hedef.name + ek))
            logger.info("Önceki veritabanı kenara alındı: %s", eski_hedef.name)
        else:
            # Hedef yokken kalan başıboş WAL/SHM yeni dosyayı zehirlemesin.
            for ek in ("-wal", "-shm"):
                db_path.with_name(db_path.name + ek).unlink(missing_ok=True)
        temp.replace(db_path)
        return eski_hedef
    except OSError as exc:
        raise BackupRestoreError(
            f"Geri yükleme yazılamadı ({exc.__class__.__name__}); diskte yer olduğundan "
            "ve dosyanın başka bir programda açık olmadığından emin olun."
        ) from exc
    finally:
        temp.unlink(missing_ok=True)


def _ensure_state_file(info: BackupInfo, kaynak: str) -> bool:
    """Geri yüklenen veritabanı ile guvenlik.json'ın tutarlı kalmasını sağlar.

    Çözüm GÜNCEL dosyayla başarıldıysa o dosya doğru DEK'i sarmalıyor demektir
    (parola değiştiyse en yeni sarmalı taşıyan da odur) → DOKUNULMAZ. Çözüm
    GÖMÜLÜ başlıkla başarıldıysa güncel dosya ya yok ya da bu veriye ait değil:
    varsa arşivlenir (silinmez: eski yedekleri açan tek sarmal olabilir), gömülü başlık
    olduğu gibi guvenlik.json olarak yazılır. Böylece geri yüklemeden çıkan
    (veritabanı, durum dosyası) çifti DAİMA aynı DEK'i anlatır ve açılıştaki
    parmak izi denetimi (`_adopt_key`) geçer.
    """
    if kaynak != _SOURCE_EMBEDDED or not info.embedded_raw:
        return False
    hedef = app_password.state_path()
    if hedef.is_file():
        damga = timezone.localtime().strftime("%Y-%m-%d-%H%M%S")
        arsiv = hedef.with_name(f"guvenlik-arsiv-{damga}.json")
        hedef.replace(arsiv)
        logger.info("Geri yüklenen veriyle eşleşmeyen guvenlik.json arşivlendi: %s", arsiv.name)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    temp = hedef.with_name(hedef.name + ".tmp")
    temp.write_bytes(info.embedded_raw)
    temp.replace(hedef)
    logger.info("guvenlik.json yedekteki kurtarma başlığından yazıldı.")
    return True
