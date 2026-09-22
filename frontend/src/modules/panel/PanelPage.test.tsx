// Genel Bakış: gezinme kartları, "Katalog Excel Şablonu" indirme kartı ve
// "Başlangıç Yol Haritası" (kurulumdan sonra; işaretler backend'de saklanır,
// bütün maddeler tamamlanınca kart gizlenebilir).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { KURULU_DURUM } from "../../test/kurulumDurumu";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { RoadmapState, SetupStatus } from "../okul/api";

const oapi = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  markRoadmapItem: vi.fn(),
  setRoadmapHidden: vi.fn(),
}));
const kapi = vi.hoisted(() => ({ catalogTemplate: vi.fn() }));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: oapi,
}));
vi.mock("../kutuphane/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../kutuphane/api")>()),
  kutuphaneApi: kapi,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: indirme.saveBlob,
}));

import PanelPage from "./PanelPage";

/** Bütün maddeler tamam: aktarımlar yapılmış, kapalı gün girilmiş, dört işaret konmuş. */
const HEPSI_TAMAM: SetupStatus = {
  ...KURULU_DURUM,
  student_count: 480,
  personnel_count: 36,
  school_break_count: 2,
  roadmap: {
    marks: {
      katalog_sablonu: "2026-09-22",
      kurtarma_zarfi: "2026-09-22",
      parola_paylasimi: "2026-09-22",
      btr_gorusmesi: "2026-09-22",
    },
    hidden: false,
  },
};

function bas() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <PanelPage />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

function yolHaritasi(): HTMLElement {
  return screen.getByRole("region", { name: "Başlangıç Yol Haritası" });
}

beforeEach(() => {
  oapi.getSetupStatus.mockResolvedValue(KURULU_DURUM);
});

afterEach(() => vi.clearAllMocks());

describe("Genel Bakış", () => {
  it("sayfanın tek adı Genel Bakış'tır; gezinme kartları sayfalarına gider", async () => {
    bas();
    await screen.findByRole("heading", { name: "Başlangıç Yol Haritası" });

    expect(screen.getByRole("heading", { level: 1, name: "Genel Bakış" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Öğrenci, öğretmen ve diğer personel sicili/ }),
    ).toHaveAttribute("href", "/kisiler");
    expect(
      screen.getByRole("link", { name: /Ders yılı, şubeler, okul bilgileri/ }),
    ).toHaveAttribute("href", "/ayarlar");
  });

  it("Katalog Excel Şablonu kartı indirme düğmesiyle görünür (bir sayfaya gitmez)", async () => {
    bas();
    await screen.findByRole("heading", { name: "Başlangıç Yol Haritası" });

    expect(screen.getByRole("heading", { name: "Katalog Excel Şablonu" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Katalog Excel Şablonu/ })).not.toBeInTheDocument();
  });
});

