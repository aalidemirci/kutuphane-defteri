"""Dolaşım masası — okutmanın masadaki anlamı (tasarım §7.3, §4.4; GA-7).

Kurallar burada YAZILMAZ: ödünç ve iadenin bütün kuralları `services.circulation`'dadır
(§9). Bu modül masadaki okutmayı o kurallara bağlar:

* **Okutulan kodun çözümü** (`kitap_coz`): nüsha barkodu, ISBN barkodu, üye kartı,
  henüz bağlanmamış ya da iptal edilmiş boş etiket, tanınmayan kod (§7.1, F4 türleri).
  Her tür için kişisel veri taşımayan bir ileti vardır (sözlük §5).
* **Kartla üye çözme** (`uye_coz`) ve **GA-7 sayacı**: görevli kipinde art arda
  `GECERSIZ_KART_SINIRI` geçersiz kart okutması kart okutmayı durdurur; sürdürmek
  için yönetici parolası gerekir (`kart_kilidini_ac`). Kart no rastgeledir (D21);
  sayaç, numaralandırmayla ad çıkarmayı (masada komşu numaraları denemek) keser.
* **Masa yanıtları** (`*_yaniti`): görevli kipinde alan listesi DARALIR. Görevli
  kartla üye çözmede yalnız **ad** ve **kalan ödünç hakkını** görür (sınıf yok);
  iadede ödünç alanın kimliğini ve gecikme gününü görmez; nüsha özetinde yalnız
  barkod ve kaynak adı vardır (§4.4, sözlük §5). Alan listeleri `serializers_masa`
  sabitleridir ve anlık görüntüyle sınanır (§5.10-8).

GA-7 SAYACININ İKİ KURALI (F6 düzeltme turu). Görevli kipinde kart okutma şu iki
durumdan birinde durur ve yönetici parolası ister:

1. **Art arda** `GECERSIZ_KART_SINIRI` geçersiz okutma (iptal edilmiş, tanınmayan ya
   da sağlaması tutmayan). Geçerli bir kart okutması bu diziyi bozar: yıpranmış
   bir kartın birkaç kez yanlış okunması masayı kilitlemesin.
2. **Son `TANINMAYAN_KART_PENCERESI_SN` saniyede** `TANINMAYAN_KART_SINIRI`
   veritabanına sorulan geçersiz okutma (sağlaması tutan ama tanınmayan ya da iptal
   edilmiş kart). Bu sayıyı geçerli kart okutması SIFIRLAMAZ. Yalnız birinci kural
   olsaydı görevli dört rastgele numaradan sonra kendi kartını okutup sayacı sıfırlar,
   numaralandırmayı sınırsız sürdürebilirdi. Sağlaması tutmayan numara sayılmaz:
   veritabanına sorulmaz, kimseyi ele vermez; Luhn hanesini hesaplayıp deneyen biri
   ise her denemede buraya düşer.

Kilit bir kez kurulunca kendiliğinden kalkmaz; yalnız yönetici parolası kaldırır
(`kart_kilidini_ac`, yönetici kipindeki bir okutma ya da kilitleyip parolayla yeniden
açma). Sayaç süreç içidir (kip durumu gibi, T16) ve anahtar dönemine
(`crypto.key_epoch()`) bağlıdır. Yönetici kipinde sayılmaz ve kesmez (yönetici üye
listesini zaten görür); yönetici kipindeki bir okutma sayacı sıfırlar (masada
yönetici vardır).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from rest_framework import status
from rest_framework.exceptions import APIException

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import selectors_dolasim, selectors_sayim
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    CardlessReason,
    Copy,
    CopyStatus,
    LibraryPolicy,
    Loan,
    LoanStatus,
    Membership,
    OverrideReason,
    StockTakeStatus,
)
from apps.kutuphane.selectors_dolasim import REVOKED_CARD_MESSAGE, CardLookup, CardLookupState
from apps.kutuphane.serializers_masa import (
    ADMIN_CHECKOUT_FIELDS,
    ADMIN_COPY_FIELDS,
    ADMIN_COPY_STATUS_FIELDS,
    ADMIN_MEMBER_FIELDS,
    ADMIN_RETURN_FIELDS,
    ADMIN_STATUS_FIELDS,
    DESK_STATE_FIELDS,
    DESK_STOCKTAKE_FIELDS,
    OPEN_LOAN_FIELDS,
    RETURN_LOAN_FIELDS,
    STAFF_CHECKOUT_FIELDS,
    STAFF_COPY_FIELDS,
    STAFF_COPY_STATUS_FIELDS,
    STAFF_MEMBER_FIELDS,
    STAFF_RETURN_FIELDS,
    STAFF_STATUS_FIELDS,
)
from apps.kutuphane.services import barcode_reservations, circulation, label_queue
from apps.kutuphane.services.circulation import CheckoutResult, DolasimReddi, ReturnResult
from apps.okul.services import app_password
from shared import crypto

logger = logging.getLogger("kutuphane_defteri.kutuphane")

# ---------------------------------------------------------------------------
# Ret kodları (masa ekranının sözleşmesi; circulation.RED_* ile aynı uzayda)
# ---------------------------------------------------------------------------
RED_KART_IPTAL = "kart_iptal"
RED_KART_TANINMADI = "kart_taninmadi"
RED_KART_HATALI = "kart_hatali"
RED_GECERSIZ_KOD = "gecersiz_kod"
RED_UYELIK_YOK = "uyelik_bulunamadi"

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK — sözlük §5; iç kodlar yüzeye çıkmaz)
# ---------------------------------------------------------------------------
#: Kart biçimi ve sağlaması doğru, ama bu programda böyle bir kart yok.
CARD_UNKNOWN_MESSAGE = "Bu kart tanınmadı — kütüphane yöneticisine yönlendirin."
#: Sağlama hanesi tutmuyor ya da kart biçiminde değil (okuma ya da yazım hatası).
CARD_INVALID_MESSAGE = "Kart numarası hatalı. Kartı yeniden okutun."
#: Aktif üye çözüldü: sıradaki iş kitabı okutmak.
MEMBER_READY_MESSAGE = "Kitabın kütüphane etiketini okutun."
CHECKOUT_DONE_MESSAGE = "Ödünç verildi."
RETURN_DONE_MESSAGE = "İade alındı."
#: Nüsha durum sorgusunun iletileri (sorgu yazmaz; §7.3 "Boş | kitap" iletileri iadededir).
ON_LOAN_STATUS_MESSAGE = "Ödünçte."
AVAILABLE_STATUS_MESSAGE = "Rafta — ödünç verilebilir."
MEMBERSHIP_NOT_FOUND_MESSAGE = "Üyelik bulunamadı."

SCAN_EMPTY_MESSAGE = "Kitabın kütüphane etiketini ya da üye kartını okutun."
SCAN_MEMBER_CARD_MESSAGE = "Bu bir üye kartı. Kitabın kütüphane etiketini okutun."
SCAN_UNKNOWN_MESSAGE = "Bu kod tanınmadı. Kitabın kütüphane etiketini ya da üye kartını okutun."
SCAN_NO_COPY_MESSAGE = (
    "Bu barkodla kayıtlı nüsha yok. Kitabı ayırın ve kütüphane yöneticisine gösterin."
)
SCAN_DELETED_MESSAGE = (
    "Bu barkodun nüshası silinmiş. Kitabı ayırın ve kütüphane yöneticisine gösterin."
)
#: Boş barkod aralığı iletileri: yönetici kipinde Hızlı Kayıt yönergesi, görevli
#: kipinde yöneticiye yönlendirme (Hızlı Kayıt görevliye kapalıdır).
SCAN_RESERVED_MESSAGE = label_queue.VERIFY_RESERVED
SCAN_CANCELLED_MESSAGE = label_queue.VERIFY_CANCELLED
SCAN_RESERVED_STAFF_MESSAGE = f"Bu etiket henüz bir kitaba bağlanmadı. {label_queue.STAFF_REFER}"
SCAN_CANCELLED_STAFF_MESSAGE = (
    f"Bu etiketin numarası iptal edildi; kullanılamaz. {label_queue.STAFF_REFER}"
)

#: GA-7: art arda bu kadar geçersiz kart okutması kart okutmayı durdurur.
GECERSIZ_KART_SINIRI: Final = 5
#: GA-7: bu süre içinde bu kadar tanınmayan ya da iptal edilmiş kart okutması da
#: durdurur; geçerli kart okutması bu sayıyı sıfırlamaz (modül başlığı, kural 2).
TANINMAYAN_KART_SINIRI: Final = 5
TANINMAYAN_KART_PENCERESI_SN: Final = 10 * 60
_KILIT_SONU = "Kart okutmaya devam etmek için kütüphane yöneticisi yönetici parolasını girmelidir."
KART_KILIDI_MESSAGE = f"Art arda {GECERSIZ_KART_SINIRI} geçersiz kart okutuldu. {_KILIT_SONU}"
KART_KILIDI_PENCERE_MESSAGE = (
    f"Son {TANINMAYAN_KART_PENCERESI_SN // 60} dakikada {TANINMAYAN_KART_SINIRI} tanınmayan ya "
    f"da iptal edilmiş kart okutuldu. {_KILIT_SONU}"
)
KART_KILIDI_ACILDI_MESSAGE = "Kart okutma yeniden açıldı."

#: Yönetici kipindeki üye bağlamında gösterilen açık ödünç satırı üst sınırı
#: (Md. 18 sınırı 3/5'tir; sınır, bozuk bir aktarımda yanıtın büyümesine karşı sigorta).
UYE_ACIK_ODUNC_LISTESI_SINIRI: Final = 50


class KartOkutmaKilidi(APIException):
    """GA-7 — görevli kipinde geçersiz kart okutmaları: 429 `kart_okutma_kilidi`.

    İleti kilidin nedenini söyler (art arda ya da son on dakikadaki okutmalar).
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "kart_okutma_kilidi"
    default_detail = KART_KILIDI_MESSAGE

    def __init__(self, message: str = KART_KILIDI_MESSAGE) -> None:
        super().__init__(detail=message)


