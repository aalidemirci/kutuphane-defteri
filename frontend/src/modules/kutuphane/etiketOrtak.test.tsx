// Etiket ekranlarının ortak parçaları (F4) — sabitlenen davranışlar:
//
//   1) Tabaka sayısı başlangıç hücresini ve "ikisi birden"in iki tabaka takımını
//      sayar; ızgarada tıklanan hücre başlangıç hücresidir (1 tabanlı).
//   2) Basım ayarı içeriğin varsayılan şablonuyla açılır (sırt → sırt tabakası,
//      diğerleri → barkod tabakası); şablonun tek yazıcısı kendiliğinden seçilir;
//      QR yalnız QR'a uygun şablonda seçilebilir; istek gövdesi ayrı sırt
//      tabakasını yalnız "ikisi birden"de taşır.
//   3) PDF ALMAK "BASILDI" DEĞİLDİR (D10): "PDF'i indir" ve "Önizle" onay ucunu
//      çağırmaz; "Basıldı olarak işaretle" onay diyaloğundan geçer, "Vazgeç"
//      denirse hiçbir istek gitmez.

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import {
  basimPartisi,
  etiketSablonu,
  hazirSablonlar,
  kalibrasyon,
} from "../../test/etiketVerileri";
import { sayfa } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const kapi = vi.hoisted(() => ({
  kalibrasyonlar: vi.fn(),
  partiPdf: vi.fn(),
  partiOnayla: vi.fn(),
  partidenVazgec: vi.fn(),
}));

const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...kapi } };
});

