// Kurulum sihirbazı — programın İLK AÇILIŞ ekranı (tasarım §6.3-1, §14.1 F1).
// Üç adım, bu sırayla:
//   1. Yönetici parolası + kurtarma anahtarı — ATLANAMAZ. Parola kurulunca anahtar
//      bir kez gösterilir (yazdır / PDF olarak kaydet / elle yaz); devam için
//      sakladığı kopyadan iki grup geri yazılır, sonra TAM anahtar sunucuda
//      doğrulanıp güvenlik dosyasına damgalanır (F1 eki, 22.09.2026 kararı 2).
//      Anahtar ekranda değilken (pencere kapandı, program çöktü) adım iki yol
//      sunar: kâğıttaki anahtarı yazıp doğrulamak ya da yönetici parolasıyla
//      YENİ anahtar üretmek (eski anahtar geçersizleşir, kayıtlar değişmez).
//   2. Okul bilgileri — okul adı, il, ilçe, müdür, hazırlık sınıfı, kademe, kısa
//      ad, "bu bilgisayar okul demirbaşıdır" onayı (zorunlu) ve demirbaş no.
//   3. Ders yılı, dönemler ve kapalı günler — ders yılı kaydedilip aktifleşince
//      iki takvim yılının resmî ve dini tatilleri eklenir; ara tatil ve yarıyıl
//      Kapalı Günler panelinden (Ayarlar'daki bileşenin aynısı) girilir.
// Kişi aktarımı sihirbazda değildir: Genel Bakış'taki "Başlangıç Yol Haritası"
// kurulumdan sonra sıradaki işleri gösterir.
//
// Durum tek kaynaktan (`GET /setup/status/`) beslenir: adım durumları ve eksik
// adımlar (`missing_steps`) backend'in `setup/complete/` kapısıyla AYNI hesaptır;
// sihirbaz ilk EKSİK adımdan açılır. Parola kurulmadan ve kurtarma anahtarı
// doğrulanmadan ilerlenemez (İleri kapalı, adım rayı tıklanmaz); kapı backend'de de
// vardır (eksik adımda 400 `kurulum_eksik`). Kurulumu bu karardan önce tamamlanmış
// (damgasız) programda ray kilitlenmez; 1. adım yalnız uyarır.

import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import type { KapiYonlendirmesi } from "../../KurulumKapisi";
import { useFormErrors } from "../../hooks/useFormErrors";
import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import KurtarmaAnahtariPaneli from "../guvenlik/KurtarmaAnahtariPaneli";
import KurtarmaAnahtariniDogrulaKarti from "../guvenlik/KurtarmaAnahtariniDogrulaKarti";
import KurtarmaAnahtariniYenileKarti from "../guvenlik/KurtarmaAnahtariniYenileKarti";
import KurtarmaCiktisiKarti from "../guvenlik/KurtarmaCiktisiKarti";
import { guvenlikApi } from "../guvenlik/api";
import {
  bekleyenKurtarmaAnahtari,
  bekleyenKurtarmaAnahtariniYaz,
  useBekleyenKurtarmaAnahtari,
} from "../guvenlik/bekleyenAnahtar";
import {
  DOGRULANMADI_BASLIGI,
  DOGRULANMADI_METNI,
  KURMA_UYARISI,
  YENILEME_METNI,
} from "../guvenlik/metinler";
import DemirbasAlanlari from "../okul/DemirbasAlanlari";
import { KISA_AD_EN_COK, SCHOOL_LEVEL_TR, SETUP_STEPS, okulApi } from "../okul/api";
import type { SchoolLevel, SchoolYear, SetupStatus, SetupStep } from "../okul/api";
import { okulBilgileriHatalari } from "../okul/okulBilgileri";
import KapaliGunlerPaneli from "../takvim/KapaliGunlerPaneli";

const ADIMLAR: readonly { key: SetupStep; label: string; icon: string }[] = [
  { key: "password", label: "Yönetici Parolası", icon: "key" },
  { key: "school", label: "Okul Bilgileri", icon: "school" },
  { key: "calendar", label: "Ders Yılı ve Kapalı Günler", icon: "calendar_month" },
];

const SON_ADIM = ADIMLAR.length - 1;

/** Hata mesajını Türkçeleştirir: ApiError gövdesi varsa onu, yoksa yedek metni verir. */
function hataMesaji(err: unknown, yedek: string): string {
  return err instanceof ApiError ? err.message : yedek;
}

/** Kalıcı hata bandı (snackbar geçici bildirim içindir — kalıcı durum inline gösterilir). */
function HataBandi({ mesaj }: { mesaj: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size="lg" />
      <span>{mesaj}</span>
    </div>
  );
}

