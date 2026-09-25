// Teslim istemcisi (F7, U11): uç yolları ve sorgu parçaları. Okutma gövdesi POST'tur
// (kod adrese yazılmaz); geri alma dökümü teslim satırı kimlikleriyle istenir.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getBlob: vi.fn(),
  postBlob: vi.fn(),
}));
vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import { TESLIM_DURUMU_TR, TESLIM_ALAN_TURU_TR, teslimApi } from "./api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("teslimApi", () => {
  it("liste süzgeçleri sorguya yazılır; belge no kodlanır", async () => {
    await teslimApi.listele({
      status: "OPEN",
      recipientKind: "SECTION",
      section: 4,
      personnel: 7,
      documentNo: " 2026/3 ",
      copy: 9,
      limit: 50,
      offset: 50,
    });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/library/deliveries/?status=OPEN&recipient_kind=SECTION&section=4&personnel=7&document_no=2026%2F3&copy=9&limit=50&offset=50",
    );
  });

  it("süzgeçsiz liste sade adrese gider", async () => {
    await teslimApi.listele();
    expect(apiMock.get).toHaveBeenCalledWith("/library/deliveries/");
  });

  it("teslim, ön denetim ve geri alma POST gövdesiyle gider", async () => {
    await teslimApi.teslimEt({ section_id: 3, barcodes: ["2026000001"] });
    await teslimApi.denetle("2026000001");
    await teslimApi.geriAl("2026000001");
    expect(apiMock.post).toHaveBeenNthCalledWith(1, "/library/deliveries/", {
      section_id: 3,
      barcodes: ["2026000001"],
    });
    expect(apiMock.post).toHaveBeenNthCalledWith(2, "/library/deliveries/check/", {
      barcode: "2026000001",
    });
    expect(apiMock.post).toHaveBeenNthCalledWith(3, "/library/deliveries/take-back/", {
      barcode: "2026000001",
    });
  });

  it("evrak: teslim listesi belge no ile, geri alma dökümü satır kimlikleri ya da belge no ile", async () => {
    await teslimApi.teslimListesiPdf("2026/3");
    await teslimApi.geriAlmaDokumuPdf({ deliveryIds: [4, 5] });
    await teslimApi.geriAlmaDokumuPdf({ documentNo: "2026/3" });
    expect(apiMock.getBlob).toHaveBeenCalledWith("/library/deliveries/pdf/?document_no=2026%2F3");
    expect(apiMock.postBlob).toHaveBeenNthCalledWith(1, "/library/deliveries/take-back-report/", {
      delivery_ids: [4, 5],
    });
    expect(apiMock.postBlob).toHaveBeenNthCalledWith(2, "/library/deliveries/take-back-report/", {
      document_no: "2026/3",
    });
  });

  it("durum ve alan adları sözlükle aynıdır (ödünç dili yok)", () => {
    expect(TESLIM_DURUMU_TR).toEqual({
      OPEN: "Teslimde",
      RETURNED: "Geri alındı",
      LOST_CONVERTED: "Kayba dönüştü",
    });
    expect(TESLIM_ALAN_TURU_TR).toEqual({ SECTION: "Sınıf kitaplığı", TEACHER: "Öğretmen" });
  });
});
