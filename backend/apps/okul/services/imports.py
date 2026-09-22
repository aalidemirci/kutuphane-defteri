"""Öğrenci/Personel toplu içe aktarma ve e-Okul MUTABAKATI — preview (dry-run) + commit.

KS'den alındı (KS bunu DD `services/imports.py` kalıbından uyarlamıştı), F1'de
mutabakatla genişletildi (tasarım §8.3, EK-20, EK-21):

- TCKN, veli ve cinsiyet zinciri TAMAMEN YOK. Öğrenci eşleştirme anahtarı OKUL
  NUMARASIDIR ve eşleştirme KÖR İNDEKSLE, tam eşleşmedir (okul no şifreli, T14):
  aynı numaranın farklı yazımı ('0123' ≡ '123') aynı kişiye iner.
- **Öğrenci mutabakatı (EK-21):** dosyada olmayan aktif öğrenciler "ayrılacak"
  kümesine girer — ama VARSAYILAN KAPSAM YALNIZ DOSYADA BULUNAN ŞUBELERDİR. Tek
  şubelik dosya diğer şubeleri ayrılmış saymaz; bütün okulla karşılaştırma yalnız
  `full_list` ("Bu dosya okulun tam listesidir") onayıyla yapılır. Şube değiştiren
  öğrenci "güncellendi"dir, ayrılmaz. Ayrılmış (canlı) kayıt aynı numarayla
  dönerse yeniden aktifleşir. Ayrılacaklar AYRILIŞ YOLUNDAN geçer
  (`persons.leave_student`: kancalar + gerekiyorsa katı silme).
- **Personel mutabakatı (EK-20):** eşleşme normalize ad-soyadla (Python; ad
  şifreli). Listede olmayan aktif personel `missing` olarak döner; yalnız
  kullanıcının seçtikleri (`mark_left_ids`) ayrılır, varsayılan hiçbiri. Ada göre
  eşleşmeyen yeni satırla listede olmayan kişi arasında "olası aynı kişi" çifti
  üretilir (soyadı değişimi); birleştirme ayrı uçtandır (`persons.merge_personnel`).
- **Kişisel veri ve kalıcı iz:** ayrılacakların ve listede olmayanların ADLARI
  yalnız API yanıtında (yönetim yüzeyi, yönetici kipi) döner; `ImportRun.report`
  (kalıcı) yalnız SAYILARI taşır (`to_run_dict`). Satır sorunlarına ad, okul no
  ve görev metni yazılmaz; günlüğe yalnız sayılar düşer.
- Excel (.xlsx ŞABLONU ve e-Okul'un .xls İHRACI) ile pano yapıştırması AYNI
  boru hattı: her girişten önce `rows` matrisi üretilir (`read_sheet` /
  `text_to_grid`), ardından `eokul.hazirla_*_matrisi` e-Okul'a özgü blok
  düzenini/dipnotlarını düzler, gerisi ortak.
- Idempotency UYARIDIR, ENGEL DEĞİL: aynı içerik (sha256) yeniden commit
  edilebilir — `already_imported=True` uyarısıyla MEVCUT COMPLETED `ImportRun`
  satırı güncellenir (koşullu unique bozulmaz). Aynı dosyanın ikinci uygulaması
  değişiklik üretmez.
- Önizleme deseni AYNEN: gerçek ingest (ayrılış yolu dahil) atomic blokta
  koşulur ve `set_rollback(True)` ile geri alınır — %100 sonuç paritesi;
  ardından kalıcı PREVIEWED izi yazılır. Ingest zincirine `transaction.on_commit`
  EKLENEMEZ; ayrılış kancaları yalnız veritabanına yazar.
- Boş/çözülemeyen hücre mevcut veriyi SİLMEZ (import silmez ilkesi).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Collection
from dataclasses import asdict, dataclass, field
from typing import Any
from zipfile import BadZipFile

from django.db import transaction
from django.utils import timezone
from openpyxl.utils.exceptions import InvalidFileException

from apps.okul import eokul, excel_ogrenci, excel_personel, normalize, selectors
from apps.okul.excel_ogrenci import ColumnMapping, ParsedRow, ParserError
from apps.okul.excel_personel import ParsedPersonnelRow, PersonnelColumnMapping
from apps.okul.models import (
    ClassSection,
    ImportRun,
    ImportSourceType,
    ImportStatus,
    MemberKind,
    Personnel,
    SchoolConfig,
    SchoolYear,
    Student,
    StudentStatus,
    student_number_blind_index,
)
from apps.okul.services import app_password, persons

logger = logging.getLogger("kutuphane_defteri.okul")

#: Önizlemede "üye türünü denetleyin" uyarısı (satır no ile; ad ve görev metni yok).
MEMBER_KIND_CHECK_MESSAGE = (
    "Üye türünü denetleyin: görev bilgisi tanınmadı. Yeni kayıt öğretmen olarak "
    "açılır; mevcut kaydın üye türü değişmez."
)
DUPLICATE_ROW_MESSAGE = "Bu okul numarası dosyada daha önce geçti; satır atlandı."

#: "Olası aynı kişi" için normalize ad-soyad düzenleme uzaklığı üst sınırı.
SIMILAR_NAME_MAX_DISTANCE = 2


@dataclass
class ImportIssue:
    """İçe aktarmada bir satır sorunu (atlama veya uyarı). Kişi adı taşımaz."""

    row_number: int
    field: str
    issue: str
    raw_value: str = ""


@dataclass
class ClassImpact:
    """Öğrenci aktarımının bir şubedeki etkisi (önizleme tablosu; kişisiz)."""

    class_label: str
    class_level: int | None
    class_section: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    leaving: int = 0


@dataclass
class LeavingStudent:
    """Ayrılacak öğrenci — AD İÇERİR: yalnız API yanıtında, `ImportRun.report`'a girmez."""

    id: int
    full_name: str
    student_number: str
    class_label: str


