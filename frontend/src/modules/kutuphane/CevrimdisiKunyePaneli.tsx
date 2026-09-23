// Çevrimdışı künye yolu (U13'ün ikinci yarısı, tasarım §8.5): künyesi eksik
// eserlerin ISBN listesi dışa aktarılır → internete bağlı BAŞKA bir cihazda
// doldurulur → dosya geri yüklenir.
//
// AYRI CİHAZ DEMEKTİR: kurum bilgisayarına telefon, mobil modem ya da kişisel
// erişim noktası bağlanarak internet alınamaz (Millî Eğitim Bakanlığı Bilgi ve
// Sistem Güvenliği Yönergesi 11/18). Bu cümle dosyanın "Bilgi" sayfasında da
// yazılıdır; mevzuatın adı `docs/mevzuat/`teki metinden doğrulanır
// (CLAUDE.md §2-13) ve tek kopyası `YONERGE` sabitidir.
//
// Bu ekran hiçbir dış istek atmaz: dosyayı program üretir, dosyayı program
// okur. Künye Getirme ayarı KAPALIYKEN de çalışır — çevrimdışı yol tam da ağı
// olmayan masa içindir.
//
// Yazma yine kullanıcının onayıyladır: önizlemede her alanın kendi kutusu
// vardır, dolu alan işaretsiz gelir ve "Seçilenleri kaydet" dendiğinde yalnız
// işaretli alanlar eserin kendi güncelleme isteğiyle yazılır (§8.5-5).

import { useRef, useState } from "react";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatNumber } from "../../lib/format";
import { YONERGE } from "../../lib/mevzuat";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import {
  CEVRIMDISI_KUNYE_DURUMU_TR,
  KUNYE_LISTESI_BELGE_ADI,
  kunyeListesiDosyaAdi,
  kutuphaneApi,
} from "./api";
import type { CevrimdisiKunyeDurumu, CevrimdisiKunyeOnizleme, CevrimdisiKunyeSatiri } from "./api";
import KunyeAlanlari, { kunyeGovdesi, secilenAlanVar, varsayilanSecim } from "./KunyeAlanlari";
import type { KunyeSecimi } from "./KunyeAlanlari";

/** Satır numarası → o satırdaki alan seçimi. */
type SatirSecimleri = Record<number, KunyeSecimi>;

