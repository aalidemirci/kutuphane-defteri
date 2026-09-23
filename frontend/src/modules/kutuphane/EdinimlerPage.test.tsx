// Edinimler ve Bağışlar: üç sekme (edinim partileri, bağış ön kayıtları,
// komisyon kararları).
//
// Sabitlenen davranışlar:
//   1) bağış kararı GERİ ALINAMAZ: onay diyaloğundan geçer ve kabul/ret sayısını
//      söyler; ret gerekçesi boşken sunucuya gidilmez;
//   2) ret kararları kalem kimliğinden gerekçeye EŞLEMEDİR (uç sözleşmesi);
//   3) kullanılmış komisyon kararının türü kilitlidir ve "Sil" düğmesi çıkmaz —
//      sunucu da reddeder, arayüz kullanıcıyı boşuna denemeye göndermez;
//   4) süzgeçler sunucuya gider (istemcide liste kesilmez).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  bagisKalemi,
  bagisOnKaydi,
  bolum,
  edinim,
  komisyonKarari,
  sayfa,
} from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  listAcquisitions: vi.fn(),
  createAcquisition: vi.fn(),
  updateAcquisition: vi.fn(),
  deleteAcquisition: vi.fn(),
  listCommissionDecisions: vi.fn(),
  createCommissionDecision: vi.fn(),
  listDonationIntakes: vi.fn(),
  getDonationIntake: vi.fn(),
  createDonationIntake: vi.fn(),
  addDonationItem: vi.fn(),
  removeDonationItem: vi.fn(),
  applyDonationDecision: vi.fn(),
  cancelDonationIntake: vi.fn(),
  listSections: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import EdinimlerPage from "./EdinimlerPage";

function ekranaBas(yol = "/katalog/edinimler") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog" element={<h1>KATALOG</h1>} />
            <Route path="/katalog/edinimler" element={<EdinimlerPage />} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.listAcquisitions.mockResolvedValue(sayfa([edinim()]));
  kapi.listCommissionDecisions.mockResolvedValue(sayfa([komisyonKarari()]));
  kapi.listDonationIntakes.mockResolvedValue(sayfa([bagisOnKaydi()]));
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
});

describe("Edinim partileri", () => {
  it("partileri listeler ve başlık sözlükteki addır", async () => {
    ekranaBas();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Edinimler ve Bağışlar" }),
    ).toBeInTheDocument();
    const tablo = within(await screen.findByRole("table"));
    expect(tablo.getByText("Satın alma")).toBeInTheDocument();
    expect(tablo.getByText("10.09.2026")).toBeInTheDocument();
  });

  it("edinim yolu süzgeci sunucuya gider", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("table");

    await user.selectOptions(screen.getByLabelText("Edinim yolu"), "DONATION");

    await waitFor(() => {
      const son = kapi.listAcquisitions.mock.calls.at(-1)?.[0] as { method: string };
      expect(son.method).toBe("DONATION");
    });
  });

  it("yeni edinim kaydedilir ve liste tazelenir", async () => {
    const user = userEvent.setup();
    kapi.createAcquisition.mockResolvedValue(edinim({ id: 9 }));
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Edinim ekle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yeni edinim" });
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.createAcquisition).toHaveBeenCalled());
    expect(kapi.createAcquisition.mock.calls[0][0]).toMatchObject({ method: "PURCHASE" });
  });

  it("komisyon kararı seçicisi edinim yoluna göre değişir", async () => {
    // "Kaynak seçimi" kararı yalnız bağış kararları yüklendiğinde hiçbir edinime
    // bağlanamıyor, ölü kayıt olarak kalıyordu. Bağışta bağış değerlendirme,
    // öbür yollarda kaynak seçimi kararı listelenir.
    const user = userEvent.setup();
    kapi.listCommissionDecisions.mockImplementation(({ decisionType }: { decisionType?: string }) =>
      Promise.resolve(
        sayfa([
          decisionType === "SELECTION"
            ? komisyonKarari({
                id: 7,
                decision_type: "SELECTION",
                decision_type_display: "Kaynak seçimi",
                decision_no: "2026/9",
              })
            : komisyonKarari(),
        ]),
      ),
    );
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Edinim ekle" }));
    const diyalog = within(await screen.findByRole("dialog", { name: "Yeni edinim" }));
    const secici = diyalog.getByLabelText("Komisyon kararı");

    // Varsayılan yol satın almadır → kaynak seçimi kararı.
    await waitFor(() =>
      expect(within(secici).getByRole("option", { name: /Kaynak seçimi/ })).toBeInTheDocument(),
    );
    expect(within(secici).queryByRole("option", { name: /Bağış değerlendirme/ })).toBeNull();

    // Diyalogdaki alan zorunludur; etiket " *" ile biter (sayfa süzgecinde bitmez).
    await user.selectOptions(diyalog.getByLabelText(/^Edinim yolu/), "DONATION");

    expect(within(secici).getByRole("option", { name: /Bağış değerlendirme/ })).toBeInTheDocument();
    expect(within(secici).queryByRole("option", { name: /Kaynak seçimi/ })).toBeNull();
  });
});

