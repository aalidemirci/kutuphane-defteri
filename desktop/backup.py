"""Otomatik şifreli yedekleme — SQLite çevrimiçi görüntü + 14 gün rotasyonu.

**Dosya kopyalama YAPILMAZ.** WAL kipinde işlenmiş sayfaların bir bölümü hâlâ
`-wal` dosyasındadır; `db.sqlite3`'ü tek başına kopyalamak tutarsız (hatta bozuk)
bir yedek üretir. `Connection.backup()` ise SQLite'ın kendi çevrimiçi yedek API'sini
kullanır: kaynak veritabanını sayfa sayfa RAM'e okur, WAL dahil tutarlı bir görüntü
çıkarır.

**Yedek YALNIZ şifreli yazılır** (tasarım §6.3-6; KS'nin "parolasız kipte düz
`.kdbak`" dalı F1'de söküldü). Görüntü, yedek açık anahtarıyla (`yedekleme.json`)
X25519 + AES-256-GCM kapsayıcısına mühürlenir ve başlığına o anki
`guvenlik.json` (kurtarma başlığı) gömülür. Yedek ATLANIR (uyarı loglanır,
düz kopya asla yazılmaz):

* `yedekleme.json` yoksa: yönetici parolası henüz kurulmamıştır (ilk açılış).
  Kişi verisi de yoktur (parola kurulmadan kişi yazılamaz); ilk yedek parola
  kurulduktan sonraki açılışta alınır. Bu davranış testle sabitlenir.
* `yedekleme.json` bozuksa: kilit bir kez açıldığında `ensure_public_config`
  dosyayı onarır.
* Kurtarma başlığı kullanılamıyorsa (`guvenlik.json` kayıp, okunamıyor, boş ya
  da biçimsiz — GA-2): böyle bir başlıkla alınan yedek ancak kaybolan dosyayla
  açılabilirdi; üretmek yerine atlanır. "Kullanılabilir" kuralı tektir ve
  `backup_crypto.is_usable_security_state`'tedir (kayıp kilidi ve geri yükleme
  de onu kullanır). Yalnız dosyanın VARLIĞINA bakmak yetmez: içi boşaltılmış
  bir dosyayla başlıksız yedekler birikir, rotasyon da sağlam başlıklı eskileri
  süpürürdü. Açılış akışı (`desktop/main.py`) bugünün yedeği alınmadıkça
  rotasyonu da koşmaz: kayıp kilidinden çıkış yolu olan eski başlıklı yedekler
  silinmez.

Yedek adları tarihlidir ve deterministiktir: aynı gün ikinci kez açılan program o
günün yedeğini yeniden ÜRETMEZ (sabah alınan yedek, akşam bozulan veriyle ezilmez).
"""

from __future__ import annotations

import logging
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from desktop.backup_crypto import (
    BACKUP_SUFFIX,
    MAGIC,
    BackupCryptoError,
    config_path,
    encrypt_to_path,
    load_public_key,
    recovery_metadata,
    usable_recovery_header,
)

DAILY_PREFIX = "gunluk"
PRE_MIGRATE_PREFIX = "pre-migrate"

DEFAULT_KEEP_DAYS = 14
DEFAULT_KEEP_PRE_MIGRATE = 5

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
# Dosya adında güvenli olmayan her şey alt çizgiye döner (sürüm etiketi "1.0/rc:1" olabilir).
_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")

logger = logging.getLogger("kutuphane_defteri.backup")

_LEGACY_PATTERNS = (
    f"{DAILY_PREFIX}-*.sqlite3",
    f"{PRE_MIGRATE_PREFIX}-*.sqlite3",
    "pre-parola-*.sqlite3",
)


# CPython `Connection.serialize`i ancak SQLite ≥3.36 (SQLITE_ENABLE_DESERIALIZE)
# ile derlendiyse sunar; Pardus 21/bullseye tabanının libsqlite3'ü 3.34'tür ve
# yöntem HİÇ yoktur — KS F9 paket `--autotest`i bullseye kabında bununla çöktü
# (eski kod parolasız kipte yedeği atladığı için tuzak hiç tetiklenmemişti).
_HAS_SERIALIZE = hasattr(sqlite3.Connection, "serialize")


