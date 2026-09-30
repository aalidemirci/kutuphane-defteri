"""Uygulama ikonlarını üretir: PNG kesimleri, Windows `.ico` ve ön yüz logosu.

Çalıştırma (depo kökünden, Docker içinde — host'a kurulum YASAK), önce logo:

    docker compose run --rm -w /repo backend python packaging/ikonlar/logo_uret.py
    docker compose run --rm -w /repo backend python packaging/ikonlar/ikon_uret.py

Çıktılar `packaging/ikonlar/` altına yazılır ve depoya COMMIT EDİLİR: paket
üretimi (CI dahil) ikon üretmez, hazır dosyaları kopyalar. Böylece Pillow
sürümü değiştiğinde paketin görüntüsü sessizce değişmez.

İki kaynak vardır, ikisini de `logo_uret.py` yazar:

* **16, 24, 32 px — elle çizilmiş kesimler** (`kutuphane-defteri-16/24/32.png`).
  Bu betik onlara DOKUNMAZ; boyutlarını denetler ve `.ico`'ya aynen koyar.
* **48 px ve üstü — ana çizim** (`kutuphane-defteri-logo.png`). Karo görünür
  sınırına kırpılır, tam piksele oturan boyuta LANCZOS ile küçültülür ve kenar
  boşluğuyla ortalanır; karonun kenarı böylece yarım piksele düşmez.

Kenar boşluğu bütün boyutlarda tek kuraldır (gerekçesi `logo_uret.py`
başlığında): karo, tuvalin kenarına ⌈boyut/32⌉ px saydam boşluk bırakır; elle
çizilmiş 16 px kesim boşluksuzdur.

`.ico`: 16, 24, 32, 48, 64, 128, 256 — her boyut KENDİ karesiyle yazılır
(Pillow `append_images`); Pillow hiçbir boyutu kendisi küçültmez. Betik dosyayı
yazdıktan sonra yeniden açar ve her karenin aynı boydaki PNG ile piksel piksel
aynı olduğunu denetler; tutmazsa hata verir.

Ön yüzün `frontend/public/app-logo.png`'si (192 px; favicon ve kenar çubuğu)
da ana çizimden aynı kuralla üretilir.

**okulapp.org proje görseli** (site deposunda `public/kutuphane-defteri.png`,
başlıkta 42 px) varsayılan koşuda YAZILMAZ: site ayrı depodur ve kendi alanına
yalnız site adımında yazılır (`docs/site-icerigi.md` §7). Ölçüsü programın
türediği kardeş sınav programının site görseliyle aynıdır (256 px, 15 px saydam
pay; görünür kutu 15..241), kaynağı yine depodaki ana çizimdir:

    docker compose run --rm -w /repo -v "<okulapp.org>/public:/site" backend \
        python packaging/ikonlar/ikon_uret.py --site /site/kutuphane-defteri.png
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import IcoImagePlugin, Image

OUTPUT_DIR = Path(__file__).resolve().parent
MASTER_SOURCE = OUTPUT_DIR / "kutuphane-defteri-logo.png"
FRONTEND_TARGET = OUTPUT_DIR.parents[1] / "frontend" / "public" / "app-logo.png"
FRONTEND_SIZE = 192
#: `logo_uret.py`'nin elle çizdiği boyutlar — bu betik yalnız okur.
HAND_DRAWN_SIZES = (16, 24, 32)
#: Ana çizimden türetilen boyutlar.
MASTER_SIZES = (48, 64, 128, 256, 512)
PNG_SIZES = HAND_DRAWN_SIZES + MASTER_SIZES
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
#: okulapp.org proje görseli: kardeş sınav programının site görseliyle aynı boyut ve pay.
SITE_SIZE = 256
SITE_MARGIN = 15


def edge_margin(size: int) -> int:
    """Karonun tuval kenarına bıraktığı saydam boşluk (px): ⌈boyut/32⌉, 16'da 0."""
    return 0 if size <= 16 else math.ceil(size / 32)


def png_path(size: int) -> Path:
    return OUTPUT_DIR / f"kutuphane-defteri-{size}.png"


