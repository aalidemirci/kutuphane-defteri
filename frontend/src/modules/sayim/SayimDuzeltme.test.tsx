// Sayım — F9 düzeltme turu (25.09.2026) bulgularını kilitleyen ön yüz testleri:
//
// - sayım fazlası penceresi ve onay kutusu açıkken okutulan kod KAYBOLMAZ: okutma kutusu
//   beklemededir, pencere kapanınca kod işlenir (F6 tamponu bu ekranda da işler);
// - sırada okutma varken sayım tamamlanmaz (tamamlanınca okutma kutusu kalkar, sıradaki kod
//   kaybolurdu); onay kutusu açıkken okutulan kod önce işlenir;
// - "Sayım Fazlası" kartı sayfalıdır, kararı bekleyenleri süzer, sayım sırasında kayda giren
//   etiketi ayrı yazar;
// - onay penceresi kayıtta kayıp ve onarımda görünen noksanlar için uyarır (K1 sonrası kayıp
//   kitapta onaydan önce "Bulundu"); onaylanmama gerekçesinde "Kişi adı yazmayın." durur.
// Bütün adlar uydurmadır.

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { belgeler, fazlaKalemi, ilerleme, kalem, ozet, sayfa, sayim } from "./testVerileri";

const api = vi.hoisted(() => ({
  sayimlar: vi.fn(),
  sayim: vi.fn(),
  okut: vi.fn(),
  kalemler: vi.fn(),
  fazlaEkle: vi.fn(),
  fazlaGuncelle: vi.fn(),
  fazlaCikar: vi.fn(),
  ilerleme: vi.fn(),
  tamamla: vi.fn(),
  onayla: vi.fn(),
  belgeler: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...api } };
});
const kutuphane = vi.hoisted(() => ({ listWorks: vi.fn() }));
vi.mock("../kutuphane/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kutuphane/api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kutuphane } };
});

import { bekleyenOkutmaIletisi } from "./SayimAyrintisi";
import { GEREKCE_YARDIMI, ONAY_BASLIGI, kayipUyarisi, onarimUyarisi } from "./SayimDiyaloglari";
import { OKUTMA_KUTUSU } from "./SayimOkutmasi";
import SayimPage from "./SayimPage";

function ciz(yol = "/katalog/sayim?sayim=7") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <SayimPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

function okutmaYaniti(kod: string) {
  return {
    results: [
      {
        code: "bulundu" as const,
        message: "Bulundu.",
        barcode: kod,
        item: kalem({ result: "FOUND", result_display: "Bulundu" }),
      },
    ],
    summary: ozet(),
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  api.sayim.mockResolvedValue(sayim());
  api.belgeler.mockResolvedValue(belgeler());
  api.ilerleme.mockResolvedValue(ilerleme());
  api.kalemler.mockResolvedValue(sayfa([]));
  api.okut.mockImplementation((_id: number, kodlar: string[]) =>
    Promise.resolve(okutmaYaniti(kodlar[0])),
  );
});

// ============================================================ okutma kuyruğu ve pencereler

describe("Okutma — pencere açıkken kod kaybolmaz", () => {
  it("sayım fazlası penceresi açıkken okutulan kod pencere kapanınca işlenir", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByLabelText(OKUTMA_KUTUSU);
    await user.click(await screen.findByRole("button", { name: "Etiketsiz kitap ekle" }));
    const pencere = await screen.findByRole("dialog", { name: "Etiketsiz kitap ekle" });
    const vazgec = within(pencere).getByRole("button", { name: "Vazgeç" });
    act(() => vazgec.focus());

    await user.keyboard("2026000041{Enter}");
    expect(api.okut).not.toHaveBeenCalled();
    await user.click(vazgec);

    await waitFor(() => expect(api.okut).toHaveBeenCalledWith(7, ["2026000041"]));
  });

  it("sırada okutma varken “Sayımı tamamla” kapalıdır", async () => {
    const user = userEvent.setup();
    let bitir: (() => void) | null = null;
    api.okut.mockImplementation(
      (_id: number, kodlar: string[]) =>
        new Promise((coz) => {
          bitir = () => coz(okutmaYaniti(kodlar[0]));
        }),
    );
    ciz();
    const kutu = await screen.findByLabelText(OKUTMA_KUTUSU);
    const tamamla = screen.getByRole("button", { name: "Sayımı tamamla" });
    expect(tamamla).toBeEnabled();

    await user.type(kutu, "2026000041{Enter}");
    await waitFor(() => expect(tamamla).toBeDisabled());
    act(() => bitir?.());
    await waitFor(() => expect(tamamla).toBeEnabled());
  });

  it("tamamlama onayı açıkken okutulan kod önce işlenir; tamamlama başlamaz", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByLabelText(OKUTMA_KUTUSU);
    await user.click(screen.getByRole("button", { name: "Sayımı tamamla" }));
    const pencere = await screen.findByRole("dialog", { name: "Sayım tamamlansın mı?" });
    const tamamlaDugmesi = within(pencere).getByRole("button", { name: "Tamamla" });
    act(() => tamamlaDugmesi.focus());

    await user.keyboard("2026000042{Enter}");
    expect(api.okut).not.toHaveBeenCalled();
    await user.click(tamamlaDugmesi);

    expect(await screen.findByText(bekleyenOkutmaIletisi(1))).toBeInTheDocument();
    expect(api.tamamla).not.toHaveBeenCalled();
    await waitFor(() => expect(api.okut).toHaveBeenCalledWith(7, ["2026000042"]));
  });
});

