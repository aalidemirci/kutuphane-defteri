// Kapalı Günler paneli testi: yıl seçimi, tür ve "tahmini" rozetleri, resmî ve dini
// tatil tohumlama, onaylı silme, öğrenciye kapalı gün aralığı ekleme ve sihirbazda
// yeniden kullanım için denetimli kip. Metinler sözlüğe uyar: ara tatil "öğrenciye
// kapalı gün"dür, kaydırma "Md. 18 gereği" diye sunulmaz.

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { Holiday } from "../okul/api";

const oapi = vi.hoisted(() => ({
  listHolidays: vi.fn(),
  createHoliday: vi.fn(),
  deleteHoliday: vi.fn(),
  seedHolidays: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: oapi };
});

// "Bugün" sabitlenir: varsayılan yıl ve yıl seçenekleri buradan türer.
vi.mock("../../lib/format", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/format")>();
  return { ...actual, todayIso: () => "2026-09-22" };
});

import KapaliGunlerPaneli from "./KapaliGunlerPaneli";
import type { KapaliGunlerPaneliProps } from "./KapaliGunlerPaneli";

const CUMHURIYET: Holiday = {
  id: 1,
  name: "Cumhuriyet Bayramı",
  start_date: "2026-10-29",
  end_date: "2026-10-29",
  kind: "OFFICIAL",
  is_estimated: false,
};

const ARA_TATIL: Holiday = {
  id: 2,
  name: "1. dönem ara tatili",
  start_date: "2026-11-09",
  end_date: "2026-11-13",
  kind: "SCHOOL_BREAK",
  is_estimated: false,
};

const RAMAZAN_2027: Holiday = {
  id: 3,
  name: "Ramazan Bayramı",
  start_date: "2027-03-09",
  end_date: "2027-03-11",
  kind: "RELIGIOUS",
  is_estimated: true,
};

function ekranaBas(props: KapaliGunlerPaneliProps = {}) {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <KapaliGunlerPaneli {...props} />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

const tarihGir = (etiket: RegExp, deger: string) =>
  fireEvent.change(screen.getByLabelText(etiket), { target: { value: deger } });

beforeEach(() => {
  oapi.listHolidays.mockImplementation((yil: number) =>
    Promise.resolve(yil === 2027 ? [RAMAZAN_2027] : [CUMHURIYET, ARA_TATIL]),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("KapaliGunlerPaneli — liste", () => {
  it("bu yılı listeler; tür rozetleri ve tarih aralığı gg.aa.yyyy yazılır", async () => {
    ekranaBas();

    const liste = await screen.findByRole("list", { name: "2026 kapalı günleri" });
    expect(oapi.listHolidays).toHaveBeenCalledWith(2026);
    expect(within(liste).getByText("Cumhuriyet Bayramı")).toBeInTheDocument();
    expect(within(liste).getByText("Resmî tatil")).toBeInTheDocument();
    expect(within(liste).getByText("Öğrenciye kapalı gün")).toBeInTheDocument();
    expect(within(liste).getByText("29.10.2026")).toBeInTheDocument();
    expect(within(liste).getByText("09.11.2026 – 13.11.2026 · 5 gün")).toBeInTheDocument();
    // Kesin tarihli yılda "tahmini" notu çıkmaz.
    expect(screen.queryByText("tahmini")).toBeNull();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("yıl seçilince o yıl yüklenir; tahmini bayram rozet ve açıklamayla gösterilir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");

    await user.selectOptions(screen.getByLabelText("Yıl"), "2027");

    expect(await screen.findByText("Ramazan Bayramı")).toBeInTheDocument();
    expect(oapi.listHolidays).toHaveBeenLastCalledWith(2027);
    expect(screen.getByText("tahmini")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Diyanet takvimi kesinleşince kontrol edin/);
  });

  it("yıl seçenekleri geçen yıldan iki yıl sonrasına uzanır", async () => {
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    const secenekler = within(screen.getByLabelText("Yıl"))
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(secenekler).toEqual(["2025", "2026", "2027", "2028"]);
  });

  it("boş yıl kullanıcıya ne yapacağını söyler", async () => {
    oapi.listHolidays.mockResolvedValue([]);
    ekranaBas();
    expect(
      await screen.findByText(/2026 yılı için kayıtlı kapalı gün yok\. Resmî ve dini tatilleri/),
    ).toBeInTheDocument();
  });

  it("yükleme hatası bantta gösterilir", async () => {
    oapi.listHolidays.mockRejectedValue(new ApiError(500, "server_error", "Liste okunamadı."));
    ekranaBas();
    expect(await screen.findByRole("alert")).toHaveTextContent("Liste okunamadı.");
  });

  it("metinler kaydırmayı “Md. 18 gereği” diye sunmaz, ara tatile yalın “tatil” demez", async () => {
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    expect(document.body.textContent).not.toMatch(/Md\. ?18/);
    expect(screen.getByText(/öğrenciye kapalı gün olarak ayrı tutulur/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Kapalı Günler" })).toBeInTheDocument();
  });
});

describe("KapaliGunlerPaneli — resmî ve dini tatilleri ekle", () => {
  it("seçili yılı tohumlar, sonucu bildirir ve listeyi yeniler", async () => {
    oapi.seedHolidays.mockResolvedValue({
      year: 2026,
      created: 9,
      skipped: 0,
      religious_available: true,
    });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");

    await user.click(screen.getByRole("button", { name: /Resmî ve dini tatilleri ekle/ }));

    expect(oapi.seedHolidays).toHaveBeenCalledWith(2026);
    expect(await screen.findByText("2026 yılı için 9 kayıt eklendi.")).toBeInTheDocument();
    await waitFor(() => expect(oapi.listHolidays).toHaveBeenCalledTimes(2));
  });

  it("ikinci tohumlamada kopya olmadığını söyler", async () => {
    oapi.seedHolidays.mockResolvedValue({
      year: 2026,
      created: 0,
      skipped: 9,
      religious_available: true,
    });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: /Resmî ve dini tatilleri ekle/ }));
    expect(
      await screen.findByText("2026 yılının resmî ve dini tatilleri zaten listede."),
    ).toBeInTheDocument();
  });

  it("programda dini bayram tarihi olmayan yılda kalıcı uyarı gösterir", async () => {
    oapi.seedHolidays.mockResolvedValue({
      year: 2026,
      created: 7,
      skipped: 0,
      religious_available: false,
    });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: /Resmî ve dini tatilleri ekle/ }));

    const bant = await screen.findByRole("status", { name: "Dini bayram tarihleri eklenemedi" });
    expect(bant).toHaveTextContent(/Diyanet takvimine bakarak/);
    await user.click(within(bant).getByRole("button", { name: "Kapat" }));
    expect(screen.queryByRole("status", { name: "Dini bayram tarihleri eklenemedi" })).toBeNull();
  });

  it("tohumlama hatası bantta gösterilir", async () => {
    oapi.seedHolidays.mockRejectedValue(
      new ApiError(400, "validation_error", "Yıl 2000 ile 2100 arasında olmalıdır."),
    );
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: /Resmî ve dini tatilleri ekle/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("arasında olmalıdır");
  });
});

