// Ders yılının kapalı günlerini tohumlama — kurulum sihirbazı ve Ayarlar → Ders Yılları
// aynı kuralı kullanır (tasarım §6.1, §9-5).
//
// İade tarihi kaydırması yalnız Kapalı Günler'deki kayıtlara bakar. Bir takvim yılının
// resmî tatilleri ve dini bayramları girilmemişse o yılın 1 Ocak'ına ya da bayramına
// düşen iade tarihi kaydırılmaz ve ertesi gün sahte gecikme doğar (F6 düzeltme turu:
// ikinci kullanım yılında Ayarlar'dan açılan ders yılı tatilsiz kalıyordu). Ders yılı
// iki takvim yılına yayılır; ikisi de tohumlanır. Tohumlama fikirdeştir: var olan
// kayıt yeniden eklenmez. Yalnız ders yılı oluşturulunca ya da aktifleşince koşar:
// sonradan silinen bir tatil her ekran açılışında geri gelmesin.

import { okulApi } from "../okul/api";
import type { SchoolYear } from "../okul/api";

/** Ders yılının kapsadığı takvim yılları ("2026-09-01" → "2027-06-30": [2026, 2027]). */
export function takvimYillari(baslangic: string, bitis: string): number[] {
  const ilk = Number(baslangic.slice(0, 4));
  const son = Number(bitis.slice(0, 4));
  const yillar: number[] = [];
  for (let y = ilk; y <= son; y += 1) yillar.push(y);
  return yillar;
}

/**
 * Ders yılının iki takvim yılına resmî ve dini tatilleri ekler. Programın dini bayram
 * tablosunda bulunmayan yılları döndürür (kullanıcı onları elle girmelidir).
 */
export async function tatilleriTohumla(yil: SchoolYear): Promise<number[]> {
  const eksikDini: number[] = [];
  for (const takvimYili of takvimYillari(yil.start_date, yil.end_date)) {
    const sonuc = await okulApi.seedHolidays(takvimYili);
    if (!sonuc.religious_available) eksikDini.push(takvimYili);
  }
  return eksikDini;
}

/** Dini bayram tarihleri programda olmayan yıllar için kullanıcı iletisi. */
export function eksikDiniBayramIletisi(yillar: number[]): string | null {
  if (yillar.length === 0) return null;
  return `Programda ${yillar.join(" ve ")} yılının dini bayram tarihleri yok; Diyanet takvimindeki tarihleri “Dini bayram” türünde elle ekleyin.`;
}
