"""Tek kopya kanalı — ikinci açılış sinyali ve kapatma olayı (tasarım §4.2-1, §4.2-5).

Çalışan program iki komut dinler:

    goster  → pencere öne gelir (ikinci açılış; ikinci süreç 0 koduyla çıkar)
    kapat   → düzenli kapanış (kurucu ve kaldırıcı; pencere, iki sunucu, tepsi)

**Windows:** adlı, otomatik sıfırlanan olaylar `KutuphaneDefteri.Goster` ve
`KutuphaneDefteri.Kapat` (§2.3). Kurucu `.Kapat`'ı `[Code]` içinden açıp
işaretler (packaging/windows/kutuphane-defteri.iss). Olay, bekleyen iş parçacığı
onu tüketene dek işaretli kalır: komut açılışın ortasında gelirse kaybolmaz,
dinleyici başlayınca işlenir. Olaylar oturum ad alanındadır (`Local\\`); başka
bir Windows oturumundaki kopyaya ulaşmaz — kurucu o durumda `Global\\` mutex'i
görür ve bekler.

**Linux:** veri kök dizininde UNIX soketi (`kanal.sock`, yalnız sahibi okur ve
yazar); tek satırlık komut. Soket tek kopya kilidi alındıktan SONRA kurulur,
bu yüzden yerinde kalmış eski bir soket dosyası her zaman bayattır ve silinir.

Kanal yalnız pencereli (normal) açılışta kurulur; `--autotest` ve
`--geri-yukle` kurmaz. Kanal kurulamazsa program yine açılır (günlüğe yazılır):
ikinci açılış o durumda "zaten çalışıyor" iletisine, kurucu mutex beklemesine
düşer.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final, Protocol

from desktop import win32_objects

logger = logging.getLogger("kutuphane_defteri.kanal")

COMMAND_SHOW: Final = "goster"
COMMAND_QUIT: Final = "kapat"
COMMANDS: Final = frozenset({COMMAND_SHOW, COMMAND_QUIT})

SHOW_EVENT_NAME: Final = "KutuphaneDefteri.Goster"
QUIT_EVENT_NAME: Final = "KutuphaneDefteri.Kapat"
_EVENT_NAMES: Final = {COMMAND_SHOW: SHOW_EVENT_NAME, COMMAND_QUIT: QUIT_EVENT_NAME}

SOCKET_FILE_NAME: Final = "kanal.sock"
#: `sockaddr_un.sun_path` sınırı (Linux 108 bayt, sonlandırıcı dahil).
_MAX_SOCKET_PATH_BYTES: Final = 107
_ACCEPT_POLL_SECONDS: Final = 0.25
_CLIENT_TIMEOUT_SECONDS: Final = 2.0
_MAX_COMMAND_BYTES: Final = 64

THREAD_NAME: Final = "kd-kanal"
_JOIN_TIMEOUT_SECONDS: Final = 2.0

CommandHandler = Callable[[str], None]


class ChannelError(OSError):
    """Kanal kurulamadı (ölümcül değil)."""


class CommandChannel(Protocol):
    """Çalışan kopyanın komut dinleyicisi."""

    def start(self, handler: CommandHandler) -> None: ...

    def close(self) -> None: ...


class EventApi(Protocol):
    """Adlı olay işlemleri — Windows'ta `desktop.win32_objects`, testte sahte."""

    def create_event(self, name: str | None) -> int | None: ...

    def open_event(self, name: str) -> int | None: ...

    def set_event(self, handle: int) -> bool: ...

    def wait_any(self, handles: Sequence[int]) -> int | None: ...

    def close_handle(self, handle: int) -> None: ...


class _Win32EventApi:
    """`EventApi`'nin gerçek (ctypes) karşılığı."""

    def create_event(self, name: str | None) -> int | None:
        return win32_objects.create_event(name)

    def open_event(self, name: str) -> int | None:
        return win32_objects.open_event(name)

    def set_event(self, handle: int) -> bool:
        return win32_objects.set_event(handle)

    def wait_any(self, handles: Sequence[int]) -> int | None:
        return win32_objects.wait_any(handles)

    def close_handle(self, handle: int) -> None:
        win32_objects.close_handle(handle)


def _dispatch(handler: CommandHandler, command: str) -> None:
    logger.info("Tek kopya kanalından komut alındı: %s.", command)
    try:
        handler(command)
    except Exception:  # noqa: BLE001 — dinleyici iş parçacığı ölmesin
        logger.exception("Kanal komutu işlenirken hata oluştu (%s).", command)


class NamedEventChannel:
    """Windows: `Goster`/`Kapat` olaylarını bekleyen dinleyici."""

    def __init__(self, api: EventApi | None = None) -> None:
        self._api: EventApi = api or _Win32EventApi()
        self._handles: list[int] = []
        try:
            # Sıra = öncelik: aynı anda işaretlilerse önce durdurma, sonra kapatma.
            stop = self._create(None)
            quit_event = self._create(QUIT_EVENT_NAME)
            show = self._create(SHOW_EVENT_NAME)
        except ChannelError:
            self._close_handles()
            raise
        self._stop, self._wait_order = stop, (stop, quit_event, show)
        self._commands: tuple[str | None, ...] = (None, COMMAND_QUIT, COMMAND_SHOW)
        self._thread: threading.Thread | None = None

    def _create(self, name: str | None) -> int:
        handle = self._api.create_event(name)
        if handle is None:
            raise ChannelError(f"Adlı olay kurulamadı: {name or 'durdurma'}")
        self._handles.append(handle)
        return handle

    def start(self, handler: CommandHandler) -> None:
        if self._thread is not None:
            raise RuntimeError("Kanal zaten dinleniyor.")

        def _loop() -> None:
            while True:
                index = self._api.wait_any(self._wait_order)
                command = self._commands[index] if index is not None else None
                if command is None:
                    return  # durdurma ya da bekleme hatası
                _dispatch(handler, command)

        self._thread = threading.Thread(target=_loop, name=THREAD_NAME, daemon=True)
        self._thread.start()

    def close(self) -> None:
        thread, self._thread = self._thread, None
        if not self._handles:
            return
        if thread is not None:
            self._api.set_event(self._stop)
            thread.join(timeout=_JOIN_TIMEOUT_SECONDS)
        self._close_handles()

    def _close_handles(self) -> None:
        handles, self._handles = self._handles, []
        for handle in handles:
            self._api.close_handle(handle)


