"""Ayıklama, nadir eser ve yıl sonu raporu testlerinin ortak kurgusu (toplanmaz: `test_` yok).

Bütün kişi adları UYDURMADIR (CLAUDE.md §2-12): "Deneme …" kalıbı. Devralacak
kurum adları da uydurmadır ve kişi adı değildir.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.utils import timezone

from apps.kutuphane.models import (
    CommissionDecision,
    CommissionDecisionType,
    Copy,
    WeedingBatch,
    WeedingItem,
)
from apps.kutuphane.services import weeding
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi
from apps.kutuphane.tests.ortak import karar
from apps.kutuphane.tests.teslim_ortak import etkin_yil

#: Uydurma TMY komisyonu (en az üç kişi — TMY 28/1).
TMY_KOMISYONU = "Deneme Birinciüye\nDeneme İkinciüye\nDeneme Üçüncüüye"
#: Uydurma harcama yetkilisi.
HARCAMA_YETKILISI = "Deneme Harcamayetkilisi"
#: Uydurma devralacak okul (kişi adı değil).
DEVRALAN_OKUL = "Deneme İlkokulu"


def ayiklama_karari(**alanlar: Any) -> CommissionDecision:
    """ "Ayıklama" türünde komisyon kararı (tarih bugün — onay tarihinden önce olmasın)."""
    alanlar.setdefault("decision_type", CommissionDecisionType.WEEDING)
    alanlar.setdefault("decision_date", timezone.localdate())
    alanlar.setdefault("decision_no", "2026/9")
    return karar(**alanlar)


def raftaki(title: str = "Ayıklanacak Eser", **alanlar: Any) -> Copy:
    """Rafta, kendi eseriyle yeni bir nüsha."""
    return odunc_nushasi(title=title, **alanlar)


def teklif(**alanlar: Any) -> WeedingBatch:
    """Etkin ders yılında taslak teklif."""
    etkin_yil()
    return weeding.create_batch(**alanlar)


def kalem_ekle(
    batch: WeedingBatch, copy: Copy, reason: str = "WORN", **alanlar: Any
) -> WeedingItem:
    return weeding.add_items(batch, reason=reason, copy_ids=[copy.pk], **alanlar)[0]


def onaya_kadar(
    batch: WeedingBatch,
    *,
    decision: CommissionDecision | None = None,
    approved_on: date | None = None,
    **onay: Any,
) -> WeedingBatch:
    """Taslak teklifi sunar, karar bağlar ve onaylar (varsayılan uydurma adlarla)."""
    weeding.submit_batch(batch)
    weeding.bind_decision(
        batch, commission_decision=decision if decision is not None else ayiklama_karari()
    )
    onay.setdefault("approved_by_name", HARCAMA_YETKILISI)
    onay.setdefault("tmy_commission_members", TMY_KOMISYONU)
    return weeding.approve_batch(batch, approved_on=approved_on or timezone.localdate(), **onay)


def tazele(copy: Copy) -> Copy:
    nusha: Copy = Copy.all_objects.select_related("work").get(pk=copy.pk)
    return nusha
