"""`kutuphane` DRF serializer'ları — gövde doğrulaması burada, iş kuralı serviste.

OYS'nin (Okul Yönetim Sistemi) `apps/kutuphane/serializers.py` dosyasından
UYARLA (tasarım §12): alan adları ve API yüzeyi korundu, `created_by` ve rol
dalları düştü (yönetim yüzeyi hesapsızdır — CLAUDE.md §4).

Üç kural bu dosyanın biçimini belirler:

1. **İş kuralı serializer'da TEKRARLANMAZ.** Nüsha açma kuralları (dijital
   kaynak, ciltsiz süreli yayın), komisyon kararı türü (D7), bağış kararının
   kapsamı ve politikanın müdürlük kararı şartı (AT-4) SERVİSTEDİR; servis
   Django `ValidationError` yükseltir ve `shared.exceptions.kd_exception_handler`
   onu alan adlarıyla 400'e çevirir. OYS aynı kuralı hem serializer'da hem
   serviste yazıyordu; iki kopya zamanla ayrışır ve hangisinin doğru olduğu
   belirsizleşir. Buradaki doğrulama gövdenin BİÇİMİYLE sınırlıdır.
2. **Kimlik ve durum alanları salt okunurdur.** `barcode` ve `accession_no`
   sayaçtan gelir, `status` kendi servislerinden (ödünç, teslim, onarım,
   kayıttan düşme) geçer. Servis bunları gövdede görürse ayrıca reddeder
   (savunma derinliği, `services.catalog.PROTECTED_COPY_FIELDS`).
3. **Şifreli alanlar olağan metin alanı gibi görünür** (bağışçı, komisyon
   adları — §6.3): şifreleme model alanının işidir. Anahtar bellekte değilken
   yazma `KeyMissingError` ile durur ve uç 409 `parola_gerekli` döner; kilitliyken
   istek zaten kilit ara katmanında 423 alır.

Türkçe anahtar alanları (`search_key`, `sort_key`, …) ve `isbn13` hiçbir
serializer'da YAZILABİLİR değildir: `Work.save()` onları her yazımda yeniden
türetir (T7, D2).
"""

from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from rest_framework import serializers

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_ayiklama
from apps.kutuphane.import_schema import MAX_COPIES_PER_ROW
from apps.kutuphane.models import (
    MIN_UNIT_PRICE,
    TERMINAL_COPY_STATUSES,
    Acquisition,
    AcquisitionMethod,
    CatalogImportRun,
    CatalogImportSource,
    CommissionDecision,
    Copy,
    CopyStatus,
    DonationIntake,
    DonationIntakeItem,
    LibraryPolicy,
    Section,
    Work,
)
from apps.kutuphane.services import commissions as commission_service
from apps.kutuphane.services import policy as policy_service

