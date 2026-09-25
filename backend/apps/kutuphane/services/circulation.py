"""Ödünç ve iade — dolaşım kurallarının TEK yeri (tasarım §9, §4.4; Md. 16-18, 23).

OYS'nin `apps/kutuphane/circulation.py` dosyasından UYARLA (tasarım §12): rol ve
izin dalları, `by_user` ve denetim kaydı (AuditLog) düştü — program hesapsızdır,
masadaki kişi ayrımı kiple yapılır (§4.4); iz ödünç kaydının kendisindedir
(gerekçe alanları, kartsız işareti). Sayım kilidi (OYS `_ensure_circulation_open`)
ALINMADI: TMY 32/3 durdurması ödüncü kapsamaz, "sayım için hizmet arası" ayrı bir
okul kararıdır ve F9'da yalnız YENİ ÖDÜNCÜ durdurur (§9-10, D18). **İade hiçbir
durumda kilitlenmez.**

KURALLAR (§9; her biri testle kilitli — `tests/test_dolasim_kurallari.py`):

1. Kim alabilir: aktif üyeliği olan aktif öğrenci ve öğretmen; diğer personel
   yalnız `staff_loans_enabled` açıksa (müdürlük kararı — AT-4). Veli üye olamaz.
2. Üyelik isteğe bağlıdır (Md. 17/1); ödünç yalnız üyeye verilir.
3. Ödünç verilmeyenler (Md. 16/1): tek türetim `Copy.is_loanable`'dır.
4. Süre on beş gündür (Md. 18, SABİT — ayar değildir, `policy.LOAN_PERIOD_DAYS`);
   sayı sınırı öğrenci 3 / öğretmen 5 / diğer personel `max_loans_staff`.
   **Sayı sınırı ve Md. 16/1 kaynakları HİÇBİR KİPTE istisna almaz**: bu
   servisin onlar için bir gerekçe parametresi YOKTUR.
5. İade tarihi `bugün + 15`; son gün kapalı güne rastlarsa izleyen ilk açık
   güne kayar (`shared.working_days.next_open_day`): hafta sonu, resmî tatil,
   dini bayram ve idari izin DAİMA (TBK 93'e kıyasen; idari izin programın
   kuralı), öğrenciye kapalı gün (ara tatil, yarıyıl) politika ayarıyla
   (`shift_due_date_on_school_break` — dayanağı yok, okulun tercihi). Kaydırma
   kullanıcıya "Md. 18 gereği" diye SUNULMAZ. İade tarihi dönem sonunu
   aşarsa UYARI döner; süre kısaltılmaz.
6. Uzatma, ceza ve harç YOKTUR. Gecikme engeli (`block_loan_if_overdue`) bir
   politika kuralıdır; istisnası YALNIZ yönetici kipinde ve gerekçeyle
   (kapalı liste + açıklama) tanınır ve kayda şifreli olarak geçer.
7. Bir nüsha aynı anda tek açık ödünçte YA DA tek açık teslimde olur (DB kısıtı +
   servis denetimi; ödünç ile teslim arasında nüsha durumunun koşullu geçişi —
   `services.nusha_durumu`, F7).
8. Sonlanmış üye iade yapabilir; ayrılışta üyelik sonlanır (`services.memberships`).
12. Kartsız ödünç YALNIZ yönetici kipinde ve kapalı listeden gerekçeyle; kayıt
   işaretlidir (Md. 23/1-a'dan sapma).
+ Yıl sonu son ödünç tarihi (`LibraryPolicy.last_loan_date`, son sınıflar için
  `last_loan_date_graduating`) geçtiyse yeni ödünç verilmez (§8.3); istisnası yoktur.

RED BİÇİMİ. Kural retleri `DolasimReddi`dir (400) ve kararlı bir `code` taşır
(`RED_*`); masa ekranı (§7.3) iletisini bu koda göre seçer ("Bu kitap başka bir
üyede. Önce iade alınsın mı?" gibi). İleti KİŞİSEL VERİ TAŞIMAZ; gecikme
engelinde görevli kipi yalnız "Ödünç verilemiyor — kütüphane yöneticisine
yönlendirin." görür (eser adı ve gecikme günü yok — §4.4, sözlük §5). Yönetici
kipine ait işler görevli kipinde `KipYetkisiz` (403 `kip_yetkisiz`) alır.
Gövde biçimsel hataları (tanınmayan gerekçe kodu) Django `ValidationError`'dır
(400 `validation_error`, alan adıyla).

DENETİM SIRASI GÖREVLİ KİPİNDE FARKLIDIR (§4.4; F6 düzeltme turu). Yönetici kipinde
nüsha denetimi (kimde, ödünç verilebilir mi) üyeye bağlı engellerden (sayı sınırı,
gecikme) ÖNCE koşar: üyenin kendi kitabını okutan yönetici "Bu kitap zaten bu üyede"
sorusunu alır, gerekçeli istisna penceresini değil. Görevli kipinde ise üyeye bağlı
bütün engeller (üyelik, yıl sonu, gecikme, sayı sınırı) nüshanın kimde olduğundan
ÖNCE koşar. Aksi hâlde görevli, gecikmesi olan ya da sınırı dolu bir üyenin kartıyla
barkodları tek tek deneyip "bu üyede / başka üyede" retlerinden üyenin elindeki
(gecikmiş) kitapları çıkarabilirdi; ret yazma yapmadığı ve kart geçerli olduğu için
hiçbir sayaç da artmazdı. Yıl sonu iletisi görevli kipinde tarih taşımaz: son
sınıflara ayrı tarih tanımlıysa tarih, kartın sahibinin son sınıfta olduğunu
gösterirdi (teknik borç TB32).

İADE TARİHİNİN KAYNAĞI Kapalı Günler'dir (`Holiday`). İade tarihinin düştüğü takvim
yılında resmî tatil ya da dini bayram kaydı yoksa kaydırma sessizce eksik kalırdı
(yıl dönümünde yeni yılın tatilleri girilmemişse); ödünç bu durumda bir UYARI döndürür
(`holidays_missing_warning`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.kutuphane import selectors_dolasim
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    CardlessReason,
    Copy,
    CopyStatus,
    Delivery,
    DeliveryStatus,
    LibraryPolicy,
    Loan,
    LoanStatus,
    Membership,
    MemberType,
    OverrideReason,
)
from apps.kutuphane.services import nusha_durumu
from apps.kutuphane.services.policy import LOAN_PERIOD_DAYS
from apps.kutuphane.services.yonetici_kipi import gorevli_kipinde_mi, require_admin_mode
from apps.okul.models import SchoolConfig, SchoolLevel
from shared.working_days import next_open_day

logger = logging.getLogger("kutuphane_defteri.kutuphane")

# ---------------------------------------------------------------------------
# Ret kodları (masa ekranının sözleşmesi — değişirse ön yüz de değişir)
# ---------------------------------------------------------------------------
RED_UYELIK = "uyelik_aktif_degil"
RED_PERSONEL = "personel_odunc_kapali"
RED_SON_TARIH = "son_odunc_tarihi"
RED_NUSHA_YOK = "nusha_bulunamadi"
RED_BU_UYEDE = "nusha_bu_uyede"
RED_BASKA_UYEDE = "nusha_baska_uyede"
RED_ODUNC_VERILMEZ = "odunc_verilmez"
RED_SINIR = "sinir_dolu"
RED_GECIKME = "gecikme_engeli"
RED_ACIK_ODUNC_YOK = "acik_odunc_yok"

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK; sözlük §5)
# ---------------------------------------------------------------------------
MEMBERSHIP_ENDED_MESSAGE = "Üyelik sonlanmış — ödünç verilemez."
MEMBER_LEFT_MESSAGE = "Üye okuldan ayrılmış — ödünç verilemez."
STAFF_LOANS_OFF_MESSAGE = "Diğer personele ödünç verilmiyor (Kütüphane Politikası)."
COPY_NOT_FOUND_MESSAGE = "Nüsha bulunamadı."
COPY_WITH_THIS_MEMBER_MESSAGE = "Bu kitap zaten bu üyede."
COPY_WITH_OTHER_MEMBER_MESSAGE = "Bu kitap başka bir üyede."
#: Açık teslimdeki nüsha (F7): nüsha durumunun iletisiyle aynı ("Sınıf kitaplığında").
DELIVERED_COPY_MESSAGE = f"{CopyStatus.DELIVERED.label} — ödünç verilemez."
#: Görevli kipinde gecikmesi olan üye için TEK ileti (eser adı ve gün YOK — §4.4).
OVERDUE_STAFF_MESSAGE = "Ödünç verilemiyor — kütüphane yöneticisine yönlendirin."
OVERDUE_ADMIN_MESSAGE = (
    "Üyenin gecikmiş ödüncü var. Önce iade alın ya da gerekçeli istisnayla ödünç verin."
)
#: Görevli kipinde yıl sonu reddi — TARİHSİZ (son sınıf tarihi sınıf düzeyini gösterirdi).
LAST_LOAN_DATE_STAFF_MESSAGE = (
    "Yıl sonu son ödünç tarihi geçti — yeni ödünç verilmez. İade alınabilir."
)
#: İade tarihinin düştüğü yılın resmî tatil ya da dini bayram kaydı yok (§9-5).
HOLIDAYS_MISSING_WARNING = (
    "{yil} yılının resmî tatil ya da dini bayram günleri Kapalı Günler'de eksik; iade "
    "tarihi bir tatile rastlamış olabilir. Kütüphane yöneticisi Ayarlar → Kapalı "
    "Günler'den eklemelidir."
)
OVERRIDE_NOTE_REQUIRED = "Gerekçeli istisnada açıklama zorunludur."
OVERRIDE_REASON_REQUIRED = "Açıklama yalnız gerekçeli istisnada yazılır; önce gerekçe seçin."
OVERRIDE_REASON_INVALID = "Geçerli bir gerekçe seçin."
CARDLESS_REASON_INVALID = "Kartsız ödünç için geçerli bir gerekçe seçin."
#: İstisna açıklamasının üst sınırı (karakter).
OVERRIDE_NOTE_MAX = 500

#: Açık ödüncü olmayan nüsha okutulunca (§7.3 "Boş | kitap") durum iletileri.
COPY_STATE_MESSAGES: dict[str, str] = {
    CopyStatus.AVAILABLE: "Rafta — ödünç değil.",
    CopyStatus.LOST: "Kayıp kaydında.",
    CopyStatus.IN_REPAIR: "Onarımda.",
    CopyStatus.DELIVERED: "Sınıf kitaplığında.",
    CopyStatus.ON_LOAN: "Ödünç kaydı bulunamadı — kütüphane yöneticisine yönlendirin.",
}
WITHDRAWN_COPY_MESSAGE = "Kayıttan düşülmüş nüsha."

#: Son sınıf (mezun olacak sınıf) seviyesi — kademeye göre (§8.3 yıl sonu akışı).
GRADUATING_LEVEL: dict[str, int] = {
    SchoolLevel.ILKOKUL: 4,
    SchoolLevel.ORTAOKUL: 8,
    SchoolLevel.ORTAOGRETIM: 12,
}


class DolasimReddi(APIException):
    """Dolaşım kuralı reddi — 400 + kararlı `code` (`RED_*`) + kişisel verisiz ileti.

    `kd_exception_handler` gövdenin `code`'unu `default_code`'dan okur; bu yüzden
    kod örnek özniteliği olarak da yazılır.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "dolasim_reddi"
    default_detail = "Ödünç işlemi yapılamadı."

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(detail=message, code=code)
        self.default_code = code

    @property
    def code(self) -> str:
        return str(self.default_code)

    @property
    def message(self) -> str:
        return str(self.detail)


