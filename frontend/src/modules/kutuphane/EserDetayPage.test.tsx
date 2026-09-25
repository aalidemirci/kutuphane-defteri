// Eser Ayrıntısı: künye, ISBN uyarısı, nüsha listesi ve hızlı nüsha açma.
//
// Sabitlenen davranışlar:
//   1) ISBN sağlama uyarısı kaydı engellemez ama EKRANDA DURUR (kapanana dek);
//   2) barkod, kayıt no ve etiket tarihleri SALT OKUNURDUR — düzenleme
//      formunda giriş alanı olarak değil, bilgi satırı olarak görünürler;
//   3) tek nüsha standart uca, birden çok nüsha TOPLU uca gider (her biri ayrı
//      numara alır);
//   4) dijital kaynakta (e-kitap) nüsha açma düğmesi hiç görünmez;
//   5) nüsha silme onay diyaloğundan geçer ve numaranın serbest kalmadığını söyler.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { bolum, edinim, eser, nusha, sayfa } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  getWork: vi.fn(),
  updateWork: vi.fn(),
  deleteWork: vi.fn(),
  listCopies: vi.fn(),
  listSections: vi.fn(),
  listAcquisitions: vi.fn(),
  createCopy: vi.fn(),
  createCopies: vi.fn(),
  updateCopy: vi.fn(),
  deleteCopy: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

// F7: nüsha penceresinin "Kayıp, Hasar ve Onarım" bölümü kendi uçlarına gider.
const kayipKapi = vi.hoisted(() => ({
  listele: vi.fn(),
  ac: vi.fn(),
  onarimaGonder: vi.fn(),
  onarimdanDon: vi.fn(),
}));
vi.mock("../kayip/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kayip/api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayipKapi } };
});
const teslimKapi = vi.hoisted(() => ({ listele: vi.fn() }));
vi.mock("../teslim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../teslim/api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslimKapi } };
});
const masaKapi = vi.hoisted(() => ({ nushaDurumu: vi.fn(), uyeAra: vi.fn() }));
vi.mock("../dolasim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dolasim/api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masaKapi } };
});

import EserDetayPage from "./EserDetayPage";

function ekranaBas() {
  return render(
    <MemoryRouter initialEntries={["/katalog/eser/7"]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog" element={<h1>KATALOG</h1>} />
            <Route path="/katalog/eser/:id" element={<EserDetayPage />} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.getWork.mockResolvedValue(eser());
  kapi.listCopies.mockResolvedValue(sayfa([nusha()]));
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
  kapi.listAcquisitions.mockResolvedValue(sayfa([edinim()]));
  kayipKapi.listele.mockResolvedValue(sayfa([]));
  teslimKapi.listele.mockResolvedValue(sayfa([]));
  masaKapi.nushaDurumu.mockResolvedValue({ kind: "COPY", message: "Rafta.", copy: null });
});

describe("Eser Ayrıntısı — künye", () => {
  it("künyeyi ve nüshaları gösterir; başlık sözlükteki addır", async () => {
    ekranaBas();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Eser Ayrıntısı" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Şiir Defteri")).toBeInTheDocument();
    expect(screen.getByText("Deneme Yayınları")).toBeInTheDocument();
    expect(screen.getByText("811 YIL")).toBeInTheDocument();
    expect(await screen.findByText("2026-000123")).toBeInTheDocument();
    // İki basım işareti ayrı sütundur: barkod ve sırt etiketi ayrı basılır (F4).
    for (const baslik of ["Barkod etiketi", "Sırt etiketi", "Etiket doğrulaması"]) {
      expect(screen.getByRole("columnheader", { name: baslik })).toBeInTheDocument();
    }
  });

  it("ISBN uyarısı bant olarak durur (kayıt engellenmez)", async () => {
    kapi.getWork.mockResolvedValue(
      eser({ isbn: "978-975-000-000-1", isbn_warning: "ISBN sağlama hanesi tutmuyor." }),
    );
    ekranaBas();

    const bant = await screen.findByRole("status", { name: "ISBN uyarısı" });
    expect(bant).toHaveTextContent("ISBN sağlama hanesi tutmuyor.");
  });

  it("eser bulunamazsa boş durum kartı ve hata bandı çıkar", async () => {
    kapi.getWork.mockRejectedValue(new Error("yok"));
    ekranaBas();

    expect(await screen.findByText("Eser bulunamadı")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Eser yüklenemedi.");
  });

  it("künye düzenleme formu kaydedilen kaydı ekrana yansıtır", async () => {
    const user = userEvent.setup();
    kapi.updateWork.mockResolvedValue(eser({ title: "İnce Kitap" }));
    ekranaBas();
    await screen.findByText("Şiir Defteri");

    await user.click(screen.getByRole("button", { name: "Künyeyi düzenle" }));
    const diyalog = await screen.findByRole("dialog");
    const ad = within(diyalog).getByLabelText(/Kaynak adı/);
    await user.clear(ad);
    await user.type(ad, "İnce Kitap");
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updateWork).toHaveBeenCalled());
    expect(await screen.findByText("İnce Kitap")).toBeInTheDocument();
  });
});

