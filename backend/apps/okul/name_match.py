"""Ad-soyad eşleştirme yardımcıları — e-Okul aktarımı ve ayrılış havuzu ortak kullanır.

Ad-soyad ŞİFRELİDİR (U3): eşleştirme DB'de değil, çözülmüş değerlerle Python'da
yapılır. Anahtar `excel_ogrenci.normalize_header`'dır (Türkçe harfleri ASCII'ye
katlar, küçük harf, tek boşluk) — aynı katlama iki tarafa da uygulanır.

"Olası aynı kişi" (tasarım §8.3, EK-20): ad aynı soyad farklı (soyadı değişimi)
YA DA normalize ad-soyad düzenleme uzaklığı ≤ 2 (küçük yazım farkı). Aktarım
önizlemesi yeni satır ↔ listede olmayan kayıt için, ayrılış havuzu havuzdaki
kişi ↔ sonradan açılan kayıt için aynı kuralı koşar (tek kaynak burası).
"""

from __future__ import annotations

from apps.okul.excel_ogrenci import normalize_header

#: "Olası aynı kişi" için normalize ad-soyad düzenleme uzaklığı üst sınırı.
SIMILAR_NAME_MAX_DISTANCE = 2


def name_key(value: str) -> str:
    """Ad-soyad eşleştirme anahtarı (ASCII'ye katlanmış, küçük harf, tek boşluk)."""
    return normalize_header(value)


def edit_distance(a: str, b: str, *, limit: int) -> int:
    """Levenshtein uzaklığı; `limit`'i aşınca erken döner (limit + 1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        simdiki = [i]
        for j, cb in enumerate(b, start=1):
            simdiki.append(min(onceki[j] + 1, simdiki[j - 1] + 1, onceki[j - 1] + (ca != cb)))
        if min(simdiki) > limit:
            return limit + 1
        onceki = simdiki
    return onceki[-1]


def probably_same_person(*, first_a: str, full_a: str, first_b: str, full_b: str) -> bool:
    """ "Olası aynı kişi": ad aynı (soyad farklı olabilir) YA DA ad-soyad uzaklığı ≤ 2."""
    ad_a = name_key(first_a)
    if ad_a and ad_a == name_key(first_b):
        return True
    return (
        edit_distance(name_key(full_a), name_key(full_b), limit=SIMILAR_NAME_MAX_DISTANCE)
        <= SIMILAR_NAME_MAX_DISTANCE
    )
