// Ağ Doktoru (tasarım §5.9).
//
// Sabitlenenler:
//   1) gösterdikleri: durum, port, adres (harici tarayıcıda, LAN adresiyle), QR,
//      kişisiz sayılar, son hata, uyarılar; beş madde; ağ profili; aday adresler;
//   2) "dinleyici ayakta" sınaması UYARI METNİYLE ve başka bilgisayar için
//      Test-NetConnection komutuyla gösterilir (sınama yapılmadan da);
//   3) düğmeler: Kuralı ekle/güncelle (onaylı, UAC), Afişi bas, Yer imi
//      dosyalarını üret, PYS talep metnini kopyala, Ağ Hizmeti Bilgi Notu;
//   4) masaüstü dışında eylemler kapalıdır, belgeler açıktır;
//   5) Pardus'ta kural değil komut gösterilir.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import {
  acikKatalog,
  adaylarVerisi,
  ayarVerisi,
  duvarVerisi,
  durumVerisi,
  ORNEK_IP,
  ORNEK_IP_2,
  ORNEK_QR,
} from "../../test/agKataloguVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const kapi = vi.hoisted(() => ({
  durum: vi.fn(),
  ayar: vi.fn(),
  eylem: vi.fn(),
  guvenlikDuvari: vi.fn(),
  kuralGuncelle: vi.fn(),
  arayuzler: vi.fn(),
  dinleyiciSinamasi: vi.fn(),
  afis: vi.fn(),
  bilgiNotu: vi.fn(),
  yerImleri: vi.fn(),
  pysMetni: vi.fn(),
}));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, agKataloguApi: { ...actual.agKataloguApi, ...kapi } };
});

vi.mock("../../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import AgDoktoruPage, { DINLEYICI_UYARISI } from "./AgDoktoruPage";

function ekranaBas() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <AgDoktoruPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.durum.mockResolvedValue(durumVerisi());
  kapi.ayar.mockResolvedValue(ayarVerisi());
  kapi.arayuzler.mockResolvedValue(adaylarVerisi());
  kapi.guvenlikDuvari.mockResolvedValue(duvarVerisi());
  const blob = new Blob(["%PDF"], { type: "application/pdf" });
  kapi.afis.mockResolvedValue(blob);
  kapi.bilgiNotu.mockResolvedValue(blob);
  kapi.yerImleri.mockResolvedValue(new Blob(["PK"], { type: "application/zip" }));
  kapi.pysMetni.mockResolvedValue({ metin: "Konu: Yerel ağ VLAN düzenlemesi — tek yön, TCP/8765" });
});

