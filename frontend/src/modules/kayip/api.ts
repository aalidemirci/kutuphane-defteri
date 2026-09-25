// `kayip` modülü API istemcisi — kayıp ve hasar dosyaları (Md. 19) ve onarım (D3).
// Backend `apps/kutuphane/views_teslim.py` ve `serializers_teslim.py` ile BİREBİR.
//
// Bütün uçlar YALNIZ yönetici kipindedir (§4.4 "kayıp dosyaları" görevliye kapalı).
// Dosya kişiye bağlıdır: sorumlunun adı ve sorumlu notu sunucuda şifrelidir;
// parola kurulmadan dosya açılamaz (409 `parola_gerekli`).
//
// Md. 19 kademe kapısı SUNUCUDADIR: bedel yolları yalnız ortaöğretimde açılır ve
// dosyanın `allowed_resolutions` alanı o kapının yansımasıdır. Ekran çözüm
// düğmelerini YALNIZ o listeden kurar; kademe bilgisini kendisi yorumlamaz.
// Program tahsilat yapmaz: bedel yalnız kaydedilir. Bedel iki adımdır (25.09.2026
// kullanıcı kararı): "Bedel belirlendi" (kişinin açık işi sürer) → "Bedel teslim
// alındı" (kişinin açık işi biter; dosya okul için açık kalır). Sözlük: asla borç,
// ceza ya da tahsilat.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";
import type { CopyStatus } from "../kutuphane/api";

/** Dosya türü — backend `CaseType` (sözlük: kayıp, hasar — "zayi", "telef" değil). */
export type DosyaTuru = "LOST" | "DAMAGED";

export const DOSYA_TURU_TR: Record<DosyaTuru, string> = {
  LOST: "Kayıp",
  DAMAGED: "Hasar",
};

/** Dosyanın çözüm durumu — backend `CaseResolution`. */
export type Cozum =
  | "PENDING"
  | "PRICE_DETERMINED"
  | "PRICE_RECEIVED"
  | "FOUND_RETURNED"
  | "REPLACED_SAME"
  | "REPAIRED"
  | "CLOSED_SAME_REPURCHASED"
  | "CLOSED_OTHER_REPURCHASED"
  | "FOUND_AFTER_PRICE"
  | "WRITE_OFF_PROPOSED"
  | "CONVERTED_TO_LOSS";

export const COZUM_TR: Record<Cozum, string> = {
  PENDING: "Çözüm bekliyor",
  PRICE_DETERMINED: "Bedel belirlendi",
  PRICE_RECEIVED: "Bedel teslim alındı",
  FOUND_RETURNED: "Bulundu",
  REPLACED_SAME: "Aynısı temin edildi",
  REPAIRED: "Onarıldı",
  CLOSED_SAME_REPURCHASED: "Bedelle aynısı alındı",
  CLOSED_OTHER_REPURCHASED: "Bedelle başka eser alındı",
  // Bedeli teslim alınmış KAYIP dosyasında kitabın bulunması (25.09.2026 kullanıcı kararı):
  // nüsha rafa döner, bedel kaydı kalır; bedelin iadesi okul yönetiminin kararıdır.
  FOUND_AFTER_PRICE: "Bulundu (bedel teslim alınmıştı)",
  WRITE_OFF_PROPOSED: "Kayıttan düşme önerildi",
  // Kullanıcının seçtiği bir çözüm DEĞİLDİR: açık hasar dosyalı nüsha kaybolunca kayıp
  // bildirimi hasar dosyasını bununla kapatır (yalnız hasarda).
  CONVERTED_TO_LOSS: "Kayba dönüştü",
};

/** Bedel yolları (backend `PRICE_RESOLUTIONS`) — yalnız ortaöğretimde. */
export const BEDEL_YOLLARI: ReadonlySet<Cozum> = new Set<Cozum>([
  "PRICE_DETERMINED",
  "PRICE_RECEIVED",
  "CLOSED_SAME_REPURCHASED",
  "CLOSED_OTHER_REPURCHASED",
  "FOUND_AFTER_PRICE",
]);

