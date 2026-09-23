// Hızlı Kayıt (yöntem B, F3) — sabitlenen davranışlar:
//
//   1) KÜNYE GETİRME KAPALIYKEN EKRANDAN HİÇBİR DIŞ İSTEK ÇIKMAZ (§8.5-1).
//      Ayar sunucudan okunur; kapalıysa sorgu işlevi HİÇ çağrılmaz ve kullanıcı
//      künyeyi elle yazar.
//   2) Yanlış kod okutulursa (kütüphane etiketi, üye kartı) kayıt başlamaz ve
//      kullanıcı ne okutması gerektiğini okur (§7.1).
//   3) Gelen künye ÖNERİDİR: kaynak ve tarih etiketiyle, "dış kaynaktan alındı,
//      doğrulayın" rozetiyle gelir; çevirmen kutusu dışarıdan DOLMAZ (§8.5-5).
//   4) Katalogda aynı ISBN varsa yeni eser açılmaz, nüsha o esere eklenir.
//   5) Kayıttan sonra odak yeniden okutma kutusuna döner (masa akışı).
//   6) Fail-open: sorgu başarısız olsa da akış sürer (§8.5-9).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  bolum,
  edinim,
  eser,
  kunyeSonucu,
  nusha,
  politika,
  sayfa,
} from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  getPolicy: vi.fn(),
  listSections: vi.fn(),
  listAcquisitions: vi.fn(),
  listWorks: vi.fn(),
  kunyeGetir: vi.fn(),
  createWork: vi.fn(),
  createCopies: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import HizliKayitPage from "./HizliKayitPage";

const ISBN = "9789750812345";

function ekranaBas() {
  return render(
    <MemoryRouter initialEntries={["/katalog/hizli-kayit"]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog/hizli-kayit" element={<HizliKayitPage />} />
            <Route path="/katalog" element={<h1>KATALOG</h1>} />
            <Route path="/katalog/eser/:id" element={<h1>ESER AYRINTISI</h1>} />
            <Route path="/ayarlar" element={<h1>AYARLAR</h1>} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

/** Kodu okutma kutusuna yazıp Enter'a basar (okuyucu da Enter gönderir). */
async function okut(user: ReturnType<typeof userEvent.setup>, kod: string) {
  const kutu = screen.getByLabelText("ISBN barkodu");
  await user.clear(kutu);
  await user.type(kutu, `${kod}{Enter}`);
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.getPolicy.mockResolvedValue(politika({ metadata_lookup_enabled: true }));
  kapi.listSections.mockResolvedValue(sayfa([bolum()]));
  kapi.listAcquisitions.mockResolvedValue(sayfa([edinim()]));
  kapi.listWorks.mockResolvedValue(sayfa([]));
  kapi.kunyeGetir.mockResolvedValue(kunyeSonucu());
  kapi.createWork.mockResolvedValue(eser({ id: 9, title: "Gökyüzü Masalları" }));
  kapi.createCopies.mockResolvedValue({ count: 1, results: [nusha({ id: 41, work: 9 })] });
});

describe("Hızlı Kayıt — künye getirme kapalı", () => {
  beforeEach(() => {
    kapi.getPolicy.mockResolvedValue(politika({ metadata_lookup_enabled: false }));
  });

  it("ISBN okutulsa da künye sorgusu ÇAĞRILMAZ", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Hızlı Kayıt" });
    // Ayarın okunmasını bekle: kapalı olduğu ekranda yazılıdır.
    await screen.findByText(/ISBN ile künye getirme kapalı/);

    await okut(user, ISBN);

    await waitFor(() => expect(kapi.listWorks).toHaveBeenCalled());
    expect(kapi.kunyeGetir).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Ayarlar → Kütüphane Politikası" })).toHaveAttribute(
      "href",
      "/ayarlar?tab=politika",
    );
  });

  it("ayar okunamazsa da sorgu çağrılmaz (kapı fail-closed'dır)", async () => {
    const user = userEvent.setup();
    kapi.getPolicy.mockRejectedValue(new ApiError(500, "server_error", "Sunucu hatası"));
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Hızlı Kayıt" });

    await okut(user, ISBN);

    await waitFor(() => expect(kapi.listWorks).toHaveBeenCalled());
    expect(kapi.kunyeGetir).not.toHaveBeenCalled();
  });

  it("künye elle yazılıp nüsha açılabilir (elle giriş tam işlevlidir)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText(/ISBN ile künye getirme kapalı/);
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Ilık Sular");
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    await waitFor(() => expect(kapi.createWork).toHaveBeenCalledTimes(1));
    expect(kapi.createWork.mock.calls[0][0]).toMatchObject({ title: "Ilık Sular" });
    expect(kapi.kunyeGetir).not.toHaveBeenCalled();
  });
});