describe("Ağ Doktoru — gösterdikleri", () => {
  it("başlık, BTR ilk geçişte açık adıyla ve Ayarlar bağlantısı", async () => {
    ekranaBas();

    expect(screen.getByRole("heading", { level: 1, name: "Ağ Doktoru" })).toBeInTheDocument();
    expect(
      screen.getByText(/bilişim teknolojileri rehber öğretmeniyle \(BTR\)/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayarlar → Ağ Kataloğu" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=ag-katalogu",
    );
    expect(await screen.findByText("Katalog Durumu")).toBeInTheDocument();
  });

  it("açık katalogun adresi LAN adresiyle harici tarayıcıda açılır; QR ve sayılar görünür", async () => {
    kapi.durum.mockResolvedValue(
      durumVerisi({
        katalog: acikKatalog({ uyarilar: ["Bu bilgisayarın IP adresi değişti."] }),
        qr: ORNEK_QR,
      }),
    );
    ekranaBas();

    const baglanti = await screen.findByRole("link", { name: `http://${ORNEK_IP}:8765/` });
    expect(baglanti).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("img", { name: "Katalog adresinin QR kodu" })).toBeInTheDocument();
    expect(
      screen.getByText(/12 gösterilen sayfa · 5 arama · 0 sınıra takılan istek/),
    ).toBeInTheDocument();
    expect(screen.getByText("Bu bilgisayarın IP adresi değişti.")).toBeInTheDocument();
    expect(screen.getByText("Açık")).toBeInTheDocument();
    expect(screen.getByText("Bütün ağ bağlantıları")).toBeInTheDocument();
  });

  it("son hata gösterilir", async () => {
    kapi.durum.mockResolvedValue(
      durumVerisi({
        katalog: acikKatalog({
          durum: "engellendi",
          adres: null,
          son_hata: "Güvenlik duvarı denetimi geçmedi.",
        }),
      }),
    );
    ekranaBas();

    const bant = await screen.findByText("Güvenlik duvarı denetimi geçmedi.");
    expect(
      within(bant.closest("[role=alert]") as HTMLElement).getByText("Son hata"),
    ).toBeInTheDocument();
  });

  it("aday adresler ve etkin arayüzler, profil ve uyarılarla listelenir", async () => {
    ekranaBas();

    expect(await screen.findByText(`${ORNEK_IP}/24`)).toBeInTheDocument();
    expect(screen.getByText(`${ORNEK_IP_2}/24`)).toBeInTheDocument();
    expect(screen.getByText("Varsayılan bağlantı")).toBeInTheDocument();
    expect(screen.getByText("IP yönlendirme açık")).toBeInTheDocument();
    expect(
      screen.getByText("Ağ Kataloğu bu ağda da erişilebilir: Ethernet 2."),
    ).toBeInTheDocument();
  });

  it("beş madde açılışta okunur; kural değerleri ve ağ profili gösterilir", async () => {
    ekranaBas();

    const liste = await screen.findByRole("list", { name: "Güvenlik duvarı denetimi" });
    expect(within(liste).getAllByRole("listitem")).toHaveLength(5);
    expect(within(liste).getByText("Kural var ve etkin: Geçti")).toBeInTheDocument();
    expect(
      within(liste).getByText("Kuraldaki port ayardaki portla aynı: Geçmedi"),
    ).toBeInTheDocument();
    expect(within(liste).getByText("Kural bu ağ profilini kapsıyor: Uyarı")).toBeInTheDocument();
    expect(screen.getByText("Yerel alt ağ, 10.60.0.0/22")).toBeInTheDocument();
    expect(screen.getByText("Ağ profili: Genel")).toBeInTheDocument();
    // Kuralın profili de Türkçe (sözlük §4.9: Public/Private/Domain yazılmaz).
    expect(screen.getByText("Etki alanı, Özel, Genel")).toBeInTheDocument();
    expect(screen.queryByText(/Domain|Private|Public/)).not.toBeInTheDocument();
  });

  it("programın bütün izin kuralları listelenir; geniş kural gizlenmez", async () => {
    const kendi = duvarVerisi().kural!;
    const genis = {
      ...kendi,
      ad: "kutuphane-defteri.exe",
      yerel_port: ["Any"],
      uzak_adres: ["Any"],
      profil: "Any",
    };
    kapi.guvenlikDuvari.mockResolvedValue(duvarVerisi({ kural: kendi, kurallar: [kendi, genis] }));
    ekranaBas();

    expect(await screen.findByText(/Bu program için 2 izin kuralı var/)).toBeInTheDocument();
    const genisKural = screen.getByLabelText("Güvenlik duvarı kuralı: kutuphane-defteri.exe");
    expect(within(genisKural).getByText("Her yer")).toBeInTheDocument();
    expect(within(genisKural).getByText("Hepsi (Etki alanı, Özel, Genel)")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Güvenlik duvarı kuralı: Kutuphane Defteri Katalog"),
    ).toHaveTextContent("Yerel alt ağ, 10.60.0.0/22");
  });

  it("tahta ağındaki bağlantı öğrenci erişimli diye işaretlenir", async () => {
    const veri = adaylarVerisi();
    kapi.arayuzler.mockResolvedValue({
      ...veri,
      arayuzler: [veri.arayuzler[0], { ...veri.arayuzler[1], tahta_agi: true }],
      uyarilar: ["Bu bilgisayar öğrenci erişimli ağda: Ethernet 2."],
    });
    ekranaBas();

    expect(await screen.findByText(/Tahta ağı \(öğrenci erişimli\)/)).toBeInTheDocument();
    expect(
      screen.getByText("Bu bilgisayar öğrenci erişimli ağda: Ethernet 2."),
    ).toBeInTheDocument();
  });

  it("dinleyici sınaması uyarı metni ve başka bilgisayar komutu sınamadan önce de görünür", async () => {
    ekranaBas();

    expect(await screen.findByText(DINLEYICI_UYARISI)).toBeInTheDocument();
    expect(screen.getByLabelText("Başka bilgisayar için sınama komutu")).toHaveTextContent(
      `Test-NetConnection ${ORNEK_IP} -Port 8765`,
    );
  });
});

