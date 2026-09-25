"""Teslim, kayıp/hasar ve onarım uçlarının serializer'ları ve ALAN LİSTELERİ (F7).

Bu dosyanın yanıtları YALNIZ yönetici kipindedir, tek istisnası geri alma
okutmasıdır (`library-delivery-take-back`, §4.4 "Teslimden geri alma
okutması"): görevli kipinde o yanıt DARALIR — `STAFF_TAKE_BACK_FIELDS`
(sonuç, ileti ve nüsha özeti: barkod + eser adı). Teslim alanın kimliği, teslim
tarihi ve belge no görevliye gösterilmez. Alan listeleri anlık görüntüyle
sabittir (`tests/test_teslim_uclari.py`).

Kurallar (`serializers.py` ile aynı): iş kuralı serializer'da TEKRARLANMAZ;
servis (`services.deliveries`, `services.loss_damage`) Django `ValidationError`
yükseltir ve `kd_exception_handler` alan adlarıyla 400'e çevirir.

**Profil yasağı** (CLAUDE.md §2-5): teslim ve dosya satırları konu, sınıflama ya
da bölüm alanı TAŞIMAZ. **Bedel yalnız kayıttır** (Md. 19): ödeme ya da tahsilat
alanı yoktur; dil "bedel belirlendi", "bedel teslim alındı"dır. Dosyanın
`is_person_open_work` alanı dosyanın kişinin açık işi olup olmadığını söyler
("Bedel teslim alındı" dosyası açıktır ama yalnız okulun işidir).
"""

from __future__ import annotations

from typing import Any, Final

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_teslim
from apps.kutuphane.models import (
    CaseResolution,
    CaseType,
    CopyRepair,
    Delivery,
    LossDamageCase,
)

# ---------------------------------------------------------------------------
# Alan listeleri
# ---------------------------------------------------------------------------
#: Geri alma okutması — görevli kipinde teslim alanın kimliği YOK (§4.4).
STAFF_TAKE_BACK_FIELDS: Final[tuple[str, ...]] = ("result", "kind", "message", "copy")
ADMIN_TAKE_BACK_FIELDS: Final[tuple[str, ...]] = ("result", "kind", "message", "copy", "delivery")
#: Yönetici kipinde geri almanın teslim ayrıntısı.
TAKE_BACK_DELIVERY_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "recipient_kind",
    "recipient_kind_display",
    "recipient_label",
    "delivered_on",
    "expected_return",
    "document_no",
    "returned_at",
)

DELIVERY_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "copy",
    "barcode",
    "barcode_display",
    "work_title",
    "call_number",
    "recipient_kind",
    "recipient_kind_display",
    "section",
    "personnel",
    "recipient_label",
    "delivered_on",
    "expected_return",
    "expected_return_passed",
    "document_no",
    "status",
    "status_display",
    "returned_at",
    "lost_at",
)

CASE_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "copy",
    "barcode",
    "barcode_display",
    "work_title",
    "copy_status",
    "copy_status_display",
    "case_type",
    "case_type_display",
    "membership",
    "loan",
    "delivery",
    "responsible_name",
    "responsible_class_label",
    "responsible_note",
    "reported_on",
    "market_price",
    "price_determined_at",
    "price_received_at",
    "resolution",
    "resolution_display",
    "is_open",
    "is_person_open_work",
    "resolved_at",
    "write_off_proposed_at",
    "allowed_resolutions",
    "price_options_available",
    "created_at",
)

REPAIR_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "copy",
    "barcode",
    "barcode_display",
    "work_title",
    "case",
    "sent_on",
    "returned_on",
)

#: Okutulan kodun gövdedeki üst sınırı (`serializers_masa.KOD_UZUNLUGU` ile aynı).
KOD_UZUNLUGU: Final = 64
#: Sorumlu notunun üst sınırı (karakter).
RESPONSIBLE_NOTE_MAX: Final = 500


