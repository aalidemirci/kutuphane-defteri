// Ayarlar → Güncelleme. Metin kullanıcı dilindedir (docs/sozluk.md §1): sürüm
// kaynağı "yayımlanan son sürüm", paket "kurulum dosyası"dır — "GitHub sürümü",
// "Release", "kurucu" ve özet algoritmasının adı yüzeye çıkmaz.
//
// Denetim YALNIZ "Şimdi denetle" düğmesiyle yapılır (tasarım T11): sekme
// açılınca da istek atılmaz. Sonuç kabuktaki banda da yayınlanır
// (`denetimOlayi.ts`), kullanıcı başka ekrana geçtiğinde hatırlatma sürer.
//
// Hedef GitHub'dır (kullanıcı kararı 27.09.2026). MEB ağında GitHub engellenebilir:
// sunucunun iletisi bunu söyler ve yeni sürümün indir.okulapp.org'dan elle
// denetlenebileceğini yazar (program o adrese istek atmaz). Sunucuya hiç
// ulaşılamazsa aynı ileti burada da gösterilir (`ULASILAMADI_METNI`). Hizmetin adı
// açıklama metninde geçmez (sözlük "Sürüm"); yalnız bu iletide ve Hakkında'dadır.
// Denetim düşünce iletinin altında elle denetleme bağlantısı durur (`INDIRME_SAYFASI`):
// `target="_blank"` — masaüstü penceresi onu dış tarayıcıda açar.

import { useState } from "react";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { updateApi } from "./api";
import type { UpdateStatus } from "./api";
import { denetimSonucunuYayinla } from "./denetimOlayi";

/** Denetim GitHub'a ulaşamadığında (backend `updates.ULASILAMADI_MESAJI` ile birebir). */
export const ULASILAMADI_METNI =
  "GitHub'a ulaşılamadı; okul ağında engellenmiş olabilir. Yeni sürümü " +
  "indir.okulapp.org'dan elle denetleyebilirsiniz.";

/**
 * Elle denetlemenin sayfası: programın okulapp.org'daki sayfası sürümü ve kurulum
 * dosyalarının bağlantılarını verir; dosyaların kendisi indir.okulapp.org'dan iner (R2
 * önekinin dizin sayfası yoktur — kök adres 404 verir, 27.09.2026 denetimi). Bağlantı
 * `target="_blank"` ile açılır: masaüstü penceresi (pywebview, `OPEN_EXTERNAL_LINKS_IN_BROWSER`
 * varsayılanı) onu DIŞ tarayıcıda açar. Program bu adrese kendisi istek ATMAZ.
 */
export const INDIRME_SAYFASI = "https://okulapp.org/kutuphane-defteri/";
/** Bağlantının görünen adresi (şema ve sondaki bölü olmadan). */
export const INDIRME_SAYFASI_ADI = "okulapp.org/kutuphane-defteri";

/** Dosya boyutu — Türkçe sayı biçimiyle (ondalık virgül): "41,5 MB". */
function formatBytes(bytes: number): string {
  if (bytes <= 0) return "";
  return `${formatNumber(Math.round((bytes / (1024 * 1024)) * 10) / 10)} MB`;
}

