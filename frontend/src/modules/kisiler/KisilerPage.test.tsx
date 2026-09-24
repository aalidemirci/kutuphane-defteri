// Kişiler sayfası testi: sekmeli liste, KVKK gereği TCKN'nin listede
// GÖRÜNMEMESİ, gecikmeli arama, elle ekleme/düzenleme/silme akışı (alan hataları
// backend `fields`'tan), boş/hata durumları ve içe aktarma paneli (önizle → aktar,
// already_imported uyarısı, şablon indirme). Cinsiyet, fotoğraf ve BEP bu
// programda yoktur; geri gelmesinler diye ayrıca sabitlenir. Sekme URL'de
// tutulur (`?tab=personel`), bu yüzden sayfa yönlendirici içinde kurulur.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type {
  Personnel,
  PersonnelImportReport,
  Student,
  StudentImportReport,
  StudentListParams,
} from "../okul/api";

const okulApiMock = vi.hoisted(() => ({
  getGradeLevels: vi.fn(),
  listStudents: vi.fn(),
  createStudent: vi.fn(),
  updateStudent: vi.fn(),
  deleteStudent: vi.fn(),
  listPersonnel: vi.fn(),
  createPersonnel: vi.fn(),
  updatePersonnel: vi.fn(),
  deletePersonnel: vi.fn(),
  leaveStudent: vi.fn(),
  leavePersonnel: vi.fn(),
  mergePersonnel: vi.fn(),
  getLeavePool: vi.fn(),
  resolveLeavePool: vi.fn(),
  previewStudentImport: vi.fn(),
  commitStudentImport: vi.fn(),
  previewPersonnelImport: vi.fn(),
  commitPersonnelImport: vi.fn(),
  studentTemplate: vi.fn(),
  personnelTemplate: vi.fn(),
}));

// Yalnız `okulApi` taklit edilir; etiket sabitleri + importCounts gerçek kalır
// (sayfa ile api katmanı arasındaki sözleşme sahte veriyle örtülmesin).
vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

vi.mock("../../lib/download", () => ({ saveBlob: vi.fn() }));

import KisilerPage from "./KisilerPage";

const STUDENT: Student = {
  id: 1,
  first_name: "Ayşe",
  last_name: "Yılmaz",
  full_name: "Ayşe Yılmaz",
  student_number: "123",
  class_level: 10,
  class_section: "A",
  class_label: "10/A",
  status: "ACTIVE",
  left_at: null,
  leave_candidate_since: null,
};

const PERSONNEL: Personnel = {
  id: 5,
  first_name: "Mehmet",
  last_name: "Demirci",
  full_name: "Mehmet Demirci",
  member_kind: "TEACHER",
  is_active: true,
  left_at: null,
  leave_candidate_since: null,
};

const PREVIEW_REPORT: StudentImportReport = {
  file_hash: "abc",
  file_name: "",
  total_rows: 4,
  processed: 3,
  created_students: 2,
  updated_students: 1,
  unchanged_students: 0,
  reactivated_students: 0,
  pool_added_students: 0,
  pool_removed_students: 0,
  full_list: false,
  already_imported: false,
  dry_run: true,
  classes: [],
  pool_added: [],
  warnings: [{ row_number: 3, field: "class", issue: "Sınıf/şube çözülemedi", raw_value: "8-A" }],
  skipped: [],
};

function page<T>(results: T[], count = results.length) {
  return { count, next: null, previous: null, results };
}

