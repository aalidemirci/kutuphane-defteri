// Raporlar sayfası (F10): dört sekme; istatistik kişisizdir ve eşik altı "—" yazılır (açıklaması
// hemen altında); çok okunanlar sayısızdır, "Yeniden hesapla" ve Ayın Kitapları afişi; okuma
// ödülü iç çıktısı "iç kullanım" uyarısıyla ve yalnız PDF; Dökümler sekmesi D kolunun bölümü.
// Bütün adlar ve eserler uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { cokOkunanlar, istatistik, pencere } from "./testVerileri";

const rapi = vi.hoisted(() => ({
  istatistik: vi.fn(),
  pano: vi.fn(),
  cokOkunanlar: vi.fn(),
  pencere: vi.fn(),
  yenidenHesapla: vi.fn(),
  afis: vi.fn(),
  okumaOdulu: vi.fn(),
}));
const oapi = vi.hoisted(() => ({ listSchoolYears: vi.fn() }));
const duzey = vi.hoisted(() => ({ getGradeLevels: vi.fn() }));
const dapi = vi.hoisted(() => ({ ozet: vi.fn(), uyeOzeti: vi.fn() }));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  raporlarApi: rapi,
}));
vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...oapi } };
});
vi.mock("../../lib/gradeLevels", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/gradeLevels")>()),
  getGradeLevels: duzey.getGradeLevels,
}));
vi.mock("../dokumler/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dokumler/api")>();
  return { ...actual, dokumlerApi: { ...actual.dokumlerApi, ...dapi } };
});
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: indirme.saveBlob,
}));

import { KILAVUZ_7_ONERISI, OKUMA_ODULU_ADI } from "./api";
import { YENIDEN_HESAPLANDI, bosListe, cokOkunanlarAciklamasi } from "./CokOkunanlarBolumu";
import { ESIK_ALTI, KISISIZLIK_NOTU, ayEtiketi, esikAciklamasi } from "./IstatistikBolumu";
import { E20_ACIKLAMASI, IC_KULLANIM_UYARISI, ODUL_OLCUTU } from "./OkumaOduluBolumu";
import RaporlarPage from "./RaporlarPage";

const YILLAR = [
  { id: 2, name: "2025-2026", start_date: "2025-09-08", end_date: "2026-06-26", is_active: false },
  { id: 3, name: "2026-2027", start_date: "2026-09-07", end_date: "2027-06-25", is_active: true },
];

function ciz(yol = "/raporlar") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <RaporlarPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

function bolum(ad: string): HTMLElement {
  return screen.getByRole("region", { name: ad });
}

beforeEach(() => {
  vi.resetAllMocks();
  rapi.istatistik.mockResolvedValue(istatistik());
  rapi.cokOkunanlar.mockResolvedValue(cokOkunanlar());
  rapi.afis.mockResolvedValue(new Blob(["%PDF"]));
  rapi.okumaOdulu.mockResolvedValue(new Blob(["%PDF"]));
  oapi.listSchoolYears.mockResolvedValue(YILLAR);
  duzey.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9. Sınıf" },
      { value: 10, label: "10. Sınıf" },
    ],
    prep_enabled: false,
  });
  dapi.ozet.mockReturnValue(new Promise(() => undefined));
  dapi.uyeOzeti.mockReturnValue(new Promise(() => undefined));
});

