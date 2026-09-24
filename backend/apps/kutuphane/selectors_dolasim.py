"""Üyelik ve dolaşım salt okuma sorguları (tasarım §7.3, §9, §4.4, T15).

Görünümler ve servisler üyelik/ödünç verisine buradan erişir. Üç kural bu
dosyanın biçimini belirler:

1. **Kart ve okul no eşleştirmesi KÖR İNDEKSLE, tam eşleşmedir** (T14). Kart no
   ve okul no şifrelidir; düz sütunla sorgu yazılmaz (`find_membership_by_card`,
   `find_active_membership_by_student_number`).
2. **Ad sıralaması ve ad araması Python'dadır** (U9, CLAUDE.md §3): ad şifreli
   olduğu için DB `order_by` token sırası verir. Kullanıcıya gösterilen her
   üyelik listesi `memberships_sorted` ile Türk alfabesine göre sıralanır.
3. **Sayılar KİŞİ bazındadır, üyelik bazında DEĞİL.** Ayrılıp dönen bir kişinin
   eski (sonlanmış) üyeliğinde iade etmediği kitap olabilir; sayı sınırı (Md.
   18) ve gecikme engeli yeni üyelikle sıfırlanmamalıdır. Açık ödünç, gecikme
   ve kalan hak bu yüzden kişinin BÜTÜN üyelikleri üzerinden sayılır.

**Profil yasağı** (tasarım §3, CLAUDE.md §2-5): bu modül üye bazında konu,
sınıflama, bölüm ya da sınıf DAĞILIMI üretmez. Üyenin ödünç geçmişi
(`member_loan_history`) yalnız yönetici kipindeki uçtan açılır ve yalnız ödünç
satırlarını verir (barkod, eser adı, tarihler); toplama yapılmaz. Koruma testi
`tests/test_dolasim_secicileri.py` modülün kaynağında konu/sınıflama alanlarının
geçmediğini de sabitler.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.kutuphane import card_numbers
from apps.kutuphane.models import (
    CardRevocation,
    LibraryPolicy,
    Loan,
    LoanStatus,
    Membership,
    MembershipStatus,
    MemberType,
    card_no_blind_index,
)
from apps.okul import normalize
from apps.okul import selectors as okul_selectors
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import Personnel, Student, StudentStatus

type Person = Student | Personnel
#: Kişi anahtarı: ('S', öğrenci pk) ya da ('P', personel pk).
type PersonKey = tuple[str, int]

#: Masada iptal edilmiş kart okutulunca gösterilen ileti (§7.3, sözlük).
REVOKED_CARD_MESSAGE = "İptal edilmiş kart — kütüphane yöneticisine yönlendirin."


# ---------------------------------------------------------------------------
# Kişi bazında sayılar
# ---------------------------------------------------------------------------
def person_key(membership: Membership) -> PersonKey:
    """Üyeliğin kişi anahtarı (sayıların kişi bazında toplanması için)."""
    if membership.student_id is not None:
        return ("S", int(membership.student_id))
    return ("P", int(membership.personnel_id or 0))


def _person_loans_q(person: Person) -> Q:
    """Kişinin BÜTÜN üyeliklerindeki ödünçler (Loan üzerinde)."""
    if isinstance(person, Student):
        return Q(membership__student=person)
    return Q(membership__personnel=person)


def _membership_person_q(person: Person) -> Q:
    """Kişinin üyelikleri (Membership üzerinde)."""
    if isinstance(person, Student):
        return Q(student=person)
    return Q(personnel=person)


def open_loans_for_person(person: Person) -> QuerySet[Loan]:
    """Kişinin açık ödünçleri — iade tarihine göre (en eski önce)."""
    return (
        Loan.objects.filter(_person_loans_q(person), status=LoanStatus.OPEN)
        .select_related("copy", "copy__work", "membership")
        .order_by("due_date", "pk")
    )


def open_loan_count(membership: Membership) -> int:
    """Üyenin (KİŞİNİN) açık ödünç sayısı — Md. 18 sayı sınırı buna uygulanır."""
    return Loan.objects.filter(_person_loans_q(membership.person), status=LoanStatus.OPEN).count()


def overdue_loan_count(membership: Membership, *, on: date | None = None) -> int:
    """Üyenin (KİŞİNİN) gecikmiş açık ödünç sayısı."""
    bugun = on or timezone.localdate()
    return Loan.objects.filter(
        _person_loans_q(membership.person), status=LoanStatus.OPEN, due_date__lt=bugun
    ).count()


def has_overdue(membership: Membership, *, on: date | None = None) -> bool:
    """Üyenin (KİŞİNİN) gecikmiş açık ödüncü var mı? ("Gecikmiş" durum değil, sorgudur.)"""
    return overdue_loan_count(membership, on=on) > 0


def loan_limit(membership: Membership, *, policy: LibraryPolicy | None = None) -> int:
    """Üye türüne göre Md. 18 sayı sınırı; diğer personele ödünç kapalıysa 0.

    Öğrenci 3, öğretmen 5 (politikada daha düşük seçilebilir), diğer personel
    `max_loans_staff` — yalnız müdürlük kararıyla açılmışsa (§9-1, AT-4).
    """
    kural = policy or LibraryPolicy.load()
    tur = membership.member_type
    if tur == MemberType.STUDENT:
        return int(kural.max_loans_student)
    if tur == MemberType.TEACHER:
        return int(kural.max_loans_teacher)
    return int(kural.max_loans_staff) if kural.staff_loans_enabled else 0


def remaining_quota(membership: Membership, *, policy: LibraryPolicy | None = None) -> int:
    """Kalan ödünç hakkı (sınır − kişinin açık ödüncü, en az 0); sonlanmış üyelikte 0.

    Görevli kipinde kart okutulunca ad ile birlikte gösterilen TEK sayıdır
    (§4.4, sözlük §5).
    """
    if not membership.is_active or not membership.person_is_active:
        return 0
    return max(0, loan_limit(membership, policy=policy) - open_loan_count(membership))


def loan_counts_by_person(
    memberships: Iterable[Membership], *, on: date | None = None
) -> dict[PersonKey, tuple[int, int]]:
    """Listelenen üyelerin kişi bazında (açık, gecikmiş) ödünç sayıları — TEK sorgu.

    Liste ekranında satır başına iki sorgu (N+1) yerine kullanılır.
    """
    satirlar = list(memberships)
    ogrenciler = {int(m.student_id) for m in satirlar if m.student_id is not None}
    personel = {int(m.personnel_id) for m in satirlar if m.personnel_id is not None}
    sonuc: dict[PersonKey, tuple[int, int]] = {}
    if not ogrenciler and not personel:
        return sonuc
    bugun = on or timezone.localdate()
    qs = (
        Loan.objects.filter(
            Q(membership__student_id__in=ogrenciler) | Q(membership__personnel_id__in=personel),
            status=LoanStatus.OPEN,
        )
        .values("membership__student_id", "membership__personnel_id")
        .annotate(acik=Count("id"), geciken=Count("id", filter=Q(due_date__lt=bugun)))
    )
    for satir in qs:
        ogrenci_id = satir["membership__student_id"]
        anahtar: PersonKey = (
            ("S", int(ogrenci_id))
            if ogrenci_id is not None
            else ("P", int(satir["membership__personnel_id"]))
        )
        acik, geciken = sonuc.get(anahtar, (0, 0))
        sonuc[anahtar] = (acik + int(satir["acik"]), geciken + int(satir["geciken"]))
    return sonuc


# ---------------------------------------------------------------------------
# Kart okutma ve üye çözme
# ---------------------------------------------------------------------------
class CardLookupState(StrEnum):
    """Kart okutmasının sonucu (§7.3 durum tablosu, "iptal kart" satırı dahil).

    - `FOUND`: numara bir üyeliğe ait (aktif ya da sonlanmış — ayrımı çağıran yapar).
    - `REVOKED`: numara iptal edilmiş (kart yenilendi, birleştirildi ya da silindi).
    - `UNKNOWN`: biçim ve sağlama doğru ama bu programda böyle bir kart yok.
    - `INVALID`: kart biçiminde değil ya da sağlama hanesi tutmuyor (yazım hatası).
    """

    FOUND = "FOUND"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


@dataclass(frozen=True)
class CardLookup:
    state: CardLookupState
    membership: Membership | None = None


def find_membership_by_card(value: object) -> CardLookup:
    """Okutulan kart no'yu üyeliğe çözer — kör indeksle tam eşleşme (T14).

    Sağlama hanesi tutmayan numara veritabanına hiç sorulmaz (`INVALID`): masa
    buna "kart numarası hatalı" diyebilir, numaralandırma denemesi de indeks
    sorgusu üretmez. Anahtar bellekte değilse `KeyMissingError` (kilitliyken
    masa zaten 423 alır).

    **İptal kaydına ÖNCE bakılır.** Birleştirmede sonlanan kaynak üyelik kart
    numarasını korur (kayıt izi) ama kartı iptal edilir; üyelik önce aransaydı eski
    kart "Üyelik sonlanmış" diye okunurdu — oysa kişinin geçerli kartı hedefteki
    üyeliğin kartıdır ve masada "İptal edilmiş kart" denmelidir. Kart yenilemede
    ve silmede numara üyelikte kalmadığı için sıra sonucu değiştirmez.
    """
    if not card_numbers.is_valid_card_no(value):
        return CardLookup(CardLookupState.INVALID)
    indeks = card_no_blind_index(value)
    if CardRevocation.objects.filter(card_no_index=indeks).exists():
        return CardLookup(CardLookupState.REVOKED)
    uyelik = (
        Membership.objects.select_related("student", "personnel")
        .filter(card_no_index=indeks)
        .first()
    )
    if uyelik is not None:
        return CardLookup(CardLookupState.FOUND, uyelik)
    return CardLookup(CardLookupState.UNKNOWN)


def find_active_membership_by_student_number(student_number: str) -> Membership | None:
    """Okul no ile AKTİF öğrencinin AKTİF üyeliği (kartsız ödünç — yönetici kipi, U12).

    Okul no kör indeksle eşleşir (`okul.selectors.find_student_by_number`).
    """
    ogrenci = okul_selectors.find_student_by_number(student_number)
    if ogrenci is None:
        return None
    return active_membership_of(ogrenci)


def active_membership_of(person: Person) -> Membership | None:
    """Kişinin aktif (canlı) üyeliği; yoksa None."""
    return (
        Membership.objects.select_related("student", "personnel")
        .filter(_membership_person_q(person), status=MembershipStatus.ACTIVE)
        .first()
    )


def get_membership(membership_id: int) -> Membership | None:
    return (
        Membership.objects.select_related("student", "personnel").filter(pk=membership_id).first()
    )


def memberships_all() -> QuerySet[Membership]:
    """Canlı üyelikler (ayrıntı uçlarının tek kayıt çözümü)."""
    return Membership.objects.select_related("student", "personnel")


# ---------------------------------------------------------------------------
# Üyelik listesi (yönetici)
# ---------------------------------------------------------------------------
def _membership_sort_key(membership: Membership) -> tuple[Any, ...]:
    """Öğrenciler önce (sınıf → şube → okul no → ad), sonra personel (ad, Türk alfabesi)."""
    if membership.student is not None:
        return (0, okul_selectors.student_sort_key(membership.student), membership.pk)
    kisi = membership.personnel
    ad = kisi.full_name if kisi is not None else ""
    return (1, normalize.tr_sort_key(ad), membership.pk)


def memberships_sorted(rows: Iterable[Membership]) -> list[Membership]:
    """Kullanıcıya gösterilen üyelik sırası — Python'da (ad ve okul no şifrelidir)."""
    return sorted(rows, key=_membership_sort_key)


