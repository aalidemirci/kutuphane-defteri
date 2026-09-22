// "Kurtarma Anahtarını Doğrula" kartı (F1 eki, 22.09.2026 kullanıcı kararı 2).
//
// Anahtar ekranda değilken (sihirbaz yeniden açıldı, pencere kapanıp açıldı ya da
// kurulum bu karardan önce tamamlandı) saklandığını doğrulamanın yolu: kullanıcı
// kâğıttaki ya da PDF'teki anahtarın TAMAMINI yazar; backend onu kurtarma
// sarmalına karşı doğrular (yanlışsa Türkçe ileti + kademeli gecikme) ve güvenlik
// dosyasına "saklandı" damgasını yazar. Anahtar programda saklanmaz; iş bitince
// alan boşaltılır. Kurulum sihirbazının ilk adımında ve Ayarlar → Güvenlik'te,
// yalnız `recovery_key_confirmed` yanlışken gösterilir.

import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { guvenlikApi } from "./api";
import type { GuvenlikDurumu } from "./api";
import { DOGRULA_KARTI_METNI } from "./metinler";

export default function KurtarmaAnahtariniDogrulaKarti({
  onDogrulandi,
}: {
  /** Sunucu damgayı yazınca güncel güvenlik durumuyla çağrılır. */
  onDogrulandi: (durum: GuvenlikDurumu) => void;
}) {
  const snackbar = useSnackbar();
  const [anahtar, setAnahtar] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      const durum = await guvenlikApi.kurtarmaAnahtariniDogrula(anahtar);
      // Anahtar işi bitince alanda bekletilmez.
      setAnahtar("");
      snackbar.success("Kurtarma anahtarının saklandığı doğrulandı.");
      onDogrulandi(durum);
    } catch (err) {
      setHata(err instanceof ApiError ? err.message : "Kurtarma anahtarı doğrulanamadı.");
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-2 flex items-center gap-3">
        <Icon name="fact_check" className="text-primary" />
        <h2 className="text-title-large text-on-surface">Kurtarma Anahtarını Doğrula</h2>
      </div>
      <p className="text-body-medium text-on-surface-variant">{DOGRULA_KARTI_METNI}</p>
      <form onSubmit={gonder} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
        <TextField
          className="flex-1 font-mono"
          label="Kurtarma anahtarı"
          value={anahtar}
          onChange={(e) => setAnahtar(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          error={hata ?? undefined}
          required
        />
        <Button
          type="submit"
          variant="tonal"
          icon="fact_check"
          className="sm:mt-7"
          disabled={calisiyor || !anahtar.trim()}
        >
          {calisiyor ? "Doğrulanıyor…" : "Doğrula"}
        </Button>
      </form>
    </Card>
  );
}
