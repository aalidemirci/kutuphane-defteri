#!/usr/bin/env bash
# =============================================================================
# Ekran görüntüleri — okulapp.org program sayfası için (UYDURMA veriyle)
# =============================================================================
# Tek komut, beş adım; hepsi Docker'da, host'a Python/Node kurulmaz:
#   1. ön yüz derlemesi (frontend/dist — programın sunduğu arayüz);
#   2. geçici Playwright imajı (Microsoft'un resmî imajı + playwright paketi + Inter ve
#      DejaVu yazı tipleri). Depo bağımlılığı DEĞİLDİR: requirements'a, spec'e, lisans listesine
#      girmez; yalnız bu betiğin yerel imajıdır (`docker rmi kd-ekran-playwright:…`);
#   3. backend kabında program: kurulum + e-Okul listeleri + katalog (deneme verisi
#      üreticisi) + Eylül'ün ödünç/iade akışı, yönetim sunucusu 127.0.0.1'de (oturum
#      belirteçli), Ağ Kataloğu 8765'te (`ekran_sunucusu.py`);
#   4. Playwright kabı AYNI kabın ağ ad alanında görüntüleri alır (`ekran_cekimi.py`);
#      dışarıya hiçbir port açılmaz;
#   5. PNG → WebP (1280×800, `webp_cevir.py`, backend kabında Pillow).
#
#     bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh            # site görüntüleri
#     bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh --kesif    # bütün ekranlar, 1x
#     bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh --sahne katalog
#     KD_EKRAN_DERLE=0 bash scripts/ekran_goruntuleri/ekran_goruntuleri.sh   # derleme yok
#
# Çıktı: dist/ekran-goruntuleri/{png,webp}/ (dist/ .gitignore'dadır). Veri dizini kabın
# /tmp'sindedir ve kapla silinir; depoya veri girmez. İlk koşu Playwright imajını indirir
# (ağ ister, ~3,5 GB); sonraki koşular yerel imajı kullanır.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

CIKTI="dist/ekran-goruntuleri"
AD="kd-ekran"
PW_SURUM="1.49.1"
PW_TABAN="mcr.microsoft.com/playwright/python:v${PW_SURUM}-noble"
PW_IMAJ="kd-ekran-playwright:${PW_SURUM}"
# Git Bash (Windows) bağlama yolu için sürücü harfli yol verir; Linux'ta düz pwd.
KOK="$(pwd -W 2>/dev/null || pwd)"

temizle() {
  docker rm -f "$AD" >/dev/null 2>&1 || true
  rm -f "$CIKTI/durum.json" "$CIKTI/bitti"
}
trap temizle EXIT
temizle
rm -rf "$CIKTI"
mkdir -p "$CIKTI"

if [ "${KD_EKRAN_DERLE:-1}" = "1" ]; then
  echo "== 1/5 ön yüz derlemesi"
  docker compose run --rm -T frontend npm run build >/dev/null
else
  echo "== 1/5 ön yüz derlemesi atlandı (KD_EKRAN_DERLE=0; frontend/dist kullanılır)"
fi

echo "== 2/5 geçici Playwright imajı ($PW_IMAJ)"
docker build -q -t "$PW_IMAJ" - >/dev/null <<EOF
FROM $PW_TABAN
RUN pip install --no-cache-dir --break-system-packages playwright==$PW_SURUM \\
 && apt-get update \\
 && apt-get install -y --no-install-recommends fonts-inter fonts-dejavu-core \\
 && rm -rf /var/lib/apt/lists/*
EOF

echo "== 3/5 program + uydurma veri (backend kabı $AD)"
docker compose run -d --name "$AD" -e KD_DEBUG=0 -w /repo backend \
  python scripts/ekran_goruntuleri/ekran_sunucusu.py --cikti "$CIKTI" >/dev/null
for _ in $(seq 1 600); do
  if docker logs "$AD" 2>&1 | grep -q "EKRAN_HAZIR"; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$AD" 2>/dev/null)" != "true" ]; then
    docker logs "$AD" >&2
    echo "HATA: program kabı durdu" >&2
    exit 1
  fi
  sleep 1
done
docker logs "$AD" 2>&1 | grep -E "^(KURULUM|AKTARIM|UYELIK|TESLIM|DOLASIM|POPULER|SAYIM|TOHUM|KATALOG|EKRAN_HAZIR)"

echo "== 4/5 görüntüler (Playwright, $AD ağında)"
docker run --rm --network "container:$AD" -v "$KOK:/repo" -w /repo \
  -e LANG=tr_TR.UTF-8 -e LANGUAGE=tr "$PW_IMAJ" \
  python scripts/ekran_goruntuleri/ekran_cekimi.py --cikti "$CIKTI" "$@"

if [ -d "$CIKTI/png" ]; then
  echo "== 5/5 WebP"
  docker compose run --rm -T -w /repo backend \
    python scripts/ekran_goruntuleri/webp_cevir.py --kaynak "$CIKTI/png" --hedef "$CIKTI/webp"
fi
echo "Çıktı: $CIKTI"
