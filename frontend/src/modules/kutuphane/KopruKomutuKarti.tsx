// Yapay zekâ köprüsünün komut kartı (tasarım §8.2).
//
// **Program hiçbir yapay zekâ servisine bağlanmaz.** Köprü bir METİN
// köprüsüdür: kullanıcı komutu panodan kendi aracına yapıştırır, dönen JSON'u
// programa yükler. Bu karttan çıkan tek istek, komut metnini SUNUCUDAN (yani
// programın kendisinden) okuyan `library/import/ai-prompt/` isteğidir.
//
// Ekrandaki dört uyarı maddesi sunucudan gelir (`ai_bridge.UI_NOTES`). Ön yüz
// onların kopyasını YAZMAZ: metin tek kaynaktan beslenir, biri değişince öbürü
// eskimez. Maddelerin sonuncusu bu adımın MEB Bilgi ve Sistem Güvenliği
// Yönergesi'yle çatışabileceğini söyler ve asıl yolun Excel olduğunu hatırlatır
// — bu yüzden kart kapatılamaz ve uyarılar katlanmış durmaz.
//
// KAPI FAIL-CLOSED'DIR: metin yüklenemezse (kilit, kip, geçici hata) uyarılar
// ekrana hiç basılamaz. O durumda `onDurum(false)` ile köprünün girdi kutusu da
// kapatılır; yoksa kullanıcı, okulun kitap listesini dışarı çıkaran adımı
// uyarıları hiç görmeden tamamlayabilirdi.

import { useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { kutuphaneApi } from "./api";
import type { KopruKomutu } from "./api";

/**
 * Metni panoya kopyalar. Pano API'si pywebview penceresinde ya da eski
 * motorlarda bulunmayabilir; o durumda gizli bir metin alanı üzerinden
 * kopyalanır. İkisi de olmazsa `false` döner ve çağıran kullanıcıya metni elle
 * seçmesini söyler.
 */
export async function panoyaKopyala(metin: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(metin);
      return true;
    }
  } catch {
    // Pano izni yoksa aşağıdaki yedek yol denenir.
  }
  try {
    const alan = document.createElement("textarea");
    alan.value = metin;
    alan.setAttribute("readonly", "");
    alan.style.position = "fixed";
    alan.style.opacity = "0";
    document.body.appendChild(alan);
    alan.select();
    const oldu = document.execCommand("copy");
    alan.remove();
    return oldu;
  } catch {
    return false;
  }
}

export default function KopruKomutuKarti({
  onDurum,
}: {
  /** Uyarılar ekranda mı? Köprünün girdi kutusu buna bağlıdır (fail-closed). */
  onDurum?: (hazir: boolean) => void;
}) {
  const [komut, setKomut] = useState<KopruKomutu | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    kutuphaneApi
      .kopruKomutu()
      .then((sonuc) => {
        if (!iptal) {
          setKomut(sonuc);
          setHata(null);
          onDurum?.(sonuc.notes.length > 0);
        }
      })
      .catch((e: unknown) => {
        if (!iptal) {
          setHata(e instanceof ApiError ? e.message : "Komut metni yüklenemedi.");
          onDurum?.(false);
        }
      });
    return () => {
      iptal = true;
    };
    // `onDurum` kararlı bir geri çağrıdır; bağımlılığa konsaydı her yeniden
    // çizimde istek yenilenirdi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const kopyala = async (): Promise<void> => {
    if (komut === null) return;
    if (await panoyaKopyala(komut.prompt)) snackbar.success("Komut metni panoya kopyalandı.");
    else snackbar.error("Komut metni kopyalanamadı; metni seçip elle kopyalayın.");
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--kd-panel-padding)] shadow-elevation-1">
      <div>
        <p className="text-title-medium text-on-surface">Yapay Zekâ Köprüsü</p>
        <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">
          Elinizdeki dağınık kitap listesini programın anladığı biçime çevirmek için: komut metnini
          kopyalayıp kullandığınız araca yapıştırın, listenizi de altına ekleyin; aracın verdiği
          JSON metnini aşağıya yapıştırıp önizleyin.
        </p>
      </div>

      {komut && (
        <ul className="list-disc space-y-1 rounded-shape-sm bg-tertiary-container px-6 py-3 text-body-small text-on-tertiary-container">
          {komut.notes.map((not) => (
            <li key={not}>{not}</li>
          ))}
        </ul>
      )}

      {hata && (
        <p role="alert" className="flex items-start gap-2 text-body-medium text-error">
          <Icon name="error" size="lg" />
          {hata} Uyarılar ekrana gelene kadar köprü kullanılamaz; sayfayı yenileyin ya da asıl yol
          olan Excel ile içe aktarın.
        </p>
      )}

      {komut && (
        <>
          <label
            htmlFor="kopru-komut-metni"
            className="block text-label-large text-on-surface-variant"
          >
            Komut metni
          </label>
          <textarea
            id="kopru-komut-metni"
            readOnly
            rows={8}
            value={komut.prompt}
            className="block w-full rounded-shape-xs border border-outline bg-surface px-4 py-3 font-mono text-body-small text-on-surface outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="tonal" icon="content_copy" onClick={() => void kopyala()}>
              Komutu kopyala
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}
