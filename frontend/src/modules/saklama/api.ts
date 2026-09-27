// Saklama ve anonimleştirme (F11 — tasarım §6.4) istemcisi.
//
// Uçların HEPSİ YÖNETİCİ KİPİNDEDİR (görevli kipi izin listesinde yok; `views_saklama`).
// Durum ve pano yanıtları KİŞİSİZDİR (yalnız sayılar); silinecek kişilerin adları yalnız
// `kisiler()` ucundan ve yalnız kullanıcı istediğinde gelir. Tetik GERİ DÖNÜŞSÜZDÜR:
// gövdede yönetici parolası ve onaylanan önizlemenin parmak izi (`digest`) gider; liste
// arada değiştiyse 409 `saklama_listesi_degisti` döner ve hiçbir şey yazılmaz.

import { api } from "../../lib/api";
import { formatNumber } from "../../lib/format";

/** Ekranın adresi (Ayarlar → Saklama sekmesi) ve başlığı (sözlük §4.3, §4.18). */
export const SAKLAMA_ADRESI = "/ayarlar?tab=saklama";
export const SAKLAMA_BASLIGI = "Saklama";

/**
 * Anonimleştirilmiş kayıttan yeniden basılan belgenin ibaresi — backend
 * `belge_izi.ANONIM_KOPYA_IBARESI` ve tasarım §6.2 ile BİREBİR (`test_on_yuz_sabitleri.py`).
 */
export const ANONIM_KOPYA_IBARESI =
  "Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir";

/**
 * Tetik öncesi yedeğin ve günlük yedeklerin saklandığı gün (desktop/backup.py); işlem geri
 * yüklemeden kalan önceki veritabanı dosyalarından bundan eski olanları siler (27.09.2026
 * kullanıcı kararı — `saklama.onceki_veritabani_siniri`).
 */
export const YEDEK_GUN = 14;
/** 409 — onaylanan liste tetik anında değişmiş. */
export const LISTE_DEGISTI_KODU = "saklama_listesi_degisti";

// ---------------------------------------------------------------------------
// Tipler — `services.saklama`
// ---------------------------------------------------------------------------

/** Kural başına kişisiz aday sayıları (`SaklamaPlani.ozet`). */
export interface SaklamaAdaylari {
  students: number;
  personnel: number;
  memberships: number;
  loans_terminated: number;
  loans_returned: number;
  cases_terminated: number;
  cases_closed: number;
  deliveries: number;
  total: number;
  /** Ayrılış süresi dolduğu hâlde açık işi ya da süresi dolmamış bağı olan kişi. */
  persons_held: number;
}

export interface SaklamaSureleri {
  left_person_years: number;
  after_termination_years: number;
  returned_loans_years: number;
  closed_cases_years: number;
  closed_deliveries_years: number;
}

export interface SonTetik {
  ran_at: string;
  backup_name: string;
  summary: SaklamaAdaylari;
  pre_migrate_removed: number;
  /** Silinen önceki veritabanı sayısı (eşleri ayrı sayılmaz). */
  old_db_removed: number;
}

export interface YedekKalintisi {
  pre_migrate: number;
  pre_anonim: number;
  /** Geri yüklemeden kalan önceki veritabanı dosyaları. */
  old_databases: number;
  /** Bunlardan işlem şimdi uygulansa silinecekler ({@link YEDEK_GUN} günden eskiler). */
  old_databases_expired: number;
}

export interface SaklamaDurumu {
  today: string;
  policy: SaklamaSureleri;
  candidates: SaklamaAdaylari;
  /** Önizlemenin parmak izi; liste boşsa "". */
  digest: string;
  pending_since: string | null;
  approval_deadline: string | null;
  overdue: boolean;
  max_wait_months: number;
  last_scan_on: string | null;
  last_run: SonTetik | null;
  price_reminders: number;
  residue: YedekKalintisi;
}

/**
 * "person": kişinin kaydı (üyelikleriyle birlikte) silinecek · "membership": yalnız sona ermiş
 * üyelik kaydı silinecek, kişi kaydı kalır (backend `saklama.KAPSAM_*`).
 */
export type SilmeKapsami = "person" | "membership";

