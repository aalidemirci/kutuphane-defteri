// İlişik listesi, yıl sonu ve yıl başı akışlarının istemcisi (F7 — tasarım §8.3, §10 E5).
// Tipler backend serializer'larıyla BİREBİRDİR (`serializers_ilisik.py`,
// `views_ilisik.py`); alan listeleri backend'de anlık görüntüyle sabittir.
//
// Uçların HİÇBİRİ görevli kipinde açık değildir (tasarım §4.4: "ilişik" kapalı).
// Genel Bakış kartı yalnız kişisiz özeti okur ve kullanıcı eylemi değildir:
// `X-KD-Etkinlik` göndermez (yönetici kipinin boşta sayacını tazelemez).
//
// PDF uçları kayıt YAZMAZ. Teslim listesi (E15) ve kayıp/hasar tutanağı (E6)
// uçları teslim ve kayıp ekranlarının kendi istemcilerindedir
// (`modules/teslim/api.ts`, `modules/kayip/api.ts`); burada yalnız sınıf
// kitaplığının güncel teslim listesi (şubeye göre) vardır.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

export type IlisikGrubu = "graduating" | "leaving" | "other";
/** Süzgeç değeri: `priority` = son sınıflar VE okuldan ayrılanlar. */
export type IlisikKapsami = "" | IlisikGrubu | "priority";
export type IlisikDurumu = "open" | "clear" | "all";
export type KisiTuru = "student" | "personnel";

export interface IlisikOdunc {
  id: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  loaned_at: string;
  due_date: string;
  overdue_days: number;
}

export interface IlisikTeslim {
  id: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  delivered_on: string;
  expected_return: string | null;
  document_no: string;
}

export interface IlisikDosya {
  id: number;
  case_type: "LOST" | "DAMAGED";
  case_type_display: string;
  resolution: string;
  resolution_display: string;
  barcode: string;
  barcode_display: string;
  work_title: string;
  reported_on: string;
}

/** İlişik listesinin satırı — `ClearanceRowSerializer`. */
export interface IlisikSatiri {
  person_type: KisiTuru;
  person_id: number;
  full_name: string;
  person_label: string;
  student_number: string;
  group: IlisikGrubu;
  is_graduating: boolean;
  /** Rozet metni: "Son sınıf" · "Ayrıldı · gg.aa.yyyy" · "Ayrılış kararı bekliyor" · "". */
  status_text: string;
  left_at: string | null;
  in_leave_pool: boolean;
  is_clear: boolean;
  open_loan_count: number;
  overdue_loan_count: number;
  open_delivery_count: number;
  open_case_count: number;
  loans: IlisikOdunc[];
  deliveries: IlisikTeslim[];
  cases: IlisikDosya[];
}

/** Açık teslimi olan şube (sınıf kitaplığı) — kişisiz. */
export interface SinifKitapligi {
  section_id: number;
  section_label: string;
  school_year_name: string;
  is_graduating: boolean;
  is_active_year: boolean;
  delivery_count: number;
  document_numbers: string[];
  open_case_count: number;
}

export interface DersYiliOzeti {
  name: string;
  start_date: string;
  end_date: string;
}

export interface IlisikSayilari {
  persons: number;
  graduating_persons: number;
  leaving_persons: number;
  open_loans: number;
  graduating_open_loans: number;
  leaving_open_loans: number;
  teacher_deliveries: number;
  section_deliveries: number;
  graduating_section_deliveries: number;
  open_cases: number;
}

export type YilSonuAdimi = "dates" | "collection" | "graduating" | "clearance";
export type YilBasiAdimi = "school_year" | "import" | "leave_pool" | "closed_days";

