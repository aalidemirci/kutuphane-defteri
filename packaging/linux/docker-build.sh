#!/usr/bin/env bash
# =============================================================================
# packaging/linux/docker-build.sh — Linux paketlerini Docker içinde üretir
# =============================================================================
# Host'a hiçbir şey kurulmaz (tasarım §1: geliştirme yalnız Docker'da).
# Derleme kabı BİLİNÇLİ olarak `python:3.12-bullseye`'dır: glibc 2.31 = Pardus
# 21 tabanı.
# Daha yeni bir tabanda derlenen paket Pardus 21'de açılmaz.
#
# Kullanım (depo kökünden):
#     bash packaging/linux/docker-build.sh          # Qt dahil (gerçek paket)
#     KD_WITH_QT=0 bash packaging/linux/docker-build.sh   # hızlı doğrulama
#
# Çıktılar: dist/cikti/{*.deb, *.tar.gz, SHA256SUMS.txt, pdf-duman.pdf}
# =============================================================================
set -euo pipefail

# Git Bash (Windows) MSYS yol dönüşümü `-w /repo` gibi konteyner yollarını
# Windows yoluna çevirip koşuyu kırar (gates.sh ile aynı koruma).
export MSYS_NO_PATHCONV=1

DEPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAJ="${KD_BUILD_IMAGE:-python:3.12-bullseye}"

echo "== derleme kabı: $IMAJ (Qt: ${KD_WITH_QT:-1})"
docker run --rm \
    -v "$DEPO:/repo" \
    -w /repo \
    -e "KD_WITH_QT=${KD_WITH_QT:-1}" \
    -e "KD_SKIP_PIP=${KD_SKIP_PIP:-0}" \
    -e "HOST_UID=$(id -u)" \
    -e "HOST_GID=$(id -g)" \
    "$IMAJ" \
    bash /repo/packaging/linux/build.sh
