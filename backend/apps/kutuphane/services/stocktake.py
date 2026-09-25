"""Sayım — TMY 32 (F9; tasarım §6.2, §9-10, §9-11, §10 E10, §13 D1, D4, D16, D17, D18).

OYS `apps/kutuphane/stocktake.py`'den UYARLA (tasarım §12): `by_user` ve
`approved_by` (kullanıcı hesabı) düştü — harcama yetkilisinin adı şifreli serbest
metindir; iki tur "Sürüyor" durumunun içinde tur sayacı oldu; devralınan kusurlar
düzeltildi:

- **D1** atıflar metinden: noksanın düşüm teklifi **32/7** (OYS 32/6 diyordu; 32/6
  yeniden sayımdır), ödünçteki/teslimdeki nüsha **32/5** (OYS 32/4), sayım fazlasının
  girişi **TMY 17** ve 32/7.
- **D4** TMY 32/3 durdurması kayıp bildirimini ve kayıp dosyası çözümünü de kapsar
  (`services.tmy_kapisi`).
- **D16** sayım fazlasının okutulan kodu `StockTakeItem.surplus_barcode`'dadır; OYS
  onu yeni nüshanın raf alanına yazıyordu. Burada hiçbir nüsha alanına yazılmaz.
- **D17** seçilen kilitler "Tamamlandı"da da sürer, onaya ya da iptale dek; onayda
  her noksan kalem YENİDEN doğrulanır, durumu değişen düşülmez.
- **D18** TMY 32/3 isteğe bağlıdır; iade hiçbir durumda kilitlenmez (OYS ödüncü ve
  iadeyi birlikte kilitliyordu).

KURALLAR (her biri testle kilitli — `tests/test_sayim.py`):

1. **İki AYRI seçenek**, taslakta seçilir ve başlatmadan sonra değişmez: TMY 32/3
   durdurması (kurulun talep tarihi, harcama yetkilisinin adı ve durdurma tarihi
   zorunlu — 32/3) ve sayım için hizmet arası (okul kararı; yeni ödüncü ve yeni
   teslimi durdurur — `services.circulation`, `services.deliveries`). Kilitler
   "Sürüyor" ve "Tamamlandı"da sürer.
2. **İade ve teslimden geri alma hiçbir durumda kilitlenmez** (Md. 23/1-c). Sayım
   sırasında iade edilen, teslimden geri alınan, kayıp dosyasında bulunan ya da
   onarımdan dönen nüsha o turda "bulundu" sayılır (`selectors_sayim.return_event_q`).
3. **Sayım kurulu** (32/2): başkan (harcama yetkilisi ya da görevlendirdiği kişi),
   taşınır kayıt yetkilisi ve en az üç FARKLI kişi; adlar ŞİFRELİ. Aynı anda tek
   canlı sayım (taslak dahil).
4. **Anlık görüntü** başlatmada alınır: kayıtlı her nüsha (kayıttan düşülmüş,
   devredilmiş ve silinmiş hariç) beklenen durumu, teslim türü, bölümü ve sınıf
   kitaplığıyla bir kalem olur. Sayım sırasındaki değişiklikler onu değiştirmez;
   sayım başladıktan sonra kayda giren nüsha "kapsam dışı"dır.
5. **Ödünçteki, teslimdeki ve onarımdaki nüsha** için kurul seçer (§9-11, AT-1):
   sayımdan önce toplanır (onarımda "geri alınır") · sınıf kitaplığında yerinde
   sayılır (32/5 birinci cümleye kıyasen) · kayda göre alınır (öğretmene teslimde 32/5
   ikinci cümle ya da 32/5'e kıyasen — 23/4; ödünçte 32/5'e kıyasen — 23/4; onarımda
   sayım kurulunun kararı, TMY'de doğrudan hüküm yok — F9 ekleri K2). Açık ödünçteki,
   öğretmendeki ya da onarımdaki nüsha noksan sayılmaz: kayda göre alınır
   (toplanamadıysa işaretlidir). SINIF KİTAPLIĞI için "kayda göre" YOKTUR (K3): orada
   bulunmayan nüsha — yerinde sayılıp bulunmayan ya da toplanamayıp yerinde de
   bulunmayan — noksandır (32/5 birinci cümle).
6. **Okutma kuyruğu**: tek istekte en çok `MAX_SCANS_PER_REQUEST` kod; her kod ayrı
   sonuç döner ve aynı kodu ikinci kez okutmak zararsızdır (hızlı okutmada kayıp
   yok). ISBN ve üye kartı reddedilir (kaydedilmez). Okutma GÖREVLİ KİPİNDE de açıktır
   (madde 24, 25.09.2026 kullanıcı kararı); sayımın öbür bütün işleri yönetici işidir.
7. **Tamamla** (32/6): ilk turda noksan varsa ikinci sayıma geçilir — bulunamayanlar
   bir kez daha aranır; ikinci turdan sonra sonuçlar yazılır, durum "Tamamlandı".
8. **Onay** (TEK işlem): harcama yetkilisinin adı ve onay tarihi zorunlu (10/1-e: sayım
   tutanağı durumu belgeleyen tutanaktır, komisyon kurulmadan onaylanır); onay tarihi
   sayımın tamamlandığı günden önce ve bugünden sonra olamaz (10/1-a). Önce kilitler
   kalkar, sonra: her noksan yeniden doğrulanır (D17) ve düşülür (32/7 — kayıptaki
   nüsha "Kayıp (kayıttan düşüldü)", ötekiler "Sayım noksanı (kayıttan düşüldü)");
   hasar önerileri 27/1 + 10/1-e yolundan düşülür ("Hasar (kayıttan düşüldü)" — F8
   ekleri 34); kayıpta görünüp bulunan nüshanın kayıp dosyası "Bulundu" ile kapanır
   (LOST uzlaştırma); sayım fazlası tek "Sayım fazlası (kayda giriş)" edinimiyle
   kayda girer (TMY 17). Harcama yetkilisinin onaylamadığı kalem gerekçesiyle
   işaretlenir, kayıtta kalır.
9. **İptal**: onaylanmamış sayım her adımda iptal edilir; kilitler kalkar, anlık
   görüntü iz olarak kalır.
10. Okutma dışında yalnız yönetici kipinde (`require_admin_mode`); şifreli adlar parola
    kurulmadan yazılmaz (`KeyMissingError` → 409; servis ayrıca `require_password_set`
    sorar).

Hata ve günlük metinleri KİŞİ ADI İÇERMEZ.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import keys, selectors_sayim
from apps.kutuphane.barcode import ScanKind
from apps.kutuphane.models import (
    FOUND_RESOLUTIONS,
    LOAN_BASIS_CHOICES,
    OPEN_CASE_RESOLUTIONS,
    OPEN_STOCKTAKE_STATUSES,
    REPAIR_BASIS_CHOICES,
    SECTION_DELIVERY_BASIS_CHOICES,
    STOCKTAKE_COMMITTEE_MIN_MEMBERS,
    TEACHER_DELIVERY_BASIS_CHOICES,
    TERMINAL_COPY_STATUSES,
    AcquisitionMethod,
    CaseType,
    Copy,
    CopyRepair,
    CopyStatus,
    CountBasis,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    Loan,
    LoanStatus,
    LossDamageCase,
    ResourceType,
    StockTake,
    StockTakeFoundVia,
    StockTakeItem,
    StockTakeOutcome,
    StockTakeResult,
    StockTakeStatus,
    StockTakeWriteOffPath,
    Work,
)
from apps.kutuphane.services import barcode_reservations, catalog, loss_damage, nusha_durumu
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul.services import app_password

logger = logging.getLogger("kutuphane_defteri.kutuphane")

#: Tek istekte okutulabilecek en çok kod (okuyucu kuyruğu — geri alma okutmasıyla aynı).
MAX_SCANS_PER_REQUEST: Final = 200
#: Ad ve metin alanlarının üst sınırları (modelle aynı).
NAME_MAX: Final = 120
TEXT_MAX: Final = 255
MEMBERS_MAX: Final = 2000
NOTES_MAX: Final = 2000
SURPLUS_BARCODE_MAX: Final = 32

# ---------------------------------------------------------------------------
# İletiler (kişisel veri YOK — sözlük: sayım, sayım kurulu, TMY 32/3 durdurması,
# sayım için hizmet arası; "sayım kilidi" ve "dondurma" kullanılmaz)
# ---------------------------------------------------------------------------
STATE_MESSAGES: Final[dict[str, str]] = {
    "draft_only": "Bu işlem yalnız taslak sayımda yapılır; sayım başladıktan sonra seçenekler "
    "ve kurul değişmez.",
    "start": "Yalnız taslak sayım başlatılır.",
    "scan": "Okutma yalnız süren sayımda yapılır.",
    "complete": "Yalnız süren sayım tamamlanır.",
    "approve": "Yalnız tamamlanmış sayım onaylanır.",
    "cancel": "Onaylanmış ya da iptal edilmiş sayım iptal edilemez.",
    "surplus_add": "Sayım fazlası yalnız süren sayımda eklenir ya da çıkarılır.",
    "surplus_edit": "Sayım fazlası yalnız süren ya da tamamlanmış sayımda düzenlenir.",
}
STOCKTAKE_MISSING_MESSAGE = "Sayım bulunamadı."
LIVE_EXISTS_MESSAGE = (
    "Onaylanmamış bir sayım var. Yeni sayım açmadan önce onu onaylayın ya da iptal edin."
)
UNKNOWN_FIELD_MESSAGE = "Bu alan sayımda değiştirilemez."
COMMITTEE_CHAIR_REQUIRED = (
    "Sayım kurulunun başkanını yazın: harcama yetkilisi ya da görevlendirdiği kişi (TMY 32/2)."
)
COMMITTEE_OFFICER_REQUIRED = (
    "Sayım kurulunda taşınır kayıt yetkilisi de bulunur (TMY 32/2): adını yazın."
)
COMMITTEE_SIZE_MESSAGE = (
    "Sayım kurulu en az üç kişiden oluşur (TMY 32/2): başkan ve taşınır kayıt yetkilisi "
    "dışında en az bir üye yazın."
)
TMY_STOP_REQUEST_REQUIRED = (
    "TMY 32/3 durdurması sayım kurulunun talebiyle olur: talebin tarihini yazın."
)
TMY_STOP_NAME_REQUIRED = "TMY 32/3 durdurmasını harcama yetkilisi yapar: adını yazın."
TMY_STOP_DATE_REQUIRED = "Harcama yetkilisinin durdurma tarihini yazın."
TMY_STOP_DATE_ORDER = "Durdurma tarihi sayım kurulunun talebinden önce olamaz."
FUTURE_DATE_MESSAGE = "Tarih bugünden sonra olamaz."
BASIS_INVALID_MESSAGE = "Bu nüshalar için geçerli bir sayım biçimi seçin."
FISCAL_YEAR_INVALID = "Mali yıl dört haneli bir yıl olmalıdır."
TOO_LONG_MESSAGE = "En çok {sinir} karakter yazılabilir."
APPROVER_REQUIRED = (
    "Kayıttan düşmeyi harcama yetkilisi onaylar (TMY 10/1-e): harcama yetkilisinin adını yazın."
)
APPROVAL_DATE_REQUIRED = "Onay tarihini yazın."
APPROVAL_BEFORE_COMPLETION = (
    "Onay tarihi sayımın tamamlandığı günden önce olamaz: onay, dayanağı olan sayım "
    "tutanağından önceki tarihi taşıyamaz (TMY 10/1-a)."
)
SURPLUS_UNRESOLVED = (
    "{sayi} sayım fazlası kitabın kayda alınacağı eseri seçin ya da gerekçesiyle "
    "“Kayda alınmayacak” diye işaretleyin."
)
SURPLUS_NOT_SURPLUS = "Bu kalem sayım fazlası değil."
SURPLUS_NOTE_REQUIRED = "Sayım fazlası için kitabın adını ya da kısa bir açıklama yazın."
SURPLUS_EXCLUDE_REASON = "Kayda alınmama gerekçesini açıklamaya yazın."
SURPLUS_WORK_AND_EXCLUDE = (
    "Sayım fazlası ya bir esere kayda alınır ya da kayda alınmaz; ikisi birden seçilemez."
)
SURPLUS_WORK_DELETED = "Seçilen eser silinmiş; başka bir eser seçin."
NOT_APPROVED_UNKNOWN = (
    "Onaylanmayan kalem yalnız noksan ya da hasar önerisi listesinden seçilebilir."
)
NOT_APPROVED_REASON = "Onaylanmayan kalemin gerekçesini yazın."
TOO_MANY_SCANS = f"Bir istekte en çok {MAX_SCANS_PER_REQUEST} kod okutulur."
RACE_MESSAGE = "{kitap}: nüshanın durumu bu arada değişti; ekranı yenileyip yeniden onaylayın."
STATE_CHANGED_NOTE = "Onayda durumu: {durum}."
#: Etiketi sayım sırasında Hızlı Kayıt'ta bağlanan fazla (F9 düzeltme turu; kişisiz).
SURPLUS_BOUND_NOTE = (
    "Etiket sayım sırasında {barkod} nüshasına bağlandı; kitap kayıtta, yeniden kayda alınmadı."
)
#: Onayda açılan edinimin notu — sayım ekrandaki adıyla anılır, iç kimlik yazılmaz (sözlük §4.15).
SURPLUS_ACQUISITION_NOTE = "Sayım fazlası — {ad} (TMY 17, 32/7)"


def sayim_adi(stocktake: StockTake) -> str:
    """Sayımın kullanıcıya görünen adı: "Sayım · 2026 · 21.12.2026" (ön yüz `sayimAdi` eşi).

    Mali yıl ve başlangıç (taslakta açılış) tarihi; iç kimlik yazılmaz.
    """
    an = stocktake.started_at or stocktake.created_at
    tarih = f"{timezone.localtime(an):%d.%m.%Y}" if an is not None else ""
    yil = stocktake.fiscal_year or (timezone.localtime(an).year if an is not None else "")
    return f"Sayım · {yil} · {tarih}"


# --- okutma sonuçları (kararlı kodlar — ön yüz iletiyi ve rengi buna göre seçer) ---
OKUTMA_BULUNDU: Final = "bulundu"
OKUTMA_ZATEN: Final = "zaten_okutuldu"
OKUTMA_FAZLA: Final = "fazla"
OKUTMA_FAZLA_TEKRAR: Final = "fazla_tekrar"
OKUTMA_KAPSAM_DISI: Final = "kapsam_disi"
OKUTMA_GECERSIZ: Final = "gecersiz"

SCAN_FOUND = "Bulundu."
SCAN_FOUND_ROUND2 = "Bulundu (ikinci sayım)."
SCAN_FOUND_ON_LOAN = (
    "Bulundu. Kayıtta ödünçte görünüyor; kitap kütüphanedeyse masada iadesini alın."
)
SCAN_FOUND_DELIVERED = (
    "Bulundu. Kayıtta teslimde görünüyor; kitap kütüphanedeyse teslimden geri alın."
)
SCAN_FOUND_LOST = "Bulundu. Kayıtta kayıp görünüyor; sayım onaylanınca kayıp kaydı kapanır."
SCAN_ALREADY = "Bu kitap bu sayımda zaten okutuldu."
SCAN_EXITED = "Bu nüsha sayım sırasında kayıttan çıktı; sayılmaz."
SCAN_OUT_OF_SCOPE = "Bu nüsha sayım başladıktan sonra kayda girdi; bu sayımda sayılmaz."
SCAN_SURPLUS_TERMINAL = (
    "Sayım fazlası: bu etiket kayıttan düşülmüş ya da devredilmiş bir nüshanın. Kitap onayda "
    "yeni numarayla kayda alınabilir."
)
SCAN_SURPLUS_DELETED = (
    "Sayım fazlası: bu etiket silinmiş bir kaydın. Kitap onayda yeni numarayla kayda alınabilir."
)
SCAN_SURPLUS_OUTSIDE = "Sayım fazlası: bu nüsha sayım başladığında sayılacaklar arasında değildi."
SCAN_SURPLUS_RESERVED = (
    "Sayım fazlası: bu etiket hiçbir kitaba bağlanmamış. Kitap onayda bu numarayla kayda "
    "alınabilir."
)
SCAN_SURPLUS_CANCELLED = (
    "Sayım fazlası: bu etiketin numarası iptal edilmiş. Kitap kayda alınırsa yeni numara "
    "verilir; etiketi sökün."
)
SCAN_SURPLUS_NO_RECORD = "Sayım fazlası: bu numarada kayıt yok."
SCAN_SURPLUS_UNKNOWN = (
    "Sayım fazlası: bu kod programın etiket biçiminde değil. Yanlış okutulduysa listeden "
    "çıkarın."
)
SCAN_SURPLUS_AGAIN = "Bu sayım fazlası zaten yazıldı."
#: F9 düzeltme turu: harf içeren kod RAKAMLARINA indirgenip yazılmaz — iki ayrı eski etiket
#: ("KTP-A00123", "KTP-B00123") aynı fazlada birleşirdi. Programın etiketleri yalnız
#: rakamdır; okutulan fazla kod da yalnız rakamdır (bilinçli sınır d).
SCAN_LETTERS = (
    "Bu kod harf içeriyor; programın kütüphane etiketi değil. Kitabın kütüphane etiketini "
    "okutun; etiketi yoksa “Etiketsiz kitap ekle” ile yazın."
)
SCAN_EMPTY = "Okutulan kod boş."
SCAN_TOO_LONG = "Okutulan kod çok uzun; kitabın kütüphane etiketini okutun."
SCAN_MEMBER_CARD = "Bu bir üye kartı. Kitabın kütüphane etiketini okutun."


# ---------------------------------------------------------------------------
# Sonuç nesneleri
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanResult:
    """Bir okutmanın sonucu: kararlı kod, kişisiz ileti, okutulan rakamlar ve kalem."""

    code: str
    message: str
    barcode: str
    item: StockTakeItem | None = None


@dataclass(frozen=True)
class CompleteResult:
    """Tamamla'nın sonucu: ikinci sayıma (32/6) geçildi mi, kaç noksan var."""

    stocktake: StockTake
    second_round: bool
    missing: int


