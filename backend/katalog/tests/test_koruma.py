"""İki yüzeyin koruma testleri — katalog tarafı (tasarım §4.1, §5.10-2 ve §5.10-3).

Bu testler yönetim tarafının URL listesini okumak için Django'yu KULLANIR
(pytest-django `config.settings`). Katalog modülünün kendisi Django'nun URL,
ORM ve veritabanı katmanlarını içe aktaramaz; bunu aşağıdaki kaynak taraması
ve alt süreçteki çalışma anı denetimi birlikte kilitler.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, resolve
from django.urls.converters import (
    IntConverter,
    PathConverter,
    SlugConverter,
    StringConverter,
    UUIDConverter,
)
from django.urls.resolvers import RegexPattern, RoutePattern

from katalog import app as katalog_app
from katalog.app import ROUTES, SIGNATURE_META, application

KATALOG_DIR = Path(katalog_app.__file__).resolve().parent
BACKEND_DIR = KATALOG_DIR.parent

# `desktop/server.py::HEALTH_PATH` ile aynı yol; masaüstü öz sınaması da bunu yoklar.
SAGLIK_YOLU = "/api/v1/setup/status/"

# ============================================================ §5.10-2 (a)
# `api/` altındaki her desen, dönüştürücüler örnek değerle doldurularak katalog
# uygulamasına gönderilir ve 404 almalıdır.

_ORNEK_UUID = "12345678-1234-5678-1234-567812345678"
_DONUSTURUCU_ORNEKLERI: dict[type[Any], str] = {
    IntConverter: "1",
    StringConverter: "x",
    SlugConverter: "x",
    PathConverter: "x",
    UUIDConverter: _ORNEK_UUID,
}
# `re_path` grupları için sırayla denenen adaylar (ör. DRF yönlendiricisinin
# `(?P<pk>[^/.]+)` ve `(?P<format>[a-z0-9]+)` grupları).
_REGEX_ADAYLARI = ("1", "x", _ORNEK_UUID, "json")

_ROUTE_PARAMETRESI = re.compile(r"<(?:(?P<donusturucu>[^>:]+):)?(?P<ad>[^>]+)>")
_ADLI_GRUP = re.compile(r"\(\?P<(?P<ad>\w+)>(?P<govde>(?:[^()\\]|\\.)*)\)")
# Kaçırılmamış düzenli ifade işleci kalırsa örnek yol güvenilir değildir.
_KACIRILMAMIS_ISLEC = re.compile(r"(?<!\\)[.()\[\]{}*+?|^$]")


def _route_ornegi(desen: RoutePattern) -> str:
    """`path()` deseninin örnek yolu: her dönüştürücü bilinen bir değer alır."""
    donusturuculer: dict[str, Any] = dict(desen.converters)

    def degistir(eslesme: re.Match[str]) -> str:
        donusturucu = donusturuculer[eslesme["ad"]]
        ornek = _DONUSTURUCU_ORNEKLERI.get(type(donusturucu))
        if ornek is None:
            raise AssertionError(
                f"{type(donusturucu).__name__} için örnek değer yok ({desen}); "
                "_DONUSTURUCU_ORNEKLERI'ne ekleyin."
            )
        return ornek

    return _ROUTE_PARAMETRESI.sub(degistir, str(desen))


def _regex_ornegi(regex: str) -> str:
    """`re_path()` deseninin örnek yolu (fail-closed: çözemediği desende düşer)."""

    def grup(eslesme: re.Match[str]) -> str:
        for aday in _REGEX_ADAYLARI:
            if re.fullmatch(eslesme["govde"], aday):
                return aday
        raise AssertionError(f"'{eslesme['ad']}' grubu için örnek değer yok: {regex!r}")

    govde = regex.removeprefix("^").removesuffix("$").removesuffix(r"\Z")
    govde = govde.replace("/?", "/")  # isteğe bağlı eğik çizgi örnekte bulunur
    govde = _ADLI_GRUP.sub(grup, govde)
    if _KACIRILMAMIS_ISLEC.search(govde):
        raise AssertionError(f"örnek yol üretilemedi: {regex!r} (üreteci genişletin)")
    return re.sub(r"\\(.)", r"\1", govde)


def _parca_ornegi(desen: object) -> str:
    if isinstance(desen, RoutePattern):
        return _route_ornegi(desen)
    if isinstance(desen, RegexPattern):
        return _regex_ornegi(str(desen))
    raise AssertionError(f"bilinmeyen desen türü: {type(desen).__name__} ({desen})")


def _rota_birlestir(on: str, parca: str) -> str:
    """Django'nun `URLResolver._join_route` kuralı: ikinci parçanın `^`'i düşer."""
    return parca if not on else on + parca.removeprefix("^")


def _api_desenleri() -> list[tuple[str, str]]:
    """`api/` altındaki her uç için (Django rotası, örnek yol) çiftleri."""
    sonuc: list[tuple[str, str]] = []

    def gez(desenler: Sequence[URLPattern | URLResolver], rota: str, zincir: list[object]) -> None:
        for desen in desenler:
            tam = _rota_birlestir(rota, str(desen.pattern))
            yeni_zincir = [*zincir, desen.pattern]
            if isinstance(desen, URLResolver):
                gez(desen.url_patterns, tam, yeni_zincir)
            elif tam.removeprefix("^").startswith("api/"):
                ornek = "/" + "".join(_parca_ornegi(parca) for parca in yeni_zincir)
                sonuc.append((tam, ornek))

    gez(get_resolver().url_patterns, "", [])
    return sonuc


def _katalog_durumu(yol: str, yontem: str = "GET") -> tuple[int, bytes]:
    yakalanan: dict[str, str] = {}

    def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> Any:
        yakalanan["status"] = status
        return lambda veri: None

    ortam = {
        "REQUEST_METHOD": yontem,
        "PATH_INFO": yol,
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8765",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "http",
    }
    govde = b"".join(application(ortam, start_response))
    return int(yakalanan["status"].split(" ", 1)[0]), govde


def test_api_desen_listesi_bos_degil_ve_saglik_yolunu_icerir() -> None:
    """Gezinti gerçekten yönetim API'sini görüyor mu (boş liste yanlış yeşil verirdi)."""
    ornekler = [ornek for _, ornek in _api_desenleri()]

    assert len(ornekler) >= 10
    assert SAGLIK_YOLU in ornekler


