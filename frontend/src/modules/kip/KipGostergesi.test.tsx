// Kip göstergesi (tasarım §4.4): yönetici kipinde geri sayım + "Görevli kipine
// geç" (kısayol Ctrl+Shift+G) + "Kilitle"; görevli kipinde "Yönetici kipine
// geç" parola diyaloğunu açar; kilitli/kurulum/okunamayan kipte gösterge boştur.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, etkinlikSaatleriniSifirla } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { KILIT_OLAYI } from "../guvenlik/GuvenlikKapisi";
import type { KipAdi, KipOzeti } from "./api";

const kip = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./api", () => ({ kipApi: kip }));

import KipGostergesi, { GOREVLI_KISAYOLU } from "./KipGostergesi";

function ozetOlustur(durum: KipAdi, ek: Partial<KipOzeti> = {}): KipOzeti {
  const yonetici = durum === "yonetici";
  return {
    durum,
    bosta_kalan_sn: yonetici ? 161 : null,
    mutlak_kalan_sn: yonetici ? 1700 : null,
    bosta_dk: 3,
    mutlak_dk: 30,
    ...ek,
  };
}

function bas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SnackbarProvider>
        <KipGostergesi />
      </SnackbarProvider>
    </QueryClientProvider>,
  );
}

function kipGrubu(): HTMLElement {
  return screen.getByRole("group", { name: "Kip" });
}

beforeEach(() => {
  vi.clearAllMocks();
  etkinlikSaatleriniSifirla();
});

describe("KipGostergesi — yönetici kipi", () => {
  it("kip adını, geri sayımı, görevli geçişini ve Kilitle'yi gösterir", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();

    expect(await screen.findByText("Yönetici kipi")).toBeInTheDocument();
    expect(screen.getByTestId("kip-geri-sayim")).toHaveTextContent("2:41");
    const gecis = within(kipGrubu()).getByRole("button", { name: "Görevli kipine geç" });
    expect(gecis).toHaveAttribute("title", `Görevli kipine geç (${GOREVLI_KISAYOLU})`);
    expect(gecis).toHaveAttribute("aria-keyshortcuts", "Control+Shift+G");
    expect(within(kipGrubu()).getByRole("button", { name: "Kilitle" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yönetici kipine geç" })).toBeNull();
  });

  it("geri sayım mutlak süre daha yakınsa onu gösterir", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici", { mutlak_kalan_sn: 65 }));
    bas();
    expect(await screen.findByTestId("kip-geri-sayim")).toHaveTextContent("1:05");
  });

  it("Görevli kipine geç düğmesi parolasız geçer", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    kip.gorevliyeGec.mockResolvedValue(ozetOlustur("gorevli"));
    bas();

    await kullanici.click(await screen.findByRole("button", { name: "Görevli kipine geç" }));

    expect(kip.gorevliyeGec).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Görevli kipi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yönetici kipine geç" })).toBeInTheDocument();
  });

  it("Ctrl+Shift+G kısayolu görevli kipine geçer", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    kip.gorevliyeGec.mockResolvedValue(ozetOlustur("gorevli"));
    bas();
    await screen.findByText("Yönetici kipi");

    fireEvent.keyDown(window, { key: "G", ctrlKey: true, shiftKey: true });

    await waitFor(() => expect(kip.gorevliyeGec).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Görevli kipi")).toBeInTheDocument();
  });

  it("kısayolun eksik biçimleri geçiş yapmaz", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    bas();
    await screen.findByText("Yönetici kipi");

    fireEvent.keyDown(window, { key: "g", ctrlKey: true });
    fireEvent.keyDown(window, { key: "G", shiftKey: true });
    fireEvent.keyDown(window, { key: "G", ctrlKey: true, shiftKey: true, altKey: true });
    fireEvent.keyDown(window, { key: "G", ctrlKey: true, shiftKey: true, repeat: true });

    expect(kip.gorevliyeGec).not.toHaveBeenCalled();
  });

  it("geçiş başarısızsa hata snackbar'da görünür", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    kip.gorevliyeGec.mockRejectedValue(
      new ApiError(409, "kip_gecisi_gecersiz", "Kip yalnız kilit açıkken değiştirilebilir."),
    );
    bas();

    await kullanici.click(await screen.findByRole("button", { name: "Görevli kipine geç" }));

    expect(
      await screen.findByText("Kip yalnız kilit açıkken değiştirilebilir."),
    ).toBeInTheDocument();
  });

  it("Kilitle kilit ucunu çağırır ve kilit olayını yayınlar", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    kip.kilitle.mockResolvedValue({});
    const dinleyici = vi.fn();
    window.addEventListener(KILIT_OLAYI, dinleyici);
    try {
      bas();
      kip.durum.mockResolvedValue(ozetOlustur("kilitli"));
      await kullanici.click(await screen.findByRole("button", { name: "Kilitle" }));

      expect(kip.kilitle).toHaveBeenCalledTimes(1);
      expect(dinleyici).toHaveBeenCalledTimes(1);
      // Kilitlenince gösterge boşalır (kip sorgusu yenilendi).
      await waitFor(() => expect(screen.queryByRole("group", { name: "Kip" })).toBeNull());
    } finally {
      window.removeEventListener(KILIT_OLAYI, dinleyici);
    }
  });

  it("kilitleme başarısızsa hata gösterilir", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("yonetici"));
    kip.kilitle.mockRejectedValue(new Error(""));
    bas();

    await kullanici.click(await screen.findByRole("button", { name: "Kilitle" }));

    expect(await screen.findByText("Kilitlenemedi.")).toBeInTheDocument();
  });

  it("geri sayım sıfırsa kip sunucuya yeniden sorulur", async () => {
    kip.durum
      .mockResolvedValueOnce(ozetOlustur("yonetici", { bosta_kalan_sn: 0 }))
      .mockResolvedValue(ozetOlustur("gorevli"));
    bas();
    expect(await screen.findByText("Görevli kipi")).toBeInTheDocument();
    expect(kip.durum).toHaveBeenCalledTimes(2);
    expect(kip.durum).toHaveBeenLastCalledWith(false);
  });
});

