// Ayarlar → Ağ Kataloğu (tasarım §5.2, §5.4, §5.6). Yalnız yönetici kipinde
// görünür (Ayarlar zaten yönetici ekranıdır; uç görevli kipinde 403 döner).
//
// * Aç/kapat: masaüstü denetçisi üzerinden (T16); ayar kalıcıdır, program
//   yeniden açıldığında da uygulanır.
// * İlk açılışta ADIM ADIM yönlendirme (§5.2): afiş hiç basılmamışken (katalog
//   açıldıktan sonra da) sekmenin başında "Ağ Kataloğunu Açmadan Önce" adımları durur —
//   BTR görüşmesi ve bilgi notu, güvenlik duvarı, adres, açma, afiş ve yer
//   imleri. Afiş basıldıktan sonra adımlar gizlenir.
// * Port: değişiklik Windows'ta güvenlik duvarı kuralını ve kurucunun okuduğu
//   değeri de yazan UAC adımından geçer (§5.7); bu yüzden form alanı değil ayrı
//   bir diyalogdur ve kaydetme gövdesine GİRMEZ.
// * Dinleme kipi ve IP, tahta ağı blokları, vitrin, konu dizini, kütüphane
//   saatleri, uyku engelleme: kısmi PUT (gönderilmeyen alana dokunulmaz).

import { useEffect, useId, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link } from "react-router-dom";

import { useFormErrors } from "../../hooks/useFormErrors";
import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import {
  AG_DOKTORU_ADRESI,
  BILGI_NOTU_BELGE_ADI,
  DINLEME_KIPI_TR,
  PORT_ALT,
  PORT_UST,
  agKataloguApi,
  belgeDosyaAdi,
  katalogKapatilabilir,
} from "./api";
import type { DinlemeKipi, IpAdaylari, KatalogAyari, KatalogAyariGovde } from "./api";
import { DurumRozeti, KomutKutusu, MasaustuYokBandi, useAgDurumu } from "./ortak";

function hataMetni(e: unknown, yedek: string): string {
  return e instanceof ApiError && e.message ? e.message : yedek;
}

/** Tahta ağı blokları: satır ya da virgülle ayrılmış; boşlar atılır. */
export function bloklariAyir(metin: string): string[] {
  return metin
    .split(/[\n,]/)
    .map((b) => b.trim())
    .filter(Boolean);
}

