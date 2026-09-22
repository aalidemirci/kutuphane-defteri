"""`okul` salt-okunur sorguları — view'lar ORM'e buradan erişir (katman disiplini).

Arama Türkçe-katlamalı yapılır: `normalize_header` (Türkçe→ASCII küçük harf) iki
tarafı da katlar. Ad-soyad VE okul no ŞİFRELİDİR (U9): ada dokunan her arama ve
kullanıcıya gösterilen her sıralama ZORUNLU olarak Python tarafındadır — yeni
ad sorgusu ORM filtresiyle YAZILMAZ; yerel ölçek (≤2000 kayıt) bunu ucuzlatır.
Okul no ile arama ve eşleştirme KÖR İNDEKSLE, tam eşleşmedir (T14): düz okul no
üzerinden DB sorgusu yazılmaz (şifreli sütunda her yazım farklı token'dır).
Sınıf, şube ve durum düz alanlardır; süzgeçleri DB tarafında kalır.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.okul import name_match, normalize
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import (
    ClassSection,
    Holiday,
    HolidayKind,
    ImportRun,
    Personnel,
    SchoolConfig,
    SchoolTerm,
    SchoolYear,
    Student,
    StudentStatus,
    student_number_blind_index,
)


def school_years() -> QuerySet[SchoolYear]:
    return SchoolYear.objects.all()


def active_school_year() -> SchoolYear | None:
    return SchoolYear.objects.filter(is_active=True).first()


def school_terms(*, school_year_id: int) -> QuerySet[SchoolTerm]:
    return SchoolTerm.objects.filter(school_year_id=school_year_id)


def get_school_term(term_id: int) -> SchoolTerm | None:
    """Tek dönem (canlı) — yoksa None. Diğer uygulamaların dönem okuma kanalı."""
    return SchoolTerm.objects.filter(pk=term_id).select_related("school_year").first()


def active_student_counts_by_level() -> dict[int, int]:
    """Seviye başına AKTİF öğrenci sayısı (pano/ön kontrol verisi; PII yok)."""
    counts: dict[int, int] = {}
    qs = (
        Student.objects.filter(status=StudentStatus.ACTIVE)
        .exclude(class_level=None)
        .values_list("class_level", flat=True)
    )
    for level in qs:
        counts[int(level)] = counts.get(int(level), 0) + 1
    return dict(sorted(counts.items()))


def last_student_import() -> ImportRun | None:
    """Son TAMAMLANMIŞ öğrenci içe aktarması ('liste ne kadar taze?')."""
    return ImportRun.objects.filter(source_type="STUDENTS", status="COMPLETED").first()


def grade_levels() -> list[dict[str, Any]]:
    """UI seçicileri için geçerli seviye listesi (1-12; hazırlık bayrağıyla 0)."""
    config = SchoolConfig.load()
    return [
        {"value": lvl, "label": "Hazırlık" if lvl == normalize.PREP_LEVEL else str(lvl)}
        for lvl in config.grade_levels
    ]


def grade_level_values() -> tuple[int, ...]:
    """Geçerli seviye değerleri (doğrulama için)."""
    return SchoolConfig.load().grade_levels


def _personnel_sort_key(person: Personnel) -> tuple[Any, ...]:
    """Ad-soyad Türk alfabesiyle ('C' < 'Ç', 'I' < 'İ'); eşitlikte kayıt sırası."""
    return (normalize.tr_sort_key(person.full_name), person.pk)


def personnel_sorted(
    rows: Iterable[Personnel] | None = None, *, only_active: bool = False
) -> list[Personnel]:
    """Ada göre Türk alfabesiyle sıralı personel (listeler, seçiciler).

    `rows` verilmezse canlı personelin tamamı (ya da yalnız aktifler) okunur.
    Ad şifreli olduğu için sıralama Python'dadır (DB sırası token sırasıdır).
    """
    if rows is None:
        rows = Personnel.objects.filter(is_active=True) if only_active else Personnel.objects.all()
    return sorted(rows, key=_personnel_sort_key)


def personnel_list(*, search: str = "", only_active: bool = False) -> list[Personnel]:
    """Personel listesi — ad araması ve sıralaması Python tarafında (şifreli ad).

    Unvan ve branş YOKTUR (V2-01); arama yalnız ad-soyad üzerindedir.
    """
    qs = Personnel.objects.all()
    if only_active:
        qs = qs.filter(is_active=True)
    rows: Iterable[Personnel] = qs
    if search.strip():
        needle = normalize_header(search)
        rows = [p for p in qs if needle in normalize_header(p.full_name)]
    return personnel_sorted(rows)


def personnel_all() -> QuerySet[Personnel]:
    """Canlı personel (ayrıntı uçlarının `get_queryset`'i — tek kayıt çözümü)."""
    return Personnel.objects.all()


def class_sections(*, school_year_id: int | None = None) -> QuerySet[ClassSection]:
    """Şube kataloğu; yıl verilmezse aktif yıl kullanılır."""
    qs = ClassSection.objects.select_related("school_year")
    if school_year_id is not None:
        return qs.filter(school_year_id=school_year_id)
    active = active_school_year()
    if active is None:
        return qs.none()
    return qs.filter(school_year=active)


def class_sections_sorted(*, school_year_id: int | None = None) -> list[ClassSection]:
    """Şube kataloğu, TÜRK ALFABESİ sırasıyla (listeleme/görüntü için).

    `ClassSection.Meta.ordering` DB sıralamasıdır ve SQLite karşılaştırması
    BINARY'dir (UTF-8 bayt = kod noktası sırası). Şube harfi artık ASCII'ye
    KATLANMADIĞI için orada 'Ç/Ğ/İ/Ö/Ş/Ü' harfleri 'Z'den sonraya düşer —
    10/I ile 10/İ listenin iki ucuna ayrılırdı. Sıralama bu yüzden Python'da,
    `normalize.tr_sort_key` ile yapılır (yerel ölçek: ~50 şube).
    """
    return sorted(
        class_sections(school_year_id=school_year_id),
        key=lambda s: (s.class_level, normalize.tr_sort_key(s.class_section)),
    )


def get_class_section(section_id: int) -> ClassSection | None:
    return ClassSection.objects.filter(pk=section_id).first()


#: Okul no'nun doğal sıralaması: '9' < '10' < '100' (metin sırasında '10' < '9').
_NUMBER_PARTS_RE = re.compile(r"(\d+)")


def _natural_number_key(student_number: str) -> tuple[Any, ...]:
    """Okul no'nun doğal sıra anahtarı; boş numara sona düşer."""
    sade = normalize.normalize_student_number(student_number)
    if not sade:
        return (1,)
    parcalar = _NUMBER_PARTS_RE.split(sade)
    return (
        0,
        tuple(
            (0, int(p), "") if p.isdigit() else (1, 0, normalize.tr_sort_key(p))
            for p in parcalar
            if p
        ),
    )


def student_sort_key(student: Student) -> tuple[Any, ...]:
    """Sınıf (sınıfsız sonda) → şube (Türk alfabesi) → okul no (doğal) → ad → kayıt sırası."""
    return (
        student.class_level is None,
        student.class_level if student.class_level is not None else 0,
        normalize.tr_sort_key(student.class_section),
        _natural_number_key(student.student_number),
        normalize.tr_sort_key(student.full_name),
        student.pk,
    )


def students_sorted(rows: Iterable[Student] | None = None) -> list[Student]:
    """Kullanıcıya gösterilen öğrenci sırası — Python'da (okul no şifrelidir, T14).

    SQLite'ın BINARY sırası şubede 'Ç/İ/Ş'yi 'Z'den sonraya atar, okul no'yu
    ise hiç sıralayamaz (token sırası). `rows` verilmezse canlı öğrencilerin
    tamamı okunur.
    """
    if rows is None:
        rows = Student.objects.all()
    return sorted(rows, key=student_sort_key)


def number_search_index(search: str) -> str:
    """Arama metni okul no'ya benziyorsa kör indeksi; değilse ''.

    Yalnız rakam (boşluk ve baştaki sıfırlar serbest) içeren arama okul no
    aramasıdır ve TAM eşleşmedir: '10' yazan '101'i bulmaz (kör indeks ön ek
    araması yapamaz; T14).
    """
    sade = normalize.normalize_student_number(search)
    if not sade or not sade.isascii() or not sade.isdigit():
        return ""
    return student_number_blind_index(sade)


def student_list(
    *,
    class_level: int | None = None,
    class_section: str = "",
    search: str = "",
    only_active: bool = False,
) -> list[Student]:
    """Öğrenci listesi (sıralı). `only_active` VARSAYILAN OLARAK KAPALIDIR.

    Sicil ekranı ayrılmış öğrenciyi de göstermek zorundadır (geçmiş kayıtların
    öğrencisi kaybolmasın); süzgeci yalnız YENİ kayıt bağlayan seçiciler
    (autocomplete) açar. Arama: ad-soyad Python'da TR katlamalı; okul no ise
    kör indeksle tam eşleşme (`number_search_index`).
    """
    qs = Student.objects.all()
    if only_active:
        qs = qs.filter(status=StudentStatus.ACTIVE)
    if class_level is not None:
        qs = qs.filter(class_level=class_level)
    if class_section.strip():
        # Kayıtlar import/serializer'da tr_upper ile büyütülür ('ş' → 'Ş');
        # filtre de AYNI katlamadan geçmeli, yoksa Türkçe harfli şube bulunamaz.
        qs = qs.filter(class_section=normalize.tr_upper(class_section.strip()))
    rows: Iterable[Student] = qs
    if search.strip():
        needle = normalize_header(search)
        number_index = number_search_index(search)
        rows = [
            s
            for s in qs
            if (number_index and s.student_number_index == number_index)
            or (needle and needle in normalize_header(s.full_name))
        ]
    return students_sorted(rows)


def get_student(student_id: int) -> Student | None:
    """Tek öğrenci (canlı) — yoksa None. Diğer uygulamaların okuma kanalı."""
    return Student.objects.filter(pk=student_id).first()


def find_student_by_number(student_number: str) -> Student | None:
    """Okul numarasıyla AKTİF canlı öğrenci arar — kör indeksle tam eşleşme (T14).

    Aynı numaranın farklı yazımları ('0123', ' 123 ') aynı indekse iner
    (`normalize.normalize_student_number`). Kart okutma (F6) ve e-Okul
    eşleştirmesi bu kanalı kullanır.
    """
    index = student_number_blind_index(student_number or "")
    if not index:
        return None
    return Student.objects.filter(student_number_index=index, status=StudentStatus.ACTIVE).first()


def find_left_student_by_number(student_number: str) -> Student | None:
    """Aynı okul no'lu AYRILMIŞ canlı öğrenci (yeniden aktifleşme adayı); en son ayrılan."""
    adaylar = left_students_by_number(student_number)
    return adaylar[0] if adaylar else None


def left_students_by_number(student_number: str) -> list[Student]:
    """Aynı okul no'lu bütün AYRILMIŞ canlı öğrenciler — en son ayrılan önce.

    Okul no ayrılan öğrenciden sonra başka öğrenciye verilebildiği için (model
    teklik kısıtı yalnız aktif kayıtlardadır) aynı indekste birden çok ayrılmış
    kayıt bulunabilir; hangisinin "dönen" öğrenci olduğuna çağıran ada bakarak
    karar verir (e-Okul aktarımı).
    """
    index = student_number_blind_index(student_number or "")
    if not index:
        return []
    return list(
        Student.objects.filter(student_number_index=index, status=StudentStatus.LEFT).order_by(
            "-left_at", "-pk"
        )
    )


def get_personnel(personnel_id: int) -> Personnel | None:
    """Tek personel (canlı) — yoksa None."""
    return Personnel.objects.filter(pk=personnel_id).first()


# ---------------------------------------------------------------------------
# Ayrılış havuzu (F1 eki 7 — kişisel veri: yalnız yönetim yüzeyi, yönetici kipi)
# ---------------------------------------------------------------------------
def _pool_students_qs() -> QuerySet[Student]:
    return Student.objects.filter(status=StudentStatus.ACTIVE, leave_candidate_since__isnull=False)


def _pool_personnel_qs() -> QuerySet[Personnel]:
    return Personnel.objects.filter(is_active=True, leave_candidate_since__isnull=False)


def leave_pool_students() -> list[Student]:
    """Havuzdaki öğrenciler — sınıf, şube (TR), okul no (doğal) sırasıyla (Python)."""
    return students_sorted(_pool_students_qs().select_related("leave_candidate_run"))


def leave_pool_personnel() -> list[Personnel]:
    """Havuzdaki öğretmen ve diğer personel — ada göre Türk alfabesiyle (Python)."""
    return personnel_sorted(_pool_personnel_qs().select_related("leave_candidate_run"))


def leave_pool_counts() -> dict[str, int]:
    """Havuzdaki kişi sayıları (Genel Bakış kartı; kişisel veri yok)."""
    return {
        "student_count": _pool_students_qs().count(),
        "personnel_count": _pool_personnel_qs().count(),
    }


def leave_pool_run(person: Student | Personnel) -> ImportRun | None:
    """Kişiyi havuza ekleyen aktarım (canlı değilse None — yumuşak silme ileri FK'da süzmez)."""
    run = person.leave_candidate_run
    if run is None or run.deleted_at is not None:
        return None
    return run


def leave_pool_similar_personnel(pool: Iterable[Personnel]) -> dict[int, list[Personnel]]:
    """Havuzdaki her personel için "olası aynı kişi" adayları (kimlik → adaylar, TR sıralı).

    Aday: aktif, havuzda OLMAYAN ve sicile kişinin havuza girdiği gün ya da sonra
    girmiş kayıt — tipik olarak aynı aktarımın yeni adla açtığı kayıt (soyadı
    değişimi). Eski kayıtlar aday sayılmaz: okulda aynı adı taşıyan başka
    öğretmenler her havuz kişisine "benzer" görünürdü. Kural aktarım
    önizlemesindekiyle aynıdır (`name_match.probably_same_person`).
    """
    kisiler = list(pool)
    if not kisiler:
        return {}
    adaylar = personnel_sorted(
        Personnel.objects.filter(is_active=True, leave_candidate_since__isnull=True)
    )
    sonuc: dict[int, list[Personnel]] = {}
    for kisi in kisiler:
        giris = kisi.leave_candidate_since
        if giris is None:
            continue
        sonuc[kisi.pk] = [
            aday
            for aday in adaylar
            if timezone.localdate(aday.created_at) >= giris
            and name_match.probably_same_person(
                first_a=kisi.first_name,
                full_a=kisi.full_name,
                first_b=aday.first_name,
                full_b=aday.full_name,
            )
        ]
    return sonuc


def get_school_year(school_year_id: int) -> SchoolYear | None:
    """Tek ders yılı (canlı) — yoksa None."""
    return SchoolYear.objects.filter(pk=school_year_id).first()


def students_all() -> QuerySet[Student]:
    return Student.objects.all()


def import_runs(*, source_type: str = "") -> QuerySet[ImportRun]:
    qs = ImportRun.objects.all()
    if source_type:
        qs = qs.filter(source_type=source_type)
    return qs


def student_count() -> int:
    """Canlı öğrenci sayısı (kurulum durumu ve yol haritası; kişisel veri yok)."""
    return Student.objects.count()


def personnel_count() -> int:
    """Canlı personel sayısı (kurulum durumu ve yol haritası; kişisel veri yok)."""
    return Personnel.objects.count()


def distinct_class_levels() -> list[int]:
    """Sicilde fiilen kayıtlı sınıf seviyeleri (artan, tekilleştirilmiş)."""
    values = Student.objects.exclude(class_level=None).values_list("class_level", flat=True)
    return sorted({int(v) for v in values})


# ---------------------------------------------------------------------------
# Kapalı günler (F1-D; kişisel veri yok)
# ---------------------------------------------------------------------------


def holidays(*, year: int | None = None) -> QuerySet[Holiday]:
    """Canlı kapalı günler; `year` verilirse o takvim yılıyla KESİŞENLER (yıl sınırını
    aşan aralık iki yılda da görünür)."""
    qs = Holiday.objects.all()
    if year is not None:
        qs = qs.filter(start_date__lte=date(year, 12, 31), end_date__gte=date(year, 1, 1))
    return qs


def holidays_sorted(*, year: int | None = None) -> list[Holiday]:
    """Kullanıcıya gösterilen liste: tarih sırası, eşitlikte TR ad sırası."""
    return sorted(
        holidays(year=year),
        key=lambda h: (h.start_date, h.end_date, normalize.tr_sort_key(h.name)),
    )


def get_holiday(holiday_id: int) -> Holiday | None:
    return Holiday.objects.filter(pk=holiday_id).first()


def school_break_count(*, start: date | str | None, end: date | str | None) -> int:
    """[start, end] aralığıyla kesişen "öğrenciye kapalı gün" KAYDI sayısı.

    Yol haritasının "öğrenciye kapalı günleri girin" maddesi aktif ders yılının
    aralığıyla sorar. Aralık yoksa (aktif yıl yok) 0.
    """
    if start is None or end is None:
        return 0
    baslangic = date.fromisoformat(start) if isinstance(start, str) else start
    bitis = date.fromisoformat(end) if isinstance(end, str) else end
    return Holiday.objects.filter(
        kind=HolidayKind.SCHOOL_BREAK, start_date__lte=bitis, end_date__gte=baslangic
    ).count()
