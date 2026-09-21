"""Ağ Kataloğu sunucusu testleri (tasarım §4.1, §4.2-2, §5.2, §5.10-1).

Bölümler: port ayarı · dinleme soketi (Windows'ta SO_EXCLUSIVEADDRUSE, diğer
platformlarda SO_REUSEADDR yok) · waitress ayarları · `KatalogServer` · öz
sınama · `start_catalog` (hata ölümcül değil) · `main.py` bağlaması · koruma
testleri (§5.10-1: yönetim sunucusu yalnız 127.0.0.1; `0.0.0.0` yalnız
`katalog_server.py`'de).

Katalog uygulaması `backend/katalog/` altındadır; paketli programda `sys.path`'e
`prepare_django` ile girer, burada fikstür ekler.
"""

from __future__ import annotations

import ast
import errno
import http.client
import logging
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from desktop import katalog_server
from desktop import main as main_mod
from desktop.errors import EXIT_OK, EXIT_SERVER_FAILED, StartupError, WebViewUnavailableError
from desktop.katalog_server import (
    ALL_INTERFACES_HOST,
    ALLOWED_LISTEN_HOSTS,
    DEFAULT_PORT,
    ENV_PORT,
    LOOPBACK_HOST,
    THREAD_NAME,
    WAITRESS_SETTINGS,
    CatalogApp,
    KatalogPortInUseError,
    KatalogSelfTestError,
    KatalogServer,
    KatalogServerError,
    load_catalog,
    open_listen_socket,
    resolve_port,
    self_test,
    start_catalog,
    stop_catalog,
    verify_exclusive_bind,
)
from desktop.paths import ENV_APP_HOME, resolve_app_paths
from desktop.server import DEFAULT_HOST, HEALTH_PATH, BackgroundServer, find_free_port

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DESKTOP_DIR = REPO_ROOT / "desktop"

# Testler tüm arayüz adresini bilerek yazar (reddedildiğini ve yalnız sabitte geçtiğini
# sınamak için); ruff S104 uyarısı tek yerde susturulur.
TUM_ARAYUZ = "0.0.0.0"  # noqa: S104
IMZA = b'<meta name="kd-katalog" content="1">'
WSGIApp = Callable[[dict[str, Any], Callable[..., Any]], Iterable[bytes]]


# ------------------------------------------------------------------ yardımcılar


@pytest.fixture
def katalog_uygulamasi(monkeypatch: pytest.MonkeyPatch) -> CatalogApp:
    """Gerçek katalog WSGI'si (`backend/` `sys.path`'e test süresince eklenir)."""
    monkeypatch.syspath_prepend(str(BACKEND_DIR))
    return load_catalog()


@pytest.fixture
def katalog_gunlugu(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Katalog günlükçüsünün iletilerini toplar.

    `caplog` yetmez: `configure_logging` üst günlükçüde `propagate=False` yapar
    ve başka bir test onu çağırdıysa kayıtlar köke ulaşmaz.
    """
    iletiler: list[str] = []

    class _Toplayici(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            iletiler.append(record.getMessage())

    gunlukcu = logging.getLogger("kutuphane_defteri.katalog")
    toplayici = _Toplayici(level=logging.DEBUG)
    onceki_duzey = gunlukcu.level
    gunlukcu.setLevel(logging.INFO)  # setLevel: düzey önbelleği de temizlenir
    gunlukcu.addHandler(toplayici)
    try:
        yield iletiler
    finally:
        gunlukcu.removeHandler(toplayici)
        gunlukcu.setLevel(onceki_duzey)


def _uygulama(yanitlar: dict[str, tuple[str, bytes]], varsayilan: tuple[str, bytes]) -> WSGIApp:
    """Yol → (durum, gövde) eşlemesiyle yanıt veren küçük WSGI uygulaması."""

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        durum, govde = yanitlar.get(environ.get("PATH_INFO", ""), varsayilan)
        start_response(durum, [("Content-Length", str(len(govde)))])
        return [govde]

    return uygulama


def _dinleyici() -> socket.socket:
    """Boş bir porta bağlanmış, dinleyen yardımcı soket (portu dolu göstermek için)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LOOPBACK_HOST, 0))
    sock.listen(1)
    return sock


class _SahteSoket:
    """`socket.socket` yerine geçen kayıt tutucu (ağa dokunmaz)."""

    def __init__(
        self, *, bind_hatasi: OSError | None = None, secenekler: dict[int, int] | None = None
    ) -> None:
        self.bind_hatasi = bind_hatasi
        self.secenekler = secenekler or {}
        self.cagrilar: list[tuple[str, Any]] = []
        self.kapandi = False

    def setsockopt(self, level: int, secenek: int, deger: int) -> None:
        self.cagrilar.append(("setsockopt", (level, secenek, deger)))

    def getsockopt(self, level: int, secenek: int) -> int:
        self.cagrilar.append(("getsockopt", (level, secenek)))
        return self.secenekler.get(secenek, 0)

    def bind(self, adres: tuple[str, int]) -> None:
        self.cagrilar.append(("bind", adres))
        if self.bind_hatasi is not None:
            raise self.bind_hatasi

    def listen(self, kuyruk: int) -> None:
        self.cagrilar.append(("listen", kuyruk))

    def close(self) -> None:
        self.kapandi = True


