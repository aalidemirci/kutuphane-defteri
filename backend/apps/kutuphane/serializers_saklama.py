"""Saklama ve anonimleştirme uçlarının serializer'ları (F11 — tasarım §6.4).

Alan listeleri anlık görüntüyle sınanır (`tests/test_saklama_uclari.py`). Yalnız
`SilinecekKisiSerializer` kişi adı taşır ve yalnız yönetici kipindeki uçta kullanılır.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class SaklamaTetikSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/retention/apply/` gövdesi: yönetici parolası + onaylanan önizleme."""

    password = serializers.CharField(trim_whitespace=False, max_length=512)
    digest = serializers.RegexField(r"^[0-9a-f]{64}$", max_length=64)


class SilinecekKisiSerializer(serializers.Serializer[Any]):
    """Kaydı ya da sona ermiş üyelik kaydı silinecek kişi (ad İÇERİR — yönetici kipi).

    `scope`: "person" (kişi kaydı üyelikleriyle silinir) · "membership" (yalnız sona ermiş
    üyelik kaydı silinir, kişi kaydı kalır; `terminated_at` üyeliğin sonlandığı gün).
    """

    kind = serializers.CharField()
    person_id = serializers.IntegerField()
    full_name = serializers.CharField()
    person_label = serializers.CharField(source="label")
    left_at = serializers.DateField(allow_null=True)
    scope = serializers.CharField()
    terminated_at = serializers.DateField(allow_null=True)


class BedelHatirlatmasiSerializer(serializers.Serializer[Any]):
    """Bedel adımında bir yıldan uzun bekleyen dosya (kişisiz)."""

    case_id = serializers.IntegerField()
    barcode = serializers.CharField()
    title = serializers.CharField()
    case_type = serializers.CharField()
    resolution = serializers.CharField()
    step_date = serializers.DateField()
    years_waiting = serializers.IntegerField()
