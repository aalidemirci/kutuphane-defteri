"""Ana marka logosunu ve elle çizilmiş küçük ikon kesimlerini üretir.

Tasarım — "Raf ve etiket" (29.09.2026 kullanıcı kararı; tasarım §14.1 F12 ekleri
L-1): cilt laciverti, köşeleri yuvarlatılmış bir karo üzerinde safran bir raf;
rafta yan yana duran üç kalın kitap sırtı (farklı yükseklikte) ve en uzun sırta
yaslanmış dördüncü kitap. En uzun sırtta safran bir sırt etiketi ve üzerinde kısa
barkod çizgileri durur: programın katalog, etiket ve barkod işine gönderme. Sırt
bantları zemin rengindedir (negatif boşluk); gölge, degrade ve metin yoktur.
Yaslanan kitap küçük boyutlarda da kalır: o olmadan üç dik çubuk bir sütun
grafiği gibi okunur, rafı "raf" yapan imdir.

Palet okulapp.org'daki program paletidir: cilt laciverti #1c3259 (karo), safran
#eea23f (raf, etiket), kâğıt #f1f3f8 (sırtlar); gök mavisi #8fb4ee yalnız ikinci
sırt tonudur.

Çıktılar (bu dizine; depoya COMMIT EDİLİR):

* ``kutuphane-defteri-logo.png`` — 1024×1024 ana çizim, saydam kenar boşluklu.
  48 px ve üstü kesimleri ``ikon_uret.py`` bundan türetir.
* ``kutuphane-defteri-16.png``, ``-24.png``, ``-32.png`` — ÖLÇEKLENMEZ: piksel
  ızgarasına oturtulmuş ayrı ve sade çizimlerdir. 16'da iki sırt, safran etiket
  bandı, merdiven biçiminde yaslanan kitap ve safran raf; 24'te üç sırt, barkod
  yok; 32'de etiketin içinde bir ince bir kalın barkod çizgisi (iki eş çizgi "II"
  okunuyordu). Dikdörtgenler tam piksele oturduğu için keskindir. ``ikon_uret.py``
  bunları olduğu gibi ``.ico``'ya koyar.

Kenar boşluğu (bütün boyutlarda tek kural; ``ikon_uret.py`` 48+ için aynısını
uygular, ``packaging/tests/test_ikonlar.py`` sınar): karo, tuvalin kenarına
⌈boyut/32⌉ px saydam boşluk bırakır — 24 ve 32'de 1 px, 48 ve 64'te 2, 256'da 8,
bu 1024'te 32. Karo doluluğu böylece ~%94'tür (24 ve 48'de tam piksele
yuvarlandığı için %91,7). Gerekçe: Windows bir boyutu tam bulamazsa bir üstünü
küçültür (Microsoft Learn, "Construct your Windows app's icon" → Icon scaling);
ölçek %125'te görev çubuğu 30 px'i elle çizilmiş 32'den, %150'de 36 px'i ana
çizimden (48) alır, Başlat sabitlemesi %100'de 32'yi, %125'te 48'i kullanır.
Pardus'un hicolor temasında da menü 24/32'yi, uygulama ızgarası 48 ve üstünü
seçer. İki aile yan yana geçtiği için doluluğu aynı olmalıdır; eski düzende
elle çizilmiş karolar tuvali kenara dek dolduruyor, ana çizim %8 boşlukla ~%86
kalıyordu ve 32 → 48 geçişinde karo gözle görülür biçimde küçülüyordu. Tek
istisna 16'dır: 1 px boşluk çizim alanının %23'ünü götürür ve onaylanan 16
kesimi rafı karonun iki kenarına dek (x = 1..15) yayar; 16'nın ölçekli komşusu
olan 20 px (%125'te başlık çubuğu ve bağlam menüsü) 24'ten küçültülür, fark 20
px'te ~1,7 px'tir.

Çalıştırma (depo kökünden, Docker içinde — host'a kurulum YASAK):

    docker compose run --rm -w /repo backend python packaging/ikonlar/logo_uret.py
    docker compose run --rm -w /repo backend python packaging/ikonlar/ikon_uret.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

KLASOR = Path(__file__).resolve().parent
LOGO = KLASOR / "kutuphane-defteri-logo.png"
KENAR = 1024
SS = 4  # süper örnekleme katsayısı (yumuşak kenar için)

Renk = tuple[int, int, int, int]
Kutu = tuple[float, float, float, float]

# --- Palet ------------------------------------------------------------------
LACIVERT: Renk = (0x1C, 0x32, 0x59, 255)  # cilt laciverti: karo, bantlar, barkod
SAFRAN: Renk = (0xEE, 0xA2, 0x3F, 255)  # raf ve sırt etiketi
KAGIT: Renk = (0xF1, 0xF3, 0xF8, 255)  # açık sırtlar
GOK: Renk = (0x8F, 0xB4, 0xEE, 255)  # ikinci sırt tonu

ZEMIN = LACIVERT
BANT = LACIVERT
BARKOD = LACIVERT
ETIKET = SAFRAN
RAF = SAFRAN
#: Soldan sağa: üç ayakta sırt + yaslanan kitap.
KITAPLAR: tuple[Renk, Renk, Renk, Renk] = (KAGIT, GOK, KAGIT, GOK)

# --- 1024 geometrisi (px) -----------------------------------------------------
ZEMIN_PAY = math.ceil(KENAR / 32)  # kenar boşluğu kuralı (başlık): 32 px
ZEMIN_YARICAP = 197  # karo kenarının ~%20,5'i (küçük kesimlerle aynı oran)

#: Ayakta duran sırtlar: (genişlik, yükseklik); raf üstü y = 0'a oturur.
SIRTLAR = ((128, 430), (108, 350), (164, 520))
SIRT_ARASI = 16
ETIKETLI_SIRT = 2  # barkod etiketi bu sırtta (en uzunu)
YASLANAN = (116, 420)  # genişlik, yükseklik
YASLANMA_ACISI = 19  # derece; üst uç sola, komşu sırta

KITAP_YARICAP = 18
BANT_KALINLIK = 22
BANT_UST = 46  # sırtın tepesinden üst bandın üstüne
BANT_ALT = 64  # sırtın dibinden alt bandın üstüne

ETIKET_PAY_YAN = 20
ETIKET_ALT = 58  # sırtın dibinden etiketin altına
ETIKET_YUKSEKLIK = 170
ETIKET_YARICAP = 14
BARKOD_PAY_YAN = 16
BARKOD_PAY_DIKEY = 22
#: Code128'i andıran çizgi/boşluk genişlikleri (modül cinsinden), çizgiyle başlar.
BARKOD_DESEN = (2, 1, 1, 2, 3, 1, 1, 1, 2, 2, 1, 1, 3, 1, 2)

RAF_KALINLIK = 50
RAF_TASMA = 44  # rafın kitapların dışına taşması
RAF_YARICAP = 18
OPTIK_KAYMA = 10  # grubun kütle merkezi aşağıda durduğu için hafif yukarı


def _s(*degerler: float) -> tuple[int, ...]:
    return tuple(round(d * SS) for d in degerler)


def _dondur(px: float, py: float, a: float, b: float, aci: float) -> tuple[float, float]:
    """Yerel noktayı (a sağa, b aşağı) pivotun çevresinde saat yönünün tersine döndürür."""
    t = math.radians(aci)
    return (px + a * math.cos(t) + b * math.sin(t), py - a * math.sin(t) + b * math.cos(t))


# --- Ana çizim (1024) -----------------------------------------------------------
def _kitap(ciz: ImageDraw.ImageDraw, kutu: Kutu, renk: Renk, *, etiketli: bool) -> None:
    """Tek kitap sırtı: gövde + üst bant + (alt bant ya da barkodlu sırt etiketi)."""
    x0, y0, x1, y1 = kutu
    ciz.rounded_rectangle(_s(x0, y0, x1, y1), radius=KITAP_YARICAP * SS, fill=renk)
    ust = y0 + BANT_UST
    ciz.rectangle(_s(x0, ust, x1, ust + BANT_KALINLIK), fill=BANT)
    if not etiketli:
        alt = y1 - BANT_ALT
        ciz.rectangle(_s(x0, alt, x1, alt + BANT_KALINLIK), fill=BANT)
        return

    ex0, ex1 = x0 + ETIKET_PAY_YAN, x1 - ETIKET_PAY_YAN
    ey1 = y1 - ETIKET_ALT
    ey0 = ey1 - ETIKET_YUKSEKLIK
    ciz.rounded_rectangle(_s(ex0, ey0, ex1, ey1), radius=ETIKET_YARICAP * SS, fill=ETIKET)
    bx0, bx1 = ex0 + BARKOD_PAY_YAN, ex1 - BARKOD_PAY_YAN
    by0, by1 = ey0 + BARKOD_PAY_DIKEY, ey1 - BARKOD_PAY_DIKEY
    modul = (bx1 - bx0) / sum(BARKOD_DESEN)
    x = bx0
    for sira, genislik in enumerate(BARKOD_DESEN):
        if sira % 2 == 0:
            ciz.rectangle(_s(x, by0, x + genislik * modul, by1), fill=BARKOD)
        x += genislik * modul


@dataclass(frozen=True)
class _Yerlesim:
    ayakta: tuple[Kutu, ...]
    yaslanan_pivot: tuple[float, float]  # yaslanan kitabın sol alt köşesi
    raf: Kutu


def _yerlesim() -> _Yerlesim:
    """Grubu yerel koordinatta kurar (raf üstü y = 0) ve tuvale ortalar."""
    ayakta: list[Kutu] = []
    x = 0.0
    for genislik, yukseklik in SIRTLAR:
        ayakta.append((x, -yukseklik, x + genislik, 0.0))
        x += genislik + SIRT_ARASI
    sag_yuz = ayakta[-1][2]

    w, h = YASLANAN
    t = math.radians(YASLANMA_ACISI)
    r = KITAP_YARICAP
    # Sol üst köşe yayının en sol noktası komşu sırtın sağ yüzüne değsin.
    px = sag_yuz + r - r * math.cos(t) + (h - r) * math.sin(t)
    # Sol alt köşe yuvarlak olduğu için dönen kitap raftan kalkar; geri indirilir.
    py = r * (math.sin(t) + math.cos(t) - 1)
    donmus = [_dondur(px, py, a, b, YASLANMA_ACISI) for a, b in ((0, 0), (w, 0), (w, -h), (0, -h))]

    raf_x0 = -RAF_TASMA
    raf_x1 = max(p[0] for p in donmus) + RAF_TASMA
    min_y = min(min(k[1] for k in ayakta), min(p[1] for p in donmus))
    ox = KENAR / 2 - (raf_x0 + raf_x1) / 2
    oy = KENAR / 2 - (min_y + RAF_KALINLIK) / 2 - OPTIK_KAYMA
    return _Yerlesim(
        ayakta=tuple((a + ox, b + oy, c + ox, d + oy) for a, b, c, d in ayakta),
        yaslanan_pivot=(px + ox, py + oy),
        raf=(raf_x0 + ox, oy, raf_x1 + ox, RAF_KALINLIK + oy),
    )


def buyuk() -> Image.Image:
    """1024×1024 ana çizim (saydam kenar boşluğuyla)."""
    tuval = Image.new("RGBA", (KENAR * SS, KENAR * SS), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(tuval)
    ciz.rounded_rectangle(
        (
            ZEMIN_PAY * SS,
            ZEMIN_PAY * SS,
            (KENAR - ZEMIN_PAY) * SS - 1,
            (KENAR - ZEMIN_PAY) * SS - 1,
        ),
        radius=ZEMIN_YARICAP * SS,
        fill=ZEMIN,
    )
    yer = _yerlesim()

    # Raf önce: kitaplar üstüne oturur.
    ciz.rounded_rectangle(_s(*yer.raf), radius=RAF_YARICAP * SS, fill=RAF)
    for sira, kutu in enumerate(yer.ayakta):
        _kitap(ciz, kutu, KITAPLAR[sira], etiketli=sira == ETIKETLI_SIRT)

    # Yaslanan kitap: ayrı katmanda dik çizilir, sol alt köşesi çevresinde döner.
    katman = Image.new("RGBA", tuval.size, (0, 0, 0, 0))
    px, py = yer.yaslanan_pivot
    w, h = YASLANAN
    _kitap(ImageDraw.Draw(katman), (px, py - h, px + w, py), KITAPLAR[3], etiketli=False)
    katman = katman.rotate(
        YASLANMA_ACISI, resample=Image.Resampling.BICUBIC, center=(px * SS, py * SS)
    )
    tuval.alpha_composite(katman)
    return tuval.resize((KENAR, KENAR), Image.Resampling.BOX)


# --- Elle çizilmiş küçük kesimler (piksel ızgarası) -------------------------------
# Koordinatlar tam sayı ve yarı açıktır: (x0, y0, x1, y1) → [x0, x1) × [y0, y1).
# Yaslanan kitap tek eğik öğedir: 24 ve 32'de yumuşatılmış bir çokgendir; 16'da
# çokgen bulanık bir leke oluyordu, orada elle dizilmiş, iki piksel genişliğinde
# bir merdivendir. 16'da orta sırt ve barkod düşer, 24'te barkod düşer.
@dataclass(frozen=True)
class _EgikKitap:
    sag_yuz: float  # yaslandığı sırtın sağ yüzü (x)
    genislik: float
    yukseklik: float
    aci: float


@dataclass(frozen=True)
class KucukCizim:
    karo: tuple[int, int, int, int]  # kenar boşluğu kuralı (başlık)
    yaricap: float
    raf: tuple[int, int, int, int]
    #: (x0, y0, x1, y1, KITAPLAR sırası)
    sirtlar: tuple[tuple[int, int, int, int, int], ...]
    bantlar: tuple[tuple[int, int, int, int], ...]
    etiket: tuple[int, int, int, int]
    barkod: tuple[tuple[int, int, int, int], ...] = ()
    #: 16 için: (satır, x0, x1) — elle dizilmiş merdiven
    yaslanan_pikseller: tuple[tuple[int, int, int], ...] = ()
    yaslanan: _EgikKitap | None = None


KUCUK: dict[int, KucukCizim] = {
    16: KucukCizim(
        karo=(0, 0, 16, 16),
        yaricap=3.5,
        raf=(1, 12, 15, 13),
        sirtlar=((2, 5, 5, 12, 0), (6, 3, 9, 12, 2)),
        bantlar=((2, 6, 5, 7), (6, 4, 9, 5)),
        etiket=(6, 7, 9, 9),
        yaslanan_pikseller=(
            (5, 9, 11),
            (6, 9, 11),
            (7, 10, 12),
            (8, 10, 12),
            (9, 11, 13),
            (10, 11, 13),
            (11, 12, 14),
        ),
    ),
    24: KucukCizim(
        karo=(1, 1, 23, 23),
        yaricap=4.5,
        raf=(3, 17, 22, 19),
        sirtlar=((4, 7, 7, 17, 0), (8, 9, 10, 17, 1), (11, 5, 15, 17, 2)),
        bantlar=((4, 8, 7, 9), (4, 15, 7, 16), (8, 10, 10, 11), (8, 15, 10, 16), (11, 6, 15, 7)),
        etiket=(11, 11, 15, 15),
        yaslanan=_EgikKitap(sag_yuz=15, genislik=2.8, yukseklik=9.8, aci=19),
    ),
    32: KucukCizim(
        karo=(1, 1, 31, 31),
        yaricap=6.5,
        raf=(3, 23, 29, 25),
        sirtlar=((5, 10, 9, 23, 0), (10, 13, 13, 23, 1), (14, 7, 20, 23, 2)),
        bantlar=(
            (5, 11, 9, 12),
            (5, 20, 9, 21),
            (10, 14, 13, 15),
            (10, 20, 13, 21),
            (14, 8, 20, 9),
        ),
        etiket=(14, 15, 20, 21),
        barkod=((15, 16, 16, 20), (17, 16, 19, 20)),
        yaslanan=_EgikKitap(sag_yuz=20, genislik=3.6, yukseklik=13.0, aci=19),
    ),
}


def kucuk(boyut: int) -> Image.Image:
    """Elle çizilmiş kesim (16, 24 ya da 32 px)."""
    cizim = KUCUK[boyut]
    tuval = Image.new("RGBA", (boyut * SS, boyut * SS), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(tuval)

    def dik(kutu: tuple[int, ...], renk: Renk) -> None:
        x0, y0, x1, y1 = kutu[:4]
        ciz.rectangle((x0 * SS, y0 * SS, x1 * SS - 1, y1 * SS - 1), fill=renk)

    kx0, ky0, kx1, ky1 = cizim.karo
    ciz.rounded_rectangle(
        (kx0 * SS, ky0 * SS, kx1 * SS - 1, ky1 * SS - 1),
        radius=round(cizim.yaricap * SS),
        fill=ZEMIN,
    )
    dik(cizim.raf, RAF)
    for sirt in cizim.sirtlar:
        dik(sirt, KITAPLAR[sirt[4]])
    for bant in cizim.bantlar:
        dik(bant, BANT)
    dik(cizim.etiket, ETIKET)
    for cizgi in cizim.barkod:
        dik(cizgi, BARKOD)

    for satir, x0, x1 in cizim.yaslanan_pikseller:
        dik((x0, satir, x1, satir + 1), KITAPLAR[3])
    if cizim.yaslanan is not None:
        egik = cizim.yaslanan
        # Sol üst köşe komşu sırta değsin; sol alt köşe raf üstünde.
        px = egik.sag_yuz + egik.yukseklik * math.sin(math.radians(egik.aci))
        py = cizim.raf[1]
        koseler = (
            (0, -egik.yukseklik),
            (egik.genislik, -egik.yukseklik),
            (egik.genislik, 0),
            (0, 0),
        )
        noktalar = [_dondur(px, py, a, b, egik.aci) for a, b in koseler]
        ciz.polygon([(x * SS, y * SS) for x, y in noktalar], fill=KITAPLAR[3])
    return tuval.resize((boyut, boyut), Image.Resampling.BOX)


def kucuk_yolu(boyut: int) -> Path:
    return KLASOR / f"kutuphane-defteri-{boyut}.png"


def generate() -> list[Path]:
    """Ana çizimi ve elle çizilmiş kesimleri yazar; yolları döndürür."""
    yazilan: list[Path] = []
    buyuk().save(LOGO, format="PNG", optimize=True)
    yazilan.append(LOGO)
    for boyut in KUCUK:
        yol = kucuk_yolu(boyut)
        kucuk(boyut).save(yol, format="PNG", optimize=True)
        yazilan.append(yol)
    return yazilan


if __name__ == "__main__":
    import sys

    for yol in generate():
        # Betik yalnız elle çalıştırılır; çıktı listesi bilinçli olarak yazılır.
        sys.stderr.write(f"yazıldı: {yol}\n")
