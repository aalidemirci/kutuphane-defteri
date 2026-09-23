"""Künye sorgusunun ağ istemcisi — §8.5'in 2., 3., 4. ve 7. kuralları burada.

**Yeni bağımlılık YOKTUR** (CLAUDE.md §2-10): `urllib.request` kullanılır.
Seçim tesadüfi değil, §8.5-7'nin gereğidir: `requests`/`httpx` gövdesi
`certifi` ile gelir ve **sistem sertifika deposunu görmez**; MEBNET'te SSL
denetimli proxy vardır ve istemcilere MEB kök sertifikası kurulur (Yönerge
11/19). `certifi` ile çalışan bir istemci tam da hedeflenen ağda sessizce
patlardı. `ssl.create_default_context()` Windows'ta sistem deposunu, Pardus'ta
OpenSSL'in sistem yollarını okur; `ProxyHandler()` de sistem/ortam proxy'sini.

Kurallar (hepsi testlidir):

* **Giden istekte yalnız ISBN vardır.** Başlıklar `BASLIKLAR` ile SABİTTİR:
  `Accept` ve `User-Agent`. Çerez işleyicisi (`HTTPCookieProcessor`) opener'a
  KONMAZ, kimlik ve anahtar başlığı yoktur, gövde her zaman boştur (GET).
  `User-Agent` yalnız program adını ve sürümünü taşır (Open Library'nin şartı).
* **Saniyede en çok bir istek** (§8.5-2). Sınırlayıcı süreç genelindedir ve
  yönlendirme isteğini de sayar.
* **Kısa zaman aşımı** (§8.5-4): uç yavaşsa kullanıcı beklemez, fail-open
  devreye girer. İKİ tavan vardır: soket zaman aşımı İŞLEM başınadır, toplam
  süre tavanı İSTEK başına — saniyede birkaç bayt damlatan bir uç her `recv`i
  soket tavanının altında tutarak isteği dakikalarca canlı tutabilirdi.
* **Boyut tavanı:** tavanı aşan yanıt okunmaz, düşürülür.
* **Yönlendirme kendiliğinden izlenmez:** en çok bir kez, aynı host ve aynı
  şema içinde. Başka hosta ya da https'ten http'ye giden yönlendirme düşürülür
  (Open Library'nin `/isbn/` ucundaki 302 bu yüzden tanımlıdır).
* **Host beyaz listesi:** istek yalnız §8.5'te sayılan iki adrese çıkar.
"""

from __future__ import annotations

import ssl
import threading
import time
import urllib.request
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit

from apps.okul.services.updates import get_app_version

#: §8.5'te sayılan iki adres. Beyaz liste hem adaptörü hem yönlendirmeyi bağlar.
BAKANLIK_HOST = "koha.ekutuphane.gov.tr"
OPENLIBRARY_HOST = "openlibrary.org"
IZINLI_HOSTLAR: frozenset[str] = frozenset({BAKANLIK_HOST, OPENLIBRARY_HOST})

#: Kısa zaman aşımı (saniye): bağlantı + okuma. Uç yavaşsa kullanıcı beklemez.
#: Bu tavan SOKET İŞLEMİ BAŞINADIR (her `recv` onu sıfırdan başlatır).
ZAMAN_ASIMI_SANIYE = 6.0
#: İsteğin tamamı için toplam süre tavanı (saniye) — yönlendirme dahil. Soket
#: tavanı tek başına yetmez: saniyede birkaç bayt gönderen bir uç, her `recv`
#: 6 sn'nin altında kaldığı sürece 512 KB'lık tavana ulaşana kadar isteği
#: canlı tutar; waitress iş parçacığı bloke kalır ve §8.5-9'un vaat ettiği
#: "İnternetten getirilemedi, elle girebilirsiniz" iletisi hiç görünmezdi.
TOPLAM_ZAMAN_ASIMI_SANIYE = 15.0
#: Yanıt boyutu tavanı. Bakanlık ucu 5 MARCXML kaydı için ~50 KB döndürür.
MAX_YANIT_BAYT = 512 * 1024
#: İki dış istek arasındaki en az süre (§8.5-2: saniyede en çok bir istek).
ISTEK_ARALIGI_SANIYE = 1.0
#: İzlenebilecek en çok yönlendirme (§8.5-4).
MAX_YONLENDIRME = 1

