// Kurulum sihirbazı testi (F1-E kod kapısı): parola adımı olmadan ilerlenmez;
// kurtarma anahtarı iki grubu geri yazılarak doğrulanmadan devam edilmez; okul
// adımının zorunlu alanları (kademe, kısa ad, demirbaş onayı); ders yılı
// kaydedilince iki takvim yılının tatilleri eklenir; `setup/complete/` reddi
// iletisiyle gösterilir; ve sihirbaz UÇTAN UCA çalışır.
//
// Backend, `okulApi`/`guvenlikApi` sınırında BELLEK İÇİ SAHTE SUNUCUYLA taklit
// edilir: `setup/status/` durumu backend `services/setup.py` ile aynı kuralla
// hesaplanır (eksik adımlar), böylece adım geçişleri gerçek sırayla sınanır.
// Yönlendirme gerçek router'dan geçer ("/" rotası işaret basar). Veriler uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ILK_ACILIS_DURUMU } from "../../test/kurulumDurumu";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type {
  SchoolConfig,
  SchoolConfigBody,
  SchoolYear,
  SetupStatus,
  SetupStep,
} from "../okul/api";

const oapi = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getSchoolConfig: vi.fn(),
  updateSchoolConfig: vi.fn(),
  completeSetup: vi.fn(),
  listSchoolYears: vi.fn(),
  createSchoolYear: vi.fn(),
  configureSchoolTerms: vi.fn(),
  activateSchoolYear: vi.fn(),
  seedHolidays: vi.fn(),
}));
const gapi = vi.hoisted(() => ({ kur: vi.fn(), kurtarmaAnahtariPdf: vi.fn() }));
const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: oapi };
});
vi.mock("../guvenlik/api", () => ({ guvenlikApi: gapi }));
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: indirme.saveBlob,
}));
// Kapalı gün paneli kendi testinde; burada yalnız hangi yıllarla bağlandığı görünür.
vi.mock("../takvim/KapaliGunlerPaneli", () => ({
  default: ({ yil, yillar }: { yil: number; yillar: number[] }) => (
    <div>
      KAPALI GÜNLER PANELİ {yil} [{yillar.join(",")}]
    </div>
  ),
}));

import KurulumPage from "./KurulumPage";

const ANAHTAR = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM";

// --- Bellek içi sahte sunucu -------------------------------------------------

interface Sunucu {
  parola: boolean;
  okul: SchoolConfig;
  yillar: SchoolYear[];
  donemli: Set<number>;
  tamam: boolean;
}

const BOS_OKUL: SchoolConfig = {
  school_name: "",
  province: "",
  district: "",
  principal_name: "",
  has_prep_class: false,
  kademe: "",
  kisa_ad: "",
  demirbas_onayi: false,
  demirbas_no: "",
  setup_completed: false,
};

let sunucu: Sunucu;

function okulTamamMi(o: SchoolConfig): boolean {
  return Boolean(o.school_name.trim() && o.kademe && o.kisa_ad.trim() && o.demirbas_onayi);
}

/** Backend `setup_status` ile aynı kural (eksik adımlar sırasıyla). */
function durum(): SetupStatus {
  const aktif = sunucu.yillar.find((y) => y.is_active) ?? null;
  const donemli = aktif !== null && sunucu.donemli.has(aktif.id);
  const eksik: SetupStep[] = [];
  if (!sunucu.parola) eksik.push("password");
  if (!okulTamamMi(sunucu.okul)) eksik.push("school");
  if (!donemli) eksik.push("calendar");
  return {
    ...ILK_ACILIS_DURUMU,
    setup_completed: sunucu.tamam,
    password_set: sunucu.parola,
    school_name: sunucu.okul.school_name,
    school_info_complete: okulTamamMi(sunucu.okul),
    has_active_school_year: aktif !== null,
    active_school_year: aktif && {
      id: aktif.id,
      name: aktif.name,
      start_date: aktif.start_date,
      end_date: aktif.end_date,
      terms_ready: donemli,
    },
    missing_steps: eksik,
  };
}

