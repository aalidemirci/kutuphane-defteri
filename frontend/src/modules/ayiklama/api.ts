// Ayıklama, nadir eserler ve yıl sonu kütüphane raporu istemcisi (F8 — tasarım §6.2, §10
// E7-E9, E16). Tipler backend serializer'larıyla BİREBİRDİR (`serializers_ayiklama.py`,
// `views_ayiklama.py`, `views_komisyon_belgeleri.py`); alan listeleri backend'de anlık
// görüntüyle sabittir.
//
// Uçların HİÇBİRİ görevli kipinde açık değildir (tasarım §4.4: komisyon, ayıklama ve
// raporlar yönetici işidir). Kural sunucudadır: E7 tablosu (gerekçe → TMY yolu)
// `library/weeding/rules/`'dan okunur, ekran kopyalamaz; hangi belgenin basılabildiği
// `…/documents/` ucundan gelir.
//
// Kişisel veri: kalemler, nadir eser satırları ve yıl sonu raporu kişisizdir. Teklifin
// onayındaki harcama yetkilisi ve TMY komisyonu adları sunucuda ŞİFRELİDİR; parola
// kurulmadan yazan istek 409 `parola_gerekli` döner (ui/ErrorBand).

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";

// ---------------------------------------------------------------------------
// Kod listeleri (backend TextChoices ile birebir) ve Türkçe adları
// ---------------------------------------------------------------------------

/** Ayıklama teklifinin durumu — `WeedingBatchStatus`. */
export type TeklifDurumu = "DRAFT" | "SUBMITTED" | "DECIDED" | "APPROVED" | "APPLIED" | "CANCELLED";

export const TEKLIF_DURUMU_TR: Record<TeklifDurumu, string> = {
  DRAFT: "Taslak",
  SUBMITTED: "Komisyona sunuldu",
  DECIDED: "Komisyon kararı bağlandı",
  APPROVED: "Harcama yetkilisi onayladı",
  APPLIED: "Uygulandı",
  CANCELLED: "İptal edildi",
};

/** Ayıklama gerekçesi — `WeedingReason` (Md. 12/1 a-ç). */
export type Gerekce = "WORN" | "OBSOLETE" | "LEVEL_MISMATCH" | "CRITERIA_MISMATCH";

export const GEREKCE_TR: Record<Gerekce, string> = {
  WORN: "Aşırı kullanımdan yıpranmış",
  OBSOLETE: "Bilimsel değeri kalmamış",
  LEVEL_MISMATCH: "Kurumun düzeyine uygun değil",
  CRITERIA_MISMATCH: "10. maddedeki ölçütlere uygun değil",
};

/** Gerekçenin Md. 12/1 bendi (ekranda etiketin yanında). */
export const GEREKCE_BENDI: Record<Gerekce, string> = {
  WORN: "Md. 12/1-a",
  OBSOLETE: "Md. 12/1-b",
  LEVEL_MISMATCH: "Md. 12/1-c; 10/1-b",
  CRITERIA_MISMATCH: "Md. 12/1-ç",
};

/** TMY yolu — `WeedingTmyPath`. */
export type TmyYolu = "TMY_27" | "TMY_28" | "TMY_24_2" | "TMY_31";

export const TMY_YOLU_TR: Record<TmyYolu, string> = {
  TMY_27: "Kullanılmaz hâle gelme nedeniyle kayıttan düşme (TMY 27/1)",
  TMY_28: "Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)",
  TMY_24_2: "Başka bir MEB okuluna devir (TMY 24/2)",
  TMY_31: "Başka bir kamu idaresine bedelsiz devir (TMY 31)",
};

/** Teklif kaleminin durumu — `WeedingItemState`. */
export type KalemDurumu = "PROPOSED" | "KEPT_BY_COMMISSION" | "NOT_APPROVED" | "APPLIED";

