"""Ağ Kataloğu WSGI uygulaması (tasarım §4.1, §5.2-§5.5).

Neden Django'nun istek zinciri değil de çıplak WSGI (T3): yönetim API'si ile
aynı uygulama ve URLconf ağa açılsaydı, tek bir izin listesi hatası yönetim
uçlarını okul ağına sızdırırdı. Burada yönetim yollarının karşılığı hiç yoktur;
yol tablosu sabit bir kümedir (`ROUTES`) ve bilinmeyen her yol sabit metinli
404 alır. Katalog Django'dan yalnız şablon motorunu kullanır (tembel yüklenir —
`sayfalar` modül belgesi); URLconf, ORM ve `django.db` içe aktarılmaz.

**İstek sırası** (her adım bir öncekini geçen isteğe uygulanır):

1. **Bakım kapısı** (`bakim.KAPI`, §5.3): geri yükleme sürerken veritabanına
   DOKUNMADAN 503. Kapıdan geçen her istek uçuştaki sayaca yazılır.
2. **Hız sınırı**: `REMOTE_ADDR` başına token-bucket → 429 + `Retry-After`.
   `X-Forwarded-For` okunmaz.
3. **Yöntem**: yalnız GET ve HEAD; diğerleri 405 + `Allow`.
4. **Gövde**: `CONTENT_LENGTH` 1024 baytı aşarsa 413, sayı değilse 400. Gövde
   hiçbir durumda OKUNMAZ (waitress ayrıca `max_request_body_size=1024`).
5. **Adres**: yol UTF-8 olarak, sorgu dizesi yüzde kodlamasından çözülür;
   bozuksa 400, sorgu dizesi çok uzunsa 414.
6. **Yol tablosu** → sayfa işleyicisi (`sayfalar`). Geçersiz `id`/`tur`/
   `konu`/harf → 404; veritabanına ulaşılamazsa 503.

**Başlıklar** her yanıtta aynıdır: CSP, `nosniff`, `no-referrer`; HTML ve hata
sayfaları `Cache-Control: no-store`. Çerez başlığı ortamdan OKUNMAZ, yanıta
çerez YAZILMAZ (T17). `Server` başlığını uygulama yazmaz (waitress `ident=None`).

**Günlük** (§5.5): erişim günlüğü YOKTUR. İstemci adresi, yol ve arama terimi
hiçbir yere yazılmaz; yalnız kişisiz günlük sayaçlar (`sayac`) ve Ağ
Doktoru'nun son hatası (sabit ileti) tutulur.

**Kuruluş.** Katalog veritabanı yolunu ve Türkçe katlama işlevlerini
kendisi bilemez (`apps.*` içe aktarılmaz); bunları `KatalogKurulumu` ile
dışarıdan alır. Modül düzeyindeki `application` süreç içi TEK örnektir ve
kurulumsuz doğar: Django açılırken (`prepare_django` → `KutuphaneConfig.ready`)
`apps.kutuphane.ag_katalogu.varsayilan_katalogu_kur()` onu veriye bağlar;
veritabanı yolu her istekte Django ayarından okunur. Kurulumsuzken `/` imzalı
ana sayfayı "bilgilere ulaşılamıyor" uyarısıyla verir, veri sayfaları 503
döner (öz sınama ve veritabanı gerektirmeyen masaüstü testleri bunu
kullanır). Ayrı bir örnek gerekiyorsa (testler, yük provası)
`create_app(...)` ya da `ag_katalogu.katalog_uygulamasi(...)` kullanılır.

**TB11.** `WAITRESS_HATA_GOREVI` (tembel): waitress'in kendi 400/413/431/500
yanıtlarını Türkçe ve CSP'li üreten görev sınıfı (`waitress_hatalari`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from katalog import sayfalar, veri
from katalog.bakim import KAPI, BakimKapisi
from katalog.hatalar import (
    HTML,
    SECURITY_HEADERS,
    SIGNATURE_META,
    Yanit,
    bakim,
    basliklar,
    hata,
)
from katalog.istek import AdresCokUzun, GecersizIstek, Istek, sorgu_dizesini_coz, yolu_coz
from katalog.sayac import GunlukSayaclar
from katalog.sayfalar import Bulunamadi, KatalogKurulumu, SayfaOrtami
from katalog.sinir import HizSiniri

if TYPE_CHECKING:
    from wsgiref.types import StartResponse, WSGIEnvironment

__all__ = [
    "ALLOWED_METHODS",
    "MAX_BODY_BYTES",
    "ROUTES",
    "SECURITY_HEADERS",
    "SIGNATURE_META",
    "KatalogKurulumu",
    "KatalogUygulamasi",
    "application",
    "create_app",
]

logger = logging.getLogger("kutuphane_defteri.katalog")

#: Kabul edilen en büyük istek gövdesi (bayt). waitress ayarıyla aynı değerdir.
MAX_BODY_BYTES: Final = 1024

#: Yalnız okuma yöntemleri; sıra `Allow` başlığında da kullanılır.
ALLOWED_METHODS: Final = ("GET", "HEAD")

#: Sabit yol tablosu (§5.5). Yeni yol yalnız buraya (ve `_SABIT`/`_PARAMETRELI`
#: eşlemelerine) eklenir; koruma testi tabloyu anlık görüntüyle karşılaştırır
#: ve yönetim API'siyle çakışmayı yakalar. `<id>` kanonik tam sayı, `<harf>`
#: dizin harflerinden biridir.
ROUTES: Final[tuple[str, ...]] = (
    "/",
    "/saglik",
    "/katalog.css",
    "/ara",
    "/eser/<id>",
    "/eserler",
    "/eserler/<harf>",
    "/yazarlar",
    "/yazarlar/<harf>",
    "/konular",
    "/konular/<harf>",
    "/hakkinda",
)

_SABIT: Final[dict[str, sayfalar.Isleyici]] = {
    "/": sayfalar.ana,
    "/saglik": sayfalar.saglik,
    "/katalog.css": sayfalar.stil,
    "/ara": sayfalar.ara,
    "/eserler": sayfalar.eserler_dizini,
    "/yazarlar": sayfalar.yazarlar_dizini,
    "/konular": sayfalar.konular,
    "/hakkinda": sayfalar.hakkinda,
}
_PARAMETRELI: Final[dict[str, sayfalar.Isleyici]] = {
    "eser": sayfalar.eser,
    "eserler": sayfalar.eserler_dizini,
    "yazarlar": sayfalar.yazarlar_dizini,
    "konular": sayfalar.konu_dizini,
}

#: Ağ Doktoru'na giden sabit hata iletileri (istisna metni, yol, sorgu YAZILMAZ).
HATA_VERI: Final = "Ağ Kataloğu veritabanına ulaşamadı."
HATA_SUNUCU: Final = "Ağ Kataloğu bir sayfayı üretirken beklenmeyen bir hata oluştu."


def _eslestir(yol: str) -> tuple[sayfalar.Isleyici, str | None] | None:
    """Yolu işleyiciye eşler; sondaki eğik çizgi ya da fazla parça 404'tür."""
    isleyici = _SABIT.get(yol)
    if isleyici is not None:
        return isleyici, None
    parcalar = yol.split("/")
    if len(parcalar) == 3 and parcalar[0] == "" and parcalar[2]:
        isleyici = _PARAMETRELI.get(parcalar[1])
        if isleyici is not None:
            return isleyici, parcalar[2]
    return None


