// AyarlarPage testi: ders yılları + kapalı günler + şube kataloğu + okul bilgileri
// (hazırlık sınıfı dahil) + güvenlik sekmesinin varlığı. Güvenlik ve kapalı gün
// panellerinin kendi davranışı modules/guvenlik ve modules/takvim testlerinde;
// burada yalnız sekme kablolaması doğrulanır.
// Kaldırılan sekmeler (ders saatleri, zümreler, şube kümeleri) ve okul türü/
// çizelge/ayrışma alanları geri gelmesin diye ayrıca sabitlenir.

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { ClassSection, SchoolYear } from "../okul/api";

const oapi = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getSchoolConfig: vi.fn(),
  updateSchoolConfig: vi.fn(),
  getGradeLevels: vi.fn(),
  listSchoolYears: vi.fn(),
  createSchoolYear: vi.fn(),
  activateSchoolYear: vi.fn(),
  listSchoolTerms: vi.fn(),
  configureSchoolTerms: vi.fn(),
  listClassSections: vi.fn(),
  createClassSection: vi.fn(),
  deleteClassSection: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: oapi };
});

// Güvenlik paneli kendi API'sine gider; bu testte içeriği önemsizdir.
vi.mock("../guvenlik/GuvenlikAyarlari", () => ({
  default: () => <div>GÜVENLİK PANELİ</div>,
}));

// Kapalı gün paneli kendi testinde; burada yalnız sekmeye bağlandığı doğrulanır.
vi.mock("../takvim/KapaliGunlerPaneli", () => ({
  default: () => <div>KAPALI GÜNLER PANELİ</div>,
}));

import AyarlarPage from "./AyarlarPage";

const AKTIF_YIL: SchoolYear = {
  id: 3,
  name: "2026-2027",
  start_date: "2026-09-01",
  end_date: "2027-06-30",
  is_active: true,
};

const PASIF_YIL: SchoolYear = {
  id: 4,
  name: "2027-2028",
  start_date: "2027-09-01",
  end_date: "2028-06-30",
  is_active: false,
};

const SUBE: ClassSection = {
  id: 11,
  school_year: 3,
  school_year_name: "2026-2027",
  class_level: 10,
  class_section: "A",
  class_label: "10/A",
};

function renderPage(yol = "/ayarlar") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <AyarlarPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  oapi.listSchoolYears.mockResolvedValue([AKTIF_YIL, PASIF_YIL]);
  oapi.getSchoolConfig.mockResolvedValue({
    school_name: "Örnek Anadolu Lisesi",
    province: "İstanbul",
    district: "Örnek",
    principal_name: "",
    has_prep_class: false,
    kademe: "ORTAOGRETIM",
    kisa_ad: "Örnek AL",
    demirbas_onayi: true,
    demirbas_no: "",
    setup_completed: true,
  });
  oapi.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9" },
      { value: 10, label: "10" },
    ],
    prep_enabled: false,
  });
  oapi.listSchoolTerms.mockResolvedValue([]);
  oapi.listClassSections.mockResolvedValue([SUBE]);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AyarlarPage — sekmeler", () => {
  it("altı sekme vardır; kaldırılan sekmeler geri gelmez", async () => {
    renderPage();
    await screen.findByText("2026-2027");
    expect(screen.getAllByRole("tab").map((t) => t.textContent?.trim())).toEqual([
      expect.stringContaining("Ders Yılları"),
      expect.stringContaining("Kapalı Günler"),
      expect.stringContaining("Şubeler"),
      expect.stringContaining("Okul Bilgileri"),
      expect.stringContaining("Güvenlik"),
      expect.stringContaining("Güncelleme"),
    ]);
    for (const ad of [/Ders Saatleri/, /Zümreler/, /Şube Kümeleri/, /Tatiller/]) {
      expect(screen.queryByRole("tab", { name: ad })).toBeNull();
    }
  });

  it("kaldırılmış bir sekmenin adresi sessizce Ders Yılları sekmesine düşer", async () => {
    renderPage("/ayarlar?tab=zumreler");
    expect(await screen.findByText("2026-2027")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Ders Yılları/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("“Diğer ayarlar”da yalnız kurulum sihirbazı bağlantısı kalır", async () => {
    renderPage();
    await screen.findByText("2026-2027");
    expect(screen.getByRole("link", { name: /Kurulum Sihirbazı/ })).toHaveAttribute(
      "href",
      "/kurulum",
    );
    expect(screen.queryByRole("link", { name: /Ders Havuzu/ })).toBeNull();
  });
});

describe("AyarlarPage — ders yılları", () => {
  it("yılları listeler, aktif olanı rozetler; pasif yıl aktifleştirilebilir", async () => {
    oapi.activateSchoolYear.mockResolvedValue(PASIF_YIL);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("2026-2027")).toBeInTheDocument();
    expect(screen.getByText("Aktif")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Aktifleştir/ }));
    const onay = await screen.findByRole("dialog", { name: "Ders yılı aktifleştirilsin mi?" });
    // Onay gövdesi sonucu söyler; kaldırılan modüllerden söz etmez.
    expect(within(onay).getByText(/e-Okul aktarımlarında görülen şubeler/)).toBeInTheDocument();
    expect(within(onay).queryByText(/sınav|ders havuzu/i)).toBeNull();
    await user.click(within(onay).getByRole("button", { name: "Aktifleştir" }));

    await waitFor(() => expect(oapi.activateSchoolYear).toHaveBeenCalledWith(4));
  });

  it("yeni ders yılı oluşturulur ve dönemleri kaydedilir", async () => {
    oapi.createSchoolYear.mockResolvedValue({ ...PASIF_YIL, id: 9, name: "2028-2029" });
    oapi.configureSchoolTerms.mockResolvedValue([]);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("2026-2027");

    await user.type(screen.getByLabelText(/Ders yılı adı/), "2028-2029");
    // Tarih alanları klavyeyle değil doğrudan değerle doldurulur (jsdom tarih girdisi).
    const tarih = (etiket: RegExp, deger: string) =>
      fireEvent.change(screen.getByLabelText(etiket), { target: { value: deger } });
    tarih(/^Başlangıç/, "2028-09-01");
    tarih(/^Bitiş/, "2029-06-30");
    tarih(/^1\. dönem bitişi/, "2029-01-16");
    tarih(/^2\. dönem başlangıcı/, "2029-02-02");
    await user.click(screen.getByRole("button", { name: "Ders yılı oluştur" }));

    await waitFor(() =>
      expect(oapi.createSchoolYear).toHaveBeenCalledWith({
        name: "2028-2029",
        start_date: "2028-09-01",
        end_date: "2029-06-30",
      }),
    );
    await waitFor(() =>
      expect(oapi.configureSchoolTerms).toHaveBeenCalledWith(9, {
        first_term_end: "2029-01-16",
        second_term_start: "2029-02-02",
      }),
    );
  });

  it("boş formda istek atılmaz, eksik alanlar işaretlenir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("2026-2027");

    await user.click(screen.getByRole("button", { name: "Ders yılı oluştur" }));

    expect(await screen.findByText("Ders yılı adı yazılmalıdır.")).toBeInTheDocument();
    expect(oapi.createSchoolYear).not.toHaveBeenCalled();
  });
});

