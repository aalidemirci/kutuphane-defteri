// Ayıklama (F8; Md. 12/1, tasarım §10 E7, D15). Katalog'un sağ üstündeki bağlantıyla
// açılır; YALNIZ yönetici kipinde (uçlar görevli izin listesinde değildir).
//
// Ayıklama komisyon kararıdır, kayıttan düşme ve devir taşınır işlemidir (sözlük:
// "Ayıklama ≠ kayıttan düşme"). Akış: taslak teklif → kalemler (gerekçe seçilince TMY
// yolu E7 tablosundan kendiliğinden gelir) → komisyona sun → Seçim ve Ayıklama
// Komisyonunun "Ayıklama" türündeki kararını bağla → harcama yetkilisinin onayını işle →
// uygula. Teklif her adımda geri çekilir (taslağa döner) ya da iptal edilir; nüsha durumu
// YALNIZ uygulamada değişir.
//
// Sayfa iki görünümlüdür: teklif listesi ve `?teklif=<kimlik>` ile teklif ayrıntısı
// (`TeklifAyrintisi.tsx`). İç kimlik ekranda yazılmaz; teklif ders yılı ve açılış
// tarihiyle tanınır.

import { useCallback, useEffect, useState } from "react";
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
import ModuleHeader from "../../ui/ModuleHeader";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { KATALOG_SAYFA_BOYUTU } from "../kutuphane/api";
import { kodSecenekleri } from "../kutuphane/ortak";
import { YanEkranBaglantilari } from "../yil/ortak";
import { AYIKLAMA_BASLIGI, NADIR_ESERLER_ADRESI, TEKLIF_DURUMU_TR, ayiklamaApi } from "./api";
import type { Teklif, TeklifDurumu } from "./api";
import { KOMISYON_KARARLARI_ADRESI, Rozet } from "./ortak";
import TeklifAyrintisi from "./TeklifAyrintisi";

export default function AyiklamaPage() {
  const [params, setParams] = useSearchParams();
  const teklifId = Number(params.get("teklif")) || null;

  const ac = useCallback(
    (id: number | null) => {
      setParams((onceki) => {
        const yeni = new URLSearchParams(onceki);
        if (id === null) yeni.delete("teklif");
        else yeni.set("teklif", String(id));
        return yeni;
      });
    },
    [setParams],
  );

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader
        backTo="/katalog"
        moduleLabel="Katalog"
        title={AYIKLAMA_BASLIGI}
        actions={
          <YanEkranBaglantilari
            baglantilar={[
              { to: NADIR_ESERLER_ADRESI, label: "Nadir Eserler", icon: "history_edu" },
              { to: KOMISYON_KARARLARI_ADRESI, label: "Komisyon Kararları", icon: "gavel" },
            ]}
          />
        }
      />

      <p className="kd-page-description max-w-4xl">
        Yıpranan, bilimsel değeri kalmayan, kurumun düzeyine uygun olmayan ya da 10. maddedeki
        ölçütlere uygun olmayan kaynaklar bir teklifle Seçim ve Ayıklama Komisyonuna sunulur
        (Yönetmelik Md. 12/1). Ayıklama komisyon kararıdır; kayıttan düşme ve devir, harcama
        yetkilisinin onayıyla yapılan taşınır işlemidir. Nüsha durumu yalnız teklif uygulanınca
        değişir.
      </p>

      {teklifId !== null ? (
        <TeklifAyrintisi id={teklifId} onGeri={() => ac(null)} />
      ) : (
        <TeklifListesi onAc={(id) => ac(id)} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Teklif listesi
// ---------------------------------------------------------------------------

const DURUM_TONU: Record<TeklifDurumu, "ikincil" | "ucuncul" | "notr"> = {
  DRAFT: "notr",
  SUBMITTED: "ucuncul",
  DECIDED: "ucuncul",
  APPROVED: "ucuncul",
  APPLIED: "ikincil",
  CANCELLED: "notr",
};

function TeklifListesi({ onAc }: { onAc: (id: number) => void }) {
  const [durum, setDurum] = useState<TeklifDurumu | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Teklif>>(emptyPage<Teklif>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    ayiklamaApi
      .teklifler({ status: durum, limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Ayıklama teklifleri yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [durum, offset]);

  const yeniTeklif = async () => {
    setBusy(true);
    setHata(null);
    try {
      const teklif = await ayiklamaApi.teklifAc();
      snackbar.success("Ayıklama teklifi açıldı.");
      onAc(teklif.id);
    } catch (e) {
      setHata(hataOku(e, "Ayıklama teklifi açılamadı."));
      setBusy(false);
    }
  };

  const sutunlar: Column<Teklif>[] = [
    { header: "Ders yılı", cell: (t) => t.school_year_name },
    { header: "Açılış", cell: (t) => formatDate(t.created_at) },
    {
      header: "Durum",
      cell: (t) => <Rozet ton={DURUM_TONU[t.status]}>{t.status_display}</Rozet>,
    },
    {
      header: "Kalem",
      align: "right",
      cell: (t) => formatNumber(t.counts.items),
    },
    {
      header: "Kayıttan düşme · devir",
      cell: (t) => `${formatNumber(t.counts.write_off)} · ${formatNumber(t.counts.transfer)}`,
    },
    {
      header: "Komisyon kararı",
      cell: (t) =>
        t.decision
          ? `${formatDate(t.decision.decision_date)}${
              t.decision.decision_no ? ` · ${t.decision.decision_no}` : ""
            }`
          : "—",
    },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
          <Select
            className="w-64"
            label="Durum"
            placeholder="Tümü"
            value={durum}
            onChange={(e) => {
              setDurum(e.target.value as TeklifDurumu | "");
              setOffset(0);
            }}
            options={kodSecenekleri(TEKLIF_DURUMU_TR)}
          />
        </Card>
        <Button icon="add" onClick={() => void yeniTeklif()} disabled={busy}>
          {busy ? "Açılıyor…" : "Yeni teklif"}
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="inventory"
          title="Gösterilecek ayıklama teklifi yok"
          description="“Yeni teklif” ile bir taslak açın; kalemleri aday listesinden seçin ya da kitapların kütüphane etiketlerini okutun."
        />
      ) : (
        <>
          <DataTable<Teklif>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(t) => onAc(t.id)}
            rowLabel={(t) =>
              `${t.school_year_name} ders yılının ${formatDate(t.created_at)} tarihli teklifini aç`
            }
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
