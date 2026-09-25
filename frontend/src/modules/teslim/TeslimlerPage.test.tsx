// Teslimler sayfası (F7): başlık ve geri bağlantısı, üç sekme (adreste `?tab=`),
// teslim ödünç değildir açıklaması.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { sayfa } from "../../test/teslimVerileri";

const teslim = vi.hoisted(() => ({ listele: vi.fn() }));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslim } };
});
const okul = vi.hoisted(() => ({ listSchoolYears: vi.fn(), listClassSections: vi.fn() }));
vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});

import { GERI_ALMA_BASLIGI } from "./GeriAlmaOkutmasi";
import TeslimlerPage, { TESLIMLER_BASLIGI } from "./TeslimlerPage";

function ciz(yol = "/dolasim/teslimler") {
  render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <TeslimlerPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  teslim.listele.mockResolvedValue(sayfa([]));
  okul.listSchoolYears.mockResolvedValue([]);
  okul.listClassSections.mockResolvedValue([]);
});

describe("TeslimlerPage", () => {
  it("başlık, masaya dönüş bağlantısı ve varsayılan sekme", async () => {
    ciz();
    expect(screen.getByRole("heading", { level: 1, name: TESLIMLER_BASLIGI })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dolaşım Masası ana sayfasına dön" })).toHaveAttribute(
      "href",
      "/dolasim",
    );
    expect(screen.getByText(/Teslim ödünç değildir/)).toBeInTheDocument();
    expect(await screen.findByText("Açık teslim yok.")).toBeInTheDocument();
  });

  it("sekmeler arasında geçilir; geri alma sekmesi adresten de açılır", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(screen.getByRole("tab", { name: /Yeni Teslim/ }));
    expect(screen.getByText("Teslim Edilecek Kitaplar")).toBeInTheDocument();
    // Etkin ders yılı yoksa şube seçicisi nereye gidileceğini söyler.
    expect(await screen.findByText(/Etkin ders yılının şubesi yok/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Geri Alma/ }));
    expect(screen.getByText(GERI_ALMA_BASLIGI)).toBeInTheDocument();
  });

  it("?tab=geri-alma doğrudan geri alma okutmasını açar", () => {
    ciz("/dolasim/teslimler?tab=geri-alma");
    expect(screen.getByText(GERI_ALMA_BASLIGI)).toBeInTheDocument();
    expect(screen.getByText("Geri alma dökümü")).toBeInTheDocument();
  });
});
