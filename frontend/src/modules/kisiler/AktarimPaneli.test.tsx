// Aktarım paneli — e-Okul MUTABAKATI (tasarım §8.3) ve AYRILIŞ HAVUZU (F1 eki 7):
// aktarım kimseyi ayırmaz ve silmez; listede bulunmayanlar havuza eklenir, karar
// Kişiler → Ayrılış Havuzu'nda verilir. Öğrenci: bütün şubeleri içeren tek dosya
// önerisi, "Bu dosya okulun tam listesidir" onayı, şube bazında etki tablosu,
// "N öğrenci ayrılış havuzuna eklenecek, M öğrenci havuzdan çıkacak" notu.
// Personel: listede olmayanlar havuza eklenecek (eski "ayrıldı sayılsın mı?" seçimi
// yok), "olası aynı kişi" çiftleri ve aktarımdan sonra onaylı "Birleştir", üye türü
// denetim uyarısı. Tüm adlar uydurmadır (KVKK).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { PersonnelImportReport, StudentImportReport } from "../okul/api";

const okulApiMock = vi.hoisted(() => ({
  previewStudentImport: vi.fn(),
  commitStudentImport: vi.fn(),
  previewPersonnelImport: vi.fn(),
  commitPersonnelImport: vi.fn(),
  mergePersonnel: vi.fn(),
  studentTemplate: vi.fn(),
  personnelTemplate: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

vi.mock("../../lib/download", () => ({ saveBlob: vi.fn() }));

import AktarimPaneli from "./AktarimPaneli";
import type { ImportKind } from "./AktarimPaneli";

const OGRENCI_ONIZLEME: StudentImportReport = {
  file_hash: "abc",
  file_name: "",
  total_rows: 3,
  processed: 3,
  created_students: 1,
  updated_students: 1,
  unchanged_students: 1,
  reactivated_students: 0,
  pool_added_students: 2,
  pool_removed_students: 1,
  full_list: true,
  already_imported: false,
  dry_run: true,
  classes: [
    {
      class_label: "10/A",
      class_level: 10,
      class_section: "A",
      created: 1,
      updated: 1,
      unchanged: 1,
      to_pool: 1,
    },
    {
      class_label: "",
      class_level: null,
      class_section: "",
      created: 0,
      updated: 0,
      unchanged: 0,
      to_pool: 1,
    },
  ],
  pool_added: [
    { id: 7, full_name: "DENEME EKSİK", student_number: "702", class_label: "10/A" },
    { id: 8, full_name: "NAKİL ÖĞRENCİ", student_number: "", class_label: "" },
  ],
  warnings: [],
  skipped: [{ row_number: 4, field: "number", issue: "Okul numarası bulunamadı.", raw_value: "" }],
};

const PERSONEL_ONIZLEME: PersonnelImportReport = {
  file_hash: "xyz",
  file_name: "",
  total_rows: 2,
  processed: 2,
  created_personnel: 1,
  updated_personnel: 0,
  unchanged_personnel: 1,
  reactivated_personnel: 0,
  pool_added_personnel: 2,
  pool_removed_personnel: 0,
  similar_pair_count: 1,
  already_imported: false,
  dry_run: true,
  pool_added: [
    { id: 11, full_name: "AYŞE KARA" },
    { id: 12, full_name: "MEHMET DEMİR" },
  ],
  similar_pairs: [
    {
      row_number: 3,
      row_name: "AYŞE BEYAZ",
      existing_id: 11,
      existing_name: "AYŞE KARA",
      new_id: null,
      reason: "ad_ayni_soyad_farkli",
    },
  ],
  warnings: [
    {
      row_number: 2,
      field: "member_kind",
      issue: "Üye türünü denetleyin: görev bilgisi tanınmadı.",
      raw_value: "",
    },
  ],
  skipped: [],
};

function kur(kind: ImportKind, onImported = vi.fn()) {
  render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <AktarimPaneli kind={kind} onImported={onImported} />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
  return onImported;
}

async function yapistirVeOnizle(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "liste");
  await user.click(screen.getByRole("button", { name: /Önizle/ }));
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("AktarimPaneli — öğrenci mutabakatı ve ayrılış havuzu", () => {
  it("bütün şubeleri içeren tek dosyayı belirgin biçimde önerir", () => {
    kur("students");

    expect(
      screen.getByText(/Önerilen yol: okulun bütün şubelerini içeren listeyi tek dosyada/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Kimse kendiliğinden ayrılmaz/)).toBeInTheDocument();
  });

  it("tam liste onayı varsayılan kapalıdır, açıklaması vardır ve önizlemeye gider", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    const user = userEvent.setup();
    kur("students");

    const onay = screen.getByRole("checkbox", { name: /Bu dosya okulun tam listesidir/ });
    expect(onay).not.toBeChecked();
    expect(screen.getByText(/yalnız dosyada bulunan şubeler karşılaştırılır/)).toBeInTheDocument();
    await user.click(onay);
    await yapistirVeOnizle(user);

    await waitFor(() =>
      expect(okulApiMock.previewStudentImport).toHaveBeenCalledWith(
        { text: "liste" },
        { fullList: true },
      ),
    );
  });

  it("önizleme havuz etkisini söyler: şube tablosu, eklenecekler ve çıkacaklar", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);

    expect(
      await screen.findByText("2 öğrenci ayrılış havuzuna eklenecek, 1 öğrenci havuzdan çıkacak."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Aktarım kimseyi ayırmaz ve kimsenin kaydını silmez/),
    ).toBeInTheDocument();
    const tablo = screen.getByRole("table", { name: "Şube bazında etki" });
    expect(
      within(tablo).getByRole("columnheader", { name: "Havuza eklenecek" }),
    ).toBeInTheDocument();
    const satirlar = within(tablo).getAllByRole("row");
    expect(
      within(satirlar[1])
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["10/A", "1", "1", "1", "1"]);
    expect(within(satirlar[2]).getByText("Sınıfsız")).toBeInTheDocument();
    expect(screen.getByText("Ayrılış havuzuna eklenecek öğrenciler (2)")).toBeInTheDocument();
    expect(screen.getByText("DENEME EKSİK")).toBeInTheDocument();
    expect(screen.getByText(/okulun tamamıyla yapıldı/)).toBeInTheDocument();
    // Eski "ayrılacak" dili kalmadı.
    expect(screen.queryByText(/ayrılacak/i)).toBeNull();
    // Atlanan satırın alan kodu kullanıcı adına çevrilir.
    expect(screen.getByRole("cell", { name: "Okul no" })).toBeInTheDocument();
  });

  it("onay kutusu değişince eski önizleme düşer (kapsam değişti)", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("checkbox", { name: /Bu dosya okulun tam listesidir/ }));

    expect(screen.queryByText("Önizleme — hiçbir kayıt yazılmadı")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();
  });

  it("şube kapsamlı önizleme başka şubeye geçen öğrencinin geçici olarak havuza düşeceğini söyler", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue({ ...OGRENCI_ONIZLEME, full_list: false });
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    expect(screen.getByText(/Kayıtlı oldukları şube dosyada var/)).toBeInTheDocument();
    expect(
      screen.getByText(/yeni şubesinin listesi aktarılınca havuzdan kendiliğinden çıkar/),
    ).toBeInTheDocument();
  });

  it("aktarım kimseyi ayırmadığı için onay istemez; sonuç havuza bağlanır", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    okulApiMock.commitStudentImport.mockResolvedValue({ ...OGRENCI_ONIZLEME, dry_run: false });
    const user = userEvent.setup();
    const onImported = kur("students");
    await yapistirVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitStudentImport).toHaveBeenCalledWith(
        { text: "liste" },
        { fullList: false },
      ),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByText("Ayrılış havuzuna eklenen öğrenciler (2)")).toBeInTheDocument();
    expect(
      screen.getByText("2 öğrenci ayrılış havuzuna eklendi, 1 öğrenci havuzdan çıktı."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayrılış Havuzu'nu aç" })).toHaveAttribute(
      "href",
      "/kisiler?tab=havuz",
    );
    expect(onImported).toHaveBeenCalledTimes(1);
  });

  it("girdi yokken önizleme istek atmaz, yönlendirir", async () => {
    const user = userEvent.setup();
    kur("students");

    await user.click(screen.getByRole("button", { name: /Önizle/ }));

    expect(
      await screen.findByText("Önce bir dosya seçin ya da listeyi yapıştırın."),
    ).toBeInTheDocument();
    expect(okulApiMock.previewStudentImport).not.toHaveBeenCalled();
  });

  it("409 parola_gerekli önizlemede kurulum sihirbazına yönlendirir", async () => {
    okulApiMock.previewStudentImport.mockRejectedValue(
      new ApiError(409, "parola_gerekli", "Kişi kaydı için önce yönetici parolasını kurun."),
    );
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);

    expect(await screen.findByText("Önce yönetici parolasını kurun")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kurulum sihirbazını aç" })).toBeInTheDocument();
  });

  it("hiç satır işlenemeyen dosyanın uyarısı “Ayrılış havuzu” alanıyla gösterilir", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue({
      ...OGRENCI_ONIZLEME,
      pool_added_students: 0,
      pool_removed_students: 0,
      pool_added: [],
      warnings: [
        {
          row_number: 1,
          field: "leave_pool",
          issue: "Dosyada işlenebilen öğrenci satırı bulunamadı.",
          raw_value: "",
        },
      ],
    });
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);

    expect(await screen.findByRole("cell", { name: "Ayrılış havuzu" })).toBeInTheDocument();
  });

  it("şablon indirilemezse hata bandı görünür", async () => {
    okulApiMock.studentTemplate.mockRejectedValue(new Error("ağ"));
    const user = userEvent.setup();
    kur("students");

    await user.click(screen.getByRole("button", { name: "Şablon indir" }));

    expect(await screen.findByText("Şablon indirilemedi.")).toBeInTheDocument();
  });
});

