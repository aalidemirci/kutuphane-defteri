// "Kurtarma anahtarı çıktısı" kartı (E14) — parola kurulduktan SONRA çıktıyı yeniden
// almak için (ör. elle yazılmış kâğıdın temiz kopyası). Anahtar programda saklanmaz:
// kullanıcı elindeki anahtarı yazar, backend onu kurtarma sarmalına karşı doğrular
// (yanlışsa Türkçe ileti + kademeli gecikme) ve yalnız doğruysa PDF üretir.
// Ayarlar → Güvenlik'te ve sihirbazın ilk adımında (parola zaten kuruluysa) durur.

import { useState } from "react";
import type { FormEvent } from "react";

import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { useKurtarmaCiktisi } from "./kurtarma";
import { CIKTI_YENIDEN_METNI } from "./metinler";

export default function KurtarmaCiktisiKarti() {
  const snackbar = useSnackbar();
  const [anahtar, setAnahtar] = useState("");
  const { indir, indiriliyor, hata } = useKurtarmaCiktisi();

  async function gonder(e: FormEvent) {
    e.preventDefault();
    if (await indir(anahtar)) {
      // Anahtar işi bitince alanda bekletilmez.
      setAnahtar("");
      snackbar.success("Kurtarma anahtarı çıktısı PDF olarak kaydedildi.");
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-2 flex items-center gap-3">
        <Icon name="picture_as_pdf" className="text-primary" />
        <h2 className="text-title-large text-on-surface">Kurtarma anahtarı çıktısı</h2>
      </div>
      <p className="text-body-medium text-on-surface-variant">{CIKTI_YENIDEN_METNI}</p>
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
          icon="download"
          className="sm:mt-7"
          disabled={indiriliyor || !anahtar.trim()}
        >
          {indiriliyor ? "Hazırlanıyor…" : "PDF olarak kaydet"}
        </Button>
      </form>
    </Card>
  );
}
