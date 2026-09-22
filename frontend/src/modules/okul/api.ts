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

/**
 * Sihirbaz adımları, sırasıyla — backend `services/setup.py::SETUP_STEPS` ile BİREBİR:
 * yönetici parolası + kurtarma anahtarı → okul bilgileri → ders yılı ve kapalı günler.
 */
export type SetupStep = "password" | "school" | "calendar";

export const SETUP_STEPS: readonly SetupStep[] = ["password", "school", "calendar"];

/** Aktif ders yılının özeti (`setup/status/` içinde; kişisel veri yok). */
export interface ActiveSchoolYearSummary {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  /** İki dönemin tarihleri tanımlı mı? (kurulumu tamamlamanın koşulu) */
  terms_ready: boolean;
}

/** Başlangıç Yol Haritası'nda kullanıcının işaretlediği maddeler (backend tek kaynak). */
export type RoadmapManualItem =
  "katalog_sablonu" | "kurtarma_zarfi" | "parola_paylasimi" | "btr_gorusmesi";

export interface RoadmapState {
  /** İşaretlenen madde → işaretlendiği gün (ISO). */
  marks: Partial<Record<RoadmapManualItem, string>>;
  /** Bütün maddeler tamamlanınca kullanıcı kartı gizleyebilir. */
  hidden: boolean;
}

/**
 * `GET /setup/status/` — sihirbaz kapısı, adım durumları, sicil sayaçları ve yol
 * haritası. Masaüstü sağlık denetiminin de ucudur: hafiftir ve KİŞİSEL VERİ İÇERMEZ.
 */
export interface SetupStatus {
  setup_completed: boolean;
  /** Yönetici parolası kurulu mu? Kurulu değilse sihirbaz ilk adımdan açılır. */
  password_set: boolean;
  /**
   * Kurtarma anahtarının saklandığı doğrulandı mı? 1. adım ancak parola kurulu VE anahtar
   * doğrulanmışsa tamamdır; kurulumu önceden tamamlanmış programda yanlışsa yol haritası ve
   * Güvenlik ekranı uyarır.
   */
  recovery_key_confirmed: boolean;
  school_name: string;
  /** Okul adı, kademe, kısa ad ve demirbaş onayı tamam mı? */
  school_info_complete: boolean;
  has_active_school_year: boolean;
  active_school_year: ActiveSchoolYearSummary | null;
  /** Eksik adımlar, sırasıyla (hepsi tamamsa boş) — backend kapısıyla aynı hesap. */
  missing_steps: SetupStep[];
  student_count: number;
  personnel_count: number;
  class_section_count: number;
  /** Aktif ders yılıyla kesişen "öğrenciye kapalı gün" kaydı sayısı. */
  school_break_count: number;
  roadmap: RoadmapState;
}

/** Okulun kademesi — backend `SchoolLevel` ile birebir; boş = henüz seçilmedi. */
export type SchoolLevel = "ILKOKUL" | "ORTAOKUL" | "ORTAOGRETIM";

export const SCHOOL_LEVEL_TR: Record<SchoolLevel, string> = {
  ILKOKUL: "İlkokul",
  ORTAOKUL: "Ortaokul",
  ORTAOGRETIM: "Ortaöğretim (lise)",
};

/** Kısa okul adının üst sınırı (etiket ve kartlarda basılır). */
export const KISA_AD_EN_COK = 24;

/** Kurum künyesi — evrak antedi buradan çözülür (`setup_completed` salt-okunur). */
export interface SchoolConfig {
  school_name: string;
  province: string;
  district: string;
  principal_name: string;
  /** Açıksa sınıf düzeylerine Hazırlık (0) eklenir. */
  has_prep_class: boolean;
  kademe: SchoolLevel | "";
  /** Etiket ve kartlarda basılan kısa okul adı (en çok 24 karakter). */
  kisa_ad: string;
  /** "Bu bilgisayar okul demirbaşıdır" onayı (kurulumda zorunlu). */
  demirbas_onayi: boolean;
  /** Bilgisayarın demirbaş no'su (isteğe bağlı). */
  demirbas_no: string;
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
 * `status`, `left_at` ve `leave_candidate_since` salt okunurdur: ayrılış `leaveStudent`
 * ya da Ayrılış Havuzu kararıyla yapılır; kayıt silinmez.
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
  /** Ayrılış havuzuna giriş tarihi (ISO); doluysa ayrılış kararı bekliyor. */
  leave_candidate_since: string | null;
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
 * `is_active`, `left_at` ve `leave_candidate_since` salt okunurdur: ayrılış
 * `leavePersonnel` ya da Ayrılış Havuzu kararıyla yapılır; kayıt silinmez.
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
  /** Ayrılış havuzuna giriş tarihi (ISO); doluysa ayrılış kararı bekliyor. */
  leave_candidate_since: string | null;
}