#: Yüklenen dosyanın bayt tavanı (`KD_MAX_UPLOAD_SIZE_MB`, varsayılan 20 MB).
#: Django'nun `DATA_UPLOAD_MAX_MEMORY_SIZE` ayarı çok parçalı istekteki DOSYA
#: parçasını sınırlamaz — gövdenin dosya DIŞI kısmını sınırlar. Tavan bu yüzden
#: serializer'da uygulanır: yanlışlıkla seçilen yüzlerce MB'lık bir dosyada
#: kullanıcı bellek şişmesi değil, Türkçe bir ileti görür.
MAX_UPLOAD_BYTES: int = int(settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024


def dosya_boyutunu_dogrula(yuklenen: Any, *, tavan: int) -> Any:
    """Yüklenen dosya tavanı aşıyorsa 400 döndürür (dosya OKUNMADAN önce)."""
    boyut = int(getattr(yuklenen, "size", 0) or 0)
    if boyut > tavan:
        raise serializers.ValidationError(f"Dosya çok büyük (en çok {tavan // (1024 * 1024)} MB).")
    return yuklenen


# `Any` değerli sözlükler: DRF stub'ı `str | _StrPromise` ister, `dict` değişmez
# (invariant) türdür — `apps/okul/serializers.py` ile aynı kalıp.
_ZORUNLU_METIN: dict[str, Any] = {
    "blank": "Bu alan boş bırakılamaz.",
    "required": "Bu alan zorunludur.",
    "null": "Bu alan zorunludur.",
}


def _iliski_hatalari(tekil: str, zorunlu: str) -> dict[str, Any]:
    """İlişki alanının Türkçe hata iletileri.

    `tekil` kaynağın sözlükteki adıdır ("eser", "edinim", "bölüm"), `zorunlu`
    alan gönderilmediğinde basılacak cümledir. DRF'in kendi iletileri yerel
    dosyasından Türkçe gelir ama kimliği yankılar ("Geçersiz pk “12”…"); sözlük
    iç kimliklerin kullanıcı metnine girmemesini ister (docs/sozluk.md §2).
    """
    return {
        "does_not_exist": f"Seçilen {tekil} bulunamadı.",
        "incorrect_type": f"Seçilen {tekil} kimliği sayısal olmalıdır.",
        "required": zorunlu,
        "null": zorunlu,
    }


# ---------------------------------------------------------------------------
# Kütüphane politikası (tek satır)
# ---------------------------------------------------------------------------
class LibraryPolicySerializer(serializers.ModelSerializer[LibraryPolicy]):
    """Kütüphane politikası — sayısal sınırların üst değerleri mevzuattandır.

    **`loan_period_days` SALT OKUNURDUR ve modelde alan DEĞİLDİR** (D19): Md. 18
    ödünç süresini "on beş gün" olarak sabitler. Değer yine de yanıta konur ki
    arayüz "15 gün" yazısını koda gömmek zorunda kalmasın; gövdede gönderilse
    yok sayılır.

    Sınır validator'ları modelden gelir (öğrenci ≤ 3, öğretmen ≤ 5 — Md. 18);
    diğer personele ödüncün müdürlük kararı şartı (AT-4) servistedir ve alan
    adlarıyla 400 döner.
    """

    loan_period_days = serializers.SerializerMethodField()

    class Meta:
        model = LibraryPolicy
        fields = [
            "loan_period_days",
            "max_loans_student",
            "max_loans_teacher",
            "max_loans_staff",
            "staff_loans_enabled",
            "staff_loans_decision_date",
            "staff_loans_decision_no",
            "block_loan_if_overdue",
            "shift_due_date_on_school_break",
            "last_loan_date",
            "last_loan_date_graduating",
            "idle_minutes",
            "admin_max_minutes",
            "popular_min_members",
            "retention_years_after_termination",
            "retention_years_returned_loans",
            "retention_years_closed_cases",
            "retention_years_closed_deliveries",
            # ISBN ile künye getirme (U13, §8.5): ana bayrak varsayılan KAPALI.
            "metadata_lookup_enabled",
            "metadata_lookup_ministry",
            "metadata_lookup_openlibrary",
            "updated_at",
        ]
        read_only_fields = ["loan_period_days", "updated_at"]

    def get_loan_period_days(self, obj: LibraryPolicy) -> int:
        return policy_service.LOAN_PERIOD_DAYS


# ---------------------------------------------------------------------------
# Bölüm (kontrollü liste)
# ---------------------------------------------------------------------------
class SectionSerializer(serializers.ModelSerializer[Section]):
    """Bölüm (sözlük: "bölüm", "raf" değil).

    Teklik denetimi SERVİSTEDİR (`catalog.ensure_section_name_free`): Türkçe
    katlamalıdır ve iletisi kullanıcı dilindedir; F3 içe aktarımı da aynı
    kapıdan geçer. `validators = []`: modelin koşullu `UniqueConstraint`'inden
    DRF'in türettiği doğrulayıcı hem İngilizce hem de yalnız harfi harfine
    eşitliğe bakar (CLAUDE.md §3 tuzağı).
    """

    name = serializers.CharField(
        max_length=80,
        error_messages={
            "blank": "Bölüm adı yazılmalıdır.",
            "required": "Bölüm adı yazılmalıdır.",
            "null": "Bölüm adı yazılmalıdır.",
            "max_length": "Bölüm adı en çok 80 karakter olabilir.",
        },
    )

    class Meta:
        model = Section
        fields = ["id", "name", "dewey_from", "dewey_to", "description", "sort_order"]
        read_only_fields = ["id"]
        validators: list[Any] = []


# ---------------------------------------------------------------------------
# Eser
# ---------------------------------------------------------------------------
class WorkSerializer(serializers.ModelSerializer[Work]):
    """Eser künyesi.

    `isbn_warning` sağlama uyarısıdır ve kaydı ENGELLEMEZ (F2 sözleşmesi §3):
    saha verisi bozuk olabilir, program numarayı olduğu gibi saklar ve formda
    uyarıyı gösterir. `isbn13` `save()`'de türetilir, gövdeden alınmaz.

    Nüsha sayaçları listede `selectors.works_with_copy_counts` anotasyonundan
    gelir (N+1 yok); ayrıntı ucunda anotasyon olmadığı için sayılır.
    """

    resource_type_display = serializers.CharField(
        source="get_resource_type_display", read_only=True
    )
    classification_source_display = serializers.CharField(
        source="get_classification_source_display", read_only=True
    )
    section_name = serializers.SerializerMethodField()
    is_digital = serializers.BooleanField(read_only=True)
    isbn_warning = serializers.CharField(read_only=True)
    copy_count = serializers.SerializerMethodField()
    available_copy_count = serializers.SerializerMethodField()
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        required=False,
        allow_null=True,
        error_messages=_iliski_hatalari("bölüm", "Bölüm seçilmelidir."),
    )

    class Meta:
        model = Work
        fields = [
            "id",
            "title",
            "authors",
            "translator",
            "edition",
            "publisher",
            "publish_year",
            "isbn",
            "isbn13",
            "isbn_warning",
            "subjects",
            "classification_code",
            "classification_source",
            "classification_source_display",
            "call_number",
            "resource_type",
            "resource_type_display",
            "language",
            "section",
            "section_name",
            "is_digital",
            "copy_count",
            "available_copy_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "isbn13",
            "isbn_warning",
            "classification_source_display",
            "resource_type_display",
            "section_name",
            "is_digital",
            "copy_count",
            "available_copy_count",
            "created_at",
        ]

    def validate_title(self, value: str) -> str:
        ad = value.strip()
        if not ad:
            raise serializers.ValidationError("Kaynak adı yazılmalıdır.")
        return ad

    def get_section_name(self, obj: Work) -> str | None:
        """Bölümün adı; bölüm seçilmemişse `null`.

        Yumuşak silinmiş bölümün adı da basılır: kayıt o bölüme aitti, listede
        boşluk göstermek kullanıcıyı yanıltır (CLAUDE.md §3 — `obj.fk` silinmişi
        geri getirir; burada bu DAVRANIŞ İSTENİR).
        """
        bolum = obj.section
        return bolum.name if bolum is not None else None

    def _sayac(self, obj: Work, alan: str, yedek: Any) -> int:
        anotasyon = getattr(obj, alan, None)
        if anotasyon is not None:
            return int(anotasyon)
        return int(yedek())

    def get_copy_count(self, obj: Work) -> int:
        """Elde bulunan nüsha sayısı — kayıttan düşülmüş ve devredilmiş HARİÇ.

        Yedek yol (ayrıntı ucu, anotasyon yok) listedeki anotasyonla AYNI
        süzgeci uygular: iki yoldan farklı sayı dönerse kullanıcı listede ve
        ayrıntıda başka rakam görür.
        """
        return self._sayac(
            obj,
            "copy_count",
            obj.copies.exclude(status__in=TERMINAL_COPY_STATUSES).count,
        )

    def get_available_copy_count(self, obj: Work) -> int:
        return self._sayac(
            obj,
            "available_copy_count",
            obj.copies.filter(status=CopyStatus.AVAILABLE).count,
        )


