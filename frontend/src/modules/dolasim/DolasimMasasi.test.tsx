// Dolaşım masası (tasarım §7.3 durum tablosu, §4.4) — HER SATIR AYRI TEST:
//
//   Boş | kart                → üye bağlamı: ad + kalan hak (görevlide sınıf yok)
//   Boş | kitap               → iade ucu (açık ödünçteyse iade, değilse durum iletisi)
//   ÜYE | kitap               → ödünç ucu, kartla; görevli istisna/kartsız alanı GÖNDERMEZ
//   ÜYE | kitap başka üyede   → "Bu kitap başka bir üyede. Önce iade alınsın mı?"
//   ÜYE | 60 sn · Bitti · başka kart → bağlam kapanır
//   Her durum | iptal kart    → sunucunun iletisi; bağlam kapanır
//   Her durum | tanınmayan/ISBN → sunucunun iletisi (iade ucundan)
//
// Ayrıca: art arda 20 okutma sırayla işlenir (kod kapısı), kart + kitaplar hızlı
// okutulunca kitaplar kartın bağlamıyla verilir; GA-7 (yönetici parolası); yönetici
// kipinde gerekçeli istisna ve kartsız ödünç. Bütün kişi verileri uydurmadır.

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import type { IadeSonucu, KartSonucu, OduncSonucu } from "./api";

const masa = vi.hoisted(() => ({
  kartOku: vi.fn(),
  uyeAc: vi.fn(),
  oduncVer: vi.fn(),
  iadeAl: vi.fn(),
  nushaDurumu: vi.fn(),
  kartKilidiniAc: vi.fn(),
  uyeAra: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masa } };
});

// F7: teslimden geri alma ve kayıp bildirimi kendi uçlarına gider.
const teslimKapi = vi.hoisted(() => ({ geriAl: vi.fn() }));
vi.mock("../teslim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../teslim/api")>();
  return { ...actual, teslimApi: { ...actual.teslimApi, ...teslimKapi } };
});
const kayipKapi = vi.hoisted(() => ({ ac: vi.fn() }));
vi.mock("../kayip/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kayip/api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayipKapi } };
});

import DolasimMasasi, {
  BAGLAM_KAPANDI,
  BAGLAM_SURESI_MS,
  BAGLAM_ZAMAN_ASIMI,
  BASKA_UYEDE_SORUSU,
  DURUM_SORGUSU_KAPANDI,
  IADE_ONERISI,
  ISTEM_BAGLAM_DEGISTI,
  KAYIP_BILDIRILDI,
  OKUTMA_KUTUSU,
  SINIF_KITAPLIGINDA,
  TESLIMDEN_GERI_AL,
  TESLIM_GERI_ALMA_ONERISI,
} from "./DolasimMasasi";
import { KART_KILIDI_BASLIGI } from "./MasaDiyaloglari";

const KART = "94718263";
const OBUR_KART = "95550005";
const KITAP = "2026000123";

function kartSonucu(ek: Partial<KartSonucu["member"]> = {}): KartSonucu {
  return {
    state: "FOUND",
    message: "Kitabın kütüphane etiketini okutun.",
    member: { full_name: "Deneme Okur", remaining_quota: 3, ...ek },
  };
}

function oduncSonucu(ek: Partial<OduncSonucu> = {}): OduncSonucu {
  return {
    message: "Ödünç verildi.",
    copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
    due_date: "2026-10-09",
    warnings: [],
    member: { full_name: "Deneme Okur", remaining_quota: 2 },
    ...ek,
  };
}

function iadeSonucu(ek: Partial<IadeSonucu> = {}): IadeSonucu {
  return {
    result: "returned",
    kind: "COPY",
    message: "İade alındı.",
    copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
    ...ek,
  };
}

function ekranaBas(gorevli = true) {
  render(<DolasimMasasi gorevli={gorevli} />);
  return screen.getByLabelText(OKUTMA_KUTUSU);
}

