// Yönetici kipine geçiş diyaloğu — görevli kipinden çıkış yönetici parolası
// ister (tasarım §4.4). Parola yalnız istek gövdesinde gider; diyalog
// kapanınca alan temizlenir (bir sonraki açılışta ekranda kalmasın).

import { useId, useState } from "react";
import type { FormEvent } from "react";

import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import TextField from "../../ui/TextField";
import { kipApi } from "./api";
import type { KipOzeti } from "./api";

interface YoneticiParolaDiyaloguProps {
  open: boolean;
  onClose: () => void;
  /** Geçiş başarılı: yeni kip özeti. */
  onGecti: (ozet: KipOzeti) => void;
}

function hataMesaji(err: unknown): string {
  return err instanceof Error && err.message ? err.message : "Yönetici kipine geçilemedi.";
}

export default function YoneticiParolaDiyalogu({
  open,
  onClose,
  onGecti,
}: YoneticiParolaDiyaloguProps) {
  const formId = useId();
  const [parola, setParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [calisiyor, setCalisiyor] = useState(false);

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
      const ozet = await kipApi.yoneticiyeGec(parola);
      setParola("");
      onGecti(ozet);
      onClose();
    } catch (err) {
      setHata(hataMesaji(err));
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={kapat}
      title="Yönetici kipine geç"
      actions={
        <>
          <Button variant="text" type="button" onClick={kapat}>
            Vazgeç
          </Button>
          <Button type="submit" form={formId} disabled={calisiyor || parola === ""}>
            {calisiyor ? "Denetleniyor…" : "Yönetici kipine geç"}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={gonder} className="flex flex-col gap-4">
        <p>Görevli kipinden çıkmak için yönetici parolasını girin.</p>
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
      </form>
    </Dialog>
  );
}
