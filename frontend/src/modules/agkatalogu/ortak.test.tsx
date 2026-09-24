// Ağ Kataloğu ortak parçaları: QR çizimi, durum rozeti, komut kutusu, durum kancası.

import { render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { durumVerisi, ORNEK_QR } from "../../test/agKataloguVerileri";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const kapi = vi.hoisted(() => ({ durum: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, agKataloguApi: { ...actual.agKataloguApi, ...kapi } };
});

import { DurumRozeti, KomutKutusu, QrKodu, useAgDurumu } from "./ortak";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("QrKodu", () => {
  it("koyu modülleri sessiz bölgeli kare bir SVG olarak çizer", () => {
    render(<QrKodu satirlar={ORNEK_QR} boyutPx={100} />);

    const svg = screen.getByRole("img", { name: "Katalog adresinin QR kodu" });
    expect(svg).toHaveAttribute("viewBox", "0 0 29 29");
    // Beyaz zemin + her satırdaki koyu parçalar.
    expect(svg.querySelectorAll("rect").length).toBeGreaterThan(21);
  });
});

describe("DurumRozeti", () => {
  it.each([
    ["acik", "Açık"],
    ["kapali", "Kapalı"],
    ["engellendi", "Güvenlik duvarı izni yok"],
    ["bakim", "Geri yükleme nedeniyle kapalı"],
  ] as const)("%s → %s", (durum, metin) => {
    render(<DurumRozeti durum={durum} />);
    expect(screen.getByText(metin)).toBeInTheDocument();
  });
});

describe("KomutKutusu", () => {
  it("komutu panoya kopyalar ve bildirir", async () => {
    const user = userEvent.setup();
    render(
      <SnackbarProvider>
        <KomutKutusu komut="Test-NetConnection 10.20.30.40 -Port 8765" etiket="Sınama komutu" />
      </SnackbarProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Kopyala" }));

    await expect(navigator.clipboard.readText()).resolves.toBe(
      "Test-NetConnection 10.20.30.40 -Port 8765",
    );
    expect(await screen.findByText("Komut panoya kopyalandı.")).toBeInTheDocument();
  });
});

describe("useAgDurumu", () => {
  it("durumu okur", async () => {
    kapi.durum.mockResolvedValue(durumVerisi());

    const { result } = renderHook(() => useAgDurumu());

    await waitFor(() => expect(result.current.durum?.masaustu).toBe(true));
    expect(result.current.hata).toBeNull();
  });

  it("okunamazsa sunucunun iletisini verir", async () => {
    kapi.durum.mockRejectedValue(new ApiError(503, "x", "Sunucu hazır değil."));

    const { result } = renderHook(() => useAgDurumu());

    await waitFor(() => expect(result.current.hata).toBe("Sunucu hazır değil."));
  });
});
