// Güvenlik ayarları testi: dürüst KVKK metni, parola değiştirme akışı, "Parolayı
// kaldır" ve "Parolayı kur" eylemlerinin OLMAMASI (tasarım §6.3 — parola yalnız
// kurulum sihirbazının ilk adımında kurulur; burada sihirbaza bağlantı durur) ve
// kurtarma anahtarı çıktısını elindeki anahtarla yeniden alma kartı (E14).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
  kurtarmaAnahtariPdf: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("./SifreliYedekleme", () => ({ default: () => null }));
vi.mock("./YedektenGeriYukleme", () => ({ default: () => null }));
vi.mock("../../lib/download", async (importOriginal) => {
  const gercek = await importOriginal<typeof import("../../lib/download")>();
  return { ...gercek, saveBlob: download.saveBlob };
});

import GuvenlikAyarlari from "./GuvenlikAyarlari";

const PAROLASIZ = {
  password_set: false,
  locked: false,
  security_file_missing: false,
  reset_available: false,
  transition_pending: false,
  transition: "",
  protected_fields: ["ad", "soyad"],
};
const PAROLALI = { ...PAROLASIZ, password_set: true };

function ekranaBas() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <GuvenlikAyarlari />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

describe("GuvenlikAyarlari", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    guvenlik.durum.mockResolvedValue(PAROLASIZ);
  });

  it("parolasız durumda dürüst kapsam metnini ve korunan alanları gösterir", async () => {
    ekranaBas();
    expect(await screen.findByText("Yönetici parolası kurulmadı")).toBeInTheDocument();
    expect(screen.getByText(/TAM DİSK ŞİFRELEME/)).toBeInTheDocument();
    expect(screen.getByText(/LUKS/)).toBeInTheDocument();
    expect(screen.getByText(/ad, soyad/)).toBeInTheDocument();
    // Okul numarası artık şifrelidir; şifrelenmeyen alanlar da açıkça söylenir.
    expect(screen.getByText(/öğrencilerin okul numaraları/)).toBeInTheDocument();
    expect(screen.getByText(/Sınıf\/şube, üye türü ve tarihler şifrelenmez/)).toBeInTheDocument();
    expect(screen.queryByText(/Okul numarası ve sınıf\/şube bilgisi şifrelenmez/)).toBeNull();
    // Fotoğraf ve sınav belgeleri bu programda yoktur; metin onlardan söz etmez.
    expect(screen.queryByText(/fotoğraf|oturma düzeni|Soru belgesi/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Öğrenci fotoğrafları" })).toBeNull();
  });

  it("parola burada kurulmaz: yalnız kurulum sihirbazına bağlantı durur", async () => {
    ekranaBas();
    expect(await screen.findByText("Yönetici parolası kurulmadı")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /parolasını kur/i })).toBeNull();
    expect(screen.getByRole("link", { name: /Kurulum sihirbazına git/ })).toHaveAttribute(
      "href",
      "/kurulum",
    );
    // Parolasızken çıktı kartı da yoktur (doğrulanacak anahtar yok).
    expect(screen.queryByRole("heading", { name: "Kurtarma anahtarı çıktısı" })).toBeNull();
  });

  it("parolalı durumda değiştirme ve kilitleme sunar; kurma ve kaldırma YOKTUR", async () => {
    guvenlik.durum.mockResolvedValue(PAROLALI);
    ekranaBas();

    expect(await screen.findByText(/Kişisel veri alanları şifreli/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Parolayı değiştir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kilitle" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /kaldır/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /parolasını kur/i })).toBeNull();
  });

  it("kurtarma anahtarı çıktısını elindeki anahtarla PDF olarak yeniden alır", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    const pdf = new Blob(["%PDF-"], { type: "application/pdf" });
    guvenlik.kurtarmaAnahtariPdf.mockResolvedValue(pdf);
    ekranaBas();

    expect(
      await screen.findByRole("heading", { name: "Kurtarma anahtarı çıktısı" }),
    ).toBeInTheDocument();
    const alan = screen.getByLabelText(/^Kurtarma anahtarı/);
    await kullanici.type(alan, "AAAA-BBBB-CCCC-DDDD");
    await kullanici.click(screen.getByRole("button", { name: "PDF olarak kaydet" }));

    await waitFor(() =>
      expect(guvenlik.kurtarmaAnahtariPdf).toHaveBeenCalledWith("AAAA-BBBB-CCCC-DDDD"),
    );
    expect(download.saveBlob).toHaveBeenCalledWith(
      pdf,
      expect.stringMatching(/^Kurtarma-Anahtarı-Çıktısı_\d{2}\.\d{2}\.\d{4}\.pdf$/),
    );
    // Anahtar işi bitince alanda bekletilmez.
    await waitFor(() => expect(alan).toHaveValue(""));
    expect(
      await screen.findByText("Kurtarma anahtarı çıktısı PDF olarak kaydedildi."),
    ).toBeInTheDocument();
  });

  it("yanlış anahtarda backend iletisini gösterir, dosya inmez", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.kurtarmaAnahtariPdf.mockRejectedValue(
      new ApiError(400, "validation_error", "Kurtarma anahtarı hatalı.", {}),
    );
    ekranaBas();

    await kullanici.type(await screen.findByLabelText(/^Kurtarma anahtarı/), "YANLIS");
    await kullanici.click(screen.getByRole("button", { name: "PDF olarak kaydet" }));

    expect(await screen.findByText("Kurtarma anahtarı hatalı.")).toBeInTheDocument();
    expect(download.saveBlob).not.toHaveBeenCalled();
  });

  it("parolayı değiştirir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.parolaDegistir.mockResolvedValue(PAROLALI);
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parolayı değiştir" }));
    await kullanici.type(screen.getByLabelText(/Mevcut parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Yeni-Parola-22");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Yeni-Parola-22");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() =>
      expect(guvenlik.parolaDegistir).toHaveBeenCalledWith("Deneme-Parola-1", "Yeni-Parola-22"),
    );
    expect(await screen.findByText("Yönetici parolası değiştirildi.")).toBeInTheDocument();
  });

  it("eşleşmeyen yeni parola tekrarında istek atmaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parolayı değiştir" }));
    await kullanici.type(screen.getByLabelText(/Mevcut parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Yeni-Parola-22");
    await kullanici.type(screen.getByLabelText(/tekrar/), "baska-bir-sey");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByText("Parolalar eşleşmedi.")).toBeInTheDocument();
    expect(guvenlik.parolaDegistir).not.toHaveBeenCalled();
  });

  it("yanlış mevcut parolada backend mesajını gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.parolaDegistir.mockRejectedValue(new Error("Parola hatalı."));
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parolayı değiştir" }));
    await kullanici.type(screen.getByLabelText(/Mevcut parola/), "yanlis");
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Yeni-Parola-22");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Yeni-Parola-22");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByText("Parola hatalı.")).toBeInTheDocument();
  });
});
