// Aktarım paneli — e-Okul MUTABAKATI (tasarım §8.3). Öğrenci: "Bu dosya okulun tam
// listesidir" onayı, şube bazında etki tablosu, ayrılacaklar listesi ve ayrılış
// doğuran aktarımın onayı. Personel: listede olmayanlar (işaretlenenler ayrılır,
// varsayılan hiçbiri), "olası aynı kişi" çiftleri ve aktarımdan sonra onaylı
// "Birleştir", üye türü denetim uyarısı. Tüm adlar uydurmadır (KVKK).

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
  leaving_students: 2,
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
      leaving: 1,
    },
    {
      class_label: "",
      class_level: null,
      class_section: "",
      created: 0,
      updated: 0,
      unchanged: 0,
      leaving: 1,
    },
  ],
  leaving: [
    { id: 7, full_name: "DENEME AYRILAN", student_number: "702", class_label: "10/A" },
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
  missing_count: 2,
  left_personnel: 0,
  similar_pair_count: 1,
  already_imported: false,
  dry_run: true,
  missing: [
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

describe("AktarimPaneli — öğrenci mutabakatı", () => {
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

  it("şube bazında etki tablosu ve ayrılacaklar listesi gösterilir", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    const user = userEvent.setup();
    kur("students");
    await yapistirVeOnizle(user);

    const tablo = await screen.findByRole("table", { name: "Şube bazında etki" });
    const satirlar = within(tablo).getAllByRole("row");
    expect(
      within(satirlar[1])
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["10/A", "1", "1", "1", "1"]);
    expect(within(satirlar[2]).getByText("Sınıfsız")).toBeInTheDocument();
    expect(screen.getByText("Ayrılacak öğrenciler (2)")).toBeInTheDocument();
    expect(screen.getByText("DENEME AYRILAN")).toBeInTheDocument();
    expect(screen.getByText(/okulun tamamıyla yapıldı/)).toBeInTheDocument();
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

  it("ayrılış doğuran aktarım onaysız uygulanmaz", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    const user = userEvent.setup();
    const onImported = kur("students");
    await yapistirVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Aktar" }));
    const onay = await screen.findByRole("dialog", { name: "Aktarım uygulansın mı?" });
    expect(within(onay).getByText(/2 öğrenci okuldan ayrılmış sayılacak/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));

    expect(okulApiMock.commitStudentImport).not.toHaveBeenCalled();
    expect(onImported).not.toHaveBeenCalled();
  });

  it("onaylanınca aktarılır, sonuç “Ayrılan” diye gösterilir", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(OGRENCI_ONIZLEME);
    okulApiMock.commitStudentImport.mockResolvedValue({ ...OGRENCI_ONIZLEME, dry_run: false });
    const user = userEvent.setup();
    const onImported = kur("students");
    await yapistirVeOnizle(user);
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Aktar" }));
    const onay = await screen.findByRole("dialog", { name: "Aktarım uygulansın mı?" });
    await user.click(within(onay).getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitStudentImport).toHaveBeenCalledWith(
        { text: "liste" },
        { fullList: false },
      ),
    );
    expect(await screen.findByText("Ayrılan öğrenciler (2)")).toBeInTheDocument();
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

  it("şablon indirilemezse hata bandı görünür", async () => {
    okulApiMock.studentTemplate.mockRejectedValue(new Error("ağ"));
    const user = userEvent.setup();
    kur("students");

    await user.click(screen.getByRole("button", { name: "Şablon indir" }));

    expect(await screen.findByText("Şablon indirilemedi.")).toBeInTheDocument();
  });
});

describe("AktarimPaneli — personel mutabakatı", () => {
  it("görev sütununun yalnız üye türü için okunduğu, branşın okunmadığı söylenir", () => {
    kur("personnel");
    expect(
      screen.getByText(
        /yalnız üye türünü .* belirlemek için kullanılır ve saklanmaz, branş okunmaz/,
      ),
    ).toBeInTheDocument();
  });

  it("listede olmayanlar sorulur; yalnız işaretlenenler ayrılır (onaylı)", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    okulApiMock.commitPersonnelImport.mockResolvedValue({
      ...PERSONEL_ONIZLEME,
      dry_run: false,
      left_personnel: 1,
    });
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    const soru = await screen.findByRole("group", {
      name: "2 kişi listede yok. Ayrıldı sayılsın mı?",
    });
    const kutular = within(soru).getAllByRole("checkbox");
    expect(kutular.every((k) => !(k as HTMLInputElement).checked)).toBe(true);
    // Olası aynı kişi çiftindeki kayıt için uyarı notu.
    expect(within(soru).getByText(/birleştirmek için işaretlemeyin/)).toBeInTheDocument();

    await user.click(within(soru).getByRole("checkbox", { name: /MEHMET DEMİR/ }));
    await user.click(screen.getByRole("button", { name: "Aktar" }));
    const onay = await screen.findByRole("dialog", { name: "Aktarım uygulansın mı?" });
    expect(within(onay).getByText(/İşaretlediğiniz 1 kişi/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitPersonnelImport).toHaveBeenCalledWith(
        { text: "liste" },
        { markLeftIds: [12] },
      ),
    );
    expect(await screen.findByText("İçe aktarma sonucu")).toBeInTheDocument();
  });

  it("işaret kaldırılınca seçim geri alınır, onaysız aktarılır", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    okulApiMock.commitPersonnelImport.mockResolvedValue({ ...PERSONEL_ONIZLEME, dry_run: false });
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    const kutu = await screen.findByRole("checkbox", { name: /AYŞE KARA/ });
    await user.click(kutu);
    await user.click(kutu);
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitPersonnelImport).toHaveBeenCalledWith(
        { text: "liste" },
        { markLeftIds: [] },
      ),
    );
    expect(screen.queryByRole("dialog", { name: "Aktarım uygulansın mı?" })).toBeNull();
  });

  it("önizlemede olası aynı kişi gösterilir ama birleştirme aktarımdan sonra sunulur", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    expect(await screen.findByText("Olası aynı kişi (1)")).toBeInTheDocument();
    expect(screen.getByText("Satır 3: AYŞE BEYAZ ↔ kayıttaki AYŞE KARA")).toBeInTheDocument();
    expect(
      screen.getByText(/Aktardıktan sonra iki kaydı birleştirebilirsiniz/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /birleştir/i })).toBeNull();
  });

  it("aktarımdan sonra “Birleştir” onaylı çalışır, çift listeden düşer", async () => {
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
    const onay = await screen.findByRole("dialog", { name: "Kayıtlar birleştirilsin mi?" });
    expect(within(onay).getByText(/eski kayıt silinir/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Birleştir" }));

    await waitFor(() => expect(okulApiMock.mergePersonnel).toHaveBeenCalledWith(11, 21));
    // Bildirim, "İçe aktarma tamamlandı." bildiriminin ardından kuyruktan gelir.
    await waitFor(() => expect(screen.queryByText(/Satır 3: AYŞE BEYAZ/)).toBeNull());
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
      within(await screen.findByRole("dialog", { name: "Kayıtlar birleştirilsin mi?" })).getByRole(
        "button",
        { name: "Vazgeç" },
      ),
    );
    expect(okulApiMock.mergePersonnel).not.toHaveBeenCalled();

    await user.click(birlestir);
    await user.click(
      within(await screen.findByRole("dialog", { name: "Kayıtlar birleştirilsin mi?" })).getByRole(
        "button",
        { name: "Birleştir" },
      ),
    );
    expect(await screen.findByText("Bir kişi kendisiyle birleştirilemez.")).toBeInTheDocument();
  });

  it("üye türü denetim uyarısı sayıyla gösterilir, alan adı Türkçedir", async () => {
    okulApiMock.previewPersonnelImport.mockResolvedValue(PERSONEL_ONIZLEME);
    const user = userEvent.setup();
    kur("personnel");
    await yapistirVeOnizle(user);

    expect(await screen.findByText(/1 satırda üye türünü denetleyin/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Üye türü" })).toBeInTheDocument();
    expect(screen.getByText("Listede olmayan")).toBeInTheDocument();
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
