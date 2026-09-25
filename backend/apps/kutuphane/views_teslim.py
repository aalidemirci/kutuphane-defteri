"""Teslim, kayıp/hasar ve onarım uçları — İNCE görünümler (F7; tasarım §9-9, §9-11, §4.4).

| Uç | Ad | Görevli kipi |
|---|---|---|
| `GET/POST library/deliveries/` | `library-delivery-list` | KAPALI — teslim listesi ve toplu teslim |
| `POST library/deliveries/check/` | `library-delivery-check` | KAPALI — teslim listesine okutma ön denetimi |
| `POST library/deliveries/take-back/` | `library-delivery-take-back` | AÇIK — geri alma okutması |
| `GET/POST library/loss-damage-cases/` | `library-loss-damage-case-list` | KAPALI |
| `GET/PATCH library/loss-damage-cases/<pk>/` | `library-loss-damage-case-detail` | KAPALI |
| `POST library/loss-damage-cases/<pk>/resolve/` | `library-loss-damage-case-resolve` | KAPALI |
| `POST library/copies/<pk>/send-to-repair/` | `library-copy-send-to-repair` | KAPALI |
| `POST library/copies/<pk>/return-from-repair/` | `library-copy-return-from-repair` | KAPALI |

Görevli kipinde AÇIK tek uç geri alma okutmasıdır (§4.4 "Teslimden geri alma
okutması"; `apps/okul/kip_izinleri.py`): yanıt görevli kipinde daralır — teslim
alanın kimliği yoktur (`serializers_teslim.STAFF_TAKE_BACK_FIELDS`). Teslim
VERME, kayıp dosyaları ve onarım yönetici işidir (§4.4 tablosunun "Kapalı"
sütunu); ara katman keser, servis bir kez daha keser (`require_admin_mode`).

Kişi YAZAN uçlar `RequiresAdminPassword` taşır (parola kurulmadan 409
`parola_gerekli`): teslim öğretmene bağlanır, geri alma o kaydı kapatır, dosya
üyeliğe ve şifreli sorumlu notuna yazar (`apps/okul/tests/test_kisi_yazan_uclar.py`).
Onarım kaydı kişisizdir.

Okutma bir OLAYDIR: geri alma her zaman 200 gövde döner (`result`, `message`);
toplu teslim bir EYLEMDİR — listedeki bir kitap teslim edilemiyorsa hiçbiri
yapılmaz ve gerekçeler `fields.barcodes` altında döner (400).
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_dolasim, selectors_teslim
from apps.kutuphane.models import (
    CaseResolution,
    CaseType,
    Copy,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    Loan,
    LossDamageCase,
    Membership,
)
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_teslim import (
    CaseCreateSerializer,
    CaseResolveSerializer,
    CaseSerializer,
    CaseUpdateSerializer,
    CopyRepairSerializer,
    DeliveryCheckSerializer,
    DeliveryCreateSerializer,
    DeliveryScanSerializer,
    DeliverySerializer,
)
from apps.kutuphane.services import deliveries as delivery_service
from apps.kutuphane.services import loss_damage as case_service
from apps.kutuphane.services import masa
from apps.kutuphane.views import _bool_param, _choice_param, _int_param
from apps.okul import selectors as okul_selectors
from apps.okul.kip import KIP
from apps.okul.models import ClassSection
from apps.okul.permissions import RequiresAdminPassword

REPAIR_SENT_MESSAGE = "Nüsha onarıma gönderildi."
REPAIR_RETURNED_MESSAGE = "Nüsha onarımdan döndü; rafta."


def _sayfali(request: Request, view: APIView, qs: Any, serializer: Any, **kw: Any) -> Response:
    sayfalayici = KatalogSayfalama()
    sayfa = sayfalayici.paginate_queryset(qs, request, view=view)
    gosterilen = list(sayfa) if sayfa is not None else list(qs)
    return sayfalayici.get_paginated_response(serializer(gosterilen, many=True, **kw).data)


def _nusha(pk: int) -> Copy:
    nusha: Copy | None = Copy.objects.select_related("work").filter(pk=pk).first()
    if nusha is None:
        raise Http404
    return nusha


# ---------------------------------------------------------------------------
# Teslim
# ---------------------------------------------------------------------------
class DeliveryListCreateView(APIView):
    """`GET/POST library/deliveries/` — teslim satırları ve toplu teslim (yalnız yönetici).

    GET süzgeçleri: `status` (OPEN/RETURNED/LOST_CONVERTED), `recipient_kind`
    (SECTION/TEACHER), `section`, `personnel`, `document_no` (E15 listesi),
    `copy`. Sayfalı, en yeni teslim önce. POST gövdesi `{section_id |
    personnel_id, barcodes: [...], delivered_on?, expected_return?,
    document_no?}`; yanıt belge no, tarihler, alan ve açılan satırlardır (201).
    """

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request) -> Response:
        params = request.query_params
        qs = selectors_teslim.deliveries(
            status=_choice_param(params, "status", DeliveryStatus.values, "durum"),
            recipient_kind=_choice_param(
                params, "recipient_kind", DeliveryRecipientKind.values, "teslim alan türü"
            ),
            section_id=_int_param(params, "section", "Şube"),
            personnel_id=_int_param(params, "personnel", "Öğretmen"),
            document_no=str(params.get("document_no", "")).strip(),
            copy_id=_int_param(params, "copy", "Nüsha"),
        )
        return _sayfali(request, self, qs, DeliverySerializer)

    def post(self, request: Request) -> Response:
        gonderi = DeliveryCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        sube: ClassSection | None = None
        ogretmen = None
        if "section_id" in veri:
            sube = okul_selectors.get_class_section(int(veri["section_id"]))
            if sube is None:
                raise serializers.ValidationError({"section_id": "Şube bulunamadı."})
        else:
            ogretmen = okul_selectors.get_personnel(int(veri["personnel_id"]))
            if ogretmen is None:
                raise serializers.ValidationError({"personnel_id": "Öğretmen bulunamadı."})
        sonuc = delivery_service.deliver(
            barcodes=list(veri["barcodes"]),
            section=sube,
            personnel=ogretmen,
            delivered_on=veri.get("delivered_on"),
            expected_return=veri.get("expected_return"),
            document_no=str(veri.get("document_no") or ""),
        )
        ilk = sonuc.deliveries[0]
        govde = {
            "document_no": sonuc.document_no,
            "delivered_on": sonuc.delivered_on,
            "expected_return": sonuc.expected_return,
            "recipient_kind": sonuc.recipient_kind,
            "recipient_kind_display": str(ilk.get_recipient_kind_display()),
            "recipient_label": selectors_teslim.delivery_recipient_label(ilk),
            "count": len(sonuc.deliveries),
            "deliveries": DeliverySerializer(list(sonuc.deliveries), many=True).data,
        }
        return Response(govde, status=status.HTTP_201_CREATED)


class DeliveryCheckView(APIView):
    """`POST library/deliveries/check/` `{barcode}` — teslim listesine okutulan kodun ön
    denetimi (yazma YOK): `{result: deliverable|rejected, kind, message, copy}`."""

    def post(self, request: Request) -> Response:
        gonderi = DeliveryCheckSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        return Response(delivery_service.delivery_check_scan(gonderi.validated_data["barcode"]))


class DeliveryTakeBackView(APIView):
    """`POST library/deliveries/take-back/` — geri alma okutması (görevli kipinde AÇIK).

    Gövde `{barcode}` → tek sonuç `{result, kind, message, copy[, delivery]}`;
    `{barcodes: [...]}` (okuyucu kuyruğu) → `{results: [...]}`. Her zaman 200.
    `result`: `returned` · `not_delivered` · `rejected`. Görevli kipinde `delivery`
    alanı yoktur. Teslim kaydını kapatır: `RequiresAdminPassword`.
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request) -> Response:
        gonderi = DeliveryScanSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        gorevli = KIP.gorevli_mi()
        if "barcodes" in veri:
            sonuclar = delivery_service.take_back_scans(veri["barcodes"], staff=gorevli)
            return Response({"results": sonuclar})
        return Response(delivery_service.take_back_scan(veri["barcode"], staff=gorevli))


