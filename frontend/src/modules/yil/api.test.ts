// İlişik ve yıl akışı istemcisi: uç yolları, sorgu dizesi, gövdeler ve özet metni.
// Genel Bakış özeti kullanıcı eylemi değildir (etkinlik başlığı gitmez).

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  getBlob: vi.fn(),
  postBlob: vi.fn(),
}));

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import { acikIslerOzeti, yilApi } from "./api";
import { ilisikSatiri } from "./testVerileri";

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.get.mockResolvedValue({});
  apiMock.getBlob.mockResolvedValue(new Blob());
  apiMock.postBlob.mockResolvedValue(new Blob());
});

describe("yilApi", () => {
  it("özet etkinlik başlığı göndermez", async () => {
    await yilApi.akislar();
    expect(apiMock.get).toHaveBeenCalledWith("/library/year-flows/", { etkinlik: false });
  });

  it("ilişik listesi sorgu dizesini kurar; varsayılan değerleri yazmaz", async () => {
    await yilApi.ilisikListesi();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/clearance/");
    await yilApi.ilisikListesi({
      state: "clear",
      group: "priority",
      personType: "student",
      obligation: "collect",
      classLevel: 12,
      classSection: "Ç",
      search: "Şükrü 1",
      limit: 50,
      offset: 50,
    });
    expect(apiMock.get).toHaveBeenLastCalledWith(
      "/library/clearance/?state=clear&group=priority&person_type=student&obligation=collect" +
        "&class_level=12&class_section=%C3%87&search=%C5%9E%C3%BCkr%C3%BC%201&limit=50&offset=50",
    );
    await yilApi.ilisikListesi({ obligation: "all", classLevel: null });
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/clearance/");
  });

  it("PDF uçları ve gövdeleri", async () => {
    await yilApi.ilisikListesiPdf({ group: "graduating" });
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/clearance/pdf/?group=graduating");
    await yilApi.ilisikBelgesiPdf({ studentIds: [3] });
    expect(apiMock.postBlob).toHaveBeenLastCalledWith("/library/clearance/certificates/", {
      student_ids: [3],
      personnel_ids: [],
    });
    await yilApi.yilSonuPusulasiPdf({ group: "priority", returnBy: "2027-06-11" });
    expect(apiMock.postBlob).toHaveBeenLastCalledWith("/library/year-end/slips/", {
      student_ids: [],
      personnel_ids: [],
      group: "priority",
      return_by: "2027-06-11",
    });
    await yilApi.yilSonuPusulasiPdf({ classLevel: 12, classSection: "A" });
    expect(apiMock.postBlob).toHaveBeenLastCalledWith("/library/year-end/slips/", {
      student_ids: [],
      personnel_ids: [],
      class_level: 12,
      class_section: "A",
    });
    await yilApi.sinifKitapligiListesiPdf(5);
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/deliveries/pdf/?section=5");
    await yilApi.sinifKitapliklari(true);
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/clearance/sections/?graduating=1");
  });
});

describe("acikIslerOzeti", () => {
  it("ödünç, gecikme, teslim ve dosya sayılarını yazar", () => {
    expect(
      acikIslerOzeti(
        ilisikSatiri({
          open_loan_count: 2,
          overdue_loan_count: 1,
          open_delivery_count: 3,
          open_case_count: 1,
        }),
      ),
    ).toBe("2 ödünç (1 gecikmiş) · 3 teslim · 1 kayıp/hasar dosyası");
    expect(acikIslerOzeti(ilisikSatiri({ open_loan_count: 0 }))).toBe("Açık işi yok");
  });
});
