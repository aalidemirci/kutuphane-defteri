#!/usr/bin/env bash
# =============================================================================
# packaging/linux/build.sh — Linux paketlerini üretir (.deb + taşınabilir .tar.gz)
# =============================================================================
# BU BETİK KONTEYNER İÇİNDE ÇALIŞIR. Doğru kullanım host'tan:
#
#     bash packaging/linux/docker-build.sh
#
# Doğrudan çalıştırmak yalnız `python:3.12-bullseye` (veya Debian 11 tabanlı)
# bir kap içinde anlamlıdır. KS kararı (K6): derleme YALNIZ bullseye'da yapılır
# çünkü glibc 2.31, Pardus 21'in tabanıdır — daha yeni bir glibc'de derlenen
# paket Pardus 21'de açılmaz ("GLIBC_2.34 not found").
#
# Adımlar:
#   1. Sistem bağımlılıkları (yalnız DERLEME için; pakete girmez)
#   2. Python bağımlılıkları
#   3. PyInstaller onedir
#   4. Duman testleri: `--bagimlilik-duman` (hiddenimports) + `--autotest` (çıkış 0)
#      + `--pdf-duman` (evrak şablonu + Türkçe PDF)
#   5. .deb sargısı (dpkg-deb; ufw profili + firewalld servis tanımı dahil)
#   6. Taşınabilir .tar.gz (+ kur.sh)
#   7. SHA256SUMS.txt
#
# Ortam değişkenleri:
#   KD_WITH_QT=0  → PySide6/QtWebEngine paketlenmez (hızlı doğrulama derlemesi;
#                   pencere açılmaz, yalnız `--autotest`/`--pdf-duman` çalışır)
#   KD_SKIP_PIP=1 → pip adımını atlar (bağımlılıklar zaten kurulu)
# =============================================================================
set -euo pipefail

DEPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DEPO"

QT_ILE="${KD_WITH_QT:-1}"
CIKTI="$DEPO/dist/cikti"
# Ara dizinler platforma özel (build.ps1 ile çarpışma önlenir); nihai
# artefaktlar iki platformda da dist/cikti'ye düşer.
PAKET_KOKU="$DEPO/dist/paket-linux"
CALISMA="$DEPO/dist/_build-linux"
GECICI_PAKETLEME="$(mktemp -d)"
trap 'rm -rf "$GECICI_PAKETLEME"' EXIT
DEB_AGACI="$GECICI_PAKETLEME/deb"

SURUM="$(tr -d '[:space:]' < "$DEPO/VERSION")"
# Debian sürüm dizgisinde "-" yukarı akış/revizyon ayırıcısıdır; ön-sürüm
# işareti "~" ile verilir ve "~" kesin sürümden ÖNCE sıralanır (2026.7.0~dev
# < 2026.7.0). Bu sayede dev paketin üstüne kesin sürüm yükseltme sayılır.
DEB_SURUM="${SURUM/-/\~}"
DEB_ADI="kutuphane-defteri_${DEB_SURUM}_amd64.deb"
TAR_ADI="kutuphane-defteri-${SURUM}-linux-x64.tar.gz"

# .deb bağımlılıkları (KS hattı, K17). Pango/glib/fontconfig Linux'ta BUNDLE
# EDİLMEZ (sistem sürümüyle çakışır); dağıtımın kendi paketleri kullanılır.
# Hepsi Debian 11 ve 12 ana deposunda mevcuttur.
DEPENDS_TEMEL="libpango-1.0-0, libpangoft2-1.0-0, libharfbuzz0b, libfontconfig1, libglib2.0-0, fonts-dejavu-core"
# Qt WebEngine'in sistemden beklediği X/GL/ses kütüphaneleri (PySide6 tekerleği
# Qt'nin kendisini taşır, ama bu sistem kütüphanelerini taşımaz). Liste
# 23.09.2026'da bullseye kabında `ldd` ile doğrulandı; Qt5'ten Qt6'ya geçişte
# iki paket EKLENDİ:
#   libxkbfile1    ← libQt6WebEngineCore (yoksa import "libxkbfile.so.1"le düşer)
#   libxcb-cursor0 ← libQt6XcbQpa / libqxcb (yoksa pencere hiç açılmaz)
# İkisi de Debian 11 ve 12 ana deposunda vardır.
# `libcups2` BİLEREK YOK: yalnız Qt'nin yazdırma eklentisi ister, evrak
# WeasyPrint'ten basılır (spec'te `QtPrintSupport` de paketlenmez).
DEPENDS_QT="libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0, libxkbfile1, libdbus-1-3, libnss3, libnspr4, libxcomposite1, libxdamage1, libxrandr2, libxtst6, libxi6, libasound2, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libxcb-cursor0"

