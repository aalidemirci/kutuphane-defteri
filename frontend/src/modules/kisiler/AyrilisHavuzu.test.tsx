// Ayrılış Havuzu (F1 eki 7): e-Okul aktarımı kimseyi ayırmaz; listede bulunmayanlar
// burada karar bekler. Öğrenci ve personel ayrı listelerde; tek tek ve toplu
// "Ayrıldı olarak işaretle" (onay diyaloğu, kayıt silinmez) ve "Aktif kalsın"
// (onaysız, havuzdan çıkar); yıl sonu için sınıf süzgeci; personelde "olası aynı kişi"
// ve onaylı "Birleştir"; bayat seçimde backend reddi. Tüm adlar uydurmadır (KVKK).

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { LeavePool } from "../okul/api";

const okulApiMock = vi.hoisted(() => ({
  getLeavePool: vi.fn(),
  resolveLeavePool: vi.fn(),
  mergePersonnel: vi.fn(),
}));

vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: okulApiMock };
});

import AyrilisHavuzu from "./AyrilisHavuzu";

const HAVUZ: LeavePool = {
  student_count: 3,
  personnel_count: 2,
  students: [
    {
      id: 1,
      full_name: "ALİ MEZUN",
      student_number: "301",
      class_label: "12/A",
      leave_candidate_since: "2026-06-20",
      run: { id: 5, file_name: "OOG01001R020.XLS", date: "2026-06-20" },
    },
    {
      id: 2,
      full_name: "VELİ MEZUN",
      student_number: "302",
      class_label: "12/A",
      leave_candidate_since: "2026-06-20",
      run: { id: 5, file_name: "OOG01001R020.XLS", date: "2026-06-20" },
    },
    {
      id: 3,
      full_name: "CAN NAKİL",
      student_number: "101",
      class_label: "9/B",
      leave_candidate_since: "2026-09-22",
      run: { id: 6, file_name: "", date: "2026-09-22" },
    },
  ],
  personnel: [
    {
      id: 11,
      full_name: "AYŞE KARA",
      member_kind: "TEACHER",
      leave_candidate_since: "2026-09-22",
      run: null,
      similar: [{ id: 21, full_name: "AYŞE BEYAZ" }],
    },
    {
      id: 12,
      full_name: "MEHMET DEMİR",
      member_kind: "STAFF",
      leave_candidate_since: "2026-09-22",
      run: null,
      similar: [],
    },
  ],
};

const BOS: LeavePool = { student_count: 0, personnel_count: 0, students: [], personnel: [] };

