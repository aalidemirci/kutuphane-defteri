// Sayım testlerinin uydurma verileri (F9). Kişi adları uydurmadır ("Deneme …").

import type { Paginated } from "../../lib/pagination";
import type {
  Sayim,
  SayimAyrintisi,
  SayimBelgesi,
  SayimDurumOzeti,
  SayimIlerlemesi,
  SayimKalemi,
  SayimOzeti,
} from "./api";

export function sayfa<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

export function ozet(ek: Partial<SayimOzeti> = {}): SayimOzeti {
  return {
    snapshot: 120,
    results: { PENDING: 0, FOUND: 110, BY_RECORD: 6, MISSING: 4, SURPLUS: 2, EXITED: 0 },
    outcomes: {
      WRITTEN_OFF: 0,
      NOT_APPROVED: 0,
      STATE_CHANGED: 0,
      RECONCILED: 0,
      ENTERED: 0,
      NOT_ENTERED: 0,
    },
    physical_expected: 114,
    physical_found: 110,
    by_record_basis: 6,
    surplus: 2,
    surplus_unresolved: 0,
    surplus_excluded: 1,
    surplus_bound: 0,
    damage_write_off: 1,
    found_in_round2: 0,
    missing_recorded_lost: 0,
    missing_in_repair: 0,
    ...ek,
  };
}

export function sayimSatiri(ek: Partial<Sayim> = {}): Sayim {
  return {
    id: 7,
    status: "IN_PROGRESS",
    status_display: "Sürüyor",
    fiscal_year: 2026,
    round: 1,
    tmy_stop: true,
    service_pause: true,
    created_at: "2026-12-20T09:00:00+03:00",
    started_at: "2026-12-21T09:00:00+03:00",
    completed_at: null,
    approved_on: null,
    cancelled_at: null,
    ...ek,
  };
}

const DURUM_ADI: Record<Sayim["status"], string> = {
  DRAFT: "Taslak",
  IN_PROGRESS: "Sürüyor",
  COMPLETED: "Tamamlandı",
  APPROVED: "Onaylandı",
  CANCELLED: "İptal edildi",
};

export function sayim(ek: Partial<SayimAyrintisi> = {}): SayimAyrintisi {
  const status = ek.status ?? "IN_PROGRESS";
  return {
    ...sayimSatiri({ status }),
    status_display: DURUM_ADI[status],
    committee_chair: "Deneme Kurulbaşkanı",
    committee_property_officer: "Deneme Taşınırkayıt",
    committee_members: "Deneme Kurulüyesi",
    tmy_stop_requested_on: "2026-12-20",
    tmy_stop_by_name: "Deneme Harcama",
    tmy_stop_on: "2026-12-20",
    service_pause_decision: "2026/15",
    loan_basis: "BY_RECORD",
    loan_basis_display: "Kayda göre alınır",
    section_delivery_basis: "IN_PLACE",
    section_delivery_basis_display: "Yerinde sayılır",
    teacher_delivery_basis: "BY_RECORD",
    teacher_delivery_basis_display: "Kayda göre alınır",
    repair_basis: "BY_RECORD",
    repair_basis_display: "Kayda göre alınır — onarımda",
    notes: "",
    round2_started_at: null,
    approved_by_name: "",
    approved_at: null,
    surplus_acquisition: null,
    cancel_reason: "",
    locks_active: status === "IN_PROGRESS" || status === "COMPLETED",
    options: [
      {
        key: "tmy_32_3",
        label: "TMY 32/3 durdurması",
        selected: true,
        text: "Sayım kurulunun 20.12.2026 tarihli talebi üzerine harcama yetkilisince 20.12.2026 tarihinde durduruldu: edinim ve yeni nüsha kaydı, kayıttan düşme, devir, kayıp bildirimi, kayıp dosyasının bulunma ve bedel adımları dışındaki çözümü ve hasar dosyasında kayıttan düşme önerisi. Durdurma ödüncü ve iadeyi kapsamaz.",
        basis: "TMY 32/3",
      },
      {
        key: "service_pause",
        label: "Sayım için hizmet arası",
        selected: true,
        text: "Seçildi (okul kararı — 2026/15): sayım süresince yeni ödünç ve teslim durdurulur; iade ve teslimden geri alma açıktır.",
        basis: "Okul kararı (TMY 32/3 ikinci cümle: sayımda önlem almak kurulun görevidir)",
      },
      {
        key: "return",
        label: "İade",
        selected: false,
        text: "İade hiçbir durumda durdurulmaz (Yönetmelik Md. 23/1-c).",
        basis: "Yönetmelik Md. 23/1-c",
      },
    ],
    basis_lines: [
      {
        category: "loan",
        label: "Ödünçteki nüsha",
        basis: "BY_RECORD",
        basis_display: "Kayda göre alınır",
        dayanak: "Kayda göre alınır: TMY 32/5'e kıyasen; 23/4 (ödünç takip sistemiyle izlenir).",
      },
      {
        category: "section_delivery",
        label: "Sınıf kitaplığına teslim edilen nüsha",
        basis: "IN_PLACE",
        basis_display: "Yerinde sayılır",
        dayanak:
          "Sınıf kitaplığında yerinde sayılır: TMY 32/5 birinci cümleye kıyasen (teslim listesi Dayanıklı Taşınırlar Listesi işlevini görür — 23/6'ya kıyasen).",
      },
      {
        category: "teacher_delivery",
        label: "Öğretmene teslim edilen nüsha",
        basis: "BY_RECORD",
        basis_display: "Kayda göre alınır",
        dayanak:
          "Kayda göre alınır: Taşınır Teslim Belgesi düzenlendiyse TMY 32/5 ikinci cümle, düzenlenmediyse 32/5'e kıyasen (23/4).",
      },
      {
        category: "repair",
        label: "Onarımdaki nüsha",
        basis: "BY_RECORD",
        basis_display: "Kayda göre alınır — onarımda",
        dayanak:
          "Kayda göre alınır — onarımda (onarım kaydıyla izlenir): sayım kurulunun kararıdır; Taşınır Mal Yönetmeliğinde onarıma gönderilmiş taşınırın sayımına ilişkin doğrudan hüküm yoktur.",
      },
    ],
    basis_choices: {
      loan_basis: [
        { value: "COLLECT", label: "Sayımdan önce toplanır" },
        { value: "BY_RECORD", label: "Kayda göre alınır" },
      ],
      section_delivery_basis: [
        { value: "IN_PLACE", label: "Yerinde sayılır" },
        { value: "COLLECT", label: "Sayımdan önce toplanır" },
      ],
      teacher_delivery_basis: [
        { value: "COLLECT", label: "Sayımdan önce toplanır" },
        { value: "BY_RECORD", label: "Kayda göre alınır" },
      ],
      repair_basis: [
        { value: "COLLECT", label: "Sayımdan önce geri alınır" },
        { value: "BY_RECORD", label: "Kayda göre alınır — onarımda" },
      ],
    },
    summary: ozet(),
    ...ek,
  };
}

