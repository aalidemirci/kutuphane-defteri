// Etiketler sayfası (F4) — sayfa kabuğu, Basım Kuyruğu ve Basım Geçmişi.
//
// Sabitlenen davranışlar:
//   1) Beş sekme adreste tutulur; sayaç şeridi onay bekleyen partiyi öne çıkarır.
//   2) Kuyruk içerik, süzgeç ve sırayla istenir; içe aktarmanın kısayolu
//      (`?edinim=`) kuyruğu o partiye süzer. Seçim yoksa parti KUYRUKTAN açılır
//      (süzgeçler ve sıra aynen gider), seçim varsa yalnız seçilen nüshalarla.
//   3) PARTİ AÇMAK "BASILDI" DEĞİLDİR (D10): parti açılınca nüshalar kuyrukta
//      kalır ve onay bekleyen parti kartı çıkar; işaret yalnız onay diyaloğundan
//      geçen "Basıldı olarak işaretle" ile yazılır.
//   4) Basım Geçmişi'nde basılmış parti onaylı olarak geri alınır (doğrulanmış
//      etiketin korunduğu söylenir) ve yeniden basılır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  basimPartisi,
  basimPartisiAyrintisi,
  bosBarkodAraligi,
  etiketOzeti,
  hazirSablonlar,
  kuyrukNushasi,
} from "../../test/etiketVerileri";
import { bolum, edinim, sayfa } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const etiket = vi.hoisted(() => ({
  ozet: vi.fn(),
  sablonlar: vi.fn(),
  kalibrasyonlar: vi.fn(),
  kuyruk: vi.fn(),
  araliklar: vi.fn(),
  partiAc: vi.fn(),
  partiOnayla: vi.fn(),
  partiler: vi.fn(),
  parti: vi.fn(),
  partiGeriAl: vi.fn(),
  yenidenBas: vi.fn(),
  dogrulanmamislar: vi.fn(),
}));

const katalog = vi.hoisted(() => ({
  listSections: vi.fn(),
  listAcquisitions: vi.fn(),
}));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...katalog } };
});

import EtiketlerPage, { ETIKETLER_SEKMELERI } from "./EtiketlerPage";

function Adres() {
  const konum = useLocation();
  return <p data-testid="adres">{`${konum.pathname}${konum.search}`}</p>;
}

