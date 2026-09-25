"""Ayıklama, nadir eser ve yıl sonu raporu serializer'ları (F8) — gövde biçimi burada, kural serviste.

`serializers.py`'nin üç kuralı burada da geçerlidir: iş kuralı TEKRARLANMAZ
(E7 eşlemesi, durum makinesi, nadir eser engeli `services.weeding`'dedir),
durum alanları salt okunurdur (geçişler kendi uçlarından yapılır), şifreli
alanlar olağan metin gibi görünür (TMY komisyonu adları ve harcama yetkilisi —
yalnız teklif AYRINTISINDA; listede yoktur).

Kişisel veri: ayıklama kalemi, nadir eser satırı ve yıl sonu raporu kişisizdir.
Yıl sonu raporunun sayıları `selectors_yil_raporu`'ndan gelir (profil yasağı).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import (
    WEEDING_EXCLUDED_STATES,
    WEEDING_TRANSFER_PATHS,
    WEEDING_WRITE_OFF_PATHS,
    AnnualLibraryReview,
    CommissionDecision,
    Copy,
    RareWorksSubmission,
    RareWorksSubmissionItem,
    WeedingBatch,
    WeedingItem,
    WeedingItemState,
)
from apps.kutuphane.services import annual_review as annual_review_service
from apps.okul.models import SchoolYear

_ZORUNLU: dict[str, Any] = {
    "blank": "Bu alan boş bırakılamaz.",
    "required": "Bu alan zorunludur.",
    "null": "Bu alan zorunludur.",
}
_TARIH: dict[str, Any] = {"invalid": "Geçerli bir tarih girin."}


def _iliski(tekil: str) -> dict[str, Any]:
    return {
        "does_not_exist": f"Seçilen {tekil} bulunamadı.",
        "incorrect_type": f"Seçilen {tekil} kimliği sayısal olmalıdır.",
        "required": f"{tekil.capitalize()} seçilmelidir.",
        "null": f"{tekil.capitalize()} seçilmelidir.",
    }


def _kimlik_eslemesi(value: dict[str, Any]) -> dict[int, Any]:
    """JSON eşlemesinin anahtarlarını (kalem kimliği) sayıya çevirir."""
    sonuc: dict[int, Any] = {}
    for anahtar, deger in value.items():
        try:
            sonuc[int(anahtar)] = deger
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError("Kalem kimliği sayısal olmalıdır.") from exc
    return sonuc


class _GerekceEslemesi(serializers.DictField):
    """Kalem kimliği → gerekçe eşlemesi (liste değil: aynı kalem iki gerekçe alamaz)."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("child", serializers.CharField(max_length=255, error_messages=_ZORUNLU))
        kwargs.setdefault("required", False)
        kwargs.setdefault("default", dict)
        kwargs.setdefault(
            "error_messages", {"not_a_dict": "Kalemler eşleme olarak gönderilmelidir."}
        )
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> dict[int, Any]:
        return _kimlik_eslemesi(super().to_internal_value(data))


class _NushaSecimi(serializers.Serializer[dict[str, Any]]):
    """Okutulan kodlar (`barcodes`) ve/veya seçilen nüsha kimlikleri (`copies`)."""

    barcodes = serializers.ListField(
        child=serializers.CharField(max_length=64, trim_whitespace=True),
        required=False,
        default=list,
        error_messages={"not_a_list": "Okutulan kodlar liste olarak gönderilmelidir."},
    )
    copies = serializers.ListField(
        child=serializers.IntegerField(
            min_value=1, error_messages={"invalid": "Nüsha kimliği sayısal olmalıdır."}
        ),
        required=False,
        default=list,
        error_messages={"not_a_list": "Seçilen nüshalar liste olarak gönderilmelidir."},
    )


