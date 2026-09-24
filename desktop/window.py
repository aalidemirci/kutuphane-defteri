"""pywebview penceresi + pencere motoru denetimi (tasarım §1, §4.5).

**MSHTML düşüşü KODLA ENGELLİDİR.** pywebview, Windows'ta EdgeChromium (WebView2)
bulamazsa sessizce eski MSHTML (Internet Explorer) motoruna düşer; React 18 orada
çalışmaz ve kullanıcı boş beyaz bir pencere görür. Bu yüzden:
  1. Açılışta WebView2 runtime'ı kayıt defterinden aranır, yoksa Türkçe yönlendirme
     verilir ve pencere hiç açılmaz;
  2. `webview.start()` çağrısına GUI motoru AÇIKÇA verilir (`gui="edgechromium"`),
     böylece pywebview'ın kendi düşüş mantığı devreye giremez.

pywebview TEMBEL içe aktarılır: paket kurulu olmayan geliştirme/test ortamında bu
modül yine de import edilebilir ve testler koşar.

**Çarpı pencereyi gizler, programı kapatmaz** (U3, §4.2-4; `WindowController`).
pywebview 5.3.2'nin `closing` olayı pencere motorunun iş parçacığında ESZAMANLI
koşar (`Event(window, should_lock=True)`) ve işleyicilerden biri `False`
döndürürse kapanma iptal edilir (winforms `on_closing` → `args.Cancel`, qt
`closeEvent` → `event.ignore()`). Program yalnız "Çık" ile kapanır: tepsi menüsü
ya da kurucunun kapatma olayı (`desktop/instance_channel.py`). Tepsi yoksa pencere
gizlenmez, küçültülür (okulzili yedeği): gizli pencereyi geri getirecek yol
kalmazdı.

**Windows oturumu kapanırken** WinForms `FormClosing`'i `WindowsShutDown`
nedeniyle gönderir. Bu kapanma iptal edilseydi program Windows'un kapanışını
engeller, sonunda zorla sonlandırılır ve temiz kapanış işareti yazılmazdı; her
sabah yanlış alarm çıkardı. Pencereye ayrıca bağlanan .NET işleyicisi bu iki
nedeni (oturum kapanışı, Görev Yöneticisi) tanır ve iptali geri alır
(`install_session_end_passthrough`).
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from desktop.errors import WebViewUnavailableError
from desktop.paths import resource_root

logger = logging.getLogger("kutuphane_defteri.window")

WINDOW_TITLE = "Kütüphane Defteri"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 860
WINDOW_MIN_SIZE = (1024, 700)
WINDOW_ICON_FILE = "kutuphane-defteri.ico"
WINDOW_APP_ID = "KutuphaneDefteri.Desktop"

# Microsoft Edge WebView2 Runtime'ın sabit ürün kimliği (Evergreen).
WEBVIEW2_CLIENT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_KEYS = (
    ("HKLM", rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
    ("HKLM", rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
    ("HKCU", rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_ID}"),
)
# "0.0.0.0" burada bir IP değil, kaldırılmış runtime'ın bıraktığı SÜRÜM damgasıdır.
_EMPTY_VERSIONS = {"", "0.0.0.0"}  # noqa: S104

RegistryReader = Callable[[str, str, str], "str | None"]
DwmSetter = Callable[[int, int, bool], int]

_WEBVIEW2_MESSAGE = "Pencere açılamadı: Microsoft Edge WebView2 Çalışma Zamanı bulunamadı."
_WEBVIEW2_HINT = (
    "Programın kurulum klasöründeki 'MicrosoftEdgeWebView2Setup.exe' dosyasını çalıştırıp "
    "WebView2'yi kurun, sonra programı yeniden açın. Kurulum yetkiniz yoksa okul bilişim "
    "sorumlusundan 'WebView2 Runtime' kurulumunu isteyin."
)


def _read_registry_value(hive: str, subkey: str, value_name: str) -> str | None:
    """Windows kayıt defterinden tek bir değer okur (Windows dışında None)."""
    if sys.platform != "win32":
        return None
    import winreg

    hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    try:
        with winreg.OpenKey(hives[hive], subkey) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return str(value)


def webview2_installed(*, registry_reader: RegistryReader | None = None) -> bool:
    """WebView2 Runtime kurulu mu? (Evergreen kaydındaki `pv` sürümüne bakar)"""
    reader = registry_reader or _read_registry_value
    for hive, subkey in _WEBVIEW2_KEYS:
        version = reader(hive, subkey, "pv")
        if version and version.strip() not in _EMPTY_VERSIONS:
            return True
    return False


def gui_backend_for(platform: str) -> str:
    """Platforma göre AÇIK GUI motoru — pywebview'ın sessiz düşüşünü engeller."""
    if platform.startswith("win"):
        return "edgechromium"  # asla "mshtml"
    if platform == "darwin":
        return "cocoa"
    # Pardus/Linux: pywebview'ın Qt arka ucu (PySide6 + QtWebEngine; bağlayıcı
    # `desktop/tray.py::load_qt` içinde `QT_API` ile sabitlenir).
    return "qt"


