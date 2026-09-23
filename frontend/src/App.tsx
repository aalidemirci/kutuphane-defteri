// Kütüphane Defteri — kök route tanımı. Route ağacı fazlarla büyür (tasarım
// §14.1): F0 iskeleti kurulum, kişiler, ayarlar, kılavuz ve hakkında
// ekranlarını taşır; F2 katalog ekranlarını (eser, nüsha, edinim, bağış)
// ekledi; dolaşım ve sayım ekranları kendi fazlarında gelir. Kilit ekranı
// (GuvenlikKapisi) kurulum kapısından ÖNCE gelir — parola kuruluysa hiçbir
// veri ekranı (sihirbaz dahil) açılmadan kilit çözülmelidir. Kip kapısı
// (KipKapisi) en içtedir: görevli kipinde rotaların yerine görevli ekranı
// durur (tasarım §4.4).

import { Route, Routes } from "react-router-dom";

import AppShell from "./AppShell";
import KurulumKapisi from "./KurulumKapisi";
import AyarlarPage from "./modules/ayarlar/AyarlarPage";
import GuvenlikKapisi from "./modules/guvenlik/GuvenlikKapisi";
import YenidenBaslatEkrani from "./modules/guvenlik/YenidenBaslatEkrani";
import HakkindaPage from "./modules/hakkinda/HakkindaPage";
import KilavuzPage from "./modules/kilavuz/KilavuzPage";
import KipKapisi from "./modules/kip/KipKapisi";
import KisilerPage from "./modules/kisiler/KisilerPage";
import KurulumPage from "./modules/kurulum/KurulumPage";
import EdinimlerPage from "./modules/kutuphane/EdinimlerPage";
import EserDetayPage from "./modules/kutuphane/EserDetayPage";
import KatalogPage from "./modules/kutuphane/KatalogPage";
import PanelPage from "./modules/panel/PanelPage";

export default function App() {
  return (
    <AppShell>
      {/* Geri yükleme sonrası tam ekran "yeniden başlatın" örtüsü — kapıların
          DIŞINDA: kilit/kurulum durumu ne olursa olsun her şeyi örtmelidir. */}
      <YenidenBaslatEkrani />
      <GuvenlikKapisi>
        <KurulumKapisi>
          <KipKapisi>
            <Routes>
              <Route path="/" element={<PanelPage />} />
              {/* Kurulum sihirbazı — kapının izin verdiği tek rota (bkz. KurulumKapisi). */}
              <Route path="/kurulum" element={<KurulumPage />} />
              {/* Öğrenci + öğretmen sicili ve e-Okul içe aktarma. */}
              <Route path="/kisiler" element={<KisilerPage />} />
              {/* Katalog: eser ve nüsha listeleri, eser ayrıntısı, edinimler ve bağışlar. */}
              <Route path="/katalog" element={<KatalogPage />} />
              <Route path="/katalog/eser/:id" element={<EserDetayPage />} />
              <Route path="/katalog/edinimler" element={<EdinimlerPage />} />
              {/* Ders yılı, şubeler, okul künyesi, güvenlik, güncelleme. */}
              <Route path="/ayarlar" element={<AyarlarPage />} />
              {/* Kullanım kılavuzu (statik içerik, çevrimdışı). */}
              <Route path="/kilavuz" element={<KilavuzPage />} />
              <Route path="/hakkinda" element={<HakkindaPage />} />
            </Routes>
          </KipKapisi>
        </KurulumKapisi>
      </GuvenlikKapisi>
    </AppShell>
  );
}
