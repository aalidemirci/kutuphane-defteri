// Ayıklama (F8; Md. 12/1, E7, D15): teklif listesi · yeni teklif · teklif ayrıntısı (adım
// rayı, kalemler, belgeler) · kalem ekle (gerekçe seçilince TMY yolu kendiliğinden, devirde
// devralacak kurum, 12/1-ç'de ölçüt, engelli nüshalar kitap kitap) · komisyona sun · karar
// bağla (ayıklanmayan kalem gerekçeli) · harcama yetkilisinin onayı · uygula (ikinci
// doğrulama kutusu) · geri çek · iptal. Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { komisyonKarari } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  belgeler,
  devirKalemi,
  kalem,
  kurallar,
  sayfa,
  teklif,
  teklifSatiri,
} from "./testVerileri";

const ayiklama = vi.hoisted(() => ({
  kurallar: vi.fn(),
  adaylar: vi.fn(),
  teklifler: vi.fn(),
  teklif: vi.fn(),
  teklifAc: vi.fn(),
  teklifSil: vi.fn(),
  kalemEkle: vi.fn(),
  kalemGuncelle: vi.fn(),
  kalemCikar: vi.fn(),
  sun: vi.fn(),
  geriCek: vi.fn(),
  kararBagla: vi.fn(),
  onayla: vi.fn(),
  uygula: vi.fn(),
  iptalEt: vi.fn(),
  belgeler: vi.fn(),
  belge: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ayiklamaApi: { ...actual.ayiklamaApi, ...ayiklama } };
});
const kutuphane = vi.hoisted(() => ({ listCommissionDecisions: vi.fn() }));
vi.mock("../kutuphane/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kutuphane/api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kutuphane } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import AyiklamaPage from "./AyiklamaPage";
import { HASAR_ONERILERI_BASLIGI, KAYIP_ONERILERI_BASLIGI } from "./TeklifDiyaloglari";

function ciz(yol = "/katalog/ayiklama") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <AyiklamaPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

async function onayla(user: ReturnType<typeof userEvent.setup>, dugme: string) {
  const pencere = await screen.findByRole("dialog");
  await user.click(within(pencere).getByRole("button", { name: dugme }));
}

beforeEach(() => {
  vi.resetAllMocks();
  ayiklama.kurallar.mockResolvedValue(kurallar());
  ayiklama.teklifler.mockResolvedValue(sayfa([teklifSatiri()]));
  ayiklama.teklif.mockResolvedValue(teklif());
  ayiklama.belgeler.mockResolvedValue(belgeler());
  ayiklama.belge.mockResolvedValue(new Blob(["%PDF"]));
  ayiklama.adaylar.mockResolvedValue({
    ...sayfa([
      {
        id: 301,
        barcode: "2026000301",
        barcode_display: "2026-000301",
        work: 30,
        work_title: "Yıpranmış Aday",
        work_authors: "Deneme Yazar",
        call_number: "",
        section_name: null,
        status: "AVAILABLE",
        status_display: "Rafta",
      },
    ]),
    lost_proposals: [
      {
        id: 302,
        barcode: "2026000302",
        barcode_display: "2026-000302",
        work: 31,
        work_title: "Kayıp Nüsha",
        work_authors: "",
        call_number: "",
        section_name: null,
        status: "LOST",
        status_display: "Kayıp",
        blocker: "Kayıp nüsha ayıklamaya konmaz; kaydı sayımda kapanır.",
      },
    ],
    damage_proposals: [
      {
        id: 303,
        barcode: "2026000303",
        barcode_display: "2026-000303",
        work: 32,
        work_title: "Hasarlı Nüsha",
        work_authors: "",
        call_number: "",
        section_name: null,
        status: "ON_LOAN",
        status_display: "Ödünçte",
        blocker:
          "Hasar dosyasında kayıttan düşme önerilen nüsha ayıklamaya konmaz (Md. 12/1 " +
          "gerekçelerinden değildir); sayımda kayıttan düşülür.",
      },
    ],
  });
  kutuphane.listCommissionDecisions.mockResolvedValue(
    sayfa([
      komisyonKarari({
        id: 9,
        decision_type: "WEEDING",
        decision_type_display: "Ayıklama",
        decision_no: "2027/5",
      }),
    ]),
  );
});

describe("AyiklamaPage — liste", () => {
  it("başlık, yan bağlantılar ve teklif satırı", async () => {
    ciz();
    expect(screen.getByRole("heading", { level: 1, name: "Ayıklama" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nadir Eserler" })).toHaveAttribute(
      "href",
      "/katalog/nadir-eserler",
    );
    expect(screen.getByRole("link", { name: "Komisyon Kararları" })).toHaveAttribute(
      "href",
      "/katalog/edinimler?tab=kararlar",
    );
    expect(
      screen.getByText(/Ayıklama komisyon kararıdır; kayıttan düşme ve devir/),
    ).toBeInTheDocument();
    expect(await screen.findByText("2026-2027")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Taslak")).toBeInTheDocument();
    expect(screen.getByText("1 · 1")).toBeInTheDocument();
  });

  it("boş liste ve durum süzgeci", async () => {
    ayiklama.teklifler.mockResolvedValue(sayfa([]));
    const user = userEvent.setup();
    ciz();
    expect(await screen.findByText("Gösterilecek ayıklama teklifi yok")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Durum"), "APPLIED");
    await waitFor(() =>
      expect(ayiklama.teklifler).toHaveBeenLastCalledWith({
        status: "APPLIED",
        limit: 25,
        offset: 0,
      }),
    );
  });

  it("yeni teklif açılır ve ayrıntısı gösterilir; satıra tıklayınca da açılır", async () => {
    ayiklama.teklifAc.mockResolvedValue(teklif());
    const user = userEvent.setup();
    ciz();
    await screen.findByText("2026-2027");
    await user.click(screen.getByRole("button", { name: "Yeni teklif" }));
    expect(ayiklama.teklifAc).toHaveBeenCalled();
    expect(await screen.findByText("Ayıklama teklifi açıldı.")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: /Ayıklama teklifi · 2026-2027/ }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tekliflere dön" }));
    await user.click(
      await screen.findByRole("button", {
        name: /2026-2027 ders yılının 01.06.2027 tarihli teklifini aç/,
      }),
    );
    expect(ayiklama.teklif).toHaveBeenLastCalledWith(3);
  });

  it("liste okunamazsa hata bandı", async () => {
    ayiklama.teklifler.mockRejectedValue(new ApiError(500, "hata", "Sunucuya ulaşılamadı."));
    ciz();
    expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeInTheDocument();
  });
});

describe("AyiklamaPage — taslak teklif", () => {
  it("adım rayı, kalemler, belgeler ve teklif listesinin basımı", async () => {
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    expect(await screen.findByRole("list", { name: "Teklif adımları" })).toBeInTheDocument();
    expect(screen.getByText("Deneme Eseri")).toBeInTheDocument();
    expect(screen.getByText("(Md. 12/1-a)")).toBeInTheDocument();
    expect(screen.getByText("Devralacak: Deneme İlkokulu")).toBeInTheDocument();
    expect(screen.getByText("Ayıklama Belgeleri")).toBeInTheDocument();
    expect(screen.getAllByText("Komisyon kararı bağlandıktan sonra basılır.")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: "Uygula" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(ayiklama.belge).toHaveBeenCalledWith(3, "teklif-listesi"));
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Ayıklama-teklif-listesi_/),
    );
  });

  it("kalem ekle: gerekçe → TMY yolu kendiliğinden, devirde kurum; seçilen ve okutulanlar", async () => {
    ayiklama.kalemEkle.mockResolvedValue({ added: [kalem(), kalem({ id: 13 })], batch: teklif() });
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(await screen.findByRole("button", { name: "Kalem ekle" }));
    const pencere = await screen.findByRole("dialog", { name: "Kalem ekle" });

    expect(await within(pencere).findByText("Yıpranmış Aday")).toBeInTheDocument();
    // 25.09.2026 kullanıcı kararı (F8 ekleri 34): öneriler aday değildir; iki bilgi kutusunda
    // gerekçesiyle yazılır, seçilemez. Öneri süzgeci ve rozeti yoktur.
    expect(within(pencere).queryByText("Kayıttan düşme önerisi")).not.toBeInTheDocument();
    expect(
      within(pencere).queryByRole("checkbox", { name: "Yalnız kayıttan düşme önerileri" }),
    ).not.toBeInTheDocument();
    expect(within(pencere).getByText(KAYIP_ONERILERI_BASLIGI)).toBeInTheDocument();
    expect(within(pencere).getByText(/Kayıp nüsha ayıklamaya konmaz/)).toBeInTheDocument();
    expect(within(pencere).getByText(HASAR_ONERILERI_BASLIGI)).toBeInTheDocument();
    expect(within(pencere).getByText(/Hasarlı Nüsha \(Ödünçte\)/)).toBeInTheDocument();
    expect(within(pencere).getByText(/sayımda kayıttan düşülür/)).toBeInTheDocument();
    expect(within(pencere).queryByRole("checkbox", { name: /Hasarlı Nüsha/ })).toBeNull();

    // Sözlük §3: seçici yer tutucusu tek biçimdir ("Seçin"); yönlendirme yardım metnindedir.
    const bosYol = within(pencere).getByLabelText(/TMY yolu/);
    expect(within(bosYol).getByRole("option", { name: "Seçin" })).toBeInTheDocument();
    expect(
      within(pencere).getByText(/Önce gerekçeyi seçin; yol gerekçeye göre/),
    ).toBeInTheDocument();
    await user.selectOptions(
      within(pencere).getByLabelText(/Ayıklama gerekçesi/),
      "LEVEL_MISMATCH",
    );
    const yol = within(pencere).getByLabelText(/TMY yolu/) as HTMLSelectElement;
    expect(yol.value).toBe("TMY_24_2");
    // Md. 12/1 devri 10/1-b için ister; düzeye uygunsuzluğun devri programın bağlamasıdır.
    expect(
      within(pencere).getByText(/\(Md\. 10\/1-b\) uygun okullara veya kurumlara devrini ister/),
    ).toBeInTheDocument();
    expect(within(pencere).getByText(/program kurumun düzeyine uygun olmayan/)).toBeInTheDocument();
    await user.selectOptions(yol, "TMY_31");
    await user.type(
      within(pencere).getByLabelText("Devralacak okul ya da kurum"),
      "Deneme Halk Kütüphanesi",
    );
    await user.click(within(pencere).getByRole("checkbox", { name: /Yıpranmış Aday/ }));
    await user.type(within(pencere).getByLabelText("Kütüphane etiketleri"), "2026-000401{enter}");
    await user.click(within(pencere).getByRole("button", { name: "Teklife ekle (2)" }));

    await waitFor(() =>
      expect(ayiklama.kalemEkle).toHaveBeenCalledWith(3, {
        reason: "LEVEL_MISMATCH",
        tmy_path: "TMY_31",
        criterion: "",
        transfer_target: "Deneme Halk Kütüphanesi",
        barcodes: ["2026-000401"],
        copies: [301],
      }),
    );
    expect(await screen.findByText("2 kalem eklendi.")).toBeInTheDocument();
  });

  it("kalem ekle: gerekçesiz ve nüshasız gönderilmez; 12/1-ç'de ölçüt; engeller kitap kitap", async () => {
    ayiklama.kalemEkle.mockRejectedValue(
      new ApiError(400, "invalid", "Eklenemedi.", {
        barcodes: [
          "2026-000401 — A: Ödünçteki nüsha ayıklamaya konamaz.",
          "2026-000402 — B: Nüsha süren başka bir ayıklama teklifinde.",
        ],
      }),
    );
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(await screen.findByRole("button", { name: "Kalem ekle" }));
    const pencere = await screen.findByRole("dialog", { name: "Kalem ekle" });
    await user.click(within(pencere).getByRole("button", { name: /Teklife ekle/ }));
    expect(within(pencere).getByText("Ayıklama gerekçesini seçin.")).toBeInTheDocument();

    await user.selectOptions(
      within(pencere).getByLabelText(/Ayıklama gerekçesi/),
      "CRITERIA_MISMATCH",
    );
    expect(within(pencere).getByLabelText(/Uyulmayan ölçüt/)).toBeInTheDocument();
    expect(
      within(pencere).getByText(/Yaş ve gelişim düzeyine uygun olmayan kaynak/),
    ).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: /Teklife ekle/ }));
    expect(within(pencere).getByText(/Aday listesinden nüsha seçin/)).toBeInTheDocument();

    await user.selectOptions(within(pencere).getByLabelText(/Uyulmayan ölçüt/), "10_4");
    await user.type(
      within(pencere).getByLabelText("Kütüphane etiketleri"),
      "2026-000401 2026-000402",
    );
    await user.click(within(pencere).getByRole("button", { name: "Teklife ekle (2)" }));
    const engeller = await within(pencere).findByRole("list", { name: "Eklenemeyen nüshalar" });
    expect(within(engeller).getAllByRole("listitem")).toHaveLength(2);
    expect(ayiklama.kalemEkle).toHaveBeenCalledWith(
      3,
      expect.objectContaining({
        reason: "CRITERIA_MISMATCH",
        criterion: "10_4",
        transfer_target: "",
      }),
    );
  });

  it("komisyona sun, kalem çıkar, taslağı sil", async () => {
    ayiklama.sun.mockResolvedValue(teklif());
    ayiklama.kalemCikar.mockResolvedValue(undefined);
    ayiklama.teklifSil.mockResolvedValue(undefined);
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");

    await user.click(await screen.findByRole("button", { name: "Komisyona sun" }));
    expect(await screen.findByText("Teklif komisyona sunulsun mu?")).toBeInTheDocument();
    await onayla(user, "Komisyona sun");
    await waitFor(() => expect(ayiklama.sun).toHaveBeenCalledWith(3));
    expect(await screen.findByText("Teklif komisyona sunuldu.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Deneme Eseri kalemini çıkar" }));
    await waitFor(() => expect(ayiklama.kalemCikar).toHaveBeenCalledWith(3, 11));

    await user.click(screen.getByRole("button", { name: "Teklifi sil" }));
    await onayla(user, "Sil");
    await waitFor(() => expect(ayiklama.teklifSil).toHaveBeenCalledWith(3));
    // Taslak silinince listeye dönülür (bildirimler sırayla gösterildiği için ileti
    // burada beklenmez).
    expect(await screen.findByRole("button", { name: "Yeni teklif" })).toBeInTheDocument();
  });

  it("taslakta kalemi düzenle", async () => {
    ayiklama.kalemGuncelle.mockResolvedValue(kalem());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(await screen.findByRole("button", { name: "Deneme Eseri kalemini düzenle" }));
    const pencere = await screen.findByRole("dialog", { name: "Kalemi düzenle" });
    await user.selectOptions(within(pencere).getByLabelText(/TMY yolu/), "TMY_28");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(ayiklama.kalemGuncelle).toHaveBeenCalledWith(3, 11, {
        reason: "WORN",
        tmy_path: "TMY_28",
        criterion: "",
        transfer_target: "",
      }),
    );
    expect(await screen.findByText("Kalem güncellendi.")).toBeInTheDocument();
  });
});

