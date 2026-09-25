"""Seçim ve Ayıklama Komisyonu kararı — yazma yolu ve TÜR DENETİMİ (D7).

OYS karar türünü kaydediyor ama kullanırken denetlemiyordu: bir ayıklama kararı
bağış edinimine, bir bağış kararı ayıklama partisine bağlanabiliyordu. Md. 10/3
bağışın komisyon değerlendirmesinden geçmesini ister; o değerlendirme "bağış
değerlendirme" kararıdır. Denetimin tek yeri `require_decision_type`'tır; bağış
akışı (F2) ve ayıklama (F8) aynı kapıdan geçer.

Başkan adı ve katılımcılar ŞİFRELİ alanlardır (§6.3): anahtar bellekte değilken
yazma `KeyMissingError` ile durur (409 `parola_gerekli`).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kutuphane.models import (
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    RareWorksSubmissionStatus,
    WeedingBatchStatus,
)

#: Karar türlerinin kullanıcıya gösterilen adları (hata iletisi için).
_TYPE_LABELS: dict[str, str] = dict(CommissionDecisionType.choices)


def require_decision_type(
    decision: CommissionDecision,
    expected: str,
    *,
    field: str = "commission_decision",
) -> None:
    """Kararın türü beklenen tür değilse `ValidationError` (D7).

    İleti kullanıcı dilindedir ve hangi türün gerektiğini söyler; "geçersiz
    karar" demekle yetinmek, kullanıcıyı listedeki doğru kaydı aramaya bırakır.
    """
    if decision.decision_type == expected:
        return
    raise ValidationError(
        {
            field: (
                f"Bu işlem “{_TYPE_LABELS[expected]}” türünde bir komisyon kararı ister; "
                f"seçilen karar “{_TYPE_LABELS.get(decision.decision_type, decision.decision_type)}” "
                "türünde."
            )
        }
    )


def decision_in_use(decision: CommissionDecision) -> bool:
    """Karar bir kayda bağlanmış mı? (canlı kayıtlar)

    Bağlanılan kayıtlar: edinim, bağış ön kaydı (F2), ayıklama teklifi ve nadir
    eserler listesi (F8). İki yerden okunur: tür değişimi kilidi (aşağıda) ve
    API'nin `in_use` alanı — arayüz türün neden kilitli, kaydın neden silinemez
    olduğunu buradan anlatır (sayılar: `selectors_ayiklama.decision_usage`).
    """
    return (
        decision.acquisitions.exists()
        or decision.donation_intakes.exists()
        or decision.weeding_batches.exists()
        or decision.rare_works_submissions.exists()
    )


@transaction.atomic
def create_commission_decision(**fields: Any) -> CommissionDecision:
    """Komisyon kararı açar."""
    decision = CommissionDecision(**fields)
    decision.full_clean()
    decision.save()
    return decision


#: F8: kararın tarihi, ona dayanan kaydın tarihinden sonraya alınamaz (TMY 10/1-a).
DATE_AFTER_DEPENDENT_MESSAGE = (
    "Kararın tarihi {tarih} tarihinden sonraya alınamaz: bu karara dayanan {kayit} o "
    "tarihi taşıyor ve dayanağından önceki bir tarihi taşıyamaz (TMY 10/1-a). Tarih "
    "yanlışsa önce o kaydı düzeltin."
)


def _dayanan_en_erken(decision: CommissionDecision) -> tuple[date, str] | None:
    """Karara DAYANAN kayıtların en erken tarihi ve kaydın adı (kişisiz).

    Kural her birinde yazılırken sınanır (onay, gönderim, bağış edinimi); kararın
    tarihi sonradan değişirken burada yeniden sınanır:

    - onaylanmış ya da uygulanmış ayıklama teklifinin onay tarihi
      (`services.weeding.approve_batch`),
    - Genel Müdürlüğe gönderilmiş nadir eserler listesinin gönderim tarihi
      (`services.rare_works.send_submission`),
    - bağış ediniminin tarihi (`services.donations.acquisition_date_for`, F8 ekleri 9).
    """
    adaylar: list[tuple[date, str]] = []
    onay = (
        decision.weeding_batches.filter(
            status__in=(WeedingBatchStatus.APPROVED, WeedingBatchStatus.APPLIED),
            approved_on__isnull=False,
        )
        .order_by("approved_on")
        .values_list("approved_on", flat=True)
        .first()
    )
    if onay is not None:
        adaylar.append((onay, "ayıklama teklifinin harcama yetkilisi onayı"))
    gonderim = (
        decision.rare_works_submissions.filter(
            status=RareWorksSubmissionStatus.SENT, sent_on__isnull=False
        )
        .order_by("sent_on")
        .values_list("sent_on", flat=True)
        .first()
    )
    if gonderim is not None:
        adaylar.append((gonderim, "el yazması ve nadir eserler listesinin gönderimi"))
    edinim = (
        decision.acquisitions.filter(method=AcquisitionMethod.DONATION)
        .order_by("date")
        .values_list("date", flat=True)
        .first()
    )
    if edinim is not None:
        adaylar.append((edinim, "bağış edinimi"))
    return min(adaylar, key=lambda a: a[0]) if adaylar else None


@transaction.atomic
def update_commission_decision(decision: CommissionDecision, **fields: Any) -> CommissionDecision:
    """Komisyon kararını günceller.

    Kullanılmış bir kararın TÜRÜ değiştirilemez: tür denetimini (D7) geriye
    dönük olarak boşa çıkarır — bağış edinimine bağlı bir karar sonradan
    "ayıklama"ya çevrilirse edinim dayanaksız kalır.

    Kullanılmış bir kararın TARİHİ, ona dayanan kaydın tarihinden sonraya
    alınamaz (F8): onay, gönderim ve bağış edinimi "karardan önce olamaz" kuralını
    yazılırken sınar; karar sonradan ileri alınırsa kural geriye dönük bozulurdu
    (VİF "dayanağını oluşturan belgenin tarihinden önceki bir tarihi taşıyamaz" —
    TMY 10/1-a). Tarihi geri almak ve karar sayısını düzeltmek serbesttir.
    """
    yeni_tur = fields.get("decision_type")
    if yeni_tur is not None and yeni_tur != decision.decision_type and decision_in_use(decision):
        raise ValidationError(
            {
                "decision_type": (
                    "Bu kararın türü değiştirilemez: karara bağlı edinim, bağış ön kaydı, "
                    "ayıklama teklifi ya da nadir eserler listesi var. Yeni bir komisyon "
                    "kararı açın."
                )
            }
        )
    yeni_tarih = fields.get("decision_date")
    if isinstance(yeni_tarih, date) and yeni_tarih > decision.decision_date:
        dayanan = _dayanan_en_erken(decision)
        if dayanan is not None and yeni_tarih > dayanan[0]:
            raise ValidationError(
                {
                    "decision_date": DATE_AFTER_DEPENDENT_MESSAGE.format(
                        tarih=f"{dayanan[0]:%d.%m.%Y}", kayit=dayanan[1]
                    )
                }
            )
    for name, value in fields.items():
        setattr(decision, name, value)
    decision.full_clean()
    decision.save()
    return decision


@transaction.atomic
def delete_commission_decision(decision: CommissionDecision) -> None:
    """Komisyon kararını yumuşak siler; kullanılmışsa reddeder.

    `PROTECT` yumuşak silmede HİÇ tetiklenmez (CLAUDE.md §3): denetim burada
    elle yapılır, aksi hâlde karara dayanan bağış edinimi dayanaksız kalırdı.
    """
    if decision_in_use(decision):
        raise ValidationError(
            {
                "decision": (
                    "Bu karara bağlı edinim, bağış ön kaydı, ayıklama teklifi ya da nadir "
                    "eserler listesi var; karar silinemez. Yanlış girilen bilgileri düzeltin."
                )
            }
        )
    decision.delete()
