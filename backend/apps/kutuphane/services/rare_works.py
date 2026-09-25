"""El yazması ve nadir eserler listesi — Md. 12/2 (F8; D14, E8).

Md. 12/2: "Seçim ve Ayıklama Komisyonu tarafından tespit edilen el yazmaları ve
nadir eserler listesi, Genel Müdürlüğe gönderilir."

KURALLAR (testle kilitli — `tests/test_nadir_eser.py`):

1. Listeye yalnız `Copy.is_rare_or_manuscript` işaretli, canlı ve elde bulunan
   (kayıttan düşülmemiş, devredilmemiş) nüsha girer.
2. Liste bir **komisyon kararına bağlıdır** (D14: OYS'de bağ yoktu). Karar Md.
   12'nin kararıdır ve "Ayıklama" türündedir (D7 — Md. 12 "Bakım, onarım ve
   ayıklama" başlığı altındadır; ayrı bir karar türü açılmadı). Karar hazırlık
   sırasında boş olabilir, gönderimden önce bağlanır (DB kısıtı).
3. Gönderim tarihi (ve varsa gönderme yazısının sayısı) yazılınca liste
   "Genel Müdürlüğe gönderildi" olur ve DEĞİŞMEZ; gönderim tarihi bugünden
   sonra ve komisyon kararından önce olamaz.
4. Gönderilmiş ya da komisyon kararı bağlanmış (komisyonun tespit ettiği) bir
   listede duran nüshanın nadir eser işareti KALDIRILAMAZ
   (`services.catalog.ensure_rare_flag_change`, `update_copy` sorar); listedeki
   nüsha silinemez (`services.catalog.delete_copy`). Nadir eser ayıklanamaz
   (`services.weeding`).
5. Yalnız yönetici kipinde. Liste kişisizdir.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    RareWorksSubmission,
    RareWorksSubmissionItem,
    RareWorksSubmissionStatus,
)
from apps.kutuphane.services import commissions, masa
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors
from apps.okul.models import SchoolYear

logger = logging.getLogger("kutuphane_defteri.kutuphane")

MAX_COPIES_PER_ADD: Final = 500

NO_SCHOOL_YEAR_MESSAGE = "Önce etkin ders yılını tanımlayın (Ayarlar → Ders Yılları)."
SUBMISSION_MISSING_MESSAGE = "Liste bulunamadı."
SENT_LOCKED_MESSAGE = "Genel Müdürlüğe gönderilmiş liste değiştirilemez."
NO_COPIES_MESSAGE = "Eklenecek nüsha seçilmedi."
TOO_MANY_MESSAGE = f"Tek seferde en çok {MAX_COPIES_PER_ADD} nüsha eklenir."
COPY_MISSING_MESSAGE = "Nüsha bulunamadı."
NOT_RARE_MESSAGE = (
    "Nüsha el yazması ya da nadir eser olarak işaretli değil; önce nüsha bilgilerinde işaretleyin."
)
TERMINAL_MESSAGE = "Kayıttan düşülmüş ya da devredilmiş nüsha listeye girmez."
ALREADY_LISTED_MESSAGE = "Nüsha bu listede zaten var."
ITEM_NOT_IN_SUBMISSION_MESSAGE = "Satır bu listeye ait değil."
NO_ITEMS_MESSAGE = "Listede en az bir nüsha olmalıdır."
DECISION_REQUIRED_MESSAGE = (
    "Liste, Seçim ve Ayıklama Komisyonunun kararına bağlıdır (Md. 12/2): önce kararı seçin."
)
SENT_ON_REQUIRED_MESSAGE = "Gönderim tarihini yazın."
SENT_IN_FUTURE_MESSAGE = "Gönderim tarihi bugünden sonra olamaz."
SENT_BEFORE_DECISION_MESSAGE = "Gönderim tarihi komisyon kararının tarihinden önce olamaz."
DOC_NO_TOO_LONG_MESSAGE = "Sayı en çok 40 karakter olabilir."


def _kitap(copy: Copy) -> str:
    return barcode_module.format_barcode(copy.barcode)


def rare_flag_locked(copy: Copy) -> bool:
    """Nüshanın nadir eser işareti kilitli mi? (gönderilmiş ya da kararı bağlanmış
    listede — kural 4; kapı `services.catalog.ensure_rare_flag_change`)."""
    return selectors_ayiklama.decided_rare_items_for_copy(copy.pk).exists()


def _taze(submission: RareWorksSubmission) -> RareWorksSubmission:
    guncel: RareWorksSubmission | None = (
        RareWorksSubmission.objects.select_related("commission_decision")
        .filter(pk=submission.pk)
        .first()
    )
    if guncel is None:
        raise ValidationError(SUBMISSION_MISSING_MESSAGE)
    return guncel


def _taslak(submission: RareWorksSubmission) -> None:
    if submission.status != RareWorksSubmissionStatus.DRAFT:
        raise ValidationError({"status": SENT_LOCKED_MESSAGE})


def _karar(decision: CommissionDecision | None) -> CommissionDecision | None:
    if decision is None:
        return None
    commissions.require_decision_type(decision, CommissionDecisionType.WEEDING)
    return decision


@transaction.atomic
def create_submission(
    *,
    school_year: SchoolYear | None = None,
    commission_decision: CommissionDecision | None = None,
    notes: str = "",
) -> RareWorksSubmission:
    """Hazırlanan liste açar (ders yılı verilmezse etkin yıl; karar sonra da bağlanır)."""
    require_admin_mode()
    yil = school_year if school_year is not None else okul_selectors.active_school_year()
    if yil is None or yil.deleted_at is not None:
        raise ValidationError({"school_year": NO_SCHOOL_YEAR_MESSAGE})
    kayit: RareWorksSubmission = RareWorksSubmission.objects.create(
        school_year=yil, commission_decision=_karar(commission_decision), notes=notes or ""
    )
    return kayit


@transaction.atomic
def update_submission(submission: RareWorksSubmission, **fields: Any) -> RareWorksSubmission:
    """Hazırlanan listenin kararını ve notlarını günceller (gönderilmiş liste değişmez)."""
    require_admin_mode()
    guncel = _taze(submission)
    _taslak(guncel)
    if "commission_decision" in fields:
        guncel.commission_decision = _karar(fields["commission_decision"])
    if "notes" in fields:
        guncel.notes = fields["notes"] or ""
    guncel.save(update_fields=["commission_decision", "notes", "updated_at"])
    return guncel


@transaction.atomic
def delete_submission(submission: RareWorksSubmission) -> None:
    """Hazırlanan listeyi satırlarıyla yumuşak siler (gönderilmiş liste silinmez)."""
    require_admin_mode()
    guncel = _taze(submission)
    _taslak(guncel)
    RareWorksSubmissionItem.objects.filter(submission=guncel).delete()
    guncel.delete()


def _engel(copy: Copy) -> str:
    if copy.deleted_at is not None or copy.work.deleted_at is not None:
        return COPY_MISSING_MESSAGE
    if copy.status in TERMINAL_COPY_STATUSES:
        return TERMINAL_MESSAGE
    if not copy.is_rare_or_manuscript:
        return NOT_RARE_MESSAGE
    return ""


@transaction.atomic
def add_copies(
    submission: RareWorksSubmission,
    *,
    barcodes: Sequence[object] = (),
    copy_ids: Sequence[int] = (),
) -> list[RareWorksSubmissionItem]:
    """Listeye nüsha ekler — TEK işlem; engeller kitap kitap `{"barcodes": [...]}` döner."""
    require_admin_mode()
    guncel = _taze(submission)
    _taslak(guncel)
    toplam = len(barcodes) + len(copy_ids)
    if toplam == 0:
        raise ValidationError({"barcodes": NO_COPIES_MESSAGE})
    if toplam > MAX_COPIES_PER_ADD:
        raise ValidationError({"barcodes": TOO_MANY_MESSAGE})
    nushalar: list[Copy] = []
    gorulen: set[int] = set()
    hatalar: list[str] = []
    for sira, deger in enumerate(barcodes, start=1):
        okutma = masa.kitap_coz(deger, staff=False)
        if okutma.copy is None:
            hatalar.append(f"{sira}. okutma: {okutma.message}")
        elif okutma.copy.pk not in gorulen:
            gorulen.add(okutma.copy.pk)
            nushalar.append(okutma.copy)
    bulunan = {c.pk: c for c in Copy.objects.select_related("work").filter(pk__in=list(copy_ids))}
    for sira, kimlik in enumerate(copy_ids, start=1):
        nusha = bulunan.get(int(kimlik))
        if nusha is None:
            hatalar.append(f"{sira}. seçim: {COPY_MISSING_MESSAGE}")
        elif nusha.pk not in gorulen:
            gorulen.add(nusha.pk)
            nushalar.append(nusha)
    listede = set(
        RareWorksSubmissionItem.objects.filter(submission=guncel).values_list("copy_id", flat=True)
    )
    for nusha in nushalar:
        engel = ALREADY_LISTED_MESSAGE if nusha.pk in listede else _engel(nusha)
        if engel:
            hatalar.append(f"{_kitap(nusha)}: {engel}")
    if hatalar:
        raise ValidationError({"barcodes": hatalar})
    eklenen: list[RareWorksSubmissionItem] = []
    for nusha in nushalar:
        try:
            with transaction.atomic():
                eklenen.append(
                    RareWorksSubmissionItem.objects.create(submission=guncel, copy=nusha)
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"barcodes": [f"{_kitap(nusha)}: {ALREADY_LISTED_MESSAGE}"]}
            ) from exc
    return eklenen


@transaction.atomic
def remove_item(item: RareWorksSubmissionItem) -> None:
    """Satırı yumuşak siler (gönderilmiş listede değil)."""
    require_admin_mode()
    satir: RareWorksSubmissionItem | None = (
        RareWorksSubmissionItem.objects.select_related("submission").filter(pk=item.pk).first()
    )
    if satir is None:
        raise ValidationError({"items": ITEM_NOT_IN_SUBMISSION_MESSAGE})
    _taslak(satir.submission)
    satir.delete()


@transaction.atomic
def send_submission(
    submission: RareWorksSubmission,
    *,
    sent_on: date | None,
    sent_document_no: str = "",
) -> RareWorksSubmission:
    """Genel Müdürlüğe gönderimi kaydeder: hazırlanıyor → gönderildi (kural 2-3)."""
    require_admin_mode()
    guncel = _taze(submission)
    _taslak(guncel)
    satirlar = list(selectors_ayiklama.submission_items(guncel))
    if not satirlar:
        raise ValidationError({"items": NO_ITEMS_MESSAGE})
    karar = guncel.commission_decision
    if karar is None or karar.deleted_at is not None:
        raise ValidationError({"commission_decision": DECISION_REQUIRED_MESSAGE})
    commissions.require_decision_type(karar, CommissionDecisionType.WEEDING)
    if sent_on is None:
        raise ValidationError({"sent_on": SENT_ON_REQUIRED_MESSAGE})
    if sent_on > timezone.localdate():
        raise ValidationError({"sent_on": SENT_IN_FUTURE_MESSAGE})
    if sent_on < karar.decision_date:
        raise ValidationError({"sent_on": SENT_BEFORE_DECISION_MESSAGE})
    sayi = (sent_document_no or "").strip()
    if len(sayi) > 40:
        raise ValidationError({"sent_document_no": DOC_NO_TOO_LONG_MESSAGE})
    hatalar = [
        f"{_kitap(s.copy)}: {engel}"
        for s in satirlar
        if (engel := _engel(Copy.all_objects.select_related("work").get(pk=s.copy_id)))
    ]
    if hatalar:
        raise ValidationError({"items": hatalar})
    guncel.status = RareWorksSubmissionStatus.SENT
    guncel.sent_on = sent_on
    guncel.sent_document_no = sayi
    guncel.save(update_fields=["status", "sent_on", "sent_document_no", "updated_at"])
    logger.info("El yazması ve nadir eserler listesinin gönderimi kaydedildi.")
    return guncel
