"""50 istemcili yük provası (tasarım §14.1 F5 kod kapısı; §4.3 GA-12, T3).

Ölçülen iki şey:

1. **Katalog cevap verir:** 50 istemci aynı anda katalog portuna istek atar;
   hepsi 200 alır. İstemciler FARKLI kaynak adreslerinden gelir (127.0.0.2 …
   127.0.0.51; Linux'ta 127/8'in tamamı yereldir): okul ağında her tahta ayrı
   bir IP'dir ve IP başına bağlantı sınırı (TB2) gerçek dağılımla sınanır.
2. **Yönetim API'si akıcı kalır:** katalog yük altındayken ayrı dinleyicideki
   yönetim sunucusuna (T3: ayrı waitress, ayrı iş parçacığı havuzu) düzenli
   istek atılır; gecikmesi ölçülür ve üst sınırla karşılaştırılır.

Katalog uygulaması her istekte bir veritabanı sorgusunu taklit eden kısa bir
bekleme yapar (katalog iş parçacığı havuzu 4'tür; 50 istek kuyrukta bekler).
Ölçümler test çıktısına yazılır (`-s` ile görünür) ve rapora girer.
"""

from __future__ import annotations

import http.client
import statistics
import sys
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from desktop.katalog_server import KatalogServer
from desktop.server import BackgroundServer

TUM_ARAYUZ = "0.0.0.0"  # noqa: S104 — yük provası tüm arayüz dinleyicisini sınar
ISTEMCI = 50
SORGU_SN = 0.02
YONETIM_P95_TAVANI_SN = 0.5

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="127/8 kaynak adresleri Linux'a özgü"
)


class _Izin:
    dinlemeye_izin = True


def _katalog_uygulamasi(
    environ: dict[str, Any], start_response: Callable[..., Any]
) -> Iterable[bytes]:
    time.sleep(SORGU_SN)  # veritabanı sorgusu taklidi
    govde = b'<meta name="kd-katalog" content="1">sonuc'
    start_response("200 OK", [("Content-Length", str(len(govde)))])
    return [govde]


def _yonetim_uygulamasi(
    environ: dict[str, Any], start_response: Callable[..., Any]
) -> Iterable[bytes]:
    start_response("200 OK", [("Content-Length", "5")])
    return [b"tamam"]


def _getir(port: int, kaynak: str | None = None, yol: str = "/ara?q=siir") -> tuple[int, float]:
    baslangic = time.perf_counter()
    baglanti = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=30, source_address=(kaynak, 0) if kaynak else None
    )
    try:
        baglanti.request("GET", yol)
        yanit = baglanti.getresponse()
        yanit.read()
        return yanit.status, time.perf_counter() - baslangic
    finally:
        baglanti.close()


def test_elli_istemcili_yukte_katalog_cevap_verir_yonetim_akici_kalir() -> None:
    katalog = KatalogServer(_katalog_uygulamasi, host=TUM_ARAYUZ, port=0, ag_izni=_Izin())
    yonetim = BackgroundServer(_yonetim_uygulamasi)
    katalog.start()
    yonetim.start()
    try:
        katalog.wait_until_started()
        yonetim.wait_until_ready()

        yonetim_gecikmeleri: list[float] = []
        dur = threading.Event()

        def yonetimi_yokla() -> None:
            while not dur.is_set():
                durum, sure = _getir(yonetim.port, yol="/api/v1/setup/status/")
                assert durum == 200
                yonetim_gecikmeleri.append(sure)
                time.sleep(0.01)

        yoklayici = threading.Thread(target=yonetimi_yokla)
        yoklayici.start()
        baslangic = time.perf_counter()
        with ThreadPoolExecutor(max_workers=ISTEMCI) as havuz:
            sonuclar = list(
                havuz.map(lambda i: _getir(katalog.port, kaynak=f"127.0.0.{i + 2}"), range(ISTEMCI))
            )
        toplam = time.perf_counter() - baslangic
        dur.set()
        yoklayici.join(timeout=10)
    finally:
        katalog.stop()
        yonetim.stop()

    durumlar = [durum for durum, _ in sonuclar]
    katalog_sureleri = sorted(sure for _, sure in sonuclar)
    yonetim_sureleri = sorted(yonetim_gecikmeleri)
    p95 = yonetim_sureleri[int(len(yonetim_sureleri) * 0.95) - 1]
    print(  # noqa: T201 — ölçüm rapora girer (pytest -s)
        f"\nYÜK PROVASI: {ISTEMCI} istemci, toplam {toplam:.2f} sn; katalog yanıtı "
        f"medyan {statistics.median(katalog_sureleri):.3f} sn, en uzun "
        f"{katalog_sureleri[-1]:.3f} sn; yönetim {len(yonetim_sureleri)} istek, "
        f"medyan {statistics.median(yonetim_sureleri) * 1000:.1f} ms, p95 {p95 * 1000:.1f} ms"
    )
    assert durumlar == [200] * ISTEMCI
    assert katalog.reddedilen_baglanti == 0  # farklı IP'ler sınıra takılmaz
    assert len(yonetim_sureleri) >= 5
    assert p95 < YONETIM_P95_TAVANI_SN


def test_tek_ipden_gelen_sel_digerlerini_ve_yonetimi_bogmaz() -> None:
    """GA-12: tek adresten açılan 60 boşta bağlantı sınırda kesilir; başka IP hizmet alır."""
    import socket

    katalog = KatalogServer(_katalog_uygulamasi, host=TUM_ARAYUZ, port=0, ag_izni=_Izin())
    katalog.start()
    sel: list[socket.socket] = []
    try:
        katalog.wait_until_started()
        for _ in range(60):
            try:
                sel.append(
                    socket.create_connection(
                        ("127.0.0.1", katalog.port), timeout=2, source_address=("127.0.0.9", 0)
                    )
                )
            except OSError:
                continue  # sınırda kesilen bağlantı bağlanırken RST alabilir
        son = time.monotonic() + 5
        while katalog.reddedilen_baglanti < 40 and time.monotonic() < son:
            time.sleep(0.02)

        durum, _ = _getir(katalog.port, kaynak="127.0.0.10")

        assert durum == 200
        assert katalog.reddedilen_baglanti >= 40  # 60 - 20
        assert len(getattr(katalog._server, "active_channels", {})) <= 21
    finally:
        for baglanti in sel:
            baglanti.close()
        katalog.stop()
