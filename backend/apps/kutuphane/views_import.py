"""Toplu katalog aktarımı uçları — önizleme, uygulama, geçmiş, köprü komutu (F3).

Görünümler İNCEDİR: dosyayı satırlara çevirmek, planı çıkarmak, kovaları
hesaplamak ve yazmak `services.import_service`'tedir (tasarım §8.1). Burada
yalnız gövde çözülür ve rapor serileştirilir.

`apps/okul/views.py`'deki içe aktarma uçlarının deseni korundu: aynı gövde
biçimi, `ParserError` → 400. Fark, kütüphane tarafında önizlemenin bir ADIM
olmasıdır: kullanıcı önizlemede şüpheli satırların kararını ve eşleşmeyen bölüm
değerlerinin karşılığını verir, uygulama isteği aynı gövdeyi o kararlarla yeniden
gönderir (dosya dahil — program yüklenen dosyayı saklamaz, yalnız içerik özetini
tutar).

**Kapılar burada tekrarlanmaz** (`views.py` ile aynı): kilitliyken 423, görevli
kipinde 403 `kip_yetkisiz`, şifreli alana parolasız yazmada 409 `parola_gerekli`.
Bu uçların hiçbiri görevli kipi izin listesinde DEĞİLDİR: toplu katalog aktarımı
masa işi değildir (CLAUDE.md §2-4).

**Dış istek yoktur.** Aktarım hattı hiçbir adımında ağa çıkmaz (§8.5 kural 2);
yapay zekâ köprüsü de yalnız METİN üretir — komut panoya kopyalanır, kullanıcı
onu kendisi taşır.
"""

from __future__ import annotations

from typing import Any

from rest_framework import generics, serializers, status
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import ai_bridge, selectors
from apps.kutuphane.models import CatalogImportRun, CatalogImportSource
from apps.kutuphane.pagination import ListeSayfalama
from apps.kutuphane.serializers import (
    CatalogImportApplySerializer,
    CatalogImportPreviewSerializer,
    CatalogImportRunSerializer,
)
from apps.kutuphane.services import import_service
from apps.okul.excel_ogrenci import ParserError


def _istek_verisi(request: Request, *, uygulama: bool) -> dict[str, Any]:
    """Gövdeyi doğrular (önizleme ve uygulama aynı alanları taşır)."""
    sinif = CatalogImportApplySerializer if uygulama else CatalogImportPreviewSerializer
    gonderi = sinif(data=request.data)
    gonderi.is_valid(raise_exception=True)
    return dict(gonderi.validated_data)


def _satirlar(veri: dict[str, Any]) -> tuple[import_service.ParsedFile, str, str, str]:
    """(ayrıştırma sonucu, içerik özeti, kaynak, dosya adı) — okunamayan dosya 400."""
    kaynak = str(veri.get("source") or CatalogImportSource.EXCEL)
    yuklenen = veri.get("file")
    try:
        if yuklenen is not None:
            parsed, ozet = import_service.rows_from_file(yuklenen.read(), source=kaynak)
            return parsed, ozet, kaynak, str(yuklenen.name or "")
        payload = veri.get("payload")
        parsed = import_service.rows_from_payload(payload)
        return parsed, import_service.content_hash(parsed.rows), kaynak, ""
    except ParserError as exc:
        raise serializers.ValidationError(str(exc)) from exc


def _spec(veri: dict[str, Any]) -> import_service.AcquisitionSpec:
    """Uygulamada açılacak edinim partisi (varsayılan: mevcut koleksiyon aktarımı)."""
    return import_service.AcquisitionSpec(
        method=str(veri.get("method") or import_service.DEFAULT_METHOD),
        date=veri.get("date"),
        source_note=str(veri.get("source_note") or ""),
        unit_price=veri.get("unit_price"),
        commission_decision=veri.get("commission_decision"),
        notes=str(veri.get("notes") or ""),
    )


