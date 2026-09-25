// Ayıklama, nadir eser ve yıl sonu raporu istemcisi: uç yolları, sorgu dizesi, gövdeler,
// belge biçimi (`?kind=xlsx` — `?format=` DRF'e ayrılmıştır) ve adlar.

import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
}));

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  api: apiMock,
}));

import {
  ayiklamaApi,
  belgeDosyaAdi,
  GEREKCE_TR,
  KALEM_DURUMU_TR,
  TEKLIF_DURUMU_TR,
  TMY_YOLU_TR,
  teklifAdi,
  teklifAdresi,
} from "./api";

beforeEach(() => {
  vi.clearAllMocks();
  for (const f of [apiMock.get, apiMock.post, apiMock.patch, apiMock.del]) f.mockResolvedValue({});
  apiMock.getBlob.mockResolvedValue(new Blob());
});

describe("ayiklamaApi — ayıklama", () => {
  it("kurallar ve aday sorgusu (TR arama kodlanır; öneri süzgeci yok — F8 ekleri 34)", async () => {
    await ayiklamaApi.kurallar();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/weeding/rules/");
    await ayiklamaApi.adaylar();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/weeding/candidates/");
    await ayiklamaApi.adaylar({ q: "Şiir", section: 4, limit: 20, offset: 40 });
    expect(apiMock.get).toHaveBeenLastCalledWith(
      "/library/weeding/candidates/?q=%C5%9Eiir&section=4&limit=20&offset=40",
    );
  });

  it("teklif uçları ve geçişler", async () => {
    await ayiklamaApi.teklifler({ status: "DRAFT", limit: 25, offset: 25 });
    expect(apiMock.get).toHaveBeenLastCalledWith(
      "/library/weeding-batches/?status=DRAFT&limit=25&offset=25",
    );
    await ayiklamaApi.teklifler();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/weeding-batches/");
    await ayiklamaApi.teklif(3);
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/weeding-batches/3/");
    await ayiklamaApi.teklifAc();
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/", { notes: "" });
    await ayiklamaApi.teklifGuncelle(3, "not");
    expect(apiMock.patch).toHaveBeenLastCalledWith("/library/weeding-batches/3/", {
      notes: "not",
    });
    await ayiklamaApi.teklifSil(3);
    expect(apiMock.del).toHaveBeenLastCalledWith("/library/weeding-batches/3/");
    await ayiklamaApi.kalemEkle(3, { reason: "WORN", barcodes: ["2026-000101"], copies: [7] });
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/items/", {
      reason: "WORN",
      barcodes: ["2026-000101"],
      copies: [7],
    });
    await ayiklamaApi.kalemGuncelle(3, 11, { transfer_target: "Deneme Okulu" });
    expect(apiMock.patch).toHaveBeenLastCalledWith("/library/weeding-batches/3/items/11/", {
      transfer_target: "Deneme Okulu",
    });
    await ayiklamaApi.kalemCikar(3, 11);
    expect(apiMock.del).toHaveBeenLastCalledWith("/library/weeding-batches/3/items/11/");
    await ayiklamaApi.sun(3);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/submit/");
    await ayiklamaApi.geriCek(3);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/withdraw/");
    await ayiklamaApi.kararBagla(3, 9, { "11": "Kullanılıyor." });
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/decision/", {
      commission_decision: 9,
      kept: { "11": "Kullanılıyor." },
    });
    await ayiklamaApi.kararBagla(3, 9);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/decision/", {
      commission_decision: 9,
      kept: {},
    });
    await ayiklamaApi.onayla(3, { approved_by_name: "Deneme", approved_on: "2027-06-10" });
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/approve/", {
      approved_by_name: "Deneme",
      approved_on: "2027-06-10",
    });
    await ayiklamaApi.uygula(3);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/apply/");
    await ayiklamaApi.iptalEt(3, "Yanlış açıldı.");
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/weeding-batches/3/cancel/", {
      reason: "Yanlış açıldı.",
    });
  });

  it("belgeler: liste, PDF ve devir listesinin Excel'i (?kind=xlsx)", async () => {
    await ayiklamaApi.belgeler(3);
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/weeding-batches/3/documents/");
    await ayiklamaApi.belge(3, "ayiklama-tutanagi");
    expect(apiMock.getBlob).toHaveBeenLastCalledWith(
      "/library/weeding-batches/3/documents/ayiklama-tutanagi/",
    );
    await ayiklamaApi.belge(3, "devir-listesi", "xlsx");
    expect(apiMock.getBlob).toHaveBeenLastCalledWith(
      "/library/weeding-batches/3/documents/devir-listesi/?kind=xlsx",
    );
  });
});

