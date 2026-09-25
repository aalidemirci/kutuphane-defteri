// Kayıp/hasar dosyasının ayrıntısı ve çözüm adımları (Md. 19; tasarım §9-9, D3).
//
// ÇÖZÜM DÜĞMELERİ YALNIZ SUNUCUNUN LİSTESİNDEN kurulur (`allowed_resolutions`):
// Md. 19 kademe kapısı sunucudadır. İlkokul ve ortaokulda bedel yolları listede
// hiç yoktur; ekran bunun sebebini söyler ama kademeyi kendisi yorumlamaz.
//
// Her çözüm onaydan geçer (docs/sozluk.md §3: başlık soru, gövde sonuç). Onay AYRI
// bir pencere değildir: pencere onay kipine geçer — başlığı soru olur, gövdesi
// sonucu anlatır, bedel yollarında piyasa bedeli sorulur. Böylece iki pencere üst
// üste açılmaz (Esc ikisini birden kapatmaz). Kapanan dosya yeniden açılmaz; TEK
// istisna sunucunun listesinden gelir: kayıttan düşme önerisiyle kapanmış kayıp
// dosyasında nüsha hâlâ "Kayıp"sa kitap bulununca "Bulundu" ("Bedelle başka eser
// alındı"dan "Bulundu (bedel teslim alınmıştı)") — öneri geri alınır, nüsha rafa döner.
// Nüsha kayıttan düşülmüşse kitap yeni nüsha olarak alınır; pencere yolu söyler.
//
// Bedelden sonra bulunan kitap (25.09.2026 kullanıcı kararı, tasarım F8 ekleri 14): "Bedel
// teslim alındı" dosyasında da "Bulundu (bedel teslim alınmıştı)" durur. İki durumda da
// pencere bedelin iadesinin okul yönetiminin kararı olduğunu tek cümleyle söyler
// (`BEDEL_IADESI_NOTU`); program para tutmaz.
//
// Program TAHSİLAT YAPMAZ ve disiplin süreci başlatmaz: bedel yalnız kaydedilir
// (sözlük "bedel belirlendi", "bedel teslim alındı" — asla borç, ceza ya da tahsilat).
// Bedel iki adımdır (25.09.2026 kullanıcı kararı): "Bedel belirlendi"de kişinin açık
// işi sürer; "Bedel teslim alındı"da biter ve dosya okul için açık kalır (pencere bunu
// `OKULUN_ACIK_ISI_NOTU` ile söyler). "Kayıttan düşme" burada yalnız ÖNERİdir;
// nüshanın durumu değişmez.

