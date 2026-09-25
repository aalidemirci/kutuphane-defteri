// Yıl Sonu (F7; tasarım §8.3): adım adım ekran — son ödünç tarihleri (politika ucu),
// kitap toplama (son sınıflar önce; yıl sonu pusulası), son sınıflar ve ayrılanlar
// (ilişik listesi), ilişik belgeleri (açık işi olmayan son sınıf öğrencileri). Belge
// başka bir işlemin ön koşulu diye sunulmaz. Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { akislar, ilisikSatiri, sayfa, sinifKitapligi, temizSatir } from "./testVerileri";

const yilApiMock = vi.hoisted(() => ({
  akislar: vi.fn(),
  ilisikListesi: vi.fn(),
  ilisikListesiPdf: vi.fn(),
  ilisikBelgesiPdf: vi.fn(),
  sinifKitapliklari: vi.fn(),
  sinifKitapligiListesiPdf: vi.fn(),
  yilSonuPusulasiPdf: vi.fn(),
}));
const kutuphaneApiMock = vi.hoisted(() => ({ updatePolicy: vi.fn() }));
const okulApiMock = vi.hoisted(() => ({ listClassSections: vi.fn() }));
const saveBlobMock = vi.hoisted(() => vi.fn());

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  yilApi: yilApiMock,
}));
vi.mock("../kutuphane/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../kutuphane/api")>()),
  kutuphaneApi: kutuphaneApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import YilSonuPage from "./YilSonuPage";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <YilSonuPage />
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
    {
      id: 2,
      school_year: 1,
      school_year_name: "2026-2027",
      class_level: 9,
      class_section: "B",
      class_label: "9/B",
    },
  ]);
  yilApiMock.akislar.mockResolvedValue(akislar());
  yilApiMock.ilisikListesi.mockResolvedValue(
    sayfa([
      ilisikSatiri({ person_id: 1, full_name: "Deneme Mezun" }),
      ilisikSatiri({
        person_type: "personnel",
        person_id: 9,
        full_name: "Deneme Teslimli",
        person_label: "Öğretmen",
        group: "other",
        status_text: "",
        open_loan_count: 0,
        loans: [],
        open_delivery_count: 2,
      }),
    ]),
  );
  yilApiMock.sinifKitapliklari.mockResolvedValue([sinifKitapligi()]);
  for (const pdf of [
    yilApiMock.ilisikListesiPdf,
    yilApiMock.ilisikBelgesiPdf,
    yilApiMock.sinifKitapligiListesiPdf,
    yilApiMock.yilSonuPusulasiPdf,
  ]) {
    pdf.mockResolvedValue(new Blob(["%PDF"]));
  }
  kutuphaneApiMock.updatePolicy.mockResolvedValue({});
});

async function adimaGec(user: ReturnType<typeof userEvent.setup>, sayi: number) {
  for (let i = 0; i < sayi; i += 1) {
    await user.click(screen.getByRole("button", { name: "Devam" }));
  }
}