def _govde_asiyor(environ: WSGIEnvironment) -> bool | None:
    """Gövde sınırı aşılıyor mu? `None`: `CONTENT_LENGTH` sayı değil (400)."""
    raw = str(environ.get("CONTENT_LENGTH") or "").strip()
    if not raw:
        return False
    if not raw.isascii() or not raw.isdigit():
        return None
    return int(raw) > MAX_BODY_BYTES


class KatalogUygulamasi:
    """Ağ Kataloğu WSGI uygulaması (modül belgesindeki istek sırası)."""

    def __init__(
        self,
        kurulum: KatalogKurulumu | None = None,
        *,
        bakim_kapisi: BakimKapisi | None = None,
        hiz_siniri: HizSiniri | None = None,
        sayaclar: GunlukSayaclar | None = None,
    ) -> None:
        self.bakim_kapisi = bakim_kapisi or KAPI
        self.hiz_siniri = hiz_siniri or HizSiniri()
        self.sayaclar = sayaclar or GunlukSayaclar()
        self.kurulum: KatalogKurulumu | None = None
        self._ortam = SayfaOrtami(None)
        self.kur(kurulum)

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD") or "").upper()
        yanit = self._yanitla(environ, method)
        start_response(yanit.status, basliklar(yanit))
        if method == "HEAD":
            # Başlıklar GET ile aynıdır (Content-Length dahil), gövde gönderilmez.
            return []
        return [yanit.body]

    def _yanitla(self, environ: WSGIEnvironment, method: str) -> Yanit:
        with self.bakim_kapisi.is_() as izin:
            if not izin:
                self.sayaclar.say("bakim")
                return bakim()
            try:
                yanit = self._isle(environ, method)
            except Exception:  # noqa: BLE001 — hiçbir hata yığın bilgisiyle ağa çıkmaz
                logger.exception(HATA_SUNUCU)
                self.sayaclar.hata_kaydet(HATA_SUNUCU)
                self.sayaclar.say("sunucu_hatasi")
                return hata(500)
        kod = int(yanit.status.split(" ", 1)[0])
        if kod == 200 and yanit.content_type == HTML:
            self.sayaclar.say("sayfa")
        elif kod == 404:
            self.sayaclar.say("bulunamadi")
        elif kod == 429:
            self.sayaclar.say("hiz_siniri")
        elif 400 <= kod < 500:
            self.sayaclar.say("reddedildi")
        return yanit

    def _isle(self, environ: WSGIEnvironment, method: str) -> Yanit:
        adres = str(environ.get("REMOTE_ADDR") or "")
        gecer, bekle = self.hiz_siniri.izin_ver(adres)
        if not gecer:
            return hata(429, ek_basliklar=(("Retry-After", str(bekle)),))

        if method not in ALLOWED_METHODS:
            return hata(405, ek_basliklar=(("Allow", ", ".join(ALLOWED_METHODS)),))

        asiyor = _govde_asiyor(environ)
        if asiyor is None:
            return hata(400)
        if asiyor:
            return hata(413)

        try:
            yol = yolu_coz(str(environ.get("PATH_INFO") or "/"))
            parametreler = sorgu_dizesini_coz(str(environ.get("QUERY_STRING") or ""))
        except AdresCokUzun:
            return hata(414)
        except GecersizIstek:
            return hata(400)

        eslesme = _eslestir(yol)
        if eslesme is None:
            return hata(404)
        isleyici, parametre = eslesme
        if isleyici is sayfalar.ara:
            self.sayaclar.say("arama")
        try:
            return isleyici(Istek(yol=yol, parametreler=parametreler), self._ortam, parametre)
        except Bulunamadi:
            return hata(404)
        except veri.VeriHatasi:
            self._veri_hatasi()
            return hata(503, ek_basliklar=(("Retry-After", "30"),))

    def _veri_hatasi(self) -> None:
        """Veriye ulaşılamadı: sabit ileti günlüğe ve Ağ Doktoru'na, sayaç bir artar.

        İstisna metni ve yığın günlüğe YAZILMAZ: dosya yolu, yol ya da sorgu
        içerebilirdi (§5.5).
        """
        logger.warning(HATA_VERI)
        self.sayaclar.hata_kaydet(HATA_VERI)
        self.sayaclar.say("veri_hatasi")

    def kur(self, kurulum: KatalogKurulumu | None) -> None:
        """Veri kaynağını (yeniden) bağlar; uçuştaki istek eski ortamla biter."""
        self.kurulum = kurulum
        self._ortam = SayfaOrtami(kurulum, veri_hatasi=self._veri_hatasi)