/** `route` derin bağlantıyı sınar: sekme URL'deki `tab` parametresinden okunur. */
function renderPage(route = "/kisiler") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <KisilerPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  okulApiMock.getGradeLevels.mockResolvedValue({
    levels: [
      { value: 9, label: "9" },
      { value: 10, label: "10" },
    ],
    prep_enabled: false,
  });
  okulApiMock.listStudents.mockResolvedValue(page([STUDENT]));
  okulApiMock.listPersonnel.mockResolvedValue(page([PERSONNEL]));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("KisilerPage — öğrenci listesi", () => {
  it("mutlu yol: liste yüklenir (yalnız ad + no + sınıf + durum — KVKK'da fazlası yok)", async () => {
    renderPage();
    expect(await screen.findByText("Ayşe Yılmaz")).toBeInTheDocument();
    expect(screen.getByText("10/A")).toBeInTheDocument();
    expect(screen.getByText("Aktif")).toBeInTheDocument();
    expect(okulApiMock.listStudents).toHaveBeenCalledWith({
      search: "",
      classLevel: null,
      classSection: "",
      limit: 25,
      offset: 0,
    });
  });

  it("arama gecikmeli olarak sorguya yansır", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ara"), "yılmaz");

    await waitFor(() =>
      expect(okulApiMock.listStudents).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "yılmaz", offset: 0 }),
      ),
    );
  });

  it("boş liste: yönlendirici boş-durum kartı", async () => {
    okulApiMock.listStudents.mockResolvedValue(page<Student>([]));
    renderPage();
    expect(await screen.findByText("Gösterilecek öğrenci yok")).toBeInTheDocument();
  });

  it("hata: backend Türkçe mesajı hata bandında gösterilir", async () => {
    okulApiMock.listStudents.mockRejectedValue(
      new ApiError(500, "server_error", "Sicil okunamadı."),
    );
    renderPage();
    expect(await screen.findByText("Sicil okunamadı.")).toBeInTheDocument();
  });

  it("hata bandı canlı bölgedir — ekran okuyucuya duyurulur", async () => {
    okulApiMock.listStudents.mockRejectedValue(
      new ApiError(500, "server_error", "Sicil okunamadı."),
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Sicil okunamadı.");
  });
});