def _sahte_soket_ac(sahte: _SahteSoket, platform: str) -> socket.socket:
    return open_listen_socket(
        LOOPBACK_HOST, 8765, platform=platform, socket_factory=lambda: cast(socket.socket, sahte)
    )


class _SahteWaitress:
    """waitress sunucusu yerine geçer; `run` kapanana dek bekler."""

    def __init__(self) -> None:
        self.effective_port: int | str = 0
        self.calisti = False
        self.kapandi = False

    def run(self) -> None:
        self.calisti = True

    def close(self) -> None:
        self.kapandi = True


EXCL = int(getattr(socket, "SO_EXCLUSIVEADDRUSE", -5))


# ------------------------------------------------------------------ port ayarı


def test_port_varsayilani_8765() -> None:
    assert DEFAULT_PORT == 8765
    assert resolve_port({}) == 8765
    assert resolve_port({ENV_PORT: ""}) == 8765


@pytest.mark.parametrize(("deger", "beklenen"), [("0", 0), ("9000", 9000), (" 9001 ", 9001)])
def test_port_gelistirme_ortam_degiskeniyle_degisir(deger: str, beklenen: int) -> None:
    assert ENV_PORT == "KD_KATALOG_PORT"
    assert resolve_port({ENV_PORT: deger}) == beklenen


@pytest.mark.parametrize("deger", ["abc", "-1", "70000", "٨٧٦٥", "80.5"])
def test_gecersiz_port_degeri_turkce_hata_verir(deger: str) -> None:
    with pytest.raises(KatalogServerError) as hata:
        resolve_port({ENV_PORT: deger})

    assert "geçersiz" in hata.value.message


# -------------------------------------------------------------- dinleme soketi


def test_windows_dalinda_ozel_kullanim_bind_oncesi_konur() -> None:
    sahte = _SahteSoket()

    _sahte_soket_ac(sahte, "win32")

    assert sahte.cagrilar == [
        ("setsockopt", (socket.SOL_SOCKET, EXCL, 1)),
        ("bind", (LOOPBACK_HOST, 8765)),
        ("listen", katalog_server.LISTEN_BACKLOG),
    ]


def test_windows_ozel_kullanim_sabiti_winsock_degeriyle_ayni() -> None:
    """winsock2.h: `~SO_REUSEADDR` = -5 (Windows'ta `socket` modülü de bunu verir)."""
    assert katalog_server._WINSOCK_EXCLUSIVEADDRUSE == ~4 == -5
    if sys.platform == "win32":
        assert socket.SO_EXCLUSIVEADDRUSE == -5


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_diger_platformlarda_so_reuseaddr_konmaz(platform: str) -> None:
    sahte = _SahteSoket()

    _sahte_soket_ac(sahte, platform)

    assert [ad for ad, _ in sahte.cagrilar] == ["bind", "listen"]  # hiç setsockopt yok


@pytest.mark.skipif(sys.platform == "win32", reason="Windows dalı ayrı sınanır")
def test_gercek_sokette_so_reuseaddr_kapali_kalir() -> None:
    sock = open_listen_socket(LOOPBACK_HOST, 0)
    try:
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0
        assert sock.getsockname()[0] == LOOPBACK_HOST
    finally:
        sock.close()


def test_port_doluysa_ozel_turkce_hata_verir() -> None:
    dolu = _dinleyici()
    port = dolu.getsockname()[1]
    try:
        with pytest.raises(KatalogPortInUseError) as hata:
            open_listen_socket(LOOPBACK_HOST, port)
    finally:
        dolu.close()

    assert hata.value.port == port
    assert f"{port} numaralı port" in hata.value.message
    assert "kullanılıyor" in hata.value.message
    assert "etkilenmez" in hata.value.hint
    # Ölümcül açılış hatası ailesinden DEĞİL: yakalanmazsa bile pencere kapanmamalı.
    assert not isinstance(hata.value, StartupError)


class _WindowsHatasi(OSError):
    """Linux'ta da `winerror` taşıyan OSError (Windows'taki alanı taklit eder)."""

    def __init__(self, winerror: int) -> None:
        super().__init__(None, "winsock hatası")
        self.winerror = winerror


@pytest.mark.parametrize(
    "hata",
    [
        OSError(errno.EADDRINUSE, "Address already in use"),
        _WindowsHatasi(10048),  # WSAEADDRINUSE
        _WindowsHatasi(10013),  # WSAEACCES: başka soket özel tutuyor ya da sistem ayırmış
    ],
)
def test_port_dolu_hata_kodlari_ozel_hataya_cevrilir(hata: OSError) -> None:
    sahte = _SahteSoket(bind_hatasi=hata)

    with pytest.raises(KatalogPortInUseError):
        _sahte_soket_ac(sahte, "win32")

    assert sahte.kapandi


def test_diger_soket_hatasi_genel_katalog_hatasina_cevrilir() -> None:
    sahte = _SahteSoket(bind_hatasi=OSError(errno.EADDRNOTAVAIL, "Cannot assign"))

    with pytest.raises(KatalogServerError) as hata:
        _sahte_soket_ac(sahte, "linux")

    assert not isinstance(hata.value, KatalogPortInUseError)
    assert "soket" in hata.value.message
    assert sahte.kapandi


