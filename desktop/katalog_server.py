"""Ağ Kataloğu sunucusu — ikinci waitress dinleyicisi (tasarım §4.1, §4.2-2, §5.2, §5.7).

Yönetim sunucusundan (`desktop/server.py`, `kd-wsgi`) tamamen ayrıdır (T3): kendi
waitress örneği, kendi iş parçacığı havuzu ve Django'dan bağımsız WSGI uygulaması
(`backend/katalog/app.py`) vardır. Yönetim API'si bu porttan hiçbir koşulda
yanıt vermez; öz sınama bunu her açılışta yoklar.

**Dinleme adresi (F5).** Üç biçim vardır ve biri dışında hepsi İZİN ister:

- `127.0.0.1` (loopback): yalnız bu bilgisayar. Paket duman testi (`--autotest`)
  soket yolunu burada kanıtlar; izin gerekmez.
- `0.0.0.0` (tüm arayüzler, varsayılan dinleme kipi) ya da **seçili LAN IP'si**
  ("yalnız seçili IP'de dinle"): okul ağı. `KatalogServer` bu adresleri YALNIZ
  güvenlik duvarı denetiminin beş maddesi geçtiyse kabul eder
  (`ag_izni.dinlemeye_izin`, `desktop/guvenlik_duvari.py`; §5.7, §5.10-10).
  İzin nesnesi olmadan ya da denetim geçmemişken kurucu `KatalogAgIzniYok`
  yükseltir: kural yoksa ya da tutmuyorsa katalog okul ağında DİNLEMEZ.

Tüm arayüz adresi yalnız bu dosyada geçer (§5.10-1 koruma testi); yönetim
sunucusu hiçbir koşulda `127.0.0.1` dışında dinlemez (`desktop/server.py`).
Hangi adreste dinleneceğine `desktop/katalog_kontrol.py` karar verir; o modül
bu dosyadaki `dinleme_hostu` işlevini çağırır.

**Soketi kendimiz açarız** (§5.2, R9 §2) ve waitress'e `sockets=[...]` ile veririz:

- Windows'ta `SO_EXCLUSIVEADDRUSE` bind'den ÖNCE konur: aynı adrese başka bir
  süreç `SO_REUSEADDR` ile bağlanıp katalog trafiğini ele geçiremez. Katalog
  artık okul ağı adresinde (tüm arayüzler ya da seçili IP) dinlediği için F0
  spike'ındaki açık (TB12: katalog 127.0.0.1'deyken başka bir süreç
  `0.0.0.0:8765`'e bağlanabiliyordu) kapanır: tüm arayüz dinleyicisi özel
  kullanımla portun bütün adreslerini tutar; seçili IP kipinde o IP'ye gelen
  trafik en belirgin bağa, yani kataloğa gider.
- Linux'ta `SO_REUSEADDR` KONUR (TB10 kararı, F5). Linux'ta bu seçenek Windows'taki
  gibi port paylaşımı DEĞİLDİR: dinleyen bir soketin adresine ikinci bir soket
  seçenekle de bağlanamaz (çekirdek dinleyen soketle çakışmayı her durumda
  reddeder; koruma testi). Tek etkisi, istemci bağlantılarını sunucunun kapattığı
  durumda portta kalan TIME_WAIT kayıtlarının katalogun yeniden açılışını (port
  ya da IP değişikliği, aç/kapa, programın yeniden başlatılması) yaklaşık bir
  dakika "port kullanımda" diye engellememesidir. Ağ istemcileri geldiğinde bu
  durum olağandır (waitress `channel_timeout` ve `Connection: close` ile
  bağlantıyı kendisi kapatır).
- waitress 3.0.2 verilen sokette de `set_reuse_addr()` çağırır. Windows'ta özel
  kullanımlı sokette bu çağrı WinError 10022 ile düşer ve waitress onu yutar;
  soket özel kalır (21.09.2026 spike). Sonuç `verify_exclusive_bind` ile her
  açılışta doğrulanır ve günlüğe yazılır.

**IP başına eşzamanlı bağlantı sınırı (TB2, §4.3 GA-12).** waitress'in
`connection_limit`'i sunucu genelidir; yavaş gönderen tek bir istemci havuzu
doldurabilir. Katalog waitress'in `TcpWSGIServer`'ının alt sınıfıyla kurulur:
kabul anında (`handle_accept`) aynı uzak IP'den açık bağlantı sayısı
`IP_BASINA_BAGLANTI_SINIRI`'na ulaşmışsa yeni bağlantı hemen, yanıt yazılmadan
kapatılır (SO_LINGER 0: sunucuda TIME_WAIT birikmez). Sayaç kişisizdir: yalnız
reddedilen bağlantı SAYISI tutulur, IP yazılmaz (§5.5). İstek başına hız
sınırı (token-bucket) katalog uygulamasındadır.

**Hata ölümcül değildir.** Katalog açılamazsa (`KatalogServerError`) yönetim
tarafı açılmaya devam eder; ileti günlüğe ve Ağ Doktoru'nun son hatasına düşer.
Bu yüzden istisna ailesi `desktop.errors.StartupError`'dan bilerek türemez.

**Günlük.** Erişim günlüğü yoktur (§5.5): IP, yol ve arama terimi yazılmaz.
"""

