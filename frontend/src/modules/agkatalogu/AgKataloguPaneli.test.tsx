// Ayarlar → Ağ Kataloğu (tasarım §5.2, §5.6).
//
// Sabitlenenler:
//   1) ilk açılışta adım adım yönlendirme; afiş basıldıktan sonra gizlenir;
//   2) kaydetme KISMİDİR ve port/aç-kapa/afiş adresi gövdeye GİRMEZ;
//   3) port ayrı diyalogdan, Windows'ta UAC uyarısıyla değişir; aralık dışı
//      değer sunucuya gitmez;
//   4) "yalnız seçili IP" kipinde adres masaüstündeki adaylardan seçilir;
//   5) aç/kapa denetçiye gider; sunucunun alan hatası alanda gösterilir.

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
  katalogVerisi,
  ORNEK_IP,
  ORNEK_IP_2,
} from "../../test/agKataloguVerileri";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const kapi = vi.hoisted(() => ({
  durum: vi.fn(),
  ayar: vi.fn(),
  ayarKaydet: vi.fn(),
  eylem: vi.fn(),
  arayuzler: vi.fn(),
  portDegistir: vi.fn(),
  bilgiNotu: vi.fn(),
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

import AgKataloguPaneli, { bloklariAyir } from "./AgKataloguPaneli";

function ekranaBas() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <AgKataloguPaneli />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.ayar.mockResolvedValue(ayarVerisi());
  kapi.durum.mockResolvedValue(durumVerisi());
  kapi.arayuzler.mockResolvedValue(adaylarVerisi());
  kapi.ayarKaydet.mockImplementation((govde: object) => Promise.resolve(ayarVerisi(govde)));
  kapi.bilgiNotu.mockResolvedValue(new Blob(["%PDF"]));
});

describe("Ağ Kataloğu — ilk açılış", () => {
  it("katalog kapalı ve afiş hiç basılmamışken adımlar sırayla gösterilir", async () => {
    ekranaBas();

    const kart = (
      await screen.findByRole("heading", { name: "Ağ Kataloğunu Açmadan Önce" })
    ).closest("div.space-y-4") as HTMLElement;
    const adimlar = within(kart).getAllByRole("listitem");
    expect(adimlar.map((a) => a.querySelector("p")?.textContent)).toEqual([
      "BTR'yle görüşün",
      "Güvenlik duvarını hazırlayın",
      "Adresi seçin (tamam)",
      "Ağ Kataloğunu açın",
      "Afişi basın, yer imlerini dağıtın",
    ]);
    expect(
      within(kart).getByText(/bilişim teknolojileri rehber öğretmeniyle \(BTR\)/),
    ).toBeInTheDocument();
    // Aç düğmesi yalnız adımların içinde durur (ikinci bir kopya yok).
    expect(screen.getAllByRole("button", { name: "Ağ Kataloğunu aç" })).toHaveLength(1);
  });

  it("güvenlik duvarı denetimi geçtiyse adım tamam görünür", async () => {
    kapi.durum.mockResolvedValue(
      durumVerisi({
        katalog: katalogVerisi({ guvenlik_duvari: duvarVerisi({ dinlemeye_izin: true }) }),
      }),
    );
    ekranaBas();

    expect(await screen.findByText("Güvenlik duvarını hazırlayın")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Güvenlik duvarını hazırlayın").textContent).toContain("(tamam)"),
    );
  });

  it("Pardus'ta güvenlik duvarı adımı komutu verir", async () => {
    kapi.durum.mockResolvedValue(
      durumVerisi({
        platform: "linux",
        katalog: katalogVerisi({
          guvenlik_duvari: duvarVerisi({
            platform: "linux",
            maddeler: [],
            kural: null,
            linux: {
              arac: "ufw",
              etkin: false,
              komut: "sudo ufw allow from 10.20.30.0/24 to any app 'Kutuphane Defteri'",
            },
          }),
        }),
      }),
    );
    ekranaBas();

    expect(await screen.findByLabelText("Güvenlik duvarı komutu")).toHaveTextContent(
      "sudo ufw allow from 10.20.30.0/24 to any app 'Kutuphane Defteri'",
    );
  });

  it("adımdaki bilgi notu düğmesi PDF'i indirir", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Hizmeti Bilgi Notu'nu bas" }));

    await waitFor(() => expect(indirme.saveBlob).toHaveBeenCalled());
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(/^Ağ-Hizmeti-Bilgi-Notu_/);
  });

  it("afiş basılmışsa adımlar gizlenir, aç düğmesi durum kartında durur", async () => {
    kapi.ayar.mockResolvedValue(ayarVerisi({ son_afis_ip: ORNEK_IP }));
    ekranaBas();

    expect(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" })).toBeInTheDocument();
    expect(screen.queryByText("Ağ Kataloğunu Açmadan Önce")).not.toBeInTheDocument();
    // Kart gizliyken BTR açılımı sekmenin açıklamasındadır (sözlük §2: ilk geçişte açılır).
    expect(
      screen.getByText(/bilişim teknolojileri rehber öğretmeniyle \(BTR\) birlikte/),
    ).toBeInTheDocument();
  });

  it("katalog açıldıktan sonra kart afiş basılana dek kalır: 4. adım tamam, 5. adım görünür", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(await screen.findByText("Ağ Kataloğu açıldı.")).toBeInTheDocument();
    const kart = screen
      .getByRole("heading", { name: "Ağ Kataloğunu Açmadan Önce" })
      .closest("div.space-y-4") as HTMLElement;
    expect(within(kart).getByText("Ağ Kataloğunu açın").textContent).toContain("(tamam)");
    expect(within(kart).getByText("Afişi basın, yer imlerini dağıtın")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ağ Kataloğunu aç" })).not.toBeInTheDocument();
    // Açık hâlde kapatma durum kartındadır.
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu kapat" })).toBeInTheDocument();
  });

  it("açılamadıysa kart kalır; 2. adımın yönlendirmesi ve kapatma yolu durur", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(
      durumVerisi({
        katalog: katalogVerisi({ durum: "engellendi", ayar_acik: true, son_hata: "Kural yok." }),
      }),
    );
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(await screen.findAllByText("Kural yok.")).not.toHaveLength(0);
    expect(screen.getByText("Güvenlik duvarını hazırlayın")).toBeInTheDocument();
    expect(screen.getByText(/Ağ Kataloğu açılamadı; nedeni aşağıdaki/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu kapat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden başlat" })).toBeInTheDocument();
  });
});

describe("Ağ Kataloğu — aç/kapa", () => {
  it("açar ve bildirir; açılamazsa gerekçeyi verir", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(kapi.eylem).toHaveBeenCalledWith("ac");
    expect(await screen.findByText("Ağ Kataloğu açıldı.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: `http://${ORNEK_IP}:8765/` })).toHaveAttribute(
      "target",
      "_blank",
    );
  });

  it("açık katalog kapatılır", async () => {
    const user = userEvent.setup();
    kapi.ayar.mockResolvedValue(ayarVerisi({ acik: true, son_afis_ip: ORNEK_IP }));
    kapi.durum.mockResolvedValue(durumVerisi({ katalog: acikKatalog() }));
    kapi.eylem.mockResolvedValue(durumVerisi());
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu kapat" }));

    expect(kapi.eylem).toHaveBeenCalledWith("kapat");
    expect(await screen.findByText("Ağ Kataloğu kapatıldı.")).toBeInTheDocument();
  });

  it("açma başarısızsa iletiyi gösterir", async () => {
    const user = userEvent.setup();
    kapi.eylem.mockResolvedValue(
      durumVerisi({ katalog: katalogVerisi({ durum: "engellendi", son_hata: "Kural yok." }) }),
    );
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" }));

    expect(await screen.findAllByText("Kural yok.")).not.toHaveLength(0);
  });

  it("ayar açık ama güvenlik duvarı izni yoksa ayar kapatılabilir ve yeniden denenir", async () => {
    const user = userEvent.setup();
    kapi.ayar.mockResolvedValue(ayarVerisi({ acik: true, son_afis_ip: ORNEK_IP }));
    kapi.durum.mockResolvedValue(
      durumVerisi({
        katalog: katalogVerisi({ durum: "engellendi", ayar_acik: true, son_hata: "Kural yok." }),
      }),
    );
    kapi.eylem.mockImplementation((eylem: string) =>
      Promise.resolve(
        eylem === "yeniden_baslat" ? durumVerisi({ katalog: acikKatalog() }) : durumVerisi(),
      ),
    );
    ekranaBas();

    expect(screen.queryByRole("button", { name: "Ağ Kataloğunu aç" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Yeniden başlat" }));
    expect(kapi.eylem).toHaveBeenCalledWith("yeniden_baslat");
    expect(await screen.findByText("Ağ Kataloğu açıldı.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Ağ Kataloğunu kapat" }));
    expect(kapi.eylem).toHaveBeenCalledWith("kapat");
    // Ayar kapandı: durum kartı yeniden "aç" sunar (bildirim kuyruğu önceki iletiyi gösteriyor).
    expect(await screen.findByRole("button", { name: "Ağ Kataloğunu aç" })).toBeInTheDocument();
  });

  it("masaüstü dışında aç düğmesi kapalıdır ve bilgi bandı çıkar", async () => {
    kapi.durum.mockResolvedValue(durumVerisi({ masaustu: false, katalog: null }));
    ekranaBas();

    expect(await screen.findByText(/masaüstü penceresi dışında çalışıyor/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ağ Kataloğunu aç" })).toBeDisabled();
    expect(kapi.arayuzler).not.toHaveBeenCalled();
  });
});

describe("Ağ Kataloğu — ayarlar", () => {
  it("kaydetme kısmidir: port, aç/kapa ve afiş adresi gönderilmez; bloklar satırlara ayrılır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    const bloklar = await screen.findByLabelText("Tahta ağı blokları");

    await user.type(bloklar, "10.60.0.0/22{enter}10.61.0.0/24");
    await user.click(screen.getByLabelText("Konu dizini gösterilir"));
    await user.type(screen.getByLabelText("Kütüphane saatleri"), "Hafta içi 08.30-16.30");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.ayarKaydet).toHaveBeenCalled());
    const govde = kapi.ayarKaydet.mock.calls[0][0] as Record<string, unknown>;
    expect(govde).toEqual({
      dinleme_kipi: "ALL",
      secili_ip: "",
      tahta_cidrleri: ["10.60.0.0/22", "10.61.0.0/24"],
      vitrin_acik: true,
      konular_acik: false,
      uyku_engelleme: true,
      kutuphane_saatleri: "Hafta içi 08.30-16.30",
    });
    expect(await screen.findByText("Ağ Kataloğu ayarları kaydedildi.")).toBeInTheDocument();
  });

  it("yalnız seçili IP kipinde adres adaylardan seçilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByLabelText("Tahta ağı blokları");
    await waitFor(() => expect(kapi.arayuzler).toHaveBeenCalled());

    await user.click(screen.getByLabelText("Yalnız seçili IP adresinde"));
    await user.selectOptions(await screen.findByLabelText("IP adresi"), ORNEK_IP_2);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.ayarKaydet).toHaveBeenCalled());
    expect(kapi.ayarKaydet.mock.calls[0][0]).toMatchObject({
      dinleme_kipi: "SELECTED",
      secili_ip: ORNEK_IP_2,
    });
  });

  it("kayıtlı adres bu bilgisayarda yoksa listede işaretlenir", async () => {
    kapi.ayar.mockResolvedValue(ayarVerisi({ dinleme_kipi: "SELECTED", secili_ip: "10.1.1.1" }));
    ekranaBas();

    expect(
      await screen.findByRole("option", { name: "10.1.1.1 (bu bilgisayarda şu an yok)" }),
    ).toBeInTheDocument();
  });

  it("sunucunun alan hatası alanda gösterilir", async () => {
    const user = userEvent.setup();
    kapi.ayarKaydet.mockRejectedValue(
      new ApiError(400, "validation_error", "Hatalı.", {
        tahta_cidrleri: ["“10.0.0.0/8” çok geniş."],
      }),
    );
    ekranaBas();
    await screen.findByLabelText("Tahta ağı blokları");

    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("“10.0.0.0/8” çok geniş.")).toBeInTheDocument();
  });

  it("ayarlar yüklenemezse hata bandı çıkar", async () => {
    kapi.ayar.mockRejectedValue(
      new ApiError(403, "kip_yetkisiz", "Bu işlem görevli kipinde yapılamaz."),
    );
    ekranaBas();

    expect(await screen.findByText("Bu işlem görevli kipinde yapılamaz.")).toBeInTheDocument();
  });
});

