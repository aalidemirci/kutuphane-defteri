// Etiketler → Boş Barkod Aralığı (önce etiket yolu, F4) — sabitlenen davranışlar:
//
//   1) Numara ayırma onay diyaloğundan geçer: ayrılan numara başka nüshaya
//      verilmez, kullanılmayan iptal edilir ve sayaca dönmez. Adet 1-1.300
//      dışındaysa istek çıkmaz.
//   2) Boş etiket PDF'i işarete dokunmaz; seçilen numaralar varsa yalnız onlar
//      basılır (bozulan etiketin yenisi). "Basıldı olarak işaretle" onaylıdır.
//   3) İptal GERİ ALINMAZ: onay düğmesi, kullanıcı etiketlerin kitaplara
//      yapıştırılmadığını denetlediğini işaretlemeden açılmaz.
//   4) Aralıktan kitaba bağlanan etiket varsa basım işareti geri alınamaz.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  bosBarkodAraligi,
  bosBarkodAraligiAyrintisi,
  hazirSablonlar,
} from "../../test/etiketVerileri";
import { sayfa } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const etiket = vi.hoisted(() => ({
  araliklar: vi.fn(),
  aralik: vi.fn(),
  aralikAyir: vi.fn(),
  aralikPdf: vi.fn(),
  aralikBasildi: vi.fn(),
  aralikBasimGeriAl: vi.fn(),
  aralikIptal: vi.fn(),
  kalibrasyonlar: vi.fn(),
}));

const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

vi.mock("../../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import BosBarkodPaneli from "./BosBarkodPaneli";

function ekranaBas(onDegisti = vi.fn()) {
  render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <BosBarkodPaneli sablonlar={hazirSablonlar()} tazeleme={0} onDegisti={onDegisti} />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
  return onDegisti;
}

beforeEach(() => {
  vi.clearAllMocks();
  etiket.araliklar.mockResolvedValue(sayfa([bosBarkodAraligi()]));
  etiket.aralik.mockResolvedValue(bosBarkodAraligiAyrintisi());
  etiket.aralikAyir.mockResolvedValue(
    bosBarkodAraligiAyrintisi({
      id: 6,
      count: 65,
      first_barcode_display: "2026-000104",
      last_barcode_display: "2026-000168",
    }),
  );
  etiket.aralikPdf.mockResolvedValue(new Blob(["%PDF"]));
  etiket.aralikBasildi.mockResolvedValue(
    bosBarkodAraligi({ printed_at: "2026-09-24T12:00:00+03:00" }),
  );
  etiket.kalibrasyonlar.mockResolvedValue(sayfa([]));
});

/** Listedeki aralığı açar. */
async function araligiAc(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole("button", { name: "2026-000101 – 2026-000103 aralığını aç" }),
  );
  await screen.findByText(/Seçilen Aralık/);
  await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));
}

describe("Boş Barkod Aralığı — ayırma", () => {
  it("adet sınır dışındaysa istek çıkmaz", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.type(screen.getByLabelText(/^Adet/), "0");
    await user.click(screen.getByRole("button", { name: "Numara ayır" }));

    expect(await screen.findByText("1 ile 1.300 arasında bir sayı yazın.")).toBeInTheDocument();
    expect(etiket.aralikAyir).not.toHaveBeenCalled();
  });

  it("ayırma onaydan geçer; ayrılan aralık açılır", async () => {
    const user = userEvent.setup();
    const onDegisti = ekranaBas();

    await user.type(screen.getByLabelText(/^Adet/), "65");
    await user.type(screen.getByLabelText("Açıklama"), "Hikâye rafı");
    await user.click(screen.getByRole("button", { name: "Numara ayır" }));

    const pencere = await screen.findByRole("dialog", { name: "65 numara ayrılsın mı?" });
    expect(within(pencere).getByText(/sayaca geri dönmez/)).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Numara ayır" }));

    await waitFor(() => expect(etiket.aralikAyir).toHaveBeenCalledWith(65, "Hikâye rafı"));
    expect(
      await screen.findByText("65 numara ayrıldı: 2026-000104 – 2026-000168."),
    ).toBeInTheDocument();
    await waitFor(() => expect(etiket.aralik).toHaveBeenCalledWith(6));
    expect(onDegisti).toHaveBeenCalled();
  });

  it("onay diyaloğunda vazgeçilirse numara ayrılmaz", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.type(screen.getByLabelText(/^Adet/), "10");
    await user.click(screen.getByRole("button", { name: "Numara ayır" }));
    const pencere = await screen.findByRole("dialog", { name: "10 numara ayrılsın mı?" });
    await user.click(within(pencere).getByRole("button", { name: "Vazgeç" }));

    expect(etiket.aralikAyir).not.toHaveBeenCalled();
  });
});