describe("Hızlı Kayıt — okutulan kodun türü", () => {
  it("kütüphane etiketi okutulursa künye sorgusu yapılmaz, doğru ileti çıkar", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Hızlı Kayıt" });

    await okut(user, "2026000123");

    expect(
      await screen.findByText(
        "Bu bir kütüphane etiketi. Hızlı kayıtta kitabın arka kapağındaki ISBN barkodu okutulur.",
      ),
    ).toBeInTheDocument();
    expect(kapi.kunyeGetir).not.toHaveBeenCalled();
    expect(kapi.listWorks).not.toHaveBeenCalled();
  });

  it("üye kartı okutulursa da kayıt başlamaz", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Hızlı Kayıt" });

    await okut(user, "94718263");

    expect(await screen.findByText(/Bu bir üye kartı numarası/)).toBeInTheDocument();
    expect(kapi.kunyeGetir).not.toHaveBeenCalled();
  });
});

describe("Hızlı Kayıt — künye önerisi", () => {
  it("öneri kaynak etiketi ve rozetle gelir, formu doldurur, çevirmeni DOLDURMAZ", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "Hızlı Kayıt" });
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    await okut(user, ISBN);

    await waitFor(() => expect(kapi.kunyeGetir).toHaveBeenCalledWith(ISBN, { force: false }));
    expect(await screen.findByText("Dış kaynaktan alındı, doğrulayın")).toBeInTheDocument();
    expect(screen.getAllByText("Bakanlık kataloğu, 23.09.2026").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Çevirmen dışarıdan doldurulmaz; çeviri eserde elle yazın."),
    ).toBeInTheDocument();

    // Form dolar; çevirmen kutusu BOŞ kalır.
    expect(screen.getByLabelText(/^Kaynak adı/)).toHaveValue("Gökyüzü Masalları");
    expect(screen.getByLabelText("Yazar(lar)")).toHaveValue("Ayşe Yılmaz");
    expect(screen.getByLabelText("Yayın yılı")).toHaveValue("2019");
    expect(screen.getByLabelText("Çevirmen")).toHaveValue("");
  });

  it("işareti kaldırılan alan forma yazılmaz", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    await okut(user, ISBN);
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");

    await user.clear(screen.getByLabelText(/^Kaynak adı/));
    await user.click(screen.getByRole("checkbox", { name: "kaynak adı alanını yaz" }));
    await user.click(screen.getByRole("button", { name: "Seçilenleri forma yaz" }));

    expect(screen.getByLabelText(/^Kaynak adı/)).toHaveValue("");
    expect(screen.getByLabelText("Yazar(lar)")).toHaveValue("Ayşe Yılmaz");
  });

  it("elle yazılmış alan SESSİZCE ezilmez; kutu işaretsiz ve kayıttaki değer görünür", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Elle girdiğim ad");
    await okut(user, ISBN);
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");

    // §8.5-5: dolu alan üzerine yazılmaz; fark ekranda görünür.
    expect(screen.getByLabelText(/^Kaynak adı/)).toHaveValue("Elle girdiğim ad");
    expect(screen.getByRole("checkbox", { name: "kaynak adı alanını yaz" })).not.toBeChecked();
    expect(screen.getAllByText("Elle girdiğim ad").length).toBeGreaterThan(0);
  });

  it("“Yeniden getir” önbelleği atlar (force)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    await okut(user, ISBN);
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");

    await user.click(screen.getByRole("button", { name: "Yeniden getir" }));

    await waitFor(() => expect(kapi.kunyeGetir).toHaveBeenCalledWith(ISBN, { force: true }));
  });

  it("sorgu sürerken ikinci okutma yeni bir sorgu başlatmaz", async () => {
    const user = userEvent.setup();
    const bekleyen: { coz?: (deger: unknown) => void } = {};
    kapi.kunyeGetir.mockImplementation(
      () =>
        new Promise((resolve) => {
          bekleyen.coz = resolve;
        }),
    );
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());

    await okut(user, ISBN);
    await waitFor(() => expect(kapi.kunyeGetir).toHaveBeenCalledTimes(1));
    await okut(user, ISBN);

    // Yeniden giriş kapısı: iki yanıt yarışmaz, "Aranıyor…" erken düşmez.
    expect(kapi.kunyeGetir).toHaveBeenCalledTimes(1);
    bekleyen.coz?.(kunyeSonucu());
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");
  });

  it("tanınmayan kod dolu ISBN alanını EZMEZ", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());
    await okut(user, ISBN);
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");

    await okut(user, "RAF-A12");

    expect(await screen.findByText(/Bu numara ISBN'e benzemiyor/)).toBeInTheDocument();
    expect(screen.getByLabelText("ISBN")).toHaveValue(ISBN);
  });

  it("sorgu başarısız olsa da akış sürer (fail-open)", async () => {
    const user = userEvent.setup();
    kapi.kunyeGetir.mockRejectedValue(
      new ApiError(503, "servis_yok", "İnternetten getirilemedi, elle girebilirsiniz."),
    );
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());

    await okut(user, ISBN);

    expect(
      await screen.findByText("İnternetten getirilemedi, elle girebilirsiniz."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^Kaynak adı/)).toBeEnabled();
  });
});