export interface PersonnelWriteBody {
  first_name: string;
  last_name: string;
  member_kind?: MemberKind;
}

// ---------------------------------------------------------------------------
// Ayrılış Havuzu — e-Okul aktarımı kimseyi ayırmaz ve silmez; listede bulunmayan
// aktif kişi burada karar bekler (backend `views_pool.py`).
// ---------------------------------------------------------------------------

/** Kişiyi havuza ekleyen aktarım: dosya adı (yapıştırılan listede boş) ve gün (ISO). */
export interface LeavePoolRun {
  id: number;
  file_name: string;
  date: string;
}

/** Havuzdaki öğrenci — LeavePoolStudentSerializer ile birebir. */
export interface LeavePoolStudent {
  id: number;
  full_name: string;
  student_number: string;
  class_label: string;
  /** Havuza giriş tarihi (ISO). */
  leave_candidate_since: string;
  run: LeavePoolRun | null;
}

/**
 * Eşleşme gerekçesi — backend `name_match.MatchReason` ile birebir (TB18).
 * "Adı aynı" adaşı da yakalar; kullanıcı bunu ancak gerekçeyi görürse anlar.
 */
export type SimilarReason = "ayni_ad_soyad" | "ad_ayni_soyad_farkli" | "yazim_farki";

/** Aday satırında ve onay diyaloğunda yazılan gerekçe (eksik kod derlemede yakalanır). */
export const SIMILAR_REASON_TR: Record<SimilarReason, string> = {
  ayni_ad_soyad: "ad ve soyadı birebir aynı",
  ad_ayni_soyad_farkli: "adı aynı, soyadı farklı",
  yazim_farki: "ad-soyadında küçük yazım farkı",
};

/** Bilinmeyen kod (eski yanıt) ekranı boş bırakmasın: kısa ve dürüst karşılık. */
export function benzerlikGerekcesi(reason: string): string {
  return SIMILAR_REASON_TR[reason as SimilarReason] ?? "ad benzerliği";
}

/** Havuzdaki kişiyle "olası aynı kişi" olan, sonradan açılmış kayıt. */
export interface LeavePoolSimilar {
  id: number;
  full_name: string;
  member_kind: MemberKind;
  /** Adayın sicile eklendiği gün (ISO) — onay diyaloğunda ayırt edici bilgi. */
  created_on: string;
  reason: SimilarReason;
}

/** Havuzdaki öğretmen / diğer personel — LeavePoolPersonnelSerializer ile birebir. */
export interface LeavePoolPersonnel {
  id: number;
  full_name: string;
  member_kind: MemberKind;
  leave_candidate_since: string;
  run: LeavePoolRun | null;
  /** Birleştirme adayları: havuzdaki kişi kaynak, aday hedef (`mergePersonnel`). */
  similar: LeavePoolSimilar[];
}

/** `GET /leave-pool/?summary=true` — yalnız sayılar (Genel Bakış kartı). */
export interface LeavePoolSummary {
  student_count: number;
  personnel_count: number;
}

/** `GET /leave-pool/` — ayrı listeler, TR sıralı. */
export interface LeavePool extends LeavePoolSummary {
  students: LeavePoolStudent[];
  personnel: LeavePoolPersonnel[];
}

/** Bir kişi türü için karar: ayrıldı olarak işaretle / aktif kalsın (kimlikler). */
export interface LeavePoolDecision {
  leave?: number[];
  keep?: number[];
}

export interface LeavePoolResolveBody {
  students?: LeavePoolDecision;
  personnel?: LeavePoolDecision;
}

