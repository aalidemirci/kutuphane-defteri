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

// ISBN ile künye getirme (U13, §8.5-1): tek dış kapı ayarı. Varsayılan KAPALI
// olduğu ve kapalıyken kaynak seçimlerinin kilitli geldiği burada sabitlenir —
// kullanıcı "işaretledim ama çalışmıyor" durumuna düşmesin.
describe("Kütüphane Politikası — Künye Getirme", () => {
  it("varsayılan kapalıdır ve kaynak seçimleri kilitli gelir", async () => {
    ekranaBas();

    const ana = await screen.findByLabelText("ISBN ile künye getirme açık");
    expect(ana).not.toBeChecked();
    expect(
      screen.getByLabelText("Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğunda ara"),
    ).toBeDisabled();
    expect(screen.getByLabelText("Bulunamazsa Open Library'de ara")).toBeDisabled();
  });

  it("dışarıya yalnız numaranın gittiğini ve önerinin onay istediğini yazar", async () => {
    ekranaBas();
    await screen.findByLabelText("ISBN ile künye getirme açık");

    expect(screen.getByText(/dışarıya yalnız numaranın kendisi gider/)).toBeInTheDocument();
    expect(screen.getByText(/çevirmen alanı dışarıdan doldurulmaz/)).toBeInTheDocument();
  });

  it("açıldığında kaynak seçimleri açılır ve üç alan birlikte kaydedilir", async () => {
    const user = userEvent.setup();
    kapi.updatePolicy.mockResolvedValue(politika({ metadata_lookup_enabled: true }));
    ekranaBas();

    await user.click(await screen.findByLabelText("ISBN ile künye getirme açık"));
    const openLibrary = screen.getByLabelText("Bulunamazsa Open Library'de ara");
    expect(openLibrary).toBeEnabled();
    await user.click(openLibrary);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updatePolicy).toHaveBeenCalled());
    expect(kapi.updatePolicy.mock.calls[0][0]).toMatchObject({
      metadata_lookup_enabled: true,
      metadata_lookup_ministry: true,
      metadata_lookup_openlibrary: false,
    });
  });

  it("iki kaynak da kapalıyken uyarır (sebep internet değil, ayardır)", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.click(await screen.findByLabelText("ISBN ile künye getirme açık"));
    await user.click(
      screen.getByLabelText("Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğunda ara"),
    );
    await user.click(screen.getByLabelText("Bulunamazsa Open Library'de ara"));

    expect(await screen.findByText(/Hiçbir kaynak seçili değil/)).toBeInTheDocument();
  });
});

// F7: yönetici kipi süreleri artık gerçekten etkilidir (kip kapısı LibraryPolicy'den okur).
describe("Kütüphane Politikası — yönetici kipi süreleri", () => {
  it("kayıtlı süreler görünür, sınırlar yazılır ve kayıtla birlikte gönderilir", async () => {
    const user = userEvent.setup();
    kapi.updatePolicy.mockResolvedValue(politika({ idle_minutes: 5, admin_max_minutes: 45 }));
    ekranaBas();
    const bosta = await screen.findByLabelText("İşlem yapılmazsa kapanma süresi (dakika)");
    const mutlak = screen.getByLabelText("En uzun açık kalma süresi (dakika)");
    expect(bosta).toHaveValue("3");
    expect(mutlak).toHaveValue("30");
    expect(screen.getByText("1 ile 15 arası; en uzun süreyi aşamaz.")).toBeInTheDocument();
    expect(screen.getByText(/^5 ile 120 arası\./)).toBeInTheDocument();

    await user.clear(bosta);
    await user.type(bosta, "5");
    await user.clear(mutlak);
    await user.type(mutlak, "45");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updatePolicy).toHaveBeenCalled());
    expect(kapi.updatePolicy.mock.calls[0][0]).toMatchObject({
      idle_minutes: 5,
      admin_max_minutes: 45,
    });
  });

  it("boş bırakılan süre kayıtlı değerle gider; sunucu reddi alanda görünür", async () => {
    const user = userEvent.setup();
    kapi.updatePolicy.mockRejectedValue(
      new ApiError(400, "validation_error", "Gönderilen veride hatalar var.", {
        idle_minutes: ["Yönetici kipinin boşta süresi mutlak süresinden uzun olamaz."],
      }),
    );
    ekranaBas();
    const bosta = await screen.findByLabelText("İşlem yapılmazsa kapanma süresi (dakika)");
    await user.clear(screen.getByLabelText("En uzun açık kalma süresi (dakika)"));
    await user.clear(bosta);
    await user.type(bosta, "15");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(kapi.updatePolicy).toHaveBeenCalled());
    expect(kapi.updatePolicy.mock.calls[0][0]).toMatchObject({
      idle_minutes: 15,
      admin_max_minutes: 30,
    });
    expect(
      await screen.findByText("Yönetici kipinin boşta süresi mutlak süresinden uzun olamaz."),
    ).toBeInTheDocument();
  });
});