@dataclass(frozen=True)
class CheckoutResult:
    """Ödünç sonucu: kayıt, uyarılar (ör. dönem sonu) ve iade tarihi kaydı mı."""

    loan: Loan
    warnings: tuple[str, ...] = ()
    due_date_shifted: bool = False


@dataclass(frozen=True)
class ReturnResult:
    """İade sonucu: kapanan ödünç ve (varsa) gecikme günü.

    Görevli kipinde ödünç alanın kimliği gösterilmez (§4.4): yanıtı daraltmak
    uç katmanının işidir; servis kaydı olduğu gibi döndürür.
    """

    loan: Loan
    overdue_days: int = 0


# ---------------------------------------------------------------------------
# İade tarihi (§9-5)
# ---------------------------------------------------------------------------
def raw_due_date(loan_day: date) -> date:
    """Md. 18: verilme günü + 15 (kaydırmasız)."""
    return loan_day + timedelta(days=LOAN_PERIOD_DAYS)


def due_date_for(loan_day: date, *, policy: LibraryPolicy | None = None) -> date:
    """İade tarihi: `loan_day + 15`, kapalı güne rastlarsa izleyen ilk açık gün.

    Öğrenciye kapalı gün (ara tatil, yarıyıl) yalnız politika ayarı açıksa
    atlanır; hafta sonu, resmî/dini tatil ve idari izin her zaman atlanır.
    """
    kural = policy or LibraryPolicy.load()
    return next_open_day(
        raw_due_date(loan_day), include_school_breaks=kural.shift_due_date_on_school_break
    )


