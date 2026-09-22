// Kabuk + yönlendirme testi (DD App.test.tsx kalıbından).
// Pinlenen davranışlar: (1) kurulum kapısı — `setup_completed=false` iken her rota
// sihirbaza düşer, `true` iken Genel Bakış açılır, durum okunamazsa kapı FAIL-OPEN;
// (2) kabuk gezinmesi (Genel Bakış/Kişiler/Ayarlar/Kılavuz + Hakkında) ve
// kopyalanmayan modüllerin bağlantı ve rotalarının iskelete sızmaması;
// (3) açılışta güncelleme denetimi YOK — kabuk açılırken `/updates/` isteği
// çıkmaz (tasarım T11); (4) M3 token bütünlüğü — kaynakta kullanılan
// şekil/opaklık sınıflarının Tailwind çıktısında gerçekten üretildiği (DD F4-D5
// bulgu 14/15 dersi); (5) kip (tasarım §4.4) — yönetici kipinde üst çubukta kip
// göstergesi, görevli kipinde rotaların yerine görevli ekranı ve gezinmesiz
// kabuk; kip okunamazsa FAIL-OPEN.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import postcss from "postcss";
import { MemoryRouter } from "react-router-dom";
import tailwindcss from "tailwindcss";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";

import { ConfirmProvider } from "./ui/ConfirmProvider";
import { SnackbarProvider } from "./ui/SnackbarProvider";
import type { SetupStatus } from "./modules/okul/api";
import { KURULU_DURUM } from "./test/kurulumDurumu";

const okulApiMock = vi.hoisted(() => ({
  getSetupStatus: vi.fn(),
  getSchoolConfig: vi.fn(),
  updateSchoolConfig: vi.fn(),
  completeSetup: vi.fn(),
  getGradeLevels: vi.fn(),
  listSchoolYears: vi.fn(),
  listSchoolTerms: vi.fn(),
  listStudents: vi.fn(),
  listPersonnel: vi.fn(),
  listClassSections: vi.fn(),
  listHolidays: vi.fn(),
  markRoadmapItem: vi.fn(),
  setRoadmapHidden: vi.fn(),
}));

vi.mock("./modules/okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./modules/okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

const kipApiMock = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./modules/kip/api", () => ({ kipApi: kipApiMock }));

import App from "./App";
import { denetimSonucunuYayinla } from "./modules/guncelleme/denetimOlayi";
import type { KipOzeti } from "./modules/kip/api";

const YONETICI_KIPI: KipOzeti = {
  durum: "yonetici",
  bosta_kalan_sn: 180,
  mutlak_kalan_sn: 1800,
  bosta_dk: 3,
  mutlak_dk: 30,
};

const GOREVLI_KIPI: KipOzeti = {
  ...YONETICI_KIPI,
  durum: "gorevli",
  bosta_kalan_sn: null,
  mutlak_kalan_sn: null,
};

const KURULU: SetupStatus = {
  ...KURULU_DURUM,
  student_count: 482,
  personnel_count: 37,
  class_section_count: 18,
};

// Parola kurulu ama okul ve takvim adımları eksik (kurulum tamamlanmamış).
const KURULMAMIS: SetupStatus = {
  ...KURULU,
  setup_completed: false,
  school_name: "",
  school_info_complete: false,
  has_active_school_year: false,
  active_school_year: null,
  missing_steps: ["school", "calendar"],
  student_count: 0,
  personnel_count: 0,
};

/** main.tsx ile aynı sağlayıcı zinciri — sayfalar react-query, snackbar ve confirm
 *  bekliyor. Her ekran taze önbellekle açılır; başarısız sorgu yeniden denenmez. */
function ekranaBas(yol = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[yol]}>
        <SnackbarProvider>
          <ConfirmProvider>
            <App />
          </ConfirmProvider>
        </SnackbarProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Kabuğun üst çubuğu. Testing Library her `<header>`i "banner" sayar (sayfa
 * içi `<header>` için ARIA istisnasını uygulamaz); kabuğunki DOM'da İLKİDİR.
 */
function ustCubuk(): HTMLElement {
  return screen.getAllByRole("banner")[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  okulApiMock.getSetupStatus.mockResolvedValue(KURULU);
  okulApiMock.getSchoolConfig.mockResolvedValue({
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
  okulApiMock.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9" },
      { value: 10, label: "10" },
    ],
    prep_enabled: false,
  });
  okulApiMock.listSchoolYears.mockResolvedValue([]);
  okulApiMock.listSchoolTerms.mockResolvedValue([]);
  okulApiMock.listClassSections.mockResolvedValue([]);
  okulApiMock.listHolidays.mockResolvedValue([]);
  const bosSayfa = { count: 0, next: null, previous: null, results: [] };
  okulApiMock.listStudents.mockResolvedValue(bosSayfa);
  okulApiMock.listPersonnel.mockResolvedValue(bosSayfa);
  kipApiMock.durum.mockResolvedValue(YONETICI_KIPI);
});

