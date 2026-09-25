// Kayıp/hasar dosyasının ayrıntısı (F7, Md. 19, D3). Çözüm düğmeleri YALNIZ sunucunun
// `allowed_resolutions` listesinden kurulur (kademe kapısı sunucudadır); ortaöğretim
// dışında bedel seçeneği görünmez ve nedeni yazılır. Her çözüm onaydan geçer (başlık
// soru, gövde sonuç); bedel yalnız kayıttır — borç/ceza dili yok. Bedel iki adımdır:
// piyasa bedeli yalnız "Bedel belirlendi"de sorulur; "Bedel teslim alındı" dosyası
// okulun açık işidir (25.09.2026). Onarıma gönder ve onarımdan dön de onaydan geçer.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { dosyaVerisi } from "../../test/teslimVerileri";
import type { Cozum, Dosya } from "./api";

const kayip = vi.hoisted(() => ({
  coz: vi.fn(),
  notuGuncelle: vi.fn(),
  onarimaGonder: vi.fn(),
  onarimdanDon: vi.fn(),
  getir: vi.fn(),
  tutanakPdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayip } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import DosyaAyrintisi, {
  BEDELLI_ONERI_GERI_ALMA_NOTU,
  BEDEL_IADESI_NOTU,
  BEDEL_YOK_NOTU,
  KAYITTAN_DUSULMUS_NOTU,
  OKULUN_ACIK_ISI_NOTU,
  ONERI_GERI_ALMA_NOTU,
  SAYIMDA_DUSULMUS_NOTU,
  bedelMetni,
  cozumSonucu,
} from "./DosyaAyrintisi";

function ciz(dosya: Dosya, onDegisti = vi.fn()) {
  const onClose = vi.fn();
  render(
    <MemoryRouter>
      <SnackbarProvider>
        <DosyaAyrintisi dosya={dosya} onClose={onClose} onDegisti={onDegisti} />
      </SnackbarProvider>
    </MemoryRouter>,
  );
  return { onClose, onDegisti };
}

const ORTAOGRETIM: Dosya["allowed_resolutions"] = [
  { value: "PRICE_DETERMINED", label: "Bedel belirlendi" },
  { value: "FOUND_RETURNED", label: "Bulundu" },
  { value: "REPLACED_SAME", label: "Aynısı temin edildi" },
  { value: "WRITE_OFF_PROPOSED", label: "Kayıttan düşme önerildi" },
];

beforeEach(() => {
  vi.resetAllMocks();
  kayip.coz.mockImplementation(async (_id: number, govde: { resolution: Cozum }) =>
    dosyaVerisi({
      resolution: govde.resolution,
      resolution_display: "Bulundu",
      is_open: false,
      resolved_at: "2026-09-25T10:00:00+03:00",
      allowed_resolutions: [],
    }),
  );
  kayip.tutanakPdf.mockResolvedValue(new Blob(["%PDF"]));
});

describe("DosyaAyrintisi — Md. 19 kademe kapısı", () => {
  it("ortaöğretim dışında bedel seçeneği yoktur ve nedeni yazılır", () => {
    ciz(dosyaVerisi());
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).getByText(BEDEL_YOK_NOTU)).toBeInTheDocument();
    expect(
      within(cozum)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Bulundu", "Aynısı temin edildi", "Kayıttan düşme önerildi"]);
    expect(screen.queryByText(/Bedel belirlendi|Bedel teslim alındı/)).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/borç|ceza|zayi/i);
  });

  it("çözüm onaydan geçer: başlık soru, gövde sonuç; İşle sunucuya yalnız çözümü yollar", async () => {
    const user = userEvent.setup();
    const { onDegisti } = ciz(dosyaVerisi());
    await user.click(screen.getByRole("button", { name: "Bulundu" }));

    const onay = screen.getByRole("dialog", { name: "“Bulundu” işlensin mi?" });
    expect(onay).toHaveTextContent("Nüsha rafa döner ve dosya kapanır.");
    expect(screen.queryByLabelText(/piyasa bedeli/)).not.toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "İşle" }));

    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "FOUND_RETURNED" }),
    );
    expect(onDegisti).toHaveBeenCalledTimes(1);
    // Kapanan dosyada çözüm bölümü kalmaz; kapanış tarihi görünür.
    expect(await screen.findByRole("dialog", { name: "Kayıp dosyası" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Çözüm" })).not.toBeInTheDocument();
    expect(screen.getByText("Kapanış")).toBeInTheDocument();
  });

  it("onay kipinden Vazgeç ayrıntıya döner, istek gitmez", async () => {
    const user = userEvent.setup();
    ciz(dosyaVerisi());
    await user.click(screen.getByRole("button", { name: "Kayıttan düşme önerildi" }));
    expect(
      screen.getByRole("dialog", { name: "“Kayıttan düşme önerildi” işlensin mi?" }),
    ).toHaveTextContent("kayıttan düşme ayrı bir işlemdir");
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("dialog", { name: "Kayıp dosyası" })).toBeInTheDocument();
    expect(kayip.coz).not.toHaveBeenCalled();
  });

  it("ortaöğretimde “Bedel belirlendi” piyasa bedelini ister ve yalnız kayıt olarak yollar", async () => {
    const user = userEvent.setup();
    ciz(dosyaVerisi({ allowed_resolutions: ORTAOGRETIM, price_options_available: true }));
    expect(screen.queryByText(BEDEL_YOK_NOTU)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bedel belirlendi" }));

    const onay = screen.getByRole("dialog", { name: "“Bedel belirlendi” işlensin mi?" });
    expect(onay).toHaveTextContent("Program tahsilat yapmaz; bedel yalnız kayıttır.");
    expect(onay).toHaveTextContent("kişinin kütüphaneyle açık işi sürer");
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    expect(
      await screen.findByText("Bedel kaydı için o günkü piyasa bedelini yazın."),
    ).toBeInTheDocument();
    expect(kayip.coz).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("O günkü piyasa bedeli (TL)"), "125,50");
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, {
        resolution: "PRICE_DETERMINED",
        market_price: "125.50",
      }),
    );
  });

  it("“Bedel teslim alındı” bedel sormaz; sonucu kişinin işinin bittiğini söyler", async () => {
    const user = userEvent.setup();
    ciz(
      dosyaVerisi({
        resolution: "PRICE_DETERMINED",
        resolution_display: "Bedel belirlendi",
        market_price: "80.00",
        price_determined_at: "2026-09-24T10:00:00+03:00",
        price_options_available: true,
        allowed_resolutions: [
          { value: "PRICE_DETERMINED", label: "Bedel belirlendi" },
          { value: "PRICE_RECEIVED", label: "Bedel teslim alındı" },
          { value: "FOUND_RETURNED", label: "Bulundu" },
        ],
      }),
    );
    expect(screen.getByText("Kaydedilen piyasa bedeli")).toBeInTheDocument();
    expect(screen.getByText("Bedel belirlendi", { selector: "dt" })).toBeInTheDocument();
    expect(screen.queryByText(OKULUN_ACIK_ISI_NOTU)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bedel teslim alındı" }));

    const onay = screen.getByRole("dialog", { name: "“Bedel teslim alındı” işlensin mi?" });
    expect(onay).toHaveTextContent("Kişinin kütüphaneyle açık işi biter");
    expect(onay).toHaveTextContent("“Kütüphaneden ilişiği yoktur” belgesi basılabilir");
    expect(onay).toHaveTextContent("Dosya okul için açık kalır");
    expect(onay).toHaveTextContent("Bu adım geri alınmaz");
    expect(screen.queryByLabelText("O günkü piyasa bedeli (TL)")).not.toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "PRICE_RECEIVED" }),
    );
  });

  it("bedeli teslim alınmış dosya okulun açık işidir; bedelle alım bedel sormaz", async () => {
    const user = userEvent.setup();
    ciz(
      dosyaVerisi({
        resolution: "PRICE_RECEIVED",
        resolution_display: "Bedel teslim alındı",
        market_price: "80.00",
        price_determined_at: "2026-09-23T10:00:00+03:00",
        price_received_at: "2026-09-25T10:00:00+03:00",
        is_person_open_work: false,
        price_options_available: true,
        allowed_resolutions: [
          { value: "CLOSED_SAME_REPURCHASED", label: "Bedelle aynısı alındı" },
          { value: "CLOSED_OTHER_REPURCHASED", label: "Bedelle başka eser alındı" },
        ],
      }),
    );
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).getByText(OKULUN_ACIK_ISI_NOTU)).toBeInTheDocument();
    expect(screen.getByText("Bedel teslim alındı", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText("25.09.2026")).toBeInTheDocument();
    // Açık dosyada sorumlu notu hâlâ düzeltilebilir.
    expect(screen.getByRole("button", { name: "Notu kaydet" })).toBeInTheDocument();

    await user.click(within(cozum).getByRole("button", { name: "Bedelle başka eser alındı" }));
    const onay = screen.getByRole("dialog", { name: "“Bedelle başka eser alındı” işlensin mi?" });
    expect(onay).toHaveTextContent("Teslim alınan bedelle başka bir eser alındı.");
    expect(screen.queryByLabelText("O günkü piyasa bedeli (TL)")).not.toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "CLOSED_OTHER_REPURCHASED" }),
    );
  });
});

