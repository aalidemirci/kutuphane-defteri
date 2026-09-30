#!/usr/bin/env bash
# =============================================================================
# packaging/r2-yukle.sh — yayın paketlerini indir.okulapp.org'a (Cloudflare R2)
# =============================================================================
# Kullanım: bash packaging/r2-yukle.sh <paket-dizini> <sürüm>
#           (sürüm etiketin `v`siz hâlidir: 2026.10.0-beta.1)
#
# R2 yüklemesinin TEK yeri; kova, önek, kovadaki adlar ve içerik türleri yalnız
# burada yazılıdır. İki yerden çağrılır:
#   * paketleme.yml `yayin` işi — GitHub Release'in hemen ardından;
#   * r2-yukle.yml — var olan bir Release'in dosyalarını, paketleri yeniden
#     üretmeden sonradan yüklemek için (secret'lar Release'ten sonra eklendiyse
#     ya da adım kırıldıysa; v2026.10.0-beta.1 R2'siz çıktı).
# Emsal DD hattındaki aynı adlı betiktir (28.09.2026'da uçtan uca yeşil); KD'de
# yüklemeden önceki denetim ve zorunlu kimlik kipi eklendi.
#
# Dizin, Release'e giden dosyaların kendisidir: dört paket + SHA256SUMS.txt.
# `.deb` adındaki `~` yayın işinin "SHA256SUMS.txt" adımında `.` yapılır ve
# özet o adları taşır; kovaya da Release'teki adlarla gider.
#
# Kimlik: CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID ortam değişkenleri.
# Token izni R2 **Admin Read & Write** olmalıdır. *Object Read & Write* YETMEZ:
# wrangler `r2 object put` Cloudflare REST API'siyle çalışır ve object-düzeyi
# token REST'te 403 (kod 10000 "Authentication error") ile reddedilir — DD
# hattında 28.09.2026'da yaşandı, KS aynı gün düzeltti
# (developers.cloudflare.com/r2/platform/troubleshooting).
# Kimlik yoksa:
#   * varsayılan: İŞ DURMAZ — sürüm ve dizin denetlenmeden uyarı basılır, 0 ile
#     çıkılır, paketler yalnız Release'te kalır (secret'ı olmayan bir çatalda da
#     sürüm çıkabilmeli; satır içi eski adımın davranışı);
#   * R2_KIMLIK_ZORUNLU=1 (r2-yukle.yml): hata — elle başlatılan yükleme işinin
#     hiçbir şey yüklemeden yeşil bitmesi yanıltıcı olurdu.
#
# Kimlik varken yüklemeden ÖNCE bütün dizin denetlenir; bir şey tutmazsa HİÇBİR
# dosya yüklenmez (yarım yükleme yok, adım kırmızı olur):
#   * SHA256SUMS.txt vardır ve `sha256sum --check` ile tutar (bozuk ya da eksik
#     indirilmiş dosya indirme alanına çıkmaz);
#   * her paket özette listelidir (özetsiz dosya yüklenmez);
#   * her dosyanın türü bilinir (yeni bir tür eşlemeye bilinçli eklenir);
#   * hiçbir paket wrangler'ın tek parça sınırını (300 MiB) aşmaz.
# Özet dosyası EN SON yüklenir: kovada özet görünüyorsa paketleri de oradadır.
# =============================================================================
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Kullanım: bash packaging/r2-yukle.sh <paket-dizini> <sürüm>" >&2
    exit 2
fi
DIZIN="$1"
SURUM="$2"
R2_KOVA="okulapp-indirme"
R2_ONEK="kutuphane-defteri"
OZET="SHA256SUMS.txt"
# wrangler `r2 object put` tek parçada yükler: en çok 300 MiB (Cloudflare "Upload
# objects": "up to 315 MB"). Üstü çok parçalı S3 yüklemesi ister (rclone, aws s3).
# v2026.10.0-beta.1'in en büyüğü Linux arşiviydi: 247.424.211 bayt (~236 MiB).
WRANGLER_AZAMI=$((300 * 1024 * 1024))

hata() {
    echo "::error::$*"
    exit 1
}

