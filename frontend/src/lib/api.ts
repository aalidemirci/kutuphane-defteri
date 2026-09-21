// Backend API istemcisi — OYS `lib/api.ts`'ten UYARLANMIŞTIR (Görev 3).
// Kütüphane Defteri authsuz/tek-kullanıcılı çalışır (README "Mimari"): JWT/Bearer,
// token yenileme, `personnel_inactive`/`password_change_required` oturum kapıları
// ve impersonation TAMAMEN çıkarıldı. Kalan: temel `fetch` sarmalayıcı, `ApiError`,
// backend `{code, message, fields}` hata sözleşmesi (CLAUDE.md §7 mirası) ve
// snake_case gövde. Blob yardımcıları (`getBlob`/`postBlob`) dosya indirmeleri
// (Excel şablonları, şifreli yedek, kurulum dosyası, evrak/PDF) için korunur.
// Kip (U5, tasarım §4.4): kullanıcı etkileşiminden hemen sonra giden isteklere
// `X-KD-Etkinlik: 1` eklenir (yönetici kipinin boşta sayacı); 403
// `kip_yetkisiz` `lib/kip.ts` olayını yayınlar. Kilit kapısı (tasarım §4.3):
// 423 `locked`/`guvenlik_dosyasi_kayip` `lib/kilit.ts` olayını yayınlar.

// Boş/tanımsız → göreli "/api/v1": geliştirmede Vite proxy'si (vite.config.ts
// server.proxy) backend'e yönlendirir. Mutlak URL yalnız özel senaryoda gerekir.
import { KILIT_KAPISI_KODLARI, kilitKapisiYayinla } from "./kilit";
import { KIP_YETKISIZ_KODU, kipYetkisizYayinla } from "./kip";
import { yenidenBaslatGerekliYayinla } from "./restart";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/** Backend "yeniden başlat" kapısındayken (geri yükleme sonrası) dönen kod. */
const RESTART_CODE = "restart_required";

// --- Kullanıcı etkinliği (tasarım §4.4 "Boşta dönüş", §5.10-14) -------------
// Yönetici kipinin boşta süresi SUNUCUDA dolar ve yalnız kullanıcı eylemi
// taşıyan isteklerle tazelenir. "Kullanıcı eylemi" = son birkaç saniye içinde
// gerçek bir etkileşim (fare/dokunma ya da tuş) olmuş olması. Zamanlayıcıyla
// giden istekler (kip ve durum sorguları, periyodik yenilemeler) başlığı
// taşımaz; bunun için çağıran `etkinlik: false` verir — aksi hâlde kullanıcının
// son tıklamasından hemen sonra denk gelen bir yoklama da eylem sayılırdı.

/** Etkileşimden sonra giden isteğin kullanıcı eylemi sayıldığı pencere. */
export const ETKINLIK_PENCERESI_MS = 5_000;
/** Backend `apps/okul/kip_middleware.ETKINLIK_BASLIGI` ile aynı. */
export const ETKINLIK_BASLIGI = "X-KD-Etkinlik";

let sonEtkilesim = Number.NEGATIVE_INFINITY;
let sonEtkinlikGonderimi = Number.NEGATIVE_INFINITY;

function etkilesimKaydet(): void {
  sonEtkilesim = Date.now();
}

// Yakalama evresinde dinlenir: bir tıklamanın kendi işleyicisi isteği
// başlatmadan ÖNCE etkileşim kaydedilmiş olur.
if (typeof window !== "undefined") {
  window.addEventListener("pointerdown", etkilesimKaydet, { capture: true, passive: true });
  window.addEventListener("keydown", etkilesimKaydet, { capture: true, passive: true });
}

/** Son etkileşimin anı (`Date.now()`); hiç yoksa -Infinity. */
export function sonEtkilesimAni(): number {
  return sonEtkilesim;
}

/** `X-KD-Etkinlik` taşıyan son isteğin gönderildiği an; hiç yoksa -Infinity. */
export function sonEtkinlikGonderimiAni(): number {
  return sonEtkinlikGonderimi;
}

/** Yalnız testler için: modül düzeyindeki etkinlik saatlerini sıfırlar. */
export function etkinlikSaatleriniSifirla(): void {
  sonEtkilesim = Number.NEGATIVE_INFINITY;
  sonEtkinlikGonderimi = Number.NEGATIVE_INFINITY;
}

