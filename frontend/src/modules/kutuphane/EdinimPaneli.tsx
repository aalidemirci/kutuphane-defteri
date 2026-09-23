// Edinim partileri — "Edinimler ve Bağışlar" ekranının ilk sekmesi.
//
// Md. 10/5 dışarıdan sağlama yollarını sayar (Bakanlık gönderimi, satın alma,
// bağış, değişim); listedeki son iki yol kayıt-içi girişlerdir (sayım fazlasının
// kayda alınması ve mevcut koleksiyonun programa aktarımı).
//
// Bağışta komisyon kararı ZORUNLUDUR (Md. 10/3) ve kararın TÜRÜ denetlenir (bağış
// değerlendirme kararı olmalıdır). İkisi de sunucudadır; form yalnız seçimi
// kolaylaştırır, kuralı tekrarlamaz — ret sunucudan alan adıyla gelir.

import { useCallback, useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatDate, formatNumber, formatPrice, todayIso } from "../../lib/format";
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
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { ACQUISITION_METHOD_TR, KATALOG_SAYFA_BOYUTU, kutuphaneApi } from "./api";
import type { Acquisition, AcquisitionBody, AcquisitionMethod, CommissionDecision } from "./api";
import {
  MetinAlani,
  SECICI_SINIRI,
  kararEtiketi,
  kodSecenekleri,
  secimKesildiMetni,
  secimKesildiMi,
} from "./ortak";

