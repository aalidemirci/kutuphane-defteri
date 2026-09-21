// TextField — etiket/alan bağı, zorunlu işareti ve hata duyurusu. Formların
// tamamı bu bileşenden geçtiği için erişilebilirlik sözleşmesi burada sabitlenir:
// hata metni `role="alert"` ile BELİRDİĞİ anda duyurulur ve alana
// `aria-describedby` ile bağlanır; yardımcı metin statiktir, duyurulmaz.

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TextField from "./TextField";

describe("TextField", () => {
  it("etiket alana bağlıdır ve yazılan değer onChange'e ulaşır", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TextField label="Eser adı" value="" onChange={onChange} />);

    await user.type(screen.getByLabelText("Eser adı"), "A");

    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("zorunlu alanda yıldız gösterir ve alanı required işaretler", () => {
    render(<TextField label="Kayıt no" required defaultValue="" />);

    expect(screen.getByText("*")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeRequired();
  });

  it("hata metni alert olarak duyurulur ve alana bağlanır", () => {
    render(
      <TextField label="Nüsha sayısı" error="Nüsha sayısı 1-50 arasında olmalı." defaultValue="" />,
    );

    const alan = screen.getByLabelText("Nüsha sayısı");
    const hata = screen.getByRole("alert");
    expect(hata).toHaveTextContent("Nüsha sayısı 1-50 arasında olmalı.");
    expect(alan).toHaveAttribute("aria-invalid", "true");
    expect(alan).toHaveAttribute("aria-describedby", hata.id);
  });

  it("yardımcı metin duyurulmaz ama alana bağlanır; hata varsa yerini hataya bırakır", () => {
    const { rerender } = render(
      <TextField label="Eski kayıt no" helperText="İsteğe bağlıdır." defaultValue="" />,
    );

    const yardim = screen.getByText("İsteğe bağlıdır.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Eski kayıt no")).toHaveAttribute("aria-describedby", yardim.id);
    expect(screen.getByLabelText("Eski kayıt no")).not.toHaveAttribute("aria-invalid");

    rerender(
      <TextField
        label="Eski kayıt no"
        helperText="İsteğe bağlıdır."
        error="Sayı girin."
        defaultValue=""
      />,
    );

    expect(screen.queryByText("İsteğe bağlıdır.")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Sayı girin.");
  });

  it("boş etiketle <label> basmaz; erişilebilir ad aria-label'dan gelir", () => {
    const { container } = render(<TextField label="" aria-label="Öğrenci ara" defaultValue="" />);

    expect(container.querySelector("label")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Öğrenci ara" })).toBeInTheDocument();
  });
});