# ----------------------------------------------------- özel kullanım doğrulaması


def test_ozel_kullanim_dogrulamasi_windows_disinda_sokete_dokunmaz() -> None:
    sahte = _SahteSoket()

    verify_exclusive_bind(cast(socket.socket, sahte), platform="linux")

    assert sahte.cagrilar == []


@pytest.mark.parametrize(
    "secenekler",
    [
        {EXCL: 0, socket.SO_REUSEADDR: 0},  # özel kullanım kalkmış
        {EXCL: 1, socket.SO_REUSEADDR: 1},  # adres paylaşımı açılmış
    ],
)
def test_ozel_kullanim_bozulmussa_katalog_acilmaz(secenekler: dict[int, int]) -> None:
    sahte = _SahteSoket(secenekler=secenekler)

    with pytest.raises(KatalogServerError) as hata:
        verify_exclusive_bind(cast(socket.socket, sahte), platform="win32")

    assert "paylaşılabilir" in hata.value.message


def test_ozel_kullanim_saglamsa_gunluge_kanit_yazilir(katalog_gunlugu: list[str]) -> None:
    sahte = _SahteSoket(secenekler={EXCL: 1, socket.SO_REUSEADDR: 0})

    verify_exclusive_bind(cast(socket.socket, sahte), platform="win32")

    assert any("özel kullanım açık" in ileti for ileti in katalog_gunlugu)
    assert any("adres paylaşımı kapalı" in ileti for ileti in katalog_gunlugu)


@pytest.mark.skipif(sys.platform != "win32", reason="yalnız Windows: SO_EXCLUSIVEADDRUSE")
def test_windows_gercek_waitress_sonrasi_soket_ozel_kalir() -> None:
    """F0 spike'ı: waitress'in `set_reuse_addr` denemesi özel kullanımı bozmamalı."""
    sunucu = KatalogServer(_uygulama({}, ("200 OK", b"")), port=0)
    sunucu.start()
    try:
        sock = sunucu._sock
        assert sock is not None
        assert sock.getsockopt(socket.SOL_SOCKET, EXCL) == 1
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0
        with socket.socket() as korsan:
            korsan.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError):
                korsan.bind((LOOPBACK_HOST, sunucu.port))
    finally:
        sunucu.stop()


# ------------------------------------------------------------ waitress ayarları


def test_waitress_ayarlari_tasarimla_ayni() -> None:
    """§5.2 anlık görüntüsü: değişiklik bilinçli yapılır."""
    assert dict(WAITRESS_SETTINGS) == {
        "threads": 4,
        "connection_limit": 300,
        "channel_timeout": 30,
        "max_request_body_size": 1024,
        "max_request_header_size": 8192,
        "ident": None,
        "expose_tracebacks": False,
        "clear_untrusted_proxy_headers": True,
    }


def test_waitress_ayarlari_kurulu_surumde_tanimli() -> None:
    from waitress.adjustments import Adjustments  # type: ignore[import-untyped]

    bilinen = {ad for ad, _ in Adjustments._params}

    assert set(WAITRESS_SETTINGS) <= bilinen
    assert "sockets" in bilinen


def test_waitress_hazir_soketle_host_ve_port_verilmeden_kurulur() -> None:
    cagri: dict[str, Any] = {}
    sahte = _SahteWaitress()

    def fabrika(app: object, **kwargs: Any) -> _SahteWaitress:
        cagri.update(kwargs)
        return sahte

    sunucu = KatalogServer(_uygulama({}, ("200 OK", b"")), port=0, server_factory=fabrika)
    sunucu.start()
    try:
        assert "host" not in cagri and "port" not in cagri and "listen" not in cagri
        (sock,) = cagri["sockets"]
        assert isinstance(sock, socket.socket)
        assert sock.getsockname() == (LOOPBACK_HOST, sunucu.port)
        for ad, deger in WAITRESS_SETTINGS.items():
            assert cagri[ad] == deger
    finally:
        sunucu.stop()


def test_gercek_waitress_ayarlari_uygular() -> None:
    from waitress.server import create_server  # type: ignore[import-untyped]

    kurulan: list[Any] = []

    def fabrika(app: object, **kwargs: Any) -> Any:
        kurulan.append(create_server(app, **kwargs))
        return kurulan[-1]

    sunucu = KatalogServer(_uygulama({}, ("200 OK", b"")), port=0, server_factory=fabrika)
    sunucu.start()
    try:
        adj = kurulan[0].adj
        assert adj.threads == 4
        assert adj.connection_limit == 300
        assert adj.channel_timeout == 30
        assert adj.max_request_body_size == 1024
        assert adj.max_request_header_size == 8192
        assert adj.ident is None
        assert adj.expose_tracebacks is False
        assert int(kurulan[0].effective_port) == sunucu.port
    finally:
        sunucu.stop()