export interface IstekSecenekleri {
  /**
   * `false`: `X-KD-Etkinlik` hiçbir koşulda gönderilmez (kip/durum/pano
   * sorguları, periyodik yenilemeler). Verilmezse son etkileşime bakılır.
   */
  etkinlik?: boolean;
}

function etkinlikBasligiEkle(headers: Record<string, string>, etkinlik?: boolean): void {
  if (etkinlik === false) return;
  const simdi = Date.now();
  if (simdi - sonEtkilesim > ETKINLIK_PENCERESI_MS) return;
  headers[ETKINLIK_BASLIGI] = "1";
  sonEtkinlikGonderimi = simdi;
}

/** Hata koduna göre uygulama çapı olayları (yeniden başlat, kilit, kip değişimi). */
function hataOlayiYayinla(status: number, code: string): void {
  // Geri yükleme sonrası kapı: HANGİ çağrı olursa olsun tam ekran
  // "yeniden başlatın" yönlendirmesi tetiklenir (sayfa yenilense bile).
  if (code === RESTART_CODE) yenidenBaslatGerekliYayinla();
  // Kilit kapısı: program arayüzün haberi olmadan kilitlendi ya da güvenlik
  // dosyası kayboldu; güvenlik kapısı durumu yeniden okur.
  if (status === 423 && KILIT_KAPISI_KODLARI.has(code)) kilitKapisiYayinla();
  // Görevli kipi kapısı: kip arayüzün haberi olmadan değişti (süre doldu).
  if (status === 403 && code === KIP_YETKISIZ_KODU) kipYetkisizYayinla();
}

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, unknown>;

  constructor(status: number, code: string, message: string, fields: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

interface RequestOptions extends IstekSecenekleri {
  method?: string;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, etkinlik } = options;
  const isForm = body instanceof FormData;
  const headers: Record<string, string> = {};
  // FormData'da Content-Type'ı tarayıcı (boundary ile) kendisi koyar.
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  etkinlikBasligiEkle(headers, etkinlik);

  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });

  if (resp.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await resp.json();
  } catch {
    /* boş gövde */
  }

  if (!resp.ok) {
    const d = (data ?? {}) as { code?: string; message?: string; fields?: Record<string, unknown> };
    const code = d.code ?? String(resp.status);
    hataOlayiYayinla(resp.status, code);
    throw new ApiError(
      resp.status,
      code,
      d.message ?? "Beklenmeyen bir hata oluştu.",
      d.fields ?? {},
    );
  }
  return data as T;
}

/** İkili (dosya) indirme — şablon, yedek, kurulum dosyası ve evrak/PDF için. */
async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const { method = "GET", body, etkinlik } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  etkinlikBasligiEkle(headers, etkinlik);
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) {
    // Hatalı yanıt genelde JSON; gövdeyi okuyup ApiError'a aktar.
    let code = String(resp.status);
    let message = "Dosya indirilemedi.";
    let fields: Record<string, unknown> = {};
    try {
      const d = (await resp.json()) as {
        code?: string;
        message?: string;
        fields?: Record<string, unknown>;
      };
      code = d.code ?? code;
      message = d.message ?? message;
      fields = d.fields ?? {};
    } catch {
      /* boş gövde */
    }
    hataOlayiYayinla(resp.status, code);
    throw new ApiError(resp.status, code, message, fields);
  }
  return resp.blob();
}

export const api = {
  get: <T>(path: string, secenekler?: IstekSecenekleri) =>
    request<T>(path, { ...secenekler, method: "GET" }),
  post: <T>(path: string, body?: unknown, secenekler?: IstekSecenekleri) =>
    request<T>(path, { ...secenekler, method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  /** Çok parçalı (dosya) gönderim — Content-Type tarayıcıya bırakılır. */
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  putForm: <T>(path: string, form: FormData) => request<T>(path, { method: "PUT", body: form }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /** Dosya indirme (evrak/PDF). */
  getBlob: (path: string, secenekler?: IstekSecenekleri) =>
    requestBlob(path, { ...secenekler, method: "GET" }),
  /** JSON body ile POST + dosya yanıtı. */
  postBlob: (path: string, body?: unknown, secenekler?: IstekSecenekleri) =>
    requestBlob(path, { ...secenekler, method: "POST", body }),
};

export { API_BASE };
