// Ağ Kataloğu ve Ağ Doktoru — API istemcisi (tasarım §5.2, §5.6, §5.9).
//
// Backend: `apps/kutuphane/views_katalog.py` (ayar) ve `views_ag_doktoru.py`
// (durum, eylemler, denetim, belgeler) ile BİREBİR. Uçların hepsi yalnız yönetici
// kipinde açıktır; görevli kipinde 403 `kip_yetkisiz` döner (izin listesinde
// değiller).
//
// Katalog dinleyicisi masaüstü programındadır. Program masaüstü penceresi
// dışında çalışıyorsa (geliştirme sunucusu) durum `masaustu: false` gelir ve
// eylemler 503 `masaustu_yok` döner; ekranlar bunu hata değil bilgi olarak
// gösterir.
//
// Port ayar ucundan DEĞİŞMEZ (Windows'ta 400): güvenlik duvarı kuralını ve
// kurucunun okuduğu değeri de yazan UAC adımından (`portDegistir`) geçer.

import { api } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, todayIso } from "../../lib/format";

const KOK = "/library/network-catalog";

/** Ağ Doktoru ekranının adresi ve başlığı (docs/sozluk.md §4). */
export const AG_DOKTORU_ADRESI = "/ag-doktoru";
export const AG_DOKTORU_BASLIGI = "Ağ Doktoru";
/** Ayarlar'daki sekme (`?tab=`). */
export const AG_KATALOGU_SEKMESI = "ag-katalogu";

/** Belge adları (sözlük §2, E3) — düğmeler ve indirilen dosya adları buradan. */
export const AFIS_BELGE_ADI = "Katalog Afişi";
export const BILGI_NOTU_BELGE_ADI = "Ağ Hizmeti Bilgi Notu";
export const YER_IMI_BELGE_ADI = "Yer İmi Dosyaları";

/** Program masaüstü penceresi dışında (backend `ag_doktoru.MasaustuYok`). */
export const MASAUSTU_YOK_KODU = "masaustu_yok";

/** Varsayılan port (backend `KATALOG_VARSAYILAN_PORT`) ve izinli aralık. */
export const VARSAYILAN_PORT = 8765;
export const PORT_ALT = 1024;
export const PORT_UST = 65535;

// ---------------------------------------------------------------------------
// Ayar
// ---------------------------------------------------------------------------

export type DinlemeKipi = "ALL" | "SELECTED";

export const DINLEME_KIPI_TR: Record<DinlemeKipi, string> = {
  ALL: "Bu bilgisayarın bütün ağ bağlantılarında",
  SELECTED: "Yalnız seçili IP adresinde",
};

export interface KatalogAyari {
  acik: boolean;
  port: number;
  dinleme_kipi: DinlemeKipi;
  secili_ip: string;
  son_afis_ip: string;
  uyku_engelleme: boolean;
  vitrin_acik: boolean;
  konular_acik: boolean;
  tahta_cidrleri: string[];
  kutuphane_saatleri: string;
}

/** Ayar formunun gönderdiği alanlar: aç/kapa ve port ayrı adımlardır, afiş adresi programındır. */
export type KatalogAyariGovde = Partial<
  Pick<
    KatalogAyari,
    | "dinleme_kipi"
    | "secili_ip"
    | "uyku_engelleme"
    | "vitrin_acik"
    | "konular_acik"
    | "tahta_cidrleri"
    | "kutuphane_saatleri"
  >
>;

// ---------------------------------------------------------------------------
// Durum
// ---------------------------------------------------------------------------

export type KatalogDurumAdi = "kapali" | "acik" | "engellendi" | "hata" | "bekliyor" | "bakim";

export const KATALOG_DURUMU_TR: Record<KatalogDurumAdi, string> = {
  kapali: "Kapalı",
  acik: "Açık",
  engellendi: "Güvenlik duvarı izni yok",
  hata: "Açılamadı",
  bekliyor: "Port bekleniyor",
  bakim: "Geri yükleme nedeniyle kapalı",
};