def test_ornek_yollar_gercekten_kendi_desenine_cozulur() -> None:
    """Örnek değer doğru mu: her örnek yol Django'da tam da o desene çözülmeli."""
    for rota, ornek in _api_desenleri():
        assert resolve(ornek).route == rota, ornek


def test_api_altindaki_her_desen_katalogda_404_doner() -> None:
    for rota, ornek in _api_desenleri():
        for yontem in ("GET", "HEAD"):
            durum, govde = _katalog_durumu(ornek, yontem)
            assert durum == 404, f"{yontem} {ornek} ({rota}) katalogda {durum} döndü"
        durum, _ = _katalog_durumu(ornek, "POST")
        assert durum == 405, f"POST {ornek} katalogda {durum} döndü"


def test_route_ornegi_donusturuculeri_doldurur() -> None:
    desen = RoutePattern("works/<int:pk>/<slug:s>/<str:a>/<path:p>/<uuid:u>/")

    assert _route_ornegi(desen) == f"works/1/x/x/x/{_ORNEK_UUID}/"


def test_regex_ornegi_drf_yonlendirici_desenlerini_cozer() -> None:
    assert _regex_ornegi(r"^works/(?P<pk>[^/.]+)/$") == "works/1/"
    assert _regex_ornegi(r"^works\.(?P<format>[a-z0-9]+)/?$") == "works.1/"
    assert _regex_ornegi(r"^copies/(?P<id>[0-9a-f-]{36})/$") == f"copies/{_ORNEK_UUID}/"


def test_regex_ornegi_cozemedigi_desende_duser() -> None:
    with pytest.raises(AssertionError):
        _regex_ornegi(r"^(?!api/).*$")
    with pytest.raises(AssertionError):
        _regex_ornegi(r"^(?P<kod>[A-Z]{3})/$")


# ============================================================ §5.10-2 (b, c)


def test_katalog_yol_tablosu_anlik_goruntuyle_ayni() -> None:
    """Yeni katalog yolu bilinçli eklenir: bu anlık görüntü de güncellenir."""
    assert sorted(ROUTES) == ["/", "/saglik"]


def test_katalog_yolu_yonetim_on_ekleriyle_baslamaz() -> None:
    for yol in ROUTES:
        assert not yol.startswith(("/api", "/static", "/admin")), yol


def test_kok_yol_spa_degil_katalog_imzasini_dondurur() -> None:
    """`/` yönetimde SPA'ya düşer; katalogda katalog sayfasıdır (SPA catch-all test dışı)."""
    durum, govde = _katalog_durumu("/")
    metin = govde.decode("utf-8")

    assert durum == 200
    assert SIGNATURE_META in metin
    assert 'id="root"' not in metin  # SPA'nın `index.html` kökü
    assert "<script" not in metin


