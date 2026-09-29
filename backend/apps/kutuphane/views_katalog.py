"""Ağ Kataloğu ayarı ucu (F5, tasarım §5.2) — `GET/PUT library/network-catalog/settings/`.

**Yalnız yönetici kipinde yazılır.** Uç görevli kipi izin listesinde DEĞİLDİR
(CLAUDE.md §2-4): görevli kipinde her yöntemi ara katmanda 403 `kip_yetkisiz`
alır, kilitliyken 423. Servis de savunma derinliği olarak kipi denetler
(`AyarYetkisiz` → 403 `kip_yetkisiz`); kurulum sürerken (parola henüz yok)
ayar yazılmaz.

PUT KISMİDİR (`library/policy/` ile aynı davranış): gövdede gönderilmeyen
alana dokunulmaz. Satır hiç yoksa GET kaydedilmemiş varsayılanları döndürür
(okuma yazmaz). Ayarın katalog dinleyicisine uygulanması masaüstü kolunun
işidir (`services.katalog_ayari.ayar_degisince`).

Windows'ta port bu uçtan değişmez (400, alan `port`): değişiklik güvenlik
duvarı kuralını ve HKLM değerini de yazan UAC adımından geçer
(`views_ag_doktoru.NetworkCatalogPortView`, §5.2).

Pardus'un taşınabilir arşivinde (KB-2, 28.09.2026 kullanıcı kararı) Ağ Kataloğu
sunulmaz: masaüstü denetçisi `sunulur: false` diyorsa bu uç kapalı ayarı
açığa ÇEVİRMEZ (400, alan `acik`). Denetçi zaten katalogu kaldırmaz; kapı,
ayarın ekranda "açık" görünüp katalogun açılmadığı yanıltıcı hâli önler.
Ayarı kapatmak her zaman serbesttir.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane.serializers_katalog import KatalogAyariSerializer
from apps.kutuphane.services import ag_doktoru
from apps.kutuphane.services import katalog_ayari as katalog_ayari_service
from apps.okul import masaustu_kanca

KIP_YETKISIZ_KODU = "kip_yetkisiz"

PORT_UAC_ILETISI = (
    "Port Ağ Doktoru'ndaki “Portu değiştir” adımıyla değiştirilir: güvenlik duvarı "
    "kuralı da yeni portla güncellenmelidir."
)

TASINABILIR_ILETISI = (
    "Ağ Kataloğu taşınabilir sürümde sunulmaz, yalnız .deb paketiyle kurulan programda açılır."
)


def _tasinabilir_kapisi(veri: Any) -> None:
    """KB-2: taşınabilir arşivde kapalı ayar bu uçtan açığa çevrilmez (modül belgesi).

    Karar masaüstü denetçisinindir (T16, tek kaynak); denetçi yoksa (geliştirme
    sunucusu, testler) kapı yoktur. Aynı değer gönderilirse ret yoktur.
    """
    if not veri.get("acik"):
        return
    denetci = masaustu_kanca.katalog_kontrolu()
    if denetci is None or denetci.durum().get("sunulur", True) is not False:
        return
    if not katalog_ayari_service.katalog_ayari().acik:
        raise ValidationError({"acik": TASINABILIR_ILETISI})


def _port_windows_kapisi(veri: Any) -> None:
    """Windows'ta port bu uçtan DEĞİŞMEZ (F5-D, tasarım §5.2, §5.7).

    Port değişince güvenlik duvarı kuralı ve kurucunun okuduğu HKLM değeri de
    değişmelidir; bunu yalnız UAC yardımcısı yapar (`library/network-catalog/
    port/`). Aynı değer gönderilirse (formun tamamı) ret yoktur.
    """
    if "port" not in veri or not ag_doktoru.windows_mu():
        return
    if int(veri["port"]) != int(katalog_ayari_service.katalog_ayari().port):
        raise ValidationError({"port": PORT_UAC_ILETISI})


class NetworkCatalogSettingsView(APIView):
    """Ağ Kataloğu ayarı (singleton) — okuma ve kısmi güncelleme."""

    def get(self, request: Request) -> Response:
        return Response(KatalogAyariSerializer(katalog_ayari_service.katalog_ayari()).data)

    def put(self, request: Request) -> Response:
        gonderi = KatalogAyariSerializer(data=request.data, partial=True)
        gonderi.is_valid(raise_exception=True)
        _port_windows_kapisi(gonderi.validated_data)
        _tasinabilir_kapisi(gonderi.validated_data)
        try:
            kayit = katalog_ayari_service.update_katalog_ayari(**dict(gonderi.validated_data))
        except katalog_ayari_service.AyarYetkisiz as exc:
            return Response(
                {"code": KIP_YETKISIZ_KODU, "message": str(exc), "fields": {}},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(KatalogAyariSerializer(kayit).data)
