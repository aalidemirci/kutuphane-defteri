// Ayıklama teklifinin pencereleri (F8): kalem ekle · kalemi düzenle · komisyon kararını
// bağla · harcama yetkilisinin onayı · iptal.
//
// Gerekçe seçilince TMY yolu E7 tablosundan (sunucunun `rules` yanıtı) KENDİLİĞİNDEN
// gelir; iki yolu olan gerekçede (yıpranma: 27/1 ya da 28; düzeye uygunsuzluk: 24/2 ya da
// 31) kullanıcı değiştirebilir. 12/1-ç kaleminde uyulmayan ölçüt zorunludur ve 10/1-b
// listede yoktur (o kaynak devredilir). Devir yolunda devralacak okul ya da kurum yazılır
// (onaydan önce zorunlu). Kural sunucudadır; ret iletisi (engelli nüshalar kitap kitap)
// olduğu gibi gösterilir. Bir nüsha engelliyse hiçbiri eklenmez (tek işlem).
//
// Harcama yetkilisinin ve komisyon üyelerinin adları KİŞİ ADIDIR: sunucuda şifreli
// saklanır; parola kurulmadan yazan istek 409 döner (ui/ErrorBand).

import { useEffect, useState } from "react";

import { useDebounced } from "../../hooks/useDebounced";
import { useFormErrors } from "../../hooks/useFormErrors";
import { formatNumber, todayIso } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import PaginationBar from "../../ui/PaginationBar";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { kararEtiketi, kodSecenekleri, MetinAlani } from "../kutuphane/ortak";
import { ayiklamaApi, GEREKCE_BENDI, GEREKCE_TR } from "./api";
import type {
  AdaySayfasi,
  AyiklamaKurallari,
  Gerekce,
  Kalem,
  KayittanDusmeOnerisi,
  TeklifAyrintisi,
  TmyYolu,
} from "./api";
import {
  alanHatalari,
  devirMi,
  gerekceYollari,
  kodlariAyir,
  OnayKutusu,
  useAyiklamaKararlari,
} from "./ortak";

const ADAY_SAYFA_BOYUTU = 20;

/** Aday penceresinin altındaki iki bilgi kutusunun başlıkları (F8 ekleri 34). */
export const KAYIP_ONERILERI_BASLIGI = "Kayıp nüshaların kayıttan düşme önerileri";
export const HASAR_ONERILERI_BASLIGI = "Hasar dosyalarının kayıttan düşme önerileri";

/**
 * Ayıklamaya KONMAYAN kayıttan düşme önerileri (25.09.2026 kullanıcı kararı, tasarım F8 ekleri
 * 34): Md. 12/1'in bentleri kaybı ve hasarı saymaz; kayıp ve hasar dosyasının önerisi sayımda
 * kayıp/hasar tutanağıyla düşülür. Liste yalnız "öneri nereye gitti" sorusunu cevaplar;
 * seçim yoktur.
 */
