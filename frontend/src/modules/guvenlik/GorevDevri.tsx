// "Görev Devri" sihirbazı (Ayarlar → Güvenlik; F11 — tasarım §4.4, E18). Yalnız yönetici kipi.
//
// Kütüphane yöneticisi değişince tek akış (sözlük "Görev devri"; adım adları sözlük §4.6).
// Kart ADIM ADIM çalışır: üstteki rayda üç adım, altında yalnız o anki adımın işi.
//   1. "Parola ve anahtar yenilenir" — yönetici parolası VE kurtarma anahtarı TEK adımda
//      yenilenir (`POST library/handover/start/`; güncel güvenlik dosyasında kilidi yalnız
//      yenileri açar — ama bkz. sınır). Yeni parolayı görevi devralan kişi belirler.
//      Kart o anki açık işlerin kişisiz sayılarını gösterir.
//   2. "Yeni anahtar saklanır" — yeni anahtar modül belleğinde "gorev-devri" kaynağıyla
//      bekletilir (`bekleyenAnahtar`) ve BU KARTIN İÇİNDE, F1'in aynı paneliyle
//      (`KurtarmaAnahtariPaneli`) saklatılıp doğrulanır; Güvenlik ekranının başındaki panel
//      bu anahtarı göstermez (adımlar tek yerde kalsın). Anahtar bellekte değilse (pencere
//      kapandı) kart "Kurtarma Anahtarını Doğrula" kartını ya da yeniden başlatmayı söyler.
//   3. "Görev devri notu basılır" — E18 (PDF). Adlar yalnız basım anında kullanılır,
//      programda saklanmaz. Sunucu, devir + doğrulama damgası yoksa 409 döner. İndirilince
//      adım tamamlanmış görünür; not yeniden indirilebilir.
//
// Metin DÜRÜSTTÜR (TB17, TB23; F11 düzeltme turu): kayıtların şifreleme anahtarı
// değişmez; eski parola ya da eski anahtar, eski bir yedekle ya da arşivlenmiş güvenlik
// dosyasıyla birlikte o anahtarı verir — devirden SONRA alınan yedekleri de açar. Bu
// yüzden kart "eski parola kilidi artık açmaz" DEMEZ; masa hesabının parolasının
// değiştirilmesini söyler (sunucu testi:
// `test_gorev_devri.py::test_sinir_eski_parola_eski_baslikla_…`). Kart sayıları
// sunucudan okur; not aynı bilgiyi basar. Açık işler yalnız sayıdır (F11 bağlantısı:
// onay bekleyen saklama kayıtları da görevi devralana kalır).

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate, formatDateTime, formatNumber, todayIso } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import KurtarmaAnahtariPaneli from "./KurtarmaAnahtariPaneli";
import { guvenlikApi } from "./api";
import type { GorevDevriDurumu } from "./api";
import {
  bekleyenKurtarmaAnahtariniYaz,
  useBekleyenAnahtarKaynagi,
  useBekleyenKurtarmaAnahtari,
} from "./bekleyenAnahtar";

/** Kartın adı (sözlük §4.6). */
export const GOREV_DEVRI_BASLIGI = "Görev Devri";
/** Belgenin adı — sözlük §2 (E18) yazımıyla, başlık yerinde de böyle kalır (sözlük §3). */
export const GOREV_DEVRI_NOTU = "Görev devri notu";
/** İndirme adı — Kurtarma anahtarı çıktısıyla aynı kalıp: "Görev-Devri-Notu_gg.aa.yyyy.pdf". */
const DOSYA_ADI_KOKU = "Görev Devri Notu";

/** Ad ve not sınırları — sunucuyla aynı (`apps/kutuphane/gorev_devri.py`). */
const AD_EN_COK = 120;
const NOT_EN_COK = 600;

/** Sihirbazın adımları — sözlük §4.6'daki adlarla, sırasıyla. */
export const GOREV_DEVRI_ADIMLARI = [
  "Parola ve anahtar yenilenir",
  "Yeni anahtar saklanır",
  "Görev devri notu basılır",
] as const;