/** Karar sonucu: uygulanan sayılar + havuzda kalan sayılar. */
export interface LeavePoolResolveResult extends LeavePoolSummary {
  students_left: number;
  students_kept: number;
  personnel_left: number;
  personnel_kept: number;
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
  /** Dosyada olmadığı için ayrılış havuzuna YENİ eklenen öğrenci sayısı. */
  to_pool: number;
}

/** Havuza eklenecek öğrenci — ad yalnız bu yanıtta gelir, kalıcı rapora yazılmaz. */
export interface PoolStudent {
  id: number;
  full_name: string;
  student_number: string;
  class_label: string;
}

/**
 * Aktarım kimseyi ayırmaz: dosyada olmayan aktif öğrenci ayrılış havuzuna girer
 * (`pool_added_students`, zaten havuzda olan sayılmaz), dosyada bulunan havuzdaki
 * öğrenci çıkar (`pool_removed_students`).
 */
export interface StudentImportReport extends ImportReportBase {
  created_students: number;
  updated_students: number;
  unchanged_students: number;
  /** Güncellenenlerin içinde: ayrılmışken aynı numarayla dönenler. */
  reactivated_students: number;
  pool_added_students: number;
  pool_removed_students: number;
  /** "Bu dosya okulun tam listesidir" onayıyla mı çalıştı? */
  full_list: boolean;
  classes: ClassImpact[];
  pool_added: PoolStudent[];
}

/** Havuza eklenecek (listede olmayan) aktif kişi — ad yalnız bu yanıtta gelir. */
export interface PoolPersonnel {
  id: number;
  full_name: string;
}

/**
 * "Olası aynı kişi": ada göre eşleşmeyen yeni satır ↔ listede olmayan kayıt.
 * `new_id` yalnız aktarımdan sonra dolar (önizlemede null); birleştirme
 * `mergePersonnel(existing_id, new_id)` ile yapılır (ya da Ayrılış Havuzu'ndan).
 */
export interface SimilarPair {
  row_number: number;
  row_name: string;
  existing_id: number;
  existing_name: string;
  new_id: number | null;
  /** Çiftin neden kurulduğu (TB18); eski raporlarda boş olabilir. */
  reason: SimilarReason | "";
}

/** Aktarım kimseyi ayırmaz: listede olmayan aktif personel ayrılış havuzuna girer. */
export interface PersonnelImportReport extends ImportReportBase {
  created_personnel: number;
  updated_personnel: number;
  unchanged_personnel: number;
  reactivated_personnel: number;
  pool_added_personnel: number;
  pool_removed_personnel: number;
  similar_pair_count: number;
  pool_added: PoolPersonnel[];
  similar_pairs: SimilarPair[];
}

export type ImportReport = StudentImportReport | PersonnelImportReport;

/** İçe aktarma girdisi — dosya yolu (multipart) veya pano metni (JSON). */
export type ImportInput = { file: File } | { text: string };

/** Öğrenci mutabakatı seçeneği: dosya okulun tam listesi mi? (varsayılan hayır) */
export interface StudentImportOptions {
  fullList?: boolean;
}

/**
 * Öğrenci/personel raporlarının farklı adlandırılmış sayaçlarını (created_students
 * ↔ created_personnel) tek şekle indirger — rapor bileşeni türden bağımsız kalır.
 */
