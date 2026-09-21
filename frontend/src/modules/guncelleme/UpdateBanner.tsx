// Kabuktaki güncelleme bandı. Açılışta DENETİM YAPMAZ (tasarım T11): kendi
// başına hiçbir istek atmaz, yalnız Ayarlar → Güncelleme'deki elle denetimin
// sonucunu (`denetimOlayi.ts`) dinler. Yeni sürüm bulunduysa kullanıcı başka
// ekrana geçtiğinde de hatırlatır; "Daha sonra" o sürüm için bandı kapatır.
// Ayarlar ekranında gizlidir: orada aynı bilgi ve indirme düğmesi zaten
// Güncelleme panelindedir, iki kopya hangisinin "asıl" olduğunu sordururdu.

import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { updateApi } from "./api";
import type { UpdateStatus } from "./api";
import { DENETIM_OLAYI } from "./denetimOlayi";

const DISMISSED_KEY = "kutuphane-defteri-dismissed-update";

export default function UpdateBanner() {
  const [update, setUpdate] = useState<UpdateStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();
  const { pathname } = useLocation();

  useEffect(() => {
    const dinleyici = (event: Event) => {
      const status = (event as CustomEvent<UpdateStatus>).detail;
      const ertelendi = window.localStorage.getItem(DISMISSED_KEY) === status.latest_version;
      setUpdate(status.update_available && !ertelendi ? status : null);
    };
    window.addEventListener(DENETIM_OLAYI, dinleyici);
    return () => window.removeEventListener(DENETIM_OLAYI, dinleyici);
  }, []);

  if (!update || pathname.startsWith("/ayarlar")) return null;

  const download = async () => {
    setBusy(true);
    try {
      const blob = await updateApi.downloadInstaller();
      saveBlob(blob, update.installer_name || `kutuphane-defteri-${update.latest_version}.exe`);
      snackbar.success("Güncelleme indirildi. Programı kapatıp kurulum dosyasını çalıştırın.");
    } catch {
      snackbar.error("Güncelleme indirilemedi. Ayarlar → Güncelleme bölümünden yeniden deneyin.");
    } finally {
      setBusy(false);
    }
  };

  const dismiss = () => {
    window.localStorage.setItem(DISMISSED_KEY, update.latest_version);
    setUpdate(null);
  };

  return (
    <div
      role="status"
      className="mb-4 flex flex-wrap items-center gap-3 rounded-shape-md border border-primary/30 bg-primary-container px-4 py-3 text-on-primary-container"
    >
      <Icon name="system_update" className="shrink-0" />
      <p className="min-w-48 flex-1 text-body-medium">
        <span className="font-medium">Kütüphane Defteri {update.latest_version} hazır.</span>{" "}
        Çalışan sürüm: {update.current_version}.
        {update.platform === "linux" && " Yeni paketi indirme sayfasından alıp kurun."}
      </p>
      <div className="flex flex-wrap gap-1">
        {update.can_download && (
          <Button variant="tonal" icon="download" disabled={busy} onClick={() => void download()}>
            {busy ? "İndiriliyor…" : "Güncellemeyi indir"}
          </Button>
        )}
        <Button variant="text" onClick={dismiss}>
          Daha sonra
        </Button>
      </div>
    </div>
  );
}
