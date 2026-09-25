// Sayım (F9; TMY 32, tasarım §9-10, §9-11, §10 E10): sayım listesi · yeni sayım · taslak
// (kurul, iki AYRI seçenek açıklamalı ve bağımsız, TMY 32/3 için kurul talebi ve harcama
// yetkilisi alanları, ödünçteki ve teslimdeki nüsha için kurulun seçimi) · başlat (onay) ·
// okutma kuyruğu ve bölüm ilerlemesi · tamamla (ikinci sayım — 32/6) · harcama yetkilisinin
// onayı (ikinci doğrulama, onaylanmayan kalem gerekçeli) · sayım fazlası · iptal · belgeler.
// Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  belgeler,
  fazlaKalemi,
  ilerleme,
  kalem,
  ozet,
  sayfa,
  sayim,
  sayimSatiri,
  taslakSayim,
} from "./testVerileri";

const api = vi.hoisted(() => ({
  sayimlar: vi.fn(),
  sayim: vi.fn(),
  taslakAc: vi.fn(),
  taslakGuncelle: vi.fn(),
  taslakSil: vi.fn(),
  baslat: vi.fn(),
  okut: vi.fn(),
  kalemler: vi.fn(),
  fazlaEkle: vi.fn(),
  fazlaGuncelle: vi.fn(),
  fazlaCikar: vi.fn(),
  ilerleme: vi.fn(),
  tamamla: vi.fn(),
  onayla: vi.fn(),
  iptalEt: vi.fn(),
  belgeler: vi.fn(),
  belge: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...api } };
});
const kutuphane = vi.hoisted(() => ({ listWorks: vi.fn() }));
vi.mock("../kutuphane/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kutuphane/api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kutuphane } };
});

import { IPTAL_BASLIGI, ONAY_BASLIGI, ONAY_DOGRULAMASI } from "./SayimDiyaloglari";
import { OKUTMA_KUTUSU } from "./SayimOkutmasi";
import SayimPage from "./SayimPage";
import { DURDURMA_ACIKLAMASI, HIZMET_ARASI_ACIKLAMASI, IADE_NOTU } from "./SayimTaslagi";

function ciz(yol = "/katalog/sayim") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <SayimPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

async function onayla(user: ReturnType<typeof userEvent.setup>, dugme: string) {
  const pencere = await screen.findByRole("dialog");
  await user.click(within(pencere).getByRole("button", { name: dugme }));
}

beforeEach(() => {
  vi.resetAllMocks();
  api.sayimlar.mockResolvedValue(
    sayfa([sayimSatiri({ id: 3, status: "APPROVED", status_display: "Onaylandı" })]),
  );
  api.sayim.mockResolvedValue(sayim());
  api.belgeler.mockResolvedValue(belgeler());
  api.belge.mockResolvedValue(new Blob(["%PDF"]));
  api.ilerleme.mockResolvedValue(ilerleme());
  api.kalemler.mockResolvedValue(sayfa([]));
});

// ============================================================ liste

