// Etiketler — sırt ve barkod etiketlerinin basımı, basım kaydı, doğrulama
// okutması, boş barkod aralığı ve tabaka şablonları (tasarım §7.2, §8.1, F4).
//
// Beş sekme, iş sırasıyla:
//   * Basım Kuyruğu — etiketi basılmamış nüshalar; içerik (sırt / barkod /
//     ikisi birden), süzgeç, basım sırası (D20), şablon + yazıcı + başlangıç
//     hücresi → basım partisi → PDF → "Basıldı olarak işaretle" (D10).
//   * Basım Geçmişi — partiler, geri alma ve yeniden basım.
//   * Boş Barkod Aralığı — önce etiket yolu (okulun ASIL yolu, S8): numara
//     ayır → boş etiket bas → Hızlı Kayıt'ta kitaba bağla; kullanılmayanı iptal et.
//   * Doğrulama Okutması — yapıştırılan etiketi okut (okuyucunun odağı kutuda kalır).
//   * Şablonlar ve Kalibrasyon — tabaka ölçüleri ve yazıcı kayması (E1).
//
// Sekme adreste tutulur (`?tab=bos-barkod`), böylece kılavuz ve başka ekranlar
// doğrudan bağlanır. İçe aktarmanın "bu partinin etiketlerini bas" kısayolu
// `?edinim=<id>` ile kuyruğu o partiye süzer.
//
// Kip: bu ekran yönetici kipindedir (görevli kipinde KipKapisi rotanın yerine
// görevli ekranını koyar). Görevli kipinde açık tek etiket işi doğrulama
// okutmasıdır ve görevli ekranından açılır (`kip/GorevliEkrani`); öbür uçlar
// 403 `kip_yetkisiz` döner (`lib/api.ts` üzerinden kip olayına düşer).

import { useEffect, useState } from "react";

import { useTabParam } from "../../hooks/useTabParam";
import { formatNumber } from "../../lib/format";
import ErrorBand from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import ModuleHeader from "../../ui/ModuleHeader";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import BasimGecmisi from "./BasimGecmisi";
import BosBarkodPaneli from "./BosBarkodPaneli";
import DogrulamaOkutmasi from "./DogrulamaOkutmasi";
import EtiketKuyrugu from "./EtiketKuyrugu";
import { etiketApi } from "./etiketApi";
import type { EtiketOzeti } from "./etiketApi";
import { useEtiketSablonlari } from "./etiketOrtak";
import { useBolumler } from "./ortak";
import SablonlarPaneli from "./SablonlarPaneli";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const ETIKETLER_BASLIGI = "Etiketler";

/** Etiketler ekranının adresi (Katalog'dan girilir). */
export const ETIKETLER_ADRESI = "/katalog/etiketler";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["kuyruk", "gecmis", "bos-barkod", "dogrulama", "sablonlar"] as const;
type TabKey = (typeof TAB_KEYS)[number];

/** Sekme adları — Başlık Düzeninde (docs/sozluk.md §4.3); kılavuz buradan doğrulanır. */
export const ETIKETLER_SEKMELERI: Record<TabKey, string> = {
  kuyruk: "Basım Kuyruğu",
  gecmis: "Basım Geçmişi",
  "bos-barkod": "Boş Barkod Aralığı",
  dogrulama: "Doğrulama Okutması",
  sablonlar: "Şablonlar ve Kalibrasyon",
};

const TABS: TabItem[] = [
  { key: "kuyruk", label: ETIKETLER_SEKMELERI.kuyruk, icon: "print" },
  { key: "gecmis", label: ETIKETLER_SEKMELERI.gecmis, icon: "history" },
  { key: "bos-barkod", label: ETIKETLER_SEKMELERI["bos-barkod"], icon: "label" },
  { key: "dogrulama", label: ETIKETLER_SEKMELERI.dogrulama, icon: "barcode_reader" },
  { key: "sablonlar", label: ETIKETLER_SEKMELERI.sablonlar, icon: "straighten" },
];

