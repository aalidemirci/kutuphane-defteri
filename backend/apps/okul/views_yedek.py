"""Dış yedek hatırlatması uçları (F11 bakım kolu; tasarım §16 risk 13).

| Uç | Ad | İş |
|---|---|---|
| `GET backups/external/` | `backup-external-reminder` | Son şifreli yedek indirmenin tarihi, hatırlatma süresi ve Genel Bakış kartının gösterilip gösterilmeyeceği (kişisel veri yok) |
| `PUT backups/external/` | `backup-external-reminder` | `{reminder_days}` — hatırlatma süresi (7-90 gün) |

Tarih indirmeyle kendiliğinden yazılır (`encrypted_backup.create_encrypted_backup`);
burada elle "indirdim" işareti YOKTUR — kart yalnız programın gördüğü olayı söyler.
Uç görevli kipi izin listesinde DEĞİLDİR (varsayılan kapalı, CLAUDE.md §2-4) ve
kilitliyken kilit kapısı keser (`backups/external/` kilit muafiyeti taşımaz).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.okul.services import dis_yedek


class DisYedekAyariSerializer(serializers.Serializer[dict[str, Any]]):
    reminder_days = serializers.IntegerField(
        min_value=dis_yedek.EN_AZ_HATIRLATMA_GUN,
        max_value=dis_yedek.EN_COK_HATIRLATMA_GUN,
        error_messages={
            "min_value": dis_yedek.SURE_ARALIK_MESAJI,
            "max_value": dis_yedek.SURE_ARALIK_MESAJI,
            "invalid": dis_yedek.SURE_ARALIK_MESAJI,
            "required": dis_yedek.SURE_ARALIK_MESAJI,
            "null": dis_yedek.SURE_ARALIK_MESAJI,
        },
    )


class DisYedekView(APIView):
    """`GET`/`PUT backups/external/` — dış yedek hatırlatmasının durumu ve süresi."""

    def get(self, request: Request) -> Response:
        return Response(dis_yedek.durum().as_dict())

    def put(self, request: Request) -> Response:
        req = DisYedekAyariSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            sonuc = dis_yedek.hatirlatma_suresini_ayarla(req.validated_data["reminder_days"])
        except ValueError as exc:  # pragma: no cover — serializer aynı aralığı denetler
            raise serializers.ValidationError({"reminder_days": [str(exc)]}) from exc
        return Response(sonuc.as_dict())
