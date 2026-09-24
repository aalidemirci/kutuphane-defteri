// Etiketler → Boş Barkod Aralığı — önce etiket yolunun ilk adımı (tasarım §8.1,
// okulun ASIL yolu: okulda hazır kitap listesi yoktur).
//
// Akış: adet yaz → "Numara ayır" → aralığı aç → boş barkod etiketlerini bas →
// "Basıldı olarak işaretle" → etiketler kitaplara yapıştırılır → Hızlı Kayıt'ta
// kitaptaki etiket okutulur ve nüsha O numarayla açılır.
//
// Numara ASLA yeniden verilmez (§7.1): ayrılan numara sayaçtan çıkmıştır;
// kullanılmayan (bozulan, kaybolan) etiketin numarası iptal edilir ve sayaca
// dönmez. Ayırma ve iptal onay diyaloğundan geçer; iptal geri alınamaz.
//
// PDF almak "basıldı" DEĞİLDİR (D10): işaret ayrı onaydır ve aralıktan hiçbir
// etiket kitaba bağlanmadıysa geri alınabilir.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatDateTime, formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import {
  BOS_BARKOD_BELGE_ADI,
  EN_COK_ETIKET,
  ETIKET_SAYFA_BOYUTU,
  bosBarkodDosyaAdi,
  etiketApi,
} from "./etiketApi";
import type {
  AyrilmisNumara,
  BosBarkodAraligi,
  BosBarkodAraligiAyrintisi,
  EtiketSablonu,
} from "./etiketApi";
import {
  BOS_BASIM_AYARI,
  BasimAyarlari,
  PdfDugmeleri,
  basimAyariGovdesi,
  varsayilanSablon,
} from "./etiketOrtak";
import type { BasimAyari } from "./etiketOrtak";

/** Numara aralığının okunur yazımı: "2026-000124 – 2026-000188". */
function aralikYazimi(aralik: BosBarkodAraligi): string {
  return aralik.count === 1
    ? aralik.first_barcode_display
    : `${aralik.first_barcode_display} – ${aralik.last_barcode_display}`;
}

