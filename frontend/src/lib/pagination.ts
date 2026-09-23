// DRF sayfalı yanıt tipi + çözücü (Tur 615 — F-fe DRY konsolidasyonu).
// 20+ modül api.ts'i kendi `Paginated<T>` kopyasını, 10'u özdeş `unwrap`
// kopyasını taşıyordu — tek doğruluk kaynağı burası. Yeni kod bunu kullanır.

/** DRF PageNumber/LimitOffset sayfalı liste yanıtı (kanonik tam şekil). */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** DRF list uçları sayfalıdır; bazı özel action'lar düz dizi döndürür —
 * iki biçimi de diziye indirger. */
export function unwrap<T>(data: Paginated<T> | T[]): T[] {
  return Array.isArray(data) ? data : data.results;
}

/** Henüz yükleme yapılmamış liste için boş sayfa (ilk çizimde `count` 0 kalır). */
export function emptyPage<T>(): Paginated<T> {
  return { count: 0, next: null, previous: null, results: [] };
}

/**
 * Boş dönen sayfa için geri düşülecek offset (gerekmiyorsa `null`).
 *
 * Son sayfadaki tek kayıt silinince liste boşalır; boş durumda sayfalama çubuğu
 * basılmadığından kullanıcı orada kilitlenirdi — bir önceki sayfaya düşülüp
 * yeniden yüklenir.
 */
export function geriDusulecekOffset<T>(
  result: Paginated<T>,
  offset: number,
  pageSize: number,
): number | null {
  if (result.results.length > 0 || offset === 0) return null;
  return Math.max(0, offset - pageSize);
}
