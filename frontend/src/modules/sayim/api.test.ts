// Sayım istemcisi (F9): uç yolları, gövde biçimleri ve adlar. Kural sunucudadır; burada
// yalnız istemcinin sunucuya ne gönderdiği sınanır.

import { beforeEach, describe, expect, it, vi } from "vitest";

const istek = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
}));
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return { ...actual, api: { ...actual.api, ...istek } };
});

import {
  EN_COK_OKUTMA,
  SAYIM_BICIMI_TR,
  SAYIM_DURUMU_TR,
  belgeDosyaAdi,
  sayimAdi,
  sayimAdresi,
  sayimApi,
} from "./api";

beforeEach(() => {
  vi.resetAllMocks();
  istek.get.mockResolvedValue({});
  istek.post.mockResolvedValue({});
  istek.patch.mockResolvedValue({});
  istek.del.mockResolvedValue(undefined);
  istek.getBlob.mockResolvedValue(new Blob());
});

describe("sayimApi", () => {
  it("durum sorgusu kullanıcı eylemi değildir (etkinlik başlığı gitmez)", async () => {
    await sayimApi.durum();
    expect(istek.get).toHaveBeenCalledWith("/library/stocktakes/state/", { etkinlik: false });
  });

  it("liste, ayrıntı, taslak, başlat, tamamla, onay ve iptal yolları", async () => {
    await sayimApi.sayimlar({ status: "DRAFT", limit: 25, offset: 50 });
    expect(istek.get).toHaveBeenLastCalledWith(
      "/library/stocktakes/?status=DRAFT&limit=25&offset=50",
    );
    await sayimApi.sayimlar();
    expect(istek.get).toHaveBeenLastCalledWith("/library/stocktakes/");
    await sayimApi.sayim(7);
    expect(istek.get).toHaveBeenLastCalledWith("/library/stocktakes/7/");
    await sayimApi.taslakAc();
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/", {});
    await sayimApi.taslakGuncelle(7, { tmy_stop: false });
    expect(istek.patch).toHaveBeenLastCalledWith("/library/stocktakes/7/", { tmy_stop: false });
    await sayimApi.taslakSil(7);
    expect(istek.del).toHaveBeenLastCalledWith("/library/stocktakes/7/");
    await sayimApi.baslat(7);
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/start/");
    await sayimApi.tamamla(7);
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/complete/");
    await sayimApi.onayla(7, { approved_by_name: "Deneme", approved_on: "2026-12-23" });
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/approve/", {
      approved_by_name: "Deneme",
      approved_on: "2026-12-23",
    });
    await sayimApi.iptalEt(7, "Kurul değişti");
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/cancel/", {
      reason: "Kurul değişti",
    });
    await sayimApi.ilerleme(7);
    expect(istek.get).toHaveBeenLastCalledWith("/library/stocktakes/7/progress/");
  });

  it("okutma: tek kod `barcode`, kuyruk `barcodes` gövdesiyle", async () => {
    await sayimApi.okut(7, ["2026000041"]);
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/scan/", {
      barcode: "2026000041",
    });
    await sayimApi.okut(7, ["1", "2"]);
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/scan/", {
      barcodes: ["1", "2"],
    });
    expect(EN_COK_OKUTMA).toBe(200);
  });

  it("kalem süzgeçleri ve sayım fazlası uçları", async () => {
    await sayimApi.kalemler(7, {
      result: "MISSING",
      outcome: "WRITTEN_OFF",
      section: 2,
      surplus: false,
      damage: true,
      q: "şiir kitabı",
      limit: 200,
      offset: 25,
    });
    expect(istek.get).toHaveBeenLastCalledWith(
      "/library/stocktakes/7/items/?result=MISSING&outcome=WRITTEN_OFF&section=2&surplus=0&damage=1&q=%C5%9Fiir%20kitab%C4%B1&limit=200&offset=25",
    );
    await sayimApi.kalemler(7);
    expect(istek.get).toHaveBeenLastCalledWith("/library/stocktakes/7/items/");
    await sayimApi.fazlaEkle(7, { note: "Etiketsiz", work: null });
    expect(istek.post).toHaveBeenLastCalledWith("/library/stocktakes/7/surplus/", {
      note: "Etiketsiz",
      work: null,
    });
    await sayimApi.fazlaGuncelle(7, 601, { excluded: true, note: "Kişisel kitap" });
    expect(istek.patch).toHaveBeenLastCalledWith("/library/stocktakes/7/items/601/", {
      excluded: true,
      note: "Kişisel kitap",
    });
    await sayimApi.fazlaCikar(7, 601);
    expect(istek.del).toHaveBeenLastCalledWith("/library/stocktakes/7/items/601/");
  });

  it("belgeler: liste, PDF ve Excel (`?kind=`)", async () => {
    await sayimApi.belgeler(7);
    expect(istek.get).toHaveBeenLastCalledWith("/library/stocktakes/7/documents/");
    await sayimApi.belge(7, "sayim-tutanagi");
    expect(istek.getBlob).toHaveBeenLastCalledWith(
      "/library/stocktakes/7/documents/sayim-tutanagi/",
    );
    await sayimApi.belge(7, "sayim-tutanagi", "xlsx");
    expect(istek.getBlob).toHaveBeenLastCalledWith(
      "/library/stocktakes/7/documents/sayim-tutanagi/?kind=xlsx",
    );
  });
});

describe("adlar", () => {
  it("sayımın kısa adı iç kimlik taşımaz; mali yıl boşsa tarihin yılı", () => {
    expect(
      sayimAdi({
        fiscal_year: 2026,
        created_at: "2026-12-20T09:00:00+03:00",
        started_at: "2026-12-21T09:00:00+03:00",
      }),
    ).toBe("Sayım · 2026 · 21.12.2026");
    expect(
      sayimAdi({ fiscal_year: null, created_at: "2027-01-05T09:00:00+03:00", started_at: null }),
    ).toBe("Sayım · 2027 · 05.01.2027");
    expect(sayimAdresi(7)).toBe("/katalog/sayim?sayim=7");
    expect(belgeDosyaAdi("Sayım tutanağı", "xlsx")).toMatch(
      /^Sayım-tutanağı_\d{2}\.\d{2}\.\d{4}\.xlsx$/,
    );
  });

  it("durum ve sayım biçimi adları sözlükteki adlardır", () => {
    expect(Object.values(SAYIM_DURUMU_TR)).toEqual([
      "Taslak",
      "Sürüyor",
      "Tamamlandı",
      "Onaylandı",
      "İptal edildi",
    ]);
    expect(SAYIM_BICIMI_TR.IN_PLACE).toBe("Yerinde sayılır");
    // Sözlük: "sayım kilidi" ve "dondurma" denmez.
    const metin = JSON.stringify([SAYIM_DURUMU_TR, SAYIM_BICIMI_TR]);
    expect(metin).not.toMatch(/kilid|dondur/iu);
  });
});
