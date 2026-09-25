// Ayıklama, nadir eser ve yıl sonu raporu testlerinin uydurma verileri (gerçek kişi ve
// kurum yok — CLAUDE.md §2-12). E7 tablosu sunucunun `rules` yanıtıyla aynıdır.

import type { Paginated } from "../../lib/pagination";
import type {
  AyiklamaBelgesi,
  AyiklamaKurallari,
  Kalem,
  NadirListeAyrintisi,
  NadirNusha,
  RaporSayilari,
  Teklif,
  TeklifAyrintisi,
  YilRaporu,
} from "./api";

export function sayfa<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results };
}

export function kurallar(): AyiklamaKurallari {
  return {
    reasons: [
      {
        value: "WORN",
        label: "Aşırı kullanımdan yıpranmış",
        paths: ["TMY_27", "TMY_28"],
        default_path: "TMY_27",
        needs_criterion: false,
      },
      {
        value: "OBSOLETE",
        label: "Bilimsel değeri kalmamış",
        paths: ["TMY_28"],
        default_path: "TMY_28",
        needs_criterion: false,
      },
      {
        value: "LEVEL_MISMATCH",
        label: "Kurumun düzeyine uygun değil",
        paths: ["TMY_24_2", "TMY_31"],
        default_path: "TMY_24_2",
        needs_criterion: false,
      },
      {
        value: "CRITERIA_MISMATCH",
        label: "10. maddedeki ölçütlere uygun değil",
        paths: ["TMY_28"],
        default_path: "TMY_28",
        needs_criterion: true,
      },
    ],
    paths: [
      {
        value: "TMY_27",
        label: "Kullanılmaz hâle gelme nedeniyle kayıttan düşme (TMY 27/1)",
        is_transfer: false,
      },
      {
        value: "TMY_28",
        label: "Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)",
        is_transfer: false,
      },
      { value: "TMY_24_2", label: "Başka bir MEB okuluna devir (TMY 24/2)", is_transfer: true },
      {
        value: "TMY_31",
        label: "Başka bir kamu idaresine bedelsiz devir (TMY 31)",
        is_transfer: true,
      },
    ],
    criteria: [
      {
        value: "10_1_A",
        label: "Türk millî eğitiminin genel amaçları ve temel ilkelerine uygun değil",
      },
      { value: "10_4", label: "Kütüphanede bulundurulamaz (Md. 10/4)" },
    ],
  };
}

export function kalem(ek: Partial<Kalem> = {}): Kalem {
  return {
    id: 11,
    copy: 101,
    barcode: "2026000101",
    barcode_display: "2026-000101",
    work: 7,
    work_title: "Deneme Eseri",
    work_authors: "Deneme Yazar",
    call_number: "813 DEN",
    copy_status: "AVAILABLE",
    copy_status_display: "Rafta",
    reason: "WORN",
    reason_display: "Aşırı kullanımdan yıpranmış",
    criterion: "",
    criterion_display: "",
    tmy_path: "TMY_27",
    tmy_path_display: "Kullanılmaz hâle gelme nedeniyle kayıttan düşme (TMY 27/1)",
    is_transfer: false,
    transfer_target: "",
    state: "PROPOSED",
    state_display: "Teklif listesinde",
    exclusion_reason: "",
    copy_is_rare: false,
    destruction_decided: false,
    ...ek,
  };
}

export function devirKalemi(ek: Partial<Kalem> = {}): Kalem {
  return kalem({
    id: 12,
    copy: 102,
    barcode_display: "2026-000102",
    work_title: "Düzeye Uygun Olmayan Eser",
    reason: "LEVEL_MISMATCH",
    reason_display: "Kurumun düzeyine uygun değil",
    tmy_path: "TMY_24_2",
    tmy_path_display: "Başka bir MEB okuluna devir (TMY 24/2)",
    is_transfer: true,
    transfer_target: "Deneme İlkokulu",
    ...ek,
  });
}

export function teklifSatiri(ek: Partial<Teklif> = {}): Teklif {
  return {
    id: 3,
    school_year: 1,
    school_year_name: "2026-2027",
    status: "DRAFT",
    status_display: "Taslak",
    commission_decision: null,
    decision: null,
    submitted_at: null,
    decided_at: null,
    approved_on: null,
    approved_at: null,
    destruction_decided: false,
    applied_at: null,
    cancelled_at: null,
    cancel_reason: "",
    notes: "",
    counts: { items: 2, proposed: 2, excluded: 0, applied: 0, write_off: 1, transfer: 1 },
    created_at: "2027-06-01T10:00:00+03:00",
    ...ek,
  };
}