def require_window_runtime(
    *,
    platform: str | None = None,
    registry_reader: RegistryReader | None = None,
) -> None:
    """Pencere motoru yoksa açılışı durdurur (Windows/WebView2)."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return
    if not webview2_installed(registry_reader=registry_reader):
        raise WebViewUnavailableError(_WEBVIEW2_MESSAGE, hint=_WEBVIEW2_HINT)


def _import_webview() -> Any:
    import webview

    return webview


def _native_window_handle(window: Any) -> int | None:
    """pywebview/WinForms penceresinin HWND değerini güvenle çözer."""
    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None)
    if handle is None:
        return None
    try:
        return int(handle.ToInt64())
    except AttributeError:
        try:
            return int(handle)
        except (TypeError, ValueError):
            return None


def _dwm_set_titlebar(hwnd: int, attribute: int, dark: bool) -> int:
    """DWM başlık çubuğu temasını ayarlar; dönüş değeri Windows HRESULT'tur."""
    import ctypes
    from ctypes import wintypes

    enabled = wintypes.BOOL(bool(dark))
    return int(
        ctypes.windll.dwmapi.DwmSetWindowAttribute(  # type: ignore[attr-defined]
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(enabled),
            ctypes.sizeof(enabled),
        )
    )


def set_windows_app_id(*, platform: str | None = None) -> bool:
    """Görev çubuğu gruplaması ve ikon çözümü için kararlı Windows uygulama kimliği."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    try:
        import ctypes

        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(WINDOW_APP_ID)
        )
    except (OSError, AttributeError):
        logger.warning("Windows uygulama kimliği atanamadı.", exc_info=True)
        return False
    return int(result) == 0


def app_icon_path(*, root: Path | None = None) -> Path | None:
    """Uygulama ikonu (.ico): paketli programda kökte, depoda `packaging/ikonlar/`.

    Spec ikonu paket köküne koyar (`kutuphane_defteri.spec` → `datas`); kök
    `paths.resource_root()`'tur (PyInstaller'da `sys._MEIPASS`).
    """
    base = resource_root() if root is None else root
    for candidate in (base / WINDOW_ICON_FILE, base / "packaging" / "ikonlar" / WINDOW_ICON_FILE):
        if candidate.is_file():
            return candidate
    return None


def set_windows_window_icon(
    window: Any,
    *,
    platform: str | None = None,
    icon_path: Path | None = None,
    loader: Callable[[Path], Any] | None = None,
) -> bool:
    """WinForms ana penceresine paketlenmiş uygulama ikonunu doğrudan atar."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    native = getattr(window, "native", None)
    if native is None:
        return False
    path = icon_path or app_icon_path()
    if path is None or not path.is_file():
        return False
    try:
        if loader is None:
            from System.Drawing import Icon

            icon = Icon(str(path))
        else:
            icon = loader(path)
        native.Icon = icon
    except (ImportError, OSError, AttributeError):
        logger.warning("Windows pencere ikonu uygulanamadı.", exc_info=True)
        return False
    return True


