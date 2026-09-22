// Yedekten geri yükleme kartı testleri: liste, sır zorunluluğu (yedekler DAİMA
// şifrelidir — düz yedek dalı yok), onay akışı, FormData içeriği (kaynak ad YA
// DA dosya) ve başarıda "yeniden başlat" olayının yayınlanması. Backend hatası
// Türkçe mesajıyla kartta gösterilir. Güvenlik dosyası kayıp ekranındaki
// kullanımı (`kayipKipi`) giriş metnini değiştirir.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { YENIDEN_BASLAT_OLAYI } from "../../lib/restart";
import { ConfirmProvider } from "../../ui/ConfirmProvider";

const guvenlik = vi.hoisted(() => ({
  yedekler: vi.fn(),
  geriYukle: vi.fn(),
}));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));

import YedektenGeriYukleme from "./YedektenGeriYukleme";

const LISTE = {
  backup_dir: "C:\\KutuphaneDefteri\\backups",
  backups: [
    {
      name: "gunluk-2026-09-01.kdbak",
      size: 2 * 1024 * 1024,
      modified_at: "2026-09-01T08:00:00+03:00",
    },
    {
      name: "gunluk-2026-08-31.kdbak",
      size: 4096,
      modified_at: "2026-08-31T08:00:00+03:00",
    },
  ],
};

const SONUC = {
  old_db_name: "db-onceki-2026-09-02-101010.sqlite3",
  state_written: false,
  restart_required: true,
};

function ekranaBas(kayipKipi = false) {
  return render(
    <ConfirmProvider>
      <YedektenGeriYukleme kayipKipi={kayipKipi} />
    </ConfirmProvider>,
  );
}

const PAROLA = "Deneme-Parola-1";

/** Onay diyaloğundaki "Geri yükle" düğmesine basar (karttaki eş adlıdan ayrışır). */
async function onayla(kullanici: ReturnType<typeof userEvent.setup>) {
  const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yüklensin mi?" });
  await kullanici.click(within(diyalog).getByRole("button", { name: "Geri yükle" }));
}

