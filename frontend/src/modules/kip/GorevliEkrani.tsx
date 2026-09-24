// Görevli kipinin ana ekranı (U5, tasarım §4.4). Görevli kipinde rotaların
// YERİNE gösterilir: masadaki görevli yönetici ekranlarına (kişiler, ayarlar,
// yedek…) ulaşamaz. Backend bunu ayrıca keser (403 `kip_yetkisiz`); bu ekran
// kullanıcıya boş ya da hata dolu sayfalar yerine ne yapacağını söyler.
//
// Görevli kipinde TEK ekrandır (F6): varsayılan iş DOLAŞIM MASASIdır (§7.3 —
// kartla üye çözme, ödünç ver, barkodla iade, nüsha durum sorgusu). Görevliye açık
// öbür iki masa işi buradan açılır ve masanın yerine geçer (iki okutma kutusu aynı
// anda odak için yarışmasın):
//   * etiket doğrulama okutması (kullanıcı kararı 24.09.2026) — sunucu görevli
//     kipinde yalnız `POST library/labels/verify/` ucunu geçirir ve nüsha özetinden
//     yalnız barkodu ve eser adını döndürür;
//   * katalogda arama — künye ve nüsha durumu (Ağ Kataloğunun alanlarına denk).
// Etiketler sayfasının öbür sekmeleri, "Doğrulanmamış Etiketler" listesi, üye
// listesi, ödünç geçmişi, gecikme listesi, gerekçeli istisna ve kartsız ödünç
// yönetici kipindedir. Sayfanın h1'i her görünümde "Görevli Kipi"dir (üst çubukla
// aynı — docs/sozluk.md §4); iş bölüm başlığıdır.

import { useState } from "react";

import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import DolasimMasasi from "../dolasim/DolasimMasasi";
import KatalogArama, { KATALOG_ARAMA_BASLIGI } from "../dolasim/KatalogArama";
import DogrulamaOkutmasi from "../kutuphane/DogrulamaOkutmasi";
import YoneticiParolaDiyalogu from "./YoneticiParolaDiyalogu";
import type { KipOzeti } from "./api";

/** Üst çubuk başlığı sayfanın h1'iyle aynıdır (docs/sozluk.md §4). */
export const GOREVLI_EKRANI_BASLIGI = "Görevli Kipi";

export const GOREVLI_EKRANI_METNI =
  "Bu kipte yalnız masa işleri yapılır; yönetici işlemleri için yönetici kipine geçin.";

/** Görevli ekranının varsayılan işi (bölüm başlığı; yönetici sayfasının adıyla aynı). */
export const GOREVLI_MASA_BASLIGI = "Dolaşım Masası";
/** Görevli ekranından açılan doğrulama okutmasının bölüm başlığı (Etiketler'deki sekme adı). */
export const GOREVLI_DOGRULAMA_BASLIGI = "Doğrulama Okutması";
/** Doğrulama okutmasını açan ve kapatan düğmeler (kılavuz bu adlarla anlatır). */
export const GOREVLI_DOGRULAMA_DUGMESI = "Doğrulama okutmasını aç";
export const GOREVLI_DOGRULAMA_BITIR = "Okutmayı bitir";
export const GOREVLI_KATALOG_DUGMESI = "Katalogda ara";
export const GOREVLI_MASAYA_DON = "Dolaşım masasına dön";

/**
 * Kurtarma anahtarı (kurulumda verilen ya da Ayarlar → Güvenlik'te yenilenen)
 * doğrulanmadan görevli kipine geçilirse (düğme, kısayol) gösterilir: anahtar
 * kaybolmadı, yönetici kipine dönülünce anahtarın gösterildiği ekran onu yeniden
 * gösterir (`guvenlik/bekleyenAnahtar`). Kurulum sürerken süreler kipi düşürmez.
 */
export const BEKLEYEN_ANAHTAR_METNI =
  "Kurtarma anahtarınız henüz doğrulanmadı. Yönetici kipine geçtiğinizde anahtar yeniden gösterilir; programı kapatmayın.";

function BekleyenAnahtarUyarisi() {
  return (
    <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-left text-body-medium text-on-tertiary-container">
      <Icon name="key" size="lg" />
      <span>{BEKLEYEN_ANAHTAR_METNI}</span>
    </p>
  );
}

type Gorunum = "masa" | "dogrulama" | "katalog";

const BOLUM: Record<Gorunum, { baslik: string; ikon: string }> = {
  masa: { baslik: GOREVLI_MASA_BASLIGI, ikon: "sync_alt" },
  dogrulama: { baslik: GOREVLI_DOGRULAMA_BASLIGI, ikon: "barcode_reader" },
  katalog: { baslik: KATALOG_ARAMA_BASLIGI, ikon: "search" },
};

export default function GorevliEkrani({
  onGecti,
  anahtarBekliyor = false,
}: {
  onGecti: (ozet: KipOzeti) => void;
  /** Kurulumda doğrulanmamış kurtarma anahtarı bellekte bekliyor mu? */
  anahtarBekliyor?: boolean;
}) {
  const [diyalogAcik, setDiyalogAcik] = useState(false);
  const [gorunum, setGorunum] = useState<Gorunum>("masa");

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-headline-small text-on-surface">{GOREVLI_EKRANI_BASLIGI}</h1>
          <p className="mt-1 text-body-medium text-on-surface-variant">{GOREVLI_EKRANI_METNI}</p>
          <h2 className="mt-3 flex items-center gap-2 text-title-large text-on-surface">
            <Icon name={BOLUM[gorunum].ikon} size="lg" className="text-primary" />
            {BOLUM[gorunum].baslik}
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {gorunum === "masa" ? (
            <>
              <Button
                variant="outlined"
                icon="barcode_reader"
                onClick={() => setGorunum("dogrulama")}
              >
                {GOREVLI_DOGRULAMA_DUGMESI}
              </Button>
              <Button variant="outlined" icon="search" onClick={() => setGorunum("katalog")}>
                {GOREVLI_KATALOG_DUGMESI}
              </Button>
            </>
          ) : (
            <Button variant="outlined" icon="arrow_back" onClick={() => setGorunum("masa")}>
              {gorunum === "dogrulama" ? GOREVLI_DOGRULAMA_BITIR : GOREVLI_MASAYA_DON}
            </Button>
          )}
          <Button icon="admin_panel_settings" onClick={() => setDiyalogAcik(true)}>
            Yönetici kipine geç
          </Button>
        </div>
      </div>
      {anahtarBekliyor && <BekleyenAnahtarUyarisi />}
      {gorunum === "masa" && <DolasimMasasi gorevli beklemede={diyalogAcik} />}
      {gorunum === "dogrulama" && <DogrulamaOkutmasi gorevli />}
      {gorunum === "katalog" && <KatalogArama />}
      <YoneticiParolaDiyalogu
        open={diyalogAcik}
        onClose={() => setDiyalogAcik(false)}
        onGecti={onGecti}
      />
    </div>
  );
}