vi.mock("../../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import type { EtiketIcerigi } from "./etiketApi";
import {
  BOS_BASIM_AYARI,
  BasimAyarlari,
  BasimPartisiKarti,
  PdfDugmeleri,
  TabakaIzgarasi,
  basimAyariGovdesi,
  ondalikOku,
  parcaSayisi,
  partiOzeti,
  sablonOlcusu,
  tabakaSayisi,
  varsayilanSablon,
} from "./etiketOrtak";
import type { BasimAyari } from "./etiketOrtak";

beforeEach(() => {
  vi.clearAllMocks();
  kapi.kalibrasyonlar.mockResolvedValue(sayfa([]));
  kapi.partiPdf.mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function saglayicilarla(dugum: ReactNode) {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>{dugum}</ConfirmProvider>
    </SnackbarProvider>,
  );
}

describe("yardımcılar", () => {
  it("tabaka sayısı başlangıç hücresini ve iki tabaka takımını sayar", () => {
    expect(tabakaSayisi(65, 1, 65)).toBe(1);
    expect(tabakaSayisi(66, 1, 65)).toBe(2);
    // 60. hücreden başlayan 6 etiket ilk tabakayı taşar.
    expect(tabakaSayisi(6, 60, 65)).toBe(1);
    expect(tabakaSayisi(7, 60, 65)).toBe(2);
    expect(tabakaSayisi(70, 1, 65, parcaSayisi("BOTH"))).toBe(4);
    expect(tabakaSayisi(0, 1, 65)).toBe(0);
    expect(parcaSayisi("BLANK")).toBe(1);
  });

  it("ondalık girdi virgül ve noktayı kabul eder; bozuk girdi null döner", () => {
    expect(ondalikOku("38,1")).toBe(38.1);
    expect(ondalikOku(" 4.75 ")).toBe(4.75);
    expect(ondalikOku("-0,5")).toBe(-0.5);
    expect(ondalikOku("")).toBeNull();
    expect(ondalikOku("12 mm")).toBeNull();
  });

  it("varsayılan şablon içeriğe göre seçilir", () => {
    const sablonlar = hazirSablonlar();
    expect(varsayilanSablon(sablonlar, "SPINE")?.id).toBe(4);
    expect(varsayilanSablon(sablonlar, "BOTH")?.id).toBe(1);
    expect(varsayilanSablon(sablonlar, "BLANK")?.id).toBe(1);
    // Varsayılan işaretli değilse türün ilki, tür hiç yoksa ilk şablon.
    const isaretsiz = sablonlar.map((s) => ({ ...s, is_default: false }));
    expect(varsayilanSablon(isaretsiz, "BARCODE")?.id).toBe(1);
    expect(varsayilanSablon([sablonlar[2]], "BARCODE")?.id).toBe(4);
    expect(varsayilanSablon([], "BARCODE")).toBeNull();
  });

  it("ölçü satırı ve parti özeti Türkçe biçimlidir", () => {
    expect(sablonOlcusu(etiketSablonu())).toBe("38,1 × 21,2 mm · 65 etiket (5 × 13)");
    expect(
      partiOzeti(
        basimPartisi({ copy_count: 70, printer_name: "Masa yazıcısı", include_qr: true }),
        etiketSablonu(),
      ),
    ).toBe(
      "Sırt ve barkod etiketi · 70 nüsha · 4 tabaka · Barkod etiketi — 38,1 × 21,2 mm, 65'li · " +
        "yazıcı: Masa yazıcısı · 1. hücreden · QR'lı",
    );
    expect(partiOzeti(basimPartisi())).toContain("kalibrasyonsuz");
  });

  it("istek gövdesi: ayrı sırt tabakası yalnız 'ikisi birden'de, QR sırt basımında yok", () => {
    const ayar: BasimAyari = {
      sablon: "1",
      kalibrasyon: "8",
      sirtSablonu: "4",
      sirtKalibrasyonu: "9",
      baslangic: 12,
      qr: true,
    };
    expect(basimAyariGovdesi(ayar, "BOTH")).toEqual({
      template: 1,
      calibration: 8,
      spine_template: 4,
      spine_calibration: 9,
      include_qr: true,
      start_cell: 12,
    });
    expect(basimAyariGovdesi(ayar, "SPINE")).toMatchObject({
      spine_template: null,
      spine_calibration: null,
      include_qr: false,
    });
    expect(basimAyariGovdesi({ ...ayar, sablon: "" }, "BARCODE")).toBeNull();
  });
});

describe("TabakaIzgarasi", () => {
  it("her hücre bir düğmedir; tıklanan hücre başlangıç hücresi olur", async () => {
    const user = userEvent.setup();
    const sec = vi.fn();
    render(<TabakaIzgarasi sablon={etiketSablonu()} baslangic={3} onBaslangic={sec} adet={5} />);

    const izgara = screen.getByRole("group", { name: "Tabaka ızgarası" });
    expect(within(izgara).getAllByRole("button")).toHaveLength(65);
    expect(screen.getByRole("button", { name: "3. hücre" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "4. hücre" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    await user.click(screen.getByRole("button", { name: "12. hücre" }));
    expect(sec).toHaveBeenCalledWith(12);
  });
});

/** Basım ayarını kendi durumunda tutan sarmalayıcı (sayfadaki kullanım). */
function AyarSarmalayici({
  icerik,
  adet,
  ilk = BOS_BASIM_AYARI,
  bildir,
}: {
  icerik: EtiketIcerigi | "BLANK";
  adet?: number;
  ilk?: BasimAyari;
  bildir?: (ayar: BasimAyari) => void;
}) {
  const [ayar, setAyar] = useState<BasimAyari>(ilk);
  return (
    <BasimAyarlari
      icerik={icerik}
      sablonlar={hazirSablonlar()}
      ayar={ayar}
      onAyar={(sonraki) => {
        setAyar(sonraki);
        bildir?.(sonraki);
      }}
      adet={adet}
    />
  );
}

describe("BasimAyarlari", () => {
  it("sırt basımı sırt tabakasıyla açılır; QR seçeneği sırtta yoktur", async () => {
    render(<AyarSarmalayici icerik="SPINE" adet={3} />);

    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("4"));
    expect(screen.queryByLabelText(/Barkodun yanına QR ekle/)).not.toBeInTheDocument();
    expect(screen.getByText("3 etiket · 1 tabaka")).toBeInTheDocument();
  });

  it("şablonun tek yazıcısı kendiliğinden seçilir", async () => {
    kapi.kalibrasyonlar.mockResolvedValue(sayfa([kalibrasyon()]));
    render(<AyarSarmalayici icerik="BARCODE" />);

    await waitFor(() => expect(screen.getByLabelText("Yazıcı (kalibrasyon)")).toHaveValue("8"));
    expect(kapi.kalibrasyonlar).toHaveBeenCalledWith(1);
  });

  it("QR yalnız QR'a uygun şablonda seçilebilir; şablon değişince başlangıç hücresi taşmaz", async () => {
    const user = userEvent.setup();
    const bildir = vi.fn();
    render(
      <AyarSarmalayici
        icerik="BARCODE"
        bildir={bildir}
        ilk={{ ...BOS_BASIM_AYARI, sablon: "1", baslangic: 60 }}
      />,
    );

    const qr = screen.getByRole("checkbox", { name: /Barkodun yanına QR ekle/ });
    expect(qr).toBeDisabled();
    expect(screen.getByText(/48,5 × 25,4 mm ve daha büyük etiketlere sığar/)).toBeInTheDocument();

    // 44'lü tabakada 60. hücre yoktur: başlangıç 1'e döner.
    await user.selectOptions(screen.getByLabelText(/^Etiket şablonu/), "2");
    expect(bildir).toHaveBeenLastCalledWith(expect.objectContaining({ sablon: "2", baslangic: 1 }));
    const qrUygun = screen.getByRole("checkbox", { name: /Barkodun yanına QR ekle/ });
    expect(qrUygun).toBeEnabled();
    await user.click(qrUygun);
    expect(bildir).toHaveBeenLastCalledWith(expect.objectContaining({ qr: true }));
  });

  it("ızgaradan ve sayı kutusundan başlangıç hücresi seçilir; tabaka sayısı güncellenir", async () => {
    const user = userEvent.setup();
    render(<AyarSarmalayici icerik="BOTH" adet={10} ilk={{ ...BOS_BASIM_AYARI, sablon: "1" }} />);

    expect(
      screen.getByText("10 etiket · 2 tabaka (önce sırt, sonra barkod tabakaları)"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "60. hücre" }));
    expect(screen.getByLabelText("Başlangıç hücresi")).toHaveValue("60");
    expect(screen.getByText(/İlk tabakanın ilk 59 hücresi boş bırakılır/)).toBeInTheDocument();
    expect(
      screen.getByText("10 etiket · 4 tabaka (önce sırt, sonra barkod tabakaları)"),
    ).toBeInTheDocument();

    // Kutu boşaltılıp yeni sayı yazılabilir (denetim bulgusu: "3" yazan "13" elde ediyordu).
    const kutu = screen.getByLabelText("Başlangıç hücresi");
    await user.clear(kutu);
    expect(kutu).toHaveValue("");
    await user.type(kutu, "3");
    expect(kutu).toHaveValue("3");
    expect(screen.getByRole("button", { name: "3. hücre" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.keyboard("{Backspace}5");
    expect(kutu).toHaveValue("5");
    expect(screen.getByRole("button", { name: "5. hücre" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Tabakada olmayan hücre yazılamaz: hata görünür, ayar son geçerli değerde
    // kalır, kutudan çıkınca kutu o değere döner.
    await user.clear(kutu);
    await user.type(kutu, "99");
    expect(screen.getByText("Başlangıç hücresi 1 ile 65 arasında olmalıdır.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "9. hücre" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.tab();
    expect(kutu).toHaveValue("9");
  });

  it("'ikisi birden'de ayrı sırt tabakası yalnız aynı ızgaradaki şablonlardan seçilir", async () => {
    await act(async () => {
      render(<AyarSarmalayici icerik="BOTH" ilk={{ ...BOS_BASIM_AYARI, sablon: "1" }} />);
    });

    const secici = screen.getByLabelText("Sırt etiketi tabakası");
    const secenekler = within(secici)
      .getAllByRole("option")
      .map((o) => o.textContent);
    // 44'lü (4 × 11) aynı ızgarada değildir; 65'li sırt tabakası seçilebilir.
    expect(secenekler).toEqual(["— yok —", "Sırt etiketi — 38,1 × 21,2 mm, 65'li"]);
  });

  it("şablon yoksa kullanıcı Şablonlar ve Kalibrasyon sekmesine yönlendirilir", () => {
    render(<BasimAyarlari icerik="BOTH" sablonlar={[]} ayar={BOS_BASIM_AYARI} onAyar={vi.fn()} />);
    expect(screen.getByText(/Şablonlar ve Kalibrasyon sekmesinden/)).toBeInTheDocument();
  });
});

describe("PdfDugmeleri — PDF almak basım işareti DEĞİLDİR", () => {
  it("indirilen PDF belge adı + tarihle kaydedilir", async () => {
    const user = userEvent.setup();
    const pdfAl = vi.fn().mockResolvedValue(new Blob(["%PDF"]));
    saglayicilarla(
      <PdfDugmeleri
        pdfAl={pdfAl}
        dosyaAdi={() => "Sırt-Etiketi_24.09.2026.pdf"}
        onizlemeBasligi="Sırt etiketi"
        onHata={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    await waitFor(() => expect(indirme.saveBlob).toHaveBeenCalledTimes(1));
    expect(indirme.saveBlob.mock.calls[0][1]).toBe("Sırt-Etiketi_24.09.2026.pdf");
  });

  it("önizleme pencere içinde açılır ve ölçeklemeyi kapatmayı söyler", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:onizleme");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    saglayicilarla(
      <PdfDugmeleri
        pdfAl={() => Promise.resolve(new Blob(["%PDF"]))}
        dosyaAdi={() => "x.pdf"}
        onizlemeBasligi="Barkod etiketi"
        onHata={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Önizle" }));

    const pencere = await screen.findByRole("dialog", { name: "Barkod etiketi" });
    expect(within(pencere).getByText(/“Gerçek boyut”/)).toBeInTheDocument();
    expect(pencere.querySelector("embed")).toHaveAttribute("src", "blob:onizleme");
    await user.click(within(pencere).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:onizleme"));
  });

  it("PDF alınamazsa hata bildirilir (etiket motoru yok: 503)", async () => {
    const user = userEvent.setup();
    const onHata = vi.fn();
    saglayicilarla(
      <PdfDugmeleri
        pdfAl={() =>
          Promise.reject(new ApiError(503, "etiket_motoru_yok", "Etiket basım motoru yüklenemedi."))
        }
        dosyaAdi={() => "x.pdf"}
        onizlemeBasligi="Barkod etiketi"
        onHata={onHata}
      />,
    );

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    await waitFor(() =>
      expect(onHata).toHaveBeenLastCalledWith(
        expect.objectContaining({ message: "Etiket basım motoru yüklenemedi." }),
      ),
    );
    expect(indirme.saveBlob).not.toHaveBeenCalled();
  });
});

describe("BasimPartisiKarti", () => {
  it("PDF'i indirmek partiyi onaylamaz", async () => {
    const user = userEvent.setup();
    saglayicilarla(<BasimPartisiKarti parti={basimPartisi()} onDegisti={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));

    await waitFor(() => expect(kapi.partiPdf).toHaveBeenCalledWith(12));
    expect(kapi.partiOnayla).not.toHaveBeenCalled();
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(
      /^Sırt-ve-Barkod-Etiketi_\d\d\.\d\d\.\d{4}\.pdf$/,
    );
  });

  it("“Basıldı olarak işaretle” onaydan geçer; vazgeçilirse istek gitmez", async () => {
    const user = userEvent.setup();
    const onDegisti = vi.fn();
    kapi.partiOnayla.mockResolvedValue(basimPartisi({ status: "CONFIRMED" }));
    saglayicilarla(<BasimPartisiKarti parti={basimPartisi()} onDegisti={onDegisti} />);

    await user.click(screen.getByRole("button", { name: "Basıldı olarak işaretle" }));
    let pencere = await screen.findByRole("dialog", {
      name: "Etiketler basıldı olarak işaretlensin mi?",
    });
    expect(within(pencere).getByText(/2 nüshanın sırt ve barkod etiketi/)).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Vazgeç" }));
    expect(kapi.partiOnayla).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Basıldı olarak işaretle" }));
    pencere = await screen.findByRole("dialog", {
      name: "Etiketler basıldı olarak işaretlensin mi?",
    });
    await user.click(within(pencere).getByRole("button", { name: "Basıldı olarak işaretle" }));

    await waitFor(() => expect(kapi.partiOnayla).toHaveBeenCalledWith(12));
    expect(onDegisti).toHaveBeenCalledWith(expect.objectContaining({ status: "CONFIRMED" }));
    expect(await screen.findByText("2 nüsha basıldı olarak işaretlendi.")).toBeInTheDocument();
  });

  it("partiden vazgeçme onaylıdır; sunucu reddederse ileti gösterilir", async () => {
    const user = userEvent.setup();
    const onDegisti = vi.fn();
    kapi.partidenVazgec.mockRejectedValue(
      new ApiError(400, "validation_error", "Bu parti zaten basıldı olarak işaretli."),
    );
    saglayicilarla(<BasimPartisiKarti parti={basimPartisi()} onDegisti={onDegisti} />);

    await user.click(screen.getByRole("button", { name: "Partiden vazgeç" }));
    const pencere = await screen.findByRole("dialog", { name: "Bu partiden vazgeçilsin mi?" });
    await user.click(within(pencere).getByRole("button", { name: "Partiden vazgeç" }));

    expect(await screen.findByText("Bu parti zaten basıldı olarak işaretli.")).toBeInTheDocument();
    expect(onDegisti).not.toHaveBeenCalled();
  });
});
