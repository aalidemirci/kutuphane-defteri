// Çevrimdışı künye yolu (§8.5) — sabitlenen davranışlar:
//
//   1) ISBN listesi belge adı + YEREL tarihle iner.
//   2) Geri yüklenen dosya ÖNİZLENİR; onaylanmadan hiçbir alan yazılmaz.
//   3) Eserde DOLU olan alan işaretsiz gelir (sessizce ezilmez); kullanıcı bilerek
//      işaretlerse yazılır.
//   4) Esere bağlanamayan satır yazılamaz ve bunu söyler.
//   5) Ekran ayrı cihaz kuralını (Yönerge 11/18) yazılı olarak taşır.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  cevrimdisiKunyeOnizleme,
  cevrimdisiKunyeSatiri,
  kunyeAlani,
} from "../../test/kutuphaneVerileri";

const mocks = vi.hoisted(() => ({
  kunyeListesiIndir: vi.fn(),
  kunyeDosyasiOnizle: vi.fn(),
  updateWork: vi.fn(),
  saveBlob: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    kutuphaneApi: {
      ...actual.kutuphaneApi,
      kunyeListesiIndir: mocks.kunyeListesiIndir,
      kunyeDosyasiOnizle: mocks.kunyeDosyasiOnizle,
      updateWork: mocks.updateWork,
    },
  };
});
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: mocks.saveBlob,
}));

import CevrimdisiKunyePaneli from "./CevrimdisiKunyePaneli";

function bas() {
  return render(
    <SnackbarProvider>
      <CevrimdisiKunyePaneli />
    </SnackbarProvider>,
  );
}

/** Doldurulmuş dosyayı seçer. */
async function dosyaYukle(user: ReturnType<typeof userEvent.setup>) {
  const dosya = new File(["x"], "kunye.xlsx");
  await user.upload(screen.getByLabelText(/^Doldurulmuş dosya/), dosya);
  return dosya;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
  mocks.kunyeDosyasiOnizle.mockResolvedValue(cevrimdisiKunyeOnizleme());
  mocks.updateWork.mockResolvedValue({});
});

describe("Çevrimdışı künye", () => {
  it("ayrı cihaz kuralını yazılı olarak taşır", () => {
    bas();

    expect(screen.getByText(/başka bir cihazda/)).toBeInTheDocument();
    expect(
      screen.getByText(/telefon, mobil modem ya da kişisel erişim noktası bağlanarak/),
    ).toBeInTheDocument();
  });

  it("dayanağı depodaki adıyla anar (CLAUDE.md §2-13)", () => {
    const { container } = bas();
    const metin = container.textContent ?? "";

    // Depodaki metnin adı: docs/mevzuat/meb-bilgi-ve-sistem-guvenligi-yonergesi.md.
    // "MEB Bilişim Kaynakları Kullanım Yönergesi" diye bir metin depoda YOKTUR;
    // okul bu ekranı BTR'ye gösterdiğinde atıf tutmalıdır.
    expect(metin).toContain("Millî Eğitim Bakanlığı Bilgi ve Sistem Güvenliği Yönergesi");
    expect(metin).not.toContain("Bilişim Kaynakları Kullanım Yönergesi");
  });

  it("ISBN listesi belge adı + yerel tarihle iner", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 23, 10, 0, 0));
    const blob = new Blob(["xlsx"]);
    mocks.kunyeListesiIndir.mockResolvedValue(blob);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    bas();

    await user.click(screen.getByRole("button", { name: "ISBN listesini indir" }));

    await waitFor(() =>
      expect(mocks.saveBlob).toHaveBeenCalledWith(blob, "ISBN-Künye-Listesi_23.09.2026.xlsx"),
    );
  });

  it("dosya önizlenir; onaylanmadan hiçbir alan yazılmaz", async () => {
    const user = userEvent.setup();
    bas();

    const dosya = await dosyaYukle(user);

    await waitFor(() => expect(mocks.kunyeDosyasiOnizle).toHaveBeenCalledWith(dosya));
    expect(await screen.findByText("Önizleme")).toBeInTheDocument();
    expect(screen.getByText(/Hiçbir kayıt değişmedi/)).toBeInTheDocument();
    expect(mocks.updateWork).not.toHaveBeenCalled();
  });

  it("seçilen alanlar eserin kendi güncelleme isteğiyle yazılır", async () => {
    const user = userEvent.setup();
    bas();
    await dosyaYukle(user);
    await screen.findByText("Önizleme");

    await user.click(screen.getByRole("button", { name: /Seçilenleri kaydet/ }));

    await waitFor(() =>
      expect(mocks.updateWork).toHaveBeenCalledWith(7, { publisher: "Deneme Yayınları" }),
    );
    expect(await screen.findByText("1 eserin künyesi güncellendi.")).toBeInTheDocument();
  });

  it("eserde DOLU olan alan işaretsiz gelir ve sessizce yazılmaz", async () => {
    const user = userEvent.setup();
    mocks.kunyeDosyasiOnizle.mockResolvedValue(
      cevrimdisiKunyeOnizleme({
        satirlar: [
          cevrimdisiKunyeSatiri({
            alanlar: [
              kunyeAlani({
                alan: "publisher",
                etiket: "yayınevi",
                deger: "Başka Yayınları",
                mevcut_deger: "Deneme Yayınları",
                dolu: true,
                farkli: true,
              }),
            ],
          }),
        ],
      }),
    );
    bas();
    await dosyaYukle(user);
    await screen.findByText("Önizleme");

    const kutu = screen.getByRole("checkbox", { name: "yayınevi alanını yaz" });
    expect(kutu).not.toBeChecked();
    expect(screen.getByText("Bu alan dolu")).toBeInTheDocument();
    // Seçili alan olmadığı için kaydetme düğmesi kapalıdır.
    expect(screen.getByRole("button", { name: /Seçilenleri kaydet/ })).toBeDisabled();

    await user.click(kutu);
    await user.click(screen.getByRole("button", { name: /Seçilenleri kaydet/ }));

    await waitFor(() =>
      expect(mocks.updateWork).toHaveBeenCalledWith(7, { publisher: "Başka Yayınları" }),
    );
  });

  it("esere bağlanamayan satır yazılamaz ve bunu söyler", async () => {
    const user = userEvent.setup();
    mocks.kunyeDosyasiOnizle.mockResolvedValue(
      cevrimdisiKunyeOnizleme({
        sayilar: { eslesti: 0, eser_yok: 1, coklu_eser: 0, isbn_yok: 0 },
        satirlar: [
          cevrimdisiKunyeSatiri({ durum: "eser_yok", work: null, work_title: "", alanlar: [] }),
        ],
      }),
    );
    bas();
    await dosyaYukle(user);

    expect(await screen.findByText(/Bu satır bir esere bağlanamadı/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Seçilenleri kaydet/ })).toBeDisabled();
  });

  it("yok sayılan sütunlar söylenir (çevirmen dışarıdan doldurulmaz)", async () => {
    const user = userEvent.setup();
    mocks.kunyeDosyasiOnizle.mockResolvedValue(
      cevrimdisiKunyeOnizleme({ atlanan_sutunlar: ["Çevirmen"] }),
    );
    bas();
    await dosyaYukle(user);

    expect(await screen.findByText(/Yok sayılan sütunlar: Çevirmen/)).toBeInTheDocument();
  });
});
