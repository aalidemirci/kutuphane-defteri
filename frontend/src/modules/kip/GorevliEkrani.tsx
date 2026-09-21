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

export default function GorevliEkrani({ onGecti }: { onGecti: (ozet: KipOzeti) => void }) {
  const [diyalogAcik, setDiyalogAcik] = useState(false);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card elevation={1} className="w-full max-w-lg p-8 text-center">
        <Icon name="badge" size="5xl" className="text-primary" />
        <h1 className="mt-3 text-headline-small text-on-surface">{GOREVLI_EKRANI_BASLIGI}</h1>
        <p className="mt-3 text-body-medium text-on-surface-variant">{GOREVLI_EKRANI_METNI}</p>
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
