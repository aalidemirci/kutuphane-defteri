"""İlişik listesi, yıl akışları ve F7 evrak uçları — İNCE görünümler, YALNIZ yönetici kipi.

| Uç | Ad | İş |
|---|---|---|
| `GET library/clearance/` | `library-clearance` | İlişik listesi (OYS adı korunur): açık işi olanlar (`state=open`), olmayanlar (`clear`) ya da hepsi; son sınıflar ve ayrılanlar önce; sayfalı |
| `GET library/clearance/pdf/` | `library-clearance-pdf` | İlişik listesi PDF'i (E5; dipnotlu, kaynak adı yok) |
| `GET library/clearance/sections/` | `library-clearance-sections` | Açık teslimi olan şubeler (sınıf kitaplığı — kişisiz) |
| `POST library/clearance/certificates/` | `library-clearance-certificate-pdf` | "Kütüphaneden ilişiği yoktur" belgesi (E5; kişi başına bir sayfa) |
| `POST library/year-end/slips/` | `library-year-end-slip-pdf` | Yıl sonu iade hatırlatma pusulası (E4 biçimi; bütün açık ödünçler) |
| `GET library/year-flows/` | `library-year-flows` | Yıl sonu ve yıl başı akışlarının durum özeti (kişisiz sayılar) |
| `GET library/loss-damage-cases/<pk>/pdf/` | `library-loss-damage-case-pdf` | Kayıp/hasar tutanağı (E6) |
| `GET library/deliveries/pdf/` | `library-delivery-pdf` | Teslim listesi (E15) — belge no, şube ya da öğretmen |
| `POST library/deliveries/take-back-report/` | `library-delivery-take-back-report` | Geri alma dökümü (E15) |

Hiçbiri görevli kipi izin listesinde DEĞİLDİR (§4.4: "ilişik", "kayıp dosyaları",
"raporlar" kapalı; varsayılan kapalı — CLAUDE.md §2-4). Ara katman keser; görünüm
bir kez daha keser (`YoneticiKipiGorunumu`). Hiçbiri kayıt YAZMAZ, bu yüzden
`RequiresAdminPassword` taşımaz (`apps/okul/tests/test_kisi_yazan_uclar.py`).
PDF yanıtları `Cache-Control: no-store` taşır; indirme adında kişi adı YOKTUR.
"""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from typing import Any, cast

from django.http import FileResponse, Http404
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import dolasim_belgeleri, ilisik_belgeleri, selectors_teslim
from apps.kutuphane import selectors_ilisik as ilisik
from apps.kutuphane import teslim_belgeleri as teslim
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.serializers_ilisik import (
    CertificateRequestSerializer,
    ClearanceQuerySerializer,
    ClearanceRowSerializer,
    DeliveryListQuerySerializer,
    SectionDeliveryRowSerializer,
    TakeBackReportRequestSerializer,
    YearEndSlipRequestSerializer,
)
from apps.kutuphane.services import yil_akislari
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors

PDF_CONTENT_TYPE = "application/pdf"
TOO_MANY_SLIPS_MESSAGE = (
    f"Tek seferde en çok {dolasim_belgeleri.MAX_SLIPS_PER_DOCUMENT} kişinin pusulası "
    "basılabilir; şube şube basın."
)


def _pdf(icerik: bytes, dosya_adi: str) -> FileResponse:
    yanit = FileResponse(
        BytesIO(icerik), as_attachment=False, filename=dosya_adi, content_type=PDF_CONTENT_TYPE
    )
    yanit["Cache-Control"] = "no-store"
    return yanit


class YoneticiKipiGorunumu(APIView):
    """Savunma derinliği: görevli kipinde görünüm de 403 `kip_yetkisiz` verir."""

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        require_admin_mode()


def _filtre(veri: Any) -> ilisik.ClearanceFilter:
    sorgu = ClearanceQuerySerializer(data=veri)
    sorgu.is_valid(raise_exception=True)
    return sorgu.filtre()


# ---------------------------------------------------------------------------
# İlişik listesi ve belgeler (E5)
# ---------------------------------------------------------------------------
class ClearanceListView(YoneticiKipiGorunumu):
    """`GET library/clearance/?state=&group=&person_type=&obligation=&class_level=&class_section=&search=`."""

    def get(self, request: Request) -> Response:
        rows = ilisik.clearance_rows(_filtre(request.query_params))
        sayfalayici = KatalogSayfalama()
        sayfa = sayfalayici.paginate_queryset(cast("Any", rows), request, view=self)
        gosterilen = list(sayfa) if sayfa is not None else rows
        return sayfalayici.get_paginated_response(
            ClearanceRowSerializer(gosterilen, many=True).data
        )


