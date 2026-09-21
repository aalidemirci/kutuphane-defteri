// Kip göstergesi — AppShell üst çubuğunda (U5, tasarım §4.4).
//
// Yönetici kipinde: kip adı + görsel geri sayım + "Görevli kipine geç" +
// "Kilitle". Görevli kipinde: kip adı + "Yönetici kipine geç" (parola
// diyaloğu) + "Kilitle". Kilitli, kurulum ya da kip okunamadıysa hiçbir şey
// göstermez (kilit ekranı ve sihirbaz kendi kapılarındadır).
//
// Geri sayım YALNIZ GÖRSELDİR: süre sunucuda tembel dolar; sayaç sıfıra
// inince kip sunucuya yeniden sorulur.
//
// Klavye kısayolu: Ctrl+Shift+G → görevli kipine geç (yalnız yönetici kipinde;
// "G" = görevli). Ctrl ya da Alt tek başına seçilmedi: tarayıcı/WebView2
// kısayollarıyla (Ctrl+G bul, Alt menü) ve barkod okuyucunun düz tuş
// akışıyla çakışmasın. Kısayol düğmenin ipucunda ve `aria-keyshortcuts`'ta yazar.

import { useCallback, useEffect, useState } from "react";

import { sonEtkinlikGonderimiAni } from "../../lib/api";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { kilitOlayiYayinla } from "../guvenlik/GuvenlikKapisi";
import YoneticiParolaDiyalogu from "./YoneticiParolaDiyalogu";
import { kipApi } from "./api";
import { kalanSaniye, sureBicimle, useEtkinlikNabzi, useKip } from "./useKip";

/** Görevli kipine geçiş kısayolu (ipucu metni). */
export const GOREVLI_KISAYOLU = "Ctrl+Shift+G";

function kisayolMu(e: KeyboardEvent): boolean {
  return e.ctrlKey && e.shiftKey && !e.altKey && !e.metaKey && (e.key === "G" || e.key === "g");
}

function hataMesaji(err: unknown, varsayilan: string): string {
  return err instanceof Error && err.message ? err.message : varsayilan;
}

export default function KipGostergesi() {
  const { ozet, alindi, yenile, ozetiYaz } = useKip();
  const snackbar = useSnackbar();
  const [simdi, setSimdi] = useState(() => Date.now());
  const [diyalogAcik, setDiyalogAcik] = useState(false);
  const durum = ozet?.durum;

  useEtkinlikNabzi(durum, ozetiYaz);

  // Saniyelik görsel geri sayım (yalnız yönetici kipinde).
  useEffect(() => {
    if (durum !== "yonetici") return;
    setSimdi(Date.now());
    const zamanlayici = window.setInterval(() => setSimdi(Date.now()), 1000);
    return () => window.clearInterval(zamanlayici);
  }, [durum]);

  const kalan = ozet ? kalanSaniye(ozet, alindi, simdi, sonEtkinlikGonderimiAni()) : null;
  const sureDoldu = kalan === 0;

  // Sayaç sıfırlandı: kip sunucuda büyük olasılıkla görevliye indi, sor.
  useEffect(() => {
    if (sureDoldu) yenile();
  }, [sureDoldu, yenile]);

  const gorevliyeGec = useCallback(async () => {
    try {
      ozetiYaz(await kipApi.gorevliyeGec());
    } catch (err) {
      snackbar.error(hataMesaji(err, "Görevli kipine geçilemedi."));
      yenile();
    }
  }, [ozetiYaz, snackbar, yenile]);

  useEffect(() => {
    if (durum !== "yonetici") return;
    const dinle = (e: KeyboardEvent) => {
      if (!kisayolMu(e) || e.repeat) return;
      e.preventDefault();
      void gorevliyeGec();
    };
    window.addEventListener("keydown", dinle);
    return () => window.removeEventListener("keydown", dinle);
  }, [durum, gorevliyeGec]);

  async function kilitle() {
    try {
      await kipApi.kilitle();
      // Kilit ekranı (GuvenlikKapisi) bu olayı dinler; kip sorgusu da yenilenir.
      kilitOlayiYayinla();
    } catch (err) {
      snackbar.error(hataMesaji(err, "Kilitlenemedi."));
    }
  }

  if (durum !== "yonetici" && durum !== "gorevli") return null;

  const yonetici = durum === "yonetici";
  const ipucu = ozet
    ? `Yönetici kipi ${ozet.bosta_dk} dakika işlem yapılmazsa ya da en geç ${ozet.mutlak_dk} dakika sonra kapanır; program görevli kipine geçer.`
    : "";

  return (
    <div className="flex items-center gap-1 sm:gap-2" aria-label="Kip" role="group">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-label-large font-semibold ${
          yonetici
            ? "bg-primary-container text-on-primary-container"
            : "bg-tertiary-container text-on-tertiary-container"
        }`}
        title={yonetici ? ipucu : undefined}
      >
        <Icon name={yonetici ? "admin_panel_settings" : "badge"} size="lg" />
        <span className="sr-only md:not-sr-only">
          {yonetici ? "Yönetici kipi" : "Görevli kipi"}
        </span>
        {yonetici && kalan !== null && (
          <span className="tabular-nums" data-testid="kip-geri-sayim">
            <span className="sr-only">, görevli kipine geçmeye kalan süre </span>
            {sureBicimle(kalan)}
          </span>
        )}
      </span>

      {yonetici ? (
        <Button
          variant="text"
          icon="badge"
          onClick={() => void gorevliyeGec()}
          aria-label="Görevli kipine geç"
          aria-keyshortcuts="Control+Shift+G"
          title={`Görevli kipine geç (${GOREVLI_KISAYOLU})`}
        >
          <span className="hidden lg:inline">Görevli kipine geç</span>
        </Button>
      ) : (
        <Button
          variant="text"
          icon="admin_panel_settings"
          onClick={() => setDiyalogAcik(true)}
          aria-label="Yönetici kipine geç"
          title="Yönetici kipine geç (yönetici parolası gerekir)"
        >
          <span className="hidden lg:inline">Yönetici kipine geç</span>
        </Button>
      )}

      <Button
        variant="text"
        icon="lock"
        onClick={() => void kilitle()}
        aria-label="Kilitle"
        title="Kilitle"
      >
        <span className="hidden lg:inline">Kilitle</span>
      </Button>

      <YoneticiParolaDiyalogu
        open={diyalogAcik}
        onClose={() => setDiyalogAcik(false)}
        onGecti={ozetiYaz}
      />
    </div>
  );
}
