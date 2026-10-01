"""Ekran görüntülerini (PNG, 2x) site için WebP'ye çevirir (backend kabında; Pillow).

Pillow programın zaten bağımlılığıdır (WeasyPrint'in bağımlılığı); yeni paket yoktur.
Varsayılan ölçü, okulapp.org'daki kardeş program sayfalarının görüntüleriyle aynıdır:
1280×800 (16:10; oradaki dosyalar 70-80 KB). 2880×1800'lük kayıttan LANCZOS ile
küçültülür, yazı 1x kayda göre daha keskin kalır; kalite 90 küçük yazıyı bulanıklaştırmaz
ve dosyalar aynı boy aralığında kalır.

    python scripts/ekran_goruntuleri/webp_cevir.py --kaynak dist/ekran-goruntuleri/png \
        --hedef dist/ekran-goruntuleri/webp
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

GENISLIK = 1280
YUKSEKLIK = 800
KALITE = 90


def cevir(kaynak: Path, hedef: Path, *, genislik: int, yukseklik: int, kalite: int) -> int:
    hedef.mkdir(parents=True, exist_ok=True)
    pngler = sorted(kaynak.glob("ekran-*.png"))
    if not pngler:
        print(f"HATA: {kaynak} içinde ekran-*.png yok", file=sys.stderr)
        return 1
    for png in pngler:
        with Image.open(png) as ham:
            resim = ham.convert("RGB").resize((genislik, yukseklik), Image.Resampling.LANCZOS)
        yol = hedef / f"{png.stem}.webp"
        resim.save(yol, "WEBP", quality=kalite, method=6)
        print(f"WEBP {yol.name} {genislik}x{yukseklik} {yol.stat().st_size // 1024} KB", flush=True)
    return 0


def main(argv: list[str]) -> int:
    ayri = argparse.ArgumentParser(description="PNG ekran görüntülerini WebP'ye çevirir")
    ayri.add_argument("--kaynak", type=Path, required=True)
    ayri.add_argument("--hedef", type=Path, required=True)
    ayri.add_argument("--genislik", type=int, default=GENISLIK)
    ayri.add_argument("--yukseklik", type=int, default=YUKSEKLIK)
    ayri.add_argument("--kalite", type=int, default=KALITE)
    s = ayri.parse_args(argv)
    return cevir(s.kaynak, s.hedef, genislik=s.genislik, yukseklik=s.yukseklik, kalite=s.kalite)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