@dataclass(frozen=True)
class ApproveResult:
    """Onayın kişisiz sayıları."""

    stocktake: StockTake
    written_off: int
    damage_written_off: int
    not_approved: int
    state_changed: int
    reconciled: int
    surplus_entered: int
    surplus_excluded: int


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------
def _taze(stocktake: StockTake) -> StockTake:
    guncel: StockTake | None = StockTake.objects.filter(pk=stocktake.pk).first()
    if guncel is None:
        raise ValidationError(STOCKTAKE_MISSING_MESSAGE)
    return guncel


def _durum(stocktake: StockTake, izinli: Iterable[str], anahtar: str) -> None:
    if stocktake.status not in tuple(izinli):
        raise ValidationError({"status": STATE_MESSAGES[anahtar]})


def _metin(deger: object, alan: str, sinir: int) -> str:
    metin = str(deger or "").strip()
    if len(metin) > sinir:
        raise ValidationError({alan: TOO_LONG_MESSAGE.format(sinir=sinir)})
    return metin


def _tarih(deger: object, alan: str) -> date | None:
    if deger in (None, ""):
        return None
    if not isinstance(deger, date):
        raise ValidationError({alan: "Geçerli bir tarih girin."})
    if deger > timezone.localdate():
        raise ValidationError({alan: FUTURE_DATE_MESSAGE})
    return deger


