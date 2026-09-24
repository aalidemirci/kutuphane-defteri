"""Etiket kuyruğu ve boş barkod aralığı testlerinin ortak kurgusu (F4-Q).

Bütün veriler UYDURMADIR (CLAUDE.md §2-12). Şablon ölçüleri yaygın 65'li A4
tabakanın ölçüleridir; kuyruk testleri geometriye bakmaz, yalnız hücre sayısını
(başlangıç hücresi sınırı) ve satır/sütun eşleşmesini kullanır.

Etiket motoru (L kolu) kuyruk testlerinde KOŞMAZ: `label_render.render_job` sahte bir
motorla değiştirilir ve motora giden işler kaydedilir. Böylece "PDF üretmek
basıldı değildir" (D10) kuralı motorun iç ayrıntısından bağımsız sınanır.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from apps.kutuphane.models import (
    Copy,
    LabelCalibration,
    LabelKind,
    LabelSheetTemplate,
)
from apps.kutuphane.services import label_render
from apps.kutuphane.tests import ortak

#: Sahte motorun döndürdüğü PDF gövdesi.
SAHTE_PDF = b"%PDF-1.4\n% sahte etiket\n"


def sablon(**alanlar: Any) -> LabelSheetTemplate:
    """65'li A4 barkod tabakası (38,1 × 21,2 mm; 5 sütun × 13 satır)."""
    alanlar.setdefault("name", "Deneme 65'li")
    alanlar.setdefault("kind", LabelKind.BARCODE)
    alanlar.setdefault("page_margin_top", Decimal("10.70"))
    alanlar.setdefault("page_margin_left", Decimal("4.75"))
    alanlar.setdefault("label_width", Decimal("38.10"))
    alanlar.setdefault("label_height", Decimal("21.20"))
    alanlar.setdefault("rows", 13)
    alanlar.setdefault("cols", 5)
    alanlar.setdefault("gutter_x", Decimal("2.54"))
    alanlar.setdefault("gutter_y", Decimal("0"))
    kayit: LabelSheetTemplate = LabelSheetTemplate.objects.create(**alanlar)
    return kayit


def kalibrasyon(template: LabelSheetTemplate, **alanlar: Any) -> LabelCalibration:
    alanlar.setdefault("printer_name", "Masa yazıcısı")
    alanlar.setdefault("offset_x", Decimal("0.50"))
    alanlar.setdefault("offset_y", Decimal("-0.30"))
    kayit: LabelCalibration = LabelCalibration.objects.create(template=template, **alanlar)
    return kayit


def nushalar(adet: int, **alanlar: Any) -> list[Copy]:
    """Aynı eser ve edinimden `adet` nüsha (sayaçtan numaralı)."""
    work = alanlar.pop("work", None) or ortak.eser()
    acquisition = alanlar.pop("acquisition", None) or ortak.edinim()
    return [ortak.nusha(work, acquisition, **alanlar) for _ in range(adet)]


def isaretler(copy: Copy) -> tuple[Any, Any, Any]:
    """Nüshanın üç işareti, veritabanından taze: (barkod basım, doğrulama, sırt basım)."""
    taze = Copy.all_objects.get(pk=copy.pk)
    return taze.label_printed_at, taze.label_verified_at, taze.spine_label_printed_at


def motoru_bagla(monkeypatch: pytest.MonkeyPatch) -> list[label_render.LabelJob]:
    """`render_job`'u sahte motorla değiştirir; motora giden işlerin listesini döndürür."""
    isler: list[label_render.LabelJob] = []

    def sahte(job: label_render.LabelJob) -> bytes:
        isler.append(job)
        return SAHTE_PDF

    monkeypatch.setattr(label_render, "render_job", sahte)
    return isler


def motoru_ayir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Motorun yüklenemediği durumu kurar (bozuk kurulum → uçta 503)."""

    def bagli_degil(job: label_render.LabelJob) -> bytes:
        raise label_render.LabelRendererUnavailable("Etiket basım motoru yüklenemedi.")

    monkeypatch.setattr(label_render, "render_job", bagli_degil)
