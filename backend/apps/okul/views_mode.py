"""Kip uçları — görevli kipi / yönetici kipi (U5, tasarım §4.4).

* `GET  security/mode/`        → `KIP.ozet()`; kip göstergesi bunu periyodik
  sorar (ön yüz `X-KD-Etkinlik` GÖNDERMEZ). Hiçbir kipte kesilmez; kilitliyken
  de yanıt verir (`security/` öneki kilit kapısından muaftır) ve `kilitli` döner.
* `POST security/mode/staff/`  → görevli kipine geçiş (parolasız).
* `POST security/mode/admin/`  → yönetici kipine geçiş; gövde `{password}`.

Kilitle için ayrı uç yoktur: mevcut `security/lock/` kullanılır.

GEÇERSİZ GEÇİŞ NEDEN 409? Kilitliyken, kurulumda ya da güvenlik dosyası
kayıpken kip değiştirmek bir yetki sorunu değil, durum çatışmasıdır: istek
programın o anki durumunda anlamsızdır ve kilidi açmak sorunu çözer. 403 bu
programda iki şeye ayrılmıştır (oturum belirteci ve `kip_yetkisiz`); ön yüz
`kip_yetkisiz`'i "kip değişti, göstergeyi yenile" diye okur. 409 +
`kip_gecisi_gecersiz` bu anlamların hiçbirine karışmaz. Görevli kipinde
`security/mode/staff/` zaten ara katmanda 403 `kip_yetkisiz` alır (izin
listesinde yoktur); servis katmanı yine de görevliyken fikirdeştir (tepsi).

Yanlış parola: 400 `validation_error`, ileti "Parola hatalı." (güvenlik
uçlarıyla aynı biçim; servis kademeli gecikmeyi uygular). Parola hiçbir
yanıtta, günlükte ya da hata iletisinde yankılanmaz.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.okul.kip import KIP, KipGecisHatasi
from apps.okul.services import app_password


class KipGecisiGecersiz(APIException):
    """409 — istenen kip geçişi programın mevcut durumunda yapılamaz."""

    status_code = 409
    default_code = "kip_gecisi_gecersiz"
    default_detail = "Kip şu anda değiştirilemez."


class YoneticiParolasiSerializer(serializers.Serializer[dict[str, Any]]):
    password = serializers.CharField(trim_whitespace=False)


class KipDurumView(APIView):
    """`GET /api/v1/security/mode/` — kip özeti (durum + kalan süreler)."""

    def get(self, request: Request) -> Response:
        return Response(KIP.ozet())


class GorevliKipineGecView(APIView):
    """`POST /api/v1/security/mode/staff/` — yönetici kipinden görevli kipine (parolasız)."""

    def post(self, request: Request) -> Response:
        try:
            KIP.gorevliye_gec()
        except KipGecisHatasi as exc:
            raise KipGecisiGecersiz(exc.message) from exc
        return Response(KIP.ozet())


class YoneticiKipineGecView(APIView):
    """`POST /api/v1/security/mode/admin/` — yönetici parolasıyla yönetici kipine."""

    def post(self, request: Request) -> Response:
        req = YoneticiParolasiSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            KIP.yoneticiye_gec(req.validated_data["password"])
        except KipGecisHatasi as exc:
            raise KipGecisiGecersiz(exc.message) from exc
        except app_password.AppPasswordError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(KIP.ozet())
