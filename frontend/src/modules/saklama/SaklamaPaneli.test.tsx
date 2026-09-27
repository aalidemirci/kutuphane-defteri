// Ayarlar → Saklama (F11 — tasarım §6.4): kişisiz önizleme, adlar yalnız istenince, yönetici
// parolası + "geri alınamaz" onayı olmadan uygulanmaz, onaylanan önizlemenin parmak izi
// gönderilir, bayat liste (409) yeniden yüklenir, altı ay uyarısı kapatılamaz. Kişiler uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { DisYedekDurumu } from "../guvenlik/api";
import type { SaklamaAdaylari, SaklamaDurumu } from "./api";

const sapi = vi.hoisted(() => ({
  durum: vi.fn(),
  kisiler: vi.fn(),
  bedelListesi: vi.fn(),
  uygula: vi.fn(),
  pano: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  saklamaApi: sapi,
}));
// F11 bağlantısı: "Son İşlem" kartı son şifreli yedek indirmesini okur.
const gapi = vi.hoisted(() => ({ disYedek: vi.fn() }));
vi.mock("../guvenlik/api", () => ({ guvenlikApi: gapi }));

import {
  ANONIM_KOPYA_IBARESI,
  LISTE_DEGISTI_KODU,
  adaySatirlari,
  anonimlestirmeSatirlari,
  silmeSatirlari,
} from "./api";
import SaklamaPaneli, {
  BAG_BASLIGI,
  DIS_YEDEK_UYARISI,
  KVKK_4_2_D,
  SILINECEK_BASLIGI,
} from "./SaklamaPaneli";

const DIGEST = "a".repeat(64);

function adaylar(alanlar: Partial<SaklamaAdaylari> = {}): SaklamaAdaylari {
  return {
    students: 0,
    personnel: 0,
    memberships: 0,
    loans_terminated: 0,
    loans_returned: 0,
    cases_terminated: 0,
    cases_closed: 0,
    deliveries: 0,
    total: 0,
    persons_held: 0,
    ...alanlar,
  };
}

function durum(alanlar: Partial<SaklamaDurumu> = {}): SaklamaDurumu {
  return {
    today: "2028-09-24",
    policy: {
      left_person_years: 2,
      after_termination_years: 2,
      returned_loans_years: 1,
      closed_cases_years: 2,
      closed_deliveries_years: 2,
    },
    candidates: adaylar({ students: 3, loans_returned: 40, deliveries: 1, total: 44 }),
    digest: DIGEST,
    pending_since: "2028-09-24",
    approval_deadline: "2029-03-24",
    overdue: false,
    max_wait_months: 6,
    last_scan_on: "2028-09-24",
    last_run: null,
    price_reminders: 0,
    residue: { pre_migrate: 2, pre_anonim: 0, old_databases: 3, old_databases_expired: 1 },
    ...alanlar,
  };
}

function disYedek(alanlar: Partial<DisYedekDurumu> = {}): DisYedekDurumu {
  return {
    last_download: "2028-09-20T09:00:00+03:00",
    reminder_days: 30,
    days_since: 4,
    remind: false,
    min_reminder_days: 7,
    max_reminder_days: 90,
    ...alanlar,
  };
}

const SON_ISLEM = {
  ran_at: "2028-09-22T10:00:00+03:00",
  backup_name: "pre-anonim-2028-09-22-100000.kdbak",
  summary: adaylar({ students: 2, total: 2 }),
  pre_migrate_removed: 1,
  old_db_removed: 2,
};

function ciz() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <SaklamaPaneli />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  sapi.durum.mockResolvedValue(durum());
  sapi.bedelListesi.mockResolvedValue([]);
  gapi.disYedek.mockResolvedValue(disYedek());
});