describe("Başlangıç Yol Haritası", () => {
  it("yeni kurulumda yedi madde yapılacak olarak görünür, ilerleme 0/7", async () => {
    bas();

    expect(
      await screen.findByRole("heading", { name: "Başlangıç Yol Haritası" }),
    ).toBeInTheDocument();
    const kart = yolHaritasi();
    expect(within(kart).getAllByRole("listitem")).toHaveLength(7);
    expect(within(kart).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(within(kart).getByText(/7 maddeden 0 tanesi tamamlandı/)).toBeInTheDocument();
    expect(within(kart).queryByRole("button", { name: "Kartı gizle" })).toBeNull();
  });

  it("gizlenmiş kart görünmez; durum okunamazsa da sayfa çalışır", async () => {
    oapi.getSetupStatus.mockResolvedValueOnce({
      ...KURULU_DURUM,
      roadmap: { marks: {}, hidden: true },
    });
    const { unmount } = bas();
    await waitFor(() => expect(oapi.getSetupStatus).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Başlangıç Yol Haritası" })).toBeNull();
    unmount();

    oapi.getSetupStatus.mockRejectedValueOnce(new Error("ağ yok"));
    bas();
    await waitFor(() => expect(oapi.getSetupStatus).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("heading", { name: "Başlangıç Yol Haritası" })).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Genel Bakış" })).toBeInTheDocument();
  });

  it("elle işaretlenen madde backend'e yazılır ve tarihiyle görünür", async () => {
    const user = userEvent.setup();
    const yeni: RoadmapState = { marks: { kurtarma_zarfi: "2026-09-22" }, hidden: false };
    oapi.markRoadmapItem.mockResolvedValue(yeni);
    bas();

    const kutu = await screen.findByRole("checkbox", {
      name: /Kurtarma anahtarını müdürlükte kapalı zarfta saklayın — yapıldı/,
    });
    await user.click(kutu);

    expect(oapi.markRoadmapItem).toHaveBeenCalledWith("kurtarma_zarfi", true);
    await waitFor(() => expect(kutu).toBeChecked());
    expect(within(yolHaritasi()).getByText("· 22.09.2026")).toBeInTheDocument();
    expect(within(yolHaritasi()).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
  });

  it("işaret kaydedilemezse hata bildirilir, kutu işaretlenmez", async () => {
    const user = userEvent.setup();
    oapi.markRoadmapItem.mockRejectedValue(
      new ApiError(403, "kip_yetkisiz", "Bu işlem görevli kipinde yapılamaz.", {}),
    );
    bas();

    const kutu = await screen.findByRole("checkbox", { name: /BTR\) görüşün — yapıldı/ });
    await user.click(kutu);

    expect(await screen.findByText("Bu işlem görevli kipinde yapılamaz.")).toBeInTheDocument();
    expect(kutu).not.toBeChecked();
  });

  it("şablon karttan indirilince şablon maddesi kendiliğinden işaretlenir", async () => {
    const user = userEvent.setup();
    kapi.catalogTemplate.mockResolvedValue(new Blob(["xlsx"]));
    oapi.markRoadmapItem.mockResolvedValue({
      marks: { katalog_sablonu: "2026-09-22" },
      hidden: false,
    });
    bas();
    await screen.findByRole("heading", { name: "Başlangıç Yol Haritası" });

    // Karttaki düğme (yol haritasının içindeki değil).
    const kartDugmesi = screen
      .getAllByRole("button", { name: /Şablonu indir/ })
      .find((d) => !yolHaritasi().contains(d));
    expect(kartDugmesi).toBeDefined();
    await user.click(kartDugmesi as HTMLElement);

    await waitFor(() => expect(oapi.markRoadmapItem).toHaveBeenCalledWith("katalog_sablonu", true));
    expect(indirme.saveBlob).toHaveBeenCalledTimes(1);
  });

  it("şablon maddesi yol haritasındaki düğmeyle de indirilir (aynı indirme işlevi)", async () => {
    const user = userEvent.setup();
    kapi.catalogTemplate.mockResolvedValue(new Blob(["xlsx"]));
    oapi.markRoadmapItem.mockResolvedValue({
      marks: { katalog_sablonu: "2026-09-22" },
      hidden: false,
    });
    bas();

    await user.click(
      within(await screen.findByRole("region", { name: "Başlangıç Yol Haritası" })).getByRole(
        "button",
        { name: /Şablonu indir/ },
      ),
    );

    await waitFor(() => expect(oapi.markRoadmapItem).toHaveBeenCalledWith("katalog_sablonu", true));
    expect(kapi.catalogTemplate).toHaveBeenCalledTimes(1);
  });

  it("bütün maddeler tamamsa kart gizlenebilir", async () => {
    const user = userEvent.setup();
    oapi.getSetupStatus.mockResolvedValue(HEPSI_TAMAM);
    oapi.setRoadmapHidden.mockResolvedValue({ ...HEPSI_TAMAM.roadmap, hidden: true });
    bas();

    expect(await screen.findByText("Bütün maddeler tamamlandı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kartı gizle" }));

    expect(oapi.setRoadmapHidden).toHaveBeenCalledWith(true);
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Başlangıç Yol Haritası" })).toBeNull(),
    );
  });
});