APT_TEMEL="libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 libglib2.0-0 fonts-dejavu-core binutils"
# libharfbuzz-subset0 Debian 11'DE YOKTUR (bookworm ile geldi). WeasyPrint font
# alt-kümeleme için arar, bulamazsa fontu tam gömer — PDF büyür ama üretilir.
# Bu yüzden hem burada hem .deb Depends'inde ZORUNLU DEĞİLDİR (KS hattının
# bağımlılık listesiyle birebir uyumlu).
APT_ISTEGE_BAGLI="libharfbuzz-subset0"
APT_QT="libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libxkbfile1 libdbus-1-3 libnss3 libnspr4 libxcomposite1 libxdamage1 libxrandr2 libxtst6 libxi6 libasound2 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libxcb-cursor0"

bilgi() { echo "== $*"; }

# apt komutları ayna tutarsızlığına karşı sarmalanır (gerekçe apt_dene.sh
# başlığında: 04.09.2026'da KS'de bir sürüm koşusu tam burada 404 ile düştü).
. "$(dirname "${BASH_SOURCE[0]}")/apt_dene.sh"

# --- 1. Sistem bağımlılıkları (derleme kabında) ------------------------------
bilgi "sistem bağımlılıkları"
export DEBIAN_FRONTEND=noninteractive
# shellcheck disable=SC2086
apt_dene apt-get install -y -qq --no-install-recommends $APT_TEMEL
# İSTEĞE BAĞLI paket YENİDEN DENENMEZ: yokluğu beklenen durumdur (Debian
# 11'de libharfbuzz-subset0 hiç yok), sarmal onu üç kez boşuna arardı.
# shellcheck disable=SC2086
apt-get install -y -qq --no-install-recommends $APT_ISTEGE_BAGLI 2>/dev/null || \
    echo "   (libharfbuzz-subset0 bu dağıtımda yok — atlandı)"
if [ "$QT_ILE" != "0" ]; then
    # PyInstaller PySide6'yı ÇÖZÜMLEMEK için import eder; libGL olmadan import
    # patlar ("libGL.so.1: cannot open shared object file"), libxkbfile1
    # olmadan da QtWebEngineCore açılmaz.
    # shellcheck disable=SC2086
    apt_dene apt-get install -y -qq --no-install-recommends $APT_QT
fi

# --- 2. Python bağımlılıkları ------------------------------------------------
if [ "${KD_SKIP_PIP:-0}" != "1" ]; then
    bilgi "python bağımlılıkları"
    pip install --no-cache-dir -q -r "$DEPO/backend/requirements.txt"
    PAKETLEME_GEREKSINIM="$DEPO/packaging/requirements-paketleme.txt"
    if [ "$QT_ILE" = "0" ]; then
        # Qt satırlarını atla (PySide6 indirmesi ~400 MB, doğrulama
        # derlemesinde gereksiz). Ad değişirse burası da değişir —
        # `test_spec_kapsami.py::test_paketleme_platform_isaretleri_bilinen_kumede`
        # linux işaretli paket kümesini kapıya bağlar.
        PAKETLEME_GEREKSINIM="$(mktemp)"
        grep -v -E '^(QtPy|PySide6)' \
            "$DEPO/packaging/requirements-paketleme.txt" > "$PAKETLEME_GEREKSINIM"
    fi
    pip install --no-cache-dir -q -r "$PAKETLEME_GEREKSINIM"