def term_end_warning(loan_day: date, due: date) -> str:
    """İade tarihi, ödüncün verildiği dönemin sonunu aşıyorsa uyarı; aşmıyorsa ''.

    Süre KISALTILMAZ (§9-5): Md. 18 on beş gün der; uyarı yalnız yöneticinin
    dönem sonunda kitabı toplamayı planlaması içindir. Etkin ders yılı ya da
    ödünç gününü kapsayan dönem tanımlı değilse uyarı üretilmez.
    """
    from apps.okul import selectors as okul_selectors
    from apps.okul.services.terms import term_for_date

    yil = okul_selectors.active_school_year()
    if yil is None:
        return ""
    donem = term_for_date(yil, loan_day)
    if donem is None or due <= donem.end_date:
        return ""
    return (
        f"İade tarihi ({due:%d.%m.%Y}) dönem sonundan ({donem.end_date:%d.%m.%Y}) sonraya "
        "düşüyor. Süre kısaltılmaz."
    )


def holidays_missing_warning(loan_day: date, due: date) -> str:
    """İade tarihinin düştüğü takvim yılının kapalı günleri eksikse uyarı; değilse ''.

    Kaydırma yalnız Kapalı Günler'deki kayıtlara bakar (`next_open_day`). Tatilleri
    kurulum sihirbazı ve ders yılının aktifleştirilmesi tohumlar; ama bir takvim yılı
    hiç tohumlanmamışsa (ör. kayıtlar silinmiş, ders yılı başka yoldan açılmış) o yılın
    1 Ocak'ına ya da bayramına düşen iade tarihi kaydırılmaz ve ertesi gün sahte
    gecikme doğar. Yılda en az bir resmî tatil VE en az bir dini bayram kaydı beklenir
    (sabit tarihli resmî tatiller ile Ramazan ve Kurban bayramı her yıl vardır).
    Bakılan yıllar ham iade tarihinden (`loan_day + 15`) kaydırılmış tarihe kadardır.
    """
    from apps.okul.models import Holiday, HolidayKind

    yillar = range(raw_due_date(loan_day).year, due.year + 1)
    eksik = [
        yil
        for yil in yillar
        if not (
            Holiday.objects.filter(kind=HolidayKind.OFFICIAL, start_date__year=yil).exists()
            and Holiday.objects.filter(kind=HolidayKind.RELIGIOUS, start_date__year=yil).exists()
        )
    ]
    if not eksik:
        return ""
    return HOLIDAYS_MISSING_WARNING.format(yil=" ve ".join(str(y) for y in eksik))


