"""`okul` modelleri — kurum künyesi, ders yılı/dönemler, kişi sicilleri, şube kataloğu, içe aktarma.

KS'den alındı (KS bunu DD'nin `apps/okul/models.py` kalıbından türetmişti);
Kütüphane Defteri için sadeleştirildi (tasarım §6.1, §12):

- `Student`: yalnız ad-soyad + okul no + sınıf/şube + durum. TCKN, veli ve
  cinsiyet alanları YOKTUR (tasarım §6.1 — en iyi KVKK önlemi veriyi hiç
  edinmemek). Ad-soyad `EncryptedCharField`'dır; ad temelli arama Python
  katmanındadır (teknik borç TB3; selectors katlayarak arar).
- `Personnel`: DD kalıbı + `is_active` + şifreli ad-soyad.
- `ClassSection`: şube kataloğu — ders yılı içinde görülen (seviye, şube)
  çiftleri; içe aktarma sonrası tohumlanır.
- Sınıf seviyeleri OKUL İÇİ SABİTTİR (`normalize.GRADE_LEVELS`, 1-12); hazırlık
  sınıfı KS'deki gibi 0 koduyla temsil edilir ve `SchoolConfig.has_prep_class`
  açıkken geçerli kümeye girer.
- Koşullu UniqueConstraint'ler SQLite partial index ile çalışır (DD'de kanıtlı).
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.okul.normalize import GRADE_LEVELS, PREP_LEVEL
from shared.crypto import EncryptedCharField
from shared.models import BaseModel


def grade_levels_for(*, has_prep_class: bool) -> tuple[int, ...]:
    """Hazırlık bayrağından geçerli sınıf seviyeleri (artan sırada)."""
    return (PREP_LEVEL, *GRADE_LEVELS) if has_prep_class else GRADE_LEVELS


def _class_label(class_level: int, class_section: str) -> str:
    """'10/A' ya da hazırlıkta 'Hz/A' — evrak ve arayüzün beklediği etiket."""
    if class_level == PREP_LEVEL:
        return f"Hz/{class_section}"
    return f"{class_level}/{class_section}"


class SchoolConfig(BaseModel):
    """Kurum bilgisi — TEK satır (singleton, pk=1).

    Kurulum sihirbazı doldurur; evrak antedi (okul adı/ilçe/müdür) buradan
    çözülür. `setup_completed` sihirbaz kapısıdır.

    `app_password_hash` (DD F5-D5 kalıbı, tasarım §5): adı tarihsel — içeriği
    parolanın özeti DEĞİLDİR; veri anahtarının (DEK) tek yönlü parmak izini
    tutar (`shared.crypto.key_fingerprint`). Parola/tuz/sarmal `guvenlik.json`
    dosyasındadır; DB ile güvenlik dosyasının eşleşmesi bu damgayla denetlenir
    ve alan şifreleme geçişi bu alanla AYNI işlemde damgalanır.
    """

    SINGLETON_PK = 1

    school_name = models.CharField("okul adı", max_length=255, blank=True, default="")
    province = models.CharField("il", max_length=64, blank=True, default="")
    district = models.CharField("ilçe", max_length=64, blank=True, default="")
    principal_name = models.CharField("müdür adı", max_length=128, blank=True, default="")
    has_prep_class = models.BooleanField("hazırlık sınıfı var", default=False)
    setup_completed = models.BooleanField("kurulum tamamlandı", default=False)
    app_password_hash = models.CharField(
        "uygulama parolası özeti", max_length=255, blank=True, default=""
    )

    class Meta:
        verbose_name = "kurum yapılandırması"
        verbose_name_plural = "kurum yapılandırması"

    def __str__(self) -> str:
        return self.school_name or "Kurulmamış okul"

    @classmethod
    def load(cls) -> SchoolConfig:
        """Singleton satırı döndürür; yoksa KAYDEDİLMEMİŞ varsayılan (okuma yazmaz)."""
        instance: SchoolConfig | None = cls.objects.filter(pk=cls.SINGLETON_PK).first()
        return instance if instance is not None else cls(pk=None)

    @property
    def grade_levels(self) -> tuple[int, ...]:
        """Bu okulda geçerli sınıf seviyeleri (0=Hazırlık dahil olabilir)."""
        return grade_levels_for(has_prep_class=self.has_prep_class)


class SchoolYear(BaseModel):
    """Ders yılı (örn. '2026-2027'). Tek-aktif kuralı hem serviste hem DB kısıtında."""

    name = models.CharField("ad", max_length=32)
    start_date = models.DateField("başlangıç")
    end_date = models.DateField("bitiş")
    is_active = models.BooleanField("aktif", default=False)

    class Meta:
        verbose_name = "ders yılı"
        verbose_name_plural = "ders yılları"
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_schoolyear_name_alive",
            ),
            # Savunma hattı: aktif yıl değişimi serviste "önce eskisini kapat"
            # sırasıyla yapılır; kısıt yarış/hata durumunda ikinci aktifi keser.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True, deleted_at__isnull=True),
                name="uq_schoolyear_single_active",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class SchoolTerm(BaseModel):
    """Ders yılının iki dönemi — dönem bazlı raporlar ve tarih → dönem çözümü buna bağlanır."""

    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.CASCADE,
        related_name="terms",
        verbose_name="ders yılı",
    )
    sequence = models.PositiveSmallIntegerField("dönem", choices=((1, "1. dönem"), (2, "2. dönem")))
    start_date = models.DateField("başlangıç")
    end_date = models.DateField("bitiş")

    class Meta:
        verbose_name = "ders dönemi"
        verbose_name_plural = "ders dönemleri"
        ordering = ["school_year", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_year", "sequence"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_schoolterm_year_sequence_alive",
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__in=(1, 2)),
                name="ck_schoolterm_sequence",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ck_schoolterm_date_order",
            ),
        ]
        indexes = [
            models.Index(fields=["school_year", "start_date"], name="schoolterm_year_start_idx"),
        ]

    @property
    def name(self) -> str:
        return f"{self.sequence}. dönem"

    def __str__(self) -> str:
        return f"{self.school_year.name} · {self.name}"


class Personnel(BaseModel):
    """Okul personeli — login'siz sicil kaydı.

    `is_active` okuldan ayrılan personeli sicilde tutarken seçicilerden düşürür.
    Ad-soyad ŞİFRELİDİR (U3) — ada dayalı arama/teklik Python katmanında
    yapılır (TB3), unvan/branş süzgeçleri DB tarafında kalır.
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    title = models.CharField("unvan", max_length=64, blank=True, default="")
    branch = models.CharField("branş", max_length=64, blank=True, default="")
    is_active = models.BooleanField("aktif", default=True)

    class Meta:
        verbose_name = "personel"
        verbose_name_plural = "personel"
        # Şifreli alanda DB sıralaması anlamsızdır (token sırası) — kayıt sırası
        # kararlı olsun diye pk; ad sıralaması selector'da Python ile yapılır.
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        """OYS `User.get_full_name` paritesi — evrak şablonları bu adı çağırır."""
        return self.full_name


