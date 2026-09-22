// Kurtarma anahtarı paneli (E14 akışı): anahtar gruplarıyla GÖRÜNÜR; yazdır, PDF
// olarak kaydet ve elle yaz yolları sunulur; devam, sakladığı kopyadan rastgele
// İKİ grubun geri yazdırılmasıyla doğrulanır (istemci tarafında, doğrulama
// kipinde anahtar ekrandan kalkar). Anahtar ve okul adı uydurmadır.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const guvenlik = vi.hoisted(() => ({ kurtarmaAnahtariPdf: vi.fn() }));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./api", () => ({ guvenlikApi: guvenlik }));
vi.mock("../../lib/download", async (importOriginal) => {
  const gercek = await importOriginal<typeof import("../../lib/download")>();
  return { ...gercek, saveBlob: indirme.saveBlob };
});

import KurtarmaAnahtariPaneli from "./KurtarmaAnahtariPaneli";
import {
  kurtarmaAnahtariniNormallestir,
  kurtarmaCiktisiDosyaAdi,
  kurtarmaGruplari,
  rastgeleIkiGrup,
} from "./kurtarma";

const ANAHTAR = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM";

/** `rastgele` sırayla bu değerleri döndürür → 2. ve 6. grup sorulur (0,1 → 1 ve 5). */
function sabitRastgele(...degerler: number[]): () => number {
  let i = 0;
  return () => degerler[i++ % degerler.length];
}

