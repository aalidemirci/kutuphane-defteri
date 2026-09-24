// `kutuphane` modülü API istemcisi — backend `apps/kutuphane/{urls,serializers}.py`
// ile BİREBİR. URL öneki (`library/…`) OYS'den korunur.
//
// Kapsam (F2): katalog Excel şablonu (F1'den), kütüphane politikası, bölümler,
// eserler, nüshalar, komisyon kararları, edinimler ve bağış ön kayıtları.
// F3: toplu katalog aktarımı (önizleme/uygulama/geçmiş), yapay zekâ köprüsünün
// komut metni ve ISBN ile künye getirme. Etiket uçları (F4) `etiketApi.ts`'tedir;
// üyelik ve dolaşım (F6) uçları kendi fazlarında eklenir.
//
// İki sözleşme notu:
//   * Liste uçları SAYFALIDIR (tasarım D9): `{count, next, previous, results}`
//     ve `?limit=&offset=`. Üst sınır sunucuda 200'dür.
//   * `library/copies/bulk/` yanıtı `{count, results}` biçimindedir — sayfalama
//     değil, işlem sonucudur (`CopyBulkResult`).
//
// Kişisel veri: bağışçı (`source_note`, `donor_name`) ve komisyon adları
// (`chair_name`, `participants_text`) sunucuda ŞİFRELİ alanlardır; yönetici
// parolası kurulmadan yazan istek 409 `parola_gerekli` döner (ui/ErrorBand).

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";

export type { Paginated };

/** Belgenin adı — kart başlığı ve indirilen dosyanın adı (backend `TEMPLATE_DOCUMENT_NAME`). */
export const KATALOG_SABLONU_BELGE_ADI = "Katalog Excel Şablonu";

/** Katalog listelerinin sayfa boyutu (backend `KatalogSayfalama.default_limit`). */
export const KATALOG_SAYFA_BOYUTU = 25;

/**
 * İndirilen şablonun adı: belge adı + YEREL tarih (docs/sozluk.md §3).
 * `Katalog-Excel-Şablonu_21.09.2026.xlsx` — backend `excel_template.template_filename`
 * ile aynı biçim. Tarih `todayIso()`'dan gelir; `toISOString()` UTC verir ve gece
 * yarısına yakın indirmede bir önceki günü yazardı.
 */
export function katalogSablonuDosyaAdi(): string {
  return dosyaAdi([KATALOG_SABLONU_BELGE_ADI, formatDate(todayIso())], "xlsx");
}

// ---------------------------------------------------------------------------
// Kod listeleri (backend TextChoices ile birebir) ve Türkçe adları
// ---------------------------------------------------------------------------

/** Kaynak türü — `ResourceType`. */
export type ResourceType = "BOOK" | "PERIODICAL" | "AV_MATERIAL" | "EBOOK" | "EDATABASE";

export const RESOURCE_TYPE_TR: Record<ResourceType, string> = {
  BOOK: "Kitap",
  PERIODICAL: "Süreli yayın",
  AV_MATERIAL: "Görsel-işitsel materyal",
  EBOOK: "E-kitap",
  EDATABASE: "E-veri tabanı",
};

/** Dijital kaynaklarda nüsha AÇILAMAZ (backend `DIGITAL_RESOURCE_TYPES`). */
export const DIJITAL_TURLER: readonly ResourceType[] = ["EBOOK", "EDATABASE"];

/** Sınıflama kodunun kaynağı — `ClassificationSource`. */
export type ClassificationSource = "CATALOG" | "ESTIMATED" | "MANUAL";

export const CLASSIFICATION_SOURCE_TR: Record<ClassificationSource, string> = {
  CATALOG: "Katalogdan bulundu",
  ESTIMATED: "Tahmini",
  MANUAL: "Elle girildi",
};

/** Nüsha durumu — `CopyStatus`. Adlar docs/sozluk.md §1'deki adlardır. */
export type CopyStatus =
  | "AVAILABLE"
  | "ON_LOAN"
  | "DELIVERED"
  | "IN_REPAIR"
  | "LOST"
  | "WITHDRAWN_WEEDED"
  | "WITHDRAWN_MISSING"
  | "WITHDRAWN_LOST"
  | "TRANSFERRED";

export const COPY_STATUS_TR: Record<CopyStatus, string> = {
  AVAILABLE: "Rafta",
  ON_LOAN: "Ödünçte",
  DELIVERED: "Sınıf kitaplığında",
  IN_REPAIR: "Onarımda",
  LOST: "Kayıp",
  WITHDRAWN_WEEDED: "Ayıklandı (kayıttan düşüldü)",
  WITHDRAWN_MISSING: "Sayım noksanı (kayıttan düşüldü)",
  WITHDRAWN_LOST: "Kayıp (kayıttan düşüldü)",
  TRANSFERRED: "Devredildi",
};

/** Edinim yolu — `AcquisitionMethod` (Md. 10/5 + iki kayıt-içi giriş). */
export type AcquisitionMethod =
  "MINISTRY" | "PURCHASE" | "DONATION" | "EXCHANGE" | "INVENTORY_FOUND" | "EXISTING_STOCK";

export const ACQUISITION_METHOD_TR: Record<AcquisitionMethod, string> = {
  MINISTRY: "Bakanlık gönderimi",
  PURCHASE: "Satın alma",
  DONATION: "Bağış",
  EXCHANGE: "Değişim",
  INVENTORY_FOUND: "Sayım fazlası (kayda giriş)",
  EXISTING_STOCK: "Mevcut koleksiyon (programa aktarım)",
};

