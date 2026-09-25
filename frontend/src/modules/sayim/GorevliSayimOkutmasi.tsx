// Görevli kipinde sayım okutması (F9 — madde 24, 25.09.2026 kullanıcı kararı; emsal etiket
// doğrulama okutması).
//
// Sunucu görevli kipinde sayım uçlarından YALNIZ okutmayı geçirir ve yanıtı daraltır: okutma
// sonucu, ileti, barkod ve eser adı (`GorevliOkutmaSonucu`). Kalem, özet, ilerleme, ikinci
// sayım listesi ve sayım fazlası kararı yönetici ekranındadır; görevli yanlış bir kodu
// okutursa yönetici tamamlamadan önce ilerlemede ve sayım fazlası kartında görür. Okuyucu
// KUYRUĞU sırayla işler (`BarcodeInput`): hızlı okutmada hiçbir kod kaybolmaz, aynı kodu ikinci
// kez okutmak zararsızdır.
//
// Kişisel veri: yanıt ödünç alanın ya da teslim alanın kimliğini taşımaz (sunucu göndermez).

import { useCallback, useEffect, useRef, useState } from "react";

import { formatNumber } from "../../lib/format";
import BarcodeInput from "../../ui/BarcodeInput";
import type { OkutmaGeriBildirimi } from "../../ui/BarcodeInput";
import Card from "../../ui/Card";
import { hataOku } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { sayimApi } from "./api";
import type { OkutmaKodu } from "./api";
import { OKUTMA_KUTUSU } from "./SayimOkutmasi";

/** Görevli ekranındaki açıklama (kılavuzun Kipler ve Sayım bölümleri aynı cümleyi kullanır). */
export const GOREVLI_SAYIM_ACIKLAMASI =
  "Rafta ve kütüphanede duran kitapların kütüphane etiketini okutun. Aynı kitabı ikinci kez " +
  "okutmak zararsızdır. Sayımın ilerlemesini, fazlasını ve sonuçlarını kütüphane yöneticisi " +
  "görür.";
/** Ekranda tutulan son okutma sayısı. */
const GOSTERILEN_OKUTMA = 20;

type SonucTuru = OkutmaKodu | "hata";

interface Okutma {
  no: number;
  sonuc: SonucTuru;
  ileti: string;
  kitap: string;
}

const GORUNUM: Record<SonucTuru, { ikon: string; sinif: string; ses: OkutmaGeriBildirimi }> = {
  bulundu: {
    ikon: "check_circle",
    sinif: "bg-secondary-container text-on-secondary-container",
    ses: "basari",
  },
  zaten_okutuldu: {
    ikon: "info",
    sinif: "bg-surface-container-high text-on-surface",
    ses: "bilgi",
  },
  fazla: {
    ikon: "add_circle",
    sinif: "bg-tertiary-container text-on-tertiary-container",
    ses: "uyari",
  },
  fazla_tekrar: {
    ikon: "info",
    sinif: "bg-surface-container-high text-on-surface",
    ses: "bilgi",
  },
  kapsam_disi: {
    ikon: "block",
    sinif: "bg-tertiary-container text-on-tertiary-container",
    ses: "uyari",
  },
  gecersiz: { ikon: "error", sinif: "bg-error-container text-on-error-container", ses: "hata" },
  hata: { ikon: "cloud_off", sinif: "bg-error-container text-on-error-container", ses: "hata" },
};

export default function GorevliSayimOkutmasi({
  sayimId,
  tur,
  beklemede = false,
}: {
  sayimId: number;
  /** 1: ilk sayım · 2: ikinci sayım (TMY 32/6). */
  tur: number;
  /** Ebeveynin diyaloğu açık (yönetici kipine geçiş): okutma kutusu beklemede. */
  beklemede?: boolean;
}) {
  const [okutmalar, setOkutmalar] = useState<Okutma[]>([]);
  const [bulunan, setBulunan] = useState(0);
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

  const okut = async (kod: string): Promise<OkutmaGeriBildirimi | undefined> => {
    try {
      const yanit = await sayimApi.gorevliOkut(sayimId, kod);
      if (!acik.current) return undefined;
      const sonuc = yanit.results[0];
      const kitap = sonuc.work_title
        ? `${sonuc.barcode_display} — ${sonuc.work_title}`
        : sonuc.barcode_display || `Okutulan: ${kod}`;
      ekle({ sonuc: sonuc.code, ileti: sonuc.message, kitap });
      if (sonuc.code === "bulundu") setBulunan((n) => n + 1);
      return GORUNUM[sonuc.code].ses;
    } catch (e) {
      if (!acik.current) return undefined;
      ekle({
        sonuc: "hata",
        ileti: hataOku(e, "Okutma kaydedilemedi; kitabı yeniden okutun.").message,
        kitap: `Okutulan: ${kod}`,
      });
      return "hata";
    }
  };

  const son = okutmalar[0];

  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        {tur === 2
          ? "İkinci sayım: bulunamayan nüshalar bir kez daha aranıyor; bulduğunuz kitapları okutun (Taşınır Mal Yönetmeliği md. 32/6). "
          : ""}
        {GOREVLI_SAYIM_ACIKLAMASI}
      </p>
      <BarcodeInput
        className="max-w-xl"
        label={OKUTMA_KUTUSU}
        onOkut={okut}
        beklemede={beklemede}
        placeholder="2026-000123"
        helperText="Okuyucuyla okutun ya da numarayı yazıp Enter'a basın."
      />

      {son && (
        <div
          role="status"
          aria-live="polite"
          className={`flex items-start gap-3 rounded-shape-md px-4 py-3 ${GORUNUM[son.sonuc].sinif}`}
        >
          <Icon name={GORUNUM[son.sonuc].ikon} size="2xl" className="shrink-0" />
          <div className="min-w-0">
            <p className="text-title-medium">{son.ileti}</p>
            {son.kitap && <p className="text-body-medium">{son.kitap}</p>}
          </div>
        </div>
      )}

      <p className="text-body-small text-on-surface-variant">
        Bu ekranda bulunan: {formatNumber(bulunan)}
      </p>

      {okutmalar.length > 1 && (
        <ol aria-label="Son okutmalar" className="space-y-1 text-body-small">
          {okutmalar.slice(1).map((o) => (
            <li key={o.no} className="flex items-start gap-2 text-on-surface-variant">
              <Icon name={GORUNUM[o.sonuc].ikon} size="sm" className="mt-0.5 shrink-0" />
              <span>
                {o.kitap ? `${o.kitap}: ` : ""}
                {o.ileti}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
