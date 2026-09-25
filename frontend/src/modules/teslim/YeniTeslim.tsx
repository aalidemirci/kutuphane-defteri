// Teslimler → Yeni Teslim (U11, tasarım §9-11). Sınıf kitaplığına (şube) ya da
// öğretmene toplu teslim — YALNIZ yönetici kipinde (§4.4 "Teslim verme" kapalı).
//
// Teslim ÖDÜNÇ DEĞİLDİR: Md. 18 sayı sınırı ve on beş günlük süre uygulanmaz; ekran
// sınır sormaz ve saymaz. Liste okutarak kurulur: her okutma sunucuda ön denetimden
// geçer (yazma yok) ve yalnız rafta duran kitap listeye girer. "Teslim et" TEK
// işlemdir: listedeki bir kitap bu arada teslim edilemez olduysa hiçbiri yapılmaz ve
// gerekçeler kitap kitap gösterilir.
//
// Teslim bir belge no alır (boş bırakılırsa program verir, numara tekrar verilmez)
// ve onaydan geçer (docs/sozluk.md §3: başlık soru, gövde sonuç). Teslimden sonra
// Teslim listesi (E15) basılır; şube tesliminde Dayanıklı Taşınırlar Listesi
// işlevini görür (TMY 23/6'ya kıyasen).
//
// Okuyucuyla hızlı okutmada reddedilen kitap sessizce kaybolmaz (F7 düzeltme turu):
// ileti kitabın barkodunu ve adını taşır, reddedilen kitaplar sonraki başarılı
// okutmada silinmeyen "Listeye girmeyen kitaplar" listesinde durur. Okutma kutusu
// odakta değilse (ör. "Şube" seçicisi) uyarı çıkar: seçicideki okutma kodu kaybolur
// ve şube seçimini değiştirebilir. Öğretmen seçilince odak kutuya döner.
//
// F9 (madde 27, 25.09.2026 kullanıcı kararı): sayım için hizmet arası yeni teslimi de
// durdurur. Sürerken ekranın üstünde masadakiyle aynı şerit durur ve "Teslim et" kapalıdır;
// ön denetim her okutmayı hizmet arasının iletisiyle reddeder. Teslimden geri alma açıktır.

