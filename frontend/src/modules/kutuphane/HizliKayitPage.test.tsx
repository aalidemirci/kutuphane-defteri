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
//   7) KİTAPTAKİ ETİKET (F4, önce etiket yolu): etiket ÖNCE sorulur (yazma yok),
//      bağlanamayacaksa eser AÇILMAZ; bağlanabiliyorsa eser açılır ve nüsha
//      etiketin numarasıyla açılır. Eser açılıp nüsha açılamazsa eser seçili
//      kalır (yeniden denemede ikinci eser açılmaz). Açık boş etiket varsa ekran
//      etiket yoluyla açılır.
//   8) Etiketsiz kitapta "Etiket yok — yeni numara ver" bugünkü yoldur; açılan
//      nüshanın etiketi tek etiket kısayoluyla bir basım partisi olarak basılır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  basimPartisi,
  basimPartisiAyrintisi,
  etiketDenetimi,
  etiketOzeti,
  hazirSablonlar,
} from "../../test/etiketVerileri";
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

const etiket = vi.hoisted(() => ({
  ozet: vi.fn(),
  etiketDenetle: vi.fn(),
  etiketleNushaAc: vi.fn(),
  sablonlar: vi.fn(),
  kalibrasyonlar: vi.fn(),
  partiAc: vi.fn(),
  partiOnayla: vi.fn(),
}));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

const sayimKapisi = vi.hoisted(() => ({ durum: vi.fn() }));
vi.mock("../sayim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../sayim/api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...sayimKapisi } };
});

import { PROGRAMA_AKTARIM_KAPALI } from "../sayim/api";
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
  // Varsayılan: açık boş etiket yok → ekran bugünkü yolla (yeni numara) açılır.
  etiket.ozet.mockResolvedValue(
    etiketOzeti({ reservations: { reserved: 0, bound: 0, cancelled: 0, open: 0 } }),
  );
  etiket.etiketDenetle.mockResolvedValue(etiketDenetimi());
  etiket.etiketleNushaAc.mockResolvedValue(
    nusha({ id: 42, work: 9, barcode: "2026000101", barcode_display: "2026-000101" }),
  );
  etiket.sablonlar.mockResolvedValue(sayfa(hazirSablonlar()));
  etiket.kalibrasyonlar.mockResolvedValue(sayfa([]));
  etiket.partiAc.mockResolvedValue(basimPartisiAyrintisi({ copy_count: 1 }));
  // Varsayılan: süren sayım ve TMY 32/3 durdurması yok.
  sayimKapisi.durum.mockResolvedValue({
    live: null,
    tmy_stop_active: false,
    service_pause_active: false,
    returns_open: true,
  });
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
    // Yeni numara yolunda odak okutma kutusuna döner, ISBN seçili: düğmede kalsaydı
    // okuyucunun sıradaki okutması kaybolur, Enter düğmeye yeniden basardı.
    const kodKutusu = screen.getByLabelText("ISBN barkodu") as HTMLInputElement;
    expect(kodKutusu).toHaveFocus();
    expect([kodKutusu.selectionStart, kodKutusu.selectionEnd]).toEqual([0, ISBN.length]);
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

