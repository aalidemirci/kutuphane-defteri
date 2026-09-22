// Kurtarma anahtarının istemci tarafı yardımcıları (tasarım §6.3-1, E14).
//
// Anahtar SUNUCUDA SAKLANMAZ: kurulumda bir kez gösterilir; "saklandı mı"
// doğrulaması (iki grubu geri yazdırma) bu yüzden istemcide yapılır. Normalleştirme
// backend `app_password.normalize_recovery_key` ile AYNIDIR: Türkçe "İ" ve "ı"
// "I" olur, büyük harfe çevrilir, ASCII harf ve rakam dışındaki her şey (boşluk,
// tire) atılır, elle yazımda karışan 0→O, 1→I, 8→B düzeltilir (anahtar alfabesi
// A-Z ve 2-7'dir; 0, 1, 8, 9 yoktur). Türkçe klavyede büyük harfle yazılan "i"
// noktalı "İ" olur ve `toUpperCase` onu "I"ya çevirmez; eşleme bu yüzden önce
// yapılır. Anahtar Türkçe metin değildir: "i", "ı", "İ" hepsi "I" olmalıdır.

import { useState } from "react";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import { guvenlikApi } from "./api";

/** Anahtar dörtlü gruplardan oluşur (backend `RECOVERY_GROUP_SIZE`). */
export const GRUP_UZUNLUGU = 4;

/** Belgenin adı (sözlük §2: E14 "Kurtarma anahtarı çıktısı"). */
export const KURTARMA_CIKTISI_BELGE_ADI = "Kurtarma Anahtarı Çıktısı";

export function kurtarmaAnahtariniNormallestir(deger: string): string {
  return deger
    .replace(/[İı]/g, "I")
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .replace(/0/g, "O")
    .replace(/1/g, "I")
    .replace(/8/g, "B");
}

/** "ABCD-EFGH-…" → ["ABCD", "EFGH", …] (normalleştirilmiş). */
export function kurtarmaGruplari(anahtar: string): string[] {
  const sade = kurtarmaAnahtariniNormallestir(anahtar);
  const gruplar: string[] = [];
  for (let i = 0; i < sade.length; i += GRUP_UZUNLUGU) {
    gruplar.push(sade.slice(i, i + GRUP_UZUNLUGU));
  }
  return gruplar;
}

/**
 * Doğrulama için iki FARKLI grup sırası (0 tabanlı, artan). `rastgele` testte
 * sabitlenir; güvenlik amacı yoktur (sır değil, saklama denetimidir).
 */
export function rastgeleIkiGrup(
  adet: number,
  rastgele: () => number = Math.random,
): [number, number] {
  const birinci = Math.floor(rastgele() * adet) % adet;
  let ikinci = Math.floor(rastgele() * (adet - 1)) % (adet - 1);
  if (ikinci >= birinci) ikinci += 1;
  return birinci < ikinci ? [birinci, ikinci] : [ikinci, birinci];
}

/** İndirilen PDF'in adı: belge adı + YEREL tarih (backend `recovery_key_pdf_filename` ile aynı). */
export function kurtarmaCiktisiDosyaAdi(): string {
  return dosyaAdi([KURTARMA_CIKTISI_BELGE_ADI, formatDate(todayIso())], "pdf");
}

/**
 * Kurtarma anahtarı çıktısını (PDF) indirir. Backend anahtarı kurtarma sarmalına
 * karşı doğrular; yanlışsa Türkçe iletiyle 400 döner ve dosya inmez.
 */
export function useKurtarmaCiktisi() {
  const [indiriliyor, setIndiriliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  async function indir(anahtar: string): Promise<boolean> {
    setIndiriliyor(true);
    setHata(null);
    try {
      const pdf = await guvenlikApi.kurtarmaAnahtariPdf(anahtar);
      saveBlob(pdf, kurtarmaCiktisiDosyaAdi());
      return true;
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Kurtarma anahtarı çıktısı hazırlanamadı.");
      return false;
    } finally {
      setIndiriliyor(false);
    }
  }

  return { indir, indiriliyor, hata };
}
