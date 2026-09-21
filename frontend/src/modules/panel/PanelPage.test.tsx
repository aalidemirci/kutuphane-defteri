// Genel Bakış: gezinme kartları ve "Katalog Excel Şablonu" indirme kartı.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { SnackbarProvider } from "../../ui/SnackbarProvider";
import PanelPage from "./PanelPage";

function bas() {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <PanelPage />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

it("sayfanın tek adı Genel Bakış'tır; gezinme kartları sayfalarına gider", () => {
  bas();

  expect(screen.getByRole("heading", { level: 1, name: "Genel Bakış" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Kişiler/ })).toHaveAttribute("href", "/kisiler");
  expect(screen.getByRole("link", { name: /Ayarlar/ })).toHaveAttribute("href", "/ayarlar");
});

it("Katalog Excel Şablonu kartı indirme düğmesiyle görünür (bir sayfaya gitmez)", () => {
  bas();

  expect(screen.getByRole("heading", { name: "Katalog Excel Şablonu" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Şablonu indir/ })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Katalog Excel Şablonu/ })).not.toBeInTheDocument();
});
