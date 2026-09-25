// Görevli ekranı — görevliye açık masa işi: etiket doğrulama okutması (kullanıcı
// kararı 24.09.2026). Sabitlenen davranışlar:
//
//   1) Doğrulama okutması görevli ekranından açılır; sayfanın h1'i "Görevli Kipi"
//      kalır (üst çubukla aynı), iş bölüm başlığıdır.
//   2) Görevli kipinde yalnız okutma ucu çağrılır: "Doğrulanmamış Etiketler"
//      listesi (yönetici ucu, görevliye 403) istenmez ve gösterilmez.
//   3) Sunucunun görevliye döndürdüğü daraltılmış özet (barkod + eser adı) yazılır.
//   4) "Okutmayı bitir" görevli ekranına döner; yönetici kipine geçiş iki görünümde
//      de açıktır.
//   5) F9 (madde 24, 26 — 25.09.2026 kullanıcı kararları): "Sayım okutmasını aç" yalnız
//      süren sayım varken görünür ve yalnız okutma ucunu çağırır; hizmet arası şeridi
//      masada açılışta görünür.

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { dogrulamaSonucu } from "../../test/etiketVerileri";

const etiket = vi.hoisted(() => ({
  dogrula: vi.fn(),
  dogrulanmamislar: vi.fn(),
}));

vi.mock("../kutuphane/etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kutuphane/etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

const katalog = vi.hoisted(() => ({
  eserAra: vi.fn(),
  nushalar: vi.fn(),
}));
// F9 (madde 24, 26): masanın kişisiz durumu — hizmet arası ve süren sayımın okutması.
const masa = vi.hoisted(() => ({ masaDurumu: vi.fn() }));

vi.mock("../dolasim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dolasim/api")>();
  return {
    ...actual,
    katalogOkumaApi: { ...actual.katalogOkumaApi, ...katalog },
    dolasimApi: { ...actual.dolasimApi, ...masa },
  };
});

// F9 (madde 24): sayım okutması — görevli kipinde yalnız okutma ucu çağrılır.
const sayimKapisi = vi.hoisted(() => ({
  gorevliOkut: vi.fn(),
  okut: vi.fn(),
  ilerleme: vi.fn(),
  kalemler: vi.fn(),
  durum: vi.fn(),
}));
vi.mock("../sayim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../sayim/api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...sayimKapisi } };
});

// F7: teslimden geri alma okutması (görevli kipinde açık tek teslim ucu).
const teslim = vi.hoisted(() => ({ geriAl: vi.fn(), geriAlmaDokumuPdf: vi.fn() }));
vi.mock("../teslim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../teslim/api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslim } };
});

import { OKUTMA_KUTUSU } from "../dolasim/DolasimMasasi";
import { GERI_ALMA_KUTUSU } from "../teslim/GeriAlmaOkutmasi";
import GorevliEkrani, {
  BEKLEYEN_ANAHTAR_METNI,
  GOREVLI_DOGRULAMA_BASLIGI,
  GOREVLI_DOGRULAMA_BITIR,
  GOREVLI_DOGRULAMA_DUGMESI,
  GOREVLI_EKRANI_METNI,
  GOREVLI_GERI_ALMA_BASLIGI,
  GOREVLI_GERI_ALMA_DUGMESI,
  GOREVLI_KATALOG_DUGMESI,
  GOREVLI_MASA_BASLIGI,
  GOREVLI_MASAYA_DON,
  GOREVLI_SAYIM_BASLIGI,
  GOREVLI_SAYIM_DUGMESI,
} from "./GorevliEkrani";
import { HIZMET_ARASI_SURUYOR } from "../sayim/SayimKarti";

beforeEach(() => {
  vi.clearAllMocks();
  masa.masaDurumu.mockResolvedValue({ service_pause: false, stocktake_scan: null });
  // Görevli kipinde sunucu nüsha özetinden yalnız barkodu ve eser adını döndürür.
  etiket.dogrula.mockResolvedValue(
    dogrulamaSonucu({
      copy: { barcode: "2026000123", barcode_display: "2026-000123", work_title: "Şiir Defteri" },
    }),
  );
});

