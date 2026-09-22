// Katalog Excel şablonunu indirme — TEK işlev (tasarım §8.1). Genel Bakış'taki
// "Katalog Excel Şablonu" kartı ve "Başlangıç Yol Haritası"nın şablon maddesi aynı
// kancayı kullanır; indirme, dosya adı ve bildirim iki yerde ayrı yazılmaz.

import { useState } from "react";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { katalogSablonuDosyaAdi, kutuphaneApi } from "./api";

/**
 * `indir()` şablonu indirir; başarıda `true` döner ve `onIndirildi` çağrılır
 * (yol haritası maddeyi işaretler). Hata snackbar'la gösterilir.
 */
export function useKatalogSablonuIndirme(onIndirildi?: () => void) {
  const snackbar = useSnackbar();
  const [indiriliyor, setIndiriliyor] = useState(false);

  async function indir(): Promise<boolean> {
    setIndiriliyor(true);
    try {
      const sablon = await kutuphaneApi.catalogTemplate();
      saveBlob(sablon, katalogSablonuDosyaAdi());
      snackbar.success("Katalog Excel şablonu indirildi.");
      onIndirildi?.();
      return true;
    } catch (error) {
      snackbar.error(error instanceof ApiError ? error.message : "Şablon indirilemedi.");
      return false;
    } finally {
      setIndiriliyor(false);
    }
  }

  return { indir, indiriliyor };
}
