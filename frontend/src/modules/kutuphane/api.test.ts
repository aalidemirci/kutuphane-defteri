// Kütüphane API istemcisi: şablon ucu OYS önekiyle çağrılır; indirme adı belge adı +
// YEREL tarihtir (backend `excel_template.template_filename` ile aynı biçim).
//
// Katalog uçlarında sınanan şey SORGU DİZESİDİR: boş süzgeç parametre üretmez
// (sunucu tanınmayan boş değeri süzgeç sanmasın), `offset=0` yazılmaz, metin
// süzgeçleri kırpılıp kaçışlanır ve yollar backend `urls.py` ile birebirdir.
// Sessiz bir yol hatası "kayıt yok" gibi görünür, bu yüzden her uç tek tek pinlenir.

import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getBlob: vi.fn(),
}));

vi.mock("../../lib/api", () => ({ api: mocks }));

import { KATALOG_SABLONU_BELGE_ADI, katalogSablonuDosyaAdi, kutuphaneApi } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("kutuphaneApi.catalogTemplate", () => {
  it("OYS'deki şablon ucunu ikili dosya olarak ister", async () => {
    const blob = new Blob(["xlsx"]);
    mocks.getBlob.mockResolvedValue(blob);

    await expect(kutuphaneApi.catalogTemplate()).resolves.toBe(blob);
    expect(mocks.getBlob).toHaveBeenCalledWith("/library/import/template/");
  });
});

describe("katalogSablonuDosyaAdi", () => {
  it("belge adı + gg.aa.yyyy tarihli, Türkçe harfleri koruyan ad kurar", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 21, 14, 0, 0));

    expect(KATALOG_SABLONU_BELGE_ADI).toBe("Katalog Excel Şablonu");
    expect(katalogSablonuDosyaAdi()).toBe("Katalog-Excel-Şablonu_21.09.2026.xlsx");
  });

  it("tarih YEREL tarihtir (gece yarısından hemen sonra UTC'ye kaymaz)", () => {
    // Yerel 22 Eylül 00:30: UTC+3'te `toISOString()` hâlâ 21 Eylül der.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 22, 0, 30, 0));

    expect(katalogSablonuDosyaAdi()).toBe("Katalog-Excel-Şablonu_22.09.2026.xlsx");
  });
});

/** Son `api.get` çağrısının yolu. */
function sonYol(mock: { mock: { calls: unknown[][] } }): string {
  return String(mock.mock.calls[mock.mock.calls.length - 1][0]);
}

describe("eser uçları", () => {
  it("süzgeçsiz listede yalnız sayfa boyutu gider (boş '?' üretilmez)", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listWorks({ limit: 25, offset: 0 });
    expect(sonYol(mocks.get)).toBe("/library/works/?limit=25");
  });

  it("hiç parametre verilmezse yol sorgusuzdur", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listWorks();
    expect(sonYol(mocks.get)).toBe("/library/works/");
  });

  it("arama kırpılır ve kaçışlanır; süzgeçler backend adlarıyla gider", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listWorks({
      q: "  şiir defteri ",
      section: 4,
      resourceType: "PERIODICAL",
      order: "author",
      limit: 25,
      offset: 50,
    });
    expect(sonYol(mocks.get)).toBe(
      "/library/works/?limit=25&offset=50&q=%C5%9Fiir%20defteri&section=4&resource_type=PERIODICAL&order=author",
    );
  });

  it("yalnız boşluktan oluşan arama parametre üretmez", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listWorks({ q: "   " });
    expect(sonYol(mocks.get)).toBe("/library/works/");
  });

  it("tekil, yaratma, güncelleme ve silme yolları", async () => {
    mocks.get.mockResolvedValue({});
    mocks.post.mockResolvedValue({});
    mocks.patch.mockResolvedValue({});
    mocks.del.mockResolvedValue(undefined);

    await kutuphaneApi.getWork(7);
    expect(sonYol(mocks.get)).toBe("/library/works/7/");

    await kutuphaneApi.createWork({ title: "Ilık Sular" });
    expect(mocks.post).toHaveBeenCalledWith("/library/works/", { title: "Ilık Sular" });

    await kutuphaneApi.updateWork(7, { title: "İnce Kitap" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/works/7/", { title: "İnce Kitap" });

    await kutuphaneApi.deleteWork(7);
    expect(mocks.del).toHaveBeenCalledWith("/library/works/7/");
  });
});

