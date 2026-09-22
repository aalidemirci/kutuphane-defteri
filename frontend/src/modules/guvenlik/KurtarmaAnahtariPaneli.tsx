// Kurtarma anahtarı paneli — kurulum sihirbazının ilk adımında, yönetici parolası
// kurulur kurulmaz gösterilir (tasarım §6.3-1, E14). Eski `KurtarmaAnahtariDiyalogu`
// bu akışa uyarlandı ve yerini bu panel aldı; parola artık yalnız sihirbazda kurulur.
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
// (doğrulama kipinde anahtar ekrandan kalkar, yoksa ekrandan kopyalanırdı).
// Doğrulama istemci tarafındadır: anahtar sunucuya yalnız PDF isteğinde gider.
//
// Yazdırma notu: program bir masaüstü penceresinde (pywebview) koştuğu için
// `window.print()` bütün kabuğu basardı. Panel görünürken devreye giren küçük
// yazdırma stili sayfadaki her şeyi gizleyip yalnız anahtar alanını bırakır.
// Kural `@media print { … }` bloğunun İÇİNDEDİR, `<style media="print">`
// niteliğiyle DEĞİL: jsdom nitelik biçimini yok sayıp kuralı ekrana da uygular,
// o zaman `visibility: hidden` tüm sayfayı erişilebilirlik ağacından düşürürdü.

import { useEffect, useMemo, useState } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import {
  kurtarmaAnahtariniNormallestir,
  kurtarmaGruplari,
  rastgeleIkiGrup,
  useKurtarmaCiktisi,
} from "./kurtarma";
import { ELLE_YAZ_METNI, KURTARMA_UYARISI, dogrulamaMetni } from "./metinler";

const YAZDIRMA_ALANI_ID = "kurtarma-anahtari-yazdirma-alani";

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
  /** İki grup doğru yazılınca `true`, doğrulama bozulunca `false` bildirilir. */
  onDogrulama: (dogrulandi: boolean) => void;
  /** Doğrulanacak grupların seçimi (testte sabitlenir). */
  rastgele?: () => number;
}

type Asama = "goster" | "dogrula";

export default function KurtarmaAnahtariPaneli({
  anahtar,
  okulAdi = "",
  onDogrulama,
  rastgele,
}: KurtarmaAnahtariPaneliProps) {
  const snackbar = useSnackbar();
  const gruplar = useMemo(() => kurtarmaGruplari(anahtar), [anahtar]);
  const [asama, setAsama] = useState<Asama>("goster");
  const [sorulan, setSorulan] = useState<[number, number]>([0, 1]);
  const [yanitlar, setYanitlar] = useState<[string, string]>(["", ""]);
  const { indir, indiriliyor, hata: pdfHatasi } = useKurtarmaCiktisi();

  const dogru = sorulan.map(
    (sira, i) => kurtarmaAnahtariniNormallestir(yanitlar[i]) === gruplar[sira],
  );
  const dogrulandi = asama === "dogrula" && dogru[0] && dogru[1];

  useEffect(() => {
    onDogrulama(dogrulandi);
  }, [dogrulandi, onDogrulama]);

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
    setSorulan(rastgeleIkiGrup(gruplar.length, rastgele));
    setYanitlar(["", ""]);
    setAsama("dogrula");
  }

  function yanitDegisti(i: 0 | 1, deger: string) {
    setYanitlar((onceki) => (i === 0 ? [deger, onceki[1]] : [onceki[0], deger]));
  }

  return (
    <Card elevation={1} className="p-6">
      <div className="flex items-center gap-3">
        <Icon name="key" className="text-primary" />
        <h2 className="text-title-medium text-on-surface">Kurtarma anahtarınız</h2>
      </div>
      <p className="mt-2 text-body-medium text-on-surface-variant">{KURTARMA_UYARISI}</p>

      {asama === "goster" ? (
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
          {dogrulandi && (
            <p
              role="status"
              className="mt-3 flex items-center gap-2 text-body-medium text-on-surface"
            >
              <Icon name="check_circle" className="text-primary" />
              Doğrulandı. Kurulumun sonraki adımına geçebilirsiniz.
            </p>
          )}
          <div className="mt-4">
            <Button
              variant="text"
              icon="visibility"
              type="button"
              onClick={() => setAsama("goster")}
            >
              Anahtarı yeniden göster
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
