// Çık düğmesi ve diyaloğu — üst çubukta her durumda görünür (tasarım §4.2-4, TB13).
//
// * Yönetici kipi, kilitli, kurulum: "Programdan çıkılsın mı?" onayı, parolasız.
// * Görevli kipi: yönetici parolası sorulur (kaza önleyicidir, güvenlik sınırı
//   değildir — Görev Yöneticisi süreci her durumda kapatabilir).
// * Tepsideki görevli kipi Çık'ı pencereyi öne getirir ve `kd:cik-iste` olayını
//   gönderir; diyalog bu olayla da açılır.
//
// Kip bilgisi yalnız hangi soruyu soracağımızı seçer; karar sunucudadır. Sunucu
// parola isterse (kip bu arada görevliye inmiş olabilir) diyalog parola alanına
// geçer. Başarıda program kapanır: pencere birazdan kendiliğinden kaybolur.

import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import TextField from "../../ui/TextField";
import { useKip } from "../kip/useKip";
import { CIKIS_ISTEK_OLAYI, CIKIS_PAROLASI_GEREKLI, cikisApi } from "./api";

function hataMesaji(err: unknown): string {
  return err instanceof Error && err.message ? err.message : "Programdan çıkılamadı.";
}

interface CikisDiyaloguProps {
  open: boolean;
  onClose: () => void;
  /** Görevli kipinde başlar: yönetici parolası sorulur. */
  parolaIle: boolean;
}

export function CikisDiyalogu({ open, onClose, parolaIle }: CikisDiyaloguProps) {
  const formId = useId();
  const [parola, setParola] = useState("");
  const [parolaGerekli, setParolaGerekli] = useState(parolaIle);
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const [kapaniyor, setKapaniyor] = useState(false);

  useEffect(() => {
    if (open) setParolaGerekli(parolaIle);
  }, [open, parolaIle]);

  function kapat() {
    setParola("");
    setHata(null);
    onClose();
  }

  async function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    setCalisiyor(true);
    try {
      await cikisApi.cik(parolaGerekli ? parola : undefined);
      setParola("");
      setKapaniyor(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === CIKIS_PAROLASI_GEREKLI) {
        setParolaGerekli(true);
      }
      setHata(hataMesaji(err));
    } finally {
      setCalisiyor(false);
    }
  }

  if (kapaniyor) {
    return (
      <Dialog open={open} onClose={() => undefined} title="Program kapanıyor">
        <p role="status">Kütüphane Defteri kapanıyor…</p>
      </Dialog>
    );
  }

  return (
    <Dialog
      open={open}
      onClose={kapat}
      // Sözlük §3: onay diyaloğunun başlığı sorudur; parola isteyen hâl bir formdur.
      title={parolaGerekli ? "Programdan çık" : "Programdan çıkılsın mı?"}
      actions={
        <>
          <Button variant="text" type="button" onClick={kapat}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            form={formId}
            icon="power_settings_new"
            disabled={calisiyor || (parolaGerekli && parola === "")}
          >
            {calisiyor ? "Kapatılıyor…" : "Çık"}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="flex flex-col gap-4">
        {parolaGerekli ? (
          <>
            <p>Görevli kipinde programdan çıkmak için yönetici parolasını girin.</p>
            <TextField
              label="Yönetici parolası"
              type="password"
              value={parola}
              onChange={(e) => setParola(e.target.value)}
              autoComplete="current-password"
              autoFocus
              error={hata ?? undefined}
              required
            />
          </>
        ) : (
          <>
            <p>
              Program kapanır; Ağ Kataloğu da kapanır. Pencerenin çarpısı programı kapatmaz, yalnız
              gizler.
            </p>
            {hata && (
              <p role="alert" className="text-body-medium text-error">
                {hata}
              </p>
            )}
          </>
        )}
      </form>
    </Dialog>
  );
}

/** Üst çubuktaki Çık düğmesi; tepsinin `kd:cik-iste` olayını da dinler. */
export default function CikisDugmesi() {
  const [acik, setAcik] = useState(false);
  const gorevli = useKip().ozet?.durum === "gorevli";

  useEffect(() => {
    const dinleyici = () => setAcik(true);
    window.addEventListener(CIKIS_ISTEK_OLAYI, dinleyici);
    return () => window.removeEventListener(CIKIS_ISTEK_OLAYI, dinleyici);
  }, []);

  return (
    <>
      <Button
        variant="text"
        icon="power_settings_new"
        onClick={() => setAcik(true)}
        aria-label="Çık"
        title="Programdan çık"
      >
        <span className="hidden xl:inline">Çık</span>
      </Button>
      <CikisDiyalogu open={acik} onClose={() => setAcik(false)} parolaIle={gorevli} />
    </>
  );
}

/**
 * "Programı kapatıp yeniden açın" ekranındaki doğrudan çıkış (parolasız; o ekran
 * diyalogların üstündedir, onay sorulmaz: programın yeniden açılması şarttır).
 */
export function DogrudanCikisDugmesi() {
  const [durum, setDurum] = useState<"bekliyor" | "kapaniyor" | "hata">("bekliyor");
  const [ileti, setIleti] = useState<string | null>(null);

  async function cik() {
    setIleti(null);
    try {
      await cikisApi.cik();
      setDurum("kapaniyor");
    } catch (err) {
      setDurum("hata");
      setIleti(hataMesaji(err));
    }
  }

  if (durum === "kapaniyor") {
    return (
      <p role="status" className="mt-5 text-body-medium text-on-surface-variant">
        Kütüphane Defteri kapanıyor…
      </p>
    );
  }
  return (
    <div className="mt-5 flex flex-col items-center gap-2">
      <Button icon="power_settings_new" onClick={() => void cik()}>
        Programdan çık
      </Button>
      {ileti && (
        <p role="alert" className="text-body-small text-error">
          {ileti}
        </p>
      )}
    </div>
  );
}
