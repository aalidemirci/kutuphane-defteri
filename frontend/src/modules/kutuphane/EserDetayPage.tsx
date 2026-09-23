// Eser Ayrıntısı — künye + o eserin nüshaları + hızlı nüsha açma.
//
// Ekranın iki ekseni vardır ve karıştırılmamalıdır (sözlük §1): ÜSTTE künye
// (eser: ad, yazar, ISBN, sınıflama), ALTTA nüshalar (rafta duran fiziksel
// kitaplar; her birinin barkodu ve kayıt numarası ayrıdır).
//
// Salt okunur alanlar: barkod, kayıt no, etiket basım ve doğrulama tarihleri.
// Numaralar sayaçtan gelir ve ASLA yeniden kullanılmaz; etiket alanlarını
// etiket basımı (F4) yazar. Ekranda görünürler ama düzenlenemezler.

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatDate, formatNumber } from "../../lib/format";
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
import TextField from "../../ui/TextField";
import UyariBandi from "../../ui/UyariBandi";
import { ACQUISITION_METHOD_TR, KATALOG_SAYFA_BOYUTU, kutuphaneApi } from "./api";
import type { Acquisition, Copy, CopyBody, Section, Work } from "./api";
import EserFormu from "./EserFormu";
import {
  OduncDurumu,
  SECICI_SINIRI,
  bolumSecenekleri,
  secimKesildiMetni,
  secimKesildiMi,
  useBolumler,
} from "./ortak";

/** Sayfanın başlığı — üst çubuktaki başlıkla aynıdır (docs/sozluk.md §4). */
export const ESER_DETAY_BASLIGI = "Eser Ayrıntısı";

/**
 * Tek seferde açılabilecek en çok nüsha — backend `MAX_COPIES_PER_ROW`'un
 * kopyasıdır. İkisinin eşitliği `apps/kutuphane/tests/test_on_yuz_sabitleri.py`
 * ile kilitlidir: sayı burada değişirse o kapı kırmızıya döner.
 */
const EN_COK_NUSHA = 50;