fi

# --- 3. Ön koşul: derlenmiş arayüz ------------------------------------------
if [ ! -f "$DEPO/frontend/dist/index.html" ]; then
    echo "HATA: frontend/dist/index.html yok. Önce arayüzü derleyin:" >&2
    echo "      docker compose run --rm frontend npm run build" >&2
    exit 1
fi

# --- 4. PyInstaller ----------------------------------------------------------
bilgi "PyInstaller onedir (Qt: $QT_ILE)"
rm -rf "$PAKET_KOKU" "$CALISMA" "$DEB_AGACI"
mkdir -p "$CIKTI"
KD_WITH_QT="$QT_ILE" pyinstaller \
    --noconfirm --clean --log-level WARN \
    --distpath "$PAKET_KOKU" \
    --workpath "$CALISMA" \
    "$DEPO/packaging/pyinstaller/kutuphane_defteri.spec"

UYGULAMA="$PAKET_KOKU/kutuphane-defteri/kutuphane-defteri"
[ -x "$UYGULAMA" ] || { echo "HATA: çalıştırılabilir üretilmedi: $UYGULAMA" >&2; exit 1; }

bilgi "paket kişisel veri sızıntısı denetimi"
python "$DEPO/packaging/veri_sizintisi.py" "$PAKET_KOKU/kutuphane-defteri"

# --- 4b. Qt zinciri pakete girdi mi? -----------------------------------------
# Linux Qt zincirinin `--bagimlilik-duman` karşılığı YOKTUR: duman kipi
# `KD_WITH_QT=0` derlemesinde de koştuğu için Qt modülleri o listeye bilerek
# girmez (giris.py::DESKTOP_RUNTIME_MODULES açıklaması). Kapı bu yüzden
# burada, dosya varlığıyla kurulur. QtWebEngineProcess yardımcı süreci
# eksikse program AÇILIR ama pencere beyaz kalır — sahada değil, burada
# yakalanmalı.
if [ "$QT_ILE" != "0" ]; then
    bilgi "Qt zinciri denetimi (PySide6 + QtWebEngineProcess)"
    eksik=0
    for parca in QtWebEngineProcess libQt6WebEngineCore.so.6 libQt6Widgets.so.6; do
        if [ -z "$(find "$PAKET_KOKU/kutuphane-defteri" -name "$parca" -print -quit)" ]; then
            echo "HATA: Qt parçası pakete girmedi: $parca" >&2
            eksik=1
        fi
    done
    [ "$eksik" = "0" ] || exit 1
fi

# --- 5. Duman testleri (paketlenmiş çalıştırılabilir üzerinden) --------------
bilgi "duman testi: --bagimlilik-duman (hiddenimports)"
"$UYGULAMA" --bagimlilik-duman

bilgi "duman testi: --pdf-duman (evrak şablonu + Türkçe PDF)"
"$UYGULAMA" --pdf-duman "$CIKTI/pdf-duman.pdf"

bilgi "duman testi: --autotest"
GECICI_VERI="$(mktemp -d)"
KD_APP_HOME="$GECICI_VERI" "$UYGULAMA" --autotest
rm -rf "$GECICI_VERI"

# --- 6. .deb sargısı ---------------------------------------------------------
bilgi ".deb üretimi ($DEB_SURUM)"
mkdir -p "$DEB_AGACI/opt" "$DEB_AGACI/usr/bin" "$DEB_AGACI/usr/share/applications" "$DEB_AGACI/DEBIAN"
cp -a "$PAKET_KOKU/kutuphane-defteri" "$DEB_AGACI/opt/kutuphane-defteri"
ln -sf /opt/kutuphane-defteri/kutuphane-defteri "$DEB_AGACI/usr/bin/kutuphane-defteri"
cp "$DEPO/packaging/linux/kutuphane-defteri.desktop" "$DEB_AGACI/usr/share/applications/"
# Ağ Kataloğu (tasarım §5.7): ufw uygulama profili ve firewalld servis tanımı
# bırakılır, kural AÇILMAZ; komutu Ağ Doktoru gösterir.
mkdir -p "$DEB_AGACI/etc/ufw/applications.d" "$DEB_AGACI/usr/lib/firewalld/services"
install -m 0644 "$DEPO/packaging/linux/ufw-kutuphane-defteri" \
    "$DEB_AGACI/etc/ufw/applications.d/kutuphane-defteri"