/** Komisyon kararı türü — `CommissionDecisionType`. */
export type CommissionDecisionType = "SELECTION" | "DONATION_REVIEW" | "WEEDING";

export const COMMISSION_DECISION_TYPE_TR: Record<CommissionDecisionType, string> = {
  SELECTION: "Kaynak seçimi",
  DONATION_REVIEW: "Bağış değerlendirme",
  WEEDING: "Ayıklama",
};

/** Bağış ön kaydının durumu — `DonationIntakeStatus`. */
export type DonationIntakeStatus = "PENDING" | "DECIDED" | "CANCELLED";

export const DONATION_STATUS_TR: Record<DonationIntakeStatus, string> = {
  PENDING: "Karar bekliyor",
  DECIDED: "Karar işlendi",
  CANCELLED: "İptal edildi",
};

/** Bağış kaleminin kararı — `DonationItemDecision`. */
export type DonationItemDecision = "PENDING" | "ACCEPTED" | "REJECTED";

export const DONATION_ITEM_DECISION_TR: Record<DonationItemDecision, string> = {
  PENDING: "Karar bekliyor",
  ACCEPTED: "Kabul edildi",
  REJECTED: "Reddedildi",
};

/**
 * Eser listesinin sıralama ekseni (backend `selectors.WORK_ORDERINGS`).
 * Üç katalog ekseni Md. 11/1'dendir (kaynak adı / yazar adı / konu); "newest"
 * son eklenenleri öne alır. Sıralama TÜRKÇE anahtar alanlarıyla sunucudadır.
 */
export type WorkOrder = "title" | "author" | "subject" | "newest";

export const WORK_ORDER_TR: Record<WorkOrder, string> = {
  title: "Kaynak adına göre",
  author: "Yazar adına göre",
  subject: "Konuya göre",
  newest: "En yeni eklenen",
};

// ---------------------------------------------------------------------------
// Kayıt tipleri (serializer alanlarıyla birebir)
// ---------------------------------------------------------------------------

/** Kütüphane politikası — `loan_period_days` SALT OKUNURDUR (Md. 18, on beş gün). */
export interface LibraryPolicy {
  loan_period_days: number;
  max_loans_student: number;
  max_loans_teacher: number;
  max_loans_staff: number;
  staff_loans_enabled: boolean;
  staff_loans_decision_date: string | null;
  staff_loans_decision_no: string;
  block_loan_if_overdue: boolean;
  shift_due_date_on_school_break: boolean;
  last_loan_date: string | null;
  last_loan_date_graduating: string | null;
  idle_minutes: number;
  admin_max_minutes: number;
  popular_min_members: number;
  retention_years_after_termination: number;
  retention_years_returned_loans: number;
  retention_years_closed_cases: number;
  retention_years_closed_deliveries: number;
  /** ISBN ile künye getirme (U13, §8.5) — VARSAYILAN KAPALI dış kapı. */
  metadata_lookup_enabled: boolean;
  metadata_lookup_ministry: boolean;
  metadata_lookup_openlibrary: boolean;
  updated_at: string;
}

/** `PUT library/policy/` KISMİDİR: gönderilmeyen alana dokunulmaz. */
export type LibraryPolicyBody = Partial<Omit<LibraryPolicy, "loan_period_days" | "updated_at">>;

// ---------------------------------------------------------------------------
// ISBN ile künye getirme (U13, tasarım §8.5) — ÖNERİ üretir, hiçbir alanı yazmaz
// ---------------------------------------------------------------------------

/** Künye kaynağı — backend `MetadataLookupSource`. Boş dize: bulunamadı. */
export type KunyeKaynagi = "MINISTRY" | "OPENLIBRARY" | "";

/**
 * Önerinin bir alanı. `mevcut_deger` esere ait olandır: dolu alan sessizce
 * ÜZERİNE YAZILMAZ (§8.5-5), ekran farkı gösterir ve kullanıcı karar verir.
 * Alan listesinde **çevirmen YOKTUR** ve olmayacaktır (kaynaklar çevirmeni
 * yazardan ayırmıyor); çevirmeni kullanıcı elle yazar.
 */
export interface KunyeAlani {
  alan: string;
  etiket: string;
  deger: string | number | null;
  mevcut_deger: string | number | null;
  dolu: boolean;
  farkli: boolean;
}

/** `POST library/metadata/lookup/` yanıtı. */
export interface KunyeSonucu {
  isbn13: string;
  bulundu: boolean;
  kaynak: KunyeKaynagi;
  kaynak_adi: string;
  kaynak_tarihi: string | null;
  /** Hazır etiket: "Bakanlık kataloğu, 23.09.2026" (tarih sunucuda biçimlenir). */
  kaynak_etiketi: string;
  kayit_sayisi: number;
  onbellekten: boolean;
  /** "Dış kaynaktan alındı, doğrulayın" (docs/sozluk.md); bulunamadıysa boş. */
  rozet: string;
  /** Fail-open iletisi: "İnternetten getirilemedi, elle girebilirsiniz." */
  ileti: string;
  uyarilar: string[];
  ek_bilgi: { pages: number | null; place: string };
  alanlar: KunyeAlani[];
}

/** Çevrimdışı dosyanın satır durumu (eşleşme ISBN üzerindendir). */
export type CevrimdisiKunyeDurumu = "eslesti" | "eser_yok" | "coklu_eser" | "isbn_yok";

export const CEVRIMDISI_KUNYE_DURUMU_TR: Record<CevrimdisiKunyeDurumu, string> = {
  eslesti: "Eşleşti",
  eser_yok: "Katalogda eser yok",
  coklu_eser: "Bu ISBN'li birden çok eser var",
  isbn_yok: "Satırda ISBN yok",
};

