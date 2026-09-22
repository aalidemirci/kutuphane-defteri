// Kapalı Günler paneli (F1; tasarım §6.1 Holiday, §9-5). Takvim yılına göre
// listeler: resmî tatil, dini bayram, öğrenciye kapalı gün (ara tatil, yarıyıl) ve
// idari izin. İade tarihi kapalı güne denk gelirse izleyen ilk açık güne kayar;
// ara tatil ve yarıyıl kanunen tatil DEĞİLDİR, bu yüzden "öğrenciye kapalı gün"
// diye ayrı tutulur ve tek başına "tatil" denmez (sözlük). Kaydırma kullanıcıya
// hiçbir yerde "Md. 18 gereği" diye sunulmaz.
//
// Yeniden kullanım (sihirbazın ders yılı adımı): `yil` + `onYilChange` ile yıl
// dışarıdan denetlenir, `yillar` seçiciyi sınırlar (ör. ders yılının iki takvim
// yılı), `baslikGizli` panel başlığını kaldırır, `onDegisti` her yazmadan sonra
// haber verir. Sağlayıcılar: SnackbarProvider + ConfirmProvider.

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import { formatDate, todayIso } from "../../lib/format";
import { parseApiFieldErrors } from "../../lib/formErrors";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import UyariBandi from "../../ui/UyariBandi";
import { HOLIDAY_KIND_TR, okulApi } from "../okul/api";
import type { Holiday, HolidayKind } from "../okul/api";

export interface KapaliGunlerPaneliProps {
  /** Gösterilen takvim yılı. Verilirse yıl dışarıdan denetlenir (`onYilChange` ile). */
  yil?: number;
  /** Yıl seçicideki seçenekler (varsayılan: geçen yıl … iki yıl sonrası). Tek yılsa seçici gizlenir. */
  yillar?: number[];
  /** Kullanıcı yıl seçince ya da eklenen kayıt başka yıla düşünce çağrılır. */
  onYilChange?: (yil: number) => void;
  /** Panel başlığını ve açıklamasını gizler (çağıran kendi başlığını yazar). */
  baslikGizli?: boolean;
  /** Ekleme, silme ya da tohumlama başarıyla bitince çağrılır. */
  onDegisti?: () => void;
}

/** Bugünün takvim yılı — `todayIso` üzerinden (UTC kayması yok). */
function buYil(): number {
  return Number(todayIso().slice(0, 4));
}

function isoYil(iso: string): number {
  return Number(iso.slice(0, 4));
}

/** ISO tarihten UTC gün numarası — iki tarih arasındaki gün farkı için (saat dilimsiz). */
function gunNo(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

function tarihAraligi(h: Pick<Holiday, "start_date" | "end_date">): string {
  if (h.start_date === h.end_date) return formatDate(h.start_date);
  const gun = gunNo(h.end_date) - gunNo(h.start_date) + 1;
  return `${formatDate(h.start_date)} – ${formatDate(h.end_date)} · ${gun} gün`;
}

// Tür rozetleri — ham renk yok, M3 kap tonları.
const TUR_ROZETI: Record<HolidayKind, string> = {
  SCHOOL_BREAK: "bg-secondary-container text-on-secondary-container",
  OFFICIAL: "bg-primary-container text-on-primary-container",
  RELIGIOUS: "bg-tertiary-container text-on-tertiary-container",
  OTHER: "bg-surface-container-highest text-on-surface-variant",
};

const TUR_ACIKLAMASI: Record<HolidayKind, string> = {
  SCHOOL_BREAK:
    "Ara tatil ve yarıyıl. Kanunen tatil değildir, mesai sürer; iade tarihinin bu günlerden sonraya kayması okulun tercihidir.",
  RELIGIOUS: "Diyanet takvimindeki kesin tarihi girin.",
  OFFICIAL:
    "Resmî tatiller “Resmî ve dini tatilleri ekle” düğmesiyle gelir; burayı yalnız listede olmayan bir tatil için kullanın.",
  OTHER: "Personelin de izinli olduğu, kütüphanenin kapalı kaldığı günler.",
};

const TAHMINI_ACIKLAMA =
  "“Tahmini” rozetli dini bayram tarihleri hesapla bulunmuştur ve bir gün kayabilir. Diyanet takvimi kesinleşince kontrol edin; tarih farklıysa kaydı silip doğru tarihle “Dini bayram” türünde yeniden ekleyin.";

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size="lg" />
      <span>{message}</span>
    </div>
  );
}

