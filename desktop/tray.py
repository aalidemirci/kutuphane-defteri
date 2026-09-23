"""Sistem tepsisi (tasarım §4.1, §4.4 tepsi kip matrisi — F0 kısmı, §4.5).

**F0 menüsü yalnız iki komuttur:** "Pencereyi aç" ve "Çık". Kip matrisinin
kalanı (ağ kataloğu durumu, aç/kapa, görevli kipi, kilitle; Çık'ın görevli
kipinde parola istemesi) `KipDurumu` ile F1/F5'te gelir (T16); o zamana dek
tepsi hiçbir durum okumaz.

**Windows — pystray (0.19.5).** `Icon.run_detached()` Win32 ileti döngüsünü
DAEMON OLMAYAN bir iş parçacığında açar (pystray `_win32._run_detached`). Bu
yüzden çıkışta `icon.stop()` ŞARTTIR: çağrılmazsa pencere kapansa da süreç asılı
kalır, mutex'ler bırakılmaz ve kurucu 30 sn bekleyip "tepsiden Çık'ı seçin"
der. Menü geri çağrıları o iş parçacığında koşar.

**Linux — Qt `QSystemTrayIcon` (PySide6).** Qt arayüz nesneleri yalnız
`QApplication`'ın iş parçacığında yaşar ve `webview.start()` ana iş parçacığını
Qt olay döngüsüyle tutar. Tepsi bu yüzden ANA iş parçacığında, `webview.start`'tan
ÖNCE kurulur. pywebview 5.3.2'nin Qt arka ucu uygulamayı `QApplication.instance()
or QApplication(sys.argv)` ile alır (`platforms/qt.py`: `setup_app` ve
`create_window`; kaynaktan doğrulandı): burada kurulan örnek aynen kullanılır.
Üç kural:

- **Bağlayıcı PySide6'dır** (LGPLv3; GPLv3'lü PyQt5'ten 23.09.2026'da çıkıldı —
  `packaging/requirements-paketleme.txt` başlığı). pywebview bağlayıcıya `qtpy`
  üzerinden ulaşır ve qtpy kurulu ilk bağlayıcıyı seçer; seçim `QT_API` ile
  `load_qt` içinde, ilk `import qtpy`'den önce sabitlenir.
- `QtWebEngineWidgets`, `QApplication` kurulmadan ÖNCE içe aktarılmalıdır: bu
  import `Qt::AA_ShareOpenGLContexts` özniteliğini kurar. Sonraya kalırsa Qt
  "Attribute Qt::AA_ShareOpenGLContexts must be set before QCoreApplication is
  created" uyarısı basar ve OpenGL bağlam paylaşımı kurulmaz. `load_qt` sırayı
  uygular.
- `setQuitOnLastWindowClosed(False)`: pencere gizliyken kapanan bir iletişim
  kutusu "son pencere kapandı" sayılıp programı sonlandırmasın. pywebview son
  pencere gerçekten kapanınca döngüyü kendisi bitirir (`_app.exit()`).

`isSystemTrayAvailable()` yanlışsa (tepsisiz GNOME) tepsi kurulmaz; pencere
çarpıda küçültülür (`WindowController`, okulzili yedeği).

**Linux oturum kapanışı.** Oturum kapanırken süreç SIGTERM alır; varsayılan
davranış sessiz ölümdür ve temiz kapanış işareti (T15) yazılmazdı — Windows'taki
`install_session_end_passthrough`'un karşılığı yoktu. Qt döngüsü C++'ta
beklerken Python sinyal işleyicisi koşamaz; kısa aralıklı bir `QTimer` yorumlayıcıya
sıra verir ve işaretlenen istek "Çık" yoluna çevrilir.

Tepsi kurulamazsa program yine çalışır; neden günlüğe yazılır.
"""

from __future__ import annotations

import importlib
import io
import logging
import os
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import FrameType, SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, Protocol

