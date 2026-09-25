"""İlişik listesi ve yıl sonu toplamasının salt okuma sorguları (F7 — tasarım §8.3, §9-8, §10 E5).

**İlişik listesi** kütüphaneyle açık işi olan kişilerdir: iade edilmemiş ödünç,
geri alınmamış teslim (yalnız öğretmen — şube teslimi kişisizdir) ve kişinin açık
işi olan kayıp/hasar dosyası (`PERSON_OPEN_RESOLUTIONS`: "Çözüm bekliyor", "Bedel
belirlendi"). **"Bedel teslim alındı"** dosyası okul için açıktır ama kişiye
YAZILMAZ: kişi listeden çıkar ve E5 basılabilir (25.09.2026 kullanıcı kararı; Md.
19/1'in "kaynak bedeli ile … satın alınır" cümlesi okulun işidir). Okuldan
AYRILMIŞ kişiler de listededir (§9-8: "açık ödünç ve teslim ilişik listesine
düşer"; kayıt silinmez). Liste yalnız yönetici kipinde açılır (§4.4 "ilişik" kapalı sütunda; uçlar görevli
izin listesinde DEĞİLDİR).

**Sıra** (§8.3): son sınıflar ve nakil gidenler ÖNCE.

- `graduating` — son sınıf: kademenin son sınıfındaki (4 · 8 · 12 —
  `circulation.GRADUATING_LEVEL`) AKTİF öğrenci. Kademe seçilmemişse kimse son
  sınıf sayılmaz.
- `leaving` — ayrılan: okuldan ayrılmış (öğrencide LEFT, personelde aktif değil)
  ya da ayrılış havuzunda karar bekleyen kişi. Programda nakil ile başka ayrılış
  ayrı tutulmaz; e-Okul listesinden düşen öğrenci havuza, kararla "Ayrıldı"ya geçer.
- `other` — öbürleri.

Grup içinde öğrenciler (sınıf → şube → okul no → ad), sonra personel (ad, Türk
alfabesi). Ad ve okul no ŞİFRELİDİR: sıralama ve ad araması Python'dadır, okul no
araması kör indeksle TAM eşleşmedir (T14, CLAUDE.md §3).

**Şube teslimleri** (sınıf kitaplığı) kişiye bağlı değildir; ilişik listesinde
kişilerden AYRI gösterilir (`section_delivery_rows`): son sınıf şubeleri önce.

**Profil yasağı** (CLAUDE.md §2-5): satırlar yalnız nüsha, kaynak adı, tarih ve
durum taşır; kişi bazında konu ya da bölüm dağılımı üretilmez. Kaynak adı ekranda
yöneticiye görünür; basılı ilişik listesine yalnız barkod ve belge no girer
(`ilisik_belgeleri`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

from django.db.models import Q
from django.utils import timezone

from apps.kutuphane import selectors_teslim
from apps.kutuphane.models import (
    PERSON_OPEN_RESOLUTIONS,
    Delivery,
    DeliveryStatus,
    Loan,
    LoanStatus,
    LossDamageCase,
)
from apps.kutuphane.services.circulation import GRADUATING_LEVEL
from apps.okul import normalize
from apps.okul import selectors as okul_selectors
from apps.okul.excel_ogrenci import normalize_header
from apps.okul.models import (
    ClassSection,
    MemberKind,
    Personnel,
    SchoolConfig,
    Student,
    StudentStatus,
)

type Person = Student | Personnel
#: Kişi anahtarı: ('S', öğrenci pk) ya da ('P', personel pk) — `selectors_dolasim.PersonKey`.
type PersonKey = tuple[str, int]

GROUP_GRADUATING: Final = "graduating"
GROUP_LEAVING: Final = "leaving"
GROUP_OTHER: Final = "other"
GROUPS: Final = (GROUP_GRADUATING, GROUP_LEAVING, GROUP_OTHER)
#: Yalnız SÜZGEÇ değeri: son sınıflar VE ayrılanlar (yıl sonu akışının 3. adımı).
GROUP_PRIORITY: Final = "priority"
GROUP_FILTERS: Final = (*GROUPS, GROUP_PRIORITY)
#: Liste sırası: son sınıflar, sonra ayrılanlar (nakil gidenler), sonra öbürleri.
GROUP_ORDER: Final[dict[str, int]] = {GROUP_GRADUATING: 0, GROUP_LEAVING: 1, GROUP_OTHER: 2}
#: Kullanıcıya görünen grup adları (rozet ve belge "Durum" sütunu).
GROUP_LABELS: Final[dict[str, str]] = {
    GROUP_GRADUATING: "Son sınıf",
    GROUP_LEAVING: "Okuldan ayrılan",
    GROUP_OTHER: "",
}

#: Liste durumu süzgeci: açık işi olanlar (ilişik listesi) · olmayanlar · hepsi.
STATE_OPEN: Final = "open"
STATE_CLEAR: Final = "clear"
STATE_ALL: Final = "all"
STATES: Final = (STATE_OPEN, STATE_CLEAR, STATE_ALL)

#: Yükümlülük süzgeci: hepsi · yalnız toplanacak kitap (ödünç ya da öğretmene teslim).
OBLIGATION_ALL: Final = "all"
OBLIGATION_COLLECT: Final = "collect"
OBLIGATIONS: Final = (OBLIGATION_ALL, OBLIGATION_COLLECT)

#: Silinmiş kişi kaydının adı yerine gösterilen metin (`dolasim_belgeleri.SILINMIS_KISI`).
SILINMIS_KISI: Final = "Kaydı silinmiş kişi"
LEAVE_POOL_LABEL: Final = "Ayrılış kararı bekliyor"


# ---------------------------------------------------------------------------
# Satır
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClearanceRow:
    """Bir kişinin kütüphaneyle açık işleri (boşsa ilişiği yoktur)."""

    person: Person
    group: str
    is_graduating: bool
    loans: tuple[Loan, ...] = ()
    deliveries: tuple[Delivery, ...] = ()
    cases: tuple[LossDamageCase, ...] = ()

    @property
    def is_student(self) -> bool:
        return isinstance(self.person, Student)

    @property
    def person_type(self) -> str:
        return "student" if self.is_student else "personnel"

    @property
    def person_id(self) -> int:
        return int(self.person.pk)

    @property
    def key(self) -> PersonKey:
        return ("S" if self.is_student else "P", self.person_id)

    @property
    def is_clear(self) -> bool:
        return not (self.loans or self.deliveries or self.cases)

    @property
    def full_name(self) -> str:
        if self.person.deleted_at is not None:
            return SILINMIS_KISI
        return " ".join(self.person.full_name.split())

    @property
    def person_label(self) -> str:
        """Öğrencide sınıf/şube ('12/A'), personelde üye türü ('Öğretmen')."""
        if isinstance(self.person, Student):
            return self.person.class_label
        return member_kind_text(self.person)

    @property
    def student_number(self) -> str:
        if isinstance(self.person, Student) and self.person.deleted_at is None:
            return str(self.person.student_number)
        return ""

    @property
    def left_at(self) -> date | None:
        return self.person.left_at

    @property
    def in_leave_pool(self) -> bool:
        return self.person.leave_candidate_since is not None

    @property
    def status_text(self) -> str:
        """Rozet metni (sözlük): 'Son sınıf' · 'Ayrıldı · gg.aa.yyyy' · 'Ayrılış kararı bekliyor'."""
        if self.left_at is not None and not _is_active(self.person):
            return f"Ayrıldı · {self.left_at:%d.%m.%Y}"
        if not _is_active(self.person):
            return "Ayrıldı"
        if self.in_leave_pool:
            return LEAVE_POOL_LABEL
        return GROUP_LABELS[GROUP_GRADUATING] if self.is_graduating else ""

    def overdue_count(self, on: date | None = None) -> int:
        gun = on or timezone.localdate()
        return sum(1 for lo in self.loans if lo.due_date < gun)


@dataclass(frozen=True)
class SectionDeliveryRow:
    """Bir şubenin (sınıf kitaplığının) açık teslimleri — kişisiz."""

    section: ClassSection
    is_graduating: bool
    is_active_year: bool
    deliveries: tuple[Delivery, ...]
    cases: tuple[LossDamageCase, ...] = field(default=())

    @property
    def label(self) -> str:
        return self.section.class_label

    @property
    def school_year_name(self) -> str:
        yil = self.section.school_year
        return yil.name if yil is not None else ""

    @property
    def document_numbers(self) -> list[str]:
        """Açık teslimlerin belge no'ları (E15) — ilk görülme sırasıyla, tekrarsız."""
        return list(dict.fromkeys(d.document_no for d in self.deliveries))


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def member_kind_text(person: Personnel) -> str:
    """'Öğretmen' / 'Diğer personel' (sözlük; ilk harf büyük)."""
    return "Diğer personel" if person.member_kind == MemberKind.STAFF else "Öğretmen"


