// Kişiler → Üyelik İstek Listesi (F6, Md. 17/1): şube seçilmeden liste yok; üye
// olanın kutusu kapalı; "tümünü seç" yalnız üye olmayanları seçer; toplu açma onay
// ister. Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const uyelikApiMock = vi.hoisted(() => ({
  istekListesi: vi.fn(),
  istekleriUygula: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listClassSections: vi.fn() }));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  uyelikApi: uyelikApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));

import IstekListesi from "./IstekListesi";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <IstekListesi />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

const SATIRLAR = [
  {
    student_id: 11,
    full_name: "Deneme Bir",
    student_number: "101",
    class_label: "9/A",
    is_member: false,
    membership_id: null,
  },
  {
    student_id: 12,
    full_name: "Deneme İki",
    student_number: "102",
    class_label: "9/A",
    is_member: true,
    membership_id: 5,
  },
  {
    student_id: 13,
    full_name: "Deneme Üç",
    student_number: "103",
    class_label: "9/A",
    is_member: false,
    membership_id: null,
  },
];

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
    {
      id: 2,
      school_year: 1,
      school_year_name: "2026-2027",
      class_level: 9,
      class_section: "Ç",
      class_label: "9/Ç",
    },
  ]);
  uyelikApiMock.istekListesi.mockResolvedValue(SATIRLAR);
});

describe("IstekListesi", () => {
  it("şube seçilmeden istek atmaz; seçilince şubenin öğrencilerini gösterir", async () => {
    const user = userEvent.setup();
    ciz();

    expect(await screen.findByText("Şube seçin")).toBeInTheDocument();
    expect(uyelikApiMock.istekListesi).not.toHaveBeenCalled();

    await user.selectOptions(await screen.findByLabelText("Şube"), "9|A");

    expect(await screen.findByText("Deneme Bir")).toBeInTheDocument();
    expect(uyelikApiMock.istekListesi).toHaveBeenCalledWith(9, "A");
    expect(screen.getByLabelText("Deneme İki seç")).toBeDisabled();
    expect(screen.getByText("3 öğrenci · 1 üye")).toBeInTheDocument();
  });

  it("tümünü seç yalnız üye olmayanları seçer; toplu açma onaydan geçer", async () => {
    const user = userEvent.setup();
    uyelikApiMock.istekleriUygula.mockResolvedValue([{ id: 7 }, { id: 8 }]);
    ciz();
    await user.selectOptions(await screen.findByLabelText("Şube"), "9|A");
    await screen.findByText("Deneme Bir");

    await user.click(screen.getByLabelText("Üye olmayanların tümünü seç"));
    await user.click(screen.getByRole("button", { name: /Seçilenleri üye yap \(2\)/ }));
    const onay = await screen.findByRole("dialog", { name: "2 öğrenciye üyelik açılsın mı?" });
    expect(onay).toHaveTextContent("isteğe bağlıdır");
    await user.click(within(onay).getByRole("button", { name: "Üyelik aç" }));

    await waitFor(() =>
      expect(uyelikApiMock.istekleriUygula).toHaveBeenCalledWith([11, 13], expect.any(String)),
    );
    expect(await screen.findByText("2 öğrenciye üyelik açıldı.")).toBeInTheDocument();
  });

  it("seçim yokken düğme kapalıdır", async () => {
    ciz();
    expect(await screen.findByRole("button", { name: "Seçilenleri üye yap" })).toBeDisabled();
  });
});
