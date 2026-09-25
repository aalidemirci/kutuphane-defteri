// `teslim` modülü API istemcisi — sınıf kitaplığına ya da öğretmene toplu teslim ve
// geri alma (tasarım §9-11, U11, §4.4). Backend `apps/kutuphane/views_teslim.py` ve
// `serializers_teslim.py` ile BİREBİR.
//
// Teslim ödünç DEĞİLDİR (sözlük: "teslim", "geri alma"; "emanet", "zimmet" değil):
// Md. 18 sayı sınırı ve on beş günlük süre uygulanmaz. Teslim VERME ve listeler
// yalnız yönetici kipindedir; görevli kipinde açık TEK uç geri alma okutmasıdır ve
// yanıtı daralır — teslim alanın kimliği (`delivery`) gelmez, nüsha özeti barkod +
// eser adıdır. Ekran bir alanın yokluğunu "görevli kipi" diye okumaz; kipi prop'tan
// bilir.
//
// Evrak (E15 "Teslim listesi · Geri alma dökümü") yalnız yönetici kipindedir ve
// kayıt yazmaz.

import { api } from "../../lib/api";
import type { Paginated } from "../../lib/pagination";
import type { MasaKodTuru, MasaNushasi } from "../dolasim/api";

/** Teslimin durumu — backend `DeliveryStatus` (sözlük). */
export type TeslimDurumu = "OPEN" | "RETURNED" | "LOST_CONVERTED";

export const TESLIM_DURUMU_TR: Record<TeslimDurumu, string> = {
  OPEN: "Teslimde",
  RETURNED: "Geri alındı",
  LOST_CONVERTED: "Kayba dönüştü",
};

/** Teslim alanın türü — backend `DeliveryRecipientKind` (kişisiz, kalıcı). */
export type TeslimAlanTuru = "SECTION" | "TEACHER";

export const TESLIM_ALAN_TURU_TR: Record<TeslimAlanTuru, string> = {
  SECTION: "Sınıf kitaplığı",
  TEACHER: "Öğretmen",
};

/** Teslim satırı (yönetici kipi) — `DELIVERY_FIELDS`. Öğretmen adı sunucuda şifrelidir. */
export interface TeslimSatiri {
  id: number;
  copy: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
  call_number: string;
  recipient_kind: TeslimAlanTuru;
  recipient_kind_display: string;
  section: number | null;
  personnel: number | null;
  /** "9/A" ya da öğretmenin adı (kapanmış teslimde bağ koparılmışsa boş olabilir). */
  recipient_label: string;
  delivered_on: string;
  expected_return: string | null;
  /** Açık teslimin beklenen dönüşü geçti mi? Ödünç gecikmesi DEĞİLDİR — bilgi. */
  expected_return_passed: boolean;
  document_no: string;
  status: TeslimDurumu;
  status_display: string;
  returned_at: string | null;
  lost_at: string | null;
}

/** `POST library/deliveries/` — toplu teslim. Şube YA DA öğretmen (ikisi birden değil). */
export interface TeslimGovdesi {
  section_id?: number;
  personnel_id?: number;
  barcodes: string[];
  delivered_on?: string;
  /** Boşsa etkin ders yılının sonu. */
  expected_return?: string | null;
  /** Boşsa program `<yıl>/<sıra>` biçiminde yeni numara verir. */
  document_no?: string;
}

/** Toplu teslimin sonucu (201): belge no, tarihler, alan ve açılan satırlar. */
export interface TeslimSonucu {
  document_no: string;
  delivered_on: string;
  expected_return: string | null;
  recipient_kind: TeslimAlanTuru;
  recipient_kind_display: string;
  recipient_label: string;
  count: number;
  deliveries: TeslimSatiri[];
}

/** Teslim listesine okutulan kodun ön denetimi (yazma yok). */
export interface TeslimDenetimi {
  result: "deliverable" | "rejected";
  kind: MasaKodTuru;
  message: string;
  copy: MasaNushasi | null;
}

/** Yönetici kipinde geri almanın teslim ayrıntısı — `TAKE_BACK_DELIVERY_FIELDS`. */
export interface GeriAlinanTeslim {
  id: number;
  recipient_kind: TeslimAlanTuru;
  recipient_kind_display: string;
  recipient_label: string;
  delivered_on: string;
  expected_return: string | null;
  document_no: string;
  returned_at: string | null;
}

export type GeriAlmaSonucuTuru = "returned" | "not_delivered" | "rejected";

