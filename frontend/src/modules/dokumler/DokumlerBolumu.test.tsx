// Raporlar → Dökümler (F10 — D kolu): dışa aktarım ve üye özeti (kişisiz), alfabetik katalog
// dökümü, Taşınır Kütüphane Defteri dökümü, yönetim hesabı cetveli hazırlığı (yalnız yıl sonu
// işaretli ve onaylanmış sayımdan — gerekçe sunucudan) ve kişi dökümü (okul no GÖVDEDE).
// Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DokumOzeti, UyeOzeti } from "./api";

const kapi = vi.hoisted(() => ({
  ozet: vi.fn(),
  uyeOzeti: vi.fn(),
  disaAktarim: vi.fn(),
  katalogDokumu: vi.fn(),
  defterDokumu: vi.fn(),
  yonetimHesabi: vi.fn(),
  kisiAra: vi.fn(),
  kisiDokumu: vi.fn(),
}));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, dokumlerApi: kapi };
});
vi.mock("../../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import { BOLUMSUZ, BOLUMSUZ_ADI } from "./api";
import DokumlerBolumu, {
  BOLUM_SECICI_YARDIMI,
  DISA_AKTARIM_GERI_YUKLEME,
  YIL_SONU_SAYIMI_YOK,
} from "./DokumlerBolumu";
import { ADAY_YOK } from "./KisiDokumuKarti";

/** Dışa Aktarım kartındaki geri yükleme bağlantısı yönlendirici ister. */
function ciz() {
  return render(
    <MemoryRouter>
      <DokumlerBolumu />
    </MemoryRouter>,
  );
}

function ozet(ek: Partial<DokumOzeti> = {}): DokumOzeti {
  return {
    export: { works: 120, copies: 340, exited: 12 },
    catalog_listing: {
      works: 118,
      copies: 340,
      axes: [
        { value: "title", label: "Kaynak adına göre" },
        { value: "author", label: "Yazar adına göre" },
        { value: "subject", label: "Konuya göre" },
      ],
      sections: [{ id: 3, name: "Edebiyat" }],
      unsectioned_works: 4,
    },
    library_register: { years: [2026, 2025] },
    management_account: { stocktakes: [] },
    ...ek,
  };
}

const UYELER: UyeOzeti = {
  total: 5,
  by_type: [
    { member_type: "STUDENT", label: "öğrenci", count: 4 },
    { member_type: "TEACHER", label: "öğretmen", count: 1 },
    { member_type: "STAFF", label: "diğer personel", count: 0 },
  ],
  by_class: [{ class_level: 9, class_section: "A", class_label: "9/A", count: 4 }],
  students_without_class: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  kapi.ozet.mockResolvedValue(ozet());
  kapi.uyeOzeti.mockResolvedValue(UYELER);
  kapi.disaAktarim.mockResolvedValue(new Blob(["x"]));
  kapi.katalogDokumu.mockResolvedValue(new Blob(["x"]));
  kapi.defterDokumu.mockResolvedValue(new Blob(["x"]));
});