describe("Eser Ayrıntısı — nüsha açma", () => {
  it("tek nüsha standart uca gider", async () => {
    const user = userEvent.setup();
    kapi.createCopy.mockResolvedValue(nusha());
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    await waitFor(() => expect(kapi.createCopy).toHaveBeenCalled());
    expect(kapi.createCopies).not.toHaveBeenCalled();
    expect(kapi.createCopy.mock.calls[0][0]).toMatchObject({ work: 7, acquisition: 3 });
  });

  it("birden çok nüsha toplu uca gider", async () => {
    const user = userEvent.setup();
    kapi.createCopies.mockResolvedValue({ count: 3, results: [] });
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());
    const adet = within(diyalog).getByLabelText("Nüsha sayısı");
    await user.clear(adet);
    await user.type(adet, "3");
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    await waitFor(() => expect(kapi.createCopies).toHaveBeenCalled());
    expect(kapi.createCopies.mock.calls[0][0]).toMatchObject({ count: 3 });
    expect(kapi.createCopy).not.toHaveBeenCalled();
  });

  it("sınır dışı nüsha sayısında sunucuya gidilmez", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: "Nüsha ekle" }));
    const diyalog = await screen.findByRole("dialog");
    const adet = within(diyalog).getByLabelText("Nüsha sayısı");
    await user.clear(adet);
    await user.type(adet, "500");
    await user.click(within(diyalog).getByRole("button", { name: "Aç" }));

    expect(
      await within(diyalog).findByText("Nüsha sayısı 1 ile 50 arasında olmalıdır."),
    ).toBeInTheDocument();
    expect(kapi.createCopy).not.toHaveBeenCalled();
    expect(kapi.createCopies).not.toHaveBeenCalled();
  });

  it("dijital kaynakta nüsha açma düğmesi yoktur", async () => {
    kapi.getWork.mockResolvedValue(
      eser({ resource_type: "EBOOK", resource_type_display: "E-kitap", is_digital: true }),
    );
    kapi.listCopies.mockResolvedValue(sayfa([]));
    ekranaBas();

    expect(
      await screen.findByText("E-kitap ve e-veri tabanında nüsha açılmaz."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nüsha ekle" })).not.toBeInTheDocument();
  });
});

describe("Eser Ayrıntısı — nüsha düzenleme", () => {
  it("barkod ve kayıt no salt okunurdur, düzenlenen alanlar sunucuya gider", async () => {
    const user = userEvent.setup();
    kapi.updateCopy.mockResolvedValue(nusha({ is_reference: true }));
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    const diyalog = await screen.findByRole("dialog");
    // Salt okunur alanlar bilgi satırıdır, giriş alanı DEĞİL.
    expect(within(diyalog).queryByLabelText("Barkod")).not.toBeInTheDocument();
    expect(within(diyalog).getByText("2026-000123")).toBeInTheDocument();

    await user.click(within(diyalog).getByLabelText("Danışma kaynağı (ödünç verilmez)"));
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updateCopy).toHaveBeenCalled());
    expect(kapi.updateCopy.mock.calls[0][1]).toMatchObject({ is_reference: true });
  });

  it("nüsha silme onay ister ve numaranın serbest kalmadığını söyler", async () => {
    const user = userEvent.setup();
    kapi.deleteCopy.mockResolvedValue(undefined);
    ekranaBas();
    await screen.findByText("2026-000123");

    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByRole("button", { name: "Sil" }));

    const onay = await screen.findByRole("dialog", { name: "Nüsha silinsin mi?" });
    expect(onay).toHaveTextContent(/Numara serbest kalmaz/);
    expect(kapi.deleteCopy).not.toHaveBeenCalled();

    await user.click(within(onay).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(kapi.deleteCopy).toHaveBeenCalledWith(21));
  });
});