describe("KapaliGunlerPaneli — silme", () => {
  it("silme onay diyaloğundan geçer; başlık soru, gövde sonuçtur", async () => {
    oapi.deleteHoliday.mockResolvedValue(undefined);
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("1. dönem ara tatili");

    await user.click(screen.getByRole("button", { name: "1. dönem ara tatili kaydını sil" }));
    const onay = await screen.findByRole("dialog", { name: "Kapalı gün silinsin mi?" });
    expect(onay).toHaveTextContent(/09\.11\.2026 – 13\.11\.2026/);
    expect(onay).toHaveTextContent(/açık gün sayılır/);
    await user.click(within(onay).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(oapi.deleteHoliday).toHaveBeenCalledWith(2));
    expect(await screen.findByText("Kapalı gün silindi.")).toBeInTheDocument();
  });

  it("vazgeçilirse silinmez", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: "Cumhuriyet Bayramı kaydını sil" }));
    const onay = await screen.findByRole("dialog", { name: "Kapalı gün silinsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(oapi.deleteHoliday).not.toHaveBeenCalled();
  });

  it("silme hatası bildirilir", async () => {
    oapi.deleteHoliday.mockRejectedValue(new ApiError(404, "not_found", "Kayıt bulunamadı."));
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: "Cumhuriyet Bayramı kaydını sil" }));
    const onay = await screen.findByRole("dialog", { name: "Kapalı gün silinsin mi?" });
    await user.click(within(onay).getByRole("button", { name: "Sil" }));
    expect(await screen.findByText("Kayıt bulunamadı.")).toBeInTheDocument();
  });
});

