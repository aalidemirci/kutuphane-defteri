"""Evrak, kart basımı ve pano uçları — İNCE görünümler, YALNIZ yönetici kipi (E2, E4, E13, E19, T15).

| Uç | Ad | İş |
|---|---|---|
| `GET library/member-cards/` | `library-member-card-list` | Kart basımı kuyruğu (`?state=pending`) ya da kartı basılmışlar (`printed`); süzgeçli, sayfalı, basım sırasıyla |
| `GET library/member-cards/template/` | `library-member-card-template` | Kart şablonu (ilk kullanımda tohumdan yazılır) |
| `POST library/member-cards/pdf/` | `library-member-card-pdf` | Üye kartı PDF'i — işarete DOKUNMAZ (D10) |
| `POST library/member-cards/confirm-print/` | `library-member-card-confirm-print` | "Basıldı olarak işaretle" (kişi yazar) |
| `POST library/member-cards/revert-print/` | `library-member-card-revert-print` | "Basım işaretini geri al" (kişi yazar) |
| `GET library/overdue-loans/` | `library-overdue-loan-list` | Gecikmiş ödünçler (kişi sırasıyla, sayfalı) |
| `GET library/overdue-loans/pdf/` | `library-overdue-loan-pdf` | Gecikmiş ödünç listesi PDF'i (dipnotlu) |
| `POST library/overdue-loans/slips/` | `library-overdue-slip-pdf` | İade hatırlatma pusulaları (tek kişilik) |
| `POST library/documents/privacy-notice/` | `library-privacy-notice-pdf` | Kütüphane aydınlatma metni |
| `GET library/documents/desk-card/` | `library-desk-card-pdf` | Masa kartı |
| `GET/POST library/dashboard/circulation/` | `library-dashboard-circulation` | Pano: gecikmiş ödünç SAYISI, beklenmedik kapanış; POST "Kontrol ettim" |
| `GET library/dashboard/recent-transactions/` | `library-dashboard-recent-transactions` | Son oturumdaki ödünç ve iadeler (T15) |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (varsayılan kapalı — CLAUDE.md
§2-4): kart basmak, gecikme listesi, pusula ve son işlemler yönetici işidir
(§4.4 "gecikme listesi", "son işlemler" kapalı). Kart basım işaretini yazan iki
uç `RequiresAdminPassword` taşır (üyelik kişi verisidir;
`apps/okul/tests/test_kisi_yazan_uclar.py`). PDF uçları hiçbir kayıt yazmaz.
PDF yanıtları `Cache-Control: no-store` taşır; indirme adında kişi adı YOKTUR.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.http import FileResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import dolasim_belgeleri, pano, selectors_dolasim
from apps.kutuphane.labels import card as card_engine
from apps.kutuphane.labels.serializers import LabelSheetTemplateSerializer
from apps.kutuphane.models import MemberType
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_evrak import (
    MemberCardPdfRequestSerializer,
    MemberCardRowSerializer,
    MemberCardSelectionSerializer,
    OverdueLoanRowSerializer,
    OverdueScopeSerializer,
    OverdueSlipRequestSerializer,
    PrivacyNoticeRequestSerializer,
    RecentTransactionSerializer,
)
from apps.kutuphane.services import member_cards
from apps.kutuphane.views import _choice_param, _int_param
from apps.okul.permissions import RequiresAdminPassword

PDF_CONTENT_TYPE = "application/pdf"
#: Yanıtta kart basımının tabaka sayısı — ön yüz "N tabaka" diyebilsin (etiketle aynı başlık).
SHEETS_HEADER = "X-KD-Tabaka-Sayisi"
CARD_STATES = ("pending", "printed")
NO_OVERDUE_MESSAGE = "Bu seçimde gecikmiş ödünç yok."


def _pdf(icerik: bytes, dosya_adi: str) -> FileResponse:
    yanit = FileResponse(
        BytesIO(icerik), as_attachment=False, filename=dosya_adi, content_type=PDF_CONTENT_TYPE
    )
    yanit["Cache-Control"] = "no-store"
    return yanit


def _sayfali(request: Request, view: APIView, rows: list[Any], serializer: Any) -> Response:
    """Python'da sıralanmış listeyi sayfalar (ad şifreli — DB sırası kullanılamaz)."""
    sayfalayici = KatalogSayfalama()
    sayfa = sayfalayici.paginate_queryset(cast("Any", rows), request, view=view)
    gosterilen = list(sayfa) if sayfa is not None else rows
    return sayfalayici.get_paginated_response(serializer(gosterilen, many=True).data)