export interface CevrimdisiKunyeSatiri {
  satir_no: number;
  isbn13: string;
  durum: CevrimdisiKunyeDurumu;
  work: number | null;
  work_title: string;
  uyarilar: string[];
  alanlar: KunyeAlani[];
}

/** `POST library/metadata/offline-preview/` yanıtı — YAZMA YOKTUR, ön izlemedir. */
export interface CevrimdisiKunyeOnizleme {
  kaynak_adi: string;
  kaynak_etiketi: string;
  rozet: string;
  sayilar: Record<CevrimdisiKunyeDurumu, number>;
  /** Yok sayılan sütunlar (ör. "Çevirmen" — §8.5-5). */
  atlanan_sutunlar: string[];
  satirlar: CevrimdisiKunyeSatiri[];
}

/** Çevrimdışı ISBN listesinin belge adı (backend `offline.DOCUMENT_NAME`). */
export const KUNYE_LISTESI_BELGE_ADI = "ISBN Künye Listesi";

/** İndirilen ISBN listesinin adı: belge adı + YEREL tarih (docs/sozluk.md §3). */
export function kunyeListesiDosyaAdi(): string {
  return dosyaAdi([KUNYE_LISTESI_BELGE_ADI, formatDate(todayIso())], "xlsx");
}

/** Bölüm — kontrollü liste (sözlük: "bölüm"). */
export interface Section {
  id: number;
  name: string;
  dewey_from: string;
  dewey_to: string;
  description: string;
  sort_order: number;
}

export type SectionBody = Omit<Section, "id">;

/** Eser künyesi. `isbn13`, `isbn_warning` ve sayaçlar sunucuda türetilir. */
export interface Work {
  id: number;
  title: string;
  authors: string;
  translator: string;
  edition: string;
  publisher: string;
  publish_year: number | null;
  isbn: string;
  isbn13: string;
  /** ISBN sağlama uyarısı; kaydı ENGELLEMEZ (boşsa uyarı yok). */
  isbn_warning: string;
  subjects: string;
  classification_code: string;
  classification_source: ClassificationSource;
  classification_source_display: string;
  call_number: string;
  resource_type: ResourceType;
  resource_type_display: string;
  language: string;
  section: number | null;
  section_name: string | null;
  /** E-kitap / e-veri tabanı: nüsha açılamaz. */
  is_digital: boolean;
  copy_count: number;
  available_copy_count: number;
  created_at: string;
}

export interface WorkBody {
  title: string;
  authors?: string;
  translator?: string;
  edition?: string;
  publisher?: string;
  publish_year?: number | null;
  isbn?: string;
  subjects?: string;
  classification_code?: string;
  classification_source?: ClassificationSource;
  call_number?: string;
  resource_type?: ResourceType;
  language?: string;
  section?: number | null;
}

/** Nüsha — dört ayrı tanımlayıcı taşır (sözlük §1: barkod / kayıt no / TKYS kodu / eski kayıt no). */
export interface Copy {
  id: number;
  work: number;
  work_title: string;
  work_authors: string;
  call_number: string;
  resource_type: ResourceType;
  acquisition: number;
  accession_no: number;
  /** Saklanan ve okutulan rakamlar (10 hane). */
  barcode: string;
  /** Basılı biçim: `2026-000123`. */
  barcode_display: string;
  external_asset_ref: string;
  old_register_no: string;
  section: number | null;
  section_name: string | null;
  is_reference: boolean;
  is_out_of_print: boolean;
  is_bound_periodical: boolean;
  is_rare_or_manuscript: boolean;
  status: CopyStatus;
  status_display: string;
  /** Ödünç verilebilirliğin tek türetimi (Md. 14/1-a, 16/1). */
  is_loanable: boolean;
  /** Verilemiyorsa gerekçe (kişisel veri taşımaz); verilebiliyorsa "". */
  not_loanable_reason: string;
  /** BARKOD etiketinin onaylı basım işareti (D10); boşsa barkod kuyruğunda. */
  label_printed_at: string | null;
  label_verified_at: string | null;
  /** SIRT etiketinin onaylı basım işareti (F4); boşsa sırt kuyruğunda. */
  spine_label_printed_at: string | null;
  created_at: string;
}

/** Nüsha açma gövdesi — barkod, kayıt no ve durum SUNUCUDAN gelir. */
export interface CopyBody {
  work: number;
  acquisition: number;
  section?: number | null;
  external_asset_ref?: string;
  old_register_no?: string;
  is_reference?: boolean;
  is_out_of_print?: boolean;
  is_bound_periodical?: boolean;
  is_rare_or_manuscript?: boolean;
}

/** Güncellemede eser ve edinim DEĞİŞMEZ (kimlik bilgisidir). */
export type CopyUpdateBody = Omit<CopyBody, "work" | "acquisition">;

/** Toplu açma: aynı künyeden `count` nüsha (Excel "Nüsha Sayısı"). */
export interface CopyBulkBody extends CopyBody {
  count: number;
}

/** `POST library/copies/bulk/` yanıtı — sayfalama DEĞİL, işlem sonucudur. */
export interface CopyBulkResult {
  count: number;
  results: Copy[];
}

/** Seçim ve Ayıklama Komisyonu kararı. Başkan adı ve katılımcılar şifreli alanlardır. */
export interface CommissionDecision {
  id: number;
  decision_type: CommissionDecisionType;
  decision_type_display: string;
  decision_date: string;
  decision_no: string;
  chair_name: string;
  chair_title: string;
  participants_text: string;
  notes: string;
  /** Karara bağlı edinim ya da bağış ön kaydı var mı? (türü kilitler, silmeyi engeller) */
  in_use: boolean;
  created_at: string;
}

