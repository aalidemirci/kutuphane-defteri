"""Üyelik ve dolaşım testlerinin ortak kurgu yardımcıları (toplanmaz: `test_` ile başlamaz).

Bütün kişi verileri UYDURMADIR (CLAUDE.md §2-12): adlar "Deneme …" kalıbındadır,
okul numaraları sıradan üretilir; gerçek bir kişiyi düşündürmez.
"""

from __future__ import annotations

import itertools
from datetime import date, timedelta
from typing import Any

import pytest
from django.utils import timezone

from apps.kutuphane.models import Copy, LibraryPolicy, Loan, Membership
from apps.kutuphane.services import circulation, memberships
from apps.kutuphane.services import policy as policy_service
from apps.kutuphane.tests.ortak import eser, nusha
from apps.okul.models import MemberKind, Personnel, SchoolTerm, SchoolYear, Student

#: Hafta içi, kapalı gün olmayan bir perşembe; +15 gün = 09.10.2026 cuma (açık gün).
ACIK_GUN = date(2026, 9, 24)

_okul_no = itertools.count(700001)


def ogrenci(**alanlar: Any) -> Student:
    """Aktif öğrenci (uydurma ad, sıradan okul no, 9/A)."""
    alanlar.setdefault("first_name", "Deneme")
    alanlar.setdefault("last_name", "Öğrenci")
    alanlar.setdefault("student_number", str(next(_okul_no)))
    alanlar.setdefault("class_level", 9)
    alanlar.setdefault("class_section", "A")
    kayit: Student = Student.objects.create(**alanlar)
    return kayit


def personel(**alanlar: Any) -> Personnel:
    """Aktif personel (varsayılan öğretmen)."""
    alanlar.setdefault("first_name", "Deneme")
    alanlar.setdefault("last_name", "Personel")
    alanlar.setdefault("member_kind", MemberKind.TEACHER)
    kayit: Personnel = Personnel.objects.create(**alanlar)
    return kayit


def uye(kisi: Student | Personnel | None = None, **alanlar: Any) -> Membership:
    """Kişiye (verilmezse yeni öğrenciye) servis yoluyla üyelik açar."""
    hedef = kisi if kisi is not None else ogrenci()
    if isinstance(hedef, Student):
        return memberships.create_membership(student=hedef, **alanlar)
    return memberships.create_membership(personnel=hedef, **alanlar)


def odunc_nushasi(**alanlar: Any) -> Copy:
    """Ödünç verilebilir (rafta, danışma değil) yeni bir nüsha — kendi eseriyle."""
    return nusha(eser(title=alanlar.pop("title", "Deneme Eseri")), **alanlar)


def politika(**alanlar: Any) -> LibraryPolicy:
    return policy_service.update_policy(**alanlar)


def personele_odunc_ac(**alanlar: Any) -> LibraryPolicy:
    """Diğer personele ödünç seçeneğini müdürlük kararıyla açar (AT-4)."""
    alanlar.setdefault("staff_loans_decision_date", date(2026, 9, 1))
    alanlar.setdefault("staff_loans_decision_no", "2026/12")
    return politika(staff_loans_enabled=True, **alanlar)


def odunc_ver(uyelik: Membership, copy: Copy | None = None, /, **alanlar: Any) -> Loan:
    """Servis yoluyla ödünç verir; ödünç kaydını döndürür."""
    hedef = copy if copy is not None else odunc_nushasi()
    return circulation.checkout(copy=hedef, membership=uyelik, **alanlar).loan


def gecikmeli_yap(loan: Loan, *, gun: int = 5) -> Loan:
    """Ödüncün iade tarihini bugünden `gun` gün öncesine çeker (gecikme kurgusu)."""
    Loan.objects.filter(pk=loan.pk).update(due_date=timezone.localdate() - timedelta(days=gun))
    loan.refresh_from_db()
    return loan


def ders_yili(
    *,
    baslangic: date = date(2026, 9, 7),
    birinci_bitis: date = date(2027, 1, 22),
    ikinci_baslangic: date = date(2027, 2, 8),
    bitis: date = date(2027, 6, 25),
) -> SchoolYear:
    """Etkin ders yılı ve iki dönemi (uydurma tarihler)."""
    yil: SchoolYear = SchoolYear.objects.create(
        name=f"{baslangic.year}-{bitis.year}", start_date=baslangic, end_date=bitis, is_active=True
    )
    SchoolTerm.objects.create(
        school_year=yil, sequence=1, start_date=baslangic, end_date=birinci_bitis
    )
    SchoolTerm.objects.create(
        school_year=yil, sequence=2, start_date=ikinci_baslangic, end_date=bitis
    )
    return yil


def gunu_sabitle(monkeypatch: pytest.MonkeyPatch, baslangic: date = ACIK_GUN) -> list[date]:
    """Argümansız `timezone.localdate()`'i sabitler; dönen listenin ilk öğesi değiştirilerek
    gün ilerletilir (`conftest.bugun`).

    Model alanlarının `default=timezone.localdate` varsayılanı tanım anında
    bağlandığı için etkilenmez (servisler tarihi açıkça yazar). Bir değeri yerel
    tarihe çeviren çağrı (`localdate(dt)`) özgün işleve gider.
    """
    gun = [baslangic]
    ozgun = timezone.localdate

    def sabit(value: Any = None, timezone: Any = None) -> date:
        return gun[0] if value is None else ozgun(value, timezone)

    monkeypatch.setattr("django.utils.timezone.localdate", sabit)
    return gun