describe("GorevliEkrani — doğrulama okutması", () => {
  it("görevli ekranından açılır; yalnız okutma ucu kullanılır", async () => {
    const user = userEvent.setup();
    render(<GorevliEkrani onGecti={vi.fn()} />);

    expect(GOREVLI_DOGRULAMA_DUGMESI).toBe("Doğrulama okutmasını aç");
    await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_DUGMESI }));

    expect(screen.getByRole("heading", { level: 1, name: "Görevli Kipi" })).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 2, name: GOREVLI_DOGRULAMA_BASLIGI }),
    ).toBeVisible();
    const kutu = screen.getByLabelText("Kütüphane etiketi");
    expect(kutu).toHaveFocus();

    await user.type(kutu, "2026000123{Enter}");

    expect(await screen.findByText("Etiket doğrulandı.")).toBeInTheDocument();
    expect(screen.getByText("2026-000123 — Şiir Defteri")).toBeInTheDocument();
    expect(etiket.dogrula).toHaveBeenCalledWith("2026000123");
    // Yönetici ucu görevli kipinde istenmez; liste de gösterilmez.
    expect(etiket.dogrulanmamislar).not.toHaveBeenCalled();
    expect(screen.queryByText(/Doğrulanmamış Etiketler/)).toBeNull();
    expect(screen.queryByText(/aşağıdaki listede kalır/)).toBeNull();
    expect(screen.getByRole("button", { name: "Yönetici kipine geç" })).toBeInTheDocument();
  });

  it("“Okutmayı bitir” görevli ekranına döner", async () => {
    const user = userEvent.setup();
    render(<GorevliEkrani onGecti={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_DUGMESI }));

    await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_BITIR }));

    expect(screen.getByText(GOREVLI_EKRANI_METNI)).toBeInTheDocument();
    expect(screen.queryByLabelText("Kütüphane etiketi")).toBeNull();
  });

  it("bekleyen kurtarma anahtarı uyarısı okutma açıkken de görünür", async () => {
    const user = userEvent.setup();
    render(<GorevliEkrani onGecti={vi.fn()} anahtarBekliyor />);
    expect(screen.getByText(BEKLEYEN_ANAHTAR_METNI)).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_DUGMESI }));
    });

    expect(screen.getByText(BEKLEYEN_ANAHTAR_METNI)).toBeInTheDocument();
  });
});

describe("GorevliEkrani — dolaşım masası ve katalog (F6)", () => {
  it("varsayılan iş dolaşım masasıdır; okutma kutusu odaktadır", () => {
    render(<GorevliEkrani onGecti={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1, name: "Görevli Kipi" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 2, name: GOREVLI_MASA_BASLIGI })).toBeVisible();
    expect(screen.getByLabelText(OKUTMA_KUTUSU)).toHaveFocus();
    // Yönetici işleri görevli ekranında yoktur.
    expect(screen.queryByRole("button", { name: "Kartsız ödünç" })).toBeNull();
  });

  it("katalogda arama yalnız izinli sorgu parametreleriyle yapılır; masaya dönülür", async () => {
    const user = userEvent.setup();
    katalog.eserAra.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 5,
          title: "Şiir Defteri",
          authors: "Deneme Yazar",
          translator: "",
          edition: "",
          publisher: "",
          publish_year: null,
          isbn: "",
          subjects: "",
          language: "",
          resource_type: "BOOK",
          resource_type_display: "Kitap",
          classification_code: "811",
          call_number: "811 DEN",
          section_name: "Edebiyat",
          copy_count: 2,
          available_copy_count: 1,
        },
      ],
    });
    katalog.nushalar.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 9,
          work: 5,
          work_title: "Şiir Defteri",
          call_number: "811 DEN",
          section_name: "Edebiyat",
          status: "ON_LOAN",
          status_display: "Ödünçte",
          is_loanable: false,
          not_loanable_reason: "Ödünçte — ödünç verilemez.",
        },
      ],
    });
    render(<GorevliEkrani onGecti={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: GOREVLI_KATALOG_DUGMESI }));
    await user.type(screen.getByLabelText(/Kaynak adı, yazar/), "şiir{Enter}");
    await user.click(await screen.findByRole("button", { name: /Şiir Defteri/ }));

    expect(katalog.eserAra).toHaveBeenCalledWith("şiir", 0);
    expect(katalog.nushalar).toHaveBeenCalledWith(5);
    expect(await screen.findByText("Edebiyat · Ödünçte")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: GOREVLI_MASAYA_DON }));
    expect(screen.getByLabelText(OKUTMA_KUTUSU)).toBeInTheDocument();
  });
});

