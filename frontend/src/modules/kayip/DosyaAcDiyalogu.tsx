// Kayıp bildirimi ve hasar dosyası açma penceresi (Md. 19, D3; tasarım §9-9).
//
// Dört yerden açılır ve her yerde aynı pencere durur: Kayıp ve Hasar sayfası
// (kitap okutularak), Dolaşım Masası'nda üyenin açık ödünçleri (yalnız yönetici
// kipi), Teslimler listesindeki açık teslim ve Eser Ayrıntısı'ndaki nüsha. Nüsha
// önceden seçilmişse okutma kutusu çıkmaz.
//
// Pencere onay diyaloğunun kuralını taşır (docs/sozluk.md §3): başlık SORU, gövde
// SONUÇtur. Kayıp bildirimi geri alınamaz: ödünç ya da teslim "Kayba dönüştü" ile
// kapanır ve "Bulundu" onu yeniden açmaz.
//
// Nüshanın durumu masa durum sorgusundan okunur (yazma yok): ödünçteki kitapta
// sorumlu ödünçten gelir, pencere üye seçtirmez (sunucu farklı üyeyi reddeder).
// Program tahsilat yapmaz ve disiplin süreci başlatmaz; pencerede borç, ceza ya da
// bedel dili yoktur — bedel, dosyanın çözüm adımında ve yalnız ortaöğretimde sorulur.

import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { formatDate, todayIso } from "../../lib/format";
import Autocomplete from "../../ui/Autocomplete";
import BarcodeInput from "../../ui/BarcodeInput";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import TextField from "../../ui/TextField";
import { dolasimApi } from "../dolasim/api";
import type { NushaDurumu, UyeAramaSatiri } from "../dolasim/api";
import { MetinAlani } from "../kutuphane/ortak";
import { SORUMLU_NOTU_YARDIMI, kayipApi } from "./api";
import type { Dosya, DosyaGovdesi, DosyaTuru } from "./api";

/** Önceden seçilmiş nüsha (masa, teslim listesi, eser ayrıntısı). */
export interface SeciliNusha {
  /** Nüsha kimliği biliniyorsa `copy_id` ile gönderilir; yoksa barkodla. */
  id?: number;
  barcode: string;
  barcode_display: string;
  work_title: string;
}

export const KAYIP_BASLIGI = "Kayıp bildirilsin mi?";
export const HASAR_BASLIGI = "Hasar dosyası açılsın mı?";
export const KAYIP_DUGMESI = "Kayıp bildir";
export const HASAR_DUGMESI = "Hasar dosyası aç";

export const KAYIP_SONUCU =
  "Nüsha “Kayıp” olarak işaretlenir ve kayıp dosyası açılır. Kitap ödünçteyse ödünç, " +
  "teslimdeyse teslim “Kayba dönüştü” olarak kapanır; kitabın çözülmemiş hasar dosyası " +
  "varsa o dosya da “Kayba dönüştü” olarak kapanır. Kitap sonradan bulunursa dosyada " +
  "“Bulundu” seçilir; kapanan ödünç ya da teslim yeniden açılmaz.";
/**
 * Teslimdeki kitapta sorumlu üye alanının yardımı: dosyanın kişisi ÖNCE üyeliktir
 * (sunucu `selectors_teslim.case_person`; kayıt defteri, ilişik listesi ve belge aynı
 * kuralı uygular).
 */
export const TESLIMDE_SORUMLU_YARDIMI =
  "Üye seçerseniz dosya o üyeye bağlanır; boş bırakırsanız teslim alana (öğretmene ya da " +
  "sınıf kitaplığına).";
export const HASAR_SONUCU =
  "Hasar dosyası açılır; nüsha dolaşımdan çıkmaz. Kitap okunamayacak durumdaysa onarıma " +
  "gönderin. Ödünçteki kitap için önce iade alın, teslimdeki kitabı önce geri alın.";