describe("Saklama — önizleme", () => {
  it("süresi dolan kayıtları kişisiz satırlarla ve süreleri politikadan yazar", async () => {
    ciz();
    const bolum = await screen.findByRole("heading", { name: "Süresi Dolan Kayıtlar" });
    const kart = bolum.closest("div.p-6") as HTMLElement;
    // "Ne silinecek" ile "kişiyle bağı koparılacak" ayrı gruplardır (silme ≠ anonimleştirme).
    const silinecek = within(kart).getByRole("heading", { name: SILINECEK_BASLIGI });
    expect(silinecek.parentElement).toHaveTextContent("3 öğrenci kaydı silinecek");
    expect(silinecek.parentElement).not.toHaveTextContent("ödünc");
    const baglar = within(kart).getByRole("heading", { name: BAG_BASLIGI });
    expect(baglar.parentElement).toHaveTextContent(
      "40 iade edilmiş ödüncün kişiyle bağı koparılacak",
    );
    expect(baglar.parentElement).toHaveTextContent(
      "1 öğretmene teslimin öğretmenle bağı koparılacak",
    );
    expect(kart).not.toHaveTextContent("sona ermiş üyelik kaydı");
    expect(kart).toHaveTextContent("en geç 24.03.2029");
    expect(screen.getByText(new RegExp(KVKK_4_2_D.slice(0, 30)))).toBeInTheDocument();
    // Adlar kendiliğinden gelmez.
    expect(sapi.kisiler).not.toHaveBeenCalled();
    // "Ne kalır" belge ibaresini tasarımdaki metinle söyler; "imha" sözcüğü yoktur.
    expect(screen.getByText(new RegExp(ANONIM_KOPYA_IBARESI))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/imha/i);
  });

  it("yedeklerde kalan: işlem 14 günden eski önceki veritabanlarını siler, yenileri kalır", async () => {
    // 27.09.2026 kullanıcı kararı: elle silme önerisi yalnız 14 günden yeni olanlar içindir.
    ciz();
    const baslik = await screen.findByRole("heading", { name: "Ne Kalır" });
    const kart = baslik.closest("div.p-6") as HTMLElement;
    const metin = (kart.textContent ?? "").replace(/\s+/g, " ");
    expect(metin).toContain(
      "geri yüklemeden kalan önceki veritabanı dosyalarından 14 günden eski olanları siler (şu an 3 önceki veritabanı; 1 tanesi 14 günden eski)",
    );
    expect(metin).toContain("Daha yenileri yakın tarihli bir geri yüklemeden dönüş için kalır");
    expect(metin).not.toContain("önceki veritabanı dosyaları (3) ve indirdiğiniz yedekler");
  });

  it("silinecek kişilerin adları yalnız istenince gelir; kişi ve üyelik ayrı tablodadır", async () => {
    sapi.kisiler.mockResolvedValue([
      {
        kind: "student",
        person_id: 1,
        full_name: "Deneme Öğrenci",
        person_label: "12/A",
        left_at: "2026-06-20",
        scope: "person",
        terminated_at: null,
      },
      {
        kind: "personnel",
        person_id: 1,
        full_name: "Deneme Öğretmen",
        person_label: "Öğretmen",
        left_at: null,
        scope: "membership",
        terminated_at: "2026-05-04",
      },
    ]);
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Silinecek kişileri göster" }));
    const tablo = await screen.findByRole("table", { name: "Kaydı silinecek kişiler" });
    // Sütun adları sözlükteki gibi (§4.18): program personelin görevini tutmaz (V2-01).
    expect(
      within(tablo)
        .getAllByRole("columnheader")
        .map((th) => th.textContent),
    ).toEqual(["Ad soyad", "Sınıf / üye türü", "Ayrılış"]);
    expect(within(tablo).getByText("Deneme Öğrenci")).toBeInTheDocument();
    expect(within(tablo).getByText("20.06.2026")).toBeInTheDocument();
    expect(within(tablo).queryByText("Deneme Öğretmen")).toBeNull();
    const uyelikler = screen.getByRole("table", { name: /Yalnız üyelik kaydı silinecek kişiler/ });
    expect(within(uyelikler).getByText("Deneme Öğretmen")).toBeInTheDocument();
    expect(within(uyelikler).getByText("04.05.2026")).toBeInTheDocument();

    // Adlar yeniden gizlenebilir (ekranda gereğinden uzun kalmasın).
    await userEvent.click(screen.getByRole("button", { name: "Adları gizle" }));
    expect(screen.queryByText("Deneme Öğrenci")).toBeNull();
    expect(sapi.kisiler).toHaveBeenCalledTimes(1);
  });

  it("yalnız sona ermiş üyelik silinecekse de adlar düğmesi çıkar; boş listede ileti", async () => {
    sapi.durum.mockResolvedValue(
      durum({ candidates: adaylar({ memberships: 2, loans_terminated: 5, total: 7 }) }),
    );
    sapi.kisiler.mockResolvedValue([]);
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Silinecek kişileri göster" }));
    expect(await screen.findByText("Silinecek kişi kaydı yok.")).toBeInTheDocument();
  });

  it("adlar yüklenemezse ileti çıkar", async () => {
    sapi.kisiler.mockRejectedValue(new ApiError(403, "kip_yetkisiz", "Yönetici kipi gerekir."));
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Silinecek kişileri göster" }));
    expect(await screen.findByText("Yönetici kipi gerekir.")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Kaydı silinecek kişiler" })).toBeNull();
  });

  it("durum okunamazsa hata bandı çıkar", async () => {
    sapi.durum.mockRejectedValue(new ApiError(500, "hata", "Sunucu hatası."));
    ciz();
    expect(await screen.findByText(/Sunucu hatası\./)).toBeInTheDocument();
  });

  it("bedel adımında bekleyen dosyalar yıllık listede satır satır görünür", async () => {
    sapi.bedelListesi.mockResolvedValue([
      {
        case_id: 7,
        barcode: "2026-000123",
        title: "Deneme Eseri",
        case_type: "Kayıp",
        resolution: "Bedel belirlendi",
        step_date: "2027-03-01",
        years_waiting: 1,
      },
    ]);
    ciz();
    const tablo = await screen.findByRole("table", { name: "Bedel adımında bekleyen dosyalar" });
    expect(within(tablo).getByText("2026-000123")).toBeInTheDocument();
    expect(
      within(tablo).getByText(/Kayıp · Bedel belirlendi \(01\.03\.2027\)/),
    ).toBeInTheDocument();
    expect(within(tablo).getByText("1 yıldır")).toBeInTheDocument();
  });

  it("aday yoksa onay düğmesi yoktur", async () => {
    sapi.durum.mockResolvedValue(durum({ candidates: adaylar(), digest: "" }));
    ciz();
    expect(await screen.findByText("Süresi dolmuş kayıt yok.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Onayla ve uygula" })).not.toBeInTheDocument();
  });

  it("altı ay dolunca kapatılamayan uyarı çıkar", async () => {
    sapi.durum.mockResolvedValue(durum({ overdue: true }));
    ciz();
    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("Onay bekleme süresi (6 ay) doldu");
    expect(within(uyari).queryByRole("button")).not.toBeInTheDocument();
  });

  it("ayrılış süresi geçtiği hâlde bekleyen kişiler sayıyla söylenir", async () => {
    sapi.durum.mockResolvedValue(
      durum({ candidates: adaylar({ loans_returned: 2, total: 2, persons_held: 4 }) }),
    );
    ciz();
    expect(await screen.findByText(/4 kişinin kaydı silinmeyecek/)).toBeInTheDocument();
    // Silinecek kişi kaydı yok: adlar düğmesi çıkmaz.
    expect(screen.queryByRole("button", { name: "Silinecek kişileri göster" })).toBeNull();
  });
});

