// Dolaşım Masası (yönetici kipi) — ödünç, iade, nüsha durumu, kartsız ödünç ve
// gerekçeli istisna (tasarım §7.3, §4.4). Görevli kipinde aynı masa görevli
// ekranındadır (`kip/GorevliEkrani`); bu sayfaya görevli kipinde ulaşılmaz (kip
// kapısı her adreste görevli ekranını gösterir).

import DolasimMasasi from "./DolasimMasasi";

/** Sayfanın h1'i = üst çubuk başlığı (docs/sozluk.md §4). */
export const DOLASIM_MASASI_BASLIGI = "Dolaşım Masası";

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
      </div>
      <DolasimMasasi gorevli={false} />
    </div>
  );
}
