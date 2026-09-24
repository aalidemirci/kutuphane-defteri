// Etiketler → Basım Geçmişi (tasarım D10, §7.2).
//
// Her basım partisi iz olarak kalır: onay bekleyen, basılan, basım işareti geri
// alınan ve vazgeçilen. Satıra tıklanınca parti tablonun üstünde açılır:
//   * onay bekliyorsa: PDF, "Basıldı olarak işaretle", "Partiden vazgeç";
//   * basıldıysa: "Basım işaretini geri al" (barkodu okutularak doğrulanmış
//     nüshanın işaretlerine — sırt ve barkod — dokunulmaz) ve "Yeniden bas";
//   * geri alındıysa ya da vazgeçildiyse: "Yeniden bas".
// Yeniden basım aynı nüshaları AYNI SIRAYLA yeni bir partide basar; başka
// başlangıç hücresi, şablon ya da yazıcı seçilebilir (hasarlı tabakanın yenisi).
//
// Ayrıntı pencere (Dialog) değil tablonun üstünde bir karttır: PDF önizlemesi ve
// onay diyaloğu iç içe pencere açmasın.

import { useEffect, useState } from "react";

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
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { ETIKET_ICERIGI_TR, ETIKET_SAYFA_BOYUTU, PARTI_DURUMU_TR, etiketApi } from "./etiketApi";
import type {
  BasimPartisi,
  BasimPartisiAyrintisi,
  EtiketIcerigi,
  EtiketSablonu,
  GeriAlmaSonucu,
  PartiDurumu,
} from "./etiketApi";
import {
  BasimAyarlari,
  BasimPartisiKarti,
  PartiDurumRozeti,
  basimAyariGovdesi,
  partiOzeti,
} from "./etiketOrtak";
import type { BasimAyari } from "./etiketOrtak";
import { kodSecenekleri } from "./ortak";

/**
 * Okutularak doğrulanmış nüshada korunan işaretlerin adı (kullanıcı kararı
 * 24.09.2026): "sırt ve barkod etiketi" partisinde İKİ işaret de korunur, yalnız
 * barkod partisinde barkod işareti. Yalnız sırt partisinde doğrulama yoktur.
 */
function korunanIsaret(kind: EtiketIcerigi): string {
  return kind === "BOTH" ? "sırt ve barkod işareti" : "barkod işareti";
}

/**
 * Geri almanın sonucu. Kuyruğa DÖNEN nüsha (`requeued`) ile işareti önceki
 * basımın damgasına dönen nüsha ayrı söylenir: yeniden basım partisi geri
 * alınınca nüshalar kuyruğa girmez, önceki basımın işaretine döner. Doğrulanmış
 * nüsha (`kept_verified`) ikisine de girmez: işaretlerine dokunulmaz.
 */
function geriAlmaIletisi(sonuc: GeriAlmaSonucu): string {
  const parcalar: string[] = [];
  if (sonuc.requeued > 0) parcalar.push(`${formatNumber(sonuc.requeued)} nüsha kuyruğa döndü.`);
  const onceki = sonuc.restored - sonuc.requeued;
  if (onceki > 0) {
    parcalar.push(
      `${formatNumber(onceki)} nüshanın işareti önceki basıma döndü; bunlar kuyruğa girmez.`,
    );
  }
  if (sonuc.kept_verified > 0) {
    parcalar.push(
      `Okutularak doğrulanmış ${formatNumber(sonuc.kept_verified)} nüshanın ` +
        `${korunanIsaret(sonuc.batch.kind)} korundu; bunlar kuyruğa dönmez.`,
    );
  }
  return parcalar.length > 0 ? parcalar.join(" ") : "Basım işareti geri alındı.";
}

/** Geri alma onayının gövdesi — partinin içeriğine göre (sırt etiketi doğrulanmaz). */
function geriAlmaOnayMetni(parti: { copy_count: number; kind: EtiketIcerigi }): string {
  const giris =
    `Bu partideki ${formatNumber(parti.copy_count)} nüshanın işareti bu basımdan önceki ` +
    "hâline döner: etiketi ilk kez basılan nüshalar kuyruğa geri gelir, daha önce basılmış " +
    "olanlar önceki basımın işaretine döner.";
  const dogrulanmis =
    parti.kind === "SPINE"
      ? ""
      : " Barkodu okutularak doğrulanmış nüshaların etiketleri kitabın üzerinde olduğu için " +
        `onların ${korunanIsaret(parti.kind)} korunur; bu nüshalar kuyruğa dönmez.`;
  return `${giris}${dogrulanmis} Parti geçmişte iz olarak kalır.`;
}

