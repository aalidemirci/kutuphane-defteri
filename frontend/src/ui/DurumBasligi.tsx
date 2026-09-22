// Program durumu ekranlarının üst çubuk başlığı (docs/sozluk.md §4: "sayfa
// başlığı (h1) … üst çubuktaki başlıkla AYNIDIR").
//
// Kilit, güvenlik dosyası kayıp ve "yeniden başlatın" ekranları bir ADRESE
// bağlı değildir: kabuğun içinde, kapıların ardında dururlar; `AppShell` yol
// adından onların başlığını türetemez. Bu yüzden ekran, açıkken kendi h1'ini
// buraya yazar; kabuk da üst çubukta onu gösterir.
//
// Yığın (tek değer değil): örtüşen iki durum ekranı olabilir — kilit ekranının
// üstüne "yeniden başlatın" örtüsü gelebilir. En SON yazan kazanır, kapanınca
// bir alttaki geri döner. Sağlayıcı yoksa (bileşen tek başına test edilirken)
// yazmak sessizce hiçbir şey yapmaz.

import { createContext, useCallback, useContext, useEffect, useId, useState } from "react";
import type { ReactNode } from "react";

type Yazar = (id: string, baslik: string | null) => void;

const DurumBasligiContext = createContext<Yazar>(() => undefined);

/** Kabuğun tarafı: o an gösterilecek durum başlığı ve ekranların yazacağı işlev. */
export function useDurumBasligiYonetimi(): { durumBasligi: string | null; yaz: Yazar } {
  const [yigin, setYigin] = useState<ReadonlyArray<{ id: string; baslik: string }>>([]);

  const yaz = useCallback<Yazar>((id, baslik) => {
    setYigin((onceki) => {
      const kalan = onceki.filter((k) => k.id !== id);
      return baslik === null ? kalan : [...kalan, { id, baslik }];
    });
  }, []);

  return { durumBasligi: yigin.length > 0 ? yigin[yigin.length - 1].baslik : null, yaz };
}

export function DurumBasligiSaglayici({ yaz, children }: { yaz: Yazar; children: ReactNode }) {
  return <DurumBasligiContext.Provider value={yaz}>{children}</DurumBasligiContext.Provider>;
}

/**
 * Bu ekran açıkken üst çubuk başlığını ekranın h1'i yapar. `null` verilirse
 * (ekran henüz görünmüyorsa) başlığa dokunulmaz — kanca koşullu çağrılamaz.
 */
export function useDurumBasligi(baslik: string | null): void {
  const yaz = useContext(DurumBasligiContext);
  const id = useId();
  useEffect(() => {
    if (baslik === null) return;
    yaz(id, baslik);
    return () => yaz(id, null);
  }, [yaz, id, baslik]);
}