export function taslakSayim(ek: Partial<SayimAyrintisi> = {}): SayimAyrintisi {
  return sayim({
    status: "DRAFT",
    status_display: "Taslak",
    started_at: null,
    fiscal_year: null,
    tmy_stop: false,
    tmy_stop_requested_on: null,
    tmy_stop_by_name: "",
    tmy_stop_on: null,
    service_pause: false,
    service_pause_decision: "",
    committee_chair: "",
    committee_property_officer: "",
    committee_members: "",
    locks_active: false,
    ...ek,
  });
}

export function kalem(ek: Partial<SayimKalemi> = {}): SayimKalemi {
  return {
    id: 501,
    copy: 41,
    barcode: "2026000041",
    barcode_display: "2026-000041",
    work: 9,
    work_title: "Bulunamayan Kitap",
    work_authors: "Deneme Yazar",
    call_number: "",
    section: 2,
    section_name: "Roman",
    class_library: "",
    copy_status: "AVAILABLE",
    copy_status_display: "Rafta",
    expected_status: "AVAILABLE",
    expected_status_display: "Rafta",
    delivery_kind: "",
    basis: "LIBRARY",
    basis_display: "Kütüphanede sayılır",
    basis_fallback: false,
    result: "MISSING",
    result_display: "Noksan",
    found_in_round: null,
    found_via: "",
    found_via_display: "",
    scanned_at: null,
    status_at_completion: "AVAILABLE",
    damage_write_off: false,
    case: null,
    case_type: "",
    case_resolution_display: "",
    outcome: "",
    outcome_display: "",
    write_off_path: "",
    write_off_path_display: "",
    outcome_note: "",
    is_surplus: false,
    surplus_barcode: "",
    surplus_barcode_display: "",
    surplus_copy: null,
    surplus_work: null,
    surplus_work_title: "",
    surplus_note: "",
    surplus_excluded: false,
    created_copy: null,
    created_copy_barcode: "",
    surplus_bound_barcode: "",
    ...ek,
  };
}

export function fazlaKalemi(ek: Partial<SayimKalemi> = {}): SayimKalemi {
  return kalem({
    id: 601,
    copy: null,
    barcode: "",
    barcode_display: "",
    work: null,
    work_title: "",
    work_authors: "",
    section: null,
    section_name: "",
    copy_status: "",
    copy_status_display: "",
    expected_status: "",
    expected_status_display: "",
    basis: "",
    basis_display: "",
    result: "SURPLUS",
    result_display: "Fazla",
    status_at_completion: "",
    is_surplus: true,
    surplus_barcode: "4455",
    surplus_barcode_display: "4455",
    surplus_note: "Rafın arkasında bulundu",
    ...ek,
  });
}

export function ilerleme(ek: Partial<SayimIlerlemesi> = {}): SayimIlerlemesi {
  return {
    round: 1,
    sections: [
      { section: 2, name: "Roman", expected: 80, found: 60 },
      { section: null, name: "", expected: 20, found: 5 },
    ],
    class_libraries: [{ class_section: 3, label: "9/A", expected: 14, found: 10 }],
    physical_expected: 114,
    physical_found: 75,
    by_record_basis: 6,
    surplus: 1,
    ...ek,
  };
}

export function durumOzeti(ek: Partial<SayimDurumOzeti> = {}): SayimDurumOzeti {
  return {
    live: {
      id: 7,
      status: "IN_PROGRESS",
      status_display: "Sürüyor",
      round: 1,
      started_at: "2026-12-21T09:00:00+03:00",
      tmy_stop: true,
      service_pause: true,
      physical_expected: 114,
      physical_found: 75,
      surplus: 1,
    },
    tmy_stop_active: true,
    service_pause_active: true,
    returns_open: true,
    ...ek,
  };
}

export function belgeler(ek: Partial<SayimBelgesi> = {}): SayimBelgesi[] {
  return [
    {
      kind: "sayim-tutanagi",
      title: "Sayım tutanağı",
      formats: ["pdf", "xlsx"],
      available: true,
      reason: "",
      ...ek,
    },
  ];
}
