"""Öğrenci/Personel kayıt işlemleri, ayrılış yolu, ayrılış havuzu ve unutma kancası.

Tasarım §6.1, §6.4, §8.3; F1 eki 7 (kullanıcı kararı 22.09.2026). İnce servis
katmanı — doğrulama/normalize serializer'da, yazma burada. View ORM çağırmaz
(katman disiplini).

UNUTMA KANCASI — KAYIT DEFTERLERİ (KS'den UYARLANDI). KS öğrenci LEFT olunca
kancalarla okul dışı veriyi hemen siliyordu. Kütüphanede kişinin açık ödüncü,
dosyası ya da teslimi olabilir; bu yüzden düzen dört kayıt defterine ayrıldı.
Bağımlılık yönü <uygulama> → okul'dur: okul diğer uygulamaları import etmez,
her uygulama kendi denetimini `AppConfig.ready` içinde buraya kaydeder (F6
üyelik ve ödünç; F7 açık teslim ve çözülmemiş kayıp/hasar dosyası yükümlülük,
kapanmış teslim silme engeli, teslimlerin birleştirmede taşınması):

- `register_obligation_check(fn)` → `fn(kişi) -> list[str]`: kişinin AÇIK
  yükümlülüklerinin Türkçe gerekçeleri ("Açık ödünç var."). Gerekçe KİŞİ ADI
  İÇERMEZ (hata metnine ve günlüğe ad yazılmaz — sözlük §5).
- `register_membership_check(fn)` → `fn(kişi) -> bool`: kişi hiç üye olmuş mu.
- `register_leave_hook(fn)` → `fn(kişi)`: ayrılışta çağrılır (F6: üyeliği
  sonlandırır).
- `register_merge_hook(fn)` → `fn(kaynak, hedef)`: personel birleştirmede
  kaynağın bağlarını hedefe taşır (F6: üyelik ve ödünçler; F7: teslimler).
- `register_deletion_block(fn)` → `fn(kişi) -> list[str]` (F7): açık yükümlülük
  olmasa da kişiye bağlı kalıcı kaydı (kapanmış teslim) olan kişinin
  kullanıcı silmesini gerekçeyle reddeder.

Kancalar AYNI veritabanı işleminde koşar: hata verirlerse durum değişikliği de
geri sarılır. Kancalar yalnız veritabanına yazmalıdır (dosya, ağ yan etkisi yok).

AYRILIŞ HAVUZU (F1 eki 7). Kullanıcının kararı: "ayrılanları doğrudan silme,
bir havuza ekle, orada karar verilsin; ayrılanın iade etmediği kitap olabilir,
kaydı silmeyelim, yalnız aktif öğrencilik durumu değişsin."

- e-Okul aktarımı hiç kimseyi AYIRMAZ ve SİLMEZ. Listede bulunmayan aktif kişi
  havuza girer (`add_to_leave_pool`: giriş tarihi + hangi aktarımla); durumu
  AKTİF kalır. Dosyada yeniden görülen kişi havuzdan kendiliğinden çıkar
  (`remove_from_leave_pool`; şube değişimi dahil).
- Karar yöneticinindir (`resolve_leave_pool`, tek tek ya da toplu): "Ayrıldı
  olarak işaretle" ayrılış yolundan geçirir, "Aktif kalsın" yalnız havuzdan
  çıkarır. Yıl sonu mezunları bu yolla toplu ayrılır.
- Havuzdaki kişi DB kısıtıyla aktiftir (`ck_*_leave_candidate_active`).

AYRILIŞ YOLU (§6.1): `left_at = localdate()`, öğrencide durum LEFT, personelde
`is_active=False`, havuz alanları temizlenir, sonra ayrılış kancaları. **Ayrılış
kaydı SİLMEZ** — üyelik ve yükümlülükten bağımsız (eski "hiç üye olmamış ve
yükümlülüksüz → katı sil" dalı F1 eki 7 ile kalktı). Ayrılmış kişinin kaydı
saklama taramasına kalır (§6.4, F11: tarama aday gösterir, yönetici onayıyla
silinir; süre F11'de kararlaştırılır).

SİLME (kullanıcının bilinçli eylemi, "Sil" düğmesi): açık yükümlülük varsa
gerekçeyle reddedilir; hiç üye olmamışsa katı silinir; üye olmuşsa ayrılış
yoluna yönlendirilir (silinmez). Katı silme BİLİNÇLİDİR: yanlış girilmiş
kaydın yumuşak silmesi kişi verisini süresiz tutardı.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.okul.models import (
    ImportRun,
    MemberKind,
    Personnel,
    Student,
    StudentStatus,
    student_number_blind_index,
)
from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.okul")

type Person = Student | Personnel

type ObligationCheck = Callable[[Person], Iterable[str]]
type MembershipCheck = Callable[[Person], bool]
type LeaveHook = Callable[[Person], None]
type MergeHook = Callable[[Personnel, Personnel], None]
type DeletionBlock = Callable[[Person], Iterable[str]]

_obligation_checks: list[ObligationCheck] = []
_membership_checks: list[MembershipCheck] = []
_leave_hooks: list[LeaveHook] = []
_merge_hooks: list[MergeHook] = []
_deletion_blocks: list[DeletionBlock] = []

#: Ayrılış havuzu alanları (öğrenci ve personelde aynı adlar).
POOL_FIELDS: tuple[str, str] = ("leave_candidate_since", "leave_candidate_run")

#: Teklik iletisi servisten gelir (DRF'nin otomatik UniqueValidator'ı yoktur:
#: kısıt şifreli alanda değil kör indekstedir).
DUPLICATE_NUMBER_MESSAGE = "Bu okul numarası başka bir aktif öğrencide kayıtlı."
ALREADY_LEFT_MESSAGE = "Bu kişi zaten ayrıldı olarak işaretli."
MEMBER_DELETE_MESSAGE = (
    "Bu kişi kütüphane üyesi olmuş; kaydı silinemez. Okuldan ayrıldıysa "
    "“Ayrıldı olarak işaretle” eylemini kullanın."
)
SELF_MERGE_MESSAGE = "Bir kişi kendisiyle birleştirilemez."
POOL_EMPTY_MESSAGE = "Karar verilecek kişi seçilmedi."
POOL_CONFLICT_MESSAGE = "Aynı kişi için hem “Ayrıldı olarak işaretle” hem “Aktif kalsın” seçilemez."
POOL_STALE_MESSAGE = (
    "Seçilen kişilerden bazıları artık ayrılış havuzunda değil. Listeyi yenileyip "
    "yeniden seçin; hiçbir karar uygulanmadı."
)


# ---------------------------------------------------------------------------
# Kayıt defterleri
# ---------------------------------------------------------------------------
def _register(registry: list[Any], fn: Any) -> None:
    """İdempotent kayıt (`AppConfig.ready` iki kez koşsa da kanca bir kez çağrılır)."""
    if fn not in registry:
        registry.append(fn)


def register_obligation_check(fn: ObligationCheck) -> None:
    """Açık yükümlülük denetimi: `fn(kişi)` Türkçe gerekçe listesi döner (ad içermez)."""
    _register(_obligation_checks, fn)


def register_membership_check(fn: MembershipCheck) -> None:
    """Üyelik denetimi: `fn(kişi)` kişi hiç kütüphane üyesi olmuşsa True döner."""
    _register(_membership_checks, fn)


def register_leave_hook(fn: LeaveHook) -> None:
    """Ayrılış kancası: `fn(kişi)` ayrılış (LEFT + tarih) yazıldıktan sonra koşar."""
    _register(_leave_hooks, fn)


def register_merge_hook(fn: MergeHook) -> None:
    """Birleştirme kancası: `fn(kaynak, hedef)` kaynağın bağlarını hedefe taşır."""
    _register(_merge_hooks, fn)


def register_deletion_block(fn: DeletionBlock) -> None:
    """Silme engeli (F7): `fn(kişi)` kapanmış da olsa kişiye bağlı kayıt varsa gerekçe döner.

    Açık yükümlülükten AYRIDIR: kapanmış bir teslim kişinin yükümlülüğü değildir
    (ilişik listesine girmez) ama teslim satırı kişiyi PROTECT ile tutar; bağı
    saklama taraması koparır (§6.4, F11), kullanıcının "Sil"i değil.
    """
    _register(_deletion_blocks, fn)


def deletion_blocks(person: Person) -> list[str]:
    """Kişinin silinmesini engelleyen (yükümlülük dışı) kayıtların gerekçeleri."""
    gerekceler: list[str] = []
    for check in _deletion_blocks:
        gerekceler.extend(check(person))
    return list(dict.fromkeys(g for g in gerekceler if g))


def open_obligations(person: Person) -> list[str]:
    """Kişinin açık yükümlülük gerekçeleri (tekilleştirilmiş, kayıt sırasıyla)."""
    gerekceler: list[str] = []
    for check in _obligation_checks:
        gerekceler.extend(check(person))
    return list(dict.fromkeys(g for g in gerekceler if g))


def was_ever_member(person: Person) -> bool:
    """Kişi hiç kütüphane üyesi olmuş mu? (F1'de kayıtlı denetim yok → False)"""
    return any(check(person) for check in _membership_checks)


# ---------------------------------------------------------------------------
# Ortak yollar
# ---------------------------------------------------------------------------
def _is_active(person: Person) -> bool:
    if isinstance(person, Student):
        return person.status == StudentStatus.ACTIVE
    return person.is_active


def _run_leave_hooks(person: Person) -> None:
    for hook in _leave_hooks:
        hook(person)


def _ensure_deletable(person: Person) -> None:
    """Kullanıcı silmesi: açık yükümlülük ya da geçmiş üyelik varsa Türkçe ret (400)."""
    gerekceler = open_obligations(person)
    if gerekceler:
        raise ValidationError("Kayıt silinemez: " + " ".join(gerekceler))
    engeller = deletion_blocks(person)
    if engeller:
        raise ValidationError(" ".join(engeller))
    if was_ever_member(person):
        raise ValidationError(MEMBER_DELETE_MESSAGE)


def _changed_fields(instance: Any, fields: dict[str, Any]) -> list[str]:
    return [name for name, value in fields.items() if getattr(instance, name) != value]


# ---------------------------------------------------------------------------
# Ayrılış havuzu (F1 eki 7)
# ---------------------------------------------------------------------------
def in_leave_pool(person: Person) -> bool:
    """Kişi ayrılış havuzunda mı (karar bekliyor mu)?"""
    return person.leave_candidate_since is not None


def add_to_leave_pool(person: Person, *, run: ImportRun | None) -> bool:
    """Aktif kişiyi ayrılış havuzuna ekler; durumu AKTİF kalır. Eklendiyse True.

    Kişi zaten havuzdaysa dokunulmaz: ilk giriş tarihi ve onu ekleyen aktarım
    korunur (aynı dosyanın ikinci uygulaması değişiklik üretmez). Yalnız havuz
    alanları yazılır — ad ve okul no'ya dokunulmaz, anahtar gerekmez.
    """
    if not _is_active(person):
        raise ValidationError(ALREADY_LEFT_MESSAGE)
    if in_leave_pool(person):
        return False
    person.leave_candidate_since = timezone.localdate()
    person.leave_candidate_run = run
    person.save(update_fields=[*POOL_FIELDS, "updated_at"])
    return True


def remove_from_leave_pool(person: Person, *, save: bool = True) -> bool:
    """Kişiyi havuzdan çıkarır (dosyada görüldü ya da "Aktif kalsın"). Havuzdaysa True.

    `save=False`: çağıran aynı kaydı başka alanlarla birlikte kendisi kaydeder
    (e-Okul aktarımı; `POOL_FIELDS`'i kendi `update_fields`'ine ekler).
    """
    if not in_leave_pool(person):
        return False
    person.leave_candidate_since = None
    person.leave_candidate_run = None
    if save:
        person.save(update_fields=[*POOL_FIELDS, "updated_at"])
    return True


@dataclass(frozen=True)
class PoolDecision:
    """Bir kişi türü için havuz kararı: ayrılacakların ve aktif kalacakların kimlikleri.

    Yinelenen kimlikler tekilleştirilir (sıra korunur).
    """

    leave: tuple[int, ...] = ()
    keep: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "leave", tuple(dict.fromkeys(self.leave)))
        object.__setattr__(self, "keep", tuple(dict.fromkeys(self.keep)))

    def ids(self) -> set[int]:
        return {*self.leave, *self.keep}


