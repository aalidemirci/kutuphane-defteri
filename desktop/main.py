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
   10. Katalog denetçisi (`katalog_kontrol`, T16) ve çıkış kancası backend'e
       kaydolur; `kd-gunluk` başlar: önce Ağ Kataloğunu AYARA göre kaldırır
       (varsayılan kapalı; açıksa güvenlik duvarı denetimi + öz sınama — hatası
       ölümcül DEĞİL), sonra gün değişimi kapısını koşar (günlük yedek,
       rotasyon, IP denetimi; saatte bir yinelenir) ve uyku engelini yönetir
   11. Tepsi (kip matrisi) + pencere (pywebview; `--tepside` ile gizli)
   `--autotest` kipinde 10-11 yerine Ağ Kataloğu yalnız loopback'te kalkar
   ve öz sınanır (paket duman testi soket yolunu kanıtlar), pencere açılmaz.

Adım sırası bilinçlidir: bütünlük denetimi yedeklemeden ÖNCE koşar; veritabanı
bozukken rotasyonun sağlam eski yedekleri silmesi istenmez.

**Kapanış** (§4.2-4/5). Çarpı pencereyi gizler; program yalnız "Çık" ile
(tepsi menüsü, arayüzdeki Çık — `POST app/quit/`, kurucunun
`KutuphaneDefteri.Kapat` olayı ya da Linux oturum kapanışı) kapanır. Sıra:
pencere → kanal → tepsi (`icon.stop()`) → kancalar bırakılır → Ağ Kataloğu →
`kd-gunluk` (uyku engeli kalkar) → yönetim sunucusu → WAL checkpoint (TB14) →
temiz kapanış işareti → kilit. Mutex'ler süreç bitene dek kalır (lock.py).

