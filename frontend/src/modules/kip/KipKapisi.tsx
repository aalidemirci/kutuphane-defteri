// Kip kapısı — görevli kipinde rotaların yerine görevli ekranını koyar.
// `GuvenlikKapisi` ile `KurulumKapisi`'nin İÇİNDE durur: kilitliyken kilit
// ekranı, kurulum bitmeden sihirbaz önce gelir. Kilit açılınca takılır ve kip
// sorgusu (staleTime 0) taze durumu okur.
//
// FAIL-OPEN'dır: kip okunamazsa içerik gösterilir; gerçek kapı backend'dedir
// (`apps/okul/kip_middleware` → 403 `kip_yetkisiz`).
//
// Sihirbaz da bu kapının içindedir: kurulumda görevli kipine düşülürse sihirbaz
// sökülür. Doğrulanmamış kurtarma anahtarı bu yüzden rota ağacının dışında
// bekler (`guvenlik/bekleyenAnahtar`); görevli ekranı bunu kullanıcıya söyler.

import type { ReactNode } from "react";

import { useBekleyenKurtarmaAnahtari } from "../guvenlik/bekleyenAnahtar";
import GorevliEkrani from "./GorevliEkrani";
import { useKip } from "./useKip";

export default function KipKapisi({ children }: { children: ReactNode }) {
  const { ozet, ozetiYaz } = useKip();
  const bekleyenAnahtar = useBekleyenKurtarmaAnahtari();

  if (ozet?.durum === "gorevli") {
    return <GorevliEkrani onGecti={ozetiYaz} anahtarBekliyor={bekleyenAnahtar !== null} />;
  }

  return <>{children}</>;
}