export default function EserDetayPage() {
  const { id } = useParams();
  const eserId = Number(id);
  const navigate = useNavigate();
  const bolumler = useBolumler();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const [eser, setEser] = useState<Work | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [duzenleniyor, setDuzenleniyor] = useState(false);
  const [isbnUyarisi, setIsbnUyarisi] = useState<string[]>([]);

  const eseriYukle = useCallback(() => {
    setYukleniyor(true);
    kutuphaneApi
      .getWork(eserId)
      .then((kayit) => {
        setEser(kayit);
        setIsbnUyarisi(kayit.isbn_warning ? [kayit.isbn_warning] : []);
        setHata(null);
      })
      .catch((e: unknown) => setHata(hataOku(e, "Eser yüklenemedi.")))
      .finally(() => setYukleniyor(false));
  }, [eserId]);

  useEffect(eseriYukle, [eseriYukle]);

  const eseriSil = async () => {
    if (eser === null) return;
    const onay = await confirm({
      title: "Eser katalogdan silinsin mi?",
      message: `“${eser.title}” künyesi katalogdan kalkar. Nüshası olan eser silinemez; önce nüshaları kayıttan düşürün. Yanlış girilmiş künyeler içindir.`,
      confirmLabel: "Sil",
    });
    if (!onay) return;
    try {
      await kutuphaneApi.deleteWork(eser.id);
      snackbar.success("Eser silindi.");
      navigate("/katalog");
    } catch (e) {
      setHata(hataOku(e, "Eser silinemedi."));
    }
  };

  return (
    <div className="space-y-[var(--kd-page-gap)]">
      <ModuleHeader
        backTo="/katalog"
        moduleLabel="Katalog"
        title={ESER_DETAY_BASLIGI}
        actions={
          eser && (
            <>
              <Button variant="text" icon="delete" onClick={eseriSil}>
                Sil
              </Button>
              <Button icon="edit" onClick={() => setDuzenleniyor(true)}>
                Künyeyi düzenle
              </Button>
            </>
          )
        }
      />

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor && eser === null ? (
        <SkeletonList rows={4} />
      ) : eser === null ? (
        <EmptyState
          icon="menu_book"
          title="Eser bulunamadı"
          description="Kayıt silinmiş ya da adres yanlış olabilir. Katalog listesinden yeniden açın."
        />
      ) : (
        <>
          <UyariBandi
            title="ISBN uyarısı"
            messages={isbnUyarisi}
            onClose={() => setIsbnUyarisi([])}
          />
          <KunyeKarti eser={eser} />
          {/* Nüsha sayısı KÜNYEDEN gelir; nüsha açıldığında ya da silindiğinde
              eser de yeniden okunur, yoksa "2 nüsha · 1 rafta" eski değerde kalır. */}
          <NushalarBolumu eser={eser} bolumler={bolumler} onEserTazele={eseriYukle} />
        </>
      )}

      {duzenleniyor && eser !== null && (
        <EserFormu
          eser={eser}
          bolumler={bolumler}
          onClose={() => setDuzenleniyor(false)}
          onSaved={(kayit) => {
            setDuzenleniyor(false);
            setEser(kayit);
            setIsbnUyarisi(kayit.isbn_warning ? [kayit.isbn_warning] : []);
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Künye
// ---------------------------------------------------------------------------

function Satir({ etiket, deger }: { etiket: string; deger: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-label-medium text-on-surface-variant">{etiket}</dt>
      <dd className="text-body-medium text-on-surface">{deger || "—"}</dd>
    </div>
  );
}

function KunyeKarti({ eser }: { eser: Work }) {
  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div>
        <p className="text-title-medium text-on-surface">{eser.title}</p>
        <p className="text-body-small text-on-surface-variant">
          {eser.authors || "Yazar yazılmamış"}
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
        <Satir etiket="Çevirmen" deger={eser.translator} />
        <Satir etiket="Yayınevi" deger={eser.publisher} />
        <Satir etiket="Baskı" deger={eser.edition} />
        <Satir
          etiket="Yayın yılı"
          deger={eser.publish_year === null ? "" : String(eser.publish_year)}
        />
        <Satir etiket="ISBN" deger={eser.isbn} />
        <Satir etiket="ISBN (13 hane)" deger={eser.isbn13} />
        <Satir etiket="Konu(lar)" deger={eser.subjects} />
        <Satir etiket="Kaynak türü" deger={eser.resource_type_display} />
        <Satir etiket="Bölüm" deger={eser.section_name ?? ""} />
        <Satir etiket="Sınıflama kodu" deger={eser.classification_code} />
        <Satir etiket="Sınıflama kaynağı" deger={eser.classification_source_display} />
        <Satir etiket="Yer numarası" deger={eser.call_number} />
        <Satir etiket="Dil" deger={eser.language} />
      </dl>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Nüshalar
// ---------------------------------------------------------------------------

function NushalarBolumu({
  eser,
  bolumler,
  onEserTazele,
}: {
  eser: Work;
  bolumler: Section[];
  /** Nüsha sayısı künyede durduğu için eser de yeniden okunur. */
  onEserTazele: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const [sayfa, setSayfa] = useState<Paginated<Copy>>(emptyPage<Copy>());
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);
  const [ekleniyor, setEkleniyor] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState<Copy | null>(null);

  const tazele = useCallback(() => {
    setTazeleme((k) => k + 1);
    onEserTazele();
  }, [onEserTazele]);

  useEffect(() => {
    let iptal = false;
    let geriDusuluyor = false;
    setYukleniyor(true);
    kutuphaneApi
      .listCopies({ work: eser.id, limit: KATALOG_SAYFA_BOYUTU, offset })
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
        if (!iptal) setHata(hataOku(e, "Nüshalar yüklenemedi."));
      })
      .finally(() => {
        if (!iptal && !geriDusuluyor) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [eser.id, offset, tazeleme]);

  const sutunlar: Column<Copy>[] = [
    { header: "Barkod", cell: (c) => c.barcode_display },
    { header: "Kayıt no", align: "right", cell: (c) => formatNumber(c.accession_no) },
    { header: "Bölüm", cell: (c) => c.section_name || "—" },
    { header: "Durum", cell: (c) => <OduncDurumu nusha={c} /> },
    { header: "Etiket basımı", cell: (c) => formatDate(c.label_printed_at) },
    { header: "Etiket doğrulaması", cell: (c) => formatDate(c.label_verified_at) },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Nüshalar</p>
          <p className="text-body-small text-on-surface-variant">
            {formatNumber(eser.copy_count)} nüsha · {formatNumber(eser.available_copy_count)} rafta
          </p>
        </div>
        {eser.is_digital ? (
          <p className="text-body-small text-on-surface-variant">
            E-kitap ve e-veri tabanında nüsha açılmaz.
          </p>
        ) : (
          <Button icon="add" onClick={() => setEkleniyor(true)}>
            Nüsha ekle
          </Button>
        )}
      </div>

      {hata && <ErrorBand hata={hata} />}

      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : sayfa.results.length === 0 ? (
        <EmptyState
          compact
          icon="inventory_2"
          title="Bu eserin nüshası yok — rafta duran kitap için nüsha açın."
        />
      ) : (
        <>
          <DataTable<Copy>
            columns={sutunlar}
            rows={sayfa.results}
            onRowClick={(c) => setDuzenlenen(c)}
            rowLabel={(c) => `${c.barcode_display} numaralı nüshayı düzenle`}
          />
          <PaginationBar
            count={sayfa.count}
            offset={offset}
            pageSize={KATALOG_SAYFA_BOYUTU}
            onOffset={setOffset}
          />
        </>
      )}

      {ekleniyor && (
        <NushaEklemeFormu
          eser={eser}
          bolumler={bolumler}
          onClose={() => setEkleniyor(false)}
          onSaved={() => {
            setEkleniyor(false);
            tazele();
          }}
        />
      )}

      {duzenlenen !== null && (
        <NushaDuzenlemeFormu
          nusha={duzenlenen}
          bolumler={bolumler}
          onClose={() => setDuzenlenen(null)}
          onSaved={() => {
            setDuzenlenen(null);
            tazele();
          }}
        />
      )}
    </div>
  );
}

/** Nüsha bayrakları — üç mevzuat kaynaklı, biri kalıcı nitelik. */
function BayrakKutulari({
  danisma,
  piyasada,
  ciltli,
  nadir,
  onChange,
}: {
  danisma: boolean;
  piyasada: boolean;
  ciltli: boolean;
  nadir: boolean;
  onChange: (alan: "danisma" | "piyasada" | "ciltli" | "nadir", deger: boolean) => void;
}) {
  const kutular: Array<{
    alan: "danisma" | "piyasada" | "ciltli" | "nadir";
    label: string;
    checked: boolean;
  }> = [
    { alan: "danisma", label: "Danışma kaynağı (ödünç verilmez)", checked: danisma },
    { alan: "piyasada", label: "Piyasada mevcudu yok (ödünç verilmez)", checked: piyasada },
    { alan: "ciltli", label: "Ciltli süreli yayın", checked: ciltli },
    { alan: "nadir", label: "El yazması / nadir eser", checked: nadir },
  ];
  return (
    <div className="space-y-1">
      {kutular.map((k) => (
        <label
          key={k.alan}
          className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface"
        >
          <input
            type="checkbox"
            checked={k.checked}
            onChange={(e) => onChange(k.alan, e.target.checked)}
            className="size-5 shrink-0 accent-primary"
          />
          {k.label}
        </label>
      ))}
    </div>
  );
}

/** Edinim seçicisinin etiketi: yol + tarih (bağışçı adı listede GÖSTERİLMEZ). */
function edinimEtiketi(edinim: Acquisition): string {
  return `${ACQUISITION_METHOD_TR[edinim.method]} — ${formatDate(edinim.date)}`;
}

function NushaEklemeFormu({
  eser,
  bolumler,
  onClose,
  onSaved,
}: {
  eser: Work;
  bolumler: Section[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [edinimler, setEdinimler] = useState<Acquisition[]>([]);
  const [edinim, setEdinim] = useState("");
  const [adet, setAdet] = useState("1");
  const [bolum, setBolum] = useState(eser.section === null ? "" : String(eser.section));
  const [eskiKayitNo, setEskiKayitNo] = useState("");
  const [tkys, setTkys] = useState("");
  const [bayraklar, setBayraklar] = useState({
    danisma: false,
    piyasada: false,
    ciltli: false,
    nadir: false,
  });
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .listAcquisitions({ limit: SECICI_SINIRI })
      .then((sayfa) => {
        if (iptal) return;
        setEdinimler(sayfa.results);
        if (sayfa.results.length > 0) setEdinim(String(sayfa.results[0].id));
      })
      .catch(() => {
        if (!iptal) setEdinimler([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    if (!edinim) {
      setFieldError("acquisition", "Edinim seçilmelidir.");
      return;
    }
    const sayi = Number(adet);
    if (!Number.isInteger(sayi) || sayi < 1 || sayi > EN_COK_NUSHA) {
      setFieldError("count", `Nüsha sayısı 1 ile ${EN_COK_NUSHA} arasında olmalıdır.`);
      return;
    }
    const govde: CopyBody = {
      work: eser.id,
      acquisition: Number(edinim),
      section: bolum ? Number(bolum) : null,
      old_register_no: eskiKayitNo.trim(),
      external_asset_ref: tkys.trim(),
      is_reference: bayraklar.danisma,
      is_out_of_print: bayraklar.piyasada,
      is_bound_periodical: bayraklar.ciltli,
      is_rare_or_manuscript: bayraklar.nadir,
    };
    setBusy(true);
    try {
      if (sayi === 1) {
        await kutuphaneApi.createCopy(govde);
        snackbar.success("Nüsha açıldı.");
      } else {
        const sonuc = await kutuphaneApi.createCopies({ ...govde, count: sayi });
        snackbar.success(`${formatNumber(sonuc.count)} nüsha açıldı.`);
      }
      onSaved();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Nüsha açılamadı."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Nüsha ekle"
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
          Barkod ve kayıt numarası program tarafından verilir; numara asla yeniden kullanılmaz.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select
            label="Edinim"
            required
            placeholder="Seçin"
            value={edinim}
            onChange={(e) => setEdinim(e.target.value)}
            options={edinimler.map((a) => ({ value: String(a.id), label: edinimEtiketi(a) }))}
            error={errors.acquisition}
            helperText={
              edinimler.length === 0
                ? "Önce Edinimler ve Bağışlar ekranından bir edinim açın."
                : secimKesildiMi(edinimler.length)
                  ? secimKesildiMetni("“Edinimler ve Bağışlar” ekranını")
                  : "Her nüsha bir edinim partisinden gelir."
            }
          />
          <TextField
            label="Nüsha sayısı"
            inputMode="numeric"
            value={adet}
            onChange={(e) => setAdet(e.target.value)}
            error={errors.count}
            helperText={`Aynı künyeden en çok ${EN_COK_NUSHA} nüsha açılır.`}
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
            label="Eski kayıt no"
            value={eskiKayitNo}
            onChange={(e) => setEskiKayitNo(e.target.value)}
            error={errors.old_register_no}
            helperText="Kitaptaki eski damga; yalnız tek nüsha açarken yazılır."
          />
          <TextField
            label="TKYS kodu"
            value={tkys}
            onChange={(e) => setTkys(e.target.value)}
            error={errors.external_asset_ref}
            helperText="Taşınır Kayıt ve Yönetim Sistemi (TKYS) karşılığı; program doğrulamaz. Okulunuz TKYS’de nüsha bazında kayıt tutmuyorsa boş bırakın."
          />
        </div>

        <BayrakKutulari
          danisma={bayraklar.danisma}
          piyasada={bayraklar.piyasada}
          ciltli={bayraklar.ciltli}
          nadir={bayraklar.nadir}
          onChange={(alan, deger) => setBayraklar((onceki) => ({ ...onceki, [alan]: deger }))}
        />
      </div>
    </Dialog>
  );
}

function NushaDuzenlemeFormu({
  nusha,
  bolumler,
  onClose,
  onSaved,
}: {
  nusha: Copy;
  bolumler: Section[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [bolum, setBolum] = useState(nusha.section === null ? "" : String(nusha.section));
  const [eskiKayitNo, setEskiKayitNo] = useState(nusha.old_register_no);
  const [tkys, setTkys] = useState(nusha.external_asset_ref);
  const [bayraklar, setBayraklar] = useState({
    danisma: nusha.is_reference,
    piyasada: nusha.is_out_of_print,
    ciltli: nusha.is_bound_periodical,
    nadir: nusha.is_rare_or_manuscript,
  });
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, applyApiError, clearErrors } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    setBusy(true);
    try {
      await kutuphaneApi.updateCopy(nusha.id, {
        section: bolum ? Number(bolum) : null,
        old_register_no: eskiKayitNo.trim(),
        external_asset_ref: tkys.trim(),
        is_reference: bayraklar.danisma,
        is_out_of_print: bayraklar.piyasada,
        is_bound_periodical: bayraklar.ciltli,
        is_rare_or_manuscript: bayraklar.nadir,
      });
      snackbar.success("Nüsha güncellendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Nüsha güncellenemedi."));
      setBusy(false);
    }
  };

  const sil = async () => {
    const onay = await confirm({
      title: "Nüsha silinsin mi?",
      message: `${nusha.barcode_display} numaralı nüsha katalogdan kalkar. Numara serbest kalmaz, başka bir kitaba verilmez. Yanlış açılmış nüshalar içindir; ayıklanan ya da kaybolan kitap için kayıttan düşme yolu kullanılır.`,
      confirmLabel: "Sil",
    });
    if (!onay) return;
    setBusy(true);
    try {
      await kutuphaneApi.deleteCopy(nusha.id);
      snackbar.success("Nüsha silindi.");
      onSaved();
    } catch (e) {
      setHata(hataOku(e, "Nüsha silinemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Nüshayı düzenle"
      actions={
        <>
          <Button variant="text" icon="delete" onClick={sil} disabled={busy}>
            Sil
          </Button>
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

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          <Satir etiket="Barkod" deger={nusha.barcode_display} />
          <Satir etiket="Kayıt no" deger={formatNumber(nusha.accession_no)} />
          <Satir etiket="Etiket basımı" deger={formatDate(nusha.label_printed_at)} />
          <Satir etiket="Etiket doğrulaması" deger={formatDate(nusha.label_verified_at)} />
        </dl>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select
            label="Bölüm"
            placeholder="— yok —"
            value={bolum}
            onChange={(e) => setBolum(e.target.value)}
            options={bolumSecenekleri(bolumler)}
            error={errors.section}
          />
          <TextField
            label="Eski kayıt no"
            value={eskiKayitNo}
            onChange={(e) => setEskiKayitNo(e.target.value)}
            error={errors.old_register_no}
          />
          <TextField
            label="TKYS kodu"
            value={tkys}
            onChange={(e) => setTkys(e.target.value)}
            error={errors.external_asset_ref}
            helperText="Taşınır Kayıt ve Yönetim Sistemi (TKYS) karşılığı; program doğrulamaz. Okulunuz TKYS’de nüsha bazında kayıt tutmuyorsa boş bırakın."
          />
        </div>

        <BayrakKutulari
          danisma={bayraklar.danisma}
          piyasada={bayraklar.piyasada}
          ciltli={bayraklar.ciltli}
          nadir={bayraklar.nadir}
          onChange={(alan, deger) => setBayraklar((onceki) => ({ ...onceki, [alan]: deger }))}
        />
      </div>
    </Dialog>
  );
}
