// Etiketler → Basım Kuyruğu (tasarım §7.2, D10, D20).
//
// Kuyruk üç tanedir, işaret iki tanedir (backend `selectors_kuyruk`):
//   * Barkod etiketi — barkod etiketi basılmamış nüshalar;
//   * Sırt etiketi — sırt etiketi basılmamış nüshalar (önce etiket yolunda
//     kitaba bağlanan nüshalar burada birikir: barkodları zaten kitaptadır);
//   * Sırt ve barkod etiketi — İKİSİ de basılmamış nüshalar.
//
// Akış: içerik + süzgeç + sıra → (isteğe bağlı) seçim → şablon + yazıcı +
// başlangıç hücresi → "Basım partisini hazırla" → PDF → "Basıldı olarak
// işaretle". Parti açmak ve PDF almak HİÇBİR işarete dokunmaz; onaya kadar
// nüshalar kuyrukta kalır ve satırda "Onay bekleyen partide" rozeti görünür.

import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { kutuphaneApi } from "./api";
import type { Acquisition, Section } from "./api";
import {
  BASIM_SIRASI_TR,
  EN_COK_ETIKET,
  ETIKET_ICERIGI_TR,
  ETIKET_SAYFA_BOYUTU,
  etiketApi,
} from "./etiketApi";
import type {
  BasimPartisi,
  BasimSirasi,
  BosBarkodAraligi,
  EtiketIcerigi,
  EtiketSablonu,
  KuyrukNushasi,
  KuyrukSuzgeci,
} from "./etiketApi";
import {
  BOS_BASIM_AYARI,
  BasimAyarlari,
  BasimPartisiKarti,
  basimAyariGovdesi,
} from "./etiketOrtak";
import type { BasimAyari } from "./etiketOrtak";
import { SECICI_SINIRI, bolumSecenekleri, kodSecenekleri } from "./ortak";

/** Kuyruğun ne içerdiği — içerik seçicisinin yardımcı metni. */
const KUYRUK_TARIFI: Record<EtiketIcerigi, string> = {
  BOTH: "İki etiketi de basılmamış nüshalar. Sırt ve barkod etiketi aynı sırayla, aynı hücrelere basılır.",
  BARCODE: "Barkod etiketi basılmamış nüshalar.",
  SPINE:
    "Sırt etiketi basılmamış nüshalar. Boş barkod etiketiyle kaydedilen kitaplar burada birikir.",
};

const ICERIK_KODLARI: readonly EtiketIcerigi[] = ["BOTH", "BARCODE", "SPINE"];

/** Edinim seçicisinin etiketi (bağışçı adı GÖSTERİLMEZ — şifreli alan). */
function edinimEtiketi(edinim: Acquisition): string {
  return `${edinim.method_display} — ${formatDate(edinim.date)} (${formatNumber(edinim.copy_count)} nüsha)`;
}

/** Aralık seçicisinin etiketi: numara aralığı + açıklama. */
export function aralikEtiketi(aralik: BosBarkodAraligi): string {
  const not = aralik.note ? ` — ${aralik.note}` : "";
  return `${aralik.first_barcode_display} – ${aralik.last_barcode_display}${not}`;
}

/** Adresteki sayısal parametre (yoksa ya da bozuksa boş). */
function sayiParametresi(deger: string | null): string {
  return deger !== null && /^\d+$/.test(deger) ? deger : "";
}

