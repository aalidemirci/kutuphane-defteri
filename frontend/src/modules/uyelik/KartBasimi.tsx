// Kişiler → Kart Basımı (F6; tasarım §7.2, §10 E2; D8, D10).
//
// **Kart basımı kuyruğu**: kartı henüz "basıldı" işaretlenmemiş aktif üyeler. Yeni
// üyelik ve "Kartı yenile" kuyruğa koyar. Kartlar A4'e 10 (85 × 54 mm) basılır;
// şube seçilirse şube tabakası sınıf listesi sırasıyla çıkar. Kartta okul adı, ad,
// üye türü ve barkodlu kart no vardır; **sınıf yazmaz** (sınıf yalnız sıralamadır).
//
// PDF almak kartı basılmış SAYMAZ (D10): "Önizle" ve "PDF'i indir" hiçbir işarete
// dokunmaz; kartlar yazıcıdan çıkınca onay diyaloğundan geçen "Basıldı olarak
// işaretle" ile kuyruktan çıkar ve "Basım işaretini geri al" ile geri döner.
// Kaydırma, kart şablonunun yazıcı kalibrasyonuyla düzeltilir (etiketlerle aynı
// kalibrasyon sayfası ve yöntem).

import { useCallback, useEffect, useState } from "react";

import { useDebounced } from "../../hooks/useDebounced";
import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import {
  BaslangicHucresiAlani,
  kalibrasyonEtiketi,
  PdfDugmeleri,
  TabakaIzgarasi,
  useKalibrasyonlar,
} from "../kutuphane/etiketOrtak";
import { KalibrasyonPaneli } from "../kutuphane/SablonlarPaneli";
import { UYE_KARTI_ADI, uyelikApi } from "./api";
import type { KartDurumu, KartSablonu, MemberCardRow, MemberType } from "./api";
import {
  kisiEtiketi,
  SatirSecimi,
  subeOku,
  TD,
  TH,
  TumunuSec,
  UYE_TURU_SECENEKLERI,
  useSubeSecenekleri,
} from "./ortak";

const PAGE_SIZE = 50;

const DURUMLAR = [
  { key: "pending", label: "Kart Basımı Bekleyen", icon: "pending_actions" },
  { key: "printed", label: "Kartı Basılmış", icon: "task_alt" },
];