class ClassSection(BaseModel):
    """Şube kataloğu — ders yılı içinde görülen (seviye, şube) çiftleri.

    İçe aktarma sonrası tohumlanır (`imports._ensure_class_sections`), elle de
    eklenebilir. Seçiciler ve şube bazlı listeler bu katalogdan beslenir.
    """

    school_year = models.ForeignKey(
        SchoolYear,
        on_delete=models.PROTECT,
        related_name="class_sections",
        verbose_name="ders yılı",
    )
    class_level = models.PositiveSmallIntegerField("sınıf")
    class_section = models.CharField("şube", max_length=8)

    class Meta:
        verbose_name = "şube"
        verbose_name_plural = "şubeler"
        ordering = ["school_year", "class_level", "class_section"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_year", "class_level", "class_section"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_class_section_alive",
            )
        ]
        indexes = [
            models.Index(
                fields=["school_year", "class_level", "class_section"],
                name="okul_class_section_lookup_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.school_year.name} — {self.class_label}"

    @property
    def class_label(self) -> str:
        return _class_label(self.class_level, self.class_section)


class StudentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Aktif"
    LEFT = "LEFT", "Ayrıldı"


class Student(BaseModel):
    """Öğrenci — okul sicilinin kişi kaydı (tasarım §6.1).

    Evrak sözleşmesi: `full_name`, `student_number`, `class_label` — basılı
    belgeler ve anlık görüntüler (snapshot) bu üçünden beslenir.

    ŞİFRELEME KAPSAMI (U3, tasarım §5): `first_name`/`last_name` şifrelidir;
    okul no ve sınıf/şube AÇIKTIR (sıralama, teklik ve süzgeçler bunlara
    dayanır; ad olmadan takma-adlıdırlar). TCKN, veli ve cinsiyet alanı YOKTUR.
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    student_number = models.CharField("okul no", max_length=16, blank=True, default="")
    class_level = models.PositiveSmallIntegerField("sınıf", null=True, blank=True)
    class_section = models.CharField("şube", max_length=8, blank=True, default="")
    status = models.CharField(
        "durum", max_length=16, choices=StudentStatus.choices, default=StudentStatus.ACTIVE
    )

    class Meta:
        verbose_name = "öğrenci"
        verbose_name_plural = "öğrenciler"
        # Ad şifreli → DB'de ada sıralanamaz; sınıf/şube/no sıralaması yeter
        # (okul no metin alanıdır, sayısal sıralama selector'da yapılır).
        ordering = ["class_level", "class_section", "student_number"]
        indexes = [
            models.Index(fields=["class_level", "class_section"], name="okul_student_class_idx"),
        ]
        constraints = [
            # Okul numaralı AKTİF canlı kayıt tekil — içe aktarma upsert anahtarı.
            # Ayrılan öğrencinin numarası ileride başka öğrenciye verilebilir.
            models.UniqueConstraint(
                fields=["student_number"],
                condition=(
                    models.Q(deleted_at__isnull=True, status="ACTIVE")
                    & ~models.Q(student_number="")
                ),
                name="uq_student_number_active_alive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.class_label or 'sınıfsız'})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def class_label(self) -> str:
        """'10/A' — evrak ve arayüzün beklediği sınıf etiketi; sınıfsız → ''."""
        if self.class_level is None or not self.class_section:
            return ""
        return _class_label(self.class_level, self.class_section)


class ImportSourceType(models.TextChoices):
    """İçe aktarma kaynak türü (xlsx ve pano yapıştırma AYNI türdedir)."""

    STUDENTS = "STUDENTS", "Öğrenci"
    PERSONNEL = "PERSONNEL", "Personel"


class ImportStatus(models.TextChoices):
    RUNNING = "RUNNING", "Çalışıyor"
    COMPLETED = "COMPLETED", "Tamamlandı"
    FAILED = "FAILED", "Başarısız"
    PREVIEWED = "PREVIEWED", "Önizlendi"


class ImportRun(BaseModel):
    """Her toplu içe aktarma için bir kayıt (geçmiş izi + idempotency uyarısı).

    DD kalıbı: aynı dosyanın yeniden COMMIT'i ENGELLENMEZ — `already_imported`
    yalnız UYARIDIR (güncelleme meşru). Kısıt bozulmasın diye yeniden commit
    MEVCUT COMPLETED satırı günceller (yeni satır açmaz).
    """

    source_type = models.CharField(
        "kaynak türü", max_length=16, choices=ImportSourceType.choices, db_index=True
    )
    file_name = models.CharField("dosya adı", max_length=255, blank=True, default="")
    file_hash = models.CharField("içerik özeti (SHA256)", max_length=64, db_index=True)
    status = models.CharField(
        "durum", max_length=16, choices=ImportStatus.choices, default=ImportStatus.RUNNING
    )
    started_at = models.DateTimeField("başlangıç", default=timezone.now)
    finished_at = models.DateTimeField("bitiş", null=True, blank=True)
    report = models.JSONField("rapor", default=dict, blank=True)

    class Meta:
        verbose_name = "içe aktarma koşusu"
        verbose_name_plural = "içe aktarma koşuları"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["source_type", "file_hash"], name="okul_importrun_hash_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "file_hash"],
                condition=models.Q(deleted_at__isnull=True, status="COMPLETED"),
                name="uq_importrun_completed_per_hash",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_type_display()} — {self.file_name or self.file_hash[:12]}"
