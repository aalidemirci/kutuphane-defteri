// Çık (tasarım §4.2-4, §5.10-18, TB13): üst çubuktaki düğme her durumda görünür;
// yönetici kipinde ve kilitliyken parolasız onay, görevli kipinde yönetici
// parolası. Sunucu parola isterse (kip bu arada değişti) diyalog parola alanına
// geçer. Tepsideki görevli kipi Çık'ı `kd:cik-iste` olayıyla diyaloğu açar.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import type { KipAdi } from "../kip/api";

const cikis = vi.hoisted(() => ({ cik: vi.fn() }));
const kip = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./api", async (orijinal) => ({
  ...(await orijinal<typeof import("./api")>()),
  cikisApi: cikis,
}));
vi.mock("../kip/api", () => ({ kipApi: kip }));

import CikisDugmesi, { CikisDiyalogu, DogrudanCikisDugmesi } from "./CikisDugmesi";
import { CIKIS_ISTEK_OLAYI } from "./api";

function ozet(durum: KipAdi) {
  return { durum, bosta_kalan_sn: null, mutlak_kalan_sn: null, bosta_dk: 3, mutlak_dk: 30 };
}

function bas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <CikisDugmesi />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CikisDugmesi", () => {
  it("yönetici kipinde parolasız onayla çıkar", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("yonetici"));
    cikis.cik.mockResolvedValue({ durum: "kapaniyor" });
    bas();

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    const diyalog = screen.getByRole("dialog");
    expect(diyalog).toHaveTextContent("Ağ Kataloğu da kapanır");
    expect(within(diyalog).queryByLabelText(/Yönetici parolası/)).toBeNull();
    await kullanici.click(within(diyalog).getByRole("button", { name: "Çık" }));

    expect(cikis.cik).toHaveBeenCalledWith(undefined);
    expect(await screen.findByRole("status")).toHaveTextContent("kapanıyor");
  });

  it("görevli kipinde yönetici parolası ister ve parolayı gövdede gönderir", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("gorevli"));
    cikis.cik.mockResolvedValue({ durum: "kapaniyor" });
    bas();
    await screen.findByRole("button", { name: "Çık" });
    await act(async () => {
      await Promise.resolve();
    });

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    const diyalog = await screen.findByRole("dialog");
    const gonder = within(diyalog).getByRole("button", { name: "Çık" });
    expect(await within(diyalog).findByLabelText(/Yönetici parolası/)).toHaveAttribute(
      "type",
      "password",
    );
    expect(gonder).toBeDisabled();

    await kullanici.type(within(diyalog).getByLabelText(/Yönetici parolası/), "Dogru-Parola-1");
    await kullanici.click(gonder);

    expect(cikis.cik).toHaveBeenCalledWith("Dogru-Parola-1");
    expect(await screen.findByRole("status")).toHaveTextContent("kapanıyor");
  });

  it("yanlış parolada iletiyi gösterir, diyalog açık kalır", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("gorevli"));
    cikis.cik.mockRejectedValue(new ApiError(400, "validation_error", "Parola hatalı."));
    bas();
    await act(async () => {
      await Promise.resolve();
    });

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    const diyalog = await screen.findByRole("dialog");
    await kullanici.type(await within(diyalog).findByLabelText(/Yönetici parolası/), "yanlis");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Çık" }));

    expect(await within(diyalog).findByRole("alert")).toHaveTextContent("Parola hatalı.");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("sunucu parola isterse (kip görevliye indi) parola alanına geçer", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("yonetici"));
    cikis.cik.mockRejectedValueOnce(
      new ApiError(
        403,
        "cikis_parolasi_gerekli",
        "Görevli kipinde programdan çıkmak için yönetici parolasını girin.",
      ),
    );
    bas();

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    const diyalog = screen.getByRole("dialog");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Çık" }));

    const alan = await within(diyalog).findByLabelText(/Yönetici parolası/);
    // Alan pencere açıkken belirdi: odak ona taşınır.
    await waitFor(() => expect(alan).toHaveFocus());
  });

  // `autoFocus` ortak Dialog'un panel odağına yeniliyordu; parola alanı
  // `initialFocusRef` ile odaklanır (tasarım §14.1 F6 ekleri 23).
  it("görevli kipinde açılışta parola alanı odaktadır", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("gorevli"));
    bas();
    await act(async () => {
      await Promise.resolve();
    });

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    const diyalog = await screen.findByRole("dialog");
    const alan = await within(diyalog).findByLabelText(/Yönetici parolası/);
    await waitFor(() => expect(alan).toHaveFocus());
  });

  it("parola isteyen pencere doğrudan açıldığında alan ilk anda odaktadır", () => {
    render(<CikisDiyalogu open onClose={vi.fn()} parolaIle />);
    expect(screen.getByLabelText(/Yönetici parolası/)).toHaveFocus();
  });

  it("tepsinin kd:cik-iste olayı diyaloğu açar", async () => {
    kip.durum.mockResolvedValue(ozet("gorevli"));
    bas();
    expect(screen.queryByRole("dialog")).toBeNull();

    act(() => {
      window.dispatchEvent(new Event(CIKIS_ISTEK_OLAYI));
    });

    expect(await screen.findByRole("dialog")).toHaveTextContent("Programdan çık");
    expect(CIKIS_ISTEK_OLAYI).toBe("kd:cik-iste");
  });

  it("kilitliyken de görünür ve parolasızdır", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("kilitli"));
    bas();

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));

    expect(within(screen.getByRole("dialog")).queryByLabelText(/Yönetici parolası/)).toBeNull();
  });

  it("Vazgeç diyaloğu kapatır, istek gitmez", async () => {
    const kullanici = userEvent.setup();
    kip.durum.mockResolvedValue(ozet("yonetici"));
    bas();

    await kullanici.click(screen.getByRole("button", { name: "Çık" }));
    await kullanici.click(screen.getByRole("button", { name: "Vazgeç" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(cikis.cik).not.toHaveBeenCalled();
  });
});

describe("DogrudanCikisDugmesi", () => {
  it("yeniden başlat ekranında parolasız çıkar", async () => {
    const kullanici = userEvent.setup();
    cikis.cik.mockResolvedValue({ durum: "kapaniyor" });
    render(<DogrudanCikisDugmesi />);

    await kullanici.click(screen.getByRole("button", { name: "Programdan çık" }));

    expect(cikis.cik).toHaveBeenCalledWith();
    expect(await screen.findByRole("status")).toHaveTextContent("kapanıyor");
  });

  it("masaüstü dışında (geliştirme) hatayı gösterir", async () => {
    const kullanici = userEvent.setup();
    cikis.cik.mockRejectedValue(
      new ApiError(503, "cikis_kullanilamiyor", "Program masaüstü penceresinde çalışmıyor."),
    );
    render(<DogrudanCikisDugmesi />);

    await kullanici.click(screen.getByRole("button", { name: "Programdan çık" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("masaüstü penceresinde");
  });
});