describe("KipGostergesi — görevli kipi", () => {
  it("Yönetici kipine geç parola diyaloğunu açar; doğru parola kipi değiştirir", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    kip.yoneticiyeGec.mockResolvedValue(ozetOlustur("yonetici"));
    bas();

    expect(await screen.findByText("Görevli kipi")).toBeInTheDocument();
    expect(screen.queryByTestId("kip-geri-sayim")).toBeNull();
    expect(screen.queryByRole("button", { name: "Görevli kipine geç" })).toBeNull();

    await kullanici.click(screen.getByRole("button", { name: "Yönetici kipine geç" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yönetici kipine geç" });
    await kullanici.type(within(diyalog).getByLabelText(/Yönetici parolası/), "Dogru-Parola-1");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yönetici kipine geç" }));

    expect(kip.yoneticiyeGec).toHaveBeenCalledWith("Dogru-Parola-1");
    expect(await screen.findByText("Yönetici kipi")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("görevli kipinde kısayol etkisizdir", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    bas();
    await screen.findByText("Görevli kipi");

    fireEvent.keyDown(window, { key: "G", ctrlKey: true, shiftKey: true });

    expect(kip.gorevliyeGec).not.toHaveBeenCalled();
  });

  it("görevli kipinde de Kilitle vardır", async () => {
    kip.durum.mockResolvedValue(ozetOlustur("gorevli"));
    bas();
    await screen.findByText("Görevli kipi");
    expect(within(kipGrubu()).getByRole("button", { name: "Kilitle" })).toBeInTheDocument();
  });
});

describe("KipGostergesi — kilit kapalı ya da okunamayan kip", () => {
  it.each<KipAdi>(["kilitli", "kurulum", "guvenlik_dosyasi_kayip"])(
    "%s durumunda gösterge boştur",
    async (durum) => {
      kip.durum.mockResolvedValue(ozetOlustur(durum));
      bas();
      await waitFor(() => expect(kip.durum).toHaveBeenCalled());
      await act(async () => {});
      expect(screen.queryByRole("group", { name: "Kip" })).toBeNull();
    },
  );

  it("kip okunamazsa gösterge boştur", async () => {
    kip.durum.mockRejectedValue(new Error("ağ yok"));
    bas();
    await waitFor(() => expect(kip.durum).toHaveBeenCalled());
    expect(screen.queryByRole("group", { name: "Kip" })).toBeNull();
  });
});