def create_app(
    kurulum: KatalogKurulumu | None,
    *,
    bakim_kapisi: BakimKapisi | None = None,
    hiz_siniri: HizSiniri | None = None,
    sayaclar: GunlukSayaclar | None = None,
) -> KatalogUygulamasi:
    """Katalog uygulamasını kurar (bakım kapısı varsayılan olarak süreç içi `KAPI`)."""
    return KatalogUygulamasi(
        kurulum, bakim_kapisi=bakim_kapisi, hiz_siniri=hiz_siniri, sayaclar=sayaclar
    )


#: Süreç içi katalog uygulaması (modül belgesi, "Kuruluş"). Kurulumsuz doğar;
#: Django açılırken `apps.kutuphane` uygulaması onu veriye bağlar.
application: Final = create_app(None)


def __getattr__(ad: str) -> object:
    """`WAITRESS_HATA_GOREVI`: waitress'in hata görevinin Türkçe alt sınıfı (TB11).

    Tembeldir: bu modülü içe aktarmak waitress'i yüklemez. waitress yoksa ad
    yokmuş gibi davranılır (`getattr(..., None)` güvenli).
    """
    if ad == "WAITRESS_HATA_GOREVI":
        try:
            from katalog.waitress_hatalari import hata_gorevi_sinifi
        except ImportError as exc:  # pragma: no cover — waitress her pakette var
            raise AttributeError(ad) from exc
        try:
            return hata_gorevi_sinifi()
        except ImportError as exc:
            raise AttributeError(ad) from exc
    raise AttributeError(f"module {__name__!r} has no attribute {ad!r}")
