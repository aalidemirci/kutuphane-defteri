// Komisyon kararları — Seçim ve Ayıklama Komisyonu (Md. 4/1-ı, 10/1).
//
// Program seçim ölçütlerini DENETLEMEZ; komisyonun kararını kayıt altına alır.
// Kararın TÜRÜ bağlayıcıdır: bağış ancak "bağış değerlendirme" kararıyla
// kataloglanır, ayıklama ancak "ayıklama" kararıyla yapılır. Kullanılmış bir
// kararın türü değiştirilemez ve kaydı silinemez — sunucu reddeder, arayüz de
// "kullanımda" rozetiyle bunu önceden söyler.
//
// Başkan adı ve katılımcılar KİŞİ ADIDIR: sunucuda şifreli saklanır; yönetici
// parolası kurulmadan yazan istek 409 döner ve bant kullanıcıyı sihirbaza yollar.

import { useCallback, useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatDate, todayIso } from "../../lib/format";
import { emptyPage, geriDusulecekOffset } from "../../lib/pagination";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { COMMISSION_DECISION_TYPE_TR, KATALOG_SAYFA_BOYUTU, kutuphaneApi } from "./api";
import type { CommissionDecision, CommissionDecisionBody, CommissionDecisionType } from "./api";
import { MetinAlani, kodSecenekleri } from "./ortak";

export default function KomisyonPaneli() {
  const [tur, setTur] = useState<CommissionDecisionType | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] =
    useState<Paginated<CommissionDecision>>(emptyPage<CommissionDecision>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [yeni, setYeni] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<CommissionDecision | null>(null);

  const tazele = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listCommissionDecisions({ decisionType: tur, limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Komisyon kararları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [tur, offset, tazeleme]);

  const sutunlar: Column<CommissionDecision>[] = [
    { header: "Karar türü", cell: (k) => k.decision_type_display },
    { header: "Karar tarihi", cell: (k) => formatDate(k.decision_date) },
    { header: "Karar sayısı", cell: (k) => k.decision_no || "—" },
    { header: "Başkan", cell: (k) => k.chair_name },
    {
      header: "Durum",
      cell: (k) =>
        k.in_use ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
            <Icon name="link" size="sm" />
            Kullanımda
          </span>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
          <Select
            className="w-64"
            label="Karar türü"
            placeholder="Tümü"
            value={tur}
            onChange={(e) => {
              setTur(e.target.value as CommissionDecisionType | "");
              setOffset(0);
            }}
            options={kodSecenekleri(COMMISSION_DECISION_TYPE_TR)}
          />
        </Card>
        <Button icon="add" onClick={() => setYeni(true)}>
          Karar ekle
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="gavel"
          title="Gösterilecek komisyon kararı yok"
          description="Bağış kabulü ve ayıklama, Seçim ve Ayıklama Komisyonu kararına dayanır."
        />
      ) : (
        <>
          <DataTable<CommissionDecision>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(k) => setDuzenlenen(k)}
            rowLabel={(k) => `${k.decision_type_display} kararını düzenle`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}

      {(yeni || duzenlenen !== null) && (
        <KararFormu
          karar={duzenlenen}
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

function KararFormu({
  karar,
  onClose,
  onSaved,
}: {
  karar: CommissionDecision | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [tur, setTur] = useState<CommissionDecisionType>(karar?.decision_type ?? "DONATION_REVIEW");
  const [tarih, setTarih] = useState(karar?.decision_date ?? todayIso());
  const [sayi, setSayi] = useState(karar?.decision_no ?? "");
  const [baskan, setBaskan] = useState(karar?.chair_name ?? "");
  const [unvan, setUnvan] = useState(karar?.chair_title ?? "");
  const [katilimcilar, setKatilimcilar] = useState(karar?.participants_text ?? "");
  const [notlar, setNotlar] = useState(karar?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const kullanimda = karar?.in_use ?? false;

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if (!baskan.trim()) {
      setFieldError("chair_name", "Başkan adı yazılmalıdır.");
      return;
    }
    const govde: CommissionDecisionBody = {
      decision_type: tur,
      decision_date: tarih,
      decision_no: sayi.trim(),
      chair_name: baskan.trim(),
      chair_title: unvan.trim(),
      participants_text: katilimcilar.trim(),
      notes: notlar.trim(),
    };
    setBusy(true);
    try {
      if (karar) await kutuphaneApi.updateCommissionDecision(karar.id, govde);
      else await kutuphaneApi.createCommissionDecision(govde);
      snackbar.success(karar ? "Komisyon kararı güncellendi." : "Komisyon kararı eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Komisyon kararı kaydedilemedi."));
      setBusy(false);
    }
  };

  const sil = async () => {
    if (karar === null) return;
    const onay = await confirm({
      title: "Komisyon kararı silinsin mi?",
      message:
        "Karar kayıttan kalkar. Bir edinime ya da bağış ön kaydına bağlı karar silinemez; o kayıtların dayanağıdır.",
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await kutuphaneApi.deleteCommissionDecision(karar.id);
      snackbar.success("Komisyon kararı silindi.");
      onSaved();
    } catch (e) {
      setHata(hataOku(e, "Komisyon kararı silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={karar ? "Kararı düzenle" : "Yeni komisyon kararı"}
      actions={
        <>
          {karar && !kullanimda && (
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
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select
            label="Karar türü"
            required
            value={tur}
            disabled={kullanimda}
            onChange={(e) => setTur(e.target.value as CommissionDecisionType)}
            options={kodSecenekleri(COMMISSION_DECISION_TYPE_TR)}
            error={errors.decision_type}
            helperText={
              kullanimda
                ? "Karara bağlı kayıt olduğu için tür değiştirilemez."
                : "Bağış kabulü ve ayıklama ayrı karar türleridir."
            }
          />
          <TextField
            label="Karar tarihi"
            required
            type="date"
            value={tarih}
            onChange={(e) => setTarih(e.target.value)}
            error={errors.decision_date}
          />
          <TextField
            label="Karar sayısı"
            value={sayi}
            onChange={(e) => setSayi(e.target.value)}
            error={errors.decision_no}
          />
          <TextField
            label="Başkan adı"
            required
            value={baskan}
            onChange={(e) => setBaskan(e.target.value)}
            error={errors.chair_name}
            helperText="Şifreli saklanır; kilitliyken ve parola kurulmadan yazılamaz."
          />
          <TextField
            label="Başkan unvanı"
            value={unvan}
            onChange={(e) => setUnvan(e.target.value)}
            error={errors.chair_title}
          />
        </div>

        <MetinAlani
          label="Katılımcılar"
          value={katilimcilar}
          onChange={setKatilimcilar}
          error={errors.participants_text}
          helperText="Satır başına bir kişi. Şifreli saklanır."
        />
        <MetinAlani label="Notlar" value={notlar} onChange={setNotlar} error={errors.notes} />
      </div>
    </Dialog>
  );
}
