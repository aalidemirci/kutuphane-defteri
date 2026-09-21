// `okul` API katmanı — kapalı gün uçları. Backend `apps/okul/urls.py` ile yol ve
// gövde hizası burada pinlenir (sessiz 404 / yanlış yıl süzgeci yakalanır).

import { afterEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(() => Promise.resolve([])),
  post: vi.fn(() => Promise.resolve({})),
  put: vi.fn(() => Promise.resolve({})),
  patch: vi.fn(() => Promise.resolve({})),
  del: vi.fn(() => Promise.resolve(undefined)),
  postForm: vi.fn(() => Promise.resolve({})),
  getBlob: vi.fn(() => Promise.resolve(new Blob())),
}));

vi.mock("../../lib/api", () => ({
  api: apiMock,
  ApiError: class ApiError extends Error {},
}));

import { HOLIDAY_KIND_TR, okulApi } from "./api";

afterEach(() => vi.clearAllMocks());

describe("okulApi — kapalı günler", () => {
  it("listHolidays yıl verilince ?year= ile, verilmezse süzgeçsiz ister", async () => {
    await okulApi.listHolidays(2027);
    expect(apiMock.get).toHaveBeenLastCalledWith("/holidays/?year=2027");
    await okulApi.listHolidays();
    expect(apiMock.get).toHaveBeenLastCalledWith("/holidays/");
  });

  it("createHoliday → POST /holidays/ (tahmini bayrağı gönderilmez)", async () => {
    const govde = {
      name: "Yarıyıl tatili",
      start_date: "2027-01-25",
      end_date: "2027-02-05",
      kind: "SCHOOL_BREAK" as const,
    };
    await okulApi.createHoliday(govde);
    expect(apiMock.post).toHaveBeenCalledWith("/holidays/", govde);
  });

  it("deleteHoliday → DELETE /holidays/<id>/", async () => {
    await okulApi.deleteHoliday(7);
    expect(apiMock.del).toHaveBeenCalledWith("/holidays/7/");
  });

  it("seedHolidays → POST /holidays/seed/ { year }", async () => {
    await okulApi.seedHolidays(2026);
    expect(apiMock.post).toHaveBeenCalledWith("/holidays/seed/", { year: 2026 });
  });

  it("tür adları sözlüğe uyar: ara tatil “öğrenciye kapalı gün”dür", () => {
    expect(HOLIDAY_KIND_TR.SCHOOL_BREAK).toBe("Öğrenciye kapalı gün");
    expect(HOLIDAY_KIND_TR.OFFICIAL).toBe("Resmî tatil");
    expect(Object.values(HOLIDAY_KIND_TR)).not.toContain("Tatil");
  });
});