describe("Ağ Kataloğu — port", () => {
  it("Windows'ta UAC uyarısıyla değişir; aralık dışı değer sunucuya gitmez", async () => {
    const user = userEvent.setup();
    kapi.portDegistir.mockResolvedValue({
      tamam: true,
      ileti: "Port değiştirildi; güvenlik duvarı kuralı da güncellendi.",
      durum: durumVerisi(),
    });
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Portu değiştir" }));
    const diyalog = await screen.findByRole("dialog", { name: "Portu değiştir" });
    expect(within(diyalog).getByText(/Windows yönetici onayı \(UAC\)/)).toBeInTheDocument();

    const alan = within(diyalog).getByLabelText(/Yeni port/);
    await user.clear(alan);
    await user.type(alan, "80");
    await user.click(within(diyalog).getByRole("button", { name: "Portu değiştir" }));
    expect(await within(diyalog).findByText(/1024 ile 65535 arasında/)).toBeInTheDocument();
    expect(kapi.portDegistir).not.toHaveBeenCalled();

    await user.clear(alan);
    await user.type(alan, "9100");
    await user.click(within(diyalog).getByRole("button", { name: "Portu değiştir" }));

    await waitFor(() => expect(kapi.portDegistir).toHaveBeenCalledWith(9100));
    expect(
      await screen.findByText("Port değiştirildi; güvenlik duvarı kuralı da güncellendi."),
    ).toBeInTheDocument();
    expect(await screen.findByText("9100")).toBeInTheDocument();
  });

  it("UAC reddedilirse port değişmez ve ileti diyalogda kalır", async () => {
    const user = userEvent.setup();
    kapi.portDegistir.mockRejectedValue(
      new ApiError(409, "kural_yazilamadi", "Yönetici izni verilmedi. Port değiştirilmedi."),
    );
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Portu değiştir" }));
    const diyalog = await screen.findByRole("dialog", { name: "Portu değiştir" });
    const alan = within(diyalog).getByLabelText(/Yeni port/);
    await user.clear(alan);
    await user.type(alan, "9200");
    await user.click(within(diyalog).getByRole("button", { name: "Portu değiştir" }));

    expect(
      await within(diyalog).findByText("Yönetici izni verilmedi. Port değiştirilmedi."),
    ).toBeInTheDocument();
    expect(screen.getByText("8765")).toBeInTheDocument();
  });

  it("Pardus'ta UAC uyarısı yerine komut bilgisi verilir", async () => {
    const user = userEvent.setup();
    kapi.durum.mockResolvedValue(durumVerisi({ platform: "linux" }));
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: "Portu değiştir" }));

    const diyalog = await screen.findByRole("dialog", { name: "Portu değiştir" });
    // Diyalog ayrı bir yüzeydir: BTR ilk geçişte açılır (sözlük §2).
    expect(
      within(diyalog).getByText(
        /Pardus'ta güvenlik duvarı kuralını okulun bilişim teknolojileri rehber öğretmeni \(BTR\)/,
      ),
    ).toBeInTheDocument();
  });
});

describe("bloklariAyir", () => {
  it("satır ve virgülle ayrılmış blokları temizler", () => {
    expect(bloklariAyir(" 10.1.0.0/24 ,\n\n10.2.0.0/24\n")).toEqual(["10.1.0.0/24", "10.2.0.0/24"]);
    expect(bloklariAyir("")).toEqual([]);
  });
});