beforeEach(() => {
  vi.resetAllMocks();
  masa.kartOku.mockResolvedValue(kartSonucu());
  masa.oduncVer.mockResolvedValue(oduncSonucu());
  masa.iadeAl.mockResolvedValue(iadeSonucu());
  masa.nushaDurumu.mockResolvedValue({
    kind: "COPY",
    message: "Ödünçte.",
    copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const uyeBaglami = () => screen.queryByRole("region", { name: "Üye bağlamı" });

describe("Boş | kart", () => {
  it("üye bağlamı açılır: ad ve kalan hak; görevlide sınıf gösterilmez", async () => {
    const user = userEvent.setup();
    const kutu = ekranaBas();
    expect(kutu).toHaveFocus();

    await user.type(kutu, `${KART}{Enter}`);

    const baglam = await screen.findByRole("region", { name: "Üye bağlamı" });
    expect(within(baglam).getByText("Deneme Okur")).toBeInTheDocument();
    expect(within(baglam).getByText("Kalan ödünç hakkı: 3")).toBeInTheDocument();
    expect(masa.kartOku).toHaveBeenCalledWith(KART);
    expect(masa.iadeAl).not.toHaveBeenCalled();
    // Görevli ekranındaki son işlemler listesinde üye adı yazmaz.
    expect(screen.getByRole("status")).not.toHaveTextContent("Deneme Okur");
  });

  it("yönetici kipinde sınıf, üye türü ve açık ödünçler görünür", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockResolvedValue(
      kartSonucu({
        membership_id: 7,
        member_type_display: "öğrenci",
        class_label: "9/A",
        open_loan_count: 1,
        open_loans: [
          {
            id: 1,
            barcode: "2026000001",
            barcode_display: "2026-000001",
            work_title: "Geciken Eser",
            loaned_at: "2026-09-01T10:00:00+03:00",
            due_date: "2026-09-16",
            overdue_days: 8,
            cardless: false,
            has_override: false,
          },
        ],
      }),
    );
    const kutu = ekranaBas(false);

    await user.type(kutu, `${KART}{Enter}`);

    const baglam = await screen.findByRole("region", { name: "Üye bağlamı" });
    expect(within(baglam).getByText(/öğrenci · 9\/A/)).toBeInTheDocument();
    expect(within(baglam).getByText("Geciken Eser")).toBeInTheDocument();
    expect(within(baglam).getByText(/8 gün gecikti/)).toBeInTheDocument();
  });
});

describe("Boş | kitap", () => {
  it("kitap okutulunca iade ucu çağrılır; iade iletisi görünür", async () => {
    const user = userEvent.setup();
    const kutu = ekranaBas();

    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("İade alındı.")).toBeInTheDocument();
    expect(masa.iadeAl).toHaveBeenCalledWith(KITAP);
    expect(masa.oduncVer).not.toHaveBeenCalled();
  });

  it("ödünçte olmayan kitapta sunucunun durum iletisi gösterilir", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue(iadeSonucu({ result: "not_on_loan", message: "Onarımda." }));
    const kutu = ekranaBas();

    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("Onarımda.")).toBeInTheDocument();
  });
});

describe("ÜYE | kitap", () => {
  it("kitap kartla ödünç verilir; görevli istisna ve kartsız alanlarını GÖNDERMEZ", async () => {
    const user = userEvent.setup();
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("Ödünç verildi.")).toBeInTheDocument();
    expect(masa.oduncVer).toHaveBeenCalledWith({ barcode: KITAP, card_no: KART });
    expect(screen.getByText("Kalan ödünç hakkı: 2")).toBeInTheDocument();
    expect(screen.getByText(/İade tarihi 09\.10\.2026/)).toBeInTheDocument();
    expect(masa.iadeAl).not.toHaveBeenCalled();
  });

  it("kişisel olmayan ret iletisi gösterilir, bağlam açık kalır", async () => {
    const user = userEvent.setup();
    masa.oduncVer.mockRejectedValue(
      new ApiError(400, "sinir_dolu", "Ödünç sınırı dolu (en çok 3 kitap)."),
    );
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("Ödünç sınırı dolu (en çok 3 kitap).")).toBeInTheDocument();
    expect(uyeBaglami()).not.toBeNull();
  });

  it("görevlide gecikme reddi yalnız yönlendirme iletisidir; istisna diyaloğu açılmaz", async () => {
    const user = userEvent.setup();
    masa.oduncVer.mockRejectedValue(
      new ApiError(
        400,
        "gecikme_engeli",
        "Ödünç verilemiyor — kütüphane yöneticisine yönlendirin.",
      ),
    );
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(
      await screen.findByText("Ödünç verilemiyor — kütüphane yöneticisine yönlendirin."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("ÜYE | kitap başka üyede", () => {
  it("“Önce iade alınsın mı?” — onaylanınca iade, ardından bu üyeye ödünç", async () => {
    const user = userEvent.setup();
    masa.oduncVer
      .mockRejectedValueOnce(new ApiError(400, "nusha_baska_uyede", "Bu kitap başka bir üyede."))
      .mockResolvedValueOnce(oduncSonucu());
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);
    expect(await screen.findByText(BASKA_UYEDE_SORUSU)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "İade al ve ödünç ver" }));

    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(2));
    expect(masa.iadeAl).toHaveBeenCalledWith(KITAP);
    expect(masa.oduncVer.mock.calls[1][0]).toEqual({ barcode: KITAP, card_no: KART });
    expect(await screen.findByText("Ödünç verildi.")).toBeInTheDocument();
  });

  it("“Vazgeç” hiçbir şey yazmaz", async () => {
    const user = userEvent.setup();
    masa.oduncVer.mockRejectedValue(
      new ApiError(400, "nusha_baska_uyede", "Bu kitap başka bir üyede."),
    );
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);

    await user.click(await screen.findByRole("button", { name: "Vazgeç" }));

    expect(masa.iadeAl).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "İade al ve ödünç ver" })).toBeNull();
  });
});

