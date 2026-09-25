// Teslimden geri alma okutması (F7, U11, §4.4). Görevli kipinde teslim alanın kimliği
// ve evrak YOK; yönetici kipinde satırda teslim alan ve belge no, bu ekranda geri
// alınanların dökümü (E15). Okutma bir olaydır: her sonuç iletisiyle gösterilir.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { GeriAlmaSonucu } from "./api";

const teslim = vi.hoisted(() => ({
  geriAl: vi.fn(),
  geriAlmaDokumuPdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslim } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import GeriAlmaOkutmasi, { GERI_ALMA_KUTUSU } from "./GeriAlmaOkutmasi";

const KITAP = "2026000123";

function geriAlindi(ek: Partial<GeriAlmaSonucu> = {}): GeriAlmaSonucu {
  return {
    result: "returned",
    kind: "COPY",
    message: "Geri alındı.",
    copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Sınıf Kitabı" },
    delivery: {
      id: 41,
      recipient_kind: "SECTION",
      recipient_kind_display: "Sınıf kitaplığı",
      recipient_label: "3/A",
      delivered_on: "2026-09-21",
      expected_return: "2027-06-18",
      document_no: "2026/4",
      returned_at: "2026-09-25T10:00:00+03:00",
    },
    ...ek,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  teslim.geriAl.mockResolvedValue(geriAlindi());
  teslim.geriAlmaDokumuPdf.mockResolvedValue(new Blob(["%PDF"]));
});

describe("GeriAlmaOkutmasi — görevli kipi", () => {
  it("okutulan kitap geri alınır; teslim alanın kimliği ve evrak görünmez", async () => {
    const user = userEvent.setup();
    // Sunucu görevli kipinde `delivery` göndermez; gelse bile ekran yazmaz.
    render(<GeriAlmaOkutmasi gorevli />);
    const kutu = screen.getByLabelText(GERI_ALMA_KUTUSU);
    expect(kutu).toHaveFocus();

    await user.type(kutu, `${KITAP}{Enter}`);

    const durum = await screen.findByRole("status");
    expect(durum).toHaveTextContent("Geri alındı.");
    expect(durum).toHaveTextContent("2026-000123 — Sınıf Kitabı");
    expect(durum).not.toHaveTextContent("3/A");
    expect(durum).not.toHaveTextContent("2026/4");
    expect(screen.getByText("Bu ekranda geri alınan: 1")).toBeInTheDocument();
    expect(screen.queryByText("Geri alma dökümü")).not.toBeInTheDocument();
    expect(teslim.geriAl).toHaveBeenCalledWith(KITAP);
  });

  it("teslimde olmayan ve reddedilen kodun iletisi gösterilir, sayaç artmaz", async () => {
    const user = userEvent.setup();
    teslim.geriAl
      .mockResolvedValueOnce(
        geriAlindi({
          result: "not_delivered",
          message: "Bu kitap teslimde değil (Rafta).",
          delivery: null,
        }),
      )
      .mockResolvedValueOnce({
        result: "rejected",
        kind: "ISBN",
        message: "Bu bir ISBN barkodu.",
        copy: null,
      });
    render(<GeriAlmaOkutmasi gorevli />);
    const kutu = screen.getByLabelText(GERI_ALMA_KUTUSU);

    await user.type(kutu, `${KITAP}{Enter}`);
    expect(await screen.findByText("Bu kitap teslimde değil (Rafta).")).toBeInTheDocument();
    await user.type(kutu, "9789750812345{Enter}");
    expect(await screen.findByText("Bu bir ISBN barkodu.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Okutulan: 9789750812345");
    expect(screen.getByText("Bu ekranda geri alınan: 0")).toBeInTheDocument();
    // Önceki okutma listede kalır.
    expect(screen.getByRole("list", { name: "Son okutmalar" })).toHaveTextContent(
      "Bu kitap teslimde değil (Rafta).",
    );
  });

  it("sunucu hatası okutmayı düşürmez; ileti gösterilir", async () => {
    const user = userEvent.setup();
    teslim.geriAl.mockRejectedValueOnce(new Error("ağ yok"));
    render(<GeriAlmaOkutmasi gorevli />);
    await user.type(screen.getByLabelText(GERI_ALMA_KUTUSU), `${KITAP}{Enter}`);
    expect(
      await screen.findByText("Geri alma kaydedilemedi; kitabı yeniden okutun."),
    ).toBeInTheDocument();
  });
});

describe("GeriAlmaOkutmasi — yönetici kipi", () => {
  it("satırda teslim alan ve belge no; döküm geri alınan satırlarla basılır", async () => {
    const user = userEvent.setup();
    const geriAlindiBildirimi = vi.fn();
    render(<GeriAlmaOkutmasi onGeriAlindi={geriAlindiBildirimi} />);
    const dokum = screen.getByRole("button", { name: "PDF'i indir" });
    expect(dokum).toBeDisabled();

    await user.type(screen.getByLabelText(GERI_ALMA_KUTUSU), `${KITAP}{Enter}`);

    const durum = await screen.findByRole("status");
    expect(durum).toHaveTextContent("Sınıf kitaplığı: 3/A · belge no 2026/4 · teslim 21.09.2026");
    expect(geriAlindiBildirimi).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(dokum).toBeEnabled());
    await user.click(dokum);
    expect(teslim.geriAlmaDokumuPdf).toHaveBeenCalledWith({ deliveryIds: [41] });
    await waitFor(() => expect(saveBlobMock).toHaveBeenCalled());
    expect(saveBlobMock.mock.calls[0][1]).toMatch(/^Geri-alma-dökümü_\d{2}\.\d{2}\.\d{4}\.pdf$/);
  });
});
