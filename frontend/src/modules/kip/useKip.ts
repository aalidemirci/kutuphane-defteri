// Kip sorgusu — kip göstergesi (AppShell üst çubuğu) ve kip kapısı (App) aynı
// react-query önbelleğini paylaşır; tek istek, tek doğruluk kaynağı.
//
// Yoklama periyodiktir ve `X-KD-Etkinlik` TAŞIMAZ (tasarım §4.4, §5.10-14):
// zamanlayıcıyla giden istek yönetici kipini canlı tutmamalıdır. Kip, arayüzün
// haberi olmadan da değişebilir (süre sunucuda dolar); bunu üç yol yakalar:
// periyodik yoklama, 403 `kip_yetkisiz` olayı (`lib/kip.ts`) ve kilitleme olayı.
//
// Sorgu hatası FAIL-OPEN'dır (`ozet: null`): gerçek kapı backend'dedir
// (`apps/okul/kip_middleware`); arayüzü burada kilitlemek bir uç hatasında
// kullanıcıyı ekrandan atmak olurdu.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";

import { sonEtkinlikGonderimiAni } from "../../lib/api";
import { KIP_YETKISIZ_OLAYI } from "../../lib/kip";
import { KILIT_OLAYI } from "../guvenlik/GuvenlikKapisi";
import { kipApi } from "./api";
import type { KipAdi, KipOzeti } from "./api";

export const KIP_SORGU_ANAHTARI = ["kip"] as const;

/** Kip göstergesinin yoklama aralığı (ms). */
export const KIP_YOKLAMA_MS = 15_000;

/**
 * Etkinlik nabzı en sık bu aralıkla gider (ms). Yönetici uzun bir formu
 * doldururken (API isteği olmadan tuşlama) boşta süresi dolmasın diye, GERÇEK
 * bir etkileşimin ardından ve son başlıklı istekten bu kadar zaman geçmişse
 * kip sorgusu bir kez başlıkla gönderilir. Zamanlayıcıyla gitmez.
 */
export const NABIZ_ARALIGI_MS = 30_000;

export interface KipBilgisi {
  /** Son okunan özet; okunamadıysa ya da henüz gelmediyse null. */
  ozet: KipOzeti | null;
  /** Özetin alındığı an (`Date.now()` ölçeği). */
  alindi: number;
  /** Sunucuya yeniden sorar (etkinlik başlığı olmadan). */
  yenile: () => void;
  /** Bir geçiş ucunun döndürdüğü özeti önbelleğe yazar. */
  ozetiYaz: (ozet: KipOzeti) => void;
}

export function useKip(): KipBilgisi {
  const queryClient = useQueryClient();
  const sorgu = useQuery({
    queryKey: KIP_SORGU_ANAHTARI,
    queryFn: () => kipApi.durum(false),
    refetchInterval: KIP_YOKLAMA_MS,
    // Kip kapısı kilit açıldıktan sonra takılır: takılırken taze durum okunur.
    staleTime: 0,
    retry: false,
  });

  const yenile = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: KIP_SORGU_ANAHTARI });
  }, [queryClient]);

  const ozetiYaz = useCallback(
    (ozet: KipOzeti) => queryClient.setQueryData(KIP_SORGU_ANAHTARI, ozet),
    [queryClient],
  );

  useEffect(() => {
    window.addEventListener(KIP_YETKISIZ_OLAYI, yenile);
    window.addEventListener(KILIT_OLAYI, yenile);
    return () => {
      window.removeEventListener(KIP_YETKISIZ_OLAYI, yenile);
      window.removeEventListener(KILIT_OLAYI, yenile);
    };
  }, [yenile]);

  return {
    // Yoklama arada bir düşerse son bilinen durum korunur (ekran sıçramaz).
    ozet: sorgu.data ?? null,
    alindi: sorgu.dataUpdatedAt,
    yenile,
    ozetiYaz,
  };
}

/**
 * Yönetici kipinde gerçek etkileşimin ardından (en sık `NABIZ_ARALIGI_MS`'de
 * bir) kip sorgusunu `X-KD-Etkinlik` ile gönderir. Başlığı `lib/api` ekler:
 * etkileşim yakalama evresinde kaydedildiği için bu istek "kullanıcı eylemi"
 * sayılır. Yalnız bir yerde (kip göstergesi) takılır.
 */
export function useEtkinlikNabzi(durum: KipAdi | undefined, ozetiYaz: (o: KipOzeti) => void) {
  const sonNabiz = useRef(Number.NEGATIVE_INFINITY);

  useEffect(() => {
    if (durum !== "yonetici") return;
    const nabiz = () => {
      const simdi = Date.now();
      const son = Math.max(sonNabiz.current, sonEtkinlikGonderimiAni());
      if (simdi - son < NABIZ_ARALIGI_MS) return;
      sonNabiz.current = simdi;
      kipApi
        .durum(true)
        .then(ozetiYaz)
        .catch(() => {
          /* nabız sessizdir; yoklama durumu zaten yeniler */
        });
    };
    window.addEventListener("pointerdown", nabiz);
    window.addEventListener("keydown", nabiz);
    return () => {
      window.removeEventListener("pointerdown", nabiz);
      window.removeEventListener("keydown", nabiz);
    };
  }, [durum, ozetiYaz]);
}

/**
 * Görsel geri sayım: görevli kipine inmeye kalan saniye (boşta ve mutlak
 * sürenin küçüğü). Yalnız GÖRSELDİR; karar her istekte sunucuda verilir.
 * Özetten sonra başlıklı bir istek gittiyse sunucu boşta sayacını tazelemiştir.
 */
export function kalanSaniye(
  ozet: KipOzeti,
  alindi: number,
  simdi: number,
  sonGonderim: number,
): number | null {
  if (ozet.durum !== "yonetici" || ozet.bosta_kalan_sn === null || ozet.mutlak_kalan_sn === null) {
    return null;
  }
  const gecen = (simdi - alindi) / 1000;
  let bosta = ozet.bosta_kalan_sn - gecen;
  if (sonGonderim > alindi) {
    bosta = Math.max(bosta, ozet.bosta_dk * 60 - (simdi - sonGonderim) / 1000);
  }
  const mutlak = ozet.mutlak_kalan_sn - gecen;
  return Math.max(0, Math.ceil(Math.min(bosta, mutlak)));
}

/** Saniye → "d:ss" (ör. 161 → "2:41"). */
export function sureBicimle(saniye: number): string {
  const dk = Math.floor(saniye / 60);
  const sn = saniye % 60;
  return `${dk}:${String(sn).padStart(2, "0")}`;
}
