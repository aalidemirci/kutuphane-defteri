// Okutma kutusu — dolaşım masası, doğrulama okutması ve hızlı kayıt ortak bileşeni
// (tasarım §7.3 "BarcodeInput"). Okuyucu klavye gibi yazar ve kodun sonuna Enter
// gönderir; masadaki görevli okutmaları arka arkaya, sonucu beklemeden yapar.
//
// Kurallar (§7.3):
//   * kendiliğinden odaklanır;
//   * Enter ile gönderir;
//   * gönderim anında kutuyu temizler ve okumaları KUYRUĞA alır: sonuç beklenirken
//     gelen okutma sıraya girer, işlemler sırayla ve tek tek yürür — hızlı okutmada
//     hiçbir kod kaybolmaz, iki istek yarışmaz (kod kapısı, `BarcodeInput.test.tsx`);
//   * sesli ve görsel geri bildirim verir (`onOkut` sonucu: başarı · uyarı · hata);
//   * odak kutudan çıkarsa görünür uyarı verir (Windows bildirimi ya da güncelleme
//     penceresi odağı çalabilir) ve odak bir yazı alanında değilken gelen okuyucu
//     tuşunu kutuya yönlendirir (tuşun kendisi de kutuya düşer).
//
// İki davranış vardır:
//   * `sira` (varsayılan): masa ve doğrulama okutması — yukarıdaki kurallar.
//   * `alan`: hızlı kayıttaki gibi okutulan kodun FORMUN PARÇASI olduğu kutular.
//     Değer ebeveyndedir (`value` + `onValueChange`), gönderimde kutu boşalmaz, önceki
//     işlem sürerken gelen Enter yok sayılır (ebeveynin yeniden giriş kapısıyla aynı),
//     odak uyarısı ve tuş yakalama varsayılan olarak kapalıdır (sayfada başka yazı
//     alanları vardır).
//
// Diyalog açıkken (`beklemede`) kuyruk DURAKLAR ve odak uyarısı çıkmaz; diyalog
// kapanınca odak kutuya döner ve kuyruk kaldığı yerden sürer. Diyalog açıkken odak
// bir yazı alanında DEĞİLSE (diyalog paneli, düğme) okuyucunun gönderdiği kod bir
// tampona alınır ve Enter'la kuyruğa girer: diyalog açıkken okutulan kitap sessizce
// kaybolmaz, diyalog kapanınca sırayla işlenir (F6 düzeltme turu). Odak diyalogdaki
// bir yazı alanındaysa tuş o alana gider (kullanıcı yazıyordur). Diyalog yokken odak
// başka bir diyalogun içindeyse tuş yakalanmaz: rakamlar arkadaki kutuya kaçmaz.
//
// Ses: WebAudio ile kısa bir bip (ek dosya yok, çevrimdışı). Tercih bu bilgisayarda
// saklanır (`okumaSesiAcikMi` / `okumaSesiniAyarla`); ses aygıtı yoksa sessiz geçer.
// Dört ses vardır: başarı (ince), uyarı (orta), hata (iki kalın) ve bilgi (iki kısa;
// yazma yapmayan okutma, ör. nüsha durum sorgusu — ödünçle karışmasın diye ayrı).

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import Button from "./Button";
import Icon from "./Icon";
import TextField from "./TextField";

/** Bir okutmanın sonucu — sesi ve kutunun kısa süreli rengini belirler. */
export type OkutmaGeriBildirimi = "basari" | "uyari" | "hata" | "bilgi";

/** Okuyucunun gönderebileceği tek karakter: rakam, Latin harfi, tire. */
const OKUYUCU_KARAKTERI = /^[0-9A-Za-z-]$/;
/** Görsel geri bildirimin süresi (ms). */
export const GERI_BILDIRIM_MS = 900;

export const ODAK_UYARISI =
  "Okutma kutusu odakta değil. Okutmadan önce kutuya dönün; okuyucunun gönderdiği kod başka bir yere yazılabilir.";

const SES_ANAHTARI = "kutuphane-defteri-okuma-sesi";