**Yükseltilmiş yardımcı kip.** `--guvenlik-duvari-kurali` (UAC ile, Ağ
Doktoru'nun "Kuralı ekle/güncelle" düğmesi) güvenlik duvarı kuralını ve HKLM
portunu yazar ve çıkar; pencere, kilit, veri dizini ve günlük AÇMAZ
(`desktop/guvenlik_duvari.py`).

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
import threading
import webbrowser
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from desktop import guvenlik_duvari
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
    is_parcacigi_baglantisiyla,
    prepare_django,
    run_migrations,
    wal_checkpoint,
)
from desktop.errors import (
    EXIT_OK,
    EXIT_SERVER_FAILED,
    EXIT_UNEXPECTED,
    AlreadyRunningError,
    StartupError,
)
from desktop.gunluk import (
    DAMGA_DOSYASI,
    GunDegisimiKapisi,
    acik_kalma_saati,
    uyku_engelleyici,
)
from desktop.instance_channel import COMMAND_QUIT, COMMAND_SHOW, CommandChannel, open_channel
from desktop.integrity import check_database_integrity
from desktop.katalog_kontrol import KatalogKontrol, django_ayar_dinleyicisi
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
    "logs/uygulama.log dosyasını okulun bilişim teknolojileri rehber "
    "öğretmenine (BTR) iletin."
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
    parser.add_argument(
        "--tepside",
        action="store_true",
        help=(
            "Pencereyi açmadan tepside başlar (otomatik başlatma için isteğe bağlı; "
            "tepsi kurulamazsa pencere yine açılır)."
        ),
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


#: Arayüzden gelen Çık (`POST app/quit/`) HTTP yanıtı gönderildikten SONRA başlasın.
_CIKIS_GECIKMESI_SN = 0.3


def cikis_kancasi(controller: WindowController) -> Callable[[], None]:
    """`app/quit/` için kanca: kapanışı ayrı iş parçacığında, yanıttan sonra başlatır."""

    def iste() -> None:
        zamanlayici = threading.Timer(_CIKIS_GECIKMESI_SN, controller.request_quit)
        zamanlayici.daemon = True
        zamanlayici.name = "kd-cikis"
        zamanlayici.start()

    return iste


def kip_durumu() -> str:
    """Tepsinin okuduğu kip (T16: `KipDurumu` tek kaynaktır); geri yükleme sonrası kilitli sütunu."""
    from apps.okul import restart_gate
    from apps.okul.kip import KIP

    if restart_gate.restart_required():
        return "yeniden_baslat"
    return is_parcacigi_baglantisiyla(KIP.durum)


def _gorevli_kipine_gec() -> None:
    from apps.okul.kip import KIP, KipGecisHatasi

    try:
        is_parcacigi_baglantisiyla(KIP.gorevliye_gec)
    except KipGecisHatasi as exc:
        logger.warning("Tepsi: görevli kipine geçilemedi (%s).", exc.durum)
    else:
        logger.info("Tepsi: görevli kipine geçildi.")


def _kilitle() -> None:
    from apps.okul.services import app_password

    is_parcacigi_baglantisiyla(app_password.lock)
    logger.info("Tepsi: program kilitlendi.")


def _arka_planda(ad: str, islem: Callable[[], Any]) -> Callable[[], None]:
    """Uzun süren tepsi komutu (güvenlik duvarı denetimi) menü döngüsünü bekletmesin."""

    def calistir() -> None:
        threading.Thread(target=islem, name=ad, daemon=True).start()

    return calistir


def _katalogu_tarayicida_ac(kontrol: KatalogKontrol) -> None:
    """Katalog LAN adresiyle harici tarayıcıda açılır (§4.1: 127.0.0.1 kullanılmaz)."""
    adres = kontrol.adres()
    if adres:
        webbrowser.open(adres)


def tepsi_eylemleri(controller: WindowController, kontrol: KatalogKontrol | None) -> TrayActions:
    """Tepsi kip matrisinin hedefleri (§4.4)."""
    if kontrol is None:
        return TrayActions(show=controller.show, quit=controller.request_quit)
    return TrayActions(
        show=controller.show,
        quit=controller.request_quit,
        kip=kip_durumu,
        quit_gorevli=controller.ask_quit_in_spa,
        katalog_satiri=kontrol.tepsi_satiri,
        katalog_acik=kontrol.acik_mi,
        katalog_kapatilabilir=kontrol.kapatilabilir_mi,
        katalog_ac=_arka_planda("kd-katalog-ac", kontrol.ac),
        katalog_kapat=_arka_planda("kd-katalog-kapat", kontrol.kapat),
        katalog_goster=lambda: _katalogu_tarayicida_ac(kontrol),
        gorevli_kipine_gec=_gorevli_kipine_gec,
        kilitle=_kilitle,
    )


def run_window_session(
    url: str,
    storage_path: Path,
    channel: CommandChannel | None,
    *,
    platform: str = sys.platform,
    kontrol: KatalogKontrol | None = None,
    tepside: bool = False,
) -> None:
    """Tepsi + kanal + pencere; "Çık" gelene dek bloklar (ANA iş parçacığında).

    Tepsi pencereden ÖNCE kurulur: Linux'ta Qt tepsisi ana iş parçacığında ve
    `webview.start`'tan önce kurulmak zorundadır (desktop/tray.py). Çıkışta
    kanal ve tepsi her durumda kapatılır; `icon.stop()` atlanırsa süreç asılı
    kalırdı. Arayüzdeki Çık (`POST app/quit/`) aynı denetçiye bağlıdır
    (`masaustu_kanca`); tepsisiz Linux masaüstünün çıkış yolu odur (TB13).
    """
    controller = WindowController(platform=platform)
    tray = start_tray(tepsi_eylemleri(controller, kontrol), platform=platform)
    controller.tray_available = tray.available
    _kancalari_kaydet(cikis=cikis_kancasi(controller))
    try:
        if channel is not None:
            channel.start(lambda command: dispatch_command(command, controller))
        open_window(
            url,
            storage_path=storage_path,
            controller=controller,
            hidden=tepside and tray.available,
        )
    finally:
        if channel is not None:
            channel.close()
        tray.stop()
    logger.info("Pencere kapandı; program düzenli kapanıyor.")


def _kancalari_kaydet(**kancalar: Any) -> None:
    """Masaüstü kancalarını backend'e kaydeder (T16). Backend yoksa (testte) sessiz."""
    try:
        from apps.okul import masaustu_kanca
    except ImportError:
        return
    masaustu_kanca.kaydet(**kancalar)


def _kancalari_birak() -> None:
    try:
        from apps.okul import masaustu_kanca
    except ImportError:
        return
    masaustu_kanca.kaldir()


def katalog_kontrolu_kur() -> KatalogKontrol:
    """Ağ Kataloğu denetçisi; backend'e kanca olarak kaydolur ve ayar değişikliğini dinler (T16)."""
    kontrol = KatalogKontrol()
    _kancalari_kaydet(katalog=kontrol)
    try:
        django_ayar_dinleyicisi(kontrol.ayar_degisince)
    except ImportError:
        logger.warning(
            "Ağ Kataloğu ayar dinleyicisi kurulamadı; değişiklik yeniden açılışta uygulanır."
        )
    return kontrol


def gun_kapisi_kur(
    paths: AppPaths,
    kontrol: KatalogKontrol,
    *,
    bugun: Callable[[], date] = date.today,
) -> GunDegisimiKapisi:
    """`kd-gunluk`: yerleşik işler (yedek + rotasyon, IP denetimi) + backend işleri."""
    kapi = GunDegisimiKapisi(
        damga_yolu=paths.data / DAMGA_DOSYASI,
        bugun=bugun,
        uyku=uyku_engelleyici(),
        uyku_gerekli=kontrol.uyku_gerekli,
    )
    kapi.kaydet("gunluk-yedek", gunluk_yedek_isi(paths, bugun=bugun))
    kapi.kaydet("ip-denetimi", kontrol.ip_denetle)
    # Damgasız: dinlenen seçili IP'nin gün içinde kaybolması ve geçici hatayla
    # kapalı kalan katalog günlük değil saatlik yakalanır.
    kapi.saatlik_kaydet("katalog-saatlik", kontrol.saatlik_denetle)
    kapi.backend_islerini_ekle()
    kontrol.uyku_dinleyicisi_ekle(kapi.uyandir)
    return kapi


def gunluk_yedek_isi(
    paths: AppPaths,
    *,
    bugun: Callable[[], date] = date.today,
    saat: Callable[[], float] = acik_kalma_saati,
) -> Callable[[], bool]:
    """Günlük yedek + 14 gün rotasyonu; yedek alınmadıysa rotasyon koşmaz (GA-2).

    Oturum içi rotasyon SAAT SIÇRAMASINA karşı korunur: program günlerce açık
    kalırken sistem saati 14 günden fazla ileri sıçrarsa (NTP ya da elle yanlış
    ayar) `bugün - 14` kesimi geçmiş günlerin bütün yedeklerini silerdi. İşin
    ilk koşusu bir çapa tutar (o günkü tarih + uyku dahil açık kalma saati);
    rotasyon `min(bugün, çapa + gerçekte geçen gün + 1)` tarihiyle yapılır.
    Saat doğruyken iki değer aynıdır (tatilde uykuda kalan bilgisayarda da:
    açık kalma saati uykuyu sayar); saat ileri sıçramışsa kesim gerçek süreye
    göre konur. "En çok 14 gün" saklama sözü (TB8, §6.4) bozulmaz: hiçbir
    yedek gerçek yaşı 14 günü aştığı hâlde tutulmaz. Açılıştaki rotasyon
    (`prepare_data`) çapasızdır, F1'deki gibi kalır.
    """
    capa: list[tuple[date, float]] = []

    def calistir() -> bool:
        gun = bugun()
        simdi = saat()
        if not capa:
            capa.append((gun, simdi))
        capa_gunu, capa_saati = capa[0]
        gecen_gun = max(0, int((simdi - capa_saati) // 86_400))
        guvenilir = capa_gunu + timedelta(days=gecen_gun + 1)
        if daily_backup(paths.db_path, paths.backups, today=gun) is None:
            return False  # parola kurulmadı / güvenlik dosyası kayıp: bir saat sonra yeniden
        rotasyon_gunu = min(gun, guvenilir)
        if rotasyon_gunu < gun:
            logger.warning(
                "Sistem saati programın açık kaldığı süreden %d gün ileride; eski yedekler "
                "gerçek süreye göre döndürülüyor. Saati denetleyin.",
                (gun - rotasyon_gunu).days,
            )
        rotate_backups(paths.backups, today=rotasyon_gunu)
        return True

    return calistir


def serve(
    paths: AppPaths,
    token: str,
    autotest: bool,
    channel: CommandChannel | None = None,
    *,
    tepside: bool = False,
) -> int:
    """Gömülü sunucuyu başlatır; `--autotest` değilse tepsiyi ve pencereyi açar."""
    application = build_wsgi_application()
    assert_session_guard_installed()

    server = BackgroundServer(application)
    server.start()
    katalog: KatalogServer | None = None
    kontrol: KatalogKontrol | None = None
    kapi: GunDegisimiKapisi | None = None
    try:
        server.wait_until_ready()
        check_health(server.base_url, token)
        if autotest:
            # Duman testi: katalog yalnız loopback'te kalkar ve öz sınanır; hatası
            # ÖLÜMCÜLDÜR — paket koşusu (CI) soket yolunun (Windows'ta
            # SO_EXCLUSIVEADDRUSE) gerçekten çalıştığını çıkış koduyla kanıtlamalı.
            katalog = start_catalog()
            if katalog is None:
                logger.error("Açılış denetimi: Ağ Kataloğu kalkmadı.")
                return EXIT_SERVER_FAILED
            logger.info("Açılış denetimi başarılı.")
            return EXIT_OK
        require_window_runtime()
        # Ağ Kataloğu (§4.2-2) yönetim sağlık denetiminden SONRA ve AYARA göre
        # kalkar; güvenlik duvarı denetimi süreceği için pencereyi bekletmez:
        # `kd-gunluk` ilk iş olarak onu kaldırır. Hatası ölümcül değildir.
        kontrol = katalog_kontrolu_kur()
        kapi = gun_kapisi_kur(paths, kontrol)
        kapi.baslat(ilk_is=kontrol.acilista_baslat)
        run_window_session(
            window_url(server.base_url, token),
            paths.webview_storage_path,
            channel,
            kontrol=kontrol,
            tepside=tepside,
        )
        return EXIT_OK
    finally:
        _kancalari_birak()
        if kontrol is not None:
            kontrol.kapanis()
        if kapi is not None:
            kapi.durdur()
        stop_catalog(katalog)
        server.stop()
        wal_checkpoint(paths.db_path)


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
            code = serve(paths, token, args.autotest, channel, tepside=args.tepside)
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
    ham = list(sys.argv[1:] if argv is None else argv)
    if guvenlik_duvari.UAC_BAYRAGI in ham:
        # Yükseltilmiş yardımcı kip: veri dizini, günlük, kilit ve pencere AÇILMAZ
        # (süreç UAC'ye kimliği girilen hesapta koşabilir).
        return guvenlik_duvari.yukseltilmis_kip(ham)
    args = build_parser().parse_args(ham)
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