describe("Sayım listesi", () => {
  it("sayımlar listelenir; canlı sayım yoksa “Yeni sayım” taslak açar ve ayrıntıya geçer", async () => {
    const user = userEvent.setup();
    api.taslakAc.mockResolvedValue(taslakSayim({ id: 12 }));
    api.sayim.mockResolvedValue(taslakSayim({ id: 12 }));
    ciz();

    expect(await screen.findByText("Onaylandı")).toBeInTheDocument();
    expect(
      screen.getByText(/Kütüphane materyalinin sayımı sayım kurulunca yapılır/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yeni sayım" }));

    expect(api.taslakAc).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Sayım Kurulu" })).toBeInTheDocument();
    expect(api.sayim).toHaveBeenCalledWith(12);
  });

  it("canlı sayım varken yeni sayım açılmaz; “Süren sayımı aç” onu açar", async () => {
    const user = userEvent.setup();
    api.sayimlar.mockResolvedValue(sayfa([sayimSatiri({ id: 7, round: 2 })]));
    ciz();

    expect(await screen.findByText("İkinci sayım")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yeni sayım" })).toBeNull();
    expect(screen.getByText(/Onaylanmamış bir sayım var/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Süren sayımı aç" }));
    expect(await screen.findByRole("heading", { name: "Kitapları Okutun" })).toBeInTheDocument();
  });

  it("liste boşsa açıklama; yüklenemezse hata bandı", async () => {
    api.sayimlar.mockResolvedValueOnce(sayfa([]));
    const { unmount } = ciz();
    expect(await screen.findByText("Henüz sayım yok")).toBeInTheDocument();
    unmount();
    api.sayimlar.mockRejectedValueOnce(new ApiError(500, "hata", "Sunucu hatası."));
    ciz();
    expect(await screen.findByText("Sunucu hatası.")).toBeInTheDocument();
  });
});

// ============================================================ taslak

describe("Taslak — kurul, iki ayrı seçenek, kurulun seçimi", () => {
  it("iki seçenek açıklamalı ve bağımsızdır; durdurma alanları yalnız seçilince çıkar", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim());
    ciz("/katalog/sayim?sayim=7");

    await screen.findByRole("heading", { name: "Sayım Sırasındaki Seçenekler" });
    expect(screen.getByText(DURDURMA_ACIKLAMASI)).toBeInTheDocument();
    expect(screen.getByText(HIZMET_ARASI_ACIKLAMASI)).toBeInTheDocument();
    expect(screen.getByText(IADE_NOTU)).toBeInTheDocument();
    expect(screen.queryByLabelText("Kurulun talep tarihi")).toBeNull();

    await user.click(screen.getByRole("checkbox", { name: "TMY 32/3 durdurması" }));
    expect(screen.getByLabelText("Kurulun talep tarihi")).toBeInTheDocument();
    expect(screen.getByLabelText("Harcama yetkilisinin adı")).toBeInTheDocument();
    expect(screen.getByLabelText("Durdurma tarihi")).toBeInTheDocument();
    // Hizmet arası ayrı seçilir; durdurma onu seçmez.
    expect(screen.getByRole("checkbox", { name: "Sayım için hizmet arası" })).not.toBeChecked();
    expect(screen.queryByLabelText("Okul kararı (isteğe bağlı)")).toBeNull();
  });

  it("kaydet gövdesi: kurul, seçenekler ve kurulun seçimi; seçilmeyen durdurmanın alanları boş", async () => {
    const user = userEvent.setup();
    const bos = taslakSayim();
    api.sayim.mockResolvedValue(bos);
    api.taslakGuncelle.mockResolvedValue(
      taslakSayim({ committee_chair: "Deneme Başkan", service_pause: true }),
    );
    ciz("/katalog/sayim?sayim=7");

    await user.type(await screen.findByLabelText("Kurul başkanı"), "Deneme Başkan");
    await user.type(screen.getByLabelText("Taşınır kayıt yetkilisi"), "Deneme Yetkili");
    await user.type(screen.getByLabelText("Kurul üyeleri"), "Deneme Üye");
    await user.click(screen.getByRole("checkbox", { name: "Sayım için hizmet arası" }));
    await user.type(screen.getByLabelText("Okul kararı (isteğe bağlı)"), "2026/15");
    await user.selectOptions(screen.getByLabelText("Ödünçteki nüsha"), "COLLECT");
    expect(screen.getByText("Kaydedince seçimin dayanağı burada yazılır.")).toBeInTheDocument();
    // K2: onarımdaki nüsha için kurulun seçimi; K3: sınıf kitaplığında "Kayda göre" yok.
    const onarim = screen.getByLabelText("Onarımdaki nüsha");
    expect(
      within(onarim)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Sayımdan önce geri alınır", "Kayda göre alınır — onarımda"]);
    await user.selectOptions(onarim, "COLLECT");
    expect(
      within(screen.getByLabelText("Sınıf kitaplığına teslim edilen nüsha"))
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).not.toContain("BY_RECORD");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(api.taslakGuncelle).toHaveBeenCalled());
    expect(api.taslakGuncelle.mock.calls[0][1]).toMatchObject({
      committee_chair: "Deneme Başkan",
      committee_property_officer: "Deneme Yetkili",
      committee_members: "Deneme Üye",
      tmy_stop: false,
      tmy_stop_requested_on: null,
      tmy_stop_by_name: "",
      tmy_stop_on: null,
      service_pause: true,
      service_pause_decision: "2026/15",
      loan_basis: "COLLECT",
      section_delivery_basis: "IN_PLACE",
      repair_basis: "COLLECT",
      fiscal_year: null,
    });
    expect(await screen.findByText("Taslak kaydedildi.")).toBeInTheDocument();
  });

  it("kayıtlı seçimin dayanağı sunucudan yazılır", async () => {
    api.sayim.mockResolvedValue(taslakSayim());
    ciz("/katalog/sayim?sayim=7");
    expect(
      await screen.findByText(
        "Kayda göre alınır: TMY 32/5'e kıyasen; 23/4 (ödünç takip sistemiyle izlenir).",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/32\/5 birinci cümleye kıyasen/)).toBeInTheDocument();
    // K2: onarımdaki nüshanın dayanağı 32/5'i anmaz.
    expect(screen.getByText(/onarıma gönderilmiş taşınırın sayımına/)).toBeInTheDocument();
  });

  it("başlat onayı seçilen seçenekleri yazar; sunucunun kurul reddi alanın altında", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim({ tmy_stop: true, service_pause: true }));
    api.baslat.mockRejectedValueOnce(
      new ApiError(400, "validation_error", "Sayım kurulu en az üç kişiden oluşur.", {
        committee_members: ["Sayım kurulu en az üç kişiden oluşur (TMY 32/2)."],
      }),
    );
    ciz("/katalog/sayim?sayim=7");

    await user.click(await screen.findByRole("button", { name: "Sayımı başlat" }));
    const pencere = await screen.findByRole("dialog");
    expect(within(pencere).getByText(/TMY 32\/3 durdurması başlar/)).toBeInTheDocument();
    // Madde 27: hizmet arası yeni teslimi de durdurur; geri alma açık.
    expect(within(pencere).getByText(/yeni ödünç ve teslim yapılamaz/)).toBeInTheDocument();
    expect(
      within(pencere).getByText(/İade ve teslimden geri alma açık kalır\./),
    ).toBeInTheDocument();
    await onayla(user, "Sayımı başlat");

    expect(
      await screen.findByText("Sayım kurulu en az üç kişiden oluşur (TMY 32/2)."),
    ).toBeInTheDocument();
    expect(api.baslat).toHaveBeenCalledWith(7);
  });

  it("başarılı başlatmada okutma ekranına geçilir", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValueOnce(taslakSayim()).mockResolvedValue(sayim());
    api.baslat.mockResolvedValue(sayim());
    ciz("/katalog/sayim?sayim=7");

    await user.click(await screen.findByRole("button", { name: "Sayımı başlat" }));
    await onayla(user, "Sayımı başlat");
    expect(await screen.findByLabelText(OKUTMA_KUTUSU)).toBeInTheDocument();
    expect(await screen.findByText("Sayım başladı.")).toBeInTheDocument();
  });

  it("taslak silinir ve listeye dönülür", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim());
    api.taslakSil.mockResolvedValue(undefined);
    ciz("/katalog/sayim?sayim=7");

    await user.click(await screen.findByRole("button", { name: "Taslağı sil" }));
    await onayla(user, "Sil");
    await waitFor(() => expect(api.taslakSil).toHaveBeenCalledWith(7));
    expect(await screen.findByText("Sayım taslağı silindi.")).toBeInTheDocument();
  });
});