def _search_matches(
    membership: Membership, needle: str, number_index: str, card_index: str
) -> bool:
    if card_index and membership.card_no_index == card_index:
        return True
    ogrenci = membership.student
    if number_index and ogrenci is not None and ogrenci.student_number_index == number_index:
        return True
    return bool(needle) and needle in normalize_header(membership.full_name)


def memberships(
    *,
    status: str = "",
    member_type: str = "",
    class_level: int | None = None,
    class_section: str = "",
    search: str = "",
) -> list[Membership]:
    """Üyelik listesi (sıralı). Süzgeçler: durum, üye türü, sınıf/şube, arama.

    Arama: ad TR katlamalı (Python); okul no ve kart no kör indeksle TAM eşleşme.
    Üye türü kişiden türediği için süzgeci de kişi alanlarından kurulur.
    """
    qs = Membership.objects.select_related("student", "personnel")
    if status:
        qs = qs.filter(status=status)
    if member_type == MemberType.STUDENT:
        qs = qs.filter(student__isnull=False)
    elif member_type == MemberType.TEACHER:
        qs = qs.filter(personnel__member_kind="TEACHER")
    elif member_type == MemberType.STAFF:
        qs = qs.filter(personnel__member_kind="STAFF")
    if class_level is not None:
        qs = qs.filter(student__class_level=class_level)
    if class_section.strip():
        qs = qs.filter(student__class_section=normalize.tr_upper(class_section.strip()))
    rows: Iterable[Membership] = qs
    if search.strip():
        needle = normalize_header(search)
        number_index = okul_selectors.number_search_index(search)
        card_index = card_no_blind_index(search) if card_numbers.is_valid_card_no(search) else ""
        rows = [m for m in qs if _search_matches(m, needle, number_index, card_index)]
    return memberships_sorted(rows)


