// Kip sorgusu ve görsel geri sayım (tasarım §4.4). Pinlenen davranışlar:
// yoklama `X-KD-Etkinlik` TAŞIMAZ (etkinlik:false); 403 `kip_yetkisiz` ve
// kilitleme olayları sorguyu yeniler; geri sayım boşta ve mutlak sürenin
// küçüğüdür ve özetten sonra giden başlıklı istek boşta sayacını tazeler;
// etkinlik nabzı yalnız gerçek etkileşimle ve seyrek gider.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { etkinlikSaatleriniSifirla } from "../../lib/api";
import { kipYetkisizYayinla } from "../../lib/kip";
import { kilitOlayiYayinla } from "../guvenlik/GuvenlikKapisi";
import type { KipAdi, KipOzeti } from "./api";

const kip = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./api", () => ({ kipApi: kip }));

import { kalanSaniye, sureBicimle, useEtkinlikNabzi, useKip } from "./useKip";

function ozetOlustur(durum: KipAdi, ek: Partial<KipOzeti> = {}): KipOzeti {
  const yonetici = durum === "yonetici";
  return {
    durum,
    bosta_kalan_sn: yonetici ? 180 : null,
    mutlak_kalan_sn: yonetici ? 1800 : null,
    bosta_dk: 3,
    mutlak_dk: 30,
    ...ek,
  };
}

function KipYazici() {
  const { ozet } = useKip();
  useEtkinlikNabzi(ozet?.durum, () => {});
  return <p>kip: {ozet?.durum ?? "yok"}</p>;
}

function bas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <KipYazici />
    </QueryClientProvider>,
  );
}

describe("kalanSaniye", () => {
  const T0 = 1_000_000;

  it("boşta ve mutlak sürenin küçüğünü, geçen süreyi düşerek verir", () => {
    const ozet = ozetOlustur("yonetici", { bosta_kalan_sn: 161, mutlak_kalan_sn: 1000 });
    expect(kalanSaniye(ozet, T0, T0, -Infinity)).toBe(161);
    expect(kalanSaniye(ozet, T0, T0 + 60_000, -Infinity)).toBe(101);
    expect(kalanSaniye(ozet, T0, T0 + 500_000, -Infinity)).toBe(0);
  });

  it("mutlak süre daha yakınsa onu gösterir", () => {
    const ozet = ozetOlustur("yonetici", { bosta_kalan_sn: 180, mutlak_kalan_sn: 40 });
    expect(kalanSaniye(ozet, T0, T0 + 10_000, -Infinity)).toBe(30);
  });

  it("özetten sonra giden başlıklı istek boşta sayacını tazeler", () => {
    const ozet = ozetOlustur("yonetici", { bosta_kalan_sn: 100, mutlak_kalan_sn: 1800 });
    // 90 sn sonra bir kullanıcı eylemi gitti; 10 sn daha geçti.
    expect(kalanSaniye(ozet, T0, T0 + 100_000, T0 + 90_000)).toBe(170);
    // Eylem özetten ÖNCE gittiyse sunucu onu zaten saymıştır.
    expect(kalanSaniye(ozet, T0, T0 + 10_000, T0 - 5_000)).toBe(90);
  });

  it("yönetici kipi dışında boştur", () => {
    expect(kalanSaniye(ozetOlustur("gorevli"), T0, T0, -Infinity)).toBeNull();
    expect(kalanSaniye(ozetOlustur("kilitli"), T0, T0, -Infinity)).toBeNull();
  });
});

describe("sureBicimle", () => {
  it.each([
    [0, "0:00"],
    [9, "0:09"],
    [161, "2:41"],
    [1800, "30:00"],
  ])("%i sn → %s", (saniye, beklenen) => {
    expect(sureBicimle(saniye)).toBe(beklenen);
  });
});

describe("useKip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    etkinlikSaatleriniSifirla();
  });

  it("yoklama etkinlik başlığı olmadan gider (etkinlik:false)", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    expect(await screen.findByText("kip: yonetici")).toBeInTheDocument();
    expect(kip.durum).toHaveBeenCalledWith(false);
  });

  it("403 kip_yetkisiz olayı sorguyu yeniler", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    await screen.findByText("kip: yonetici");
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    act(() => kipYetkisizYayinla());
    expect(await screen.findByText("kip: gorevli")).toBeInTheDocument();
  });

  it("kilitleme olayı sorguyu yeniler", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    await screen.findByText("kip: yonetici");
    kip.durum.mockResolvedValue(ozetOlustur("kilitli"));
    act(() => kilitOlayiYayinla());
    expect(await screen.findByText("kip: kilitli")).toBeInTheDocument();
  });

  it("sorgu hatasında özet boştur (fail-open)", async () => {
    kip.durum.mockRejectedValue(new Error("ağ yok"));
    bas();
    await waitFor(() => expect(kip.durum).toHaveBeenCalled());
    expect(screen.getByText("kip: yok")).toBeInTheDocument();
  });
});

describe("useEtkinlikNabzi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    etkinlikSaatleriniSifirla();
  });

  it("yönetici kipinde etkileşim nabız gönderir, hemen ikincisi gönderilmez", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    await screen.findByText("kip: yonetici");
    kip.durum.mockClear();

    act(() => {
      window.dispatchEvent(new Event("pointerdown"));
      window.dispatchEvent(new Event("keydown"));
    });

    await waitFor(() => expect(kip.durum).toHaveBeenCalledTimes(1));
    expect(kip.durum).toHaveBeenCalledWith(true);
  });

  it("görevli kipinde nabız gönderilmez", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    bas();
    await screen.findByText("kip: gorevli");
    kip.durum.mockClear();

    act(() => window.dispatchEvent(new Event("pointerdown")));

    expect(kip.durum).not.toHaveBeenCalled();
  });
});