export default function BasimGecmisi({
  sablonlar,
  tazeleme,
  onDegisti,
}: {
  sablonlar: EtiketSablonu[];
  tazeleme: number;
  onDegisti: () => void;
}) {
  const [durum, setDurum] = useState<PartiDurumu | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<BasimPartisi>>(emptyPage<BasimPartisi>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [seciliId, setSeciliId] = useState<number | null>(null);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    etiketApi
      .partiler({ status: durum, limit: ETIKET_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Basım geçmişi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [durum, offset, tazeleme]);

  const sutunlar: Column<BasimPartisi>[] = [
    { header: "Hazırlandı", cell: (p) => formatDateTime(p.created_at) },
    { header: "İçerik", cell: (p) => p.kind_display },
    { header: "Nüsha", align: "right", cell: (p) => formatNumber(p.copy_count) },
    { header: "Şablon", cell: (p) => p.template_name },
    { header: "Yazıcı", cell: (p) => p.printer_name ?? "—" },
    { header: "Durum", cell: (p) => <PartiDurumRozeti parti={p} /> },
  ];

  return (
    <div className="space-y-4">
      {seciliId !== null && (
        <PartiAyrintisi
          key={seciliId}
          id={seciliId}
          sablonlar={sablonlar}
          onSec={setSeciliId}
          onKapat={() => setSeciliId(null)}
          onDegisti={onDegisti}
        />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <Select
          className="w-64"
          label="Durum"
          placeholder="Tümü"
          value={durum}
          onChange={(e) => {
            setDurum(e.target.value as PartiDurumu | "");
            setOffset(0);
          }}
          options={kodSecenekleri(PARTI_DURUMU_TR)}
        />
        <p className="text-body-small text-on-surface-variant">
          Ayrıntı ve eylemler için satıra tıklayın.
        </p>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="history"
          title="Henüz basım partisi yok."
          description="Basım Kuyruğu'nda hazırladığınız partiler burada iz olarak kalır."
        />
      ) : (
        <>
          <DataTable
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(p) => setSeciliId(p.id)}
            rowLabel={(p) => `${p.kind_display}, ${formatDateTime(p.created_at)} — ayrıntıyı aç`}
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
// Seçilen parti
// ---------------------------------------------------------------------------

function PartiAyrintisi({
  id,
  sablonlar,
  onSec,
  onKapat,
  onDegisti,
}: {
  id: number;
  sablonlar: EtiketSablonu[];
  /** Yeniden basımla açılan partiye geçer. */
  onSec: (id: number) => void;
  onKapat: () => void;
  onDegisti: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [parti, setParti] = useState<BasimPartisiAyrintisi | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [yenidenBasim, setYenidenBasim] = useState(false);
  const [nushalarAcik, setNushalarAcik] = useState(false);
  const [tazeleme, setTazeleme] = useState(0);

  useEffect(() => {
    let iptal = false;
    etiketApi
      .parti(id)
      .then((sonuc) => {
        if (!iptal) setParti(sonuc);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Basım partisi yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [id, tazeleme]);

  if (parti === null) {
    return hata ? <ErrorBand hata={hata} /> : <SkeletonList rows={2} />;
  }

  const sablon = sablonlar.find((s) => s.id === parti.template);

  const geriAl = async () => {
    const tamam = await confirm({
      title: "Basım işareti geri alınsın mı?",
      message: geriAlmaOnayMetni(parti),
      confirmLabel: "Basım işaretini geri al",
    });
    if (!tamam) return;
    setBusy(true);
    setHata(null);
    try {
      const sonuc = await etiketApi.partiGeriAl(parti.id);
      snackbar.success(geriAlmaIletisi(sonuc), { duration: 8000 });
      setTazeleme((k) => k + 1);
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, "Basım işareti geri alınamadı."));
    } finally {
      setBusy(false);
    }
  };

  const partiDegisti = () => {
    setTazeleme((k) => k + 1);
    onDegisti();
  };

  return (
    <div className="space-y-3">
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-2 text-title-medium text-on-surface">
            <Icon name="inventory" size="lg" className="text-primary" />
            Seçilen Basım Partisi
          </p>
          <div className="flex items-center gap-2">
            <PartiDurumRozeti parti={parti} />
            <Button
              variant="text"
              icon="close"
              onClick={onKapat}
              aria-label="Seçilen partiyi kapat"
            >
              Kapat
            </Button>
          </div>
        </div>
        <p className="text-body-medium text-on-surface">{partiOzeti(parti, sablon)}</p>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-body-small sm:grid-cols-2">
          <Tarih etiket="Hazırlandı" deger={parti.created_at} />
          <Tarih etiket="Basıldı olarak işaretlendi" deger={parti.confirmed_at} />
          {parti.reverted_at && (
            <Tarih etiket="Basım işareti geri alındı" deger={parti.reverted_at} />
          )}
          {parti.discarded_at && <Tarih etiket="Vazgeçildi" deger={parti.discarded_at} />}
          <div className="flex gap-2">
            <dt className="text-on-surface-variant">Basım sırası:</dt>
            <dd className="text-on-surface">{parti.order_display}</dd>
          </div>
          {parti.reprint_of !== null && (
            <div className="flex gap-2">
              <dt className="text-on-surface-variant">Yeniden basım:</dt>
              <dd className="text-on-surface">önceki bir partinin aynı nüshaları</dd>
            </div>
          )}
        </dl>
        {hata && <ErrorBand hata={hata} />}
        {parti.status !== "PENDING" && (
          <div className="flex flex-wrap gap-2">
            {parti.status === "CONFIRMED" && (
              <Button variant="outlined" icon="undo" onClick={() => void geriAl()} disabled={busy}>
                Basım işaretini geri al
              </Button>
            )}
            <Button
              variant="outlined"
              icon="print"
              onClick={() => setYenidenBasim((acik) => !acik)}
              disabled={busy}
            >
              Yeniden bas
            </Button>
          </div>
        )}
        <div>
          <Button
            variant="text"
            icon={nushalarAcik ? "expand_less" : "expand_more"}
            onClick={() => setNushalarAcik((acik) => !acik)}
            aria-expanded={nushalarAcik}
          >
            {nushalarAcik ? "Nüshaları gizle" : "Nüshaları göster"}
          </Button>
          {nushalarAcik && (
            <ol className="mt-2 max-h-72 space-y-1 overflow-y-auto rounded-shape-sm bg-surface-container-low p-3 text-body-small scrollbar-thin">
              {parti.items.map((kalem) => (
                <li key={kalem.position} className="flex flex-wrap gap-x-3">
                  <span className="w-10 text-right text-on-surface-variant">{kalem.position}.</span>
                  <span className="font-mono text-on-surface">{kalem.barcode_display}</span>
                  <span className="text-on-surface">{kalem.work_title}</span>
                  <span className="text-on-surface-variant">{kalem.call_number}</span>
                  {!kalem.printable && (
                    <span className="text-error">
                      silinmiş ya da elden çıkmış — PDF&apos;te hücresi boş kalır
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      </Card>

      {parti.status === "PENDING" && (
        <BasimPartisiKarti
          parti={parti}
          sablon={sablon}
          baslik="Onay Bekleyen Parti"
          onDegisti={partiDegisti}
        />
      )}

      {yenidenBasim && parti.status !== "PENDING" && (
        <YenidenBasimFormu
          parti={parti}
          sablonlar={sablonlar}
          onVazgec={() => setYenidenBasim(false)}
          onHazir={(yeni) => {
            setYenidenBasim(false);
            onDegisti();
            onSec(yeni.id);
          }}
        />
      )}
    </div>
  );
}

function Tarih({ etiket, deger }: { etiket: string; deger: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="text-on-surface-variant">{etiket}:</dt>
      <dd className="text-on-surface">{formatDateTime(deger)}</dd>
    </div>
  );
}

/** Yeniden basım: içerik, şablon, yazıcı ve başlangıç hücresi değiştirilebilir. */
function YenidenBasimFormu({
  parti,
  sablonlar,
  onVazgec,
  onHazir,
}: {
  parti: BasimPartisi;
  sablonlar: EtiketSablonu[];
  onVazgec: () => void;
  onHazir: (yeni: BasimPartisi) => void;
}) {
  const [icerik, setIcerik] = useState<EtiketIcerigi>(parti.kind);
  const [ayar, setAyar] = useState<BasimAyari>({
    sablon: String(parti.template),
    kalibrasyon: parti.calibration === null ? "" : String(parti.calibration),
    sirtSablonu: "",
    sirtKalibrasyonu: "",
    baslangic: parti.start_cell,
    qr: parti.include_qr,
  });
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const govde = basimAyariGovdesi(ayar, icerik);

  const hazirla = async () => {
    if (govde === null) return;
    setBusy(true);
    setHata(null);
    try {
      const yeni = await etiketApi.yenidenBas(parti.id, {
        kind: icerik,
        template: govde.template,
        calibration: govde.calibration ?? null,
        start_cell: govde.start_cell,
      });
      onHazir(yeni);
    } catch (e) {
      setHata(hataOku(e, "Yeniden basım hazırlanamadı."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <p className="text-title-medium text-on-surface">Yeniden Basım</p>
      <p className="text-body-small text-on-surface-variant">
        Aynı {formatNumber(parti.copy_count)} nüsha aynı sırayla yeni bir partide basılır. Bozulan
        tabakanın yerine basıyorsanız yalnız bozulan içeriği seçebilir, kısmen kullanılmış tabakada
        başlangıç hücresini değiştirebilirsiniz.
      </p>
      <Select
        className="max-w-sm"
        label="Etiket içeriği"
        value={icerik}
        onChange={(e) => setIcerik(e.target.value as EtiketIcerigi)}
        options={(Object.keys(ETIKET_ICERIGI_TR) as EtiketIcerigi[]).map((kod) => ({
          value: kod,
          label: ETIKET_ICERIGI_TR[kod],
        }))}
      />
      <BasimAyarlari
        icerik={icerik}
        sablonlar={sablonlar}
        ayar={ayar}
        onAyar={setAyar}
        adet={parti.copy_count}
        ekSecenekler={false}
      />
      <p className="text-body-small text-on-surface-variant">
        QR seçimi ve ayrı sırt tabakası önceki partiden alınır.
      </p>
      {hata && <ErrorBand hata={hata} />}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="text" onClick={onVazgec} disabled={busy}>
          Vazgeç
        </Button>
        <Button icon="print" onClick={() => void hazirla()} disabled={busy || govde === null}>
          {busy ? "Hazırlanıyor…" : "Yeniden basım partisini hazırla"}
        </Button>
      </div>
    </Card>
  );
}
