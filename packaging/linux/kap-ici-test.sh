#!/usr/bin/env bash
# =============================================================================
# kap-ici-test.sh — TEMİZ bir Debian kabında .deb kurulum provası
# =============================================================================
# `test-kurulum.sh` tarafından debian:11 ve debian:12 kaplarının İÇİNDE
# çalıştırılır (tasarım §14 F12 "Pardus'ta aynı zincir" — Pardus 21 bullseye,
# Pardus 23 bookworm tabanlıdır).
#
# Sınananlar:
#   1. dpkg -i + apt-get -f install ile bağımlılıkların gerçekten çözülmesi
#   2. `--autotest` → ÇIKIŞ KODU 0 (açılış zinciri: kilit, yedek, göç, sunucu)
#   3. `--bagimlilik-duman` → üçüncü taraf modüller pakette mi (hiddenimports)
#   4. `--pdf-duman` → evrak taban şablonundan Türkçe PDF + pypdf ile geri okuma
#   5. Dosya yerleşimi (menü kaydı, ikon, /usr/bin bağlantısı)
#   6. Temiz kaldırma
# =============================================================================
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Yerelde `test-kurulum.sh` paketleri /paketler'e bağlar; CI'da artefakt başka
# bir dizine iner → PAKET_DIZINI ile geçersiz kılınır.
PAKET_DIZINI="${PAKET_DIZINI:-/paketler}"

echo "== dağıtım"
head -2 /etc/os-release

DEB="$(find "$PAKET_DIZINI" -maxdepth 1 -name '*.deb' | sort | head -1)"
[ -n "$DEB" ] || { echo "HATA: $PAKET_DIZINI içinde .deb yok" >&2; exit 1; }
echo "== paket: $DEB"

echo "== dpkg -i (bağımlılıklar eksik olabilir)"
dpkg -i "$DEB" || true

echo "== apt-get -f install (bağımlılık çözümü)"
# `apt_dene` her denemede önce `apt-get update` koşar; ayrı update adımı
# yoktur — ayna tutarsızlığında listeler tazelenip yeniden denenir.
. "$(dirname "${BASH_SOURCE[0]}")/apt_dene.sh"
apt_dene apt-get -f install -y -qq

echo "== paket durumu"
dpkg -s kutuphane-defteri | grep -E '^(Package|Version|Status|Depends)'

echo "== dosya yerleşimi"
test -x /opt/kutuphane-defteri/kutuphane-defteri
test -L /usr/bin/kutuphane-defteri
test -f /usr/share/applications/kutuphane-defteri.desktop
test -f /usr/share/icons/hicolor/48x48/apps/kutuphane-defteri.png

echo "== --bagimlilik-duman (üçüncü taraf modüller pakette mi)"
kutuphane-defteri --bagimlilik-duman

echo "== --pdf-duman (evrak şablonu + Türkçe PDF + font doğrulaması)"
kutuphane-defteri --pdf-duman /tmp/duman.pdf
test -s /tmp/duman.pdf

echo "== --autotest (açılış zinciri; çıkış kodu 0 beklenir)"
kutuphane-defteri --autotest

echo "== ikinci --autotest (var olan veritabanı üzerinde)"
kutuphane-defteri --autotest

echo "== kaldırma"
dpkg -r kutuphane-defteri
test ! -e /opt/kutuphane-defteri
test ! -e /usr/bin/kutuphane-defteri

echo "TAMAM"
