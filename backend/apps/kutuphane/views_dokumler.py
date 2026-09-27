"""F10 dökümleri ve dışa aktarım uçları (D kolu) — İNCE görünümler.

| Uç | Ad | İş |
|---|---|---|
| `GET library/export/` | `library-export` | Dışa aktarım dosyası (XLSX; tasarım §8.4) |
| `GET library/export/member-summary/` | `library-export-member-summary` | Üye özeti — kişisiz sayılar |
| `GET library/reports/documents/` | `library-report-documents` | Dökümler ekranının özeti (sayılar, eksenler, bölümler, yıllar, yıl sonu sayımları) |
| `GET library/reports/catalog-listing/?axis=&section=&kind=pdf\\|xlsx` | `library-report-catalog-listing` | Alfabetik katalog dökümü (E17; PDF bir eksen, XLSX üç eksen; `section=0` bölümü yazılmamış eserler) |
| `GET library/reports/library-register/?year=&kind=pdf\\|xlsx` | `library-report-library-register` | Taşınır Kütüphane Defteri dökümü (E11) |
| `GET library/reports/management-account/<pk>/?kind=pdf\\|xlsx` | `library-report-management-account` | Yönetim hesabı cetveli hazırlığı (E11; yıl sonu sayımı, onaylı) |
| `POST library/reports/person-record/search/` | `library-report-person-record-search` | Kişi dökümü için aday kişiler (okul no ya da ad — GÖVDEDE) |
| `GET library/reports/person-record/<tur>/<pk>/` | `library-report-person-record` | Kişi dökümü (KVKK md. 11; PDF) |

**Hiçbiri görevli kipi izin listesinde DEĞİLDİR** (dökümler ve dışa aktarım yönetici
işidir; varsayılan kapalı — CLAUDE.md §2-4). Ara katman keser; görünüm bir kez daha keser
(`YoneticiKipiGorunumu`); kişi dökümünün servisi de keser (`require_admin_mode`). Hiçbiri
kayıt YAZMAZ, bu yüzden `RequiresAdminPassword` taşımaz (`test_kisi_yazan_uclar.py`
`DIGER_UCLAR`). Dosya yanıtları `Cache-Control: no-store` taşır; indirme adında kişi adı
YOKTUR. Rapor biçimi `?kind=pdf|xlsx` alır (`?format=` DRF içerik müzakeresine ayrılmıştır
— CLAUDE.md §3). Okul no sorgu dizesine yazılmaz: arama POST gövdesiyle yapılır.
"""

from __future__ import annotations

from typing import Any

from django.http import FileResponse, Http404
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.kutuphane import (
    disa_aktarim,
    katalog_dokumu,
    kisi_dokumu,
    selectors_sayim,
    tmy_dokumleri,
)
from apps.kutuphane import dokum_ortak as ortak
from apps.kutuphane.models import Section
from apps.kutuphane.views import _choice_param, _int_param
from apps.kutuphane.views_ilisik import YoneticiKipiGorunumu
from apps.kutuphane.views_komisyon_belgeleri import _dosya

_BICIMLER = (ortak.PDF, ortak.XLSX)


def _bicim(request: Request) -> str:
    return _choice_param(request.query_params, "kind", _BICIMLER, "biçim") or ortak.PDF


def _bolum(request: Request) -> int | None:
    """Bölüm süzgeci: boş = bütün bölümler, `0` = bölümü yazılmamış eserler (E17)."""
    pk = _int_param(request.query_params, "section", "Bölüm")
    if pk == katalog_dokumu.SECTION_NONE:
        return pk
    if pk is not None and not Section.objects.filter(pk=pk).exists():
        raise serializers.ValidationError({"section": "Seçilen bölüm bulunamadı."})
    return pk


class ExportView(YoneticiKipiGorunumu):
    """`GET library/export/` — dışa aktarım dosyası (XLSX). Kişisel veri YOKTUR."""

    def get(self, request: Request) -> FileResponse:
        return _dosya(
            disa_aktarim.build_export_xlsx(), disa_aktarim.export_filename(), bicim=ortak.XLSX
        )


class MemberSummaryView(YoneticiKipiGorunumu):
    """`GET library/export/member-summary/` — üye türüne ve şubeye göre aktif üye sayısı."""

    def get(self, request: Request) -> Response:
        return Response(disa_aktarim.uye_ozeti())


