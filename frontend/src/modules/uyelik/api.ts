// Üyelik, kart basımı, gecikmiş ödünç, evrak ve pano uçlarının istemcisi (F6 — E kolu).
// Tipler backend serializer'larıyla BİREBİRDİR (`serializers_uyelik.py`,
// `serializers_evrak.py`); alan listeleri backend'de anlık görüntüyle sabittir.
//
// Uçların HİÇBİRİ görevli kipinde açık değildir (tasarım §4.4): üye listesi, ödünç
// geçmişi, gecikme listesi, kart basımı ve "son işlemler" yönetici işidir. Pano
// sorguları (`dolasimOzeti`, `sonIslemler`) kullanıcı eylemi değildir:
// `X-KD-Etkinlik` göndermez (yönetici kipinin boşta sayacını tazelemez).
//
// PDF uçları hiçbir kayda dokunmaz (D10): kart "basıldı" işareti yalnız
// `kartBasildi` ile yazılır, `kartBasimiGeriAl` ile geri alınır.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

export type MemberType = "STUDENT" | "TEACHER" | "STAFF";
export type MembershipStatus = "ACTIVE" | "TERMINATED";
/** Elle seçilebilen sonlandırma nedenleri (backend `MANUAL_TERMINATION_REASONS`). */
export type ManualTerminationReason = "MEMBER_REQUEST" | "RECORD_ERROR";

/** Üye türü etiketi (sözlük: öğrenci / öğretmen / diğer personel). */
export const MEMBER_TYPE_TR: Record<MemberType, string> = {
  STUDENT: "Öğrenci",
  TEACHER: "Öğretmen",
  STAFF: "Diğer personel",
};

export const MEMBERSHIP_STATUS_TR: Record<MembershipStatus, string> = {
  ACTIVE: "Aktif",
  TERMINATED: "Sonlandı",
};

/** "Üyeliği sonlandır" diyaloğunun seçenekleri (kapalı liste — D12). */
export const MANUAL_TERMINATION_TR: Record<ManualTerminationReason, string> = {
  MEMBER_REQUEST: "Üyenin isteği",
  RECORD_ERROR: "Yanlış kayıt",
};

/** Üyelik (yönetici kipi) — `MembershipSerializer`. Sayılar KİŞİ bazındadır. */
export interface Membership {
  id: number;
  student: number | null;
  personnel: number | null;
  member_type: MemberType;
  member_type_display: string;
  full_name: string;
  class_label: string;
  student_number: string;
  card_no: string;
  card_printed_at: string | null;
  status: MembershipStatus;
  status_display: string;
  requested_at: string;
  started_at: string;
  terminated_at: string | null;
  termination_reason: string;
  termination_reason_display: string;
  open_loan_count: number;
  overdue_loan_count: number;
  loan_limit: number;
  remaining_quota: number;
}

/** Üyenin ödünç kaydı satırı — konu/sınıflama alanı YOKTUR (profil yasağı). */
export interface MemberLoan {
  id: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  loaned_at: string;
  due_date: string;
  returned_at: string | null;
  /** F7: `LOST_CONVERTED` — kayıp bildirimiyle kapanan ödünç ("Kayba dönüştü"). */
  status: "OPEN" | "RETURNED" | "LOST_CONVERTED";
  status_display: string;
  overdue_days: number;
  has_override: boolean;
  override_reason_display: string;
  cardless: boolean;
  cardless_reason_display: string;
}

/** Üyelik istek listesi satırı (şubedeki aktif öğrenci). */
export interface MembershipRequestRow {
  student_id: number;
  full_name: string;
  student_number: string;
  class_label: string;
  is_member: boolean;
  membership_id: number | null;
}

/** Kart basımı kuyruğunun satırı — sınıf yalnız bilgi ve sıradır, karta basılmaz. */
export interface MemberCardRow {
  id: number;
  full_name: string;
  member_type: MemberType;
  member_type_display: string;
  class_label: string;
  student_number: string;
  card_no: string;
  card_printed_at: string | null;
  started_at: string;
}

/** Gecikmiş ödünç satırı (yönetici kipi). */
export interface OverdueLoanRow {
  id: number;
  membership_id: number;
  full_name: string;
  /** Öğrencide sınıf/şube ("9/A"), personelde üye türü ("Öğretmen"). */
  person_label: string;
  is_student: boolean;
  barcode: string;
  barcode_display: string;
  work_title: string;
  loaned_at: string;
  due_date: string;
  overdue_days: number;
}

/** Pano özeti — kişisiz. */
export interface CirculationSummary {
  overdue_count: number;
  unexpected_shutdown: boolean;
}