@dataclass
class StudentImportReport:
    """Öğrenci içe aktarma özeti (UI raporu; `to_run_dict` → ImportRun.report)."""

    file_hash: str
    file_name: str = ""
    total_rows: int = 0
    processed: int = 0
    created_students: int = 0
    updated_students: int = 0
    unchanged_students: int = 0
    #: Güncellenenlerin içinde: ayrılmışken aynı numarayla dönen öğrenciler.
    reactivated_students: int = 0
    leaving_students: int = 0
    full_list: bool = False
    already_imported: bool = False
    dry_run: bool = False
    classes: list[ClassImpact] = field(default_factory=list)
    leaving: list[LeavingStudent] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)
    skipped: list[ImportIssue] = field(default_factory=list)

    def add_warning(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.warnings.append(ImportIssue(row, field_name, issue, raw))

    def add_skip(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.skipped.append(ImportIssue(row, field_name, issue, raw))

    def to_dict(self) -> dict[str, Any]:
        """API yanıtı (yönetim yüzeyi): ayrılacakların adları dahil."""
        return asdict(self)

    def to_run_dict(self) -> dict[str, Any]:
        """Kalıcı `ImportRun.report`: yalnız sayılar — ad listesi ÇIKARILIR."""
        veri = asdict(self)
        veri.pop("leaving", None)
        return veri

    def summary_tr(self) -> str:
        return (
            f"İçe aktarma: {self.processed}/{self.total_rows} satır işlendi — "
            f"{self.created_students} yeni, {self.updated_students} güncellenen, "
            f"{self.unchanged_students} değişmeyen, {self.leaving_students} ayrılan öğrenci; "
            f"{len(self.warnings)} uyarı, {len(self.skipped)} atlanan."
        )


@dataclass
class MissingPersonnel:
    """Listede olmayan aktif personel — AD İÇERİR: yalnız API yanıtında."""

    id: int
    full_name: str


@dataclass
class SimilarPair:
    """ "Olası aynı kişi": ada göre eşleşmeyen yeni satır ↔ listede olmayan kayıt.

    AD İÇERİR: yalnız API yanıtında. `new_id` yalnız uygulamada dolar (önizlemede
    yeni kayıt geri alındığı için None'dır); birleştirme `personnel/<existing_id>/merge/`
    ucuna `{into_id: new_id}` ile yapılır.
    """

    row_number: int
    row_name: str
    existing_id: int
    existing_name: str
    new_id: int | None = None


@dataclass
class PersonnelImportReport:
    """Personel içe aktarma özeti (UI raporu; `to_run_dict` → ImportRun.report)."""

    file_hash: str
    file_name: str = ""
    total_rows: int = 0
    processed: int = 0
    created_personnel: int = 0
    updated_personnel: int = 0
    unchanged_personnel: int = 0
    #: Güncellenenlerin içinde: ayrılmışken listede yeniden görülen personel.
    reactivated_personnel: int = 0
    missing_count: int = 0
    left_personnel: int = 0
    similar_pair_count: int = 0
    already_imported: bool = False
    dry_run: bool = False
    missing: list[MissingPersonnel] = field(default_factory=list)
    similar_pairs: list[SimilarPair] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)
    skipped: list[ImportIssue] = field(default_factory=list)

    def add_warning(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.warnings.append(ImportIssue(row, field_name, issue, raw))

    def add_skip(self, row: int, field_name: str, issue: str, raw: str = "") -> None:
        self.skipped.append(ImportIssue(row, field_name, issue, raw))

    def to_dict(self) -> dict[str, Any]:
        """API yanıtı (yönetim yüzeyi): listede olmayanların ve çiftlerin adları dahil."""
        return asdict(self)

    def to_run_dict(self) -> dict[str, Any]:
        """Kalıcı `ImportRun.report`: yalnız sayılar — ad listeleri ÇIKARILIR."""
        veri = asdict(self)
        veri.pop("missing", None)
        veri.pop("similar_pairs", None)
        return veri

    def summary_tr(self) -> str:
        return (
            f"Personel içe aktarma: {self.processed}/{self.total_rows} satır — "
            f"{self.created_personnel} yeni, {self.updated_personnel} güncellenen, "
            f"{self.unchanged_personnel} değişmeyen, {self.left_personnel} ayrılan; "
            f"{len(self.warnings)} uyarı, {len(self.skipped)} atlanan."
        )


# ---------------------------------------------------------------------------
# Girdi normalize — dosya ve pano aynı matris biçimine iner
# ---------------------------------------------------------------------------
def file_hash(file_bytes: bytes) -> str:
    """Yüklenen dosyanın SHA256 özeti (aynı içerik tespiti için)."""
    return hashlib.sha256(file_bytes).hexdigest()


def text_hash(text: str) -> str:
    """Yapıştırılan metnin SHA256 özeti (satır sonları normalize edilir)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def text_to_grid(text: str) -> list[list[Any]]:
    """Pano metnini satır matrisine çevirir (tab ayraçlı — Excel kopyala/yapıştır)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [list(line.split("\t")) for line in normalized.split("\n")]


def _grid_from_file(file_bytes: bytes) -> list[list[Any]]:
    """Excel baytlarını matrise çevirir (.xlsx ve e-Okul'un .xls'i); okunamazsa ParserError."""
    try:
        return excel_ogrenci.read_sheet(file_bytes)
    except (BadZipFile, InvalidFileException) as exc:
        raise ParserError(
            "Dosya Excel olarak okunamadı. Desteklenen biçimler: e-Okul ihracı (.xls) ve "
            "uygulama şablonu (.xlsx). CSV ve PDF desteklenmez."
        ) from exc


def _valid_levels() -> tuple[int, ...]:
    """Okulun geçerli seviye kümesi (1-12 + hazırlık bayrağı; parser'a parametre geçilir)."""
    return SchoolConfig.load().grade_levels


#: e-Okul bloğu düzleştirildiğinde sütun başlığı 10. satırdan sonra kalabilir
#: (kurum başlığı + öğretmen satırları); tarama penceresi o yüzden genişletilir.
_EOKUL_SCAN_LIMIT = 30


def _parse_student_grid(grid: list[list[Any]]) -> tuple[ColumnMapping, list[ParsedRow]]:
    """Matristen (mapping, satırlar); kritik sütun eksikse ParserError.

    Ayrıştırmadan önce e-Okul önişleyicisi çalışır: şube blokları düzleştirilir
    (sınıf/şube sentetik sütuna yazılır) ve rapor dipnotları boşaltılır.
    """
    grid, notes = eokul.hazirla_ogrenci_matrisi(grid)
    limit = _EOKUL_SCAN_LIMIT if notes else 10
    mapping = excel_ogrenci.detect_columns(grid, scan_limit=limit)
    if not mapping.is_usable:
        missing = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {missing}.")
    mapping.warnings = [*notes, *mapping.warnings]
    return mapping, excel_ogrenci.parse_rows(grid, mapping, valid_levels=_valid_levels())


def _parse_personnel_grid(
    grid: list[list[Any]],
) -> tuple[PersonnelColumnMapping, list[ParsedPersonnelRow]]:
    grid, notes = eokul.hazirla_personel_matrisi(grid)
    mapping = excel_personel.detect_columns(grid)
    if not mapping.is_usable:
        missing = ", ".join(mapping.missing_critical)
        raise ParserError(f"Zorunlu sütun(lar) bulunamadı: {missing}.")
    mapping.warnings = [*notes, *mapping.warnings]
    return mapping, excel_personel.parse_rows(grid, mapping)


# ---------------------------------------------------------------------------
# ImportRun yaşam döngüsü (idempotency uyarısı + koşullu unique koruması)
# ---------------------------------------------------------------------------
def _open_run(*, source_type: str, source_hash: str, file_name: str) -> tuple[ImportRun, bool]:
    """Koşu kaydını açar → (run, zaten_tamamlanmış_mı)."""
    existing: ImportRun | None = ImportRun.objects.filter(
        source_type=source_type, file_hash=source_hash, status=ImportStatus.COMPLETED
    ).first()
    if existing is not None:
        existing.status = ImportStatus.RUNNING
        existing.started_at = timezone.now()
        existing.finished_at = None
        if file_name:
            existing.file_name = file_name
        existing.save(
            update_fields=["status", "started_at", "finished_at", "file_name", "updated_at"]
        )
        return existing, True
    run = ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.RUNNING,
    )
    return run, False


def _close_run(run: ImportRun, report_dict: dict[str, Any]) -> None:
    run.status = ImportStatus.COMPLETED
    run.finished_at = timezone.now()
    run.report = report_dict
    run.save(update_fields=["status", "finished_at", "report", "updated_at"])


# ---------------------------------------------------------------------------
# Öğrenci içe aktarma + mutabakat
# ---------------------------------------------------------------------------
ClassKey = tuple[int | None, str]


def _class_key_label(key: ClassKey) -> str:
    level, section = key
    if level is None or not section:
        return ""
    return Student(class_level=level, class_section=section).class_label


def _class_sort_key(impact: ClassImpact) -> tuple[Any, ...]:
    return (
        impact.class_level is None,
        impact.class_level if impact.class_level is not None else 0,
        normalize.tr_sort_key(impact.class_section),
    )


@dataclass
class _StudentRun:
    """Tek aktarım koşusunun ara durumu (eşleşenler, kapsam, şube etkileri)."""

    report: StudentImportReport
    matched_ids: set[int] = field(default_factory=set)
    seen_indexes: set[str] = field(default_factory=set)
    scope: set[ClassKey] = field(default_factory=set)
    impacts: dict[ClassKey, ClassImpact] = field(default_factory=dict)

    def impact(self, key: ClassKey) -> ClassImpact:
        if key not in self.impacts:
            self.impacts[key] = ClassImpact(
                class_label=_class_key_label(key), class_level=key[0], class_section=key[1]
            )
        return self.impacts[key]


@transaction.atomic
def _ingest_students(
    *, grid: list[list[Any]], source_hash: str, file_name: str = "", full_list: bool = False
) -> StudentImportReport:
    """Matristeki öğrenci satırlarını yazar ve mutabakatı uygular (kör indeks eşleşmesi)."""
    app_password.require_password_set()
    mapping, rows = _parse_student_grid(grid)
    report = StudentImportReport(
        file_hash=source_hash, file_name=file_name, total_rows=len(rows), full_list=full_list
    )
    run, already = _open_run(
        source_type=ImportSourceType.STUDENTS, source_hash=source_hash, file_name=file_name
    )
    report.already_imported = already
    for header_warning in mapping.warnings:
        report.add_warning(mapping.header_row + 1, "header", header_warning)

    kosu = _StudentRun(report=report)
    for row in rows:
        if row.class_level is not None:
            # Kapsam: dosyada GÖRÜLEN şubeler (satır başka sebeple atlansa da).
            kosu.scope.add((row.class_level, row.class_section))
        _process_student_row(row, kosu)

    _reconcile_students(kosu)
    report.classes = sorted(kosu.impacts.values(), key=_class_sort_key)
    _ensure_class_sections()
    _close_run(run, report.to_run_dict())
    return report


def _process_student_row(row: ParsedRow, kosu: _StudentRun) -> None:
    """Tek satır: doğrula → kör indeksle bul (aktif / ayrılmış) → oluştur/güncelle."""
    report = kosu.report
    if not row.student_number:
        report.add_skip(row.row_number, "number", "Okul numarası bulunamadı.")
        return
    if row.class_level is None:
        report.add_skip(row.row_number, "class", "Sınıf/şube çözülemedi", row.raw_class)
        return
    if not row.student_first and not row.student_last:
        report.add_skip(row.row_number, "student_name", "Öğrenci adı boş; satır atlandı.")
        return
    index = student_number_blind_index(row.student_number)
    if index in kosu.seen_indexes:
        # Numara (şifreli kişi verisi) rapora YAZILMAZ; satır no yeter.
        report.add_skip(row.row_number, "number", DUPLICATE_ROW_MESSAGE)
        return
    kosu.seen_indexes.add(index)

    fields: dict[str, Any] = {
        "first_name": row.student_first,
        "last_name": row.student_last,
        "class_level": row.class_level,
        "class_section": row.class_section,
    }
    impact = kosu.impact((row.class_level, row.class_section))

    # Tekillik DB kısıtıyla garanti (`uq_student_number_index_active_alive`):
    # aktif canlı kayıtlar arasında kör indeks tekil → çift eşleşme dalı yoktur.
    student = Student.objects.filter(
        student_number_index=index, status=StudentStatus.ACTIVE
    ).first()
    reactivated = False
    if student is None:
        student = selectors.find_left_student_by_number(row.student_number)
        if student is not None:
            persons.reactivate_student(student)
            reactivated = True
    if student is None:
        created = Student.objects.create(**fields, student_number=row.student_number)
        kosu.matched_ids.add(created.pk)
        report.created_students += 1
        impact.created += 1
    else:
        changed = [name for name, value in fields.items() if getattr(student, name) != value]
        for name in changed:
            setattr(student, name, fields[name])
        if reactivated:
            changed += ["status", "left_at"]
        if changed:
            # Okul no yazılmaz: kör indeks zaten eşit (yalnız yazım farkı olabilir).
            student.save(update_fields=[*changed, "updated_at"])
            report.updated_students += 1
            impact.updated += 1
            if reactivated:
                report.reactivated_students += 1
        else:
            report.unchanged_students += 1
            impact.unchanged += 1
        kosu.matched_ids.add(student.pk)
    report.processed += 1


def _reconcile_students(kosu: _StudentRun) -> None:
    """Dosyada olmayan AKTİF öğrencileri ayrılış yolundan geçirir (EK-21).

    Kapsam varsayılan olarak yalnız dosyada bulunan şubelerdir; `full_list`
    verilmişse bütün aktif öğrenciler (sınıfsızlar dahil) karşılaştırılır.
    Bu dosyada eşleşen öğrenci (şube değiştirmiş olsa da) hiçbir durumda
    ayrılmaz.
    """
    report = kosu.report
    adaylar = Student.objects.filter(status=StudentStatus.ACTIVE).exclude(pk__in=kosu.matched_ids)
    ayrilacaklar = [
        s for s in adaylar if report.full_list or (s.class_level, s.class_section) in kosu.scope
    ]
    for student in selectors.students_sorted(ayrilacaklar):
        kosu.impact((student.class_level, student.class_section)).leaving += 1
        report.leaving.append(
            LeavingStudent(
                id=student.pk,
                full_name=student.full_name,
                student_number=student.student_number,
                class_label=student.class_label,
            )
        )
        persons.leave_student(student)
        report.leaving_students += 1


def _ensure_class_sections() -> None:
    """Sicildeki aktif öğrenci şubelerini aktif yılın şube kataloğuna ekler."""
    year = SchoolYear.objects.filter(is_active=True).first()
    if year is None:
        return
    class_pairs = set(
        Student.objects.filter(status=StudentStatus.ACTIVE)
        .exclude(class_level=None)
        .exclude(class_section="")
        .values_list("class_level", "class_section")
    )
    for level, section in sorted(class_pairs):
        ClassSection.objects.get_or_create(
            school_year=year,
            class_level=level,
            class_section=section,
        )


# ---------------------------------------------------------------------------
# Personel içe aktarma + mutabakat
# ---------------------------------------------------------------------------
def _name_key(value: str) -> str:
    """Ad-soyad eşleştirme anahtarı (ASCII'ye katlanmış, küçük harf, tek boşluk)."""
    return excel_ogrenci.normalize_header(value)


def _edit_distance(a: str, b: str, *, limit: int) -> int:
    """Levenshtein uzaklığı; `limit`'i aşınca erken döner (limit + 1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        simdiki = [i]
        for j, cb in enumerate(b, start=1):
            simdiki.append(min(onceki[j] + 1, simdiki[j - 1] + 1, onceki[j - 1] + (ca != cb)))
        if min(simdiki) > limit:
            return limit + 1
        onceki = simdiki
    return onceki[-1]


def _probably_same(row: ParsedPersonnelRow, person: Personnel) -> bool:
    """ "Olası aynı kişi": ad aynı soyad farklı (soyadı değişimi) YA DA ad-soyad uzaklığı ≤ 2."""
    row_first = _name_key(row.first_name)
    if row_first and row_first == _name_key(person.first_name):
        return True
    return (
        _edit_distance(
            _name_key(row.raw_full_name),
            _name_key(person.full_name),
            limit=SIMILAR_NAME_MAX_DISTANCE,
        )
        <= SIMILAR_NAME_MAX_DISTANCE
    )


@dataclass
class _PersonnelRun:
    report: PersonnelImportReport
    by_key: dict[str, list[Personnel]] = field(default_factory=dict)
    matched_ids: set[int] = field(default_factory=set)
    created: list[tuple[ParsedPersonnelRow, Personnel]] = field(default_factory=list)


@transaction.atomic
def _ingest_personnel(
    *,
    grid: list[list[Any]],
    source_hash: str,
    file_name: str = "",
    mark_left_ids: Collection[int] = (),
) -> PersonnelImportReport:
    """Matristeki personel satırlarını yazar ve mutabakatı uygular (ada göre eşleşme).

    Eşleşme anahtarı normalize edilmiş ad-soyaddır — ad ŞİFRELİ saklandığından
    dizin daima Python tarafında kurulur (çözülmüş değerlerle; kilitliyken API
    kapısı zaten 423 verir). Adaşlar tek tek tüketilir: aynı adı taşıyan iki
    satır iki ayrı kayda eşleşir (biri "listede yok" sayılmaz). Aktif kayıt
    ayrılmış kayıttan önce eşleşir; ayrılmış kayıt eşleşirse yeniden aktifleşir.
    """
    app_password.require_password_set()
    mapping, rows = _parse_personnel_grid(grid)
    report = PersonnelImportReport(file_hash=source_hash, file_name=file_name, total_rows=len(rows))
    run, already = _open_run(
        source_type=ImportSourceType.PERSONNEL, source_hash=source_hash, file_name=file_name
    )
    report.already_imported = already
    for header_warning in mapping.warnings:
        report.add_warning(mapping.header_row + 1, "header", header_warning)

    mevcut = sorted(Personnel.objects.all(), key=lambda p: (not p.is_active, p.pk))
    kosu = _PersonnelRun(report=report)
    for person in mevcut:
        kosu.by_key.setdefault(_name_key(person.full_name), []).append(person)
    for row in rows:
        _process_personnel_row(row, kosu)

    missing = selectors.personnel_sorted(
        p for p in mevcut if p.is_active and p.pk not in kosu.matched_ids
    )
    report.missing = [MissingPersonnel(id=p.pk, full_name=p.full_name) for p in missing]
    report.missing_count = len(missing)

    ayrilacak = set(mark_left_ids)
    report.similar_pairs = [
        SimilarPair(
            row_number=row.row_number,
            row_name=row.raw_full_name,
            existing_id=person.pk,
            existing_name=person.full_name,
            new_id=new_person.pk,
        )
        for row, new_person in kosu.created
        for person in missing
        # Ayrıldı olarak işaretlenen kişi kullanıcının kararıyla başka biridir.
        if person.pk not in ayrilacak and _probably_same(row, person)
    ]
    report.similar_pair_count = len(report.similar_pairs)

    for person in missing:
        if person.pk in ayrilacak:
            persons.leave_personnel(person)
            report.left_personnel += 1

    _close_run(run, report.to_run_dict())
    return report


def _process_personnel_row(row: ParsedPersonnelRow, kosu: _PersonnelRun) -> None:
    """Tek personel satırı: ada göre bul/oluştur; boş hücre mevcut veriyi silmez."""
    report = kosu.report
    if not row.first_name and not row.last_name:
        report.add_skip(row.row_number, "full_name", "Ad-soyad boş; satır atlandı.")
        return
    if row.member_kind_unrecognized:
        report.add_warning(row.row_number, "member_kind", MEMBER_KIND_CHECK_MESSAGE)

    adaylar = [
        p for p in kosu.by_key.get(_name_key(row.raw_full_name), []) if p.pk not in kosu.matched_ids
    ]
    if not adaylar:
        person = Personnel.objects.create(
            first_name=row.first_name,
            last_name=row.last_name,
            member_kind=row.member_kind or MemberKind.TEACHER,
        )
        kosu.created.append((row, person))
        kosu.matched_ids.add(person.pk)
        report.created_personnel += 1
        report.processed += 1
        return

    person = adaylar[0]
    changed: list[str] = []
    reactivated = not person.is_active
    if reactivated:
        persons.reactivate_personnel(person)
        changed += ["is_active", "left_at"]
    if row.member_kind and person.member_kind != row.member_kind:
        person.member_kind = row.member_kind
        changed.append("member_kind")
    if changed:
        person.save(update_fields=[*changed, "updated_at"])
        report.updated_personnel += 1
        if reactivated:
            report.reactivated_personnel += 1
    else:
        report.unchanged_personnel += 1
    kosu.matched_ids.add(person.pk)
    report.processed += 1


# ---------------------------------------------------------------------------
# Kamu API — dosya ve pano girişleri (preview/commit)
# ---------------------------------------------------------------------------
def commit_students_file(
    *, file_bytes: bytes, file_name: str = "", full_list: bool = False
) -> StudentImportReport:
    return _student_entry(
        lambda: _grid_from_file(file_bytes),
        file_hash(file_bytes),
        file_name,
        preview=False,
        full_list=full_list,
    )


def commit_students_text(*, text: str, full_list: bool = False) -> StudentImportReport:
    return _student_entry(
        lambda: text_to_grid(text), text_hash(text), "", preview=False, full_list=full_list
    )


def preview_students_file(
    *, file_bytes: bytes, file_name: str = "", full_list: bool = False
) -> StudentImportReport:
    return _student_entry(
        lambda: _grid_from_file(file_bytes),
        file_hash(file_bytes),
        file_name,
        preview=True,
        full_list=full_list,
    )


def preview_students_text(*, text: str, full_list: bool = False) -> StudentImportReport:
    return _student_entry(
        lambda: text_to_grid(text), text_hash(text), "", preview=True, full_list=full_list
    )


def commit_personnel_file(
    *, file_bytes: bytes, file_name: str = "", mark_left_ids: Collection[int] = ()
) -> PersonnelImportReport:
    return _personnel_entry(
        lambda: _grid_from_file(file_bytes),
        file_hash(file_bytes),
        file_name,
        preview=False,
        mark_left_ids=mark_left_ids,
    )


def commit_personnel_text(
    *, text: str, mark_left_ids: Collection[int] = ()
) -> PersonnelImportReport:
    return _personnel_entry(
        lambda: text_to_grid(text), text_hash(text), "", preview=False, mark_left_ids=mark_left_ids
    )


def preview_personnel_file(
    *, file_bytes: bytes, file_name: str = "", mark_left_ids: Collection[int] = ()
) -> PersonnelImportReport:
    return _personnel_entry(
        lambda: _grid_from_file(file_bytes),
        file_hash(file_bytes),
        file_name,
        preview=True,
        mark_left_ids=mark_left_ids,
    )


def preview_personnel_text(
    *, text: str, mark_left_ids: Collection[int] = ()
) -> PersonnelImportReport:
    return _personnel_entry(
        lambda: text_to_grid(text), text_hash(text), "", preview=True, mark_left_ids=mark_left_ids
    )


def _student_entry(
    grid_supplier: Callable[[], list[list[Any]]],
    source_hash: str,
    file_name: str,
    *,
    preview: bool,
    full_list: bool,
) -> StudentImportReport:
    """Ortak giriş: ParserError'da kalıcı FAILED izi bırakır ve hatayı yükseltir.

    Ingest atomiktir — hata rollback'i RUNNING satırını da siler; FAILED izi bu
    yüzden transaction DIŞINDA, burada yazılır (geçmiş görünümü boş kalmasın).
    """
    try:
        grid = grid_supplier()
        if preview:
            return _preview_students(
                grid=grid, source_hash=source_hash, file_name=file_name, full_list=full_list
            )
        report = _ingest_students(
            grid=grid, source_hash=source_hash, file_name=file_name, full_list=full_list
        )
    except ParserError as exc:
        _record_failed(ImportSourceType.STUDENTS, source_hash, file_name, exc)
        raise
    # Günlüğe yalnız sayılar (kişi adı, okul no yok — sözlük §5).
    logger.info(
        "Öğrenci aktarımı uygulandı: %d yeni, %d güncellenen, %d değişmeyen, %d ayrılan.",
        report.created_students,
        report.updated_students,
        report.unchanged_students,
        report.leaving_students,
    )
    return report


def _personnel_entry(
    grid_supplier: Callable[[], list[list[Any]]],
    source_hash: str,
    file_name: str,
    *,
    preview: bool,
    mark_left_ids: Collection[int],
) -> PersonnelImportReport:
    try:
        grid = grid_supplier()
        if preview:
            return _preview_personnel(
                grid=grid,
                source_hash=source_hash,
                file_name=file_name,
                mark_left_ids=mark_left_ids,
            )
        report = _ingest_personnel(
            grid=grid, source_hash=source_hash, file_name=file_name, mark_left_ids=mark_left_ids
        )
    except ParserError as exc:
        _record_failed(ImportSourceType.PERSONNEL, source_hash, file_name, exc)
        raise
    logger.info(
        "Personel aktarımı uygulandı: %d yeni, %d güncellenen, %d değişmeyen, %d ayrılan.",
        report.created_personnel,
        report.updated_personnel,
        report.unchanged_personnel,
        report.left_personnel,
    )
    return report


def _preview_students(
    *, grid: list[list[Any]], source_hash: str, file_name: str = "", full_list: bool = False
) -> StudentImportReport:
    """Öğrenci importunu YAZMADAN simüle eder (gerçek ingest + mutabakat + rollback)."""
    with transaction.atomic():
        report = _ingest_students(
            grid=grid, source_hash=source_hash, file_name=file_name, full_list=full_list
        )
        transaction.set_rollback(True)
    report.dry_run = True
    _record_preview(ImportSourceType.STUDENTS, report.file_hash, file_name, report.to_run_dict())
    return report


def _preview_personnel(
    *,
    grid: list[list[Any]],
    source_hash: str,
    file_name: str = "",
    mark_left_ids: Collection[int] = (),
) -> PersonnelImportReport:
    with transaction.atomic():
        report = _ingest_personnel(
            grid=grid, source_hash=source_hash, file_name=file_name, mark_left_ids=mark_left_ids
        )
        transaction.set_rollback(True)
    report.dry_run = True
    # Önizlemenin açtığı yeni kayıtlar geri alındı: kimlikleri anlamsızdır.
    for pair in report.similar_pairs:
        pair.new_id = None
    _record_preview(ImportSourceType.PERSONNEL, report.file_hash, file_name, report.to_run_dict())
    return report


def _record_preview(
    source_type: str, source_hash: str, file_name: str, report_dict: dict[str, Any]
) -> None:
    """Kalıcı PREVIEWED izi (geçmiş görünümü) — rollback DIŞINDA yazılır; ad içermez."""
    ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.PREVIEWED,
        finished_at=timezone.now(),
        report=report_dict,
    )


def _record_failed(source_type: str, source_hash: str, file_name: str, error: Exception) -> None:
    """Kalıcı FAILED izi. `error` metni yalnız yapısal bilgidir (sütun adları) — PII yok."""
    ImportRun.objects.create(
        source_type=source_type,
        file_name=file_name,
        file_hash=source_hash,
        status=ImportStatus.FAILED,
        finished_at=timezone.now(),
        report={"error": str(error)},
    )