class CatalogImportPreviewView(APIView):
    """`POST library/import/preview/` — yazmadan önizler (uygulamanın birebir provası).

    Gerçek yazma koşulur ve geri sarılır; yanıttaki sayılar uygulamanın yazacağı
    sayılardır. Yanıt ayrıca ekranın toplaması gereken eksikleri söyler: karar
    bekleyen şüpheli satırlar, bölüm listesinde bulunmayan değerler, aynı dosyanın
    daha önce uygulanmış olması.
    """

    def post(self, request: Request) -> Response:
        veri = _istek_verisi(request, uygulama=False)
        parsed, ozet, kaynak, dosya_adi = _satirlar(veri)
        rapor = import_service.preview_import(
            parsed,
            payload_sha256=ozet,
            source=kaynak,
            file_name=dosya_adi,
            decisions=veri.get("decisions"),
            section_map=veri.get("section_map"),
            new_sections=veri.get("new_sections"),
        )
        return Response(rapor.to_dict())


class CatalogImportApplyView(APIView):
    """`POST library/import/apply/` — onaylanan aktarımı uygular.

    Yazmadan önce üç kapı: şüpheli satırların kararı verilmiş olmalı, eşleşmeyen
    bölüm değerleri karşılanmış olmalı, aynı dosya daha önce uygulanmamış olmalı
    (§8.1 fikirdeşlik — uyarı değil ENGEL). Her biri sözleşmeli 400 döner.
    """

    def post(self, request: Request) -> Response:
        veri = _istek_verisi(request, uygulama=True)
        parsed, ozet, kaynak, dosya_adi = _satirlar(veri)
        rapor = import_service.apply_import(
            parsed,
            payload_sha256=ozet,
            source=kaynak,
            file_name=dosya_adi,
            decisions=veri.get("decisions"),
            section_map=veri.get("section_map"),
            new_sections=veri.get("new_sections"),
            spec=_spec(veri),
        )
        return Response(rapor.to_dict(), status=status.HTTP_201_CREATED)


class CatalogImportRunListView(generics.ListAPIView[CatalogImportRun]):
    """`GET library/import/runs/` — aktarım geçmişi (en yeniden eskiye).

    Sorgu parametreleri: `status`, `source`. Kişisel veri taşımaz.
    """

    serializer_class = CatalogImportRunSerializer
    pagination_class = ListeSayfalama

    def get_queryset(self) -> Any:
        params = self.request.query_params
        return selectors.catalog_import_runs(
            status=str(params.get("status", "")).strip(),
            source=str(params.get("source", "")).strip(),
        )


class CatalogImportRunDiscardView(APIView):
    """`POST library/import/runs/<pk>/discard/` — önizlemeden vazgeçildi.

    Yalnız önizleme koşusu iptal edilir; uygulanmış aktarım kayıtta kalır (aynı
    dosyanın ikinci kez uygulanmasını engelleyen iz odur).
    """

    def post(self, request: Request, pk: int) -> Response:
        kayit: CatalogImportRun = get_object_or_404(selectors.catalog_import_runs(), pk=pk)
        return Response(CatalogImportRunSerializer(import_service.discard_run(kayit)).data)


class CatalogAiPromptView(APIView):
    """`GET library/import/ai-prompt/` — köprünün komut metni ve uyarıları (§8.2).

    Veritabanına dokunmaz ve DIŞARIYA hiçbir istek atmaz: metin programın
    içindedir, kullanıcı onu panoya kopyalayıp kendi aracına kendisi taşır.
    Ekrandaki dört uyarı maddesi de buradan gelir (tek kaynak).
    """

    def get(self, request: Request) -> Response:
        return Response(
            {
                "schema_version": ai_bridge.SCHEMA_VERSION,
                "prompt": ai_bridge.AI_PROMPT,
                "notes": list(ai_bridge.UI_NOTES),
            }
        )
