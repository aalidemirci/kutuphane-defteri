"""Ağ Kataloğu WSGI uygulamasının davranış testleri (tasarım §5.4, §5.5).

Uygulama doğrudan WSGI sözleşmesiyle çağrılır; sunucu ve Django gerekmez.
Gerçek waitress üzerinden uçtan uca sınama `desktop/tests/test_katalog_server.py`
içindedir.
"""

from __future__ import annotations

import ast
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from katalog import app as katalog_app
from katalog.app import MAX_BODY_BYTES, SIGNATURE_META, application

KATALOG_DIR = Path(katalog_app.__file__).resolve().parent

BEKLENEN_CSP = (
    "default-src 'none'; style-src 'self'; img-src 'self' data:; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


class _Yanit:
    def __init__(self, status: str, headers: list[tuple[str, str]], body: bytes) -> None:
        self.status = status
        self.code = int(status.split(" ", 1)[0])
        self.headers = headers
        self.body = body

    def header(self, ad: str) -> str | None:
        degerler = [v for k, v in self.headers if k.lower() == ad.lower()]
        assert len(degerler) <= 1, f"{ad} başlığı birden çok kez gönderildi"
        return degerler[0] if degerler else None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")


def _ortam(path: str = "/", method: str = "GET", **ek: Any) -> dict[str, Any]:
    ortam: dict[str, Any] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8765",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    ortam.update(ek)
    return ortam


def _cagir(ortam: dict[str, Any]) -> _Yanit:
    yakalanan: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]], exc_info: Any = None) -> Any:
        yakalanan["status"] = status
        yakalanan["headers"] = headers
        return lambda veri: None

    govde = b"".join(application(ortam, start_response))
    return _Yanit(yakalanan["status"], yakalanan["headers"], govde)


def _istek(path: str = "/", method: str = "GET", **ek: Any) -> _Yanit:
    return _cagir(_ortam(path, method, **ek))


# ----------------------------------------------------------------- sayfalar


def test_ana_sayfa_imzayi_ve_turkce_basligi_dondurur() -> None:
    yanit = _istek("/")

    assert yanit.code == 200
    assert yanit.header("Content-Type") == "text/html; charset=utf-8"
    assert SIGNATURE_META in yanit.text
    assert "Kütüphane Defteri — Ağ Kataloğu hazırlanıyor" in yanit.text
    assert '<html lang="tr">' in yanit.text
    assert yanit.header("Content-Length") == str(len(yanit.body))


def test_saglik_yolu_duz_metin_tamam_doner() -> None:
    yanit = _istek("/saglik")

    assert yanit.code == 200
    assert yanit.header("Content-Type") == "text/plain; charset=utf-8"
    assert yanit.body == b"tamam"


@pytest.mark.parametrize(
    "yol",
    [
        "/yok",
        "/saglik/",  # sondaki eğik çizgi ayrı bir yoldur
        "/api/v1/setup/status/",
        "/admin/",
        "/static/app.js",
        "/<script>alert(1)</script>",
    ],
)
def test_bilinmeyen_yol_sabit_turkce_404_doner(yol: str) -> None:
    yanit = _istek(yol)

    assert yanit.code == 404
    assert "Sayfa bulunamadı" in yanit.text
    assert SIGNATURE_META in yanit.text  # yanıtı veren katalogdur
    # Sabit metin: istenen yol, sürüm ya da iç bilgi geri basılmaz.
    assert yol not in yanit.text
    assert "script" not in yanit.text.lower()
    assert "Traceback" not in yanit.text


# ------------------------------------------------------------------ yöntemler


@pytest.mark.parametrize(
    "yontem", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
)
def test_yalniz_get_ve_head_kabul_edilir(yontem: str) -> None:
    yanit = _istek("/", yontem)

    assert yanit.code == 405
    assert yanit.header("Allow") == "GET, HEAD"
    assert "desteklenmiyor" in yanit.text


def test_yontem_buyuk_kucuk_harfe_duyarsiz_okunur() -> None:
    assert _istek("/", "get").code == 200
    assert _istek("/", "post").code == 405


def test_head_govdesiz_ama_get_ile_ayni_basliklari_doner() -> None:
    get = _istek("/")
    head = _istek("/", "HEAD")

    assert head.code == 200
    assert head.body == b""
    assert head.headers == get.headers  # Content-Length dahil


def test_bilinmeyen_yolda_head_de_404_doner() -> None:
    yanit = _istek("/api/v1/students/", "HEAD")

    assert yanit.code == 404
    assert yanit.body == b""


# ------------------------------------------------------------------- gövde


def test_bir_kilobayti_asan_govde_413_ile_reddedilir() -> None:
    yanit = _istek("/", CONTENT_LENGTH=str(MAX_BODY_BYTES + 1))

    assert yanit.code == 413
    assert "çok büyük" in yanit.text