from desktop.window import app_icon_path

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger("kutuphane_defteri.tepsi")

MENU_SHOW: Final = "Pencereyi aç"
MENU_QUIT: Final = "Çık"
TRAY_NAME: Final = "kutuphane-defteri"
TRAY_TITLE: Final = "Kütüphane Defteri"
#: .deb'in kurduğu hicolor tema ikonu (packaging/linux/build.sh).
THEME_ICON_NAME: Final = "kutuphane-defteri"
_FALLBACK_ICON_COLOR: Final = "#1f4e79"
_FALLBACK_ICON_SIZE: Final = 64
#: SIGTERM'in Qt döngüsünde fark edilme aralığı.
_SIGNAL_POLL_MS: Final = 500
#: Linux Qt bağlayıcısı (LGPLv3). Python paketi ve qtpy'nin `QT_API` değeri.
QT_PACKAGE: Final = "PySide6"
QT_BINDING: Final = "pyside6"


@dataclass(frozen=True)
class TrayActions:
    """Tepsi komutlarının hedefleri (`WindowController.show` / `.request_quit`)."""

    show: Callable[[], None]
    quit: Callable[[], None]


class Tray(Protocol):
    @property
    def available(self) -> bool: ...

    def stop(self) -> None: ...


def menu_entries(actions: TrayActions) -> tuple[tuple[str, Callable[[], None]], ...]:
    """F0 menüsü: ilk öğe varsayılan eylemdir (simgeye tıklama)."""
    return ((MENU_SHOW, actions.show), (MENU_QUIT, actions.quit))


def _guarded(text: str, action: Callable[[], None]) -> Callable[..., None]:
    """Geri çağrıyı sarar: hata tepsi döngüsünü düşürmez, günlüğe yazılır.

    Konumsal argümanı yoktur, fazlasını yutar: pystray eylemin
    `__code__.co_argcount`'una bakıp (0) argümansız çağırır; Qt'nin
    `triggered(bool)` sinyali `checked` değerini verir, o da yutulur.
    """

    def run(*_signal_args: object) -> None:
        try:
            action()
        except Exception:  # noqa: BLE001 — tepsi döngüsü ayakta kalmalı
            logger.exception("Tepsi komutu başarısız: %s", text)

    return run


def load_icon_image(icon_path: Path | None) -> Image.Image:
    """Tepsi simgesi: uygulama ikonu (.ico'nun en büyük boyutu) ya da düz renk yedek."""
    from PIL import Image

    if icon_path is not None:
        try:
            with Image.open(icon_path) as source:
                return source.convert("RGBA")
        except OSError:
            logger.warning("Tepsi ikonu okunamadı: %s", icon_path, exc_info=True)
    size = (_FALLBACK_ICON_SIZE, _FALLBACK_ICON_SIZE)
    return Image.new("RGBA", size, _FALLBACK_ICON_COLOR)


class NullTray:
    """Tepsi yok (desteklenmeyen platform)."""

    available = False

    def stop(self) -> None:
        return None


