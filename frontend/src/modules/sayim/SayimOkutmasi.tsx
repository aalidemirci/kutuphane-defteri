// Sayım okutması (F9; tasarım §7.3 BarcodeInput, §9-10). Kitapların kütüphane etiketi
// okutulur; okuyucu KUYRUĞU sırayla ve tek tek işler — hızlı okutmada hiçbir kod kaybolmaz,
// aynı kodu ikinci kez okutmak zararsızdır (sunucu "zaten okutuldu" der). ISBN ve üye kartı
// reddedilir, kayda yazılmaz. Anlık görüntüde olmayan kod "sayım fazlası" olarak yazılır.
//
// İlerleme bölüm bölüm ve (yerinde sayılan) sınıf kitaplığı sınıf kitaplığı sunucudan okunur
// (`…/progress/`, kişisiz); okutmalar durulunca tazelenir. İkinci sayımda (TMY 32/6)
// bulunamayan nüshaların listesi gösterilir: kurul bunları bir kez daha arar.
//
// Kişisel veri: sonuçlarda ödünç alanın ya da teslim alanın kimliği yoktur (sunucu
// göndermez).

import { useCallback, useEffect, useRef, useState } from "react";

import { formatNumber } from "../../lib/format";
import BarcodeInput from "../../ui/BarcodeInput";
import type { OkutmaGeriBildirimi } from "../../ui/BarcodeInput";
import Card from "../../ui/Card";
import { hataOku } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { sayimApi } from "./api";
import type { OkutmaKodu, SayimIlerlemesi, SayimKalemi } from "./api";

/** Okutma kutusunun etiketi ve kartın başlığı (kılavuz bu adlarla anlatır). */
export const OKUTMA_KUTUSU = "Kütüphane etiketi";
export const OKUTMA_BASLIGI = "Kitapları Okutun";
export const IKINCI_SAYIM_BASLIGI = "İkinci Sayım: Bulunamayan Nüshalar";
/** Okutmalar durulduktan sonra ilerleme bu kadar beklenip tazelenir (ms). */
export const ILERLEME_GECIKMESI_MS = 600;
/** Ekranda tutulan son okutma sayısı. */
const GOSTERILEN_OKUTMA = 30;

type SonucTuru = OkutmaKodu | "hata";

