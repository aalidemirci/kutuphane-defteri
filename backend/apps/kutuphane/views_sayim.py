"""Sayım uçları — İNCE görünümler (F9; TMY 32, tasarım §9-10, §9-11, §10 E10).

| Uç | Ad | Görevli kipi |
|---|---|---|
| `GET/POST library/stocktakes/` | `library-stocktake-list` | KAPALI |
| `GET library/stocktakes/state/` | `library-stocktake-state` | KAPALI |
| `GET/PATCH/DELETE library/stocktakes/<pk>/` | `library-stocktake-detail` | KAPALI |
| `POST library/stocktakes/<pk>/start/` | `library-stocktake-start` | KAPALI |
| `POST library/stocktakes/<pk>/scan/` | `library-stocktake-scan` | AÇIK — yanıt daralır |
| `GET library/stocktakes/<pk>/items/` | `library-stocktake-items` | KAPALI |
| `PATCH/DELETE library/stocktakes/<pk>/items/<item_pk>/` | `library-stocktake-item-detail` | KAPALI |
| `POST library/stocktakes/<pk>/surplus/` | `library-stocktake-surplus` | KAPALI |
| `GET library/stocktakes/<pk>/progress/` | `library-stocktake-progress` | KAPALI |
| `POST library/stocktakes/<pk>/complete/` | `library-stocktake-complete` | KAPALI |
| `POST library/stocktakes/<pk>/approve/` | `library-stocktake-approve` | KAPALI |
| `POST library/stocktakes/<pk>/cancel/` | `library-stocktake-cancel` | KAPALI |
| `GET library/stocktakes/<pk>/tmy-34-1/` | `library-stocktake-tmy-34-1` | KAPALI |

Görevli kipi izin listesinde YALNIZ okutma (`library-stocktake-scan` POST) vardır
(madde 24, 25.09.2026 kullanıcı kararı; emsal etiket doğrulama okutması): görevli
kitapların etiketini okutabilir, yanıt daralır — yalnız okutma sonucu, ileti, barkod ve
eser adı (`serializers_sayim.STAFF_SCAN_FIELDS`; kalem, özet ve kayda göre durum yok).
Başlatma, tamamlama, onay, iptal, kalem listesi, ilerleme, fazla kararı ve belgeler
yönetici işidir (varsayılan kapalı — CLAUDE.md §2-4): ara katman keser, görünüm
(`YoneticiKipiGorunumu` — okumalar dahil) ve servis bir kez daha keser. Görevli ekranı
süren sayımı masa durumundan öğrenir (`library-desk-state`, `views_masa`).

Kurul ve harcama yetkilisi adları şifreli alandır; parola kurulmadan yazan istek 409
`parola_gerekli` alır. Kalem yanıtları kişisizdir (ödünç alanın kimliği yok).
Okutma kuyruğu bir EYLEM değil, bir dizi okutmadır: her kod ayrı sonuç döner (biri
reddedilse de öbürleri işlenir) — hızlı okutmada kayıp olmaz.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import selectors_sayim
from apps.kutuphane.models import (
    CountBasis,
    StockTake,
    StockTakeItem,
    StockTakeOutcome,
    StockTakeResult,
    StockTakeStatus,
)
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_sayim import (
    StockTakeApproveSerializer,
    StockTakeCancelSerializer,
    StockTakeDetailSerializer,
    StockTakeItemSerializer,
    StockTakeListSerializer,
    StockTakeScanSerializer,
    StockTakeSurplusCreateSerializer,
    StockTakeSurplusUpdateSerializer,
    StockTakeWriteSerializer,
    staff_scan_result,
)
from apps.kutuphane.services import stocktake as stocktake_service
from apps.kutuphane.views import _bool_param, _choice_param, _int_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.okul.kip import KIP


def _sayim(pk: int) -> StockTake:
    sayim = selectors_sayim.get_stocktake(pk)
    if sayim is None:
        raise Http404
    return sayim


def _kalem(pk: int, item_pk: int) -> StockTakeItem:
    kalem: StockTakeItem | None = StockTakeItem.objects.filter(pk=item_pk, stocktake_id=pk).first()
    if kalem is None:
        raise Http404
    return kalem


def _ayrinti(sayim: StockTake, *, kod: int = status.HTTP_200_OK) -> Response:
    return Response(StockTakeDetailSerializer(_sayim(sayim.pk)).data, status=kod)


def _gecerli(serializer_sinifi: Any, data: Any, **kw: Any) -> dict[str, Any]:
    gonderi = serializer_sinifi(data=data, **kw)
    gonderi.is_valid(raise_exception=True)
    return dict(gonderi.validated_data)


def _istege_bagli_bool(params: Any, ad: str) -> bool | None:
    """`?surplus=1|0` — verilmemişse None (süzgeç yok)."""
    if str(params.get(ad, "")).strip() == "":
        return None
    return _bool_param(params, ad)


# ---------------------------------------------------------------------------
# Sayımlar
# ---------------------------------------------------------------------------
class StockTakeListCreateView(YoneticiKipiGorunumu):
    """`GET/POST library/stocktakes/` — süzgeçler `status`, `fiscal_year`."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        qs = selectors_sayim.stocktakes(
            status=_choice_param(params, "status", StockTakeStatus.values, "durum"),
            fiscal_year=_int_param(params, "fiscal_year", "Mali yıl"),
        )
        sayfalayici = KatalogSayfalama()
        sayfa = sayfalayici.paginate_queryset(qs, request, view=self)
        gosterilen = list(sayfa) if sayfa is not None else list(qs)
        return sayfalayici.get_paginated_response(
            StockTakeListSerializer(gosterilen, many=True).data
        )

    def post(self, request: Request) -> Response:
        veri = _gecerli(StockTakeWriteSerializer, request.data)
        return _ayrinti(stocktake_service.create_stocktake(**veri), kod=status.HTTP_201_CREATED)


