// Ayarlar → Bölümler. Bölüm KONTROLLÜ BİR LİSTEDİR (sözlük §1: "bölüm", "raf"
// değil): Excel'den gelen "Edebiyat", "edebiyat ", "EDEBİYAT " yazımları tek
// bölüme eşlensin, raf etiketleri ve Ağ Kataloğu dizinleri tutarlı kalsın.
//
// Ad tekliği SUNUCUDA ve Türkçe katlamalıdır; burada tekrarlanmaz. DOS aralığı
// yalnız bilgilendirmedir: aralığı aşan bir eser de o bölüme konabilir.

import { useCallback, useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { kutuphaneApi } from "./api";
import type { Section, SectionBody } from "./api";
import { SECICI_SINIRI } from "./ortak";

export default function BolumlerPaneli() {
  const [bolumler, setBolumler] = useState<Section[]>([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [yeni, setYeni] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<Section | null>(null);

  const tazele = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    kutuphaneApi
      // Kontrollü liste kısadır; seçiciler de aynı listeden beslenir, kesilmemeli.
      .listSections({ limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (iptal) return;
        setBolumler(sayfa.results);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Bölümler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [tazeleme]);

  const sutunlar: Column<Section>[] = [
    { header: "Ad", cell: (b) => b.name },
    {
      header: "DOS aralığı",
      cell: (b) =>
        b.dewey_from || b.dewey_to ? `${b.dewey_from || "…"}–${b.dewey_to || "…"}` : "—",
    },
    { header: "Kısa tarif", cell: (b) => b.description || "—" },
    { header: "Sıra", align: "right", cell: (b) => formatNumber(b.sort_order) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Bölümler</p>
          <p className="text-body-small text-on-surface-variant">
            Eser ve nüshalar bu listedeki bölümlere bağlanır. Küçük sıra numarası önce gelir. “DOS
            aralığı” bölümün Dewey Onlu Sınıflama (DOS) aralığıdır ve yalnız bilgilendirmedir.
          </p>
        </div>
        <Button icon="add" onClick={() => setYeni(true)}>
          Bölüm ekle
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : bolumler.length === 0 ? (
        <EmptyState
          icon="category"
          title="Henüz bölüm yok"
          description="Kütüphanenin konu bölümlerini buradan tanımlayın (ör. Edebiyat, Tarih, Başvuru)."
        />
      ) : (
        <DataTable<Section>
          columns={sutunlar}
          rows={bolumler}
          onRowClick={(b) => setDuzenlenen(b)}
          rowLabel={(b) => `${b.name} bölümünü düzenle`}
        />
      )}

      {(yeni || duzenlenen !== null) && (
        <BolumFormu
          bolum={duzenlenen}
          onClose={() => {
            setYeni(false);
            setDuzenlenen(null);
          }}
          onSaved={() => {
            setYeni(false);
            setDuzenlenen(null);
            tazele();
          }}
        />
      )}
    </div>
  );
}

function BolumFormu({
  bolum,
  onClose,
  onSaved,
}: {
  bolum: Section | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [ad, setAd] = useState(bolum?.name ?? "");
  const [dosBas, setDosBas] = useState(bolum?.dewey_from ?? "");
  const [dosSon, setDosSon] = useState(bolum?.dewey_to ?? "");
  const [tarif, setTarif] = useState(bolum?.description ?? "");
  const [sira, setSira] = useState(String(bolum?.sort_order ?? 0));
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if (!ad.trim()) {
      setFieldError("name", "Bölüm adı yazılmalıdır.");
      return;
    }
    const govde: SectionBody = {
      name: ad.trim(),
      dewey_from: dosBas.trim(),
      dewey_to: dosSon.trim(),
      description: tarif.trim(),
      sort_order: Number(sira) || 0,
    };
    setBusy(true);
    try {
      if (bolum) await kutuphaneApi.updateSection(bolum.id, govde);
      else await kutuphaneApi.createSection(govde);
      snackbar.success(bolum ? "Bölüm güncellendi." : "Bölüm eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Bölüm kaydedilemedi."));
      setBusy(false);
    }
  };

  const sil = async () => {
    if (bolum === null) return;
    const onay = await confirm({
      title: "Bölüm silinsin mi?",
      message: `“${bolum.name}” listeden kalkar. Bölümde eser ya da nüsha varsa silinemez; önce onları başka bir bölüme taşıyın.`,
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await kutuphaneApi.deleteSection(bolum.id);
      snackbar.success("Bölüm silindi.");
      onSaved();
    } catch (e) {
      setHata(hataOku(e, "Bölüm silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={bolum ? "Bölümü düzenle" : "Yeni bölüm"}
      actions={
        <>
          {bolum && (
            <Button variant="text" icon="delete" onClick={sil} disabled={busy}>
              Sil
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={kaydet} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {hata && <ErrorBand hata={hata} />}
        <TextField
          label="Ad"
          required
          value={ad}
          onChange={(e) => setAd(e.target.value)}
          error={errors.name}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="DOS aralığı başı"
            value={dosBas}
            onChange={(e) => setDosBas(e.target.value)}
            error={errors.dewey_from}
            helperText="Dewey Onlu Sınıflama (DOS). Ör. 800"
          />
          <TextField
            label="DOS aralığı sonu"
            value={dosSon}
            onChange={(e) => setDosSon(e.target.value)}
            error={errors.dewey_to}
            helperText="Ör. 899"
          />
        </div>
        <TextField
          label="Kısa tarif"
          value={tarif}
          onChange={(e) => setTarif(e.target.value)}
          error={errors.description}
        />
        <TextField
          label="Sıra"
          inputMode="numeric"
          value={sira}
          onChange={(e) => setSira(e.target.value)}
          error={errors.sort_order}
          helperText="Küçük sayı önce gelir; eşitlikte ad sırası uygulanır."
        />
      </div>
    </Dialog>
  );
}
