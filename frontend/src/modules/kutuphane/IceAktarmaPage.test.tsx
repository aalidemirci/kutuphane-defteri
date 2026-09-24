// İçe Aktarma ekranı (F3) — sabitlenen davranışlar:
//
//   1) Önizleme yazmaz ve bunu SÖYLER; sayılar uygulamanın yazacağı sayılardır.
//   2) Karar bekleyen satır ve karşılıksız bölüm değeri varken "Uygula" KAPALIDIR
//      ve neden kapalı olduğu yazılıdır (kullanıcı 400 yemesin).
//   3) Kullanıcının verdiği kararlar ve bölüm karşılıkları ikinci önizlemede
//      sunucuya gider; uygulama da AYNI gövdeyi taşır.
//   4) Aynı dosya daha önce uygulanmışsa uygulama engellenir (uyarı değil ENGEL).
//   5) Yarım kalan önizleme koşusu geçmişe çöp bırakmaz: yeni önizleme ve başarılı
//      uygulama öncekini iptal eder.
//   6) Yapay zekâ köprüsünde §8.2'nin dört uyarısı SUNUCUDAN gelir ve ekranda
//      yazılıdır; program hiçbir servise bağlanmaz, JSON'u kullanıcı taşır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import {
  aktarimKosusu,
  aktarimRaporu,
  aktarimSatiri,
  aktarimSayilari,
  bolum,
  sayfa,
} from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  listSections: vi.fn(),
  listCommissionDecisions: vi.fn(),
  aktarimOnizle: vi.fn(),
  aktarimiUygula: vi.fn(),
  aktarimGecmisi: vi.fn(),
  aktarimiIptalEt: vi.fn(),
  kopruKomutu: vi.fn(),
  catalogTemplate: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import IceAktarmaPage from "./IceAktarmaPage";

const KOMUT = {
  schema_version: "v1",
  prompt: "Aşağıdaki tabloda bir okul kütüphanesinin kitap listesi var…",
  notes: [
    "Listede kişisel veri bulunmamalıdır.",
    "Listeyi dış hizmete kullanıcı taşır.",
    "Program hiçbir yapay zekâ servisine bağlanmaz.",
    "Bu adım Yönerge'nin 11/23 maddesiyle çatışabilir; asıl yol Excel ile içe aktarmadır.",
  ],
};

function ekranaBas(yol = "/katalog/ice-aktarma") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <Routes>
            <Route path="/katalog/ice-aktarma" element={<IceAktarmaPage />} />
            <Route path="/katalog" element={<h1>KATALOG</h1>} />
          </Routes>
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

/** Dosyayı seçip önizlemeyi çalıştırır. */
async function dosyaSecVeOnizle(user: ReturnType<typeof userEvent.setup>) {
  const dosya = new File(["x"], "katalog.xlsx", { type: "application/vnd.ms-excel" });
  await user.upload(screen.getByLabelText(/^Dosya/), dosya);
  await user.click(screen.getByRole("button", { name: "Önizle" }));
  return dosya;
}

/** `aktarimOnizle`ye giden son gövde. */
function sonOnizlemeGovdesi(): Record<string, unknown> {
  const cagrilar = kapi.aktarimOnizle.mock.calls;
  return cagrilar[cagrilar.length - 1][0] as Record<string, unknown>;
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.listSections.mockResolvedValue(sayfa([bolum(), bolum({ id: 2, name: "Tarih" })]));
  kapi.listCommissionDecisions.mockResolvedValue(sayfa([]));
  kapi.aktarimGecmisi.mockResolvedValue(sayfa([]));
  kapi.aktarimiIptalEt.mockResolvedValue(aktarimKosusu({ status: "DISCARDED" }));
  kapi.kopruKomutu.mockResolvedValue(KOMUT);
  kapi.aktarimOnizle.mockResolvedValue(aktarimRaporu());
  kapi.aktarimiUygula.mockResolvedValue(
    aktarimRaporu({
      dry_run: false,
      run_id: 12,
      stats: aktarimSayilari({ copies_created: 3 }),
      label_batch: {
        acquisition: 4,
        copy_count: 3,
        first_barcode: "2026000101",
        last_barcode: "2026000103",
      },
    }),
  );
});

