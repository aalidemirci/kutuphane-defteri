"""Etiket kuyruğu, basım partileri ve boş barkod aralıkları — gövde ve yanıt biçimleri (F4-Q).

`serializers.py`'nin kuralları aynen geçerlidir: iş kuralı serializer'da
TEKRARLANMAZ (servis `ValidationError` yükseltir, `kd_exception_handler` 400'e
çevirir), kimlik ve işaret alanları salt okunurdur. Buradaki doğrulama gövdenin
BİÇİMİYLE sınırlıdır.

Yanıtlar kişisel veri taşımaz: nüsha özeti (barkod, eser adı, yer numarası,
bölüm) ve sayaçlar.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_kuyruk
from apps.kutuphane.models import (
    MAX_LABELS_PER_JOB,
    MAX_LABELS_PER_JOB_TEXT,
    BarcodeReservation,
    Copy,
    LabelCalibration,
    LabelOrder,
    LabelPrintBatch,
    LabelPrintBatchStatus,
    LabelPrintKind,
    LabelSheetTemplate,
    ReservedBarcode,
    ReservedBarcodeState,
)
from apps.kutuphane.serializers import CopyWriteSerializer, _iliski_hatalari

_SECIM_HATASI: dict[str, Any] = {"invalid_choice": "Geçerli bir seçenek seçin."}


def _template_field(**kwargs: Any) -> serializers.PrimaryKeyRelatedField[LabelSheetTemplate]:
    return serializers.PrimaryKeyRelatedField(
        queryset=LabelSheetTemplate.objects.all(),
        error_messages=_iliski_hatalari("etiket şablonu", "Etiket şablonu seçilmelidir."),
        **kwargs,
    )


def _calibration_field() -> serializers.PrimaryKeyRelatedField[LabelCalibration]:
    return serializers.PrimaryKeyRelatedField(
        queryset=LabelCalibration.objects.all(),
        required=False,
        allow_null=True,
        error_messages=_iliski_hatalari("kalibrasyon", "Kalibrasyon seçilmelidir."),
    )


def _start_cell_field(**kwargs: Any) -> serializers.IntegerField:
    return serializers.IntegerField(
        min_value=1,
        error_messages={
            "invalid": "Başlangıç hücresi sayısal olmalıdır.",
            "min_value": "Başlangıç hücresi en az 1 olmalıdır.",
        },
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Kuyruk
# ---------------------------------------------------------------------------
class LabelQueueCopySerializer(serializers.ModelSerializer[Copy]):
    """Kuyruk ve doğrulanmamışlar listesinin satırı — nüsha özeti + işaretler.

    `pending_batch`: nüsha onay bekleyen bir partideyse o partinin kimliği
    (bağlamdaki `pending_batches` sözlüğünden; D10 — PDF'i alınmış ama basıldı
    olarak işaretlenmemiş etiketi ikinci kez basmadan önce kullanıcı görsün).
    """

    work_title = serializers.CharField(source="work.title", read_only=True)
    work_authors = serializers.CharField(source="work.authors", read_only=True)
    call_number = serializers.CharField(source="work.call_number", read_only=True)
    section_name = serializers.SerializerMethodField()
    barcode_display = serializers.SerializerMethodField()
    pending_batch = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = [
            "id",
            "work",
            "work_title",
            "work_authors",
            "call_number",
            "acquisition",
            "accession_no",
            "barcode",
            "barcode_display",
            "section",
            "section_name",
            "label_printed_at",
            "label_verified_at",
            "spine_label_printed_at",
            "pending_batch",
            "created_at",
        ]
        read_only_fields = fields

    def get_section_name(self, obj: Copy) -> str | None:
        bolum = obj.section
        return bolum.name if bolum is not None else None

    def get_barcode_display(self, obj: Copy) -> str:
        return barcode_module.format_barcode(obj.barcode)

    def get_pending_batch(self, obj: Copy) -> int | None:
        bekleyen: dict[int, int] = self.context.get("pending_batches", {})
        return bekleyen.get(obj.pk)


# ---------------------------------------------------------------------------
# Basım partileri
# ---------------------------------------------------------------------------
class LabelBatchSerializer(serializers.ModelSerializer[LabelPrintBatch]):
    """Basım geçmişinin satırı (durum damgalardan türetilir)."""

    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    order_display = serializers.CharField(source="get_order_display", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    printer_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = LabelPrintBatch
        fields = [
            "id",
            "kind",
            "kind_display",
            "template",
            "template_name",
            "calibration",
            "printer_name",
            "spine_template",
            "spine_calibration",
            "include_qr",
            "order",
            "order_display",
            "start_cell",
            "copy_count",
            "status",
            "status_display",
            "created_at",
            "confirmed_at",
            "reverted_at",
            "discarded_at",
            "reprint_of",
        ]
        read_only_fields = fields

    def get_printer_name(self, obj: LabelPrintBatch) -> str | None:
        kalibrasyon = obj.calibration
        return kalibrasyon.printer_name if kalibrasyon is not None else None

    def get_status_display(self, obj: LabelPrintBatch) -> str:
        return str(LabelPrintBatchStatus(obj.status).label)


class LabelBatchDetailSerializer(LabelBatchSerializer):
    """Parti ayrıntısı: nüshalar BASIM SIRASINDA (`position` 1'den başlar).

    Kalemin `printable` alanı: nüsha sonradan silinmiş ya da elden çıkmışsa
    `false` — partinin PDF'inde hücresi boş kalır, onay işaretine dokunmaz.
    """

    items = serializers.SerializerMethodField()

    class Meta(LabelBatchSerializer.Meta):
        fields = [*LabelBatchSerializer.Meta.fields, "items"]
        read_only_fields = fields

    def get_items(self, obj: LabelPrintBatch) -> list[dict[str, Any]]:
        kalemler = obj.items.select_related("copy", "copy__work", "copy__section").order_by(
            "position"
        )
        return [
            {
                "position": kalem.position,
                **LabelQueueCopySerializer(kalem.copy).data,
                "printable": kalem.copy.is_labelable,
            }
            for kalem in kalemler
        ]


class LabelBatchCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Parti açma gövdesi — nüshalar ya AÇIKÇA (`copies`) ya KUYRUKTAN (`from_queue`).

    Kuyruktan seçimde süzgeçler kuyruk ucundakilerle aynıdır ve kuyruk türü
    partinin içeriğidir (`kind`); seçilen sıradaki ilk `limit` nüsha alınır.
    """

    kind = serializers.ChoiceField(choices=LabelPrintKind.choices, error_messages=_SECIM_HATASI)
    template = _template_field()
    calibration = _calibration_field()
    spine_template = _template_field(required=False, allow_null=True)
    spine_calibration = _calibration_field()
    include_qr = serializers.BooleanField(default=False)
    order = serializers.ChoiceField(
        choices=LabelOrder.choices, default=LabelOrder.CALL_NUMBER, error_messages=_SECIM_HATASI
    )
    start_cell = _start_cell_field(default=1)
    copies = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_LABELS_PER_JOB,
        error_messages={
            "max_length": f"Bir basım partisine en çok {MAX_LABELS_PER_JOB_TEXT} nüsha girer.",
        },
    )
    from_queue = serializers.BooleanField(default=False)
    limit = serializers.IntegerField(
        min_value=1, max_value=MAX_LABELS_PER_JOB, default=MAX_LABELS_PER_JOB
    )
    section = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    acquisition = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    reservation = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    created_from = serializers.DateField(required=False, allow_null=True)
    created_to = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        secili = attrs.get("copies")
        if attrs.get("from_queue"):
            if secili:
                raise serializers.ValidationError(
                    {"copies": "Ya nüshaları seçin ya da kuyruktan basın; ikisi birden olmaz."}
                )
        elif not secili:
            raise serializers.ValidationError({"copies": "Etiketi basılacak nüshaları seçin."})
        return attrs


