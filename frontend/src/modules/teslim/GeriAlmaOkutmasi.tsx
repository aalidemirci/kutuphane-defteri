// Teslimden geri alma okutması (U11, tasarım §9-11, §4.4). Sınıf kitaplığından ya da
// öğretmenden dönen kitapların kütüphane etiketi okutulur; okunan kitabın açık
// teslimi kapanır ve kitap rafa döner. Geri alma hiçbir durumda kilitlenmez (iade
// gibi).
//
// İki yerde durur ve `gorevli` prop'u yalnız görüntüyü ayırır — asıl kapı
// sunucudadır:
//   * Yönetici kipinde Teslimler → Geri Alma sekmesi: her satırda teslim alan ve
//     belge no; bu ekranda geri alınanların "Geri alma dökümü" (E15) basılır. Belgenin
//     bütün satırlarının dökümü (başka oturumda, masada ya da görevli kipinde geri
//     alınanlar dahil) Teslim Kayıtları'ndaki belge kartından basılır.
//   * Görevli kipinde görevli ekranı (`kip/GorevliEkrani`): görevli kipinde açık TEK
//     teslim ucu budur (§4.4 "Teslimden geri alma okutması"). Sunucu teslim alanın
//     kimliğini göndermez; ekran yalnız barkodu, eser adını ve iletiyi yazar. Evrak
//     yönetici kipindedir.
//
// Okutma bir OLAYDIR (masa iadesiyle aynı sözleşme): sunucu her durumda bir sonuç
// gövdesi döner — geri alındı · teslimde değil (durum iletisi) · reddedildi.

import { useCallback, useEffect, useRef, useState } from "react";

import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import BarcodeInput from "../../ui/BarcodeInput";
import type { OkutmaGeriBildirimi } from "../../ui/BarcodeInput";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import type { MasaNushasi } from "../dolasim/api";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { GERI_ALMA_DOKUMU_ADI, teslimApi } from "./api";
import type { GeriAlinanTeslim, GeriAlmaSonucuTuru } from "./api";

/** Okutma kutusunun etiketi (testler ve kılavuz bu adla anlatır). */
export const GERI_ALMA_KUTUSU = "Kütüphane etiketi";
export const GERI_ALMA_BASLIGI = "Geri Alınan Kitapları Okutun";

/** Ekranda tutulan son okutma sayısı. */
const GOSTERILEN_OKUTMA = 30;

type SonucTuru = GeriAlmaSonucuTuru | "hata";

interface Okutma {
  no: number;
  kod: string;
  sonuc: SonucTuru;
  ileti: string;
  nusha: MasaNushasi | null;
  teslim: GeriAlinanTeslim | null;
}

const SONUC_GORUNUMU: Record<SonucTuru, { ikon: string; sinif: string }> = {
  returned: { ikon: "input", sinif: "bg-secondary-container text-on-secondary-container" },
  not_delivered: {
    ikon: "info",
    sinif: "bg-tertiary-container text-on-tertiary-container",
  },
  rejected: { ikon: "error", sinif: "bg-error-container text-on-error-container" },
  hata: { ikon: "cloud_off", sinif: "bg-error-container text-on-error-container" },
};

const GERI_BILDIRIM: Record<SonucTuru, OkutmaGeriBildirimi> = {
  returned: "basari",
  not_delivered: "uyari",
  rejected: "hata",
  hata: "hata",
};

function nushaMetni(nusha: MasaNushasi | null, kod: string): string {
  return nusha ? `${nusha.barcode_display} — ${nusha.work_title}` : `Okutulan: ${kod}`;
}

/** Yönetici kipinde satırın teslim ayrıntısı: kimden geri alındı, hangi belgeyle. */
function teslimMetni(teslim: GeriAlinanTeslim | null): string {
  if (teslim === null) return "";
  const alan = [teslim.recipient_kind_display, teslim.recipient_label].filter(Boolean).join(": ");
  return [alan, `belge no ${teslim.document_no}`, `teslim ${formatDate(teslim.delivered_on)}`]
    .filter(Boolean)
    .join(" · ");
}