/** Kaydı ya da sona ermiş üyeliği silinecek kişi — AD İÇERİR (yalnız yönetici kipinde, istenince). */
export interface SilinecekKisi {
  kind: "student" | "personnel";
  person_id: number;
  full_name: string;
  person_label: string;
  left_at: string | null;
  scope: SilmeKapsami;
  /** Yalnız "membership" kapsamında: üyeliğin sonlandığı gün. */
  terminated_at: string | null;
}

/** Bedel adımında bir yıldan uzun bekleyen dosya (kişisiz). */
export interface BedelHatirlatmasi {
  case_id: number;
  barcode: string;
  title: string;
  case_type: string;
  resolution: string;
  step_date: string;
  years_waiting: number;
}

export interface SaklamaPanoOzeti {
  candidates: number;
  pending_since: string | null;
  approval_deadline: string | null;
  overdue: boolean;
  price_reminders: number;
}

export interface TetikSonucu {
  ran_at: string;
  backup_name: string;
  summary: SaklamaAdaylari;
  pre_migrate_removed: number;
  old_db_removed: number;
  wal_truncated: boolean;
}

export const saklamaApi = {
  durum: (): Promise<SaklamaDurumu> => api.get<SaklamaDurumu>("/library/retention/"),
  kisiler: (): Promise<SilinecekKisi[]> => api.get<SilinecekKisi[]>("/library/retention/persons/"),
  bedelListesi: (): Promise<BedelHatirlatmasi[]> =>
    api.get<BedelHatirlatmasi[]>("/library/retention/price-reminders/"),
  uygula: (password: string, digest: string): Promise<TetikSonucu> =>
    api.post<TetikSonucu>("/library/retention/apply/", { password, digest }),
  /** Genel Bakış kartı — kullanıcı eylemi değildir. */
  pano: (): Promise<SaklamaPanoOzeti> =>
    api.get<SaklamaPanoOzeti>("/library/dashboard/retention/", { etkinlik: false }),
};

// ---------------------------------------------------------------------------
// Metin yardımcıları (sözlük §4.18)
// ---------------------------------------------------------------------------

function yaz(satirlar: [number, string][]): string[] {
  return satirlar.filter(([n]) => n > 0).map(([n, metin]) => `${formatNumber(n)} ${metin}`);
}

/**
 * "Ne silinecek" — kaydın KENDİSİ kalkar (kişi kaydı, sona ermiş üyelik kaydı). Sözlük §4.18:
 * silme ≠ anonimleştirme. Sıfır olan satır yazılmaz.
 */
export function silmeSatirlari(a: SaklamaAdaylari): string[] {
  return yaz([
    [a.students, "öğrenci kaydı silinecek"],
    [a.personnel, "öğretmen ya da diğer personel kaydı silinecek"],
    [a.memberships, "sona ermiş üyelik kaydı silinecek"],
  ]);
}

/**
 * "Kişiyle bağı koparılacak" (anonimleştirme) — kayıt KALIR, kişisiz sayım ve istatistik
 * için; yalnız kişiyle bağı ve açıklamaları temizlenir. Sıfır olan satır yazılmaz.
 */
export function anonimlestirmeSatirlari(a: SaklamaAdaylari): string[] {
  return yaz([
    [a.loans_terminated, "ödüncün kişiyle bağı koparılacak (sona ermiş üyelik)"],
    [a.loans_returned, "iade edilmiş ödüncün kişiyle bağı koparılacak"],
    [a.cases_terminated, "kayıp/hasar dosyasının kişiyle bağı koparılacak (sona ermiş üyelik)"],
    [a.cases_closed, "kapanmış kayıp/hasar dosyasının kişiyle bağı koparılacak"],
    [a.deliveries, "öğretmene teslimin öğretmenle bağı koparılacak"],
  ]);
}

/** Aday sayılarının bütün satırları (önce silme, sonra anonimleştirme). */
export function adaySatirlari(a: SaklamaAdaylari): string[] {
  return [...silmeSatirlari(a), ...anonimlestirmeSatirlari(a)];
}

/** Onay bekleme süresinin söylenişi: "6 ay". */
export function beklemeSuresi(ay: number): string {
  return `${formatNumber(ay)} ay`;
}
