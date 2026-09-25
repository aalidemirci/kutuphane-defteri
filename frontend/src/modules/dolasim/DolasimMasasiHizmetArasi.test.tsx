// Dolaşım masasında "Sayım için hizmet arası" (F9; tasarım §9-10). Hizmet arası okul
// kararıdır ve yeni ödüncü ve yeni teslimi durdurur (madde 27); iade hiçbir durumda durmaz.
//
// - Masa hizmet arasını kişisiz masa durumundan (`library-desk-state`) AÇILIŞTA öğrenir —
//   görevli kipinde de (madde 26, 25.09.2026 kullanıcı kararı); sayımın yönetici uçlarını
//   hiç sormaz.
// - Ödünç reddi (`sayim_hizmet_arasi`) şeridi hemen açar ve okutulan kitabın iadesi önerilir.
// - Hizmet arası sürerken üye kartı okutmadan okutulan kitabın iadesi alınır.
// Bütün kişi verileri uydurmadır.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";

const masa = vi.hoisted(() => ({
  kartOku: vi.fn(),
  oduncVer: vi.fn(),
  iadeAl: vi.fn(),
  masaDurumu: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masa } };
});
const sayim = vi.hoisted(() => ({ durum: vi.fn() }));
vi.mock("../sayim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../sayim/api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...sayim } };
});

import { HIZMET_ARASI_SURUYOR } from "../sayim/SayimKarti";
import DolasimMasasi, { IADE_ONERISI, OKUTMA_KUTUSU } from "./DolasimMasasi";

const KART = "94718263";
const KITAP = "2026000123";

function ekranaBas(gorevli: boolean) {
  render(<DolasimMasasi gorevli={gorevli} />);
  return screen.getByLabelText(OKUTMA_KUTUSU);
}

beforeEach(() => {
  vi.resetAllMocks();
  masa.kartOku.mockResolvedValue({
    state: "FOUND",
    message: "Kitabın kütüphane etiketini okutun.",
    member: { full_name: "Deneme Okur", remaining_quota: 3 },
  });
  masa.oduncVer.mockRejectedValue(new ApiError(400, "sayim_hizmet_arasi", HIZMET_ARASI_SURUYOR));
  masa.iadeAl.mockResolvedValue({
    result: "returned",
    kind: "COPY",
    message: "İade alındı.",
    copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
  });
  masa.masaDurumu.mockResolvedValue({ service_pause: false, stocktake_scan: null });
});

describe("Masa — sayım için hizmet arası", () => {
  it.each([
    ["görevli", true],
    ["yönetici", false],
  ])(
    "%s: hizmet arası sürüyorsa şerit AÇILIŞTA görünür (madde 26); iade alınır",
    async (_kip, gorevli) => {
      const user = userEvent.setup();
      masa.masaDurumu.mockResolvedValue({ service_pause: true, stocktake_scan: null });
      const kutu = ekranaBas(gorevli);

      const serit = await screen.findByRole("status", { name: "Sayım için hizmet arası" });
      expect(serit).toHaveTextContent(HIZMET_ARASI_SURUYOR);
      expect(serit).toHaveTextContent("yeni ödünç ve teslim yapılamıyor");
      expect(masa.oduncVer).not.toHaveBeenCalled(); // retten ÖNCE
      await user.type(kutu, `${KITAP}{Enter}`);
      expect(await screen.findByText("İade alındı.")).toBeInTheDocument();
      expect(masa.iadeAl).toHaveBeenCalledWith(KITAP);
      // Sayımın yönetici uçları sorulmaz (görevli kipinde 403 kip olayı doğmaz).
      expect(sayim.durum).not.toHaveBeenCalled();
    },
  );

  it("görevli: ödünç reddiyle şerit hemen açılır, iade önerilir", async () => {
    const user = userEvent.setup();
    const kutu = ekranaBas(true);
    await waitFor(() => expect(masa.masaDurumu).toHaveBeenCalled());
    expect(screen.queryByRole("status", { name: "Sayım için hizmet arası" })).toBeNull();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${KITAP}{Enter}`);

    const serit = await screen.findByRole("status", { name: "Sayım için hizmet arası" });
    expect(serit).toHaveTextContent(HIZMET_ARASI_SURUYOR);
    expect(screen.getByText(IADE_ONERISI)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "İade al" }));
    await waitFor(() => expect(masa.iadeAl).toHaveBeenCalledWith(KITAP));
  });

  it("görevli: hizmet arası kalkınca ilk başarılı ödünçle şerit de kalkar", async () => {
    // F9 düzeltme turu: şerit ilk retten sonra hiç kalkmıyordu; görevli ödüncün kapalı
    // olduğunu sanıp kitap vermeyebilirdi.
    const user = userEvent.setup();
    masa.oduncVer
      .mockRejectedValueOnce(new ApiError(400, "sayim_hizmet_arasi", HIZMET_ARASI_SURUYOR))
      .mockResolvedValueOnce({
        message: "Ödünç verildi.",
        copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
        due_date: "2026-10-12",
        warnings: [],
        member: { full_name: "Deneme Okur", remaining_quota: 2 },
      });
    const kutu = ekranaBas(true);
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${KITAP}{Enter}`);
    expect(
      await screen.findByRole("status", { name: "Sayım için hizmet arası" }),
    ).toBeInTheDocument();

    await user.type(kutu, `${KITAP}{Enter}`);
    expect(await screen.findByText("Ödünç verildi.")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Sayım için hizmet arası" })).toBeNull();
  });

  it("yönetici: hizmet arası yoksa şerit görünmez", async () => {
    ekranaBas(false);
    await waitFor(() => expect(masa.masaDurumu).toHaveBeenCalled());
    expect(screen.queryByRole("status", { name: "Sayım için hizmet arası" })).toBeNull();
  });
});
