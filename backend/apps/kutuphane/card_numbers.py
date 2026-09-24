"""Üye kartı numarası — biçim, sağlama hanesi ve kör indeks girdisi (tasarım §7.1, D21).

Şema (§7.1, docs/sozluk.md "kart no"):

| | Biçim | Örnek |
|---|---|---|
| Üye kartı | 8 hane: `9` + 6 **rastgele** hane + 1 mod-10 sağlama | `94718263` |

**Neden rastgele?** OYS kart numarasını yıl bazlı SIRALI bir sayaçtan
(`CardCounter`) veriyordu (D21): bir kartı gören, komşu numaraları tahmin edip
masada başkasının adını ve kalan hakkını okutabilirdi. Rastgele gövde, masadaki
"art arda geçersiz kart okutması → yönetici parolası" kuralıyla (GA-7) birlikte
numaralandırmayla ad çıkarmayı pahalılaştırır. `CardCounter` bu yüzden YOKTUR.

**Sağlama hanesi** Luhn (mod-10) algoritmasıdır: tek hane yazım hatalarının ve
bitişik iki hanenin yer değiştirmesinin hemen hepsini yakalar. Masa ekranı bu
sayede elle yazılmış hatalı numarayı "tanınmayan kart" yerine "kart numarası
hatalı" diye ayırabilir; yanlış numara başka bir üyeye denk gelmez.

**Numara asla yeniden kullanılmaz.** Bu modül SAF'tır (veritabanına bakmaz);
teklik ve "hiç verilmemiş olma" denetimi `services.memberships`'tedir ve
`IssuedCard` tablosuna karşı yapılır: verilmiş BÜTÜN numaraların kişisiz kör
indeksi orada kalıcı olarak durur, üyelik katı silinse de silinmez.

**Kör indeks girdisi** (T14): `card_index_input` numarayı rakamlarına indirir ve
başına alan ayracı (`kart-no:`) koyar. Ayraç, okul no kör indeksiyle (aynı HMAC
anahtarı) aynı rakam dizisinin aynı indeksi üretmesini önler: iki sütun
yan yana konsa bile "bu öğrencinin okul no'su şu kartın numarasıdır" çıkarımı
yapılamaz. Ayraç değişirse bütün kart indeksleri yeniden hesaplanmalıdır —
sabittir.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable

from apps.kutuphane import barcode as barcode_module

#: Kart no uzunluğu ve ön eki — ayrımın tek kaynağı `barcode` modülündedir.
CARD_LENGTH = barcode_module.MEMBER_CARD_LENGTH
CARD_PREFIX = barcode_module.MEMBER_CARD_PREFIX
#: Rastgele gövdenin hane sayısı (8 = 1 ön ek + 6 gövde + 1 sağlama).
BODY_DIGITS = CARD_LENGTH - len(CARD_PREFIX) - 1
#: Kör indeks girdisinin alan ayracı (modül yorumu).
INDEX_DOMAIN = "kart-no:"

#: Rastgele gövde üreticisi — testler çakışma senaryosu için değiştirir.
#: `secrets` kullanılır: numara tahmin edilemez olmalıdır (D21).
BodySource = Callable[[], str]


def random_body() -> str:
    """6 haneli rastgele gövde ('000000'…'999999')."""
    return f"{secrets.randbelow(10**BODY_DIGITS):0{BODY_DIGITS}d}"


def luhn_check_digit(digits: str) -> str:
    """Luhn (mod-10) sağlama hanesi: `digits` + dönen hane Luhn'dan geçer."""
    if not digits.isascii() or not digits.isdigit():
        raise ValueError("Sağlama hanesi yalnız rakamlardan hesaplanır.")
    toplam = 0
    # Sağlama hanesi eklenince en sağdaki hane çift konuma düşer: sağdan
    # başlayarak birinci, üçüncü… haneler ikiye katlanır.
    for sira, ch in enumerate(reversed(digits)):
        hane = int(ch)
        if sira % 2 == 0:
            hane *= 2
            if hane > 9:
                hane -= 9
        toplam += hane
    return str((10 - toplam % 10) % 10)


def build_card_no(body: str) -> str:
    """Gövdeden tam kart no: `9` + gövde + sağlama hanesi."""
    if len(body) != BODY_DIGITS or not body.isascii() or not body.isdigit():
        raise ValueError(f"Kart numarası gövdesi {BODY_DIGITS} rakam olmalıdır.")
    partial = CARD_PREFIX + body
    return partial + luhn_check_digit(partial)


def normalize_card_no(value: object) -> str:
    """Okuyucu ya da klavye girdisini rakamlarına indirir (nüsha barkoduyla aynı kural)."""
    return barcode_module.normalize_scan(value)


def has_card_shape(value: object) -> bool:
    """Biçimce kart no mu? (8 hane, `9` ile başlar) — sağlama denetlenmez."""
    digits = normalize_card_no(value)
    return len(digits) == CARD_LENGTH and digits.startswith(CARD_PREFIX)


def is_valid_card_no(value: object) -> bool:
    """Biçim + Luhn sağlaması doğru mu? Yanlışsa numara hiç verilmemiştir."""
    digits = normalize_card_no(value)
    if len(digits) != CARD_LENGTH or not digits.startswith(CARD_PREFIX):
        return False
    return luhn_check_digit(digits[:-1]) == digits[-1]


def card_index_input(value: object) -> str:
    """Kör indekse verilecek normalleştirilmiş girdi; rakamsız girdide ''."""
    digits = normalize_card_no(value)
    return f"{INDEX_DOMAIN}{digits}" if digits else ""
