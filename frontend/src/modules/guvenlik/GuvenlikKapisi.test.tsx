// Güvenlik kapısı testi: kilitliyken içerik GÖRÜNMEZ, kilit açılınca görünür;
// güvenlik dosyası kayıpken kilit ekranı yerine AYRI "Güvenlik dosyası
// bulunamadı" ekranı ve çıkış yolları (dosyayı geri koy + yeniden denetle,
// yedekten geri yükle) gösterilir; durum ucu hata verirse kapı FAIL-OPEN
// davranır (gerçek kapı backend'dedir).

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const guvenlik = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kilitle: vi.fn(),
  kurtar: vi.fn(),
  parolaDegistir: vi.fn(),
  sifirla: vi.fn(),
}));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
// Geri yükleme kartının kendi davranışı YedektenGeriYukleme.test.tsx'tedir.
vi.mock("./YedektenGeriYukleme", () => ({
  default: ({ kayipKipi }: { kayipKipi?: boolean }) => (
    <p>{kayipKipi ? "geri yükleme kartı (kayıp kipi)" : "geri yükleme kartı"}</p>
  ),
}));

import { ApiError } from "../../lib/api";
import { kilitKapisiYayinla } from "../../lib/kilit";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import GuvenlikKapisi, { kilitOlayiYayinla } from "./GuvenlikKapisi";

const ACIK = {
  password_set: true,
  locked: false,
  security_file_missing: false,
  transition_pending: false,
  transition: "",
  protected_fields: ["ad"],
};
const KILITLI = { ...ACIK, locked: true };
const KAYIP = { ...ACIK, locked: true, security_file_missing: true, reset_available: false };
/** Kişi kaydı hiç girilmemiş kurulumda bozuk dosya: sıfırlama yolu açık. */
const SIFIRLANABILIR = { ...KAYIP, reset_available: true };
const KURULUMA_DONDU = { ...ACIK, password_set: false, locked: false };

function icerikliKapi() {
  return render(
    <ConfirmProvider>
      <GuvenlikKapisi>
        <p>Gizli içerik</p>
      </GuvenlikKapisi>
    </ConfirmProvider>,
  );
}

