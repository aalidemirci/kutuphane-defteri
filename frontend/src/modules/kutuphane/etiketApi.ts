// Etiket uçlarının istemcisi (F4) — backend `apps/kutuphane/labels/{serializers,views}.py`
// (etiket motoru: şablon, yazıcı kalibrasyonu, kalibrasyon sayfası) ve
// `serializers_kuyruk.py` + `views_kuyruk.py` (basım kuyruğu, basım partisi,
// doğrulama okutması, boş barkod aralığı) ile BİREBİR. Katalog istemcisi
// (`api.ts`) zaten büyük olduğu için etiket yüzeyi bu dosyadadır.
//
// Üç sözleşme notu:
//   * **PDF üretmek "basıldı" DEĞİLDİR** (tasarım D10). Parti "basım onayı
//     bekliyor" hâlinde açılır; PDF'i istenildiği kadar yeniden alınır; işaret
//     yalnız `partiOnayla` ("Basıldı olarak işaretle") ile yazılır ve
//     `partiGeriAl` ile geri alınır. Boş barkod aralığında da aynı kural geçerlidir.
//   * Başlangıç hücresi **1'den başlar** ve satır satır, soldan sağa sayılır
//     (kullanıcının gördüğü "1. hücre").
//   * Ölçüler JSON'da SAYIDIR (mm, iki ondalık); ön yüz tabaka ızgarasını
//     (başlangıç hücresi seçici) bu sayılarla çizer.
//
// Görevli kipi izin listesinde yalnız `dogrula` (doğrulama okutması; kullanıcı
// kararı 24.09.2026) vardır; öbür uçlar görevli kipinde 403 `kip_yetkisiz` döner
// (`lib/api.ts` olayı yayınlar). Yanıtlar kişisel veri taşımaz: nüsha özeti
// (barkod, kaynak adı, yer numarası, bölüm) ve sayaçlar.

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";
import type { CopyBody, Copy } from "./api";

// ---------------------------------------------------------------------------
// Kod listeleri (backend TextChoices ile birebir) ve Türkçe adları
// ---------------------------------------------------------------------------

/** Basım partisinin içeriği — backend `LabelPrintKind`. */
export type EtiketIcerigi = "SPINE" | "BARCODE" | "BOTH";

/**
 * İçerik adları (docs/sozluk.md). Sıra seçicideki sıradır: varsayılan "ikisi
 * birden" başta durur — önce liste yolunda raf raf yapıştırılan iki etikettir.
 */
export const ETIKET_ICERIGI_TR: Record<EtiketIcerigi, string> = {
  BOTH: "Sırt ve barkod etiketi",
  BARCODE: "Barkod etiketi",
  SPINE: "Sırt etiketi",
};

/** Basım sırası — backend `LabelOrder` (D20: seçilebilir, varsayılan yer numarası). */
export type BasimSirasi = "CALL_NUMBER" | "IMPORT_ROW" | "BARCODE";

export const BASIM_SIRASI_TR: Record<BasimSirasi, string> = {
  CALL_NUMBER: "Yer numarası",
  IMPORT_ROW: "İçe aktarma sırası",
  BARCODE: "Barkod",
};

/** Basım partisinin durumu — backend `LabelPrintBatchStatus` (türetilir, alan değil). */
export type PartiDurumu = "PENDING" | "CONFIRMED" | "REVERTED" | "DISCARDED";

export const PARTI_DURUMU_TR: Record<PartiDurumu, string> = {
  PENDING: "Basım onayı bekliyor",
  CONFIRMED: "Basıldı",
  REVERTED: "Basım işareti geri alındı",
  DISCARDED: "Vazgeçildi",
};

/** Etiket şablonunun türü — backend `LabelKind` (kart şablonu bu ekranda yoktur). */
export type SablonTuru = "BARCODE" | "SPINE";

export const SABLON_TURU_TR: Record<SablonTuru, string> = {
  BARCODE: "Barkod etiketi",
  SPINE: "Sırt etiketi",
};

/** Ayrılmış numaranın durumu — backend `ReservedBarcodeState`. */
export type AyrilmisNumaraDurumu = "OPEN" | "BOUND" | "CANCELLED";

/** Doğrulama okutmasının sonucu. */
export type DogrulamaSonucuTuru = "verified" | "already_verified" | "rejected";