# ---------------------------------------------------------------------------
# Yıl sonu son ödünç tarihi (§8.3)
# ---------------------------------------------------------------------------
def _is_graduating(membership: Membership) -> bool:
    ogrenci = membership.student
    if ogrenci is None or ogrenci.class_level is None:
        return False
    seviye = GRADUATING_LEVEL.get(SchoolConfig.load().kademe)
    return seviye is not None and ogrenci.class_level == seviye


def effective_last_loan_date(membership: Membership, *, policy: LibraryPolicy) -> date | None:
    """Üyeye uygulanan son ödünç tarihi; yoksa None.

    Son sınıf öğrencisine (kademenin son sınıfı) daha erken bir tarih
    tanımlanmışsa o uygulanır. **Eski yılın tarihi uygulanmaz:** etkin ders yılı
    tarihten SONRA başlamışsa (yeni yıla geçilmiş, ayar güncellenmemiş) kural
    düşer — geçen Haziran'ın tarihi Eylül'de bütün ödünçleri kilitlememelidir.
    """
    from apps.okul import selectors as okul_selectors

    adaylar = [policy.last_loan_date]
    # Kademe sorusu (SchoolConfig) yalnız son sınıf tarihi tanımlıysa sorulur.
    if policy.last_loan_date_graduating is not None and _is_graduating(membership):
        adaylar.append(policy.last_loan_date_graduating)
    tarihler = [t for t in adaylar if t is not None]
    if not tarihler:
        return None
    yil = okul_selectors.active_school_year()
    gecerli = [t for t in tarihler if yil is None or t >= yil.start_date]
    return min(gecerli) if gecerli else None


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def copy_state_message(copy: Copy) -> str:
    """Açık ödüncü olmayan nüshanın durum iletisi (§7.3; kişisel veri yok)."""
    if copy.status in TERMINAL_COPY_STATUSES:
        return WITHDRAWN_COPY_MESSAGE
    return COPY_STATE_MESSAGES.get(copy.status, str(copy.get_status_display()))


