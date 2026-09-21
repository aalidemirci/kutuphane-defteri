"""Ağ Kataloğu sunucusu — ikinci waitress dinleyicisi (tasarım §4.1, §4.2-2, §5.2).

Yönetim sunucusundan (`desktop/server.py`, `kd-wsgi`) tamamen ayrıdır (T3): kendi
waitress örneği, kendi iş parçacığı havuzu ve Django'dan bağımsız WSGI uygulaması
(`backend/katalog/app.py`) vardır. Yönetim API'si bu porttan hiçbir koşulda
yanıt vermez; öz sınama bunu her açılışta yoklar.

**Dinleme adresi.** Bu sürümde katalog yalnız `127.0.0.1`'de dinler (F0-F4,
UY-19). Okul ağına açılış (`0.0.0.0`) güvenlik duvarı kuralı beş maddelik
denetimden geçtiğinde gelir (F5, §5.7). Yönetim tarafında bu adres hiç geçmez;
koruma testi (§5.10-1) adresin yalnız bu dosyada durduğunu denetler.

**Soketi kendimiz açarız** (§5.2, R9 §2) ve waitress'e `sockets=[...]` ile veririz:

- Windows'ta `SO_EXCLUSIVEADDRUSE` bind'den ÖNCE konur: aynı adrese başka bir
  süreç `SO_REUSEADDR` ile bağlanıp katalog trafiğini ele geçiremez.
- Diğer platformlarda `SO_REUSEADDR` bilerek KONMAZ.
- waitress 3.0.2 verilen sokette de `set_reuse_addr()` çağırır (`BaseWSGIServer.
  __init__`: `getsockopt(SO_REUSEADDR) | 1` ile `setsockopt`, `except OSError:
  pass`). Windows'ta özel kullanımlı sokette bu çağrı WinError 10022 (WSAEINVAL)
  ile düşer ve waitress onu yutar; soket özel kalır (Windows 11, 21.09.2026
  spike). Linux'ta çağrı başarılı olur ama bind ve listen çoktan yapılmıştır:
  dinleyen bir soketin portuna ikinci bir soket `SO_REUSEADDR` ile de
  bağlanamaz. Windows'ta sonuç `verify_exclusive_bind` ile her açılışta
  doğrulanır ve günlüğe yazılır.

**Hata ölümcül değildir.** Katalog açılamazsa (`KatalogServerError`) yönetim
tarafı açılmaya devam eder; ileti günlüğe düşer. Bu yüzden istisna ailesi
`desktop.errors.StartupError`'dan bilerek türemez.

**Günlük.** Erişim günlüğü yoktur (§5.5): IP, yol ve arama terimi yazılmaz.
"""

from __future__ import annotations

import errno
import http.client
import logging
import os
import socket
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from desktop.server import HEALTH_PATH, ServerFactory, WSGIServerLike

if TYPE_CHECKING:
    from wsgiref.types import WSGIApplication

logger = logging.getLogger("kutuphane_defteri.katalog")

THREAD_NAME: Final = "kd-katalog"
LOOPBACK_HOST: Final = "127.0.0.1"
#: Okul ağına açılış adresi (F5): yalnız güvenlik duvarı denetimi geçerse (§5.7).
#: Bu sürümde KULLANILMAZ; `KatalogServer` bu adresi reddeder.
ALL_INTERFACES_HOST: Final = "0.0.0.0"  # noqa: S104 — bilerek; bkz. yukarıdaki not
#: Bu sürümde kabul edilen dinleme adresleri (F0-F4: yalnız loopback).
ALLOWED_LISTEN_HOSTS: Final = frozenset({LOOPBACK_HOST})

DEFAULT_PORT: Final = 8765
#: Yalnız geliştirme ve test içindir (§2.3); gerçek kaynak ileride `KatalogAyari`.
ENV_PORT: Final = "KD_KATALOG_PORT"
LISTEN_BACKLOG: Final = 128

#: waitress ayarları (§5.2). `ident=None`: `Server:` başlığı sürüm sızdırmaz.
#: `clear_untrusted_proxy_headers`: `X-Forwarded-For` uygulamaya ulaşmaz (§5.5).
WAITRESS_SETTINGS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "threads": 4,
        "connection_limit": 300,
        "channel_timeout": 30,
        "max_request_body_size": 1024,
        "max_request_header_size": 8192,
        "ident": None,
        "expose_tracebacks": False,
        "clear_untrusted_proxy_headers": True,
    }
)

