"""Üyelik yönetim uçları — İNCE görünümler, YALNIZ yönetici kipi (tasarım §4.4, §9-2).

Uçlar (hiçbiri görevli kipi izin listesinde DEĞİLDİR — CLAUDE.md §2-4; masa
uçları ayrıdır):

* `GET/POST library/memberships/` — üyelik listesi (süzgeçli, sayfalı, TR
  sıralı) ve tek kişiye üyelik açma (personelde olağan yol).
* `GET/DELETE library/memberships/<pk>/` — ayrıntı; yanlış açılmış ve hiç
  ödünç kaydı olmayan üyeliğin silinmesi (kart iptal edilir).
* `POST library/memberships/<pk>/renew-card/` — kartı yenile.
* `POST library/memberships/<pk>/terminate/` — elle sonlandırma (neden zorunlu, D12).
* `GET library/memberships/<pk>/loans/` — üyenin ödünç kaydı (sayfalı).
* `GET/POST library/membership-requests/` — şube bazlı üyelik istek listesi
  ve seçilenlere toplu üyelik (Md. 17/1).

Kişi yazan uçlar `RequiresAdminPassword` taşır (parola kurulmadan yazma
yöntemleri 409 `parola_gerekli`; kart no şifreli alan olduğundan izin sınıfı
unutulsa da `KeyMissingError` aynı yanıtı verir). Koruma testi
`apps/okul/tests/test_kisi_yazan_uclar.py` listeyi sabitler.

Kurallar serviste (`services.memberships`), okuma selector'da
(`selectors_dolasim`); görünüm yalnız parametre çözer ve serileştirir.
"""

from __future__ import annotations

from typing import Any, cast

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import LibraryPolicy, Membership, MembershipStatus, MemberType
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_uyelik import (
    MemberLoanSerializer,
    MembershipCreateSerializer,
    MembershipRequestApplySerializer,
    MembershipRequestQuerySerializer,
    MembershipRequestRowSerializer,
    MembershipSerializer,
    MembershipTerminateSerializer,
)
from apps.kutuphane.services import memberships as membership_service
from apps.kutuphane.views import _choice_param, _int_param
from apps.okul import selectors as okul_selectors
from apps.okul.permissions import RequiresAdminPassword


def _uyelik(pk: int) -> Membership:
    uyelik = selectors_dolasim.get_membership(pk)
    if uyelik is None:
        raise Http404
    return uyelik


def _baglam(rows: list[Membership]) -> dict[str, Any]:
    """Liste serileştirmesinin bağlamı: politika bir kez, sayılar TEK sorguyla."""
    return {
        "policy": LibraryPolicy.load(),
        "sayilar": selectors_dolasim.loan_counts_by_person(rows),
    }


class MembershipListCreateView(APIView):
    """`GET/POST library/memberships/` — liste (yönetici) ve tek kişiye üyelik açma.

    GET süzgeçleri: `status` (ACTIVE/TERMINATED), `member_type`
    (STUDENT/TEACHER/STAFF), `class_level`, `class_section`, `search` (ad; okul
    no ve kart no TAM eşleşme). Yanıt sayfalıdır (`{count, next, previous, results}`).
    POST gövdesi `{student_id}` YA DA `{personnel_id}` (+ isteğe bağlı `requested_at`).
    """

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request) -> Response:
        params = request.query_params
        rows = selectors_dolasim.memberships(
            status=_choice_param(params, "status", MembershipStatus.values, "durum"),
            member_type=_choice_param(params, "member_type", MemberType.values, "üye türü"),
            class_level=_int_param(params, "class_level", "Sınıf"),
            class_section=str(params.get("class_section", "")),
            search=str(params.get("search", "")),
        )
        sayfalayici = KatalogSayfalama()
        # Sıralama Python'da yapıldığı için sayfalanan bir listedir (QuerySet değil).
        sayfa = sayfalayici.paginate_queryset(cast("Any", rows), request, view=self)
        gosterilen: list[Membership] = list(sayfa) if sayfa is not None else rows
        veri = MembershipSerializer(gosterilen, many=True, context=_baglam(gosterilen)).data
        return sayfalayici.get_paginated_response(veri)

    def post(self, request: Request) -> Response:
        gonderi = MembershipCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        ogrenci = personel = None
        if "student_id" in veri:
            ogrenci = okul_selectors.get_student(int(veri["student_id"]))
            if ogrenci is None:
                raise serializers.ValidationError({"student_id": "Öğrenci bulunamadı."})
        else:
            personel = okul_selectors.get_personnel(int(veri["personnel_id"]))
            if personel is None:
                raise serializers.ValidationError({"personnel_id": "Personel bulunamadı."})
        uyelik = membership_service.create_membership(
            student=ogrenci, personnel=personel, requested_at=veri.get("requested_at")
        )
        return Response(MembershipSerializer(uyelik).data, status=status.HTTP_201_CREATED)


