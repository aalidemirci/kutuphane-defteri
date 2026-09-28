// Genel Bakış'ın saklama kartları (F11 — tasarım §6.4): yalnız sayı, ad yok; altı ayı aşan
// beklemede kapatılamayan uyarı; bedel adımında bekleyen dosyaların yıllık hatırlatması.

import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SaklamaPanoOzeti } from "./api";

const sapi = vi.hoisted(() => ({ pano: vi.fn() }));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  saklamaApi: sapi,
}));

import { SAKLAMA_ADRESI } from "./api";
import SaklamaKartlari, {
  AZAMI_BEKLEME_AY,
  BEDEL_KARTI_BASLIGI,
  SAKLAMA_KARTI_BASLIGI,
} from "./SaklamaKartlari";

function ozet(alanlar: Partial<SaklamaPanoOzeti> = {}): SaklamaPanoOzeti {
  return {
    candidates: 0,
    pending_since: null,
    approval_deadline: null,
    overdue: false,
    price_reminders: 0,
    ...alanlar,
  };
}

function ciz() {
  return render(
    <MemoryRouter>
      <SaklamaKartlari />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Genel Bakış — saklama kartları", () => {
  it("aday varsa sayıyı, bekleme başlangıcını ve en geç günü yazar; ekrana bağlanır", async () => {
    sapi.pano.mockResolvedValue(
      ozet({ candidates: 12, pending_since: "2028-09-24", approval_deadline: "2029-03-24" }),
    );
    ciz();
    const kart = await screen.findByRole("region", { name: SAKLAMA_KARTI_BASLIGI });
    expect(kart).toHaveTextContent("12 kaydın saklama süresi doldu");
    expect(kart).toHaveTextContent("Bekleme başlangıcı 24.09.2028");
    expect(kart).toHaveTextContent("24.03.2029");
    expect(within(kart).getByRole("link", { name: "Saklama ekranını aç" })).toHaveAttribute(
      "href",
      SAKLAMA_ADRESI,
    );
    expect(within(kart).queryByRole("alert")).not.toBeInTheDocument();
    expect(sapi.pano).toHaveBeenCalledTimes(1);
  });

  it("altı ayı aşan beklemede kapatılamayan uyarı çıkar", async () => {
    sapi.pano.mockResolvedValue(
      ozet({
        candidates: 3,
        pending_since: "2028-09-24",
        approval_deadline: "2029-03-24",
        overdue: true,
      }),
    );
    ciz();
    const kart = await screen.findByRole("region", { name: SAKLAMA_KARTI_BASLIGI });
    const uyari = within(kart).getByRole("alert");
    expect(uyari).toHaveTextContent(`Onay bekleme süresi (${AZAMI_BEKLEME_AY} ay) doldu`);
    // Kapatma düğmesi yoktur: uyarı yalnız işlem onaylanınca kalkar.
    expect(within(kart).queryByRole("button")).not.toBeInTheDocument();
  });

  it("aday yoksa saklama kartı yoktur; bedel listesi doluysa yalnız o kart çıkar", async () => {
    sapi.pano.mockResolvedValue(ozet({ price_reminders: 2 }));
    ciz();
    const kart = await screen.findByRole("region", { name: BEDEL_KARTI_BASLIGI });
    expect(kart).toHaveTextContent("2 kayıp/hasar dosyası bir yıldan uzun süredir bedel");
    expect(kart).toHaveTextContent("silinmez");
    expect(screen.queryByRole("region", { name: SAKLAMA_KARTI_BASLIGI })).not.toBeInTheDocument();
  });

  it("okunamazsa hiçbir şey çizilmez", async () => {
    sapi.pano.mockRejectedValue(new Error("ağ"));
    const { container } = ciz();
    await vi.waitFor(() => expect(sapi.pano).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
