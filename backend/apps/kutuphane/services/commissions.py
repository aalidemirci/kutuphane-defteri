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

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kutuphane.models import CommissionDecision, CommissionDecisionType

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
    """Karar bir edinime ya da bağış ön kaydına bağlanmış mı? (canlı kayıtlar)

    İki yerden okunur: tür değişimi kilidi (aşağıda) ve API'nin `in_use` alanı —
    arayüz türün neden kilitli, kaydın neden silinemez olduğunu buradan anlatır.
    """
    return decision.acquisitions.exists() or decision.donation_intakes.exists()


@transaction.atomic
def create_commission_decision(**fields: Any) -> CommissionDecision:
    """Komisyon kararı açar."""
    decision = CommissionDecision(**fields)
    decision.full_clean()
    decision.save()
    return decision


@transaction.atomic
def update_commission_decision(decision: CommissionDecision, **fields: Any) -> CommissionDecision:
    """Komisyon kararını günceller.

    Kullanılmış bir kararın TÜRÜ değiştirilemez: tür denetimini (D7) geriye
    dönük olarak boşa çıkarır — bağış edinimine bağlı bir karar sonradan
    "ayıklama"ya çevrilirse edinim dayanaksız kalır.
    """
    yeni_tur = fields.get("decision_type")
    if yeni_tur is not None and yeni_tur != decision.decision_type and decision_in_use(decision):
        raise ValidationError(
            {
                "decision_type": (
                    "Bu kararın türü değiştirilemez: karara bağlı edinim ya da bağış ön "
                    "kaydı var. Yeni bir komisyon kararı açın."
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
                    "Bu karara bağlı edinim ya da bağış ön kaydı var; karar silinemez. "
                    "Yanlış girilen bilgileri düzeltin."
                )
            }
        )
    decision.delete()
