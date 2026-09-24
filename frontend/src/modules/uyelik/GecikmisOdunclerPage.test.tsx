// Gecikmiş Ödünçler (F6, E4): kişi sırasıyla liste (ad kişinin ilk satırında),
// seçilen kişilerin pusulası, seçim yoksa kapsamın pusulası, dipnotlu toplu liste.
// Uzatma/ceza/harç dili yok. Bütün adlar uydurmadır.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { gecikmeSatiri, sayfa } from "./testVerileri";

const uyelikApiMock = vi.hoisted(() => ({
  gecikmisOduncler: vi.fn(),
  pusulaPdf: vi.fn(),
  gecikmeListesiPdf: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listClassSections: vi.fn() }));
const saveBlobMock = vi.hoisted(() => vi.fn());

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  uyelikApi: uyelikApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import GecikmisOdunclerPage from "./GecikmisOdunclerPage";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <GecikmisOdunclerPage />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  okulApiMock.listClassSections.mockResolvedValue([
    {
      id: 1,
      school_year: 1,
      school_year_name: "2026-2027",
      class_level: 9,
      class_section: "A",
      class_label: "9/A",
    },
  ]);
  uyelikApiMock.gecikmisOduncler.mockResolvedValue(
    sayfa([
      gecikmeSatiri({ id: 1, membership_id: 4, full_name: "Deneme Bir", work_title: "Kaynak A" }),
      gecikmeSatiri({ id: 2, membership_id: 4, full_name: "Deneme Bir", work_title: "Kaynak B" }),
      gecikmeSatiri({
        id: 3,
        membership_id: 6,
        full_name: "Ayla Deneme",
        person_label: "Öğretmen",
        is_student: false,
        overdue_days: 20,
      }),
    ]),
  );
  uyelikApiMock.pusulaPdf.mockResolvedValue(new Blob(["%PDF"]));
  uyelikApiMock.gecikmeListesiPdf.mockResolvedValue(new Blob(["%PDF"]));
});

describe("GecikmisOdunclerPage", () => {
  it("başlık, kişi sırası ve gün sayısı; uzatma, ceza ve harç dili yok", async () => {
    ciz();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Gecikmiş Ödünçler" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Kaynak B")).toBeInTheDocument();
    expect(screen.getAllByText("Deneme Bir")).toHaveLength(1);
    expect(screen.getByText("20 gün gecikti")).toBeInTheDocument();
    expect(screen.getByText(/Kişisel veri içerir — asılmaz, çoğaltılmaz\./)).toBeInTheDocument();
    const metin = document.body.textContent ?? "";
    expect(metin).not.toMatch(/ceza tutarı|harç tutarı|süreyi uzat/i);
  });

  it("seçilen kişinin pusulası üyelik kimliğiyle istenir", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Kaynak B");

    await user.click(screen.getByLabelText("Ayla Deneme seç"));
    expect(screen.getByText(/yalnız seçilen 1 kişiye basılır/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "PDF'i indir" })[0]);

    await waitFor(() =>
      expect(uyelikApiMock.pusulaPdf).toHaveBeenCalledWith({ membershipIds: [6] }),
    );
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^İade-Hatırlatma-Pusulası_/),
    );
  });

  it("seçim yokken pusula ve toplu liste şube kapsamıyla istenir", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Kaynak B");
    await user.selectOptions(await screen.findByLabelText("Şube"), "9|A");
    await waitFor(() =>
      expect(uyelikApiMock.gecikmisOduncler).toHaveBeenLastCalledWith(
        expect.objectContaining({ classLevel: 9, classSection: "A" }),
      ),
    );
    await screen.findByText("Kaynak B");

    const indirler = screen.getAllByRole("button", { name: "PDF'i indir" });
    await user.click(indirler[0]);
    await waitFor(() =>
      expect(uyelikApiMock.pusulaPdf).toHaveBeenCalledWith({ classLevel: 9, classSection: "A" }),
    );
    await user.click(indirler[1]);
    await waitFor(() =>
      expect(uyelikApiMock.gecikmeListesiPdf).toHaveBeenCalledWith({
        classLevel: 9,
        classSection: "A",
      }),
    );
  });

  it("gecikme yoksa boş durum ve kapalı düğmeler", async () => {
    uyelikApiMock.gecikmisOduncler.mockResolvedValue(sayfa([]));
    ciz();
    expect(await screen.findByText("Gecikmiş ödünç yok.")).toBeInTheDocument();
    for (const dugme of screen.getAllByRole("button", { name: "PDF'i indir" })) {
      expect(dugme).toBeDisabled();
    }
  });
});
