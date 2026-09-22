// "Katalog Excel Şablonu" kartı: indirme akışı (ucu çağırır, belge adı + tarihle
// kaydeder, snackbar), hata iletisi ve sözlüğe uygun metin.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const mocks = vi.hoisted(() => ({
  catalogTemplate: vi.fn(),
  saveBlob: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  kutuphaneApi: { catalogTemplate: mocks.catalogTemplate },
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: mocks.saveBlob,
}));

import { ApiError } from "../../lib/api";
import KatalogSablonuKarti from "./KatalogSablonuKarti";

function bas() {
  return render(
    <SnackbarProvider>
      <KatalogSablonuKarti />
    </SnackbarProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.useRealTimers());

it("başlık, kısa açıklama ve “Şablonu indir” düğmesi görünür", () => {
  bas();

  expect(screen.getByRole("heading", { name: "Katalog Excel Şablonu" })).toBeInTheDocument();
  expect(screen.getByText(/şimdiden başlayabilirsiniz/)).toBeInTheDocument();
  expect(screen.getByText(/kişisel veri yazılmaz/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Şablonu indir/ })).toBeEnabled();
});

it("şablonu indirir ve belge adı + yerel tarihle kaydeder", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 21, 10, 0, 0));
  const blob = new Blob(["xlsx"]);
  mocks.catalogTemplate.mockResolvedValue(blob);
  bas();

  await userEvent.click(screen.getByRole("button", { name: /Şablonu indir/ }));

  await waitFor(() =>
    expect(mocks.saveBlob).toHaveBeenCalledWith(blob, "Katalog-Excel-Şablonu_21.09.2026.xlsx"),
  );
  expect(mocks.catalogTemplate).toHaveBeenCalledTimes(1);
  expect(await screen.findByText("Katalog Excel şablonu indirildi.")).toBeInTheDocument();
});

it("indirme sürerken düğme kapalıdır (çift tıklama iki dosya indirmez)", async () => {
  let bitir: (b: Blob) => void = () => {};
  mocks.catalogTemplate.mockReturnValue(
    new Promise<Blob>((resolve) => {
      bitir = resolve;
    }),
  );
  bas();
  const dugme = screen.getByRole("button", { name: /Şablonu indir/ });

  await userEvent.click(dugme);
  expect(dugme).toBeDisabled();

  bitir(new Blob(["x"]));
  await waitFor(() => expect(dugme).toBeEnabled());
  expect(mocks.saveBlob).toHaveBeenCalledTimes(1);
});

it("sunucu hatasında backend iletisini gösterir, dosya kaydetmez", async () => {
  mocks.catalogTemplate.mockRejectedValue(
    new ApiError(423, "locked", "Kayıtlar yönetici parolasıyla kilitli."),
  );
  bas();

  await userEvent.click(screen.getByRole("button", { name: /Şablonu indir/ }));

  expect(await screen.findByText("Kayıtlar yönetici parolasıyla kilitli.")).toBeInTheDocument();
  expect(mocks.saveBlob).not.toHaveBeenCalled();
});

it("beklenmeyen hatada genel iletiyi gösterir", async () => {
  mocks.catalogTemplate.mockRejectedValue(new TypeError("ağ yok"));
  bas();

  await userEvent.click(screen.getByRole("button", { name: /Şablonu indir/ }));

  expect(await screen.findByText("Şablon indirilemedi.")).toBeInTheDocument();
});

it("başarılı indirmede `onIndirildi` çağrılır (yol haritası maddesi), hatada çağrılmaz", async () => {
  const onIndirildi = vi.fn();
  mocks.catalogTemplate.mockRejectedValueOnce(new TypeError("ağ yok"));
  render(
    <SnackbarProvider>
      <KatalogSablonuKarti onIndirildi={onIndirildi} />
    </SnackbarProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /Şablonu indir/ }));
  await screen.findByText("Şablon indirilemedi.");
  expect(onIndirildi).not.toHaveBeenCalled();

  mocks.catalogTemplate.mockResolvedValue(new Blob(["xlsx"]));
  await userEvent.click(screen.getByRole("button", { name: /Şablonu indir/ }));
  await waitFor(() => expect(onIndirildi).toHaveBeenCalledTimes(1));
});
