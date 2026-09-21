// Güncelleme bandı testleri: açılışta denetim YOK (tasarım T11), bant yalnız
// elle denetimin yayınladığı sonucu gösterir; ertelenen sürümü yeniden
// göstermez; Ayarlar ekranında (panel oradayken) gizlidir.

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { UpdateStatus } from "./api";
import { denetimSonucunuYayinla } from "./denetimOlayi";
import UpdateBanner from "./UpdateBanner";

const mocks = vi.hoisted(() => ({ check: vi.fn(), downloadInstaller: vi.fn(), saveBlob: vi.fn() }));

vi.mock("./api", () => ({
  updateApi: { check: mocks.check, downloadInstaller: mocks.downloadInstaller },
}));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

const STATUS: UpdateStatus = {
  current_version: "2026.9.0",
  latest_version: "2026.10.0",
  update_available: true,
  release_name: "Ekim sürümü",
  published_at: "2026-10-01T12:00:00Z",
  release_url: "https://example.invalid/kutuphane-defteri/v2026.10.0",
  can_download: true,
  installer_name: "kutuphane-defteri-2026.10.0-win64-setup.exe",
  installer_size: 42,
};

function renderBanner(yol = "/") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <UpdateBanner />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

function yayinla(status: UpdateStatus) {
  act(() => denetimSonucunuYayinla(status));
}

describe("UpdateBanner", () => {
  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("açılışta sürüm denetlemez ve hiçbir şey göstermez", () => {
    const { container } = renderBanner();
    expect(mocks.check).not.toHaveBeenCalled();
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });

  it("elle denetim yeni sürüm bulunca bant görünür ve doğrulanmış kurulum dosyasını indirir", async () => {
    const blob = new Blob(["kurulum"]);
    mocks.downloadInstaller.mockResolvedValue(blob);
    const user = userEvent.setup();
    renderBanner();

    yayinla(STATUS);

    expect(screen.getByText(/Kütüphane Defteri 2026.10.0 hazır/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /güncellemeyi indir/i }));
    await waitFor(() => expect(mocks.downloadInstaller).toHaveBeenCalledTimes(1));
    expect(mocks.saveBlob).toHaveBeenCalledWith(blob, STATUS.installer_name);
    // Bant da kendi başına denetim yapmadı.
    expect(mocks.check).not.toHaveBeenCalled();
  });

  it("indirme başarısızsa Ayarlar'a yönlendiren hata bildirimi çıkar", async () => {
    mocks.downloadInstaller.mockRejectedValue(new Error("kesildi"));
    const user = userEvent.setup();
    renderBanner();
    yayinla(STATUS);

    await user.click(screen.getByRole("button", { name: /güncellemeyi indir/i }));

    expect(await screen.findByText(/Ayarlar → Güncelleme bölümünden/)).toBeInTheDocument();
  });

  it("güncel sonuç yayınlanırsa bant görünmez", () => {
    const { container } = renderBanner();
    yayinla({ ...STATUS, latest_version: STATUS.current_version, update_available: false });
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });

  it("“Daha sonra” sürümü erteler; aynı sürüm yeniden yayınlansa da gösterilmez", async () => {
    const user = userEvent.setup();
    renderBanner();
    yayinla(STATUS);

    await user.click(screen.getByRole("button", { name: "Daha sonra" }));
    expect(screen.queryByText(/Kütüphane Defteri 2026.10.0 hazır/)).not.toBeInTheDocument();
    expect(window.localStorage.getItem("kutuphane-defteri-dismissed-update")).toBe("2026.10.0");

    yayinla(STATUS);
    expect(screen.queryByText(/Kütüphane Defteri 2026.10.0 hazır/)).not.toBeInTheDocument();
  });

  it("Ayarlar ekranında gizlidir (aynı bilgi Güncelleme panelinde)", () => {
    const { container } = renderBanner("/ayarlar");
    yayinla(STATUS);
    expect(container.querySelector('[role="status"]')).not.toBeInTheDocument();
  });

  it("Linux'ta indirme düğmesi yerine paket yönlendirmesi gösterir", () => {
    renderBanner();
    yayinla({ ...STATUS, platform: "linux", can_download: false });
    expect(screen.getByText(/Yeni paketi indirme sayfasından alıp kurun/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /güncellemeyi indir/i })).toBeNull();
  });
});
