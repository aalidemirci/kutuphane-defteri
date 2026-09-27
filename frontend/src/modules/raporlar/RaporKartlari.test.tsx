// Genel Bakış'ın F10 kartları: Md. 7/1 bilgi kartı yalnız eşik aşılınca ve yalnız bilgi; çok
// okunanlar özeti sayısız ve liste boşsa yok; okunamazsa hiçbir şey çizilmez. Eserler uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { donemPenceresi, kitapEsigi, panoOzeti, pencere } from "./testVerileri";

const rapi = vi.hoisted(() => ({ pano: vi.fn() }));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  raporlarApi: rapi,
}));

import { MD7_1_METNI } from "./api";
import RaporKartlari, {
  COK_OKUNANLAR_BASLIGI,
  KITAP_ESIGI_BASLIGI,
  MD7_SAYIM_KURALI,
  kayipDahilMetni,
} from "./RaporKartlari";

function ciz() {
  return render(
    <MemoryRouter>
      <RaporKartlari />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Genel Bakış — Md. 7/1 bilgi kartı", () => {
  it("eşik aşılınca sayıyı ve maddenin cümlesini yazar; yalnız bilgidir", async () => {
    rapi.pano.mockResolvedValue(
      panoOzeti({ book_threshold: kitapEsigi({ in_stock_books: 10_482, exceeded: true }) }),
    );
    ciz();
    const kart = await screen.findByRole("region", { name: KITAP_ESIGI_BASLIGI });
    expect(within(kart).getByText("Elde bulunan kitap: 10.482.")).toBeInTheDocument();
    expect(within(kart).getByText(`“${MD7_1_METNI}”`)).toBeInTheDocument();
    expect(kart).toHaveTextContent("Kart yalnız bilgi verir.");
    // Sözlükle aynı kural: kayıttan düşülmemiş VE devredilmemiş (F10 düzeltme turu).
    expect(kart).toHaveTextContent(MD7_SAYIM_KURALI);
    expect(MD7_SAYIM_KURALI).toContain("kayıttan düşülmemiş, devredilmemiş");
    expect(kart).not.toHaveTextContent("Kayıp bildirilmiş");
    // Kart bir işe yönlendirmez (bağlantı ya da düğme yok).
    expect(within(kart).queryByRole("link")).not.toBeInTheDocument();
    expect(within(kart).queryByRole("button")).not.toBeInTheDocument();
  });

  it("kayıp bildirilmiş ama kayıttan düşülmemiş kitabın sayıya dahil olduğunu yazar", async () => {
    rapi.pano.mockResolvedValue(
      panoOzeti({
        book_threshold: kitapEsigi({ in_stock_books: 10_020, lost_books: 25, exceeded: true }),
      }),
    );
    ciz();
    const kart = await screen.findByRole("region", { name: KITAP_ESIGI_BASLIGI });
    expect(kart).toHaveTextContent(kayipDahilMetni(25));
    expect(kayipDahilMetni(1_250)).toContain("1.250 kitap");
  });

  it("eşik aşılmadıysa (10.000 dahil) kart yoktur", async () => {
    rapi.pano.mockResolvedValue(
      panoOzeti({ book_threshold: kitapEsigi({ in_stock_books: 10_000, exceeded: false }) }),
    );
    ciz();
    await screen.findByRole("region", { name: COK_OKUNANLAR_BASLIGI });
    expect(screen.queryByRole("region", { name: KITAP_ESIGI_BASLIGI })).not.toBeInTheDocument();
  });
});

describe("Genel Bakış — çok okunanlar özeti", () => {
  it("dönem ve ay listeleri sırayla, sayısız; Raporlar'a bağlanır", async () => {
    rapi.pano.mockResolvedValue(panoOzeti());
    ciz();
    const kart = await screen.findByRole("region", { name: COK_OKUNANLAR_BASLIGI });
    const donem = within(kart).getByRole("list", {
      name: "Dönem: 2026-2027 ders yılı 1. dönem",
    });
    expect(
      within(donem)
        .getAllByRole("listitem")
        .map((l) => l.textContent),
    ).toEqual([
      "1. Deneme Romanı — Örnek Yazar",
      "2. Uydurma Öyküler",
      "3. Örnek Şiirler — Deneme Şair",
    ]);
    expect(within(kart).getByRole("list", { name: "Ay: Eylül 2026" })).toBeInTheDocument();
    expect(kart).toHaveTextContent("Sıra farklı üye sayısına göredir; sayı gösterilmez.");
    expect(within(kart).getByRole("link", { name: "Çok Okunanlar'ı aç" })).toHaveAttribute(
      "href",
      "/raporlar?tab=cok-okunanlar",
    );
  });

  it("yalnız bir pencere doluysa o gösterilir", async () => {
    rapi.pano.mockResolvedValue(
      panoOzeti({ popular: { term: donemPenceresi({ works: [] }), month: pencere() } }),
    );
    ciz();
    const kart = await screen.findByRole("region", { name: COK_OKUNANLAR_BASLIGI });
    expect(within(kart).queryByRole("list", { name: /^Dönem/ })).not.toBeInTheDocument();
    expect(within(kart).getByRole("list", { name: /^Ay/ })).toBeInTheDocument();
  });

  it("liste boşsa kart yoktur", async () => {
    rapi.pano.mockResolvedValue(panoOzeti({ popular: { term: null, month: null } }));
    const { container } = ciz();
    await waitFor(() => expect(rapi.pano).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: COK_OKUNANLAR_BASLIGI })).toBeNull(),
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("özet okunamazsa hiçbir şey çizilmez", async () => {
    rapi.pano.mockRejectedValue(new Error("ağ yok"));
    const { container } = ciz();
    await waitFor(() => expect(rapi.pano).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