def _clean_override(override_reason: str, override_note: str) -> tuple[str, str]:
    """Gerekçe + açıklama biçim denetimi (kapalı liste; ikisi birlikte — D12)."""
    gerekce = (override_reason or "").strip()
    aciklama = (override_note or "").strip()
    if not gerekce and not aciklama:
        return "", ""
    if not gerekce:
        raise ValidationError({"override_reason": [OVERRIDE_REASON_REQUIRED]})
    if gerekce not in OverrideReason.values:
        raise ValidationError({"override_reason": [OVERRIDE_REASON_INVALID]})
    if not aciklama:
        raise ValidationError({"override_note": [OVERRIDE_NOTE_REQUIRED]})
    if len(aciklama) > OVERRIDE_NOTE_MAX:
        raise ValidationError(
            {"override_note": [f"Açıklama en çok {OVERRIDE_NOTE_MAX} karakter olabilir."]}
        )
    return gerekce, aciklama


def _clean_cardless(cardless_reason: str) -> str:
    gerekce = (cardless_reason or "").strip()
    if gerekce and gerekce not in CardlessReason.values:
        raise ValidationError({"cardless_reason": [CARDLESS_REASON_INVALID]})
    return gerekce


def _ensure_member_may_borrow(membership: Membership, *, policy: LibraryPolicy) -> None:
    """§9-1: aktif üyelik + aktif kişi; diğer personelde müdürlük kararı."""
    if not membership.is_active:
        raise DolasimReddi(MEMBERSHIP_ENDED_MESSAGE, code=RED_UYELIK)
    if not membership.person_is_active:
        raise DolasimReddi(MEMBER_LEFT_MESSAGE, code=RED_UYELIK)
    if membership.member_type == MemberType.STAFF and not policy.staff_loans_enabled:
        raise DolasimReddi(STAFF_LOANS_OFF_MESSAGE, code=RED_PERSONEL)


def _ensure_before_last_loan_date(
    membership: Membership, *, policy: LibraryPolicy, today: date, staff: bool
) -> None:
    """Yıl sonu son ödünç tarihi. Görevli kipinde ileti TARİHSİZDİR (modül başlığı)."""
    son = effective_last_loan_date(membership, policy=policy)
    if son is not None and today > son:
        if staff:
            raise DolasimReddi(LAST_LOAN_DATE_STAFF_MESSAGE, code=RED_SON_TARIH)
        raise DolasimReddi(
            f"Yıl sonu son ödünç tarihi ({son:%d.%m.%Y}) geçti — yeni ödünç verilmez. "
            "İade alınabilir.",
            code=RED_SON_TARIH,
        )


def _ensure_copy_loanable(copy: Copy, membership: Membership) -> None:
    """§9-7 ve §9-3: açık ödünçte ya da açık teslimdeki nüsha ve `is_loanable` dışı kaynak
    verilmez."""
    acik = Loan.objects.filter(copy_id=copy.pk, status=LoanStatus.OPEN).first()
    if acik is not None:
        ayni_kisi = acik.membership is not None and selectors_dolasim.person_key(
            acik.membership
        ) == selectors_dolasim.person_key(membership)
        if ayni_kisi:
            raise DolasimReddi(COPY_WITH_THIS_MEMBER_MESSAGE, code=RED_BU_UYEDE)
        raise DolasimReddi(COPY_WITH_OTHER_MEMBER_MESSAGE, code=RED_BASKA_UYEDE)
    if Delivery.objects.filter(copy_id=copy.pk, status=DeliveryStatus.OPEN).exists():
        # F7 tek açık kayıt: teslimdeki nüsha ödünç verilmez (durumu zaten "Sınıf
        # kitaplığında"dır; bu denetim tutarsız bir satıra karşı savunmadır).
        raise DolasimReddi(DELIVERED_COPY_MESSAGE, code=RED_ODUNC_VERILMEZ)
    if not copy.is_loanable:
        raise DolasimReddi(copy.not_loanable_reason, code=RED_ODUNC_VERILMEZ)


