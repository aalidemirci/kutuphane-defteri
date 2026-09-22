// Kurtarma anahtarı paneli — kurulum sihirbazının ilk adımında, yönetici parolası
// kurulur kurulmaz gösterilir (tasarım §6.3-1, E14). Anahtar yenilendiğinde (sihirbaz
// ya da Ayarlar → Güvenlik) yeni anahtar da bu panelle saklatılıp doğrulatılır.
//
// Anahtar SUNUCUDA SAKLANMAZ, bu panel onu gösteren TEK yerdir. Kural "basım
// zorunlu" değil "SAKLAMA zorunlu"dur; üç saklama yolu sunulur:
//   1. Yazdır — pencere içi yazdırma; yazdırma stili yalnız anahtar alanını bırakır.
//   2. PDF olarak kaydet — backend E14 çıktısı (anahtar kurtarma sarmalına karşı
//      doğrulanır, yanlış yazılmış anahtar basılmaz). Eski "metin dosyası olarak
//      kaydet" KALDIRILDI: düz .txt bilgisayarda unutulan, arama dizinine giren ve
//      yazdırıldığında ne olduğu anlaşılmayan bir kopyaydı; PDF aynı işi resmî çıktı
//      biçiminde görür ve saklama önerilerini de taşır.
//   3. Elle yaz — yönerge metni.
// Devam için anahtarın rastgele İKİ GRUBU sakladığı kopyaya bakılarak geri yazılır
// (doğrulama kipinde anahtar ekrandan kalkar, yoksa ekrandan kopyalanırdı). İki grup
// istemcide tutunca bellekteki TAM anahtar `security/recovery-key/confirm/`'a gider:
// sunucu onu kurtarma sarmalına karşı doğrulayıp güvenlik dosyasına "saklandı"
// damgası yazar (F1 eki, karar 2; kurulum damgasız tamamlanmaz). `onDogrulama(true)`
// ancak sunucu damgayı yazınca bildirilir; hata olursa ileti ve "Yeniden dene" çıkar.
//
// GÖZETİMSİZ EKRAN (TB19): kurulum bitene kadar kip süreyle düşmez (kullanıcı kararı
// 2-1) — anahtar bellekte kalır, program kendiliğinden kilitlenmez. Bedeli anahtarın
// ekranda süresiz durmasıydı; panel 5 dakika hiç etkileşim olmazsa anahtarı YERİNDE
// gizler ("Anahtarı göster" ile geri gelir). Sayaç yalnız görseldir: kipi düşürmez,
// sunucuya bir şey sormaz, anahtarı bellekten silmez — masadan kalkıldığında omuz
// üstünden okunmasını zorlaştıran kaza önleyicidir (§4.2-4'teki Çık parolası gibi).
// Etkileşim saati `lib/api.ts` içinde ZATEN tutulur (kip boşta sayacı için, yakalama
// evresinde pointerdown + keydown): panel kendi küresel dinleyicisini kurmaz, o saati
// okur — ikinci bir dinleyici aynı olayı iki kez izler ve iki ölçü birbirinden
// kayardı. Panele ait olan yalnız yoklama zamanlayıcısıdır. Gizliyken anahtar DOM'da
// da değildir: yazdırma alanı da onu göstermez. PDF yolu etkilenmez (bellekteki
// anahtarla çalışır), düğmeler anahtarla birlikte geri gelir.
//
// Yazdırma notu: program bir masaüstü penceresinde (pywebview) koştuğu için
// `window.print()` bütün kabuğu basardı. Panel görünürken devreye giren küçük
// yazdırma stili sayfadaki her şeyi gizleyip yalnız anahtar alanını bırakır.
// Kural `@media print { … }` bloğunun İÇİNDEDİR, `<style media="print">`
// niteliğiyle DEĞİL: jsdom nitelik biçimini yok sayıp kuralı ekrana da uygular,
// o zaman `visibility: hidden` tüm sayfayı erişilebilirlik ağacından düşürürdü.