/** Pencereyi açan ekranın başarı iletisi (pencere kendisi snackbar göstermez). */
export function dosyaAcildiIletisi(tur: DosyaTuru): string {
  return tur === "LOST" ? "Kayıp bildirildi; kayıp dosyası açıldı." : "Hasar dosyası açıldı.";
}

/** Okutulan (ya da seçilen) nüshanın masa durum sorgusu sonucu. */
type Durum = { durum: NushaDurumu; kod: string } | null;

export default function DosyaAcDiyalogu({
  open,
  tur,
  nusha = null,
  onClose,
  onAcildi,
}: {
  open: boolean;
  tur: DosyaTuru;
  nusha?: SeciliNusha | null;
  onClose: () => void;
  onAcildi: (dosya: Dosya) => void;
}) {
  const formId = useId();
  const kutuRef = useRef<HTMLInputElement>(null);
  const [kod, setKod] = useState("");
  const [durum, setDurum] = useState<Durum>(null);
  const [tarih, setTarih] = useState(todayIso());
  const [uye, setUye] = useState<UyeAramaSatiri | null>(null);
  const [not, setNot] = useState("");
  const [onarima, setOnarima] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError, setFieldError } = useFormErrors();
  const kayip = tur === "LOST";

  // Pencere her açılışta boş başlar; önceden seçilmiş nüshanın durumu okunur.
  useEffect(() => {
    if (!open) return;
    setKod("");
    setDurum(null);
    setTarih(todayIso());
    setUye(null);
    setNot("");
    setOnarima(false);
    setHata(null);
    clearErrors();
    if (nusha === null) return;
    let iptal = false;
    dolasimApi
      .nushaDurumu(nusha.barcode)
      .then((d) => {
        if (!iptal) setDurum({ durum: d, kod: nusha.barcode });
      })
      .catch(() => {
        // Durum okunamadıysa pencere yine çalışır: sunucu dosyayı açarken denetler.
      });
    return () => {
      iptal = true;
    };
    // `nusha` nesnesi her çizimde yeniden kurulabilir; barkodu yeter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, nusha?.barcode, clearErrors]);

  const okut = async () => {
    const deger = kod.trim();
    if (!deger) return;
    setHata(null);
    clearErrors();
    try {
      const d = await dolasimApi.nushaDurumu(deger);
      if (d.copy === null) {
        setDurum(null);
        setFieldError("barcode", d.message);
        return;
      }
      setDurum({ durum: d, kod: deger });
    } catch (e) {
      setDurum(null);
      setHata(hataOku(e, "Nüsha okunamadı; etiketi yeniden okutun."));
    }
  };

  const kopya = durum?.durum.copy ?? null;
  const odunc = durum?.durum.loan ?? null;
  const durumKodu = kopya?.status;
  // Ödünçteki kitapta sorumlu ödünçten gelir (sunucu başka üyeyi reddeder).
  const uyeSorulur = !(kayip && odunc);

  const gonder = async (e: FormEvent) => {
    e.preventDefault();
    clearErrors();
    setHata(null);
    const govde: DosyaGovdesi = { case_type: tur, reported_on: tarih || undefined };
    if (nusha?.id !== undefined) govde.copy_id = nusha.id;
    else if (kopya?.id !== undefined) govde.copy_id = kopya.id;
    else if (nusha !== null) govde.barcode = nusha.barcode;
    else if (durum !== null) govde.barcode = durum.kod;
    else {
      setFieldError("barcode", "Önce kitabın kütüphane etiketini okutun.");
      return;
    }
    if (uyeSorulur && uye !== null) govde.membership_id = uye.id;
    if (not.trim()) govde.responsible_note = not.trim();
    if (!kayip && onarima) govde.send_to_repair = true;
    setBusy(true);
    try {
      onAcildi(await kayipApi.ac(govde));
    } catch (err) {
      applyApiError(err);
      setHata(hataOku(err, kayip ? "Kayıp bildirilemedi." : "Hasar dosyası açılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const gosterilen = nusha ?? (kopya ? { ...kopya } : null);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={kayip ? KAYIP_BASLIGI : HASAR_BASLIGI}
      wide
      initialFocusRef={nusha === null ? kutuRef : undefined}
      actions={
        <>
          <Button variant="text" type="button" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            form={formId}
            icon={kayip ? "report" : "healing"}
            disabled={busy || (nusha === null && durum === null)}
          >
            {busy ? "Kaydediliyor…" : kayip ? KAYIP_DUGMESI : HASAR_DUGMESI}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="space-y-4">
        <p className="text-body-medium text-on-surface">{kayip ? KAYIP_SONUCU : HASAR_SONUCU}</p>
        {hata && <ErrorBand hata={hata} />}

        {nusha === null && (
          <BarcodeInput
            ref={kutuRef}
            davranis="alan"
            kendiliginden={false}
            className="max-w-xl"
            label="Kütüphane etiketi"
            value={kod}
            onValueChange={setKod}
            onOkut={() => okut()}
            error={errors.barcode ?? errors.copy_id}
            placeholder="2026-000123"
            helperText="Kitabın kütüphane etiketini okutun ya da numarayı yazıp Enter'a basın."
          />
        )}

        {gosterilen && (
          <section
            aria-label="Nüsha"
            className="rounded-shape-sm bg-surface-container px-4 py-3 text-body-medium text-on-surface"
          >
            <p className="text-title-small">
              {gosterilen.barcode_display} — {gosterilen.work_title}
            </p>
            {kopya?.status_display && (
              <p className="text-on-surface-variant">Durum: {kopya.status_display}</p>
            )}
            {odunc && (
              <p className="text-on-surface-variant">
                Ödünç alan: {[odunc.member_name, odunc.class_label].filter(Boolean).join(" · ")} ·
                iade tarihi {formatDate(odunc.due_date)}
              </p>
            )}
          </section>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Tespit tarihi"
            type="date"
            value={tarih}
            max={todayIso()}
            onChange={(e) => setTarih(e.target.value)}
            error={errors.reported_on}
          />
          {uyeSorulur ? (
            <Autocomplete<UyeAramaSatiri>
              label="Sorumlu üye (isteğe bağlı)"
              placeholder="Okul no ya da ad"
              selected={uye}
              search={async (q) => (await dolasimApi.uyeAra(q)).results}
              onSelect={setUye}
              onClear={() => setUye(null)}
              getLabel={(u) => u.full_name}
              getSublabel={(u) =>
                [u.member_type_display, u.class_label].filter(Boolean).join(" · ")
              }
              getKey={(u) => u.id}
              emptyText="Aktif üyeliği olan kişi bulunamadı."
              error={errors.membership_id}
              helperText={
                kayip && durumKodu === "DELIVERED"
                  ? TESLIMDE_SORUMLU_YARDIMI
                  : "Üye değilse ya da bilinmiyorsa boş bırakın; gerekirse sorumlu notuna yazın."
              }
            />
          ) : (
            <p className="self-end text-body-small text-on-surface-variant">
              Sorumlu, kitabı ödünç alan üyedir; ödünç kaydından belirlenir.
            </p>
          )}
        </div>

        <MetinAlani
          label="Sorumlu notu (isteğe bağlı)"
          value={not}
          onChange={setNot}
          rows={2}
          helperText={SORUMLU_NOTU_YARDIMI}
          error={errors.responsible_note}
        />

        {!kayip &&
          (durumKodu === "IN_REPAIR" ? (
            <p className="text-body-small text-on-surface-variant">
              Nüsha onarımda; açık onarım kaydı bu dosyaya bağlanır.
            </p>
          ) : (
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
              <input
                type="checkbox"
                checked={onarima}
                onChange={(e) => setOnarima(e.target.checked)}
                className="size-5 shrink-0 accent-primary"
              />
              Nüshayı onarıma da gönder
            </label>
          ))}
      </form>
    </Dialog>
  );
}
