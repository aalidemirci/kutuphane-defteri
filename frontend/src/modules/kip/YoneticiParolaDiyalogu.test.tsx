// Yönetici kipine geçiş diyaloğu: parola yalnız gövdede gider; yanlış parolada
// sunucunun iletisi ("Parola hatalı.") alanın altında görünür ve diyalog açık
// kalır; Vazgeç alanı temizler.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../lib/api";
import type { KipOzeti } from "./api";

const kip = vi.hoisted(() => ({
  durum: vi.fn(),
  gorevliyeGec: vi.fn(),
  yoneticiyeGec: vi.fn(),
  kilitle: vi.fn(),
}));

vi.mock("./api", () => ({ kipApi: kip }));

import YoneticiParolaDiyalogu from "./YoneticiParolaDiyalogu";

const YONETICI: KipOzeti = {
  durum: "yonetici",
  bosta_kalan_sn: 180,
  mutlak_kalan_sn: 1800,
  bosta_dk: 3,
  mutlak_dk: 30,
};

function bas(open = true) {
  const onClose = vi.fn();
  const onGecti = vi.fn();
  const sonuc = render(<YoneticiParolaDiyalogu open={open} onClose={onClose} onGecti={onGecti} />);
  return { ...sonuc, onClose, onGecti };
}

describe("YoneticiParolaDiyalogu", () => {
  beforeEach(() => vi.clearAllMocks());

  it("kapalıyken hiçbir şey göstermez", () => {
    bas(false);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  // `autoFocus` ortak Dialog'un panel odağına yeniliyordu; parola alanı
  // `initialFocusRef` ile odaklanır (tasarım §14.1 F6 ekleri 23).
  it("açılışta parola alanı odaktadır", () => {
    bas();
    expect(screen.getByLabelText(/Yönetici parolası/)).toHaveFocus();
  });

  it("parola girilmeden gönderme düğmesi kapalıdır", () => {
    bas();
    expect(screen.getByRole("button", { name: "Yönetici kipine geç" })).toBeDisabled();
    expect(screen.getByLabelText(/Yönetici parolası/)).toHaveAttribute("type", "password");
  });

  it("yanlış parolada iletiyi gösterir, diyalog açık kalır", async () => {
    const kullanici = userEvent.setup();
    kip.yoneticiyeGec.mockRejectedValue(new ApiError(400, "validation_error", "Parola hatalı."));
    const { onClose, onGecti } = bas();

    await kullanici.type(screen.getByLabelText(/Yönetici parolası/), "yanlis-parola");
    await kullanici.click(screen.getByRole("button", { name: "Yönetici kipine geç" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Parola hatalı.");
    expect(onGecti).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("doğru parolada yeni özeti bildirir ve kapanır (Enter ile gönderim)", async () => {
    const kullanici = userEvent.setup();
    kip.yoneticiyeGec.mockResolvedValue(YONETICI);
    const { onClose, onGecti } = bas();

    await kullanici.type(screen.getByLabelText(/Yönetici parolası/), "Dogru-Parola-1{Enter}");

    expect(kip.yoneticiyeGec).toHaveBeenCalledWith("Dogru-Parola-1");
    expect(onGecti).toHaveBeenCalledWith(YONETICI);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("beklenmeyen hatada genel ileti gösterilir", async () => {
    const kullanici = userEvent.setup();
    kip.yoneticiyeGec.mockRejectedValue("?");
    bas();

    await kullanici.type(screen.getByLabelText(/Yönetici parolası/), "x{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("Yönetici kipine geçilemedi.");
  });

  it("Vazgeç diyaloğu kapatır ve alanı temizler", async () => {
    const kullanici = userEvent.setup();
    const { onClose, rerender } = bas();
    await kullanici.type(screen.getByLabelText(/Yönetici parolası/), "yarim");

    await kullanici.click(screen.getByRole("button", { name: "Vazgeç" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    rerender(<YoneticiParolaDiyalogu open onClose={onClose} onGecti={vi.fn()} />);
    expect(screen.getByLabelText(/Yönetici parolası/)).toHaveValue("");
  });
});
