"""Ağ Kataloğu sayfaları — doğrulama, sorgu ve şablon (tasarım §5.3, §5.4).

Her sayfa işleyicisi `(istek, ortam, parametre) -> Yanit` imzasındadır. Kurallar:

- **Doğrulama önce gelir.** `tur`, `konu`, harf ve `id` sabit kümeden ya da
  kanonik tam sayı olmak zorundadır; değilse veritabanına gidilmeden 404
  (`Bulunamadi`). `sayfa` tam sayı olmalıdır ve `1..min(ceil(toplam/20), 500)`
  aralığına kırpılır. Arama metni en çok 100 karakterdir, fazlası kırpılır.
- **Arama katlaması tek kaynaktandır.** Sorgu, eserin `search_key` alanını
  üreten AYNI katlamadan geçer. Katlama işlevi (`apps.kutuphane.keys`) Django
  tarafındadır ve katalog onu içe aktaramaz (§4.1); işlev kuruluşta
  `KatalogKurulumu` ile verilir. Harf dizini de aynı yoldan sıralama anahtarı
  işlevini alır.
- **Şablon motoru tembel yüklenir.** `django.template` paketinin kendisi
  yüklenirken Django'nun sistem denetimi modülünü, o da `django.db` paket
  başlangıcını içe aktarır (Django'nun iç zinciri; bağlantı ya da ORM
  kullanılmaz). Katalog modüllerinin içe aktarılması Django'nun veri katmanını
  yüklememelidir (§5.10-3 çalışma anı denetimi); motor bu yüzden ilk sayfa
  üretiminde kurulur. Çalışma anında da ORM, veritabanı arka ucu ve URL
  katmanının YÜKLENMEDİĞİ ayrı bir alt süreç testiyle sabitlenir.
- **Kişisel veri YOKTUR.** Şablonlara yalnız görünümlerin sütunları gider;
  sayılar sayfaya dizge olarak verilir (yerelleştirme ayarı araya girmesin).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from katalog import sabitler, veri
from katalog.hatalar import CSS, HTML, NO_STORE, Yanit
from katalog.istek import Istek

if TYPE_CHECKING:
    import sqlite3

    from django.template import Engine

PAKET_DIZINI: Final = Path(__file__).resolve().parent
SABLON_DIZINI: Final = PAKET_DIZINI / "sablonlar"
#: Gömülü stil: bellekte tutulur, `/katalog.css` yolundan verilir (§5.4).
CSS_BAYTLARI: Final = (PAKET_DIZINI / "katalog.css").read_bytes()
CSS_YOLU: Final = "/katalog.css"
#: Stilin tarayıcıda önbelleklenme süresi (HTML sayfaları hiç önbelleklenmez).
CSS_ONBELLEK: Final = "public, max-age=3600"


class Bulunamadi(Exception):
    """Geçersiz ya da bulunamayan kaynak → sabit 404 sayfası."""


@dataclass(frozen=True)
class KatalogKurulumu:
    """Katalog uygulamasının dışarıdan aldığı her şey (katalog `apps.*` içe aktarmaz).

    - `db_yolu`: programın SQLite dosyası (salt okur açılır) ya da onu her
      istekte döndüren işlev (Django ayarı sonradan değişebilir — ör. test
      veritabanı).
    - `arama_parcalari`: kullanıcı sorgusunu `search_key` ile aynı katlamadan
      geçirip parçalara böler (`apps.kutuphane.keys.search_terms`).
    - `siralama_anahtari`: Türk alfabesi sıralama anahtarı
      (`apps.kutuphane.keys.tr_collation_key`); harf dizini ilk karakterini kullanır.
    """

    db_yolu: Path | Callable[[], Path]
    arama_parcalari: Callable[[str], list[str]]
    siralama_anahtari: Callable[[str], str]
    sorgu_suresi: float = veri.VARSAYILAN_SORGU_SURESI

    def veritabani(self) -> Path:
        return self.db_yolu if isinstance(self.db_yolu, Path) else self.db_yolu()


@dataclass(frozen=True)
class SayfaOrtami:
    """İşleyicilere verilen ortam: kurulum (yoksa katalog verisiz çalışır).

    `veri_hatasi`: verisiz de açılan sayfalar (`/`, `/hakkinda`) veriye
    ulaşamadığında hatayı yutmadan önce bunu çağırır (Ağ Doktoru'nun son hatası).
    """

    kurulum: KatalogKurulumu | None
    veri_hatasi: Callable[[], None] | None = None

    def veri_hatasini_bildir(self) -> None:
        if self.kurulum is not None and self.veri_hatasi is not None:
            self.veri_hatasi()

    @contextmanager
    def baglanti(self) -> Iterator[sqlite3.Connection]:
        if self.kurulum is None:
            raise veri.VeriHatasi("katalog veritabanı yapılandırılmadı")
        with veri.baglan(self.kurulum.veritabani(), sorgu_suresi=self.kurulum.sorgu_suresi) as conn:
            yield conn


Isleyici = Callable[[Istek, SayfaOrtami, str | None], Yanit]

# ---------------------------------------------------------------------------
# Şablon motoru (tembel)
# ---------------------------------------------------------------------------
_motor_kilidi = threading.Lock()
_motor: list[Engine] = []


def sablon_motoru() -> Engine:
    """Otomatik kaçırmalı şablon motoru (§5.4); ilk çağrıda kurulur."""
    with _motor_kilidi:
        if not _motor:
            from django.template import Engine

            _motor.append(
                Engine(
                    dirs=[str(SABLON_DIZINI)],
                    autoescape=True,
                    debug=False,
                    string_if_invalid="",
                )
            )
        return _motor[0]


def isle(sablon: str, baglam: Mapping[str, Any]) -> bytes:
    from django.template import Context

    metin = sablon_motoru().get_template(sablon).render(Context(dict(baglam), autoescape=True))
    return metin.encode("utf-8")


def _html(sablon: str, baglam: Mapping[str, Any]) -> Yanit:
    return Yanit("200 OK", HTML, isle(sablon, baglam), NO_STORE)


# ---------------------------------------------------------------------------
# Doğrulama yardımcıları
# ---------------------------------------------------------------------------
_EN_UZUN_SAYI: Final = 12


def kanonik_tam_sayi(deger: str | None) -> int:
    """Yalnız ASCII rakamlı, baştaki sıfırsız pozitif tam sayı; değilse `Bulunamadi`."""
    if (
        deger is None
        or not deger
        or len(deger) > _EN_UZUN_SAYI
        or not deger.isascii()
        or not deger.isdigit()
        or str(int(deger)) != deger
        or int(deger) < 1
    ):
        raise Bulunamadi
    return int(deger)


def sayfa_numarasi(deger: str | None) -> int:
    """`sayfa` parametresi: yoksa 1; varsa ASCII rakam olmalı (kırpma sonra yapılır)."""
    if deger is None or deger == "":
        return 1
    if len(deger) > 6 or not deger.isascii() or not deger.isdigit():
        raise Bulunamadi
    return int(deger)


def tur_kodu(deger: str | None) -> str | None:
    if deger is None or deger == "":
        return None
    kod = sabitler.TURLER.get(deger)
    if kod is None:
        raise Bulunamadi
    return kod


def ana_sinif(deger: str | None) -> str | None:
    if deger is None or deger == "":
        return None
    if deger not in sabitler.ANA_SINIFLAR:
        raise Bulunamadi
    return deger


def harf(deger: str | None) -> str:
    if deger is None or (deger not in sabitler.HARFLER and deger != sabitler.DIGER):
        raise Bulunamadi
    return deger


# ---------------------------------------------------------------------------
# Görünüm biçimlendirme
# ---------------------------------------------------------------------------
def _metin(deger: object) -> str:
    return "" if deger is None else str(deger).strip()


def nusha_ozeti(e: Mapping[str, Any]) -> str:
    """ "3 nüsha · 2 rafta · 1 ödünçte" (§5.1); sayılar yalnız görünür nüshalardandır."""
    toplam = int(e["nusha_sayisi"] or 0)
    if toplam == 0:
        if e["tur"] in sabitler.DIJITAL_TURLER:
            return "Dijital kaynak — künye bilgisidir; erişim için kütüphaneye başvurun."
        return "Kütüphanede okunur."
    parcalar = [f"{toplam} nüsha"]
    for anahtar, ad in (
        ("rafta", "rafta"),
        ("oduncte", "ödünçte"),
        ("sinifta", "sınıf kitaplığında"),
        ("onarimda", "onarımda"),
    ):
        adet = int(e[anahtar] or 0)
        if adet:
            parcalar.append(f"{adet} {ad}")
    if int(e["odunc_verilmez_sayisi"] or 0) == toplam:
        parcalar.append(sabitler.ODUNC_VERILMEZ)
    return " · ".join(parcalar)


def _eser_satiri(istek: Istek, e: Mapping[str, Any]) -> dict[str, str]:
    bilgi = [sabitler.TUR_ADLARI.get(str(e["tur"]), "")]
    if e["yil"]:
        bilgi.append(str(e["yil"]))
    if _metin(e["yer_no"]):
        bilgi.append(_metin(e["yer_no"]))
    return {
        "bag": istek.bag(f"/eser/{int(e['id'])}"),
        "baslik": _metin(e["baslik"]),
        "yazarlar": _metin(e["yazarlar"]),
        "konular": _metin(e["konular"]),
        "bilgi": " · ".join(parca for parca in bilgi if parca),
        "nusha_ozeti": nusha_ozeti(e),
    }


def _sayfalama(
    istek: Istek, yol: str, sonuc: veri.Sayfa, parametreler: Mapping[str, str | None]
) -> dict[str, Any]:
    def bag(sayfa: int) -> str:
        return istek.bag(yol, **parametreler, sayfa=None if sayfa == 1 else sayfa)

    return {
        "sayfa": str(sonuc.sayfa),
        "sayfa_sayisi": sonuc.sayfa_sayisi,
        "onceki": bag(sonuc.sayfa - 1) if sonuc.sayfa > 1 else "",
        "sonraki": bag(sonuc.sayfa + 1) if sonuc.sayfa < sonuc.sayfa_sayisi else "",
    }


def _sonuc(istek: Istek, sonuc: veri.Sayfa, toplam_metni: str) -> dict[str, Any]:
    return {
        "toplam": sonuc.toplam,
        "toplam_metni": toplam_metni,
        "eserler": [_eser_satiri(istek, e) for e in sonuc.satirlar],
    }


def _taban(istek: Istek, okul: veri.OkulBilgisi | None, *, sayfa_basligi: str) -> dict[str, Any]:
    """Her sayfanın ortak bağlamı (bağlantılar tahta kipini taşır)."""
    return {
        "sayfa_basligi": sayfa_basligi,
        "tahta": istek.tahta,
        "css_adresi": CSS_YOLU,
        "okul_adi": okul.okul_adi if okul else "",
        "konular_acik": okul.konular_acik if okul else True,
        "veri_yok": okul is None,
        "en_uzun_arama": sabitler.EN_UZUN_ARAMA,
        "bag": {
            "ana": istek.bag("/"),
            "ara": istek.bag("/ara"),
            "ara_formu": "/ara",
            "eserler": istek.bag("/eserler"),
            "yazarlar": istek.bag("/yazarlar"),
            "konular": istek.bag("/konular"),
            "hakkinda": istek.bag("/hakkinda"),
        },
        "arama": {"q": "", "konu": ""},
        "tur_secenekleri": _tur_secenekleri(None),
    }


def _tur_secenekleri(secili: str | None) -> list[dict[str, Any]]:
    return [
        {"kod": kisa, "ad": sabitler.TUR_ADLARI[kod], "secili": kod == secili}
        for kisa, kod in sabitler.TURLER.items()
    ]


def _harf_anahtari(ortam: SayfaOrtami, h: str) -> str:
    assert ortam.kurulum is not None
    anahtar = ortam.kurulum.siralama_anahtari(h)
    if not anahtar:
        raise Bulunamadi
    return anahtar[0]


def _diger_ust_siniri(ortam: SayfaOrtami) -> str:
    return min(_harf_anahtari(ortam, h) for h in sabitler.HARFLER)


def _harf_cubugu(
    istek: Istek, ortam: SayfaOrtami, eksen: str, sayilar: Mapping[str, int], secili: str | None
) -> list[dict[str, Any]]:
    cubuk: list[dict[str, Any]] = []
    for h in sabitler.HARFLER:
        adet = sayilar.get(_harf_anahtari(ortam, h), 0)
        cubuk.append(
            {"ad": h, "bag": istek.bag(f"/{eksen}/{h}") if adet else "", "secili": h == secili}
        )
    ust = _diger_ust_siniri(ortam)
    diger = sum(adet for ilk, adet in sayilar.items() if ilk < ust)
    cubuk.append(
        {
            "ad": sabitler.DIGER_ADI,
            "bag": istek.bag(f"/{eksen}/{sabitler.DIGER}") if diger else "",
            "secili": secili == sabitler.DIGER,
        }
    )
    return cubuk


# ---------------------------------------------------------------------------
# İşleyiciler
# ---------------------------------------------------------------------------
def saglik(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    return Yanit("200 OK", "text/plain; charset=utf-8", b"tamam")


def stil(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    return Yanit("200 OK", CSS, CSS_BAYTLARI, CSS_ONBELLEK)


def ana(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    """`/`: arama ve vitrin. Veri yoksa da açılır (öz sınama imzası bu sayfadadır)."""
    okul: veri.OkulBilgisi | None = None
    yeni: list[dict[str, Any]] = []
    cok: list[dict[str, Any]] = []
    try:
        with ortam.baglanti() as conn:
            okul = veri.okul_bilgisi(conn)
            if okul.vitrin_acik:
                yeni = veri.yeni_gelenler(conn)
                cok = veri.cok_okunanlar(conn)
    except veri.VeriHatasi:
        ortam.veri_hatasini_bildir()
        okul, yeni, cok = None, [], []
    baglam = _taban(istek, okul, sayfa_basligi="Ana Sayfa")
    baglam.update(
        {
            "vitrin_acik": bool(okul and okul.vitrin_acik),
            "yeni_gelenler": [_eser_satiri(istek, e) for e in yeni],
            "cok_okunanlar": [_eser_satiri(istek, e) for e in cok],
        }
    )
    return _html("ana.html", baglam)


def ara(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    """`/ara?q=&tur=&konu=&sayfa=` (§5.3 doğrulamaları)."""
    ham_q = (istek.parametre("q") or "").strip()
    kirpildi = len(ham_q) > sabitler.EN_UZUN_ARAMA
    q = ham_q[: sabitler.EN_UZUN_ARAMA]
    tur_kisa = istek.parametre("tur") or ""
    tur = tur_kodu(tur_kisa)
    konu = ana_sinif(istek.parametre("konu"))
    istenen_sayfa = sayfa_numarasi(istek.parametre("sayfa"))
    if ortam.kurulum is None:
        raise veri.VeriHatasi("katalog veritabanı yapılandırılmadı")
    parcalar = ortam.kurulum.arama_parcalari(q) if q else []

    with ortam.baglanti() as conn:
        okul = veri.okul_bilgisi(conn)
        if q and not parcalar:
            sonuc = veri.Sayfa([], 0, 1, 1)
        else:
            sonuc = veri.ara(conn, parcalar=parcalar, tur=tur, ana_sinif=konu, sayfa=istenen_sayfa)
    filtre = bool(q or tur or konu)
    baglam = _taban(istek, okul, sayfa_basligi="Arama Sonuçları" if filtre else "Bütün Kaynaklar")
    parametreler: dict[str, str | None] = {"q": q or None, "tur": tur_kisa or None, "konu": konu}
    baglam.update(
        {
            "arama": {
                "q": q,
                "konu": konu or "",
                "konu_adi": sabitler.ANA_SINIFLAR[konu] if konu else "",
                "konusuz_bag": istek.bag("/ara", q=q or None, tur=tur_kisa or None),
                "kirpildi": kirpildi,
            },
            "tur_secenekleri": _tur_secenekleri(tur),
            "sonuc": _sonuc(istek, sonuc, f"{sonuc.toplam} kaynak bulundu."),
            "sayfalama": _sayfalama(istek, "/ara", sonuc, parametreler),
        }
    )
    return _html("ara.html", baglam)


def _kunye_satirlari(e: Mapping[str, Any]) -> list[dict[str, str]]:
    sinif = _metin(e["sinif_kodu"])
    ana = sabitler.ANA_SINIFLAR.get(_metin(e["ana_sinif"]))
    if sinif and ana:
        sinif = f"{sinif} — Dewey Onlu Sınıflama (DOS) ana sınıfı: {ana}"
    bolum = _metin(e["bolum_adi"])
    if bolum and _metin(e["bolum_tarifi"]):
        bolum = f"{bolum} — {_metin(e['bolum_tarifi'])}"
    satirlar = (
        ("Yazar(lar)", _metin(e["yazarlar"])),
        ("Çevirmen", _metin(e["cevirmen"])),
        ("Yayınevi", _metin(e["yayinevi"])),
        ("Baskı", _metin(e["baski"])),
        ("Yayın yılı", _metin(e["yil"])),
        ("ISBN", _metin(e["isbn"])),
        ("Konu(lar)", _metin(e["konular"])),
        ("Dil", _metin(e["dil"])),
        ("Kaynak türü", sabitler.TUR_ADLARI.get(str(e["tur"]), "")),
        ("Sınıflama kodu", sinif),
        ("Yer numarası", _metin(e["yer_no"])),
        ("Bölüm", bolum),
    )
    return [{"ad": ad, "deger": deger} for ad, deger in satirlar if deger]


def _nusha_satiri(n: Mapping[str, Any]) -> dict[str, str]:
    durum = str(n["durum"])
    if durum == "AVAILABLE" and n["odunc_verilmez"]:
        ad, sinif = sabitler.ODUNC_VERILMEZ, "durum-okunur"
    elif durum == "AVAILABLE":
        ad, sinif = sabitler.DURUM_ADLARI[durum], "durum-rafta"
    elif durum == "ON_LOAN":
        ad, sinif = sabitler.DURUM_ADLARI[durum], "durum-oduncte"
    else:
        ad, sinif = sabitler.DURUM_ADLARI.get(durum, ""), ""
    return {"durum_adi": ad, "sinif": sinif, "bolum_adi": _metin(n["bolum_adi"])}


def eser(istek: Istek, ortam: SayfaOrtami, parametre: str | None) -> Yanit:
    """`/eser/<id>`: künye ve nüsha durumları. Görünmeyen eser 404'tür."""
    eser_id = kanonik_tam_sayi(parametre)
    with ortam.baglanti() as conn:
        okul = veri.okul_bilgisi(conn)
        satir = veri.eser(conn, eser_id)
        if satir is None:
            raise Bulunamadi
        nushalar = veri.nushalar(conn, eser_id)
    baglam = _taban(istek, okul, sayfa_basligi=_metin(satir["baslik"]) or "Kaynak")
    baglam.update(
        {
            "eser": {"baslik": _metin(satir["baslik"]), "nusha_ozeti": nusha_ozeti(satir)},
            "kunye_satirlari": _kunye_satirlari(satir),
            "nushalar": [_nusha_satiri(n) for n in nushalar],
        }
    )
    return _html("eser.html", baglam)


_DIZIN_ACIKLAMALARI: Final = {
    "eserler": "Kaynaklar, kaynak adının ilk harfine göre Türk alfabesi sırasıyla dizilir.",
    "yazarlar": "Kaynaklar, ilk yazarın soyadının ilk harfine göre dizilir.",
    "konular": "Kaynaklar, ilk konunun ilk harfine göre dizilir.",
}


def _dizin(eksen: str, istek: Istek, ortam: SayfaOrtami, parametre: str | None) -> Yanit:
    if eksen == "konular" and parametre is None:
        raise Bulunamadi  # `/konular` ayrı sayfadır
    secili = None if parametre is None else harf(parametre)
    istenen_sayfa = sayfa_numarasi(istek.parametre("sayfa"))
    if ortam.kurulum is None:
        raise veri.VeriHatasi("katalog veritabanı yapılandırılmadı")
    sutun, baslik = sabitler.EKSENLER[eksen]
    with ortam.baglanti() as conn:
        okul = veri.okul_bilgisi(conn)
        if eksen == "konular" and not okul.konular_acik:
            raise Bulunamadi
        sayilar = veri.ilk_harf_sayilari(conn, sutun=sutun)
        sonuc = None
        if secili is not None:
            sonuc = veri.harf_dizini(
                conn,
                sutun=sutun,
                harf_anahtari=None if secili == sabitler.DIGER else _harf_anahtari(ortam, secili),
                diger_ust_siniri=_diger_ust_siniri(ortam),
                sayfa=istenen_sayfa,
            )
    harf_adi = sabitler.DIGER_ADI if secili == sabitler.DIGER else secili
    baglam = _taban(istek, okul, sayfa_basligi=f"{baslik}: {harf_adi}" if harf_adi else baslik)
    baglam.update(
        {
            "eksen": eksen,
            "dizin_aciklamasi": _DIZIN_ACIKLAMALARI[eksen],
            "harf_cubugu": _harf_cubugu(istek, ortam, eksen, sayilar, secili),
            "sonuc": None
            if sonuc is None
            else _sonuc(istek, sonuc, f"Bu harfte {sonuc.toplam} kaynak var."),
            "sayfalama": {}
            if sonuc is None
            else _sayfalama(istek, f"/{eksen}/{secili}", sonuc, {}),
        }
    )
    return _html("dizin.html", baglam)


def eserler_dizini(istek: Istek, ortam: SayfaOrtami, parametre: str | None) -> Yanit:
    return _dizin("eserler", istek, ortam, parametre)


def yazarlar_dizini(istek: Istek, ortam: SayfaOrtami, parametre: str | None) -> Yanit:
    return _dizin("yazarlar", istek, ortam, parametre)


def konu_dizini(istek: Istek, ortam: SayfaOrtami, parametre: str | None) -> Yanit:
    return _dizin("konular", istek, ortam, parametre)


def konular(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    """`/konular`: DOS ana sınıfları ve konu dizininin harf çubuğu (§5.4)."""
    if ortam.kurulum is None:
        raise veri.VeriHatasi("katalog veritabanı yapılandırılmadı")
    with ortam.baglanti() as conn:
        okul = veri.okul_bilgisi(conn)
        if not okul.konular_acik:
            raise Bulunamadi
        sinif_sayilari = veri.ana_sinif_sayilari(conn)
        sayilar = veri.ilk_harf_sayilari(conn, sutun=sabitler.EKSENLER["konular"][0])
    siniflar = []
    for hane, ad in sabitler.ANA_SINIFLAR.items():
        adet = sinif_sayilari.get(hane, 0)
        siniflar.append(
            {
                "ad": ad,
                "adet_metni": f"{adet} kaynak",
                "bag": istek.bag("/ara", konu=hane) if adet else "",
            }
        )
    siniflandirilmamis = sum(
        adet for hane, adet in sinif_sayilari.items() if hane not in sabitler.ANA_SINIFLAR
    )
    baglam = _taban(istek, okul, sayfa_basligi="Konular")
    baglam.update(
        {
            "siniflar": siniflar,
            "siniflandirilmamis": str(siniflandirilmamis) if siniflandirilmamis else "",
            "harf_cubugu": _harf_cubugu(istek, ortam, "konular", sayilar, None),
        }
    )
    return _html("konular.html", baglam)


def hakkinda(istek: Istek, ortam: SayfaOrtami, _p: str | None) -> Yanit:
    """`/hakkinda`: saatler; katalogun ne gösterip ne göstermediği. Veri yoksa da açılır."""
    okul: veri.OkulBilgisi | None
    try:
        with ortam.baglanti() as conn:
            okul = veri.okul_bilgisi(conn)
    except veri.VeriHatasi:
        ortam.veri_hatasini_bildir()
        okul = None
    baglam = _taban(istek, okul, sayfa_basligi="Hakkında")
    baglam["saatler"] = okul.saatler if okul else ""
    return _html("hakkinda.html", baglam)