def _kapsam(veri: Any) -> tuple[int | None, str]:
    sorgu = OverdueScopeSerializer(data=veri)
    sorgu.is_valid(raise_exception=True)
    seviye = sorgu.validated_data.get("class_level")
    return (int(seviye) if seviye is not None else None), str(
        sorgu.validated_data.get("class_section") or ""
    )


# ---------------------------------------------------------------------------
# E2 — üye kartı
# ---------------------------------------------------------------------------
class MemberCardListView(APIView):
    """`GET library/member-cards/` — `?state=pending|printed&member_type=&class_level=&class_section=&search=`."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        durum = _choice_param(params, "state", CARD_STATES, "durum") or "pending"
        rows = member_cards.card_queue(
            printed=durum == "printed",
            member_type=_choice_param(params, "member_type", MemberType.values, "üye türü"),
            class_level=_int_param(params, "class_level", "Sınıf"),
            class_section=str(params.get("class_section", "")),
            search=str(params.get("search", "")),
        )
        return _sayfali(request, self, rows, MemberCardRowSerializer)


class MemberCardTemplateView(APIView):
    """`GET library/member-cards/template/` — kart şablonu (kalibrasyonları etiket uçlarından)."""

    def get(self, request: Request) -> Response:
        return Response(LabelSheetTemplateSerializer(card_engine.ensure_card_template()).data)


class MemberCardPdfView(APIView):
    """`POST library/member-cards/pdf/` — kart PDF'i (basım sırası; sınıf karta basılmaz)."""

    def post(self, request: Request) -> FileResponse:
        istek = MemberCardPdfRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        veri = istek.validated_data
        uyelikler = member_cards.memberships_for_print(veri["membership_ids"])
        sablon = veri.get("template") or card_engine.ensure_card_template()
        sonuc = card_engine.render_member_cards(
            member_cards.card_items(uyelikler),
            template=sablon,
            calibration=veri.get("calibration"),
            start_cell=int(veri["start_cell"]),
            cut_guides=bool(veri["cut_guides"]),
        )
        yanit = _pdf(sonuc.pdf, dolasim_belgeleri.belge_dosya_adi(card_engine.DOCUMENT_NAME))
        yanit[SHEETS_HEADER] = str(sonuc.sheet_count)
        return yanit


class MemberCardConfirmPrintView(APIView):
    """`POST library/member-cards/confirm-print/` `{membership_ids}` — "Basıldı olarak işaretle"."""

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        istek = MemberCardSelectionSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        sayi = member_cards.confirm_printed(istek.validated_data["membership_ids"])
        return Response({"marked": sayi})


class MemberCardRevertPrintView(APIView):
    """`POST library/member-cards/revert-print/` `{membership_ids}` — kartlar kuyruğa döner."""

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        istek = MemberCardSelectionSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        sayi = member_cards.revert_printed(istek.validated_data["membership_ids"])
        return Response({"reverted": sayi})


# ---------------------------------------------------------------------------
# E4 — gecikmiş ödünçler, liste ve pusula
# ---------------------------------------------------------------------------
class OverdueLoanListView(APIView):
    """`GET library/overdue-loans/?class_level=&class_section=` — kişi sırasıyla, sayfalı."""

    def get(self, request: Request) -> Response:
        seviye, sube = _kapsam(request.query_params)
        rows = dolasim_belgeleri.overdue_rows(class_level=seviye, class_section=sube)
        return _sayfali(request, self, rows, OverdueLoanRowSerializer)