describe("İçe Aktarma — Excel", () => {
  it("önizleme yazmadığını söyler ve sayılar uygulamanınkiyle aynıdır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });

    const dosya = await dosyaSecVeOnizle(user);

    expect(await screen.findByText("Önizleme — hiçbir kayıt yazılmadı")).toBeInTheDocument();
    expect(kapi.aktarimOnizle).toHaveBeenCalledTimes(1);
    expect(sonOnizlemeGovdesi()).toMatchObject({ file: dosya, source: "EXCEL" });
    expect(
      screen.getByText(/ekrandaki sayılar uygulamanın yazacağı sayılardır/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Açılacak nüsha")).toBeInTheDocument();
  });

  it("dosya seçilmeden önizleme istenirse istek çıkmaz, kullanıcıya söylenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });

    await user.click(screen.getByRole("button", { name: "Önizle" }));

    expect(kapi.aktarimOnizle).not.toHaveBeenCalled();
    expect(await screen.findByText("Önce içe aktarılacak dosyayı seçin.")).toBeInTheDocument();
  });

  it("karar bekleyen satır varken Uygula kapalıdır; karar ikinci önizlemede gider", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({
        pending_decisions: [2],
        stats: aktarimSayilari({ suspect: 1 }),
        rows: [
          aktarimSatiri({
            row: 2,
            bucket: "suspect",
            needs_decision: true,
            candidates: [{ work: 7, row: null, title: "Şiir Defteri", authors: "Ayşe Yılmaz" }],
          }),
        ],
      }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    await screen.findByText("Karar bekleyen satırlar (1)");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
    expect(screen.getByText(/1 satır karar bekliyor/)).toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText("Kararınız"),
      "“Şiir Defteri” eserine nüsha ekle",
    );
    await user.click(screen.getByRole("button", { name: "Yeniden önizle" }));

    await waitFor(() => expect(kapi.aktarimOnizle).toHaveBeenCalledTimes(2));
    expect(sonOnizlemeGovdesi()).toMatchObject({
      decisions: { 2: { action: "attach", work: 7 } },
    });
  });

  it("aday listesi tavana takıldıysa kaç kayıt daha olduğu yazılır", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({
        pending_decisions: [2],
        stats: aktarimSayilari({ suspect: 1 }),
        rows: [
          aktarimSatiri({
            row: 2,
            bucket: "suspect",
            needs_decision: true,
            candidates: [{ work: 7, row: null, title: "Matematik", authors: "Ayşe Yılmaz" }],
            candidate_count: 300,
            candidates_truncated: true,
          }),
        ],
      }),
    );
    ekranaBas();
    await dosyaSecVeOnizle(user);

    expect(await screen.findByText(/ve 299 kayıt daha/)).toBeInTheDocument();
  });

  it("karar bekleyen satır sayısı listelenenden çoksa fark açıkça söylenir", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({
        // Sunucu satır raporunu tavanlar (MAX_REPORT_ROWS): listede 1 satır var,
        // karar bekleyen 612. Kullanıcı "hepsini karara bağladım ama sayı
        // düşmedi" sanmasın.
        pending_decisions: Array.from({ length: 612 }, (_, i) => i + 2),
        stats: aktarimSayilari({ suspect: 612 }),
        rows: [aktarimSatiri({ row: 2, bucket: "suspect", needs_decision: true })],
      }),
    );
    ekranaBas();
    await dosyaSecVeOnizle(user);

    expect(await screen.findByText(/kalan 611 satır sırayla gelecek/)).toBeInTheDocument();
  });

  it("bölüm listesinde olmayan değer sorulur; yeni bölüm kararı sunucuya gider", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({ unknown_sections: [{ value: "Gezi", rows: [2, 5], count: 2 }] }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    await screen.findByText("Bölüm listesinde bulunmayan değerler (1)");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Karşılığı"), "Yeni bölüm aç: “Gezi”");
    await user.click(screen.getByRole("button", { name: "Yeniden önizle" }));

    await waitFor(() => expect(kapi.aktarimOnizle).toHaveBeenCalledTimes(2));
    expect(sonOnizlemeGovdesi()).toMatchObject({ new_sections: ["Gezi"] });
  });

  it("var olan bölümle eşleştirme section_map olarak gider", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({ unknown_sections: [{ value: "Tarihi Eserler", rows: [3], count: 1 }] }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    await user.selectOptions(await screen.findByLabelText("Karşılığı"), "Tarih");
    await user.click(screen.getByRole("button", { name: "Yeniden önizle" }));

    await waitFor(() => expect(kapi.aktarimOnizle).toHaveBeenCalledTimes(2));
    expect(sonOnizlemeGovdesi()).toMatchObject({ section_map: { "Tarihi Eserler": 2 } });
  });

  it("aynı dosya daha önce uygulanmışsa uygulama ENGELLENİR", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({ already_applied: true, applied_at: "20.09.2026" }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    // Bant (tarih ayrı bir metin düğümündedir) ve uygulamanın önündeki engel.
    expect(
      await screen.findByText(/Aynı dosya ikinci kez uygulanamaz — kitaplar kayda iki kez girerdi/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Bu dosya 20.09.2026 tarihinde zaten aktarıldı; aynı dosya ikinci kez uygulanamaz.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
    expect(kapi.aktarimiUygula).not.toHaveBeenCalled();
  });

  it("uygulama edinim alanlarını taşır, sonuç barkod aralığını basılı biçimde yazar", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(kapi.aktarimiUygula).toHaveBeenCalledTimes(1));
    const govde = kapi.aktarimiUygula.mock.calls[0][0] as Record<string, unknown>;
    // Uygulama önizlemenin gövdesini taşır (DOSYA DAHİL) + edinim alanları.
    expect(govde.file).toBeInstanceOf(File);
    expect(govde.method).toBe("EXISTING_STOCK");

    expect(await screen.findByText("Aktarım tamamlandı")).toBeInTheDocument();
    expect(screen.getByText(/2026-000101 ile 2026-000103 arasında/)).toBeInTheDocument();
    // "Bu partinin etiketlerini bas" kısayolu (§8.1) Etiketler → Basım Kuyruğu'nu
    // o edinim partisine süzer; nüsha kimlikleri adrese taşınmaz.
    expect(screen.getByRole("link", { name: "Bu partinin etiketlerini bas" })).toHaveAttribute(
      "href",
      "/katalog/etiketler?edinim=4",
    );
    // Yarım kalan önizleme koşusu geçmişe çöp bırakmaz.
    expect(kapi.aktarimiIptalEt).toHaveBeenCalledWith(11);
  });

  it("sunucu uygulamayı reddederse gerekçe UYGULA düğmesinin yanında yazar", async () => {
    const user = userEvent.setup();
    kapi.aktarimiUygula.mockRejectedValue(
      new ApiError(400, "validation_error", "Bağışta komisyon kararı zorunludur.", {
        commission_decision: ["Bağışta komisyon kararı zorunludur."],
      }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Uygula" }));

    expect(await screen.findByText("Bağışta komisyon kararı zorunludur.")).toBeInTheDocument();
    expect(screen.queryByText("Aktarım tamamlandı")).toBeNull();
  });

  it("ders kitabı ve tahmini kod satırları önizlemede ayrıca söylenir", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({
        stats: aktarimSayilari({ reference_defaults: 2, estimated_codes: 1 }),
        rows: [aktarimSatiri({ reference_by_textbook: true, classification_source: "ESTIMATED" })],
      }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    expect(
      await screen.findByText(/ders kitabı olduğu için danışma kaynağı sayıldı/),
    ).toBeInTheDocument();
    expect(screen.getByText(/sınıflama kodu “tahmini” olarak işaretlendi/)).toBeInTheDocument();
  });

  it("satır listesi sorunlu satır sayısını başlıkta söyler", async () => {
    const user = userEvent.setup();
    kapi.aktarimOnizle.mockResolvedValueOnce(
      aktarimRaporu({
        rows: [
          aktarimSatiri(),
          aktarimSatiri({
            row: 3,
            bucket: "skipped",
            issues: ["Eser adı boş; satır içe aktarılmadı."],
          }),
        ],
      }),
    );
    ekranaBas();
    await screen.findByRole("heading", { level: 1, name: "İçe Aktarma" });
    await dosyaSecVeOnizle(user);

    expect(await screen.findByText(/Satır listesi \(2 satır, 1 sorunlu\)/)).toBeInTheDocument();
    expect(screen.getByText("Eser adı boş; satır içe aktarılmadı.")).toBeInTheDocument();
  });
});

