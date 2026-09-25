// Teslimler (F7; U11, tasarım §9-11). Sınıf kitaplığına (şube) ya da öğretmene toplu
// teslim, teslim kayıtları ve geri alma okutması. YALNIZ yönetici kipinde açılır:
// görevli kipinde her adreste görevli ekranı durur; oradan yalnız "Teslimden geri
// alma" okutması açılır (§4.4). Menüde yoktur; Dolaşım Masası sayfasının sağ
// üstündeki "Teslimler" bağlantısıyla açılır.
//
// Teslim ödünç DEĞİLDİR (sözlük): Md. 18 sayı sınırı uygulanmaz, üyelik gerekmez.

import { useState } from "react";

import { useTabParam } from "../../hooks/useTabParam";
import ModuleHeader from "../../ui/ModuleHeader";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import GeriAlmaOkutmasi from "./GeriAlmaOkutmasi";
import TeslimKayitlari from "./TeslimKayitlari";
import YeniTeslim from "./YeniTeslim";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const TESLIMLER_BASLIGI = "Teslimler";
export const TESLIMLER_ADRESI = "/dolasim/teslimler";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["kayitlar", "yeni", "geri-alma"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TABS: TabItem[] = [
  { key: "kayitlar", label: "Teslim Kayıtları", icon: "list_alt" },
  { key: "yeni", label: "Yeni Teslim", icon: "outbox" },
  { key: "geri-alma", label: "Geri Alma", icon: "move_to_inbox" },
];

export default function TeslimlerPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "kayitlar");
  const [tazeleme, setTazeleme] = useState(0);
  const tazele = () => setTazeleme((k) => k + 1);

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader backTo="/dolasim" moduleLabel="Dolaşım Masası" title={TESLIMLER_BASLIGI} />

      <p className="kd-page-description max-w-4xl">
        Kitapların sınıf kitaplığına ya da öğretmene toplu teslimi. Teslim ödünç değildir: sayı
        sınırı ve on beş günlük süre uygulanmaz, kitaplar teslim alanın ödünç hakkından düşmez.
        Teslimdeki kitap katalogda “Sınıf kitaplığında” görünür ve ödünç verilmez. Geri alma,
        kitaplar okutularak yapılır; masadaki görevli de geri alma okutmasını yapabilir.
      </p>

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Teslim bölümleri"
        idBase="teslimler"
      />

      <div {...tabPanelProps("teslimler", tab)}>
        {tab === "kayitlar" && <TeslimKayitlari tazeleme={tazeleme} />}
        {tab === "yeni" && <YeniTeslim onTeslimEdildi={tazele} />}
        {tab === "geri-alma" && <GeriAlmaOkutmasi onGeriAlindi={tazele} />}
      </div>
    </div>
  );
}
