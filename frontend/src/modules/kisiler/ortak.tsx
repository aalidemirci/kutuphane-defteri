// Kişiler sayfasının ortak parçaları: hata bandı (409 `parola_gerekli` dahil),
// durum rozeti ("Ayrıldı · gg.aa.yyyy", "Ayrılış kararı bekliyor") ve API hatasını
// sayfa hatasına çeviren yardımcı. Sayfa (KisilerPage), aktarım paneli
// (AktarimPaneli) ve Ayrılış Havuzu (AyrilisHavuzu) paylaşır.

import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import Icon from "../../ui/Icon";

/** Backend sözleşmesi §2: yönetici parolası kurulmadan kişi yazan uç 409 döner. */
export const PAROLA_GEREKLI_KODU = "parola_gerekli";

/** Sayfada gösterilecek hata: ileti + (varsa) parola kurulmamış olduğu bilgisi. */
export interface SayfaHatasi {
  message: string;
  parolaGerekli: boolean;
}

/** Herhangi bir hatayı sayfa hatasına çevirir; backend iletisi yoksa `yedek` kullanılır. */
export function hataOku(e: unknown, yedek: string): SayfaHatasi {
  if (e instanceof ApiError) {
    return { message: e.message, parolaGerekli: e.code === PAROLA_GEREKLI_KODU };
  }
  return { message: yedek, parolaGerekli: false };
}

/**
 * Hata bandı canlı bölgedir: başarısız yükleme/kaydetme/silme ekran okuyucuya
 * duyurulur. Parola kurulmamışsa (409) ileti okunaklı bir başlıkla verilir ve
 * kullanıcı kurulum sihirbazına yönlendirilir: bu bir "hata" değil, eksik adımdır.
 */
export function ErrorBand({ hata }: { hata: SayfaHatasi | string }) {
  const { message, parolaGerekli } =
    typeof hata === "string" ? { message: hata, parolaGerekli: false } : hata;
  if (parolaGerekli) {
    return (
      <div
        role="alert"
        className="flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container"
      >
        <Icon name="lock" size="lg" className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-label-large">Önce yönetici parolasını kurun</p>
          <p className="mt-1 text-body-medium">{message}</p>
          <Link
            to="/kurulum"
            className="mt-2 inline-flex text-label-large text-primary underline underline-offset-2"
          >
            Kurulum sihirbazını aç
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size="lg" />
      <span>{message}</span>
    </div>
  );
}

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