# ---------------------------------------------------------------------------
# Nüsha — okuma / yazma ayrı (OYS deseni)
# ---------------------------------------------------------------------------
class CopyReadSerializer(serializers.ModelSerializer[Copy]):
    """Nüsha okuma — eser özeti ve ödünç verilebilirlik gerekçesi gömülü.

    `barcode_display` basılı biçimdir (`2026-000123`); saklanan, aranan ve
    okutulan değer `barcode` alanındaki rakamlardır (§7.1).
    """

    work_title = serializers.CharField(source="work.title", read_only=True)
    work_authors = serializers.CharField(source="work.authors", read_only=True)
    call_number = serializers.CharField(source="work.call_number", read_only=True)
    resource_type = serializers.CharField(source="work.resource_type", read_only=True)
    section_name = serializers.SerializerMethodField()
    barcode_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_loanable = serializers.BooleanField(read_only=True)
    not_loanable_reason = serializers.CharField(read_only=True)

    class Meta:
        model = Copy
        fields = [
            "id",
            "work",
            "work_title",
            "work_authors",
            "call_number",
            "resource_type",
            "acquisition",
            "accession_no",
            "barcode",
            "barcode_display",
            "external_asset_ref",
            "old_register_no",
            "section",
            "section_name",
            "is_reference",
            "is_out_of_print",
            "is_bound_periodical",
            "is_rare_or_manuscript",
            "status",
            "status_display",
            "is_loanable",
            "not_loanable_reason",
            "label_printed_at",
            "label_verified_at",
            "spine_label_printed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_section_name(self, obj: Copy) -> str | None:
        bolum = obj.section
        return bolum.name if bolum is not None else None

    def get_barcode_display(self, obj: Copy) -> str:
        return barcode_module.format_barcode(obj.barcode)


class CopyWriteSerializer(serializers.ModelSerializer[Copy]):
    """Nüsha yaratma/güncelleme — yalnız betimsel alanlar.

    `barcode`, `accession_no` ve `status` salt okunurdur (bkz. dosya başlığı).
    Nüsha açma kuralları serviste denetlenir; burada tekrarlanmaz.
    """

    work = serializers.PrimaryKeyRelatedField(
        queryset=Work.objects.all(),
        error_messages=_iliski_hatalari("eser", "Eser seçilmelidir."),
    )
    acquisition = serializers.PrimaryKeyRelatedField(
        queryset=Acquisition.objects.all(),
        error_messages=_iliski_hatalari("edinim", "Edinim seçilmelidir."),
    )
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        required=False,
        allow_null=True,
        error_messages=_iliski_hatalari("bölüm", "Bölüm seçilmelidir."),
    )

    class Meta:
        model = Copy
        fields = [
            "id",
            "work",
            "acquisition",
            "section",
            "external_asset_ref",
            "old_register_no",
            "is_reference",
            "is_out_of_print",
            "is_bound_periodical",
            "is_rare_or_manuscript",
            "accession_no",
            "barcode",
            "status",
        ]
        read_only_fields = ["id", "accession_no", "barcode", "status"]