export default function KartBasimi() {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const subeler = useSubeSecenekleri();
  const [durum, setDurum] = useState<KartDurumu>("pending");
  const [sube, setSube] = useState("");
  const [tur, setTur] = useState<MemberType | "">("");
  const [aramaGirdisi, setAramaGirdisi] = useState("");
  const arama = useDebounced(aramaGirdisi);
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<MemberCardRow>>(emptyPage<MemberCardRow>());
  const [secim, setSecim] = useState<Set<number>>(new Set());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [tazeleme, setTazeleme] = useState(0);
  const [sablon, setSablon] = useState<KartSablonu | null>(null);
  const [kalibrasyon, setKalibrasyon] = useState("");
  const [baslangic, setBaslangic] = useState(1);
  const [kesim, setKesim] = useState(true);
  const [kalibrasyonAcik, setKalibrasyonAcik] = useState(false);
  const { kalibrasyonlar } = useKalibrasyonlar(sablon?.id ?? null, tazeleme);

  const yenile = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    uyelikApi
      .kartSablonu()
      .then((s) => {
        if (!iptal) setSablon(s);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Kart şablonu yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    const { classLevel, classSection } = subeOku(sube);
    uyelikApi
      .kartKuyrugu({
        state: durum,
        memberType: tur,
        classLevel,
        classSection,
        search: arama.trim(),
        limit: PAGE_SIZE,
        offset,
      })
      .then((s) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(s, offset, PAGE_SIZE);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Kart listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [durum, sube, tur, arama, offset, tazeleme]);

  // Süzgeç ya da durum değişince seçim bırakılır (görünmeyen satır seçili kalmasın).
  const suz = (fn: () => void) => {
    fn();
    setOffset(0);
    setSecim(new Set());
  };

  const seciliKimlikler = [...secim];
  const hucre = sablon?.labels_per_sheet ?? 10;

  const isaretle = async () => {
    const tamam = await confirm({
      title: `${formatNumber(secim.size)} kart basıldı olarak işaretlensin mi?`,
      message:
        "PDF'i almak kartı basılmış saymaz. Kartlar yazıcıdan düzgün çıktıysa işaretleyin: kuyruktan çıkarlar. İşaret sonra “Kartı Basılmış” listesinden geri alınabilir.",
      confirmLabel: "Basıldı olarak işaretle",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      const { marked } = await uyelikApi.kartBasildi(seciliKimlikler);
      snackbar.success(`${formatNumber(marked)} kart basıldı olarak işaretlendi.`);
      setSecim(new Set());
      yenile();
    } catch (e) {
      setHata(hataOku(e, "Kartlar işaretlenemedi."));
    } finally {
      setMesgul(false);
    }
  };

  const geriAl = async () => {
    const tamam = await confirm({
      title: `${formatNumber(secim.size)} kartın basım işareti geri alınsın mı?`,
      message: "Kartlar yeniden “Kart Basımı Bekleyen” listesine döner. Kart numarası değişmez.",
      confirmLabel: "Basım işaretini geri al",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      const { reverted } = await uyelikApi.kartBasimiGeriAl(seciliKimlikler);
      snackbar.success(`${formatNumber(reverted)} kart basım kuyruğuna döndü.`);
      setSecim(new Set());
      yenile();
    } catch (e) {
      setHata(hataOku(e, "Basım işareti geri alınamadı."));
    } finally {
      setMesgul(false);
    }
  };

  const pdfAl = () =>
    uyelikApi.kartPdf({
      membership_ids: seciliKimlikler,
      template: sablon?.id ?? null,
      calibration: kalibrasyon ? Number(kalibrasyon) : null,
      start_cell: baslangic,
      cut_guides: kesim,
    });

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        Üye kartı 85 × 54 mm'dir, bir sayfaya 10 kart basılır. Kartta okulun adı, üyenin adı, üye
        türü ve barkodlu kart no bulunur; sınıf yazmaz. Şube seçerseniz kartlar sınıf listesi
        sırasıyla basılır.
      </p>

      <Tabs
        items={DURUMLAR}
        active={durum}
        onChange={(key) => suz(() => setDurum(key as KartDurumu))}
        ariaLabel="Kart basımı listeleri"
        idBase="kart-basimi"
      />

      <div {...tabPanelProps("kart-basimi", durum)} className="space-y-[var(--kd-page-gap)]">
        <Card
          elevation={0}
          className="grid items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1 sm:grid-cols-[minmax(14rem,1fr)_9rem_11rem]"
        >
          <TextField
            label="Ara"
            value={aramaGirdisi}
            onChange={(e) => suz(() => setAramaGirdisi(e.target.value))}
            placeholder="Ad soyad, okul no ya da kart no…"
          />
          <Select
            label="Şube"
            placeholder="Tümü"
            value={sube}
            onChange={(e) => suz(() => setSube(e.target.value))}
            options={subeler}
          />
          <Select
            label="Üye türü"
            placeholder="Tümü"
            value={tur}
            onChange={(e) => suz(() => setTur(e.target.value as MemberType | ""))}
            options={UYE_TURU_SECENEKLERI}
          />
        </Card>

        {hata && <ErrorBand hata={hata} />}

        {yukleniyor ? (
          <SkeletonList rows={5} />
        ) : sayfa.results.length === 0 ? (
          <EmptyState
            icon="badge"
            title={
              durum === "pending" ? "Kart basımı bekleyen üye yok." : "Kartı basılmış üye yok."
            }
            description={
              durum === "pending"
                ? "Yeni üyelik açılınca ya da kart yenilenince kart burada basılmayı bekler."
                : undefined
            }
          />
        ) : (
          <Card elevation={0} className="space-y-2 p-[var(--kd-panel-padding)] shadow-elevation-1">
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(secim.size)} kart seçili
            </p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-body-small">
                <caption className="sr-only">
                  {durum === "pending" ? "Kart basımı bekleyen üyeler" : "Kartı basılmış üyeler"}
                </caption>
                <thead>
                  <tr className="border-b border-outline-variant">
                    <th className={TH}>
                      <TumunuSec
                        kimlikler={sayfa.results.map((s) => s.id)}
                        secim={secim}
                        onSecim={setSecim}
                        etiket="Bu sayfadakilerin tümünü seç"
                      />
                    </th>
                    <th className={TH}>Ad soyad</th>
                    <th className={TH}>Sınıf / üye türü</th>
                    <th className={TH}>Kart no</th>
                    <th className={TH}>{durum === "pending" ? "Üyelik başlangıcı" : "Basıldı"}</th>
                  </tr>
                </thead>
                <tbody>
                  {sayfa.results.map((s) => (
                    <tr key={s.id} className="border-t border-outline-variant/50">
                      <td className={TD}>
                        <SatirSecimi
                          id={s.id}
                          etiket={`${s.full_name} seç`}
                          secim={secim}
                          onSecim={setSecim}
                        />
                      </td>
                      <td className={TD}>{s.full_name}</td>
                      <td className={TD}>{kisiEtiketi(s)}</td>
                      <td className={`${TD} tabular-nums`}>{s.card_no}</td>
                      <td className={TD}>
                        {durum === "pending"
                          ? formatDate(s.started_at)
                          : formatDate(s.card_printed_at?.slice(0, 10))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={PAGE_SIZE}
              onOffset={(yeni) => {
                setOffset(yeni);
              }}
            />
          </Card>
        )}

        <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
          <p className="text-title-medium text-on-surface">Basım Ayarları</p>
          <div className="flex flex-wrap items-start gap-6">
            {sablon && (
              <TabakaIzgarasi
                sablon={sablon}
                baslangic={baslangic}
                onBaslangic={setBaslangic}
                adet={secim.size}
              />
            )}
            <div className="min-w-[16rem] flex-1 space-y-3">
              <p className="text-body-medium text-on-surface">
                Kart şablonu: {sablon ? sablon.name : "—"}
              </p>
              <Select
                label="Yazıcı (kalibrasyon)"
                placeholder="— yok —"
                value={kalibrasyon}
                onChange={(e) => setKalibrasyon(e.target.value)}
                options={kalibrasyonlar.map((k) => ({
                  value: String(k.id),
                  label: kalibrasyonEtiketi(k),
                }))}
              />
              <BaslangicHucresiAlani
                baslangic={baslangic}
                hucre={hucre}
                onBaslangic={setBaslangic}
              />
              <label className="flex items-center gap-2 text-body-medium text-on-surface">
                <input
                  type="checkbox"
                  checked={kesim}
                  onChange={(e) => setKesim(e.target.checked)}
                  className="size-5 accent-primary"
                />
                Kesim çizgisi bas
              </label>
              <p className="text-body-small text-on-surface-variant">
                Düz kâğıda ya da kartona basıp keserken açık bırakın; önceden kesilmiş kart
                tabakasında kapatın.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={pdfAl}
              dosyaAdi={() => dosyaAdi([UYE_KARTI_ADI, formatDate(todayIso())], "pdf")}
              onizlemeBasligi={UYE_KARTI_ADI}
              disabled={secim.size === 0}
              onHata={setHata}
            />
            {durum === "pending" ? (
              <Button
                icon="task_alt"
                onClick={() => void isaretle()}
                disabled={secim.size === 0 || mesgul}
              >
                Basıldı olarak işaretle
              </Button>
            ) : (
              <Button
                variant="outlined"
                icon="undo"
                onClick={() => void geriAl()}
                disabled={secim.size === 0 || mesgul}
              >
                Basım işaretini geri al
              </Button>
            )}
          </div>
        </Card>

        {sablon && (
          <div className="space-y-3">
            <Button
              variant="text"
              icon={kalibrasyonAcik ? "expand_less" : "expand_more"}
              aria-expanded={kalibrasyonAcik}
              onClick={() => setKalibrasyonAcik((a) => !a)}
            >
              {kalibrasyonAcik ? "Yazıcı kalibrasyonunu gizle" : "Yazıcı kalibrasyonunu göster"}
            </Button>
            {kalibrasyonAcik && <KalibrasyonPaneli key={sablon.id} sablon={sablon} />}
          </div>
        )}
      </div>
    </div>
  );
}