class MembershipDetailView(APIView):
    """`GET/DELETE library/memberships/<pk>/` — ayrıntı ve yanlış açılmış üyeliğin silinmesi."""

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request, pk: int) -> Response:
        return Response(MembershipSerializer(_uyelik(pk)).data)

    def delete(self, request: Request, pk: int) -> Response:
        membership_service.delete_membership(_uyelik(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MembershipRenewCardView(APIView):
    """`POST library/memberships/<pk>/renew-card/` — kartı yenile (yalnız yönetici kipi).

    Yanıt güncel üyeliktir (yeni kart no); eski kart iptal edilmiştir ve kart
    basımı kuyruğa döner.
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request, pk: int) -> Response:
        uyelik = membership_service.renew_card(_uyelik(pk))
        return Response(MembershipSerializer(uyelik).data)


class MembershipTerminateView(APIView):
    """`POST library/memberships/<pk>/terminate/` gövde `{reason}` — elle sonlandırma (D12)."""

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request, pk: int) -> Response:
        gonderi = MembershipTerminateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        uyelik = membership_service.terminate_membership(
            _uyelik(pk), reason=str(gonderi.validated_data["reason"])
        )
        return Response(MembershipSerializer(uyelik).data)


class MembershipLoansView(APIView):
    """`GET library/memberships/<pk>/loans/` — üyenin ödünç kaydı (sayfalı, en yeni önce).

    YALNIZ yönetici kipi (görevli kipinde "ödünç geçmişi" kapalıdır — §4.4).
    Konu/sınıflama alanı ve toplama YOKTUR (profil yasağı).
    """

    def get(self, request: Request, pk: int) -> Response:
        sayfalayici = KatalogSayfalama()
        qs = selectors_dolasim.member_loan_history(_uyelik(pk))
        sayfa = sayfalayici.paginate_queryset(qs, request, view=self)
        gosterilen = list(sayfa) if sayfa is not None else list(qs)
        return sayfalayici.get_paginated_response(MemberLoanSerializer(gosterilen, many=True).data)


class MembershipRequestsView(APIView):
    """`GET/POST library/membership-requests/` — şube bazlı üyelik istek listesi (§9-2).

    GET `?class_level=&class_section=`: şubedeki aktif öğrenciler ve üyelik
    durumları (sınıf listesi sırası; sayfasız — bir şube küçüktür). POST gövdesi
    `{student_ids: [...], requested_at?}`: seçilenlere TEK işlemde üyelik açar
    (ya hepsi ya hiçbiri). Yanıt açılan üyeliklerdir.
    """

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request) -> Response:
        sorgu = MembershipRequestQuerySerializer(data=request.query_params)
        sorgu.is_valid(raise_exception=True)
        satirlar = selectors_dolasim.membership_request_list(
            class_level=int(sorgu.validated_data["class_level"]),
            class_section=str(sorgu.validated_data["class_section"]),
        )
        return Response(MembershipRequestRowSerializer(satirlar, many=True).data)

    def post(self, request: Request) -> Response:
        gonderi = MembershipRequestApplySerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        acilan = membership_service.create_memberships_for_students(
            list(gonderi.validated_data["student_ids"]),
            requested_at=gonderi.validated_data.get("requested_at"),
        )
        veri = MembershipSerializer(acilan, many=True, context=_baglam(acilan)).data
        return Response(veri, status=status.HTTP_201_CREATED)