class ReportDocumentsView(YoneticiKipiGorunumu):
    """`GET library/reports/documents/` — Dökümler bölümünün düğmeleri ve seçicileri."""

    def get(self, request: Request) -> Response:
        return Response(
            {
                "export": disa_aktarim.exit_count_summary(),
                "catalog_listing": {
                    **katalog_dokumu.listing_summary(),
                    "axes": [{"value": k, "label": v} for k, v in katalog_dokumu.AXES.items()],
                    "sections": [
                        {"id": b.pk, "name": b.name}
                        for b in Section.objects.order_by("sort_order", "name_sort_key", "pk")
                    ],
                    # Bölümü yazılmamış eser sayısı (seçicide "Bölümü yazılmamış" — id 0).
                    "unsectioned_works": katalog_dokumu.listing_summary(
                        section_id=katalog_dokumu.SECTION_NONE
                    )["works"],
                },
                "library_register": {"years": tmy_dokumleri.register_years()},
                "management_account": {"stocktakes": tmy_dokumleri.year_end_stocktakes()},
            }
        )


class CatalogListingView(YoneticiKipiGorunumu):
    """`GET library/reports/catalog-listing/?axis=title|author|subject&section=&kind=` (E17)."""

    def get(self, request: Request) -> FileResponse:
        bicim = _bicim(request)
        bolum = _bolum(request)
        if bicim == ortak.XLSX:
            icerik = katalog_dokumu.catalog_listing_xlsx(section_id=bolum)
        else:
            eksen = (
                _choice_param(request.query_params, "axis", tuple(katalog_dokumu.AXES), "eksen")
                or katalog_dokumu.AXIS_TITLE
            )
            icerik = katalog_dokumu.catalog_listing_pdf(eksen, section_id=bolum)
        return _dosya(icerik, katalog_dokumu.catalog_listing_filename(bicim), bicim=bicim)


class LibraryRegisterView(YoneticiKipiGorunumu):
    """`GET library/reports/library-register/?year=&kind=` — Taşınır Kütüphane Defteri dökümü."""

    def get(self, request: Request) -> FileResponse:
        bicim = _bicim(request)
        yil = _int_param(request.query_params, "year", "Yıl")
        uret = (
            tmy_dokumleri.library_register_xlsx
            if bicim == ortak.XLSX
            else tmy_dokumleri.library_register_pdf
        )
        return _dosya(uret(year=yil), tmy_dokumleri.library_register_filename(bicim), bicim=bicim)


class ManagementAccountView(YoneticiKipiGorunumu):
    """`GET library/reports/management-account/<pk>/?kind=` — yıl sonu sayımına dayanır."""

    def get(self, request: Request, pk: int) -> FileResponse:
        sayim = selectors_sayim.get_stocktake(pk)
        if sayim is None:
            raise Http404
        bicim = _bicim(request)
        uret = (
            tmy_dokumleri.management_account_xlsx
            if bicim == ortak.XLSX
            else tmy_dokumleri.management_account_pdf
        )
        return _dosya(uret(sayim), tmy_dokumleri.management_account_filename(bicim), bicim=bicim)


class PersonSearchSerializer(serializers.Serializer[dict[str, Any]]):
    school_no = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class PersonRecordSearchView(YoneticiKipiGorunumu):
    """`POST library/reports/person-record/search/` — `{school_no, name}` → aday kişiler.

    Okul no kör indeksle TAM eşleşir; aynı numaralı birden çok kayıt (ayrılan öğrencinin
    numarası yeniden verilmiş olabilir) ayrı aday olarak döner.
    """

    def post(self, request: Request) -> Response:
        govde = PersonSearchSerializer(data=request.data)
        govde.is_valid(raise_exception=True)
        return Response(
            {
                "results": kisi_dokumu.person_candidates(
                    school_no=govde.validated_data["school_no"],
                    name=govde.validated_data["name"],
                )
            }
        )


class PersonRecordView(YoneticiKipiGorunumu):
    """`GET library/reports/person-record/<tur>/<pk>/` — kişi dökümü (PDF)."""

    def get(self, request: Request, tur: str, pk: int) -> FileResponse:
        if tur not in kisi_dokumu.KINDS:
            raise Http404
        return _dosya(
            kisi_dokumu.person_record_pdf(tur, pk),
            kisi_dokumu.person_record_filename(),
            bicim=ortak.PDF,
        )
