// Ağ Doktoru ve Ayarlar → Ağ Kataloğu'nun ortak parçaları: durum rozeti, QR
// çizimi, kopyalanabilir komut kutusu, "masaüstü dışında" bilgisi ve durum kancası.

import { useCallback, useEffect, useState } from "react";

import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { panoyaKopyala } from "../kutuphane/KopruKomutuKarti";
import { KATALOG_DURUMU_TR, agKataloguApi } from "./api";
import type { AgDurumu, KatalogDurumAdi } from "./api";

/** Durum ekranının kendiliğinden yenilenme aralığı (ayar değişikliği dinleyiciyi arka planda kurar). */
export const YENILEME_ARALIGI_MS = 15_000;

const ROZET_RENGI: Record<KatalogDurumAdi, string> = {
  acik: "bg-success-container text-on-success-container",
  kapali: "bg-surface-container-high text-on-surface-variant",
  engellendi: "bg-error-container text-on-error-container",
  hata: "bg-error-container text-on-error-container",
  bekliyor: "bg-tertiary-container text-on-tertiary-container",
  bakim: "bg-tertiary-container text-on-tertiary-container",
};

const ROZET_IKONU: Record<KatalogDurumAdi, string> = {
  acik: "check_circle",
  kapali: "radio_button_unchecked",
  engellendi: "block",
  hata: "error",
  bekliyor: "hourglass_top",
  bakim: "build",
};

export function DurumRozeti({ durum }: { durum: KatalogDurumAdi }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-label-large ${ROZET_RENGI[durum]}`}
    >
      <Icon name={ROZET_IKONU[durum]} size="base" />
      {KATALOG_DURUMU_TR[durum]}
    </span>
  );
}

/**
 * QR kodu — sunucunun verdiği modül satırlarından çizilir (ön yüzde QR
 * kitaplığı yoktur). 4 modül sessiz bölge; renkler temadan bağımsız siyah/beyaz
 * kalır ki koyu temada da okunabilsin.
 */
export function QrKodu({ satirlar, boyutPx = 128 }: { satirlar: string[]; boyutPx?: number }) {
  const n = satirlar.length;
  const toplam = n + 8;
  const kareler: Array<{ x: number; y: number; w: number }> = [];
  satirlar.forEach((satir, y) => {
    let x = 0;
    while (x < n) {
      if (satir[x] === "1") {
        const bas = x;
        while (x < n && satir[x] === "1") x += 1;
        kareler.push({ x: bas + 4, y: y + 4, w: x - bas });
      } else {
        x += 1;
      }
    }
  });
  return (
    <svg
      role="img"
      aria-label="Katalog adresinin QR kodu"
      width={boyutPx}
      height={boyutPx}
      viewBox={`0 0 ${toplam} ${toplam}`}
      shapeRendering="crispEdges"
    >
      <rect width={toplam} height={toplam} fill="#fff" />
      <g fill="#000">
        {kareler.map((k) => (
          <rect key={`${k.x}-${k.y}`} x={k.x} y={k.y} width={k.w} height={1} />
        ))}
      </g>
    </svg>
  );
}

/** Tek satırlık komut + "Kopyala" düğmesi (BTR'ye verilecek komutlar). */
export function KomutKutusu({ komut, etiket }: { komut: string; etiket?: string }) {
  const snackbar = useSnackbar();
  async function kopyala() {
    if (await panoyaKopyala(komut)) snackbar.success("Komut panoya kopyalandı.");
    else snackbar.error("Komut kopyalanamadı; metni seçip elle kopyalayın.");
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <code
        aria-label={etiket}
        className="min-w-0 flex-1 whitespace-pre-wrap break-all rounded-shape-sm bg-surface-container px-3 py-2 font-mono text-body-small text-on-surface"
      >
        {komut}
      </code>
      <Button variant="text" icon="content_copy" onClick={kopyala}>
        Kopyala
      </Button>
    </div>
  );
}

/** Program masaüstü penceresi dışında çalışıyor: dinleyici ve güvenlik duvarı burada yok. */
export function MasaustuYokBandi() {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-shape-md bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
    >
      <Icon name="info" size="lg" className="mt-0.5 shrink-0" />
      <span>
        Program masaüstü penceresi dışında çalışıyor. Ağ Kataloğunu açıp kapatmak, güvenlik duvarını
        denetlemek ve dinleyiciyi sınamak yalnız masaüstü programında yapılır. Ayarlar ve belgeler
        burada da hazırlanabilir.
      </span>
    </div>
  );
}

/**
 * Ağ Kataloğu durumu: açılışta okunur, `YENILEME_ARALIGI_MS` aralıkla tazelenir
 * (ayar değişikliği dinleyiciyi arka planda yeniden kurar). Yenileme yönetici
 * kipinin boşta sayacını tazelemez (`etkinlik: false`).
 */
export function useAgDurumu() {
  const [durum, setDurum] = useState<AgDurumu | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  const yenile = useCallback(async () => {
    try {
      const sonuc = await agKataloguApi.durum();
      setDurum(sonuc);
      setHata(null);
    } catch (e) {
      setHata(e instanceof Error && e.message ? e.message : "Ağ Kataloğunun durumu okunamadı.");
    }
  }, []);

  useEffect(() => {
    void yenile();
    const zamanlayici = window.setInterval(() => void yenile(), YENILEME_ARALIGI_MS);
    return () => window.clearInterval(zamanlayici);
  }, [yenile]);

  return { durum, setDurum, hata, yenile };
}
