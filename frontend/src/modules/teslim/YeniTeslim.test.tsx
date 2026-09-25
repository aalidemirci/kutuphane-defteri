// Yeni Teslim (F7, U11, §9-11): teslim ödünç DEĞİLDİR — sayı sınırı sorulmaz; liste
// okutmayla kurulur (ön denetim, tekrar okutma bir kez sayılır); teslim onaydan geçer
// (başlık soru); TEK işlemdir — reddedilen kitaplar gerekçeleriyle listelenir;
// teslimden sonra Teslim listesi (E15) belge no'lu dosya adıyla indirilir. Bütün adlar
// uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { teslimSatiri } from "../../test/teslimVerileri";
import type { TeslimDenetimi, TeslimSonucu } from "./api";

const teslim = vi.hoisted(() => ({
  denetle: vi.fn(),
  teslimEt: vi.fn(),
  teslimListesiPdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslim } };
});
const okul = vi.hoisted(() => ({
  listSchoolYears: vi.fn(),
  listClassSections: vi.fn(),
  listPersonnel: vi.fn(),
}));
vi.mock("../okul/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../okul/api")>();
  return { ...actual, okulApi: { ...actual.okulApi, ...okul } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import { ODAK_UYARISI } from "../../ui/BarcodeInput";
import YeniTeslim, { LISTEYE_GIRMEYENLER, TESLIM_KUTUSU, ZATEN_LISTEDE } from "./YeniTeslim";

function denetim(barkod: string, ad: string): TeslimDenetimi {
  return {
    result: "deliverable",
    kind: "COPY",
    message: "Teslim edilebilir.",
    copy: {
      barcode: barkod,
      barcode_display: `${barkod.slice(0, 4)}-${barkod.slice(4)}`,
      work_title: ad,
    },
  };
}

function sonuc(ek: Partial<TeslimSonucu> = {}): TeslimSonucu {
  return {
    document_no: "2026/4",
    delivered_on: "2026-09-25",
    expected_return: "2027-06-18",
    recipient_kind: "SECTION",
    recipient_kind_display: "Sınıf kitaplığı",
    recipient_label: "3/A",
    count: 2,
    deliveries: [teslimSatiri({ id: 1 }), teslimSatiri({ id: 2 })],
    ...ek,
  };
}

function ciz(onTeslimEdildi = vi.fn()) {
  render(
    <SnackbarProvider>
      <ConfirmProvider>
        <YeniTeslim onTeslimEdildi={onTeslimEdildi} />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
  return onTeslimEdildi;
}

beforeEach(() => {
  vi.resetAllMocks();
  okul.listSchoolYears.mockResolvedValue([
    { id: 1, name: "2025-2026", is_active: false },
    { id: 2, name: "2026-2027", is_active: true },
  ]);
  okul.listClassSections.mockResolvedValue([
    {
      id: 7,
      school_year: 2,
      school_year_name: "2026-2027",
      class_level: 3,
      class_section: "A",
      class_label: "3/A",
    },
  ]);
  okul.listPersonnel.mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: [
      {
        id: 21,
        first_name: "Deneme",
        last_name: "Öğretmen",
        full_name: "Deneme Öğretmen",
        member_kind: "TEACHER",
        is_active: true,
        left_at: null,
        leave_candidate_since: null,
      },
      {
        id: 22,
        first_name: "Deneme",
        last_name: "Memur",
        full_name: "Deneme Memur",
        member_kind: "STAFF",
        is_active: true,
        left_at: null,
        leave_candidate_since: null,
      },
    ],
  });
  teslim.denetle.mockImplementation(async (kod: string) =>
    denetim(kod, kod.endsWith("1") ? "Birinci Kitap" : "İkinci Kitap"),
  );
  teslim.teslimEt.mockResolvedValue(sonuc());
  teslim.teslimListesiPdf.mockResolvedValue(new Blob(["%PDF"]));
});

async function okut(user: ReturnType<typeof userEvent.setup>, kod: string) {
  await user.type(screen.getByLabelText(TESLIM_KUTUSU), `${kod}{Enter}`);
}

