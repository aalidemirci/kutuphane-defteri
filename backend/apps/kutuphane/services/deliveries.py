"""Toplu teslim ve geri alma — sınıf kitaplığına ya da öğretmene teslim (U11; §9-11, §4.4).

**Teslim ödünç DEĞİLDİR** (§9-11, sözlük "teslim"; "ödünç", "emanet", "zimmet"
değil): Md. 18 sayı sınırı ve on beş günlük süre uygulanmaz, üyelik gerekmez,
teslim alanın ödünç hakkından bir şey eksilmez. Kurallar:

1. **Alan**: etkin ders yılının bir şubesi (sınıf kitaplığı — Md. 4/1-i) YA DA
   aktif bir öğretmen. Diğer personele teslim yapılmaz (tasarım "sınıf
   kitaplığına ya da öğretmene"; fail-closed). Teslim açıkken alan silinemez:
   öğretmende açık yükümlülüktür (kişi kayıt defteri), şubede silme reddedilir
   (şube tesliminden doğan çözülmemiş dosya da şubeyi tutar). Personel
   birleştirmesinde açık teslim yalnız öğretmen olan kayda geçer.
2. **Toplu teslim** okutmayla kurulan bir listedir ve TEK işlemdir (ya hepsi ya
   hiçbiri). Listedeki her nüsha RAFTA olmalıdır; ödünçte, teslimde, onarımda,
   kayıp ya da kayıttan düşülmüş nüsha teslim edilmez. Bir listenin bütün
   satırları aynı belge no'yu taşır (E15). Belge no verilmezse program
   `<yıl>/<sıra>` biçiminde yeni numara verir; kullanılmış numara tekrar verilmez.
3. **Tek açık kayıt** (§9-7): nüsha "Rafta"dan "Sınıf kitaplığında"ya KOŞULLU
   geçer (`services.nusha_durumu`); aynı anda ödünç verilen nüsha için yalnız
   biri kazanır, öbürü geri sarılır.
4. **Geri alma okutmayla** yapılır ve görevli kipinde de AÇIKTIR (§4.4 "Teslimden
   geri alma okutması"); teslim VERME yalnız yönetici kipindedir. Okutma bir
   olaydır (her zaman bir sonuç gövdesi döner); görevli kipinde yanıt yalnız
   barkodu ve eser adını taşır — teslim alanın kimliği yoktur. Geri alma hiçbir
   durumda kilitlenmez (sayım dahil — iade gibi).
5. Kayıp bildirimi teslimdeki nüshanın teslimini "Kayba dönüştü" ile kapatır
   (`services.loss_damage.report_lost`).
6. **Sayım için hizmet arası** (F9, okul kararı) yeni TESLİMİ de durdurur (madde 27,
   25.09.2026 kullanıcı kararı): toplu teslim ve teslim listesine okutmanın ön
   denetimi hizmet arası sürerken reddeder — ödünç reddiyle AYNI kod ve ileti
   (`circulation.RED_HIZMET_ARASI`, `circulation.SERVICE_PAUSE_MESSAGE`). Teslimden
   geri alma ve iade hiçbir durumda durmaz. TMY 32/3 durdurması teslimi kapsamaz
   (teslim TMY'de giriş-çıkış değildir).

Hata ve günlük metinleri KİŞİ ADI İÇERMEZ.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_sayim, selectors_teslim
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    Copy,
    CopyStatus,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    Loan,
    LoanStatus,
)
from apps.kutuphane.serializers_teslim import (
    ADMIN_TAKE_BACK_FIELDS,
    STAFF_TAKE_BACK_FIELDS,
    TAKE_BACK_DELIVERY_FIELDS,
)
from apps.kutuphane.services import circulation, masa, nusha_durumu
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import selectors as okul_selectors
from apps.okul.models import ClassSection, MemberKind, Personnel, Student
from apps.okul.services import app_password, persons, sections

logger = logging.getLogger("kutuphane_defteri.kutuphane")

type Person = Student | Personnel

#: Tek toplu teslimde en çok nüsha (bir sınıf kitaplığı birkaç yüz kitabı geçmez;
#: sınır tek istekte binlerce satırlık işlemi önleyen sigortadır).
MAX_DELIVERY_BATCH: Final = 500
#: Geri alma okutmasında tek istekte en çok kod (okuyucu kuyruğunun boşaltılması).
MAX_TAKE_BACK_BATCH: Final = 200

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK — sözlük: teslim, geri alma)
# ---------------------------------------------------------------------------
RECIPIENT_REQUIRED_MESSAGE = "Teslim için bir şube ya da bir öğretmen seçin."
SECTION_NOT_FOUND_MESSAGE = "Şube bulunamadı."
SECTION_OLD_YEAR_MESSAGE = "Teslim yalnız etkin ders yılının şubesine yapılır."
TEACHER_NOT_FOUND_MESSAGE = "Öğretmen bulunamadı."
TEACHER_LEFT_MESSAGE = "Ayrılmış personele teslim yapılamaz."
TEACHER_ONLY_MESSAGE = (
    "Teslim yalnız sınıf kitaplığına ya da öğretmene yapılır; diğer personele teslim yapılmaz."
)
NO_COPIES_MESSAGE = "Teslim edilecek kitap okutulmadı."
TOO_MANY_MESSAGE = f"Tek teslimde en çok {MAX_DELIVERY_BATCH} kitap olabilir."
DELIVERED_IN_FUTURE_MESSAGE = "Teslim tarihi bugünden sonra olamaz."
EXPECTED_BEFORE_MESSAGE = "Beklenen dönüş teslim tarihinden önce olamaz."
DOCUMENT_NO_USED_MESSAGE = (
    "Bu belge no başka bir teslimde kullanılmış. Boş bırakın, program yeni numara verir."
)
DOCUMENT_NO_LENGTH_MESSAGE = "Belge no en çok 40 karakter olabilir."
RACE_MESSAGE = "{kitap}: kitap bu arada başka bir işlemde raftan çıktı; listeyi yenileyin."

DELIVERABLE_MESSAGE = "Teslim edilebilir."
TAKE_BACK_DONE_MESSAGE = "Geri alındı."
NOT_DELIVERED_MESSAGE = "Bu kitap teslimde değil ({durum})."
NOT_DELIVERED_ON_LOAN_MESSAGE = (
    "Bu kitap teslimde değil (Ödünçte). İade için dolaşım masasını kullanın."
)
SECTION_DELETE_MESSAGE = "Bu şubede {sayi} açık teslim var; önce geri alın."
SECTION_DELETE_CASE_MESSAGE = (
    "Bu şubenin tesliminden doğan {sayi} çözülmemiş kayıp/hasar dosyası var; önce dosyayı çözün."
)
DELIVERY_HISTORY_DELETE_MESSAGE = (
    "Bu kişiye kütüphaneden teslim yapılmış; kaydı silinemez. Okuldan ayrıldıysa "
    "“Ayrıldı olarak işaretle” eylemini kullanın."
)
MERGE_TARGET_NOT_TEACHER_MESSAGE = (
    "Birleştirilecek kaydın {sayi} açık teslimi var; teslim yalnız öğretmene yapılır. "
    "Kalacak kaydın üye türü “Öğretmen” olmalıdır ya da önce teslimleri geri alın."
)

#: Geri alma okutmasının sonuçları (masa iadesiyle aynı sözleşme: okutma bir olaydır).
GERI_ALINDI: Final = "returned"
TESLIMDE_DEGIL: Final = "not_delivered"
REDDEDILDI: Final = "rejected"
#: Teslim ön denetiminin sonuçları.
TESLIM_EDILEBILIR: Final = "deliverable"

_BELGE_NO = re.compile(r"^(\d{4})/(\d+)$")


@dataclass(frozen=True)
class DeliveryBatch:
    """Toplu teslimin sonucu: belge no, tarihler, alan ve açılan satırlar (okutma sırası)."""

    document_no: str
    delivered_on: date
    expected_return: date | None
    recipient_kind: str
    section: ClassSection | None
    personnel: Personnel | None
    deliveries: tuple[Delivery, ...]


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _kitap(copy: Copy) -> str:
    return barcode_module.format_barcode(copy.barcode)


def delivery_obstacle(copy: Copy) -> str:
    """Nüsha teslim edilebilir mi? Edilemezse kişisel veri taşımayan gerekçe, yoksa ''.

    Teslim ödünç olmadığı için `is_loanable` (danışma, piyasada yok, süreli
    yayın) burada ARANMAZ; aranan yalnız nüshanın rafta ve başka bir açık kayıtta
    olmamasıdır (§9-7).
    """
    if copy.deleted_at is not None:
        return masa.SCAN_DELETED_MESSAGE
    if copy.work.deleted_at is not None:
        return "Bu nüshanın eseri silinmiş — teslim edilemez."
    if copy.status != CopyStatus.AVAILABLE:
        return f"{copy.get_status_display()} — teslim edilemez."
    if Loan.objects.filter(copy_id=copy.pk, status=LoanStatus.OPEN).exists():
        return f"{CopyStatus.ON_LOAN.label} — teslim edilemez."
    if selectors_teslim.open_delivery_for_copy(copy.pk) is not None:
        return f"{CopyStatus.DELIVERED.label} — teslim edilemez."
    return ""


def ensure_no_service_pause() -> None:
    """Sayım için hizmet arası sürüyorsa yeni teslim yapılmaz (kural 6; madde 27).

    Ödünç reddiyle aynı kod ve ileti: masa ve teslim ekranı aynı cümleyi yazar.
    """
    if selectors_sayim.service_pause_active():
        raise circulation.DolasimReddi(
            circulation.SERVICE_PAUSE_MESSAGE, code=circulation.RED_HIZMET_ARASI
        )


def _alan(
    *, section: ClassSection | None, personnel: Personnel | None
) -> tuple[str, ClassSection | None, Personnel | None]:
    """Teslim alanı doğrular: şube XOR öğretmen (kural 1)."""
    if (section is None) == (personnel is None):
        raise ValidationError(RECIPIENT_REQUIRED_MESSAGE)
    if section is not None:
        if section.deleted_at is not None:
            raise ValidationError({"section_id": SECTION_NOT_FOUND_MESSAGE})
        yil = okul_selectors.active_school_year()
        if yil is None or section.school_year_id != yil.pk:
            raise ValidationError({"section_id": SECTION_OLD_YEAR_MESSAGE})
        return DeliveryRecipientKind.SECTION, section, None
    assert personnel is not None
    if personnel.deleted_at is not None:
        raise ValidationError({"personnel_id": TEACHER_NOT_FOUND_MESSAGE})
    if not personnel.is_active:
        raise ValidationError({"personnel_id": TEACHER_LEFT_MESSAGE})
    if personnel.member_kind != MemberKind.TEACHER:
        raise ValidationError({"personnel_id": TEACHER_ONLY_MESSAGE})
    return DeliveryRecipientKind.TEACHER, None, personnel


def _tarihler(delivered_on: date | None, expected_return: date | None) -> tuple[date, date | None]:
    """Teslim tarihi (bugün ya da geçmiş) ve beklenen dönüş (verilmezse ders yılı sonu)."""
    bugun = timezone.localdate()
    teslim = delivered_on or bugun
    if teslim > bugun:
        raise ValidationError({"delivered_on": DELIVERED_IN_FUTURE_MESSAGE})
    donus = expected_return
    if donus is None:
        yil = okul_selectors.active_school_year()
        if yil is not None and yil.end_date >= teslim:
            donus = yil.end_date
    if donus is not None and donus < teslim:
        raise ValidationError({"expected_return": EXPECTED_BEFORE_MESSAGE})
    return teslim, donus


def next_document_no(on: date) -> str:
    """Yılın sıradaki belge no'su (`2026/7`) — kullanılmış numaranın bir fazlası.

    Silinmiş satırlar dahil bütün numaralara bakılır: belge no tekrar verilmez.
    Elle yazılmış ve bu kalıba uyan numara da sayılır.
    """
    en_buyuk = 0
    for numara in selectors_teslim.document_numbers(f"{on.year}/"):
        eslesme = _BELGE_NO.match(numara)
        if eslesme and int(eslesme.group(1)) == on.year:
            en_buyuk = max(en_buyuk, int(eslesme.group(2)))
    return f"{on.year}/{en_buyuk + 1}"


def _belge_no(document_no: str, on: date) -> str:
    belge = (document_no or "").strip()
    if not belge:
        return next_document_no(on)
    if len(belge) > 40:
        raise ValidationError({"document_no": DOCUMENT_NO_LENGTH_MESSAGE})
    if selectors_teslim.document_no_used(belge):
        raise ValidationError({"document_no": DOCUMENT_NO_USED_MESSAGE})
    return belge


def _okutmalari_coz(barcodes: Sequence[object]) -> tuple[list[Copy], list[str]]:
    """Okutulan kodları nüshalara çözer (tekrar okutmalar tekilleşir); gerekçeli hatalar."""
    nushalar: list[Copy] = []
    gorulen: set[int] = set()
    hatalar: list[str] = []
    for sira, deger in enumerate(barcodes, start=1):
        okutma = masa.kitap_coz(deger, staff=False)
        if okutma.copy is None:
            # Ham kod YANKILANMAZ (üye kartı okutulmuş olabilir): sıra numarası yeter.
            hatalar.append(f"{sira}. okutma: {okutma.message}")
            continue
        if okutma.copy.pk in gorulen:
            continue
        gorulen.add(okutma.copy.pk)
        engel = okutma.message or delivery_obstacle(okutma.copy)
        if engel:
            hatalar.append(f"{_kitap(okutma.copy)}: {engel}")
            continue
        nushalar.append(okutma.copy)
    return nushalar, hatalar


# ---------------------------------------------------------------------------
# Toplu teslim (yalnız yönetici kipi)
# ---------------------------------------------------------------------------
@transaction.atomic
def deliver(
    *,
    barcodes: Sequence[object],
    section: ClassSection | None = None,
    personnel: Personnel | None = None,
    delivered_on: date | None = None,
    expected_return: date | None = None,
    document_no: str = "",
) -> DeliveryBatch:
    """Toplu teslim: okutulan nüshaları şubeye YA DA öğretmene teslim eder (TEK işlem).

    Md. 18 sayı sınırı UYGULANMAZ (teslim ödünç değildir). Listedeki nüshalardan
    biri teslim edilemiyorsa hiçbir teslim yapılmaz ve bütün gerekçeler
    `{"barcodes": [...]}` olarak döner (400). Tekrar okutulan nüsha bir kez
    sayılır. Yalnız yönetici kipinde (görevli kipinde `KipYetkisiz`). Sayım için
    hizmet arası sürerken reddedilir (kural 6; 400 `sayim_hizmet_arasi`).
    """
    require_admin_mode()
    app_password.require_password_set()
    ensure_no_service_pause()
    tur, sube, ogretmen = _alan(section=section, personnel=personnel)
    teslim_tarihi, beklenen = _tarihler(delivered_on, expected_return)
    kodlar = list(barcodes)
    if not kodlar:
        raise ValidationError({"barcodes": NO_COPIES_MESSAGE})
    if len(kodlar) > MAX_DELIVERY_BATCH:
        raise ValidationError({"barcodes": TOO_MANY_MESSAGE})
    nushalar, hatalar = _okutmalari_coz(kodlar)
    if hatalar:
        raise ValidationError({"barcodes": hatalar})
    if not nushalar:
        raise ValidationError({"barcodes": NO_COPIES_MESSAGE})
    belge = _belge_no(document_no, teslim_tarihi)

    acilan: list[Delivery] = []
    for nusha in nushalar:
        # Tek açık kayıt (§9-7): "Rafta"dan çıkışı yalnız bir işlem kazanır.
        if not nusha_durumu.gecir(nusha.pk, eski=CopyStatus.AVAILABLE, yeni=CopyStatus.DELIVERED):
            raise ValidationError({"barcodes": [RACE_MESSAGE.format(kitap=_kitap(nusha))]})
        try:
            with transaction.atomic():
                acilan.append(
                    Delivery.objects.create(
                        copy=nusha,
                        recipient_kind=tur,
                        section=sube,
                        personnel=ogretmen,
                        delivered_on=teslim_tarihi,
                        expected_return=beklenen,
                        document_no=belge,
                    )
                )
        except IntegrityError as exc:
            raise ValidationError({"barcodes": [RACE_MESSAGE.format(kitap=_kitap(nusha))]}) from exc
    logger.info("Toplu teslim yapıldı: %d kitap.", len(acilan))
    return DeliveryBatch(
        document_no=belge,
        delivered_on=teslim_tarihi,
        expected_return=beklenen,
        recipient_kind=tur,
        section=sube,
        personnel=ogretmen,
        deliveries=tuple(acilan),
    )


def delivery_check_scan(value: object) -> dict[str, Any]:
    """Teslim listesine okutulan kodun ön denetimi — yazma YOK (yalnız yönetici kipi).

    `{result, kind, message, copy}`; `result` = `deliverable` · `rejected`. Sayım için
    hizmet arası sürerken her okutma reddedilir ve ileti hizmet arasınınkidir (kural 6).
    """
    require_admin_mode()
    okutma = masa.kitap_coz(value, staff=False)
    if okutma.copy is None:
        return {
            "result": REDDEDILDI,
            "kind": str(okutma.kind),
            "message": okutma.message,
            "copy": None,
        }
    hizmet_arasi = selectors_sayim.service_pause_active()
    engel = (
        circulation.SERVICE_PAUSE_MESSAGE
        if hizmet_arasi
        else okutma.message or delivery_obstacle(okutma.copy)
    )
    return {
        "result": REDDEDILDI if engel else TESLIM_EDILEBILIR,
        "kind": str(okutma.kind),
        "message": engel or DELIVERABLE_MESSAGE,
        "copy": masa.nusha_ozeti(okutma.copy, staff=False),
    }


# ---------------------------------------------------------------------------
# Geri alma (görevli kipinde de açık — okutma)
# ---------------------------------------------------------------------------
def _close_delivery(delivery: Delivery) -> Delivery:
    delivery.status = DeliveryStatus.RETURNED
    delivery.returned_at = timezone.now()
    delivery.save(update_fields=["status", "returned_at", "updated_at"])
    # Nüsha teslimdeyse rafa döner (tutarsız bir durumda başka duruma dokunulmaz).
    nusha_durumu.gecir(delivery.copy_id, eski=CopyStatus.DELIVERED, yeni=CopyStatus.AVAILABLE)
    return delivery


@transaction.atomic
def take_back(copy: Copy) -> Delivery | None:
    """Nüshanın açık teslimini kapatır ve nüshayı rafa döndürür; açık teslim yoksa None.

    Hiçbir durumda kilitlenmez (kip, sayım, alanın ayrılmış olması durdurmaz).
    """
    acik = selectors_teslim.open_delivery_for_copy(copy.pk)
    if acik is None:
        return None
    return _close_delivery(acik)


def _teslim_ozeti(delivery: Delivery) -> dict[str, Any]:
    """Yönetici kipinde geri almanın teslim ayrıntısı (teslim alanın adı dahil)."""
    veri = {
        "id": delivery.pk,
        "recipient_kind": delivery.recipient_kind,
        "recipient_kind_display": str(delivery.get_recipient_kind_display()),
        "recipient_label": selectors_teslim.delivery_recipient_label(delivery),
        "delivered_on": delivery.delivered_on,
        "expected_return": delivery.expected_return,
        "document_no": delivery.document_no,
        "returned_at": delivery.returned_at,
    }
    return {alan: veri[alan] for alan in TAKE_BACK_DELIVERY_FIELDS}


def _geri_alma_yaniti(
    result: str,
    kind: ScanKind,
    message: str,
    copy: Copy | None,
    *,
    staff: bool,
    delivery: Delivery | None = None,
) -> dict[str, Any]:
    veri = {
        "result": result,
        "kind": str(kind),
        "message": message,
        "copy": masa.nusha_ozeti(copy, staff=staff) if copy is not None else None,
        "delivery": _teslim_ozeti(delivery) if delivery is not None else None,
    }
    return {
        alan: veri[alan] for alan in (STAFF_TAKE_BACK_FIELDS if staff else ADMIN_TAKE_BACK_FIELDS)
    }


def _teslimde_degil_iletisi(copy: Copy) -> str:
    if copy.status == CopyStatus.ON_LOAN:
        return NOT_DELIVERED_ON_LOAN_MESSAGE
    if copy.status in TERMINAL_COPY_STATUSES:
        return circulation.WITHDRAWN_COPY_MESSAGE
    return NOT_DELIVERED_MESSAGE.format(durum=copy.get_status_display())


def take_back_scan(value: object, *, staff: bool) -> dict[str, Any]:
    """Geri alma okutması → `{result, kind, message, copy[, delivery]}` (§4.4, U11).

    `result`: `returned` (geri alındı) · `not_delivered` (açık teslimi yok; durum
    iletisi) · `rejected` (nüsha barkodu değil). Görevli kipinde `delivery`
    alanı YOKTUR ve nüsha özeti barkod + eser adıdır (`STAFF_TAKE_BACK_FIELDS`).
    """
    okutma = masa.kitap_coz(value, staff=staff)
    if not okutma.usable or okutma.copy is None:
        return _geri_alma_yaniti(REDDEDILDI, okutma.kind, okutma.message, None, staff=staff)
    teslim = take_back(okutma.copy)
    nusha = Copy.all_objects.select_related("work").get(pk=okutma.copy.pk)
    if teslim is None:
        return _geri_alma_yaniti(
            TESLIMDE_DEGIL, okutma.kind, _teslimde_degil_iletisi(nusha), nusha, staff=staff
        )
    return _geri_alma_yaniti(
        GERI_ALINDI, okutma.kind, TAKE_BACK_DONE_MESSAGE, nusha, staff=staff, delivery=teslim
    )


def take_back_scans(values: Iterable[object], *, staff: bool) -> list[dict[str, Any]]:
    """Toplu geri alma: okuyucu kuyruğundaki kodlar sırayla (her biri kendi işleminde).

    Bir kodun reddi öbürlerini durdurmaz — okutma bir olaydır; sonuçlar sırayla döner.
    """
    kodlar = list(values)
    if len(kodlar) > MAX_TAKE_BACK_BATCH:
        raise ValidationError(
            {"barcodes": f"Tek istekte en çok {MAX_TAKE_BACK_BATCH} kod okutulabilir."}
        )
    return [take_back_scan(kod, staff=staff) for kod in kodlar]


# ---------------------------------------------------------------------------
# Kişi ve şube kayıt defterlerine kaydolan kancalar (apps.okul.services)
# ---------------------------------------------------------------------------
def open_delivery_obligations(person: Person) -> list[str]:
    """Açık yükümlülük: öğretmenin açık teslimleri (ad içermez — sözlük §5)."""
    sayi = selectors_teslim.open_deliveries_for_person(person).count()
    return [f"{sayi} açık teslim var."] if sayi else []


def delivery_deletion_blocks(person: Person) -> list[str]:
    """Silme engeli: kişiye (kapanmış da olsa) teslim yapılmışsa kayıt silinmez.

    Teslim satırı alanı PROTECT ile tutar; kapanmış teslimin bağını saklama
    taraması koparır (§6.4, F11) — kullanıcının "Sil"i değil.
    """
    if isinstance(person, Personnel) and Delivery.all_objects.filter(personnel=person).exists():
        return [DELIVERY_HISTORY_DELETE_MESSAGE]
    return []


def move_deliveries_on_merge(source: Personnel, target: Personnel) -> None:
    """Personel birleştirmede kaynağın BÜTÜN teslimleri hedefe taşınır (PROTECT bağı).

    Kural 1 birleştirmede de geçerlidir (F7 düzeltme turu): kaynağın AÇIK teslimi
    varsa hedef öğretmen olmalıdır — açık teslim "diğer personel"e geçmez (teslim
    listesi onu "Öğretmen" diye basardı, aynı kişiye yeni teslim de reddedilirdi).
    Ret gerekçelidir ve kişi adı taşımaz; birleştirme tek işlem olduğu için hiçbir
    bağ taşınmamış olur. Kapanmış teslimler hedefin türüne bakılmadan taşınır
    (alanın türü `recipient_kind`'da kalıcıdır).
    """
    acik = selectors_teslim.open_deliveries_for_person(source).count()
    if acik and target.member_kind != MemberKind.TEACHER:
        raise ValidationError(MERGE_TARGET_NOT_TEACHER_MESSAGE.format(sayi=acik))
    Delivery.all_objects.filter(personnel=source).update(
        personnel=target, updated_at=timezone.now()
    )


def section_delete_obstacles(section: ClassSection) -> list[str]:
    """Şube silme engeli: sınıf kitaplığında açık teslim ya da şube tesliminden doğan
    çözülmemiş kayıp/hasar dosyası varsa (ikisi de ilişik listesinde şubenin açık işidir)."""
    gerekceler: list[str] = []
    sayi = selectors_teslim.open_deliveries_for_section(section).count()
    if sayi:
        gerekceler.append(SECTION_DELETE_MESSAGE.format(sayi=sayi))
    dosya = selectors_teslim.open_cases_for_section(section).count()
    if dosya:
        gerekceler.append(SECTION_DELETE_CASE_MESSAGE.format(sayi=dosya))
    return gerekceler


def register_hooks() -> None:
    """Kancaları okul kayıt defterlerine kaydeder (fikirdeş — `KutuphaneConfig.ready`)."""
    persons.register_obligation_check(open_delivery_obligations)
    persons.register_deletion_block(delivery_deletion_blocks)
    persons.register_merge_hook(move_deliveries_on_merge)
    sections.register_delete_check(section_delete_obstacles)
