"""Ayıklama, nadir eser ve yıl sonu raporu uçları — İNCE görünümler (F8; tasarım §6.2, §10).

| Uç | Ad | Görevli kipi |
|---|---|---|
| `GET library/weeding/rules/` | `library-weeding-rules` | KAPALI |
| `GET library/weeding/candidates/` | `library-weeding-candidates` | KAPALI |
| `GET/POST library/weeding-batches/` | `library-weeding-batch-list` | KAPALI |
| `GET/PATCH/DELETE library/weeding-batches/<pk>/` | `library-weeding-batch-detail` | KAPALI |
| `POST library/weeding-batches/<pk>/items/` | `library-weeding-batch-items` | KAPALI |
| `PATCH/DELETE library/weeding-batches/<pk>/items/<item_pk>/` | `library-weeding-batch-item-detail` | KAPALI |
| `POST library/weeding-batches/<pk>/submit/` | `library-weeding-batch-submit` | KAPALI |
| `POST library/weeding-batches/<pk>/withdraw/` | `library-weeding-batch-withdraw` | KAPALI |
| `POST library/weeding-batches/<pk>/decision/` | `library-weeding-batch-decision` | KAPALI |
| `POST library/weeding-batches/<pk>/approve/` | `library-weeding-batch-approve` | KAPALI |
| `POST library/weeding-batches/<pk>/apply/` | `library-weeding-batch-apply` | KAPALI |
| `POST library/weeding-batches/<pk>/cancel/` | `library-weeding-batch-cancel` | KAPALI |
| `GET library/rare-copies/` | `library-rare-copy-list` | KAPALI |
| `GET/POST library/rare-works-submissions/` | `library-rare-works-submission-list` | KAPALI |
| `GET/PATCH/DELETE library/rare-works-submissions/<pk>/` | `library-rare-works-submission-detail` | KAPALI |
| `POST library/rare-works-submissions/<pk>/items/` | `library-rare-works-submission-items` | KAPALI |
| `DELETE library/rare-works-submissions/<pk>/items/<item_pk>/` | `library-rare-works-submission-item-detail` | KAPALI |
| `POST library/rare-works-submissions/<pk>/send/` | `library-rare-works-submission-send` | KAPALI |
| `GET/POST library/annual-reviews/` | `library-annual-review-list` | KAPALI |
| `GET/PATCH library/annual-reviews/<pk>/` | `library-annual-review-detail` | KAPALI |
| `POST library/annual-reviews/<pk>/finalize/` | `library-annual-review-finalize` | KAPALI |
| `POST library/annual-reviews/<pk>/reopen/` | `library-annual-review-reopen` | KAPALI |

HİÇBİRİ görevli kipi izin listesinde DEĞİLDİR (§4.4: komisyon, ayıklama ve
raporlar yönetici işidir; ara katman keser, görünüm (`YoneticiKipiGorunumu` —
okumalar dahil) ve servis `require_admin_mode` ile bir kez daha keser). Hiçbiri kişi SİCİLİ yazmaz: ayıklama kalemleri, nadir eser
satırları ve yıl sonu raporu kişisizdir. Teklifin onayındaki adlar (harcama
yetkilisi, TMY komisyonu) şifreli alandır; parola kurulmadan yazan istek 409
`parola_gerekli` alır (fail-closed — `KeyMissingError`; servis ayrıca
`require_password_set` sorar).

Çok nüshalı ekleme bir EYLEMDİR (toplu teslim gibi): bir nüsha engelliyse hiçbiri
eklenmez ve gerekçeler `fields.barcodes` altında döner (400). Evrak (E7, E8, E9,
E16) bu dosyada DEĞİLDİR — belge kolu kendi uçlarını ekler.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.models import (
    CRITERIA_MISMATCH_CRITERIA,
    WEEDING_PATHS,
    WEEDING_TRANSFER_PATHS,
    AnnualLibraryReview,
    RareWorksSubmission,
    RareWorksSubmissionItem,
    RareWorksSubmissionStatus,
    WeedingBatch,
    WeedingBatchStatus,
    WeedingCriterion,
    WeedingItem,
    WeedingReason,
    WeedingTmyPath,
)
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_ayiklama import (
    AnnualLibraryReviewCreateSerializer,
    AnnualLibraryReviewListSerializer,
    AnnualLibraryReviewSerializer,
    AnnualLibraryReviewUpdateSerializer,
    RareCopySerializer,
    RareWorksAddSerializer,
    RareWorksItemSerializer,
    RareWorksSendSerializer,
    RareWorksSubmissionDetailSerializer,
    RareWorksSubmissionSerializer,
    RareWorksSubmissionWriteSerializer,
    WeedingApprovalSerializer,
    WeedingBatchCreateSerializer,
    WeedingBatchDetailSerializer,
    WeedingBatchSerializer,
    WeedingBatchUpdateSerializer,
    WeedingCancelSerializer,
    WeedingCandidateSerializer,
    WeedingDecisionSerializer,
    WeedingItemAddSerializer,
    WeedingItemSerializer,
    WeedingItemUpdateSerializer,
)
from apps.kutuphane.services import annual_review as review_service
from apps.kutuphane.services import rare_works as rare_service
from apps.kutuphane.services import weeding as weeding_service
from apps.kutuphane.views import _bool_param, _choice_param, _int_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.okul.models import SchoolYear

#: Ayıklamaya konamayan kayıttan düşme önerilerinin gerekçeleri (aday ekranı; F8 ekleri 34).
LOST_PROPOSAL_BLOCKER = weeding_service.LOST_MESSAGE
DAMAGE_PROPOSAL_BLOCKER = weeding_service.DAMAGE_PROPOSAL_MESSAGE


def _sayfali(request: Request, view: APIView, qs: Any, serializer: Any) -> Response:
    sayfalayici = KatalogSayfalama()
    sayfa = sayfalayici.paginate_queryset(qs, request, view=view)
    gosterilen = list(sayfa) if sayfa is not None else list(qs)
    return sayfalayici.get_paginated_response(serializer(gosterilen, many=True).data)


def _teklif(pk: int) -> WeedingBatch:
    teklif = selectors_ayiklama.get_weeding_batch(pk)
    if teklif is None:
        raise Http404
    return teklif


def _kalem(pk: int, item_pk: int) -> WeedingItem:
    kalem: WeedingItem | None = (
        WeedingItem.objects.select_related("batch", "copy", "copy__work")
        .filter(pk=item_pk, batch_id=pk)
        .first()
    )
    if kalem is None:
        raise Http404
    return kalem


def _teklif_yaniti(teklif: WeedingBatch, *, kod: int = status.HTTP_200_OK) -> Response:
    guncel = selectors_ayiklama.get_weeding_batch(teklif.pk)
    assert guncel is not None
    return Response(WeedingBatchDetailSerializer(guncel).data, status=kod)


def _gecerli(serializer_sinifi: Any, data: Any, **kw: Any) -> dict[str, Any]:
    gonderi = serializer_sinifi(data=data, **kw)
    gonderi.is_valid(raise_exception=True)
    return dict(gonderi.validated_data)


# ---------------------------------------------------------------------------
# Ayıklama — kurallar ve adaylar
# ---------------------------------------------------------------------------
class WeedingRulesView(YoneticiKipiGorunumu):
    """`GET library/weeding/rules/` — E7 tablosu (gerekçe → TMY yolları) ve seçenekler.

    Ekran gerekçe seçilince TMY yolunu buradan kendiliğinden koyar; kural
    sunucudadır (`models.WEEDING_PATHS`), ekran kopyalamaz. Kişisel veri yok.
    """

    def get(self, request: Request) -> Response:
        return Response(
            {
                "reasons": [
                    {
                        "value": gerekce.value,
                        "label": gerekce.label,
                        "paths": list(WEEDING_PATHS[gerekce.value]),
                        "default_path": WEEDING_PATHS[gerekce.value][0],
                        "needs_criterion": gerekce == WeedingReason.CRITERIA_MISMATCH,
                    }
                    for gerekce in WeedingReason
                ],
                "paths": [
                    {
                        "value": yol.value,
                        "label": yol.label,
                        "is_transfer": yol.value in WEEDING_TRANSFER_PATHS,
                    }
                    for yol in WeedingTmyPath
                ],
                "criteria": [
                    {"value": o.value, "label": o.label}
                    for o in WeedingCriterion
                    if o.value in CRITERIA_MISMATCH_CRITERIA
                ],
            }
        )


class WeedingCandidatesView(YoneticiKipiGorunumu):
    """`GET library/weeding/candidates/` — ayıklamaya konabilecek nüshalar (sayfalı).

    Süzgeçler: `q` (TR arama), `section`. Yanıta ayrıca iki liste eklenir:
    kayıttan düşme önerilmiş KAYIP nüshalar (`lost_proposals`) ve HASAR dosyasında
    kayıttan düşme önerilmiş nüshalar (`damage_proposals`) — ikisi de ayıklamaya
    konmaz, sayımda kayıttan düşülür; gerekçesiyle (`blocker`) gösterilir (25.09.2026
    kullanıcı kararı, tasarım F8 ekleri 34).
    """

    def get(self, request: Request) -> Response:
        params = request.query_params
        qs = selectors_ayiklama.weeding_candidates(
            q=str(params.get("q", "")),
            section_id=_int_param(params, "section", "Bölüm"),
        )
        yanit = _sayfali(request, self, qs, WeedingCandidateSerializer)
        for anahtar, sorgu, gerekce in (
            (
                "lost_proposals",
                selectors_ayiklama.lost_write_off_proposals(),
                LOST_PROPOSAL_BLOCKER,
            ),
            (
                "damage_proposals",
                selectors_ayiklama.damage_write_off_proposals(),
                DAMAGE_PROPOSAL_BLOCKER,
            ),
        ):
            yanit.data[anahtar] = [
                {**satir, "blocker": gerekce}
                for satir in WeedingCandidateSerializer(sorgu, many=True).data
            ]
        return yanit


# ---------------------------------------------------------------------------
# Ayıklama — teklifler
# ---------------------------------------------------------------------------
class WeedingBatchListCreateView(YoneticiKipiGorunumu):
    """`GET/POST library/weeding-batches/` — süzgeçler `status`, `school_year`."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        qs = selectors_ayiklama.weeding_batches(
            status=_choice_param(params, "status", WeedingBatchStatus.values, "durum"),
            school_year_id=_int_param(params, "school_year", "Ders yılı"),
        )
        return _sayfali(request, self, qs, WeedingBatchSerializer)

    def post(self, request: Request) -> Response:
        veri = _gecerli(WeedingBatchCreateSerializer, request.data)
        teklif = weeding_service.create_batch(**veri)
        return _teklif_yaniti(teklif, kod=status.HTTP_201_CREATED)