# ---------------------------------------------------------------------------
# GA-7 sayacı
# ---------------------------------------------------------------------------
class GecersizKartSayaci:
    """Görevli kipinde geçersiz kart okutmalarını sayar (süreç içi, iş parçacığı güvenli).

    İki kural (modül başlığı): art arda geçersiz okutma (geçerli okutma diziyi bozar)
    ve pencere içinde veritabanına sorulan geçersiz okutma (geçerli okutma SIFIRLAMAZ).
    Kilit kurulunca yalnız `sifirla` (yönetici parolası) kaldırır. Anahtar dönemi
    değişince (kilitlenip parolayla yeniden açılınca) sıfırdan başlar.
    """

    def __init__(
        self,
        sinir: int = GECERSIZ_KART_SINIRI,
        *,
        pencere_siniri: int = TANINMAYAN_KART_SINIRI,
        pencere_sn: float = TANINMAYAN_KART_PENCERESI_SN,
        saat: Callable[[], float] = time.monotonic,
    ) -> None:
        self._kilit = threading.Lock()
        self._sinir = sinir
        self._pencere_siniri = pencere_siniri
        self._pencere_sn = pencere_sn
        self._saat = saat
        self._sayi = 0
        self._sorulanlar: deque[float] = deque()
        self._neden: str | None = None
        self._donem: int | None = None

    def _bosalt(self) -> None:
        self._sayi = 0
        self._sorulanlar.clear()
        self._neden = None

    def _doneme_bak(self) -> None:
        donem = crypto.key_epoch()
        if donem != self._donem:
            self._donem = donem
            self._bosalt()

    @property
    def sayi(self) -> int:
        """Art arda geçersiz okutma sayısı (birinci kural)."""
        with self._kilit:
            self._doneme_bak()
            return self._sayi

    def kilit_iletisi(self) -> str | None:
        """Kilitliyse nedenini söyleyen ileti; değilse None."""
        with self._kilit:
            self._doneme_bak()
            return self._neden

    def kilitli_mi(self) -> bool:
        return self.kilit_iletisi() is not None

    def gecersiz(self, *, veritabanina_soruldu: bool = False) -> str | None:
        """Bir geçersiz okutma kaydeder; kilit kurulduysa (ya da zaten varsa) iletisi.

        `veritabanina_soruldu`: sağlaması tutan ama tanınmayan ya da iptal edilmiş kart
        (ikinci kurala da sayılır).
        """
        with self._kilit:
            self._doneme_bak()
            self._sayi += 1
            simdi = self._saat()
            if veritabanina_soruldu:
                self._sorulanlar.append(simdi)
            while self._sorulanlar and simdi - self._sorulanlar[0] > self._pencere_sn:
                self._sorulanlar.popleft()
            if self._neden is None:
                if self._sayi >= self._sinir:
                    self._neden = KART_KILIDI_MESSAGE
                elif len(self._sorulanlar) >= self._pencere_siniri:
                    self._neden = KART_KILIDI_PENCERE_MESSAGE
            return self._neden

    def gecerli(self) -> None:
        """Geçerli kart okutması: yalnız ART ARDA diziyi bozar (pencere sayısı kalır)."""
        with self._kilit:
            self._doneme_bak()
            self._sayi = 0

    def sifirla(self) -> None:
        """Yönetici parolası girildi: iki sayı da sıfırlanır, kilit kalkar."""
        with self._kilit:
            self._doneme_bak()
            self._bosalt()

    def _reset_for_tests(self) -> None:
        with self._kilit:
            self._bosalt()
            self._donem = None


