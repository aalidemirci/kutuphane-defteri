"""Öğrenci/Personel kayıt işlemleri, ayrılış yolu ve unutma kancası (tasarım §6.1, §6.4).

İnce servis katmanı — doğrulama/normalize serializer'da, yazma burada. View ORM
çağırmaz (katman disiplini).

UNUTMA KANCASI — KAYIT DEFTERLERİ (KS'den UYARLANDI). KS öğrenci LEFT olunca
kancalarla okul dışı veriyi hemen siliyordu. Kütüphanede kişinin açık ödüncü,
dosyası ya da teslimi olabilir; bu yüzden düzen dört kayıt defterine ayrıldı.
Bağımlılık yönü <uygulama> → okul'dur: okul diğer uygulamaları import etmez,
her uygulama kendi denetimini `AppConfig.ready` içinde buraya kaydeder (F6
üyelik ve ödünç, F7 teslim ve kayıp dosyası):

- `register_obligation_check(fn)` → `fn(kişi) -> list[str]`: kişinin AÇIK
  yükümlülüklerinin Türkçe gerekçeleri ("Açık ödünç var."). Gerekçe KİŞİ ADI
  İÇERMEZ (hata metnine ve günlüğe ad yazılmaz — sözlük §5).
- `register_membership_check(fn)` → `fn(kişi) -> bool`: kişi hiç üye olmuş mu.
- `register_leave_hook(fn)` → `fn(kişi)`: ayrılışta çağrılır (F6: üyeliği
  sonlandırır).
- `register_merge_hook(fn)` → `fn(kaynak, hedef)`: personel birleştirmede
  kaynağın bağlarını hedefe taşır (F6: üyelik ve ödünçler).

Kancalar AYNI veritabanı işleminde koşar: hata verirlerse durum değişikliği de
geri sarılır. Aktarım önizlemesi ayrılış yolunu savepoint içinde koşup geri
sardığı için kancalar yalnız veritabanına yazmalıdır (dosya, ağ yan etkisi yok).

AYRILIŞ YOLU (§6.1): `left_at = localdate()`, öğrencide durum LEFT, personelde
`is_active=False`, sonra ayrılış kancaları. **Hiç üye olmamış ve açık yükümlülüğü
olmayan kişi o anda KATI silinir** (saklanacak bir kütüphane ilişkisi yoktur,
kişisel veri tutulmaz); aksi hâlde kayıt kalır ve saklama süreleri (§6.4, F11)
işler. F1'de kayıtlı denetim yoktur: bugün her ayrılış katı silmeyle biter.

SİLME (kullanıcı eylemi): açık yükümlülük varsa gerekçeyle reddedilir; hiç üye
olmamışsa katı silinir; üye olmuşsa ayrılış yoluna yönlendirilir (silinmez).
Katı silme BİLİNÇLİDİR: `BaseModel.delete()`'in yumuşak silmesi kişi verisini
süresiz tutardı (§6.4 "hemen").
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.okul.models import (
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

_obligation_checks: list[ObligationCheck] = []
_membership_checks: list[MembershipCheck] = []
_leave_hooks: list[LeaveHook] = []
_merge_hooks: list[MergeHook] = []

#: Teklik iletisi servisten gelir (DRF'nin otomatik UniqueValidator'ı yoktur:
#: kısıt şifreli alanda değil kör indekstedir).
DUPLICATE_NUMBER_MESSAGE = "Bu okul numarası başka bir aktif öğrencide kayıtlı."
ALREADY_LEFT_MESSAGE = "Bu kişi zaten ayrıldı olarak işaretli."
MEMBER_DELETE_MESSAGE = (
    "Bu kişi kütüphane üyesi olmuş; kaydı silinemez. Okuldan ayrıldıysa "
    "“Ayrıldı olarak işaretle” eylemini kullanın."
)
SELF_MERGE_MESSAGE = "Bir kişi kendisiyle birleştirilemez."


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
    """Ayrılış kancası: `fn(kişi)` ayrılış işlendikten sonra, silme kararından önce koşar."""
    _register(_leave_hooks, fn)


def register_merge_hook(fn: MergeHook) -> None:
    """Birleştirme kancası: `fn(kaynak, hedef)` kaynağın bağlarını hedefe taşır."""
    _register(_merge_hooks, fn)


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
def _finish_leave(person: Person) -> bool:
    """Ayrılış kancaları + silme kararı. Kayıt katı silindiyse True döner."""
    for hook in _leave_hooks:
        hook(person)
    if was_ever_member(person) or open_obligations(person):
        return False
    person.hard_delete()
    return True


def _ensure_deletable(person: Person) -> None:
    """Kullanıcı silmesi: açık yükümlülük ya da geçmiş üyelik varsa Türkçe ret (400)."""
    gerekceler = open_obligations(person)
    if gerekceler:
        raise ValidationError("Kayıt silinemez: " + " ".join(gerekceler))
    if was_ever_member(person):
        raise ValidationError(MEMBER_DELETE_MESSAGE)


def _changed_fields(instance: Any, fields: dict[str, Any]) -> list[str]:
    return [name for name, value in fields.items() if getattr(instance, name) != value]


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
def leave_student(student: Student, *, log: bool = True) -> bool:
    """Ayrılış yolu (§6.1). Kayıt katı silindiyse True, saklandıysa False döner.

    `log=False`: toplu çağıran (e-Okul aktarımı) kişi başına günlük satırı
    yazdırmaz — önizleme bu yolu savepoint'te koşup GERİ SARAR ve günlük geri
    sarılmaz; aktarım kendi sayısal özetini yalnız uygulamada yazar.
    """
    if student.status == StudentStatus.LEFT:
        raise ValidationError(ALREADY_LEFT_MESSAGE)
    student.status = StudentStatus.LEFT
    student.left_at = timezone.localdate()
    student.save(update_fields=["status", "left_at", "updated_at"])
    silindi = _finish_leave(student)
    if log:
        logger.info("Öğrenci ayrılışı işlendi; kayıt %s.", "silindi" if silindi else "saklandı")
    return silindi


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
def leave_personnel(person: Personnel, *, log: bool = True) -> bool:
    """Ayrılış yolu (§6.1). Kayıt katı silindiyse True, saklandıysa False döner.

    `log=False`: toplu çağıran kişi başına günlük satırı yazdırmaz (bkz.
    `leave_student`).
    """
    if not person.is_active:
        raise ValidationError(ALREADY_LEFT_MESSAGE)
    person.is_active = False
    person.left_at = timezone.localdate()
    person.save(update_fields=["is_active", "left_at", "updated_at"])
    silindi = _finish_leave(person)
    if log:
        logger.info("Personel ayrılışı işlendi; kayıt %s.", "silindi" if silindi else "saklandı")
    return silindi


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
    listede artık bulunmayan eski kayıt KAYNAKTIR. İki kayıt da canlı olmalıdır
    (görünüm yalnız canlı kayıtları çözer) ve aynı kişi olamaz. Taşıma
    birleştirme kancalarıyla yapılır (F6: üyelik ve ödünçler); F1'de kayıtlı
    kanca yoktur.
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
