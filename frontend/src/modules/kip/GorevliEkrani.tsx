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
//   * katalogda arama — künye ve nüsha durumu (Ağ Kataloğunun alanlarına denk);
//   * teslimden geri alma okutması (F7, §4.4 "Teslimden geri alma okutması" açık) —
//     sınıf kitaplığından ya da öğretmenden dönen kitaplar okutulur; sunucu teslim
//     alanın kimliğini göndermez. Teslim VERME ve teslim listeleri yönetici kipindedir;
//   * sayım okutması (F9 — madde 24, 25.09.2026 kullanıcı kararı): düğme YALNIZ okutması
//     açık süren bir sayım varken görünür (masanın kişisiz durumu — `library-desk-state`).
//     Sunucu sayım uçlarından yalnız okutmayı geçirir; yanıt sonuç, ileti, barkod ve eser
//     adıdır. Sayımı başlatmak, tamamlamak ve onaylamak yönetici işidir.
// Etiketler sayfasının öbür sekmeleri, "Doğrulanmamış Etiketler" listesi, üye
// listesi, ödünç geçmişi, gecikme listesi, gerekçeli istisna ve kartsız ödünç
// yönetici kipindedir. Sayfanın h1'i her görünümde "Görevli Kipi"dir (üst çubukla
// aynı — docs/sozluk.md §4); iş bölüm başlığıdır.

import { useState } from "react";

import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import DolasimMasasi from "../dolasim/DolasimMasasi";
import KatalogArama, { KATALOG_ARAMA_BASLIGI } from "../dolasim/KatalogArama";
import { useMasaDurumu } from "../dolasim/masaDurumu";
import DogrulamaOkutmasi from "../kutuphane/DogrulamaOkutmasi";
import GorevliSayimOkutmasi from "../sayim/GorevliSayimOkutmasi";
import GeriAlmaOkutmasi from "../teslim/GeriAlmaOkutmasi";
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
/** Görevli ekranından açılan teslimden geri alma okutmasının bölüm başlığı ve düğmesi (F7). */
export const GOREVLI_GERI_ALMA_BASLIGI = "Teslimden Geri Alma";
export const GOREVLI_GERI_ALMA_DUGMESI = "Teslimden geri al";
/** Görevli ekranından açılan sayım okutmasının bölüm başlığı ve düğmesi (F9 — madde 24). */
export const GOREVLI_SAYIM_BASLIGI = "Sayım Okutması";
export const GOREVLI_SAYIM_DUGMESI = "Sayım okutmasını aç";
/** Okutma sürerken sayım tamamlandı ya da iptal edildi (masa durumu artık süren sayım demez). */
export const SAYIM_OKUTMASI_KAPANDI =
  "Süren sayım yok: okutma kapandı. Dolaşım masasına dönmek için “Okutmayı bitir”e basın.";

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

type Gorunum = "masa" | "dogrulama" | "katalog" | "geriAlma" | "sayim";

const BOLUM: Record<Gorunum, { baslik: string; ikon: string }> = {
  masa: { baslik: GOREVLI_MASA_BASLIGI, ikon: "sync_alt" },
  dogrulama: { baslik: GOREVLI_DOGRULAMA_BASLIGI, ikon: "barcode_reader" },
  katalog: { baslik: KATALOG_ARAMA_BASLIGI, ikon: "search" },
  geriAlma: { baslik: GOREVLI_GERI_ALMA_BASLIGI, ikon: "move_to_inbox" },
  sayim: { baslik: GOREVLI_SAYIM_BASLIGI, ikon: "inventory_2" },
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
  // Okutması açık süren sayım (kişisiz: kimlik ve tur). Sayım okutma sürerken tamamlanırsa
  // sunucu okutmayı reddeder ("Okutma yalnız süren sayımda yapılır."); düğme bir sonraki
  // okumada kalkar.
  const surenSayim = useMasaDurumu()?.stocktake_scan ?? null;

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
              <Button
                variant="outlined"
                icon="move_to_inbox"
                onClick={() => setGorunum("geriAlma")}
              >
                {GOREVLI_GERI_ALMA_DUGMESI}
              </Button>
              {surenSayim !== null && (
                <Button variant="outlined" icon="inventory_2" onClick={() => setGorunum("sayim")}>
                  {GOREVLI_SAYIM_DUGMESI}
                </Button>
              )}
            </>
          ) : (
            <Button variant="outlined" icon="arrow_back" onClick={() => setGorunum("masa")}>
              {gorunum === "dogrulama" || gorunum === "geriAlma" || gorunum === "sayim"
                ? GOREVLI_DOGRULAMA_BITIR
                : GOREVLI_MASAYA_DON}
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
      {gorunum === "geriAlma" && <GeriAlmaOkutmasi gorevli beklemede={diyalogAcik} />}
      {gorunum === "sayim" &&
        (surenSayim !== null ? (
          <GorevliSayimOkutmasi
            sayimId={surenSayim.id}
            tur={surenSayim.round}
            beklemede={diyalogAcik}
          />
        ) : (
          <p className="text-body-medium text-on-surface-variant">{SAYIM_OKUTMASI_KAPANDI}</p>
        ))}
      <YoneticiParolaDiyalogu
        open={diyalogAcik}
        onClose={() => setDiyalogAcik(false)}
        onGecti={onGecti}
      />
    </div>
  );
}