import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, sonEtkilesimAni } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { guvenlikApi } from "./api";
import {
  kurtarmaAnahtariniNormallestir,
  kurtarmaGruplari,
  rastgeleIkiGrup,
  useKurtarmaCiktisi,
} from "./kurtarma";
import { ELLE_YAZ_METNI, KURTARMA_UYARISI, dogrulamaMetni } from "./metinler";

const YAZDIRMA_ALANI_ID = "kurtarma-anahtari-yazdirma-alani";

/** Anahtarın ekranda gizleneceği boşta süre (TB19; yalnız görsel önlem). */
export const BOSTA_GIZLEME_MS = 5 * 60_000;
/** Boşta süresinin yoklanma aralığı — saniye hassasiyeti gerekmez. */
const YOKLAMA_ARALIGI_MS = 15_000;

const YAZDIRMA_STILI = `
  @media print {
    body * { visibility: hidden !important; }
    #${YAZDIRMA_ALANI_ID}, #${YAZDIRMA_ALANI_ID} * { visibility: visible !important; }
    #${YAZDIRMA_ALANI_ID} { position: absolute; left: 0; top: 0; width: 100%; }
  }
`;

interface KurtarmaAnahtariPaneliProps {
  /** Sunucunun bir daha üretemeyeceği anahtar (ör. "A1B2-C3D4-…"). */
  anahtar: string;
  /** Okul adı — yazıcı çıktısında hangi kuruma ait olduğu belli olsun (boş olabilir). */
  okulAdi?: string;
  /**
   * İki grup doğru yazılıp sunucu "saklandı" damgasını yazınca `true`, doğrulama
   * bozulunca (grup değişti, anahtar yeniden gösterildi) `false` bildirilir.
   */
  onDogrulama: (dogrulandi: boolean) => void;
  /** Doğrulama sonrası ileti (sihirbazda sonraki adım, Güvenlik'te bitti). */
  dogrulandiMetni?: string;
  /** Doğrulanacak grupların seçimi (testte sabitlenir). */
  rastgele?: () => number;
}

type Asama = "goster" | "dogrula";

/** Sunucu doğrulamasının durumu (iki grup istemcide tuttuktan sonra). */
type Onay = "bekliyor" | "gonderiliyor" | "tamam" | "hata";

