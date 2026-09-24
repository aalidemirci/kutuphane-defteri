"""Django'yu masaüstü kabuğu içinde ayağa kaldırma.

`backend/` dizini `sys.path`'e eklenir (paket içinde exe'nin yanındadır),
veri dizini `KD_DATA_DIR` ile settings'e bildirilir. Django içe aktarmaları
TEMBELDİR: bu modül import edildiğinde Django kurulmuş olmak zorunda değildir,
böylece `paths`/`lock`/`backup` testleri Django olmadan koşar.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

from desktop.errors import MigrationError, ServerStartError
from desktop.logging_setup import apply_access_log_policy
from desktop.session_guard import ENV_TOKEN

logger = logging.getLogger("kutuphane_defteri.django")

SETTINGS_MODULE = "config.settings"
ENV_DATA_DIR = "KD_DATA_DIR"
GUARD_MIDDLEWARE_PATH = "desktop.session_guard.SessionTokenMiddleware"


def prepare_django(backend_dir: Path, data_dir: Path) -> None:
    """Django'yu yapılandırır ve `django.setup()` çağırır.

    ÖNEMLİ: bu çağrıdan ÖNCE `KD_SESSION_TOKEN` ayarlanmış olmalıdır — ayar
    dosyası oturum belirteci middleware'ini o değişkene bakarak ekler ve
    ayarlar bir kez okunduktan sonra değişmez.
    """
    backend = str(backend_dir)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.environ[ENV_DATA_DIR] = str(data_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", SETTINGS_MODULE)

    import django

    django.setup()
    # `django.setup()` kendi günlük yapılandırmasını uygular ve `django.request`
    # susturmasını siler (bkz. `logging_setup.apply_access_log_policy`) → yeniden uygula.
    apply_access_log_policy()


def has_pending_migrations() -> bool:
    """Uygulanmamış göç var mı? (varsa `migrate` öncesi ayrı yedek alınır)"""
    from django.db import connections
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connections["default"])
    targets = executor.loader.graph.leaf_nodes()
    return bool(executor.migration_plan(targets))


def run_migrations() -> None:
    """`migrate --no-input` — hata halinde açılış durur (pencere açılmaz)."""
    from django.core.management import call_command

    try:
        call_command("migrate", interactive=False, verbosity=0)
    except Exception as exc:  # noqa: BLE001 — her göç hatası aynı kullanıcı akışına çıkar
        logger.exception("Veritabanı güncellemesi başarısız.")
        raise MigrationError(
            "Veritabanı güncellenemedi; program veriyi korumak için açılmadı.",
            hint=(
                "Yedek klasöründeki en son 'pre-migrate-*' veya günlük yedeği geri "
                "yüklemek için Başlat menüsündeki 'Kütüphane Defteri — Yedekten Geri "
                "Yükle' kısayolunu (veya 'kutuphane-defteri --geri-yukle' komutunu) "
                "çalıştırıp programı yeniden açın."
            ),
        ) from exc


def assert_session_guard_installed() -> None:
    """Fail-closed: belirteç koruması gerçekten zincirde mi?

    `KD_SESSION_TOKEN` ayarlandığı hâlde middleware yüklenmemişse (ayar dosyası
    değişmiş, sıralama bozulmuş) API kimlik doğrulamasız açılırdı. Bu sessiz
    hata veri sızıntısıdır → açılış durur.
    """
    from django.conf import settings

    if not os.environ.get(ENV_TOKEN):
        raise ServerStartError("Program başlatılamadı: oturum belirteci üretilmedi.")
    if GUARD_MIDDLEWARE_PATH not in list(settings.MIDDLEWARE):
        raise ServerStartError(
            "Program başlatılamadı: yerel erişim koruması yüklenmedi.",
            hint="Kurulum bozuk olabilir; programı yeniden kurun.",
        )


def is_parcacigi_baglantisiyla[T](islem: Callable[[], T]) -> T:
    """ORM'ye istek DIŞI bir iş parçacığından (tepsi, `kd-gunluk`, katalog denetçisi) dokunur.

    Django bağlantıları iş parçacığına özgüdür ve istek dışında kimse onları
    kapatmaz. Uzun ömürlü bir iş parçacığında açık kalan bağlantı Windows'ta
    geri yüklemeyi bozar: SQLite dosyayı `FILE_SHARE_DELETE` olmadan açar,
    `live_restore`'un `connections.close_all()`'u yalnız KENDİ iş parçacığının
    bağlantılarını kapatır ve takas (`os.replace`) erişim hatasıyla düşerdi.
    Bu sarmal, çağrının AÇTIĞI bağlantıyı sonunda kapatır; çağrıdan önce açık
    olan bir bağlantıya (HTTP isteğinin kendisi) dokunmaz.
    """
    from django.db import connections

    baglanti = connections["default"]
    onceden_acik = baglanti.connection is not None
    try:
        return islem()
    finally:
        if not onceden_acik and not baglanti.in_atomic_block:
            baglanti.close()


def wal_checkpoint(db_path: Path) -> bool:
    """Düzenli kapanışta WAL'i ana dosyaya yazar ve kırpar (TB14).

    İki sunucu durduktan SONRA çağrılır: `PRAGMA wal_checkpoint(TRUNCATE)`
    bütün WAL sayfalarını veritabanı dosyasına aktarır ve `-wal` dosyasını
    sıfırlar. Böylece kurucunun kapatma olayında ya da elektrik kesintisinde
    geriye tek, tutarlı bir dosya kalır. Başka bir bağlantı hâlâ okuyorsa
    checkpoint kısmi kalır (sonuç `False`); hata çıkışı durdurmaz.
    """
    import sqlite3
    from contextlib import closing

    if not db_path.exists():
        return False
    try:
        from django.db import connections

        connections.close_all()  # bu iş parçacığının Django bağlantıları
    except Exception:  # noqa: BLE001 — Django kurulmamış olabilir (açılış hatası)
        logger.debug("Django bağlantıları kapatılamadı (Django kurulmamış olabilir).")
    try:
        with closing(sqlite3.connect(db_path, timeout=5)) as baglanti:
            mesgul, _, _ = baglanti.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    except sqlite3.Error:
        logger.warning("Kapanışta WAL checkpoint yapılamadı.", exc_info=True)
        return False
    if mesgul:
        logger.warning("Kapanışta WAL checkpoint kısmi kaldı (veritabanı meşgul).")
        return False
    logger.info("Kapanışta WAL checkpoint yapıldı.")
    return True


def build_wsgi_application() -> object:
    """WSGI uygulamasını üretir (middleware zinciri burada kurulur)."""
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
    # `get_wsgi_application()` içeride `django.setup()`'ı TEKRAR çağırır ve Django'nun
    # günlük yapılandırması `django.request` susturmasını yeniden siler. Politika bu
    # yüzden Django'ya dokunan HER giriş noktasından sonra uygulanır; aksi hâlde
    # 4xx/5xx yanıtların istek yolu (DEBUG açıkken) konsola düşer.
    apply_access_log_policy()
    return application
