"""Ayıklama, nadir eser ve komisyon kullanımı — salt okuma sorguları (F8; tasarım §6.2, E7, E8).

Kişisel veri: ayıklama kalemleri ve nadir eser satırları kişisizdir. Teklifin
şifreli adları (TMY komisyonu, harcama yetkilisi) yalnız teklif ayrıntısında
serileştirilir; listeler ve aday sorgusu onlara dokunmaz.

Sıralama: kullanıcıya gösterilen her liste Türkçe sıralanır (CLAUDE.md §3):
nüsha listeleri eserin `sort_key`'i (TR katlamalı) ve kayıt no ile, teklifler
tarihle sıralanır. Yumuşak silme ileri FK'da süzülmez: nüshanın ESERİ elle
denetlenir (`work__deleted_at__isnull=True`).
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.kutuphane import keys
from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    OPEN_WEEDING_STATUSES,
    TERMINAL_COPY_STATUSES,
    CaseType,
    CommissionDecision,
    Copy,
    CopyStatus,
    LossDamageCase,
    RareWorksSubmission,
    RareWorksSubmissionItem,
    RareWorksSubmissionStatus,
    WeedingBatch,
    WeedingItem,
)


# ---------------------------------------------------------------------------
# Ayıklama teklifleri
# ---------------------------------------------------------------------------
def weeding_batches(
    *, status: str = "", school_year_id: int | None = None
) -> QuerySet[WeedingBatch]:
    """Teklifler (en yeni önce); komisyon kararı ve ders yılı birlikte gelir."""
    qs = WeedingBatch.objects.select_related("commission_decision", "school_year")
    if status:
        qs = qs.filter(status=status)
    if school_year_id is not None:
        qs = qs.filter(school_year_id=school_year_id)
    return qs.order_by("-created_at", "-pk")


def get_weeding_batch(batch_id: int) -> WeedingBatch | None:
    return weeding_batches().filter(pk=batch_id).first()


def batch_items(batch: WeedingBatch) -> QuerySet[WeedingItem]:
    """Teklifin canlı kalemleri — eser adının Türkçe sırasıyla (tutanak sırası)."""
    return (
        WeedingItem.objects.filter(batch=batch)
        .select_related("copy", "copy__work", "copy__section")
        .order_by("copy__work__sort_key", "copy__accession_no", "pk")
    )


def open_batch_items_for_copy(copy_id: int) -> QuerySet[WeedingItem]:
    """Nüshanın SÜREN (uygulanmamış, iptal edilmemiş) tekliflerdeki canlı kalemleri."""
    return WeedingItem.objects.filter(
        copy_id=copy_id,
        batch__status__in=OPEN_WEEDING_STATUSES,
        batch__deleted_at__isnull=True,
    )


def weeding_items_for_copy(copy_id: int) -> QuerySet[WeedingItem]:
    """Nüshanın canlı tekliflerdeki (süren, uygulanmış ya da iptal edilmiş) canlı kalemleri.

    Nüsha silme kapısı (`services.catalog.delete_copy`) sorar: bir teklife girmiş nüsha
    yanlış açılmış bir kayıt değildir.
    """
    return WeedingItem.objects.filter(copy_id=copy_id, batch__deleted_at__isnull=True)


def _oneri_dosyalari() -> QuerySet[LossDamageCase]:
    """Kayıttan düşme önerisi taşıyan KAPANMIŞ dosyalar (F7: "Kayıttan düşme önerildi",
    "Bedelle başka eser alındı")."""
    return LossDamageCase.objects.filter(write_off_proposed_at__isnull=False).exclude(
        resolution__in=OPEN_CASE_RESOLUTIONS
    )


def has_damage_write_off_proposal(copy_id: int) -> bool:
    """Nüshanın HASAR dosyasında kayıttan düşme önerisi var mı? (ayıklamaya konmaz)"""
    return _oneri_dosyalari().filter(copy_id=copy_id, case_type=CaseType.DAMAGED).exists()


def _canli_nusha_q() -> Q:
    return Q(work__deleted_at__isnull=True)


def weeding_candidates(
    *,
    q: str = "",
    section_id: int | None = None,
) -> QuerySet[Copy]:
    """Ayıklamaya konabilecek nüshalar (aday listesi — tasarım §14.1 F8).

    Ölçüt (`services.weeding.ayiklama_engeli` ile aynı): nüsha ve eseri canlı,
    RAFTA (ödünçte, teslimde, onarımda, kayıp ya da kayıttan düşülmüş değil),
    nadir/el yazması DEĞİL, çözülmemiş kayıp/hasar dosyası yok, kayıp/hasar
    dosyasının kayıttan düşme önerisi yok ve süren bir teklifte değil.

    Kayıttan düşme önerileri BU LİSTEDE DEĞİLDİR (25.09.2026 kullanıcı kararı,
    tasarım F8 ekleri 34): Md. 12/1'in bentleri kaybı ve hasarı saymaz; kayıp ve
    hasar dosyasının önerisi sayımda TMY 27/1 yolundan, kayıp/hasar tutanağıyla
    düşülür. Ekran onları ayrı gösterir (`lost_write_off_proposals`,
    `damage_write_off_proposals`).
    """
    acik_dosya = LossDamageCase.objects.filter(
        copy_id=OuterRef("pk"), resolution__in=OPEN_CASE_RESOLUTIONS
    )
    suren_teklif = WeedingItem.objects.filter(
        copy_id=OuterRef("pk"),
        batch__status__in=OPEN_WEEDING_STATUSES,
        batch__deleted_at__isnull=True,
    )
    # Raftaki nüshada öneri yalnız hasar dosyasından gelebilir (kayıp nüsha rafta
    # değildir; öneriden bulunma öneriyi kaldırır — `loss_damage.ONERIDEN_BULUNMA`).
    hasar_onerisi = _oneri_dosyalari().filter(copy_id=OuterRef("pk"), case_type=CaseType.DAMAGED)
    qs = (
        Copy.objects.filter(_canli_nusha_q(), status=CopyStatus.AVAILABLE)
        .filter(is_rare_or_manuscript=False)
        .exclude(Exists(acik_dosya))
        .exclude(Exists(hasar_onerisi))
        .exclude(Exists(suren_teklif))
        .select_related("work", "section")
    )
    for term in keys.search_terms(q):
        qs = qs.filter(work__search_key__contains=term)
    if section_id is not None:
        qs = qs.filter(
            Q(section_id=section_id) | Q(section__isnull=True, work__section_id=section_id)
        )
    sirali: QuerySet[Copy] = qs.order_by("work__sort_key", "accession_no")
    return sirali


def lost_write_off_proposals() -> QuerySet[Copy]:
    """Kayıttan düşme önerilmiş KAYIP nüshalar — ayıklamaya konmaz, sayımda kapanır.

    Aday ekranı bunları ayrı gösterir ki "öneri nereye gitti" sorusu cevapsız
    kalmasın; ayıklama teklifine eklenmeleri servis kuralıyla reddedilir.
    """
    oneri = _oneri_dosyalari().filter(copy_id=OuterRef("pk"))
    return (
        Copy.objects.filter(_canli_nusha_q(), status=CopyStatus.LOST)
        .filter(Exists(oneri))
        .select_related("work", "section")
        .order_by("work__sort_key", "accession_no")
    )


def damage_write_off_proposals() -> QuerySet[Copy]:
    """HASAR dosyasında kayıttan düşme önerilmiş nüshalar — ayıklamaya konmaz, sayımda düşülür.

    Hasar dosyası nüshayı dolaşımdan çıkarmadığı için nüsha rafta, ödünçte, teslimde
    ya da onarımda olabilir; kayıp nüsha `lost_write_off_proposals`'tadır, kayıttan
    düşülmüş ve devredilmiş nüsha zaten çıkmıştır.
    """
    oneri = _oneri_dosyalari().filter(copy_id=OuterRef("pk"), case_type=CaseType.DAMAGED)
    return (
        Copy.objects.filter(_canli_nusha_q())
        .exclude(status__in=(CopyStatus.LOST, *TERMINAL_COPY_STATUSES))
        .filter(Exists(oneri))
        .select_related("work", "section")
        .order_by("work__sort_key", "accession_no")
    )


# ---------------------------------------------------------------------------
# Nadir eserler (Md. 12/2)
# ---------------------------------------------------------------------------
def rare_works_submissions(*, status: str = "") -> QuerySet[RareWorksSubmission]:
    qs = RareWorksSubmission.objects.select_related("commission_decision", "school_year")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-created_at", "-pk")


def get_rare_works_submission(submission_id: int) -> RareWorksSubmission | None:
    return rare_works_submissions().filter(pk=submission_id).first()


def submission_items(submission: RareWorksSubmission) -> QuerySet[RareWorksSubmissionItem]:
    return (
        RareWorksSubmissionItem.objects.filter(submission=submission)
        .select_related("copy", "copy__work")
        .order_by("copy__work__sort_key", "copy__accession_no", "pk")
    )


def sent_rare_items_for_copy(copy_id: int) -> QuerySet[RareWorksSubmissionItem]:
    """Nüshanın Genel Müdürlüğe GÖNDERİLMİŞ listelerdeki satırları."""
    return RareWorksSubmissionItem.objects.filter(
        copy_id=copy_id,
        submission__status=RareWorksSubmissionStatus.SENT,
        submission__deleted_at__isnull=True,
    )


def rare_items_for_copy(copy_id: int) -> QuerySet[RareWorksSubmissionItem]:
    """Nüshanın canlı nadir eserler listelerindeki satırları (hazırlanan ya da gönderilmiş)."""
    return RareWorksSubmissionItem.objects.filter(
        copy_id=copy_id, submission__deleted_at__isnull=True
    )


def decided_rare_items_for_copy(copy_id: int) -> QuerySet[RareWorksSubmissionItem]:
    """Nüshanın komisyonca TESPİT EDİLMİŞ listelerdeki satırları (Md. 12/2).

    Liste gönderilmişse ya da hazırlanırken Seçim ve Ayıklama Komisyonunun kararı
    bağlanmışsa nüshanın nadir eser olduğu artık bir veri girişi değil, komisyonun
    tespitidir: işaret kaldırılamaz (`services.catalog.ensure_rare_flag_change`).
    """
    return RareWorksSubmissionItem.objects.filter(
        Q(submission__status=RareWorksSubmissionStatus.SENT)
        | Q(submission__commission_decision__isnull=False),
        copy_id=copy_id,
        submission__deleted_at__isnull=True,
    )


def rare_copies(*, unsent_only: bool = False) -> QuerySet[Copy]:
    """El yazması ya da nadir eser işaretli nüshalar (Nadir Eserler ekranı).

    `sent` alanı nüshanın gönderilmiş bir listede olup olmadığını söyler;
    `unsent_only` yalnız henüz bildirilmemişleri verir (yeni liste için aday).
    """
    gonderilmis = RareWorksSubmissionItem.objects.filter(
        copy_id=OuterRef("pk"),
        submission__status=RareWorksSubmissionStatus.SENT,
        submission__deleted_at__isnull=True,
    )
    qs = (
        Copy.objects.filter(_canli_nusha_q(), is_rare_or_manuscript=True)
        .annotate(sent=Exists(gonderilmis))
        .select_related("work", "section")
    )
    if unsent_only:
        qs = qs.filter(sent=False)
    sirali: QuerySet[Copy] = qs.order_by("work__sort_key", "accession_no")
    return sirali


# ---------------------------------------------------------------------------
# Komisyon kararının kullanımı (D7 — tür kilidi ve silme engeli)
# ---------------------------------------------------------------------------
def decision_usage(decision: CommissionDecision) -> dict[str, int]:
    """Karara bağlı CANLI kayıtların sayıları (kişisiz).

    Komisyon ekranı kararın neden kilitli olduğunu buradan anlatır; toplamı
    sıfırdan büyükse kararın türü değiştirilemez ve kayıt silinemez
    (`services.commissions.decision_in_use`).
    """
    return {
        "acquisitions": decision.acquisitions.count(),
        "donation_intakes": decision.donation_intakes.count(),
        "weeding_batches": decision.weeding_batches.count(),
        "rare_works_submissions": decision.rare_works_submissions.count(),
    }