describe("App — kip (görevli / yönetici)", () => {
  it("yönetici kipinde üst çubukta kip göstergesi durur, sayfalar açılır", async () => {
    ekranaBas("/");
    expect(await screen.findByRole("heading", { name: "Genel Bakış" })).toBeInTheDocument();
    const cubuk = ustCubuk();
    expect(await within(cubuk).findByText("Yönetici kipi")).toBeInTheDocument();
    expect(within(cubuk).getByRole("button", { name: "Görevli kipine geç" })).toBeInTheDocument();
    expect(within(cubuk).getByRole("button", { name: "Kilitle" })).toBeInTheDocument();
    expect(kipApiMock.durum).toHaveBeenCalledWith(false);
  });

  it("görevli kipinde rotaların yerine görevli ekranı durur ve gezinme boşalır", async () => {
    kipApiMock.durum.mockResolvedValue(GOREVLI_KIPI);
    ekranaBas("/kisiler");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Görevli Kipi" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kişiler" })).not.toBeInTheDocument();
    expect(within(ustCubuk()).getByText("Görevli Kipi")).toBeInTheDocument();
    const gezinme = screen.getByRole("navigation", { name: "Ana gezinme" });
    expect(within(gezinme).queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryByRole("link", { name: "Hakkında ve Lisans" })).not.toBeInTheDocument();
    expect(
      within(ustCubuk()).getByRole("button", { name: "Yönetici kipine geç" }),
    ).toBeInTheDocument();
  });

  it("Görevli kipine geç düğmesi ekranı görevli ekranına çevirir", async () => {
    const user = userEvent.setup();
    kipApiMock.gorevliyeGec.mockResolvedValue(GOREVLI_KIPI);
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });

    await user.click(await within(ustCubuk()).findByRole("button", { name: "Görevli kipine geç" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Görevli Kipi" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Genel Bakış" })).not.toBeInTheDocument();
  });

  it("güncelleme bandı görevli kipinde görünmez (indirme yönetici işidir)", async () => {
    const user = userEvent.setup();
    kipApiMock.gorevliyeGec.mockResolvedValue(GOREVLI_KIPI);
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });

    // Yönetici Ayarlar → Güncelleme'de elle denetledi ve yeni sürüm bulundu.
    act(() =>
      denetimSonucunuYayinla({
        current_version: "2026.9.0",
        latest_version: "2026.10.0",
        update_available: true,
        release_name: "",
        published_at: "",
        release_url: "",
        platform: "windows",
        can_download: true,
        installer_name: "kurulum.exe",
        installer_size: 1,
      }),
    );
    expect(await screen.findByText(/Kütüphane Defteri 2026\.10\.0 hazır\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Güncellemeyi indir" })).toBeInTheDocument();

    await user.click(await within(ustCubuk()).findByRole("button", { name: "Görevli kipine geç" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Görevli Kipi" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/2026\.10\.0 hazır/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Güncellemeyi indir" })).not.toBeInTheDocument();
  });

  it("kip okunamazsa sayfalar açılır, gösterge görünmez (fail-open)", async () => {
    kipApiMock.durum.mockRejectedValue(new Error("ağ yok"));
    ekranaBas("/");
    expect(await screen.findByRole("heading", { name: "Genel Bakış" })).toBeInTheDocument();
    await waitFor(() => expect(kipApiMock.durum).toHaveBeenCalled());
    expect(screen.queryByRole("group", { name: "Kip" })).not.toBeInTheDocument();
  });
});

