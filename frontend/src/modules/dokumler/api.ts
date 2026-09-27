// Dökümler ve dışa aktarım (F10 — D kolu) istemcisi: dışa aktarım dosyası (tasarım §8.4),
// üye özeti (kişisiz), alfabetik katalog dökümü (E17), Taşınır Kütüphane Defteri dökümü ve
// yönetim hesabı cetveli hazırlığı (E11), kişi dökümü (KVKK md. 11).
//
// Uçların hepsi YÖNETİCİ KİPİNDEDİR (görevli kipi izin listesinde yok). Kişi aramada okul no
// sorgu dizesine yazılmaz, POST gövdesiyle gider. Rapor biçimi `?kind=pdf|xlsx`.

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";

export type Bicim = "pdf" | "xlsx";
export type KatalogEkseni = "title" | "author" | "subject";
export type KisiTuru = "student" | "personnel";

/** Belge adları (sözlük §2 — E11, E17) ve kartların başlıkları. */
export const DISA_AKTARIM_ADI = "Katalog dışa aktarımı";
export const ALFABETIK_KATALOG_ADI = "Alfabetik katalog dökümü";
export const DEFTER_DOKUMU_ADI = "Taşınır Kütüphane Defteri dökümü";
export const YONETIM_HESABI_ADI = "Yönetim hesabı cetveli hazırlığı";
export const KISI_DOKUMU_ADI = "Kişi dökümü";
/** E17 bölüm süzgecinde bölümü yazılmamış eserler (backend `katalog_dokumu.SECTION_NONE`). */
export const BOLUMSUZ = 0;
export const BOLUMSUZ_ADI = "Bölümü yazılmamış";

/** `GET library/reports/documents/` — Dökümler bölümünün özeti. */
export interface DokumOzeti {
  export: { works: number; copies: number; exited: number };
  catalog_listing: {
    works: number;
    copies: number;
    axes: Array<{ value: KatalogEkseni; label: string }>;
    sections: Array<{ id: number; name: string }>;
    /** Bölümü yazılmamış eser sayısı (seçicide "Bölümü yazılmamış" — sorguda `section=0`). */
    unsectioned_works: number;
  };
  library_register: { years: number[] };
  management_account: { stocktakes: YilSonuSayimi[] };
}

/** Yıl sonu işaretli sayım — yönetim hesabı cetveli hazırlığının seçicisi. */
export interface YilSonuSayimi {
  id: number;
  name: string;
  fiscal_year: number | null;
  status: string;
  status_display: string;
  approved_on: string | null;
  available: boolean;
  reason: string;
}

/** `GET library/export/member-summary/` — KİŞİSİZ sayılar. */
export interface UyeOzeti {
  total: number;
  by_type: Array<{ member_type: string; label: string; count: number }>;
  by_class: Array<{
    class_level: number;
    class_section: string;
    class_label: string;
    count: number;
  }>;
  students_without_class: number;
}

/** Kişi dökümünün adayı (yalnız yönetici kipinde; ad yalnız bu ekranda görünür). */
export interface KisiAdayi {
  kind: KisiTuru;
  id: number;
  full_name: string;
  detail: string;
  status_display: string;
}

/** İndirme adı: belge adı + kapsam + tarih (`lib/download.ts`; kişi adı YOK). */
export function dokumDosyaAdi(ad: string, bicim: Bicim, kapsam?: string): string {
  return dosyaAdi([ad, kapsam, formatDate(todayIso())], bicim);
}

function sorgu(yol: string, parcalar: Record<string, string | number | null | undefined>): string {
  const q = Object.entries(parcalar)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return q.length > 0 ? `${yol}?${q.join("&")}` : yol;
}

export const dokumlerApi = {
  ozet: (): Promise<DokumOzeti> => api.get<DokumOzeti>("/library/reports/documents/"),

  disaAktarim: (): Promise<Blob> => api.getBlob("/library/export/"),

  uyeOzeti: (): Promise<UyeOzeti> => api.get<UyeOzeti>("/library/export/member-summary/"),

  katalogDokumu: (bicim: Bicim, eksen: KatalogEkseni, bolum?: number | null): Promise<Blob> =>
    api.getBlob(
      sorgu("/library/reports/catalog-listing/", {
        kind: bicim,
        axis: bicim === "pdf" ? eksen : undefined,
        section: bolum ?? undefined,
      }),
    ),

  defterDokumu: (bicim: Bicim, yil?: number | null): Promise<Blob> =>
    api.getBlob(
      sorgu("/library/reports/library-register/", { kind: bicim, year: yil ?? undefined }),
    ),

  yonetimHesabi: (sayimId: number, bicim: Bicim): Promise<Blob> =>
    api.getBlob(sorgu(`/library/reports/management-account/${sayimId}/`, { kind: bicim })),

  /** Okul no ya da ad GÖVDEDE gider (sorgu dizesine kişisel veri yazılmaz). */
  kisiAra: (govde: { school_no?: string; name?: string }): Promise<{ results: KisiAdayi[] }> =>
    api.post<{ results: KisiAdayi[] }>("/library/reports/person-record/search/", govde),

  kisiDokumu: (tur: KisiTuru, id: number): Promise<Blob> =>
    api.getBlob(`/library/reports/person-record/${tur}/${id}/`),
};
