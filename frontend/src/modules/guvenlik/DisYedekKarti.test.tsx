// Genel Bakış "Şifreli Yedeği USB Belleğe Alın" kartı (F11; tasarım §16 risk 13):
// yalnız süre dolunca görünür, son indirmeyi ya da hiç indirme olmadığını söyler,
// Güvenlik sekmesine bağlanır; pano okuması kullanıcı etkinliği sayılmaz.

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("../../lib/api", () => ({ api: { get: mocks.get } }));

import DisYedekKarti, { DIS_YEDEK_KARTI_BASLIGI, GUVENLIK_ADRESI } from "./DisYedekKarti";

const TEMEL = {
  last_download: null,
  reminder_days: 30,
  days_since: 10,
  remind: true,
  min_reminder_days: 7,
  max_reminder_days: 90,
};

function bas() {
  return render(
    <MemoryRouter>
      <DisYedekKarti />
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

it("hiç indirme yoksa bunu söyler ve Güvenlik sekmesine bağlanır", async () => {
  mocks.get.mockResolvedValue(TEMEL);
  bas();

  expect(await screen.findByRole("heading", { name: DIS_YEDEK_KARTI_BASLIGI })).toBeInTheDocument();
  expect(screen.getByText("Bu bilgisayarda henüz şifreli yedek indirilmedi.")).toBeInTheDocument();
  expect(screen.getByText(/USB belleğe kopyalayın/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Güvenlik/ })).toHaveAttribute("href", GUVENLIK_ADRESI);
  // Pano okuması boşta süreyi tazelemez (tasarım §4.4).
  expect(mocks.get).toHaveBeenCalledWith("/backups/external/", { etkinlik: false });
});

it("son indirmenin tarihini gg.aa.yyyy ve gün sayısıyla yazar", async () => {
  mocks.get.mockResolvedValue({
    ...TEMEL,
    last_download: "2026-08-20T09:05:00+03:00",
    days_since: 38,
  });
  bas();

  expect(
    await screen.findByText("Son şifreli yedek 20.08.2026 tarihinde indirildi (38 gün önce)."),
  ).toBeInTheDocument();
});

it("süre dolmadıysa kart görünmez", async () => {
  mocks.get.mockResolvedValue({ ...TEMEL, remind: false });
  const { container } = bas();

  await waitFor(() => expect(mocks.get).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});

it("özet okunamazsa kart görünmez", async () => {
  mocks.get.mockRejectedValue(new Error("423"));
  const { container } = bas();

  await waitFor(() => expect(mocks.get).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});