from __future__ import annotations

import errno
import functools
import http.client
import ipaddress
import logging
import os
import socket
import struct
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Protocol

from desktop.server import HEALTH_PATH, ServerFactory, WSGIServerLike

if TYPE_CHECKING:
    from wsgiref.types import WSGIApplication

logger = logging.getLogger("kutuphane_defteri.katalog")

THREAD_NAME: Final = "kd-katalog"
LOOPBACK_HOST: Final = "127.0.0.1"
#: Okul ağına açılış adresi: YALNIZ güvenlik duvarı denetimi geçtiyse (§5.7).
ALL_INTERFACES_HOST: Final = "0.0.0.0"  # noqa: S104 — bilerek; bkz. modül belgesi

#: Dinleme kipleri (`KatalogAyari` ile aynı kodlar).
DINLEME_TUM: Final = "ALL"
DINLEME_SECILI: Final = "SELECTED"

DEFAULT_PORT: Final = 8765
#: Yalnız geliştirme ve test içindir (§2.3); gerçek kaynak `KatalogAyari`.
ENV_PORT: Final = "KD_KATALOG_PORT"
LISTEN_BACKLOG: Final = 128
#: Kabul anında aynı uzak IP'den açık bağlantı tavanı (TB2, §5.2 "ör. 20").
#: Bir tarayıcı bir sunucuya en çok 6 bağlantı açar; 20, aynı IP'yi paylaşan
#: (ör. NAT arkasındaki) üç tarayıcıya yeter.
IP_BASINA_BAGLANTI_SINIRI: Final = 20

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
#: Seçili IP artık bu bilgisayarda yok (WSAEADDRNOTAVAIL / EADDRNOTAVAIL).
_WINERRORS_ADDR_NOT_AVAILABLE: Final = frozenset({10049})

_HINT_NOT_FATAL: Final = "Yönetim işleri bundan etkilenmez."


class AgIzni(Protocol):
    """Okul ağında dinleme izni (`guvenlik_duvari.GuvenlikDuvariDenetimi`)."""

    @property
    def dinlemeye_izin(self) -> bool: ...


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
                f"{_HINT_NOT_FATAL} Portu kullanan programı kapatın; Ağ Kataloğu kısa süre "
                "içinde kendiliğinden yeniden denenir."
            ),
        )
        self.port = port


class KatalogAdresYokError(KatalogServerError):
    """Seçili IP bu bilgisayarda artık yok (adres değişti ya da ağ kablosu çıktı)."""

    def __init__(self) -> None:
        super().__init__(
            "Ağ Kataloğu açılamadı: seçili IP adresi bu bilgisayarda artık yok.",
            hint=f"{_HINT_NOT_FATAL} Ayarlar → Ağ Kataloğu → Dinleme'den yeni adresi seçin.",
        )


