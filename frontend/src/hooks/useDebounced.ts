// Gecikmeli (debounce) değer — sunucu tarafı aramanın ön yüz ayağı.
// Arama sunucudadır (F2 sözleşmesi §4: "arama gecikmeli ve sunucuda"); her tuş
// vuruşunda istek atmak on binlik bir katalogda pencereyi kilitler. Kanca yalnız
// değeri geciktirir, isteği çağıran yer atar.
//
// Kişiler sayfası da aynı deseni kullanır; kopya yerine tek kaynak burasıdır.

import { useEffect, useState } from "react";

/** `value`'nun `delay` ms boyunca değişmemiş hâli (varsayılan 300 ms). */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
