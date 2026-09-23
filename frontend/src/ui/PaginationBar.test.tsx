// Sayfalama çubuğu: aralık metni, uçlardaki kapalı düğmeler ve offset hesabı.
// Sayfalama SUNUCUDADIR; çubuk yalnız yeni offset'i bildirir.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PaginationBar from "./PaginationBar";

describe("PaginationBar", () => {
  it("görüntülenen aralığı ve toplamı Türkçe biçimde yazar", () => {
    render(<PaginationBar count={1234} offset={25} pageSize={25} onOffset={vi.fn()} />);
    expect(screen.getByText("26–50 / 1.234 kayıt")).toBeInTheDocument();
  });

  it("kayıt yokken aralık sıfırdan başlar ve iki düğme de kapalıdır", () => {
    render(<PaginationBar count={0} offset={0} pageSize={25} onOffset={vi.fn()} />);
    expect(screen.getByText("0–0 / 0 kayıt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Önceki/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Sonraki/ })).toBeDisabled();
  });

  it("son sayfada 'Sonraki' kapalıdır, aralık toplamda biter", () => {
    render(<PaginationBar count={30} offset={25} pageSize={25} onOffset={vi.fn()} />);
    expect(screen.getByText("26–30 / 30 kayıt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sonraki/ })).toBeDisabled();
  });

  it("düğmeler bir sonraki ve bir önceki offset'i bildirir", async () => {
    const user = userEvent.setup();
    const onOffset = vi.fn();
    render(<PaginationBar count={100} offset={25} pageSize={25} onOffset={onOffset} />);

    await user.click(screen.getByRole("button", { name: /Sonraki/ }));
    expect(onOffset).toHaveBeenLastCalledWith(50);

    await user.click(screen.getByRole("button", { name: /Önceki/ }));
    expect(onOffset).toHaveBeenLastCalledWith(0);
  });
});