# ---------------------------------------------------------------------------
# Ayıklama
# ---------------------------------------------------------------------------
class WeedingItemSerializer(serializers.ModelSerializer[WeedingItem]):
    """Teklif kalemi — nüsha özeti, gerekçe, ölçüt, TMY yolu, kalem durumu (kişisiz)."""

    barcode = serializers.CharField(source="copy.barcode", read_only=True)
    barcode_display = serializers.SerializerMethodField()
    work = serializers.IntegerField(source="copy.work_id", read_only=True)
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    work_authors = serializers.CharField(source="copy.work.authors", read_only=True)
    call_number = serializers.CharField(source="copy.work.call_number", read_only=True)
    copy_status = serializers.CharField(source="copy.status", read_only=True)
    copy_status_display = serializers.CharField(source="copy.get_status_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    criterion_display = serializers.CharField(source="get_criterion_display", read_only=True)
    tmy_path_display = serializers.CharField(source="get_tmy_path_display", read_only=True)
    state_display = serializers.CharField(source="get_state_display", read_only=True)
    is_transfer = serializers.BooleanField(read_only=True)
    copy_is_rare = serializers.BooleanField(source="copy.is_rare_or_manuscript", read_only=True)

    class Meta:
        model = WeedingItem
        fields = [
            "id",
            "copy",
            "barcode",
            "barcode_display",
            "work",
            "work_title",
            "work_authors",
            "call_number",
            "copy_status",
            "copy_status_display",
            "reason",
            "reason_display",
            "criterion",
            "criterion_display",
            "tmy_path",
            "tmy_path_display",
            "is_transfer",
            "transfer_target",
            "state",
            "state_display",
            "exclusion_reason",
            "copy_is_rare",
            "destruction_decided",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: WeedingItem) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)


def _karar_ozeti(karar: CommissionDecision | None) -> dict[str, Any] | None:
    if karar is None:
        return None
    return {
        "id": karar.pk,
        "decision_type": karar.decision_type,
        "decision_date": karar.decision_date,
        "decision_no": karar.decision_no,
    }