describe("GuvenlikKapisi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("kilitliyken içerik yerine kilit ekranını gösterir", async () => {
    guvenlik.durum.mockResolvedValue(KILITLI);
    icerikliKapi();
    expect(await screen.findByText("Kayıtlar kilitli")).toBeInTheDocument();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
  });

  it("kilit açılınca içeriği gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(KILITLI);
    guvenlik.ac.mockResolvedValue(ACIK);
    icerikliKapi();

    await kullanici.type(await screen.findByLabelText(/Yönetici parolası/), "Deneme-Parola-1");
    await kullanici.click(screen.getByRole("button", { name: "Aç" }));

    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("parola kurulu değilse doğrudan içeriği gösterir", async () => {
    guvenlik.durum.mockResolvedValue({ ...ACIK, password_set: false });
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("durum ucu hata verirse fail-open davranır", async () => {
    guvenlik.durum.mockRejectedValue(new Error("bağlantı yok"));
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("kilitle olayında içeriği gizler", async () => {
    guvenlik.durum.mockResolvedValue(ACIK);
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();

    act(() => kilitOlayiYayinla());
    await waitFor(() => expect(screen.queryByText("Gizli içerik")).toBeNull());
    expect(screen.getByText("Kayıtlar kilitli")).toBeInTheDocument();
  });

  it("güvenlik dosyası kayıpken kilit ekranı yerine ayrı ekranı ve çıkış yollarını gösterir", async () => {
    guvenlik.durum.mockResolvedValue(KAYIP);
    icerikliKapi();

    expect(
      await screen.findByRole("heading", { name: "Güvenlik dosyası bulunamadı ya da okunamıyor" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
    // Parola sorulmaz: dosya yokken hiçbir parola kabul edilmezdi.
    expect(screen.queryByText("Kayıtlar kilitli")).toBeNull();
    expect(screen.queryByLabelText(/Yönetici parolası/)).toBeNull();
    // Ne olduğu ve ne yapılacağı anlaşılır dille söylenir.
    expect(screen.getByText(/guvenlik\.json\) veri klasöründe bulunamadı/)).toBeInTheDocument();
    expect(screen.getByText(/veri klasörüne geri koyun/)).toBeInTheDocument();
    expect(screen.getByText(/bir yedeği geri yükleyin/)).toBeInTheDocument();
    expect(screen.getByText("geri yükleme kartı (kayıp kipi)")).toBeInTheDocument();
    // İç kodlar kullanıcı metnine girmez.
    expect(screen.queryByText(/GA-2|guvenlik_dosyasi_kayip/)).toBeNull();
  });

  it("sıfırlama yolu koşul sağlanmadıkça görünmez", async () => {
    guvenlik.durum.mockResolvedValue(KAYIP);
    icerikliKapi();
    await screen.findByRole("heading", { name: "Güvenlik dosyası bulunamadı ya da okunamıyor" });
    expect(
      screen.queryByRole("button", { name: "Güvenlik dosyasını sıfırla ve kuruluma dön" }),
    ).toBeNull();
  });

  it("korunan veri yokken sıfırlama onayla çalışır ve kuruluma döner", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValueOnce(SIFIRLANABILIR).mockResolvedValueOnce(KURULUMA_DONDU);
    guvenlik.sifirla.mockResolvedValue({ ...KURULUMA_DONDU, archived_as: "guvenlik-arsiv-x.json" });
    icerikliKapi();

    await kullanici.click(
      await screen.findByRole("button", { name: "Güvenlik dosyasını sıfırla ve kuruluma dön" }),
    );
    // Onay diyaloğu: başlık soru, gövde sonuç (sözlük §3).
    const diyalog = await screen.findByRole("dialog", { name: "Güvenlik dosyası sıfırlansın mı?" });
    expect(diyalog).toHaveTextContent(/arşivlenir/);
    await kullanici.click(screen.getByRole("button", { name: "Sıfırla ve kuruluma dön" }));

    await waitFor(() => expect(guvenlik.sifirla).toHaveBeenCalledTimes(1));
    // Parola kurulmamış duruma dönüldü: içerik (içteki kurulum kapısı sihirbaza götürür).
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();
  });

  it("sıfırlamadan vazgeçilirse istek atılmaz", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(SIFIRLANABILIR);
    icerikliKapi();

    await kullanici.click(
      await screen.findByRole("button", { name: "Güvenlik dosyasını sıfırla ve kuruluma dön" }),
    );
    await kullanici.click(await screen.findByRole("button", { name: "Vazgeç" }));
    expect(guvenlik.sifirla).not.toHaveBeenCalled();
  });

  it("sıfırlama reddedilirse backend iletisini gösterir", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValue(SIFIRLANABILIR);
    guvenlik.sifirla.mockRejectedValue(
      new ApiError(409, "sifirlama_uygun_degil", "Güvenlik dosyası sıfırlanamaz.", {}),
    );
    icerikliKapi();

    await kullanici.click(
      await screen.findByRole("button", { name: "Güvenlik dosyasını sıfırla ve kuruluma dön" }),
    );
    await kullanici.click(await screen.findByRole("button", { name: "Sıfırla ve kuruluma dön" }));
    expect(await screen.findByText("Güvenlik dosyası sıfırlanamaz.")).toBeInTheDocument();
  });

  it("dosya geri konunca “Yeniden denetle” olağan kilit ekranına geçer", async () => {
    const kullanici = userEvent.setup();
    guvenlik.durum.mockResolvedValueOnce(KAYIP).mockResolvedValueOnce(KILITLI);
    icerikliKapi();

    await kullanici.click(await screen.findByRole("button", { name: "Yeniden denetle" }));

    expect(await screen.findByText("Kayıtlar kilitli")).toBeInTheDocument();
    expect(guvenlik.durum).toHaveBeenCalledTimes(2);
  });

  it("oturum ortasında 423 kilit olayında durumu yeniden okur ve kayıp ekranına geçer", async () => {
    guvenlik.durum.mockResolvedValueOnce(ACIK).mockResolvedValueOnce(KAYIP);
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();

    act(() => kilitKapisiYayinla());

    expect(
      await screen.findByRole("heading", { name: "Güvenlik dosyası bulunamadı ya da okunamıyor" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
    expect(guvenlik.durum).toHaveBeenCalledTimes(2);
  });

  it("oturum ortasında 423 kilit olayında başka yoldan kilitlenmişse kilit ekranına geçer", async () => {
    guvenlik.durum.mockResolvedValueOnce(ACIK).mockResolvedValueOnce(KILITLI);
    icerikliKapi();
    expect(await screen.findByText("Gizli içerik")).toBeInTheDocument();

    act(() => kilitKapisiYayinla());

    expect(await screen.findByText("Kayıtlar kilitli")).toBeInTheDocument();
    expect(screen.queryByText("Gizli içerik")).toBeNull();
  });
});
