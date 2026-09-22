// Genel Bakış (hub) — modül kartları. Sayfanın TEK adı "Genel Bakış"tır
// (gezinme + üst çubuk + h1 — docs/sozluk.md §4); kart başlıkları gittikleri
// sayfanın h1'iyle aynıdır. Pano kartları (başlangıç yol haritası, temiz
// kapanış uyarısı…) kendi fazlarında gelir (tasarım §12, §14.1). "Katalog Excel
// Şablonu" kartı bir sayfaya gitmez, şablonu indirir (tasarım §8.1).

import HubFeatureCard from "../../ui/HubFeatureCard";
import KatalogSablonuKarti from "../kutuphane/KatalogSablonuKarti";

export default function PanelPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <h1 className="text-headline-medium font-semibold tracking-tight text-on-surface">
          Genel Bakış
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Okulun kütüphane işlerini yürüttüğü yerel araç. Veriler yalnız bu bilgisayarda durur.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <HubFeatureCard
          to="/kisiler"
          icon="group"
          title="Kişiler"
          description="Öğrenci, öğretmen ve diğer personel sicili; e-Okul listelerinden içe aktarma."
        />
        <HubFeatureCard
          to="/ayarlar"
          icon="settings"
          title="Ayarlar"
          description="Ders yılı, şubeler, okul bilgileri, güvenlik, yedek ve güncelleme."
        />
      </div>
      <KatalogSablonuKarti />
    </div>
  );
}