def graduating_level() -> int | None:
    """Kademenin son sınıfı (4 · 8 · 12); kademe seçilmemişse None."""
    return GRADUATING_LEVEL.get(SchoolConfig.load().kademe)


def _is_active(person: Person) -> bool:
    if person.deleted_at is not None:
        return False
    if isinstance(person, Student):
        return person.status == StudentStatus.ACTIVE
    return bool(person.is_active)


def is_graduating(person: Person, level: int | None) -> bool:
    """Son sınıf: kademenin son sınıfındaki AKTİF öğrenci."""
    return (
        level is not None
        and isinstance(person, Student)
        and _is_active(person)
        and person.class_level == level
    )


def person_group(person: Person, level: int | None) -> str:
    """Kişinin liste grubu: ayrılan (ayrılmış ya da havuzda) · son sınıf · öbürleri."""
    if not _is_active(person) or person.leave_candidate_since is not None:
        return GROUP_LEAVING
    if is_graduating(person, level):
        return GROUP_GRADUATING
    return GROUP_OTHER


def _key(person: Person) -> PersonKey:
    return ("S" if isinstance(person, Student) else "P", int(person.pk))


def _person_sort_key(person: Person) -> tuple[Any, ...]:
    if isinstance(person, Student):
        return (0, okul_selectors.student_sort_key(person))
    return (1, normalize.tr_sort_key(person.full_name), person.pk)