def test_waitress_sonrasi_ikinci_soket_portu_ele_geciremez() -> None:
    """waitress dinleyen sokete SO_REUSEADDR koysa da portu başkası alamaz."""
    # Windows'ta 127.0.0.1'deki dinleyici varken başka bir soket 0.0.0.0'a aynı
    # portla bağlanabilir (spike 21.09.2026); loopback trafiği yine en belirgin
    # bağa, yani kataloğa gider. Joker adres denemesi bu yüzden yalnız Linux'tadır.
    adresler = [LOOPBACK_HOST] + ([TUM_ARAYUZ] if sys.platform != "win32" else [])
    sunucu = KatalogServer(_uygulama({}, ("200 OK", b"")), port=0)
    sunucu.start()
    try:
        for adres in adresler:
            with socket.socket() as korsan:
                korsan.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                with pytest.raises(OSError):
                    korsan.bind((adres, sunucu.port))
    finally:
        sunucu.stop()


# ------------------------------------------------------------- KatalogServer


@pytest.mark.parametrize("host", [TUM_ARAYUZ, "", "localhost", "192.168.1.10", "::"])
def test_katalog_bu_surumde_yalniz_loopback_adresinde_dinler(host: str) -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        KatalogServer(_uygulama({}, ("200 OK", b"")), host=host)


def test_tum_arayuz_adresi_izinli_adreslerde_degil() -> None:
    assert ALL_INTERFACES_HOST == TUM_ARAYUZ
    assert frozenset({LOOPBACK_HOST}) == ALLOWED_LISTEN_HOSTS


@pytest.mark.parametrize("port", [-1, 65536])
def test_gecersiz_port_reddedilir(port: int) -> None:
    with pytest.raises(ValueError):
        KatalogServer(_uygulama({}, ("200 OK", b"")), port=port)


def test_katalog_kd_katalog_is_parcaciginda_kosar_ve_durdurulur() -> None:
    sahte = _SahteWaitress()
    sunucu = KatalogServer(
        _uygulama({}, ("200 OK", b"")), port=0, server_factory=lambda app, **kw: sahte
    )

    url = sunucu.start()
    sunucu.wait_until_started(timeout=2.0)

    assert sunucu.thread is not None
    assert sunucu.thread.name == THREAD_NAME == "kd-katalog"
    assert sunucu.thread.daemon
    assert url == f"http://127.0.0.1:{sunucu.port}"
    sunucu.thread.join(timeout=2.0)  # sahte `run` hemen döner
    assert sahte.calisti

    sunucu.stop()

    assert sahte.kapandi
    assert sunucu.thread is None
    assert sunucu.port == 0


def test_sunucu_kurulamazsa_soket_kapatilir_ve_turkce_hata() -> None:
    acilan: list[socket.socket] = []

    def acici(host: str, port: int) -> socket.socket:
        acilan.append(open_listen_socket(host, port))
        return acilan[-1]

    def patla(app: object, **kwargs: Any) -> Any:
        raise RuntimeError("kurulamadı")

    sunucu = KatalogServer(
        _uygulama({}, ("200 OK", b"")), port=0, server_factory=patla, socket_opener=acici
    )

    with pytest.raises(KatalogServerError) as hata:
        sunucu.start()

    assert "sunucu kurulamadı" in hata.value.message
    assert acilan[0].fileno() == -1  # soket kapandı, port sızmadı


def test_ozel_kullanim_dogrulanamazsa_sunucu_ve_soket_kapatilir() -> None:
    sahte = _SahteWaitress()
    sahte_soket = _SahteSoket(secenekler={EXCL: 0})
    sunucu = KatalogServer(
        _uygulama({}, ("200 OK", b"")),
        port=0,
        server_factory=lambda app, **kw: sahte,
        socket_opener=lambda h, p: cast(socket.socket, sahte_soket),
        platform="win32",
    )

    with pytest.raises(KatalogServerError):
        sunucu.start()

    assert sahte.kapandi and sahte_soket.kapandi
    assert sunucu.thread is None


def test_iki_kez_baslatma_reddedilir() -> None:
    sunucu = KatalogServer(
        _uygulama({}, ("200 OK", b"")), port=0, server_factory=lambda app, **kw: _SahteWaitress()
    )
    sunucu.start()
    try:
        with pytest.raises(RuntimeError):
            sunucu.start()
    finally:
        sunucu.stop()


