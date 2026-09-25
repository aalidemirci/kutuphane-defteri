// Sayım istemcisi (F9 — Taşınır Mal Yönetmeliği md. 32; tasarım §9-10, §9-11, §10 E10).
// Tipler backend serializer'larıyla BİREBİRDİR (`serializers_sayim.py`, `views_sayim.py`,
// `selectors_sayim.py`, `views_sayim_belgeleri.py`); alan listeleri backend'de anlık
// görüntüyle sabittir.
//
// Görevli kipinde YALNIZ okutma ucu açıktır (madde 24, 25.09.2026 kullanıcı kararı): yanıt
// daralır — `{results: [{code, message, barcode, barcode_display, work_title}]}` (kalem ve
// özet yok; `GorevliOkutmaYaniti`). Sayımı başlatmak, tamamlamak, onaylamak, iptal etmek ve
// fazlaya karar vermek yönetici işidir. Görevli ekranı süren sayımı masa durumundan öğrenir
// (`dolasim/api.ts::masaDurumu`). Kural sunucudadır: kurulun seçebildikleri
// (`basis_choices`), seçeneklerin tutanak satırları (`options`), kurul seçiminin dayanağı
// (`basis_lines`) ve belgenin basılabilirliği (`…/documents/`) sunucudan okunur; ekran
// kopyalamaz.
//
// Sözlük (docs/sozluk.md — bağlayıcı): "sayım", "sayım kurulu", "TMY 32/3 durdurması",
// "sayım için hizmet arası". "Sayım kilidi" ve "dondurma" DENMEZ. İade hiçbir durumda
// durmaz.
//
// Kişisel veri: kalemler kişisizdir (ödünç alanın ve teslim alanın kimliği yoktur). Kurul
// ve harcama yetkilisi adları sunucuda ŞİFRELİDİR; parola kurulmadan yazan istek 409
// `parola_gerekli` döner (ui/ErrorBand).

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";
import type { CopyStatus } from "../kutuphane/api";

// ---------------------------------------------------------------------------
// Kod listeleri (backend TextChoices ile birebir) ve Türkçe adları
// ---------------------------------------------------------------------------

/** Sayımın durumu — `StockTakeStatus`. */
export type SayimDurumu = "DRAFT" | "IN_PROGRESS" | "COMPLETED" | "APPROVED" | "CANCELLED";

export const SAYIM_DURUMU_TR: Record<SayimDurumu, string> = {
  DRAFT: "Taslak",
  IN_PROGRESS: "Sürüyor",
  COMPLETED: "Tamamlandı",
  APPROVED: "Onaylandı",
  CANCELLED: "İptal edildi",
};

/**
 * Nüshanın nasıl sayıldığı — `CountBasis` (kurul ödünçteki, teslimdeki ve onarımdaki nüsha için
 * seçer). Onarımda adlar kararın sözcükleridir ("Sayımdan önce geri alınır", "Kayda göre
 * alınır — onarımda"); sunucu `basis_choices` ve `basis_display` ile verir.
 */
export type SayimBicimi = "LIBRARY" | "COLLECT" | "IN_PLACE" | "BY_RECORD";

export const SAYIM_BICIMI_TR: Record<SayimBicimi, string> = {
  LIBRARY: "Kütüphanede sayılır",
  COLLECT: "Sayımdan önce toplanır",
  IN_PLACE: "Yerinde sayılır",
  BY_RECORD: "Kayda göre alınır",
};

/** Kalemin sayım sonucu — `StockTakeResult`. */
export type SayimSonucu = "PENDING" | "FOUND" | "BY_RECORD" | "MISSING" | "SURPLUS" | "EXITED";

export const SAYIM_SONUCU_TR: Record<SayimSonucu, string> = {
  PENDING: "Sayılmadı",
  FOUND: "Bulundu",
  BY_RECORD: "Kayda göre alındı",
  MISSING: "Noksan",
  SURPLUS: "Fazla",
  EXITED: "Sayım sırasında kayıttan çıktı",
};

/** Onayda kaleme ne olduğu — `StockTakeOutcome`. */
export type OnaySonucu =
  "WRITTEN_OFF" | "NOT_APPROVED" | "STATE_CHANGED" | "RECONCILED" | "ENTERED" | "NOT_ENTERED";

