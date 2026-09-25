// Nadir Eserler (F8; Md. 12/2, D14): listeler · yeni liste · liste penceresi (karar bağlama,
// eser ekleme ve çıkarma, Genel Müdürlüğe gönderim — onaylı, belge) · nadir eser işaretli
// nüshalar (bildirildi rozeti, süzgeç). Bütün adlar uydurmadır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { komisyonKarari } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { nadirListe, nadirNusha, sayfa } from "./testVerileri";

const ayiklama = vi.hoisted(() => ({
  nadirNushalar: vi.fn(),
  listeler: vi.fn(),
  liste: vi.fn(),
  listeAc: vi.fn(),
  listeGuncelle: vi.fn(),
  listeSil: vi.fn(),
  listeyeEkle: vi.fn(),
  listedenCikar: vi.fn(),
  gonderildi: vi.fn(),
  listePdf: vi.fn(),
}));
vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ayiklamaApi: { ...actual.ayiklamaApi, ...ayiklama } };
});
const kutuphane = vi.hoisted(() => ({ listCommissionDecisions: vi.fn() }));
vi.mock("../kutuphane/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../kutuphane/api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kutuphane } };
});
const saveBlobMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/download")>()),
  saveBlob: saveBlobMock,
}));

import NadirEserlerPage from "./NadirEserlerPage";

function ciz(yol = "/katalog/nadir-eserler") {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <SnackbarProvider>
        <ConfirmProvider>
          <NadirEserlerPage />
        </ConfirmProvider>
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  ayiklama.listeler.mockResolvedValue(sayfa([nadirListe()]));
  ayiklama.liste.mockResolvedValue(nadirListe());
  ayiklama.nadirNushalar.mockResolvedValue(sayfa([nadirNusha()]));
  ayiklama.listePdf.mockResolvedValue(new Blob(["%PDF"]));
  kutuphane.listCommissionDecisions.mockResolvedValue(
    sayfa([komisyonKarari({ id: 9, decision_type: "WEEDING", decision_type_display: "Ayıklama" })]),
  );
});

