// Etiketler → Doğrulama Okutması (F4, tasarım §7.2 ve §7.3 BarcodeInput) —
// sabitlenen davranışlar:
//
//   1) Kutu kendiliğinden odaklanır; okutma anında boşalır ve odak kutuda kalır.
//   2) Sonuç beklenirken gelen okutma SIRAYA alınır: hiçbir kod kaybolmaz, istekler
//      yarışmaz (ikinci istek birinci bitince gider).
//   3) Sunucunun iletisi olduğu gibi gösterilir (ISBN barkodu, bağlanmamış boş
//      etiket…); doğrulanan etiket doğrulanmamışlar listesini tazeler.
//   4) Odak kutudan çıkarsa görünür uyarı çıkar; yazı alanı dışında basılan
//      rakam (okuyucu da klavyedir) odağı kutuya döndürür.

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { dogrulamaSonucu, kuyrukNushasi } from "../../test/etiketVerileri";
import { sayfa } from "../../test/kutuphaneVerileri";
import type { DogrulamaSonucu } from "./etiketApi";

const etiket = vi.hoisted(() => ({
  dogrula: vi.fn(),
  dogrulanmamislar: vi.fn(),
}));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

import DogrulamaOkutmasi from "./DogrulamaOkutmasi";

beforeEach(() => {
  vi.clearAllMocks();
  etiket.dogrula.mockResolvedValue(dogrulamaSonucu());
  etiket.dogrulanmamislar.mockResolvedValue(
    sayfa([kuyrukNushasi({ label_printed_at: "2026-09-24T11:30:00+03:00" })]),
  );
});

/** Ekranı kurar ve doğrulanmamışlar listesinin ilk yüklemesini bekler. */
async function ekranaBas() {
  const onDegisti = vi.fn();
  await act(async () => {
    render(<DogrulamaOkutmasi tazeleme={0} onDegisti={onDegisti} />);
  });
  return onDegisti;
}

