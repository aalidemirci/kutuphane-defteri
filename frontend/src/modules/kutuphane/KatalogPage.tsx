// Katalog sayfası — eser ve nüsha listelerinin tek ekranı (tasarım §6.2, F2).
// İki sekme: "Eserler" (künye ekseni: Türkçe arama + üç eksenli sıralama) ve
// "Nüshalar" (fiziksel eksen: barkod, bölüm, durum, ödünç verilebilirlik).
// Sekme adreste tutulur (`?tab=nushalar`), böylece kılavuz ve başka ekranlar
// doğrudan bağlanabilir.
//
// Arama ve sıralama SUNUCUDADIR (T7, D2): Türkçe katlama ve alfabe sırası
// veritabanında anahtar alanlarla çalışır, ön yüz yalnız gecikmeli (debounce)
// gönderir. Sayfalama da sunucudadır (D9) — katalog on binlerce satır olabilir.
//
// Kip: bu ekran yönetici kipindedir; görevli kipinde gezinme zaten kapalıdır ve
// uçlar 403 `kip_yetkisiz` döner. 423/403 yanıtları `lib/api.ts` üzerinden mevcut
// kilit ve kip olaylarına düşer — burada ayrı bir yol açılmaz.

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useDebounced } from "../../hooks/useDebounced";
import { useTabParam } from "../../hooks/useTabParam";
import { formatNumber } from "../../lib/format";
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
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import {
  COPY_STATUS_TR,
  KATALOG_SAYFA_BOYUTU,
  RESOURCE_TYPE_TR,
  WORK_ORDER_TR,
  kutuphaneApi,
} from "./api";
import type { Copy, CopyStatus, ResourceType, Section, Work, WorkOrder } from "./api";
import EserFormu from "./EserFormu";
import { OduncDurumu, bolumSecenekleri, kodSecenekleri, useBolumler } from "./ortak";

/** Edinimler ve Bağışlar ekranının adresi (katalogdan girilir). */
export const EDINIMLER_ADRESI = "/katalog/edinimler";

