// Raporlar → Çok Okunanlar (F10; tasarım §5.3, §10 E12).
//
// Liste gün değişimi kapısında her gün hesaplanır ve `kd_katalog_populer` tablosuna yazılır;
// ekran bu tabloyu okur (Ağ Kataloğu vitrini ve Ayın Kitapları afişiyle aynı kaynak). Eşik
// en az k FARKLI üyedir: aynı üyenin tekrar tekrar alması eseri listeye sokmaz. SAYI YOKTUR,
// yalnız sıra (profil yasağı). Kapanan dönem ve ay son hâliyle kalır ("Kapandı" rozeti).
//
// "Yeniden hesapla" kapıdaki günlük işin aynısını şimdi yapar (eşik değişince ya da ay başında
// afiş basılırken liste ertesi güne kalmasın). Geri yükleme sürerken sunucu 503 `bakimda`
// döner; ileti olduğu gibi yazılır. Ayın Kitapları afişi (E12) ay listesinin kartından basılır.

import { useCallback, useEffect, useState } from "react";

import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { Rozet } from "../ayiklama/ortak";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { AYIN_KITAPLARI_ADI, raporDosyaAdi, raporlarApi } from "./api";
import type { CokOkunanlar, Pencere, PencereBilgisi, PencereTuru } from "./api";

/** Bölümün açıklaması (kılavuz aynı kuralı anlatır). */
export function cokOkunanlarAciklamasi(k: number): string {
  return (
    `Bir eser listeye ancak en az ${formatNumber(k)} farklı üye ödünç aldıysa girer; aynı ` +
    "üyenin tekrar tekrar alması eseri listeye sokmaz. Sıra farklı üye sayısına göredir ve " +
    "hiçbir sayı gösterilmez. Liste her gün kendiliğinden yenilenir; kapanan dönem ve ay son " +
    "hâliyle kalır. Dönem listesi Ağ Kataloğu vitrininde, ay listesi Ayın Kitapları afişinde " +
    "kullanılır."
  );
}

/** Liste boşken (henüz eşiği geçen eser yokken). */
export function bosListe(k: number): string {
  return `Henüz liste yok: en az ${formatNumber(k)} farklı üyenin ödünç aldığı eser bulunmuyor.`;
}

export const YENIDEN_HESAPLANDI = "Çok okunanlar yeniden hesaplandı.";

