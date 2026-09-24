"""Etiket şablonu ve yazıcı kalibrasyonu yazma servisleri (View → Service → Model).

Kurallar:

- **Izgara A4'e sığmalıdır** (`SheetGeometry.validate`); sığmayan şablon hiç
  kaydedilmez — basımda değil tanımda reddedilir.
- **Tür başına tek varsayılan şablon.** Yeni varsayılan atanırken eskisi AYNI
  işlemde kapatılır (önce kapat, sonra ata): kısmi tekil kısıt
  (`uq_labelsheet_default_per_kind`) ara durumda ihlal edilmez.
- **Ad tekilliği** Türkçe katlamayla denetlenir ("Sırt" ile "SIRT" aynı ad).
- **Kalibrasyon şablon × yazıcı başına tektir** (canlı kayıtlar arasında);
  yazıcı adı da Türkçe katlamayla karşılaştırılır. Kayma ±10 mm'yi aşamaz.
- **Silme yumuşaktır.** Şablon silinince kalibrasyonları da AÇIKÇA silinir:
  yumuşak silmede `CASCADE` tetiklenmez (CLAUDE.md §3).

Hatalar Django `ValidationError`'dır (alan adlı); `kd_exception_handler` 400'e çevirir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.kutuphane.keys import fold_search
from apps.kutuphane.labels.geometry import CalibrationOffset, SheetGeometry
from apps.kutuphane.labels.metrics import clean_text
from apps.kutuphane.models import LabelCalibration, LabelKind, LabelSheetTemplate

TEMPLATE_FIELDS = (
    "name",
    "kind",
    "page_margin_top",
    "page_margin_left",
    "label_width",
    "label_height",
    "rows",
    "cols",
    "gutter_x",
    "gutter_y",
    "corner_radius",
    "is_default",
)
CALIBRATION_FIELDS = ("template", "printer_name", "offset_x", "offset_y")


def _name_key(value: object) -> str:
    return fold_search(clean_text(value))


def _validate_template(template: LabelSheetTemplate) -> None:
    if not clean_text(template.name):
        raise ValidationError({"name": ["Şablon adı boş olamaz."]})
    if template.kind == LabelKind.CARD:
        # Üye kartı (85 × 54 mm) F6'nın işidir; etiket ekranından kart şablonu açılmaz.
        raise ValidationError({"kind": ["Üye kartı şablonu bu ekrandan tanımlanmaz."]})
    SheetGeometry.from_template(template).validate()
    anahtar = _name_key(template.name)
    for diger in LabelSheetTemplate.objects.exclude(pk=template.pk).only("pk", "name"):
        if _name_key(diger.name) == anahtar:
            raise ValidationError({"name": ["Bu adla bir etiket şablonu zaten var."]})


def _apply(obj: Any, fields: dict[str, Any], allowed: tuple[str, ...]) -> None:
    for ad, deger in fields.items():
        if ad not in allowed:
            raise ValidationError({ad: ["Bu alan değiştirilemez."]})
        setattr(obj, ad, deger)


def _save_template(template: LabelSheetTemplate) -> LabelSheetTemplate:
    template.name = clean_text(template.name)
    _validate_template(template)
    with transaction.atomic():
        if template.is_default:
            LabelSheetTemplate.objects.filter(kind=template.kind, is_default=True).exclude(
                pk=template.pk
            ).update(is_default=False, updated_at=timezone.now())
        template.save()
    return template


def create_template(**fields: Any) -> LabelSheetTemplate:
    sablon = LabelSheetTemplate()
    _apply(sablon, fields, TEMPLATE_FIELDS)
    return _save_template(sablon)


def update_template(template: LabelSheetTemplate, **fields: Any) -> LabelSheetTemplate:
    _apply(template, fields, TEMPLATE_FIELDS)
    return _save_template(template)


def delete_template(template: LabelSheetTemplate) -> None:
    """Şablonu ve kalibrasyonlarını yumuşak siler."""
    with transaction.atomic():
        LabelCalibration.objects.filter(template=template).update(
            deleted_at=timezone.now(), updated_at=timezone.now()
        )
        template.delete()


def _validate_calibration(calibration: LabelCalibration) -> None:
    if not calibration.printer_name:
        raise ValidationError({"printer_name": ["Yazıcı adı boş olamaz."]})
    sablon = calibration.template
    if sablon.deleted_at is not None:
        raise ValidationError({"template": ["Etiket şablonu silinmiş."]})
    CalibrationOffset(
        x=float(calibration.offset_x or Decimal("0")),
        y=float(calibration.offset_y or Decimal("0")),
    ).validate()
    anahtar = _name_key(calibration.printer_name)
    kardesler = LabelCalibration.objects.filter(template_id=calibration.template_id).exclude(
        pk=calibration.pk
    )
    for diger in kardesler.only("pk", "printer_name"):
        if _name_key(diger.printer_name) == anahtar:
            raise ValidationError(
                {"printer_name": ["Bu şablon için bu yazıcının kalibrasyonu zaten var."]}
            )


def _save_calibration(calibration: LabelCalibration) -> LabelCalibration:
    calibration.printer_name = clean_text(calibration.printer_name)
    _validate_calibration(calibration)
    calibration.save()
    return calibration


def create_calibration(**fields: Any) -> LabelCalibration:
    kalibrasyon = LabelCalibration()
    _apply(kalibrasyon, fields, CALIBRATION_FIELDS)
    return _save_calibration(kalibrasyon)


def update_calibration(calibration: LabelCalibration, **fields: Any) -> LabelCalibration:
    if "template" in fields and fields["template"].pk != calibration.template_id:
        raise ValidationError(
            {"template": ["Kalibrasyonun şablonu değiştirilemez; yeni kalibrasyon açın."]}
        )
    _apply(calibration, fields, CALIBRATION_FIELDS)
    return _save_calibration(calibration)


def delete_calibration(calibration: LabelCalibration) -> None:
    calibration.delete()
