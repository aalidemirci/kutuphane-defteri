// Katalog sayfası: sunucu tarafı arama (gecikmeli), süzgeçler, sayfalama, boş
// durum, eser ekleme ve nüsha sekmesi.
//
// Sabitlenen davranışlar:
//   1) arama HER TUŞTA istek atmaz — gecikme dolunca TEK istek gider ve sorgu
//      sunucuya olduğu gibi iletilir (katlama sunucudadır, T7);
//   2) süzgeç ya da sıralama değişince sayfa BAŞA döner (yoksa kullanıcı 3.
//      sayfada boş liste görürdü);
//   3) sayfalama sunucudadır: "Sonraki" offset ile yeni istek atar;
//   4) eser eklemede boş kaynak adı istemcide durur, kayıt sonrası ayrıntıya gidilir.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { bolum, eser, nusha, sayfa } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  listWorks: vi.fn(),
  listCopies: vi.fn(),
  listSections: vi.fn(),
  createWork: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import KatalogPage from "./KatalogPage";

function ekranaBas(yol = "/katalog") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog" element={<KatalogPage />} />
            <Route path="/katalog/eser/:id" element={<h1>ESER AYRINTISI</h1>} />
            <Route path="/katalog/edinimler" element={<h1>EDİNİMLER</h1>} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

/** `listWorks`'e giden son çağrının parametreleri. */
function sonEserSorgusu(): Record<string, unknown> {
  const cagrilar = kapi.listWorks.mock.calls;
  return cagrilar[cagrilar.length - 1][0] as Record<string, unknown>;
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.listSections.mockResolvedValue(sayfa([bolum(), bolum({ id: 2, name: "Tarih" })]));
  kapi.listWorks.mockResolvedValue(sayfa([eser()]));
  kapi.listCopies.mockResolvedValue(sayfa([nusha()]));
});