export interface YilSonuOzeti {
  in_window: boolean;
  school_year: DersYiliOzeti | null;
  graduating_level: number | null;
  last_loan_date: string | null;
  last_loan_date_graduating: string | null;
  last_loan_date_stale: boolean;
  last_loan_date_graduating_stale: boolean;
  graduating_students: number;
  graduating_clear_students: number;
  counts: IlisikSayilari;
  steps: Record<YilSonuAdimi, boolean>;
  /**
   * F8: etkin ders yılının yıl sonu kütüphane raporu (Md. 12/1, E9) — kişisiz durum;
   * henüz hazırlanmadıysa `null`. Sunucunun adım işaretlerine (`steps`) girmez; Yıl
   * Sonu ekranının beşinci adımı ve Genel Bakış kartı buradan okur.
   */
  annual_review: { id: number; is_finalized: boolean } | null;
}

export interface YilBasiOzeti {
  in_window: boolean;
  school_year: DersYiliOzeti | null;
  school_year_ready: boolean;
  kademe_missing: boolean;
  last_student_import: string | null;
  last_personnel_import: string | null;
  student_import_fresh: boolean;
  personnel_import_fresh: boolean;
  leave_pool_students: number;
  leave_pool_personnel: number;
  school_break_count: number;
  holidays_missing_years: number[];
  stale_last_loan_dates: boolean;
  steps: Record<YilBasiAdimi, boolean>;
}

/** `GET library/year-flows/` — kişisiz. */
export interface YilAkislari {
  today: string;
  year_end: YilSonuOzeti;
  year_start: YilBasiOzeti;
}