class OverdueLoanPdfView(APIView):
    """`GET library/overdue-loans/pdf/?class_level=&class_section=` — toplu liste (dipnotlu)."""

    def get(self, request: Request) -> FileResponse:
        seviye, sube = _kapsam(request.query_params)
        rows = dolasim_belgeleri.overdue_rows(class_level=seviye, class_section=sube)
        pdf = dolasim_belgeleri.overdue_list_pdf(rows, class_level=seviye, class_section=sube)
        return _pdf(
            pdf,
            dolasim_belgeleri.belge_dosya_adi(
                dolasim_belgeleri.LISTE_ADI, kapsam=dolasim_belgeleri.scope_slug(seviye, sube)
            ),
        )


class OverdueSlipPdfView(APIView):
    """`POST library/overdue-loans/slips/` `{membership_ids?, class_level?, class_section?}`.

    Kişi başına bir pusula (kişinin bütün gecikmiş ödünçleri). `membership_ids`
    verilirse yalnız o kişiler; verilmezse kapsamdaki herkes.
    """

    def post(self, request: Request) -> FileResponse:
        istek = OverdueSlipRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        veri = istek.validated_data
        seviye = veri.get("class_level")
        gruplar = dolasim_belgeleri.overdue_groups(
            class_level=int(seviye) if seviye is not None else None,
            class_section=str(veri.get("class_section") or ""),
            membership_ids=veri.get("membership_ids"),
        )
        if not gruplar:
            raise ValidationError(NO_OVERDUE_MESSAGE)
        if len(gruplar) > dolasim_belgeleri.MAX_SLIPS_PER_DOCUMENT:
            raise ValidationError(
                f"Tek seferde en çok {dolasim_belgeleri.MAX_SLIPS_PER_DOCUMENT} kişinin pusulası "
                "basılabilir; şube şube basın."
            )
        pdf = dolasim_belgeleri.slips_pdf(gruplar)
        return _pdf(pdf, dolasim_belgeleri.belge_dosya_adi(dolasim_belgeleri.PUSULA_ADI))


# ---------------------------------------------------------------------------
# E13, E19
# ---------------------------------------------------------------------------
class PrivacyNoticePdfView(APIView):
    """`POST library/documents/privacy-notice/` `{basvuru_adresi?, iletisim?}` — saklanmaz."""

    def post(self, request: Request) -> FileResponse:
        istek = PrivacyNoticeRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        pdf = dolasim_belgeleri.privacy_notice_pdf(
            basvuru_adresi=str(istek.validated_data["basvuru_adresi"]),
            iletisim=str(istek.validated_data["iletisim"]),
        )
        return _pdf(pdf, dolasim_belgeleri.belge_dosya_adi(dolasim_belgeleri.AYDINLATMA_ADI))


class DeskCardPdfView(APIView):
    """`GET library/documents/desk-card/` — masa kartı (kişisel veri yok)."""

    def get(self, request: Request) -> FileResponse:
        return _pdf(
            dolasim_belgeleri.desk_card_pdf(),
            dolasim_belgeleri.belge_dosya_adi(dolasim_belgeleri.MASA_KARTI_ADI),
        )


# ---------------------------------------------------------------------------
# Pano (A11, T15)
# ---------------------------------------------------------------------------
class DashboardCirculationView(APIView):
    """`GET/POST library/dashboard/circulation/` — kişisiz özet; POST beklenmedik kapanışı onaylar."""

    def get(self, request: Request) -> Response:
        return Response(pano.circulation_summary())

    def post(self, request: Request) -> Response:
        pano.acknowledge_unexpected_shutdown()
        return Response(pano.circulation_summary())


class RecentTransactionsView(APIView):
    """`GET library/dashboard/recent-transactions/` — bu oturumdan önceki son ödünç ve iadeler."""

    def get(self, request: Request) -> Response:
        islemler = selectors_dolasim.recent_transactions()
        return Response(RecentTransactionSerializer(islemler, many=True).data)
