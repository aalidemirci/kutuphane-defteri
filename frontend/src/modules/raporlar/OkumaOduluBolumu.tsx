// Raporlar → Okuma Ödülü (F10; tasarım §3 KVKK, §10 E20).
//
// Uygulama Kılavuzu 7'nin ÖNERİSİ için İÇ ÇIKTI: programda adlı sıralamanın geçtiği TEK yer.
// Profil yasağı (CLAUDE.md §2-5) onu şu sınırlara bağlar ve ekran bunların hepsini söyler:
// - yalnız yönetici kipinde (sunucu da seçici de ister; görevli kipinde bu sayfa hiç açılmaz),
// - "İç kullanım": asılmaz, çoğaltılmaz, ağda ve velilerle paylaşılmaz; Ağ Kataloğu, Genel
//   Bakış, Ayın Kitapları afişi ve yıl sonu raporu bu çıktıyı içermez,
// - SAYI basılmaz (yalnız sıra, eşitler aynı sırada), okul no basılmaz,
// - ADLAR EKRANA GELMEZ: çıktı yalnız PDF'tir (önizleme penceresi PDF'i gösterir), ekranda
//   aday listesi tutulmaz.
// Sorguda kişisel veri yoktur (dönem, sınıf düzeyi, sıra sayısı). İndirme adında kişi adı yok.

import { useEffect, useState } from "react";

import { getGradeLevels } from "../../lib/gradeLevels";
import type { GradeLevelOption } from "../../lib/gradeLevels";
import Card from "../../ui/Card";
import ErrorBand from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { YONETMELIK } from "../../lib/mevzuat";
import {
  KILAVUZ_7_ONERISI,
  ODUL_SIRA_EN_COK,
  ODUL_SIRA_VARSAYILAN,
  OKUMA_ODULU_ADI,
  raporDosyaAdi,
  raporlarApi,
} from "./api";
import type { DonemSecimi } from "./api";
import DonemSecici, { eksikAralik } from "./DonemSecici";

/** "İç kullanım" uyarısı — belgenin dipnotuyla aynı kural (backend `okuma_odulu_belgesi`). */
export const IC_KULLANIM_UYARISI =
  "Bu çıktı öğrenci adı taşır: asılmaz, çoğaltılmaz, ağda ve velilerle paylaşılmaz. Yalnız " +
  "yönetici kipinde basılır; Ağ Kataloğu, Genel Bakış, Ayın Kitapları afişi ve yıl sonu " +
  "raporu bu sıralamayı içermez.";

/**
 * Bölümün açıklaması — programın kendi sesi. Ödünç sırasını "en çok (kitap) okuyan öğrenciler"
 * listesi diye sunmaz (sözlük: ödünç ≠ okuduğu kitap; F10 düzeltme turu). Kılavuz 7'nin cümlesi
 * yalnız alıntıdır (`KILAVUZ_7_ONERISI`).
 */
export const E20_ACIKLAMASI =
  "Okul, Uygulama Kılavuzu 7'deki ödül önerisini uygulamak isterse karar vermesine yardım eden " +
  "iç çıktı. Öneridir, bağlayıcı değildir; ödül verilip verilmeyeceğine okul karar verir.";

/** Ölçütün anlatımı (belgenin notlarıyla aynı kural). */
export const ODUL_OLCUTU =
  "Sıra, dönem içinde ödünç alınıp iade edilmiş farklı eser sayısına göredir: aynı eserin " +
  "yeniden alınması bir kez sayılır. Eşit olanlar aynı sıradadır ve sınırdaki eşitlerin hepsi " +
  "girer. Yalnız okuldaki öğrenciler sıralanır. Çıktıda sayı ve okul no yoktur. Ödünç kaydı " +
  "okunan kitabı göstermez.";

function siraSayisi(ham: string): number | null {
  const n = Number(ham.trim());
  return Number.isInteger(n) && n >= 1 && n <= ODUL_SIRA_EN_COK ? n : null;
}

export default function OkumaOduluBolumu() {
  const [donem, setDonem] = useState<DonemSecimi>({ tur: "etkin" });
  const [sinif, setSinif] = useState("");
  const [sira, setSira] = useState(String(ODUL_SIRA_VARSAYILAN));
  const [duzeyler, setDuzeyler] = useState<GradeLevelOption[]>([]);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    getGradeLevels()
      .then((g) => {
        if (!iptal) setDuzeyler(g.levels);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  const siraNo = siraSayisi(sira);
  const sinifNo = sinif === "" ? null : Number(sinif);
  const kapsam = sinifNo === null ? undefined : duzeyler.find((d) => d.value === sinifNo)?.label;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div
        role="note"
        aria-label="İç kullanım"
        className="flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container"
      >
        <Icon name="visibility_lock" size="lg" className="mt-0.5 shrink-0" />
        <div className="min-w-0 space-y-0.5">
          <p className="text-label-large">İç kullanım</p>
          <p className="text-body-small">{IC_KULLANIM_UYARISI}</p>
        </div>
      </div>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div>
          <h2 className="text-title-medium font-semibold text-on-surface">{OKUMA_ODULU_ADI}</h2>
          <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
            {E20_ACIKLAMASI}
          </p>
        </div>
        <figure className="rounded-shape-md border-l-4 border-outline bg-surface-container px-4 py-3">
          <blockquote className="text-body-medium text-on-surface">{`“${KILAVUZ_7_ONERISI}”`}</blockquote>
          <figcaption className="mt-1 text-body-small text-on-surface-variant">
            {`${YONETMELIK} Uygulama Kılavuzu, 7`}
          </figcaption>
        </figure>
        <p className="max-w-3xl text-body-small text-on-surface-variant">{ODUL_OLCUTU}</p>

        <DonemSecici deger={donem} onDegisti={setDonem} aninda />
        <div className="flex flex-wrap items-end gap-3">
          <Select
            className="w-56"
            label="Sınıf"
            value={sinif}
            onChange={(e) => setSinif(e.target.value)}
            options={[
              { value: "", label: "Bütün sınıflar" },
              ...duzeyler.map((d) => ({ value: String(d.value), label: d.label })),
            ]}
          />
          <TextField
            className="w-40"
            label="Sıra sayısı"
            inputMode="numeric"
            value={sira}
            onChange={(e) => setSira(e.target.value)}
            error={siraNo === null ? `1 ile ${ODUL_SIRA_EN_COK} arası bir sayı yazın.` : undefined}
            helperText={`1 ile ${ODUL_SIRA_EN_COK} arası.`}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() =>
              raporlarApi.okumaOdulu({
                donem,
                sinif: sinifNo,
                sira: siraNo ?? ODUL_SIRA_VARSAYILAN,
              })
            }
            dosyaAdi={() => raporDosyaAdi(OKUMA_ODULU_ADI, kapsam)}
            onizlemeBasligi={OKUMA_ODULU_ADI}
            disabled={siraNo === null || eksikAralik(donem)}
            onHata={setHata}
          />
        </div>
        {hata && <ErrorBand hata={hata} />}
      </Card>
    </div>
  );
}
