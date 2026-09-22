// KORUMA TESTİ (tasarım §6.3-1 "saklama zorunlu"; F1 kod kapısı "parola adımı
// atlanamaz"): kurtarma anahtarı ekrandayken sihirbaz sayfası sökülürse anahtar
// kaybolmamalı ve doğrulama atlanmamalıdır. Tam App ağacı (kilit, kurulum ve
// kip kapıları gerçek); yalnız API sınırı sahtedir.
//
// Sayfanın söküldüğü üç yol sınanır: boşta süre dolup kip görevliye iner
// (sunucu kararı; ön yüz kip yoklamasıyla öğrenir), "Kilitle" (kilit ekranı) ve
// üst menüden başka bir sayfaya gidilmesi (kurulum kapısı sihirbazı sıfırdan açar).
// Her yolda sihirbaz yeniden 1. adımda anahtarı gösterir ve iki grup yeniden
// doğrulanmadan "Devam" kapalı kalır.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SetupStatus } from "./modules/okul/api";
import { ILK_ACILIS_DURUMU } from "./test/kurulumDurumu";
import { ConfirmProvider } from "./ui/ConfirmProvider";
import { SnackbarProvider } from "./ui/SnackbarProvider";

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
const gapi = vi.hoisted(() => ({
  durum: vi.fn(),
  kur: vi.fn(),
  ac: vi.fn(),
  kurtarmaAnahtariPdf: vi.fn(),
}));
vi.mock("./modules/guvenlik/api", () => ({ guvenlikApi: gapi }));

import App from "./App";
import { kilitOlayiYayinla } from "./modules/guvenlik/GuvenlikKapisi";
import { KIP_YETKISIZ_OLAYI } from "./lib/kip";
import { BEKLEYEN_ANAHTAR_METNI } from "./modules/kip/GorevliEkrani";

const ANAHTAR = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM";
const GRUPLAR = ANAHTAR.split("-");
const PAROLA = "Gizli-Parola-42";
let parolaKurulu = false;
let kilitli = false;

const kipOzeti = (durum: string) => ({
  durum,
  bosta_kalan_sn: durum === "yonetici" ? 180 : null,
  mutlak_kalan_sn: durum === "yonetici" ? 1800 : null,
  bosta_dk: 3,
  mutlak_dk: 30,
});

function kurulumDurumu(): SetupStatus {
  return parolaKurulu
    ? { ...ILK_ACILIS_DURUMU, password_set: true, missing_steps: ["school", "calendar"] }
    : ILK_ACILIS_DURUMU;
}

function guvenlikDurumu() {
  return {
    password_set: parolaKurulu,
    locked: kilitli,
    security_file_missing: false,
    reset_available: false,
    transition_pending: false,
    transition: "",
    protected_fields: [],
  };
}

beforeEach(() => {
  parolaKurulu = false;
  kilitli = false;
  okulApiMock.getSetupStatus.mockImplementation(async () => kurulumDurumu());
  okulApiMock.getSchoolConfig.mockResolvedValue({
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
  });
  okulApiMock.listSchoolYears.mockResolvedValue([]);
  gapi.durum.mockImplementation(async () => guvenlikDurumu());
  gapi.kur.mockImplementation(async () => {
    parolaKurulu = true;
    return { recovery_key: ANAHTAR };
  });
  gapi.ac.mockImplementation(async () => {
    kilitli = false;
    return guvenlikDurumu();
  });
  kipApiMock.durum.mockResolvedValue(kipOzeti("kurulum"));
});

function bas() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/kurulum"]}>
        <SnackbarProvider>
          <ConfirmProvider>
            <App />
          </ConfirmProvider>
        </SnackbarProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function parolayiKur() {
  const kullanici = userEvent.setup();
  await screen.findByLabelText(/^Yönetici parolası/);
  await kullanici.type(screen.getByLabelText(/^Yönetici parolası/), PAROLA);
  await kullanici.type(screen.getByLabelText(/^Parola \(tekrar\)/), PAROLA);
  await kullanici.click(screen.getByRole("button", { name: "Yönetici parolasını kur" }));
  await screen.findByText("Kurtarma anahtarınız");
  return kullanici;
}