describe("Ağ Doktoru — eylemler", () => {
  it("katalogu açar ve bildirir", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(kapi.eylem).toHaveBeenCalledWith("ac");
    expect(await screen.findByText("Ağ Kataloğu açıldı.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu kapat" })).toBeInTheDocument();
  });

  it("açılamazsa gerekçe bildirilir", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(
      durumVerisi({
        katalog: acikKatalog({ durum: "engellendi", adres: null, son_hata: "Kural yok." }),
      }),
    );
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(await screen.findAllByText("Kural yok.")).not.toHaveLength(0);
  });

  it("açık katalog yeniden başlatılır", async () => {
    const user = userEvent.setup();
    kapi.durum.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    kapi.eylem.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Yeniden başlat" }));

    expect(kapi.eylem).toHaveBeenCalledWith("yeniden_baslat");
    expect(await screen.findByText("Ağ Kataloğu yeniden başlatıldı.")).toBeInTheDocument();
  });

  it("ayar açık ama katalog açılamadıysa kapatılabilir", async () => {
    const user = userEvent.setup();
    kapi.durum.mockResolvedValue(
      durumVerisi({
        katalog: acikKatalog({
          durum: "engellendi",
          adres: null,
          son_hata: "Güvenlik duvarı denetimi geçmedi.",
        }),
      }),
    );
    kapi.eylem.mockResolvedValue(durumVerisi());
    ekranaBas();

    expect(await screen.findByRole("button", { name: "Yeniden başlat" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ağ Kataloğunu aç" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ağ Kataloğunu kapat" }));

    expect(kapi.eylem).toHaveBeenCalledWith("kapat");
  });

  it("açık katalog kapatılır", async () => {
    const user = userEvent.setup();
    kapi.durum.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    kapi.eylem.mockResolvedValue(durumVerisi());
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu kapat" }));

    expect(kapi.eylem).toHaveBeenCalledWith("kapat");
    expect(await screen.findByText("Ağ Kataloğu kapatıldı.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu aç" })).toBeInTheDocument();
  });

  it("kural güncellemesi onay ister, UAC sonrası denetimi yeniden okur", async () => {
    const user = userEvent.setup();
    kapi.kuralGuncelle.mockResolvedValue({
      tamam: true,
      ileti: "Güvenlik duvarı kuralı güncellendi.",
      durum: durumVerisi(),
    });
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Kuralı ekle/güncelle" }));
    const diyalog = await screen.findByRole("dialog");
    expect(within(diyalog).getByText(/Windows yönetici onayı \(UAC\)/)).toBeInTheDocument();
    await user.click(within(diyalog).getByRole("button", { name: "Kuralı güncelle" }));

    await waitFor(() => expect(kapi.kuralGuncelle).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Güvenlik duvarı kuralı güncellendi.")).toBeInTheDocument();
    await waitFor(() => expect(kapi.guvenlikDuvari).toHaveBeenCalledTimes(2));
  });

  it("UAC reddedilirse ileti hata olarak gösterilir", async () => {
    const user = userEvent.setup();
    kapi.kuralGuncelle.mockResolvedValue({
      tamam: false,
      ileti: "Yönetici izni verilmedi; kural değiştirilmedi.",
      durum: durumVerisi(),
    });
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Kuralı ekle/güncelle" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Kuralı güncelle" }),
    );

    expect(
      await screen.findByText("Yönetici izni verilmedi; kural değiştirilmedi."),
    ).toBeInTheDocument();
    expect(kapi.guvenlikDuvari).toHaveBeenCalledTimes(1); // yalnız açılıştaki okuma
  });

  it("dinleyici sınaması sonuçları arayüz başına gösterir", async () => {
    const user = userEvent.setup();
    kapi.dinleyiciSinamasi.mockResolvedValue({
      acik: true,
      port: 8765,
      sonuclar: [
        { ip: ORNEK_IP, ad: "Ethernet", ayakta: true, komut: "x" },
        { ip: ORNEK_IP_2, ad: "Ethernet 2", ayakta: false, komut: "y" },
      ],
      uyari: "…",
    });
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Dinleyiciyi sına" }));

    expect(
      await screen.findByText(`Ethernet (${ORNEK_IP}): dinleyici bu arayüzde ayakta`),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`Ethernet 2 (${ORNEK_IP_2}): dinleyici bu arayüzde yanıt vermedi`),
    ).toBeInTheDocument();
  });

  it("sunucu hatası bildirilir", async () => {
    const user = userEvent.setup();
    kapi.dinleyiciSinamasi.mockRejectedValue(new ApiError(503, "masaustu_yok", "Masaüstü yok."));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Dinleyiciyi sına" }));

    expect(await screen.findByText("Masaüstü yok.")).toBeInTheDocument();
  });
});