export default function KapaliGunlerPaneli({
  yil,
  yillar,
  onYilChange,
  baslikGizli = false,
  onDegisti,
}: KapaliGunlerPaneliProps) {
  const [icYil, setIcYil] = useState<number>(() => yil ?? buYil());
  const seciliYil = yil ?? icYil;

  const [kayitlar, setKayitlar] = useState<Holiday[]>([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [surum, setSurum] = useState(0);
  const [tohumlaniyor, setTohumlaniyor] = useState(false);
  // Tohumlama bu yılın dini bayramlarını bulamadıysa (gömülü tablo dışı) kalıcı uyarı.
  const [diniEksikYil, setDiniEksikYil] = useState<number | null>(null);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const secenekler = useMemo(() => {
    const kume = new Set(yillar ?? [buYil() - 1, buYil(), buYil() + 1, buYil() + 2]);
    kume.add(seciliYil);
    return [...kume].sort((a, b) => a - b);
  }, [yillar, seciliYil]);

  const yilSec = (y: number) => {
    if (yil === undefined) setIcYil(y);
    onYilChange?.(y);
  };

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    okulApi
      .listHolidays(seciliYil)
      .then((rows) => {
        if (iptal) return;
        setKayitlar(rows);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(e instanceof ApiError ? e.message : "Kapalı günler yüklenemedi.");
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [seciliYil, surum]);

  const degisti = () => {
    setSurum((s) => s + 1);
    onDegisti?.();
  };

  const tohumla = async () => {
    setTohumlaniyor(true);
    setHata(null);
    try {
      const sonuc = await okulApi.seedHolidays(seciliYil);
      if (sonuc.created > 0) {
        const atlanan = sonuc.skipped > 0 ? `; ${sonuc.skipped} kayıt zaten vardı` : "";
        snackbar.success(`${sonuc.year} yılı için ${sonuc.created} kayıt eklendi${atlanan}.`);
      } else {
        snackbar.success(`${sonuc.year} yılının resmî ve dini tatilleri zaten listede.`);
      }
      setDiniEksikYil(sonuc.religious_available ? null : sonuc.year);
      degisti();
    } catch (e) {
      setHata(e instanceof ApiError ? e.message : "Resmî ve dini tatiller eklenemedi.");
    } finally {
      setTohumlaniyor(false);
    }
  };

  const sil = async (h: Holiday) => {
    const ok = await confirm({
      title: "Kapalı gün silinsin mi?",
      message: `“${h.name}” (${tarihAraligi(h)}) listeden kalkar. Bundan sonra hesaplanan iade tarihlerinde bu günler açık gün sayılır.`,
      confirmLabel: "Sil",
    });
    if (!ok) return;
    try {
      await okulApi.deleteHoliday(h.id);
      snackbar.success("Kapalı gün silindi.");
      degisti();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Kapalı gün silinemedi.");
    }
  };

  const eklendi = (h: Holiday) => {
    // Eklenen kayıt gösterilen yılla kesişmiyorsa onun yılına geçilir; yoksa
    // kullanıcı kaydını listede göremez ve eklenmedi sanır.
    if (isoYil(h.start_date) > seciliYil || isoYil(h.end_date) < seciliYil) {
      yilSec(isoYil(h.start_date));
    }
    degisti();
  };

  const tahminiVar = kayitlar.some((h) => h.is_estimated);

  return (
    <div className="space-y-6">
      {hata && <ErrorBanner message={hata} />}

      <Card elevation={1} className="p-6">
        {!baslikGizli && (
          <>
            <h2 className="text-title-medium text-on-surface">Kapalı Günler</h2>
            <p className="mt-1 text-body-medium text-on-surface-variant">
              İade tarihi kapalı bir güne denk gelirse izleyen ilk açık güne kayar. Hafta sonu,
              resmî tatil, dini bayram ve idari izin her zaman kapalıdır. Ara tatil ve yarıyıl
              kanunen tatil değildir; bunlar öğrenciye kapalı gün olarak ayrı tutulur.
            </p>
          </>
        )}

        <div
          className={`flex flex-wrap items-end justify-between gap-3 ${baslikGizli ? "" : "mt-4"}`}
        >
          {secenekler.length > 1 ? (
            <Select
              className="w-40"
              label="Yıl"
              value={String(seciliYil)}
              onChange={(e) => yilSec(Number(e.target.value))}
              options={secenekler.map((y) => ({ value: String(y), label: String(y) }))}
            />
          ) : (
            <p className="text-title-small text-on-surface">{seciliYil}</p>
          )}
          <Button
            variant="tonal"
            icon="event_repeat"
            onClick={() => void tohumla()}
            disabled={tohumlaniyor}
          >
            {tohumlaniyor ? "Ekleniyor…" : "Resmî ve dini tatilleri ekle"}
          </Button>
        </div>

        {diniEksikYil === seciliYil && (
          <UyariBandi
            className="mt-4"
            title="Dini bayram tarihleri eklenemedi"
            messages={[
              `Programda ${seciliYil} yılının dini bayram tarihleri kayıtlı değil. Diyanet takvimine bakarak Ramazan ve Kurban Bayramı'nı aşağıdaki formdan “Dini bayram” türünde ekleyin.`,
            ]}
            onClose={() => setDiniEksikYil(null)}
          />
        )}

        {tahminiVar && (
          <p
            role="note"
            className="mt-4 flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-small text-on-secondary-container"
          >
            <Icon name="info" size="lg" className="shrink-0" />
            <span>{TAHMINI_ACIKLAMA}</span>
          </p>
        )}

        {yukleniyor ? (
          <SkeletonList rows={4} className="mt-4" />
        ) : kayitlar.length === 0 ? (
          <div className="mt-2">
            <EmptyState
              compact
              icon="event_available"
              title={`${seciliYil} yılı için kayıtlı kapalı gün yok. Resmî ve dini tatilleri ekleyin; ara tatil ve yarıyılı aşağıdaki formdan girin.`}
            />
          </div>
        ) : (
          <ul
            aria-label={`${seciliYil} kapalı günleri`}
            className="mt-4 divide-y divide-outline-variant/50"
          >
            {kayitlar.map((h) => (
              <li key={h.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-body-large text-on-surface">
                    <span
                      className={`inline-flex items-center rounded-shape-xl px-2 py-0.5 text-label-small ${TUR_ROZETI[h.kind]}`}
                    >
                      {HOLIDAY_KIND_TR[h.kind]}
                    </span>
                    {h.name}
                    {h.is_estimated && (
                      <span
                        title="Diyanet takvimi kesinleşince kontrol edin."
                        className="inline-flex items-center rounded-shape-xl border border-outline px-2 py-0.5 text-label-small text-on-surface-variant"
                      >
                        tahmini
                      </span>
                    )}
                  </p>
                  <p className="text-label-small text-on-surface-variant">{tarihAraligi(h)}</p>
                </div>
                <Button
                  variant="text"
                  icon="delete"
                  aria-label={`${h.name} kaydını sil`}
                  onClick={() => void sil(h)}
                >
                  Sil
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <KapaliGunEkleKarti onEklendi={eklendi} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ekleme formu — varsayılan tür öğrenciye kapalı gün (ara tatil, yarıyıl)
// ---------------------------------------------------------------------------

const TUR_SECENEKLERI = (Object.keys(HOLIDAY_KIND_TR) as HolidayKind[]).map((value) => ({
  value,
  label: HOLIDAY_KIND_TR[value],
}));

function KapaliGunEkleKarti({ onEklendi }: { onEklendi: (h: Holiday) => void }) {
  const [ad, setAd] = useState("");
  const [tur, setTur] = useState<HolidayKind>("SCHOOL_BREAK");
  const [baslangic, setBaslangic] = useState("");
  const [bitis, setBitis] = useState("");
  const [alanHatalari, setAlanHatalari] = useState<Record<string, string>>({});
  const [formHatasi, setFormHatasi] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const snackbar = useSnackbar();

  const gonder = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormHatasi(null);
    // İstemci yalnız BOŞ alanı yakalar; tarih sırası ve süre sınırı backend'dedir.
    const eksik: Record<string, string> = {};
    if (!ad.trim()) eksik.name = "Ad yazılmalıdır.";
    if (!baslangic) eksik.start_date = "Başlangıç tarihi seçilmelidir.";
    if (Object.keys(eksik).length > 0) {
      setAlanHatalari(eksik);
      return;
    }
    setAlanHatalari({});
    setMesgul(true);
    try {
      const kayit = await okulApi.createHoliday({
        name: ad.trim(),
        start_date: baslangic,
        end_date: bitis || baslangic,
        kind: tur,
      });
      snackbar.success("Kapalı gün eklendi.");
      setAd("");
      setBaslangic("");
      setBitis("");
      onEklendi(kayit);
    } catch (err) {
      const alanlar = parseApiFieldErrors(err) ?? {};
      if (Object.keys(alanlar).length > 0) {
        setAlanHatalari(alanlar);
      } else {
        setFormHatasi(err instanceof ApiError ? err.message : "Kapalı gün eklenemedi.");
      }
    } finally {
      setMesgul(false);
    }
  };

  return (
    <Card elevation={1} className="p-6">
      <h2 className="text-title-medium text-on-surface">Kapalı Gün Ekle</h2>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Ara tatil ve yarıyıl için “Öğrenciye kapalı gün” türünü seçin. Tek günlük kayıtta bitişi boş
        bırakabilirsiniz.
      </p>
      <form className="mt-4 space-y-4" onSubmit={gonder} noValidate>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Ad"
            required
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            placeholder="Yarıyıl tatili"
            error={alanHatalari.name}
          />
          <Select
            label="Tür"
            value={tur}
            onChange={(e) => setTur(e.target.value as HolidayKind)}
            options={TUR_SECENEKLERI}
            helperText={TUR_ACIKLAMASI[tur]}
            error={alanHatalari.kind}
          />
          <TextField
            label="Başlangıç"
            required
            type="date"
            value={baslangic}
            onChange={(e) => setBaslangic(e.target.value)}
            error={alanHatalari.start_date}
          />
          <TextField
            label="Bitiş"
            type="date"
            value={bitis}
            min={baslangic || undefined}
            onChange={(e) => setBitis(e.target.value)}
            helperText="Boş bırakılırsa tek gün sayılır."
            error={alanHatalari.end_date}
          />
        </div>
        {formHatasi && <ErrorBanner message={formHatasi} />}
        <div className="flex justify-end">
          <Button type="submit" icon="add" disabled={mesgul}>
            {mesgul ? "Ekleniyor…" : "Ekle"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