export default function EtiketlerPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "kuyruk");
  const bolumler = useBolumler();
  const sablonDurumu = useEtiketSablonlari();
  const [ozet, setOzet] = useState<EtiketOzeti | null>(null);
  // Bir sekmede yazma olunca (parti onayı, ayırma, okutma) sayaçlar ve öbür
  // sekmelerin listeleri tazelenir.
  const [tazeleme, setTazeleme] = useState(0);
  const tazele = () => setTazeleme((k) => k + 1);

  useEffect(() => {
    let iptal = false;
    etiketApi
      .ozet()
      .then((sonuc) => {
        if (!iptal) setOzet(sonuc);
      })
      .catch(() => {
        // Sayaçlar yalnız bilgidir; okunamazsa şerit gösterilmez.
        if (!iptal) setOzet(null);
      });
    return () => {
      iptal = true;
    };
  }, [tazeleme]);

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader backTo="/katalog" moduleLabel="Katalog" title={ETIKETLER_BASLIGI} />

      <p className="kd-page-description max-w-4xl">
        Sırt ve barkod etiketlerini basar, basılanı kayda geçirir ve yapıştırılan etiketi okutarak
        doğrular. PDF'i almak “basıldı” saymaz: tabakayı denetleyip “Basıldı olarak işaretle”
        dediğinizde nüshalar kuyruktan çıkar ve bu işaret geri alınabilir.
      </p>

      {sablonDurumu.hata && <ErrorBand hata={sablonDurumu.hata} />}
      {ozet && <OzetSeridi ozet={ozet} onSekme={(key) => setTab(key)} />}

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Etiket bölümleri"
        idBase="etiketler"
      />

      <div {...tabPanelProps("etiketler", tab)}>
        {tab === "kuyruk" && (
          <EtiketKuyrugu
            bolumler={bolumler}
            sablonlar={sablonDurumu.sablonlar}
            tazeleme={tazeleme}
            onDegisti={tazele}
            onGecmis={() => setTab("gecmis")}
          />
        )}
        {tab === "gecmis" && (
          <BasimGecmisi sablonlar={sablonDurumu.sablonlar} tazeleme={tazeleme} onDegisti={tazele} />
        )}
        {tab === "bos-barkod" && (
          <BosBarkodPaneli
            sablonlar={sablonDurumu.sablonlar}
            tazeleme={tazeleme}
            onDegisti={tazele}
          />
        )}
        {tab === "dogrulama" && <DogrulamaOkutmasi tazeleme={tazeleme} onDegisti={tazele} />}
        {tab === "sablonlar" && (
          <SablonlarPaneli
            sablonlar={sablonDurumu.sablonlar}
            yukleniyor={sablonDurumu.yukleniyor}
            onDegisti={sablonDurumu.yenile}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Kişisiz sayaçlar: kuyruk, onay bekleyen parti, doğrulanmamış etiket, açık
 * boş etiket. Onay bekleyen parti varsa uyarı olarak öne çıkar — PDF'i alınıp
 * işaretlenmeyen parti, aynı etiketin ikinci kez basılmasının en sık nedenidir.
 */
function OzetSeridi({ ozet, onSekme }: { ozet: EtiketOzeti; onSekme: (key: TabKey) => void }) {
  const kalemler: Array<{ etiket: string; deger: number; sekme: TabKey; ikon: string }> = [
    { etiket: "Sırt etiketi bekleyen", deger: ozet.queue.SPINE, sekme: "kuyruk", ikon: "print" },
    {
      etiket: "Barkod etiketi bekleyen",
      deger: ozet.queue.BARCODE,
      sekme: "kuyruk",
      ikon: "print",
    },
    {
      etiket: "Doğrulanmamış etiket",
      deger: ozet.unverified,
      sekme: "dogrulama",
      ikon: "barcode_reader",
    },
    {
      etiket: "Bağlanmamış boş etiket",
      deger: ozet.reservations.open,
      sekme: "bos-barkod",
      ikon: "label",
    },
  ];
  return (
    <div className="space-y-2">
      {ozet.pending_batches > 0 && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
        >
          <Icon name="hourglass_top" size="lg" className="shrink-0" />
          <span className="min-w-0 flex-1">
            {formatNumber(ozet.pending_batches)} basım partisi onay bekliyor. PDF'i yazdırdıysanız
            Basım Geçmişi'nde “Basıldı olarak işaretle” deyin; yazdırmadıysanız partiden vazgeçin.
          </span>
          <button
            type="button"
            onClick={() => onSekme("gecmis")}
            className="text-label-large text-primary underline underline-offset-2"
          >
            Basım Geçmişi'ni aç
          </button>
        </div>
      )}
      <ul className="flex flex-wrap gap-2" aria-label="Etiket sayaçları">
        {kalemler.map((k) => (
          <li key={k.etiket}>
            <button
              type="button"
              onClick={() => onSekme(k.sekme)}
              className="inline-flex min-h-10 items-center gap-2 rounded-full border border-outline-variant bg-surface-container-lowest px-3 text-label-large text-on-surface transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Icon name={k.ikon} size="sm" className="text-primary" />
              {k.etiket}: {formatNumber(k.deger)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
