import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import ModuleHeader from "./ModuleHeader";

function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route
          path="/katalog/eser"
          element={<ModuleHeader backTo="/katalog" moduleLabel="Katalog" title="Eser Ayrıntısı" />}
        />
        <Route path="/katalog" element={<div>KATALOG ANA SAYFASI</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ModuleHeader", () => {
  it("başlık ve modül adını basar", () => {
    renderAt("/katalog/eser");
    expect(screen.getByRole("heading", { name: "Eser Ayrıntısı" })).toBeInTheDocument();
    expect(screen.getByText("Katalog")).toBeInTheDocument();
  });

  it("geri butonu modül köküne gider (erişilebilir ad ile)", async () => {
    renderAt("/katalog/eser");
    const back = screen.getByRole("link", { name: "Katalog ana sayfasına dön" });
    await userEvent.click(back);
    expect(screen.getByText("KATALOG ANA SAYFASI")).toBeInTheDocument();
  });
});