def test_gercek_katalog_uctan_uca(katalog_uygulamasi: CatalogApp) -> None:
    """Gerçek waitress + gerçek katalog WSGI: imza, başlıklar, yöntem ve gövde sınırı."""
    sunucu = KatalogServer(katalog_uygulamasi.application, port=0)
    sunucu.start()
    try:
        sunucu.wait_until_started()
        self_test(sunucu.host, sunucu.port, signature=katalog_uygulamasi.signature)

        with urllib.request.urlopen(sunucu.base_url + "/", timeout=5) as yanit:  # noqa: S310
            govde = yanit.read()
            assert yanit.status == 200
            assert IMZA in govde
            assert "default-src 'none'" in yanit.headers["Content-Security-Policy"]
            assert yanit.headers["Server"] is None  # ident=None: sürüm sızdırılmaz
            assert yanit.headers["Set-Cookie"] is None

        istek = urllib.request.Request(  # noqa: S310
            sunucu.base_url + "/", data=b"x", method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as hata:
            urllib.request.urlopen(istek, timeout=5)  # noqa: S310
        assert hata.value.code == 405

        # 1 KB'ı aşan gövde uygulamaya ulaşmadan waitress'te reddedilir. Gövde
        # gönderilmez: yalnız başlık yeter, okunmamış veri RST'ye yol açmasın.
        baglanti = http.client.HTTPConnection(sunucu.host, sunucu.port, timeout=5)
        try:
            baglanti.putrequest("GET", "/")
            baglanti.putheader("Content-Length", "2048")
            baglanti.endheaders()
            assert baglanti.getresponse().status == 413
        finally:
            baglanti.close()
        port = sunucu.port
    finally:
        sunucu.stop()

    with pytest.raises(OSError):  # dinleyici kapandı
        socket.create_connection((LOOPBACK_HOST, port), timeout=1.0).close()


# ----------------------------------------------------------------- öz sınama


def _calisan(uygulama: WSGIApp) -> KatalogServer:
    sunucu = KatalogServer(uygulama, port=0)
    sunucu.start()
    sunucu.wait_until_started()
    return sunucu


def test_oz_sinama_imzasiz_ana_sayfayi_reddeder() -> None:
    sunucu = _calisan(_uygulama({"/": ("200 OK", b"<html>baska</html>")}, ("404 Not Found", IMZA)))
    try:
        with pytest.raises(KatalogSelfTestError) as hata:
            self_test(sunucu.host, sunucu.port, signature=IMZA, timeout=5.0)
    finally:
        sunucu.stop()

    assert "ana sayfa" in hata.value.message


def test_oz_sinama_yonetim_yolu_yanit_verirse_reddeder() -> None:
    """Portta her yola 200 dönen bir uygulama (ör. SPA catch-all) varsa katalog kapanır."""
    sunucu = _calisan(_uygulama({}, ("200 OK", IMZA)))
    try:
        with pytest.raises(KatalogSelfTestError) as hata:
            self_test(sunucu.host, sunucu.port, signature=IMZA, timeout=5.0)
    finally:
        sunucu.stop()

    assert "yönetim yolu" in hata.value.message


def test_oz_sinama_404u_katalogdan_baska_uygulama_verirse_reddeder() -> None:
    sunucu = _calisan(_uygulama({"/": ("200 OK", IMZA)}, ("404 Not Found", b"Not Found")))
    try:
        with pytest.raises(KatalogSelfTestError):
            self_test(sunucu.host, sunucu.port, signature=IMZA, timeout=5.0)
    finally:
        sunucu.stop()


def test_oz_sinama_yonetim_saglik_yolunu_yoklar() -> None:
    gorulen: list[str] = []

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        gorulen.append(environ["PATH_INFO"])
        durum = "200 OK" if environ["PATH_INFO"] == "/" else "404 Not Found"
        start_response(durum, [("Content-Length", str(len(IMZA)))])
        return [IMZA]

    sunucu = _calisan(uygulama)
    try:
        self_test(sunucu.host, sunucu.port, signature=IMZA, timeout=5.0)
    finally:
        sunucu.stop()

    assert gorulen == ["/", HEALTH_PATH]


def test_oz_sinama_tek_baglanti_kullanir_ve_kapatir() -> None:
    """İki istek aynı bağlantıdan gider; bağlantıyı istemci kapatır (TIME_WAIT bizde kalır)."""
    uzak_portlar: list[str] = []

    def uygulama(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        uzak_portlar.append(environ["REMOTE_PORT"])
        durum = "200 OK" if environ["PATH_INFO"] == "/" else "404 Not Found"
        start_response(durum, [("Content-Length", str(len(IMZA)))])
        return [IMZA]

    sunucu = _calisan(uygulama)
    try:
        self_test(sunucu.host, sunucu.port, signature=IMZA, timeout=5.0)
    finally:
        sunucu.stop()

    assert len(uzak_portlar) == 2
    assert len(set(uzak_portlar)) == 1


def test_oz_sinama_ulasilamayan_portta_turkce_hata() -> None:
    kapali = find_free_port()

    with pytest.raises(KatalogSelfTestError) as hata:
        self_test(LOOPBACK_HOST, kapali, signature=IMZA, timeout=1.0)

    assert "bağlantısı kurulamadı" in hata.value.message


# ------------------------------------------------------------- start_catalog


def test_start_catalog_gercek_katalogu_kaldirir(
    katalog_uygulamasi: CatalogApp, katalog_gunlugu: list[str]
) -> None:
    sunucu = start_catalog(environ={ENV_PORT: "0"})
    try:
        assert sunucu is not None
        assert sunucu.host == LOOPBACK_HOST
        with urllib.request.urlopen(sunucu.base_url + "/", timeout=5) as yanit:  # noqa: S310
            assert IMZA in yanit.read()
    finally:
        stop_catalog(sunucu)

    assert any("Ağ Kataloğu hazır" in ileti for ileti in katalog_gunlugu)
    assert any("kapatıldı" in ileti for ileti in katalog_gunlugu)
    # Erişim günlüğü yok: istek yolu ve sorgu işareti günlüğe düşmez (§5.5).
    assert not any("setup/status" in ileti or "?" in ileti for ileti in katalog_gunlugu)


def test_start_catalog_port_doluysa_none_doner_ve_gunluge_yazar(
    katalog_uygulamasi: CatalogApp, katalog_gunlugu: list[str]
) -> None:
    dolu = _dinleyici()
    try:
        sunucu = start_catalog(environ={ENV_PORT: str(dolu.getsockname()[1])})
    finally:
        dolu.close()

    assert sunucu is None
    assert any("kullanılıyor" in ileti and "etkilenmez" in ileti for ileti in katalog_gunlugu)


def test_start_catalog_oz_sinama_gecmezse_dinleyiciyi_kapatir(
    katalog_gunlugu: list[str],
) -> None:
    port = find_free_port()
    spa_gibi = CatalogApp(application=_uygulama({}, ("200 OK", b"<div id=root>")), signature=IMZA)

    sunucu = start_catalog(environ={ENV_PORT: str(port)}, loader=lambda: spa_gibi)

    assert sunucu is None
    assert any("öz sınamada" in ileti for ileti in katalog_gunlugu)
    with pytest.raises(OSError):  # dinleyici kapatıldı
        socket.create_connection((LOOPBACK_HOST, port), timeout=1.0).close()


@pytest.mark.parametrize(
    "hata", [KatalogServerError("Ağ Kataloğu açılamadı: deneme."), RuntimeError("beklenmedik")]
)
def test_start_catalog_hic_hata_sizdirmaz(hata: Exception, katalog_gunlugu: list[str]) -> None:
    def yukleyici() -> CatalogApp:
        raise hata

    assert start_catalog(environ={ENV_PORT: "0"}, loader=yukleyici) is None
    assert katalog_gunlugu


def test_katalog_paketi_yoksa_turkce_hata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "katalog.app", None)  # içe aktarma ImportError verir

    with pytest.raises(KatalogServerError) as hata:
        load_catalog()

    assert "katalog dosyaları bulunamadı" in hata.value.message


def test_stop_catalog_bos_ve_hatali_durumda_sessiz_kalir(katalog_gunlugu: list[str]) -> None:
    stop_catalog(None)

    class _Patlayan:
        def stop(self) -> None:
            raise RuntimeError("kapanmadı")

    stop_catalog(cast(KatalogServer, _Patlayan()))  # çıkış durmaz

    assert any("yok sayıldı" in ileti for ileti in katalog_gunlugu)


# ---------------------------------------------------------- main.py bağlaması


class _SahteYonetim:
    """Yönetim `BackgroundServer`'ının yerine geçer; sırayı kaydeder."""

    sira: list[str] = []

    def __init__(self, application: object) -> None:
        self.base_url = "http://127.0.0.1:54321"

    def start(self) -> str:
        self.sira.append("yonetim-basla")
        return self.base_url

    def wait_until_ready(self) -> None:
        pass

    def stop(self) -> None:
        self.sira.append("yonetim-dur")


class _SahteTepsi:
    available = False

    def stop(self) -> None:
        pass


@pytest.fixture
def sahte_servis(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """`serve()` çevresini izole eder: Django ve pencere sahte, sıra kayıtlı."""
    sira: list[str] = []
    monkeypatch.setattr(_SahteYonetim, "sira", sira)
    kayit: dict[str, Any] = {
        "sira": sira,
        "paths": resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)}),
    }
    monkeypatch.setattr(main_mod, "build_wsgi_application", lambda: object())
    monkeypatch.setattr(main_mod, "assert_session_guard_installed", lambda: None)
    monkeypatch.setattr(main_mod, "BackgroundServer", _SahteYonetim)
    monkeypatch.setattr(main_mod, "check_health", lambda url, token: sira.append("saglik"))
    monkeypatch.setattr(main_mod, "require_window_runtime", lambda: None)
    monkeypatch.setattr(
        main_mod, "open_window", lambda url, storage_path, **_: sira.append("pencere")
    )
    # Tepsi sahte: katalog bağlaması testleri gerçek Qt/pystray aramasın.
    monkeypatch.setattr(main_mod, "start_tray", lambda actions, **_: _SahteTepsi())
    return kayit