GECERSIZ_KARTLAR = GecersizKartSayaci()


def uye_coz(value: object, *, staff: bool) -> CardLookup:
    """Okutulan kartı üyeliğe çözer; görevli kipinde GA-7 sayacını işletir.

    Görevli kipinde kilit varsa ya da bu okutma kilidi kurduysa `KartOkutmaKilidi`
    (429). Numara `find_membership_by_card` ile kör indeksten, TAM eşleşmeyle
    çözülür (T14); sağlaması tutmayan numara veritabanına sorulmaz.
    """
    if not staff:
        GECERSIZ_KARTLAR.sifirla()
        return selectors_dolasim.find_membership_by_card(value)
    ileti = GECERSIZ_KARTLAR.kilit_iletisi()
    if ileti is not None:
        raise KartOkutmaKilidi(ileti)
    sonuc = selectors_dolasim.find_membership_by_card(value)
    if sonuc.state == CardLookupState.FOUND:
        GECERSIZ_KARTLAR.gecerli()
        return sonuc
    ileti = GECERSIZ_KARTLAR.gecersiz(
        veritabanina_soruldu=sonuc.state in (CardLookupState.UNKNOWN, CardLookupState.REVOKED)
    )
    if ileti is not None:
        logger.warning("Geçersiz kart okutması sınırı doldu; kart okutma durduruldu.")
        raise KartOkutmaKilidi(ileti)
    return sonuc


