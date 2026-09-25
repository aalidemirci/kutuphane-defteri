// Nadir Eserler (F8; Yönetmelik Md. 12/2, D14). Katalog'un ve Ayıklama'nın sağ üstündeki
// bağlantıyla açılır; YALNIZ yönetici kipinde.
//
// Md. 12/2: Seçim ve Ayıklama Komisyonunca tespit edilen el yazmaları ve nadir eserler
// listesi Genel Müdürlüğe (Destek Hizmetleri Genel Müdürlüğü — Md. 4/1-c) gönderilir.
// Nüshanın nadir eser olduğu Eser Ayrıntısı → nüsha penceresindeki "El yazması / nadir
// eser" kutusudur; nadir eser AYIKLANMAZ. Liste bir komisyon kararına ("Ayıklama" türü)
// bağlanır; gönderilmiş liste değişmez. Gönderilmiş ya da kararı bağlanmış listedeki
// nüshanın işareti kaldırılamaz ve listedeki nüsha silinemez (kural sunucuda). Gönderim
// geri alınamadığı için onay diyaloğundan geçer.
//
// İki sekme: "Listeler" (El yazması ve nadir eserler listeleri) ve "Nadir Eser İşaretli
// Nüshalar" (hangisinin bildirildiği).

import { useCallback, useEffect, useState } from "react";

import { useTabParam } from "../../hooks/useTabParam";
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
import ModuleHeader from "../../ui/ModuleHeader";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { KATALOG_SAYFA_BOYUTU } from "../kutuphane/api";
import { kararEtiketi } from "../kutuphane/ortak";
import { YanEkranBaglantilari } from "../yil/ortak";
import { AYIKLAMA_ADRESI, NADIR_ESER_BELGESI, NADIR_ESERLER_BASLIGI, ayiklamaApi } from "./api";
import type { NadirListe, NadirListeAyrintisi, NadirNusha } from "./api";
import {
  BelgeSatiri,
  Bilgi,
  KOMISYON_KARARLARI_ADRESI,
  OnayKutusu,
  Rozet,
  useAyiklamaKararlari,
} from "./ortak";

// TAB_KEYS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TAB_KEYS = ["listeler", "nushalar"] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TABS: TabItem[] = [
  { key: "listeler", label: "Listeler", icon: "list_alt" },
  { key: "nushalar", label: "Nadir Eser İşaretli Nüshalar", icon: "history_edu" },
];

