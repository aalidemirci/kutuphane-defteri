// Görev Devri sihirbazı (F11; tasarım §4.4, E18): adım adım — (1) parola + kurtarma anahtarı
// TEK adımda yenilenir, (2) yeni anahtar KARTIN İÇİNDE saklatılıp doğrulanır, (3) Görev
// devri notu indirilir. Metin dürüsttür: eski parola/anahtar eski bir yedekle kayıtların
// anahtarını verir, devirden sonraki yedekleri de açar. Açık işler yalnız sayıdır. Adlar ve
// anahtar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { GorevDevriDurumu } from "./api";

const guvenlik = vi.hoisted(() => ({
  gorevDevri: vi.fn(),
  gorevDevriBaslat: vi.fn(),
  gorevDevriNotu: vi.fn(),
  kurtarmaAnahtariPdf: vi.fn(),
  kurtarmaAnahtariniDogrula: vi.fn(),
}));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: indirme.saveBlob,
}));

import GorevDevri, {
  ANAHTAR_YOK_METNI,
  GOREV_DEVRI_ADIMLARI,
  GOREV_DEVRI_BASLIGI,
} from "./GorevDevri";
import {
  bekleyenAnahtarKaynagi,
  bekleyenKurtarmaAnahtari,
  bekleyenKurtarmaAnahtariniYaz,
} from "./bekleyenAnahtar";

const BASLAMAMIS: GorevDevriDurumu = {
  started_at: null,
  confirmed_at: null,
  note_available: false,
  open_work: [
    { key: "acik_odunc", label: "İade edilmemiş ödünç", count: 12 },
    { key: "acik_teslim", label: "Geri alınmamış teslim", count: 0 },
    { key: "saklama_onayi", label: "Saklama süresi dolmuş, onay bekleyen kayıt", count: 3 },
  ],
  old_backup_count: 9,
  oldest_backup: "14.09.2026",
  archive_count: 1,
};
const BASLAMIS: GorevDevriDurumu = { ...BASLAMAMIS, started_at: "2026-09-27T10:00:00+03:00" };
const HAZIR: GorevDevriDurumu = {
  ...BASLAMIS,
  confirmed_at: "2026-09-27T10:05:00+03:00",
  note_available: true,
};
const YENI_ANAHTAR = "YENI-ANAH-TARD-EFGH-JKLM-NOPQ-RSTU-VWXY";

function bas(
  ozellikler: { onBasladi?: () => void; onAnahtarDogrulama?: (d: boolean) => void } = {},
) {
  render(
    <SnackbarProvider>
      <GorevDevri anahtarDogrulandi {...ozellikler} />
    </SnackbarProvider>,
  );
}

/** Rayda adımın durumu: `aria-current="step"` yalnız o anki adımdadır. */
function anlikAdim(): string | null {
  const ray = screen.getByRole("list", { name: "Görev devri adımları" });
  const anlik = ray.querySelector('[aria-current="step"]');
  return anlik ? (anlik.textContent ?? "") : null;
}

beforeEach(() => {
  vi.clearAllMocks();
  bekleyenKurtarmaAnahtariniYaz(null);
  guvenlik.gorevDevri.mockResolvedValue(BASLAMAMIS);
  vi.spyOn(Math, "random").mockReturnValue(0.125); // panelde sorulan gruplar: 1. ve 2.
});

