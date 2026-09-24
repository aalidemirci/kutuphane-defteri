// BarcodeInput (tasarım §7.3) — sabitlenen davranışlar:
//
//   1) KOD KAPISI: hızlı okutmada okuma kaybı yok. Art arda 20 okutma (her biri
//      sonuç beklenmeden) sırayla ve TEK TEK işlenir: hiçbiri kaybolmaz, sıra
//      bozulmaz, aynı anda iki işlem yürümez.
//   2) Kendiliğinden odak; Enter ile gönderim; gönderim anında kutu boşalır.
//   3) Sonuç geri bildirimi (başarı · uyarı · hata · bilgi) kutuda görünür iz bırakır;
//      işleyici hata fırlatsa da kuyruk durmaz.
//   4) Odak kaybında görünür uyarı; yazı alanı dışındaki okuyucu tuşu kutuya döner;
//      diyalog açıkken (`beklemede`) kuyruk durur; odak yazı alanında değilse okuyucunun
//      kodu tampona alınır ve diyalog kapanınca işlenir (kaybolmaz).
//   5) `alan` davranışı: değer ebeveyndedir, kutu boşalmaz, işlem sürerken Enter yok sayılır.

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import BarcodeInput, { OKUMA_TONLARI, ODAK_UYARISI } from "./BarcodeInput";
import type { OkutmaGeriBildirimi } from "./BarcodeInput";

/** Elle çözülen işleyici: her çağrı bir söz bırakır; sırayla çözülür. */
function bekleyenIsleyici() {
  const cagrilar: string[] = [];
  const cozuculer: Array<(sonuc: OkutmaGeriBildirimi) => void> = [];
  let esZamanli = 0;
  let enCokEsZamanli = 0;
  const isleyici = vi.fn(
    (kod: string) =>
      new Promise<OkutmaGeriBildirimi>((coz) => {
        cagrilar.push(kod);
        esZamanli += 1;
        enCokEsZamanli = Math.max(enCokEsZamanli, esZamanli);
        cozuculer.push((sonuc) => {
          esZamanli -= 1;
          coz(sonuc);
        });
      }),
  );
  return { isleyici, cagrilar, cozuculer, enCok: () => enCokEsZamanli };
}

const kodlar = Array.from({ length: 20 }, (_, i) => `2026${String(100 + i).padStart(6, "0")}`);

describe("BarcodeInput — hızlı okutmada okuma kaybı yok (kod kapısı)", () => {
  it("art arda 20 okutma sırayla, tek tek ve eksiksiz işlenir", async () => {
    const user = userEvent.setup();
    const { isleyici, cagrilar, cozuculer, enCok } = bekleyenIsleyici();
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");

    // Okuyucu 20 kodu, ilk sonuç gelmeden arka arkaya gönderir.
    for (const kod of kodlar) await user.type(kutu, `${kod}{Enter}`);

    expect(kutu).toHaveValue("");
    expect(isleyici).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Sırada bekleyen okutma: 19")).toBeInTheDocument();

    for (let i = 0; i < kodlar.length; i += 1) {
      await waitFor(() => expect(cozuculer).toHaveLength(i + 1));
      await act(async () => cozuculer[i]("basari"));
    }

    await waitFor(() => expect(isleyici).toHaveBeenCalledTimes(20));
    expect(cagrilar).toEqual(kodlar);
    expect(enCok()).toBe(1);
    await waitFor(() => expect(screen.queryByText(/Sırada bekleyen okutma/)).toBeNull());
  });

  it("olay döngüsüne dönmeden gelen okutmalar da kaybolmaz (okuyucu hızı)", async () => {
    const { isleyici, cagrilar, cozuculer } = bekleyenIsleyici();
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");

    // Eşzamanlı döngü: değer yaz + Enter, 20 kez; aralarda hiçbir söz beklenmez
    // (her olay kendi görevinde işlenir — okuyucunun tuş olayları gibi).
    for (const kod of kodlar) {
      fireEvent.change(kutu, { target: { value: kod } });
      fireEvent.keyDown(kutu, { key: "Enter" });
    }

    for (let i = 0; i < kodlar.length; i += 1) {
      await waitFor(() => expect(cozuculer).toHaveLength(i + 1));
      await act(async () => cozuculer[i]("basari"));
    }
    expect(cagrilar).toEqual(kodlar);
  });

  it("işleyici hata fırlatsa da kuyruk durmaz", async () => {
    const user = userEvent.setup();
    const isleyici = vi
      .fn<(kod: string) => Promise<OkutmaGeriBildirimi>>()
      .mockRejectedValueOnce(new Error("ağ yok"))
      .mockResolvedValue("basari");
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");

    await user.type(kutu, "1{Enter}2{Enter}3{Enter}");

    await waitFor(() => expect(isleyici).toHaveBeenCalledTimes(3));
    expect(isleyici.mock.calls.map((c) => c[0])).toEqual(["1", "2", "3"]);
  });
});

