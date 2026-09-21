// Kullanım Kılavuzu testleri: kabuk (başlık üçlüsü) yerinde, içerik şimdilik
// kısa bir yer tutucudur (tasarım §12: içerik yeniden yazılır). Bölümler
// özelliklerle birlikte eklendikçe her bölümün metni burada kilitlenir —
// özellik kılavuzda ANLATILMADAN sürüme girmesin (§14.1).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import KilavuzPage from "./KilavuzPage";

describe("KilavuzPage", () => {
  it("kabuğu ve yer tutucu metni gösterir", () => {
    render(<KilavuzPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Kullanım Kılavuzu" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Kütüphane Defteri")).toBeInTheDocument();
    expect(screen.getByText(/Kılavuz, özellikler geldikçe yazılacak\./)).toBeInTheDocument();
  });

  it("başka programın kılavuz içeriği taşınmadı", () => {
    render(<KilavuzPage />);

    // Tek bölüm: yer tutucu. Sınav/salon/ders havuzu anlatımı kalmadı.
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
    for (const kalinti of [/sınav/i, /salon/i, /ders havuzu/i, /zümre/i]) {
      expect(screen.queryByText(kalinti)).not.toBeInTheDocument();
    }
  });
});