#: winsock2.h: `#define SO_EXCLUSIVEADDRUSE ((int)(~SO_REUSEADDR))` = ~4 = -5.
#: CPython'un Windows yapısı sabiti `socket.SO_EXCLUSIVEADDRUSE` olarak verir
#: (3.11.9'da -5 doğrulandı); bu değer yalnız eksik olma ihtimaline karşı yedektir.
_WINSOCK_EXCLUSIVEADDRUSE: Final = -5
#: Port dolu (WSAEADDRINUSE) ya da başka bir soket onu özel tutuyor / sistem
#: ayırmış (WSAEACCES — Hyper-V dışlanan port aralıkları da bu kodu verir).
_WINERRORS_PORT_UNAVAILABLE: Final = frozenset({10048, 10013})

_HINT_NOT_FATAL: Final = "Yönetim işleri bundan etkilenmez."


class KatalogServerError(Exception):
    """Ağ Kataloğu açılamadı. ÖLÜMCÜL DEĞİLDİR: program açılmaya devam eder."""

    def __init__(self, message: str, *, hint: str = _HINT_NOT_FATAL) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    @property
    def full_message(self) -> str:
        """Günlüğe yazılan tek satırlık metin (ileti + varsa ipucu)."""
        return f"{self.message} {self.hint}" if self.hint else self.message


class KatalogPortInUseError(KatalogServerError):
    """Katalog portu başka bir program tarafından kullanılıyor ya da ayrılmış."""

    def __init__(self, port: int) -> None:
        super().__init__(
            f"Ağ Kataloğu açılamadı: {port} numaralı port başka bir program tarafından "
            "kullanılıyor ya da sistemce ayrılmış.",
            hint=(
                f"{_HINT_NOT_FATAL} Portu kullanan programı kapatıp Kütüphane Defteri'ni "
                "yeniden açın."
            ),
        )
        self.port = port


class KatalogSelfTestError(KatalogServerError):
    """Öz sınama geçmedi: katalog kapatılır (§4.2-2)."""


@dataclass(frozen=True)
class CatalogApp:
    """Sunulacak WSGI uygulaması ve öz sınamanın `/` yanıtında arayacağı imza."""

    application: WSGIApplication
    signature: bytes


def load_catalog() -> CatalogApp:
    """Katalog uygulamasını TEMBEL yükler.

    `katalog` paketi `backend/` altındadır ve `sys.path`'e `prepare_django` ile
    girer; bu yüzden katalog yalnız o adımdan SONRA kalkar (§4.1 değişmezi).
    """
    try:
        from katalog.app import SIGNATURE_META, application
    except ImportError as exc:
        raise KatalogServerError(
            "Ağ Kataloğu açılamadı: katalog dosyaları bulunamadı.",
            hint=f"{_HINT_NOT_FATAL} Sorun sürerse programı yeniden kurun.",
        ) from exc
    return CatalogApp(application=application, signature=SIGNATURE_META.encode("utf-8"))


def resolve_port(environ: Mapping[str, str]) -> int:
    """Katalog portu: `KD_KATALOG_PORT` (geliştirme/test; 0 = boş port) ya da 8765."""
    raw = environ.get(ENV_PORT, "").strip()
    if not raw:
        return DEFAULT_PORT
    if raw.isascii() and raw.isdigit() and int(raw) <= 65535:
        return int(raw)
    raise KatalogServerError(f"Ağ Kataloğu açılamadı: {ENV_PORT} değeri geçersiz.")


def _exclusive_addr_option() -> int:
    return int(getattr(socket, "SO_EXCLUSIVEADDRUSE", _WINSOCK_EXCLUSIVEADDRUSE))


def _is_port_unavailable(exc: OSError) -> bool:
    return (
        exc.errno == errno.EADDRINUSE
        or getattr(exc, "winerror", None) in _WINERRORS_PORT_UNAVAILABLE
    )


def _new_tcp_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def open_listen_socket(
    host: str,
    port: int,
    *,
    platform: str = sys.platform,
    socket_factory: Callable[[], socket.socket] = _new_tcp_socket,
) -> socket.socket:
    """Dinleme soketini açar: (Windows'ta özel kullanım) → bind → listen.

    Port doluysa `KatalogPortInUseError`, diğer soket hatalarında
    `KatalogServerError` yükseltir; iki durumda da soket kapatılır.
    """
    sock = socket_factory()
    try:
        if platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, _exclusive_addr_option(), 1)
        # Diğer platformlarda SO_REUSEADDR bilerek konmaz (modül belgesi).
        sock.bind((host, port))
        sock.listen(LISTEN_BACKLOG)
    except OSError as exc:
        sock.close()
        if _is_port_unavailable(exc):
            raise KatalogPortInUseError(port) from exc
        raise KatalogServerError("Ağ Kataloğu açılamadı: dinleme soketi kurulamadı.") from exc
    return sock


