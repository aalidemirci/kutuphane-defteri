// Yıl akışı ve ilişik testlerinin uydurma verileri (gerçek kişi yok — CLAUDE.md §2-12).

import type { Paginated } from "../../lib/pagination";
import type { IlisikSatiri, SinifKitapligi, YilAkislari } from "./api";

export function sayfa<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results };
}

export function ilisikSatiri(ek: Partial<IlisikSatiri> = {}): IlisikSatiri {
  return {
    person_type: "student",
    person_id: 1,
    full_name: "Deneme Öğrenci",
    person_label: "12/A",
    student_number: "701",
    group: "graduating",
    is_graduating: true,
    status_text: "Son sınıf",
    left_at: null,
    in_leave_pool: false,
    is_clear: false,
    open_loan_count: 1,
    overdue_loan_count: 0,
    open_delivery_count: 0,
    open_case_count: 0,
    loans: [
      {
        id: 11,
        barcode: "2026000011",
        barcode_display: "2026-000011",
        work_title: "Deneme Kaynağı",
        loaned_at: "2027-05-10T09:00:00+03:00",
        due_date: "2027-05-25",
        overdue_days: 0,
      },
    ],
    deliveries: [],
    cases: [],
    ...ek,
  };
}

export function temizSatir(ek: Partial<IlisikSatiri> = {}): IlisikSatiri {
  return ilisikSatiri({
    is_clear: true,
    open_loan_count: 0,
    loans: [],
    ...ek,
  });
}

export function sinifKitapligi(ek: Partial<SinifKitapligi> = {}): SinifKitapligi {
  return {
    section_id: 5,
    section_label: "12/A",
    school_year_name: "2026-2027",
    is_graduating: true,
    is_active_year: true,
    delivery_count: 4,
    document_numbers: ["2026/2"],
    open_case_count: 0,
    ...ek,
  };
}

export function akislar(
  ek: {
    yilSonu?: Partial<YilAkislari["year_end"]>;
    yilBasi?: Partial<YilAkislari["year_start"]>;
  } = {},
): YilAkislari {
  return {
    today: "2027-05-17",
    year_end: {
      in_window: true,
      school_year: { name: "2026-2027", start_date: "2026-09-07", end_date: "2027-06-25" },
      graduating_level: 12,
      last_loan_date: null,
      last_loan_date_graduating: null,
      last_loan_date_stale: false,
      last_loan_date_graduating_stale: false,
      graduating_students: 40,
      graduating_clear_students: 37,
      counts: {
        persons: 5,
        graduating_persons: 3,
        leaving_persons: 1,
        open_loans: 9,
        graduating_open_loans: 4,
        leaving_open_loans: 1,
        teacher_deliveries: 3,
        section_deliveries: 4,
        graduating_section_deliveries: 4,
        open_cases: 1,
      },
      steps: { dates: false, collection: false, graduating: false, clearance: false },
      ...ek.yilSonu,
    },
    year_start: {
      in_window: false,
      school_year: { name: "2026-2027", start_date: "2026-09-07", end_date: "2027-06-25" },
      school_year_ready: true,
      kademe_missing: false,
      last_student_import: "2026-08-28",
      last_personnel_import: null,
      student_import_fresh: true,
      personnel_import_fresh: false,
      leave_pool_students: 2,
      leave_pool_personnel: 0,
      school_break_count: 0,
      holidays_missing_years: [2027],
      stale_last_loan_dates: false,
      steps: { school_year: true, import: true, leave_pool: false, closed_days: false },
      ...ek.yilBasi,
    },
  };
}
