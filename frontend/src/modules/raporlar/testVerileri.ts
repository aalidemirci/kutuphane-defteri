// Raporlar testlerinin uydurma verileri (F10). Eser adları ve yazarlar uydurmadır; kişi adı yoktur
// (istatistik ve çok okunanlar kişisizdir).

import type {
  CokOkunanlar,
  Istatistik,
  KitapEsigi,
  PanoOzeti,
  Pencere,
  PencereBilgisi,
} from "./api";

export function kitapEsigi(ek: Partial<KitapEsigi> = {}): KitapEsigi {
  return { threshold: 10_000, in_stock_books: 1_250, lost_books: 0, exceeded: false, ...ek };
}

export function istatistik(ek: Partial<Istatistik> = {}): Istatistik {
  return {
    schema: 1,
    generated_on: "2026-09-26",
    period: { start: "2026-09-01", end: "2027-08-31" },
    k_threshold: 5,
    collection: {
      catalog_work_count: 812,
      work_count: 790,
      register_count: 1_402,
      in_stock_count: 1_380,
      status_counts: { AVAILABLE: 1_300, ON_LOAN: 60, DELIVERED: 20, WITHDRAWN_WEEDED: 22 },
      resource_type_counts: { BOOK: 1_250, PERIODICAL: 100, AV_MATERIAL: 30 },
      reference_count: 45,
      rare_count: 2,
      sections: [
        { section: "Edebiyat", copies: 900 },
        { section: "", copies: 480 },
      ],
      works_by_resource_type: { BOOK: 700, PERIODICAL: 80, AV_MATERIAL: 20, EBOOK: 12 },
      available_count: 1_300,
    },
    book_threshold: kitapEsigi(),
    acquisitions: {
      copies_by_method: { PURCHASE: 40, DONATION: 25, EXISTING_STOCK: 1_200 },
      total_copies: 65,
      works: 50,
      register_entry_copies: 1_200,
      donation_intakes_decided: 2,
      donation_items_accepted: 25,
      donation_items_rejected: 3,
    },
    circulation: {
      k_threshold: 5,
      loans: 340,
      returns: 300,
      distinct_borrowers: 120,
      by_member_type: {
        STUDENT: { loans: 330, below_threshold: false },
        TEACHER: { loans: null, below_threshold: true },
        STAFF: { loans: null, below_threshold: true },
      },
      by_class_level: [
        { class_level: 9, loans: 200, below_threshold: false },
        { class_level: 10, loans: 130, below_threshold: false },
        { class_level: 12, loans: null, below_threshold: true },
      ],
      by_month: [
        { month: "2026-09", loans: 140 },
        { month: "2026-10", loans: 200 },
      ],
      // Eşiksiz (F10 ekleri K1): diğer personelin ödüncü gizliyken üye sayısı yazılır.
      active_members: { STUDENT: 300, TEACHER: 12, STAFF: 2 },
      returned_late: 18,
      lost_converted: 2,
      open_now: 40,
      overdue_now: 6,
    },
    deliveries: {
      delivered: { section: 3, teacher: 4 },
      returned: 2,
      lost: 0,
      open_now: { section: 1, teacher: 4 },
    },
    loss_damage: {
      repairs_sent: 3,
      repairs_returned: 2,
      in_repair_now: 1,
      damage_cases: 2,
      loss_cases: 4,
      resolutions: { FOUND_RETURNED: 1, REPLACED_SAME: 2, REPAIRED: 0 },
      write_off_proposals: 1,
      open_cases_now: 3,
      lost_copies_now: 2,
    },
    weeding: {
      withdrawn: 22,
      transferred: 5,
      by_reason: { WORN: 20, LEVEL_MISMATCH: 5 },
      by_path: { TMY_27: 20, TMY_24_2: 5 },
      batches_applied: 1,
    },
    ...ek,
  };
}

export function pencere(ek: Partial<Pencere> = {}): Pencere {
  return {
    window_type: "AY",
    window: "2026-09",
    label: "Eylül 2026",
    frozen: false,
    computed_on: "2026-09-26",
    works: [
      { rank: 1, work_id: 11, title: "Deneme Romanı", authors: "Örnek Yazar" },
      { rank: 2, work_id: 12, title: "Uydurma Öyküler", authors: "" },
      { rank: 3, work_id: 13, title: "Örnek Şiirler", authors: "Deneme Şair" },
    ],
    ...ek,
  };
}

export function donemPenceresi(ek: Partial<Pencere> = {}): Pencere {
  return pencere({
    window_type: "DONEM",
    window: "2026-2027/1",
    label: "2026-2027 ders yılı 1. dönem",
    ...ek,
  });
}

/** Pencerenin künyesi (eserler olmadan). */
export function bilgi(p: Pencere): PencereBilgisi {
  return {
    window_type: p.window_type,
    window: p.window,
    label: p.label,
    frozen: p.frozen,
    computed_on: p.computed_on,
  };
}

export function cokOkunanlar(ek: Partial<CokOkunanlar> = {}): CokOkunanlar {
  const ay = pencere();
  const donem = donemPenceresi();
  return {
    k_threshold: 5,
    term_windows: [bilgi(donem)],
    month_windows: [
      bilgi(ay),
      {
        window_type: "AY",
        window: "2026-08",
        label: "Ağustos 2026",
        frozen: true,
        computed_on: "2026-09-01",
      },
    ],
    term: donem,
    month: ay,
    ...ek,
  };
}

export function panoOzeti(ek: Partial<PanoOzeti> = {}): PanoOzeti {
  return {
    book_threshold: kitapEsigi(),
    popular: { term: donemPenceresi(), month: pencere() },
    ...ek,
  };
}
