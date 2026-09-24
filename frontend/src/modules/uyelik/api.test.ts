// Üyelik istemcisi (F6): uç yolları, sorgu parçaları ve pano sorgularının
// kullanıcı eylemi SAYILMAMASI (`X-KD-Etkinlik` yok — tasarım §4.4 boşta dönüş).

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
  postBlob: vi.fn(),
}));
vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import { uyelikApi } from "./api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("uyelikApi", () => {
  it("pano sorguları etkinlik başlığı göndermez", async () => {
    await uyelikApi.dolasimOzeti();
    await uyelikApi.sonIslemler();
    expect(apiMock.get).toHaveBeenCalledWith("/library/dashboard/circulation/", {
      etkinlik: false,
    });
    expect(apiMock.get).toHaveBeenCalledWith("/library/dashboard/recent-transactions/", {
      etkinlik: false,
    });
  });

  it("üyelik listesi süzgeçleri sorguya yazılır (Türkçe şube kodlanır)", async () => {
    await uyelikApi.uyelikler({
      status: "ACTIVE",
      memberType: "STUDENT",
      classLevel: 9,
      classSection: "Ç",
      search: "Deneme",
      limit: 25,
      offset: 25,
    });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/library/memberships/?limit=25&offset=25&status=ACTIVE&member_type=STUDENT&class_level=9&class_section=%C3%87&search=Deneme",
    );
  });

  it("kart kuyruğu, işaret ve geri alma uçları", async () => {
    await uyelikApi.kartKuyrugu({ state: "printed", limit: 50 });
    expect(apiMock.get).toHaveBeenCalledWith("/library/member-cards/?state=printed&limit=50");
    await uyelikApi.kartBasildi([1, 2]);
    expect(apiMock.post).toHaveBeenCalledWith("/library/member-cards/confirm-print/", {
      membership_ids: [1, 2],
    });
    await uyelikApi.kartBasimiGeriAl([2]);
    expect(apiMock.post).toHaveBeenCalledWith("/library/member-cards/revert-print/", {
      membership_ids: [2],
    });
  });

  it("pusula gövdesi yalnız verilen alanları taşır", async () => {
    await uyelikApi.pusulaPdf({ membershipIds: [4] });
    expect(apiMock.postBlob).toHaveBeenCalledWith("/library/overdue-loans/slips/", {
      membership_ids: [4],
    });
    await uyelikApi.pusulaPdf({ classLevel: 9, classSection: "A" });
    expect(apiMock.postBlob).toHaveBeenLastCalledWith("/library/overdue-loans/slips/", {
      class_level: 9,
      class_section: "A",
    });
    await uyelikApi.gecikmeListesiPdf({});
    expect(apiMock.getBlob).toHaveBeenCalledWith("/library/overdue-loans/pdf/");
  });

  it("istek listesi ve toplu açma", async () => {
    await uyelikApi.istekListesi(9, "A");
    expect(apiMock.get).toHaveBeenCalledWith(
      "/library/membership-requests/?class_level=9&class_section=A",
    );
    await uyelikApi.istekleriUygula([11], "2026-09-24");
    expect(apiMock.post).toHaveBeenCalledWith("/library/membership-requests/", {
      student_ids: [11],
      requested_at: "2026-09-24",
    });
  });
});