export default function KurtarmaAnahtariPaneli({
  anahtar,
  okulAdi = "",
  onDogrulama,
  dogrulandiMetni = "Doğrulandı. Kurulumun sonraki adımına geçebilirsiniz.",
  rastgele,
}: KurtarmaAnahtariPaneliProps) {
  const snackbar = useSnackbar();
  const gruplar = useMemo(() => kurtarmaGruplari(anahtar), [anahtar]);
  const [asama, setAsama] = useState<Asama>("goster");
  const [sorulan, setSorulan] = useState<[number, number]>([0, 1]);
  const [yanitlar, setYanitlar] = useState<[string, string]>(["", ""]);
  const [onay, setOnay] = useState<Onay>("bekliyor");
  const [onayHatasi, setOnayHatasi] = useState<string | null>(null);
  // Boşta gizleme (TB19): `gorunurlukAni` anahtarın en son gösterildiği andır;
  // etkileşim saati lib/api.ts'ten okunur (panelin kendi dinleyicisi yok).
  const [gizli, setGizli] = useState(false);
  const [gorunurlukAni, setGorunurlukAni] = useState(() => Date.now());
  // Her yeni istek (ya da iptal) sayacı artırır; bayat yanıt durumu değiştirmez.
  const istekNo = useRef(0);
  const { indir, indiriliyor, hata: pdfHatasi } = useKurtarmaCiktisi();

  const dogru = sorulan.map(
    (sira, i) => kurtarmaAnahtariniNormallestir(yanitlar[i]) === gruplar[sira],
  );
  const dogrulandi = asama === "dogrula" && dogru[0] && dogru[1] && onay === "tamam";

  useEffect(() => {
    onDogrulama(dogrulandi);
  }, [dogrulandi, onDogrulama]);

  // Anahtar ekrandayken boşta süreyi yoklar; doğrulama kipinde zaten ekranda değildir.
  useEffect(() => {
    if (asama !== "goster" || gizli) return;
    const zamanlayici = window.setInterval(() => {
      const sonHareket = Math.max(gorunurlukAni, sonEtkilesimAni());
      if (Date.now() - sonHareket >= BOSTA_GIZLEME_MS) setGizli(true);
    }, YOKLAMA_ARALIGI_MS);
    return () => window.clearInterval(zamanlayici);
  }, [asama, gizli, gorunurlukAni]);

  function anahtariGoster() {
    setGorunurlukAni(Date.now()); // sayaç sıfırlanır
    setGizli(false);
  }

  function onayiBirak() {
    istekNo.current += 1;
    setOnay("bekliyor");
    setOnayHatasi(null);
  }

  async function sunucudaDogrula() {
    istekNo.current += 1;
    const no = istekNo.current;
    setOnay("gonderiliyor");
    setOnayHatasi(null);
    try {
      await guvenlikApi.kurtarmaAnahtariniDogrula(anahtar);
      if (no === istekNo.current) setOnay("tamam");
    } catch (err) {
      if (no !== istekNo.current) return;
      setOnay("hata");
      setOnayHatasi(
        err instanceof ApiError ? err.message : "Doğrulama kaydedilemedi. Yeniden deneyin.",
      );
    }
  }

  function yazdir() {
    // jsdom/bazı gömülü motorlarda `print` bulunmayabilir — sessizce atlanır.
    if (typeof window.print === "function") window.print();
  }

  async function pdfKaydet() {
    if (await indir(anahtar)) {
      snackbar.success("Kurtarma anahtarı çıktısı PDF olarak kaydedildi.");
    }
  }

  function dogrulamayaGec() {
    onayiBirak();
    setSorulan(rastgeleIkiGrup(gruplar.length, rastgele));
    setYanitlar(["", ""]);
    setAsama("dogrula");
  }

  function anahtariYenidenGoster() {
    onayiBirak();
    anahtariGoster();
    setAsama("goster");
  }

  function yanitDegisti(i: 0 | 1, deger: string) {
    const yeni: [string, string] = i === 0 ? [deger, yanitlar[1]] : [yanitlar[0], deger];
    setYanitlar(yeni);
    const ikisiDeDogru = sorulan.every(
      (sira, k) => kurtarmaAnahtariniNormallestir(yeni[k]) === gruplar[sira],
    );
    // İki grup tutunca TAM anahtar sunucuda doğrulanır; bozulunca bekleyen yanıt bayatlar.
    if (ikisiDeDogru) void sunucudaDogrula();
    else onayiBirak();
  }

  return (
    <Card elevation={1} className="p-6">
      <div className="flex items-center gap-3">
        <Icon name="key" className="text-primary" />
        <h2 className="text-title-medium text-on-surface">Kurtarma Anahtarınız</h2>
      </div>
      <p className="mt-2 text-body-medium text-on-surface-variant">{KURTARMA_UYARISI}</p>

      {asama === "goster" && gizli ? (
        <div className="mt-4 rounded-shape-md bg-surface-container-high p-4">
          <p className="flex items-center gap-2 text-body-medium text-on-surface">
            <Icon name="visibility_off" className="text-on-surface-variant" />
            Anahtar güvenlik için gizlendi. Beş dakikadır bu pencerede işlem yapılmadı; anahtar
            bellekte duruyor, kaybolmadı.
          </p>
          <div className="mt-3 flex flex-wrap justify-between gap-2">
            <Button variant="tonal" icon="visibility" type="button" onClick={anahtariGoster}>
              Anahtarı göster
            </Button>
            <Button icon="fact_check" type="button" onClick={dogrulamayaGec}>
              Sakladım, doğrula
            </Button>
          </div>
        </div>
      ) : asama === "goster" ? (
        <>
          <style>{YAZDIRMA_STILI}</style>
          <div id={YAZDIRMA_ALANI_ID} className="mt-4">
            <p className="text-label-large text-on-surface-variant">
              Kütüphane Defteri kurtarma anahtarı{okulAdi ? ` — ${okulAdi}` : ""}
            </p>
            <ol
              aria-label="Kurtarma anahtarının grupları"
              className="mt-2 grid grid-cols-2 gap-2 rounded-shape-md bg-surface-container-high p-4 sm:grid-cols-4"
            >
              {gruplar.map((grup, i) => (
                <li key={i} className="flex flex-col items-center">
                  <span className="text-label-small text-on-surface-variant">{i + 1}. grup</span>
                  <span className="font-mono text-title-large tracking-widest text-on-surface">
                    {grup}
                  </span>
                </li>
              ))}
            </ol>
            <p
              // Tek satırlık kopya: `select-all` + tek aralıklı yazı, elle yazımda karışmasın.
              className="mt-2 select-all break-all text-center font-mono text-body-medium text-on-surface"
              data-testid="kurtarma-anahtari"
            >
              {anahtar}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="tonal" icon="print" type="button" onClick={yazdir}>
              Yazdır
            </Button>
            <Button
              variant="tonal"
              icon="picture_as_pdf"
              type="button"
              onClick={() => void pdfKaydet()}
              disabled={indiriliyor}
            >
              {indiriliyor ? "Hazırlanıyor…" : "PDF olarak kaydet"}
            </Button>
          </div>
          {pdfHatasi && (
            <p role="alert" className="mt-2 text-body-small text-error">
              {pdfHatasi}
            </p>
          )}
          <p className="mt-3 text-body-small text-on-surface-variant">{ELLE_YAZ_METNI}</p>

          <div className="mt-5 flex justify-end">
            <Button icon="fact_check" type="button" onClick={dogrulamayaGec}>
              Sakladım, doğrula
            </Button>
          </div>
        </>
      ) : (
        <div className="mt-4">
          <h3 className="text-title-small text-on-surface">Sakladığınızı doğrulayın</h3>
          <p className="mt-1 text-body-medium text-on-surface-variant">
            {dogrulamaMetni(sorulan[0] + 1, sorulan[1] + 1)}
          </p>
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {([0, 1] as const).map((i) => {
              const yazildi = kurtarmaAnahtariniNormallestir(yanitlar[i]).length >= 4;
              return (
                <TextField
                  key={sorulan[i]}
                  label={`${sorulan[i] + 1}. grup`}
                  value={yanitlar[i]}
                  onChange={(e) => yanitDegisti(i, e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  className="font-mono"
                  error={yazildi && !dogru[i] ? "Bu grup anahtarla eşleşmiyor." : undefined}
                />
              );
            })}
          </div>
          {onay === "gonderiliyor" && (
            <p className="mt-3 text-body-medium text-on-surface-variant">Doğrulanıyor…</p>
          )}
          {dogrulandi && (
            <p
              role="status"
              className="mt-3 flex items-center gap-2 text-body-medium text-on-surface"
            >
              <Icon name="check_circle" className="text-primary" />
              {dogrulandiMetni}
            </p>
          )}
          {onay === "hata" && onayHatasi && (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <p role="alert" className="text-body-medium text-error">
                {onayHatasi}
              </p>
              <Button
                variant="tonal"
                icon="refresh"
                type="button"
                onClick={() => void sunucudaDogrula()}
              >
                Yeniden dene
              </Button>
            </div>
          )}
          <div className="mt-4">
            <Button variant="text" icon="visibility" type="button" onClick={anahtariYenidenGoster}>
              Anahtarı yeniden göster
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
