// Kişiler → Üyeler (F6): liste, Üyelik penceresi, onaylı "Kartı yenile", nedeni
// zorunlu "Üyeliği sonlandır", ödünç kaydı (profil yasağı dili) ve Üyelik Belgeleri.
// Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { sayfa, uyelik } from "./testVerileri";

const uyelikApiMock = vi.hoisted(() => ({
  uyelikler: vi.fn(),
  uyelikAc: vi.fn(),
  uyelikSil: vi.fn(),
  kartiYenile: vi.fn(),
  sonlandir: vi.fn(),
  oduncKaydi: vi.fn(),
  pusulaPdf: vi.fn(),
  aydinlatmaMetniPdf: vi.fn(),
  masaKartiPdf: vi.fn(),
}));
const okulApiMock = vi.hoisted(() => ({
  listClassSections: vi.fn(),
  listPersonnel: vi.fn(),
}));
const saveBlobMock = vi.hoisted(() => vi.fn());

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  uyelikApi: uyelikApiMock,
}));
vi.mock("../okul/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../okul/api")>()),
  okulApi: okulApiMock,
}));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import UyelerSekmesi from "./UyelerSekmesi";

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <UyelerSekmesi />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  okulApiMock.listClassSections.mockResolvedValue([
    {
      id: 1,
      school_year: 1,
      school_year_name: "2026-2027",
      class_level: 9,
      class_section: "A",
      class_label: "9/A",
    },
  ]);
  okulApiMock.listPersonnel.mockResolvedValue(sayfa([]));
  uyelikApiMock.uyelikler.mockResolvedValue(
    sayfa([
      uyelik({ id: 1, full_name: "Deneme Öğrenci", overdue_loan_count: 2 }),
      uyelik({
        id: 2,
        student: null,
        personnel: 5,
        member_type: "TEACHER",
        full_name: "Ayla Deneme",
        class_label: "",
        card_printed_at: "2026-09-22T09:00:00+03:00",
      }),
    ]),
  );
  uyelikApiMock.oduncKaydi.mockResolvedValue(
    sayfa([
      {
        id: 9,
        barcode: "2026000001",
        barcode_display: "2026-000001",
        work_title: "Deneme Kaynağı",
        loaned_at: "2026-09-01T10:00:00+03:00",
        due_date: "2026-09-16",
        returned_at: null,
        status: "OPEN",
        status_display: "Açık",
        overdue_days: 8,
        has_override: false,
        override_reason_display: "",
        cardless: true,
        cardless_reason_display: "Kart yanında değil",
      },
    ]),
  );
});

