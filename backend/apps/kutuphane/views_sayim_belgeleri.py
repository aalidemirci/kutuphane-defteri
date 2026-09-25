"""Sayım belgesinin uçları (E10 — F9) — İNCE görünümler.

| Uç | Ad | İş |
|---|---|---|
| `GET library/stocktakes/<pk>/documents/` | `library-stocktake-documents` | Sayımın belgeleri ve basılabilirlikleri (ekran düğmeleri) |
| `GET library/stocktakes/<pk>/documents/<belge>/?kind=pdf\\|xlsx` | `library-stocktake-document` | Sayım tutanağı (PDF + XLSX; ekinde TMY 34/1 büyüklükleri) |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (sayım yönetici işidir; varsayılan kapalı —
CLAUDE.md §2-4). Ara katman keser; görünüm bir kez daha keser (`YoneticiKipiGorunumu`).
Kayıt YAZMAZ, bu yüzden `RequiresAdminPassword` taşımaz
(`apps/okul/tests/test_kisi_yazan_uclar.py`). Yanıtlar `Cache-Control: no-store` taşır;
indirme adında kişi adı YOKTUR. Rapor biçimi `?kind=pdf|xlsx` alır (`?format=` DRF içerik
müzakeresine ayrılmıştır — CLAUDE.md §3). Basılamayan belge 400 + gerekçe
(`sayim_belgeleri.stocktake_document_blocker`), tanınmayan belge 404.
"""

from __future__ import annotations

from django.http import FileResponse, Http404
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane import sayim_belgeleri as belgeler
from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import StockTake
from apps.kutuphane.views import _choice_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.kutuphane.views_komisyon_belgeleri import _dosya


def _sayim(pk: int) -> StockTake:
    sayim = selectors_sayim.get_stocktake(pk)
    if sayim is None:
        raise Http404
    return sayim


class StockTakeDocumentsView(YoneticiKipiGorunumu):
    """`GET library/stocktakes/<pk>/documents/` — `[{kind, title, formats, available, reason}]`."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(belgeler.stocktake_documents(_sayim(pk)))


class StockTakeDocumentView(YoneticiKipiGorunumu):
    """`GET library/stocktakes/<pk>/documents/<belge>/?kind=pdf|xlsx` — sayım tutanağı."""

    def get(self, request: Request, pk: int, belge: str) -> FileResponse:
        if belge not in {b.slug for b in belgeler.SAYIM_BELGELERI}:
            raise Http404
        bicim = (
            _choice_param(request.query_params, "kind", (belgeler.PDF, belgeler.XLSX), "biçim")
            or belgeler.PDF
        )
        icerik = belgeler.stocktake_document(_sayim(pk), belge, bicim)
        return _dosya(icerik, belgeler.stocktake_document_filename(belge, bicim), bicim=bicim)