def kart_kilidini_ac(password: str) -> None:
    """GA-7 kilidini yönetici parolasıyla açar. Yanlış parola `AppPasswordError`
    (kademeli gecikmeyle — `app_password.verify_password`)."""
    app_password.verify_password(password)
    GECERSIZ_KARTLAR.sifirla()


def card_state_message(lookup: CardLookup) -> str:
    """Kart okutmasının kişisel veri taşımayan iletisi."""
    if lookup.state == CardLookupState.REVOKED:
        return REVOKED_CARD_MESSAGE
    if lookup.state == CardLookupState.UNKNOWN:
        return CARD_UNKNOWN_MESSAGE
    if lookup.state == CardLookupState.INVALID:
        return CARD_INVALID_MESSAGE
    uyelik = lookup.membership
    assert uyelik is not None
    if not uyelik.is_active:
        return circulation.MEMBERSHIP_ENDED_MESSAGE
    if not uyelik.person_is_active:
        return circulation.MEMBER_LEFT_MESSAGE
    return MEMBER_READY_MESSAGE


def card_rejection(lookup: CardLookup) -> DolasimReddi:
    """Ödünçte okutulan kart çözülemediyse dönen ret (kod + ileti)."""
    kodlar = {
        CardLookupState.REVOKED: RED_KART_IPTAL,
        CardLookupState.UNKNOWN: RED_KART_TANINMADI,
        CardLookupState.INVALID: RED_KART_HATALI,
    }
    return DolasimReddi(card_state_message(lookup), code=kodlar[lookup.state])