class StockTakeStateView(YoneticiKipiGorunumu):
    """`GET library/stocktakes/state/` — Genel Bakış kartı: canlı sayım ve iki kilidin durumu.

    Kişisiz: sayının durumu, seçenekler ve fiziki ilerleme. İade her zaman açıktır.
    """

    def get(self, request: Request) -> Response:
        canli = selectors_sayim.live_stocktake()
        ozet: dict[str, Any] | None = None
        if canli is not None:
            ilerleme = selectors_sayim.progress(canli)
            ozet = {
                "id": canli.pk,
                "status": canli.status,
                "status_display": canli.get_status_display(),
                "round": canli.round,
                "started_at": canli.started_at,
                "tmy_stop": canli.tmy_stop,
                "service_pause": canli.service_pause,
                "physical_expected": ilerleme["physical_expected"],
                "physical_found": ilerleme["physical_found"],
                "surplus": ilerleme["surplus"],
            }
        return Response(
            {
                "live": ozet,
                "tmy_stop_active": selectors_sayim.tmy_stop_active(),
                "service_pause_active": selectors_sayim.service_pause_active(),
                "returns_open": True,
            }
        )


class StockTakeDetailView(YoneticiKipiGorunumu):
    """`GET/PATCH/DELETE library/stocktakes/<pk>/` — düzenleme ve silme yalnız taslakta."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(StockTakeDetailSerializer(_sayim(pk)).data)

    def patch(self, request: Request, pk: int) -> Response:
        veri = _gecerli(StockTakeWriteSerializer, request.data, partial=True)
        return _ayrinti(stocktake_service.update_stocktake(_sayim(pk), **veri))

    def delete(self, request: Request, pk: int) -> Response:
        stocktake_service.delete_stocktake(_sayim(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class StockTakeStartView(YoneticiKipiGorunumu):
    """Başlat — anlık görüntü alınır, seçilen kilitler başlar."""

    def post(self, request: Request, pk: int) -> Response:
        return _ayrinti(stocktake_service.start_stocktake(_sayim(pk)))


class StockTakeScanView(APIView):
    """Okut — `{barcode}` ya da okuyucu kuyruğu `{barcodes}` (en çok 200); her kod ayrı sonuç.

    GÖREVLİ KİPİNDE AÇIK (madde 24): yanıt `{results: [{code, message, barcode,
    barcode_display, work_title}]}` — kalem ve özet YOK. Kip, ara katmanla aynı süreç içi
    nesneden okunur; kip arada yöneticiden görevliye inmişse yanıt daralmış döner (güvenli
    yön).
    """

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(StockTakeScanSerializer, request.data)
        sayim = _sayim(pk)
        sonuclar = stocktake_service.scan_many(sayim, veri["values"])
        if KIP.gorevli_mi():
            return Response({"results": [staff_scan_result(sonuc) for sonuc in sonuclar]})
        return Response(
            {
                "results": [
                    {
                        "code": sonuc.code,
                        "message": sonuc.message,
                        "barcode": sonuc.barcode,
                        "item": (
                            StockTakeItemSerializer(sonuc.item).data
                            if sonuc.item is not None
                            else None
                        ),
                    }
                    for sonuc in sonuclar
                ],
                "summary": selectors_sayim.summary(sayim),
            }
        )


class StockTakeItemsView(YoneticiKipiGorunumu):
    """`GET …/items/` — süzgeçler `result`, `basis`, `outcome`, `section`, `class_section`,
    `surplus`, `damage`, `undecided` (kararı bekleyen sayım fazlası), `q` (eser adı ya da
    barkod). Sayfalı; Türkçe sıralı."""

    def get(self, request: Request, pk: int) -> Response:
        params = request.query_params
        qs = selectors_sayim.items(
            _sayim(pk),
            result=_choice_param(params, "result", StockTakeResult.values, "sonuç"),
            basis=_choice_param(params, "basis", CountBasis.values, "sayım biçimi"),
            outcome=_choice_param(params, "outcome", StockTakeOutcome.values, "onay sonucu"),
            section_id=_int_param(params, "section", "Bölüm"),
            class_section_id=_int_param(params, "class_section", "Sınıf kitaplığı"),
            surplus=_istege_bagli_bool(params, "surplus"),
            damage=_istege_bagli_bool(params, "damage"),
            undecided=_istege_bagli_bool(params, "undecided"),
            q=str(params.get("q", "")),
        )
        sayfalayici = KatalogSayfalama()
        sayfa = sayfalayici.paginate_queryset(qs, request, view=self)
        gosterilen = list(sayfa) if sayfa is not None else list(qs)
        return sayfalayici.get_paginated_response(
            StockTakeItemSerializer(gosterilen, many=True).data
        )


class StockTakeSurplusView(YoneticiKipiGorunumu):
    """`POST …/surplus/` — etiketsiz ya da okutulamayan kitabı sayım fazlası olarak yazar."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(StockTakeSurplusCreateSerializer, request.data)
        kalem = stocktake_service.add_surplus(_sayim(pk), note=veri["note"], work=veri["work"])
        return Response(StockTakeItemSerializer(kalem).data, status=status.HTTP_201_CREATED)


