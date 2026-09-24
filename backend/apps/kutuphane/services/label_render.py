"""Etiket PDF'inin kuyruk tarafındaki TEK kapısı (F4-Q ↔ F4-L arayüzü).

Basım kuyruğu (bu kol) NE basılacağını ve HANGİ SIRAYLA basılacağını bilir;
etiket motoru (`apps.kutuphane.labels`, L kolu) hücre konumlarını, içerik
üreticilerini, HTML'i ve PDF'i (yalnız `shared.pdf.html_to_pdf`) bilir. İkisi
arasındaki sözleşme bu dosyadaki `LabelJob`'dır:

- `copies` basım SIRASINDADIR (D20 — sıra kuyrukta seçilir, motor sıralamaz).
  Sırt ve barkod etiketi "ikisi birden" basılırken motor AYNI sırayı ve AYNI
  hücre düzenini kullanır (§7.2): iki tabakanın N. hücresi aynı kitabındır.
- `start_cell` **1'den başlar** (kullanıcının gördüğü "1. hücre"; satır satır,
  soldan sağa); motor da 1 tabanlıdır.
- `barcodes` yalnız `kind == BLANK_KIND` iken doludur: önceden basılmış boş
  barkod etiketleri (yöntem B) — yalnız barkod + okunur numara + kısa okul adı.
- `calibration` boş olabilir (kaymasız basım).
- `hold_unprintable` yalnız basım partisinin PDF'inde açıktır: partideki bir
  nüsha sonradan silinmiş ya da elden çıkmışsa etiketi basılmaz, hücresi boş
  kalır ve sonraki etiketler kaymaz (parti bir iz kaydıdır — D10).

**PDF üretmek "basıldı" DEĞİLDİR** (D10): bu kapı hiçbir işarete dokunmaz;
işaret `services.label_queue.confirm_batch` ile yazılır.

**Bağlantı.** L kolu bu kolla paralel yazıldı ve `LabelJob`'ı olduğu gibi
kabul eden `apps.kutuphane.labels.render_label_job`'ı sundu (`kind` için
"BLANK" eş adını da tanır). Bağlantı yalnız `render_job` işlevinin gövdesidir;
motorun içe aktarımı TEMBELDİR (WeasyPrint ağırdır, kuyruk uçları onu
yüklemez). Motor paketi yüklenemezse `LabelRendererUnavailable` yükselir ve uç
503 döner — kuyruk, basım kaydı, onay ve geri alma motorsuz da çalışır.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError

from apps.kutuphane.models import Copy, LabelCalibration, LabelKind, LabelSheetTemplate

#: Önceden basılmış (boş) barkod etiketinin iş türü — `LabelPrintKind` DIŞINDADIR,
#: çünkü nüshası yoktur (bkz. `models.LabelPrintKind`).
BLANK_KIND = "BLANK"


class LabelRendererUnavailable(RuntimeError):
    """Etiket motoru yüklenemedi (bozuk kurulum) — uçta 503 `etiket_motoru_yok`."""


@dataclass(frozen=True)
class LabelJob:
    """Motorun bir basım işi için ihtiyaç duyduğu HER ŞEY (sıra dahil)."""

    kind: str
    template: LabelSheetTemplate
    calibration: LabelCalibration | None
    start_cell: int
    copies: Sequence[Copy] = field(default_factory=tuple)
    barcodes: Sequence[str] = field(default_factory=tuple)
    spine_template: LabelSheetTemplate | None = None
    spine_calibration: LabelCalibration | None = None
    include_qr: bool = False
    hold_unprintable: bool = False


def _validate_sheet(
    template: LabelSheetTemplate,
    calibration: LabelCalibration | None,
    *,
    template_field: str,
    calibration_field: str,
) -> None:
    if template.deleted_at is not None:
        raise ValidationError({template_field: "Seçilen etiket şablonu silinmiş; başkasını seçin."})
    if template.kind == LabelKind.CARD:
        raise ValidationError(
            {
                template_field: "Üye kartı şablonu etiket basımında kullanılmaz; etiket şablonu seçin."
            }
        )
    if calibration is None:
        return
    if calibration.deleted_at is not None:
        raise ValidationError({calibration_field: "Seçilen kalibrasyon silinmiş; başkasını seçin."})
    if calibration.template_id != template.pk:
        raise ValidationError(
            {calibration_field: "Seçilen kalibrasyon bu etiket şablonuna ait değil."}
        )


def validate_print_setup(
    *,
    template: LabelSheetTemplate,
    calibration: LabelCalibration | None,
    start_cell: int,
    spine_template: LabelSheetTemplate | None = None,
    spine_calibration: LabelCalibration | None = None,
) -> None:
    """Basım ayarının tutarlılığı — parti AÇILIRKEN, basımdan önce reddetmek için.

    - Silinmiş şablon ya da kalibrasyon kullanılmaz (CLAUDE.md §3: yumuşak silme
      ileri FK'da süzmez, canlılık elle denetlenir).
    - Üye kartı şablonu etiket basımında kullanılmaz (kart F6'nın işidir).
    - Kalibrasyon şablon + yazıcı çiftine aittir (§7.2): başka şablonun
      kalibrasyonu, bu tabakanın hücrelerini yanlış yere kaydırırdı.
    - Ayrı sırt tabakası ana tabakayla AYNI satır ve sütun sayısında olmalıdır:
      sırt ve barkod etiketi aynı sıra ve hücre düzeninde basılır (§7.2).
    - Başlangıç hücresi tabakanın içinde olmalıdır (1 … satır × sütun).

    Etiket motoru aynı denetimleri basımda da yapar (savunma derinliği); burada
    yapılmaları, hatalı ayarla "basım onayı bekliyor" bir parti açılmasın diyedir.
    """
    _validate_sheet(
        template, calibration, template_field="template", calibration_field="calibration"
    )
    if spine_template is None and spine_calibration is not None:
        raise ValidationError(
            {"spine_calibration": "Sırt kalibrasyonu yalnız ayrı bir sırt şablonuyla seçilir."}
        )
    if spine_template is not None:
        _validate_sheet(
            spine_template,
            spine_calibration,
            template_field="spine_template",
            calibration_field="spine_calibration",
        )
        if (spine_template.rows, spine_template.cols) != (template.rows, template.cols):
            raise ValidationError(
                {
                    "spine_template": (
                        "Sırt ve barkod etiketleri aynı sıra ve hücre düzeninde basılır; iki "
                        "şablonun satır ve sütun sayısı aynı olmalıdır."
                    )
                }
            )
    hucre = int(template.labels_per_sheet)
    if not 1 <= int(start_cell) <= hucre:
        raise ValidationError(
            {"start_cell": f"Başlangıç hücresi 1 ile {hucre} arasında olmalıdır."}
        )


def render_job(job: LabelJob) -> bytes:
    """İşi PDF'e çevirir — etiket motoruna giden TEK nokta (işaretlere dokunmaz).

    Motorun retleri (`LabelError`, Django `ValidationError`'ı) olduğu gibi
    geçer ve uçta 400 olur. Kuyruk testleri bu işlevi `monkeypatch` ile sahte
    motorla değiştirir; gerçek motorla uçtan uca akış
    `tests/test_bos_barkod_uctan_uca.py`'dedir.
    """
    try:
        from apps.kutuphane.labels import render_label_job
    except ImportError as exc:  # pragma: no cover - paket her dağıtımda vardır
        raise LabelRendererUnavailable(
            "Etiket basım motoru yüklenemedi. Programı yeniden kurun."
        ) from exc
    return bytes(render_label_job(job).pdf)
