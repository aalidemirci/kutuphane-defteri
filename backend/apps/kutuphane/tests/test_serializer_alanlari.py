"""Serializer alan listelerinin anlık görüntüsü (T13).

Program OpenAPI şeması ÜRETMEZ (tasarım §13 T13: drf-spectacular alınmadı, ön
yüz tipleri elle yazılır). Bunun bedeli, alan listesinin sessizce değişmesidir:
eklenen bir alan arayüzün tipleriyle ayrışır, silinen bir alan ekranı boş
bırakır. Bu dosya alan kümelerini SABİTLER — değişiklik bilinçli olur ve ön
yüzün tipleriyle aynı değişiklikte güncellenir.

İkinci bir işi daha var: **hangi alanın yazılabilir olduğunu** sabitler. Kimlik
ve durum alanları (`barcode`, `accession_no`, `status`), türetilmiş alanlar
(`isbn13`, Türkçe anahtarlar) ve karar alanları salt okunurdur; biri yanlışlıkla
yazılabilir hâle gelirse test düşer.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.kutuphane.serializers import (
    AcquisitionSerializer,
    CommissionDecisionSerializer,
    CopyBulkCreateSerializer,
    CopyReadSerializer,
    CopyUpdateSerializer,
    CopyWriteSerializer,
    DonationDecisionSerializer,
    DonationIntakeCreateSerializer,
    DonationIntakeItemSerializer,
    DonationIntakeSerializer,
    LibraryPolicySerializer,
    SectionSerializer,
    WorkSerializer,
)

#: Yanıtta görünen alanlar (okuma yüzeyi).
ALANLAR: dict[str, list[str]] = {
    "LibraryPolicySerializer": [
        "loan_period_days",
        "max_loans_student",
        "max_loans_teacher",
        "max_loans_staff",
        "staff_loans_enabled",
        "staff_loans_decision_date",
        "staff_loans_decision_no",
        "block_loan_if_overdue",
        "shift_due_date_on_school_break",
        "last_loan_date",
        "last_loan_date_graduating",
        "idle_minutes",
        "admin_max_minutes",
        "popular_min_members",
        "retention_years_after_termination",
        "retention_years_returned_loans",
        "retention_years_closed_cases",
        "retention_years_closed_deliveries",
        "updated_at",
    ],
    "SectionSerializer": ["id", "name", "dewey_from", "dewey_to", "description", "sort_order"],
    "WorkSerializer": [
        "id",
        "title",
        "authors",
        "translator",
        "edition",
        "publisher",
        "publish_year",
        "isbn",
        "isbn13",
        "isbn_warning",
        "subjects",
        "classification_code",
        "classification_source",
        "classification_source_display",
        "call_number",
        "resource_type",
        "resource_type_display",
        "language",
        "section",
        "section_name",
        "is_digital",
        "copy_count",
        "available_copy_count",
        "created_at",
    ],
    "CopyReadSerializer": [
        "id",
        "work",
        "work_title",
        "work_authors",
        "call_number",
        "resource_type",
        "acquisition",
        "accession_no",
        "barcode",
        "barcode_display",
        "external_asset_ref",
        "old_register_no",
        "section",
        "section_name",
        "is_reference",
        "is_out_of_print",
        "is_bound_periodical",
        "is_rare_or_manuscript",
        "status",
        "status_display",
        "is_loanable",
        "not_loanable_reason",
        "label_printed_at",
        "label_verified_at",
        "created_at",
    ],
    "CopyWriteSerializer": [
        "id",
        "work",
        "acquisition",
        "section",
        "external_asset_ref",
        "old_register_no",
        "is_reference",
        "is_out_of_print",
        "is_bound_periodical",
        "is_rare_or_manuscript",
        "accession_no",
        "barcode",
        "status",
    ],
    "CommissionDecisionSerializer": [
        "id",
        "decision_type",
        "decision_type_display",
        "decision_date",
        "decision_no",
        "chair_name",
        "chair_title",
        "participants_text",
        "notes",
        "in_use",
        "created_at",
    ],
    "AcquisitionSerializer": [
        "id",
        "method",
        "method_display",
        "date",
        "source_note",
        "unit_price",
        "commission_decision",
        "notes",
        "copy_count",
        "created_at",
    ],
    "DonationIntakeItemSerializer": [
        "id",
        "title",
        "authors",
        "publisher",
        "publish_year",
        "isbn",
        "copies",
        "decision",
        "decision_display",
        "reject_reason",
        "work",
        "work_title",
        "notes",
    ],
    "DonationIntakeSerializer": [
        "id",
        "donor_name",
        "received_date",
        "status",
        "status_display",
        "commission_decision",
        "acquisition",
        "decided_at",
        "notes",
        "items",
        "item_count",
        "created_at",
    ],
    "DonationDecisionSerializer": [
        "commission_decision",
        "accepted_ids",
        "rejected",
        "acquisition_date",
        "section",
        "unit_price",
    ],
}

#: Gövdeden YAZILABİLEN alanlar. Buradaki eksiklik ya da fazlalık davranış
#: değişikliğidir: eksik alan ekranı kilitler, fazla alan kuralı delip geçer.
YAZILABILIR: dict[str, set[str]] = {
    "LibraryPolicySerializer": {
        "max_loans_student",
        "max_loans_teacher",
        "max_loans_staff",
        "staff_loans_enabled",
        "staff_loans_decision_date",
        "staff_loans_decision_no",
        "block_loan_if_overdue",
        "shift_due_date_on_school_break",
        "last_loan_date",
        "last_loan_date_graduating",
        "idle_minutes",
        "admin_max_minutes",
        "popular_min_members",
        "retention_years_after_termination",
        "retention_years_returned_loans",
        "retention_years_closed_cases",
        "retention_years_closed_deliveries",
    },
    "SectionSerializer": {"name", "dewey_from", "dewey_to", "description", "sort_order"},
    "WorkSerializer": {
        "title",
        "authors",
        "translator",
        "edition",
        "publisher",
        "publish_year",
        "isbn",
        "subjects",
        "classification_code",
        "classification_source",
        "call_number",
        "resource_type",
        "language",
        "section",
    },
    "CopyWriteSerializer": {
        "work",
        "acquisition",
        "section",
        "external_asset_ref",
        "old_register_no",
        "is_reference",
        "is_out_of_print",
        "is_bound_periodical",
        "is_rare_or_manuscript",
    },
    "CopyUpdateSerializer": {
        "section",
        "external_asset_ref",
        "old_register_no",
        "is_reference",
        "is_out_of_print",
        "is_bound_periodical",
        "is_rare_or_manuscript",
    },
    "CopyBulkCreateSerializer": {
        "work",
        "acquisition",
        "section",
        "external_asset_ref",
        "old_register_no",
        "is_reference",
        "is_out_of_print",
        "is_bound_periodical",
        "is_rare_or_manuscript",
        "count",
    },
    "CommissionDecisionSerializer": {
        "decision_type",
        "decision_date",
        "decision_no",
        "chair_name",
        "chair_title",
        "participants_text",
        "notes",
    },
    "AcquisitionSerializer": {
        "method",
        "date",
        "source_note",
        "unit_price",
        "commission_decision",
        "notes",
    },
    "DonationIntakeItemSerializer": {
        "title",
        "authors",
        "publisher",
        "publish_year",
        "isbn",
        "copies",
        "notes",
    },
    "DonationIntakeSerializer": {"donor_name", "received_date", "notes"},
    "DonationIntakeCreateSerializer": {"donor_name", "received_date", "notes", "items"},
    "DonationDecisionSerializer": {
        "commission_decision",
        "accepted_ids",
        "rejected",
        "acquisition_date",
        "section",
        "unit_price",
    },
}

# `Any`: DRF stub'ında `ModelSerializer[X]` model türünde değişmezdir (invariant),
# ortak bir üst tür altında toplanamaz — tablo yalnız adları sınıflara bağlar.
SINIFLAR: dict[str, Any] = {
    "LibraryPolicySerializer": LibraryPolicySerializer,
    "SectionSerializer": SectionSerializer,
    "WorkSerializer": WorkSerializer,
    "CopyReadSerializer": CopyReadSerializer,
    "CopyWriteSerializer": CopyWriteSerializer,
    "CopyUpdateSerializer": CopyUpdateSerializer,
    "CopyBulkCreateSerializer": CopyBulkCreateSerializer,
    "CommissionDecisionSerializer": CommissionDecisionSerializer,
    "AcquisitionSerializer": AcquisitionSerializer,
    "DonationIntakeItemSerializer": DonationIntakeItemSerializer,
    "DonationIntakeSerializer": DonationIntakeSerializer,
    "DonationIntakeCreateSerializer": DonationIntakeCreateSerializer,
    "DonationDecisionSerializer": DonationDecisionSerializer,
}


@pytest.mark.parametrize("ad", sorted(ALANLAR))
def test_alan_listesi_anlik_goruntuyle_sabit(ad: str) -> None:
    assert list(SINIFLAR[ad]().fields) == ALANLAR[ad]


@pytest.mark.parametrize("ad", sorted(YAZILABILIR))
def test_yazilabilir_alanlar_anlik_goruntuyle_sabit(ad: str) -> None:
    alanlar = SINIFLAR[ad]().fields
    assert {isim for isim, alan in alanlar.items() if not alan.read_only} == YAZILABILIR[ad]


def test_butun_serializerlar_sinanir() -> None:
    """Yeni bir serializer eklendiyse iki tabloya da yazılsın (sessiz kalmasın)."""
    from apps.kutuphane import serializers as modul

    tanimli = {
        ad
        for ad in dir(modul)
        if ad.endswith("Serializer") and isinstance(getattr(modul, ad), type)
    }
    # `DonationCancelSerializer` tek alanlıdır (`reason`) ve ayrı sınanır.
    assert tanimli - set(SINIFLAR) == {"DonationCancelSerializer"}


def test_iptal_gerekcesi_istege_baglidir() -> None:
    from apps.kutuphane.serializers import DonationCancelSerializer

    alanlar = DonationCancelSerializer().fields
    assert list(alanlar) == ["reason"]
    assert alanlar["reason"].required is False