describe("Raporlar — sayfa", () => {
  it("h1 Raporlar; dört sekme sözlükteki adlarla; varsayılan İstatistik", async () => {
    ciz();
    expect(screen.getByRole("heading", { level: 1, name: "Raporlar" })).toBeInTheDocument();
    const sekmeler = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(sekmeler.map((s) => s?.replace(/^[a-z_]+/, ""))).toEqual([
      "İstatistik",
      "Çok Okunanlar",
      "Dökümler",
      "Okuma Ödülü",
    ]);
    expect(screen.getByRole("tab", { name: /İstatistik/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(await screen.findByRole("region", { name: "Koleksiyon" })).toBeInTheDocument();
  });

  it("sekme değişince ilgili bölüm açılır; Dökümler D kolunun bölümüdür", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(screen.getByRole("tab", { name: /Dökümler/ }));
    await waitFor(() => expect(dapi.ozet).toHaveBeenCalled());
    await user.click(screen.getByRole("tab", { name: /Çok Okunanlar/ }));
    expect(await screen.findByRole("region", { name: "Ayın Kitapları" })).toBeInTheDocument();
  });
});

describe("Raporlar — İstatistik", () => {
  it("dönemi ve bölümleri sunucudan yazar; kişisizlik notu ve Yıl Sonu Raporu bağlantısı", async () => {
    ciz();
    expect(
      await screen.findByText("Dönem 01.09.2026 – 31.08.2027 · 26.09.2026 tarihli kayıtlarla."),
    ).toBeInTheDocument();
    expect(screen.getByText(new RegExp(KISISIZLIK_NOTU.slice(0, 40)))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Yıl Sonu Raporu" })).toHaveAttribute(
      "href",
      "/yil-sonu-raporu",
    );
    for (const ad of [
      "Koleksiyon",
      "Edinim",
      "Dolaşım",
      "Teslim",
      "Kayıp ve Hasar",
      "Ayıklama ve Devir",
    ]) {
      expect(bolum(ad)).toBeInTheDocument();
    }
    const koleksiyon = bolum("Koleksiyon");
    expect(within(koleksiyon).getByText("Elde bulunan kitap").nextSibling).toHaveTextContent(
      "1.250",
    );
    expect(within(koleksiyon).getByText("Bölümü yazılmamış")).toBeInTheDocument();
    expect(within(koleksiyon).getByText("Görsel-işitsel materyal")).toBeInTheDocument();
    const edinim = bolum("Edinim");
    expect(within(edinim).getByText("Mevcut koleksiyon (programa aktarım)")).toBeInTheDocument();
    // Kapanmış dosyalarda sıfır olan çözüm yazılmaz.
    const kayip = bolum("Kayıp ve Hasar");
    expect(within(kayip).getByText("Aynısı temin edildi")).toBeInTheDocument();
    expect(within(kayip).queryByText("Onarıldı")).not.toBeInTheDocument();
    expect(within(bolum("Ayıklama ve Devir")).getByText("Devredilen")).toBeInTheDocument();
  });

  it("dolaşım kırılımında eşik altı “—” yazılır; açıklama k ile hemen altındadır", async () => {
    ciz();
    const dolasim = await screen.findByRole("region", { name: "Dolaşım" });
    const turler = within(dolasim).getByRole("table", { name: "Üye türüne göre" });
    const ogretmen = within(turler).getByRole("row", { name: /Öğretmen/ });
    expect(within(ogretmen).getAllByText(ESIK_ALTI)).toHaveLength(1);
    expect(within(ogretmen).getByText("12")).toBeInTheDocument();
    // Aktif üye sayısı eşiksiz (F10 ekleri K1): ödünç "—" iken üye sayısı yazılır.
    const personel = within(turler).getByRole("row", { name: /Diğer personel/ });
    expect(within(personel).getAllByText(ESIK_ALTI)).toHaveLength(1);
    expect(within(personel).getAllByText(/eşiğin altında, gösterilmez/)).toHaveLength(1);
    expect(within(personel).getByText("2")).toBeInTheDocument();
    expect(esikAciklamasi(5)).not.toMatch(/aktif üyesi olan/);
    expect(esikAciklamasi(5)).toContain("Aktif üye sayısı ödünç verisi değildir; eşiksiz yazılır.");
    const duzeyler = within(dolasim).getByRole("table", { name: "Sınıf düzeyine göre" });
    expect(within(duzeyler).getByRole("row", { name: /12\. Sınıf/ })).toHaveTextContent(ESIK_ALTI);
    expect(within(duzeyler).getByRole("row", { name: /9\. Sınıf/ })).toHaveTextContent("200");
    const aylar = within(dolasim).getByRole("table", { name: "Aylara göre" });
    expect(within(aylar).getByText(ayEtiketi("2026-10"))).toBeInTheDocument();
    expect(within(dolasim).getByLabelText("Eşik açıklaması")).toHaveTextContent(esikAciklamasi(5));
    // Profil yasağı: dolaşımda konu ya da bölüm kırılımı yoktur.
    expect(within(dolasim).queryByText(/Konu|Bölüm/)).not.toBeInTheDocument();
  });

  it("geçmiş ders yılı seçilince o yılın istatistiği istenir", async () => {
    const user = userEvent.setup();
    ciz();
    const secici = await screen.findByLabelText("Dönem");
    await waitFor(() =>
      expect(
        within(secici).getByRole("option", { name: "2026-2027 ders yılı (etkin)" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(secici, "yil-2");
    await waitFor(() => expect(rapi.istatistik).toHaveBeenLastCalledWith({ tur: "yil", yilId: 2 }));
    await user.selectOptions(secici, "");
    await waitFor(() => expect(rapi.istatistik).toHaveBeenLastCalledWith({ tur: "etkin" }));
  });

  it("tarih aralığı “Göster” denince uygulanır; yarım aralıkla istek atılmaz", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByRole("region", { name: "Koleksiyon" });
    expect(rapi.istatistik).toHaveBeenCalledTimes(1);
    await user.selectOptions(screen.getByLabelText("Dönem"), "aralik");
    const goster = screen.getByRole("button", { name: "Göster" });
    expect(goster).toBeDisabled();
    await user.type(screen.getByLabelText("Başlangıç tarihi"), "2026-09-01");
    await user.type(screen.getByLabelText("Bitiş tarihi"), "2026-12-31");
    expect(rapi.istatistik).toHaveBeenCalledTimes(1);
    await user.click(goster);
    await waitFor(() =>
      expect(rapi.istatistik).toHaveBeenLastCalledWith({
        tur: "aralik",
        bas: "2026-09-01",
        son: "2026-12-31",
      }),
    );
  });

  it("sunucunun reddi bantta yazar", async () => {
    rapi.istatistik.mockRejectedValue(
      new ApiError(400, "validation_error", "Başlangıç tarihi bitiş tarihinden sonra olamaz."),
    );
    ciz();
    expect(
      await screen.findByText("Başlangıç tarihi bitiş tarihinden sonra olamaz."),
    ).toBeInTheDocument();
  });
});

describe("Raporlar — Çok Okunanlar", () => {
  it("eşik açıklaması; iki liste sırayla ve SAYISIZ; rozet ve son hesap", async () => {
    ciz("/raporlar?tab=cok-okunanlar");
    expect(await screen.findByText(cokOkunanlarAciklamasi(5))).toBeInTheDocument();
    const ay = bolum("Ayın Kitapları");
    const liste = within(ay).getByRole("list", { name: "Eylül 2026 sırası" });
    const satirlar = within(liste).getAllByRole("listitem");
    expect(satirlar.map((s) => s.textContent)).toEqual([
      "1.Deneme Romanı — Örnek Yazar",
      "2.Uydurma Öyküler",
      "3.Örnek Şiirler — Deneme Şair",
    ]);
    expect(within(ay).getByText("Sürüyor")).toBeInTheDocument();
    expect(within(ay).getByText("Son hesap: 26.09.2026")).toBeInTheDocument();
    const donem = bolum("Dönemin Çok Okunanları");
    expect(within(donem).getByLabelText("Dönem")).toHaveValue("2026-2027/1");
    // Dönem kartında afiş yoktur (afiş ay listesindendir).
    expect(within(donem).queryByRole("button", { name: "PDF'i indir" })).not.toBeInTheDocument();
  });

  it("başka ay seçilince o ayın listesi okunur; kapanmış ay “Kapandı” rozetini taşır", async () => {
    const user = userEvent.setup();
    rapi.pencere.mockResolvedValue(
      pencere({ window: "2026-08", label: "Ağustos 2026", frozen: true, works: [] }),
    );
    ciz("/raporlar?tab=cok-okunanlar");
    const ay = await screen.findByRole("region", { name: "Ayın Kitapları" });
    await user.selectOptions(within(ay).getByLabelText("Ay"), "2026-08");
    await waitFor(() => expect(rapi.pencere).toHaveBeenCalledWith("AY", "2026-08"));
    expect(await within(ay).findByText("Kapandı")).toBeInTheDocument();
    expect(within(ay).getByText("Bu listede eser yok.")).toBeInTheDocument();
    // Boş ayın afişi basılmaz.
    expect(within(ay).getByRole("button", { name: "PDF'i indir" })).toBeDisabled();
  });

  it("pencere okunamazsa kartta hata yazar", async () => {
    const user = userEvent.setup();
    rapi.pencere.mockRejectedValue(
      new ApiError(404, "not_found", "Seçilen dönem ya da ay için çok okunanlar listesi yok."),
    );
    ciz("/raporlar?tab=cok-okunanlar");
    const ay = await screen.findByRole("region", { name: "Ayın Kitapları" });
    await user.selectOptions(within(ay).getByLabelText("Ay"), "2026-08");
    expect(
      await within(ay).findByText("Seçilen dönem ya da ay için çok okunanlar listesi yok."),
    ).toBeInTheDocument();
  });

  it("Ayın Kitapları afişi seçili ayla indirilir; dosya adı belge adı + ay + tarih", async () => {
    const user = userEvent.setup();
    ciz("/raporlar?tab=cok-okunanlar");
    const ay = await screen.findByRole("region", { name: "Ayın Kitapları" });
    await user.click(within(ay).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(rapi.afis).toHaveBeenCalledWith("2026-09"));
    await waitFor(() => expect(indirme.saveBlob).toHaveBeenCalled());
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(/^Ayın-Kitapları-afişi_Eylül-2026_/);
  });

  it("Yeniden hesapla: kapıdaki işi çalıştırır, listeyi tazeler ve bildirir", async () => {
    const user = userEvent.setup();
    rapi.yenidenHesapla.mockResolvedValue({
      computed_on: "2026-09-26",
      k_threshold: 5,
      windows: [],
    });
    ciz("/raporlar?tab=cok-okunanlar");
    await user.click(await screen.findByRole("button", { name: "Yeniden hesapla" }));
    await waitFor(() => expect(rapi.yenidenHesapla).toHaveBeenCalled());
    expect(await screen.findByText(YENIDEN_HESAPLANDI)).toBeInTheDocument();
    expect(rapi.cokOkunanlar).toHaveBeenCalledTimes(2);
  });

  it("geri yükleme sürerken (503) sunucunun iletisi yazar", async () => {
    const user = userEvent.setup();
    rapi.yenidenHesapla.mockRejectedValue(
      new ApiError(503, "bakimda", "Geri yükleme sürüyor; çok okunanlar şimdi hesaplanamaz."),
    );
    ciz("/raporlar?tab=cok-okunanlar");
    await user.click(await screen.findByRole("button", { name: "Yeniden hesapla" }));
    expect(
      await screen.findByText("Geri yükleme sürüyor; çok okunanlar şimdi hesaplanamaz."),
    ).toBeInTheDocument();
  });

  it("henüz liste yoksa eşikle birlikte söyler", async () => {
    rapi.cokOkunanlar.mockResolvedValue(
      cokOkunanlar({
        k_threshold: 7,
        term_windows: [],
        month_windows: [],
        term: null,
        month: null,
      }),
    );
    ciz("/raporlar?tab=cok-okunanlar");
    expect(await screen.findAllByText(bosListe(7))).toHaveLength(2);
  });

  it("özet okunamazsa hata bandı", async () => {
    rapi.cokOkunanlar.mockRejectedValue(new Error("ağ yok"));
    ciz("/raporlar?tab=cok-okunanlar");
    expect(await screen.findByText("Çok okunanlar yüklenemedi.")).toBeInTheDocument();
  });
});

describe("Raporlar — Okuma Ödülü", () => {
  it("iç kullanım uyarısı, Kılavuz 7 alıntısı ve ölçüt; adlar ekrana gelmez (yalnız PDF)", async () => {
    ciz("/raporlar?tab=okuma-odulu");
    const not = await screen.findByRole("note", { name: "İç kullanım" });
    expect(not).toHaveTextContent(IC_KULLANIM_UYARISI);
    expect(screen.getByText(`“${KILAVUZ_7_ONERISI}”`)).toBeInTheDocument();
    expect(screen.getByText(ODUL_OLCUTU)).toBeInTheDocument();
    expect(screen.getByText(/Öneridir, bağlayıcı değildir/)).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("programın kendi metni ödünç sırasını “en çok (kitap) okuyan” listesi diye sunmaz", async () => {
    // Sözlük E20: "en çok okuyan öğrenciler listesi" yasak; Kılavuz 7 cümlesi yalnız alıntıdır.
    const { container } = ciz("/raporlar?tab=okuma-odulu");
    await screen.findByRole("note", { name: "İç kullanım" });
    expect(screen.getByText(E20_ACIKLAMASI)).toBeInTheDocument();
    const metin = (container.textContent ?? "").split(KILAVUZ_7_ONERISI).join("");
    expect(metin).not.toMatch(/en çok (kitap )?okuyan/i);
    expect(E20_ACIKLAMASI).not.toMatch(/okuyan/i);
  });

  it("PDF dönem, sınıf ve sıra sayısıyla istenir; indirme adında kişi adı yok", async () => {
    const user = userEvent.setup();
    ciz("/raporlar?tab=okuma-odulu");
    const sinif = await screen.findByLabelText("Sınıf");
    await waitFor(() =>
      expect(within(sinif).getByRole("option", { name: "9. Sınıf" })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() =>
      expect(rapi.okumaOdulu).toHaveBeenLastCalledWith({
        donem: { tur: "etkin" },
        sinif: null,
        sira: 10,
      }),
    );
    await user.selectOptions(sinif, "9");
    await user.clear(screen.getByLabelText("Sıra sayısı"));
    await user.type(screen.getByLabelText("Sıra sayısı"), "5");
    const donem = screen.getByLabelText("Dönem");
    await waitFor(() =>
      expect(
        within(donem).getByRole("option", { name: "2025-2026 ders yılı" }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(donem, "yil-2");
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() =>
      expect(rapi.okumaOdulu).toHaveBeenLastCalledWith({
        donem: { tur: "yil", yilId: 2 },
        sinif: 9,
        sira: 5,
      }),
    );
    const adlar = indirme.saveBlob.mock.calls.map((c) => String(c[1]));
    expect(adlar[0]).toMatch(/^Okuma-ödülü-iç-çıktısı_\d{2}\.\d{2}\.\d{4}\.pdf$/);
    expect(adlar[1]).toMatch(/^Okuma-ödülü-iç-çıktısı_9-Sınıf_\d{2}\.\d{2}\.\d{4}\.pdf$/);
  });

  it("geçersiz sıra sayısında ve yarım tarih aralığında basılmaz", async () => {
    const user = userEvent.setup();
    ciz("/raporlar?tab=okuma-odulu");
    const sira = await screen.findByLabelText("Sıra sayısı");
    await user.clear(sira);
    await user.type(sira, "0");
    expect(screen.getByText("1 ile 50 arası bir sayı yazın.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF'i indir" })).toBeDisabled();
    await user.clear(sira);
    await user.type(sira, "10");
    await user.selectOptions(screen.getByLabelText("Dönem"), "aralik");
    // İç çıktıda "Göster" yoktur: tarihler yazıldıkça iletilir; yarım aralıkta düğme kapalı.
    expect(screen.queryByRole("button", { name: "Göster" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF'i indir" })).toBeDisabled();
    await user.type(screen.getByLabelText("Başlangıç tarihi"), "2026-09-01");
    expect(screen.getByRole("button", { name: "PDF'i indir" })).toBeDisabled();
    await user.type(screen.getByLabelText("Bitiş tarihi"), "2027-01-22");
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() =>
      expect(rapi.okumaOdulu).toHaveBeenLastCalledWith({
        donem: { tur: "aralik", bas: "2026-09-01", son: "2027-01-22" },
        sinif: null,
        sira: 10,
      }),
    );
  });

  it("boş dönemde sunucunun iletisi yazar", async () => {
    const user = userEvent.setup();
    rapi.okumaOdulu.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Bu dönemde ve kapsamda ödünç alıp iade eden öğrenci yok.",
      ),
    );
    ciz("/raporlar?tab=okuma-odulu");
    await user.click(await screen.findByRole("button", { name: "PDF'i indir" }));
    expect(
      await screen.findByText("Bu dönemde ve kapsamda ödünç alıp iade eden öğrenci yok."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: OKUMA_ODULU_ADI })).toBeInTheDocument();
  });
});

describe("Raporlar — sözlük", () => {
  it("yasak sözcükler geçmez (okuduğu kitaplar, okuma karnesi, okuma puanı, popüler)", async () => {
    const { container, unmount } = ciz();
    await screen.findByRole("region", { name: "Koleksiyon" });
    let metin = container.textContent ?? "";
    unmount();
    for (const sekme of ["cok-okunanlar", "okuma-odulu"]) {
      const { container: c, unmount: kaldir } = ciz(`/raporlar?tab=${sekme}`);
      await screen.findAllByRole("heading", { level: 2 });
      metin += c.textContent ?? "";
      kaldir();
    }
    for (const yasak of [
      /okuduğu kitap/i,
      /okuma karnesi/i,
      /okuma puanı/i,
      /okuma geçmişi/i,
      /popüler/i,
      /en çok ödünç alınan/i,
      /\b[UTAFSDEK]\d{1,2}\b/,
    ]) {
      expect(metin).not.toMatch(yasak);
    }
  });
});