class CopyUpdateSerializer(CopyWriteSerializer):
    """Güncelleme gövdesi: eser ve edinim DEĞİŞTİRİLEMEZ.

    Bir nüshanın hangi eserin nüshası olduğu ve hangi partiden geldiği kimlik
    bilgisidir; sonradan değiştirilmesi Kütüphane Defteri satırını dayanaksız
    bırakır. Yanlış eserin altına açılmış nüsha silinip yeniden açılır.

    İki alan BURADA YENİDEN TANIMLANIR: `Meta.read_only_fields` yalnız modelden
    türetilen alanlara işler, üst sınıfta AÇIKÇA tanımlanmış bir alanı salt
    okunur yapmaz (DRF tuzağı — sessizce yazılabilir kalırdı).
    """

    work = serializers.PrimaryKeyRelatedField(read_only=True)
    acquisition = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(CopyWriteSerializer.Meta):
        read_only_fields = ["id", "accession_no", "barcode", "status"]


class CopyBulkCreateSerializer(CopyWriteSerializer):
    """Toplu nüsha açma gövdesi: aynı künyeden `count` nüsha (Excel "Nüsha Sayısı").

    Eski kayıt no tek nüshaya aittir; `count > 1` iken dolu gönderilirse servis
    reddeder (§8.1).
    """

    count = serializers.IntegerField(
        min_value=1,
        max_value=MAX_COPIES_PER_ROW,
        default=1,
        error_messages={
            "invalid": "Nüsha sayısı sayısal olmalıdır.",
            "min_value": "Nüsha sayısı en az 1 olmalıdır.",
            "max_value": f"Tek seferde en çok {MAX_COPIES_PER_ROW} nüsha açılır.",
        },
    )

    class Meta(CopyWriteSerializer.Meta):
        fields = [*CopyWriteSerializer.Meta.fields, "count"]