export interface CommissionDecisionBody {
  decision_type: CommissionDecisionType;
  decision_date: string;
  decision_no?: string;
  chair_name: string;
  chair_title?: string;
  participants_text?: string;
  notes?: string;
}

/** Edinim partisi. `source_note` (bağışçı/satıcı) şifreli alandır. */
export interface Acquisition {
  id: number;
  method: AcquisitionMethod;
  method_display: string;
  date: string;
  source_note: string;
  /** DRF ondalığı METİN olarak gönderir ("45.00"). */
  unit_price: string | null;
  commission_decision: number | null;
  notes: string;
  copy_count: number;
  created_at: string;
}

export interface AcquisitionBody {
  method: AcquisitionMethod;
  date: string;
  source_note?: string;
  unit_price?: string | null;
  commission_decision?: number | null;
  notes?: string;
}

/** Bağış kalemi — henüz eser ve nüsha DEĞİL. Karar alanları salt okunurdur. */
export interface DonationIntakeItem {
  id: number;
  title: string;
  authors: string;
  publisher: string;
  publish_year: number | null;
  isbn: string;
  copies: number;
  decision: DonationItemDecision;
  decision_display: string;
  reject_reason: string;
  work: number | null;
  work_title: string | null;
  notes: string;
}

export interface DonationIntakeItemBody {
  title: string;
  authors?: string;
  publisher?: string;
  publish_year?: number | null;
  isbn?: string;
  copies?: number;
  notes?: string;
}

/** Bağış ön kaydı — komisyon kararına kadar nüsha açılmaz (Md. 10/3). */
export interface DonationIntake {
  id: number;
  donor_name: string;
  received_date: string;
  status: DonationIntakeStatus;
  status_display: string;
  commission_decision: number | null;
  acquisition: number | null;
  decided_at: string | null;
  notes: string;
  items: DonationIntakeItem[];
  item_count: number;
  created_at: string;
}

export interface DonationIntakeBody {
  donor_name?: string;
  received_date: string;
  notes?: string;
  items?: DonationIntakeItemBody[];
}

/**
 * Komisyon kararının uygulanması. `rejected` kalem kimliğinden GEREKÇEYE bir
 * eşlemedir (liste değil: aynı kalem iki gerekçeyle gönderilemesin). Her kalem
 * tam olarak bir kez kararlanmalıdır.
 */
export interface DonationDecisionBody {
  commission_decision: number;
  accepted_ids: number[];
  rejected: Record<string, string>;
  acquisition_date?: string | null;
  section?: number | null;
  unit_price?: string | null;
}

export interface DonationDecisionResult {
  intake: DonationIntake;
  accepted: number;
  rejected: number;
  acquisition: number | null;
  work_count: number;
  copy_count: number;
}

/** Koleksiyon özeti — kişisel veri İÇERMEZ. */
export interface LibraryStats {
  work_count: number;
  /** Kayıt defterinin toplamı: kayıttan düşülmüş ve devredilmiş nüshalar DAHİL. */
  copy_count: number;
  /** Elde bulunan nüsha (terminal durumlar düşülür) — Md. 7 eşiği budur. */
  in_stock_count: number;
  /** Şu anda RAFTA olan (ödünçteki ve teslimdeki nüsha elde vardır, rafta değildir). */
  available_count: number;
  status_counts: Record<CopyStatus, number>;
  section_count: number;
  /** Sıradaki nüsha numarasının basılı biçimi; sayacı İLERLETMEZ (sayaç doluysa null). */
  next_barcode: string | null;
}

// ---------------------------------------------------------------------------
// Toplu katalog aktarımı (F3, tasarım §8.1) — önizleme uygulamanın provasıdır
// ---------------------------------------------------------------------------

/** Aktarımın kaynağı — backend `CatalogImportSource`. */
export type AktarimKaynagi = "EXCEL" | "AI_JSON" | "EXPORT";

/** Koşu durumu — backend `CatalogImportStatus`. */
export type AktarimDurumu = "DRY_RUN" | "APPLIED" | "DISCARDED";

/** Eşleşme kovası — backend `import_service.BUCKET_*`. */
export type AktarimKovasi = "new" | "existing" | "suspect" | "skipped";

/** Kova adları (satır rozetinde ve sayaç kartlarında aynı metin). */
export const AKTARIM_KOVASI_TR: Record<AktarimKovasi, string> = {
  new: "Yeni eser",
  existing: "Mevcut esere nüsha",
  suspect: "Şüpheli",
  skipped: "Aktarılmadı",
};

/** Şüpheli satırın eşleşme adayı: ya katalogdaki eser ya bu dosyanın bir satırı. */
export interface AktarimAdayi {
  work: number | null;
  row: number | null;
  title: string;
  authors: string;
}

/** Köprünün bildirdiği düzeltme (sessiz düzeltme yoktur — §8.2). */
export interface AktarimDuzeltmesi {
  field: string;
  original: string;
  corrected: string;
}