def _ensure_within_limit(membership: Membership, *, policy: LibraryPolicy) -> None:
    """Md. 18 sayı sınırı — HİÇBİR KİPTE istisna yok (gerekçe parametresi de yok)."""
    sinir = selectors_dolasim.loan_limit(membership, policy=policy)
    if selectors_dolasim.open_loan_count(membership) >= sinir:
        raise DolasimReddi(f"Ödünç sınırı dolu (en çok {sinir} kitap).", code=RED_SINIR)


def _overdue_exception_used(
    membership: Membership, *, policy: LibraryPolicy, today: date, reason: str, staff: bool
) -> bool:
    """Gecikme engeli (§9-6): engel yoksa `False`; gerekçe varsa istisna kullanılır (`True`).

    Gerekçe yalnız yönetici kipinde gelebilir (görevli kipinde `require_admin_mode`
    daha önce keser); görevli iletisi eser adı ve gecikme günü taşımaz (§4.4).
    """
    if not (policy.block_loan_if_overdue and selectors_dolasim.has_overdue(membership, on=today)):
        return False
    if not reason:
        raise DolasimReddi(
            OVERDUE_STAFF_MESSAGE if staff else OVERDUE_ADMIN_MESSAGE, code=RED_GECIKME
        )
    return True


# ---------------------------------------------------------------------------
# Ödünç ver
# ---------------------------------------------------------------------------
@transaction.atomic
def checkout(
    *,
    copy: Copy,
    membership: Membership,
    override_reason: str = "",
    override_note: str = "",
    cardless_reason: str = "",
) -> CheckoutResult:
    """Ödünç verir: kurallar sağlanınca `Loan` açar ve nüshayı "Ödünçte"ye alır.

    `override_reason` + `override_note`: gecikme engeli istisnası (yalnız
    yönetici kipi; kapalı liste + zorunlu açıklama). Engel yoksa (politika
    kapalı ya da gecikme yok) istisna KAYDA GEÇMEZ — gereksiz bir gerekçe
    ödünç kaydında yanıltıcı olurdu.

    `cardless_reason`: kartsız ödünç (yalnız yönetici kipi; kapalı liste).
    Kayıt `cardless=True` ile işaretlenir.

    Sayı sınırı ve Md. 16/1 kaynakları için parametre YOKTUR: hiçbir kipte
    istisna almazlar.
    """
    # 1. Kip: yönetici işleri görevli kipinde 403 (ara katman da keser — savunma).
    if (
        (override_reason or "").strip()
        or (override_note or "").strip()
        or (cardless_reason or "").strip()
    ):
        require_admin_mode()
    gerekce, aciklama = _clean_override(override_reason, override_note)
    kartsiz = _clean_cardless(cardless_reason)

    politika = LibraryPolicy.load()
    bugun = timezone.localdate()

    uyelik = selectors_dolasim.get_membership(membership.pk)
    if uyelik is None:
        raise DolasimReddi(MEMBERSHIP_ENDED_MESSAGE, code=RED_UYELIK)
    nusha = Copy.objects.select_related("work").filter(pk=copy.pk).first()
    if nusha is None:
        raise DolasimReddi(COPY_NOT_FOUND_MESSAGE, code=RED_NUSHA_YOK)

    gorevli = gorevli_kipinde_mi()
    _ensure_member_may_borrow(uyelik, policy=politika)
    _ensure_before_last_loan_date(uyelik, policy=politika, today=bugun, staff=gorevli)
    if gorevli:
        # Görevli kipinde üyeye bağlı engeller nüshanın kimde olduğundan ÖNCE (modül
        # başlığı): ret sırası üyenin elindeki kitapları ele vermez.
        istisna_kullanildi = _overdue_exception_used(
            uyelik, policy=politika, today=bugun, reason=gerekce, staff=True
        )
        _ensure_within_limit(uyelik, policy=politika)
        _ensure_copy_loanable(nusha, uyelik)
    else:
        _ensure_copy_loanable(nusha, uyelik)
        _ensure_within_limit(uyelik, policy=politika)
        istisna_kullanildi = _overdue_exception_used(
            uyelik, policy=politika, today=bugun, reason=gerekce, staff=False
        )

    ham_tarih = raw_due_date(bugun)
    iade_tarihi = due_date_for(bugun, policy=politika)
    try:
        with transaction.atomic():
            loan = Loan.objects.create(
                copy=nusha,
                membership=uyelik,
                loaned_at=timezone.now(),
                due_date=iade_tarihi,
                status=LoanStatus.OPEN,
                override_reason=gerekce if istisna_kullanildi else "",
                override_note=aciklama if istisna_kullanildi else "",
                cardless=bool(kartsiz),
                cardless_reason=kartsiz,
            )
    except IntegrityError as exc:
        # Yarış: aynı nüsha arada başka bir işlemde ödünç verildi (§9-7 DB kısıtı).
        raise DolasimReddi(COPY_WITH_OTHER_MEMBER_MESSAGE, code=RED_BASKA_UYEDE) from exc
    # §9-7 (F7): ödünç ile teslim arasındaki tek açık kayıt kuralının güvencesi —
    # "Rafta"dan çıkışı yalnız bir işlem kazanır (`services.nusha_durumu`). Kaybeden
    # ödünç, bu işlemle birlikte geri sarılır (hata `transaction.atomic`'ten çıkar).
    if not nusha_durumu.gecir(nusha.pk, eski=CopyStatus.AVAILABLE, yeni=CopyStatus.ON_LOAN):
        guncel = Copy.all_objects.select_related("work").get(pk=nusha.pk)
        raise DolasimReddi(
            guncel.not_loanable_reason or COPY_WITH_OTHER_MEMBER_MESSAGE, code=RED_ODUNC_VERILMEZ
        )
    nusha.status = CopyStatus.ON_LOAN

    if istisna_kullanildi:
        logger.info("Gecikme engeline gerekçeli istisnayla ödünç verildi.")
    if kartsiz:
        logger.info("Kartsız ödünç verildi.")

    uyarilar = tuple(
        u
        for u in (
            term_end_warning(bugun, iade_tarihi),
            holidays_missing_warning(bugun, iade_tarihi),
        )
        if u
    )
    return CheckoutResult(
        loan=loan,
        warnings=uyarilar,
        due_date_shifted=iade_tarihi != ham_tarih,
    )


