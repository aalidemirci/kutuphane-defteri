// Başlangıç Yol Haritası kartı: maddeler (sözlük), kendiliğinden tespit edilen
// maddeler (setup/status sayıları), her maddenin ilgili sayfaya bağlanması.

import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { KURULU_DURUM } from "../../test/kurulumDurumu";
import { SnackbarProvider } from "../../ui/SnackbarProvider";
import type { SetupStatus } from "../okul/api";
import BaslangicYolHaritasi, { YOL_HARITASI_MADDELERI, maddeTamamMi } from "./BaslangicYolHaritasi";

function bas(durum: SetupStatus = KURULU_DURUM) {
  return render(
    <MemoryRouter>
      <SnackbarProvider>
        <BaslangicYolHaritasi durum={durum} onIsaretle={vi.fn()} onGizle={vi.fn()} />
      </SnackbarProvider>
    </MemoryRouter>,
  );
}

function madde(metin: RegExp): HTMLElement {
  const li = screen.getByText(metin).closest("li");
  if (!li) throw new Error("madde bulunamadı");
  return li;
}

describe("BaslangicYolHaritasi", () => {
  it("sözleşmedeki yedi madde bu sırayla durur", () => {
    expect(YOL_HARITASI_MADDELERI.map((m) => m.anahtar)).toEqual([
      "ogrenci_aktarimi",
      "personel_aktarimi",
      "kapali_gunler",
      "katalog_sablonu",
      "kurtarma_zarfi",
      "parola_paylasimi",
      "btr_gorusmesi",
    ]);
  });

  it("kendiliğinden tespit edilen maddeler sayılardan, diğerleri işaretten okunur", () => {
    const durum: SetupStatus = {
      ...KURULU_DURUM,
      student_count: 3,
      personnel_count: 0,
      school_break_count: 1,
      roadmap: { marks: { parola_paylasimi: "2026-09-22" }, hidden: false },
    };
    expect(maddeTamamMi("ogrenci_aktarimi", durum)).toBe(true);
    expect(maddeTamamMi("personel_aktarimi", durum)).toBe(false);
    expect(maddeTamamMi("kapali_gunler", durum)).toBe(true);
    expect(maddeTamamMi("parola_paylasimi", durum)).toBe(true);
    expect(maddeTamamMi("kurtarma_zarfi", durum)).toBe(false);
  });

  it("her madde ilgili sayfaya bağlanır", () => {
    bas();
    const bag = (metin: RegExp) => within(madde(metin)).getByRole("link");
    expect(bag(/e-Okul öğrenci listesini aktarın/)).toHaveAttribute("href", "/kisiler");
    expect(bag(/Öğretmen ve diğer personel listesini aktarın/)).toHaveAttribute(
      "href",
      "/kisiler?tab=personel",
    );
    expect(bag(/Öğrenciye kapalı günleri girin/)).toHaveAttribute(
      "href",
      "/ayarlar?tab=kapali-gunler",
    );
    expect(bag(/Kurtarma anahtarını müdürlükte kapalı zarfta saklayın/)).toHaveAttribute(
      "href",
      "/ayarlar?tab=guvenlik",
    );
    expect(bag(/Yönetici parolasını en az iki görevlendirilmiş kişiyle paylaşın/)).toHaveAttribute(
      "href",
      "/ayarlar?tab=guvenlik",
    );
    expect(bag(/bilişim teknolojileri rehber öğretmeniyle \(BTR\)/)).toHaveAttribute(
      "href",
      "/kilavuz",
    );
    // Şablon maddesi bir sayfaya değil, şablon indirme işlevine bağlanır.
    expect(
      within(madde(/Katalog Excel şablonunu indirip/)).getByRole("button", {
        name: /Şablonu indir/,
      }),
    ).toBeInTheDocument();
  });

  it("kendiliğinden tespit edilen maddelerde işaret kutusu yoktur", () => {
    bas();
    expect(within(madde(/e-Okul öğrenci listesini aktarın/)).queryByRole("checkbox")).toBeNull();
    expect(
      within(madde(/e-Okul öğrenci listesini aktarın/)).getByText(
        "Yapıldığında kendiliğinden işaretlenir.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(4);
  });

  it("aktarımlar yapılınca maddeler tamamlandı olarak görünür", () => {
    bas({ ...KURULU_DURUM, student_count: 480, personnel_count: 36 });
    expect(
      within(madde(/e-Okul öğrenci listesini aktarın/)).getByText(/tamamlandı/),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
  });

  it("iç kodlar kullanıcı metnine girmez; yerel araç dili korunur", () => {
    const { container } = bas();
    expect(container.textContent).not.toMatch(/\b(F1|U10|E14|T5|KM-|OPAC)\b/);
    expect(container.textContent).not.toMatch(/otomasyon sistemi/i);
  });
});