/** Bir satırın önizleme/uygulama sonucu. KİŞİSEL VERİ TAŞIMAZ. */
export interface AktarimSatiri {
  /** Kullanıcının gördüğü satır numarası (Excel satırı ya da köprüdeki sıra). */
  row: number;
  title: string;
  bucket: AktarimKovasi;
  /** Eşleşen eser; önizlemede AÇILACAK eserlerde boştur. */
  work: number | null;
  /** Bu dosyada açılacak bir esere bağlanıyorsa o satırın numarası. */
  work_row: number | null;
  copies: number;
  copies_created: number;
  section: string;
  shelf_location: string;
  is_reference: boolean;
  /** Danışma bayrağı "ders kitabı" kuralından geldi (Md. 14/1-a, 16/1-a). */
  reference_by_textbook: boolean;
  classification_source: ClassificationSource;
  needs_decision: boolean;
  decision: string;
  /** Ekranda listelenen adaylar — TAVANLI (sunucudaki `MAX_CANDIDATES`). */
  candidates: AktarimAdayi[];
  /** Katalogdaki toplam aday sayısı (tavanla kırpılmadan önceki). */
  candidate_count: number;
  candidates_truncated: boolean;
  corrections: AktarimDuzeltmesi[];
  issues: string[];
}

/** Bölüm listesinde bulunmayan "Bölüm" değeri (önizlemede sorulur — D5). */
export interface BilinmeyenBolum {
  value: string;
  rows: number[];
  count: number;
}

/** F4 etiket kısayolunun bağlanacağı parti (nüsha kimlikleri taşınmaz). */
export interface EtiketPartisi {
  acquisition: number;
  copy_count: number;
  first_barcode: string;
  last_barcode: string;
}

/** Raporun sayaçları (backend `_ingest` hepsini her zaman doldurur). */
export interface AktarimSayilari {
  total_rows: number;
  imported_rows: number;
  new_works: number;
  existing_matches: number;
  suspect: number;
  skipped_rows: number;
  error_rows: number;
  copies_created: number;
  reference_defaults: number;
  estimated_codes: number;
  corrections: number;
  sections_created: number;
}

/** Önizleme ve uygulamanın ORTAK raporu (ekran tek biçim bekler). */
export interface AktarimRaporu {
  payload_sha256: string;
  source: AktarimKaynagi;
  schema_version: string;
  file_name: string;
  dry_run: boolean;
  /** Aynı içerik daha önce UYGULANMIŞ: önizlemede uyarı, uygulamada engel. */
  already_applied: boolean;
  applied_at: string;
  stats: AktarimSayilari;
  rows: AktarimSatiri[];
  /** Satır listesi tavana takıldı (sorunlu satırlar daima listededir). */
  rows_truncated: boolean;
  unknown_sections: BilinmeyenBolum[];
  unknown_headers: string[];
  missing_columns: string[];
  pending_decisions: number[];
  label_batch: EtiketPartisi | null;
  run_id: number | null;
}

/** Şüpheli satırın kararı: yeni eser aç ya da gösterilen esere nüsha ekle. */
export type AktarimKarari =
  { action: "new" } | { action: "attach"; work: number } | { action: "attach"; row: number };

/** Önizleme gövdesi — dosya ya da yapıştırılan JSON'dan TAM OLARAK BİRİ. */
export interface AktarimGovdesi {
  file?: File | null;
  payload?: unknown;
  /** Yalnız dosya yolunda anlamlı; JSON gövdesinde sunucu AI_JSON'a sabitler. */
  source?: AktarimKaynagi;
  /** Satır numarası → karar. */
  decisions?: Record<number, AktarimKarari>;
  /** Dosyadaki bölüm değeri → var olan bölümün kimliği. */
  section_map?: Record<string, number>;
  /** Yeni bölüm olarak açılacak değerler. */
  new_sections?: string[];
}

/** Uygulama gövdesi: önizlemenin aynısı + açılacak edinim partisi. */
export interface AktarimUygulamaGovdesi extends AktarimGovdesi {
  method?: AcquisitionMethod;
  date?: string | null;
  source_note?: string;
  unit_price?: string | null;
  commission_decision?: number | null;
  notes?: string;
}

/** Aktarım geçmişinin bir satırı (salt okunur; kişisel veri yok). */
export interface AktarimKosusu {
  id: number;
  uploaded_file_name: string;
  source: AktarimKaynagi;
  source_display: string;
  status: AktarimDurumu;
  status_display: string;
  payload_sha256: string;
  schema_version: string;
  acquisition: number | null;
  stats: Partial<AktarimSayilari>;
  report: Record<string, unknown>;
  created_at: string;
}

/** `GET library/import/ai-prompt/` — komut metni ve §8.2'nin dört uyarısı. */
export interface KopruKomutu {
  schema_version: string;
  prompt: string;
  /** Ekranda yazılı duran uyarı maddeleri; TEK KAYNAK sunucudadır. */
  notes: string[];
}

// ---------------------------------------------------------------------------
// Süzgeç parametreleri
// ---------------------------------------------------------------------------

export interface SayfaParametreleri {
  limit?: number;
  offset?: number;
}

export interface WorkListParams extends SayfaParametreleri {
  /** Serbest arama: ad + yazar + konu + ISBN (sunucuda Türkçe katlamalı). */
  q?: string;
  section?: number | null;
  resourceType?: ResourceType | "";
  order?: WorkOrder;
}

export interface CopyListParams extends SayfaParametreleri {
  work?: number | null;
  /** Edinim partisi — aktarımdan sonra "bu partinin etiketleri" kuyruğu (F4). */
  acquisition?: number | null;
  section?: number | null;
  status?: CopyStatus | "";
  /** Okutulan ya da basılı biçim; TAM eşleşme. */
  barcode?: string;
  oldRegisterNo?: string;
  onlyLoanable?: boolean;
  onlyUnlabeled?: boolean;
  /** Kayıttan düşülmüş ve devredilmiş nüshaları gizler. */
  excludeTerminal?: boolean;
}

