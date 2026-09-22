"""`okul` DRF serializer'ları — doğrulama + normalize burada, yazma serviste.

Elle giriş, içe aktarmayla AYNI normalize edicilerden geçer (`apps.okul.normalize`):
şube harfi Türkçe büyük harfe çevrilir (`tr_upper` — 'ş' → 'Ş', 'i' → 'İ'; ASCII'ye
KATLANMAZ, 10/I ile 10/İ ayrı şubelerdir); seviye kümesi okul içi sabittir (1-12,
hazırlık bayrağıyla 0). Hatalar Türkçedir (`{code, message, fields}` sözleşmesi).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.okul import normalize, selectors
from apps.okul.models import (
    ClassSection,
    Holiday,
    HolidayKind,
    MemberKind,
    Personnel,
    SchoolConfig,
    SchoolTerm,
    SchoolYear,
    Student,
)
from apps.okul.services import calendar as calendar_service


def _validate_level(value: int) -> int:
    """Seviyeyi okulun geçerli kümesine karşı doğrular (1-12; hazırlık açıksa 0)."""
    levels = selectors.grade_level_values()
    if value not in levels:
        etiketler = ", ".join(
            "Hazırlık" if lvl == normalize.PREP_LEVEL else str(lvl) for lvl in levels
        )
        raise serializers.ValidationError(f"Sınıf şu seviyelerden biri olmalıdır: {etiketler}.")
    return value


class SchoolConfigSerializer(serializers.ModelSerializer[SchoolConfig]):
    """Kurum künyesi — sihirbaz ve Okul Bilgileri ekranının ortak sözleşmesi."""

    class Meta:
        model = SchoolConfig
        fields = [
            "school_name",
            "province",
            "district",
            "principal_name",
            "has_prep_class",
            "setup_completed",
        ]
        read_only_fields = ["setup_completed"]


class SchoolYearSerializer(serializers.ModelSerializer[SchoolYear]):
    class Meta:
        model = SchoolYear
        fields = ["id", "name", "start_date", "end_date", "is_active"]
        read_only_fields = ["is_active"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "Bitiş tarihi başlangıçtan sonra olmalıdır."}
            )
        return attrs


class SchoolTermSerializer(serializers.ModelSerializer[SchoolTerm]):
    name = serializers.CharField(read_only=True)

    class Meta:
        model = SchoolTerm
        fields = ["id", "school_year", "sequence", "name", "start_date", "end_date"]
        read_only_fields = fields


class SchoolTermConfigurationSerializer(serializers.Serializer[dict[str, Any]]):
    first_term_end = serializers.DateField()
    second_term_start = serializers.DateField()


# ---------------------------------------------------------------------------
# Kapalı günler (F1-D; tasarım §6.1 Holiday, §9-5)
# ---------------------------------------------------------------------------

# `Any` değerli: DRF stub'ı `str | _StrPromise` ister, `dict` değişmez (invariant) türdür.
_DATE_ERRORS: dict[str, Any] = {
    "invalid": "Geçerli bir tarih girin.",
    "required": "Tarih seçilmelidir.",
    "null": "Tarih seçilmelidir.",
}

_YEAR_RANGE_MESSAGE = (
    f"Yıl {calendar_service.MIN_YEAR} ile {calendar_service.MAX_YEAR} arasında olmalıdır."
)
_YEAR_ERRORS: dict[str, Any] = {
    "invalid": "Yıl dört haneli bir sayı olmalıdır.",
    "min_value": _YEAR_RANGE_MESSAGE,
    "max_value": _YEAR_RANGE_MESSAGE,
}


def _year_field(*, required: bool) -> serializers.IntegerField:
    return serializers.IntegerField(
        required=required,
        min_value=calendar_service.MIN_YEAR,
        max_value=calendar_service.MAX_YEAR,
        error_messages=_YEAR_ERRORS,
    )


class HolidaySerializer(serializers.ModelSerializer[Holiday]):
    """Kapalı gün kaydı. `is_estimated` salt okunurdur: yalnız tohumlama yazar,
    elle girilen kayıt kesin tarih sayılır.

    Teklik (ad + başlangıç) servistedir ve Türkçe reddeder; DRF'nin koşullu
    kısıttan türettiği İngilizce alan adlı doğrulayıcı `validators = []` ile kapalıdır.
    """

    name = serializers.CharField(
        max_length=128,
        error_messages={
            "blank": "Ad yazılmalıdır.",
            "required": "Ad yazılmalıdır.",
            "max_length": "Ad en çok 128 karakter olabilir.",
        },
    )
    start_date = serializers.DateField(error_messages=_DATE_ERRORS)
    end_date = serializers.DateField(error_messages=_DATE_ERRORS)
    kind = serializers.ChoiceField(
        choices=HolidayKind.choices,
        default=HolidayKind.SCHOOL_BREAK,
        error_messages={"invalid_choice": "Geçerli bir tür seçin."},
    )

    class Meta:
        model = Holiday
        fields = ["id", "name", "start_date", "end_date", "kind", "is_estimated"]
        read_only_fields = ["is_estimated"]
        validators: list[Any] = []

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end:
            if end < start:
                raise serializers.ValidationError(
                    {"end_date": "Bitiş tarihi başlangıçtan önce olamaz."}
                )
            if (end - start).days + 1 > calendar_service.MAX_SPAN_DAYS:
                raise serializers.ValidationError({"end_date": calendar_service.span_message()})
        return attrs


class HolidayListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """`GET holidays/?year=` — yıl verilmezse bütün kayıtlar."""

    year = _year_field(required=False)


class HolidaySeedRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST holidays/seed/` — yıl verilmezse bugünün takvim yılı (`localdate`)."""

    year = _year_field(required=False)