# ---------------------------------------------------------------------------
# Kitap okutması
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KitapOkutmasi:
    """Okutulan kodun masadaki çözümü: kullanılabilir nüsha YA DA ret iletisi."""

    kind: ScanKind
    copy: Copy | None
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.copy is not None and not self.message


def kitap_coz(value: object, *, staff: bool) -> KitapOkutmasi:
    """Okutulan kodu nüshaya çözer (§7.1, F4 türleri). Nüsha yoksa ileti döner.

    Kayıttan düşülmüş nüsha KULLANILABİLİR döner: iadesi alınabilir (iade hiçbir
    durumda kilitlenmez); ödünçte `is_loanable` onu zaten reddeder.
    """
    info = barcode_reservations.describe_scan(value)
    if not info.digits:
        return KitapOkutmasi(info.kind, None, SCAN_EMPTY_MESSAGE)
    if info.kind == ScanKind.ISBN:
        return KitapOkutmasi(info.kind, None, barcode_module.ISBN_SCAN_MESSAGE)
    if info.kind == ScanKind.MEMBER_CARD:
        return KitapOkutmasi(info.kind, None, SCAN_MEMBER_CARD_MESSAGE)
    if info.kind == ScanKind.RESERVED:
        ileti = SCAN_RESERVED_STAFF_MESSAGE if staff else SCAN_RESERVED_MESSAGE
        return KitapOkutmasi(info.kind, None, ileti)
    if info.kind == ScanKind.CANCELLED:
        ileti = SCAN_CANCELLED_STAFF_MESSAGE if staff else SCAN_CANCELLED_MESSAGE
        return KitapOkutmasi(info.kind, None, ileti)
    if info.kind != ScanKind.COPY:
        return KitapOkutmasi(info.kind, None, SCAN_UNKNOWN_MESSAGE)
    nusha = info.copy
    if nusha is None:
        return KitapOkutmasi(info.kind, None, SCAN_NO_COPY_MESSAGE)
    if nusha.deleted_at is not None:
        return KitapOkutmasi(info.kind, None, SCAN_DELETED_MESSAGE)
    return KitapOkutmasi(info.kind, nusha)


def book_rejection(okutma: KitapOkutmasi) -> DolasimReddi:
    """Ödünçte okutulan kod kullanılabilir bir nüsha değilse dönen ret."""
    kod = RED_GECERSIZ_KOD
    if okutma.message in (SCAN_NO_COPY_MESSAGE, SCAN_DELETED_MESSAGE):
        kod = circulation.RED_NUSHA_YOK
    return DolasimReddi(okutma.message, code=kod)


# ---------------------------------------------------------------------------
# Yanıt parçaları — görevli kipinde DARALIR (alan listeleri `serializers_masa`)
# ---------------------------------------------------------------------------
def _sec(veri: dict[str, Any], alanlar: tuple[str, ...]) -> dict[str, Any]:
    return {alan: veri[alan] for alan in alanlar}