function sunucuyuKur(baslangic: Partial<Sunucu> = {}) {
  sunucu = {
    parola: false,
    okul: { ...BOS_OKUL },
    yillar: [],
    donemli: new Set(),
    tamam: false,
    ...baslangic,
  };
  oapi.getSetupStatus.mockImplementation(async () => durum());
  oapi.getSchoolConfig.mockImplementation(async () => ({ ...sunucu.okul }));
  oapi.updateSchoolConfig.mockImplementation(async (govde: SchoolConfigBody) => {
    sunucu.okul = { ...sunucu.okul, ...govde };
    return { ...sunucu.okul };
  });
  oapi.listSchoolYears.mockImplementation(async () => [...sunucu.yillar]);
  oapi.createSchoolYear.mockImplementation(
    async (govde: { name: string; start_date: string; end_date: string }) => {
      const yil: SchoolYear = { id: sunucu.yillar.length + 5, is_active: false, ...govde };
      sunucu.yillar.push(yil);
      return yil;
    },
  );
  oapi.configureSchoolTerms.mockImplementation(async (id: number) => {
    sunucu.donemli.add(id);
    return [];
  });
  oapi.activateSchoolYear.mockImplementation(async (id: number) => {
    sunucu.yillar = sunucu.yillar.map((y) => ({ ...y, is_active: y.id === id }));
    return sunucu.yillar.find((y) => y.id === id);
  });
  oapi.seedHolidays.mockImplementation(async (year: number) => ({
    year,
    created: 10,
    skipped: 0,
    religious_available: true,
  }));
  oapi.completeSetup.mockImplementation(async () => {
    const eksik = durum().missing_steps;
    if (eksik.length > 0) {
      throw new ApiError(400, "kurulum_eksik", `Kurulum tamamlanamadı. Eksik: ${eksik.join(",")}`);
    }
    sunucu.tamam = true;
    return { setup_completed: true };
  });
  gapi.kur.mockImplementation(async () => {
    sunucu.parola = true;
    return { ...durum(), recovery_key: ANAHTAR, locked: false };
  });
}

const TAM_OKUL: SchoolConfig = {
  ...BOS_OKUL,
  school_name: "Deneme Anadolu Lisesi",
  kademe: "ORTAOGRETIM",
  kisa_ad: "Deneme AL",
  demirbas_onayi: true,
};

const AKTIF_YIL: SchoolYear = {
  id: 3,
  name: "2026-2027",
  start_date: "2026-09-07",
  end_date: "2027-06-25",
  is_active: true,
};

/** `state` kapı yönlendirmesini taklit eder (KurulumKapisi'nin taşıdığı sebep). */
function renderPage(state?: unknown) {
  return render(
    <SnackbarProvider>
      <ConfirmProvider>
        <MemoryRouter initialEntries={[{ pathname: "/kurulum", state }]}>
          <Routes>
            <Route path="/kurulum" element={<KurulumPage />} />
            <Route path="/" element={<div>PANEL EKRANI</div>} />
          </Routes>
        </MemoryRouter>
      </ConfirmProvider>
    </SnackbarProvider>,
  );
}

const ileri = (ad: string | RegExp) => screen.getByRole("button", { name: ad });

/** Parolayı kurar ve anahtarın sorulan iki grubunu (sabit rastgele: 1. ve 2.) doğrular. */
async function parolaAdiminiGec(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText(/^Yönetici parolası/), "Deneme-Parola-1");
  await user.type(screen.getByLabelText(/^Parola \(tekrar\)/), "Deneme-Parola-1");
  await user.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));
  expect(await screen.findByTestId("kurtarma-anahtari")).toHaveTextContent(ANAHTAR);
  await user.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));
  await user.type(screen.getByLabelText("1. grup"), "TEST");
  await user.type(screen.getByLabelText("2. grup"), "KURT");
  await user.click(ileri("Devam"));
}

