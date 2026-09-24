// Güvenlik ayarları testi: dürüst KVKK metni, parola değiştirme akışı, "Parolayı
// kaldır" ve "Parolayı kur" eylemlerinin OLMAMASI (tasarım §6.3 — parola yalnız
// kurulum sihirbazının ilk adımında kurulur; burada sihirbaza bağlantı durur),
// kurtarma anahtarı çıktısını elindeki anahtarla yeniden alma kartı (E14) ve
// kurtarma anahtarının doğrulanması/yenilenmesi (F1 eki, 22.09.2026 kararı 2).

import { render, screen, waitFor, within } from "@testing-library/react";
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
  kurtarmaAnahtariniDogrula: vi.fn(),
  kurtarmaAnahtariniYenile: vi.fn(),
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
import { bekleyenKurtarmaAnahtariniYaz } from "./bekleyenAnahtar";

const PAROLASIZ = {
  password_set: false,
  locked: false,
  security_file_missing: false,
  reset_available: false,
  transition_pending: false,
  transition: "",
  recovery_key_confirmed: false,
  protected_fields: ["ad", "soyad"],
};
const PAROLALI = { ...PAROLASIZ, password_set: true, recovery_key_confirmed: true };
/** Anahtarı doğrulanmamış kurulum (karardan önce tamamlanmış ya da yenilenmiş anahtar). */
const DOGRULANMAMIS = { ...PAROLALI, recovery_key_confirmed: false };
const YENI_ANAHTAR = "YENI-ANAH-TARD-EFGH-JKLM-NOPQ-RSTU-VWXY";