function OneriListesi({ baslik, oneriler }: { baslik: string; oneriler: KayittanDusmeOnerisi[] }) {
  if (oneriler.length === 0) return null;
  return (
    <div className="rounded-shape-md bg-surface-container px-3 py-2">
      <p className="text-label-large text-on-surface">{baslik}</p>
      <ul className="mt-1 space-y-1 text-body-small text-on-surface-variant">
        {oneriler.map((n) => (
          <li key={n.id}>
            <span className="font-mono">{n.barcode_display}</span> — {n.work_title}
            {n.status !== "AVAILABLE" && n.status !== "LOST" ? ` (${n.status_display})` : ""}:{" "}
            {n.blocker}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Gerekçe seçeneklerinin etiketi: ad + bent ("Aşırı kullanımdan yıpranmış (Md. 12/1-a)"). */
function gerekceSecenekleri() {
  return kodSecenekleri(GEREKCE_TR).map((s) => ({
    ...s,
    label: `${s.label} (${GEREKCE_BENDI[s.value as Gerekce]})`,
  }));
}

/** Gerekçe · yol · ölçüt · devralacak kurum alanları (ekleme ve düzenleme ortak). */
function GerekceAlanlari({
  kurallar,
  gerekce,
  yol,
  olcut,
  kurum,
  onGerekce,
  onYol,
  onOlcut,
  onKurum,
  errors,
  kilitli = false,
}: {
  kurallar: AyiklamaKurallari | null;
  gerekce: Gerekce | "";
  yol: TmyYolu | "";
  olcut: string;
  kurum: string;
  onGerekce: (g: Gerekce | "", varsayilanYol: TmyYolu | "") => void;
  onYol: (y: TmyYolu) => void;
  onOlcut: (o: string) => void;
  onKurum: (k: string) => void;
  errors: Partial<Record<string, string>>;
  /** Yalnız devralacak kurum düzenlenir (sunulmuş teklif). */
  kilitli?: boolean;
}) {
  const { yollar, olcutGerekir } = gerekceYollari(kurallar, gerekce);
  const yolSecenekleri = (kurallar?.paths ?? [])
    .filter((p) => yollar.includes(p.value))
    .map((p) => ({ value: p.value, label: p.label }));
  const devir = devirMi(kurallar, yol);
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <Select
        label="Ayıklama gerekçesi"
        required
        placeholder="Seçin"
        value={gerekce}
        disabled={kilitli}
        onChange={(e) => {
          const g = e.target.value as Gerekce | "";
          onGerekce(g, gerekceYollari(kurallar, g).varsayilan);
        }}
        options={gerekceSecenekleri()}
        error={errors.reason}
        helperText="Yönetmelik Md. 12/1'de sayılan nedenler."
      />
      <Select
        label="TMY yolu"
        required
        placeholder="Seçin"
        value={yol}
        disabled={kilitli || yolSecenekleri.length < 2}
        onChange={(e) => onYol(e.target.value as TmyYolu)}
        options={yolSecenekleri}
        error={errors.tmy_path}
        helperText={
          gerekce === ""
            ? "Önce gerekçeyi seçin; yol gerekçeye göre kendiliğinden gelir."
            : gerekce === "LEVEL_MISMATCH"
              ? "Md. 12/1, yaş ve gelişim düzeyine uygun olmayan kaynağın (Md. 10/1-b) uygun okullara veya kurumlara devrini ister; program kurumun düzeyine uygun olmayan kaynağı da devir yoluna bağlar."
              : gerekce === "WORN"
                ? "Kendiliğinden seçilir. Ekonomik ömrü bittiyse hurdaya ayırma (TMY 28) seçilebilir."
                : "Gerekçeye göre kendiliğinden seçilir."
        }
      />
      {olcutGerekir && (
        <Select
          className="sm:col-span-2"
          label="Uyulmayan ölçüt"
          required
          placeholder="Seçin"
          value={olcut}
          disabled={kilitli}
          onChange={(e) => onOlcut(e.target.value)}
          options={(kurallar?.criteria ?? []).map((c) => ({ value: c.value, label: c.label }))}
          error={errors.criterion}
          helperText="Yaş ve gelişim düzeyine uygun olmayan kaynak bu listede yoktur: “Kurumun düzeyine uygun değil” gerekçesiyle devredilir."
        />
      )}
      {devir && (
        <TextField
          className="sm:col-span-2"
          label="Devralacak okul ya da kurum"
          value={kurum}
          onChange={(e) => onKurum(e.target.value)}
          error={errors.transfer_target}
          helperText="Onaydan önce yazılmalıdır. Kişi adı değil, okulun ya da kurumun adı."
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kalem ekle
// ---------------------------------------------------------------------------

export function KalemEkleDiyalogu({
  teklifId,
  kurallar,
  onClose,
  onEklendi,
}: {
  teklifId: number;
  kurallar: AyiklamaKurallari | null;
  onClose: () => void;
  onEklendi: (adet: number) => void;
}) {
  const [gerekce, setGerekce] = useState<Gerekce | "">("");
  const [yol, setYol] = useState<TmyYolu | "">("");
  const [olcut, setOlcut] = useState("");
  const [kurum, setKurum] = useState("");
  const [kodlar, setKodlar] = useState("");
  const [secili, setSecili] = useState<Set<number>>(new Set());
  const [ara, setAra] = useState("");
  const [offset, setOffset] = useState(0);
  const [adaylar, setAdaylar] = useState<AdaySayfasi | null>(null);
  const [engeller, setEngeller] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const arananMetin = useDebounced(ara);

  useEffect(() => {
    let iptal = false;
    ayiklamaApi
      .adaylar({
        q: arananMetin.trim(),
        limit: ADAY_SAYFA_BOYUTU,
        offset,
      })
      .then((s) => {
        if (!iptal) setAdaylar(s);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Aday nüshalar yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, [arananMetin, offset]);

  const okutulan = kodlariAyir(kodlar);
  const toplam = okutulan.length + secili.size;

  const ekle = async () => {
    clearErrors();
    setHata(null);
    setEngeller([]);
    if (!gerekce) {
      setFieldError("reason", "Ayıklama gerekçesini seçin.");
      return;
    }
    if (toplam === 0) {
      setFieldError("barcodes", "Aday listesinden nüsha seçin ya da kütüphane etiketini okutun.");
      return;
    }
    setBusy(true);
    try {
      const sonuc = await ayiklamaApi.kalemEkle(teklifId, {
        reason: gerekce,
        tmy_path: yol,
        criterion: olcut,
        transfer_target: devirMi(kurallar, yol) ? kurum.trim() : "",
        barcodes: okutulan,
        copies: Array.from(secili),
      });
      onEklendi(sonuc.added.length);
    } catch (e) {
      const liste = alanHatalari(e, "barcodes");
      if (liste.length > 1) setEngeller(liste);
      applyApiError(e);
      setHata(hataOku(e, "Kalemler eklenemedi."));
      setBusy(false);
    }
  };

  const secimDegistir = (id: number, deger: boolean) =>
    setSecili((onceki) => {
      const yeni = new Set(onceki);
      if (deger) yeni.add(id);
      else yeni.delete(id);
      return yeni;
    });

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Kalem ekle"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="add" onClick={() => void ekle()} disabled={busy}>
            {busy ? "Ekleniyor…" : `Teklife ekle (${formatNumber(toplam)})`}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        {engeller.length > 0 && (
          <ul
            aria-label="Eklenemeyen nüshalar"
            className="list-disc space-y-1 rounded-shape-sm bg-error-container py-2 pl-8 pr-3 text-body-small text-on-error-container"
          >
            {engeller.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        )}
        <p className="text-body-small text-on-surface-variant">
          Aynı gerekçe ve yol, bu pencerede seçilen ve okutulan bütün nüshalara verilir. Bir nüsha
          ayıklamaya konamıyorsa (ödünçte, teslimde, onarımda, kayıp, nadir eser, çözülmemiş dosyası
          ya da hasar dosyasında kayıttan düşme önerisi var ya da başka bir teklifte) hiçbiri
          eklenmez.
        </p>

        <GerekceAlanlari
          kurallar={kurallar}
          gerekce={gerekce}
          yol={yol}
          olcut={olcut}
          kurum={kurum}
          onGerekce={(g, v) => {
            setGerekce(g);
            setYol(v);
            setOlcut("");
          }}
          onYol={setYol}
          onOlcut={setOlcut}
          onKurum={setKurum}
          errors={errors}
        />

        <MetinAlani
          label="Kütüphane etiketleri"
          value={kodlar}
          onChange={setKodlar}
          rows={3}
          placeholder="2026-000123"
          error={errors.barcodes}
          helperText="Okuyucuyla okutun ya da numaraları yazın; her kod ayrı satıra düşer."
        />

        <section aria-labelledby="adaylar-baslik" className="space-y-2">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h3 id="adaylar-baslik" className="text-title-small font-semibold text-on-surface">
              Aday Nüshalar
            </h3>
            <p className="text-body-small text-on-surface-variant">
              {`${formatNumber(secili.size)} nüsha seçildi`}
            </p>
          </div>
          <TextField
            label="Ara"
            value={ara}
            placeholder="Kaynak adı, yazar ya da ISBN…"
            onChange={(e) => {
              setAra(e.target.value);
              setOffset(0);
            }}
          />
          {adaylar === null ? (
            <SkeletonList rows={3} />
          ) : adaylar.results.length === 0 ? (
            <EmptyState
              compact
              icon="search_off"
              title="Aday nüsha yok"
              description="Yalnız raftaki, nadir eser olmayan ve süren bir teklifte bulunmayan nüshalar ayıklamaya konur."
            />
          ) : (
            <>
              <ul className="divide-y divide-outline-variant/50 rounded-shape-md border border-outline-variant/70">
                {adaylar.results.map((n) => (
                  <li key={n.id} className="px-3">
                    <OnayKutusu
                      checked={secili.has(n.id)}
                      onChange={(d) => secimDegistir(n.id, d)}
                      etiket={
                        <span className="flex flex-wrap items-center gap-x-2">
                          <span className="font-mono">{n.barcode_display}</span>
                          <span className="text-on-surface">{n.work_title}</span>
                          {n.work_authors && (
                            <span className="text-on-surface-variant">{n.work_authors}</span>
                          )}
                        </span>
                      }
                    />
                  </li>
                ))}
              </ul>
              <PaginationBar
                count={adaylar.count}
                offset={offset}
                pageSize={ADAY_SAYFA_BOYUTU}
                onOffset={setOffset}
              />
            </>
          )}
          {adaylar !== null && (
            <OneriListesi baslik={KAYIP_ONERILERI_BASLIGI} oneriler={adaylar.lost_proposals} />
          )}
          {adaylar !== null && (
            <OneriListesi baslik={HASAR_ONERILERI_BASLIGI} oneriler={adaylar.damage_proposals} />
          )}
        </section>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Kalemi düzenle
// ---------------------------------------------------------------------------

export function KalemDuzenleDiyalogu({
  teklifId,
  kalem,
  taslak,
  kurallar,
  onClose,
  onKaydedildi,
}: {
  teklifId: number;
  kalem: Kalem;
  /** Taslakta bütün alanlar; sunulmuş teklifte yalnız devralacak kurum değişir. */
  taslak: boolean;
  kurallar: AyiklamaKurallari | null;
  onClose: () => void;
  onKaydedildi: () => void;
}) {
  const [gerekce, setGerekce] = useState<Gerekce | "">(kalem.reason);
  const [yol, setYol] = useState<TmyYolu | "">(kalem.tmy_path);
  const [olcut, setOlcut] = useState(kalem.criterion);
  const [kurum, setKurum] = useState(kalem.transfer_target);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError } = useFormErrors();

  const kaydet = async () => {
    clearErrors();
    setHata(null);
    setBusy(true);
    try {
      await ayiklamaApi.kalemGuncelle(
        teklifId,
        kalem.id,
        taslak
          ? {
              reason: gerekce || undefined,
              tmy_path: yol,
              criterion: olcut,
              transfer_target: devirMi(kurallar, yol) ? kurum.trim() : "",
            }
          : { transfer_target: kurum.trim() },
      );
      onKaydedildi();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Kalem güncellenemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={taslak ? "Kalemi düzenle" : "Devralacak kurumu düzenle"}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={() => void kaydet()} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-medium text-on-surface">
          <span className="font-mono">{kalem.barcode_display}</span> — {kalem.work_title}
        </p>
        <GerekceAlanlari
          kurallar={kurallar}
          gerekce={gerekce}
          yol={yol}
          olcut={olcut}
          kurum={kurum}
          onGerekce={(g, v) => {
            setGerekce(g);
            setYol(v);
            setOlcut("");
          }}
          onYol={setYol}
          onOlcut={setOlcut}
          onKurum={setKurum}
          errors={errors}
          kilitli={!taslak}
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Dışarıda bırakılan kalemler (komisyon kararı ve onay ortak)
// ---------------------------------------------------------------------------

function DisaridaBirakma({
  kalemler,
  etiket,
  secili,
  gerekceler,
  onSecim,
  onGerekce,
  hata,
}: {
  kalemler: Kalem[];
  etiket: string;
  secili: Record<number, boolean>;
  gerekceler: Record<number, string>;
  onSecim: (id: number, deger: boolean) => void;
  onGerekce: (id: number, metin: string) => void;
  hata?: string;
}) {
  return (
    <div className="space-y-2">
      {hata && (
        <p role="alert" className="text-body-small text-error">
          {hata}
        </p>
      )}
      <ul className="space-y-2">
        {kalemler.map((k) => (
          <li key={k.id} className="rounded-shape-md border border-outline-variant/70 px-3 py-2">
            <p className="text-body-medium text-on-surface">
              <span className="font-mono">{k.barcode_display}</span> — {k.work_title}
            </p>
            <p className="text-body-small text-on-surface-variant">
              {k.reason_display} · {k.tmy_path_display}
            </p>
            <OnayKutusu
              etiket={etiket}
              checked={secili[k.id] ?? false}
              onChange={(d) => onSecim(k.id, d)}
            />
            {secili[k.id] && (
              <TextField
                label="Gerekçe"
                value={gerekceler[k.id] ?? ""}
                onChange={(e) => onGerekce(k.id, e.target.value)}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Seçili kalemlerin gerekçe eşlemesi; gerekçesi boş olan varsa `null`. */
function gerekceEslemesi(
  secili: Record<number, boolean>,
  gerekceler: Record<number, string>,
): Record<string, string> | null {
  const sonuc: Record<string, string> = {};
  for (const [id, isaretli] of Object.entries(secili)) {
    if (!isaretli) continue;
    const metin = (gerekceler[Number(id)] ?? "").trim();
    if (!metin) return null;
    sonuc[id] = metin;
  }
  return sonuc;
}

// ---------------------------------------------------------------------------
// Komisyon kararını bağla
// ---------------------------------------------------------------------------

export function KararBaglaDiyalogu({
  teklifId,
  kalemler,
  onClose,
  onBaglandi,
}: {
  teklifId: number;
  kalemler: Kalem[];
  onClose: () => void;
  onBaglandi: () => void;
}) {
  const kararlar = useAyiklamaKararlari();
  const [karar, setKarar] = useState("");
  const [secili, setSecili] = useState<Record<number, boolean>>({});
  const [gerekceler, setGerekceler] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();

  const bagla = async () => {
    clearErrors();
    setHata(null);
    if (!karar) {
      setFieldError("commission_decision", "Komisyon kararı seçilmelidir.");
      return;
    }
    const kept = gerekceEslemesi(secili, gerekceler);
    if (kept === null) {
      setFieldError("kept", "Ayıklanmayan her kalemin gerekçesi yazılmalıdır.");
      return;
    }
    setBusy(true);
    try {
      await ayiklamaApi.kararBagla(teklifId, Number(karar), kept);
      onBaglandi();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Komisyon kararı bağlanamadı."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Komisyon kararını bağla"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="gavel" onClick={() => void bagla()} disabled={busy}>
            {busy ? "Bağlanıyor…" : "Kararı bağla"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <Select
          label="Komisyon kararı"
          required
          placeholder="Seçin"
          value={karar}
          onChange={(e) => setKarar(e.target.value)}
          options={(kararlar ?? []).map((k) => ({ value: String(k.id), label: kararEtiketi(k) }))}
          error={errors.commission_decision}
          helperText={
            kararlar !== null && kararlar.length === 0
              ? "Önce Edinimler ve Bağışlar → Komisyon Kararları sekmesinden bir “Ayıklama” kararı ekleyin."
              : "Yalnız “Ayıklama” türündeki kararlar listelenir."
          }
        />
        <p className="text-body-small text-on-surface-variant">
          Komisyonun ayıklanmasına karar vermediği kalemi işaretleyin ve gerekçesini yazın; kalem
          silinmez, tutanakta ayrı tabloda görünür. El yazması ya da nadir eser olarak işaretli
          kalem ayıklanamaz: onu da bu kutuyla işaretleyin.
        </p>
        <DisaridaBirakma
          kalemler={kalemler}
          etiket="Komisyon ayıklanmasına karar vermedi"
          secili={secili}
          gerekceler={gerekceler}
          onSecim={(id, d) => setSecili((o) => ({ ...o, [id]: d }))}
          onGerekce={(id, m) => setGerekceler((o) => ({ ...o, [id]: m }))}
          hata={errors.kept}
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Harcama yetkilisinin onayı
// ---------------------------------------------------------------------------

export function OnayDiyalogu({
  teklif,
  kalemler,
  onClose,
  onOnaylandi,
}: {
  teklif: TeklifAyrintisi;
  kalemler: Kalem[];
  onClose: () => void;
  onOnaylandi: () => void;
}) {
  const [ad, setAd] = useState("");
  const [tarih, setTarih] = useState(todayIso());
  const [uyeler, setUyeler] = useState("");
  const [imha, setImha] = useState(false);
  /** İmha kararının kapsamı DIŞINDA bırakılan hurdaya ayırma kalemleri (TMY 28/5 kalem düzeyinde). */
  const [imhaDisi, setImhaDisi] = useState<Record<number, boolean>>({});
  const [secili, setSecili] = useState<Record<number, boolean>>({});
  const [gerekceler, setGerekceler] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const hurda = kalemler.some((k) => k.tmy_path === "TMY_28");
  const kurumsuz = kalemler.filter((k) => k.is_transfer && !k.transfer_target.trim());
  // İmha kapsamına yalnız onaylanan (dışarıda bırakılmayan) hurdaya ayırma kalemleri girer.
  const hurdaKalemleri = kalemler.filter((k) => k.tmy_path === "TMY_28" && !secili[k.id]);
  const imhaKalemleri = hurdaKalemleri.filter((k) => !imhaDisi[k.id]).map((k) => k.id);

  const onayla = async () => {
    clearErrors();
    setHata(null);
    if (!ad.trim()) {
      setFieldError("approved_by_name", "Onaylayan harcama yetkilisinin adını yazın.");
      return;
    }
    const notApproved = gerekceEslemesi(secili, gerekceler);
    if (notApproved === null) {
      setFieldError("not_approved", "Onaylanmayan her kalemin gerekçesi yazılmalıdır.");
      return;
    }
    const imhaVar = hurda && imha;
    if (imhaVar && imhaKalemleri.length === 0) {
      setFieldError("destruction_items", "İmha kararının kapsadığı en az bir kalem seçilmelidir.");
      return;
    }
    setBusy(true);
    try {
      await ayiklamaApi.onayla(teklif.id, {
        approved_by_name: ad.trim(),
        approved_on: tarih,
        tmy_commission_members: uyeler.trim(),
        destruction_decided: imhaVar,
        destruction_items: imhaVar ? imhaKalemleri : null,
        not_approved: notApproved,
      });
      onOnaylandi();
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Onay işlenemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Harcama yetkilisinin onayı"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="approval" onClick={() => void onayla()} disabled={busy}>
            {busy ? "İşleniyor…" : "Onayı işle"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-small text-on-surface-variant">
          Kayıttan düşmeyi ve devri harcama yetkilisi onaylar (Taşınır Mal Yönetmeliği md. 10/1-e,
          28/4; devirde md. 24, 31). Onay, imzalı belgenin tarihiyle işlenir; nüshalar ancak
          “Uygula” ile kayıttan düşülür ya da devredilir.
        </p>
        {kurumsuz.length > 0 && (
          <p
            role="alert"
            className="rounded-shape-sm bg-error-container px-3 py-2 text-body-small text-on-error-container"
          >
            {`${formatNumber(kurumsuz.length)} devir kaleminin devralacak kurumu yazılmadı; önce kalem listesinden yazın.`}
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Harcama yetkilisinin adı"
            required
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            error={errors.approved_by_name}
            helperText="Şifreli saklanır."
          />
          <TextField
            label="Onay tarihi"
            required
            type="date"
            value={tarih}
            onChange={(e) => setTarih(e.target.value)}
            error={errors.approved_on}
            helperText="Komisyon kararının tarihinden önce ve bugünden sonra olamaz."
          />
        </div>
        <MetinAlani
          label="Komisyon üyeleri"
          value={uyeler}
          onChange={setUyeler}
          error={errors.tmy_commission_members}
          helperText={
            hurda
              ? "Hurdaya ayırma yolunda zorunludur: harcama yetkilisinin belirlediği, biri işin uzmanı en az üç kişi (TMY md. 28/1). İşin uzmanını ilk satıra yazın. Satır başına bir kişi; şifreli saklanır."
              : "İsteğe bağlı: durumu belgeleyen tutanak varsa harcama yetkilisi komisyon kurulmadan onaylayabilir (TMY md. 10/1-e); Ayıklama tutanağının bu tutanak sayılıp sayılmayacağını harcama yetkilisi değerlendirir. Satır başına bir kişi; şifreli saklanır."
          }
        />
        {hurda && (
          <div>
            <OnayKutusu
              etiket="İmha kararı verildi (TMY md. 28/5)"
              checked={imha}
              onChange={setImha}
            />
            <p className="text-body-small text-on-surface-variant">
              Komisyon, ekonomik değeri olmadığına ya da imha edilmesi gerektiğine karar verdiyse
              işaretleyin; İmha tutanağı yalnız imha kararının kapsadığı kalemleri basar. Ekonomik
              değeri olan hurda için 7330 sayılı Kanun uygulanır (TMY md. 28/8): o kalemi imha
              kararının kapsamından çıkarın.
            </p>
            {imha && hurdaKalemleri.length > 0 && (
              <div className="mt-2 space-y-1" aria-label="İmha kararının kapsadığı kalemler">
                <p className="text-label-large text-on-surface">
                  İmha kararının kapsadığı kalemler
                </p>
                {errors.destruction_items && (
                  <p role="alert" className="text-body-small text-error">
                    {errors.destruction_items}
                  </p>
                )}
                <ul className="space-y-1">
                  {hurdaKalemleri.map((k) => (
                    <li key={k.id}>
                      <OnayKutusu
                        etiket={`${k.barcode_display} — ${k.work_title}`}
                        checked={!imhaDisi[k.id]}
                        onChange={(d) => setImhaDisi((o) => ({ ...o, [k.id]: !d }))}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        <p className="text-body-small text-on-surface-variant">
          Harcama yetkilisinin onaylamadığı kalemi işaretleyin ve gerekçesini yazın; kalem kayıttan
          düşülmez ya da devredilmez.
        </p>
        <DisaridaBirakma
          kalemler={kalemler}
          etiket="Onaylanmadı"
          secili={secili}
          gerekceler={gerekceler}
          onSecim={(id, d) => setSecili((o) => ({ ...o, [id]: d }))}
          onGerekce={(id, m) => setGerekceler((o) => ({ ...o, [id]: m }))}
          hata={errors.not_approved}
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// İptal
// ---------------------------------------------------------------------------

export function IptalDiyalogu({
  teklifId,
  onClose,
  onIptal,
}: {
  teklifId: number;
  onClose: () => void;
  onIptal: () => void;
}) {
  const [gerekce, setGerekce] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);

  const iptalEt = async () => {
    setBusy(true);
    setHata(null);
    try {
      await ayiklamaApi.iptalEt(teklifId, gerekce.trim());
      onIptal();
    } catch (e) {
      setHata(hataOku(e, "Teklif iptal edilemedi."));
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Teklif iptal edilsin mi?"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="cancel" onClick={() => void iptalEt()} disabled={busy}>
            {busy ? "İptal ediliyor…" : "İptal et"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}
        <p className="text-body-medium text-on-surface">
          Teklif “İptal edildi” olarak kapanır; nüshalara dokunulmaz, kayıt kalır. İptal geri
          alınmaz.
        </p>
        <TextField
          label="İptal gerekçesi (isteğe bağlı)"
          value={gerekce}
          onChange={(e) => setGerekce(e.target.value)}
        />
      </div>
    </Dialog>
  );
}
