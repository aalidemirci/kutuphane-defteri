"""Ağ Doktoru uçları (F5, tasarım §5.9) — `library/network-catalog/…`.

**Yalnız yönetici kipinde.** Hiçbiri görevli kipi izin listesinde DEĞİLDİR
(CLAUDE.md §2-4): görevli kipinde ara katman 403 `kip_yetkisiz`, kilitliyken 423
döner. Katalog denetçisine masaüstü kancası üzerinden gidilir
(`services.ag_doktoru`); kanca yoksa eylemler 503 `masaustu_yok` döner.

| Uç | Yöntem | İş |
|---|---|---|
| `status/` | GET | durum, adres ve QR, kişisiz günlük sayaçlar, son hata |
| `control/` | POST `{eylem}` | aç / kapat / yeniden başlat |
| `firewall/` | GET | beş maddelik denetimi yeniden okur |
| `firewall-rule/` | POST | "Kuralı ekle/güncelle" (UAC) |
| `interfaces/` | GET | aday IP'ler ve etkin arayüzler, uyarılar |
| `listener-test/` | POST | "dinleyici bu arayüzde ayakta" öz sınaması + komutlar |
| `port/` | POST `{port}` | port değişikliği (Windows'ta UAC ile kural + HKLM) |
| `poster/` | POST `{ip?}` | katalog afişi PDF'i; afiş adresi kaydedilir |
| `info-note/` | GET `?ip=` | Ağ Hizmeti Bilgi Notu PDF'i |
| `bookmarks/` | GET `?ip=` | yer imi dosyaları (ZIP) |
| `pys-text/` | GET `?ip=` | PYS talep metni (panoya kopyalanır) |

Öz sınama ve kural güncellemesi POST'tur: ağ bağlantısı kuran ya da UAC açan
bir işlem adres çubuğundan veya bir önyüklemeden tetiklenmemelidir.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from django.http import FileResponse
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import ag_belgeleri
from apps.kutuphane.models import KATALOG_PORT_ALT, KATALOG_PORT_UST
from apps.kutuphane.services import ag_doktoru

PDF_TURU = "application/pdf"
ZIP_TURU = "application/zip"


class _EylemSerializer(serializers.Serializer[Any]):
    eylem = serializers.ChoiceField(choices=sorted(ag_doktoru.EYLEMLER))


class _PortSerializer(serializers.Serializer[Any]):
    port = serializers.IntegerField(min_value=KATALOG_PORT_ALT, max_value=KATALOG_PORT_UST)


class _AdresSerializer(serializers.Serializer[Any]):
    ip = serializers.CharField(max_length=15, required=False, allow_blank=True, default="")


def _istenen_ip(veri: Any) -> str | None:
    gonderi = _AdresSerializer(data=veri)
    gonderi.is_valid(raise_exception=True)
    return str(gonderi.validated_data.get("ip") or "").strip() or None


def _dosya(icerik: bytes, ad: str, tur: str) -> FileResponse:
    yanit = FileResponse(BytesIO(icerik), as_attachment=True, filename=ad, content_type=tur)
    yanit["Cache-Control"] = "no-store"
    return yanit


class NetworkCatalogStatusView(APIView):
    def get(self, request: Request) -> Response:
        return Response(ag_doktoru.durum_ozeti())


class NetworkCatalogControlView(APIView):
    def post(self, request: Request) -> Response:
        gonderi = _EylemSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        return Response(ag_doktoru.eylem(str(gonderi.validated_data["eylem"])))


class NetworkCatalogFirewallView(APIView):
    def get(self, request: Request) -> Response:
        return Response(ag_doktoru.guvenlik_duvari())


class NetworkCatalogFirewallRuleView(APIView):
    def post(self, request: Request) -> Response:
        return Response(ag_doktoru.kural_guncelle())


class NetworkCatalogInterfacesView(APIView):
    def get(self, request: Request) -> Response:
        return Response(ag_doktoru.ip_adaylari())


class NetworkCatalogListenerTestView(APIView):
    def post(self, request: Request) -> Response:
        return Response(ag_doktoru.dinleyici_sinamasi())


class NetworkCatalogPortView(APIView):
    def post(self, request: Request) -> Response:
        gonderi = _PortSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        return Response(ag_doktoru.port_degistir(int(gonderi.validated_data["port"])))


class NetworkCatalogPosterView(APIView):
    """Afiş basılınca adres `son_afis_ip` olarak kaydedilir (yan etkili: POST)."""

    def post(self, request: Request) -> FileResponse:
        ip = ag_doktoru.yayin_ip(_istenen_ip(request.data))
        return _dosya(
            ag_belgeleri.afis_pdf(ip),
            ag_belgeleri.belge_dosya_adi(ag_belgeleri.AFIS_ADI, "pdf"),
            PDF_TURU,
        )


class NetworkCatalogInfoNoteView(APIView):
    """Adres bulunamazsa not yine basılır; adres satırı elle doldurulacak çizgi olur."""

    def get(self, request: Request) -> FileResponse:
        istenen = _istenen_ip(request.query_params)
        try:
            ip: str | None = ag_doktoru.yayin_ip(istenen)
        except ag_doktoru.AdresYok:
            ip = None
        return _dosya(
            ag_belgeleri.bilgi_notu_pdf(ip),
            ag_belgeleri.belge_dosya_adi(ag_belgeleri.BILGI_NOTU_ADI, "pdf"),
            PDF_TURU,
        )


class NetworkCatalogBookmarksView(APIView):
    def get(self, request: Request) -> FileResponse:
        ip = ag_doktoru.yayin_ip(_istenen_ip(request.query_params))
        return _dosya(
            ag_belgeleri.yer_imi_zip(ip),
            ag_belgeleri.belge_dosya_adi(ag_belgeleri.YER_IMI_ADI, "zip"),
            ZIP_TURU,
        )


class NetworkCatalogPysTextView(APIView):
    def get(self, request: Request) -> Response:
        istenen = _istenen_ip(request.query_params)
        try:
            ip: str | None = ag_doktoru.yayin_ip(istenen)
        except ag_doktoru.AdresYok:
            ip = None
        return Response({"metin": ag_belgeleri.pys_talep_metni(ip)})