export type MaddeDurumu = "gecti" | "kaldi" | "uyari" | "bilinmiyor";

export const MADDE_DURUMU_TR: Record<MaddeDurumu, string> = {
  gecti: "Geçti",
  kaldi: "Geçmedi",
  uyari: "Uyarı",
  bilinmiyor: "Denetlenemedi",
};

export interface GuvenlikMaddesi {
  kod: string;
  baslik: string;
  durum: MaddeDurumu;
  aciklama: string;
}

export interface GuvenlikKurali {
  ad: string;
  program: string;
  yerel_port: string[];
  uzak_adres: string[];
  profil: string;
  etkin: boolean;
}

export interface GuvenlikDuvari {
  platform: "windows" | "linux";
  dinlemeye_izin: boolean;
  maddeler: GuvenlikMaddesi[];
  /** İlk izin kuralı (programın kendi adlı kuralı öncelikli). */
  kural: GuvenlikKurali | null;
  /** Portu kapsayan BÜTÜN izin kuralları: Windows herhangi birine uyan bağlantıyı kabul eder. */
  kurallar?: GuvenlikKurali[];
  ag_profilleri: string[];
  hata: string | null;
  linux: {
    arac?: string | null;
    etkin?: boolean | null;
    komut?: string;
    bloklar?: string[];
    tanim_var?: boolean;
  };
}

export interface KatalogDurumu {
  durum: KatalogDurumAdi;
  ayar_acik: boolean;
  dinleme_kipi: DinlemeKipi;
  tum_arayuzler: boolean;
  dinleme_ip: string | null;
  port: number;
  adres: string | null;
  guncel_ip: string | null;
  son_afis_ip: string | null;
  ip_degisti: boolean;
  son_hata: string | null;
  uyarilar: string[];
  guvenlik_duvari: GuvenlikDuvari | null;
  reddedilen_baglanti: number;
  uyku_engelli: boolean;
}

export type Platform = "windows" | "linux" | "diger";

export interface KatalogSayaclari {
  bugun: Record<string, number>;
  son_hata: { zaman: string; ileti: string } | null;
}

export interface AgDurumu {
  masaustu: boolean;
  platform: Platform;
  katalog: KatalogDurumu | null;
  /** Katalog adresinin QR modülleri, satır satır ("1" koyu); katalog kapalıyken null. */
  qr: string[] | null;
  sayaclar: KatalogSayaclari;
}

export interface Arayuz {
  ad: string;
  ip: string;
  onek: number;
  varsayilan_rota: boolean;
  ag_profili: string | null;
  yonlendirme: boolean | null;
  /** Adres Ayarlar'daki tahta ağı bloklarından birinin içinde (öğrenci erişimli ağ, §5.8). */
  tahta_agi?: boolean;
}

export interface IpAdaylari {
  arayuzler: Arayuz[];
  varsayilan_ip: string | null;
  yonlendirme_acik: boolean;
  uyarilar: string[];
  kaynak: string;
  /** Arayüz listesi okunamadı (yalnız varsayılan adres biliniyor). */
  okunamadi?: boolean;
}

export interface DinleyiciSinamasi {
  acik: boolean;
  port: number;
  sonuclar: Array<{ ip: string; ad: string; ayakta: boolean; komut: string }>;
  uyari: string;
}

export interface KuralSonucu {
  tamam: boolean;
  ileti: string;
  durum: AgDurumu;
}

export type KatalogEylemi = "ac" | "kapat" | "yeniden_baslat";

/** Ağ profili adları (Windows kategorileri → arayüz dili). */
export const AG_PROFILI_TR: Record<string, string> = {
  Domain: "Etki alanı",
  DomainAuthenticated: "Etki alanı",
  Private: "Özel",
  Public: "Genel",
};

