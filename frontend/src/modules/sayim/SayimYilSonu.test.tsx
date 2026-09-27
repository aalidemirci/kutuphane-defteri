// "Yıl sonu sayımı" işareti (F10 — F9 ekleri K6; TMY 32/1): taslakta seçenekler arasında,
// sürerken ve tamamlanmışken ayrıntıda değişir (onaya dek); işaretsiz sayımın belgeler kartı
// ekin "Ara sayım" başlığını aldığını söyler. Bütün adlar uydurmadır.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { belgeler, ilerleme, sayfa, sayim, sayimSatiri, taslakSayim } from "./testVerileri";

const api = vi.hoisted(() => ({
  sayimlar: vi.fn(),
  sayim: vi.fn(),
  taslakGuncelle: vi.fn(),
  yilSonuIsaretle: vi.fn(),
  ilerleme: vi.fn(),
  kalemler: vi.fn(),
  belgeler: vi.fn(),
  belge: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, sayimApi: { ...actual.sayimApi, ...api } };
});

import { ARA_SAYIM_ADI, EK_ADI, YIL_SONU_SAYIMI } from "./api";
import SayimPage from "./SayimPage";

function ciz(yol = "/katalog/sayim?sayim=7") {
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

beforeEach(() => {
  vi.resetAllMocks();
  api.sayimlar.mockResolvedValue(sayfa([sayimSatiri()]));
  api.belgeler.mockResolvedValue(belgeler());
  api.belge.mockResolvedValue(new Blob(["%PDF"]));
  api.ilerleme.mockResolvedValue(ilerleme());
  api.kalemler.mockResolvedValue(sayfa([]));
});

describe("Yıl sonu sayımı işareti", () => {
  it("taslakta işaretlenir ve kaydedilir", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim());
    api.taslakGuncelle.mockResolvedValue(taslakSayim({ is_year_end: true }));
    ciz();
    await user.click(await screen.findByLabelText(YIL_SONU_SAYIMI));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(api.taslakGuncelle).toHaveBeenCalled());
    expect(api.taslakGuncelle.mock.calls[0][1]).toMatchObject({ is_year_end: true });
  });

  it("süren sayımda ayrıntıdan değişir; işaretsizse belgeler kartı ara sayımı söyler", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(sayim({ status: "IN_PROGRESS", is_year_end: false }));
    api.yilSonuIsaretle.mockResolvedValue(sayim({ status: "IN_PROGRESS", is_year_end: true }));
    ciz();
    expect(
      await screen.findByText(/Bu sayım yıl sonu sayımı olarak işaretli değil/),
    ).toHaveTextContent(ARA_SAYIM_ADI);
    expect(screen.getByText("Ara sayım")).toBeInTheDocument();
    api.sayim.mockResolvedValue(sayim({ status: "IN_PROGRESS", is_year_end: true }));
    await user.click(screen.getByLabelText(YIL_SONU_SAYIMI));
    await waitFor(() => expect(api.yilSonuIsaretle).toHaveBeenCalledWith(7, true));
    expect(await screen.findByText(/^Sayım tutanağının ekinde “/)).toHaveTextContent(EK_ADI);
  });

  it("onaylanmış sayımda işaret değişmez (kutu yok), türü yazar", async () => {
    api.sayim.mockResolvedValue(
      sayim({ status: "APPROVED", status_display: "Onaylandı", is_year_end: true }),
    );
    ciz();
    expect(await screen.findByText(YIL_SONU_SAYIMI)).toBeInTheDocument();
    expect(screen.queryByLabelText(YIL_SONU_SAYIMI)).not.toBeInTheDocument();
  });

  it("başlatma onayı sayımın türünü söyler (yıl sonu sayımı)", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim({ is_year_end: true }));
    ciz();
    await user.click(await screen.findByRole("button", { name: "Sayımı başlat" }));
    const pencere = await screen.findByRole("dialog");
    expect(pencere).toHaveTextContent(`Sayım yıl sonu sayımıdır: tutanağın ekinde “${EK_ADI}”`);
  });

  it("başlatma onayı işaretsiz sayımın ara sayım olduğunu söyler", async () => {
    const user = userEvent.setup();
    api.sayim.mockResolvedValue(taslakSayim({ is_year_end: false }));
    ciz();
    await user.click(await screen.findByRole("button", { name: "Sayımı başlat" }));
    const pencere = await screen.findByRole("dialog");
    expect(pencere).toHaveTextContent("Sayım yıl sonu sayımı olarak işaretli değil");
    expect(pencere).toHaveTextContent(ARA_SAYIM_ADI);
    expect(pencere).toHaveTextContent("İşaret onaya dek değiştirilebilir.");
  });

  it("sayım listesinin Tür sütunu yıl sonu sayımını ara sayımdan ayırır", async () => {
    api.sayimlar.mockResolvedValue(
      sayfa([
        sayimSatiri({ id: 3, is_year_end: true, status: "APPROVED", status_display: "Onaylandı" }),
        sayimSatiri({ id: 2, is_year_end: false, status: "APPROVED", status_display: "Onaylandı" }),
      ]),
    );
    ciz("/katalog/sayim");
    expect(await screen.findByRole("columnheader", { name: "Tür" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: YIL_SONU_SAYIMI })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Ara sayım" })).toBeInTheDocument();
  });
});