def nusha_ozeti(copy: Copy, *, staff: bool) -> dict[str, Any]:
    """Masada gösterilen nüsha özeti (kişisel veri yok)."""

    veri = {
        "id": copy.pk,
        "barcode": copy.barcode,
        "barcode_display": barcode_module.format_barcode(copy.barcode),
        "work_title": copy.work.title,
        "call_number": copy.work.call_number,
        "status": copy.status,
        "status_display": str(copy.get_status_display()),
    }
    return _sec(veri, STAFF_COPY_FIELDS if staff else ADMIN_COPY_FIELDS)


def nusha_durumu(copy: Copy, *, staff: bool) -> dict[str, Any]:
    """Nüsha durum sorgusunun özeti: durum + ödünç verilebilirlik (kişisel veri yok)."""

    veri = {
        **nusha_ozeti(copy, staff=False),
        "is_loanable": copy.is_loanable,
        "not_loanable_reason": copy.not_loanable_reason,
    }
    return _sec(veri, STAFF_COPY_STATUS_FIELDS if staff else ADMIN_COPY_STATUS_FIELDS)


def _acik_odunc_satiri(loan: Loan) -> dict[str, Any]:
    veri = {
        "id": loan.pk,
        "barcode": loan.copy.barcode,
        "barcode_display": barcode_module.format_barcode(loan.copy.barcode),
        "work_title": loan.copy.work.title,
        "loaned_at": loan.loaned_at,
        "due_date": loan.due_date,
        "overdue_days": loan.overdue_days(),
        "cardless": loan.cardless,
        "has_override": loan.has_override,
    }
    return _sec(veri, OPEN_LOAN_FIELDS)


def uye_ozeti(
    membership: Membership, *, staff: bool, policy: LibraryPolicy | None = None
) -> dict[str, Any]:
    """Üye bağlamı. Görevli: YALNIZ ad + kalan hak (sınıf yok — §4.4, sözlük §5)."""

    kural = policy or LibraryPolicy.load()
    kalan = selectors_dolasim.remaining_quota(membership, policy=kural)
    if staff:
        return _sec(
            {"full_name": membership.full_name, "remaining_quota": kalan}, STAFF_MEMBER_FIELDS
        )
    ogrenci = membership.student
    acik = selectors_dolasim.open_loans_for_person(membership.person)
    veri = {
        "membership_id": membership.pk,
        "full_name": membership.full_name,
        "member_type": membership.member_type,
        "member_type_display": membership.get_member_type_display(),
        "class_label": ogrenci.class_label if ogrenci is not None else "",
        "status": membership.status,
        "status_display": str(membership.get_status_display()),
        "person_is_active": membership.person_is_active,
        "loan_limit": selectors_dolasim.loan_limit(membership, policy=kural),
        "open_loan_count": acik.count(),
        "overdue_loan_count": selectors_dolasim.overdue_loan_count(membership),
        "remaining_quota": kalan,
        "open_loans": [_acik_odunc_satiri(lo) for lo in acik[:UYE_ACIK_ODUNC_LISTESI_SINIRI]],
    }
    return _sec(veri, ADMIN_MEMBER_FIELDS)


def kart_yaniti(lookup: CardLookup, *, staff: bool) -> dict[str, Any]:
    """`POST library/desk/member/` gövdesi — `{state, message, member}`."""
    uye = (
        uye_ozeti(lookup.membership, staff=staff)
        if lookup.state == CardLookupState.FOUND and lookup.membership is not None
        else None
    )
    return {"state": str(lookup.state), "message": card_state_message(lookup), "member": uye}


