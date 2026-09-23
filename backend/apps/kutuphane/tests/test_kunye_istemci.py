"""Künye ağ istemcisinin sert kuralları (§8.5-2/3/4/7, §5.10-19c).

**Gerçek ağa ÇIKILMAZ:** bütün yanıtlar taklit edilir (sahte opener). Testler
giden isteğin **tamamını** dolaşır: adres, sorgu dizesi, gövde ve BÜTÜN
başlıklar. Kimlik, anahtar, çerez, okul adı, demirbaş no, kart no ve barkod
hiçbir yerde geçemez.
"""

from __future__ import annotations

import ast
import email.message
import ssl
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.kutuphane.kunye import bakanlik, istemci, openlibrary

ISBN = "9789753638029"

#: Programın içinde bulunan ve dışarı ASLA çıkmaması gereken örnek değerler.
#: Hepsi uydurmadır (CLAUDE.md §2-12).
SIZMAMASI_GEREKENLER: tuple[str, ...] = (
    "Örnek Anadolu Lisesi",
    "2026-000123",  # nüsha barkodu
    "KART-0007",  # üye kart no
    "X-KD-Token",
    "kd_oturum",
    "Cookie",
    "Authorization",
    "aalidemirci",
)


class SahteYanit:
    """`urlopen` yanıtının test karşılığı (bağlam yöneticisi + parçalı okuma)."""

    def __init__(self, govde: bytes, icerik_turu: str = "application/xml") -> None:
        self._govde = govde
        self._konum = 0
        self.headers = {"Content-Type": icerik_turu}

    def __enter__(self) -> SahteYanit:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, boyut: int = -1) -> bytes:
        if boyut is None or boyut < 0:
            boyut = len(self._govde) - self._konum
        parca = self._govde[self._konum : self._konum + boyut]
        self._konum += len(parca)
        return parca


class SahteSaat:
    """Testin elle ilerlettiği monotonik saat (`istemci._simdi` yerine geçer).

    Sabit bir değer listesi DEĞİL: istemci saati birden çok yerde okur (hız
    sınırı, toplam süre tavanı, gövde okuma döngüsü) ve liste tabanlı bir sahte
    saat, çağrı sayısı değişince ilgisiz testleri kırardı.
    """

    def __init__(self, baslangic: float = 100.0) -> None:
        self.simdi = baslangic

    def __call__(self) -> float:
        return self.simdi


class YavasYanit(SahteYanit):
    """Her okumada saati ilerleten yanıt: saniyede birkaç bayt damlatan uç."""

    def __init__(self, govde: bytes, saat: SahteSaat, adim: float) -> None:
        super().__init__(govde)
        self._saat = saat
        self._adim = adim

    def read(self, boyut: int = -1) -> bytes:
        self._saat.simdi += self._adim
        return super().read(min(boyut if boyut and boyut > 0 else 8, 8))


class SahteAcici:
    """İstekleri kaydeden, sırayla yanıt veren sahte opener."""

    def __init__(self, *yanitlar: Any) -> None:
        self.yanitlar = list(yanitlar)
        self.istekler: list[urllib.request.Request] = []
        self.zaman_asimlari: list[float] = []

    def open(self, istek: Any, /, timeout: float = 0.0) -> Any:
        self.istekler.append(istek)
        self.zaman_asimlari.append(timeout)
        if not self.yanitlar:
            raise AssertionError("Beklenenden çok istek atıldı.")
        sonraki = self.yanitlar.pop(0)
        if isinstance(sonraki, Exception):
            raise sonraki
        return sonraki


def isleyiciler() -> list[Any]:
    """Opener zincirindeki işleyiciler (`OpenerDirector` stub'ı bu alanı bildirmiyor)."""
    opener: Any = istemci._opener()
    return list(opener.handlers)


def yonlendirme(hedef: str, kod: int = 302) -> HTTPError:
    basliklar = email.message.Message()
    basliklar["Location"] = hedef
    return HTTPError("http://ornek/", kod, "Found", basliklar, None)


