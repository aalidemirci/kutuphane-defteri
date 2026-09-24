"""`okul` modelleri — kurum künyesi, ders yılı/dönemler, kapalı günler, kişi sicilleri, şube kataloğu, içe aktarma.

KS'den alındı (KS bunu DD'nin `apps/okul/models.py` kalıbından türetmişti);
Kütüphane Defteri için sadeleştirildi (tasarım §6.1, §12):

- `Student`: yalnız ad-soyad + okul no + sınıf/şube + durum + ayrılış tarihi.
  TCKN, veli ve cinsiyet alanları YOKTUR (tasarım §6.1 — en iyi KVKK önlemi
  veriyi hiç edinmemek). Ad-soyad VE okul no `EncryptedCharField`'dır (U9);
  okul no'nun eşleştirmesi ve tekliği kör indeksledir (T14), ad temelli arama
  ve bütün sıralamalar Python katmanındadır (selectors).
- `Personnel`: DD kalıbı + `is_active` + şifreli ad-soyad + `member_kind` +
  ayrılış tarihi. Unvan ve branş YOKTUR (V2-01: branş, küçük okulda öğretmeni
  kişiye bağlar).
- AYRILIŞ HAVUZU (F1 eki 7, kullanıcı kararı 22.09.2026): `Student` ve
  `Personnel` `leave_candidate_since` + `leave_candidate_run` taşır. e-Okul
  aktarımında listede bulunmayan AKTİF kişi havuza girer, durumu aktif kalır;
  karar yöneticinindir (`services.persons`). Havuzdaki kişi DB kısıtıyla
  aktiftir: ayrılış havuz alanlarını aynı kayıtta temizler.
- `ClassSection`: şube kataloğu — ders yılı içinde görülen (seviye, şube)
  çiftleri; içe aktarma sonrası tohumlanır.
- `Holiday`: DD'nin tatil tablosu, UYARLANARAK — + `SCHOOL_BREAK` türü
  ("öğrenciye kapalı gün"); iade tarihi kaydırmasının veri kaynağıdır
  (`shared.working_days`, tasarım §9-5).
- Sınıf seviyeleri OKUL İÇİ SABİTTİR (`normalize.GRADE_LEVELS`, 1-12); hazırlık
  sınıfı KS'deki gibi 0 koduyla temsil edilir ve `SchoolConfig.has_prep_class`
  açıkken geçerli kümeye girer.
- Koşullu UniqueConstraint'ler SQLite partial index ile çalışır (DD'de kanıtlı).
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.utils import timezone

from apps.okul.normalize import GRADE_LEVELS, PREP_LEVEL, normalize_student_number
from shared.crypto import EncryptedCharField, blind_index
from shared.models import BaseModel


def grade_levels_for(*, has_prep_class: bool) -> tuple[int, ...]:
    """Hazırlık bayrağından geçerli sınıf seviyeleri (artan sırada)."""
    return (PREP_LEVEL, *GRADE_LEVELS) if has_prep_class else GRADE_LEVELS


def _class_label(class_level: int, class_section: str) -> str:
    """'10/A' ya da hazırlıkta 'Hz/A' — evrak ve arayüzün beklediği etiket."""
    if class_level == PREP_LEVEL:
        return f"Hz/{class_section}"
    return f"{class_level}/{class_section}"


class SchoolLevel(models.TextChoices):
    """Okulun kademesi (tasarım §3 "Okul türü", §6.1 `SchoolConfig.kademe`).

    Md. 19 kayıp bedeli yalnız ortaöğretimde uygulanır; ilkokulda sınıf
    kitaplığı zorunludur (Md. 4/1-i, 5/1). Bu kurallar F6/F7'de buna bağlanır.
    F1'de kademe sınıf seviyelerini KISITLAMAZ (1-12 okul içi sabit kalır).
    """

    ILKOKUL = "ILKOKUL", "İlkokul"
    ORTAOKUL = "ORTAOKUL", "Ortaokul"
    ORTAOGRETIM = "ORTAOGRETIM", "Ortaöğretim (lise)"


class SchoolConfig(BaseModel):
    """Kurum bilgisi — TEK satır (singleton, pk=1).

    Kurulum sihirbazı doldurur; evrak antedi (okul adı/ilçe/müdür) buradan
    çözülür. `setup_completed` sihirbaz kapısıdır.

    `app_password_hash` (DD F5-D5 kalıbı, tasarım §5): adı tarihsel — içeriği
    parolanın özeti DEĞİLDİR; veri anahtarının (DEK) tek yönlü parmak izini
    tutar (`shared.crypto.key_fingerprint`). Parola/tuz/sarmal `guvenlik.json`
    dosyasındadır; DB ile güvenlik dosyasının eşleşmesi bu damgayla denetlenir
    ve alan şifreleme geçişi bu alanla AYNI işlemde damgalanır.

    F1 sihirbaz alanları (tasarım §3, §6.1, §14.1): `kademe`, `kisa_ad`
    (etiket ve kartlarda basılan kısa ad), `demirbas_onayi` + `demirbas_no`
    (Bilgi ve Sistem Güvenliği Yönergesi 11/8, 11/23: program yalnız kurum
    demirbaşı bilgisayara kurulur). Hiçbiri kişisel veri değildir, şifrelenmez.

    `yol_haritasi`: Genel Bakış'taki "Başlangıç Yol Haritası" kartının
    KULLANICININ İŞARETLEDİĞİ maddeleri (`{"isaretler": {madde: "gg-aa-yyyy"
    ISO tarih}, "gizli": bool}`; biçim `services.setup` tek kaynağındadır).
    Tarayıcı depolaması yerine burada durur: yönetim yüzeyi her açılışta
    RASTGELE portta dinler, köken (origin) değiştiği için `localStorage`
    açılışlar arasında taşınmaz; pencere profili de silinebilir önbellektedir.
    Kişisel veri İÇERMEZ (madde anahtarı + tarih).
    """

    SINGLETON_PK = 1

    school_name = models.CharField("okul adı", max_length=255, blank=True, default="")
    province = models.CharField("il", max_length=64, blank=True, default="")
    district = models.CharField("ilçe", max_length=64, blank=True, default="")
    principal_name = models.CharField("müdür adı", max_length=128, blank=True, default="")
    has_prep_class = models.BooleanField("hazırlık sınıfı var", default=False)
    kademe = models.CharField(
        "kademe", max_length=16, choices=SchoolLevel.choices, blank=True, default=""
    )
    kisa_ad = models.CharField("kısa okul adı", max_length=24, blank=True, default="")
    demirbas_onayi = models.BooleanField("bilgisayar okul demirbaşıdır", default=False)
    demirbas_no = models.CharField(
        "bilgisayarın demirbaş no'su", max_length=64, blank=True, default=""
    )
    yol_haritasi = models.JSONField("başlangıç yol haritası işaretleri", default=dict, blank=True)
    # F5 (tasarım §6.1, §5.1): Ağ Kataloğunun "Hakkında" sayfasında gösterilir
    # (`kd_katalog_okul` görünümü). Serbest metin; kişisel veri İÇERMEZ.
    kutuphane_saatleri = models.TextField(
        "kütüphane saatleri", max_length=500, blank=True, default=""
    )
    setup_completed = models.BooleanField("kurulum tamamlandı", default=False)
    app_password_hash = models.CharField(
        "yönetici parolası parmak izi", max_length=255, blank=True, default=""
    )

    class Meta:
        verbose_name = "kurum yapılandırması"
        verbose_name_plural = "kurum yapılandırması"
        constraints = [
            # Boş = sihirbazda henüz seçilmedi (kurulum tamamlanamaz).
            models.CheckConstraint(
                condition=models.Q(kademe__in=[*SchoolLevel.values, ""]),
                name="ck_schoolconfig_kademe",
            ),
        ]

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


class HolidayKind(models.TextChoices):
    """Kapalı gün türü — DD `HolidayKind` + `SCHOOL_BREAK` (tasarım §6.1, §9-5).

    İade tarihi kaydırmasında türler İKİ ayrı kurala ayrılır; dayanakları farklıdır
    (`shared.working_days` modül yorumu):

    - `OFFICIAL`, `RELIGIOUS`, `OTHER` her zaman kapalıdır (hafta sonu gibi).
    - `SCHOOL_BREAK` ("öğrenciye kapalı gün": ara tatil, yarıyıl) kanunen tatil
      DEĞİLDİR, mesai sürer; bu günlerde kaydırma okulun tercihidir ve ayarla
      kapanır. DD bu günleri Holiday'e hiç almıyordu (disiplin süreleri işler);
      kütüphanede öğrenci okulda olmadığı için ayrı türle tutulur (UY-13, SU-6).
    """

    OFFICIAL = "OFFICIAL", "Resmî tatil"
    RELIGIOUS = "RELIGIOUS", "Dini bayram"
    SCHOOL_BREAK = "SCHOOL_BREAK", "Öğrenciye kapalı gün"
    OTHER = "OTHER", "İdari izin / diğer"


class Holiday(BaseModel):
    """Kapalı gün aralığı (DD `Holiday` — UYARLA; tasarım §6.1).

    Ders yılına BAĞLANMAZ (DD kalıbı): kapalı gün sorusu tarih kapsamasıyla
    cevaplanır. Tek günlük kayıtta başlangıç ve bitiş aynı gündür.

    `is_estimated`: hicri takvime bağlı dini bayramlar Diyanet takvimi
    kesinleşmeden önce TAHMİNİDİR (2027 ve sonrası); arayüz "tahmini" rozetiyle
    gösterir. Yalnız tohumlama yazar; elle girilen kayıt kesin tarih sayılır.
    """

    name = models.CharField("ad", max_length=128)
    start_date = models.DateField("başlangıç", db_index=True)
    end_date = models.DateField("bitiş")
    kind = models.CharField(
        "tür", max_length=16, choices=HolidayKind.choices, default=HolidayKind.OFFICIAL
    )
    is_estimated = models.BooleanField("tahmini", default=False)

    class Meta:
        verbose_name = "kapalı gün"
        verbose_name_plural = "kapalı günler"
        ordering = ["start_date", "end_date", "pk"]
        constraints = [
            # Tohumlama fikirdeşliğinin DB sigortası: aynı (ad, başlangıç) canlı satır tekil.
            models.UniqueConstraint(
                fields=["name", "start_date"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_holiday_name_start_alive",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ck_holiday_date_order",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=HolidayKind.values),
                name="ck_holiday_kind",
            ),
            # "Tahmini" yalnız hicri takvime bağlı dini bayramda anlamlıdır.
            models.CheckConstraint(
                condition=models.Q(is_estimated=False) | models.Q(kind=HolidayKind.RELIGIOUS),
                name="ck_holiday_estimated_religious",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date})"


class MemberKind(models.TextChoices):
    """Personelin üye türü (sözlük: "öğretmen" / "diğer personel").

    Md. 18 sayı sınırı (öğretmen 5) ve diğer personele ödünç kararı (F6) buna
    bağlanır. Şifrelenmez (tasarım §6.3 "açık kalanlar"). Unvanın yerini
    ALMAZ: e-Okul'daki görev metni yalnız bu iki değerden birini seçmek için
    aktarım sırasında geçici okunur, saklanmaz (C sözleşmesi, F1 eki).
    """

    TEACHER = "TEACHER", "öğretmen"
    STAFF = "STAFF", "diğer personel"


class Personnel(BaseModel):
    """Okul personeli — login'siz sicil kaydı (tasarım §6.1).

    Ayrılışta `is_active=False` + `left_at` yazılır (`services.persons`
    ayrılış yolu); kayıt SİLİNMEZ (F1 eki 7), saklama taraması (§6.4, F11)
    aday gösterir. e-Okul listesinde bulunmayan aktif kişi önce ayrılış
    havuzuna girer (`leave_candidate_since`). Ad-soyad ŞİFRELİDİR (U3) — ada
    dayalı arama, sıralama ve eşleştirme Python katmanında yapılır. Unvan ve
    branş YOKTUR (V2-01).
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    member_kind = models.CharField(
        "üye türü", max_length=16, choices=MemberKind.choices, default=MemberKind.TEACHER
    )
    is_active = models.BooleanField("aktif", default=True)
    left_at = models.DateField("ayrılış tarihi", null=True, blank=True)
    leave_candidate_since = models.DateField("ayrılış havuzuna giriş tarihi", null=True, blank=True)
    leave_candidate_run = models.ForeignKey(
        "ImportRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="havuza ekleyen aktarım",
    )

    class Meta:
        verbose_name = "personel"
        verbose_name_plural = "personel"
        # Şifreli alanda DB sıralaması anlamsızdır (token sırası) — kayıt sırası
        # kararlı olsun diye pk; ad sıralaması selector'da Python ile yapılır.
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(member_kind__in=MemberKind.values),
                name="ck_personnel_member_kind",
            ),
            # Ayrılış havuzunda yalnız AKTİF kişi bekler (ayrılış havuzu temizler).
            models.CheckConstraint(
                condition=models.Q(leave_candidate_since__isnull=True) | models.Q(is_active=True),
                name="ck_personnel_leave_candidate_active",
            ),
        ]

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