class ClearancePdfView(YoneticiKipiGorunumu):
    """`GET library/clearance/pdf/?group=&class_level=&class_section=` — yalnız açık işi olanlar.

    Şube teslimleri tablosu kapsamda kişi sınıfı süzgeci yokken eklenir (son sınıf
    kapsamında yalnız son sınıf şubeleri; ayrılanlar kapsamında hiç).
    """

    def get(self, request: Request) -> FileResponse:
        filtre = _filtre(request.query_params)
        filtre = ilisik.ClearanceFilter(
            state=ilisik.STATE_OPEN,
            group=filtre.group,
            class_level=filtre.class_level,
            class_section=filtre.class_section,
            person_type=filtre.person_type,
        )
        rows = ilisik.clearance_rows(filtre)
        subeler: list[ilisik.SectionDeliveryRow] = []
        if (
            filtre.class_level is None
            and not filtre.sube
            and filtre.person_type != "student"
            and filtre.group in ("", ilisik.GROUP_GRADUATING, ilisik.GROUP_PRIORITY)
        ):
            subeler = ilisik.section_delivery_rows(graduating_only=bool(filtre.group))
        pdf = ilisik_belgeleri.clearance_list_pdf(rows, subeler, filtre=filtre)
        return _pdf(
            pdf,
            dolasim_belgeleri.belge_dosya_adi(
                ilisik_belgeleri.LISTE_ADI, kapsam=ilisik_belgeleri.scope_slug(filtre)
            ),
        )


class ClearanceSectionsView(YoneticiKipiGorunumu):
    """`GET library/clearance/sections/?graduating=1` — açık teslimi olan şubeler (kişisiz)."""

    def get(self, request: Request) -> Response:
        yalniz_son = str(request.query_params.get("graduating", "")).strip() in ("1", "true")
        satirlar = ilisik.section_delivery_rows(graduating_only=yalniz_son)
        return Response(SectionDeliveryRowSerializer(satirlar, many=True).data)


class ClearanceCertificatePdfView(YoneticiKipiGorunumu):
    """`POST library/clearance/certificates/` `{student_ids?, personnel_ids?}` — E5 belgesi.

    Seçilenlerden biri bile açık işliyse HİÇBİR belge basılmaz (400; kişi adı yok).
    """

    def post(self, request: Request) -> FileResponse:
        istek = CertificateRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        rows, eksik = ilisik.persons_for_certificate(
            student_ids=istek.validated_data["student_ids"],
            personnel_ids=istek.validated_data["personnel_ids"],
        )
        ilisik_belgeleri.ensure_certifiable(rows, eksik)
        return _pdf(
            ilisik_belgeleri.certificate_pdf(rows),
            dolasim_belgeleri.belge_dosya_adi(ilisik_belgeleri.BELGE_ADI),
        )


# ---------------------------------------------------------------------------
# Yıl sonu pusulası ve yıl akışları
# ---------------------------------------------------------------------------
class YearEndSlipPdfView(YoneticiKipiGorunumu):
    """`POST library/year-end/slips/` `{student_ids?, personnel_ids?, group?, class_level?,
    class_section?, return_by?}` — açık ödüncü olan kişilerin yıl sonu pusulaları.

    Kişi seçilirse yalnız onlar; seçilmezse kapsamdaki herkes (son sınıflar önce).
    """

    def post(self, request: Request) -> FileResponse:
        istek = YearEndSlipRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        veri = istek.validated_data
        seviye = veri.get("class_level")
        rows = ilisik.clearance_rows(
            ilisik.ClearanceFilter(
                state=ilisik.STATE_OPEN,
                group=str(veri.get("group") or ""),
                class_level=int(seviye) if seviye is not None else None,
                class_section=str(veri.get("class_section") or ""),
                obligation=ilisik.OBLIGATION_COLLECT,
            )
        )
        ogrenci = set(veri["student_ids"])
        personel = set(veri["personnel_ids"])
        if ogrenci or personel:
            rows = [
                r
                for r in rows
                if (r.is_student and r.person_id in ogrenci)
                or (not r.is_student and r.person_id in personel)
            ]
        gruplar = ilisik_belgeleri.collection_groups(rows)
        if len(gruplar) > dolasim_belgeleri.MAX_SLIPS_PER_DOCUMENT:
            raise serializers.ValidationError(TOO_MANY_SLIPS_MESSAGE)
        pdf = ilisik_belgeleri.year_end_slips_pdf(gruplar, return_by=veri.get("return_by"))
        return _pdf(
            pdf,
            dolasim_belgeleri.belge_dosya_adi(
                dolasim_belgeleri.PUSULA_ADI, kapsam=(ilisik_belgeleri.YIL_SONU_PUSULA_KAPSAMI,)
            ),
        )


