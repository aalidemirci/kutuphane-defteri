// Genel Bakış'ın F10 kartları (tasarım §14.1 F10): Md. 7/1 bilgi kartı ve çok okunanlar özeti.
//
// - **Kitap Sayısı 10.000'i Aştı** — elde bulunan KİTAP nüshası Yönetmelik Md. 7/1'in eşiğini
//   aşınca görünür. YALNIZ BİLGİ verir, hüküm yorumlamaz: maddenin cümlesini ve sayıyı yazar,
//   okula bir iş yüklemez (kütüphaneci ataması okulun kararı değildir). Eşik aşılmadıysa kart
//   yoktur.
// - **Çok Okunanlar** — son dönemin ve son ayın ilk üç eseri; SAYI YOK, yalnız sıra (profil
//   yasağı: bu bir eser sıralamasıdır, adlı sıralama panoya girmez). Liste boşsa kart yoktur.
//
// İkisi tek istekten beslenir (`GET library/dashboard/statistics/`, kullanıcı eylemi değildir).
// Okunamazsa hiçbir şey çizilmez; Genel Bakış'ın geri kalanı çalışır.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatNumber } from "../../lib/format";
import { YONETMELIK } from "../../lib/mevzuat";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { MD7_1_METNI, raporlarAdresi, raporlarApi } from "./api";
import type { PanoOzeti, Pencere } from "./api";

export const KITAP_ESIGI_BASLIGI = "Kitap Sayısı 10.000'i Aştı";
export const COK_OKUNANLAR_BASLIGI = "Çok Okunanlar";
/**
 * Md. 7/1 kartının sayım kuralı — sözlükle aynı ("kayıttan düşülmemiş ve devredilmemiş").
 * Kural programındır; Yönetmelik "kitap"ı tanımlamaz (F10 düzeltme turu).
 */
export const MD7_SAYIM_KURALI =
  "Sayılan, kaynak türü “Kitap” olan ve kayıttan düşülmemiş, devredilmemiş nüshalardır " +
  "(danışma kitapları dahil); süreli yayın, görsel-işitsel materyal ve dijital kaynak " +
  "sayılmaz. Kart yalnız bilgi verir.";
/** Kayıp bildirilmiş ama kayıttan düşülmemiş nüsha kayıttadır ve sayılır — kart bunu yazar. */
export function kayipDahilMetni(n: number): string {
  return `Kayıp bildirilmiş ama henüz kayıttan düşülmemiş ${formatNumber(n)} kitap bu sayıya dahildir.`;
}

const BAGLANTI =
  "inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

function KitapEsigiKarti({ ozet }: { ozet: PanoOzeti["book_threshold"] }) {
  return (
    <section aria-labelledby="kitap-esigi-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-secondary-container text-on-secondary-container">
            <Icon name="info" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="kitap-esigi-karti" className="text-title-medium font-semibold text-on-surface">
              {KITAP_ESIGI_BASLIGI}
            </h2>
            <p className="text-body-medium text-on-surface">
              {`Elde bulunan kitap: ${formatNumber(ozet.in_stock_books)}.`}
            </p>
            <figure className="rounded-shape-md border-l-4 border-outline bg-surface-container px-3 py-2">
              <blockquote className="text-body-small text-on-surface">{`“${MD7_1_METNI}”`}</blockquote>
              <figcaption className="text-body-small text-on-surface-variant">
                {`${YONETMELIK}, Md. 7/1`}
              </figcaption>
            </figure>
            <p className="text-body-small text-on-surface-variant">{MD7_SAYIM_KURALI}</p>
            {ozet.lost_books > 0 && (
              <p className="text-body-small text-on-surface-variant">
                {kayipDahilMetni(ozet.lost_books)}
              </p>
            )}
          </div>
        </div>
      </Card>
    </section>
  );
}

function KisaListe({ baslik, pencere }: { baslik: string; pencere: Pencere }) {
  return (
    <div className="min-w-0">
      <p className="text-label-medium text-on-surface-variant">{`${baslik} · ${pencere.label}`}</p>
      <ol aria-label={`${baslik}: ${pencere.label}`} className="mt-1 space-y-0.5">
        {pencere.works.map((e) => (
          <li key={e.work_id} className="truncate text-body-medium text-on-surface">
            {`${e.rank}. ${e.title}`}
            {e.authors && <span className="text-on-surface-variant">{` — ${e.authors}`}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

function CokOkunanlarKarti({ ozet }: { ozet: PanoOzeti["popular"] }) {
  const donem = ozet.term && ozet.term.works.length > 0 ? ozet.term : null;
  const ay = ozet.month && ozet.month.works.length > 0 ? ozet.month : null;
  if (donem === null && ay === null) return null;
  return (
    <section aria-labelledby="cok-okunanlar-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-primary-container text-primary">
            <Icon name="trending_up" />
          </span>
          <div className="min-w-0 flex-1 space-y-2">
            <h2
              id="cok-okunanlar-karti"
              className="text-title-medium font-semibold text-on-surface"
            >
              {COK_OKUNANLAR_BASLIGI}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {donem && <KisaListe baslik="Dönem" pencere={donem} />}
              {ay && <KisaListe baslik="Ay" pencere={ay} />}
            </div>
            <p className="text-body-small text-on-surface-variant">
              Sıra farklı üye sayısına göredir; sayı gösterilmez.
            </p>
            <Link to={raporlarAdresi("cok-okunanlar")} className={BAGLANTI}>
              Çok Okunanlar&apos;ı aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}

export default function RaporKartlari() {
  const [ozet, setOzet] = useState<PanoOzeti | null>(null);

  useEffect(() => {
    let iptal = false;
    raporlarApi
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
      {ozet.book_threshold.exceeded && <KitapEsigiKarti ozet={ozet.book_threshold} />}
      <CokOkunanlarKarti ozet={ozet.popular} />
    </>
  );
}