/**
 * Bir basım işine girebilecek en çok etiket (backend `MAX_LABELS_PER_JOB`:
 * 20 tabaka × 65). Kuyruktan basımda seçilen sıradaki ilk bu kadar nüsha alınır.
 */
export const EN_COK_ETIKET = 1300;

/** Kalibrasyon kaymasının sınırı (mm, backend `MAX_OFFSET_MM`). */
export const EN_COK_KAYMA_MM = 10;

/** Etiket listelerinin sayfa boyutu (backend `KatalogSayfalama.default_limit`). */
export const ETIKET_SAYFA_BOYUTU = 25;

/** Seçicileri dolduran listelerin üst sınırı (sunucunun `max_limit`'i). */
const LISTE_SINIRI = 200;

// ---------------------------------------------------------------------------
// Belge adları ve indirme adları (docs/sozluk.md §2 E1, §3)
// ---------------------------------------------------------------------------

/** Basım içeriğinin belge adı — backend `labels.render.DOCUMENT_NAMES` ile aynı. */
export const ETIKET_BELGE_ADI: Record<EtiketIcerigi, string> = {
  SPINE: "Sırt Etiketi",
  BARCODE: "Barkod Etiketi",
  BOTH: "Sırt ve Barkod Etiketi",
};

export const BOS_BARKOD_BELGE_ADI = "Boş Barkod Etiketi";
export const KALIBRASYON_BELGE_ADI = "Kalibrasyon Sayfası";

/** İndirilen etiket PDF'inin adı: belge adı + YEREL tarih (`todayIso`, UTC değil). */
export function etiketDosyaAdi(icerik: EtiketIcerigi): string {
  return dosyaAdi([ETIKET_BELGE_ADI[icerik], formatDate(todayIso())], "pdf");
}

/** Boş barkod etiketlerinin adı: belge adı + numara aralığı (kapsam) + tarih. */
export function bosBarkodDosyaAdi(aralik: {
  first_barcode_display: string;
  last_barcode_display: string;
}): string {
  return dosyaAdi(
    [
      BOS_BARKOD_BELGE_ADI,
      aralik.first_barcode_display,
      aralik.last_barcode_display,
      formatDate(todayIso()),
    ],
    "pdf",
  );
}

/** Kalibrasyon sayfasının adı. */
export function kalibrasyonDosyaAdi(): string {
  return dosyaAdi([KALIBRASYON_BELGE_ADI, formatDate(todayIso())], "pdf");
}

// ---------------------------------------------------------------------------
// Kayıt tipleri (serializer alanlarıyla birebir)
// ---------------------------------------------------------------------------

/** Etiket şablonu (tabaka ölçüsü). Ölçüler mm ve SAYIDIR. */
export interface EtiketSablonu {
  id: number;
  name: string;
  kind: SablonTuru;
  kind_display: string;
  page_margin_top: number;
  page_margin_left: number;
  label_width: number;
  label_height: number;
  rows: number;
  cols: number;
  gutter_x: number;
  gutter_y: number;
  corner_radius: number;
  is_default: boolean;
  /** Türetilir: satır × sütun. */
  labels_per_sheet: number;
  /** Barkodun yanında QR'a yer var mı (48,5 × 25,4 mm ve üstü)? */
  supports_qr: boolean;
  /** Barkod (sessiz bölgelerle 27,94 mm) ve metin satırları sığıyor mu? */
  supports_barcode: boolean;
  updated_at: string;
}

/** Şablon yazma gövdesi (türetilen alanlar gönderilmez). */
export interface EtiketSablonuGovdesi {
  name: string;
  kind: SablonTuru;
  page_margin_top: number;
  page_margin_left: number;
  label_width: number;
  label_height: number;
  rows: number;
  cols: number;
  gutter_x: number;
  gutter_y: number;
  corner_radius?: number;
  is_default: boolean;
}

/** Yazıcı kalibrasyonu (şablon × yazıcı). Pozitif X sağa, pozitif Y aşağı kaydırır. */
export interface YaziciKalibrasyonu {
  id: number;
  template: number;
  template_name: string;
  printer_name: string;
  offset_x: number;
  offset_y: number;
  updated_at: string;
}

export interface YaziciKalibrasyonuGovdesi {
  template: number;
  printer_name: string;
  offset_x: number;
  offset_y: number;
}