// ============================================================ sayım fazlası kartı

describe("Sayım fazlası kartı", () => {
  it("sayfalıdır; kararı bekleyenler süzülür; sayımda kayda giren etiket ayrı yazılır", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(sayim({ summary: ozet({ surplus: 30, surplus_unresolved: 4 }) }));
    api.kalemler.mockImplementation((_id: number, s: { surplus?: boolean; offset?: number }) => {
      if (!s.surplus) return Promise.resolve(sayfa([]));
      const liste = [
        fazlaKalemi({ id: 701, surplus_bound_barcode: "2026-000009" }),
        fazlaKalemi({ id: 702 }),
      ];
      return Promise.resolve({ count: 30, next: null, previous: null, results: liste });
    });
    ciz();

    const liste = await screen.findByRole("list", { name: "Sayım fazlası kitaplar" });
    expect(liste).toHaveTextContent("Sayım sırasında kayda girdi: 2026-000009");
    // Kayda girmiş fazlada karar düğmeleri yok; öbüründe var.
    expect(screen.getAllByRole("button", { name: /için eser seç/ })).toHaveLength(1);
    expect(screen.getByText("30 sayım fazlası · kararı bekleyen 4")).toBeInTheDocument();
    expect(api.kalemler).toHaveBeenCalledWith(7, {
      surplus: true,
      undecided: undefined,
      limit: 25,
      offset: 0,
    });

    await user.selectOptions(screen.getByLabelText("Göster"), "bekleyen");
    await waitFor(() =>
      expect(api.kalemler).toHaveBeenCalledWith(7, {
        surplus: true,
        undecided: true,
        limit: 25,
        offset: 0,
      }),
    );
    // 30 kalem: sayfalama çubuğu ikinci sayfaya geçer.
    await user.click(screen.getAllByRole("button", { name: /Sonraki/ })[0]);
    await waitFor(() =>
      expect(api.kalemler).toHaveBeenCalledWith(7, {
        surplus: true,
        undecided: true,
        limit: 25,
        offset: 25,
      }),
    );
  });
});

// ============================================================ onay penceresi

describe("Onay penceresi — uyarılar ve gerekçe", () => {
  it("kayıtta kayıp ve onarımda görünen noksanlar için uyarır; gerekçede kişi adı uyarısı", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(
      sayim({
        status: "COMPLETED",
        completed_at: "2026-12-22T16:00:00+03:00",
        summary: ozet({ missing_recorded_lost: 1, missing_in_repair: 2 }),
      }),
    );
    api.kalemler.mockImplementation((_id: number, s: { surplus?: boolean; damage?: boolean }) =>
      Promise.resolve(
        sayfa(s.surplus || s.damage ? [] : [kalem({ status_at_completion: "LOST" })]),
      ),
    );
    ciz();
    await user.click(
      await screen.findByRole("button", { name: "Harcama yetkilisinin onayını işle" }),
    );
    const pencere = await screen.findByRole("dialog", { name: ONAY_BASLIGI });
    const uyari = within(pencere).getByRole("note", {
      name: "Kayıtta kayıp ya da onarımda görünen noksanlar",
    });
    expect(uyari).toHaveTextContent(kayipUyarisi(1));
    expect(uyari).toHaveTextContent(onarimUyarisi(2));
    // K1 (25.09.2026): kayıp dosyasında "Bulundu" durdurma sürerken de seçilir — uyarı
    // "Onaylanmadı" yerine onaydan önce bulunmayı söyler.
    expect(kayipUyarisi(1)).toContain("onaydan önce kayıp dosyasında “Bulundu”yu seçin");
    expect(kayipUyarisi(1)).not.toContain("Onaylanmadı");
    expect(
      await within(pencere).findByText(
        "Kitap getirildiyse önce kayıp dosyasında “Bulundu”yu seçin.",
      ),
    ).toBeInTheDocument();

    await user.click(within(pencere).getByRole("checkbox", { name: "Onaylanmadı" }));
    expect(within(pencere).getByText(GEREKCE_YARDIMI)).toBeInTheDocument();
  });
});