def database_snapshot(source_path: Path) -> bytes:
    """WAL dahil tutarlı SQLite görüntüsünü üretir (mümkünse RAM'de).

    `serialize` yoksa görüntü, veri dizini altında 0700 izinli geçici bir
    dizine `Connection.backup()` ile alınır ve baytları okunur okunmaz silinir.
    Şifreli kipte düz baytların diske bu KISA temasını, Pardus 21 uyumu için
    bilinçli kabul ediyoruz — kalıcı düz kopya yine yazılmaz.
    """
    with closing(sqlite3.connect(source_path)) as source:
        if _HAS_SERIALIZE:
            with closing(sqlite3.connect(":memory:")) as target:
                source.backup(target)
                return bytes(target.serialize())
        with tempfile.TemporaryDirectory(dir=source_path.parent) as tmp_dir:
            snapshot_path = Path(tmp_dir) / "goruntu.sqlite3"
            with closing(sqlite3.connect(snapshot_path)) as target:
                source.backup(target)
            return snapshot_path.read_bytes()


def _copy_database(source_path: Path, target_path: Path) -> bool:
    """Tutarlı SQLite görüntüsünü ŞİFRELİ yazar; yazıldıysa True döner.

    Düz kopya hiçbir durumda yazılmaz. Yedek anahtarı (`yedekleme.json`) yoksa,
    bozuksa ya da kurtarma başlığı (`guvenlik.json`) kullanılamıyorsa (yok,
    boş, bozuk, bölümleri eksik) yedek atlanır (False; gerekçeler modül başlığında).
    """
    data_dir = source_path.parent
    if not config_path(data_dir).is_file():
        logger.info("Yönetici parolası henüz kurulmadı; yedek alınmadı.")
        return False
    try:
        public_key = load_public_key(data_dir)
    except BackupCryptoError:
        logger.warning(
            "Şifreli yedekleme anahtarı bozuk; yedek alınamadı (düz kopya yazılmadı). "
            "Yönetici parolasıyla kilidi açmak dosyayı onarır."
        )
        return False
    # Başlık DOĞRULANMIŞ baytlardan gömülür (varlık denetimi + ayrı okuma arasında
    # dosya değişse bile gömülen, denetlenenle aynıdır).
    header = usable_recovery_header(data_dir)
    if header is None:
        logger.warning(
            "Güvenlik dosyası (guvenlik.json) bulunamadı ya da okunamıyor; kurtarma "
            "başlığı olmadan yedek alınmadı. Eski yedekler korunuyor."
        )
        return False
    encrypt_to_path(
        database_snapshot(source_path),
        target_path,
        public_key,
        recovery_header=header,
    )
    return True