describe("AyarlarPage — şubeler", () => {
  it("şube kataloğunu listeler ve yeni şube ekler", async () => {
    oapi.createClassSection.mockResolvedValue({ ...SUBE, id: 12, class_section: "B" });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Şubeler/ }));
    expect(await screen.findByText("10/A")).toBeInTheDocument();
    // Katalog tarifi kaldırılan salon/sınav özelliklerinden söz etmez.
    expect(screen.getByText(/aktarımında görülen şubeler buraya/)).toBeInTheDocument();
    expect(screen.queryByText(/[Ss]alon|sınav duyurusu/)).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Şube"), "B");
    await user.click(screen.getByRole("button", { name: "Şube ekle" }));

    await waitFor(() =>
      expect(oapi.createClassSection).toHaveBeenCalledWith({
        school_year: 3,
        class_level: 9,
        class_section: "B",
      }),
    );
  });

  it("şube kaldırma onaydan geçer", async () => {
    oapi.deleteClassSection.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Şubeler/ }));
    await screen.findByText("10/A");

    await user.click(screen.getByRole("button", { name: "10/A şubesini kaldır" }));
    const onay = await screen.findByRole("dialog", { name: "Şube katalogdan kaldırılsın mı?" });
    await user.click(within(onay).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(oapi.deleteClassSection).toHaveBeenCalledWith(11));
  });
});