/** Bilgilendirme bandı (uyarı/ipucu) — tonal yüzey, ham renk yok. */
function BilgiBandi({ ikon, children }: { ikon: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
      <Icon name={ikon} size="lg" />
      <span>{children}</span>
    </div>
  );
}

/** Sihirbaz ilk EKSİK adımdan açılır (hepsi tamsa son adım: "Kurulumu tamamla"). */
function ilkEksikAdim(s: SetupStatus): number {
  const ilk = SETUP_STEPS.findIndex((adim) => s.missing_steps.includes(adim));
  return ilk === -1 ? SON_ADIM : ilk;
}

/** Okul adımının form değerleri (sihirbaz kabuğunda tutulur: "Kaydet ve devam et" oradadır). */
interface OkulFormu {
  okulAdi: string;
  il: string;
  ilce: string;
  mudur: string;
  hazirlikVar: boolean;
  kademe: SchoolLevel | "";
  kisaAd: string;
  demirbasOnayi: boolean;
  demirbasNo: string;
}

const BOS_OKUL_FORMU: OkulFormu = {
  okulAdi: "",
  il: "",
  ilce: "",
  mudur: "",
  hazirlikVar: false,
  kademe: "",
  kisaAd: "",
  demirbasOnayi: false,
  demirbasNo: "",
};

