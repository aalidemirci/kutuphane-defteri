// Kip API istemcisi — uç yolları ve etkinlik sözleşmesi backend
// `apps/okul/urls.py` (security/mode/*) ile birebir.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiSahte = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({}),
  post: vi.fn().mockResolvedValue({}),
}));

vi.mock("../../lib/api", () => ({ api: apiSahte }));

import { kipApi } from "./api";

describe("kipApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("durum sorgusu varsayılan olarak etkinlik başlığı göndermez", async () => {
    await kipApi.durum();
    expect(apiSahte.get).toHaveBeenCalledWith("/security/mode/", { etkinlik: false });
  });

  it("nabız sorgusu etkinlik kuralına bırakılır", async () => {
    await kipApi.durum(true);
    expect(apiSahte.get).toHaveBeenCalledWith("/security/mode/", { etkinlik: true });
  });

  it("geçiş ve kilit uçları", async () => {
    await kipApi.gorevliyeGec();
    await kipApi.yoneticiyeGec("Dogru-Parola-1");
    await kipApi.kilitle();
    expect(apiSahte.post.mock.calls).toEqual([
      ["/security/mode/staff/"],
      ["/security/mode/admin/", { password: "Dogru-Parola-1" }],
      ["/security/lock/"],
    ]);
  });
});