def odunc_yaniti(sonuc: CheckoutResult, *, staff: bool) -> dict[str, Any]:
    """`POST library/checkout/` gövdesi (201)."""

    loan = sonuc.loan
    uyelik = loan.membership
    assert uyelik is not None
    veri = {
        "message": CHECKOUT_DONE_MESSAGE,
        "loan_id": loan.pk,
        "copy": nusha_ozeti(loan.copy, staff=staff),
        "due_date": loan.due_date,
        "due_date_shifted": sonuc.due_date_shifted,
        "warnings": list(sonuc.warnings),
        "cardless": loan.cardless,
        "cardless_reason_display": _etiket(CardlessReason, loan.cardless_reason),
        "has_override": loan.has_override,
        "override_reason_display": _etiket(OverrideReason, loan.override_reason),
        "member": uye_ozeti(uyelik, staff=staff),
    }
    return _sec(veri, STAFF_CHECKOUT_FIELDS if staff else ADMIN_CHECKOUT_FIELDS)


def _etiket(secenekler: Any, kod: object) -> str:
    deger = str(kod or "")
    return str(secenekler(deger).label) if deger in secenekler.values else ""


def _iade_ayrintisi(sonuc: ReturnResult) -> dict[str, Any]:
    """Yönetici kipinde iadenin ayrıntısı: kimden alındı, gecikme."""

    loan = sonuc.loan
    uyelik = loan.membership
    ogrenci = uyelik.student if uyelik is not None else None
    veri = {
        "id": loan.pk,
        "member_name": uyelik.full_name if uyelik is not None else "",
        "class_label": ogrenci.class_label if ogrenci is not None else "",
        "loaned_at": loan.loaned_at,
        "due_date": loan.due_date,
        "overdue_days": sonuc.overdue_days,
        "cardless": loan.cardless,
    }
    return _sec(veri, RETURN_LOAN_FIELDS)


def iade_yaniti(
    result: str,
    okutma: KitapOkutmasi,
    message: str,
    *,
    staff: bool,
    iade: ReturnResult | None = None,
) -> dict[str, Any]:
    """`POST library/return/` gövdesi (her zaman 200 — okutma bir olaydır)."""

    veri = {
        "result": result,
        "kind": str(okutma.kind),
        "message": message,
        "copy": nusha_ozeti(okutma.copy, staff=staff) if okutma.copy is not None else None,
        "loan": _iade_ayrintisi(iade) if iade is not None else None,
    }
    return _sec(veri, STAFF_RETURN_FIELDS if staff else ADMIN_RETURN_FIELDS)


# ---------------------------------------------------------------------------
# Masa işlemleri
# ---------------------------------------------------------------------------
IADE_ALINDI = "returned"
ODUNCTE_DEGIL = "not_on_loan"
REDDEDILDI = "rejected"


def iade_okut(value: object, *, staff: bool) -> dict[str, Any]:
    """Boş bağlamda kitap okutması (§7.3): açık ödünçteyse İADE, değilse durum iletisi.

    İade hiçbir durumda kilitlenmez (§9-8, §9-10). Görevli kipinde ödünç alanın
    kimliği ve gecikme günü yanıta girmez; yönetici kipinde iletiye gecikme eklenir.
    """
    okutma = kitap_coz(value, staff=staff)
    if not okutma.usable or okutma.copy is None:
        return iade_yaniti(REDDEDILDI, okutma, okutma.message, staff=staff)
    nusha_pk = okutma.copy.pk

    def guncel() -> KitapOkutmasi:
        # Nüsha tazelenir: yanıttaki durum iadeden sonraki durum olsun.
        return KitapOkutmasi(okutma.kind, Copy.all_objects.select_related("work").get(pk=nusha_pk))

    try:
        iade = circulation.return_copy(copy=okutma.copy)
    except DolasimReddi as ret:
        if ret.code != circulation.RED_ACIK_ODUNC_YOK:
            raise
        return iade_yaniti(ODUNCTE_DEGIL, guncel(), ret.message, staff=staff)
    ileti = RETURN_DONE_MESSAGE
    if not staff and iade.overdue_days > 0:
        ileti = f"{ileti} {iade.overdue_days} gün gecikti."
    return iade_yaniti(IADE_ALINDI, guncel(), ileti, staff=staff, iade=iade)


