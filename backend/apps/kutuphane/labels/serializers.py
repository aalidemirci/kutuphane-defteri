"""Etiket uçlarının serializer'ları (şablon, kalibrasyon, PDF istekleri).

Ölçüler JSON'da SAYI olarak gider (`coerce_to_string=False`): ön yüz tabaka
ızgarasını (başlangıç hücresi seçici) bu sayılarla çizer. Alan kümeleri
`tests/test_etiket_uclari.py`'de anlık görüntüyle sabitlenir (T13 — OpenAPI
yok, ön yüz tipleri elle yazılır).

Doğrulama iş kuralı YAZMAZ: ızgaranın A4'e sığması, varsayılan tekliği ve
kayma sınırı servistedir (`labels/services.py`, `labels/geometry.py`); burada
yalnız biçim ve aralık denetlenir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.kutuphane.labels.content import LabelContent, LabelSelection
from apps.kutuphane.labels.geometry import MAX_LABELS_PER_DOCUMENT, MAX_OFFSET_MM
from apps.kutuphane.labels.layout import supports
from apps.kutuphane.models import LabelCalibration, LabelKind, LabelSheetTemplate


def _mm_field(
    *, min_value: str = "0", max_value: str = "297", required: bool = True
) -> serializers.DecimalField:
    """Şablon ölçüsü (mm): iki ondalık, JSON'da sayı; A4'ten büyük ölçü anlamsızdır."""
    return serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        coerce_to_string=False,
        min_value=Decimal(min_value),
        max_value=Decimal(max_value),
        required=required,
    )


def _offset_field() -> serializers.DecimalField:
    """Kalibrasyon kayması (mm): ±`MAX_OFFSET_MM`."""
    return serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        coerce_to_string=False,
        min_value=Decimal(str(-MAX_OFFSET_MM)),
        max_value=Decimal(str(MAX_OFFSET_MM)),
    )


class LabelSheetTemplateSerializer(serializers.ModelSerializer[LabelSheetTemplate]):
    """Etiket şablonu. `labels_per_sheet` ve `supports_qr` türetilir (salt okunur)."""

    kind = serializers.ChoiceField(
        choices=[
            (LabelKind.BARCODE, LabelKind.BARCODE.label),
            (LabelKind.SPINE, LabelKind.SPINE.label),
        ]
    )
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    page_margin_top = _mm_field()
    page_margin_left = _mm_field()
    label_width = _mm_field(min_value="1")
    label_height = _mm_field(min_value="1")
    gutter_x = _mm_field(required=False)
    gutter_y = _mm_field(required=False)
    corner_radius = _mm_field(max_value="20", required=False)
    rows = serializers.IntegerField(min_value=1, max_value=50)
    cols = serializers.IntegerField(min_value=1, max_value=20)
    labels_per_sheet = serializers.IntegerField(read_only=True)
    supports_qr = serializers.SerializerMethodField()
    supports_barcode = serializers.SerializerMethodField()

    class Meta:
        model = LabelSheetTemplate
        fields = [
            "id",
            "name",
            "kind",
            "kind_display",
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
            "labels_per_sheet",
            "supports_qr",
            "supports_barcode",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
        # Ad tekliği ve varsayılan tekliği servistedir (Türkçe katlamalı).
        validators: list[Any] = []

    def get_supports_qr(self, obj: LabelSheetTemplate) -> bool:
        """48,5 × 25,4 mm ve üstü etiket barkodun yanında QR taşıyabilir (§7.2)."""
        return supports(
            float(obj.label_width),
            float(obj.label_height),
            content=LabelContent.BARCODE,
            include_qr=True,
        )

    def get_supports_barcode(self, obj: LabelSheetTemplate) -> bool:
        """Barkod (sessiz bölgeleriyle 27,94 mm) ve metin satırları etikete sığıyor mu?"""
        return supports(
            float(obj.label_width), float(obj.label_height), content=LabelContent.BARCODE
        )


class LabelCalibrationSerializer(serializers.ModelSerializer[LabelCalibration]):
    """Yazıcı kalibrasyonu (şablon × yazıcı). Pozitif X sağa, pozitif Y aşağı."""

    template = serializers.PrimaryKeyRelatedField(
        queryset=LabelSheetTemplate.objects.all(),
        error_messages={"does_not_exist": "Etiket şablonu bulunamadı."},
    )
    template_name = serializers.CharField(source="template.name", read_only=True)
    printer_name = serializers.CharField(max_length=160)
    offset_x = _offset_field()
    offset_y = _offset_field()

    class Meta:
        model = LabelCalibration
        fields = [
            "id",
            "template",
            "template_name",
            "printer_name",
            "offset_x",
            "offset_y",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
        validators: list[Any] = []


def _template_field(*, required: bool = True) -> serializers.PrimaryKeyRelatedField[Any]:
    return serializers.PrimaryKeyRelatedField(
        queryset=LabelSheetTemplate.objects.all(),
        required=required,
        allow_null=not required,
        error_messages={"does_not_exist": "Etiket şablonu bulunamadı."},
    )


def _calibration_field() -> serializers.PrimaryKeyRelatedField[Any]:
    return serializers.PrimaryKeyRelatedField(
        queryset=LabelCalibration.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Kalibrasyon kaydı bulunamadı."},
    )


class CalibrationSheetRequestSerializer(serializers.Serializer[Any]):
    """`POST library/labels/calibration/` gövdesi."""

    template = _template_field()
    calibration = _calibration_field()


class LabelPreviewRequestSerializer(serializers.Serializer[Any]):
    """`POST library/labels/preview/` gövdesi — PDF üretir, hiçbir kayıt YAZMAZ.

    `content`: `SPINE` · `BARCODE` · `BOTH` (önce sırt, sonra barkod tabakaları)
    · `BLANK_BARCODE` (boş barkod etiketi; `barcodes` ister). Diğerleri `copy_ids`
    ister ve sıra korunur.
    """

    content = serializers.ChoiceField(choices=[s.value for s in LabelSelection])
    template = _template_field()
    calibration = _calibration_field()
    spine_template = _template_field(required=False)
    spine_calibration = _calibration_field()
    copy_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_LABELS_PER_DOCUMENT,
    )
    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        max_length=MAX_LABELS_PER_DOCUMENT,
    )
    start_cell = serializers.IntegerField(min_value=1, required=False, default=1)
    include_qr = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        secim = LabelSelection(attrs["content"])
        if secim == LabelSelection.BLANK_BARCODE:
            if not attrs.get("barcodes"):
                raise serializers.ValidationError(
                    {"barcodes": "Boş barkod etiketi için numara listesi gerekir."}
                )
            if attrs.get("copy_ids"):
                raise serializers.ValidationError(
                    {"copy_ids": "Boş barkod etiketi nüshaya değil numaraya basılır."}
                )
        else:
            if not attrs.get("copy_ids"):
                raise serializers.ValidationError({"copy_ids": "En az bir nüsha seçin."})
            if attrs.get("barcodes"):
                raise serializers.ValidationError(
                    {"barcodes": "Numara listesi yalnız boş barkod etiketinde kullanılır."}
                )
        if secim != LabelSelection.BOTH and attrs.get("spine_template"):
            raise serializers.ValidationError(
                {
                    "spine_template": (
                        "Ayrı sırt şablonu yalnız sırt ve barkod birlikte basılırken seçilir."
                    )
                }
            )
        if attrs.get("spine_calibration") and not attrs.get("spine_template"):
            raise serializers.ValidationError(
                {"spine_calibration": "Sırt kalibrasyonu için önce ayrı sırt şablonu seçin."}
            )
        return attrs
