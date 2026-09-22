// "Kilit kapısı" olayı — backend kilit kapısının (`apps/okul/lock_middleware`)
// arayüz ayağı. Oturum ortasında bir istek 423 `locked` ya da
// `guvenlik_dosyasi_kayip` alırsa program arayüzün haberi olmadan kilitlenmiş
// (başka yoldan kilit: yönetim komutu, ileride tepsi) ya da güvenlik dosyası
// kaybolmuştur (tasarım §4.3; kapı anahtar bellekteyken de kapanır). `lib/api.ts`
// bu kodları görünce olayı yayınlar; güvenlik kapısı
// (`modules/guvenlik/GuvenlikKapisi`) dinler ve durumu yeniden okur, böylece
// ilgili ekran (kilit ya da "Güvenlik dosyası bulunamadı ya da okunamıyor") hemen görünür.
// `lib/restart.ts` deseni.

export const KILIT_KAPISI_OLAYI = "kd:kilit-kapisi";

/** 423 gövdesindeki kodlar (`lock_middleware`). */
export const KILIT_KAPISI_KODLARI: ReadonlySet<string> = new Set([
  "locked",
  "guvenlik_dosyasi_kayip",
]);

export function kilitKapisiYayinla(): void {
  window.dispatchEvent(new CustomEvent(KILIT_KAPISI_OLAYI));
}
