// Hakkında sayfası testleri: üst yazı, konum notu (tasarım §3 — program
// "yerel araç"tır, Bakanlık otomasyon sistemindeki kaydın yerine geçmez),
// şifreleme yöntemi adlarının YALNIZ bu sayfada geçmesi (docs/sozluk.md §1 —
// ayar ekranları "güçlü şifrelemeyle korunur" der) ve dış isteğin yalnız elle
// güncelleme denetimi olduğu (tasarım T11).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HakkindaPage from "./HakkindaPage";

describe("HakkindaPage", () => {
  it("üst yazı konumu, geliştiriciyi, iletişim bilgilerini ve kullanım koşullarını sayar", () => {
    render(<HakkindaPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Hakkında ve Lisans" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Programın konumu, geliştiricisi, iletişim bilgileri ve kullanım koşulları.",
      ),
    ).toBeInTheDocument();
  });

  it("konum notu: yerel araçtır, Bakanlık otomasyon sistemindeki kaydın yerine geçmez", () => {
    render(<HakkindaPage />);

    expect(screen.getByRole("heading", { level: 2, name: "Program" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Program okulun kütüphane işlerini yürüttüğü yerel araçtır; Bakanlıkça belirlenen otomasyon sistemindeki kaydın yerine geçmez.",
      ),
    ).toBeInTheDocument();
    // Program kendine "otomasyon sistemi" adını vermez (docs/sozluk.md §1).
    expect(screen.queryByText(/kütüphane otomasyon sistemi/i)).not.toBeInTheDocument();
  });

  it("teknik bilgiler kartı şifreleme yöntemlerini adıyla verir; fotoğraf şifrelemesi anlatılmaz", () => {
    render(<HakkindaPage />);

    expect(screen.getByRole("heading", { level: 2, name: "Teknik Bilgiler" })).toBeInTheDocument();
    expect(screen.getByText(/X25519 ve AES-256-GCM/)).toBeInTheDocument();
    expect(screen.getByText(/Argon2id/)).toBeInTheDocument();
    expect(screen.queryByText(/fotoğraf/i)).not.toBeInTheDocument();
  });

  it("dış isteğin iki kapıdan çıktığını söyler (açılışta istek yok, ISBN sorgusu kapalı)", () => {
    render(<HakkindaPage />);

    expect(screen.getByText(/Program açılışta internete çıkmaz\./)).toBeInTheDocument();
    expect(screen.getByText(/“Şimdi denetle” düğmesine bastığınızda/)).toBeInTheDocument();
    // U13 (tasarım §8.5): ikinci kapı ve varsayılan kapalı olduğu yazılı olmalı.
    expect(screen.getByText(/ISBN sorgusu/)).toBeInTheDocument();
    expect(screen.getByText(/varsayılan olarak kapalıdır/)).toBeInTheDocument();
    expect(screen.getByText(/kişisel veri dışarı çıkmaz/)).toBeInTheDocument();
  });
});