describe("Doğrulama Okutması", () => {
  it("okutulan etiket doğrulanır; kutu boşalır ve odakta kalır", async () => {
    const user = userEvent.setup();
    const onDegisti = await ekranaBas();
    const kutu = screen.getByLabelText("Kütüphane etiketi");
    expect(kutu).toHaveFocus();
    expect(await screen.findByText("Doğrulanmamış Etiketler: 1")).toBeInTheDocument();

    await user.type(kutu, "2026000123{Enter}");

    expect(kutu).toHaveValue("");
    expect(await screen.findByText("Etiket doğrulandı.")).toBeInTheDocument();
    expect(screen.getByText("2026-000123 — Şiir Defteri")).toBeInTheDocument();
    expect(etiket.dogrula).toHaveBeenCalledWith("2026000123");
    expect(kutu).toHaveFocus();
    expect(screen.getByText(/Bu ekranda doğrulanan: 1/)).toBeInTheDocument();
    // Doğrulanan etiket listeyi ve sayaçları tazeler.
    await waitFor(() => expect(etiket.dogrulanmamislar).toHaveBeenCalledTimes(2));
    expect(onDegisti).toHaveBeenCalled();
  });

  it("yanlış kod türü sunucunun iletisiyle reddedilir; liste tazelenmez", async () => {
    const user = userEvent.setup();
    etiket.dogrula.mockResolvedValue(
      dogrulamaSonucu({
        result: "rejected",
        kind: "ISBN",
        message: "Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.",
        copy: null,
      }),
    );
    const onDegisti = await ekranaBas();

    await user.type(screen.getByLabelText("Kütüphane etiketi"), "9789750812345{Enter}");

    expect(
      await screen.findByText("Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."),
    ).toBeInTheDocument();
    expect(screen.getByText("Okutulan: 9789750812345")).toBeInTheDocument();
    expect(onDegisti).not.toHaveBeenCalled();
  });

  it("sonuç beklenirken gelen okutma sıraya alınır; hiçbir kod kaybolmaz", async () => {
    const user = userEvent.setup();
    const bekleyen: Array<(sonuc: DogrulamaSonucu) => void> = [];
    etiket.dogrula.mockImplementation(
      () =>
        new Promise<DogrulamaSonucu>((coz) => {
          bekleyen.push(coz);
        }),
    );
    await ekranaBas();
    const kutu = screen.getByLabelText("Kütüphane etiketi");

    await user.type(kutu, "2026000123{Enter}");
    await user.type(kutu, "2026000124{Enter}");

    // İkinci istek birinci bitmeden gitmez.
    expect(etiket.dogrula).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/sırada bekleyen okutma: 1/)).toBeInTheDocument();

    bekleyen[0](dogrulamaSonucu());
    await waitFor(() => expect(etiket.dogrula).toHaveBeenCalledTimes(2));
    expect(etiket.dogrula.mock.calls[1][0]).toBe("2026000124");
    bekleyen[1](
      dogrulamaSonucu({ result: "already_verified", message: "Bu etiket daha önce doğrulandı." }),
    );
    expect(await screen.findByText("Bu etiket daha önce doğrulandı.")).toBeInTheDocument();
    // Önceki okutma listede kalır.
    expect(screen.getByRole("list", { name: "Son okutmalar" })).toHaveTextContent(
      "Etiket doğrulandı.",
    );
  });

  it("sunucuya ulaşılamazsa okutmanın yinelenmesi istenir", async () => {
    const user = userEvent.setup();
    etiket.dogrula.mockRejectedValue(new ApiError(503, "503", "Sunucu yanıt vermedi."));
    await ekranaBas();

    await user.type(screen.getByLabelText("Kütüphane etiketi"), "2026000123{Enter}");

    expect(await screen.findByText("Sunucu yanıt vermedi.")).toBeInTheDocument();
  });

  it("boş Enter istek göndermez", async () => {
    const user = userEvent.setup();
    await ekranaBas();

    await user.type(screen.getByLabelText("Kütüphane etiketi"), "   {Enter}");

    expect(etiket.dogrula).not.toHaveBeenCalled();
  });

  it("odak kutudan çıkınca uyarı çıkar; rakam tuşu ve “Kutuya dön” odağı geri getirir", async () => {
    const user = userEvent.setup();
    await ekranaBas();
    const kutu = screen.getByLabelText("Kütüphane etiketi");
    await screen.findByText("Doğrulanmamış Etiketler: 1");

    act(() => kutu.blur());
    expect(await screen.findByText(/Okutma kutusu odakta değil/)).toBeInTheDocument();

    // Okuyucu klavye gibi yazar: yazı alanı dışındayken gelen rakam kutuya yönlenir.
    await user.keyboard("7");
    expect(kutu).toHaveFocus();
    expect(screen.queryByText(/Okutma kutusu odakta değil/)).not.toBeInTheDocument();

    act(() => kutu.blur());
    await user.click(await screen.findByRole("button", { name: "Kutuya dön" }));
    expect(kutu).toHaveFocus();
  });

  it("Boşluk tuşu odağı çalmaz: odaktaki düğme Boşluk ile çalışır", async () => {
    const user = userEvent.setup();
    await ekranaBas();
    const kutu = screen.getByLabelText("Kütüphane etiketi");
    await screen.findByText("Doğrulanmamış Etiketler: 1");

    act(() => kutu.blur());
    const dugme = await screen.findByRole("button", { name: "Kutuya dön" });
    act(() => dugme.focus());
    await user.keyboard(" ");

    // Düğme Boşluk ile etkinleşti (odak kutuya döndü) ve kutuya boşluk yazılmadı.
    expect(kutu).toHaveFocus();
    expect(kutu).toHaveValue("");
  });

  it("doğrulanmamış etiket yoksa söylenir", async () => {
    etiket.dogrulanmamislar.mockResolvedValue(sayfa([]));
    await ekranaBas();

    expect(
      await screen.findByText("Doğrulanmamış etiket yok — basılan bütün etiketler okutuldu."),
    ).toBeInTheDocument();
  });
});
