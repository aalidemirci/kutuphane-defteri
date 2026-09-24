"""Etiket PDF'lerini ÖLÇEN test yardımcısı — içerik akışının küçük bir yorumlayıcısı.

Etiket testleri "HTML şuna benziyor" demekle yetinmez: basılacak olan PDF'tir.
Bu modül PDF sayfasının içerik akışını (pypdf `ContentStream`) sırayla
yürütür ve iki şey çıkarır:

- **Dolgular** (`re` + `f`): barkod barları ve beyaz arka planlar; her biri
  sayfa üzerinde mm cinsinden dikdörtgen + dolgu rengi.
- **Metin koşuları** (`TJ` / `Tj`): her koşunun sayfadaki başlangıç ve bitiş
  x'i, taban çizgisi y'si ve Unicode metni. Genişlik, PDF'in KENDİ yazı tipi
  genişlik tablosundan (`/W`) hesaplanır — yani ölçü, yazıcıya gidecek
  çizimin ölçüsüdür, programın kendi tahmini değil.

Desteklenen işleçler WeasyPrint'in ürettikleridir: `q Q cm re m l f n W S BT ET
Tf Tm Td TD T* Tc Tw TJ Tj rg g Do`. Çizgiyle çizilen doğru parçaları (`m` + `l`
+ `S` — kalibrasyon cetveli) sınır kutusuyla `cizgiler`'e girer. Koordinatlar
sayfanın sol üst köşesine göre mm'dir (etiket geometrisiyle aynı eksen).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ContentStream

MM_PER_PT = 25.4 / 72

Matris = tuple[float, float, float, float, float, float]
KIMLIK: Matris = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _carp(m1: Matris, m2: Matris) -> Matris:
    """m1 × m2 (PDF satır vektörü düzeni: önce m1 uygulanır)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _uygula(m: Matris, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


@dataclass(frozen=True)
class Dolgu:
    """Doldurulmuş dikdörtgen (mm, sayfanın sol üst köşesine göre)."""

    x0: float
    y0: float
    x1: float
    y1: float
    renk: tuple[float, ...]

    @property
    def genislik(self) -> float:
        return self.x1 - self.x0

    @property
    def yukseklik(self) -> float:
        return self.y1 - self.y0

    @property
    def siyah(self) -> bool:
        return all(abs(kanal) < 1e-6 for kanal in self.renk)


@dataclass(frozen=True)
class Cizgi:
    """Çizgiyle (stroke) çizilmiş dikdörtgen — kalibrasyon çerçeveleri."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Yazi:
    """Tek metin koşusu: sayfadaki yatay aralık, taban çizgisi ve yazı boyu (mm)."""

    metin: str
    x0: float
    x1: float
    taban: float
    boy_mm: float
    kalin: bool


@dataclass
class _YaziTipi:
    genislikler: dict[int, float]
    varsayilan: float
    unicode: dict[int, str]
    kalin: bool


@dataclass
class _Durum:
    ctm: Matris = KIMLIK
    renk: tuple[float, ...] = (0.0,)
    tc: float = 0.0
    tw: float = 0.0


@dataclass
class SayfaOlcumu:
    dolgular: list[Dolgu] = field(default_factory=list)
    cizgiler: list[Cizgi] = field(default_factory=list)
    yazilar: list[Yazi] = field(default_factory=list)

    def siyah_dolgular(self) -> list[Dolgu]:
        return [d for d in self.dolgular if d.siyah]

    def metinler(self) -> list[str]:
        return [y.metin for y in self.yazilar]


def _w_dizisi(w: Any) -> dict[int, float]:
    """CIDFont `/W` dizisi → {cid: genişlik (1/1000 em)}."""
    sonuc: dict[int, float] = {}
    dizi = list(w or [])
    sira = 0
    while sira < len(dizi):
        ilk = int(dizi[sira])
        ikinci = dizi[sira + 1]
        if isinstance(ikinci, list) or hasattr(ikinci, "__iter__"):
            for kayma, deger in enumerate(list(ikinci)):
                sonuc[ilk + kayma] = float(deger)
            sira += 2
        else:
            son = int(ikinci)
            deger = float(dizi[sira + 2])
            for cid in range(ilk, son + 1):
                sonuc[cid] = deger
            sira += 3
    return sonuc


_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
_HEX = re.compile(rb"<([0-9a-fA-F]+)>")


def _utf16(hex_metin: bytes) -> str:
    return bytes.fromhex(hex_metin.decode()).decode("utf-16-be")


def _to_unicode(akis: Any) -> dict[int, str]:
    if akis is None:
        return {}
    veri = akis.get_object().get_data()
    eslem: dict[int, str] = {}
    for blok in _BFCHAR.findall(veri):
        degerler = _HEX.findall(blok)
        for kaynak, hedef in zip(degerler[0::2], degerler[1::2], strict=False):
            eslem[int(kaynak, 16)] = _utf16(hedef)
    for blok in _BFRANGE.findall(veri):
        for satir in blok.strip().splitlines():
            degerler = _HEX.findall(satir)
            if len(degerler) == 3:
                bas, son, hedef = (int(d, 16) for d in degerler)
                for kayma in range(son - bas + 1):
                    eslem[bas + kayma] = chr(hedef + kayma)
    return eslem


def _yazi_tipi(nesne: Any) -> _YaziTipi:
    yt = nesne.get_object()
    kalin = "Bold" in str(yt.get("/BaseFont", ""))
    if yt.get("/Subtype") == "/Type0":
        alt = yt["/DescendantFonts"][0].get_object()
        return _YaziTipi(
            genislikler=_w_dizisi(alt.get("/W")),
            varsayilan=float(alt.get("/DW", 1000)),
            unicode=_to_unicode(yt.get("/ToUnicode")),
            kalin=kalin,
        )
    ilk = int(yt.get("/FirstChar", 0))
    genislikler = {ilk + i: float(w) for i, w in enumerate(yt.get("/Widths", []))}
    return _YaziTipi(genislikler, 0.0, _to_unicode(yt.get("/ToUnicode")), kalin)


class _Yorumlayici:
    def __init__(self, sayfa_yuksekligi_pt: float) -> None:
        self.h = sayfa_yuksekligi_pt
        self.olcum = SayfaOlcumu()

    def _mm(self, x: float, y: float) -> tuple[float, float]:
        return x * MM_PER_PT, (self.h - y) * MM_PER_PT

    def _dikdortgen(self, ctm: Matris, x: float, y: float, w: float, h: float) -> tuple[float, ...]:
        koseler = [
            self._mm(*_uygula(ctm, px, py))
            for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))
        ]
        xs = [k[0] for k in koseler]
        ys = [k[1] for k in koseler]
        return min(xs), min(ys), max(xs), max(ys)

    def yurut(self, icerik: Any, kaynaklar: Any, baslangic: Matris) -> None:
        durum = _Durum(ctm=baslangic)
        yigin: list[_Durum] = []
        yol: list[tuple[float, ...]] = []
        nokta: tuple[float, float] = (0.0, 0.0)
        yazi_tipleri: dict[str, _YaziTipi] = {}
        if kaynaklar is not None and "/Font" in kaynaklar:
            for ad, nesne in kaynaklar["/Font"].get_object().items():
                yazi_tipleri[str(ad)] = _yazi_tipi(nesne)
        tm: Matris = KIMLIK
        tlm: Matris = KIMLIK
        yazi_tipi: _YaziTipi | None = None
        boy = 0.0
        akis = icerik if isinstance(icerik, ContentStream) else ContentStream(icerik, None)
        for islenenler, isleci in akis.operations:
            op = isleci.decode("latin-1") if isinstance(isleci, bytes) else str(isleci)
            if op == "q":
                yigin.append(_Durum(durum.ctm, durum.renk, durum.tc, durum.tw))
            elif op == "Q":
                durum = yigin.pop()
            elif op == "cm":
                a, b, c, d, e, f = (float(s) for s in islenenler)
                durum.ctm = _carp((a, b, c, d, e, f), durum.ctm)
            elif op == "rg":
                durum.renk = tuple(float(s) for s in islenenler)
            elif op == "g":
                durum.renk = (float(islenenler[0]),)
            elif op == "re":
                x, y, w, h = (float(s) for s in islenenler)
                yol.append(self._dikdortgen(durum.ctm, x, y, w, h))
            elif op == "m":
                nokta = self._mm(*_uygula(durum.ctm, float(islenenler[0]), float(islenenler[1])))
            elif op == "l":
                # Doğru parçası (kalibrasyon cetveli çentikleri): çizilince sınır kutusu kaydedilir.
                yeni = self._mm(*_uygula(durum.ctm, float(islenenler[0]), float(islenenler[1])))
                yol.append(
                    (
                        min(nokta[0], yeni[0]),
                        min(nokta[1], yeni[1]),
                        max(nokta[0], yeni[0]),
                        max(nokta[1], yeni[1]),
                    )
                )
                nokta = yeni
            elif op in ("f", "F", "f*"):
                for x0, y0, x1, y1 in yol:
                    self.olcum.dolgular.append(Dolgu(x0, y0, x1, y1, durum.renk))
                yol = []
            elif op in ("S", "s", "B", "B*", "b", "b*"):
                for x0, y0, x1, y1 in yol:
                    self.olcum.cizgiler.append(Cizgi(x0, y0, x1, y1))
                yol = []
            elif op == "n":
                yol = []
            elif op == "BT":
                tm = tlm = KIMLIK
            elif op == "Tf":
                yazi_tipi = yazi_tipleri.get(str(islenenler[0]))
                boy = float(islenenler[1])
            elif op == "Tm":
                a, b, c, d, e, f = (float(s) for s in islenenler)
                tm = tlm = (a, b, c, d, e, f)
            elif op in ("Td", "TD"):
                tlm = _carp((1, 0, 0, 1, float(islenenler[0]), float(islenenler[1])), tlm)
                tm = tlm
            elif op == "Tc":
                durum.tc = float(islenenler[0])
            elif op == "Tw":
                durum.tw = float(islenenler[0])
            elif op in ("TJ", "Tj"):
                parcalar = islenenler[0] if op == "TJ" else [islenenler[0]]
                tm = self._metin(parcalar, yazi_tipi, boy, tm, durum)
            elif op == "Do":
                ad = str(islenenler[0])
                nesne = kaynaklar["/XObject"][ad].get_object()
                if nesne.get("/Subtype") == "/Form":
                    a, b, c, d, e, f = (float(s) for s in nesne.get("/Matrix", KIMLIK))
                    self.yurut(nesne, nesne.get("/Resources"), _carp((a, b, c, d, e, f), durum.ctm))

    def _metin(
        self,
        parcalar: Any,
        yazi_tipi: _YaziTipi | None,
        boy: float,
        tm: Matris,
        durum: _Durum,
    ) -> Matris:
        assert yazi_tipi is not None, "yazı tipi seçilmeden metin"
        ilerleme = 0.0
        karakterler: list[str] = []
        for parca in parcalar:
            if isinstance(parca, int | float) or hasattr(parca, "as_numeric"):
                ilerleme -= float(parca) / 1000 * boy
                continue
            ham = bytes(parca.original_bytes if hasattr(parca, "original_bytes") else parca)
            for sira in range(0, len(ham), 2):
                cid = int.from_bytes(ham[sira : sira + 2], "big")
                w = yazi_tipi.genislikler.get(cid, yazi_tipi.varsayilan)
                ilerleme += w / 1000 * boy + durum.tc
                karakterler.append(yazi_tipi.unicode.get(cid, "�"))
        bas = _carp(tm, durum.ctm)
        son = _carp(_carp((1, 0, 0, 1, ilerleme, 0), tm), durum.ctm)
        x0, taban = self._mm(*_uygula(bas, 0, 0))
        x1, _ = self._mm(*_uygula(son, 0, 0))
        # Yazı boyu: metin uzayında 1 birim yukarı çıkınca sayfada kaç mm.
        _, ust = self._mm(*_uygula(bas, 0, boy))
        self.olcum.yazilar.append(
            Yazi(
                "".join(karakterler),
                min(x0, x1),
                max(x0, x1),
                taban,
                abs(taban - ust),
                yazi_tipi.kalin,
            )
        )
        return _carp((1, 0, 0, 1, ilerleme, 0), tm)


def sayfalar(pdf: bytes) -> list[SayfaOlcumu]:
    """PDF'in her sayfası için ölçüm."""
    okuyucu = PdfReader(io.BytesIO(pdf))
    sonuc: list[SayfaOlcumu] = []
    for sayfa in okuyucu.pages:
        yorumlayici = _Yorumlayici(float(sayfa.mediabox.height))
        icerik = sayfa.get_contents()
        assert icerik is not None
        yorumlayici.yurut(icerik, sayfa.get("/Resources"), KIMLIK)
        sonuc.append(yorumlayici.olcum)
    return sonuc


def sayfa_sayisi(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def barlar_hucrede(olcum: SayfaOlcumu, x0: float, y0: float, x1: float, y1: float) -> list[Dolgu]:
    """Kutunun içindeki siyah dolgular, soldan sağa (barkod barları)."""
    icerde = [
        d
        for d in olcum.siyah_dolgular()
        if d.x0 >= x0 - 1e-6 and d.x1 <= x1 + 1e-6 and d.y0 >= y0 - 1e-6 and d.y1 <= y1 + 1e-6
    ]
    return sorted(icerde, key=lambda d: d.x0)


def yazilar_hucrede(olcum: SayfaOlcumu, x0: float, y0: float, x1: float, y1: float) -> list[Yazi]:
    """Taban çizgisi ve başlangıcı kutunun içinde olan metin koşuları."""
    return [y for y in olcum.yazilar if x0 - 1e-6 <= y.x0 <= x1 and y0 <= y.taban <= y1]