def _kitap(copy: Copy | None) -> str:
    """İletide kitabı gösteren kişisiz etiket: basılı barkod + eser adı."""
    if copy is None:
        return "Sayım fazlası"
    return f"{barcode_module.format_barcode(copy.barcode)} {copy.work.title}"


# ---------------------------------------------------------------------------
# Taslak: aç, düzenle, sil
# ---------------------------------------------------------------------------
#: Taslakta yazılabilen alanlar (servis dışından durum ve zaman alanı yazılmaz).
DRAFT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "fiscal_year",
        "committee_chair",
        "committee_property_officer",
        "committee_members",
        "tmy_stop",
        "tmy_stop_requested_on",
        "tmy_stop_by_name",
        "tmy_stop_on",
        "service_pause",
        "service_pause_decision",
        "loan_basis",
        "section_delivery_basis",
        "teacher_delivery_basis",
        "repair_basis",
        "notes",
    }
)
_BASIS_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "loan_basis": LOAN_BASIS_CHOICES,
    "section_delivery_basis": SECTION_DELIVERY_BASIS_CHOICES,
    "teacher_delivery_basis": TEACHER_DELIVERY_BASIS_CHOICES,
    "repair_basis": REPAIR_BASIS_CHOICES,
}


def _uyelerin_satirlari(metin: object) -> str:
    """Kurul üyeleri: satır başına bir kişi; boş satırlar atılır."""
    satirlar = [s.strip() for s in str(metin or "").splitlines() if s.strip()]
    birlesik = "\n".join(satirlar)
    if len(birlesik) > MEMBERS_MAX:
        raise ValidationError({"committee_members": TOO_LONG_MESSAGE.format(sinir=MEMBERS_MAX)})
    return birlesik


def _uygula(stocktake: StockTake, fields: Mapping[str, Any]) -> None:
    """Taslak alanlarını biçim denetimiyle yazar (tam denetim başlatmadadır)."""
    bilinmeyen = set(fields) - DRAFT_FIELDS
    if bilinmeyen:
        raise ValidationError(dict.fromkeys(sorted(bilinmeyen), UNKNOWN_FIELD_MESSAGE))
    for ad, deger in fields.items():
        if ad == "fiscal_year":
            if deger is not None and not (isinstance(deger, int) and 2000 <= deger <= 2999):
                raise ValidationError({ad: FISCAL_YEAR_INVALID})
            stocktake.fiscal_year = deger
        elif ad in ("committee_chair", "committee_property_officer", "tmy_stop_by_name"):
            setattr(stocktake, ad, _metin(deger, ad, NAME_MAX))
        elif ad == "committee_members":
            stocktake.committee_members = _uyelerin_satirlari(deger)
        elif ad in ("tmy_stop", "service_pause"):
            setattr(stocktake, ad, bool(deger))
        elif ad in ("tmy_stop_requested_on", "tmy_stop_on"):
            setattr(stocktake, ad, _tarih(deger, ad))
        elif ad == "service_pause_decision":
            stocktake.service_pause_decision = _metin(deger, ad, NAME_MAX)
        elif ad in _BASIS_FIELDS:
            if deger not in _BASIS_FIELDS[ad]:
                raise ValidationError({ad: BASIS_INVALID_MESSAGE})
            setattr(stocktake, ad, deger)
        elif ad == "notes":
            stocktake.notes = _metin(deger, ad, NOTES_MAX)
    # Seçilmeyen seçeneğin alanları boşalır (DB kısıtı ve tutanak tutarlılığı).
    if not stocktake.tmy_stop:
        stocktake.tmy_stop_requested_on = None
        stocktake.tmy_stop_by_name = ""
        stocktake.tmy_stop_on = None
    if not stocktake.service_pause:
        stocktake.service_pause_decision = ""


@transaction.atomic
def create_stocktake(**fields: Any) -> StockTake:
    """Taslak sayım açar. Aynı anda tek canlı sayım (taslak dahil)."""
    require_admin_mode()
    app_password.require_password_set()
    if selectors_sayim.live_stocktake() is not None:
        raise ValidationError({"status": LIVE_EXISTS_MESSAGE})
    sayim = StockTake()
    _uygula(sayim, fields)
    try:
        with transaction.atomic():
            sayim.save()
    except IntegrityError as exc:  # yarış: iki taslak aynı anda
        raise ValidationError({"status": LIVE_EXISTS_MESSAGE}) from exc
    logger.info("Sayım taslağı açıldı.")
    return sayim


@transaction.atomic
def update_stocktake(stocktake: StockTake, **fields: Any) -> StockTake:
    """Taslağı günceller — seçenekler, kurul ve kurulun seçimleri YALNIZ taslakta değişir."""
    require_admin_mode()
    app_password.require_password_set()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.DRAFT,), "draft_only")
    _uygula(sayim, fields)
    sayim.save()
    return sayim


@transaction.atomic
def delete_stocktake(stocktake: StockTake) -> None:
    """Taslağı yumuşak siler (anlık görüntüsü yoktur). Başlamış sayım iptal edilir."""
    require_admin_mode()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.DRAFT,), "draft_only")
    sayim.delete()


# ---------------------------------------------------------------------------
# Başlat — kurul ve durdurma denetimi, anlık görüntü
# ---------------------------------------------------------------------------
def committee_names(stocktake: StockTake) -> list[str]:
    """Kurulun adları: başkan, taşınır kayıt yetkilisi, üyeler (boşlar atılır)."""
    uyeler = [s.strip() for s in stocktake.committee_members.splitlines() if s.strip()]
    return [
        ad
        for ad in (
            stocktake.committee_chair.strip(),
            stocktake.committee_property_officer.strip(),
            *uyeler,
        )
        if ad
    ]