def _pool_members(model: type[Any], ids: Collection[int]) -> dict[int, Any]:
    """Kimlikleri havuzdaki AKTİF canlı kayıtlara çözer; biri eksikse hiçbir şey yapılmaz."""
    if not ids:
        return {}
    aktif: dict[str, Any] = (
        {"status": StudentStatus.ACTIVE} if model is Student else {"is_active": True}
    )
    bulunan = {
        kayit.pk: kayit
        for kayit in model.objects.filter(pk__in=ids, leave_candidate_since__isnull=False, **aktif)
    }
    if len(bulunan) != len(set(ids)):
        raise ValidationError(POOL_STALE_MESSAGE)
    return bulunan


@transaction.atomic
def resolve_leave_pool(
    *, students: PoolDecision | None = None, personnel: PoolDecision | None = None
) -> dict[str, int]:
    """Ayrılış havuzu kararı — tek tek ya da toplu; TEK işlem (ya hepsi ya hiçbiri).

    `leave` → ayrılış yolu (LEFT / `is_active=False` + `left_at`, havuzdan çıkış,
    ayrılış kancaları; kayıt SİLİNMEZ). `keep` → "Aktif kalsın": yalnız havuzdan
    çıkar. Seçilen kişi havuzda değilse (başka pencerede karar verilmiş, ayrılmış,
    silinmiş) bütün karar reddedilir. Günlüğe yalnız sayılar yazılır.
    """
    app_password.require_password_set()
    students = students or PoolDecision()
    personnel = personnel or PoolDecision()
    for karar in (students, personnel):
        if set(karar.leave) & set(karar.keep):
            raise ValidationError(POOL_CONFLICT_MESSAGE)
    if not (students.ids() or personnel.ids()):
        raise ValidationError(POOL_EMPTY_MESSAGE)

    ogrenciler = _pool_members(Student, students.ids())
    personeller = _pool_members(Personnel, personnel.ids())
    for pk in students.leave:
        leave_student(ogrenciler[pk], log=False)
    for pk in students.keep:
        remove_from_leave_pool(ogrenciler[pk])
    for pk in personnel.leave:
        leave_personnel(personeller[pk], log=False)
    for pk in personnel.keep:
        remove_from_leave_pool(personeller[pk])

    sonuc = {
        "students_left": len(students.leave),
        "students_kept": len(students.keep),
        "personnel_left": len(personnel.leave),
        "personnel_kept": len(personnel.keep),
    }
    logger.info(
        "Ayrılış havuzu kararı: %d öğrenci ayrıldı, %d öğrenci aktif kaldı; "
        "%d personel ayrıldı, %d personel aktif kaldı.",
        sonuc["students_left"],
        sonuc["students_kept"],
        sonuc["personnel_left"],
        sonuc["personnel_kept"],
    )
    return sonuc