describe("nüsha uçları", () => {
  it("bütün süzgeçler backend adlarıyla ve yalnız doluyken gider", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listCopies({
      work: 7,
      section: 2,
      status: "ON_LOAN",
      barcode: " 2026-000123 ",
      oldRegisterNo: "A-12",
      onlyLoanable: true,
      onlyUnlabeled: true,
      excludeTerminal: true,
      limit: 25,
    });
    expect(sonYol(mocks.get)).toBe(
      "/library/copies/?limit=25&work=7&section=2&status=ON_LOAN&barcode=2026-000123" +
        "&old_register_no=A-12&only_loanable=true&only_unlabeled=true&exclude_terminal=true",
    );
  });

  it("kapalı onay kutuları parametre ÜRETMEZ (sunucu varsayılanı korunur)", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await kutuphaneApi.listCopies({
      onlyLoanable: false,
      onlyUnlabeled: false,
      excludeTerminal: false,
    });
    expect(sonYol(mocks.get)).toBe("/library/copies/");
  });

  it("toplu açma ayrı uca gider (yanıtı sayfalama değil, işlem sonucudur)", async () => {
    mocks.post.mockResolvedValue({ count: 3, results: [] });
    await kutuphaneApi.createCopies({ work: 7, acquisition: 3, count: 3 });
    expect(mocks.post).toHaveBeenCalledWith("/library/copies/bulk/", {
      work: 7,
      acquisition: 3,
      count: 3,
    });
  });

  it("tek nüsha, güncelleme ve silme yolları", async () => {
    mocks.post.mockResolvedValue({});
    mocks.patch.mockResolvedValue({});
    mocks.del.mockResolvedValue(undefined);

    await kutuphaneApi.createCopy({ work: 7, acquisition: 3 });
    expect(mocks.post).toHaveBeenCalledWith("/library/copies/", { work: 7, acquisition: 3 });

    await kutuphaneApi.updateCopy(21, { is_reference: true });
    expect(mocks.patch).toHaveBeenCalledWith("/library/copies/21/", { is_reference: true });

    await kutuphaneApi.deleteCopy(21);
    expect(mocks.del).toHaveBeenCalledWith("/library/copies/21/");
  });
});