// ============================================================ süren sayım

describe("Süren sayım — seçenekler, okutma, ilerleme, tamamla", () => {
  it("iki seçenek ve iade ayrı satırlarda; süren seçenekler işaretli", async () => {
    ciz("/katalog/sayim?sayim=7");
    const bolum = await screen.findByRole("region", { name: "Seçenekler" });
    const satirlar = within(bolum).getAllByRole("listitem");
    expect(satirlar).toHaveLength(3);
    expect(satirlar[0]).toHaveTextContent("TMY 32/3 durdurması");
    expect(satirlar[1]).toHaveTextContent("Sayım için hizmet arası");
    expect(satirlar[2]).toHaveTextContent("İade hiçbir durumda durdurulmaz");
    expect(within(bolum).getAllByText("Sürüyor")).toHaveLength(2);
    expect(
      screen.getByText("Deneme Kurulbaşkanı · Deneme Taşınırkayıt · Deneme Kurulüyesi"),
    ).toBeInTheDocument();
  });

  it("okutulan kod kuyruktan tek tek gönderilir; ileti ve kitap yazılır", async () => {
    const user = userEvent.setup();
    api.okut
      .mockResolvedValueOnce({
        results: [
          {
            code: "bulundu",
            message: "Bulundu.",
            barcode: "2026000041",
            item: kalem({ result: "FOUND", result_display: "Bulundu" }),
          },
        ],
        summary: ozet(),
      })
      .mockResolvedValueOnce({
        results: [
          {
            code: "fazla",
            message: "Sayım fazlası: bu numarada kayıt yok.",
            barcode: "4455",
            item: fazlaKalemi(),
          },
        ],
        summary: ozet(),
      });
    ciz("/katalog/sayim?sayim=7");

    const kutu = await screen.findByLabelText(OKUTMA_KUTUSU);
    await user.type(kutu, "2026000041{Enter}");
    await user.type(kutu, "4455{Enter}");

    expect(await screen.findByText("Sayım fazlası: bu numarada kayıt yok.")).toBeInTheDocument();
    expect(api.okut).toHaveBeenNthCalledWith(1, 7, ["2026000041"]);
    expect(api.okut).toHaveBeenNthCalledWith(2, 7, ["4455"]);
    expect(screen.getByText("Bu ekranda bulunan: 1")).toBeInTheDocument();
    const son = screen.getByRole("list", { name: "Son okutmalar" });
    expect(son).toHaveTextContent("2026-000041 — Bulunamayan Kitap: Bulundu.");
  });

  it("okutma hatası listede yazılır", async () => {
    const user = userEvent.setup();
    api.okut.mockRejectedValue(
      new ApiError(400, "validation_error", "Okutma yalnız süren sayımda yapılır."),
    );
    ciz("/katalog/sayim?sayim=7");
    await user.type(await screen.findByLabelText(OKUTMA_KUTUSU), "2026000041{Enter}");
    expect(await screen.findByText("Okutma yalnız süren sayımda yapılır.")).toBeInTheDocument();
  });

  it("bölüm bölüm ve yerinde sayılan sınıf kitaplığı ilerlemesi", async () => {
    ciz("/katalog/sayim?sayim=7");
    expect(await screen.findByText("75 / 114 nüsha bulundu", { exact: false })).toBeInTheDocument();
    const bolumler = screen.getByRole("list", { name: "Bölümler" });
    expect(bolumler).toHaveTextContent("Roman60 / 80");
    expect(bolumler).toHaveTextContent("Bölümsüz5 / 20");
    expect(screen.getByRole("list", { name: "Sınıf kitaplıkları" })).toHaveTextContent(
      "9/A10 / 14",
    );
  });

  it("tamamla: noksan varsa ikinci sayım başlar (TMY 32/6)", async () => {
    const user = userEvent.setup();
    api.tamamla.mockResolvedValue({
      second_round: true,
      missing: 4,
      stocktake: sayim({ round: 2 }),
    });
    api.sayim.mockResolvedValueOnce(sayim()).mockResolvedValue(sayim({ round: 2 }));
    api.kalemler.mockResolvedValue(sayfa([kalem()]));
    ciz("/katalog/sayim?sayim=7");

    await user.click(await screen.findByRole("button", { name: "Sayımı tamamla" }));
    const pencere = await screen.findByRole("dialog", { name: "Sayım tamamlansın mı?" });
    expect(pencere).toHaveTextContent("ikinci sayıma geçilir (Taşınır Mal Yönetmeliği md. 32/6)");
    await onayla(user, "Tamamla");

    expect(
      await screen.findByText("4 nüsha bulunamadı; ikinci sayım başladı."),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "İkinci Sayım: Bulunamayan Nüshalar" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Aranan nüshalar" })).toHaveTextContent(
      "2026-000041Bulunamayan Kitap",
    );
    expect(screen.getByRole("button", { name: "İkinci sayımı tamamla" })).toBeInTheDocument();
  });

  it("ikinci sayımı tamamlama onayı noksanın yazılacağını söyler", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(sayim({ round: 2 }));
    api.tamamla.mockResolvedValue({
      second_round: false,
      missing: 2,
      stocktake: sayim({ status: "COMPLETED" }),
    });
    ciz("/katalog/sayim?sayim=7");
    await user.click(await screen.findByRole("button", { name: "İkinci sayımı tamamla" }));
    const pencere = await screen.findByRole("dialog", { name: "İkinci sayım tamamlansın mı?" });
    expect(pencere).toHaveTextContent("“Noksan” olarak yazılır");
    await onayla(user, "Tamamla");
    expect(await screen.findByText("Sayım tamamlandı: 2 noksan.")).toBeInTheDocument();
  });
});

