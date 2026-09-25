// Katalog testlerinin ortak kalıpları (backend serializer alan kümeleriyle
// birebir). Alan kümesi büyüdükçe her test dosyası ayrı ayrı güncellenmesin diye
// tek yerde durur; testler yalnız farkı yazar.
//
// KVKK: bütün adlar UYDURMADIR (CLAUDE.md §2-12) — gerçek kitap, bağışçı ya da
// komisyon üyesi verisi kullanılmaz.

import type {
  Acquisition,
  AktarimKosusu,
  AktarimRaporu,
  AktarimSatiri,
  AktarimSayilari,
  CevrimdisiKunyeOnizleme,
  CevrimdisiKunyeSatiri,
  CommissionDecision,
  Copy,
  DonationIntake,
  DonationIntakeItem,
  KunyeAlani,
  KunyeSonucu,
  LibraryPolicy,
  Paginated,
  Section,
  Work,
} from "../modules/kutuphane/api";

/** Tek sayfalık DRF yanıtı (`count` verilmezse dizinin uzunluğu). */
export function sayfa<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results };
}

export function bolum(ozel: Partial<Section> = {}): Section {
  return {
    id: 1,
    name: "Edebiyat",
    dewey_from: "800",
    dewey_to: "899",
    description: "",
    sort_order: 10,
    ...ozel,
  };
}

export function eser(ozel: Partial<Work> = {}): Work {
  return {
    id: 7,
    title: "Şiir Defteri",
    authors: "Ayşe Yılmaz",
    translator: "",
    edition: "",
    publisher: "Deneme Yayınları",
    publish_year: 2020,
    isbn: "",
    isbn13: "",
    isbn_warning: "",
    subjects: "Şiir",
    classification_code: "811",
    classification_source: "MANUAL",
    classification_source_display: "Elle girildi",
    call_number: "811 YIL",
    resource_type: "BOOK",
    resource_type_display: "Kitap",
    language: "Türkçe",
    section: 1,
    section_name: "Edebiyat",
    is_digital: false,
    copy_count: 2,
    available_copy_count: 1,
    created_at: "2026-09-21T09:00:00+03:00",
    ...ozel,
  };
}

export function nusha(ozel: Partial<Copy> = {}): Copy {
  return {
    id: 21,
    work: 7,
    work_title: "Şiir Defteri",
    work_authors: "Ayşe Yılmaz",
    call_number: "811 YIL",
    resource_type: "BOOK",
    acquisition: 3,
    accession_no: 2026000123,
    barcode: "2026000123",
    barcode_display: "2026-000123",
    external_asset_ref: "",
    old_register_no: "",
    section: 1,
    section_name: "Edebiyat",
    is_reference: false,
    is_out_of_print: false,
    is_bound_periodical: false,
    is_rare_or_manuscript: false,
    status: "AVAILABLE",
    status_display: "Rafta",
    is_loanable: true,
    not_loanable_reason: "",
    label_printed_at: null,
    label_verified_at: null,
    spine_label_printed_at: null,
    created_at: "2026-09-21T09:00:00+03:00",
    ...ozel,
  };
}

export function edinim(ozel: Partial<Acquisition> = {}): Acquisition {
  return {
    id: 3,
    method: "PURCHASE",
    method_display: "Satın alma",
    date: "2026-09-10",
    source_note: "",
    unit_price: null,
    commission_decision: null,
    notes: "",
    copy_count: 2,
    created_at: "2026-09-10T09:00:00+03:00",
    ...ozel,
  };
}

export function komisyonKarari(ozel: Partial<CommissionDecision> = {}): CommissionDecision {
  return {
    id: 5,
    decision_type: "DONATION_REVIEW",
    decision_type_display: "Bağış değerlendirme",
    decision_date: "2026-09-15",
    decision_no: "2026/4",
    chair_name: "Mehmet Demir",
    chair_title: "Şube müdürü",
    participants_text: "",
    notes: "",
    in_use: false,
    usage: { acquisitions: 0, donation_intakes: 0, weeding_batches: 0, rare_works_submissions: 0 },
    created_at: "2026-09-15T09:00:00+03:00",
    ...ozel,
  };
}

export function bagisKalemi(ozel: Partial<DonationIntakeItem> = {}): DonationIntakeItem {
  return {
    id: 31,
    title: "Ilık Sular",
    authors: "Zeynep Kaya",
    publisher: "",
    publish_year: null,
    isbn: "",
    copies: 1,
    decision: "PENDING",
    decision_display: "Karar bekliyor",
    reject_reason: "",
    work: null,
    work_title: null,
    notes: "",
    ...ozel,
  };
}

export function bagisOnKaydi(ozel: Partial<DonationIntake> = {}): DonationIntake {
  return {
    id: 11,
    donor_name: "Fatma Aydın",
    received_date: "2026-09-18",
    status: "PENDING",
    status_display: "Karar bekliyor",
    commission_decision: null,
    acquisition: null,
    decided_at: null,
    notes: "",
    items: [bagisKalemi()],
    item_count: 1,
    created_at: "2026-09-18T09:00:00+03:00",
    ...ozel,
  };
}

export function politika(ozel: Partial<LibraryPolicy> = {}): LibraryPolicy {
  return {
    loan_period_days: 15,
    max_loans_student: 3,
    max_loans_teacher: 5,
    max_loans_staff: 3,
    staff_loans_enabled: false,
    staff_loans_decision_date: null,
    staff_loans_decision_no: "",
    block_loan_if_overdue: true,
    shift_due_date_on_school_break: true,
    last_loan_date: null,
    last_loan_date_graduating: null,
    idle_minutes: 3,
    admin_max_minutes: 30,
    popular_min_members: 5,
    retention_years_after_termination: 2,
    retention_years_returned_loans: 1,
    retention_years_closed_cases: 2,
    retention_years_closed_deliveries: 2,
    // Künye getirme varsayılan KAPALI (§8.5-1); kaynak seçimleri yalnız açıkken anlamlı.
    metadata_lookup_enabled: false,
    metadata_lookup_ministry: true,
    metadata_lookup_openlibrary: true,
    updated_at: "2026-09-21T09:00:00+03:00",
    ...ozel,
  };
}