describe("Görev Devri sihirbazı — 1. adım", () => {
  it("adımları, dürüst sınırı ve açık işlerin kişisiz sayılarını gösterir", async () => {
    bas();

    expect(await screen.findByRole("heading", { name: GOREV_DEVRI_BASLIGI })).toBeInTheDocument();
    const adimlar = screen.getByRole("list", { name: "Görev devri adımları" });
    for (const ad of GOREV_DEVRI_ADIMLARI) {
      expect(within(adimlar).getByText(ad)).toBeInTheDocument();
    }
    expect(anlikAdim()).toContain("Parola ve anahtar yenilenir");
    // F11 düzeltme turu: eski parola eski bir başlıkla devirden SONRAKİ yedekleri de açar
    // (sunucu testi sabitler); kart "kilidi artık açmaz" demez, masa hesabını anar.
    const sinir = await screen.findByText(/devirden sonra alınan yedekleri de açar/);
    expect(sinir).toHaveTextContent("Windows hesabının parolasını da değiştirin");
    expect(screen.queryByText(/kilidi artık açmaz/)).toBeNull();
    expect(screen.getByText(/9 yedek \(en eskisi 14\.09\.2026\)/)).toBeInTheDocument();
    // Sıfır olan iş listelenmez; yalnız sayı, ad yok. Saklama onayı da devredilen iştir.
    expect(screen.getByText("İade edilmemiş ödünç: 12")).toBeInTheDocument();
    expect(screen.getByText("Saklama süresi dolmuş, onay bekleyen kayıt: 3")).toBeInTheDocument();
    expect(screen.queryByText(/Geri alınmamış teslim/)).not.toBeInTheDocument();
    // Yalnız 1. adımın işi görünür: not formu ve yeniden başlatma yok.
    expect(screen.getByRole("button", { name: "Görev devrini başlat" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Görev devri notunu indir/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Görev devrini yeniden başlat" })).toBeNull();
  });

  it("parola ve anahtarı birlikte yeniler; yeni anahtar kartın içinde gösterilir", async () => {
    guvenlik.gorevDevriBaslat.mockResolvedValue({ recovery_key: YENI_ANAHTAR, handover: BASLAMIS });
    const onBasladi = vi.fn();
    bas({ onBasladi });

    await userEvent.click(await screen.findByRole("button", { name: "Görev devrini başlat" }));
    const diyalog = screen.getByRole("dialog", { name: "Görev devri başlatılsın mı?" });
    await userEvent.type(
      within(diyalog).getByLabelText(/Mevcut yönetici parolası/),
      "eski-parola-1",
    );
    await userEvent.type(within(diyalog).getByLabelText(/Yeni yönetici parolası/), "yeni-parola-2");
    await userEvent.type(within(diyalog).getByLabelText(/Parola \(tekrar\)/), "yeni-parola-2");
    await userEvent.click(
      within(diyalog).getByRole("button", { name: /Parolayı ve anahtarı yenile/ }),
    );

    await waitFor(() =>
      expect(guvenlik.gorevDevriBaslat).toHaveBeenCalledWith("eski-parola-1", "yeni-parola-2"),
    );
    expect(bekleyenKurtarmaAnahtari()).toBe(YENI_ANAHTAR);
    expect(bekleyenAnahtarKaynagi()).toBe("gorev-devri");
    expect(onBasladi).toHaveBeenCalled();
    // 2. adım: anahtar bu kartta (üstteki panelde değil).
    expect(await screen.findByTestId("kurtarma-anahtari")).toHaveTextContent(YENI_ANAHTAR);
    expect(anlikAdim()).toContain("Yeni anahtar saklanır");
    expect(
      screen.getByRole("button", { name: "Görev devrini yeniden başlat" }),
    ).toBeInTheDocument();
  });

  it("parolalar eşleşmezse istek atmaz", async () => {
    bas();

    await userEvent.click(await screen.findByRole("button", { name: "Görev devrini başlat" }));
    const diyalog = screen.getByRole("dialog");
    await userEvent.type(
      within(diyalog).getByLabelText(/Mevcut yönetici parolası/),
      "eski-parola-1",
    );
    await userEvent.type(within(diyalog).getByLabelText(/Yeni yönetici parolası/), "yeni-parola-2");
    await userEvent.type(within(diyalog).getByLabelText(/Parola \(tekrar\)/), "baska-parola-3");
    await userEvent.click(
      within(diyalog).getByRole("button", { name: /Parolayı ve anahtarı yenile/ }),
    );

    expect(await within(diyalog).findByText("Parolalar eşleşmedi.")).toBeInTheDocument();
    expect(guvenlik.gorevDevriBaslat).not.toHaveBeenCalled();
  });

  it("sunucunun reddini diyalogda gösterir (yanlış mevcut parola)", async () => {
    guvenlik.gorevDevriBaslat.mockRejectedValue(
      new ApiError(400, "validation_error", "Parola hatalı.", {}),
    );
    bas();

    await userEvent.click(await screen.findByRole("button", { name: "Görev devrini başlat" }));
    const diyalog = screen.getByRole("dialog");
    await userEvent.type(
      within(diyalog).getByLabelText(/Mevcut yönetici parolası/),
      "yanlis-parola",
    );
    await userEvent.type(within(diyalog).getByLabelText(/Yeni yönetici parolası/), "yeni-parola-2");
    await userEvent.type(within(diyalog).getByLabelText(/Parola \(tekrar\)/), "yeni-parola-2");
    await userEvent.click(
      within(diyalog).getByRole("button", { name: /Parolayı ve anahtarı yenile/ }),
    );

    expect(await within(diyalog).findByText("Parola hatalı.")).toBeInTheDocument();
    expect(bekleyenKurtarmaAnahtari()).toBeNull();
  });

  it("vazgeçilen pencere alanları temizler", async () => {
    bas();

    await userEvent.click(await screen.findByRole("button", { name: "Görev devrini başlat" }));
    const diyalog = screen.getByRole("dialog");
    await userEvent.type(within(diyalog).getByLabelText(/Mevcut yönetici parolası/), "x");
    await userEvent.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await userEvent.click(screen.getByRole("button", { name: "Görev devrini başlat" }));
    expect(screen.getByLabelText(/Mevcut yönetici parolası/)).toHaveValue("");
  });
});

describe("Görev Devri sihirbazı — 2. adım", () => {
  it("anahtar kartta saklanıp doğrulanınca bildirir ve not adımına geçer", async () => {
    guvenlik.gorevDevri.mockResolvedValueOnce(BASLAMIS).mockResolvedValue(HAZIR);
    guvenlik.kurtarmaAnahtariniDogrula.mockResolvedValue({ recovery_key_confirmed: true });
    bekleyenKurtarmaAnahtariniYaz(YENI_ANAHTAR, "gorev-devri");
    const onAnahtarDogrulama = vi.fn();
    bas({ onAnahtarDogrulama });

    await userEvent.click(await screen.findByRole("button", { name: "Sakladım, doğrula" }));
    const gruplar = YENI_ANAHTAR.split("-");
    await userEvent.type(screen.getByLabelText("1. grup"), gruplar[0]);
    await userEvent.type(screen.getByLabelText("2. grup"), gruplar[1]);

    await waitFor(() =>
      expect(guvenlik.kurtarmaAnahtariniDogrula).toHaveBeenCalledWith(YENI_ANAHTAR),
    );
    await waitFor(() => expect(onAnahtarDogrulama).toHaveBeenCalledWith(true));
    expect(onAnahtarDogrulama).not.toHaveBeenCalledWith(false);
    // Durum yeniden okunur: not adımı açılır.
    expect(await screen.findByLabelText("Görevi devreden (adı soyadı)")).toBeInTheDocument();
  });

  it("dinleyici verilmezse kart anahtarı bellekten kendisi bırakır", async () => {
    guvenlik.gorevDevri.mockResolvedValueOnce(BASLAMIS).mockResolvedValue(HAZIR);
    guvenlik.kurtarmaAnahtariniDogrula.mockResolvedValue({ recovery_key_confirmed: true });
    bekleyenKurtarmaAnahtariniYaz(YENI_ANAHTAR, "gorev-devri");
    bas();

    await userEvent.click(await screen.findByRole("button", { name: "Sakladım, doğrula" }));
    const gruplar = YENI_ANAHTAR.split("-");
    await userEvent.type(screen.getByLabelText("1. grup"), gruplar[0]);
    await userEvent.type(screen.getByLabelText("2. grup"), gruplar[1]);

    await waitFor(() => expect(bekleyenKurtarmaAnahtari()).toBeNull());
    expect(bekleyenAnahtarKaynagi()).toBeNull();
  });

  it("anahtar ekranda değilse doğrulama ya da yeniden başlatma yolunu söyler", async () => {
    guvenlik.gorevDevri.mockResolvedValue(BASLAMIS);
    bas();

    expect(await screen.findByText(ANAHTAR_YOK_METNI)).toBeInTheDocument();
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Görev devrini yeniden başlat" }),
    ).toBeInTheDocument();
  });

  it("başka akışın bekleyen anahtarı bu kartta gösterilmez", async () => {
    guvenlik.gorevDevri.mockResolvedValue(BASLAMIS);
    bekleyenKurtarmaAnahtariniYaz(YENI_ANAHTAR); // "Kurtarma anahtarını yenile" (kaynaksız)
    bas();

    expect(await screen.findByText(ANAHTAR_YOK_METNI)).toBeInTheDocument();
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
  });
});

describe("Görev Devri sihirbazı — 3. adım", () => {
  it("doğrulanınca Görev devri notu adlarla indirilir; adlar yalnız istek gövdesindedir", async () => {
    guvenlik.gorevDevri.mockResolvedValue(HAZIR);
    const pdf = new Blob(["%PDF-"]);
    guvenlik.gorevDevriNotu.mockResolvedValue(pdf);
    bas();

    await userEvent.type(
      await screen.findByLabelText("Görevi devreden (adı soyadı)"),
      "Deneme Devreden",
    );
    expect(anlikAdim()).toContain("Görev devri notu basılır");
    expect(screen.getByText(/yeni anahtarın saklandığı doğrulandı/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Görevi devralan (adı soyadı)"), "Deneme Devralan");
    await userEvent.type(screen.getByLabelText(/Ek not/), "Okuyucu kutusunda.");
    await userEvent.click(screen.getByRole("button", { name: /Görev devri notunu indir/ }));

    await waitFor(() =>
      expect(guvenlik.gorevDevriNotu).toHaveBeenCalledWith({
        outgoing_name: "Deneme Devreden",
        incoming_name: "Deneme Devralan",
        note: "Okuyucu kutusunda.",
      }),
    );
    expect(indirme.saveBlob).toHaveBeenCalledWith(
      pdf,
      expect.stringMatching(/^Görev-Devri-Notu_\d{2}\.\d{2}\.\d{4}\.pdf$/),
    );
    // Dosya adı kişi adı taşımaz.
    const [, ad] = indirme.saveBlob.mock.calls[0] as [Blob, string];
    expect(ad).not.toMatch(/Deneme/);
    // Adım tamamlandı: rayda anlık adım kalmaz, imza bilgisi görünür.
    expect(await screen.findByText(/Not indirildi\./)).toBeInTheDocument();
    expect(anlikAdim()).toBeNull();
  });

  it("not hazırlanamazsa ileti gösterilir, dosya inmez", async () => {
    guvenlik.gorevDevri.mockResolvedValue(HAZIR);
    guvenlik.gorevDevriNotu.mockRejectedValue(
      new ApiError(409, "gorev_devri_eksik", "Görev devri notu basılamadı.", {}),
    );
    bas();

    await userEvent.click(await screen.findByRole("button", { name: /Görev devri notunu indir/ }));

    expect(await screen.findByText("Görev devri notu basılamadı.")).toBeInTheDocument();
    expect(indirme.saveBlob).not.toHaveBeenCalled();
    expect(screen.queryByText(/Not indirildi\./)).toBeNull();
  });
});
