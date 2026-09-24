#!/usr/bin/env bash
# =============================================================================
# Ağ Kataloğu provası (tasarım §14.1 F5 kod kapısı)
# =============================================================================
# İki ayrı Docker kabı, aynı compose ağında iki ayrı bilgisayar gibi davranır:
#   A: gerçek masaüstü yolu — yönetim sunucusu 127.0.0.1'de (oturum belirteçli),
#      Ağ Kataloğu `KatalogKontrol` ile TÜM ARAYÜZLERDE (8765), 10.000 sentetik eser;
#   B: A'ya ağdan bağlanır.
# Üç kanıt, her biri eşikli ve nöbetçili (`ADIM_OK_*`):
#   (1) İKİNCİ BİLGİSAYARDAN ARAMA: B → "ŞİİR" araması 200 + imza + CSP + çerez yok;
#       katalog portunda yönetim yolu 404; A'nın yönetim portu ağdan KAPALI. A'nın
#       gördüğü istek adresi B'nin IP'sidir (127.0.0.1 değil).
#   (2) YÖNETİM TABANI: yüksüzken yönetim API'si gecikmesi (A'da ayrı süreç).
#   (3) 50 İSTEMCİLİ YÜK: B'de 50 eşzamanlı istemci, her biri AYRI kaynak IP'den
#       (--cap-add NET_ADMIN), katalog sayfalarını <sn> boyunca çeker; aynı anda
#       A'da yönetim API'si ölçülür. Hata 0, hız sınırı 429'u 0, yönetim p95 < 500 ms.
#
#     bash scripts/ag_katalogu_provasi.sh [yük-sn=30] [istemci=50] [düşünme-sn=0]
#
# Düşünme süresi 0: her istemci yanıtı alır almaz yeni sayfa ister (en kötü durum).
# Kapıda gecelik koşar (`KD_YAVAS=1 bash scripts/gates.sh`). Kişi verisi yoktur.
# =============================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "${BASH_SOURCE[0]}")/.."

YUK_SN="${1:-30}"
ISTEMCI="${2:-50}"
DUSUNME="${3:-0}"
AD="kd-katalog-prova"
GUNLUK="$(mktemp)"
YUK_GUNLUGU="$(mktemp)"
docker rm -f "$AD" >/dev/null 2>&1 || true
trap 'docker rm -f "$AD" >/dev/null 2>&1 || true; rm -f "$GUNLUK" "$YUK_GUNLUGU"' EXIT

nobetci() {  # nobetci <dosya> <ad>
  if ! grep -q "ADIM_OK_$2" "$1"; then
    echo "HATA: '$2' adımı nöbetçi kanıtı üretmedi" >&2
    exit 1
  fi
}

echo "== A: katalog + yönetim kabı (KD_DEBUG=0, gerçek masaüstü yolu)"
docker compose run -d --name "$AD" -e KD_DEBUG=0 -w /repo backend \
  python scripts/ag_katalogu_provasi.py sun 1200 >/dev/null
for _ in $(seq 1 300); do
  if docker logs "$AD" 2>&1 | grep -q "KATALOG_HAZIR"; then break; fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$AD" 2>/dev/null)" != "true" ]; then
    docker logs "$AD" >&2
    echo "HATA: katalog kabı durdu" >&2
    exit 1
  fi
  sleep 1
done
docker logs "$AD" 2>&1 | grep -E "^(TOHUM|KONTROL_DURUMU|KATALOG_HAZIR)"
SATIR="$(docker logs "$AD" 2>&1 | grep KATALOG_HAZIR | tail -1)"
A_IP="$(echo "$SATIR" | awk '{print $2}' | cut -d: -f1)"
YON_PORT="$(echo "$SATIR" | sed -E 's/.*yonetim_port=([0-9]+).*/\1/')"
ILK="$(echo "$SATIR" | sed -E 's/.*eser=([0-9]+)-([0-9]+).*/\1/')"
SON="$(echo "$SATIR" | sed -E 's/.*eser=([0-9]+)-([0-9]+).*/\2/')"
AG_ADI="$(docker inspect -f '{{range $ad, $_ := .NetworkSettings.Networks}}{{$ad}}{{end}}' "$AD")"
ALT_AG="$(docker network inspect "$AG_ADI" --format '{{(index .IPAM.Config 0).Subnet}}')"

echo "== (1) İkinci bilgisayardan arama: B kabı → $A_IP:8765"
docker compose run --rm -T -w /repo backend \
  python scripts/ag_katalogu_provasi.py iste "$A_IP" "$YON_PORT" 2>&1 | tee "$GUNLUK"
nobetci "$GUNLUK" ikinci_bilgisayar
GORULEN="$(docker logs "$AD" 2>&1 | grep YENI_ADRES | awk '{print $2}' | sort -u | tr '\n' ' ')"
echo "== A'nın gördüğü istek adresleri: $GORULEN"
B_GELDI=0
for ip in $GORULEN; do
  if [ "$ip" != "127.0.0.1" ] && [ "$ip" != "$A_IP" ]; then B_GELDI=1; fi
done
if [ "$B_GELDI" != 1 ]; then
  echo "HATA: istek başka bir adresten gelmedi" >&2
  exit 1
fi

echo "== (2) Yönetim API'si, yüksüz taban (10 sn)"
docker exec "$AD" python scripts/ag_katalogu_provasi.py yokla 10 yuksuz 2>&1 | tee "$GUNLUK"
nobetci "$GUNLUK" yonetim_yuksuz

echo "== (3) Yük: $ISTEMCI istemci × $YUK_SN sn (düşünme $DUSUNME sn), ağ $ALT_AG"
docker compose run --rm -T --cap-add NET_ADMIN -w /repo backend \
  python scripts/ag_katalogu_provasi.py yuk "$A_IP" "$YUK_SN" "$ISTEMCI" "$ALT_AG" \
  "$ILK" "$SON" "$DUSUNME" >"$YUK_GUNLUGU" 2>&1 &
YUK_PID=$!
# Yönetim ölçüm penceresi yükün İÇİNDE kalır: yük başladıktan sonra açılır, bitmeden kapanır.
for _ in $(seq 1 240); do
  if grep -q KAYNAK_ADRESLER "$YUK_GUNLUGU" 2>/dev/null; then break; fi
  sleep 0.5
done
sleep 2
docker exec "$AD" python scripts/ag_katalogu_provasi.py yokla "$((YUK_SN - 5))" yuk_altinda \
  2>&1 | tee "$GUNLUK"
wait "$YUK_PID" || true
grep -v "Container" "$YUK_GUNLUGU"
nobetci "$YUK_GUNLUGU" yuk
nobetci "$GUNLUK" yonetim_yuk_altinda
echo "== A'nın kişisiz sayaçları"
docker logs "$AD" 2>&1 | grep "^SAYAC" | tail -1
echo "KAPI_OK_ag_provasi"