def test_sinirdaki_govde_kabul_edilir_ama_okunmaz() -> None:
    class _OkunmayanGirdi(io.BytesIO):
        def read(self, *args: Any, **kwargs: Any) -> bytes:
            raise AssertionError("katalog istek gövdesini okumamalı")

    ortam = _ortam("/", CONTENT_LENGTH=str(MAX_BODY_BYTES))
    ortam["wsgi.input"] = _OkunmayanGirdi(b"x" * MAX_BODY_BYTES)

    yanit = _cagir(ortam)

    assert yanit.code == 200


@pytest.mark.parametrize("deger", ["abc", "-1", "1e3", "١٢"])
def test_gecersiz_icerik_uzunlugu_400_doner(deger: str) -> None:
    yanit = _istek("/", CONTENT_LENGTH=deger)

    assert yanit.code == 400
    assert "Geçersiz istek" in yanit.text


def test_bos_icerik_uzunlugu_gecerlidir() -> None:
    assert _istek("/", CONTENT_LENGTH="").code == 200


def test_govde_siniri_waitress_ayariyla_ayni() -> None:
    """Uygulama sınırı ile sunucu sınırı aynı değerdir (§5.2: 1 KB)."""
    assert MAX_BODY_BYTES == 1024


# ------------------------------------------------------------- başlıklar


def _tum_yanit_turleri() -> Iterator[_Yanit]:
    yield _istek("/")
    yield _istek("/saglik")
    yield _istek("/", "HEAD")
    yield _istek("/yok")
    yield _istek("/", "POST")
    yield _istek("/", CONTENT_LENGTH="5000")
    yield _istek("/", CONTENT_LENGTH="abc")


def test_guvenlik_basliklari_her_yanitta_bulunur() -> None:
    for yanit in _tum_yanit_turleri():
        assert yanit.header("Content-Security-Policy") == BEKLENEN_CSP, yanit.status
        assert yanit.header("X-Content-Type-Options") == "nosniff", yanit.status
        assert yanit.header("Referrer-Policy") == "no-referrer", yanit.status
        assert yanit.header("Cache-Control") == "no-store", yanit.status
        assert yanit.header("Set-Cookie") is None, yanit.status
        assert yanit.header("Server") is None, yanit.status


def test_html_sayfalarinda_betik_ve_satir_ici_stil_yok() -> None:
    """CSP `default-src 'none'`: satır içi betik/stil zaten çalışmaz; hiç yazılmaz."""
    for yanit in _tum_yanit_turleri():
        metin = yanit.text.lower()
        assert "<script" not in metin
        assert "<style" not in metin
        assert "style=" not in metin
        assert "javascript:" not in metin


# ------------------------------------------------------------------ çerez


class _KayitliOrtam(dict[str, Any]):
    """Hangi anahtarların okunduğunu kaydeden WSGI ortamı."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.okunan: set[str] = set()

    def __getitem__(self, anahtar: str) -> Any:
        self.okunan.add(anahtar)
        return super().__getitem__(anahtar)

    def get(self, anahtar: str, varsayilan: Any = None) -> Any:
        self.okunan.add(anahtar)
        return super().get(anahtar, varsayilan)

    def __contains__(self, anahtar: object) -> bool:
        self.okunan.add(str(anahtar))
        return super().__contains__(anahtar)

    def __iter__(self) -> Iterator[str]:
        self.okunan.add("*")
        return super().__iter__()

    def keys(self) -> Any:
        self.okunan.add("*")
        return super().keys()

    def items(self) -> Any:
        self.okunan.add("*")
        return super().items()

    def values(self) -> Any:
        self.okunan.add("*")
        return super().values()


@pytest.mark.parametrize(("yol", "yontem"), [("/", "GET"), ("/yok", "GET"), ("/", "POST")])
def test_cerez_basligi_okunmaz_ve_cerez_yazilmaz(yol: str, yontem: str) -> None:
    ortam = _KayitliOrtam(_ortam(yol, yontem, HTTP_COOKIE="kd_oturum=gizli"))

    yanit = _cagir(ortam)

    assert "HTTP_COOKIE" not in ortam.okunan
    assert "*" not in ortam.okunan  # ortam toptan dolaşılmaz (dolaylı okuma yok)
    assert yanit.header("Set-Cookie") is None
    assert "gizli" not in yanit.text


def test_katalog_kaynaginda_cerez_sabiti_gecmez() -> None:
    """Statik sigorta: çerez başlığının adı kaynakta bir değer olarak hiç geçmez."""
    bulunan: list[str] = []
    for dosya in sorted(KATALOG_DIR.rglob("*.py")):
        if "tests" in dosya.relative_to(KATALOG_DIR).parts:
            continue
        for dugum in ast.walk(ast.parse(dosya.read_text(encoding="utf-8"))):
            if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
                if dugum.value.strip().lower() in {"http_cookie", "set-cookie", "cookie"}:
                    bulunan.append(f"{dosya.name}:{dugum.lineno}")

    assert bulunan == []