describe("Saklama — son işlem ve dış yedek", () => {
  it("işlemden sonra şifreli yedek indirilmediyse USB uyarısı ve Güvenlik bağlantısı çıkar", async () => {
    sapi.durum.mockResolvedValue(durum({ last_run: SON_ISLEM }));
    gapi.disYedek.mockResolvedValue(disYedek({ last_download: "2028-09-20T09:00:00+03:00" }));
    ciz();
    expect(await screen.findByText(DIS_YEDEK_UYARISI)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ayarlar → Güvenlik'i aç/ })).toHaveAttribute(
      "href",
      "/ayarlar?tab=guvenlik",
    );
    expect(screen.getByText(/pre-anonim-2028-09-22-100000\.kdbak/)).toBeInTheDocument();
    expect(screen.getByText(/Silinen güncelleme öncesi yedek: 1\./)).toBeInTheDocument();
    expect(screen.getByText(/Silinen önceki veritabanı: 2\./)).toBeInTheDocument();
  });

  it("hiç indirme yoksa da uyarı çıkar", async () => {
    sapi.durum.mockResolvedValue(durum({ last_run: SON_ISLEM }));
    gapi.disYedek.mockResolvedValue(disYedek({ last_download: null, days_since: null }));
    ciz();
    expect(await screen.findByText(DIS_YEDEK_UYARISI)).toBeInTheDocument();
  });

  it("işlemden sonra yedek indirildiyse ya da son indirme okunamazsa uyarı yoktur", async () => {
    sapi.durum.mockResolvedValue(durum({ last_run: SON_ISLEM }));
    gapi.disYedek.mockResolvedValue(disYedek({ last_download: "2028-09-23T08:00:00+03:00" }));
    const { unmount } = ciz();
    expect(await screen.findByText(/pre-anonim-2028-09-22/)).toBeInTheDocument();
    expect(screen.queryByText(DIS_YEDEK_UYARISI)).toBeNull();
    unmount();

    gapi.disYedek.mockRejectedValue(new ApiError(423, "locked", "Kilitli."));
    ciz();
    expect(await screen.findByText(/pre-anonim-2028-09-22/)).toBeInTheDocument();
    expect(screen.queryByText(DIS_YEDEK_UYARISI)).toBeNull();
  });

  it("işlem hiç uygulanmadıysa uyarı yoktur", async () => {
    gapi.disYedek.mockResolvedValue(disYedek({ last_download: null }));
    ciz();
    expect(await screen.findByText("Saklama işlemi henüz uygulanmadı.")).toBeInTheDocument();
    expect(screen.queryByText(DIS_YEDEK_UYARISI)).toBeNull();
  });
});