def row_sort_key(row: ClearanceRow) -> tuple[Any, ...]:
    """Liste sırası: grup (son sınıf → ayrılan → öbürleri), sonra kişi sırası."""
    return (GROUP_ORDER[row.group], _person_sort_key(row.person))


# ---------------------------------------------------------------------------
# Açık işler — toplu (her tür için TEK sorgu)
# ---------------------------------------------------------------------------
@dataclass
class _Isler:
    loans: list[Loan] = field(default_factory=list)
    deliveries: list[Delivery] = field(default_factory=list)
    cases: list[LossDamageCase] = field(default_factory=list)


def _loan_key(loan: Loan) -> PersonKey | None:
    uyelik = loan.membership
    if uyelik is None:
        return None
    if uyelik.student_id is not None:
        return ("S", int(uyelik.student_id))
    if uyelik.personnel_id is not None:
        return ("P", int(uyelik.personnel_id))
    return None


def _case_key(case: LossDamageCase) -> PersonKey | None:
    """Dosyanın kişi anahtarı — `selectors_teslim.case_person` ile AYNI kural (önce üyelik)."""
    uyelik = case.membership
    if uyelik is not None:
        if uyelik.student_id is not None:
            return ("S", int(uyelik.student_id))
        if uyelik.personnel_id is not None:
            return ("P", int(uyelik.personnel_id))
    teslim = case.delivery
    if teslim is not None and teslim.personnel_id is not None:
        return ("P", int(teslim.personnel_id))
    return None


def open_obligations_by_person() -> dict[PersonKey, _Isler]:
    """Açık ödünç, öğretmene açık teslim ve kişinin açık işi olan dosyalar — kişi anahtarına göre.

    Üç sorgu; kişi kaydına bağı kopmuş (anonimleştirilmiş) kayıt kimseye yazılmaz.
    Bedeli teslim alınmış dosya kişiye yazılmaz (`PERSON_OPEN_RESOLUTIONS`).
    """
    isler: dict[PersonKey, _Isler] = {}
    for lo in Loan.objects.filter(status=LoanStatus.OPEN, membership__isnull=False).select_related(
        "copy", "copy__work", "membership"
    ):
        anahtar = _loan_key(lo)
        if anahtar is not None:
            isler.setdefault(anahtar, _Isler()).loans.append(lo)
    for teslim in Delivery.objects.filter(
        status=DeliveryStatus.OPEN, personnel__isnull=False
    ).select_related("copy", "copy__work"):
        isler.setdefault(("P", int(teslim.personnel_id or 0)), _Isler()).deliveries.append(teslim)
    for dosya in LossDamageCase.objects.filter(
        resolution__in=PERSON_OPEN_RESOLUTIONS
    ).select_related("copy", "copy__work", "membership", "delivery"):
        anahtar = _case_key(dosya)
        if anahtar is not None:
            isler.setdefault(anahtar, _Isler()).cases.append(dosya)
    return isler


