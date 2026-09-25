// İçe Aktarma — katalogun toplu giriş ekranı (tasarım §8.1, §8.2, §8.5).
//
// Dört sekme, dört ayrı iş:
//   * Excel Aktarımı — okulun listesi ya da program şablonu (yöntem A).
//   * Yapay Zekâ Köprüsü — dağınık listeyi biçime sokmanın İSTEĞE BAĞLI yolu;
//     program hiçbir servise bağlanmaz, metni kullanıcı taşır (§8.2).
//   * Çevrimdışı Künye — künyesi eksik eserlerin ISBN listesi dışa aktarılır,
//     internetli başka bir cihazda doldurulur, geri yüklenir (§8.5).
//   * Aktarım Geçmişi — hangi dosya ne zaman aktarıldı.
//
// Sekme adreste tutulur (`?tab=kopru`), böylece kılavuz doğrudan bağlanabilir.
// Kitap kitap giriş (yöntem B, okulun asıl yolu) bu ekranda değil, Katalog →
// Hızlı Kayıt'tadır.

import { useState } from "react";

import { useTabParam } from "../../hooks/useTabParam";
import Button from "../../ui/Button";
import ModuleHeader from "../../ui/ModuleHeader";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import { AktarimBandi } from "../sayim/SayimKarti";
import AktarimGecmisi from "./AktarimGecmisi";
import AktarimPaneli from "./AktarimPaneli";
import CevrimdisiKunyePaneli from "./CevrimdisiKunyePaneli";
import { useBolumler } from "./ortak";
import { useKatalogSablonuIndirme } from "./useKatalogSablonu";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const ICE_AKTARMA_BASLIGI = "İçe Aktarma";

/** İçe Aktarma ekranının adresi (Katalog'dan girilir). */
export const ICE_AKTARMA_ADRESI = "/katalog/ice-aktarma";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["excel", "kopru", "cevrimdisi", "gecmis"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TABS: TabItem[] = [
  { key: "excel", label: "Excel Aktarımı", icon: "upload_file" },
  { key: "kopru", label: "Yapay Zekâ Köprüsü", icon: "smart_toy" },
  { key: "cevrimdisi", label: "Çevrimdışı Künye", icon: "sync_alt" },
  { key: "gecmis", label: "Aktarım Geçmişi", icon: "history" },
];

export default function IceAktarmaPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "excel");
  const bolumler = useBolumler();
  const { indir, indiriliyor } = useKatalogSablonuIndirme();
  // Aktarım uygulandığında geçmiş sekmesi eski listeyi göstermesin.
  const [tazeleme, setTazeleme] = useState(0);

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader
        backTo="/katalog"
        moduleLabel="Katalog"
        title={ICE_AKTARMA_BASLIGI}
        actions={
          <Button
            variant="outlined"
            icon="download"
            onClick={() => void indir()}
            disabled={indiriliyor}
          >
            Katalog Excel şablonu
          </Button>
        }
      />

      <p className="kd-page-description max-w-4xl">
        Eldeki listeyi toplu olarak kataloğa aktarır. Önizleme uygulamanın birebir provasıdır:
        ekrandaki sayılar uygulamanın yazacağı sayılardır ve önizlemede hiçbir kayıt yazılmaz. Kitap
        kitap giriş için Katalog → Hızlı Kayıt ekranını kullanın.
      </p>

      {/* F9: TMY 32/3 durdurması sürerken içe aktarımın önizlemesi de reddedilir. Programa
          aktarım taşınır girişi değildir: bant TMY'ye dayanmaz (F9 ekleri K4). */}
      <AktarimBandi />

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="İçe aktarma bölümleri"
        idBase="ice-aktarma"
      />

      <div {...tabPanelProps("ice-aktarma", tab)}>
        {tab === "excel" && (
          <AktarimPaneli
            kaynak="excel"
            bolumler={bolumler}
            onAktarildi={() => setTazeleme((k) => k + 1)}
          />
        )}
        {tab === "kopru" && (
          <AktarimPaneli
            kaynak="kopru"
            bolumler={bolumler}
            onAktarildi={() => setTazeleme((k) => k + 1)}
          />
        )}
        {tab === "cevrimdisi" && <CevrimdisiKunyePaneli />}
        {tab === "gecmis" && <AktarimGecmisi tazeleme={tazeleme} />}
      </div>
    </div>
  );
}
