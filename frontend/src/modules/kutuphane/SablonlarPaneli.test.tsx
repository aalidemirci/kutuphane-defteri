// Etiketler → Şablonlar ve Kalibrasyon (F4, E1) — sabitlenen davranışlar:
//
//   1) Kalibrasyon sayfası seçilen şablon için, seçilen yazıcının O ANKİ
//      kaymasıyla (ya da kaymasız) istenir.
//   2) Cetvelde okunan değer mevcut kaymaya EKLENİR (sağa ve aşağı artı);
//      kayma ±10 mm dışındaysa istek çıkmaz. Ondalık virgülle yazılabilir.
//   3) Şablon formu adı ve ölçüleri istemcide denetler; ölçüler sunucuya SAYI
//      olarak gider. Şablon silme onaylıdır.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { hazirSablonlar, kalibrasyon } from "../../test/etiketVerileri";
import { sayfa } from "../../test/kutuphaneVerileri";
import { ConfirmProvider } from "../../ui/ConfirmProvider";
import { SnackbarProvider } from "../../ui/SnackbarProvider";

const etiket = vi.hoisted(() => ({
  kalibrasyonlar: vi.fn(),
  kalibrasyonSayfasi: vi.fn(),
  kalibrasyonOlustur: vi.fn(),
  kalibrasyonGuncelle: vi.fn(),
  kalibrasyonSil: vi.fn(),
  sablonOlustur: vi.fn(),
  sablonGuncelle: vi.fn(),
  sablonSil: vi.fn(),
}));

const indirme = vi.hoisted(() => ({ saveBlob: vi.fn() }));

vi.mock("./etiketApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./etiketApi")>();
  return { ...actual, etiketApi: { ...actual.etiketApi, ...etiket } };
});

vi.mock("../../lib/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/download")>();
  return { ...actual, saveBlob: indirme.saveBlob };
});

import SablonlarPaneli from "./SablonlarPaneli";

function ekranaBas(onDegisti = vi.fn()) {
  render(
    <SnackbarProvider>
      <ConfirmProvider>
        <SablonlarPaneli sablonlar={hazirSablonlar()} yukleniyor={false} onDegisti={onDegisti} />
      </ConfirmProvider>
    </SnackbarProvider>,
  );
  return onDegisti;
}

beforeEach(() => {
  vi.clearAllMocks();
  etiket.kalibrasyonlar.mockResolvedValue(sayfa([kalibrasyon()]));
  etiket.kalibrasyonSayfasi.mockResolvedValue(new Blob(["%PDF"]));
  etiket.kalibrasyonOlustur.mockResolvedValue(kalibrasyon({ id: 9 }));
  etiket.kalibrasyonGuncelle.mockResolvedValue(kalibrasyon());
  etiket.sablonOlustur.mockResolvedValue(hazirSablonlar()[0]);
  etiket.sablonGuncelle.mockResolvedValue(hazirSablonlar()[0]);
  etiket.sablonSil.mockResolvedValue(undefined);
});