describe("AktarimPaneli — personel mutabakatı ve ayrılış havuzu", () => {
  it("görev sütununun yalnız üye türü için okunduğu, branşın okunmadığı söylenir", () => {
    kur("personnel");
    expect(
      screen.getByText(
        /yalnız üye türünü .* belirlemek için kullanılır ve saklanmaz, branş okunmaz/,
      ),
    ).toBeInTheDocument();
    // Tek dosya önerisi yalnız öğrenci panelindedir.
    expect(screen.queryByText(/Önerilen yol/)).toBeNull();
  });

  it("listede olmayanlar havuza eklenecek diye listelenir; seçim yok, aktarım onaysız", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    okulApiMock.commitPersonnelImport.mockResolvedValue({ ...PERSONEL_ONIZLEME, dry_run: false });
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    expect(
      await screen.findByText("Listede olmayan 2 kişi ayrılış havuzuna eklenecek"),
    ).toBeInTheDocument();
    expect(screen.getByText("MEHMET DEMİR")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByText(/Ayrıldı sayılsın mı/)).toBeNull();
    expect(screen.getByText(/olası aynı kişi — aşağıya bakın/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitPersonnelImport).toHaveBeenCalledWith({ text: "liste" }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByText("İçe aktarma sonucu")).toBeInTheDocument();
    expect(screen.getByText("Listede olmayan 2 kişi ayrılış havuzuna eklendi")).toBeInTheDocument();
  });

  it("önizlemede olası aynı kişi gösterilir ama birleştirme aktarımdan sonra sunulur", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    expect(await screen.findByText("Olası aynı kişi (1)")).toBeInTheDocument();
    expect(screen.getByText("Satır 3: AYŞE BEYAZ ↔ kayıttaki AYŞE KARA")).toBeInTheDocument();
    expect(
      screen.getByText(/burada ya da Ayrılış Havuzu'nda birleştirebilirsiniz/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /birleştir/i })).toBeNull();
  });

  it("aktarımdan sonra “Birleştir” onaylı çalışır, çift ve havuz satırı listeden düşer", async () => {
    const sonuc: PersonnelImportReport = {
      ...PERSONEL_ONIZLEME,
      dry_run: false,
      similar_pairs: [{ ...PERSONEL_ONIZLEME.similar_pairs[0], new_id: 21 }],
    };
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    okulApiMock.commitPersonnelImport.mockResolvedValue(sonuc);
    okulApiMock.mergePersonnel.mockResolvedValue({});
    const user = userEvent.setup();
    const onImported = kur("personnel");
    await yapistirVeOnizle(user);
    await screen.findByText("Olası aynı kişi (1)");
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    const birlestir = await screen.findByRole("button", {
      name: "AYŞE KARA kaydını AYŞE BEYAZ kaydıyla birleştir",
    });
    await user.click(birlestir);
    const onay = await screen.findByRole("dialog", { name: "Bu iki kayıt aynı kişi mi?" });
    expect(within(onay).getByText(/eski kayıt silinir/)).toBeInTheDocument();
    // Gerekçe + ikinci doğrulama (TB18): kutu işaretlenmeden düğme kapalıdır.
    expect(within(onay).getByText(/adı aynı, soyadı farklı/)).toBeInTheDocument();
    const dugme = within(onay).getByRole("button", { name: "Birleştir" });
    expect(dugme).toBeDisabled();
    await user.click(
      within(onay).getByRole("checkbox", {
        name: "Bu iki kaydın aynı kişi olduğunu doğruladım",
      }),
    );
    await user.click(dugme);

    await waitFor(() => expect(okulApiMock.mergePersonnel).toHaveBeenCalledWith(11, 21));
    await waitFor(() => expect(screen.queryByText(/Satır 3: AYŞE BEYAZ/)).toBeNull());
    expect(screen.getByText("Listede olmayan 1 kişi ayrılış havuzuna eklendi")).toBeInTheDocument();
    expect(onImported).toHaveBeenCalledTimes(2); // aktarım + birleştirme
  });

  it("birleştirme onayından vazgeçilirse istek atılmaz; hata bantta gösterilir", async () => {
    const sonuc: PersonnelImportReport = {
      ...PERSONEL_ONIZLEME,
      dry_run: false,
      similar_pairs: [{ ...PERSONEL_ONIZLEME.similar_pairs[0], new_id: 21 }],
    };
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    okulApiMock.commitPersonnelImport.mockResolvedValue(sonuc);
    okulApiMock.mergePersonnel.mockRejectedValue(
      new ApiError(400, "validation_error", "Bir kişi kendisiyle birleştirilemez."),
    );
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);
    await screen.findByText("Olası aynı kişi (1)");
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    const birlestir = await screen.findByRole("button", { name: /kaydıyla birleştir/ });
    await user.click(birlestir);
    await user.click(
      within(await screen.findByRole("dialog", { name: "Bu iki kayıt aynı kişi mi?" })).getByRole(
        "button",
        { name: "Vazgeç" },
      ),
    );
    expect(okulApiMock.mergePersonnel).not.toHaveBeenCalled();

    await user.click(birlestir);
    const onay = await screen.findByRole("dialog", { name: "Bu iki kayıt aynı kişi mi?" });
    // Kutu vazgeçilen onaydan devralınmaz: her açılışta yeniden işaretlenir.
    await user.click(
      within(onay).getByRole("checkbox", { name: "Bu iki kaydın aynı kişi olduğunu doğruladım" }),
    );
    await user.click(within(onay).getByRole("button", { name: "Birleştir" }));
    expect(await screen.findByText("Bir kişi kendisiyle birleştirilemez.")).toBeInTheDocument();
  });

  it("üye türü denetim uyarısı sayıyla gösterilir, alan adı Türkçedir", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    expect(await screen.findByText(/1 satırda üye türünü denetleyin/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Üye türü" })).toBeInTheDocument();
    expect(screen.getByText("Havuza eklenecek")).toBeInTheDocument();
    expect(
      screen.getByText("2 kişi ayrılış havuzuna eklenecek, 0 kişi havuzdan çıkacak."),
    ).toBeInTheDocument();
  });

  it("personel şablonu indirilir", async () => {
    const blob = new Blob(["x"]);
    okulApiMock.personnelTemplate.mockResolvedValue(blob);
    const user = userEvent.setup();
    kur("personnel");

    await user.click(screen.getByRole("button", { name: "Şablon indir" }));

    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, "sablon-personel.xlsx"));
  });
});
