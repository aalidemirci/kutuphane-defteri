// Genel Bakış'ın dolaşım kartları (F6; A11, T15).
//
// - **Gecikmiş Ödünçler**: yalnız SAYI ("N ödünç gecikti"); liste kartın açtığı
//   sayfadadır ve yalnız yönetici kipindedir. Gecikme yoksa kart görünmez.
// - **Son Oturumu Kontrol Edin**: önceki oturum düzensiz bittiyse (elektrik
//   kesintisi, zorla kapatma) son işlemler diske yazılmamış olabilir. Kart diske
//   yazılmış son ödünç ve iadeleri gösterir ki masadaki kitaplarla karşılaştırılsın.
//   "Kontrol ettim" kartı bu oturum için kapatır.
//
// Sorgular kullanıcı eylemi değildir (`X-KD-Etkinlik` gitmez). Okunamazsa kart
// gösterilmez; sayfanın geri kalanı çalışır.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatDateTime, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import ErrorBand, { hataOku } from "../../ui/ErrorBand";
import type { SayfaHatasi } from "../../ui/ErrorBand";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { uyelikApi } from "./api";
import type { CirculationSummary, RecentTransaction } from "./api";
import { GECIKMIS_ODUNCLER_ADRESI, GECIKMIS_ODUNCLER_BASLIGI } from "./GecikmisOdunclerPage";

export const KAPANIS_KARTI_BASLIGI = "Son Oturumu Kontrol Edin";

export default function DolasimKartlari() {
  const [ozet, setOzet] = useState<CirculationSummary | null>(null);

  useEffect(() => {
    let iptal = false;
    uyelikApi
      .dolasimOzeti()
      .then((o) => {
        if (!iptal) setOzet(o);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  if (ozet === null) return null;
  return (
    <>
      {ozet.unexpected_shutdown && <KapanisKarti onKapandi={setOzet} />}
      {ozet.overdue_count > 0 && <GecikmeKarti sayi={ozet.overdue_count} />}
    </>
  );
}

function GecikmeKarti({ sayi }: { sayi: number }) {
  return (
    <section aria-labelledby="gecikme-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-error-container text-on-error-container">
            <Icon name="event_busy" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="gecikme-karti" className="text-title-medium font-semibold text-on-surface">
              {GECIKMIS_ODUNCLER_BASLIGI}
            </h2>
            <p className="text-body-medium text-on-surface">
              {formatNumber(sayi)} ödüncün iade tarihi geçti.
            </p>
            <p className="text-body-small text-on-surface-variant">
              Kişiye özel iade hatırlatma pusulasını ve gecikmiş ödünç listesini oradan basın.
            </p>
            <Link
              to={GECIKMIS_ODUNCLER_ADRESI}
              className="inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Gecikmiş Ödünçler&apos;i aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}

function KapanisKarti({ onKapandi }: { onKapandi: (ozet: CirculationSummary) => void }) {
  const snackbar = useSnackbar();
  const [islemler, setIslemler] = useState<RecentTransaction[] | null>(null);
  const [hata, setHata] = useState<SayfaHatasi | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    let iptal = false;
    uyelikApi
      .sonIslemler()
      .then((l) => {
        if (!iptal) setIslemler(l);
      })
      .catch((e: unknown) => {
        if (!iptal) setHata(hataOku(e, "Son işlemler yüklenemedi."));
      });
    return () => {
      iptal = true;
    };
  }, []);

  const kontrolEttim = async () => {
    setMesgul(true);
    try {
      onKapandi(await uyelikApi.kontrolEttim());
      snackbar.success("Son oturumun kontrolü tamamlandı.");
    } catch (e) {
      setHata(hataOku(e, "Kart kapatılamadı."));
    } finally {
      setMesgul(false);
    }
  };

  return (
    <section aria-labelledby="kapanis-karti">
      <Card elevation={0} className="space-y-3 p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-tertiary-container text-on-tertiary-container">
            <Icon name="power_off" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="kapanis-karti" className="text-title-medium font-semibold text-on-surface">
              {KAPANIS_KARTI_BASLIGI}
            </h2>
            <p className="text-body-medium text-on-surface">
              Program önceki oturumda düzgün kapanmadı (elektrik kesintisi ya da zorla kapatma
              olabilir). Son oturumdaki ödünç ve iadeleri kontrol edin.
            </p>
            <p className="text-body-small text-on-surface-variant">
              Aşağıda kayda geçmiş son işlemler var. Masada verildiğini ya da alındığını bildiğiniz
              bir kitap listede yoksa işlemi yeniden yapın.
            </p>
          </div>
        </div>
        {hata && <ErrorBand hata={hata} />}
        {islemler !== null &&
          (islemler.length === 0 ? (
            <p className="text-body-small text-on-surface-variant">Kayıtlı ödünç ya da iade yok.</p>
          ) : (
            <ul className="max-h-72 divide-y divide-outline-variant/60 overflow-y-auto rounded-shape-sm border border-outline-variant/70">
              {islemler.map((i) => (
                <li key={`${i.kind}-${i.loan_id}`} className="px-3 py-2">
                  <span className="block text-body-medium text-on-surface">
                    {i.kind_display} · {i.work_title}
                  </span>
                  <span className="block text-body-small text-on-surface-variant">
                    {formatDateTime(i.at)} · {i.barcode_display}
                    {i.full_name ? ` · ${i.full_name}` : ""}
                    {i.person_label ? ` (${i.person_label})` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ))}
        <Button
          variant="tonal"
          icon="task_alt"
          onClick={() => void kontrolEttim()}
          disabled={mesgul}
        >
          Kontrol ettim
        </Button>
      </Card>
    </section>
  );
}