export const KALEM_DURUMU_TR: Record<KalemDurumu, string> = {
  PROPOSED: "Teklif listesinde",
  KEPT_BY_COMMISSION: "Komisyon ayıklanmasına karar vermedi",
  NOT_APPROVED: "Onaylanmadı",
  APPLIED: "Uygulandı",
};

/** Nadir eserler listesinin durumu — `RareWorksSubmissionStatus`. */
export type ListeDurumu = "DRAFT" | "SENT";

export const LISTE_DURUMU_TR: Record<ListeDurumu, string> = {
  DRAFT: "Hazırlanıyor",
  SENT: "Genel Müdürlüğe gönderildi",
};

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

/** `GET library/weeding/rules/` — E7 tablosu (tek kaynak sunucuda). */
export interface AyiklamaKurallari {
  reasons: Array<{
    value: Gerekce;
    label: string;
    paths: TmyYolu[];
    default_path: TmyYolu;
    needs_criterion: boolean;
  }>;
  paths: Array<{ value: TmyYolu; label: string; is_transfer: boolean }>;
  criteria: Array<{ value: string; label: string }>;
}

/** Aday nüsha (kişisiz) — `WeedingCandidateSerializer`. */
export interface AdayNusha {
  id: number;
  barcode: string;
  barcode_display: string;
  work: number;
  work_title: string;
  work_authors: string;
  call_number: string;
  section_name: string | null;
  status: string;
  status_display: string;
}

/**
 * Kayıp ya da hasar dosyasının kayıttan düşme önerisi — ayıklamaya KONMAZ (sayımda kayıttan
 * düşülür; 25.09.2026 kullanıcı kararı, tasarım F8 ekleri 34), gerekçesiyle gösterilir.
 */
export interface KayittanDusmeOnerisi extends AdayNusha {
  blocker: string;
}

export interface AdaySayfasi extends Paginated<AdayNusha> {
  /** Kayıp nüshaların önerileri. */
  lost_proposals: KayittanDusmeOnerisi[];
  /** Hasar dosyalarının önerileri (nüsha rafta, ödünçte, teslimde ya da onarımda olabilir). */
  damage_proposals: KayittanDusmeOnerisi[];
}

/** Teklif kalemi — `WeedingItemSerializer`. */
export interface Kalem {
  id: number;
  copy: number;
  barcode: string;
  barcode_display: string;
  work: number;
  work_title: string;
  work_authors: string;
  call_number: string;
  copy_status: string;
  copy_status_display: string;
  reason: Gerekce;
  reason_display: string;
  criterion: string;
  criterion_display: string;
  tmy_path: TmyYolu;
  tmy_path_display: string;
  is_transfer: boolean;
  transfer_target: string;
  state: KalemDurumu;
  state_display: string;
  exclusion_reason: string;
  /** Nüsha el yazması ya da nadir eser olarak işaretli mi? (işaretliyse ayıklanamaz) */
  copy_is_rare: boolean;
  /** TMY 28/5 imha kararının kapsadığı kalem mi? (kalem düzeyinde) */
  destruction_decided: boolean;
}

export interface KararOzeti {
  id: number;
  decision_type: string;
  decision_date: string;
  decision_no: string;
}

export interface TeklifSayilari {
  items: number;
  proposed: number;
  excluded: number;
  applied: number;
  write_off: number;
  transfer: number;
}

/** Teklif listesi satırı — `WeedingBatchSerializer` (şifreli adlar YOK). */
export interface Teklif {
  id: number;
  school_year: number;
  school_year_name: string;
  status: TeklifDurumu;
  status_display: string;
  commission_decision: number | null;
  decision: KararOzeti | null;
  submitted_at: string | null;
  decided_at: string | null;
  approved_on: string | null;
  approved_at: string | null;
  destruction_decided: boolean;
  applied_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string;
  notes: string;
  counts: TeklifSayilari;
  created_at: string;
}

