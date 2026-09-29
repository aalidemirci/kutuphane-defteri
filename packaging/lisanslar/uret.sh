#!/usr/bin/env bash
# =============================================================================
# packaging/lisanslar/uret.sh — THIRD_PARTY_LICENSES/ dizinini yeniden üretir
# =============================================================================
# Ne zaman koşulur: bir Python ya da npm bağımlılığı eklendiğinde, sürümü
# değiştiğinde ya da kaldırıldığında (kapı testi `packaging/tests/
# test_lisans_kapisi.py` listeyle gereksinim dosyaları ayrışınca kırılır).
#
# İki adım, ikisi de Docker'da (host'a hiçbir şey kurulmaz):
#   1. Ön yüz kabı: Vite derlemesi yazmadan koşar, çıktıya giren npm paketlerini
#      ve lisans metinlerini JSON olarak verir (on_yuz_paketleri.mjs).
#   2. Backend kabı: Python bağımlılık kapanışını iki platform için çözer, lisans
#      dosyalarını toplar, dizini baştan yazar (lisanslar.py uret). AĞ GEREKİR:
#      yalnız paket ortamında kurulan dağıtımlar (pywebview, pystray, pythonnet,
#      PySide6 …) PyPI'dan okunur; WebView2 SDK lisansı NuGet'ten alınır.
#
# Kullanım (depo kökünden):  bash packaging/lisanslar/uret.sh
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1

DEPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DEPO"

ARA="dist/lisans"
mkdir -p "$ARA"

echo "== ön yüz: çıktıya giren npm paketleri"
docker compose run --rm -T frontend node --input-type=module \
    < packaging/lisanslar/on_yuz_paketleri.mjs > "$ARA/on-yuz.json"
# `docker compose run` çıkış kodunu zaman zaman yutar (scripts/gates.sh): JSON'un
# gerçekten üretildiği ayrıca denetlenir.
grep -q '"paketler"' "$ARA/on-yuz.json" || { echo "HATA: ön yüz listesi üretilmedi" >&2; exit 1; }

echo "== Python bağımlılıkları + lisans dosyaları"
docker compose run --rm -T -w /repo backend \
    python packaging/lisanslar/lisanslar.py uret --on-yuz "/repo/$ARA/on-yuz.json"

echo "== bitti: THIRD_PARTY_LICENSES/ (git diff ile gözden geçirin)"
