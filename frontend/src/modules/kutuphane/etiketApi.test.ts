// Etiket istemcisi (F4): yollar backend `labels/urls.py` + `urls.py` (F4-Q bloğu)
// ile BİREBİR; boş süzgeç parametre üretmez; PDF uçları ikili dosya ister ve
// hiçbir "basıldı" gövdesi taşımaz (D10: işaret yalnız onay ucuyla yazılır).
// İndirme adları belge adı + YEREL tarihtir (docs/sozluk.md §3).

import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
  postBlob: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ api: mocks }));

import { bosBarkodDosyaAdi, etiketApi, etiketDosyaAdi, kalibrasyonDosyaAdi } from "./etiketApi";

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

function sonCagri(mock: { mock: { calls: unknown[][] } }): unknown[] {
  return mock.mock.calls[mock.mock.calls.length - 1];
}

describe("etiketApi — şablon ve kalibrasyon", () => {
  it("şablon listesi seçici sınırıyla ve isteğe bağlı türle istenir", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.sablonlar();
    expect(sonCagri(mocks.get)[0]).toBe("/library/label-templates/?limit=200");
    await etiketApi.sablonlar("SPINE");
    expect(sonCagri(mocks.get)[0]).toBe("/library/label-templates/?limit=200&kind=SPINE");
  });

  it("şablon yazma, düzenleme ve silme yolları", async () => {
    const govde = {
      name: "Deneme",
      kind: "BARCODE" as const,
      page_margin_top: 10.7,
      page_margin_left: 4.75,
      label_width: 38.1,
      label_height: 21.2,
      rows: 13,
      cols: 5,
      gutter_x: 2.5,
      gutter_y: 0,
      is_default: false,
    };
    await etiketApi.sablonOlustur(govde);
    expect(mocks.post).toHaveBeenCalledWith("/library/label-templates/", govde);
    await etiketApi.sablonGuncelle(3, { name: "Yeni ad" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/label-templates/3/", { name: "Yeni ad" });
    await etiketApi.sablonSil(3);
    expect(mocks.del).toHaveBeenCalledWith("/library/label-templates/3/");
  });

  it("kalibrasyonlar şablona göre süzülür; yazma yolları", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.kalibrasyonlar(4);
    expect(sonCagri(mocks.get)[0]).toBe("/library/label-calibrations/?limit=200&template=4");
    const govde = { template: 4, printer_name: "Masa yazıcısı", offset_x: 1.5, offset_y: -0.5 };
    await etiketApi.kalibrasyonOlustur(govde);
    expect(mocks.post).toHaveBeenCalledWith("/library/label-calibrations/", govde);
    await etiketApi.kalibrasyonGuncelle(8, { offset_x: 2 });
    expect(mocks.patch).toHaveBeenCalledWith("/library/label-calibrations/8/", { offset_x: 2 });
    await etiketApi.kalibrasyonSil(8);
    expect(mocks.del).toHaveBeenCalledWith("/library/label-calibrations/8/");
  });

  it("kalibrasyon sayfası POST ile PDF ister (kalibrasyonsuz basımda null)", async () => {
    await etiketApi.kalibrasyonSayfasi(4);
    expect(mocks.postBlob).toHaveBeenCalledWith("/library/labels/calibration/", {
      template: 4,
      calibration: null,
    });
    await etiketApi.kalibrasyonSayfasi(4, 8);
    expect(sonCagri(mocks.postBlob)[1]).toEqual({ template: 4, calibration: 8 });
  });
});

describe("etiketApi — kuyruk, özet ve doğrulama", () => {
  it("kuyruk süzgeçleri yalnız doluysa yazılır; offset=0 yazılmaz", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.kuyruk({ kind: "BOTH", order: "CALL_NUMBER", limit: 25, offset: 0 });
    expect(sonCagri(mocks.get)[0]).toBe(
      "/library/labels/queue/?limit=25&kind=BOTH&order=CALL_NUMBER",
    );
    await etiketApi.kuyruk({
      kind: "SPINE",
      order: "IMPORT_ROW",
      section: 2,
      acquisition: 4,
      reservation: 6,
      created_from: "2026-09-01",
      created_to: "2026-09-24",
      limit: 25,
      offset: 50,
    });
    expect(sonCagri(mocks.get)[0]).toBe(
      "/library/labels/queue/?limit=25&offset=50&kind=SPINE&order=IMPORT_ROW&section=2" +
        "&acquisition=4&reservation=6&created_from=2026-09-01&created_to=2026-09-24",
    );
  });

  it("doğrulanmamışlar ve özet; özet kullanıcı eylemi sayılmaz", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.dogrulanmamislar({ limit: 25, section: 3 });
    expect(sonCagri(mocks.get)[0]).toBe("/library/labels/unverified/?limit=25&section=3");
    await etiketApi.ozet();
    expect(sonCagri(mocks.get)).toEqual(["/library/labels/summary/", { etkinlik: false }]);
  });

  it("doğrulama okutması kodu gövdeyle gönderir", async () => {
    await etiketApi.dogrula("2026-000123");
    expect(mocks.post).toHaveBeenCalledWith("/library/labels/verify/", { code: "2026-000123" });
  });
});

