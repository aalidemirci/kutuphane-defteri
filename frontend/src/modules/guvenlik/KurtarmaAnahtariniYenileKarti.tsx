// "Kurtarma Anahtarını Yenile" kartı (F1 eki, 22.09.2026 kullanıcı kararı 2-3).
//
// Anahtar kurulumda kaydedilemediyse (pencere kapandı, program çöktü) ya da sonradan
// kaybolduysa yenisi üretilir. Onay diyaloğu yönetici parolasını ister (başlık soru,
// gövde sonuç — sözlük §3); backend parolayı bellekteki anahtara karşı doğrular,
// aynı veri anahtarını YENİ kurtarma anahtarıyla sarmalar, önceki güvenlik dosyasını
// "guvenlik-arsiv" adıyla saklar ve yeni anahtarı BİR KEZ döndürür.
//
// Yeni anahtar bileşen durumunda DEĞİL, rota ağacının dışındaki modül belleğinde
// bekletilir (`bekleyenAnahtar`): sayfa görevli kipi, Kilitle ya da gezinmeyle
// sökülse de kaybolmaz; sihirbaz ve Güvenlik ekranı onu `KurtarmaAnahtariPaneli`
// ile saklatıp doğrulatır. Metinler dürüsttür: eski yedeklerin eski anahtarla
// açıldığını ve yenilemenin ele geçmiş anahtara karşı koruma olmadığını söyler.

import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { guvenlikApi } from "./api";
import { bekleyenKurtarmaAnahtariniYaz } from "./bekleyenAnahtar";
import {
  ELE_GECMIS_ANAHTAR_METNI,
  ESKI_YEDEK_METNI,
  YENILEME_METNI,
  YENILEME_SONUCU_METNI,
} from "./metinler";

export default function KurtarmaAnahtariniYenileKarti({
  aciklama = YENILEME_METNI,
  onYenilendi,
}: {
  /** Kartın açıklaması (sihirbazda "kaydedemediyseniz yenisini üretin" vurgusuyla). */
  aciklama?: string;
  /** Yeni anahtar bekletildikten sonra çağrılır (durum tazelemesi için). */
  onYenilendi?: () => void;
}) {
  const snackbar = useSnackbar();
  const [acik, setAcik] = useState(false);
  const [parola, setParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  function kapat() {
    setAcik(false);
    setParola("");
    setHata(null);
  }

  async function yenile(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      const sonuc = await guvenlikApi.kurtarmaAnahtariniYenile(parola);
      bekleyenKurtarmaAnahtariniYaz(sonuc.recovery_key);
      kapat();
      snackbar.success("Yeni kurtarma anahtarı üretildi. Saklayıp doğrulayın.");
      onYenilendi?.();
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Kurtarma anahtarı yenilenemedi.");
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-2 flex items-center gap-3">
        <Icon name="autorenew" className="text-primary" />
        <h2 className="text-title-large text-on-surface">Kurtarma Anahtarını Yenile</h2>
      </div>
      <p className="text-body-medium text-on-surface-variant">{aciklama}</p>
      <div className="mt-4">
        <Button variant="tonal" icon="autorenew" onClick={() => setAcik(true)}>
          Kurtarma anahtarını yenile
        </Button>
      </div>

      <Dialog open={acik} onClose={kapat} title="Kurtarma anahtarı yenilensin mi?">
        <form onSubmit={yenile} className="flex flex-col gap-4">
          <p className="text-body-medium text-on-surface">{YENILEME_SONUCU_METNI}</p>
          <p className="text-body-medium text-on-surface-variant">{ESKI_YEDEK_METNI}</p>
          <p className="text-body-small text-on-surface-variant">{ELE_GECMIS_ANAHTAR_METNI}</p>
          <TextField
            label="Yönetici parolası"
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete="current-password"
            error={hata ?? undefined}
            required
          />
          <div className="flex justify-end gap-2">
            <Button variant="text" type="button" onClick={kapat}>
              Vazgeç
            </Button>
            <Button type="submit" icon="autorenew" disabled={calisiyor || !parola}>
              {calisiyor ? "Üretiliyor…" : "Yeni anahtar üret"}
            </Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}