describe("KisilerPage — öğrenci ekleme/düzenleme/silme", () => {
  it("zorunlu alan boşken istek atılmaz, hata alanın altında görünür", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    expect(await within(dialog).findByText("Ad zorunludur.")).toBeInTheDocument();
    expect(within(dialog).getByText("Soyad zorunludur.")).toBeInTheDocument();
    expect(okulApiMock.createStudent).not.toHaveBeenCalled();
  });

  it("yeni öğrenci: boş sınıf alanı null olarak gönderilir", async () => {
    okulApiMock.createStudent.mockResolvedValue({ ...STUDENT, id: 2 });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(okulApiMock.createStudent).toHaveBeenCalledWith(
        expect.objectContaining({
          first_name: "Zeynep",
          last_name: "Kaya",
          class_level: null,
        }),
      ),
    );
    // Durum formdan yazılmaz: ayrılış yalnız "Ayrıldı olarak işaretle" ile.
    expect(okulApiMock.createStudent.mock.calls[0][0]).not.toHaveProperty("status");
  });

  it("cinsiyet ne listede ne formda vardır; gövdede gender alanı gönderilmez", async () => {
    okulApiMock.createStudent.mockResolvedValue({ ...STUDENT, id: 3 });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    expect(screen.queryByRole("columnheader", { name: /Cinsiyet/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    expect(within(dialog).queryByLabelText("Cinsiyet")).toBeNull();
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(okulApiMock.createStudent).toHaveBeenCalledTimes(1));
    expect(okulApiMock.createStudent.mock.calls[0][0]).not.toHaveProperty("gender");
  });

  it("düzenlemede değişiklik updateStudent'a gider ve liste tazelenir", async () => {
    okulApiMock.updateStudent.mockResolvedValue({ ...STUDENT, class_section: "B" });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    const sube = within(dialog).getByLabelText("Şube");
    await user.clear(sube);
    await user.type(sube, "b");
    const onceki = okulApiMock.listStudents.mock.calls.length;
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(okulApiMock.updateStudent).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ class_level: 10, class_section: "b" }),
      ),
    );
    expect(await screen.findByText("Öğrenci güncellendi.")).toBeInTheDocument();
    await waitFor(() => expect(okulApiMock.listStudents.mock.calls.length).toBeGreaterThan(onceki));
  });

  it("backend alan hatası (fields) ilgili alanın altına yazılır", async () => {
    okulApiMock.createStudent.mockRejectedValue(
      new ApiError(400, "validation_error", "Girdiğiniz bilgileri kontrol edin.", {
        student_number: ["Bu okul numarası zaten kayıtlı."],
      }),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    expect(await within(dialog).findByText("Bu okul numarası zaten kayıtlı.")).toBeInTheDocument();
    expect(within(dialog).getByText("Girdiğiniz bilgileri kontrol edin.")).toBeInTheDocument();
  });

  it("satıra tıklama düzenleme formunu açar; alanlar dolu gelir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    expect(within(dialog).getByLabelText("Okul no")).toHaveValue("123");
  });

  it("son sayfadaki tek kayıt silinince önceki sayfaya düşer (boş sayfada kilitlenmez)", async () => {
    const SON_KAYIT: Student = {
      ...STUDENT,
      id: 9,
      first_name: "Zeynep",
      last_name: "Kaya",
      full_name: "Zeynep Kaya",
    };
    // İkinci sayfada tek kayıt var; silinince o sayfa boşalır (count 26 → 25).
    let silindi = false;
    okulApiMock.listStudents.mockImplementation((params: StudentListParams) =>
      Promise.resolve(
        (params.offset ?? 0) === 0
          ? page([STUDENT], silindi ? 25 : 26)
          : silindi
            ? page<Student>([], 25)
            : page([SON_KAYIT], 26),
      ),
    );
    okulApiMock.deleteStudent.mockImplementation(() => {
      silindi = true;
      return Promise.resolve(undefined);
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: /Sonraki/ }));
    await screen.findByText("Zeynep Kaya");

    await user.click(screen.getByRole("button", { name: "Zeynep Kaya kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));
    const confirmDialog = await screen.findByRole("dialog", {
      name: "Öğrenci sicilden silinsin mi?",
    });
    await user.click(within(confirmDialog).getByRole("button", { name: "Sil" }));

    // Önceki sayfa yeniden yüklenir: liste dolu ve sayfalama çubuğu yerinde.
    expect(await screen.findByText("Ayşe Yılmaz")).toBeInTheDocument();
    expect(screen.queryByText("Gösterilecek öğrenci yok")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Önceki/ })).toBeDisabled();
  });

  it("silme: onay dialogu onaylanınca API çağrılır", async () => {
    okulApiMock.deleteStudent.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    // Başlık soru, gövde sonuç; silme artık KALICIDIR ve ayrılış yolu ayrıca gösterilir.
    const confirmDialog = await screen.findByRole("dialog", {
      name: "Öğrenci sicilden silinsin mi?",
    });
    expect(within(confirmDialog).getByText(/kalıcı olarak silinir/)).toBeInTheDocument();
    expect(within(confirmDialog).getByText(/Ayrıldı olarak işaretle/)).toBeInTheDocument();
    // Kaldırılan sınav modülüne atıf kalmadı.
    expect(within(confirmDialog).queryByText(/oturum|sınav/i)).not.toBeInTheDocument();
    expect(within(confirmDialog).queryByText(/soft delete/i)).not.toBeInTheDocument();
    await user.click(within(confirmDialog).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(okulApiMock.deleteStudent).toHaveBeenCalledWith(1));
  });
});