describe("YedektenGeriYukleme", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    guvenlik.yedekler.mockResolvedValue(LISTE);
  });

  it("yedekleri ve yedek klasörünü listeler; parola alanları hep görünür", async () => {
    ekranaBas();

    expect(await screen.findByText("gunluk-2026-09-01.kdbak")).toBeInTheDocument();
    expect(screen.getByText("gunluk-2026-08-31.kdbak")).toBeInTheDocument();
    // Düz yedek yoktur: "şifresiz" etiketi de yoktur.
    expect(screen.queryByText(/şifresiz/)).toBeNull();
    expect(screen.getByLabelText("Yönetici parolası")).toBeInTheDocument();
    expect(screen.getByLabelText("Kurtarma anahtarı")).toBeInTheDocument();
    expect(screen.getByText("C:\\KutuphaneDefteri\\backups")).toBeInTheDocument();
    // Kaynak seçilmeden geri yükleme düğmesi kapalıdır.
    expect(screen.getByRole("button", { name: "Geri yükle" })).toBeDisabled();
  });

  it("program açılmıyorsa iki platformun da kurtarma yolunu söyler", async () => {
    ekranaBas();
    await screen.findByText("gunluk-2026-09-01.kdbak");

    // docs/kurulum.md §5.1 ile aynı: Windows kısayolu + Pardus/Linux komutu.
    expect(
      screen.getByText(/“Kütüphane Defteri — Yedekten Geri Yükle” kısayolunu/),
    ).toBeInTheDocument();
    expect(screen.getByText("kutuphane-defteri --geri-yukle")).toBeInTheDocument();
  });

  it("yedek yokken günlük yedeğin “her gün ilk açılışta” alındığını söyler", async () => {
    guvenlik.yedekler.mockResolvedValue({ ...LISTE, backups: [] });
    ekranaBas();

    expect(await screen.findByText(/her gün ilk açılışta günlük\s+yedek alır/)).toBeInTheDocument();
  });

  it("yedeği parola ve onayla geri yükler, yeniden başlat olayını yayınlar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue(SONUC);
    const dinleyici = vi.fn();
    window.addEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    try {
      ekranaBas();

      await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
      await kullanici.type(screen.getByLabelText("Yönetici parolası"), PAROLA);
      await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
      // Onay metni kenara alma davranışını açıkça söyler.
      const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yüklensin mi?" });
      expect(diyalog).toHaveTextContent("db-onceki-");
      // Gövde SONUCU söyler; başlıktaki soruyu yinelemez (docs/sozluk.md §3).
      expect(diyalog).toHaveTextContent("o yedekten sonra girdiğiniz kayıtlar ekrandan kalkar");
      expect(diyalog).not.toHaveTextContent("Devam edilsin mi?");
      await kullanici.click(within(diyalog).getByRole("button", { name: "Geri yükle" }));

      await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
      const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
      expect(form.get("name")).toBe("gunluk-2026-08-31.kdbak");
      expect(form.get("file")).toBeNull();
      expect(form.get("password")).toBe(PAROLA);
      expect(form.get("recovery_key")).toBeNull();
      await waitFor(() => expect(dinleyici).toHaveBeenCalled());
    } finally {
      window.removeEventListener(YENIDEN_BASLAT_OLAYI, dinleyici);
    }
  });

  it("parola ya da kurtarma anahtarı girilmeden istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-09-01/ }));
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Yedekler şifrelidir; yönetici parolasını ya da kurtarma anahtarını girin.",
    );
    expect(guvenlik.geriYukle).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("kurtarma anahtarıyla gönderir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue({ ...SONUC, state_written: true });
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-09-01/ }));
    await kullanici.type(screen.getByLabelText("Kurtarma anahtarı"), "AAAA-BBBB");
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
    const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
    expect(form.get("name")).toBe("gunluk-2026-09-01.kdbak");
    expect(form.get("recovery_key")).toBe("AAAA-BBBB");
    expect(form.get("password")).toBeNull();
  });

  it("elden dosya yüklemesini FormData'ya koyar", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockResolvedValue(SONUC);
    ekranaBas();

    const dosya = new File([new Uint8Array([1, 2, 3])], "elden.kdbak");
    await kullanici.upload(await screen.findByLabelText(/elinizdeki yedek dosyası/), dosya);
    await kullanici.type(screen.getByLabelText("Yönetici parolası"), PAROLA);
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    await waitFor(() => expect(guvenlik.geriYukle).toHaveBeenCalledTimes(1));
    const form = guvenlik.geriYukle.mock.calls[0][0] as FormData;
    expect(form.get("name")).toBeNull();
    expect((form.get("file") as File).name).toBe("elden.kdbak");
  });

  it("onay reddedilirse istek atmaz", async () => {
    const kullanici = userEvent.setup();
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
    await kullanici.type(screen.getByLabelText("Yönetici parolası"), PAROLA);
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    const diyalog = await screen.findByRole("dialog", { name: "Yedekten geri yüklensin mi?" });
    await kullanici.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));

    expect(guvenlik.geriYukle).not.toHaveBeenCalled();
  });

  it("backend hatasını Türkçe mesajıyla gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.geriYukle.mockRejectedValue(
      new ApiError(400, "validation_error", "Yedek açılamadı: yönetici parolası hatalı."),
    );
    ekranaBas();

    await kullanici.click(await screen.findByRole("radio", { name: /gunluk-2026-08-31/ }));
    await kullanici.type(screen.getByLabelText("Yönetici parolası"), "Yanlis-Parola-9");
    await kullanici.click(screen.getByRole("button", { name: "Geri yükle" }));
    await onayla(kullanici);

    expect(await screen.findByRole("alert")).toHaveTextContent("Yedek açılamadı");
  });

  it("yedek klasörü boşken dosya yükleme yolu açık kalır", async () => {
    guvenlik.yedekler.mockResolvedValue({ backup_dir: "C:\\x", backups: [] });
    ekranaBas();

    expect(await screen.findByText(/geri yüklenebilir dosya yok/)).toBeInTheDocument();
    expect(screen.getByLabelText(/elinizdeki yedek dosyası/)).toBeInTheDocument();
  });

  it("kayıp kipinde giriş metni en yeni yedeği önerir", async () => {
    ekranaBas(true);

    expect(await screen.findByText(/En yeni yedeği seçin/)).toBeInTheDocument();
    expect(screen.queryByText(/Yanlış veri girişinden sonra/)).toBeNull();
  });

  it.each([false, true])(
    "kullanıcı metninde teknik dosya uzantısı geçmez (kayıp kipi: %s)",
    async (kayipKipi) => {
      // Sözlük: ".kdbak" kullanıcı metninde kullanılmaz; teknik adlar yalnız
      // Hakkında sayfasında. Liste boşken ekrandaki her metin kartın kendisinindir
      // (dolu listede dosya adları sunucudan gelen veridir, metin değil).
      guvenlik.yedekler.mockResolvedValue({ backup_dir: "C:\\x", backups: [] });
      const { container } = ekranaBas(kayipKipi);

      await screen.findByText(/geri yüklenebilir dosya yok/);
      expect(container.textContent).not.toMatch(/kdbak/i);
    },
  );
});