function kur(onDegisti = vi.fn()) {
  render(
    <MemoryRouter>
      <SnackbarProvider>
        <ConfirmProvider>
          <AyrilisHavuzu onDegisti={onDegisti} />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
  return onDegisti;
}

function ogrenciBolumu(): HTMLElement {
  return screen.getByRole("region", { name: /^Öğrenciler/ });
}

function personelBolumu(): HTMLElement {
  return screen.getByRole("region", { name: /^Öğretmenler ve Diğer Personel/ });
}

beforeEach(() => {
  okulApiMock.getLeavePool.mockResolvedValue(HAVUZ);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AyrilisHavuzu — liste", () => {
  it("öğrenci ve personel ayrı listelerde; giriş tarihi, aktarım ve sayılar görünür", async () => {
    kur();

    expect(await screen.findByRole("heading", { name: "Öğrenciler (3)" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Öğretmenler ve Diğer Personel (2)" }),
    ).toBeInTheDocument();
    const ogrenci = ogrenciBolumu();
    const satir = within(ogrenci).getByRole("row", { name: /ALİ MEZUN/ });
    expect(
      within(satir)
        .getAllByRole("cell")
        .slice(1)
        .map((c) => c.textContent),
    ).toEqual(["301", "ALİ MEZUN", "12/A", "20.06.2026", "OOG01001R020.XLS"]);
    expect(within(ogrenci).getByText("Yapıştırılan liste")).toBeInTheDocument();
    expect(within(personelBolumu()).getByText("Diğer personel")).toBeInTheDocument();
    expect(screen.getByText(/kimseyi ayırmaz ve kimsenin kaydını silmez/)).toBeInTheDocument();
  });

  it("havuz boşsa boş durum gösterilir", async () => {
    okulApiMock.getLeavePool.mockResolvedValue(BOS);
    kur();

    expect(await screen.findByText("Ayrılış kararı bekleyen kişi yok")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ayrıldı olarak işaretle" })).toBeNull();
  });

  it("yükleme hatası bantta gösterilir", async () => {
    okulApiMock.getLeavePool.mockRejectedValue(
      new ApiError(403, "kip_yetkisiz", "Bu işlem görevli kipinde yapılamaz."),
    );
    kur();

    expect(await screen.findByText("Bu işlem görevli kipinde yapılamaz.")).toBeInTheDocument();
  });
});

describe("AyrilisHavuzu — karar", () => {
  it("seçim yokken eylemler kapalıdır", async () => {
    kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });

    const bolum = ogrenciBolumu();
    expect(within(bolum).getByText("Karar vermek için öğrenci seçin.")).toBeInTheDocument();
    expect(within(bolum).getByRole("button", { name: "Ayrıldı olarak işaretle" })).toBeDisabled();
    expect(within(bolum).getByRole("button", { name: "Aktif kalsın" })).toBeDisabled();
  });

  it("yıl sonu: sınıf süzgeciyle mezunlar toplu seçilir, onayla ayrılır (kayıt silinmez)", async () => {
    okulApiMock.resolveLeavePool.mockResolvedValue({
      students_left: 2,
      students_kept: 0,
      personnel_left: 0,
      personnel_kept: 0,
      student_count: 1,
      personnel_count: 2,
    });
    const user = userEvent.setup();
    const onDegisti = kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });
    const bolum = ogrenciBolumu();

    await user.selectOptions(within(bolum).getByLabelText("Sınıf"), "12/A");
    expect(within(bolum).queryByText("CAN NAKİL")).toBeNull();
    await user.click(
      within(bolum).getByRole("checkbox", { name: "Görünen öğrencilerin tümünü seç" }),
    );
    expect(within(bolum).getByText("2 öğrenci seçili.")).toBeInTheDocument();
    await user.click(within(bolum).getByRole("button", { name: "Ayrıldı olarak işaretle" }));

    const onay = await screen.findByRole("dialog", {
      name: "2 öğrenci ayrıldı olarak işaretlensin mi?",
    });
    expect(within(onay).getByText(/Kayıtları silinmez/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Ayrıldı olarak işaretle" }));

    await waitFor(() =>
      expect(okulApiMock.resolveLeavePool).toHaveBeenCalledWith({
        students: { leave: [1, 2] },
      }),
    );
    expect(await screen.findByText("2 öğrenci ayrıldı olarak işaretlendi.")).toBeInTheDocument();
    expect(onDegisti).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(okulApiMock.getLeavePool).toHaveBeenCalledTimes(2));
  });

  it("karardan sonra listeden düşen sınıf süzgeci sıfırlanır (kalanlar görünür kalır)", async () => {
    okulApiMock.resolveLeavePool.mockResolvedValue({
      students_left: 2,
      students_kept: 0,
      personnel_left: 0,
      personnel_kept: 0,
      student_count: 1,
      personnel_count: 2,
    });
    const kalan: LeavePool = {
      ...HAVUZ,
      student_count: 1,
      students: HAVUZ.students.filter((o) => o.class_label === "9/B"),
    };
    okulApiMock.getLeavePool.mockResolvedValueOnce(HAVUZ).mockResolvedValue(kalan);
    const user = userEvent.setup();
    kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });

    await user.selectOptions(within(ogrenciBolumu()).getByLabelText("Sınıf"), "12/A");
    await user.click(
      within(ogrenciBolumu()).getByRole("checkbox", { name: "Görünen öğrencilerin tümünü seç" }),
    );
    await user.click(
      within(ogrenciBolumu()).getByRole("button", { name: "Ayrıldı olarak işaretle" }),
    );
    await user.click(
      within(
        await screen.findByRole("dialog", { name: "2 öğrenci ayrıldı olarak işaretlensin mi?" }),
      ).getByRole("button", { name: "Ayrıldı olarak işaretle" }),
    );

    // 12/A seçeneği listeden düştü: süzgeç bayat kalsaydı tablo boş görünür,
    // seçici ise eşleşen seçenek bulamadığı için "Tümü" yazardı.
    expect(await screen.findByRole("heading", { name: "Öğrenciler (1)" })).toBeInTheDocument();
    const bolum = ogrenciBolumu();
    await waitFor(() => expect(within(bolum).getByLabelText("Sınıf")).toHaveValue(""));
    expect(within(bolum).getByText("CAN NAKİL")).toBeInTheDocument();
  });

  it("ayrılış onayından vazgeçilirse istek atılmaz", async () => {
    const user = userEvent.setup();
    kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });
    const bolum = ogrenciBolumu();

    await user.click(within(bolum).getByRole("checkbox", { name: "CAN NAKİL seç" }));
    await user.click(within(bolum).getByRole("button", { name: "Ayrıldı olarak işaretle" }));
    await user.click(
      within(
        await screen.findByRole("dialog", { name: "1 öğrenci ayrıldı olarak işaretlensin mi?" }),
      ).getByRole("button", { name: "Vazgeç" }),
    );

    expect(okulApiMock.resolveLeavePool).not.toHaveBeenCalled();
  });

  it("tek kişi “Aktif kalsın”: onaysız, yalnız havuzdan çıkar", async () => {
    okulApiMock.resolveLeavePool.mockResolvedValue({
      students_left: 0,
      students_kept: 0,
      personnel_left: 0,
      personnel_kept: 1,
      student_count: 3,
      personnel_count: 1,
    });
    const user = userEvent.setup();
    kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });
    const bolum = personelBolumu();

    await user.click(within(bolum).getByRole("checkbox", { name: "MEHMET DEMİR seç" }));
    await user.click(within(bolum).getByRole("button", { name: "Aktif kalsın" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() =>
      expect(okulApiMock.resolveLeavePool).toHaveBeenCalledWith({ personnel: { keep: [12] } }),
    );
    expect(
      await screen.findByText("1 kişi aktif kalacak; havuzdan çıkarıldı."),
    ).toBeInTheDocument();
  });

  it("bayat seçim: backend reddi bantta gösterilir, liste yenilenir", async () => {
    okulApiMock.resolveLeavePool.mockRejectedValue(
      new ApiError(
        400,
        "validation_error",
        "Seçilen kişilerden bazıları artık ayrılış havuzunda değil. Listeyi yenileyip yeniden seçin; hiçbir karar uygulanmadı.",
      ),
    );
    const user = userEvent.setup();
    kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });
    const bolum = ogrenciBolumu();

    await user.click(within(bolum).getByRole("checkbox", { name: "ALİ MEZUN seç" }));
    await user.click(within(bolum).getByRole("button", { name: "Aktif kalsın" }));

    expect(await screen.findByText(/artık ayrılış havuzunda değil/)).toBeInTheDocument();
    await waitFor(() => expect(okulApiMock.getLeavePool).toHaveBeenCalledTimes(2));
  });
});

describe("AyrilisHavuzu — olası aynı kişi", () => {
  it("aday gösterilir; “Birleştir” onaylı çalışır (havuzdaki kayıt kaynak)", async () => {
    okulApiMock.mergePersonnel.mockResolvedValue({});
    const user = userEvent.setup();
    const onDegisti = kur();
    await screen.findByRole("heading", { name: "Öğrenciler (3)" });

    expect(screen.getByText(/Öyleyse ayrıldı diye işaretlemeyin/)).toBeInTheDocument();
    await user.click(
      within(personelBolumu()).getByRole("button", {
        name: "AYŞE KARA kaydını AYŞE BEYAZ kaydıyla birleştir",
      }),
    );
    const onay = await screen.findByRole("dialog", { name: "Kayıtlar birleştirilsin mi?" });
    expect(within(onay).getByText(/eski kayıt silinir/)).toBeInTheDocument();
    await user.click(within(onay).getByRole("button", { name: "Birleştir" }));

    await waitFor(() => expect(okulApiMock.mergePersonnel).toHaveBeenCalledWith(11, 21));
    expect(await screen.findByText("Kayıtlar birleştirildi.")).toBeInTheDocument();
    expect(onDegisti).toHaveBeenCalledTimes(1);
  });
});