def _row(person: Person, isler: _Isler | None, level: int | None) -> ClearanceRow:
    bos = _Isler()
    kayit = isler or bos
    return ClearanceRow(
        person=person,
        group=person_group(person, level),
        is_graduating=is_graduating(person, level),
        loans=tuple(sorted(kayit.loans, key=lambda lo: (lo.due_date, lo.pk))),
        deliveries=tuple(sorted(kayit.deliveries, key=lambda d: (d.delivered_on, d.pk))),
        cases=tuple(sorted(kayit.cases, key=lambda c: (c.reported_on, c.pk))),
    )


#: Grup hesabı için yeterli düz alanlar — şifreli ad ve okul no ÇÖZÜLMEZ (sayılar).
_OGRENCI_DURUM_ALANLARI: Final = (
    "pk",
    "status",
    "class_level",
    "class_section",
    "left_at",
    "leave_candidate_since",
    "deleted_at",
)
_PERSONEL_DURUM_ALANLARI: Final = (
    "pk",
    "is_active",
    "member_kind",
    "left_at",
    "leave_candidate_since",
    "deleted_at",
)


def _persons_by_key(
    keys: Iterable[PersonKey], *, yalniz_durum: bool = False
) -> dict[PersonKey, Person]:
    """Anahtarlardaki kişiler — silinmişler DAHİL (açık işi olan kişi silinemez; savunma).

    `yalniz_durum`: yalnız grup hesabının düz alanları okunur (sayılar için; ad
    çözülmez).
    """
    anahtarlar = list(keys)
    ogrenci = [pk for tur, pk in anahtarlar if tur == "S"]
    personel = [pk for tur, pk in anahtarlar if tur == "P"]
    ogrenci_qs = Student.all_objects.filter(pk__in=ogrenci)
    personel_qs = Personnel.all_objects.filter(pk__in=personel)
    if yalniz_durum:
        ogrenci_qs = ogrenci_qs.only(*_OGRENCI_DURUM_ALANLARI)
        personel_qs = personel_qs.only(*_PERSONEL_DURUM_ALANLARI)
    kisiler: dict[PersonKey, Person] = {}
    for o in ogrenci_qs:
        kisiler[("S", int(o.pk))] = o
    for p in personel_qs:
        kisiler[("P", int(p.pk))] = p
    return kisiler


# ---------------------------------------------------------------------------
# Süzgeçler
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClearanceFilter:
    """Liste süzgeci (uç parametreleriyle birebir)."""

    state: str = STATE_OPEN
    group: str = ""
    class_level: int | None = None
    class_section: str = ""
    search: str = ""
    obligation: str = OBLIGATION_ALL
    person_type: str = ""

    @property
    def sube(self) -> str:
        return normalize.tr_upper(self.class_section.strip())


def _matches(row: ClearanceRow, filtre: ClearanceFilter, needle: str, number_index: str) -> bool:
    if filtre.group == GROUP_PRIORITY:
        if row.group not in (GROUP_GRADUATING, GROUP_LEAVING):
            return False
    elif filtre.group and row.group != filtre.group:
        return False
    if filtre.person_type and row.person_type != filtre.person_type:
        return False
    if filtre.class_level is not None or filtre.sube:
        kisi = row.person
        if not isinstance(kisi, Student):
            return False
        if filtre.class_level is not None and kisi.class_level != filtre.class_level:
            return False
        if filtre.sube and kisi.class_section != filtre.sube:
            return False
    if filtre.obligation == OBLIGATION_COLLECT and not (row.loans or row.deliveries):
        return False
    if needle or number_index:
        kisi = row.person
        numara_tutar = bool(
            number_index and isinstance(kisi, Student) and kisi.student_number_index == number_index
        )
        ad_tutar = bool(needle) and needle in normalize_header(kisi.full_name)
        if not (numara_tutar or ad_tutar):
            return False
    return True


