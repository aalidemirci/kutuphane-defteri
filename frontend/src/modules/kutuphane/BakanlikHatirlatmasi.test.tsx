// "Bakanlık sistemi kullanımda" (A21 — F10): ayar varsayılan KAPALIDIR; açıkken ayrılış ve
// ilişik ekranları kaydın Bakanlık otomasyon sisteminde de güncellenmesini hatırlatır. Konum
// dili: program o sistemin yerine geçmez.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { politika } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  getPolicy: vi.fn(),
  updatePolicy: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import BakanlikHatirlatmasi, {
  AYRILIS_HATIRLATMASI,
  BAKANLIK_SISTEMI_AYARI,
  ILISIK_HATIRLATMASI,
  KONUM_CUMLESI,
} from "./BakanlikHatirlatmasi";
import KutuphanePolitikasiPaneli from "./KutuphanePolitikasiPaneli";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Bakanlık sistemi hatırlatması", () => {
  it("ayar kapalıyken hiçbir şey çizmez", async () => {
    kapi.getPolicy.mockResolvedValue(politika());
    render(<BakanlikHatirlatmasi metin={AYRILIS_HATIRLATMASI} />);
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("ayar açıkken hatırlatır ve konum dilini söyler", async () => {
    kapi.getPolicy.mockResolvedValue(politika({ ministry_system_in_use: true }));
    render(<BakanlikHatirlatmasi metin={ILISIK_HATIRLATMASI} />);
    const not = await screen.findByRole("note", { name: BAKANLIK_SISTEMI_AYARI });
    expect(not).toHaveTextContent("Bakanlık otomasyon sistemindeki kaydı da güncelleyin");
    expect(not).toHaveTextContent("o sistemin yerine geçmez");
    expect(AYRILIS_HATIRLATMASI.endsWith(KONUM_CUMLESI)).toBe(true);
  });

  it("ayar okunamazsa sessizce gizlenir", async () => {
    kapi.getPolicy.mockRejectedValue(new Error("kip"));
    render(<BakanlikHatirlatmasi metin={AYRILIS_HATIRLATMASI} />);
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("Kütüphane Politikası'nda ayar varsayılan kapalıdır ve kaydedilir", async () => {
    const user = userEvent.setup();
    kapi.getPolicy.mockResolvedValue(politika());
    kapi.updatePolicy.mockResolvedValue(politika({ ministry_system_in_use: true }));
    render(
      <SnackbarProvider>
        <KutuphanePolitikasiPaneli />
      </SnackbarProvider>,
    );
    const kutu = await screen.findByLabelText(BAKANLIK_SISTEMI_AYARI);
    expect(kutu).not.toBeChecked();
    await user.click(kutu);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kapi.updatePolicy).toHaveBeenCalled());
    expect(kapi.updatePolicy.mock.calls[0][0]).toMatchObject({ ministry_system_in_use: true });
  });
});