describe("DosyaAyrintisi — bedelden sonra bulunan kitap (25.09.2026 kullanıcı kararı)", () => {
  const BEDELLI_BULUNMA: Dosya["allowed_resolutions"][number] = {
    value: "FOUND_AFTER_PRICE",
    label: "Bulundu (bedel teslim alınmıştı)",
  };

  it("“Bedel teslim alındı” dosyasında bulunma rafa döndürür; bedelin iadesi okulun kararıdır", async () => {
    const user = userEvent.setup();
    ciz(
      dosyaVerisi({
        resolution: "PRICE_RECEIVED",
        resolution_display: "Bedel teslim alındı",
        market_price: "80.00",
        price_determined_at: "2026-09-23T10:00:00+03:00",
        price_received_at: "2026-09-25T10:00:00+03:00",
        is_person_open_work: false,
        price_options_available: true,
        allowed_resolutions: [
          { value: "CLOSED_SAME_REPURCHASED", label: "Bedelle aynısı alındı" },
          { value: "CLOSED_OTHER_REPURCHASED", label: "Bedelle başka eser alındı" },
          BEDELLI_BULUNMA,
        ],
      }),
    );
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).getByText(BEDEL_IADESI_NOTU)).toBeInTheDocument();
    expect(BEDEL_IADESI_NOTU).toMatch(/okul yönetiminin kararıdır; program para tutmaz\.$/u);

    await user.click(
      within(cozum).getByRole("button", { name: "Bulundu (bedel teslim alınmıştı)" }),
    );
    const onay = screen.getByRole("dialog", {
      name: "“Bulundu (bedel teslim alınmıştı)” işlensin mi?",
    });
    expect(onay).toHaveTextContent("nüsha rafa döner ve dosya kapanır");
    expect(onay).toHaveTextContent(BEDEL_IADESI_NOTU);
    expect(screen.queryByLabelText("O günkü piyasa bedeli (TL)")).not.toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "FOUND_AFTER_PRICE" }),
    );
  });

  it("“Bedelle başka eser alındı” ile kapanmış dosyada kitap bulunursa öneri geri alınır", async () => {
    const user = userEvent.setup();
    ciz(
      dosyaVerisi({
        is_open: false,
        resolution: "CLOSED_OTHER_REPURCHASED",
        resolution_display: "Bedelle başka eser alındı",
        market_price: "80.00",
        price_determined_at: "2026-09-23T10:00:00+03:00",
        price_received_at: "2026-09-24T10:00:00+03:00",
        resolved_at: "2026-09-25T10:00:00+03:00",
        write_off_proposed_at: "2026-09-25T10:00:00+03:00",
        allowed_resolutions: [BEDELLI_BULUNMA],
      }),
    );
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).getByText(BEDELLI_ONERI_GERI_ALMA_NOTU)).toBeInTheDocument();
    expect(within(cozum).queryByText(ONERI_GERI_ALMA_NOTU)).not.toBeInTheDocument();
    expect(within(cozum).getByText(BEDEL_IADESI_NOTU)).toBeInTheDocument();

    await user.click(
      within(cozum).getByRole("button", { name: "Bulundu (bedel teslim alınmıştı)" }),
    );
    const onay = screen.getByRole("dialog", {
      name: "“Bulundu (bedel teslim alınmıştı)” işlensin mi?",
    });
    expect(onay).toHaveTextContent("Kayıttan düşme önerisi geri alınır");
    expect(onay).toHaveTextContent("Bedelle alınan eser kayıtta kalır");
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "FOUND_AFTER_PRICE" }),
    );
  });

  it("nüsha kayıttan düşülmüşse bulunan kitabın yolu “Sayım fazlası” edinimidir", () => {
    ciz(
      dosyaVerisi({
        is_open: false,
        copy_status: "WITHDRAWN_LOST",
        copy_status_display: "Kayıp (kayıttan düşüldü)",
        resolution: "CLOSED_OTHER_REPURCHASED",
        resolution_display: "Bedelle başka eser alındı",
        resolved_at: "2026-09-25T10:00:00+03:00",
        write_off_proposed_at: "2026-09-25T10:00:00+03:00",
        allowed_resolutions: [],
      }),
    );
    expect(screen.queryByRole("region", { name: "Çözüm" })).not.toBeInTheDocument();
    const bolum = screen.getByRole("region", { name: "Bulunan kitap" });
    expect(within(bolum).getByText(KAYITTAN_DUSULMUS_NOTU)).toBeInTheDocument();
    expect(KAYITTAN_DUSULMUS_NOTU).toContain("“Sayım fazlası (kayda giriş)”");
    expect(within(bolum).getByText(BEDEL_IADESI_NOTU)).toBeInTheDocument();
  });

  it("F9: açık dosyanın nüshası sayımda kayıttan düşüldüyse bulunan kitabın yolu yazılır", () => {
    // Sunucu bulunma çözümlerini listeden çıkarır; temin ve bedel yolları kalır.
    ciz(
      dosyaVerisi({
        is_open: true,
        copy_status: "WITHDRAWN_LOST",
        copy_status_display: "Kayıp (kayıttan düşüldü)",
        allowed_resolutions: [{ value: "REPLACED_SAME", label: "Aynısı temin edildi" }],
      }),
    );
    const bolum = screen.getByRole("region", { name: "Bulunan kitap" });
    expect(within(bolum).getByText(SAYIMDA_DUSULMUS_NOTU)).toBeInTheDocument();
    expect(SAYIMDA_DUSULMUS_NOTU).toContain("“Sayım fazlası (kayda giriş)”");
    expect(SAYIMDA_DUSULMUS_NOTU).toContain("“Nüsha ekle”");
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).queryByRole("button", { name: "Bulundu" })).toBeNull();
    expect(within(cozum).getByRole("button", { name: "Aynısı temin edildi" })).toBeInTheDocument();
  });

  it("bedelden sonra bulunmuş dosya bedelin iadesinin okulun kararı olduğunu söyler", () => {
    ciz(
      dosyaVerisi({
        is_open: false,
        copy_status: "AVAILABLE",
        copy_status_display: "Rafta",
        resolution: "FOUND_AFTER_PRICE",
        resolution_display: "Bulundu (bedel teslim alınmıştı)",
        market_price: "80.00",
        price_received_at: "2026-09-24T10:00:00+03:00",
        resolved_at: "2026-09-25T10:00:00+03:00",
        allowed_resolutions: [],
      }),
    );
    expect(screen.getByText(BEDEL_IADESI_NOTU)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Bulunan kitap" })).not.toBeInTheDocument();
  });
});