def _kurulu_denetle(stocktake: StockTake) -> None:
    """TMY 32/2: başkan + taşınır kayıt yetkilisi + en az üç FARKLI kişi."""
    hatalar: dict[str, str] = {}
    if not stocktake.committee_chair.strip():
        hatalar["committee_chair"] = COMMITTEE_CHAIR_REQUIRED
    if not stocktake.committee_property_officer.strip():
        hatalar["committee_property_officer"] = COMMITTEE_OFFICER_REQUIRED
    farkli = {keys.fold_search(ad) or ad.casefold() for ad in committee_names(stocktake)}
    if len(farkli) < STOCKTAKE_COMMITTEE_MIN_MEMBERS:
        hatalar["committee_members"] = COMMITTEE_SIZE_MESSAGE
    if hatalar:
        raise ValidationError(hatalar)


def _durdurmayi_denetle(stocktake: StockTake) -> None:
    """TMY 32/3: durdurma seçildiyse kurulun talebi + harcama yetkilisinin adı ve tarihi."""
    if not stocktake.tmy_stop:
        return
    hatalar: dict[str, str] = {}
    if stocktake.tmy_stop_requested_on is None:
        hatalar["tmy_stop_requested_on"] = TMY_STOP_REQUEST_REQUIRED
    if not stocktake.tmy_stop_by_name.strip():
        hatalar["tmy_stop_by_name"] = TMY_STOP_NAME_REQUIRED
    if stocktake.tmy_stop_on is None:
        hatalar["tmy_stop_on"] = TMY_STOP_DATE_REQUIRED
    elif (
        stocktake.tmy_stop_requested_on is not None
        and stocktake.tmy_stop_on < stocktake.tmy_stop_requested_on
    ):
        hatalar["tmy_stop_on"] = TMY_STOP_DATE_ORDER
    if hatalar:
        raise ValidationError(hatalar)


def _kalem_bicimi(stocktake: StockTake, durum: str, teslim_turu: str) -> str:
    """Anlık görüntüde nüshanın nasıl sayılacağı (kurulun seçimi — §9-11)."""
    if durum == CopyStatus.ON_LOAN:
        return stocktake.loan_basis
    if durum == CopyStatus.DELIVERED and teslim_turu == DeliveryRecipientKind.SECTION:
        return stocktake.section_delivery_basis
    if durum == CopyStatus.DELIVERED and teslim_turu == DeliveryRecipientKind.TEACHER:
        return stocktake.teacher_delivery_basis
    if durum == CopyStatus.IN_REPAIR:
        # Onarımdaki nüsha onarımcıda olabilir (F7 bilinen sınır c): kurul "Sayımdan önce
        # geri alınır" ya da "Kayda göre alınır — onarımda" der (F9 ekleri K2).
        return stocktake.repair_basis
    # Rafta, kayıpta ya da açık teslimi bulunmayan (tutarsız kayıt) nüsha kütüphanede
    # aranır.
    return CountBasis.LIBRARY


def _anlik_goruntu_al(stocktake: StockTake) -> int:
    """Kayıtlı her nüsha için bir kalem yazar; yazılan kalem sayısını döndürür."""
    teslimler = {
        int(copy_id): (tur, sube)
        for copy_id, tur, sube in Delivery.objects.filter(status=DeliveryStatus.OPEN).values_list(
            "copy_id", "recipient_kind", "section_id"
        )
    }
    nushalar = (
        Copy.objects.filter(work__deleted_at__isnull=True)
        .exclude(status__in=TERMINAL_COPY_STATUSES)
        .values_list("pk", "status", "section_id", "work__section_id")
        .order_by("pk")
    )
    kalemler: list[StockTakeItem] = []
    for pk, durum, bolum, eser_bolumu in nushalar.iterator(chunk_size=2000):
        tur, sube = teslimler.get(int(pk), ("", None))
        teslimde = durum == CopyStatus.DELIVERED
        kalemler.append(
            StockTakeItem(
                stocktake=stocktake,
                copy_id=pk,
                expected_status=durum,
                delivery_kind=tur if teslimde else "",
                basis=_kalem_bicimi(stocktake, durum, tur if teslimde else ""),
                section_id=bolum or eser_bolumu,
                class_section_id=(
                    sube if teslimde and tur == DeliveryRecipientKind.SECTION else None
                ),
            )
        )
    StockTakeItem.objects.bulk_create(kalemler, batch_size=500)
    return len(kalemler)


@transaction.atomic
def start_stocktake(stocktake: StockTake) -> StockTake:
    """Taslak → Sürüyor: kurul ve durdurma denetlenir, anlık görüntü alınır, kilitler başlar."""
    require_admin_mode()
    app_password.require_password_set()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.DRAFT,), "start")
    _kurulu_denetle(sayim)
    _durdurmayi_denetle(sayim)
    sayim.fiscal_year = sayim.fiscal_year or timezone.localdate().year
    sayim.status = StockTakeStatus.IN_PROGRESS
    sayim.started_at = timezone.now()
    sayim.save()
    adet = _anlik_goruntu_al(sayim)
    logger.info("Sayım başladı: anlık görüntüde %d nüsha.", adet)
    return sayim


# ---------------------------------------------------------------------------
# Okutma
# ---------------------------------------------------------------------------
def _acik_odunc_mu(copy_id: int) -> bool:
    return Loan.objects.filter(copy_id=copy_id, status=LoanStatus.OPEN).exists()


def _acik_teslim_mi(copy_id: int) -> bool:
    return Delivery.objects.filter(copy_id=copy_id, status=DeliveryStatus.OPEN).exists()


def _bulundu(stocktake: StockTake, kalem: StockTakeItem, rakamlar: str) -> ScanResult:
    """Anlık görüntüdeki nüsha okutuldu: bulundu (aynı kod ikinci kez zararsızdır).

    İlk turun sonunda "sayım sırasında kütüphaneye döndü" diye bulunmuş kalem
    okutulunca okutulmuş olur (bulunduğu tur korunur).
    """
    if kalem.result == StockTakeResult.FOUND and kalem.found_via == StockTakeFoundVia.SCAN:
        return ScanResult(OKUTMA_ZATEN, SCAN_ALREADY, rakamlar, kalem)
    nusha: Copy = Copy.all_objects.get(pk=kalem.copy_id)
    if nusha.deleted_at is not None or nusha.status in TERMINAL_COPY_STATUSES:
        return ScanResult(OKUTMA_KAPSAM_DISI, SCAN_EXITED, rakamlar, kalem)
    kalem.found_in_round = kalem.found_in_round or stocktake.round
    kalem.result = StockTakeResult.FOUND
    kalem.found_via = StockTakeFoundVia.SCAN
    kalem.scanned_at = timezone.now()
    kalem.basis_fallback = False
    kalem.save(
        update_fields=[
            "result",
            "found_via",
            "found_in_round",
            "scanned_at",
            "basis_fallback",
            "updated_at",
        ]
    )
    if _acik_odunc_mu(nusha.pk):
        ileti = SCAN_FOUND_ON_LOAN
    elif kalem.basis != CountBasis.IN_PLACE and _acik_teslim_mi(nusha.pk):
        ileti = SCAN_FOUND_DELIVERED
    elif nusha.status == CopyStatus.LOST:
        ileti = SCAN_FOUND_LOST
    elif stocktake.round == 2:
        ileti = SCAN_FOUND_ROUND2
    else:
        ileti = SCAN_FOUND
    return ScanResult(OKUTMA_BULUNDU, ileti, rakamlar, kalem)


def _fazla(
    stocktake: StockTake, rakamlar: str, ileti: str, *, eski: Copy | None = None
) -> ScanResult:
    """Sayım fazlası kalemi yazar (D16: kod YALNIZ `surplus_barcode`'a yazılır)."""
    mevcut = StockTakeItem.objects.filter(
        stocktake=stocktake, copy__isnull=True, surplus_barcode=rakamlar
    ).first()
    if mevcut is not None:
        return ScanResult(OKUTMA_FAZLA_TEKRAR, SCAN_SURPLUS_AGAIN, rakamlar, mevcut)
    eser = eski.work if eski is not None and eski.work.deleted_at is None else None
    try:
        with transaction.atomic():
            kalem: StockTakeItem = StockTakeItem.objects.create(
                stocktake=stocktake,
                result=StockTakeResult.SURPLUS,
                surplus_barcode=rakamlar,
                surplus_copy=eski,
                surplus_work=eser,
            )
    except IntegrityError:
        tekrar = StockTakeItem.objects.get(
            stocktake=stocktake, copy__isnull=True, surplus_barcode=rakamlar
        )
        return ScanResult(OKUTMA_FAZLA_TEKRAR, SCAN_SURPLUS_AGAIN, rakamlar, tekrar)
    return ScanResult(OKUTMA_FAZLA, ileti, rakamlar, kalem)


