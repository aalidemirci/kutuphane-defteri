// Şifreli yedek kartı testleri: parola kapısı, yalnız .kdbak indirmesi, dosya
// adında YEREL tarih (UTC `toISOString` değil) ve kripto jargonsuz metin.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const mocks = vi.hoisted(() => ({
  postBlob: vi.fn(),
  saveBlob: vi.fn(),
  get: vi.fn(),
  put: vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  api: { postBlob: mocks.postBlob, get: mocks.get, put: mocks.put },
  ApiError: class extends Error {},
}));
vi.mock("../../lib/download", () => ({ saveBlob: mocks.saveBlob }));

import SifreliYedekleme from "./SifreliYedekleme";

/** Dış yedek hatırlatmasının sunucu özeti (F11) — varsayılan: hiç indirme yok. */
const HIC_INDIRILMEDI = {
  last_download: null,
  reminder_days: 30,
  days_since: 3,
  remind: false,
  min_reminder_days: 7,
  max_reminder_days: 90,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue(HIC_INDIRILMEDI);
});
afterEach(() => vi.useRealTimers());

it("son indirme tarihini gösterir; indirme sonrası tarih yeniden okunur (F11)", async () => {
  mocks.postBlob.mockResolvedValue(new Blob(["x"]));
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  expect(
    await screen.findByText("Bu bilgisayarda henüz şifreli yedek indirilmedi."),
  ).toBeInTheDocument();
  expect(mocks.get).toHaveBeenCalledWith("/backups/external/", { etkinlik: false });

  mocks.get.mockResolvedValue({
    ...HIC_INDIRILMEDI,
    last_download: "2026-09-27T10:15:00+03:00",
    days_since: 0,
  });
  await userEvent.click(screen.getByRole("button", { name: /Şifreli yedeği indir/ }));

  expect(
    await screen.findByText("Son şifreli yedek 27.09.2026 tarihinde indirildi (0 gün önce)."),
  ).toBeInTheDocument();
});

it("hatırlatma süresi seçilince sunucuya yazılır (F11)", async () => {
  mocks.put.mockResolvedValue({ ...HIC_INDIRILMEDI, reminder_days: 60 });
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  const secim = await screen.findByLabelText("Hatırlatma süresi");
  await userEvent.selectOptions(secim, "60");

  await waitFor(() =>
    expect(mocks.put).toHaveBeenCalledWith("/backups/external/", { reminder_days: 60 }),
  );
  expect(await screen.findByText("Hatırlatma süresi kaydedildi.")).toBeInTheDocument();
});

it("hatırlatma süresi dolunca kartta ne yapılacağı yazar; dolmadıysa kalan gün (F11)", async () => {
  mocks.get.mockResolvedValue({
    ...HIC_INDIRILMEDI,
    last_download: "2026-08-01T10:00:00+03:00",
    days_since: 57,
    remind: true,
  });
  const { unmount } = render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Hatırlatma süresi doldu: şifreli yedeği indirip USB belleğe kopyalayın.",
  );
  unmount();

  mocks.get.mockResolvedValue({
    ...HIC_INDIRILMEDI,
    last_download: "2026-09-20T10:00:00+03:00",
    days_since: 7,
  });
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );
  expect(
    await screen.findByText("Genel Bakış 23 gün sonra yeniden hatırlatır."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("hiç indirme yokken ve süre dolmamışken hatırlatma cümlesi çizilmez", async () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );
  expect(
    await screen.findByText("Bu bilgisayarda henüz şifreli yedek indirilmedi."),
  ).toBeInTheDocument();
  expect(screen.queryByText(/yeniden hatırlatır/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Hatırlatma süresi doldu/)).not.toBeInTheDocument();
});

it("parola kurulmadan dış yedek özeti istenmez", () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu={false} />
    </SnackbarProvider>,
  );

  expect(mocks.get).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Hatırlatma süresi")).not.toBeInTheDocument();
});

it("parola yokken şifreli yedek indirmesini kapalı tutar", () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu={false} />
    </SnackbarProvider>,
  );

  expect(screen.getByRole("button", { name: /Şifreli yedeği indir/ })).toBeDisabled();
  expect(screen.getByText(/önce yönetici parolası kurmalısınız/)).toBeInTheDocument();
});

it("yalnız şifreli kdbak dosyasını kullanıcıya indirir", async () => {
  const blob = new Blob(["KDBAK-encrypted"]);
  mocks.postBlob.mockResolvedValue(blob);
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /Şifreli yedeği indir/ }));

  await waitFor(() => {
    expect(mocks.postBlob).toHaveBeenCalledWith("/backups/encrypted/");
    expect(mocks.saveBlob).toHaveBeenCalledWith(
      blob,
      expect.stringMatching(/^kutuphane-defteri-yedek-\d{4}-\d{2}-\d{2}\.kdbak$/),
    );
  });
});

it("dosya adındaki tarih YEREL tarihtir (UTC'den türetilmez)", async () => {
  // Yerel 18 Eylül 00:30: UTC+3'te `toISOString()` hâlâ 17 Eylül der. Sahte saat
  // yalnız Date'i dondurur (zamanlayıcılar gerçek kalır — waitFor çalışsın).
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 18, 0, 30, 0));
  mocks.postBlob.mockResolvedValue(new Blob(["x"]));
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /Şifreli yedeği indir/ }));

  await waitFor(() =>
    expect(mocks.saveBlob).toHaveBeenCalledWith(
      expect.anything(),
      "kutuphane-defteri-yedek-2026-09-18.kdbak",
    ),
  );
});

it("metin kripto jargonu kullanmaz (teknik adlar yalnız Hakkında sayfasında)", async () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );
  // Dış yedek özeti gelsin (durum güncellemesi testin içinde kalsın).
  await screen.findByLabelText("Hatırlatma süresi");

  expect(screen.getByText(/güçlü şifrelemeyle\s+korunur/)).toBeInTheDocument();
  expect(screen.getByText(/ağ diskine/)).toBeInTheDocument();
  expect(screen.queryByText(/X25519|AES-256|NAS/)).not.toBeInTheDocument();
});

it("buluta kopyalamayı önermez (Yönerge 11/23: bulut depolama sistemine veri aktarılmaz)", async () => {
  render(
    <SnackbarProvider>
      <SifreliYedekleme parolaKurulu />
    </SnackbarProvider>,
  );
  await screen.findByLabelText("Hatırlatma süresi");

  expect(screen.getByText(/bulut\s+depolama hizmetine yüklemeyin/)).toBeInTheDocument();
  expect(screen.queryByText(/bulut klasörüne/)).not.toBeInTheDocument();
});