describe("Saklama — onay", () => {
  it("parola ve 'geri alınamaz' onayı olmadan uygulanmaz; parmak izi gönderilir", async () => {
    sapi.uygula.mockResolvedValue({
      ran_at: "2028-09-24T10:00:00+03:00",
      backup_name: "pre-anonim-2028-09-24-100000.kdbak",
      summary: adaylar({ total: 44 }),
      pre_migrate_removed: 2,
      old_db_removed: 0,
      wal_truncated: true,
    });
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Onayla ve uygula" }));
    const pencere = await screen.findByRole("dialog", { name: "Saklama işlemi uygulansın mı?" });
    // Pencere de "ne silinecek / ne kalacak" ayrımını tekrarlar.
    expect(within(pencere).getByRole("heading", { name: SILINECEK_BASLIGI })).toBeInTheDocument();
    expect(within(pencere).getByRole("heading", { name: BAG_BASLIGI })).toBeInTheDocument();
    expect(pencere).toHaveTextContent(
      /geri yüklemeden kalan önceki veritabanı dosyalarından 14 günden eski olanlar silinir/,
    );
    const uygula = within(pencere).getByRole("button", { name: "Uygula" });
    expect(uygula).toBeDisabled();
    const parola = within(pencere).getByLabelText(/Yönetici parolası/);
    expect(parola).toHaveFocus();
    await userEvent.type(parola, "Deneme-Parola-1");
    expect(uygula).toBeDisabled();
    await userEvent.click(
      within(pencere).getByRole("checkbox", { name: "Bu işlemin geri alınamayacağını anladım" }),
    );
    await userEvent.click(uygula);

    await waitFor(() => expect(sapi.uygula).toHaveBeenCalledWith("Deneme-Parola-1", DIGEST));
    expect(await screen.findByText(/Saklama işlemi uygulandı: 44 kayıt/)).toBeInTheDocument();
    expect(sapi.durum).toHaveBeenCalledTimes(2);
  });

  it("yanlış parola pencerede gösterilir", async () => {
    sapi.uygula.mockRejectedValue(new ApiError(400, "validation_error", "Parola hatalı."));
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Onayla ve uygula" }));
    const pencere = await screen.findByRole("dialog");
    await userEvent.type(within(pencere).getByLabelText(/Yönetici parolası/), "yanlis");
    await userEvent.click(within(pencere).getByRole("checkbox"));
    await userEvent.click(within(pencere).getByRole("button", { name: "Uygula" }));
    expect(await within(pencere).findByText("Parola hatalı.")).toBeInTheDocument();
  });

  it("liste değiştiyse pencere kapanır ve önizleme yenilenir", async () => {
    sapi.uygula.mockRejectedValue(
      new ApiError(409, LISTE_DEGISTI_KODU, "Saklama listesi siz onaylarken değişti."),
    );
    ciz();
    await userEvent.click(await screen.findByRole("button", { name: "Onayla ve uygula" }));
    const pencere = await screen.findByRole("dialog");
    await userEvent.type(within(pencere).getByLabelText(/Yönetici parolası/), "x");
    await userEvent.click(within(pencere).getByRole("checkbox"));
    await userEvent.click(within(pencere).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(sapi.durum).toHaveBeenCalledTimes(2);
  });
});

describe("Saklama — yardımcılar", () => {
  it("aday satırları sıfırları atlar ve sayıyı Türkçe biçimler", () => {
    expect(adaySatirlari(adaylar({ loans_returned: 1250 }))).toEqual([
      "1.250 iade edilmiş ödüncün kişiyle bağı koparılacak",
    ]);
  });

  it("silme ve anonimleştirme satırları ayrı gruptur; hepsi önce silmeyi verir", () => {
    const a = adaylar({
      students: 1,
      personnel: 2,
      memberships: 3,
      loans_terminated: 4,
      cases_terminated: 5,
      cases_closed: 6,
      deliveries: 7,
    });
    expect(silmeSatirlari(a)).toEqual([
      "1 öğrenci kaydı silinecek",
      "2 öğretmen ya da diğer personel kaydı silinecek",
      "3 sona ermiş üyelik kaydı silinecek",
    ]);
    expect(anonimlestirmeSatirlari(a)).toHaveLength(4);
    expect(anonimlestirmeSatirlari(a).every((s) => s.includes("bağı koparılacak"))).toBe(true);
    expect(adaySatirlari(a)).toEqual([...silmeSatirlari(a), ...anonimlestirmeSatirlari(a)]);
  });
});