function bas(onDogrulama = vi.fn(), rastgele = sabitRastgele(0.125, 0.6)) {
  render(
    <SnackbarProvider>
      <KurtarmaAnahtariPaneli
        anahtar={ANAHTAR}
        okulAdi="Deneme Anadolu Lisesi"
        onDogrulama={onDogrulama}
        rastgele={rastgele}
      />
    </SnackbarProvider>,
  );
  return onDogrulama;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("kurtarma yardımcıları", () => {
  it("normalleştirme örnek tablosu backend ile aynı (Türkçe İ/ı dahil)", () => {
    // AYNI tablo backend'de sınanır: apps/okul/tests/test_app_password.py
    // NORMALLESTIRME_ORNEKLERI. Biri değişirse öteki de değişmeli.
    const ornekler: Array<[string, string]> = [
      [" test-kurt ", "TESTKURT"],
      ["o0i1b8", "OOIIBB"],
      ["abci-ABCI-ABCİ-ABCı", "ABCIABCIABCIABCI"],
      ["TARİ tarı Tari", "TARITARITARI"],
      ["ŞAKA-12", "AKAI2"],
    ];
    for (const [yazim, beklenen] of ornekler) {
      expect(kurtarmaAnahtariniNormallestir(yazim)).toBe(beklenen);
    }
  });

  it("Türkçe klavyede büyük harfle yazılan grup doğrulamayı geçer", () => {
    expect(kurtarmaGruplari(ANAHTAR.replace(/I/g, "İ"))).toEqual(ANAHTAR.split("-"));
  });

  it("anahtar dörtlü gruplara ayrılır", () => {
    expect(kurtarmaGruplari(ANAHTAR)).toEqual(ANAHTAR.split("-"));
  });

  it("iki farklı grup seçilir, sıralı döner", () => {
    for (const [a, b] of [
      [0, 0],
      [0.99, 0.99],
      [0.5, 0.1],
      [0.2, 0.9],
    ]) {
      const [x, y] = rastgeleIkiGrup(8, sabitRastgele(a, b));
      expect(x).toBeLessThan(y);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThan(8);
    }
  });

  it("PDF dosya adı belge adı + yerel tarih taşır, anahtar taşımaz", () => {
    expect(kurtarmaCiktisiDosyaAdi()).toMatch(
      /^Kurtarma-Anahtarı-Çıktısı_\d{2}\.\d{2}\.\d{4}\.pdf$/,
    );
  });
});

describe("KurtarmaAnahtariPaneli", () => {
  it("anahtarı numaralı gruplarla ve tek satırda gösterir, üç saklama yolunu sunar", () => {
    bas();
    expect(screen.getByTestId("kurtarma-anahtari")).toHaveTextContent(ANAHTAR);
    expect(screen.getByText("1. grup")).toBeInTheDocument();
    expect(screen.getByText("8. grup")).toBeInTheDocument();
    expect(screen.getByText(/Deneme Anadolu Lisesi/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yazdır" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF olarak kaydet" })).toBeInTheDocument();
    expect(screen.getByText(/elle yazacaksanız/i)).toBeInTheDocument();
    // Metin dosyası yolu kaldırıldı (PDF aynı işi resmî çıktı biçiminde görür).
    expect(screen.queryByRole("button", { name: /metin dosyası/i })).toBeNull();
  });

  it("Yazdır pencere yazdırmasını çağırır", async () => {
    const kullanici = userEvent.setup();
    const yazdir = vi.fn();
    vi.stubGlobal("print", yazdir);
    bas();
    await kullanici.click(screen.getByRole("button", { name: "Yazdır" }));
    expect(yazdir).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it("PDF olarak kaydet: anahtarı backend'e gönderir ve dosyayı belge adıyla indirir", async () => {
    const kullanici = userEvent.setup();
    const pdf = new Blob(["%PDF-"], { type: "application/pdf" });
    guvenlik.kurtarmaAnahtariPdf.mockResolvedValue(pdf);
    bas();

    await kullanici.click(screen.getByRole("button", { name: "PDF olarak kaydet" }));

    await waitFor(() => expect(guvenlik.kurtarmaAnahtariPdf).toHaveBeenCalledWith(ANAHTAR));
    expect(indirme.saveBlob).toHaveBeenCalledWith(pdf, kurtarmaCiktisiDosyaAdi());
    expect(
      await screen.findByText("Kurtarma anahtarı çıktısı PDF olarak kaydedildi."),
    ).toBeInTheDocument();
  });

  it("PDF hatasında backend iletisi görünür", async () => {
    const kullanici = userEvent.setup();
    guvenlik.kurtarmaAnahtariPdf.mockRejectedValue(
      new ApiError(423, "locked", "Kayıtlar yönetici parolasıyla kilitli.", {}),
    );
    bas();
    await kullanici.click(screen.getByRole("button", { name: "PDF olarak kaydet" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Kayıtlar yönetici parolasıyla kilitli.",
    );
    expect(indirme.saveBlob).not.toHaveBeenCalled();
  });

  it("doğrulama kipinde anahtar ekrandan kalkar; iki grup doğru yazılınca doğrulanır", async () => {
    const kullanici = userEvent.setup();
    const onDogrulama = bas();
    expect(onDogrulama).toHaveBeenLastCalledWith(false);

    await kullanici.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));

    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
    expect(screen.getByText(/anahtarın 2\. ve 6\. grubunu yazın/)).toBeInTheDocument();
    // Küçük harf ve boşluk serbest (backend normalleştirmesiyle aynı).
    await kullanici.type(screen.getByLabelText("2. grup"), "kurt");
    await kullanici.type(screen.getByLabelText("6. grup"), "ab cd");

    expect(await screen.findByRole("status")).toHaveTextContent("Doğrulandı.");
    expect(onDogrulama).toHaveBeenLastCalledWith(true);
  });

  it("yanlış grup doğrulanmaz ve alan hatası gösterir", async () => {
    const kullanici = userEvent.setup();
    const onDogrulama = bas();
    await kullanici.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));

    await kullanici.type(screen.getByLabelText("2. grup"), "KURT");
    await kullanici.type(screen.getByLabelText("6. grup"), "ABCE");

    expect(screen.getByText("Bu grup anahtarla eşleşmiyor.")).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
    expect(onDogrulama).not.toHaveBeenCalledWith(true);
  });

  it("anahtar yeniden gösterilince doğrulama düşer", async () => {
    const kullanici = userEvent.setup();
    const onDogrulama = bas();
    await kullanici.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));
    await kullanici.type(screen.getByLabelText("2. grup"), "KURT");
    await kullanici.type(screen.getByLabelText("6. grup"), "ABCD");
    expect(onDogrulama).toHaveBeenLastCalledWith(true);

    await kullanici.click(screen.getByRole("button", { name: "Anahtarı yeniden göster" }));

    expect(screen.getByTestId("kurtarma-anahtari")).toBeInTheDocument();
    expect(onDogrulama).toHaveBeenLastCalledWith(false);
  });
});