# ---------------------------------------------------------------------------
# Komisyon kararı
# ---------------------------------------------------------------------------
class CommissionDecisionSerializer(serializers.ModelSerializer[CommissionDecision]):
    """Seçim ve Ayıklama Komisyonu kararı (Md. 4/1-ı, 10/1).

    `chair_name` ve `participants_text` ŞİFRELİDİR (§6.3): parola kurulmadan
    yazan istek 409 `parola_gerekli` alır. `in_use` karara bağlı edinim ya da
    bağış ön kaydı olup olmadığını söyler — arayüz türün neden kilitli
    olduğunu (D7) ve kaydın neden silinemediğini buradan anlatır.
    """

    decision_type_display = serializers.CharField(
        source="get_decision_type_display", read_only=True
    )
    in_use = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    chair_name = serializers.CharField(max_length=120, error_messages=_ZORUNLU_METIN)

    class Meta:
        model = CommissionDecision
        fields = [
            "id",
            "decision_type",
            "decision_type_display",
            "decision_date",
            "decision_no",
            "chair_name",
            "chair_title",
            "participants_text",
            "notes",
            "in_use",
            "usage",
            "created_at",
        ]
        read_only_fields = ["id", "decision_type_display", "in_use", "usage", "created_at"]

    def get_in_use(self, obj: CommissionDecision) -> bool:
        return commission_service.decision_in_use(obj)

    def get_usage(self, obj: CommissionDecision) -> dict[str, int]:
        """F8: karara bağlı kayıtların sayıları (edinim, bağış, ayıklama, nadir eser)."""
        return selectors_ayiklama.decision_usage(obj)


# ---------------------------------------------------------------------------
# Edinim
# ---------------------------------------------------------------------------
class AcquisitionSerializer(serializers.ModelSerializer[Acquisition]):
    """Edinim partisi (Md. 10/5 + iki kayıt-içi giriş).

    Bağışta komisyon kararı zorunludur ve türü denetlenir (Md. 10/3, D7) —
    ikisi de serviste (`services.catalog.ensure_acquisition_decision`).
    `source_note` (bağışçı, satıcı) ŞİFRELİDİR.
    """

    method_display = serializers.CharField(source="get_method_display", read_only=True)
    commission_decision = serializers.PrimaryKeyRelatedField(
        queryset=CommissionDecision.objects.all(),
        required=False,
        allow_null=True,
        error_messages=_iliski_hatalari("komisyon kararı", "Komisyon kararı seçilmelidir."),
    )
    copy_count = serializers.SerializerMethodField()

    class Meta:
        model = Acquisition
        fields = [
            "id",
            "method",
            "method_display",
            "date",
            "source_note",
            "unit_price",
            "commission_decision",
            "notes",
            "copy_count",
            "created_at",
        ]
        read_only_fields = ["id", "method_display", "copy_count", "created_at"]

    def get_copy_count(self, obj: Acquisition) -> int:
        anotasyon = getattr(obj, "copy_count", None)
        if anotasyon is not None:
            return int(anotasyon)
        return int(obj.copies.count())


