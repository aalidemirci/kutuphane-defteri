"""Etiket PDF'i — motorun tek giriş noktası (`render_labels`).

Girdi: kalem listesi (nüsha ya da numara — `content.py`) + bir ya da iki parça
(içerik türü + şablon + kalibrasyon) + başlangıç hücresi + QR seçeneği. Çıktı:
PDF baytları ve yerleşim planı. **Veritabanına YAZMAZ**: PDF üretmek "basıldı"
demek değildir (D10); basım kaydı ve "Basıldı olarak işaretle" basım partisinin
(Q kolu, `LabelPrintBatch`) işidir. Motor yalnız kısa okul adını okur, o da
`school_short_name` verilmemişse.

**Sırt ve barkod aynı düzende** (§7.2): iki parça verilirse ikisi de AYNI
yerleşim planını (`geometry.plan_placements`) kullanır; parçaların şablonları
aynı satır × sütun ızgarasında olmalıdır, değilse ret. PDF'te önce birinci
parçanın bütün tabakaları, sonra ikincininkiler gelir: n. sırt tabakasının
k. hücresindeki etiket, n. barkod tabakasının k. hücresindeki etiketle aynı
kitabındır.

PDF yalnız `shared.pdf.html_to_pdf` kapısından üretilir (süreç genelinde kilit
ve paylaşılan yazı tipi yapılandırması — CLAUDE.md §3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from django.template.loader import render_to_string

from apps.kutuphane.labels.content import (
    SELECTION_CONTENTS,
    LabelContent,
    LabelItem,
    LabelSelection,
    items_from_barcodes,
    items_from_copies,
    parse_selection,
    validate_items,
)
from apps.kutuphane.labels.geometry import (
    CalibrationOffset,
    LabelError,
    Placement,
    SheetGeometry,
    mm_text,
    plan_placements,
    sheet_count,
)
from apps.kutuphane.labels.layout import LabelLayout, TextBox, label_layout
from shared.pdf import html_to_pdf

if TYPE_CHECKING:
    from apps.kutuphane.models import Copy, LabelCalibration, LabelSheetTemplate

TEMPLATE_NAME = "documents/etiket_tabakasi.html"

#: Belge adları (sözlük §2: E1) — PDF başlığı ve indirme adı buradan.
DOCUMENT_NAMES: dict[LabelSelection, str] = {
    LabelSelection.SPINE: "Sırt Etiketi",
    LabelSelection.BARCODE: "Barkod Etiketi",
    LabelSelection.BOTH: "Sırt ve Barkod Etiketi",
    LabelSelection.BLANK_BARCODE: "Boş Barkod Etiketi",
}

_ALIGN_CSS = {"left": "l", "center": "c", "right": "r"}


@dataclass(frozen=True)
class LabelPart:
    """Bir içerik türünün basıldığı tabaka: şablon + (varsa) yazıcı kalibrasyonu.

    `template` bir `LabelSheetTemplate` ya da doğrudan `SheetGeometry`;
    `calibration` bir `LabelCalibration`, `CalibrationOffset` ya da `None`.
    """

    content: LabelContent
    template: LabelSheetTemplate | SheetGeometry
    calibration: LabelCalibration | CalibrationOffset | None = None

    def geometry(self) -> SheetGeometry:
        if isinstance(self.template, SheetGeometry):
            return self.template
        return SheetGeometry.from_template(self.template)

    def offset(self) -> CalibrationOffset:
        if isinstance(self.calibration, CalibrationOffset):
            return self.calibration
        return CalibrationOffset.from_calibration(self.calibration)


@dataclass(frozen=True)
class RenderedLabels:
    """Motorun çıktısı: PDF + yerleşim planı (bütün parçalar için aynı)."""

    pdf: bytes
    placements: tuple[Placement, ...]
    contents: tuple[LabelContent, ...]
    sheets_per_part: int

    @property
    def page_count(self) -> int:
        return self.sheets_per_part * len(self.contents)


def build_parts(
    selection: LabelSelection | str,
    *,
    template: LabelSheetTemplate | SheetGeometry,
    calibration: LabelCalibration | CalibrationOffset | None = None,
    spine_template: LabelSheetTemplate | SheetGeometry | None = None,
    spine_calibration: LabelCalibration | CalibrationOffset | None = None,
) -> tuple[LabelPart, ...]:
    """Kullanıcı seçiminden parçalar. `BOTH`'ta sırt ayrı tabakadaysa `spine_*` verilir.

    `spine_template` verilmezse sırt da `template`'e (ve onun kalibrasyonuna)
    basılır; `spine_template` verilip `spine_calibration` verilmezse sırt
    kalibrasyonsuz basılır.
    """
    secim = parse_selection(selection)
    parcalar: list[LabelPart] = []
    for icerik in SELECTION_CONTENTS[secim]:
        if icerik == LabelContent.SPINE and secim == LabelSelection.BOTH and spine_template:
            parcalar.append(LabelPart(icerik, spine_template, spine_calibration))
        else:
            parcalar.append(LabelPart(icerik, template, calibration))
    return tuple(parcalar)


def _validate_part(part: LabelPart) -> SheetGeometry:
    from apps.kutuphane.models import LabelCalibration, LabelKind, LabelSheetTemplate

    sablon = part.template
    if isinstance(sablon, LabelSheetTemplate):
        if sablon.deleted_at is not None:
            raise LabelError("Etiket şablonu silinmiş.")
        if sablon.kind == LabelKind.CARD:
            raise LabelError("Üye kartı şablonu etikete kullanılamaz; etiket şablonu seçin.")
    kalibrasyon = part.calibration
    if isinstance(kalibrasyon, LabelCalibration):
        if kalibrasyon.deleted_at is not None:
            raise LabelError("Kalibrasyon kaydı silinmiş.", field="calibration")
        if isinstance(sablon, LabelSheetTemplate) and kalibrasyon.template_id != sablon.pk:
            raise LabelError(
                "Seçilen kalibrasyon bu etiket şablonuna ait değil.", field="calibration"
            )
    geometri = part.geometry()
    geometri.validate()
    part.offset().validate()
    return geometri


def _school_short_name(value: str | None) -> str:
    if value is not None:
        return value
    from apps.okul.models import SchoolConfig

    return SchoolConfig.load().kisa_ad


def _text_context(box: TextBox) -> dict[str, str]:
    sinif = _ALIGN_CSS.get(box.align, "c")
    return {
        "css": f"{sinif} b" if box.bold else sinif,
        "text": box.text,
        "left": mm_text(box.left),
        "top": mm_text(box.top),
        "width": mm_text(box.width),
        "height": mm_text(box.height),
        "size": f"{box.size_pt:.2f}",
    }


def _layout_context(layout: LabelLayout) -> dict[str, Any]:
    return {
        "texts": [_text_context(kutu) for kutu in layout.texts],
        "graphics": [
            {
                "svg": g.svg,
                "left": mm_text(g.left),
                "top": mm_text(g.top),
                "width": mm_text(g.width),
                "height": mm_text(g.height),
            }
            for g in layout.graphics
        ],
    }


def build_document_context(
    items: Sequence[LabelItem],
    parts: Sequence[LabelPart],
    *,
    start_cell: int = 1,
    school_short_name: str | None = None,
    include_qr: bool = False,
    title: str = "Etiket",
) -> tuple[dict[str, Any], tuple[Placement, ...], int]:
    """Şablon bağlamı + yerleşim planı + parça başına tabaka sayısı (PDF'siz; test edilebilir)."""
    kalemler = validate_items(items, field="items")
    if not parts:
        raise LabelError("En az bir etiket türü seçilmelidir.", field="content")
    icerikler = [parca.content for parca in parts]
    if len(set(icerikler)) != len(icerikler):
        raise LabelError("Aynı etiket türü iki kez seçilmiş.", field="content")
    if LabelContent.BLANK_BARCODE in icerikler and len(icerikler) > 1:
        raise LabelError(
            "Boş barkod etiketi künye taşımaz; sırt etiketiyle birlikte basılmaz.", field="content"
        )
    geometriler = [_validate_part(parca) for parca in parts]
    if len({g.same_grid_key for g in geometriler}) > 1:
        raise LabelError(
            "Sırt ve barkod etiketleri aynı sıra ve hücre düzeninde basılır; iki şablonun "
            "satır ve sütun sayısı aynı olmalıdır.",
            field="spine_template",
        )
    kapasite = geometriler[0].capacity
    plan = plan_placements(len(kalemler), capacity=kapasite, start_cell=start_cell)
    tabaka_sayisi = sheet_count(len(kalemler), capacity=kapasite, start_cell=start_cell)
    okul = _school_short_name(school_short_name)

    tabakalar: list[dict[str, Any]] = []
    for parca, geometri in zip(parts, geometriler, strict=True):
        kayma = parca.offset()
        qr = include_qr and parca.content != LabelContent.SPINE
        hucreler: list[list[dict[str, Any]]] = [[] for _ in range(tabaka_sayisi)]
        for yer in plan:
            kalem = kalemler[yer.item_index]
            if kalem.held:
                continue  # hücre boş kalır, yeri tutulur (sonraki etiketler kaymaz)
            hucre = geometri.cell(yer.cell_index, kayma)
            duzen = label_layout(kalem, hucre, content=parca.content, school=okul, include_qr=qr)
            hucreler[yer.sheet].append(
                {
                    "left": mm_text(hucre.left),
                    "top": mm_text(hucre.top),
                    "width": mm_text(hucre.width),
                    "height": mm_text(hucre.height),
                    **_layout_context(duzen),
                }
            )
        tabakalar.extend(
            {"content": parca.content.value, "number": sira + 1, "cells": tabaka}
            for sira, tabaka in enumerate(hucreler)
        )
    baglam = {"document_title": title, "sheets": tabakalar}
    return baglam, plan, tabaka_sayisi


def render_labels(
    items: Sequence[LabelItem],
    parts: Sequence[LabelPart],
    *,
    start_cell: int = 1,
    school_short_name: str | None = None,
    include_qr: bool = False,
    title: str = "Etiket",
) -> RenderedLabels:
    """Etiket PDF'ini üretir. Ret durumunda `LabelError` (uçta 400).

    - `items`: `items_from_copies(...)` ya da `items_from_barcodes(...)`; sıra korunur.
    - `parts`: `build_parts(...)` ya da elle `LabelPart` listesi (1 ya da 2 parça).
    - `start_cell`: ilk tabakada basımın başladığı hücre (1 tabanlı).
    - `school_short_name`: `None` ise `SchoolConfig.kisa_ad`.
    - `include_qr`: yalnız barkod etiketlerine; 48,5 × 25,4 mm ve üstü şablon ister.
    """
    baglam, plan, tabaka_sayisi = build_document_context(
        items,
        parts,
        start_cell=start_cell,
        school_short_name=school_short_name,
        include_qr=include_qr,
        title=title,
    )
    pdf = html_to_pdf(render_to_string(TEMPLATE_NAME, baglam))
    return RenderedLabels(
        pdf=pdf,
        placements=plan,
        contents=tuple(parca.content for parca in parts),
        sheets_per_part=tabaka_sayisi,
    )


class LabelJobLike(Protocol):
    """Basım kuyruğunun iş tanımıyla (`services.label_render.LabelJob`) aynı alanlar.

    Salt okunur özellikler olarak tanımlıdır: kuyruğun işi dondurulmuş
    (`frozen`) bir dataclass'tır.
    """

    @property
    def kind(self) -> str: ...
    @property
    def template(self) -> LabelSheetTemplate: ...
    @property
    def calibration(self) -> LabelCalibration | None: ...
    @property
    def start_cell(self) -> int: ...
    @property
    def copies(self) -> Sequence[Copy]: ...
    @property
    def barcodes(self) -> Sequence[str]: ...
    @property
    def spine_template(self) -> LabelSheetTemplate | None: ...
    @property
    def spine_calibration(self) -> LabelCalibration | None: ...
    @property
    def include_qr(self) -> bool: ...
    @property
    def hold_unprintable(self) -> bool: ...


def render_label_job(job: LabelJobLike) -> RenderedLabels:
    """Basım partisi / boş barkod aralığı işini basar (kuyruk kolunun bağlantı noktası).

    `kind`: `SPINE` · `BARCODE` · `BOTH` · `BLANK` ya da `BLANK_BARCODE`. Boş
    barkodda `barcodes`, diğerlerinde `copies` kullanılır; ikisinde de sıra
    korunur. Belge adı PDF başlığına yazılır. `hold_unprintable` (partinin
    PDF'i): sonradan silinmiş ya da elden çıkmış nüshanın hücresi boş kalır.
    """
    secim = parse_selection(job.kind)
    if secim == LabelSelection.BLANK_BARCODE:
        kalemler = items_from_barcodes(job.barcodes)
    else:
        kalemler = items_from_copies(job.copies, hold_unprintable=job.hold_unprintable)
    parcalar = build_parts(
        secim,
        template=job.template,
        calibration=job.calibration,
        spine_template=job.spine_template,
        spine_calibration=job.spine_calibration,
    )
    return render_labels(
        kalemler,
        parcalar,
        start_cell=job.start_cell,
        include_qr=job.include_qr,
        title=DOCUMENT_NAMES[secim],
    )