describe("Şablonlar", () => {
  it("şablonlar ölçü ve rozetleriyle listelenir", async () => {
    ekranaBas();

    // 65'li barkod ve 65'li sırt tabakası aynı ölçüdedir.
    expect(
      screen.getAllByText("38,1 × 21,2 mm · 65 etiket (5 × 13)", { exact: false }),
    ).toHaveLength(2);
    expect(screen.getAllByText("Varsayılan")).toHaveLength(2);
    expect(screen.getByText("QR'a uygun")).toBeInTheDocument();
    await screen.findByText(/Masa yazıcısı/, { selector: "span" });
  });

  it("yeni şablon: ad ve ölçü istemcide denetlenir, ölçüler sayı olarak gider", async () => {
    const user = userEvent.setup();
    const onDegisti = ekranaBas();

    await user.click(screen.getAllByRole("button", { name: "Yeni şablon" })[0]);
    const pencere = await screen.findByRole("dialog", { name: "Yeni etiket şablonu" });
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    expect(await within(pencere).findByText("Şablona bir ad verin.")).toBeInTheDocument();

    await user.type(within(pencere).getByLabelText(/^Şablon adı/), "Sırt — 25 × 38 mm, 40'lı");
    await user.selectOptions(within(pencere).getByLabelText("Tür"), "SPINE");
    await user.type(within(pencere).getByLabelText(/^Satır sayısı/), "8");
    await user.type(within(pencere).getByLabelText(/^Sütun sayısı/), "5");
    await user.type(within(pencere).getByLabelText(/^Etiket genişliği/), "38,1");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    // Boş ölçü alanı sayı değildir.
    expect(
      await within(pencere).findByText("Milimetre olarak bir sayı yazın (ör. 38,1)."),
    ).toBeInTheDocument();

    await user.type(within(pencere).getByLabelText(/^Etiket yüksekliği/), "25");
    await user.type(within(pencere).getByLabelText(/^Üst kenar boşluğu/), "8,5");
    await user.type(within(pencere).getByLabelText(/^Sol kenar boşluğu/), "4.75");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(etiket.sablonOlustur).toHaveBeenCalledTimes(1));
    expect(etiket.sablonOlustur.mock.calls[0][0]).toEqual({
      name: "Sırt — 25 × 38 mm, 40'lı",
      kind: "SPINE",
      label_width: 38.1,
      label_height: 25,
      page_margin_top: 8.5,
      page_margin_left: 4.75,
      gutter_x: 0,
      gutter_y: 0,
      rows: 8,
      cols: 5,
      is_default: false,
    });
    expect(onDegisti).toHaveBeenCalled();
  });

  it("şablon düzenleme mevcut ölçülerle açılır", async () => {
    const user = userEvent.setup();
    ekranaBas();

    await user.click(screen.getAllByRole("button", { name: "Düzenle" })[0]);
    const pencere = await screen.findByRole("dialog", { name: "Şablonu düzenle" });
    expect(within(pencere).getByLabelText(/^Etiket genişliği/)).toHaveValue("38,1");
    expect(within(pencere).getByLabelText(/^Sol kenar boşluğu/)).toHaveValue("4,75");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(etiket.sablonGuncelle).toHaveBeenCalledTimes(1));
    expect(etiket.sablonGuncelle.mock.calls[0][0]).toBe(1);
  });

  it("şablon silme onaylıdır", async () => {
    const user = userEvent.setup();
    const onDegisti = ekranaBas();

    await user.click(screen.getAllByRole("button", { name: "Sil" })[0]);
    const pencere = await screen.findByRole("dialog", {
      name: "“Barkod etiketi — 38,1 × 21,2 mm, 65'li” silinsin mi?",
    });
    expect(within(pencere).getByText(/kalibrasyonları da silinir/)).toBeInTheDocument();
    await user.click(within(pencere).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(etiket.sablonSil).toHaveBeenCalledWith(1));
    expect(onDegisti).toHaveBeenCalled();
  });
});

