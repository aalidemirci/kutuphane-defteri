// Ayarlar → Kütüphane Politikası.
//
// Sabitlenen davranışlar:
//   1) ödünç süresi AYAR DEĞİLDİR: sunucudan gelen değer bilgi olarak yazılır,
//      giriş alanı yoktur ve gövdede gönderilmez (Md. 18 sabit);
//   2) diğer personele ödünç açılınca müdürlük kararı alanları görünür;
//   3) sunucunun alan hatası ilgili alanda gösterilir (genel banda düşmez).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import { politika } from "../../test/kutuphaneVerileri";

const kapi = vi.hoisted(() => ({
  getPolicy: vi.fn(),
  updatePolicy: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, kutuphaneApi: { ...actual.kutuphaneApi, ...kapi } };
});

import KutuphanePolitikasiPaneli from "./KutuphanePolitikasiPaneli";

function ekranaBas() {
  return render(
    <SnackbarProvider>
      <KutuphanePolitikasiPaneli />
    </SnackbarProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  kapi.getPolicy.mockResolvedValue(politika());
});

describe("Kütüphane Politikası", () => {
  it("ödünç süresini bilgi olarak yazar, giriş alanı sunmaz", async () => {
    ekranaBas();

    expect(await screen.findByText(/Ödünç süresi 15 gündür ve değiştirilemez/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Ödünç süresi/)).not.toBeInTheDocument();
  });

  it("kaydetme kısmidir: ödünç süresi gövdeye girmez", async () => {
    const user = userEvent.setup();
    kapi.updatePolicy.mockResolvedValue(politika({ max_loans_student: 2 }));
    ekranaBas();
    const ogrenci = await screen.findByLabelText("Öğrenci");

    await user.clear(ogrenci);
    await user.type(ogrenci, "2");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updatePolicy).toHaveBeenCalled());
    const govde = kapi.updatePolicy.mock.calls[0][0] as Record<string, unknown>;
    expect(govde.max_loans_student).toBe(2);
    expect(govde).not.toHaveProperty("loan_period_days");
  });

  it("diğer personele ödünç açılınca müdürlük kararı alanları çıkar", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByLabelText("Öğrenci");

    expect(screen.queryByLabelText(/Müdürlük kararı tarihi/)).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Diğer personele ödünç verilir"));

    expect(await screen.findByLabelText(/Müdürlük kararı tarihi/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Müdürlük kararı sayısı/)).toBeInTheDocument();
  });

  it("sunucunun alan hatası ilgili alanda gösterilir", async () => {
    const user = userEvent.setup();
    kapi.updatePolicy.mockRejectedValue(
      new ApiError(400, "invalid", "Kayıt doğrulanamadı.", {
        staff_loans_decision_no: ["Müdürlük kararının sayısı zorunludur."],
      }),
    );
    ekranaBas();
    await screen.findByLabelText("Öğrenci");
    await user.click(screen.getByLabelText("Diğer personele ödünç verilir"));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    expect(await screen.findByText("Müdürlük kararının sayısı zorunludur.")).toBeInTheDocument();
  });

  it("politika okunamazsa hata bandı çıkar", async () => {
    kapi.getPolicy.mockRejectedValue(new Error("ağ yok"));
    ekranaBas();

    expect(await screen.findByRole("alert")).toHaveTextContent("Kütüphane politikası yüklenemedi.");
  });
});
