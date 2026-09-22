// `kutuphane` modülü API istemcisi — backend `apps/kutuphane/urls.py` ile BİREBİR.
// URL öneki (`library/…`) OYS'den korunur. F1'de yalnız katalog Excel şablonu
// vardır (tasarım §8.1: şablon ve sütun sözlüğü F1'de sabitlenir); eser, nüsha ve
// içe aktarma uçları sonraki fazlarda buraya eklenir.

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";

/** Belgenin adı — kart başlığı ve indirilen dosyanın adı (backend `TEMPLATE_DOCUMENT_NAME`). */
export const KATALOG_SABLONU_BELGE_ADI = "Katalog Excel Şablonu";

/**
 * İndirilen şablonun adı: belge adı + YEREL tarih (docs/sozluk.md §3).
 * `Katalog-Excel-Şablonu_21.09.2026.xlsx` — backend `excel_template.template_filename`
 * ile aynı biçim. Tarih `todayIso()`'dan gelir; `toISOString()` UTC verir ve gece
 * yarısına yakın indirmede bir önceki günü yazardı.
 */
export function katalogSablonuDosyaAdi(): string {
  return dosyaAdi([KATALOG_SABLONU_BELGE_ADI, formatDate(todayIso())], "xlsx");
}

export const kutuphaneApi = {
  /** `GET /library/import/template/` — boş katalog Excel şablonu (.xlsx). */
  catalogTemplate: (): Promise<Blob> => api.getBlob("/library/import/template/"),
};
