// Doğrulanmayı bekleyen kurtarma anahtarı — ROTA AĞACININ DIŞINDA, modül belleğinde.
//
// Neden bileşen durumunda değil: anahtar sunucuda saklanmaz ve bir daha
// gösterilemez (tasarım §6.3-1 "saklama zorunlu"). Sihirbaz sayfası anahtar
// ekrandayken sökülebilir: "Görevli kipine geç" ya da Ctrl+Shift+G KipKapisi'nde
// rotaların yerine görevli ekranını koyar; "Kilitle" kilit ekranını getirir; üst
// menüden bir bağlantıya tıklamak da KurulumKapisi üzerinden sihirbazı sıfırdan
// açar. (Kurulum sürerken boşta ve mutlak süre kipi DÜŞÜRMEZ — backend `kip.py`,
// F1 eki karar 2-1; kurulumdan sonra yenilenen anahtarda süre yine bu yola girer.)
// Anahtar bileşen durumunda dursaydı bu yolların her biri onu sessizce silerdi.
// Burada tutulan anahtar sihirbaz (ya da Ayarlar → Güvenlik) yeniden açılınca geri
// gelir; iki grup yeniden doğrulanmadan ilerlenemez.
//
// Anahtar YALNIZ bellektedir: tarayıcı deposuna (localStorage, sessionStorage)
// YAZILMAZ — o, anahtarı diske düz metin olarak bırakırdı. Pencere kapanırsa ya
// da program çökerse anahtar gider: sihirbaz ve Güvenlik ekranı bu durumda
// "kâğıttaki anahtarı doğrula" ya da "yenisini üret" yolunu sunar (sunucudaki
// "saklandı" damgası yoktur). Sunucu damgayı yazınca bırakılır.

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
