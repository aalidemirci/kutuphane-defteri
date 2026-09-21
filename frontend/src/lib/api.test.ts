// lib/api "yeniden başlat" sözleşmesi: backend restart_gate kapısındayken HANGİ
// uç çağrılırsa çağrılsın 503 `restart_required` döner; istemci ApiError fırlatır
// VE yeniden başlat olayını yayınlar (YenidenBaslatEkrani bunu dinler). Sıradan
// hatalar olayı yayınlamaz.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  ETKINLIK_BASLIGI,
  ETKINLIK_PENCERESI_MS,
  api,
  etkinlikSaatleriniSifirla,
  sonEtkilesimAni,
  sonEtkinlikGonderimiAni,
} from "./api";
import { KILIT_KAPISI_OLAYI } from "./kilit";
import { KIP_YETKISIZ_OLAYI } from "./kip";
import { YENIDEN_BASLAT_OLAYI } from "./restart";

function sahteYanit(status: number, govde: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(govde),
    blob: () => Promise.resolve(new Blob()),
  };
}

describe("api — restart_required sözleşmesi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("503 restart_required hem ApiError fırlatır hem olayı yayınlar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sahteYanit(503, {
          code: "restart_required",
          message: "Yedekten geri yükleme uygulandı.",
          fields: {},
        }),
      ),
    );
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      await expect(api.get("/security/status/")).rejects.toMatchObject({
        code: "restart_required",
        status: 503,
      });
      expect(dinleyici).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });

  it("sıradan hata olayı yayınlamaz", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sahteYanit(400, { code: "validation_error", message: "Hata.", fields: {} }),
        ),
    );
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      await expect(api.get("/students/")).rejects.toBeInstanceOf(ApiError);
      expect(dinleyici).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });
});

// Kip sözleşmesi (tasarım §4.4, §5.10-14): kullanıcı etkileşiminden hemen sonra
// giden istek `X-KD-Etkinlik: 1` taşır; zamanlayıcıyla giden istek (çağıran
// `etkinlik: false` verir) ve etkileşimsiz istek taşımaz. 403 `kip_yetkisiz`
// kip olayını yayınlar; oturum belirteci 403'ü (kodsuz) yayınlamaz.

function gonderilenBasliklar(fetchSahte: ReturnType<typeof vi.fn>): Record<string, string> {
  const [, init] = fetchSahte.mock.calls[0] as [string, RequestInit];
  return init.headers as Record<string, string>;
}

describe("api — etkinlik başlığı", () => {
  let fetchSahte: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    etkinlikSaatleriniSifirla();
    fetchSahte = vi.fn().mockResolvedValue(sahteYanit(200, {}));
    vi.stubGlobal("fetch", fetchSahte);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("etkileşim yoksa başlık gönderilmez", async () => {
    await api.get("/students/");
    expect(gonderilenBasliklar(fetchSahte)).not.toHaveProperty(ETKINLIK_BASLIGI);
    expect(sonEtkinlikGonderimiAni()).toBe(Number.NEGATIVE_INFINITY);
  });

  it.each(["pointerdown", "keydown"])(
    "%s sonrasındaki istek başlığı taşır ve gönderim anını kaydeder",
    async (olay) => {
      window.dispatchEvent(new Event(olay));
      expect(sonEtkilesimAni()).toBeGreaterThan(0);
      await api.post("/students/", { ad: "x" });
      expect(gonderilenBasliklar(fetchSahte)[ETKINLIK_BASLIGI]).toBe("1");
      expect(sonEtkinlikGonderimiAni()).toBeGreaterThan(0);
    },
  );

  it("pencere dolduktan sonraki istek başlık taşımaz", async () => {
    const simdi = Date.now();
    const saat = vi.spyOn(Date, "now").mockReturnValue(simdi);
    window.dispatchEvent(new Event("pointerdown"));
    saat.mockReturnValue(simdi + ETKINLIK_PENCERESI_MS + 1);
    await api.get("/students/");
    expect(gonderilenBasliklar(fetchSahte)).not.toHaveProperty(ETKINLIK_BASLIGI);
  });

  it("etkinlik:false verilen istek etkileşimden hemen sonra da başlık taşımaz", async () => {
    window.dispatchEvent(new Event("keydown"));
    await api.get("/security/mode/", { etkinlik: false });
    expect(gonderilenBasliklar(fetchSahte)).not.toHaveProperty(ETKINLIK_BASLIGI);
    expect(sonEtkinlikGonderimiAni()).toBe(Number.NEGATIVE_INFINITY);
  });

  it("dosya indirmeleri de aynı kuralla başlık taşır", async () => {
    window.dispatchEvent(new Event("pointerdown"));
    await api.getBlob("/templates/students/");
    expect(gonderilenBasliklar(fetchSahte)[ETKINLIK_BASLIGI]).toBe("1");
  });

  it("dosya indirmesinde etkinlik:false başlığı keser", async () => {
    window.dispatchEvent(new Event("pointerdown"));
    await api.postBlob("/backups/encrypted/", undefined, { etkinlik: false });
    expect(gonderilenBasliklar(fetchSahte)).not.toHaveProperty(ETKINLIK_BASLIGI);
  });
});