def _is_encrypted_container(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(len(MAGIC)) == MAGIC


def encrypt_legacy_backups(backup_dir: Path, data_dir: Path) -> list[Path]:
    """Eski düz yedekleri atomik olarak şifreli `.kdbak` biçimine çevirir.

    Program artık düz yedek yazmaz; bu yordam, parolasız dal sökülmeden önceki
    geliştirme sürümlerinden kalmış olabilecek düz dosyalar içindir (`*.sqlite3`
    adlı ya da düz baytlı `.kdbak`). Parola kurulduğunda ve kilit her
    açıldığında çağrılır — diskte düz kopya kalmaz.
    """
    if not backup_dir.is_dir():
        return []
    try:
        public_key = load_public_key(data_dir)
    except BackupCryptoError:
        return []
    encrypted: list[Path] = []
    for pattern in _LEGACY_PATTERNS:
        for source in sorted(backup_dir.glob(pattern)):
            target = source.with_suffix(BACKUP_SUFFIX)
            encrypt_to_path(
                source.read_bytes(),
                target,
                public_key,
                recovery_header=recovery_metadata(data_dir),
            )
            source.unlink()
            encrypted.append(target)
    for pattern in (
        f"{DAILY_PREFIX}-*{BACKUP_SUFFIX}",
        f"{PRE_MIGRATE_PREFIX}-*{BACKUP_SUFFIX}",
    ):
        for source in sorted(backup_dir.glob(pattern)):
            if _is_encrypted_container(source):
                continue
            encrypt_to_path(
                source.read_bytes(),
                source,
                public_key,
                recovery_header=recovery_metadata(data_dir),
            )
            encrypted.append(source)
    if encrypted:
        logger.info("%d düz yedek şifreli biçime dönüştürüldü.", len(encrypted))
    return encrypted


def _safe_name(value: str) -> str:
    return _UNSAFE_RE.sub("_", value).strip("_") or "bilinmeyen"


def _parse_date(path: Path) -> date | None:
    match = _DATE_RE.search(path.stem)
    if match is None:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def daily_backup(db_path: Path, backup_dir: Path, *, today: date | None = None) -> Path | None:
    """Günün yedeğini alır. Veritabanı yoksa veya yedek zaten varsa yeniden üretmez."""
    if not db_path.exists():
        return None
    day = today or date.today()
    target = backup_dir / f"{DAILY_PREFIX}-{day.isoformat()}{BACKUP_SUFFIX}"
    if target.exists():
        return target
    if not _copy_database(db_path, target):
        return None
    logger.info("Günlük yedek alındı: %s", target.name)
    return target


def pre_migrate_backup(
    db_path: Path,
    backup_dir: Path,
    app_version: str,
    *,
    today: date | None = None,
) -> Path | None:
    """Şema güncellemesinden ÖNCE ayrı bir kopya alır (yükseltme geri alınabilsin)."""
    if not db_path.exists():
        return None
    day = today or date.today()
    name = f"{PRE_MIGRATE_PREFIX}-{_safe_name(app_version)}-{day.isoformat()}{BACKUP_SUFFIX}"
    target = backup_dir / name
    if target.exists():
        return target
    if not _copy_database(db_path, target):
        return None
    logger.info("Güncelleme öncesi yedek alındı: %s", target.name)
    return target


def rotate_backups(
    backup_dir: Path,
    *,
    keep_days: int = DEFAULT_KEEP_DAYS,
    keep_pre_migrate: int = DEFAULT_KEEP_PRE_MIGRATE,
    today: date | None = None,
) -> list[Path]:
    """Eskimiş yedekleri siler; sildiklerini döndürür.

    Günlük yedekler GÜN (varsayılan 14), güncelleme öncesi yedekler ADET
    (varsayılan son 5) ile sınırlanır — ikincisi haftalar sonra fark edilen bir
    yükseltme sorununda hâlâ elde olmalıdır. Program dışı/elle konmuş dosyalara
    (adı desenlerimize uymayan her şey) DOKUNULMAZ.
    """
    if not backup_dir.is_dir():
        return []
    day = today or date.today()
    removed: list[Path] = []

    cutoff = day - timedelta(days=keep_days)
    for path in sorted(backup_dir.glob(f"{DAILY_PREFIX}-*{BACKUP_SUFFIX}")):
        taken = _parse_date(path)
        if taken is not None and taken < cutoff:
            path.unlink(missing_ok=True)
            removed.append(path)

    pre_migrate = [
        path
        for path in backup_dir.glob(f"{PRE_MIGRATE_PREFIX}-*{BACKUP_SUFFIX}")
        if _parse_date(path) is not None
    ]
    # En yeni tarih başta; aynı gün birden fazlaysa ad sırası belirleyicidir.
    pre_migrate.sort(key=lambda p: (_parse_date(p) or date.min, p.name), reverse=True)
    for path in pre_migrate[keep_pre_migrate:]:
        path.unlink(missing_ok=True)
        removed.append(path)

    if removed:
        logger.info("Eskimiş %d yedek silindi.", len(removed))
    return removed