export default function EdinimPaneli() {
  const [yol, setYol] = useState<AcquisitionMethod | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Acquisition>>(emptyPage<Acquisition>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [yeni, setYeni] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<Acquisition | null>(null);

  const tazele = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listAcquisitions({ method: yol, limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Edinim listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [yol, offset, tazeleme]);

  const sutunlar: Column<Acquisition>[] = [
    { header: "Edinim yolu", cell: (a) => a.method_display },
    { header: "Tarih", cell: (a) => formatDate(a.date) },
    { header: "Kaynak notu", cell: (a) => a.source_note || "—" },
    { header: "Birim fiyat", align: "right", cell: (a) => formatPrice(a.unit_price) },
    { header: "Nüsha", align: "right", cell: (a) => formatNumber(a.copy_count) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
          <Select
            className="w-64"
            label="Edinim yolu"
            placeholder="Tümü"
            value={yol}
            onChange={(e) => {
              setYol(e.target.value as AcquisitionMethod | "");
              setOffset(0);
            }}
            options={kodSecenekleri(ACQUISITION_METHOD_TR)}
          />
        </Card>
        <Button icon="add" onClick={() => setYeni(true)}>
          Edinim ekle
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="local_shipping"
          title="Gösterilecek edinim yok"
          description="Nüsha açabilmek için önce kaynağın hangi yolla geldiğini kaydedin."
        />
      ) : (
        <>
          <DataTable<Acquisition>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(a) => setDuzenlenen(a)}
            rowLabel={(a) => `${a.method_display} partisini düzenle`}
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
        <EdinimFormu
          edinim={duzenlenen}
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

function EdinimFormu({
  edinim,
  onClose,
  onSaved,
}: {
  edinim: Acquisition | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [yol, setYol] = useState<AcquisitionMethod>(edinim?.method ?? "PURCHASE");
  const [tarih, setTarih] = useState(edinim?.date ?? todayIso());
  const [kaynakNotu, setKaynakNotu] = useState(edinim?.source_note ?? "");
  const [fiyat, setFiyat] = useState(edinim?.unit_price ?? "");
  const [karar, setKarar] = useState(
    edinim?.commission_decision == null ? "" : String(edinim.commission_decision),
  );
  const [notlar, setNotlar] = useState(edinim?.notes ?? "");
  const [kararlar, setKararlar] = useState<CommissionDecision[]>([]);
  const [kesildi, setKesildi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  // Komisyon kararı seçicisi. İKİ tür yüklenir: bağışa "bağış değerlendirme",
  // öbür edinim yollarına "kaynak seçimi" kararı bağlanır (sunucu yalnız
  // ayıklama kararını reddeder). Tek tür yüklendiğinde "kaynak seçimi"
  // kararları hiçbir edinime bağlanamıyor, ölü kayıt olarak kalıyordu.
  useEffect(() => {
    let iptal = false;
    Promise.all([
      kutuphaneApi.listCommissionDecisions({
        decisionType: "DONATION_REVIEW",
        limit: SECICI_SINIRI,
      }),
      kutuphaneApi.listCommissionDecisions({ decisionType: "SELECTION", limit: SECICI_SINIRI }),
    ])
      .then(([bagis, secim]) => {
        if (iptal) return;
        setKararlar([...bagis.results, ...secim.results]);
        setKesildi(secimKesildiMi(bagis.results.length) || secimKesildiMi(secim.results.length));
      })
      .catch(() => {
        if (!iptal) setKararlar([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  // Seçenekler edinim yoluna göre daralır; KAYITLI değer her hâlde listede
  // kalır — yoksa `<select>` boş görünür ve kullanıcı kararın düştüğünü sanır.
  const beklenenKararTuru = yol === "DONATION" ? "DONATION_REVIEW" : "SELECTION";
  const kararSecenekleri = kararlar
    .filter((k) => k.decision_type === beklenenKararTuru || String(k.id) === karar)
    .map((k) => ({ value: String(k.id), label: kararEtiketi(k) }));

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    const govde: AcquisitionBody = {
      method: yol,
      date: tarih,
      source_note: kaynakNotu.trim(),
      unit_price: fiyat.trim() ? fiyat.trim() : null,
      commission_decision: karar ? Number(karar) : null,
      notes: notlar.trim(),
    };
    setBusy(true);
    try {
      if (edinim) await kutuphaneApi.updateAcquisition(edinim.id, govde);
      else await kutuphaneApi.createAcquisition(govde);
      snackbar.success(edinim ? "Edinim güncellendi." : "Edinim eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Edinim kaydedilemedi."));
      setBusy(false);
    }
  };

  const sil = async () => {
    if (edinim === null) return;
    const onay = await confirm({
      title: "Edinim partisi silinsin mi?",
      message:
        "Parti kayıttan kalkar. Nüshası ya da bağış ön kaydı olan parti silinemez; önce o kayıtlar düzeltilir.",
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await kutuphaneApi.deleteAcquisition(edinim.id);
      snackbar.success("Edinim silindi.");
      onSaved();
    } catch (e) {
      setHata(hataOku(e, "Edinim silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={edinim ? "Edinimi düzenle" : "Yeni edinim"}
      actions={
        <>
          {edinim && (
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
            label="Edinim yolu"
            required
            value={yol}
            onChange={(e) => setYol(e.target.value as AcquisitionMethod)}
            options={kodSecenekleri(ACQUISITION_METHOD_TR)}
            error={errors.method}
          />
          <TextField
            label="Edinim tarihi"
            required
            type="date"
            value={tarih}
            onChange={(e) => setTarih(e.target.value)}
            error={errors.date}
          />
          <TextField
            label="Kaynak notu"
            value={kaynakNotu}
            onChange={(e) => setKaynakNotu(e.target.value)}
            error={errors.source_note}
            helperText="Bağışçı, satıcı ya da parti açıklaması. Kişi adı şifreli saklanır."
          />
          <TextField
            label="Birim fiyat"
            inputMode="decimal"
            value={fiyat}
            onChange={(e) => setFiyat(e.target.value)}
            error={errors.unit_price}
            helperText="İsteğe bağlı; ondalık ayracı nokta ile yazılır (45.00)."
          />
          <Select
            className="sm:col-span-2"
            label="Komisyon kararı"
            placeholder="— yok —"
            value={karar}
            onChange={(e) => setKarar(e.target.value)}
            options={kararSecenekleri}
            error={errors.commission_decision}
            helperText={
              kesildi
                ? secimKesildiMetni("“Komisyon Kararları” sekmesini")
                : yol === "DONATION"
                  ? "Bağışta zorunludur ve bağış değerlendirme kararı olmalıdır."
                  : "İsteğe bağlı; bu yollarda kaynak seçimi kararı bağlanır."
            }
          />
        </div>

        <MetinAlani label="Notlar" value={notlar} onChange={setNotlar} error={errors.notes} />
      </div>
    </Dialog>
  );
}
