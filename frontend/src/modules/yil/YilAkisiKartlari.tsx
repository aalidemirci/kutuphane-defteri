// Genel Bakış'ın yıl akışı kartları (F7; tasarım §8.3 — "Genel Bakış'tan açılır, tarih
// penceresinde kart çıkar").
//
// - **Yıl Sonu**: 1 Mayıs - 30 Haziran (ders yılı daha geç biterse bitişten iki hafta
//   sonrasına dek) görünür; yalnız SAYI yazar.
// - **Yıl Başı**: 15 Ağustos - 31 Ekim (ya da ders yılı başlangıcının çevresi) görünür;
//   bütün adımlar tamamsa görünmez.
// - **Yıl Sonu Raporu** (F8; Md. 12/1, E9): yıl sonu penceresinde, etkin yılın raporu
//   sonlandırılmadıkça görünür (hazırlanmadı / taslak).
//
// Pencere ve sayılar sunucudan gelir (`GET library/year-flows/`, kişisiz). Sorgu kullanıcı
// eylemi değildir (`X-KD-Etkinlik` gitmez). Okunamazsa kart gösterilmez.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { YIL_SONU_RAPORU_ADRESI, YIL_SONU_RAPORU_BASLIGI } from "../ayiklama/api";
import {
  YIL_BASI_ADRESI,
  YIL_BASI_BASLIGI,
  YIL_SONU_ADRESI,
  YIL_SONU_BASLIGI,
  yilApi,
} from "./api";
import type { YilAkislari } from "./api";

const BAGLANTI =
  "inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary";

function AkisKarti({
  id,
  icon,
  baslik,
  metin,
  aciklama,
  to,
  baglanti,
}: {
  id: string;
  icon: string;
  baslik: string;
  metin: string;
  aciklama: string;
  to: string;
  baglanti: string;
}) {
  return (
    <section aria-labelledby={id}>
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-secondary-container text-on-secondary-container">
            <Icon name={icon} />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id={id} className="text-title-medium font-semibold text-on-surface">
              {baslik}
            </h2>
            <p className="text-body-medium text-on-surface">{metin}</p>
            <p className="text-body-small text-on-surface-variant">{aciklama}</p>
            <Link to={to} className={BAGLANTI}>
              {baglanti}
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}

export default function YilAkisiKartlari() {
  const [akislar, setAkislar] = useState<YilAkislari | null>(null);

  useEffect(() => {
    let iptal = false;
    yilApi
      .akislar()
      .then((a) => {
        if (!iptal) setAkislar(a);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  if (akislar === null) return null;
  const sonu = akislar.year_end;
  const basi = akislar.year_start;
  const basiTamam = Object.values(basi.steps).every(Boolean);
  const c = sonu.counts;

  return (
    <>
      {sonu.in_window && (
        <AkisKarti
          id="yil-sonu-karti"
          icon="event_upcoming"
          baslik={YIL_SONU_BASLIGI}
          metin={
            c.persons > 0
              ? `${formatNumber(c.open_loans)} açık ödünç; kütüphaneyle açık işi olan ${formatNumber(
                  c.persons,
                )} kişi (son sınıflarda ${formatNumber(c.graduating_persons)}).`
              : "Kütüphaneyle açık işi olan kimse yok."
          }
          aciklama="Son ödünç tarihi, kitap toplama, son sınıflar ve ilişik belgeleri adım adım."
          to={YIL_SONU_ADRESI}
          baglanti="Yıl Sonu'nu aç"
        />
      )}
      {sonu.in_window && !(sonu.annual_review?.is_finalized ?? false) && (
        <AkisKarti
          id="yil-sonu-raporu-karti"
          icon="summarize"
          baslik={YIL_SONU_RAPORU_BASLIGI}
          metin={
            !sonu.annual_review
              ? "Bu ders yılının raporu henüz hazırlanmadı."
              : "Rapor taslak; sonlandırılmadı."
          }
          aciklama="Kaynaklar gözden geçirilir ve tespit edilen hususlar raporla okul müdürlüğüne bildirilir (Yönetmelik Md. 12/1)."
          to={YIL_SONU_RAPORU_ADRESI}
          baglanti="Yıl Sonu Raporu'nu aç"
        />
      )}
      {basi.in_window && !basiTamam && (
        <AkisKarti
          id="yil-basi-karti"
          icon="event_available"
          baslik={YIL_BASI_BASLIGI}
          metin={
            basi.school_year_ready
              ? `Yeni ders yılı için ${formatNumber(
                  Object.values(basi.steps).filter((t) => !t).length,
                )} adım bekliyor.`
              : "Bu yılın ders yılı henüz açılmadı."
          }
          aciklama="Ders yılı, yeni e-Okul listeleri, Ayrılış Havuzu ve kapalı günler adım adım."
          to={YIL_BASI_ADRESI}
          baglanti="Yıl Başı'nı aç"
        />
      )}
    </>
  );
}