function ekranaBas(adres = "/katalog/etiketler") {
  return render(
    <MemoryRouter initialEntries={[adres]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route
              path="/katalog/etiketler"
              element={
                <>
                  <EtiketlerPage />
                  <Adres />
                </>
              }
            />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  etiket.ozet.mockResolvedValue(etiketOzeti());
  etiket.sablonlar.mockResolvedValue(sayfa(hazirSablonlar()));
  etiket.kalibrasyonlar.mockResolvedValue(sayfa([]));
  etiket.kuyruk.mockResolvedValue(
    sayfa([kuyrukNushasi(), kuyrukNushasi({ id: 22, barcode_display: "2026-000124" })]),
  );
  etiket.araliklar.mockResolvedValue(sayfa([bosBarkodAraligi()]));
  etiket.partiAc.mockResolvedValue(basimPartisiAyrintisi());
  etiket.partiOnayla.mockResolvedValue(basimPartisi({ status: "CONFIRMED" }));
  etiket.partiler.mockResolvedValue(sayfa([basimPartisi()]));
  etiket.dogrulanmamislar.mockResolvedValue(sayfa([]));
  katalog.listSections.mockResolvedValue(sayfa([bolum()]));
  katalog.listAcquisitions.mockResolvedValue(sayfa([edinim({ id: 4 })]));
});

/** Kuyruğun son isteğinin parametreleri. */
function sonKuyrukIstegi(): Record<string, unknown> {
  const cagrilar = etiket.kuyruk.mock.calls;
  return cagrilar[cagrilar.length - 1][0] as Record<string, unknown>;
}

describe("Etiketler — sayfa", () => {
  it("başlık, beş sekme ve sayaç şeridi", async () => {
    ekranaBas();

    expect(await screen.findByRole("heading", { level: 1, name: "Etiketler" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(5);
    expect(Object.values(ETIKETLER_SEKMELERI)).toEqual([
      "Basım Kuyruğu",
      "Basım Geçmişi",
      "Boş Barkod Aralığı",
      "Doğrulama Okutması",
      "Şablonlar ve Kalibrasyon",
    ]);
    for (const ad of Object.values(ETIKETLER_SEKMELERI)) {
      expect(screen.getByRole("tab", { name: ad })).toBeInTheDocument();
    }
    const serit = await screen.findByRole("list", { name: "Etiket sayaçları" });
    expect(within(serit).getByText(/Sırt etiketi bekleyen: 4/)).toBeInTheDocument();
    expect(within(serit).getByText(/Bağlanmamış boş etiket: 52/)).toBeInTheDocument();
  });

  it("onay bekleyen parti öne çıkar ve Basım Geçmişi'ne götürür", async () => {
    const user = userEvent.setup();
    etiket.ozet.mockResolvedValue(etiketOzeti({ pending_batches: 2 }));
    ekranaBas();

    expect(await screen.findByText(/2 basım partisi onay bekliyor/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Basım Geçmişi'ni aç" }));

    expect(screen.getByTestId("adres")).toHaveTextContent("?tab=gecmis");
    await waitFor(() => expect(etiket.partiler).toHaveBeenCalled());
  });

  it("sayaç çipi ilgili sekmeye gider", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.click(await screen.findByRole("button", { name: /Doğrulanmamış etiket: 2/ }));
    expect(screen.getByTestId("adres")).toHaveTextContent("?tab=dogrulama");
  });
});

describe("Etiketler — Basım Kuyruğu", () => {
  it("içe aktarma kısayolu kuyruğu edinim partisine süzer; varsayılan içerik ve sıra", async () => {
    ekranaBas("/katalog/etiketler?edinim=4");

    await waitFor(() => expect(etiket.kuyruk).toHaveBeenCalled());
    expect(sonKuyrukIstegi()).toMatchObject({
      kind: "BOTH",
      order: "CALL_NUMBER",
      acquisition: 4,
      limit: 25,
      offset: 0,
    });
    expect(await screen.findByText("Kuyruk: 2 nüsha")).toBeInTheDocument();
    expect(screen.getByLabelText("Edinim partisi")).toHaveValue("4");
  });

  it("boş barkod aralığı kısayolu sırt kuyruğunu o aralığa süzer", async () => {
    ekranaBas("/katalog/etiketler?aralik=5&icerik=SPINE");

    await waitFor(() => expect(etiket.kuyruk).toHaveBeenCalled());
    expect(sonKuyrukIstegi()).toMatchObject({ kind: "SPINE", reservation: 5 });
    // Sırt basımı sırt tabakasıyla açılır.
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("4"));
  });

  it("içerik ve sıra değişince kuyruk yeniden istenir; şablon içeriğe göre değişir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));

    await user.selectOptions(screen.getByLabelText("Etiket içeriği"), "SPINE");
    await user.selectOptions(screen.getByLabelText("Basım sırası"), "IMPORT_ROW");

    await waitFor(() =>
      expect(sonKuyrukIstegi()).toMatchObject({ kind: "SPINE", order: "IMPORT_ROW" }),
    );
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("4"));
  });

  it("onay bekleyen partideki nüsha satırda işaretlenir", async () => {
    etiket.kuyruk.mockResolvedValue(sayfa([kuyrukNushasi({ pending_batch: 12 })]));
    ekranaBas();

    expect(await screen.findByText("Onay bekleyen partide")).toBeInTheDocument();
  });

  it("seçim yoksa parti kuyruktan açılır; parti açmak basıldı DEMEK DEĞİLDİR", async () => {
    const user = userEvent.setup();
    ekranaBas("/katalog/etiketler?edinim=4");
    await screen.findByText("Kuyruk: 2 nüsha");
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));

    await user.click(screen.getByRole("button", { name: "12. hücre" }));
    await user.click(screen.getByRole("button", { name: "Basım partisini hazırla" }));

    await waitFor(() => expect(etiket.partiAc).toHaveBeenCalledTimes(1));
    expect(etiket.partiAc.mock.calls[0][0]).toMatchObject({
      kind: "BOTH",
      order: "CALL_NUMBER",
      template: 1,
      calibration: null,
      start_cell: 12,
      from_queue: true,
      limit: 2,
      acquisition: 4,
    });
    expect(etiket.partiAc.mock.calls[0][0]).not.toHaveProperty("copies");
    // Kart çıkar, işaret YAZILMAZ; ikinci parti hazırlanamaz.
    expect(await screen.findByText("Hazırlanan Basım Partisi")).toBeInTheDocument();
    expect(etiket.partiOnayla).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Basım partisini hazırla" })).toBeDisabled();
  });

  it("seçilen nüshalarla parti açılır ve onaydan sonra kuyruk tazelenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Kuyruk: 2 nüsha");
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));

    await user.click(screen.getByRole("checkbox", { name: "2026-000124 seç" }));
    expect(screen.getByText(/Seçtiğiniz 1 nüshanın etiketi/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Basım partisini hazırla" }));

    await waitFor(() => expect(etiket.partiAc).toHaveBeenCalledTimes(1));
    expect(etiket.partiAc.mock.calls[0][0]).toMatchObject({ copies: [22] });
    expect(etiket.partiAc.mock.calls[0][0]).not.toHaveProperty("from_queue");

    const kuyrukIstekleri = etiket.kuyruk.mock.calls.length;
    await user.click(await screen.findByRole("button", { name: "Basıldı olarak işaretle" }));
    const pencere = await screen.findByRole("dialog", {
      name: "Etiketler basıldı olarak işaretlensin mi?",
    });
    // Barkod etiketi içeren parti: onayın doğrulamayı sıfırladığı söylenir (sözlük).
    expect(within(pencere).getByText(/doğrulaması sıfırlanır/)).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Basıldı olarak işaretle" }));

    await waitFor(() => expect(etiket.partiOnayla).toHaveBeenCalledWith(12));
    await waitFor(() => expect(etiket.kuyruk.mock.calls.length).toBeGreaterThan(kuyrukIstekleri));
    expect(screen.queryByText("Hazırlanan Basım Partisi")).not.toBeInTheDocument();
    // Barkod etiketi basıldı: yapıştırdıktan sonra okutma hatırlatılır.
    expect(screen.getByText(/Doğrulama Okutması sekmesinde tek tek okutun/)).toBeInTheDocument();
  });

  it("sayfadakilerin hepsi tek kutuyla seçilir ve bırakılır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Kuyruk: 2 nüsha");

    await user.click(screen.getByRole("checkbox", { name: "Sayfadakilerin hepsini seç" }));
    expect(screen.getByRole("button", { name: "Seçimi bırak (2)" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Sayfadakilerin hepsini seç" }));
    expect(screen.queryByRole("button", { name: /Seçimi bırak/ })).not.toBeInTheDocument();
  });

  it("kuyruk boşsa parti hazırlanamaz", async () => {
    etiket.kuyruk.mockResolvedValue(sayfa([]));
    ekranaBas();

    expect(await screen.findByText("Kuyrukta bu süzgece uyan nüsha yok.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Basım partisini hazırla" })).toBeDisabled();
  });

  it("parti açılamazsa sunucunun iletisi gösterilir", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("../../lib/api");
    etiket.partiAc.mockRejectedValue(
      new ApiError(400, "validation_error", "Başlangıç hücresi 1 ile 65 arasında olmalıdır."),
    );
    ekranaBas();
    await screen.findByText("Kuyruk: 2 nüsha");
    await waitFor(() => expect(screen.getByLabelText(/^Etiket şablonu/)).toHaveValue("1"));

    await user.click(screen.getByRole("button", { name: "Basım partisini hazırla" }));

    expect(
      await screen.findByText("Başlangıç hücresi 1 ile 65 arasında olmalıdır."),
    ).toBeInTheDocument();
  });
});