def verify_exclusive_bind(sock: socket.socket, *, platform: str = sys.platform) -> None:
    """Windows: waitress'in sonradan denediği `SO_REUSEADDR` özel kullanımı bozmadı mı?

    Özel kullanım kalkmışsa ya da adres paylaşımı açılmışsa katalog açılmaz
    (fail-closed). Sonuç, paket duman testinin (`--autotest`) kanıtı olarak
    günlüğe yazılır.
    """
    if platform != "win32":
        return
    exclusive = sock.getsockopt(socket.SOL_SOCKET, _exclusive_addr_option())
    shared = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
    logger.info(
        "Ağ Kataloğu soketi: özel kullanım %s, adres paylaşımı %s.",
        "açık" if exclusive else "KAPALI",
        "AÇIK" if shared else "kapalı",
    )
    if not exclusive or shared:
        raise KatalogServerError(
            "Ağ Kataloğu açılamadı: port başka programlarla paylaşılabilir durumda kaldı."
        )


def _waitress_factory(app: Any, **kwargs: Any) -> WSGIServerLike:
    """waitress TEMBEL içe aktarılır (yönetim sunucusundaki desenle aynı)."""
    from waitress.server import create_server  # type: ignore[import-untyped]

    server: WSGIServerLike = create_server(app, **kwargs)
    return server


class KatalogServer:
    """Katalog WSGI'sini kendi waitress örneğiyle arka plan iş parçacığında sunar.

    Yüzeyi yönetim `BackgroundServer`'ıyla uyumludur (`start`, `port`,
    `base_url`, `thread`, `stop`); farkı soketi kendisinin açmasıdır.
    """

    def __init__(
        self,
        app: WSGIApplication,
        *,
        host: str = LOOPBACK_HOST,
        port: int = DEFAULT_PORT,
        server_factory: ServerFactory | None = None,
        socket_opener: Callable[[str, int], socket.socket] | None = None,
        platform: str = sys.platform,
    ) -> None:
        if host not in ALLOWED_LISTEN_HOSTS:
            raise ValueError(f"Ağ Kataloğu bu sürümde yalnız {LOOPBACK_HOST} adresinde dinler.")
        if not 0 <= port <= 65535:
            raise ValueError(f"Geçersiz port: {port}")
        self._app = app
        self._host = host
        self._requested_port = port
        self._factory = server_factory or _waitress_factory
        self._platform = platform
        self._open_socket = socket_opener or (
            lambda h, p: open_listen_socket(h, p, platform=self._platform)
        )
        self._server: WSGIServerLike | None = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._stopping = threading.Event()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        """Dinlenen gerçek port (0 istendiyse işletim sisteminin seçtiği); kapalıyken 0."""
        if self._sock is None:
            return 0
        return int(self._sock.getsockname()[1])

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self.port}"

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    def start(self) -> str:
        """Soketi açar, waitress'i kurar ve `kd-katalog` iş parçacığını başlatır."""
        if self._server is not None:
            raise RuntimeError("Ağ Kataloğu zaten çalışıyor.")
        sock = self._open_socket(self._host, self._requested_port)
        try:
            server = self._factory(self._app, sockets=[sock], **WAITRESS_SETTINGS)
        except Exception as exc:  # noqa: BLE001 — her kurulum hatası aynı iletiye çıkar
            sock.close()
            raise KatalogServerError("Ağ Kataloğu açılamadı: sunucu kurulamadı.") from exc
        try:
            verify_exclusive_bind(sock, platform=self._platform)
        except (KatalogServerError, OSError):
            _close_quietly(server)
            sock.close()
            raise

        self._server, self._sock = server, sock
        self._stopping.clear()

        def _run() -> None:
            self._started.set()
            try:
                server.run()
            except Exception:  # noqa: BLE001 — iş parçacığı sessizce ölmesin
                if not self._stopping.is_set():
                    logger.exception("Ağ Kataloğu dinleyicisi beklenmedik biçimde durdu.")

        self._thread = threading.Thread(target=_run, name=THREAD_NAME, daemon=True)
        self._thread.start()
        logger.info("Ağ Kataloğu dinlemeye başladı (%s:%d).", self._host, self.port)
        return self.base_url

    def wait_until_started(self, *, timeout: float = 5.0) -> None:
        """İş parçacığının çalışmaya başlamasını bekler.

        Soket waitress'e verilmeden önce `listen` durumundadır: bağlantılar
        döngü başlamadan da kuyruğa girer, ayrıca bağlantı yoklaması gerekmez.
        """
        if not self._started.wait(timeout):
            raise KatalogServerError("Ağ Kataloğu açılamadı: sunucu yanıt vermedi.")

    def stop(self) -> None:
        """Dinleyiciyi ve iş parçacığı havuzunu kapatır (çıkışı bloklamaz)."""
        server, self._server = self._server, None
        sock, self._sock = self._sock, None
        thread, self._thread = self._thread, None
        self._stopping.set()
        if server is not None:
            _close_quietly(server)
            dispatcher = getattr(server, "task_dispatcher", None)
            if dispatcher is not None:
                dispatcher.shutdown(cancel_pending=True, timeout=2)
        if sock is not None:
            sock.close()  # waitress kapattıysa etkisizdir
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._started.clear()
        if server is not None:
            logger.info("Ağ Kataloğu kapatıldı.")