describe("Boş Barkod Aralığı — basım ve iptal", () => {
  it("PDF bütün açık numaralarla, seçim varsa yalnız seçilenlerle istenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await araligiAc(user);

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(etiket.aralikPdf).toHaveBeenCalledTimes(1));
    expect(etiket.aralikPdf.mock.calls[0]).toEqual([
      5,
      { template: 1, calibration: null, start_cell: 1, include_qr: false, barcodes: undefined },
    ]);
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(
      /^Boş-Barkod-Etiketi_2026-000101_2026-000103_\d\d\.\d\d\.\d{4}\.pdf$/,
    );

    await user.click(screen.getByRole("checkbox", { name: "2026-000102 seç" }));
    expect(screen.getByText(/Yalnız seçtiğiniz 1 numaranın etiketi basılır/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(etiket.aralikPdf).toHaveBeenCalledTimes(2));
    expect(etiket.aralikPdf.mock.calls[1][1]).toMatchObject({ barcodes: ["2026000102"] });
    // PDF almak basım işareti yazmaz.
    expect(etiket.aralikBasildi).not.toHaveBeenCalled();
  });

  it("“Basıldı olarak işaretle” onaylıdır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await araligiAc(user);

    await user.click(screen.getByRole("button", { name: "Basıldı olarak işaretle" }));
    const pencere = await screen.findByRole("dialog", {
      name: "Boş etiketler basıldı olarak işaretlensin mi?",
    });
    await user.click(within(pencere).getByRole("button", { name: "Basıldı olarak işaretle" }));

    await waitFor(() => expect(etiket.aralikBasildi).toHaveBeenCalledWith(5));
    expect(
      await screen.findByText("Boş etiketler basıldı olarak işaretlendi."),
    ).toBeInTheDocument();
  });

  it("kitaba bağlanmış etiket varsa basım işareti geri alınamaz", async () => {
    etiket.aralik.mockResolvedValue(
      bosBarkodAraligiAyrintisi({ printed_at: "2026-09-24T12:00:00+03:00", bound_count: 1 }),
    );
    const user = userEvent.setup();
    ekranaBas();
    await araligiAc(user);

    expect(screen.getByRole("button", { name: "Basım işaretini geri al" })).toBeDisabled();
    expect(screen.getByText(/basım işareti geri alınamaz/)).toBeInTheDocument();
  });

  it("basılmış ve bağlanmamış aralığın basım işareti onayla geri alınır", async () => {
    etiket.aralik.mockResolvedValue(
      bosBarkodAraligiAyrintisi({ printed_at: "2026-09-24T12:00:00+03:00", bound_count: 0 }),
    );
    etiket.aralikBasimGeriAl.mockResolvedValue(bosBarkodAraligi());
    const user = userEvent.setup();
    ekranaBas();
    await araligiAc(user);

    await user.click(screen.getByRole("button", { name: "Basım işaretini geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Basım işareti geri alınsın mı?" });
    await user.click(within(pencere).getByRole("button", { name: "Basım işaretini geri al" }));

    await waitFor(() => expect(etiket.aralikBasimGeriAl).toHaveBeenCalledWith(5));
  });

  it("iptal, etiketlerin yapıştırılmadığı işaretlenmeden onaylanamaz; gerekçe gider", async () => {
    const user = userEvent.setup();
    etiket.aralikIptal.mockResolvedValue({
      cancelled: 1,
      reservation: bosBarkodAraligiAyrintisi({ open_count: 1, cancelled_count: 1 }),
    });
    const onDegisti = ekranaBas();
    await araligiAc(user);

    await user.click(screen.getByRole("checkbox", { name: "2026-000101 seç" }));
    await user.type(screen.getByLabelText("İptal gerekçesi"), "Etiket yırtıldı");
    await user.click(screen.getByRole("button", { name: "Seçilenleri iptal et" }));

    const pencere = await screen.findByRole("dialog", { name: "1 numara iptal edilsin mi?" });
    expect(within(pencere).getByText(/geri alınamaz/)).toBeInTheDocument();
    const onay = within(pencere).getByRole("button", { name: "Numaraları iptal et" });
    expect(onay).toBeDisabled();
    await user.click(within(pencere).getByRole("checkbox"));
    await user.click(onay);

    await waitFor(() =>
      expect(etiket.aralikIptal).toHaveBeenCalledWith(5, {
        barcodes: ["2026000101"],
        reason: "Etiket yırtıldı",
      }),
    );
    expect(await screen.findByText("1 numara iptal edildi.")).toBeInTheDocument();
    expect(onDegisti).toHaveBeenCalled();
  });

  it("bağlanmamış bütün numaraların iptali numara listesi göndermez", async () => {
    const user = userEvent.setup();
    etiket.aralikIptal.mockResolvedValue({
      cancelled: 2,
      reservation: bosBarkodAraligiAyrintisi({ open_count: 0, cancelled_count: 2 }),
    });
    ekranaBas();
    await araligiAc(user);

    await user.click(screen.getByRole("button", { name: "Bağlanmamış bütün numaraları iptal et" }));
    const pencere = await screen.findByRole("dialog", { name: "2 numara iptal edilsin mi?" });
    await user.click(within(pencere).getByRole("checkbox"));
    await user.click(within(pencere).getByRole("button", { name: "Numaraları iptal et" }));

    await waitFor(() =>
      expect(etiket.aralikIptal).toHaveBeenCalledWith(5, { barcodes: undefined, reason: "" }),
    );
    expect(
      await screen.findByText("Bu aralıkta basılacak bağlanmamış numara kalmadı."),
    ).toBeInTheDocument();
  });

  it("bağlanan kitapların sırt etiketlerine kuyruk bağlantısı verilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await araligiAc(user);

    expect(screen.getByRole("link", { name: "Sırt etiketlerini bas" })).toHaveAttribute(
      "href",
      "/katalog/etiketler?aralik=5&icerik=SPINE",
    );
    expect(screen.getByText("Gökyüzü Masalları")).toBeInTheDocument();
  });
});
