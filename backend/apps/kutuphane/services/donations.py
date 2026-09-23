"""Bağış ön kaydı ve komisyon kararından sonra toplu kataloglama (SU-23, Md. 10/3).

Okula gelen bağış kataloğa HEMEN girmez. Md. 10/3 bağışın Seçim ve Ayıklama
Komisyonu değerlendirmesinden geçmesini ister; kitapları önceden kayda almak iki
yanlış doğurur: komisyon reddederse kayıttan düşme işlemi gerekir, kabul ederse
edinim tarihi kararın tarihiyle tutmaz. Bu yüzden gelen kitaplar önce ön kayda
yazılır (nüsha açılmaz); karar girilince kabul edilen kalemler TEK İŞLEMDE
(`transaction.atomic`) kataloglanır, reddedilenler gerekçesiyle işaretlenir ve
kayıtta kalır — okul bağışçıya ne olduğunu söyleyebilsin.

Karar TÜRÜ denetlenir (D7): bağış ancak "bağış değerlendirme" kararıyla
kataloglanır.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    DonationIntake,
    DonationIntakeItem,
    DonationIntakeStatus,
    DonationItemDecision,
    Section,
    Work,
)
from apps.kutuphane.services import catalog, commissions


@transaction.atomic
def create_intake(*, items: Iterable[Mapping[str, Any]] = (), **fields: Any) -> DonationIntake:
    """Bağış ön kaydı açar; kalemler aynı işlemde yazılır."""
    intake = DonationIntake(**fields)
    intake.full_clean()
    intake.save()
    for item in items:
        add_item(intake, **item)
    return intake


@transaction.atomic
def update_intake(intake: DonationIntake, **fields: Any) -> DonationIntake:
    """Ön kaydın künyesini (bağışçı, geliş tarihi, notlar) günceller.

    Karar işlendikten sonra değiştirilemez: kayıt artık bir edinimin ve
    kataloglanmış eserlerin dayanağıdır.
    """
    _require_pending(intake)
    for name, value in fields.items():
        setattr(intake, name, value)
    intake.full_clean()
    intake.save()
    return intake


@transaction.atomic
def delete_intake(intake: DonationIntake) -> None:
    """Yanlış açılmış ön kaydı (kalemleriyle birlikte) yumuşak siler.

    Kararı işlenmiş ön kayıt SİLİNMEZ: hangi kitabın hangi kararla kütüphaneye
    girdiğinin ve neyin hangi gerekçeyle reddedildiğinin tek kaydıdır — okul
    bağışçıya bunu söyleyebilmelidir. Vazgeçme yolu iptaldir (`cancel_intake`).
    """
    if intake.status == DonationIntakeStatus.DECIDED:
        raise ValidationError(
            {
                "status": (
                    "Kararı işlenmiş bağış ön kaydı silinemez; kayıtta kalır. "
                    "Yanlış girilen bilgileri düzeltin."
                )
            }
        )
    for item in intake.items.all():
        item.delete()
    intake.delete()


@transaction.atomic
def add_item(intake: DonationIntake, **fields: Any) -> DonationIntakeItem:
    """Ön kayda kalem ekler (karar işlendikten sonra eklenemez)."""
    _require_pending(intake)
    item = DonationIntakeItem(intake=intake, **fields)
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def update_item(item: DonationIntakeItem, **fields: Any) -> DonationIntakeItem:
    """Kalemi günceller (karar işlendikten sonra değiştirilemez)."""
    _require_pending(item.intake)
    for name, value in fields.items():
        setattr(item, name, value)
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def remove_item(item: DonationIntakeItem) -> None:
    """Kalemi yumuşak siler (karar işlendikten sonra silinemez)."""
    _require_pending(item.intake)
    item.delete()


def _require_pending(intake: DonationIntake) -> None:
    if intake.status != DonationIntakeStatus.PENDING:
        raise ValidationError(
            {
                "status": (
                    "Bu bağış ön kaydının kararı işlendi; kalemleri değiştirilemez. "
                    "Yeni bir ön kayıt açın."
                )
            }
        )


@transaction.atomic
def cancel_intake(intake: DonationIntake, *, reason: str = "") -> DonationIntake:
    """Ön kaydı iptal eder (bağış geri verildi, liste yanlış girildi vb.)."""
    _require_pending(intake)
    intake.status = DonationIntakeStatus.CANCELLED
    if reason:
        intake.notes = f"{intake.notes}\n{reason}".strip()
    intake.decided_at = timezone.now()
    intake.save(update_fields=["status", "notes", "decided_at", "updated_at"])
    return intake


@transaction.atomic
def apply_decision(
    intake: DonationIntake,
    *,
    commission_decision: CommissionDecision,
    accepted_ids: Iterable[int] = (),
    rejected: Mapping[int, str] | None = None,
    acquisition_date: Any = None,
    section: Section | None = None,
    unit_price: Any = None,
) -> dict[str, Any]:
    """Komisyon kararını uygular: kabul edilenleri kataloglar, reddedilenleri işaretler.

    Her kalem TAM OLARAK bir kez kararlanmalıdır (kabul ya da ret); eksik ya da
    fazla karar bütün işlemi reddeder — yarım kararlanmış bir liste, hangi
    kitabın kayda girdiği sorusunu cevapsız bırakır. Ret gerekçesi zorunludur.

    Döner: `{"acquisition", "works", "copies", "accepted", "rejected"}`.
    """
    _require_pending(intake)
    commissions.require_decision_type(commission_decision, CommissionDecisionType.DONATION_REVIEW)

    ret_kararlari: dict[int, str] = {int(k): str(v or "") for k, v in (rejected or {}).items()}
    kabul_edilenler = [int(pk) for pk in accepted_ids]
    _ensure_full_coverage(intake, kabul_edilenler, ret_kararlari)

    kalemler = {item.pk: item for item in intake.items.all()}
    acquisition: Acquisition | None = None
    works: list[Work] = []
    copies: list[Copy] = []
    if kabul_edilenler:
        # Edinim YALNIZ kabul varsa açılır: hepsi reddedilmiş bir bağışın
        # kütüphaneye girmiş bir partisi yoktur.
        acquisition = catalog.create_acquisition(
            method=AcquisitionMethod.DONATION,
            date=acquisition_date or intake.received_date,
            source_note=intake.donor_name,
            commission_decision=commission_decision,
            unit_price=unit_price,
            notes=f"Bağış ön kaydı #{intake.pk}",
        )
        for pk in kabul_edilenler:
            item = kalemler[pk]
            work = catalog.create_work(
                title=item.title,
                authors=item.authors,
                publisher=item.publisher,
                publish_year=item.publish_year,
                isbn=item.isbn,
                section=section,
            )
            copies.extend(
                catalog.create_copies(
                    work=work, acquisition=acquisition, count=item.copies, section=section
                )
            )
            item.decision = DonationItemDecision.ACCEPTED
            item.work = work
            item.save(update_fields=["decision", "work", "updated_at"])
            works.append(work)

    for pk, gerekce in ret_kararlari.items():
        item = kalemler[pk]
        item.decision = DonationItemDecision.REJECTED
        item.reject_reason = gerekce
        item.save(update_fields=["decision", "reject_reason", "updated_at"])

    intake.status = DonationIntakeStatus.DECIDED
    intake.commission_decision = commission_decision
    intake.acquisition = acquisition
    intake.decided_at = timezone.now()
    intake.save(
        update_fields=["status", "commission_decision", "acquisition", "decided_at", "updated_at"]
    )
    return {
        "acquisition": acquisition,
        "works": works,
        "copies": copies,
        "accepted": len(kabul_edilenler),
        "rejected": len(ret_kararlari),
    }


def _ensure_full_coverage(
    intake: DonationIntake, accepted: list[int], rejected: dict[int, str]
) -> None:
    """Her kalem tam olarak bir kez kararlanmış mı; gerekçeler dolu mu?"""
    kalem_pkleri = set(intake.items.values_list("pk", flat=True))
    kararlananlar = [*accepted, *rejected]
    yinelenen = len(kararlananlar) != len(set(kararlananlar))
    yabanci = set(kararlananlar) - kalem_pkleri
    eksik = kalem_pkleri - set(kararlananlar)
    if yabanci:
        raise ValidationError(
            {"items": "Karar verilen kalemlerden biri bu bağış ön kaydına ait değil."}
        )
    if yinelenen:
        raise ValidationError(
            {"items": "Bir kalem hem kabul hem ret listesinde ya da iki kez var."}
        )
    if eksik:
        raise ValidationError(
            {"items": f"{len(eksik)} kalem karar bekliyor; her kalem için kabul ya da ret girin."}
        )
    bos_gerekce = [pk for pk, gerekce in rejected.items() if not gerekce.strip()]
    if bos_gerekce:
        raise ValidationError({"rejected": "Reddedilen her kalemin gerekçesi yazılmalıdır."})
