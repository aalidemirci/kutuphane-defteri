// Kullanım Kılavuzu — statik içerik, çevrimdışı. Kabuk korunur, içerik
// yeniden yazılır (tasarım §12): her fazın "kılavuz bölümü" iş kalemiyle
// (§14.1) bölümler özelliklerle birlikte eklenir. Kalıp HakkindaPage'den:
// max-w-4xl kap, üstbaşlık üçlüsü, bölüm başına Card + 44px ikon rozeti.
// Mevzuat atıfları yalnız `docs/mevzuat/`'taki tam metinlerden alınır; madde
// numarası uydurulmaz.

import Card from "../../ui/Card";
import Icon from "../../ui/Icon";

export default function KilavuzPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <p className="text-label-medium font-semibold tracking-wide text-primary">
          Kütüphane Defteri
        </p>
        <h1 className="mt-1 text-headline-medium font-semibold tracking-tight text-on-surface">
          Kullanım Kılavuzu
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Programın adım adım anlatımı. Program çevrimdışı çalışır, veriler yalnız bu bilgisayarda
          durur.
        </p>
      </header>

      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-primary-container text-on-primary-container">
            <Icon name="edit_note" size="xl" />
          </span>
          <div className="min-w-0">
            <h2 className="text-title-large font-semibold text-on-surface">Hazırlanıyor</h2>
            <p className="mt-3 text-body-medium text-on-surface-variant">
              Kılavuz, özellikler geldikçe yazılacak. Şimdilik kurulum sihirbazı, Kişiler ve Ayarlar
              ekranlarındaki açıklamalar yol gösterir.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