/** Kuyruk ve doğrulanmamışlar listesinin satırı — nüsha özeti + işaretler. */
export interface KuyrukNushasi {
  id: number;
  work: number;
  work_title: string;
  work_authors: string;
  call_number: string;
  acquisition: number;
  accession_no: number;
  barcode: string;
  barcode_display: string;
  section: number | null;
  section_name: string | null;
  /** BARKOD etiketinin onaylı basım işareti. */
  label_printed_at: string | null;
  label_verified_at: string | null;
  /** SIRT etiketinin onaylı basım işareti. */
  spine_label_printed_at: string | null;
  /** Nüsha onay bekleyen bir partideyse o partinin kimliği (PDF'i alınmış olabilir). */
  pending_batch: number | null;
  created_at: string;
}

/** Basım geçmişinin satırı. */
export interface BasimPartisi {
  id: number;
  kind: EtiketIcerigi;
  kind_display: string;
  template: number;
  template_name: string;
  calibration: number | null;
  printer_name: string | null;
  spine_template: number | null;
  spine_calibration: number | null;
  include_qr: boolean;
  order: BasimSirasi;
  order_display: string;
  start_cell: number;
  copy_count: number;
  status: PartiDurumu;
  status_display: string;
  created_at: string;
  confirmed_at: string | null;
  reverted_at: string | null;
  discarded_at: string | null;
  reprint_of: number | null;
}

/** Partinin nüshası — basım sırasında (`position` 1'den başlar). */
export interface PartiKalemi extends KuyrukNushasi {
  position: number;
  /**
   * `false`: nüsha parti açıldıktan sonra silinmiş ya da elden çıkmış. Partinin
   * PDF'inde hücresi boş kalır, onay işaretine dokunmaz, yeniden basım onu almaz.
   */
  printable: boolean;
}

export interface BasimPartisiAyrintisi extends BasimPartisi {
  items: PartiKalemi[];
}

/** Kuyruk süzgeçleri (kuyruk ucu ve "kuyruktan bas" gövdesi aynı adları taşır). */
export interface KuyrukSuzgeci {
  section?: number | null;
  acquisition?: number | null;
  reservation?: number | null;
  /** Nüshanın kayıt (açılış) günü — yerel gün, ISO `yyyy-mm-dd`. */
  created_from?: string | null;
  created_to?: string | null;
}

export interface KuyrukParametreleri extends KuyrukSuzgeci {
  kind?: EtiketIcerigi;
  order?: BasimSirasi;
  limit?: number;
  offset?: number;
}

/** Basım ayarı: şablon, yazıcı, başlangıç hücresi, QR ve (yalnız "ikisi birden") ayrı sırt tabakası. */
export interface BasimAyariGovdesi {
  template: number;
  calibration?: number | null;
  spine_template?: number | null;
  spine_calibration?: number | null;
  include_qr?: boolean;
  start_cell?: number;
}

/** Parti açma gövdesi — nüshalar ya AÇIKÇA (`copies`) ya KUYRUKTAN (`from_queue`). */
export interface PartiAcmaGovdesi extends BasimAyariGovdesi, KuyrukSuzgeci {
  kind: EtiketIcerigi;
  order?: BasimSirasi;
  copies?: number[];
  from_queue?: boolean;
  limit?: number;
}

/** Yeniden basım gövdesi — verilmeyen ayar eski partiden alınır. */
export interface YenidenBasimGovdesi {
  kind?: EtiketIcerigi;
  template?: number;
  calibration?: number | null;
  start_cell?: number;
}

/**
 * `POST …/revert/` yanıtı. `restored`: işareti bu basımdan önceki hâline dönen
 * nüsha; `requeued`: bunlardan kuyruğa DÖNEN (yeniden basım partisinde nüshalar
 * önceki basımın işaretine döner, kuyruğa girmez); `kept_verified`: barkodu
 * okutularak doğrulandığı için işaretlerine dokunulmayan nüsha (sırt ve barkod
 * partisinde iki işaret de korunur; bu nüshalar `restored`'a ve `requeued`'a girmez).
 */
export interface GeriAlmaSonucu {
  batch: BasimPartisi;
  restored: number;
  requeued: number;
  kept_verified: number;
}

/** `GET library/labels/summary/` — kişisiz sayaçlar. */
export interface EtiketOzeti {
  queue: Record<EtiketIcerigi, number>;
  unverified: number;
  pending_batches: number;
  reservations: { reserved: number; bound: number; cancelled: number; open: number };
}

