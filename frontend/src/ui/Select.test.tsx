// Select — yerel <select> üzerinde etiket bağı, yer tutucu ve hata duyurusu.
// TextField ile AYNI erişilebilirlik sözleşmesini taşır (hata `role="alert"`).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import Select from "./Select";

const DURUMLAR = [
  { value: "AVAILABLE", label: "Rafta" },
  { value: "ON_LOAN", label: "Ödünçte" },
];

describe("Select", () => {
  it("seçenekleri listeler ve seçim onChange'e ulaşır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Select label="Nüsha durumu" options={DURUMLAR} value="AVAILABLE" onChange={onChange} />,
    );

    await user.selectOptions(screen.getByLabelText("Nüsha durumu"), "ON_LOAN");

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("yer tutucu boş değerli ilk seçenektir; verilmezse basılmaz", () => {
    const { rerender } = render(
      <Select label="Durum" options={DURUMLAR} placeholder="Seçin" defaultValue="" />,
    );

    const secenekler = screen.getAllByRole("option") as HTMLOptionElement[];
    expect(secenekler[0]).toHaveTextContent("Seçin");
    expect(secenekler[0].value).toBe("");

    rerender(<Select label="Durum" options={DURUMLAR} defaultValue="AVAILABLE" />);
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("hata metni alert olarak duyurulur ve alana bağlanır", () => {
    render(<Select label="Dönem" options={DURUMLAR} error="Dönem seçin." defaultValue="" />);

    const alan = screen.getByLabelText("Dönem");
    const hata = screen.getByRole("alert");
    expect(hata).toHaveTextContent("Dönem seçin.");
    expect(alan).toHaveAttribute("aria-invalid", "true");
    expect(alan).toHaveAttribute("aria-describedby", hata.id);
  });

  it("yardımcı metin duyurulmaz", () => {
    render(
      <Select label="Tür" options={DURUMLAR} helperText="Sonradan değişmez." defaultValue="" />,
    );

    expect(screen.getByText("Sonradan değişmez.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
