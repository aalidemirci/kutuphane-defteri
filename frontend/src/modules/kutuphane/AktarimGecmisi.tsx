// Aktarım geçmişi (tasarım §8.1) — hangi dosya ne zaman aktarıldı.
//
// Liste iki soruya cevap verir: bu dosya daha önce uygulandı mı (fikirdeşliğin
// izi) ve hangi aktarımdan kaç nüsha doğdu. Kişisel veri taşımaz; dosya adı ve
// sayılardan ibarettir.
//
// Her ÖNİZLEME de buraya bir satır yazar (sunucu kalıcı iz tutar). Kullanıcı
// yarım kalmış bir önizlemeyi "Önizlemeyi iptal et" ile düşürebilir; uygulanmış
// aktarım iptal EDİLEMEZ — aynı dosyanın ikinci kez uygulanmasını engelleyen iz
// odur.

import { useCallback, useEffect, useState } from "react";

import { formatDateTime, formatNumber } from "../../lib/format";
import { emptyPage } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { KATALOG_SAYFA_BOYUTU, kutuphaneApi } from "./api";
import type { AktarimKosusu } from "./api";

export default function AktarimGecmisi({ tazeleme = 0 }: { tazeleme?: number }) {
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<AktarimKosusu>>(emptyPage<AktarimKosusu>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [yenile, setYenile] = useState(0);
  const confirm = useConfirm();
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    kutuphaneApi
      .aktarimGecmisi({ limit: KATALOG_SAYFA_BOYUTU, offset })
      .then((sonuc) => {
        if (iptal) return;
        setSayfa(sonuc);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Aktarım geçmişi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [offset, yenile, tazeleme]);

  const iptalEt = useCallback(
    async (kosu: AktarimKosusu) => {
      const onay = await confirm({
        title: "Bu önizleme geçmişten düşürülsün mü?",
        message:
          "Önizleme hiçbir kayıt yazmamıştı; satır “İptal edildi” olarak işaretlenir. " +
          "Aynı dosyayı yeniden önizleyip uygulayabilirsiniz.",
        confirmLabel: "İptal et",
      });
      if (!onay) return;
      try {
        await kutuphaneApi.aktarimiIptalEt(kosu.id);
        snackbar.success("Önizleme iptal edildi.");
        setYenile((k) => k + 1);
      } catch (e) {
        setHata(hataOku(e, "Önizleme iptal edilemedi."));
      }
    },
    [confirm, snackbar],
  );

  const sutunlar: Column<AktarimKosusu>[] = [
    { header: "Tarih", cell: (k) => formatDateTime(k.created_at) },
    { header: "Dosya", cell: (k) => k.uploaded_file_name || "Yapıştırılan liste" },
    { header: "Kaynak", cell: (k) => k.source_display },
    { header: "Durum", cell: (k) => k.status_display },
    {
      header: "Satır",
      align: "right",
      cell: (k) => formatNumber(k.stats.total_rows ?? 0),
    },
    {
      header: "Nüsha",
      align: "right",
      cell: (k) => formatNumber(k.stats.copies_created ?? 0),
    },
    {
      header: "",
      cell: (k) =>
        k.status === "DRY_RUN" ? (
          <Button variant="text" icon="delete" onClick={() => void iptalEt(k)}>
            Önizlemeyi iptal et
          </Button>
        ) : null,
    },
  ];

  if (yukleniyor) return <SkeletonList rows={4} />;

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      {hata && <ErrorBand hata={hata} />}
      {sayfa.results.length === 0 ? (
        <EmptyState
          icon="history"
          title="Henüz aktarım yapılmadı"
          description="Excel dosyasından ya da yapay zekâ köprüsünden yaptığınız her önizleme ve aktarım burada listelenir."
        />
      ) : (
        <>
          <DataTable<AktarimKosusu> columns={sutunlar} rows={sayfa.results} />
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