describe("ÜYE | 60 sn · Bitti · başka kart", () => {
  it("60 saniye işlem yapılmazsa bağlam kapanır; işlem süreyi tazeler", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });

    await act(async () => vi.advanceTimersByTime(BAGLAM_SURESI_MS - 5_000));
    await user.type(kutu, `${KITAP}{Enter}`);
    await screen.findByText("Ödünç verildi.");
    await act(async () => vi.advanceTimersByTime(BAGLAM_SURESI_MS - 5_000));
    expect(uyeBaglami()).not.toBeNull();

    await act(async () => vi.advanceTimersByTime(10_000));
    expect(uyeBaglami()).toBeNull();
    expect(screen.getByText(BAGLAM_ZAMAN_ASIMI)).toBeInTheDocument();
  });

  it("“Bitti” bağlamı kapatır; sonraki kitap iade ucuna gider", async () => {
    const user = userEvent.setup();
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });

    await user.click(screen.getByRole("button", { name: "Bitti" }));

    expect(uyeBaglami()).toBeNull();
    expect(screen.getByText(BAGLAM_KAPANDI)).toBeInTheDocument();
    expect(kutu).toHaveFocus();
    await user.type(kutu, `${KITAP}{Enter}`);
    await waitFor(() => expect(masa.iadeAl).toHaveBeenCalledWith(KITAP));
    expect(masa.oduncVer).not.toHaveBeenCalled();
  });

  it("başka kart okutulunca bağlam yeni üyeye geçer", async () => {
    const user = userEvent.setup();
    masa.kartOku
      .mockResolvedValueOnce(kartSonucu())
      .mockResolvedValueOnce(kartSonucu({ full_name: "Öteki Okur", remaining_quota: 5 }));
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByText("Deneme Okur");
    await user.type(kutu, `${OBUR_KART}{Enter}`);

    expect(await screen.findByText("Öteki Okur")).toBeInTheDocument();
    expect(screen.queryByText("Deneme Okur")).toBeNull();
    await user.type(kutu, `${KITAP}{Enter}`);
    await waitFor(() =>
      expect(masa.oduncVer).toHaveBeenCalledWith({ barcode: KITAP, card_no: OBUR_KART }),
    );
  });
});

