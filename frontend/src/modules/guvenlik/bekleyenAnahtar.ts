// Doğrulanmayı bekleyen kurtarma anahtarı — ROTA AĞACININ DIŞINDA, modül belleğinde.
//
// Neden bileşen durumunda değil: anahtar sunucuda saklanmaz ve bir daha üretilemez
// (tasarım §6.3-1 "saklama zorunlu"). Sihirbaz sayfası anahtar ekrandayken
// sökülebilir: 3 dakika boşta kalınca kip görevliye iner ve KipKapisi rotaların
// yerine görevli ekranını koyar; "Kilitle" ya da Ctrl+Shift+G aynı şeyi anında
// yapar; üst menüden bir bağlantıya tıklamak da KurulumKapisi üzerinden sihirbazı
// sıfırdan açar. Anahtar bileşen durumunda dursaydı bu yolların her biri onu
// sessizce silerdi ve sihirbaz 2. adımdan, doğrulama istemeden açılırdı.
// Burada tutulan anahtar sihirbaz yeniden açılınca geri gelir; iki grup yeniden
// doğrulanmadan ilerlenemez.
//
// Anahtar YALNIZ bellektedir: tarayıcı deposuna (localStorage, sessionStorage)
// YAZILMAZ — o, anahtarı diske düz metin olarak bırakırdı. Pencere kapanırsa ya
// da program çökerse anahtar gider; kılavuz ve panel metni bunu söyler.
// Doğrulanıp sihirbazda ilerlenince bırakılır.

import { useSyncExternalStore } from "react";

let bekleyen: string | null = null;
const dinleyiciler = new Set<() => void>();

/** Doğrulanmamış anahtar (yoksa null). */
export function bekleyenKurtarmaAnahtari(): string | null {
  return bekleyen;
}

/** Anahtarı bekletir (`null`: bırakır). Dinleyen bileşenler yeniden çizilir. */
export function bekleyenKurtarmaAnahtariniYaz(anahtar: string | null): void {
  if (bekleyen === anahtar) return;
  bekleyen = anahtar;
  for (const dinleyici of dinleyiciler) dinleyici();
}

function abone(dinleyici: () => void): () => void {
  dinleyiciler.add(dinleyici);
  return () => {
    dinleyiciler.delete(dinleyici);
  };
}

/** Bekleyen anahtarı okuyan kanca (değişince bileşen yeniden çizilir). */
export function useBekleyenKurtarmaAnahtari(): string | null {
  return useSyncExternalStore(abone, bekleyenKurtarmaAnahtari, bekleyenKurtarmaAnahtari);
}
