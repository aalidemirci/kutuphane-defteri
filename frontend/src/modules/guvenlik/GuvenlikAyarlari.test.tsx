// Güvenlik ayarları testi: yönetici parolası kurma → kurtarma anahtarı
// diyaloğunun ONAYSIZ KAPANMAMASI, parola değiştirme akışı, "Parolayı kaldır"
// eyleminin OLMAMASI (tasarım §6.3) ve dürüst KVKK metni. En kritik iddia:
// kurtarma anahtarı ekranda GÖRÜNÜR ve "kaydettim" işaretlenene kadar "Kapat"
// düğmesi kapalıdır (anahtar bir daha üretilemez).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
}));
const download = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("./SifreliYedekleme", () => ({ default: () => null }));
vi.mock("./YedektenGeriYukleme", () => ({ default: () => null }));
vi.mock("../../lib/download", () => ({ saveBlob: download.saveBlob }));

import GuvenlikAyarlari from "./GuvenlikAyarlari";

const PAROLASIZ = {
  password_set: false,
  locked: false,
  security_file_missing: false,
  transition_pending: false,
  transition: "",
  protected_fields: ["ad", "soyad"],
};
const PAROLALI = { ...PAROLASIZ, password_set: true };

function ekranaBas() {
  return render(
    <SnackbarProvider>
      <GuvenlikAyarlari okulAdi="Deneme Anadolu Lisesi" />
    </SnackbarProvider>,
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
    // Şifrelenmeyen alanlar da açıkça söylenir.
    expect(
      screen.getByText(/Okul numarası ve sınıf\/şube bilgisi şifrelenmez/),
    ).toBeInTheDocument();
    // Fotoğraf ve sınav belgeleri bu programda yoktur; metin onlardan söz etmez.
    expect(screen.queryByText(/fotoğraf|oturma düzeni|Soru belgesi/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Öğrenci fotoğrafları" })).toBeNull();
  });

  it("yönetici parolasını kurar ve kurtarma anahtarını onay alınmadan kapatmaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kur.mockResolvedValue({ ...PAROLALI, recovery_key: "AAAA-BBBB-CCCC-DDDD" });
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Yönetici parolasını kur" }));
    // Parolanın zorunlu ve kaldırılamaz olduğu açıkça söylenir.
    expect(screen.getByText(/Kurulduktan sonra kaldırılamaz/)).toBeInTheDocument();
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarınız" });
    expect(within(diyalog).getByTestId("kurtarma-anahtari")).toHaveTextContent(
      "AAAA-BBBB-CCCC-DDDD",
    );

    const kapat = within(diyalog).getByRole("button", { name: "Kapat" });
    expect(kapat).toBeDisabled();
    await kullanici.click(within(diyalog).getByRole("checkbox"));
    expect(kapat).toBeEnabled();
    await kullanici.click(kapat);
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Kurtarma anahtarınız" })).toBeNull(),
    );
  });

  it("kurtarma anahtarı metin dosyası olarak indirilebilir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kur.mockResolvedValue({ ...PAROLALI, recovery_key: "AAAA-BBBB" });
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Yönetici parolasını kur" }));
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarınız" });
    await kullanici.click(
      within(diyalog).getByRole("button", { name: /Metin dosyası olarak kaydet/ }),
    );
    expect(download.saveBlob).toHaveBeenCalledWith(expect.any(Blob), "kurtarma-anahtari.txt");
  });

  it("eşleşmeyen parola tekrarında istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Yönetici parolasını kur" }));
    await kullanici.type(screen.getByLabelText(/^Yeni parola/), "Deneme-Parola-1");
    await kullanici.type(screen.getByLabelText(/tekrar/), "baska-bir-sey");
    await kullanici.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByText("Parolalar eşleşmedi.")).toBeInTheDocument();
    expect(guvenlik.kur).not.toHaveBeenCalled();
  });

  it("parolalı durumda değiştirme ve kilitleme sunar; parolayı kaldırma YOKTUR", async () => {
    guvenlik.durum.mockResolvedValue(PAROLALI);
    ekranaBas();

    expect(await screen.findByText(/Kişisel veri alanları şifreli/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Parolayı değiştir" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kilitle" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /kaldır/i })).toBeNull();
    expect(screen.queryByRole("button", { name: "Yönetici parolasını kur" })).toBeNull();
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