describe("Hızlı Kayıt — kitaptaki etiket (önce etiket yolu)", () => {
  beforeEach(() => {
    etiket.ozet.mockResolvedValue(etiketOzeti());
  });

  /** Etiket yolunun açılmasını bekler (açık boş etiket sayısı sunucudan okunur). */
  async function etiketYolunuBekle() {
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Kitaptaki etiketi okutun" })).toBeChecked(),
    );
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());
  }

  it("açık boş etiket varsa ekran etiket yoluyla açılır; nüsha sayısı sorulmaz", async () => {
    ekranaBas();
    await etiketYolunuBekle();

    expect(screen.getByLabelText("Kütüphane etiketi")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nüsha sayısı")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Etiket yok — yeni numara ver" })).not.toBeChecked();
  });

  it("ISBN okutulunca odak etiket kutusuna geçer; etiket ÖNCE sorulur, sonra eser ve nüsha açılır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await etiketYolunuBekle();

    await okut(user, ISBN);
    await screen.findByText("Dış kaynaktan alındı, doğrulayın");
    const etiketKutusu = screen.getByLabelText("Kütüphane etiketi");
    await waitFor(() => expect(etiketKutusu).toHaveFocus());

    await user.type(etiketKutusu, "2026-000101{Enter}");

    await waitFor(() => expect(etiket.etiketleNushaAc).toHaveBeenCalledTimes(1));
    expect(etiket.etiketDenetle).toHaveBeenCalledWith("2026-000101");
    expect(etiket.etiketleNushaAc.mock.calls[0][0]).toMatchObject({
      work: 9,
      acquisition: 3,
      label_code: "2026-000101",
    });
    // Sıra bağlayıcıdır: ön denetim → eser → nüsha.
    const sira = [
      etiket.etiketDenetle.mock.invocationCallOrder[0],
      kapi.createWork.mock.invocationCallOrder[0],
      etiket.etiketleNushaAc.mock.invocationCallOrder[0],
    ];
    expect(sira).toEqual([...sira].sort((a, b) => a - b));
    expect(kapi.createCopies).not.toHaveBeenCalled();
    expect(await screen.findByText("Nüsha 2026-000101 numarasıyla açıldı.")).toBeInTheDocument();
    expect(screen.getByText(/barkod etiketi okutulmuş sayılır/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sırt etiketini bas" })).toBeInTheDocument();
    expect(screen.getByLabelText("ISBN barkodu")).toHaveFocus();
    expect(screen.getByLabelText("Kütüphane etiketi")).toHaveValue("");
  });

  it("başka nüshaya bağlı etiket için eser AÇILMAZ; kitap zaten kayıtlı olabilir denir, yeni numara ÖNERİLMEZ", async () => {
    const user = userEvent.setup();
    etiket.etiketDenetle.mockResolvedValue(
      etiketDenetimi({
        bindable: false,
        kind: "COPY",
        copy: 77,
        work_title: "Şiir Defteri",
        message:
          "Bu etiket zaten kayıtlı bir nüshanın: 2026-000101 — Şiir Defteri. Elinizdeki kitap buysa kitap zaten kayıtlıdır; yeniden kaydetmeyin. Başka bir kitapsa etiketi sökün ve kitaba başka bir boş etiket yapıştırın.",
        hint: "",
      }),
    );
    ekranaBas();
    await etiketYolunuBekle();

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.type(screen.getByLabelText("Kütüphane etiketi"), "2026000101{Enter}");

    expect(await screen.findByText(/yeniden kaydetmeyin/)).toBeInTheDocument();
    expect(screen.queryByText(/“Etiket yok — yeni numara ver” seçeneğini kullanın/)).toBeNull();
    expect(kapi.createWork).not.toHaveBeenCalled();
    expect(etiket.etiketleNushaAc).not.toHaveBeenCalled();
    // Kullanıcının yazdığı künye kaybolmaz.
    expect(screen.getByLabelText(/^Kaynak adı/)).toHaveValue("Gökyüzü Masalları");
  });

  it("iptal edilmiş etikette gerekçe ve yeni numara yolu söylenir", async () => {
    const user = userEvent.setup();
    etiket.etiketDenetle.mockResolvedValue(
      etiketDenetimi({
        bindable: false,
        kind: "CANCELLED",
        message:
          "Bu etiketin numarası iptal edildi; kullanılamaz. Etiketi kitaptan sökün ve başka bir boş etiket yapıştırın.",
        hint: "Kitapta etiket yoksa “Etiket yok — yeni numara ver” seçeneğini kullanın.",
      }),
    );
    ekranaBas();
    await etiketYolunuBekle();

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.type(screen.getByLabelText("Kütüphane etiketi"), "2026000101{Enter}");

    expect(await screen.findByText(/numarası iptal edildi/)).toBeInTheDocument();
    expect(
      screen.getByText(/“Etiket yok — yeni numara ver” seçeneğini kullanın/),
    ).toBeInTheDocument();
    expect(kapi.createWork).not.toHaveBeenCalled();
  });

  it("katalogda aynı ISBN varken “Bu esere nüsha ekle” odağı etiket kutusuna taşır; okutulan etiket kaydı bitirir", async () => {
    const user = userEvent.setup();
    kapi.listWorks.mockResolvedValue(
      sayfa([eser({ id: 5, title: "Şiir Defteri", copy_count: 1 })]),
    );
    ekranaBas();
    await etiketYolunuBekle();

    await okut(user, ISBN);
    await user.click(await screen.findByRole("button", { name: "Bu esere nüsha ekle" }));
    await screen.findByText("Seçilen eser");
    expect(screen.getByLabelText("Kütüphane etiketi")).toHaveFocus();

    // Okuyucu odaktaki kutuya yazar; sondaki Enter kaydı bitirir.
    await user.keyboard("2026000101{Enter}");

    await waitFor(() => expect(etiket.etiketleNushaAc).toHaveBeenCalledTimes(1));
    expect(etiket.etiketDenetle).toHaveBeenCalledWith("2026000101");
    expect(etiket.etiketleNushaAc.mock.calls[0][0]).toMatchObject({
      work: 5,
      label_code: "2026000101",
    });
    expect(kapi.createWork).not.toHaveBeenCalled();
  });

  it("erken okutulan etiket seçili kalır: künye tamamlanıp etiket yeniden okutulunca TEK kod gider", async () => {
    const user = userEvent.setup();
    kapi.getPolicy.mockResolvedValue(politika({ metadata_lookup_enabled: false }));
    ekranaBas();
    await etiketYolunuBekle();

    await okut(user, ISBN);
    const etiketKutusu = screen.getByLabelText("Kütüphane etiketi") as HTMLInputElement;
    await waitFor(() => expect(etiketKutusu).toHaveFocus());
    // Kullanıcı künyeyi yazmadan etiketi okutur.
    await user.keyboard("2026-000101{Enter}");
    expect(await screen.findByText("Kaynak adı yazılmalıdır.")).toBeInTheDocument();
    expect(etiketKutusu.value).toBe("2026-000101");
    expect([etiketKutusu.selectionStart, etiketKutusu.selectionEnd]).toEqual([0, 11]);

    // Künyeyi yazar, kutuya tıklayıp etiketi yeniden okutur.
    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.click(etiketKutusu);
    await user.keyboard("2026-000101{Enter}");

    await waitFor(() => expect(etiket.etiketDenetle).toHaveBeenCalledTimes(1));
    expect(etiket.etiketDenetle).toHaveBeenCalledWith("2026-000101");
  });

  it("etiket okutulmadan kayıt başlamaz", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await etiketYolunuBekle();

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    expect(
      await screen.findByText("Kitaba yapıştırdığınız kütüphane etiketini okutun."),
    ).toBeInTheDocument();
    expect(etiket.etiketDenetle).not.toHaveBeenCalled();
    expect(kapi.createWork).not.toHaveBeenCalled();
  });

  it("eser açılıp nüsha açılamazsa eser seçili kalır; yeniden denemede ikinci eser açılmaz", async () => {
    const user = userEvent.setup();
    etiket.etiketleNushaAc.mockRejectedValueOnce(
      new ApiError(400, "validation_error", "Bu etiketin numarası iptal edildi; kullanılamaz.", {
        label_code: ["Bu etiketin numarası iptal edildi; kullanılamaz."],
      }),
    );
    ekranaBas();
    await etiketYolunuBekle();

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.type(screen.getByLabelText("Kütüphane etiketi"), "2026000101{Enter}");

    expect(await screen.findByText(/Eser kaydedildi; sorunu giderip/)).toBeInTheDocument();
    expect(screen.getByText("Seçilen eser")).toBeInTheDocument();
    expect(kapi.createWork).toHaveBeenCalledTimes(1);

    const etiketKutusu = screen.getByLabelText("Kütüphane etiketi");
    await user.clear(etiketKutusu);
    await user.type(etiketKutusu, "2026000102{Enter}");

    await waitFor(() => expect(etiket.etiketleNushaAc).toHaveBeenCalledTimes(2));
    expect(kapi.createWork).toHaveBeenCalledTimes(1);
    expect(etiket.etiketleNushaAc.mock.calls[1][0]).toMatchObject({
      work: 9,
      label_code: "2026000102",
    });
  });

  it("etiket yolunda ISBN kutusuna okutulan kütüphane etiketi için yol gösterilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await etiketYolunuBekle();

    await okut(user, "2026000101");

    expect(
      await screen.findByText(/etiketi “Kütüphane etiketi” kutusuna okutun/),
    ).toBeInTheDocument();
    expect(kapi.listWorks).not.toHaveBeenCalled();
  });

  it("“Etiket yok — yeni numara ver” seçilirse sayaçtan numara verilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await etiketYolunuBekle();

    await user.click(screen.getByRole("radio", { name: "Etiket yok — yeni numara ver" }));
    expect(screen.queryByLabelText("Kütüphane etiketi")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));

    await waitFor(() => expect(kapi.createCopies).toHaveBeenCalledTimes(1));
    expect(etiket.etiketDenetle).not.toHaveBeenCalled();
  });
});