export default function CevrimdisiKunyePaneli() {
  const [onizleme, setOnizleme] = useState<CevrimdisiKunyeOnizleme | null>(null);
  const [secimler, setSecimler] = useState<SatirSecimleri>({});
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [yazilan, setYazilan] = useState<number | null>(null);
  const dosyaRef = useRef<HTMLInputElement>(null);
  const snackbar = useSnackbar();

  const indir = async (): Promise<void> => {
    setBusy(true);
    setHata(null);
    try {
      saveBlob(await kutuphaneApi.kunyeListesiIndir(), kunyeListesiDosyaAdi());
      snackbar.success(`${KUNYE_LISTESI_BELGE_ADI} indirildi.`);
    } catch (e) {
      setHata(hataOku(e, "ISBN künye listesi indirilemedi."));
    } finally {
      setBusy(false);
    }
  };

  const dosyaSecildi = async (dosya: File | null): Promise<void> => {
    setOnizleme(null);
    setSecimler({});
    setYazilan(null);
    setHata(null);
    if (dosya === null) return;
    setBusy(true);
    try {
      const sonuc = await kutuphaneApi.kunyeDosyasiOnizle(dosya);
      setOnizleme(sonuc);
      const baslangic: SatirSecimleri = {};
      for (const satir of sonuc.satirlar) {
        baslangic[satir.satir_no] = varsayilanSecim(satir.alanlar);
      }
      setSecimler(baslangic);
    } catch (e) {
      setHata(hataOku(e, "Künye dosyası okunamadı."));
    } finally {
      setBusy(false);
    }
  };

  /** Seçilen alanları eserlere yazar (her eser kendi güncelleme isteğiyle). */
  const kaydet = async (): Promise<void> => {
    if (onizleme === null) return;
    setBusy(true);
    setHata(null);
    let sayac = 0;
    try {
      for (const satir of onizleme.satirlar) {
        if (satir.work === null) continue;
        const govde = kunyeGovdesi(satir.alanlar, secimler[satir.satir_no] ?? {});
        if (Object.keys(govde).length === 0) continue;
        await kutuphaneApi.updateWork(satir.work, govde);
        sayac += 1;
      }
      setYazilan(sayac);
      snackbar.success(
        sayac === 0 ? "Seçili alan yok; hiçbir kayıt değişmedi." : `${sayac} eser güncellendi.`,
      );
    } catch (e) {
      setHata(hataOku(e, "Künyeler kaydedilemedi."));
      if (e instanceof ApiError) setYazilan(sayac);
    } finally {
      setBusy(false);
    }
  };

  const yazilabilirSatirlar = (onizleme?.satirlar ?? []).filter(
    (satir) => satir.work !== null && secilenAlanVar(satir.alanlar, secimler[satir.satir_no] ?? {}),
  );

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-title-medium text-on-surface">{KUNYE_LISTESI_BELGE_ADI}</p>
            <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
              Künyesi eksik eserlerin ISBN listesini indirin, boş hücreleri internete bağlı{" "}
              <strong>başka bir cihazda</strong> doldurun ve dosyayı buraya geri yükleyin. Kurum
              bilgisayarına telefon, mobil modem ya da kişisel erişim noktası bağlanarak internet
              alınamaz ({YONERGE} 11/18); taşınabilir bellekle taşırken Yönerge 10/4 ve 10/5
              kuralları geçerlidir.
            </p>
          </div>
          <Button variant="outlined" icon="download" onClick={() => void indir()} disabled={busy}>
            ISBN listesini indir
          </Button>
        </div>

        <p className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-small text-on-secondary-container">
          <Icon name="info" size="lg" className="mt-0.5 shrink-0" />
          <span>
            Dosyaya öğrenci, veli ya da personel bilgisi yazmayın; bu dosya yalnız kitap künyesi
            taşır. “Eser No” ve “ISBN” sütunlarını değiştirmeyin: eşleşme o iki sütundan yapılır.
            Çevirmen sütunu yoktur; çeviri eserde çevirmeni programda elle yazarsınız.
          </span>
        </p>

        <div>
          <label
            htmlFor="cevrimdisi-kunye-dosyasi"
            className="mb-1 block text-label-large text-on-surface-variant"
          >
            Doldurulmuş dosya (.xlsx ya da .csv)
          </label>
          <input
            id="cevrimdisi-kunye-dosyasi"
            ref={dosyaRef}
            type="file"
            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => void dosyaSecildi(e.target.files?.[0] ?? null)}
            className="block min-h-[var(--kd-field-height)] w-full rounded-shape-sm border border-outline bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1.5 file:text-label-large file:text-on-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
        </div>

        {hata && <ErrorBand hata={hata} />}
      </Card>

      {onizleme && (
        <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <div>
            <p className="text-title-medium text-on-surface">Önizleme</p>
            <p className="mt-0.5 text-body-small text-on-surface-variant">
              Hiçbir kayıt değişmedi. Aşağıda işaretlediğiniz alanlar “Seçilenleri kaydet”
              dediğinizde yazılır; dolu alanlar işaretsiz gelir.
            </p>
          </div>

          <SayimSatiri sayilar={onizleme.sayilar} />

          {onizleme.atlanan_sutunlar.length > 0 && (
            <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-small text-on-tertiary-container">
              <Icon name="warning" size="lg" className="mt-0.5 shrink-0" />
              <span>Yok sayılan sütunlar: {onizleme.atlanan_sutunlar.join(", ")}.</span>
            </p>
          )}

          {onizleme.satirlar.length === 0 ? (
            <EmptyState
              compact
              icon="description"
              title="Dosyada okunacak satır yok"
              description="Dosyanın “Künye” sayfasını doldurup yeniden yükleyin."
            />
          ) : (
            <div className="space-y-4">
              {onizleme.satirlar.map((satir) => (
                <SatirKarti
                  key={satir.satir_no}
                  satir={satir}
                  kaynakEtiketi={onizleme.kaynak_etiketi}
                  rozet={onizleme.rozet}
                  secim={secimler[satir.satir_no] ?? {}}
                  onSecim={(alan, secili) =>
                    setSecimler((onceki) => ({
                      ...onceki,
                      [satir.satir_no]: { ...(onceki[satir.satir_no] ?? {}), [alan]: secili },
                    }))
                  }
                />
              ))}
            </div>
          )}

          {yazilan !== null && (
            <p className="text-body-medium text-on-surface">
              {yazilan === 0
                ? "Hiçbir alan seçilmediği için kayıt değişmedi."
                : `${formatNumber(yazilan)} eserin künyesi güncellendi.`}
            </p>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              icon="check"
              onClick={() => void kaydet()}
              disabled={busy || yazilabilirSatirlar.length === 0}
            >
              {busy
                ? "Kaydediliyor…"
                : `Seçilenleri kaydet (${formatNumber(yazilabilirSatirlar.length)} eser)`}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function SayimSatiri({ sayilar }: { sayilar: Record<CevrimdisiKunyeDurumu, number> }) {
  const durumlar = Object.keys(CEVRIMDISI_KUNYE_DURUMU_TR) as CevrimdisiKunyeDurumu[];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {durumlar.map((durum) => (
        <div key={durum} className="rounded-shape-sm bg-surface-container px-3 py-2">
          <dt className="text-label-small text-on-surface-variant">
            {CEVRIMDISI_KUNYE_DURUMU_TR[durum]}
          </dt>
          <dd className="text-title-medium text-on-surface">{formatNumber(sayilar[durum] ?? 0)}</dd>
        </div>
      ))}
    </dl>
  );
}

function SatirKarti({
  satir,
  kaynakEtiketi,
  rozet,
  secim,
  onSecim,
}: {
  satir: CevrimdisiKunyeSatiri;
  kaynakEtiketi: string;
  rozet: string;
  secim: KunyeSecimi;
  onSecim: (alan: string, secili: boolean) => void;
}) {
  const eslesti = satir.durum === "eslesti" && satir.work !== null;
  return (
    <div className="space-y-2 rounded-shape-md bg-surface-container-low p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-label-large text-on-surface">
          Satır {satir.satir_no}: {satir.work_title || satir.isbn13 || "—"}
        </p>
        <span className="inline-flex rounded-full bg-surface-container-highest px-2 py-0.5 text-label-small text-on-surface-variant">
          {CEVRIMDISI_KUNYE_DURUMU_TR[satir.durum]}
        </span>
      </div>
      {eslesti ? (
        <KunyeAlanlari
          alanlar={satir.alanlar}
          secim={secim}
          onSecim={onSecim}
          kaynakEtiketi={kaynakEtiketi}
          rozet={rozet}
          uyarilar={satir.uyarilar}
          baslik="Dosyadan gelen künye"
        />
      ) : (
        <p className="text-body-small text-on-surface-variant">
          Bu satır bir esere bağlanamadı, bu yüzden yazılamaz. ISBN sütununu değiştirmeden
          doldurduğunuzdan emin olun.
        </p>
      )}
    </div>
  );
}
