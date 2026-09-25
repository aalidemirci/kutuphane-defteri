// Teslim Kayıtları (F7, U11): açık teslimler varsayılan; beklenen dönüşü geçen teslim
// gecikme değildir (yalnız bilgi rozeti); belge no'ya tıklanınca o belgenin Teslim
// listesi (E15) basılır; açık teslimde kayıp bildirimi. Adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { dosyaVerisi, sayfa, teslimSatiri } from "../../test/teslimVerileri";

const teslim = vi.hoisted(() => ({
  listele: vi.fn(),
  teslimListesiPdf: vi.fn(),
  geriAlmaDokumuPdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslim } };
});
const kayip = vi.hoisted(() => ({ ac: vi.fn() }));
vi.mock("../kayip/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kayip/api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayip } };
});
const masa = vi.hoisted(() => ({ nushaDurumu: vi.fn(), uyeAra: vi.fn() }));
vi.mock("../dolasim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dolasim/api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masa } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import TeslimKayitlari, { BEKLENEN_DONUS_GECTI } from "./TeslimKayitlari";

function ciz() {
  render(
    <MemoryRouter>
      <SnackbarProvider>
        <TeslimKayitlari />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  teslim.listele.mockResolvedValue(
    sayfa([
      teslimSatiri({ id: 1, document_no: "2026/1" }),
      teslimSatiri({
        id: 2,
        copy: 12,
        barcode: "2026000124",
        barcode_display: "2026-000124",
        work_title: "Öğretmen Kitabı",
        recipient_kind: "TEACHER",
        recipient_kind_display: "Öğretmen",
        section: null,
        personnel: 21,
        recipient_label: "Deneme Öğretmen",
        document_no: "2026/2",
        expected_return_passed: true,
      }),
    ]),
  );
  teslim.teslimListesiPdf.mockResolvedValue(new Blob(["%PDF"]));
  teslim.geriAlmaDokumuPdf.mockResolvedValue(new Blob(["%PDF"]));
  masa.nushaDurumu.mockResolvedValue({ kind: "COPY", message: "Sınıf kitaplığında.", copy: null });
  kayip.ac.mockResolvedValue(dosyaVerisi());
});

describe("TeslimKayitlari", () => {
  it("açık teslimler listelenir; beklenen dönüşü geçen yalnız bilgi rozetidir", async () => {
    ciz();
    const tablo = await screen.findByRole("table", { name: "Teslimler" });
    expect(teslim.listele).toHaveBeenCalledWith(
      expect.objectContaining({ status: "OPEN", recipientKind: "", documentNo: "", offset: 0 }),
    );
    expect(within(tablo).getByText("Sınıf kitaplığı: 3/A")).toBeInTheDocument();
    expect(within(tablo).getByText("Öğretmen: Deneme Öğretmen")).toBeInTheDocument();
    expect(within(tablo).getAllByText(BEKLENEN_DONUS_GECTI)).toHaveLength(1);
    expect(tablo).not.toHaveTextContent(/gecikti|ceza/);
  });

  it("belge no'ya tıklanınca liste o belgeye süzülür ve teslim listesi indirilir", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(
      await screen.findByRole("button", { name: "Belge no 2026/1 satırlarını göster" }),
    );
    await waitFor(() =>
      expect(teslim.listele).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "", documentNo: "2026/1" }),
      ),
    );
    expect(await screen.findByText("Teslim listesi — belge no 2026/1")).toBeInTheDocument();
    await user.click(
      within(screen.getByRole("region", { name: "Teslim listesi" })).getByRole("button", {
        name: "PDF'i indir",
      }),
    );
    await waitFor(() => expect(saveBlobMock).toHaveBeenCalled());
    expect(teslim.teslimListesiPdf).toHaveBeenCalledWith("2026/1");
    expect(saveBlobMock.mock.calls[0][1]).toBe("Teslim-listesi_2026-1_21.09.2026.pdf");

    await user.click(screen.getByRole("button", { name: "Temizle" }));
    await waitFor(() =>
      expect(teslim.listele).toHaveBeenLastCalledWith(expect.objectContaining({ documentNo: "" })),
    );
  });

  it("belge kartından o belgenin geri alma dökümü belge no ile basılır (oturumdan bağımsız)", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(
      await screen.findByRole("button", { name: "Belge no 2026/2 satırlarını göster" }),
    );
    const dokum = await screen.findByRole("region", { name: "Geri alma dökümü" });
    expect(dokum).toHaveTextContent("görevli kipinde ya da masada");
    await user.click(within(dokum).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(saveBlobMock).toHaveBeenCalled());
    expect(teslim.geriAlmaDokumuPdf).toHaveBeenCalledWith({ documentNo: "2026/2" });
    expect(teslim.teslimListesiPdf).not.toHaveBeenCalled();
    expect(saveBlobMock.mock.calls[0][1]).toMatch(
      /^Geri-alma-dökümü_2026-2_\d{2}\.\d{2}\.\d{4}\.pdf$/,
    );
  });

  it("süzgeçler isteğe yazılır", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByRole("table", { name: "Teslimler" });
    await user.selectOptions(screen.getByLabelText("Durum"), "RETURNED");
    await user.selectOptions(screen.getByLabelText("Teslim alan"), "TEACHER");
    await user.type(screen.getByLabelText("Belge no"), "2026/9");
    await user.click(screen.getByRole("button", { name: "Ara" }));
    await waitFor(() =>
      expect(teslim.listele).toHaveBeenLastCalledWith(
        expect.objectContaining({
          status: "RETURNED",
          recipientKind: "TEACHER",
          documentNo: "2026/9",
        }),
      ),
    );
  });

  it("açık teslimde kayıp bildirimi dosya penceresini açar; liste tazelenir", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(await screen.findByRole("button", { name: "2026-000123 için kayıp bildir" }));
    const pencere = await screen.findByRole("dialog", { name: "Kayıp bildirilsin mi?" });
    const onceki = teslim.listele.mock.calls.length;
    await user.click(within(pencere).getByRole("button", { name: "Kayıp bildir" }));
    await waitFor(() =>
      expect(kayip.ac).toHaveBeenCalledWith(
        expect.objectContaining({ case_type: "LOST", copy_id: 11 }),
      ),
    );
    await waitFor(() => expect(teslim.listele.mock.calls.length).toBeGreaterThan(onceki));
    expect(
      await screen.findByText("Kayıp bildirildi; teslim kayba dönüştü ve kayıp dosyası açıldı."),
    ).toBeInTheDocument();
  });

  it("açık teslim yoksa boş durum", async () => {
    teslim.listele.mockResolvedValue(sayfa([]));
    ciz();
    expect(await screen.findByText("Açık teslim yok.")).toBeInTheDocument();
  });
});
