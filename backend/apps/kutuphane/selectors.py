"""`kutuphane` salt okuma sorguları — görünümler ORM'e buradan erişir.

İki kural bu dosyanın biçimini belirler:

1. **Türkçe arama ve sıralama anahtar alanlarıyla yapılır** (T7, D2). Ham
   `title__icontains` SQLite'ta "ŞİİR" ile "şiir"i eşleştirmez; ham `order_by`
   Ç/Ğ/İ/Ö/Ş/Ü'yü 'Z'den sonraya atar. Arama `Work.search_key` üzerinde, sorgu
   da AYNI katlamadan (`keys.search_terms`) geçerek yapılır; sıralama
   `*_sort_key` alanlarıyladır.
2. **Sayfalamaya uygun, kararlı sıra** (D9). Her sıralama `pk` ile biter:
   eşit anahtarlı satırlar sayfalar arasında yer değiştirmesin, 2. sayfada
   1. sayfanın kaydı yeniden görünmesin.

Yumuşak silme: varsayılan manager yalnız canlı kayıtları döndürür, ama
`Count("copies")` SQL JOIN'idir ve silinmiş nüshaları de sayar — sayaçlar bu
yüzden `filter=Q(copies__deleted_at__isnull=True)` taşır (CLAUDE.md §3).
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import keys
from apps.kutuphane.models import (
    DIGITAL_RESOURCE_TYPES,
    TERMINAL_COPY_STATUSES,
    Acquisition,
    CatalogImportRun,
    CommissionDecision,
    Copy,
    CopyStatus,
    DonationIntake,
    ResourceType,
    Section,
    Work,
)

#: `Copy.is_loanable` özelliğinin DB tarafı karşılığı (Md. 14/1-a, 16/1).
#: İKİSİ AYNI SONUCU VERMEK ZORUNDADIR — koruma testi bütün kombinasyonlarda
#: karşılaştırır (`tests/test_models.py::test_oduncluk_suzgeci_ozellikle_ayni_sonucu_verir`).
LOANABLE_Q = (
    Q(is_reference=False)
    & Q(is_out_of_print=False)
    & ~Q(work__resource_type__in=DIGITAL_RESOURCE_TYPES)
    & ~Q(work__resource_type=ResourceType.PERIODICAL)
    & Q(status=CopyStatus.AVAILABLE)
)

#: Eser listesinin sıralama eksenleri (Md. 11/1 üç ekseni + en yeni).
WORK_ORDERINGS: dict[str, tuple[str, ...]] = {
    "title": ("sort_key", "pk"),
    "author": ("author_sort_key", "sort_key", "pk"),
    "subject": ("subject_sort_key", "sort_key", "pk"),
    "newest": ("-created_at", "-pk"),
}
DEFAULT_WORK_ORDERING = "title"


def sections() -> QuerySet[Section]:
    """Bölümler — sıra alanına, sonra Türkçe ad sırasına göre."""
    return Section.objects.all()


def get_section(section_id: int) -> Section | None:
    return Section.objects.filter(pk=section_id).first()


def work_ordering(order: str | None) -> tuple[str, ...]:
    """Sıralama ekseninin alan listesi; tanınmayan eksende varsayılan (ad)."""
    return WORK_ORDERINGS.get(order or DEFAULT_WORK_ORDERING, WORK_ORDERINGS[DEFAULT_WORK_ORDERING])


def works(
    *,
    q: str = "",
    section_id: int | None = None,
    resource_type: str = "",
    order: str | None = None,
) -> QuerySet[Work]:
    """Eser listesi: Türkçe arama + süzgeçler + kararlı sıralama.

    Sorgudaki her sözcük AYRI aranır ve hepsi birden bulunur ("kürk madonna"
    → iki parça): kullanıcı sözcük sırasını hatırlamak zorunda kalmaz. ISBN
    yazımı ('978-605-…') rakamlarına indirilir.
    """
    # `select_related("section")`: liste serializer'ı her satırda bölüm adını
    # basar; olmadan sayfa başına 25 ek sorgu çıkar.
    qs = Work.objects.select_related("section")
    for term in keys.search_terms(q):
        qs = qs.filter(search_key__contains=term)
    if section_id is not None:
        qs = qs.filter(section_id=section_id)
    if resource_type:
        qs = qs.filter(resource_type=resource_type)
    return qs.order_by(*work_ordering(order))


def works_with_copy_counts(**filters: Any) -> QuerySet[Work]:
    """`works()` + nüsha sayaçları (elde bulunan ve rafta olan).

    İki süzgeç de zorunludur:

    - **Yumuşak silme.** `Count("copies")` SQL JOIN'idir ve silinmiş nüshaları
      de sayar; silinmiş nüsha listede "1 nüsha" göstermemelidir.
    - **Terminal durumlar.** Kayıttan düşülmüş ve devredilmiş nüsha artık elde
      DEĞİLDİR (`TERMINAL_COPY_STATUSES` — tek kaynak); katalog listesinin
      "Nüsha" sütunu elde bulunanı sayar. Kayıt defteri toplamı (kayıttan
      düşülenler dahil) TMY dökümünün işidir (F10), katalog listesinin değil.
    """
    canli = Q(copies__deleted_at__isnull=True) & ~Q(copies__status__in=TERMINAL_COPY_STATUSES)
    return works(**filters).annotate(
        copy_count=Count("copies", filter=canli, distinct=True),
        available_copy_count=Count(
            "copies",
            filter=canli & Q(copies__status=CopyStatus.AVAILABLE),
            distinct=True,
        ),
    )


def get_work(work_id: int) -> Work | None:
    return Work.objects.filter(pk=work_id).select_related("section").first()


def copies(
    *,
    work_id: int | None = None,
    section_id: int | None = None,
    acquisition_id: int | None = None,
    status: str = "",
    barcode: object = "",
    old_register_no: object = "",
    only_loanable: bool = False,
    only_unlabeled: bool = False,
    include_terminal: bool = True,
) -> QuerySet[Copy]:
    """Nüsha listesi (eser, bölüm, edinim, durum, barkod süzgeçleriyle); kayıt no sırasında.

    `acquisition_id` PARTİ süzgecidir: toplu aktarımdan sonra çıkan "bu partinin
    etiketlerini bas" kısayolunun (§8.1, F4) bağlanacağı yer burasıdır —
    `?acquisition=<id>&only_unlabeled=true` o partinin etiketlenmemiş
    nüshalarını verir. Aktarım raporu parti kimliğini `label_batch` alanında
    döndürür.

    `include_terminal=False` kayıttan düşülmüş ve devredilmiş nüshaları eler —
    etiket kuyruğu ve sayım gibi "elimizdekiler" listeleri bunu ister.

    `barcode` okutulan ya da yazılan koddur: `normalize_scan`'den geçer (basılı
    '2026-000123' yazımı ve okuyucunun eklediği boşluk aynı kayda gider) ve TAM
    eşleşme arar — barkodun bir parçası başka bir nüshaya ait olabilir, kısmi
    eşleşme masada yanlış kitabı getirirdi. `old_register_no` kitaptaki eski
    damgadır ve TEKİL DEĞİLDİR: birden çok nüsha dönebilir.
    """
    qs = Copy.objects.select_related("work", "section")
    if work_id is not None:
        qs = qs.filter(work_id=work_id)
    if section_id is not None:
        qs = qs.filter(section_id=section_id)
    if acquisition_id is not None:
        qs = qs.filter(acquisition_id=acquisition_id)
    if status:
        qs = qs.filter(status=status)
    if barcode:
        digits = barcode_module.normalize_scan(barcode)
        if len(digits) != barcode_module.BARCODE_LENGTH:
            return Copy.objects.none()
        qs = qs.filter(barcode=digits)
    if old_register_no:
        aranan = str(old_register_no).strip()
        if not aranan:
            return Copy.objects.none()
        qs = qs.filter(old_register_no=aranan)
    if not include_terminal:
        qs = qs.exclude(status__in=TERMINAL_COPY_STATUSES)
    if only_loanable:
        qs = qs.filter(LOANABLE_Q)
    if only_unlabeled:
        qs = qs.filter(label_printed_at__isnull=True)
    return qs.order_by("accession_no")


def get_copy(copy_id: int) -> Copy | None:
    return Copy.objects.filter(pk=copy_id).select_related("work", "section").first()


def find_copy_by_barcode(value: object) -> Copy | None:
    """Okutulan ya da yazılan barkoda göre nüsha (tam eşleşme).

    Girdi `barcode.normalize_scan` ile sadeleştirilir: okuyucunun eklediği
    boşluk ve kullanıcının yazdığı basılı biçim ('2026-000123') aynı kayda gider.
    """
    digits = barcode_module.normalize_scan(value)
    if len(digits) != barcode_module.BARCODE_LENGTH:
        return None
    return Copy.objects.filter(barcode=digits).select_related("work", "section").first()


def find_copies_by_old_register_no(value: object) -> QuerySet[Copy]:
    """Kitaptaki eski damgaya göre nüshalar (retrospektif aktarımda eşleştirme).

    Eski kayıt no TEKİL DEĞİLDİR: farklı defterlerden gelen numaralar
    çakışabilir, bu yüzden liste döner.
    """
    aranan = str(value or "").strip()
    if not aranan:
        return Copy.objects.none()
    return (
        Copy.objects.filter(old_register_no=aranan).select_related("work").order_by("accession_no")
    )


def acquisitions(*, method: str = "") -> QuerySet[Acquisition]:
    """Edinimler (en yeniden eskiye) + canlı nüsha sayacı.

    Sayaç listede gösterilir ve edinimin neden silinemediğini anlatır; JOIN
    silinmiş nüshaları de getireceği için süzgeçlidir (CLAUDE.md §3).
    """
    qs: QuerySet[Acquisition] = Acquisition.objects.select_related("commission_decision").annotate(
        copy_count=Count("copies", filter=Q(copies__deleted_at__isnull=True), distinct=True)
    )
    if method:
        qs = qs.filter(method=method)
    return qs


def get_acquisition(acquisition_id: int) -> Acquisition | None:
    return (
        Acquisition.objects.filter(pk=acquisition_id).select_related("commission_decision").first()
    )


def commission_decisions(*, decision_type: str = "") -> QuerySet[CommissionDecision]:
    """Komisyon kararları (en yeniden eskiye); türle daraltılabilir."""
    qs = CommissionDecision.objects.all()
    if decision_type:
        qs = qs.filter(decision_type=decision_type)
    return qs


def get_commission_decision(decision_id: int) -> CommissionDecision | None:
    return CommissionDecision.objects.filter(pk=decision_id).first()


def donation_intakes(*, status: str = "") -> QuerySet[DonationIntake]:
    """Bağış ön kayıtları (en yeniden eskiye)."""
    qs = DonationIntake.objects.select_related("commission_decision", "acquisition")
    if status:
        qs = qs.filter(status=status)
    return qs


def get_donation_intake(intake_id: int) -> DonationIntake | None:
    return (
        DonationIntake.objects.filter(pk=intake_id)
        .select_related("commission_decision", "acquisition")
        .first()
    )


# ---------------------------------------------------------------------------
# Künye getirme (U13, §8.5) — çevrimdışı yolun sorguları
# ---------------------------------------------------------------------------
def works_missing_metadata() -> QuerySet[Work]:
    """Künyesi eksik ve **ISBN'i olan** eserler (çevrimdışı ISBN listesi, §8.5).

    ISBN'siz eser listeye GİRMEZ: dosyanın eşleşme anahtarı ISBN'dir, numarasız
    satır internetli cihazda da doldurulamaz, geri aktarımda da eşleşmez.

    "Eksik" ölçütü kullanıcının gözüyle tanımlıdır: yayınevi, yayın yılı, konu
    ya da sınıflama kodundan biri boşsa künye tamamlanmamıştır. Eser adı zaten
    zorunludur, ölçüte girmez.

    Sıra Türkçedir (`Meta.ordering` = `sort_key`), sayfalamaya uygundur.
    """
    return Work.objects.exclude(isbn13="").filter(
        Q(publisher="") | Q(publish_year__isnull=True) | Q(subjects="") | Q(classification_code="")
    )


def works_by_isbn13(numaralar: Any) -> QuerySet[Work]:
    """Verilen ISBN-13 listesine sahip canlı eserler (çevrimdışı dosya eşleşmesi).

    Aynı ISBN'li birden çok eser olabilir (teklik kısıtı YOKTUR, §6.2): çağıran
    çokluğu görür ve kullanıcıya sorar, program sessizce ilkini seçmez.
    """
    return Work.objects.filter(isbn13__in=list(numaralar))


def collection_summary() -> dict[str, Any]:
    """Koleksiyon özeti — kişisiz sayaçlar (pano kartı ve Md. 7 eşiği için).

    Kişisel veri İÇERMEZ: yalnız eser ve nüsha sayıları, durum kırılımı.

    Üç sayaç üç ayrı soruya cevap verir ve KARIŞTIRILMAMALIDIR:

    - `copy_count` kayıt defterinin toplamıdır: kayıttan düşülmüş ve devredilmiş
      nüshalar da sayılır (TMY dökümünün baktığı sayı).
    - `in_stock_count` **elde bulunan** nüshadır (terminal durumlar düşülür).
      Md. 7/1'in "kitap sayısı 10.000'i aşan" eşiği budur: eşik eldeki dermeye
      bakar, defterden düşmüş kayıtlara değil.
    - `available_count` şu anda rafta olandır (ödünçteki, teslimdeki, onarımdaki
      nüsha elde vardır ama rafta değildir).
    """
    durum_sayilari = {
        satir["status"]: satir["adet"]
        for satir in Copy.objects.values("status").annotate(adet=Count("pk"))
    }
    toplam = Copy.objects.count()
    dusulen = sum(durum_sayilari.get(durum, 0) for durum in TERMINAL_COPY_STATUSES)
    return {
        "work_count": Work.objects.count(),
        "copy_count": toplam,
        "in_stock_count": toplam - dusulen,
        "available_count": durum_sayilari.get(CopyStatus.AVAILABLE, 0),
        "status_counts": {
            durum: durum_sayilari.get(durum, 0) for durum, _etiket in CopyStatus.choices
        },
        "section_count": Section.objects.count(),
    }


def catalog_import_runs(*, status: str = "", source: str = "") -> QuerySet[CatalogImportRun]:
    """Toplu katalog aktarımlarının geçmişi (en yeniden eskiye; F3, §8.1).

    Koşu satırı dosya adını, içerik özetini, sayıları ve sorunlu satırların
    NUMARALARINI tutar; dosyadaki ham eser adı ve ham hücre değeri gömen hata
    iletileri kütüğe YAZILMAZ (`ImportRowReport.to_run_dict`). Geçmiş iki soruya
    cevap verir — bu dosya daha önce uygulandı mı (fikirdeşlik kütüğü) ve hangi
    edinim partisi hangi aktarımdan doğdu (F4 etiket kısayolu).
    """
    qs = CatalogImportRun.objects.select_related("acquisition")
    if status:
        qs = qs.filter(status=status)
    if source:
        qs = qs.filter(source=source)
    return qs