describe("Etiketler — Basım Geçmişi", () => {
  it("basılmış parti onaylı olarak geri alınır; doğrulanmış nüshanın iki işaretinin korunduğu söylenir", async () => {
    const user = userEvent.setup();
    const basildi = basimPartisi({
      status: "CONFIRMED",
      status_display: "Basıldı",
      confirmed_at: "2026-09-24T11:30:00+03:00",
    });
    etiket.partiler.mockResolvedValue(sayfa([basildi]));
    etiket.parti.mockResolvedValue(basimPartisiAyrintisi({ ...basildi }));
    etiket.partiGeriAl.mockResolvedValue({
      batch: { ...basildi, status: "REVERTED" },
      restored: 1,
      requeued: 1,
      kept_verified: 1,
    });
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(
      await screen.findByRole("button", { name: /Sırt ve barkod etiketi, .* ayrıntıyı aç/ }),
    );
    expect(await screen.findByText("Seçilen Basım Partisi")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Nüshaları göster" }));
    expect(screen.getByText("2026-000124")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Basım işaretini geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Basım işareti geri alınsın mı?" });
    // Kullanıcı kararı (24.09.2026): sırt ve barkod partisinde doğrulanmış nüshanın
    // İKİ işareti de korunur, nüsha hiçbir kuyruğa dönmez.
    expect(
      within(pencere).getByText(
        /Barkodu okutularak doğrulanmış nüshaların .* sırt ve barkod işareti korunur; bu nüshalar kuyruğa dönmez\./,
      ),
    ).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Basım işaretini geri al" }));

    await waitFor(() => expect(etiket.partiGeriAl).toHaveBeenCalledWith(12));
    expect(
      await screen.findByText(
        "1 nüsha kuyruğa döndü. Okutularak doğrulanmış 1 nüshanın sırt ve barkod işareti " +
          "korundu; bunlar kuyruğa dönmez.",
      ),
    ).toBeInTheDocument();
  });

  it("barkod partisinde yalnız barkod işareti, sırt partisinde hiçbir doğrulama anılmaz", async () => {
    const user = userEvent.setup();
    const barkod = basimPartisi({
      kind: "BARCODE",
      kind_display: "Barkod etiketi",
      status: "CONFIRMED",
      status_display: "Basıldı",
      confirmed_at: "2026-09-24T11:30:00+03:00",
    });
    etiket.partiler.mockResolvedValue(sayfa([barkod]));
    etiket.parti.mockResolvedValue(basimPartisiAyrintisi({ ...barkod }));
    etiket.partiGeriAl.mockResolvedValue({
      batch: { ...barkod, status: "REVERTED" },
      restored: 0,
      requeued: 0,
      kept_verified: 2,
    });
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(await screen.findByRole("button", { name: /ayrıntıyı aç/ }));
    await user.click(await screen.findByRole("button", { name: "Basım işaretini geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Basım işareti geri alınsın mı?" });
    expect(within(pencere).getByText(/onların barkod işareti korunur/)).toBeInTheDocument();
    expect(within(pencere).queryByText(/sırt ve barkod işareti/)).toBeNull();
    await user.click(within(pencere).getByRole("button", { name: "Basım işaretini geri al" }));

    expect(
      await screen.findByText(
        "Okutularak doğrulanmış 2 nüshanın barkod işareti korundu; bunlar kuyruğa dönmez.",
      ),
    ).toBeInTheDocument();
  });

  it("sırt partisinin geri alma onayı doğrulamadan söz etmez", async () => {
    const user = userEvent.setup();
    const sirt = basimPartisi({
      kind: "SPINE",
      kind_display: "Sırt etiketi",
      status: "CONFIRMED",
      status_display: "Basıldı",
      confirmed_at: "2026-09-24T11:30:00+03:00",
    });
    etiket.partiler.mockResolvedValue(sayfa([sirt]));
    etiket.parti.mockResolvedValue(basimPartisiAyrintisi({ ...sirt }));
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(await screen.findByRole("button", { name: /ayrıntıyı aç/ }));
    await user.click(await screen.findByRole("button", { name: "Basım işaretini geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Basım işareti geri alınsın mı?" });

    expect(within(pencere).getByText(/bu basımdan önceki hâline döner/)).toBeInTheDocument();
    expect(within(pencere).queryByText(/doğrulanmış/)).toBeNull();
  });

  it("yeniden basım partisi geri alınınca nüshaların kuyruğa DÖNMEDİĞİ söylenir", async () => {
    const user = userEvent.setup();
    const basildi = basimPartisi({
      status: "CONFIRMED",
      status_display: "Basıldı",
      confirmed_at: "2026-09-24T11:30:00+03:00",
      reprint_of: 11,
    });
    etiket.partiler.mockResolvedValue(sayfa([basildi]));
    etiket.parti.mockResolvedValue(basimPartisiAyrintisi({ ...basildi }));
    etiket.partiGeriAl.mockResolvedValue({
      batch: { ...basildi, status: "REVERTED" },
      restored: 2,
      requeued: 0,
      kept_verified: 0,
    });
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(await screen.findByRole("button", { name: /ayrıntıyı aç/ }));
    await user.click(await screen.findByRole("button", { name: "Basım işaretini geri al" }));
    const pencere = await screen.findByRole("dialog", { name: "Basım işareti geri alınsın mı?" });
    expect(
      within(pencere).getByText(/daha önce basılmış olanlar önceki basımın işaretine döner/),
    ).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Basım işaretini geri al" }));

    expect(
      await screen.findByText("2 nüshanın işareti önceki basıma döndü; bunlar kuyruğa girmez."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/kuyruğa döndü/)).not.toBeInTheDocument();
  });

  it("partide sonradan silinen nüsha işaretlenir: PDF'te hücresi boş kalır", async () => {
    const user = userEvent.setup();
    const parti = basimPartisiAyrintisi();
    parti.items[1] = { ...parti.items[1], printable: false };
    etiket.partiler.mockResolvedValue(sayfa([basimPartisi()]));
    etiket.parti.mockResolvedValue(parti);
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(await screen.findByRole("button", { name: /ayrıntıyı aç/ }));
    await user.click(await screen.findByRole("button", { name: "Nüshaları göster" }));

    expect(screen.getAllByText(/PDF'te hücresi boş kalır/)).toHaveLength(1);
  });

  it("yeniden basım aynı partiden yeni bir parti açar ve onu gösterir", async () => {
    const user = userEvent.setup();
    const geriAlindi = basimPartisi({
      status: "REVERTED",
      status_display: "Basım işareti geri alındı",
      start_cell: 3,
    });
    etiket.partiler.mockResolvedValue(sayfa([geriAlindi]));
    etiket.parti.mockImplementation((id: number) =>
      Promise.resolve(
        id === 12 ? basimPartisiAyrintisi({ ...geriAlindi }) : basimPartisiAyrintisi({ id: 13 }),
      ),
    );
    etiket.yenidenBas.mockResolvedValue(basimPartisiAyrintisi({ id: 13, reprint_of: 12 }));
    ekranaBas("/katalog/etiketler?tab=gecmis");

    await user.click(await screen.findByRole("button", { name: /ayrıntıyı aç/ }));
    await user.click(await screen.findByRole("button", { name: "Yeniden bas" }));
    expect(screen.getByText("Yeniden Basım")).toBeInTheDocument();
    expect(screen.getByLabelText("Başlangıç hücresi")).toHaveValue("3");
    await user.selectOptions(screen.getAllByLabelText("Etiket içeriği")[0], "BARCODE");
    await user.click(screen.getByRole("button", { name: "Yeniden basım partisini hazırla" }));

    await waitFor(() =>
      expect(etiket.yenidenBas).toHaveBeenCalledWith(12, {
        kind: "BARCODE",
        template: 1,
        calibration: null,
        start_cell: 3,
      }),
    );
    await waitFor(() => expect(etiket.parti).toHaveBeenCalledWith(13));
    expect(await screen.findByText("Onay Bekleyen Parti")).toBeInTheDocument();
  });

  it("durum süzgeci sunucuya gider; boş geçmiş söylenir", async () => {
    const user = userEvent.setup();
    etiket.partiler.mockResolvedValue(sayfa([]));
    ekranaBas("/katalog/etiketler?tab=gecmis");

    expect(await screen.findByText("Henüz basım partisi yok.")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Durum"), "CONFIRMED");
    await waitFor(() =>
      expect(etiket.partiler).toHaveBeenLastCalledWith({
        status: "CONFIRMED",
        limit: 25,
        offset: 0,
      }),
    );
  });
});