describe("KisilerPage — öğretmenler ve diğer personel sekmesi", () => {
  it("sekmeye geçince liste yüklenir: ad + üye türü + durum (unvan ve branş yok)", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("tab", { name: /Öğretmenler ve Diğer Personel/ }));

    expect(await screen.findByText("Mehmet Demirci")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Üye türü" })).toBeInTheDocument();
    expect(screen.getByText("Öğretmen")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Unvan|Branş/ })).toBeNull();
    expect(okulApiMock.listPersonnel).toHaveBeenCalledWith({
      search: "",
      limit: 25,
      offset: 0,
    });
  });

  // docs/sozluk.md: üye türü "öğretmen" / "diğer personel"; "personel" tek başına
  // yalnız e-Okul raporunun adında ("Personel Listesi raporu") geçer.
  it("ekleme diyaloğu üye türü sorar; unvan ve branş alanı yoktur", async () => {
    okulApiMock.createPersonnel.mockResolvedValue({ ...PERSONNEL, member_kind: "STAFF" });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: /Öğretmenler/ }));
    await user.click(await screen.findByRole("button", { name: "Kişi ekle" }));

    const dialog = await screen.findByRole("dialog", { name: "Yeni kişi" });
    expect(within(dialog).queryByLabelText("Unvan")).toBeNull();
    expect(within(dialog).queryByLabelText("Branş")).toBeNull();
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Mehmet");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Demirci");
    await user.selectOptions(within(dialog).getByLabelText("Üye türü"), "STAFF");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() =>
      expect(okulApiMock.createPersonnel).toHaveBeenCalledWith({
        first_name: "Mehmet",
        last_name: "Demirci",
        member_kind: "STAFF",
      }),
    );
    expect(await screen.findByText("Kayıt eklendi.")).toBeInTheDocument();
    expect(screen.queryByText(/Personel eklendi/)).not.toBeInTheDocument();
    // e-Okul raporunun ADI değişmez.
    expect(screen.getByText(/OOK01001R1 — Personel Listesi raporunu/)).toBeInTheDocument();
  });

  it("silme onayı başlıklıdır ve kalıcı olduğunu söyler", async () => {
    okulApiMock.deletePersonnel.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("tab", { name: /Öğretmenler/ }));
    await user.click(await screen.findByRole("button", { name: "Mehmet Demirci kaydını düzenle" }));

    const dialog = await screen.findByRole("dialog", { name: "Kişiyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));

    const onay = await screen.findByRole("dialog", { name: "Kişi sicilden silinsin mi?" });
    expect(within(onay).getByText(/kalıcı olarak silinir/)).toBeInTheDocument();
    expect(within(onay).queryByText(/gözetmen|görevlendirme/)).not.toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(okulApiMock.deletePersonnel).toHaveBeenCalledWith(5));
    expect(await screen.findByText("Kayıt silindi.")).toBeInTheDocument();
  });

  it("ayrıldı olarak işaretleme onaylı yapılır; kaydın silinmediği söylenir", async () => {
    okulApiMock.leavePersonnel.mockResolvedValue({
      ...PERSONNEL,
      is_active: false,
      left_at: "2026-09-22",
    });
    const user = userEvent.setup();
    renderPage("/kisiler?tab=personel");
    await user.click(await screen.findByRole("button", { name: "Mehmet Demirci kaydını düzenle" }));

    const dialog = await screen.findByRole("dialog", { name: "Kişiyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Ayrıldı olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "Kişi ayrıldı olarak işaretlensin mi?",
    });
    expect(within(onay).getByText(/Kaydı silinmez/)).toBeInTheDocument();
    expect(within(onay).queryByText(/hemen silinir/)).toBeNull();
    await user.click(within(onay).getByRole("button", { name: "Ayrıldı olarak işaretle" }));

    await waitFor(() => expect(okulApiMock.leavePersonnel).toHaveBeenCalledWith(5));
    expect(await screen.findByText("Kişi ayrıldı olarak işaretlendi.")).toBeInTheDocument();
  });

  it("ayrılmış kişide rozet görünür, ayrılış eylemi sunulmaz", async () => {
    okulApiMock.listPersonnel.mockResolvedValue(
      page([{ ...PERSONNEL, is_active: false, left_at: "2026-06-20" }]),
    );
    const user = userEvent.setup();
    renderPage("/kisiler?tab=personel");

    expect(await screen.findByText("Ayrıldı · 20.06.2026")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mehmet Demirci kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Kişiyi düzenle" });
    expect(
      within(dialog).queryByRole("button", { name: "Ayrıldı olarak işaretle" }),
    ).not.toBeInTheDocument();
    expect(within(dialog).getByText("Ayrıldı · 20.06.2026")).toBeInTheDocument();
  });
});

