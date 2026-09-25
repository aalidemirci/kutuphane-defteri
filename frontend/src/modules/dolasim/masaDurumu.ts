// Masanın kişisiz durumu (F9 — madde 24, 26; 25.09.2026 kullanıcı kararları).
//
// `GET library/desk/state/` iki kipte de açıktır ve yalnız iki şey söyler: sayım için hizmet
// arası sürüyor mu (masa şeridi açılışta çizilir — görevli kipinde de, ilk ödünç reddinden
// ÖNCE) ve okutması açık süren bir sayım var mı (görevli ekranının "Sayım okutmasını aç"
// düğmesi). Masa gün boyu açık kalır; durum aralıkla yeniden okunur ki hizmet arası kalkınca
// şerit de kalksın. Okunamazsa `null` döner ve hiçbir şey çizilmez.

import { useEffect, useState } from "react";

import { dolasimApi } from "./api";
import type { MasaDurumu } from "./api";

/** Masa gün boyu açık kalır: durum bu aralıkla yeniden okunur (ms). */
export const MASA_DURUMU_YENILEME_MS = 60_000;

export function useMasaDurumu(yenilemeMs: number = MASA_DURUMU_YENILEME_MS): MasaDurumu | null {
  const [durum, setDurum] = useState<MasaDurumu | null>(null);
  useEffect(() => {
    let iptal = false;
    const oku = () => {
      dolasimApi
        .masaDurumu()
        .then((d) => {
          if (!iptal) setDurum(d);
        })
        .catch(() => undefined);
    };
    oku();
    const zamanlayici = yenilemeMs > 0 ? setInterval(oku, yenilemeMs) : null;
    return () => {
      iptal = true;
      if (zamanlayici !== null) clearInterval(zamanlayici);
    };
  }, [yenilemeMs]);
  return durum;
}