/** Kip sorgusunu yeniden okutur (403 `kip_yetkisiz` olayı yoklamayı tetikler). */
function kipDegisti(durum: string) {
  kipApiMock.durum.mockResolvedValue(kipOzeti(durum));
  act(() => {
    window.dispatchEvent(new CustomEvent(KIP_YETKISIZ_OLAYI));
  });
}

/** Sihirbaz anahtarı yeniden gösteriyor ve doğrulanmadan ilerlemiyor mu? */
async function anahtarYenidenGosterilir() {
  await screen.findByText("Kurtarma anahtarınız");
  expect(screen.getByTestId("kurtarma-anahtari")).toHaveTextContent(ANAHTAR);
  expect(screen.queryByText("2. Okul bilgileri")).toBeNull();
  expect(screen.getByRole("button", { name: "Devam" })).toBeDisabled();
}

/** Anahtarı doğrular ve 2. adıma geçer (grup sırası testte sabit değil: ekrandan okunur). */
async function dogrulaVeDevamEt(kullanici: ReturnType<typeof userEvent.setup>) {
  await kullanici.click(screen.getByRole("button", { name: "Sakladım, doğrula" }));
  const alanlar = screen.getAllByLabelText(/^\d+\. grup/) as HTMLInputElement[];
  expect(alanlar).toHaveLength(2);
  for (const alan of alanlar) {
    const grupNo = Number(/^(\d+)\. grup/.exec(alan.labels?.[0]?.textContent ?? "")?.[1]);
    await kullanici.type(alan, GRUPLAR[grupNo - 1]);
  }
  const devam = screen.getByRole("button", { name: "Devam" });
  expect(devam).toBeEnabled();
  await kullanici.click(devam);
  await screen.findByText("2. Okul bilgileri");
}

describe("kurtarma anahtarı doğrulanmadan sihirbaz sökülürse anahtar kaybolmaz", () => {
  it("boşta süre dolup görevli kipine inince anahtar bekler, yönetici kipinde geri gelir", async () => {
    bas();
    const kullanici = await parolayiKur();

    kipDegisti("gorevli");
    await screen.findByRole("heading", { name: "Görevli Kipi" });
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
    expect(screen.getByText(BEKLEYEN_ANAHTAR_METNI)).toBeInTheDocument();

    kipDegisti("yonetici");
    await anahtarYenidenGosterilir();
    await dogrulaVeDevamEt(kullanici);
    // Doğrulanıp ilerlenince anahtar bellekten bırakılır: geri dönülünce gösterilmez.
    await kullanici.click(screen.getByRole("button", { name: "Geri" }));
    await screen.findByText("1. Yönetici parolası kurulu");
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
  });

  it("Kilitle ile kilit ekranına düşülünce anahtar bekler, kilit açılınca geri gelir", async () => {
    bas();
    const kullanici = await parolayiKur();

    kilitli = true;
    act(() => kilitOlayiYayinla());
    const parolaAlani = await screen.findByLabelText(/^Yönetici parolası/);
    expect(screen.queryByTestId("kurtarma-anahtari")).toBeNull();
    await kullanici.type(parolaAlani, PAROLA);
    await kullanici.click(screen.getByRole("button", { name: "Aç" }));

    await anahtarYenidenGosterilir();
  });

  it("menüden başka sayfaya gidilince sihirbaz anahtarı yeniden gösterir", async () => {
    bas();
    const kullanici = await parolayiKur();

    const menu = screen.getAllByRole("link", { name: /Genel Bakış/ })[0];
    await kullanici.click(menu);

    await anahtarYenidenGosterilir();
    expect(
      within(document.body).getByText(/Kurulum tamamlanmadan diğer ekranlar açılmaz/),
    ).toBeInTheDocument();
  });
});