/** "Kurtarma Anahtarını Doğrula" kartının formu (PDF kartıyla aynı etiketi taşır). */
function dogrulamaFormu(): HTMLElement {
  const dugme = screen.getByRole("button", { name: "Doğrula" });
  const form = dugme.closest("form");
  if (form === null) throw new Error("Doğrulama formu bulunamadı.");
  return form;
}

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
    // Bekleyen anahtar modül belleğindedir: testler arasında sızmasın.
    bekleyenKurtarmaAnahtariniYaz(null);
    vi.spyOn(Math, "random").mockReturnValue(0.125); // sorulan gruplar: 1. ve 2.
  });

  it("parolasız durumda dürüst kapsam metnini ve korunan alanları gösterir", async () => {
    ekranaBas();
    expect(await screen.findByText("Yönetici parolası kurulmadı.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Yönetici Parolası ve Şifreleme" }),
    ).toBeInTheDocument();
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
    expect(await screen.findByText("Yönetici parolası kurulmadı.")).toBeInTheDocument();
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

    expect(await screen.findByText("Kişisel veri alanları şifreli.")).toBeInTheDocument();
    // Kart başlığı durumla DEĞİŞMEZ (sözlük §4.6): yol tarifi hep aynı addır.
    expect(
      screen.getByRole("heading", { name: "Yönetici Parolası ve Şifreleme" }),
    ).toBeInTheDocument();
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

  it("anahtar doğrulanmamışsa uyarı ve doğrulama kartı çıkar; doğrulanınca kalkar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(DOGRULANMAMIS);
    guvenlik.kurtarmaAnahtariniDogrula.mockResolvedValue(PAROLALI);
    ekranaBas();

    expect(await screen.findByText(/Kurtarma anahtarı doğrulanmadı/)).toBeInTheDocument();
    const form = dogrulamaFormu();
    await kullanici.type(within(form).getByLabelText(/^Kurtarma anahtarı/), "AAAA-BBBB");
    await kullanici.click(within(form).getByRole("button", { name: "Doğrula" }));

    await waitFor(() =>
      expect(guvenlik.kurtarmaAnahtariniDogrula).toHaveBeenCalledWith("AAAA-BBBB"),
    );
    expect(
      await screen.findByText("Kurtarma anahtarının saklandığı doğrulandı."),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Kurtarma anahtarı doğrulanmadı/)).toBeNull());
  });

  it("yanlış anahtarda doğrulama kartı backend iletisini gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(DOGRULANMAMIS);
    guvenlik.kurtarmaAnahtariniDogrula.mockRejectedValue(
      new ApiError(400, "validation_error", "Kurtarma anahtarı hatalı.", {}),
    );
    ekranaBas();

    await screen.findByRole("heading", { name: "Kurtarma Anahtarını Doğrula" });
    const form = dogrulamaFormu();
    await kullanici.type(within(form).getByLabelText(/^Kurtarma anahtarı/), "YANLIS");
    await kullanici.click(within(form).getByRole("button", { name: "Doğrula" }));

    expect(await screen.findByText("Kurtarma anahtarı hatalı.")).toBeInTheDocument();
    expect(screen.getByText(/Kurtarma anahtarı doğrulanmadı/)).toBeInTheDocument();
  });

  it("kurtarma anahtarını yeniler: parola ister, yeni anahtarı bir kez gösterir, doğrulatır", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.kurtarmaAnahtariniYenile.mockResolvedValue({
      ...DOGRULANMAMIS,
      recovery_key: YENI_ANAHTAR,
    });
    guvenlik.kurtarmaAnahtariniDogrula.mockResolvedValue(PAROLALI);
    ekranaBas();

    await kullanici.click(
      await screen.findByRole("button", { name: "Kurtarma anahtarını yenile" }),
    );
    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarı yenilensin mi?" });
    // Dürüst metinler: eski yedekler ve ele geçmiş anahtar.
    expect(within(diyalog).getByText(/Bugünden önce alınmış yedekler/)).toBeInTheDocument();
    expect(
      within(diyalog).getByText(/eline geçmiş bir anahtara karşı koruma değildir/),
    ).toBeInTheDocument();
    await kullanici.type(within(diyalog).getByLabelText(/^Yönetici parolası/), "Deneme-Parola-1");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yeni anahtar üret" }));

    await waitFor(() =>
      expect(guvenlik.kurtarmaAnahtariniYenile).toHaveBeenCalledWith("Deneme-Parola-1"),
    );
    expect(await screen.findByTestId("kurtarma-anahtari")).toHaveTextContent(YENI_ANAHTAR);
    expect(
      await screen.findByText("Yeni kurtarma anahtarı üretildi. Saklayıp doğrulayın."),
    ).toBeInTheDocument();

    // Yeni anahtar da saklanıp doğrulanır (iki grup → sunucu damgası).
    await kullanici.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));
    const gruplar = YENI_ANAHTAR.split("-");
    await kullanici.type(screen.getByLabelText("1. grup"), gruplar[0]);
    await kullanici.type(screen.getByLabelText("2. grup"), gruplar[1]);

    await waitFor(() =>
      expect(guvenlik.kurtarmaAnahtariniDogrula).toHaveBeenCalledWith(YENI_ANAHTAR),
    );
    // Doğrulanınca anahtar bellekten bırakılır (panel kalkar) ve durum yeniden okunur.
    await waitFor(() => expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull());
    expect(guvenlik.durum.mock.calls.length).toBeGreaterThan(1);
  });

  it("yenilemede yanlış parola: ileti gösterilir, yeni anahtar gösterilmez", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    guvenlik.kurtarmaAnahtariniYenile.mockRejectedValue(
      new ApiError(400, "validation_error", "Parola hatalı.", {}),
    );
    ekranaBas();

    await kullanici.click(
      await screen.findByRole("button", { name: "Kurtarma anahtarını yenile" }),
    );
    const diyalog = await screen.findByRole("dialog");
    await kullanici.type(within(diyalog).getByLabelText(/^Yönetici parolası/), "yanlis");
    await kullanici.click(within(diyalog).getByRole("button", { name: "Yeni anahtar üret" }));

    expect(await within(diyalog).findByText("Parola hatalı.")).toBeInTheDocument();
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
  });

  it("parolasızken yenileme ve doğrulama kartları yoktur", async () => {
    ekranaBas();
    expect(await screen.findByText("Yönetici parolası kurulmadı.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kurtarma Anahtarını Yenile" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Kurtarma Anahtarını Doğrula" })).toBeNull();
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

  // Parola pencereleri açılınca parola alanı odaktadır (`ui/Dialog` `initialFocusRef`;
  // tasarım §14.1 F6 ekleri 23).
  it("parola değiştirme penceresi açılınca “Mevcut parola” alanı odaktadır", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    ekranaBas();

    await kullanici.click(await screen.findByRole("button", { name: "Parolayı değiştir" }));

    expect(screen.getByLabelText(/Mevcut parola/)).toHaveFocus();
  });

  it("kurtarma anahtarı yenileme penceresi açılınca parola alanı odaktadır", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(PAROLALI);
    ekranaBas();

    await kullanici.click(
      await screen.findByRole("button", { name: "Kurtarma anahtarını yenile" }),
    );
    const diyalog = await screen.findByRole("dialog", { name: "Kurtarma anahtarı yenilensin mi?" });

    expect(within(diyalog).getByLabelText(/^Yönetici parolası/)).toHaveFocus();
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
