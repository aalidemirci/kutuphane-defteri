"""`kutuphane` modelleri — katalog çekirdeği: bölüm, eser, nüsha, edinim, politika.

OYS'nin (Okul Yönetim Sistemi) `apps/kutuphane/models.py` dosyasından UYARLA
(tasarım §6.2, §12). Ortak değişiklikler: `created_by`/`by_user` düşer (tek
kullanıcılı masaüstü programı — "kim yaptı" anlamsız), `core.*` bağları
`okul.*` olur, göç ağacı `0001`'den başlar. OYS'nin üyelik, ödünç, ayıklama ve
sayım modelleri BU FAZDA GELMEZ; kendi fazlarında (F6-F9) eklenir.

Bu fazın kararları (tasarım §6.2, F2 sözleşmesi §1):

- **`LibraryPolicy`'de ödünç süresi alanı YOKTUR** (D19, CLAUDE.md §2-6).
  Md. 18: "Bir kitabı ödünç alma süresi on beş gündür." OYS'nin 1-15 arası
  ayarlanabilir alanı ALINMADI: mevzuatın sabit koyduğu bir süreyi ayara
  açmak, okulu farkında olmadan hükme aykırı bir uygulamaya sokar.
- **Türkçe anahtar alanları** (`search_key`, `sort_key`, `author_sort_key`,
  `subject_sort_key`): SQLite'ın `LIKE`'ı ve BINARY sıralaması Türkçe harflerde
  çalışmaz (T7, D2). Anahtarlar `save()`'de türetilir; tek katlama kaynağı
  `apps.kutuphane.keys` üzerinden `shared.text` ve `apps.okul.normalize`'dır.
- **Tanımlayıcı tablosu** (SU-11, UY-22): bir nüshanın dört ayrı numarası
  olabilir ve hepsi farklı şeyi anlatır — `barcode` (programın ürettiği 10
  haneli kütüphane numarası), `accession_no` (aynı sayının tamsayı hâli, TMY
  Kütüphane Defteri'nin kayıt no'su), `external_asset_ref` (TKYS kodu),
  `old_register_no` (kitaptaki eski damga). Karıştırılmasınlar diye dördü de
  ayrı alandır ve sözlükte ayrı adları vardır.
- **Şifreli alanlar** (§6.3): bağışçı (`Acquisition.source_note`,
  `DonationIntake.donor_name`) ve komisyon adları (`CommissionDecision`).
  Katalog alanları ASLA şifrelenmez (T6): şifreli alanda DB araması yapılamaz
  ve Ağ Kataloğu program kilitliyken de çalışmalıdır.
- **Barkod ve kayıt no asla yeniden kullanılmaz**: teklik kısıtı DÜZ `unique`'tir
  (kısmi değil), yani yumuşak silinmiş nüshanın numarası da tutulur.
- **F4 (etiketler)**: basım kaydı (`LabelPrintBatch` — PDF üretmek "basıldı"
  değildir, D10), iki ayrı basım işareti (`Copy.label_printed_at` barkod,
  `Copy.spine_label_printed_at` sırt) ve boş barkod aralığı
  (`BarcodeReservation` + `ReservedBarcode`, yöntem B — numaralar AYNI sayaçtan,
  iptal edilen numara sayaca dönmez).

CLAUDE.md §3 "soft-delete ileri FK'da süzmez": `obj.fk` erişimi silinmiş kaydı
geri getirir. Evraka ad basan yollar `deleted_at`'i elle denetler; katalog
görünümleri (F5) silinmiş eser ve nüshayı TANIMLARINDA süzer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane import keys
from apps.kutuphane.import_schema import MAX_COPIES_PER_ROW
from shared.crypto import EncryptedCharField, EncryptedTextField
from shared.models import BaseModel


class ResourceType(models.TextChoices):
    """Kaynak türü (Okul Kütüphaneleri Yönetmeliği Md. 4/1-ç geniş tanımı).

    Danışma kaynağı BİR TÜR DEĞİLDİR — nüsha bayrağıdır (`Copy.is_reference`);
    ders kitabı da ayrı bir tür değil, danışma varsayılanını açan bir konudur
    (§8.1). EBOOK/EDATABASE dijitaldir: eser olarak katalogda yer alır ama
    nüshası açılamaz (TMY'nin fiziksel taşınır düzeni dışı — servis kuralı).
    """

    BOOK = "BOOK", "Kitap"
    PERIODICAL = "PERIODICAL", "Süreli yayın"
    AV_MATERIAL = "AV_MATERIAL", "Görsel-işitsel materyal"
    EBOOK = "EBOOK", "E-kitap"
    EDATABASE = "EDATABASE", "E-veri tabanı"


#: Dijital kaynak türleri — nüsha açılamaz (tek kaynak; servisler buna bakar).
DIGITAL_RESOURCE_TYPES: tuple[str, ...] = (ResourceType.EBOOK, ResourceType.EDATABASE)

#: Yayın yılının makul aralığı. Amaç doğrulama değil, YAZIM HATASI süzgecidir:
#: alan `PositiveSmallIntegerField` olduğu için 30000 bile kabul ediliyordu ve
#: künye ekranda saçma görünüyordu. Üst sınır sabittir (çağrılabilir sınır DRF
#: `min_value`/`max_value` eşlemesini bozar) ve pratikte hiç dolmaz.
PUBLISH_YEAR_MIN = 1000
PUBLISH_YEAR_MAX = 2999

#: Birim fiyat TMY Md. 13/2'nin giriş kaydına esas değeridir ve F10'un Taşınır
#: Kütüphane Defteri dökümünde TOPLANIR: eksi işaretli tek bir yazım hatası
#: toplamı sessizce bozar. Bedelsiz giriş (bağış, Bakanlık gönderimi) sıfırdır,
#: eksi değil.
MIN_UNIT_PRICE = Decimal("0")


class ClassificationSource(models.TextChoices):
    """Sınıflama kodunun kaynağı (içe aktarma izlenebilirliği — F3).

    CATALOG: kütüphane kataloğundan bulundu · ESTIMATED: yakın kategoriden
    tahmin (arayüzde "tahmini" rozetiyle gösterilir) · MANUAL: elle girildi.
    """

    CATALOG = "CATALOG", "Katalogdan bulundu"
    ESTIMATED = "ESTIMATED", "Tahmini"
    MANUAL = "MANUAL", "Elle girildi"


class AcquisitionMethod(models.TextChoices):
    """Edinim yolu (Md. 10/5 kapalı listesi + iki kayıt-içi giriş).

    Md. 10/5 *dışarıdan sağlama* yollarını sayar: MINISTRY/PURCHASE/DONATION/
    EXCHANGE. INVENTORY_FOUND (sayım fazlasının kayda alınması — TMY Md. 17,
    32/7) ve EXISTING_STOCK (mevcut koleksiyonun programa ilk aktarımı — dış
    edinim değil, kayıt işlemi) kayıt-içi girişlerdir.
    """

    MINISTRY = "MINISTRY", "Bakanlık gönderimi"
    PURCHASE = "PURCHASE", "Satın alma"
    DONATION = "DONATION", "Bağış"
    EXCHANGE = "EXCHANGE", "Değişim"
    INVENTORY_FOUND = "INVENTORY_FOUND", "Sayım fazlası (kayda giriş)"
    EXISTING_STOCK = "EXISTING_STOCK", "Mevcut koleksiyon (programa aktarım)"


class CopyStatus(models.TextChoices):
    """Nüsha durumu. Geçişler YALNIZ servislerden yapılır (view durum yazmaz).

    Kullanıcıya görünen adlar docs/sozluk.md'dedir. "Gecikmiş" BURADA YOKTUR:
    gecikme türetilmiş bir sorgudur (F6), durum değil. Danışma kaynağının
    "Ödünç verilmez — kütüphanede okunur" hâli de durum değildir, nüsha
    bayrağından (`is_reference`) türetilir.

    DELIVERED (U11): sınıf kitaplığına ya da öğretmene teslim. Teslim ödünç
    DEĞİLDİR, Md. 18 sayı sınırı uygulanmaz (§9-11); akışı F7'de gelir.
    IN_REPAIR'in giriş/çıkış yolu F7'de yazılır (D3).
    WITHDRAWN_*/TRANSFERRED terminaldir — yumuşak silme DEĞİL: kayıttan düşülen
    nüsha defterde ve tutanakta görünmeye devam eder.
    """

    AVAILABLE = "AVAILABLE", "Rafta"
    ON_LOAN = "ON_LOAN", "Ödünçte"
    DELIVERED = "DELIVERED", "Sınıf kitaplığında"
    IN_REPAIR = "IN_REPAIR", "Onarımda"
    LOST = "LOST", "Kayıp"
    WITHDRAWN_WEEDED = "WITHDRAWN_WEEDED", "Ayıklandı (kayıttan düşüldü)"
    WITHDRAWN_MISSING = "WITHDRAWN_MISSING", "Sayım noksanı (kayıttan düşüldü)"
    WITHDRAWN_LOST = "WITHDRAWN_LOST", "Kayıp (kayıttan düşüldü)"
    TRANSFERRED = "TRANSFERRED", "Devredildi"


#: Kayıttan düşülmüş ya da devredilmiş nüshalar — etiket kuyruğuna, sayıma ve
#: dolaşıma girmezler (tek kaynak; selector'lar buna bakar).
TERMINAL_COPY_STATUSES: tuple[str, ...] = (
    CopyStatus.WITHDRAWN_WEEDED,
    CopyStatus.WITHDRAWN_MISSING,
    CopyStatus.WITHDRAWN_LOST,
    CopyStatus.TRANSFERRED,
)


class CommissionDecisionType(models.TextChoices):
    """Seçim ve Ayıklama Komisyonu karar türü (Md. 4/1-ı, 10/1).

    Tür denetimi D7'nin düzeltmesidir: OYS türü kaydediyor ama kullanırken
    denetlemiyordu — bir ayıklama kararı bağış edinimine, bir bağış kararı
    ayıklama partisine bağlanabiliyordu. Denetim servislerdedir
    (`services.commissions.require_decision_type`).
    """

    SELECTION = "SELECTION", "Kaynak seçimi"
    DONATION_REVIEW = "DONATION_REVIEW", "Bağış değerlendirme"
    WEEDING = "WEEDING", "Ayıklama"


class LibraryPolicy(BaseModel):
    """Kütüphane politikası — tek satır (singleton, pk=1). Kişisel veri taşımaz.

    Sayısal sınırlar koda gömülmez, buradan okunur; mevzuatın üst sınırı
    validator ile zorlanır (üstüne çıkılamaz — Md. 18).

    **Ödünç süresi alanı YOKTUR** (D19): Md. 18 süreyi "on beş gün" olarak
    sabitler. Süre `shared`/servis sabitidir (F6), ayar değildir.

    `staff_loans_enabled` (diğer personele ödünç): Yönetmelikte ayrıca
    düzenlenmemiştir; 13/1 diğer personeli yalnız kullanıcı hizmetlerinden
    yararlananlar arasında sayar. Programın ihtiyat kuralı (AT-4): seçenek okul
    müdürlüğü kararıyla açılır ve kararın TARİHİ ile SAYISI zorunludur — DB
    kısıtı da bunu zorlar.
    """

    SINGLETON_PK = 1

    max_loans_student = models.PositiveSmallIntegerField(
        "öğrenci ödünç sayısı sınırı",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text="Md. 18: öğrenciye bir defasında en fazla üç kitap verilir.",
    )
    max_loans_teacher = models.PositiveSmallIntegerField(
        "öğretmen ödünç sayısı sınırı",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Md. 18: öğretmene bir defasında en fazla beş kitap verilir.",
    )
    max_loans_staff = models.PositiveSmallIntegerField(
        "diğer personel ödünç sayısı sınırı",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Mevzuatta sayı sınırı yoktur; okulun takdiridir (öğretmen paritesi ≤ 5).",
    )
    staff_loans_enabled = models.BooleanField(
        "diğer personele ödünç verilir",
        default=False,
        help_text="Okul müdürlüğü kararıyla açılır; kararın tarihi ve sayısı zorunludur.",
    )
    staff_loans_decision_date = models.DateField("müdürlük kararı tarihi", null=True, blank=True)
    staff_loans_decision_no = models.CharField(
        "müdürlük kararı sayısı", max_length=40, blank=True, default=""
    )
    block_loan_if_overdue = models.BooleanField(
        "gecikmiş kitabı olana yeni ödünç verilmez",
        default=True,
        help_text="İstisnası yalnız yönetici kipinde ve gerekçeyle tanınır (F6).",
    )
    shift_due_date_on_school_break = models.BooleanField(
        "iade tarihi öğrenciye kapalı günlerde kaydırılır",
        default=True,
        help_text=(
            "Ara tatil ve yarıyıl kanunen tatil değildir; bu kaydırmanın mevzuat "
            "dayanağı yoktur, okulun tercihidir (§9-5). Resmî ve dini tatil "
            "kaydırması bu ayardan bağımsızdır ve her zaman uygulanır."
        ),
    )
    last_loan_date = models.DateField(
        "yıl sonu son ödünç tarihi",
        null=True,
        blank=True,
        help_text="Bu tarihten sonra yeni ödünç verilmez (yıl sonu toplama akışı, §8.3).",
    )
    last_loan_date_graduating = models.DateField(
        "son sınıflar için son ödünç tarihi",
        null=True,
        blank=True,
        help_text="İsteğe bağlı; mezun olacak sınıflar için daha erken bir tarih (§8.3).",
    )
    idle_minutes = models.PositiveSmallIntegerField(
        "yönetici kipi boşta süresi (dakika)",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Bu süre boyunca işlem yapılmazsa görevli kipine inilir (§4.4).",
    )
    admin_max_minutes = models.PositiveSmallIntegerField(
        "yönetici kipi mutlak süresi (dakika)",
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(480)],
        help_text="İşlem yapılsa da bu süre sonunda görevli kipine inilir (§4.4).",
    )
    popular_min_members = models.PositiveSmallIntegerField(
        "çok okunanlar için en az üye sayısı",
        default=5,
        validators=[MinValueValidator(2), MaxValueValidator(50)],
        help_text=(
            "Bir eser vitrine ancak en az bu kadar FARKLI üye ödünç aldıysa girer; "
            "sayı hiçbir yerde gösterilmez (profil yasağı, tasarım §3)."
        ),
    )
    retention_years_after_termination = models.PositiveSmallIntegerField(
        "üyelik sonlandıktan sonra saklama (yıl)",
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Sonlanmış üyeliğin ödünç ve dosya bağları bu süre sonunda koparılır (§6.4).",
    )
    retention_years_returned_loans = models.PositiveSmallIntegerField(
        "iade edilmiş ödünçlerde saklama (yıl)",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Aktif üyenin iade edilmiş ödünçlerinde ders yılı sonundan sonraki süre (§6.4).",
    )
    retention_years_closed_cases = models.PositiveSmallIntegerField(
        "kapanmış kayıp/hasar dosyalarında saklama (yıl)",
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    retention_years_closed_deliveries = models.PositiveSmallIntegerField(
        "kapanmış teslimlerde saklama (yıl)",
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    # -- ISBN ile künye getirme (U13, tasarım §8.5) ------------------------
    # Üçü de VARSAYILAN KAPALI değildir: ana bayrak kapalıdır, kaynak seçimleri
    # yalnız o bayrak açıkken anlam taşır. Ana bayrak kapalıyken kod hiç ağa
    # çıkmaz (koruma testi `tests/test_kunye_servisi.py`).
    metadata_lookup_enabled = models.BooleanField(
        "ISBN ile künye getirme açık",
        default=False,
        help_text=(
            "Varsayılan kapalıdır (§8.5-1). Açıkken yalnız kullanıcının başlattığı "
            "tek sorgu dışarı çıkar; dışarı yalnız ISBN gider."
        ),
    )
    metadata_lookup_ministry = models.BooleanField(
        "Bakanlık kataloğundan sorulur",
        default=True,
        help_text="Kültür ve Turizm Bakanlığı halk kütüphaneleri kataloğu (ilk sırada sorulur).",
    )
    metadata_lookup_openlibrary = models.BooleanField(
        "Open Library'den sorulur",
        default=True,
        help_text="Bakanlık kataloğunda bulunamayan numaralar için yedek kaynak.",
    )

    class Meta:
        verbose_name = "kütüphane politikası"
        verbose_name_plural = "kütüphane politikası"
        constraints = [
            # AT-4: seçenek açıksa müdürlük kararının tarihi ve sayısı dolu olmalı.
            models.CheckConstraint(
                name="ck_librarypolicy_staff_loans_decision",
                condition=(
                    models.Q(staff_loans_enabled=False)
                    | (
                        models.Q(staff_loans_decision_date__isnull=False)
                        & ~models.Q(staff_loans_decision_no="")
                    )
                ),
            ),
        ]

    def __str__(self) -> str:
        return "Kütüphane politikası"

    @classmethod
    def load(cls) -> LibraryPolicy:
        """Tek satırı döndürür; yoksa KAYDEDİLMEMİŞ varsayılan örnek (okuma yazmaz)."""
        return cls.objects.filter(pk=cls.SINGLETON_PK).first() or cls(pk=cls.SINGLETON_PK)


class Section(BaseModel):
    """Bölüm — kontrollü liste (Md. 4/1-a, 6/1; sözlük: "bölüm", "raf" değil).

    Yönetmeliğin "alan"ı ortaöğretimde konu bölümüdür. Serbest metin yerine
    kontrollü liste seçildi (tasarım §6.2): Excel'den gelen "Edebiyat", "edebiyat
    ", "EDEBİYAT " yazımları tek bölüme eşlensin, raf etiketleri ve Ağ Kataloğu
    dizinleri tutarlı kalsın.

    `dewey_from`/`dewey_to` bölümün DOS aralığıdır (ör. 800-899) ve yalnız
    bilgilendirme amaçlıdır: kullanıcı aralığı aşan bir eseri de bu bölüme
    koyabilir, program engellemez.
    """

    name = models.CharField("ad", max_length=80)
    name_sort_key = models.CharField(
        "ad sıralama anahtarı", max_length=80, blank=True, default="", editable=False
    )
    dewey_from = models.CharField("DOS aralığı başı", max_length=20, blank=True, default="")
    dewey_to = models.CharField("DOS aralığı sonu", max_length=20, blank=True, default="")
    description = models.CharField("kısa tarif", max_length=255, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(
        "sıra", default=0, help_text="Küçük sayı önce gelir; eşitlikte ad sırası uygulanır."
    )

    class Meta:
        verbose_name = "bölüm"
        verbose_name_plural = "bölümler"
        # TR sıralama anahtarı (BINARY `order_by` Türkçe harfleri bozar — T7).
        ordering = ["sort_order", "name_sort_key", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_section_name_alive",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Ad sıralama anahtarını türetip kaydeder (bkz. `Work.save` gerekçesi)."""
        self.name_sort_key = keys.tr_collation_key(self.name)
        kwargs = _with_derived_update_fields(kwargs, ("name_sort_key",))
        super().save(*args, **kwargs)


def _with_derived_update_fields(kwargs: dict[str, Any], derived: tuple[str, ...]) -> dict[str, Any]:
    """`update_fields` verilmişse türetilmiş alanları da listeye ekler.

    Aksi hâlde `save(update_fields=["title"])` yeni başlığı yazar, sıralama ve
    arama anahtarları eski başlıkta kalırdı — liste ve arama sessizce bozulurdu
    (KS'nin kör indeks dersi, `Student.save`).
    """
    update_fields = kwargs.get("update_fields")
    if update_fields is None:
        return kwargs
    kwargs["update_fields"] = list(dict.fromkeys([*update_fields, *derived]))
    return kwargs


class Work(BaseModel):
    """Eser — bibliyografik künye (Md. 8/1-a, 11/1). Kişisel veri taşımaz.

    Üç katalog ekseni (kaynak adı / yazar adı / konu — Md. 11/1) hem aramada hem
    sıralamada Türkçe anahtar alanlarıyla çalışır (T7, D2):

    - `search_key`: ad + yazar + konu + ISBN, katlanmış. Arama ham alanlarda
      DEĞİL burada yapılır ve sorgu da aynı katlamadan geçer.
    - `sort_key`, `author_sort_key`, `subject_sort_key`: Türk alfabesi sırası.
      `Meta.ordering` `title` yerine `sort_key`'tedir.

    `isbn` kullanıcının yazdığı numaradır; `isbn13` normalleştirilmiş 13 haneli
    karşılığıdır (ISBN-10 çevrilir). İkisi de TEKİL DEĞİLDİR: aynı ISBN'li
    birden çok eser kaydı olabilir, nüsha kimliği barkoddur. Sağlama hatası
    kaydı engellemez, `isbn_warning` ile uyarı verir.

    Dijital kaynaklarda (e-kitap, e-veri tabanı) nüsha AÇILAMAZ — servis kuralı
    (`services.catalog`), TMY'nin fiziksel taşınır düzeni dışıdır.
    """

    #: `save()`'in her yazımda yeniden türettiği alanlar.
    DERIVED_FIELDS: tuple[str, ...] = (
        "isbn13",
        "search_key",
        "sort_key",
        "author_sort_key",
        "subject_sort_key",
    )

    title = models.CharField("kaynak adı", max_length=500)
    authors = models.CharField("yazar(lar)", max_length=500, blank=True, default="")
    translator = models.CharField("çevirmen", max_length=255, blank=True, default="")
    edition = models.CharField("baskı", max_length=60, blank=True, default="")
    publisher = models.CharField("yayınevi", max_length=255, blank=True, default="")
    publish_year = models.PositiveSmallIntegerField(
        "yayın yılı",
        null=True,
        blank=True,
        validators=[MinValueValidator(PUBLISH_YEAR_MIN), MaxValueValidator(PUBLISH_YEAR_MAX)],
    )
    isbn = models.CharField(
        "ISBN",
        max_length=20,
        blank=True,
        default="",
        help_text="Kullanıcının yazdığı biçim; tireli olabilir. Tekil değildir.",
    )
    isbn13 = models.CharField(
        "ISBN (13 hane)",
        max_length=13,
        blank=True,
        default="",
        editable=False,
        help_text="Normalleştirilmiş biçim; ISBN-10 çevrilir. `save()` türetir.",
    )
    subjects = models.CharField(
        "konu(lar)",
        max_length=500,
        blank=True,
        default="",
        help_text="Birden çok konu virgülle ayrılır (Md. 11/1 konu ekseni).",
    )
    classification_code = models.CharField(
        "sınıflama kodu",
        max_length=60,
        blank=True,
        default="",
        help_text="Dewey Onlu Sınıflama (DOS) kodu; serbest metin.",
    )
    classification_source = models.CharField(
        "sınıflama kaynağı",
        max_length=10,
        choices=ClassificationSource.choices,
        default=ClassificationSource.MANUAL,
    )
    call_number = models.CharField(
        "yer numarası",
        max_length=80,
        blank=True,
        default="",
        help_text=(
            "Sırt etiketi içeriği (sınıflama kodu + yazar soyadının ilk üç harfi, "
            "ör. 813.54 STE). Boş bırakılırsa üretilir; elle değiştirilebilir."
        ),
    )
    resource_type = models.CharField(
        "kaynak türü",
        max_length=12,
        choices=ResourceType.choices,
        default=ResourceType.BOOK,
    )
    language = models.CharField("dil", max_length=40, blank=True, default="")
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="works",
        verbose_name="bölüm",
        null=True,
        blank=True,
    )
    search_key = models.TextField("arama anahtarı", blank=True, default="", editable=False)
    sort_key = models.CharField(
        "ad sıralama anahtarı", max_length=500, blank=True, default="", editable=False
    )
    author_sort_key = models.CharField(
        "yazar sıralama anahtarı", max_length=500, blank=True, default="", editable=False
    )
    subject_sort_key = models.CharField(
        "konu sıralama anahtarı", max_length=500, blank=True, default="", editable=False
    )

    class Meta:
        verbose_name = "eser"
        verbose_name_plural = "eserler"
        # `title` DEĞİL: SQLite'ta BINARY sıralama Ç/Ğ/İ/Ö/Ş/Ü'yü Z'den sonraya atar.
        ordering = ["sort_key", "pk"]
        indexes = [
            models.Index(fields=["sort_key"], name="kutuphane_work_sort_idx"),
            models.Index(fields=["author_sort_key"], name="kutuphane_work_author_idx"),
            models.Index(fields=["subject_sort_key"], name="kutuphane_work_subject_idx"),
            models.Index(fields=["isbn13"], name="kutuphane_work_isbn13_idx"),
            models.Index(fields=["resource_type"], name="kutuphane_work_restype_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        """ISBN'i normalleştirip Türkçe anahtarları türetir, sonra kaydeder.

        Anahtarlar HER yazımda yeniden hesaplanır (ucuzdur ve tek satırlık
        tutarsızlık arama sonucunu sessizce bozar). `QuerySet.update()`,
        `bulk_update` ve `bulk_create` `save()`'i ATLAR: toplu yazan yollar
        (F3 içe aktarımı) anahtarları elle doldurmak zorundadır — koruma testi
        `tests/test_tr_anahtarlari.py` bunu sabitler.
        """
        self.isbn13 = isbn_module.to_isbn13(self.isbn)
        self.search_key = keys.work_search_key(
            title=self.title,
            authors=self.authors,
            subjects=self.subjects,
            isbn=self.isbn,
            isbn13=self.isbn13,
        )
        self.sort_key = keys.tr_collation_key(self.title)
        self.author_sort_key = keys.tr_collation_key(keys.author_sort_name(self.authors))
        self.subject_sort_key = keys.tr_collation_key(keys.first_subject(self.subjects))
        kwargs = _with_derived_update_fields(kwargs, self.DERIVED_FIELDS)
        super().save(*args, **kwargs)

    @property
    def is_digital(self) -> bool:
        """Dijital kaynak mı? (e-kitap / e-veri tabanı — nüsha açılamaz)"""
        return self.resource_type in DIGITAL_RESOURCE_TYPES

    @property
    def isbn_warning(self) -> str:
        """ISBN uyarısı (sağlama/uzunluk); numara sağlamsa ya da boşsa ''."""
        return isbn_module.isbn_warning(self.isbn)


class Copy(BaseModel):
    """Nüsha — fiziksel taşınır (TMY Kütüphane Defteri, Md. 9/1-ç). Kişisel veri yok.

    **Tanımlayıcı tablosu** (SU-11, UY-22, sözlük §1):

    | Alan | Ad | Nedir |
    |---|---|---|
    | `barcode` | barkod | Programın ürettiği 10 hane (`2026000123`), basılı `2026-000123` |
    | `accession_no` | kayıt no | Aynı sayının tamsayı hâli; TMY defterinin sıra numarası |
    | `external_asset_ref` | TKYS kodu | Taşınır kaydındaki karşılık (doğrulanmaz). **Hiçbir akışta zorunlu değildir** ve arayüzde geri plandadır: saha cevabına göre (S8, 23.09.2026) okullar TKYS'de nüsha bazında kayıt fiilen tutmuyor |
    | `old_register_no` | eski kayıt no | Kitaptaki eski damga ya da defter no (isteğe bağlı) |

    İkisi de TEK sayaçtan (`CopyCounter`) doğar ve **asla yeniden kullanılmaz**:
    teklik kısıtı kısmi değil DÜZ `unique`'tir, yani yumuşak silinmiş nüshanın
    numarası da ölçüye girer. Bir kitabın hangi numarayla deftere girdiği
    sorusunun iki cevabı olamaz.

    Durum geçişleri YALNIZ servislerdedir. `is_loanable` ödünç verilebilirliğin
    TEK türetimidir (Md. 14/1-a, 16/1).
    """

    work = models.ForeignKey(
        Work, on_delete=models.PROTECT, related_name="copies", verbose_name="eser"
    )
    acquisition = models.ForeignKey(
        "Acquisition",
        on_delete=models.PROTECT,
        related_name="copies",
        verbose_name="edinim",
        help_text="Her nüsha bir edinimden gelir (sayım fazlası dahil).",
    )
    accession_no = models.PositiveBigIntegerField(
        "kayıt no", unique=True, help_text="Barkodun sayı hâli; sayaçtan üretilir."
    )
    barcode = models.CharField(
        "barkod",
        max_length=10,
        unique=True,  # unique zaten indeks üretir — ayrı db_index gereksiz
        help_text="10 hane: yıl + altı hane sıra. ASLA yeniden kullanılmaz.",
    )
    external_asset_ref = models.CharField(
        "TKYS kodu",
        max_length=64,
        blank=True,
        default="",
        help_text="Taşınır kaydındaki karşılık; program doğrulamaz.",
    )
    old_register_no = models.CharField(
        "eski kayıt no",
        max_length=40,
        blank=True,
        default="",
        help_text="Kitaptaki eski damga ya da eski defterin sıra numarası (isteğe bağlı).",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="copies",
        verbose_name="bölüm",
        null=True,
        blank=True,
        help_text="Nüshanın durduğu bölüm (kontrollü liste; serbest raf metni değil).",
    )
    is_reference = models.BooleanField(
        "danışma kaynağı", default=False, help_text="Md. 14/1-a, 16/1-a — ödünç verilmez."
    )
    is_out_of_print = models.BooleanField(
        "piyasada mevcudu yok", default=False, help_text="Md. 16/1-b — ödünç verilmez."
    )
    is_bound_periodical = models.BooleanField(
        "ciltli süreli yayın",
        default=False,
        help_text="TMY Md. 15/4: süreli yayın yalnız ciltletildiğinde kayda girer.",
    )
    is_rare_or_manuscript = models.BooleanField(
        "el yazması / nadir eser",
        default=False,
        help_text="Md. 12/2 — nüshanın kalıcı özelliği; ayıklamada engeldir (F8).",
    )
    status = models.CharField(
        "durum", max_length=20, choices=CopyStatus.choices, default=CopyStatus.AVAILABLE
    )
    label_printed_at = models.DateTimeField(
        "etiket basım tarihi",
        null=True,
        blank=True,
        help_text=(
            "BARKOD etiketinin basım işareti. Boş = barkod etiketi kuyruğunda (F4). "
            "Onaylı işarettir (D10): PDF üretmek yazmaz, kullanıcı onaylar; geri alınabilir."
        ),
    )
    label_verified_at = models.DateTimeField(
        "etiket doğrulama tarihi",
        null=True,
        blank=True,
        help_text="Yapıştırdıktan sonra barkod etiketini okutunca yazılır (F4).",
    )
    # F4-Q: sırt etiketinin AYRI işareti. Tek işaret yöntem B'de (önce etiket,
    # §8.1) yetmiyordu: kitaba önceden basılmış BARKOD etiketi yapıştırılır ve
    # hızlı kayıtta bağlanır, ama sırt etiketi (yer numarası) künye tamamlanınca
    # basılır. Tek işaretle ya bu nüshalar sırt kuyruğuna hiç girmez ya da
    # "ikisi birden" basımında kitaba İKİNCİ bir barkod etiketi basılırdı.
    spine_label_printed_at = models.DateTimeField(
        "sırt etiketi basım tarihi",
        null=True,
        blank=True,
        help_text="Boş = sırt etiketi kuyruğunda (F4). Onaylı işaret; geri alınabilir.",
    )

    class Meta:
        verbose_name = "nüsha"
        verbose_name_plural = "nüshalar"
        ordering = ["accession_no"]
        indexes = [
            models.Index(fields=["status"], name="kutuphane_copy_status_idx"),
            models.Index(fields=["work", "status"], name="kutuphane_copy_workst_idx"),
            models.Index(fields=["old_register_no"], name="kutuphane_copy_oldreg_idx"),
        ]

    def __str__(self) -> str:
        return self.barcode

    @property
    def is_labelable(self) -> bool:
        """Etiket basılabilir mi (F4): nüsha ve eseri canlı, nüsha elden çıkmamış.

        Yumuşak silme ileri FK'da süzülmez (CLAUDE.md §3): eserin canlılığı elle
        denetlenir. Basım partisinin PDF'inde böyle olmayan nüshanın hücresi boş
        kalır, onayda işaretine dokunulmaz, yeniden basımda partiye girmez. DB
        tarafı süzgeç `selectors_kuyruk.labelable_copies`'tir.
        """
        return (
            self.deleted_at is None
            and self.work.deleted_at is None
            and self.status not in TERMINAL_COPY_STATUSES
        )

    @property
    def is_loanable(self) -> bool:
        """Ödünç verilebilirliğin TEK türetimi (Md. 14/1-a, 16/1; §9-3).

        Ödünç verilmeyenler: danışma kaynağı, piyasada mevcudu olmayan eser,
        süreli yayın ve DİJİTAL kaynak (e-kitap, e-veri tabanı — rafta durmaz,
        elden ele geçmez). Bunlara ek olarak nüsha rafta olmalıdır.

        Dijital koşulu savunma derinliğidir: dijital eserin nüshası zaten
        açılamaz (`services.catalog.ensure_copy_allowed`) ve var olan nüshalı
        bir eser dijitale ÇEVRİLEMEZ (`ensure_work_type_change`). İki kapı da
        aşılırsa nüsha ödünç verilebilir GÖRÜNMEMELİDİR.

        `resource_type` eserdedir; toplu listelerde `select_related("work")`
        kullanın. DB tarafı süzgeç `selectors.LOANABLE_Q`'dur ve bu özellikle
        aynı sonucu vermek ZORUNDADIR (koruma testi ikisini tüm kombinasyonlarda
        karşılaştırır).
        """
        return (
            not self.is_reference
            and not self.is_out_of_print
            and not self.work.is_digital
            and self.work.resource_type != ResourceType.PERIODICAL
            and self.status == CopyStatus.AVAILABLE
        )

    @property
    def not_loanable_reason(self) -> str:
        """Ödünç verilemiyorsa kullanıcıya gösterilecek gerekçe; verilebiliyorsa ''.

        Metinler docs/sozluk.md'ye uyar ve KİŞİSEL VERİ TAŞIMAZ (masa ekranında
        yan yana duran öğrenciye de görünür).
        """
        if self.is_reference:
            return "Ödünç verilmez — kütüphanede okunur."
        if self.is_out_of_print:
            return "Piyasada mevcudu yok — ödünç verilmez."
        if self.work.is_digital:
            return "Dijital kaynak — ödünç verilmez."
        if self.work.resource_type == ResourceType.PERIODICAL:
            return "Süreli yayın — ödünç verilmez."
        if self.status != CopyStatus.AVAILABLE:
            return f"{self.get_status_display()} — ödünç verilemez."
        return ""


class CopyCounter(models.Model):
    """Yıl bazlı nüsha numarası sayacı (barkod ve kayıt no aynı sayaçtan).

    Yıl `timezone.localdate()` ile alınır (D6 — OYS `timezone.now().year`
    kullanıyordu; yıl dönümünde UTC ile yerel gün ayrışır ve 1 Ocak gece yarısı
    Türkiye'de açılan bir nüsha bir önceki yılın numarasını alırdı).

    Sayaç GERİ GİTMEZ: nüsha silinse de numara yeniden dağıtılmaz. Yarış için
    `select_for_update` SQLite'ta etkisizdir (CLAUDE.md §4); güvence tek yazar +
    `transaction_mode=IMMEDIATE` ve `Copy.barcode`'un düz `unique` kısıtıdır.
    """

    year = models.PositiveSmallIntegerField("yıl", primary_key=True)
    last_no = models.PositiveIntegerField("son numara", default=0)

    class Meta:
        verbose_name = "nüsha sayacı"
        verbose_name_plural = "nüsha sayaçları"
        ordering = ["-year"]

    def __str__(self) -> str:
        return f"{self.year}: {self.last_no}"


class CommissionDecision(BaseModel):
    """Seçim ve Ayıklama Komisyonu kararı (Md. 4/1-ı, 10/1).

    Komisyon başkanı ilçe millî eğitim müdürlüğü şube müdürüdür; program
    kullanıcısı değildir — başkan ve katılımcılar serbest metindir ve KİŞİ ADI
    taşıdıkları için ŞİFRELİDİR (§6.3). Başkanın unvanı şifrelenmez: kişiyi tek
    başına tanımlamaz ve listelerde süzgeç olarak kullanılır.

    Program seçim kriterlerini (Md. 10/1 a-f) DENETLEMEZ; komisyonun kararını
    kayıt altına alır (Md. 10/1-2).
    """

    decision_type = models.CharField(
        "karar türü", max_length=16, choices=CommissionDecisionType.choices
    )
    decision_date = models.DateField("karar tarihi")
    decision_no = models.CharField("karar sayısı", max_length=40, blank=True, default="")
    chair_name = EncryptedCharField("başkan adı", max_length=120)
    chair_title = models.CharField("başkan unvanı", max_length=120, blank=True, default="")
    participants_text = EncryptedTextField(
        "katılımcılar",
        blank=True,
        default="",
        help_text="Komisyon üyeleri; satır başına bir kişi.",
    )
    notes = models.TextField("notlar", blank=True, default="")

    class Meta:
        verbose_name = "komisyon kararı"
        verbose_name_plural = "komisyon kararları"
        ordering = ["-decision_date", "-pk"]
        indexes = [
            models.Index(fields=["decision_type", "decision_date"], name="kutuphane_cd_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_decision_type_display()} — {self.decision_date}"


class Acquisition(BaseModel):
    """Edinim partisi (Md. 10/5 + TMY dayanaklı iki kayıt-içi giriş).

    Her nüsha bir edinimden gelir (`Copy.acquisition` zorunlu). Bağışta
    (DONATION) komisyon kararı ZORUNLUDUR (Md. 10/3 — DB kısıtı); kararın
    TÜRÜNÜN denetimi servistedir (D7).

    `source_note` bağışçının ya da satıcının adını taşıyabilir → ŞİFRELİDİR
    (§6.3). Anahtar bellekte değilken boş olmayan değer YAZILMAZ (fail-closed):
    edinim yaratan uç program kilitliyken 409 `parola_gerekli` alır.
    """

    method = models.CharField("edinim yolu", max_length=16, choices=AcquisitionMethod.choices)
    date = models.DateField("edinim tarihi")
    source_note = EncryptedCharField(
        "kaynak notu",
        max_length=255,
        blank=True,
        default="",
        help_text="Bağışçı, satıcı ya da parti açıklaması (serbest metin).",
    )
    unit_price = models.DecimalField(
        "birim fiyat",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_UNIT_PRICE)],
    )
    commission_decision = models.ForeignKey(
        CommissionDecision,
        on_delete=models.PROTECT,
        related_name="acquisitions",
        verbose_name="komisyon kararı",
        null=True,
        blank=True,
        help_text="Bağışta zorunludur (Md. 10/3).",
    )
    notes = models.TextField("notlar", blank=True, default="")

    class Meta:
        verbose_name = "edinim"
        verbose_name_plural = "edinimler"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(fields=["method", "date"], name="kutuphane_acq_method_idx"),
        ]
        constraints = [
            # Md. 10/3: bağış Seçim ve Ayıklama Komisyonu değerlendirmesinden geçer.
            models.CheckConstraint(
                name="ck_acquisition_donation_needs_commission",
                condition=~models.Q(method=AcquisitionMethod.DONATION)
                | models.Q(commission_decision__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_method_display()} — {self.date}"


class DonationIntakeStatus(models.TextChoices):
    """Bağış ön kaydının yaşam döngüsü (SU-23)."""

    PENDING = "PENDING", "Karar bekliyor"
    DECIDED = "DECIDED", "Karar işlendi"
    CANCELLED = "CANCELLED", "İptal edildi"


class DonationItemDecision(models.TextChoices):
    """Bağış kaleminin komisyon kararındaki sonucu."""

    PENDING = "PENDING", "Karar bekliyor"
    ACCEPTED = "ACCEPTED", "Kabul edildi"
    REJECTED = "REJECTED", "Reddedildi"


class DonationIntake(BaseModel):
    """Bağış ön kaydı — komisyon kararına kadar NÜSHA AÇILMAZ (SU-23, Md. 10/3).

    Okula bağış gelir gelmez kataloğa girmek iki yanlış doğurur: komisyon
    reddederse kayıttan düşme işlemi gerekir, kabul ederse edinim tarihi
    kararın tarihiyle tutmaz. Bu yüzden gelen kitaplar önce burada listelenir;
    karar girilince kabul edilen kalemler TEK İŞLEMDE kataloglanır, reddedilenler
    gerekçesiyle işaretlenir ve kayıtta kalır (okul bağışçıya ne olduğunu
    söyleyebilsin).

    `donor_name` kişi adıdır → ŞİFRELİDİR (§6.3).
    """

    donor_name = EncryptedCharField(
        "bağışçı",
        max_length=160,
        blank=True,
        default="",
        help_text="Bağışçının adı (isteğe bağlı).",
    )
    received_date = models.DateField("geliş tarihi")
    status = models.CharField(
        "durum",
        max_length=12,
        choices=DonationIntakeStatus.choices,
        default=DonationIntakeStatus.PENDING,
    )
    commission_decision = models.ForeignKey(
        CommissionDecision,
        on_delete=models.PROTECT,
        related_name="donation_intakes",
        verbose_name="komisyon kararı",
        null=True,
        blank=True,
    )
    acquisition = models.ForeignKey(
        Acquisition,
        on_delete=models.PROTECT,
        related_name="donation_intakes",
        verbose_name="edinim",
        null=True,
        blank=True,
        help_text="Kataloglama sırasında açılan edinim partisi.",
    )
    decided_at = models.DateTimeField("karar işlenme zamanı", null=True, blank=True)
    notes = models.TextField("notlar", blank=True, default="")

    class Meta:
        verbose_name = "bağış ön kaydı"
        verbose_name_plural = "bağış ön kayıtları"
        ordering = ["-received_date", "-pk"]
        indexes = [
            models.Index(fields=["status", "received_date"], name="kutuphane_di_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Bağış ön kaydı #{self.pk} — {self.received_date}"


class DonationIntakeItem(BaseModel):
    """Bağış ön kaydının bir kalemi — henüz eser ve nüsha DEĞİL.

    Künye alanları eserin alanlarıyla aynı adları taşır: kabul edilen kalem
    kataloglanırken alanlar birebir `Work`'e geçer. `work` alanı kataloglamadan
    SONRA dolar ve izlenebilirliği sağlar (bağışçıya "hangi kitap kayda girdi"
    sorusunun cevabı).
    """

    intake = models.ForeignKey(
        DonationIntake,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="bağış ön kaydı",
    )
    title = models.CharField("kaynak adı", max_length=500)
    authors = models.CharField("yazar(lar)", max_length=500, blank=True, default="")
    publisher = models.CharField("yayınevi", max_length=255, blank=True, default="")
    publish_year = models.PositiveSmallIntegerField(
        "yayın yılı",
        null=True,
        blank=True,
        validators=[MinValueValidator(PUBLISH_YEAR_MIN), MaxValueValidator(PUBLISH_YEAR_MAX)],
    )
    isbn = models.CharField("ISBN", max_length=20, blank=True, default="")
    copies = models.PositiveSmallIntegerField(
        "nüsha sayısı",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_COPIES_PER_ROW)],
    )
    decision = models.CharField(
        "karar",
        max_length=10,
        choices=DonationItemDecision.choices,
        default=DonationItemDecision.PENDING,
    )
    reject_reason = models.CharField("ret gerekçesi", max_length=255, blank=True, default="")
    work = models.ForeignKey(
        Work,
        on_delete=models.SET_NULL,
        related_name="donation_items",
        verbose_name="eser",
        null=True,
        blank=True,
    )
    notes = models.TextField("notlar", blank=True, default="")

    class Meta:
        verbose_name = "bağış kalemi"
        verbose_name_plural = "bağış kalemleri"
        ordering = ["intake", "pk"]
        constraints = [
            # Reddedilen kalemin gerekçesi boş kalamaz (D12 sınıfı kusur).
            models.CheckConstraint(
                name="ck_donationitem_reject_reason",
                condition=~models.Q(decision=DonationItemDecision.REJECTED)
                | ~models.Q(reject_reason=""),
            ),
        ]

    def __str__(self) -> str:
        return self.title


class CatalogImportSource(models.TextChoices):
    """Toplu katalog aktarımının kaynağı (F3'te doldurulur)."""

    EXCEL = "EXCEL", "Excel dosyası"
    AI_JSON = "AI_JSON", "Yapay zekâ JSON dosyası"
    EXPORT = "EXPORT", "Dışa aktarım dosyası"


class CatalogImportStatus(models.TextChoices):
    """Toplu katalog aktarımının durumu.

    DRY_RUN: yalnız önizleme yapıldı (yazma yok) · APPLIED: onaylanıp uygulandı ·
    DISCARDED: önizleme reddedildi ya da terk edildi.
    """

    DRY_RUN = "DRY_RUN", "Önizleme"
    APPLIED = "APPLIED", "Uygulandı"
    DISCARDED = "DISCARDED", "İptal edildi"


class CatalogImportRun(BaseModel):
    """Toplu katalog aktarımı koşusu (izlenebilirlik; F3 doldurur, F2 modeli kurar).

    `payload_sha256` fikirdeşliğin (idempotency) anahtarıdır (D5): aynı dosyanın
    ikinci kez uygulanması engellenir. Program hiçbir yapay zekâ servisine
    BAĞLANMAZ (çevrimdışı çalışır): kullanıcı Excel'ini kendi aracına verir,
    dönen JSON'u programa yükler (§8.2).

    `report` kalıcıdır ve koşu satırının silme ucu yoktur; bu yüzden dosyadan
    gelen HAM METİN oraya yazılmaz (sütunu kaymış bir listede ham "Eser Adı"
    hücresi bir kişi adı olabilirdi). Yazılan: satır numaraları, kovalar ve
    sayılar — biçimin gerekçesi `ImportRowReport.to_run_dict`tedir.
    """

    uploaded_file_name = models.CharField(
        "yüklenen dosya adı", max_length=255, blank=True, default=""
    )
    source = models.CharField(
        "kaynak",
        max_length=10,
        choices=CatalogImportSource.choices,
        default=CatalogImportSource.EXCEL,
    )
    payload_sha256 = models.CharField(
        "içerik özeti (SHA256)", max_length=64, blank=True, default=""
    )
    schema_version = models.CharField("şema sürümü", max_length=10, default="v1")
    status = models.CharField(
        "durum",
        max_length=10,
        choices=CatalogImportStatus.choices,
        default=CatalogImportStatus.DRY_RUN,
    )
    acquisition = models.ForeignKey(
        Acquisition,
        on_delete=models.SET_NULL,
        related_name="import_runs",
        verbose_name="edinim",
        null=True,
        blank=True,
        help_text="Uygulama sırasında bağlanan edinim partisi.",
    )
    stats = models.JSONField("özet", default=dict, blank=True)
    report = models.JSONField("satır raporu", default=dict, blank=True)

    class Meta:
        verbose_name = "katalog aktarımı"
        verbose_name_plural = "katalog aktarımları"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["source", "payload_sha256"], name="kutuphane_cir_hash_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_display()} — {self.get_status_display()}"


class LabelKind(models.TextChoices):
    """Etiket tabakasının türü (§7.2). Basım F4'tedir; model F2'de kurulur."""

    SPINE = "SPINE", "Sırt etiketi"
    BARCODE = "BARCODE", "Barkod etiketi"
    CARD = "CARD", "Üye kartı"


class LabelSheetTemplate(BaseModel):
    """Etiket tabakası ön ayarı — mm hassasiyetli parametrik ızgara (§7.2).

    Ölçüler üründen teyit edilir; özel ölçü girişi serbesttir. Yazıcı sapması
    ŞABLONDA DEĞİL `LabelCalibration`'dadır: aynı tabaka iki yazıcıda farklı
    kayar, kalibrasyon şablon + yazıcı çiftiyle saklanır.
    """

    name = models.CharField("şablon adı", max_length=120)
    name_sort_key = models.CharField(
        "ad sıralama anahtarı", max_length=120, blank=True, default="", editable=False
    )
    kind = models.CharField(
        "tür", max_length=10, choices=LabelKind.choices, default=LabelKind.BARCODE
    )
    page_margin_top = models.DecimalField("üst kenar boşluğu (mm)", max_digits=6, decimal_places=2)
    page_margin_left = models.DecimalField("sol kenar boşluğu (mm)", max_digits=6, decimal_places=2)
    label_width = models.DecimalField("etiket genişliği (mm)", max_digits=6, decimal_places=2)
    label_height = models.DecimalField("etiket yüksekliği (mm)", max_digits=6, decimal_places=2)
    rows = models.PositiveSmallIntegerField("satır sayısı", validators=[MinValueValidator(1)])
    cols = models.PositiveSmallIntegerField("sütun sayısı", validators=[MinValueValidator(1)])
    gutter_x = models.DecimalField("yatay boşluk (mm)", max_digits=6, decimal_places=2, default=0)
    gutter_y = models.DecimalField("dikey boşluk (mm)", max_digits=6, decimal_places=2, default=0)
    corner_radius = models.DecimalField(
        "köşe yarıçapı (mm)", max_digits=5, decimal_places=2, default=0
    )
    is_default = models.BooleanField("varsayılan şablon", default=False)

    class Meta:
        verbose_name = "etiket şablonu"
        verbose_name_plural = "etiket şablonları"
        # `name` DEĞİL: SQLite'ta BINARY sıralama Ç/Ğ/İ/Ö/Ş/Ü'yü Z'den sonraya
        # atar ve F4'ün şablon listesinde "Çıkartma" en sona düşerdi (T7).
        ordering = ["kind", "name_sort_key", "pk"]
        constraints = [
            # Tür başına tek CANLI varsayılan şablon.
            models.UniqueConstraint(
                fields=["kind", "is_default"],
                condition=models.Q(is_default=True, deleted_at__isnull=True),
                name="uq_labelsheet_default_per_kind",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Ad sıralama anahtarını türetip kaydeder (bkz. `Section.save` gerekçesi)."""
        self.name_sort_key = keys.tr_collation_key(self.name)
        kwargs = _with_derived_update_fields(kwargs, ("name_sort_key",))
        super().save(*args, **kwargs)

    @property
    def labels_per_sheet(self) -> int:
        return int(self.rows) * int(self.cols)


class LabelCalibration(BaseModel):
    """Yazıcı sapması düzeltmesi — ŞABLON + YAZICI çifti başına (§7.2, F4).

    Aynı etiket tabakası okulun iki yazıcısında farklı kayar; kalibrasyonu
    şablona yazmak, ikinci yazıcıda basan kullanıcıyı her seferinde yeniden
    ayar yapmaya zorlardı.
    """

    template = models.ForeignKey(
        LabelSheetTemplate,
        on_delete=models.CASCADE,
        related_name="calibrations",
        verbose_name="etiket şablonu",
    )
    printer_name = models.CharField("yazıcı adı", max_length=160)
    printer_name_sort_key = models.CharField(
        "yazıcı adı sıralama anahtarı", max_length=160, blank=True, default="", editable=False
    )
    offset_x = models.DecimalField(
        "kalibrasyon X (mm)",
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Pozitif değer sağa kaydırır.",
    )
    offset_y = models.DecimalField(
        "kalibrasyon Y (mm)",
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Pozitif değer aşağı kaydırır.",
    )

    class Meta:
        verbose_name = "etiket kalibrasyonu"
        verbose_name_plural = "etiket kalibrasyonları"
        # `printer_name` DEĞİL — TR sıralama anahtarı (T7; bkz. şablon).
        ordering = ["template", "printer_name_sort_key", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "printer_name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_labelcalibration_template_printer_alive",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Yazıcı adı sıralama anahtarını türetip kaydeder (T7)."""
        self.printer_name_sort_key = keys.tr_collation_key(self.printer_name)
        kwargs = _with_derived_update_fields(kwargs, ("printer_name_sort_key",))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.template_id} — {self.printer_name}"


# ---------------------------------------------------------------------------
# F4-Q — basım kuyruğu, basım kaydı (D10) ve boş barkod aralığı (yöntem B)
# ---------------------------------------------------------------------------
#: Bir basım partisine ya da bir boş barkod aralığına giren en çok etiket.
#: 20 tabaka × 65 (varsayılan 38,1 × 21,2 mm tabaka). Sınır bir basım İŞİNİN
#: sınırıdır, kuyruğun değil: 10.000 kitaplık bir okul kuyruğu süzgeçle
#: (bölüm, parti, tarih) böler. Tabaka parası ve yazıcı sıkışması da zaten
#: tabaka tabaka basmayı gerektirir; tek istekte on binlerce etiketlik PDF
#: dizmek pencereyi dakikalarca bekletirdi.
MAX_LABELS_PER_JOB = 1300
#: Aynı sınırın kullanıcı metnindeki yazımı (binlik ayracı nokta: "1.300").
MAX_LABELS_PER_JOB_TEXT = f"{MAX_LABELS_PER_JOB:,}".replace(",", ".")


class LabelPrintKind(models.TextChoices):
    """Basım partisinin içeriği (§7.2).

    Şablonun türünden (`LabelKind`) AYRIDIR: şablon tabakanın ölçüsünü, bu
    seçenek hücreye ne basılacağını söyler. "İkisi birden" TEK şablonla basılır
    — sırt ve barkod etiketi **aynı sıra ve hücre düzeninde** çıkar (§7.2), yani
    iki tabakanın N. hücresi aynı kitabındır ve yapıştırma kolaylaşır. Önceden
    basılmış boş barkod etiketi (yöntem B) bir parti türü DEĞİLDİR: nüshası
    henüz yoktur, basımı `BarcodeReservation` üzerinden yürür.
    """

    SPINE = "SPINE", "Sırt etiketi"
    BARCODE = "BARCODE", "Barkod etiketi"
    BOTH = "BOTH", "Sırt ve barkod etiketi"


#: Barkod etiketi içeren parti türleri (basımı `label_printed_at`'e yazılır).
BARCODE_PRINT_KINDS: tuple[str, ...] = (LabelPrintKind.BARCODE, LabelPrintKind.BOTH)
#: Sırt etiketi içeren parti türleri (basımı `spine_label_printed_at`'e yazılır).
SPINE_PRINT_KINDS: tuple[str, ...] = (LabelPrintKind.SPINE, LabelPrintKind.BOTH)


class LabelOrder(models.TextChoices):
    """Basım sırası — seçilebilir (D20, §7.2).

    OYS kuyruğu yalnız barkod sırasında veriyordu (D20); raf raf yapıştırmada
    işe yarayan sıra ise yer numarası sırasıdır (varsayılan). "İçe aktarma
    sırası" nüshaların KAYIT sırasıdır: bir Excel aktarımında satırlar sırayla
    işlenir ve her nüsha bir öncekinden sonra açılır, yani aktarımın içinde bu
    sıra dosyanın satır sırasıdır (hızlı kayıtta da kitapların masadan geçiş
    sırası). Barkod sırası bunlardan ayrılabilir: yöntem B'de önceden ayrılmış
    numara, kendisinden sonra açılan nüshadan daha küçük olabilir.
    """

    CALL_NUMBER = "CALL_NUMBER", "Yer numarası"
    IMPORT_ROW = "IMPORT_ROW", "İçe aktarma sırası"
    BARCODE = "BARCODE", "Barkod"


class LabelPrintBatchStatus(models.TextChoices):
    """Basım partisinin durumu (türetilir; alan değil — bkz. `LabelPrintBatch.status`)."""

    PENDING = "PENDING", "Basım onayı bekliyor"
    CONFIRMED = "CONFIRMED", "Basıldı"
    REVERTED = "REVERTED", "Basım işareti geri alındı"
    DISCARDED = "DISCARDED", "Vazgeçildi"


class LabelPrintBatch(BaseModel):
    """Etiket basım kaydı — PDF üretmek "basıldı" DEMEK DEĞİLDİR (D10, §7.2).

    OYS "basıldı" işaretini PDF üretilince koyuyordu (D10): yazıcı sıkışsa,
    kâğıt ters takılsa ya da kullanıcı PDF'i hiç yazdırmasa bile nüshalar
    kuyruktan düşüyor ve bir daha görünmüyordu. Burada parti önce "basım onayı
    bekliyor" hâlinde açılır; nüshaların işareti ancak kullanıcı "Basıldı
    olarak işaretle" deyince yazılır ve **geri alınabilir**. Geri alınan ya da
    vazgeçilen parti SİLİNMEZ, iz olarak kalır; aynı nüshalar yeni bir partiyle
    (`reprint_of`) yeniden basılabilir. Partinin PDF'i her hâlinde yeniden
    üretilebilir — işaretlere dokunmaz. Partideki bir nüsha sonradan silinir ya
    da elden çıkarsa (`Copy.is_labelable`) PDF'te hücresi boş kalır (sonraki
    etiketler kaymaz), onay onun işaretine dokunmaz, yeniden basım onu almaz.

    Durum alanı yoktur; üç zaman damgasından türetilir (`status`). Böylece
    "onaylandı ama zamanı boş" gibi tutarsız bir satır yazılamaz — kısıtlar da
    aynı şeyi DB'de söyler.

    Kişisel veri taşımaz.
    """

    kind = models.CharField("içerik", max_length=8, choices=LabelPrintKind.choices)
    template = models.ForeignKey(
        LabelSheetTemplate,
        on_delete=models.PROTECT,
        related_name="print_batches",
        verbose_name="etiket şablonu",
    )
    calibration = models.ForeignKey(
        LabelCalibration,
        on_delete=models.SET_NULL,
        related_name="print_batches",
        verbose_name="kalibrasyon",
        null=True,
        blank=True,
        help_text="Boş: kaymasız (kalibrasyonsuz) basım.",
    )
    spine_template = models.ForeignKey(
        LabelSheetTemplate,
        on_delete=models.PROTECT,
        related_name="spine_print_batches",
        verbose_name="sırt etiketi şablonu",
        null=True,
        blank=True,
        help_text=(
            "Yalnız “sırt ve barkod etiketi” basımında, sırt etiketleri AYRI bir tabakaya "
            "basılacaksa. Boş: sırt da ana şablona basılır. İki tabaka aynı sıra ve hücre "
            "planını paylaşır (§7.2)."
        ),
    )
    spine_calibration = models.ForeignKey(
        LabelCalibration,
        on_delete=models.SET_NULL,
        related_name="spine_print_batches",
        verbose_name="sırt etiketi kalibrasyonu",
        null=True,
        blank=True,
    )
    include_qr = models.BooleanField(
        "QR kod",
        default=False,
        help_text="Varsayılan kapalı (§7.2). İçerik rakamdır, adres değil; geniş şablon ister.",
    )
    order = models.CharField(
        "basım sırası", max_length=12, choices=LabelOrder.choices, default=LabelOrder.CALL_NUMBER
    )
    start_cell = models.PositiveSmallIntegerField(
        "başlangıç hücresi",
        default=1,
        validators=[MinValueValidator(1)],
        help_text=(
            "1'den başlar, satır satır sayılır (soldan sağa, yukarıdan aşağı). Kısmen "
            "kullanılmış tabakanın ilk boş hücresi."
        ),
    )
    copy_count = models.PositiveIntegerField("nüsha sayısı", default=0)
    confirmed_at = models.DateTimeField("basım onayı", null=True, blank=True)
    reverted_at = models.DateTimeField("geri alma", null=True, blank=True)
    discarded_at = models.DateTimeField("vazgeçme", null=True, blank=True)
    reprint_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reprints",
        verbose_name="yeniden basılan parti",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "etiket basım partisi"
        verbose_name_plural = "etiket basım partileri"
        ordering = ["-created_at", "-pk"]
        constraints = [
            # Geri alma yalnız onaylanmış partide olur.
            models.CheckConstraint(
                name="ck_labelbatch_revert_needs_confirm",
                condition=models.Q(reverted_at__isnull=True) | models.Q(confirmed_at__isnull=False),
            ),
            # Onaylanan partiden vazgeçilmez (geri alınır); vazgeçilen onaylanmaz.
            models.CheckConstraint(
                name="ck_labelbatch_confirm_xor_discard",
                condition=models.Q(confirmed_at__isnull=True) | models.Q(discarded_at__isnull=True),
            ),
            # Ayrı sırt tabakası yalnız "sırt ve barkod etiketi" basımında anlamlıdır.
            models.CheckConstraint(
                name="ck_labelbatch_spine_template_only_both",
                condition=models.Q(kind=LabelPrintKind.BOTH)
                | (
                    models.Q(spine_template__isnull=True) & models.Q(spine_calibration__isnull=True)
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"Basım partisi #{self.pk} — {self.get_kind_display()}"

    @property
    def status(self) -> str:
        """Türetilmiş durum (`LabelPrintBatchStatus`)."""
        if self.discarded_at is not None:
            return LabelPrintBatchStatus.DISCARDED
        if self.reverted_at is not None:
            return LabelPrintBatchStatus.REVERTED
        if self.confirmed_at is not None:
            return LabelPrintBatchStatus.CONFIRMED
        return LabelPrintBatchStatus.PENDING

    @property
    def prints_barcode(self) -> bool:
        return self.kind in BARCODE_PRINT_KINDS

    @property
    def prints_spine(self) -> bool:
        return self.kind in SPINE_PRINT_KINDS


class LabelPrintBatchItem(models.Model):
    """Partinin bir nüshası — basım SIRASIYLA (`position`) ve onay öncesi işaretleriyle.

    `previous_*` alanları onay anında nüshanın ESKİ işaretlerini saklar: geri
    alma işareti "boşa" değil, onaydan önceki değerine döndürür. Aynı nüshanın
    hasarlı etiketi yeniden basılıp parti geri alınırsa nüsha kuyruğa DÜŞMEZ,
    ilk basımın tarihine döner.

    `BaseModel` DEĞİLDİR (yumuşak silme yok): kalem partinin değişmez içeriğidir
    ve silme yolu yoktur.
    """

    batch = models.ForeignKey(
        LabelPrintBatch, on_delete=models.CASCADE, related_name="items", verbose_name="parti"
    )
    copy = models.ForeignKey(
        Copy, on_delete=models.PROTECT, related_name="label_batch_items", verbose_name="nüsha"
    )
    position = models.PositiveIntegerField("sıra")
    previous_printed_at = models.DateTimeField("önceki barkod basım işareti", null=True, blank=True)
    previous_verified_at = models.DateTimeField("önceki doğrulama işareti", null=True, blank=True)
    previous_spine_printed_at = models.DateTimeField(
        "önceki sırt basım işareti", null=True, blank=True
    )

    class Meta:
        verbose_name = "basım partisi kalemi"
        verbose_name_plural = "basım partisi kalemleri"
        ordering = ["batch", "position"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "position"], name="uq_labelbatchitem_pos"),
            models.UniqueConstraint(fields=["batch", "copy"], name="uq_labelbatchitem_copy"),
        ]

    def __str__(self) -> str:
        return f"{self.batch_id}/{self.position}"


class BarcodeReservation(BaseModel):
    """Boş barkod aralığı — önceden basılacak etiketlerin numaraları (yöntem B, §8.1).

    Okulun ASIL yolu (S8, 23.09.2026): hazır liste yoktur; numaralar önce
    ayrılır ve boş barkod etiketi olarak basılır, kitaplar raf başında
    etiketlenir, sonra hızlı kayıtta kitap elde künyesi girilirken yapıştırılan
    etiket okutulur ve nüsha O numarayla açılır.

    **Numaralar nüsha sayacından alınır** (`CopyCounter`, tek sayaç): ayrılmış
    bir numara hiçbir zaman başka bir nüshaya verilmez, çünkü sayaç onun
    ötesine geçmiştir. Kullanılmayan numara **iptal edilir**, sayaca geri
    DÖNMEZ (`ReservedBarcode.cancelled_at`); tanımlayıcı tablosunun "numara asla
    yeniden kullanılmaz" kuralı (§7.1) ayrılmış numarada da geçerlidir.

    Aralık tek işlemde ayrıldığı için numaralar ardışıktır ve aynı yıla aittir
    (`first_barcode`…`last_barcode` gösterim içindir; asıl kayıt numara
    satırlarıdır). `printed_at` onaylı basım işaretidir (D10 ile aynı kural):
    PDF üretmek yazmaz, kullanıcı onaylar, geri alınabilir.

    Kişisel veri taşımaz; `note` kullanıcının kısa açıklamasıdır ("Tarih rafı").
    """

    year = models.PositiveSmallIntegerField("yıl")
    first_barcode = models.CharField("ilk barkod", max_length=10)
    last_barcode = models.CharField("son barkod", max_length=10)
    count = models.PositiveIntegerField(
        "adet", validators=[MinValueValidator(1), MaxValueValidator(MAX_LABELS_PER_JOB)]
    )
    note = models.CharField("açıklama", max_length=120, blank=True, default="")
    printed_at = models.DateTimeField("basım onayı", null=True, blank=True)

    class Meta:
        verbose_name = "boş barkod aralığı"
        verbose_name_plural = "boş barkod aralıkları"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"{self.first_barcode}–{self.last_barcode}"


class ReservedBarcodeState(models.TextChoices):
    """Ayrılmış numaranın durumu (türetilir; bkz. `ReservedBarcode.state`)."""

    OPEN = "OPEN", "Bağlanmadı"
    BOUND = "BOUND", "Nüshaya bağlandı"
    CANCELLED = "CANCELLED", "İptal edildi"


class ReservedBarcode(models.Model):
    """Ayrılmış tek numara ve durumu: açık · bağlandı (nüshaya) · iptal edildi.

    `BaseModel` DEĞİLDİR (yumuşak silme yok — `CopyCounter` gibi): satır, bir
    numaranın dağıtıldığının KALICI kaydıdır. Yumuşak silme bile zararlı olurdu:
    canlı sorgudan düşen numara okutulduğunda "ayrılmış değil" denir ve iz
    kaybolur. Silme yolu yoktur; `copy` PROTECT'tir (nüsha katı silinemez).

    Değişmezler (DB kısıtı + servis):

    - Bağlı numara iptal edilemez; iptal edilen numara bağlanamaz.
    - Bir numara en çok bir nüshaya bağlanır (`OneToOne`), nüshanın `barcode` ve
      `accession_no` alanları bu satırdan gelir ve düz `unique`'tir.
    """

    reservation = models.ForeignKey(
        BarcodeReservation,
        on_delete=models.PROTECT,
        related_name="numbers",
        verbose_name="boş barkod aralığı",
    )
    barcode = models.CharField("barkod", max_length=10, unique=True)
    accession_no = models.PositiveBigIntegerField("kayıt no", unique=True)
    copy = models.OneToOneField(
        Copy,
        on_delete=models.PROTECT,
        related_name="reserved_barcode",
        verbose_name="bağlandığı nüsha",
        null=True,
        blank=True,
    )
    bound_at = models.DateTimeField("bağlanma", null=True, blank=True)
    cancelled_at = models.DateTimeField("iptal", null=True, blank=True)
    cancel_reason = models.CharField("iptal gerekçesi", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "ayrılmış barkod"
        verbose_name_plural = "ayrılmış barkodlar"
        ordering = ["accession_no"]
        constraints = [
            # Bağlı numara iptal edilemez; iptal edilen bağlanamaz.
            models.CheckConstraint(
                name="ck_reservedbarcode_bound_xor_cancelled",
                condition=models.Q(copy__isnull=True) | models.Q(cancelled_at__isnull=True),
            ),
            # Bağlanma zamanı ile bağlı nüsha birlikte dolar.
            models.CheckConstraint(
                name="ck_reservedbarcode_bound_at",
                condition=(models.Q(copy__isnull=True) & models.Q(bound_at__isnull=True))
                | (models.Q(copy__isnull=False) & models.Q(bound_at__isnull=False)),
            ),
        ]

    def __str__(self) -> str:
        return self.barcode

    @property
    def state(self) -> str:
        """Türetilmiş durum (`ReservedBarcodeState`)."""
        if self.copy_id is not None:
            return ReservedBarcodeState.BOUND
        if self.cancelled_at is not None:
            return ReservedBarcodeState.CANCELLED
        return ReservedBarcodeState.OPEN


class MetadataLookupSource(models.TextChoices):
    """Künye önerisinin geldiği dış kaynak (U13, §8.5). Sıra da budur."""

    MINISTRY = "MINISTRY", "Bakanlık kataloğu"
    OPENLIBRARY = "OPENLIBRARY", "Open Library"


class MetadataLookupCache(models.Model):
    """ISBN künye sorgusunun YEREL ÖNBELLEĞİ (§8.5-6): aynı ISBN ikinci kez sorulmaz.

    `BaseModel` DEĞİLDİR (yumuşak silme yok — `CopyCounter` gibi): önbellek
    satırının silinmesi bir kayıt kaybı değil, yalnız bir sorunun yeniden
    sorulmasıdır. Yumuşak silme burada zararlı olurdu: `isbn13` tekildir ve
    silinmiş satır canlı sorguda görünmediği için aynı ISBN ikinci kez
    yazılmak istendiğinde teklik kısıtı patlardı.

    Kişisel veri taşımaz: satır bir kitabın künyesidir, kimin sorduğu yazılmaz
    (Ağ Kataloğu'nun erişim günlüğü tutmama kuralıyla aynı çizgi — §5.5). Arama
    terimi de yoktur; anahtar normalleştirilmiş ISBN-13'tür.

    `payload` dışarıdan gelen ve **temizlenmiş** künye önerisidir
    (`kunye.temizlik`ten geçmiştir: NFC, denetim karakteri, uzunluk tavanı).
    Ham yanıt SAKLANMAZ — güvenilmeyen bir gövdeyi ikinci kez ayrıştırmanın
    değeri yoktur.

    Bulunamayan numara da yazılır (`source=""`): kaynakta olmayan bir ISBN'i her
    denemede yeniden sormak §8.5-2'nin "saniyede en çok bir istek" kuralını
    kullanıcıya fark ettirmeden tüketirdi. Kullanıcı "yeniden getir" derse
    önbellek atlanır (servis `force`), yani karar yine kullanıcınındır.
    """

    isbn13 = models.CharField("ISBN (13 hane)", max_length=13, unique=True)
    source = models.CharField(
        "kaynak",
        max_length=12,
        choices=MetadataLookupSource.choices,
        blank=True,
        default="",
        help_text="Boş: hiçbir kaynakta bulunamadı.",
    )
    record_count = models.PositiveIntegerField(
        "kaynaktaki kayıt sayısı",
        default=0,
        help_text="Mükerrer kayıt kuralı (§8.5): kullanıcıya kaç kayıt bulunduğu söylenir.",
    )
    fetched_on = models.DateField(
        "getirilme tarihi",
        help_text="Kaynak etiketinde gösterilir ('Bakanlık kataloğu, 23.09.2026').",
    )
    payload = models.JSONField("künye önerisi", default=dict, blank=True)
    updated_at = models.DateTimeField("güncellenme", auto_now=True)

    class Meta:
        verbose_name = "künye önbelleği"
        verbose_name_plural = "künye önbelleği"
        ordering = ["-fetched_on", "-pk"]

    def __str__(self) -> str:
        return f"{self.isbn13} — {self.get_source_display() or 'bulunamadı'}"


# ---------------------------------------------------------------------------
# F5 — Ağ Kataloğu: ayar satırı ve çok okunanlar tablosu (tasarım §5, §6.2)
# ---------------------------------------------------------------------------
#: Ağ Kataloğunun varsayılan portu (§5.2). Değişikliği yalnız yönetici kipinde
#: yapılır; güvenlik duvarı kuralı ve HKLM değeri UAC yardımcısıyla güncellenir.
KATALOG_VARSAYILAN_PORT = 8765
#: Kullanılabilir port aralığı. 1024 altı ayrıcalıklı portlardır ve Windows'ta
#: sistem hizmetleriyle çakışır; üst sınır TCP'nin kendisidir.
KATALOG_PORT_ALT = 1024
KATALOG_PORT_UST = 65535


class DinlemeKipi(models.TextChoices):
    """Ağ Kataloğunun dinlediği adres (§5.2).

    ALL: bütün ağ arayüzleri (0.0.0.0) — varsayılan; güvenlik duvarı kuralı
    `remoteip` ile kapsamı daraltır. SELECTED: yalnız seçili IP (ikinci ağ
    kartı ya da tahta VLAN'ına bağlı makine — §5.8); IP değişirse dinleyici
    yeni adreste yeniden açılır ve kullanıcı uyarılır (masaüstü kolu).
    """

    ALL = "ALL", "Bütün ağ bağlantılarında"
    SELECTED = "SELECTED", "Yalnız seçili IP adresinde"


class KatalogAyari(BaseModel):
    """Ağ Kataloğu ayarları — tek satır (singleton, pk=1). Kişisel veri taşımaz.

    **Port ve IP'nin tek kaynağı budur** (tasarım §2.3, §6.2): `KD_KATALOG_PORT`
    ve `KD_KATALOG_HOST` yalnız geliştirme ve test içindir. Katalog varsayılan
    olarak KAPALIDIR (§5.2): ilk açılışta Ağ Doktoru adım adım yönlendirir.

    Yazma yalnız yönetici kipindedir (`services.katalog_ayari`); uç görevli
    kipi izin listesinde DEĞİLDİR. `vitrin_acik` ve `konular_acik` Ağ Kataloğu
    tarafından `kd_katalog_okul` görünümünden okunur; öbür alanlar (port, IP,
    CIDR) görünüme HİÇ girmez — ağa açılan yüzey dinleme ayrıntısını bilmez.

    `tahta_cidrleri`: BTR'nin doğruladığı tahta ağı blokları (S1). Güvenlik
    duvarı kuralının `remoteip` güncellemesinde kullanılır (§5.7, UAC adımı);
    RFC1918'in tamamı bilerek kabul edilmez (GA-6).
    """

    SINGLETON_PK = 1

    acik = models.BooleanField(
        "Ağ Kataloğu açık",
        default=False,
        help_text="Varsayılan kapalıdır; ilk açılışta Ağ Doktoru yönlendirir (§5.2).",
    )
    port = models.PositiveIntegerField(
        "port",
        default=KATALOG_VARSAYILAN_PORT,
        validators=[MinValueValidator(KATALOG_PORT_ALT), MaxValueValidator(KATALOG_PORT_UST)],
        help_text="Değişikliği güvenlik duvarı kuralını da günceller (yönetici onayı ister).",
    )
    dinleme_kipi = models.CharField(
        "dinleme kipi", max_length=10, choices=DinlemeKipi.choices, default=DinlemeKipi.ALL
    )
    secili_ip = models.CharField(
        "seçili IP adresi",
        max_length=15,
        blank=True,
        default="",
        help_text="Yalnız 'yalnız seçili IP adresinde' kipinde kullanılır (IPv4).",
    )
    son_afis_ip = models.CharField(
        "son afişteki IP adresi",
        max_length=15,
        blank=True,
        default="",
        help_text="Katalog afişi basıldığında yazılır; IP değişince uyarı bununla karşılaştırılır.",
    )
    uyku_engelleme = models.BooleanField(
        "katalog açıkken boşta kalma uykusu engellenir",
        default=True,
        help_text="Kullanıcının başlattığı uyku ve kapak kapatma engellenmez (§4.5).",
    )
    vitrin_acik = models.BooleanField(
        "vitrin gösterilir",
        default=True,
        help_text="Ağ Kataloğu ana sayfasında yeni gelenler ve çok okunanlar.",
    )
    konular_acik = models.BooleanField(
        "konu dizini gösterilir",
        default=True,
        help_text="Ağ Kataloğunda DOS ana sınıfları ve konu dizini.",
    )
    tahta_cidrleri = models.JSONField(
        "tahta ağı blokları",
        default=list,
        blank=True,
        help_text="BTR'nin doğruladığı IPv4 blokları (ör. <tahta-ağı>); kural güncellemesinde kullanılır.",
    )

    class Meta:
        verbose_name = "Ağ Kataloğu ayarı"
        verbose_name_plural = "Ağ Kataloğu ayarları"
        constraints = [
            models.CheckConstraint(
                name="ck_katalogayari_dinleme_kipi",
                condition=models.Q(dinleme_kipi__in=DinlemeKipi.values),
            ),
            models.CheckConstraint(
                name="ck_katalogayari_port_araligi",
                condition=models.Q(port__gte=KATALOG_PORT_ALT)
                & models.Q(port__lte=KATALOG_PORT_UST),
            ),
            # Seçili IP kipinde adres boş kalamaz (servis Türkçe iletiyle de söyler).
            models.CheckConstraint(
                name="ck_katalogayari_secili_ip",
                condition=~models.Q(dinleme_kipi=DinlemeKipi.SELECTED) | ~models.Q(secili_ip=""),
            ),
        ]

    def __str__(self) -> str:
        return "Ağ Kataloğu ayarı"

    @classmethod
    def load(cls) -> KatalogAyari:
        """Tek satırı döndürür; yoksa KAYDEDİLMEMİŞ varsayılan örnek (okuma yazmaz)."""
        return cls.objects.filter(pk=cls.SINGLETON_PK).first() or cls(pk=cls.SINGLETON_PK)


class PopulerPencereTuru(models.TextChoices):
    """Çok okunanlar penceresi (§5.3): ağ vitrini dönem, E12 afişi ay penceresidir."""

    DONEM = "DONEM", "Dönem"
    AY = "AY", "Ay"


class KatalogPopuler(models.Model):
    """Çok okunanlar — (eser, pencere, sıra); tablo adı `kd_katalog_populer` (§5.3).

    KİŞİSİZDİR ve SAYI TAŞIMAZ: satır yalnız bir eserin o penceredeki SIRASIDIR.
    Kaç kez ödünç alındığı, kimin aldığı ya da kaç farklı üyenin aldığı burada
    yoktur (GA-10, KM-11, EK-23; profil yasağı CLAUDE.md §2-5). Eşik (pencere
    içinde en az k FARKLI üye — `LibraryPolicy.popular_min_members`) hesaplayan
    tarafın işidir; tabloya eşiği geçmemiş eser yazılmaz.

    Hesap Django tarafında, gün değişimi kapısında günde bir kez yapılır; F5'te
    yalnız tablo ve yazıcı iskeleti vardır (`services.populer`), gerçek hesap
    ödünç verisi gelince (F6/F10) bağlanır. Kapanmış pencere DONDURULUR
    (`dondu`): anonimleştirmeden sonra yeniden hesaplanmaz, çünkü kişi bağı
    koparılmış ödünçlerle aynı eşik artık ölçülemez.

    Ağ Kataloğu bu tabloyu doğrudan okur (adı `kd_katalog_` ile başlar;
    authorizer tablosu §5.3, 5. argüman boş satırı) ve silinmiş eseri
    `kd_katalog_eser` ile birleştirerek süzer. `BaseModel` DEĞİLDİR: satır
    hesabın çıktısıdır, yumuşak silinmez, pencere yeniden yazılırken değişir.
    """

    eser = models.ForeignKey(
        Work, on_delete=models.PROTECT, related_name="populer_siralari", verbose_name="eser"
    )
    pencere_turu = models.CharField(
        "pencere türü", max_length=5, choices=PopulerPencereTuru.choices
    )
    pencere = models.CharField(
        "pencere", max_length=20, help_text="Dönem için '2026-2027/1', ay için '2026-09'."
    )
    sira = models.PositiveSmallIntegerField("sıra", validators=[MinValueValidator(1)])
    hesaplanma = models.DateField("hesaplanma tarihi")
    dondu = models.BooleanField(
        "donduruldu", default=False, help_text="Kapanmış pencere yeniden hesaplanmaz."
    )

    class Meta:
        db_table = "kd_katalog_populer"
        verbose_name = "çok okunanlar sırası"
        verbose_name_plural = "çok okunanlar sıraları"
        ordering = ["pencere_turu", "-pencere", "sira"]
        constraints = [
            models.UniqueConstraint(
                fields=["pencere_turu", "pencere", "sira"], name="uq_katalogpopuler_sira"
            ),
            models.UniqueConstraint(
                fields=["pencere_turu", "pencere", "eser"], name="uq_katalogpopuler_eser"
            ),
            models.CheckConstraint(
                name="ck_katalogpopuler_pencere_turu",
                condition=models.Q(pencere_turu__in=PopulerPencereTuru.values),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pencere_turu} {self.pencere} #{self.sira}"
