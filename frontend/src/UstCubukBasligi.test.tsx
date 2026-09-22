// Üst çubuk başlığı = ekranın h1'i (docs/sozluk.md §4). Adrese bağlı sayfalar
// için bu `App.test.tsx`'te sabitlenmiştir; burada PROGRAM DURUMU ekranları
// (sözlük §4.2) sınanır: kilitli, güvenlik dosyası kayıp ve yedekten geri
// yükleme sonrası "yeniden başlatın" örtüsü. Bu ekranlar bir rotaya bağlı
// olmadığı için başlığı `ui/DurumBasligi` üzerinden kabuğa kendileri bildirir.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { GuvenlikDurumu } from "./modules/guvenlik/api";
import { ConfirmProvider } from "./ui/ConfirmProvider";
import { SnackbarProvider } from "./ui/SnackbarProvider";
import { KURULU_DURUM } from "./test/kurulumDurumu";

const guvenlikApiMock = vi.hoisted(() => ({
  durum: vi.fn(),
  yedekler: vi.fn(),
}));

vi.mock("./modules/guvenlik/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./modules/guvenlik/api")>();
  return { ...actual, guvenlikApi: { ...actual.guvenlikApi, ...guvenlikApiMock } };
});

const okulApiMock = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getLeavePoolSummary: vi.fn(),
  markRoadmapItem: vi.fn(),
  setRoadmapHidden: vi.fn(),
}));

vi.mock("./modules/okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./modules/okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okulApiMock } };
});

const kipApiMock = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./modules/kip/api", () => ({ kipApi: kipApiMock }));

import App from "./App";
import { KILIT_EKRANI_BASLIGI } from "./modules/guvenlik/KilitEkrani";
import { YENIDEN_BASLAT_BASLIGI } from "./modules/guvenlik/YenidenBaslatEkrani";
import { DOSYA_KAYIP_BASLIGI } from "./modules/guvenlik/metinler";
import { yenidenBaslatGerekliYayinla } from "./lib/restart";

const ACIK: GuvenlikDurumu = {
  password_set: true,
  locked: false,
  security_file_missing: false,
  reset_available: false,
  transition_pending: false,
  transition: "",
  recovery_key_confirmed: true,
  protected_fields: [],
};

function ekranaBas() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <SnackbarProvider>
          <ConfirmProvider>
            <App />
          </ConfirmProvider>
        </SnackbarProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Kabuğun üst çubuğu — DOM'daki ilk `banner` (App.test.tsx ile aynı kalıp). */
function ustCubuk(): HTMLElement {
  return screen.getAllByRole("banner")[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  guvenlikApiMock.durum.mockResolvedValue(ACIK);
  guvenlikApiMock.yedekler.mockResolvedValue({ backup_dir: "", backups: [] });
  okulApiMock.getSetupStatus.mockResolvedValue(KURULU_DURUM);
  okulApiMock.getLeavePoolSummary.mockResolvedValue({ student_count: 0, personnel_count: 0 });
  kipApiMock.durum.mockResolvedValue({
    durum: "yonetici",
    bosta_kalan_sn: 180,
    mutlak_kalan_sn: 1800,
    bosta_dk: 3,
    mutlak_dk: 30,
  });
});

describe("Üst çubuk başlığı — program durumu ekranları", () => {
  it("kilitliyken ekranın h1'i ve üst çubuk aynı başlığı gösterir", async () => {
    guvenlikApiMock.durum.mockResolvedValue({ ...ACIK, locked: true });
    ekranaBas();

    expect(
      await screen.findByRole("heading", { level: 1, name: KILIT_EKRANI_BASLIGI }),
    ).toBeInTheDocument();
    // Başlığı ekran MOUNT sonrası bildirir (etki); üst çubuk bir sonraki
    // çizimde yetişir — bu yüzden `findByText`.
    expect(await within(ustCubuk()).findByText(KILIT_EKRANI_BASLIGI)).toBeInTheDocument();
    expect(within(ustCubuk()).queryByText("Genel Bakış")).not.toBeInTheDocument();
  });

  it("güvenlik dosyası kayıpken ekranın h1'i ve üst çubuk aynı başlığı gösterir", async () => {
    guvenlikApiMock.durum.mockResolvedValue({ ...ACIK, security_file_missing: true });
    ekranaBas();

    expect(
      await screen.findByRole("heading", { level: 1, name: DOSYA_KAYIP_BASLIGI }),
    ).toBeInTheDocument();
    expect(await within(ustCubuk()).findByText(DOSYA_KAYIP_BASLIGI)).toBeInTheDocument();
  });

  it("yeniden başlat örtüsü açılınca üst çubuk onun başlığını gösterir", async () => {
    ekranaBas();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Genel Bakış" }),
    ).toBeInTheDocument();
    expect(within(ustCubuk()).getByText("Genel Bakış")).toBeInTheDocument();

    act(() => yenidenBaslatGerekliYayinla());

    const ortu = screen.getByRole("alertdialog", { name: "Programı yeniden başlatın" });
    expect(ortu).toHaveTextContent(YENIDEN_BASLAT_BASLIGI);
    expect(within(ustCubuk()).getByText(YENIDEN_BASLAT_BASLIGI)).toBeInTheDocument();
    expect(within(ustCubuk()).queryByText("Genel Bakış")).not.toBeInTheDocument();
  });
});