class PystrayTray:
    """Windows tepsisi (pystray, daemon olmayan iş parçacığı)."""

    def __init__(
        self,
        actions: TrayActions,
        *,
        icon_path: Path | None = None,
        pystray_module: Any | None = None,
    ) -> None:
        self._actions = actions
        self._icon_path = icon_path
        self._module = pystray_module
        self._icon: Any | None = None

    @property
    def available(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        try:
            pystray = self._module or importlib.import_module("pystray")
            items = [
                pystray.MenuItem(text, _guarded(text, action), default=index == 0)
                for index, (text, action) in enumerate(menu_entries(self._actions))
            ]
            icon = pystray.Icon(
                TRAY_NAME, load_icon_image(self._icon_path), TRAY_TITLE, pystray.Menu(*items)
            )
            icon.run_detached()
        except Exception:  # noqa: BLE001 — tepsisiz de çalışılır
            logger.warning("Sistem tepsisi başlatılamadı; program tepsisiz sürüyor.", exc_info=True)
            return False
        self._icon = icon
        logger.info("Sistem tepsisi hazır.")
        return True

    def stop(self) -> None:
        """`icon.stop()` — tepsi iş parçacığını bitirir (çağrılmazsa süreç asılı kalır)."""
        icon, self._icon = self._icon, None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception:  # noqa: BLE001 — çıkış sürmeli
            logger.warning("Sistem tepsisi kapatılamadı.", exc_info=True)


def load_qt() -> SimpleNamespace:
    """PySide6 sınıfları; `QtWebEngineWidgets` `QApplication`'dan ÖNCE yüklenir (modül belgesi).

    Bağlayıcı seçimi burada sabitlenir: qtpy kararını ilk `import qtpy` anında
    verir ve o an pywebview'ın Qt arka ucu yüklenirken gelir — tepsi ondan önce
    kurulduğu için değişken burada yazılabilir. `setdefault`, dışarıdan verilmiş
    bir seçimi ezmez (sahada teşhis için).
    """
    os.environ.setdefault("QT_API", QT_BINDING)
    importlib.import_module(f"{QT_PACKAGE}.QtWebEngineWidgets")
    qt_core = importlib.import_module(f"{QT_PACKAGE}.QtCore")
    qt_gui = importlib.import_module(f"{QT_PACKAGE}.QtGui")
    qt_widgets = importlib.import_module(f"{QT_PACKAGE}.QtWidgets")
    return SimpleNamespace(
        QApplication=qt_widgets.QApplication,
        QSystemTrayIcon=qt_widgets.QSystemTrayIcon,
        QMenu=qt_widgets.QMenu,
        QIcon=qt_gui.QIcon,
        QPixmap=qt_gui.QPixmap,
        QTimer=qt_core.QTimer,
    )


def prepare_qt_application(qt: Any) -> Any:
    """pywebview'ın da kullanacağı tek `QApplication` örneği (ana iş parçacığında)."""
    app = qt.QApplication.instance()
    if app is None:
        # pywebview `platforms/qt.py` içe aktarılırken aynısını yapar (bazı
        # dağıtımlarda geçersiz stil uyarısı); uygulama artık ondan ÖNCE kurulduğu
        # için değişken burada, kurulumdan önce yazılır.
        os.environ["QT_STYLE_OVERRIDE"] = ""
        app = qt.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    return app


def _qt_icon(qt: Any, icon_path: Path | None) -> Any:
    """Tema ikonu (.deb) → yoksa .ico Pillow ile PNG'ye çevrilir (Qt'nin ico eklentisi gerekmez)."""
    themed = qt.QIcon.fromTheme(THEME_ICON_NAME)
    if not themed.isNull():
        return themed
    buffer = io.BytesIO()
    load_icon_image(icon_path).save(buffer, format="PNG")
    pixmap = qt.QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return qt.QIcon(pixmap)


SignalInstaller = Callable[..., Any]


class QtTray:
    """Linux tepsisi (Qt, ana iş parçacığı) + SIGTERM → "Çık" köprüsü."""

    def __init__(
        self,
        actions: TrayActions,
        *,
        icon_path: Path | None = None,
        qt_loader: Callable[[], Any] = load_qt,
        signal_installer: SignalInstaller = signal.signal,
    ) -> None:
        self._actions = actions
        self._icon_path = icon_path
        self._qt_loader = qt_loader
        self._install_signal = signal_installer
        self._qt: Any | None = None
        self._tray: Any | None = None
        self._menu: Any | None = None
        self._timer: Any | None = None
        self._previous_sigterm: Any | None = None
        self._termination_requested = threading.Event()

    @property
    def available(self) -> bool:
        return self._tray is not None

    def start(self) -> bool:
        try:
            qt = self._qt_loader()
            app = prepare_qt_application(qt)
        except Exception:  # noqa: BLE001 — Qt yoksa pencere de açılmaz; hata orada söylenir
            logger.warning("Qt yüklenemedi; sistem tepsisi kurulmadı.", exc_info=True)
            return False
        self._qt = qt
        self._watch_termination(qt)
        if not qt.QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning(
                "Masaüstünde sistem tepsisi yok; pencere çarpıda küçültülecek, program kapanmayacak."
            )
            return False
        try:
            tray = qt.QSystemTrayIcon(_qt_icon(qt, self._icon_path), app)
            tray.setToolTip(TRAY_TITLE)
            menu = qt.QMenu()
            for text, action in menu_entries(self._actions):
                menu.addAction(text).triggered.connect(_guarded(text, action))
            tray.setContextMenu(menu)
            tray.activated.connect(self._on_activated)
            tray.show()
        except Exception:  # noqa: BLE001 — tepsisiz de çalışılır
            logger.warning("Sistem tepsisi kurulamadı; program tepsisiz sürüyor.", exc_info=True)
            return False
        # Menü nesnesi Python tarafında tutulmazsa çöp toplayıcı onu siler.
        self._tray, self._menu = tray, menu
        logger.info("Sistem tepsisi hazır.")
        return True

    def _on_activated(self, reason: Any) -> None:
        tray_class = self._qt.QSystemTrayIcon if self._qt is not None else None
        if tray_class is not None and reason in (tray_class.Trigger, tray_class.DoubleClick):
            _guarded(MENU_SHOW, self._actions.show)()

    # ------------------------------------------------------------ SIGTERM köprüsü

    def _watch_termination(self, qt: Any) -> None:
        try:
            self._previous_sigterm = self._install_signal(signal.SIGTERM, self._on_sigterm)
        except (ValueError, OSError):  # ana iş parçacığı dışında kurulamaz
            logger.warning("SIGTERM işleyicisi kurulamadı.", exc_info=True)
            return
        timer = qt.QTimer()
        timer.timeout.connect(self.poll_termination)
        timer.start(_SIGNAL_POLL_MS)
        self._timer = timer

    def _on_sigterm(self, _signum: int, _frame: FrameType | None) -> None:
        self._termination_requested.set()

    def poll_termination(self) -> None:
        """Qt zamanlayıcısından: SIGTERM geldiyse "Çık" yolunu çalıştırır."""
        if not self._termination_requested.is_set():
            return
        self._termination_requested.clear()
        logger.info("Oturum kapanıyor (SIGTERM); program düzenli kapanıyor.")
        _guarded(MENU_QUIT, self._actions.quit)()

    def stop(self) -> None:
        tray, self._tray = self._tray, None
        self._menu = None
        timer, self._timer = self._timer, None
        if timer is not None:
            timer.stop()
        if self._previous_sigterm is not None:
            try:
                self._install_signal(signal.SIGTERM, self._previous_sigterm)
            except (ValueError, OSError):
                pass
            self._previous_sigterm = None
        if tray is not None:
            try:
                tray.hide()
            except Exception:  # noqa: BLE001 — çıkış sürmeli
                logger.warning("Sistem tepsisi gizlenemedi.", exc_info=True)


def start_tray(
    actions: TrayActions,
    *,
    platform: str = sys.platform,
    icon_path: Path | None = None,
) -> Tray:
    """Platforma uygun tepsiyi kurar. Nesne her durumda döner; `available` sonucu söyler.

    Linux'ta tepsi kurulamasa da nesne SIGTERM köprüsünü taşır: `stop()` ŞART.
    """
    path = icon_path if icon_path is not None else app_icon_path()
    tray: PystrayTray | QtTray
    if platform == "win32":
        tray = PystrayTray(actions, icon_path=path)
    elif platform.startswith("linux"):
        tray = QtTray(actions, icon_path=path)
    else:
        logger.info("Bu platformda sistem tepsisi yok (%s).", platform)
        return NullTray()
    tray.start()
    return tray