def _candidates(filtre: ClearanceFilter) -> list[Person]:
    """Açık işi OLMAYAN kişiler için aday havuzu: canlı öğrenci ve personel (ayrılmışlar dahil).

    Şube süzgecinde personel aday değildir; DB'de süzülebilen alanlar burada süzülür.
    """
    ogrenciler = Student.objects.all()
    if filtre.class_level is not None:
        ogrenciler = ogrenciler.filter(class_level=filtre.class_level)
    if filtre.sube:
        ogrenciler = ogrenciler.filter(class_section=filtre.sube)
    adaylar: list[Person] = []
    if filtre.person_type in ("", "student"):
        adaylar.extend(ogrenciler)
    if (
        filtre.person_type in ("", "personnel")
        and filtre.class_level is None
        and not filtre.sube
        and filtre.group != GROUP_GRADUATING
    ):
        adaylar.extend(Personnel.objects.all())
    return adaylar


def clearance_rows(filtre: ClearanceFilter | None = None) -> list[ClearanceRow]:
    """İlişik listesi (varsayılan: açık işi olanlar) — sıralı (§8.3).

    `state`: `open` açık işi olanlar · `clear` olmayanlar ("Kütüphaneden ilişiği
    yoktur" belgesi basılabilecekler) · `all` hepsi. Açık işi olmayan kişiler canlı
    sicilden (ayrılmışlar dahil) okunur; açık işi olan kişi silinmişse de listededir
    (savunma: açık yükümlülüğü olan kişi silinemez).
    """
    f = filtre or ClearanceFilter()
    level = graduating_level()
    isler = open_obligations_by_person()
    satirlar: dict[PersonKey, ClearanceRow] = {}
    if f.state in (STATE_OPEN, STATE_ALL):
        for anahtar, kisi in _persons_by_key(isler).items():
            satirlar[anahtar] = _row(kisi, isler.get(anahtar), level)
    if f.state in (STATE_CLEAR, STATE_ALL):
        for kisi in _candidates(f):
            anahtar = _key(kisi)
            if anahtar in isler:
                continue
            satirlar[anahtar] = _row(kisi, None, level)
    needle = normalize_header(f.search) if f.search.strip() else ""
    number_index = okul_selectors.number_search_index(f.search) if f.search.strip() else ""
    secilen = [s for s in satirlar.values() if _matches(s, f, needle, number_index)]
    return sorted(secilen, key=row_sort_key)


def person_clearance(person: Person) -> ClearanceRow:
    """Tek kişinin açık işleri (E5 belgesi basılmadan önce denetim)."""
    level = graduating_level()
    isler = open_obligations_by_person().get(_key(person))
    return _row(person, isler, level)


def persons_for_certificate(
    *, student_ids: Iterable[int] = (), personnel_ids: Iterable[int] = ()
) -> tuple[list[ClearanceRow], list[str]]:
    """Belge istenen kişilerin satırları (sıralı) + bulunamayan kimlik iletileri.

    Yalnız CANLI kişi (ayrılmışlar dahil) belgeye girer; silinmiş kayda belge basılmaz.
    """
    level = graduating_level()
    isler = open_obligations_by_person()
    ogrenci_ids = list(dict.fromkeys(int(i) for i in student_ids))
    personel_ids = list(dict.fromkeys(int(i) for i in personnel_ids))
    ogrenciler = {int(o.pk): o for o in Student.objects.filter(pk__in=ogrenci_ids)}
    personel = {int(p.pk): p for p in Personnel.objects.filter(pk__in=personel_ids)}
    eksik: list[str] = []
    satirlar: list[ClearanceRow] = []
    for pk in ogrenci_ids:
        ogrenci = ogrenciler.get(pk)
        if ogrenci is None:
            eksik.append("Öğrenci bulunamadı.")
            continue
        satirlar.append(_row(ogrenci, isler.get(("S", pk)), level))
    for pk in personel_ids:
        kisi = personel.get(pk)
        if kisi is None:
            eksik.append("Personel bulunamadı.")
            continue
        satirlar.append(_row(kisi, isler.get(("P", pk)), level))
    return sorted(satirlar, key=row_sort_key), eksik


