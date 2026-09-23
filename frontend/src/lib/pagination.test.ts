import { describe, expect, it } from "vitest";

import { emptyPage, geriDusulecekOffset, unwrap, type Paginated } from "./pagination";

describe("unwrap", () => {
  it("sayfalı yanıttan results dizisini çıkarır", () => {
    const page: Paginated<number> = { count: 2, next: null, previous: null, results: [1, 2] };
    expect(unwrap(page)).toEqual([1, 2]);
  });

  it("düz diziyi olduğu gibi döndürür", () => {
    expect(unwrap([3, 4])).toEqual([3, 4]);
  });

  it("boş sonuç listesini korur", () => {
    const page: Paginated<string> = { count: 0, next: null, previous: null, results: [] };
    expect(unwrap(page)).toEqual([]);
  });
});

describe("emptyPage", () => {
  it("ilk çizim için sayısı sıfır, sonucu boş bir sayfa verir", () => {
    expect(emptyPage<number>()).toEqual({ count: 0, next: null, previous: null, results: [] });
  });
});

describe("geriDusulecekOffset", () => {
  const bos: Paginated<number> = { count: 0, next: null, previous: null, results: [] };
  const dolu: Paginated<number> = { count: 1, next: null, previous: null, results: [1] };

  it("dolu sayfada geri düşülmez", () => {
    expect(geriDusulecekOffset(dolu, 25, 25)).toBeNull();
  });

  it("ilk sayfa boşsa geri düşülmez (kayıt gerçekten yok)", () => {
    expect(geriDusulecekOffset(bos, 0, 25)).toBeNull();
  });

  it("son sayfadaki tek kayıt silinince bir önceki sayfaya düşülür", () => {
    expect(geriDusulecekOffset(bos, 25, 25)).toBe(0);
    expect(geriDusulecekOffset(bos, 75, 25)).toBe(50);
  });

  it("offset sayfa boyutundan küçükse sıfıra düşülür (eksiye inmez)", () => {
    expect(geriDusulecekOffset(bos, 10, 25)).toBe(0);
  });
});