@pytest.fixture(autouse=True)
def hizli_saat(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[float]]:
    """Hız sınırlayıcı gerçek `sleep` çağırmasın; uyku süreleri kaydedilir."""
    uykular: list[float] = []
    monkeypatch.setattr(istemci, "_uyu", uykular.append)
    istemci._sifirla_testler_icin()
    yield uykular
    istemci._sifirla_testler_icin()


# ===================================================== Giden istek (§5.10-19c)
class TestGidenIstek:
    def test_bakanlik_adresinde_yalniz_isbn_degiskendir(self) -> None:
        parca = urlsplit(bakanlik.sorgu_adresi(ISBN))
        parametreler = parse_qs(parca.query)

        assert parca.hostname == istemci.BAKANLIK_HOST
        assert parametreler == {
            "version": ["1.1"],
            "operation": ["searchRetrieve"],
            "query": [f"bath.isbn={ISBN}"],
            "maximumRecords": ["5"],
            "recordSchema": ["marcxml"],
        }

    def test_openlibrary_adresinde_yalniz_isbn_degiskendir(self) -> None:
        parca = urlsplit(openlibrary.sorgu_adresi(ISBN))
        parametreler = parse_qs(parca.query)

        assert parca.scheme == "https"
        assert parca.hostname == istemci.OPENLIBRARY_HOST
        assert parametreler["q"] == [f"isbn:{ISBN}"]
        assert parametreler["limit"] == ["1"]

    def test_basliklar_sabittir_ve_govde_bostur(self) -> None:
        istek = istemci.istek_kur(bakanlik.sorgu_adresi(ISBN), kabul="application/xml")

        assert istek.headers == {
            "Accept": "application/xml",
            "User-agent": istemci.kullanici_ajani(),
        }
        assert istek.unredirected_hdrs == {}
        assert istek.data is None
        assert istek.get_method() == "GET"

    def test_kullanici_ajani_yalniz_program_adi_ve_surumudur(self) -> None:
        ajan = istemci.kullanici_ajani()

        assert ajan.startswith("KutuphaneDefteri/")
        assert " " not in ajan  # iletişim adresi, okul adı, işletim sistemi yok

    def test_istegin_hicbir_yerinde_program_verisi_gecmez(self) -> None:
        """§5.10-19c: adres, sorgu dizesi, gövde ve başlıklar dolaşılır."""
        acici = SahteAcici(SahteYanit(b"<records/>"))
        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)
        (istek,) = acici.istekler

        metin = " ".join(
            [
                istek.full_url,
                repr(istek.data),
                repr(istek.headers),
                repr(istek.unredirected_hdrs),
            ]
        )
        for yasak in SIZMAMASI_GEREKENLER:
            assert yasak.lower() not in metin.lower(), yasak
        assert ISBN in istek.full_url

    def test_zaman_asimi_kisadir(self) -> None:
        acici = SahteAcici(SahteYanit(b"<records/>"))
        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

        assert acici.zaman_asimlari == [istemci.ZAMAN_ASIMI_SANIYE]
        assert istemci.ZAMAN_ASIMI_SANIYE <= 10