# ---------------------------------------------------------------------------
# Kayıp / hasar dosyası
# ---------------------------------------------------------------------------
def _dosya(pk: int) -> LossDamageCase:
    dosya = selectors_teslim.get_case(pk)
    if dosya is None:
        raise Http404
    return dosya


def _dosya_nushasi(veri: dict[str, Any]) -> Copy:
    if "copy_id" in veri:
        nusha: Copy | None = (
            Copy.objects.select_related("work").filter(pk=int(veri["copy_id"])).first()
        )
        if nusha is None:
            raise serializers.ValidationError({"copy_id": "Nüsha bulunamadı."})
        return nusha
    okutma = masa.kitap_coz(veri["barcode"], staff=False)
    if not okutma.usable or okutma.copy is None:
        raise serializers.ValidationError({"barcode": okutma.message})
    return okutma.copy


def _secimlik(model: Any, veri: dict[str, Any], alan: str, etiket: str) -> Any:
    if alan not in veri:
        return None
    kayit = model.objects.filter(pk=int(veri[alan])).first()
    if kayit is None:
        raise serializers.ValidationError({alan: f"{etiket} bulunamadı."})
    return kayit


class LossDamageCaseListCreateView(APIView):
    """`GET/POST library/loss-damage-cases/` — dosyalar ve dosya açma (yalnız yönetici).

    GET süzgeçleri: `resolution`, `case_type` (LOST/DAMAGED), `open` (1: yalnız
    çözülmemişler), `copy`. Sayfalı yanıt ayrıca `price_options_available` taşır
    (Md. 19 kademe kapısının yansıması — liste boşken de ekran bedel süzgecini
    buna göre kurar). POST: `{case_type, copy_id | barcode, loan_id?,
    delivery_id?, membership_id?, responsible_note?, reported_on?,
    send_to_repair?}` — kayıpta ödünç ve teslim kendiliğinden bulunur ve kapanır.
    """

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request) -> Response:
        params = request.query_params
        qs = selectors_teslim.loss_damage_cases(
            resolution=_choice_param(params, "resolution", CaseResolution.values, "çözüm"),
            case_type=_choice_param(params, "case_type", CaseType.values, "dosya türü"),
            open_only=_bool_param(params, "open"),
            copy_id=_int_param(params, "copy", "Nüsha"),
        )
        bedel = case_service.price_options_available()
        yanit = _sayfali(
            request, self, qs, CaseSerializer, context={"price_options_available": bedel}
        )
        yanit.data["price_options_available"] = bedel
        return yanit

    def post(self, request: Request) -> Response:
        gonderi = CaseCreateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        nusha = _dosya_nushasi(veri)
        uyelik: Membership | None = None
        if "membership_id" in veri:
            uyelik = selectors_dolasim.get_membership(int(veri["membership_id"]))
            if uyelik is None:
                raise serializers.ValidationError({"membership_id": "Üyelik bulunamadı."})
        if veri["case_type"] == CaseType.LOST:
            dosya = case_service.report_lost(
                copy=nusha,
                membership=uyelik,
                responsible_note=str(veri.get("responsible_note") or ""),
                reported_on=veri.get("reported_on"),
            )
        else:
            dosya = case_service.open_damage_case(
                copy=nusha,
                loan=_secimlik(Loan, veri, "loan_id", "Ödünç"),
                delivery=_secimlik(Delivery, veri, "delivery_id", "Teslim"),
                membership=uyelik,
                responsible_note=str(veri.get("responsible_note") or ""),
                reported_on=veri.get("reported_on"),
                send_to_repair=bool(veri.get("send_to_repair")),
            )
        return Response(CaseSerializer(_dosya(dosya.pk)).data, status=status.HTTP_201_CREATED)