function SiraListesi({ pencere }: { pencere: Pencere }) {
  if (pencere.works.length === 0) {
    return <p className="text-body-medium text-on-surface-variant">Bu listede eser yok.</p>;
  }
  return (
    <ol aria-label={`${pencere.label} sırası`} className="space-y-1.5">
      {pencere.works.map((e) => (
        <li key={e.work_id} className="flex items-baseline gap-3">
          <span className="w-6 shrink-0 text-right text-label-large font-semibold text-primary">
            {`${e.rank}.`}
          </span>
          <span className="min-w-0">
            <span className="text-body-medium font-semibold text-on-surface">{e.title}</span>
            {e.authors && (
              <span className="text-body-small text-on-surface-variant">{` — ${e.authors}`}</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

function PencereKarti({
  baslik,
  aciklama,
  secimEtiketi,
  tur,
  pencereler,
  ilk,
  k,
}: {
  baslik: string;
  aciklama: string;
  secimEtiketi: string;
  tur: PencereTuru;
  pencereler: PencereBilgisi[];
  ilk: Pencere | null;
  k: number;
}) {
  const [secilen, setSecilen] = useState(ilk?.window ?? "");
  const [pencere, setPencere] = useState<Pencere | null>(ilk);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  // Yeniden hesaplamadan sonra sayfa yeni özeti getirir (yeni nesne): seçim en son pencereye
  // döner.
  useEffect(() => {
    setSecilen(ilk?.window ?? "");
    setPencere(ilk);
    setHata(null);
  }, [ilk]);

  const sec = async (deger: string) => {
    setSecilen(deger);
    setHata(null);
    try {
      setPencere(await raporlarApi.pencere(tur, deger));
    } catch (e) {
      setPencere(null);
      setHata(hataOku(e, "Liste yüklenemedi."));
    }
  };

  return (
    <section aria-label={baslik}>
      <Card
        elevation={0}
        className="h-full space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <div>
          <h2 className="text-title-medium font-semibold text-on-surface">{baslik}</h2>
          <p className="mt-0.5 text-body-small text-on-surface-variant">{aciklama}</p>
        </div>
        {pencereler.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">{bosListe(k)}</p>
        ) : (
          <>
            <Select
              className="max-w-xs"
              label={secimEtiketi}
              value={secilen}
              onChange={(e) => void sec(e.target.value)}
              options={pencereler.map((p) => ({ value: p.window, label: p.label }))}
            />
            {hata && <ErrorBand hata={hata} />}
            {pencere && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  {pencere.frozen ? (
                    <Rozet ton="notr" icon="lock">
                      Kapandı
                    </Rozet>
                  ) : (
                    <Rozet ton="ikincil" icon="autorenew">
                      Sürüyor
                    </Rozet>
                  )}
                  <span className="text-body-small text-on-surface-variant">
                    {`Son hesap: ${formatDate(pencere.computed_on)}`}
                  </span>
                </div>
                <SiraListesi pencere={pencere} />
                {tur === "AY" && <AfisDugmeleri pencere={pencere} />}
              </>
            )}
          </>
        )}
      </Card>
    </section>
  );
}

function AfisDugmeleri({ pencere }: { pencere: Pencere }) {
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  return (
    <div className="space-y-2 border-t border-outline-variant/60 pt-3">
      <p className="text-label-large font-semibold text-on-surface">{AYIN_KITAPLARI_ADI}</p>
      <p className="text-body-small text-on-surface-variant">
        Okul girişine ya da kütüphaneye asılacak tek sayfalık afiş: sıra, kaynak adı ve yazar. Sayı
        ve kişi bilgisi yoktur. Süren ayın afişi, kartta &ldquo;Son hesap&rdquo; diye yazan günün
        sırasıyla basılır.
      </p>
      <div className="flex flex-wrap gap-2">
        <PdfDugmeleri
          pdfAl={() => raporlarApi.afis(pencere.window)}
          dosyaAdi={() => raporDosyaAdi(AYIN_KITAPLARI_ADI, pencere.label)}
          onizlemeBasligi={`${AYIN_KITAPLARI_ADI} — ${pencere.label}`}
          disabled={pencere.works.length === 0}
          onHata={setHata}
        />
      </div>
      {hata && <ErrorBand hata={hata} />}
    </div>
  );
}

export default function CokOkunanlarBolumu() {
  const [ozet, setOzet] = useState<CokOkunanlar | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  const yukle = useCallback(async () => {
    try {
      setOzet(await raporlarApi.cokOkunanlar());
      setHata(null);
    } catch (e) {
      setHata(hataOku(e, "Çok okunanlar yüklenemedi."));
    }
  }, []);

  useEffect(() => {
    void yukle();
  }, [yukle]);

  const yenidenHesapla = async () => {
    setBusy(true);
    setHata(null);
    try {
      await raporlarApi.yenidenHesapla();
      await yukle();
      snackbar.success(YENIDEN_HESAPLANDI);
    } catch (e) {
      setHata(hataOku(e, "Çok okunanlar yeniden hesaplanamadı."));
    } finally {
      setBusy(false);
    }
  };

  if (ozet === null) {
    return hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={4} />;
  }

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card
        elevation={0}
        className="flex flex-wrap items-start justify-between gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1"
      >
        <p className="max-w-3xl text-body-medium text-on-surface">
          {cokOkunanlarAciklamasi(ozet.k_threshold)}
        </p>
        <Button
          variant="tonal"
          icon="refresh"
          onClick={() => void yenidenHesapla()}
          disabled={busy}
        >
          {busy ? "Hesaplanıyor…" : "Yeniden hesapla"}
        </Button>
      </Card>
      {hata && <ErrorBand hata={hata} />}
      <div className="grid gap-[var(--kd-page-gap)] lg:grid-cols-2">
        <PencereKarti
          baslik="Dönemin Çok Okunanları"
          aciklama="Ders dönemine göre; Ağ Kataloğu vitrininde bu liste görünür."
          secimEtiketi="Dönem"
          tur="DONEM"
          pencereler={ozet.term_windows}
          ilk={ozet.term}
          k={ozet.k_threshold}
        />
        <PencereKarti
          baslik="Ayın Kitapları"
          aciklama="Takvim ayına göre; Ayın Kitapları afişi bu listeden basılır."
          secimEtiketi="Ay"
          tur="AY"
          pencereler={ozet.month_windows}
          ilk={ozet.month}
          k={ozet.k_threshold}
        />
      </div>
    </div>
  );
}