def set_windows_titlebar_theme(
    window: Any,
    dark: bool,
    *,
    platform: str | None = None,
    setter: DwmSetter | None = None,
) -> bool:
    """Windows başlık çubuğunu uygulamanın açık/koyu temasıyla eşitler."""
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    hwnd = _native_window_handle(window)
    if hwnd is None:
        return False

    apply_attribute = setter or _dwm_set_titlebar
    # 20: Windows 10 20H1+; 19: daha eski Windows 10 yapıları için geri dönüş.
    for attribute in (20, 19):
        if apply_attribute(hwnd, attribute, dark) == 0:
            return True
    return False


class TitleBarApi:
    """Frontend temasını yerel Windows başlık çubuğuna taşıyan küçük JS köprüsü."""

    def __init__(self, *, platform: str) -> None:
        self._platform = platform
        self._window: Any | None = None
        self._icon_applied = False

    def bind_window(self, window: Any) -> None:
        self._window = window

    def set_titlebar_theme(self, dark: bool) -> bool:
        if self._window is None:
            return False
        try:
            if not self._icon_applied:
                self._icon_applied = set_windows_window_icon(
                    self._window,
                    platform=self._platform,
                )
            return set_windows_titlebar_theme(
                self._window,
                bool(dark),
                platform=self._platform,
            )
        except OSError:
            logger.warning("Windows başlık çubuğu teması uygulanamadı.", exc_info=True)
            return False


#: Kapanmanın iptal EDİLMEYECEĞİ `FormClosing` nedenleri (System.Windows.Forms.CloseReason).
SESSION_END_REASONS = frozenset({"WindowsShutDown", "TaskManagerClosing"})
#: pythonnet enum'u sayı olarak basarsa: WindowsShutDown = 1, TaskManagerClosing = 4.
_CLOSE_REASON_CODES = {"1": "WindowsShutDown", "4": "TaskManagerClosing"}


def close_reason_name(args: Any) -> str:
    """`FormClosingEventArgs.CloseReason`'ın adı (`"WindowsShutDown"` gibi)."""
    text = str(getattr(args, "CloseReason", "")).rsplit(".", 1)[-1]
    return _CLOSE_REASON_CODES.get(text, text)