# ---------------------------------------------------------------------------
# İade al
# ---------------------------------------------------------------------------
def _close_loan(loan: Loan) -> ReturnResult:
    gecikme = loan.overdue_days(timezone.localdate())
    loan.status = LoanStatus.RETURNED
    loan.returned_at = timezone.now()
    loan.save(update_fields=["status", "returned_at", "updated_at"])
    nusha = Copy.all_objects.get(pk=loan.copy_id)
    if nusha.status == CopyStatus.ON_LOAN:
        nusha.status = CopyStatus.AVAILABLE
        nusha.save(update_fields=["status", "updated_at"])
    return ReturnResult(loan=loan, overdue_days=gecikme)


@transaction.atomic
def return_copy(*, copy: Copy) -> ReturnResult:
    """Barkodla iade (§7.3; D9): nüshanın açık ödüncünü kapatır, nüsha "Rafta"ya döner.

    **Hiçbir durumda kilitlenmez**: kip, üyeliğin sonlanmış olması, gecikme,
    yıl sonu tarihi ya da sayım iadeyi durdurmaz (§9-8, §9-10; Md. 23/1-c).
    Açık ödüncü olmayan nüshada `DolasimReddi` (`RED_ACIK_ODUNC_YOK`) nüshanın
    durum iletisiyle döner ("Rafta — ödünç değil." …).
    """
    loan = (
        Loan.objects.select_related("copy", "copy__work", "membership")
        .filter(copy_id=copy.pk, status=LoanStatus.OPEN)
        .first()
    )
    if loan is None:
        nusha = Copy.all_objects.filter(pk=copy.pk).first()
        ileti = copy_state_message(nusha) if nusha is not None else COPY_NOT_FOUND_MESSAGE
        raise DolasimReddi(ileti, code=RED_ACIK_ODUNC_YOK)
    return _close_loan(loan)


@transaction.atomic
def return_loan(*, loan: Loan) -> ReturnResult:
    """Ödünç kaydından iade (yönetici listesinden); kurallar `return_copy` ile aynı."""
    guncel = (
        Loan.objects.select_related("copy", "copy__work", "membership").filter(pk=loan.pk).first()
    )
    if guncel is None or guncel.status != LoanStatus.OPEN:
        raise DolasimReddi("Bu ödünç zaten kapanmış.", code=RED_ACIK_ODUNC_YOK)
    return _close_loan(guncel)
