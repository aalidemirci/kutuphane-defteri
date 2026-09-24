// Toplu katalog aktarımı paneli (tasarım §8.1) — Excel dosyası ve yapay zekâ
// köprüsünün JSON'u AYNI hattan geçer: önizle → kararları ver → uygula.
//
// ÖNİZLEME UYGULAMANIN PROVASIDIR. Sunucu gerçek yazmayı koşup geri sarar;
// ekrandaki sayılar uygulamanın yazacağı sayılardır. Bu yüzden panel iki ayrı
// "tahmin" ekranı tutmaz: tek rapor biçimi vardır (AktarimRaporu).
//
// Uygulama, önizlemenin gövdesinin AYNISINI gönderir — DOSYA DAHİL. Program
// yüklenen dosyayı saklamaz (yalnız içerik özetini tutar), bu yüzden onay
// anında dosya yeniden gönderilir. Kararlar ve bölüm eşlemesi de iki istekte
// aynı adlarla taşınır.
//
// Aynı dosyanın ikinci kez uygulanması ENGELDİR, uyarı değil (§8.1): kitaplar
// kayda iki kez girerdi. Önizleme bunu bant olarak söyler, uygulama reddeder.
//
// Her önizleme kalıcı bir koşu satırı yazar (aktarım geçmişi). Kullanıcı
// kararlarını değiştirip yeniden önizlediğinde ya da aktarımı uyguladığında
// önceki önizleme koşusu İPTAL edilir; yoksa geçmiş yarım denemelerle dolar.

import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber, todayIso } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { ACQUISITION_METHOD_TR, kutuphaneApi } from "./api";
import type {
  AcquisitionMethod,
  AktarimGovdesi,
  AktarimKarari,
  AktarimRaporu,
  AktarimUygulamaGovdesi,
  CommissionDecision,
  Section,
} from "./api";
import AktarimRaporuGorunumu, { YENI_BOLUM, kararCoz } from "./AktarimRaporu";
import KopruKomutuKarti from "./KopruKomutuKarti";
import { MetinAlani, SECICI_SINIRI, kararEtiketi, kodSecenekleri } from "./ortak";
import { barkodBicimle } from "./tarama";

export type AktarimKaynagiSecimi = "excel" | "kopru";