class WindowController:
    """Pencerenin gizle / göster / çık davranışı (U3, §4.2-4).

    Üç yerden çağrılır: pywebview olayları (pencere iş parçacığı), tepsi menüsü
    (Windows'ta `pystray` iş parçacığı, Linux'ta Qt ana iş parçacığı) ve tek kopya
    kanalı (`kd-kanal`). Durum bu yüzden kilit altındadır; pywebview çağrıları
    kilit DIŞINDA yapılır (pencere iş parçacığına sıralanıp bloklayabilirler).

    Görevli kipinde tepsideki "Çık" doğrudan kapatmaz (§4.2-4): `ask_quit_in_spa`
    pencereyi öne getirir ve arayüze `kd:cik-iste` olayını gönderir; arayüz
    yönetici parolasını sorar ve `POST app/quit/` ile döner, kapanış yine
    `request_quit`'ten geçer (masaüstü kancası).

    Pencere tepside GİZLİ başlatılabilir (`--tepside`). Gizli pencerede
    pywebview'ın `shown` olayı hiç gelmeyebilir; sayfa yüklenince gelen
    `loaded` olayı da pencereyi "hazır" sayar (göster/kapat komutları işler).
    """

    #: Tepsideki görevli kipi Çık'ının arayüze gönderdiği olay (frontend `lib/cikis.ts`).
    SPA_QUIT_EVENT = "kd:cik-iste"

    def __init__(self, *, platform: str | None = None) -> None:
        self._platform = sys.platform if platform is None else platform
        self._lock = threading.Lock()
        self._window: Any | None = None
        self._shown = False
        self._quitting = False
        self._destroy_requested = False
        self._minimized = False
        self._maximized = False
        self._passthrough_installed = False
        #: Tepsi kurulduysa çarpı gizler; kurulamadıysa küçültür.
        self.tray_available = False

    @property
    def quitting(self) -> bool:
        with self._lock:
            return self._quitting

    def bind(self, window: Any) -> None:
        """pywebview penceresine bağlanır (`webview.start`'tan ÖNCE)."""
        with self._lock:
            self._window = window
        events = window.events
        events.closing += self.on_closing
        events.shown += self._on_shown
        loaded = getattr(events, "loaded", None)
        if loaded is not None:
            events.loaded += self._on_loaded
        events.minimized += self._on_minimized
        events.maximized += self._on_maximized
        events.restored += self._on_restored

    # ------------------------------------------------------------ pywebview olayları

    def on_closing(self) -> bool:
        """Çarpı: `False` kapanmayı iptal eder; yalnız "Çık"tan sonra `True`."""
        with self._lock:
            if self._quitting:
                return True
            window = self._window
        if window is None:
            return True
        try:
            if self.tray_available:
                window.hide()
                logger.info("Pencere gizlendi; program tepside çalışmaya devam ediyor.")
            else:
                window.minimize()
                logger.info("Sistem tepsisi yok; pencere küçültüldü, program kapanmadı.")
        except Exception:  # noqa: BLE001 — pencere görünür kalır, kapanmaz
            logger.warning("Pencere gizlenemedi.", exc_info=True)
        return False

    def _on_shown(self) -> None:
        with self._lock:
            self._shown = True
            window = self._window
            pending_quit = self._quitting
            install = self._platform == "win32" and not self._passthrough_installed
            self._passthrough_installed = self._passthrough_installed or install
        if window is None:
            return
        if install:
            install_session_end_passthrough(window, self, platform=self._platform)
        if pending_quit:
            self._destroy(window)

    def _on_loaded(self) -> None:
        """Sayfa yüklendi: gizli başlatılan pencere de artık komut alabilir."""
        with self._lock:
            if self._shown:
                return
            self._shown = True
            window = self._window
            pending_quit = self._quitting
        if window is not None and pending_quit:
            self._destroy(window)

    def _on_minimized(self) -> None:
        with self._lock:
            self._minimized = True

    def _on_maximized(self) -> None:
        with self._lock:
            self._minimized, self._maximized = False, True

    def _on_restored(self) -> None:
        with self._lock:
            self._minimized, self._maximized = False, False

    # ------------------------------------------------------- tepsi ve kanal komutları

    def show(self) -> None:
        """Tepsideki "Pencereyi aç": gizliyse gösterir, küçültülmüşse eski boyutuna döndürür."""
        with self._lock:
            window = self._window if self._shown and not self._quitting else None
            minimized, maximized = self._minimized, self._maximized
        if window is None:
            return
        try:
            window.show()
            if minimized:
                if maximized:
                    window.maximize()
                else:
                    window.restore()
        except Exception:  # noqa: BLE001 — tepsi komutu programı düşürmesin
            logger.warning("Pencere gösterilemedi.", exc_info=True)

    def ask_quit_in_spa(self) -> None:
        """Görevli kipinde tepsideki Çık: pencere öne gelir, arayüz parolayı sorar (§4.2-4)."""
        self.show()
        with self._lock:
            window = self._window if self._shown and not self._quitting else None
        if window is None:
            return
        try:
            window.evaluate_js(f"window.dispatchEvent(new Event('{self.SPA_QUIT_EVENT}'))")
        except Exception:  # noqa: BLE001 — pencere hazır değilse kullanıcı Çık'ı arayüzden seçer
            logger.warning("Çıkış isteği arayüze iletilemedi.", exc_info=True)

    def request_quit(self) -> None:
        """Tepsideki "Çık": pencereyi gerçekten kapatır; `webview.start` döner, çıkış sürer.

        Pencere henüz gösterilmediyse (komut açılış sırasında geldi) kapanma
        `shown` olayında yapılır; `open_window` başlatmadan önce de bakar.
        """
        with self._lock:
            self._quitting = True
            window = self._window if self._shown else None
        logger.info("Çıkış istendi; program düzenli kapanıyor.")
        if window is not None:
            self._destroy(window)

    def allow_session_end(self, reason: str) -> None:
        """Windows oturumu kapanıyor: kapanma iptal edilmez, düzenli çıkış sürer."""
        with self._lock:
            self._quitting = True
            self._destroy_requested = True  # pencereyi Windows kapatıyor
        logger.info("Windows oturumu kapanıyor (%s); program düzenli kapanıyor.", reason)

    def _destroy(self, window: Any) -> None:
        with self._lock:
            if self._destroy_requested:
                return
            self._destroy_requested = True
        try:
            window.destroy()
        except Exception:  # noqa: BLE001 — çıkış yolu hata yüzünden takılmasın
            logger.exception("Pencere kapatılamadı.")


