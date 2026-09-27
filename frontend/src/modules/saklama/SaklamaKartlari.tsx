// Genel Bakış'ın saklama kartları (F11 — tasarım §6.4 çalışma biçimi).
//
// - "Saklama Süresi Dolan Kayıtlar": gün değişimi kapısındaki tarama süresi dolan kayıt
//   bulunca görünür; yalnız SAYI (ad yok) ve Ayarlar → Saklama bağlantısı. Onay beklemesi
//   altı ayı aşarsa kartta KAPATILAMAYAN bir uyarı durur (`role="alert"`, kapatma düğmesi
//   yok) — ancak işlem onaylanınca kalkar.
// - "Bedel Bekleyen Dosyalar": "Bedel belirlendi" ya da "Bedel teslim alındı" adımında bir
//   yıldan uzun bekleyen dosya varsa yıllık hatırlatma (sessizce silinmezler).
// Sorgu kullanıcı eylemi değildir (`etkinlik: false`); okunamazsa hiçbir şey çizilmez.

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { SAKLAMA_ADRESI, beklemeSuresi, saklamaApi } from "./api";
import type { SaklamaPanoOzeti } from "./api";

export const SAKLAMA_KARTI_BASLIGI = "Saklama Süresi Dolan Kayıtlar";
export const BEDEL_KARTI_BASLIGI = "Bedel Bekleyen Dosyalar";
/** Onay beklemesinin azami süresi (ay) — backend `saklama.AZAMI_BEKLEME_AY` ile aynı (test). */
export const AZAMI_BEKLEME_AY = 6;

function Kart({
  id,
  baslik,
  simge,
  children,
}: {
  id: string;
  baslik: string;
  simge: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id}>
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-tertiary-container text-on-tertiary-container">
            <Icon name={simge} />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id={id} className="text-title-medium font-semibold text-on-surface">
              {baslik}
            </h2>
            {children}
            <Link
              to={SAKLAMA_ADRESI}
              className="inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Saklama ekranını aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}

export default function SaklamaKartlari() {
  const [ozet, setOzet] = useState<SaklamaPanoOzeti | null>(null);

  useEffect(() => {
    let iptal = false;
    saklamaApi
      .pano()
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
      {ozet.candidates > 0 && (
        <Kart id="saklama-karti" baslik={SAKLAMA_KARTI_BASLIGI} simge="auto_delete">
          <p className="text-body-medium text-on-surface">
            {formatNumber(ozet.candidates)} kaydın saklama süresi doldu; silme ve anonimleştirme
            onayınızı bekliyor.
          </p>
          <p className="text-body-small text-on-surface-variant">
            Bekleme başlangıcı {formatDate(ozet.pending_since)}; en geç{" "}
            {formatDate(ozet.approval_deadline)} tarihine kadar onaylayın (
            {beklemeSuresi(AZAMI_BEKLEME_AY)}).
          </p>
          {ozet.overdue && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-shape-sm bg-error-container px-3 py-2 text-body-medium text-on-error-container"
            >
              <Icon name="warning" />
              <span>
                Onay bekleme süresi ({beklemeSuresi(AZAMI_BEKLEME_AY)}) doldu. Kişisel veriler
                gereğinden uzun saklanıyor; bu uyarı işlem onaylanana dek kalır.
              </span>
            </p>
          )}
        </Kart>
      )}
      {ozet.price_reminders > 0 && (
        <Kart id="bedel-karti" baslik={BEDEL_KARTI_BASLIGI} simge="request_quote">
          <p className="text-body-medium text-on-surface">
            {formatNumber(ozet.price_reminders)} kayıp/hasar dosyası bir yıldan uzun süredir bedel
            adımında bekliyor. Bu dosyalar silinmez; kapatılmaları gerekir.
          </p>
        </Kart>
      )}
    </>
  );
}