export const GOREV_DEVRI_METNI =
  "Kütüphane yöneticisi değiştiğinde yetki ayrılan kişide kalmasın: yönetici parolası ve " +
  "kurtarma anahtarı birlikte yenilenir, yeni anahtar saklanıp doğrulanır ve görev devri " +
  "notu basılır. Yeni parolayı görevi devralan kişi belirler.";

export const GOREV_DEVRI_SINIR_METNI =
  "Kayıtların şifreleme anahtarı görev devrinde değişmez; yalnız parolanın ve kurtarma " +
  "anahtarının açtığı kilit yenilenir. Bu yüzden eski parola ya da eski kurtarma anahtarı, " +
  "devirden önce alınmış bir yedekle (USB bellektekiler dahil) ya da arşivlenmiş güvenlik " +
  "dosyasıyla birlikte kayıtların anahtarını verir; bu anahtar devirden sonra alınan " +
  "yedekleri de açar. Görev devri, görevi devredenin bu bilgisayara ve yedeklere erişimi " +
  "kesildiğinde anlam taşır: kütüphane masası Windows hesabının parolasını da değiştirin. " +
  "Görev devri notu yedeklerin ve eski kâğıdın ne yapılacağını yazar.";

/** 2. adım, anahtar bu kartta beklerken. */
export const ANAHTAR_ADIMI_METNI =
  "Yeni kurtarma anahtarı aşağıda bir kez gösterilir. Yazdırın, PDF olarak USB belleğe " +
  "kaydedin ya da elle yazın; sonra iki grubunu geri yazarak doğrulayın. Görev devri notu " +
  "ondan sonra basılır.";

/** 2. adım, anahtar bellekte değilken (pencere kapandı, program yeniden açıldı). */
export const ANAHTAR_YOK_METNI =
  "Yeni kurtarma anahtarı ekranda değil. Kâğıda yazdıysanız “Kurtarma Anahtarını Doğrula” " +
  "kartından doğrulayın; kaydedemediyseniz görev devrini yeniden başlatın.";

function hataMetni(err: unknown, varsayilan: string): string {
  return err instanceof ApiError || err instanceof Error ? err.message || varsayilan : varsayilan;
}

type Adim = "parola" | "anahtar" | "not";