import { useCallback, useEffect, useRef, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { ApiError } from "../../lib/api";
import { dosyaAdi } from "../../lib/download";
import { formatDate, formatNumber, todayIso } from "../../lib/format";
import Autocomplete from "../../ui/Autocomplete";
import BarcodeInput from "../../ui/BarcodeInput";
import type { OkutmaGeriBildirimi } from "../../ui/BarcodeInput";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import type { SelectOption } from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import type { MasaNushasi } from "../dolasim/api";
import { useMasaDurumu } from "../dolasim/masaDurumu";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { HizmetArasiSeridi } from "../sayim/SayimKarti";
import { okulApi } from "../okul/api";
import type { Personnel } from "../okul/api";
import { GERI_ALMA_DOKUMU_ADI, TESLIM_ALAN_TURU_TR, TESLIM_LISTESI_ADI, teslimApi } from "./api";
import type { TeslimAlanTuru, TeslimGovdesi, TeslimSonucu } from "./api";

export const TESLIM_KUTUSU = "Kütüphane etiketi";
export const TESLIM_ET_DUGMESI = "Teslim et";
export const ZATEN_LISTEDE = "Bu kitap zaten listede.";
export const LISTEYE_GIRMEYENLER = "Listeye girmeyen kitaplar";

/** Hizmet arası şeridinin teslim ekranındaki ipucu (madde 27). */
export const TESLIM_HIZMET_ARASI_IPUCU =
  "Sayım onaylanınca ya da iptal edilince teslim yeniden açılır. Dönen kitapları Geri Alma sekmesinde okutun.";

/** Öğretmen seçicisinde diğer personelin gerekçesi (sunucu da reddeder). */
export const DIGER_PERSONEL_GEREKCESI = "diğer personele teslim yapılmaz";

interface Satir {
  kod: string;
  nusha: MasaNushasi;
}

/** Reddedilen okutma: kitabın kimliği (barkod + ad) ve sunucunun gerekçesi. */
interface Ret {
  barkod: string;
  metin: string;
}

/** Okutma iletisi: nüsha biliniyorsa "2026-000123 — Kaynak adı: gerekçe". */
export function okutmaIletisi(nusha: MasaNushasi | null, ileti: string): string {
  return nusha ? `${nusha.barcode_display} — ${nusha.work_title}: ${ileti}` : ileti;
}

/** Belge no'lu dosya adı: bölü dosya adında yasaktır ("2026/7" → "2026-7"). */
export function belgeDosyaAdi(belgeNo: string, tarih: string): string {
  return dosyaAdi([TESLIM_LISTESI_ADI, belgeNo.replace(/\//g, "-"), formatDate(tarih)], "pdf");
}

/** Belge no'lu geri alma dökümünün dosya adı (basım günüyle). */
export function dokumDosyaAdi(belgeNo: string): string {
  return dosyaAdi(
    [GERI_ALMA_DOKUMU_ADI, belgeNo.replace(/\//g, "-"), formatDate(todayIso())],
    "pdf",
  );
}

/** Etkin ders yılının şubeleri (teslim yalnız etkin yılın şubesine yapılır). */
function useEtkinSubeler(): { secenekler: SelectOption[]; etiketler: Map<string, string> } {
  const [secenekler, setSecenekler] = useState<SelectOption[]>([]);
  useEffect(() => {
    let iptal = false;
    okulApi
      .listSchoolYears()
      .then(async (yillar) => {
        const etkin = yillar.find((y) => y.is_active);
        if (etkin === undefined) return [];
        return okulApi.listClassSections(etkin.id);
      })
      .then((subeler) => {
        if (!iptal)
          setSecenekler(subeler.map((s) => ({ value: String(s.id), label: s.class_label })));
      })
      .catch(() => {
        if (!iptal) setSecenekler([]);
      });
    return () => {
      iptal = true;
    };
  }, []);
  return { secenekler, etiketler: new Map(secenekler.map((s) => [s.value, s.label])) };
}

export default function YeniTeslim({
  beklemede = false,
  onTeslimEdildi,
}: {
  beklemede?: boolean;
  /** Teslim yapıldı (kayıtlar sekmesi tazelensin). */
  onTeslimEdildi?: (sonuc: TeslimSonucu) => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const { secenekler: subeler, etiketler: subeEtiketleri } = useEtkinSubeler();
  const [alanTuru, setAlanTuru] = useState<TeslimAlanTuru>("SECTION");
  const [sube, setSube] = useState("");
  const [ogretmen, setOgretmen] = useState<Personnel | null>(null);
  const [teslimTarihi, setTeslimTarihi] = useState(todayIso());
  const [donus, setDonus] = useState("");
  const [belgeNo, setBelgeNo] = useState("");
  const [liste, setListe] = useState<Satir[]>([]);
  const listeRef = useRef<Satir[]>([]);
  const [sonOkutma, setSonOkutma] = useState<{ ileti: string; tur: "uyari" | "hata" } | null>(null);
  // Reddedilen kitaplar: sonraki başarılı okutma silmez (yalnız aynı kitap listeye
  // girerse ya da liste boşaltılınca/teslim yapılınca çıkar).
  const [girmeyenler, setGirmeyenler] = useState<Ret[]>([]);
  const kutuRef = useRef<HTMLInputElement>(null);
  const [retler, setRetler] = useState<string[]>([]);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [busy, setBusy] = useState(false);
  const [sonuc, setSonuc] = useState<TeslimSonucu | null>(null);
  const [pdfHatasi, setPdfHatasi] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError, setFieldError } = useFormErrors();
  // F9 (madde 27): sayım için hizmet arası sürerken yeni teslim yapılmaz (kural sunucudadır).
  const hizmetArasi = useMasaDurumu()?.service_pause ?? false;

  const listeyiYaz = useCallback((yeni: Satir[]) => {
    listeRef.current = yeni;
    setListe(yeni);
  }, []);

  /** Tek okutma — ön denetim (yazma yok); listede olan kitap ikinci kez girmez. */
  const okut = async (kod: string): Promise<OkutmaGeriBildirimi> => {
    setRetler([]);
    try {
      const d = await teslimApi.denetle(kod);
      if (d.result !== "deliverable" || d.copy === null) {
        const metin = okutmaIletisi(d.copy, d.message);
        setSonOkutma({ ileti: metin, tur: "hata" });
        const reddedilen = d.copy;
        if (reddedilen !== null) {
          setGirmeyenler((onceki) => [
            ...onceki.filter((r) => r.barkod !== reddedilen.barcode),
            { barkod: reddedilen.barcode, metin },
          ]);
        }
        return "hata";
      }
      const nusha = d.copy;
      if (listeRef.current.some((s) => s.nusha.barcode === nusha.barcode)) {
        setSonOkutma({ ileti: `${nusha.barcode_display}: ${ZATEN_LISTEDE}`, tur: "uyari" });
        return "uyari";
      }
      listeyiYaz([...listeRef.current, { kod, nusha }]);
      setGirmeyenler((onceki) => onceki.filter((r) => r.barkod !== nusha.barcode));
      setSonOkutma(null);
      return "basari";
    } catch (e) {
      setSonOkutma({
        ileti: hataOku(e, "Kitap denetlenemedi; yeniden okutun.").message,
        tur: "hata",
      });
      return "hata";
    }
  };

  const cikar = (barkod: string) =>
    listeyiYaz(listeRef.current.filter((s) => s.nusha.barcode !== barkod));

  const listeyiBosalt = async () => {
    const onay = await confirm({
      title: "Liste boşaltılsın mı?",
      message: `Okutulan ${formatNumber(listeRef.current.length)} kitap listeden çıkar; teslim yapılmaz.`,
      confirmLabel: "Boşalt",
    });
    if (onay) {
      listeyiYaz([]);
      setSonOkutma(null);
      setRetler([]);
      setGirmeyenler([]);
    }
  };

  const alanEtiketi =
    alanTuru === "SECTION"
      ? `${subeEtiketleri.get(sube) ?? ""} sınıf kitaplığına`
      : `${ogretmen?.full_name ?? ""} adlı öğretmene`;

  const teslimEt = async () => {
    clearErrors();
    setHata(null);
    setRetler([]);
    if (alanTuru === "SECTION" && !sube) {
      setFieldError("section_id", "Şube seçin.");
      return;
    }
    if (alanTuru === "TEACHER" && ogretmen === null) {
      setFieldError("personnel_id", "Öğretmen seçin.");
      return;
    }
    if (liste.length === 0) {
      setHata({ message: "Teslim edilecek kitap okutulmadı.", parolaGerekli: false });
      return;
    }
    const onay = await confirm({
      title: `${formatNumber(liste.length)} kitap ${alanEtiketi} teslim edilsin mi?`,
      message:
        "Kitaplar “Sınıf kitaplığında” görünür ve geri alınana kadar ödünç verilmez. Teslime " +
        "bir belge no verilir; teslim listesi bu numarayla basılır. Geri alma, kitaplar " +
        "okutularak yapılır.",
      confirmLabel: TESLIM_ET_DUGMESI,
    });
    if (!onay) return;
    const govde: TeslimGovdesi = {
      barcodes: liste.map((s) => s.nusha.barcode),
      delivered_on: teslimTarihi || undefined,
      expected_return: donus || null,
      document_no: belgeNo.trim(),
    };
    if (alanTuru === "SECTION") govde.section_id = Number(sube);
    else if (ogretmen !== null) govde.personnel_id = ogretmen.id;
    setBusy(true);
    try {
      const yeni = await teslimApi.teslimEt(govde);
      setSonuc(yeni);
      listeyiYaz([]);
      setSonOkutma(null);
      setGirmeyenler([]);
      snackbar.success(`${formatNumber(yeni.count)} kitap teslim edildi.`);
      onTeslimEdildi?.(yeni);
    } catch (e) {
      applyApiError(e);
      const kitaplar = e instanceof ApiError ? e.fields.barcodes : undefined;
      if (Array.isArray(kitaplar) && kitaplar.length > 0) {
        setRetler(kitaplar.map(String));
        setHata({
          message: "Listedeki bazı kitaplar teslim edilemiyor; hiçbir teslim yapılmadı.",
          parolaGerekli: false,
        });
      } else {
        setHata(hataOku(e, "Teslim yapılamadı."));
      }
    } finally {
      setBusy(false);
    }
  };

  const yeniTeslim = () => {
    setSonuc(null);
    setBelgeNo("");
    setDonus("");
    setTeslimTarihi(todayIso());
    setPdfHatasi(null);
  };

  if (sonuc !== null) {
    return (
      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <div role="status" className="flex items-start gap-3">
          <Icon name="check_circle" size="2xl" className="shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="text-title-medium text-on-surface">
              {formatNumber(sonuc.count)} kitap teslim edildi.
            </p>
            <p className="text-body-medium text-on-surface-variant">
              {sonuc.recipient_kind_display}: {sonuc.recipient_label} · belge no {sonuc.document_no}{" "}
              · teslim {formatDate(sonuc.delivered_on)}
              {sonuc.expected_return && ` · beklenen dönüş ${formatDate(sonuc.expected_return)}`}
            </p>
          </div>
        </div>
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          Teslim listesini basıp teslim alana imzalatın ve saklayın. Kitaplar dönünce Teslimler →
          Geri Alma sekmesinde okutulur.
        </p>
        {pdfHatasi && <ErrorBand hata={pdfHatasi} />}
        <div className="flex flex-wrap gap-2">
          <PdfDugmeleri
            pdfAl={() => teslimApi.teslimListesiPdf(sonuc.document_no)}
            dosyaAdi={() => belgeDosyaAdi(sonuc.document_no, sonuc.delivered_on)}
            onizlemeBasligi={TESLIM_LISTESI_ADI}
            onHata={setPdfHatasi}
          />
          <Button variant="text" icon="add" onClick={yeniTeslim}>
            Yeni teslim
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {hizmetArasi && <HizmetArasiSeridi ipucu={TESLIM_HIZMET_ARASI_IPUCU} />}
      <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Teslim Alan</p>
        <fieldset className="flex flex-wrap gap-4">
          <legend className="sr-only">Teslim alanın türü</legend>
          {(Object.keys(TESLIM_ALAN_TURU_TR) as TeslimAlanTuru[]).map((k) => (
            <label
              key={k}
              className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface"
            >
              <input
                type="radio"
                name="teslim-alan-turu"
                value={k}
                checked={alanTuru === k}
                onChange={() => {
                  setAlanTuru(k);
                  clearErrors();
                }}
                className="size-5 accent-primary"
              />
              {TESLIM_ALAN_TURU_TR[k]}
            </label>
          ))}
        </fieldset>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {alanTuru === "SECTION" ? (
            <Select
              label="Şube"
              required
              placeholder="Seçin"
              value={sube}
              onChange={(e) => setSube(e.target.value)}
              options={subeler}
              error={errors.section_id}
              helperText={
                subeler.length === 0
                  ? "Etkin ders yılının şubesi yok. Şubeleri Ayarlar → Şubeler'den ekleyin."
                  : "Yalnız etkin ders yılının şubeleri."
              }
            />
          ) : (
            <Autocomplete<Personnel>
              label="Öğretmen"
              required
              placeholder="Ad ya da soyad"
              selected={ogretmen}
              search={async (q) =>
                (await okulApi.listPersonnel({ search: q, onlyActive: true, limit: 20 })).results
              }
              onSelect={(p) => {
                setOgretmen(p);
                // Seçimden sonra okutma kutuya düşsün (arama kutusuna değil).
                kutuRef.current?.focus();
              }}
              onClear={() => setOgretmen(null)}
              getLabel={(p) => p.full_name}
              getKey={(p) => p.id}
              getDisabled={(p) =>
                p.member_kind === "TEACHER" ? undefined : DIGER_PERSONEL_GEREKCESI
              }
              emptyText="Aktif öğretmen bulunamadı."
              error={errors.personnel_id}
            />
          )}
          <TextField
            label="Teslim tarihi"
            type="date"
            value={teslimTarihi}
            max={todayIso()}
            onChange={(e) => setTeslimTarihi(e.target.value)}
            error={errors.delivered_on}
          />
          <TextField
            label="Beklenen dönüş (isteğe bağlı)"
            type="date"
            value={donus}
            onChange={(e) => setDonus(e.target.value)}
            error={errors.expected_return}
            helperText="Boş bırakılırsa ders yılının son günü yazılır. Gecikme sayılmaz; bilgi içindir."
          />
          <TextField
            label="Belge no (isteğe bağlı)"
            value={belgeNo}
            onChange={(e) => setBelgeNo(e.target.value)}
            error={errors.document_no}
            helperText="Boş bırakın, program yeni numara verir. Kullanılmış numara yeniden verilmez."
          />
        </div>
      </Card>

      <Card elevation={0} className="space-y-3 p-[var(--kd-panel-padding)] shadow-elevation-1">
        <p className="text-title-medium text-on-surface">Teslim Edilecek Kitaplar</p>
        <p className="max-w-4xl text-body-medium text-on-surface-variant">
          Kitapların kütüphane etiketini okutun; rafta duran her kitap listeye girer. Teslim ödünç
          değildir: sayı sınırı yoktur ve kitaplar teslim alanın ödünç hakkından düşmez.
        </p>
        <BarcodeInput
          ref={kutuRef}
          className="max-w-xl"
          label={TESLIM_KUTUSU}
          onOkut={okut}
          beklemede={beklemede || busy}
          placeholder="2026-000123"
          helperText="Okuyucuyla okutun ya da numarayı yazıp Enter'a basın."
        />
        {sonOkutma && (
          <p
            role="status"
            className={`flex items-start gap-2 rounded-shape-sm px-3 py-2 text-body-medium ${
              sonOkutma.tur === "hata"
                ? "bg-error-container text-on-error-container"
                : "bg-tertiary-container text-on-tertiary-container"
            }`}
          >
            <Icon name={sonOkutma.tur === "hata" ? "error" : "warning"} size="lg" />
            {sonOkutma.ileti}
          </p>
        )}

        {girmeyenler.length > 0 && (
          <div className="space-y-1 rounded-shape-sm bg-error-container/40 px-3 py-2">
            <p className="text-title-small text-on-surface">
              {LISTEYE_GIRMEYENLER} ({formatNumber(girmeyenler.length)})
            </p>
            <ul aria-label={LISTEYE_GIRMEYENLER} className="list-disc space-y-1 pl-6">
              {girmeyenler.map((r) => (
                <li key={r.barkod} className="text-body-medium text-on-surface">
                  {r.metin}
                </li>
              ))}
            </ul>
          </div>
        )}

        {hata && <ErrorBand hata={hata} />}
        {retler.length > 0 && (
          <ul aria-label="Teslim edilemeyen kitaplar" className="list-disc space-y-1 pl-6">
            {retler.map((r) => (
              <li key={r} className="text-body-medium text-error">
                {r}
              </li>
            ))}
          </ul>
        )}

        <p className="text-body-medium text-on-surface">
          Listede {formatNumber(liste.length)} kitap
        </p>
        {liste.length > 0 && (
          <ol
            aria-label="Teslim listesi"
            className="divide-y divide-outline-variant/60 rounded-shape-sm border border-outline-variant/70"
          >
            {liste.map((s, i) => (
              <li
                key={s.nusha.barcode}
                className="flex items-center justify-between gap-3 px-3 py-2"
              >
                <span className="min-w-0 text-body-medium text-on-surface">
                  <span className="mr-2 text-on-surface-variant">{i + 1}.</span>
                  <span className="font-mono">{s.nusha.barcode_display}</span> —{" "}
                  {s.nusha.work_title}
                </span>
                <Button
                  variant="text"
                  icon="close"
                  onClick={() => cikar(s.nusha.barcode)}
                  aria-label={`${s.nusha.barcode_display} listeden çıkar`}
                >
                  Çıkar
                </Button>
              </li>
            ))}
          </ol>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          {liste.length > 0 && (
            <Button variant="text" onClick={() => void listeyiBosalt()} disabled={busy}>
              Listeyi boşalt
            </Button>
          )}
          <Button
            icon="outbox"
            onClick={() => void teslimEt()}
            disabled={busy || liste.length === 0 || hizmetArasi}
          >
            {busy ? "Teslim ediliyor…" : TESLIM_ET_DUGMESI}
          </Button>
        </div>
      </Card>
    </div>
  );
}