def _okut(stocktake: StockTake, deger: object) -> ScanResult:
    """Tek kodu sayımda okutur (kural 4, 6). Yazma yalnız bulunduda ve fazlada."""
    if any(ch.isalpha() for ch in str(deger or "")):
        # Harfli kod rakamlarına indirgenmez (iki ayrı etiket tek fazlada birleşmesin);
        # yazılmaz. ISBN-10'un "X"i de buraya düşer — o da kütüphane etiketi değildir.
        return ScanResult(OKUTMA_GECERSIZ, SCAN_LETTERS, "")
    info = barcode_reservations.describe_scan(deger)
    rakamlar = info.digits
    if not rakamlar:
        return ScanResult(OKUTMA_GECERSIZ, SCAN_EMPTY, "")
    if info.kind == ScanKind.ISBN:
        return ScanResult(OKUTMA_GECERSIZ, barcode_module.ISBN_SCAN_MESSAGE, rakamlar)
    if info.kind == ScanKind.MEMBER_CARD:
        # Üye kartı numarası sayım kaydına yazılmaz (kişiye bağlanabilir).
        return ScanResult(OKUTMA_GECERSIZ, SCAN_MEMBER_CARD, "")
    if len(rakamlar) > SURPLUS_BARCODE_MAX:
        return ScanResult(OKUTMA_GECERSIZ, SCAN_TOO_LONG, "")
    if info.kind == ScanKind.COPY and info.copy is not None:
        nusha = info.copy
        kalem = StockTakeItem.objects.filter(stocktake=stocktake, copy_id=nusha.pk).first()
        if kalem is not None:
            return _bulundu(stocktake, kalem, rakamlar)
        assert stocktake.started_at is not None
        if nusha.created_at >= stocktake.started_at:
            return ScanResult(OKUTMA_KAPSAM_DISI, SCAN_OUT_OF_SCOPE, rakamlar)
        if nusha.deleted_at is not None:
            ileti = SCAN_SURPLUS_DELETED
        elif nusha.status in TERMINAL_COPY_STATUSES:
            ileti = SCAN_SURPLUS_TERMINAL
        else:  # eseri silinmiş nüsha — anlık görüntüye girmedi
            ileti = SCAN_SURPLUS_OUTSIDE
        return _fazla(stocktake, rakamlar, ileti, eski=nusha)
    iletiler = {
        ScanKind.RESERVED: SCAN_SURPLUS_RESERVED,
        ScanKind.CANCELLED: SCAN_SURPLUS_CANCELLED,
        ScanKind.COPY: SCAN_SURPLUS_NO_RECORD,
    }
    return _fazla(stocktake, rakamlar, iletiler.get(info.kind, SCAN_SURPLUS_UNKNOWN))


@transaction.atomic
def scan(stocktake: StockTake, value: object) -> ScanResult:
    """Tek kod okutur (yalnız süren sayımda)."""
    return scan_many(stocktake, [value])[0]


@transaction.atomic
def scan_many(stocktake: StockTake, values: Sequence[object]) -> list[ScanResult]:
    """Okuyucu kuyruğu: her kod ayrı sonuç döner (kural 6). En çok `MAX_SCANS_PER_REQUEST`.

    GÖREVLİ KİPİNDE DE AÇIKTIR (madde 24, 25.09.2026 kullanıcı kararı; emsal etiket
    doğrulama okutması): `require_admin_mode` yalnız burada sorulmaz. Okutma yalnız
    "bulundu" ve sayım fazlası yazar; kişi verisi yazmaz ve okumaz. Başlatma, tamamlama,
    onay, iptal, kalem listesi ve fazla kararı yönetici kipinde kalır; görevliye giden
    yanıt görünümde daralır (`serializers_sayim.STAFF_SCAN_FIELDS`).
    """
    if len(values) > MAX_SCANS_PER_REQUEST:
        raise ValidationError({"barcodes": TOO_MANY_SCANS})
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.IN_PROGRESS,), "scan")
    return [_okut(sayim, deger) for deger in values]


# ---------------------------------------------------------------------------
# Sayım fazlası — elle ekleme (etiketsiz kitap), düzenleme, çıkarma
# ---------------------------------------------------------------------------
def surplus_copy_fields(work: Work, eski: Copy | None) -> dict[str, Any]:
    """Fazlanın kayda alınacağı nüshanın alanları; kurallar `catalog`'unkilerdir.

    Kayıttan düşülmüş/silinmiş eski kaydın bölümü ve işaretleri taşınır; eski barkod
    ve kayıt no hiçbir alana YAZILMAZ (D16 — numara asla yeniden kullanılmaz). Süreli
    yayın ancak ciltliyse kayda girer (TMY 15/4); kayda alınan fazla süreli yayın bu
    yüzden ciltli sayılır — ciltsiz dergi taşınır değildir, "Kayda alınmayacak" seçilir.
    """
    alanlar: dict[str, Any] = {
        "is_bound_periodical": work.resource_type == ResourceType.PERIODICAL,
    }
    if eski is not None:
        alanlar.update(
            is_reference=eski.is_reference,
            is_out_of_print=eski.is_out_of_print,
            is_rare_or_manuscript=eski.is_rare_or_manuscript,
        )
        bolum = eski.section
        if bolum is not None and bolum.deleted_at is None:
            alanlar["section"] = bolum
    return alanlar


def _fazla_eserini_denetle(work: Work, eski: Copy | None) -> None:
    if work.deleted_at is not None:
        raise ValidationError({"work": SURPLUS_WORK_DELETED})
    catalog.ensure_copy_allowed(
        work, is_bound_periodical=bool(surplus_copy_fields(work, eski)["is_bound_periodical"])
    )


@transaction.atomic
def add_surplus(stocktake: StockTake, *, note: str, work: Work | None = None) -> StockTakeItem:
    """Etiketsiz ya da okutulamayan kitabı sayım fazlası olarak yazar (kodsuz)."""
    require_admin_mode()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.IN_PROGRESS,), "surplus_add")
    aciklama = _metin(note, "note", TEXT_MAX)
    if not aciklama:
        raise ValidationError({"note": SURPLUS_NOTE_REQUIRED})
    if work is not None:
        _fazla_eserini_denetle(work, None)
    kalem: StockTakeItem = StockTakeItem.objects.create(
        stocktake=sayim,
        result=StockTakeResult.SURPLUS,
        surplus_note=aciklama,
        surplus_work=work,
    )
    return kalem


_UNSET: Final = object()


@transaction.atomic
def update_surplus(
    item: StockTakeItem,
    *,
    work: Work | None | object = _UNSET,
    note: str | object = _UNSET,
    excluded: bool | object = _UNSET,
) -> StockTakeItem:
    """Fazlanın eserini, açıklamasını ya da "kayda alınmayacak" işaretini değiştirir.

    Eser seçmek işareti kaldırır; işaret eseri kaldırır ve gerekçe (açıklama) ister.
    """
    require_admin_mode()
    kalem: StockTakeItem = StockTakeItem.objects.select_related("stocktake", "surplus_copy").get(
        pk=item.pk
    )
    _durum(
        kalem.stocktake,
        (StockTakeStatus.IN_PROGRESS, StockTakeStatus.COMPLETED),
        "surplus_edit",
    )
    if not kalem.is_surplus:
        raise ValidationError(SURPLUS_NOT_SURPLUS)
    if work is not _UNSET and work is not None and excluded is True:
        raise ValidationError({"excluded": SURPLUS_WORK_AND_EXCLUDE})
    if note is not _UNSET:
        kalem.surplus_note = _metin(note, "note", TEXT_MAX)
    if work is not _UNSET:
        if work is not None:
            assert isinstance(work, Work)
            _fazla_eserini_denetle(work, kalem.surplus_copy)
            kalem.surplus_excluded = False
        kalem.surplus_work = work if isinstance(work, Work) else None
    if excluded is not _UNSET:
        kalem.surplus_excluded = bool(excluded)
        if kalem.surplus_excluded:
            kalem.surplus_work = None
    if kalem.surplus_excluded and not kalem.surplus_note:
        raise ValidationError({"note": SURPLUS_EXCLUDE_REASON})
    kalem.save(update_fields=["surplus_note", "surplus_work", "surplus_excluded", "updated_at"])
    return kalem