describe("GorevliEkrani — teslimden geri alma (F7)", () => {
  it("görevli ekranından açılır; teslim alanın kimliği ve evrak görünmez; masaya dönülür", async () => {
    const user = userEvent.setup();
    // Görevli kipinde sunucu `delivery` göndermez.
    teslim.geriAl.mockResolvedValue({
      result: "returned",
      kind: "COPY",
      message: "Geri alındı.",
      copy: { barcode: "2026000123", barcode_display: "2026-000123", work_title: "Sınıf Kitabı" },
    });
    render(<GorevliEkrani onGecti={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: GOREVLI_GERI_ALMA_DUGMESI }));
    expect(screen.getByRole("heading", { level: 1, name: "Görevli Kipi" })).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 2, name: GOREVLI_GERI_ALMA_BASLIGI }),
    ).toBeVisible();
    const kutu = screen.getByLabelText(GERI_ALMA_KUTUSU);
    expect(kutu).toHaveFocus();

    await user.type(kutu, "2026000123{Enter}");
    expect(await screen.findByText("Geri alındı.")).toBeInTheDocument();
    expect(screen.getByText("2026-000123 — Sınıf Kitabı")).toBeInTheDocument();
    expect(screen.queryByText("Geri alma dökümü")).toBeNull();
    // Teslim verme görevli ekranında yoktur.
    expect(screen.queryByRole("button", { name: "Teslim et" })).toBeNull();

    await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_BITIR }));
    expect(screen.getByRole("heading", { level: 2, name: GOREVLI_MASA_BASLIGI })).toBeVisible();
  });
});

describe("GorevliEkrani — sayım okutması ve hizmet arası (F9)", () => {
  it("süren sayım yoksa “Sayım okutmasını aç” görünmez", async () => {
    render(<GorevliEkrani onGecti={vi.fn()} />);
    await vi.waitFor(() => expect(masa.masaDurumu).toHaveBeenCalled());
    expect(GOREVLI_SAYIM_DUGMESI).toBe("Sayım okutmasını aç");
    expect(screen.queryByRole("button", { name: GOREVLI_SAYIM_DUGMESI })).toBeNull();
  });

  it("süren sayımda okutma açılır; yalnız okutma ucu çağrılır, yanıt kişisizdir", async () => {
    const user = userEvent.setup();
    masa.masaDurumu.mockResolvedValue({
      service_pause: false,
      stocktake_scan: { id: 7, round: 1 },
    });
    // Görevli kipinde sunucu yalnız sonuç, ileti, barkod ve eser adını döndürür (madde 24).
    sayimKapisi.gorevliOkut.mockResolvedValue({
      results: [
        {
          code: "bulundu",
          message: "Bulundu.",
          barcode: "2026000123",
          barcode_display: "2026-000123",
          work_title: "Sayım Kitabı",
        },
      ],
    });
    render(<GorevliEkrani onGecti={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: GOREVLI_SAYIM_DUGMESI }));
    expect(screen.getByRole("heading", { level: 1, name: "Görevli Kipi" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 2, name: GOREVLI_SAYIM_BASLIGI })).toBeVisible();
    const kutu = screen.getByLabelText("Kütüphane etiketi");
    await user.type(kutu, "2026000123{Enter}");

    expect(await screen.findByText("Bulundu.")).toBeInTheDocument();
    expect(screen.getByText("2026-000123 — Sayım Kitabı")).toBeInTheDocument();
    expect(sayimKapisi.gorevliOkut).toHaveBeenCalledWith(7, "2026000123");
    // Yönetici uçları (ilerleme, kalemler, durum) görevli kipinde istenmez.
    for (const uc of [
      sayimKapisi.okut,
      sayimKapisi.ilerleme,
      sayimKapisi.kalemler,
      sayimKapisi.durum,
    ]) {
      expect(uc).not.toHaveBeenCalled();
    }
    // Sayımı tamamlamak ve onaylamak görevli ekranında yoktur.
    expect(screen.queryByRole("button", { name: /Sayımı tamamla/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: GOREVLI_DOGRULAMA_BITIR }));
    expect(screen.getByRole("heading", { level: 2, name: GOREVLI_MASA_BASLIGI })).toBeVisible();
  });

  it("hizmet arası masada AÇILIŞTA görünür (madde 26)", async () => {
    masa.masaDurumu.mockResolvedValue({ service_pause: true, stocktake_scan: null });
    render(<GorevliEkrani onGecti={vi.fn()} />);
    expect(
      await screen.findByRole("status", { name: "Sayım için hizmet arası" }),
    ).toHaveTextContent(HIZMET_ARASI_SURUYOR);
  });
});
