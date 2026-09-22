// Görevli kipinin ana ekranı (U5, tasarım §4.4). Görevli kipinde rotaların
// YERİNE gösterilir: masadaki görevli yönetici ekranlarına (kişiler, ayarlar,
// yedek…) ulaşamaz. Backend bunu ayrıca keser (403 `kip_yetkisiz`); bu ekran
// kullanıcıya boş ya da hata dolu sayfalar yerine ne yapacağını söyler.
// Dolaşım masası bu ekrana kendi fazında eklenir; metin gelecek vadetmez.

import { useState } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import YoneticiParolaDiyalogu from "./YoneticiParolaDiyalogu";
import type { KipOzeti } from "./api";

/** Üst çubuk başlığı sayfanın h1'iyle aynıdır (docs/sozluk.md §4). */
export const GOREVLI_EKRANI_BASLIGI = "Görevli Kipi";

export const GOREVLI_EKRANI_METNI =
  "Bu kipte yalnız masa işleri yapılır; yönetici işlemleri için yönetici kipine geçin.";

/**
 * Kurulum sırasında, kurtarma anahtarı doğrulanmadan görevli kipine düşülürse
 * (boşta süre, Kilitle, kısayol) gösterilir: anahtar kaybolmadı, yönetici kipine
 * dönülünce sihirbaz onu yeniden gösterir (`guvenlik/bekleyenAnahtar`).
 */
export const BEKLEYEN_ANAHTAR_METNI =
  "Kurtarma anahtarınız henüz doğrulanmadı. Yönetici kipine geçtiğinizde Kurulum Sihirbazı anahtarı yeniden gösterir; programı kapatmayın.";

export default function GorevliEkrani({
  onGecti,
  anahtarBekliyor = false,
}: {
  onGecti: (ozet: KipOzeti) => void;
  /** Kurulumda doğrulanmamış kurtarma anahtarı bellekte bekliyor mu? */
  anahtarBekliyor?: boolean;
}) {
  const [diyalogAcik, setDiyalogAcik] = useState(false);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card elevation={1} className="w-full max-w-lg p-8 text-center">
        <Icon name="badge" size="5xl" className="text-primary" />
        <h1 className="mt-3 text-headline-small text-on-surface">{GOREVLI_EKRANI_BASLIGI}</h1>
        <p className="mt-3 text-body-medium text-on-surface-variant">{GOREVLI_EKRANI_METNI}</p>
        {anahtarBekliyor && (
          <p className="mt-4 flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-left text-body-medium text-on-tertiary-container">
            <Icon name="key" size="lg" />
            <span>{BEKLEYEN_ANAHTAR_METNI}</span>
          </p>
        )}
        <div className="mt-6 flex justify-center">
          <Button icon="admin_panel_settings" onClick={() => setDiyalogAcik(true)}>
            Yönetici kipine geç
          </Button>
        </div>
      </Card>
      <YoneticiParolaDiyalogu
        open={diyalogAcik}
        onClose={() => setDiyalogAcik(false)}
        onGecti={onGecti}
      />
    </div>
  );
}