class KatalogArayuzOkunamadiError(KatalogServerError):
    """Ağ bağlantılarının listesi okunamadı; seçili IP denetlenemedi (geçici hata)."""

    def __init__(self) -> None:
        super().__init__(
            "Ağ Kataloğu açılamadı: bu bilgisayarın ağ bağlantıları okunamadı, seçili IP "
            "adresi denetlenemedi.",
        )


class KatalogSelfTestError(KatalogServerError):
    """Öz sınama geçmedi: katalog kapatılır (§4.2-2)."""


class KatalogAgIzniYok(ValueError):
    """Okul ağı adresi güvenlik duvarı denetimi geçmeden istendi (§5.10-10)."""


@dataclass(frozen=True)
class CatalogApp:
    """Sunulacak WSGI uygulaması ve öz sınamanın `/` yanıtında arayacağı imza."""

    application: WSGIApplication
    signature: bytes


def load_catalog() -> CatalogApp:
    """Süreç içi katalog uygulamasını (`katalog.app.application`) TEMBEL yükler.

    `katalog` paketi `backend/` altındadır ve `sys.path`'e `prepare_django` ile
    girer; bu yüzden katalog yalnız o adımdan SONRA kalkar (§4.1 değişmezi).
    Uygulama veriye `prepare_django` sırasında bağlanır
    (`apps.kutuphane.ag_katalogu.varsayilan_katalogu_kur`, `KutuphaneConfig.ready`);
    Django kurulmadan yüklenirse `/` imzalı ana sayfayı döndürür, veri sayfaları
    503 verir (öz sınama ve masaüstü testleri bu hâli kullanır).
    """
    try:
        from katalog.app import SIGNATURE_META, application
    except ImportError as exc:
        raise KatalogServerError(
            "Ağ Kataloğu açılamadı: katalog dosyaları bulunamadı.",
            hint=f"{_HINT_NOT_FATAL} Sorun sürerse programı yeniden kurun.",
        ) from exc
    return CatalogApp(application=application, signature=str(SIGNATURE_META).encode("utf-8"))


def resolve_port(environ: Mapping[str, str]) -> int:
    """Duman testi portu: `KD_KATALOG_PORT` (geliştirme/test; 0 = boş port) ya da 8765."""
    raw = environ.get(ENV_PORT, "").strip()
    if not raw:
        return DEFAULT_PORT
    if raw.isascii() and raw.isdigit() and int(raw) <= 65535:
        return int(raw)
    raise KatalogServerError(f"Ağ Kataloğu açılamadı: {ENV_PORT} değeri geçersiz.")


def dinleme_hostu(dinleme_kipi: str, secili_ip: str) -> str:
    """Ayardaki dinleme kipinden dinleme adresi: tüm arayüzler ya da seçili IP.

    Tüm arayüz adresinin geçtiği TEK yer burasıdır (§5.10-1). Seçili IP geçerli
    bir aday değilse `ValueError`.
    """
    if dinleme_kipi == DINLEME_TUM:
        return ALL_INTERFACES_HOST
    if dinleme_kipi == DINLEME_SECILI:
        if not _lan_adresi_mi(secili_ip):
            raise ValueError("Seçili IP geçerli bir yerel ağ adresi değil.")
        return secili_ip
    raise ValueError(f"Bilinmeyen dinleme kipi: {dinleme_kipi}")


def tum_arayuzler_mi(host: str) -> bool:
    return host == ALL_INTERFACES_HOST


def _lan_adresi_mi(host: str) -> bool:
    try:
        adres = ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return not (
        adres.is_loopback
        or adres.is_link_local
        or adres.is_multicast
        or adres.is_unspecified
        or adres.is_reserved
        or int(adres) == 0xFFFFFFFF
    )