/** Teklif ayrıntısı — kalemler ve onayın şifreli adları (yalnız yönetici kipinde). */
export interface TeklifAyrintisi extends Teklif {
  approved_by_name: string;
  tmy_commission_members: string;
  items: Kalem[];
}

export interface KalemEkleGovdesi {
  reason: Gerekce;
  tmy_path?: TmyYolu | "";
  criterion?: string;
  transfer_target?: string;
  barcodes?: string[];
  copies?: number[];
}

export interface KalemGuncelleGovdesi {
  reason?: Gerekce;
  tmy_path?: TmyYolu | "";
  criterion?: string;
  transfer_target?: string;
}

export interface OnayGovdesi {
  approved_by_name: string;
  approved_on: string;
  tmy_commission_members?: string;
  destruction_decided?: boolean;
  /** İmha kararının kapsadığı kalemler (TMY 28/5); verilmezse onaylanan bütün 28 kalemleri. */
  destruction_items?: number[] | null;
  /** Kalem kimliği → onaylanmama gerekçesi. */
  not_approved?: Record<string, string>;
}

/** Ayıklama belgesinin basılabilirliği — `GET …/documents/`. */
export interface AyiklamaBelgesi {
  kind: string;
  title: string;
  formats: Array<"pdf" | "xlsx">;
  available: boolean;
  reason: string;
}

/** Nadir eser işaretli nüsha — `RareCopySerializer`. */
export interface NadirNusha {
  id: number;
  barcode_display: string;
  work: number;
  work_title: string;
  work_authors: string;
  status: string;
  status_display: string;
  /** Genel Müdürlüğe gönderilmiş bir listede mi? */
  sent: boolean;
}

export interface NadirSatir {
  id: number;
  copy: number;
  barcode_display: string;
  work_title: string;
  work_authors: string;
  publisher: string;
  publish_year: number | null;
  call_number: string;
  copy_status_display: string;
}

/** El yazması ve nadir eserler listesi — `RareWorksSubmissionSerializer`. */
export interface NadirListe {
  id: number;
  school_year: number;
  school_year_name: string;
  commission_decision: number | null;
  decision: KararOzeti | null;
  status: ListeDurumu;
  status_display: string;
  sent_on: string | null;
  sent_document_no: string;
  notes: string;
  item_count: number;
  created_at: string;
}

export interface NadirListeAyrintisi extends NadirListe {
  items: NadirSatir[];
}

/** Eşikli kırılım hücresi (profil yasağı: k farklı üyenin altında sayı YOK). */
export interface EsikliSayi {
  loans: number | null;
  below_threshold: boolean;
}

/** Yıl sonu raporunun kişisiz sayıları — `selectors_yil_raporu.annual_review_stats`. */
export interface RaporSayilari {
  schema: number;
  generated_on: string;
  school_year: { label: string; start_date: string; end_date: string };
  period: { start: string; end: string };
  collection: {
    catalog_work_count: number;
    work_count: number;
    register_count: number;
    in_stock_count: number;
    status_counts: Record<string, number>;
    resource_type_counts: Record<string, number>;
    reference_count: number;
    rare_count: number;
    sections: Array<{ section: string; copies: number }>;
  };
  acquisitions: {
    copies_by_method: Record<string, number>;
    /** Yalnız Md. 10/5 yolları (Bakanlık gönderimi, satın alma, bağış, değişim). */
    total_copies: number;
    works: number;
    /** Kayıt içi girişler (programa aktarım, sayım fazlası) — kazandırılan sayılmaz. */
    register_entry_copies: number;
    donation_intakes_decided: number;
    donation_items_accepted: number;
    donation_items_rejected: number;
  };
  weeding: {
    withdrawn: number;
    transferred: number;
    by_reason: Record<string, number>;
    by_path: Record<string, number>;
    batches_applied: number;
  };
  findings: {
    repairs_sent: number;
    repairs_returned: number;
    in_repair_now: number;
    damage_cases: number;
    loss_cases: number;
    resolutions: Record<string, number>;
    write_off_proposals: number;
    open_cases_now: number;
    lost_copies_now: number;
  };
  circulation: {
    k_threshold: number;
    loans: number;
    returns: number;
    distinct_borrowers: number;
    by_member_type: Record<"STUDENT" | "TEACHER" | "STAFF", EsikliSayi>;
    by_class_level: Array<{ class_level: number } & EsikliSayi>;
    by_month: Array<{ month: string; loans: number }>;
    deliveries: { section: number; teacher: number };
    /** k'dan az (sıfır değil) üyesi olan türde `null` (profil yasağı). */
    active_members: Record<"STUDENT" | "TEACHER" | "STAFF", number | null>;
  };
}

