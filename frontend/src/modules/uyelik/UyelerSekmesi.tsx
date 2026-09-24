// Kişiler → Üyeler (F6; tasarım §9-1/2, §4.4, D12). Kütüphane üyelerinin listesi:
// durum (Aktif / Sonlandı), kart no, kart basımı, kişi bazında açık ve gecikmiş
// ödünç sayısı. Satıra tıklanınca **Üyelik** penceresi: "Kartı yenile" (onaylı;
// eski kart iptal edilir), "Üyeliği sonlandır" (neden kapalı listeden ve zorunlu),
// yanlış açılmış üyeliği silme, iade hatırlatma pusulası ve üyenin ödünç kaydı.
//
// Üyelik isteğe bağlıdır (Md. 17/1): öğrencide şube bazlı "Üyelik İstek Listesi"
// sekmesinden, personelde buradaki "Personele üyelik aç" ile tek tek açılır.
// Altta **Üyelik Belgeleri**: kütüphane aydınlatma metni (e-Okul aktarımından önce
// duyurulur) ve masa kartı.
//
// Profil yasağı (tasarım §3): ödünç kaydı yalnız satırlardır; konu ya da sınıf
// dağılımı gösterilmez. Sözlük: "ödünç kaydı", asla "okuduğu kitaplar".

import { useCallback, useEffect, useState } from "react";

import { useDebounced } from "../../hooks/useDebounced";
import { ApiError } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
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
import Icon from "../../ui/Icon";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { MEMBER_KIND_TR, okulApi } from "../okul/api";
import type { Personnel } from "../okul/api";
import {
  AYDINLATMA_ADI,
  MANUAL_TERMINATION_TR,
  MASA_KARTI_ADI,
  MEMBERSHIP_STATUS_TR,
  PUSULA_ADI,
  uyelikApi,
} from "./api";
import type {
  ManualTerminationReason,
  MemberLoan,
  MemberType,
  Membership,
  MembershipStatus,
} from "./api";
import { kisiEtiketi, subeOku, UYE_TURU_SECENEKLERI, useSubeSecenekleri } from "./ortak";

const PAGE_SIZE = 25;

const DURUM_SECENEKLERI = (
  Object.entries(MEMBERSHIP_STATUS_TR) as Array<[MembershipStatus, string]>
).map(([value, label]) => ({ value, label }));