def _close_quietly(server: WSGIServerLike) -> None:
    try:
        server.close()
    except OSError:
        pass


def _fetch(conn: http.client.HTTPConnection, path: str) -> tuple[int, bytes]:
    conn.request("GET", path)
    response = conn.getresponse()
    return response.status, response.read()


def self_test(
    host: str,
    port: int,
    *,
    signature: bytes,
    management_paths: Sequence[str] = (HEALTH_PATH,),
    timeout: float = 5.0,
) -> None:
    """Öz sınama (§4.2-2): `/` imzayı döndürmeli, yönetim yolları 404 almalı.

    Yönetim yolunun 404'ü de imzayı taşımalıdır: yanıtı başka bir uygulama
    değil katalog vermiştir. Tek bir HTTP/1.1 bağlantısı kullanılır ve onu
    İSTEMCİ kapatır; TIME_WAIT istemcinin geçici portunda kalır, katalog
    portunda değil. Linux'ta `SO_REUSEADDR` konmadığı için katalog portunda
    kalan bir TIME_WAIT, hemen ardından gelen açılışta portu yaklaşık bir
    dakika "kullanımda" gösterirdi (21.09.2026 spike'ı).
    """
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        status, body = _fetch(conn, "/")
        if status != 200 or signature not in body:
            raise KatalogSelfTestError(
                "Ağ Kataloğu kapatıldı: öz sınamada ana sayfa beklenen yanıtı vermedi."
            )
        for path in management_paths:
            status, body = _fetch(conn, path)
            if status != 404 or signature not in body:
                raise KatalogSelfTestError(
                    "Ağ Kataloğu kapatıldı: öz sınamada yönetim yolu katalog portunda "
                    "yanıt verdi."
                )
    except (OSError, http.client.HTTPException) as exc:
        raise KatalogSelfTestError(
            "Ağ Kataloğu kapatıldı: öz sınama bağlantısı kurulamadı."
        ) from exc
    finally:
        conn.close()


def start_catalog(
    *,
    environ: Mapping[str, str] | None = None,
    loader: Callable[[], CatalogApp] | None = None,
) -> KatalogServer | None:
    """Ağ Kataloğunu kaldırır ve öz sınamadan geçirir; açılamazsa `None` döner.

    Hiçbir hata dışarı sızmaz: yönetim tarafı (pencere, API) her durumda
    açılmaya devam eder. Öz sınama geçmezse dinleyici kapatılır.
    """
    server: KatalogServer | None = None
    try:
        catalog = (loader or load_catalog)()
        port = resolve_port(os.environ if environ is None else environ)
        server = KatalogServer(catalog.application, host=LOOPBACK_HOST, port=port)
        server.start()
        server.wait_until_started()
        self_test(server.host, server.port, signature=catalog.signature)
    except KatalogServerError as exc:
        logger.warning("%s", exc.full_message)
        stop_catalog(server)
        return None
    except Exception:  # noqa: BLE001 — katalog hatası açılışı durdurmaz
        logger.exception("Ağ Kataloğu açılırken beklenmeyen hata; yönetim işleri etkilenmedi.")
        stop_catalog(server)
        return None
    logger.info("Ağ Kataloğu hazır (%s:%d); öz sınama geçti.", server.host, server.port)
    return server


def stop_catalog(server: KatalogServer | None) -> None:
    """Katalog açıksa kapatır; kapanış hatası çıkışı durdurmaz."""
    if server is None:
        return
    try:
        server.stop()
    except Exception:  # noqa: BLE001 — çıkış her durumda sürer
        logger.exception("Ağ Kataloğu kapatılırken hata oluştu (yok sayıldı).")