class WeedingBatchDetailView(YoneticiKipiGorunumu):
    """`GET/PATCH/DELETE library/weeding-batches/<pk>/` — silme yalnız taslakta."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(WeedingBatchDetailSerializer(_teklif(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        veri = _gecerli(WeedingBatchUpdateSerializer, request.data)
        return _teklif_yaniti(weeding_service.update_batch(_teklif(pk), **veri))

    def delete(self, request: Request, pk: int) -> Response:
        weeding_service.delete_batch(_teklif(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class WeedingBatchItemsView(YoneticiKipiGorunumu):
    """`POST library/weeding-batches/<pk>/items/` — okutulan ya da seçilen nüshaları ekler."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(WeedingItemAddSerializer, request.data)
        teklif = _teklif(pk)
        eklenen = weeding_service.add_items(
            teklif,
            reason=veri["reason"],
            barcodes=veri["barcodes"],
            copy_ids=veri["copies"],
            tmy_path=veri["tmy_path"],
            criterion=veri["criterion"],
            transfer_target=veri["transfer_target"],
        )
        return Response(
            {
                "added": WeedingItemSerializer(eklenen, many=True).data,
                "batch": WeedingBatchDetailSerializer(_teklif(pk)).data,
            },
            status=status.HTTP_201_CREATED,
        )


