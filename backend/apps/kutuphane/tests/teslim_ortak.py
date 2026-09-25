"""Teslim ve kayıp/hasar testlerinin ortak kurgu yardımcıları (toplanmaz: `test_` ile başlamaz).

Bütün kişi verileri UYDURMADIR (CLAUDE.md §2-12): adlar "Deneme …" kalıbındadır.
Şube etiketleri kişisel veri değildir.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.kutuphane.models import Copy, Delivery, LossDamageCase
from apps.kutuphane.services import deliveries
from apps.kutuphane.tests.dolasim_ortak import ders_yili, odunc_nushasi, personel
from apps.okul.models import ClassSection, MemberKind, Personnel, SchoolConfig, SchoolYear


def etkin_yil() -> SchoolYear:
    """Etkin ders yılı (varsa onu, yoksa uydurma tarihli yeni yılı döndürür)."""
    yil: SchoolYear | None = SchoolYear.objects.filter(is_active=True).first()
    return yil if yil is not None else ders_yili()


def sube(
    class_level: int = 9, class_section: str = "A", *, yil: SchoolYear | None = None
) -> ClassSection:
    """Etkin ders yılının şubesi (sınıf kitaplığı)."""
    hedef = yil if yil is not None else etkin_yil()
    kayit: ClassSection
    kayit, _ = ClassSection.objects.get_or_create(
        school_year=hedef, class_level=class_level, class_section=class_section
    )
    return kayit


def ogretmen(**alanlar: Any) -> Personnel:
    alanlar.setdefault("first_name", "Deneme")
    alanlar.setdefault("last_name", "Öğretmen")
    alanlar.setdefault("member_kind", MemberKind.TEACHER)
    return personel(**alanlar)


def nushalar(sayi: int, **alanlar: Any) -> list[Copy]:
    """`sayi` adet rafta nüsha (her biri kendi eseriyle)."""
    return [odunc_nushasi(title=f"Deneme Eseri {i + 1}", **alanlar) for i in range(sayi)]


def teslim_et(
    copies: list[Copy],
    *,
    section: ClassSection | None = None,
    personnel: Personnel | None = None,
    **alanlar: Any,
) -> deliveries.DeliveryBatch:
    """Servis yoluyla toplu teslim (alan verilmezse etkin yılın 9/A şubesi)."""
    if section is None and personnel is None:
        section = sube()
    return deliveries.deliver(
        barcodes=[c.barcode for c in copies], section=section, personnel=personnel, **alanlar
    )


def kademe_yaz(kademe: str) -> SchoolConfig:
    """Okulun kademesini yazar (Md. 19 kapısı)."""
    config: SchoolConfig
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.kademe = kademe
    config.save()
    return config


def tazele_nusha(copy: Copy) -> Copy:
    nusha: Copy = Copy.all_objects.select_related("work").get(pk=copy.pk)
    return nusha


def tazele_teslim(delivery: Delivery) -> Delivery:
    teslim: Delivery = Delivery.all_objects.get(pk=delivery.pk)
    return teslim


def tazele_dosya(case: LossDamageCase) -> LossDamageCase:
    dosya: LossDamageCase = LossDamageCase.all_objects.select_related("copy").get(pk=case.pk)
    return dosya


GECMIS_GUN = date(2026, 9, 10)
