// Kayıp/hasar istemcisi (F7, Md. 19, D3): uç yolları, sorgu parçaları ve sözlük adları.
// Borç, ceza, zayi dili YOKTUR.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  getBlob: vi.fn(),
}));
vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import {
  ACIK_COZUMLER,
  BEDEL_SORULAN,
  BEDEL_YOLLARI,
  COZUM_TR,
  DOSYA_TURU_TR,
  KISI_ACIK_COZUMLER,
  kayipApi,
} from "./api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("kayipApi", () => {
  it("liste süzgeçleri sorguya yazılır", async () => {
    await kayipApi.listele({
      resolution: "PENDING",
      caseType: "LOST",
      open: true,
      copy: 12,
      limit: 25,
      offset: 25,
    });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/library/loss-damage-cases/?resolution=PENDING&case_type=LOST&open=1&copy=12&limit=25&offset=25",
    );
    await kayipApi.listele();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/loss-damage-cases/");
  });

  it("dosya açma, ayrıntı, not, çözüm ve onarım uçları", async () => {
    await kayipApi.ac({ case_type: "DAMAGED", copy_id: 3, send_to_repair: true });
    await kayipApi.getir(8);
    await kayipApi.notuGuncelle(8, "Kısa not");
    await kayipApi.coz(8, { resolution: "PRICE_DETERMINED", market_price: "120.00" });
    await kayipApi.onarimaGonder(3);
    await kayipApi.onarimdanDon(3);
    await kayipApi.tutanakPdf(8);
    expect(apiMock.post).toHaveBeenCalledWith("/library/loss-damage-cases/", {
      case_type: "DAMAGED",
      copy_id: 3,
      send_to_repair: true,
    });
    expect(apiMock.get).toHaveBeenCalledWith("/library/loss-damage-cases/8/");
    expect(apiMock.patch).toHaveBeenCalledWith("/library/loss-damage-cases/8/", {
      responsible_note: "Kısa not",
    });
    expect(apiMock.post).toHaveBeenCalledWith("/library/loss-damage-cases/8/resolve/", {
      resolution: "PRICE_DETERMINED",
      market_price: "120.00",
    });
    expect(apiMock.post).toHaveBeenCalledWith("/library/copies/3/send-to-repair/", {});
    expect(apiMock.post).toHaveBeenCalledWith("/library/copies/3/return-from-repair/", {});
    expect(apiMock.getBlob).toHaveBeenCalledWith("/library/loss-damage-cases/8/pdf/");
  });

  it("çözüm adları sözlükle aynıdır; borç, ceza ve zayi dili yoktur", () => {
    expect(DOSYA_TURU_TR).toEqual({ LOST: "Kayıp", DAMAGED: "Hasar" });
    expect(Object.values(COZUM_TR)).toEqual([
      "Çözüm bekliyor",
      "Bedel belirlendi",
      "Bedel teslim alındı",
      "Bulundu",
      "Aynısı temin edildi",
      "Onarıldı",
      "Bedelle aynısı alındı",
      "Bedelle başka eser alındı",
      "Kayıttan düşme önerildi",
      "Kayba dönüştü",
    ]);
    const metin = Object.values(COZUM_TR).join(" ").toLocaleLowerCase("tr");
    for (const yasak of ["borç", "ceza", "zayi", "tahsil"]) expect(metin).not.toContain(yasak);
  });

  it("bedel yolları ve açık kalan çözümler backend kümeleriyle aynıdır", () => {
    expect([...BEDEL_YOLLARI]).toEqual([
      "PRICE_DETERMINED",
      "PRICE_RECEIVED",
      "CLOSED_SAME_REPURCHASED",
      "CLOSED_OTHER_REPURCHASED",
    ]);
    expect(BEDEL_SORULAN).toBe("PRICE_DETERMINED");
    // Dosya açık (okulun açık işi) ≠ kişinin açık işi: "Bedel teslim alındı" (25.09.2026).
    expect([...ACIK_COZUMLER]).toEqual(["PENDING", "PRICE_DETERMINED", "PRICE_RECEIVED"]);
    expect([...KISI_ACIK_COZUMLER]).toEqual(["PENDING", "PRICE_DETERMINED"]);
  });
});