export const ONAY_SONUCU_TR: Record<OnaySonucu, string> = {
  WRITTEN_OFF: "Kayıttan düşüldü",
  NOT_APPROVED: "Onaylanmadı",
  STATE_CHANGED: "Onayda durumu değişmişti — düşülmedi",
  RECONCILED: "Kayıp kaydı kapandı",
  ENTERED: "Kayda alındı",
  NOT_ENTERED: "Kayda alınmadı",
};

/** Okutmanın sonucu (kararlı kodlar — `services.stocktake.OKUTMA_*`). */
export type OkutmaKodu =
  "bulundu" | "zaten_okutuldu" | "fazla" | "fazla_tekrar" | "kapsam_disi" | "gecersiz";

/** Tek istekte okutulabilecek en çok kod (backend `MAX_SCANS_PER_REQUEST`). */
export const EN_COK_OKUTMA = 200;

// ---------------------------------------------------------------------------
// Tipler
// ---------------------------------------------------------------------------

/** Kurulun seçenek satırı — `{value, label}`. */
export interface Secenek<T extends string = string> {
  value: T;
  label: string;
}

/** Tutanak satırı: iki seçenek ve iade AYRI satırlarda (`selectors_sayim.options_lines`). */
export interface SecenekSatiri {
  key: "tmy_32_3" | "service_pause" | "return";
  label: string;
  selected: boolean;
  text: string;
  basis: string;
}

/** Kurulun ödünçteki, teslimdeki ve onarımdaki nüsha seçimi ve dayanağı (`basis_lines`). */
export interface KurulSecimiSatiri {
  category: "loan" | "section_delivery" | "teacher_delivery" | "repair";
  label: string;
  basis: SayimBicimi;
  basis_display: string;
  dayanak: string;
}

/** Kişisiz sayılar — `selectors_sayim.summary`. */
export interface SayimOzeti {
  snapshot: number;
  results: Record<SayimSonucu, number>;
  outcomes: Record<OnaySonucu, number>;
  physical_expected: number;
  physical_found: number;
  by_record_basis: number;
  surplus: number;
  surplus_unresolved: number;
  surplus_excluded: number;
  /** Etiketi sayım sırasında bir nüshaya bağlanan fazla (onay ikinci kez kayda almaz). */
  surplus_bound: number;
  damage_write_off: number;
  found_in_round2: number;
  /** Tamamlanırken kayıtta "Kayıp" ya da "Onarımda" görünen noksanlar (onay uyarısı). */
  missing_recorded_lost: number;
  missing_in_repair: number;
}

/** Liste satırı — `StockTakeListSerializer` (kişi adı YOK). */
export interface Sayim {
  id: number;
  status: SayimDurumu;
  status_display: string;
  fiscal_year: number | null;
  round: number;
  tmy_stop: boolean;
  service_pause: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  approved_on: string | null;
  cancelled_at: string | null;
}

/** Sayım ayrıntısı — `StockTakeDetailSerializer` (kurul ve harcama yetkilileri şifreli alandan). */
export interface SayimAyrintisi extends Sayim {
  committee_chair: string;
  committee_property_officer: string;
  committee_members: string;
  tmy_stop_requested_on: string | null;
  tmy_stop_by_name: string;
  tmy_stop_on: string | null;
  service_pause_decision: string;
  loan_basis: SayimBicimi;
  loan_basis_display: string;
  section_delivery_basis: SayimBicimi;
  section_delivery_basis_display: string;
  teacher_delivery_basis: SayimBicimi;
  teacher_delivery_basis_display: string;
  /** Onarımdaki nüsha (K2): "COLLECT" · "BY_RECORD". */
  repair_basis: SayimBicimi;
  repair_basis_display: string;
  notes: string;
  round2_started_at: string | null;
  approved_by_name: string;
  approved_at: string | null;
  surplus_acquisition: number | null;
  cancel_reason: string;
  locks_active: boolean;
  options: SecenekSatiri[];
  basis_lines: KurulSecimiSatiri[];
  basis_choices: {
    loan_basis: Secenek<SayimBicimi>[];
    section_delivery_basis: Secenek<SayimBicimi>[];
    teacher_delivery_basis: Secenek<SayimBicimi>[];
    repair_basis: Secenek<SayimBicimi>[];
  };
  summary: SayimOzeti;
}

