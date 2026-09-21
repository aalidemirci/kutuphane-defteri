// Kip kapısı + görevli ekranı (tasarım §4.4): görevli kipinde içerik yerine
// sade görevli ekranı durur; yönetici kipinde ve kip okunamazsa (fail-open)
// içerik görünür; görevli ekranından parolayla yönetici kipine dönülür.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KipAdi, KipOzeti } from "./api";

const kip = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./api", () => ({ kipApi: kip }));

import { GOREVLI_EKRANI_METNI } from "./GorevliEkrani";
import KipKapisi from "./KipKapisi";

function ozetOlustur(durum: KipAdi): KipOzeti {
  const yonetici = durum === "yonetici";
  return {
    durum,
    bosta_kalan_sn: yonetici ? 180 : null,
    mutlak_kalan_sn: yonetici ? 1800 : null,
    bosta_dk: 3,
    mutlak_dk: 30,
  };
}

function bas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <KipKapisi>
        <p>Yönetici içeriği</p>
      </KipKapisi>
    </QueryClientProvider>,
  );
}

describe("KipKapisi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("görevli kipinde içerik yerine görevli ekranını gösterir", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    bas();

    expect(await screen.findByRole("heading", { level: 1, name: "Görevli Kipi" })).toBeVisible();
    expect(screen.getByText(GOREVLI_EKRANI_METNI)).toBeInTheDocument();
    expect(GOREVLI_EKRANI_METNI).toBe(
      "Bu kipte yalnız masa işleri yapılır; yönetici işlemleri için yönetici kipine geçin.",
    );
    expect(screen.queryByText("Yönetici içeriği")).toBeNull();
  });

  it("yönetici kipinde içeriği gösterir", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    await waitFor(() => expect(kip.durum).toHaveBeenCalled());
    expect(screen.getByText("Yönetici içeriği")).toBeInTheDocument();
  });

  it("kip okunamazsa içerik gösterilir (fail-open)", async () => {
    kip.durum.mockRejectedValue(new Error("ağ yok"));
    bas();
    await waitFor(() => expect(kip.durum).toHaveBeenCalled());
    expect(screen.getByText("Yönetici içeriği")).toBeInTheDocument();
  });

  it("görevli ekranından yönetici parolasıyla içeriğe dönülür", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    kip.yoneticiyeGec.mockResolvedValue(ozetOlustur("yonetici"));
    bas();

    await kullanici.click(await screen.findByRole("button", { name: "Yönetici kipine geç" }));
    const diyalog = screen.getByRole("dialog", { name: "Yönetici kipine geç" });
    await kullanici.type(within(diyalog).getByLabelText(/Yönetici parolası/), "Dogru-Parola-1");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yönetici kipine geç" }));

    expect(await screen.findByText("Yönetici içeriği")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Görevli Kipi" })).toBeNull();
  });
});