describe("NadirEserlerPage", () => {
  it("başlık, Md. 12/2 açıklaması, yan bağlantılar ve liste satırı", async () => {
    ciz();
    expect(screen.getByRole("heading", { level: 1, name: "Nadir Eserler" })).toBeInTheDocument();
    expect(screen.getByText(/El yazması ve nadir eser ayıklanmaz/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ayıklama" })).toHaveAttribute(
      "href",
      "/katalog/ayiklama",
    );
    expect(await screen.findByText("Hazırlanıyor")).toBeInTheDocument();
  });

  it("yeni liste açılır; pencerede karar bağlanır, eser eklenir ve çıkarılır, PDF basılır", async () => {
    ayiklama.listeAc.mockResolvedValue(nadirListe());
    ayiklama.listeGuncelle.mockResolvedValue(nadirListe());
    ayiklama.listeyeEkle.mockResolvedValue({ added: [], submission: nadirListe() });
    ayiklama.listedenCikar.mockResolvedValue(undefined);
    const user = userEvent.setup();
    ciz();
    await screen.findByText("Hazırlanıyor");
    await user.click(screen.getByRole("button", { name: "Yeni liste" }));
    const pencere = await screen.findByRole("dialog", {
      name: "El yazması ve nadir eserler listesi",
    });
    expect(ayiklama.listeAc).toHaveBeenCalled();
    expect(await within(pencere).findByText(/Deneme Nadir Eseri/)).toBeInTheDocument();

    await within(pencere).findByRole("option", { name: /Ayıklama —/ });
    await user.selectOptions(within(pencere).getByLabelText(/Komisyon kararı/), "9");
    await user.click(within(pencere).getByRole("button", { name: "Kararı kaydet" }));
    await waitFor(() =>
      expect(ayiklama.listeGuncelle).toHaveBeenCalledWith(5, { commission_decision: 9 }),
    );

    await user.click(within(pencere).getByRole("checkbox", { name: /Deneme Yazması/ }));
    await user.click(within(pencere).getByRole("button", { name: "Seçilenleri listeye ekle (1)" }));
    await waitFor(() => expect(ayiklama.listeyeEkle).toHaveBeenCalledWith(5, { copies: [201] }));

    await user.click(
      within(pencere).getByRole("button", { name: "Deneme Nadir Eseri eserini listeden çıkar" }),
    );
    await waitFor(() => expect(ayiklama.listedenCikar).toHaveBeenCalledWith(5, 51));

    await user.click(within(pencere).getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(ayiklama.listePdf).toHaveBeenCalledWith(5));
    expect(saveBlobMock).toHaveBeenCalledWith(
      expect.any(Blob),
      expect.stringMatching(/^El-yazması-ve-nadir-eserler-listesi_/),
    );
  });

  it("gönderim onay ister; gönderilmiş liste değişmez; silme onaylı", async () => {
    ayiklama.gonderildi.mockResolvedValue(
      nadirListe({ status: "SENT", status_display: "Genel Müdürlüğe gönderildi" }),
    );
    ayiklama.listeSil.mockResolvedValue(undefined);
    const user = userEvent.setup();
    ciz();
    await user.click(await screen.findByRole("button", { name: /listesini aç/ }));
    const pencere = await screen.findByRole("dialog", {
      name: "El yazması ve nadir eserler listesi",
    });
    await within(pencere).findByText(/Deneme Nadir Eseri/);
    await user.type(within(pencere).getByLabelText(/Gönderme yazısının sayısı/), "E-77");
    await user.click(within(pencere).getByRole("button", { name: "Gönderildi olarak işaretle" }));
    const onay = await screen.findByRole("dialog", {
      name: "Liste gönderildi olarak işaretlensin mi?",
    });
    await user.click(within(onay).getByRole("button", { name: "Gönderildi olarak işaretle" }));
    await waitFor(() =>
      expect(ayiklama.gonderildi).toHaveBeenCalledWith(5, {
        sent_on: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        sent_document_no: "E-77",
      }),
    );

    await user.click(within(pencere).getByRole("button", { name: "Listeyi sil" }));
    const silme = await screen.findByRole("dialog", { name: "Liste silinsin mi?" });
    await user.click(within(silme).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(ayiklama.listeSil).toHaveBeenCalledWith(5));
  });

  it("gönderilmiş listede düzenleme yok", async () => {
    ayiklama.liste.mockResolvedValue(
      nadirListe({
        status: "SENT",
        status_display: "Genel Müdürlüğe gönderildi",
        sent_on: "2027-06-10",
        sent_document_no: "E-77",
        commission_decision: 9,
      }),
    );
    const user = userEvent.setup();
    ciz();
    await user.click(await screen.findByRole("button", { name: /listesini aç/ }));
    const pencere = await screen.findByRole("dialog", {
      name: "El yazması ve nadir eserler listesi",
    });
    expect(await within(pencere).findByText("10.06.2027 · E-77")).toBeInTheDocument();
    expect(within(pencere).queryByRole("button", { name: "Listeyi sil" })).not.toBeInTheDocument();
    expect(within(pencere).queryByRole("button", { name: /çıkar/ })).not.toBeInTheDocument();
    expect(within(pencere).getByLabelText(/Komisyon kararı/)).toBeDisabled();
  });

  it("nüshalar sekmesi: bildirildi rozeti ve süzgeç", async () => {
    ayiklama.nadirNushalar.mockResolvedValue(
      sayfa([nadirNusha(), nadirNusha({ id: 202, work_title: "Bildirilmiş Eser", sent: true })]),
    );
    const user = userEvent.setup();
    ciz("/katalog/nadir-eserler?tab=nushalar");
    expect(await screen.findByText("Bildirilmiş Eser")).toBeInTheDocument();
    expect(screen.getByText("Bildirildi")).toBeInTheDocument();
    expect(screen.getByText("Bildirilmedi")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Yalnız bildirilmemişler" }));
    await waitFor(() =>
      expect(ayiklama.nadirNushalar).toHaveBeenLastCalledWith({
        unsent: true,
        limit: 25,
        offset: 0,
      }),
    );
  });

  it("boş listeler", async () => {
    ayiklama.listeler.mockResolvedValue(sayfa([]));
    ayiklama.nadirNushalar.mockResolvedValue(sayfa([]));
    const user = userEvent.setup();
    ciz();
    expect(await screen.findByText("Gösterilecek liste yok")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /Nadir Eser İşaretli Nüshalar/ }));
    expect(await screen.findByText("Nadir eser işaretli nüsha yok")).toBeInTheDocument();
  });
});
