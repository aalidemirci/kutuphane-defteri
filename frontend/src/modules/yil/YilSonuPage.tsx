// Yıl Sonu (F7; tasarım §8.3 — SU-8, EK-22). Mezunlar Haziran'da ayrılır; Eylül'de kitap
// toplamak fiilen imkânsızdır. Adım adım ekran; Genel Bakış'ta Mayıs-Haziran'da kart
// çıkar, İlişik Listesi sayfasının sağ üstündeki bağlantıyla her zaman açılır. YALNIZ
// yönetici kipinde (uçlar görevli izin listesinde değildir).
//
// Adımlar:
// 1. Son ödünç tarihleri — yalnız YENİ ödüncü durdurur, iade sürer; son sınıflar için
//    daha erken tarih isteğe bağlıdır. Eski yılın tarihi yeni yılda uygulanmaz.
// 2. Kitap toplama — açık ödünç ve teslimler, son sınıflar önce; iade hatırlatma
//    pusulası (kişinin BÜTÜN açık ödünçleri) ve sınıf kitaplıkları.
// 3. Son sınıflar ve okuldan ayrılanlar — açık ödünç ve teslim listesi (ilişik listesi).
// 4. İlişik ve belgeler — mezuniyetten önce "Kütüphaneden ilişiği yoktur" belgeleri.
// 5. Yıl sonu raporu (F8) — Md. 12/1: kaynaklar gözden geçirilir, tespit edilen hususlar
//    raporla okul müdürlüğüne bildirilir. Adım kayıt yazmaz; Yıl Sonu Raporu ekranına
//    götürür. "Tamam" işareti rapor sonlandırılınca konur (sunucunun `steps`'ine girmez,
//    `annual_review` alanından okunur).
//
// Ekranın hiçbir yerinde belge başka bir işlemin ön koşulu diye sunulmaz (§8.3).

import { useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import { emptyPage } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import { YIL_SONU_RAPORU_ADRESI } from "../ayiklama/api";
import { kutuphaneApi } from "../kutuphane/api";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { subeOku, useSubeSecenekleri } from "../uyelik/ortak";
import {
  ILISIK_BELGESI_ADI,
  ILISIK_LISTESI_ADI,
  ILISIK_LISTESI_ADRESI,
  KAPSAM_SECENEKLERI,
  LISTE_DIPNOTU,
  PUSULA_ADI,
  YIL_BASI_ADRESI,
  YIL_SONU_BASLIGI,
  yilApi,
} from "./api";
import type { IlisikKapsami, IlisikSatiri, YilSonuAdimi, YilSonuOzeti } from "./api";
import {
  AdimBasligi,
  IlisikTablosu,
  MetinBaglantisi,
  SinifKitapliklari,
  secimiAyir,
  useYilAkislari,
  YanEkranBaglantilari,
} from "./ortak";

/** Kitap Toplama adımındaki listenin GÖRÜNÜR başlığı (kılavuz ve sözlük bu adla anar). */
export const TOPLAMA_TABLOSU = "Toplanacak kitaplar";

/** Beşinci adım (F8) sunucunun adım işaretlerinde yoktur; rapor durumundan türer. */
type Adim = YilSonuAdimi | "review";

const ADIMLAR: Array<{ key: Adim; label: string; icon: string }> = [
  { key: "dates", label: "Son Ödünç Tarihleri", icon: "event_busy" },
  { key: "collection", label: "Kitap Toplama", icon: "assignment_return" },
  { key: "graduating", label: "Son Sınıflar ve Ayrılanlar", icon: "school" },
  { key: "clearance", label: "İlişik ve Belgeler", icon: "verified" },
  { key: "review", label: "Yıl Sonu Raporu", icon: "summarize" },
];

/** Adımın "tamam" işareti: dört adım sunucudan, rapor adımı raporun sonlandırılmasından. */
function adimTamam(ozet: YilSonuOzeti | null, key: Adim): boolean {
  if (ozet === null) return false;
  if (key === "review") return ozet.annual_review?.is_finalized ?? false;
  return ozet.steps[key];
}

const PAGE_SIZE = 50;

export default function YilSonuPage() {
  const { akislar, hata, yenile } = useYilAkislari();
  const [adim, setAdim] = useState(0);
  const ozet = akislar?.year_end ?? null;

  const items: StepperItem[] = ADIMLAR.map((a, i) => ({
    key: a.key,
    label: a.label,
    icon: a.icon,
    status: i === adim ? "current" : adimTamam(ozet, a.key) ? "done" : "upcoming",
  }));

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">{YIL_SONU_BASLIGI}</h1>
          <p className="kd-page-description max-w-4xl">
            Ders yılı sona ererken kitapların toplanması ve ilişik işleri, adım adım. Son sınıflar
            ve okuldan ayrılanlar önce gelir. Son ödünç tarihi yalnız yeni ödüncü durdurur; iade
            hiçbir zaman durmaz.
          </p>
        </div>
        <YanEkranBaglantilari
          baglantilar={[
            { to: ILISIK_LISTESI_ADRESI, label: "İlişik Listesi", icon: "fact_check" },
            { to: YIL_BASI_ADRESI, label: "Yıl Başı", icon: "event_available" },
          ]}
        />
      </div>

      <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
        <Stepper items={items} ariaLabel="Yıl sonu adımları" onSelect={(_, i) => setAdim(i)} />
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {ozet === null ? (
        !hata && <SkeletonList rows={4} />
      ) : (
        <>
          {adim === 0 && <TarihlerAdimi ozet={ozet} onKaydedildi={yenile} />}
          {adim === 1 && <ToplamaAdimi ozet={ozet} />}
          {adim === 2 && <SonSiniflarAdimi ozet={ozet} />}
          {adim === 3 && <IlisikAdimi ozet={ozet} />}
          {adim === 4 && <RaporAdimi ozet={ozet} />}
          <div className="flex flex-wrap justify-between gap-2">
            <Button
              variant="outlined"
              icon="arrow_back"
              disabled={adim === 0}
              onClick={() => setAdim((a) => Math.max(0, a - 1))}
            >
              Geri
            </Button>
            {adim < ADIMLAR.length - 1 && (
              <Button icon="arrow_forward" onClick={() => setAdim((a) => a + 1)}>
                Devam
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Son ödünç tarihleri
// ---------------------------------------------------------------------------

function TarihlerAdimi({ ozet, onKaydedildi }: { ozet: YilSonuOzeti; onKaydedildi: () => void }) {
  const snackbar = useSnackbar();
  const [genel, setGenel] = useState(ozet.last_loan_date ?? "");
  const [sonSinif, setSonSinif] = useState(ozet.last_loan_date_graduating ?? "");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);

  const kaydet = async () => {
    setMesgul(true);
    setHata(null);
    try {
      await kutuphaneApi.updatePolicy({
        last_loan_date: genel || null,
        last_loan_date_graduating: sonSinif || null,
      });
      snackbar.success("Son ödünç tarihleri kaydedildi.");
      onKaydedildi();
    } catch (e) {
      setHata(hataOku(e, "Tarihler kaydedilemedi."));
    } finally {
      setMesgul(false);
    }
  };

  const eskiler: string[] = [];
  if (ozet.last_loan_date_stale && ozet.last_loan_date) {
    eskiler.push(
      `Kayıtlı yıl sonu son ödünç tarihi (${formatDate(ozet.last_loan_date)}) önceki ders yılına ait; bu yıl uygulanmaz.`,
    );
  }
  if (ozet.last_loan_date_graduating_stale && ozet.last_loan_date_graduating) {
    eskiler.push(
      `Kayıtlı son sınıflar için son ödünç tarihi (${formatDate(ozet.last_loan_date_graduating)}) önceki ders yılına ait; bu yıl uygulanmaz.`,
    );
  }

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <AdimBasligi
        sira={1}
        baslik="Son Ödünç Tarihleri"
        tamam={ozet.steps.dates}
        durum={
          ozet.last_loan_date && !ozet.last_loan_date_stale
            ? `Yıl sonu son ödünç tarihi: ${formatDate(ozet.last_loan_date)}`
            : "Yıl sonu son ödünç tarihi girilmedi."
        }
      />
      <p className="max-w-3xl text-body-medium text-on-surface">
        Bu tarihten sonra yeni ödünç verilmez; iade alınmaya devam eder. Son sınıflar (mezun olacak
        sınıf) için daha erken bir tarih isteğe bağlıdır. Tarihler Ayarlar → Kütüphane
        Politikası'ndaki alanların aynısıdır.
      </p>
      {ozet.graduating_level === null && (
        <p className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
          <Icon name="warning" className="mt-0.5 shrink-0" />
          Okulun kademesi seçilmemiş; son sınıflar belirlenemiyor. Ayarlar → Okul Bilgileri'nden
          kademeyi seçin.
        </p>
      )}
      {eskiler.map((m) => (
        <p
          key={m}
          className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container"
        >
          <Icon name="history" className="mt-0.5 shrink-0" />
          {m}
        </p>
      ))}
      {hata && <ErrorBand hata={hata} />}
      <div className="flex flex-wrap items-end gap-3">
        <TextField
          className="w-60"
          type="date"
          label="Yıl sonu son ödünç tarihi"
          value={genel}
          onChange={(e) => setGenel(e.target.value)}
        />
        <TextField
          className="w-60"
          type="date"
          label="Son sınıflar için son ödünç tarihi"
          helperText="İsteğe bağlı; daha erken bir tarih."
          value={sonSinif}
          onChange={(e) => setSonSinif(e.target.value)}
        />
        <Button icon="save" onClick={() => void kaydet()} disabled={mesgul}>
          Kaydet
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 2. Kitap toplama
// ---------------------------------------------------------------------------

function useIlisikSayfasi(
  sorgu: {
    group: IlisikKapsami;
    sube: string;
    obligation?: "all" | "collect";
  },
  offset: number,
): { sayfa: Paginated<IlisikSatiri>; yukleniyor: boolean; hata: SayfaHatasi | null } {
  const [sayfa, setSayfa] = useState<Paginated<IlisikSatiri>>(emptyPage<IlisikSatiri>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { group, sube, obligation } = sorgu;
  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    const { classLevel, classSection } = subeOku(sube);
    yilApi
      .ilisikListesi({ group, classLevel, classSection, obligation, limit: PAGE_SIZE, offset })
      .then((s) => {
        if (!iptal) {
          setSayfa(s);
          setHata(null);
        }
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Liste yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [group, sube, obligation, offset]);
  return { sayfa, yukleniyor, hata };
}

function ToplamaAdimi({ ozet }: { ozet: YilSonuOzeti }) {
  const subeler = useSubeSecenekleri();
  const [kapsam, setKapsam] = useState<IlisikKapsami>("");
  const [sube, setSube] = useState("");
  const [offset, setOffset] = useState(0);
  const [secim, setSecim] = useState<Set<string>>(new Set());
  const [sonGun, setSonGun] = useState("");
  const [pdfHatasi, setPdfHatasi] = useState<SayfaHatasi | null>(null);
  const { sayfa, yukleniyor, hata } = useIlisikSayfasi(
    { group: kapsam, sube, obligation: "collect" },
    offset,
  );
  const c = ozet.counts;
  const secilenSube = subeOku(sube);
  const tarih = formatDate(todayIso());

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <AdimBasligi
          sira={2}
          baslik="Kitap Toplama"
          tamam={ozet.steps.collection}
          durum={`${formatNumber(c.open_loans)} açık ödünç (son sınıflarda ${formatNumber(
            c.graduating_open_loans,
          )}, okuldan ayrılanlarda ${formatNumber(c.leaving_open_loans)}) · öğretmenlerde ${formatNumber(
            c.teacher_deliveries,
          )} teslim · sınıf kitaplıklarında ${formatNumber(c.section_deliveries)} kitap`}
        />
        <div className="flex flex-wrap items-end gap-3">
          <Select
            className="w-64"
            label="Kapsam"
            value={kapsam}
            onChange={(e) => {
              setKapsam(e.target.value as IlisikKapsami);
              setOffset(0);
              setSecim(new Set());
            }}
            options={KAPSAM_SECENEKLERI}
          />
          <Select
            className="w-44"
            label="Şube"
            placeholder="Bütün okul"
            value={sube}
            onChange={(e) => {
              setSube(e.target.value);
              setOffset(0);
              setSecim(new Set());
            }}
            options={subeler}
          />
        </div>
        <p className="text-title-small text-on-surface">{TOPLAMA_TABLOSU}</p>
        {hata && <ErrorBand hata={hata} />}
        {yukleniyor ? (
          <SkeletonList rows={4} />
        ) : sayfa.results.length === 0 ? (
          <EmptyState compact icon="task_alt" title="Bu seçimde toplanacak kitap yok." />
        ) : (
          <>
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(sayfa.count)} kişi
            </p>
            <IlisikTablosu
              satirlar={sayfa.results}
              secim={secim}
              onSecim={setSecim}
              secilebilir={(s) => s.open_loan_count > 0}
              baslik={TOPLAMA_TABLOSU}
            />
            {sayfa.count > PAGE_SIZE && (
              <PaginationBar
                count={sayfa.count}
                offset={offset}
                pageSize={PAGE_SIZE}
                onOffset={setOffset}
              />
            )}
          </>
        )}
      </Card>

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">{PUSULA_ADI}</p>
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          {secim.size > 0
            ? `Pusula yalnız seçilen ${formatNumber(secim.size)} kişiye basılır.`
            : "Kişi seçmezseniz pusula süzgeçteki, ödüncü olan herkese basılır."}{" "}
          Yıl sonu pusulası kişinin bütün açık ödünçlerini yazar (gecikmemişler dahil). Her pusula
          tek kişiliktir ve katlanınca içeriği görünmez; kütüphane yöneticisi ya da sınıf rehber
          öğretmeni eliyle verilir, sınıfta okunmaz.
        </p>
        {pdfHatasi && <ErrorBand hata={pdfHatasi} />}
        <div className="flex flex-wrap items-end gap-3">
          <TextField
            className="w-56"
            type="date"
            label="Son getirme günü"
            helperText="Pusulaya yazılır; kaydedilmez."
            value={sonGun}
            onChange={(e) => setSonGun(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() =>
                yilApi.yilSonuPusulasiPdf(
                  secim.size > 0
                    ? { ...secimiAyir(secim), returnBy: sonGun || undefined }
                    : {
                        group: kapsam,
                        classLevel: secilenSube.classLevel,
                        classSection: secilenSube.classSection,
                        returnBy: sonGun || undefined,
                      },
                )
              }
              dosyaAdi={() => dosyaAdi([PUSULA_ADI, "Yıl Sonu", tarih], "pdf")}
              onizlemeBasligi={PUSULA_ADI}
              disabled={c.open_loans === 0}
              onHata={setPdfHatasi}
            />
          </div>
        </div>
      </Card>

      <SinifKitapliklari onHata={setPdfHatasi} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Son sınıflar ve okuldan ayrılanlar
// ---------------------------------------------------------------------------

function SonSiniflarAdimi({ ozet }: { ozet: YilSonuOzeti }) {
  const [offset, setOffset] = useState(0);
  const [pdfHatasi, setPdfHatasi] = useState<SayfaHatasi | null>(null);
  const { sayfa, yukleniyor, hata } = useIlisikSayfasi({ group: "priority", sube: "" }, offset);
  const c = ozet.counts;
  const tarih = formatDate(todayIso());

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <AdimBasligi
          sira={3}
          baslik="Son Sınıflar ve Ayrılanlar"
          tamam={ozet.steps.graduating}
          durum={`Son sınıflarda ${formatNumber(c.graduating_persons)} kişi, okuldan ayrılanlarda ${formatNumber(
            c.leaving_persons,
          )} kişi · son sınıf şubelerinin kitaplıklarında ${formatNumber(
            c.graduating_section_deliveries,
          )} kitap`}
        />
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          Açık ödüncü, teslimi ya da çözülmemiş kayıp/hasar dosyası olan son sınıf öğrencileri ile
          okuldan ayrılan ya da ayrılış kararı bekleyen kişiler. Liste “{LISTE_DIPNOTU}” dipnotuyla
          basılır.
        </p>
        {pdfHatasi && <ErrorBand hata={pdfHatasi} />}
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() => yilApi.ilisikListesiPdf({ group: "priority" })}
            dosyaAdi={() =>
              dosyaAdi([ILISIK_LISTESI_ADI, "Son Sınıflar ve Ayrılanlar", tarih], "pdf")
            }
            onizlemeBasligi={ILISIK_LISTESI_ADI}
            onHata={setPdfHatasi}
          />
        </div>
        {hata && <ErrorBand hata={hata} />}
        {yukleniyor ? (
          <SkeletonList rows={3} />
        ) : sayfa.results.length === 0 ? (
          <EmptyState
            compact
            icon="task_alt"
            title="Son sınıflarda ve okuldan ayrılanlarda açık iş yok."
          />
        ) : (
          <>
            <IlisikTablosu satirlar={sayfa.results} baslik="Son sınıflar ve ayrılanlar" />
            {sayfa.count > PAGE_SIZE && (
              <PaginationBar
                count={sayfa.count}
                offset={offset}
                pageSize={PAGE_SIZE}
                onOffset={setOffset}
              />
            )}
          </>
        )}
      </Card>
      <SinifKitapliklari yalnizSonSinif onHata={setPdfHatasi} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. İlişik ve belgeler
// ---------------------------------------------------------------------------

/** Tek istekte basılabilecek en çok belge (sunucu sınırı). */
const EN_COK_BELGE = 150;

function IlisikAdimi({ ozet }: { ozet: YilSonuOzeti }) {
  const subeler = useSubeSecenekleri();
  const [sube, setSube] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const tarih = formatDate(todayIso());
  const seviye = ozet.graduating_level;
  const sonSinifSubeleri = subeler.filter(
    (s) => seviye !== null && subeOku(s.value).classLevel === seviye,
  );

  /** Açık işi olmayan son sınıf öğrencilerinin (şube seçildiyse o şubenin) belgeleri. */
  const belgeleriAl = async (): Promise<Blob> => {
    const secilen = subeOku(sube);
    const temizler = await yilApi.ilisikListesi({
      state: "clear",
      group: "graduating",
      classLevel: secilen.classLevel,
      classSection: secilen.classSection,
      limit: EN_COK_BELGE,
    });
    if (temizler.count > EN_COK_BELGE) {
      throw new ApiError(
        400,
        "cok_fazla",
        `Tek seferde en çok ${EN_COK_BELGE} belge basılır; şube şube basın.`,
      );
    }
    return yilApi.ilisikBelgesiPdf({ studentIds: temizler.results.map((s) => s.person_id) });
  };

  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <AdimBasligi
        sira={4}
        baslik="İlişik ve Belgeler"
        tamam={ozet.steps.clearance}
        durum={`Kütüphaneyle açık işi olan ${formatNumber(ozet.counts.persons)} kişi · açık işi olmayan son sınıf öğrencisi: ${formatNumber(
          ozet.graduating_clear_students,
        )} / ${formatNumber(ozet.graduating_students)}`}
      />
      <p className="max-w-3xl text-body-medium text-on-surface">
        Mezuniyetten önce açık işi olmayan son sınıf öğrencilerinin “Kütüphaneden ilişiği yoktur”
        belgeleri basılır (kişi başına bir sayfa). Açık işi olanlar İlişik Listesi'nde görünür; tek
        tek belge de oradan basılır.
      </p>
      <MetinBaglantisi to={ILISIK_LISTESI_ADRESI}>İlişik Listesi'ni aç</MetinBaglantisi>
      {hata && <ErrorBand hata={hata} />}
      <div className="flex flex-wrap items-end gap-3">
        <Select
          className="w-52"
          label="Son sınıf şubesi"
          placeholder="Bütün son sınıflar"
          value={sube}
          onChange={(e) => setSube(e.target.value)}
          options={sonSinifSubeleri}
          disabled={seviye === null}
        />
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={belgeleriAl}
            dosyaAdi={() => dosyaAdi([ILISIK_BELGESI_ADI, "Son Sınıflar", tarih], "pdf")}
            onizlemeBasligi={ILISIK_BELGESI_ADI}
            disabled={seviye === null || ozet.graduating_clear_students === 0}
            onHata={setHata}
          />
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 5. Yıl sonu raporu (F8 — Md. 12/1, E9)
// ---------------------------------------------------------------------------

function RaporAdimi({ ozet }: { ozet: YilSonuOzeti }) {
  const rapor = ozet.annual_review;
  const durum =
    rapor === null
      ? "Bu ders yılının raporu henüz hazırlanmadı."
      : rapor.is_finalized
        ? "Rapor sonlandırıldı; sayılar dondurulmuş."
        : "Rapor taslak; sonlandırılmadı.";
  return (
    <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <AdimBasligi
        sira={5}
        baslik="Yıl Sonu Raporu"
        tamam={rapor?.is_finalized ?? false}
        durum={durum}
      />
      <p className="max-w-3xl text-body-medium text-on-surface">
        Ders yılı sonunda kütüphane kaynakları gözden geçirilir ve tespit edilen hususlar raporla
        okul müdürlüğüne bildirilir (Yönetmelik Md. 12/1). Rapor kitap durumunu, yıl içinde
        kazandırılan, ayıklanan ve devredilen kaynakları ve kişisiz ödünç sayılarını taşır.
      </p>
      <MetinBaglantisi to={YIL_SONU_RAPORU_ADRESI}>Yıl Sonu Raporu'nu aç</MetinBaglantisi>
    </Card>
  );
}