# ---------------------------------------------------------------------------
# Üyelik istek listesi (Md. 17/1 — şube bazlı, §9-2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MembershipRequestRow:
    """İstek listesinin bir satırı: şubedeki aktif öğrenci ve (varsa) aktif üyeliği."""

    student: Student
    membership: Membership | None


def membership_request_list(*, class_level: int, class_section: str) -> list[MembershipRequestRow]:
    """Şubedeki AKTİF öğrenciler ve üyelik durumları — sınıf listesi sırasıyla.

    Üyelik isteğe bağlıdır (Md. 17/1): liste kimseyi üye YAPMAZ; yönetici
    üye olmak isteyenleri seçer, toplu açma servisi (`create_memberships_for_students`)
    yalnız seçilenlere üyelik açar.
    """
    ogrenciler = list(
        Student.objects.filter(
            status=StudentStatus.ACTIVE,
            class_level=class_level,
            class_section=normalize.tr_upper(class_section.strip()),
        )
    )
    aktifler = {
        int(m.student_id): m
        for m in Membership.objects.filter(
            student__in=ogrenciler, status=MembershipStatus.ACTIVE
        ).select_related("student")
        if m.student_id is not None
    }
    return [
        MembershipRequestRow(student=o, membership=aktifler.get(o.pk))
        for o in okul_selectors.students_sorted(ogrenciler)
    ]