/**
 * Doğrulama okutmasında gösterilen nüsha özeti. Görevli kipinde sunucu yalnız
 * barkodu ve eser adını döndürür (`label_queue.STAFF_COPY_FIELDS`); öbür alanlar
 * yalnız yönetici kipinde gelir, bu yüzden isteğe bağlıdır.
 */
export interface TaramaNushasi {
  barcode: string;
  barcode_display: string;
  work_title: string;
  id?: number;
  call_number?: string;
  label_printed_at?: string | null;
  label_verified_at?: string | null;
}

/** `POST library/labels/verify/` — HER ZAMAN 200: okutma bir olaydır, hata değil. */
export interface DogrulamaSonucu {
  result: DogrulamaSonucuTuru;
  /** Okutulan kodun türü (backend `ScanKind`). */
  kind: string;
  message: string;
  copy: TaramaNushasi | null;
}

/** Boş barkod aralığı + numara durum sayaçları. */
export interface BosBarkodAraligi {
  id: number;
  year: number;
  first_barcode: string;
  first_barcode_display: string;
  last_barcode: string;
  last_barcode_display: string;
  count: number;
  note: string;
  /** Boş etiketlerin onaylı basım işareti (D10 kuralı burada da geçerli). */
  printed_at: string | null;
  open_count: number;
  bound_count: number;
  cancelled_count: number;
  created_at: string;
}

/** Aralıktaki tek numara. */
export interface AyrilmisNumara {
  barcode: string;
  barcode_display: string;
  state: AyrilmisNumaraDurumu;
  state_display: string;
  copy: number | null;
  work_title: string;
  bound_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string;
}

export interface BosBarkodAraligiAyrintisi extends BosBarkodAraligi {
  numbers: AyrilmisNumara[];
}

/** Boş etiket PDF'inin parametreleri (`barcodes`: yalnız bozulan etiketlerin yeniden basımı). */
export interface BosBarkodPdfParametreleri {
  template: number;
  calibration?: number | null;
  start_cell?: number;
  include_qr?: boolean;
  barcodes?: string[];
}

/** `POST …/cancel/` yanıtı. */
export interface IptalSonucu {
  cancelled: number;
  reservation: BosBarkodAraligiAyrintisi;
}

/** `GET library/barcode-reservations/check/?code=` — hızlı kayıt ön denetimi (yazma yok). */
export interface EtiketDenetimi {
  bindable: boolean;
  kind: string;
  barcode: string;
  barcode_display: string;
  reservation: number | null;
  copy: number | null;
  work_title: string;
  /** Bağlanabiliyorsa "Etiket boş; …", değilse Türkçe gerekçe. */
  message: string;
  /**
   * Ret varsa "Etiket yok — yeni numara ver" yolunu hatırlatır; numara başka bir
   * nüshaya bağlıysa boştur (kitap zaten kayıtlı olabilir).
   */
  hint: string;
}

/** `POST library/copies/from-label/` gövdesi: nüsha alanları + kitaptaki etiketin kodu. */
export interface EtiketliNushaGovdesi extends CopyBody {
  label_code: string;
}

// ---------------------------------------------------------------------------
// Sorgu dizesi yardımcıları
// ---------------------------------------------------------------------------