import { useEffect, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { dosyaAdi } from "../../lib/download";
import { formatDate, formatDateTime, formatPrice } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { PdfDugmeleri } from "../kutuphane/etiketOrtak";
import { MetinAlani } from "../kutuphane/ortak";
import { BEDEL_SORULAN, SORUMLU_NOTU_YARDIMI, TUTANAK_ADI, kayipApi } from "./api";
import type { Cozum, Dosya } from "./api";

/** Bedel seçenekleri sunulmayan okulda dosyada görünen açıklama (Md. 19). */
export const BEDEL_YOK_NOTU =
  "Bedel seçenekleri yalnız ortaöğretim okullarında sunulur (Yönetmelik Md. 19). Okulun " +
  "kademesi Ayarlar → Okul Bilgileri'nde seçilir.";

/** "Bedel teslim alındı" dosyasında görünen açıklama: kişinin işi bitti, dosya okulun işi. */
export const OKULUN_ACIK_ISI_NOTU =
  "Bedel teslim alındı: kişinin kütüphaneyle açık işi kalmadı; İlişik Listesi'nde görünmez ve " +
  "“Kütüphaneden ilişiği yoktur” belgesi basılabilir. Dosya okulun açık işi olarak kalır; " +
  "bedelle alınan kaynak kaydedilince kapanır.";

/** Öneriyle kapanmış kayıp dosyasında "Bulundu" düğmesinin üstündeki açıklama. */
export const ONERI_GERI_ALMA_NOTU =
  "Kayıttan düşme yalnız önerildi; nüsha hâlâ “Kayıp”. Kitap bulunduysa “Bulundu” seçin: " +
  "öneri geri alınır ve nüsha rafa döner.";

/** "Bedelle başka eser alındı" ile kapanmış kayıp dosyasında bulunma düğmesinin açıklaması. */
export const BEDELLI_ONERI_GERI_ALMA_NOTU =
  "Kayıttan düşme yalnız önerildi; nüsha hâlâ “Kayıp”. Kitap bulunduysa “Bulundu (bedel teslim " +
  "alınmıştı)” seçin: öneri geri alınır ve nüsha rafa döner; bedelle alınan eser kayıtta kalır.";

/** Bedel teslim alındıktan sonra bulunan kitapta (F8 ekleri 14) — tek cümle. */
export const BEDEL_IADESI_NOTU =
  "Teslim alınan bedelin kişiye iadesi ya da başka kaynak alımında kullanılması okul " +
  "yönetiminin kararıdır; program para tutmaz.";

/** Öneriyle kapanmış kayıp dosyasının nüshası kayıttan düşülmüşse (sayım) bulunan kitabın yolu. */
export const KAYITTAN_DUSULMUS_NOTU =
  "Nüsha kayıttan düşülmüş; kitap bulunursa bu dosyadan rafa dönmez. Kitabı “Sayım fazlası " +
  "(kayda giriş)” yoluyla açılan bir edinimle, Eser Ayrıntısı'nda “Nüsha ekle” diyerek yeni " +
  "nüsha olarak kaydedin.";

/** Öneriyle kapanan çözümler (sunucu `WRITE_OFF_RESOLUTIONS`). */
const ONERI_COZUMLERI: ReadonlySet<Cozum> = new Set<Cozum>([
  "CLOSED_OTHER_REPURCHASED",
  "WRITE_OFF_PROPOSED",
]);

/** Çözümün sonucu — onay penceresinin gövdesi (dosya türüne ve açıklığına göre). */
export function cozumSonucu(
  cozum: Cozum,
  dosya: Pick<Dosya, "case_type"> & Partial<Pick<Dosya, "is_open">>,
): string {
  const kayip = dosya.case_type === "LOST";
  if (cozum === "FOUND_RETURNED" && dosya.is_open === false) {
    return (
      "Kayıttan düşme önerisi geri alınır: nüsha rafa döner ve dosya “Bulundu” olarak " +
      "kapanır. Kayba dönüşen ödünç ya da teslim yeniden açılmaz."
    );
  }
  if (cozum === "FOUND_AFTER_PRICE" && dosya.is_open === false) {
    return (
      "Kayıttan düşme önerisi geri alınır: nüsha rafa döner ve dosya “Bulundu (bedel teslim " +
      "alınmıştı)” olarak kapanır. Bedelle alınan eser kayıtta kalır; kaydedilen bedel dosyada " +
      `kalır. ${BEDEL_IADESI_NOTU}`
    );
  }
  switch (cozum) {
    case "PRICE_DETERMINED":
      return (
        "O günkü piyasa bedeli dosyaya kaydedilir. Dosya açık kalır ve kişinin kütüphaneyle " +
        "açık işi sürer: İlişik Listesi'nde kalır. Program tahsilat yapmaz; bedel yalnız " +
        "kayıttır. Bedel kişiden teslim alınınca “Bedel teslim alındı” seçilir."
      );
    case "PRICE_RECEIVED":
      return (
        "Bedelin kişiden teslim alındığı kaydedilir. Kişinin kütüphaneyle açık işi biter: " +
        "İlişik Listesi'nden çıkar ve “Kütüphaneden ilişiği yoktur” belgesi basılabilir. " +
        "Dosya okul için açık kalır; kaynak bedelle alınınca “Bedelle aynısı alındı” ya da " +
        "“Bedelle başka eser alındı” seçilir" +
        (kayip ? ", kitap bulunursa “Bulundu (bedel teslim alınmıştı)”. " : ". ") +
        "Program tahsilat yapmaz, yalnız kaydeder. Bu adım geri alınmaz ve kaydedilen bedel " +
        "artık değişmez."
      );
    case "FOUND_RETURNED":
      return (
        "Nüsha rafa döner ve dosya kapanır. Kayba dönüşen ödünç ya da teslim yeniden " +
        "açılmaz. Kapanan dosya yeniden açılmaz."
      );
    case "FOUND_AFTER_PRICE":
      return (
        "Kitap bulundu: nüsha rafa döner ve dosya kapanır; kaydedilen bedel ve teslim tarihi " +
        `dosyada kalır. ${BEDEL_IADESI_NOTU} Kayba dönüşen ödünç ya da teslim yeniden açılmaz.`
      );
    case "REPLACED_SAME":
      return kayip
        ? "Kaynağın aynısı temin edildi: nüsha rafa döner ve dosya kapanır. Yeni kitaba " +
            "nüshanın etiketini Etiketler ekranından yeniden basın."
        : "Kaynağın aynısı temin edildi: nüsha onarımdaysa onarım kaydı kapanır ve nüsha " +
            "rafa döner; dosya kapanır.";
    case "REPAIRED":
      return (
        "Kitap onarıldı: nüsha onarımdaysa onarım kaydı kapanır ve nüsha rafa döner; dosya " +
        "kapanır."
      );
    case "CLOSED_SAME_REPURCHASED":
      return kayip
        ? "Teslim alınan bedelle kaynağın aynısı alındı: nüsha rafa döner ve dosya kapanır."
        : "Teslim alınan bedelle kaynağın aynısı alındı: nüsha onarımdaysa rafa döner ve " +
            "dosya kapanır.";
    case "CLOSED_OTHER_REPURCHASED":
      return (
        "Teslim alınan bedelle başka bir eser alındı. Dosya kapanır ve bu nüsha için kayıttan " +
        "düşme önerilir; nüshanın durumu değişmez, kayıttan düşme sayımda yapılır. Alınan " +
        "eseri katalogda ayrıca kaydedin." +
        (kayip
          ? " Kitap sonradan bulunursa ve nüsha henüz kayıttan düşülmemişse bu dosyada " +
            "“Bulundu (bedel teslim alınmıştı)” seçilir; öneri geri alınır ve nüsha rafa döner."
          : "")
      );
    case "WRITE_OFF_PROPOSED":
      return kayip
        ? "Dosya kapanır ve nüsha için kayıttan düşme önerilir. Nüsha “Kayıp” kalır; " +
            "kayıttan düşme ayrı bir işlemdir. Kitap sonradan bulunursa bu dosyada " +
            "“Bulundu” seçilir; öneri geri alınır ve nüsha rafa döner."
        : "Dosya kapanır ve nüsha için kayıttan düşme önerilir. Nüshanın durumu değişmez: " +
            "rafta duruyorsa ödünç verilebilir kalır, okunamayacak durumdaysa raftan ayırın. " +
            "Kayıttan düşme ayrı bir işlemdir.";
    default:
      return "";
  }
}

/**
 * Kullanıcının yazdığı bedeli sunucunun ondalık biçimine çevirir ("125,50" → "125.50").
 * Virgül varsa ondalık odur ve noktalar binlik ayracıdır ("1.250,5"); virgül yoksa tek
 * nokta ve en çok iki hane ondalık sayılır ("125.50"), öbür noktalar binliktir ("1.250").
 */
export function bedelMetni(deger: string): string | null {
  let temiz = deger.trim().replace(/\s/g, "");
  if (temiz.includes(",")) temiz = temiz.replace(/\./g, "").replace(",", ".");
  else if (!/^\d+\.\d{1,2}$/.test(temiz)) temiz = temiz.replace(/\./g, "");
  if (!temiz) return null;
  const sayi = Number(temiz);
  if (!Number.isFinite(sayi) || sayi <= 0) return null;
  return sayi.toFixed(2);
}

type Onay =
  { tur: "cozum"; cozum: Cozum; etiket: string } | { tur: "onarima" } | { tur: "onarimdan" };

function Satir({ etiket, deger }: { etiket: string; deger: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-label-medium text-on-surface-variant">{etiket}</dt>
      <dd className="text-body-medium text-on-surface">{deger || "—"}</dd>
    </div>
  );
}

export default function DosyaAyrintisi({
  dosya,
  onClose,
  onDegisti,
}: {
  dosya: Dosya;
  onClose: () => void;
  /** Dosya ya da nüsha değişti (liste tazelensin). */
  onDegisti: (dosya: Dosya) => void;
}) {
  const snackbar = useSnackbar();
  const [guncel, setGuncel] = useState<Dosya>(dosya);
  const [not, setNot] = useState(dosya.responsible_note);
  const [onay, setOnay] = useState<Onay | null>(null);
  const [bedel, setBedel] = useState("");
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const { errors, clearErrors, applyApiError, setFieldError } = useFormErrors();

  useEffect(() => {
    setGuncel(dosya);
    setNot(dosya.responsible_note);
  }, [dosya]);

  const yaz = (yeni: Dosya) => {
    setGuncel(yeni);
    setNot(yeni.responsible_note);
    onDegisti(yeni);
  };

  const onayla = (yeni: Onay) => {
    clearErrors();
    setHata(null);
    if (yeni.tur === "cozum" && yeni.cozum === BEDEL_SORULAN) {
      // Bedel yeniden belirlenirken kayıttaki bedelle gelir (düzeltme).
      setBedel(guncel.market_price ? guncel.market_price.replace(".", ",") : "");
    }
    setOnay(yeni);
  };

  const notuKaydet = async () => {
    clearErrors();
    setHata(null);
    setBusy(true);
    try {
      yaz(await kayipApi.notuGuncelle(guncel.id, not.trim()));
      snackbar.success("Sorumlu notu kaydedildi.");
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "Sorumlu notu kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  const isle = async () => {
    if (onay === null) return;
    clearErrors();
    setHata(null);
    setBusy(true);
    try {
      if (onay.tur === "cozum") {
        let marketPrice: string | undefined;
        if (onay.cozum === BEDEL_SORULAN) {
          const metin = bedelMetni(bedel);
          if (metin === null) {
            setFieldError("market_price", "Bedel kaydı için o günkü piyasa bedelini yazın.");
            return;
          }
          marketPrice = metin;
        }
        const yeni = await kayipApi.coz(guncel.id, {
          resolution: onay.cozum,
          ...(marketPrice !== undefined ? { market_price: marketPrice } : {}),
        });
        snackbar.success(`Çözüm işlendi: ${yeni.resolution_display}.`);
        yaz(yeni);
      } else {
        const sonuc =
          onay.tur === "onarima"
            ? await kayipApi.onarimaGonder(guncel.copy)
            : await kayipApi.onarimdanDon(guncel.copy);
        snackbar.success(sonuc.message);
        yaz(await kayipApi.getir(guncel.id));
      }
      setOnay(null);
    } catch (e) {
      applyApiError(e);
      setHata(hataOku(e, "İşlem yapılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const baslik =
    onay === null
      ? `${guncel.case_type_display} dosyası`
      : onay.tur === "cozum"
        ? `“${onay.etiket}” işlensin mi?`
        : onay.tur === "onarima"
          ? "Nüsha onarıma gönderilsin mi?"
          : "Nüsha onarımdan dönsün mü?";

  const onayMetni =
    onay === null
      ? ""
      : onay.tur === "cozum"
        ? cozumSonucu(onay.cozum, guncel)
        : onay.tur === "onarima"
          ? "Nüsha “Onarımda” olur ve dönene kadar ödünç verilmez. Onarım kaydı yıl sonu raporuna girer."
          : "Onarım kaydı bugünle kapanır ve nüsha rafa döner. Hasar dosyası kendiliğinden kapanmaz; kitap onarıldıysa “Onarıldı” çözümünü ayrıca seçin.";

  const bedelSorulur = onay?.tur === "cozum" && onay.cozum === BEDEL_SORULAN;
  const sorumlu = [guncel.responsible_name, guncel.responsible_class_label]
    .filter(Boolean)
    .join(" · ");
  const hasarAcik = guncel.is_open && guncel.case_type === "DAMAGED";
  // Kapanmış dosyada da sunucu bir çözüm verebilir (öneriyle kapanan kayıpta "Bulundu").
  const cozumVar = guncel.is_open || guncel.allowed_resolutions.length > 0;
  const bedelliBulunmaVar = guncel.allowed_resolutions.some((c) => c.value === "FOUND_AFTER_PRICE");
  // Öneriyle kapanmış kayıp dosyasının nüshası kayıttan düşülmüşse (sayım) bulunan kitap
  // bu dosyadan dönmez; yeni nüsha olarak alınır (F8 ekleri 14).
  const kayittanDusulmus =
    !guncel.is_open &&
    guncel.case_type === "LOST" &&
    ONERI_COZUMLERI.has(guncel.resolution) &&
    guncel.copy_status.startsWith("WITHDRAWN_");

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={baslik}
      actions={
        onay === null ? (
          <Button variant="text" onClick={onClose}>
            Kapat
          </Button>
        ) : (
          <>
            <Button variant="text" onClick={() => setOnay(null)} disabled={busy}>
              Vazgeç
            </Button>
            <Button icon="check" onClick={() => void isle()} disabled={busy}>
              {busy ? "İşleniyor…" : onay.tur === "cozum" ? "İşle" : "Onayla"}
            </Button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {hata && <ErrorBand hata={hata} />}

        {onay !== null ? (
          <div className="space-y-4">
            <p className="text-body-medium text-on-surface">
              {guncel.barcode_display} — {guncel.work_title}
            </p>
            <p className="text-body-medium text-on-surface">{onayMetni}</p>
            {bedelSorulur && (
              <TextField
                label="O günkü piyasa bedeli (TL)"
                inputMode="decimal"
                value={bedel}
                onChange={(e) => setBedel(e.target.value)}
                error={errors.market_price}
                helperText="Yalnız kayıt içindir; program tahsilat yapmaz."
              />
            )}
          </div>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
              <Satir etiket="Nüsha" deger={`${guncel.barcode_display} — ${guncel.work_title}`} />
              <Satir etiket="Nüsha durumu" deger={guncel.copy_status_display} />
              <Satir etiket="Dosya türü" deger={guncel.case_type_display} />
              <Satir etiket="Tespit tarihi" deger={formatDate(guncel.reported_on)} />
              <Satir etiket="Sorumlu üye" deger={sorumlu} />
              <Satir etiket="Çözüm" deger={guncel.resolution_display} />
              {guncel.market_price !== null && (
                <Satir etiket="Kaydedilen piyasa bedeli" deger={formatPrice(guncel.market_price)} />
              )}
              {guncel.price_determined_at && (
                <Satir etiket="Bedel belirlendi" deger={formatDate(guncel.price_determined_at)} />
              )}
              {guncel.price_received_at && (
                <Satir etiket="Bedel teslim alındı" deger={formatDate(guncel.price_received_at)} />
              )}
              {guncel.resolved_at && (
                <Satir etiket="Kapanış" deger={formatDateTime(guncel.resolved_at)} />
              )}
              {guncel.write_off_proposed_at && (
                <Satir
                  etiket="Kayıttan düşme önerisi"
                  deger={formatDateTime(guncel.write_off_proposed_at)}
                />
              )}
            </dl>

            {guncel.is_open ? (
              <div className="space-y-2">
                <MetinAlani
                  label="Sorumlu notu"
                  value={not}
                  onChange={setNot}
                  rows={2}
                  helperText={SORUMLU_NOTU_YARDIMI}
                  error={errors.responsible_note}
                />
                <Button
                  variant="outlined"
                  icon="save"
                  onClick={() => void notuKaydet()}
                  disabled={busy || not.trim() === guncel.responsible_note}
                >
                  Notu kaydet
                </Button>
              </div>
            ) : (
              guncel.responsible_note && (
                <Satir etiket="Sorumlu notu" deger={guncel.responsible_note} />
              )
            )}

            {guncel.resolution === "FOUND_AFTER_PRICE" && (
              <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
                <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
                {BEDEL_IADESI_NOTU}
              </p>
            )}

            {kayittanDusulmus && (
              <section aria-label="Bulunan kitap" className="space-y-2">
                <p className="text-body-small text-on-surface-variant">{KAYITTAN_DUSULMUS_NOTU}</p>
                {guncel.resolution === "CLOSED_OTHER_REPURCHASED" && (
                  <p className="text-body-small text-on-surface-variant">{BEDEL_IADESI_NOTU}</p>
                )}
              </section>
            )}

            {cozumVar && (
              <section aria-label="Çözüm" className="space-y-2">
                <p className="text-title-small text-on-surface">Çözüm</p>
                {!guncel.is_open && (
                  <p className="text-body-small text-on-surface-variant">
                    {guncel.resolution === "CLOSED_OTHER_REPURCHASED"
                      ? BEDELLI_ONERI_GERI_ALMA_NOTU
                      : ONERI_GERI_ALMA_NOTU}
                  </p>
                )}
                {bedelliBulunmaVar && (
                  <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
                    <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
                    {BEDEL_IADESI_NOTU}
                  </p>
                )}
                {guncel.is_open && !guncel.is_person_open_work && (
                  <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
                    <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
                    {OKULUN_ACIK_ISI_NOTU}
                  </p>
                )}
                {guncel.is_open && !guncel.price_options_available && (
                  <p className="flex items-start gap-2 rounded-shape-sm bg-surface-container-high px-3 py-2 text-body-small text-on-surface">
                    <Icon name="info" size="sm" className="mt-0.5 shrink-0" />
                    {BEDEL_YOK_NOTU}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  {guncel.allowed_resolutions.map((c) => (
                    <Button
                      key={c.value}
                      variant="tonal"
                      onClick={() => onayla({ tur: "cozum", cozum: c.value, etiket: c.label })}
                      disabled={busy}
                    >
                      {c.label}
                    </Button>
                  ))}
                </div>
              </section>
            )}

            {hasarAcik &&
              (guncel.copy_status === "AVAILABLE" || guncel.copy_status === "IN_REPAIR") && (
                <section aria-label="Onarım" className="space-y-2">
                  <p className="text-title-small text-on-surface">Onarım</p>
                  {guncel.copy_status === "AVAILABLE" ? (
                    <Button
                      variant="outlined"
                      icon="build"
                      onClick={() => onayla({ tur: "onarima" })}
                      disabled={busy}
                    >
                      Onarıma gönder
                    </Button>
                  ) : (
                    <Button
                      variant="outlined"
                      icon="assignment_return"
                      onClick={() => onayla({ tur: "onarimdan" })}
                      disabled={busy}
                    >
                      Onarımdan dön
                    </Button>
                  )}
                </section>
              )}

            <section aria-label={TUTANAK_ADI} className="space-y-2">
              <p className="text-title-small text-on-surface">{TUTANAK_ADI}</p>
              <div className="flex flex-wrap gap-2">
                <PdfDugmeleri
                  pdfAl={() => kayipApi.tutanakPdf(guncel.id)}
                  dosyaAdi={() =>
                    dosyaAdi(
                      [
                        // Bölü dosya adında yasaktır ("Kayıp-hasar tutanağı_…").
                        TUTANAK_ADI.replace("/", "-"),
                        guncel.barcode_display,
                        formatDate(guncel.reported_on),
                      ],
                      "pdf",
                    )
                  }
                  onizlemeBasligi={TUTANAK_ADI}
                  onHata={setHata}
                />
              </div>
            </section>
          </>
        )}
      </div>
    </Dialog>
  );
}