describe("Ağ Doktoru — belgeler", () => {
  it("afiş, yer imleri ve bilgi notu indirilir; afiş seçili adresle basılır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText(`${ORNEK_IP}/24`);

    await user.click(screen.getByRole("button", { name: "Afişi bas" }));
    await waitFor(() => expect(kapi.afis).toHaveBeenCalledWith(undefined));
    expect(indirme.saveBlob).toHaveBeenLastCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Katalog-Afişi_.*\.pdf$/),
    );

    await user.selectOptions(screen.getByLabelText("Belgelerde kullanılacak adres"), ORNEK_IP_2);
    await user.click(screen.getByRole("button", { name: "Afişi bas" }));
    await waitFor(() => expect(kapi.afis).toHaveBeenLastCalledWith(ORNEK_IP_2));

    await user.click(screen.getByRole("button", { name: "Yer imi dosyalarını üret" }));
    await waitFor(() => expect(kapi.yerImleri).toHaveBeenCalledWith(ORNEK_IP_2));
    expect(indirme.saveBlob).toHaveBeenLastCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Yer-İmi-Dosyaları_.*\.zip$/),
    );

    await user.click(screen.getByRole("button", { name: "Ağ Hizmeti Bilgi Notu'nu bas" }));
    await waitFor(() => expect(kapi.bilgiNotu).toHaveBeenCalledWith(ORNEK_IP_2));
    expect(indirme.saveBlob).toHaveBeenLastCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Ağ-Hizmeti-Bilgi-Notu_.*\.pdf$/),
    );
  });

  it("PYS talep metni panoya kopyalanır", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "PYS talep metnini kopyala" }));

    await expect(navigator.clipboard.readText()).resolves.toBe(
      "Konu: Yerel ağ VLAN düzenlemesi — tek yön, TCP/8765",
    );
    expect(await screen.findByText("PYS talep metni panoya kopyalandı.")).toBeInTheDocument();
  });

  it("belge üretilemezse sunucunun iletisi gösterilir", async () => {
    const user = userEvent.setup();
    kapi.afis.mockRejectedValue(new ApiError(409, "adres_yok", "Adres belirlenemedi."));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Afişi bas" }));

    expect(await screen.findByText("Adres belirlenemedi.")).toBeInTheDocument();
    expect(indirme.saveBlob).not.toHaveBeenCalled();
  });
});

describe("Ağ Doktoru — masaüstü dışında ve Pardus", () => {
  it("masaüstü dışında eylemler kapalı, belgeler açıktır; adres elle yazılır", async () => {
    const user = userEvent.setup();
    kapi.durum.mockResolvedValue(durumVerisi({ masaustu: false, katalog: null }));
    ekranaBas();

    expect(await screen.findByText(/masaüstü penceresi dışında çalışıyor/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu aç" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Kuralı ekle/güncelle" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Dinleyiciyi sına" })).toBeDisabled();
    expect(kapi.arayuzler).not.toHaveBeenCalled();
    expect(kapi.guvenlikDuvari).not.toHaveBeenCalled();
    // Katalog kapalıyken port ayardan gelir.
    expect(await screen.findByLabelText("Başka bilgisayar için sınama komutu")).toHaveTextContent(
      "-Port 8765",
    );

    await user.type(screen.getByLabelText("Belgelerde kullanılacak adres"), "10.5.5.5");
    await user.click(screen.getByRole("button", { name: "Afişi bas" }));
    await waitFor(() => expect(kapi.afis).toHaveBeenCalledWith("10.5.5.5"));
  });

  it("Pardus'ta kural değil BTR'nin çalıştıracağı komut gösterilir", async () => {
    kapi.durum.mockResolvedValue(
      durumVerisi({
        platform: "linux",
        katalog: acikKatalog({
          guvenlik_duvari: duvarVerisi({
            platform: "linux",
            maddeler: [],
            kural: null,
            linux: {
              arac: "ufw",
              etkin: true,
              komut: "sudo ufw allow from 10.20.30.0/24 to any app 'Kutuphane Defteri'",
            },
          }),
        }),
      }),
    );
    kapi.guvenlikDuvari.mockResolvedValue(
      duvarVerisi({
        platform: "linux",
        maddeler: [],
        kural: null,
        linux: {
          arac: "ufw",
          etkin: true,
          komut: "sudo ufw allow from 10.20.30.0/24 to any app 'Kutuphane Defteri'",
        },
      }),
    );
    ekranaBas();

    expect(await screen.findByLabelText("Güvenlik duvarı komutu")).toHaveTextContent(
      "sudo ufw allow from 10.20.30.0/24 to any app 'Kutuphane Defteri'",
    );
    expect(screen.getByText(/ufw \(\s*etkin\s*\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kuralı ekle/güncelle" })).not.toBeInTheDocument();
  });

  it("durum okunamazsa hata bandı çıkar", async () => {
    kapi.durum.mockRejectedValue(new ApiError(500, "x", "Sunucu hatası."));
    ekranaBas();

    expect(await screen.findByText("Sunucu hatası.")).toBeInTheDocument();
  });
});