// ---------------------------------------------------------------------------
// Toplu katalog aktarımı (F3, §8.1)
// ---------------------------------------------------------------------------

/** Rapordaki sayaçlar — backend her koşuda hepsini doldurur. */
export function aktarimSayilari(ozel: Partial<AktarimSayilari> = {}): AktarimSayilari {
  return {
    total_rows: 2,
    imported_rows: 2,
    new_works: 2,
    existing_matches: 0,
    suspect: 0,
    skipped_rows: 0,
    error_rows: 0,
    copies_created: 3,
    reference_defaults: 0,
    estimated_codes: 0,
    corrections: 0,
    sections_created: 0,
    ...ozel,
  };
}

export function aktarimSatiri(ozel: Partial<AktarimSatiri> = {}): AktarimSatiri {
  return {
    row: 2,
    title: "Gökyüzü Masalları",
    bucket: "new",
    work: null,
    work_row: null,
    copies: 1,
    copies_created: 0,
    section: "Edebiyat",
    shelf_location: "Edebiyat",
    is_reference: false,
    reference_by_textbook: false,
    classification_source: "MANUAL",
    needs_decision: false,
    decision: "",
    candidates: [],
    candidate_count: 0,
    candidates_truncated: false,
    corrections: [],
    issues: [],
    ...ozel,
  };
}

export function aktarimRaporu(ozel: Partial<AktarimRaporu> = {}): AktarimRaporu {
  return {
    payload_sha256: "a".repeat(64),
    source: "EXCEL",
    schema_version: "v1",
    file_name: "katalog.xlsx",
    dry_run: true,
    already_applied: false,
    applied_at: "",
    stats: aktarimSayilari(),
    rows: [aktarimSatiri(), aktarimSatiri({ row: 3, title: "Deniz Fenerleri" })],
    rows_truncated: false,
    unknown_sections: [],
    unknown_headers: [],
    missing_columns: [],
    pending_decisions: [],
    label_batch: null,
    run_id: 11,
    ...ozel,
  };
}

export function aktarimKosusu(ozel: Partial<AktarimKosusu> = {}): AktarimKosusu {
  return {
    id: 11,
    uploaded_file_name: "katalog.xlsx",
    source: "EXCEL",
    source_display: "Excel dosyası",
    status: "APPLIED",
    status_display: "Uygulandı",
    payload_sha256: "a".repeat(64),
    schema_version: "v1",
    acquisition: 3,
    stats: aktarimSayilari(),
    report: {},
    created_at: "2026-09-23T10:00:00+03:00",
    ...ozel,
  };
}

// ---------------------------------------------------------------------------
// ISBN ile künye getirme (U13, §8.5)
// ---------------------------------------------------------------------------

export function kunyeAlani(ozel: Partial<KunyeAlani> = {}): KunyeAlani {
  return {
    alan: "title",
    etiket: "kaynak adı",
    deger: "Gökyüzü Masalları",
    mevcut_deger: "",
    dolu: false,
    farkli: true,
    ...ozel,
  };
}

export function kunyeSonucu(ozel: Partial<KunyeSonucu> = {}): KunyeSonucu {
  return {
    isbn13: "9789750812345",
    bulundu: true,
    kaynak: "MINISTRY",
    kaynak_adi: "Bakanlık kataloğu",
    kaynak_tarihi: "2026-09-23",
    kaynak_etiketi: "Bakanlık kataloğu, 23.09.2026",
    kayit_sayisi: 3,
    onbellekten: false,
    rozet: "Dış kaynaktan alındı, doğrulayın",
    ileti: "",
    uyarilar: ["Çevirmen dışarıdan doldurulmaz; çeviri eserde elle yazın."],
    ek_bilgi: { pages: 180, place: "İstanbul" },
    alanlar: [
      kunyeAlani(),
      kunyeAlani({ alan: "authors", etiket: "yazar(lar)", deger: "Ayşe Yılmaz" }),
      kunyeAlani({ alan: "publish_year", etiket: "yayın yılı", deger: 2019 }),
    ],
    ...ozel,
  };
}

export function cevrimdisiKunyeSatiri(
  ozel: Partial<CevrimdisiKunyeSatiri> = {},
): CevrimdisiKunyeSatiri {
  return {
    satir_no: 2,
    isbn13: "9789750812345",
    durum: "eslesti",
    work: 7,
    work_title: "Şiir Defteri",
    uyarilar: [],
    alanlar: [kunyeAlani({ alan: "publisher", etiket: "yayınevi", deger: "Deneme Yayınları" })],
    ...ozel,
  };
}

export function cevrimdisiKunyeOnizleme(
  ozel: Partial<CevrimdisiKunyeOnizleme> = {},
): CevrimdisiKunyeOnizleme {
  return {
    kaynak_adi: "Çevrimdışı künye dosyası",
    kaynak_etiketi: "Çevrimdışı künye dosyası, 23.09.2026",
    rozet: "Dış kaynaktan alındı, doğrulayın",
    sayilar: { eslesti: 1, eser_yok: 0, coklu_eser: 0, isbn_yok: 0 },
    atlanan_sutunlar: [],
    satirlar: [cevrimdisiKunyeSatiri()],
    ...ozel,
  };
}
