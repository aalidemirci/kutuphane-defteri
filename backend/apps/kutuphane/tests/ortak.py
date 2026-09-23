"""Katalog testleri için ortak kurgu yardımcıları.

Bütün veriler UYDURMADIR (CLAUDE.md §2-12): gerçek öğrenci, personel ya da
bağışçı adı kullanılmaz. Kitap künyeleri kişisel veri değildir; bağışçı ve
komisyon adları uydurma kişilerdir.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from apps.kutuphane import selectors
from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    Section,
    Work,
)
from apps.kutuphane.services import catalog

VARSAYILAN_TARIH = date(2026, 9, 1)


def edinim(**alanlar: Any) -> Acquisition:
    """Kayıt-içi giriş türünde edinim (komisyon kararı istemez)."""
    alanlar.setdefault("method", AcquisitionMethod.EXISTING_STOCK)
    alanlar.setdefault("date", VARSAYILAN_TARIH)
    return catalog.create_acquisition(**alanlar)


def karar(**alanlar: Any) -> CommissionDecision:
    """Komisyon kararı (başkan adı uydurmadır ve şifreli alana yazılır)."""
    alanlar.setdefault("decision_type", CommissionDecisionType.DONATION_REVIEW)
    alanlar.setdefault("decision_date", VARSAYILAN_TARIH)
    alanlar.setdefault("decision_no", "2026/7")
    alanlar.setdefault("chair_name", "Deniz Korkmaz")
    decision: CommissionDecision = CommissionDecision.objects.create(**alanlar)
    return decision


def bolum(**alanlar: Any) -> Section:
    alanlar.setdefault("name", "Edebiyat")
    return catalog.create_section(**alanlar)


def eser(**alanlar: Any) -> Work:
    alanlar.setdefault("title", "Kürk Mantolu Madonna")
    alanlar.setdefault("authors", "Sabahattin Ali")
    return catalog.create_work(**alanlar)


def nusha(work: Work | None = None, acquisition: Acquisition | None = None, **alanlar: Any) -> Copy:
    hedef_eser = work if work is not None else eser()
    hedef_edinim = acquisition if acquisition is not None else edinim()
    return catalog.create_copy(work=hedef_eser, acquisition=hedef_edinim, **alanlar)


def nusha_sayaclari(work_id: int) -> dict[str, int]:
    """Eserin nüsha sayaçları (`annotate` alanları django-stubs'a görünmez, `cast`)."""
    qs = cast("Any", selectors.works_with_copy_counts())
    satir = qs.values("copy_count", "available_copy_count").get(pk=work_id)
    return {ad: int(deger) for ad, deger in satir.items()}
