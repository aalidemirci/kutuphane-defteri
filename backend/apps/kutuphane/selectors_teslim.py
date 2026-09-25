"""Teslim, kayıp/hasar ve onarım salt okuma sorguları (F7 — tasarım §6.2, §9-9, §9-11).

Görünümler, servisler ve (sonraki kolların) ilişik listesi ile evrak (E5, E6,
E15) bu verilere buradan erişir. Kurallar `services.deliveries` ve
`services.loss_damage`'dadır.

- **Kişi bağı TEK kuraldır** (`case_person`): kayıp/hasar dosyası ÖNCE üyeliğin
  kişisine (öğrenci ya da personel), üyelik yoksa teslim alan öğretmene bağlanır.
  Üyeliği olan dosyada teslim alan öğretmen dosyanın kişisi DEĞİLDİR (teslimdeki
  kitabı kaybeden öğrenci seçildiyse dosya onundur). Açık yükümlülük soruları
  (`open_cases_for_person`, `persons_with_open_cases`) ve ilişik listesi
  (`selectors_ilisik`) aynı kuralı uygular — F7 düzeltme turu; tutarlılık testi
  `tests/test_kayip_hasar.py`. Açık teslim yalnız öğretmene bağlıdır (şube
  teslimi kişisizdir); üyeliği olmayan ve şube tesliminden doğan dosya şubenin
  açık işidir (`open_cases_for_section`).
- **Kişinin açık işi ≠ açık dosya** (25.09.2026 kullanıcı kararı): kişiye ya da
  şubeye yazılan dosyalar yalnız "Çözüm bekliyor" ve "Bedel belirlendi"dir
  (`PERSON_OPEN_RESOLUTIONS`). "Bedel teslim alındı" dosyası açıktır (nüsha başına
  tek açık dosya, Kayıp ve Hasar ekranı) ama yalnız okulun işidir.
- **Sıralama**: listeler tarihe ve kimliğe göre sıralanır (DB `order_by` tarih ve
  tamsayıda güvenlidir). Öğretmen adı şifreli olduğu için ada göre sıralama ya
  da süzme istenirse Python'da yapılır (CLAUDE.md §3); bu modül adla sorgu
  YAZMAZ.
- **Profil yasağı** (CLAUDE.md §2-5): burada üye bazında konu ya da sınıf
  dağılımı üretilmez; dosya ve teslim satırları yalnız nüsha, eser adı, tarih ve
  durum taşır.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from django.db.models import Q, QuerySet

from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    PERSON_OPEN_RESOLUTIONS,
    CopyRepair,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    LossDamageCase,
)
from apps.okul.models import ClassSection, Personnel, Student

type Person = Student | Personnel

_TESLIM_ILISKILERI = ("copy", "copy__work", "section", "section__school_year", "personnel")
_DOSYA_ILISKILERI = (
    "copy",
    "copy__work",
    "membership",
    "membership__student",
    "membership__personnel",
    "loan",
    "delivery",
    "delivery__section",
    "delivery__personnel",
)


# ---------------------------------------------------------------------------
# Teslim
# ---------------------------------------------------------------------------
def delivery_recipient_label(delivery: Delivery) -> str:
    """Teslim alanın ekranda ve evrakta gösterilen adı: şube etiketi ya da öğretmen adı.

    Öğretmen adı ŞİFRELİDİR (yalnız yönetici kipinde gösterilir). Saklama sonunda
    bağı koparılmış teslimde (F11) boş döner. Yumuşak silinmiş şube de etiketini
    verir: teslim o şubeye yapılmıştır (belge izi).
    """
    if delivery.recipient_kind == DeliveryRecipientKind.SECTION:
        return delivery.section.class_label if delivery.section is not None else ""
    return delivery.personnel.full_name if delivery.personnel is not None else ""


def deliveries(
    *,
    status: str = "",
    recipient_kind: str = "",
    section_id: int | None = None,
    personnel_id: int | None = None,
    document_no: str = "",
    copy_id: int | None = None,
    ids: Iterable[int] | None = None,
) -> QuerySet[Delivery]:
    """Teslim satırları (en yeni teslim önce). Süzgeçler isteğe bağlıdır ve birleşir."""
    qs = Delivery.objects.select_related(*_TESLIM_ILISKILERI)
    if status:
        qs = qs.filter(status=status)
    if recipient_kind:
        qs = qs.filter(recipient_kind=recipient_kind)
    if section_id is not None:
        qs = qs.filter(section_id=section_id)
    if personnel_id is not None:
        qs = qs.filter(personnel_id=personnel_id)
    if document_no:
        qs = qs.filter(document_no=document_no)
    if copy_id is not None:
        qs = qs.filter(copy_id=copy_id)
    if ids is not None:
        qs = qs.filter(pk__in=list(ids))
    return qs.order_by("-delivered_on", "-pk")


def get_delivery(delivery_id: int) -> Delivery | None:
    return Delivery.objects.select_related(*_TESLIM_ILISKILERI).filter(pk=delivery_id).first()


def open_delivery_for_copy(copy_id: int) -> Delivery | None:
    """Nüshanın açık teslimi (en çok bir tane — `uq_delivery_open_per_copy`)."""
    return (
        Delivery.objects.select_related(*_TESLIM_ILISKILERI)
        .filter(copy_id=copy_id, status=DeliveryStatus.OPEN)
        .first()
    )


def open_deliveries_for_person(person: Person) -> QuerySet[Delivery]:
    """Kişinin açık teslimleri — yalnız öğretmene yapılır; öğrencide her zaman boştur."""
    if not isinstance(person, Personnel):
        return Delivery.objects.none()
    return deliveries(status=DeliveryStatus.OPEN, personnel_id=person.pk)


def open_deliveries_for_section(section: ClassSection) -> QuerySet[Delivery]:
    """Şubenin (sınıf kitaplığının) açık teslimleri."""
    return deliveries(status=DeliveryStatus.OPEN, section_id=section.pk)


def document_numbers(prefix: str) -> list[str]:
    """Bu önekle başlayan bütün belge numaraları (silinmiş satırlar dahil — numara tekrar
    kullanılmaz)."""
    return list(
        Delivery.all_objects.filter(document_no__startswith=prefix)
        .values_list("document_no", flat=True)
        .distinct()
    )


def document_no_used(document_no: str) -> bool:
    return Delivery.all_objects.filter(document_no=document_no).exists()


# ---------------------------------------------------------------------------
# Kayıp / hasar dosyası
# ---------------------------------------------------------------------------
def case_person(case: LossDamageCase) -> Person | None:
    """Dosyanın bağlı olduğu kişi: üyeliğin kişisi, yoksa teslim alan öğretmen (TEK kural)."""
    if case.membership is not None:
        return case.membership.person
    if case.delivery is not None and case.delivery.personnel is not None:
        personel: Personnel = case.delivery.personnel
        return personel
    return None


def _person_case_q(person: Person) -> Q:
    """`case_person` kuralının DB karşılığı: önce üyelik, üyelik yoksa teslim alan."""
    if isinstance(person, Student):
        return Q(membership__student=person)
    return Q(membership__personnel=person) | Q(membership__isnull=True, delivery__personnel=person)


def section_case_q() -> Q:
    """Şubenin açık işi sayılan dosyalar: üyeliği olmayan ve şube tesliminden doğan dosya."""
    return Q(membership__isnull=True, delivery__section__isnull=False)


def loss_damage_cases(
    *,
    resolution: str = "",
    case_type: str = "",
    open_only: bool = False,
    copy_id: int | None = None,
    ids: Iterable[int] | None = None,
) -> QuerySet[LossDamageCase]:
    """Kayıp/hasar dosyaları (en yeni tespit önce)."""
    qs = LossDamageCase.objects.select_related(*_DOSYA_ILISKILERI)
    if resolution:
        qs = qs.filter(resolution=resolution)
    if case_type:
        qs = qs.filter(case_type=case_type)
    if open_only:
        qs = qs.filter(resolution__in=OPEN_CASE_RESOLUTIONS)
    if copy_id is not None:
        qs = qs.filter(copy_id=copy_id)
    if ids is not None:
        qs = qs.filter(pk__in=list(ids))
    return qs.order_by("-reported_on", "-pk")


def get_case(case_id: int) -> LossDamageCase | None:
    return LossDamageCase.objects.select_related(*_DOSYA_ILISKILERI).filter(pk=case_id).first()


def open_case_for_copy(copy_id: int) -> LossDamageCase | None:
    """Nüshanın çözülmemiş dosyası (en çok bir tane — `uq_lossdamagecase_open_per_copy`)."""
    return loss_damage_cases(open_only=True, copy_id=copy_id).first()


def _person_open_cases() -> QuerySet[LossDamageCase]:
    """Kişinin (ya da şubenin) açık işi sayılan dosyalar — "Bedel teslim alındı" HARİÇ."""
    return loss_damage_cases().filter(resolution__in=PERSON_OPEN_RESOLUTIONS)


def open_cases_for_person(person: Person) -> QuerySet[LossDamageCase]:
    """Kişinin açık işi olan dosyaları (bütün üyelikleri + üyeliksiz öğretmen teslimi üzerinden).

    Bedeli teslim alınmış dosya kişiye yazılmaz (`PERSON_OPEN_RESOLUTIONS`).
    """
    return _person_open_cases().filter(_person_case_q(person)).distinct()


def open_cases_for_section(section: ClassSection) -> QuerySet[LossDamageCase]:
    """Şubenin (sınıf kitaplığının) açık işi olan dosyaları — kişiye bağlanmamış şube teslimi."""
    return _person_open_cases().filter(section_case_q()).filter(delivery__section=section)


# ---------------------------------------------------------------------------
# İlişik listesi için toplu sorular (kişi anahtarı: ('S', öğrenci pk) / ('P', personel pk))
# ---------------------------------------------------------------------------
def persons_with_open_deliveries() -> set[tuple[str, int]]:
    """Açık teslimi olan kişiler — yalnız öğretmenler (şube teslimi kişisizdir). TEK sorgu."""
    return {
        ("P", int(pk))
        for pk in Delivery.objects.filter(status=DeliveryStatus.OPEN, personnel__isnull=False)
        .values_list("personnel_id", flat=True)
        .distinct()
    }


def persons_with_open_cases() -> set[tuple[str, int]]:
    """Açık işi olan kayıp/hasar dosyası olan kişiler (`case_person` kuralıyla). TEK sorgu.

    Bedeli teslim alınmış dosya sayılmaz (`PERSON_OPEN_RESOLUTIONS`).
    """
    anahtarlar: set[tuple[str, int]] = set()
    satirlar = LossDamageCase.objects.filter(resolution__in=PERSON_OPEN_RESOLUTIONS).values_list(
        "membership_id",
        "membership__student_id",
        "membership__personnel_id",
        "delivery__personnel_id",
    )
    for uyelik_pk, ogrenci_pk, personel_pk, teslim_personel_pk in satirlar:
        if ogrenci_pk is not None:
            anahtarlar.add(("S", int(ogrenci_pk)))
        elif personel_pk is not None:
            anahtarlar.add(("P", int(personel_pk)))
        elif uyelik_pk is None and teslim_personel_pk is not None:
            anahtarlar.add(("P", int(teslim_personel_pk)))
    return anahtarlar


# ---------------------------------------------------------------------------
# Onarım (D3)
# ---------------------------------------------------------------------------
def open_repair_for_copy(copy_id: int) -> CopyRepair | None:
    """Nüshanın açık onarım kaydı (en çok bir tane — `uq_copyrepair_open_per_copy`)."""
    return CopyRepair.objects.filter(copy_id=copy_id, returned_on__isnull=True).first()


def repairs(
    *, open_only: bool = False, sent_from: date | None = None, sent_to: date | None = None
) -> QuerySet[CopyRepair]:
    """Onarım kayıtları (yıl sonu raporunun onarım sayısı — E9, F8)."""
    qs = CopyRepair.objects.select_related("copy", "copy__work", "case")
    if open_only:
        qs = qs.filter(returned_on__isnull=True)
    if sent_from is not None:
        qs = qs.filter(sent_on__gte=sent_from)
    if sent_to is not None:
        qs = qs.filter(sent_on__lte=sent_to)
    return qs.order_by("-sent_on", "-pk")