interface Okutma {
  no: number;
  kod: string;
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

function kitapMetni(kalem: SayimKalemi | null, kod: string): string {
  if (kalem === null) return kod ? `Okutulan: ${kod}` : "";
  if (kalem.is_surplus) {
    return `${kalem.surplus_barcode_display || kod} — sayım fazlası${
      kalem.surplus_work_title ? `: ${kalem.surplus_work_title}` : ""
    }`;
  }
  return `${kalem.barcode_display} — ${kalem.work_title}`;
}

export default function SayimOkutmasi({
  sayimId,
  tur,
  beklemede = false,
  onOkutuldu,
  onBekleyen,
}: {
  sayimId: number;
  /** 1: ilk sayım · 2: ikinci sayım (TMY 32/6). */
  tur: number;
  /** Ebeveynin diyaloğu açık: okutma kutusu beklemede. */
  beklemede?: boolean;
  /** Bir kod işlendi (fazla listesi ve sonuçlar tazelensin). */
  onOkutuldu?: (kod: OkutmaKodu) => void;
  /** Sırada bekleyen ve işlenmekte olan okutma sayısı (tamamlama bunlar bitmeden başlamaz). */
  onBekleyen?: (bekleyen: number) => void;
}) {
  const [okutmalar, setOkutmalar] = useState<Okutma[]>([]);
  const [bulunan, setBulunan] = useState(0);
  const [ilerleme, setIlerleme] = useState<SayimIlerlemesi | null>(null);
  const [aranacaklar, setAranacaklar] = useState<SayimKalemi[] | null>(null);
  const [aranacakSayisi, setAranacakSayisi] = useState(0);
  const [tazele, setTazele] = useState(0);
  const sayac = useRef(0);
  const acik = useRef(true);

  useEffect(() => {
    acik.current = true;
    return () => {
      acik.current = false;
    };
  }, []);

  // İlerleme ve (ikinci sayımda) aranacaklar: açılışta hemen, okutmalar durulunca gecikmeli.
  useEffect(() => {
    let iptal = false;
    const oku = () => {
      sayimApi
        .ilerleme(sayimId)
        .then((i) => {
          if (!iptal) setIlerleme(i);
        })
        .catch(() => undefined);
      if (tur === 2) {
        sayimApi
          .kalemler(sayimId, { result: "MISSING", limit: 200 })
          .then((s) => {
            if (iptal) return;
            setAranacaklar(s.results);
            setAranacakSayisi(s.count);
          })
          .catch(() => undefined);
      }
    };
    if (tazele === 0) {
      oku();
      return () => {
        iptal = true;
      };
    }
    const zamanlayici = setTimeout(oku, ILERLEME_GECIKMESI_MS);
    return () => {
      iptal = true;
      clearTimeout(zamanlayici);
    };
  }, [sayimId, tur, tazele]);

  const ekle = useCallback((okutma: Omit<Okutma, "no">) => {
    sayac.current += 1;
    const no = sayac.current;
    setOkutmalar((onceki) => [{ ...okutma, no }, ...onceki].slice(0, GOSTERILEN_OKUTMA));
  }, []);

  /** Tek okutma — `BarcodeInput` kuyruğundan sırayla gelir. */
  const okut = async (kod: string): Promise<OkutmaGeriBildirimi | undefined> => {
    try {
      const yanit = await sayimApi.okut(sayimId, [kod]);
      if (!acik.current) return undefined;
      const sonuc = yanit.results[0];
      ekle({ kod, sonuc: sonuc.code, ileti: sonuc.message, kitap: kitapMetni(sonuc.item, kod) });
      if (sonuc.code === "bulundu") setBulunan((n) => n + 1);
      setTazele((n) => n + 1);
      onOkutuldu?.(sonuc.code);
      return GORUNUM[sonuc.code].ses;
    } catch (e) {
      if (!acik.current) return undefined;
      ekle({
        kod,
        sonuc: "hata",
        ileti: hataOku(e, "Okutma kaydedilemedi; kitabı yeniden okutun.").message,
        kitap: `Okutulan: ${kod}`,
      });
      return "hata";
    }
  };

  const son = okutmalar[0];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <h2 className="text-title-medium font-semibold text-on-surface">{OKUTMA_BASLIGI}</h2>
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          {tur === 2
            ? "İkinci sayım: bulunamayan nüshaları bir kez daha arayın ve bulduklarınızı okutun (Taşınır Mal Yönetmeliği md. 32/6). "
            : "Rafta ve onarımda duran kitapların, yerinde sayılan sınıf kitaplıklarında da kitapların kütüphane etiketini okutun. "}
          Aynı kitabı ikinci kez okutmak zararsızdır. Kitabın arka kapağındaki ISBN barkodunu değil,
          kütüphane etiketini okutun.
        </p>
        <BarcodeInput
          className="max-w-xl"
          label={OKUTMA_KUTUSU}
          onOkut={okut}
          beklemede={beklemede}
          onBekleyenDegisti={onBekleyen}
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

      {tur === 2 && aranacaklar !== null && (
        <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <h2 className="text-title-medium font-semibold text-on-surface">
            {IKINCI_SAYIM_BASLIGI}
          </h2>
          {aranacaklar.length === 0 ? (
            <p className="text-body-medium text-on-surface-variant">
              Bulunamayan nüsha kalmadı. Sayımı tamamlayabilirsiniz.
            </p>
          ) : (
            <>
              <p className="text-body-small text-on-surface-variant">
                {`${formatNumber(aranacakSayisi)} nüsha aranıyor. Bulunanı okutun; yine bulunamayan “Noksan” olarak yazılır.`}
              </p>
              <ul aria-label="Aranan nüshalar" className="divide-y divide-outline-variant/50">
                {aranacaklar.map((k) => (
                  <li key={k.id} className="flex flex-wrap gap-x-3 py-1.5 text-body-small">
                    <span className="font-mono text-on-surface">{k.barcode_display}</span>
                    <span className="text-on-surface">{k.work_title}</span>
                    <span className="text-on-surface-variant">
                      {[k.section_name, k.class_library, k.expected_status_display]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </li>
                ))}
              </ul>
              {aranacakSayisi > aranacaklar.length && (
                <p className="text-body-small text-on-surface-variant">
                  {`İlk ${formatNumber(aranacaklar.length)} nüsha gösteriliyor; bütün liste sayım tutanağının ara dökümündedir (Sayım Belgeleri).`}
                </p>
              )}
            </>
          )}
        </Card>
      )}

      {ilerleme !== null && <Ilerleme ilerleme={ilerleme} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// İlerleme (kişisiz)
// ---------------------------------------------------------------------------

function Cubuk({ bulunan, beklenen }: { bulunan: number; beklenen: number }) {
  const oran = beklenen > 0 ? Math.min(100, Math.round((bulunan / beklenen) * 100)) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-container-highest">
      <div className="h-full bg-primary" style={{ width: `${oran}%` }} />
    </div>
  );
}

export function Ilerleme({ ilerleme }: { ilerleme: SayimIlerlemesi }) {
  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <h2 className="text-title-medium font-semibold text-on-surface">Bölümlere Göre İlerleme</h2>
      <p className="text-body-medium text-on-surface">
        {`${formatNumber(ilerleme.physical_found)} / ${formatNumber(ilerleme.physical_expected)} nüsha bulundu`}
        {ilerleme.by_record_basis > 0 &&
          ` · kayda göre alınacak ${formatNumber(ilerleme.by_record_basis)} nüsha`}
        {ilerleme.surplus > 0 && ` · sayım fazlası ${formatNumber(ilerleme.surplus)}`}
      </p>
      <p className="text-body-small text-on-surface-variant">
        Sayım sırasında iade edilen, teslimden geri alınan ya da onarımdan dönen kitap da bulunmuş
        sayılır.
      </p>
      {ilerleme.sections.length > 0 && (
        <ul aria-label="Bölümler" className="space-y-2">
          {ilerleme.sections.map((b) => (
            <li key={b.section ?? "bolumsuz"} className="space-y-1">
              <div className="flex justify-between gap-3 text-body-small">
                <span className="text-on-surface">{b.name || "Bölümsüz"}</span>
                <span className="text-on-surface-variant">
                  {`${formatNumber(b.found)} / ${formatNumber(b.expected)}`}
                </span>
              </div>
              <Cubuk bulunan={b.found} beklenen={b.expected} />
            </li>
          ))}
        </ul>
      )}
      {ilerleme.class_libraries.length > 0 && (
        <>
          <h3 className="pt-1 text-title-small font-semibold text-on-surface">
            Yerinde Sayılan Sınıf Kitaplıkları
          </h3>
          <ul aria-label="Sınıf kitaplıkları" className="space-y-2">
            {ilerleme.class_libraries.map((s) => (
              <li key={s.class_section ?? s.label} className="space-y-1">
                <div className="flex justify-between gap-3 text-body-small">
                  <span className="text-on-surface">{s.label || "—"}</span>
                  <span className="text-on-surface-variant">
                    {`${formatNumber(s.found)} / ${formatNumber(s.expected)}`}
                  </span>
                </div>
                <Cubuk bulunan={s.found} beklenen={s.expected} />
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
