"""Ağ Kataloğu WSGI uygulamasının HTTP davranışı (tasarım §5.4, §5.5, §5.10-6).

Bu dosyadaki testler veritabanı İSTEMEZ: kurulumsuz bir örnek (`create_app(None)`)
yöntem, gövde, başlık, çerez, bakım ve hata sayfası davranışını sınar. Veriye
ulaşan sayfalar `test_sayfalar.py`'dedir; gerçek waitress üzerinden uçtan uca
sınama `desktop/tests/test_katalog_server.py` ve `test_waitress_hatalari.py`'dedir.
"""

from __future__ import annotations

import ast
import io
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from katalog import app as katalog_app
from katalog.app import (
    MAX_BODY_BYTES,
    SIGNATURE_META,
    KatalogKurulumu,
    KatalogUygulamasi,
    create_app,
)
from katalog.bakim import BakimKapisi
from katalog.hatalar import CSP
from katalog.sayac import GunlukSayaclar
from katalog.tests.conftest import Yanit, cagir, genis_hiz_siniri, ortam_kur

KATALOG_DIR = Path(katalog_app.__file__).resolve().parent


@pytest.fixture
def uygulama() -> KatalogUygulamasi:
    """Kurulumsuz (verisiz) katalog: kendi bakım kapısı, geniş hız sınırı."""
    return create_app(None, bakim_kapisi=BakimKapisi(), hiz_siniri=genis_hiz_siniri())


def _istek(uygulama: Any, adres: str = "/", yontem: str = "GET", **ek: Any) -> Yanit:
    return cagir(uygulama, ortam_kur(adres, yontem=yontem, **ek))


# ----------------------------------------------------------------- sayfalar