def _exclusive_addr_option() -> int:
    return int(getattr(socket, "SO_EXCLUSIVEADDRUSE", _WINSOCK_EXCLUSIVEADDRUSE))


def _is_port_unavailable(exc: OSError) -> bool:
    return (
        exc.errno == errno.EADDRINUSE
        or getattr(exc, "winerror", None) in _WINERRORS_PORT_UNAVAILABLE
    )


def _is_addr_not_available(exc: OSError) -> bool:
    return (
        exc.errno == errno.EADDRNOTAVAIL
        or getattr(exc, "winerror", None) in _WINERRORS_ADDR_NOT_AVAILABLE
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
    """Dinleme soketini açar: (Windows'ta özel kullanım / diğerlerinde SO_REUSEADDR) → bind → listen.

    Port doluysa `KatalogPortInUseError`, adres bu bilgisayarda yoksa
    `KatalogAdresYokError`, diğer soket hatalarında `KatalogServerError`
    yükseltir; her durumda soket kapatılır.
    """
    sock = socket_factory()
    try:
        if platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, _exclusive_addr_option(), 1)
        else:
            # TB10 (F5): Linux'ta port paylaşımı değildir, yalnız TIME_WAIT'i aşar
            # (modül belgesi). Dinleyen sokete ikinci bağ yine reddedilir.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(LISTEN_BACKLOG)
    except OSError as exc:
        sock.close()
        if _is_port_unavailable(exc):
            raise KatalogPortInUseError(port) from exc
        if _is_addr_not_available(exc):
            raise KatalogAdresYokError() from exc
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


# ------------------------------------------------ waitress: IP başına sınır (TB2)


def _abortive_close(conn: socket.socket) -> None:
    """Bağlantıyı RST ile kapatır: reddedilen istemci için sunucuda TIME_WAIT kalmaz."""
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    except OSError:
        pass
    try:
        conn.close()
    except OSError:
        pass


@functools.cache
def katalog_sunucu_sinifi() -> type:
    """waitress `TcpWSGIServer`'ının kabul anında IP başına sınır koyan alt sınıfı.

    waitress TEMBEL içe aktarılır (yönetim sunucusundaki desen); sınıf ilk
    istekte bir kez kurulur.
    """
    from waitress.server import TcpWSGIServer  # type: ignore[import-untyped]

    class KatalogWSGIServer(TcpWSGIServer):  # type: ignore[misc]
        """`handle_accept`: aynı IP'den açık bağlantı tavana ulaştıysa yeni bağlantı kapatılır."""

        ip_basina_sinir: int = IP_BASINA_BAGLANTI_SINIRI
        reddedilen: int = 0

        def ip_baglanti_sayisi(self, ip: str) -> int:
            sayi = 0
            for kanal in list(self.active_channels.values()):
                adres = getattr(kanal, "addr", None)
                if isinstance(adres, tuple) and adres and adres[0] == ip:
                    sayi += 1
            return sayi

        def handle_accept(self) -> None:
            try:
                kabul = self.accept()
                if kabul is None:
                    return
                conn, addr = kabul
                self.set_socket_options(conn)
            except OSError:
                # waitress'in kendi davranışı: sahte soket ya da istemci çoktan kapattı.
                return
            addr = self.fix_addr(addr)
            ip = addr[0] if isinstance(addr, tuple) and addr else ""
            if self.ip_baglanti_sayisi(ip) >= self.ip_basina_sinir:
                # Kişisiz sayaç: IP yazılmaz (§5.5).
                self.reddedilen += 1
                _abortive_close(conn)
                return
            self.channel_class(self, conn, addr, self.adj, map=self._map)

    return KatalogWSGIServer