class StockTakeItemDetailView(YoneticiKipiGorunumu):
    """`PATCH/DELETE …/items/<item_pk>/` — yalnız sayım fazlası düzenlenir ya da çıkarılır."""

    def patch(self, request: Request, pk: int, item_pk: int) -> Response:
        veri = _gecerli(StockTakeSurplusUpdateSerializer, request.data, partial=True)
        kalem = stocktake_service.update_surplus(_kalem(pk, item_pk), **veri)
        return Response(StockTakeItemSerializer(_kalem(pk, kalem.pk)).data)

    def delete(self, request: Request, pk: int, item_pk: int) -> Response:
        stocktake_service.remove_surplus(_kalem(pk, item_pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class StockTakeProgressView(YoneticiKipiGorunumu):
    """`GET …/progress/` — bölüm bölüm ve sınıf kitaplığı sınıf kitaplığı ilerleme (kişisiz)."""

    def get(self, request: Request, pk: int) -> Response:
        return Response(selectors_sayim.progress(_sayim(pk)))


class StockTakeCompleteView(YoneticiKipiGorunumu):
    """Tamamla — ilk turda noksan varsa ikinci sayıma (TMY 32/6) geçilir."""

    def post(self, request: Request, pk: int) -> Response:
        sonuc = stocktake_service.complete_stocktake(_sayim(pk))
        return Response(
            {
                "second_round": sonuc.second_round,
                "missing": sonuc.missing,
                "stocktake": StockTakeDetailSerializer(_sayim(pk)).data,
            }
        )


class StockTakeApproveView(YoneticiKipiGorunumu):
    """Onay — harcama yetkilisi (ad şifreli); noksan 32/7, hasar 27/1, fazla TMY 17."""

    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(StockTakeApproveSerializer, request.data)
        sonuc = stocktake_service.approve_stocktake(
            _sayim(pk),
            approved_by_name=veri["approved_by_name"],
            approved_on=veri["approved_on"],
            not_approved=veri["not_approved"],
        )
        return Response(
            {
                "written_off": sonuc.written_off,
                "damage_written_off": sonuc.damage_written_off,
                "not_approved": sonuc.not_approved,
                "state_changed": sonuc.state_changed,
                "reconciled": sonuc.reconciled,
                "surplus_entered": sonuc.surplus_entered,
                "surplus_excluded": sonuc.surplus_excluded,
                "stocktake": StockTakeDetailSerializer(_sayim(pk)).data,
            }
        )


class StockTakeCancelView(YoneticiKipiGorunumu):
    def post(self, request: Request, pk: int) -> Response:
        veri = _gecerli(StockTakeCancelSerializer, request.data)
        return _ayrinti(stocktake_service.cancel_stocktake(_sayim(pk), reason=veri["reason"]))


class StockTakeTmy341View(YoneticiKipiGorunumu):
    """`GET …/tmy-34-1/?fiscal_year=` — TMY 34/1 büyüklükleri (E10 eki; cetvel TKYS'dedir)."""

    def get(self, request: Request, pk: int) -> Response:
        yil = _int_param(request.query_params, "fiscal_year", "Mali yıl")
        if yil is not None and not 2000 <= yil <= 2999:
            raise serializers.ValidationError(
                {"fiscal_year": "Mali yıl dört haneli bir yıl olmalıdır."}
            )
        return Response(selectors_sayim.tmy_34_1(_sayim(pk), fiscal_year=yil))