# Kimlik denetimi İLK iştir: kimlik yokken (varsayılan kip) yayın işi, satır içi
# eski adımda olduğu gibi hiçbir girdiye bakılmadan uyarıyla sürer. Sürüm ve dizin
# denetimleri yalnız yükleme yolundadır.
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] || [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
    if [ "${R2_KIMLIK_ZORUNLU:-0}" = "1" ]; then
        hata "CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID secret'ları tanımlı değil — hiçbir dosya yüklenmedi. Ekleme adımları: packaging/README.md \"R2 secret'ları\"."
    fi
    echo "::warning::CLOUDFLARE_API_TOKEN/ACCOUNT_ID tanımsız — R2 yüklemesi atlandı; paketler yalnız GitHub Release'te. Secret'lar eklenince: Actions → \"R2'ye yükle\" → etiket = v${SURUM}."
    exit 0
fi

# CalVer + isteğe bağlı ön sürüm eki (packaging/README.md "Sürüm"). Başında `v`
# kalırsa özet kovaya `SHA256SUMS-v….txt` adıyla giderdi.
if ! [[ "${SURUM}" =~ ^20[0-9]{2}\.[0-9]{1,2}\.[0-9]+(-(alpha|beta|rc)\.[0-9]+)?$ ]]; then
    hata "Sürüm biçimi tanınmadı: '${SURUM}' (beklenen ör. 2026.10.0-beta.1; başında 'v' olmadan)."
fi
[ -d "${DIZIN}" ] || hata "Paket dizini yok: ${DIZIN}"

# Kovadaki ad (HEDEF) ve içerik türü (TUR). SHA256SUMS SÜRÜMLÜ adla yazılır:
# kovada eski sürümlerin paketleri durur, sabit ad her yayında onların özetini
# silerdi.
hedef_ve_tur() {
    case "$1" in
        "${OZET}") HEDEF="SHA256SUMS-${SURUM}.txt"; TUR="text/plain; charset=utf-8" ;;
        *.exe)     HEDEF="$1"; TUR="application/vnd.microsoft.portable-executable" ;;
        *.zip)     HEDEF="$1"; TUR="application/zip" ;;
        *.deb)     HEDEF="$1"; TUR="application/vnd.debian.binary-package" ;;
        *.tar.gz)  HEDEF="$1"; TUR="application/gzip" ;;
        *)         return 1 ;;
    esac
}

cd "${DIZIN}"

# --- denetim (hiçbir şey yüklenmeden önce) ----------------------------------
[ -f "${OZET}" ] || hata "${OZET} yok: özetsiz paket indirme alanına çıkmaz — hiçbir dosya yüklenmedi."
if ! sha256sum --check --strict --quiet "${OZET}"; then
    hata "${OZET} doğrulanmadı (bozuk ya da eksik dosya) — hiçbir dosya yüklenmedi."
fi

# Özetteki adlar: "<özet>  <ad>" (metin kipi) ya da "<özet> *<ad>" (ikili kip).
declare -A LISTELI=()
while IFS= read -r satir || [ -n "${satir}" ]; do
    [ -n "${satir}" ] || continue
    ad="${satir#* }"
    LISTELI["${ad#[ *]}"]=1
done < "${OZET}"

shopt -s nullglob
PAKETLER=()
for dosya in *; do
    if [ "${dosya}" = "${OZET}" ]; then
        continue
    fi
    [ -f "${dosya}" ] || hata "Paket dizininde beklenmeyen öğe: ${dosya} — hiçbir dosya yüklenmedi."
    hedef_ve_tur "${dosya}" \
        || hata "Türü bilinmeyen dosya: ${dosya} (eşleme packaging/r2-yukle.sh'de) — hiçbir dosya yüklenmedi."
    [ -n "${LISTELI[${dosya}]:-}" ] \
        || hata "${dosya} ${OZET}'de yok ('.deb' adındaki '~' yayın işinde '.' yapılır) — hiçbir dosya yüklenmedi."
    boyut="$(stat -c %s -- "${dosya}")"
    [ "${boyut}" -le "${WRANGLER_AZAMI}" ] \
        || hata "${dosya} ${boyut} bayt: wrangler tek parçada en çok ${WRANGLER_AZAMI} bayt (300 MiB) yükler — çok parçalı S3 yüklemesi gerekir (packaging/README.md \"Boyut sınırı\"); hiçbir dosya yüklenmedi."
    PAKETLER+=("${dosya}")
done
[ "${#PAKETLER[@]}" -gt 0 ] || hata "Yüklenecek paket yok: ${DIZIN}"

# --- yükleme ------------------------------------------------------------------
yukle() {
    hedef_ve_tur "$1"
    echo "→ ${R2_ONEK}/${HEDEF}"
    npx --yes wrangler@4 r2 object put "${R2_KOVA}/${R2_ONEK}/${HEDEF}" \
        --file="$1" --content-type="${TUR}" --remote
}

for dosya in "${PAKETLER[@]}"; do
    yukle "${dosya}"
done
yukle "${OZET}"

echo "::notice::Paketler indir.okulapp.org/${R2_ONEK}/ altına yüklendi. Sıradaki elle iş: okulapp.org deposunda src/data/kd-release.json (sürüm, tarih ve boyutlar) güncellenmeli."