export default function GorevDevri({
  anahtarDogrulandi,
  onBasladi,
  onAnahtarDogrulama,
}: {
  /** Güvenlik durumundaki doğrulama damgası — değişince devir durumu yeniden okunur. */
  anahtarDogrulandi: boolean;
  /** Devir başlayınca (yeni anahtar bekletildi) güvenlik durumunu tazelemek için. */
  onBasladi?: () => void;
  /**
   * 2. adımdaki panel sunucu damgasını yazınca `true` bildirilir (Güvenlik ekranı anahtarı
   * bellekten bırakır ve durumu tazeler). Verilmezse kart anahtarı kendisi bırakır.
   */
  onAnahtarDogrulama?: (dogrulandi: boolean) => void;
}) {
  const snackbar = useSnackbar();
  const bekleyenAnahtar = useBekleyenKurtarmaAnahtari();
  const anahtarKaynagi = useBekleyenAnahtarKaynagi();
  const [devir, setDevir] = useState<GorevDevriDurumu | null>(null);
  const [acik, setAcik] = useState(false);
  const mevcutAlani = useRef<HTMLInputElement>(null);
  const [mevcut, setMevcut] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const [devreden, setDevreden] = useState("");
  const [devralan, setDevralan] = useState("");
  const [ekNot, setEkNot] = useState("");
  const [basiliyor, setBasiliyor] = useState(false);
  // Bu oturumda not indirildi mi? (3. adım "tamamlandı" görünür; not yeniden indirilebilir.)
  const [notIndirildi, setNotIndirildi] = useState(false);
  // Panel sunucu damgasını yazdı; devir durumu yeniden okunana dek 2. adım "doğrulandı" der.
  const [dogrulamaTamam, setDogrulamaTamam] = useState(false);

  const oku = useCallback(() => {
    guvenlikApi
      .gorevDevri()
      .then(setDevir)
      .catch(() => undefined);
  }, []);

  // Doğrulama damgası değişince (panel doğruladı) not adımı açılır.
  useEffect(() => oku(), [oku, anahtarDogrulandi]);

  const anahtarSaklandi = useCallback(
    (dogru: boolean) => {
      if (!dogru) return;
      setDogrulamaTamam(true);
      if (onAnahtarDogrulama) onAnahtarDogrulama(true);
      else bekleyenKurtarmaAnahtariniYaz(null);
      oku();
    },
    [onAnahtarDogrulama, oku],
  );

  function kapat() {
    setAcik(false);
    setMevcut("");
    setYeni("");
    setTekrar("");
    setHata(null);
  }

  async function baslat(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    if (yeni !== tekrar) {
      setHata("Parolalar eşleşmedi.");
      return;
    }
    setCalisiyor(true);
    try {
      const sonuc = await guvenlikApi.gorevDevriBaslat(mevcut, yeni);
      bekleyenKurtarmaAnahtariniYaz(sonuc.recovery_key, "gorev-devri");
      setDevir(sonuc.handover);
      setNotIndirildi(false);
      setDogrulamaTamam(false);
      kapat();
      snackbar.success(
        "Yönetici parolası ve kurtarma anahtarı yenilendi. Yeni anahtarı saklayıp doğrulayın.",
      );
      onBasladi?.();
    } catch (err) {
      setHata(hataMetni(err, "Görev devri başlatılamadı."));
    } finally {
      setCalisiyor(false);
    }
  }

  async function notuIndir(e: FormEvent) {
    e.preventDefault();
    setBasiliyor(true);
    try {
      const pdf = await guvenlikApi.gorevDevriNotu({
        outgoing_name: devreden.trim(),
        incoming_name: devralan.trim(),
        note: ekNot,
      });
      saveBlob(pdf, dosyaAdi([DOSYA_ADI_KOKU, formatDate(todayIso())], "pdf"));
      setNotIndirildi(true);
      snackbar.success("Görev devri notu indirildi. İmzalanıp müdürlükte saklanır.");
    } catch (err) {
      snackbar.error(hataMetni(err, "Görev devri notu hazırlanamadı."));
    } finally {
      setBasiliyor(false);
    }
  }

  const basladi = Boolean(devir?.started_at);
  const dogrulandi = Boolean(devir?.confirmed_at) || (basladi && dogrulamaTamam);
  const notHazir = Boolean(devir?.note_available);
  const adim: Adim = notHazir ? "not" : basladi ? "anahtar" : "parola";
  // Yalnız görev devrinin anahtarı bu kartta gösterilir (öbürleri Güvenlik ekranının başında).
  const panelAnahtari = anahtarKaynagi === "gorev-devri" ? bekleyenAnahtar : null;
  const adimlar: StepperItem[] = [
    {
      key: "parola",
      label: GOREV_DEVRI_ADIMLARI[0],
      icon: "key",
      status: basladi ? "done" : "current",
    },
    {
      key: "anahtar",
      label: GOREV_DEVRI_ADIMLARI[1],
      icon: "fact_check",
      status: dogrulandi ? "done" : basladi ? "current" : "upcoming",
    },
    {
      key: "not",
      label: GOREV_DEVRI_ADIMLARI[2],
      icon: "description",
      status: notIndirildi ? "done" : notHazir ? "current" : "upcoming",
    },
  ];
  const acikIsler = (devir?.open_work ?? []).filter((satir) => satir.count > 0);

  return (
    <Card className="p-6">
      <div className="mb-2 flex items-center gap-3">
        <Icon name="swap_horiz" className="text-primary" />
        <h2 className="text-title-large text-on-surface">{GOREV_DEVRI_BASLIGI}</h2>
      </div>
      <p className="text-body-medium text-on-surface-variant">{GOREV_DEVRI_METNI}</p>

      <div className="mt-4">
        <Stepper items={adimlar} ariaLabel="Görev devri adımları" />
      </div>

      {devir?.started_at && (
        <p className="mt-3 text-body-small text-on-surface-variant">
          Son görev devri: {formatDateTime(devir.started_at)}
          {devir.confirmed_at
            ? ` · yeni anahtarın saklandığı doğrulandı: ${formatDateTime(devir.confirmed_at)}`
            : ""}
          .
        </p>
      )}

      {/* ---------------------------------------------------- 1. adım: başlamadan önce */}
      {devir && adim === "parola" && (
        <section aria-labelledby="gorev-devri-adim-1" className="mt-5 space-y-3">
          <h3 id="gorev-devri-adim-1" className="text-title-small text-on-surface">
            1. {GOREV_DEVRI_ADIMLARI[0]}
          </h3>
          <p className="text-body-medium text-on-surface">
            Görevi devreden ve görevi devralan birlikte oturur. Mevcut yönetici parolasını görevi
            devreden, yeni parolayı görevi devralan yazar. Kilidi bundan sonra yeni parola ve yeni
            kurtarma anahtarı açar; eski parolanın sınırı aşağıdadır.
          </p>
          <Button variant="tonal" icon="swap_horiz" onClick={() => setAcik(true)}>
            Görev devrini başlat
          </Button>
        </section>
      )}

      {/* ---------------------------------------------------- 2. adım: yeni anahtar */}
      {adim === "anahtar" && (
        <section aria-labelledby="gorev-devri-adim-2" className="mt-5 space-y-3">
          <h3 id="gorev-devri-adim-2" className="text-title-small text-on-surface">
            2. {GOREV_DEVRI_ADIMLARI[1]}
          </h3>
          {panelAnahtari !== null ? (
            <>
              <p className="text-body-medium text-on-surface">{ANAHTAR_ADIMI_METNI}</p>
              <KurtarmaAnahtariPaneli
                anahtar={panelAnahtari}
                onDogrulama={anahtarSaklandi}
                dogrulandiMetni="Doğrulandı. Görev devri notu adımına geçebilirsiniz."
              />
            </>
          ) : dogrulandi ? (
            <p role="status" className="flex items-center gap-2 text-body-medium text-primary">
              <Icon name="check_circle" />
              Yeni kurtarma anahtarının saklandığı doğrulandı.
            </p>
          ) : (
            <div
              role="status"
              className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
            >
              <Icon name="key" />
              <span>{ANAHTAR_YOK_METNI}</span>
            </div>
          )}
        </section>
      )}

      {/* ---------------------------------------------------- 3. adım: görev devri notu */}
      {adim === "not" && (
        <form
          onSubmit={notuIndir}
          aria-labelledby="gorev-devri-adim-3"
          className="mt-5 flex flex-col gap-4"
        >
          <h3 id="gorev-devri-adim-3" className="text-title-small text-on-surface">
            3. {GOREV_DEVRI_ADIMLARI[2]}
          </h3>
          <p className="text-body-small text-on-surface-variant">
            Adlar programda saklanmaz; yalnız basılan nota yazılır. Boş bırakırsanız notta elle
            doldurulacak çizgi basılır. Not, teslim edilenlerin listesini ve notun düzenlendiği
            gündeki açık işlerin sayılarını taşır; kişi ve kitap adı taşımaz. Not son görev devrinin
            tarihini yazar: yeni bir görev devri için önce aşağıdaki “Görev devrini yeniden başlat”a
            basın.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Görevi devreden (adı soyadı)"
              value={devreden}
              onChange={(e) => setDevreden(e.target.value)}
              maxLength={AD_EN_COK}
              autoComplete="off"
            />
            <TextField
              label="Görevi devralan (adı soyadı)"
              value={devralan}
              onChange={(e) => setDevralan(e.target.value)}
              maxLength={AD_EN_COK}
              autoComplete="off"
            />
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-label-medium font-semibold text-on-surface-variant">
              Ek not (isteğe bağlı)
            </span>
            <textarea
              value={ekNot}
              onChange={(e) => setEkNot(e.target.value)}
              rows={3}
              maxLength={NOT_EN_COK}
              className="w-full rounded-shape-sm border border-outline-variant bg-surface-container-lowest p-3 text-body-medium text-on-surface"
            />
          </label>
          <div>
            <Button type="submit" icon="picture_as_pdf" disabled={basiliyor}>
              {basiliyor ? "Hazırlanıyor…" : "Görev devri notunu indir"}
            </Button>
          </div>
          {notIndirildi && (
            <p role="status" className="flex items-center gap-2 text-body-medium text-primary">
              <Icon name="check_circle" />
              Not indirildi. Görevi devreden, görevi devralan ve okul müdürü imzalar; not müdürlükte
              saklanır.
            </p>
          )}
        </form>
      )}

      {acikIsler.length > 0 && (
        <div className="mt-5">
          <h3 className="text-title-small text-on-surface">Açık işler</h3>
          <p className="text-body-small text-on-surface-variant">
            Görevi devralana kalan işler; sayılar görev devri notuna da basılır.
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-body-small text-on-surface-variant">
            {acikIsler.map((satir) => (
              <li key={satir.key}>
                {satir.label}: {formatNumber(satir.count)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {devir && (
        <div className="mt-4 space-y-2 text-body-small text-on-surface-variant">
          <p>{GOREV_DEVRI_SINIR_METNI}</p>
          <p>
            Bu bilgisayarda {basladi ? "devirden önce alınmış" : "bugüne dek alınmış"}{" "}
            {formatNumber(devir.old_backup_count)} yedek
            {devir.oldest_backup ? ` (en eskisi ${devir.oldest_backup})` : ""} ve veri klasöründe{" "}
            {formatNumber(devir.archive_count)} arşivlenmiş güvenlik dosyası var. Günlük yedekler 14
            gün içinde kendiliğinden silinir.
          </p>
        </div>
      )}

      {basladi && (
        <div className="mt-5">
          <Button variant="outlined" icon="swap_horiz" onClick={() => setAcik(true)}>
            Görev devrini yeniden başlat
          </Button>
        </div>
      )}

      <Dialog
        open={acik}
        onClose={kapat}
        title="Görev devri başlatılsın mı?"
        initialFocusRef={mevcutAlani}
      >
        <form onSubmit={baslat} className="flex flex-col gap-4">
          <p className="text-body-medium text-on-surface">
            Yönetici parolası ve kurtarma anahtarı birlikte yenilenir; kilidi bundan sonra yenileri
            açar. Yeni anahtar bir kez gösterilir: saklayıp doğrulamadan programı kapatmayın.
          </p>
          <p className="text-body-small text-on-surface-variant">{GOREV_DEVRI_SINIR_METNI}</p>
          <TextField
            ref={mevcutAlani}
            label="Mevcut yönetici parolası"
            type="password"
            value={mevcut}
            onChange={(e) => setMevcut(e.target.value)}
            autoComplete="current-password"
            required
          />
          <TextField
            label="Yeni yönetici parolası"
            type="password"
            value={yeni}
            onChange={(e) => setYeni(e.target.value)}
            autoComplete="new-password"
            helperText="En az 8 karakter; eskisinden farklı. Görevi devralan kişi belirler."
            required
          />
          <TextField
            label="Parola (tekrar)"
            type="password"
            value={tekrar}
            onChange={(e) => setTekrar(e.target.value)}
            autoComplete="new-password"
            error={hata ?? undefined}
            required
          />
          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" icon="swap_horiz" disabled={calisiyor}>
              {calisiyor ? "Yenileniyor…" : "Parolayı ve anahtarı yenile"}
            </Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}