function Onay({
  label,
  checked,
  onChange,
  helperText,
}: {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  helperText?: string;
}) {
  return (
    <div>
      <label className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="size-5 shrink-0 accent-primary"
        />
        {label}
      </label>
      {helperText && <p className="text-body-small text-on-surface-variant">{helperText}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// İlk açılış adımları
// ---------------------------------------------------------------------------

function Adim({
  no,
  baslik,
  tamam,
  children,
}: {
  no: number;
  baslik: string;
  tamam?: boolean;
  children: ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className={`flex size-8 shrink-0 items-center justify-center rounded-full text-label-large ${
          tamam ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
        }`}
      >
        {tamam ? <Icon name="check" size="base" /> : no}
      </span>
      <div className="min-w-0 flex-1 space-y-2 text-body-medium text-on-surface-variant">
        <p className="text-label-large text-on-surface">
          {baslik}
          {tamam && <span className="sr-only"> (tamam)</span>}
        </p>
        {children}
      </div>
    </li>
  );
}

function IlkAcilisAdimlari({
  ayar,
  duvarGecti,
  linuxKomutu,
  windows,
  masaustu,
  mesgul,
  acik,
  ayarAcik,
  onAc,
}: {
  ayar: KatalogAyari;
  duvarGecti: boolean | null;
  linuxKomutu: string | null;
  windows: boolean;
  masaustu: boolean;
  mesgul: boolean;
  /** Katalog şu an okul ağında açık. */
  acik: boolean;
  /** Ayar açık (açık ya da açılamamış): 4. adımın düğmesi yerine durum yazılır. */
  ayarAcik: boolean;
  onAc: () => void;
}) {
  const snackbar = useSnackbar();
  const [basiliyor, setBasiliyor] = useState(false);
  const adresSecildi =
    ayar.dinleme_kipi === "ALL" || (ayar.dinleme_kipi === "SELECTED" && ayar.secili_ip !== "");

  async function notuBas() {
    setBasiliyor(true);
    try {
      saveBlob(await agKataloguApi.bilgiNotu(), belgeDosyaAdi(BILGI_NOTU_BELGE_ADI, "pdf"));
      snackbar.success("Ağ Hizmeti Bilgi Notu hazırlandı.");
    } catch (e) {
      snackbar.error(hataMetni(e, "Ağ Hizmeti Bilgi Notu üretilemedi."));
    } finally {
      setBasiliyor(false);
    }
  }

  return (
    <Card elevation={1} className="space-y-4 p-6">
      <div>
        <h2 className="text-title-medium text-on-surface">Ağ Kataloğunu Açmadan Önce</h2>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Ağ Kataloğu okul ağına bu bilgisayarın bir portundan hizmet verir. İlk açılışta adımları
          sırayla izleyin; afiş basıldıktan sonra bu kutu gizlenir.
        </p>
      </div>
      <ol className="space-y-4">
        <Adim no={1} baslik="BTR'yle görüşün">
          <p>
            Okulun bilişim teknolojileri rehber öğretmeniyle (BTR) portu, güvenlik duvarı kuralını
            ve bu bilgisayarın ağ adresinin sabit kalmasını (DHCP'de sabit adres) konuşun. Ağ
            Hizmeti Bilgi Notu'nu basıp BTR'ye ve okul müdürüne imzalatın; not okulda saklanır.
          </p>
          <Button
            variant="outlined"
            icon="assignment"
            disabled={basiliyor}
            onClick={() => void notuBas()}
          >
            Ağ Hizmeti Bilgi Notu'nu bas
          </Button>
        </Adim>
        <Adim no={2} baslik="Güvenlik duvarını hazırlayın" tamam={duvarGecti === true}>
          {windows ? (
            <p>
              Kurulumda “Yerel ağdan katalog taramasına izin ver” seçildiyse kural hazırdır. Ağ
              Doktoru'ndaki beş denetimin geçtiğini görün; geçmiyorsa oradaki “Kuralı ekle/güncelle”
              adımıyla kuralı yazın (Windows yönetici onayı ister).
            </p>
          ) : (
            <>
              <p>Pardus'ta kuralı BTR açar. Önerilen komut:</p>
              {linuxKomutu ? (
                <KomutKutusu komut={linuxKomutu} etiket="Güvenlik duvarı komutu" />
              ) : (
                <p>Komut Ağ Doktoru'nda gösterilir.</p>
              )}
            </>
          )}
          <Link
            to={AG_DOKTORU_ADRESI}
            className="inline-flex text-label-large text-primary underline underline-offset-2"
          >
            Ağ Doktoru'nu aç
          </Link>
        </Adim>
        <Adim no={3} baslik="Adresi seçin" tamam={adresSecildi}>
          <p>
            Aşağıdaki Dinleme bölümünde katalogun hangi ağ bağlantısında açılacağını seçin.
            Bilgisayarda tek ağ bağlantısı varsa varsayılan seçenek yeterlidir.
          </p>
        </Adim>
        <Adim no={4} baslik="Ağ Kataloğunu açın" tamam={acik}>
          {acik ? (
            <p>Ağ Kataloğu açık. Son adıma geçin.</p>
          ) : ayarAcik ? (
            <p>
              Ağ Kataloğu açılamadı; nedeni aşağıdaki Ağ Kataloğu kartında ve Ağ Doktoru'nda yazar.
              Düzelttikten sonra “Yeniden başlat”a basın.
            </p>
          ) : (
            <Button icon="play_circle" disabled={mesgul || !masaustu} onClick={onAc}>
              Ağ Kataloğunu aç
            </Button>
          )}
        </Adim>
        <Adim no={5} baslik="Afişi basın, yer imlerini dağıtın">
          <p>
            Ağ Doktoru'ndan katalog afişini basın ve tahtalar ile bilgisayarlar için yer imi
            dosyalarını üretip BTR'ye verin. Tahta ağından erişim yoksa PYS talep metnini de oradan
            kopyalayın.
          </p>
        </Adim>
      </ol>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Port diyaloğu
// ---------------------------------------------------------------------------

function PortDiyalogu({
  open,
  mevcut,
  windows,
  onClose,
  onDegisti,
}: {
  open: boolean;
  mevcut: number;
  windows: boolean;
  onClose: () => void;
  onDegisti: (port: number) => void;
}) {
  const formId = useId();
  const snackbar = useSnackbar();
  const [deger, setDeger] = useState(String(mevcut));
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  useEffect(() => {
    if (open) {
      setDeger(String(mevcut));
      setHata(null);
    }
  }, [open, mevcut]);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    const port = Number(deger.trim());
    if (!Number.isInteger(port) || port < PORT_ALT || port > PORT_UST) {
      setHata(`Port ${PORT_ALT} ile ${PORT_UST} arasında bir sayı olmalıdır.`);
      return;
    }
    setCalisiyor(true);
    setHata(null);
    try {
      const sonuc = await agKataloguApi.portDegistir(port);
      snackbar.success(sonuc.ileti);
      onDegisti(port);
      onClose();
    } catch (err) {
      setHata(hataMetni(err, "Port değiştirilemedi."));
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Portu değiştir"
      actions={
        <>
          <Button variant="text" type="button" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="submit" form={formId} disabled={calisiyor}>
            {calisiyor ? "Değiştiriliyor…" : "Portu değiştir"}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="space-y-4">
        <p className="text-body-medium text-on-surface-variant">
          {windows
            ? "Port değişince güvenlik duvarı kuralı da yeni portla yazılır: Windows yönetici onayı (UAC) açılır ve okulun bilişim teknolojileri rehber öğretmeninin (BTR) kimliği gerekir. Onay verilmezse port değişmez."
            : "Pardus'ta güvenlik duvarı kuralını okulun bilişim teknolojileri rehber öğretmeni (BTR) yeni portla açar; komut Ağ Doktoru'nda gösterilir."}{" "}
          Port değişince afişi yeniden basın, yer imlerini güncelleyin ve Ağ Hizmeti Bilgi Notu'nu
          yenileyin.
        </p>
        <TextField
          label="Yeni port"
          value={deger}
          onChange={(e) => setDeger(e.target.value)}
          inputMode="numeric"
          error={hata ?? undefined}
          helperText={`${PORT_ALT}-${PORT_UST} arası. Varsayılan 8765.`}
          required
        />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

export default function AgKataloguPaneli() {
  const { durum, setDurum, yenile } = useAgDurumu();
  const snackbar = useSnackbar();
  const { errors, clearErrors, applyApiError } = useFormErrors();
  const [ayar, setAyar] = useState<KatalogAyari | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [adaylar, setAdaylar] = useState<IpAdaylari | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [portAcik, setPortAcik] = useState(false);
  const alanId = useId();

  const [dinlemeKipi, setDinlemeKipi] = useState<DinlemeKipi>("ALL");
  const [seciliIp, setSeciliIp] = useState("");
  const [bloklar, setBloklar] = useState("");
  const [vitrin, setVitrin] = useState(true);
  const [konular, setKonular] = useState(true);
  const [uyku, setUyku] = useState(true);
  const [saatler, setSaatler] = useState("");

  const doldur = (a: KatalogAyari) => {
    setAyar(a);
    setDinlemeKipi(a.dinleme_kipi);
    setSeciliIp(a.secili_ip);
    setBloklar(a.tahta_cidrleri.join("\n"));
    setVitrin(a.vitrin_acik);
    setKonular(a.konular_acik);
    setUyku(a.uyku_engelleme);
    setSaatler(a.kutuphane_saatleri);
  };

  useEffect(() => {
    let iptal = false;
    agKataloguApi
      .ayar()
      .then((a) => {
        if (!iptal) {
          doldur(a);
          setHata(null);
        }
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Ağ Kataloğu ayarları yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const masaustu = durum?.masaustu ?? false;
  useEffect(() => {
    if (!masaustu) return;
    let iptal = false;
    agKataloguApi
      .arayuzler()
      .then((sonuc) => {
        if (!iptal) setAdaylar(sonuc);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, [masaustu]);

  async function acKapa(eylem: "ac" | "kapat") {
    setMesgul(true);
    try {
      const sonuc = await agKataloguApi.eylem(eylem);
      setDurum(sonuc);
      // Ayarın gerçek değeri yanıttadır (yazılamadıysa değişmemiştir).
      const ayarAcik = sonuc.katalog?.ayar_acik ?? eylem === "ac";
      setAyar((a) => (a ? { ...a, acik: ayarAcik } : a));
      if (eylem === "kapat") snackbar.success("Ağ Kataloğu kapatıldı.");
      else if (sonuc.katalog?.durum === "acik") snackbar.success("Ağ Kataloğu açıldı.");
      else snackbar.error(sonuc.katalog?.son_hata ?? "Ağ Kataloğu açılamadı.");
    } catch (e) {
      snackbar.error(hataMetni(e, "İşlem yapılamadı."));
    } finally {
      setMesgul(false);
    }
  }

  async function yenidenBaslat() {
    setMesgul(true);
    try {
      const sonuc = await agKataloguApi.eylem("yeniden_baslat");
      setDurum(sonuc);
      if (sonuc.katalog?.durum === "acik") snackbar.success("Ağ Kataloğu açıldı.");
      else snackbar.error(sonuc.katalog?.son_hata ?? "Ağ Kataloğu açılamadı.");
    } catch (e) {
      snackbar.error(hataMetni(e, "İşlem yapılamadı."));
    } finally {
      setMesgul(false);
    }
  }

  async function kaydet(e: FormEvent) {
    e.preventDefault();
    if (!ayar) return;
    clearErrors();
    const govde: KatalogAyariGovde = {
      dinleme_kipi: dinlemeKipi,
      secili_ip: seciliIp.trim(),
      tahta_cidrleri: bloklariAyir(bloklar),
      vitrin_acik: vitrin,
      konular_acik: konular,
      uyku_engelleme: uyku,
      kutuphane_saatleri: saatler,
    };
    setKaydediliyor(true);
    try {
      doldur(await agKataloguApi.ayarKaydet(govde));
      snackbar.success("Ağ Kataloğu ayarları kaydedildi.");
      void yenile();
    } catch (err) {
      if (!applyApiError(err)) snackbar.error(hataMetni(err, "Ayarlar kaydedilemedi."));
    } finally {
      setKaydediliyor(false);
    }
  }

  if (yukleniyor) return <SkeletonList rows={4} />;
  if (hata || !ayar) return <ErrorBand hata={hata ?? "Ağ Kataloğu ayarları yüklenemedi."} />;

  const katalog = durum?.katalog ?? null;
  const windows = durum?.platform === "windows";
  const acik = katalog ? katalog.durum === "acik" : ayar.acik;
  // Ayar açık ama katalog açılamadıysa (güvenlik duvarı, port, adres) de kapatılabilir.
  const kapatilabilir = acik || (katalog ? katalogKapatilabilir(katalog) : ayar.acik);
  // Kart afiş basılana dek durur: açtıktan sonraki son adım (afiş, yer imleri) ve
  // açılamazsa ikinci adımın yönlendirmesi ekranda kalsın (kart metni ve kılavuz).
  const ilkAcilis = !ayar.son_afis_ip;
  const duvar = katalog?.guvenlik_duvari ?? null;
  const ipSecenekleri = (adaylar?.arayuzler ?? []).map((a) => ({
    value: a.ip,
    label: `${a.ip} — ${a.ad}${a.varsayilan_rota ? " (varsayılan bağlantı)" : ""}`,
  }));
  if (seciliIp && !ipSecenekleri.some((s) => s.value === seciliIp)) {
    ipSecenekleri.unshift({ value: seciliIp, label: `${seciliIp} (bu bilgisayarda şu an yok)` });
  }

  return (
    <div className="space-y-6">
      {!masaustu && durum && <MasaustuYokBandi />}

      {ilkAcilis && (
        <IlkAcilisAdimlari
          ayar={ayar}
          duvarGecti={duvar ? duvar.dinlemeye_izin : null}
          linuxKomutu={duvar?.linux.komut || null}
          windows={windows}
          masaustu={masaustu}
          mesgul={mesgul}
          acik={acik}
          ayarAcik={kapatilabilir}
          onAc={() => void acKapa("ac")}
        />
      )}

      <Card elevation={1} className="space-y-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-title-medium text-on-surface">Ağ Kataloğu</h2>
            <p className="mt-1 text-body-medium text-on-surface-variant">
              Okul ağındaki bilgisayarlar ve etkileşimli tahtalar kataloğu tarayıcıyla tarar.
              Kişisel veri göstermez: üye, ödünç alan ve iade tarihi hiçbir sayfasında geçmez.
              Varsayılan olarak kapalıdır.
              {/* Sözlük §2: BTR ilk geçişte açılır; ilk açılış kartı görünürken açılım oradadır. */}
              {!ilkAcilis &&
                " Ağ ayarları okulun bilişim teknolojileri rehber öğretmeniyle (BTR) birlikte yapılır."}
            </p>
          </div>
          {katalog && <DurumRozeti durum={katalog.durum} />}
        </div>
        {katalog?.adres && (
          <p className="text-body-medium text-on-surface">
            Adres:{" "}
            <a
              href={katalog.adres}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline underline-offset-2"
            >
              {katalog.adres}
            </a>
          </p>
        )}
        {katalog?.son_hata && <ErrorBand hata={katalog.son_hata} />}
        <div className="flex flex-wrap gap-2">
          {kapatilabilir ? (
            <>
              <Button
                variant="outlined"
                icon="stop_circle"
                disabled={mesgul || !masaustu}
                onClick={() => void acKapa("kapat")}
              >
                Ağ Kataloğunu kapat
              </Button>
              {!acik && (
                <Button
                  variant="outlined"
                  icon="restart_alt"
                  disabled={mesgul || !masaustu}
                  onClick={() => void yenidenBaslat()}
                >
                  Yeniden başlat
                </Button>
              )}
            </>
          ) : (
            !ilkAcilis && (
              <Button
                icon="play_circle"
                disabled={mesgul || !masaustu}
                onClick={() => void acKapa("ac")}
              >
                Ağ Kataloğunu aç
              </Button>
            )
          )}
          <Link
            to={AG_DOKTORU_ADRESI}
            className="inline-flex min-h-[var(--kd-control-height)] items-center gap-2 rounded-shape-md px-2.5 text-label-large font-semibold text-primary hover:bg-primary/8"
          >
            <Icon name="troubleshoot" size="lg" />
            Ağ Doktoru
          </Link>
        </div>
      </Card>

      <form onSubmit={kaydet} className="space-y-6" noValidate>
        <Card elevation={1} className="space-y-4 p-6">
          <h2 className="text-title-medium text-on-surface">Dinleme</h2>
          <div className="flex flex-wrap items-end gap-3">
            <p className="text-body-medium text-on-surface">
              Port: <span className="font-semibold">{ayar.port}</span>
            </p>
            <Button type="button" variant="text" icon="edit" onClick={() => setPortAcik(true)}>
              Portu değiştir
            </Button>
          </div>
          <fieldset className="space-y-1">
            <legend className="text-label-large text-on-surface">
              Katalog hangi ağ bağlantısında açılsın?
            </legend>
            {(["ALL", "SELECTED"] as const).map((kip) => (
              <label
                key={kip}
                className="flex min-h-11 cursor-pointer items-center gap-2 text-body-medium text-on-surface"
              >
                <input
                  type="radio"
                  name="dinleme_kipi"
                  value={kip}
                  checked={dinlemeKipi === kip}
                  onChange={() => setDinlemeKipi(kip)}
                  className="size-5 accent-primary"
                />
                {DINLEME_KIPI_TR[kip]}
              </label>
            ))}
            <p className="text-body-small text-on-surface-variant">
              Bilgisayarda birden çok ağ bağlantısı varsa (ör. ikinci ağ kartı) “Yalnız seçili IP
              adresinde” seçeneğiyle katalog yalnız okul ağına açılır.
            </p>
          </fieldset>
          {dinlemeKipi === "SELECTED" &&
            (ipSecenekleri.length > 0 ? (
              <Select
                label="IP adresi"
                value={seciliIp}
                onChange={(e) => setSeciliIp(e.target.value)}
                placeholder="Seçin"
                options={ipSecenekleri}
                error={errors.secili_ip}
              />
            ) : (
              <TextField
                label="IP adresi"
                value={seciliIp}
                onChange={(e) => setSeciliIp(e.target.value)}
                inputMode="decimal"
                error={errors.secili_ip}
                helperText="Bu bilgisayarın okul ağındaki adresi. Adresler masaüstü programında listelenir."
              />
            ))}
          <div className="space-y-1">
            <label htmlFor={`${alanId}-bloklar`} className="block text-label-large text-on-surface">
              Tahta ağı blokları
            </label>
            <textarea
              id={`${alanId}-bloklar`}
              value={bloklar}
              onChange={(e) => setBloklar(e.target.value)}
              rows={3}
              aria-describedby={`${alanId}-bloklar-yardim`}
              className="w-full rounded-shape-sm border border-outline-variant bg-surface-container-lowest p-3 text-body-medium text-on-surface"
            />
            <span
              id={`${alanId}-bloklar-yardim`}
              className="block text-body-small text-on-surface-variant"
            >
              Her satıra bir blok (ör. adres/24). Yalnız BTR'nin doğruladığı tahta ağı blokları
              yazılır; güvenlik duvarı kuralı yerel alt ağa ek olarak bunlara izin verir.
              Kaydettikten sonra Ağ Doktoru'nda kuralı güncelleyin.
            </span>
            {errors.tahta_cidrleri && (
              <span role="alert" className="block text-body-small text-error">
                {errors.tahta_cidrleri}
              </span>
            )}
          </div>
        </Card>

        <Card elevation={1} className="space-y-4 p-6">
          <h2 className="text-title-medium text-on-surface">Katalog Sayfaları</h2>
          <Onay
            label="Vitrin (yeni gelenler ve çok okunanlar) ana sayfada gösterilir"
            checked={vitrin}
            onChange={setVitrin}
            helperText="Çok okunanlarda sayı gösterilmez, yalnız sıra."
          />
          <Onay label="Konu dizini gösterilir" checked={konular} onChange={setKonular} />
          <div className="space-y-1">
            <label htmlFor={`${alanId}-saatler`} className="block text-label-large text-on-surface">
              Kütüphane saatleri
            </label>
            <textarea
              id={`${alanId}-saatler`}
              value={saatler}
              onChange={(e) => setSaatler(e.target.value)}
              rows={3}
              maxLength={500}
              aria-describedby={`${alanId}-saatler-yardim`}
              className="w-full rounded-shape-sm border border-outline-variant bg-surface-container-lowest p-3 text-body-medium text-on-surface"
            />
            <span
              id={`${alanId}-saatler-yardim`}
              className="block text-body-small text-on-surface-variant"
            >
              Ağ Kataloğunun Hakkında sayfasında ve katalog afişinde görünür.
            </span>
            {errors.kutuphane_saatleri && (
              <span role="alert" className="block text-body-small text-error">
                {errors.kutuphane_saatleri}
              </span>
            )}
          </div>
        </Card>

        <Card elevation={1} className="space-y-4 p-6">
          <h2 className="text-title-medium text-on-surface">Uyku</h2>
          <Onay
            label="Ağ Kataloğu açıkken bilgisayar boşta uykuya geçmesin"
            checked={uyku}
            onChange={setUyku}
            helperText="Yalnız boşta kalma uykusu engellenir; kapağı kapatmak ya da uykuya elle almak engellenmez. Program Windows oturumu açılmadan çalışmaz."
          />
        </Card>

        <div className="flex justify-end">
          <Button type="submit" icon="save" disabled={kaydediliyor}>
            {kaydediliyor ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </form>

      <PortDiyalogu
        open={portAcik}
        mevcut={ayar.port}
        windows={windows}
        onClose={() => setPortAcik(false)}
        onDegisti={(port) => {
          setAyar((a) => (a ? { ...a, port } : a));
          void yenile();
        }}
      />
    </div>
  );
}