/** Taslak gövdesi (`POST library/stocktakes/`, taslakta `PATCH`). */
export interface TaslakGovdesi {
  fiscal_year?: number | null;
  committee_chair?: string;
  committee_property_officer?: string;
  committee_members?: string;
  tmy_stop?: boolean;
  tmy_stop_requested_on?: string | null;
  tmy_stop_by_name?: string;
  tmy_stop_on?: string | null;
  service_pause?: boolean;
  service_pause_decision?: string;
  loan_basis?: SayimBicimi;
  section_delivery_basis?: SayimBicimi;
  teacher_delivery_basis?: SayimBicimi;
  repair_basis?: SayimBicimi;
  notes?: string;
}

/** Sayım kalemi — `StockTakeItemSerializer` (KİŞİSİZ). Fazlada nüsha alanları boştur. */
export interface SayimKalemi {
  id: number;
  copy: number | null;
  barcode: string;
  barcode_display: string;
  work: number | null;
  work_title: string;
  work_authors: string;
  call_number: string;
  section: number | null;
  section_name: string;
  class_library: string;
  copy_status: CopyStatus | "";
  copy_status_display: string;
  expected_status: CopyStatus | "";
  expected_status_display: string;
  delivery_kind: "SECTION" | "TEACHER" | "";
  basis: SayimBicimi | "";
  basis_display: string;
  basis_fallback: boolean;
  result: SayimSonucu;
  result_display: string;
  found_in_round: number | null;
  found_via: "SCAN" | "RETURN" | "";
  found_via_display: string;
  scanned_at: string | null;
  status_at_completion: CopyStatus | "";
  damage_write_off: boolean;
  case: number | null;
  case_type: "LOST" | "DAMAGED" | "";
  case_resolution_display: string;
  outcome: OnaySonucu | "";
  outcome_display: string;
  write_off_path: "MISSING_32_7" | "DAMAGE_27_1" | "";
  write_off_path_display: string;
  outcome_note: string;
  is_surplus: boolean;
  surplus_barcode: string;
  surplus_barcode_display: string;
  surplus_copy: number | null;
  surplus_work: number | null;
  surplus_work_title: string;
  surplus_note: string;
  surplus_excluded: boolean;
  created_copy: number | null;
  created_copy_barcode: string;
  /** Etiketi sayım sırasında bağlandıysa o nüshanın basılı barkodu (yoksa boş). */
  surplus_bound_barcode: string;
}

/** Bir okutmanın sonucu. */
export interface OkutmaSonucu {
  code: OkutmaKodu;
  message: string;
  barcode: string;
  item: SayimKalemi | null;
}

export interface OkutmaYaniti {
  results: OkutmaSonucu[];
  summary: SayimOzeti;
}

/**
 * Görevli kipinde bir okutmanın sonucu (backend `serializers_sayim.STAFF_SCAN_FIELDS`): yalnız
 * sonuç, ileti, barkod ve eser adı. Kalem, özet ve kayda göre durum YOKTUR (madde 24).
 */
export interface GorevliOkutmaSonucu {
  code: OkutmaKodu;
  message: string;
  barcode: string;
  barcode_display: string;
  work_title: string;
}

export interface GorevliOkutmaYaniti {
  results: GorevliOkutmaSonucu[];
}

/** Bölüm bölüm ve sınıf kitaplığı sınıf kitaplığı ilerleme — `selectors_sayim.progress`. */
export interface SayimIlerlemesi {
  round: number;
  sections: Array<{ section: number | null; name: string; expected: number; found: number }>;
  class_libraries: Array<{
    class_section: number | null;
    label: string;
    expected: number;
    found: number;
  }>;
  physical_expected: number;
  physical_found: number;
  by_record_basis: number;
  surplus: number;
}

/** Genel Bakış kartı — `GET library/stocktakes/state/` (kişisiz). */
export interface SayimDurumOzeti {
  live: {
    id: number;
    status: SayimDurumu;
    status_display: string;
    round: number;
    started_at: string | null;
    tmy_stop: boolean;
    service_pause: boolean;
    physical_expected: number;
    physical_found: number;
    surplus: number;
  } | null;
  tmy_stop_active: boolean;
  service_pause_active: boolean;
  returns_open: true;
}

export interface TamamlamaYaniti {
  second_round: boolean;
  missing: number;
  stocktake: SayimAyrintisi;
}

export interface OnayGovdesi {
  approved_by_name: string;
  approved_on: string;
  /** Kalem kimliği → onaylanmama gerekçesi (yalnız noksan ya da hasar önerisi). */
  not_approved?: Record<string, string>;
}

export interface OnayYaniti {
  written_off: number;
  damage_written_off: number;
  not_approved: number;
  state_changed: number;
  reconciled: number;
  surplus_entered: number;
  surplus_excluded: number;
  stocktake: SayimAyrintisi;
}