export default function EtiketKuyrugu({
  bolumler,
  sablonlar,
  tazeleme,
  onDegisti,
  onGecmis,
}: {
  bolumler: Section[];
  sablonlar: EtiketSablonu[];
  tazeleme: number;
  /** Parti açıldı, onaylandı ya da vazgeçildi: sayaçlar tazelenir. */
  onDegisti: () => void;
  onGecmis: () => void;
}) {
  const [params] = useSearchParams();
  // İçe aktarmanın "bu partinin etiketlerini bas" kısayolu (`?edinim=`) ve boş
  // barkod aralığının "sırt etiketlerini bas" kısayolu (`?aralik=`) buraya bağlanır.
  const [edinim, setEdinim] = useState(() => sayiParametresi(params.get("edinim")));
  const [aralik, setAralik] = useState(() => sayiParametresi(params.get("aralik")));
  const [icerik, setIcerik] = useState<EtiketIcerigi>(() => {
    const istenen = params.get("icerik");
    if (istenen !== null && (ICERIK_KODLARI as readonly string[]).includes(istenen)) {
      return istenen as EtiketIcerigi;
    }
    return params.get("aralik") ? "SPINE" : "BOTH";
  });
  const [sira, setSira] = useState<BasimSirasi>("CALL_NUMBER");
  const [bolum, setBolum] = useState("");
  const [baslangicTarihi, setBaslangicTarihi] = useState("");
  const [bitisTarihi, setBitisTarihi] = useState("");

  const [edinimler, setEdinimler] = useState<Acquisition[]>([]);
  const [araliklar, setAraliklar] = useState<BosBarkodAraligi[]>([]);

  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<KuyrukNushasi>>(emptyPage<KuyrukNushasi>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [secili, setSecili] = useState<Set<number>>(new Set());

  const [ayar, setAyar] = useState<BasimAyari>(BOS_BASIM_AYARI);
  const [parti, setParti] = useState<BasimPartisi | null>(null);
  const [hazirlaniyor, setHazirlaniyor] = useState(false);
  const [sonOnay, setSonOnay] = useState<BasimPartisi | null>(null);

  const suzgec: KuyrukSuzgeci = {
    section: bolum ? Number(bolum) : null,
    acquisition: edinim ? Number(edinim) : null,
    reservation: aralik ? Number(aralik) : null,
    created_from: baslangicTarihi || null,
    created_to: bitisTarihi || null,
  };

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listAcquisitions({ limit: SECICI_SINIRI })
      .then((s) => {
        if (!iptal) setEdinimler(s.results);
      })
      .catch(() => {
        if (!iptal) setEdinimler([]);
      });
    etiketApi
      .araliklar({ limit: SECICI_SINIRI })
      .then((s) => {
        if (!iptal) setAraliklar(s.results);
      })
      .catch(() => {
        if (!iptal) setAraliklar([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    etiketApi
      .kuyruk({
        kind: icerik,
        order: sira,
        section: bolum ? Number(bolum) : null,
        acquisition: edinim ? Number(edinim) : null,
        reservation: aralik ? Number(aralik) : null,
        created_from: baslangicTarihi || null,
        created_to: bitisTarihi || null,
        limit: ETIKET_SAYFA_BOYUTU,
        offset,
      })
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
        if (!iptal) setHata(hataOku(e, "Etiket kuyruğu yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [icerik, sira, bolum, edinim, aralik, baslangicTarihi, bitisTarihi, offset, tazeleme]);

  /** Süzgeç ya da içerik değişti: ilk sayfaya dönülür, seçim bırakılır. */
  const suzgecDegisti = (degistir: () => void) => {
    degistir();
    setOffset(0);
    setSecili(new Set());
  };

  const sayfadakiler = sayfa.results.map((n) => n.id);
  const hepsiSecili = sayfadakiler.length > 0 && sayfadakiler.every((id) => secili.has(id));
  const basilacak = secili.size > 0 ? secili.size : Math.min(sayfa.count, EN_COK_ETIKET);
  const govde = basimAyariGovdesi(ayar, icerik);

  const hazirla = async () => {
    if (govde === null || basilacak === 0) return;
    setHazirlaniyor(true);
    setHata(null);
    setSonOnay(null);
    try {
      const secim =
        secili.size > 0
          ? { copies: [...secili] }
          : { from_queue: true, limit: basilacak, ...suzgec };
      const yeni = await etiketApi.partiAc({ kind: icerik, order: sira, ...govde, ...secim });
      setParti(yeni);
      setSecili(new Set());
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, "Basım partisi hazırlanamadı."));
    } finally {
      setHazirlaniyor(false);
    }
  };

  const partiDegisti = (guncel: BasimPartisi) => {
    setParti(null);
    if (guncel.status === "CONFIRMED") setSonOnay(guncel);
    onDegisti();
  };

  const sutunlar: Column<KuyrukNushasi>[] = [
    {
      header: (
        <input
          type="checkbox"
          aria-label="Sayfadakilerin hepsini seç"
          checked={hepsiSecili}
          disabled={sayfadakiler.length === 0}
          onChange={() =>
            setSecili((onceki) => {
              const sonraki = new Set(onceki);
              for (const id of sayfadakiler) {
                if (hepsiSecili) sonraki.delete(id);
                else sonraki.add(id);
              }
              return sonraki;
            })
          }
          className="size-5 accent-primary"
        />
      ),
      cell: (n) => (
        <input
          type="checkbox"
          aria-label={`${n.barcode_display} seç`}
          checked={secili.has(n.id)}
          onChange={() =>
            setSecili((onceki) => {
              const sonraki = new Set(onceki);
              if (sonraki.has(n.id)) sonraki.delete(n.id);
              else sonraki.add(n.id);
              return sonraki;
            })
          }
          className="size-5 accent-primary"
        />
      ),
    },
    { header: "Barkod", cell: (n) => <span className="font-mono">{n.barcode_display}</span> },
    {
      header: "Kaynak adı",
      cell: (n) => (
        <span>
          {n.work_title}
          {n.work_authors && (
            <span className="block text-on-surface-variant">{n.work_authors}</span>
          )}
        </span>
      ),
    },
    { header: "Yer numarası", cell: (n) => n.call_number || "—" },
    { header: "Bölüm", cell: (n) => n.section_name || "—" },
    { header: "Kayıt", cell: (n) => formatDate(n.created_at) },
    {
      header: "Durum",
      cell: (n) =>
        n.pending_batch !== null ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-tertiary-container px-2 py-0.5 text-label-medium text-on-tertiary-container">
            <Icon name="hourglass_top" size="sm" />
            Onay bekleyen partide
          </span>
        ) : (
          "Kuyrukta"
        ),
    },
  ];

  const aktifSablon = sablonlar.find((s) => String(s.id) === ayar.sablon);
  const partiSablonu = parti ? sablonlar.find((s) => s.id === parti.template) : undefined;

  return (
    <div className="space-y-4">
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Ne Basılacak</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Select
            label="Etiket içeriği"
            value={icerik}
            onChange={(e) =>
              suzgecDegisti(() => {
                setIcerik(e.target.value as EtiketIcerigi);
                // Şablon içeriğin varsayılanına döner (sırt ↔ barkod tabakası).
                setAyar((onceki) => ({ ...onceki, sablon: "", kalibrasyon: "", qr: false }));
              })
            }
            options={ICERIK_KODLARI.map((kod) => ({ value: kod, label: ETIKET_ICERIGI_TR[kod] }))}
            helperText={KUYRUK_TARIFI[icerik]}
          />
          <Select
            label="Basım sırası"
            value={sira}
            onChange={(e) => suzgecDegisti(() => setSira(e.target.value as BasimSirasi))}
            options={kodSecenekleri(BASIM_SIRASI_TR)}
            helperText="Yer numarası sırası raf raf yapıştırmayı kolaylaştırır."
          />
          <Select
            label="Bölüm"
            placeholder="Tümü"
            value={bolum}
            onChange={(e) => suzgecDegisti(() => setBolum(e.target.value))}
            options={bolumSecenekleri(bolumler)}
          />
          <Select
            label="Edinim partisi"
            placeholder="Tümü"
            value={edinim}
            onChange={(e) => suzgecDegisti(() => setEdinim(e.target.value))}
            options={edinimler.map((a) => ({ value: String(a.id), label: edinimEtiketi(a) }))}
          />
          <Select
            label="Boş barkod aralığı"
            placeholder="Tümü"
            value={aralik}
            onChange={(e) => suzgecDegisti(() => setAralik(e.target.value))}
            options={araliklar.map((a) => ({ value: String(a.id), label: aralikEtiketi(a) }))}
            helperText="Önceden basılmış etiketle kaydedilen kitapları aralık aralık basmak için."
          />
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Kayıt tarihi (ilk)"
              type="date"
              value={baslangicTarihi}
              onChange={(e) => suzgecDegisti(() => setBaslangicTarihi(e.target.value))}
            />
            <TextField
              label="Kayıt tarihi (son)"
              type="date"
              value={bitisTarihi}
              onChange={(e) => suzgecDegisti(() => setBitisTarihi(e.target.value))}
            />
          </div>
        </div>
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {sonOnay && sonOnay.kind !== "SPINE" && (
        <p
          role="status"
          className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container"
        >
          <Icon name="barcode_reader" size="lg" className="mt-0.5 shrink-0" />
          Etiketleri kitaplara yapıştırdıktan sonra Doğrulama Okutması sekmesinde tek tek okutun;
          okutulmayan etiketler “doğrulanmamış” olarak listelenir.
        </p>
      )}

      {parti && <BasimPartisiKarti parti={parti} sablon={partiSablonu} onDegisti={partiDegisti} />}

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-title-medium text-on-surface">
            Kuyruk: {formatNumber(sayfa.count)} nüsha
          </p>
          {secili.size > 0 && (
            <Button variant="text" icon="deselect" onClick={() => setSecili(new Set())}>
              Seçimi bırak ({formatNumber(secili.size)})
            </Button>
          )}
        </div>
        {yukleniyor ? (
          <SkeletonList rows={5} />
        ) : sayfa.results.length === 0 ? (
          <EmptyState
            icon="task_alt"
            title="Kuyrukta bu süzgece uyan nüsha yok."
            description="Etiketi basılıp işaretlenen nüshalar kuyruktan çıkar. Yeni açılan nüshalar kendiliğinden kuyruğa girer."
          />
        ) : (
          <>
            <DataTable columns={sutunlar} rows={sayfa.results} />
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={ETIKET_SAYFA_BOYUTU}
              onOffset={setOffset}
            />
          </>
        )}
      </div>

      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Basım Ayarları</p>
        <BasimAyarlari
          icerik={icerik}
          sablonlar={sablonlar}
          ayar={ayar}
          onAyar={setAyar}
          adet={basilacak}
        />
        <div className="space-y-1 text-body-medium text-on-surface-variant">
          {secili.size > 0 ? (
            <p>
              Seçtiğiniz {formatNumber(secili.size)} nüshanın etiketi seçilen sırayla hazırlanır.
            </p>
          ) : (
            <p>
              Seçim yapmazsanız süzgece uyan kuyruğun ilk {formatNumber(basilacak)} nüshası seçilen
              sırayla hazırlanır.
            </p>
          )}
          {secili.size === 0 && sayfa.count > EN_COK_ETIKET && (
            <p>
              Kuyrukta {formatNumber(sayfa.count)} nüsha var; bir partiye en çok{" "}
              {formatNumber(EN_COK_ETIKET)} nüsha girer, kalanlar kuyrukta kalır ve bir sonraki
              parti kaldığı yerden devam eder.
            </p>
          )}
          {parti && (
            <p>
              Önce hazırlanan partiyi basıldı olarak işaretleyin ya da partiden vazgeçin; önceki
              partiler için{" "}
              <button
                type="button"
                onClick={onGecmis}
                className="text-primary underline underline-offset-2"
              >
                Basım Geçmişi
              </button>
              'ne bakın.
            </p>
          )}
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            icon="print"
            onClick={() => void hazirla()}
            disabled={
              hazirlaniyor ||
              parti !== null ||
              govde === null ||
              basilacak === 0 ||
              aktifSablon === undefined
            }
          >
            {hazirlaniyor ? "Hazırlanıyor…" : "Basım partisini hazırla"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
