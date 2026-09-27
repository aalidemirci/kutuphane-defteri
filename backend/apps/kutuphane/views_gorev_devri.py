"""Görev devri uçları (tasarım §4.4 SU-25, E18; F11) — İNCE görünümler, YALNIZ yönetici kipi.

| Uç | Ad | İş |
|---|---|---|
| `GET library/handover/` | `library-handover` | Devrin damgaları, açık işlerin kişisiz sayıları, devirden önceki yedek ve arşiv sayıları |
| `POST library/handover/start/` | `library-handover-start` | `{current_password, new_password}` — parola ve kurtarma anahtarı TEK yazımda yenilenir; yeni anahtar yanıtla BİR KEZ döner |
| `POST library/handover/note/` | `library-handover-note` | `{outgoing_name, incoming_name, note}` — Görev devri notu PDF'i (E18); adlar saklanmaz |

Yeni anahtarın saklandığı mevcut uçla doğrulanır (`security/recovery-key/confirm/`,
F1). Uçlar görevli kipi izin listesinde DEĞİLDİR (varsayılan kapalı; ara katman ve
`YoneticiKipiGorunumu` keser) ve `library/` önekinde oldukları için kilitliyken
423 alır (kilit açmanın yolu değildirler). Sırlar ve adlar yalnız gövdede gelir;
yanıtlar `Cache-Control: no-store` taşır; `sensitive_variables` hata raporlarını
gizler; hiçbir şey günlüğe yazılmaz.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from django.http import FileResponse
from django.views.decorators.debug import sensitive_variables
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane import gorev_devri
from apps.kutuphane.views_ilisik import PDF_CONTENT_TYPE, YoneticiKipiGorunumu
from apps.okul.services import app_password


class GorevDevriEksikYaniti(APIException):
    """Devir başlatılmadı ya da yeni anahtar doğrulanmadı — 409 `gorev_devri_eksik`."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "gorev_devri_eksik"
    default_detail = gorev_devri.EKSIK_MESAJI


class DevirBaslatSerializer(serializers.Serializer[dict[str, Any]]):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class DevirNotuSerializer(serializers.Serializer[dict[str, Any]]):
    outgoing_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=gorev_devri.AD_EN_COK
    )
    incoming_name = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=gorev_devri.AD_EN_COK
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=gorev_devri.NOT_EN_COK,
        trim_whitespace=False,
    )


class GorevDevriDurumView(YoneticiKipiGorunumu):
    """`GET library/handover/` — kartın özeti (kişisel veri yok)."""

    def get(self, request: Request) -> Response:
        return Response(gorev_devri.durum())


class GorevDevriBaslatView(YoneticiKipiGorunumu):
    """`POST library/handover/start/` — parola + kurtarma anahtarı birlikte yenilenir.

    Yanlış mevcut parola 400 "Parola hatalı." + kademeli gecikme; yeni parola
    eskisiyle aynıysa 400. Yanıttaki `recovery_key` tek seferliktir.
    """

    @sensitive_variables("req", "anahtar")
    def post(self, request: Request) -> Response:
        req = DevirBaslatSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            anahtar = app_password.start_handover(
                current_password=req.validated_data["current_password"],
                new_password=req.validated_data["new_password"],
            )
        except app_password.AppPasswordError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        yanit = Response(
            {
                "recovery_key": anahtar,
                **app_password.status(),
                "handover": gorev_devri.durum(),
            }
        )
        yanit["Cache-Control"] = "no-store"
        return yanit


class GorevDevriNotuView(YoneticiKipiGorunumu):
    """`POST library/handover/note/` — E18 PDF'i (adlar yalnız bu yanıttadır)."""

    @sensitive_variables("req", "icerik")
    def post(self, request: Request) -> FileResponse:
        req = DevirNotuSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        try:
            icerik = gorev_devri.not_pdf(
                devreden=req.validated_data["outgoing_name"],
                devralan=req.validated_data["incoming_name"],
                ek_not=req.validated_data["note"],
            )
        except gorev_devri.GorevDevriEksik as exc:
            raise GorevDevriEksikYaniti() from exc
        yanit = FileResponse(
            BytesIO(icerik),
            as_attachment=True,
            filename=gorev_devri.not_dosya_adi(),
            content_type=PDF_CONTENT_TYPE,
        )
        yanit["Cache-Control"] = "no-store"
        return yanit