# ---------------------------------------------------------------------------
# Öğrenci
# ---------------------------------------------------------------------------
def ensure_student_number_free(student_number: str, *, exclude_pk: int | None = None) -> None:
    """Okul no başka bir AKTİF canlı öğrencide mi? Kör indeksle tam eşleşme (T14).

    DB kısıtı (`uq_student_number_index_active_alive`) son savunma hattıdır;
    buradaki denetim çakışmayı 500 (IntegrityError) yerine Türkçe 400'e çevirir.
    """
    index = student_number_blind_index(student_number)
    if not index:
        return
    qs = Student.objects.filter(student_number_index=index, status=StudentStatus.ACTIVE)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError({"student_number": [DUPLICATE_NUMBER_MESSAGE]})


@transaction.atomic
def create_student(**fields: Any) -> Student:
    app_password.require_password_set()
    if fields.get("status", StudentStatus.ACTIVE) == StudentStatus.ACTIVE:
        ensure_student_number_free(str(fields.get("student_number") or ""))
    student: Student = Student.objects.create(**fields)
    return student


@transaction.atomic
def update_student(student: Student, **fields: Any) -> Student:
    """Yalnız DEĞİŞEN alanı yazar (bayat kopya başka alanı geri sarmaz).

    Durum buradan değişmez: ayrılış `leave_student`, yeniden aktifleşme e-Okul
    aktarımıyla olur (serializer `status`'u salt okunur sunar).
    """
    changed = _changed_fields(student, fields)
    if "student_number" in changed and student.status == StudentStatus.ACTIVE:
        ensure_student_number_free(str(fields["student_number"] or ""), exclude_pk=student.pk)
    if changed:
        for name in changed:
            setattr(student, name, fields[name])
        student.save(update_fields=[*changed, "updated_at"])
    return student


