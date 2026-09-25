// Kütüphane Defteri — kök route tanımı. Route ağacı fazlarla büyür (tasarım
// §14.1): F0 iskeleti kurulum, kişiler, ayarlar, kılavuz ve hakkında
// ekranlarını taşır; F2 katalog ekranlarını (eser, nüsha, edinim, bağış)
// ekledi; F3 toplu aktarım ve hızlı kayıt ekranlarını, F4 etiket ekranını,
// F5 Ağ Doktoru'nu ekledi; dolaşım ve sayım ekranları kendi fazlarında gelir. Kilit ekranı
// (GuvenlikKapisi) kurulum kapısından ÖNCE gelir — parola kuruluysa hiçbir
// veri ekranı (sihirbaz dahil) açılmadan kilit çözülmelidir. Kip kapısı
// (KipKapisi) en içtedir: görevli kipinde rotaların yerine görevli ekranı
// durur (tasarım §4.4).

import { Route, Routes } from "react-router-dom";

import AppShell from "./AppShell";
import KurulumKapisi from "./KurulumKapisi";
import AgDoktoruPage from "./modules/agkatalogu/AgDoktoruPage";
import AyarlarPage from "./modules/ayarlar/AyarlarPage";
import DolasimMasasiPage from "./modules/dolasim/DolasimMasasiPage";
import GuvenlikKapisi from "./modules/guvenlik/GuvenlikKapisi";
import YenidenBaslatEkrani from "./modules/guvenlik/YenidenBaslatEkrani";
import HakkindaPage from "./modules/hakkinda/HakkindaPage";
import KayipHasarPage from "./modules/kayip/KayipHasarPage";
import KilavuzPage from "./modules/kilavuz/KilavuzPage";
import KipKapisi from "./modules/kip/KipKapisi";
import KisilerPage from "./modules/kisiler/KisilerPage";
import KurulumPage from "./modules/kurulum/KurulumPage";
import EdinimlerPage from "./modules/kutuphane/EdinimlerPage";
import EserDetayPage from "./modules/kutuphane/EserDetayPage";
import EtiketlerPage from "./modules/kutuphane/EtiketlerPage";
import HizliKayitPage from "./modules/kutuphane/HizliKayitPage";
import IceAktarmaPage from "./modules/kutuphane/IceAktarmaPage";
import KatalogPage from "./modules/kutuphane/KatalogPage";
import PanelPage from "./modules/panel/PanelPage";
import TeslimlerPage from "./modules/teslim/TeslimlerPage";
import GecikmisOdunclerPage from "./modules/uyelik/GecikmisOdunclerPage";
import IlisikListesiPage from "./modules/yil/IlisikListesiPage";
import YilBasiPage from "./modules/yil/YilBasiPage";
import YilSonuPage from "./modules/yil/YilSonuPage";

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
              {/* Dolaşım Masası (F6, §7.3): ödünç, iade, kartsız ödünç ve istisna.
                  Görevli kipinde aynı masa görevli ekranındadır (KipKapisi). */}
              <Route path="/dolasim" element={<DolasimMasasiPage />} />
              {/* F7: toplu teslim ve geri alma (U11), kayıp/hasar dosyaları (Md. 19, D3).
                  Menüde yok; Dolaşım Masası'nın sağ üstündeki bağlantılarla açılır.
                  Yalnız yönetici kipinde (görevli kipinde geri alma okutması görevli
                  ekranındadır). */}
              <Route path="/dolasim/teslimler" element={<TeslimlerPage />} />
              <Route path="/dolasim/kayip-hasar" element={<KayipHasarPage />} />
              {/* Kurulum sihirbazı — kapının izin verdiği tek rota (bkz. KurulumKapisi). */}
              <Route path="/kurulum" element={<KurulumPage />} />
              {/* Öğrenci + öğretmen sicili ve e-Okul içe aktarma. */}
              <Route path="/kisiler" element={<KisilerPage />} />
              {/* Gecikmiş ödünçler, iade hatırlatma pusulası ve toplu liste (F6, E4);
                  menüde yok, Genel Bakış kartından açılır. Yalnız yönetici kipinde. */}
              <Route path="/gecikmis-oduncler" element={<GecikmisOdunclerPage />} />
              {/* F7: İlişik Listesi, Yıl Sonu ve Yıl Başı akışları (§8.3, E5); menüde yok,
                  Genel Bakış kartlarından açılır. Yalnız yönetici kipinde. */}
              <Route path="/ilisik-listesi" element={<IlisikListesiPage />} />
              <Route path="/yil-sonu" element={<YilSonuPage />} />
              <Route path="/yil-basi" element={<YilBasiPage />} />
              {/* Katalog: eser ve nüsha listeleri, eser ayrıntısı, edinimler ve bağışlar. */}
              <Route path="/katalog" element={<KatalogPage />} />
              <Route path="/katalog/eser/:id" element={<EserDetayPage />} />
              <Route path="/katalog/edinimler" element={<EdinimlerPage />} />
              {/* Toplu katalog aktarımı, yapay zekâ köprüsü ve çevrimdışı künye (F3). */}
              <Route path="/katalog/ice-aktarma" element={<IceAktarmaPage />} />
              {/* Kitap elde, ISBN okutarak tek tek giriş (yöntem B, F3). */}
              <Route path="/katalog/hizli-kayit" element={<HizliKayitPage />} />
              {/* Sırt ve barkod etiketi, basım kaydı, doğrulama, boş barkod aralığı (F4). */}
              <Route path="/katalog/etiketler" element={<EtiketlerPage />} />
              {/* Ders yılı, şubeler, okul künyesi, güvenlik, güncelleme, Ağ Kataloğu. */}
              <Route path="/ayarlar" element={<AyarlarPage />} />
              {/* Ağ Doktoru (F5): Ağ Kataloğu denetimi ve belgeleri; yalnız yönetici kipinde. */}
              <Route path="/ag-doktoru" element={<AgDoktoruPage />} />
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