beforeEach(() => {
  sunucuyuKur();
  // Doğrulanacak gruplar sabit: 1. ve 2. grup (rastgeleIkiGrup(8, () => 0.125)).
  vi.spyOn(Math, "random").mockReturnValue(0.125);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("KurulumPage — 1. adım: yönetici parolası (atlanamaz)", () => {
  it("ilk açılışta parola adımından başlar; parola kurulmadan ilerlenemez", async () => {
    renderPage();

    expect(await screen.findByText("1. Yönetici parolası")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Kurulum Sihirbazı" }),
    ).toBeInTheDocument();
    expect(ileri("Devam")).toBeDisabled();
    expect(screen.getByText("Devam etmek için yönetici parolasını kurun.")).toBeInTheDocument();
    // Adım rayı tıklanmaz (tamamlanmış adım olsa bile parola kapısı kapalı).
    const ray = screen.getByRole("list", { name: "Kurulum adımları" });
    expect(within(ray).queryAllByRole("button")).toHaveLength(0);
    // Eski "isteğe bağlı parola" dili yoktur.
    expect(screen.queryByText(/isteğe bağlı/i)).toBeNull();
    expect(screen.queryByText("2. Okul bilgileri")).toBeNull();
  });

  it("okul bilgileri önceden tamam olsa bile parola yokken adım rayı atlatmaz", async () => {
    sunucuyuKur({ okul: { ...TAM_OKUL } });
    renderPage();
    expect(await screen.findByText("1. Yönetici parolası")).toBeInTheDocument();
    const ray = screen.getByRole("list", { name: "Kurulum adımları" });
    expect(within(ray).queryAllByRole("button")).toHaveLength(0);
  });

  it("eşleşmeyen parola tekrarında istek atmaz", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(await screen.findByLabelText(/^Yönetici parolası/), "Deneme-Parola-1");
    await user.type(screen.getByLabelText(/^Parola \(tekrar\)/), "baska");
    await user.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));
    expect(await screen.findByText("Parolalar eşleşmedi.")).toBeInTheDocument();
    expect(gapi.kur).not.toHaveBeenCalled();
  });

  it("backend reddi (ör. kısa parola) iletisiyle gösterilir", async () => {
    const user = userEvent.setup();
    gapi.kur.mockRejectedValue(
      new ApiError(400, "validation_error", "Parola en az 8 karakter olmalıdır.", {}),
    );
    renderPage();
    await user.type(await screen.findByLabelText(/^Yönetici parolası/), "kisa");
    await user.type(screen.getByLabelText(/^Parola \(tekrar\)/), "kisa");
    await user.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));
    expect(await screen.findByText("Parola en az 8 karakter olmalıdır.")).toBeInTheDocument();
  });

  it("anahtar gösterilir; iki grup doğrulanmadan devam edilemez, doğrulanınca okul adımına geçer", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(await screen.findByLabelText(/^Yönetici parolası/), "Deneme-Parola-1");
    await user.type(screen.getByLabelText(/^Parola \(tekrar\)/), "Deneme-Parola-1");
    await user.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));

    expect(await screen.findByTestId("kurtarma-anahtari")).toHaveTextContent(ANAHTAR);
    expect(ileri("Devam")).toBeDisabled();
    expect(
      screen.getByText("Devam etmek için kurtarma anahtarını sakladığınızı doğrulayın."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));
    await user.type(screen.getByLabelText("1. grup"), "TEST");
    await user.type(screen.getByLabelText("2. grup"), "YANL");
    expect(ileri("Devam")).toBeDisabled();

    await user.clear(screen.getByLabelText("2. grup"));
    await user.type(screen.getByLabelText("2. grup"), "kurt");
    await waitFor(() => expect(ileri("Devam")).toBeEnabled());
    await user.click(ileri("Devam"));

    expect(await screen.findByText("2. Okul bilgileri")).toBeInTheDocument();
    // Geri dönülünce anahtar bir daha gösterilmez (bellekte tutulmaz).
    await user.click(screen.getByRole("button", { name: "Geri" }));
    expect(await screen.findByText("1. Yönetici parolası kurulu")).toBeInTheDocument();
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
    expect(screen.getByRole("heading", { name: "Kurtarma anahtarı çıktısı" })).toBeInTheDocument();
  });

  it("anahtar sihirbazdan PDF olarak kaydedilir", async () => {
    const user = userEvent.setup();
    const pdf = new Blob(["%PDF-"]);
    gapi.kurtarmaAnahtariPdf.mockResolvedValue(pdf);
    renderPage();
    await user.type(await screen.findByLabelText(/^Yönetici parolası/), "Deneme-Parola-1");
    await user.type(screen.getByLabelText(/^Parola \(tekrar\)/), "Deneme-Parola-1");
    await user.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));

    await user.click(await screen.findByRole("button", { name: "PDF olarak kaydet" }));

    await waitFor(() => expect(gapi.kurtarmaAnahtariPdf).toHaveBeenCalledWith(ANAHTAR));
    expect(indirme.saveBlob).toHaveBeenCalledWith(
      pdf,
      expect.stringMatching(/^Kurtarma-Anahtarı-Çıktısı_\d{2}\.\d{2}\.\d{4}\.pdf$/),
    );
  });
});

