"""Kapalı günler uçları — liste/ekle, sil, resmî ve dini tatilleri tohumla (F1-D).

DD'nin Holiday görünümlerinden UYARLANDI (tasarım §12); `views.py`'den ayrı dosyada
durur (F1 dosya sahipliği). İnce görünümler: okuma `selectors`, yazma
`services.calendar`. Hata gövdesi `{code, message, fields}` sözleşmesindedir;
servisin Django `ValidationError`'ı `kd_exception_handler`'da 400'e çevrilir.

Kişisel veri taşımaz → parola kapısı (409) gerekmez. Görevli kipi izin listesinde
YOKTUR: kapalı gün yönetimi yönetici işidir (varsayılan kapalı, tasarım §4.4).
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.okul import selectors
from apps.okul.serializers import (
    HolidayListQuerySerializer,
    HolidaySeedRequestSerializer,
    HolidaySerializer,
)
from apps.okul.services import calendar as calendar_service


class HolidayListCreateView(APIView):
    """`GET holidays/?year=` (takvim yılıyla kesişenler) · `POST holidays/` (elle ekle)."""

    def get(self, request: Request) -> Response:
        query = HolidayListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = selectors.holidays_sorted(year=query.validated_data.get("year"))
        return Response(HolidaySerializer(rows, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = HolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        holiday = calendar_service.create_holiday(
            name=data["name"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            kind=data["kind"],
        )
        return Response(HolidaySerializer(holiday).data, status=status.HTTP_201_CREATED)


class HolidayDetailView(APIView):
    """`DELETE holidays/<pk>/` — yumuşak silme."""

    def delete(self, request: Request, pk: int) -> Response:
        holiday = selectors.get_holiday(pk)
        if holiday is None:
            raise NotFound("Kayıt bulunamadı.")
        calendar_service.delete_holiday(holiday)
        return Response(status=status.HTTP_204_NO_CONTENT)


class HolidaySeedView(APIView):
    """`POST holidays/seed/` `{year?}` — yılın sabit resmî tatilleri + dini bayramlar (fikirdeş)."""

    def post(self, request: Request) -> Response:
        serializer = HolidaySeedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data.get("year") or timezone.localdate().year
        result = calendar_service.seed_holidays(year)
        return Response(
            {
                "year": result.year,
                "created": result.created,
                "skipped": result.skipped,
                "religious_available": result.religious_available,
            }
        )
