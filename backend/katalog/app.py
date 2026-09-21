"""Ağ Kataloğu WSGI uygulaması — iskelet (tasarım §4.1, §5.2, §5.4, §5.5).

Bu sürüm yalnız iskelettir: sabit bir "hazırlanıyor" sayfası ve kısa bir sağlık
yanıtı sunar. Arama, eser sayfaları ve dizinler sonraki fazda (F5) aynı yol
tablosuna eklenir; şablonlar `django.template.Engine(autoescape=True)` ile
işlenecektir. Bu modül bugün yalnız standart kütüphaneyi kullanır.

Neden Django'nun istek zinciri değil de çıplak WSGI (T3): yönetim API'si ile
aynı uygulama ve URLconf ağa açılsaydı, tek bir izin listesi hatası yönetim
uçlarını okul ağına sızdırırdı. Burada yönetim yollarının karşılığı hiç yoktur;
bilinmeyen her yol sabit metinli 404 alır.

Güvenlik yüzeyi (§5.5):

- Yöntem: yalnız GET ve HEAD; diğerleri 405 + `Allow`.
- Gövde: `CONTENT_LENGTH` 1024 baytı aşarsa 413. Gövde hiçbir durumda okunmaz
  (waitress ayrıca `max_request_body_size=1024` ile sınırlar).
- Başlıklar her yanıtta aynıdır: CSP, `nosniff`, `no-referrer`, `no-store`.
- Çerez başlığı ortamdan okunmaz, yanıta çerez yazılmaz (T17).
- Hata sayfaları Türkçe ve sabittir: istenen yol, sürüm ya da iç bilgi basılmaz.
- Her HTML sayfası `SIGNATURE_META` işaretini taşır; masaüstü öz sınaması
  (`desktop/katalog_server.py`) `/` yanıtında bu işareti arar. Böylece portta
  başka bir uygulamanın (ör. yönetim SPA'sının) yanıt vermediği kanıtlanır.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from wsgiref.types import StartResponse, WSGIEnvironment

#: Katalog sayfalarının imzası: öz sınama ve koruma testleri bunu arar.
SIGNATURE_META: Final = '<meta name="kd-katalog" content="1">'

#: Kabul edilen en büyük istek gövdesi (bayt). waitress ayarıyla aynı değerdir.
MAX_BODY_BYTES: Final = 1024

#: Yalnız okuma yöntemleri; sıra `Allow` başlığında da kullanılır.
ALLOWED_METHODS: Final = ("GET", "HEAD")

#: Her yanıtta gönderilen güvenlik başlıkları (§5.5). Satır içi stil ve betik
#: yoktur; F5'te gömülü CSS `style-src 'self'` altında ayrı yoldan sunulur.
SECURITY_HEADERS: Final = (
    (
        "Content-Security-Policy",
        "default-src 'none'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    ),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)

_HTML: Final = "text/html; charset=utf-8"
_TEXT: Final = "text/plain; charset=utf-8"


class Response(NamedTuple):
    """Yol işleyicisinin ürettiği yanıt (başlıklar uygulama tarafından eklenir)."""

    status: str
    content_type: str
    body: bytes


def _page(title: str, heading: str, paragraph: str) -> bytes:
    """Sabit metinli, betiksiz, satır içi stilsiz bir HTML sayfası üretir.

    Girdiler modül içi sabitlerdir; kullanıcı girdisi buraya ulaşmaz. F5'te
    sayfalar otomatik kaçırmalı şablon motoruna taşınır.
    """
    html = (
        "<!doctype html>\n"
        '<html lang="tr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{SIGNATURE_META}\n"
        f"<title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>{heading}</h1>\n"
        f"<p>{paragraph}</p>\n"
        "</body>\n"
        "</html>\n"
    )
    return html.encode("utf-8")


_INDEX_BODY: Final = _page(
    "Ağ Kataloğu — Kütüphane Defteri",
    "Kütüphane Defteri — Ağ Kataloğu hazırlanıyor",
    "Okul kütüphanesinin kataloğu yakında buradan taranabilecek. "
    "Ağ Kataloğu kişisel veri göstermez.",
)
_NOT_FOUND_BODY: Final = _page(
    "Sayfa bulunamadı — Ağ Kataloğu",
    "Sayfa bulunamadı",
    'Aradığınız sayfa Ağ Kataloğunda yok. <a href="/">Ana sayfaya dönün.</a>',
)
_METHOD_NOT_ALLOWED_BODY: Final = _page(
    "İstek desteklenmiyor — Ağ Kataloğu",
    "Bu istek desteklenmiyor",
    'Ağ Kataloğu yalnız sayfa görüntülemeye açıktır. <a href="/">Ana sayfaya dönün.</a>',
)
_TOO_LARGE_BODY: Final = _page(
    "İstek çok büyük — Ağ Kataloğu",
    "İstek çok büyük",
    'Ağ Kataloğu bu isteği kabul etmedi. <a href="/">Ana sayfaya dönün.</a>',
)
_BAD_REQUEST_BODY: Final = _page(
    "Geçersiz istek — Ağ Kataloğu",
    "Geçersiz istek",
    'Ağ Kataloğu bu isteği anlayamadı. <a href="/">Ana sayfaya dönün.</a>',
)


def _index() -> Response:
    return Response("200 OK", _HTML, _INDEX_BODY)


def _health() -> Response:
    return Response("200 OK", _TEXT, b"tamam")


#: Sabit yol tablosu (§5.5). Yeni yol yalnız buraya eklenir; koruma testi
#: tabloyu anlık görüntüyle karşılaştırır ve yönetim API'siyle çakışmayı yakalar.
ROUTES: Final[Mapping[str, Callable[[], Response]]] = MappingProxyType(
    {
        "/": _index,
        "/saglik": _health,
    }
)


def _body_too_large(environ: WSGIEnvironment) -> bool | None:
    """Gövde sınırı aşılıyor mu? `None`: `CONTENT_LENGTH` sayı değil (400)."""
    raw = str(environ.get("CONTENT_LENGTH") or "").strip()
    if not raw:
        return False
    if not raw.isascii() or not raw.isdigit():
        return None
    return int(raw) > MAX_BODY_BYTES


def _dispatch(environ: WSGIEnvironment, method: str) -> tuple[Response, list[tuple[str, str]]]:
    """İsteği yanıta çevirir: yöntem → gövde → yol sırasıyla denetlenir."""
    if method not in ALLOWED_METHODS:
        response = Response("405 Method Not Allowed", _HTML, _METHOD_NOT_ALLOWED_BODY)
        return response, [("Allow", ", ".join(ALLOWED_METHODS))]

    too_large = _body_too_large(environ)
    if too_large is None:
        return Response("400 Bad Request", _HTML, _BAD_REQUEST_BODY), []
    if too_large:
        return Response("413 Content Too Large", _HTML, _TOO_LARGE_BODY), []

    handler = ROUTES.get(str(environ.get("PATH_INFO") or "/"))
    if handler is None:
        return Response("404 Not Found", _HTML, _NOT_FOUND_BODY), []
    return handler(), []


def application(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    """Ağ Kataloğu WSGI giriş noktası."""
    method = str(environ.get("REQUEST_METHOD") or "").upper()
    response, extra_headers = _dispatch(environ, method)
    headers = [
        ("Content-Type", response.content_type),
        ("Content-Length", str(len(response.body))),
        *SECURITY_HEADERS,
        *extra_headers,
    ]
    start_response(response.status, headers)
    if method == "HEAD":
        # Başlıklar GET ile aynıdır (Content-Length dahil), gövde gönderilmez.
        return []
    return [response.body]