describe("İçe Aktarma — yapay zekâ köprüsü", () => {
  it("komut metni ve dört uyarı SUNUCUDAN gelir, ekranda yazılıdır", async () => {
    ekranaBas("/katalog/ice-aktarma?tab=kopru");

    expect(await screen.findByText(KOMUT.prompt)).toBeInTheDocument();
    for (const not of KOMUT.notes) {
      expect(screen.getByText(not)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Komutu kopyala" })).toBeInTheDocument();
  });

  it("komut panoya kopyalanır", async () => {
    const user = userEvent.setup();
    ekranaBas("/katalog/ice-aktarma?tab=kopru");
    await screen.findByText(KOMUT.prompt);

    await user.click(screen.getByRole("button", { name: "Komutu kopyala" }));

    await expect(navigator.clipboard.readText()).resolves.toBe(KOMUT.prompt);
    expect(await screen.findByText("Komut metni panoya kopyalandı.")).toBeInTheDocument();
  });

  it("yapıştırılan JSON dosyasız gövdeyle önizlenir", async () => {
    const user = userEvent.setup();
    ekranaBas("/katalog/ice-aktarma?tab=kopru");
    await screen.findByText(KOMUT.prompt);

    await user.type(
      screen.getByLabelText("Yapay zekâ aracının verdiği JSON"),
      '{{"schema_version": "v1"}',
    );
    await user.click(screen.getByRole("button", { name: "Önizle" }));

    await waitFor(() => expect(kapi.aktarimOnizle).toHaveBeenCalledTimes(1));
    expect(sonOnizlemeGovdesi()).toEqual({ payload: '{"schema_version": "v1"}' });
  });

  it("uyarılar yüklenemezse köprü KAPANIR (fail-closed)", async () => {
    kapi.kopruKomutu.mockRejectedValue(new ApiError(503, "servis_yok", "Komut metni okunamadı."));
    ekranaBas("/katalog/ice-aktarma?tab=kopru");

    // §8.2'nin dört uyarısı ekrana basılamadıysa, okulun kitap listesini dışarı
    // çıkaran adım da başlayamaz.
    await screen.findByText(/Komut metni okunamadı/);
    expect(screen.getByLabelText("Yapay zekâ aracının verdiği JSON")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Önizle" })).toBeDisabled();
  });
});

describe("İçe Aktarma — geçmiş", () => {
  it("uygulanmış koşu iptal edilemez, önizleme koşusu edilebilir", async () => {
    const user = userEvent.setup();
    kapi.aktarimGecmisi.mockResolvedValue(
      sayfa([
        aktarimKosusu({ id: 11, status: "APPLIED", status_display: "Uygulandı" }),
        aktarimKosusu({
          id: 12,
          status: "DRY_RUN",
          status_display: "Önizleme",
          uploaded_file_name: "deneme.xlsx",
        }),
      ]),
    );
    ekranaBas("/katalog/ice-aktarma?tab=gecmis");

    const satirlar = await screen.findAllByRole("row");
    // Başlık satırı + iki koşu.
    expect(satirlar).toHaveLength(3);
    expect(within(satirlar[1]).queryByRole("button")).toBeNull();

    await user.click(within(satirlar[2]).getByRole("button", { name: "Önizlemeyi iptal et" }));
    await user.click(await screen.findByRole("button", { name: "İptal et" }));

    await waitFor(() => expect(kapi.aktarimiIptalEt).toHaveBeenCalledWith(12));
  });
});