describe("KisilerPage — öğrenci ayrılışı ve parola uyarısı", () => {
  it("ayrıldı olarak işaretle: kayıt silinmez, onaydan sonra işaretlendiği bildirilir", async () => {
    okulApiMock.leaveStudent.mockResolvedValue({
      ...STUDENT,
      status: "LEFT",
      left_at: "2026-09-22",
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Ayrıldı olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "Öğrenci ayrıldı olarak işaretlensin mi?",
    });
    expect(within(onay).getByText(/Kaydı silinmez/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Ayrıldı olarak işaretle" }));

    await waitFor(() => expect(okulApiMock.leaveStudent).toHaveBeenCalledWith(1));
    expect(await screen.findByText("Öğrenci ayrıldı olarak işaretlendi.")).toBeInTheDocument();
    expect(screen.queryByText(/kaydı silindi/)).toBeNull();
  });

  it("ayrılış havuzundaki öğrencide “Ayrılış kararı bekliyor” rozeti görünür", async () => {
    okulApiMock.listStudents.mockResolvedValue(
      page([{ ...STUDENT, leave_candidate_since: "2026-09-22" }]),
    );
    renderPage();

    expect(await screen.findByText("Ayrılış kararı bekliyor")).toBeInTheDocument();
    expect(screen.getByText("Aktif")).toBeInTheDocument();
  });

  it("ayrılış onayından vazgeçilirse istek atılmaz", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Ayrıldı olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "Öğrenci ayrıldı olarak işaretlensin mi?",
    });
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));

    expect(okulApiMock.leaveStudent).not.toHaveBeenCalled();
  });

  it("ayrılış hatası diyalogda gösterilir", async () => {
    okulApiMock.leaveStudent.mockRejectedValue(
      new ApiError(400, "validation_error", "Bu kişi zaten ayrıldı olarak işaretli."),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Ayşe Yılmaz kaydını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Öğrenciyi düzenle" });
    await user.click(within(dialog).getByRole("button", { name: "Ayrıldı olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "Öğrenci ayrıldı olarak işaretlensin mi?",
    });
    await user.click(within(onay).getByRole("button", { name: "Ayrıldı olarak işaretle" }));

    expect(
      await within(dialog).findByText("Bu kişi zaten ayrıldı olarak işaretli."),
    ).toBeInTheDocument();
  });

  it("ayrılmış öğrencide “Ayrıldı · tarih” rozeti görünür", async () => {
    okulApiMock.listStudents.mockResolvedValue(
      page([{ ...STUDENT, status: "LEFT" as const, left_at: "2026-06-20" }]),
    );
    renderPage();

    expect(await screen.findByText("Ayrıldı · 20.06.2026")).toBeInTheDocument();
  });

  it("409 parola_gerekli: ileti okunaklı gösterilir ve kurulum sihirbazına bağlanır", async () => {
    okulApiMock.createStudent.mockRejectedValue(
      new ApiError(
        409,
        "parola_gerekli",
        "Kişi kaydı için önce yönetici parolasını kurun (Kurulum Sihirbazı'nın ilk adımı).",
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Öğrenci ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni öğrenci" });
    await user.type(within(dialog).getByLabelText(/^Ad \*$/), "Zeynep");
    await user.type(within(dialog).getByLabelText(/^Soyad \*$/), "Kaya");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    const bant = await within(dialog).findByRole("alert");
    expect(within(bant).getByText("Önce yönetici parolasını kurun")).toBeInTheDocument();
    expect(within(bant).getByText(/Kurulum Sihirbazı'nın ilk adımı/)).toBeInTheDocument();
    expect(within(bant).getByRole("link", { name: "Kurulum sihirbazını aç" })).toHaveAttribute(
      "href",
      "/kurulum",
    );
  });

  it("okul no araması tam numarayla yapıldığı söylenir", async () => {
    renderPage();
    await screen.findByText("Ayşe Yılmaz");
    expect(screen.getByText("Okul numarası tam yazılarak aranır.")).toBeInTheDocument();
  });
});

describe("KisilerPage — sekmeler", () => {
  it("sekmeler: sicil, Ayrılış Havuzu ve F6 üyelik sekmeleri (BEP ve fotoğraf yok)", async () => {
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      expect.stringContaining("Öğrenciler"),
      expect.stringContaining("Öğretmenler ve Diğer Personel"),
      expect.stringContaining("Ayrılış Havuzu"),
      expect.stringContaining("Üyeler"),
      expect.stringContaining("Üyelik İstek Listesi"),
      expect.stringContaining("Kart Basımı"),
    ]);
    expect(screen.queryByRole("tab", { name: /BEP/ })).toBeNull();
    expect(screen.queryByText(/fotoğraf/i)).toBeNull();
  });

  it("derin bağlantı: /kisiler?tab=havuz Ayrılış Havuzu sekmesini açar", async () => {
    okulApiMock.getLeavePool.mockResolvedValue({
      student_count: 0,
      personnel_count: 0,
      students: [],
      personnel: [],
    });
    renderPage("/kisiler?tab=havuz");

    expect(await screen.findByText("Ayrılış kararı bekleyen kişi yok")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Ayrılış Havuzu/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(okulApiMock.listStudents).not.toHaveBeenCalled();
  });

  it("derin bağlantı: /kisiler?tab=personel doğrudan Öğretmenler sekmesini açar", async () => {
    renderPage("/kisiler?tab=personel");

    expect(await screen.findByText("Mehmet Demirci")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Öğretmenler/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(okulApiMock.listStudents).not.toHaveBeenCalled();
  });

  it("geçersiz ya da kaldırılmış sekme parametresi sessizce Öğrenciler sekmesine düşer", async () => {
    renderPage("/kisiler?tab=bep");

    expect(await screen.findByText("Öğrenci Sicili")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Öğrenciler/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});

describe("KisilerPage — içe aktarma paneli", () => {
  it("yapıştırılan metin: önizleme raporu gösterilir, Aktar önizlemeden önce kapalıdır", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(PREVIEW_REPORT);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "ad\tsoyad");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));

    await waitFor(() =>
      expect(okulApiMock.previewStudentImport).toHaveBeenCalledWith(
        { text: "ad\tsoyad" },
        { fullList: false },
      ),
    );
    expect(await screen.findByText("Önizleme — hiçbir kayıt yazılmadı")).toBeInTheDocument();
    expect(screen.getByText("Uyarılar (1)")).toBeInTheDocument();
    expect(screen.getByText("Sınıf/şube çözülemedi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktar" })).toBeEnabled();
  });

  it("aktar: commit sonrası liste tazelenir ve already_imported uyarısı görünür", async () => {
    okulApiMock.previewStudentImport.mockResolvedValue(PREVIEW_REPORT);
    okulApiMock.commitStudentImport.mockResolvedValue({
      ...PREVIEW_REPORT,
      dry_run: false,
      already_imported: true,
      warnings: [],
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "ad\tsoyad");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    const callsBefore = okulApiMock.listStudents.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Aktar" }));

    await waitFor(() =>
      expect(okulApiMock.commitStudentImport).toHaveBeenCalledWith(
        { text: "ad\tsoyad" },
        { fullList: false },
      ),
    );
    expect(await screen.findByText(/daha önce aktarılmış/)).toBeInTheDocument();
    await waitFor(() =>
      expect(okulApiMock.listStudents.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });

  it("öğrenci aktarım yardımı cinsiyet ve pansiyon sütunlarının okunmadığını söyler", async () => {
    renderPage();
    await screen.findByText("Ayşe Yılmaz");
    expect(screen.getByText(/Cinsiyet ve pansiyon sütunları okunmaz\./)).toBeInTheDocument();
    expect(screen.queryByText(/ayrışma/)).toBeNull();
  });

  it("öğretmen ve diğer personel aktarımı: sonuç sayaçları gösterilir, zümre bandı yoktur", async () => {
    const rapor: PersonnelImportReport = {
      file_hash: "xyz",
      file_name: "",
      total_rows: 2,
      processed: 2,
      created_personnel: 2,
      updated_personnel: 0,
      unchanged_personnel: 0,
      reactivated_personnel: 0,
      pool_added_personnel: 0,
      pool_removed_personnel: 0,
      similar_pair_count: 0,
      already_imported: false,
      dry_run: true,
      pool_added: [],
      similar_pairs: [],
      warnings: [],
      skipped: [],
    };
    okulApiMock.previewPersonnelImport.mockResolvedValue(rapor);
    okulApiMock.commitPersonnelImport.mockResolvedValue({ ...rapor, dry_run: false });
    const user = userEvent.setup();
    renderPage("/kisiler?tab=personel");

    await user.type(await screen.findByLabelText("Ya da tabloyu yapıştırın"), "ad\tsoyad");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));
    await screen.findByText("Önizleme — hiçbir kayıt yazılmadı");

    await user.click(screen.getByRole("button", { name: "Aktar" }));
    expect(await screen.findByText("İçe aktarma sonucu")).toBeInTheDocument();
    await waitFor(() =>
      expect(okulApiMock.commitPersonnelImport).toHaveBeenCalledWith({ text: "ad\tsoyad" }),
    );
    expect(screen.queryByText(/zümre/i)).toBeNull();
    expect(screen.queryByRole("link", { name: /Zümreler/ })).toBeNull();
  });

  it("önizleme hatası: backend mesajı bantta görünür, Aktar kapalı kalır", async () => {
    okulApiMock.previewStudentImport.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Dosya (file) veya metin (text) alanlarından biri gerekli.",
      ),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.type(screen.getByLabelText("Ya da tabloyu yapıştırın"), "x");
    await user.click(screen.getByRole("button", { name: /Önizle/ }));

    expect(
      await screen.findByText("Dosya (file) veya metin (text) alanlarından biri gerekli."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aktar" })).toBeDisabled();
  });

  it("dosya seçimi kaldırılınca yapıştırma alanı yeniden etkinleşir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    const dosyaAlani = screen.getByLabelText(
      "Dosya (e-Okul .xls veya şablon .xlsx)",
    ) as HTMLInputElement;
    // e-Okul ihracı BÜYÜK harfli .XLS uzantısıyla iner — seçici onu da kabul etmeli.
    expect(dosyaAlani.accept).toContain(".xls");
    await user.upload(dosyaAlani, new File(["x"], "OOG01001R020_827.XLS"));
    expect(screen.getByLabelText("Ya da tabloyu yapıştırın")).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Dosyayı kaldır/ }));

    expect(screen.getByLabelText("Ya da tabloyu yapıştırın")).toBeEnabled();
    expect(dosyaAlani.files?.length ?? 0).toBe(0);
  });

  it("şablon indir: blob dosya olarak kaydedilir", async () => {
    const blob = new Blob(["x"]);
    okulApiMock.studentTemplate.mockResolvedValue(blob);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Ayşe Yılmaz");

    await user.click(screen.getByRole("button", { name: "Şablon indir" }));

    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, "sablon-ogrenci.xlsx"));
  });
});