@transaction.atomic
def remove_surplus(item: StockTakeItem) -> None:
    """Yanlış okutulan sayım fazlasını listeden çıkarır (yumuşak silme; yalnız süren sayımda)."""
    require_admin_mode()
    kalem = StockTakeItem.objects.select_related("stocktake").get(pk=item.pk)
    _durum(kalem.stocktake, (StockTakeStatus.IN_PROGRESS,), "surplus_add")
    if not kalem.is_surplus:
        raise ValidationError(SURPLUS_NOT_SURPLUS)
    kalem.delete()


# ---------------------------------------------------------------------------
# Sınıflandırma — tamamlarken ve onayda (D17) aynı kural
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Anlik:
    """Nüshanın şu anki kaydı (kişisiz)."""

    status: str
    gone: bool  # silinmiş ya da kayıttan çıkmış
    open_loan: bool
    open_delivery: bool
    returned: bool  # sayım başladığından beri kütüphaneye döndü


@dataclass(frozen=True)
class _Sinif:
    result: str
    found_via: str = ""
    fallback: bool = False


def _anlik_durumlar(stocktake: StockTake) -> dict[int, _Anlik]:
    """Anlık görüntüdeki nüshaların şu anki kaydı — birkaç toplu sorgu (alt sorguyla)."""
    assert stocktake.started_at is not None
    kalemler = StockTakeItem.objects.filter(stocktake=stocktake, copy__isnull=False)
    kimlikler = kalemler.values("copy_id")
    acik_odunc = set(
        Loan.objects.filter(copy_id__in=kimlikler, status=LoanStatus.OPEN).values_list(
            "copy_id", flat=True
        )
    )
    acik_teslim = set(
        Delivery.objects.filter(copy_id__in=kimlikler, status=DeliveryStatus.OPEN).values_list(
            "copy_id", flat=True
        )
    )
    donenler = set(
        kalemler.filter(selectors_sayim.return_event_q(stocktake.started_at)).values_list(
            "copy_id", flat=True
        )
    )
    sonuc: dict[int, _Anlik] = {}
    for pk, durum, silinme, eser_silinme in Copy.all_objects.filter(pk__in=kimlikler).values_list(
        "pk", "status", "deleted_at", "work__deleted_at"
    ):
        sonuc[int(pk)] = _Anlik(
            status=durum,
            gone=silinme is not None or eser_silinme is not None or durum in TERMINAL_COPY_STATUSES,
            open_loan=pk in acik_odunc,
            open_delivery=pk in acik_teslim,
            returned=pk in donenler,
        )
    return sonuc


def _siniflandir(kalem: StockTakeItem, anlik: _Anlik) -> _Sinif:
    """Okutulmamış kalemin sonucu (kural 2, 5). Okutulan kalem bulunmuştur."""
    if kalem.result == StockTakeResult.FOUND and kalem.found_via == StockTakeFoundVia.SCAN:
        return _Sinif(StockTakeResult.FOUND, StockTakeFoundVia.SCAN)
    if anlik.gone:
        return _Sinif(StockTakeResult.EXITED)
    if anlik.returned:
        return _Sinif(StockTakeResult.FOUND, StockTakeFoundVia.RETURN)
    if anlik.open_loan:
        return _Sinif(StockTakeResult.BY_RECORD, fallback=kalem.basis != CountBasis.BY_RECORD)
    if anlik.open_delivery:
        if (
            kalem.basis == CountBasis.IN_PLACE
            or kalem.delivery_kind == DeliveryRecipientKind.SECTION
        ):
            # Sınıf kitaplığı kayda göre alınmaz (K3): yerinde sayılıp ya da toplanamayıp
            # yerinde de aranıp bulunmadı — noksan (32/5 birinci cümle).
            return _Sinif(StockTakeResult.MISSING)
        return _Sinif(StockTakeResult.BY_RECORD, fallback=kalem.basis != CountBasis.BY_RECORD)
    if kalem.expected_status == CopyStatus.IN_REPAIR and anlik.status == CopyStatus.IN_REPAIR:
        # Onarımdaki nüsha (K2): kayda göre alınır — "Sayımdan önce geri alınır" seçildiyse
        # geri alınamadığı işaretlenir (onarım kaydı hâlâ açık).
        return _Sinif(StockTakeResult.BY_RECORD, fallback=kalem.basis != CountBasis.BY_RECORD)
    return _Sinif(StockTakeResult.MISSING)


def _sinifi_yaz(kalem: StockTakeItem, sinif: _Sinif, tur: int) -> bool:
    """Sınıfı kaleme yazar; değişiklik olduysa True."""
    bulundu = sinif.result == StockTakeResult.FOUND
    yeni = (
        sinif.result,
        sinif.found_via if bulundu else "",
        (kalem.found_in_round or tur) if bulundu else None,
        sinif.fallback,
    )
    eski = (kalem.result, kalem.found_via, kalem.found_in_round, kalem.basis_fallback)
    if yeni == eski:
        return False
    kalem.result, kalem.found_via, kalem.found_in_round, kalem.basis_fallback = yeni
    return True


def _toplu_yaz(kalemler: Sequence[StockTakeItem], alanlar: Sequence[str]) -> None:
    simdi = timezone.now()
    for kalem in kalemler:
        kalem.updated_at = simdi
    StockTakeItem.objects.bulk_update(kalemler, [*alanlar, "updated_at"], batch_size=500)


_SONUC_ALANLARI: Final = ("result", "found_via", "found_in_round", "basis_fallback")


def _dosyalar(stocktake: StockTake) -> dict[int, LossDamageCase]:
    """Nüshanın sayımı ilgilendiren kayıp/hasar dosyası: açık dosya, yoksa kayıttan düşme
    önerisi taşıyan en son kapanmış dosya."""
    kimlikler = StockTakeItem.objects.filter(stocktake=stocktake, copy__isnull=False).values(
        "copy_id"
    )
    dosyalar: dict[int, LossDamageCase] = {}
    for dosya in LossDamageCase.objects.filter(
        copy_id__in=kimlikler, write_off_proposed_at__isnull=False
    ).order_by("write_off_proposed_at", "pk"):
        dosyalar[int(dosya.copy_id)] = dosya  # en son öneri kalır
    for dosya in LossDamageCase.objects.filter(
        copy_id__in=kimlikler, resolution__in=OPEN_CASE_RESOLUTIONS
    ):
        dosyalar[int(dosya.copy_id)] = dosya  # açık dosya öneriden önce gelir
    return dosyalar


def _hasar_onerisi_mi(dosya: LossDamageCase | None) -> bool:
    return (
        dosya is not None
        and dosya.case_type == CaseType.DAMAGED
        and dosya.write_off_proposed_at is not None
        and not dosya.is_open
    )


def _sonuclari_yaz(stocktake: StockTake, anliklar: Mapping[int, _Anlik]) -> None:
    """Tamamlanırken: durum, dosya bağı ve hasar önerisi (kural 8 hazırlığı)."""
    dosyalar = _dosyalar(stocktake)
    kalemler = list(StockTakeItem.objects.filter(stocktake=stocktake, copy__isnull=False))
    for kalem in kalemler:
        assert kalem.copy_id is not None
        anlik = anliklar[kalem.copy_id]
        dosya = dosyalar.get(kalem.copy_id)
        kalem.status_at_completion = anlik.status
        kalem.case = dosya
        kalem.damage_write_off = (
            kalem.result == StockTakeResult.FOUND
            and anlik.status in (CopyStatus.AVAILABLE, CopyStatus.IN_REPAIR)
            and not anlik.open_loan
            and not anlik.open_delivery
            and _hasar_onerisi_mi(dosya)
        )
    _toplu_yaz(kalemler, ("status_at_completion", "case", "damage_write_off"))