/** Sayım belgesinin basılabilirliği — `GET …/documents/`. */
export interface SayimBelgesi {
  kind: string;
  title: string;
  formats: Array<"pdf" | "xlsx">;
  available: boolean;
  reason: string;
}

export interface KalemSorgusu {
  result?: SayimSonucu | "";
  outcome?: OnaySonucu | "";
  section?: number | null;
  surplus?: boolean;
  damage?: boolean;
  /** Kararı bekleyen sayım fazlası (eseri seçilmemiş, "Kayda alınmayacak" denmemiş). */
  undecided?: boolean;
  q?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Adlar ve adresler (sözlük §2, §4)
// ---------------------------------------------------------------------------

export const SAYIM_ADRESI = "/katalog/sayim";
export const SAYIM_BASLIGI = "Sayım";
/** Belge adı (sözlük §2 — E10) ve ekin adı (A8 kararı). */
export const SAYIM_TUTANAGI_ADI = "Sayım tutanağı";
export const EK_ADI = "Taşınır Sayım ve Döküm Cetveline aktarılacak sayılar";

/** İki seçeneğin adları (sözlük §1 — tutanakta ve ekranda ayrı satırlarda). */
export const TMY_DURDURMASI = "TMY 32/3 durdurması";
export const HIZMET_ARASI = "Sayım için hizmet arası";

/**
 * TMY 32/3 durdurmasının kapsadığı işlemler — backend `selectors_sayim.TMY_STOP_SCOPE_TEXT` ile
 * BİREBİR (`test_on_yuz_sabitleri.py` sınar). Kapının gerçek kapsamıdır: kayıp dosyasında bedel
 * adımları, hasar dosyasında öneri yazmayan çözümler durmaz.
 */
export const TMY_DURDURMA_KAPSAMI =
  "edinim ve yeni nüsha kaydı, kayıttan düşme, devir, kayıp bildirimi, kayıp dosyasının bulunma ve bedel adımları dışındaki çözümü ve hasar dosyasında kayıttan düşme önerisi";
/**
 * Programa aktarım durdurma süresince kapalıdır ama TMY'ye dayandırılmaz (F9 ekleri K4) —
 * backend `tmy_kapisi.PROGRAMA_AKTARIM_MESSAGE` ile BİREBİR (`test_on_yuz_sabitleri.py`).
 */
export const PROGRAMA_AKTARIM_KAPALI =
  "Sayım sürerken programa aktarım yapılamaz; sayım bitince aktarın.";
/**
 * Durdurmanın kapsamadıkları — durumu değil KAPSAMI söyler (backend
 * `TMY_STOP_NOT_COVERED_TEXT`): hizmet arası da seçildiyse yeni ödünç o yüzden kapalıdır.
 */
export const TMY_DURDURMA_KAPSAMAZ = "Durdurma ödüncü ve iadeyi kapsamaz.";

/** Sayım adresi (listeden ayrıntıya). */
export function sayimAdresi(id: number): string {
  return `${SAYIM_ADRESI}?sayim=${id}`;
}

/** Sayımın kısa adı: "Sayım · 2026 · 25.09.2026" (iç kimlik yazılmaz). */
export function sayimAdi(s: Pick<Sayim, "fiscal_year" | "created_at" | "started_at">): string {
  const tarih = formatDate(s.started_at ?? s.created_at);
  // Mali yıl taslakta boş olabilir (başlatınca sayımın başladığı yıl yazılır).
  const yil = s.fiscal_year ?? tarih.slice(-4);
  return `Sayım · ${yil} · ${tarih}`;
}

/** İndirme adı: belge adı + tarih (`lib/download.ts`). */
export function belgeDosyaAdi(ad: string, uzanti: "pdf" | "xlsx" = "pdf"): string {
  return dosyaAdi([ad, formatDate(todayIso())], uzanti);
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

const SAYIM = "/library/stocktakes/";

function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

export const sayimApi = {
  /** Genel Bakış kartı ve kilit bantları (kişisiz; kullanıcı eylemi değildir). */
  durum: (): Promise<SayimDurumOzeti> =>
    api.get<SayimDurumOzeti>(`${SAYIM}state/`, { etkinlik: false }),

  sayimlar: (
    s: { status?: SayimDurumu | ""; limit?: number; offset?: number } = {},
  ): Promise<Paginated<Sayim>> => {
    const parts: string[] = [];
    if (s.status) parts.push(`status=${s.status}`);
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<Paginated<Sayim>>(withQuery(SAYIM, parts));
  },

  sayim: (id: number): Promise<SayimAyrintisi> => api.get<SayimAyrintisi>(`${SAYIM}${id}/`),

  taslakAc: (govde: TaslakGovdesi = {}): Promise<SayimAyrintisi> =>
    api.post<SayimAyrintisi>(SAYIM, govde),

  taslakGuncelle: (id: number, govde: TaslakGovdesi): Promise<SayimAyrintisi> =>
    api.patch<SayimAyrintisi>(`${SAYIM}${id}/`, govde),

  taslakSil: (id: number): Promise<void> => api.del<void>(`${SAYIM}${id}/`),

  baslat: (id: number): Promise<SayimAyrintisi> => api.post<SayimAyrintisi>(`${SAYIM}${id}/start/`),

  /** Okuyucu kuyruğu: tek kod ya da en çok `EN_COK_OKUTMA` kod; her kod ayrı sonuç döner. */
  okut: (id: number, kodlar: string[]): Promise<OkutmaYaniti> =>
    api.post<OkutmaYaniti>(
      `${SAYIM}${id}/scan/`,
      kodlar.length === 1 ? { barcode: kodlar[0] } : { barcodes: kodlar },
    ),

  /** Görevli kipinde okutma (aynı uç; yanıt daralmıştır — madde 24). Tek kod. */
  gorevliOkut: (id: number, kod: string): Promise<GorevliOkutmaYaniti> =>
    api.post<GorevliOkutmaYaniti>(`${SAYIM}${id}/scan/`, { barcode: kod }),

  kalemler: (id: number, s: KalemSorgusu = {}): Promise<Paginated<SayimKalemi>> => {
    const parts: string[] = [];
    if (s.result) parts.push(`result=${s.result}`);
    if (s.outcome) parts.push(`outcome=${s.outcome}`);
    if (s.section !== undefined && s.section !== null) parts.push(`section=${s.section}`);
    if (s.surplus !== undefined) parts.push(`surplus=${s.surplus ? 1 : 0}`);
    if (s.damage !== undefined) parts.push(`damage=${s.damage ? 1 : 0}`);
    if (s.undecided !== undefined) parts.push(`undecided=${s.undecided ? 1 : 0}`);
    if (s.q) parts.push(`q=${encodeURIComponent(s.q)}`);
    if (s.limit !== undefined) parts.push(`limit=${s.limit}`);
    if (s.offset) parts.push(`offset=${s.offset}`);
    return api.get<Paginated<SayimKalemi>>(withQuery(`${SAYIM}${id}/items/`, parts));
  },

  fazlaEkle: (id: number, govde: { note: string; work?: number | null }): Promise<SayimKalemi> =>
    api.post<SayimKalemi>(`${SAYIM}${id}/surplus/`, govde),

  fazlaGuncelle: (
    id: number,
    kalemId: number,
    govde: { note?: string; work?: number | null; excluded?: boolean },
  ): Promise<SayimKalemi> => api.patch<SayimKalemi>(`${SAYIM}${id}/items/${kalemId}/`, govde),

  fazlaCikar: (id: number, kalemId: number): Promise<void> =>
    api.del<void>(`${SAYIM}${id}/items/${kalemId}/`),

  ilerleme: (id: number): Promise<SayimIlerlemesi> =>
    api.get<SayimIlerlemesi>(`${SAYIM}${id}/progress/`),

  tamamla: (id: number): Promise<TamamlamaYaniti> =>
    api.post<TamamlamaYaniti>(`${SAYIM}${id}/complete/`),

  onayla: (id: number, govde: OnayGovdesi): Promise<OnayYaniti> =>
    api.post<OnayYaniti>(`${SAYIM}${id}/approve/`, govde),

  iptalEt: (id: number, reason = ""): Promise<SayimAyrintisi> =>
    api.post<SayimAyrintisi>(`${SAYIM}${id}/cancel/`, { reason }),

  belgeler: (id: number): Promise<SayimBelgesi[]> =>
    api.get<SayimBelgesi[]>(`${SAYIM}${id}/documents/`),

  belge: (id: number, tur: string, bicim: "pdf" | "xlsx" = "pdf"): Promise<Blob> =>
    api.getBlob(
      bicim === "pdf"
        ? `${SAYIM}${id}/documents/${tur}/`
        : `${SAYIM}${id}/documents/${tur}/?kind=${bicim}`,
    ),
};
