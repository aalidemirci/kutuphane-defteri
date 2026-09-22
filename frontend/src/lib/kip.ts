// "Kip yetkisiz" olayı — backend kip kapısının (`apps/okul/kip_middleware`)
// arayüz ayağı. Görevli kipinde izin listesi dışındaki bir uç 403
// `kip_yetkisiz` döner; bu genelde kipin arayüzün haberi olmadan değiştiği
// anlamına gelir (boşta süre ya da mutlak süre sunucuda doldu). `lib/api.ts`
// bu kodu görünce olayı yayınlar; kip sorgusu (`modules/kip/useKip`) dinler ve
// yenilenir, ekran görevli kipine geçer. `lib/restart.ts` deseni.

export const KIP_YETKISIZ_OLAYI = "kd:kip-yetkisiz";

/** 403 gövdesindeki kod — oturum belirteci 403'ünden bununla ayrılır. */
export const KIP_YETKISIZ_KODU = "kip_yetkisiz";

export function kipYetkisizYayinla(): void {
  window.dispatchEvent(new CustomEvent(KIP_YETKISIZ_OLAYI));
}
