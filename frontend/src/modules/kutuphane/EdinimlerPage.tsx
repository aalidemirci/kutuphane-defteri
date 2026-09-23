// Edinimler ve Bağışlar — koleksiyona kaynak girişinin tek ekranı (Md. 10).
//
// Üç sekme, üç ayrı kayıt: "Edinim Partileri" (her nüsha bir partiden gelir),
// "Bağış Ön Kayıtları" (komisyon kararına kadar nüsha AÇILMAZ — Md. 10/3) ve
// "Komisyon Kararları" (Seçim ve Ayıklama Komisyonu; bağış kararı ve ayıklama
// kararı ayrı türlerdir ve birbirinin yerine kullanılamaz).
//
// Bağışçı ve komisyon başkanı adları kişi adıdır: sunucuda şifreli saklanır ve
// yönetici parolası kurulmadan yazılamaz (409 → ui/ErrorBand'in ayrı dalı).

import { useTabParam } from "../../hooks/useTabParam";
import ModuleHeader from "../../ui/ModuleHeader";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import BagisPaneli from "./BagisPaneli";
import EdinimPaneli from "./EdinimPaneli";
import KomisyonPaneli from "./KomisyonPaneli";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const EDINIMLER_BASLIGI = "Edinimler ve Bağışlar";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["partiler", "bagislar", "kararlar"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TABS: TabItem[] = [
  { key: "partiler", label: "Edinim Partileri", icon: "local_shipping" },
  { key: "bagislar", label: "Bağış Ön Kayıtları", icon: "volunteer_activism" },
  { key: "kararlar", label: "Komisyon Kararları", icon: "gavel" },
];

export default function EdinimlerPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "partiler");

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader backTo="/katalog" moduleLabel="Katalog" title={EDINIMLER_BASLIGI} />

      <p className="kd-page-description">
        Kütüphaneye giren her kaynak bir edinim partisine bağlıdır. Bağışta kitaplar önce ön kayda
        yazılır; Seçim ve Ayıklama Komisyonu kararı girilinceye kadar nüsha açılmaz.
      </p>

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Edinim bölümleri"
        idBase="edinimler"
      />

      <div {...tabPanelProps("edinimler", tab)}>
        {tab === "partiler" && <EdinimPaneli />}
        {tab === "bagislar" && <BagisPaneli />}
        {tab === "kararlar" && <KomisyonPaneli />}
      </div>
    </div>
  );
}
