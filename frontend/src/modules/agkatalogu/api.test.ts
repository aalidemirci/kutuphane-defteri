// Ağ Kataloğu istemcisi: uç adresleri ve yöntemleri backend ile birebir; durum
// yoklaması yönetici kipinin boşta sayacını tazelemez; adres sorgusu kodlanır.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ETKINLIK_BASLIGI } from "../../lib/api";
import {
  agKataloguApi,
  agProfiliAdi,
  belgeDosyaAdi,
  katalogKapatilabilir,
  kuralProfiliAdi,
} from "./api";
import { katalogVerisi } from "../../test/agKataloguVerileri";

function jsonYanit(govde: unknown = {}): Response {
  return new Response(JSON.stringify(govde), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function sahteFetch(yanit: Response = jsonYanit()) {
  const fetchSahte = vi.fn().mockResolvedValue(yanit);
  vi.stubGlobal("fetch", fetchSahte);
  return fetchSahte;
}

function cagri(fetchSahte: ReturnType<typeof vi.fn>, sira = 0): [string, RequestInit] {
  return fetchSahte.mock.calls[sira] as [string, RequestInit];
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("agKataloguApi", () => {
  it("durum GET'tir ve etkinlik başlığı taşımaz (periyodik yenileme)", async () => {
    const fetchSahte = sahteFetch();
    window.dispatchEvent(new Event("pointerdown"));

    await agKataloguApi.durum();

    const [url, secenek] = cagri(fetchSahte);
    expect(url).toBe("/api/v1/library/network-catalog/status/");
    expect(secenek.method).toBe("GET");
    expect((secenek.headers as Record<string, string>)[ETKINLIK_BASLIGI]).toBeUndefined();
  });

  it("eylem, kural, sınama ve port POST'tur", async () => {
    const fetchSahte = sahteFetch();

    await agKataloguApi.eylem("ac");
    const [url, secenek] = cagri(fetchSahte);
    expect(url).toBe("/api/v1/library/network-catalog/control/");
    expect(secenek.method).toBe("POST");
    expect(JSON.parse(String(secenek.body))).toEqual({ eylem: "ac" });

    fetchSahte.mockResolvedValue(jsonYanit());
    await agKataloguApi.portDegistir(9100);
    expect(cagri(fetchSahte, 1)[0]).toBe("/api/v1/library/network-catalog/port/");
    expect(JSON.parse(String(cagri(fetchSahte, 1)[1].body))).toEqual({ port: 9100 });

    fetchSahte.mockResolvedValue(jsonYanit());
    await agKataloguApi.kuralGuncelle();
    expect(cagri(fetchSahte, 2)[0]).toBe("/api/v1/library/network-catalog/firewall-rule/");

    fetchSahte.mockResolvedValue(jsonYanit());
    await agKataloguApi.dinleyiciSinamasi();
    expect(cagri(fetchSahte, 3)[0]).toBe("/api/v1/library/network-catalog/listener-test/");
  });

  it("okuma uçları GET'tir", async () => {
    const fetchSahte = sahteFetch();
    await agKataloguApi.guvenlikDuvari();
    fetchSahte.mockResolvedValue(jsonYanit());
    await agKataloguApi.arayuzler();
    fetchSahte.mockResolvedValue(jsonYanit());
    await agKataloguApi.ayar();

    expect(fetchSahte.mock.calls.map((c) => c[0])).toEqual([
      "/api/v1/library/network-catalog/firewall/",
      "/api/v1/library/network-catalog/interfaces/",
      "/api/v1/library/network-catalog/settings/",
    ]);
  });

  it("ayar kaydı kısmi PUT'tur", async () => {
    const fetchSahte = sahteFetch();

    await agKataloguApi.ayarKaydet({ vitrin_acik: false });

    const [url, secenek] = cagri(fetchSahte);
    expect(url).toBe("/api/v1/library/network-catalog/settings/");
    expect(secenek.method).toBe("PUT");
    expect(JSON.parse(String(secenek.body))).toEqual({ vitrin_acik: false });
  });

  it("afiş POST ile, belgeler GET ile ve seçili adresle istenir", async () => {
    const fetchSahte = sahteFetch(new Response(new Blob(["%PDF"]), { status: 200 }));

    await agKataloguApi.afis("10.20.30.40");
    expect(cagri(fetchSahte)[0]).toBe("/api/v1/library/network-catalog/poster/");
    expect(cagri(fetchSahte)[1].method).toBe("POST");
    expect(JSON.parse(String(cagri(fetchSahte)[1].body))).toEqual({ ip: "10.20.30.40" });

    fetchSahte.mockResolvedValue(new Response(new Blob(["%PDF"]), { status: 200 }));
    await agKataloguApi.bilgiNotu();
    expect(cagri(fetchSahte, 1)[0]).toBe("/api/v1/library/network-catalog/info-note/");

    fetchSahte.mockResolvedValue(new Response(new Blob(["PK"]), { status: 200 }));
    await agKataloguApi.yerImleri("10.20.30.40");
    expect(cagri(fetchSahte, 2)[0]).toBe(
      "/api/v1/library/network-catalog/bookmarks/?ip=10.20.30.40",
    );

    fetchSahte.mockResolvedValue(jsonYanit({ metin: "Konu" }));
    await expect(agKataloguApi.pysMetni()).resolves.toEqual({ metin: "Konu" });
    expect(cagri(fetchSahte, 3)[0]).toBe("/api/v1/library/network-catalog/pys-text/");
  });

  it("afiş adressiz istenince gövde boştur (adresi sunucu seçer)", async () => {
    const fetchSahte = sahteFetch(new Response(new Blob(["%PDF"]), { status: 200 }));

    await agKataloguApi.afis();

    expect(cagri(fetchSahte)[1].body).toBe("{}");
  });
});

describe("yardımcılar", () => {
  it("belge dosya adı belge adı + yerel tarih taşır", () => {
    expect(belgeDosyaAdi("Katalog Afişi", "pdf")).toMatch(
      /^Katalog-Afişi_\d{2}\.\d{2}\.\d{4}\.pdf$/,
    );
  });

  it("ağ profili adları Türkçedir", () => {
    expect(agProfiliAdi("Public")).toBe("Genel");
    expect(agProfiliAdi("DomainAuthenticated")).toBe("Etki alanı");
    expect(agProfiliAdi(null)).toBe("Bilinmiyor");
    expect(agProfiliAdi("Tuhaf")).toBe("Tuhaf");
  });

  it("kural profili Windows değerinden Türkçeye çevrilir", () => {
    expect(kuralProfiliAdi("Domain, Private, Public")).toBe("Etki alanı, Özel, Genel");
    expect(kuralProfiliAdi("Any")).toBe("Hepsi (Etki alanı, Özel, Genel)");
    expect(kuralProfiliAdi("Private;Public")).toBe("Özel, Genel");
    expect(kuralProfiliAdi("")).toBe("—");
    expect(kuralProfiliAdi(null)).toBe("—");
  });

  it("ayar açık ve katalog kapalı ya da geri yüklemede değilse kapatılabilir", () => {
    expect(katalogKapatilabilir(katalogVerisi({ durum: "engellendi", ayar_acik: true }))).toBe(
      true,
    );
    expect(katalogKapatilabilir(katalogVerisi({ durum: "bekliyor", ayar_acik: true }))).toBe(true);
    expect(katalogKapatilabilir(katalogVerisi({ durum: "hata", ayar_acik: false }))).toBe(false);
    expect(katalogKapatilabilir(katalogVerisi({ durum: "kapali", ayar_acik: true }))).toBe(false);
    expect(katalogKapatilabilir(katalogVerisi({ durum: "bakim", ayar_acik: true }))).toBe(false);
    expect(katalogKapatilabilir(null)).toBe(false);
  });
});
