"""Öğrenci/Personel elle kayıt işlemleri (KS'den alındı; tasarım §6.1).

İnce servis katmanı — doğrulama/normalize serializer'da, yazma burada. View ORM
çağırmaz (katman disiplini).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import transaction

from apps.okul.models import Personnel, Student, StudentStatus

#: Ayrılan/silinen öğrencinin OKUL DIŞI uygulamalardaki kişisel verisini silen
#: kancalar (KS, 20.09.2026). Bağımlılık yönü <uygulama> → okul'dur; okul diğer
#: uygulamaları import etmez — her uygulama kendi temizliğini `AppConfig.ready`
#: içinde buraya kaydeder (unutma kancası — tasarım §6.1). Kanca AYNI işlemde
#: koşar: hata verirse durum değişikliği de geri sarılır.
_forget_hooks: list[Callable[[int], None]] = []


def register_student_forget_hook(hook: Callable[[int], None]) -> None:
    """Öğrenci pasifleşince/silinince `hook(student_id)` çağrılsın (idempotent kayıt)."""
    if hook not in _forget_hooks:
        _forget_hooks.append(hook)


def _forget_student_data(student_id: int) -> None:
    """KVKK: ayrılan/silinen öğrencinin kancalı verileri temizlenir."""
    for hook in _forget_hooks:
        hook(student_id)


@transaction.atomic
def create_student(**fields: Any) -> Student:
    student: Student = Student.objects.create(**fields)
    return student


@transaction.atomic
def update_student(student: Student, **fields: Any) -> Student:
    changed = [name for name, value in fields.items() if getattr(student, name) != value]
    if changed:
        for name in changed:
            setattr(student, name, fields[name])
        student.save(update_fields=[*changed, "updated_at"])
    if student.status != StudentStatus.ACTIVE:
        # KVKK: ayrılan öğrencinin okul dışı verisi kancalarla temizlenir.
        _forget_student_data(student.pk)
    return student


@transaction.atomic
def delete_student(student: Student) -> None:
    student.delete()  # soft delete (BaseModel)
    # Kayıt gizlenir; kancalı kişisel veri artığı kalmasın.
    _forget_student_data(student.pk)


@transaction.atomic
def create_personnel(**fields: Any) -> Personnel:
    person: Personnel = Personnel.objects.create(**fields)
    return person


@transaction.atomic
def update_personnel(person: Personnel, **fields: Any) -> Personnel:
    changed = [name for name, value in fields.items() if getattr(person, name) != value]
    if changed:
        for name in changed:
            setattr(person, name, fields[name])
        person.save(update_fields=[*changed, "updated_at"])
    return person


@transaction.atomic
def delete_personnel(person: Personnel) -> None:
    person.delete()  # soft delete (BaseModel)