describe("api — kip_yetkisiz sözleşmesi", () => {
  afterEach(() => vi.unstubAllGlobals());

  async function olaySayisi(istek: () => Promise<unknown>): Promise<number> {
    const dinleyici = vi.fn();
    window.addEventListener(KIP_YETKISIZ_OLAYI, dinleyici);
    try {
      await istek().catch(() => undefined);
    } finally {
      window.removeEventListener(KIP_YETKISIZ_OLAYI, dinleyici);
    }
    return dinleyici.mock.calls.length;
  }

  const KIP_YETKISIZ = {
    code: "kip_yetkisiz",
    message: "Bu işlem görevli kipinde yapılamaz. Yönetici kipine geçin.",
    fields: {},
  };

  it("403 kip_yetkisiz hem ApiError fırlatır hem kip olayını yayınlar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sahteYanit(403, KIP_YETKISIZ)));
    await expect(api.get("/students/")).rejects.toMatchObject({
      status: 403,
      code: "kip_yetkisiz",
    });
    expect(await olaySayisi(() => api.get("/students/"))).toBe(1);
  });

  it("dosya indirmesindeki 403 kip_yetkisiz de olayı yayınlar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sahteYanit(403, KIP_YETKISIZ)));
    expect(await olaySayisi(() => api.getBlob("/templates/students/"))).toBe(1);
  });

  it("kodsuz 403 (oturum belirteci) kip olayını yayınlamaz", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sahteYanit(403, { detail: "Yasak" })));
    expect(await olaySayisi(() => api.get("/students/"))).toBe(0);
  });
});

// Kilit kapısı (tasarım §4.3): oturum ortasında 423 `locked` ya da
// `guvenlik_dosyasi_kayip` gelirse güvenlik kapısı durumu yeniden okusun diye
// olay yayınlanır; başka kodlu 423 yayınlamaz.
describe("api — kilit kapısı sözleşmesi", () => {
  afterEach(() => vi.unstubAllGlobals());

  async function olaySayisi(istek: () => Promise<unknown>): Promise<number> {
    const dinleyici = vi.fn();
    window.addEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    try {
      await istek().catch(() => undefined);
    } finally {
      window.removeEventListener(KILIT_KAPISI_OLAYI, dinleyici);
    }
    return dinleyici.mock.calls.length;
  }

  it.each(["locked", "guvenlik_dosyasi_kayip"])(
    "423 %s hem ApiError fırlatır hem kilit olayını yayınlar",
    async (code) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(sahteYanit(423, { code, message: "Kilitli.", fields: {} })),
      );
      await expect(api.get("/students/")).rejects.toMatchObject({ status: 423, code });
      expect(await olaySayisi(() => api.get("/students/"))).toBe(1);
      expect(await olaySayisi(() => api.getBlob("/templates/students/"))).toBe(1);
    },
  );

  it("başka kodlu 423 ve 423 dışı kilit kodu olayı yayınlamaz", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sahteYanit(423, { code: "baska" })));
    expect(await olaySayisi(() => api.get("/students/"))).toBe(0);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sahteYanit(400, { code: "locked" })));
    expect(await olaySayisi(() => api.get("/students/"))).toBe(0);
  });
});