def student_number_blind_index(student_number: str) -> str:
    """Okul numarasının kör indeksi (tasarım §6.3, T14); boş numara → ''.

    Yazmada (`Student.save`) ve aramada (`selectors`) AYNI yol kullanılır:
    `normalize_student_number` ('0123' ≡ '123') + `crypto.blind_index`.
    Anahtar bellekte değilse `KeyMissingError` (fail-closed).
    """
    return blind_index(normalize_student_number(student_number))


class Student(BaseModel):
    """Öğrenci — okul sicilinin kişi kaydı (tasarım §6.1).

    Evrak sözleşmesi: `full_name`, `student_number`, `class_label` — basılı
    belgeler ve anlık görüntüler (snapshot) bu üçünden beslenir.

    ŞİFRELEME KAPSAMI (U9, tasarım §6.3): ad, soyad ve OKUL NO şifrelidir;
    sınıf/şube ve durum AÇIKTIR. Okul no şifreli olduğu için DB'de onunla
    süzülemez ve sıralanamaz: kimlik eşleştirmesi (e-Okul, arama, teklik)
    `student_number_index` kör indeksiyle TAM EŞLEŞMEDİR, okul no'ya göre
    sıralama selector'da Python'dadır. TCKN, veli ve cinsiyet alanı YOKTUR.

    KÖR İNDEKS YALNIZ `save()` İLE YAZILIR: `QuerySet.update(student_number=…)`,
    `bulk_update` ve `bulk_create` `save()`'i atlar, indeks eski numarada (ya da
    boş) kalır ve eşleştirme sessizce bozulur. Okul no toplu yazılmaz (koruma
    testi: `test_models.py::test_okul_no_toplu_yazilmaz`).

    AYRILIŞ HAVUZU (F1 eki 7): e-Okul aktarımı kimseyi ayırmaz; dosyada
    bulunmayan aktif öğrenci `leave_candidate_since` (+ hangi aktarımla)
    damgasıyla havuza girer, durumu AKTİF kalır. Ayrılış (LEFT + `left_at`)
    kaydı silmez.
    """

    first_name = EncryptedCharField("ad", max_length=100)
    last_name = EncryptedCharField("soyad", max_length=100)
    student_number = EncryptedCharField("okul no", max_length=16, blank=True, default="")
    student_number_index = models.CharField(
        "okul no kör indeksi", max_length=64, blank=True, default="", editable=False
    )
    class_level = models.PositiveSmallIntegerField("sınıf", null=True, blank=True)
    class_section = models.CharField("şube", max_length=8, blank=True, default="")
    status = models.CharField(
        "durum", max_length=16, choices=StudentStatus.choices, default=StudentStatus.ACTIVE
    )
    left_at = models.DateField("ayrılış tarihi", null=True, blank=True)
    leave_candidate_since = models.DateField("ayrılış havuzuna giriş tarihi", null=True, blank=True)
    leave_candidate_run = models.ForeignKey(
        "ImportRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="havuza ekleyen aktarım",
    )

    class Meta:
        verbose_name = "öğrenci"
        verbose_name_plural = "öğrenciler"
        # Ad ve okul no şifreli → DB'de onlara sıralanamaz. Kararlı bir DB sırası
        # yeter; kullanıcıya gösterilen sıra (sınıf, şube TR, okul no doğal)
        # `selectors.students_sorted` ile Python'da kurulur.
        ordering = ["class_level", "class_section", "pk"]
        indexes = [
            models.Index(fields=["class_level", "class_section"], name="okul_student_class_idx"),
            # Eşleştirme (e-Okul, arama, yeniden aktifleşme) indeks üzerinden yapılır.
            models.Index(fields=["student_number_index"], name="okul_student_numidx_idx"),
        ]
        constraints = [
            # Okul numaralı AKTİF canlı kayıt tekil — içe aktarma eşleştirme anahtarı.
            # Teklik KÖR İNDEKSE konur (T14): şifreli sütunda token her yazımda
            # değiştiği için teklik orada çalışmaz. Ayrılan öğrencinin numarası
            # ileride başka öğrenciye verilebilir.
            models.UniqueConstraint(
                fields=["student_number_index"],
                condition=(
                    models.Q(deleted_at__isnull=True, status="ACTIVE")
                    & ~models.Q(student_number_index="")
                ),
                name="uq_student_number_index_active_alive",
            ),
            # Ayrılış havuzunda yalnız AKTİF öğrenci bekler (ayrılış havuzu temizler).
            models.CheckConstraint(
                condition=models.Q(leave_candidate_since__isnull=True) | models.Q(status="ACTIVE"),
                name="ck_student_leave_candidate_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.class_label or 'sınıfsız'})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Okul no'nun kör indeksini günceller, sonra kaydeder.

        `update_fields` verilmişse ve okul no içinde yoksa indeks yeniden
        hesaplanmaz (numara değişmedi; anahtar gerekmez). Okul no içindeyse
        indeks alanı da `update_fields`'e eklenir — aksi hâlde yeni numara
        yazılır, indeks eskide kalırdı.
        """
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "student_number" in update_fields:
            self.student_number_index = student_number_blind_index(self.student_number)
            if update_fields is not None and "student_number_index" not in update_fields:
                kwargs["update_fields"] = [*update_fields, "student_number_index"]
        super().save(*args, **kwargs)

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