export default function KurulumPage() {
  const navigate = useNavigate();
  const snackbar = useSnackbar();
  // Kapı yönlendirmesiyle mi gelindi? (KurulumKapisi gezinme durumunda taşır.)
  const kapidanGelenYol =
    (useLocation().state as KapiYonlendirmesi | null)?.kapiYonlendirdi ?? null;

  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [adim, setAdim] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [okul, setOkul] = useState<OkulFormu>(BOS_OKUL_FORMU);

  // Parola kurulur kurulmaz (ya da anahtar yenilenince) gelen kurtarma anahtarı
  // YALNIZ bellekte, 1. adımda durur; kullanıcı doğrulayıp devam edince bırakılır
  // (sunucuda saklanmaz). Anahtar bu bileşenin durumunda DEĞİL, rota ağacının
  // dışındaki modül belleğindedir (`guvenlik/bekleyenAnahtar`): sayfa görevli
  // kipine geçiş, Kilitle ya da menü gezinmesiyle sökülse de anahtar kaybolmaz ve
  // sihirbaz yeniden açılınca 1. adımda yeniden gösterilir. Doğrulama durumu ise
  // bileşendedir: yeniden açılan sihirbaz iki grubu yeniden sorar (sunucu damgası
  // zaten yazıldıysa anahtar bırakılır).
  const kurtarmaAnahtari = useBekleyenKurtarmaAnahtari();
  const [anahtarDogrulandi, setAnahtarDogrulandi] = useState(false);

  const [busy, setBusy] = useState(false);
  const [adimHatasi, setAdimHatasi] = useState<string | null>(null);
  const { errors, applyApiError, clearErrors, setFieldError } = useFormErrors<string>();

  /** Durum özetini tazeler (adım rozetleri, eksik adımlar, sayımlar bundan okur). */
  const durumTazele = useCallback(async () => {
    try {
      setStatus(await okulApi.getSetupStatus());
    } catch {
      /* durum tazelemesi başarısız olsa da asıl işlem tamamlanmıştır */
    }
  }, []);

  useEffect(() => {
    let iptal = false;
    Promise.all([okulApi.getSetupStatus(), okulApi.getSchoolConfig()])
      .then(([s, c]) => {
        if (iptal) return;
        setStatus(s);
        // Parola kurulu değilse bekleyen anahtarın karşılığı yoktur (ör. güvenlik
        // dosyası sıfırlandı); anahtar sunucuda doğrulandıysa bellekte tutulmaz.
        if (!s.password_set || s.recovery_key_confirmed) bekleyenKurtarmaAnahtariniYaz(null);
        setOkul({
          okulAdi: c.school_name,
          il: c.province,
          ilce: c.district,
          mudur: c.principal_name,
          hazirlikVar: c.has_prep_class,
          kademe: c.kademe,
          kisaAd: c.kisa_ad,
          demirbasOnayi: c.demirbas_onayi,
          demirbasNo: c.demirbas_no,
        });
        // Doğrulanmamış anahtar bekliyorsa sihirbaz 1. adımda, anahtarla açılır.
        setAdim(bekleyenKurtarmaAnahtari() !== null ? 0 : ilkEksikAdim(s));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setLoadError(hataMesaji(e, "Kurulum durumu yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setLoading(false);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const parolaKurulu = status?.password_set ?? false;
  // Sunucu damgası: anahtarın saklandığı doğrulandı mı? (kurulum kapısının 2. koşulu)
  const anahtarSaklandi = status?.recovery_key_confirmed ?? false;
  // Anahtar gösterildi ama saklandığı henüz doğrulanmadı: 1. adımdan çıkılmaz.
  const anahtarBekliyor = kurtarmaAnahtari !== null && !anahtarDogrulandi;

  // Adım rozetleri: her adımın "tamam" ölçütü backend durumundan türetilir.
  const tamam = useMemo(
    () => [
      parolaKurulu && anahtarSaklandi && !anahtarBekliyor,
      status?.school_info_complete ?? false,
      status?.active_school_year?.terms_ready ?? false,
    ],
    [status, parolaKurulu, anahtarSaklandi, anahtarBekliyor],
  );

  // Parola adımı kapısı (kod kapısı): parola kurulmadan ya da anahtar doğrulanmadan
  // hiçbir adıma geçilmez — ne İleri ile ne de adım rayından. Kurulumu önceden
  // tamamlanmış (damgasız) programda ray kilitlenmez; 1. adım uyarı gösterir.
  const parolaKapisiKapali =
    !parolaKurulu || anahtarBekliyor || (!anahtarSaklandi && !status?.setup_completed);

  const stepperItems: StepperItem[] = ADIMLAR.map((a, i) => ({
    key: a.key,
    label: a.label,
    icon: a.icon,
    status: i === adim ? "current" : tamam[i] ? "done" : "upcoming",
  }));

  const adimaGit = (hedef: number) => {
    setAdimHatasi(null);
    if (hedef > 0 && parolaKapisiKapali) return;
    if (adim === 0 && kurtarmaAnahtari !== null && anahtarDogrulandi) {
      // Anahtar saklandı ve doğrulandı: bellekte tutulmaz.
      bekleyenKurtarmaAnahtariniYaz(null);
      setAnahtarDogrulandi(false);
    }
    setAdim(Math.max(0, Math.min(hedef, SON_ADIM)));
  };

  const parolaKuruldu = async (anahtar: string) => {
    bekleyenKurtarmaAnahtariniYaz(anahtar);
    setAnahtarDogrulandi(false);
    await durumTazele();
  };

  // Panel `true`yu ancak sunucu damgayı yazınca bildirir: durum hemen güncellenir
  // (İleri beklemeden açılır), ardından sunucudan tazelenir.
  const onDogrulama = useCallback(
    (dogru: boolean) => {
      setAnahtarDogrulandi(dogru);
      if (!dogru) return;
      setStatus((s) =>
        s === null
          ? s
          : {
              ...s,
              recovery_key_confirmed: true,
              missing_steps: s.missing_steps.filter((a) => a !== "password"),
            },
      );
      void durumTazele();
    },
    [durumTazele],
  );

  const yenilendi = () => {
    // Yeni anahtar bekleyen belleğe yazıldı (kart yazar); panel onu gösterir.
    setAnahtarDogrulandi(false);
    void durumTazele();
  };

  const okulBilgileriniKaydet = async () => {
    clearErrors();
    // İstemci tarafı zorunlu alan denetimi — backend `missing_school_fields` ile aynı küme.
    const hatalar = okulBilgileriHatalari(okul);
    if (Object.keys(hatalar).length > 0) {
      for (const [alan, mesaj] of Object.entries(hatalar)) setFieldError(alan, mesaj);
      setAdimHatasi("Zorunlu alanları doldurun.");
      return;
    }
    setBusy(true);
    setAdimHatasi(null);
    try {
      await okulApi.updateSchoolConfig({
        school_name: okul.okulAdi.trim(),
        province: okul.il.trim(),
        district: okul.ilce.trim(),
        principal_name: okul.mudur.trim(),
        has_prep_class: okul.hazirlikVar,
        kademe: okul.kademe,
        kisa_ad: okul.kisaAd.trim(),
        demirbas_onayi: okul.demirbasOnayi,
        demirbas_no: okul.demirbasNo.trim(),
      });
      snackbar.success("Okul bilgileri kaydedildi.");
      await durumTazele();
      setAdim(2);
    } catch (e) {
      applyApiError(e);
      setAdimHatasi(hataMesaji(e, "Okul bilgileri kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  const kurulumuTamamla = async () => {
    setBusy(true);
    setAdimHatasi(null);
    try {
      await okulApi.completeSetup();
      snackbar.success("Kurulum tamamlandı.");
      navigate("/");
    } catch (e) {
      // Backend eksik adımı adıyla söyler (400 `kurulum_eksik`).
      setAdimHatasi(hataMesaji(e, "Kurulum tamamlanamadı."));
      await durumTazele();
      setBusy(false);
    }
  };

  const eksikAdimVar = (status?.missing_steps.length ?? 1) > 0;
  let ileriIpucu: string | null = null;
  if (adim === 0 && !parolaKurulu) ileriIpucu = "Devam etmek için yönetici parolasını kurun.";
  else if (adim === 0 && anahtarBekliyor)
    ileriIpucu = "Devam etmek için kurtarma anahtarını sakladığınızı doğrulayın.";
  else if (adim === 0 && parolaKapisiKapali)
    ileriIpucu = "Devam etmek için kurtarma anahtarını doğrulayın ya da yenisini üretin.";
  else if (adim === SON_ADIM && eksikAdimVar)
    ileriIpucu = "Kurulumu tamamlamak için eksik adımları bitirin.";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="kd-page-header">
        <div>
          <h1 className="kd-page-title">Kurulum Sihirbazı</h1>
          <p className="kd-page-description">
            Programı kullanmaya başlamadan önce üç adımı tamamlayın: yönetici parolası, okul
            bilgileri, ders yılı ve kapalı günler. Okul bilgilerini ve takvimi daha sonra Ayarlar
            ekranından değiştirebilirsiniz.
          </p>
        </div>
      </div>

      {kapidanGelenYol !== null && (
        <BilgiBandi ikon="lock">
          Kurulum tamamlanmadan diğer ekranlar açılmaz; bu yüzden buraya getirildiniz. Aşağıdaki
          adımları bitirip “Kurulumu tamamla” dediğinizde menüdeki tüm bölümler açılır.
        </BilgiBandi>
      )}

      {status?.setup_completed && (
        <div className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container">
          <Icon name="check_circle" size="lg" />
          <span>
            Kurulum daha önce tamamlanmıştı. Bilgileri buradan gözden geçirip güncelleyebilirsiniz.
          </span>
        </div>
      )}

      <Stepper
        items={stepperItems}
        ariaLabel="Kurulum adımları"
        onSelect={parolaKapisiKapali ? undefined : (_key, index) => adimaGit(index)}
      />

      {loadError && <HataBandi mesaj={loadError} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : (
        !loadError &&
        status && (
          <>
            {adim === 0 && (
              <ParolaAdimi
                status={status}
                kurtarmaAnahtari={kurtarmaAnahtari}
                okulAdi={okul.okulAdi}
                onKuruldu={parolaKuruldu}
                onDogrulama={onDogrulama}
                onKagittanDogrulandi={() => void durumTazele()}
                onYenilendi={yenilendi}
              />
            )}
            {adim === 1 && (
              <OkulBilgileriAdimi
                form={okul}
                errors={errors}
                onChange={(degisiklik) => setOkul((f) => ({ ...f, ...degisiklik }))}
              />
            )}
            {adim === 2 && <TakvimAdimi status={status} onChanged={durumTazele} />}

            {adimHatasi && <HataBandi mesaj={adimHatasi} />}

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button
                variant="text"
                icon="arrow_back"
                onClick={() => adimaGit(adim - 1)}
                disabled={adim === 0 || busy}
              >
                Geri
              </Button>
              <div className="flex flex-wrap items-center justify-end gap-3">
                {ileriIpucu && (
                  <p className="text-body-small text-on-surface-variant">{ileriIpucu}</p>
                )}
                {adim === 0 && (
                  <Button
                    icon="arrow_forward"
                    onClick={() => adimaGit(1)}
                    disabled={busy || parolaKapisiKapali}
                  >
                    Devam
                  </Button>
                )}
                {adim === 1 && (
                  <Button
                    icon="arrow_forward"
                    onClick={() => void okulBilgileriniKaydet()}
                    disabled={busy}
                  >
                    {busy ? "Kaydediliyor…" : "Kaydet ve devam et"}
                  </Button>
                )}
                {adim === SON_ADIM && (
                  <Button
                    icon="check_circle"
                    onClick={() => void kurulumuTamamla()}
                    disabled={busy || eksikAdimVar}
                  >
                    {busy ? "Tamamlanıyor…" : "Kurulumu tamamla"}
                  </Button>
                )}
              </div>
            </div>
          </>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. adım — Yönetici parolası + kurtarma anahtarı
// ---------------------------------------------------------------------------

interface ParolaAdimiProps {
  status: SetupStatus;
  kurtarmaAnahtari: string | null;
  okulAdi: string;
  onKuruldu: (anahtar: string) => Promise<void>;
  onDogrulama: (dogru: boolean) => void;
  /** Kâğıttaki anahtar yazılıp sunucuda doğrulandı (durum tazelenir). */
  onKagittanDogrulandi: () => void;
  /** Yeni anahtar üretildi ve bekleyen belleğe yazıldı (panel onu gösterir). */
  onYenilendi: () => void;
}

/** Sihirbazdaki yenileme kartının vurgusu (sözleşme: "kaydedemediyseniz yenisini üretin"). */
const SIHIRBAZ_YENILEME_METNI = `Anahtarı kaydedemediyseniz yenisini üretin. ${YENILEME_METNI}`;

function ParolaAdimi({
  status,
  kurtarmaAnahtari,
  okulAdi,
  onKuruldu,
  onDogrulama,
  onKagittanDogrulandi,
  onYenilendi,
}: ParolaAdimiProps) {
  const snackbar = useSnackbar();
  const [parola, setParola] = useState("");
  const [parolaTekrar, setParolaTekrar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  if (kurtarmaAnahtari !== null) {
    return (
      <KurtarmaAnahtariPaneli
        anahtar={kurtarmaAnahtari}
        okulAdi={okulAdi}
        onDogrulama={onDogrulama}
      />
    );
  }

  if (status.password_set && !status.recovery_key_confirmed) {
    // Anahtar ekranda değil (pencere kapandı, program çöktü) ve saklandığı doğrulanmadı.
    return (
      <div className="space-y-4">
        <div className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container">
          <Icon name="key_off" size="lg" />
          <span>
            <strong>{DOGRULANMADI_BASLIGI}.</strong> {DOGRULANMADI_METNI}
          </span>
        </div>
        <KurtarmaAnahtariniDogrulaKarti onDogrulandi={onKagittanDogrulandi} />
        <KurtarmaAnahtariniYenileKarti
          aciklama={SIHIRBAZ_YENILEME_METNI}
          onYenilendi={onYenilendi}
        />
      </div>
    );
  }

  if (status.password_set) {
    return (
      <div className="space-y-4">
        <Card elevation={1} className="p-6">
          <div className="flex items-center gap-3">
            <Icon name="verified_user" className="text-primary" />
            <p className="text-title-medium text-on-surface">1. Yönetici Parolası</p>
          </div>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            Parola kurulu, kurtarma anahtarının saklandığı doğrulandı. Anahtarı müdürlükte kapalı
            zarfta saklayın. Parolayı Ayarlar → Güvenlik bölümünden değiştirebilirsiniz; parola
            kaldırılamaz. Anahtar kaybolursa aynı bölümden yenisini üretebilirsiniz.
          </p>
        </Card>
        <KurtarmaCiktisiKarti />
      </div>
    );
  }

  async function kur(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    if (parola !== parolaTekrar) {
      setHata("Parolalar eşleşmedi.");
      return;
    }
    setCalisiyor(true);
    try {
      const sonuc = await guvenlikApi.kur(parola);
      setParola("");
      setParolaTekrar("");
      snackbar.success("Yönetici parolası kuruldu.");
      await onKuruldu(sonuc.recovery_key);
    } catch (err) {
      setHata(hataMesaji(err, "Yönetici parolası kurulamadı."));
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">1. Yönetici Parolası</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">{KURMA_UYARISI}</p>
      <p className="mt-2 text-body-medium text-on-surface-variant">
        Parola kurulunca bir kurtarma anahtarı gösterilir. Parola unutulursa kayıtlara erişmenin tek
        yolu odur; bir sonraki ekranda onu saklamanız istenecek.
      </p>
      <form onSubmit={kur} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TextField
          label="Yönetici parolası"
          type="password"
          value={parola}
          onChange={(e) => setParola(e.target.value)}
          autoComplete="new-password"
          helperText="En az 8 karakter."
          required
        />
        <TextField
          label="Parola (tekrar)"
          type="password"
          value={parolaTekrar}
          onChange={(e) => setParolaTekrar(e.target.value)}
          autoComplete="new-password"
          error={hata ?? undefined}
          required
        />
        <div className="flex justify-end sm:col-span-2">
          <Button type="submit" icon="lock" disabled={calisiyor || !parola || !parolaTekrar}>
            {calisiyor ? "Kuruluyor…" : "Yönetici parolasını kur"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 2. adım — Okul bilgileri (antet, hazırlık, kademe, kısa ad, demirbaş)
// ---------------------------------------------------------------------------

interface OkulBilgileriProps {
  form: OkulFormu;
  errors: Partial<Record<string, string>>;
  onChange: (degisiklik: Partial<OkulFormu>) => void;
}

const KADEME_SECENEKLERI = (Object.keys(SCHOOL_LEVEL_TR) as SchoolLevel[]).map((k) => ({
  value: k,
  label: SCHOOL_LEVEL_TR[k],
}));

function OkulBilgileriAdimi({ form, errors, onChange }: OkulBilgileriProps) {
  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">2. Okul Bilgileri</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Bu bilgiler programın bastığı evrakın antedinde, etiketlerde ve üye kartlarında kullanılır.
        Hazırlık sınıfı varsa sınıf düzeylerine Hazırlık eklenir.
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TextField
          className="sm:col-span-2"
          label="Okul adı"
          required
          value={form.okulAdi}
          onChange={(e) => onChange({ okulAdi: e.target.value })}
          error={errors.school_name}
          placeholder="Örn. Örnek Anadolu Lisesi"
          helperText="Evrak antedinin ilk satırı."
        />
        <TextField
          label="Kısa ad"
          required
          maxLength={KISA_AD_EN_COK}
          value={form.kisaAd}
          onChange={(e) => onChange({ kisaAd: e.target.value })}
          error={errors.kisa_ad}
          placeholder="Örn. Örnek AL"
          helperText={`Etiketlerde ve üye kartlarında basılır; en çok ${KISA_AD_EN_COK} karakter.`}
        />
        <Select
          label="Kademe"
          required
          value={form.kademe}
          onChange={(e) => onChange({ kademe: e.target.value as SchoolLevel | "" })}
          placeholder="Seçin"
          options={KADEME_SECENEKLERI}
          error={errors.kademe}
          helperText="Kayıp kitap bedeli ve sınıf kitaplığı kuralları kademeye göre uygulanır."
        />
        <TextField
          label="İl"
          value={form.il}
          onChange={(e) => onChange({ il: e.target.value })}
          error={errors.province}
        />
        <TextField
          label="İlçe"
          value={form.ilce}
          onChange={(e) => onChange({ ilce: e.target.value })}
          error={errors.district}
        />
        <TextField
          label="Okul müdürü"
          value={form.mudur}
          onChange={(e) => onChange({ mudur: e.target.value })}
          error={errors.principal_name}
          helperText="Evrak imza bloğunda görünür; boş bırakılırsa şablon yer tutucu basar."
        />
        <Select
          label="Hazırlık sınıfı"
          value={form.hazirlikVar ? "1" : "0"}
          onChange={(e) => onChange({ hazirlikVar: e.target.value === "1" })}
          options={[
            { value: "0", label: "Yok" },
            { value: "1", label: "Var" },
          ]}
          error={errors.has_prep_class}
          helperText="Varsa sınıf düzeylerine Hazırlık eklenir; yoksa program hazırlık satırı üretmez."
        />
      </div>

      <DemirbasAlanlari
        onay={form.demirbasOnayi}
        no={form.demirbasNo}
        errors={errors}
        onOnay={(v) => onChange({ demirbasOnayi: v })}
        onNo={(v) => onChange({ demirbasNo: v })}
      />
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 3. adım — Ders yılı, dönemler ve kapalı günler
// ---------------------------------------------------------------------------

/** Bugüne göre makul ders yılı önerisi: eylül ve sonrası yeni yılı başlatır. */
function varsayilanDersYili(): {
  ad: string;
  baslangic: string;
  bitis: string;
  birinciDonemBitis: string;
  ikinciDonemBaslangic: string;
} {
  const bugun = new Date();
  const yil = bugun.getMonth() >= 8 ? bugun.getFullYear() : bugun.getFullYear() - 1;
  return {
    ad: `${yil}-${yil + 1}`,
    baslangic: `${yil}-09-01`,
    bitis: `${yil + 1}-06-30`,
    birinciDonemBitis: `${yil + 1}-01-16`,
    ikinciDonemBaslangic: `${yil + 1}-02-02`,
  };
}

function takvimYillari(baslangic: string, bitis: string): number[] {
  const ilk = Number(baslangic.slice(0, 4));
  const son = Number(bitis.slice(0, 4));
  const yillar: number[] = [];
  for (let y = ilk; y <= son; y += 1) yillar.push(y);
  return yillar;
}

function TakvimAdimi({
  status,
  onChanged,
}: {
  status: SetupStatus;
  onChanged: () => Promise<void>;
}) {
  const aktif = status.active_school_year;
  const yillar = useMemo(
    () => (aktif ? takvimYillari(aktif.start_date, aktif.end_date) : []),
    [aktif],
  );
  const [gosterilenYil, setGosterilenYil] = useState<number | null>(null);
  const yil = gosterilenYil !== null && yillar.includes(gosterilenYil) ? gosterilenYil : yillar[0];

  return (
    <div className="space-y-4">
      <DersYiliAdimi status={status} onChanged={onChanged} />

      {aktif && yil !== undefined && (
        <Card elevation={1} className="p-6">
          <p className="text-title-medium text-on-surface">Kapalı Günler</p>
          <p className="mt-1 text-body-medium text-on-surface-variant">
            Ders yılı kaydedilince iki takvim yılının resmî ve dini tatilleri kendiliğinden eklenir.
            Ara tatil ve yarıyılı “öğrenciye kapalı gün” olarak girin; iade tarihi kapalı bir güne
            denk gelirse izleyen ilk açık güne kayar. Kapalı günleri daha sonra Ayarlar → Kapalı
            Günler'den de düzenleyebilirsiniz.
          </p>
          <div className="mt-4">
            <KapaliGunlerPaneli
              yil={yil}
              yillar={yillar}
              onYilChange={setGosterilenYil}
              baslikGizli
              onDegisti={() => void onChanged()}
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function DersYiliAdimi({
  status,
  onChanged,
}: {
  status: SetupStatus;
  onChanged: () => Promise<void>;
}) {
  const varsayilan = useMemo(varsayilanDersYili, []);
  const [yillar, setYillar] = useState<SchoolYear[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uyari, setUyari] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ad, setAd] = useState(varsayilan.ad);
  const [baslangic, setBaslangic] = useState(varsayilan.baslangic);
  const [bitis, setBitis] = useState(varsayilan.bitis);
  const [birinciDonemBitis, setBirinciDonemBitis] = useState(varsayilan.birinciDonemBitis);
  const [ikinciDonemBaslangic, setIkinciDonemBaslangic] = useState(varsayilan.ikinciDonemBaslangic);
  const { errors, applyApiError, clearErrors } = useFormErrors<string>();
  const snackbar = useSnackbar();
  const aktif = status.active_school_year;

  const yukle = useCallback(() => {
    setLoading(true);
    okulApi
      .listSchoolYears()
      .then((r) => {
        setYillar(r);
        setError(null);
      })
      .catch((e: unknown) => setError(hataMesaji(e, "Ders yılları yüklenemedi.")))
      .finally(() => setLoading(false));
  }, []);
  useEffect(yukle, [yukle]);

  /**
   * Sihirbaz ders yılının İKİ takvim yılını da tohumlar (resmî + dini tatiller;
   * fikirdeş). Yalnız ders yılı oluşturulunca ya da aktifleşince koşar: sonradan
   * silinen bir tatil sihirbaz her açıldığında geri gelmesin.
   */
  const tatilleriEkle = async (yil: SchoolYear) => {
    const eksikDini: number[] = [];
    for (const takvimYili of takvimYillari(yil.start_date, yil.end_date)) {
      const sonuc = await okulApi.seedHolidays(takvimYili);
      if (!sonuc.religious_available) eksikDini.push(takvimYili);
    }
    setUyari(
      eksikDini.length > 0
        ? `Programda ${eksikDini.join(" ve ")} yılının dini bayram tarihleri yok; Diyanet takvimindeki tarihleri “Dini bayram” türünde elle ekleyin.`
        : null,
    );
  };

  const olustur = async () => {
    setBusy(true);
    setError(null);
    clearErrors();
    try {
      // Sihirbazda oluşturulan yıl dönemleriyle kurulur ve doğrudan aktifleştirilir.
      const olusan = await okulApi.createSchoolYear({
        name: ad.trim(),
        start_date: baslangic,
        end_date: bitis,
      });
      await okulApi.configureSchoolTerms(olusan.id, {
        first_term_end: birinciDonemBitis,
        second_term_start: ikinciDonemBaslangic,
      });
      await okulApi.activateSchoolYear(olusan.id);
      await tatilleriEkle(olusan);
      snackbar.success("Ders yılı oluşturuldu, aktifleştirildi; resmî ve dini tatiller eklendi.");
      yukle();
      await onChanged();
    } catch (e) {
      applyApiError(e);
      setError(hataMesaji(e, "Ders yılı oluşturulamadı."));
    } finally {
      setBusy(false);
    }
  };

  const aktiflestir = async (yil: SchoolYear) => {
    setBusy(true);
    setError(null);
    try {
      await okulApi.activateSchoolYear(yil.id);
      await tatilleriEkle(yil);
      snackbar.success(`${yil.name} ders yılı aktifleştirildi.`);
      yukle();
      await onChanged();
    } catch (e) {
      setError(hataMesaji(e, "Ders yılı aktifleştirilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">3. Ders Yılı</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Şube kataloğu ve e-Okul aktarımı aktif ders yılına bağlanır. Aynı anda yalnız bir yıl
          aktif olabilir; kurulumun tamamlanması için aktif yılın iki döneminin tarihleri tanımlı
          olmalıdır.
        </p>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : yillar.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Henüz ders yılı tanımlanmamış. Aşağıdaki formla ilk yılı oluşturun.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-outline-variant/50">
            {yillar.map((y) => (
              <li key={y.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-body-medium text-on-surface">
                    {y.name}
                    {y.is_active && (
                      <span className="inline-flex items-center rounded-shape-xl bg-primary-container px-2 py-0.5 text-label-small text-on-primary-container">
                        Aktif
                      </span>
                    )}
                  </p>
                  <p className="text-label-small text-on-surface-variant">
                    {formatDate(y.start_date)} – {formatDate(y.end_date)}
                  </p>
                </div>
                {!y.is_active && (
                  <Button
                    variant="text"
                    icon="check"
                    onClick={() => void aktiflestir(y)}
                    disabled={busy}
                  >
                    Aktifleştir
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {uyari && (
          <div className="mt-4">
            <BilgiBandi ikon="warning">{uyari}</BilgiBandi>
          </div>
        )}
      </Card>

      {aktif && !aktif.terms_ready && (
        <DonemFormu
          yilId={aktif.id}
          yilAdi={aktif.name}
          baslangic={aktif.start_date}
          onKaydedildi={onChanged}
        />
      )}

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Yeni Ders Yılı</p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <TextField
            label="Ad"
            required
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            error={errors.name}
            helperText="Örn. 2026-2027"
          />
          <TextField
            label="Başlangıç"
            type="date"
            required
            value={baslangic}
            onChange={(e) => {
              const value = e.target.value;
              setBaslangic(value);
              const year = Number(value.slice(0, 4));
              if (Number.isFinite(year)) {
                setBirinciDonemBitis(`${year + 1}-01-16`);
                setIkinciDonemBaslangic(`${year + 1}-02-02`);
              }
            }}
            error={errors.start_date}
          />
          <TextField
            label="Bitiş"
            type="date"
            required
            value={bitis}
            onChange={(e) => setBitis(e.target.value)}
            error={errors.end_date}
          />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField
            label="1. dönem bitişi"
            type="date"
            required
            value={birinciDonemBitis}
            onChange={(e) => setBirinciDonemBitis(e.target.value)}
            error={errors.first_term_end}
          />
          <TextField
            label="2. dönem başlangıcı"
            type="date"
            required
            value={ikinciDonemBaslangic}
            onChange={(e) => setIkinciDonemBaslangic(e.target.value)}
            error={errors.second_term_start}
          />
        </div>
        <p className="mt-2 text-label-small text-on-surface-variant">
          Yarıyıl tatili 1. dönemin bitişiyle 2. dönemin başlangıcı arasında kalır.
        </p>
        {error && (
          <div className="mt-4">
            <HataBandi mesaj={error} />
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <Button
            icon="calendar_add_on"
            onClick={() => void olustur()}
            disabled={
              busy ||
              !ad.trim() ||
              !baslangic ||
              !bitis ||
              !birinciDonemBitis ||
              !ikinciDonemBaslangic
            }
          >
            {busy ? "Kaydediliyor…" : "Ders yılını kaydet ve aktifleştir"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

/** Aktif yılın dönemleri tanımlı değilse (ör. Ayarlar'dan eklenmiş yıl) dönem formu. */
function DonemFormu({
  yilId,
  yilAdi,
  baslangic,
  onKaydedildi,
}: {
  yilId: number;
  yilAdi: string;
  baslangic: string;
  onKaydedildi: () => Promise<void>;
}) {
  const ilkYil = Number(baslangic.slice(0, 4));
  const [birinciBitis, setBirinciBitis] = useState(`${ilkYil + 1}-01-16`);
  const [ikinciBaslangic, setIkinciBaslangic] = useState(`${ilkYil + 1}-02-02`);
  const [hata, setHata] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  const kaydet = async () => {
    setBusy(true);
    setHata(null);
    try {
      await okulApi.configureSchoolTerms(yilId, {
        first_term_end: birinciBitis,
        second_term_start: ikinciBaslangic,
      });
      snackbar.success("Dönem tarihleri kaydedildi.");
      await onKaydedildi();
    } catch (e) {
      setHata(hataMesaji(e, "Dönem tarihleri kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">{yilAdi} Dönemleri</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Aktif ders yılının dönem tarihleri tanımlı değil. Kurulumu tamamlamak için iki dönemin
        tarihlerini girin.
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TextField
          label="1. dönem bitişi"
          type="date"
          required
          value={birinciBitis}
          onChange={(e) => setBirinciBitis(e.target.value)}
        />
        <TextField
          label="2. dönem başlangıcı"
          type="date"
          required
          value={ikinciBaslangic}
          onChange={(e) => setIkinciBaslangic(e.target.value)}
        />
      </div>
      {hata && (
        <div className="mt-4">
          <HataBandi mesaj={hata} />
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <Button
          icon="check"
          onClick={() => void kaydet()}
          disabled={busy || !birinciBitis || !ikinciBaslangic}
        >
          {busy ? "Kaydediliyor…" : "Dönemleri kaydet"}
        </Button>
      </div>
    </Card>
  );
}
