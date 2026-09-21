// Güncelleme paneli testleri: denetim YALNIZ düğmeyle (tasarım T11 — sekme
// açılınca istek yok), kullanıcı dili ("yayımlanan son sürüm", "kurulum
// dosyası" — GitHub/Release/kurucu/SHA jargonu yok), doğrulanmış indirme,
// sonucun kabuk bandına yayınlanması ve çevrimdışı hata bandı.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { DENETIM_OLAYI } from "./denetimOlayi";

const mocks = vi.hoisted(() => ({ check: vi.fn(), downloadInstaller: vi.fn(), saveBlob: vi.fn() }));

vi.mock("./api", () => ({
  updateApi: { check: mocks.check, downloadInstaller: mocks.downloadInstaller },
}));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

import UpdatePanel from "./UpdatePanel";

const GUNCEL = {
  current_version: "2026.9.0",
  latest_version: "2026.9.0",
  update_available: false,
  release_name: "Eylül sürümü",
  published_at: "2026-09-01T12:00:00Z",
  release_url: "https://example.invalid/kutuphane-defteri/v2026.9.0",
  can_download: false,
  installer_name: "",
  installer_size: 0,
};

const YENI_SURUM = {
  ...GUNCEL,
  latest_version: "2026.10.0",
  update_available: true,
  can_download: true,
  installer_name: "kutuphane-defteri-2026.10.0-win64-setup.exe",
  installer_size: 43_515_904,
};

function renderPanel() {
  return render(
    <SnackbarProvider>
      <UpdatePanel />
    </SnackbarProvider>,
  );
}

/** Kullanıcının tek denetim yolu: "Şimdi denetle" düğmesi. */
async function denetle() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Şimdi denetle" }));
  return user;
}

afterEach(() => vi.clearAllMocks());

describe("UpdatePanel", () => {
  it("sekme açılınca denetim YAPMAZ; yalnız düğmeyle denetlendiğini söyler", () => {
    renderPanel();

    expect(mocks.check).not.toHaveBeenCalled();
    expect(screen.getByText(/program açılışta internete çıkmaz/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Şimdi denetle" })).toBeEnabled();
    expect(screen.queryByText("Kurulu sürüm")).not.toBeInTheDocument();
  });

  it("sürümleri kullanıcı diliyle gösterir — GitHub/Release/kurucu/SHA jargonu yok", async () => {
    mocks.check.mockResolvedValue(GUNCEL);
    renderPanel();
    await denetle();

    expect(await screen.findByText("Uygulama güncel.")).toBeInTheDocument();
    expect(screen.getByText("Kurulu sürüm")).toBeInTheDocument();
    expect(screen.getByText("Yayımlanan son sürüm")).toBeInTheDocument();
    expect(screen.getByText(/bütünlüğü doğrulanmadan indirmeye sunulmaz/)).toBeInTheDocument();
    expect(screen.queryByText(/GitHub|Release|kurucu|SHA-256/)).not.toBeInTheDocument();
  });

  it("“Şimdi denetle” sunucuyu zorla (önbelleği atlayarak) sorar", async () => {
    mocks.check.mockResolvedValue(GUNCEL);
    renderPanel();
    await denetle();

    await waitFor(() => expect(mocks.check).toHaveBeenCalledTimes(1));
    expect(mocks.check).toHaveBeenCalledWith(true);
  });

  it("denetim sonucunu kabuk bandı için yayınlar", async () => {
    const yakalanan: unknown[] = [];
    const dinleyici = (e: Event) => yakalanan.push((e as CustomEvent).detail);
    window.addEventListener(DENETIM_OLAYI, dinleyici);
    mocks.check.mockResolvedValue(YENI_SURUM);
    renderPanel();
    await denetle();

    await waitFor(() => expect(yakalanan).toEqual([YENI_SURUM]));
    window.removeEventListener(DENETIM_OLAYI, dinleyici);
  });

  it("yeni sürümde kurulum dosyası doğrulanarak indirilir", async () => {
    const blob = new Blob(["kurulum"]);
    mocks.check.mockResolvedValue(YENI_SURUM);
    mocks.downloadInstaller.mockResolvedValue(blob);
    renderPanel();
    const user = await denetle();

    expect(await screen.findByText("Yeni sürüm hazır: 2026.10.0")).toBeInTheDocument();
    // 41,5 MB — Türkçe sayı biçimi (ondalık virgül).
    expect(screen.getByText("Windows kurulum dosyası: 41,5 MB")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Doğrula ve indir" }));

    await waitFor(() =>
      expect(mocks.saveBlob).toHaveBeenCalledWith(blob, YENI_SURUM.installer_name),
    );
    expect(await screen.findByText("Kurulum dosyası doğrulanarak indirildi.")).toBeInTheDocument();
  });

  it("indirme başarısızsa hata bandı gösterilir", async () => {
    mocks.check.mockResolvedValue(YENI_SURUM);
    mocks.downloadInstaller.mockRejectedValue(new Error("kesildi"));
    renderPanel();
    const user = await denetle();

    await user.click(await screen.findByRole("button", { name: "Doğrula ve indir" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Güncelleme dosyası indirilemedi.");
  });

  it("indirilecek dosya yoksa bunu “kurulum dosyası” diye söyler", async () => {
    mocks.check.mockResolvedValue({ ...YENI_SURUM, can_download: false });
    renderPanel();
    await denetle();

    expect(
      await screen.findByText("Bu sürümde Windows kurulum dosyası bulunmuyor."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Doğrula ve indir" })).toBeDisabled();
  });

  it("Pardus/Linux’ta Windows kurulum dosyası önermez, paketle güncellemeye yönlendirir", async () => {
    mocks.check.mockResolvedValue({
      ...YENI_SURUM,
      platform: "linux",
      can_download: false,
      installer_name: "",
      installer_size: 0,
    });
    renderPanel();
    await denetle();

    expect(await screen.findByText("Yeni sürüm hazır: 2026.10.0")).toBeInTheDocument();
    expect(screen.getByText(/güncelleme paketle yapılır/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Doğrula ve indir" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Windows kurulum dosyası/)).not.toBeInTheDocument();
  });

  it("denetim başarısızsa hata canlı bölgede gösterilir", async () => {
    mocks.check.mockRejectedValue(new Error("ağ yok"));
    renderPanel();
    await denetle();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Güncelleme denetlenemedi. İnternet bağlantısını kontrol edin.",
    );
  });
});