class WeedingBatchItemDetailView(YoneticiKipiGorunumu):
    """`PATCH/DELETE library/weeding-batches/<pk>/items/<item_pk>/` (D15: kalem silme)."""

    def patch(self, request: Request, pk: int, item_pk: int) -> Response:
        gonderi = WeedingItemUpdateSerializer(data=request.data, partial=True)
        gonderi.is_valid(raise_exception=True)
        kalem = weeding_service.update_item(_kalem(pk, item_pk), **dict(gonderi.validated_data))
        return Response(WeedingItemSerializer(kalem).data)

    def delete(self, request: Request, pk: int, item_pk: int) -> Response:
        weeding_service.remove_item(_kalem(pk, item_pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class WeedingBatchSubmitView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        return _teklif_yaniti(weeding_service.submit_batch(_teklif(pk)))


class WeedingBatchWithdrawView(YoneticiKipiGorunumu):
    """Teklifi geri çek (D15) — taslağa döner, sonraki adımların kayıtları temizlenir."""

    def post(self, request: Request, pk: int) -> Response:
        return _teklif_yaniti(weeding_service.withdraw_batch(_teklif(pk)))


class WeedingBatchDecisionView(YoneticiKipiGorunumu):
    """Komisyon kararını bağla — `{commission_decision, kept?: {kalem: gerekçe}}`."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(WeedingDecisionSerializer, request.data)
        teklif = weeding_service.bind_decision(
            _teklif(pk), commission_decision=veri["commission_decision"], kept=veri["kept"]
        )
        return _teklif_yaniti(teklif)


class WeedingBatchApproveView(YoneticiKipiGorunumu):
    """Harcama yetkilisi onayı — adlar şifreli; onaylanmayan kalemler `not_approved`."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(WeedingApprovalSerializer, request.data)
        teklif = weeding_service.approve_batch(_teklif(pk), **veri)
        return _teklif_yaniti(teklif)


class WeedingBatchApplyView(YoneticiKipiGorunumu):
    """Uygula — nüshalar kayıttan düşülür ya da devredilir (TEK işlem)."""

    def post(self, request: Request, pk: int) -> Response:
        sonuc = weeding_service.apply_batch(_teklif(pk))
        return Response(
            {
                "withdrawn": sonuc.withdrawn,
                "transferred": sonuc.transferred,
                "batch": WeedingBatchDetailSerializer(_teklif(pk)).data,
            }
        )


class WeedingBatchCancelView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(WeedingCancelSerializer, request.data)
        return _teklif_yaniti(weeding_service.cancel_batch(_teklif(pk), reason=veri["reason"]))


# ---------------------------------------------------------------------------
# Nadir eserler (Md. 12/2)
# ---------------------------------------------------------------------------
def _liste(pk: int) -> RareWorksSubmission:
    liste = selectors_ayiklama.get_rare_works_submission(pk)
    if liste is None:
        raise Http404
    return liste


def _liste_yaniti(liste: RareWorksSubmission, *, kod: int = status.HTTP_200_OK) -> Response:
    return Response(RareWorksSubmissionDetailSerializer(_liste(liste.pk)).data, status=kod)


class RareCopyListView(YoneticiKipiGorunumu):
    """`GET library/rare-copies/` — nadir eser işaretli nüshalar; `unsent=1` yalnız bildirilmemiş."""

    def get(self, request: Request) -> Response:
        qs = selectors_ayiklama.rare_copies(unsent_only=_bool_param(request.query_params, "unsent"))
        return _sayfali(request, self, qs, RareCopySerializer)


class RareWorksSubmissionListCreateView(YoneticiKipiGorunumu):
    def get(self, request: Request) -> Response:
        qs = selectors_ayiklama.rare_works_submissions(
            status=_choice_param(
                request.query_params, "status", RareWorksSubmissionStatus.values, "durum"
            )
        )
        return _sayfali(request, self, qs, RareWorksSubmissionSerializer)

    def post(self, request: Request) -> Response:
        veri = _gecerli(RareWorksSubmissionWriteSerializer, request.data)
        liste = rare_service.create_submission(
            school_year=veri.get("school_year"),
            commission_decision=veri.get("commission_decision"),
            notes=veri.get("notes", ""),
        )
        return _liste_yaniti(liste, kod=status.HTTP_201_CREATED)


class RareWorksSubmissionDetailView(YoneticiKipiGorunumu):
    def get(self, request: Request, pk: int) -> Response:
        return Response(RareWorksSubmissionDetailSerializer(_liste(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        gonderi = RareWorksSubmissionWriteSerializer(data=request.data, partial=True)
        gonderi.is_valid(raise_exception=True)
        alanlar = {
            ad: deger
            for ad, deger in gonderi.validated_data.items()
            if ad in ("commission_decision", "notes") and ad in request.data
        }
        return _liste_yaniti(rare_service.update_submission(_liste(pk), **alanlar))

    def delete(self, request: Request, pk: int) -> Response:
        rare_service.delete_submission(_liste(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RareWorksSubmissionItemsView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(RareWorksAddSerializer, request.data)
        eklenen = rare_service.add_copies(
            _liste(pk), barcodes=veri["barcodes"], copy_ids=veri["copies"]
        )
        return Response(
            {
                "added": RareWorksItemSerializer(eklenen, many=True).data,
                "submission": RareWorksSubmissionDetailSerializer(_liste(pk)).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RareWorksSubmissionItemDetailView(YoneticiKipiGorunumu):
    def delete(self, request: Request, pk: int, item_pk: int) -> Response:
        satir: RareWorksSubmissionItem | None = RareWorksSubmissionItem.objects.filter(
            pk=item_pk, submission_id=pk
        ).first()
        if satir is None:
            raise Http404
        rare_service.remove_item(satir)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RareWorksSubmissionSendView(YoneticiKipiGorunumu):
    """Genel Müdürlüğe gönderimi kaydet — `{sent_on, sent_document_no?}`."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(RareWorksSendSerializer, request.data)
        return _liste_yaniti(rare_service.send_submission(_liste(pk), **veri))


# ---------------------------------------------------------------------------
# Yıl sonu kütüphane raporu (E9)
# ---------------------------------------------------------------------------
def _rapor(pk: int) -> AnnualLibraryReview:
    rapor: AnnualLibraryReview | None = (
        AnnualLibraryReview.objects.select_related("school_year").filter(pk=pk).first()
    )
    if rapor is None:
        raise Http404
    return rapor


class AnnualLibraryReviewListCreateView(YoneticiKipiGorunumu):
    """`GET/POST library/annual-reviews/` — ders yılı başına tek rapor."""

    def get(self, request: Request) -> Response:
        qs = AnnualLibraryReview.objects.select_related("school_year").order_by(
            "-school_year__start_date", "-pk"
        )
        return _sayfali(request, self, qs, AnnualLibraryReviewListSerializer)

    def post(self, request: Request) -> Response:
        veri = _gecerli(AnnualLibraryReviewCreateSerializer, request.data)
        yil: SchoolYear | None = veri.get("school_year")
        rapor = review_service.create_review(school_year=yil)
        return Response(
            AnnualLibraryReviewSerializer(_rapor(rapor.pk)).data, status=status.HTTP_201_CREATED
        )


class AnnualLibraryReviewDetailView(YoneticiKipiGorunumu):
    def get(self, request: Request, pk: int) -> Response:
        return Response(AnnualLibraryReviewSerializer(_rapor(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        gonderi = AnnualLibraryReviewUpdateSerializer(data=request.data, partial=True)
        gonderi.is_valid(raise_exception=True)
        rapor = review_service.update_review(_rapor(pk), **dict(gonderi.validated_data))
        return Response(AnnualLibraryReviewSerializer(_rapor(rapor.pk)).data)


class AnnualLibraryReviewFinalizeView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        rapor = review_service.finalize_review(_rapor(pk))
        return Response(AnnualLibraryReviewSerializer(_rapor(rapor.pk)).data)


class AnnualLibraryReviewReopenView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        rapor = review_service.reopen_review(_rapor(pk))
        return Response(AnnualLibraryReviewSerializer(_rapor(rapor.pk)).data)
