// Okutulan ya da elle yazılan kodun türü — backend `apps/kutuphane/barcode.py`
// ile aynı kurallar (tasarım §7.1; `barcode.py` docstring'i "aynı yardımcının
// bir eşi ön yüzde bulunur" der).
//
// Ön yüzde neden ikinci bir kopya var: hızlı kayıtta okuyucu masadadır ve her
// okutmada sunucuya sorup cevabı beklemek akışı kesecek kadar yavaştır. Ayrım
// üç şemanın UZUNLUK ve ÖN EK farkından ibarettir; yanlış sınıflama da bir ret
// değil, yalnız kullanıcıya gösterilen iletiyi değiştirir.
//
// | Tür | Biçim | Örnek |
// |---|---|---|
// | Nüsha barkodu (kütüphane etiketi) | 10 hane: `YYYY` + 6 hane sıra | `2026000123` |
// | Üye kartı | 8 hane: `9` + 6 rastgele + 1 sağlama (Luhn) | `94718263` |
// | Kitabın ISBN barkodu | 13 hane, 978/979 | `9789750812345` |
//
// Kalan belirsizlik (TB22, backend ile aynı): ilk dört hanesi 2000-2999'a düşen
// ISBN-10'lar nüsha barkodundan ayrılamaz. ISBN-10 2007'den beri basılmıyor.

/** Nüsha barkodunun uzunluğu (4 hane yıl + 6 hane sıra). */
export const BARKOD_UZUNLUGU = 10;
/** Üye kartı numarasının uzunluğu ve ön eki. */
export const UYE_KARTI_UZUNLUGU = 8;
export const UYE_KARTI_ONEKI = "9";
/** ISBN-13'ün uzunluğu ve Bookland ön ekleri. */
export const ISBN13_UZUNLUGU = 13;
export const ISBN13_ONEKLERI: readonly string[] = ["978", "979"];
/** Nüsha barkodunun yıl ön ekinin okutmada makul sayıldığı aralık. */
export const TARAMA_YIL_EN_AZ = 2000;
export const TARAMA_YIL_EN_COK = 2999;

/** Okutulan kodun türü — backend `barcode.ScanKind` ile aynı kodlar. */
export type KodTuru = "COPY" | "MEMBER_CARD" | "ISBN" | "UNKNOWN";

/**
 * Barkodun basılı biçimi: "2026000123" → "2026-000123" (backend
 * `barcode.format_barcode`). Nüsha listeleri bu değeri sunucudan hazır alır;
 * burası yalnız aktarım raporunun barkod aralığı gibi ham değerler içindir.
 * Biçimlendirme YALNIZ görüntüdür: saklanan ve okutulan değer rakamlardır.
 */
export function barkodBicimle(barkod: string): string {
  const rakamlar = taramaNormalize(barkod);
  if (rakamlar.length !== BARKOD_UZUNLUGU) return barkod;
  return `${rakamlar.slice(0, 4)}-${rakamlar.slice(4)}`;
}

/**
 * Okuyucu ya da klavye girdisini sadeleştirir: rakam dışındaki her şey atılır.
 * Okuyucular sonuna Enter, bazı modeller araya boşluk ya da tire koyar;
 * kullanıcı basılı biçimi ("2026-000123") elle de yazabilir.
 */
export function taramaNormalize(deger: string): string {
  return Array.from(deger)
    .filter((ch) => ch >= "0" && ch <= "9")
    .join("");
}

/**
 * ISBN'i sadeleştirir: rakamlar ve sağlama harfi "X" kalır. Küçük "x" tek
 * karakter eşlemesiyle büyütülür — `toUpperCase()` Türkçe metinde i→I basar
 * (CLAUDE.md §2-9), bu yüzden hiç çağrılmaz.
 */
export function isbnNormalize(deger: string): string {
  return Array.from(deger)
    .map((ch) => (ch === "x" ? "X" : ch))
    .filter((ch) => (ch >= "0" && ch <= "9") || ch === "X")
    .join("");
}

/** ISBN-10'un sağlama hanesi (ilk 9 rakamdan; 10 değeri "X"). */
function isbn10SaglamaHanesi(govde: string): string {
  let toplam = 0;
  for (let i = 0; i < 9; i += 1) toplam += (i + 1) * Number(govde[i]);
  const kalan = toplam % 11;
  return kalan === 10 ? "X" : String(kalan);
}

/** Sağlaması tutan 10 haneli numara mı? (biçim: 9 rakam + rakam ya da "X") */
export function gecerliIsbn10(deger: string): boolean {
  if (deger.length !== BARKOD_UZUNLUGU) return false;
  if (!/^\d{9}$/.test(deger.slice(0, 9))) return false;
  return deger[9] === isbn10SaglamaHanesi(deger);
}

/** 10 haneli kodun ilk dört hanesi makul bir barkod yılı mı? */
export function barkodYilOnekiVarMi(rakamlar: string): boolean {
  if (rakamlar.length !== BARKOD_UZUNLUGU || !/^\d+$/.test(rakamlar)) return false;
  const yil = Number(rakamlar.slice(0, 4));
  return yil >= TARAMA_YIL_EN_AZ && yil <= TARAMA_YIL_EN_COK;
}

/** Okutulan kod kitabın ISBN barkodu mu? (13 hane + 978/979; sağlama denetlenmez) */
export function isbnBarkoduMu(deger: string): boolean {
  const rakamlar = isbnNormalize(deger);
  if (rakamlar.length !== ISBN13_UZUNLUGU || !/^\d+$/.test(rakamlar)) return false;
  return ISBN13_ONEKLERI.some((onek) => rakamlar.startsWith(onek));
}

/**
 * Okutulan ya da yazılan kodun türü (§7.1). Tanınmayan kod `UNKNOWN` döner.
 *
 * 10 hane tek başına yetmez: kullanıcı kitabın künye sayfasındaki eski ISBN-10'u
 * kutuya elle yazabilir; o da 10 hanedir ve nüsha barkodundan yalnız yıl önekiyle
 * ayrılır. Yıl gibi görünmeyen 10 haneli bir numaranın sağlaması tutuyorsa
 * ISBN-10 sayılır.
 */
export function kodTuru(deger: string): KodTuru {
  const rakamlar = taramaNormalize(deger);
  if (rakamlar.length === BARKOD_UZUNLUGU) {
    if (barkodYilOnekiVarMi(rakamlar)) return "COPY";
    return gecerliIsbn10(rakamlar) ? "ISBN" : "UNKNOWN";
  }
  if (rakamlar.length === UYE_KARTI_UZUNLUGU && rakamlar.startsWith(UYE_KARTI_ONEKI)) {
    return "MEMBER_CARD";
  }
  // Sağlama harfi "X" ile biten ISBN-10 buraya düşmez ve `UNKNOWN` olur:
  // backend `classify_scan` de öyle davranır ("X" rakam değildir, kod 9 haneye
  // iner). İki kopyanın aynı kalması, iletinin iki katmanda aynı olmasıdır.
  return isbnBarkoduMu(rakamlar) ? "ISBN" : "UNKNOWN";
}