def install_session_end_passthrough(
    window: Any, controller: WindowController, *, platform: str | None = None
) -> bool:
    """Windows: oturum kapanışında `FormClosing` iptalini geri alan .NET işleyicisi.

    pywebview'ın kendi işleyicisi (`on_closing` → `closing` olayı → iptal) daha
    önce bağlandığı için önce o koşar; bu işleyici ondan SONRA koşar ve
    `WindowsShutDown`/`TaskManagerClosing` nedenlerinde `Cancel`'ı geri alır.
    """
    system = sys.platform if platform is None else platform
    if not system.startswith("win"):
        return False
    native = getattr(window, "native", None)
    if native is None:
        return False

    def _on_form_closing(_sender: Any, args: Any) -> None:
        reason = close_reason_name(args)
        if reason in SESSION_END_REASONS:
            controller.allow_session_end(reason)
            args.Cancel = False

    try:
        native.FormClosing += _on_form_closing
    except Exception:  # noqa: BLE001 — pythonnet hataları çeşitli; açılış sürer
        logger.warning("Oturum kapanışı işleyicisi bağlanamadı.", exc_info=True)
        return False
    return True


def open_window(
    url: str,
    *,
    title: str = WINDOW_TITLE,
    storage_path: Path,
    webview: Any | None = None,
    platform: str | None = None,
    importer: Callable[[], Any] | None = None,
    controller: WindowController | None = None,
    hidden: bool = False,
) -> None:
    """Pencereyi açar ve kapanana kadar bloklar (pywebview'ın olay döngüsü).

    `controller` verilirse çarpı pencereyi gizler (U3); pencere yalnız
    `controller.request_quit()` ile kapanır. `hidden`: tepside gizli açılış
    (`--tepside`; yalnız tepsi kurulduysa verilir, aksi hâlde pencereye dönüş
    yolu kalmazdı).
    """
    system = sys.platform if platform is None else platform
    module = webview
    if module is None:
        try:
            module = (importer or _import_webview)()
        except ImportError as exc:
            raise WebViewUnavailableError(
                "Pencere açılamadı: pencere bileşeni (pywebview) yüklü değil.",
                hint="Kurulum eksik görünüyor; programı yeniden kurun.",
            ) from exc

    storage_path.mkdir(parents=True, exist_ok=True)
    set_windows_app_id(platform=system)
    # pywebview 5.x dosya indirmelerini varsayılan olarak engeller. Frontend'in
    # ortak `saveBlob` akışı Excel şablonları, resmî PDF'ler, ekler ve kurtarma
    # anahtarı için `<a download>` kullandığından bu izin pencere oluşturulmadan
    # önce açılmalıdır; aksi hâlde tıklama hata vermeden sessizce yutulur.
    module.settings["ALLOW_DOWNLOADS"] = True
    titlebar_api = TitleBarApi(platform=system)
    window = module.create_window(
        title,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=WINDOW_MIN_SIZE,
        text_select=True,
        js_api=titlebar_api,
        hidden=hidden,
    )
    titlebar_api.bind_window(window)
    if controller is not None:
        controller.bind(window)
        if controller.quitting:
            logger.info("Çıkış pencere açılmadan istendi; pencere açılmıyor.")
            return
    logger.info("Pencere açılıyor (%s).", gui_backend_for(system))
    module.start(
        gui=gui_backend_for(system),
        private_mode=False,  # oturum çerezi + taslaklar pencere ömrü boyunca kalsın
        storage_path=str(storage_path),
        debug=False,
    )