export interface IlisikSorgusu {
  state?: IlisikDurumu;
  group?: IlisikKapsami;
  personType?: KisiTuru | "";
  /** `collect`: yalnız toplanacak kitabı (ödünç ya da öğretmene teslim) olanlar. */
  obligation?: "all" | "collect";
  classLevel?: number | null;
  classSection?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface PusulaIstegi {
  studentIds?: number[];
  personnelIds?: number[];
  group?: IlisikKapsami;
  classLevel?: number | null;
  classSection?: string;
  /** "En geç … tarihine kadar" — pusulaya basılır, SAKLANMAZ. */
  returnBy?: string;
}

// ---------------------------------------------------------------------------
// Adlar ve metinler (sözlük §2, §4) — indirme adları `lib/download.ts::dosyaAdi` ile
// ---------------------------------------------------------------------------

export const ILISIK_BELGESI_ADI = "Kütüphaneden İlişiği Yoktur Belgesi";
export const ILISIK_LISTESI_ADI = "İlişik Listesi";
export const PUSULA_ADI = "İade Hatırlatma Pusulası";
export const TESLIM_LISTESI_ADI = "Teslim Listesi";
/** Toplu listenin dipnotu (sözlük §5) — ekranda da gösterilir. */
export const LISTE_DIPNOTU = "Kişisel veri içerir — asılmaz, çoğaltılmaz.";

export const ILISIK_LISTESI_ADRESI = "/ilisik-listesi";
export const YIL_SONU_ADRESI = "/yil-sonu";
export const YIL_BASI_ADRESI = "/yil-basi";
export const ILISIK_LISTESI_BASLIGI = "İlişik Listesi";
export const YIL_SONU_BASLIGI = "Yıl Sonu";
export const YIL_BASI_BASLIGI = "Yıl Başı";

/** Kapsam seçicisinin seçenekleri (ilişik listesi ve yıl sonu). */
export const KAPSAM_SECENEKLERI: Array<{ value: IlisikKapsami; label: string }> = [
  { value: "", label: "Bütün kişiler" },
  { value: "graduating", label: "Son sınıflar" },
  { value: "leaving", label: "Okuldan ayrılanlar" },
  { value: "priority", label: "Son sınıflar ve okuldan ayrılanlar" },
  { value: "other", label: "Diğerleri" },
];

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

function sorguParcalari(s: IlisikSorgusu): string[] {
  const parts: string[] = [];
  if (s.state) parts.push(`state=${s.state}`);
  if (s.group) parts.push(`group=${s.group}`);
  if (s.personType) parts.push(`person_type=${s.personType}`);
  if (s.obligation && s.obligation !== "all") parts.push(`obligation=${s.obligation}`);
  if (s.classLevel !== undefined && s.classLevel !== null) {
    parts.push(`class_level=${s.classLevel}`);
  }
  if (s.classSection) parts.push(`class_section=${encodeURIComponent(s.classSection)}`);
  if (s.search) parts.push(`search=${encodeURIComponent(s.search)}`);
  if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
  if (s.offset) parts.push(`offset=${s.offset}`);
  return parts;
}

/** "2 ödünç (1 gecikmiş) · 3 teslim · 1 dosya" — satırın kısa özeti. */
export function acikIslerOzeti(s: IlisikSatiri): string {
  const parcalar: string[] = [];
  if (s.open_loan_count > 0) {
    parcalar.push(
      s.overdue_loan_count > 0
        ? `${s.open_loan_count} ödünç (${s.overdue_loan_count} gecikmiş)`
        : `${s.open_loan_count} ödünç`,
    );
  }
  if (s.open_delivery_count > 0) parcalar.push(`${s.open_delivery_count} teslim`);
  if (s.open_case_count > 0) parcalar.push(`${s.open_case_count} kayıp/hasar dosyası`);
  return parcalar.length > 0 ? parcalar.join(" · ") : "Açık işi yok";
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

export const yilApi = {
  /** Yıl sonu ve yıl başı özetleri (kişisiz; kullanıcı eylemi değildir). */
  akislar: (): Promise<YilAkislari> =>
    api.get<YilAkislari>("/library/year-flows/", { etkinlik: false }),

  ilisikListesi: (s: IlisikSorgusu = {}): Promise<Paginated<IlisikSatiri>> =>
    api.get<Paginated<IlisikSatiri>>(withQuery("/library/clearance/", sorguParcalari(s))),

  ilisikListesiPdf: (
    s: Pick<IlisikSorgusu, "group" | "classLevel" | "classSection"> = {},
  ): Promise<Blob> => api.getBlob(withQuery("/library/clearance/pdf/", sorguParcalari(s))),

  sinifKitapliklari: (yalnizSonSinif = false): Promise<SinifKitapligi[]> =>
    api.get<SinifKitapligi[]>(
      yalnizSonSinif ? "/library/clearance/sections/?graduating=1" : "/library/clearance/sections/",
    ),

  /** "Kütüphaneden ilişiği yoktur" belgesi — açık işi olan biri varsa hiçbiri basılmaz (400). */
  ilisikBelgesiPdf: (kisiler: { studentIds?: number[]; personnelIds?: number[] }): Promise<Blob> =>
    api.postBlob("/library/clearance/certificates/", {
      student_ids: kisiler.studentIds ?? [],
      personnel_ids: kisiler.personnelIds ?? [],
    }),

  /** Yıl sonu iade hatırlatma pusulası (kişinin bütün açık ödünçleri). */
  yilSonuPusulasiPdf: (istek: PusulaIstegi): Promise<Blob> =>
    api.postBlob("/library/year-end/slips/", {
      student_ids: istek.studentIds ?? [],
      personnel_ids: istek.personnelIds ?? [],
      ...(istek.group ? { group: istek.group } : {}),
      ...(istek.classLevel !== undefined && istek.classLevel !== null
        ? { class_level: istek.classLevel }
        : {}),
      ...(istek.classSection ? { class_section: istek.classSection } : {}),
      ...(istek.returnBy ? { return_by: istek.returnBy } : {}),
    }),

  /** Sınıf kitaplığının ŞU AN teslimdeki kitapları (E15, şubeye göre). */
  sinifKitapligiListesiPdf: (sectionId: number): Promise<Blob> =>
    api.getBlob(`/library/deliveries/pdf/?section=${sectionId}`),
};
