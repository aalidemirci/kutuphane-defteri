// Yıl Sonu Raporu (F8; Md. 12/1, E9): etkin yılın raporu yoksa "Raporu hazırla" · rapor
// alanları (sayı, tarih, tespit edilen hususlar — "Kişi adı yazmayın.") · sonlandırma ve
// geri alma (onaylı) · kişisiz sayılar · belge basımı · ders yılı seçici. Uydurma veri.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { akislar } from "../yil/testVerileri";
import { rapor, sayfa } from "./testVerileri";

const ayiklama = vi.hoisted(() => ({
  raporlar: vi.fn(),
  rapor: vi.fn(),
  raporAc: vi.fn(),
  raporGuncelle: vi.fn(),
  raporuSonlandir: vi.fn(),
  sonlandirmayiGeriAl: vi.fn(),
  raporPdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ayiklamaApi: { ...actual.ayiklamaApi, ...ayiklama } };
});
const yil = vi.hoisted(() => ({ akislar: vi.fn() }));
vi.mock("../yil/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../yil/api")>();
  return { ...actual, yilApi: { ...actual.yilApi, ...yil } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import YilSonuRaporuPage, { TESPIT_YARDIMI, YAZ_DONEMI_UYARISI } from "./YilSonuRaporuPage";

function ciz(yol = "/yil-sonu-raporu") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <YilSonuRaporuPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

const SATIR = {
  id: 8,
  school_year: 1,
  school_year_name: "2026-2027",
  document_date: null,
  document_no: "",
  findings: "",
  is_finalized: false,
  finalized_at: null,
  created_at: "2027-06-20T10:00:00+03:00",
};

beforeEach(() => {
  vi.resetAllMocks();
  yil.akislar.mockResolvedValue(
    akislar({ yilSonu: { annual_review: { id: 8, is_finalized: false } } }),
  );
  ayiklama.raporlar.mockResolvedValue(sayfa([SATIR]));
  ayiklama.rapor.mockResolvedValue(rapor());
  ayiklama.raporPdf.mockResolvedValue(new Blob(["%PDF"]));
});

describe("YilSonuRaporuPage", () => {
  it("başlık, Md. 12/1, yan bağlantılar, kişisiz sayılar ve taslak rozeti", async () => {
    ciz();
    expect(screen.getByRole("heading", { level: 1, name: "Yıl Sonu Raporu" })).toBeInTheDocument();
    expect(screen.getByText(/raporla okul müdürlüğüne bildirilir/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Yıl Sonu" })).toHaveAttribute("href", "/yil-sonu");
    expect(await screen.findByText("Taslak")).toBeInTheDocument();
    expect(screen.getByText(TESPIT_YARDIMI)).toBeInTheDocument();
    // 25.09.2026 kullanıcı kararı (F8 ekleri 35 — a): dönem kuralı kalır, ekran uyarır.
    expect(screen.getByText(YAZ_DONEMI_UYARISI)).toBeInTheDocument();
    expect(YAZ_DONEMI_UYARISI).toContain(
      "yeni ders yılı tanımlandıktan sonra sonlandırmanız önerilir; Haziran'da sonlandırırsanız " +
        "yaz aylarındaki işler",
    );
    expect(YAZ_DONEMI_UYARISI).toContain("bu rapora girmez");
    expect(screen.getByText("1.150")).toBeInTheDocument();
    expect(
      screen.getByText(/5 farklı üyeden azının ödünç aldığı grubun sayısı gösterilmez/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Raporu hazırla")).not.toBeInTheDocument();
  });

  it("alanlar kaydedilir; sonlandırma onaylıdır; belge basılır", async () => {
    ayiklama.raporGuncelle.mockResolvedValue(rapor({ document_no: "E-9", findings: "Raflar." }));
    ayiklama.raporuSonlandir.mockResolvedValue(
      rapor({ is_finalized: true, finalized_at: "2027-06-21T10:00:00+03:00" }),
    );
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Taslak");
    await user.type(screen.getByLabelText("Sayı"), "E-9");
    await user.type(screen.getByLabelText("Tespit edilen hususlar"), "Raflar.");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(ayiklama.raporGuncelle).toHaveBeenCalledWith(8, {
        document_no: "E-9",
        document_date: null,
        findings: "Raflar.",
      }),
    );
    expect(await screen.findByText("Rapor kaydedildi.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Raporu sonlandır" }));
    const pencere = await screen.findByRole("dialog", { name: "Rapor sonlandırılsın mı?" });
    await user.click(within(pencere).getByRole("button", { name: "Raporu sonlandır" }));
    await waitFor(() => expect(ayiklama.raporuSonlandir).toHaveBeenCalledWith(8));
    expect(await screen.findByText("Sonlandırıldı · 21.06.2027")).toBeInTheDocument();
    expect(screen.getByLabelText("Sayı")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(ayiklama.raporPdf).toHaveBeenCalledWith(8));
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Yıl-sonu-kütüphane-raporu_/),
    );
  });

  it("kaydedilmemiş tespit metni sonlandırmadan önce kaydedilir; onay dönemi ve bunu söyler", async () => {
    ayiklama.raporGuncelle.mockResolvedValue(rapor({ findings: "Yazılan tespit." }));
    ayiklama.raporuSonlandir.mockResolvedValue(
      rapor({
        findings: "Yazılan tespit.",
        is_finalized: true,
        finalized_at: "2027-06-21T10:00:00+03:00",
      }),
    );
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Taslak");
    await user.type(screen.getByLabelText("Tespit edilen hususlar"), "Yazılan tespit.");
    expect(
      screen.getByText("Kaydedilmemiş değişiklikler belgeye girmez; önce “Kaydet”."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Raporu sonlandır" }));
    const pencere = await screen.findByRole("dialog", { name: "Rapor sonlandırılsın mı?" });
    expect(
      within(pencere).getByText(/07\.09\.2026 – 25\.06\.2027 dönemine aittir/),
    ).toBeInTheDocument();
    expect(
      within(pencere).getByText(/Kaydedilmemiş değişiklikler önce kaydedilir\./),
    ).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Raporu sonlandır" }));
    await waitFor(() => expect(ayiklama.raporuSonlandir).toHaveBeenCalledWith(8));
    expect(ayiklama.raporGuncelle).toHaveBeenCalledWith(8, {
      document_no: "",
      document_date: null,
      findings: "Yazılan tespit.",
    });
    expect(ayiklama.raporGuncelle.mock.invocationCallOrder[0]).toBeLessThan(
      ayiklama.raporuSonlandir.mock.invocationCallOrder[0],
    );
    expect(await screen.findByDisplayValue("Yazılan tespit.")).toBeDisabled();
  });

  it("kazandırılan ile kayıt içi giriş ayrı gösterilir", async () => {
    ciz();
    await screen.findByText("Taslak");
    expect(screen.getByText("Kayıt içi giriş")).toBeInTheDocument();
    expect(screen.getByText("1.100")).toBeInTheDocument();
    expect(
      screen.getByText(/programa aktarım ve sayım fazlası kayıt içi giriştir/),
    ).toBeInTheDocument();
  });

  it("sonlandırma geri alınır", async () => {
    ayiklama.rapor.mockResolvedValue(
      rapor({ is_finalized: true, finalized_at: "2027-06-21T10:00:00+03:00" }),
    );
    ayiklama.sonlandirmayiGeriAl.mockResolvedValue(rapor());
    const user = userEvent.setup();
    ciz();
    await user.click(await screen.findByRole("button", { name: "Sonlandırmayı geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Sonlandırma geri alınsın mı?" });
    await user.click(within(pencere).getByRole("button", { name: "Sonlandırmayı geri al" }));
    await waitFor(() => expect(ayiklama.sonlandirmayiGeriAl).toHaveBeenCalledWith(8));
    expect(await screen.findByText("Sonlandırma geri alındı.")).toBeInTheDocument();
  });

  it("etkin yılın raporu yoksa hazırlanır", async () => {
    yil.akislar.mockResolvedValue(akislar());
    ayiklama.raporlar.mockResolvedValue(sayfa([]));
    ayiklama.raporAc.mockResolvedValue(rapor());
    const user = userEvent.setup();
    ciz();
    expect(
      await screen.findByText("2026-2027 ders yılının raporu henüz hazırlanmadı."),
    ).toBeInTheDocument();
    ayiklama.raporlar.mockResolvedValue(sayfa([SATIR]));
    await user.click(screen.getByRole("button", { name: "Raporu hazırla" }));
    await waitFor(() => expect(ayiklama.raporAc).toHaveBeenCalled());
    expect(await screen.findByText("Yıl sonu raporu hazırlandı.")).toBeInTheDocument();
    await waitFor(() => expect(ayiklama.rapor).toHaveBeenCalledWith(8));
  });

  it("birden çok raporda ders yılı seçilir; hiç rapor ve etkin yıl yoksa boş durum", async () => {
    ayiklama.raporlar.mockResolvedValue(
      sayfa([SATIR, { ...SATIR, id: 6, school_year: 0, school_year_name: "2025-2026" }]),
    );
    const user = userEvent.setup();
    const { unmount } = ciz();
    await screen.findByText("Taslak");
    await user.selectOptions(screen.getByLabelText("Ders yılı"), "6");
    await waitFor(() => expect(ayiklama.rapor).toHaveBeenLastCalledWith(6));
    unmount();

    yil.akislar.mockRejectedValue(new Error("x"));
    ayiklama.raporlar.mockResolvedValue(sayfa([]));
    ciz();
    expect(await screen.findByText("Henüz yıl sonu raporu yok")).toBeInTheDocument();
  });

  it("raporlar okunamazsa hata bandı", async () => {
    ayiklama.raporlar.mockRejectedValue(new ApiError(500, "hata", "Sunucuya ulaşılamadı."));
    ciz();
    expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeInTheDocument();
  });
});