# ===================================================== Yanıt (§8.5-4)
class TestYanit:
    def test_boyut_tavanini_asan_yanit_dusurulur(self) -> None:
        acici = SahteAcici(SahteYanit(b"x" * (istemci.MAX_YANIT_BAYT + 1)))

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

    def test_tavana_kadar_olan_yanit_okunur(self) -> None:
        govde = b"y" * (istemci.MAX_YANIT_BAYT - 1)
        acici = SahteAcici(SahteYanit(govde))

        assert (
            istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici).govde
            == govde
        )

    def test_ag_hatasi_kunye_hatasina_cevrilir(self) -> None:
        acici = SahteAcici(URLError("bağlantı yok"))

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

    def test_http_hatasi_kunye_hatasina_cevrilir(self) -> None:
        acici = SahteAcici(HTTPError("http://ornek/", 500, "Hata", None, None))  # type: ignore[arg-type]

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

    def test_damlatan_uc_toplam_sure_tavaninda_kesilir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Soket zaman aşımı işlem başınadır; toplam tavan olmasa istek sürerdi (§8.5-9)."""
        saat = SahteSaat(100.0)
        monkeypatch.setattr(istemci, "_simdi", saat)
        # Her okuma 8 bayt verir ve saati 5 sn ilerletir: soket tavanı (6 sn)
        # hiç aşılmaz ama toplam tavan (15 sn) dolar.
        acici = SahteAcici(YavasYanit(b"<a/>" * 1000, saat, adim=5.0))

        with pytest.raises(istemci.KunyeAgHatasi, match="çok yavaş"):
            istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

    def test_toplam_tavan_altinda_kalan_yanit_okunur(self, monkeypatch: pytest.MonkeyPatch) -> None:
        saat = SahteSaat(100.0)
        monkeypatch.setattr(istemci, "_simdi", saat)
        acici = SahteAcici(YavasYanit(b"<a/>", saat, adim=0.1))

        yanit = istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

        assert yanit.govde == b"<a/>"


# ===================================================== Yönlendirme (§8.5-4)
class TestYonlendirme:
    def test_ayni_host_icinde_bir_kez_izlenir(self) -> None:
        adres = f"https://{istemci.OPENLIBRARY_HOST}/isbn/{ISBN}.json"
        acici = SahteAcici(
            yonlendirme(f"https://{istemci.OPENLIBRARY_HOST}/books/OL1M.json"),
            SahteYanit(b"{}", "application/json"),
        )

        yanit = istemci.getir(adres, kabul="application/json", acici=acici)

        assert yanit.govde == b"{}"
        assert [istek.full_url for istek in acici.istekler] == [
            adres,
            f"https://{istemci.OPENLIBRARY_HOST}/books/OL1M.json",
        ]

    def test_baska_hosta_giden_yonlendirme_dusurulur(self) -> None:
        acici = SahteAcici(yonlendirme("https://ornek-saldirgan.test/kunye.json"))

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(
                f"https://{istemci.OPENLIBRARY_HOST}/isbn/{ISBN}.json",
                kabul="application/json",
                acici=acici,
            )
        assert len(acici.istekler) == 1

    def test_https_ten_http_ye_dusuren_yonlendirme_izlenmez(self) -> None:
        """Aynı host içinde olsa bile şema düşürmesi TLS korumasını kaldırırdı (§8.5-7)."""
        acici = SahteAcici(yonlendirme(f"http://{istemci.OPENLIBRARY_HOST}/books/OL1M.json"))

        with pytest.raises(istemci.KunyeAgHatasi, match="şema"):
            istemci.getir(
                f"https://{istemci.OPENLIBRARY_HOST}/isbn/{ISBN}.json",
                kabul="application/json",
                acici=acici,
            )
        assert len(acici.istekler) == 1

    def test_ikinci_yonlendirme_izlenmez(self) -> None:
        acici = SahteAcici(
            yonlendirme(f"https://{istemci.OPENLIBRARY_HOST}/bir"),
            yonlendirme(f"https://{istemci.OPENLIBRARY_HOST}/iki"),
        )

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(
                f"https://{istemci.OPENLIBRARY_HOST}/isbn/{ISBN}.json",
                kabul="application/json",
                acici=acici,
            )
        assert len(acici.istekler) == 2

    def test_opener_kendiliginden_yonlendirme_izlemez(self) -> None:
        zincir = isleyiciler()

        assert any(isinstance(h, istemci._YonlendirmeYok) for h in zincir)
        assert all(
            not isinstance(h, urllib.request.HTTPRedirectHandler)
            or isinstance(h, istemci._YonlendirmeYok)
            for h in zincir
        )


# ===================================================== Adres beyaz listesi
class TestAdres:
    @pytest.mark.parametrize(
        "adres",
        [
            "https://ornek-saldirgan.test/kunye.json",
            "file:///etc/passwd",
            "ftp://koha.ekutuphane.gov.tr/x",
            "https://kullanici:parola@openlibrary.org/search.json",
        ],
    )
    def test_izinsiz_adrese_istek_atilmaz(self, adres: str) -> None:
        acici = SahteAcici()

        with pytest.raises(istemci.KunyeAgHatasi):
            istemci.getir(adres, kabul="application/json", acici=acici)
        assert acici.istekler == []


# ===================================================== Hız sınırı (§8.5-2)
class TestHizSiniri:
    def test_saniyede_en_cok_bir_istek(
        self, monkeypatch: pytest.MonkeyPatch, hizli_saat: list[float]
    ) -> None:
        saat = SahteSaat(100.0)
        monkeypatch.setattr(istemci, "_simdi", saat)
        acici = SahteAcici(SahteYanit(b"<a/>"), SahteYanit(b"<a/>"))

        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)
        saat.simdi = 100.2  # ikinci istek 0,2 sn sonra
        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

        assert hizli_saat and pytest.approx(hizli_saat[0], abs=0.01) == 0.8

    def test_arali_gecmisse_beklenmez(
        self, monkeypatch: pytest.MonkeyPatch, hizli_saat: list[float]
    ) -> None:
        saat = SahteSaat(100.0)
        monkeypatch.setattr(istemci, "_simdi", saat)
        acici = SahteAcici(SahteYanit(b"<a/>"), SahteYanit(b"<a/>"))

        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)
        saat.simdi = 105.0  # aralık çoktan geçti
        istemci.getir(bakanlik.sorgu_adresi(ISBN), kabul="application/xml", acici=acici)

        assert hizli_saat == []


# ===================================================== TLS ve proxy (§8.5-7)
class TestTlsVeProxy:
    def test_sistem_sertifika_deposu_dogrulamasi_aciktir(self) -> None:
        baglam = istemci.tls_baglami()

        assert baglam.verify_mode == ssl.CERT_REQUIRED
        assert baglam.check_hostname is True

    def test_opener_sistem_proxysini_kullanir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ortamda proxy tanımlıysa opener onu görür (MEBNET'te SSL denetimli proxy var).

        `ProxyHandler` proxy tanımı YOKKEN hiçbir `*_open` yöntemi üretmez ve
        opener zincirine hiç girmez; bu yüzden denetim proxy tanımlı ortamda
        yapılır — aksi hâlde test ortamın proxy'siz olmasına takılırdı.
        """
        monkeypatch.setenv("http_proxy", "http://proxy.ornek.test:8080")

        zincir = isleyiciler()

        proxy: list[Any] = [h for h in zincir if isinstance(h, urllib.request.ProxyHandler)]
        tanimli: dict[str, str] = proxy[0].proxies if proxy else {}
        assert tanimli.get("http") == "http://proxy.ornek.test:8080"

    def test_opener_cerez_islemez(self) -> None:
        zincir = isleyiciler()

        assert not any(isinstance(h, urllib.request.HTTPCookieProcessor) for h in zincir)

    def test_kunye_paketi_certifi_ice_aktarmaz(self) -> None:
        """MEBNET'te `certifi` ile çalışan istemci sessizce patlardı (§8.5-7)."""
        paket = Path(__file__).resolve().parents[1] / "kunye"
        for dosya in paket.rglob("*.py"):
            agac = ast.parse(dosya.read_text(encoding="utf-8"))
            for dugum in ast.walk(agac):
                if isinstance(dugum, ast.Import):
                    adlar = [alias.name for alias in dugum.names]
                elif isinstance(dugum, ast.ImportFrom):
                    adlar = [dugum.module or ""]
                else:
                    continue
                assert all(not ad.startswith("certifi") for ad in adlar), dosya.name