# ============================================================== §5.10-3
# Katalog paketi Django'nun veri, ayar ve URL katmanlarını; yönetim
# uygulamalarını; DRF'yi içe aktarmaz. Django'dan yalnız şablon motoru ve
# yardımcıları gelebilir (F5).

_YASAK_KOKLER = frozenset({"apps", "config", "rest_framework", "importlib"})
_DJANGO_IZINLI = ("django.template", "django.utils")


def _yasak_mi(modul: str) -> bool:
    kok = modul.split(".", 1)[0]
    if kok in _YASAK_KOKLER:
        return True
    if kok == "django":
        return not any(modul == izin or modul.startswith(izin + ".") for izin in _DJANGO_IZINLI)
    return False


def _importlari_tara(kaynak: str, paket: str) -> list[str]:
    """Kaynağın içe aktardığı (mutlak) adlardan yasak olanları döndürür."""
    yasaklar: list[str] = []
    for dugum in ast.walk(ast.parse(kaynak)):
        adlar: list[str] = []
        if isinstance(dugum, ast.Import):
            adlar = [alias.name for alias in dugum.names]
        elif isinstance(dugum, ast.ImportFrom):
            if dugum.level:
                taban = paket.split(".")[: len(paket.split(".")) - (dugum.level - 1)]
                on = ".".join([*taban, dugum.module] if dugum.module else taban)
            else:
                on = dugum.module or ""
            adlar = [f"{on}.{alias.name}" if on else alias.name for alias in dugum.names]
        elif isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name):
            if dugum.func.id == "__import__":
                adlar = ["importlib.__import__"]  # dinamik içe aktarma taramayı atlatırdı
        yasaklar.extend(ad for ad in adlar if _yasak_mi(ad))
    return yasaklar


def _katalog_kaynaklari() -> list[Path]:
    return sorted(
        dosya
        for dosya in KATALOG_DIR.rglob("*")
        if dosya.is_file()
        and "tests" not in dosya.relative_to(KATALOG_DIR).parts
        and "__pycache__" not in dosya.parts
    )


def test_katalog_kaynaginda_yasak_import_yok() -> None:
    bulunan: dict[str, list[str]] = {}
    for dosya in _katalog_kaynaklari():
        if dosya.suffix != ".py":
            continue
        # Göreli içe aktarma dosyanın bulunduğu pakete göre çözülür (`__init__` dahil).
        paket = ".".join(dosya.relative_to(BACKEND_DIR).parts[:-1])
        yasak = _importlari_tara(dosya.read_text(encoding="utf-8"), paket)
        if yasak:
            bulunan[str(dosya.relative_to(BACKEND_DIR))] = yasak

    assert bulunan == {}


@pytest.mark.parametrize(
    "kaynak",
    [
        "import django.db",
        "from django.db import models",
        "from django import db",
        "from django.conf import settings",
        "from django.urls import reverse",
        "import django",
        "from apps.okul import models",
        "import config.urls",
        "from rest_framework import serializers",
        "import importlib",
        "__import__('django.db')",
        "from ..apps.okul import models",
        "from .. import config",
    ],
)
def test_import_tarayicisi_yasak_importu_yakalar(kaynak: str) -> None:
    assert _importlari_tara(kaynak, "katalog") != []


@pytest.mark.parametrize(
    "kaynak",
    [
        "import sqlite3",
        "from django.template import Engine",
        "from django import template",
        "from django.utils.html import escape",
        "from . import app",
        "from .app import ROUTES",
        "from katalog.app import application",
    ],
)
def test_import_tarayicisi_izinli_importa_takilmaz(kaynak: str) -> None:
    assert _importlari_tara(kaynak, "katalog") == []


