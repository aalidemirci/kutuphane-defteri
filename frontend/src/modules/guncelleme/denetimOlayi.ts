// "Güncelleme denetlendi" olayı — Ayarlar → Güncelleme'deki elle denetimin
// sonucunu kabuktaki banda taşır. Program açılışta denetim YAPMAZ (tasarım
// T11: MEB ağında dış istekler engelli olabilir; programın tek dış bağlantısı
// kullanıcının bastığı "Şimdi denetle" düğmesidir). Bant kendi başına istek
// atmaz, yalnız bu olayı dinler. Desen `lib/restart.ts` ile aynıdır.

import type { UpdateStatus } from "./api";

export const DENETIM_OLAYI = "kd:guncelleme-denetlendi";

export function denetimSonucunuYayinla(status: UpdateStatus): void {
  window.dispatchEvent(new CustomEvent<UpdateStatus>(DENETIM_OLAYI, { detail: status }));
}