/** Yıl sonu kütüphane raporu — liste satırı (sayısız). */
export interface YilRaporuSatiri {
  id: number;
  school_year: number;
  school_year_name: string;
  document_date: string | null;
  document_no: string;
  findings: string;
  is_finalized: boolean;
  finalized_at: string | null;
  created_at: string;
}

export interface YilRaporu extends YilRaporuSatiri {
  stats: RaporSayilari;
}

export interface YilRaporuGovdesi {
  document_date?: string | null;
  document_no?: string;
  findings?: string;
}

// ---------------------------------------------------------------------------
// Adlar ve adresler (sözlük §2, §4)
// ---------------------------------------------------------------------------

export const AYIKLAMA_ADRESI = "/katalog/ayiklama";
export const NADIR_ESERLER_ADRESI = "/katalog/nadir-eserler";
export const YIL_SONU_RAPORU_ADRESI = "/yil-sonu-raporu";
export const AYIKLAMA_BASLIGI = "Ayıklama";
export const NADIR_ESERLER_BASLIGI = "Nadir Eserler";
export const YIL_SONU_RAPORU_BASLIGI = "Yıl Sonu Raporu";

/** Belge adları (sözlük §2 — E8, E9, E16); E7 adları sunucudan gelir. */
export const NADIR_ESER_BELGESI = "El yazması ve nadir eserler listesi";
export const YIL_SONU_RAPORU_BELGESI = "Yıl sonu kütüphane raporu";
export const BAGIS_LISTESI_BELGESI = "Bağış ön kayıt listesi";
/**
 * Komisyon kararı uygulandıktan sonraki döküm (25.09.2026 kullanıcı kararı, tasarım F8 ekleri
 * 13): kabul ve ret edilen kalemler, gerekçeler, karar tarih/sayısı. "Bağış kabul tutanağı"
 * denmez — TMY'de böyle bir belge yoktur.
 */
export const BAGIS_SONUCU_BELGESI = "Bağış değerlendirme sonucu";

/** Teklif adresi (listeden ayrıntıya). */
export function teklifAdresi(id: number): string {
  return `${AYIKLAMA_ADRESI}?teklif=${id}`;
}

/** Teklifin kısa adı: "Ayıklama teklifi · 2026-2027 · 12.06.2027" (iç kimlik yazılmaz). */
export function teklifAdi(t: Pick<Teklif, "school_year_name" | "created_at">): string {
  return `Ayıklama teklifi · ${t.school_year_name} · ${formatDate(t.created_at)}`;
}

/** İndirme adı: belge adı + tarih (`lib/download.ts`). */
export function belgeDosyaAdi(ad: string, uzanti: "pdf" | "xlsx" = "pdf"): string {
  return dosyaAdi([ad, formatDate(todayIso())], uzanti);
}

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