def socket_path(root: Path) -> Path:
    """Linux kanal soketinin yolu (veri kök dizininde, kilit dosyasının yanında)."""
    return root / SOCKET_FILE_NAME


def _check_socket_path(path: Path) -> None:
    if len(os.fsencode(path)) > _MAX_SOCKET_PATH_BYTES:
        raise ChannelError("Kanal soketi yolu çok uzun (veri dizini derin bir klasörde).")


def _open_unix_listener(path: Path) -> socket.socket:
    """Soketi kurar (yalnız sahibi erişir); Windows'ta kanal adlı olaylardır."""
    if sys.platform == "win32":
        raise ChannelError("UNIX soketi kanalı Windows'ta kullanılmaz (adlı olaylar).")
    _check_socket_path(path)
    # Tek kopya kilidi bizde: yerinde duran soket dosyası bayattır.
    path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(4)
        server.settimeout(_ACCEPT_POLL_SECONDS)
    except OSError as exc:
        server.close()
        path.unlink(missing_ok=True)
        raise ChannelError("Kanal soketi kurulamadı.") from exc
    return server


class UnixSocketChannel:
    """Linux: veri kök dizinindeki UNIX soketini dinleyen kanal."""

    def __init__(self, root: Path) -> None:
        self._path: Path = socket_path(root)
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._server: socket.socket | None = _open_unix_listener(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def start(self, handler: CommandHandler) -> None:
        if self._thread is not None:
            raise RuntimeError("Kanal zaten dinleniyor.")
        if self._server is None:
            raise RuntimeError("Kanal kapatılmış.")
        server: socket.socket = self._server

        def _loop() -> None:
            while not self._stopping.is_set():
                try:
                    conn, _ = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if not self._stopping.is_set():
                        logger.exception("Kanal soketi beklenmedik biçimde kapandı.")
                    return
                command = _read_command(conn)
                if command is not None:
                    _dispatch(handler, command)

        self._thread = threading.Thread(target=_loop, name=THREAD_NAME, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stopping.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=_JOIN_TIMEOUT_SECONDS)
        server, self._server = self._server, None
        if server is not None:
            server.close()
            self._path.unlink(missing_ok=True)


def _read_command(conn: socket.socket) -> str | None:
    """Bağlantıdan tek komut okur; bilinmeyen ya da bozuk girdi `None` (yok sayılır)."""
    with conn:
        try:
            conn.settimeout(_CLIENT_TIMEOUT_SECONDS)
            raw = conn.recv(_MAX_COMMAND_BYTES)
        except OSError:
            return None
    command = raw.decode("ascii", errors="replace").strip()
    if command not in COMMANDS:
        logger.warning("Kanal soketine bilinmeyen komut geldi; yok sayıldı.")
        return None
    return command


def open_channel(
    root: Path,
    *,
    platform: str = sys.platform,
    event_api: EventApi | None = None,
) -> CommandChannel | None:
    """Platforma uygun kanalı kurar; kurulamazsa günlüğe yazıp `None` döner."""
    try:
        if platform == "win32":
            return NamedEventChannel(event_api)
        if platform.startswith("linux"):
            return UnixSocketChannel(root)
    except OSError as exc:  # ChannelError dahil
        logger.warning("Tek kopya kanalı kurulamadı: %s", exc)
        return None
    logger.info("Bu platformda tek kopya kanalı yok (%s).", platform)
    return None


def send_command(
    root: Path,
    command: str,
    *,
    platform: str = sys.platform,
    event_api: EventApi | None = None,
) -> bool:
    """Çalışan kopyaya komut gönderir; ulaştıysa `True`.

    `False`: çalışan kopya kanal kurmamış (ör. `--autotest`), henüz kurmamış ya
    da kanal bozuk. Çağıran bu durumda eski davranışa ("zaten çalışıyor") düşer.
    """
    if command not in COMMANDS:
        raise ValueError(f"Bilinmeyen kanal komutu: {command}")
    if platform == "win32":
        api: EventApi = event_api or _Win32EventApi()
        handle = api.open_event(_EVENT_NAMES[command])
        if handle is None:
            return False
        try:
            return api.set_event(handle)
        finally:
            api.close_handle(handle)
    if not platform.startswith("linux"):
        return False
    if sys.platform == "win32":
        return False  # sahte platform adıyla Windows'ta UNIX soketi denenmez
    path = socket_path(root)
    try:
        _check_socket_path(path)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(_CLIENT_TIMEOUT_SECONDS)
            client.connect(str(path))
            client.sendall(f"{command}\n".encode("ascii"))
    except OSError:
        return False
    return True