// ============================================================ sayım fazlası

describe("Sayım fazlası", () => {
  it("etiketsiz kitap eklenir; eser seçilir ya da kayda alınmayacak denir", async () => {
    const user = userEvent.setup();
    api.kalemler.mockImplementation((_id: number, s: { surplus?: boolean }) =>
      Promise.resolve(sayfa(s.surplus ? [fazlaKalemi()] : [])),
    );
    api.fazlaEkle.mockResolvedValue(fazlaKalemi({ id: 602 }));
    api.fazlaGuncelle.mockResolvedValue(fazlaKalemi());
    kutuphane.listWorks.mockResolvedValue(
      sayfa([{ id: 33, title: "Fazla Eser", authors: "Deneme Yazar" }]),
    );
    ciz("/katalog/sayim?sayim=7");

    const liste = await screen.findByRole("list", { name: "Sayım fazlası kitaplar" });
    expect(liste).toHaveTextContent("4455 — Rafın arkasında bulundu");
    expect(liste).toHaveTextContent("Karar bekliyor");

    await user.click(screen.getByRole("button", { name: "Etiketsiz kitap ekle" }));
    let pencere = await screen.findByRole("dialog", { name: "Etiketsiz kitap ekle" });
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    expect(
      within(pencere).getByText("Kitabın adını ya da kısa bir açıklama yazın."),
    ).toBeInTheDocument();
    await user.type(within(pencere).getByLabelText(/Açıklama/), "Masada unutulmuş");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(api.fazlaEkle).toHaveBeenCalledWith(7, { note: "Masada unutulmuş", work: null }),
    );

    await user.click(await screen.findByRole("button", { name: "Kayda alınmayacak" }));
    pencere = await screen.findByRole("dialog", { name: "Kayda alınmayacak kitap" });
    const gerekce = within(pencere).getByLabelText(/Gerekçe/);
    await user.clear(gerekce);
    await user.type(gerekce, "Öğretmenin kişisel kitabı");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(api.fazlaGuncelle).toHaveBeenCalledWith(7, 601, {
        excluded: true,
        note: "Öğretmenin kişisel kitabı",
      }),
    );
  });

  it("eser seçilmeden kaydedilmez; seçilince gönderilir", async () => {
    const user = userEvent.setup();
    api.kalemler.mockImplementation((_id: number, s: { surplus?: boolean }) =>
      Promise.resolve(sayfa(s.surplus ? [fazlaKalemi()] : [])),
    );
    api.fazlaGuncelle.mockResolvedValue(fazlaKalemi());
    kutuphane.listWorks.mockResolvedValue(
      sayfa([{ id: 33, title: "Fazla Eser", authors: "Deneme Yazar" }]),
    );
    ciz("/katalog/sayim?sayim=7");

    await user.click(await screen.findByRole("button", { name: "4455 için eser seç" }));
    const pencere = await screen.findByRole("dialog", { name: "Kayda alınacağı eser" });
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    expect(within(pencere).getByText("Kitabın kayda alınacağı eseri seçin.")).toBeInTheDocument();
    await user.type(within(pencere).getByRole("combobox", { name: /Eser/ }), "Fazla");
    await user.click(await within(pencere).findByRole("option", { name: /Fazla Eser/ }));
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(api.fazlaGuncelle).toHaveBeenCalledWith(7, 601, {
        work: 33,
        note: "Rafın arkasında bulundu",
      }),
    );
  });

  it("yanlış okutulan fazla listeden çıkarılır", async () => {
    const user = userEvent.setup();
    api.kalemler.mockImplementation((_id: number, s: { surplus?: boolean }) =>
      Promise.resolve(sayfa(s.surplus ? [fazlaKalemi()] : [])),
    );
    api.fazlaCikar.mockResolvedValue(undefined);
    ciz("/katalog/sayim?sayim=7");
    await user.click(await screen.findByRole("button", { name: "Çıkar" }));
    await onayla(user, "Çıkar");
    await waitFor(() => expect(api.fazlaCikar).toHaveBeenCalledWith(7, 601));
  });
});

