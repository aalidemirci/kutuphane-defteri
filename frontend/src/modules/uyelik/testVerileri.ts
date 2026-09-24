// Üyelik ekranı testlerinin ortak uydurma verileri (KVKK: gerçek kişi yok).

import type { MemberCardRow, Membership, OverdueLoanRow } from "./api";

export function uyelik(alanlar: Partial<Membership> = {}): Membership {
  return {
    id: 1,
    student: 10,
    personnel: null,
    member_type: "STUDENT",
    member_type_display: "öğrenci",
    full_name: "Deneme Öğrenci",
    class_label: "9/A",
    student_number: "701",
    card_no: "90000016",
    card_printed_at: null,
    status: "ACTIVE",
    status_display: "Aktif",
    requested_at: "2026-09-20",
    started_at: "2026-09-21",
    terminated_at: null,
    termination_reason: "",
    termination_reason_display: "",
    open_loan_count: 1,
    overdue_loan_count: 0,
    loan_limit: 3,
    remaining_quota: 2,
    ...alanlar,
  };
}

export function kartSatiri(alanlar: Partial<MemberCardRow> = {}): MemberCardRow {
  return {
    id: 1,
    full_name: "Deneme Öğrenci",
    member_type: "STUDENT",
    member_type_display: "öğrenci",
    class_label: "9/A",
    student_number: "701",
    card_no: "90000016",
    card_printed_at: null,
    started_at: "2026-09-21",
    ...alanlar,
  };
}

export function gecikmeSatiri(alanlar: Partial<OverdueLoanRow> = {}): OverdueLoanRow {
  return {
    id: 1,
    membership_id: 1,
    full_name: "Deneme Öğrenci",
    person_label: "9/A",
    is_student: true,
    barcode: "2026000001",
    barcode_display: "2026-000001",
    work_title: "Deneme Kaynağı",
    loaned_at: "2026-09-01T10:00:00+03:00",
    due_date: "2026-09-16",
    overdue_days: 8,
    ...alanlar,
  };
}

export function sayfa<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

export const KART_SABLONU = {
  id: 7,
  name: "Üye kartı — 85 × 54 mm, 10'lu",
  kind: "CARD" as const,
  kind_display: "Üye kartı",
  page_margin_top: 13.5,
  page_margin_left: 20,
  label_width: 85,
  label_height: 54,
  rows: 5,
  cols: 2,
  gutter_x: 0,
  gutter_y: 0,
  corner_radius: 0,
  is_default: true,
  labels_per_sheet: 10,
  supports_qr: true,
  supports_barcode: true,
  updated_at: "2026-09-24T10:00:00+03:00",
};