@transaction.atomic
def complete_stocktake(stocktake: StockTake) -> CompleteResult:
    """Sürüyor → (ikinci sayım) → Tamamlandı (kural 7; TMY 32/6).

    İlk turda noksan varsa sayım "Sürüyor"da kalır ve ikinci tura geçer: noksanlar
    bir kez daha aranır (okutulan bulunur). İkinci turda ya da ilk turda noksan yoksa
    sonuçlar kesinleşir ve durum "Tamamlandı" olur; kilitler onaya dek sürer (D17).
    """
    require_admin_mode()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.IN_PROGRESS,), "complete")
    anliklar = _anlik_durumlar(sayim)
    kalemler = list(
        StockTakeItem.objects.filter(stocktake=sayim, copy__isnull=False).exclude(
            result=StockTakeResult.FOUND, found_via=StockTakeFoundVia.SCAN
        )
    )
    degisen = []
    noksan = 0
    for kalem in kalemler:
        assert kalem.copy_id is not None
        sinif = _siniflandir(kalem, anliklar[kalem.copy_id])
        if sinif.result == StockTakeResult.MISSING:
            noksan += 1
        if _sinifi_yaz(kalem, sinif, sayim.round):
            degisen.append(kalem)
    _toplu_yaz(degisen, _SONUC_ALANLARI)
    simdi = timezone.now()
    if sayim.round == 1 and noksan:
        sayim.round = 2
        sayim.round2_started_at = simdi
        sayim.save(update_fields=["round", "round2_started_at", "updated_at"])
        logger.info("Sayımda %d nüsha bulunamadı; ikinci sayıma geçildi (TMY 32/6).", noksan)
        return CompleteResult(stocktake=sayim, second_round=True, missing=noksan)
    _sonuclari_yaz(sayim, anliklar)
    sayim.status = StockTakeStatus.COMPLETED
    sayim.completed_at = simdi
    sayim.save(update_fields=["status", "completed_at", "updated_at"])
    logger.info("Sayım tamamlandı: %d noksan.", noksan)
    return CompleteResult(stocktake=sayim, second_round=False, missing=noksan)


# ---------------------------------------------------------------------------
# Onay (D17) — noksan (32/7), hasar (27/1 + 10/1-e), kayıp uzlaştırma, fazla (TMY 17)
# ---------------------------------------------------------------------------
def _onay_tarihi(approved_on: object, sayim: StockTake) -> date:
    if approved_on in (None, ""):
        raise ValidationError({"approved_on": APPROVAL_DATE_REQUIRED})
    tarih = _tarih(approved_on, "approved_on")
    assert tarih is not None and sayim.completed_at is not None
    if tarih < timezone.localdate(sayim.completed_at):
        raise ValidationError({"approved_on": APPROVAL_BEFORE_COMPLETION})
    return tarih


def _onaylanmayanlar(not_approved: Mapping[Any, Any] | None, gecerli: set[int]) -> dict[int, str]:
    sonuc: dict[int, str] = {}
    for anahtar, gerekce in (not_approved or {}).items():
        try:
            kimlik = int(anahtar)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"not_approved": NOT_APPROVED_UNKNOWN}) from exc
        if kimlik not in gecerli:
            raise ValidationError({"not_approved": NOT_APPROVED_UNKNOWN})
        metin = _metin(gerekce, "not_approved", TEXT_MAX)
        if not metin:
            raise ValidationError({"not_approved": NOT_APPROVED_REASON})
        sonuc[kimlik] = metin
    return sonuc


def _onarimi_kapat(copy_id: int) -> None:
    """Kayıttan düşülen nüshanın açık onarım kaydı kapanır ("Onarımda" ⇔ açık kayıt)."""
    acik: CopyRepair | None = CopyRepair.objects.filter(
        copy_id=copy_id, returned_on__isnull=True
    ).first()
    if acik is not None:
        acik.returned_on = max(timezone.localdate(), acik.sent_on)
        acik.save(update_fields=["returned_on", "updated_at"])


def _teslimi_kayba_donustur(copy_id: int, simdi: datetime) -> None:
    """Yerinde sayılıp bulunmayan sınıf kitaplığı nüshasının açık teslimi kapanır."""
    Delivery.objects.filter(copy_id=copy_id, status=DeliveryStatus.OPEN).update(
        status=DeliveryStatus.LOST_CONVERTED, lost_at=simdi, updated_at=simdi
    )


def _dus(kalem: StockTakeItem, anlik: _Anlik, hedef: str, simdi: datetime) -> None:
    """Nüshayı koşullu olarak kayıttan düşer; durum arada değiştiyse bütün onay geri sarılır."""
    assert kalem.copy_id is not None
    if anlik.status == CopyStatus.IN_REPAIR:
        _onarimi_kapat(kalem.copy_id)
    if anlik.open_delivery:
        _teslimi_kayba_donustur(kalem.copy_id, simdi)
    if not nusha_durumu.gecir(kalem.copy_id, eski=anlik.status, yeni=hedef):
        raise ValidationError({"items": [RACE_MESSAGE.format(kitap=_kitap(kalem.copy))]})


def _durum_degisti(kalem: StockTakeItem, anlik: _Anlik) -> str:
    """Onay notu: nüshanın onaydaki durumu (kişisiz)."""
    etiket = CopyStatus(anlik.status).label if anlik.status in CopyStatus.values else ""
    return STATE_CHANGED_NOTE.format(durum=etiket or "kayıttan çıktı")


def _kayip_dosyasi(kalem: StockTakeItem) -> LossDamageCase | None:
    """Bulunan kayıp nüshanın dosyası: açık kayıp dosyası, yoksa öneriyle kapanmış olanı."""
    assert kalem.copy_id is not None
    acik: LossDamageCase | None = LossDamageCase.objects.filter(
        copy_id=kalem.copy_id, resolution__in=OPEN_CASE_RESOLUTIONS, case_type=CaseType.LOST
    ).first()
    if acik is not None:
        return acik
    dosya: LossDamageCase | None = (
        LossDamageCase.objects.filter(
            copy_id=kalem.copy_id,
            case_type=CaseType.LOST,
            resolution__in=tuple(loss_damage.ONERIDEN_BULUNMA),
        )
        .order_by("-resolved_at", "-pk")
        .first()
    )
    return dosya


def _kaybi_uzlastir(kalem: StockTakeItem) -> bool:
    """Kayıpta görünüp sayımda okutulan nüsha: kayıp dosyası "Bulundu" ile kapanır (uzlaştırma).

    Dosya yoksa (eski veri) nüsha doğrudan rafa döner. Kayıp bildirimi okutmadan SONRA
    yapılmışsa (kitap okutulduktan sonra kaybolmuş) uzlaştırma yapılmaz.
    """
    assert kalem.copy_id is not None
    dosya = _kayip_dosyasi(kalem)
    if dosya is None:
        return nusha_durumu.gecir(kalem.copy_id, eski=CopyStatus.LOST, yeni=CopyStatus.AVAILABLE)
    if kalem.scanned_at is not None and dosya.created_at > kalem.scanned_at:
        return False
    secenekler = [
        cozum
        for cozum in loss_damage.allowed_resolutions(dosya, price_options=False)
        if cozum in FOUND_RESOLUTIONS
    ]
    if not secenekler:
        return False
    loss_damage.resolve_case(dosya, resolution=secenekler[0])
    kalem.case = dosya
    return True


def _fazlayi_al(kalem: StockTakeItem, edinim: Any) -> Copy:
    """Sayım fazlasını kayda alır (TMY 17): boş etiketse o numarayla, değilse yeni numarayla."""
    assert kalem.surplus_work is not None
    alanlar = surplus_copy_fields(kalem.surplus_work, kalem.surplus_copy)
    if kalem.surplus_barcode:
        info = barcode_reservations.describe_scan(kalem.surplus_barcode)
        if info.kind == ScanKind.RESERVED and not barcode_reservations.bind_rejection(info):
            return barcode_reservations.bind_label(
                label=kalem.surplus_barcode,
                work=kalem.surplus_work,
                acquisition=edinim,
                **alanlar,
            )
    return catalog.create_copy(work=kalem.surplus_work, acquisition=edinim, **alanlar)


