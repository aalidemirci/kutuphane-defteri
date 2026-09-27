// Raporlar (F10 — tasarım §14.1 F10) istemcisi: kişisiz istatistik, Md. 7/1 bilgi kartı,
// çok okunanlar (sayısız), Ayın Kitapları afişi (E12) ve okuma ödülü iç çıktısı (E20).
// Dökümler ve dışa aktarım `modules/dokumler`'dedir; bu sayfa onları bir sekmede gösterir.
//
// Uçların HEPSİ YÖNETİCİ KİPİNDEDİR (görevli kipi izin listesinde yok; `views_istatistik`).
// Profil yasağı sunucudadır (CLAUDE.md §2-5): istatistikte üye bazında bilgi yoktur, üye türü
// ve sınıf düzeyi kırılımında k farklı üyenin altındaki grup `loans: null` gelir ve "—"
// yazılır; çok okunanlarda sayı YOKTUR, yalnız sıra; E20 adlıdır ama sayı taşımaz ve yalnız
// PDF'tir (ekrana ad gelmez). Genel Bakış kartlarının sorgusu kullanıcı eylemi değildir
// (`etkinlik: false`).

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";
import type { EsikliSayi, RaporSayilari } from "../ayiklama/api";

/** Sayfanın adresi ve başlığı (gezinme etiketi, üst çubuk ve h1 aynı — sözlük §4). */
export const RAPORLAR_ADRESI = "/raporlar";
export const RAPORLAR_BASLIGI = "Raporlar";

/** Sekmeler (`?tab=`) — ilk anahtar varsayılandır (sözlük §4.3). */
export const RAPOR_SEKMELERI = {
  istatistik: "İstatistik",
  "cok-okunanlar": "Çok Okunanlar",
  dokumler: "Dökümler",
  "okuma-odulu": "Okuma Ödülü",
} as const;
export type RaporSekmesi = keyof typeof RAPOR_SEKMELERI;

export function raporlarAdresi(sekme: RaporSekmesi): string {
  return sekme === "istatistik" ? RAPORLAR_ADRESI : `${RAPORLAR_ADRESI}?tab=${sekme}`;
}

/** Belge adları (sözlük §2 — E12, E20); backend `BELGE_ADI` sabitleriyle aynı (test sınar). */
export const AYIN_KITAPLARI_ADI = "Ayın Kitapları afişi";
export const OKUMA_ODULU_ADI = "Okuma ödülü iç çıktısı";

/**
 * Yönetmelik Md. 7/1'in ilk cümlesi — docs/mevzuat ve backend
 * `selectors_istatistik.MD7_1_METNI` ile BİREBİR (`test_rapor_metinleri.py` sınar).
 */
export const MD7_1_METNI =
  "Kitap sayısı 10.000'i aşan okul kütüphanelerine bir kütüphaneci atanır.";

/**
 * Uygulama Kılavuzu 7'nin önerisi — docs/mevzuat ve backend
 * `okuma_odulu_belgesi.KILAVUZ_7_ONERISI` ile BİREBİR (test sınar).
 */
export const KILAVUZ_7_ONERISI =
  "En çok kitap okuyan öğrenciler ödüllendirilerek teşvik sistemi kurulabilir.";

/** E20 sıra sayısının sınırları — backend `selectors_okuma_odulu` ile aynı (test sınar). */
export const ODUL_SIRA_VARSAYILAN = 10;
export const ODUL_SIRA_EN_COK = 50;

// ---------------------------------------------------------------------------
// Tipler — `selectors_istatistik.istatistik`, `selectors_populer`
// ---------------------------------------------------------------------------

/** Md. 7/1 bilgi kartı: elde bulunan KİTAP nüshası ve eşik ("aşan" = büyüktür). */
export interface KitapEsigi {
  threshold: number;
  in_stock_books: number;
  /** Sayıya dahil, kayıp bildirilmiş ama kayıttan düşülmemiş kitap nüshası. */
  lost_books: number;
  exceeded: boolean;
}

export type UyeTuru = "STUDENT" | "TEACHER" | "STAFF";

/** `GET library/statistics/` — KİŞİSİZ, k eşikli (şema 1). */
export interface Istatistik {
  schema: number;
  generated_on: string;
  period: { start: string; end: string };
  k_threshold: number;
  collection: RaporSayilari["collection"] & {
    /** Katalogdaki eser sayısı, kaynak türüne göre (nüshasız dijital kaynak dahil). */
    works_by_resource_type: Record<string, number>;
    /** Şu an rafta olan nüsha. */
    available_count: number;
  };
  book_threshold: KitapEsigi;
  acquisitions: RaporSayilari["acquisitions"];
  circulation: {
    k_threshold: number;
    loans: number;
    returns: number;
    distinct_borrowers: number;
    by_member_type: Record<UyeTuru, EsikliSayi>;
    by_class_level: Array<{ class_level: number } & EsikliSayi>;
    by_month: Array<{ month: string; loans: number }>;
    /** Bugünkü aktif üyelik sayısı — EŞİKSİZ: üyelik sayısı ödünç verisi değildir
     *  (27.09.2026 kullanıcı kararı, tasarım F10 ekleri K1). */
    active_members: Record<UyeTuru, number>;
    returned_late: number;
    lost_converted: number;
    open_now: number;
    overdue_now: number;
  };
  deliveries: {
    delivered: { section: number; teacher: number };
    returned: number;
    lost: number;
    open_now: { section: number; teacher: number };
  };
  loss_damage: RaporSayilari["findings"];
  weeding: RaporSayilari["weeding"];
}