export default function BosBarkodPaneli({
  sablonlar,
  tazeleme,
  onDegisti,
}: {
  sablonlar: EtiketSablonu[];
  tazeleme: number;
  onDegisti: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const varsayilan = varsayilanSablon(sablonlar, "BLANK");
  const [adet, setAdet] = useState("");
  const [aciklama, setAciklama] = useState("");
  const [adetHatasi, setAdetHatasi] = useState("");
  const [ayriliyor, setAyriliyor] = useState(false);

  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<BosBarkodAraligi>>(emptyPage<BosBarkodAraligi>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [seciliId, setSeciliId] = useState<number | null>(null);
  const [yerelTazeleme, setYerelTazeleme] = useState(0);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    etiketApi
      .araliklar({ limit: ETIKET_SAYFA_BOYUTU, offset })
      .then((sonuc) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(sonuc, offset, ETIKET_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(sonuc);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Boş barkod aralıkları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [offset, tazeleme, yerelTazeleme]);

  const degisti = () => {
    setYerelTazeleme((k) => k + 1);
    onDegisti();
  };

  const ayir = async () => {
    setAdetHatasi("");
    const sayi = Number(adet.trim());
    if (!Number.isInteger(sayi) || sayi < 1 || sayi > EN_COK_ETIKET) {
      setAdetHatasi(`1 ile ${formatNumber(EN_COK_ETIKET)} arasında bir sayı yazın.`);
      return;
    }
    const tamam = await confirm({
      title: `${formatNumber(sayi)} numara ayrılsın mı?`,
      message:
        "Numaralar kütüphanenin tek sayacından sırayla alınır ve başka hiçbir nüshaya " +
        "verilmez. Kullanmadığınız numaraları sonradan iptal edersiniz; iptal edilen numara " +
        "sayaca geri dönmez.",
      confirmLabel: "Numara ayır",
    });
    if (!tamam) return;
    setAyriliyor(true);
    setHata(null);
    try {
      const yeni = await etiketApi.aralikAyir(sayi, aciklama.trim());
      snackbar.success(`${formatNumber(yeni.count)} numara ayrıldı: ${aralikYazimi(yeni)}.`);
      setAdet("");
      setAciklama("");
      setOffset(0);
      setSeciliId(yeni.id);
      degisti();
    } catch (e) {
      setHata(hataOku(e, "Numara ayrılamadı."));
    } finally {
      setAyriliyor(false);
    }
  };

  const sutunlar: Column<BosBarkodAraligi>[] = [
    { header: "Numaralar", cell: (a) => <span className="font-mono">{aralikYazimi(a)}</span> },
    { header: "Adet", align: "right", cell: (a) => formatNumber(a.count) },
    { header: "Açıklama", cell: (a) => a.note || "—" },
    { header: "Ayrıldı", cell: (a) => formatDateTime(a.created_at) },
    {
      header: "Basım",
      cell: (a) => (a.printed_at ? formatDateTime(a.printed_at) : "Basıldı olarak işaretlenmedi"),
    },
    { header: "Bağlanan", align: "right", cell: (a) => formatNumber(a.bound_count) },
    { header: "İptal", align: "right", cell: (a) => formatNumber(a.cancelled_count) },
    { header: "Bağlanmamış", align: "right", cell: (a) => formatNumber(a.open_count) },
  ];

  return (
    <div className="space-y-4">
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Numara Ayır</p>
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          Önce etiket yolunda kitaplar kataloğa girmeden barkod etiketi basılır: numaralar burada
          ayrılır, boş barkod etiketi olarak basılır ve kitaplara yapıştırılır. Kitap Hızlı Kayıt
          ekranında kaydedilirken üzerindeki etiket okutulur, nüsha o numarayla açılır.
          {varsayilan &&
            ` Varsayılan tabakada ${formatNumber(varsayilan.labels_per_sheet)} etiket vardır; tabakanın katları kadar ayırmak kâğıt israfını önler.`}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <TextField
            className="w-40"
            label="Adet"
            required
            inputMode="numeric"
            value={adet}
            onChange={(e) => setAdet(e.target.value)}
            error={adetHatasi || undefined}
            placeholder={varsayilan ? String(varsayilan.labels_per_sheet) : "65"}
          />
          <TextField
            className="min-w-[16rem] flex-1"
            label="Açıklama"
            value={aciklama}
            maxLength={120}
            onChange={(e) => setAciklama(e.target.value)}
            helperText="İsteğe bağlı: etiketlerin nerede kullanılacağı (ör. “Hikâye rafı”). Kişi adı yazmayın."
          />
          <Button icon="add" onClick={() => void ayir()} disabled={ayriliyor}>
            {ayriliyor ? "Ayrılıyor…" : "Numara ayır"}
          </Button>
        </div>
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {seciliId !== null && (
        <AralikAyrintisi
          key={seciliId}
          id={seciliId}
          sablonlar={sablonlar}
          onKapat={() => setSeciliId(null)}
          onDegisti={degisti}
        />
      )}

      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="label"
          title="Henüz numara ayrılmadı."
          description="Kitapları etiketle kaydetmeye başlamak için yukarıdan numara ayırın."
        />
      ) : (
        <>
          <DataTable
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(a) => setSeciliId(a.id)}
            rowLabel={(a) => `${aralikYazimi(a)} aralığını aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={ETIKET_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Seçilen aralık: basım, basım işareti, numaralar ve iptal
// ---------------------------------------------------------------------------

function AralikAyrintisi({
  id,
  sablonlar,
  onKapat,
  onDegisti,
}: {
  id: number;
  sablonlar: EtiketSablonu[];
  onKapat: () => void;
  onDegisti: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [aralik, setAralik] = useState<BosBarkodAraligiAyrintisi | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [ayar, setAyar] = useState<BasimAyari>(BOS_BASIM_AYARI);
  const [secili, setSecili] = useState<Set<string>>(new Set());
  const [gerekce, setGerekce] = useState("");
  const [tazeleme, setTazeleme] = useState(0);

  useEffect(() => {
    let iptal = false;
    etiketApi
      .aralik(id)
      .then((sonuc) => {
        if (!iptal) setAralik(sonuc);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Aralık yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [id, tazeleme]);

  if (aralik === null) {
    return hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={2} />;
  }

  const acikNumaralar = aralik.numbers.filter((n) => n.state === "OPEN");
  const seciliNumaralar = acikNumaralar.filter((n) => secili.has(n.barcode));
  const basilacak = seciliNumaralar.length > 0 ? seciliNumaralar.length : aralik.open_count;
  const govde = basimAyariGovdesi(ayar, "BLANK");

  const yenile = () => {
    setTazeleme((k) => k + 1);
    onDegisti();
  };

  const islem = async (yap: () => Promise<unknown>, basari: string) => {
    setBusy(true);
    setHata(null);
    try {
      await yap();
      snackbar.success(basari);
      yenile();
    } catch (e) {
      setHata(hataOku(e, "İşlem tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  };

  const basildi = async () => {
    const tamam = await confirm({
      title: "Boş etiketler basıldı olarak işaretlensin mi?",
      message:
        `${formatNumber(aralik.open_count)} boş etiketin basıldığı kayda geçer. Tabaka hatalı ` +
        "çıktıysa işaretlemeyin; PDF'i yeniden basabilirsiniz. İşaret, aralıktan hiçbir etiket " +
        "kitaba bağlanmadıysa geri alınabilir.",
      confirmLabel: "Basıldı olarak işaretle",
    });
    if (!tamam) return;
    await islem(
      () => etiketApi.aralikBasildi(aralik.id),
      "Boş etiketler basıldı olarak işaretlendi.",
    );
  };

  const basimiGeriAl = async () => {
    const tamam = await confirm({
      title: "Basım işareti geri alınsın mı?",
      message:
        "Aralığın etiketleri basılmamış sayılır. Numaralar ayrılmış olarak kalır; iptal edilmez.",
      confirmLabel: "Basım işaretini geri al",
    });
    if (!tamam) return;
    await islem(() => etiketApi.aralikBasimGeriAl(aralik.id), "Basım işareti geri alındı.");
  };

  const iptalEt = async (numaralar: AyrilmisNumara[] | null) => {
    const sayi = numaralar === null ? aralik.open_count : numaralar.length;
    const tamam = await confirm({
      title: `${formatNumber(sayi)} numara iptal edilsin mi?`,
      message:
        "İptal edilen numara hiçbir yolla yeniden verilmez ve sayaca dönmez. Etiketi kitaba " +
        "yapıştırılmışsa kitap o etiketle kaydedilemez; etiket sökülür ve başka bir boş etiket " +
        "yapıştırılır. Bu işlem geri alınamaz.",
      confirmLabel: "Numaraları iptal et",
      acknowledgeLabel: "Bu numaraların etiketlerinin kitaplara yapıştırılmadığını denetledim.",
    });
    if (!tamam) return;
    setBusy(true);
    setHata(null);
    try {
      const sonuc = await etiketApi.aralikIptal(aralik.id, {
        barcodes: numaralar === null ? undefined : numaralar.map((n) => n.barcode),
        reason: gerekce.trim(),
      });
      snackbar.success(`${formatNumber(sonuc.cancelled)} numara iptal edildi.`);
      setAralik(sonuc.reservation);
      setSecili(new Set());
      setGerekce("");
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, "Numaralar iptal edilemedi."));
    } finally {
      setBusy(false);
    }
  };

  const sirtBaglantisi = `/katalog/etiketler?aralik=${aralik.id}&icerik=SPINE`;

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-title-medium text-on-surface">
          <Icon name="label" size="lg" className="text-primary" />
          Seçilen Aralık: <span className="font-mono">{aralikYazimi(aralik)}</span>
        </p>
        <Button variant="text" icon="close" onClick={onKapat} aria-label="Seçilen aralığı kapat">
          Kapat
        </Button>
      </div>
      <p className="text-body-medium text-on-surface">
        Ayrılan {formatNumber(aralik.count)} · kitaba bağlanan {formatNumber(aralik.bound_count)} ·
        iptal {formatNumber(aralik.cancelled_count)} · bağlanmamış {formatNumber(aralik.open_count)}
        {aralik.note && ` · ${aralik.note}`}
      </p>
      {hata && <ErrorBand hata={hata} />}

      {aralik.open_count > 0 ? (
        <div className="space-y-3 rounded-shape-md bg-surface-container-low p-3">
          <p className="text-title-small font-semibold text-on-surface">Boş etiketleri basın</p>
          <BasimAyarlari
            icerik="BLANK"
            sablonlar={sablonlar}
            ayar={ayar}
            onAyar={setAyar}
            adet={basilacak}
          />
          <p className="text-body-small text-on-surface-variant">
            {seciliNumaralar.length > 0
              ? `Yalnız seçtiğiniz ${formatNumber(seciliNumaralar.length)} numaranın etiketi basılır (bozulan etiketin yenisi).`
              : "Bağlanmamış ve iptal edilmemiş bütün numaraların etiketi basılır."}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <PdfDugmeleri
              pdfAl={() =>
                etiketApi.aralikPdf(aralik.id, {
                  template: govde?.template ?? 0,
                  calibration: govde?.calibration ?? null,
                  start_cell: govde?.start_cell ?? 1,
                  include_qr: govde?.include_qr ?? false,
                  barcodes:
                    seciliNumaralar.length > 0 ? seciliNumaralar.map((n) => n.barcode) : undefined,
                })
              }
              dosyaAdi={() => bosBarkodDosyaAdi(aralik)}
              onizlemeBasligi={BOS_BARKOD_BELGE_ADI}
              disabled={busy || govde === null}
              onHata={setHata}
            />
            {aralik.printed_at === null ? (
              <Button icon="task_alt" onClick={() => void basildi()} disabled={busy}>
                Basıldı olarak işaretle
              </Button>
            ) : (
              <>
                <span className="inline-flex items-center gap-1 rounded-full bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
                  <Icon name="check_circle" size="sm" />
                  Basıldı · {formatDateTime(aralik.printed_at)}
                </span>
                <Button
                  variant="text"
                  icon="undo"
                  onClick={() => void basimiGeriAl()}
                  disabled={busy || aralik.bound_count > 0}
                >
                  Basım işaretini geri al
                </Button>
              </>
            )}
          </div>
          {aralik.printed_at !== null && aralik.bound_count > 0 && (
            <p className="text-body-small text-on-surface-variant">
              Aralıktan kitaba bağlanmış etiket olduğu için basım işareti geri alınamaz; bozulan
              etiketlerin numaralarını iptal edin.
            </p>
          )}
        </div>
      ) : (
        <p className="text-body-medium text-on-surface-variant">
          Bu aralıkta basılacak bağlanmamış numara kalmadı.
        </p>
      )}

      {aralik.bound_count > 0 && (
        <p className="text-body-medium text-on-surface-variant">
          Bu aralıkla kaydedilen kitapların barkodu kitabın üzerindedir; sırt etiketleri kuyrukta
          bekler.{" "}
          <Link to={sirtBaglantisi} className="text-primary underline underline-offset-2">
            Sırt etiketlerini bas
          </Link>
        </p>
      )}

      <div className="space-y-2">
        <p className="text-title-small font-semibold text-on-surface">Numaralar</p>
        <div className="max-h-80 overflow-y-auto rounded-shape-sm border border-outline-variant/70 scrollbar-thin">
          <table className="w-full border-collapse text-body-small">
            <thead className="sticky top-0 bg-surface-container-low">
              <tr className="text-left text-label-medium text-on-surface-variant">
                <th className="w-12 px-3 py-2">
                  <span className="sr-only">Seç</span>
                </th>
                <th className="px-3 py-2">Barkod</th>
                <th className="px-3 py-2">Durum</th>
                <th className="px-3 py-2">Kitap ya da gerekçe</th>
              </tr>
            </thead>
            <tbody>
              {aralik.numbers.map((n) => (
                <tr key={n.barcode} className="border-t border-outline-variant/50">
                  <td className="px-3 py-1.5">
                    {n.state === "OPEN" && (
                      <input
                        type="checkbox"
                        aria-label={`${n.barcode_display} seç`}
                        checked={secili.has(n.barcode)}
                        onChange={() =>
                          setSecili((onceki) => {
                            const sonraki = new Set(onceki);
                            if (sonraki.has(n.barcode)) sonraki.delete(n.barcode);
                            else sonraki.add(n.barcode);
                            return sonraki;
                          })
                        }
                        className="size-5 accent-primary"
                      />
                    )}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-on-surface">{n.barcode_display}</td>
                  <td className="px-3 py-1.5 text-on-surface">{n.state_display}</td>
                  <td className="px-3 py-1.5 text-on-surface-variant">
                    {n.state === "BOUND" ? n.work_title : n.cancel_reason || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {aralik.open_count > 0 && (
        <div className="space-y-3 rounded-shape-md bg-surface-container-low p-3">
          <p className="text-title-small font-semibold text-on-surface">Kullanılmayan numaralar</p>
          <p className="text-body-small text-on-surface-variant">
            Bozulan, kaybolan ya da kullanılmayacak etiketin numarasını iptal edin. İptal edilen
            numara başka bir kitaba verilmez; okutulursa “iptal edildi” iletisi çıkar.
          </p>
          <TextField
            label="İptal gerekçesi"
            value={gerekce}
            maxLength={255}
            onChange={(e) => setGerekce(e.target.value)}
            helperText="İsteğe bağlı (ör. “Etiket yırtıldı”). Kişi adı yazmayın."
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outlined"
              icon="block"
              onClick={() => void iptalEt(seciliNumaralar)}
              disabled={busy || seciliNumaralar.length === 0}
            >
              Seçilenleri iptal et
            </Button>
            <Button variant="text" icon="block" onClick={() => void iptalEt(null)} disabled={busy}>
              Bağlanmamış bütün numaraları iptal et
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