/** Geri alma okutmasının sonucu (her zaman 200). Görevli kipinde `delivery` YOKTUR. */
export interface GeriAlmaSonucu {
  result: GeriAlmaSonucuTuru;
  kind: MasaKodTuru;
  message: string;
  copy: MasaNushasi | null;
  delivery?: GeriAlinanTeslim | null;
}

export interface TeslimListeParametreleri {
  status?: TeslimDurumu | "";
  recipientKind?: TeslimAlanTuru | "";
  section?: number | null;
  personnel?: number | null;
  documentNo?: string;
  copy?: number | null;
  limit?: number;
  offset?: number;
}

/** Evrak adları (docs/sozluk.md §2 — E15). İndirilen dosyanın adı bunlarla başlar. */
export const TESLIM_LISTESI_ADI = "Teslim listesi";
export const GERI_ALMA_DOKUMU_ADI = "Geri alma dökümü";

/**
 * Geri alma dökümünün kapsamı: bu ekranda geri alınan satırlar (okutma oturumu) YA DA
 * bir belge no'nun bütün satırları (Teslim Kayıtları'ndaki belge kartı — görevli
 * kipinde, masada ya da başka bir oturumda yapılan geri almaların dökümü de buradan
 * alınır).
 */
export type GeriAlmaDokumuKapsami = { deliveryIds: number[] } | { documentNo: string };

/** Teslim listesinin sayfa boyutu. */
export const TESLIM_SAYFA_BOYUTU = 50;

function withQuery(path: string, parts: string[]): string {
  return parts.length ? `${path}?${parts.join("&")}` : path;
}

function listeParcalari(p: TeslimListeParametreleri): string[] {
  const parts: string[] = [];
  if (p.status) parts.push(`status=${p.status}`);
  if (p.recipientKind) parts.push(`recipient_kind=${p.recipientKind}`);
  if (p.section) parts.push(`section=${p.section}`);
  if (p.personnel) parts.push(`personnel=${p.personnel}`);
  if (p.documentNo?.trim()) parts.push(`document_no=${encodeURIComponent(p.documentNo.trim())}`);
  if (p.copy) parts.push(`copy=${p.copy}`);
  if (p.limit !== undefined) parts.push(`limit=${p.limit}`);
  if (p.offset) parts.push(`offset=${p.offset}`);
  return parts;
}

export const teslimApi = {
  /** `GET library/deliveries/` — en yeni teslim önce (yalnız yönetici kipi). */
  listele: (params: TeslimListeParametreleri = {}): Promise<Paginated<TeslimSatiri>> =>
    api.get<Paginated<TeslimSatiri>>(withQuery("/library/deliveries/", listeParcalari(params))),

  /**
   * `POST library/deliveries/` — toplu teslim TEK işlemdir: listedeki bir kitap
   * teslim edilemiyorsa hiçbiri yapılmaz ve gerekçeler `fields.barcodes` altında döner.
   */
  teslimEt: (govde: TeslimGovdesi): Promise<TeslimSonucu> =>
    api.post<TeslimSonucu>("/library/deliveries/", govde),

  /** `POST library/deliveries/check/` — okutulan kod teslim listesine girebilir mi? */
  denetle: (barcode: string): Promise<TeslimDenetimi> =>
    api.post<TeslimDenetimi>("/library/deliveries/check/", { barcode }),

  /** `POST library/deliveries/take-back/` — geri alma okutması (görevli kipinde de açık). */
  geriAl: (barcode: string): Promise<GeriAlmaSonucu> =>
    api.post<GeriAlmaSonucu>("/library/deliveries/take-back/", { barcode }),

  /** E15 Teslim listesi — bir belge no'nun bütün satırları (kayıt yazmaz). */
  teslimListesiPdf: (documentNo: string): Promise<Blob> =>
    api.getBlob(`/library/deliveries/pdf/?document_no=${encodeURIComponent(documentNo)}`),

  /**
   * E15 Geri alma dökümü (kayıt yazmaz): okutma oturumunun satırları ya da bir belge
   * no'nun bütünü (geri alındı · teslimde · kayba dönüştü).
   */
  geriAlmaDokumuPdf: (kapsam: GeriAlmaDokumuKapsami): Promise<Blob> =>
    api.postBlob(
      "/library/deliveries/take-back-report/",
      "documentNo" in kapsam
        ? { document_no: kapsam.documentNo }
        : { delivery_ids: kapsam.deliveryIds },
    ),
};