class _SahteKatalog:
    def __init__(self, sira: list[str]) -> None:
        self.sira = sira

    def stop(self) -> None:
        self.sira.append("katalog-dur")


def _sahte_katalog_baslat(
    monkeypatch: pytest.MonkeyPatch, sira: list[str]
) -> Callable[[], _SahteKatalog]:
    def baslat() -> _SahteKatalog:
        sira.append("katalog-basla")
        return _SahteKatalog(sira)

    monkeypatch.setattr(main_mod, "start_catalog", baslat)
    return baslat


def test_katalog_yonetim_saglik_denetiminden_sonra_kalkar_ve_once_kapanir(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _sahte_katalog_baslat(monkeypatch, sahte_servis["sira"])

    kod = main_mod.serve(sahte_servis["paths"], "belirtec", False)

    assert kod == EXIT_OK
    assert sahte_servis["sira"] == [
        "yonetim-basla",
        "saglik",
        "katalog-basla",  # yönetim ayakta ve korumalı olduktan SONRA
        "pencere",
        "katalog-dur",  # çıkışta yönetimden ÖNCE
        "yonetim-dur",
    ]


def test_autotest_kipinde_de_katalog_kalkar_ve_kapanir(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _sahte_katalog_baslat(monkeypatch, sahte_servis["sira"])

    kod = main_mod.serve(sahte_servis["paths"], "belirtec", True)

    assert kod == EXIT_OK
    assert "pencere" not in sahte_servis["sira"]
    assert sahte_servis["sira"][-2:] == ["katalog-dur", "yonetim-dur"]
    assert "katalog-basla" in sahte_servis["sira"]


def test_katalog_baslatma_hatasi_acilisi_durdurmaz(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gerçek `start_catalog`; katalog yüklenemez → pencere yine açılır."""

    def patla() -> CatalogApp:
        raise RuntimeError("katalog yüklenemedi")

    monkeypatch.setattr(katalog_server, "load_catalog", patla)

    kod = main_mod.serve(sahte_servis["paths"], "belirtec", False)

    assert kod == EXIT_OK
    assert "pencere" in sahte_servis["sira"]


def test_katalog_portu_doluyken_program_acilir(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch, katalog_uygulamasi: CatalogApp
) -> None:
    dolu = _dinleyici()
    monkeypatch.setenv(ENV_PORT, str(dolu.getsockname()[1]))
    try:
        kod = main_mod.serve(sahte_servis["paths"], "belirtec", False)
    finally:
        dolu.close()

    assert kod == EXIT_OK
    assert "pencere" in sahte_servis["sira"]


def test_pencere_hatasinda_da_katalog_durdurulur(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _sahte_katalog_baslat(monkeypatch, sahte_servis["sira"])

    def pencere_yok() -> None:
        raise WebViewUnavailableError("WebView2 yok.")

    monkeypatch.setattr(main_mod, "require_window_runtime", pencere_yok)

    with pytest.raises(WebViewUnavailableError):
        main_mod.serve(sahte_servis["paths"], "belirtec", False)

    assert sahte_servis["sira"][-2:] == ["katalog-dur", "yonetim-dur"]


@pytest.mark.slow
def test_autotest_gercek_acilista_katalogu_kaldirir(tmp_path: Path) -> None:
    """Uçtan uca: `--autotest` gerçek katalog soketini açar, öz sınar, kapatır."""
    sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
        [sys.executable, "-m", "desktop.main", "--autotest", "--data-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, ENV_PORT: "0"},
    )

    assert sonuc.returncode == EXIT_OK, sonuc.stderr
    gunluk = (tmp_path / "logs" / "uygulama.log").read_text(encoding="utf-8")
    assert "Ağ Kataloğu hazır" in gunluk
    assert "öz sınama geçti" in gunluk
    assert "Ağ Kataloğu kapatıldı" in gunluk


# ------------------------------------------------------ koruma testleri §5.10-1


@pytest.mark.parametrize("host", [TUM_ARAYUZ, "", "localhost", "192.168.1.5", "::"])
def test_yonetim_sunucusu_yalniz_varsayilan_hostu_kabul_eder(host: str) -> None:
    assert DEFAULT_HOST == "127.0.0.1"

    with pytest.raises(ValueError, match="127.0.0.1"):
        BackgroundServer(_uygulama({}, ("200 OK", b"")), host=host)


def test_yonetim_sunucusu_varsayilan_hostla_kurulur() -> None:
    sunucu = BackgroundServer(_uygulama({}, ("200 OK", b"")), host=DEFAULT_HOST)

    assert sunucu.base_url.startswith("http://127.0.0.1:")


def test_main_yonetim_sunucusunu_host_vermeden_kurar() -> None:
    agac = ast.parse((DESKTOP_DIR / "main.py").read_text(encoding="utf-8"))
    cagrilar = [
        dugum
        for dugum in ast.walk(agac)
        if isinstance(dugum, ast.Call)
        and isinstance(dugum.func, ast.Name)
        and dugum.func.id == "BackgroundServer"
    ]

    assert cagrilar, "main.py yönetim sunucusunu kurmuyor (desen değişti mi)"
    for cagri in cagrilar:
        assert not any(k.arg == "host" for k in cagri.keywords)
        assert len(cagri.args) == 1  # yalnız uygulama; host konumsal da verilmez


# Taranan üretim kaynakları: masaüstü kabuğu, paket giriş noktası, backend ayarları
# ve katalog paketi. Testler kapsam dışıdır (bu dosya adresi bilerek yazar).
_TARANAN_KOKLER = (
    DESKTOP_DIR,
    REPO_ROOT / "packaging" / "pyinstaller",
    BACKEND_DIR / "config",
    BACKEND_DIR / "katalog",
)
# Bilinçli istisna: `window.py`'deki "0.0.0.0" bir IP değil, kaldırılmış WebView2
# çalışma zamanının bıraktığı sürüm damgasıdır. Muafiyet ATAMA adıyla verilir;
# aynı dosyaya eklenecek başka bir kullanım yine yakalanır.
_MUAF_ATAMALAR = {("desktop/window.py", "_EMPTY_VERSIONS")}


def _uretim_kaynaklari() -> Iterator[Path]:
    for kok in _TARANAN_KOKLER:
        for dosya in sorted(kok.rglob("*.py")):
            if "tests" in dosya.relative_to(REPO_ROOT).parts:
                continue
            yield dosya


def _tum_arayuz_metinleri(goreli: str, kaynak: str) -> list[int]:
    """Kaynakta "0.0.0.0" içeren metin sabitlerinin (belge dizeleri dahil) satırları."""
    agac = ast.parse(kaynak)
    muaf: set[int] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Assign | ast.AnnAssign) and dugum.value is not None:
            hedefler = dugum.targets if isinstance(dugum, ast.Assign) else [dugum.target]
            if any(isinstance(h, ast.Name) and (goreli, h.id) in _MUAF_ATAMALAR for h in hedefler):
                muaf.update(id(alt) for alt in ast.walk(dugum.value))
    return sorted(
        dugum.lineno
        for dugum in ast.walk(agac)
        if isinstance(dugum, ast.Constant)
        and isinstance(dugum.value, str)
        and TUM_ARAYUZ in dugum.value
        and id(dugum) not in muaf
    )


def test_tum_arayuz_adresi_yalniz_katalog_sunucusunda_gecer() -> None:
    bulunan: list[str] = []
    for dosya in _uretim_kaynaklari():
        goreli = dosya.relative_to(REPO_ROOT).as_posix()
        if goreli == "desktop/katalog_server.py":
            continue
        kaynak = dosya.read_text(encoding="utf-8")
        bulunan.extend(f"{goreli}:{no}" for no in _tum_arayuz_metinleri(goreli, kaynak))

    assert bulunan == []


def test_yonetim_sunucusu_kaynaginda_tum_arayuz_adresi_hic_gecmez() -> None:
    """`server.py`'de yorum dahil hiçbir yerde geçmez (ham metin taraması)."""
    assert TUM_ARAYUZ not in (DESKTOP_DIR / "server.py").read_text(encoding="utf-8")


def test_tum_arayuz_taramasi_muafiyet_disini_yakalar() -> None:
    """Tarayıcının kendisi: muaf atama geçer; başka ad, dosya ya da belge dizesi yakalanır."""
    kaynak = '"""0.0.0.0 belgede"""\nX = "0.0.0.0"\n_EMPTY_VERSIONS = {"", "0.0.0.0"}\n'

    assert _tum_arayuz_metinleri("desktop/window.py", kaynak) == [1, 2]
    assert _tum_arayuz_metinleri("desktop/main.py", kaynak) == [1, 2, 3]


def test_katalog_sunucusunda_tum_arayuz_adresi_yalniz_sabit_olarak_gecer() -> None:
    """`0.0.0.0` bu sürümde yalnız ileride kullanılacak bir sabittir (F5'te bağlanır)."""
    kaynak = (DESKTOP_DIR / "katalog_server.py").read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    sabitler = [
        dugum
        for dugum in ast.walk(agac)
        if isinstance(dugum, ast.Constant) and dugum.value == TUM_ARAYUZ
    ]
    atama = [
        dugum
        for dugum in ast.walk(agac)
        if isinstance(dugum, ast.AnnAssign)
        and isinstance(dugum.target, ast.Name)
        and dugum.target.id == "ALL_INTERFACES_HOST"
    ]

    assert len(sabitler) == 1
    assert len(atama) == 1 and atama[0].value is sabitler[0]


def test_tum_arayuz_sabiti_hicbir_yerde_kullanilmaz() -> None:
    kullanim: list[str] = []
    for dosya in _uretim_kaynaklari():
        for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
            if isinstance(dugum, ast.Name) and isinstance(dugum.ctx, ast.Load):
                ad = dugum.id
            elif isinstance(dugum, ast.Attribute):
                ad = dugum.attr
            else:
                continue
            if ad == "ALL_INTERFACES_HOST":
                kullanim.append(f"{dosya.relative_to(REPO_ROOT).as_posix()}:{dugum.lineno}")

    assert kullanim == []


def test_diger_tum_arayuz_bicimleri_uretim_kaynaginda_yok() -> None:
    """IPv6 `::`, boş host ve `INADDR_ANY` de tüm arayüzlere bağlanır."""
    bulunan: list[str] = []
    for dosya in _uretim_kaynaklari():
        for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
            if isinstance(dugum, ast.Constant) and dugum.value in {"::", "::0"}:
                bulunan.append(f"{dosya.name}:{dugum.lineno}")
            if isinstance(dugum, ast.Attribute) and dugum.attr in {"INADDR_ANY", "IN6ADDR_ANY"}:
                bulunan.append(f"{dosya.name}:{dugum.lineno}")
            if isinstance(dugum, ast.keyword) and dugum.arg == "host":
                if isinstance(dugum.value, ast.Constant) and dugum.value.value == "":
                    bulunan.append(f"{dosya.name}:{dugum.value.lineno}")

    assert bulunan == []


def test_autotest_kipinde_katalog_kalkmazsa_6_doner(
    sahte_servis: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duman testi (paket koşusu) katalog soket yolunu çıkış koduyla kanıtlar."""
    monkeypatch.setattr(main_mod, "start_catalog", lambda: None)

    kod = main_mod.serve(sahte_servis["paths"], "belirtec", True)

    assert kod == EXIT_SERVER_FAILED
    assert sahte_servis["sira"][-1] == "yonetim-dur"  # yönetim yine düzenli kapanır