describe("AyiklamaPage — sunulmuş, kararlı, onaylı teklif", () => {
  it("komisyon kararını bağla: ayıklanmayan kalemin gerekçesi zorunlu", async () => {
    ayiklama.teklif.mockResolvedValue(
      teklif({ status: "SUBMITTED", status_display: "Komisyona sunuldu" }),
    );
    ayiklama.kararBagla.mockResolvedValue(teklif());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(await screen.findByRole("button", { name: "Komisyon kararını bağla" }));
    const pencere = await screen.findByRole("dialog", { name: "Komisyon kararını bağla" });
    await within(pencere).findByRole("option", { name: /Ayıklama — .* · 2027\/5/ });
    await user.click(within(pencere).getByRole("button", { name: "Kararı bağla" }));
    expect(within(pencere).getByText("Komisyon kararı seçilmelidir.")).toBeInTheDocument();

    await user.selectOptions(within(pencere).getByLabelText(/Komisyon kararı/), "9");
    const kutular = within(pencere).getAllByRole("checkbox", {
      name: "Komisyon ayıklanmasına karar vermedi",
    });
    await user.click(kutular[0]);
    await user.click(within(pencere).getByRole("button", { name: "Kararı bağla" }));
    expect(
      within(pencere).getByText("Ayıklanmayan her kalemin gerekçesi yazılmalıdır."),
    ).toBeInTheDocument();
    await user.type(within(pencere).getByLabelText("Gerekçe"), "Hâlâ kullanılıyor.");
    await user.click(within(pencere).getByRole("button", { name: "Kararı bağla" }));
    await waitFor(() =>
      expect(ayiklama.kararBagla).toHaveBeenCalledWith(3, 9, { "11": "Hâlâ kullanılıyor." }),
    );
    expect(await screen.findByText("Komisyon kararı bağlandı.")).toBeInTheDocument();
  });

  it("geri çekme onay ister; sunulmuş teklifte devralacak kurum düzenlenir", async () => {
    ayiklama.teklif.mockResolvedValue(
      teklif({ status: "SUBMITTED", status_display: "Komisyona sunuldu" }),
    );
    ayiklama.geriCek.mockResolvedValue(teklif());
    ayiklama.kalemGuncelle.mockResolvedValue(devirKalemi());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");

    await user.click(
      await screen.findByRole("button", { name: "Düzeye Uygun Olmayan Eser kalemini düzenle" }),
    );
    const pencere = await screen.findByRole("dialog", { name: "Devralacak kurumu düzenle" });
    expect(within(pencere).getByLabelText(/Ayıklama gerekçesi/)).toBeDisabled();
    const kurum = within(pencere).getByLabelText("Devralacak okul ya da kurum");
    await user.clear(kurum);
    await user.type(kurum, "Deneme Ortaokulu");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(ayiklama.kalemGuncelle).toHaveBeenCalledWith(3, 12, {
        transfer_target: "Deneme Ortaokulu",
      }),
    );

    await user.click(screen.getByRole("button", { name: "Teklifi geri çek" }));
    expect(await screen.findByText("Teklif geri çekilsin mi?")).toBeInTheDocument();
    await onayla(user, "Geri çek");
    await waitFor(() => expect(ayiklama.geriCek).toHaveBeenCalledWith(3));
    expect(ayiklama.teklif).toHaveBeenCalledTimes(3);
  });

  it("harcama yetkilisinin onayı: ad zorunlu; 28 yolunda imha kararı; onaylanmayan kalem", async () => {
    const hurda = kalem({
      reason: "OBSOLETE",
      reason_display: "Bilimsel değeri kalmamış",
      tmy_path: "TMY_28",
      tmy_path_display: "Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)",
    });
    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "DECIDED",
        status_display: "Komisyon kararı bağlandı",
        decision: {
          id: 9,
          decision_type: "WEEDING",
          decision_date: "2027-06-05",
          decision_no: "2027/5",
        },
        items: [hurda, devirKalemi({ transfer_target: "" })],
      }),
    );
    ayiklama.onayla.mockResolvedValue(teklif());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    expect(await screen.findByText("Devralacak kurum yazılmadı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Harcama yetkilisinin onayını işle" }));
    const pencere = await screen.findByRole("dialog", { name: "Harcama yetkilisinin onayı" });
    expect(within(pencere).getByText(/devralacak kurumu yazılmadı/)).toBeInTheDocument();
    expect(within(pencere).getByText(/Hurdaya ayırma yolunda zorunludur/)).toBeInTheDocument();

    await user.click(within(pencere).getByRole("button", { name: "Onayı işle" }));
    expect(
      within(pencere).getByText("Onaylayan harcama yetkilisinin adını yazın."),
    ).toBeInTheDocument();
    await user.type(within(pencere).getByLabelText(/Harcama yetkilisinin adı/), "Deneme Yetkili");
    await user.type(
      within(pencere).getByLabelText("Komisyon üyeleri"),
      "Deneme Bir{enter}Deneme İki{enter}Deneme Üç",
    );
    await user.click(within(pencere).getByRole("checkbox", { name: /İmha kararı verildi/ }));
    // İmha kararı kalem düzeyindedir (TMY 28/5): hurdaya ayırma kalemi varsayılan olarak seçili.
    const kapsam = within(pencere).getByLabelText("İmha kararının kapsadığı kalemler");
    expect(
      within(kapsam).getByRole("checkbox", {
        name: `${hurda.barcode_display} — ${hurda.work_title}`,
      }),
    ).toBeChecked();
    expect(within(pencere).getByText(/TMY md\. 28\/8/)).toBeInTheDocument();
    expect(within(pencere).getByText(/İşin uzmanını ilk satıra yazın/)).toBeInTheDocument();
    const onaylanmadi = within(pencere).getAllByRole("checkbox", { name: "Onaylanmadı" });
    await user.click(onaylanmadi[1]);
    await user.type(within(pencere).getByLabelText("Gerekçe"), "Devralacak okul bulunamadı.");
    await user.click(within(pencere).getByRole("button", { name: "Onayı işle" }));
    await waitFor(() =>
      expect(ayiklama.onayla).toHaveBeenCalledWith(3, {
        approved_by_name: "Deneme Yetkili",
        approved_on: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        tmy_commission_members: "Deneme Bir\nDeneme İki\nDeneme Üç",
        destruction_decided: true,
        destruction_items: [hurda.id],
        not_approved: { "12": "Devralacak okul bulunamadı." },
      }),
    );
    expect(await screen.findByText("Harcama yetkilisinin onayı işlendi.")).toBeInTheDocument();
  });

  it("imha kararının kapsamından çıkarılan kalem gönderilmez; hiçbiri kalmazsa uyarır", async () => {
    const birinci = kalem({
      reason: "OBSOLETE",
      reason_display: "Bilimsel değeri kalmamış",
      tmy_path: "TMY_28",
      tmy_path_display: "Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)",
    });
    const ikinci = kalem({
      ...birinci,
      id: 13,
      copy: 103,
      barcode_display: "2026-000103",
      work_title: "Ekonomik Değeri Olan Eser",
    });
    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "DECIDED",
        status_display: "Komisyon kararı bağlandı",
        items: [birinci, ikinci],
      }),
    );
    ayiklama.onayla.mockResolvedValue(teklif());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(
      await screen.findByRole("button", { name: "Harcama yetkilisinin onayını işle" }),
    );
    const pencere = await screen.findByRole("dialog", { name: "Harcama yetkilisinin onayı" });
    await user.type(within(pencere).getByLabelText(/Harcama yetkilisinin adı/), "Deneme Yetkili");
    await user.click(within(pencere).getByRole("checkbox", { name: /İmha kararı verildi/ }));
    const kapsam = within(pencere).getByLabelText("İmha kararının kapsadığı kalemler");
    const kutu = (k: typeof birinci) =>
      within(kapsam).getByRole("checkbox", { name: `${k.barcode_display} — ${k.work_title}` });
    await user.click(kutu(birinci));
    await user.click(kutu(ikinci));
    await user.click(within(pencere).getByRole("button", { name: "Onayı işle" }));
    expect(
      within(pencere).getByText("İmha kararının kapsadığı en az bir kalem seçilmelidir."),
    ).toBeInTheDocument();
    expect(ayiklama.onayla).not.toHaveBeenCalled();

    await user.click(kutu(birinci));
    await user.click(within(pencere).getByRole("button", { name: "Onayı işle" }));
    await waitFor(() =>
      expect(ayiklama.onayla).toHaveBeenCalledWith(
        3,
        expect.objectContaining({ destruction_decided: true, destruction_items: [birinci.id] }),
      ),
    );
  });

  it("nadir eser işaretli kalem rozetle gösterilir; imha kararı kalemde yazılır", async () => {
    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "SUBMITTED",
        status_display: "Komisyona sunuldu",
        items: [
          kalem({ copy_is_rare: true }),
          kalem({
            id: 13,
            copy: 103,
            barcode_display: "2026-000103",
            reason: "OBSOLETE",
            reason_display: "Bilimsel değeri kalmamış",
            tmy_path: "TMY_28",
            tmy_path_display: "Hurdaya ayırma nedeniyle kayıttan düşme (TMY 28)",
            destruction_decided: true,
          }),
        ],
      }),
    );
    ciz("/katalog/ayiklama?teklif=3");
    expect(await screen.findByText("Nadir eser — ayıklanamaz")).toBeInTheDocument();
    expect(screen.getByText("İmha kararı (TMY 28/5)")).toBeInTheDocument();
  });

  it("uygula: ikinci doğrulama kutusu işaretlenmeden onaylanmaz", async () => {
    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "APPROVED",
        status_display: "Harcama yetkilisi onayladı",
        approved_on: "2027-06-10",
        approved_by_name: "Deneme Yetkili",
        tmy_commission_members: "Deneme Bir\nDeneme İki",
        destruction_decided: true,
      }),
    );
    ayiklama.belgeler.mockResolvedValue(
      belgeler(["teklif-listesi", "ayiklama-tutanagi", "kayittan-dusme", "devir-listesi"]),
    );
    ayiklama.uygula.mockResolvedValue({ withdrawn: 1, transferred: 1, batch: teklif() });
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    expect(await screen.findByText("Deneme Yetkili · 10.06.2027")).toBeInTheDocument();
    expect(screen.getByText("Deneme Bir · Deneme İki")).toBeInTheDocument();
    expect(screen.getByText("Var (TMY 28/5)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Excel'i indir" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Uygula" }));
    const pencere = await screen.findByRole("dialog");
    expect(within(pencere).getByText(/İşlem geri alınamaz/)).toBeInTheDocument();
    const uygulaDugmesi = within(pencere).getByRole("button", { name: "Uygula" });
    expect(uygulaDugmesi).toBeDisabled();
    await user.click(within(pencere).getByRole("checkbox"));
    await user.click(uygulaDugmesi);
    await waitFor(() => expect(ayiklama.uygula).toHaveBeenCalledWith(3));
    expect(
      await screen.findByText("Teklif uygulandı: 1 nüsha kayıttan düşüldü, 1 nüsha devredildi."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Excel'i indir" }));
    await waitFor(() => expect(ayiklama.belge).toHaveBeenCalledWith(3, "devir-listesi", "xlsx"));
  });

  it("iptal penceresi gerekçeyi gönderir; iptal edilmiş teklif eylemsizdir", async () => {
    ayiklama.iptalEt.mockResolvedValue(teklif());
    const user = userEvent.setup();
    ciz("/katalog/ayiklama?teklif=3");
    await user.click(await screen.findByRole("button", { name: "İptal et" }));
    const pencere = await screen.findByRole("dialog", { name: "Teklif iptal edilsin mi?" });
    await user.type(within(pencere).getByLabelText(/İptal gerekçesi/), "Yanlış açıldı.");
    await user.click(within(pencere).getByRole("button", { name: "İptal et" }));
    await waitFor(() => expect(ayiklama.iptalEt).toHaveBeenCalledWith(3, "Yanlış açıldı."));
    expect(await screen.findByText("Teklif iptal edildi.")).toBeInTheDocument();
  });

  it("iptal edilmiş ve uygulanmış teklif", async () => {
    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "CANCELLED",
        status_display: "İptal edildi",
        cancelled_at: "2027-06-11T10:00:00+03:00",
        cancel_reason: "Yanlış açıldı.",
      }),
    );
    const { unmount } = ciz("/katalog/ayiklama?teklif=3");
    expect(
      await screen.findByText(/11.06.2027 tarihinde iptal edildi: Yanlış açıldı./),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "İptal et" })).not.toBeInTheDocument();
    unmount();

    ayiklama.teklif.mockResolvedValue(
      teklif({
        status: "APPLIED",
        status_display: "Uygulandı",
        applied_at: "2027-06-12T10:00:00+03:00",
        items: [kalem({ state: "APPLIED", state_display: "Uygulandı" })],
      }),
    );
    ciz("/katalog/ayiklama?teklif=3");
    expect(await screen.findByText("12.06.2027")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Teklifi geri çek" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /düzenle/ })).not.toBeInTheDocument();
  });

  it("teklif okunamazsa hata bandı ve dönüş düğmesi", async () => {
    ayiklama.teklif.mockRejectedValue(new ApiError(404, "not_found", "Teklif bulunamadı."));
    ciz("/katalog/ayiklama?teklif=99");
    expect(await screen.findByText("Teklif bulunamadı.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tekliflere dön" })).toBeInTheDocument();
  });
});
