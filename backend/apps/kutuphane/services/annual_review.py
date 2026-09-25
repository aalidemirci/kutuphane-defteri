"""Yıl sonu kütüphane raporu — Md. 12/1, Kılavuz 2.4 (F8; E9). KİŞİSEL VERİ YOK.

Rapor ders yılı başına BİR kayıttır (DB kısıtı). Taslakta sayılar her okumada
yeniden hesaplanır (`selectors_yil_raporu.annual_review_stats`); "Raporu
sonlandır" sayıları `stats` alanına DONDURUR — yeniden basılan rapor aynı
sayıları taşır. Sonlandırma geri alınabilir (sunulmadan önce düzeltme için);
geri alınınca sayılar yeniden canlı hesaplanır.

Serbest metin (`findings` — "tespit edilen hususlar") kütüphanecinindir;
program kişi adı içerip içermediğini denetleyemez, yardım metni uyarır.
Sayıların kişisizliği modülün değil seçicinin sözleşmesidir (profil yasağı).

Yalnız yönetici kipinde (§4.4 "raporlar" kapalı).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import selectors_yil_raporu
from apps.kutuphane.models import AnnualLibraryReview
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolYear

logger = logging.getLogger("kutuphane_defteri.kutuphane")

FINDINGS_MAX: Final = 5000
NO_SCHOOL_YEAR_MESSAGE = "Önce etkin ders yılını tanımlayın (Ayarlar → Ders Yılları)."
REVIEW_EXISTS_MESSAGE = "Bu ders yılının raporu zaten var; onu açın."
REVIEW_MISSING_MESSAGE = "Rapor bulunamadı."
FINALIZED_LOCKED_MESSAGE = "Sonlandırılmış rapor değiştirilemez; önce sonlandırmayı geri alın."
NOT_FINALIZED_MESSAGE = "Rapor sonlandırılmamış."
ALREADY_FINALIZED_MESSAGE = "Rapor zaten sonlandırılmış."
DOC_NO_TOO_LONG_MESSAGE = "Sayı en çok 40 karakter olabilir."
FINDINGS_TOO_LONG_MESSAGE = f"Tespit edilen hususlar en çok {FINDINGS_MAX} karakter olabilir."
DATE_IN_FUTURE_MESSAGE = "Tarih bugünden sonra olamaz."


def _taze(review: AnnualLibraryReview) -> AnnualLibraryReview:
    guncel: AnnualLibraryReview | None = (
        AnnualLibraryReview.objects.select_related("school_year").filter(pk=review.pk).first()
    )
    if guncel is None:
        raise ValidationError(REVIEW_MISSING_MESSAGE)
    return guncel


def review_stats(review: AnnualLibraryReview) -> dict[str, Any]:
    """Raporun sayıları: sonlandırılmışsa dondurulmuş hâli, değilse canlı hesap."""
    if review.stats is not None:
        dondurulmus: dict[str, Any] = review.stats
        return dondurulmus
    return selectors_yil_raporu.annual_review_stats(review.school_year)


@transaction.atomic
def create_review(*, school_year: SchoolYear | None = None) -> AnnualLibraryReview:
    """Ders yılının raporunu açar (verilmezse etkin yıl). Yıl başına tek rapor."""
    require_admin_mode()
    yil = school_year if school_year is not None else okul_selectors.active_school_year()
    if yil is None or yil.deleted_at is not None:
        raise ValidationError({"school_year": NO_SCHOOL_YEAR_MESSAGE})
    if AnnualLibraryReview.objects.filter(school_year=yil).exists():
        raise ValidationError({"school_year": REVIEW_EXISTS_MESSAGE})
    try:
        with transaction.atomic():
            rapor: AnnualLibraryReview = AnnualLibraryReview.objects.create(school_year=yil)
    except IntegrityError as exc:
        raise ValidationError({"school_year": REVIEW_EXISTS_MESSAGE}) from exc
    return rapor


#: `update_review`'un yazabildiği alanlar.
EDITABLE_FIELDS: Final[frozenset[str]] = frozenset({"document_date", "document_no", "findings"})


@transaction.atomic
def update_review(review: AnnualLibraryReview, **fields: Any) -> AnnualLibraryReview:
    """Tarih, sayı ve "tespit edilen hususlar"ı günceller (yalnız sonlandırılmamış raporda).

    Yalnız verilen alanlar değişir (`EDITABLE_FIELDS`); `document_date=None` tarihi siler.
    """
    require_admin_mode()
    guncel = _taze(review)
    if guncel.is_finalized:
        raise ValidationError({"status": FINALIZED_LOCKED_MESSAGE})
    bilinmeyen = set(fields) - EDITABLE_FIELDS
    if bilinmeyen:
        raise ValidationError({alan: "Bu alan buradan değiştirilemez." for alan in bilinmeyen})
    if "document_date" in fields:
        tarih = fields["document_date"]
        if tarih is not None and (not isinstance(tarih, date) or tarih > timezone.localdate()):
            raise ValidationError({"document_date": DATE_IN_FUTURE_MESSAGE})
        guncel.document_date = tarih
    if "document_no" in fields:
        sayi = str(fields["document_no"] or "").strip()
        if len(sayi) > 40:
            raise ValidationError({"document_no": DOC_NO_TOO_LONG_MESSAGE})
        guncel.document_no = sayi
    if "findings" in fields:
        metin = str(fields["findings"] or "").strip()
        if len(metin) > FINDINGS_MAX:
            raise ValidationError({"findings": FINDINGS_TOO_LONG_MESSAGE})
        guncel.findings = metin
    guncel.save(update_fields=["document_date", "document_no", "findings", "updated_at"])
    return guncel


@transaction.atomic
def finalize_review(review: AnnualLibraryReview) -> AnnualLibraryReview:
    """Raporu sonlandırır: sayılar o anki hâliyle dondurulur."""
    require_admin_mode()
    guncel = _taze(review)
    if guncel.is_finalized:
        raise ValidationError({"status": ALREADY_FINALIZED_MESSAGE})
    guncel.stats = selectors_yil_raporu.annual_review_stats(guncel.school_year)
    guncel.finalized_at = timezone.now()
    guncel.save(update_fields=["stats", "finalized_at", "updated_at"])
    logger.info("Yıl sonu kütüphane raporu sonlandırıldı.")
    return guncel


@transaction.atomic
def reopen_review(review: AnnualLibraryReview) -> AnnualLibraryReview:
    """Sonlandırmayı geri alır: dondurulmuş sayılar atılır, rapor yeniden düzenlenebilir."""
    require_admin_mode()
    guncel = _taze(review)
    if not guncel.is_finalized:
        raise ValidationError({"status": NOT_FINALIZED_MESSAGE})
    guncel.stats = None
    guncel.finalized_at = None
    guncel.save(update_fields=["stats", "finalized_at", "updated_at"])
    return guncel