def _yil_sonu(ozet: yil_akislari.YearEndSummary) -> dict[str, Any]:
    return {
        "in_window": ozet.in_window,
        "school_year": ozet.school_year,
        "graduating_level": ozet.graduating_level,
        "last_loan_date": ozet.last_loan_date,
        "last_loan_date_graduating": ozet.last_loan_date_graduating,
        "last_loan_date_stale": ozet.last_loan_date_stale,
        "last_loan_date_graduating_stale": ozet.last_loan_date_graduating_stale,
        "graduating_students": ozet.graduating_students,
        "graduating_clear_students": ozet.graduating_clear_students,
        "counts": asdict(ozet.counts),
        "steps": ozet.steps,
    }


def _yil_basi(ozet: yil_akislari.YearStartSummary) -> dict[str, Any]:
    return {
        "in_window": ozet.in_window,
        "school_year": ozet.school_year,
        "school_year_ready": ozet.school_year_ready,
        "kademe_missing": ozet.kademe_missing,
        "last_student_import": ozet.last_student_import,
        "last_personnel_import": ozet.last_personnel_import,
        "student_import_fresh": ozet.student_import_fresh,
        "personnel_import_fresh": ozet.personnel_import_fresh,
        "leave_pool_students": ozet.leave_pool_students,
        "leave_pool_personnel": ozet.leave_pool_personnel,
        "school_break_count": ozet.school_break_count,
        "holidays_missing_years": list(ozet.holidays_missing_years),
        "stale_last_loan_dates": ozet.stale_last_loan_dates,
        "steps": ozet.steps,
    }


#: `GET library/year-flows/` yanıtının üst ve alt alan listeleri (anlık görüntü testi).
YEAR_FLOWS_FIELDS = ("today", "year_end", "year_start")


class YearFlowsView(YoneticiKipiGorunumu):
    """`GET library/year-flows/` — yıl sonu ve yıl başı adımlarının durumu (kişisiz sayılar)."""

    def get(self, request: Request) -> Response:
        sonu = yil_akislari.year_end_summary()
        basi = yil_akislari.year_start_summary(on=sonu.today)
        return Response(
            {"today": sonu.today, "year_end": _yil_sonu(sonu), "year_start": _yil_basi(basi)}
        )


# ---------------------------------------------------------------------------
# E6 ve E15
# ---------------------------------------------------------------------------
class LossDamageCaseReportView(YoneticiKipiGorunumu):
    """`GET library/loss-damage-cases/<pk>/pdf/` — kayıp/hasar tutanağı (E6)."""

    def get(self, request: Request, pk: int) -> FileResponse:
        dosya = selectors_teslim.get_case(pk)
        if dosya is None:
            raise Http404
        return _pdf(
            teslim.case_report_pdf(dosya),
            dolasim_belgeleri.belge_dosya_adi(
                teslim.TUTANAK_ADI,
                kapsam=(barcode_module.format_barcode(dosya.copy.barcode),),
            ),
        )


class DeliveryListPdfView(YoneticiKipiGorunumu):
    """`GET library/deliveries/pdf/?document_no=|section=|personnel=` — teslim listesi (E15)."""

    def get(self, request: Request) -> FileResponse:
        sorgu = DeliveryListQuerySerializer(data=request.query_params)
        sorgu.is_valid(raise_exception=True)
        veri = sorgu.validated_data
        belge = str(veri.get("document_no") or "")
        sube = None
        ogretmen = None
        kapsam: tuple[str, ...] = (belge,) if belge else ()
        if not belge and veri.get("section") is not None:
            sube = okul_selectors.get_class_section(int(veri["section"]))
            if sube is None:
                raise serializers.ValidationError({"section": "Şube bulunamadı."})
            kapsam = (sube.class_label,)
        elif not belge and veri.get("personnel") is not None:
            ogretmen = okul_selectors.get_personnel(int(veri["personnel"]))
            if ogretmen is None:
                raise serializers.ValidationError({"personnel": "Öğretmen bulunamadı."})
        satirlar = teslim.delivery_list_rows(document_no=belge, section=sube, personnel=ogretmen)
        return _pdf(
            teslim.delivery_list_pdf(satirlar),
            dolasim_belgeleri.belge_dosya_adi(teslim.TESLIM_LISTESI_ADI, kapsam=kapsam),
        )


class DeliveryTakeBackReportView(YoneticiKipiGorunumu):
    """`POST library/deliveries/take-back-report/` `{delivery_ids}` ya da `{document_no}` (E15)."""

    def post(self, request: Request) -> FileResponse:
        istek = TakeBackReportRequestSerializer(data=request.data)
        istek.is_valid(raise_exception=True)
        belge = str(istek.validated_data.get("document_no") or "")
        satirlar = teslim.take_back_rows(
            delivery_ids=istek.validated_data["delivery_ids"], document_no=belge
        )
        return _pdf(
            teslim.take_back_pdf(satirlar, document_no=belge),
            dolasim_belgeleri.belge_dosya_adi(
                teslim.GERI_ALMA_ADI, kapsam=(belge,) if belge else ()
            ),
        )