describe("Hızlı Kayıt — tek etiket kısayolu", () => {
  it("açılan nüshanın etiketi basım partisi olarak hazırlanır (PDF almak basıldı saymaz)", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.click(screen.getByRole("button", { name: "Nüshayı aç" }));
    await user.click(await screen.findByRole("button", { name: "Etiketini bas" }));

    expect(await screen.findByText("Etiket Basımı")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));
    await user.click(screen.getByRole("button", { name: "7. hücre" }));
    await user.click(screen.getByRole("button", { name: "Basım partisini hazırla" }));

    await waitFor(() => expect(etiket.partiAc).toHaveBeenCalledTimes(1));
    expect(etiket.partiAc.mock.calls[0][0]).toMatchObject({
      kind: "BOTH",
      order: "IMPORT_ROW",
      copies: [41],
      template: 1,
      start_cell: 7,
    });
    expect(
      await screen.findByRole("button", { name: "Basıldı olarak işaretle" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Etiket basımını kapat" }));
    expect(screen.queryByText("Etiket Basımı")).not.toBeInTheDocument();
    expect(screen.getByLabelText("ISBN barkodu")).toHaveFocus();
  });
});

describe("Hızlı Kayıt — sırt etiketi kısayolu (etiket yolu)", () => {
  it("sırt etiketi onaylanınca doğrulama okutması ÖNERİLMEZ (sırt etiketi barkod taşımaz)", async () => {
    const user = userEvent.setup();
    etiket.ozet.mockResolvedValue(etiketOzeti());
    etiket.partiAc.mockResolvedValue(
      basimPartisiAyrintisi({ kind: "SPINE", kind_display: "Sırt etiketi", copy_count: 1 }),
    );
    etiket.partiOnayla.mockResolvedValue(
      basimPartisi({ kind: "SPINE", kind_display: "Sırt etiketi", status: "CONFIRMED" }),
    );
    ekranaBas();
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Kitaptaki etiketi okutun" })).toBeChecked(),
    );
    await waitFor(() => expect(kapi.listAcquisitions).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/^Kaynak adı/), "Gökyüzü Masalları");
    await user.type(screen.getByLabelText("Kütüphane etiketi"), "2026000101{Enter}");
    await user.click(await screen.findByRole("button", { name: "Sırt etiketini bas" }));
    await waitFor(() =>
      expect((screen.getByLabelText(/^Etiket şablonu/) as HTMLSelectElement).value).not.toBe(""),
    );
    await user.click(screen.getByRole("button", { name: "Basım partisini hazırla" }));
    await waitFor(() => expect(etiket.partiAc).toHaveBeenCalledTimes(1));
    expect(etiket.partiAc.mock.calls[0][0]).toMatchObject({ kind: "SPINE" });

    await user.click(await screen.findByRole("button", { name: "Basıldı olarak işaretle" }));
    const pencere = await screen.findByRole("dialog", {
      name: "Etiketler basıldı olarak işaretlensin mi?",
    });
    expect(within(pencere).queryByText(/doğrulaması sıfırlanır/)).toBeNull();
    await user.click(within(pencere).getByRole("button", { name: "Basıldı olarak işaretle" }));

    expect(await screen.findByText("Sırt etiketi basıldı olarak işaretlendi.")).toBeInTheDocument();
    expect(screen.queryByText(/Doğrulama Okutması'nda okutabilirsiniz/)).toBeNull();
  });
});

describe("Hızlı Kayıt — TMY 32/3 durdurması (F9 düzeltme turu)", () => {
  it("durdurma sürerken “Nüshayı aç” kapalıdır; eser açılıp nüshasız kalmaz", async () => {
    const user = userEvent.setup();
    sayimKapisi.durum.mockResolvedValue({
      live: null,
      tmy_stop_active: true,
      service_pause_active: false,
      returns_open: true,
    });
    ekranaBas();
    expect(
      await screen.findByRole("status", { name: "TMY 32/3 durdurması sürüyor" }),
    ).toBeInTheDocument();
    const dugme = screen.getByRole("button", { name: "Nüshayı aç" });
    await waitFor(() => expect(dugme).toBeDisabled());
    await user.click(dugme);
    expect(kapi.createWork).not.toHaveBeenCalled();
    expect(etiket.etiketDenetle).not.toHaveBeenCalled();
  });

  it("programa aktarım ediniminde bant TMY'ye dayanmaz (K4); “Nüshayı aç” yine kapalıdır", async () => {
    kapi.listAcquisitions.mockResolvedValue(
      sayfa([
        edinim({
          method: "EXISTING_STOCK",
          method_display: "Mevcut koleksiyon (programa aktarım)",
        }),
      ]),
    );
    sayimKapisi.durum.mockResolvedValue({
      live: null,
      tmy_stop_active: true,
      service_pause_active: false,
      returns_open: true,
    });
    ekranaBas();
    const bant = await screen.findByRole("status", { name: "Sayım sürüyor" });
    expect(bant).toHaveTextContent(PROGRAMA_AKTARIM_KAPALI);
    expect(bant).not.toHaveTextContent("TMY");
    expect(screen.queryByRole("status", { name: "TMY 32/3 durdurması sürüyor" })).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Nüshayı aç" })).toBeDisabled());
  });
});