# ---------------------------------------------------------------------------
# Gecikmiş ödünçler (yönetici — A11; toplu liste ve pano sayısı)
# ---------------------------------------------------------------------------
def overdue_loans(*, on: date | None = None) -> list[Loan]:
    """Gecikmiş açık ödünçler — iade tarihine göre, eşitlikte üye adına göre (TR).

    Liste kişisel veri içerir ve YALNIZ yönetici kipinde açılır (§9-13); basılı
    hâli (E4) dipnot taşır.
    """
    bugun = on or timezone.localdate()
    satirlar = list(
        Loan.objects.filter(status=LoanStatus.OPEN, due_date__lt=bugun).select_related(
            "copy", "copy__work", "membership", "membership__student", "membership__personnel"
        )
    )

    def _anahtar(loan: Loan) -> tuple[Any, ...]:
        uyelik = loan.membership
        sira = _membership_sort_key(uyelik) if uyelik is not None else (2,)
        return (loan.due_date, sira, loan.pk)

    return sorted(satirlar, key=_anahtar)


def overdue_count(*, on: date | None = None) -> int:
    """Gecikmiş açık ödünç SAYISI — kişisiz; pano kartı için (liste yönetici kipinde)."""
    bugun = on or timezone.localdate()
    return Loan.objects.filter(status=LoanStatus.OPEN, due_date__lt=bugun).count()


