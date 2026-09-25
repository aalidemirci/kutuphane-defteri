// Ayıklama, nadir eserler ve yıl sonu raporu ekranlarının ortak parçaları (F8):
// E7 kural kancası (gerekçe → TMY yolu sunucudan), "Ayıklama" türündeki komisyon
// kararlarının kancası, belge satırı (Önizle · PDF'i indir · Excel'i indir), rozet ve
// bilgi satırı.
//
// Kural kopyalanmaz: TMY yolu sunucunun `library/weeding/rules/` yanıtından seçilir,
// belgenin basılabilirliği `…/documents/` yanıtından okunur.

import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { kutuphaneApi } from "../kutuphane/api";
import type { CommissionDecision } from "../kutuphane/api";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { SECICI_SINIRI } from "../kutuphane/ortak";
import { ayiklamaApi, belgeDosyaAdi } from "./api";
import type { AyiklamaKurallari, Gerekce, TmyYolu } from "./api";

/** E7 tablosu (sunucudan; okunamazsa `null` — ekran yolu göstermez, sunucu yine denetler). */
export function useKurallar(): AyiklamaKurallari | null {
  const [kurallar, setKurallar] = useState<AyiklamaKurallari | null>(null);
  useEffect(() => {
    let iptal = false;
    ayiklamaApi
      .kurallar()
      .then((k) => {
        if (!iptal) setKurallar(k);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);
  return kurallar;
}

/** Gerekçenin izin verdiği TMY yolları ve varsayılanı (E7). */
export function gerekceYollari(
  kurallar: AyiklamaKurallari | null,
  gerekce: Gerekce | "",
): { yollar: TmyYolu[]; varsayilan: TmyYolu | ""; olcutGerekir: boolean } {
  const satir = kurallar?.reasons.find((r) => r.value === gerekce);
  if (!satir) return { yollar: [], varsayilan: "", olcutGerekir: false };
  return {
    yollar: satir.paths,
    varsayilan: satir.default_path,
    olcutGerekir: satir.needs_criterion,
  };
}

/** Yol devir mi? (sunucunun `is_transfer` işaretinden) */
export function devirMi(kurallar: AyiklamaKurallari | null, yol: TmyYolu | ""): boolean {
  return kurallar?.paths.find((p) => p.value === yol)?.is_transfer ?? false;
}

/** Seçim ve Ayıklama Komisyonunun "Ayıklama" türündeki kararları (D7: tür bağlayıcıdır). */
export function useAyiklamaKararlari(): CommissionDecision[] | null {
  const [kararlar, setKararlar] = useState<CommissionDecision[] | null>(null);
  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listCommissionDecisions({ decisionType: "WEEDING", limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (!iptal) setKararlar(sayfa.results);
      })
      .catch(() => {
        if (!iptal) setKararlar([]);
      });
    return () => {
      iptal = true;
    };
  }, []);
  return kararlar;
}

/** Komisyon kararları sekmesinin adresi (karar yoksa kullanıcı buraya gider). */
export const KOMISYON_KARARLARI_ADRESI = "/katalog/edinimler?tab=kararlar";

/** Küçük durum rozeti. */
export function Rozet({
  children,
  ton = "ikincil",
  icon,
}: {
  children: ReactNode;
  ton?: "ikincil" | "ucuncul" | "hata" | "notr";
  icon?: string;
}) {
  const renk = {
    ikincil: "bg-secondary-container text-on-secondary-container",
    ucuncul: "bg-tertiary-container text-on-tertiary-container",
    hata: "bg-error-container text-on-error-container",
    notr: "bg-surface-container-highest text-on-surface-variant",
  }[ton];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-shape-sm px-2 py-0.5 text-label-small ${renk}`}
    >
      {icon && <Icon name={icon} size="sm" />}
      {children}
    </span>
  );
}

/** Tanım listesi satırı. */
export function Bilgi({ etiket, children }: { etiket: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-label-medium text-on-surface-variant">{etiket}</dt>
      <dd className="break-words text-body-medium text-on-surface">{children}</dd>
    </div>
  );
}

/** Excel indirme düğmesi (devir listesi). */
export function ExcelDugmesi({
  al,
  dosyaAdi,
  onHata,
}: {
  al: () => Promise<Blob>;
  dosyaAdi: () => string;
  onHata: (hata: SayfaHatasi | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const indir = async () => {
    setBusy(true);
    onHata(null);
    try {
      saveBlob(await al(), dosyaAdi());
    } catch (e) {
      onHata(hataOku(e, "Excel dosyası hazırlanamadı."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button variant="outlined" icon="table_view" onClick={() => void indir()} disabled={busy}>
      {busy ? "Hazırlanıyor…" : "Excel'i indir"}
    </Button>
  );
}

/**
 * Bir belgenin satırı: adı, basılabiliyorsa "Önizle" · "PDF'i indir" (+ Excel), değilse
 * sunucunun gerekçesi. PDF almak hiçbir kayda dokunmaz.
 */
export function BelgeSatiri({
  ad,
  basilabilir = true,
  gerekce = "",
  pdfAl,
  excelAl,
  aciklama,
}: {
  ad: string;
  basilabilir?: boolean;
  gerekce?: string;
  pdfAl: () => Promise<Blob>;
  excelAl?: () => Promise<Blob>;
  aciklama?: string;
}) {
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body-medium font-semibold text-on-surface">{ad}</p>
          {aciklama && <p className="text-body-small text-on-surface-variant">{aciklama}</p>}
          {!basilabilir && gerekce && (
            <p className="text-body-small text-on-surface-variant">{gerekce}</p>
          )}
        </div>
        {basilabilir && (
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={pdfAl}
              dosyaAdi={() => belgeDosyaAdi(ad)}
              onizlemeBasligi={ad}
              onHata={setHata}
            />
            {excelAl && (
              <ExcelDugmesi
                al={excelAl}
                dosyaAdi={() => belgeDosyaAdi(ad, "xlsx")}
                onHata={setHata}
              />
            )}
          </div>
        )}
      </div>
      {hata && <ErrorBand hata={hata} />}
    </li>
  );
}

/** Onay kutusu (kitteki onay kutusu biçimi — 44px dokunma hedefi). */
export function OnayKutusu({
  etiket,
  checked,
  onChange,
  disabled = false,
}: {
  etiket: ReactNode;
  checked: boolean;
  onChange: (deger: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="size-5 shrink-0 accent-primary"
      />
      <span className="min-w-0">{etiket}</span>
    </label>
  );
}

/** Okutulan ya da yazılan kodları satırlara böler (boşlar atılır, sıra korunur, tekrar düşer). */
export function kodlariAyir(metin: string): string[] {
  return Array.from(
    new Set(
      metin
        .split(/[\s,;]+/)
        .map((k) => k.trim())
        .filter(Boolean),
    ),
  );
}

/** Sunucunun alan hatası listesi (ör. `fields.barcodes`) — metin dizisine indirger. */
export function alanHatalari(e: unknown, alan: string): string[] {
  const fields = (e as { fields?: Record<string, unknown> } | null)?.fields;
  const deger = fields?.[alan];
  if (Array.isArray(deger)) return deger.map(String);
  if (typeof deger === "string") return [deger];
  return [];
}
