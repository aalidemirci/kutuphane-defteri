// Sayfa hata bandı — yükleme/kaydetme/silme başarısız olduğunda görünen canlı bölge.
// Kişiler sayfasında doğdu (F1), F2'de katalog ekranları da aynı iki durumu taşıdığı
// için ortak kite alındı; `modules/kisiler/ortak.tsx` buradan yeniden dışa verir.
//
// İki durum vardır:
//   1) olağan hata → kırmızı bant, backend iletisi olduğu gibi;
//   2) 409 `parola_gerekli` → bu bir "hata" değil, eksik adımdır: yönetici parolası
//      kurulmadan şifreli alana (kişi adı, bağışçı, komisyon başkanı) yazılamaz
//      (tasarım §6.3, F1 sözleşmesi §2). Kullanıcı sihirbaza yönlendirilir.

import { Link } from "react-router-dom";

import { ApiError } from "../lib/api";
import Icon from "./Icon";

/** Backend sözleşmesi §2: yönetici parolası kurulmadan şifreli alan yazan uç 409 döner. */
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
export default function ErrorBand({ hata }: { hata: SayfaHatasi | string }) {
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