# ---------------------------------------------------------------------------
# Bağış ön kaydı (SU-23)
# ---------------------------------------------------------------------------
class DonationIntakeItemSerializer(serializers.ModelSerializer[DonationIntakeItem]):
    """Bağış kalemi (okuma + kalem düzenleme).

    Karar alanları (`decision`, `reject_reason`, `work`) BURADAN yazılmaz:
    komisyon kararı tek işlemde uygulanır (`donation-intakes/<pk>/decision/`),
    kalem kalem işaretlenmez — yarım kararlanmış bir liste hangi kitabın kayda
    girdiği sorusunu cevapsız bırakır.
    """

    decision_display = serializers.CharField(source="get_decision_display", read_only=True)
    work_title = serializers.SerializerMethodField()

    class Meta:
        model = DonationIntakeItem
        fields = [
            "id",
            "title",
            "authors",
            "publisher",
            "publish_year",
            "isbn",
            "copies",
            "decision",
            "decision_display",
            "reject_reason",
            "work",
            "work_title",
            "notes",
        ]
        read_only_fields = [
            "id",
            "decision",
            "decision_display",
            "reject_reason",
            "work",
            "work_title",
        ]

    def get_work_title(self, obj: DonationIntakeItem) -> str | None:
        eser = obj.work
        return eser.title if eser is not None else None

    def validate_title(self, value: str) -> str:
        ad = value.strip()
        if not ad:
            raise serializers.ValidationError("Kaynak adı yazılmalıdır.")
        return ad


class DonationIntakeSerializer(serializers.ModelSerializer[DonationIntake]):
    """Bağış ön kaydı — komisyon kararına kadar nüsha açılmaz (Md. 10/3).

    `donor_name` ŞİFRELİDİR (§6.3). Karar alanları (`status`,
    `commission_decision`, `acquisition`, `decided_at`) salt okunurdur: karar
    kendi ucundan uygulanır.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = DonationIntakeItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = DonationIntake
        fields = [
            "id",
            "donor_name",
            "received_date",
            "status",
            "status_display",
            "commission_decision",
            "acquisition",
            "decided_at",
            "notes",
            "items",
            "item_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "status_display",
            "commission_decision",
            "acquisition",
            "decided_at",
            "items",
            "item_count",
            "created_at",
        ]

    def get_item_count(self, obj: DonationIntake) -> int:
        return int(obj.items.count())


class DonationIntakeCreateSerializer(DonationIntakeSerializer):
    """Ön kayıt açma gövdesi: kalemler aynı istekte gönderilebilir."""

    items = DonationIntakeItemSerializer(many=True, required=False)

    class Meta(DonationIntakeSerializer.Meta):
        read_only_fields = [
            alan for alan in DonationIntakeSerializer.Meta.read_only_fields if alan != "items"
        ]


class DonationDecisionSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST donation-intakes/<pk>/decision/` — komisyon kararının uygulanması.

    Her kalem TAM OLARAK bir kez kararlanmalıdır; eksik, fazla ve yabancı kalem
    denetimi serviste ve TEK işlemdedir. `rejected` kalem kimliğinden gerekçeye
    bir eşlemedir (sözlük yerine liste kullanılsaydı aynı kalem iki gerekçeyle
    gönderilebilirdi).
    """

    commission_decision = serializers.PrimaryKeyRelatedField(
        queryset=CommissionDecision.objects.all(),
        error_messages=_iliski_hatalari("komisyon kararı", "Komisyon kararı seçilmelidir."),
    )
    accepted_ids = serializers.ListField(
        child=serializers.IntegerField(
            min_value=1, error_messages={"invalid": "Kalem kimliği sayısal olmalıdır."}
        ),
        required=False,
        default=list,
        error_messages={"not_a_list": "Kabul edilen kalemler liste olarak gönderilmelidir."},
    )
    rejected = serializers.DictField(
        child=serializers.CharField(max_length=255, error_messages=_ZORUNLU_METIN),
        required=False,
        default=dict,
        error_messages={"not_a_dict": "Reddedilen kalemler eşleme olarak gönderilmelidir."},
    )
    acquisition_date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        error_messages={"invalid": "Geçerli bir tarih girin."},
    )
    section = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages=_iliski_hatalari("bölüm", "Bölüm seçilmelidir."),
    )
    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=None,
        min_value=MIN_UNIT_PRICE,  # `Acquisition.unit_price` ile aynı taban
        error_messages={"min_value": "Birim fiyat eksi olamaz."},
    )
    # F8: kabul edilen kalemin nüshalarının ekleneceği eser (kalem kimliği → eser
    # kimliği; `null` = yeni eser aç). Verilmeyen kalemde katalogdaki birebir
    # eşleşme kendiliğinden kullanılır (`services.donations.item_matches`).
    work_links = serializers.DictField(
        child=serializers.IntegerField(
            min_value=1,
            allow_null=True,
            error_messages={"invalid": "Eser kimliği sayısal olmalıdır."},
        ),
        required=False,
        default=dict,
        error_messages={"not_a_dict": "Eser bağları eşleme olarak gönderilmelidir."},
    )

    def validate_work_links(self, value: dict[str, int | None]) -> dict[int, int | None]:
        """JSON anahtarları (kalem kimliği) metindir; sayıya çevrilir."""
        sonuc: dict[int, int | None] = {}
        for anahtar, eser in value.items():
            try:
                sonuc[int(anahtar)] = eser
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError("Kalem kimliği sayısal olmalıdır.") from exc
        return sonuc

    def validate_rejected(self, value: dict[str, str]) -> dict[int, str]:
        """Sözlük anahtarlarını kalem kimliğine çevirir (JSON anahtarı metindir)."""
        sonuc: dict[int, str] = {}
        for anahtar, gerekce in value.items():
            try:
                kimlik = int(anahtar)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    "Reddedilen kalem kimliği sayısal olmalıdır."
                ) from exc
            sonuc[kimlik] = gerekce
        return sonuc


class DonationCancelSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST donation-intakes/<pk>/cancel/` — bağış geri verildi, liste yanlış girildi…"""

    reason = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default="", trim_whitespace=True
    )


# ---------------------------------------------------------------------------
# Toplu katalog aktarımı (F3, tasarım §8.1 ve §8.2)
# ---------------------------------------------------------------------------
class JsonOrTextField(serializers.JSONField):
    """JSON gövdesinde nesne, çok parçalı (multipart) istekte JSON METNİ kabul eder.

    İçe aktarma isteği hem dosyayı hem kararları taşır: dosya yüklenirken gövde
    `multipart/form-data` olur ve orada her alan METİNDİR. DRF'in `JSONField`'ı
    metni olduğu gibi geçirir (metin de geçerli JSON'dur), yani kararlar sessizce
    dizge olarak servise inerdi.
    """

    default_error_messages = {"invalid": "Geçerli bir JSON değeri gönderin."}

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                self.fail("invalid")
        return super().to_internal_value(data)


class CatalogImportPreviewSerializer(serializers.Serializer[dict[str, Any]]):
    """`POST library/import/preview/` — dosya (Excel ya da köprü JSON'u) + kararlar.

    Dosya ile yapıştırılan JSON'dan tam olarak biri gönderilir. Önizleme ile
    uygulama AYNI gövdeyi alır: uygulama yalnız edinim alanlarını ekler, yani
    ekranda toplanan kararlar iki istekte de aynı adlarla taşınır.

    `decisions`: satır numarası → `{"action": "new"}` ya da
    `{"action": "attach", "work": <eser kimliği>}` / `{"action": "attach",
    "row": <dosya satırı>}` (şüpheli satırın kararı, §8.1).
    `section_map`: dosyadaki bölüm değeri → var olan bölümün kimliği.
    `new_sections`: yeni bölüm olarak açılacak değerler.
    """

    file = serializers.FileField(required=False)
    payload = JsonOrTextField(required=False)
    # `source` DRF `Field`'ın kendi özniteliğiyle aynı adı taşır ama çakışmaz:
    # serializer meta sınıfı tanımlanan alanları sınıf gövdesinden ÇIKARIP
    # `_declared_fields`'a taşır. Ad, `CatalogImportRun.source` ile aynı kalsın
    # diye korunmuştur (yanıtta da bu adla döner).
    source = serializers.ChoiceField(  # type: ignore[assignment]
        choices=CatalogImportSource.choices,
        required=False,
        default=CatalogImportSource.EXCEL,
        error_messages={"invalid_choice": "Geçerli bir kaynak seçin."},
    )
    # Varsayılan VERİLMEZ: gönderilmeyen alan `validated_data`'da hiç bulunmaz ve
    # servis kendi varsayılanını uygular (tek yer).
    decisions = JsonOrTextField(required=False)
    section_map = JsonOrTextField(required=False)
    new_sections = JsonOrTextField(required=False)

    def validate_file(self, value: Any) -> Any:
        return dosya_boyutunu_dogrula(value, tavan=MAX_UPLOAD_BYTES)

    def validate_decisions(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Kararlar satır numarasına göre eşleme olmalıdır.")
        return value

    def validate_section_map(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Bölüm eşlemesi bir eşleme olmalıdır.")
        return value

    def validate_new_sections(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise serializers.ValidationError("Yeni bölümler liste olarak gönderilmelidir.")
        return [str(ad).strip() for ad in value if str(ad).strip()]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        dosya_var = attrs.get("file") is not None
        govde_var = attrs.get("payload") is not None
        if dosya_var == govde_var:  # ikisi birden ya da hiçbiri
            raise serializers.ValidationError(
                "Dosya ya da yapıştırılan JSON alanlarından tam olarak biri gereklidir."
            )
        if govde_var:
            # Yapıştırılan JSON her zaman köprü şemasıdır (§8.2).
            attrs["source"] = CatalogImportSource.AI_JSON
        return attrs


class CatalogImportApplySerializer(CatalogImportPreviewSerializer):
    """`POST library/import/apply/` — önizlemedeki gövde + açılacak edinim partisi.

    Edinim alanları `AcquisitionSerializer` ile aynı adları taşır; kurallar
    (bağışta komisyon kararı ve türü — Md. 10/3, D7) servistedir.
    """

    method = serializers.ChoiceField(
        choices=AcquisitionMethod.choices,
        required=False,
        default=AcquisitionMethod.EXISTING_STOCK,
        error_messages={"invalid_choice": "Geçerli bir edinim yolu seçin."},
    )
    date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None,
        error_messages={"invalid": "Geçerli bir tarih girin."},
    )
    source_note = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default="", trim_whitespace=True
    )
    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        default=None,
        min_value=MIN_UNIT_PRICE,
        error_messages={"min_value": "Birim fiyat eksi olamaz."},
    )
    commission_decision = serializers.PrimaryKeyRelatedField(
        queryset=CommissionDecision.objects.all(),
        required=False,
        allow_null=True,
        default=None,
        error_messages=_iliski_hatalari("komisyon kararı", "Komisyon kararı seçilmelidir."),
    )
    notes = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=True
    )


class CatalogImportRunSerializer(serializers.ModelSerializer[CatalogImportRun]):
    """`GET library/import/runs/` — aktarım geçmişi (salt okunur; kişisel veri yok).

    Geçmiş iki soruya cevap verir: bu dosya daha önce uygulandı mı (fikirdeşlik)
    ve hangi parti hangi aktarımdan doğdu (F4 etiket kısayolu).
    """

    source_display = serializers.CharField(source="get_source_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CatalogImportRun
        fields = [
            "id",
            "uploaded_file_name",
            "source",
            "source_display",
            "status",
            "status_display",
            "payload_sha256",
            "schema_version",
            "acquisition",
            "stats",
            "report",
            "created_at",
        ]
        read_only_fields = fields