def load_tile() -> Image.Image:
    """Ana çizimin karosu: saydam kenar boşluğu kırpılmış hâli."""
    image = Image.open(MASTER_SOURCE).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError(f"Logo tamamen saydam: {MASTER_SOURCE}")
    return image.crop(bbox)


def from_master(tile: Image.Image, size: int, margin: int | None = None) -> Image.Image:
    """Ana çizimden `size` px kesim: karo tam piksele küçültülür, boşlukla ortalanır.

    `margin` verilmezse kenar boşluğu kuralı uygulanır (`edge_margin`); kendi
    payını yalnız site görseli verir (`site_image`).
    """
    if margin is None:
        margin = edge_margin(size)
    inner = size - 2 * margin
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(tile.resize((inner, inner), Image.Resampling.LANCZOS), (margin, margin))
    return canvas


def site_image(tile: Image.Image) -> Image.Image:
    """okulapp.org proje görseli: 256 px, 15 px saydam pay (modül belgesi)."""
    return from_master(tile, SITE_SIZE, SITE_MARGIN)


def load_hand_drawn(size: int) -> Image.Image:
    """`logo_uret.py`'nin yazdığı elle çizilmiş kesim (boyutu denetlenir)."""
    path = png_path(size)
    if not path.is_file():
        raise RuntimeError(f"Elle çizilmiş kesim yok, önce logo_uret.py koşulur: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != (size, size):
        raise RuntimeError(f"{path.name} {image.size} boyutunda; {size}×{size} bekleniyordu")
    return image


def write_ico(target: Path, frames: dict[int, Image.Image]) -> None:
    """`.ico`'yu her boyut kendi karesiyle yazar ve yeniden açıp denetler."""
    largest = frames[max(ICO_SIZES)]
    others = [frames[size] for size in ICO_SIZES if size != max(ICO_SIZES)]
    largest.save(
        target,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=others,
    )
    with Image.open(target) as ico:
        if not isinstance(ico, IcoImagePlugin.IcoImageFile):
            raise RuntimeError(f".ico olarak açılamadı: {target}")
        found = sorted(width for width, _ in ico.ico.sizes())
        if found != sorted(ICO_SIZES):
            raise RuntimeError(f".ico boyutları beklenenden farklı: {found}")
        for size in ICO_SIZES:
            frame = ico.ico.getimage((size, size)).convert("RGBA")
            if frame.tobytes() != frames[size].tobytes():
                raise RuntimeError(f".ico'daki {size} px kare PNG kesimiyle aynı değil")


def generate() -> list[Path]:
    """Tüm ikon dosyalarını yazar ve yollarını döndürür."""
    tile = load_tile()
    frames = {size: load_hand_drawn(size) for size in HAND_DRAWN_SIZES}
    written: list[Path] = []

    for size in MASTER_SIZES:
        frames[size] = from_master(tile, size)
        target = png_path(size)
        frames[size].save(target, format="PNG", optimize=True)
        written.append(target)

    ico = OUTPUT_DIR / "kutuphane-defteri.ico"
    write_ico(ico, frames)
    written.append(ico)

    FRONTEND_TARGET.parent.mkdir(parents=True, exist_ok=True)
    from_master(tile, FRONTEND_SIZE).save(FRONTEND_TARGET, format="PNG", optimize=True)
    written.append(FRONTEND_TARGET)
    return written


def write_site_image(target: Path) -> Path:
    """Site görselini `target`'a yazar; depodaki dosyalara dokunmaz."""
    site_image(load_tile()).save(target, format="PNG", optimize=True)
    return target


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Uygulama ikonlarını üretir.")
    parser.add_argument(
        "--site",
        type=Path,
        metavar="DOSYA",
        help="yalnız okulapp.org proje görselini bu dosyaya yazar (depoya dokunmaz)",
    )
    args = parser.parse_args()
    paths = [write_site_image(args.site)] if args.site is not None else generate()
    for path in paths:
        # Betik yalnız elle çalıştırılır; çıktı listesi bilinçli olarak yazılır.
        sys.stderr.write(f"yazıldı: {path}\n")