def test_ana_sayfa_imzayi_ve_turkce_icerigi_doner(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/")

    assert yanit.code == 200
    assert yanit.header("Content-Type") == "text/html; charset=utf-8"
    assert SIGNATURE_META in yanit.text
    assert '<html lang="tr">' in yanit.text
    assert "Ağ Kataloğu" in yanit.text
    assert yanit.header("Content-Length") == str(len(yanit.body))


def test_verisiz_ana_sayfa_acilir_ama_uyarir(uygulama: KatalogUygulamasi) -> None:
    """Kurulumsuz ya da veritabanına ulaşılamayan katalog `/`'da imzalı sayfa verir."""
    yanit = _istek(uygulama, "/")

    assert "Katalog bilgilerine şu an ulaşılamıyor" in yanit.text


@pytest.mark.parametrize("yol", ["/ara", "/eser/1", "/eserler/A", "/yazarlar", "/konular"])
def test_verisiz_veri_sayfalari_503_ve_sabit_turkce_doner(
    uygulama: KatalogUygulamasi, yol: str
) -> None:
    yanit = _istek(uygulama, yol)

    assert yanit.code == 503
    assert "şu an kullanılamıyor" in yanit.text
    assert yanit.header("Retry-After") == "30"
    assert SIGNATURE_META in yanit.text


def test_saglik_yolu_duz_metin_tamam_doner(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/saglik")

    assert yanit.code == 200
    assert yanit.header("Content-Type") == "text/plain; charset=utf-8"
    assert yanit.body == b"tamam"


def test_gomulu_stil_css_olarak_ve_onbellekli_verilir(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/katalog.css")

    assert yanit.code == 200
    assert yanit.header("Content-Type") == "text/css; charset=utf-8"
    assert yanit.header("Cache-Control") == "public, max-age=3600"
    assert yanit.header("X-Content-Type-Options") == "nosniff"
    assert b"any-pointer: coarse" in yanit.body


@pytest.mark.parametrize(
    "yol",
    [
        "/yok",
        "/saglik/",  # sondaki eğik çizgi ayrı bir yoldur
        "/eser/1/",
        "/eser/1/2",
        "/api/v1/setup/status/",
        "/admin/",
        "/static/app.js",
        "/<script>alert(1)</script>",
    ],
)
def test_bilinmeyen_yol_sabit_turkce_404_doner(uygulama: KatalogUygulamasi, yol: str) -> None:
    yanit = _istek(uygulama, yol)

    assert yanit.code == 404
    assert "Sayfa bulunamadı" in yanit.text
    assert SIGNATURE_META in yanit.text  # yanıtı veren katalogdur
    # Sabit metin: istenen yol, sürüm ya da iç bilgi geri basılmaz.
    assert yol not in yanit.text
    assert "script" not in yanit.text.lower()
    assert "Traceback" not in yanit.text


# ------------------------------------------------------------------ yöntemler (§5.10-6)


@pytest.mark.parametrize(
    "yontem", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
)
@pytest.mark.parametrize("yol", ["/", "/ara", "/eser/1", "/yok"])
def test_yalniz_get_ve_head_kabul_edilir(
    uygulama: KatalogUygulamasi, yontem: str, yol: str
) -> None:
    yanit = _istek(uygulama, yol, yontem)

    assert yanit.code == 405
    assert yanit.header("Allow") == "GET, HEAD"
    assert "desteklenmiyor" in yanit.text


def test_yontem_buyuk_kucuk_harfe_duyarsiz_okunur(uygulama: KatalogUygulamasi) -> None:
    assert _istek(uygulama, "/", "get").code == 200
    assert _istek(uygulama, "/", "post").code == 405


def test_head_govdesiz_ama_get_ile_ayni_basliklari_doner(uygulama: KatalogUygulamasi) -> None:
    get = _istek(uygulama, "/saglik")
    head = _istek(uygulama, "/saglik", "HEAD")

    assert head.code == 200
    assert head.body == b""
    assert head.headers == get.headers  # Content-Length dahil


def test_bilinmeyen_yolda_head_de_404_doner(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/api/v1/students/", "HEAD")

    assert yanit.code == 404
    assert yanit.body == b""


# ------------------------------------------------------------------- gövde


def test_bir_kilobayti_asan_govde_413_ile_reddedilir(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/", CONTENT_LENGTH=str(MAX_BODY_BYTES + 1))

    assert yanit.code == 413
    assert "çok büyük" in yanit.text


def test_sinirdaki_govde_kabul_edilir_ama_okunmaz(uygulama: KatalogUygulamasi) -> None:
    class _OkunmayanGirdi(io.BytesIO):
        def read(self, *args: Any, **kwargs: Any) -> bytes:
            raise AssertionError("katalog istek gövdesini okumamalı")

    ortam = ortam_kur("/saglik", CONTENT_LENGTH=str(MAX_BODY_BYTES))
    ortam["wsgi.input"] = _OkunmayanGirdi(b"x" * MAX_BODY_BYTES)

    assert cagir(uygulama, ortam).code == 200


@pytest.mark.parametrize("deger", ["abc", "-1", "1e3", "١٢"])
def test_gecersiz_icerik_uzunlugu_400_doner(uygulama: KatalogUygulamasi, deger: str) -> None:
    yanit = _istek(uygulama, "/", CONTENT_LENGTH=deger)

    assert yanit.code == 400
    assert "Geçersiz istek" in yanit.text


def test_bos_icerik_uzunlugu_gecerlidir(uygulama: KatalogUygulamasi) -> None:
    assert _istek(uygulama, "/saglik", CONTENT_LENGTH="").code == 200


def test_govde_siniri_waitress_ayariyla_ayni() -> None:
    """Uygulama sınırı ile sunucu sınırı aynı değerdir (§5.2: 1 KB)."""
    assert MAX_BODY_BYTES == 1024


# ------------------------------------------------------------------ adres çözümü


@pytest.mark.parametrize(
    "adres",
    [
        "/ara?q=%ZZ",  # bozuk yüzde kodlaması
        "/ara?q=%FF%FE",  # UTF-8 değil
        "/ara?q=a%0Ab",  # denetim karakteri
        "/ara?q=a%00b",
    ],
)
def test_bozuk_sorgu_dizesi_400_doner(uygulama: KatalogUygulamasi, adres: str) -> None:
    yanit = _istek(uygulama, adres)

    assert yanit.code == 400
    assert "Geçersiz istek" in yanit.text


def test_utf8_olmayan_yol_400_doner(uygulama: KatalogUygulamasi) -> None:
    ortam = ortam_kur("/")
    ortam["PATH_INFO"] = "/eser/\xff"  # tek bayt 0xFF: UTF-8 değil
    assert cagir(uygulama, ortam).code == 400


def test_cok_uzun_sorgu_dizesi_414_doner(uygulama: KatalogUygulamasi) -> None:
    yanit = _istek(uygulama, "/ara?q=" + "a" * 3000)

    assert yanit.code == 414
    assert "Adres çok uzun" in yanit.text


# ------------------------------------------------------------- başlıklar (§5.5)


def _tum_yanit_turleri(uygulama: KatalogUygulamasi) -> Iterator[Yanit]:
    yield _istek(uygulama, "/")
    yield _istek(uygulama, "/hakkinda")
    yield _istek(uygulama, "/saglik")
    yield _istek(uygulama, "/", "HEAD")
    yield _istek(uygulama, "/yok")
    yield _istek(uygulama, "/ara")  # verisiz: 503
    yield _istek(uygulama, "/", "POST")
    yield _istek(uygulama, "/", CONTENT_LENGTH="5000")
    yield _istek(uygulama, "/", CONTENT_LENGTH="abc")
    yield _istek(uygulama, "/ara?q=" + "a" * 3000)


def test_guvenlik_basliklari_her_yanitta_bulunur(uygulama: KatalogUygulamasi) -> None:
    for yanit in [*_tum_yanit_turleri(uygulama), _istek(uygulama, "/katalog.css")]:
        assert yanit.header("Content-Security-Policy") == CSP, yanit.status
        assert yanit.header("X-Content-Type-Options") == "nosniff", yanit.status
        assert yanit.header("Referrer-Policy") == "no-referrer", yanit.status
        assert yanit.header("Set-Cookie") is None, yanit.status
        assert yanit.header("Server") is None, yanit.status


def test_csp_tasarimdaki_metinle_birebir() -> None:
    assert CSP == (
        "default-src 'none'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )


def test_html_ve_hata_sayfalari_onbelleklenmez(uygulama: KatalogUygulamasi) -> None:
    for yanit in _tum_yanit_turleri(uygulama):
        assert yanit.header("Cache-Control") == "no-store", yanit.status


def test_html_sayfalarinda_betik_ve_satir_ici_stil_yok(uygulama: KatalogUygulamasi) -> None:
    """CSP `default-src 'none'`: satır içi betik/stil zaten çalışmaz; hiç yazılmaz."""
    for yanit in _tum_yanit_turleri(uygulama):
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


@pytest.mark.parametrize(
    ("yol", "yontem"), [("/", "GET"), ("/yok", "GET"), ("/", "POST"), ("/ara?q=x", "GET")]
)
def test_cerez_basligi_okunmaz_ve_cerez_yazilmaz(
    uygulama: KatalogUygulamasi, yol: str, yontem: str
) -> None:
    ortam = _KayitliOrtam(ortam_kur(yol, yontem=yontem, HTTP_COOKIE="kd_oturum=gizli"))

    yanit = cagir(uygulama, ortam)

    assert "HTTP_COOKIE" not in ortam.okunan
    assert "HTTP_X_FORWARDED_FOR" not in ortam.okunan
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
                if dugum.value.strip().lower() in {
                    "http_cookie",
                    "set-cookie",
                    "cookie",
                    "http_x_forwarded_for",
                    "x-forwarded-for",
                }:
                    bulunan.append(f"{dosya.name}:{dugum.lineno}")

    assert bulunan == []


# ----------------------------------------------------------- bakım kapısı (§5.3)


def _dokunulmamasi_gereken_kurulum() -> KatalogKurulumu:
    def yol() -> Path:
        raise AssertionError("bakımdayken katalog veritabanına dokunmamalı")

    return KatalogKurulumu(db_yolu=yol, arama_parcalari=str.split, siralama_anahtari=str)


@pytest.mark.parametrize("yol", ["/", "/ara?q=x", "/eser/1", "/saglik", "/katalog.css", "/yok"])
def test_bakimdayken_her_yol_veritabanina_dokunmadan_503_doner(yol: str) -> None:
    kapi = BakimKapisi()
    sayaclar = GunlukSayaclar()
    uygulama = create_app(
        _dokunulmamasi_gereken_kurulum(),
        bakim_kapisi=kapi,
        hiz_siniri=genis_hiz_siniri(),
        sayaclar=sayaclar,
    )
    assert kapi.bakima_al(bekleme_sn=0.1)

    yanit = _istek(uygulama, yol)

    assert yanit.code == 503
    assert "bakımda" in yanit.text
    assert yanit.header("Content-Security-Policy") == CSP
    assert sayaclar.gun()["bakim"] == 1
    assert kapi.ucusta == 0


def test_bakim_ucustaki_istegin_bitmesini_bekler() -> None:
    """Geri yükleme adım 2: uçuştaki istek sayacı sıfıra inene dek beklenir."""
    kapi = BakimKapisi()
    icerde = threading.Event()
    birak = threading.Event()

    def yavas_arama(sorgu: str) -> list[str]:
        icerde.set()
        assert birak.wait(5)
        return [sorgu]

    kurulum = KatalogKurulumu(
        db_yolu=Path("/yok/boyle/bir/dosya.sqlite3"),
        arama_parcalari=yavas_arama,
        siralama_anahtari=str,
    )
    uygulama = create_app(kurulum, bakim_kapisi=kapi, hiz_siniri=genis_hiz_siniri())
    sonuc: list[int] = []
    is_parcacigi = threading.Thread(
        target=lambda: sonuc.append(_istek(uygulama, "/ara?q=x").code), daemon=True
    )
    is_parcacigi.start()
    assert icerde.wait(5)

    assert kapi.ucusta == 1
    assert kapi.bakima_al(bekleme_sn=0.05) is False  # istek hâlâ uçuşta
    assert _istek(uygulama, "/saglik").code == 503  # yeni istek girmez
    birak.set()
    is_parcacigi.join(5)
    assert kapi.bakima_al(bekleme_sn=5) is True
    assert sonuc == [503]  # veritabanı yok: uçuştaki istek kendi hatasıyla bitti


# -------------------------------------------------------- beklenmeyen hata


def test_beklenmeyen_hata_sabit_500_doner_ve_yigin_sizdirmaz() -> None:
    def patlayan(sorgu: str) -> list[str]:
        raise RuntimeError("iç ayrıntı /gizli/yol")

    sayaclar = GunlukSayaclar()
    uygulama = create_app(
        KatalogKurulumu(db_yolu=Path("/x"), arama_parcalari=patlayan, siralama_anahtari=str),
        bakim_kapisi=BakimKapisi(),
        hiz_siniri=genis_hiz_siniri(),
        sayaclar=sayaclar,
    )

    yanit = _istek(uygulama, "/ara?q=deneme")

    assert yanit.code == 500
    assert "Bir sorun oluştu" in yanit.text
    assert "gizli" not in yanit.text and "Traceback" not in yanit.text
    assert sayaclar.gun()["sunucu_hatasi"] == 1
    assert sayaclar.son_hata is not None
    assert "gizli" not in sayaclar.son_hata.ileti


# ------------------------------------------------------ modül düzeyi örnek


def test_surec_ici_uygulama_tek_ornektir_ve_waitress_gorevini_tembel_verir() -> None:
    assert isinstance(katalog_app.application, KatalogUygulamasi)
    gorev = katalog_app.WAITRESS_HATA_GOREVI
    assert isinstance(gorev, type)
    assert gorev is katalog_app.WAITRESS_HATA_GOREVI  # bir kez kurulur
    with pytest.raises(AttributeError):
        _ = katalog_app.YOK_BOYLE_BIR_AD


def test_surec_ici_uygulama_django_acilisinda_veriye_baglanir() -> None:
    """`KutuphaneConfig.ready` süreç içi örneği kurar; yol istek anında okunur."""
    from django.conf import settings

    kurulum = katalog_app.application.kurulum
    assert kurulum is not None
    assert kurulum.veritabani() == Path(str(settings.DATABASES["default"]["NAME"]))
