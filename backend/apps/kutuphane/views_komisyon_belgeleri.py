"""Komisyon ve yıl sonu raporu belgelerinin uçları (E7, E8, E9, E16 — F8) — İNCE görünümler.

| Uç | Ad | İş |
|---|---|---|
| `GET library/weeding-batches/<pk>/documents/` | `library-weeding-batch-documents` | Teklifin ayıklama belgeleri ve basılabilirlikleri (ekran düğmeleri) |
| `GET library/weeding-batches/<pk>/documents/<belge>/?kind=pdf\\|xlsx` | `library-weeding-batch-document` | Ayıklama belgesi (E7): teklif listesi, ayıklama tutanağı, kayıttan düşme teklif listesi, imha tutanağı, devir listesi (PDF + XLSX) |
| `GET library/rare-works-submissions/<pk>/pdf/` | `library-rare-works-submission-pdf` | El yazması ve nadir eserler listesi (E8) |
| `GET library/annual-reviews/<pk>/pdf/` | `library-annual-review-pdf` | Yıl sonu kütüphane raporu (E9) |
| `GET library/donation-intakes/<pk>/pdf/` | `library-donation-intake-pdf` | Bağış ön kayıt listesi (E16) |
| `GET library/donation-intakes/<pk>/result-pdf/` | `library-donation-intake-result-pdf` | Bağış değerlendirme sonucu (E16; yalnız karar uygulandıktan sonra) |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (§4.4: komisyon, ayıklama ve raporlar
yönetici işidir; varsayılan kapalı — CLAUDE.md §2-4). Ara katman keser; görünüm bir
kez daha keser (`YoneticiKipiGorunumu`). Hiçbiri kayıt YAZMAZ, bu yüzden
`RequiresAdminPassword` taşımaz (`apps/okul/tests/test_kisi_yazan_uclar.py`). Belge
yanıtları `Cache-Control: no-store` taşır; indirme adında kişi adı YOKTUR. Rapor biçimi
`?kind=pdf|xlsx` alır (`?format=` DRF içerik müzakeresine ayrılmıştır — CLAUDE.md §3).
"""

from __future__ import annotations

from io import BytesIO

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane import komisyon_belgeleri as belgeler
from apps.kutuphane import selectors, selectors_ayiklama, yil_raporu_belgesi
from apps.kutuphane.models import AnnualLibraryReview, DonationIntake, WeedingBatch
from apps.kutuphane.views import _choice_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu

PDF_CONTENT_TYPE = "application/pdf"
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _dosya(icerik: bytes, dosya_adi: str, *, bicim: str = belgeler.PDF) -> FileResponse:
    yanit = FileResponse(
        BytesIO(icerik),
        as_attachment=bicim == belgeler.XLSX,
        filename=dosya_adi,
        content_type=XLSX_CONTENT_TYPE if bicim == belgeler.XLSX else PDF_CONTENT_TYPE,
    )
    yanit["Cache-Control"] = "no-store"
    return yanit


def _teklif(pk: int) -> WeedingBatch:
    teklif = selectors_ayiklama.get_weeding_batch(pk)
    if teklif is None:
        raise Http404
    return teklif


class WeedingBatchDocumentsView(YoneticiKipiGorunumu):
    """`GET library/weeding-batches/<pk>/documents/` — belgeler ve basılabilirlikleri.

    Yanıt: `[{kind, title, formats, available, reason}]`. Kural sunucudadır
    (`komisyon_belgeleri.weeding_document_blocker`); ekran düğmeleri buradan kurar.
    """

    def get(self, request: Request, pk: int) -> Response:
        return Response(belgeler.weeding_documents(_teklif(pk)))


class WeedingBatchDocumentView(YoneticiKipiGorunumu):
    """`GET library/weeding-batches/<pk>/documents/<belge>/?kind=pdf|xlsx` — ayıklama belgesi.

    Basılamayan belge 400 ve gerekçe (`message`) döner; tanınmayan belge 404.
    """

    def get(self, request: Request, pk: int, belge: str) -> FileResponse:
        if belge not in {b.slug for b in belgeler.AYIKLAMA_BELGELERI}:
            raise Http404
        bicim = (
            _choice_param(request.query_params, "kind", (belgeler.PDF, belgeler.XLSX), "biçim")
            or belgeler.PDF
        )
        teklif = _teklif(pk)
        icerik = belgeler.weeding_document(teklif, belge, bicim)
        return _dosya(icerik, belgeler.weeding_document_filename(belge, bicim), bicim=bicim)


class RareWorksSubmissionPdfView(YoneticiKipiGorunumu):
    """`GET library/rare-works-submissions/<pk>/pdf/` — el yazması ve nadir eserler listesi."""

    def get(self, request: Request, pk: int) -> FileResponse:
        liste = selectors_ayiklama.get_rare_works_submission(pk)
        if liste is None:
            raise Http404
        return _dosya(
            belgeler.rare_works_pdf(liste), belgeler.belge_dosya_adi(belgeler.NADIR_ESER_ADI)
        )


class AnnualLibraryReviewPdfView(YoneticiKipiGorunumu):
    """`GET library/annual-reviews/<pk>/pdf/` — yıl sonu kütüphane raporu (kişisel veri yok)."""

    def get(self, request: Request, pk: int) -> FileResponse:
        rapor: AnnualLibraryReview = get_object_or_404(
            AnnualLibraryReview.objects.select_related("school_year"), pk=pk
        )
        return _dosya(
            yil_raporu_belgesi.annual_review_pdf(rapor),
            yil_raporu_belgesi.annual_review_filename(rapor),
        )


class DonationIntakePdfView(YoneticiKipiGorunumu):
    """`GET library/donation-intakes/<pk>/pdf/` — bağış ön kayıt listesi (komisyona sunulur)."""

    def get(self, request: Request, pk: int) -> FileResponse:
        kayit: DonationIntake = get_object_or_404(selectors.donation_intakes(), pk=pk)
        return _dosya(
            belgeler.donation_intake_pdf(kayit),
            belgeler.belge_dosya_adi(belgeler.BAGIS_LISTESI_ADI),
        )


class DonationIntakeResultPdfView(YoneticiKipiGorunumu):
    """`GET library/donation-intakes/<pk>/result-pdf/` — bağış değerlendirme sonucu.

    Yalnız komisyon kararı uygulanmış ön kayıtta basılır; öncesinde 400 ve gerekçe
    (`komisyon_belgeleri.DONATION_NOT_DECIDED_MESSAGE`). Bağışçının adı (şifreli) yalnız
    belgeye çözülür; indirme adında kişi adı yoktur.
    """

    def get(self, request: Request, pk: int) -> FileResponse:
        kayit: DonationIntake = get_object_or_404(selectors.donation_intakes(), pk=pk)
        return _dosya(
            belgeler.donation_result_pdf(kayit),
            belgeler.belge_dosya_adi(belgeler.BAGIS_SONUCU_ADI),
        )