describe("Katalog — eser listesi", () => {
  it("eserleri künye sütunlarıyla listeler", async () => {
    ekranaBas();

    expect(await screen.findByRole("heading", { level: 1, name: "Katalog" })).toBeInTheDocument();
    await screen.findByText("Şiir Defteri");
    // Süzgeç seçeneklerinde de aynı metinler var; satır TABLODA aranır.
    const tablo = within(screen.getByRole("table"));
    expect(tablo.getByText("Ayşe Yılmaz")).toBeInTheDocument();
    expect(tablo.getByText("Edebiyat")).toBeInTheDocument();
    expect(tablo.getByText("Kitap")).toBeInTheDocument();
  });

  it("kayıt yokken boş durum kartı çıkar", async () => {
    kapi.listWorks.mockResolvedValue(sayfa([]));
    ekranaBas();

    expect(await screen.findByText("Gösterilecek eser yok")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("arama gecikmelidir: yazarken istek çıkmaz, gecikme dolunca tek istek gider", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Şiir Defteri");
    expect(kapi.listWorks).toHaveBeenCalledTimes(1);

    await user.type(screen.getByLabelText("Ara"), "şiir");

    // Tuş başına istek ATILMAZ (dört harf = dört istek değil).
    expect(kapi.listWorks).toHaveBeenCalledTimes(1);

    await waitFor(() => expect(kapi.listWorks).toHaveBeenCalledTimes(2));
    expect(sonEserSorgusu().q).toBe("şiir");
  });

  it("arama kutusunun yardım metni gerçek davranışı anlatır", async () => {
    // 'ı' ile 'i' BİLİNÇLİ olarak ayrıdır (T7). "Türkçe harfler ayırt edilmez"
    // demek kullanıcıyı "ilik" yazıp sonuç bulamayınca kayıt yok sanmaya iter.
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    const yardim = screen.getByText(/“ı” ile “i” ayrı harflerdir/);
    expect(yardim).toBeInTheDocument();
    expect(screen.queryByText(/Türkçe harfler ayırt edilmez/)).toBeNull();
  });

  it("süzgeç ve sıralama sunucuya gider, sayfa başa döner", async () => {
    const user = userEvent.setup();
    kapi.listWorks.mockResolvedValue(sayfa([eser()], 60));
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    // Önce ikinci sayfaya geç.
    await user.click(screen.getByRole("button", { name: /Sonraki/ }));
    await waitFor(() => expect(sonEserSorgusu().offset).toBe(25));

    await user.selectOptions(screen.getByLabelText("Bölüm"), "2");
    await waitFor(() => expect(sonEserSorgusu().section).toBe(2));
    expect(sonEserSorgusu().offset).toBe(0);

    await user.selectOptions(screen.getByLabelText("Kaynak türü"), "PERIODICAL");
    await waitFor(() => expect(sonEserSorgusu().resourceType).toBe("PERIODICAL"));

    await user.selectOptions(screen.getByLabelText("Sırala"), "author");
    await waitFor(() => expect(sonEserSorgusu().order).toBe("author"));
  });

  it("sayfalama sunucudadır: kayıt aralığı ve toplam sayı gösterilir", async () => {
    kapi.listWorks.mockResolvedValue(sayfa([eser()], 60));
    ekranaBas();

    expect(await screen.findByText("1–25 / 60 kayıt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Önceki/ })).toBeDisabled();
  });
});

describe("Katalog — eser ekleme", () => {
  it("kaynak adı boşken sunucuya gidilmez, alan hatası gösterilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("button", { name: "Eser ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    expect(await within(diyalog).findByText("Kaynak adı yazılmalıdır.")).toBeInTheDocument();
    expect(kapi.createWork).not.toHaveBeenCalled();
  });

  it("kaydedilen eserin ayrıntı sayfasına gidilir", async () => {
    const user = userEvent.setup();
    kapi.createWork.mockResolvedValue(eser({ id: 42, title: "Ilık Sular" }));
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("button", { name: "Eser ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await user.type(within(diyalog).getByLabelText(/Kaynak adı/), "Ilık Sular");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.createWork).toHaveBeenCalled());
    expect((kapi.createWork.mock.calls[0][0] as { title: string }).title).toBe("Ilık Sular");
    expect(await screen.findByRole("heading", { name: "ESER AYRINTISI" })).toBeInTheDocument();
  });
});

describe("Katalog — nüsha sekmesi", () => {
  it("nüshaları barkod ve ödünç durumuyla listeler", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("tab", { name: "Nüshalar" }));

    expect(await screen.findByText("2026-000123")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Rafta")).toBeInTheDocument();
  });

  it("ödünç verilemeyen nüshada gerekçe gösterilir (kişisel veri taşımaz)", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([
        nusha({
          is_reference: true,
          is_loanable: false,
          not_loanable_reason: "Ödünç verilmez — kütüphanede okunur.",
        }),
      ]),
    );
    ekranaBas();
    await screen.findByText("Şiir Defteri");
    await user.click(screen.getByRole("tab", { name: "Nüshalar" }));

    expect(await screen.findByText("Ödünç verilmez — kütüphanede okunur.")).toBeInTheDocument();
  });

  it("süzgeçler sunucuya gider (barkod gecikmeli, onay kutuları anında)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Şiir Defteri");
    await user.click(screen.getByRole("tab", { name: "Nüshalar" }));
    await screen.findByText("2026-000123");

    await user.click(screen.getByLabelText("Yalnız ödünç verilebilenler"));
    await waitFor(() => {
      const son = kapi.listCopies.mock.calls[kapi.listCopies.mock.calls.length - 1][0] as {
        onlyLoanable: boolean;
      };
      expect(son.onlyLoanable).toBe(true);
    });

    await user.type(screen.getByLabelText("Barkod"), "2026-000123");
    await waitFor(() => {
      const son = kapi.listCopies.mock.calls[kapi.listCopies.mock.calls.length - 1][0] as {
        barcode: string;
      };
      expect(son.barcode).toBe("2026-000123");
    });
  });
});

describe("Katalog — hata ve gezinme", () => {
  it("liste yüklenemezse hata bandı çıkar", async () => {
    kapi.listWorks.mockRejectedValue(new Error("ağ yok"));
    ekranaBas();

    expect(await screen.findByRole("alert")).toHaveTextContent("Eser listesi yüklenemedi.");
  });

  it("Edinimler ve Bağışlar bağlantısı o ekrana götürür", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("link", { name: "Edinimler ve Bağışlar" }));

    expect(await screen.findByRole("heading", { name: "EDİNİMLER" })).toBeInTheDocument();
  });
});
