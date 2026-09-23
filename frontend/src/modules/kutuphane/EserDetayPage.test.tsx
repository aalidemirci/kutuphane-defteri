// Eser Ayrıntısı: künye, ISBN uyarısı, nüsha listesi ve hızlı nüsha açma.
//
// Sabitlenen davranışlar:
//   1) ISBN sağlama uyarısı kaydı engellemez ama EKRANDA DURUR (kapanana dek);
//   2) barkod, kayıt no ve etiket tarihleri SALT OKUNURDUR — düzenleme
//      formunda giriş alanı olarak değil, bilgi satırı olarak görünürler;
//   3) tek nüsha standart uca, birden çok nüsha TOPLU uca gider (her biri ayrı
//      numara alır);
//   4) dijital kaynakta (e-kitap) nüsha açma düğmesi hiç görünmez;
//   5) nüsha silme onay diyaloğundan geçer ve numaranın serbest kalmadığını söyler.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { bolum, edinim, eser, nusha, sayfa } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  getWork: vi.fn(),
  updateWork: vi.fn(),
  deleteWork: vi.fn(),
  listCopies: vi.fn(),
  listSections: vi.fn(),
  listAcquisitions: vi.fn(),
  createCopy: vi.fn(),
  createCopies: vi.fn(),
  updateCopy: vi.fn(),
  deleteCopy: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import EserDetayPage from "./EserDetayPage";

function ekranaBas() {
  return render(
    <MemoryRouter initialEntries={["/katalog/eser/7"]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog" element={<h1>KATALOG</h1>} />
            <Route path="/katalog/eser/:id" element={<EserDetayPage />} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.getWork.mockResolvedValue(eser());
  kapi.listCopies.mockResolvedValue(sayfa([nusha()]));
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
  kapi.listAcquisitions.mockResolvedValue(sayfa([edinim()]));
});

describe("Eser Ayrıntısı — künye", () => {
  it("künyeyi ve nüshaları gösterir; başlık sözlükteki addır", async () => {
    ekranaBas();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Eser Ayrıntısı" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Şiir Defteri")).toBeInTheDocument();
    expect(screen.getByText("Deneme Yayınları")).toBeInTheDocument();
    expect(screen.getByText("811 YIL")).toBeInTheDocument();
    expect(await screen.findByText("2026-000123")).toBeInTheDocument();
  });

  it("ISBN uyarısı bant olarak durur (kayıt engellenmez)", async () => {
    kapi.getWork.mockResolvedValue(
      eser({ isbn: "978-975-000-000-1", isbn_warning: "ISBN sağlama hanesi tutmuyor." }),
    );
    ekranaBas();

    const bant = await screen.findByRole("status", { name: "ISBN uyarısı" });
    expect(bant).toHaveTextContent("ISBN sağlama hanesi tutmuyor.");
  });

  it("eser bulunamazsa boş durum kartı ve hata bandı çıkar", async () => {
    kapi.getWork.mockRejectedValue(new Error("yok"));
    ekranaBas();

    expect(await screen.findByText("Eser bulunamadı")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Eser yüklenemedi.");
  });

  it("künye düzenleme formu kaydedilen kaydı ekrana yansıtır", async () => {
    const user = userEvent.setup();
    kapi.updateWork.mockResolvedValue(eser({ title: "İnce Kitap" }));
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("button", { name: "Künyeyi düzenle" }));
    const diyalog = await screen.findByRole("dialog");
    const ad = within(diyalog).getByLabelText(/Kaynak adı/);
    await user.clear(ad);
    await user.type(ad, "İnce Kitap");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updateWork).toHaveBeenCalled());
    expect(await screen.findByText("İnce Kitap")).toBeInTheDocument();
  });
});

describe("Eser Ayrıntısı — nüsha açma", () => {
  it("tek nüsha standart uca gider", async () => {
    const user = userEvent.setup();
    kapi.createCopy.mockResolvedValue(nusha());
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    await waitFor(() => expect(kapi.createCopy).toHaveBeenCalled());
    expect(kapi.createCopies).not.toHaveBeenCalled();
    expect(kapi.createCopy.mock.calls[0][0]).toMatchObject({ work: 7, acquisition: 3 });
  });

  it("birden çok nüsha toplu uca gider", async () => {
    const user = userEvent.setup();
    kapi.createCopies.mockResolvedValue({ count: 3, results: [] });
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());
    const adet = within(diyalog).getByLabelText("Nüsha sayısı");
    await user.clear(adet);
    await user.type(adet, "3");
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    await waitFor(() => expect(kapi.createCopies).toHaveBeenCalled());
    expect(kapi.createCopies.mock.calls[0][0]).toMatchObject({ count: 3 });
    expect(kapi.createCopy).not.toHaveBeenCalled();
  });

  it("sınır dışı nüsha sayısında sunucuya gidilmez", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    const adet = within(diyalog).getByLabelText("Nüsha sayısı");
    await user.clear(adet);
    await user.type(adet, "500");
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    expect(
      await within(diyalog).findByText("Nüsha sayısı 1 ile 50 arasında olmalıdır."),
    ).toBeInTheDocument();
    expect(kapi.createCopy).not.toHaveBeenCalled();
    expect(kapi.createCopies).not.toHaveBeenCalled();
  });

  it("dijital kaynakta nüsha açma düğmesi yoktur", async () => {
    kapi.getWork.mockResolvedValue(
      eser({ resource_type: "EBOOK", resource_type_display: "E-kitap", is_digital: true }),
    );
    kapi.listCopies.mockResolvedValue(sayfa([]));
    ekranaBas();

    expect(
      await screen.findByText("E-kitap ve e-veri tabanında nüsha açılmaz."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nüsha ekle" })).not.toBeInTheDocument();
  });
});

describe("Eser Ayrıntısı — nüsha düzenleme", () => {
  it("barkod ve kayıt no salt okunurdur, düzenlenen alanlar sunucuya gider", async () => {
    const user = userEvent.setup();
    kapi.updateCopy.mockResolvedValue(nusha({ is_reference: true }));
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    const diyalog = await screen.findByRole("dialog");
    // Salt okunur alanlar bilgi satırıdır, giriş alanı DEĞİL.
    expect(within(diyalog).queryByLabelText("Barkod")).not.toBeInTheDocument();
    expect(within(diyalog).getByText("2026-000123")).toBeInTheDocument();

    await user.click(within(diyalog).getByLabelText("Danışma kaynağı (ödünç verilmez)"));
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updateCopy).toHaveBeenCalled());
    expect(kapi.updateCopy.mock.calls[0][1]).toMatchObject({ is_reference: true });
  });

  it("nüsha silme onay ister ve numaranın serbest kalmadığını söyler", async () => {
    const user = userEvent.setup();
    kapi.deleteCopy.mockResolvedValue(undefined);
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByRole("button", { name: "Sil" }));

    const onay = await screen.findByRole("dialog", { name: "Nüsha silinsin mi?" });
    expect(onay).toHaveTextContent(/Numara serbest kalmaz/);
    expect(kapi.deleteCopy).not.toHaveBeenCalled();

    await user.click(within(onay).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(kapi.deleteCopy).toHaveBeenCalledWith(21));
  });
});
