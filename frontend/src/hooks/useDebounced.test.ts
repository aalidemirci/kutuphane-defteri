// Gecikmeli değer kancası: arama kutusu her tuşta istek attırmasın diye değeri
// bekletir. Sahte zamanlayıcıyla sınanır — gerçek beklemede test yavaşlar ve
// yarış üretir.

import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useDebounced } from "./useDebounced";

afterEach(() => {
  vi.useRealTimers();
});

describe("useDebounced", () => {
  it("ilk değeri hemen döndürür", () => {
    const { result } = renderHook(() => useDebounced("şiir"));
    expect(result.current).toBe("şiir");
  });

  it("gecikme dolmadan yeni değeri vermez", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ deger }) => useDebounced(deger), {
      initialProps: { deger: "" },
    });

    rerender({ deger: "ş" });
    rerender({ deger: "şi" });
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("şi");
  });

  it("gecikme süresi ayarlanabilir", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ deger }) => useDebounced(deger, 50), {
      initialProps: { deger: "a" },
    });

    rerender({ deger: "b" });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current).toBe("b");
  });
});
