// İçe Aktarma → Excel Aktarımı → "Dışa aktarım dosyası" (F10 — tasarım §8.4): dosya türü
// seçilince gövde `source: EXPORT` taşır, edinim partisi alanları gösterilmez ve gönderilmez
// (edinimler dosyadan gelir), sonuç kartı nüshaların kendi barkoduyla kayda girdiğini söyler.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  aktarimKosusu,
  aktarimRaporu,
  aktarimSayilari,
  bolum,
  sayfa,
} from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  listSections: vi.fn(),
  listCommissionDecisions: vi.fn(),
  aktarimOnizle: vi.fn(),
  aktarimiUygula: vi.fn(),
  aktarimGecmisi: vi.fn(),
  aktarimiIptalEt: vi.fn(),
  catalogTemplate: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import { DISA_AKTARIM_ACIKLAMASI, aktarilmayanSatirEngeli } from "./AktarimPaneli";
import IceAktarmaPage, { DISA_AKTARIM_ICE_AKTARMA_ADRESI } from "./IceAktarmaPage";

function ekranaBas() {
  return render(
    <MemoryRouter initialEntries={["/katalog/ice-aktarma"]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog/ice-aktarma" element={<IceAktarmaPage />} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
  kapi.listCommissionDecisions.mockResolvedValue(sayfa([]));
  kapi.aktarimGecmisi.mockResolvedValue(sayfa([]));
  kapi.aktarimiIptalEt.mockResolvedValue(aktarimKosusu({ status: "DISCARDED" }));
  kapi.aktarimOnizle.mockResolvedValue(aktarimRaporu({ source: "EXPORT" }));
  kapi.aktarimiUygula.mockResolvedValue(
    aktarimRaporu({
      source: "EXPORT",
      dry_run: false,
      run_id: 12,
      stats: aktarimSayilari({ copies_created: 7 }),
      label_batch: null,
    }),
  );
});

describe("İçe Aktarma — dışa aktarım dosyası", () => {
  it("kaynak EXPORT gider; edinim partisi sorulmaz; sonuç barkodların korunduğunu söyler", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await user.selectOptions(await screen.findByLabelText("İçe aktarılacak dosya"), "disa_aktarim");
    expect(screen.getByText(DISA_AKTARIM_ACIKLAMASI)).toBeInTheDocument();
    const dosya = new File(["x"], "katalog.xlsx", { type: "application/vnd.ms-excel" });
    await user.upload(screen.getByLabelText(/^Dosya/), dosya);
    await user.click(screen.getByRole("button", { name: "Önizle" }));
    await waitFor(() => expect(kapi.aktarimOnizle).toHaveBeenCalled());
    expect(kapi.aktarimOnizle.mock.calls[0][0]).toMatchObject({ source: "EXPORT", file: dosya });

    expect(await screen.findByText("Dışa Aktarım Dosyasını Uygula")).toBeInTheDocument();
    expect(screen.queryByText("Açılacak Edinim Partisi")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Edinim yolu")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(kapi.aktarimiUygula).toHaveBeenCalled());
    const govde = kapi.aktarimiUygula.mock.calls[0][0] as Record<string, unknown>;
    expect(govde.source).toBe("EXPORT");
    expect(govde).not.toHaveProperty("method");
    expect(await screen.findByText(/7 nüsha kendi barkoduyla kayda girdi/)).toBeInTheDocument();
  });
});

describe("İçe Aktarma — dışa aktarım dosyasında hepsi ya da hiçbiri", () => {
  it("aktarılamayan satır varken Uygula kapalıdır ve nedeni yazar", async () => {
    // F10 düzeltme turu: reddedilen satırın numarası sayaç ilerlediği için bir daha
    // kullanılamazdı; kısmi uygulama yoktur (sunucu da reddeder).
    kapi.aktarimOnizle.mockResolvedValue(
      aktarimRaporu({
        source: "EXPORT",
        stats: aktarimSayilari({ imported_rows: 5, skipped_rows: 1, error_rows: 1 }),
      }),
    );
    const user = userEvent.setup();
    ekranaBas();
    await user.selectOptions(await screen.findByLabelText("İçe aktarılacak dosya"), "disa_aktarim");
    const dosya = new File(["x"], "katalog.xlsx", { type: "application/vnd.ms-excel" });
    await user.upload(screen.getByLabelText(/^Dosya/), dosya);
    await user.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByText(aktarilmayanSatirEngeli(2))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
    expect(DISA_AKTARIM_ACIKLAMASI).toContain("boş bir kataloga");
    expect(DISA_AKTARIM_ACIKLAMASI).toContain("bütün satırlarla");
  });
});

describe("İçe Aktarma — Raporlar'dan gelen bağlantı", () => {
  it("?dosya=disa-aktarim ile Excel Aktarımı dışa aktarım dosyası seçili açılır", async () => {
    render(
      <MemoryRouter initialEntries={[DISA_AKTARIM_ICE_AKTARMA_ADRESI]}>
        <SnackbarProvider>
          <ConfirmProvider>
            <Routes>
              <Route path="/katalog/ice-aktarma" element={<IceAktarmaPage />} />
            </Routes>
          </ConfirmProvider>
        </SnackbarProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByLabelText("İçe aktarılacak dosya")).toHaveValue("disa_aktarim");
    expect(screen.getByText(DISA_AKTARIM_ACIKLAMASI)).toBeInTheDocument();
  });

  it("parametresiz açılışta olağan Excel listesi seçilidir", async () => {
    ekranaBas();
    expect(await screen.findByLabelText("İçe aktarılacak dosya")).toHaveValue("liste");
  });
});