describe("BarcodeInput — temel davranış", () => {
  it("kendiliğinden odaklanır; Enter gönderir ve kutuyu boşaltır; boş Enter gitmez", async () => {
    const user = userEvent.setup();
    const isleyici = vi.fn().mockResolvedValue("basari");
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");
    expect(kutu).toHaveFocus();

    await user.type(kutu, "  {Enter}");
    expect(isleyici).not.toHaveBeenCalled();

    await user.type(kutu, " 2026-000123 {Enter}");
    expect(kutu).toHaveValue("");
    await waitFor(() => expect(isleyici).toHaveBeenCalledWith("2026-000123"));
  });

  it("sonuç kutuda görsel iz bırakır (başarı · uyarı · hata)", async () => {
    const user = userEvent.setup();
    const isleyici = vi
      .fn<(kod: string) => Promise<OkutmaGeriBildirimi>>()
      .mockResolvedValueOnce("basari")
      .mockResolvedValueOnce("hata");
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");

    await user.type(kutu, "1{Enter}");
    await waitFor(() => expect(kutu).toHaveAttribute("data-geri-bildirim", "basari"));
    await user.type(kutu, "2{Enter}");
    await waitFor(() => expect(kutu).toHaveAttribute("data-geri-bildirim", "hata"));
  });

  it("odak kaybında uyarı; okuyucu tuşu ve “Kutuya dön” odağı geri getirir", async () => {
    const user = userEvent.setup();
    render(<BarcodeInput label="Okut" onOkut={vi.fn()} />);
    const kutu = screen.getByLabelText("Okut");

    act(() => kutu.blur());
    expect(await screen.findByText(ODAK_UYARISI)).toBeInTheDocument();
    await user.keyboard("7");
    expect(kutu).toHaveFocus();
    expect(kutu).toHaveValue("7");
    expect(screen.queryByText(ODAK_UYARISI)).toBeNull();

    act(() => kutu.blur());
    await user.click(await screen.findByRole("button", { name: "Kutuya dön" }));
    expect(kutu).toHaveFocus();
  });

  it("beklemedeyken (diyalog açık) tuş yakalanmaz ve uyarı çıkmaz; bitince odak döner", async () => {
    const user = userEvent.setup();
    function Kap() {
      const [bekle, setBekle] = useState(false);
      return (
        <>
          <BarcodeInput label="Okut" onOkut={vi.fn()} beklemede={bekle} />
          <button type="button" onClick={() => setBekle((b) => !b)}>
            değiştir
          </button>
        </>
      );
    }
    render(<Kap />);
    const kutu = screen.getByLabelText("Okut");

    await user.click(screen.getByRole("button", { name: "değiştir" }));
    expect(screen.queryByText(ODAK_UYARISI)).toBeNull();
    await user.keyboard("5");
    expect(kutu).not.toHaveFocus();
    expect(kutu).toHaveValue("");

    await user.click(screen.getByRole("button", { name: "değiştir" }));
    await waitFor(() => expect(kutu).toHaveFocus());
  });

  it("beklemedeyken okutulan kod kaybolmaz: tampona alınır, diyalog kapanınca işlenir", async () => {
    const user = userEvent.setup();
    const isleyici = vi.fn().mockResolvedValue("basari");
    function Kap() {
      const [bekle, setBekle] = useState(true);
      return (
        <>
          <BarcodeInput label="Okut" onOkut={isleyici} beklemede={bekle} />
          <div role="dialog" tabIndex={-1}>
            <input aria-label="Açıklama" />
            <button type="button" onClick={() => setBekle(false)}>
              kapat
            </button>
          </div>
        </>
      );
    }
    render(<Kap />);
    const panel = screen.getByRole("dialog");
    act(() => panel.focus());

    // Odak diyalog panelinde: okuyucunun iki kodu tampona, oradan kuyruğa girer.
    await user.keyboard("2026000302{Enter}2026000303{Enter}");
    // Odak diyalogdaki yazı alanında: tuşlar ALANA gider, kuyruğa girmez.
    await user.type(screen.getByLabelText("Açıklama"), "Ödev 12{Enter}");
    expect(screen.getByLabelText("Açıklama")).toHaveValue("Ödev 12");
    expect(isleyici).not.toHaveBeenCalled();
    expect(screen.getByText("Sırada bekleyen okutma: 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "kapat" }));

    await waitFor(() => expect(isleyici).toHaveBeenCalledTimes(2));
    expect(isleyici.mock.calls.map((c) => c[0])).toEqual(["2026000302", "2026000303"]);
    await waitFor(() => expect(screen.getByLabelText("Okut")).toHaveFocus());
  });

  it("diyalog okutmanın ortasında açılırsa kod ikiye bölünmez", async () => {
    const user = userEvent.setup();
    const isleyici = vi.fn().mockResolvedValue("basari");
    function Kap() {
      const [bekle, setBekle] = useState(false);
      return (
        <>
          <BarcodeInput label="Okut" onOkut={isleyici} beklemede={bekle} />
          <div role="dialog" tabIndex={-1} aria-label="pencere">
            <button type="button" onClick={() => setBekle((b) => !b)}>
              aç-kapat
            </button>
          </div>
        </>
      );
    }
    render(<Kap />);
    const kutu = screen.getByLabelText("Okut");

    await user.type(kutu, "20260");
    // Pencere açılır ve odağı alır; okuyucunun kalan haneleri panele gider.
    await user.click(screen.getByRole("button", { name: "aç-kapat" }));
    act(() => screen.getByRole("dialog", { name: "pencere" }).focus());
    await user.keyboard("00302{Enter}");
    expect(kutu).toHaveValue("");
    expect(isleyici).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "aç-kapat" }));
    await waitFor(() => expect(isleyici).toHaveBeenCalledWith("2026000302"));
    expect(isleyici).toHaveBeenCalledTimes(1);
  });

  it("işleyici diyalog açtırınca kuyruk durur; kapanınca sıradakiler işlenir", async () => {
    const user = userEvent.setup();
    const cagrilar: string[] = [];
    let ilkiniCoz: () => void = () => undefined;
    function Kap() {
      const [bekle, setBekle] = useState(false);
      return (
        <>
          <BarcodeInput
            label="Okut"
            beklemede={bekle}
            onOkut={async (kod): Promise<OkutmaGeriBildirimi> => {
              cagrilar.push(kod);
              if (kod === "1") {
                setBekle(true); // ör. gerekçeli istisna penceresi açıldı
                await new Promise<void>((coz) => {
                  ilkiniCoz = coz;
                });
              }
              return "uyari";
            }}
          />
          <button type="button" onClick={() => setBekle(false)}>
            pencereyi kapat
          </button>
        </>
      );
    }
    render(<Kap />);
    const kutu = screen.getByLabelText("Okut");

    await user.type(kutu, "1{Enter}2{Enter}3{Enter}");
    await waitFor(() => expect(cagrilar).toEqual(["1"]));
    // İlk okutmanın işleyicisi biter; pencere açık olduğu için sıradakiler BEKLER.
    await act(async () => ilkiniCoz());
    expect(cagrilar).toEqual(["1"]);
    expect(screen.getByText("Sırada bekleyen okutma: 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "pencereyi kapat" }));
    await waitFor(() => expect(cagrilar).toEqual(["1", "2", "3"]));
  });

  it("bilgi sonucu (yazma yapmayan okutma) ayrı iz ve ayrı ses tonudur", async () => {
    const user = userEvent.setup();
    const isleyici = vi.fn().mockResolvedValue("bilgi");
    render(<BarcodeInput label="Okut" onOkut={isleyici} />);
    const kutu = screen.getByLabelText("Okut");

    await user.type(kutu, "1{Enter}");

    await waitFor(() => expect(kutu).toHaveAttribute("data-geri-bildirim", "bilgi"));
    expect(OKUMA_TONLARI.bilgi).not.toEqual(OKUMA_TONLARI.basari);
    expect(OKUMA_TONLARI.bilgi).not.toEqual(OKUMA_TONLARI.uyari);
  });

  it("odak bir diyalogun içindeyken tuş yakalanmaz", async () => {
    const user = userEvent.setup();
    render(
      <>
        <BarcodeInput label="Okut" onOkut={vi.fn()} />
        <div role="dialog">
          <button type="button">diyalog düğmesi</button>
        </div>
      </>,
    );
    const dugme = screen.getByRole("button", { name: "diyalog düğmesi" });
    act(() => dugme.focus());

    await user.keyboard("5");

    expect(dugme).toHaveFocus();
    expect(screen.getByLabelText("Okut")).toHaveValue("");
  });
});

describe("BarcodeInput — alan davranışı", () => {
  it("değer ebeveyndedir, kutu boşalmaz; işlem sürerken Enter yok sayılır", async () => {
    const user = userEvent.setup();
    const { isleyici, cozuculer } = bekleyenIsleyici();
    function Kap() {
      const [deger, setDeger] = useState("");
      return (
        <BarcodeInput
          davranis="alan"
          label="ISBN"
          value={deger}
          onValueChange={setDeger}
          onOkut={isleyici}
        />
      );
    }
    render(<Kap />);
    const kutu = screen.getByLabelText("ISBN");

    await user.type(kutu, "9789750812345{Enter}");
    expect(kutu).toHaveValue("9789750812345");
    await user.type(kutu, "{Enter}");
    expect(isleyici).toHaveBeenCalledTimes(1);

    await act(async () => cozuculer[0]("basari"));
    await user.type(kutu, "{Enter}");
    expect(isleyici).toHaveBeenCalledTimes(2);
    // Alan davranışında odak uyarısı varsayılan olarak kapalıdır (formda başka alanlar var).
    act(() => kutu.blur());
    expect(screen.queryByText(ODAK_UYARISI)).toBeNull();
  });
});
