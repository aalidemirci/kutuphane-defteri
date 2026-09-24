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

import GorevliEkrani, {
  BEKLEYEN_ANAHTAR_METNI,
  GOREVLI_DOGRULAMA_BASLIGI,
  GOREVLI_DOGRULAMA_BITIR,
  GOREVLI_DOGRULAMA_DUGMESI,
  GOREVLI_EKRANI_METNI,
} from "./GorevliEkrani";

beforeEach(() => {
  vi.clearAllMocks();
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
