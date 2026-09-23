// Okutulan kodun türü (§7.1) — ön yüzdeki ayrımın backend `barcode.py` ile aynı
// kararları vermesi sınanır. İki kopyanın ayrışması, masadaki kullanıcıya iki
// katmanda farklı ileti göstermek demektir (CLAUDE.md §3 `version_key` dersi).

import { describe, expect, it } from "vitest";

import { barkodBicimle, isbnNormalize, kodTuru, taramaNormalize } from "./tarama";

describe("kodTuru", () => {
  it("10 hane + makul yıl öneki nüsha barkodudur", () => {
    expect(kodTuru("2026000123")).toBe("COPY");
    expect(kodTuru("2026-000123")).toBe("COPY");
    // Okuyucular araya boşluk koyabilir; rakam dışı her şey atılır.
    expect(kodTuru(" 2026 000123\n")).toBe("COPY");
  });

  it("8 hane ve 9 öneki üye kartıdır", () => {
    expect(kodTuru("94718263")).toBe("MEMBER_CARD");
    expect(kodTuru("84718263")).toBe("UNKNOWN");
  });

  it("13 hane + 978/979 ISBN barkodudur (sağlama denetlenmez)", () => {
    expect(kodTuru("9789750812345")).toBe("ISBN");
    expect(kodTuru("979-10-90636-07-1")).toBe("ISBN");
    // Bookland öneki olmayan 13 hane tanınmaz.
    expect(kodTuru("1234567890123")).toBe("UNKNOWN");
  });

  it("yıl gibi görünmeyen 10 hane, sağlaması tutuyorsa ISBN-10 sayılır", () => {
    // 0306406152 geçerli bir ISBN-10 sağlamasıdır; ilk dört hanesi yıl değildir.
    expect(kodTuru("0306406152")).toBe("ISBN");
    // Sağlaması tutmayan 10 hane tanınmaz ("nüsha bulunamadı" demek yanıltırdı).
    expect(kodTuru("0306406150")).toBe("UNKNOWN");
  });

  it("boş ve anlamsız girdi UNKNOWN döner", () => {
    expect(kodTuru("")).toBe("UNKNOWN");
    expect(kodTuru("abc")).toBe("UNKNOWN");
  });

  it("sağlama harfi X ile biten ISBN-10 backend gibi UNKNOWN döner", () => {
    // `barcode.normalize_scan` X'i atar, kod 9 haneye iner ve hiçbir şemaya
    // uymaz. Ön yüz aynı kararı vermelidir; yoksa aynı numara iki katmanda
    // farklı ileti alır.
    expect(kodTuru("123456789X")).toBe("UNKNOWN");
  });
});

describe("normalleştirme", () => {
  it("tarama girdisinden yalnız rakamlar kalır", () => {
    expect(taramaNormalize("2026-000123")).toBe("2026000123");
    expect(taramaNormalize("ISBN 978 975 08 1234 5")).toBe("9789750812345");
  });

  it("ISBN'de sağlama harfi X korunur, küçük x büyütülür", () => {
    expect(isbnNormalize("0-8044-2957-x")).toBe("080442957X");
  });
});

describe("barkodBicimle", () => {
  it("10 haneyi basılı biçime çevirir", () => {
    expect(barkodBicimle("2026000123")).toBe("2026-000123");
  });

  it("10 hane olmayan değer olduğu gibi kalır", () => {
    expect(barkodBicimle("123")).toBe("123");
  });
});