const DOSYA_TURLERI =
  ".xlsx,.xls,application/vnd.ms-excel," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export default function AktarimPaneli({
  kaynak,
  bolumler,
  onAktarildi,
}: {
  kaynak: AktarimKaynagiSecimi;
  bolumler: Section[];
  /** Uygulama başarılı olunca çağrılır (geçmiş listesi tazelenir). */
  onAktarildi?: () => void;
}) {
  const [dosya, setDosya] = useState<File | null>(null);
  const [metin, setMetin] = useState("");
  // Köprü kapısı FAIL-CLOSED: §8.2'nin dört uyarısı ekranda değilken JSON
  // kutusu ve "Önizle" kapalıdır — okulun kitap listesini dışarı çıkaran adım
  // uyarılar görülmeden başlamasın.
  const [kopruHazir, setKopruHazir] = useState(false);
  const [rapor, setRapor] = useState<AktarimRaporu | null>(null);
  const [kararlar, setKararlar] = useState<Record<number, AktarimKarari>>({});
  const [bolumSecimi, setBolumSecimi] = useState<Record<string, string>>({});
  const [onizlemeKosusu, setOnizlemeKosusu] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  // Hata hangi adımdan geldi? Bant o adımın kartında durur: uygulama reddi
  // ekranın en altındadır, hatayı en üste yazmak kullanıcıyı boşa arattırırdı.
  const [hataAdimi, setHataAdimi] = useState<"girdi" | "uygulama">("girdi");

  // Uygulamanın açacağı edinim partisi (Md. 10/5 + kayıt-içi girişler).
  const [yol, setYol] = useState<AcquisitionMethod>("EXISTING_STOCK");
  const [tarih, setTarih] = useState(todayIso());
  const [kaynakNotu, setKaynakNotu] = useState("");
  const [birimFiyat, setBirimFiyat] = useState("");
  const [komisyonKarari, setKomisyonKarari] = useState("");
  const [notlar, setNotlar] = useState("");
  const [kararSecenekleri, setKararSecenekleri] = useState<CommissionDecision[]>([]);

  const { errors, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const dosyaRef = useRef<HTMLInputElement>(null);
  const dosyaId = useId();

  // Komisyon kararları YALNIZ bağış yolunda gerekir (Md. 10/3); liste o seçilince
  // okunur — her açılışta bir istek daha atmanın anlamı yok.
  useEffect(() => {
    if (yol !== "DONATION") return;
    let iptal = false;
    kutuphaneApi
      .listCommissionDecisions({ limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (!iptal) setKararSecenekleri(sayfa.results);
      })
      .catch(() => {
        if (!iptal) setKararSecenekleri([]);
      });
    return () => {
      iptal = true;
    };
  }, [yol]);

  /** Yarım kalan önizleme koşusunu geçmişten düşürür (akışı durdurmaz). */
  const kosuyuBirak = async (id: number | null): Promise<void> => {
    if (id === null) return;
    try {
      await kutuphaneApi.aktarimiIptalEt(id);
    } catch {
      // İptal edilemezse geçmişte bir önizleme satırı kalır; aktarım etkilenmez.
    }
  };

  /** Girdi değişti: eski önizleme geçersizdir, kararlar da o dosyaya aitti. */
  const sifirla = (): void => {
    void kosuyuBirak(onizlemeKosusu);
    setOnizlemeKosusu(null);
    setRapor(null);
    setKararlar({});
    setBolumSecimi({});
    setHata(null);
  };

  const govdeKur = (): AktarimGovdesi => {
    const bolumEslemesi: Record<string, number> = {};
    const yeniBolumler: string[] = [];
    for (const [deger, secim] of Object.entries(bolumSecimi)) {
      if (!secim) continue;
      if (secim === YENI_BOLUM) yeniBolumler.push(deger);
      else bolumEslemesi[deger] = Number(secim);
    }
    const ortak: AktarimGovdesi = {};
    if (Object.keys(kararlar).length > 0) ortak.decisions = kararlar;
    if (Object.keys(bolumEslemesi).length > 0) ortak.section_map = bolumEslemesi;
    if (yeniBolumler.length > 0) ortak.new_sections = yeniBolumler;
    return kaynak === "excel"
      ? { ...ortak, file: dosya, source: "EXCEL" }
      : { ...ortak, payload: metin.trim() };
  };

  const girdiVar = kaynak === "excel" ? dosya !== null : kopruHazir && metin.trim().length > 0;

  const onizle = async (): Promise<void> => {
    if (!girdiVar) {
      setHataAdimi("girdi");
      setHata({
        message:
          kaynak === "excel"
            ? "Önce içe aktarılacak dosyayı seçin."
            : "Önce yapay zekâ aracının verdiği JSON metnini yapıştırın.",
        parolaGerekli: false,
      });
      return;
    }
    setBusy(true);
    setHata(null);
    clearErrors();
    const oncekiKosu = onizlemeKosusu;
    try {
      const sonuc = await kutuphaneApi.aktarimOnizle(govdeKur());
      void kosuyuBirak(oncekiKosu);
      setRapor(sonuc);
      setOnizlemeKosusu(sonuc.run_id);
    } catch (e) {
      applyApiError(e);
      setHataAdimi("girdi");
      setHata(hataOku(e, "Önizleme yapılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const uygula = async (): Promise<void> => {
    setBusy(true);
    setHata(null);
    clearErrors();
    const govde: AktarimUygulamaGovdesi = {
      ...govdeKur(),
      method: yol,
      date: tarih || null,
      source_note: kaynakNotu.trim(),
      unit_price: birimFiyat.trim() || null,
      commission_decision: komisyonKarari ? Number(komisyonKarari) : null,
      notes: notlar.trim(),
    };
    try {
      const sonuc = await kutuphaneApi.aktarimiUygula(govde);
      void kosuyuBirak(onizlemeKosusu);
      setOnizlemeKosusu(null);
      setRapor(sonuc);
      snackbar.success(
        `${formatNumber(sonuc.stats.copies_created)} nüsha açıldı; aktarım tamamlandı.`,
      );
      onAktarildi?.();
    } catch (e) {
      applyApiError(e);
      setHataAdimi("uygulama");
      setHata(hataOku(e, "Aktarım uygulanamadı."));
    } finally {
      setBusy(false);
    }
  };

  const onizleme = rapor !== null && rapor.dry_run;
  const eksikler = rapor === null ? [] : uygulamaEngelleri(rapor);
  const uygulanabilir = onizleme && eksikler.length === 0;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      {kaynak === "kopru" && <KopruKomutuKarti onDurum={setKopruHazir} />}

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        {kaynak === "excel" ? (
          <div>
            <p className="text-title-medium text-on-surface">Excel dosyasından katalog aktar</p>
            <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
              Katalog şablonunu ya da okulun kendi listesini yükleyin. Dosyanın “Katalog” sayfası
              okunur; sayfa yoksa ilk sayfa okunur. Başlık satırında “Eser Adı” sütunu ve en az bir
              künye sütunu daha bulunmalıdır.
            </p>
            <label
              htmlFor={dosyaId}
              className="mb-1 mt-4 block text-label-large text-on-surface-variant"
            >
              Dosya (.xlsx ya da Excel 97-2003 .xls)
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                id={dosyaId}
                ref={dosyaRef}
                type="file"
                accept={DOSYA_TURLERI}
                onChange={(e) => {
                  setDosya(e.target.files?.[0] ?? null);
                  sifirla();
                }}
                className="block min-h-[var(--kd-field-height)] flex-1 rounded-shape-sm border border-outline bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1.5 file:text-label-large file:text-on-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              />
              {dosya && (
                <Button
                  variant="text"
                  icon="close"
                  onClick={() => {
                    if (dosyaRef.current) dosyaRef.current.value = "";
                    setDosya(null);
                    sifirla();
                  }}
                >
                  Dosyayı kaldır
                </Button>
              )}
            </div>
            {errors.file && (
              <p role="alert" className="mt-1 text-body-small text-error">
                {errors.file}
              </p>
            )}
          </div>
        ) : (
          <MetinAlani
            label="Yapay zekâ aracının verdiği JSON"
            rows={6}
            value={metin}
            disabled={!kopruHazir}
            onChange={(deger) => {
              setMetin(deger);
              sifirla();
            }}
            placeholder='{"schema_version": "v1", "items": [ … ]}'
            error={errors.payload}
            helperText={
              kopruHazir
                ? "Aracın verdiği metnin tamamını (süslü parantezle başlayıp biten bölümü) yapıştırın."
                : "Yukarıdaki uyarılar ekrana gelene kadar köprü kullanılamaz."
            }
          />
        )}

        {hata && hataAdimi === "girdi" && <ErrorBand hata={hata} />}

        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            variant="tonal"
            icon="visibility"
            onClick={() => void onizle()}
            disabled={busy || (kaynak === "kopru" && !kopruHazir)}
          >
            {busy ? "Çalışıyor…" : rapor === null ? "Önizle" : "Yeniden önizle"}
          </Button>
        </div>
      </Card>

      {rapor && (
        <AktarimRaporuGorunumu
          rapor={rapor}
          bolumler={bolumler}
          kararlar={kararlar}
          onKarar={(satir, deger) =>
            setKararlar((onceki) => {
              const sonraki = { ...onceki };
              const karar = kararCoz(deger);
              if (karar === null) delete sonraki[satir];
              else sonraki[satir] = karar;
              return sonraki;
            })
          }
          bolumSecimi={bolumSecimi}
          onBolum={(deger, secim) => setBolumSecimi((onceki) => ({ ...onceki, [deger]: secim }))}
        />
      )}

      {onizleme && (
        <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <div>
            <p className="text-title-medium text-on-surface">Açılacak Edinim Partisi</p>
            <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
              Aktarılan bütün nüshalar tek bir edinim partisinden doğar; kayıt defterinde parti
              böyle görünür. Mevcut koleksiyonu programa ilk kez aktarıyorsanız yolu değiştirmeyin.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Select
              label="Edinim yolu"
              value={yol}
              onChange={(e) => setYol(e.target.value as AcquisitionMethod)}
              options={kodSecenekleri(ACQUISITION_METHOD_TR)}
              error={errors.method}
            />
            <TextField
              label="Tarih"
              type="date"
              value={tarih}
              onChange={(e) => setTarih(e.target.value)}
              error={errors.date}
            />
            <TextField
              label="Birim fiyat"
              inputMode="decimal"
              value={birimFiyat}
              onChange={(e) => setBirimFiyat(e.target.value)}
              error={errors.unit_price}
              helperText="İsteğe bağlı; satın almada kayıt defterine yazılır."
            />
            <TextField
              className="sm:col-span-2"
              label="Bağışçı ya da satıcı"
              value={kaynakNotu}
              onChange={(e) => setKaynakNotu(e.target.value)}
              error={errors.source_note}
              helperText="Kişi adı yazarsanız kayıt şifreli tutulur."
            />
            {yol === "DONATION" && (
              <Select
                label="Komisyon kararı"
                required
                placeholder="Seçin"
                value={komisyonKarari}
                onChange={(e) => setKomisyonKarari(e.target.value)}
                options={kararSecenekleri.map((k) => ({
                  value: String(k.id),
                  label: kararEtiketi(k),
                }))}
                error={errors.commission_decision}
                helperText="Bağışta karar zorunludur (Md. 10/3)."
              />
            )}
          </div>
          <MetinAlani
            label="Notlar"
            rows={2}
            value={notlar}
            onChange={setNotlar}
            error={errors.notes}
          />

          {hata && hataAdimi === "uygulama" && <ErrorBand hata={hata} />}

          {eksikler.length > 0 && (
            <ul className="list-disc space-y-1 rounded-shape-sm bg-tertiary-container px-6 py-3 text-body-small text-on-tertiary-container">
              {eksikler.map((eksik) => (
                <li key={eksik}>{eksik}</li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button icon="upload" onClick={() => void uygula()} disabled={busy || !uygulanabilir}>
              Uygula
            </Button>
          </div>
        </Card>
      )}

      {rapor && !rapor.dry_run && <SonucKarti rapor={rapor} />}
    </div>
  );
}

/**
 * Uygulamanın önündeki engeller — sunucunun `_require_ready` kapılarının
 * kullanıcı diline çevrilmiş hâli. İstek atılmadan söylenmesinin sebebi:
 * kullanıcı "Uygula"ya basıp 400 almasın, ne eksik olduğunu önce görsün.
 */
function uygulamaEngelleri(rapor: AktarimRaporu): string[] {
  const engeller: string[] = [];
  if (rapor.already_applied) {
    engeller.push(
      `Bu dosya ${rapor.applied_at} tarihinde zaten aktarıldı; aynı dosya ikinci kez uygulanamaz.`,
    );
  }
  if (rapor.pending_decisions.length > 0) {
    engeller.push(
      `${formatNumber(rapor.pending_decisions.length)} satır karar bekliyor. Kararları verip ` +
        "“Yeniden önizle” deyin.",
    );
  }
  if (rapor.unknown_sections.length > 0) {
    engeller.push(
      `${formatNumber(rapor.unknown_sections.length)} bölüm değerinin karşılığı verilmedi. ` +
        "Karşılıklarını seçip “Yeniden önizle” deyin.",
    );
  }
  if (rapor.stats.imported_rows === 0) {
    engeller.push("Aktarılabilecek satır yok; dosyadaki sorunları giderip yeniden önizleyin.");
  }
  return engeller;
}

/**
 * Uygulamadan sonra açılan parti ve "Bu partinin etiketlerini bas" kısayolu
 * (tasarım §8.1): Etiketler → Basım Kuyruğu o edinim partisine süzülmüş açılır
 * (`?edinim=`); nüsha kimlikleri taşınmaz, kuyruk partiyi kendisi bulur.
 */
function SonucKarti({ rapor }: { rapor: AktarimRaporu }) {
  const parti = rapor.label_batch;
  return (
    <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="flex items-center gap-2 text-title-medium text-on-surface">
        <Icon name="check_circle" size="lg" className="text-primary" />
        Aktarım tamamlandı
      </p>
      {parti === null ? (
        <p className="text-body-medium text-on-surface-variant">Bu aktarımda nüsha açılmadı.</p>
      ) : (
        <>
          <p className="text-body-medium text-on-surface">
            {formatNumber(parti.copy_count)} nüsha açıldı. Barkodlar{" "}
            {barkodBicimle(parti.first_barcode)} ile {barkodBicimle(parti.last_barcode)} arasında.
          </p>
          <p className="text-body-small text-on-surface-variant">
            Bu nüshaların etiketleri henüz basılmadı; Etiketler → Basım Kuyruğu'nda bekler. Yer
            numarası sırasında basıp raf raf yapıştırabilirsiniz.
          </p>
          <div className="flex justify-end">
            <Link
              to={`/katalog/etiketler?edinim=${parti.acquisition}`}
              className="inline-flex min-h-[var(--kd-control-height)] items-center gap-2 rounded-shape-md border border-outline-variant bg-surface-container-lowest px-4 text-label-large font-semibold text-primary transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Icon name="print" size="lg" />
              Bu partinin etiketlerini bas
            </Link>
          </div>
        </>
      )}
    </Card>
  );
}