describe("AyarlarPage — okul bilgileri", () => {
  it("künyeyi yükler ve kaydedince künyeyi, hazırlık bayrağını, kademeyi ve demirbaşı gönderir", async () => {
    oapi.updateSchoolConfig.mockResolvedValue({});
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    expect(await screen.findByLabelText(/Okul adı/)).toHaveValue("Örnek Anadolu Lisesi");
    // Kaldırılan alanlar formda yoktur (API sözleşmesi, F0 temizliği).
    for (const etiket of [/Okul türü/, /ders saati/i, /ayrışma/i]) {
      expect(screen.queryByLabelText(etiket)).toBeNull();
    }
    expect(screen.queryByText(/çizelge/i)).toBeNull();

    await user.selectOptions(screen.getByLabelText("Hazırlık sınıfı"), "1");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(oapi.updateSchoolConfig).toHaveBeenCalledWith({
        school_name: "Örnek Anadolu Lisesi",
        province: "İstanbul",
        district: "Örnek",
        principal_name: "",
        has_prep_class: true,
        kademe: "ORTAOGRETIM",
        kisa_ad: "Örnek AL",
        demirbas_onayi: true,
        demirbas_no: "",
      }),
    );
    expect(await screen.findByText("Okul bilgileri kaydedildi.")).toBeInTheDocument();
  });

  it("kademe, kısa ad ve bilgisayarın demirbaş no'su düzenlenir", async () => {
    oapi.updateSchoolConfig.mockResolvedValue({});
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    expect(await screen.findByLabelText(/^Kademe/)).toHaveValue("ORTAOGRETIM");
    expect(screen.getByLabelText(/^Kısa ad/)).toHaveValue("Örnek AL");
    expect(screen.getByRole("checkbox", { name: /Bu bilgisayar okul demirbaşıdır/ })).toBeChecked();

    await user.selectOptions(screen.getByLabelText(/^Kademe/), "ORTAOKUL");
    await user.clear(screen.getByLabelText(/^Kısa ad/));
    await user.type(screen.getByLabelText(/^Kısa ad/), "Örnek OO");
    await user.type(screen.getByLabelText("Bilgisayarın demirbaş no'su"), "BLG-17");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(oapi.updateSchoolConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          kademe: "ORTAOKUL",
          kisa_ad: "Örnek OO",
          demirbas_onayi: true,
          demirbas_no: "BLG-17",
        }),
      ),
    );
  });

  it("kurulumdan sonra zorunlu alanlar boşaltılamaz (sihirbazla aynı kural)", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    const kademe = await screen.findByLabelText(/^Kademe/);
    // Kayıtlı kademe varken boş seçenek sunulmaz.
    expect(within(kademe).queryByRole("option", { name: "Seçin" })).toBeNull();

    await user.clear(screen.getByLabelText(/^Kısa ad/));
    await user.click(screen.getByRole("checkbox", { name: /Bu bilgisayar okul demirbaşıdır/ }));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Zorunlu alanları doldurun.")).toBeInTheDocument();
    expect(screen.getByText("Kısa ad zorunludur.")).toBeInTheDocument();
    expect(
      screen.getByText("Program yalnız okul demirbaşı bilgisayara kurulur; onay zorunludur."),
    ).toBeInTheDocument();
    expect(oapi.updateSchoolConfig).not.toHaveBeenCalled();
  });

  it("kademe hiç kaydedilmemişse seçici boş seçenekle açılır", async () => {
    oapi.getSchoolConfig.mockResolvedValue({
      school_name: "Örnek Anadolu Lisesi",
      province: "",
      district: "",
      principal_name: "",
      has_prep_class: false,
      kademe: "",
      kisa_ad: "",
      demirbas_onayi: false,
      demirbas_no: "",
      setup_completed: false,
    });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    const kademe = await screen.findByLabelText(/^Kademe/);
    expect(kademe).toHaveValue("");
    expect(within(kademe).getByRole("option", { name: "Seçin" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Kademe seçin.")).toBeInTheDocument();
    expect(oapi.updateSchoolConfig).not.toHaveBeenCalled();
  });

  it("kaydetme hatası bantta gösterilir", async () => {
    oapi.updateSchoolConfig.mockRejectedValue(
      new ApiError(500, "server_error", "Kayıt yazılamadı."),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    await screen.findByLabelText(/Okul adı/);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Kayıt yazılamadı.")).toBeInTheDocument();
  });

  it("alan hatası ilgili alanın altına yazılır", async () => {
    oapi.updateSchoolConfig.mockRejectedValue(
      new ApiError(400, "validation_error", "Girdiğiniz bilgileri kontrol edin.", {
        school_name: ["Okul adı zorunludur."],
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: /Okul Bilgileri/ }));
    await user.clear(await screen.findByLabelText(/Okul adı/));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Okul adı zorunludur.")).toBeInTheDocument();
  });
});

describe("AyarlarPage — kapalı günler", () => {
  it("“Kapalı Günler” sekmesi paneli gösterir", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: /Kapalı Günler/ }));
    expect(await screen.findByText("KAPALI GÜNLER PANELİ")).toBeInTheDocument();
  });

  it("?tab=kapali-gunler adresi sekmeyi seçili açar", async () => {
    renderPage("/ayarlar?tab=kapali-gunler");
    expect(await screen.findByText("KAPALI GÜNLER PANELİ")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Kapalı Günler/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("dönem düzenleyicisi yarıyılın kapalı gün olarak girilmesini söyler", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("2026-2027");
    await user.click(screen.getAllByRole("button", { name: /Dönemler/ })[0]);
    expect(
      await screen.findByText(/Kapalı Günler sekmesinde öğrenciye kapalı gün olarak ekleyin/),
    ).toBeInTheDocument();
  });
});

describe("AyarlarPage — güvenlik", () => {
  it("güvenlik sekmesi paneli gösterir", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: /Güvenlik/ }));
    expect(await screen.findByText("GÜVENLİK PANELİ")).toBeInTheDocument();
  });
});
