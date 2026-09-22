"""Ad-soyad eşleştirme yardımcıları — e-Okul aktarımı ve ayrılış havuzu ortak kullanır.

Ad-soyad ŞİFRELİDİR (U3): eşleştirme DB'de değil, çözülmüş değerlerle Python'da
yapılır. Anahtar `excel_ogrenci.normalize_header`'dır (Türkçe harfleri ASCII'ye
katlar, küçük harf, tek boşluk) — aynı katlama iki tarafa da uygulanır.

"Olası aynı kişi" (tasarım §8.3, EK-20): ad aynı soyad farklı (soyadı değişimi)
YA DA normalize ad-soyad düzenleme uzaklığı ≤ 2 (küçük yazım farkı). Aktarım
önizlemesi yeni satır ↔ listede olmayan kayıt için, ayrılış havuzu havuzdaki
kişi ↔ sonradan açılan kayıt için aynı kuralı koşar (tek kaynak burası).

Kural DEĞİL, GEREKÇE eklendi (TB18): aday satırı neden aday olduğunu söylesin.
"Adı aynı" adaşı da yakalar; kullanıcı bunu ancak gerekçeyi görürse anlar. Kural
gevşetilmedi — soyadı değişiminde soyadlar tamamen farklıdır, soyad yakınlığı
aramak kuralı işlevsiz bırakırdı.
"""

from __future__ import annotations

from enum import StrEnum

from apps.okul.excel_ogrenci import normalize_header

#: "Olası aynı kişi" için normalize ad-soyad düzenleme uzaklığı üst sınırı.
SIMILAR_NAME_MAX_DISTANCE = 2


class MatchReason(StrEnum):
    """Bir çiftin neden "olası aynı kişi" sayıldığı (aday satırında gösterilir)."""

    #: Normalize ad-soyad birebir aynı (aynı adı taşıyan iki kayıt).
    SAME_FULL_NAME = "ayni_ad_soyad"
    #: Ad aynı, soyad farklı — kuralın asıl işi (soyadı değişimi), adaş da buraya düşer.
    SAME_FIRST_NAME = "ad_ayni_soyad_farkli"
    #: Ad-soyad düzenleme uzaklığı ≤ 2 (yazım/harf farkı).
    SPELLING = "yazim_farki"


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


def match_reason(*, first_a: str, full_a: str, first_b: str, full_b: str) -> MatchReason | None:
    """Çift neden "olası aynı kişi"? Aday değilse None.

    Sıra kuralı DEĞİŞTİRMEZ, yalnız gerekçeyi ayrıştırır: birebir aynı ad-soyad
    "adı aynı, soyadı farklı" diye sunulmasın.
    """
    tam_a, tam_b = name_key(full_a), name_key(full_b)
    if tam_a and tam_a == tam_b:
        return MatchReason.SAME_FULL_NAME
    ad_a = name_key(first_a)
    if ad_a and ad_a == name_key(first_b):
        return MatchReason.SAME_FIRST_NAME
    if edit_distance(tam_a, tam_b, limit=SIMILAR_NAME_MAX_DISTANCE) <= SIMILAR_NAME_MAX_DISTANCE:
        return MatchReason.SPELLING
    return None


def probably_same_person(*, first_a: str, full_a: str, first_b: str, full_b: str) -> bool:
    """ "Olası aynı kişi": ad aynı (soyad farklı olabilir) YA DA ad-soyad uzaklığı ≤ 2."""
    return match_reason(first_a=first_a, full_a=full_a, first_b=first_b, full_b=full_b) is not None