export default function UpdatePanel() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snackbar = useSnackbar();

  // Kullanıcı düğmeye bastı: sunucu önbelleği atlanır (`force`), taze sonuç alınır.
  const check = async () => {
    setChecking(true);
    setError(null);
    try {
      const sonuc = await updateApi.check(true);
      setStatus(sonuc);
      denetimSonucunuYayinla(sonuc);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : ULASILAMADI_METNI);
    } finally {
      setChecking(false);
    }
  };

  const download = async () => {
    if (!status) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await updateApi.downloadInstaller();
      saveBlob(blob, status.installer_name || `kutuphane-defteri-${status.latest_version}.exe`);
      snackbar.success("Kurulum dosyası doğrulanarak indirildi.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Güncelleme dosyası indirilemedi.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card elevation={1} className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-title-medium text-on-surface">Uygulama Güncellemesi</p>
            <p className="mt-1 text-body-medium text-on-surface-variant">
              Yayımlanan son sürüm yalnız “Şimdi denetle” düğmesine bastığınızda denetlenir; program
              açılışta internete çıkmaz. Bu istek kişisel veri taşımaz. Denetim okul ağında
              engellenirse yeni sürümü indir.okulapp.org&apos;dan elle denetleyebilirsiniz. Kurulum
              dosyası, bütünlüğü doğrulanmadan indirmeye sunulmaz.
            </p>
          </div>
          <Button
            variant="outlined"
            icon="refresh"
            disabled={checking || downloading}
            onClick={() => void check()}
          >
            {checking ? "Denetleniyor…" : "Şimdi denetle"}
          </Button>
        </div>

        {error && (
          <div className="mt-4 space-y-2">
            <div
              role="alert"
              className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
            >
              <Icon name="error" />
              <span>{error}</span>
            </div>
            {/* Denetim hangi nedenle düşerse düşsün elle denetleme yolu verilir; bağlantı
                dış tarayıcıda açılır (program o adrese istek atmaz). */}
            <p className="text-body-small text-on-surface-variant">
              Yeni sürümü ve kurulum dosyalarını tarayıcıda elle görebilirsiniz; dosyalar
              indir.okulapp.org&apos;dan iner:{" "}
              <a
                href={INDIRME_SAYFASI}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-label-large font-medium text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {INDIRME_SAYFASI_ADI}
                <Icon name="open_in_new" size="sm" />
              </a>
            </p>
          </div>
        )}

        {/* İlk denetim sürerken kart boş kalmasın (diğer panellerle aynı kalıp). */}
        {checking && !status && !error && <SkeletonList rows={2} className="mt-5" />}

        {status && (
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-shape-md bg-surface-container p-4">
              <p className="text-label-medium text-on-surface-variant">Kurulu sürüm</p>
              <p className="mt-1 text-title-large text-on-surface">{status.current_version}</p>
            </div>
            <div className="rounded-shape-md bg-surface-container p-4">
              <p className="text-label-medium text-on-surface-variant">Yayımlanan son sürüm</p>
              <p className="mt-1 text-title-large text-on-surface">{status.latest_version}</p>
            </div>
          </div>
        )}

        {status && !status.update_available && (
          <p className="mt-4 flex items-center gap-2 text-body-medium text-primary">
            <Icon name="check_circle" />
            Uygulama güncel.
          </p>
        )}

        {status?.update_available && (
          <div className="mt-4 rounded-shape-md border border-primary/30 bg-primary-container p-4 text-on-primary-container">
            <p className="text-title-small">Yeni sürüm hazır: {status.latest_version}</p>
            {status.installer_size > 0 && (
              <p className="mt-1 text-body-small">
                Windows kurulum dosyası: {formatBytes(status.installer_size)}
              </p>
            )}
            {status.platform === "linux" ? (
              // Pardus/Linux: uygulama içi indirme Windows kurulum dosyasını verirdi —
              // burada çalışmaz. Güncelleme paketle yapılır (docs/kurulum.md §3).
              <p className="mt-2 text-body-small">
                Pardus ve Linux’ta güncelleme paketle yapılır: yeni sürümün <code>.deb</code> (ya da{" "}
                <code>.tar.gz</code>) dosyasını indirme sayfasından alıp eski sürümün üzerine kurun.
                Verileriniz kurulum klasörünün dışında tutulduğu için korunur.
              </p>
            ) : (
              <>
                <p className="mt-2 text-body-small">
                  İndirme tamamlanınca programı kapatın ve indirilen kurulum dosyasını çalıştırın.
                  Verileriniz kurulum klasörünün dışında tutulduğu için korunur.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    icon="download"
                    disabled={!status.can_download || downloading}
                    onClick={() => void download()}
                  >
                    {downloading ? "İndiriliyor…" : "Doğrula ve indir"}
                  </Button>
                  {!status.can_download && (
                    <span className="self-center text-label-small">
                      Bu sürümde Windows kurulum dosyası bulunmuyor.
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