describe("YeniTeslim", () => {
  it("şubeler yalnız etkin ders yılından gelir; sayı sınırı dili yoktur", async () => {
    ciz();
    await waitFor(() => expect(okul.listClassSections).toHaveBeenCalledWith(2));
    expect(await screen.findByRole("option", { name: "3/A" })).toBeInTheDocument();
    expect(screen.getByText(/sayı sınırı yoktur/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/emanet|zimmet|kalan hak/i);
  });

  it("okutulan kitaplar listeye girer; tekrar okutma ve reddedilen kitap listeye girmez", async () => {
    const user = userEvent.setup();
    ciz();
    teslim.denetle.mockImplementationOnce(async (kod: string) => denetim(kod, "Birinci Kitap"));
    await okut(user, "2026000001");
    await okut(user, "2026000002");
    await okut(user, "2026000001");
    // Sunucunun gerçek yanıt biçimi: reddedilen nüshanın özeti de gelir.
    teslim.denetle.mockResolvedValueOnce({
      result: "rejected",
      kind: "COPY",
      message: "Ödünçte — teslim edilemez.",
      copy: { barcode: "2026000003", barcode_display: "2026-000003", work_title: "Üçüncü Kitap" },
    });
    await okut(user, "2026000003");

    const liste = await screen.findByRole("list", { name: "Teslim listesi" });
    await waitFor(() => expect(within(liste).getAllByRole("listitem")).toHaveLength(2));
    expect(screen.getByText("Listede 2 kitap")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "2026-000003 — Üçüncü Kitap: Ödünçte — teslim edilemez.",
    );
    expect(teslim.denetle).toHaveBeenCalledTimes(4);

    // Tekrar okutmanın iletisi (sonraki okutmadan önce görünür).
    await okut(user, "2026000002");
    expect(await screen.findByText(`2026-000002: ${ZATEN_LISTEDE}`)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "2026-000001 listeden çıkar" }));
    expect(screen.getByText("Listede 1 kitap")).toBeInTheDocument();
  });

  it("reddedilen kitap sonraki başarılı okutmada silinmez; listeye girince çıkar", async () => {
    const user = userEvent.setup();
    ciz();
    const red = {
      result: "rejected" as const,
      kind: "COPY" as const,
      message: "Ödünçte — teslim edilemez.",
      copy: { barcode: "2026000005", barcode_display: "2026-000005", work_title: "Beşinci Kitap" },
    };
    teslim.denetle.mockResolvedValueOnce(red);
    // Okuyucu kuyruğu: red ve ardından başarılı okutmalar arka arkaya.
    await okut(user, "2026000005");
    await okut(user, "2026000001");
    await okut(user, "2026000002");

    await screen.findByText("Listede 2 kitap");
    const girmeyen = screen.getByRole("list", { name: LISTEYE_GIRMEYENLER });
    expect(within(girmeyen).getAllByRole("listitem")).toHaveLength(1);
    expect(girmeyen).toHaveTextContent("2026-000005 — Beşinci Kitap: Ödünçte — teslim edilemez.");
    // Son okutma başarılıydı: geçici bant boşaldı ama kalıcı liste duruyor.
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    // Aynı kitap iade alınıp yeniden okutulursa listeye girer ve kalıcı listeden çıkar.
    teslim.denetle.mockResolvedValueOnce({
      ...red,
      result: "deliverable",
      message: "Teslim edilebilir.",
    });
    await okut(user, "2026000005");
    await screen.findByText("Listede 3 kitap");
    expect(screen.queryByRole("list", { name: LISTEYE_GIRMEYENLER })).not.toBeInTheDocument();
  });

  it("okutma kutusu odakta değilken uyarı çıkar; öğretmen seçilince odak kutuya döner", async () => {
    const user = userEvent.setup();
    ciz();
    await screen.findByRole("option", { name: "3/A" });
    expect(screen.getByLabelText(TESLIM_KUTUSU)).toHaveFocus();
    expect(screen.queryByText(ODAK_UYARISI)).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/Şube/), "7");
    expect(screen.getByText(ODAK_UYARISI)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kutuya dön" }));
    expect(screen.getByLabelText(TESLIM_KUTUSU)).toHaveFocus();

    await user.click(screen.getByRole("radio", { name: "Öğretmen" }));
    await user.type(screen.getByRole("combobox"), "Deneme");
    await user.click(await screen.findByRole("option", { name: /Deneme Öğretmen/ }));
    expect(screen.getByLabelText(TESLIM_KUTUSU)).toHaveFocus();
    expect(screen.queryByText(ODAK_UYARISI)).not.toBeInTheDocument();
  });

  it("şube seçilmeden teslim edilmez; seçilince onay sorusu ve TEK istek", async () => {
    const user = userEvent.setup();
    const bildirim = ciz();
    await okut(user, "2026000001");
    await okut(user, "2026000002");
    await screen.findByText("Listede 2 kitap");

    await user.click(screen.getByRole("button", { name: "Teslim et" }));
    expect(await screen.findByText("Şube seçin.")).toBeInTheDocument();
    expect(teslim.teslimEt).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText(/Şube/), "7");
    await user.type(screen.getByLabelText("Belge no (isteğe bağlı)"), "2026/4");
    await user.click(screen.getByRole("button", { name: "Teslim et" }));
    const onay = await screen.findByRole("dialog", {
      name: "2 kitap 3/A sınıf kitaplığına teslim edilsin mi?",
    });
    await user.click(within(onay).getByRole("button", { name: "Teslim et" }));

    await waitFor(() => expect(teslim.teslimEt).toHaveBeenCalledTimes(1));
    expect(teslim.teslimEt).toHaveBeenCalledWith(
      expect.objectContaining({
        section_id: 7,
        barcodes: ["2026000001", "2026000002"],
        document_no: "2026/4",
        expected_return: null,
      }),
    );
    expect(teslim.teslimEt.mock.calls[0][0]).not.toHaveProperty("personnel_id");
    // Sonuç kartı ve snackbar aynı cümleyi taşır.
    expect(await screen.findAllByText("2 kitap teslim edildi.")).toHaveLength(2);
    expect(screen.getByText(/belge no 2026\/4/)).toBeInTheDocument();
    expect(bildirim).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(saveBlobMock).toHaveBeenCalled());
    expect(teslim.teslimListesiPdf).toHaveBeenCalledWith("2026/4");
    expect(saveBlobMock.mock.calls[0][1]).toBe("Teslim-listesi_2026-4_25.09.2026.pdf");

    await user.click(screen.getByRole("button", { name: "Yeni teslim" }));
    expect(screen.getByText("Listede 0 kitap")).toBeInTheDocument();
  });

  it("onaydan vazgeçilirse istek gitmez", async () => {
    const user = userEvent.setup();
    ciz();
    await okut(user, "2026000001");
    await screen.findByText("Listede 1 kitap");
    await user.selectOptions(await screen.findByLabelText(/Şube/), "7");
    await user.click(screen.getByRole("button", { name: "Teslim et" }));
    const onay = await screen.findByRole("dialog");
    await user.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(teslim.teslimEt).not.toHaveBeenCalled();
    expect(screen.getByText("Listede 1 kitap")).toBeInTheDocument();
  });

  it("listedeki kitap bu arada teslim edilemez olduysa gerekçeler listelenir, hiçbir teslim yapılmaz", async () => {
    const user = userEvent.setup();
    ciz();
    teslim.teslimEt.mockRejectedValueOnce(
      new ApiError(400, "validation_error", "2026-000001: Ödünçte — teslim edilemez.", {
        barcodes: ["2026-000001: Ödünçte — teslim edilemez."],
      }),
    );
    await okut(user, "2026000001");
    await screen.findByText("Listede 1 kitap");
    await user.selectOptions(await screen.findByLabelText(/Şube/), "7");
    await user.click(screen.getByRole("button", { name: "Teslim et" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Teslim et" }),
    );

    const retler = await screen.findByRole("list", { name: "Teslim edilemeyen kitaplar" });
    expect(retler).toHaveTextContent("2026-000001: Ödünçte — teslim edilemez.");
    expect(
      screen.getByText("Listedeki bazı kitaplar teslim edilemiyor; hiçbir teslim yapılmadı."),
    ).toBeInTheDocument();
    // Liste korunur: kullanıcı kitabı çıkarıp yeniden dener.
    expect(screen.getByText("Listede 1 kitap")).toBeInTheDocument();
  });

  it("öğretmene teslim: diğer personel seçilemez; gövde personnel_id taşır", async () => {
    const user = userEvent.setup();
    teslim.teslimEt.mockResolvedValueOnce(
      sonuc({
        recipient_kind: "TEACHER",
        recipient_kind_display: "Öğretmen",
        recipient_label: "Deneme Öğretmen",
        count: 1,
      }),
    );
    ciz();
    await user.click(screen.getByRole("radio", { name: "Öğretmen" }));
    await user.type(screen.getByRole("combobox"), "Deneme");
    const memur = await screen.findByRole("option", { name: /Deneme Memur/ });
    expect(memur).toHaveAttribute("aria-disabled", "true");
    expect(memur).toHaveTextContent("diğer personele teslim yapılmaz");
    await user.click(screen.getByRole("option", { name: /Deneme Öğretmen/ }));
    expect(okul.listPersonnel).toHaveBeenCalledWith({
      search: "Deneme",
      onlyActive: true,
      limit: 20,
    });

    await okut(user, "2026000001");
    await screen.findByText("Listede 1 kitap");
    await user.click(screen.getByRole("button", { name: "Teslim et" }));
    await user.click(
      within(
        await screen.findByRole("dialog", {
          name: "1 kitap Deneme Öğretmen adlı öğretmene teslim edilsin mi?",
        }),
      ).getByRole("button", { name: "Teslim et" }),
    );
    await waitFor(() =>
      expect(teslim.teslimEt).toHaveBeenCalledWith(expect.objectContaining({ personnel_id: 21 })),
    );
    expect(teslim.teslimEt.mock.calls[0][0]).not.toHaveProperty("section_id");
  });

  it("listeyi boşaltmak onay ister", async () => {
    const user = userEvent.setup();
    ciz();
    await okut(user, "2026000001");
    await screen.findByText("Listede 1 kitap");
    await user.click(screen.getByRole("button", { name: "Listeyi boşalt" }));
    const onay = await screen.findByRole("dialog", { name: "Liste boşaltılsın mı?" });
    await user.click(within(onay).getByRole("button", { name: "Boşalt" }));
    expect(screen.getByText("Listede 0 kitap")).toBeInTheDocument();
  });
});
