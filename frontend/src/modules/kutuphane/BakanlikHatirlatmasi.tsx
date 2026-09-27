// "Bakanlık sistemi kullanımda" hatırlatması (A21 — tasarım §3 "Çıkış planı", F10).
//
// Kütüphane Politikası'ndaki ayar VARSAYILAN KAPALIDIR; açıkken ayrılış (Kişiler → Ayrılış
// Havuzu ve Kişiler ekranındaki "Ayrıldı olarak işaretle" onayı — F10 düzeltme turu, tasarım
// §9-8 ayrılışın yolunu ayırmaz) ve İlişik Listesi ekranları, kaydın Bakanlık otomasyon sisteminde de
// güncellenmesini hatırlatır. Konum dili (CLAUDE.md §2-13, sözlük §1): program okulun
// kütüphane işlerini yürüttüğü yerel araçtır; o sisteme bağlanmaz ve yerine geçmez.
//
// Bant ayarı kendisi okur; ayar okunamazsa (ör. yetkisiz kip) hiçbir şey çizmez — hatırlatma
// ekranın işini engellemez.

import { useEffect, useState } from "react";

import Icon from "../../ui/Icon";
import { kutuphaneApi } from "./api";

/** Ayarın adı (Kütüphane Politikası → Bakanlık Sistemi). */
export const BAKANLIK_SISTEMI_AYARI = "Bakanlık sistemi kullanımda";
/** Konum cümlesi — iki hatırlatmanın ve ayar açıklamasının ortak sonu. */
export const KONUM_CUMLESI =
  "Kütüphane Defteri okulun kütüphane işlerini yürüttüğü yerel araçtır; Bakanlık otomasyon " +
  "sistemine bağlanmaz ve o sistemin yerine geçmez.";
export const AYRILIS_HATIRLATMASI =
  "Okuldan ayrılan kişi için Bakanlık otomasyon sistemindeki kaydı da güncelleyin. " +
  KONUM_CUMLESI;
export const ILISIK_HATIRLATMASI =
  "İlişik ve iade işlemlerinde Bakanlık otomasyon sistemindeki kaydı da güncelleyin. " +
  KONUM_CUMLESI;

/**
 * Ayar açık mı? (okunamazsa kapalı sayılır — hatırlatma ekranın işini engellemez). Onay
 * pencerelerinin metnine hatırlatma ekleyen ekranlar da bunu kullanır.
 */
export function useBakanlikSistemi(): boolean {
  const [acik, setAcik] = useState(false);

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .getPolicy()
      .then((p) => {
        if (!iptal) setAcik(Boolean(p.ministry_system_in_use));
      })
      .catch(() => {
        if (!iptal) setAcik(false);
      });
    return () => {
      iptal = true;
    };
  }, []);
  return acik;
}

export default function BakanlikHatirlatmasi({ metin }: { metin: string }) {
  const acik = useBakanlikSistemi();
  if (!acik) return null;
  return (
    <p
      role="note"
      aria-label={BAKANLIK_SISTEMI_AYARI}
      className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-small text-on-secondary-container"
    >
      <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
      <span>{metin}</span>
    </p>
  );
}
