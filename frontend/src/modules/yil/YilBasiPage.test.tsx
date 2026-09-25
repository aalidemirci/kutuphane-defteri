// Yıl Başı (F7; tasarım §8.3): ders yılı → e-Okul listeleri → Ayrılış Havuzu → kapalı
// günler. Ekran kayıt yazmaz; her adım işin yapıldığı ekrana bağlanır. "Yıl devri"
// işlemi yoktur.

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { akislar } from "./testVerileri";

const yilApiMock = vi.hoisted(() => ({ akislar: vi.fn() }));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  yilApi: yilApiMock,
}));

import YilBasiPage from "./YilBasiPage";

function ciz() {
  return render(
    <MemoryRouter>
      <YilBasiPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  yilApiMock.akislar.mockResolvedValue(akislar());
});

describe("YilBasiPage", () => {
  it("adımlar sırayla, her biri kendi ekranına bağlanır", async () => {
    const user = userEvent.setup();
    ciz();

    expect(await screen.findByRole("heading", { level: 1, name: "Yıl Başı" })).toBeInTheDocument();
    expect(
      await screen.findByText("Etkin ders yılı: 2026-2027 (07.09.2026 – 25.06.2027)"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ders Yılları'nı aç" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=ders-yillari",
    );

    await user.click(screen.getByRole("button", { name: "Devam" }));
    expect(screen.getByText("Son öğrenci listesi aktarımı: 28.08.2026")).toBeInTheDocument();
    expect(screen.getByText(/Personel listesi: hiç aktarılmadı/)).toBeInTheDocument();
    expect(screen.getByText(/yıl devri işlemi yoktur/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Öğrencileri aç" })).toHaveAttribute(
      "href",
      "/kisiler?tab=ogrenciler",
    );

    await user.click(screen.getByRole("button", { name: "Devam" }));
    expect(screen.getByText(/2 kişi ayrılış kararı bekliyor/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayrılış Havuzu'nu aç" })).toHaveAttribute(
      "href",
      "/kisiler?tab=havuz",
    );

    await user.click(screen.getByRole("button", { name: "Devam" }));
    expect(
      screen.getByText(/2027 yılının resmî tatil ya da dini bayram günleri/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kapalı Günler'i aç" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=kapali-gunler",
    );
    expect(screen.queryByRole("button", { name: "Devam" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Geri" }));
    expect(screen.getByText(/2 kişi ayrılış kararı bekliyor/)).toBeInTheDocument();
  });

  it("tamamlanan adıma raydan dönülür", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText(/Etkin ders yılı/);
    await user.click(screen.getByRole("button", { name: "Devam" }));
    await user.click(screen.getByRole("button", { name: "Devam" }));

    const ray = screen.getByRole("list", { name: "Yıl başı adımları" });
    await user.click(within(ray).getByRole("button", { name: /Ders Yılı/ }));
    expect(screen.getByRole("link", { name: "Ders Yılları'nı aç" })).toBeInTheDocument();
  });

  it("ders yılı açılmamışsa, kademe yoksa ve eski tarih varsa uyarır", async () => {
    yilApiMock.akislar.mockResolvedValue(
      akislar({
        yilBasi: {
          school_year: null,
          school_year_ready: false,
          kademe_missing: true,
          stale_last_loan_dates: true,
        },
      }),
    );
    ciz();

    expect(await screen.findByText("Etkin ders yılı yok.")).toBeInTheDocument();
    expect(screen.getByText(/Bu yılın ders yılı açılmamış/)).toBeInTheDocument();
    expect(screen.getByText(/Okulun kademesi seçilmemiş/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kütüphane Politikası'nı aç" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=politika",
    );
  });
});
