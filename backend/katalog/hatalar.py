"""Yanıt türü, güvenlik başlıkları ve Türkçe sabit hata sayfaları (tasarım §5.4, §5.5).

Hata sayfaları ŞABLON MOTORU KULLANMADAN, modül yüklenirken bir kez üretilen
sabit baytlardır: şablon motoru ya da veritabanı çökse bile Türkçe ve CSP'li bir
hata sayfası verilebilsin. İçerikleri sabittir — istenen yol, sorgu, sürüm,
iç yol ya da yığın bilgisi basılmaz (§5.4 "Hata sayfaları").

Aynı sayfalar waitress'in kendi ürettiği 400/413/431/500 yanıtlarında da
kullanılır (`katalog.waitress_hatalari`, TB11): istek uygulamaya hiç
ulaşmadığında da okul ağındaki tarayıcı Türkçe bir sayfa görür.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, NamedTuple

#: Katalog sayfalarının imzası: öz sınama ve koruma testleri bunu arar.
SIGNATURE_META: Final = '<meta name="kd-katalog" content="1">'

HTML: Final = "text/html; charset=utf-8"
TEXT: Final = "text/plain; charset=utf-8"
CSS: Final = "text/css; charset=utf-8"

#: İçerik güvenlik politikası (§5.5) — birebir.
CSP: Final = (
    "default-src 'none'; style-src 'self'; img-src 'self' data:; "
    "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)

#: Her yanıtta gönderilen güvenlik başlıkları (§5.5). `Cache-Control` yanıt
#: türüne göre ayrıca eklenir: HTML ve hata sayfaları `no-store` (paylaşılan
#: tahta tarayıcısında arama izi kalmasın), gömülü stil kısa süre önbelleklenir.
SECURITY_HEADERS: Final[tuple[tuple[str, str], ...]] = (
    ("Content-Security-Policy", CSP),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
)
NO_STORE: Final = "no-store"


class Yanit(NamedTuple):
    """Yol işleyicisinin ürettiği yanıt (güvenlik başlıkları uygulamada eklenir)."""

    status: str
    content_type: str
    body: bytes
    cache_control: str = NO_STORE
    ek_basliklar: tuple[tuple[str, str], ...] = ()


def _sayfa(baslik: str, paragraf: str) -> bytes:
    """Sabit metinli, betiksiz, satır içi stilsiz bir hata sayfası (girdiler modül sabitidir)."""
    html = (
        "<!doctype html>\n"
        '<html lang="tr">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{SIGNATURE_META}\n"
        '<meta name="referrer" content="no-referrer">\n'
        '<link rel="icon" href="data:,">\n'
        '<link rel="stylesheet" href="/katalog.css">\n'
        f"<title>{baslik} — Ağ Kataloğu</title>\n"
        "</head>\n"
        "<body>\n"
        '<main class="icerik">\n'
        f"<h1>{baslik}</h1>\n"
        f"<p>{paragraf}</p>\n"
        '<p><a href="/">Ağ Kataloğu ana sayfasına dönün.</a></p>\n'
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )
    return html.encode("utf-8")


#: Durum kodu → (durum satırı, sayfa baytları). Durum satırının gerekçe ifadesi
#: HTTP'nin kendisidir (İngilizce); kullanıcı yalnız Türkçe gövdeyi görür.
HATA_SAYFALARI: Final = MappingProxyType(
    {
        400: (
            "400 Bad Request",
            _sayfa("Geçersiz istek", "Ağ Kataloğu bu isteği anlayamadı."),
        ),
        404: (
            "404 Not Found",
            _sayfa("Sayfa bulunamadı", "Aradığınız sayfa Ağ Kataloğunda yok."),
        ),
        405: (
            "405 Method Not Allowed",
            _sayfa(
                "Bu istek desteklenmiyor",
                "Ağ Kataloğu yalnız sayfa görüntülemeye açıktır.",
            ),
        ),
        413: (
            "413 Content Too Large",
            _sayfa("İstek çok büyük", "Ağ Kataloğu bu isteği kabul etmedi."),
        ),
        414: (
            "414 URI Too Long",
            _sayfa("Adres çok uzun", "Ağ Kataloğu bu kadar uzun bir adresi kabul etmez."),
        ),
        429: (
            "429 Too Many Requests",
            _sayfa(
                "Çok sık istek gönderildi",
                "Bu bilgisayardan kısa sürede çok sayıda istek geldi. "
                "Birkaç saniye bekleyip yeniden deneyin.",
            ),
        ),
        431: (
            "431 Request Header Fields Too Large",
            _sayfa("İstek çok büyük", "Ağ Kataloğu bu isteği kabul etmedi."),
        ),
        500: (
            "500 Internal Server Error",
            _sayfa(
                "Bir sorun oluştu",
                "Ağ Kataloğu bu sayfayı şu an gösteremiyor. Biraz sonra yeniden deneyin.",
            ),
        ),
        501: (
            "501 Not Implemented",
            _sayfa("Bu istek desteklenmiyor", "Ağ Kataloğu yalnız sayfa görüntülemeye açıktır."),
        ),
        503: (
            "503 Service Unavailable",
            _sayfa(
                "Ağ Kataloğu şu an kullanılamıyor",
                "Katalog bilgilerine şu an ulaşılamıyor. Biraz sonra yeniden deneyin; "
                "sorun sürerse kütüphaneye haber verin.",
            ),
        ),
    }
)

#: Bakım (geri yükleme) sırasındaki 503 sayfası — veritabanına DOKUNULMADAN verilir.
BAKIM_SAYFASI: Final = _sayfa(
    "Ağ Kataloğu bakımda",
    "Kütüphane Defteri'nde bakım yapılıyor; katalog kısa bir süre kapalı. "
    "Biraz sonra yeniden deneyin.",
)


def hata(kod: int, *, ek_basliklar: tuple[tuple[str, str], ...] = ()) -> Yanit:
    """Sabit Türkçe hata yanıtı; bilinmeyen kod 500 sayfasına düşer."""
    status, govde = HATA_SAYFALARI.get(kod, HATA_SAYFALARI[500])
    return Yanit(status, HTML, govde, NO_STORE, ek_basliklar)


def bakim() -> Yanit:
    return Yanit("503 Service Unavailable", HTML, BAKIM_SAYFASI, NO_STORE, (("Retry-After", "60"),))


def basliklar(yanit: Yanit) -> list[tuple[str, str]]:
    """Yanıtın bütün başlıkları: içerik, güvenlik, önbellek ve ekler (tekrar yok)."""
    return [
        ("Content-Type", yanit.content_type),
        ("Content-Length", str(len(yanit.body))),
        *SECURITY_HEADERS,
        ("Cache-Control", yanit.cache_control),
        *yanit.ek_basliklar,
    ]