describe("KurulumPage — 2. adım: okul bilgileri", () => {
  beforeEach(() => sunucuyuKur({ parola: true }));

  it("kademe, kısa ad ve demirbaş onayı olmadan kaydetmez; alan hataları gösterilir", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("2. Okul bilgileri")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Okul adı/), "Deneme Anadolu Lisesi");
    await user.click(ileri("Kaydet ve devam et"));

    expect(await screen.findByText("Kademe seçin.")).toBeInTheDocument();
    expect(screen.getByText("Kısa ad zorunludur.")).toBeInTheDocument();
    expect(screen.getByText(/onay zorunludur/)).toBeInTheDocument();
    expect(oapi.updateSchoolConfig).not.toHaveBeenCalled();
    expect(screen.getByText("2. Okul bilgileri")).toBeInTheDocument();
  });

  it("tam gövdeyi gönderir ve 3. adıma geçer", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("2. Okul bilgileri");
    await user.type(screen.getByLabelText(/Okul adı/), "Deneme Anadolu Lisesi");
    await user.type(screen.getByLabelText(/Kısa ad/), "Deneme AL");
    await user.selectOptions(screen.getByLabelText(/Kademe/), "ORTAOGRETIM");
    await user.type(screen.getByLabelText("İl"), "Ankara");
    await user.click(screen.getByRole("checkbox", { name: /Bu bilgisayar okul demirbaşıdır/ }));
    await user.type(screen.getByLabelText("Bilgisayarın demirbaş no'su"), "BLG-17");
    await user.click(ileri("Kaydet ve devam et"));

    await waitFor(() =>
      expect(oapi.updateSchoolConfig).toHaveBeenCalledWith({
        school_name: "Deneme Anadolu Lisesi",
        province: "Ankara",
        district: "",
        principal_name: "",
        has_prep_class: false,
        kademe: "ORTAOGRETIM",
        kisa_ad: "Deneme AL",
        demirbas_onayi: true,
        demirbas_no: "BLG-17",
      }),
    );
    expect(await screen.findByText("3. Ders yılı")).toBeInTheDocument();
  });

  it("kayıt hatasında Türkçe hata bandı + alan hatası gösterilir, adım değişmez", async () => {
    const user = userEvent.setup();
    sunucuyuKur({ parola: true, okul: { ...TAM_OKUL } });
    sunucu.yillar = [AKTIF_YIL];
    sunucu.donemli.add(AKTIF_YIL.id);
    oapi.updateSchoolConfig.mockRejectedValue(
      new ApiError(400, "validation_error", "Kısa ad en çok 24 karakter olabilir.", {
        kisa_ad: ["Kısa ad en çok 24 karakter olabilir."],
      }),
    );
    renderPage();
    // Hepsi tamamken sihirbaz son adımdan açılır; okul adımına raydan dönülür.
    const ray = await screen.findByRole("list", { name: "Kurulum adımları" });
    await user.click(within(ray).getByRole("button", { name: /Okul bilgileri/ }));
    await user.click(ileri("Kaydet ve devam et"));

    expect(await screen.findAllByText("Kısa ad en çok 24 karakter olabilir.")).not.toHaveLength(0);
    expect(screen.getByText("2. Okul bilgileri")).toBeInTheDocument();
  });
});

