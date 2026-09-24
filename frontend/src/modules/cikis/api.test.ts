// Çık ucu istemcisi: parola yalnız gövdede, etkinlik başlığı gönderilmez.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ETKINLIK_BASLIGI } from "../../lib/api";
import { cikisApi } from "./api";

function yanit(): Response {
  return new Response(JSON.stringify({ durum: "kapaniyor" }), {
    status: 202,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cikisApi", () => {
  it("parolasız çıkış boş gövdeyle POST eder", async () => {
    const fetchSahte = vi.fn().mockResolvedValue(yanit());
    vi.stubGlobal("fetch", fetchSahte);

    await cikisApi.cik();

    const [url, secenek] = fetchSahte.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/app/quit/");
    expect(secenek.method).toBe("POST");
    expect(secenek.body).toBe("{}");
    expect((secenek.headers as Record<string, string>)[ETKINLIK_BASLIGI]).toBeUndefined();
  });

  it("görevli kipinde parola gövdede gider", async () => {
    const fetchSahte = vi.fn().mockResolvedValue(yanit());
    vi.stubGlobal("fetch", fetchSahte);

    await cikisApi.cik("Dogru-Parola-1");

    const [, secenek] = fetchSahte.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(secenek.body))).toEqual({ password: "Dogru-Parola-1" });
  });
});
