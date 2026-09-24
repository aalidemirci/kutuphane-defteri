// Genel Bakış'ın dolaşım kartları (F6; A11, T15): gecikme kartı yalnız sayı taşır
// ve sayfaya bağlanır; beklenmedik kapanış kartı son işlemleri listeler ve
// "Kontrol ettim" ile kapanır. Pano sorguları kullanıcı eylemi değildir.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const uyelikApiMock = vi.hoisted(() => ({
  dolasimOzeti: vi.fn(),
  sonIslemler: vi.fn(),
  kontrolEttim: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  uyelikApi: uyelikApiMock,
}));

import DolasimKartlari from "./DolasimKartlari";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <DolasimKartlari />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  uyelikApiMock.sonIslemler.mockResolvedValue([
    {
      kind: "RETURN",
      kind_display: "İade alındı",
      at: "2026-09-23T15:10:00+03:00",
      loan_id: 4,
      barcode_display: "2026-000004",
      work_title: "Deneme Kaynağı",
      full_name: "Deneme Öğrenci",
      person_label: "9/A",
    },
  ]);
});

describe("DolasimKartlari", () => {
  it("gecikme ve kapanış yoksa hiçbir kart görünmez", async () => {
    uyelikApiMock.dolasimOzeti.mockResolvedValue({ overdue_count: 0, unexpected_shutdown: false });
    const { container } = ciz();
    await waitFor(() => expect(uyelikApiMock.dolasimOzeti).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(uyelikApiMock.sonIslemler).not.toHaveBeenCalled();
  });

  it("gecikme kartı yalnız sayıyı yazar ve Gecikmiş Ödünçler sayfasına bağlanır", async () => {
    uyelikApiMock.dolasimOzeti.mockResolvedValue({ overdue_count: 12, unexpected_shutdown: false });
    ciz();

    expect(await screen.findByRole("heading", { name: "Gecikmiş Ödünçler" })).toBeInTheDocument();
    expect(screen.getByText("12 ödüncün iade tarihi geçti.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gecikmiş Ödünçler'i aç" })).toHaveAttribute(
      "href",
      "/gecikmis-oduncler",
    );
  });

  it("beklenmedik kapanışta son işlemler listelenir; Kontrol ettim kartı kapatır", async () => {
    const user = userEvent.setup();
    uyelikApiMock.dolasimOzeti.mockResolvedValue({ overdue_count: 0, unexpected_shutdown: true });
    uyelikApiMock.kontrolEttim.mockResolvedValue({ overdue_count: 0, unexpected_shutdown: false });
    ciz();

    expect(
      await screen.findByRole("heading", { name: "Son Oturumu Kontrol Edin" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("İade alındı · Deneme Kaynağı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kontrol ettim" }));

    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Son Oturumu Kontrol Edin" })).toBeNull(),
    );
    expect(uyelikApiMock.kontrolEttim).toHaveBeenCalledTimes(1);
  });

  it("özet okunamazsa kart gösterilmez", async () => {
    uyelikApiMock.dolasimOzeti.mockRejectedValue(new Error("çevrimdışı"));
    const { container } = ciz();
    await waitFor(() => expect(uyelikApiMock.dolasimOzeti).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
