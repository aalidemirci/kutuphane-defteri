// Dolaşım Masası (yönetici kipi) — ödünç, iade, nüsha durumu, kartsız ödünç ve
// gerekçeli istisna (tasarım §7.3, §4.4). Görevli kipinde aynı masa görevli
// ekranındadır (`kip/GorevliEkrani`); bu sayfaya görevli kipinde ulaşılmaz (kip
// kapısı her adreste görevli ekranını gösterir).
//
// F7: sağ üstteki bağlantılar masanın yan ekranlarını açar — Teslimler (sınıf
// kitaplığına ya da öğretmene toplu teslim ve geri alma, U11) ve Kayıp ve Hasar
// (Md. 19 dosyaları, D3). İkisi de yalnız yönetici kipindedir.

import { Link } from "react-router-dom";

import Icon from "../../ui/Icon";
import { KAYIP_HASAR_ADRESI, KAYIP_HASAR_BASLIGI } from "../kayip/KayipHasarPage";
import { TESLIMLER_ADRESI, TESLIMLER_BASLIGI } from "../teslim/TeslimlerPage";
import DolasimMasasi from "./DolasimMasasi";

/** Sayfanın h1'i = üst çubuk başlığı (docs/sozluk.md §4). */
export const DOLASIM_MASASI_BASLIGI = "Dolaşım Masası";

const YAN_EKRANLAR: { to: string; label: string; icon: string }[] = [
  { to: TESLIMLER_ADRESI, label: TESLIMLER_BASLIGI, icon: "outbox" },
  { to: KAYIP_HASAR_ADRESI, label: KAYIP_HASAR_BASLIGI, icon: "report" },
];

export default function DolasimMasasiPage() {
  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{DOLASIM_MASASI_BASLIGI}</h1>
          <p className="kd-page-description">
            Üye kartını ve kitapların kütüphane etiketini okutarak ödünç verin, iadeleri alın. Ödünç
            süresi on beş gündür; iade tarihi kapalı güne rastlarsa izleyen ilk açık güne kayar.
            Kart yanında olmayan üyeye “Kartsız ödünç” ile, gecikmiş ödüncü olan üyeye gerekçeli
            istisnayla ödünç verebilirsiniz; ikisi de ödünç kaydına geçer.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {YAN_EKRANLAR.map((ekran) => (
            <Link
              key={ekran.to}
              to={ekran.to}
              className="inline-flex min-h-[var(--kd-control-height)] items-center gap-2 rounded-shape-md border border-outline-variant bg-surface-container-lowest px-4 text-label-large font-semibold text-primary transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Icon name={ekran.icon} size="lg" />
              {ekran.label}
            </Link>
          ))}
        </div>
      </div>
      <DolasimMasasi gorevli={false} />
    </div>
  );
}