export function agProfiliAdi(profil: string | null | undefined): string {
  if (!profil) return "Bilinmiyor";
  return AG_PROFILI_TR[profil] ?? profil;
}

/**
 * Güvenlik duvarı kuralının `Profile` değeri ("Any" ya da "Domain, Private, Public")
 * → arayüz dili (sözlük §4.9: Public/Private/Domain kullanıcı metninde geçmez).
 * Backend karşılığı `ag_belgeleri._profil_metni` (bilgi notu) ile aynı kural.
 */
export function kuralProfiliAdi(profil: string | null | undefined): string {
  const metin = (profil ?? "").trim();
  if (!metin) return "—";
  if (metin.toLowerCase() === "any") return "Hepsi (Etki alanı, Özel, Genel)";
  return metin
    .replace(/;/g, ",")
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
    .map(agProfiliAdi)
    .join(", ");
}

/**
 * Katalog kapatılabilir mi? Ayar açıksa ve katalog kapalı ya da geri yüklemede
 * değilse (açık, güvenlik duvarı izni yok, açılamadı, port bekleniyor): ayar açık
 * kaldıkça program her açılışta yeniden dener, kullanıcı vazgeçebilmelidir.
 */
export function katalogKapatilabilir(katalog: KatalogDurumu | null | undefined): boolean {
  return Boolean(katalog?.ayar_acik) && katalog?.durum !== "kapali" && katalog?.durum !== "bakim";
}

/** Günlük sayaçların arayüzdeki adları (backend `katalog.sayac.OLAYLAR`). */
export const SAYAC_TR: Record<string, string> = {
  sayfa: "gösterilen sayfa",
  arama: "arama",
  bulunamadi: "bulunamayan sayfa",
  reddedildi: "reddedilen istek",
  hiz_siniri: "sınıra takılan istek",
  bakim: "bakımda karşılanan istek",
  veri_hatasi: "veri hatası",
  sunucu_hatasi: "katalog hatası",
};

function ipSorgusu(ip?: string): string {
  return ip ? `?ip=${encodeURIComponent(ip)}` : "";
}

/** İndirilen belgenin adı: belge adı + YEREL tarih (sözlük §3). */
export function belgeDosyaAdi(ad: string, uzanti: string): string {
  return dosyaAdi([ad, formatDate(todayIso())], uzanti);
}

export const agKataloguApi = {
  ayar: () => api.get<KatalogAyari>(`${KOK}/settings/`),
  ayarKaydet: (govde: KatalogAyariGovde) => api.put<KatalogAyari>(`${KOK}/settings/`, govde),
  /** Periyodik yenilemede de çağrılır: etkinlik başlığı taşımaz (yönetici kipini canlı tutmaz). */
  durum: () => api.get<AgDurumu>(`${KOK}/status/`, { etkinlik: false }),
  eylem: (eylem: KatalogEylemi) => api.post<AgDurumu>(`${KOK}/control/`, { eylem }),
  guvenlikDuvari: () => api.get<GuvenlikDuvari>(`${KOK}/firewall/`),
  kuralGuncelle: () => api.post<KuralSonucu>(`${KOK}/firewall-rule/`, {}),
  arayuzler: () => api.get<IpAdaylari>(`${KOK}/interfaces/`),
  dinleyiciSinamasi: () => api.post<DinleyiciSinamasi>(`${KOK}/listener-test/`, {}),
  portDegistir: (port: number) => api.post<KuralSonucu>(`${KOK}/port/`, { port }),
  afis: (ip?: string) => api.postBlob(`${KOK}/poster/`, ip ? { ip } : {}),
  bilgiNotu: (ip?: string) => api.getBlob(`${KOK}/info-note/${ipSorgusu(ip)}`),
  yerImleri: (ip?: string) => api.getBlob(`${KOK}/bookmarks/${ipSorgusu(ip)}`),
  pysMetni: (ip?: string) => api.get<{ metin: string }>(`${KOK}/pys-text/${ipSorgusu(ip)}`),
};
