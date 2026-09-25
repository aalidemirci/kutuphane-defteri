// Genel Bakış'ın "Sayım" kartı ve kilitli işlemlerin bantları (F9; tasarım §9-10).
// Kart canlı sayım varken görünür; süren iki seçenek AYRI satırlarda yazılır ve iade her
// zaman açıktır. Durdurma bandı yalnız TMY 32/3 durdurması sürerken çıkar.

import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TMY_DURDURMA_KAPSAMI } from "./api";
import { durumOzeti } from "./testVerileri";

const api = vi.hoisted(() => ({ durum: vi.fn() }));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...api } };
});

import SayimKarti, {
  DurdurmaBandi,
  HIZMET_ARASI_SURUYOR,
  HizmetArasiSeridi,
  IADE_ACIK,
} from "./SayimKarti";

function ciz(icerik: ReactNode) {
  return render(<MemoryRouter>{icerik}</MemoryRouter>);
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Genel Bakış — Sayım kartı", () => {
  it("süren sayım: ilerleme, iki seçenek ayrı satırda, iade açık ve bağlantı", async () => {
    api.durum.mockResolvedValue(durumOzeti());
    ciz(<SayimKarti />);

    expect(await screen.findByRole("heading", { name: "Sayım" })).toBeInTheDocument();
    expect(screen.getByText("Sayım sürüyor: 75 / 114 nüsha bulundu.")).toBeInTheDocument();
    const secenekler = screen.getByRole("list", { name: "Süren seçenekler" });
    const satirlar = secenekler.querySelectorAll("li");
    expect(satirlar).toHaveLength(2);
    expect(satirlar[0]).toHaveTextContent("TMY 32/3 durdurması: edinim ve yeni nüsha kaydı");
    expect(satirlar[0]).toHaveTextContent(`${TMY_DURDURMA_KAPSAMI} yapılamaz.`);
    // Madde 27: hizmet arası yeni teslimi de durdurur.
    expect(satirlar[1]).toHaveTextContent(
      "Sayım için hizmet arası: yeni ödünç ve teslim yapılamıyor.",
    );
    expect(screen.getByText(IADE_ACIK)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sayım'ı aç" })).toHaveAttribute(
      "href",
      "/katalog/sayim?sayim=7",
    );
  });

  it("ikinci sayım, taslak ve onay bekleyen sayım metinleri; seçenek yoksa liste yok", async () => {
    const canli = durumOzeti().live;
    if (canli === null) throw new Error("test verisinde canlı sayım yok");
    api.durum.mockResolvedValueOnce(
      durumOzeti({
        live: { ...canli, round: 2 },
        tmy_stop_active: false,
        service_pause_active: false,
      }),
    );
    const { unmount } = ciz(<SayimKarti />);
    expect(
      await screen.findByText("İkinci sayım sürüyor: 75 / 114 nüsha bulundu."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Süren seçenekler" })).toBeNull();
    unmount();

    api.durum.mockResolvedValueOnce(
      durumOzeti({
        live: { ...canli, status: "DRAFT" },
        tmy_stop_active: false,
        service_pause_active: false,
      }),
    );
    const ikinci = ciz(<SayimKarti />);
    expect(
      await screen.findByText("Sayım taslağı hazırlanıyor; henüz başlatılmadı."),
    ).toBeInTheDocument();
    ikinci.unmount();

    api.durum.mockResolvedValueOnce(durumOzeti({ live: { ...canli, status: "COMPLETED" } }));
    ciz(<SayimKarti />);
    expect(
      await screen.findByText("Sayım tamamlandı; harcama yetkilisinin onayı bekleniyor."),
    ).toBeInTheDocument();
  });

  it("canlı sayım yoksa ya da durum okunamazsa kart çizilmez", async () => {
    api.durum.mockResolvedValueOnce(
      durumOzeti({ live: null, tmy_stop_active: false, service_pause_active: false }),
    );
    const { container, unmount } = ciz(<SayimKarti />);
    await waitFor(() => expect(api.durum).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    unmount();

    api.durum.mockRejectedValueOnce(new Error("çevrimdışı"));
    const ikinci = ciz(<SayimKarti />);
    await waitFor(() => expect(api.durum).toHaveBeenCalledTimes(2));
    expect(ikinci.container).toBeEmptyDOMElement();
  });
});

describe("Durdurma bandı ve hizmet arası şeridi", () => {
  it("TMY 32/3 durdurması sürerken işlemin adıyla bant çıkar", async () => {
    api.durum.mockResolvedValue(durumOzeti());
    ciz(<DurdurmaBandi islem="edinim ve yeni nüsha kaydı" />);
    const bant = await screen.findByRole("status", { name: "TMY 32/3 durdurması sürüyor" });
    expect(bant).toHaveTextContent(
      "Sayım onaylanana ya da iptal edilene dek edinim ve yeni nüsha kaydı yapılamaz (Taşınır Mal Yönetmeliği md. 32/3). Durdurma ödüncü ve iadeyi kapsamaz.",
    );
    // Hizmet arası da sürerken bant "ödünç açıktır" demez (F9 düzeltme turu).
    expect(bant).not.toHaveTextContent("Ödünç ve iade açıktır");
    expect(screen.getByRole("link", { name: "Sayım'ı aç" })).toBeInTheDocument();
  });

  it("durdurma yoksa bant çizilmez", async () => {
    api.durum.mockResolvedValue(durumOzeti({ tmy_stop_active: false }));
    const { container } = ciz(<DurdurmaBandi islem="devir" />);
    await waitFor(() => expect(api.durum).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("hizmet arası şeridi sunucunun iletisini ve iadenin alındığını yazar", () => {
    ciz(<HizmetArasiSeridi />);
    const serit = screen.getByRole("status", { name: "Sayım için hizmet arası" });
    expect(serit).toHaveTextContent(HIZMET_ARASI_SURUYOR);
    expect(serit).toHaveTextContent("iadesi alınır");
  });
});