/** Bir eserin ayrıntı adresi. */
export function eserAdresi(id: number): string {
  return `/katalog/eser/${id}`;
}

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["eserler", "nushalar"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TABS: TabItem[] = [
  { key: "eserler", label: "Eserler", icon: "menu_book" },
  { key: "nushalar", label: "Nüshalar", icon: "inventory_2" },
];

export default function KatalogPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "eserler");
  const bolumler = useBolumler();

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">Katalog</h1>
          <p className="kd-page-description">
            Kütüphanenin künye ve nüsha kayıtları. Bir eserin birden çok nüshası olabilir; rafta
            duran her kitabın kendi barkodu ve kayıt numarası vardır. Arama kaynak adı, yazar, konu
            ve ISBN üzerinde çalışır.
          </p>
        </div>
        <Link
          to={EDINIMLER_ADRESI}
          className="inline-flex min-h-[var(--kd-control-height)] items-center gap-2 rounded-shape-md border border-outline-variant bg-surface-container-lowest px-4 text-label-large font-semibold text-primary transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="local_shipping" size="lg" />
          Edinimler ve Bağışlar
        </Link>
      </div>

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Katalog bölümleri"
        idBase="katalog"
      />

      <div {...tabPanelProps("katalog", tab)}>
        {tab === "eserler" && <EserlerSekmesi bolumler={bolumler} />}
        {tab === "nushalar" && <NushalarSekmesi bolumler={bolumler} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Eserler sekmesi
// ---------------------------------------------------------------------------

function EserlerSekmesi({ bolumler }: { bolumler: Section[] }) {
  const navigate = useNavigate();
  const [aramaGirdisi, setAramaGirdisi] = useState("");
  const arama = useDebounced(aramaGirdisi);
  const [bolum, setBolum] = useState("");
  const [tur, setTur] = useState<ResourceType | "">("");
  const [siralama, setSiralama] = useState<WorkOrder>("title");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Work>>(emptyPage<Work>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [yeniEser, setYeniEser] = useState(false);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listWorks({
        q: arama,
        section: bolum ? Number(bolum) : null,
        resourceType: tur,
        order: siralama,
        limit: KATALOG_SAYFA_BOYUTU,
        offset,
      })
      .then((sonuc) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(sonuc, offset, KATALOG_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(sonuc);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Eser listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [arama, bolum, tur, siralama, offset, tazeleme]);

  const sutunlar: Column<Work>[] = [
    { header: "Kaynak adı", cell: (w) => w.title },
    { header: "Yazar(lar)", cell: (w) => w.authors || "—" },
    { header: "Bölüm", cell: (w) => w.section_name || "—" },
    { header: "Kaynak türü", cell: (w) => w.resource_type_display },
    { header: "Nüsha", align: "right", cell: (w) => formatNumber(w.copy_count) },
    { header: "Rafta", align: "right", cell: (w) => formatNumber(w.available_copy_count) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Eserler</p>
          {!yukleniyor && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(sayfa.count)} kayıt
            </p>
          )}
        </div>
        <Button icon="add" onClick={() => setYeniEser(true)}>
          Eser ekle
        </Button>
      </div>

      <Card
        elevation={0}
        className="grid items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1 sm:grid-cols-[minmax(15rem,1fr)_10rem_10rem_12rem]"
      >
        <TextField
          label="Ara"
          value={aramaGirdisi}
          onChange={(e) => {
            setAramaGirdisi(e.target.value);
            setOffset(0);
          }}
          placeholder="Kaynak adı, yazar, konu veya ISBN…"
          helperText="Büyük-küçük harf ve düzeltme işareti aranmaz; “ı” ile “i” ayrı harflerdir."
        />
        <Select
          label="Bölüm"
          placeholder="Tümü"
          value={bolum}
          onChange={(e) => {
            setBolum(e.target.value);
            setOffset(0);
          }}
          options={bolumSecenekleri(bolumler)}
        />
        <Select
          label="Kaynak türü"
          placeholder="Tümü"
          value={tur}
          onChange={(e) => {
            setTur(e.target.value as ResourceType | "");
            setOffset(0);
          }}
          options={kodSecenekleri(RESOURCE_TYPE_TR)}
        />
        <Select
          label="Sırala"
          value={siralama}
          onChange={(e) => {
            setSiralama(e.target.value as WorkOrder);
            setOffset(0);
          }}
          options={kodSecenekleri(WORK_ORDER_TR)}
        />
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={5} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="menu_book"
          title="Gösterilecek eser yok"
          description="Süzgeçleri değiştirin ya da yeni bir eser ekleyin. Toplu giriş için Genel Bakış'taki Katalog Excel Şablonu'nu kullanabilirsiniz."
        />
      ) : (
        <>
          <DataTable<Work>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(w) => navigate(eserAdresi(w.id))}
            rowLabel={(w) => `${w.title} künyesini aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}

      {yeniEser && (
        <EserFormu
          eser={null}
          bolumler={bolumler}
          onClose={() => setYeniEser(false)}
          onSaved={(eser) => {
            setYeniEser(false);
            setTazeleme((k) => k + 1);
            navigate(eserAdresi(eser.id));
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Nüshalar sekmesi
// ---------------------------------------------------------------------------

function NushalarSekmesi({ bolumler }: { bolumler: Section[] }) {
  const navigate = useNavigate();
  const [barkodGirdisi, setBarkodGirdisi] = useState("");
  const barkod = useDebounced(barkodGirdisi);
  const [bolum, setBolum] = useState("");
  const [durum, setDurum] = useState<CopyStatus | "">("");
  const [yalnizOdunc, setYalnizOdunc] = useState(false);
  const [yalnizEtiketsiz, setYalnizEtiketsiz] = useState(false);
  const [dusulenleriGizle, setDusulenleriGizle] = useState(false);
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Copy>>(emptyPage<Copy>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listCopies({
        barcode: barkod,
        section: bolum ? Number(bolum) : null,
        status: durum,
        onlyLoanable: yalnizOdunc,
        onlyUnlabeled: yalnizEtiketsiz,
        excludeTerminal: dusulenleriGizle,
        limit: KATALOG_SAYFA_BOYUTU,
        offset,
      })
      .then((sonuc) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(sonuc, offset, KATALOG_SAYFA_BOYUTU);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(sonuc);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Nüsha listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [barkod, bolum, durum, yalnizOdunc, yalnizEtiketsiz, dusulenleriGizle, offset]);

  const sutunlar: Column<Copy>[] = [
    { header: "Barkod", cell: (c) => c.barcode_display },
    { header: "Kaynak adı", cell: (c) => c.work_title },
    { header: "Bölüm", cell: (c) => c.section_name || "—" },
    { header: "Durum", cell: (c) => <OduncDurumu nusha={c} /> },
    { header: "Kayıt no", align: "right", cell: (c) => formatNumber(c.accession_no) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div>
        <p className="text-title-medium text-on-surface">Nüshalar</p>
        {!yukleniyor && (
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(sayfa.count)} kayıt
          </p>
        )}
      </div>

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div className="grid items-end gap-3 sm:grid-cols-[minmax(12rem,1fr)_10rem_12rem]">
          <TextField
            label="Barkod"
            value={barkodGirdisi}
            onChange={(e) => {
              setBarkodGirdisi(e.target.value);
              setOffset(0);
            }}
            placeholder="2026-000123"
            helperText="Okutulan ya da basılı biçim; numaranın tamamı yazılır."
          />
          <Select
            label="Bölüm"
            placeholder="Tümü"
            value={bolum}
            onChange={(e) => {
              setBolum(e.target.value);
              setOffset(0);
            }}
            options={bolumSecenekleri(bolumler)}
          />
          <Select
            label="Durum"
            placeholder="Tümü"
            value={durum}
            onChange={(e) => {
              setDurum(e.target.value as CopyStatus | "");
              setOffset(0);
            }}
            options={kodSecenekleri(COPY_STATUS_TR)}
          />
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <SuzgecKutusu
            label="Yalnız ödünç verilebilenler"
            checked={yalnizOdunc}
            onChange={(v) => {
              setYalnizOdunc(v);
              setOffset(0);
            }}
          />
          <SuzgecKutusu
            label="Yalnız etiketlenmemişler"
            checked={yalnizEtiketsiz}
            onChange={(v) => {
              setYalnizEtiketsiz(v);
              setOffset(0);
            }}
          />
          <SuzgecKutusu
            label="Kayıttan düşülenleri gizle"
            checked={dusulenleriGizle}
            onChange={(v) => {
              setDusulenleriGizle(v);
              setOffset(0);
            }}
          />
        </div>
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={5} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="inventory_2"
          title="Gösterilecek nüsha yok"
          description="Süzgeçleri değiştirin. Nüshalar eserin künye sayfasından açılır."
        />
      ) : (
        <>
          <DataTable<Copy>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(c) => navigate(eserAdresi(c.work))}
            rowLabel={(c) => `${c.work_title} künyesini aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}
    </div>
  );
}

/** Süzgeç onay kutusu — etiketle birlikte tek dokunma hedefi. */
function SuzgecKutusu({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-5 shrink-0 accent-primary"
      />
      {label}
    </label>
  );
}
