// Genel Bakış'ta "Şifreli Yedeği USB Belleğe Alın" kartı (F11; tasarım §16 risk 13).
//
// Otomatik yedekler bu bilgisayardadır: disk bozulur, bilgisayar değişir ya da program
// yeniden kurulursa onlar da gider. Okulun elinde kalan tek kopya, Ayarlar → Güvenlik'ten
// indirilip USB belleğe alınan şifreli yedektir. Sunucu son indirmenin tarihini veri
// klasöründe tutar (`GET backups/external/`); süre dolunca (varsayılan 30 gün; hiç indirme
// yoksa parola kurulduktan 7 gün sonra) kart çıkar. Süre dolmadıysa, okunamazsa ya da
// parola kurulmamışsa hiçbir şey göstermez.
//
// Dürüst dil: program dosyanın USB belleğe gerçekten kopyalandığını bilemez; kart "son
// indirme"yi söyler ve kopyalamayı ister. Kişisel veri yok (yalnız tarih ve gün sayısı).

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatDate, formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { guvenlikApi } from "./api";
import type { DisYedekDurumu } from "./api";

/** Kartın adı (sözlük §4.5) — başlık ve testler buradan okur. */
export const DIS_YEDEK_KARTI_BASLIGI = "Şifreli Yedeği USB Belleğe Alın";
/** Güvenlik sekmesinin adresi (yedek indirme kartı orada). */
export const GUVENLIK_ADRESI = "/ayarlar?tab=guvenlik";

/** Kartın durum cümlesi — son indirme ya da hiç indirme olmadığı (gün sayısıyla). */
export function disYedekCumlesi(durum: DisYedekDurumu): string {
  if (durum.last_download) {
    const gun = durum.days_since ?? 0;
    return `Son şifreli yedek ${formatDate(durum.last_download)} tarihinde indirildi (${formatNumber(gun)} gün önce).`;
  }
  return "Bu bilgisayarda henüz şifreli yedek indirilmedi.";
}

/**
 * Hatırlatmanın durumu (Güvenlik → Şifreli Veritabanı Yedeği kartı): süre dolduysa ne
 * yapılacağı, dolmadıysa Genel Bakış'ın kaç gün sonra hatırlatacağı. Hiç indirme yokken ve
 * süre dolmamışken (parola yeni kurulmuş) `null` — ilk hatırlatmanın günü sunucudadır.
 */
export function disYedekHatirlatmaCumlesi(durum: DisYedekDurumu): string | null {
  if (durum.remind) {
    return "Hatırlatma süresi doldu: şifreli yedeği indirip USB belleğe kopyalayın.";
  }
  if (durum.last_download && durum.days_since !== null) {
    const kalan = Math.max(1, durum.reminder_days - durum.days_since);
    return `Genel Bakış ${formatNumber(kalan)} gün sonra yeniden hatırlatır.`;
  }
  return null;
}

export default function DisYedekKarti() {
  const [durum, setDurum] = useState<DisYedekDurumu | null>(null);

  useEffect(() => {
    let iptal = false;
    guvenlikApi
      .disYedek()
      .then((d) => {
        if (!iptal) setDurum(d);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  if (durum === null || !durum.remind) return null;

  return (
    <section aria-labelledby="dis-yedek-karti">
      <Card elevation={0} className="p-5">
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-shape-lg bg-tertiary-container text-on-tertiary-container">
            <Icon name="save" />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 id="dis-yedek-karti" className="text-title-medium font-semibold text-on-surface">
              {DIS_YEDEK_KARTI_BASLIGI}
            </h2>
            <p className="text-body-medium text-on-surface">{disYedekCumlesi(durum)}</p>
            <p className="text-body-small text-on-surface-variant">
              Programın her gün aldığı yedekler bu bilgisayardadır; disk bozulursa onlar da gider.
              Şifreli yedeği indirip USB belleğe kopyalayın ve belleği bilgisayardan ayrı saklayın.
            </p>
            <Link
              to={GUVENLIK_ADRESI}
              className="inline-flex pt-1 text-label-large text-primary underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Ayarlar → Güvenlik&apos;i aç
            </Link>
          </div>
        </div>
      </Card>
    </section>
  );
}