@transaction.atomic
def approve_stocktake(
    stocktake: StockTake,
    *,
    approved_by_name: str,
    approved_on: date | None,
    not_approved: Mapping[Any, Any] | None = None,
) -> ApproveResult:
    """Tamamlandı → Onaylandı — TEK işlem (kural 8; D17).

    `not_approved`: harcama yetkilisinin onaylamadığı noksan ya da hasar önerisi
    kalemleri → gerekçe. Bu kalemler kayıtta kalır ve tutanakta gerekçesiyle görünür.
    """
    require_admin_mode()
    app_password.require_password_set()
    sayim = _taze(stocktake)
    _durum(sayim, (StockTakeStatus.COMPLETED,), "approve")
    ad = _metin(approved_by_name, "approved_by_name", NAME_MAX)
    if not ad:
        raise ValidationError({"approved_by_name": APPROVER_REQUIRED})
    tarih = _onay_tarihi(approved_on, sayim)
    kalemler = list(
        StockTakeItem.objects.filter(stocktake=sayim).select_related(
            "copy", "copy__work", "case", "surplus_copy", "surplus_copy__section", "surplus_work"
        )
    )
    noksanlar = [k for k in kalemler if k.result == StockTakeResult.MISSING]
    hasarlar = [k for k in kalemler if k.damage_write_off]
    # D17 fazlaya da uygulanır (F9 düzeltme turu): etiketi sayım SIRASINDA bir nüshaya
    # bağlanmış fazla kayda girmiştir; onay onu ikinci kez kayda almaz.
    bagli_kimlikler = set(
        StockTakeItem.objects.filter(stocktake=sayim)
        .filter(selectors_sayim.surplus_bound_q(sayim))
        .values_list("pk", flat=True)
    )
    bagli = [k for k in kalemler if k.pk in bagli_kimlikler]
    fazlalar = [k for k in kalemler if k.is_surplus and k.pk not in bagli_kimlikler]
    reddedilen = _onaylanmayanlar(not_approved, {k.pk for k in (*noksanlar, *hasarlar)})
    cozulmemis = [k for k in fazlalar if k.surplus_work is None and not k.surplus_excluded]
    if cozulmemis:
        raise ValidationError({"surplus": SURPLUS_UNRESOLVED.format(sayi=len(cozulmemis))})
    for kalem in fazlalar:
        if kalem.surplus_work is not None:
            _fazla_eserini_denetle(kalem.surplus_work, kalem.surplus_copy)

    simdi = timezone.now()
    # 1) Kilitler onayla kalkar (D17): sayımın kendi girişi ve çıkışı kapıdan geçebilsin.
    sayim.status = StockTakeStatus.APPROVED
    sayim.open_slot = None
    sayim.approved_by_name = ad
    sayim.approved_on = tarih
    sayim.approved_at = simdi
    sayim.save(
        update_fields=[
            "status",
            "open_slot",
            "approved_by_name",
            "approved_on",
            "approved_at",
            "updated_at",
        ]
    )
    anliklar = _anlik_durumlar(sayim)
    sayac: Counter[str] = Counter()
    yazilacak: list[StockTakeItem] = []

    # 2) Noksan: her kalem yeniden doğrulanır; durumu değişen düşülmez (D17).
    for kalem in noksanlar:
        assert kalem.copy_id is not None
        anlik = anliklar[kalem.copy_id]
        sinif = _siniflandir(kalem, anlik)
        if sinif.result != StockTakeResult.MISSING or anlik.status != kalem.status_at_completion:
            _sinifi_yaz(kalem, sinif, sayim.round)
            kalem.outcome = StockTakeOutcome.STATE_CHANGED
            kalem.outcome_note = _durum_degisti(kalem, anlik)
            sayac["state_changed"] += 1
        elif kalem.pk in reddedilen:
            kalem.outcome = StockTakeOutcome.NOT_APPROVED
            kalem.outcome_note = reddedilen[kalem.pk]
            sayac["not_approved"] += 1
        else:
            hedef = (
                CopyStatus.WITHDRAWN_LOST
                if anlik.status == CopyStatus.LOST
                else CopyStatus.WITHDRAWN_MISSING
            )
            _dus(kalem, anlik, hedef, simdi)
            kalem.outcome = StockTakeOutcome.WRITTEN_OFF
            kalem.write_off_path = StockTakeWriteOffPath.MISSING_32_7
            sayac["written_off"] += 1
        yazilacak.append(kalem)

    # 3) Hasar önerisi: TMY 27/1 + 10/1-e — kayıp/hasar tutanağıyla komisyonsuz (F8 ekleri 34).
    for kalem in hasarlar:
        assert kalem.copy_id is not None
        anlik = anliklar[kalem.copy_id]
        dosya = LossDamageCase.objects.filter(pk=kalem.case_id).first() if kalem.case_id else None
        yerinde = (
            anlik.status in (CopyStatus.AVAILABLE, CopyStatus.IN_REPAIR)
            and anlik.status == kalem.status_at_completion
            and not anlik.open_loan
            and not anlik.open_delivery
        )
        if not (yerinde and _hasar_onerisi_mi(dosya)):
            kalem.outcome = StockTakeOutcome.STATE_CHANGED
            kalem.outcome_note = _durum_degisti(kalem, anlik)
            sayac["state_changed"] += 1
        elif kalem.pk in reddedilen:
            kalem.outcome = StockTakeOutcome.NOT_APPROVED
            kalem.outcome_note = reddedilen[kalem.pk]
            sayac["not_approved"] += 1
        else:
            _dus(kalem, anlik, CopyStatus.WITHDRAWN_DAMAGED, simdi)
            kalem.outcome = StockTakeOutcome.WRITTEN_OFF
            kalem.write_off_path = StockTakeWriteOffPath.DAMAGE_27_1
            sayac["damage_written_off"] += 1
        yazilacak.append(kalem)

    # 4) Kayıp uzlaştırma: kayıpta görünüp okutulan nüsha rafa döner, dosyası kapanır.
    for kalem in kalemler:
        if (
            kalem.result == StockTakeResult.FOUND
            and kalem.found_via == StockTakeFoundVia.SCAN
            and kalem.status_at_completion == CopyStatus.LOST
            and kalem.copy_id is not None
            and anliklar[kalem.copy_id].status == CopyStatus.LOST
            and _kaybi_uzlastir(kalem)
        ):
            kalem.outcome = StockTakeOutcome.RECONCILED
            sayac["reconciled"] += 1
            yazilacak.append(kalem)

    # 5) Sayım fazlası: tek "Sayım fazlası (kayda giriş)" edinimiyle kayda (TMY 17, 32/7).
    # Etiketi sayım sırasında bağlanan fazla kayda girmiştir: ikinci nüsha açılmaz.
    for kalem in bagli:
        nusha = selectors_sayim.bound_surplus_copy(kalem)
        kalem.outcome = StockTakeOutcome.NOT_ENTERED
        kalem.outcome_note = SURPLUS_BOUND_NOTE.format(
            barkod=barcode_module.format_barcode(nusha.barcode if nusha else kalem.surplus_barcode)
        )
        yazilacak.append(kalem)
    alinacaklar = [k for k in fazlalar if k.surplus_work is not None]
    if alinacaklar:
        edinim = catalog.create_acquisition(
            method=AcquisitionMethod.INVENTORY_FOUND,
            date=tarih,
            notes=SURPLUS_ACQUISITION_NOTE.format(ad=sayim_adi(sayim)),
        )
        sayim.surplus_acquisition = edinim
        sayim.save(update_fields=["surplus_acquisition", "updated_at"])
        for kalem in alinacaklar:
            kalem.created_copy = _fazlayi_al(kalem, edinim)
            kalem.outcome = StockTakeOutcome.ENTERED
            sayac["surplus_entered"] += 1
            yazilacak.append(kalem)
    for kalem in fazlalar:
        if kalem.surplus_excluded:
            kalem.outcome = StockTakeOutcome.NOT_ENTERED
            sayac["surplus_excluded"] += 1
            yazilacak.append(kalem)

    _toplu_yaz(
        yazilacak,
        (*_SONUC_ALANLARI, "outcome", "outcome_note", "write_off_path", "case", "created_copy"),
    )
    logger.info(
        "Sayım onaylandı: %d noksan ve %d hasar önerisi kayıttan düşüldü, %d fazla kayda alındı.",
        sayac["written_off"],
        sayac["damage_written_off"],
        sayac["surplus_entered"],
    )
    return ApproveResult(
        stocktake=sayim,
        written_off=sayac["written_off"],
        damage_written_off=sayac["damage_written_off"],
        not_approved=sayac["not_approved"],
        state_changed=sayac["state_changed"],
        reconciled=sayac["reconciled"],
        surplus_entered=sayac["surplus_entered"],
        surplus_excluded=sayac["surplus_excluded"],
    )


# ---------------------------------------------------------------------------
# İptal
# ---------------------------------------------------------------------------
@transaction.atomic
def cancel_stocktake(stocktake: StockTake, *, reason: str = "") -> StockTake:
    """Onaylanmamış sayımı iptal eder: kilitler kalkar, anlık görüntü iz olarak kalır."""
    require_admin_mode()
    sayim = _taze(stocktake)
    if sayim.status not in OPEN_STOCKTAKE_STATUSES:
        raise ValidationError({"status": STATE_MESSAGES["cancel"]})
    sayim.status = StockTakeStatus.CANCELLED
    sayim.open_slot = None
    sayim.cancelled_at = timezone.now()
    sayim.cancel_reason = _metin(reason, "reason", TEXT_MAX)
    sayim.save(update_fields=["status", "open_slot", "cancelled_at", "cancel_reason", "updated_at"])
    logger.info("Sayım iptal edildi.")
    return sayim
