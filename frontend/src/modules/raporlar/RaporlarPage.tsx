// Raporlar (F10; tasarım §14.1 F10, §8.4, §10 E11/E12/E17/E20).
//
// Dört sekme:
//   * İstatistik — kişisiz, k eşikli sayılar (koleksiyon, edinim, dolaşım, teslim, kayıp ve
//     hasar, ayıklama ve devir); eşik altı "—".
//   * Çok Okunanlar — dönem ve ay listeleri (sayısız), "Yeniden hesapla", Ayın Kitapları afişi.
//   * Dökümler — dışa aktarım ve üye özeti, alfabetik katalog dökümü, Taşınır Kütüphane Defteri
//     dökümü, yönetim hesabı cetveli hazırlığı ve kişi dökümü (`modules/dokumler`).
//   * Okuma Ödülü — okuma ödülü iç çıktısı ("iç kullanım"; adlar yalnız PDF'te).
//
// Sekme adreste tutulur (`?tab=dokumler`), kılavuz ve Genel Bakış kartları doğrudan bağlanır.
// Kip: bütün uçlar yönetici kipindedir (görevli kipinde KipKapisi her adreste görevli ekranını
// koyar; uçlar 403 `kip_yetkisiz` döner). Sayfa kayıt yazmaz; tek yazan "Yeniden hesapla"dır
// ve yalnız kişisiz sıra tablosunu yazar.

import { useTabParam } from "../../hooks/useTabParam";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import DokumlerBolumu from "../dokumler/DokumlerBolumu";
import { RAPORLAR_BASLIGI, RAPOR_SEKMELERI } from "./api";
import type { RaporSekmesi } from "./api";
import CokOkunanlarBolumu from "./CokOkunanlarBolumu";
import IstatistikBolumu from "./IstatistikBolumu";
import OkumaOduluBolumu from "./OkumaOduluBolumu";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["istatistik", "cok-okunanlar", "dokumler", "okuma-odulu"] as const;

const TABS: TabItem[] = [
  { key: "istatistik", label: RAPOR_SEKMELERI.istatistik, icon: "bar_chart" },
  { key: "cok-okunanlar", label: RAPOR_SEKMELERI["cok-okunanlar"], icon: "trending_up" },
  { key: "dokumler", label: RAPOR_SEKMELERI.dokumler, icon: "description" },
  { key: "okuma-odulu", label: RAPOR_SEKMELERI["okuma-odulu"], icon: "workspace_premium" },
];

export default function RaporlarPage() {
  const [tab, setTab] = useTabParam<RaporSekmesi>("tab", TAB_KEYS, "istatistik");

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{RAPORLAR_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            Kütüphanenin kişisiz sayıları, çok okunanlar, dökümler ve dışa aktarım. Sayılar
            programdaki kayıtlardan gelir; bu sayfa katalog, üye ve ödünç kayıtlarını değiştirmez.
            Ödünç kaydı okunan kitabı göstermez: adlı sıralama yalnız Okuma Ödülü sekmesindeki iç
            çıktıda basılır.
          </p>
        </div>
      </div>

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as RaporSekmesi)}
        ariaLabel="Rapor bölümleri"
        idBase="raporlar"
      />

      <div {...tabPanelProps("raporlar", tab)}>
        {tab === "istatistik" && <IstatistikBolumu />}
        {tab === "cok-okunanlar" && <CokOkunanlarBolumu />}
        {tab === "dokumler" && <DokumlerBolumu />}
        {tab === "okuma-odulu" && <OkumaOduluBolumu />}
      </div>
    </div>
  );
}