describe("Her durum | iptal kart · tanınmayan · ISBN", () => {
  it("iptal edilmiş kart iletisi gösterilir ve açık bağlam kapanır", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockResolvedValueOnce(kartSonucu()).mockResolvedValueOnce({
      state: "REVOKED",
      message: "İptal edilmiş kart — kütüphane yöneticisine yönlendirin.",
      member: null,
    });
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${OBUR_KART}{Enter}`);

    expect(
      await screen.findByText("İptal edilmiş kart — kütüphane yöneticisine yönlendirin."),
    ).toBeInTheDocument();
    expect(uyeBaglami()).toBeNull();
  });

  it("ISBN barkodunda sunucunun özel iletisi gösterilir", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue({
      result: "rejected",
      kind: "ISBN",
      message: "Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.",
      copy: null,
    });
    const kutu = ekranaBas();

    await user.type(kutu, "9789750812345{Enter}");

    expect(
      await screen.findByText("Bu ISBN barkodu. Kitabın kütüphane etiketini okutun."),
    ).toBeInTheDocument();
    expect(masa.kartOku).not.toHaveBeenCalled();
  });
});

describe("Hızlı okutma (kod kapısı)", () => {
  it("art arda 20 kitap okutması sırayla ve eksiksiz iade ucuna gider", async () => {
    const user = userEvent.setup();
    const cozuculer: Array<() => void> = [];
    masa.iadeAl.mockImplementation(
      () =>
        new Promise<IadeSonucu>((coz) => {
          cozuculer.push(() => coz(iadeSonucu()));
        }),
    );
    const kutu = ekranaBas();
    const kodlar = Array.from({ length: 20 }, (_, i) => `2026${String(500 + i).padStart(6, "0")}`);

    for (const kod of kodlar) await user.type(kutu, `${kod}{Enter}`);
    expect(masa.iadeAl).toHaveBeenCalledTimes(1);

    for (let i = 0; i < kodlar.length; i += 1) {
      await waitFor(() => expect(cozuculer).toHaveLength(i + 1));
      await act(async () => cozuculer[i]());
    }
    await waitFor(() => expect(masa.iadeAl).toHaveBeenCalledTimes(20));
    expect(masa.iadeAl.mock.calls.map((c) => c[0])).toEqual(kodlar);
  });

  it("kart ve kitaplar sonuç beklenmeden okutulunca kitaplar kartın bağlamıyla verilir", async () => {
    const user = userEvent.setup();
    let kartiCoz: (() => void) | null = null;
    masa.kartOku.mockImplementation(
      () =>
        new Promise<KartSonucu>((coz) => {
          kartiCoz = () => coz(kartSonucu());
        }),
    );
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}2026000201{Enter}2026000202{Enter}`);
    expect(masa.oduncVer).not.toHaveBeenCalled();
    await act(async () => kartiCoz?.());

    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(2));
    expect(masa.oduncVer.mock.calls.map((c) => c[0])).toEqual([
      { barcode: "2026000201", card_no: KART },
      { barcode: "2026000202", card_no: KART },
    ]);
    expect(masa.iadeAl).not.toHaveBeenCalled();
  });
});

describe("GA-7 — geçersiz kart okutmaları", () => {
  const kilit = () => new ApiError(429, "kart_okutma_kilidi", "Art arda 5 geçersiz kart okutuldu.");

  it("kart okutma durunca şerit yönetici parolası ister; doğru parola okutmayı açar", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockRejectedValueOnce(kilit());
    masa.kartKilidiniAc.mockResolvedValue({ message: "Kart okutma yeniden açıldı." });
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);

    const serit = await screen.findByRole("region", { name: KART_KILIDI_BASLIGI });
    // Pencere DEĞİL: masada kipsel diyalog açılmaz, okutma kutusu odakta kalır.
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(kutu).toHaveFocus();
    await user.type(within(serit).getByLabelText(/Yönetici parolası/), "parola-1");
    await user.click(within(serit).getByRole("button", { name: "Kart okutmayı aç" }));

    await waitFor(() =>
      expect(screen.queryByRole("region", { name: KART_KILIDI_BASLIGI })).toBeNull(),
    );
    expect(masa.kartKilidiniAc).toHaveBeenCalledWith("parola-1");
    await waitFor(() => expect(kutu).toHaveFocus());
  });

  it("kilit dururken okutulan kitabın iadesi alınır (iade kilitlenmez)", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockRejectedValue(kilit());
    const kutu = ekranaBas();

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: KART_KILIDI_BASLIGI });
    // Okuyucu klavye gibi yazar: odak neredeyse oraya.
    await user.keyboard(`${KITAP}{Enter}`);

    await waitFor(() => expect(masa.iadeAl).toHaveBeenCalledWith(KITAP));
    expect(await screen.findByText("İade alındı.")).toBeInTheDocument();
    // Kilitliyken okutulan kart yine kesilir, şerit durur.
    await user.keyboard(`${KART}{Enter}`);
    await waitFor(() => expect(masa.kartOku).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("region", { name: KART_KILIDI_BASLIGI })).toBeInTheDocument();
    expect(masa.oduncVer).not.toHaveBeenCalled();
  });

  it("şeritteki parola alanına yazılırken tuşlar okutma kutusuna kaçmaz", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockRejectedValueOnce(kilit());
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    const serit = await screen.findByRole("region", { name: KART_KILIDI_BASLIGI });

    const parola = within(serit).getByLabelText(/Yönetici parolası/);
    await user.click(parola);
    await user.keyboard("12ab");

    expect(parola).toHaveValue("12ab");
    expect(kutu).toHaveValue("");
    // Yönetici şeritte yazarken "kutu odakta değil" uyarısı çıkmaz.
    expect(screen.queryByText(/Okutma kutusu odakta değil/)).toBeNull();
  });
});