describe("UyelerSekmesi", () => {
  it("aktif üyeleri listeler: tür, kart no, gecikme ve kart basımı durumu", async () => {
    ciz();

    const tablo = await screen.findByRole("table");
    expect(within(tablo).getByText("Deneme Öğrenci")).toBeInTheDocument();
    expect(within(tablo).getByText("Öğretmen")).toBeInTheDocument();
    expect(within(tablo).getByText("2 gecikmiş")).toBeInTheDocument();
    expect(within(tablo).getByText("Kart basımı bekliyor")).toBeInTheDocument();
    expect(within(tablo).getByText("Basıldı · 22.09.2026")).toBeInTheDocument();
    expect(uyelikApiMock.uyelikler).toHaveBeenCalledWith(
      expect.objectContaining({ status: "ACTIVE", limit: 25, offset: 0 }),
    );
  });

  it("Kartı yenile onay ister ve onaylanınca yeniler", async () => {
    const user = userEvent.setup();
    uyelikApiMock.kartiYenile.mockResolvedValue(uyelik({ id: 1, card_no: "90000024" }));
    ciz();

    await user.click(await screen.findByRole("button", { name: "Deneme Öğrenci üyeliğini aç" }));
    const pencere = await screen.findByRole("dialog", { name: "Üyelik" });
    await user.click(within(pencere).getByRole("button", { name: "Kartı yenile" }));
    const onay = await screen.findByRole("dialog", { name: "Kart yenilensin mi?" });
    expect(onay).toHaveTextContent("İptal edilmiş kart");
    expect(uyelikApiMock.kartiYenile).not.toHaveBeenCalled();
    await user.click(within(onay).getByRole("button", { name: "Kartı yenile" }));

    await waitFor(() => expect(uyelikApiMock.kartiYenile).toHaveBeenCalledWith(1));
    expect(
      await screen.findByText("Kart yenilendi. Yeni kart basım kuyruğunda."),
    ).toBeInTheDocument();
  });

  it("Üyeliği sonlandır nedeni zorunlu tutar ve kapalı listeden gönderir", async () => {
    const user = userEvent.setup();
    uyelikApiMock.sonlandir.mockResolvedValue(
      uyelik({ id: 1, status: "TERMINATED", terminated_at: "2026-09-24" }),
    );
    ciz();

    await user.click(await screen.findByRole("button", { name: "Deneme Öğrenci üyeliğini aç" }));
    const pencere = await screen.findByRole("dialog", { name: "Üyelik" });
    await user.click(within(pencere).getByRole("button", { name: "Üyeliği sonlandır" }));
    const sonlandir = await screen.findByRole("dialog", { name: "Üyeliği sonlandır" });
    await user.click(within(sonlandir).getByRole("button", { name: "Üyeliği sonlandır" }));
    expect(
      await within(sonlandir).findByText("Sonlandırma nedeni zorunludur."),
    ).toBeInTheDocument();
    expect(uyelikApiMock.sonlandir).not.toHaveBeenCalled();

    await user.selectOptions(
      within(sonlandir).getByLabelText(/Sonlandırma nedeni/),
      "MEMBER_REQUEST",
    );
    await user.click(within(sonlandir).getByRole("button", { name: "Üyeliği sonlandır" }));

    await waitFor(() => expect(uyelikApiMock.sonlandir).toHaveBeenCalledWith(1, "MEMBER_REQUEST"));
  });

  it("üyelik penceresi ödünç kaydını satır satır gösterir, okuma dili kullanmaz", async () => {
    const user = userEvent.setup();
    ciz();

    await user.click(await screen.findByRole("button", { name: "Deneme Öğrenci üyeliğini aç" }));
    const pencere = await screen.findByRole("dialog", { name: "Üyelik" });
    const kayit = await within(pencere).findByRole("region", { name: "Ödünç kaydı" });

    expect(within(kayit).getByText("Deneme Kaynağı")).toBeInTheDocument();
    expect(kayit).toHaveTextContent("8 gün gecikti");
    expect(kayit).toHaveTextContent("kartsız ödünç (Kart yanında değil)");
    expect(pencere.textContent ?? "").not.toMatch(/okuduğu|okuma geçmişi/i);
    // Gecikmiş ödüncü olan üyeye pusula basılabilir.
    expect(within(pencere).getByText("İade Hatırlatma Pusulası")).toBeInTheDocument();
  });

  it("aydınlatma metni başvuru bilgileriyle basılır ve indirilir", async () => {
    const user = userEvent.setup();
    uyelikApiMock.aydinlatmaMetniPdf.mockResolvedValue(new Blob(["%PDF"]));
    ciz();
    await screen.findByRole("table");

    const belgeler = screen.getByRole("region", { name: "Üyelik Belgeleri" });
    await user.type(within(belgeler).getByLabelText("Başvuru adresi"), "  Örnek Mahallesi  ");
    await user.type(within(belgeler).getByLabelText("E-posta ya da telefon"), "ornek@example.org");
    const indir = within(belgeler).getAllByRole("button", { name: "PDF'i indir" })[0];
    await user.click(indir);

    await waitFor(() =>
      expect(uyelikApiMock.aydinlatmaMetniPdf).toHaveBeenCalledWith({
        basvuru_adresi: "Örnek Mahallesi",
        iletisim: "ornek@example.org",
      }),
    );
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^Kütüphane-Aydınlatma-Metni_\d{2}\.\d{2}\.\d{4}\.pdf$/),
    );
  });
});