describe("Bağış ön kayıtları", () => {
  async function bagisSekmesi(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("tab", { name: "Bağış Ön Kayıtları" }));
    return screen.findByText("Fatma Aydın");
  }

  it("ön kayıtları listeler ve ayrıntısında kalemleri gösterir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("table");
    await bagisSekmesi(user);

    await user.click(screen.getByRole("button", { name: /bağış ön kaydını aç/ }));
    const diyalog = await screen.findByRole("dialog", { name: "Bağış ön kaydı" });
    expect(within(diyalog).getByText("Ilık Sular")).toBeInTheDocument();
  });

  it("kalem eklenince ön kayıt yeniden okunur", async () => {
    const user = userEvent.setup();
    kapi.addDonationItem.mockResolvedValue(bagisKalemi({ id: 32, title: "İnce Kitap" }));
    kapi.getDonationIntake.mockResolvedValue(
      bagisOnKaydi({ items: [bagisKalemi(), bagisKalemi({ id: 32, title: "İnce Kitap" })] }),
    );
    ekranaBas();
    await screen.findByRole("table");
    await bagisSekmesi(user);
    await user.click(screen.getByRole("button", { name: /bağış ön kaydını aç/ }));
    const diyalog = await screen.findByRole("dialog", { name: "Bağış ön kaydı" });

    await user.type(within(diyalog).getByLabelText("Kaynak adı"), "İnce Kitap");
    await user.click(within(diyalog).getByRole("button", { name: "Kalem ekle" }));

    await waitFor(() =>
      expect(kapi.addDonationItem).toHaveBeenCalledWith(11, {
        title: "İnce Kitap",
        authors: "",
        copies: 1,
      }),
    );
    await waitFor(() => expect(kapi.getDonationIntake).toHaveBeenCalledWith(11));
    expect(await screen.findByText("İnce Kitap")).toBeInTheDocument();
  });

  it("karar onaydan geçer; kabul ve ret kalemleri sözleşmedeki biçimde gider", async () => {
    const user = userEvent.setup();
    const kayit = bagisOnKaydi({
      items: [bagisKalemi(), bagisKalemi({ id: 32, title: "Yıpranmış Kitap" })],
    });
    kapi.listDonationIntakes.mockResolvedValue(sayfa([kayit]));
    kapi.applyDonationDecision.mockResolvedValue({
      intake: { ...kayit, status: "DECIDED", status_display: "Karar işlendi" },
      accepted: 1,
      rejected: 1,
      acquisition: 4,
      work_count: 1,
      copy_count: 1,
    });
    ekranaBas();
    await screen.findByRole("table");
    await bagisSekmesi(user);
    await user.click(screen.getByRole("button", { name: /bağış ön kaydını aç/ }));

    const diyalog = await screen.findByRole("dialog", { name: "Bağış ön kaydı" });
    await user.click(within(diyalog).getByRole("button", { name: "Komisyon kararını uygula" }));

    const kararDiyalogu = await screen.findByRole("dialog", {
      name: "Komisyon kararını uygula",
    });
    await waitFor(() => expect(kapi.listCommissionDecisions).toHaveBeenCalled());
    await user.selectOptions(within(kararDiyalogu).getByLabelText(/Komisyon kararı/), "5");

    // İkinci kalem reddedilsin: kutusu boşaltılır, gerekçe alanı açılır.
    await user.click(within(kararDiyalogu).getByText(/Yıpranmış Kitap/));
    await user.click(within(kararDiyalogu).getByRole("button", { name: "Kararı uygula" }));

    // Gerekçe boşken sunucuya GİDİLMEZ.
    expect(
      await within(kararDiyalogu).findByText("Reddedilen her kalemin gerekçesi yazılmalıdır."),
    ).toBeInTheDocument();
    expect(kapi.applyDonationDecision).not.toHaveBeenCalled();

    await user.type(within(kararDiyalogu).getByLabelText("Ret gerekçesi"), "Yıpranmış");
    await user.click(within(kararDiyalogu).getByRole("button", { name: "Kararı uygula" }));

    const onay = await screen.findByRole("dialog", { name: "Komisyon kararı uygulansın mı?" });
    expect(onay).toHaveTextContent("geri alınamaz");
    await user.click(within(onay).getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(kapi.applyDonationDecision).toHaveBeenCalled());
    expect(kapi.applyDonationDecision.mock.calls[0][1]).toMatchObject({
      commission_decision: 5,
      accepted_ids: [31],
      rejected: { "32": "Yıpranmış" },
    });
  });

  it("iptal gerekçesi sunucuya gider (kapanan kayıtta notlar artık düzenlenemez)", async () => {
    const user = userEvent.setup();
    kapi.cancelDonationIntake.mockResolvedValue(
      bagisOnKaydi({ status: "CANCELLED", status_display: "İptal edildi" }),
    );
    ekranaBas();
    await screen.findByRole("table");
    await bagisSekmesi(user);
    await user.click(screen.getByRole("button", { name: /bağış ön kaydını aç/ }));

    const diyalog = await screen.findByRole("dialog", { name: "Bağış ön kaydı" });
    await user.click(within(diyalog).getByRole("button", { name: "İptal et" }));

    const iptalDiyalogu = await screen.findByRole("dialog", {
      name: "Bağış ön kaydını iptal et",
    });
    await user.type(within(iptalDiyalogu).getByLabelText("İptal gerekçesi"), "Bağış geri verildi");
    await user.click(within(iptalDiyalogu).getByRole("button", { name: "İptal et" }));

    const onay = await screen.findByRole("dialog", { name: "Bağış ön kaydı iptal edilsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "İptal et" }));

    await waitFor(() =>
      expect(kapi.cancelDonationIntake).toHaveBeenCalledWith(11, "Bağış geri verildi"),
    );
  });

  it("kararı işlenmiş ön kayıtta kalem eklenemez ve karar düğmesi yoktur", async () => {
    const user = userEvent.setup();
    kapi.listDonationIntakes.mockResolvedValue(
      sayfa([
        bagisOnKaydi({
          status: "DECIDED",
          status_display: "Karar işlendi",
          decided_at: "2026-09-20T10:00:00+03:00",
          items: [
            bagisKalemi({
              decision: "REJECTED",
              decision_display: "Reddedildi",
              reject_reason: "Ders kitabı",
            }),
          ],
        }),
      ]),
    );
    ekranaBas();
    await screen.findByRole("table");
    await bagisSekmesi(user);
    await user.click(screen.getByRole("button", { name: /bağış ön kaydını aç/ }));

    const diyalog = await screen.findByRole("dialog", { name: "Bağış ön kaydı" });
    expect(within(diyalog).getByText(/Reddedildi · Ders kitabı/)).toBeInTheDocument();
    expect(
      within(diyalog).queryByRole("button", { name: "Komisyon kararını uygula" }),
    ).not.toBeInTheDocument();
    expect(within(diyalog).queryByLabelText("Kaynak adı")).not.toBeInTheDocument();
  });
});