export function teklif(ek: Partial<TeklifAyrintisi> = {}): TeklifAyrintisi {
  return {
    ...teklifSatiri(),
    approved_by_name: "",
    tmy_commission_members: "",
    items: [kalem(), devirKalemi()],
    ...ek,
  };
}

export function belgeler(acik: string[] = ["teklif-listesi"]): AyiklamaBelgesi[] {
  const tanimlar: Array<[string, string, Array<"pdf" | "xlsx">]> = [
    ["teklif-listesi", "Ayıklama teklif listesi", ["pdf"]],
    ["ayiklama-tutanagi", "Ayıklama tutanağı", ["pdf"]],
    ["kayittan-dusme", "Kayıttan düşme teklif listesi", ["pdf"]],
    ["imha-tutanagi", "İmha tutanağı", ["pdf"]],
    ["devir-listesi", "Devir listesi", ["pdf", "xlsx"]],
  ];
  return tanimlar.map(([kind, title, formats]) => ({
    kind,
    title,
    formats,
    available: acik.includes(kind),
    reason: acik.includes(kind) ? "" : "Komisyon kararı bağlandıktan sonra basılır.",
  }));
}

export function nadirNusha(ek: Partial<NadirNusha> = {}): NadirNusha {
  return {
    id: 201,
    barcode_display: "2026-000201",
    work: 9,
    work_title: "Deneme Yazması",
    work_authors: "Deneme Hattat",
    status: "AVAILABLE",
    status_display: "Rafta",
    sent: false,
    ...ek,
  };
}

export function nadirListe(ek: Partial<NadirListeAyrintisi> = {}): NadirListeAyrintisi {
  return {
    id: 5,
    school_year: 1,
    school_year_name: "2026-2027",
    commission_decision: null,
    decision: null,
    status: "DRAFT",
    status_display: "Hazırlanıyor",
    sent_on: null,
    sent_document_no: "",
    notes: "",
    item_count: 1,
    created_at: "2027-06-02T10:00:00+03:00",
    items: [
      {
        id: 51,
        copy: 202,
        barcode_display: "2026-000202",
        work_title: "Deneme Nadir Eseri",
        work_authors: "Deneme Müellif",
        publisher: "Deneme Matbaası",
        publish_year: 1890,
        call_number: "",
        copy_status_display: "Rafta",
      },
    ],
    ...ek,
  };
}

export function raporSayilari(): RaporSayilari {
  return {
    schema: 2,
    generated_on: "2027-06-20",
    school_year: { label: "2026-2027", start_date: "2026-09-07", end_date: "2027-06-25" },
    period: { start: "2026-09-07", end: "2027-06-25" },
    collection: {
      catalog_work_count: 812,
      work_count: 790,
      register_count: 1200,
      in_stock_count: 1150,
      status_counts: { AVAILABLE: 1100 },
      resource_type_counts: { BOOK: 1150 },
      reference_count: 20,
      rare_count: 2,
      sections: [],
    },
    acquisitions: {
      copies_by_method: { DONATION: 30 },
      total_copies: 30,
      register_entry_copies: 1100,
      works: 25,
      donation_intakes_decided: 2,
      donation_items_accepted: 25,
      donation_items_rejected: 3,
    },
    weeding: { withdrawn: 14, transferred: 6, by_reason: {}, by_path: {}, batches_applied: 1 },
    findings: {
      repairs_sent: 4,
      repairs_returned: 3,
      in_repair_now: 1,
      damage_cases: 2,
      loss_cases: 1,
      resolutions: {},
      write_off_proposals: 1,
      open_cases_now: 1,
      lost_copies_now: 1,
    },
    circulation: {
      k_threshold: 5,
      loans: 640,
      returns: 610,
      distinct_borrowers: 211,
      by_member_type: {
        STUDENT: { loans: 600, below_threshold: false },
        TEACHER: { loans: 40, below_threshold: false },
        STAFF: { loans: null, below_threshold: true },
      },
      by_class_level: [],
      by_month: [],
      deliveries: { section: 3, teacher: 1 },
      active_members: { STUDENT: 300, TEACHER: 20, STAFF: null },
    },
  };
}

export function rapor(ek: Partial<YilRaporu> = {}): YilRaporu {
  return {
    id: 8,
    school_year: 1,
    school_year_name: "2026-2027",
    document_date: null,
    document_no: "",
    findings: "",
    is_finalized: false,
    finalized_at: null,
    created_at: "2027-06-20T10:00:00+03:00",
    stats: raporSayilari(),
    ...ek,
  };
}