/** Piyasa bedeli YALNIZ bu adımda sorulur (teslim alınan bedel sonradan değişmez). */
export const BEDEL_SORULAN: Cozum = "PRICE_DETERMINED";

/** Dosyayı AÇIK bırakan çözümler (backend `OPEN_CASE_RESOLUTIONS`) — okulun açık işi. */
export const ACIK_COZUMLER: ReadonlySet<Cozum> = new Set<Cozum>([
  "PENDING",
  "PRICE_DETERMINED",
  "PRICE_RECEIVED",
]);

/**
 * KİŞİNİN açık işi sayılan çözümler (backend `PERSON_OPEN_RESOLUTIONS`): "Bedel teslim
 * alındı" dosyası açıktır ama kişiye yazılmaz (ilişik listesi, E5).
 */
export const KISI_ACIK_COZUMLER: ReadonlySet<Cozum> = new Set<Cozum>([
  "PENDING",
  "PRICE_DETERMINED",
]);

/** Sorumlu notunun yardım metni (backend `RESPONSIBLE_NOTE_HELP` ile aynı uyarı). */
export const SORUMLU_NOTU_YARDIMI =
  "Üye olmayan sorumlu ya da kısa açıklama. Sağlık ya da aile bilgisi yazmayın.";

/** Kayıp/hasar dosyası (yönetici kipi) — `CASE_FIELDS`. */
export interface Dosya {
  id: number;
  copy: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  copy_status: CopyStatus;
  copy_status_display: string;
  case_type: DosyaTuru;
  case_type_display: string;
  membership: number | null;
  loan: number | null;
  delivery: number | null;
  /** Sorumlu üyenin adı (şifreli alandan çözülür); sorumlu yoksa boş. */
  responsible_name: string;
  responsible_class_label: string;
  responsible_note: string;
  reported_on: string;
  /** Piyasa bedeli — YALNIZ KAYIT (DRF ondalığı metin gönderir: "125.50"). */
  market_price: string | null;
  /** "Bedel belirlendi" adımının zamanı (bedel düzeltilince yenilenir). */
  price_determined_at: string | null;
  /** "Bedel teslim alındı" adımının zamanı — yalnız kayıt; program tahsilat yapmaz. */
  price_received_at: string | null;
  resolution: Cozum;
  resolution_display: string;
  /** Dosya açık mı (okulun açık işi)? */
  is_open: boolean;
  /** Dosya kişinin açık işi mi? "Bedel teslim alındı"da hayır (dosya açık kalsa da). */
  is_person_open_work: boolean;
  resolved_at: string | null;
  write_off_proposed_at: string | null;
  /** Şu an seçilebilecek çözümler (Md. 19 kademe kapısının yansıması). */
  allowed_resolutions: Array<{ value: Cozum; label: string }>;
  /** Okulda bedel seçenekleri sunuluyor mu? (yalnız ortaöğretim) */
  price_options_available: boolean;
  created_at: string;
}

/**
 * Dosya listesinin sayfası. `price_options_available` Md. 19 kademe kapısının
 * yansımasıdır (liste boşken de gelir): "Çözüm" süzgecindeki bedel yolları buna göre
 * kurulur.
 */
export type DosyaSayfasi = Paginated<Dosya> & { price_options_available: boolean };

/** `POST library/loss-damage-cases/` — kayıp bildirimi ya da hasar dosyası açma. */
export interface DosyaGovdesi {
  case_type: DosyaTuru;
  /** Nüsha `copy_id` YA DA okutulan `barcode` ile gelir. */
  copy_id?: number;
  barcode?: string;
  loan_id?: number;
  delivery_id?: number;
  /** Sorumlu üye (ödünç ya da teslim yoksa; ödünçteki kitapta sorumlu ödünçten gelir). */
  membership_id?: number;
  responsible_note?: string;
  reported_on?: string;
  /** Yalnız hasarda: raftaki nüsha aynı işlemde onarıma gönderilir. */
  send_to_repair?: boolean;
}

export interface CozumGovdesi {
  resolution: Cozum;
  /** Yalnız "Bedel belirlendi"de; metin olarak gönderilir ("125.50"). */
  market_price?: string | null;
}