export function importCounts(report: ImportReport): {
  created: number;
  updated: number;
  unchanged: number;
  poolAdded: number;
  poolRemoved: number;
} {
  if ("created_students" in report) {
    return {
      created: report.created_students,
      updated: report.updated_students,
      unchanged: report.unchanged_students,
      poolAdded: report.pool_added_students,
      poolRemoved: report.pool_removed_students,
    };
  }
  return {
    created: report.created_personnel,
    updated: report.updated_personnel,
    unchanged: report.unchanged_personnel,
    poolAdded: report.pool_added_personnel,
    poolRemoved: report.pool_removed_personnel,
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

type ImportExtra = Record<string, boolean>;

/**
 * Dosya yolu multipart (`file`), metin yolu JSON (`text`) — backend tam olarak birini
 * bekler. Mutabakat seçeneği (`full_list`) iki yolda da gider. Personelde seçenek
 * yoktur: listede olmayanlar Ayrılış Havuzu'na girer, karar orada verilir.
 */
function importRequest<R>(path: string, input: ImportInput, extra: ImportExtra = {}): Promise<R> {
  if ("file" in input) {
    const form = new FormData();
    form.append("file", input.file);
    for (const [key, value] of Object.entries(extra)) form.append(key, String(value));
    return api.postForm<R>(path, form);
  }
  return api.post<R>(path, { text: input.text, ...extra });
}

/** Yalnız anlamlı seçenekler gönderilir (varsayılanlar backend'dedir). */
function studentExtra(options: StudentImportOptions): ImportExtra {
  return options.fullList ? { full_list: true } : {};
}

export const okulApi = {
  // --- Kurulum sihirbazı ---

  getSetupStatus: (): Promise<SetupStatus> => api.get<SetupStatus>("/setup/status/"),

  getSchoolConfig: (): Promise<SchoolConfig> => api.get<SchoolConfig>("/setup/school-config/"),

  /** Kısmi gövde gönderilebilir — backend MERGE eder (verilmeyen alan korunur). */
  updateSchoolConfig: (body: SchoolConfigBody): Promise<SchoolConfig> =>
    api.put<SchoolConfig>("/setup/school-config/", body),

  /** Eksik adımda 400 `kurulum_eksik` — ileti hangi adımın eksik olduğunu söyler. */
  completeSetup: (): Promise<{ setup_completed: boolean }> =>
    api.post<{ setup_completed: boolean }>("/setup/complete/"),

  /** Yol haritasında elle işaretlenen bir maddeyi işaretler ya da işareti kaldırır. */
  markRoadmapItem: (item: RoadmapManualItem, done: boolean): Promise<RoadmapState> =>
    api.post<RoadmapState>("/setup/roadmap/", { item, done }),

  /** Kartı gizler (yalnız bütün maddeler tamamken) ya da yeniden gösterir. */
  setRoadmapHidden: (hidden: boolean): Promise<RoadmapState> =>
    api.post<RoadmapState>("/setup/roadmap/", { hidden }),

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

  /** "Ayrıldı olarak işaretle" — ayrılış yolu; kayıt SİLİNMEZ, ayrılmış kayıt döner. */
  leaveStudent: (id: number): Promise<Student> => api.post<Student>(`/students/${id}/leave/`),

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

  /** "Ayrıldı olarak işaretle" — kayıt SİLİNMEZ, ayrılmış kayıt döner. */
  leavePersonnel: (id: number): Promise<Personnel> =>
    api.post<Personnel>(`/personnel/${id}/leave/`),

  /** "Olası aynı kişi": `sourceId` (eski kayıt) `intoId` (yeni kayıt) kaydına birleşir. */
  mergePersonnel: (sourceId: number, intoId: number): Promise<Personnel> =>
    api.post<Personnel>(`/personnel/${sourceId}/merge/`, { into_id: intoId }),

  // --- Ayrılış Havuzu ---

  /** Ayrılış kararı bekleyen öğrenci ve personel (ayrı listeler, TR sıralı). */
  getLeavePool: (): Promise<LeavePool> => api.get<LeavePool>("/leave-pool/"),

  /** Yalnız sayılar — Genel Bakış kartı (kişisel veri gelmez). */
  getLeavePoolSummary: (): Promise<LeavePoolSummary> =>
    api.get<LeavePoolSummary>("/leave-pool/?summary=true"),

  /**
   * Toplu karar (tek işlem): `leave` → ayrıldı olarak işaretle (kayıt kalır),
   * `keep` → aktif kalsın (havuzdan çıkar). Seçilenlerden biri artık havuzda
   * değilse hiçbir karar uygulanmaz (400).
   */
  resolveLeavePool: (body: LeavePoolResolveBody): Promise<LeavePoolResolveResult> =>
    api.post<LeavePoolResolveResult>("/leave-pool/resolve/", body),

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

  previewPersonnelImport: (input: ImportInput): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>("/imports/personnel/preview/", input),

  commitPersonnelImport: (input: ImportInput): Promise<PersonnelImportReport> =>
    importRequest<PersonnelImportReport>("/imports/personnel/commit/", input),

  // --- Şablon indirme (xlsx blob) ---

  studentTemplate: (): Promise<Blob> => api.getBlob("/templates/students/"),

  personnelTemplate: (): Promise<Blob> => api.getBlob("/templates/personnel/"),
};
