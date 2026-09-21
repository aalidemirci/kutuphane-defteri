// Kütüphane API istemcisi: şablon ucu OYS önekiyle çağrılır; indirme adı belge adı +
// YEREL tarihtir (backend `excel_template.template_filename` ile aynı biçim).

import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getBlob: vi.fn() }));

vi.mock("../../lib/api", () => ({ api: { getBlob: mocks.getBlob } }));

import { KATALOG_SABLONU_BELGE_ADI, katalogSablonuDosyaAdi, kutuphaneApi } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("kutuphaneApi.catalogTemplate", () => {
  it("OYS'deki şablon ucunu ikili dosya olarak ister", async () => {
    const blob = new Blob(["xlsx"]);
    mocks.getBlob.mockResolvedValue(blob);

    await expect(kutuphaneApi.catalogTemplate()).resolves.toBe(blob);
    expect(mocks.getBlob).toHaveBeenCalledWith("/library/import/template/");
  });
});

describe("katalogSablonuDosyaAdi", () => {
  it("belge adı + gg.aa.yyyy tarihli, Türkçe harfleri koruyan ad kurar", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 21, 14, 0, 0));

    expect(KATALOG_SABLONU_BELGE_ADI).toBe("Katalog Excel Şablonu");
    expect(katalogSablonuDosyaAdi()).toBe("Katalog-Excel-Şablonu_21.09.2026.xlsx");
  });

  it("tarih YEREL tarihtir (gece yarısından hemen sonra UTC'ye kaymaz)", () => {
    // Yerel 22 Eylül 00:30: UTC+3'te `toISOString()` hâlâ 21 Eylül der.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 22, 0, 30, 0));

    expect(katalogSablonuDosyaAdi()).toBe("Katalog-Excel-Şablonu_22.09.2026.xlsx");
  });
});
