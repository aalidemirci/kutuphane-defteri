"""Kütüphane politikası — tek satırın (singleton) okunması ve yazılması.

**Ödünç süresi burada YOKTUR** (D19, CLAUDE.md §2-6): Md. 18 süreyi "on beş
gün" olarak sabitler; ayar alanı açmak okulu farkında olmadan hükme aykırı bir
uygulamaya sokardı. Sayı sınırlarının üst değerleri de mevzuattandır ve model
validator'ları ile zorlanır (öğrenci ≤ 3, öğretmen ≤ 5).

**Diğer personele ödünç** (AT-4): Yönetmelikte ayrıca düzenlenmemiştir. Program
seçeneği okul müdürlüğü kararıyla açar ve kararın TARİHİ ile SAYISINI ister —
bu bir mevzuat hükmü değil, programın ihtiyat kuralıdır ve kullanıcı metni de
bunu böyle söyler.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kutuphane.models import LibraryPolicy

#: Ödünç süresi — Md. 18, sabit. Ayar DEĞİLDİR; F6 dolaşımı buradan okur.
LOAN_PERIOD_DAYS = 15


def load_policy() -> LibraryPolicy:
    """Politika satırını döndürür; yoksa KAYDEDİLMEMİŞ varsayılan (okuma yazmaz)."""
    return LibraryPolicy.load()


def ensure_staff_loan_decision(policy: LibraryPolicy) -> None:
    """Diğer personele ödünç açıksa müdürlük kararının tarihi ve sayısı dolu mu?

    DB kısıtı da aynı şeyi söyler; buradaki denetim kullanıcıya hangi alanın
    eksik olduğunu söyleyen Türkçe iletiyi üretmek içindir.
    """
    if not policy.staff_loans_enabled:
        return
    eksik: dict[str, str] = {}
    if policy.staff_loans_decision_date is None:
        eksik["staff_loans_decision_date"] = (
            "Diğer personele ödünç seçeneği açılırken müdürlük kararının tarihi zorunludur."
        )
    if not str(policy.staff_loans_decision_no or "").strip():
        eksik["staff_loans_decision_no"] = (
            "Diğer personele ödünç seçeneği açılırken müdürlük kararının sayısı zorunludur."
        )
    if eksik:
        raise ValidationError(eksik)


@transaction.atomic
def update_policy(**fields: Any) -> LibraryPolicy:
    """Politikayı günceller (satır yoksa varsayılanlarla açar).

    Gönderilmeyen alana DOKUNULMAZ: ekranın bir sekmesinden yapılan kayıt,
    öbür sekmedeki ayarları varsayılana döndürmemelidir.
    """
    policy: LibraryPolicy
    policy, _created = LibraryPolicy.objects.get_or_create(pk=LibraryPolicy.SINGLETON_PK)
    for name, value in fields.items():
        setattr(policy, name, value)
    if not policy.staff_loans_enabled:
        # Seçenek kapatıldığında karar bilgisi anlamını yitirir; DB kısıtı da
        # yalnız açıkken dolu olmasını ister. Temizlenmezse eski karar, seçenek
        # yeniden açıldığında sessizce "hâlâ geçerli" görünürdü.
        policy.staff_loans_decision_date = None
        policy.staff_loans_decision_no = ""
    ensure_staff_loan_decision(policy)
    policy.full_clean()
    policy.save()
    return policy