describe("Komisyon kararları", () => {
  it("kullanılmış kararın türü kilitlidir ve silinemez", async () => {
    const user = userEvent.setup();
    kapi.listCommissionDecisions.mockResolvedValue(sayfa([komisyonKarari({ in_use: true })]));
    ekranaBas();
    await screen.findByRole("table");

    await user.click(screen.getByRole("tab", { name: "Komisyon Kararları" }));
    expect(await screen.findByText("Kullanımda")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /kararını düzenle/ }));
    const diyalog = await screen.findByRole("dialog", { name: "Kararı düzenle" });
    expect(within(diyalog).getByLabelText(/Karar türü/)).toBeDisabled();
    expect(within(diyalog).queryByRole("button", { name: "Sil" })).not.toBeInTheDocument();
  });

  it("başkan adı boşken sunucuya gidilmez", async () => {
    const user = userEvent.setup();
    kapi.listCommissionDecisions.mockResolvedValue(sayfa([]));
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Edinimler ve Bağışlar" });

    await user.click(screen.getByRole("tab", { name: "Komisyon Kararları" }));
    await user.click(await screen.findByRole("button", { name: "Karar ekle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yeni komisyon kararı" });
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    expect(await within(diyalog).findByText("Başkan adı yazılmalıdır.")).toBeInTheDocument();
    expect(kapi.createCommissionDecision).not.toHaveBeenCalled();
  });
});
