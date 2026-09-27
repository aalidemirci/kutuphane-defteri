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
//
// Kaynak (F11): anahtarı hangi akışın ürettiği de burada durur. Görev devrinin anahtarı
// ("gorev-devri") Güvenlik ekranının başındaki panelde değil, Görev Devri sihirbazının
// "Yeni anahtar saklanır" adımında saklatılıp doğrulanır — adımlar tek kartta kalsın.
// Öbür akışlar (kurulum, "Kurtarma anahtarını yenile") kaynak vermez.

import { useSyncExternalStore } from "react";

/** Anahtarı bekleten akış; `null` kurulum ya da "Kurtarma anahtarını yenile"dir. */
export type BekleyenAnahtarKaynagi = "gorev-devri" | null;

let bekleyen: string | null = null;
let kaynak: BekleyenAnahtarKaynagi = null;
const dinleyiciler = new Set<() => void>();

/** Doğrulanmamış anahtar (yoksa null). */
export function bekleyenKurtarmaAnahtari(): string | null {
  return bekleyen;
}

/** Bekleyen anahtarın kaynağı (anahtar yoksa null). */
export function bekleyenAnahtarKaynagi(): BekleyenAnahtarKaynagi {
  return kaynak;
}

/**
 * Anahtarı bekletir (`null`: bırakır). Dinleyen bileşenler yeniden çizilir. `yeniKaynak`
 * yalnız görev devrinde verilir; anahtar bırakılınca kaynak da sıfırlanır.
 */
export function bekleyenKurtarmaAnahtariniYaz(
  anahtar: string | null,
  yeniKaynak: BekleyenAnahtarKaynagi = null,
): void {
  const hedefKaynak = anahtar === null ? null : yeniKaynak;
  if (bekleyen === anahtar && kaynak === hedefKaynak) return;
  bekleyen = anahtar;
  kaynak = hedefKaynak;
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

/** Bekleyen anahtarın kaynağını okuyan kanca. */
export function useBekleyenAnahtarKaynagi(): BekleyenAnahtarKaynagi {
  return useSyncExternalStore(abone, bekleyenAnahtarKaynagi, bekleyenAnahtarKaynagi);
}