function withQuery(path: string, parts: string[]): string {
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

function sayfaParcalari(params: { limit?: number; offset?: number }): string[] {
  const parts: string[] = [];
  if (params.limit !== undefined) parts.push(`limit=${params.limit}`);
  if (params.offset) parts.push(`offset=${params.offset}`);
  return parts;
}

function suzgecParcalari(suzgec: KuyrukSuzgeci): string[] {
  const parts: string[] = [];
  if (suzgec.section) parts.push(`section=${suzgec.section}`);
  if (suzgec.acquisition) parts.push(`acquisition=${suzgec.acquisition}`);
  if (suzgec.reservation) parts.push(`reservation=${suzgec.reservation}`);
  if (suzgec.created_from) parts.push(`created_from=${encodeURIComponent(suzgec.created_from)}`);
  if (suzgec.created_to) parts.push(`created_to=${encodeURIComponent(suzgec.created_to)}`);
  return parts;
}

// ---------------------------------------------------------------------------
// İstemci
// ---------------------------------------------------------------------------

export const etiketApi = {
  // --- Şablonlar (ilk liste isteği hazır şablonları yazar) ---

  sablonlar: (kind?: SablonTuru): Promise<Paginated<EtiketSablonu>> => {
    const parts = [`limit=${LISTE_SINIRI}`];
    if (kind) parts.push(`kind=${kind}`);
    return api.get<Paginated<EtiketSablonu>>(withQuery("/library/label-templates/", parts));
  },

  sablonOlustur: (govde: EtiketSablonuGovdesi): Promise<EtiketSablonu> =>
    api.post<EtiketSablonu>("/library/label-templates/", govde),

  sablonGuncelle: (id: number, govde: Partial<EtiketSablonuGovdesi>): Promise<EtiketSablonu> =>
    api.patch<EtiketSablonu>(`/library/label-templates/${id}/`, govde),

  /** Silme yumuşaktır; şablonun kalibrasyonları da silinir. */
  sablonSil: (id: number): Promise<void> => api.del<void>(`/library/label-templates/${id}/`),

  // --- Yazıcı kalibrasyonları ---

  kalibrasyonlar: (template?: number): Promise<Paginated<YaziciKalibrasyonu>> => {
    const parts = [`limit=${LISTE_SINIRI}`];
    if (template) parts.push(`template=${template}`);
    return api.get<Paginated<YaziciKalibrasyonu>>(withQuery("/library/label-calibrations/", parts));
  },

  kalibrasyonOlustur: (govde: YaziciKalibrasyonuGovdesi): Promise<YaziciKalibrasyonu> =>
    api.post<YaziciKalibrasyonu>("/library/label-calibrations/", govde),

  kalibrasyonGuncelle: (
    id: number,
    govde: Partial<YaziciKalibrasyonuGovdesi>,
  ): Promise<YaziciKalibrasyonu> =>
    api.patch<YaziciKalibrasyonu>(`/library/label-calibrations/${id}/`, govde),

  kalibrasyonSil: (id: number): Promise<void> =>
    api.del<void>(`/library/label-calibrations/${id}/`),

  /** Kalibrasyon sayfası PDF'i — seçilen yazıcının O ANKİ kaymasıyla basılır. */
  kalibrasyonSayfasi: (template: number, calibration?: number | null): Promise<Blob> =>
    api.postBlob("/library/labels/calibration/", {
      template,
      calibration: calibration ?? null,
    }),

  // --- Kuyruk, özet, doğrulama ---

  kuyruk: (params: KuyrukParametreleri = {}): Promise<Paginated<KuyrukNushasi>> => {
    const parts = sayfaParcalari(params);
    if (params.kind) parts.push(`kind=${params.kind}`);
    if (params.order) parts.push(`order=${params.order}`);
    parts.push(...suzgecParcalari(params));
    return api.get<Paginated<KuyrukNushasi>>(withQuery("/library/labels/queue/", parts));
  },

  dogrulanmamislar: (params: KuyrukParametreleri = {}): Promise<Paginated<KuyrukNushasi>> => {
    const parts = sayfaParcalari(params);
    if (params.order) parts.push(`order=${params.order}`);
    parts.push(...suzgecParcalari(params));
    return api.get<Paginated<KuyrukNushasi>>(withQuery("/library/labels/unverified/", parts));
  },

  /** Sayaçlar — sayfa açılışında okunur; kullanıcı eylemi değildir (boşta sayacını tazelemez). */
  ozet: (): Promise<EtiketOzeti> =>
    api.get<EtiketOzeti>("/library/labels/summary/", { etkinlik: false }),

  /** Doğrulama okutması — yanıt HER ZAMAN 200 gövdedir (`result`). */
  dogrula: (code: string): Promise<DogrulamaSonucu> =>
    api.post<DogrulamaSonucu>("/library/labels/verify/", { code }),

  // --- Basım partileri ---

  partiler: (
    params: { status?: PartiDurumu | ""; limit?: number; offset?: number } = {},
  ): Promise<Paginated<BasimPartisi>> => {
    const parts = sayfaParcalari(params);
    if (params.status) parts.push(`status=${params.status}`);
    return api.get<Paginated<BasimPartisi>>(withQuery("/library/labels/batches/", parts));
  },

  /** Parti açar ("basım onayı bekliyor"); işaretlere DOKUNMAZ. */
  partiAc: (govde: PartiAcmaGovdesi): Promise<BasimPartisiAyrintisi> =>
    api.post<BasimPartisiAyrintisi>("/library/labels/batches/", govde),

  parti: (id: number): Promise<BasimPartisiAyrintisi> =>
    api.get<BasimPartisiAyrintisi>(`/library/labels/batches/${id}/`),

  /** Partinin PDF'i — istenildiği kadar yeniden alınır, işarete DOKUNMAZ. */
  partiPdf: (id: number): Promise<Blob> => api.getBlob(`/library/labels/batches/${id}/pdf/`),

  /** "Basıldı olarak işaretle". */
  partiOnayla: (id: number): Promise<BasimPartisi> =>
    api.post<BasimPartisi>(`/library/labels/batches/${id}/confirm/`, {}),

  /** Basım işaretini geri alır (parti iz olarak kalır). */
  partiGeriAl: (id: number): Promise<GeriAlmaSonucu> =>
    api.post<GeriAlmaSonucu>(`/library/labels/batches/${id}/revert/`, {}),

  /** Onaylanmamış partiden vazgeçer. */
  partidenVazgec: (id: number): Promise<BasimPartisi> =>
    api.post<BasimPartisi>(`/library/labels/batches/${id}/discard/`, {}),

  /** Aynı nüshalar, aynı sıra, yeni parti. */
  yenidenBas: (id: number, govde: YenidenBasimGovdesi = {}): Promise<BasimPartisiAyrintisi> =>
    api.post<BasimPartisiAyrintisi>(`/library/labels/batches/${id}/reprint/`, govde),

  // --- Boş barkod aralıkları (önce etiket yolu) ---

  araliklar: (
    params: { limit?: number; offset?: number } = {},
  ): Promise<Paginated<BosBarkodAraligi>> =>
    api.get<Paginated<BosBarkodAraligi>>(
      withQuery("/library/barcode-reservations/", sayfaParcalari(params)),
    ),

  /** Numara ayırır — sayaçtan alınan numaralar başka nüshaya ASLA verilmez. */
  aralikAyir: (count: number, note = ""): Promise<BosBarkodAraligiAyrintisi> =>
    api.post<BosBarkodAraligiAyrintisi>("/library/barcode-reservations/", { count, note }),

  aralik: (id: number): Promise<BosBarkodAraligiAyrintisi> =>
    api.get<BosBarkodAraligiAyrintisi>(`/library/barcode-reservations/${id}/`),

  /** Aralığın boş barkod etiketleri — işarete DOKUNMAZ. */
  aralikPdf: (id: number, params: BosBarkodPdfParametreleri): Promise<Blob> => {
    const parts = [`template=${params.template}`];
    if (params.calibration) parts.push(`calibration=${params.calibration}`);
    parts.push(`start_cell=${params.start_cell ?? 1}`);
    parts.push(`include_qr=${params.include_qr ? "true" : "false"}`);
    if (params.barcodes && params.barcodes.length > 0) {
      parts.push(`barcodes=${encodeURIComponent(params.barcodes.join(","))}`);
    }
    return api.getBlob(withQuery(`/library/barcode-reservations/${id}/pdf/`, parts));
  },

  aralikBasildi: (id: number): Promise<BosBarkodAraligi> =>
    api.post<BosBarkodAraligi>(`/library/barcode-reservations/${id}/confirm-print/`, {}),

  aralikBasimGeriAl: (id: number): Promise<BosBarkodAraligi> =>
    api.post<BosBarkodAraligi>(`/library/barcode-reservations/${id}/revert-print/`, {}),

  /** Kullanılmayan numaraları iptal eder (`barcodes` yoksa bütün açık numaralar). GERİ ALINMAZ. */
  aralikIptal: (
    id: number,
    govde: { barcodes?: string[]; reason?: string },
  ): Promise<IptalSonucu> =>
    api.post<IptalSonucu>(`/library/barcode-reservations/${id}/cancel/`, govde),

  // --- Hızlı kayıtta bağlama ---

  /** Okutulan etiket bağlanabilir mi? (yazma YOK — eser açılmadan ÖNCE sorulur) */
  etiketDenetle: (code: string): Promise<EtiketDenetimi> =>
    api.get<EtiketDenetimi>(
      `/library/barcode-reservations/check/?code=${encodeURIComponent(code)}`,
    ),

  /** Nüshayı kitaptaki önceden basılmış etiketin numarasıyla açar. */
  etiketleNushaAc: (govde: EtiketliNushaGovdesi): Promise<Copy> =>
    api.post<Copy>("/library/copies/from-label/", govde),
};
