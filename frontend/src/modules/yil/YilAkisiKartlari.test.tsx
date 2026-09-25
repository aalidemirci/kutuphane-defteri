// Genel Bakış'ın yıl akışı kartları (F7): tarih penceresinde görünür, yalnız sayı yazar;
// yıl başı adımları tamamsa kart çıkmaz; özet okunamazsa hiçbir şey çizilmez.

import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { akislar } from "./testVerileri";

const yilApiMock = vi.hoisted(() => ({ akislar: vi.fn() }));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  yilApi: yilApiMock,
}));

import YilAkisiKartlari from "./YilAkisiKartlari";

function ciz() {
  return render(
    <MemoryRouter>
      <YilAkisiKartlari />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("YilAkisiKartlari", () => {
  it("yıl sonu penceresinde yalnız sayılarla kart", async () => {
    yilApiMock.akislar.mockResolvedValue(akislar());
    ciz();

    expect(await screen.findByRole("heading", { name: "Yıl Sonu" })).toBeInTheDocument();
    expect(
      screen.getByText("9 açık ödünç; kütüphaneyle açık işi olan 5 kişi (son sınıflarda 3)."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Yıl Sonu'nu aç" })).toHaveAttribute(
      "href",
      "/yil-sonu",
    );
    expect(screen.queryByRole("heading", { name: "Yıl Başı" })).not.toBeInTheDocument();
  });

  it("yıl başı penceresinde bekleyen adım sayısı; adımlar tamamsa kart yok", async () => {
    yilApiMock.akislar.mockResolvedValue(
      akislar({ yilSonu: { in_window: false }, yilBasi: { in_window: true } }),
    );
    const { unmount } = ciz();

    expect(await screen.findByRole("heading", { name: "Yıl Başı" })).toBeInTheDocument();
    expect(screen.getByText("Yeni ders yılı için 2 adım bekliyor.")).toBeInTheDocument();
    unmount();

    yilApiMock.akislar.mockResolvedValue(
      akislar({
        yilSonu: { in_window: false },
        yilBasi: {
          in_window: true,
          steps: { school_year: true, import: true, leave_pool: true, closed_days: true },
        },
      }),
    );
    ciz();
    await act(async () => {
      await Promise.resolve();
    });
    expect(yilApiMock.akislar).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("heading", { name: "Yıl Başı" })).not.toBeInTheDocument();
  });

  it("açık iş yoksa ve ders yılı açılmamışsa metinler", async () => {
    const veri = akislar({ yilBasi: { in_window: true, school_year_ready: false } });
    veri.year_end.counts.persons = 0;
    yilApiMock.akislar.mockResolvedValue(veri);
    ciz();

    expect(await screen.findByText("Kütüphaneyle açık işi olan kimse yok.")).toBeInTheDocument();
    expect(screen.getByText("Bu yılın ders yılı henüz açılmadı.")).toBeInTheDocument();
  });

  it("pencere dışında ya da özet okunamazsa kart yok", async () => {
    yilApiMock.akislar.mockRejectedValue(new Error("x"));
    const { container } = ciz();
    await act(async () => {
      await Promise.resolve();
    });
    expect(yilApiMock.akislar).toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });
});