describe("DosyaAyrintisi — sorumlu notu, onarım ve tutanak", () => {
  it("açık dosyada sorumlu notu kaydedilir", async () => {
    const user = userEvent.setup();
    kayip.notuGuncelle.mockResolvedValue(dosyaVerisi({ responsible_note: "Kütüphane dışı kişi" }));
    ciz(dosyaVerisi());
    const kaydet = screen.getByRole("button", { name: "Notu kaydet" });
    expect(kaydet).toBeDisabled();
    await user.type(screen.getByLabelText("Sorumlu notu"), "Kütüphane dışı kişi");
    await user.click(kaydet);
    await waitFor(() => expect(kayip.notuGuncelle).toHaveBeenCalledWith(5, "Kütüphane dışı kişi"));
  });

  it("hasar dosyasında raftaki nüsha onaydan geçerek onarıma gönderilir", async () => {
    const user = userEvent.setup();
    const hasar = dosyaVerisi({
      case_type: "DAMAGED",
      case_type_display: "Hasar",
      copy_status: "AVAILABLE",
      copy_status_display: "Rafta",
      allowed_resolutions: [{ value: "REPAIRED", label: "Onarıldı" }],
    });
    kayip.onarimaGonder.mockResolvedValue({ message: "Nüsha onarıma gönderildi.", repair: null });
    kayip.getir.mockResolvedValue({
      ...hasar,
      copy_status: "IN_REPAIR",
      copy_status_display: "Onarımda",
    });
    const { onDegisti } = ciz(hasar);

    await user.click(screen.getByRole("button", { name: "Onarıma gönder" }));
    const onay = screen.getByRole("dialog", { name: "Nüsha onarıma gönderilsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(kayip.onarimaGonder).toHaveBeenCalledWith(11));
    expect(kayip.getir).toHaveBeenCalledWith(5);
    expect(onDegisti).toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: "Onarımdan dön" })).toBeInTheDocument();
  });

  it("onarımdan dönüş dosyayı kendiliğinden kapatmadığını söyler", async () => {
    const user = userEvent.setup();
    const hasar = dosyaVerisi({
      case_type: "DAMAGED",
      case_type_display: "Hasar",
      copy_status: "IN_REPAIR",
      copy_status_display: "Onarımda",
    });
    kayip.onarimdanDon.mockResolvedValue({
      message: "Nüsha onarımdan döndü; rafta.",
      repair: null,
    });
    kayip.getir.mockResolvedValue({ ...hasar, copy_status: "AVAILABLE" });
    ciz(hasar);
    await user.click(screen.getByRole("button", { name: "Onarımdan dön" }));
    const onay = screen.getByRole("dialog", { name: "Nüsha onarımdan dönsün mü?" });
    expect(onay).toHaveTextContent("Hasar dosyası kendiliğinden kapanmaz");
    await user.click(within(onay).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(kayip.onarimdanDon).toHaveBeenCalledWith(11));
  });

  it("öneriyle kapanan kayıp dosyasında sunucu “Bulundu”yu verirse düğme ve açıklama çıkar", async () => {
    const user = userEvent.setup();
    const { onDegisti } = ciz(
      dosyaVerisi({
        is_open: false,
        resolution: "WRITE_OFF_PROPOSED",
        resolution_display: "Kayıttan düşme önerildi",
        resolved_at: "2026-09-25T10:00:00+03:00",
        write_off_proposed_at: "2026-09-25T10:00:00+03:00",
        allowed_resolutions: [{ value: "FOUND_RETURNED", label: "Bulundu" }],
      }),
    );
    const cozum = screen.getByRole("region", { name: "Çözüm" });
    expect(within(cozum).getByText(ONERI_GERI_ALMA_NOTU)).toBeInTheDocument();
    // Kapanmış dosyada bedel notu ve not düzeltme yoktur.
    expect(within(cozum).queryByText(BEDEL_YOK_NOTU)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notu kaydet" })).not.toBeInTheDocument();

    await user.click(within(cozum).getByRole("button", { name: "Bulundu" }));
    const onay = screen.getByRole("dialog", { name: "“Bulundu” işlensin mi?" });
    expect(onay).toHaveTextContent("Kayıttan düşme önerisi geri alınır");
    await user.click(within(onay).getByRole("button", { name: "İşle" }));
    await waitFor(() =>
      expect(kayip.coz).toHaveBeenCalledWith(5, { resolution: "FOUND_RETURNED" }),
    );
    expect(onDegisti).toHaveBeenCalledTimes(1);
  });

  it("kapanmış dosyada çözüm yoktur, not salt okunur; tutanak indirilir", async () => {
    const user = userEvent.setup();
    ciz(
      dosyaVerisi({
        is_open: false,
        resolution: "WRITE_OFF_PROPOSED",
        resolution_display: "Kayıttan düşme önerildi",
        resolved_at: "2026-09-25T10:00:00+03:00",
        write_off_proposed_at: "2026-09-25T10:00:00+03:00",
        responsible_note: "Kısa not",
        allowed_resolutions: [],
      }),
    );
    expect(screen.queryByRole("region", { name: "Çözüm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notu kaydet" })).not.toBeInTheDocument();
    expect(screen.getByText("Kısa not")).toBeInTheDocument();
    expect(screen.getByText("Kayıttan düşme önerisi")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(saveBlobMock).toHaveBeenCalled());
    expect(kayip.tutanakPdf).toHaveBeenCalledWith(5);
    expect(saveBlobMock.mock.calls[0][1]).toBe("Kayıp-hasar-tutanağı_2026-000123_24.09.2026.pdf");
  });
});

