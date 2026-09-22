// `okul` modülü API istemcisi — kurum künyesi/kurulum, ders yılı + dönemler,
// kapalı günler, kişi sicilleri (öğrenci + personel; ayrılış ve birleştirme), şube
// kataloğu, toplu içe aktarma (e-Okul mutabakatı dahil) ve şablon indirme uçları.
// Backend `apps/okul/{urls,views,serializers}.py` ile BİREBİR. TCKN, veli,
// cinsiyet, fotoğraf, unvan ve branş alanları YOKTUR — o veriler hiç toplanmaz
// (tasarım §6.1).

import { api } from "../../lib/api";
import { getGradeLevels as fetchGradeLevels } from "../../lib/gradeLevels";
import type { GradeLevelOption, GradeLevelsResponse } from "../../lib/gradeLevels";
import { unwrap } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";

export type { GradeLevelOption, GradeLevelsResponse, Paginated };

// ---------------------------------------------------------------------------
// Ders yılı
// ---------------------------------------------------------------------------

/** Ders yılı — SchoolYearSerializer ile birebir (`is_active` salt-okunur). */
export interface SchoolYear {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface SchoolYearCreateBody {
  name: string;
  start_date: string;
  end_date: string;
}

export interface SchoolTerm {
  id: number;
  school_year: number;
  sequence: 1 | 2;
  name: string;
  start_date: string;
  end_date: string;
}

export interface SchoolTermConfigurationBody {
  first_term_end: string;
  second_term_start: string;
}

// ---------------------------------------------------------------------------
// Kapalı günler (resmî tatil, dini bayram, öğrenciye kapalı gün, idari izin)
// ---------------------------------------------------------------------------

/** Backend `HolidayKind` ile birebir. */
export type HolidayKind = "OFFICIAL" | "RELIGIOUS" | "SCHOOL_BREAK" | "OTHER";

/**
 * Tür adları (sözlük): ara tatil ve yarıyıl kanunen tatil DEĞİLDİR — "öğrenciye
 * kapalı gün" diye ayrı adlandırılır, tek başına "tatil" denmez.
 */
export const HOLIDAY_KIND_TR: Record<HolidayKind, string> = {
  SCHOOL_BREAK: "Öğrenciye kapalı gün",
  OFFICIAL: "Resmî tatil",
  RELIGIOUS: "Dini bayram",
  OTHER: "İdari izin / diğer",
};

/** Kapalı gün kaydı — HolidaySerializer ile birebir. Tek günde başlangıç = bitiş. */
export interface Holiday {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  kind: HolidayKind;
  /** Dini bayram tarihi hesapla bulunmuş, Diyanet takvimiyle henüz kesinleşmemiş. */
  is_estimated: boolean;
}

/** Elle ekleme gövdesi — `is_estimated` gönderilmez (elle girilen tarih kesindir). */
export interface HolidayCreateBody {
  name: string;
  start_date: string;
  end_date: string;
  kind: HolidayKind;
}

/** `POST /holidays/seed/` sonucu. */
export interface HolidaySeedResult {
  year: number;
  /** Yeni eklenen kayıt sayısı. */
  created: number;
  /** Zaten var olduğu için atlanan kayıt sayısı. */
  skipped: number;
  /** false → programda bu yılın dini bayram tarihleri yok; elle girilmeli. */
  religious_available: boolean;
}

// ---------------------------------------------------------------------------
// Kurulum sihirbazı / kurum künyesi
// ---------------------------------------------------------------------------

/** `GET /setup/status/` — sihirbaz kapısı + sicil doluluk sayaçları. */
export interface SetupStatus {
  setup_completed: boolean;
  school_name: string;
  has_active_school_year: boolean;
  student_count: number;
  personnel_count: number;
  class_section_count: number;
}

/** Kurum künyesi — evrak antedi buradan çözülür (`setup_completed` salt-okunur). */
export interface SchoolConfig {
  school_name: string;
  province: string;
  district: string;
  principal_name: string;
  /** Açıksa sınıf düzeylerine Hazırlık (0) eklenir. */
  has_prep_class: boolean;
  setup_completed: boolean;
}

/** PUT gövdesi kısmi olabilir — backend MERGE semantiği uygular. */
export type SchoolConfigBody = Partial<Omit<SchoolConfig, "setup_completed">>;

// ---------------------------------------------------------------------------
// Kişi sicilleri
// ---------------------------------------------------------------------------

export type StudentStatus = "ACTIVE" | "LEFT";

export const STUDENT_STATUS_TR: Record<StudentStatus, string> = {
  ACTIVE: "Aktif",
  LEFT: "Ayrıldı",
};

/**
 * Öğrenci sicili — StudentSerializer ile birebir (`full_name`/`class_label` türetilmiş).
 * Okul no şifreli saklanır; arama ve eşleştirme numaranın tamamıyla yapılır.
 * `status` ve `left_at` salt okunurdur: ayrılış `leaveStudent` ile yapılır.
 */
export interface Student {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  student_number: string;
  class_level: number | null;
  class_section: string;
  class_label: string;
  status: StudentStatus;
  /** Ayrılış tarihi (ISO); aktif öğrencide null. */
  left_at: string | null;
}

/** Öğrenci yazma gövdesi — türetilmiş ve salt okunur alanlar gönderilmez. */
export interface StudentWriteBody {
  first_name: string;
  last_name: string;
  student_number?: string;
  class_level?: number | null;
  class_section?: string;
}

/** Üye türü — backend `MemberKind` ile birebir. */
export type MemberKind = "TEACHER" | "STAFF";

/** Sözlük: "öğretmen" / "diğer personel" ("personel" tek başına öğretmen anlamında kullanılmaz). */
export const MEMBER_KIND_TR: Record<MemberKind, string> = {
  TEACHER: "Öğretmen",
  STAFF: "Diğer personel",
};

/**
 * Personel sicili — PersonnelSerializer ile birebir (`full_name` türetilmiş).
 * Unvan ve branş bu programda YOKTUR (branş, küçük okulda öğretmeni kişiye bağlar).
 * `is_active` ve `left_at` salt okunurdur: ayrılış `leavePersonnel` ile yapılır.
 */
export interface Personnel {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  member_kind: MemberKind;
  is_active: boolean;
  /** Ayrılış tarihi (ISO); aktif kişide null. */
  left_at: string | null;
}

export interface PersonnelWriteBody {
  first_name: string;
  last_name: string;
  member_kind?: MemberKind;
}

/**
 * Ayrılış sonucu: hiç üye olmamış ve açık işlemi olmayan kişi o anda silinir
 * (`deleted: true`, kayıt null); aksi hâlde ayrılmış kayıt döner.
 */
export interface StudentLeaveResult {
  deleted: boolean;
  student: Student | null;
}

export interface PersonnelLeaveResult {
  deleted: boolean;
  personnel: Personnel | null;
}

/** Şube kataloğu satırı — ClassSectionSerializer ile birebir. */
export interface ClassSection {
  id: number;
  school_year: number;
  school_year_name: string;
  class_level: number;
  class_section: string;
  class_label: string;
}

export interface ClassSectionWriteBody {
  school_year: number;
  class_level: number;
  class_section: string;
}

export interface StudentListParams {
  search?: string;
  classLevel?: number | null;
  classSection?: string;
  onlyActive?: boolean;
  limit?: number;
  offset?: number;
}

export interface PersonnelListParams {
  search?: string;
  onlyActive?: boolean;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// İçe aktarma (Excel dosyası — e-Okul .xls ya da şablon .xlsx — VEYA pano metni)
// ---------------------------------------------------------------------------

/** Rapordaki tek satır sorunu (uyarı veya atlanan satır). */
export interface ImportIssue {
  row_number: number;
  field: string;
  issue: string;
  raw_value: string;
}

interface ImportReportBase {
  file_hash: string;
  file_name: string;
  total_rows: number;
  processed: number;
  /** Aynı içerik daha önce aktarılmış — UYARIDIR, engel değil. */
  already_imported: boolean;
  /** Önizleme (true) hiçbir şey yazmaz; commit false döner. */
  dry_run: boolean;
  warnings: ImportIssue[];
  skipped: ImportIssue[];
}

/** Öğrenci aktarımının bir şubedeki etkisi (kişisiz sayılar). */
export interface ClassImpact {
  /** "10/A"; sınıfı olmayan öğrencilerde boş. */
  class_label: string;
  class_level: number | null;
  class_section: string;
  created: number;
  updated: number;
  unchanged: number;
  /** Dosyada olmadığı için ayrılmış sayılacak öğrenci sayısı. */
  leaving: number;
}

/** Ayrılacak öğrenci — ad yalnız bu yanıtta gelir, kalıcı rapora yazılmaz. */
export interface LeavingStudent {
  id: number;
  full_name: string;
  student_number: string;
  class_label: string;
}

export interface StudentImportReport extends ImportReportBase {
  created_students: number;
  updated_students: number;
  unchanged_students: number;
  /** Güncellenenlerin içinde: ayrılmışken aynı numarayla dönenler. */
  reactivated_students: number;
  leaving_students: number;
  /** "Bu dosya okulun tam listesidir" onayıyla mı çalıştı? */
  full_list: boolean;
  classes: ClassImpact[];
  leaving: LeavingStudent[];
}

/** Listede olmayan aktif kişi (ad yalnız bu yanıtta gelir). */
export interface MissingPersonnel {
  id: number;
  full_name: string;
}

/**
 * "Olası aynı kişi": ada göre eşleşmeyen yeni satır ↔ listede olmayan kayıt.
 * `new_id` yalnız aktarımdan sonra dolar (önizlemede null); birleştirme
 * `mergePersonnel(existing_id, new_id)` ile yapılır.
 */
export interface SimilarPair {
  row_number: number;
  row_name: string;
  existing_id: number;
  existing_name: string;
  new_id: number | null;
}

export interface PersonnelImportReport extends ImportReportBase {
  created_personnel: number;
  updated_personnel: number;
  unchanged_personnel: number;
  reactivated_personnel: number;
  missing_count: number;
  left_personnel: number;
  similar_pair_count: number;
  missing: MissingPersonnel[];
  similar_pairs: SimilarPair[];
}

export type ImportReport = StudentImportReport | PersonnelImportReport;

/** İçe aktarma girdisi — dosya yolu (multipart) veya pano metni (JSON). */
export type ImportInput = { file: File } | { text: string };

/** Öğrenci mutabakatı seçeneği: dosya okulun tam listesi mi? (varsayılan hayır) */
export interface StudentImportOptions {
  fullList?: boolean;
}

/** Personel mutabakatı seçeneği: listede olmayanlardan ayrılacak sayılanlar. */
export interface PersonnelImportOptions {
  markLeftIds?: number[];
}

/**
 * Öğrenci/personel raporlarının farklı adlandırılmış sayaçlarını (created_students
 * ↔ created_personnel) tek şekle indirger — rapor bileşeni türden bağımsız kalır.
 */
export function importCounts(report: ImportReport): {
  created: number;
  updated: number;
  unchanged: number;
} {
  if ("created_students" in report) {
    return {
      created: report.created_students,
      updated: report.updated_students,
      unchanged: report.unchanged_students,
    };
  }
  return {
    created: report.created_personnel,
    updated: report.updated_personnel,
    unchanged: report.unchanged_personnel,
  };
}

/** Şablon dosya adları — indirme sırasında tarayıcıya verilir (backend ile aynı). */
export const STUDENT_TEMPLATE_FILENAME = "sablon-ogrenci.xlsx";
export const PERSONNEL_TEMPLATE_FILENAME = "sablon-personel.xlsx";

// ---------------------------------------------------------------------------
// Yardımcılar
// ---------------------------------------------------------------------------

/** Parça yoksa yolu olduğu gibi bırakır (gereksiz "?" üretmez). */
function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

/** Düz dizi dönen uçları da sayfalama zarfına indirger (tek tüketim şekli). */
function asPage<T>(data: Paginated<T> | T[]): Paginated<T> {
  return Array.isArray(data)
    ? { count: data.length, next: null, previous: null, results: data }
    : data;
}

type ImportExtra = Record<string, boolean | number[]>;

/**
 * Dosya yolu multipart (`file`), metin yolu JSON (`text`) — backend tam olarak birini
 * bekler. Mutabakat seçenekleri (`full_list`, `mark_left_ids`) iki yolda da gider:
 * çok parçalı gövdede liste alanı tekrarlanarak eklenir (DRF `ListField`).
 */
function importRequest<R>(path: string, input: ImportInput, extra: ImportExtra = {}): Promise<R> {
  if ("file" in input) {
    const form = new FormData();
    form.append("file", input.file);
    for (const [key, value] of Object.entries(extra)) {
      if (Array.isArray(value)) value.forEach((v) => form.append(key, String(v)));
      else form.append(key, String(value));
    }
    return api.postForm<R>(path, form);
  }
  return api.post<R>(path, { text: input.text, ...extra });
}

/** Yalnız anlamlı seçenekler gönderilir (varsayılanlar backend'dedir). */
function studentExtra(options: StudentImportOptions): ImportExtra {
  return options.fullList ? { full_list: true } : {};
}

function personnelExtra(options: PersonnelImportOptions): ImportExtra {
  return options.markLeftIds && options.markLeftIds.length > 0
    ? { mark_left_ids: options.markLeftIds }
    : {};
}

export const okulApi = {
  // --- Kurulum sihirbazı ---

  getSetupStatus: (): Promise<SetupStatus> => api.get<SetupStatus>("/setup/status/"),

  getSchoolConfig: (): Promise<SchoolConfig> => api.get<SchoolConfig>("/setup/school-config/"),

  /** Kısmi gövde gönderilebilir — backend MERGE eder (verilmeyen alan korunur). */
  updateSchoolConfig: (body: SchoolConfigBody): Promise<SchoolConfig> =>
    api.put<SchoolConfig>("/setup/school-config/", body),

  completeSetup: (): Promise<{ setup_completed: boolean }> =>
    api.post<{ setup_completed: boolean }>("/setup/complete/"),

  /** Öğrenim seviyeleri — okul içi sabit 1-12, hazırlık açıksa başta 0. */
  getGradeLevels: (): Promise<GradeLevelsResponse> => fetchGradeLevels(),

  // --- Ders yılları ---

  /** Ders yıllarını listeler (DRF sayfalı yanıt → düz dizi). */
  listSchoolYears: async (): Promise<SchoolYear[]> => {
    const data = await api.get<Paginated<SchoolYear>>("/school-years/?limit=200");
    return unwrap(data);
  },

  /** Yeni ders yılı oluşturur (pasif doğar; aktivasyon ayrı uçtan). */
  createSchoolYear: (body: SchoolYearCreateBody): Promise<SchoolYear> =>
    api.post<SchoolYear>("/school-years/", body),

  /** Ders yılını aktifleştirir — backend diğerlerini pasifler. */
  activateSchoolYear: (id: number): Promise<SchoolYear> =>
    api.post<SchoolYear>(`/school-years/${id}/activate/`),

  listSchoolTerms: (schoolYearId: number): Promise<SchoolTerm[]> =>
    api.get<SchoolTerm[]>(`/school-years/${schoolYearId}/terms/`),

  configureSchoolTerms: (
    schoolYearId: number,
    body: SchoolTermConfigurationBody,
  ): Promise<SchoolTerm[]> => api.put<SchoolTerm[]>(`/school-years/${schoolYearId}/terms/`, body),

  // --- Kapalı günler ---

  /** Takvim yılıyla KESİŞEN kayıtlar, tarih sırasıyla (yıl verilmezse hepsi). */
  listHolidays: (year?: number): Promise<Holiday[]> =>
    api.get<Holiday[]>(year === undefined ? "/holidays/" : `/holidays/?year=${year}`),

  createHoliday: (body: HolidayCreateBody): Promise<Holiday> =>
    api.post<Holiday>("/holidays/", body),

  deleteHoliday: (id: number): Promise<void> => api.del<void>(`/holidays/${id}/`),

  /** Yılın sabit resmî tatilleri + dini bayramlar; tekrar çağrılınca kopya üretmez. */
  seedHolidays: (year: number): Promise<HolidaySeedResult> =>
    api.post<HolidaySeedResult>("/holidays/seed/", { year }),

  // --- Öğrenciler ---

  listStudents: async (params: StudentListParams = {}): Promise<Paginated<Student>> => {
    const parts: string[] = [];
    if (params.search?.trim()) parts.push(`search=${encodeURIComponent(params.search.trim())}`);
    if (params.classLevel !== undefined && params.classLevel !== null) {
      parts.push(`class_level=${params.classLevel}`);
    }
    if (params.classSection?.trim()) {
      parts.push(`class_section=${encodeURIComponent(params.classSection.trim())}`);
    }
    if (params.onlyActive) parts.push("only_active=true");
    if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
    if (params.offset) parts.push(`offset=${params.offset}`);
    const data = await api.get<Paginated<Student> | Student[]>(withQuery("/students/", parts));
    return asPage(data);
  },

  getStudent: (id: number): Promise<Student> => api.get<Student>(`/students/${id}/`),

  createStudent: (body: StudentWriteBody): Promise<Student> =>
    api.post<Student>("/students/", body),

  updateStudent: (id: number, body: Partial<StudentWriteBody>): Promise<Student> =>
    api.patch<Student>(`/students/${id}/`, body),

  /** Hiç üye olmamış ve açık işlemi olmayan öğrencinin kaydını siler (yoksa 400). */
  deleteStudent: (id: number): Promise<void> => api.del<void>(`/students/${id}/`),

  /** "Ayrıldı olarak işaretle" — ayrılış yolu; kayıt silinebilir (bkz. `deleted`). */
  leaveStudent: (id: number): Promise<StudentLeaveResult> =>
    api.post<StudentLeaveResult>(`/students/${id}/leave/`),

  // --- Personel ---

  listPersonnel: async (params: PersonnelListParams = {}): Promise<Paginated<Personnel>> => {
    const parts: string[] = [];
    if (params.search?.trim()) parts.push(`search=${encodeURIComponent(params.search.trim())}`);
    if (params.onlyActive) parts.push("only_active=true");
    if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
    if (params.offset) parts.push(`offset=${params.offset}`);
    const data = await api.get<Paginated<Personnel> | Personnel[]>(withQuery("/personnel/", parts));
    return asPage(data);
  },

  getPersonnel: (id: number): Promise<Personnel> => api.get<Personnel>(`/personnel/${id}/`),

  createPersonnel: (body: PersonnelWriteBody): Promise<Personnel> =>
    api.post<Personnel>("/personnel/", body),

  updatePersonnel: (id: number, body: Partial<PersonnelWriteBody>): Promise<Personnel> =>
    api.patch<Personnel>(`/personnel/${id}/`, body),

  deletePersonnel: (id: number): Promise<void> => api.del<void>(`/personnel/${id}/`),

  leavePersonnel: (id: number): Promise<PersonnelLeaveResult> =>
    api.post<PersonnelLeaveResult>(`/personnel/${id}/leave/`),

  /** "Olası aynı kişi": `sourceId` (eski kayıt) `intoId` (yeni kayıt) kaydına birleşir. */
  mergePersonnel: (sourceId: number, intoId: number): Promise<Personnel> =>
    api.post<Personnel>(`/personnel/${sourceId}/merge/`, { into_id: intoId }),

  // --- Şube kataloğu ---

  listClassSections: async (schoolYear?: number): Promise<ClassSection[]> => {
    const path =
      schoolYear === undefined
        ? "/class-sections/?limit=500"
        : `/class-sections/?school_year=${schoolYear}&limit=500`;
    const data = await api.get<Paginated<ClassSection> | ClassSection[]>(path);
    return unwrap(data);
  },

  createClassSection: (body: ClassSectionWriteBody): Promise<ClassSection> =>
    api.post<ClassSection>("/class-sections/", body),

  deleteClassSection: (id: number): Promise<void> => api.del<void>(`/class-sections/${id}/`),

  // --- İçe aktarma (önizleme hiçbir şey yazmaz; commit gerçek yazar) ---

  previewStudentImport: (
    input: ImportInput,
    options: StudentImportOptions = {},
  ): Promise<StudentImportReport> =>
    importRequest<StudentImportReport>("/imports/students/preview/", input, studentExtra(options)),

  commitStudentImport: (
    input: ImportInput,
    options: StudentImportOptions = {},
  ): Promise<StudentImportReport> =>
    importRequest<StudentImportReport>("/imports/students/commit/", input, studentExtra(options)),

  previewPersonnelImport: (
    input: ImportInput,
    options: PersonnelImportOptions = {},
  ): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>(
      "/imports/personnel/preview/",
      input,
      personnelExtra(options),
    ),

  commitPersonnelImport: (
    input: ImportInput,
    options: PersonnelImportOptions = {},
  ): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>(
      "/imports/personnel/commit/",
      input,
      personnelExtra(options),
    ),

  // --- Şablon indirme (xlsx blob) ---

  studentTemplate: (): Promise<Blob> => api.getBlob("/templates/students/"),

  personnelTemplate: (): Promise<Blob> => api.getBlob("/templates/personnel/"),
};
