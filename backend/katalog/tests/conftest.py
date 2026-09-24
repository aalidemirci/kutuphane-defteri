"""Ağ Kataloğu testlerinin ortak kurgusu (tasarım §5.3 "Test ortamı").

Veriye ulaşan katalog testleri **dosya tabanlı test veritabanı** ve
`django_db(transaction=True)` ile koşar: katalog veritabanını ayrı bir `mode=ro`
bağlantısıyla açar; bellek içi test veritabanını ve kapanmamış (geri
sarılacak) bir işlemin yazdıklarını göremezdi. Dosya yolu
`config/settings.py` `DATABASES["default"]["TEST"]["NAME"]`dedir.

`katalog` fikstürü AYRI bir uygulama örneği kurar: kendi bakım kapısı ve
testleri boğmayacak genişlikte bir hız sınırı. Hız sınırının kendisi
`test_sinirlar.py`'de sınanır.

İstek, waitress'in WSGI ortamını kurduğu gibi kurulur: yolun yüzde kodlaması
çözülür ve baytlar latin-1 dizesi olarak `PATH_INFO`'ya konur; sorgu dizesi
ham (kodlu) kalır.
"""

from __future__ import annotations

import html
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from katalog.app import KatalogUygulamasi
from katalog.bakim import BakimKapisi
from katalog.sayac import GunlukSayaclar
from katalog.sinir import HizSiniri

_HREF = re.compile(r'href="([^"]*)"')


def _yuzde_coz_bayt(metin: str) -> bytes:
    """Tarayıcının gönderdiği yolun sunucudaki çözümü (yüzde → bayt)."""
    cikti = bytearray()
    i = 0
    ham = metin.encode("utf-8")
    while i < len(ham):
        if ham[i] == 0x25:  # '%'
            cikti.append(int(ham[i + 1 : i + 3], 16))
            i += 3
            continue
        cikti.append(ham[i])
        i += 1
    return bytes(cikti)


def ortam_kur(
    adres: str = "/",
    *,
    yontem: str = "GET",
    istemci: str = "10.20.30.40",
    **ek: Any,
) -> dict[str, Any]:
    yol, _, sorgu = adres.partition("?")
    ortam: dict[str, Any] = {
        "REQUEST_METHOD": yontem,
        "PATH_INFO": _yuzde_coz_bayt(yol).decode("latin-1"),
        "QUERY_STRING": sorgu,
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8765",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": istemci,
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    ortam.update(ek)
    return ortam


@dataclass
class Yanit:
    status: str
    headers: list[tuple[str, str]]
    body: bytes
    code: int = field(init=False)

    def __post_init__(self) -> None:
        self.code = int(self.status.split(" ", 1)[0])

    def header(self, ad: str) -> str | None:
        degerler = [v for k, v in self.headers if k.lower() == ad.lower()]
        assert len(degerler) <= 1, f"{ad} başlığı birden çok kez gönderildi"
        return degerler[0] if degerler else None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def baglantilar(self) -> list[str]:
        """Sayfadaki bütün `href` değerleri (HTML kaçırması çözülmüş)."""
        return [html.unescape(h) for h in _HREF.findall(self.text)]


def cagir(uygulama: Any, ortam: dict[str, Any]) -> Yanit:
    yakalanan: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> Any:
        yakalanan["status"] = status
        yakalanan["headers"] = headers
        return lambda veri: None

    govde = b"".join(uygulama(ortam, start_response))
    return Yanit(yakalanan["status"], yakalanan["headers"], govde)


class KatalogIstemcisi:
    """Katalog uygulamasına tarayıcı gibi istek atan küçük yardımcı."""

    def __init__(self, uygulama: KatalogUygulamasi) -> None:
        self.uygulama = uygulama

    def get(self, adres: str = "/", **ek: Any) -> Yanit:
        return cagir(self.uygulama, ortam_kur(adres, **ek))

    def istek(self, adres: str = "/", *, yontem: str, **ek: Any) -> Yanit:
        return cagir(self.uygulama, ortam_kur(adres, yontem=yontem, **ek))


def genis_hiz_siniri() -> HizSiniri:
    return HizSiniri(kapasite=1_000_000, dolum_hizi=1_000_000)


@pytest.fixture
def bakim_kapisi() -> BakimKapisi:
    return BakimKapisi()


@pytest.fixture
def katalog(bakim_kapisi: BakimKapisi) -> Iterator[KatalogIstemcisi]:
    """Veriye bağlı, kendi bakım kapısı ve geniş hız sınırı olan katalog örneği."""
    from apps.kutuphane.ag_katalogu import katalog_uygulamasi

    uygulama = katalog_uygulamasi(
        bakim_kapisi=bakim_kapisi,
        hiz_siniri=genis_hiz_siniri(),
        sayaclar=GunlukSayaclar(),
    )
    yield KatalogIstemcisi(uygulama)