export interface AktarimKosusuListParams extends SayfaParametreleri {
  status?: AktarimDurumu | "";
  source?: AktarimKaynagi | "";
}

export interface CommissionDecisionListParams extends SayfaParametreleri {
  decisionType?: CommissionDecisionType | "";
}

export interface AcquisitionListParams extends SayfaParametreleri {
  method?: AcquisitionMethod | "";
}

export interface DonationIntakeListParams extends SayfaParametreleri {
  status?: DonationIntakeStatus | "";
}

// ---------------------------------------------------------------------------
// Sorgu dizesi yardımcıları
// ---------------------------------------------------------------------------

/** Parça yoksa yolu olduğu gibi bırakır (gereksiz "?" üretmez). */
function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

/** Sayfalama parçaları — `limit` her zaman, `offset` yalnız sıfırdan büyükse. */
function sayfaParcalari(params: SayfaParametreleri): string[] {
  const parts: string[] = [];
  if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
  if (params.offset) parts.push(`offset=${params.offset}`);
  return parts;
}

/** Boş olmayan metin süzgeci (kırpılmış ve kaçışlı). */
function metinParcasi(parts: string[], ad: string, deger: string | undefined): void {
  const temiz = (deger ?? "").trim();
  if (temiz) parts.push(`${ad}=${encodeURIComponent(temiz)}`);
}

/**
 * Aktarım isteğini gönderir: önizleme ve uygulama AYNI gövdeyi taşır.
 *
 * Dosya varsa istek çok parçalıdır (`multipart/form-data`) ve orada her alan
 * METİNDİR: kararlar, bölüm eşlemesi ve yeni bölüm listesi JSON metni olarak
 * yazılır (sunucudaki `JsonOrTextField` onları çözer). Dosya yoksa gövde düz
 * JSON'dur; sunucu kaynağı kendisi köprüye sabitler.
 *
 * Gönderilmeyen alan gövdede HİÇ bulunmaz: servis kendi varsayılanını uygular
 * (tek yer). `null` göndermek "bu alanı boşalt" demek olurdu.
 */
function aktarimIstegi(yol: string, govde: AktarimUygulamaGovdesi): Promise<AktarimRaporu> {
  const kararlar = govde.decisions;
  const bolumEslemesi = govde.section_map;
  const yeniBolumler = govde.new_sections;
  if (!govde.file) {
    const paket: Record<string, unknown> = { payload: govde.payload };
    if (kararlar) paket.decisions = kararlar;
    if (bolumEslemesi) paket.section_map = bolumEslemesi;
    if (yeniBolumler) paket.new_sections = yeniBolumler;
    return api.post<AktarimRaporu>(yol, { ...paket, ...edinimAlanlari(govde) });
  }
  const form = new FormData();
  form.append("file", govde.file);
  form.append("source", govde.source ?? "EXCEL");
  if (kararlar) form.append("decisions", JSON.stringify(kararlar));
  if (bolumEslemesi) form.append("section_map", JSON.stringify(bolumEslemesi));
  if (yeniBolumler) form.append("new_sections", JSON.stringify(yeniBolumler));
  for (const [ad, deger] of Object.entries(edinimAlanlari(govde))) {
    if (deger !== undefined && deger !== null) form.append(ad, String(deger));
  }
  return api.postForm<AktarimRaporu>(yol, form);
}

