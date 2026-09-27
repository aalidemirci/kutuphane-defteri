// Raporlar istemcisi (F10): uç yolları ve sorgu parçaları. Sorguda kişisel veri yoktur (dönem,
// sınıf düzeyi, sıra sayısı, pencere); Genel Bakış sorgusu kullanıcı eylemi değildir.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getBlob: vi.fn(),
}));
vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import { RAPORLAR_ADRESI, donemParcalari, raporDosyaAdi, raporlarAdresi, raporlarApi } from "./api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("raporlarApi", () => {
  it("istatistik dönemi sorguya yazar: etkin yıl boş, ders yılı kimlik, aralık iki tarih", async () => {
    await raporlarApi.istatistik({ tur: "etkin" });
    await raporlarApi.istatistik({ tur: "yil", yilId: 4 });
    await raporlarApi.istatistik({ tur: "aralik", bas: "2026-09-01", son: "2026-12-31" });
    expect(apiMock.get.mock.calls.map((c) => c[0])).toEqual([
      "/library/statistics/",
      "/library/statistics/?school_year=4",
      "/library/statistics/?start=2026-09-01&end=2026-12-31",
    ]);
  });

  it("Genel Bakış sorgusu kullanıcı eylemi sayılmaz", async () => {
    await raporlarApi.pano();
    expect(apiMock.get).toHaveBeenCalledWith("/library/dashboard/statistics/", {
      etkinlik: false,
    });
  });

  it("çok okunanlar: özet, pencere, yeniden hesap ve afiş", async () => {
    await raporlarApi.cokOkunanlar();
    await raporlarApi.pencere("DONEM", "2026-2027/1");
    await raporlarApi.yenidenHesapla();
    await raporlarApi.afis("2026-09");
    expect(apiMock.get.mock.calls.map((c) => c[0])).toEqual([
      "/library/popular/",
      "/library/popular/?window_type=DONEM&window=2026-2027%2F1",
    ]);
    expect(apiMock.post).toHaveBeenCalledWith("/library/popular/refresh/");
    expect(apiMock.getBlob).toHaveBeenCalledWith("/library/popular/poster/?window=2026-09");
  });

  it("okuma ödülü iç çıktısı: dönem, sınıf ve sıra sayısı; kişisel veri yok", async () => {
    await raporlarApi.okumaOdulu({ donem: { tur: "yil", yilId: 3 }, sinif: 9, sira: 5 });
    await raporlarApi.okumaOdulu({ donem: { tur: "etkin" }, sinif: null, sira: 10 });
    expect(apiMock.getBlob.mock.calls.map((c) => c[0])).toEqual([
      "/library/reading-award/pdf/?school_year=3&class_level=9&limit=5",
      "/library/reading-award/pdf/?limit=10",
    ]);
  });
});

describe("yardımcılar", () => {
  it("dönem parçaları", () => {
    expect(donemParcalari({ tur: "etkin" })).toEqual({});
    expect(donemParcalari({ tur: "yil", yilId: 2 })).toEqual({ school_year: 2 });
    expect(donemParcalari({ tur: "aralik", bas: "a", son: "b" })).toEqual({
      start: "a",
      end: "b",
    });
  });

  it("sekme adresleri: varsayılan sekme parametresizdir", () => {
    expect(raporlarAdresi("istatistik")).toBe(RAPORLAR_ADRESI);
    expect(raporlarAdresi("cok-okunanlar")).toBe("/raporlar?tab=cok-okunanlar");
  });

  it("indirme adı belge adı + kapsam + tarih taşır", () => {
    expect(raporDosyaAdi("Ayın Kitapları afişi", "Eylül 2026")).toMatch(
      /^Ayın-Kitapları-afişi_Eylül-2026_\d{2}\.\d{2}\.\d{4}\.pdf$/,
    );
    expect(raporDosyaAdi("Okuma ödülü iç çıktısı")).toMatch(
      /^Okuma-ödülü-iç-çıktısı_\d{2}\.\d{2}\.\d{4}\.pdf$/,
    );
  });
});