describe("etiketApi — basım partileri (D10)", () => {
  it("parti açma, ayrıntı ve durum süzgeci", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.partiler({ status: "PENDING", limit: 25 });
    expect(sonCagri(mocks.get)[0]).toBe("/library/labels/batches/?limit=25&status=PENDING");
    await etiketApi.partiler();
    expect(sonCagri(mocks.get)[0]).toBe("/library/labels/batches/");
    const govde = { kind: "BOTH" as const, template: 1, copies: [3, 4], start_cell: 12 };
    await etiketApi.partiAc(govde);
    expect(mocks.post).toHaveBeenCalledWith("/library/labels/batches/", govde);
    await etiketApi.parti(9);
    expect(sonCagri(mocks.get)[0]).toBe("/library/labels/batches/9/");
  });

  it("PDF ikili dosyadır ve ayrı uçtur; onay, geri alma, vazgeçme ve yeniden basım ayrı uçlardır", async () => {
    await etiketApi.partiPdf(9);
    expect(mocks.getBlob).toHaveBeenCalledWith("/library/labels/batches/9/pdf/");
    // PDF almak hiçbir POST göndermez.
    expect(mocks.post).not.toHaveBeenCalled();

    await etiketApi.partiOnayla(9);
    expect(sonCagri(mocks.post)[0]).toBe("/library/labels/batches/9/confirm/");
    await etiketApi.partiGeriAl(9);
    expect(sonCagri(mocks.post)[0]).toBe("/library/labels/batches/9/revert/");
    await etiketApi.partidenVazgec(9);
    expect(sonCagri(mocks.post)[0]).toBe("/library/labels/batches/9/discard/");
    await etiketApi.yenidenBas(9, { start_cell: 5 });
    expect(sonCagri(mocks.post)).toEqual(["/library/labels/batches/9/reprint/", { start_cell: 5 }]);
    await etiketApi.yenidenBas(9);
    expect(sonCagri(mocks.post)).toEqual(["/library/labels/batches/9/reprint/", {}]);
  });
});

describe("etiketApi — boş barkod aralığı ve hızlı kayıt", () => {
  it("ayırma, liste, ayrıntı, basım işareti ve iptal yolları", async () => {
    mocks.get.mockResolvedValue({ results: [] });
    await etiketApi.araliklar({ limit: 25, offset: 25 });
    expect(sonCagri(mocks.get)[0]).toBe("/library/barcode-reservations/?limit=25&offset=25");
    await etiketApi.aralikAyir(65, "Hikâye rafı");
    expect(mocks.post).toHaveBeenCalledWith("/library/barcode-reservations/", {
      count: 65,
      note: "Hikâye rafı",
    });
    await etiketApi.aralik(2);
    expect(sonCagri(mocks.get)[0]).toBe("/library/barcode-reservations/2/");
    await etiketApi.aralikBasildi(2);
    expect(sonCagri(mocks.post)[0]).toBe("/library/barcode-reservations/2/confirm-print/");
    await etiketApi.aralikBasimGeriAl(2);
    expect(sonCagri(mocks.post)[0]).toBe("/library/barcode-reservations/2/revert-print/");
    await etiketApi.aralikIptal(2, { barcodes: ["2026000101"], reason: "Yırtıldı" });
    expect(sonCagri(mocks.post)).toEqual([
      "/library/barcode-reservations/2/cancel/",
      { barcodes: ["2026000101"], reason: "Yırtıldı" },
    ]);
  });

  it("boş etiket PDF'i sorgu dizesiyle istenir; yalnız seçilen numaralar virgülle gider", async () => {
    await etiketApi.aralikPdf(2, { template: 1 });
    expect(sonCagri(mocks.getBlob)[0]).toBe(
      "/library/barcode-reservations/2/pdf/?template=1&start_cell=1&include_qr=false",
    );
    await etiketApi.aralikPdf(2, {
      template: 1,
      calibration: 3,
      start_cell: 7,
      include_qr: true,
      barcodes: ["2026000101", "2026000102"],
    });
    expect(sonCagri(mocks.getBlob)[0]).toBe(
      "/library/barcode-reservations/2/pdf/?template=1&calibration=3&start_cell=7" +
        "&include_qr=true&barcodes=2026000101%2C2026000102",
    );
  });

  it("etiket ön denetimi kodu kaçışlar; bağlama gövdesi `label_code` taşır", async () => {
    await etiketApi.etiketDenetle("2026-000 101");
    expect(sonCagri(mocks.get)[0]).toBe("/library/barcode-reservations/check/?code=2026-000%20101");
    const govde = { work: 7, acquisition: 3, label_code: "2026000101" };
    await etiketApi.etiketleNushaAc(govde);
    expect(mocks.post).toHaveBeenCalledWith("/library/copies/from-label/", govde);
  });
});

describe("indirme adları", () => {
  it("belge adı + yerel tarih; boş etiketlerde numara aralığı kapsamdır", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    // Yerel 25 Eylül 00:30: UTC'ye göre hâlâ 24 Eylül'dür; ad yerel günü taşır.
    vi.setSystemTime(new Date(2026, 8, 25, 0, 30, 0));

    expect(etiketDosyaAdi("BOTH")).toBe("Sırt-ve-Barkod-Etiketi_25.09.2026.pdf");
    expect(etiketDosyaAdi("SPINE")).toBe("Sırt-Etiketi_25.09.2026.pdf");
    expect(kalibrasyonDosyaAdi()).toBe("Kalibrasyon-Sayfası_25.09.2026.pdf");
    expect(
      bosBarkodDosyaAdi({
        first_barcode_display: "2026-000101",
        last_barcode_display: "2026-000165",
      }),
    ).toBe("Boş-Barkod-Etiketi_2026-000101_2026-000165_25.09.2026.pdf");
  });
});
