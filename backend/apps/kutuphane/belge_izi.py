"""Resmî belgenin kişisiz izi ve anonimleştirilmiş kopyanın ibaresi (§6.2 `BelgeIzi`, KM-12; F11).

"Arşiv yükümlülüğü ize, KVKK yükümlülüğü içeriğe" (KM-12): kişiyi adıyla anan ve
ıslak imzayla okul arşivine giren belgeler (E5, E6, E15 — `models.BelgeTuru`) her
üretildiğinde kişisiz bir iz bırakır: tür, tarih, sayı (belge no ya da dosya
numarası), satır sayısı ve PDF'in SHA-256 özeti. Saklama süresi dolup kişi bağı
koparılınca (`services.saklama`) belge yeniden üretilebilir ama artık kişiyi anmaz;
o zaman başında **"Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul
arşivindedir"** ibaresi basılır (tasarım §6.2 — tam metin; kod kapısı) ve iz
`anonim_kopya` işaretiyle yazılır.

Belge üreticileri (`teslim_belgeleri`, `ilisik_belgeleri`) veritabanına YAZMAZ; iz
görünüm katmanında, PDF yanıtı dönmeden hemen önce `iz_birak` ile yazılır (en az
dokunuş). İz yazılamazsa belge yine verilir: iz arşivin yardımcısıdır, belgenin
ön koşulu değildir (hata günlüğe düşer, kişi bilgisi yazılmaz).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from datetime import date
from typing import Final

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.kutuphane.models import BelgeIzi, BelgeTuru

logger = logging.getLogger("kutuphane_defteri.kutuphane")

#: Anonimleştirmeden sonra yeniden üretilen belgenin ibaresi — tasarım §6.2 `BelgeIzi`
#: satırıyla BİREBİR (kod kapısı; `tests/test_saklama.py` sınar).
ANONIM_KOPYA_IBARESI: Final = "Anonimleştirilmiş kopya — ıslak imzalı asıl nüsha okul arşivindedir"

#: Anonimleştirilmiş kaydın kişi alanında basılan değer (ad yerine).
ANONIM_KISI: Final = "Anonimleştirildi"


def ibare(anonim: bool) -> str:
    """Belge bağlamının `anonim_kopya_ibaresi` değeri: anonimse ibare, değilse boş."""
    return ANONIM_KOPYA_IBARESI if anonim else ""


def herhangi_anonim(damgalar: Iterable[object]) -> bool:
    """Satırlardan biri anonimleştirilmiş mi? (`anonymized_at` değerleri verilir)"""
    return any(d is not None for d in damgalar)


def iz_birak(
    tur: str,
    pdf: bytes,
    *,
    belge_tarihi: date | None = None,
    belge_sayisi: str = "",
    kapsam: str = "",
    adet: int = 0,
    anonim_kopya: bool = False,
) -> BelgeIzi | None:
    """Belgenin kişisiz izini yazar; yazılamazsa `None` (belge yine verilir).

    `belge_sayisi` ve `kapsam` KİŞİSİZ olmalıdır (belge no, dosya numarası, barkod,
    şube etiketi); kişi adı ya da kimliği verilmez — çağıranın yükümlülüğü, testle
    sınanır. İz kendi işlem bloğundadır: çağıranın işlemi geri sarılsa da belge
    verildiyse iz kalmalıdır, ama burada çağıranın işlemi yoktur (PDF uçları okur).
    """
    if tur not in BelgeTuru.values:
        raise ValueError(f"Bilinmeyen belge türü: {tur}")
    try:
        with transaction.atomic():
            return BelgeIzi.objects.create(
                tur=tur,
                belge_tarihi=belge_tarihi or timezone.localdate(),
                belge_sayisi=belge_sayisi[:255],
                kapsam=kapsam[:255],
                adet=max(0, int(adet)),
                sha256=hashlib.sha256(pdf).hexdigest(),
                anonim_kopya=anonim_kopya,
            )
    except DatabaseError:
        logger.exception("Belge izi yazılamadı (%s).", tur)
        return None