describe("KurulumPage — 3. adım: ders yılı ve kapalı günler", () => {
  beforeEach(() => sunucuyuKur({ parola: true, okul: { ...TAM_OKUL } }));

  it("ders yılı kaydedilince dönemler kurulur, yıl aktifleşir ve iki takvim yılı tohumlanır", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("3. Ders yılı")).toBeInTheDocument();
    expect(ileri("Kurulumu tamamla")).toBeDisabled();
    // Aktif yıl yokken kapalı gün paneli görünmez.
    expect(screen.queryByText(/KAPALI GÜNLER PANELİ/)).toBeNull();

    await user.clear(screen.getByLabelText(/^Ad/));
    await user.type(screen.getByLabelText(/^Ad/), "2026-2027");
    await user.click(screen.getByRole("button", { name: "Ders yılını kaydet ve aktifleştir" }));

    await waitFor(() => expect(oapi.activateSchoolYear).toHaveBeenCalled());
    expect(oapi.configureSchoolTerms).toHaveBeenCalled();
    await waitFor(() => expect(oapi.seedHolidays).toHaveBeenCalledTimes(2));
    const tohumlanan = oapi.seedHolidays.mock.calls.map(([y]) => y as number);
    expect(tohumlanan[1] - tohumlanan[0]).toBe(1);
    expect(
      await screen.findByText(`KAPALI GÜNLER PANELİ ${tohumlanan[0]} [${tohumlanan.join(",")}]`),
    ).toBeInTheDocument();
    await waitFor(() => expect(ileri("Kurulumu tamamla")).toBeEnabled());
  });

  it("dini bayram tarihleri programda yoksa uyarı gösterilir", async () => {
    const user = userEvent.setup();
    oapi.seedHolidays.mockImplementation(async (year: number) => ({
      year,
      created: 5,
      skipped: 0,
      religious_available: year < 2027,
    }));
    renderPage();
    await screen.findByText("3. Ders yılı");
    await user.click(screen.getByRole("button", { name: "Ders yılını kaydet ve aktifleştir" }));
    expect(await screen.findByText(/dini bayram tarihleri yok/)).toBeInTheDocument();
  });

  it("aktif yılın dönemleri yoksa dönem formu çıkar; kaydedilince tamamlanabilir", async () => {
    const user = userEvent.setup();
    sunucu.yillar = [AKTIF_YIL];
    renderPage();

    expect(await screen.findByText("2026-2027 dönemleri")).toBeInTheDocument();
    expect(ileri("Kurulumu tamamla")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Dönemleri kaydet" }));

    await waitFor(() =>
      expect(oapi.configureSchoolTerms).toHaveBeenCalledWith(AKTIF_YIL.id, {
        first_term_end: "2027-01-16",
        second_term_start: "2027-02-02",
      }),
    );
    await waitFor(() => expect(ileri("Kurulumu tamamla")).toBeEnabled());
  });

  it("backend eksik adım reddi (kurulum_eksik) iletisiyle bantta gösterilir", async () => {
    const user = userEvent.setup();
    sunucu.yillar = [AKTIF_YIL];
    sunucu.donemli.add(AKTIF_YIL.id);
    oapi.completeSetup.mockRejectedValue(
      new ApiError(
        400,
        "kurulum_eksik",
        "Kurulum tamamlanamadı. 1. adım (yönetici parolası): yönetici parolası kurulmadı.",
      ),
    );
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Kurulumu tamamla" }));
    expect(await screen.findByText(/1\. adım \(yönetici parolası\)/)).toBeInTheDocument();
    expect(screen.queryByText("PANEL EKRANI")).toBeNull();
  });
});

describe("KurulumPage — uçtan uca", () => {
  it("parola → kurtarma anahtarı → okul bilgileri → ders yılı → Kurulumu tamamla → Genel Bakış", async () => {
    const user = userEvent.setup();
    renderPage();

    // 1. adım
    await parolaAdiminiGec(user);

    // 2. adım
    expect(await screen.findByText("2. Okul bilgileri")).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Okul adı/), "Deneme Anadolu Lisesi");
    await user.type(screen.getByLabelText(/Kısa ad/), "Deneme AL");
    await user.selectOptions(screen.getByLabelText(/Kademe/), "ORTAOGRETIM");
    await user.click(screen.getByRole("checkbox", { name: /Bu bilgisayar okul demirbaşıdır/ }));
    await user.click(ileri("Kaydet ve devam et"));

    // 3. adım
    expect(await screen.findByText("3. Ders yılı")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ders yılını kaydet ve aktifleştir" }));
    await waitFor(() => expect(ileri("Kurulumu tamamla")).toBeEnabled());

    // Adım rayında üç adım da tamam.
    const ray = screen.getByRole("list", { name: "Kurulum adımları" });
    expect(within(ray).getAllByRole("button")).toHaveLength(2); // tamam + tıklanabilir: 1 ve 2

    await user.click(ileri("Kurulumu tamamla"));
    expect(await screen.findByText("PANEL EKRANI")).toBeInTheDocument();
    expect(sunucu.tamam).toBe(true);
    expect(sunucu.parola).toBe(true);
  });
});

describe("KurulumPage — bilgilendirme", () => {
  it("kapı yönlendirmesiyle gelindiyse sebebi söyler", async () => {
    renderPage({ kapiYonlendirdi: "/kisiler" });
    expect(await screen.findByText(/bu yüzden buraya getirildiniz/)).toBeInTheDocument();
  });

  it("kurulum daha önce tamamlandıysa bunu söyler ve son adımdan açılır", async () => {
    sunucuyuKur({ parola: true, okul: { ...TAM_OKUL }, tamam: true });
    sunucu.yillar = [AKTIF_YIL];
    sunucu.donemli.add(AKTIF_YIL.id);
    renderPage();
    expect(await screen.findByText(/Kurulum daha önce tamamlanmıştı/)).toBeInTheDocument();
    expect(await screen.findByText("3. Ders yılı")).toBeInTheDocument();
  });

  it("durum okunamazsa Türkçe hata bandı gösterilir", async () => {
    oapi.getSetupStatus.mockRejectedValue(new ApiError(500, "error", "Sunucuya ulaşılamadı."));
    renderPage();
    expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeInTheDocument();
  });
});
