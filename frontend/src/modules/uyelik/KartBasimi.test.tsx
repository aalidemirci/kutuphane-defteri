// Kişiler → Kart Basımı (F6, E2, D10): kuyruk listesi, seçim, PDF'in işarete
// dokunmaması, onaylı "Basıldı olarak işaretle", "Kartı Basılmış" listesinde geri
// alma ve kart şablonuyla basım gövdesi. Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { KART_SABLONU, kartSatiri, sayfa } from "./testVerileri";

const uyelikApiMock = vi.hoisted(() => ({
  kartKuyrugu: vi.fn(),
  kartSablonu: vi.fn(),
  kartPdf: vi.fn(),
  kartBasildi: vi.fn(),
  kartBasimiGeriAl: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({ listClassSections: vi.fn() }));
const etiketApiMock = vi.hoisted(() => ({ kalibrasyonlar: vi.fn() }));
const saveBlobMock = vi.hoisted(() => vi.fn());

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  uyelikApi: uyelikApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));
vi.mock("../kutuphane/etiketApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../kutuphane/etiketApi")>()),
  etiketApi: etiketApiMock,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import KartBasimi from "./KartBasimi";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <KartBasimi />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  okulApiMock.listClassSections.mockResolvedValue([]);
  etiketApiMock.kalibrasyonlar.mockResolvedValue(
    sayfa([
      {
        id: 3,
        template: 7,
        template_name: KART_SABLONU.name,
        printer_name: "Müdürlük yazıcısı",
        offset_x: 1.2,
        offset_y: -0.5,
        updated_at: "2026-09-24T10:00:00+03:00",
      },
    ]),
  );
  uyelikApiMock.kartSablonu.mockResolvedValue(KART_SABLONU);
  uyelikApiMock.kartKuyrugu.mockImplementation(({ state }: { state: string }) =>
    Promise.resolve(
      state === "pending"
        ? sayfa([kartSatiri({ id: 1 }), kartSatiri({ id: 2, full_name: "Deneme İki" })])
        : sayfa([
            kartSatiri({
              id: 3,
              full_name: "Deneme Basılı",
              card_printed_at: "2026-09-22T09:00:00+03:00",
            }),
          ]),
    ),
  );
});

describe("KartBasimi", () => {
  it("kuyruğu listeler; seçim yokken PDF ve işaret düğmeleri kapalıdır", async () => {
    ciz();

    expect(await screen.findByText("Deneme İki")).toBeInTheDocument();
    expect(uyelikApiMock.kartKuyrugu).toHaveBeenCalledWith(
      expect.objectContaining({ state: "pending", limit: 50 }),
    );
    expect(screen.getByRole("button", { name: "Basıldı olarak işaretle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "PDF'i indir" })).toBeDisabled();
    expect(await screen.findByText(`Kart şablonu: ${KART_SABLONU.name}`)).toBeInTheDocument();
  });

  it("PDF kart şablonu, yazıcı ve başlangıç hücresiyle istenir; işarete dokunmaz", async () => {
    const user = userEvent.setup();
    uyelikApiMock.kartPdf.mockResolvedValue(new Blob(["%PDF"]));
    ciz();
    await screen.findByText("Deneme İki");
    await screen.findByRole("option", { name: /Müdürlük yazıcısı/ });

    await user.click(screen.getByLabelText("Bu sayfadakilerin tümünü seç"));
    await user.selectOptions(screen.getByLabelText("Yazıcı (kalibrasyon)"), "3");
    await user.click(screen.getByRole("button", { name: "3. hücre" }));
    await user.click(screen.getByLabelText("Kesim çizgisi bas"));
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    await waitFor(() =>
      expect(uyelikApiMock.kartPdf).toHaveBeenCalledWith({
        membership_ids: [1, 2],
        template: 7,
        calibration: 3,
        start_cell: 3,
        cut_guides: false,
      }),
    );
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Üye-Kartı_\d{2}\.\d{2}\.\d{4}\.pdf$/),
    );
    expect(uyelikApiMock.kartBasildi).not.toHaveBeenCalled();
  });

  it("Basıldı olarak işaretle onaydan geçer", async () => {
    const user = userEvent.setup();
    uyelikApiMock.kartBasildi.mockResolvedValue({ marked: 1 });
    ciz();
    await screen.findByText("Deneme İki");

    await user.click(screen.getByLabelText("Deneme İki seç"));
    await user.click(screen.getByRole("button", { name: "Basıldı olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "1 kart basıldı olarak işaretlensin mi?",
    });
    expect(onay).toHaveTextContent("PDF'i almak kartı basılmış saymaz.");
    await user.click(within(onay).getByRole("button", { name: "Basıldı olarak işaretle" }));

    await waitFor(() => expect(uyelikApiMock.kartBasildi).toHaveBeenCalledWith([2]));
    expect(await screen.findByText("1 kart basıldı olarak işaretlendi.")).toBeInTheDocument();
  });

  it("Kartı Basılmış listesinde basım işareti geri alınır", async () => {
    const user = userEvent.setup();
    uyelikApiMock.kartBasimiGeriAl.mockResolvedValue({ reverted: 1 });
    ciz();
    await screen.findByText("Deneme İki");

    await user.click(screen.getByRole("tab", { name: /Kartı Basılmış/ }));
    await screen.findByText("Deneme Basılı");
    expect(screen.getByText("22.09.2026")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Deneme Basılı seç"));
    await user.click(screen.getByRole("button", { name: "Basım işaretini geri al" }));
    const onay = await screen.findByRole("dialog", {
      name: "1 kartın basım işareti geri alınsın mı?",
    });
    await user.click(within(onay).getByRole("button", { name: "Basım işaretini geri al" }));

    await waitFor(() => expect(uyelikApiMock.kartBasimiGeriAl).toHaveBeenCalledWith([3]));
  });

  it("kart şablonunun yazıcı kalibrasyonu aynı panelden açılır", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(await screen.findByRole("button", { name: "Yazıcı kalibrasyonunu göster" }));
    expect(
      await screen.findByText(`Yazıcı Kalibrasyonu: ${KART_SABLONU.name}`),
    ).toBeInTheDocument();
  });
});