describe("YilSonuPage", () => {
  it("başlık, adım rayı ve ilk adım: tarihler politika ucuna yazılır", async () => {
    const user = userEvent.setup();
    ciz();

    expect(await screen.findByRole("heading", { level: 1, name: "Yıl Sonu" })).toBeInTheDocument();
    const ray = screen.getByRole("list", { name: "Yıl sonu adımları" });
    expect(within(ray).getByText("Kitap Toplama")).toBeInTheDocument();
    expect(await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.")).toBeInTheDocument();
    expect(screen.getByText(/iade alınmaya devam eder/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Yıl sonu son ödünç tarihi"), "2027-06-04");
    await user.type(screen.getByLabelText("Son sınıflar için son ödünç tarihi"), "2027-05-28");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(kutuphaneApiMock.updatePolicy).toHaveBeenCalledWith({
        last_loan_date: "2027-06-04",
        last_loan_date_graduating: "2027-05-28",
      }),
    );
    expect(await screen.findByText("Son ödünç tarihleri kaydedildi.")).toBeInTheDocument();
    await waitFor(() => expect(yilApiMock.akislar).toHaveBeenCalledTimes(2));
  });

  it("eski yılın tarihi ve kademe eksikliği uyarılır", async () => {
    yilApiMock.akislar.mockResolvedValue(
      akislar({
        yilSonu: {
          last_loan_date: "2026-06-05",
          last_loan_date_stale: true,
          graduating_level: null,
        },
      }),
    );
    ciz();

    expect(
      await screen.findByText(
        /Kayıtlı yıl sonu son ödünç tarihi \(05\.06\.2026\) önceki ders yılına ait/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Okulun kademesi seçilmemiş/)).toBeInTheDocument();
  });

  it("kitap toplama: son sınıflar önce, yalnız ödüncü olan seçilir, pusula seçilenlere", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.");
    await adimaGec(user, 1);

    const tablo = await screen.findByRole("table", { name: "Toplanacak kitaplar" });
    // Kılavuz ve sözlük listeyi bu adla anar: başlık ekranda GÖRÜNÜR (yalnız tablo
    // adı değil — tablo adı ekran okuyucuya gizli `caption`'dır).
    const gorunurler = screen
      .getAllByText("Toplanacak kitaplar")
      .filter((el) => el.tagName !== "CAPTION");
    expect(gorunurler).toHaveLength(1);
    expect(gorunurler[0]).not.toHaveClass("sr-only");
    expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith(
      expect.objectContaining({ obligation: "collect", group: "" }),
    );
    expect(within(tablo).getByText("Deneme Mezun")).toBeInTheDocument();
    expect(within(tablo).getByRole("checkbox", { name: "Deneme Teslimli seç" })).toBeDisabled();
    await user.click(within(tablo).getByRole("checkbox", { name: "Deneme Mezun seç" }));
    expect(screen.getByText(/Pusula yalnız seçilen 1 kişiye basılır./)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Son getirme günü"), "2027-06-11");

    const onizlemeler = screen.getAllByRole("button", { name: "PDF'i indir" });
    await user.click(onizlemeler[0]);
    await waitFor(() =>
      expect(yilApiMock.yilSonuPusulasiPdf).toHaveBeenCalledWith({
        studentIds: [1],
        personnelIds: [],
        returnBy: "2027-06-11",
      }),
    );
    expect(saveBlobMock).toHaveBeenCalled();
  });

  it("kitap toplama: seçim yoksa pusula kapsamdakilere", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.");
    await adimaGec(user, 1);
    await screen.findByRole("table", { name: "Toplanacak kitaplar" });

    await user.selectOptions(screen.getByLabelText("Kapsam"), "graduating");
    await screen.findByRole("table", { name: "Toplanacak kitaplar" });
    await user.click(screen.getAllByRole("button", { name: "PDF'i indir" })[0]);

    await waitFor(() =>
      expect(yilApiMock.yilSonuPusulasiPdf).toHaveBeenCalledWith({
        group: "graduating",
        classLevel: null,
        classSection: "",
        returnBy: undefined,
      }),
    );
  });

  it("son sınıflar ve ayrılanlar: öncelikli liste ve son sınıf kitaplıkları", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.");
    await adimaGec(user, 2);

    await screen.findByRole("table", { name: "Son sınıflar ve ayrılanlar" });
    expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith(
      expect.objectContaining({ group: "priority" }),
    );
    await waitFor(() => expect(yilApiMock.sinifKitapliklari).toHaveBeenLastCalledWith(true));
    await user.click(screen.getAllByRole("button", { name: "PDF'i indir" })[0]);
    await waitFor(() =>
      expect(yilApiMock.ilisikListesiPdf).toHaveBeenCalledWith({ group: "priority" }),
    );
  });

  it("ilişik ve belgeler: açık işi olmayan son sınıf öğrencilerinin belgeleri", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.");
    await adimaGec(user, 3);

    expect(
      await screen.findByText(/açık işi olmayan son sınıf öğrencisi: 37 \/ 40/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "İlişik Listesi'ni aç" })).toHaveAttribute(
      "href",
      "/ilisik-listesi",
    );
    expect(screen.queryByRole("button", { name: "Devam" })).not.toBeInTheDocument();
    // Yalnız son sınıfın şubeleri seçilebilir.
    await screen.findByRole("option", { name: "12/A" });
    expect(screen.queryByRole("option", { name: "9/B" })).not.toBeInTheDocument();
    yilApiMock.ilisikListesi.mockResolvedValue(
      sayfa([temizSatir({ person_id: 31 }), temizSatir({ person_id: 32 })]),
    );
    await user.selectOptions(screen.getByLabelText("Son sınıf şubesi"), "12|A");
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    await waitFor(() =>
      expect(yilApiMock.ilisikBelgesiPdf).toHaveBeenCalledWith({ studentIds: [31, 32] }),
    );
    expect(yilApiMock.ilisikListesi).toHaveBeenLastCalledWith({
      state: "clear",
      group: "graduating",
      classLevel: 12,
      classSection: "A",
      limit: 150,
    });
    const sayfaMetni = (document.body.textContent ?? "").toLowerCase();
    for (const yasak of ["karne", "diploma", "borç"]) expect(sayfaMetni).not.toContain(yasak);
  });

  it("çok büyük seçimde belge basılmaz, şube şube basılması söylenir", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Yıl sonu son ödünç tarihi girilmedi.");
    await adimaGec(user, 3);
    await screen.findByText(/açık işi olmayan son sınıf öğrencisi/);
    yilApiMock.ilisikListesi.mockResolvedValue(sayfa([temizSatir()], 151));

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    expect(
      await screen.findByText(/en çok 150 belge basılır; şube şube basın/),
    ).toBeInTheDocument();
    expect(yilApiMock.ilisikBelgesiPdf).not.toHaveBeenCalled();
  });

  it("özet okunamazsa hata bandı", async () => {
    const { ApiError } = await import("../../lib/api");
    yilApiMock.akislar.mockRejectedValue(new ApiError(500, "hata", "Sunucuya ulaşılamadı."));
    ciz();
    expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeInTheDocument();
  });
});