export interface AdaySorgusu {
  q?: string;
  section?: number | null;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

const TEKLIF = "/library/weeding-batches/";
const LISTE = "/library/rare-works-submissions/";
const RAPOR = "/library/annual-reviews/";

export const ayiklamaApi = {
  // --- Ayıklama ---------------------------------------------------------------
  kurallar: (): Promise<AyiklamaKurallari> => api.get<AyiklamaKurallari>("/library/weeding/rules/"),

  adaylar: (s: AdaySorgusu = {}): Promise<AdaySayfasi> => {
    const parts: string[] = [];
    if (s.q) parts.push(`q=${encodeURIComponent(s.q)}`);
    if (s.section !== undefined && s.section !== null) parts.push(`section=${s.section}`);
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<AdaySayfasi>(withQuery("/library/weeding/candidates/", parts));
  },

  teklifler: (
    s: { status?: TeklifDurumu | ""; limit?: number; offset?: number } = {},
  ): Promise<Paginated<Teklif>> => {
    const parts: string[] = [];
    if (s.status) parts.push(`status=${s.status}`);
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<Paginated<Teklif>>(withQuery(TEKLIF, parts));
  },

  teklif: (id: number): Promise<TeklifAyrintisi> => api.get<TeklifAyrintisi>(`${TEKLIF}${id}/`),

  teklifAc: (notes = ""): Promise<TeklifAyrintisi> => api.post<TeklifAyrintisi>(TEKLIF, { notes }),

  teklifGuncelle: (id: number, notes: string): Promise<TeklifAyrintisi> =>
    api.patch<TeklifAyrintisi>(`${TEKLIF}${id}/`, { notes }),

  teklifSil: (id: number): Promise<void> => api.del<void>(`${TEKLIF}${id}/`),

  kalemEkle: (
    id: number,
    govde: KalemEkleGovdesi,
  ): Promise<{ added: Kalem[]; batch: TeklifAyrintisi }> =>
    api.post<{ added: Kalem[]; batch: TeklifAyrintisi }>(`${TEKLIF}${id}/items/`, govde),

  kalemGuncelle: (id: number, kalemId: number, govde: KalemGuncelleGovdesi): Promise<Kalem> =>
    api.patch<Kalem>(`${TEKLIF}${id}/items/${kalemId}/`, govde),

  kalemCikar: (id: number, kalemId: number): Promise<void> =>
    api.del<void>(`${TEKLIF}${id}/items/${kalemId}/`),

  sun: (id: number): Promise<TeklifAyrintisi> =>
    api.post<TeklifAyrintisi>(`${TEKLIF}${id}/submit/`),

  geriCek: (id: number): Promise<TeklifAyrintisi> =>
    api.post<TeklifAyrintisi>(`${TEKLIF}${id}/withdraw/`),

  kararBagla: (
    id: number,
    kararId: number,
    kept: Record<string, string> = {},
  ): Promise<TeklifAyrintisi> =>
    api.post<TeklifAyrintisi>(`${TEKLIF}${id}/decision/`, {
      commission_decision: kararId,
      kept,
    }),

  onayla: (id: number, govde: OnayGovdesi): Promise<TeklifAyrintisi> =>
    api.post<TeklifAyrintisi>(`${TEKLIF}${id}/approve/`, govde),

  uygula: (
    id: number,
  ): Promise<{ withdrawn: number; transferred: number; batch: TeklifAyrintisi }> =>
    api.post<{ withdrawn: number; transferred: number; batch: TeklifAyrintisi }>(
      `${TEKLIF}${id}/apply/`,
    ),

  iptalEt: (id: number, reason = ""): Promise<TeklifAyrintisi> =>
    api.post<TeklifAyrintisi>(`${TEKLIF}${id}/cancel/`, { reason }),

  belgeler: (id: number): Promise<AyiklamaBelgesi[]> =>
    api.get<AyiklamaBelgesi[]>(`${TEKLIF}${id}/documents/`),

  belge: (id: number, tur: string, bicim: "pdf" | "xlsx" = "pdf"): Promise<Blob> =>
    api.getBlob(
      bicim === "pdf"
        ? `${TEKLIF}${id}/documents/${tur}/`
        : `${TEKLIF}${id}/documents/${tur}/?kind=${bicim}`,
    ),

  // --- Nadir eserler (Md. 12/2) ------------------------------------------------
  nadirNushalar: (
    s: { unsent?: boolean; limit?: number; offset?: number } = {},
  ): Promise<Paginated<NadirNusha>> => {
    const parts: string[] = [];
    if (s.unsent) parts.push("unsent=1");
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<Paginated<NadirNusha>>(withQuery("/library/rare-copies/", parts));
  },

  listeler: (s: { limit?: number; offset?: number } = {}): Promise<Paginated<NadirListe>> => {
    const parts: string[] = [];
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<Paginated<NadirListe>>(withQuery(LISTE, parts));
  },

  liste: (id: number): Promise<NadirListeAyrintisi> =>
    api.get<NadirListeAyrintisi>(`${LISTE}${id}/`),

  listeAc: (govde: { commission_decision?: number | null; notes?: string } = {}) =>
    api.post<NadirListeAyrintisi>(LISTE, govde),

  listeGuncelle: (
    id: number,
    govde: { commission_decision?: number | null; notes?: string },
  ): Promise<NadirListeAyrintisi> => api.patch<NadirListeAyrintisi>(`${LISTE}${id}/`, govde),

  listeSil: (id: number): Promise<void> => api.del<void>(`${LISTE}${id}/`),

  listeyeEkle: (
    id: number,
    govde: { barcodes?: string[]; copies?: number[] },
  ): Promise<{ added: NadirSatir[]; submission: NadirListeAyrintisi }> =>
    api.post<{ added: NadirSatir[]; submission: NadirListeAyrintisi }>(
      `${LISTE}${id}/items/`,
      govde,
    ),

  listedenCikar: (id: number, satirId: number): Promise<void> =>
    api.del<void>(`${LISTE}${id}/items/${satirId}/`),

  gonderildi: (
    id: number,
    govde: { sent_on: string; sent_document_no?: string },
  ): Promise<NadirListeAyrintisi> => api.post<NadirListeAyrintisi>(`${LISTE}${id}/send/`, govde),

  listePdf: (id: number): Promise<Blob> => api.getBlob(`${LISTE}${id}/pdf/`),

  // --- Yıl sonu kütüphane raporu (E9) -------------------------------------------
  raporlar: (): Promise<Paginated<YilRaporuSatiri>> =>
    api.get<Paginated<YilRaporuSatiri>>(`${RAPOR}?limit=50`),

  rapor: (id: number): Promise<YilRaporu> => api.get<YilRaporu>(`${RAPOR}${id}/`),

  raporAc: (schoolYear?: number | null): Promise<YilRaporu> =>
    api.post<YilRaporu>(RAPOR, schoolYear ? { school_year: schoolYear } : {}),

  raporGuncelle: (id: number, govde: YilRaporuGovdesi): Promise<YilRaporu> =>
    api.patch<YilRaporu>(`${RAPOR}${id}/`, govde),

  raporuSonlandir: (id: number): Promise<YilRaporu> =>
    api.post<YilRaporu>(`${RAPOR}${id}/finalize/`),

  sonlandirmayiGeriAl: (id: number): Promise<YilRaporu> =>
    api.post<YilRaporu>(`${RAPOR}${id}/reopen/`),

  raporPdf: (id: number): Promise<Blob> => api.getBlob(`${RAPOR}${id}/pdf/`),

  // --- Bağış ön kayıt listesi (E16) ---------------------------------------------
  bagisListesiPdf: (intakeId: number): Promise<Blob> =>
    api.getBlob(`/library/donation-intakes/${intakeId}/pdf/`),

  /** Bağış değerlendirme sonucu — yalnız komisyon kararı uygulanmış ön kayıtta (öncesi 400). */
  bagisSonucuPdf: (intakeId: number): Promise<Blob> =>
    api.getBlob(`/library/donation-intakes/${intakeId}/result-pdf/`),
};