@transaction.atomic
def leave_student(student: Student, *, log: bool = True) -> Student:
    """Ayrılış yolu (§6.1): LEFT + `left_at`, havuzdan çıkış, kancalar. Kayıt SİLİNMEZ.

    `log=False`: toplu çağıran (havuz kararı) kişi başına günlük satırı
    yazdırmaz; kendi sayısal özetini yazar.
    """
    if student.status == StudentStatus.LEFT:
        raise ValidationError(ALREADY_LEFT_MESSAGE)
    student.status = StudentStatus.LEFT
    student.left_at = timezone.localdate()
    remove_from_leave_pool(student, save=False)
    student.save(update_fields=["status", "left_at", *POOL_FIELDS, "updated_at"])
    _run_leave_hooks(student)
    if log:
        logger.info("Öğrenci ayrılışı işlendi; kayıt saklandı.")
    return student


def reactivate_student(student: Student) -> None:
    """Ayrılmış (canlı) öğrenci aynı okul no ile döndü: AKTİF, `left_at` temizlenir.

    Kaydı çağıran kaydeder (aktarım aynı `save`'de ad ve şube değişikliğini de yazar).
    """
    student.status = StudentStatus.ACTIVE
    student.left_at = None


@transaction.atomic
def delete_student(student: Student) -> None:
    """Kullanıcı silmesi: açık yükümlülük yoksa ve hiç üye olmamışsa KATI silinir."""
    _ensure_deletable(student)
    student.hard_delete()
    logger.info("Öğrenci kaydı silindi.")