describe("App — kurulum kapısı", () => {
  it("kurulum tamamlanmadıysa kök rotadan sihirbaza yönlendirir", async () => {
    okulApiMock.getSetupStatus.mockResolvedValue(KURULMAMIS);
    ekranaBas("/");
    expect(await screen.findByRole("heading", { name: "Kurulum Sihirbazı" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Genel Bakış" })).not.toBeInTheDocument();
  });

  it("kurulum tamamlanmadıysa iç rotalardan da sihirbaza yönlendirir", async () => {
    okulApiMock.getSetupStatus.mockResolvedValue(KURULMAMIS);
    ekranaBas("/kisiler");
    expect(await screen.findByRole("heading", { name: "Kurulum Sihirbazı" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kişiler" })).not.toBeInTheDocument();
  });

  it("kurulum tamamlandıysa kök rotada Genel Bakış açılır", async () => {
    ekranaBas("/");
    expect(await screen.findByRole("heading", { name: "Genel Bakış" })).toBeInTheDocument();
  });

  it("kurulum tamamlandıktan sonra sihirbaz elle açılabilir kalır", async () => {
    ekranaBas("/kurulum");
    expect(await screen.findByRole("heading", { name: "Kurulum Sihirbazı" })).toBeInTheDocument();
  });

  it("durum okunamazsa kapı açılır (fail-open) — program kilitlenmez", async () => {
    okulApiMock.getSetupStatus.mockRejectedValue(new Error("ağ yok"));
    ekranaBas("/");
    expect(await screen.findByRole("heading", { name: "Genel Bakış" })).toBeInTheDocument();
  });
});

describe("App — kabuk gezinmesi", () => {
  it("gezinme tam olarak Genel Bakış, Kişiler, Ayarlar ve Kılavuz'dur (bu sırayla)", async () => {
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });
    const gezinme = screen.getByRole("navigation", { name: "Ana gezinme" });
    const baglantilar = within(gezinme).getAllByRole("link");
    const beklenen: Array<[ad: string, yol: string]> = [
      ["Genel Bakış", "/"],
      ["Kişiler", "/kisiler"],
      ["Ayarlar", "/ayarlar"],
      ["Kılavuz", "/kilavuz"],
    ];
    expect(baglantilar).toHaveLength(beklenen.length);
    beklenen.forEach(([ad, yol], i) => {
      expect(baglantilar[i]).toHaveAccessibleName(ad);
      expect(baglantilar[i]).toHaveAttribute("href", yol);
    });
    expect(screen.getByRole("link", { name: "Hakkında ve Lisans" })).toHaveAttribute(
      "href",
      "/hakkinda",
    );
  });

  it("Kişiler bağlantısına tıklayınca sicil sayfası açılır", async () => {
    const user = userEvent.setup();
    ekranaBas("/");
    const gezinme = await screen.findByRole("navigation", { name: "Ana gezinme" });
    await user.click(within(gezinme).getByRole("link", { name: "Kişiler" }));
    expect(await screen.findByRole("heading", { name: "Kişiler" })).toBeInTheDocument();
  });

  it("Ayarlar bağlantısına tıklayınca ayarlar sayfası açılır", async () => {
    const user = userEvent.setup();
    ekranaBas("/");
    const gezinme = await screen.findByRole("navigation", { name: "Ana gezinme" });
    await user.click(within(gezinme).getByRole("link", { name: "Ayarlar" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Ayarlar" })).toBeInTheDocument();
  });

  it("Hakkında ve Lisans bağlantısı geliştirici ve kullanım koşullarını gösterir", async () => {
    const user = userEvent.setup();
    ekranaBas("/");
    await user.click(await screen.findByRole("link", { name: "Hakkında ve Lisans" }));
    expect(await screen.findByRole("heading", { name: "Hakkında ve Lisans" })).toBeInTheDocument();
    expect(screen.getByText("Ahmet Ali DEMİRCİ")).toBeInTheDocument();
    expect(screen.getByText(/PolyForm Noncommercial License 1.0.0/)).toBeInTheDocument();
  });

  it("Kılavuz bağlantısı kullanım kılavuzunu açar", async () => {
    const user = userEvent.setup();
    ekranaBas("/");
    await user.click(await screen.findByRole("link", { name: "Kılavuz" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Kullanım Kılavuzu" }),
    ).toBeInTheDocument();
  });

  // docs/sozluk.md §4: üst çubuktaki başlık sayfanın h1'iyle AYNIDIR. Eskiden
  // üst çubuk "Genel bakış", sayfa "Panel", gezinme "Panel" diyordu.
  it.each([
    ["/", "Genel Bakış"],
    ["/kisiler", "Kişiler"],
    ["/ayarlar", "Ayarlar"],
    ["/kilavuz", "Kullanım Kılavuzu"],
    ["/hakkinda", "Hakkında ve Lisans"],
    ["/kurulum", "Kurulum Sihirbazı"],
  ])("üst çubuk başlığı sayfanın h1'iyle aynıdır: %s", async (yol, baslik) => {
    ekranaBas(yol);
    expect(await screen.findByRole("heading", { level: 1, name: baslik })).toBeInTheDocument();
    expect(within(ustCubuk()).getByText(baslik)).toBeInTheDocument();
  });

  it("tema anahtarı tek yerdedir (kenar çubuğu) — üst çubukta ikinci kopya yok", async () => {
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });
    expect(screen.getAllByRole("button", { name: /temaya geç/ })).toHaveLength(1);
    expect(
      within(ustCubuk()).queryByRole("button", { name: /temaya geç/ }),
    ).not.toBeInTheDocument();
  });

  it("kopyalanmayan modüllerin bağlantıları iskelete sızmadı (gezinme ve Genel Bakış)", async () => {
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });
    // Kaynak programların gezinme etiketleri — tam ad (ileride gelecek kütüphane
    // ekranlarının adlarıyla yanlış eşleşmesin).
    for (const ad of [
      "Takvimler",
      "Oturumlar",
      "Mazeret Takibi",
      "Salonlar",
      "Ders Havuzu",
      "BEP",
      "Disiplin",
      "Onur / Ödül",
      "Bilgi Notları",
    ]) {
      expect(screen.queryByRole("link", { name: ad })).not.toBeInTheDocument();
    }
    const hedefler = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    for (const yol of ["/takvimler", "/oturumlar", "/mazeret", "/salonlar", "/dersler"]) {
      expect(hedefler).not.toContain(yol);
    }
  });

  it.each(["/takvimler", "/oturumlar", "/mazeret", "/salonlar", "/dersler"])(
    "kaldırılan rota %s hiçbir sayfa açmaz; üst çubuk program adını gösterir",
    async (yol) => {
      // Yönlendiricinin "eşleşen rota yok" uyarısı beklenen sonuçtur: yakalanır
      // ve kanıt olarak denetlenir (test çıktısını da kirletmez).
      const uyari = vi.spyOn(console, "warn").mockImplementation(() => {});
      try {
        ekranaBas(yol);
        // Kabuk yüklenir (gezinme durur); kilit ve kurulum kapıları geçilince
        // iskelet kalkar ama rota eşleşmediği için sayfa başlığı yoktur.
        await screen.findByRole("navigation", { name: "Ana gezinme" });
        await waitFor(() => expect(okulApiMock.getSetupStatus).toHaveBeenCalled());
        await waitFor(() => expect(screen.queryByText("Yükleniyor…")).not.toBeInTheDocument());
        expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
        expect(within(ustCubuk()).getAllByText("Kütüphane Defteri").length).toBeGreaterThan(0);
        expect(uyari).toHaveBeenCalledWith(
          expect.stringContaining(`No routes matched location "${yol}"`),
        );
      } finally {
        uyari.mockRestore();
      }
    },
  );
});

describe("App — açılışta dış istek yok", () => {
  let fetchCasusu: MockInstance<typeof fetch>;

  beforeEach(() => {
    // Ağ katmanı en alttan dinlenir: okulApi dışındaki her istek (güvenlik
    // durumu, güncelleme…) buradan geçer. Çevrimdışı gibi davranır.
    fetchCasusu = vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("çevrimdışı"));
  });

  afterEach(() => {
    fetchCasusu.mockRestore();
  });

  it("kabuk açılırken /updates/ isteği çıkmaz (güncelleme yalnız elle denetlenir)", async () => {
    ekranaBas("/");
    await screen.findByRole("heading", { name: "Genel Bakış" });

    const yollar = fetchCasusu.mock.calls.map(([girdi]) => String(girdi));
    // Casus gerçekten ağ katmanını görüyor: kilit kapısı güvenlik durumunu sordu.
    expect(yollar.some((y) => y.includes("/security/status/"))).toBe(true);
    expect(yollar.filter((y) => y.includes("/updates/"))).toEqual([]);
  });

  it("gezinme boyunca da /updates/ isteği çıkmaz", async () => {
    const user = userEvent.setup();
    ekranaBas("/");
    const gezinme = await screen.findByRole("navigation", { name: "Ana gezinme" });
    for (const ad of ["Kişiler", "Kılavuz", "Genel Bakış"]) {
      await user.click(within(gezinme).getByRole("link", { name: ad }));
    }
    await screen.findByRole("heading", { level: 1, name: "Genel Bakış" });

    const yollar = fetchCasusu.mock.calls.map(([girdi]) => String(girdi));
    expect(yollar.filter((y) => y.includes("/updates/"))).toEqual([]);
  });
});

// --- M3 token bütünlüğü ------------------------------------------------------
// Tailwind JIT, ölçekte KARŞILIĞI OLMAYAN bir token için sessizce hiç kural
// üretmez: `rounded-shape-full` ya da `bg-on-surface/8` yazılınca derleme
// patlamaz, sınıf yok sayılır ve kusur ancak gözle fark edilir (DD F4-D5 bulgu
// 14: köşeli gezinme sekmeleri, bulgu 15: hover geri bildirimi hiç oluşmaması).
// Bu test gerçek Tailwind çıktısını üretip kaynakta kullanılan her şekil ve
// opaklık token'ının CSS'te GERÇEKTEN yer aldığını doğrular.

// Vitest'in çalışma dizini proje kökü (`frontend/`) — `import.meta.url` burada
// dosya URL'i değil (vite-node sanal yolu), o yüzden cwd tabanlı çözülür.
const KOK = process.cwd();
const SRC_DIR = path.join(KOK, "src");

/** `src/` altındaki tüm ürün kaynağı (test dosyaları hariç). */
function kaynakDosyalari(dizin: string): string[] {
  const cikti: string[] = [];
  for (const girdi of readdirSync(dizin, { withFileTypes: true })) {
    const yol = path.join(dizin, girdi.name);
    if (girdi.isDirectory()) cikti.push(...kaynakDosyalari(yol));
    else if (/\.tsx?$/.test(girdi.name) && !/\.test\.tsx?$/.test(girdi.name)) cikti.push(yol);
  }
  return cikti;
}

// Şekil ölçeği: `rounded-shape-*`. Opaklık modifiyesi: yalnız SAYISAL olanlar —
// `bg-scrim/[0.32]` gibi keyfi değerler ölçeğe bakmadan üretildiği için kapsam dışı.
const SEKIL_DESENI = /\brounded-shape-[a-z0-9]+/g;
const OPAKLIK_DESENI =
  /\b(?:bg|text|border|ring|outline|fill|stroke|divide|from|via|to)-[a-z][a-z0-9-]*\/\d+\b/g;

/** Sınıf adının CSS'te üretilmiş bir seçici olarak var olup olmadığı.
 *
 * CSS çıktısında `/` kaçışlıdır (`.bg-primary\/8`). Sınıf bir varyantın ardından
 * da gelebilir (`hover:`, `placeholder:` → `.hover\:bg-primary\/8`), o yüzden
 * önünde `.` ya da kaçışlı `:` aranır.
 */
function uretildiMi(css: string, sinif: string): boolean {
  const desen = sinif
    .replace(/\//g, "\\/") // CSS kaçışı
    .replace(/[.\\/]/g, "\\$&"); // regex kaçışı
  return new RegExp(`(?:\\.|\\\\:)${desen}(?![\\w-])`).test(css);
}

describe("M3 token bütünlüğü", () => {
  it("kaynakta kullanılan şekil ve opaklık token'ları Tailwind çıktısında üretilir", async () => {
    const kullanilan = new Map<string, string>(); // sınıf → ilk görüldüğü dosya
    for (const dosya of kaynakDosyalari(SRC_DIR)) {
      const metin = readFileSync(dosya, "utf8");
      for (const desen of [SEKIL_DESENI, OPAKLIK_DESENI]) {
        for (const eslesme of metin.matchAll(desen)) {
          if (!kullanilan.has(eslesme[0]))
            kullanilan.set(eslesme[0], path.relative(SRC_DIR, dosya));
        }
      }
    }
    expect(kullanilan.size).toBeGreaterThan(0); // tarama gerçekten bir şey buldu

    const { css } = await postcss([
      tailwindcss({ config: path.join(KOK, "tailwind.config.js") }),
    ]).process("@tailwind utilities;", { from: undefined });

    const tanimsiz = [...kullanilan].filter(([sinif]) => !uretildiMi(css, sinif));
    expect(tanimsiz.map(([sinif, dosya]) => `${sinif} (${dosya})`)).toEqual([]);
  }, 60_000);
});