describe("Kalibrasyon", () => {
  it("kalibrasyon sayfası seçilen yazıcının kaymasıyla ya da kaymasız istenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText("Yazıcı Kalibrasyonu: Barkod etiketi — 38,1 × 21,2 mm, 65'li");

    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(etiket.kalibrasyonSayfasi).toHaveBeenCalledWith(1, null));
    expect(indirme.saveBlob.mock.calls[0][1]).toMatch(/^Kalibrasyon-Sayfası_/);

    await screen.findByText(/Masa yazıcısı/, { selector: "span" });
    await user.selectOptions(screen.getByLabelText("Sayfaya uygulanacak kayma"), "8");
    await user.click(screen.getByRole("button", { name: "PDF'i indir" }));
    await waitFor(() => expect(etiket.kalibrasyonSayfasi).toHaveBeenLastCalledWith(1, 8));
  });

  it("başka şablonun kalibrasyonu seçilince o şablonun yazıcıları istenir", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await waitFor(() => expect(etiket.kalibrasyonlar).toHaveBeenCalledWith(1));

    await user.click(screen.getAllByRole("button", { name: "Kalibrasyon" })[1]);

    await waitFor(() => expect(etiket.kalibrasyonlar).toHaveBeenCalledWith(2));
  });

  it("cetvelde okunan değer kaymaya eklenir; kayıt sayı olarak gider", async () => {
    const user = userEvent.setup();
    etiket.kalibrasyonlar.mockResolvedValue(sayfa([]));
    ekranaBas();
    await screen.findByText(/kayıtlı yazıcı yok/);

    await user.click(screen.getByRole("button", { name: "Yeni yazıcı kalibrasyonu" }));
    const pencere = await screen.findByRole("dialog", { name: "Yeni yazıcı kalibrasyonu" });
    await user.type(within(pencere).getByLabelText(/^Yazıcı adı/), "Kütüphane lazer yazıcısı");
    await user.type(within(pencere).getByLabelText("Okunan yatay değer"), "1,5");
    await user.type(within(pencere).getByLabelText("Okunan dikey değer"), "-0,5");
    await user.click(within(pencere).getByRole("button", { name: "Kaymaya ekle" }));
    expect(within(pencere).getByLabelText("Yatay kayma (mm)")).toHaveValue("1,5");
    expect(within(pencere).getByLabelText("Dikey kayma (mm)")).toHaveValue("-0,5");

    // İkinci ölçüm üst üste eklenir.
    await user.type(within(pencere).getByLabelText("Okunan yatay değer"), "0,25");
    await user.click(within(pencere).getByRole("button", { name: "Kaymaya ekle" }));
    expect(within(pencere).getByLabelText("Yatay kayma (mm)")).toHaveValue("1,75");

    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(etiket.kalibrasyonOlustur).toHaveBeenCalledWith({
        template: 1,
        printer_name: "Kütüphane lazer yazıcısı",
        offset_x: 1.75,
        offset_y: -0.5,
      }),
    );
  });

  it("sınır dışı kayma ve boş yazıcı adı istemcide durur", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText(/Masa yazıcısı/, { selector: "span" });

    await user.click(screen.getAllByRole("button", { name: "Düzenle" }).at(-1) as HTMLElement);
    const pencere = await screen.findByRole("dialog", { name: "Kalibrasyonu düzenle" });
    expect(within(pencere).getByLabelText("Yatay kayma (mm)")).toHaveValue("1,5");

    await user.clear(within(pencere).getByLabelText("Yatay kayma (mm)"));
    await user.type(within(pencere).getByLabelText("Yatay kayma (mm)"), "12");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    expect(
      await within(pencere).findByText("-10 ile 10 mm arasında bir sayı yazın."),
    ).toBeInTheDocument();

    await user.clear(within(pencere).getByLabelText(/^Yazıcı adı/));
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    expect(await within(pencere).findByText("Yazıcının adını yazın.")).toBeInTheDocument();
    expect(etiket.kalibrasyonGuncelle).not.toHaveBeenCalled();

    await user.type(within(pencere).getByLabelText(/^Yazıcı adı/), "Masa yazıcısı");
    await user.clear(within(pencere).getByLabelText("Yatay kayma (mm)"));
    await user.type(within(pencere).getByLabelText("Yatay kayma (mm)"), "2");
    await user.click(within(pencere).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(etiket.kalibrasyonGuncelle).toHaveBeenCalledWith(8, {
        template: 1,
        printer_name: "Masa yazıcısı",
        offset_x: 2,
        offset_y: -0.5,
      }),
    );
  });

  it("kalibrasyon silme onaylıdır", async () => {
    const user = userEvent.setup();
    ekranaBas();
    await screen.findByText(/Masa yazıcısı/, { selector: "span" });

    await user.click(screen.getAllByRole("button", { name: "Sil" }).at(-1) as HTMLElement);
    const pencere = await screen.findByRole("dialog", {
      name: "“Masa yazıcısı” kalibrasyonu silinsin mi?",
    });
    await user.click(within(pencere).getByRole("button", { name: "Sil" }));

    await waitFor(() => expect(etiket.kalibrasyonSil).toHaveBeenCalledWith(8));
  });
});
