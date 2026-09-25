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

**F8 — komisyon kararıyla bütünleşme** (tasarım §14.1 F8 "bağış kararı → toplu
katalog"):

- **Edinim tarihi kabul tarihidir.** TMY 10/1-a Varlık İşlem Fişini "ilgili
  mevzuatı çerçevesinde kabul edilerek teslim alınan" taşınırın girişine bağlar
  ve fişin "dayanağını oluşturan belgenin tarihinden önceki bir tarihi"
  taşıyamayacağını söyler. Bağış komisyonca değerlendirilir (Md. 10/3) ve uygun
  bulunan kitap kütüphaneye kazandırılır (Uygulama Kılavuzu 2.3.3): edinim
  tarihi verilmezse karar tarihi ile geliş tarihinin geç olanıdır; verilen tarih
  bunlardan önce ve bugünden sonra olamaz. (F2'de varsayılan geliş tarihiydi —
  kararın tarihinden önce bir giriş tarihi doğabiliyordu.)
- **Var olan esere bağlama.** Kabul edilen kalem katalogda zaten bulunan bir
  kitapsa yeni eser AÇILMAZ, nüshalar o esere eklenir: eşleşme ölçütü F3 içe
  aktarımıyla aynıdır (ISBN-13 + aynı ad ya da aynı ad + aynı yazar, TR
  katlamalı — `item_matches`). Kullanıcı `work_links` ile kalemi başka bir esere
  bağlayabilir ya da (`None`) yeni eser açtırabilir. F2'de her kabul edilen
  kalem yeni eser açıyor, katalogda aynı kitabın ikinci kaydı doğuyordu.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane import keys
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


ACQUISITION_BEFORE_DECISION_MESSAGE = (
    "Edinim tarihi komisyon kararının tarihinden önce olamaz: bağış komisyonca değerlendirilir "
    "(Md. 10/3), uygun bulunan kitap kütüphaneye kazandırılır (Uygulama Kılavuzu 2.3.3) ve "
    "giriş kaydı dayanağından önceki tarihi taşıyamaz (TMY 10/1-a)."
)
ACQUISITION_BEFORE_RECEIVED_MESSAGE = "Edinim tarihi bağışın geliş tarihinden önce olamaz."
ACQUISITION_IN_FUTURE_MESSAGE = "Edinim tarihi bugünden sonra olamaz."
LINK_NOT_ACCEPTED_MESSAGE = "Esere bağlanan kalem kabul edilenler arasında olmalıdır."
LINK_WORK_MISSING_MESSAGE = "Bağlanacak eser bulunamadı."


def acquisition_date_for(
    intake: DonationIntake, decision: CommissionDecision, requested: date | None = None
) -> date:
    """Bağış ediniminin tarihi (modül belgesi, "Edinim tarihi kabul tarihidir").

    Verilmezse karar tarihi ile geliş tarihinin geç olanı. Verilen tarih ikisinden
    önce ve bugünden sonra olamaz.
    """
    en_erken = max(decision.decision_date, intake.received_date)
    if requested is None:
        return en_erken
    if requested < decision.decision_date:
        raise ValidationError({"acquisition_date": ACQUISITION_BEFORE_DECISION_MESSAGE})
    if requested < intake.received_date:
        raise ValidationError({"acquisition_date": ACQUISITION_BEFORE_RECEIVED_MESSAGE})
    if requested > timezone.localdate():
        raise ValidationError({"acquisition_date": ACQUISITION_IN_FUTURE_MESSAGE})
    return requested


@dataclass
class ItemMatch:
    """Bağış kaleminin katalogdaki karşılığı (F3 içe aktarımıyla aynı ölçüt).

    `exact`: kalemin nüshaları bu esere eklenir (ISBN-13 + aynı ad, ya da aynı ad +
    aynı yazar; TR katlamalı; birden çoksa en eski kayıt). `suspects`: aynı
    ISBN'li ama adı farklı ya da aynı adlı ama yazarı farklı eserler — program
    bunlara KENDİLİĞİNDEN bağlamaz, kullanıcı `work_links` ile seçer.
    """

    exact: Work | None = None
    suspects: list[Work] = field(default_factory=list)


def item_matches(item: DonationIntakeItem) -> ItemMatch:
    """Kalemin katalogdaki eşleşmesi (salt okur)."""
    ad = keys.fold_search(item.title)
    yazar = keys.fold_search(item.authors)
    isbn13 = isbn_module.to_isbn13(item.isbn)
    sonuc = ItemMatch()
    adaylar: list[Work] = []
    if isbn13:
        adaylar.extend(Work.objects.filter(isbn13=isbn13).order_by("pk"))
    if ad:
        gorulen = {w.pk for w in adaylar}
        # Ad katlaması arama anahtarının parçasıdır; kaba süzgeç DB'de, kesin karar Python'da.
        for work in Work.objects.filter(search_key__contains=ad).order_by("pk"):
            if work.pk not in gorulen:
                adaylar.append(work)
    for work in adaylar:
        ayni_ad = keys.fold_search(work.title) == ad
        ayni_isbn = bool(isbn13) and work.isbn13 == isbn13
        if (ayni_isbn and ayni_ad) or (ayni_ad and keys.fold_search(work.authors) == yazar):
            if sonuc.exact is None:
                sonuc.exact = work
            continue
        if ayni_isbn or ayni_ad:
            sonuc.suspects.append(work)
    return sonuc


def _hedef_eser(
    item: DonationIntakeItem, links: Mapping[int, int | None], section: Section | None
) -> tuple[Work, bool]:
    """Kalemin nüshalarının ekleneceği eser ve yeni açılıp açılmadığı."""
    if item.pk in links:
        hedef = links[item.pk]
        if hedef is not None:
            work: Work | None = Work.objects.filter(pk=hedef).first()
            if work is None:
                raise ValidationError({"work_links": LINK_WORK_MISSING_MESSAGE})
            return work, False
    else:
        eslesme = item_matches(item).exact
        if eslesme is not None:
            return eslesme, False
    yeni = catalog.create_work(
        title=item.title,
        authors=item.authors,
        publisher=item.publisher,
        publish_year=item.publish_year,
        isbn=item.isbn,
        section=section,
    )
    return yeni, True


@transaction.atomic
def apply_decision(
    intake: DonationIntake,
    *,
    commission_decision: CommissionDecision,
    accepted_ids: Iterable[int] = (),
    rejected: Mapping[int, str] | None = None,
    acquisition_date: date | None = None,
    section: Section | None = None,
    unit_price: Any = None,
    work_links: Mapping[int, int | None] | None = None,
) -> dict[str, Any]:
    """Komisyon kararını uygular: kabul edilenleri kataloglar, reddedilenleri işaretler.

    Her kalem TAM OLARAK bir kez kararlanmalıdır (kabul ya da ret); eksik ya da
    fazla karar bütün işlemi reddeder — yarım kararlanmış bir liste, hangi
    kitabın kayda girdiği sorusunu cevapsız bırakır. Ret gerekçesi zorunludur.

    Edinim tarihi kabul tarihidir (`acquisition_date_for`). Kabul edilen kalem
    katalogdaki bir eserle birebir eşleşiyorsa nüshaları o esere eklenir
    (`item_matches`); `work_links` (kalem kimliği → eser kimliği ya da `None` =
    yeni eser aç) bu seçimi kalem kalem değiştirir.

    Döner: `{"acquisition", "works", "copies", "accepted", "rejected",
    "linked_works"}` — `works` bu kararla YENİ açılan eserlerdir, `linked_works`
    nüshaları var olan esere eklenen kalemlerin eserleri.
    """
    _require_pending(intake)
    commissions.require_decision_type(commission_decision, CommissionDecisionType.DONATION_REVIEW)

    ret_kararlari: dict[int, str] = {int(k): str(v or "") for k, v in (rejected or {}).items()}
    kabul_edilenler = [int(pk) for pk in accepted_ids]
    _ensure_full_coverage(intake, kabul_edilenler, ret_kararlari)
    baglar: dict[int, int | None] = {
        int(k): (int(v) if v is not None else None) for k, v in (work_links or {}).items()
    }
    if set(baglar) - set(kabul_edilenler):
        raise ValidationError({"work_links": LINK_NOT_ACCEPTED_MESSAGE})
    tarih = acquisition_date_for(intake, commission_decision, acquisition_date)

    kalemler = {item.pk: item for item in intake.items.all()}
    acquisition: Acquisition | None = None
    works: list[Work] = []
    linked: list[Work] = []
    copies: list[Copy] = []
    if kabul_edilenler:
        # Edinim YALNIZ kabul varsa açılır: hepsi reddedilmiş bir bağışın
        # kütüphaneye girmiş bir partisi yoktur.
        acquisition = catalog.create_acquisition(
            method=AcquisitionMethod.DONATION,
            date=tarih,
            source_note=intake.donor_name,
            commission_decision=commission_decision,
            unit_price=unit_price,
            notes=f"Bağış ön kaydı #{intake.pk}",
        )
        for pk in kabul_edilenler:
            item = kalemler[pk]
            work, yeni = _hedef_eser(item, baglar, section)
            copies.extend(
                catalog.create_copies(
                    work=work, acquisition=acquisition, count=item.copies, section=section
                )
            )
            item.decision = DonationItemDecision.ACCEPTED
            item.work = work
            item.save(update_fields=["decision", "work", "updated_at"])
            (works if yeni else linked).append(work)

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
        "linked_works": linked,
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
