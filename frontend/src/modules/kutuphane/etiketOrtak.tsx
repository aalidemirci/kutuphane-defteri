// Etiket ekranlarının ortak parçaları (F4): şablon ve kalibrasyon kancaları,
// tabaka ızgarası (başlangıç hücresi seçici), basım ayarları, PDF önizleme ve
// indirme düğmeleri, onay bekleyen basım partisinin kartı.
//
// Etiketler sayfasının sekmeleri ve Hızlı Kayıt'ın tek etiket kısayolu aynı
// parçaları kullanır: basım ayarı iki yerde farklı davranmasın.
//
// **PDF üretmek "basıldı" DEĞİLDİR** (tasarım D10): "Önizle" ve "PDF'i indir"
// hiçbir işarete dokunmaz; "Basıldı olarak işaretle" onay diyaloğundan geçer ve
// geri alınabilir (Basım Geçmişi).

import { useEffect, useRef, useState } from "react";

import { saveBlob } from "../../lib/download";
import { formatDateTime, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import type { SelectOption } from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { ETIKET_ICERIGI_TR, etiketApi, etiketDosyaAdi } from "./etiketApi";
import type {
  BasimAyariGovdesi,
  BasimPartisi,
  EtiketIcerigi,
  EtiketSablonu,
  PartiDurumu,
  YaziciKalibrasyonu,
} from "./etiketApi";

// ---------------------------------------------------------------------------
// Sayı ve ölçü yardımcıları
// ---------------------------------------------------------------------------

/** Ölçüyü Türkçe yazar: 38.1 → "38,1". */
export function mm(deger: number): string {
  return formatNumber(Number(deger.toFixed(2)));
}

/** Şablonun kısa ölçü satırı: "38,1 × 21,2 mm · 65 etiket (5 × 13)". */
export function sablonOlcusu(sablon: EtiketSablonu): string {
  return (
    `${mm(sablon.label_width)} × ${mm(sablon.label_height)} mm · ` +
    `${formatNumber(sablon.labels_per_sheet)} etiket (${sablon.cols} × ${sablon.rows})`
  );
}

/**
 * Kullanıcının yazdığı ondalık sayı: virgül de nokta da kabul edilir ("38,1").
 * Boş ya da sayı olmayan girdi `null` döner (alan hatası çağıranındır).
 */
export function ondalikOku(girdi: string): number | null {
  const temiz = girdi.trim().replace(",", ".");
  if (temiz === "" || !/^[-+]?\d*\.?\d+$/.test(temiz)) return null;
  return Number(temiz);
}

/**
 * Bir basımın tabaka sayısı: başlangıç hücresinden önceki hücreler ilk tabakada
 * boş kalır; "sırt ve barkod etiketi" iki ayrı tabaka takımıdır.
 */
export function tabakaSayisi(
  adet: number,
  baslangic: number,
  hucre: number,
  parca: number = 1,
): number {
  if (adet <= 0 || hucre <= 0) return 0;
  return Math.ceil((baslangic - 1 + adet) / hucre) * parca;
}

/** İçeriğin kaç tabaka takımı olduğu ("ikisi birden" önce sırt, sonra barkod). */
export function parcaSayisi(icerik: EtiketIcerigi | "BLANK"): number {
  return icerik === "BOTH" ? 2 : 1;
}

/** İçeriğe göre varsayılan şablon: sırt için sırt tabakası, diğerleri için barkod tabakası. */
export function varsayilanSablon(
  sablonlar: EtiketSablonu[],
  icerik: EtiketIcerigi | "BLANK",
): EtiketSablonu | null {
  const tur = icerik === "SPINE" ? "SPINE" : "BARCODE";
  return (
    sablonlar.find((s) => s.kind === tur && s.is_default) ??
    sablonlar.find((s) => s.kind === tur) ??
    sablonlar[0] ??
    null
  );
}

/** Şablon seçicisinin seçenekleri: ad + ölçü. */
export function sablonSecenekleri(sablonlar: EtiketSablonu[]): SelectOption[] {
  return sablonlar.map((s) => ({ value: String(s.id), label: s.name }));
}

/** Kalibrasyon seçicisinin etiketi: yazıcı + kayma. */
export function kalibrasyonEtiketi(k: YaziciKalibrasyonu): string {
  return `${k.printer_name} (yatay ${mm(k.offset_x)} mm, dikey ${mm(k.offset_y)} mm)`;
}

// ---------------------------------------------------------------------------
// Kancalar
// ---------------------------------------------------------------------------

/**
 * Etiket şablonları. İlk liste isteği hazır şablonları yazar (sunucu); ekran
 * açıkken şablon düzenlenirse `yenile` çağrılır.
 */
export function useEtiketSablonlari(): {
  sablonlar: EtiketSablonu[];
  yukleniyor: boolean;
  hata: SayfaHatasi | null;
  yenile: () => void;
} {
  const [sablonlar, setSablonlar] = useState<EtiketSablonu[]>([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [tazeleme, setTazeleme] = useState(0);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    etiketApi
      .sablonlar()
      .then((sayfa) => {
        if (iptal) return;
        setSablonlar(sayfa.results);
        setHata(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Etiket şablonları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, [tazeleme]);

  return { sablonlar, yukleniyor, hata, yenile: () => setTazeleme((k) => k + 1) };
}

/** Bir şablonun yazıcı kalibrasyonları (şablon seçilmemişse boş liste). */
export function useKalibrasyonlar(
  sablonId: number | null,
  tazeleme: number = 0,
): { kalibrasyonlar: YaziciKalibrasyonu[]; yuklendi: number | null } {
  const [kalibrasyonlar, setKalibrasyonlar] = useState<YaziciKalibrasyonu[]>([]);
  // Hangi şablonun listesinin yüklendiği: kendiliğinden seçim yalnız o anda yapılır.
  const [yuklendi, setYuklendi] = useState<number | null>(null);

  useEffect(() => {
    let iptal = false;
    if (sablonId === null) {
      setKalibrasyonlar([]);
      setYuklendi(null);
      return;
    }
    etiketApi
      .kalibrasyonlar(sablonId)
      .then((sayfa) => {
        if (iptal) return;
        setKalibrasyonlar(sayfa.results);
        setYuklendi(sablonId);
      })
      .catch(() => {
        if (iptal) return;
        // Kalibrasyon zorunlu değildir: okunamazsa kaymasız basılır.
        setKalibrasyonlar([]);
        setYuklendi(sablonId);
      });
    return () => {
      iptal = true;
    };
  }, [sablonId, tazeleme]);

  return { kalibrasyonlar, yuklendi };
}

// ---------------------------------------------------------------------------
// Tabaka ızgarası — başlangıç hücresi seçici
// ---------------------------------------------------------------------------

/** Sayfa ölçüsü (mm) — ızgara bu orana göre çizilir. */
const SAYFA_GENISLIGI = 210;
const SAYFA_YUKSEKLIGI = 297;

/**
 * Tabakanın küçük resmi: hücreler şablon ölçüleriyle yerleştirilir, tıklanan
 * hücre başlangıç hücresidir. Başlangıçtan önceki hücreler "kullanılmış"
 * görünür, bu basımın ilk tabakada dolduracağı hücreler vurgulanır.
 *
 * Her hücre bir düğmedir ("12. hücre"); klavyeyle de seçilir. Aynı değer yanda
 * sayı kutusuyla da yazılabilir.
 */
export function TabakaIzgarasi({
  sablon,
  baslangic,
  onBaslangic,
  adet,
}: {
  sablon: EtiketSablonu;
  baslangic: number;
  onBaslangic: (hucre: number) => void;
  /** Basılacak etiket sayısı (ilk tabakada dolacak hücreleri vurgulamak için). */
  adet?: number;
}) {
  const hucreler = sablon.labels_per_sheet;
  const ilkTabakadaDolan = adet === undefined ? 0 : Math.min(adet, hucreler - baslangic + 1);
  const yuzdeX = (deger: number) => `${(deger / SAYFA_GENISLIGI) * 100}%`;
  const yuzdeY = (deger: number) => `${(deger / SAYFA_YUKSEKLIGI) * 100}%`;

  return (
    <div
      role="group"
      aria-label="Tabaka ızgarası"
      className="relative aspect-[210/297] w-full max-w-[15rem] shrink-0 rounded-shape-sm border border-outline-variant bg-surface-container-low"
    >
      {Array.from({ length: hucreler }, (_, i) => {
        const no = i + 1;
        const satir = Math.floor(i / sablon.cols);
        const sutun = i % sablon.cols;
        const sol = sablon.page_margin_left + sutun * (sablon.label_width + sablon.gutter_x);
        const ust = sablon.page_margin_top + satir * (sablon.label_height + sablon.gutter_y);
        const kullanilmis = no < baslangic;
        const dolacak = no >= baslangic && no < baslangic + ilkTabakadaDolan;
        const secili = no === baslangic;
        return (
          <button
            key={no}
            type="button"
            aria-label={`${no}. hücre`}
            aria-pressed={secili}
            title={`${no}. hücre`}
            onClick={() => onBaslangic(no)}
            style={{
              left: yuzdeX(sol),
              top: yuzdeY(ust),
              width: yuzdeX(sablon.label_width),
              height: yuzdeY(sablon.label_height),
            }}
            className={`absolute rounded-[2px] border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              secili
                ? "z-10 border-primary bg-primary ring-2 ring-primary"
                : dolacak
                  ? "border-primary/60 bg-primary/40"
                  : kullanilmis
                    ? "border-outline-variant bg-outline-variant/60"
                    : "border-outline-variant bg-surface-container-lowest hover:bg-primary/10"
            }`}
          />
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Basım ayarları
// ---------------------------------------------------------------------------

/** Basım ayarının ekran durumu (seçici değerleri metin; "" = seçilmedi / yok). */
export interface BasimAyari {
  sablon: string;
  kalibrasyon: string;
  /** Yalnız "sırt ve barkod etiketi": sırt ayrı tabakaya basılacaksa şablonu. */
  sirtSablonu: string;
  sirtKalibrasyonu: string;
  baslangic: number;
  qr: boolean;
}

export const BOS_BASIM_AYARI: BasimAyari = {
  sablon: "",
  kalibrasyon: "",
  sirtSablonu: "",
  sirtKalibrasyonu: "",
  baslangic: 1,
  qr: false,
};

/** Ekran durumundan istek gövdesi (şablon seçilmemişse `null`). */
export function basimAyariGovdesi(
  ayar: BasimAyari,
  icerik: EtiketIcerigi | "BLANK",
): BasimAyariGovdesi | null {
  if (!ayar.sablon) return null;
  const ikisi = icerik === "BOTH";
  return {
    template: Number(ayar.sablon),
    calibration: ayar.kalibrasyon ? Number(ayar.kalibrasyon) : null,
    spine_template: ikisi && ayar.sirtSablonu ? Number(ayar.sirtSablonu) : null,
    spine_calibration:
      ikisi && ayar.sirtSablonu && ayar.sirtKalibrasyonu ? Number(ayar.sirtKalibrasyonu) : null,
    include_qr: icerik !== "SPINE" && ayar.qr,
    start_cell: ayar.baslangic,
  };
}

/**
 * Şablon + yazıcı (kalibrasyon) + başlangıç hücresi + QR seçimi. Etiket
 * içeriği değişince şablon içeriğin varsayılanına döner (çağıran `sablon`u
 * boşaltır); şablonun tek kalibrasyonu varsa o yazıcı kendiliğinden seçilir.
 */
/**
 * "Başlangıç hücresi" kutusu. Kutunun HAM metni yerel durumdadır: kullanıcı
 * kutuyu boşaltıp yeni sayı yazabilsin. Önceden kutu doğrudan ayara bağlıydı;
 * boş metin geçersiz sayılıp reddedilince kutu eski değeri gösteriyor, "3"
 * yazan kullanıcı "13" elde ediyordu (denetim bulgusu, 24.09.2026). Geçerli
 * sayı hemen ayara yazılır; geçersiz metin kutuda kalır ve alan hatası
 * gösterilir, kutudan çıkınca son geçerli değere döner. Tabaka ızgarasından
 * seçilen hücre kutuya yansır.
 */
export function BaslangicHucresiAlani({
  baslangic,
  hucre,
  onBaslangic,
}: {
  baslangic: number;
  hucre: number;
  onBaslangic: (no: number) => void;
}) {
  const [metin, setMetin] = useState(String(baslangic));

  useEffect(() => {
    // Dışarıdan (ızgara, şablon değişimi) gelen değer; kutudaki geçerli metin aynıysa dokunulmaz.
    setMetin((onceki) => (Number(onceki) === baslangic ? onceki : String(baslangic)));
  }, [baslangic]);

  const sayi = Number(metin);
  const gecerli = metin !== "" && Number.isInteger(sayi) && sayi >= 1 && sayi <= hucre;

  return (
    <TextField
      label="Başlangıç hücresi"
      inputMode="numeric"
      value={metin}
      onChange={(e) => {
        const yeni = e.target.value.replace(/\D/g, "");
        setMetin(yeni);
        const deger = Number(yeni);
        if (yeni !== "" && Number.isInteger(deger) && deger >= 1 && deger <= hucre) {
          onBaslangic(deger);
        }
      }}
      onBlur={() => {
        if (!gecerli) setMetin(String(baslangic));
      }}
      error={
        gecerli || metin === ""
          ? undefined
          : `Başlangıç hücresi 1 ile ${formatNumber(hucre)} arasında olmalıdır.`
      }
      helperText={`1 ile ${formatNumber(hucre)} arasında; hücreler satır satır, soldan sağa sayılır.`}
    />
  );
}

export function BasimAyarlari({
  icerik,
  sablonlar,
  ayar,
  onAyar,
  adet,
  ekSecenekler = true,
}: {
  icerik: EtiketIcerigi | "BLANK";
  sablonlar: EtiketSablonu[];
  ayar: BasimAyari;
  onAyar: (sonraki: BasimAyari) => void;
  adet?: number;
  /**
   * `false`: QR ve ayrı sırt tabakası seçicileri gösterilmez (yeniden basım
   * onları önceki partiden alır; ekranda seçilebilir görünüp yok sayılmasınlar).
   */
  ekSecenekler?: boolean;
}) {
  const sablon = sablonlar.find((s) => String(s.id) === ayar.sablon) ?? null;
  const sirtSablonu = sablonlar.find((s) => String(s.id) === ayar.sirtSablonu) ?? null;
  const { kalibrasyonlar, yuklendi } = useKalibrasyonlar(sablon?.id ?? null);
  const { kalibrasyonlar: sirtKalibrasyonlari } = useKalibrasyonlar(sirtSablonu?.id ?? null);
  const kendiligindenSecilen = useRef<number | null>(null);
  // Güncel ayar ve bildirim işlevi: etkiler yalnız sunucu yanıtına tepki verir.
  const guncel = useRef({ ayar, onAyar });
  guncel.current = { ayar, onAyar };

  // Şablon seçilmemişse içeriğin varsayılanı.
  useEffect(() => {
    if (ayar.sablon !== "" || sablonlar.length === 0) return;
    const secilen = varsayilanSablon(sablonlar, icerik);
    if (secilen === null) return;
    guncel.current.onAyar({
      ...guncel.current.ayar,
      sablon: String(secilen.id),
      kalibrasyon: "",
      baslangic: 1,
      qr: false,
    });
  }, [ayar.sablon, sablonlar, icerik]);

  // Şablonun tek yazıcısı varsa o seçilir (şablon başına bir kez).
  useEffect(() => {
    if (sablon === null || yuklendi !== sablon.id) return;
    if (kendiligindenSecilen.current === sablon.id) return;
    kendiligindenSecilen.current = sablon.id;
    if (guncel.current.ayar.kalibrasyon === "" && kalibrasyonlar.length === 1) {
      guncel.current.onAyar({ ...guncel.current.ayar, kalibrasyon: String(kalibrasyonlar[0].id) });
    }
  }, [sablon, yuklendi, kalibrasyonlar]);

  if (sablonlar.length === 0) {
    return (
      <p className="text-body-medium text-on-surface-variant">
        Etiket şablonu yok. Şablonlar ve Kalibrasyon sekmesinden bir şablon tanımlayın.
      </p>
    );
  }

  const barkodVar = icerik !== "SPINE";
  const qrUygun = barkodVar && sablon !== null && sablon.supports_qr;
  // Ayrı sırt tabakası aynı satır × sütun düzeninde olmalıdır (§7.2: iki tabakanın
  // N. hücresi aynı kitabındır).
  const sirtAdaylari =
    sablon === null
      ? []
      : sablonlar.filter(
          (s) => s.id !== sablon.id && s.rows === sablon.rows && s.cols === sablon.cols,
        );
  const hucre = sablon?.labels_per_sheet ?? 0;
  const tabaka =
    adet === undefined ? 0 : tabakaSayisi(adet, ayar.baslangic, hucre, parcaSayisi(icerik));

  const sablonDegisti = (deger: string) => {
    const yeni = sablonlar.find((s) => String(s.id) === deger) ?? null;
    onAyar({
      ...ayar,
      sablon: deger,
      kalibrasyon: "",
      sirtSablonu: "",
      sirtKalibrasyonu: "",
      baslangic: yeni !== null && ayar.baslangic > yeni.labels_per_sheet ? 1 : ayar.baslangic,
      qr: yeni?.supports_qr ? ayar.qr : false,
    });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Select
          label="Etiket şablonu"
          required
          placeholder="Seçin"
          value={ayar.sablon}
          onChange={(e) => sablonDegisti(e.target.value)}
          options={sablonSecenekleri(sablonlar)}
          helperText={sablon ? sablonOlcusu(sablon) : undefined}
        />
        <Select
          label="Yazıcı (kalibrasyon)"
          placeholder="— yok —"
          value={ayar.kalibrasyon}
          onChange={(e) => onAyar({ ...ayar, kalibrasyon: e.target.value })}
          options={kalibrasyonlar.map((k) => ({
            value: String(k.id),
            label: kalibrasyonEtiketi(k),
          }))}
          helperText={
            kalibrasyonlar.length === 0
              ? "Bu şablon için kayıtlı yazıcı yok; kaymasız basılır."
              : "Yazıcının ölçülen kayması basıma uygulanır."
          }
        />
        {icerik === "BOTH" && ekSecenekler && (
          <>
            <Select
              label="Sırt etiketi tabakası"
              placeholder="— yok —"
              value={ayar.sirtSablonu}
              onChange={(e) =>
                onAyar({ ...ayar, sirtSablonu: e.target.value, sirtKalibrasyonu: "" })
              }
              options={sablonSecenekleri(sirtAdaylari)}
              helperText="Boş bırakılırsa sırt etiketleri de aynı şablonla, ayrı tabakalara basılır. Ayrı tabaka aynı satır ve sütun düzeninde olmalıdır."
            />
            {sirtSablonu !== null && (
              <Select
                label="Sırt tabakasının yazıcısı"
                placeholder="— yok —"
                value={ayar.sirtKalibrasyonu}
                onChange={(e) => onAyar({ ...ayar, sirtKalibrasyonu: e.target.value })}
                options={sirtKalibrasyonlari.map((k) => ({
                  value: String(k.id),
                  label: kalibrasyonEtiketi(k),
                }))}
              />
            )}
          </>
        )}
      </div>

      {barkodVar && ekSecenekler && (
        <label
          className={`flex min-h-11 items-start gap-2 text-body-medium ${
            qrUygun ? "cursor-pointer text-on-surface" : "text-on-surface-variant"
          }`}
        >
          <input
            type="checkbox"
            checked={qrUygun && ayar.qr}
            disabled={!qrUygun}
            onChange={(e) => onAyar({ ...ayar, qr: e.target.checked })}
            className="mt-0.5 size-5 shrink-0 accent-primary"
          />
          <span>
            Barkodun yanına QR ekle
            <span className="block text-body-small text-on-surface-variant">
              {qrUygun
                ? "QR yalnız barkod numarasını taşır, adres taşımaz."
                : "QR yalnız 48,5 × 25,4 mm ve daha büyük etiketlere sığar."}
            </span>
          </span>
        </label>
      )}

      {sablon !== null && (
        <div className="flex flex-wrap items-start gap-4">
          <TabakaIzgarasi
            sablon={sablon}
            baslangic={ayar.baslangic}
            onBaslangic={(no) => onAyar({ ...ayar, baslangic: no })}
            adet={adet}
          />
          <div className="min-w-[14rem] flex-1 space-y-2 text-body-medium text-on-surface-variant">
            <BaslangicHucresiAlani
              baslangic={ayar.baslangic}
              hucre={hucre}
              onBaslangic={(no) => onAyar({ ...ayar, baslangic: no })}
            />
            <p>
              Kısmen kullanılmış bir tabakaya basacaksanız ilk boş hücreyi tabaka üzerinde tıklayın.
              {ayar.baslangic > 1 &&
                ` İlk tabakanın ilk ${formatNumber(ayar.baslangic - 1)} hücresi boş bırakılır.`}
            </p>
            {adet !== undefined && adet > 0 && (
              <p className="text-on-surface">
                {formatNumber(adet)} etiket · {formatNumber(tabaka)} tabaka
                {icerik === "BOTH" && " (önce sırt, sonra barkod tabakaları)"}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PDF önizleme ve indirme
// ---------------------------------------------------------------------------

/**
 * "Önizle" (pencere içinde) ve "PDF'i indir" düğmeleri. İkisi de aynı PDF'i
 * sunucudan yeniden alır ve HİÇBİR işarete dokunmaz.
 *
 * Yazdırma notu metinde durur: etiket tabakası "gerçek boyutta" basılmazsa
 * hücreler kayar ve kalibrasyon boşa gider.
 */
export function PdfDugmeleri({
  pdfAl,
  dosyaAdi,
  onizlemeBasligi,
  disabled = false,
  onHata,
}: {
  pdfAl: () => Promise<Blob>;
  dosyaAdi: () => string;
  onizlemeBasligi: string;
  disabled?: boolean;
  onHata: (hata: SayfaHatasi | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  // Pencere kapanınca geçici adres bırakılır.
  useEffect(
    () => () => {
      if (url !== null) URL.revokeObjectURL(url);
    },
    [url],
  );

  const al = async (): Promise<Blob | null> => {
    setBusy(true);
    onHata(null);
    try {
      return await pdfAl();
    } catch (e) {
      onHata(hataOku(e, "PDF hazırlanamadı."));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const onizle = async () => {
    const blob = await al();
    if (blob !== null) setUrl(URL.createObjectURL(blob));
  };

  const indir = async () => {
    const blob = await al();
    if (blob !== null) saveBlob(blob, dosyaAdi());
  };

  return (
    <>
      <Button
        variant="outlined"
        icon="preview"
        onClick={() => void onizle()}
        disabled={disabled || busy}
      >
        Önizle
      </Button>
      <Button
        variant="outlined"
        icon="download"
        onClick={() => void indir()}
        disabled={disabled || busy}
      >
        {busy ? "Hazırlanıyor…" : "PDF'i indir"}
      </Button>
      <Dialog
        open={url !== null}
        onClose={() => setUrl(null)}
        title={onizlemeBasligi}
        wide
        actions={
          <>
            <Button variant="text" icon="download" onClick={() => void indir()} disabled={busy}>
              PDF'i indir
            </Button>
            <Button variant="text" onClick={() => setUrl(null)}>
              Kapat
            </Button>
          </>
        }
      >
        <p className="mb-2 text-body-small text-on-surface-variant">
          Yazdırırken ölçeklemeyi kapatın (“Gerçek boyut” ya da %100); sığdırılarak basılan tabakada
          etiketler hücrelere oturmaz.
        </p>
        {url !== null && (
          <embed
            src={url}
            type="application/pdf"
            aria-label={`${onizlemeBasligi} önizlemesi`}
            className="h-[60vh] w-full rounded-shape-sm"
          />
        )}
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Parti durumu ve onay bekleyen partinin kartı
// ---------------------------------------------------------------------------

const DURUM_RENGI: Record<PartiDurumu, string> = {
  PENDING: "bg-tertiary-container text-on-tertiary-container",
  CONFIRMED: "bg-secondary-container text-on-secondary-container",
  REVERTED: "bg-surface-container-highest text-on-surface-variant",
  DISCARDED: "bg-surface-container-highest text-on-surface-variant",
};

const DURUM_IKONU: Record<PartiDurumu, string> = {
  PENDING: "hourglass_top",
  CONFIRMED: "check_circle",
  REVERTED: "undo",
  DISCARDED: "block",
};

export function PartiDurumRozeti({ parti }: { parti: BasimPartisi }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-label-medium ${DURUM_RENGI[parti.status]}`}
    >
      <Icon name={DURUM_IKONU[parti.status]} size="sm" />
      {parti.status_display}
    </span>
  );
}

/** Partinin tek satırlık özeti: içerik · nüsha · şablon · yazıcı · başlangıç hücresi. */
export function partiOzeti(parti: BasimPartisi, sablon?: EtiketSablonu): string {
  const parcalar = [
    parti.kind_display,
    `${formatNumber(parti.copy_count)} nüsha`,
    parti.template_name,
    parti.printer_name ? `yazıcı: ${parti.printer_name}` : "kalibrasyonsuz",
    `${formatNumber(parti.start_cell)}. hücreden`,
  ];
  if (sablon !== undefined) {
    const tabaka = tabakaSayisi(
      parti.copy_count,
      parti.start_cell,
      sablon.labels_per_sheet,
      parcaSayisi(parti.kind),
    );
    parcalar.splice(2, 0, `${formatNumber(tabaka)} tabaka`);
  }
  if (parti.include_qr) parcalar.push("QR'lı");
  return parcalar.join(" · ");
}

/**
 * Onay bekleyen basım partisinin kartı: PDF'i al → yazdır → tabakayı denetle →
 * "Basıldı olarak işaretle". Parti onaylanana kadar nüshalar kuyrukta kalır.
 */
export function BasimPartisiKarti({
  parti,
  sablon,
  onDegisti,
  baslik = "Hazırlanan Basım Partisi",
}: {
  parti: BasimPartisi;
  sablon?: EtiketSablonu;
  /** Onay ya da vazgeçmeden sonra güncel parti. */
  onDegisti: (parti: BasimPartisi) => void;
  baslik?: string;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const icerikAdi = ETIKET_ICERIGI_TR[parti.kind].toLocaleLowerCase("tr");

  const onayla = async () => {
    const tamam = await confirm({
      title: "Etiketler basıldı olarak işaretlensin mi?",
      message:
        `${formatNumber(parti.copy_count)} nüshanın ${icerikAdi} basıldı olarak işaretlenir ` +
        "ve nüshalar kuyruktan çıkar. " +
        // Sözlük "Basım kaydı": barkod etiketi içeren partinin onayı doğrulamayı sıfırlar.
        (parti.kind === "SPINE"
          ? ""
          : "Barkod etiketlerinin doğrulaması sıfırlanır: yeni etiketleri yapıştırdıktan " +
            "sonra Doğrulama Okutması'nda okutun. ") +
        "Tabaka hatalı çıktıysa işaretlemeyin: PDF'i yeniden basabilir ya da partiden " +
        "vazgeçebilirsiniz. İşaret sonradan Basım Geçmişi'nden geri alınabilir.",
      confirmLabel: "Basıldı olarak işaretle",
    });
    if (!tamam) return;
    setBusy(true);
    setHata(null);
    try {
      const guncel = await etiketApi.partiOnayla(parti.id);
      snackbar.success(`${formatNumber(guncel.copy_count)} nüsha basıldı olarak işaretlendi.`);
      onDegisti(guncel);
    } catch (e) {
      setHata(hataOku(e, "Basım işareti yazılamadı."));
    } finally {
      setBusy(false);
    }
  };

  const vazgec = async () => {
    const tamam = await confirm({
      title: "Bu partiden vazgeçilsin mi?",
      message:
        "Nüshalar kuyrukta kalır; parti basım geçmişinde “Vazgeçildi” olarak durur. Aynı " +
        "nüshaları daha sonra yeniden basabilirsiniz.",
      confirmLabel: "Partiden vazgeç",
    });
    if (!tamam) return;
    setBusy(true);
    setHata(null);
    try {
      const guncel = await etiketApi.partidenVazgec(parti.id);
      snackbar.success("Partiden vazgeçildi; nüshalar kuyrukta.");
      onDegisti(guncel);
    } catch (e) {
      setHata(hataOku(e, "Partiden vazgeçilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      elevation={0}
      className="space-y-3 border-primary/40 p-[var(--kd-panel-padding)] shadow-elevation-1"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-title-medium text-on-surface">
          <Icon name="print" size="lg" className="text-primary" />
          {baslik}
        </p>
        <PartiDurumRozeti parti={parti} />
      </div>
      <p className="text-body-medium text-on-surface">{partiOzeti(parti, sablon)}</p>
      <p className="text-body-small text-on-surface-variant">
        Hazırlandı: {formatDateTime(parti.created_at)}. PDF'i yazdırın ve tabakayı denetleyin.
        Etiketler hücrelere düzgün oturduysa “Basıldı olarak işaretle” deyin; o zamana kadar
        nüshalar kuyrukta kalır. PDF'i almak basıldı saymaz.
      </p>
      {hata && <ErrorBand hata={hata} />}
      <div className="flex flex-wrap items-center gap-2">
        <PdfDugmeleri
          pdfAl={() => etiketApi.partiPdf(parti.id)}
          dosyaAdi={() => etiketDosyaAdi(parti.kind)}
          onizlemeBasligi={ETIKET_ICERIGI_TR[parti.kind]}
          disabled={busy}
          onHata={setHata}
        />
        <Button icon="task_alt" onClick={() => void onayla()} disabled={busy}>
          Basıldı olarak işaretle
        </Button>
        <Button variant="text" icon="block" onClick={() => void vazgec()} disabled={busy}>
          Partiden vazgeç
        </Button>
      </div>
    </Card>
  );
}
