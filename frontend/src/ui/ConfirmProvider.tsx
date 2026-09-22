// Onay (confirm) altyapısı (CLAUDE.md §7.5): uygulama kökünde tek M3 Dialog host'u
// + `useConfirm` hook'u. Native `window.confirm()` yerine erişilebilir ui/Dialog
// (scrim + klavye tuzağı + ESC + odak yönetimi). KVKK: onay metni (dosya/kişi adı)
// tarayıcı-native dialog yerine uygulama içinde, kontrollü bileşende gösterilir.
//
// Kullanım — native confirm'in eşdeğeri:
//   const confirm = useConfirm();
//   if (!(await confirm({ message: "'X' silinsin mi?", confirmLabel: "Sil" }))) return;
// Onayla → Promise true; Vazgeç / ESC / scrim → false.
//
// İKİNCİ DOĞRULAMA (`acknowledgeLabel`, TB18): geri alınamayan ve kararı PROGRAMIN
// DEĞİL kullanıcının verdiği işlemlerde (ör. "olası aynı kişi" birleştirmesi —
// aday yalnız ad benzerliğiyle bulunur, adaş olabilir) onay düğmesi kutu
// işaretlenmeden etkinleşmez. Kutu her açılışta boştur: bir önceki onayın
// işareti sonrakine devredilmez.

import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import Button from "./Button";
import Dialog from "./Dialog";

export interface ConfirmOptions {
  /** Gövde metni (zorunlu). */
  message: string;
  /** Başlık (varsayılan "Onay"). */
  title?: string;
  /** Onay butonu etiketi — eylemi tarif etmeli, örn. "Sil"/"Çıkar" (varsayılan "Onayla"). */
  confirmLabel?: string;
  /** İptal butonu etiketi (varsayılan "Vazgeç"). */
  cancelLabel?: string;
  /**
   * Verilirse onay düğmesi bu kutu işaretlenmeden KAPALI kalır (geri alınamayan,
   * kullanıcının kendi bilgisiyle doğrulaması gereken işlemler — TB18).
   */
  acknowledgeLabel?: string;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm yalnız ConfirmProvider içinde kullanılabilir.");
  return ctx;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [dogrulandi, setDogrulandi] = useState(false);
  const dogrulamaId = useId();
  // Bekleyen Promise'in resolve'u — StrictMode state-updater'ı iki kez çağırdığı
  // için resolve'u updater İÇİNDE değil, olay işleyicide ref üzerinden çağırırız
  // (aksi halde Promise iki kez resolve olur).
  const resolveRef = useRef<((ok: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((opts) => {
    return new Promise<boolean>((resolve) => {
      // Bekleyen önceki onay varsa iptal say (üst üste çağrıya karşı güvenlik).
      resolveRef.current?.(false);
      resolveRef.current = resolve;
      setOptions(opts);
    });
  }, []);

  const close = useCallback((ok: boolean) => {
    setOptions(null);
    const resolve = resolveRef.current;
    resolveRef.current = null;
    resolve?.(ok);
  }, []);

  // Her açılışta kutu boşalır (önceki onayın işareti devredilmez).
  useEffect(() => {
    if (options !== null) setDogrulandi(false);
  }, [options]);

  const dogrulamaGerekli = options?.acknowledgeLabel !== undefined;

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={options !== null}
        onClose={() => close(false)}
        title={options?.title ?? "Onay"}
        actions={
          <>
            <Button variant="text" onClick={() => close(false)}>
              {options?.cancelLabel ?? "Vazgeç"}
            </Button>
            <Button
              variant="filled"
              disabled={dogrulamaGerekli && !dogrulandi}
              onClick={() => close(true)}
            >
              {options?.confirmLabel ?? "Onayla"}
            </Button>
          </>
        }
      >
        {options?.message}
        {options?.acknowledgeLabel !== undefined && (
          <label
            htmlFor={dogrulamaId}
            className="mt-4 flex items-start gap-3 rounded-shape-sm bg-surface-container px-3 py-2 text-body-medium text-on-surface"
          >
            <input
              id={dogrulamaId}
              type="checkbox"
              checked={dogrulandi}
              onChange={(e) => setDogrulandi(e.target.checked)}
              className="mt-0.5 size-5 shrink-0 accent-primary"
            />
            <span>{options.acknowledgeLabel}</span>
          </label>
        )}
      </Dialog>
    </ConfirmContext.Provider>
  );
}