// F7: nüsha penceresindeki "Kayıp, Hasar ve Onarım" bölümü (D3, Md. 19, U11).
describe("Eser Ayrıntısı — kayıp, hasar ve onarım", () => {
  async function nushaPenceresi(user: ReturnType<typeof userEvent.setup>) {
    ekranaBas();
    await screen.findByText("2026-000123");
    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    return screen.findByRole("dialog", { name: "Nüshayı düzenle" });
  }

  it("raftaki nüshada onarım, hasar ve kayıp işlemleri; açık dosya ve teslim sorulur", async () => {
    const user = userEvent.setup();
    const diyalog = await nushaPenceresi(user);
    const bolum = within(diyalog).getByRole("region", { name: "Kayıp, Hasar ve Onarım" });
    for (const ad of ["Onarıma gönder", "Hasar dosyası aç", "Kayıp bildir"]) {
      expect(within(bolum).getByRole("button", { name: ad })).toBeInTheDocument();
    }
    await waitFor(() =>
      expect(kayipKapi.listele).toHaveBeenCalledWith({ copy: 21, open: true, limit: 1 }),
    );
    // Teslimde olmayan nüshanın teslimi sorulmaz.
    expect(teslimKapi.listele).not.toHaveBeenCalled();
  });

  it("kayıp bildirimi nüsha penceresini kapatıp kayıp penceresini açar", async () => {
    const user = userEvent.setup();
    kayipKapi.ac.mockResolvedValue({ id: 5, case_type: "LOST" });
    const diyalog = await nushaPenceresi(user);
    await user.click(within(diyalog).getByRole("button", { name: "Kayıp bildir" }));

    expect(screen.queryByRole("dialog", { name: "Nüshayı düzenle" })).not.toBeInTheDocument();
    const kayip = await screen.findByRole("dialog", { name: "Kayıp bildirilsin mi?" });
    await user.click(within(kayip).getByRole("button", { name: "Kayıp bildir" }));
    await waitFor(() =>
      expect(kayipKapi.ac).toHaveBeenCalledWith(
        expect.objectContaining({ case_type: "LOST", copy_id: 21 }),
      ),
    );
    expect(await screen.findByText("Kayıp bildirildi; kayıp dosyası açıldı.")).toBeInTheDocument();
  });

  it("onarıma gönderme onaydan geçer", async () => {
    const user = userEvent.setup();
    kayipKapi.onarimaGonder.mockResolvedValue({
      message: "Nüsha onarıma gönderildi.",
      repair: null,
    });
    const diyalog = await nushaPenceresi(user);
    await user.click(within(diyalog).getByRole("button", { name: "Onarıma gönder" }));
    const onay = await screen.findByRole("dialog", { name: "Nüsha onarıma gönderilsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Onarıma gönder" }));
    await waitFor(() => expect(kayipKapi.onarimaGonder).toHaveBeenCalledWith(21));
    expect(await screen.findByText("Nüsha onarıma gönderildi.")).toBeInTheDocument();
  });

  it("teslimdeki nüshada teslim alan görünür; çözülmemiş hasar dosyası varsa yalnız kayıp bildirilir", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([
        nusha({ status: "DELIVERED", status_display: "Sınıf kitaplığında", is_loanable: false }),
      ]),
    );
    teslimKapi.listele.mockResolvedValue(
      sayfa([
        {
          id: 1,
          recipient_kind_display: "Sınıf kitaplığı",
          recipient_label: "3/A",
          document_no: "2026/2",
          delivered_on: "2026-09-21",
        },
      ]),
    );
    kayipKapi.listele.mockResolvedValue(
      sayfa([
        {
          id: 8,
          case_type: "DAMAGED",
          case_type_display: "Hasar",
          is_open: true,
          reported_on: "2026-09-22",
          resolution_display: "Çözüm bekliyor",
        },
      ]),
    );
    const diyalog = await nushaPenceresi(user);
    const bolum = within(diyalog).getByRole("region", { name: "Kayıp, Hasar ve Onarım" });
    expect(
      await within(bolum).findByText(/Teslimde — Sınıf kitaplığı: 3\/A · belge no 2026\/2/),
    ).toBeInTheDocument();
    expect(await within(bolum).findByText(/Çözülmemiş hasar dosyası/)).toBeInTheDocument();
    expect(within(bolum).getByRole("link", { name: "Dosyayı göster" })).toHaveAttribute(
      "href",
      "/dolasim/kayip-hasar?dosya=8",
    );
    // İkinci hasar dosyası açılmaz; kayıp bildirimi hasar dosyasını "Kayba dönüştü" ile
    // kapatır (F7 düzeltme turu).
    expect(
      within(bolum).queryByRole("button", { name: "Hasar dosyası aç" }),
    ).not.toBeInTheDocument();
    expect(within(bolum).getByRole("button", { name: "Kayıp bildir" })).toBeInTheDocument();
    expect(teslimKapi.listele).toHaveBeenCalledWith({ copy: 21, status: "OPEN", limit: 1 });
  });

  it("çözülmemiş kayıp dosyası varken yeni dosya açılmaz", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([nusha({ status: "ON_LOAN", status_display: "Ödünçte", is_loanable: false })]),
    );
    kayipKapi.listele.mockResolvedValue(
      sayfa([
        {
          id: 9,
          case_type: "LOST",
          case_type_display: "Kayıp",
          is_open: true,
          reported_on: "2026-09-22",
          resolution_display: "Çözüm bekliyor",
        },
      ]),
    );
    const diyalog = await nushaPenceresi(user);
    const bolum = within(diyalog).getByRole("region", { name: "Kayıp, Hasar ve Onarım" });
    expect(await within(bolum).findByText(/Çözülmemiş kayıp dosyası/)).toBeInTheDocument();
    expect(within(bolum).queryByRole("button", { name: "Kayıp bildir" })).not.toBeInTheDocument();
  });

  it("kayıp nüshada son dosya (kapanmış da olsa) gösterilir; “Bulundu” oradan seçilir", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([nusha({ status: "LOST", status_display: "Kayıp", is_loanable: false })]),
    );
    kayipKapi.listele.mockResolvedValue(
      sayfa([
        {
          id: 10,
          case_type: "LOST",
          case_type_display: "Kayıp",
          is_open: false,
          reported_on: "2026-09-22",
          resolution_display: "Kayıttan düşme önerildi",
        },
      ]),
    );
    const diyalog = await nushaPenceresi(user);
    const bolum = within(diyalog).getByRole("region", { name: "Kayıp, Hasar ve Onarım" });
    expect(
      await within(bolum).findByText(
        /Kayıp dosyası · tespit 22\.09\.2026 · Kayıttan düşme önerildi/,
      ),
    ).toBeInTheDocument();
    expect(within(bolum).getByRole("link", { name: "Dosyayı göster" })).toHaveAttribute(
      "href",
      "/dolasim/kayip-hasar?dosya=10",
    );
    expect(kayipKapi.listele).toHaveBeenCalledWith({ copy: 21, open: false, limit: 1 });
    expect(within(bolum).queryByRole("button")).not.toBeInTheDocument();
  });

  it("kayıttan düşülmüş nüshada bölüm görünmez", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([
        nusha({ status: "WITHDRAWN_WEEDED", status_display: "Ayıklandı (kayıttan düşüldü)" }),
      ]),
    );
    const diyalog = await nushaPenceresi(user);
    expect(
      within(diyalog).queryByRole("region", { name: "Kayıp, Hasar ve Onarım" }),
    ).not.toBeInTheDocument();
    expect(kayipKapi.listele).not.toHaveBeenCalled();
  });
});