# ---------------------------------------------------------------------------
# Personel
# ---------------------------------------------------------------------------
@transaction.atomic
def create_personnel(**fields: Any) -> Personnel:
    app_password.require_password_set()
    fields.setdefault("member_kind", MemberKind.TEACHER)
    person: Personnel = Personnel.objects.create(**fields)
    return person


@transaction.atomic
def update_personnel(person: Personnel, **fields: Any) -> Personnel:
    """Yalnız DEĞİŞEN alanı yazar. Ayrılış `leave_personnel` ile olur."""
    changed = _changed_fields(person, fields)
    if changed:
        for name in changed:
            setattr(person, name, fields[name])
        person.save(update_fields=[*changed, "updated_at"])
    return person


@transaction.atomic
def leave_personnel(person: Personnel, *, log: bool = True) -> Personnel:
    """Ayrılış yolu (§6.1): `is_active=False` + `left_at`, havuzdan çıkış, kancalar.

    Kayıt SİLİNMEZ. `log=False`: toplu çağıran kişi başına günlük satırı
    yazdırmaz (bkz. `leave_student`).
    """
    if not person.is_active:
        raise ValidationError(ALREADY_LEFT_MESSAGE)
    person.is_active = False
    person.left_at = timezone.localdate()
    remove_from_leave_pool(person, save=False)
    person.save(update_fields=["is_active", "left_at", *POOL_FIELDS, "updated_at"])
    _run_leave_hooks(person)
    if log:
        logger.info("Personel ayrılışı işlendi; kayıt saklandı.")
    return person


def reactivate_personnel(person: Personnel) -> None:
    """Ayrılmış (canlı) personel listede yeniden görüldü: aktif, `left_at` temizlenir."""
    person.is_active = True
    person.left_at = None


@transaction.atomic
def delete_personnel(person: Personnel) -> None:
    """Kullanıcı silmesi: açık yükümlülük yoksa ve hiç üye olmamışsa KATI silinir."""
    _ensure_deletable(person)
    person.hard_delete()
    logger.info("Personel kaydı silindi.")


@transaction.atomic
def merge_personnel(source: Personnel, target: Personnel) -> Personnel:
    """ "Olası aynı kişi" birleştirmesi: kaynağın bağları hedefe taşınır, kaynak KATI silinir.

    Tipik kullanım soyadı değişimidir: e-Okul'dan yeni adla gelen kayıt HEDEF,
    listede artık bulunmayan (ayrılış havuzundaki) eski kayıt KAYNAKTIR.
    Birleştirme aktarım önizlemesinden sonra ya da ayrılış havuzundan yapılır.
    İki kayıt da canlı olmalıdır (görünüm yalnız canlı kayıtları çözer) ve aynı
    kişi olamaz. Taşıma birleştirme kancalarıyla yapılır (F6: üyelik ve
    ödünçler); F1'de kayıtlı kanca yoktur.
    """
    if source.pk == target.pk:
        raise ValidationError(SELF_MERGE_MESSAGE)
    if source.deleted_at is not None or target.deleted_at is not None:
        raise ValidationError("Birleştirilecek iki kayıt da sicilde bulunmalıdır.")
    for hook in _merge_hooks:
        hook(source, target)
    source.hard_delete()
    logger.info("Personel kayıtları birleştirildi.")
    return target