class LossDamageCaseDetailView(APIView):
    """`GET/PATCH library/loss-damage-cases/<pk>/` — ayrıntı ve sorumlu notu (açık dosyada)."""

    permission_classes = [RequiresAdminPassword]

    def get(self, request: Request, pk: int) -> Response:
        return Response(CaseSerializer(_dosya(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        gonderi = CaseUpdateSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        case_service.update_case_note(
            _dosya(pk), responsible_note=str(gonderi.validated_data["responsible_note"])
        )
        return Response(CaseSerializer(_dosya(pk)).data)


class LossDamageCaseResolveView(APIView):
    """`POST library/loss-damage-cases/<pk>/resolve/` `{resolution, market_price?}`.

    Bedel yolları yalnız ortaöğretimde (Md. 19); ilkokul ve ortaokulda 400.
    Program tahsilat yapmaz — bedel yalnız kaydedilir.
    """

    permission_classes = [RequiresAdminPassword]

    def post(self, request: Request, pk: int) -> Response:
        gonderi = CaseResolveSerializer(data=request.data)
        gonderi.is_valid(raise_exception=True)
        veri = gonderi.validated_data
        case_service.resolve_case(
            _dosya(pk),
            resolution=str(veri["resolution"]),
            market_price=veri.get("market_price"),
        )
        return Response(CaseSerializer(_dosya(pk)).data)


# ---------------------------------------------------------------------------
# Onarım (D3)
# ---------------------------------------------------------------------------
class CopySendToRepairView(APIView):
    """`POST library/copies/<pk>/send-to-repair/` — "Rafta" → "Onarımda" (yalnız yönetici).

    Nüshanın çözülmemiş hasar dosyası varsa onarım kaydı ona bağlanır. Yanıt
    `{message, repair}` (201).
    """

    def post(self, request: Request, pk: int) -> Response:
        kayit = case_service.send_to_repair(_nusha(pk))
        return Response(
            {"message": REPAIR_SENT_MESSAGE, "repair": CopyRepairSerializer(kayit).data},
            status=status.HTTP_201_CREATED,
        )


class CopyReturnFromRepairView(APIView):
    """`POST library/copies/<pk>/return-from-repair/` — "Onarımda" → "Rafta" (yalnız yönetici).

    Hasar dosyasını kendiliğinden kapatmaz ("Onarıldı" ayrıca seçilir). Yanıt
    `{message, repair}`; kaydı olmayan eski "Onarımda" nüshada `repair` boştur.
    """

    def post(self, request: Request, pk: int) -> Response:
        kayit = case_service.return_from_repair(_nusha(pk))
        return Response(
            {
                "message": REPAIR_RETURNED_MESSAGE,
                "repair": CopyRepairSerializer(kayit).data if kayit is not None else None,
            }
        )
