// Okul bilgilerinin zorunlu alan denetimi — kurulum sihirbazının 2. adımı ve
// Ayarlar → Okul Bilgileri AYNI kuralı kullanır. Küme backend'dekiyle aynıdır:
// `services/setup.py::missing_school_fields` (kurulumu tamamlama kapısı) ve
// `SchoolConfigSerializer.validate_*` (kurulumdan sonra boşaltma reddi). İletiler
// de backend'le birebir aynıdır; biri değişirse öteki de değişmeli.

import type { SchoolLevel } from "./api";

export interface OkulZorunluAlanlari {
  okulAdi: string;
  kademe: SchoolLevel | "";
  kisaAd: string;
  demirbasOnayi: boolean;
}

/** Eksik zorunlu alanlar → alan adı (backend alan kodu) → Türkçe ileti. */
export function okulBilgileriHatalari(f: OkulZorunluAlanlari): Record<string, string> {
  const hatalar: Record<string, string> = {};
  if (!f.okulAdi.trim()) hatalar.school_name = "Okul adı zorunludur.";
  if (!f.kademe) hatalar.kademe = "Kademe seçin.";
  if (!f.kisaAd.trim()) hatalar.kisa_ad = "Kısa ad zorunludur.";
  if (!f.demirbasOnayi) {
    hatalar.demirbas_onayi = "Program yalnız okul demirbaşı bilgisayara kurulur; onay zorunludur.";
  }
  return hatalar;
}
