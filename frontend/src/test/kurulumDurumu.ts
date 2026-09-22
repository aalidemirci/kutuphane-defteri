// Testlerin ortak `SetupStatus` kalıpları (backend `services/setup.py::setup_status`
// alan kümesiyle birebir). Alan kümesi büyüdükçe her test dosyası ayrı ayrı
// güncellenmesin diye tek yerde durur; testler yalnız farkı yazar.

import type { SetupStatus } from "../modules/okul/api";

/** Kurulum bitmiş, parola kurulu, anahtar doğrulanmış, aktif yıl dönemleriyle hazır; yol haritası boş. */
export const KURULU_DURUM: SetupStatus = {
  setup_completed: true,
  password_set: true,
  recovery_key_confirmed: true,
  school_name: "Örnek Anadolu Lisesi",
  school_info_complete: true,
  has_active_school_year: true,
  active_school_year: {
    id: 1,
    name: "2026-2027",
    start_date: "2026-09-07",
    end_date: "2027-06-25",
    terms_ready: true,
  },
  missing_steps: [],
  student_count: 0,
  personnel_count: 0,
  class_section_count: 0,
  school_break_count: 0,
  roadmap: { marks: {}, hidden: false },
};

/** İlk açılış: parola yok, okul bilgisi yok, ders yılı yok. */
export const ILK_ACILIS_DURUMU: SetupStatus = {
  ...KURULU_DURUM,
  setup_completed: false,
  password_set: false,
  recovery_key_confirmed: false,
  school_name: "",
  school_info_complete: false,
  has_active_school_year: false,
  active_school_year: null,
  missing_steps: ["password", "school", "calendar"],
};
