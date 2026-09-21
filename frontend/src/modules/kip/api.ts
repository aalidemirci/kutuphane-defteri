// `kip` modülü API istemcisi — görevli kipi / yönetici kipi (tasarım §4.4).
// Backend `apps/okul/views_mode.py` ve `apps/okul/kip.py::KipDurumu.ozet` ile
// BİREBİR. Yönetici parolası yalnız gövdede taşınır, hiçbir yanıtta dönmez.

import { api } from "../../lib/api";

/** Backend `apps/okul/kip.py` durumları. */
export type KipAdi = "kurulum" | "kilitli" | "guvenlik_dosyasi_kayip" | "yonetici" | "gorevli";

/** `GET /security/mode/` yanıtı. */
export interface KipOzeti {
  durum: KipAdi;
  /** Boşta kalınırsa görevli kipine inmeye kalan saniye (yalnız yönetici kipinde). */
  bosta_kalan_sn: number | null;
  /** Etkinlikten bağımsız mutlak süreden kalan saniye (yalnız yönetici kipinde). */
  mutlak_kalan_sn: number | null;
  /** Ayarlı boşta süresi (dakika). */
  bosta_dk: number;
  /** Ayarlı mutlak süre (dakika). */
  mutlak_dk: number;
}

export const kipApi = {
  /**
   * Kip özeti. Varsayılan olarak `X-KD-Etkinlik` GÖNDERMEZ: periyodik yoklama
   * yönetici kipini canlı tutmamalıdır (§5.10-14). `etkinlik: true` yalnız
   * gerçek bir etkileşimin hemen ardından verilir (etkinlik nabzı, `useKip`).
   */
  durum: (etkinlik = false) => api.get<KipOzeti>("/security/mode/", { etkinlik }),
  gorevliyeGec: () => api.post<KipOzeti>("/security/mode/staff/"),
  yoneticiyeGec: (password: string) => api.post<KipOzeti>("/security/mode/admin/", { password }),
  /** Kilitle her kipte parolasızdır; mevcut kilit ucu kullanılır. */
  kilitle: () => api.post<unknown>("/security/lock/"),
};
