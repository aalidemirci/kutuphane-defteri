// Güvenlik dosyası kayıp ekranı (tasarım §4.3 — kilitliyken guvenlik.json
// silinir, yeniden adlandırılır ya da içi boşaltılır/bozulur; backend ikisini
// aynı `security_file_missing` durumuyla bildirir). Program "parolasız"a DÖNMEZ; backend bu
// durumda veri uçlarını 423 `guvenlik_dosyasi_kayip` ile keser ve yalnız durum
// uçlarını, yedek listesini ve yedekten geri yüklemeyi açık bırakır.
//
// Ekran iki çıkış yolunu anlaşılır dille söyler:
// 1. Dosyanın kopyasını veri klasörüne geri koymak → "Yeniden denetle"
//    (backend her istekte diske baktığı için dosya döndüğü anda olağan kilit
//    ekranına geçilir).
// 2. Yedekten geri yüklemek → geri yükleme guvenlik.json'u yedeğin kurtarma
//    başlığından yeniden yazar; ardından "yeniden başlat" ekranı gelir.

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import YedektenGeriYukleme from "./YedektenGeriYukleme";
import {
  DOSYA_KAYIP_BASLIGI,
  DOSYA_KAYIP_GERI_KOY,
  DOSYA_KAYIP_METNI,
  DOSYA_KAYIP_YEDEKTEN,
} from "./metinler";

interface GuvenlikDosyasiKayipProps {
  /** Güvenlik durumunu yeniden okur (dosya geri konduysa kilit ekranına geçilir). */
  onYenidenDenetle: () => void;
}

export default function GuvenlikDosyasiKayip({ onYenidenDenetle }: GuvenlikDosyasiKayipProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
      <Card elevation={1} className="p-6">
        <div className="mb-4 flex items-center gap-3">
          <Icon name="gpp_maybe" size="lg" className="text-error" />
          <h1 className="text-headline-small text-on-surface">{DOSYA_KAYIP_BASLIGI}</h1>
        </div>
        <p className="text-body-medium text-on-surface-variant">{DOSYA_KAYIP_METNI}</p>
        <h2 className="mt-4 text-title-medium text-on-surface">Ne yapmalı?</h2>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-body-medium text-on-surface-variant">
          <li>{DOSYA_KAYIP_GERI_KOY}</li>
          <li>{DOSYA_KAYIP_YEDEKTEN}</li>
        </ol>
        <div className="mt-5">
          <Button variant="tonal" icon="refresh" onClick={onYenidenDenetle}>
            Yeniden denetle
          </Button>
        </div>
      </Card>

      <YedektenGeriYukleme kayipKipi />
    </div>
  );
}