def test_katalog_ice_aktarilinca_veri_ve_url_katmani_yuklenmez() -> None:
    """Çalışma anı sigortası: dolaylı içe aktarma da (ör. `shared.models`) yakalanır.

    Taze bir alt süreçte yalnız `katalog.app` içe aktarılır; Django ayarı verilmez.
    """
    betik = "import json, sys\n" "import katalog.app\n" "print(json.dumps(sorted(sys.modules)))\n"
    ortam = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    sonuc = subprocess.run(  # noqa: S603 — sabit argümanlar, kabuk yok
        [sys.executable, "-c", betik],
        cwd=BACKEND_DIR,
        env=ortam,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert sonuc.returncode == 0, sonuc.stderr
    moduller: list[str] = json.loads(sonuc.stdout)

    def yuklu(on: str) -> list[str]:
        return [m for m in moduller if m == on or m.startswith(on + ".")]

    for yasak in ("django.db", "django.urls", "apps", "config", "rest_framework"):
        assert yuklu(yasak) == [], f"{yasak} katalogla birlikte yüklendi"


# Şablon kuralı (§4.1): katalog şablonlarında URL çözümleme ve etiket kitaplığı
# yükleme etiketleri geçmez. Kural bugünden paketteki HER dosyaya (şablon,
# gömülü HTML metni) uygulanır; şablon dizini F5'te eklendiğinde de kapsamdadır.
_YASAK_SABLON_ETIKETI = re.compile(r"\{%\s*(?:url|load)\b")


def test_katalog_dosyalarinda_url_ve_load_etiketi_yok() -> None:
    kaynaklar = _katalog_kaynaklari()
    assert any(dosya.name == "app.py" for dosya in kaynaklar)  # tarama boş koşmuyor

    bulunan = [
        str(dosya.relative_to(BACKEND_DIR))
        for dosya in kaynaklar
        if _YASAK_SABLON_ETIKETI.search(dosya.read_text(encoding="utf-8", errors="replace"))
    ]

    assert bulunan == []


@pytest.mark.parametrize(
    ("metin", "yasak"),
    [
        ("{% url 'setup-status' %}", True),
        ("{%url 'x'%}", True),
        ("{%   load static %}", True),
        ("{% urlize metin %}", False),
        ("{{ url }}", False),
        ("{% if yukle %}", False),
    ],
)
def test_sablon_etiketi_denetimi_dogru_ayirt_eder(metin: str, yasak: bool) -> None:
    assert bool(_YASAK_SABLON_ETIKETI.search(metin)) is yasak


# ============================================================== §5.10-20
# Ağ Kataloğu süreci HİÇ dış bağlantı açmaz (§4.1 değişmezi, §8.5-8). ISBN ile
# künye getirme (U13) yönetim yüzeyinin bir özelliğidir: katalog kaynağında ne
# künye paketi ne de giden bağlantı açan bir standart kütüphane modülü bulunur.
# Katalog sunucusunun DİNLEYEN soketi `desktop/katalog_server.py`dedir; bu paket
# yalnız WSGI uygulamasıdır ve soket açmaz.

_DIS_BAGLANTI_MODULLERI = frozenset(
    {
        "urllib",
        "http",
        "socket",
        "ssl",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "webbrowser",
        "requests",
        "httpx",
        "urllib3",
    }
)
#: Künye paketinin içe aktarıldığını yakalayan desen (ad alanı değişse de görünür).
_KUNYE_IMPORTU = re.compile(r"\bkunye\b")


def _dis_baglanti_importlari(kaynak: str) -> list[str]:
    bulunan: list[str] = []
    for dugum in ast.walk(ast.parse(kaynak)):
        adlar: list[str] = []
        if isinstance(dugum, ast.Import):
            adlar = [alias.name for alias in dugum.names]
        elif isinstance(dugum, ast.ImportFrom) and not dugum.level:
            adlar = [dugum.module or ""]
        bulunan.extend(ad for ad in adlar if ad.split(".", 1)[0] in _DIS_BAGLANTI_MODULLERI)
    return bulunan


def test_katalog_kaynaginda_dis_baglanti_cagrisi_ve_kunye_modulu_yok() -> None:
    bulunan: dict[str, list[str]] = {}
    for dosya in _katalog_kaynaklari():
        if dosya.suffix != ".py":
            continue
        kaynak = dosya.read_text(encoding="utf-8")
        sorunlar = _dis_baglanti_importlari(kaynak)
        if _KUNYE_IMPORTU.search(kaynak):
            sorunlar.append("kunye")
        if sorunlar:
            bulunan[str(dosya.relative_to(BACKEND_DIR))] = sorunlar

    assert bulunan == {}


@pytest.mark.parametrize(
    "kaynak",
    [
        "import urllib.request",
        "from urllib.request import urlopen",
        "import socket",
        "import http.client",
        "import requests",
    ],
)
def test_dis_baglanti_tarayicisi_yakalar(kaynak: str) -> None:
    assert _dis_baglanti_importlari(kaynak) != []


@pytest.mark.parametrize("kaynak", ["import sqlite3", "from django.template import Engine"])
def test_dis_baglanti_tarayicisi_izinli_importa_takilmaz(kaynak: str) -> None:
    assert _dis_baglanti_importlari(kaynak) == []