export default function NadirEserlerPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TAB_KEYS, "listeler");

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader
        backTo="/katalog"
        moduleLabel="Katalog"
        title={NADIR_ESERLER_BASLIGI}
        actions={
          <YanEkranBaglantilari
            baglantilar={[
              { to: AYIKLAMA_ADRESI, label: "Ayıklama", icon: "inventory" },
              { to: KOMISYON_KARARLARI_ADRESI, label: "Komisyon Kararları", icon: "gavel" },
            ]}
          />
        }
      />

      <p className="kd-page-description max-w-4xl">
        Seçim ve Ayıklama Komisyonunca tespit edilen el yazmaları ve nadir eserlerin listesi Genel
        Müdürlüğe gönderilir (Yönetmelik Md. 12/2). El yazması ve nadir eser ayıklanmaz. Nüshayı
        işaretlemek için Eser Ayrıntısı&apos;nda nüshanın penceresindeki “El yazması / nadir eser”
        kutusunu kullanın.
      </p>

      <Tabs
        items={TABS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Nadir eser bölümleri"
        idBase="nadir"
      />

      <div {...tabPanelProps("nadir", tab)}>
        {tab === "listeler" && <ListelerSekmesi />}
        {tab === "nushalar" && <NushalarSekmesi />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Listeler
// ---------------------------------------------------------------------------

function ListelerSekmesi() {
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<NadirListe>>(emptyPage<NadirListe>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [acik, setAcik] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    ayiklamaApi
      .listeler({ limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Listeler yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [offset, tazeleme]);

  const yeniListe = async () => {
    setBusy(true);
    setHata(null);
    try {
      const liste = await ayiklamaApi.listeAc();
      snackbar.success("Liste açıldı.");
      setTazeleme((k) => k + 1);
      setAcik(liste.id);
    } catch (e) {
      setHata(hataOku(e, "Liste açılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const sutunlar: Column<NadirListe>[] = [
    { header: "Ders yılı", cell: (l) => l.school_year_name },
    {
      header: "Durum",
      cell: (l) => <Rozet ton={l.status === "SENT" ? "ikincil" : "notr"}>{l.status_display}</Rozet>,
    },
    { header: "Eser", align: "right", cell: (l) => formatNumber(l.item_count) },
    {
      header: "Komisyon kararı",
      cell: (l) =>
        l.decision
          ? `${formatDate(l.decision.decision_date)}${
              l.decision.decision_no ? ` · ${l.decision.decision_no}` : ""
            }`
          : "—",
    },
    { header: "Gönderim", cell: (l) => formatDate(l.sent_on) },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex justify-end">
        <Button icon="add" onClick={() => void yeniListe()} disabled={busy}>
          {busy ? "Açılıyor…" : "Yeni liste"}
        </Button>
      </div>
      {hata && <ErrorBand hata={hata} />}
      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="history_edu"
          title="Gösterilecek liste yok"
          description="Komisyonun tespit ettiği el yazması ve nadir eserler için “Yeni liste” ile bir liste açın."
        />
      ) : (
        <>
          <DataTable<NadirListe>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(l) => setAcik(l.id)}
            rowLabel={(l) => `${l.school_year_name} ders yılının listesini aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}
      {acik !== null && (
        <ListeAyrintisi
          id={acik}
          onClose={() => setAcik(null)}
          onDegisti={() => setTazeleme((k) => k + 1)}
          onSilindi={() => {
            setAcik(null);
            setTazeleme((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}

function ListeAyrintisi({
  id,
  onClose,
  onDegisti,
  onSilindi,
}: {
  id: number;
  onClose: () => void;
  onDegisti: () => void;
  onSilindi: () => void;
}) {
  const kararlar = useAyiklamaKararlari();
  const [liste, setListe] = useState<NadirListeAyrintisi | null>(null);
  const [adaylar, setAdaylar] = useState<NadirNusha[]>([]);
  const [secili, setSecili] = useState<Set<number>>(new Set());
  const [karar, setKarar] = useState("");
  const [gonderim, setGonderim] = useState(todayIso());
  const [yazi, setYazi] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const yukle = useCallback(async () => {
    const [l, a] = await Promise.all([
      ayiklamaApi.liste(id),
      ayiklamaApi.nadirNushalar({ unsent: true, limit: 200 }),
    ]);
    setListe(l);
    setKarar(l.commission_decision ? String(l.commission_decision) : "");
    const listede = new Set(l.items.map((s) => s.copy));
    setAdaylar(a.results.filter((n) => !listede.has(n.id)));
    setSecili(new Set());
  }, [id]);

  useEffect(() => {
    yukle().catch((e: unknown) => setHata(hataOku(e, "Liste yüklenemedi.")));
  }, [yukle]);

  const calistir = async (is: () => Promise<unknown>, ileti: string, yedek: string) => {
    setBusy(true);
    setHata(null);
    try {
      await is();
      snackbar.success(ileti);
      await yukle();
      onDegisti();
    } catch (e) {
      setHata(hataOku(e, yedek));
    } finally {
      setBusy(false);
    }
  };

  const gonder = async () => {
    if (liste === null) return;
    const onay = await confirm({
      title: "Liste gönderildi olarak işaretlensin mi?",
      message:
        "Gönderilmiş liste değiştirilemez ve içindeki nüshaların nadir eser işareti kaldırılamaz. İşaret geri alınmaz.",
      confirmLabel: "Gönderildi olarak işaretle",
    });
    if (onay) {
      await calistir(
        () =>
          ayiklamaApi.gonderildi(liste.id, { sent_on: gonderim, sent_document_no: yazi.trim() }),
        "Liste Genel Müdürlüğe gönderildi olarak işaretlendi.",
        "Gönderim işlenemedi.",
      );
    }
  };

  const sil = async () => {
    if (liste === null) return;
    const onay = await confirm({
      title: "Liste silinsin mi?",
      message: "Hazırlanan liste kaldırılır; nüshaların nadir eser işareti kalır.",
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await ayiklamaApi.listeSil(liste.id);
      snackbar.success("Liste silindi.");
      onSilindi();
    } catch (e) {
      setHata(hataOku(e, "Liste silinemedi."));
      setBusy(false);
    }
  };

  const hazirlaniyor = liste?.status === "DRAFT";

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={NADIR_ESER_BELGESI}
      actions={
        <>
          {hazirlaniyor && (
            <Button variant="text" icon="delete" onClick={() => void sil()} disabled={busy}>
              Listeyi sil
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Kapat
          </Button>
        </>
      }
    >
      {liste === null ? (
        hata ? (
          <ErrorBand hata={hata} />
        ) : (
          <SkeletonList rows={3} />
        )
      ) : (
        <div className="space-y-4">
          {hata && <ErrorBand hata={hata} />}
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Bilgi etiket="Ders yılı">{liste.school_year_name}</Bilgi>
            <Bilgi etiket="Durum">{liste.status_display}</Bilgi>
            <Bilgi etiket="Genel Müdürlüğe gönderim">
              {liste.sent_on
                ? `${formatDate(liste.sent_on)}${
                    liste.sent_document_no ? ` · ${liste.sent_document_no}` : ""
                  }`
                : "—"}
            </Bilgi>
          </dl>

          <div className="flex flex-wrap items-end gap-3">
            <Select
              className="min-w-72 flex-1"
              label="Komisyon kararı"
              placeholder="— yok —"
              value={karar}
              disabled={!hazirlaniyor}
              onChange={(e) => setKarar(e.target.value)}
              options={(kararlar ?? []).map((k) => ({
                value: String(k.id),
                label: kararEtiketi(k),
              }))}
              helperText={
                kararlar !== null && kararlar.length === 0
                  ? "Önce Edinimler ve Bağışlar → Komisyon Kararları sekmesinden bir “Ayıklama” kararı ekleyin."
                  : "Liste Seçim ve Ayıklama Komisyonunun “Ayıklama” türündeki kararına bağlanır. Karar bağlanınca listedeki nüshaların nadir eser işareti kaldırılamaz."
              }
            />
            {hazirlaniyor && (
              <Button
                variant="tonal"
                icon="check"
                disabled={busy}
                onClick={() =>
                  void calistir(
                    () =>
                      ayiklamaApi.listeGuncelle(liste.id, {
                        commission_decision: karar ? Number(karar) : null,
                      }),
                    "Komisyon kararı kaydedildi.",
                    "Komisyon kararı kaydedilemedi.",
                  )
                }
              >
                Kararı kaydet
              </Button>
            )}
          </div>

          <section aria-labelledby="liste-eserleri" className="space-y-2">
            <h3 id="liste-eserleri" className="text-title-small font-semibold text-on-surface">
              Listedeki Eserler
            </h3>
            {liste.items.length === 0 ? (
              <EmptyState compact icon="list_alt" title="Listede eser yok." />
            ) : (
              <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/70">
                {liste.items.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-body-medium text-on-surface">
                        <span className="font-mono">{s.barcode_display}</span> — {s.work_title}
                      </p>
                      <p className="text-body-small text-on-surface-variant">
                        {[s.work_authors, s.publisher, s.publish_year, s.copy_status_display]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {hazirlaniyor && (
                      <Button
                        variant="text"
                        icon="close"
                        disabled={busy}
                        aria-label={`${s.work_title} eserini listeden çıkar`}
                        onClick={() =>
                          void calistir(
                            () => ayiklamaApi.listedenCikar(liste.id, s.id),
                            "Eser listeden çıkarıldı.",
                            "Eser çıkarılamadı.",
                          )
                        }
                      >
                        Çıkar
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {hazirlaniyor && (
            <section aria-labelledby="liste-adaylari" className="space-y-2">
              <h3 id="liste-adaylari" className="text-title-small font-semibold text-on-surface">
                Bildirilmemiş Nadir Eserler
              </h3>
              {adaylar.length === 0 ? (
                <p className="text-body-small text-on-surface-variant">
                  Listeye eklenecek, bildirilmemiş nadir eser işaretli nüsha yok.
                </p>
              ) : (
                <>
                  <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/70">
                    {adaylar.map((n) => (
                      <li key={n.id} className="px-3">
                        <OnayKutusu
                          checked={secili.has(n.id)}
                          onChange={(d) =>
                            setSecili((o) => {
                              const yeni = new Set(o);
                              if (d) yeni.add(n.id);
                              else yeni.delete(n.id);
                              return yeni;
                            })
                          }
                          etiket={`${n.barcode_display} — ${n.work_title}`}
                        />
                      </li>
                    ))}
                  </ul>
                  <Button
                    variant="tonal"
                    icon="add"
                    disabled={busy || secili.size === 0}
                    onClick={() =>
                      void calistir(
                        () => ayiklamaApi.listeyeEkle(liste.id, { copies: Array.from(secili) }),
                        "Eserler listeye eklendi.",
                        "Eserler eklenemedi.",
                      )
                    }
                  >
                    {`Seçilenleri listeye ekle (${formatNumber(secili.size)})`}
                  </Button>
                </>
              )}
            </section>
          )}

          {hazirlaniyor && (
            <section
              aria-labelledby="liste-gonderim"
              className="space-y-2 rounded-shape-md bg-surface-container px-3 py-3"
            >
              <h3 id="liste-gonderim" className="text-title-small font-semibold text-on-surface">
                Genel Müdürlüğe Gönderim
              </h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <TextField
                  label="Gönderim tarihi"
                  type="date"
                  value={gonderim}
                  onChange={(e) => setGonderim(e.target.value)}
                  helperText="Komisyon kararının tarihinden önce ve bugünden sonra olamaz."
                />
                <TextField
                  label="Gönderme yazısının sayısı (isteğe bağlı)"
                  value={yazi}
                  onChange={(e) => setYazi(e.target.value)}
                />
              </div>
              <Button
                icon="send"
                disabled={busy || liste.items.length === 0}
                onClick={() => void gonder()}
              >
                Gönderildi olarak işaretle
              </Button>
            </section>
          )}

          <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/70">
            <BelgeSatiri
              ad={NADIR_ESER_BELGESI}
              basilabilir={liste.items.length > 0}
              gerekce="Listede eser yok."
              pdfAl={() => ayiklamaApi.listePdf(liste.id)}
              aciklama="Komisyon imzasına ve Genel Müdürlüğe gönderime hazır liste."
            />
          </ul>
        </div>
      )}
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Nadir eser işaretli nüshalar
// ---------------------------------------------------------------------------

function NushalarSekmesi() {
  const [yalnizBildirilmemis, setYalnizBildirilmemis] = useState(false);
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<NadirNusha>>(emptyPage<NadirNusha>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    ayiklamaApi
      .nadirNushalar({ unsent: yalnizBildirilmemis, limit: KATALOG_SAYFA_BOYUTU, offset })
      .then((s) => {
        if (iptal) return;
        setSayfa(s);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Nüshalar yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [yalnizBildirilmemis, offset]);

  const sutunlar: Column<NadirNusha>[] = [
    { header: "Barkod", cell: (n) => <span className="font-mono">{n.barcode_display}</span> },
    { header: "Kaynak adı", cell: (n) => n.work_title },
    { header: "Yazar", cell: (n) => n.work_authors || "—" },
    { header: "Nüsha durumu", cell: (n) => n.status_display },
    {
      header: "Genel Müdürlük",
      cell: (n) =>
        n.sent ? (
          <Rozet ton="ikincil" icon="send">
            Bildirildi
          </Rozet>
        ) : (
          <Rozet ton="notr">Bildirilmedi</Rozet>
        ),
    },
  ];

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <Card elevation={0} className="p-[var(--kd-panel-padding)] shadow-elevation-1">
        <OnayKutusu
          etiket="Yalnız bildirilmemişler"
          checked={yalnizBildirilmemis}
          onChange={(d) => {
            setYalnizBildirilmemis(d);
            setOffset(0);
          }}
        />
      </Card>
      {hata && <ErrorBand hata={hata} />}
      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="history_edu"
          title="Nadir eser işaretli nüsha yok"
          description="Nüshayı Eser Ayrıntısı'nda “El yazması / nadir eser” kutusuyla işaretleyin."
        />
      ) : (
        <>
          <DataTable<NadirNusha> columns={sutunlar} rows={sayfa.results} />
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