/** Onarım kaydı (kişisiz). */
export interface OnarimKaydi {
  id: number;
  copy: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  case: number | null;
  sent_on: string;
  returned_on: string | null;
}

export interface OnarimSonucu {
  message: string;
  /** Kaydı olmayan (eski veriden gelen) "Onarımda" nüshada boştur. */
  repair: OnarimKaydi | null;
}

export interface DosyaListeParametreleri {
  resolution?: Cozum | "";
  caseType?: DosyaTuru | "";
  /** Yalnız çözülmemiş dosyalar. */
  open?: boolean;
  copy?: number | null;
  limit?: number;
  offset?: number;
}

/** Evrak adı (docs/sozluk.md §2 — E6). */
export const TUTANAK_ADI = "Kayıp/hasar tutanağı";

/** Dosya listesinin sayfa boyutu. */
export const DOSYA_SAYFA_BOYUTU = 25;

function withQuery(path: string, parts: string[]): string {
  return parts.length ? `${path}?${parts.join("&")}` : path;
}

function listeParcalari(p: DosyaListeParametreleri): string[] {
  const parts: string[] = [];
  if (p.resolution) parts.push(`resolution=${p.resolution}`);
  if (p.caseType) parts.push(`case_type=${p.caseType}`);
  if (p.open) parts.push("open=1");
  if (p.copy) parts.push(`copy=${p.copy}`);
  if (p.limit !== undefined) parts.push(`limit=${p.limit}`);
  if (p.offset) parts.push(`offset=${p.offset}`);
  return parts;
}

export const kayipApi = {
  listele: (params: DosyaListeParametreleri = {}): Promise<DosyaSayfasi> =>
    api.get<DosyaSayfasi>(withQuery("/library/loss-damage-cases/", listeParcalari(params))),

  /**
   * Dosya açar. Kayıpta ödünçteki nüshanın ödüncü, teslimdeki nüshanın teslimi
   * "Kayba dönüştü" ile kapanır ve nüsha "Kayıp" olur.
   */
  ac: (govde: DosyaGovdesi): Promise<Dosya> =>
    api.post<Dosya>("/library/loss-damage-cases/", govde),

  getir: (id: number): Promise<Dosya> => api.get<Dosya>(`/library/loss-damage-cases/${id}/`),

  /** Yalnız açık dosyada: sorumlu notu (şifreli alan). */
  notuGuncelle: (id: number, responsibleNote: string): Promise<Dosya> =>
    api.patch<Dosya>(`/library/loss-damage-cases/${id}/`, { responsible_note: responsibleNote }),

  /**
   * Çözüm işler. Bedel yolları ilkokul ve ortaokulda 400 alır (Md. 19). Kapanmış
   * dosyada yalnız öneri geri alınır (öneriyle kapanmış kayıp dosyasında nüsha hâlâ
   * "Kayıp"sa "Bulundu" ya da "Bulundu (bedel teslim alınmıştı)" — `allowed_resolutions`
   * söyler). "Bedel teslim alındı" dosyası "Bedelle aynısı alındı", "Bedelle başka eser
   * alındı" ya da (kayıpta) "Bulundu (bedel teslim alınmıştı)" ile kapanır.
   */
  coz: (id: number, govde: CozumGovdesi): Promise<Dosya> =>
    api.post<Dosya>(`/library/loss-damage-cases/${id}/resolve/`, govde),

  /** "Rafta" → "Onarımda" (nüshanın çözülmemiş hasar dosyası varsa kayda bağlanır). */
  onarimaGonder: (copyId: number): Promise<OnarimSonucu> =>
    api.post<OnarimSonucu>(`/library/copies/${copyId}/send-to-repair/`, {}),

  /** "Onarımda" → "Rafta". Hasar dosyasını kendiliğinden kapatmaz ("Onarıldı" ayrıca seçilir). */
  onarimdanDon: (copyId: number): Promise<OnarimSonucu> =>
    api.post<OnarimSonucu>(`/library/copies/${copyId}/return-from-repair/`, {}),

  /** E6 Kayıp/hasar tutanağı (kayıt yazmaz). */
  tutanakPdf: (id: number): Promise<Blob> => api.getBlob(`/library/loss-damage-cases/${id}/pdf/`),
};