describe("bölüm, politika ve özet uçları", () => {
  it("bölüm listesi sayfa sınırını taşır, yazma uçları doğru yola gider", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    mocks.post.mockResolvedValue({});
    mocks.patch.mockResolvedValue({});
    mocks.del.mockResolvedValue(undefined);

    await kutuphaneApi.listSections({ limit: 200 });
    expect(sonYol(mocks.get)).toBe("/library/sections/?limit=200");

    await kutuphaneApi.createSection({
      name: "Tarih",
      dewey_from: "900",
      dewey_to: "999",
      description: "",
      sort_order: 1,
    });
    expect(mocks.post.mock.calls[0][0]).toBe("/library/sections/");

    await kutuphaneApi.updateSection(1, { name: "Tarih" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/sections/1/", { name: "Tarih" });

    await kutuphaneApi.deleteSection(1);
    expect(mocks.del).toHaveBeenCalledWith("/library/sections/1/");
  });

  it("politika PUT ile, özet GET ile okunur", async () => {
    mocks.get.mockResolvedValue({});
    mocks.put.mockResolvedValue({});

    await kutuphaneApi.getPolicy();
    expect(sonYol(mocks.get)).toBe("/library/policy/");

    await kutuphaneApi.updatePolicy({ max_loans_student: 2 });
    expect(mocks.put).toHaveBeenCalledWith("/library/policy/", { max_loans_student: 2 });

    await kutuphaneApi.getStats();
    expect(sonYol(mocks.get)).toBe("/library/stats/");
  });
});

describe("edinim, komisyon ve bağış uçları", () => {
  it("süzgeçler yalnız doluyken gider", async () => {
    mocks.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });

    await kutuphaneApi.listAcquisitions({ method: "DONATION", limit: 25 });
    expect(sonYol(mocks.get)).toBe("/library/acquisitions/?limit=25&method=DONATION");

    await kutuphaneApi.listAcquisitions({ method: "" });
    expect(sonYol(mocks.get)).toBe("/library/acquisitions/");

    await kutuphaneApi.listCommissionDecisions({ decisionType: "DONATION_REVIEW", limit: 200 });
    expect(sonYol(mocks.get)).toBe(
      "/library/commission-decisions/?limit=200&decision_type=DONATION_REVIEW",
    );

    await kutuphaneApi.listDonationIntakes({ status: "PENDING" });
    expect(sonYol(mocks.get)).toBe("/library/donation-intakes/?status=PENDING");
  });

  it("edinim ve komisyon yazma uçları", async () => {
    mocks.post.mockResolvedValue({});
    mocks.patch.mockResolvedValue({});
    mocks.del.mockResolvedValue(undefined);

    await kutuphaneApi.createAcquisition({ method: "PURCHASE", date: "2026-09-10" });
    expect(mocks.post.mock.calls[0][0]).toBe("/library/acquisitions/");
    await kutuphaneApi.updateAcquisition(3, { notes: "not" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/acquisitions/3/", { notes: "not" });
    await kutuphaneApi.deleteAcquisition(3);
    expect(mocks.del).toHaveBeenCalledWith("/library/acquisitions/3/");

    await kutuphaneApi.createCommissionDecision({
      decision_type: "WEEDING",
      decision_date: "2026-09-15",
      chair_name: "Mehmet Demir",
    });
    expect(mocks.post.mock.calls[1][0]).toBe("/library/commission-decisions/");
    await kutuphaneApi.updateCommissionDecision(5, { decision_no: "2026/5" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/commission-decisions/5/", {
      decision_no: "2026/5",
    });
    await kutuphaneApi.deleteCommissionDecision(5);
    expect(mocks.del).toHaveBeenCalledWith("/library/commission-decisions/5/");
  });

  it("bağış ön kaydının alt kaynakları ön kaydın altındadır", async () => {
    mocks.get.mockResolvedValue({});
    mocks.post.mockResolvedValue({});
    mocks.patch.mockResolvedValue({});
    mocks.del.mockResolvedValue(undefined);

    await kutuphaneApi.getDonationIntake(11);
    expect(sonYol(mocks.get)).toBe("/library/donation-intakes/11/");

    await kutuphaneApi.createDonationIntake({ received_date: "2026-09-18" });
    expect(mocks.post.mock.calls[0][0]).toBe("/library/donation-intakes/");

    await kutuphaneApi.updateDonationIntake(11, { donor_name: "Fatma Aydın" });
    expect(mocks.patch).toHaveBeenCalledWith("/library/donation-intakes/11/", {
      donor_name: "Fatma Aydın",
    });

    await kutuphaneApi.addDonationItem(11, { title: "Ilık Sular" });
    expect(mocks.post.mock.calls[1][0]).toBe("/library/donation-intakes/11/items/");

    await kutuphaneApi.updateDonationItem(11, 31, { copies: 2 });
    expect(mocks.patch).toHaveBeenCalledWith("/library/donation-intakes/11/items/31/", {
      copies: 2,
    });

    await kutuphaneApi.removeDonationItem(11, 31);
    expect(mocks.del).toHaveBeenCalledWith("/library/donation-intakes/11/items/31/");

    await kutuphaneApi.deleteDonationIntake(11);
    expect(mocks.del).toHaveBeenCalledWith("/library/donation-intakes/11/");
  });

  it("karar ve iptal uçları ön kaydın altındadır; ret gerekçeleri EŞLEMEDİR", async () => {
    mocks.post.mockResolvedValue({});

    await kutuphaneApi.applyDonationDecision(11, {
      commission_decision: 5,
      accepted_ids: [31],
      rejected: { "32": "Yıpranmış" },
    });
    expect(mocks.post).toHaveBeenCalledWith("/library/donation-intakes/11/decision/", {
      commission_decision: 5,
      accepted_ids: [31],
      rejected: { "32": "Yıpranmış" },
    });

    await kutuphaneApi.cancelDonationIntake(11, "Bağış geri verildi");
    expect(mocks.post).toHaveBeenCalledWith("/library/donation-intakes/11/cancel/", {
      reason: "Bağış geri verildi",
    });
  });
});