# ---------------------------------------------------------------------------
# Şube (sınıf kitaplığı) teslimleri — kişisiz
# ---------------------------------------------------------------------------
def section_delivery_rows(*, graduating_only: bool = False) -> list[SectionDeliveryRow]:
    """Açık teslimi olan şubeler: son sınıf şubeleri önce, sonra sınıf ve şube (TR).

    Etkin ders yılında olmayan (geçen yıldan kalmış) şubenin açık teslimi de
    listelenir: geri alınmamış kitap o şubede bekliyordur. Şube teslimi kayba
    dönüşmüşse dosyası ("Çözüm bekliyor" ya da "Bedel belirlendi") şubenin satırında
    sayılır; bedeli teslim alınmış dosya okulun işidir, sayılmaz.
    """
    level = graduating_level()
    yil = okul_selectors.active_school_year()
    gruplar: dict[int, list[Delivery]] = {}
    subeler: dict[int, ClassSection] = {}
    for teslim in Delivery.objects.filter(
        status=DeliveryStatus.OPEN, section__isnull=False
    ).select_related("section", "section__school_year", "copy", "copy__work"):
        assert teslim.section is not None
        gruplar.setdefault(int(teslim.section_id or 0), []).append(teslim)
        subeler[int(teslim.section_id or 0)] = teslim.section
    dosyalar: dict[int, list[LossDamageCase]] = {}
    for dosya in (
        LossDamageCase.objects.filter(resolution__in=PERSON_OPEN_RESOLUTIONS)
        .filter(selectors_teslim.section_case_q())
        .select_related("delivery", "delivery__section", "delivery__section__school_year", "copy")
    ):
        assert dosya.delivery is not None and dosya.delivery.section is not None
        sube_pk = int(dosya.delivery.section_id or 0)
        dosyalar.setdefault(sube_pk, []).append(dosya)
        subeler.setdefault(sube_pk, dosya.delivery.section)

    satirlar: list[SectionDeliveryRow] = []
    for pk, sube in subeler.items():
        etkin = yil is not None and sube.school_year_id == yil.pk
        son_sinif = etkin and level is not None and sube.class_level == level
        if graduating_only and not son_sinif:
            continue
        satirlar.append(
            SectionDeliveryRow(
                section=sube,
                is_graduating=son_sinif,
                is_active_year=etkin,
                deliveries=tuple(sorted(gruplar.get(pk, []), key=lambda d: (d.delivered_on, d.pk))),
                cases=tuple(dosyalar.get(pk, [])),
            )
        )
    return sorted(
        satirlar,
        key=lambda s: (
            not s.is_graduating,
            not s.is_active_year,
            s.section.class_level,
            normalize.tr_sort_key(s.section.class_section),
            s.section.pk,
        ),
    )


# ---------------------------------------------------------------------------
# Sayılar (Genel Bakış ve yıl akışı ekranları — kişisel veri YOK)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ClearanceCounts:
    persons: int
    graduating_persons: int
    leaving_persons: int
    open_loans: int
    graduating_open_loans: int
    leaving_open_loans: int
    teacher_deliveries: int
    section_deliveries: int
    graduating_section_deliveries: int
    open_cases: int


def clearance_counts() -> ClearanceCounts:
    """Açık işlerin sayıları (kişi adı çözülmez — yalnız anahtar ve grup)."""
    level = graduating_level()
    isler = open_obligations_by_person()
    kisiler = _persons_by_key(isler, yalniz_durum=True)
    kisi = son = ayrilan = 0
    son_odunc = ayrilan_odunc = 0
    for anahtar, kayit in isler.items():
        hedef = kisiler.get(anahtar)
        if hedef is None:
            continue
        kisi += 1
        grup = person_group(hedef, level)
        if grup == GROUP_GRADUATING:
            son += 1
            son_odunc += len(kayit.loans)
        elif grup == GROUP_LEAVING:
            ayrilan += 1
            ayrilan_odunc += len(kayit.loans)
    subeler = section_delivery_rows()
    return ClearanceCounts(
        persons=kisi,
        graduating_persons=son,
        leaving_persons=ayrilan,
        open_loans=Loan.objects.filter(status=LoanStatus.OPEN).count(),
        graduating_open_loans=son_odunc,
        leaving_open_loans=ayrilan_odunc,
        teacher_deliveries=Delivery.objects.filter(
            status=DeliveryStatus.OPEN, personnel__isnull=False
        ).count(),
        section_deliveries=sum(len(s.deliveries) for s in subeler),
        graduating_section_deliveries=sum(len(s.deliveries) for s in subeler if s.is_graduating),
        open_cases=LossDamageCase.objects.filter(resolution__in=PERSON_OPEN_RESOLUTIONS).count(),
    )


def graduating_students_q(level: int | None) -> Q:
    """Son sınıftaki aktif öğrenciler (havuzdakiler hariç) — DB süzgeci."""
    if level is None:
        return Q(pk__in=[])
    return Q(status=StudentStatus.ACTIVE, class_level=level, leave_candidate_since__isnull=True)