/** Okuma sesi açık mı? (bu bilgisayarın tercihi; varsayılan açık) */
export function okumaSesiAcikMi(): boolean {
  try {
    return window.localStorage.getItem(SES_ANAHTARI) !== "kapali";
  } catch {
    return true;
  }
}

export function okumaSesiniAyarla(acik: boolean): void {
  try {
    window.localStorage.setItem(SES_ANAHTARI, acik ? "acik" : "kapali");
  } catch {
    /* depolama yoksa tercih bu oturumda kalmaz */
  }
}

let sesBaglami: AudioContext | null = null;

/** Seslerin tonları: [frekans (Hz), başlangıç (sn), süre (sn)]. */
export const OKUMA_TONLARI: Record<
  OkutmaGeriBildirimi,
  ReadonlyArray<readonly [frekans: number, baslangic: number, sure: number]>
> = {
  basari: [[1046, 0, 0.08]],
  uyari: [[660, 0, 0.16]],
  hata: [
    [220, 0, 0.14],
    [220, 0.2, 0.14],
  ],
  bilgi: [
    [784, 0, 0.05],
    [784, 0.09, 0.05],
  ],
};

/** Kısa bip: başarı tek ince ton, uyarı orta ton, hata iki kalın ton, bilgi iki kısa ton. */
export function okumaSesiCal(tur: OkutmaGeriBildirimi): void {
  if (!okumaSesiAcikMi()) return;
  try {
    const Baglam =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Baglam) return;
    sesBaglami ??= new Baglam();
    const baglam = sesBaglami;
    const tonlar = OKUMA_TONLARI[tur];
    for (const [frekans, baslangic, sure] of tonlar) {
      const osilator = baglam.createOscillator();
      const kazanc = baglam.createGain();
      osilator.frequency.value = frekans;
      kazanc.gain.value = 0.08;
      osilator.connect(kazanc).connect(baglam.destination);
      const t = baglam.currentTime + baslangic;
      osilator.start(t);
      osilator.stop(t + sure);
    }
  } catch {
    /* ses aygıtı yok ya da tarayıcı izin vermedi: sessiz geç */
  }
}

/** Odak bir yazı alanında mı? (oradaysa kullanıcı yazıyordur) */
function yaziAlaniMi(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const etiket = el.tagName;
  return etiket === "INPUT" || etiket === "TEXTAREA" || etiket === "SELECT" || el.isContentEditable;
}

/** Odak bir yazı alanında ya da diyalogda mı? (oradaysa tuş kutuya yönlendirilmez) */
function tusYakalanmazMi(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.closest('[role="dialog"]') !== null || yaziAlaniMi(el);
}

const GERI_BILDIRIM_HALKASI: Record<OkutmaGeriBildirimi, string> = {
  basari: "[&_div.flex]:!border-primary [&_div.flex]:ring-2 [&_div.flex]:ring-primary/40",
  uyari: "[&_div.flex]:!border-tertiary [&_div.flex]:ring-2 [&_div.flex]:ring-tertiary/40",
  hata: "[&_div.flex]:!border-error [&_div.flex]:ring-2 [&_div.flex]:ring-error/40",
  bilgi: "[&_div.flex]:!border-secondary [&_div.flex]:ring-2 [&_div.flex]:ring-secondary/40",
};

type OkutmaSonucu = OkutmaGeriBildirimi | void;

export interface BarcodeInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "value" | "onChange" | "defaultValue" | "onSubmit"
> {
  label: string;
  /** Bir okutma: kuyruktan sırayla, önceki bitince çağrılır. Sonuç geri bildirimdir. */
  onOkut: (kod: string) => OkutmaSonucu | Promise<OkutmaSonucu>;
  /** `sira` (varsayılan) ya da `alan` (dosya başındaki not). */
  davranis?: "sira" | "alan";
  /** `alan` davranışında değer ebeveyndedir. */
  value?: string;
  onValueChange?: (deger: string) => void;
  /** Açılışta kendiliğinden odaklanır (varsayılan açık). */
  kendiliginden?: boolean;
  /** Yazı alanı dışında basılan okuyucu tuşunu kutuya yönlendirir. */
  tusYakala?: boolean;
  /** Odak kutudan çıkınca görünür uyarı. */
  odakUyarisi?: boolean;
  /** Diyalog açık: tuş yakalanmaz, uyarı çıkmaz; kapanınca odak kutuya döner. */
  beklemede?: boolean;
  helperText?: ReactNode;
  error?: string;
}

