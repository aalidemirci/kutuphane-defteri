// Kayıp bildirimi ve hasar dosyası penceresi (F7, Md. 19, D3). Başlık soru, gövde
// sonuç; ödünçteki kitapta sorumlu ödünçten gelir (üye sorulmaz); hasarda onarıma
// gönderme seçilebilir; önceden seçilmiş nüshada okutma kutusu yoktur. Adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { todayIso } from "../../lib/format";
import { dosyaVerisi } from "../../test/teslimVerileri";
import type { NushaDurumu } from "../dolasim/api";

const kayip = vi.hoisted(() => ({ ac: vi.fn() }));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kayipApi: { ...actual.kayipApi, ...kayip } };
});
const masa = vi.hoisted(() => ({ nushaDurumu: vi.fn(), uyeAra: vi.fn() }));
vi.mock("../dolasim/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../dolasim/api")>();
  return { ...actual, dolasimApi: { ...actual.dolasimApi, ...masa } };
});

import DosyaAcDiyalogu, {
  HASAR_BASLIGI,
  KAYIP_BASLIGI,
  KAYIP_SONUCU,
  TESLIMDE_SORUMLU_YARDIMI,
  dosyaAcildiIletisi,
} from "./DosyaAcDiyalogu";

const KITAP = "2026000123";

/** Hata bandının kurulum bağlantısı yönlendirici ister. */
function ciz(ogeler: ReactElement) {
  return render(<MemoryRouter>{ogeler}</MemoryRouter>);
}

function durum(ek: Partial<NushaDurumu> = {}): NushaDurumu {
  return {
    kind: "COPY",
    message: "Ödünçte.",
    copy: {
      id: 11,
      barcode: KITAP,
      barcode_display: "2026-000123",
      work_title: "Deneme Kitabı",
      status: "ON_LOAN",
      status_display: "Ödünçte",
    },
    loan: {
      member_name: "Deneme Okur",
      class_label: "9/A",
      loaned_at: "2026-09-10T10:00:00+03:00",
      due_date: "2026-09-25",
      overdue_days: 0,
    },
    ...ek,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  masa.nushaDurumu.mockResolvedValue(durum());
  masa.uyeAra.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 3,
        full_name: "Deneme Okur",
        member_type_display: "Öğrenci",
        class_label: "9/A",
        student_number: "101",
        status: "ACTIVE",
        remaining_quota: 3,
      },
    ],
  });
  kayip.ac.mockResolvedValue(dosyaVerisi());
});

describe("DosyaAcDiyalogu — kayıp bildirimi", () => {
  it("kitap okutulur; ödünçteki kitapta sorumlu ödünçten gelir, üye sorulmaz", async () => {
    const user = userEvent.setup();
    const onAcildi = vi.fn();
    ciz(<DosyaAcDiyalogu open tur="LOST" onClose={vi.fn()} onAcildi={onAcildi} />);

    const pencere = screen.getByRole("dialog", { name: KAYIP_BASLIGI });
    expect(pencere).toHaveTextContent(KAYIP_SONUCU);
    const dugme = within(pencere).getByRole("button", { name: "Kayıp bildir" });
    expect(dugme).toBeDisabled();

    await user.type(screen.getByLabelText("Kütüphane etiketi"), `${KITAP}{Enter}`);
    const nusha = await screen.findByRole("region", { name: "Nüsha" });
    expect(nusha).toHaveTextContent("2026-000123 — Deneme Kitabı");
    expect(nusha).toHaveTextContent("Durum: Ödünçte");
    expect(nusha).toHaveTextContent("Ödünç alan: Deneme Okur · 9/A");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText(/Sorumlu, kitabı ödünç alan üyedir/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Sorumlu notu (isteğe bağlı)"), "Kitap okulda kayboldu");
    await user.click(dugme);
    await waitFor(() => expect(onAcildi).toHaveBeenCalledTimes(1));
    expect(kayip.ac).toHaveBeenCalledWith({
      case_type: "LOST",
      copy_id: 11,
      reported_on: todayIso(),
      responsible_note: "Kitap okulda kayboldu",
    });
    expect(document.body).not.toHaveTextContent(/borç|ceza|zayi|bedel/i);
  });

  it("teslimdeki kitapta üye alanı dosyanın kime bağlanacağını söyler", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValue(
      durum({
        message: "Sınıf kitaplığında.",
        copy: {
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
          status: "DELIVERED",
          status_display: "Sınıf kitaplığında",
        },
        loan: null,
      }),
    );
    ciz(<DosyaAcDiyalogu open tur="LOST" onClose={vi.fn()} onAcildi={vi.fn()} />);
    await user.type(screen.getByLabelText("Kütüphane etiketi"), `${KITAP}{Enter}`);
    await screen.findByText("Durum: Sınıf kitaplığında");
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText(TESLIMDE_SORUMLU_YARDIMI)).toBeInTheDocument();
  });

  it("tanınmayan kod alan hatası verir, dosya açılmaz", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValueOnce({
      kind: "ISBN",
      message: "Bu bir ISBN barkodu.",
      copy: null,
    });
    ciz(<DosyaAcDiyalogu open tur="LOST" onClose={vi.fn()} onAcildi={vi.fn()} />);
    await user.type(screen.getByLabelText("Kütüphane etiketi"), "9789750812345{Enter}");
    expect(await screen.findByText("Bu bir ISBN barkodu.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kayıp bildir" })).toBeDisabled();
  });

  it("raftaki kitapta sorumlu üye seçilebilir", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValueOnce(
      durum({
        message: "Rafta.",
        copy: {
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
          status: "AVAILABLE",
          status_display: "Rafta",
        },
        loan: null,
      }),
    );
    ciz(<DosyaAcDiyalogu open tur="LOST" onClose={vi.fn()} onAcildi={vi.fn()} />);
    await user.type(screen.getByLabelText("Kütüphane etiketi"), `${KITAP}{Enter}`);
    await screen.findByRole("region", { name: "Nüsha" });
    await user.type(screen.getByRole("combobox"), "Deneme");
    await user.click(await screen.findByRole("option", { name: /Deneme Okur/ }));
    await user.click(screen.getByRole("button", { name: "Kayıp bildir" }));
    await waitFor(() =>
      expect(kayip.ac).toHaveBeenCalledWith(expect.objectContaining({ membership_id: 3 })),
    );
  });

  it("parola kurulmadan (409) kurulum yönlendirmesi gösterilir", async () => {
    const user = userEvent.setup();
    kayip.ac.mockRejectedValueOnce(
      new ApiError(409, "parola_gerekli", "Kişi kaydı için önce yönetici parolasını kurun."),
    );
    ciz(
      <DosyaAcDiyalogu
        open
        tur="LOST"
        nusha={{
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
        }}
        onClose={vi.fn()}
        onAcildi={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Kayıp bildir" }));
    expect(await screen.findByText("Önce yönetici parolasını kurun")).toBeInTheDocument();
  });
});

