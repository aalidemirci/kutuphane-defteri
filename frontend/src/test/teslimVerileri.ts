// Teslim ve kayıp/hasar testlerinin uydurma verileri (F7). Kişi adları uydurmadır
// (docs/sozluk.md §2.1).

import type { Paginated } from "../lib/pagination";
import type { Dosya } from "../modules/kayip/api";
import type { TeslimSatiri } from "../modules/teslim/api";

export function sayfa<T>(results: T[], count = results.length): Paginated<T> {
  return { count, next: null, previous: null, results };
}

export function teslimSatiri(fazlasi: Partial<TeslimSatiri> = {}): TeslimSatiri {
  return {
    id: 1,
    copy: 11,
    barcode: "2026000123",
    barcode_display: "2026-000123",
    work_title: "Deneme Kitabı",
    call_number: "",
    recipient_kind: "SECTION",
    recipient_kind_display: "Sınıf kitaplığı",
    section: 4,
    personnel: null,
    recipient_label: "3/A",
    delivered_on: "2026-09-21",
    expected_return: "2027-06-18",
    expected_return_passed: false,
    document_no: "2026/1",
    status: "OPEN",
    status_display: "Teslimde",
    returned_at: null,
    lost_at: null,
    ...fazlasi,
  };
}

export function dosyaVerisi(fazlasi: Partial<Dosya> = {}): Dosya {
  return {
    id: 5,
    copy: 11,
    barcode: "2026000123",
    barcode_display: "2026-000123",
    work_title: "Deneme Kitabı",
    copy_status: "LOST",
    copy_status_display: "Kayıp",
    case_type: "LOST",
    case_type_display: "Kayıp",
    membership: 3,
    loan: 7,
    delivery: null,
    responsible_name: "Deneme Okur",
    responsible_class_label: "9/A",
    responsible_note: "",
    reported_on: "2026-09-24",
    market_price: null,
    price_determined_at: null,
    price_received_at: null,
    resolution: "PENDING",
    resolution_display: "Çözüm bekliyor",
    is_open: true,
    is_person_open_work: true,
    resolved_at: null,
    write_off_proposed_at: null,
    allowed_resolutions: [
      { value: "FOUND_RETURNED", label: "Bulundu" },
      { value: "REPLACED_SAME", label: "Aynısı temin edildi" },
      { value: "WRITE_OFF_PROPOSED", label: "Kayıttan düşme önerildi" },
    ],
    price_options_available: false,
    created_at: "2026-09-24T10:00:00+03:00",
    ...fazlasi,
  };
}