_YONLENDIRME_KODLARI = frozenset({301, 302, 303, 307, 308})


def kullanici_ajani() -> str:
    """`User-Agent` — yalnız program adı ve sürümü (Open Library'nin şartı).

    Okul adı, kurum kodu, kullanıcı adı ve iletişim adresi GEÇMEZ (§8.5-3).
    """
    return f"KutuphaneDefteri/{get_app_version()}"


class KunyeAgHatasi(RuntimeError):
    """Ağ katmanının fail-open hatası: servis yakalar, kullanıcıya yansımaz."""


@dataclass(frozen=True, slots=True)
class Yanit:
    """Dış ucun yanıtı — gövde ham bayttır, ayrıştırma adaptörün işidir."""

    govde: bytes
    icerik_turu: str


class Acici(Protocol):
    """`urllib.request.OpenerDirector`un test edilebilir en dar yüzü.

    İlk parametre KONUMSALDIR (`/`): sahte opener'ın parametre adı `urllib`in
    `fullurl`ü ile aynı olmak zorunda kalmasın.
    """

    def open(self, istek: Any, /, timeout: float = ...) -> Any: ...


class _YonlendirmeYok(urllib.request.HTTPRedirectHandler):
    """Yönlendirmeyi kendiliğinden İZLEMEZ; kararı `getir` verir (§8.5-4)."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_baglam_kilidi = threading.Lock()
_tls_baglami: ssl.SSLContext | None = None

_hiz_kilidi = threading.Lock()
_son_istek: float = 0.0

# Testlerin yerine koyabildiği saat kaynakları (gerçek `sleep` beklemesin).
_simdi = time.monotonic
_uyu = time.sleep


def tls_baglami() -> ssl.SSLContext:
    """Sistem sertifika deposunu kullanan TLS bağlamı (§8.5-7); bir kez kurulur."""
    global _tls_baglami
    with _baglam_kilidi:
        if _tls_baglami is None:
            # `create_default_context` → check_hostname=True, CERT_REQUIRED ve
            # `load_default_certs()`: Windows'ta sistem deposu, Linux'ta OpenSSL
            # sistem yolları. `certifi` KULLANILMAZ (MEB kök sertifikası).
            _tls_baglami = ssl.create_default_context()
        return _tls_baglami


def _opener() -> urllib.request.OpenerDirector:
    """Proxy'li, yönlendirmesiz, ÇEREZSİZ opener.

    `build_opener` varsayılan zincire `HTTPCookieProcessor` KOYMAZ; buraya da
    konmaz (§8.5-3: çerez yok). `ProxyHandler()` argümansız çağrılır: sistem ve
    ortam proxy ayarları okunur.
    """
    return urllib.request.build_opener(
        urllib.request.ProxyHandler(),
        urllib.request.HTTPSHandler(context=tls_baglami()),
        _YonlendirmeYok,
    )


def _hiz_sinirla() -> None:
    """Saniyede en çok bir istek (§8.5-2). Süreç genelinde tek sayaç."""
    global _son_istek
    with _hiz_kilidi:
        simdi = _simdi()
        kalan = ISTEK_ARALIGI_SANIYE - (simdi - _son_istek)
        if _son_istek and kalan > 0:
            _uyu(kalan)
            simdi = _simdi()
        _son_istek = simdi


def _adres_denetle(
    url: str, *, beklenen_host: str | None = None, beklenen_sema: str | None = None
) -> tuple[str, str]:
    """Adres beyaz listede mi, şeması taşınıyor mu? Değilse `KunyeAgHatasi`.

    Yönlendirme denetimi hem HOSTU hem ŞEMAYI karşılaştırır: yalnız host
    karşılaştırılsaydı `https://openlibrary.org/…` ucundan dönen bir
    `Location: http://openlibrary.org/…` izlenir ve gövde doğrulanmamış bir
    kanaldan gelirdi — TLS koruması (§8.5-7) o istek için düşerdi.
    """
    parca = urlsplit(url)
    if parca.scheme not in {"http", "https"}:
        raise KunyeAgHatasi(f"Desteklenmeyen adres şeması: {parca.scheme!r}")
    host = (parca.hostname or "").lower()
    if host not in IZINLI_HOSTLAR:
        raise KunyeAgHatasi(f"İzin verilmeyen adres: {host!r}")
    if parca.username or parca.password:
        raise KunyeAgHatasi("Adreste kimlik bilgisi taşınamaz.")
    if beklenen_host is not None and host != beklenen_host:
        raise KunyeAgHatasi("Yönlendirme başka bir hosta gidiyor; istek düşürüldü.")
    if beklenen_sema is not None and parca.scheme != beklenen_sema:
        raise KunyeAgHatasi("Yönlendirme adresin şemasını değiştiriyor; istek düşürüldü.")
    return parca.scheme, host


def istek_kur(url: str, *, kabul: str) -> urllib.request.Request:
    """Giden isteği kurar. BAŞLIKLAR SABİTTİR — koruma testi bunu dolaşır."""
    return urllib.request.Request(  # noqa: S310 — şema ve host `_adres_denetle`de
        url,
        data=None,  # GET: gövde yok
        headers={"Accept": kabul, "User-Agent": kullanici_ajani()},
        method="GET",
    )


def _govde_oku(yanit: HTTPResponse, son_tarih: float) -> bytes:
    """Tavanı aşan ya da ÇOK YAVAŞ akan yanıtı okumaz, düşürür (§8.5-4).

    Döngünün her turunda toplam süre denetlenir: bayt sayacı tek başına
    damlatan bir ucu durdurmaz, çünkü tavana ulaşmak dakikalar sürebilir.
    """
    parcalar: list[bytes] = []
    toplam = 0
    while True:
        if _simdi() > son_tarih:
            raise KunyeAgHatasi("Yanıt çok yavaş; istek düşürüldü.")
        parca = yanit.read(min(64 * 1024, MAX_YANIT_BAYT + 1 - toplam))
        if not parca:
            break
        toplam += len(parca)
        if toplam > MAX_YANIT_BAYT:
            raise KunyeAgHatasi("Yanıt boyut tavanını aştı; düşürüldü.")
        parcalar.append(parca)
    return b"".join(parcalar)


def getir(url: str, *, kabul: str, acici: Acici | None = None) -> Yanit:
    """Tek bir GET isteği atar; yönlendirmeyi en çok bir kez, aynı host içinde izler.

    Her hata `KunyeAgHatasi`dır: çağıran (servis) fail-open davranır.
    """
    sema, host = _adres_denetle(url)
    gonderen: Acici | urllib.request.OpenerDirector = acici if acici is not None else _opener()
    adres = url
    # Toplam süre tavanı YÖNLENDİRMEYİ DE kapsar: son tarih bir kez hesaplanır.
    son_tarih = _simdi() + TOPLAM_ZAMAN_ASIMI_SANIYE
    for kalan in range(MAX_YONLENDIRME, -1, -1):
        if _simdi() > son_tarih:
            raise KunyeAgHatasi("Yanıt çok yavaş; istek düşürüldü.")
        _hiz_sinirla()
        istek = istek_kur(adres, kabul=kabul)
        try:
            with gonderen.open(istek, timeout=ZAMAN_ASIMI_SANIYE) as yanit:
                return Yanit(
                    govde=_govde_oku(yanit, son_tarih),
                    icerik_turu=str(yanit.headers.get("Content-Type", "")),
                )
        except HTTPError as exc:
            if exc.code not in _YONLENDIRME_KODLARI:
                raise KunyeAgHatasi(f"Dış uç HTTP {exc.code} yanıtı verdi.") from exc
            if kalan <= 0:
                raise KunyeAgHatasi("Yönlendirme sınırı aşıldı; istek düşürüldü.") from exc
            hedef = str(exc.headers.get("Location", "")).strip() if exc.headers else ""
            if not hedef:
                raise KunyeAgHatasi("Yönlendirme adresi boş; istek düşürüldü.") from exc
            adres = urljoin(adres, hedef)
            _adres_denetle(adres, beklenen_host=host, beklenen_sema=sema)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise KunyeAgHatasi("Dış uca ulaşılamadı.") from exc
    raise KunyeAgHatasi("Yönlendirme sınırı aşıldı; istek düşürüldü.")


def _sifirla_testler_icin() -> None:
    """Hız sınırlayıcının sayacını sıfırlar (yalnız testler çağırır)."""
    global _son_istek
    with _hiz_kilidi:
        _son_istek = 0.0
