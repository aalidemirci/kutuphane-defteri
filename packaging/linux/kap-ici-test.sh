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
#   4b. `--dagitim-duman kurulu` → dpkg ile kurulan program kendini KURULU sayar
#      (KB-2: taşınabilir arşivde Ağ Kataloğu açılmaz; ölçüt desktop/dagitim.py)
#   5. Dosya yerleşimi (menü kaydı, ikon, /usr/bin bağlantısı) ve lisanslar
#      (DEP-5 copyright, THIRD_PARTY_LICENSES, readline ve Qt'nin yalnız GPL'li
#      modülleri yok, Windows'a özgü pywebview dosyaları yok)
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

echo "== lisans dosyaları (DEP-5 copyright, THIRD_PARTY_LICENSES — F12, TB28)"
DOC=/usr/share/doc/kutuphane-defteri
test -f "$DOC/copyright"
grep -q '^Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/' "$DOC/copyright"
test -f /opt/kutuphane-defteri/LICENSE.txt
test -f /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/BENIOKU.txt
test -f /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/bilesenler.json
test -f "$DOC/THIRD_PARTY_LICENSES/paket-icerigi.txt"
test -d /opt/kutuphane-defteri/THIRD_PARTY_LICENSES/yerel-kutuphaneler
# Yalnız GPL'li readline pakete girmemeli (spec `excludes`; derleme de denetler).
if find /opt/kutuphane-defteri -name 'libreadline*' | grep -q .; then
    echo "HATA: libreadline pakette (GPL-3.0)" >&2
    exit 1
fi
# Qt'nin yalnız GPL-3.0 ile sunulan modülleri pakete girmemeli (spec `qt_gpl_suz`;
# derleme de denetler; liste `lisanslar.py::QT_YALNIZ_GPL_MODULLER` ile aynı — kapı
# testi eşitliği sınar).
QT_GPL_MODULLER='Bodymovin|Charts|Coap|DataVisualization|Graphs|Grpc|HttpServer|Mqtt|NetworkAuth|QmlCompiler|Quick3D|QuickTimeline|VirtualKeyboard|WaylandCompositor'
QT_GPL_QML='Qt/labs/lottieqt|QtCharts|QtCoap|QtDataVisualization|QtGraphs|QtGrpc|QtHttpServer|QtMqtt|QtNetworkAuth|QtQuick/Timeline|QtQuick/VirtualKeyboard|QtQuick3D|QtWayland/Compositor'
QT_GPL_BULGU="$(find /opt/kutuphane-defteri -regextype posix-extended \( \
    -regex ".*/(lib)?Qt6(${QT_GPL_MODULLER})[^/]*" \
    -o -regex ".*/Qt(${QT_GPL_MODULLER})[A-Za-z0-9_]*\.(abi3\.so|so|pyi)" \
    -o -regex ".*/qml/(${QT_GPL_QML})(/.*)?" \) -print | head -3)"
if [ -n "$QT_GPL_BULGU" ]; then
    echo "HATA: Qt'nin yalnız GPL'li modül dosyaları pakette:" >&2
    echo "$QT_GPL_BULGU" >&2
    exit 1
fi
# WebView2 SDK DLL'leri ve pywebview'ın Android arşivi Linux paketine girmemeli.
if find /opt/kutuphane-defteri -path '*webview*' \( -name '*.dll' -o -name '*.jar' \) | grep -q .; then
    echo "HATA: Windows'a özgü pywebview dosyaları Linux paketinde" >&2
    exit 1
fi

echo "== --bagimlilik-duman (üçüncü taraf modüller pakette mi)"
kutuphane-defteri --bagimlilik-duman

echo "== --pdf-duman (evrak şablonu + Türkçe PDF + font doğrulaması)"
kutuphane-defteri --pdf-duman /tmp/duman.pdf
test -s /tmp/duman.pdf

echo "== --dagitim-duman (KB-2: gerçek dpkg kurulumunda program KURULU sayılır)"
# Taşınabilir arşivde Ağ Kataloğu açılmaz; ayrım paketli ikilinin sys.executable'ı ile
# dpkg listesinden yapılır (desktop/dagitim.py). /usr/bin bağlantısından ve /opt'taki
# dosyadan açılan program ikisi de kurulu sayılmalı; karşılığı build.sh'te.
kutuphane-defteri --dagitim-duman kurulu
/opt/kutuphane-defteri/kutuphane-defteri --dagitim-duman kurulu

echo "== --autotest (açılış zinciri; çıkış kodu 0 beklenir)"
kutuphane-defteri --autotest

echo "== ikinci --autotest (var olan veritabanı üzerinde)"
kutuphane-defteri --autotest

echo "== kaldırma"
dpkg -r kutuphane-defteri
test ! -e /opt/kutuphane-defteri
test ! -e /usr/bin/kutuphane-defteri

echo "TAMAM"