describe("yardımcılar", () => {
  it("bedel metni sunucunun ondalık biçimine çevrilir", () => {
    expect(bedelMetni("125,50")).toBe("125.50");
    expect(bedelMetni("1.250,5")).toBe("1250.50");
    expect(bedelMetni("125.50")).toBe("125.50");
    expect(bedelMetni("1.250")).toBe("1250.00");
    expect(bedelMetni(" 90 ")).toBe("90.00");
    expect(bedelMetni("0")).toBeNull();
    expect(bedelMetni("-5")).toBeNull();
    expect(bedelMetni("abc")).toBeNull();
    expect(bedelMetni("")).toBeNull();
  });

  it("her çözümün sonucu yazılıdır ve tahsilat dili içermez", () => {
    const cozumler: Cozum[] = [
      "PRICE_DETERMINED",
      "PRICE_RECEIVED",
      "FOUND_RETURNED",
      "REPLACED_SAME",
      "REPAIRED",
      "CLOSED_SAME_REPURCHASED",
      "CLOSED_OTHER_REPURCHASED",
      "FOUND_AFTER_PRICE",
      "WRITE_OFF_PROPOSED",
    ];
    for (const tur of ["LOST", "DAMAGED"] as const) {
      for (const c of cozumler) {
        const metin = cozumSonucu(c, { case_type: tur });
        expect(metin.length).toBeGreaterThan(20);
        expect(metin).not.toMatch(/borç|ceza|tahsil edil/i);
      }
    }
    expect(cozumSonucu("PENDING", { case_type: "LOST" })).toBe("");
  });

  it("öneri sonucunda bulunma yolunun hangi düğmeyle açık kaldığı yazar", () => {
    expect(cozumSonucu("WRITE_OFF_PROPOSED", { case_type: "LOST" })).toContain(
      "“Bulundu” seçilir; öneri geri alınır",
    );
    // 25.09.2026 kullanıcı kararı (F8 ekleri 14): "Bedelle başka eser alındı"dan sonra da
    // nüsha kayıttan düşülmemişse kitap rafa döner.
    expect(cozumSonucu("CLOSED_OTHER_REPURCHASED", { case_type: "LOST" })).toContain(
      "henüz kayıttan düşülmemişse bu dosyada “Bulundu (bedel teslim alınmıştı)” seçilir",
    );
    expect(cozumSonucu("CLOSED_OTHER_REPURCHASED", { case_type: "LOST" })).not.toContain(
      "seçilemez",
    );
    expect(cozumSonucu("CLOSED_OTHER_REPURCHASED", { case_type: "DAMAGED" })).not.toContain(
      "Bulundu",
    );
    expect(cozumSonucu("PRICE_RECEIVED", { case_type: "LOST" })).toContain(
      "kitap bulunursa “Bulundu (bedel teslim alınmıştı)”",
    );
    expect(cozumSonucu("PRICE_RECEIVED", { case_type: "DAMAGED" })).not.toContain("Bulundu");
    expect(cozumSonucu("FOUND_RETURNED", { case_type: "LOST", is_open: false })).toContain(
      "önerisi geri alınır",
    );
    expect(cozumSonucu("FOUND_AFTER_PRICE", { case_type: "LOST", is_open: false })).toContain(
      "önerisi geri alınır",
    );
    expect(cozumSonucu("FOUND_AFTER_PRICE", { case_type: "LOST" })).toContain(BEDEL_IADESI_NOTU);
  });
});
