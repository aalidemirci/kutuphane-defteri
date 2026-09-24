// `dolasim` modülü API istemcisi — dolaşım masası (tasarım §7.3, §4.4).
// Backend `apps/kutuphane/views_masa.py` ve `serializers_masa.py` ile BİREBİR.
//
// Görevli kipinde yanıtlar DARALIR: kartla üye çözmede yalnız ad + kalan hak,
// iadede ödünç alanın kimliği ve gecikme günü yok, nüsha özetinde barkod ve kaynak
// adı. Yönetici kipindeki ek alanlar bu yüzden `?` ile işaretlidir; ekran bir alanın
// yokluğunu "görevli kipi" diye okumaz, kipi `gorevli` prop'undan bilir.
//
// Kart no URL'ye yazılmaz (POST gövdesi). Görevli kipinde `membership_id`,
// `override_*` ve `cardless_reason` HİÇ gönderilmez: ara katman bu alanları taşıyan
// isteği (değeri boş olsa da) 403 ile keser.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";

/** Kart okutmasının sonucu (backend `CardLookupState`). */
export type KartDurumu = "FOUND" | "REVOKED" | "UNKNOWN" | "INVALID";

/** Okutulan kodun türü (backend `barcode.ScanKind`). */
export type MasaKodTuru = "COPY" | "RESERVED" | "CANCELLED" | "MEMBER_CARD" | "ISBN" | "UNKNOWN";

/** Yönetici kipindeki üye bağlamının açık ödünç satırı. */
export interface AcikOdunc {
  id: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  loaned_at: string;
  due_date: string;
  overdue_days: number;
  cardless: boolean;
  has_override: boolean;
}

/** Üye bağlamı. Görevli kipinde YALNIZ `full_name` + `remaining_quota`. */
export interface MasaUyesi {
  full_name: string;
  remaining_quota: number;
  membership_id?: number;
  member_type?: "STUDENT" | "TEACHER" | "STAFF";
  member_type_display?: string;
  class_label?: string;
  status?: "ACTIVE" | "TERMINATED";
  status_display?: string;
  person_is_active?: boolean;
  loan_limit?: number;
  open_loan_count?: number;
  overdue_loan_count?: number;
  open_loans?: AcikOdunc[];
}

export interface KartSonucu {
  state: KartDurumu;
  message: string;
  member: MasaUyesi | null;
}

/** Masa nüsha özeti. Görevli kipinde barkod + kaynak adı. */
export interface MasaNushasi {
  barcode: string;
  barcode_display: string;
  work_title: string;
  id?: number;
  call_number?: string;
  status?: string;
  status_display?: string;
  is_loanable?: boolean;
  not_loanable_reason?: string;
}

export interface OduncSonucu {
  message: string;
  copy: MasaNushasi;
  due_date: string;
  warnings: string[];
  member: MasaUyesi;
  loan_id?: number;
  due_date_shifted?: boolean;
  cardless?: boolean;
  cardless_reason_display?: string;
  has_override?: boolean;
  override_reason_display?: string;
}

/** Yönetici kipinde iadenin ayrıntısı (kimden alındı, gecikme). */
export interface IadeAyrintisi {
  id: number;
  member_name: string;
  class_label: string;
  loaned_at: string;
  due_date: string;
  overdue_days: number;
  cardless: boolean;
}

export type IadeSonucuTuru = "returned" | "not_on_loan" | "rejected";

export interface IadeSonucu {
  result: IadeSonucuTuru;
  kind: MasaKodTuru;
  message: string;
  copy: MasaNushasi | null;
  loan?: IadeAyrintisi | null;
}

export interface NushaDurumu {
  kind: MasaKodTuru;
  message: string;
  copy: MasaNushasi | null;
  loan?: {
    member_name: string;
    class_label: string;
    loaned_at: string;
    due_date: string;
    overdue_days: number;
  } | null;
}

/** Gecikme engeli istisnasının gerekçesi (backend `OverrideReason`, kapalı liste). */
export type IstisnaGerekcesi = "COURSE_NEED" | "EXCUSED_DELAY" | "RETURN_ARRANGED" | "OTHER";
export const ISTISNA_GEREKCELERI: ReadonlyArray<{ value: IstisnaGerekcesi; label: string }> = [
  { value: "COURSE_NEED", label: "Ders ya da ödev için gerekli" },
  { value: "EXCUSED_DELAY", label: "Gecikmenin geçerli bir mazereti var" },
  { value: "RETURN_ARRANGED", label: "Gecikmiş kaynağın iadesi için görüşüldü" },
  { value: "OTHER", label: "Diğer" },
];
/** İstisna açıklamasının üst sınırı (backend `circulation.OVERRIDE_NOTE_MAX`). */
export const ISTISNA_ACIKLAMA_EN_COK = 500;

/** Kartsız ödüncün gerekçesi (backend `CardlessReason`, kapalı liste). */
export type KartsizGerekce =
  "CARD_NOT_WITH_MEMBER" | "CARD_LOST" | "CARD_NOT_PRINTED" | "CARD_UNREADABLE";