// ============================================================ onay, iptal, belgeler

describe("Tamamlanmış sayım — harcama yetkilisinin onayı", () => {
  beforeEach(() => {
    api.sayim.mockResolvedValue(
      sayim({ status: "COMPLETED", completed_at: "2026-12-22T16:00:00+03:00" }),
    );
    api.kalemler.mockImplementation(
      (_id: number, s: { result?: string; damage?: boolean; surplus?: boolean }) => {
        if (s.surplus) return Promise.resolve(sayfa([]));
        if (s.damage) {
          return Promise.resolve(
            sayfa([
              kalem({
                id: 502,
                work_title: "Hasarlı Kitap",
                damage_write_off: true,
                result: "FOUND",
              }),
            ]),
          );
        }
        return Promise.resolve(sayfa([kalem()]));
      },
    );
  });

  it("sonuçlar ve noksan listesi; onay ikinci doğrulama ister, onaylanmayan kalem gerekçeli", async () => {
    const user = userEvent.setup();
    api.onayla.mockResolvedValue({
      written_off: 3,
      damage_written_off: 1,
      not_approved: 1,
      state_changed: 0,
      reconciled: 0,
      surplus_entered: 1,
      surplus_excluded: 1,
      stocktake: sayim({ status: "APPROVED" }),
    });
    ciz("/katalog/sayim?sayim=7");

    expect(await screen.findByRole("heading", { name: "Sonuçlar" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Kalemler" })).toBeInTheDocument();
    expect(screen.getByLabelText("Sonuç")).toHaveValue("MISSING");

    await user.click(screen.getByRole("button", { name: "Harcama yetkilisinin onayını işle" }));
    const pencere = await screen.findByRole("dialog", { name: ONAY_BASLIGI });
    expect(pencere).toHaveTextContent(
      "4 noksan nüsha kayıttan düşülür (Taşınır Mal Yönetmeliği md. 32/7)",
    );
    expect(pencere).toHaveTextContent("(md. 27/1)");
    const onayDugmesi = within(pencere).getByRole("button", { name: "Onayla" });
    expect(onayDugmesi).toBeDisabled();
    await user.click(within(pencere).getByRole("checkbox", { name: ONAY_DOGRULAMASI }));
    await user.click(onayDugmesi);
    expect(within(pencere).getByText("Harcama yetkilisinin adını yazın.")).toBeInTheDocument();

    await user.type(within(pencere).getByLabelText(/Harcama yetkilisinin adı/), "Deneme Harcama");
    const kutular = await within(pencere).findAllByRole("checkbox", { name: "Onaylanmadı" });
    expect(kutular).toHaveLength(2);
    await user.click(kutular[0]);
    await user.click(onayDugmesi);
    expect(
      within(pencere).getByText("Onaylanmayan her kalemin gerekçesini yazın."),
    ).toBeInTheDocument();
    await user.type(within(pencere).getByLabelText("Gerekçe"), "Ciltçide");
    await user.click(onayDugmesi);

    await waitFor(() => expect(api.onayla).toHaveBeenCalled());
    expect(api.onayla.mock.calls[0][1]).toMatchObject({
      approved_by_name: "Deneme Harcama",
      not_approved: { "501": "Ciltçide" },
    });
    expect(
      await screen.findByText("Sayım onaylandı: 4 nüsha kayıttan düşüldü, 1 fazla kayda alındı."),
    ).toBeInTheDocument();
  });

  it("çözülmemiş fazla varken onay penceresi uyarır", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(
      sayim({ status: "COMPLETED", summary: ozet({ surplus_unresolved: 2 }) }),
    );
    ciz("/katalog/sayim?sayim=7");
    await user.click(
      await screen.findByRole("button", { name: "Harcama yetkilisinin onayını işle" }),
    );
    const pencere = await screen.findByRole("dialog", { name: ONAY_BASLIGI });
    expect(within(pencere).getByRole("alert")).toHaveTextContent(
      "2 sayım fazlası kitabın kayda alınacağı eseri seçin",
    );
  });

  it("iptal onay penceresinden geçer; gerekçe isteğe bağlıdır", async () => {
    const user = userEvent.setup();
    api.iptalEt.mockResolvedValue(sayim({ status: "CANCELLED" }));
    ciz("/katalog/sayim?sayim=7");
    await user.click(await screen.findByRole("button", { name: "İptal et" }));
    const pencere = await screen.findByRole("dialog", { name: IPTAL_BASLIGI });
    expect(pencere).toHaveTextContent("seçilen durdurma ve hizmet arası kalkar");
    await user.type(within(pencere).getByLabelText(/İptal gerekçesi/), "Kurul değişti");
    await user.click(within(pencere).getByRole("button", { name: "İptal et" }));
    await waitFor(() => expect(api.iptalEt).toHaveBeenCalledWith(7, "Kurul değişti"));
    expect(await screen.findByText("Sayım iptal edildi.")).toBeInTheDocument();
  });

  it("sayım tutanağı belge kartında: PDF ve Excel", async () => {
    ciz("/katalog/sayim?sayim=7");
    expect(await screen.findByRole("heading", { name: "Sayım Belgeleri" })).toBeInTheDocument();
    expect(screen.getByText("Sayım tutanağı")).toBeInTheDocument();
    expect(
      screen.getByText(/Taşınır Sayım ve Döküm Cetveline aktarılacak sayılar/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Excel'i indir" })).toBeInTheDocument();
  });
});

describe("Onaylanmış ve iptal edilmiş sayım", () => {
  it("onaylanmışta eylem yok; onay bilgisi yazılır", async () => {
    api.sayim.mockResolvedValue(
      sayim({
        status: "APPROVED",
        approved_on: "2026-12-23",
        approved_by_name: "Deneme Harcama",
      }),
    );
    ciz("/katalog/sayim?sayim=7");
    expect(await screen.findByText("Deneme Harcama · 23.12.2026")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sayımı tamamla" })).toBeNull();
    expect(screen.queryByRole("button", { name: "İptal et" })).toBeNull();
    expect(screen.queryByLabelText(OKUTMA_KUTUSU)).toBeNull();
  });

  it("iptal edilmişte gerekçe yazılır; belge basılamaz", async () => {
    api.sayim.mockResolvedValue(
      sayim({
        status: "CANCELLED",
        cancelled_at: "2026-12-22T10:00:00+03:00",
        cancel_reason: "Kurul değişti",
      }),
    );
    api.belgeler.mockResolvedValue(
      belgeler({ available: false, reason: "İptal edilmiş sayımın tutanağı basılmaz." }),
    );
    ciz("/katalog/sayim?sayim=7");
    expect(
      await screen.findByText(/22\.12\.2026 tarihinde iptal edildi: Kurul değişti/),
    ).toBeInTheDocument();
    expect(screen.getByText("İptal edilmiş sayımın tutanağı basılmaz.")).toBeInTheDocument();
  });

  it("ayrıntı yüklenemezse hata ve geri dönüş", async () => {
    const user = userEvent.setup();
    api.sayim.mockRejectedValue(new ApiError(404, "not_found", "Bulunamadı."));
    ciz("/katalog/sayim?sayim=99");
    expect(await screen.findByText("Bulunamadı.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sayımlara dön" }));
    expect(
      await screen.findByRole("button", { name: /Yeni sayım|Süren sayımı aç/ }),
    ).toBeInTheDocument();
  });
});
