// Yıl Sonu Raporu (F8; Yönetmelik Md. 12/1, Uygulama Kılavuzu 2.4, tasarım §10 E9).
// Menüde yoktur: Genel Bakış'ın yıl sonu penceresindeki kartından ve Yıl Sonu ekranının
// son adımından açılır. YALNIZ yönetici kipinde.
//
// Md. 12/1: ders yılı sonunda kaynaklar gözden geçirilir ve tespit edilen hususlar
// raporla okul müdürlüğüne bildirilir. Rapor ders yılı başına BİR kayıttır; sayıları
// kişisizdir ve sunucudan gelir (profil yasağı — üye bazında hiçbir şey yok; üye türü ve
// sınıf düzeyi kırılımı k farklı üyenin altında gösterilmez). "Raporu sonlandır" sayıları
// dondurur; yeniden basılan rapor aynı sayıları taşır; sonlandırma geri alınabilir.
//
// Serbest metin ("Tespit edilen hususlar") kütüphane yöneticisinindir; ekran kişi adı
// yazılmamasını söyler (program metni denetleyemez).
//
// Kaydedilmemiş değişiklik (sayı, tarih, tespit) sonlandırmada önce kaydedilir ve onay
// penceresi bunu söyler; belge satırı kaydedilmemiş değişikliğin belgeye girmediğini
// yazar (F8 düzeltme turu: "Raporu sonlandır" yazılan metni sessizce atıyordu).
//
// Dönem kuralı (25.09.2026 kullanıcı kararı, tasarım F8 ekleri 35 — seçenek a): dönem ders
// yılının başından SONRAKİ ders yılının başına dektir; sonraki yıl tanımlanmadan (Haziran'da)
// sonlandırılan rapor ders yılı sonunda kapanır. Kural değişmedi; ekran bunu
// `YAZ_DONEMI_UYARISI` ile söyler, onay penceresi dönemi yazar.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { MetinAlani } from "../kutuphane/ortak";
import { ILISIK_LISTESI_ADRESI, YIL_SONU_ADRESI, yilApi } from "../yil/api";
import type { YilAkislari } from "../yil/api";
import { YanEkranBaglantilari } from "../yil/ortak";
import { YIL_SONU_RAPORU_BASLIGI, YIL_SONU_RAPORU_BELGESI, ayiklamaApi } from "./api";
import type { RaporSayilari, YilRaporu, YilRaporuSatiri } from "./api";
import { BelgeSatiri, Bilgi, Rozet } from "./ortak";

/** "Tespit edilen hususlar" alanının yardım metni (sunucu modelinin yardım metniyle aynı). */
export const TESPIT_YARDIMI = "Kaynakların durumu ve öneriler. Kişi adı yazmayın.";

/** Raporun dönemi yaz aylarını ancak yeni ders yılı tanımlanınca kapsar (F8 ekleri 35). */
export const YAZ_DONEMI_UYARISI =
  "Raporu yeni ders yılı tanımlandıktan sonra sonlandırmanız önerilir; Haziran'da " +
  "sonlandırırsanız yaz aylarındaki işler (ör. Ağustos'taki ayıklama) bu rapora girmez. " +
  "Gerekirse sonlandırmayı geri alıp yeni ders yılı tanımlandıktan sonra yeniden sonlandırın.";