describe("Dökümler", () => {
  it("dışa aktarım dosyası indirilir; üye özeti kişisiz sayılardır", async () => {
    const user = userEvent.setup();
    ciz();
    expect(
      await screen.findByText(/120 eser · 340 nüsha kayıtta · 12 nüsha kayıttan düşülmüş/),
    ).toBeInTheDocument();
    const ozetBolumu = screen.getByRole("region", { name: "Üye Özeti" });
    expect(within(ozetBolumu).getByText("9/A")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dışa aktarım dosyasını indir" }));
    await waitFor(() => expect(indirme.saveBlob).toHaveBeenCalled());
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(/^Katalog-dışa-aktarımı_.*\.xlsx$/);
    // Geri yükleme İçe Aktarma'dadır: bağlantı "Dışa aktarım dosyası" seçili açar.
    expect(screen.getByRole("link", { name: DISA_AKTARIM_GERI_YUKLEME })).toHaveAttribute(
      "href",
      "/katalog/ice-aktarma?dosya=disa-aktarim",
    );
  });

  it("alfabetik katalog dökümü seçilen eksen ve bölümle istenir; Excel üç eksendir", async () => {
    const user = userEvent.setup();
    ciz();
    await user.selectOptions(await screen.findByLabelText("Eksen"), "subject");
    await user.selectOptions(screen.getByLabelText("Bölüm"), "3");
    const kart = screen
      .getByRole("heading", { name: "Alfabetik Katalog Dökümü" })
      .closest("div")!.parentElement!;
    await user.click(within(kart).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(kapi.katalogDokumu).toHaveBeenCalledWith("pdf", "subject", 3));
    await user.click(within(kart).getByRole("button", { name: "Excel'i indir" }));
    await waitFor(() => expect(kapi.katalogDokumu).toHaveBeenCalledWith("xlsx", "subject", 3));
  });

  it("bölümü yazılmamış eserler kendi seçeneğiyle basılır (section=0)", async () => {
    // F10 düzeltme turu: "bölüm bölüm basabilirsiniz" denirken bölümsüz eserler hiçbir bölüm
    // çıktısına girmiyordu.
    const user = userEvent.setup();
    ciz();
    const secici = await screen.findByLabelText("Bölüm");
    await user.selectOptions(secici, String(BOLUMSUZ));
    expect(screen.getByRole("option", { name: BOLUMSUZ_ADI })).toBeInTheDocument();
    const kart = screen
      .getByRole("heading", { name: "Alfabetik Katalog Dökümü" })
      .closest("div")!.parentElement!;
    await user.click(within(kart).getByRole("button", { name: "Excel'i indir" }));
    await waitFor(() => expect(kapi.katalogDokumu).toHaveBeenCalledWith("xlsx", "title", 0));
    expect(kart).toHaveTextContent(BOLUM_SECICI_YARDIMI);
  });

  it("bölümsüz eser yoksa “Bölümü yazılmamış” seçeneği görünmez", async () => {
    kapi.ozet.mockResolvedValue(
      ozet({
        catalog_listing: { ...ozet().catalog_listing, unsectioned_works: 0 },
      }),
    );
    ciz();
    await screen.findByLabelText("Bölüm");
    expect(screen.queryByRole("option", { name: BOLUMSUZ_ADI })).not.toBeInTheDocument();
  });

  it("defter dökümü yıl kapsamıyla istenir", async () => {
    const user = userEvent.setup();
    ciz();
    await user.selectOptions(await screen.findByLabelText("Kapsam"), "2026");
    const kart = screen
      .getByRole("heading", { name: "Taşınır Kütüphane Defteri Dökümü" })
      .closest("div")!.parentElement!;
    await user.click(within(kart).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(kapi.defterDokumu).toHaveBeenCalledWith("pdf", 2026));
  });

  it("yıl sonu sayımı yoksa nasıl işaretleneceğini söyler", async () => {
    ciz();
    expect(await screen.findByText(YIL_SONU_SAYIMI_YOK)).toBeInTheDocument();
  });

  it("onaylanmamış yıl sonu sayımında sunucunun gerekçesi yazar, düğme yoktur", async () => {
    kapi.ozet.mockResolvedValue(
      ozet({
        management_account: {
          stocktakes: [
            {
              id: 9,
              name: "Sayım · 2026 · 21.12.2026",
              fiscal_year: 2026,
              status: "COMPLETED",
              status_display: "Tamamlandı",
              approved_on: null,
              available: false,
              reason: "Yönetim hesabı cetveli hazırlığı sayım onaylandıktan sonra basılır.",
            },
            {
              id: 8,
              name: "Sayım · 2025 · 20.12.2025",
              fiscal_year: 2025,
              status: "APPROVED",
              status_display: "Onaylandı",
              approved_on: "2025-12-29",
              available: true,
              reason: "",
            },
          ],
        },
      }),
    );
    kapi.yonetimHesabi.mockResolvedValue(new Blob(["x"]));
    const user = userEvent.setup();
    ciz();
    expect(
      await screen.findByText(/Tamamlandı — Yönetim hesabı cetveli hazırlığı sayım onaylandıktan/),
    ).toBeInTheDocument();
    const satir = screen.getByText("Sayım · 2025 · 20.12.2025").closest("li")!;
    await user.click(within(satir).getByRole("button", { name: "Excel'i indir" }));
    await waitFor(() => expect(kapi.yonetimHesabi).toHaveBeenCalledWith(8, "xlsx"));
    const bekleyen = screen.getByText("Sayım · 2026 · 21.12.2026").closest("li")!;
    expect(within(bekleyen).queryByRole("button")).not.toBeInTheDocument();
  });

  it("kişi dökümü: okul no gövdede gider, adaylar ayrı satırda", async () => {
    kapi.kisiAra.mockResolvedValue({
      results: [
        {
          kind: "student",
          id: 4,
          full_name: "Deneme Öğrenci",
          detail: "9/A",
          status_display: "Aktif",
        },
        {
          kind: "student",
          id: 2,
          full_name: "Deneme Eski",
          detail: "12/B",
          status_display: "Ayrıldı",
        },
      ],
    });
    kapi.kisiDokumu.mockResolvedValue(new Blob(["x"]));
    const user = userEvent.setup();
    ciz();
    await user.type(await screen.findByLabelText("Okul no"), "700123");
    await user.click(screen.getByRole("button", { name: "Ara" }));
    await waitFor(() =>
      expect(kapi.kisiAra).toHaveBeenCalledWith({ school_no: "700123", name: "" }),
    );
    const liste = await screen.findByRole("list", { name: "Bulunan kişiler" });
    expect(within(liste).getAllByRole("listitem")).toHaveLength(2);
    const satir = within(liste).getByText("Deneme Eski").closest("li")!;
    await user.click(within(satir).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(kapi.kisiDokumu).toHaveBeenCalledWith("student", 2));
    // İndirme adında kişi adı yok.
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(/^Kişi-dökümü_/);
    expect(indirme.saveBlob.mock.calls[0][1]).not.toContain("Deneme");
  });

  it("eşleşme yoksa söyler", async () => {
    kapi.kisiAra.mockResolvedValue({ results: [] });
    const user = userEvent.setup();
    ciz();
    await user.type(await screen.findByLabelText("Ad soyad"), "Yok");
    await user.click(screen.getByRole("button", { name: "Ara" }));
    expect(await screen.findByText(ADAY_YOK)).toBeInTheDocument();
  });
});
