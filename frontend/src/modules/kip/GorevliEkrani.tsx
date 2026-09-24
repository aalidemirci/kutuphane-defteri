// Görevli kipinin ana ekranı (U5, tasarım §4.4). Görevli kipinde rotaların
// YERİNE gösterilir: masadaki görevli yönetici ekranlarına (kişiler, ayarlar,
// yedek…) ulaşamaz. Backend bunu ayrıca keser (403 `kip_yetkisiz`); bu ekran
// kullanıcıya boş ya da hata dolu sayfalar yerine ne yapacağını söyler.
// Dolaşım masası bu ekrana kendi fazında eklenir; metin gelecek vadetmez.
//
// Görevliye açık masa işleri buradan açılır. Bugün tek iş etiket doğrulama
// okutmasıdır (kullanıcı kararı 24.09.2026): yapıştırılan etiket okutulur; sunucu
// görevli kipinde yalnız `POST library/labels/verify/` ucunu geçirir ve nüsha
// özetinden yalnız barkodu ve eser adını döndürür. Etiketler sayfasının öbür
// sekmeleri (basım, basım geçmişi, boş barkod, şablonlar) ve "Doğrulanmamış
// Etiketler" listesi yönetici kipindedir. Okutma açıkken de sayfanın h1'i
// "Görevli Kipi"dir (üst çubukla aynı — docs/sozluk.md §4); iş bölüm başlığıdır.

import { useState } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import DogrulamaOkutmasi from "../kutuphane/DogrulamaOkutmasi";
import YoneticiParolaDiyalogu from "./YoneticiParolaDiyalogu";
import type { KipOzeti } from "./api";

/** Üst çubuk başlığı sayfanın h1'iyle aynıdır (docs/sozluk.md §4). */
export const GOREVLI_EKRANI_BASLIGI = "Görevli Kipi";

export const GOREVLI_EKRANI_METNI =
  "Bu kipte yalnız masa işleri yapılır; yönetici işlemleri için yönetici kipine geçin.";

/** Görevli ekranından açılan doğrulama okutmasının bölüm başlığı (Etiketler'deki sekme adı). */
export const GOREVLI_DOGRULAMA_BASLIGI = "Doğrulama Okutması";
/** Doğrulama okutmasını açan ve kapatan düğmeler (kılavuz bu adlarla anlatır). */
export const GOREVLI_DOGRULAMA_DUGMESI = "Doğrulama okutmasını aç";
export const GOREVLI_DOGRULAMA_BITIR = "Okutmayı bitir";

/**
 * Kurtarma anahtarı (kurulumda verilen ya da Ayarlar → Güvenlik'te yenilenen)
 * doğrulanmadan görevli kipine geçilirse (düğme, kısayol) gösterilir: anahtar
 * kaybolmadı, yönetici kipine dönülünce anahtarın gösterildiği ekran onu yeniden
 * gösterir (`guvenlik/bekleyenAnahtar`). Kurulum sürerken süreler kipi düşürmez.
 */
export const BEKLEYEN_ANAHTAR_METNI =
  "Kurtarma anahtarınız henüz doğrulanmadı. Yönetici kipine geçtiğinizde anahtar yeniden gösterilir; programı kapatmayın.";

function BekleyenAnahtarUyarisi() {
  return (
    <p className="mt-4 flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-left text-body-medium text-on-tertiary-container">
      <Icon name="key" size="lg" />
      <span>{BEKLEYEN_ANAHTAR_METNI}</span>
    </p>
  );
}

export default function GorevliEkrani({
  onGecti,
  anahtarBekliyor = false,
}: {
  onGecti: (ozet: KipOzeti) => void;
  /** Kurulumda doğrulanmamış kurtarma anahtarı bellekte bekliyor mu? */
  anahtarBekliyor?: boolean;
}) {
  const [diyalogAcik, setDiyalogAcik] = useState(false);
  const [dogrulama, setDogrulama] = useState(false);

  const yoneticiyeGec = (
    <Button icon="admin_panel_settings" onClick={() => setDiyalogAcik(true)}>
      Yönetici kipine geç
    </Button>
  );
  const parolaDiyalogu = (
    <YoneticiParolaDiyalogu
      open={diyalogAcik}
      onClose={() => setDiyalogAcik(false)}
      onGecti={onGecti}
    />
  );

  if (dogrulama) {
    return (
      <div className="space-y-[var(--kd-page-gap)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-headline-small text-on-surface">{GOREVLI_EKRANI_BASLIGI}</h1>
            <h2 className="mt-1 flex items-center gap-2 text-title-large text-on-surface">
              <Icon name="barcode_reader" size="lg" className="text-primary" />
              {GOREVLI_DOGRULAMA_BASLIGI}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outlined" icon="arrow_back" onClick={() => setDogrulama(false)}>
              {GOREVLI_DOGRULAMA_BITIR}
            </Button>
            {yoneticiyeGec}
          </div>
        </div>
        {anahtarBekliyor && <BekleyenAnahtarUyarisi />}
        <DogrulamaOkutmasi gorevli />
        {parolaDiyalogu}
      </div>
    );
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-4">
      <Card elevation={1} className="w-full max-w-lg p-8 text-center">
        <Icon name="badge" size="5xl" className="text-primary" />
        <h1 className="mt-3 text-headline-small text-on-surface">{GOREVLI_EKRANI_BASLIGI}</h1>
        <p className="mt-3 text-body-medium text-on-surface-variant">{GOREVLI_EKRANI_METNI}</p>
        {anahtarBekliyor && <BekleyenAnahtarUyarisi />}
        <p className="mt-4 text-body-medium text-on-surface-variant">
          Kitaplara yapıştırılan kütüphane etiketlerini okutarak doğrulayabilirsiniz.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button variant="outlined" icon="barcode_reader" onClick={() => setDogrulama(true)}>
            {GOREVLI_DOGRULAMA_DUGMESI}
          </Button>
          {yoneticiyeGec}
        </div>
      </Card>
      {parolaDiyalogu}
    </div>
  );
}
