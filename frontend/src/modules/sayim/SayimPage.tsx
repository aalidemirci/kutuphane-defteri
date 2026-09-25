// Sayım (F9; Taşınır Mal Yönetmeliği md. 32, tasarım §9-10, §9-11, §10 E10). Katalog'un sağ
// üstündeki bağlantıyla ve Genel Bakış'taki "Sayım" kartıyla açılır; YALNIZ yönetici kipinde
// (görevli izin listesinde sayım uçlarından yalnız okutma vardır — görevli okutmayı Görevli
// Kipi ekranından yapar, madde 24).
//
// Akış: taslak (sayım kurulu, iki AYRI seçenek — TMY 32/3 durdurması ve sayım için hizmet
// arası —, ödünçteki, teslimdeki ve onarımdaki nüsha için kurulun seçimi) → başlat (anlık görüntü) →
// okutma (kuyruk) → tamamla (noksan varsa ikinci sayım — 32/6) → harcama yetkilisinin onayı
// (noksan 32/7, hasar önerisi 27/1, fazla TMY 17) · her adımda iptal. İade hiçbir durumda
// durmaz.
//
// Sayfa iki görünümlüdür: sayım listesi ve `?sayim=<kimlik>` ile sayım ayrıntısı
// (`SayimAyrintisi.tsx`). İç kimlik ekranda yazılmaz; sayım mali yılı ve başlangıç
// tarihiyle tanınır.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import ModuleHeader from "../../ui/ModuleHeader";
import PaginationBar from "../../ui/PaginationBar";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { Rozet } from "../ayiklama/ortak";
import { KATALOG_SAYFA_BOYUTU } from "../kutuphane/api";
import { SAYIM_BASLIGI, sayimAdi, sayimApi } from "./api";
import type { Sayim, SayimDurumu } from "./api";
import SayimAyrintisi from "./SayimAyrintisi";

/** Sayfanın açıklaması (kılavuz aynı dili kullanır). */
export const SAYIM_ACIKLAMASI =
  "Kütüphane materyalinin sayımı sayım kurulunca yapılır (Taşınır Mal Yönetmeliği md. 32). " +
  "Başlatınca o anki kayıtlar sayımın anlık görüntüsü olur; kitaplar okutulur, bulunamayanlar " +
  "bir kez daha aranır ve sonuç harcama yetkilisinin onayıyla kayda geçer. İade hiçbir " +
  "durumda durmaz.";

export default function SayimPage() {
  const [params, setParams] = useSearchParams();
  const sayimId = Number(params.get("sayim")) || null;

  const ac = useCallback(
    (id: number | null) => {
      setParams((onceki) => {
        const yeni = new URLSearchParams(onceki);
        if (id === null) yeni.delete("sayim");
        else yeni.set("sayim", String(id));
        return yeni;
      });
    },
    [setParams],
  );

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader backTo="/katalog" moduleLabel="Katalog" title={SAYIM_BASLIGI} />
      <p className="kd-page-description max-w-4xl">{SAYIM_ACIKLAMASI}</p>
      {sayimId !== null ? (
        <SayimAyrintisi id={sayimId} onGeri={() => ac(null)} />
      ) : (
        <SayimListesi onAc={(id) => ac(id)} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sayım listesi
// ---------------------------------------------------------------------------

const DURUM_TONU: Record<SayimDurumu, "ikincil" | "ucuncul" | "notr"> = {
  DRAFT: "notr",
  IN_PROGRESS: "ucuncul",
  COMPLETED: "ucuncul",
  APPROVED: "ikincil",
  CANCELLED: "notr",
};

/** Canlı (onaylanmamış, iptal edilmemiş) sayım durumları — aynı anda tek canlı sayım. */
const CANLI: SayimDurumu[] = ["DRAFT", "IN_PROGRESS", "COMPLETED"];

function SayimListesi({ onAc }: { onAc: (id: number) => void }) {
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Sayim>>(emptyPage<Sayim>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    sayimApi
      .sayimlar({ limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Sayımlar yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [offset]);

  const canli = sayfa.results.find((s) => CANLI.includes(s.status)) ?? null;

  const yeniSayim = async () => {
    setBusy(true);
    setHata(null);
    try {
      const sayim = await sayimApi.taslakAc();
      snackbar.success("Sayım taslağı açıldı.");
      onAc(sayim.id);
    } catch (e) {
      setHata(hataOku(e, "Sayım taslağı açılamadı."));
      setBusy(false);
    }
  };

  const sutunlar: Column<Sayim>[] = [
    { header: "Mali yıl", cell: (s) => (s.fiscal_year ? String(s.fiscal_year) : "—") },
    { header: "Başlangıç", cell: (s) => formatDate(s.started_at) },
    {
      header: "Durum",
      cell: (s) => (
        <Rozet ton={DURUM_TONU[s.status]}>
          {s.status === "IN_PROGRESS" && s.round === 2 ? "İkinci sayım" : s.status_display}
        </Rozet>
      ),
    },
    {
      header: "Seçenekler",
      cell: (s) =>
        [s.tmy_stop ? "TMY 32/3 durdurması" : "", s.service_pause ? "Hizmet arası" : ""]
          .filter(Boolean)
          .join(" · ") || "—",
    },
    { header: "Onay", cell: (s) => formatDate(s.approved_on) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-body-medium text-on-surface-variant">
          {canli
            ? "Onaylanmamış bir sayım var; yeni sayım açmadan önce onu onaylayın ya da iptal edin."
            : `${formatNumber(sayfa.count)} sayım kaydı.`}
        </p>
        {canli ? (
          <Button icon="open_in_new" variant="tonal" onClick={() => onAc(canli.id)}>
            Süren sayımı aç
          </Button>
        ) : (
          <Button icon="add" onClick={() => void yeniSayim()} disabled={busy || yukleniyor}>
            {busy ? "Açılıyor…" : "Yeni sayım"}
          </Button>
        )}
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="inventory_2"
          title="Henüz sayım yok"
          description="“Yeni sayım” ile bir taslak açın: sayım kurulunu ve seçenekleri yazın, sonra sayımı başlatın."
        />
      ) : (
        <>
          <DataTable<Sayim>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(s) => onAc(s.id)}
            rowLabel={(s) => `${sayimAdi(s)} sayımını aç`}
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