export const KARTSIZ_GEREKCELER: ReadonlyArray<{ value: KartsizGerekce; label: string }> = [
  { value: "CARD_NOT_WITH_MEMBER", label: "Kart yanında değil" },
  { value: "CARD_LOST", label: "Kart kayıp — yenilenecek" },
  { value: "CARD_NOT_PRINTED", label: "Kart henüz basılmadı" },
  { value: "CARD_UNREADABLE", label: "Kart okunmuyor" },
];

/** Masa ret kodları (backend `circulation.RED_*`, `masa.RED_*`). Ekran akışını seçer. */
export const RED = {
  baskaUyede: "nusha_baska_uyede",
  buUyede: "nusha_bu_uyede",
  gecikme: "gecikme_engeli",
  kartKilidi: "kart_okutma_kilidi",
  uyelik: "uyelik_aktif_degil",
  personel: "personel_odunc_kapali",
  sonTarih: "son_odunc_tarihi",
  sinir: "sinir_dolu",
} as const;

/**
 * Üyeye bağlı ödünç retleri: kitaptan değil üyeden kaynaklanır. Masa bu retlerde okutulan
 * kitabın iadesini önerir (kitap iade için getirilmiş olabilir; §9-8 sonlanmış üye de
 * iade yapar). Görevli kipinde sunucu bu retleri nüshanın kimde olduğundan ÖNCE verir.
 */
export const UYEYE_BAGLI_RETLER: ReadonlySet<string> = new Set([
  RED.uyelik,
  RED.personel,
  RED.sonTarih,
  RED.gecikme,
  RED.sinir,
]);

/** Yönetici kipinde kartsız ödünç için üye arama satırı (`library/memberships/`). */
export interface UyeAramaSatiri {
  id: number;
  full_name: string;
  member_type_display: string;
  class_label: string;
  student_number: string;
  status: "ACTIVE" | "TERMINATED";
  remaining_quota: number;
}

export interface OduncGovdesi {
  barcode: string;
  card_no?: string;
  membership_id?: number;
  cardless_reason?: KartsizGerekce;
  override_reason?: IstisnaGerekcesi;
  override_note?: string;
}

export const dolasimApi = {
  /** Kartla üye çözme (görevli kipinde açık). */
  kartOku: (cardNo: string): Promise<KartSonucu> =>
    api.post<KartSonucu>("/library/desk/member/", { card_no: cardNo }),

  /** Yalnız yönetici kipi: kartsız ödünç için bulunan üyenin bağlamı. */
  uyeAc: (membershipId: number): Promise<KartSonucu> =>
    api.post<KartSonucu>("/library/desk/member/", { membership_id: membershipId }),

  oduncVer: (govde: OduncGovdesi): Promise<OduncSonucu> =>
    api.post<OduncSonucu>("/library/checkout/", govde),

  /** Boş bağlamda kitap okutması: açık ödünçteyse iade, değilse durum iletisi. */
  iadeAl: (barcode: string): Promise<IadeSonucu> =>
    api.post<IadeSonucu>("/library/return/", { barcode }),

  nushaDurumu: (barcode: string): Promise<NushaDurumu> =>
    api.get<NushaDurumu>(`/library/desk/copy-status/?barcode=${encodeURIComponent(barcode)}`),

  /** GA-7: art arda geçersiz kart okutmasından sonra yönetici parolasıyla sürdürme. */
  kartKilidiniAc: (password: string): Promise<{ message: string }> =>
    api.post<{ message: string }>("/library/desk/card-unlock/", { password }),

  /** Yalnız yönetici kipi: okul no ya da adla aktif üye arama (kartsız ödünç). */
  uyeAra: (arama: string): Promise<Paginated<UyeAramaSatiri>> =>
    api.get<Paginated<UyeAramaSatiri>>(
      `/library/memberships/?status=ACTIVE&limit=20&search=${encodeURIComponent(arama)}`,
    ),
};

// --- Görevli kipinde katalog okuma (Ağ Kataloğuna denk alanlar) ---

export interface GorevliEser {
  id: number;
  title: string;
  authors: string;
  translator: string;
  edition: string;
  publisher: string;
  publish_year: number | null;
  isbn: string;
  subjects: string;
  language: string;
  resource_type: string;
  resource_type_display: string;
  classification_code: string;
  call_number: string;
  section_name: string | null;
  copy_count: number;
  available_copy_count: number;
}

export interface GorevliNusha {
  id: number;
  work: number;
  work_title: string;
  call_number: string;
  section_name: string | null;
  status: string;
  status_display: string;
  is_loanable: boolean;
  not_loanable_reason: string;
}

/** Katalog aramasının sayfa boyutu. */
export const KATALOG_SAYFA_BOYUTU = 10;

export const katalogOkumaApi = {
  /** Görevli kipinde izinli sorgu parametreleri: q, limit, offset (başkası 403). */
  eserAra: (q: string, offset = 0): Promise<Paginated<GorevliEser>> =>
    api.get<Paginated<GorevliEser>>(
      `/library/works/?q=${encodeURIComponent(q)}&limit=${KATALOG_SAYFA_BOYUTU}&offset=${offset}`,
    ),
  nushalar: (workId: number): Promise<Paginated<GorevliNusha>> =>
    api.get<Paginated<GorevliNusha>>(`/library/copies/?work=${workId}&limit=50&offset=0`),
};
