"""Etiket motoru (F4, tasarım §7.1-7.2, §8.1 yöntem B, E1).

Katmanlar:

- `geometry` — tabaka ızgarası, kalibrasyon kayması, başlangıç hücresi,
  yerleşim planı, barkodun yazıcı noktasına hizalanması (saf hesap).
- `metrics` — DejaVu genişlik tablosu, Türkçe güvenli kırpma.
- `content` — basılacak kalemler (nüsha ya da numara), yer numarasının satırları.
- `layout` — tek etiketin iç düzeni (metin, Code128-C, isteğe bağlı QR).
- `render` — etiket PDF'i (`render_labels`); `calibration` — kalibrasyon sayfası.
- `seed` — hazır şablonlar (`ensure_default_templates`); `services` — şablon ve
  kalibrasyon yazma; `serializers`, `views`, `urls` — uçlar.

**Başka kolların motoru çağırma biçimi** (basım partisi, boş barkod aralığı)::

    from apps.kutuphane.labels import (
        LabelSelection, build_parts, items_from_barcodes, items_from_copies, render_labels,
    )

    sonuc = render_labels(
        items_from_copies(nushalar),            # ya da items_from_barcodes(numaralar)
        build_parts(LabelSelection.BOTH, template=sablon, calibration=kalibrasyon),
        start_cell=3,                            # 1 tabanlı; ilk tabakada
    )
    sonuc.pdf, sonuc.placements, sonuc.sheets_per_part

Motor veritabanına YAZMAZ (D10): PDF üretmek "basıldı" demek değildir.
Retler `LabelError`dır (Django `ValidationError`, alan adlı) ve uçta 400 olur.
"""

from __future__ import annotations

from apps.kutuphane.labels.calibration import render_calibration_sheet
from apps.kutuphane.labels.content import (
    LabelContent,
    LabelItem,
    LabelSelection,
    items_from_barcodes,
    items_from_copies,
    split_call_number,
)
from apps.kutuphane.labels.geometry import (
    CalibrationOffset,
    LabelError,
    Placement,
    SheetGeometry,
    plan_placements,
    sheet_count,
)
from apps.kutuphane.labels.render import (
    DOCUMENT_NAMES,
    LabelPart,
    RenderedLabels,
    build_parts,
    render_label_job,
    render_labels,
)

__all__ = [
    "DOCUMENT_NAMES",
    "CalibrationOffset",
    "LabelContent",
    "LabelError",
    "LabelItem",
    "LabelPart",
    "LabelSelection",
    "Placement",
    "RenderedLabels",
    "SheetGeometry",
    "build_parts",
    "items_from_barcodes",
    "items_from_copies",
    "plan_placements",
    "render_calibration_sheet",
    "render_label_job",
    "render_labels",
    "sheet_count",
    "split_call_number",
]
