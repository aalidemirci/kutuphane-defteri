// Kayıp ve Hasar sayfası (F7, Md. 19, D3): çözülmemiş dosyalar varsayılan; satır dosya
// ayrıntısını açar; `?dosya=` doğrudan açar; dosya açma pencereleri; tahsilat dili yok.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { dosyaVerisi, sayfa } from "../../test/teslimVerileri";

const kayip = vi.hoisted(() => ({ listele: vi.fn(), getir: vi.fn(), ac: vi.fn() }));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayip } };
});
const masa = vi.hoisted(() => ({ nushaDurumu: vi.fn(), uyeAra: vi.fn() }));
vi.mock("../dolasim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dolasim/api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masa } };
});

import KayipHasarPage, { KAYIP_HASAR_BASLIGI, OKULUN_ACIK_ISI_ETIKETI } from "./KayipHasarPage";

function ciz(yol = "/dolasim/kayip-hasar") {
  render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <KayipHasarPage />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  kayip.listele.mockResolvedValue(sayfa([dosyaVerisi()]));
  kayip.getir.mockResolvedValue(dosyaVerisi({ id: 9, barcode_display: "2026-000999" }));
});

describe("KayipHasarPage", () => {
  it("başlık, açıklama ve çözülmemiş dosyalar; tahsilat dili yok", async () => {
    ciz();
    expect(
      screen.getByRole("heading", { level: 1, name: KAYIP_HASAR_BASLIGI }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Program tahsilat yapmaz/)).toBeInTheDocument();
    expect(await screen.findByText("Deneme Okur · 9/A")).toBeInTheDocument();
    expect(kayip.listele).toHaveBeenCalledWith(
      expect.objectContaining({ open: true, caseType: "", resolution: "", offset: 0 }),
    );
    expect(document.body).not.toHaveTextContent(/borç|ceza|zayi/i);
  });

  it("satıra tıklanınca dosya ayrıntısı açılır", async () => {
    const user = userEvent.setup();
    ciz();
    await user.click(
      await screen.findByRole("button", { name: "2026-000123 numaralı nüshanın dosyasını aç" }),
    );
    expect(screen.getByRole("dialog", { name: "Kayıp dosyası" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kapat" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("?dosya= adresi dosyayı doğrudan açar", async () => {
    ciz("/dolasim/kayip-hasar?dosya=9");
    await waitFor(() => expect(kayip.getir).toHaveBeenCalledWith(9));
    const pencere = await screen.findByRole("dialog", { name: "Kayıp dosyası" });
    expect(pencere).toHaveTextContent("2026-000999");
  });

  it("bütün dosyalar görünümünde çözüm süzgeci çıkar", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Deneme Okur · 9/A");
    expect(screen.queryByLabelText("Çözüm")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Görünüm"), "tumu");
    await user.selectOptions(screen.getByLabelText("Çözüm"), "REPAIRED");
    await user.selectOptions(screen.getByLabelText("Tür"), "DAMAGED");
    await waitFor(() =>
      expect(kayip.listele).toHaveBeenLastCalledWith(
        expect.objectContaining({ open: false, resolution: "REPAIRED", caseType: "DAMAGED" }),
      ),
    );
  });

  it("ilkokul ve ortaokulda çözüm süzgecinde ve açıklamada bedel yolu yoktur (Md. 19)", async () => {
    const user = userEvent.setup();
    kayip.listele.mockResolvedValue({ ...sayfa([dosyaVerisi()]), price_options_available: false });
    ciz();
    await screen.findByText("Deneme Okur · 9/A");
    expect(screen.getByText(/kütüphaneyle açık işi olarak kalır/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/yükümlülü|piyasa bedeli/i);
    await user.selectOptions(screen.getByLabelText("Görünüm"), "tumu");
    const secenekler = within(screen.getByLabelText("Çözüm"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(secenekler).toContain("Bulundu");
    expect(secenekler).toContain("Kayba dönüştü");
    for (const bedel of [
      "Bedel belirlendi",
      "Bedel teslim alındı",
      "Bedelle aynısı alındı",
      "Bedelle başka eser alındı",
    ])
      expect(secenekler).not.toContain(bedel);
    expect(document.body).not.toHaveTextContent(/bedel teslim alınınca/);
  });

  it("ortaöğretimde bedel yolları süzgeçte ve açıklamada görünür (boş listede de)", async () => {
    const user = userEvent.setup();
    kayip.listele.mockResolvedValue({ ...sayfa([]), price_options_available: true });
    ciz();
    expect(
      await screen.findByText(/piyasa bedeli yalnız kaydedilir \(Yönetmelik Md\. 19\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/bedel teslim alınınca kişinin açık işi biter, dosya okulun açık işi/),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Görünüm"), "tumu");
    const secenekler = within(screen.getByLabelText("Çözüm"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(secenekler).toEqual(
      expect.arrayContaining(["Bedel belirlendi", "Bedel teslim alındı", "Bedelle aynısı alındı"]),
    );
  });

  it("bedeli teslim alınmış dosya çözülmemişlerde “Okulun açık işi” notuyla durur", async () => {
    kayip.listele.mockResolvedValue({
      ...sayfa([
        dosyaVerisi(),
        dosyaVerisi({
          id: 6,
          barcode_display: "2026-000124",
          resolution: "PRICE_RECEIVED",
          resolution_display: "Bedel teslim alındı",
          market_price: "80.00",
          is_person_open_work: false,
        }),
      ]),
      price_options_available: true,
    });
    ciz();
    const satir = await screen.findByRole("button", {
      name: "2026-000124 numaralı nüshanın dosyasını aç",
    });
    expect(satir).toHaveTextContent("Bedel teslim alındı");
    expect(within(satir).getByText(OKULUN_ACIK_ISI_ETIKETI)).toBeInTheDocument();
    // Kişinin açık işi olan dosyada not yoktur.
    expect(screen.getAllByText(OKULUN_ACIK_ISI_ETIKETI)).toHaveLength(1);
  });

  it("dosya açma düğmeleri pencereyi açar; açılan dosya ayrıntıda gösterilir", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValue({
      kind: "COPY",
      message: "Rafta.",
      copy: {
        id: 11,
        barcode: "2026000123",
        barcode_display: "2026-000123",
        work_title: "Deneme Kitabı",
        status: "AVAILABLE",
        status_display: "Rafta",
      },
      loan: null,
    });
    kayip.ac.mockResolvedValue(
      dosyaVerisi({
        id: 12,
        case_type: "DAMAGED",
        case_type_display: "Hasar",
        copy_status: "AVAILABLE",
      }),
    );
    ciz();
    await user.click(screen.getByRole("button", { name: "Hasar dosyası aç" }));
    const pencere = screen.getByRole("dialog", { name: "Hasar dosyası açılsın mı?" });
    await user.type(within(pencere).getByLabelText("Kütüphane etiketi"), "2026000123{Enter}");
    await within(pencere).findByText("Durum: Rafta");
    await user.click(within(pencere).getByRole("button", { name: "Hasar dosyası aç" }));
    expect(await screen.findByRole("dialog", { name: "Hasar dosyası" })).toBeInTheDocument();
    expect(screen.getByText("Hasar dosyası açıldı.")).toBeInTheDocument();
  });

  it("dosya yoksa boş durum", async () => {
    kayip.listele.mockResolvedValue(sayfa([]));
    ciz();
    expect(
      await screen.findByText("Çözülmemiş kayıp ya da hasar dosyası yok."),
    ).toBeInTheDocument();
  });
});