/** Üyelik durumu rozeti: "Aktif" ya da "Sonlandı · gg.aa.yyyy". */
export function UyelikDurumu({ uyelik }: { uyelik: Membership }) {
  const aktif = uyelik.status === "ACTIVE";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-label-medium ${
        aktif
          ? "bg-secondary-container text-on-secondary-container"
          : "bg-surface-container-highest text-on-surface-variant"
      }`}
    >
      <Icon name={aktif ? "badge" : "block"} size="sm" />
      {aktif ? "Aktif" : `Sonlandı · ${formatDate(uyelik.terminated_at)}`}
    </span>
  );
}

function KartDurumu({ uyelik }: { uyelik: Membership }) {
  if (uyelik.status !== "ACTIVE") return <>—</>;
  return uyelik.card_printed_at ? (
    <>Basıldı · {formatDate(uyelik.card_printed_at.slice(0, 10))}</>
  ) : (
    <span className="text-tertiary">Kart basımı bekliyor</span>
  );
}

export default function UyelerSekmesi() {
  const [aramaGirdisi, setAramaGirdisi] = useState("");
  const arama = useDebounced(aramaGirdisi);
  const [durum, setDurum] = useState<MembershipStatus | "">("ACTIVE");
  const [tur, setTur] = useState<MemberType | "">("");
  const [sube, setSube] = useState("");
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Membership>>(emptyPage<Membership>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [secili, setSecili] = useState<Membership | null>(null);
  const [personelFormu, setPersonelFormu] = useState(false);
  const subeler = useSubeSecenekleri();

  const yenile = useCallback(() => setTazeleme((k) => k + 1), []);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    const secim = subeOku(sube);
    uyelikApi
      .uyelikler({
        status: durum,
        memberType: tur,
        classLevel: secim.classLevel,
        classSection: secim.classSection,
        search: arama.trim(),
        limit: PAGE_SIZE,
        offset,
      })
      .then((sonuc) => {
        if (iptal) return;
        const geri = geriDusulecekOffset(sonuc, offset, PAGE_SIZE);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setSayfa(sonuc);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Üye listesi yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [arama, durum, tur, sube, offset, tazeleme]);

  const sutunlar: Column<Membership>[] = [
    { header: "Ad soyad", cell: (u) => u.full_name },
    { header: "Sınıf / üye türü", cell: (u) => kisiEtiketi(u) },
    { header: "Kart no", cell: (u) => <span className="tabular-nums">{u.card_no}</span> },
    { header: "Durum", cell: (u) => <UyelikDurumu uyelik={u} /> },
    {
      header: "Açık ödünç",
      align: "right",
      cell: (u) => (
        <span className="tabular-nums">
          {formatNumber(u.open_loan_count)} / {formatNumber(u.loan_limit)}
          {u.overdue_loan_count > 0 && (
            <span className="ml-2 rounded-full bg-error-container px-2 py-0.5 text-label-small text-on-error-container">
              {formatNumber(u.overdue_loan_count)} gecikmiş
            </span>
          )}
        </span>
      ),
    },
    { header: "Üye kartı", cell: (u) => <KartDurumu uyelik={u} /> },
  ];

  const filtre = (fn: () => void) => {
    fn();
    setOffset(0);
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Kütüphane Üyeleri</p>
          {!yukleniyor && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(sayfa.count)} üyelik
            </p>
          )}
        </div>
        <Button icon="person_add" onClick={() => setPersonelFormu(true)}>
          Personele üyelik aç
        </Button>
      </div>
      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        Üyelik isteğe bağlıdır. Öğrencilere “Üyelik İstek Listesi” sekmesinden şube şube, öğretmen
        ve diğer personele buradan tek tek üyelik açılır. Yeni üyenin kartı “Kart Basımı” sekmesinde
        basılmayı bekler.
      </p>

      <Card
        elevation={0}
        className="grid items-end gap-3 p-[var(--kd-panel-padding)] shadow-elevation-1 sm:grid-cols-[minmax(15rem,1fr)_10rem_11rem_9rem]"
      >
        <TextField
          label="Ara"
          value={aramaGirdisi}
          onChange={(e) => filtre(() => setAramaGirdisi(e.target.value))}
          placeholder="Ad soyad, okul no ya da kart no…"
          helperText="Okul no ve kart no tam yazılarak aranır."
        />
        <Select
          label="Durum"
          placeholder="Tümü"
          value={durum}
          onChange={(e) => filtre(() => setDurum(e.target.value as MembershipStatus | ""))}
          options={DURUM_SECENEKLERI}
        />
        <Select
          label="Üye türü"
          placeholder="Tümü"
          value={tur}
          onChange={(e) => filtre(() => setTur(e.target.value as MemberType | ""))}
          options={UYE_TURU_SECENEKLERI}
        />
        <Select
          label="Şube"
          placeholder="Tümü"
          value={sube}
          onChange={(e) => filtre(() => setSube(e.target.value))}
          options={subeler}
        />
      </Card>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={5} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          icon="badge"
          title="Gösterilecek üye yok"
          description="Süzgeçleri değiştirin ya da “Üyelik İstek Listesi” sekmesinden öğrencilere üyelik açın."
        />
      ) : (
        <>
          <DataTable<Membership>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={setSecili}
            rowLabel={(u) => `${u.full_name} üyeliğini aç`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={PAGE_SIZE}
            onOffset={setOffset}
          />
        </>
      )}

      <UyelikBelgeleri />

      {secili !== null && (
        <UyelikPenceresi
          uyelik={secili}
          onKapat={() => setSecili(null)}
          onDegisti={(yeni) => {
            if (yeni === null) setSecili(null);
            else setSecili(yeni);
            yenile();
          }}
        />
      )}
      {personelFormu && (
        <PersoneleUyelikPenceresi
          onKapat={() => setPersonelFormu(false)}
          onAcildi={() => {
            setPersonelFormu(false);
            yenile();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Üyelik penceresi
// ---------------------------------------------------------------------------

function Bilgi({ etiket, deger }: { etiket: string; deger: string }) {
  return (
    <div>
      <dt className="text-label-medium text-on-surface-variant">{etiket}</dt>
      <dd className="text-body-medium text-on-surface">{deger}</dd>
    </div>
  );
}

export function UyelikPenceresi({
  uyelik,
  onKapat,
  onDegisti,
}: {
  uyelik: Membership;
  onKapat: () => void;
  /** İşlem sonrası güncel üyelik (silindiyse null). */
  onDegisti: (yeni: Membership | null) => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [sonlandirma, setSonlandirma] = useState(false);
  const aktif = uyelik.status === "ACTIVE";

  const kartiYenile = async () => {
    const tamam = await confirm({
      title: "Kart yenilensin mi?",
      message:
        "Üyeye yeni kart numarası verilir. Eski kart iptal edilir: masada okutulunca “İptal edilmiş kart — kütüphane yöneticisine yönlendirin.” iletisi çıkar. Açık ödünçler üyelikte kalır; yeni kart “Kart Basımı” sekmesinde basılmayı bekler.",
      confirmLabel: "Kartı yenile",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      const yeni = await uyelikApi.kartiYenile(uyelik.id);
      snackbar.success("Kart yenilendi. Yeni kart basım kuyruğunda.");
      onDegisti(yeni);
    } catch (e) {
      setHata(hataOku(e, "Kart yenilenemedi."));
    } finally {
      setMesgul(false);
    }
  };

  const sil = async () => {
    const tamam = await confirm({
      title: "Üyelik silinsin mi?",
      message:
        "Yalnız yanlışlıkla açılmış ve hiç ödünç kaydı olmayan üyelik silinir. Kartı iptal edilir; numarası bir daha kimseye verilmez. Ödünç kaydı olan üyelik silinmez, “Yanlış kayıt” nedeniyle sonlandırılır.",
      confirmLabel: "Sil",
    });
    if (!tamam) return;
    setMesgul(true);
    setHata(null);
    try {
      await uyelikApi.uyelikSil(uyelik.id);
      snackbar.success("Üyelik silindi.");
      onDegisti(null);
    } catch (e) {
      setHata(hataOku(e, "Üyelik silinemedi."));
    } finally {
      setMesgul(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onKapat}
      title="Üyelik"
      wide
      actions={
        <Button variant="text" onClick={onKapat}>
          Kapat
        </Button>
      }
    >
      <div className="space-y-4">
        <dl className="grid gap-3 sm:grid-cols-3">
          <Bilgi etiket="Ad soyad" deger={uyelik.full_name} />
          <Bilgi etiket="Sınıf / üye türü" deger={kisiEtiketi(uyelik)} />
          <Bilgi etiket="Kart no" deger={uyelik.card_no} />
          <Bilgi
            etiket="Durum"
            deger={
              aktif
                ? "Aktif"
                : `Sonlandı · ${formatDate(uyelik.terminated_at)} · ${uyelik.termination_reason_display}`
            }
          />
          <Bilgi etiket="Üyelik başlangıcı" deger={formatDate(uyelik.started_at)} />
          <Bilgi
            etiket="Üye kartı"
            deger={
              !aktif
                ? "—"
                : uyelik.card_printed_at
                  ? `Basıldı · ${formatDate(uyelik.card_printed_at.slice(0, 10))}`
                  : "Kart basımı bekliyor"
            }
          />
          <Bilgi
            etiket="Açık ödünç / sınır"
            deger={`${formatNumber(uyelik.open_loan_count)} / ${formatNumber(uyelik.loan_limit)}`}
          />
          <Bilgi etiket="Kalan ödünç hakkı" deger={formatNumber(uyelik.remaining_quota)} />
          <Bilgi etiket="Gecikmiş ödünç" deger={formatNumber(uyelik.overdue_loan_count)} />
        </dl>

        {hata && <ErrorBand hata={hata} />}

        <div className="flex flex-wrap gap-2">
          {aktif && (
            <>
              <Button
                variant="tonal"
                icon="autorenew"
                onClick={() => void kartiYenile()}
                disabled={mesgul}
              >
                Kartı yenile
              </Button>
              <Button
                variant="outlined"
                icon="person_off"
                onClick={() => setSonlandirma(true)}
                disabled={mesgul}
              >
                Üyeliği sonlandır
              </Button>
            </>
          )}
          <Button variant="text" icon="delete" onClick={() => void sil()} disabled={mesgul}>
            Üyeliği sil
          </Button>
        </div>

        {uyelik.overdue_loan_count > 0 && (
          <Card elevation={0} className="space-y-2 p-4 shadow-elevation-1">
            <p className="text-title-small text-on-surface">İade Hatırlatma Pusulası</p>
            <p className="text-body-small text-on-surface-variant">
              Pusula kişiye özeldir ve katlanınca içeriği görünmez. Kütüphane yöneticisi ya da sınıf
              rehber öğretmeni eliyle verilir; sınıfta okunmaz, öğrenci görevliye dağıttırılmaz.
            </p>
            <div className="flex flex-wrap gap-2">
              <PdfDugmeleri
                pdfAl={() => uyelikApi.pusulaPdf({ membershipIds: [uyelik.id] })}
                dosyaAdi={() => dosyaAdi([PUSULA_ADI, formatDate(todayIso())], "pdf")}
                onizlemeBasligi={PUSULA_ADI}
                onHata={setHata}
              />
            </div>
          </Card>
        )}

        <OduncKaydi uyelikId={uyelik.id} />
      </div>

      {sonlandirma && (
        <SonlandirmaPenceresi
          uyelik={uyelik}
          onKapat={() => setSonlandirma(false)}
          onSonlandi={(yeni) => {
            setSonlandirma(false);
            snackbar.success("Üyelik sonlandırıldı.");
            onDegisti(yeni);
          }}
        />
      )}
    </Dialog>
  );
}

function SonlandirmaPenceresi({
  uyelik,
  onKapat,
  onSonlandi,
}: {
  uyelik: Membership;
  onKapat: () => void;
  onSonlandi: (yeni: Membership) => void;
}) {
  const [neden, setNeden] = useState<ManualTerminationReason | "">("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [alanHatasi, setAlanHatasi] = useState<string | undefined>();
  const [mesgul, setMesgul] = useState(false);

  const gonder = async () => {
    if (!neden) {
      setAlanHatasi("Sonlandırma nedeni zorunludur.");
      return;
    }
    setMesgul(true);
    setHata(null);
    try {
      onSonlandi(await uyelikApi.sonlandir(uyelik.id, neden));
    } catch (e) {
      if (e instanceof ApiError && typeof e.fields.reason === "string") {
        setAlanHatasi(e.fields.reason);
      }
      setHata(hataOku(e, "Üyelik sonlandırılamadı."));
    } finally {
      setMesgul(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onKapat}
      title="Üyeliği sonlandır"
      actions={
        <>
          <Button variant="text" onClick={onKapat}>
            Vazgeç
          </Button>
          <Button onClick={() => void gonder()} disabled={mesgul}>
            Üyeliği sonlandır
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-body-medium text-on-surface">
          {uyelik.full_name} üyeliği sonlandırılır; kart masada kullanılamaz. Kayıt ve ödünç geçmişi
          silinmez. Açık ödüncü olan üyelik sonlandırılamaz: önce iade alın. Üye okuldan ayrıldıysa
          Kişiler ekranında “Ayrıldı olarak işaretle” eylemini kullanın.
        </p>
        <Select
          label="Sonlandırma nedeni"
          placeholder="Seçin"
          required
          value={neden}
          onChange={(e) => {
            setNeden(e.target.value as ManualTerminationReason | "");
            setAlanHatasi(undefined);
          }}
          options={(
            Object.entries(MANUAL_TERMINATION_TR) as Array<[ManualTerminationReason, string]>
          ).map(([value, label]) => ({ value, label }))}
          error={alanHatasi}
        />
        {hata && <ErrorBand hata={hata} />}
      </div>
    </Dialog>
  );
}

function OduncKaydi({ uyelikId }: { uyelikId: number }) {
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<MemberLoan>>(emptyPage<MemberLoan>());
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const boyut = 10;

  useEffect(() => {
    let iptal = false;
    uyelikApi
      .oduncKaydi(uyelikId, { limit: boyut, offset })
      .then((s) => {
        if (!iptal) setSayfa(s);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Ödünç kaydı yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [uyelikId, offset]);

  return (
    <section aria-label="Ödünç kaydı" className="space-y-2">
      <p className="text-title-small text-on-surface">Ödünç Kaydı</p>
      {hata && <ErrorBand hata={hata} />}
      {sayfa.results.length === 0 ? (
        <p className="text-body-small text-on-surface-variant">Bu üyeliğin ödünç kaydı yok.</p>
      ) : (
        <>
          <ul className="divide-y divide-outline-variant/60 rounded-shape-sm border border-outline-variant/70">
            {sayfa.results.map((lo) => (
              <li key={lo.id} className="px-3 py-2">
                <span className="block text-body-medium text-on-surface">{lo.work_title}</span>
                <span className="block text-body-small text-on-surface-variant">
                  {lo.barcode_display} · verildi {formatDate(lo.loaned_at.slice(0, 10))} · iade
                  tarihi {formatDate(lo.due_date)}
                  {lo.returned_at
                    ? ` · iade alındı ${formatDate(lo.returned_at.slice(0, 10))}`
                    : lo.overdue_days > 0
                      ? ` · ${formatNumber(lo.overdue_days)} gün gecikti`
                      : " · açık"}
                  {lo.has_override && ` · gerekçeli istisna (${lo.override_reason_display})`}
                  {lo.cardless && ` · kartsız ödünç (${lo.cardless_reason_display})`}
                </span>
              </li>
            ))}
          </ul>
          {sayfa.count > boyut && (
            <PaginationBar
              count={sayfa.count}
              offset={offset}
              pageSize={boyut}
              onOffset={setOffset}
            />
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Personele üyelik
// ---------------------------------------------------------------------------

function PersoneleUyelikPenceresi({
  onKapat,
  onAcildi,
}: {
  onKapat: () => void;
  onAcildi: () => void;
}) {
  const snackbar = useSnackbar();
  const [personel, setPersonel] = useState<Personnel[]>([]);
  const [secim, setSecim] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    okulApi
      .listPersonnel({ onlyActive: true, limit: 500 })
      .then((s) => {
        if (!iptal) setPersonel(s.results);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Personel listesi yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, []);

  const ac = async () => {
    if (!secim) return;
    setMesgul(true);
    setHata(null);
    try {
      await uyelikApi.uyelikAc({ personnel_id: Number(secim) });
      snackbar.success("Üyelik açıldı. Kartı basım kuyruğunda.");
      onAcildi();
    } catch (e) {
      setHata(hataOku(e, "Üyelik açılamadı."));
    } finally {
      setMesgul(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onKapat}
      title="Personele üyelik aç"
      actions={
        <>
          <Button variant="text" onClick={onKapat}>
            Vazgeç
          </Button>
          <Button onClick={() => void ac()} disabled={!secim || mesgul}>
            Üyelik aç
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-body-medium text-on-surface-variant">
          Diğer personele üyelik, Kütüphane Politikası'nda diğer personele ödünç müdürlük kararıyla
          açıldıysa açılır.
        </p>
        <Select
          label="Öğretmen ya da diğer personel"
          placeholder="Seçin"
          value={secim}
          onChange={(e) => setSecim(e.target.value)}
          options={personel.map((p) => ({
            value: String(p.id),
            label: `${p.full_name} (${MEMBER_KIND_TR[p.member_kind]})`,
          }))}
        />
        {hata && <ErrorBand hata={hata} />}
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Üyelik belgeleri: aydınlatma metni (E13) ve masa kartı (E19)
// ---------------------------------------------------------------------------

function UyelikBelgeleri() {
  const [adres, setAdres] = useState("");
  const [iletisim, setIletisim] = useState("");
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  return (
    <section aria-labelledby="uyelik-belgeleri">
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <h2 id="uyelik-belgeleri" className="text-title-medium text-on-surface">
          Üyelik Belgeleri
        </h2>
        <div className="space-y-2">
          <p className="text-title-small text-on-surface">{AYDINLATMA_ADI}</p>
          <p className="max-w-3xl text-body-small text-on-surface-variant">
            Öğrenci ve personel listeleri programa aktarılmadan önce duyurulur. Okul adı, ilçe ve
            müdür adı “Ayarlar → Okul Bilgileri”nden gelir. Başvuru adresi ve iletişim bilgisi
            yalnız bu basıma yazılır, saklanmaz; boş bırakılırsa elle doldurulacak satır basılır.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField
              label="Başvuru adresi"
              value={adres}
              maxLength={300}
              onChange={(e) => setAdres(e.target.value)}
              placeholder="Okulun yazışma adresi"
            />
            <TextField
              label="E-posta ya da telefon"
              value={iletisim}
              maxLength={120}
              onChange={(e) => setIletisim(e.target.value)}
              placeholder="Okulun kurumsal iletişim bilgisi"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() =>
                uyelikApi.aydinlatmaMetniPdf({
                  basvuru_adresi: adres.trim(),
                  iletisim: iletisim.trim(),
                })
              }
              dosyaAdi={() => dosyaAdi([AYDINLATMA_ADI, formatDate(todayIso())], "pdf")}
              onizlemeBasligi={AYDINLATMA_ADI}
              onHata={setHata}
            />
          </div>
        </div>
        <div className="space-y-2 border-t border-outline-variant/60 pt-4">
          <p className="text-title-small text-on-surface">{MASA_KARTI_ADI}</p>
          <p className="max-w-3xl text-body-small text-on-surface-variant">
            Kütüphane masasında görev yapan öğrenci ve personel için tek sayfalık kullanım ve
            gizlilik uyarısı. Görevliye göreve başlamadan verin; masada görünür bir yerde durur.
          </p>
          <div className="flex flex-wrap gap-2">
            <PdfDugmeleri
              pdfAl={() => uyelikApi.masaKartiPdf()}
              dosyaAdi={() => dosyaAdi([MASA_KARTI_ADI, formatDate(todayIso())], "pdf")}
              onizlemeBasligi={MASA_KARTI_ADI}
              onHata={setHata}
            />
          </div>
        </div>
        {hata && <ErrorBand hata={hata} />}
      </Card>
    </section>
  );
}