/** Son oturumdan bir ödünç ya da iade (beklenmedik kapanış kartı). */
export interface RecentTransaction {
  kind: "LOAN" | "RETURN";
  kind_display: string;
  at: string;
  loan_id: number;
  barcode_display: string;
  work_title: string;
  full_name: string;
  person_label: string;
}

/** Kart şablonu (etiket şablonu biçiminde; tür CARD). */
export interface KartSablonu {
  id: number;
  name: string;
  kind: "CARD";
  kind_display: string;
  page_margin_top: number;
  page_margin_left: number;
  label_width: number;
  label_height: number;
  rows: number;
  cols: number;
  gutter_x: number;
  gutter_y: number;
  corner_radius: number;
  is_default: boolean;
  labels_per_sheet: number;
  supports_qr: boolean;
  supports_barcode: boolean;
  updated_at: string;
}

export interface UyelikListeParametreleri {
  status?: MembershipStatus | "";
  memberType?: MemberType | "";
  classLevel?: number | null;
  classSection?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export type KartDurumu = "pending" | "printed";

export interface KartKuyruguParametreleri {
  state: KartDurumu;
  memberType?: MemberType | "";
  classLevel?: number | null;
  classSection?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface KartPdfGovdesi {
  membership_ids: number[];
  template?: number | null;
  calibration?: number | null;
  start_cell: number;
  cut_guides: boolean;
}

export interface GecikmeKapsami {
  classLevel?: number | null;
  classSection?: string;
}

// ---------------------------------------------------------------------------
// Belge adları (sözlük §2) — indirme adları `lib/download.ts::dosyaAdi` ile
// ---------------------------------------------------------------------------

export const UYE_KARTI_ADI = "Üye Kartı";
export const PUSULA_ADI = "İade Hatırlatma Pusulası";
export const GECIKME_LISTESI_ADI = "Gecikmiş Ödünç Listesi";
export const AYDINLATMA_ADI = "Kütüphane Aydınlatma Metni";
export const MASA_KARTI_ADI = "Masa Kartı";

/** Toplu gecikme listesinin dipnotu (sözlük §5) — ekranda da gösterilir. */
export const LISTE_DIPNOTU = "Kişisel veri içerir — asılmaz, çoğaltılmaz.";

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

function kapsamParcalari(kapsam: GecikmeKapsami): string[] {
  const parts: string[] = [];
  if (kapsam.classLevel !== undefined && kapsam.classLevel !== null) {
    parts.push(`class_level=${kapsam.classLevel}`);
  }
  if (kapsam.classSection) parts.push(`class_section=${encodeURIComponent(kapsam.classSection)}`);
  return parts;
}

function sayfaParcalari(p: { limit?: number; offset?: number }): string[] {
  const parts: string[] = [];
  if (p.limit !== undefined) parts.push(`limit=${p.limit}`);
  if (p.offset) parts.push(`offset=${p.offset}`);
  return parts;
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

export const uyelikApi = {
  // --- Üyelikler (yönetici kipi) ---

  uyelikler: (p: UyelikListeParametreleri = {}): Promise<Paginated<Membership>> => {
    const parts = sayfaParcalari(p);
    if (p.status) parts.push(`status=${p.status}`);
    if (p.memberType) parts.push(`member_type=${p.memberType}`);
    if (p.classLevel !== undefined && p.classLevel !== null) {
      parts.push(`class_level=${p.classLevel}`);
    }
    if (p.classSection) parts.push(`class_section=${encodeURIComponent(p.classSection)}`);
    if (p.search) parts.push(`search=${encodeURIComponent(p.search)}`);
    return api.get<Paginated<Membership>>(withQuery("/library/memberships/", parts));
  },

  /** Tek kişiye üyelik: öğrenci YA DA personel (personelde olağan yol). */
  uyelikAc: (govde: { student_id: number } | { personnel_id: number }): Promise<Membership> =>
    api.post<Membership>("/library/memberships/", govde),

  /** Yanlış açılmış ve hiç ödünç kaydı olmayan üyeliği siler (kart iptal edilir). */
  uyelikSil: (id: number): Promise<void> => api.del<void>(`/library/memberships/${id}/`),

  kartiYenile: (id: number): Promise<Membership> =>
    api.post<Membership>(`/library/memberships/${id}/renew-card/`),

  sonlandir: (id: number, reason: ManualTerminationReason): Promise<Membership> =>
    api.post<Membership>(`/library/memberships/${id}/terminate/`, { reason }),

  oduncKaydi: (
    id: number,
    p: { limit?: number; offset?: number } = {},
  ): Promise<Paginated<MemberLoan>> =>
    api.get<Paginated<MemberLoan>>(
      withQuery(`/library/memberships/${id}/loans/`, sayfaParcalari(p)),
    ),

  // --- Üyelik istek listesi (Md. 17/1) ---

  istekListesi: (classLevel: number, classSection: string): Promise<MembershipRequestRow[]> =>
    api.get<MembershipRequestRow[]>(
      withQuery("/library/membership-requests/", [
        `class_level=${classLevel}`,
        `class_section=${encodeURIComponent(classSection)}`,
      ]),
    ),

  istekleriUygula: (studentIds: number[], requestedAt?: string): Promise<Membership[]> =>
    api.post<Membership[]>("/library/membership-requests/", {
      student_ids: studentIds,
      ...(requestedAt ? { requested_at: requestedAt } : {}),
    }),

  // --- Kart basımı (E2) ---

  kartKuyrugu: (p: KartKuyruguParametreleri): Promise<Paginated<MemberCardRow>> => {
    const parts = [`state=${p.state}`, ...sayfaParcalari(p)];
    if (p.memberType) parts.push(`member_type=${p.memberType}`);
    if (p.classLevel !== undefined && p.classLevel !== null) {
      parts.push(`class_level=${p.classLevel}`);
    }
    if (p.classSection) parts.push(`class_section=${encodeURIComponent(p.classSection)}`);
    if (p.search) parts.push(`search=${encodeURIComponent(p.search)}`);
    return api.get<Paginated<MemberCardRow>>(withQuery("/library/member-cards/", parts));
  },

  kartSablonu: (): Promise<KartSablonu> => api.get<KartSablonu>("/library/member-cards/template/"),

  /** Kart PDF'i — hiçbir işarete dokunmaz. */
  kartPdf: (govde: KartPdfGovdesi): Promise<Blob> =>
    api.postBlob("/library/member-cards/pdf/", govde),

  kartBasildi: (ids: number[]): Promise<{ marked: number }> =>
    api.post<{ marked: number }>("/library/member-cards/confirm-print/", { membership_ids: ids }),

  kartBasimiGeriAl: (ids: number[]): Promise<{ reverted: number }> =>
    api.post<{ reverted: number }>("/library/member-cards/revert-print/", { membership_ids: ids }),

  // --- Gecikmiş ödünçler (E4) ---

  gecikmisOduncler: (
    kapsam: GecikmeKapsami & { limit?: number; offset?: number } = {},
  ): Promise<Paginated<OverdueLoanRow>> =>
    api.get<Paginated<OverdueLoanRow>>(
      withQuery("/library/overdue-loans/", [...kapsamParcalari(kapsam), ...sayfaParcalari(kapsam)]),
    ),

  gecikmeListesiPdf: (kapsam: GecikmeKapsami = {}): Promise<Blob> =>
    api.getBlob(withQuery("/library/overdue-loans/pdf/", kapsamParcalari(kapsam))),

  /** Pusulalar: `membershipIds` verilirse yalnız o kişiler, verilmezse kapsamdaki herkes. */
  pusulaPdf: (kapsam: GecikmeKapsami & { membershipIds?: number[] } = {}): Promise<Blob> =>
    api.postBlob("/library/overdue-loans/slips/", {
      ...(kapsam.membershipIds ? { membership_ids: kapsam.membershipIds } : {}),
      ...(kapsam.classLevel !== undefined && kapsam.classLevel !== null
        ? { class_level: kapsam.classLevel }
        : {}),
      ...(kapsam.classSection ? { class_section: kapsam.classSection } : {}),
    }),

  // --- Belgeler (E13, E19) ---

  aydinlatmaMetniPdf: (govde: { basvuru_adresi: string; iletisim: string }): Promise<Blob> =>
    api.postBlob("/library/documents/privacy-notice/", govde),

  masaKartiPdf: (): Promise<Blob> => api.getBlob("/library/documents/desk-card/"),

  // --- Pano (kullanıcı eylemi değildir: etkinlik başlığı yok) ---

  dolasimOzeti: (): Promise<CirculationSummary> =>
    api.get<CirculationSummary>("/library/dashboard/circulation/", { etkinlik: false }),

  kontrolEttim: (): Promise<CirculationSummary> =>
    api.post<CirculationSummary>("/library/dashboard/circulation/", {}),

  sonIslemler: (): Promise<RecentTransaction[]> =>
    api.get<RecentTransaction[]>("/library/dashboard/recent-transactions/", { etkinlik: false }),
};
