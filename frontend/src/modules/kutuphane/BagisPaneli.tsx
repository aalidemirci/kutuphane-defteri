// Bağış ön kayıtları (Md. 10/3) — gelen bağış kataloğa HEMEN girmez.
//
// Akış: okula bağış gelir → kitaplar ön kayda yazılır (nüsha AÇILMAZ) → Seçim ve
// Ayıklama Komisyonu kararı girilir → kabul edilen kalemler TEK İŞLEMDE
// kataloglanır, reddedilenler gerekçesiyle kayıtta kalır (okul bağışçıya ne
// olduğunu söyleyebilsin).
//
// Karar geri alınamaz: uygulama onay diyaloğundan geçer. Her kalem tam olarak bir
// kez kararlanmalıdır; eksik karar bütün işlemi reddeder (sunucu kuralı, burada
// tekrarlanmaz — form yalnız kullanıcıya kalan kalemi gösterir).

import { useCallback, useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
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
import { DONATION_STATUS_TR, KATALOG_SAYFA_BOYUTU, kutuphaneApi } from "./api";
import type {
  CommissionDecision,
  DonationIntake,
  DonationIntakeItem,
  DonationIntakeStatus,
} from "./api";
import {
  MetinAlani,
  SECICI_SINIRI,
  bolumSecenekleri,
  kararEtiketi,
  kodSecenekleri,
  secimKesildiMetni,
  secimKesildiMi,
  useBolumler,
} from "./ortak";

/** Ayrıntı penceresinin başlığı kipe göre değişir (sözlük §4: başlık = ekranın adı). */
const KIP_BASLIKLARI: Record<"liste" | "karar" | "iptal", string> = {
  liste: "Bağış ön kaydı",
  karar: "Komisyon kararını uygula",
  iptal: "Bağış ön kaydını iptal et",
};

export default function BagisPaneli() {
  const [durum, setDurum] = useState<DonationIntakeStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<DonationIntake>>(emptyPage<DonationIntake>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [yeni, setYeni] = useState(false);
  const [acik, setAcik] = useState<DonationIntake | null>(null);

  const tazele = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listDonationIntakes({ status: durum, limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Bağış ön kayıtları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [durum, offset, tazeleme]);

  const sutunlar: Column<DonationIntake>[] = [
    { header: "Bağışçı", cell: (b) => b.donor_name || "—" },
    { header: "Geliş tarihi", cell: (b) => formatDate(b.received_date) },
    { header: "Kalem", align: "right", cell: (b) => formatNumber(b.item_count) },
    { header: "Durum", cell: (b) => b.status_display },
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
              setDurum(e.target.value as DonationIntakeStatus | "");
              setOffset(0);
            }}
            options={kodSecenekleri(DONATION_STATUS_TR)}
          />
        </Card>
        <Button icon="add" onClick={() => setYeni(true)}>
          Bağış ön kaydı ekle
        </Button>
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={4} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="volunteer_activism"
          title="Gösterilecek bağış ön kaydı yok"
          description="Okula bağış geldiğinde kitapları önce buraya yazın; komisyon kararına kadar nüsha açılmaz."
        />
      ) : (
        <>
          <DataTable<DonationIntake>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(b) => setAcik(b)}
            rowLabel={(b) => `${formatDate(b.received_date)} tarihli bağış ön kaydını aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}

      {yeni && (
        <OnKayitFormu
          onClose={() => setYeni(false)}
          onSaved={(kayit) => {
            setYeni(false);
            tazele();
            setAcik(kayit);
          }}
        />
      )}

      {acik !== null && (
        <OnKayitAyrintisi
          kayit={acik}
          onClose={() => setAcik(null)}
          onChanged={(guncel) => {
            setAcik(guncel);
            tazele();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Yeni ön kayıt
// ---------------------------------------------------------------------------

function OnKayitFormu({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: (kayit: DonationIntake) => void;
}) {
  const [bagisci, setBagisci] = useState("");
  const [gelisTarihi, setGelisTarihi] = useState(todayIso());
  const [notlar, setNotlar] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    setBusy(true);
    try {
      const kayit = await kutuphaneApi.createDonationIntake({
        donor_name: bagisci.trim(),
        received_date: gelisTarihi,
        notes: notlar.trim(),
      });
      snackbar.success("Bağış ön kaydı açıldı.");
      onSaved(kayit);
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Bağış ön kaydı açılamadı."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Yeni bağış ön kaydı"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={kaydet} disabled={busy}>
            {busy ? "Açılıyor…" : "Aç"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-small text-on-surface-variant">
          Kitaplar bir sonraki adımda kalem kalem yazılır; liste günler içinde tamamlanabilir.
        </p>
        <TextField
          label="Bağışçı"
          value={bagisci}
          onChange={(e) => setBagisci(e.target.value)}
          error={errors.donor_name}
          helperText="İsteğe bağlı. Kişi adıdır, şifreli saklanır."
        />
        <TextField
          label="Geliş tarihi"
          required
          type="date"
          value={gelisTarihi}
          onChange={(e) => setGelisTarihi(e.target.value)}
          error={errors.received_date}
        />
        <MetinAlani label="Notlar" value={notlar} onChange={setNotlar} error={errors.notes} />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Ayrıntı: kalemler + komisyon kararı
// ---------------------------------------------------------------------------

function OnKayitAyrintisi({
  kayit,
  onClose,
  onChanged,
}: {
  kayit: DonationIntake;
  onClose: () => void;
  onChanged: (guncel: DonationIntake) => void;
}) {
  const [kip, setKip] = useState<"liste" | "karar" | "iptal">("liste");
  const [iptalGerekcesi, setIptalGerekcesi] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const bekliyor = kayit.status === "PENDING";

  // Kalem ekleme/çıkarma ön kaydın KENDİ kaydını değiştirir (kalemler gömülü
  // gelir); ayrıntı ucundan yeniden okunur, liste de tazelenir.
  const yenidenOku = useCallback(async () => {
    onChanged(await kutuphaneApi.getDonationIntake(kayit.id));
  }, [kayit.id, onChanged]);

  // Gerekçe iptal ANINDA yazılır: kapanan ön kaydın notları artık düzenlenemez
  // (sunucu yalnız karar bekleyen kaydı günceller) ve bağışçıya ne söyleneceğinin
  // tek kaydı budur.
  const iptalEt = async () => {
    const onay = await confirm({
      title: "Bağış ön kaydı iptal edilsin mi?",
      message:
        "Kayıt “İptal edildi” olarak kapanır ve kalemleri kataloglanmaz. Bağış geri verildiğinde ya da liste yanlış girildiğinde kullanılır.",
      confirmLabel: "İptal et",
      cancelLabel: "Vazgeç",
    });
    if (!onay) return;
    setBusy(true);
    try {
      const guncel = await kutuphaneApi.cancelDonationIntake(kayit.id, iptalGerekcesi.trim());
      snackbar.success("Bağış ön kaydı iptal edildi.");
      setKip("liste");
      setIptalGerekcesi("");
      onChanged(guncel);
    } catch (e) {
      setHata(hataOku(e, "Bağış ön kaydı iptal edilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={KIP_BASLIKLARI[kip]}
      actions={
        kip !== "liste" ? undefined : (
          <>
            {bekliyor && (
              <Button variant="text" icon="cancel" onClick={() => setKip("iptal")} disabled={busy}>
                İptal et
              </Button>
            )}
            {bekliyor && kayit.items.length > 0 && (
              <Button icon="gavel" onClick={() => setKip("karar")} disabled={busy}>
                Komisyon kararını uygula
              </Button>
            )}
            <Button variant="text" onClick={onClose} disabled={busy}>
              Kapat
            </Button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <dt className="text-label-medium text-on-surface-variant">Bağışçı</dt>
            <dd className="text-body-medium text-on-surface">{kayit.donor_name || "—"}</dd>
          </div>
          <div>
            <dt className="text-label-medium text-on-surface-variant">Geliş tarihi</dt>
            <dd className="text-body-medium text-on-surface">{formatDate(kayit.received_date)}</dd>
          </div>
          <div>
            <dt className="text-label-medium text-on-surface-variant">Durum</dt>
            <dd className="text-body-medium text-on-surface">{kayit.status_display}</dd>
          </div>
          <div>
            <dt className="text-label-medium text-on-surface-variant">Karar işlenme</dt>
            <dd className="text-body-medium text-on-surface">{formatDate(kayit.decided_at)}</dd>
          </div>
        </dl>

        {kip === "liste" && (
          <KalemListesi
            kayit={kayit}
            duzenlenebilir={bekliyor}
            onHata={setHata}
            onDegisti={yenidenOku}
          />
        )}

        {kip === "karar" && (
          <KararFormu
            kayit={kayit}
            onVazgec={() => setKip("liste")}
            onUygulandi={(guncel) => {
              setKip("liste");
              onChanged(guncel);
            }}
          />
        )}

        {kip === "iptal" && (
          <div className="space-y-4">
            <p className="text-body-medium text-on-surface-variant">
              Gerekçe ön kaydın notlarına yazılır; okul bağışçıya ne olduğunu buradan söyleyebilir.
            </p>
            <MetinAlani
              label="İptal gerekçesi"
              value={iptalGerekcesi}
              onChange={setIptalGerekcesi}
              placeholder="Bağış geri verildi, liste yanlış girildi…"
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="text" onClick={() => setKip("liste")} disabled={busy}>
                Vazgeç
              </Button>
              <Button icon="cancel" onClick={iptalEt} disabled={busy}>
                {busy ? "İptal ediliyor…" : "İptal et"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}

function KalemListesi({
  kayit,
  duzenlenebilir,
  onHata,
  onDegisti,
}: {
  kayit: DonationIntake;
  duzenlenebilir: boolean;
  onHata: (hata: SayfaHatasi | null) => void;
  onDegisti: () => Promise<void>;
}) {
  const [ad, setAd] = useState("");
  const [yazar, setYazar] = useState("");
  const [adet, setAdet] = useState("1");
  const [busy, setBusy] = useState(false);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();

  const kalemEkle = async () => {
    clearErrors();
    onHata(null);
    if (!ad.trim()) {
      setFieldError("title", "Kaynak adı yazılmalıdır.");
      return;
    }
    setBusy(true);
    try {
      await kutuphaneApi.addDonationItem(kayit.id, {
        title: ad.trim(),
        authors: yazar.trim(),
        copies: Number(adet) || 1,
      });
      setAd("");
      setYazar("");
      setAdet("1");
      snackbar.success("Kalem eklendi.");
      await onDegisti();
    } catch (e) {
      applyApiError(e);
      onHata(hataOku(e, "Kalem eklenemedi."));
    } finally {
      setBusy(false);
    }
  };

  const kalemSil = async (kalem: DonationIntakeItem) => {
    setBusy(true);
    onHata(null);
    try {
      await kutuphaneApi.removeDonationItem(kayit.id, kalem.id);
      snackbar.success("Kalem çıkarıldı.");
      await onDegisti();
    } catch (e) {
      onHata(hataOku(e, "Kalem çıkarılamadı."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-title-medium text-on-surface">Kalemler</p>

      {kayit.items.length === 0 ? (
        <EmptyState compact icon="list_alt" title="Henüz kalem yazılmadı." />
      ) : (
        <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/70">
          {kayit.items.map((kalem) => (
            <li key={kalem.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-body-medium text-on-surface">{kalem.title}</p>
                <p className="truncate text-body-small text-on-surface-variant">
                  {[kalem.authors, `${formatNumber(kalem.copies)} nüsha`, kalem.decision_display]
                    .filter(Boolean)
                    .join(" · ")}
                  {kalem.reject_reason ? ` · ${kalem.reject_reason}` : ""}
                </p>
              </div>
              {duzenlenebilir && (
                <Button
                  variant="text"
                  icon="close"
                  onClick={() => kalemSil(kalem)}
                  disabled={busy}
                  aria-label={`${kalem.title} kalemini çıkar`}
                >
                  Çıkar
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {duzenlenebilir && (
        <div className="grid items-end gap-3 sm:grid-cols-[minmax(12rem,1fr)_minmax(8rem,1fr)_6rem_auto]">
          <TextField
            label="Kaynak adı"
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            error={errors.title}
          />
          <TextField
            label="Yazar(lar)"
            value={yazar}
            onChange={(e) => setYazar(e.target.value)}
            error={errors.authors}
          />
          <TextField
            label="Nüsha"
            inputMode="numeric"
            value={adet}
            onChange={(e) => setAdet(e.target.value)}
            error={errors.copies}
          />
          <Button variant="tonal" icon="add" onClick={kalemEkle} disabled={busy}>
            Kalem ekle
          </Button>
        </div>
      )}
    </div>
  );
}

function KararFormu({
  kayit,
  onVazgec,
  onUygulandi,
}: {
  kayit: DonationIntake;
  onVazgec: () => void;
  onUygulandi: (guncel: DonationIntake) => void;
}) {
  const bolumler = useBolumler();
  const [kararlar, setKararlar] = useState<CommissionDecision[]>([]);
  const [karar, setKarar] = useState("");
  const [bolum, setBolum] = useState("");
  const [edinimTarihi, setEdinimTarihi] = useState("");
  const [fiyat, setFiyat] = useState("");
  const [kabuller, setKabuller] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(kayit.items.map((k) => [k.id, true])),
  );
  const [gerekceler, setGerekceler] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listCommissionDecisions({ decisionType: "DONATION_REVIEW", limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (!iptal) setKararlar(sayfa.results);
      })
      .catch(() => {
        if (!iptal) setKararlar([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const uygula = async () => {
    clearErrors();
    setHata(null);
    if (!karar) {
      setFieldError("commission_decision", "Komisyon kararı seçilmelidir.");
      return;
    }
    const kabulEdilen = kayit.items.filter((k) => kabuller[k.id]).map((k) => k.id);
    const reddedilen: Record<string, string> = {};
    for (const kalem of kayit.items) {
      if (kabuller[kalem.id]) continue;
      const gerekce = (gerekceler[kalem.id] ?? "").trim();
      if (!gerekce) {
        setFieldError("rejected", "Reddedilen her kalemin gerekçesi yazılmalıdır.");
        return;
      }
      reddedilen[String(kalem.id)] = gerekce;
    }
    const onay = await confirm({
      title: "Komisyon kararı uygulansın mı?",
      message: `${formatNumber(kabulEdilen.length)} kalem kataloglanır ve nüshaları açılır, ${formatNumber(
        Object.keys(reddedilen).length,
      )} kalem gerekçesiyle reddedilmiş olarak kayıtta kalır. İşlem geri alınamaz.`,
      confirmLabel: "Uygula",
    });
    if (!onay) return;
    setBusy(true);
    try {
      const sonuc = await kutuphaneApi.applyDonationDecision(kayit.id, {
        commission_decision: Number(karar),
        accepted_ids: kabulEdilen,
        rejected: reddedilen,
        acquisition_date: edinimTarihi || null,
        section: bolum ? Number(bolum) : null,
        unit_price: fiyat.trim() ? fiyat.trim() : null,
      });
      snackbar.success(
        `Karar işlendi: ${formatNumber(sonuc.work_count)} eser, ${formatNumber(sonuc.copy_count)} nüsha kataloglandı.`,
      );
      onUygulandi(sonuc.intake);
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Komisyon kararı uygulanamadı."));
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {hata && <ErrorBand hata={hata} />}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          className="sm:col-span-2"
          label="Komisyon kararı"
          required
          placeholder="Seçin"
          value={karar}
          onChange={(e) => setKarar(e.target.value)}
          options={kararlar.map((k) => ({ value: String(k.id), label: kararEtiketi(k) }))}
          error={errors.commission_decision}
          helperText={
            kararlar.length === 0
              ? "Önce Komisyon Kararları sekmesinden bir bağış değerlendirme kararı ekleyin."
              : secimKesildiMi(kararlar.length)
                ? secimKesildiMetni("“Komisyon Kararları” sekmesini")
                : "Yalnız bağış değerlendirme kararları listelenir."
          }
        />
        <TextField
          label="Edinim tarihi"
          type="date"
          value={edinimTarihi}
          onChange={(e) => setEdinimTarihi(e.target.value)}
          error={errors.acquisition_date}
          helperText="Boş bırakılırsa bağışın geliş tarihi kullanılır."
        />
        <Select
          label="Bölüm"
          placeholder="— yok —"
          value={bolum}
          onChange={(e) => setBolum(e.target.value)}
          options={bolumSecenekleri(bolumler)}
          error={errors.section}
        />
        <TextField
          label="Birim fiyat"
          inputMode="decimal"
          value={fiyat}
          onChange={(e) => setFiyat(e.target.value)}
          error={errors.unit_price}
          helperText="İsteğe bağlı; ondalık ayracı nokta ile yazılır."
        />
      </div>

      <div className="space-y-2">
        <p className="text-title-medium text-on-surface">Kalem kararları</p>
        {errors.rejected && (
          <p role="alert" className="text-body-small text-error">
            {errors.rejected}
          </p>
        )}
        <ul className="space-y-2">
          {kayit.items.map((kalem) => (
            <li
              key={kalem.id}
              className="rounded-shape-md border border-outline-variant/70 px-3 py-2"
            >
              <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
                <input
                  type="checkbox"
                  checked={kabuller[kalem.id] ?? false}
                  onChange={(e) =>
                    setKabuller((onceki) => ({ ...onceki, [kalem.id]: e.target.checked }))
                  }
                  className="size-5 shrink-0 accent-primary"
                />
                <span className="min-w-0 flex-1 truncate">
                  {kalem.title}
                  {kalem.authors ? ` · ${kalem.authors}` : ""}
                </span>
              </label>
              {!kabuller[kalem.id] && (
                <TextField
                  label="Ret gerekçesi"
                  value={gerekceler[kalem.id] ?? ""}
                  onChange={(e) =>
                    setGerekceler((onceki) => ({ ...onceki, [kalem.id]: e.target.value }))
                  }
                />
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="text" onClick={onVazgec} disabled={busy}>
          Vazgeç
        </Button>
        <Button icon="check" onClick={uygula} disabled={busy}>
          {busy ? "Uygulanıyor…" : "Kararı uygula"}
        </Button>
      </div>
    </div>
  );
}