describe("DosyaAcDiyalogu — hasar dosyası", () => {
  it("önceden seçilmiş raftaki nüsha: okutma yok, onarıma gönderme seçilebilir", async () => {
    const user = userEvent.setup();
    masa.nushaDurumu.mockResolvedValueOnce(
      durum({
        copy: {
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
          status: "AVAILABLE",
          status_display: "Rafta",
        },
        loan: null,
      }),
    );
    const onAcildi = vi.fn();
    ciz(
      <DosyaAcDiyalogu
        open
        tur="DAMAGED"
        nusha={{
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
        }}
        onClose={vi.fn()}
        onAcildi={onAcildi}
      />,
    );
    expect(screen.getByRole("dialog", { name: HASAR_BASLIGI })).toBeInTheDocument();
    expect(screen.queryByLabelText("Kütüphane etiketi")).not.toBeInTheDocument();
    await waitFor(() => expect(masa.nushaDurumu).toHaveBeenCalledWith(KITAP));
    expect(await screen.findByText("Durum: Rafta")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Nüshayı onarıma da gönder" }));
    await user.click(screen.getByRole("button", { name: "Hasar dosyası aç" }));
    await waitFor(() => expect(onAcildi).toHaveBeenCalled());
    expect(kayip.ac).toHaveBeenCalledWith({
      case_type: "DAMAGED",
      copy_id: 11,
      reported_on: todayIso(),
      send_to_repair: true,
    });
  });

  it("onarımdaki nüshada onarım kaydının dosyaya bağlanacağı yazılır", async () => {
    masa.nushaDurumu.mockResolvedValueOnce(
      durum({
        copy: {
          id: 11,
          barcode: KITAP,
          barcode_display: "2026-000123",
          work_title: "Deneme Kitabı",
          status: "IN_REPAIR",
          status_display: "Onarımda",
        },
        loan: null,
      }),
    );
    ciz(
      <DosyaAcDiyalogu
        open
        tur="DAMAGED"
        nusha={{ barcode: KITAP, barcode_display: "2026-000123", work_title: "Deneme Kitabı" }}
        onClose={vi.fn()}
        onAcildi={vi.fn()}
      />,
    );
    expect(
      await screen.findByText("Nüsha onarımda; açık onarım kaydı bu dosyaya bağlanır."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("başarı iletileri tam cümledir", () => {
    expect(dosyaAcildiIletisi("LOST")).toBe("Kayıp bildirildi; kayıp dosyası açıldı.");
    expect(dosyaAcildiIletisi("DAMAGED")).toBe("Hasar dosyası açıldı.");
  });
});