class WeedingBatchSerializer(serializers.ModelSerializer[WeedingBatch]):
    """Teklif listesi satırı — sayılar ve adımların zamanları (şifreli adlar YOK)."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    decision = serializers.SerializerMethodField()
    counts = serializers.SerializerMethodField()

    class Meta:
        model = WeedingBatch
        fields = [
            "id",
            "school_year",
            "school_year_name",
            "status",
            "status_display",
            "commission_decision",
            "decision",
            "submitted_at",
            "decided_at",
            "approved_on",
            "approved_at",
            "destruction_decided",
            "applied_at",
            "cancelled_at",
            "cancel_reason",
            "notes",
            "counts",
            "created_at",
        ]
        read_only_fields = fields

    def get_decision(self, obj: WeedingBatch) -> dict[str, Any] | None:
        return _karar_ozeti(obj.commission_decision)

    def get_counts(self, obj: WeedingBatch) -> dict[str, int]:
        """Kalem sayıları: toplam, teklif listesinde, dışarıda bırakılan, uygulanan; yollar."""
        kalemler = list(obj.items.values_list("state", "tmy_path"))
        etkin = [yol for durum, yol in kalemler if durum not in WEEDING_EXCLUDED_STATES]
        return {
            "items": len(kalemler),
            "proposed": sum(1 for d, _ in kalemler if d == WeedingItemState.PROPOSED),
            "excluded": sum(1 for d, _ in kalemler if d in WEEDING_EXCLUDED_STATES),
            "applied": sum(1 for d, _ in kalemler if d == WeedingItemState.APPLIED),
            "write_off": sum(1 for y in etkin if y in WEEDING_WRITE_OFF_PATHS),
            "transfer": sum(1 for y in etkin if y in WEEDING_TRANSFER_PATHS),
        }


class WeedingBatchDetailSerializer(WeedingBatchSerializer):
    """Teklif ayrıntısı: kalemler + onayın şifreli adları (yalnız yönetici kipi)."""

    items = serializers.SerializerMethodField()

    class Meta(WeedingBatchSerializer.Meta):
        fields = [
            *WeedingBatchSerializer.Meta.fields,
            "approved_by_name",
            "tmy_commission_members",
            "items",
        ]
        read_only_fields = fields

    def get_items(self, obj: WeedingBatch) -> list[dict[str, Any]]:
        from apps.kutuphane import selectors_ayiklama

        return list(WeedingItemSerializer(selectors_ayiklama.batch_items(obj), many=True).data)


class WeedingBatchCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/weeding-batches/` — ders yılı verilmezse etkin yıl."""

    school_year = serializers.PrimaryKeyRelatedField(
        queryset=SchoolYear.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages=_iliski("ders yılı"),
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class WeedingBatchUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    notes = serializers.CharField(allow_blank=True)


class WeedingItemAddSerializer(_NushaSecimi):
    """`POST …/items/` — okutulan ya da seçilen nüshalar aynı gerekçe ve yolu alır."""

    reason = serializers.CharField(max_length=20, error_messages=_ZORUNLU)
    tmy_path = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    criterion = serializers.CharField(max_length=8, required=False, allow_blank=True, default="")
    transfer_target = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class WeedingItemUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """`PATCH …/items/<pk>/` — verilen alanlar değişir (servis adımına göre sınırlar)."""

    reason = serializers.CharField(max_length=20, required=False)
    tmy_path = serializers.CharField(max_length=10, required=False, allow_blank=True)
    criterion = serializers.CharField(max_length=8, required=False, allow_blank=True)
    transfer_target = serializers.CharField(max_length=255, required=False, allow_blank=True)


class WeedingDecisionSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST …/decision/` — "Ayıklama" türünde karar + komisyonun ayıklamadığı kalemler."""

    commission_decision = serializers.PrimaryKeyRelatedField(
        queryset=CommissionDecision.objects.all(), error_messages=_iliski("komisyon kararı")
    )
    kept = _GerekceEslemesi()


class WeedingApprovalSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST …/approve/` — harcama yetkilisi onayı (adlar ŞİFRELİ saklanır)."""

    approved_by_name = serializers.CharField(max_length=120, error_messages=_ZORUNLU)
    approved_on = serializers.DateField(error_messages={**_TARIH, **_ZORUNLU})
    tmy_commission_members = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2000
    )
    destruction_decided = serializers.BooleanField(required=False, default=False)
    #: İmha kararının kapsadığı kalemler (TMY 28/5); verilmezse onaylanan bütün 28 kalemleri.
    destruction_items = serializers.ListField(
        child=serializers.IntegerField(
            min_value=1, error_messages={"invalid": "Kalem kimliği sayısal olmalıdır."}
        ),
        required=False,
        allow_null=True,
        default=None,
        error_messages={"not_a_list": "İmha kalemleri liste olarak gönderilmelidir."},
    )
    not_approved = _GerekceEslemesi()


class WeedingCancelSerializer(serializers.Serializer[dict[str, Any]]):
    reason = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default="", trim_whitespace=True
    )


class WeedingCandidateSerializer(serializers.ModelSerializer[Copy]):
    """Aday nüsha (kişisiz): künye özeti ve nüsha durumu.

    Kayıp ve hasar dosyasının kayıttan düşme önerisi aday DEĞİLDİR (F8 ekleri 34);
    aday ucu onları aynı alanlarla ve engel gerekçesiyle ayrı listeler.
    """

    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="work.title", read_only=True)
    work_authors = serializers.CharField(source="work.authors", read_only=True)
    call_number = serializers.CharField(source="work.call_number", read_only=True)
    section_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Copy
        fields = [
            "id",
            "barcode",
            "barcode_display",
            "work",
            "work_title",
            "work_authors",
            "call_number",
            "section_name",
            "status",
            "status_display",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: Copy) -> str:
        return barcode_module.format_barcode(obj.barcode)

    def get_section_name(self, obj: Copy) -> str | None:
        bolum = obj.section if obj.section is not None else obj.work.section
        return bolum.name if bolum is not None else None


# ---------------------------------------------------------------------------
# Nadir eserler (Md. 12/2)
# ---------------------------------------------------------------------------
class RareWorksItemSerializer(serializers.ModelSerializer[RareWorksSubmissionItem]):
    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="copy.work.title", read_only=True)
    work_authors = serializers.CharField(source="copy.work.authors", read_only=True)
    publisher = serializers.CharField(source="copy.work.publisher", read_only=True)
    publish_year = serializers.IntegerField(source="copy.work.publish_year", read_only=True)
    call_number = serializers.CharField(source="copy.work.call_number", read_only=True)
    copy_status_display = serializers.CharField(source="copy.get_status_display", read_only=True)

    class Meta:
        model = RareWorksSubmissionItem
        fields = [
            "id",
            "copy",
            "barcode_display",
            "work_title",
            "work_authors",
            "publisher",
            "publish_year",
            "call_number",
            "copy_status_display",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: RareWorksSubmissionItem) -> str:
        return barcode_module.format_barcode(obj.copy.barcode)


class RareWorksSubmissionSerializer(serializers.ModelSerializer[RareWorksSubmission]):
    """El yazması ve nadir eserler listesi (kişisiz). Durum ve gönderim kendi ucundan."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    decision = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = RareWorksSubmission
        fields = [
            "id",
            "school_year",
            "school_year_name",
            "commission_decision",
            "decision",
            "status",
            "status_display",
            "sent_on",
            "sent_document_no",
            "notes",
            "item_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_decision(self, obj: RareWorksSubmission) -> dict[str, Any] | None:
        return _karar_ozeti(obj.commission_decision)

    def get_item_count(self, obj: RareWorksSubmission) -> int:
        return int(obj.items.count())


class RareWorksSubmissionDetailSerializer(RareWorksSubmissionSerializer):
    items = serializers.SerializerMethodField()

    class Meta(RareWorksSubmissionSerializer.Meta):
        fields = [*RareWorksSubmissionSerializer.Meta.fields, "items"]
        read_only_fields = fields

    def get_items(self, obj: RareWorksSubmission) -> list[dict[str, Any]]:
        from apps.kutuphane import selectors_ayiklama

        return list(
            RareWorksItemSerializer(selectors_ayiklama.submission_items(obj), many=True).data
        )


class RareWorksSubmissionWriteSerializer(serializers.Serializer[dict[str, Any]]):
    """Liste açma ve düzenleme gövdesi (karar sonradan da bağlanır)."""

    school_year = serializers.PrimaryKeyRelatedField(
        queryset=SchoolYear.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages=_iliski("ders yılı"),
    )
    commission_decision = serializers.PrimaryKeyRelatedField(
        queryset=CommissionDecision.objects.all(),
        required=False,
        allow_null=True,
        error_messages=_iliski("komisyon kararı"),
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class RareWorksAddSerializer(_NushaSecimi):
    """`POST …/items/` — yalnız nadir eser işaretli nüshalar."""


class RareWorksSendSerializer(serializers.Serializer[dict[str, Any]]):
    sent_on = serializers.DateField(error_messages={**_TARIH, **_ZORUNLU})
    sent_document_no = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default=""
    )


class RareCopySerializer(serializers.ModelSerializer[Copy]):
    """Nadir eser işaretli nüsha — gönderilmiş bir listede olup olmadığıyla."""

    barcode_display = serializers.SerializerMethodField()
    work_title = serializers.CharField(source="work.title", read_only=True)
    work_authors = serializers.CharField(source="work.authors", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    sent = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = [
            "id",
            "barcode_display",
            "work",
            "work_title",
            "work_authors",
            "status",
            "status_display",
            "sent",
        ]
        read_only_fields = fields

    def get_barcode_display(self, obj: Copy) -> str:
        return barcode_module.format_barcode(obj.barcode)

    def get_sent(self, obj: Copy) -> bool:
        return bool(getattr(obj, "sent", False))


# ---------------------------------------------------------------------------
# Yıl sonu kütüphane raporu (E9)
# ---------------------------------------------------------------------------
class AnnualLibraryReviewListSerializer(serializers.ModelSerializer[AnnualLibraryReview]):
    """Liste satırı — sayılar yok (her satırda canlı hesap pahalıdır)."""

    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    is_finalized = serializers.BooleanField(read_only=True)

    class Meta:
        model = AnnualLibraryReview
        fields = [
            "id",
            "school_year",
            "school_year_name",
            "document_date",
            "document_no",
            "findings",
            "is_finalized",
            "finalized_at",
            "created_at",
        ]
        read_only_fields = fields


class AnnualLibraryReviewSerializer(AnnualLibraryReviewListSerializer):
    """Rapor ve sayıları (sonlandırılmışsa dondurulmuş, değilse canlı) — KİŞİSİZ."""

    stats = serializers.SerializerMethodField()

    class Meta(AnnualLibraryReviewListSerializer.Meta):
        fields = [*AnnualLibraryReviewListSerializer.Meta.fields, "stats"]
        read_only_fields = fields

    def get_stats(self, obj: AnnualLibraryReview) -> dict[str, Any]:
        return annual_review_service.review_stats(obj)


class AnnualLibraryReviewCreateSerializer(serializers.Serializer[dict[str, Any]]):
    school_year = serializers.PrimaryKeyRelatedField(
        queryset=SchoolYear.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages=_iliski("ders yılı"),
    )


class AnnualLibraryReviewUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    document_date = serializers.DateField(required=False, allow_null=True, error_messages=_TARIH)
    document_no = serializers.CharField(max_length=40, required=False, allow_blank=True)
    findings = serializers.CharField(required=False, allow_blank=True, max_length=5000)