export default function YilSonuRaporuPage() {
  const [params, setParams] = useSearchParams();
  const secilen = Number(params.get("rapor")) || null;
  const [raporlar, setRaporlar] = useState<YilRaporuSatiri[] | null>(null);
  const [akislar, setAkislar] = useState<YilAkislari | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [tazeleme, setTazeleme] = useState(0);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    Promise.all([ayiklamaApi.raporlar(), yilApi.akislar().catch(() => null)])
      .then(([r, a]) => {
        if (iptal) return;
        setRaporlar(r.results);
        setAkislar(a);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Raporlar yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [tazeleme]);

  const sec = useCallback(
    (id: number) =>
      setParams((onceki) => {
        const yeni = new URLSearchParams(onceki);
        yeni.set("rapor", String(id));
        return yeni;
      }),
    [setParams],
  );

  const hazirla = async () => {
    setBusy(true);
    setHata(null);
    try {
      const rapor = await ayiklamaApi.raporAc();
      snackbar.success("Yıl sonu raporu hazırlandı.");
      setTazeleme((k) => k + 1);
      sec(rapor.id);
    } catch (e) {
      setHata(hataOku(e, "Rapor hazırlanamadı."));
    } finally {
      setBusy(false);
    }
  };

  const etkinYil = akislar?.year_end.school_year ?? null;
  const etkinYilRaporuYok =
    akislar !== null && etkinYil !== null && !akislar.year_end.annual_review;
  const gosterilen = secilen ?? raporlar?.[0]?.id ?? null;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{YIL_SONU_RAPORU_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            Her ders yılı sonunda kütüphane kaynakları gözden geçirilir ve tespit edilen hususlar
            raporla okul müdürlüğüne bildirilir (Yönetmelik Md. 12/1). Rapor kişisizdir: üye bazında
            bilgi içermez; sayılar programdaki kayıtlardan gelir.
          </p>
        </div>
        <YanEkranBaglantilari
          baglantilar={[
            { to: YIL_SONU_ADRESI, label: "Yıl Sonu", icon: "event_upcoming" },
            { to: ILISIK_LISTESI_ADRESI, label: "İlişik Listesi", icon: "fact_check" },
          ]}
        />
      </div>

      {hata && <ErrorBand hata={hata} />}

      {etkinYilRaporuYok && (
        <Card elevation={0} className="flex flex-wrap items-center justify-between gap-3 p-5">
          <p className="text-body-medium text-on-surface">
            {`${etkinYil?.name ?? ""} ders yılının raporu henüz hazırlanmadı.`}
          </p>
          <Button icon="note_add" onClick={() => void hazirla()} disabled={busy}>
            {busy ? "Hazırlanıyor…" : "Raporu hazırla"}
          </Button>
        </Card>
      )}

      {raporlar === null ? (
        !hata && <SkeletonList rows={4} />
      ) : raporlar.length === 0 ? (
        !etkinYilRaporuYok && (
          <EmptyState
            icon="summarize"
            title="Henüz yıl sonu raporu yok"
            description="Etkin ders yılı tanımlandıktan sonra rapor hazırlanır."
          />
        )
      ) : (
        <>
          {raporlar.length > 1 && (
            <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
              <Select
                className="w-64"
                label="Ders yılı"
                value={gosterilen === null ? "" : String(gosterilen)}
                onChange={(e) => sec(Number(e.target.value))}
                options={raporlar.map((r) => ({ value: String(r.id), label: r.school_year_name }))}
              />
            </Card>
          )}
          {gosterilen !== null && (
            <RaporAyrintisi
              key={gosterilen}
              id={gosterilen}
              onDegisti={() => setTazeleme((k) => k + 1)}
            />
          )}
        </>
      )}
    </div>
  );
}

function RaporAyrintisi({ id, onDegisti }: { id: number; onDegisti: () => void }) {
  const [rapor, setRapor] = useState<YilRaporu | null>(null);
  const [sayi, setSayi] = useState("");
  const [tarih, setTarih] = useState("");
  const [tespit, setTespit] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const doldur = (r: YilRaporu) => {
    setRapor(r);
    setSayi(r.document_no);
    setTarih(r.document_date ?? "");
    setTespit(r.findings);
  };

  useEffect(() => {
    let iptal = false;
    ayiklamaApi
      .rapor(id)
      .then((r) => {
        if (!iptal) doldur(r);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Rapor yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [id]);

  const calistir = async (is: () => Promise<YilRaporu>, ileti: string, yedek: string) => {
    setBusy(true);
    setHata(null);
    try {
      doldur(await is());
      snackbar.success(ileti);
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, yedek));
    } finally {
      setBusy(false);
    }
  };

  if (rapor === null) {
    return hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={4} />;
  }

  const sonlandirildi = rapor.is_finalized;
  /** Ekrandaki alanlar kayıttakinden farklı mı? (sonlandırma ve basım bunu bilir) */
  const kirli =
    !sonlandirildi &&
    (sayi.trim() !== rapor.document_no ||
      (tarih || null) !== (rapor.document_date ?? null) ||
      tespit.trim() !== rapor.findings);
  const alanlar = () => ({
    document_no: sayi.trim(),
    document_date: tarih || null,
    findings: tespit.trim(),
  });

  const kaydet = () =>
    calistir(
      () => ayiklamaApi.raporGuncelle(rapor.id, alanlar()),
      "Rapor kaydedildi.",
      "Rapor kaydedilemedi.",
    );

  const sonlandir = async () => {
    const donem = `${formatDate(rapor.stats.period.start)} – ${formatDate(rapor.stats.period.end)}`;
    const onay = await confirm({
      title: "Rapor sonlandırılsın mı?",
      message: `Sayılar ${donem} dönemine aittir ve bugünkü hâliyle dondurulur; yeniden basılan rapor aynı sayıları taşır. Sonlandırma geri alınabilir.${
        kirli ? " Kaydedilmemiş değişiklikler önce kaydedilir." : ""
      }`,
      confirmLabel: "Raporu sonlandır",
    });
    if (onay) {
      await calistir(
        async () => {
          if (kirli) await ayiklamaApi.raporGuncelle(rapor.id, alanlar());
          return ayiklamaApi.raporuSonlandir(rapor.id);
        },
        "Rapor sonlandırıldı.",
        "Rapor sonlandırılamadı.",
      );
    }
  };

  const geriAl = async () => {
    const onay = await confirm({
      title: "Sonlandırma geri alınsın mı?",
      message:
        "Dondurulan sayılar atılır; rapor yeniden düzenlenebilir ve sayılar basım anındaki kayıtlardan hesaplanır.",
      confirmLabel: "Sonlandırmayı geri al",
    });
    if (onay) {
      await calistir(
        () => ayiklamaApi.sonlandirmayiGeriAl(rapor.id),
        "Sonlandırma geri alındı.",
        "Sonlandırma geri alınamadı.",
      );
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-title-large font-semibold text-on-surface">
            {`${rapor.school_year_name} ders yılı`}
          </h2>
          {sonlandirildi ? (
            <Rozet ton="ikincil" icon="lock">
              {`Sonlandırıldı · ${formatDate(rapor.finalized_at)}`}
            </Rozet>
          ) : (
            <Rozet ton="notr">Taslak</Rozet>
          )}
        </div>
        {hata && <ErrorBand hata={hata} />}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Sayı"
            value={sayi}
            disabled={sonlandirildi}
            onChange={(e) => setSayi(e.target.value)}
            helperText="Yazının sayısı; boş bırakılırsa belgede elle yazılır."
          />
          <TextField
            label="Tarih"
            type="date"
            value={tarih}
            disabled={sonlandirildi}
            onChange={(e) => setTarih(e.target.value)}
            helperText="Bugünden sonra olamaz."
          />
        </div>
        <MetinAlani
          label="Tespit edilen hususlar"
          value={tespit}
          onChange={setTespit}
          rows={6}
          disabled={sonlandirildi}
          helperText={TESPIT_YARDIMI}
        />
        <div className="flex flex-wrap gap-2">
          {!sonlandirildi && (
            <>
              <Button icon="save" onClick={() => void kaydet()} disabled={busy}>
                Kaydet
              </Button>
              <Button variant="tonal" icon="lock" onClick={() => void sonlandir()} disabled={busy}>
                Raporu sonlandır
              </Button>
            </>
          )}
          {sonlandirildi && (
            <Button
              variant="outlined"
              icon="lock_open"
              onClick={() => void geriAl()}
              disabled={busy}
            >
              Sonlandırmayı geri al
            </Button>
          )}
        </div>
        <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
          <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
          {YAZ_DONEMI_UYARISI}
        </p>
      </Card>

      <Sayilar stats={rapor.stats} dondurulmus={sonlandirildi} />

      <Card elevation={0} className="shadow-elevation-1">
        <ul>
          <BelgeSatiri
            ad={YIL_SONU_RAPORU_BELGESI}
            pdfAl={() => ayiklamaApi.raporPdf(rapor.id)}
            aciklama={
              sonlandirildi
                ? "Dondurulmuş sayılarla basılır."
                : kirli
                  ? "Kaydedilmemiş değişiklikler belgeye girmez; önce “Kaydet”."
                  : "Rapor sonlandırılmadıkça “Taslak” ibaresiyle basılır."
            }
          />
        </ul>
      </Card>
    </div>
  );
}

function Sayilar({ stats, dondurulmus }: { stats: RaporSayilari; dondurulmus: boolean }) {
  const c = stats.collection;
  const a = stats.acquisitions;
  const w = stats.weeding;
  const f = stats.findings;
  const d = stats.circulation;
  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div>
        <h2 className="text-title-medium font-semibold text-on-surface">Rapordaki Sayılar</h2>
        <p className="text-body-small text-on-surface-variant">
          {`Dönem ${formatDate(stats.period.start)} – ${formatDate(stats.period.end)}. `}
          {dondurulmus
            ? "Sayılar sonlandırıldığı andaki hâliyle dondurulmuştur."
            : "Sayılar şu anki kayıtlardandır; sonlandırılınca dondurulur."}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Bilgi etiket="Elde bulunan nüsha">{formatNumber(c.in_stock_count)}</Bilgi>
        <Bilgi etiket="Kazandırılan nüsha">{formatNumber(a.total_copies)}</Bilgi>
        <Bilgi etiket="Kayıt içi giriş">{formatNumber(a.register_entry_copies)}</Bilgi>
        <Bilgi etiket="Kayıttan düşülen">{formatNumber(w.withdrawn)}</Bilgi>
        <Bilgi etiket="Devredilen">{formatNumber(w.transferred)}</Bilgi>
        <Bilgi etiket="Onarıma gönderilen">{formatNumber(f.repairs_sent)}</Bilgi>
        <Bilgi etiket="Hasar dosyası">{formatNumber(f.damage_cases)}</Bilgi>
        <Bilgi etiket="Kayıp dosyası">{formatNumber(f.loss_cases)}</Bilgi>
        <Bilgi etiket="Verilen ödünç">{formatNumber(d.loans)}</Bilgi>
        <Bilgi etiket="Ödünç alan farklı üye">{formatNumber(d.distinct_borrowers)}</Bilgi>
        <Bilgi etiket="Katalogdaki eser">{formatNumber(c.catalog_work_count)}</Bilgi>
      </dl>
      <p className="text-body-small text-on-surface-variant">
        {`Üye türü, sınıf düzeyi ve ay kırılımları basılı raporda yer alır; ${formatNumber(
          d.k_threshold,
        )} farklı üyeden azının ödünç aldığı grubun sayısı gösterilmez ve toplamdan hesaplanamasın diye gerekirse bir grup daha gizlenir. Kazandırılan nüsha Yönetmelik Md. 10/5'teki yollardandır; programa aktarım ve sayım fazlası kayıt içi giriştir.`}
      </p>
    </Card>
  );
}
