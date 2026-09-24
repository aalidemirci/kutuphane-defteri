"""Ağ Kataloğu ayarı serializer'ı (F5, tasarım §5.2, §6.2).

Alan listesi masaüstü ve ayar ekranının sözleşmesidir; iş kuralları servistedir
(`services.katalog_ayari`). `kutuphane_saatleri` modelde değil `SchoolConfig`'te
durur (§6.1) ama ayar ekranının aynı bölümünde düzenlendiği için burada okunur
ve yazılır.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane.models import KatalogAyari
from apps.kutuphane.services import katalog_ayari as katalog_ayari_service

KATALOG_AYARI_ALANLARI: tuple[str, ...] = (
    "acik",
    "port",
    "dinleme_kipi",
    "secili_ip",
    "son_afis_ip",
    "uyku_engelleme",
    "vitrin_acik",
    "konular_acik",
    "tahta_cidrleri",
    "kutuphane_saatleri",
)


class KatalogAyariSerializer(serializers.ModelSerializer[KatalogAyari]):
    """GET: bütün alanlar · PUT: kısmi (gönderilmeyen alana dokunulmaz)."""

    # IP alanları servis tarafında doğrulanır (Türkçe ileti, geri döngü/bağlantı
    # yerel denetimi); burada yalnız dize.
    secili_ip = serializers.CharField(max_length=15, allow_blank=True, required=False)
    son_afis_ip = serializers.CharField(max_length=15, allow_blank=True, required=False)
    tahta_cidrleri = serializers.ListField(
        child=serializers.CharField(max_length=18, allow_blank=False), required=False
    )
    # Modelde değil: yazmada servis `SchoolConfig`'e yazar, okumada aşağıda eklenir.
    kutuphane_saatleri = serializers.CharField(
        max_length=katalog_ayari_service.EN_COK_SAATLER,
        allow_blank=True,
        required=False,
        trim_whitespace=True,
        write_only=True,
    )

    class Meta:
        model = KatalogAyari
        fields = KATALOG_AYARI_ALANLARI

    def to_representation(self, instance: KatalogAyari) -> dict[str, Any]:
        veri: dict[str, Any] = super().to_representation(instance)
        veri["kutuphane_saatleri"] = katalog_ayari_service.kutuphane_saatleri()
        return veri
