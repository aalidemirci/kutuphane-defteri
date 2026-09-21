"""Kütüphane Defteri masaüstü başlatıcısı — açılış ve kapanış sırası (tasarım §4.2).

    1. Veri dizinleri (exe DIŞINDA) + günlük yapılandırması
    2. Tek-instance kilidi ................. ikinci kopya pencere AÇMAZ; bayraksız
       normal açılışsa çalışan kopyanın penceresini öne getirip 0 ile çıkar
    3. Temiz kapanış işareti okunur ve silinir (T15) + tek kopya kanalı kurulur
    4. Oturum belirteci ..................... ayarlar okunmadan ÖNCE üretilir
    5. Sürüm damgası ........................ eski program yeni veriyi AÇMAZ
    6. Bütünlük denetimi .................... bozuk veriyle pencere AÇILMAZ
    7. Günlük yedek + 14 gün rotasyonu ...... `Connection.backup()`; yalnız şifreli
       `.kdbak`. Yönetici parolası kurulmadan (ilk açılış) yedek atlanır; bugünün
       yedeği alınmadıysa rotasyon da koşmaz (tasarım §6.3-6)
    8. Göç öncesi yedek + `migrate --no-input`
    9. Gömülü sunucu (waitress, 127.0.0.1, boş port) + sağlık denetimi
       → Ağ Kataloğu (ikinci waitress, 127.0.0.1:8765, öz sınamalı); hatası
       ölümcül DEĞİL, çıkışta yönetim sunucusundan önce kapanır
   10. Tepsi + pencere (pywebview) — `--autotest` kipinde AÇILMAZ

Adım sırası bilinçlidir: bütünlük denetimi yedeklemeden ÖNCE koşar; veritabanı
bozukken rotasyonun sağlam eski yedekleri silmesi istenmez.

**Kapanış** (§4.2-4/5). Çarpı pencereyi gizler; program yalnız "Çık" ile
(tepsi menüsü ya da kurucunun `KutuphaneDefteri.Kapat` olayı) kapanır. Sıra:
pencere → kanal → tepsi (`icon.stop()`) → Ağ Kataloğu → yönetim sunucusu →
temiz kapanış işareti → kilit. Mutex'ler süreç bitene dek kalır (lock.py).

Herhangi bir adım başarısız olursa pencere açılmaz; kullanıcıya Türkçe ileti +
"son yedekten dön" yolu gösterilir ve hataya özel bir çıkış kodu döner (CI ve
paket kurulum testleri bu kodlara bakar). "Son yedekten dön" yolunun kendisi
`--geri-yukle` kipidir (desktop/restore.py): pencere/sunucu açılmadan yedek
seçtirilir ve veritabanının yerine konur.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from desktop.backup import (
    daily_backup,
    encrypt_legacy_backups,
    pre_migrate_backup,
    rotate_backups,
)
from desktop.clean_shutdown import (
    consume_marker,
    publish,
    restore_after_failed_startup,
    write_marker_quietly,
)
from desktop.dialogs import show_error
from desktop.django_bootstrap import (
    assert_session_guard_installed,
    build_wsgi_application,
    has_pending_migrations,
    prepare_django,
    run_migrations,
)
from desktop.errors import (
    EXIT_OK,
    EXIT_SERVER_FAILED,
    EXIT_UNEXPECTED,
    AlreadyRunningError,
    StartupError,
)
from desktop.instance_channel import COMMAND_QUIT, COMMAND_SHOW, CommandChannel, open_channel
from desktop.integrity import check_database_integrity
from desktop.katalog_server import KatalogServer, start_catalog, stop_catalog
from desktop.lock import SingleInstanceLock, signal_running_instance
from desktop.logging_setup import configure_logging, enable_crash_log
from desktop.paths import (
    ENV_APP_HOME,
    AppPaths,
    check_sync_hazard,
    resolve_app_paths,
    resolve_backend_dir,
)
from desktop.restore import run_restore
from desktop.server import BackgroundServer, check_health
from desktop.session_guard import ENV_TOKEN, generate_session_token, window_url
from desktop.tray import TrayActions, start_tray
from desktop.version import (
    ensure_stamp_compatible,
    get_app_version,
    write_version_stamp,
)
from desktop.window import WindowController, open_window, require_window_runtime

logger = logging.getLogger("kutuphane_defteri")

_UNEXPECTED_MESSAGE = "Program açılırken beklenmeyen bir hata oluştu."
_UNEXPECTED_HINT = (
    "Programı yeniden başlatmayı deneyin. Sorun sürerse veri klasöründeki "
    "logs/uygulama.log dosyasını okul bilişim sorumlusuna iletin."
)


def build_parser() -> argparse.ArgumentParser:
    """Komut satırı arayüzü."""
    parser = argparse.ArgumentParser(
        prog="kutuphane-defteri",
        description="Kütüphane Defteri — okul kütüphanesi için çevrimdışı masaüstü programı.",
    )
    parser.add_argument(
        "--autotest",
        action="store_true",
        help="Pencere açmadan açılış adımlarını koşar, sağlık denetimi yapıp çıkar.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Veri klasörünü değiştirir (taşınabilir kip ve testler için).",
    )
    parser.add_argument(
        "--geri-yukle",
        nargs="?",
        const="",
        default=None,
        metavar="YEDEK",
        help=(
            "Programı açmak yerine verilen .kdbak yedeğini veritabanının yerine "
            "geri yükler; dosya verilmezse yedek klasöründen seçtirir."
        ),
    )
    parser.add_argument(
        "--parola",
        default=None,
        help="Geri yükleme: yönetici parolası (otomasyon içindir; komut geçmişine düşer).",
    )
    parser.add_argument(
        "--kurtarma-anahtari",
        default=None,
        help="Geri yükleme: kurtarma anahtarı (otomasyon içindir).",
    )
    parser.add_argument(
        "--evet",
        action="store_true",
        help="Geri yükleme onay sorusunu ve kapanış beklemesini atlar.",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> AppPaths:
    """`--data-dir` verildiyse yerleşimi ona bağlar."""
    if args.data_dir:
        os.environ[ENV_APP_HOME] = str(args.data_dir)
    return resolve_app_paths()


def is_plain_launch(args: argparse.Namespace) -> bool:
    """Bayraksız normal açılış mı? (pencereli kip; §4.2-1)

    `--autotest` ve `--geri-yukle` kiptir: çalışan kopya bulurlarsa 2 koduyla
    çıkarlar, sinyal göndermezler. `--data-dir` kip değil konumdur; aynı veri
    dizinini kullanan kopyaya sinyal gider. (`--pdf-duman` ve
    `--bagimlilik-duman` bu işleve hiç gelmez: `packaging/pyinstaller/giris.py`.)
    """
    return not args.autotest and args.geri_yukle is None


def prepare_data(paths: AppPaths, app_version: str) -> None:
    """Veriyi açılışa hazırlar: sürüm → bütünlük → yedek → göç → damga."""
    ensure_stamp_compatible(paths.version_stamp_path, app_version)
    check_database_integrity(paths.db_path, backup_dir=paths.backups)

    encrypt_legacy_backups(paths.backups, paths.data)
    # Rotasyon yalnız bugünün yedeği elde varken koşar: yedek atlandıysa
    # (parola henüz kurulmadı, yedek anahtarı bozuk, guvenlik.json kayıp) eski
    # yedekler silinmez — kayıp kilidinden çıkış yolu onlardır (GA-2).
    if daily_backup(paths.db_path, paths.backups) is not None:
        rotate_backups(paths.backups)

    prepare_django(resolve_backend_dir(), paths.data)
    if has_pending_migrations():
        pre_migrate_backup(paths.db_path, paths.backups, app_version)
    run_migrations()
    write_version_stamp(paths.version_stamp_path, app_version)


def dispatch_command(command: str, controller: WindowController) -> None:
    """Tek kopya kanalından gelen komut → pencere denetçisi."""
    if command == COMMAND_SHOW:
        controller.show()
    elif command == COMMAND_QUIT:
        controller.request_quit()


def run_window_session(
    url: str,
    storage_path: Path,
    channel: CommandChannel | None,
    *,
    platform: str = sys.platform,
) -> None:
    """Tepsi + kanal + pencere; "Çık" gelene dek bloklar (ANA iş parçacığında).

    Tepsi pencereden ÖNCE kurulur: Linux'ta Qt tepsisi ana iş parçacığında ve
    `webview.start`'tan önce kurulmak zorundadır (desktop/tray.py). Çıkışta
    kanal ve tepsi her durumda kapatılır; `icon.stop()` atlanırsa süreç asılı
    kalırdı.
    """
    controller = WindowController(platform=platform)
    tray = start_tray(
        TrayActions(show=controller.show, quit=controller.request_quit), platform=platform
    )
    controller.tray_available = tray.available
    try:
        if channel is not None:
            channel.start(lambda command: dispatch_command(command, controller))
        open_window(url, storage_path=storage_path, controller=controller)
    finally:
        if channel is not None:
            channel.close()
        tray.stop()
    logger.info("Pencere kapandı; program düzenli kapanıyor.")


def serve(
    paths: AppPaths, token: str, autotest: bool, channel: CommandChannel | None = None
) -> int:
    """Gömülü sunucuyu başlatır; `--autotest` değilse tepsiyi ve pencereyi açar."""
    application = build_wsgi_application()
    assert_session_guard_installed()

    server = BackgroundServer(application)
    server.start()
    katalog: KatalogServer | None = None
    try:
        server.wait_until_ready()
        check_health(server.base_url, token)
        # Ağ Kataloğu (tasarım §4.2-2) yönetim sağlık denetiminden SONRA kalkar; hatası
        # ölümcül değildir (günlüğe düşer, `None` döner). `--autotest` de kaldırır ki
        # paket duman testinde soket yolu (Windows'ta SO_EXCLUSIVEADDRUSE) gerçekten koşsun.
        katalog = start_catalog()
        if autotest:
            # Duman testi kipinde katalog hatası ÖLÜMCÜLDÜR: paket koşusu (CI) soket
            # yolunun gerçekten çalıştığını çıkış koduyla kanıtlamalı. Normal açılışta
            # hata ölümcül değildir (yukarıdaki yorum).
            if katalog is None:
                logger.error("Açılış denetimi: Ağ Kataloğu kalkmadı.")
                return EXIT_SERVER_FAILED
            logger.info("Açılış denetimi başarılı.")
            return EXIT_OK
        require_window_runtime()
        run_window_session(
            window_url(server.base_url, token),
            paths.webview_storage_path,
            channel,
        )
        return EXIT_OK
    finally:
        stop_catalog(katalog)
        server.stop()


def _run_locked(paths: AppPaths, args: argparse.Namespace, app_version: str) -> int:
    """Kilit alındıktan sonraki akış: işaret → kanal → veri → sunucu/pencere → işaret."""
    previous = consume_marker(paths.data, paths.db_path)
    publish(previous)
    channel = open_channel(paths.root) if is_plain_launch(args) else None
    try:
        # Belirteç, ayarlar okunmadan ÖNCE üretilir: `config/settings.py`
        # middleware'i bu değişkene bakarak ekler.
        token = generate_session_token()
        os.environ[ENV_TOKEN] = token
        try:
            prepare_data(paths, app_version)
            code = serve(paths, token, args.autotest, channel)
        except StartupError:
            # Bu oturumda veriye işlem yazılmadı: önceki oturumun durumu korunur.
            restore_after_failed_startup(previous, paths.data, app_version)
            raise
        if code == EXIT_OK:
            write_marker_quietly(paths.data, app_version)
        return code
    finally:
        if channel is not None:
            channel.close()


def run(argv: Sequence[str] | None = None) -> int:
    """Programı çalıştırır ve süreç çıkış kodunu döndürür."""
    args = build_parser().parse_args(argv)
    paths = resolve_paths(args)
    paths.ensure()
    configure_logging(paths.logs, echo=args.autotest)

    # PyInstaller çalışma-zamanı kancası günlük yapılandırmasından ÖNCE koşar;
    # uyarısını env'e bırakır, buraya kadar taşınmazsa sessizce kaybolurdu.
    rthook_uyarisi = os.environ.pop("KD_RTHOOK_UYARI", "")
    if rthook_uyarisi:
        logger.warning("Paket ortamı uyarısı: %s", rthook_uyarisi)

    app_version = get_app_version()
    logger.info("Kütüphane Defteri %s başlıyor.", app_version)
    # PDF motorunun C katmanındaki bir çöküş süreci anında kapatır ve bu günlüğe
    # hiçbir şey düşmez (19.09.2026); o an Python yığını `logs/cokme.log`a yazılır.
    enable_crash_log(paths.logs, app_version)
    hazard = check_sync_hazard(paths.root)
    if hazard:
        logger.warning("%s", hazard)

    if args.geri_yukle is not None:
        # Geri yükleme kipi: pencere/sunucu açılmaz; bütünlük denetimi ve göç
        # KOŞULMAZ — bozuk veritabanı bu kipin varlık sebebidir. Tek-instance
        # kilidini ve hata gösterimini akış kendi içinde yönetir.
        return run_restore(paths, args)

    lock = SingleInstanceLock(paths.lock_path)
    try:
        try:
            lock.acquire()
        except AlreadyRunningError:
            # §4.2-1: YALNIZ bayraksız açılış çalışan kopyanın penceresini öne
            # getirir; sinyal ulaşmazsa (kanal yok) "zaten çalışıyor" iletisi.
            if is_plain_launch(args) and signal_running_instance(paths.root):
                logger.info("Program zaten çalışıyor; penceresi öne getirildi.")
                return EXIT_OK
            raise
        try:
            return _run_locked(paths, args, app_version)
        finally:
            os.environ.pop(ENV_TOKEN, None)
            lock.release()
    except StartupError as exc:
        logger.error("Açılış durdu: %s", exc.message)
        show_error(exc.title, exc.full_message)
        return exc.exit_code
    except Exception:
        logger.exception("Açılışta beklenmeyen hata.")
        show_error("Kütüphane Defteri açılamadı", f"{_UNEXPECTED_MESSAGE}\n\n{_UNEXPECTED_HINT}")
        return EXIT_UNEXPECTED


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