describe("Hızlı Kayıt — kayıt", () => {
  it("katalogda aynı ISBN varsa yeni eser AÇILMAZ, nüsha o esere eklenir", async () => {
    const user = userEvent.setup();
    kapi.listWorks.mockResolvedValue(sayfa([eser({ id: 7, title: "Şiir Defteri" })]));
    ekranaBas();
    await waitFor(() => expect(kapi.getPolicy).toHaveBeenCalled());

    await okut(user, ISBN);
    await screen.findByText(/Katalogda bu numarayla 1 eser var/);
    await user.click(screen.getByRole("button", { name: "Bu esere nüsha ekle" }));

    expect(screen.getByText("Seçilen eser")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    await waitFor(() => expect(kapi.createCopies).toHaveBeenCalledTimes(1));
    expect(kapi.createWork).not.toHaveBeenCalled();
    expect(kapi.createCopies.mock.calls[0][0]).toMatchObject({
      work: 7,
      acquisition: 3,
      count: 1,
    });
  });

  it("kayıttan sonra barkod gösterilir ve odak yeniden okutma kutusuna döner", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    expect(await screen.findByText("Eser ve nüsha açıldı")).toBeInTheDocument();
    expect(screen.getByText(/2026-000123/)).toBeInTheDocument();
    expect(screen.getByLabelText("ISBN barkodu")).toHaveFocus();
  });

  it("kayıttan sonra künye ve nüsha alanları BOŞALIR (sıradaki kitap devralmaz)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.type(screen.getByLabelText("Çevirmen"), "Deniz Korkmaz");
    await user.type(screen.getByLabelText("Eski kayıt no"), "1452");
    await user.click(screen.getByLabelText(/Danışma kaynağı/));
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));
    await screen.findByText("Eser ve nüsha açıldı");

    // A kitabının künyesi B kitabına devredemez: "Nüshayı aç" formu sıfırlar.
    expect(screen.getByLabelText(/^Kaynak adı/)).toHaveValue("");
    expect(screen.getByLabelText("Çevirmen")).toHaveValue("");
    expect(screen.getByLabelText("Eski kayıt no")).toHaveValue("");
    expect(screen.getByLabelText(/Danışma kaynağı/)).not.toBeChecked();
    expect(screen.getByLabelText("Nüsha sayısı")).toHaveValue("1");
  });

  it("kaynak adı boşken istemcide durur (sunucuya boş istek gitmez)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    expect(await screen.findByText("Kaynak adı yazılmalıdır.")).toBeInTheDocument();
    expect(kapi.createWork).not.toHaveBeenCalled();
  });
});