/** Uygulamanın edinim alanları (önizlemede gönderilmez, orada hepsi boştur). */
function edinimAlanlari(govde: AktarimUygulamaGovdesi): Record<string, unknown> {
  const alanlar: Record<string, unknown> = {};
  if (govde.method !== undefined) alanlar.method = govde.method;
  if (govde.date !== undefined && govde.date !== null) alanlar.date = govde.date;
  if (govde.source_note !== undefined) alanlar.source_note = govde.source_note;
  if (govde.unit_price !== undefined && govde.unit_price !== null) {
    alanlar.unit_price = govde.unit_price;
  }
  if (govde.commission_decision !== undefined && govde.commission_decision !== null) {
    alanlar.commission_decision = govde.commission_decision;
  }
  if (govde.notes !== undefined) alanlar.notes = govde.notes;
  return alanlar;
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

export const kutuphaneApi = {
  /** `GET /library/import/template/` — boş katalog Excel şablonu (.xlsx). */
  catalogTemplate: (): Promise<Blob> => api.getBlob("/library/import/template/"),

  // --- Toplu katalog aktarımı (F3, §8.1) ---

  /**
   * `POST library/import/preview/` — yazmadan önizler.
   *
   * Sunucu gerçek yazmayı koşup geri sarar: buradaki sayılar uygulamanın
   * yazacağı sayılardır. Yanıt ayrıca ekranın toplaması gereken eksikleri
   * söyler (`pending_decisions`, `unknown_sections`, `already_applied`).
   */
  aktarimOnizle: (govde: AktarimGovdesi): Promise<AktarimRaporu> =>
    aktarimIstegi("/library/import/preview/", govde),

  /**
   * `POST library/import/apply/` — onaylanan aktarımı uygular.
   *
   * Gövde önizlemenin AYNISIDIR (dosya dahil: program yüklenen dosyayı
   * saklamaz), üstüne açılacak edinim partisinin alanları eklenir. Aynı dosya
   * ikinci kez uygulanamaz (§8.1 fikirdeşlik — uyarı değil engel).
   */
  aktarimiUygula: (govde: AktarimUygulamaGovdesi): Promise<AktarimRaporu> =>
    aktarimIstegi("/library/import/apply/", govde),

  /** `GET library/import/runs/` — aktarım geçmişi (en yeniden eskiye). */
  aktarimGecmisi: (params: AktarimKosusuListParams = {}): Promise<Paginated<AktarimKosusu>> => {
    const parts = sayfaParcalari(params);
    if (params.status) parts.push(`status=${params.status}`);
    if (params.source) parts.push(`source=${params.source}`);
    return api.get<Paginated<AktarimKosusu>>(withQuery("/library/import/runs/", parts));
  },

  /**
   * `POST library/import/runs/<id>/discard/` — önizlemeden vazgeçildi.
   *
   * Her önizleme kalıcı bir koşu satırı yazar; kullanıcı kararlarını değiştirip
   * yeniden önizlediğinde eskisi iptal edilir, yoksa geçmiş önizlemelerle dolar.
   * Uygulanmış aktarım iptal EDİLEMEZ (fikirdeşliğin izi odur).
   */
  aktarimiIptalEt: (id: number): Promise<AktarimKosusu> =>
    api.post<AktarimKosusu>(`/library/import/runs/${id}/discard/`, {}),

  /**
   * `GET library/import/ai-prompt/` — köprünün komut metni ve uyarıları (§8.2).
   *
   * Metin programın içindedir; DIŞARIYA istek atılmaz. Ekrandaki dört uyarı
   * maddesi de buradan gelir (tek kaynak — ön yüz kopya yazmaz).
   */
  kopruKomutu: (): Promise<KopruKomutu> => api.get<KopruKomutu>("/library/import/ai-prompt/"),

  // --- Kütüphane politikası ---

  getPolicy: (): Promise<LibraryPolicy> => api.get<LibraryPolicy>("/library/policy/"),

  /** PUT kısmidir: yalnız gönderilen alanlar değişir (Ayarlar birden çok sekmeden yazar). */
  updatePolicy: (body: LibraryPolicyBody): Promise<LibraryPolicy> =>
    api.put<LibraryPolicy>("/library/policy/", body),

  /** Kişisiz koleksiyon özeti + sıradaki nüsha numarası. */
  getStats: (): Promise<LibraryStats> => api.get<LibraryStats>("/library/stats/"),

  // --- ISBN ile künye getirme (U13, §8.5) ---

  /**
   * `POST library/metadata/lookup/` — tek ISBN'in künye ÖNERİSİ.
   *
   * Yalnız kullanıcının eylemiyle çağrılır (§8.5-2): açılışta, arka planda ve
   * toplu içe aktarımda ASLA. Ayar kapalıyken sunucu 409 `kunye_kapali` döner
   * ve hiçbir dış istek çıkmaz. Yanıt öneridir: kullanıcı onaylayıp
   * `updateWork` ile kaydedene kadar hiçbir alan değişmez.
   */
  kunyeGetir: (isbn: string, secenekler: { work?: number; force?: boolean } = {}) =>
    api.post<KunyeSonucu>("/library/metadata/lookup/", {
      isbn,
      work: secenekler.work ?? null,
      force: secenekler.force ?? false,
    }),

  /** `GET library/metadata/offline-export/` — künyesi eksik eserlerin ISBN listesi (.xlsx). */
  kunyeListesiIndir: (): Promise<Blob> => api.getBlob("/library/metadata/offline-export/"),

  /** `POST library/metadata/offline-preview/` — doldurulmuş dosyanın ön izlemesi (yazma yok). */
  kunyeDosyasiOnizle: (dosya: File): Promise<CevrimdisiKunyeOnizleme> => {
    const form = new FormData();
    form.append("file", dosya);
    return api.postForm<CevrimdisiKunyeOnizleme>("/library/metadata/offline-preview/", form);
  },

  // --- Bölümler ---

  listSections: (params: SayfaParametreleri = {}): Promise<Paginated<Section>> =>
    api.get<Paginated<Section>>(withQuery("/library/sections/", sayfaParcalari(params))),

  createSection: (body: SectionBody): Promise<Section> =>
    api.post<Section>("/library/sections/", body),

  updateSection: (id: number, body: Partial<SectionBody>): Promise<Section> =>
    api.patch<Section>(`/library/sections/${id}/`, body),

  deleteSection: (id: number): Promise<void> => api.del<void>(`/library/sections/${id}/`),

  // --- Eserler ---

  listWorks: (params: WorkListParams = {}): Promise<Paginated<Work>> => {
    const parts = sayfaParcalari(params);
    metinParcasi(parts, "q", params.q);
    if (params.section) parts.push(`section=${params.section}`);
    if (params.resourceType) parts.push(`resource_type=${params.resourceType}`);
    if (params.order) parts.push(`order=${params.order}`);
    return api.get<Paginated<Work>>(withQuery("/library/works/", parts));
  },

  getWork: (id: number): Promise<Work> => api.get<Work>(`/library/works/${id}/`),

  createWork: (body: WorkBody): Promise<Work> => api.post<Work>("/library/works/", body),

  updateWork: (id: number, body: Partial<WorkBody>): Promise<Work> =>
    api.patch<Work>(`/library/works/${id}/`, body),

  /** Canlı nüshası olan eser silinmez (sunucu reddeder). */
  deleteWork: (id: number): Promise<void> => api.del<void>(`/library/works/${id}/`),

  // --- Nüshalar ---

  listCopies: (params: CopyListParams = {}): Promise<Paginated<Copy>> => {
    const parts = sayfaParcalari(params);
    if (params.work) parts.push(`work=${params.work}`);
    if (params.acquisition) parts.push(`acquisition=${params.acquisition}`);
    if (params.section) parts.push(`section=${params.section}`);
    if (params.status) parts.push(`status=${params.status}`);
    metinParcasi(parts, "barcode", params.barcode);
    metinParcasi(parts, "old_register_no", params.oldRegisterNo);
    if (params.onlyLoanable) parts.push("only_loanable=true");
    if (params.onlyUnlabeled) parts.push("only_unlabeled=true");
    if (params.excludeTerminal) parts.push("exclude_terminal=true");
    return api.get<Paginated<Copy>>(withQuery("/library/copies/", parts));
  },

  createCopy: (body: CopyBody): Promise<Copy> => api.post<Copy>("/library/copies/", body),

  /** Aynı künyeden `count` nüsha; her biri AYRI numara alır. Yanıt `{count, results}`. */
  createCopies: (body: CopyBulkBody): Promise<CopyBulkResult> =>
    api.post<CopyBulkResult>("/library/copies/bulk/", body),

  updateCopy: (id: number, body: Partial<CopyUpdateBody>): Promise<Copy> =>
    api.patch<Copy>(`/library/copies/${id}/`, body),

  /** Yalnız veri giriş hatası içindir; numarayı serbest BIRAKMAZ. */
  deleteCopy: (id: number): Promise<void> => api.del<void>(`/library/copies/${id}/`),

  // --- Komisyon kararları ---

  listCommissionDecisions: (
    params: CommissionDecisionListParams = {},
  ): Promise<Paginated<CommissionDecision>> => {
    const parts = sayfaParcalari(params);
    if (params.decisionType) parts.push(`decision_type=${params.decisionType}`);
    return api.get<Paginated<CommissionDecision>>(
      withQuery("/library/commission-decisions/", parts),
    );
  },

  createCommissionDecision: (body: CommissionDecisionBody): Promise<CommissionDecision> =>
    api.post<CommissionDecision>("/library/commission-decisions/", body),

  updateCommissionDecision: (
    id: number,
    body: Partial<CommissionDecisionBody>,
  ): Promise<CommissionDecision> =>
    api.patch<CommissionDecision>(`/library/commission-decisions/${id}/`, body),

  deleteCommissionDecision: (id: number): Promise<void> =>
    api.del<void>(`/library/commission-decisions/${id}/`),

  // --- Edinimler ---

  listAcquisitions: (params: AcquisitionListParams = {}): Promise<Paginated<Acquisition>> => {
    const parts = sayfaParcalari(params);
    if (params.method) parts.push(`method=${params.method}`);
    return api.get<Paginated<Acquisition>>(withQuery("/library/acquisitions/", parts));
  },

  createAcquisition: (body: AcquisitionBody): Promise<Acquisition> =>
    api.post<Acquisition>("/library/acquisitions/", body),

  updateAcquisition: (id: number, body: Partial<AcquisitionBody>): Promise<Acquisition> =>
    api.patch<Acquisition>(`/library/acquisitions/${id}/`, body),

  /** Nüshası ya da bağış ön kaydı olan parti silinmez (sunucu reddeder). */
  deleteAcquisition: (id: number): Promise<void> => api.del<void>(`/library/acquisitions/${id}/`),

  // --- Bağış ön kayıtları ---

  listDonationIntakes: (
    params: DonationIntakeListParams = {},
  ): Promise<Paginated<DonationIntake>> => {
    const parts = sayfaParcalari(params);
    if (params.status) parts.push(`status=${params.status}`);
    return api.get<Paginated<DonationIntake>>(withQuery("/library/donation-intakes/", parts));
  },

  getDonationIntake: (id: number): Promise<DonationIntake> =>
    api.get<DonationIntake>(`/library/donation-intakes/${id}/`),

  createDonationIntake: (body: DonationIntakeBody): Promise<DonationIntake> =>
    api.post<DonationIntake>("/library/donation-intakes/", body),

  updateDonationIntake: (
    id: number,
    body: Partial<Omit<DonationIntakeBody, "items">>,
  ): Promise<DonationIntake> => api.patch<DonationIntake>(`/library/donation-intakes/${id}/`, body),

  /** Kararı işlenmiş ön kayıt silinmez; vazgeçme yolu iptaldir. */
  deleteDonationIntake: (id: number): Promise<void> =>
    api.del<void>(`/library/donation-intakes/${id}/`),

  addDonationItem: (intakeId: number, body: DonationIntakeItemBody): Promise<DonationIntakeItem> =>
    api.post<DonationIntakeItem>(`/library/donation-intakes/${intakeId}/items/`, body),

  updateDonationItem: (
    intakeId: number,
    itemId: number,
    body: Partial<DonationIntakeItemBody>,
  ): Promise<DonationIntakeItem> =>
    api.patch<DonationIntakeItem>(`/library/donation-intakes/${intakeId}/items/${itemId}/`, body),

  removeDonationItem: (intakeId: number, itemId: number): Promise<void> =>
    api.del<void>(`/library/donation-intakes/${intakeId}/items/${itemId}/`),

  /** Komisyon kararını uygular: kabul edilenler TEK İŞLEMDE kataloglanır. */
  applyDonationDecision: (
    intakeId: number,
    body: DonationDecisionBody,
  ): Promise<DonationDecisionResult> =>
    api.post<DonationDecisionResult>(`/library/donation-intakes/${intakeId}/decision/`, body),

  cancelDonationIntake: (intakeId: number, reason: string): Promise<DonationIntake> =>
    api.post<DonationIntake>(`/library/donation-intakes/${intakeId}/cancel/`, { reason }),
};