# ---------------------------------------------------------------------------
# Teslim
# ---------------------------------------------------------------------------
class DeliveryCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/deliveries/` — toplu teslim: `{section_id | personnel_id, barcodes, …}`."""

    section_id = serializers.IntegerField(min_value=1, required=False)
    personnel_id = serializers.IntegerField(min_value=1, required=False)
    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=KOD_UZUNLUGU, allow_blank=True),
        allow_empty=False,
        error_messages={"empty": "Teslim edilecek kitap okutulmadı."},
    )
    delivered_on = serializers.DateField(required=False)
    expected_return = serializers.DateField(required=False, allow_null=True)
    document_no = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if ("section_id" in attrs) == ("personnel_id" in attrs):
            raise serializers.ValidationError("Teslim için bir şube ya da bir öğretmen seçin.")
        return attrs


class DeliveryScanSerializer(serializers.Serializer[dict[str, Any]]):
    """Okutma gövdesi: `{barcode}` YA DA (okuyucu kuyruğu) `{barcodes: [...]}`."""

    barcode = serializers.CharField(max_length=KOD_UZUNLUGU, required=False, allow_blank=True)
    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=KOD_UZUNLUGU, allow_blank=True),
        required=False,
        allow_empty=False,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if ("barcode" in attrs) == ("barcodes" in attrs):
            raise serializers.ValidationError("Kitabın kütüphane etiketini okutun.")
        return attrs


class DeliveryCheckSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/deliveries/check/` — teslim listesine okutulan tek kod."""

    barcode = serializers.CharField(max_length=KOD_UZUNLUGU, allow_blank=True)


class DeliverySerializer(serializers.ModelSerializer[Delivery]):
    """Teslim satırı (yönetici kipi) — teslim alanın adı dahil (öğretmen adı şifreli)."""

    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    call_number = serializers.CharField(source="copy.work.call_number", read_only=True)
    recipient_kind_display = serializers.CharField(
        source="get_recipient_kind_display", read_only=True
    )
    recipient_label = serializers.SerializerMethodField()
    expected_return_passed = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Delivery
        fields = list(DELIVERY_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: Delivery) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)

    def get_recipient_label(self, obj: Delivery) -> str:
        return selectors_teslim.delivery_recipient_label(obj)

    def get_expected_return_passed(self, obj: Delivery) -> bool:
        """Açık teslimin beklenen dönüşü geçti mi? (ödünç gecikmesi DEĞİLDİR — bilgi)."""
        from django.utils import timezone

        return (
            obj.is_open
            and obj.expected_return is not None
            and obj.expected_return < timezone.localdate()
        )


# ---------------------------------------------------------------------------
# Kayıp / hasar dosyası
# ---------------------------------------------------------------------------
class CaseCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/loss-damage-cases/` — kayıp bildirimi ya da hasar dosyası açma.

    Nüsha `copy_id` YA DA okutulan `barcode` ile gelir. Kayıpta ödünç ve teslim
    kendiliğinden bulunur; hasarda iadesi alınmış ödünç (`loan_id`) ya da geri
    alınmış teslim (`delivery_id`) sorumluyu gösterebilir. `membership_id`
    sorumlu üyedir (ödünç ya da teslim yoksa).
    """

    case_type = serializers.ChoiceField(
        choices=CaseType.choices,
        error_messages={"invalid_choice": "Dosya türünü seçin (kayıp ya da hasar)."},
    )
    copy_id = serializers.IntegerField(min_value=1, required=False)
    barcode = serializers.CharField(max_length=KOD_UZUNLUGU, required=False, allow_blank=True)
    loan_id = serializers.IntegerField(min_value=1, required=False)
    delivery_id = serializers.IntegerField(min_value=1, required=False)
    membership_id = serializers.IntegerField(min_value=1, required=False)
    responsible_note = serializers.CharField(
        max_length=RESPONSIBLE_NOTE_MAX, required=False, allow_blank=True, default=""
    )
    reported_on = serializers.DateField(required=False)
    send_to_repair = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        barkod = str(attrs.get("barcode") or "").strip()
        if bool(barkod) == ("copy_id" in attrs):
            raise serializers.ValidationError("Nüshayı seçin ya da kütüphane etiketini okutun.")
        attrs["barcode"] = barkod
        return attrs


class CaseUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """`PATCH library/loss-damage-cases/<pk>/` — yalnız sorumlu notu (açık dosyada)."""

    responsible_note = serializers.CharField(max_length=RESPONSIBLE_NOTE_MAX, allow_blank=True)


class CaseResolveSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/loss-damage-cases/<pk>/resolve/` — `{resolution, market_price?}`."""

    resolution = serializers.ChoiceField(
        choices=CaseResolution.choices,
        error_messages={"invalid_choice": "Geçerli bir çözüm seçin."},
    )
    market_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )


class CaseSerializer(serializers.ModelSerializer[LossDamageCase]):
    """Kayıp/hasar dosyası (yönetici kipi) — sorumlunun adı şifreli alandan çözülür.

    `allowed_resolutions` ekrana hangi çözüm düğmelerinin konacağını söyler
    (Md. 19 kademe kapısı SERVİSTEDİR; bu alan yalnız onun yansımasıdır).
    """

    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    copy_status = serializers.CharField(source="copy.status", read_only=True)
    copy_status_display = serializers.CharField(source="copy.get_status_display", read_only=True)
    case_type_display = serializers.CharField(source="get_case_type_display", read_only=True)
    responsible_name = serializers.SerializerMethodField()
    responsible_class_label = serializers.SerializerMethodField()
    resolution_display = serializers.CharField(source="get_resolution_display", read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    is_person_open_work = serializers.BooleanField(read_only=True)
    allowed_resolutions = serializers.SerializerMethodField()
    price_options_available = serializers.SerializerMethodField()

    class Meta:
        model = LossDamageCase
        fields = list(CASE_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: LossDamageCase) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)

    def get_responsible_name(self, obj: LossDamageCase) -> str:
        kisi = selectors_teslim.case_person(obj)
        return kisi.full_name if kisi is not None else ""

    def get_responsible_class_label(self, obj: LossDamageCase) -> str:
        kisi = selectors_teslim.case_person(obj)
        return str(getattr(kisi, "class_label", "") or "")

    def _bedel(self) -> bool:
        """Kademe kapısı (Md. 19) — liste serileştirmesinde BİR KEZ sorulur (bağlamda tutulur)."""
        from apps.kutuphane.services import loss_damage

        deger = self.context.get("price_options_available")
        if not isinstance(deger, bool):
            deger = loss_damage.price_options_available()
            self.context["price_options_available"] = deger
        return deger

    def get_allowed_resolutions(self, obj: LossDamageCase) -> list[dict[str, str]]:
        from apps.kutuphane.services import loss_damage

        return [
            {"value": deger, "label": str(CaseResolution(deger).label)}
            for deger in loss_damage.allowed_resolutions(obj, price_options=self._bedel())
        ]

    def get_price_options_available(self, obj: LossDamageCase) -> bool:
        return self._bedel()


class CopyRepairSerializer(serializers.ModelSerializer[CopyRepair]):
    """Onarım kaydı (kişisiz)."""

    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)

    class Meta:
        model = CopyRepair
        fields = list(REPAIR_FIELDS)
        read_only_fields = fields

    def get_barcode_display(self, obj: CopyRepair) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)