/** Çok okunanlar penceresi: dönem (Ağ Kataloğu vitrini) ya da ay (Ayın Kitapları afişi). */
export type PencereTuru = "DONEM" | "AY";

/** Listedeki bir eser — yalnız sıra, kaynak adı ve yazar (SAYI YOK). */
export interface SiradakiEser {
  rank: number;
  work_id: number;
  title: string;
  authors: string;
}

/** Hesaplanmış bir pencerenin künyesi. */
export interface PencereBilgisi {
  window_type: PencereTuru;
  window: string;
  label: string;
  /** Pencere kapandı: liste son hâliyle kalır, bir daha yazılmaz. */
  frozen: boolean;
  computed_on: string;
}

export interface Pencere extends PencereBilgisi {
  works: SiradakiEser[];
}

/** `GET library/popular/` (parametresiz). */
export interface CokOkunanlar {
  k_threshold: number;
  term_windows: PencereBilgisi[];
  month_windows: PencereBilgisi[];
  term: Pencere | null;
  month: Pencere | null;
}

/** `GET library/dashboard/statistics/` — Genel Bakış kartları. */
export interface PanoOzeti {
  book_threshold: KitapEsigi;
  popular: { term: Pencere | null; month: Pencere | null };
}

/** `POST library/popular/refresh/` — kişisiz özet (eser kimliği ve sayı yok). */
export interface YenidenHesapSonucu {
  computed_on: string;
  k_threshold: number;
  windows: Array<{ window_type: PencereTuru; window: string; ranked: number; final: boolean }>;
}

/**
 * İstatistiğin ve E20'nin dönemi. Boş seçim sunucunun varsayılanıdır (etkin ders yılı; yoksa
 * takvim yılının başından bugüne); ders yılında dönem yıl sonu raporununkiyle aynıdır.
 */
export type DonemSecimi =
  { tur: "etkin" } | { tur: "yil"; yilId: number } | { tur: "aralik"; bas: string; son: string };

export interface OkumaOduluSecimi {
  donem: DonemSecimi;
  sinif: number | null;
  sira: number;
}

function sorgu(yol: string, parcalar: Record<string, string | number | null | undefined>): string {
  const q = Object.entries(parcalar)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return q.length > 0 ? `${yol}?${q.join("&")}` : yol;
}

/** Dönem seçimini sorgu parçalarına çevirir (kişisel veri yok: tarih ve kimlik). */
export function donemParcalari(d: DonemSecimi): Record<string, string | number | undefined> {
  if (d.tur === "yil") return { school_year: d.yilId };
  if (d.tur === "aralik") return { start: d.bas, end: d.son };
  return {};
}

/** İndirme adı: belge adı + kapsam + tarih (`lib/download.ts`; kişi adı YOK). */
export function raporDosyaAdi(ad: string, kapsam?: string): string {
  return dosyaAdi([ad, kapsam, formatDate(todayIso())], "pdf");
}

export const raporlarApi = {
  istatistik: (donem: DonemSecimi): Promise<Istatistik> =>
    api.get<Istatistik>(sorgu("/library/statistics/", donemParcalari(donem))),

  /** Genel Bakış: pano sorgusu kullanıcı eylemi değildir. */
  pano: (): Promise<PanoOzeti> =>
    api.get<PanoOzeti>("/library/dashboard/statistics/", { etkinlik: false }),

  cokOkunanlar: (): Promise<CokOkunanlar> => api.get<CokOkunanlar>("/library/popular/"),

  pencere: (tur: PencereTuru, pencere: string): Promise<Pencere> =>
    api.get<Pencere>(sorgu("/library/popular/", { window_type: tur, window: pencere })),

  yenidenHesapla: (): Promise<YenidenHesapSonucu> =>
    api.post<YenidenHesapSonucu>("/library/popular/refresh/"),

  /** Ayın Kitapları afişi (E12) — `pencere` bir ay ('2026-09'). */
  afis: (pencere: string): Promise<Blob> =>
    api.getBlob(sorgu("/library/popular/poster/", { window: pencere })),

  /** Okuma ödülü iç çıktısı (E20) — ADLI PDF; sorguda kişisel veri yok. */
  okumaOdulu: (s: OkumaOduluSecimi): Promise<Blob> =>
    api.getBlob(
      sorgu("/library/reading-award/pdf/", {
        ...donemParcalari(s.donem),
        class_level: s.sinif ?? undefined,
        limit: s.sira,
      }),
    ),
};
