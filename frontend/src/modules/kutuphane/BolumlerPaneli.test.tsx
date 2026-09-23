// Ayarlar → Bölümler.
//
// Sabitlenen davranışlar:
//   1) liste sunucunun ÜST SINIRIYLA istenir (seçiciler de aynı listeden
//      beslenir; 25'te kesilen bir liste kullanıcıya bölümü buldurmaz);
//   2) boş ad istemcide durur — teklik ve katlama denetimi sunucudadır;
//   3) silme onay diyaloğundan geçer ve "içinde eser varsa silinemez"i söyler.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { bolum, sayfa } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  listSections: vi.fn(),
  createSection: vi.fn(),
  updateSection: vi.fn(),
  deleteSection: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import BolumlerPaneli from "./BolumlerPaneli";

function ekranaBas() {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <BolumlerPaneli />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
});

describe("Bölümler", () => {
  it("bölümleri listeler; liste üst sınırla istenir", async () => {
    ekranaBas();

    expect(await screen.findByRole("table")).toBeInTheDocument();
    const tablo = within(screen.getByRole("table"));
    expect(tablo.getByText("Edebiyat")).toBeInTheDocument();
    expect(tablo.getByText("800–899")).toBeInTheDocument();
    expect(kapi.listSections).toHaveBeenCalledWith({ limit: 200 });
  });

  it("DOS kısaltması bu ekranda açılır", async () => {
    // docs/sozluk.md §2: açıklanmamış kısaltma kullanılmaz. Kullanıcı bu sekmeyi
    // eser formunu hiç görmeden açabilir; açılım yalnız orada olmamalı.
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("table");

    expect(screen.getByText(/Dewey Onlu Sınıflama \(DOS\)/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Bölüm ekle" }));
    const diyalog = within(await screen.findByRole("dialog", { name: "Yeni bölüm" }));
    expect(diyalog.getByText(/Dewey Onlu Sınıflama \(DOS\)/)).toBeInTheDocument();
  });

  it("hiç bölüm yokken boş durum kartı çıkar", async () => {
    kapi.listSections.mockResolvedValue(sayfa([]));
    ekranaBas();

    expect(await screen.findByText("Henüz bölüm yok")).toBeInTheDocument();
  });

  it("boş ad istemcide durur", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Bölüm ekle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yeni bölüm" });
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    expect(await within(diyalog).findByText("Bölüm adı yazılmalıdır.")).toBeInTheDocument();
    expect(kapi.createSection).not.toHaveBeenCalled();
  });

  it("yeni bölüm kaydedilir", async () => {
    const user = userEvent.setup();
    kapi.createSection.mockResolvedValue(bolum({ id: 2, name: "Tarih" }));
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Bölüm ekle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yeni bölüm" });
    await user.type(within(diyalog).getByLabelText(/Ad/), "Tarih");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.createSection).toHaveBeenCalled());
    expect(kapi.createSection.mock.calls[0][0]).toMatchObject({ name: "Tarih" });
  });

  it("aynı adın sunucudaki reddi alanda gösterilir", async () => {
    const user = userEvent.setup();
    kapi.createSection.mockRejectedValue(
      new ApiError(400, "invalid", "Kayıt doğrulanamadı.", {
        name: ["Bu adda bir bölüm zaten var."],
      }),
    );
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Bölüm ekle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yeni bölüm" });
    await user.type(within(diyalog).getByLabelText(/Ad/), "edebiyat");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    expect(await within(diyalog).findByText("Bu adda bir bölüm zaten var.")).toBeInTheDocument();
  });

  it("silme onaydan geçer ve sonucunu söyler", async () => {
    const user = userEvent.setup();
    kapi.deleteSection.mockResolvedValue(undefined);
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Edebiyat bölümünü düzenle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Bölümü düzenle" });
    await user.click(within(diyalog).getByRole("button", { name: "Sil" }));

    const onay = await screen.findByRole("dialog", { name: "Bölüm silinsin mi?" });
    expect(onay).toHaveTextContent("eser ya da nüsha varsa silinemez");
    await user.click(within(onay).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(kapi.deleteSection).toHaveBeenCalledWith(1));
  });
});
