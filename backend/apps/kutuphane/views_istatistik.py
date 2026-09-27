"""İstatistik, Md. 7 bilgi kartı, çok okunanlar ve E12/E20 uçları — İNCE, YALNIZ yönetici kipi (F10).

| Uç | Ad | İş |
|---|---|---|
| `GET library/statistics/?school_year=&start=&end=` | `library-statistics` | Kişisiz, k eşikli istatistik (koleksiyon, edinim, dolaşım, teslim, kayıp/hasar, ayıklama) |
| `GET library/dashboard/statistics/` | `library-dashboard-statistics` | Genel Bakış: Md. 7/1 bilgi kartı + çok okunanlar özeti (sayısız) |
| `GET library/popular/?window_type=&window=` | `library-popular` | Çok okunanlar: pencere listeleri ve seçilen pencerenin sırası (sayısız) |
| `POST library/popular/refresh/` | `library-popular-refresh` | Çok okunanları şimdi yeniden hesapla (gün değişimi kapısının işiyle aynı) |
| `GET library/popular/poster/?window=` | `library-popular-poster` | Ayın Kitapları afişi (E12) PDF'i |
| `GET library/reading-award/pdf/?school_year=&start=&end=&class_level=&limit=` | `library-reading-award-pdf` | Okuma ödülü iç çıktısı (E20) PDF'i — ADLI, "İç kullanım" |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (varsayılan kapalı — CLAUDE.md §2-4) ve
hepsi `YoneticiKipiGorunumu`'dur (ara katmana ek savunma: görevli kipinde görünüm de
403 `kip_yetkisiz` verir). E20 seçicisi ayrıca kendisi de yönetici kipi ister. PDF
yanıtları `Cache-Control: no-store` taşır; indirme adında kişi adı YOKTUR. Uç yolunda
ve sorgu dizesinde kişisel veri yoktur (tarih, sınıf düzeyi, pencere). Hiçbir uç
kayıt yazmaz; yalnız "yeniden hesapla" `kd_katalog_populer`'i yazar (kişisiz).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from io import BytesIO

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane import (
    ayin_kitaplari_belgesi,
    okuma_odulu_belgesi,
    selectors_istatistik,
    selectors_okuma_odulu,
    selectors_populer,
)
from apps.kutuphane.models import PopulerPencereTuru
from apps.kutuphane.services import populer
from apps.kutuphane.views import _choice_param, _int_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.okul.models import SchoolYear

PDF_CONTENT_TYPE = "application/pdf"
PENCERE_YOK = "Seçilen dönem ya da ay için çok okunanlar listesi yok."


class Bakimda(APIException):
    """Geri yükleme sürüyor — 503 `bakimda` (çok okunanlar şimdi hesaplanamaz)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "bakimda"
    default_detail = "Geri yükleme sürüyor; çok okunanlar şimdi hesaplanamaz."


def _pdf(icerik: bytes, dosya_adi: str) -> FileResponse:
    yanit = FileResponse(
        BytesIO(icerik), as_attachment=False, filename=dosya_adi, content_type=PDF_CONTENT_TYPE
    )
    yanit["Cache-Control"] = "no-store"
    return yanit


def _tarih_param(params: Mapping[str, str], ad: str, etiket: str) -> date | None:
    ham = str(params.get(ad, "")).strip()
    if not ham:
        return None
    try:
        return date.fromisoformat(ham)
    except ValueError as exc:
        raise serializers.ValidationError({ad: f"{etiket} geçerli bir tarih olmalıdır."}) from exc


def _donem(params: Mapping[str, str]) -> tuple[date, date]:
    """Sorgu dizesinden dönem: `start`+`end`, `school_year` ya da etkin ders yılı."""
    yil_id = _int_param(params, "school_year", "Ders yılı")
    yil = get_object_or_404(SchoolYear, pk=yil_id) if yil_id is not None else None
    return selectors_istatistik.istatistik_donemi(
        school_year=yil,
        bas=_tarih_param(params, "start", "Başlangıç tarihi"),
        son=_tarih_param(params, "end", "Bitiş tarihi"),
    )