describe("KapaliGunlerPaneli — ekleme", () => {
  it("varsayılan tür öğrenciye kapalı gündür; aralık gönderilir", async () => {
    oapi.createHoliday.mockResolvedValue({ ...ARA_TATIL, id: 9, name: "Yarıyıl tatili" });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");

    expect(screen.getByLabelText("Tür")).toHaveValue("SCHOOL_BREAK");
    expect(screen.getByText(/Kanunen tatil değildir, mesai sürer/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Ad/), "Yarıyıl tatili");
    tarihGir(/^Başlangıç/, "2026-12-28");
    tarihGir(/^Bitiş/, "2026-12-31");
    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(oapi.createHoliday).toHaveBeenCalledWith({
        name: "Yarıyıl tatili",
        start_date: "2026-12-28",
        end_date: "2026-12-31",
        kind: "SCHOOL_BREAK",
      }),
    );
    expect(await screen.findByText("Kapalı gün eklendi.")).toBeInTheDocument();
  });

  it("bitiş boşsa tek gün sayılır; tür değiştirilebilir", async () => {
    oapi.createHoliday.mockResolvedValue({ ...CUMHURIYET, id: 10, kind: "OTHER" });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");

    await user.type(screen.getByLabelText(/^Ad/), "İdari izin");
    await user.selectOptions(screen.getByLabelText("Tür"), "OTHER");
    tarihGir(/^Başlangıç/, "2026-12-31");
    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() =>
      expect(oapi.createHoliday).toHaveBeenCalledWith({
        name: "İdari izin",
        start_date: "2026-12-31",
        end_date: "2026-12-31",
        kind: "OTHER",
      }),
    );
  });

  it("boş formda istek atılmaz, eksik alanlar işaretlenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.click(screen.getByRole("button", { name: "Ekle" }));
    expect(await screen.findByText("Ad yazılmalıdır.")).toBeInTheDocument();
    expect(screen.getByText("Başlangıç tarihi seçilmelidir.")).toBeInTheDocument();
    expect(oapi.createHoliday).not.toHaveBeenCalled();
  });

  it("backend alan hatası ilgili alanın altına yazılır", async () => {
    oapi.createHoliday.mockRejectedValue(
      new ApiError(400, "validation_error", "Bitiş tarihi başlangıçtan önce olamaz.", {
        end_date: ["Bitiş tarihi başlangıçtan önce olamaz."],
      }),
    );
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.type(screen.getByLabelText(/^Ad/), "Ters");
    tarihGir(/^Başlangıç/, "2026-11-13");
    tarihGir(/^Bitiş/, "2026-11-09");
    await user.click(screen.getByRole("button", { name: "Ekle" }));
    expect(await screen.findByText("Bitiş tarihi başlangıçtan önce olamaz.")).toBeInTheDocument();
  });

  it("alan dışı backend hatası form bandında gösterilir", async () => {
    oapi.createHoliday.mockRejectedValue(new ApiError(423, "locked", "Program kilitli."));
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.type(screen.getByLabelText(/^Ad/), "Ara tatil");
    tarihGir(/^Başlangıç/, "2026-11-09");
    await user.click(screen.getByRole("button", { name: "Ekle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Program kilitli.");
  });

  it("başka yıla düşen kayıt eklenince o yıla geçilir", async () => {
    oapi.createHoliday.mockResolvedValue({
      ...ARA_TATIL,
      id: 11,
      name: "Yarıyıl tatili",
      start_date: "2027-01-25",
      end_date: "2027-02-05",
    });
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Cumhuriyet Bayramı");
    await user.type(screen.getByLabelText(/^Ad/), "Yarıyıl tatili");
    tarihGir(/^Başlangıç/, "2027-01-25");
    tarihGir(/^Bitiş/, "2027-02-05");
    await user.click(screen.getByRole("button", { name: "Ekle" }));

    await waitFor(() => expect(oapi.listHolidays).toHaveBeenLastCalledWith(2027));
    expect(screen.getByLabelText("Yıl")).toHaveValue("2027");
  });
});

describe("KapaliGunlerPaneli — sihirbazda yeniden kullanım", () => {
  it("yıl dışarıdan verilir, tek yılda seçici ve başlık gizlenir, yazma haber verilir", async () => {
    oapi.seedHolidays.mockResolvedValue({
      year: 2027,
      created: 9,
      skipped: 0,
      religious_available: true,
    });
    const onDegisti = vi.fn();
    const user = userEvent.setup();
    ekranaBas({ yil: 2027, yillar: [2027], baslikGizli: true, onDegisti });

    expect(await screen.findByText("Ramazan Bayramı")).toBeInTheDocument();
    expect(oapi.listHolidays).toHaveBeenCalledWith(2027);
    expect(screen.queryByLabelText("Yıl")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Kapalı Günler" })).toBeNull();

    await user.click(screen.getByRole("button", { name: /Resmî ve dini tatilleri ekle/ }));
    await waitFor(() => expect(onDegisti).toHaveBeenCalledTimes(1));
    expect(oapi.seedHolidays).toHaveBeenCalledWith(2027);
  });

  it("denetimli kipte yıl seçimi çağırana bildirilir", async () => {
    const onYilChange = vi.fn();
    const user = userEvent.setup();
    ekranaBas({ yil: 2026, yillar: [2026, 2027], onYilChange });
    await screen.findByText("Cumhuriyet Bayramı");

    await user.selectOptions(screen.getByLabelText("Yıl"), "2027");

    expect(onYilChange).toHaveBeenCalledWith(2027);
    // Denetimli: çağıran `yil`'i değiştirmedikçe gösterilen yıl aynı kalır.
    expect(oapi.listHolidays).toHaveBeenLastCalledWith(2026);
  });
});