# ---------------------------------------------------------------------------
# Üyenin ödünç geçmişi (YALNIZ yönetici kipi — profil yasağı modül başlığında)
# ---------------------------------------------------------------------------
def member_loan_history(membership: Membership) -> QuerySet[Loan]:
    """Bir üyeliğin ödünç kayıtları — en yeni önce. Toplama/dağılım YOKTUR.

    Sözlük: "ödünç kaydı", "ödünç geçmişi" — ödünç, üyenin okuma alışkanlığı diye sunulmaz.
    """
    return (
        Loan.objects.filter(membership=membership)
        .select_related("copy", "copy__work")
        .order_by("-loaned_at", "-pk")
    )


# ---------------------------------------------------------------------------
# Beklenmedik kapanış (T15): son oturumdaki ödünç ve iadeler (yalnız yönetici)
# ---------------------------------------------------------------------------
class TransactionKind(StrEnum):
    LOAN = "LOAN"
    RETURN = "RETURN"


#: Son işlemler listesindeki etiketler (Snackbar/kart metni değil, satır türü).
TRANSACTION_LABELS: dict[str, str] = {
    TransactionKind.LOAN: "Ödünç verildi",
    TransactionKind.RETURN: "İade alındı",
}

#: Son işlemler listesinin varsayılan uzunluğu.
RECENT_TRANSACTION_LIMIT = 30

_surec_baslangici: datetime | None = None


def mark_process_start(now: datetime | None = None) -> datetime:
    """Bu sürecin başlangıcını işaretler (bir kez; `KutuphaneConfig.ready`)."""
    global _surec_baslangici
    if _surec_baslangici is None:
        _surec_baslangici = now or timezone.now()
    return _surec_baslangici


def process_started_at() -> datetime:
    """Bu süreç (oturum) ne zaman başladı? İşaret yoksa şimdi işaretlenir."""
    return mark_process_start()


def previous_session_unexpected() -> bool:
    """Önceki oturum beklenmedik biçimde mi kapandı? (masaüstü kabuğunun `KD_ONCEKI_OTURUM`'u)

    Değişken yoksa (geliştirme sunucusu, testler) `False`: kart gösterilmez.
    """
    from desktop.clean_shutdown import PreviousSession, previous_session_from_env

    return previous_session_from_env() is PreviousSession.UNEXPECTED


@dataclass(frozen=True)
class RecentTransaction:
    """Son oturumdan bir işlem: ödünç verme ya da iade (ödünç satırıyla)."""

    kind: str
    at: datetime
    loan: Loan

    @property
    def label(self) -> str:
        return TRANSACTION_LABELS[self.kind]


def recent_transactions(
    *, before: datetime | None = None, limit: int = RECENT_TRANSACTION_LIMIT
) -> list[RecentTransaction]:
    """Bu oturumdan ÖNCEKİ son ödünç ve iadeler — en yeni önce (T15).

    Beklenmedik kapanışta (elektrik kesintisi, zorla sonlandırma) WAL'deki son
    işlemler kaybolmuş olabilir; liste diske YAZILMIŞ son işlemleri gösterir ki
    yönetici masadaki kitaplarla karşılaştırsın. Kişisel veri içerir: yalnız
    yönetici kipinde gösterilir. `before` verilmezse bu sürecin başlangıcıdır.
    """
    sinir = before or process_started_at()
    iliskiler = (
        "copy",
        "copy__work",
        "membership",
        "membership__student",
        "membership__personnel",
    )
    verilen = list(
        Loan.objects.filter(loaned_at__lt=sinir)
        .select_related(*iliskiler)
        .order_by("-loaned_at", "-pk")[:limit]
    )
    alinan = list(
        Loan.objects.filter(returned_at__isnull=False, returned_at__lt=sinir)
        .select_related(*iliskiler)
        .order_by("-returned_at", "-pk")[:limit]
    )
    islemler = [RecentTransaction(TransactionKind.LOAN, lo.loaned_at, lo) for lo in verilen]
    islemler += [
        RecentTransaction(TransactionKind.RETURN, lo.returned_at, lo)
        for lo in alinan
        if lo.returned_at is not None
    ]
    islemler.sort(key=lambda islem: (islem.at, islem.loan.pk), reverse=True)
    return islemler[:limit]