export default function GeriAlmaOkutmasi({
  gorevli = false,
  beklemede = false,
  onGeriAlindi,
}: {
  /** Görevli kipi: teslim alanın kimliği yok, evrak yok. */
  gorevli?: boolean;
  /** Ebeveynin diyaloğu açık: okutma kutusu beklemede. */
  beklemede?: boolean;
  /** Bir kitap geri alınınca (liste sekmesi tazelensin). */
  onGeriAlindi?: () => void;
}) {
  const [okutmalar, setOkutmalar] = useState<Okutma[]>([]);
  // Bu ekranda geri alınan teslim satırları (döküm bunlardan basılır; yalnız yönetici).
  const [geriAlinanlar, setGeriAlinanlar] = useState<GeriAlinanTeslim[]>([]);
  const [geriAlinanSayisi, setGeriAlinanSayisi] = useState(0);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const sayac = useRef(0);
  const acik = useRef(true);

  useEffect(() => {
    acik.current = true;
    return () => {
      acik.current = false;
    };
  }, []);

  const ekle = useCallback((okutma: Omit<Okutma, "no">) => {
    sayac.current += 1;
    const no = sayac.current;
    setOkutmalar((onceki) => [{ ...okutma, no }, ...onceki].slice(0, GOSTERILEN_OKUTMA));
  }, []);

  /** Tek okutma — `BarcodeInput` kuyruğundan sırayla gelir. */
  const okut = async (kod: string): Promise<OkutmaGeriBildirimi | undefined> => {
    try {
      const sonuc = await teslimApi.geriAl(kod);
      if (!acik.current) return undefined;
      const teslim = gorevli ? null : (sonuc.delivery ?? null);
      ekle({ kod, sonuc: sonuc.result, ileti: sonuc.message, nusha: sonuc.copy, teslim });
      if (sonuc.result === "returned") {
        setGeriAlinanSayisi((n) => n + 1);
        if (teslim !== null) setGeriAlinanlar((onceki) => [...onceki, teslim]);
        onGeriAlindi?.();
      }
      return GERI_BILDIRIM[sonuc.result];
    } catch (e) {
      if (!acik.current) return undefined;
      ekle({
        kod,
        sonuc: "hata",
        ileti: hataOku(e, "Geri alma kaydedilemedi; kitabı yeniden okutun.").message,
        nusha: null,
        teslim: null,
      });
      return "hata";
    }
  };

  const son = okutmalar[0];

  return (
    <div className="space-y-4">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">{GERI_ALMA_BASLIGI}</p>
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          Sınıf kitaplığından ya da öğretmenden dönen kitapların kütüphane etiketini okutun.
          Okutulan kitabın teslimi kapanır ve kitap rafa döner. Kitabın arka kapağındaki ISBN
          barkodunu değil, kütüphane etiketini okutun.
        </p>
        <BarcodeInput
          className="max-w-xl"
          label={GERI_ALMA_KUTUSU}
          onOkut={okut}
          beklemede={beklemede}
          placeholder="2026-000123"
          helperText="Okuyucuyla okutun ya da numarayı yazıp Enter'a basın."
        />

        {son && (
          <div
            role="status"
            aria-live="polite"
            className={`flex items-start gap-3 rounded-shape-md px-4 py-3 ${SONUC_GORUNUMU[son.sonuc].sinif}`}
          >
            <Icon name={SONUC_GORUNUMU[son.sonuc].ikon} size="2xl" className="shrink-0" />
            <div className="min-w-0">
              <p className="text-title-medium">{son.ileti}</p>
              <p className="text-body-medium">{nushaMetni(son.nusha, son.kod)}</p>
              {son.teslim && <p className="text-body-medium">{teslimMetni(son.teslim)}</p>}
            </div>
          </div>
        )}

        <p className="text-body-small text-on-surface-variant">
          Bu ekranda geri alınan: {formatNumber(geriAlinanSayisi)}
        </p>

        {okutmalar.length > 1 && (
          <ol aria-label="Son okutmalar" className="space-y-1 text-body-small">
            {okutmalar.slice(1).map((o) => (
              <li key={o.no} className="flex items-start gap-2 text-on-surface-variant">
                <Icon name={SONUC_GORUNUMU[o.sonuc].ikon} size="sm" className="mt-0.5 shrink-0" />
                <span>
                  {nushaMetni(o.nusha, o.kod)}: {o.ileti}
                  {o.teslim && ` · ${teslimMetni(o.teslim)}`}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Card>

      {!gorevli && (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-title-medium text-on-surface">{GERI_ALMA_DOKUMU_ADI}</p>
          <p className="max-w-3xl text-body-small text-on-surface-variant">
            Bu ekranda geri alınan kitapların dökümü: hangi kitabın hangi teslimden geri alındığını
            gösterir. Teslim listesiyle birlikte saklanır. Başka bir zamanda, masada ya da görevli
            kipinde geri alınan kitapların dökümü Teslim Kayıtları&apos;nda belge no&apos;ya
            tıklayınca çıkan kartta basılır.
          </p>
          {hata && <ErrorBand hata={hata} />}
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() =>
                teslimApi.geriAlmaDokumuPdf({ deliveryIds: geriAlinanlar.map((t) => t.id) })
              }
              dosyaAdi={() => dosyaAdi([GERI_ALMA_DOKUMU_ADI, formatDate(todayIso())], "pdf")}
              onizlemeBasligi={GERI_ALMA_DOKUMU_ADI}
              disabled={geriAlinanlar.length === 0}
              onHata={setHata}
            />
          </div>
        </Card>
      )}
    </div>
  );
}