class LabelBatchReprintSerializer(serializers.Serializer[dict[str, Any]]):
    """Yeniden basım gövdesi — verilmeyen ayar eski partiden alınır."""

    kind = serializers.ChoiceField(
        choices=LabelPrintKind.choices, required=False, error_messages=_SECIM_HATASI
    )
    template = _template_field(required=False)
    calibration = _calibration_field()
    start_cell = _start_cell_field(required=False)


class LabelVerifySerializer(serializers.Serializer[dict[str, Any]]):
    """Doğrulama okutması gövdesi: okutulan kod (boş da gelebilir — ileti döner)."""

    code = serializers.CharField(max_length=64, allow_blank=True, trim_whitespace=True)


# ---------------------------------------------------------------------------
# Boş barkod aralıkları
# ---------------------------------------------------------------------------
class BarcodeReservationSerializer(serializers.ModelSerializer[BarcodeReservation]):
    """Aralık satırı + numara durum sayaçları (aralık raporu)."""

    first_barcode_display = serializers.SerializerMethodField()
    last_barcode_display = serializers.SerializerMethodField()
    open_count = serializers.SerializerMethodField()
    bound_count = serializers.SerializerMethodField()
    cancelled_count = serializers.SerializerMethodField()

    class Meta:
        model = BarcodeReservation
        fields = [
            "id",
            "year",
            "first_barcode",
            "first_barcode_display",
            "last_barcode",
            "last_barcode_display",
            "count",
            "note",
            "printed_at",
            "open_count",
            "bound_count",
            "cancelled_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_first_barcode_display(self, obj: BarcodeReservation) -> str:
        return barcode_module.format_barcode(obj.first_barcode)

    def get_last_barcode_display(self, obj: BarcodeReservation) -> str:
        return barcode_module.format_barcode(obj.last_barcode)

    @staticmethod
    def _sayac(obj: BarcodeReservation, ad: str) -> int:
        """`annotate` sayacı (liste sorgusu); yoksa satırlardan sayılır (yeni kayıt)."""
        deger = getattr(obj, ad, None)
        if deger is not None:
            return int(deger)
        numaralar = obj.numbers.all()
        if ad == "bound_count":
            return numaralar.filter(copy__isnull=False).count()
        if ad == "cancelled_count":
            return numaralar.filter(cancelled_at__isnull=False).count()
        return numaralar.filter(copy__isnull=True, cancelled_at__isnull=True).count()

    def get_open_count(self, obj: BarcodeReservation) -> int:
        return self._sayac(obj, "open_count")

    def get_bound_count(self, obj: BarcodeReservation) -> int:
        return self._sayac(obj, "bound_count")

    def get_cancelled_count(self, obj: BarcodeReservation) -> int:
        return self._sayac(obj, "cancelled_count")


class ReservedBarcodeSerializer(serializers.ModelSerializer[ReservedBarcode]):
    """Aralıktaki tek numara: durum ve (bağlıysa) nüshanın eser adı."""

    barcode_display = serializers.SerializerMethodField()
    state = serializers.CharField(read_only=True)
    state_display = serializers.SerializerMethodField()
    work_title = serializers.SerializerMethodField()

    class Meta:
        model = ReservedBarcode
        fields = [
            "barcode",
            "barcode_display",
            "state",
            "state_display",
            "copy",
            "work_title",
            "bound_at",
            "cancelled_at",
            "cancel_reason",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: ReservedBarcode) -> str:
        return barcode_module.format_barcode(obj.barcode)

    def get_state_display(self, obj: ReservedBarcode) -> str:
        return str(ReservedBarcodeState(obj.state).label)

    def get_work_title(self, obj: ReservedBarcode) -> str:
        nusha = obj.copy
        return nusha.work.title if nusha is not None else ""


class BarcodeReservationDetailSerializer(BarcodeReservationSerializer):
    """Aralık ayrıntısı: numaraların tamamı (aralık en çok `MAX_LABELS_PER_JOB`)."""

    numbers = serializers.SerializerMethodField()

    class Meta(BarcodeReservationSerializer.Meta):
        fields = [*BarcodeReservationSerializer.Meta.fields, "numbers"]
        read_only_fields = fields

    def get_numbers(self, obj: BarcodeReservation) -> Any:
        return ReservedBarcodeSerializer(selectors_kuyruk.reservation_numbers(obj), many=True).data


class BarcodeReservationCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """Aralık ayırma gövdesi: adet (+ isteğe bağlı kısa açıklama)."""

    count = serializers.IntegerField(
        min_value=1,
        max_value=MAX_LABELS_PER_JOB,
        error_messages={
            "invalid": "Adet sayısal olmalıdır.",
            "required": "Kaç numara ayrılacağını yazın.",
            "min_value": "En az 1 numara ayrılır.",
            "max_value": f"Tek seferde en çok {MAX_LABELS_PER_JOB_TEXT} numara ayrılır.",
        },
    )
    note = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class ReservationCancelSerializer(serializers.Serializer[dict[str, Any]]):
    """İptal gövdesi: `barcodes` verilmezse aralığın bütün açık numaraları iptal edilir."""

    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=32), required=False, max_length=MAX_LABELS_PER_JOB
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ReservationPdfParamsSerializer(serializers.Serializer[dict[str, Any]]):
    """Boş etiket PDF'inin sorgu parametreleri (`barcodes` virgülle ayrılmış liste)."""

    template = _template_field()
    calibration = _calibration_field()
    start_cell = _start_cell_field(default=1)
    include_qr = serializers.BooleanField(default=False)
    barcodes = serializers.CharField(required=False, allow_blank=True, max_length=20000)


class CopyFromLabelSerializer(CopyWriteSerializer):
    """Hızlı kayıtta bağlama gövdesi: nüsha alanları + kitaptaki etiketin okutulan kodu."""

    label_code = serializers.CharField(
        max_length=64,
        error_messages={
            "required": "Kitaba yapıştırdığınız kütüphane etiketini okutun.",
            "blank": "Kitaba yapıştırdığınız kütüphane etiketini okutun.",
        },
    )

    class Meta(CopyWriteSerializer.Meta):
        fields = [*CopyWriteSerializer.Meta.fields, "label_code"]