def _turkce_hata_yanitlari(server: Any) -> None:
    """TB11: waitress'in kendi 400/413/431/500 yanıtları Türkçe ve CSP'li olsun.

    Kanca katalog paketindedir (`katalog.waitress_hatalari.uygula`): sunucu
    ÖRNEĞİNİN kanal sınıfını, o anki sınıfı taban alarak değiştirir; yönetim
    sunucusu özgün waitress sınıflarıyla kalır. Paket yoksa (eski kurulum)
    waitress'in özgün yanıtları kalır.
    """
    try:
        from katalog.waitress_hatalari import uygula
    except ImportError:
        logger.warning("Ağ Kataloğu: Türkçe hata sayfaları yüklenemedi.")
        return
    uygula(server)


def _katalog_waitress_factory(app: Any, **kwargs: Any) -> WSGIServerLike:
    """`waitress.create_server`'ın tek soketli dalı, katalog alt sınıfıyla (TB2) + TB11."""
    from waitress.adjustments import Adjustments  # type: ignore[import-untyped]
    from waitress.task import ThreadedTaskDispatcher  # type: ignore[import-untyped]

    adj = Adjustments(**kwargs)
    soketler = list(adj.sockets)
    if len(soketler) != 1:
        raise ValueError("Ağ Kataloğu tek soketle kurulur.")
    sock = soketler[0]
    dispatcher = ThreadedTaskDispatcher()
    dispatcher.set_thread_count(adj.threads)
    sinif = katalog_sunucu_sinifi()
    server: WSGIServerLike = sinif(
        app,
        {},
        True,
        sock,
        dispatcher=dispatcher,
        adj=adj,
        bind_socket=False,
        sockinfo=(sock.family, sock.type, sock.proto, sock.getsockname()),
    )
    _turkce_hata_yanitlari(server)
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
        ag_izni: AgIzni | None = None,
        server_factory: ServerFactory | None = None,
        socket_opener: Callable[[str, int], socket.socket] | None = None,
        platform: str = sys.platform,
    ) -> None:
        if host != LOOPBACK_HOST:
            if not (tum_arayuzler_mi(host) or _lan_adresi_mi(host)):
                raise ValueError(
                    f"Ağ Kataloğu yalnız {LOOPBACK_HOST}, tüm arayüzler ya da bu bilgisayarın "
                    "yerel ağ adresinde dinler."
                )
            if ag_izni is None or not ag_izni.dinlemeye_izin:
                # §5.10-10: kural yoksa ya da tutmuyorsa okul ağında DİNLEMEZ.
                raise KatalogAgIzniYok(
                    "Ağ Kataloğu okul ağında yalnız güvenlik duvarı denetimi geçtiğinde dinler."
                )
        if not 0 <= port <= 65535:
            raise ValueError(f"Geçersiz port: {port}")
        self._app = app
        self._host = host
        self._requested_port = port
        self._factory: ServerFactory = server_factory or _katalog_waitress_factory
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
        """Dinleme adresi (tüm arayüzler, seçili IP ya da loopback)."""
        return self._host

    @property
    def tum_arayuzler(self) -> bool:
        return tum_arayuzler_mi(self._host)

    @property
    def baglanti_hostu(self) -> str:
        """Bu bilgisayardan bağlanılacak adres: tüm arayüz adresine bağlantı kurulamaz (§5.2)."""
        return LOOPBACK_HOST if self.tum_arayuzler else self._host

    @property
    def port(self) -> int:
        """Dinlenen gerçek port (0 istendiyse işletim sisteminin seçtiği); kapalıyken 0."""
        if self._sock is None:
            return 0
        return int(self._sock.getsockname()[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.baglanti_hostu}:{self.port}"

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    @property
    def reddedilen_baglanti(self) -> int:
        """IP başına sınırda reddedilen bağlantı sayısı (kişisiz sayaç)."""
        return int(getattr(self._server, "reddedilen", 0) or 0)

    def start(self) -> str:
        """Soketi açar, waitress'i kurar ve `kd-katalog` iş parçacığını başlatır."""
        if self._server is not None:
            raise RuntimeError("Ağ Kataloğu zaten çalışıyor.")
        sock = self._open_socket(self._host, self._requested_port)
        try:
            server = self._factory(self._app, sockets=[sock], **WAITRESS_SETTINGS)
        except Exception as exc:  # noqa: BLE001 — her kurulum hatası aynı iletiye çıkar
            sock.close()
            raise KatalogServerError("Ağ Kataloğu açılamadı: dinleyici kurulamadı.") from exc
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
        logger.info(
            "Ağ Kataloğu dinlemeye başladı (%s, port %d).",
            "tüm arayüzler" if self.tum_arayuzler else self._host,
            self.port,
        )
        return self.base_url

    def wait_until_started(self, *, timeout: float = 5.0) -> None:
        """İş parçacığının çalışmaya başlamasını bekler.

        Soket waitress'e verilmeden önce `listen` durumundadır: bağlantılar
        döngü başlamadan da kuyruğa girer, ayrıca bağlantı yoklaması gerekmez.
        """
        if not self._started.wait(timeout):
            raise KatalogServerError("Ağ Kataloğu açılamadı: dinleyici başlamadı.")

    def stop(self) -> None:
        """Dinleyiciyi, açık kanalları ve iş parçacığı havuzunu kapatır (çıkışı bloklamaz).

        Açık istemci kanalları da kapanır (`wasyncore.close_all(map)`): geri
        yüklemede kanallar kapatılır (§5.3-3), port bir sonraki açılışta boştur.
        """
        server, self._server = self._server, None
        sock, self._sock = self._sock, None
        thread, self._thread = self._thread, None
        self._stopping.set()
        if server is not None:
            _close_quietly(server)
            _close_channels(server)
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


def _close_channels(server: WSGIServerLike) -> None:
    """Sunucunun soket haritasındaki bütün kanalları kapatır (waitress `wasyncore.close_all`)."""
    harita = getattr(server, "_map", None)
    if not isinstance(harita, dict) or not harita:
        return
    try:
        from waitress import wasyncore  # type: ignore[import-untyped]

        wasyncore.close_all(harita, ignore_all=True)
    except Exception:  # noqa: BLE001 — kapanış sürmeli
        logger.warning("Ağ Kataloğu kanalları kapatılamadı.", exc_info=True)


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
    portunda değil. `host` bağlanılabilir bir adrestir (tüm arayüz adresi
    değil; `KatalogServer.baglanti_hostu`).
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


def dinleyici_ayakta_mi(ip: str, port: int, *, signature: bytes, timeout: float = 3.0) -> bool:
    """Ağ Doktoru öz sınaması: bu arayüzde katalog yanıt veriyor mu?

    GÜVENLİK DUVARINI YA DA VLAN'I KANITLAMAZ: makinenin kendi IP'sine yapılan
    bağlantı loopback'ten geçer (§5.9). Ekran bunu uyarıyla söyler ve başka
    bilgisayar için `Test-NetConnection` komutu verir.
    """
    conn = http.client.HTTPConnection(ip, port, timeout=timeout)
    try:
        status, body = _fetch(conn, "/")
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()
    return status == 200 and signature in body


def start_catalog(
    *,
    environ: Mapping[str, str] | None = None,
    loader: Callable[[], CatalogApp] | None = None,
) -> KatalogServer | None:
    """Loopback'te katalog kaldırır ve öz sınamadan geçirir; açılamazsa `None` döner.

    Paket duman testi (`--autotest`) içindir: soket yolunun (Windows'ta
    `SO_EXCLUSIVEADDRUSE`) gerçekten çalıştığını ayar ve güvenlik duvarından
    bağımsız kanıtlar. Olağan açılışta katalogu `desktop/katalog_kontrol.py`
    ayara göre kaldırır. Hiçbir hata dışarı sızmaz.
    """
    server: KatalogServer | None = None
    try:
        catalog = (loader or load_catalog)()
        port = resolve_port(os.environ if environ is None else environ)
        server = KatalogServer(
            catalog.application,
            host=LOOPBACK_HOST,
            port=port,
        )
        server.start()
        server.wait_until_started()
        self_test(server.baglanti_hostu, server.port, signature=catalog.signature)
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