describe("ayiklamaApi — nadir eserler, yıl sonu raporu, bağış listesi", () => {
  it("nadir eser uçları", async () => {
    await ayiklamaApi.nadirNushalar({ unsent: true, limit: 200 });
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/rare-copies/?unsent=1&limit=200");
    await ayiklamaApi.nadirNushalar();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/rare-copies/");
    await ayiklamaApi.listeler({ limit: 25, offset: 25 });
    expect(apiMock.get).toHaveBeenLastCalledWith(
      "/library/rare-works-submissions/?limit=25&offset=25",
    );
    await ayiklamaApi.liste(5);
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/");
    await ayiklamaApi.listeAc();
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/rare-works-submissions/", {});
    await ayiklamaApi.listeGuncelle(5, { commission_decision: 9 });
    expect(apiMock.patch).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/", {
      commission_decision: 9,
    });
    await ayiklamaApi.listeSil(5);
    expect(apiMock.del).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/");
    await ayiklamaApi.listeyeEkle(5, { copies: [201] });
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/items/", {
      copies: [201],
    });
    await ayiklamaApi.listedenCikar(5, 51);
    expect(apiMock.del).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/items/51/");
    await ayiklamaApi.gonderildi(5, { sent_on: "2027-06-10", sent_document_no: "E-1" });
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/send/", {
      sent_on: "2027-06-10",
      sent_document_no: "E-1",
    });
    await ayiklamaApi.listePdf(5);
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/rare-works-submissions/5/pdf/");
  });

  it("yıl sonu raporu uçları", async () => {
    await ayiklamaApi.raporlar();
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/annual-reviews/?limit=50");
    await ayiklamaApi.rapor(8);
    expect(apiMock.get).toHaveBeenLastCalledWith("/library/annual-reviews/8/");
    await ayiklamaApi.raporAc();
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/annual-reviews/", {});
    await ayiklamaApi.raporAc(2);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/annual-reviews/", { school_year: 2 });
    await ayiklamaApi.raporGuncelle(8, { findings: "Tespit." });
    expect(apiMock.patch).toHaveBeenLastCalledWith("/library/annual-reviews/8/", {
      findings: "Tespit.",
    });
    await ayiklamaApi.raporuSonlandir(8);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/annual-reviews/8/finalize/");
    await ayiklamaApi.sonlandirmayiGeriAl(8);
    expect(apiMock.post).toHaveBeenLastCalledWith("/library/annual-reviews/8/reopen/");
    await ayiklamaApi.raporPdf(8);
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/annual-reviews/8/pdf/");
    await ayiklamaApi.bagisListesiPdf(4);
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/donation-intakes/4/pdf/");
    await ayiklamaApi.bagisSonucuPdf(4);
    expect(apiMock.getBlob).toHaveBeenLastCalledWith("/library/donation-intakes/4/result-pdf/");
  });
});

describe("adlar", () => {
  it("kod listeleri backend etiketleriyle birebir (sözlük §4.14)", () => {
    expect(Object.values(TEKLIF_DURUMU_TR)).toEqual([
      "Taslak",
      "Komisyona sunuldu",
      "Komisyon kararı bağlandı",
      "Harcama yetkilisi onayladı",
      "Uygulandı",
      "İptal edildi",
    ]);
    expect(Object.values(KALEM_DURUMU_TR)).toContain("Komisyon ayıklanmasına karar vermedi");
    expect(GEREKCE_TR.LEVEL_MISMATCH).toBe("Kurumun düzeyine uygun değil");
    expect(TMY_YOLU_TR.TMY_24_2).toBe("Başka bir MEB okuluna devir (TMY 24/2)");
  });

  it("teklif adı iç kimlik taşımaz; adres ve indirme adı", () => {
    expect(
      teklifAdi({ school_year_name: "2026-2027", created_at: "2027-06-01T10:00:00+03:00" }),
    ).toBe("Ayıklama teklifi · 2026-2027 · 01.06.2027");
    expect(teklifAdresi(3)).toBe("/katalog/ayiklama?teklif=3");
    expect(belgeDosyaAdi("Devir listesi", "xlsx")).toMatch(
      /^Devir-listesi_\d{2}\.\d{2}\.\d{4}\.xlsx$/,
    );
  });
});
