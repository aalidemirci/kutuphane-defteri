"""Üyelik ve üye kartı iş mantığı (tasarım §6.2, §7.1, §9-1/2/8; D12, D21).

OYS'nin üyelik yollarından UYARLA (tasarım §12): rol/izin dalları, `by_user` ve
denetim kaydı düştü; `CardCounter` (yıl bazlı SIRALI kart numarası — D21)
KALDIRILDI. Yazma yolları ve işlem sınırı buradadır; okuma `selectors_dolasim`'da.

**Üyelik isteğe bağlıdır** (Md. 17/1 "üye olmak isteyen"): öğrenci ya da
personel kaydı açmak, e-Okul aktarımı ya da sınıf atlaması kimseyi üye YAPMAZ.
Öğrencide şube bazlı istek listesinden toplu (`create_memberships_for_students`),
personelde tek tek (`create_membership`) açılır. Diğer personele üyelik yalnız
müdürlük kararıyla ödünç seçeneği açıksa açılır (§9-1, AT-4).

**Kart no** (§7.1, D21): `9` + 6 rastgele hane + Luhn sağlaması
(`card_numbers`). Yeni numara `IssuedCard`'a (verilmiş bütün numaraların
kişisiz kör indeksi) karşı denetlenir ve oraya yazılır: **numara asla yeniden
kullanılmaz** — üyelik katı silinse, kart yenilense, kişi anonimleştirilse de.
Yedekten geri yükleme `IssuedCard`'ı da geri sardığı için indeks ayrıca veri
dizinindeki verilmiş kart defterine yazılır ve ona karşı da denetlenir
(`card_ledger`).

**Kartı yenile** (§4.4): yalnız yönetici kipinde. Eski numaranın kör indeksi
`CardRevocation`'a yazılır (okutulunca "iptal edilmiş kart"); yeni numara
verilir, kart basım işareti boşalır (kart kuyruğa döner); açık ödünçler
üyelikte kalır.

**Sonlandırma** (D12): neden KAPALI LİSTEDENDİR ve zorunludur (DB kısıtı da).
Elle sonlandırmada açık ödünç varsa ret: önce iade alınır. Ayrılışta (kanca)
açık ödünç olsa da üyelik sonlanır; ödünç kişinin açık yükümlülüğü olarak
kalır ve ilişik listesine düşer (§9-8, F7). Sonlanmış üye iade yapabilir.

**Kişi kayıt defterleri** (`apps.okul.services.persons`): bu modül dört
kancayı `register_person_hooks()` ile kaydeder (`KutuphaneConfig.ready`):
açık ödünç = açık yükümlülük; "hiç üye olmuş mu"; ayrılışta üyeliği
sonlandır; personel birleştirmede üyelik ve ödünçleri taşı. Kancalar kişinin
durum değişikliğiyle AYNI işlemde koşar ve yalnız veritabanına yazar. Hata ve
günlük metinleri KİŞİ ADI İÇERMEZ.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.kutuphane import card_ledger, card_numbers
from apps.kutuphane.models import (
    MANUAL_TERMINATION_REASONS,
    CardRevocation,
    CardRevocationReason,
    IssuedCard,
    LibraryPolicy,
    Loan,
    LoanStatus,
    LossDamageCase,
    Membership,
    MembershipStatus,
    TerminationReason,
    card_no_blind_index,
)
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul.models import MemberKind, Personnel, Student, StudentStatus
from apps.okul.services import app_password, persons

logger = logging.getLogger("kutuphane_defteri.kutuphane")

type Person = Student | Personnel

#: Rastgele numara denemesinin üst sınırı. 1.000.000'luk uzayda okulun verdiği
#: birkaç bin numara varken art arda 64 çakışma olasılığı pratikte sıfırdır;
#: sınır yalnız sonsuz döngüye karşı sigortadır.
MAX_CARD_TRIES = 64

PERSON_REQUIRED_MESSAGE = "Üyelik için bir öğrenci ya da bir personel seçin."
ALREADY_MEMBER_MESSAGE = "Bu kişinin aktif üyeliği var."
PERSON_LEFT_MESSAGE = "Ayrılmış kişiye üyelik açılamaz."
PERSON_MISSING_MESSAGE = "Kişi kaydı bulunamadı."
STAFF_MEMBERSHIP_OFF_MESSAGE = (
    "Diğer personele ödünç Kütüphane Politikası'nda açık değil. Seçenek müdürlük "
    "kararıyla açılmadan diğer personele üyelik açılmaz."
)
REQUESTED_IN_FUTURE_MESSAGE = "Üyelik isteği tarihi bugünden sonra olamaz."
REQUEST_EMPTY_MESSAGE = "Üye yapılacak öğrenci seçilmedi."
REQUEST_STALE_MESSAGE = (
    "Seçilen öğrencilerden bazıları artık üye yapılamaz (zaten üye, ayrılmış ya da "
    "kaydı silinmiş). Listeyi yenileyip yeniden seçin; hiçbir üyelik açılmadı."
)
CARD_EXHAUSTED_MESSAGE = "Yeni kart numarası üretilemedi. İşlemi yeniden deneyin."
RENEW_TERMINATED_MESSAGE = "Sonlanmış üyeliğin kartı yenilenemez."
TERMINATE_REASON_MESSAGE = "Sonlandırma nedenini listeden seçin."
ALREADY_TERMINATED_MESSAGE = "Bu üyelik zaten sonlanmış."
TERMINATE_OPEN_LOANS_MESSAGE = (
    "Açık ödüncü olan üyelik sonlandırılamaz. Önce iade alın; üye okuldan ayrıldıysa "
    "Kişiler ekranında “Ayrıldı olarak işaretle” eylemini kullanın."
)
DELETE_HAS_CASES_MESSAGE = (
    "Kayıp/hasar dosyası olan üyelik silinemez. Üyelik yanlış açıldıysa “Yanlış kayıt” "
    "nedeniyle sonlandırın."
)
DELETE_HAS_LOANS_MESSAGE = (
    "Ödünç kaydı olan üyelik silinemez. Üyelik yanlış açıldıysa “Yanlış kayıt” "
    "nedeniyle sonlandırın."
)


# ---------------------------------------------------------------------------
# Kart numarası
# ---------------------------------------------------------------------------
def issue_card_number() -> str:
    """Hiç verilmemiş yeni bir kart no üretir ve `IssuedCard`'a yazar (çağıranın işleminde).

    Rastgele gövde `card_numbers.random_body`'den gelir (testler çakışma
    senaryosu için değiştirir). Numaranın kör indeksi `IssuedCard`'da ya da
    veri dizinindeki verilmiş kart defterinde (`card_ledger` — yedekten geri
    yükleme onu geri sarmaz) varsa — üyeliği silinmiş, yenilenmiş, hâlâ kullanımda
    ya da geri yüklemede kaybolmuş olsun — numara atılır ve yenisi çekilir.
    `IssuedCard.card_no_index` teklik kısıtı son savunmadır.
    """
    defter = card_ledger.issued_indexes()
    for _ in range(MAX_CARD_TRIES):
        kart = card_numbers.build_card_no(card_numbers.random_body())
        indeks = card_no_blind_index(kart)
        if indeks in defter or IssuedCard.objects.filter(card_no_index=indeks).exists():
            continue
        IssuedCard.objects.create(card_no_index=indeks)
        card_ledger.record(indeks)
        return kart
    raise ValidationError(CARD_EXHAUSTED_MESSAGE)


def _revoke_card(
    card_no_index: str, *, membership: Membership | None, reason: str
) -> CardRevocation:
    """Kartı iptal edilmişler tablosuna yazar (fikirdeş: aynı numara ikinci kez yazılmaz)."""
    kayit, _ = CardRevocation.objects.get_or_create(
        card_no_index=card_no_index,
        defaults={"membership": membership, "reason": reason},
    )
    return kayit


# ---------------------------------------------------------------------------
# Üyelik açma
# ---------------------------------------------------------------------------
def _person_q(person: Person) -> Q:
    return Q(student=person) if isinstance(person, Student) else Q(personnel=person)


def _ensure_person_can_join(person: Person, *, policy: LibraryPolicy) -> None:
    """Kişi canlı ve aktif mi, aktif üyeliği yok mu, diğer personelde karar var mı?"""
    if person.deleted_at is not None:
        raise ValidationError(PERSON_MISSING_MESSAGE)
    aktif = (
        person.status == StudentStatus.ACTIVE if isinstance(person, Student) else person.is_active
    )
    if not aktif:
        raise ValidationError(PERSON_LEFT_MESSAGE)
    if Membership.objects.filter(_person_q(person), status=MembershipStatus.ACTIVE).exists():
        raise ValidationError(ALREADY_MEMBER_MESSAGE)
    if (
        isinstance(person, Personnel)
        and person.member_kind == MemberKind.STAFF
        and not policy.staff_loans_enabled
    ):
        raise ValidationError(STAFF_MEMBERSHIP_OFF_MESSAGE)


@transaction.atomic
def create_membership(
    *,
    student: Student | None = None,
    personnel: Personnel | None = None,
    requested_at: date | None = None,
) -> Membership:
    """Tek kişiye üyelik açar (personelde olağan yol); yeni kart no verir.

    `requested_at`: üyelik isteğinin tarihi (Md. 17/1; varsayılan bugün,
    gelecekte olamaz). Başlangıç tarihi bugündür.
    """
    app_password.require_password_set()
    kisi: Person | None = student if student is not None else personnel
    if kisi is None or (student is not None and personnel is not None):
        raise ValidationError(PERSON_REQUIRED_MESSAGE)
    bugun = timezone.localdate()
    istek = requested_at or bugun
    if istek > bugun:
        raise ValidationError({"requested_at": [REQUESTED_IN_FUTURE_MESSAGE]})
    _ensure_person_can_join(kisi, policy=LibraryPolicy.load())
    uyelik = Membership(
        student=student,
        personnel=personnel,
        card_no=issue_card_number(),
        requested_at=istek,
        started_at=bugun,
    )
    uyelik.save()
    return uyelik


@transaction.atomic
def create_memberships_for_students(
    student_ids: Sequence[int], *, requested_at: date | None = None
) -> list[Membership]:
    """Üyelik istek listesi (§9-2): seçilen öğrencilere TEK işlemde üyelik açar.

    Ya hepsi ya hiçbiri: seçilenlerden biri artık aktif değilse, silinmişse ya
    da zaten üyeyse (başka pencerede işlenmiş) hiçbir üyelik açılmaz ve
    kullanıcı listeyi yenilemeye çağrılır (ayrılış havuzu kararıyla aynı kural).
    Üyelikler seçim sırasıyla açılır. Günlüğe yalnız sayı yazılır.
    """
    app_password.require_password_set()
    kimlikler = list(dict.fromkeys(int(i) for i in student_ids))
    if not kimlikler:
        raise ValidationError(REQUEST_EMPTY_MESSAGE)
    ogrenciler = {
        s.pk: s for s in Student.objects.filter(pk__in=kimlikler, status=StudentStatus.ACTIVE)
    }
    zaten_uye = Membership.objects.filter(
        student_id__in=kimlikler, status=MembershipStatus.ACTIVE
    ).exists()
    if len(ogrenciler) != len(kimlikler) or zaten_uye:
        raise ValidationError(REQUEST_STALE_MESSAGE)
    acilan = [
        create_membership(student=ogrenciler[i], requested_at=requested_at) for i in kimlikler
    ]
    logger.info("Üyelik istek listesinden %d üyelik açıldı.", len(acilan))
    return acilan


# ---------------------------------------------------------------------------
# Kartı yenile, sonlandır, sil
# ---------------------------------------------------------------------------
@transaction.atomic
def renew_card(membership: Membership) -> Membership:
    """Kartı yenile (yalnız yönetici kipi): yeni no, eski no iptal; açık ödünçler kalır."""
    require_admin_mode()
    app_password.require_password_set()
    if not membership.is_active:
        raise ValidationError(RENEW_TERMINATED_MESSAGE)
    _revoke_card(
        membership.card_no_index, membership=membership, reason=CardRevocationReason.RENEWED
    )
    membership.card_no = issue_card_number()
    membership.card_printed_at = None
    membership.save(update_fields=["card_no", "card_printed_at", "updated_at"])
    logger.info("Üye kartı yenilendi; eski kart iptal edildi.")
    return membership


def _terminate(membership: Membership, *, reason: str, on: date | None = None) -> Membership:
    membership.status = MembershipStatus.TERMINATED
    membership.terminated_at = on or timezone.localdate()
    membership.termination_reason = reason
    membership.save(update_fields=["status", "terminated_at", "termination_reason", "updated_at"])
    return membership


@transaction.atomic
def terminate_membership(membership: Membership, *, reason: str) -> Membership:
    """Üyeliği elle sonlandırır — neden kapalı listeden ve zorunlu (D12).

    Elle seçilebilen nedenler `MANUAL_TERMINATION_REASONS`'tır; "Okuldan
    ayrıldı" ayrılış yolunun, "Kişi kayıtları birleştirildi" birleştirmenin
    işidir. Açık ödüncü olan üyelik elle sonlandırılamaz.
    """
    app_password.require_password_set()
    if reason not in MANUAL_TERMINATION_REASONS:
        raise ValidationError({"reason": [TERMINATE_REASON_MESSAGE]})
    if not membership.is_active:
        raise ValidationError(ALREADY_TERMINATED_MESSAGE)
    if Loan.objects.filter(membership=membership, status=LoanStatus.OPEN).exists():
        raise ValidationError(TERMINATE_OPEN_LOANS_MESSAGE)
    _terminate(membership, reason=reason)
    logger.info("Üyelik elle sonlandırıldı.")
    return membership


@transaction.atomic
def delete_membership(membership: Membership) -> None:
    """Yanlış açılan, hiç ödünç kaydı olmayan üyeliği KATI siler; kartı iptal edilir.

    Kart basılıp verilmiş olabilir: okutulduğunda "tanınmayan" değil "iptal
    edilmiş kart" denmesi için numara `CardRevocation`'a yazılır. Numara
    `IssuedCard`'da kalır — asla yeniden verilmez. Ödünç kaydı olan üyelik
    silinmez (sonlandırılır).
    """
    app_password.require_password_set()
    if Loan.all_objects.filter(membership=membership).exists():
        raise ValidationError(DELETE_HAS_LOANS_MESSAGE)
    if LossDamageCase.all_objects.filter(membership=membership).exists():
        # F7: silme, dosyanın sorumlu bağını SET_NULL ile sessizce koparırdı.
        raise ValidationError(DELETE_HAS_CASES_MESSAGE)
    _revoke_card(membership.card_no_index, membership=None, reason=CardRevocationReason.DELETED)
    membership.hard_delete()
    logger.info("Yanlış açılan üyelik silindi; kartı iptal edildi.")


# ---------------------------------------------------------------------------
# Kişi kayıt defterlerine kaydolan kancalar (apps.okul.services.persons)
# ---------------------------------------------------------------------------
def open_loan_obligations(person: Person) -> list[str]:
    """Açık yükümlülük denetimi: kişinin (bütün üyeliklerinde) açık ödüncü.

    Gerekçe KİŞİ ADI İÇERMEZ (hata metnine ve günlüğe ad yazılmaz — sözlük §5).
    """
    lookup = (
        Q(membership__student=person)
        if isinstance(person, Student)
        else Q(membership__personnel=person)
    )
    sayi = Loan.objects.filter(lookup, status=LoanStatus.OPEN).count()
    return [f"{sayi} açık ödünç var."] if sayi else []


def was_ever_member(person: Person) -> bool:
    """Üyelik denetimi: kişi hiç kütüphane üyesi olmuş mu (silinmişler dahil)?"""
    return Membership.all_objects.filter(_person_q(person)).exists()


def terminate_on_leave(person: Person) -> None:
    """Ayrılış kancası (§9-8): kişinin aktif üyeliği "Okuldan ayrıldı" ile sonlanır.

    Açık ödünçler üyelikte kalır: kişinin açık yükümlülüğüdür, ilişik listesine
    düşer (F7). Sonlanmış üye iade yapabilir.
    """
    for uyelik in Membership.objects.filter(_person_q(person), status=MembershipStatus.ACTIVE):
        _terminate(uyelik, reason=TerminationReason.LEFT_SCHOOL)


def move_on_merge(source: Personnel, target: Personnel) -> None:
    """Birleştirme kancası: kaynağın üyelik ve ödünçleri hedefe taşınır (§8.3).

    Tipik kullanım soyadı değişimidir. Kaynağın BÜTÜN üyelikleri (sonlanmışlar
    ve silinmişler dahil) hedefe bağlanır; aksi hâlde kaynağın katı silinmesi
    PROTECT bağında durur. Hedefin zaten aktif üyeliği varsa kaynağın aktif
    üyeliğindeki AÇIK ödünçler hedefin aktif üyeliğine geçer, kaynak üyelik
    "Kişi kayıtları birleştirildi" nedeniyle sonlanır ve kartı iptal edilir
    (kişinin tek geçerli kartı hedefin kartıdır). Hedef ayrılmışsa taşınan
    aktif üyelik "Okuldan ayrıldı" ile sonlanır. Sayı sınırını aşan açık
    ödünçler geri çevrilmez; yeni ödünç iadeye kadar verilmez.
    """
    hedef_aktif = Membership.objects.filter(
        personnel=target, status=MembershipStatus.ACTIVE
    ).first()
    for uyelik in Membership.all_objects.filter(personnel=source).order_by("pk"):
        alanlar = ["personnel", "updated_at"]
        if uyelik.status == MembershipStatus.ACTIVE and uyelik.deleted_at is None:
            if hedef_aktif is not None:
                Loan.all_objects.filter(membership=uyelik, status=LoanStatus.OPEN).update(
                    membership=hedef_aktif, updated_at=timezone.now()
                )
                _revoke_card(
                    uyelik.card_no_index,
                    membership=uyelik,
                    reason=CardRevocationReason.MERGED,
                )
                uyelik.status = MembershipStatus.TERMINATED
                uyelik.terminated_at = timezone.localdate()
                uyelik.termination_reason = TerminationReason.MERGED
                alanlar += ["status", "terminated_at", "termination_reason"]
            elif not target.is_active:
                uyelik.status = MembershipStatus.TERMINATED
                uyelik.terminated_at = timezone.localdate()
                uyelik.termination_reason = TerminationReason.LEFT_SCHOOL
                alanlar += ["status", "terminated_at", "termination_reason"]
        uyelik.personnel = target
        uyelik.save(update_fields=alanlar)


def register_person_hooks() -> None:
    """Dört kancayı kişi kayıt defterlerine kaydeder (fikirdeş — `AppConfig.ready`)."""
    persons.register_obligation_check(open_loan_obligations)
    persons.register_membership_check(was_ever_member)
    persons.register_leave_hook(terminate_on_leave)
    persons.register_merge_hook(move_on_merge)