describe("Yönetici kipi — gerekçeli istisna ve kartsız ödünç", () => {
  it("gecikme reddinde istisna diyaloğu açılır; gerekçe ve açıklamayla ödünç verilir", async () => {
    const user = userEvent.setup();
    masa.oduncVer
      .mockRejectedValueOnce(new ApiError(400, "gecikme_engeli", "Üyenin gecikmiş ödüncü var."))
      .mockResolvedValueOnce(oduncSonucu({ has_override: true }));
    const kutu = ekranaBas(false);

    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);

    const diyalog = await screen.findByRole("dialog", { name: "Gerekçeli istisna" });
    expect(within(diyalog).getByText("Sağlık ya da aile bilgisi yazmayın.")).toBeInTheDocument();
    // Pencere hangi kitap için açıldığını söyler.
    expect(within(diyalog).getByText("Kitap: 2026-000123 — Masa Kitabı")).toBeInTheDocument();
    await user.selectOptions(within(diyalog).getByLabelText(/Gerekçe/), "COURSE_NEED");
    await user.type(within(diyalog).getByLabelText(/Açıklama/), "Ödev için gerekli.");
    await user.click(within(diyalog).getByRole("button", { name: "Gerekçeyle ödünç ver" }));

    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(2));
    expect(masa.oduncVer.mock.calls[1][0]).toEqual({
      barcode: KITAP,
      card_no: KART,
      override_reason: "COURSE_NEED",
      override_note: "Ödev için gerekli.",
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("kartsız ödünç: okul no ile üye bulunur, gerekçe seçilir, kayıt kartsız gider", async () => {
    const user = userEvent.setup();
    masa.uyeAra.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 42,
          full_name: "Deneme Okur",
          member_type_display: "öğrenci",
          class_label: "9/A",
          student_number: "700001",
          status: "ACTIVE",
          remaining_quota: 3,
        },
      ],
    });
    masa.uyeAc.mockResolvedValue(kartSonucu({ membership_id: 42 }));
    const kutu = ekranaBas(false);

    await user.click(screen.getByRole("button", { name: "Kartsız ödünç" }));
    const diyalog = await screen.findByRole("dialog", { name: "Kartsız ödünç" });
    await user.type(within(diyalog).getByLabelText("Okul no ya da ad"), "700001{Enter}");
    await within(diyalog).findByText("Deneme Okur");
    await user.selectOptions(within(diyalog).getByLabelText(/Gerekçe/), "CARD_NOT_WITH_MEMBER");
    await user.click(within(diyalog).getByRole("button", { name: "Üyeyi aç" }));

    const baglam = await screen.findByRole("region", { name: "Üye bağlamı" });
    expect(within(baglam).getByText(/Kartsız ödünç — gerekçe: Kart yanında değil/)).toBeVisible();
    await waitFor(() => expect(kutu).toHaveFocus());
    await user.type(kutu, `${KITAP}{Enter}`);

    await waitFor(() =>
      expect(masa.oduncVer).toHaveBeenCalledWith({
        barcode: KITAP,
        membership_id: 42,
        cardless_reason: "CARD_NOT_WITH_MEMBER",
      }),
    );
  });

  it("pencere açıkken okutulan kitaplar kaybolmaz; pencere kapanınca sırayla işlenir", async () => {
    const user = userEvent.setup();
    masa.oduncVer
      .mockRejectedValueOnce(new ApiError(400, "gecikme_engeli", "Üyenin gecikmiş ödüncü var."))
      .mockResolvedValue(oduncSonucu());
    const kutu = ekranaBas(false);
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, "2026000301{Enter}");
    await screen.findByRole("dialog", { name: "Gerekçeli istisna" });

    // Okuyucu ikinci ve üçüncü kitabı okutur (tuşlar odaktaki diyalog paneline gider).
    await user.keyboard("2026000302{Enter}2026000303{Enter}");
    expect(masa.oduncVer).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Vazgeç" }));

    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(3));
    expect(masa.oduncVer.mock.calls.map((c) => (c[0] as { barcode: string }).barcode)).toEqual([
      "2026000301",
      "2026000302",
      "2026000303",
    ]);
  });

  it("kuyrukta bekleyen retler açık pencereyi ezmez: her kitap kendi penceresini alır", async () => {
    const user = userEvent.setup();
    masa.oduncVer.mockImplementation((govde: { barcode: string; override_reason?: string }) =>
      govde.override_reason
        ? Promise.resolve(oduncSonucu())
        : Promise.reject(new ApiError(400, "gecikme_engeli", `Gecikme ${govde.barcode}`)),
    );
    const kutu = ekranaBas(false);
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, "2026000301{Enter}2026000302{Enter}");

    const ilk = await screen.findByRole("dialog", { name: "Gerekçeli istisna" });
    expect(within(ilk).getByText("Gecikme 2026000301")).toBeInTheDocument();
    await user.selectOptions(within(ilk).getByLabelText(/Gerekçe/), "COURSE_NEED");
    await user.type(within(ilk).getByLabelText(/Açıklama/), "Ödev için gerekli.");
    await user.click(within(ilk).getByRole("button", { name: "Gerekçeyle ödünç ver" }));

    // İlk kitap istisnayla verildi; ikinci kitap ŞİMDİ işlenir ve kendi penceresini açar.
    await waitFor(() =>
      expect(
        within(screen.getByRole("dialog", { name: "Gerekçeli istisna" })).getByText(
          "Gecikme 2026000302",
        ),
      ).toBeInTheDocument(),
    );
    const istisnalilar = masa.oduncVer.mock.calls
      .map((c) => c[0] as { barcode: string; override_reason?: string })
      .filter((g) => g.override_reason);
    expect(istisnalilar.map((g) => g.barcode)).toEqual(["2026000301"]);
  });

  it("istisna penceresi açıkken 60 sn bağlamı kapatmaz", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    masa.oduncVer
      .mockRejectedValueOnce(new ApiError(400, "gecikme_engeli", "Üyenin gecikmiş ödüncü var."))
      .mockResolvedValueOnce(oduncSonucu({ has_override: true }));
    const kutu = ekranaBas(false);
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${KITAP}{Enter}`);
    const diyalog = await screen.findByRole("dialog", { name: "Gerekçeli istisna" });
    await user.selectOptions(within(diyalog).getByLabelText(/Gerekçe/), "COURSE_NEED");
    await user.type(within(diyalog).getByLabelText(/Açıklama/), "Ödev için gerekli.");

    await act(async () => vi.advanceTimersByTime(BAGLAM_SURESI_MS + 1_000));
    expect(uyeBaglami()).not.toBeNull();

    await user.click(within(diyalog).getByRole("button", { name: "Gerekçeyle ödünç ver" }));
    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // Pencere kapanınca süre baştan başlar.
    await act(async () => vi.advanceTimersByTime(BAGLAM_SURESI_MS + 1_000));
    expect(uyeBaglami()).toBeNull();
  });

  it("kartsız ödünç penceresi açılınca “Okul no ya da ad” alanı odaktadır", async () => {
    const user = userEvent.setup();
    ekranaBas(false);

    await user.click(screen.getByRole("button", { name: "Kartsız ödünç" }));
    const diyalog = await screen.findByRole("dialog", { name: "Kartsız ödünç" });

    await waitFor(() => expect(within(diyalog).getByLabelText("Okul no ya da ad")).toHaveFocus());
  });

  it("görevli ekranında kartsız ödünç düğmesi yoktur", () => {
    ekranaBas(true);
    expect(screen.queryByRole("button", { name: "Kartsız ödünç" })).toBeNull();
  });
});

describe("Üyeye bağlı ret · istem yarışı", () => {
  it.each([
    ["uyelik_aktif_degil", "Üyelik sonlanmış — ödünç verilemez."],
    ["sinir_dolu", "Ödünç sınırı dolu (en çok 3 kitap)."],
    ["gecikme_engeli", "Ödünç verilemiyor — kütüphane yöneticisine yönlendirin."],
    ["son_odunc_tarihi", "Yıl sonu son ödünç tarihi geçti — yeni ödünç verilmez. İade alınabilir."],
  ])("görevli: %s reddinde okutulan kitabın iadesi önerilir", async (kod, ileti) => {
    // Sonlanmış üyenin kartı okutulduysa kendi kitabı ödünç retiyle kalmamalı (§9-8).
    const user = userEvent.setup();
    masa.oduncVer.mockRejectedValue(new ApiError(400, kod, ileti));
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText(ileti)).toBeInTheDocument();
    expect(screen.getByText(IADE_ONERISI)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "İade al" }));

    await waitFor(() => expect(masa.iadeAl).toHaveBeenCalledWith(KITAP));
    expect(masa.oduncVer).toHaveBeenCalledTimes(1); // iade sonrası ödünç denenmez
  });

  it("kişisel olmayan kitap reddinde (ödünç verilmez) iade önerilmez", async () => {
    const user = userEvent.setup();
    masa.oduncVer.mockRejectedValue(
      new ApiError(400, "odunc_verilmez", "Ödünç verilmez — kütüphanede okunur."),
    );
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("Ödünç verilmez — kütüphanede okunur.")).toBeInTheDocument();
    expect(screen.queryByText(IADE_ONERISI)).toBeNull();
  });

  it("“İade al ve ödünç ver” sürerken yeni kart okutulursa kitap ikinci üyeye VERİLMEZ", async () => {
    const user = userEvent.setup();
    let iadeyiCoz: (() => void) | null = null;
    masa.kartOku
      .mockResolvedValueOnce(kartSonucu({ full_name: "Birinci Okur" }))
      .mockResolvedValueOnce(kartSonucu({ full_name: "İkinci Okur" }));
    masa.oduncVer.mockRejectedValueOnce(
      new ApiError(400, "nusha_baska_uyede", "Bu kitap başka bir üyede."),
    );
    masa.iadeAl.mockImplementation(
      () =>
        new Promise<IadeSonucu>((coz) => {
          iadeyiCoz = () => coz(iadeSonucu());
        }),
    );
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByText("Birinci Okur");
    await user.type(kutu, `${KITAP}{Enter}`);
    await user.click(await screen.findByRole("button", { name: "İade al ve ödünç ver" }));

    await user.type(kutu, `${OBUR_KART}{Enter}`);
    await screen.findByText("İkinci Okur");
    await act(async () => iadeyiCoz?.());

    expect(await screen.findByText(ISTEM_BAGLAM_DEGISTI)).toBeInTheDocument();
    expect(masa.oduncVer).toHaveBeenCalledTimes(1);
  });
});

describe("Nüsha durum sorgusu", () => {
  it("durum sorgusu ödünçten ayrı sesle biter; üye kartı okutulunca kendiliğinden kapanır", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValue({
      kind: "COPY",
      message: "Rafta — ödünç verilebilir.",
      copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
    });
    const kutu = ekranaBas();
    const kutucuk = screen.getByLabelText(/Yalnız durum sor/);

    await user.click(kutucuk);
    await user.type(kutu, `${KITAP}{Enter}`);
    await waitFor(() => expect(kutu).toHaveAttribute("data-geri-bildirim", "bilgi"));

    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    expect(kutucuk).not.toBeChecked();
    expect(screen.getByText(DURUM_SORGUSU_KAPANDI)).toBeInTheDocument();
    await user.type(kutu, `${KITAP}{Enter}`);
    await waitFor(() => expect(masa.oduncVer).toHaveBeenCalledTimes(1));
    expect(masa.nushaDurumu).toHaveBeenCalledTimes(1);
  });

  it("“Yalnız durum sor” açıkken kitap okutması yazma yapmaz", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValue({
      kind: "COPY",
      message: "Rafta — ödünç verilebilir.",
      copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
    });
    const kutu = ekranaBas();

    await user.click(screen.getByLabelText(/Yalnız durum sor/));
    await user.type(kutu, `${KITAP}{Enter}`);

    expect(await screen.findByText("Rafta — ödünç verilebilir.")).toBeInTheDocument();
    expect(masa.nushaDurumu).toHaveBeenCalledWith(KITAP);
    expect(masa.iadeAl).not.toHaveBeenCalled();
  });
});

// F7 — teslimdeki kitap masada okutulunca (U11, §4.4) ve açık ödüncün kayıp bildirimi.
describe("F7 | teslimdeki kitap ve kayıp bildirimi", () => {
  it("görevli: teslimdeki kitap iade edilmez, teslimden geri alma önerilir; kime teslim edildiği yazmaz", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue(
      iadeSonucu({ result: "not_on_loan", message: SINIF_KITAPLIGINDA }),
    );
    teslimKapi.geriAl.mockResolvedValue({
      result: "returned",
      kind: "COPY",
      message: "Geri alındı.",
      copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
    });
    const kutu = ekranaBas();

    await user.type(kutu, `${KITAP}{Enter}`);
    expect(await screen.findByText(TESLIM_GERI_ALMA_ONERISI)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: TESLIMDEN_GERI_AL }));

    await waitFor(() => expect(teslimKapi.geriAl).toHaveBeenCalledWith(KITAP));
    const durum = await screen.findByRole("status");
    expect(durum).toHaveTextContent("Geri alındı.");
    expect(durum).toHaveTextContent("2026-000123 — Masa Kitabı");
    expect(screen.queryByRole("button", { name: TESLIMDEN_GERI_AL })).not.toBeInTheDocument();
  });

  it("yönetici: nüsha durumu teslimdeyse öneri çıkar; geri almada teslim alan yazılır", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue(
      iadeSonucu({
        result: "not_on_loan",
        message: "Durum iletisi",
        copy: {
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Masa Kitabı",
          status: "DELIVERED",
          status_display: "Sınıf kitaplığında",
        },
      }),
    );
    teslimKapi.geriAl.mockResolvedValue({
      result: "returned",
      kind: "COPY",
      message: "Geri alındı.",
      copy: { barcode: KITAP, barcode_display: "2026-000123", work_title: "Masa Kitabı" },
      delivery: {
        id: 3,
        recipient_kind: "SECTION",
        recipient_kind_display: "Sınıf kitaplığı",
        recipient_label: "3/A",
        delivered_on: "2026-09-21",
        expected_return: null,
        document_no: "2026/1",
        returned_at: null,
      },
    });
    const kutu = ekranaBas(false);
    await user.type(kutu, `${KITAP}{Enter}`);
    await user.click(await screen.findByRole("button", { name: TESLIMDEN_GERI_AL }));
    expect(await screen.findByText(/Sınıf kitaplığı: 3\/A/)).toBeInTheDocument();
  });

  it("rafta ya da başka durumdaki kitapta teslim önerisi çıkmaz", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue(
      iadeSonucu({ result: "not_on_loan", message: "Rafta — ödünç değil." }),
    );
    const kutu = ekranaBas();
    await user.type(kutu, `${KITAP}{Enter}`);
    expect(await screen.findByText("Rafta — ödünç değil.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: TESLIMDEN_GERI_AL })).not.toBeInTheDocument();
  });

  it("geri alma isteği başarısız olursa ileti düşer", async () => {
    const user = userEvent.setup();
    masa.iadeAl.mockResolvedValue(
      iadeSonucu({ result: "not_on_loan", message: SINIF_KITAPLIGINDA }),
    );
    teslimKapi.geriAl.mockRejectedValue(new Error("ağ yok"));
    const kutu = ekranaBas();
    await user.type(kutu, `${KITAP}{Enter}`);
    await user.click(await screen.findByRole("button", { name: TESLIMDEN_GERI_AL }));
    expect(
      await screen.findByText("Geri alma kaydedilemedi; kitabı yeniden okutun."),
    ).toBeInTheDocument();
  });

  const ACIK_ODUNC = {
    id: 1,
    barcode: "2026000001",
    barcode_display: "2026-000001",
    work_title: "Kaybolan Eser",
    loaned_at: "2026-09-01T10:00:00+03:00",
    due_date: "2026-09-16",
    overdue_days: 0,
    cardless: false,
    has_override: false,
  };

  it("yönetici: açık ödünçte kayıp bildirimi; ödünç kapanır ve kalan hak sunucudan tazelenir", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockResolvedValue(
      kartSonucu({
        membership_id: 7,
        remaining_quota: 2,
        open_loan_count: 1,
        open_loans: [ACIK_ODUNC],
      }),
    );
    masa.uyeAc.mockResolvedValue(
      kartSonucu({ membership_id: 7, remaining_quota: 3, open_loan_count: 0, open_loans: [] }),
    );
    kayipKapi.ac.mockResolvedValue({ id: 9, case_type: "LOST" });
    const kutu = ekranaBas(false);
    await user.type(kutu, `${KART}{Enter}`);
    const baglam = await screen.findByRole("region", { name: "Üye bağlamı" });

    await user.click(within(baglam).getByRole("button", { name: "2026-000001 için kayıp bildir" }));
    const pencere = await screen.findByRole("dialog", { name: "Kayıp bildirilsin mi?" });
    expect(pencere).toHaveTextContent("2026-000001 — Kaybolan Eser");
    await user.click(within(pencere).getByRole("button", { name: "Kayıp bildir" }));

    await waitFor(() =>
      expect(kayipKapi.ac).toHaveBeenCalledWith(
        expect.objectContaining({ case_type: "LOST", barcode: "2026000001" }),
      ),
    );
    await waitFor(() => expect(masa.uyeAc).toHaveBeenCalledWith(7));
    expect(await screen.findByText(KAYIP_BILDIRILDI)).toBeInTheDocument();
    expect(await within(baglam).findByText("Kalan ödünç hakkı: 3")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("görevli kipinde kayıp bildirimi kısayolu yoktur", async () => {
    const user = userEvent.setup();
    masa.kartOku.mockResolvedValue(kartSonucu({ open_loans: [ACIK_ODUNC] }));
    const kutu = ekranaBas();
    await user.type(kutu, `${KART}{Enter}`);
    await screen.findByRole("region", { name: "Üye bağlamı" });
    expect(screen.queryByRole("button", { name: /kayıp bildir/i })).not.toBeInTheDocument();
  });
});