describe("Eser Ayrıntısı — onarımdaki nüsha", () => {
  it("onarımdan dönüş onaydan geçer; hata iletisi bölümde görünür", async () => {
    const user = userEvent.setup();
    kapi.listCopies.mockResolvedValue(
      sayfa([nusha({ status: "IN_REPAIR", status_display: "Onarımda", is_loanable: false })]),
    );
    kayipKapi.onarimdanDon.mockRejectedValueOnce(new Error("ağ yok"));
    ekranaBas();
    await screen.findByText("2026-000123");
    await user.click(screen.getByRole("button", { name: /2026-000123 numaralı nüshayı düzenle/ }));
    const diyalog = await screen.findByRole("dialog", { name: "Nüshayı düzenle" });
    const bolum = within(diyalog).getByRole("region", { name: "Kayıp, Hasar ve Onarım" });
    expect(within(bolum).queryByRole("button", { name: "Kayıp bildir" })).not.toBeInTheDocument();
    expect(within(bolum).getByRole("button", { name: "Hasar dosyası aç" })).toBeInTheDocument();

    await user.click(within(bolum).getByRole("button", { name: "Onarımdan dön" }));
    const onay = await screen.findByRole("dialog", { name: "Nüsha onarımdan dönsün mü?" });
    expect(onay).toHaveTextContent("Hasar dosyası kendiliğinden kapanmaz");
    await user.click(within(onay).getByRole("button", { name: "Onarımdan dön" }));
    await waitFor(() => expect(kayipKapi.onarimdanDon).toHaveBeenCalledWith(21));
    expect(await within(bolum).findByText("Onarım işlenemedi.")).toBeInTheDocument();
  });
});