def masa_durumu() -> dict[str, Any]:
    """Masanın ve görevli ekranının KİŞİSİZ durumu (F9 — madde 24, 26; iki kipte aynı).

    - `service_pause`: sayım için hizmet arası sürüyor mu (yeni ödünç ve teslim durur;
      şerit açılışta çizilir — görevli kipinde de, ilk retten önce);
    - `stocktake_scan`: okutması açık süren sayım (`{id, round}`) ya da `None`. Görevli
      ekranı "Sayım okutmasını aç" düğmesini buna göre gösterir. Taslak, tamamlanmış ve
      onaylanmış sayım okutulmaz.
    """
    canli = selectors_sayim.locking_stocktake()
    okutma = None
    if canli is not None and canli.status == StockTakeStatus.IN_PROGRESS:
        okutma = _sec({"id": canli.pk, "round": canli.round}, DESK_STOCKTAKE_FIELDS)
    return _sec(
        {"service_pause": selectors_sayim.service_pause_active(), "stocktake_scan": okutma},
        DESK_STATE_FIELDS,
    )


def durum_sorgula(value: object, *, staff: bool) -> dict[str, Any]:
    """Nüsha durum sorgusu — yazma YOK. `{kind, message, copy, loan}` (loan yalnız yönetici)."""
    okutma = kitap_coz(value, staff=staff)
    veri: dict[str, Any] = {
        "kind": str(okutma.kind),
        "message": okutma.message,
        "copy": None,
        "loan": None,
    }
    if okutma.usable:
        assert okutma.copy is not None
        nusha = okutma.copy
        acik = (
            Loan.objects.select_related(
                "membership", "membership__student", "membership__personnel"
            )
            .filter(copy_id=nusha.pk, status=LoanStatus.OPEN)
            .first()
        )
        veri["copy"] = nusha_durumu(nusha, staff=staff)
        if acik is not None:
            veri["message"] = ON_LOAN_STATUS_MESSAGE
            uyelik = acik.membership
            ogrenci = uyelik.student if uyelik is not None else None
            veri["loan"] = {
                "member_name": uyelik.full_name if uyelik is not None else "",
                "class_label": ogrenci.class_label if ogrenci is not None else "",
                "loaned_at": acik.loaned_at,
                "due_date": acik.due_date,
                "overdue_days": acik.overdue_days(),
            }
        elif nusha.status == CopyStatus.AVAILABLE:
            veri["message"] = nusha.not_loanable_reason or AVAILABLE_STATUS_MESSAGE
        else:
            veri["message"] = circulation.copy_state_message(nusha)
    return _sec(veri, STAFF_STATUS_FIELDS if staff else ADMIN_STATUS_FIELDS)


def odunc_ver(
    *,
    barcode: object,
    card_no: object = "",
    membership: Membership | None = None,
    override_reason: str = "",
    override_note: str = "",
    cardless_reason: str = "",
    staff: bool,
) -> dict[str, Any]:
    """Üye bağlamında kitap okutması (§7.3): kurallar sağlanınca ödünç verir.

    Üye kartla (`card_no`) ya da — yalnız yönetici kipinde, kartsız ödünçte —
    üyelik kaydıyla (`membership`) gelir. Kart ödünç anında YENİDEN çözülür:
    görevli kipinde üyeyi kanıtlayan tek şey okutulan karttır (üyelik kimliğiyle
    ödünç görevliye kapalıdır; aksi hâlde kartsız ödünç kapısı aşılırdı).
    """
    if membership is None:
        lookup = uye_coz(card_no, staff=staff)
        if lookup.state != CardLookupState.FOUND or lookup.membership is None:
            raise card_rejection(lookup)
        membership = lookup.membership
    okutma = kitap_coz(barcode, staff=staff)
    if not okutma.usable:
        raise book_rejection(okutma)
    assert okutma.copy is not None
    sonuc = circulation.checkout(
        copy=okutma.copy,
        membership=membership,
        override_reason=override_reason,
        override_note=override_note,
        cardless_reason=cardless_reason,
    )
    return odunc_yaniti(sonuc, staff=staff)