class PersonnelSerializer(serializers.ModelSerializer[Personnel]):
    """Personel sicili. Unvan ve branş YOKTUR (V2-01).

    `is_active` ve `left_at` salt okunurdur: ayrılış yalnız `personnel/<pk>/leave/`
    ayrılış yolundan geçer (kancalar + katı silme kararı, tasarım §6.1); gövdeyle
    gönderilen değer yok sayılır.
    """

    full_name = serializers.CharField(read_only=True)
    member_kind = serializers.ChoiceField(
        choices=MemberKind.choices,
        default=MemberKind.TEACHER,
        error_messages={
            "invalid_choice": "Geçerli bir üye türü seçin (öğretmen ya da diğer personel)."
        },
    )

    class Meta:
        model = Personnel
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "member_kind",
            "is_active",
            "left_at",
        ]
        read_only_fields = ["is_active", "left_at"]


class ClassSectionSerializer(serializers.ModelSerializer[ClassSection]):
    school_year_name = serializers.CharField(source="school_year.name", read_only=True)
    class_label = serializers.CharField(read_only=True)

    class Meta:
        model = ClassSection
        validators: list[Any] = []
        fields = [
            "id",
            "school_year",
            "school_year_name",
            "class_level",
            "class_section",
            "class_label",
        ]

    def validate_class_level(self, value: int) -> int:
        return _validate_level(value)

    def validate_class_section(self, value: str) -> str:
        normalized = normalize.tr_upper(value.strip())
        if not normalized:
            raise serializers.ValidationError("Şube zorunludur.")
        return normalized

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        instance = self.instance if isinstance(self.instance, ClassSection) else None
        year = attrs.get("school_year", getattr(instance, "school_year", None))
        level = attrs.get("class_level", getattr(instance, "class_level", None))
        section = attrs.get("class_section", getattr(instance, "class_section", ""))
        if year is not None and level is not None and section:
            duplicate = ClassSection.objects.filter(
                school_year=year,
                class_level=level,
                class_section=section,
            )
            if instance is not None:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"class_section": "Bu ders yılı için şube zaten kayıtlı."}
                )
        return attrs


class StudentSerializer(serializers.ModelSerializer[Student]):
    """Öğrenci sicili.

    Okul no şifreli + kör indekslidir (T14). Teklik kısıtı kör indekstedir;
    Türkçe teklik iletisi SERVİSTEN gelir (`persons.ensure_student_number_free`).
    Alan elle tanımlanır (`validators=[]`): DRF tek alanlı kısıttan otomatik
    UniqueValidator türetmesin (CLAUDE.md §3 tuzağı; şifreli sütunda zaten
    çalışmazdı).

    `status` ve `left_at` salt okunurdur: ayrılış `students/<pk>/leave/`
    ayrılış yolundan, yeniden aktifleşme e-Okul aktarımından geçer.
    """

    full_name = serializers.CharField(read_only=True)
    class_label = serializers.CharField(read_only=True)
    student_number = serializers.CharField(
        max_length=16,
        required=False,
        allow_blank=True,
        default="",
        validators=[],
        error_messages={"max_length": "Okul no en çok 16 karakter olabilir."},
    )

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "student_number",
            "class_level",
            "class_section",
            "class_label",
            "status",
            "left_at",
        ]
        read_only_fields = ["status", "left_at"]
        validators: list[Any] = []

    def validate_student_number(self, value: str) -> str:
        return value.strip()

    def validate_class_level(self, value: int | None) -> int | None:
        if value is None:
            return None
        return _validate_level(value)

    def validate_class_section(self, value: str) -> str:
        # İçe aktarmayla aynı katlama: Türkçe büyük harf ('ş' → 'Ş', 'i' → 'İ').
        if not value.strip():
            return ""
        return normalize.tr_upper(value.strip())


class ImportRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """İçe aktarma girdisi: Excel dosyası (e-Okul .xls / şablon .xlsx) VEYA pano metni.

    Mutabakat seçenekleri (tasarım §8.3; önizleme ve uygulama AYNI kodu koşar,
    ikisi de kabul eder):

    - `full_list` (öğrenci): "Bu dosya okulun tam listesidir" onayı. Verilmezse
      karşılaştırma YALNIZ dosyada bulunan şubelerle yapılır (EK-21).
    - `mark_left_ids` (personel): listede olmayan aktif personelden ayrıldı
      sayılacaklar; varsayılan hiçbiri (EK-20). Çok parçalı gövdede alan
      tekrarlanarak gönderilir.
    """

    file = serializers.FileField(required=False)
    text = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    full_list = serializers.BooleanField(required=False, default=False)
    mark_left_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        has_file = attrs.get("file") is not None
        has_text = bool(str(attrs.get("text", "")).strip())
        if has_file == has_text:  # ikisi birden veya hiçbiri
            raise serializers.ValidationError(
                "Dosya (file) veya yapıştırılan metin (text) alanlarından tam olarak biri gerekli."
            )
        return attrs


class PersonnelMergeSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST personnel/<pk>/merge/` — `<pk>` (kaynak) `into_id` (hedef) kaydına birleşir."""

    into_id = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "Birleştirilecek hedef kayıt seçilmelidir.",
            "invalid": "Hedef kayıt kimliği sayısal olmalıdır.",
        },
    )