const BarcodeInput = forwardRef<HTMLInputElement, BarcodeInputProps>(function BarcodeInput(
  {
    label,
    onOkut,
    davranis = "sira",
    value,
    onValueChange,
    kendiliginden = true,
    tusYakala,
    odakUyarisi,
    beklemede = false,
    helperText,
    error,
    className = "",
    onFocus,
    onBlur,
    onKeyDown,
    ...rest
  },
  ref,
) {
  const alan = davranis === "alan";
  const yakala = tusYakala ?? !alan;
  const uyar = odakUyarisi ?? !alan;

  const kutuRef = useRef<HTMLInputElement>(null);
  useImperativeHandle(ref, () => kutuRef.current as HTMLInputElement);

  const [icDeger, setIcDeger] = useState("");
  const deger = alan ? (value ?? "") : icDeger;
  const [odakta, setOdakta] = useState(true);
  const [bekleyen, setBekleyen] = useState(0);
  const [isaret, setIsaret] = useState<OkutmaGeriBildirimi | null>(null);

  const sira = useRef<string[]>([]);
  const isleniyor = useRef(false);
  const acik = useRef(true);
  const isaretZamanlayici = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Kuyruk döngüsü her zaman EN SON verilen işleyiciyi çağırır.
  const onOkutRef = useRef(onOkut);
  onOkutRef.current = onOkut;
  // Diyalog açıkken kuyruk durur; döngü bunu her adımda ref'ten okur.
  const beklemedeRef = useRef(beklemede);
  beklemedeRef.current = beklemede;
  // Diyalog açıkken odak yazı alanında değilse okuyucunun gönderdiği karakterler.
  const tampon = useRef("");

  useEffect(() => {
    acik.current = true;
    if (kendiliginden) kutuRef.current?.focus();
    return () => {
      acik.current = false;
      if (isaretZamanlayici.current) clearTimeout(isaretZamanlayici.current);
    };
    // Yalnız takılışta (kendiliğinden odak bir kez).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const geriBildir = useCallback((tur: OkutmaGeriBildirimi) => {
    okumaSesiCal(tur);
    setIsaret(tur);
    if (isaretZamanlayici.current) clearTimeout(isaretZamanlayici.current);
    isaretZamanlayici.current = setTimeout(() => setIsaret(null), GERI_BILDIRIM_MS);
  }, []);

  const calistir = useCallback(
    async (kod: string) => {
      try {
        const sonuc = await onOkutRef.current(kod);
        if (acik.current && sonuc) geriBildir(sonuc);
      } catch {
        // İşleyici kendi hatasını gösterir; kuyruk durmasın.
        if (acik.current) geriBildir("hata");
      }
    },
    [geriBildir],
  );

  const isle = useCallback(async () => {
    if (isleniyor.current) return;
    isleniyor.current = true;
    try {
      // Diyalog açıkken (beklemede) kuyruk DURUR; kapanınca kaldığı yerden sürer.
      while (sira.current.length > 0 && acik.current && !beklemedeRef.current) {
        const siradaki = sira.current.shift() as string;
        setBekleyen(sira.current.length);
        await calistir(siradaki);
      }
    } finally {
      isleniyor.current = false;
    }
  }, [calistir]);

  const kuyrugaAl = useCallback(
    (kod: string) => {
      sira.current.push(kod);
      setBekleyen(sira.current.length);
      void isle();
    },
    [isle],
  );

  // Diyalog kapanınca odak kutuya döner (diyalog odağı açan düğmeye verdikten SONRA)
  // ve diyalog açıkken biriken okutmalar işlenir.
  const oncekiBeklemede = useRef(beklemede);
  useEffect(() => {
    tampon.current = "";
    if (oncekiBeklemede.current && !beklemede) {
      oncekiBeklemede.current = beklemede;
      void isle();
      if (!kendiliginden) return undefined;
      const zamanlayici = setTimeout(() => kutuRef.current?.focus(), 0);
      return () => clearTimeout(zamanlayici);
    }
    oncekiBeklemede.current = beklemede;
    return undefined;
  }, [beklemede, kendiliginden, isle]);

  useEffect(() => {
    if (!yakala) return;
    const tus = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (beklemedeRef.current) {
        // Diyalog açık. Odak kutunun kendisindeyse her şey olağandır (Enter kuyruğa
        // koyar, kuyruk bekler). Başka bir yazı alanındaysa tuş oraya gider (kullanıcı
        // yazıyordur); değilse (diyalog paneli, düğme) okuyucunun kodu tampona alınır ve
        // Enter'la kuyruğa girer — diyalog kapanınca işlenir, sessizce kaybolmaz.
        const aktif = document.activeElement;
        if (aktif === kutuRef.current) return;
        if (yaziAlaniMi(aktif)) {
          tampon.current = "";
          return;
        }
        if (OKUYUCU_KARAKTERI.test(e.key)) {
          // Diyalog okutmanın ORTASINDA açıldıysa kodun başı kutuda kalmıştır: tampona
          // taşınır, kod ikiye bölünmez.
          const yarim = kutuRef.current?.value ?? "";
          if (tampon.current === "" && yarim !== "") {
            tampon.current = yarim;
            setIcDeger("");
          }
          tampon.current += e.key;
          e.preventDefault();
          return;
        }
        if (e.key === "Enter" && tampon.current) {
          e.preventDefault();
          e.stopPropagation();
          const kod = tampon.current.trim();
          tampon.current = "";
          if (kod) kuyrugaAl(kod);
          return;
        }
        if (e.key !== "Shift") tampon.current = "";
        return;
      }
      if (!OKUYUCU_KARAKTERI.test(e.key)) return;
      if (tusYakalanmazMi(document.activeElement)) return;
      kutuRef.current?.focus();
    };
    document.addEventListener("keydown", tus, true);
    return () => document.removeEventListener("keydown", tus, true);
  }, [yakala, kuyrugaAl]);

  const gonder = () => {
    if (alan) {
      // Değer formundur: boş Enter'ı da ebeveyn karşılar (ör. "etiketi okutun" iletisi).
      if (isleniyor.current) return;
      isleniyor.current = true;
      void calistir(deger.trim()).finally(() => {
        isleniyor.current = false;
      });
      return;
    }
    const ham = icDeger.trim();
    // Kutu HEMEN boşalır: okuyucunun sıradaki kodu öncekine eklenmesin.
    setIcDeger("");
    if (!ham) return;
    kuyrugaAl(ham);
  };

  const halka = isaret ? GERI_BILDIRIM_HALKASI[isaret] : "";

  return (
    <div className="space-y-2">
      <TextField
        {...rest}
        className={`${className} ${halka}`.trim()}
        label={label}
        ref={kutuRef}
        value={deger}
        autoComplete="off"
        data-geri-bildirim={isaret ?? undefined}
        onChange={(e) => (alan ? onValueChange?.(e.target.value) : setIcDeger(e.target.value))}
        onFocus={(e) => {
          setOdakta(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setOdakta(false);
          onBlur?.(e);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            gonder();
          }
          onKeyDown?.(e);
        }}
        helperText={helperText}
        error={error}
      />
      {uyar && !odakta && !beklemede && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
        >
          <Icon name="warning" size="lg" className="shrink-0" />
          <span className="min-w-0 flex-1">{ODAK_UYARISI}</span>
          <Button variant="text" icon="barcode_reader" onClick={() => kutuRef.current?.focus()}>
            Kutuya dön
          </Button>
        </div>
      )}
      {!alan && bekleyen > 0 && (
        <p role="status" className="text-body-small text-on-surface-variant">
          Sırada bekleyen okutma: {bekleyen}
        </p>
      )}
    </div>
  );
});

export default BarcodeInput;