# ---------------------------------------------------------------------------
# İstatistik ve Genel Bakış
# ---------------------------------------------------------------------------
class StatisticsView(YoneticiKipiGorunumu):
    """`GET library/statistics/?school_year=&start=&end=` — kişisiz, k eşikli istatistik."""

    def get(self, request: Request) -> Response:
        bas, son = _donem(request.query_params)
        return Response(selectors_istatistik.istatistik(bas, son))


class DashboardStatisticsView(YoneticiKipiGorunumu):
    """`GET library/dashboard/statistics/` — Md. 7/1 bilgi kartı ve çok okunanlar özeti."""

    def get(self, request: Request) -> Response:
        return Response(
            {
                "book_threshold": selectors_istatistik.kitap_esigi(),
                "popular": selectors_populer.pano_ozeti(),
            }
        )


# ---------------------------------------------------------------------------
# Çok okunanlar ve E12
# ---------------------------------------------------------------------------
class PopularView(YoneticiKipiGorunumu):
    """`GET library/popular/` — pencere listeleri ve son pencereler; `?window_type=&window=`
    verilirse o pencerenin sırası (bulunamazsa 404)."""

    def get(self, request: Request) -> Response:
        params = request.query_params
        tur = _choice_param(params, "window_type", PopulerPencereTuru.values, "liste türü")
        pencere = str(params.get("window", "")).strip()
        if not tur and not pencere:
            return Response(selectors_populer.raporlar_ozeti())
        if not tur or not pencere:
            raise serializers.ValidationError(
                {"window": "Liste türünü (dönem ya da ay) ve dönemi ya da ayı birlikte seçin."}
            )
        ozet = selectors_populer.pencere_ozeti(tur, pencere)
        if ozet is None:
            raise NotFound(PENCERE_YOK)
        return Response(ozet)


class PopularRefreshView(YoneticiKipiGorunumu):
    """`POST library/popular/refresh/` — kapıdaki günlük işle aynı hesap; kişisiz özet döner."""

    def post(self, request: Request) -> Response:
        try:
            ozet = populer.yeniden_hesapla(timezone.localdate())
        except populer.BakimSuruyor as exc:
            raise Bakimda(str(exc)) from exc
        return Response(ozet)


class PopularPosterView(YoneticiKipiGorunumu):
    """`GET library/popular/poster/?window=2026-09` — Ayın Kitapları afişi (verilmezse son ay)."""

    def get(self, request: Request) -> FileResponse:
        pencere = str(request.query_params.get("window", "")).strip() or (
            selectors_populer.son_pencere(PopulerPencereTuru.AY) or ""
        )
        return _pdf(
            ayin_kitaplari_belgesi.afis_pdf(pencere),
            ayin_kitaplari_belgesi.belge_dosya_adi(pencere),
        )


# ---------------------------------------------------------------------------
# E20
# ---------------------------------------------------------------------------
class ReadingAwardPdfView(YoneticiKipiGorunumu):
    """`GET library/reading-award/pdf/` — okuma ödülü iç çıktısı (ADLI; yalnız yönetici kipi).

    `?school_year=&start=&end=` dönem (istatistikle aynı kural), `?class_level=`
    kapsam, `?limit=` sıra sınırı (1-50, varsayılan 10).
    """

    def get(self, request: Request) -> FileResponse:
        params = request.query_params
        bas, son = _donem(params)
        limit = _int_param(params, "limit", "Sıra sınırı")
        belge = okuma_odulu_belgesi.ic_cikti_pdf(
            bas,
            son,
            class_level=_int_param(params, "class_level", "Sınıf"),
            sira_sayisi=limit if limit is not None else selectors_okuma_odulu.VARSAYILAN_SIRA,
        )
        return _pdf(belge, okuma_odulu_belgesi.belge_dosya_adi())