install -m 0644 "$DEPO/packaging/linux/firewalld-kutuphane-defteri.xml" \
    "$DEB_AGACI/usr/lib/firewalld/services/kutuphane-defteri.xml"

for boyut in 16 24 32 48 64 128 256; do
    hedef="$DEB_AGACI/usr/share/icons/hicolor/${boyut}x${boyut}/apps"
    mkdir -p "$hedef"
    cp "$DEPO/packaging/ikonlar/kutuphane-defteri-${boyut}.png" "$hedef/kutuphane-defteri.png"
done

DEPENDS="$DEPENDS_TEMEL"
if [ "$QT_ILE" != "0" ]; then
    DEPENDS="$DEPENDS, $DEPENDS_QT"
fi
BOYUT_KB="$(du -sk "$DEB_AGACI" | cut -f1)"

sed -e "s|@VERSION@|${DEB_SURUM}|" \
    -e "s|@SIZE@|${BOYUT_KB}|" \
    -e "s|@DEPENDS@|${DEPENDS}|" \
    "$DEPO/packaging/linux/debian-control.tmpl" > "$DEB_AGACI/DEBIAN/control"
install -m 0755 "$DEPO/packaging/linux/postinst" "$DEB_AGACI/DEBIAN/postinst"
install -m 0755 "$DEPO/packaging/linux/prerm" "$DEB_AGACI/DEBIAN/prerm"
chmod 0755 "$DEB_AGACI/DEBIAN"

dpkg-deb --root-owner-group --build "$DEB_AGACI" "$CIKTI/$DEB_ADI"

# --- 7. Taşınabilir .tar.gz --------------------------------------------------
bilgi "taşınabilir arşiv"
TAR_KOKU="$GECICI_PAKETLEME/tar"
TAR_AGACI="$TAR_KOKU/kutuphane-defteri-${SURUM}"
mkdir -p "$TAR_AGACI"
cp -a "$PAKET_KOKU/kutuphane-defteri" "$TAR_AGACI/uygulama"
install -m 0755 "$DEPO/packaging/linux/kur.sh" "$TAR_AGACI/kur.sh"
install -m 0755 "$DEPO/packaging/linux/kaldir.sh" "$TAR_AGACI/kaldir.sh"
cp "$DEPO/packaging/linux/BENIOKU.txt" "$TAR_AGACI/BENIOKU.txt"
cp "$DEPO/packaging/linux/kutuphane-defteri.desktop" "$TAR_AGACI/"
mkdir -p "$TAR_AGACI/ikonlar"
cp "$DEPO/packaging/ikonlar/kutuphane-defteri-"*.png "$TAR_AGACI/ikonlar/"
tar -czf "$CIKTI/$TAR_ADI" -C "$TAR_KOKU" "kutuphane-defteri-${SURUM}"

# --- 8. Sağlama toplamları ---------------------------------------------------
bilgi "SHA256SUMS.txt"
( cd "$CIKTI" && sha256sum "$DEB_ADI" "$TAR_ADI" > SHA256SUMS.txt )

# --- 9. Dosya sahipliğini host kullanıcısına geri ver ------------------------
# Kap root olarak çalışır; aksi hâlde host'ta `dist/` root'a ait kalır ve
# sonraki koşu silemez.
if [ -n "${HOST_UID:-}" ] && [ -n "${HOST_GID:-}" ]; then
    chown -R "$HOST_UID:$HOST_GID" "$DEPO/dist" || true
fi

bilgi "bitti — çıktılar: $CIKTI"
ls -la "$CIKTI"
