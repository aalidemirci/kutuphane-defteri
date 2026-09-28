"""Ağ tuzağı: `desktop.main`'i dışarı giden her bağlantı KAYDEDİLİP reddedilerek koşar.

`python -m desktop.tests.ag_tuzagi <desktop.main argümanları>` — program HİÇBİR modülü
import etmeden önce soket katmanı değiştirilir (`--betik <komut> …` ile aynı tuzak
altında prova betiği koşar; ör. gün değişimi kapısının işleri):

* `socket.socket.connect` / `connect_ex`: yerel olmayan (loopback dışı) IPv4/IPv6
  hedefe bağlantı kaydedilir ve `OSError` ile reddedilir;
* `socket.getaddrinfo`: yerel olmayan bir ADIN çözülmesi (DNS) kaydedilir ve reddedilir;
* `urllib.request.urlopen`: yerel olmayan her adres kaydedilir ve reddedilir
  (yönetim sunucusunun 127.0.0.1 sağlık denetimi geçer).

İstisna: `192.0.2.0/24` (TEST-NET-1). `desktop/ag.py` IP adaylarını o bloğa UDP
`connect` ile bulur — UDP'de `connect` paket göndermez, yalnız rota tablosuna bakar.

Kayıt `KD_AG_TUZAGI_KAYIT` ortam değişkenindeki dosyaya satır satır JSON olarak
yazılır. `--kendini-sina` bayrağıyla tuzak kendini sınar (dış bağlantı dener, kaydın
düştüğünü gösterir) ve 0 ile çıkar — testin yanlış yeşil vermediğinin kanıtı.
Toplanmaz (`test_` ile başlamaz).
"""

from __future__ import annotations

import ipaddress
import json
import os
import runpy
import socket
import sys
import urllib.request
from typing import Any
from urllib.parse import urlsplit

_KAYIT = os.environ.get("KD_AG_TUZAGI_KAYIT", "")
_YEREL_ADLAR = frozenset({"", "localhost"})
#: TEST-NET-1 (RFC 5737): `desktop/ag.py`'nin UDP rota sorgusu hedefi — paket gitmez.
_TEST_NET_1 = ipaddress.ip_network("192.0.2.0/24")


def _kaydet(tur: str, hedef: Any) -> None:
    if not _KAYIT:
        return
    with open(_KAYIT, "a", encoding="utf-8") as dosya:
        dosya.write(json.dumps([tur, str(hedef)], ensure_ascii=False) + "\n")


def _yerel_mi(host: Any) -> bool:
    """Loopback, "belirtilmemiş" (dinleme joker adresi — waitress bunu çözer) ya da TEST-NET-1."""
    if host is None:
        return True
    ad = host.decode() if isinstance(host, bytes) else str(host)
    if ad in _YEREL_ADLAR:
        return True
    try:
        ip = ipaddress.ip_address(ad.split("%", 1)[0])
    except ValueError:
        return False  # çözülmesi gereken bir ad: dışarı giden DNS sorgusu
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_unspecified or ip in _TEST_NET_1


_ozgun_connect = socket.socket.connect
_ozgun_connect_ex = socket.socket.connect_ex
_ozgun_getaddrinfo = socket.getaddrinfo


def _dis_mi(sock: socket.socket, adres: Any) -> bool:
    return (
        sock.family in (socket.AF_INET, socket.AF_INET6)
        and isinstance(adres, tuple)
        and not _yerel_mi(adres[0])
    )


def _connect(self: socket.socket, adres: Any) -> None:
    if _dis_mi(self, adres):
        _kaydet("connect", adres)
        raise OSError("Dış bağlantı engellendi (ağ tuzağı).")
    _ozgun_connect(self, adres)


def _connect_ex(self: socket.socket, adres: Any) -> int:
    if _dis_mi(self, adres):
        _kaydet("connect_ex", adres)
        return 111  # ECONNREFUSED
    return _ozgun_connect_ex(self, adres)


def _getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if not _yerel_mi(host):
        _kaydet("dns", host)
        raise socket.gaierror("Ad çözümü engellendi (ağ tuzağı).")
    return _ozgun_getaddrinfo(host, *args, **kwargs)


_ozgun_urlopen = urllib.request.urlopen


def _urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
    adres = str(getattr(url, "full_url", url))
    if _yerel_mi(urlsplit(adres).hostname):
        # Yönetim sunucusunun 127.0.0.1 sağlık denetimi (desktop/server.py).
        return _ozgun_urlopen(url, *args, **kwargs)
    _kaydet("urlopen", adres)
    raise OSError("Dış istek engellendi (ağ tuzağı).")


def kur() -> None:
    # setattr: tip denetçisi yöntem imzasını C katmanının imzasıyla karşılaştırmasın.
    setattr(socket.socket, "connect", _connect)  # noqa: B010
    setattr(socket.socket, "connect_ex", _connect_ex)  # noqa: B010
    socket.getaddrinfo = _getaddrinfo
    urllib.request.urlopen = _urlopen


def _kendini_sina() -> int:
    for deneme in (
        lambda: socket.create_connection(("dis-ornek.invalid", 443), timeout=1),
        lambda: socket.create_connection(("203.0.113.7", 443), timeout=1),
        lambda: urllib.request.urlopen("https://api.github.com/", timeout=1),
    ):
        try:
            deneme()
        except OSError:
            pass
    return 0


def main() -> None:
    kur()
    argumanlar = sys.argv[1:]
    if argumanlar[:1] == ["--kendini-sina"]:
        raise SystemExit(_kendini_sina())
    # `--betik <komut> …`: prova betiğini tuzak altında koşar (ör. `gun-kapisi` — gün
    # değişimi kapısının gerçek işleri; `--autotest` kapıyı kurmadan döner).
    modul = "desktop.main"
    if argumanlar[:1] == ["--betik"]:
        modul, argumanlar = "desktop.tests.prova_betigi", argumanlar[1:]
    sys.argv = [modul, *argumanlar]
    runpy.run_module(modul, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
