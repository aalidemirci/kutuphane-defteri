// Kişiler sayfasının ortak parçaları: durum rozeti ("Ayrıldı · gg.aa.yyyy",
// "Ayrılış kararı bekliyor") ve Ayrılış Havuzu'nun adresi. Sayfa (KisilerPage),
// aktarım paneli (AktarimPaneli) ve Ayrılış Havuzu (AyrilisHavuzu) paylaşır.
//
// Hata bandı ve `hataOku` F2'de `ui/ErrorBand`'e taşındı (katalog ekranları da
// aynı iki durumu taşıyor); buradan yeniden dışa verilir, çağrı yerleri değişmedi.

import { formatDate } from "../../lib/format";
import Icon from "../../ui/Icon";

export { default as ErrorBand, hataOku, PAROLA_GEREKLI_KODU } from "../../ui/ErrorBand";
export type { SayfaHatasi } from "../../ui/ErrorBand";

/** Ayrılış Havuzu sekmesinin adresi (Kişiler → `?tab=havuz`). */
export const HAVUZ_ADRESI = "/kisiler?tab=havuz";

/**
 * Sicil durum rozeti: aktif kişide "Aktif", ayrılmışta "Ayrıldı · gg.aa.yyyy".
 * Ayrılış havuzundaki (aktif) kişide ek rozet: "Ayrılış kararı bekliyor".
 */
export function DurumRozeti({
  aktif,
  leftAt,
  havuzda = false,
}: {
  aktif: boolean;
  leftAt: string | null;
  havuzda?: boolean;
}) {
  if (aktif && havuzda) {
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <span>Aktif</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-tertiary-container px-2 py-0.5 text-label-medium text-on-tertiary-container">
          <Icon name="pending_actions" size="sm" />
          Ayrılış kararı bekliyor
        </span>
      </span>
    );
  }
  if (aktif) return <span>Aktif</span>;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-highest px-2 py-0.5 text-label-medium text-on-surface-variant">
      <Icon name="logout" size="sm" />
      {leftAt ? `Ayrıldı · ${formatDate(leftAt)}` : "Ayrıldı"}
    </span>
  );
}
