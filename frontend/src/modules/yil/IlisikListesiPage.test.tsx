// İlişik Listesi (F7, E5): son sınıflar ve ayrılanlar önce gelen liste, süzgeçler,
// sınıf kitaplıkları, dipnotlu toplu liste ve "Kütüphaneden ilişiği yoktur" belgesi
// (yalnız açık işi olmayan kişi seçilebilir). Belge başka bir işlemin ön koşulu diye
// sunulmaz. Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { ilisikSatiri, sayfa, sinifKitapligi, temizSatir } from "./testVerileri";

const yilApiMock = vi.hoisted(() => ({
  ilisikListesi: vi.fn(),
  ilisikListesiPdf: vi.fn(),
  ilisikBelgesiPdf: vi.fn(),
  sinifKitapliklari: vi.fn(),
  sinifKitapligiListesiPdf: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listClassSections: vi.fn() }));
const saveBlobMock = vi.hoisted(() => vi.fn());

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  yilApi: yilApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import IlisikListesiPage from "./IlisikListesiPage";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <IlisikListesiPage />
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
      class_level: 12,
      class_section: "A",
      class_label: "12/A",
    },
  ]);
  yilApiMock.ilisikListesi.mockResolvedValue(
    sayfa([
      ilisikSatiri({ person_id: 1, full_name: "Deneme Mezun" }),
      ilisikSatiri({
        person_type: "personnel",
        person_id: 7,
        full_name: "Deneme Hoca",
        person_label: "Öğretmen",
        student_number: "",
        group: "leaving",
        is_graduating: false,
        status_text: "Ayrıldı · 12.06.2027",
        open_loan_count: 0,
        loans: [],
        open_delivery_count: 1,
        deliveries: [
          {
            id: 21,
            barcode: "2026000021",
            barcode_display: "2026-000021",
            work_title: "Sınıf Kaynağı",
            delivered_on: "2026-10-01",
            expected_return: "2027-06-25",
            document_no: "2026/3",
          },
        ],
      }),
    ]),
  );
  yilApiMock.sinifKitapliklari.mockResolvedValue([sinifKitapligi()]);
  yilApiMock.ilisikListesiPdf.mockResolvedValue(new Blob(["%PDF"]));
  yilApiMock.ilisikBelgesiPdf.mockResolvedValue(new Blob(["%PDF"]));
  yilApiMock.sinifKitapligiListesiPdf.mockResolvedValue(new Blob(["%PDF"]));
});

describe("IlisikListesiPage", () => {
  it("başlık, satırlar, rozetler ve açık işler; kişisel veri uyarısı", async () => {
    ciz();

    expect(
      await screen.findByRole("heading", { level: 1, name: "İlişik Listesi" }),
    ).toBeInTheDocument();
    const tablo = await screen.findByRole("table", { name: "İlişik listesi" });
    expect(within(tablo).getByText("Deneme Mezun")).toBeInTheDocument();
    expect(within(tablo).getByText("Son sınıf")).toBeInTheDocument();
    expect(within(tablo).getByText("Ayrıldı · 12.06.2027")).toBeInTheDocument();
    expect(within(tablo).getByText("1 teslim")).toBeInTheDocument();
    expect(within(tablo).getByText(/belge no 2026\/3/)).toBeInTheDocument();
    expect(screen.getByText(/Bu liste kişisel veri içerir/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Yıl Sonu/ })).toHaveAttribute("href", "/yil-sonu");
    expect(screen.getByRole("link", { name: /Yıl Başı/ })).toHaveAttribute("href", "/yil-basi");
    const sayfaMetni = document.body.textContent ?? "";
    for (const yasak of ["karne", "diploma", "borç", "ilişik kesme"]) {
      expect(sayfaMetni.toLowerCase()).not.toContain(yasak);
    }
  });

  it("kapsam, şube ve arama süzgeçleri uca gider", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByRole("table", { name: "İlişik listesi" });

    await user.selectOptions(screen.getByLabelText("Kapsam"), "priority");
    await waitFor(() =>
      expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith(
        expect.objectContaining({ group: "priority", offset: 0 }),
      ),
    );
    await screen.findByRole("option", { name: "12/A" });
    await user.selectOptions(screen.getByLabelText("Şube"), "12|A");
    await waitFor(() =>
      expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith(
        expect.objectContaining({ classLevel: 12, classSection: "A" }),
      ),
    );
    await user.type(screen.getByLabelText("Ara"), "Deneme");
    await user.click(screen.getAllByRole("button", { name: "Ara" })[0]);
    await waitFor(() =>
      expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "Deneme" }),
      ),
    );
  });

  it("sınıf kitaplıkları ayrı kartta; şubenin teslim listesi basılır", async () => {
    const user = userEvent.setup();
    ciz();

    const tablo = await screen.findByRole("table", {
      name: "Sınıf kitaplıklarındaki açık teslimler",
    });
    expect(within(tablo).getByText("12/A")).toBeInTheDocument();
    expect(within(tablo).getByText("2026/2")).toBeInTheDocument();
    await user.click(within(tablo).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(yilApiMock.sinifKitapligiListesiPdf).toHaveBeenCalledWith(5));
    expect(saveBlobMock).toHaveBeenCalled();
  });

  it("boş listede açıklama; toplu liste kapsamla basılır", async () => {
    yilApiMock.ilisikListesi.mockResolvedValue(sayfa([]));
    yilApiMock.sinifKitapliklari.mockResolvedValue([]);
    const user = userEvent.setup();
    ciz();

    expect(
      await screen.findByText("Bu seçimde kütüphaneyle açık işi olan kişi yok."),
    ).toBeInTheDocument();
    expect(await screen.findByText("Sınıf kitaplıklarında açık teslim yok.")).toBeInTheDocument();
    // Tek PDF düğmesi toplu listenindir (belge kartı arama yapılmadan düğme göstermez).
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() =>
      expect(yilApiMock.ilisikListesiPdf).toHaveBeenCalledWith({
        group: "",
        classLevel: null,
        classSection: "",
      }),
    );
  });

  it("belge kartı: yalnız açık işi olmayan kişi seçilir ve belgesi basılır", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByRole("table", { name: "İlişik listesi" });
    yilApiMock.ilisikListesi.mockResolvedValue(
      sayfa([
        temizSatir({ person_id: 3, full_name: "Deneme Temiz" }),
        ilisikSatiri({ person_id: 4, full_name: "Deneme Açıkişli" }),
      ]),
    );

    await user.type(screen.getByLabelText("Kişi"), "Deneme");
    const aramalar = screen.getAllByRole("button", { name: "Ara" });
    await user.click(aramalar[aramalar.length - 1]);

    const tablo = await screen.findByRole("table", { name: "Belge için arama sonuçları" });
    expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith({
      state: "all",
      search: "Deneme",
      limit: 50,
    });
    expect(within(tablo).getByRole("checkbox", { name: "Deneme Açıkişli seç" })).toBeDisabled();
    await user.click(within(tablo).getByRole("checkbox", { name: "Deneme Temiz seç" }));
    // Belge kartı sayfanın en altındadır: son "PDF'i indir" onundur.
    const indirmeler = screen.getAllByRole("button", { name: "PDF'i indir" });
    await user.click(indirmeler[indirmeler.length - 1]);
    await waitFor(() =>
      expect(yilApiMock.ilisikBelgesiPdf).toHaveBeenCalledWith({
        studentIds: [3],
        personnelIds: [],
      }),
    );
  });
});
