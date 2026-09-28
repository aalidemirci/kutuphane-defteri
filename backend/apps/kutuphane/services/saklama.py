"""Saklama taraması ve onaylı anonimleştirme tetiği (tasarım §6.4 — BAĞLAYICI; D13, TB16; F11).

KVKK md. 4/2-d kişisel verinin "İlgili mevzuatta öngörülen veya işlendikleri amaç
için gerekli olan süre kadar muhafaza edilme"sini, md. 7/1 işlenmesini gerektiren
sebepler ortadan kalkınca "silinir, yok edilir veya anonim hâle getirilir"
olmasını ister (docs/mevzuat/6698-kvkk.md). Silme, Yok Etme veya Anonim Hâle
Getirme Yönetmeliği depoda YOKTUR; ona atıf yapılmaz (TB9, §6.4-4).

§6.4 TABLOSU — HER SATIR BİR KURAL (süreler `LibraryPolicy`'dedir, 1-10 yıl):

| Kural | Ne olur | Süre (varsayılan) |
|---|---|---|
| Ayrılmış kişi (üye olmuş ya da olmamış) | Kişi kaydı KATI silinir | ayrılış + 2 yıl (`retention_years_left_person`, kullanıcı kararı 27.09.2026) |
| Sonlanmış üyeliğin ödünç ve dosya bağları | `membership=NULL` + `anonymized_at`; gerekçe ve not metinleri temizlenir | sonlanma + 2 yıl (`retention_years_after_termination`) |
| Sonlanmış üyelik satırı | Açık yükümlülük yoksa KATI silinir (kartı "iptal edilmiş kart" olur) | sonlanma + 2 yıl (aynı süre) |
| Aktif üyenin iade edilmiş ödünçleri (A3) | Kişi bağı koparılır, gerekçeler temizlenir | ders yılı sonu + 1 yıl (`retention_years_returned_loans`) |
| Kapanmış kayıp/hasar dosyası | Kişi bağı ve `responsible_note` temizlenir | kapanış + 2 yıl (`retention_years_closed_cases`) |
| "Bedel belirlendi" / "Bedel teslim alındı"da bekleyen dosya | Sessizce silinmez: bir yılı geçen dosya yıllık hatırlatma listesine düşer | — |
| Kapanmış öğretmen teslimi | Alan bağı AÇIK GÜNCELLEMEYLE koparılır (`on_delete`'e güvenilmez — CLAUDE.md §3) | geri alma + 2 yıl (`retention_years_closed_deliveries`) |

AYRINTILI KURALLAR (kod kapısı ve testler — `tests/test_saklama.py`):

- **Açık yükümlülük varken kişi silinmez.** Açık ödünç, açık teslim (PROTECT),
  açık kayıp/hasar dosyası — bedel adımında bekleyen dahil (okulun açık işi) — olan
  kişi aday OLMAZ; tetik her kişi için `persons.open_obligations` ve
  `persons.deletion_blocks`'u yeniden sorar, biri doluysa BÜTÜN tetik geri sarılır.
  Kişinin bütün üyelikleri silinebilir (süresi dolmuş, açık işi yok) ve bütün
  öğretmen teslimlerinin bağı bu tetikte koparılabilir olmalıdır; değilse kişi
  bekler (PROTECT bağı).
- **"Ders yılı sonu"**: iade gününü kapsayan ders yılının bitişi; iki ders yılı
  arasındaki (yaz) iade bir sonraki ders yılının bitişine sayılır; ders yılı
  tanımlanmamışsa izleyen 30 Haziran. İade edilmiş ödünç = "İade edildi" ya da
  "Kayba dönüştü" (kapanış anı iade ya da kayba dönüşme zamanı).
- **Kişi bağı F7'nin tek kuralıyla tutarlıdır** (`selectors_teslim.person_case_q`):
  anonimleştirilmiş dosya hiçbir kişiye yazılmaz. Dosyanın ödünç ve teslim bağı
  KALIR (o satırların kişi bağı kendi süreleriyle koparılır); öğretmen tesliminin
  bağı, kişiyi o teslimden bulan (üyeliksiz) ve henüz anonimleştirilmemiş bir
  dosya varken koparılmaz — dosya kendi süresinden önce kişisini yitirmesin.
- **Yeniden eşleşmeye karşı bekletme** (F11 düzeltme turu): (a) öğretmen tesliminin
  bağı BELGE NO düzeyinde koparılır — aynı belge no'nun bağı koparılmamış bütün
  satırları bu tetikte koparılabiliyorsa hepsi, değilse hiçbiri; (b) kişisini
  teslimden bulan dosya, o teslimin bağı bu tetikte koparılmıyorsa bekler; (c) kişi
  bağı koparılmamış (açık ya da süresi dolmamış) dosyaya bağlı ödünç bekler, dosyayla
  birlikte koparılır. Aksi hâlde "anonimleştirilmiş" satır belge no ya da dosya
  üzerinden kişiye yeniden bağlanırdı (KVKK 3/1-b).
- **Şube (sınıf kitaplığı) teslimi kişiye bağlı değildir** (§6.3: şube açık
  kalanlardandır); bağı koparılmaz.
- **Kişisiz kalanlar**: ödünç satırı (istatistik), dosya satırı (E9), teslim satırı
  ve türü, verilmiş kart numarası (`IssuedCard`), iptal edilmiş kart, belge izi
  (`BelgeIzi`). Çok okunanların kapanmış pencereleri ve sonlandırılmış yıl sonu
  raporu (E9) DONDURULMUŞTUR; anonimleştirme onları değiştirmez.

ÇALIŞMA BİÇİMİ (§6.4):

1. Gün değişimi kapısında aday tespiti (`gunluk_tarama`, kayıt adı
   `saklama-taramasi`): kişisiz özet `RetentionState`'e yazılır; aday varken onay
   beklemenin başladığı gün (`pending_since`) tutulur.
2. Genel Bakış kartı ve Ayarlar → Saklama ekranı (kişisiz sayılar; silinecek
   kişilerin adları yalnız yönetici kipinde, ayrı uçtan).
3. Yönetici parolasıyla GERİ DÖNÜŞSÜZ tetik (`tetikle`): önce
   `pre-anonim-<tarih>-<saat>.kdbak` (alınamazsa tetik ÇALIŞMAZ); sonra TEK işlemde
   bütün kurallar (hepsi ya da hiçbiri; önizlemedeki liste değiştiyse ret); işlem
   bittikten sonra tetik anından eski `pre-migrate` yedekleri ve geri yüklemenin
   kenara aldığı `db-onceki-*` dosyalarından tetik anından 14 günden eski olanlar
   (27.09.2026 kullanıcı kararı) silinir ve WAL `checkpoint(TRUNCATE)` ile boşaltılır
   (`secure_delete` açıktır — TB24). Silinecek dosyalar YALNIZ tetik anında belirlenir;
   silinemeyenleri gün değişimi kapısı ADIYLA yeniden dener (saat kayması — D-7).
4. Onay beklemenin azami süresi **6 ay**dır; dolunca Genel Bakış'ta kapatılamayan
   uyarı çıkar.

Günlüğe ve hata iletilerine KİŞİ BİLGİSİ yazılmaz; yalnız sayılar.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Final, cast

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    CardRevocation,
    CardRevocationReason,
    CaseResolution,
    Delivery,
    DeliveryRecipientKind,
    DeliveryStatus,
    LibraryPolicy,
    Loan,
    LoanStatus,
    LossDamageCase,
    Membership,
    MembershipStatus,
    RetentionRun,
    RetentionState,
)
from apps.kutuphane.selectors_ilisik import member_kind_text
from apps.kutuphane.services.yonetici_kipi import require_admin_mode
from apps.okul import normalize
from apps.okul.models import Personnel, SchoolYear, Student, StudentStatus
from apps.okul.services import app_password, backup_restore, persons
from katalog.bakim import KAPI, BakimKapisi
from shared.models import SoftDeleteQuerySet

logger = logging.getLogger("kutuphane_defteri.kutuphane")

#: Gün değişimi kapısındaki kayıt adı (`masaustu_kanca.gunluk_is_kaydet`; ASCII).
GUNLUK_IS_ADI: Final = "saklama-taramasi"
#: Onay beklemenin azami süresi (ay) — §6.4-4. Silme Yönetmeliği depoya alınınca
#: onun periyodik imha hükmüne göre ayarlanır (TB9).
AZAMI_BEKLEME_AY: Final = 6
#: Bedel adımında bekleyen dosyanın yıllık hatırlatma listesine düşme süresi (yıl).
BEDEL_HATIRLATMA_YIL: Final = 1
#: Kapanmış ödünçler (iade edildi ya da kayba dönüştü).
KAPALI_ODUNC: Final = (LoanStatus.RETURNED, LoanStatus.LOST_CONVERTED)
#: Bedel adımında bekleyen dosya durumları (§6.4; F7 ekleri 26).
BEDEL_BEKLEYEN: Final = (CaseResolution.PRICE_DETERMINED, CaseResolution.PRICE_RECEIVED)
#: Tek sorguda en çok kimlik (SQLite değişken sınırının çok altında).
_PARCA: Final = 500

BOS_MESAJI: Final = "Süresi dolmuş kayıt yok; saklama işlemi uygulanmadı."
YEDEK_ALINAMADI_MESAJI: Final = (
    "Saklama işleminden önceki yedek alınamadı; hiçbir kayıt değişmedi. Yönetici parolası "
    "kurulu ve güvenlik dosyası yerindeyse işlemi yeniden deneyin."
)
BAKIM_MESAJI: Final = "Geri yükleme sürüyor; saklama işlemi şimdi uygulanamaz."
ACIK_YUKUMLULUK_MESAJI: Final = (
    "Silinecek kişilerden birinin kütüphaneyle açık işi var; saklama işlemi uygulanmadı. "
    "Listeyi yenileyin."
)
LISTE_DEGISTI_MESAJI: Final = (
    "Saklama listesi siz onaylarken değişti; hiçbir kayıt değişmedi. Önizlemeyi yenileyip "
    "yeniden onaylayın."
)


class SaklamaListesiDegisti(APIException):
    """Onaylanan önizleme ile tetik anındaki liste aynı değil — 409 (hiçbir şey yazılmaz)."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "saklama_listesi_degisti"
    default_detail = LISTE_DEGISTI_MESAJI


# ---------------------------------------------------------------------------
# Tarih yardımcıları
# ---------------------------------------------------------------------------
def yil_ekle(gun: date, yil: int) -> date:
    """`gun`e yıl ekler (eksi olabilir); 29 Şubat karşılığı olmayan yılda 28 Şubat olur."""
    try:
        return gun.replace(year=gun.year + yil)
    except ValueError:
        return gun.replace(year=gun.year + yil, day=28)


def ay_ekle(gun: date, ay: int) -> date:
    """`gun`e ay ekler; ayın günü hedef ayda yoksa ayın son günü olur."""
    toplam = gun.month - 1 + ay
    yil, ay0 = gun.year + toplam // 12, toplam % 12 + 1
    sonraki = date(yil + (ay0 // 12), ay0 % 12 + 1, 1)
    return date(yil, ay0, min(gun.day, (sonraki - timedelta(days=1)).day))


def _gun_bitti(gun: date) -> datetime:
    """`gun`ün bittiği an (ertesi günün yerel 00:00'ı) — `__lt` ile "o gün ya da önce"."""
    return timezone.make_aware(datetime.combine(gun + timedelta(days=1), time.min))


def _ders_yillari() -> list[tuple[date, date]]:
    return sorted(
        (bas, son) for bas, son in SchoolYear.objects.values_list("start_date", "end_date")
    )


def ders_yili_sonu(gun: date, yillar: Sequence[tuple[date, date]] | None = None) -> date:
    """`gun`ü kapsayan ders yılının bitişi (A3 "ders yılı sonu").

    Kapsayan yıl yoksa (yaz arası) bitişi `gun`den sonra gelen ilk ders yılı; hiç yoksa
    izleyen 30 Haziran (Türkiye'de ders yılı Haziran'da biter — yedek kural).
    """
    yillar = _ders_yillari() if yillar is None else yillar
    for bas, son in yillar:
        if bas <= gun <= son:
            return son
    sonrakiler = [son for _bas, son in yillar if son >= gun]
    if sonrakiler:
        return min(sonrakiler)
    return date(gun.year if gun.month <= 6 else gun.year + 1, 6, 30)


def _parcalar(kimlikler: Iterable[int]) -> Iterator[list[int]]:
    liste = sorted(set(kimlikler))
    for i in range(0, len(liste), _PARCA):
        yield liste[i : i + _PARCA]


# ---------------------------------------------------------------------------
# Plan (aday tespiti) — kişisiz kimlik kümeleri
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SaklamaPlani:
    """Bugün süresi dolmuş kayıtlar — kural başına kimlik kümeleri (kişisiz; yalnız pk).

    Ödünç ve dosyada kural sırası: önce "sonlanmış üyelik" (üyeliğin bütün kapalı
    bağları), sonra kendi süresi (A3 / kapanış + N); bir kayıt yalnız birinde sayılır.
    """

    bugun: date
    loans_terminated: frozenset[int]
    loans_returned: frozenset[int]
    cases_terminated: frozenset[int]
    cases_closed: frozenset[int]
    deliveries: frozenset[int]
    memberships: frozenset[int]
    students: frozenset[int]
    personnel: frozenset[int]
    persons_held: int

    @property
    def loans(self) -> frozenset[int]:
        return self.loans_terminated | self.loans_returned

    @property
    def cases(self) -> frozenset[int]:
        return self.cases_terminated | self.cases_closed

    @property
    def bos(self) -> bool:
        return not any(
            (
                self.loans,
                self.cases,
                self.deliveries,
                self.memberships,
                self.students,
                self.personnel,
            )
        )

    def ozet(self) -> dict[str, Any]:
        """Kişisiz sayılar (API, pano, günlük ve `RetentionRun.summary`)."""
        sayilar = {
            "students": len(self.students),
            "personnel": len(self.personnel),
            "memberships": len(self.memberships),
            "loans_terminated": len(self.loans_terminated),
            "loans_returned": len(self.loans_returned),
            "cases_terminated": len(self.cases_terminated),
            "cases_closed": len(self.cases_closed),
            "deliveries": len(self.deliveries),
        }
        return {**sayilar, "total": sum(sayilar.values()), "persons_held": self.persons_held}

    @property
    def anahtar(self) -> str:
        """Önizlemenin parmak izi: onaylanan liste ile tetik anındaki liste aynı mı?"""
        veri = {
            "bugun": self.bugun.isoformat(),
            "loans_terminated": sorted(self.loans_terminated),
            "loans_returned": sorted(self.loans_returned),
            "cases_terminated": sorted(self.cases_terminated),
            "cases_closed": sorted(self.cases_closed),
            "deliveries": sorted(self.deliveries),
            "memberships": sorted(self.memberships),
            "students": sorted(self.students),
            "personnel": sorted(self.personnel),
        }
        return hashlib.sha256(json.dumps(veri, sort_keys=True).encode("utf-8")).hexdigest()


def _kimlikler(qs: Any, alan: str = "pk") -> set[int]:
    return {int(v) for v in qs.values_list(alan, flat=True) if v is not None}


def plan_hesapla(bugun: date | None = None) -> SaklamaPlani:
    """Bugün süresi dolan kayıtları bulur (kayıt YAZMAZ). Bütün yumuşak silinmişler dahil.

    Yumuşak silinmiş satır da kişi bağı taşıyabilir; saklama `all_objects` ile bakar.
    """
    gun = bugun or timezone.localdate()
    politika = LibraryPolicy.load()

    # A — süresi dolmuş sonlanmış üyelikler; bağları (kapalı ödünç ve dosya) koparılır.
    esik_uyelik = yil_ekle(gun, -int(politika.retention_years_after_termination))
    vadeli_uyelikler = _kimlikler(
        Membership.all_objects.filter(
            status=MembershipStatus.TERMINATED, terminated_at__lte=esik_uyelik
        )
    )
    loans_terminated = _kimlikler(
        Loan.all_objects.filter(
            membership_id__in=vadeli_uyelikler,
            status__in=KAPALI_ODUNC,
            anonymized_at__isnull=True,
        )
    )

    # C (A3) — iade edilmiş ödünçler: ders yılı sonu + M. Kapanış gününden M yıl geçmemiş
    # ödünç zaten aday olamaz (ders yılı sonu kapanıştan önce değildir); süzgeç bunu DB'de ister.
    m_yil = int(politika.retention_years_returned_loans)
    sinir = _gun_bitti(yil_ekle(gun, -m_yil))
    yillar = _ders_yillari()
    loans_returned: set[int] = set()
    for pk, iade, kayip in (
        Loan.all_objects.filter(
            membership__isnull=False, anonymized_at__isnull=True, status__in=KAPALI_ODUNC
        )
        .filter(Q(returned_at__lt=sinir) | Q(lost_at__lt=sinir))
        .values_list("pk", "returned_at", "lost_at")
    ):
        kapanis_ani = iade if iade is not None else kayip
        if kapanis_ani is None or pk in loans_terminated:
            continue
        kapanis = timezone.localdate(kapanis_ani)
        if yil_ekle(ders_yili_sonu(kapanis, yillar), m_yil) <= gun:
            loans_returned.add(int(pk))

    # A — dosyalar; D — kapanış + N (kişi bağı taşıyan kapanmış dosyalar).
    cases_terminated = _kimlikler(
        LossDamageCase.all_objects.filter(
            membership_id__in=vadeli_uyelikler, anonymized_at__isnull=True
        ).exclude(resolution__in=OPEN_CASE_RESOLUTIONS)
    )
    esik_dosya = yil_ekle(gun, -int(politika.retention_years_closed_cases))
    cases_closed = (
        _kimlikler(
            LossDamageCase.all_objects.filter(
                anonymized_at__isnull=True, resolved_at__lt=_gun_bitti(esik_dosya)
            )
            .exclude(resolution__in=OPEN_CASE_RESOLUTIONS)
            .filter(
                Q(membership__isnull=False)
                | ~Q(responsible_note="")
                | Q(delivery__personnel__isnull=False)
            )
        )
        - cases_terminated
    )
    dosyalar = cases_terminated | cases_closed

    # E — kapanmış öğretmen teslimleri (geri alma ya da kayba dönüşme + N). Kişiyi bu
    # teslimden bulan, anonimleştirilmemiş ve bu tetikte de anonimleştirilmeyecek dosya
    # (üyeliksiz — açık ya da süresi dolmamış) varken bağ KOPARILMAZ.
    esik_teslim = _gun_bitti(yil_ekle(gun, -int(politika.retention_years_closed_deliveries)))
    ogretmen_teslimleri = Delivery.all_objects.filter(
        recipient_kind=DeliveryRecipientKind.TEACHER,
        personnel__isnull=False,
        anonymized_at__isnull=True,
    )
    aday_teslim = _kimlikler(
        ogretmen_teslimleri.filter(
            Q(status=DeliveryStatus.RETURNED, returned_at__lt=esik_teslim)
            | Q(status=DeliveryStatus.LOST_CONVERTED, lost_at__lt=esik_teslim)
        )
    )
    teslime_dayanan = _kimlikler(
        LossDamageCase.all_objects.filter(
            delivery_id__in=aday_teslim, membership__isnull=True, anonymized_at__isnull=True
        ).exclude(pk__in=dosyalar),
        "delivery_id",
    )
    uygun_teslim = aday_teslim - teslime_dayanan
    # Düzeltme turu (F11): bağ BELGE NO düzeyinde koparılır. Aynı toplu teslimin satırları
    # aynı belge no'yu taşır (E15); bir satırın bağı koparılıp öbürü öğretmene bağlı kalsa
    # anonimleştirilmiş satır o belge no üzerinden öğretmene yeniden bağlanır (KVKK 3/1-b
    # "başka verilerle eşleştirilerek dahi") ve yeniden basılan E15 ibareyle birlikte
    # öğretmenin adını basardı. Belgenin bağı koparılmamış BÜTÜN satırları bu tetikte
    # koparılabiliyorsa hepsi birlikte koparılır; değilse hepsi bekler (dosyadaki bekletme
    # kuralının aynısı). Kişinin silinmesi zaten bütün teslimlerini ister (`personel_engel`).
    belge_satirlari = ogretmen_teslimleri.filter(
        document_no__in=set(
            Delivery.all_objects.filter(pk__in=uygun_teslim).values_list("document_no", flat=True)
        )
    ).values_list("pk", "document_no")
    bekleyen_belgeler = {belge for pk, belge in belge_satirlari if pk not in uygun_teslim}
    deliveries = {pk for pk, belge in belge_satirlari if belge not in bekleyen_belgeler}

    # Kişisini teslim bağından bulan dosya (üyeliksiz, öğretmen teslimi) o teslimin bağı bu
    # tetikte koparılmıyorsa bekler: yoksa anonimleştirilmiş tutanağın "Teslim — belge no"
    # satırı kişiyi yeniden gösterirdi. Tek geçiş yeter: bekleyen dosyanın teslimi zaten
    # planda değildir (ve belgesi bekler).
    teslimi_bekleyen = _kimlikler(
        LossDamageCase.all_objects.filter(
            pk__in=dosyalar,
            membership__isnull=True,
            delivery__recipient_kind=DeliveryRecipientKind.TEACHER,
            delivery__personnel__isnull=False,
            delivery__anonymized_at__isnull=True,
        ).exclude(delivery_id__in=deliveries)
    )
    cases_terminated -= teslimi_bekleyen
    cases_closed -= teslimi_bekleyen
    dosyalar = cases_terminated | cases_closed

    # Düzeltme turu (F11): kişi bağı henüz koparılmamış bir dosyaya (açık ya da süresi
    # dolmamış) bağlı ödünç BEKLER. Ödünç → dosya.loan → dosya.membership zinciri ödüncü
    # kişiye yeniden bağlardı; açık yükümlülükte bağ koparılmaz (§6.4). Dosya kapanıp
    # kendi süresi dolunca ödünç onunla birlikte koparılır.
    # Yalnız hâlâ bir kişiye bağlanan dosya bekletir (kişi bağı hiç olmayan dosya ödüncü
    # kimseye bağlayamaz; onu beklemek ödüncü sonsuza dek bekletirdi).
    dosyasi_bekleyen_odunc = _kimlikler(
        LossDamageCase.all_objects.filter(loan__isnull=False, anonymized_at__isnull=True)
        .filter(
            Q(membership__isnull=False)
            | ~Q(responsible_note="")
            | Q(delivery__personnel__isnull=False)
        )
        .exclude(pk__in=dosyalar),
        "loan_id",
    )
    loans_terminated -= dosyasi_bekleyen_odunc
    loans_returned -= dosyasi_bekleyen_odunc

    # B — silinecek üyelik satırları: süresi dolmuş, açık ödüncü, açık dosyası ve bekleyen
    # (bağı bu tetikte koparılmayan) ödüncü yok.
    acik = (
        _kimlikler(
            Loan.all_objects.filter(membership_id__in=vadeli_uyelikler, status=LoanStatus.OPEN),
            "membership_id",
        )
        | _kimlikler(
            LossDamageCase.all_objects.filter(
                membership_id__in=vadeli_uyelikler, resolution__in=OPEN_CASE_RESOLUTIONS
            ),
            "membership_id",
        )
        | _kimlikler(
            Loan.all_objects.filter(
                membership_id__in=vadeli_uyelikler, pk__in=dosyasi_bekleyen_odunc
            ),
            "membership_id",
        )
    )
    memberships = vadeli_uyelikler - acik

    # R1 — ayrılmış kişiler (karar 2: ayrılış + 2 yıl). Bütün üyelikleri silinebilir ve
    # (personelde) bütün teslim bağları bu tetikte koparılabilir olmalı; değilse bekler.
    esik_kisi = yil_ekle(gun, -int(politika.retention_years_left_person))
    ogrenci_aday = _kimlikler(
        Student.all_objects.filter(
            status=StudentStatus.LEFT, left_at__isnull=False, left_at__lte=esik_kisi
        )
    )
    personel_aday = _kimlikler(
        Personnel.all_objects.filter(is_active=False, left_at__isnull=False, left_at__lte=esik_kisi)
    )
    ogrenci_engel = {
        int(kisi)
        for kisi, uyelik in Membership.all_objects.filter(student_id__in=ogrenci_aday).values_list(
            "student_id", "pk"
        )
        if uyelik not in memberships
    }
    personel_engel = {
        int(kisi)
        for kisi, uyelik in Membership.all_objects.filter(
            personnel_id__in=personel_aday
        ).values_list("personnel_id", "pk")
        if uyelik not in memberships
    } | {
        int(kisi)
        for kisi, teslim in Delivery.all_objects.filter(personnel_id__in=personel_aday).values_list(
            "personnel_id", "pk"
        )
        if teslim not in deliveries
    }
    students = ogrenci_aday - ogrenci_engel
    personnel = personel_aday - personel_engel

    return SaklamaPlani(
        bugun=gun,
        loans_terminated=frozenset(loans_terminated),
        loans_returned=frozenset(loans_returned),
        cases_terminated=frozenset(cases_terminated),
        cases_closed=frozenset(cases_closed),
        deliveries=frozenset(deliveries),
        memberships=frozenset(memberships),
        students=frozenset(students),
        personnel=frozenset(personnel),
        persons_held=len(ogrenci_engel) + len(personel_engel),
    )


# ---------------------------------------------------------------------------
# Uygulama (tek işlem)
# ---------------------------------------------------------------------------
def _uygula(plan: SaklamaPlani, an: datetime) -> None:
    """Planı uygular — çağıranın işlem bloğunda; bir adım düşerse hepsi geri sarılır.

    Sıra: ödünç → dosya → teslim bağları (açık güncelleme), sonra üyelik satırları
    (kart iptal kaydı + katı silme), en son kişiler (katı silme). Silme öncesi her
    kişi için açık yükümlülük yeniden sorulur (kod kapısı).
    """
    for parca in _parcalar(plan.loans):
        Loan.all_objects.filter(pk__in=parca, anonymized_at__isnull=True).update(
            membership=None,
            override_reason="",
            override_note="",
            cardless_reason="",
            anonymized_at=an,
            updated_at=an,
        )
    for parca in _parcalar(plan.cases):
        LossDamageCase.all_objects.filter(pk__in=parca, anonymized_at__isnull=True).exclude(
            resolution__in=OPEN_CASE_RESOLUTIONS
        ).update(membership=None, responsible_note="", anonymized_at=an, updated_at=an)
    for parca in _parcalar(plan.deliveries):
        Delivery.all_objects.filter(pk__in=parca, anonymized_at__isnull=True).exclude(
            status=DeliveryStatus.OPEN
        ).update(personnel=None, anonymized_at=an, updated_at=an)

    for parca in _parcalar(plan.memberships):
        # Basılıp verilmiş kart okutulursa "tanınmayan" değil "iptal edilmiş kart" denir
        # (`services.memberships.delete_membership` kuralı); iptal kaydı kişisizdir.
        indeksler = set(
            Membership.all_objects.filter(pk__in=parca).values_list("card_no_index", flat=True)
        )
        var = set(
            CardRevocation.objects.filter(card_no_index__in=indeksler).values_list(
                "card_no_index", flat=True
            )
        )
        CardRevocation.objects.bulk_create(
            [
                CardRevocation(
                    card_no_index=indeks, membership=None, reason=CardRevocationReason.DELETED
                )
                for indeks in sorted(indeksler - var)
            ]
        )
        CardRevocation.objects.filter(membership_id__in=parca).update(membership=None)
        if (
            Loan.all_objects.filter(membership_id__in=parca).exists()
            or LossDamageCase.all_objects.filter(membership_id__in=parca).exists()
        ):
            # Plan her kapalı bağı içerir; açık bağ varsa üyelik plana girmemiştir.
            raise ValidationError(LISTE_DEGISTI_MESAJI)
        cast("SoftDeleteQuerySet", Membership.all_objects.filter(pk__in=parca)).hard_delete()

    for model, kimlikler in ((Student, plan.students), (Personnel, plan.personnel)):
        for parca in _parcalar(kimlikler):
            for kisi in model.all_objects.filter(pk__in=parca):
                if persons.open_obligations(kisi) or persons.deletion_blocks(kisi):
                    raise ValidationError(ACIK_YUKUMLULUK_MESAJI)
            cast("SoftDeleteQuerySet", model.all_objects.filter(pk__in=parca)).hard_delete()


def durum_yaz(gun: date, plan: SaklamaPlani) -> RetentionState:
    """Taramanın kişisiz özetini yazar; onay bekleme başlangıcını tutar ya da boşaltır."""
    durum, _ = RetentionState.objects.get_or_create(pk=RetentionState.SINGLETON_PK)
    if plan.bos:
        durum.pending_since = None
    elif durum.pending_since is None:
        durum.pending_since = gun
    durum.last_scan_on = gun
    durum.last_scan = plan.ozet()
    durum.save()
    return durum


def _veritabani_yolu() -> Path:
    return Path(str(connection.settings_dict["NAME"]))


def _veri_dizini() -> Path:
    """Veritabanının klasörü: geri yükleme önceki veritabanını buraya kenara alır."""
    return _veritabani_yolu().parent


def _yedek_al(an: datetime) -> Path:
    """Tetik öncesi `pre-anonim` yedeği; alınamazsa tetik çalışmaz (hiçbir şey yazılmadı)."""
    from desktop import backup
    from desktop.backup_crypto import BackupCryptoError

    yol: Path | None = None
    veritabani = _veritabani_yolu()
    if veritabani.is_file():
        try:
            yol = backup.pre_anonim_backup(
                veritabani,
                app_password.backup_dir(),
                data_dir=app_password.state_path().parent,
                now=timezone.localtime(an),
            )
        except (OSError, sqlite3.Error, BackupCryptoError, ValueError):
            logger.exception("Saklama tetiği öncesi yedek alınamadı.")
            yol = None
    if yol is None:
        raise ValidationError(YEDEK_ALINAMADI_MESAJI)
    return yol


def pre_migrate_temizle(an: datetime) -> tuple[int, list[str]]:
    """Tetik anından eski güncelleme öncesi yedekleri siler (§6.4): (silinen sayısı,
    silinemeyen ADLAR).

    Hangi dosyaların silineceği YALNIZ tetik anında, dosya zamanıyla belirlenir; sonra
    her şey ada göredir (`pre_migrate_yeniden_dene`).
    """
    from desktop import backup

    dizin = app_password.backup_dir()
    hedefler = [yol.name for yol in backup.pre_migrate_before(dizin, an)]
    silinen, kalan = backup.remove_pre_migrate_named(dizin, hedefler)
    return len(silinen), kalan


def pre_migrate_yeniden_dene() -> int:
    """Tetikte silinemeyen güncelleme öncesi yedekleri ADIYLA yeniden siler; silinen sayısı.

    Gün değişimi kapısının kendini onarma adımıdır (F11 düzeltme turu): dosya zamanını
    tetik anıyla karşılaştırmaz — okul bilgisayarının saati sonradan geri kayarsa
    (CMOS pili, ağsız NTP) tetikten SONRA alınmış bir güncelleme yedeği "eski" görünür
    ve silinirdi; geri dönülecek yedek kalmazdı.
    """
    from desktop import backup

    dizin = app_password.backup_dir()
    toplam = 0
    for run in RetentionRun.objects.order_by("pk"):
        if not run.pre_migrate_pending:
            continue
        silinen, kalan = backup.remove_pre_migrate_named(
            dizin, [str(ad) for ad in run.pre_migrate_pending]
        )
        run.pre_migrate_removed += len(silinen)
        run.pre_migrate_pending = kalan
        run.save(update_fields=["pre_migrate_removed", "pre_migrate_pending"])
        toplam += len(silinen)
    return toplam


def onceki_veritabani_siniri(an: datetime) -> datetime:
    """Önceki veritabanı dosyasının tetikte silinme sınırı: `an`dan 14 gün önce.

    14 gün günlük ve işlem öncesi (`pre-anonim`) yedeklerin süresidir
    (`backup.DEFAULT_KEEP_DAYS`) ve aynı gerekçeye dayanır (27.09.2026 kullanıcı kararı):
    yakın tarihli bir geri yüklemeden dönüş yolu korunur, eski artık temizlenir.
    """
    from desktop import backup

    return timezone.localtime(an) - timedelta(days=int(backup.DEFAULT_KEEP_DAYS))


def _veritabani_sayisi(adlar: Iterable[str]) -> int:
    """Dosya adlarından veritabanı sayısı: `-wal`/`-shm` eşleri ayrı sayılmaz (D-4)."""
    return sum(1 for ad in adlar if backup_restore.is_old_database_file(ad))


def onceki_veritabani_temizle(an: datetime) -> tuple[int, list[str]]:
    """Tetik anından 14 günden eski önceki veritabanı dosyalarını siler: (silinen veritabanı
    sayısı, silinemeyen ADLAR).

    Geri yükleme veritabanını silmez, veri klasöründe `db-onceki-<damga>.sqlite3` adıyla
    (`-wal`/`-shm` eşleriyle) kenara alır; o dosya anonimleştirilen bağları ve silinen
    kişileri taşır. Yaş ADINDAKİ damgadan okunur (geri yüklemenin anı), dosya zamanından
    değil: taşınan dosya zamanını korur, yani dosya zamanı eski veritabanına son yazılan
    anı söyler (gerekçe `backup_restore` başlığında). Silinecekler YALNIZ tetik anında
    belirlenir; sonra her şey ada göredir (`onceki_veritabani_yeniden_dene`).
    """
    veri = _veri_dizini()
    hedefler = backup_restore.old_databases_before(veri, onceki_veritabani_siniri(an))
    silinen, kalan = backup_restore.remove_old_databases_named(veri, hedefler)
    return _veritabani_sayisi(silinen), kalan


def onceki_veritabani_yeniden_dene() -> int:
    """Tetikte silinemeyen önceki veritabanı dosyalarını ADIYLA yeniden siler; silinen
    veritabanı sayısı.

    Gün değişimi kapısının kendini onarma adımıdır (`pre_migrate_yeniden_dene`'nin eşi):
    damgayı tetik anıyla yeniden karşılaştırmaz — sistem saati tetikten sonra geri kaymış
    ya da ileri gitmişken yapılan bir geri yüklemenin dosyası "eski" görünse de silinmez.
    """
    veri = _veri_dizini()
    toplam = 0
    for run in RetentionRun.objects.order_by("pk"):
        if not run.old_db_pending:
            continue
        silinen, kalan = backup_restore.remove_old_databases_named(
            veri, [str(ad) for ad in run.old_db_pending]
        )
        sayi = _veritabani_sayisi(silinen)
        run.old_db_removed += sayi
        run.old_db_pending = kalan
        run.save(update_fields=["old_db_removed", "old_db_pending"])
        toplam += sayi
    return toplam


def wal_bosalt() -> bool:
    """`PRAGMA wal_checkpoint(TRUNCATE)` — işlem bloğu dışında; başarıyla boşaldıysa True.

    `secure_delete` açık olduğu için koparılan bağların eski değerleri veritabanı
    sayfalarında sıfırla ezilir; WAL'deki eski sayfa görüntüleri de checkpoint ile
    dosyaya işlenip WAL sıfıra indirilir (TB24 değerlendirmesi). Ağ Kataloğu'nun salt
    okur bağlantısı o an okuyorsa checkpoint "meşgul" döner; bir sonraki olağan
    checkpoint aynı işi yapar.
    """
    if connection.in_atomic_block:
        return False
    try:
        with connection.cursor() as imlec:
            imlec.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            satir = imlec.fetchone()
    except DatabaseError:
        logger.warning("Saklama tetiği sonrası WAL boşaltılamadı.", exc_info=True)
        return False
    return bool(satir) and int(satir[0]) == 0


@dataclass(frozen=True)
class TetikSonucu:
    run: RetentionRun
    ozet: dict[str, Any]
    wal_bosaldi: bool


def tetikle(*, anahtar: str, bugun: date | None = None, kapi: BakimKapisi = KAPI) -> TetikSonucu:
    """Onaylı, GERİ DÖNÜŞSÜZ saklama tetiği (§6.4 çalışma biçimi 2-3).

    Yönetici kipinde ve yönetici parolası doğrulandıktan sonra çağrılır (görünüm
    parolayı sorar). `anahtar` kullanıcının onayladığı önizlemenin parmak izidir;
    tetik anındaki liste farklıysa 409 ve hiçbir şey yazılmaz. Sıra: yedek → tek
    işlem → işlem sonrası dosya işleri (pre-migrate silme, 14 günden eski önceki
    veritabanı dosyalarını silme, WAL boşaltma). Dosya işleri işlem KALICI olduktan sonra
    yapılır: işlem geri sarılırsa hiçbir dosya silinmez; silinemeyen dosya tetiği
    başarısız saymaz (adı `RetentionRun`'a yazılır, gün değişimi kapısı yeniden dener).
    """
    require_admin_mode()
    app_password.require_password_set()
    gun = bugun or timezone.localdate()
    with kapi.is_() as izin:
        if not izin:
            raise ValidationError(BAKIM_MESAJI)
        plan = plan_hesapla(gun)
        if plan.bos:
            raise ValidationError(BOS_MESAJI)
        if plan.anahtar != anahtar:
            raise SaklamaListesiDegisti()
        an = timezone.now()
        yedek = _yedek_al(an)
        with transaction.atomic():
            plan = plan_hesapla(gun)
            if plan.anahtar != anahtar:
                raise SaklamaListesiDegisti()
            _uygula(plan, an)
            ozet = plan.ozet()
            run = RetentionRun.objects.create(ran_at=an, backup_name=yedek.name, summary=ozet)
            durum_yaz(gun, plan_hesapla(gun))
        # İşlem kalıcı oldu: tetik anından eski güncelleme öncesi yedekler anonimleştirilen
        # bağları taşır. Silinemeyen dosyayı gün değişimi taraması ADIYLA yeniden dener.
        try:
            run.pre_migrate_removed, run.pre_migrate_pending = pre_migrate_temizle(an)
            run.save(update_fields=["pre_migrate_removed", "pre_migrate_pending"])
        except OSError:
            logger.warning("Güncelleme öncesi yedekler silinemedi.", exc_info=True)
        # Geri yüklemenin kenara aldığı veritabanı da silinen kişileri ve koparılan bağları
        # taşır: tetik anından 14 günden eskiler silinir (27.09.2026 kullanıcı kararı);
        # yenileri yakın tarihli geri yüklemenin dönüş yolu olarak kalır.
        try:
            run.old_db_removed, run.old_db_pending = onceki_veritabani_temizle(an)
            run.save(update_fields=["old_db_removed", "old_db_pending"])
        except OSError:
            logger.warning("Önceki veritabanı dosyaları silinemedi.", exc_info=True)
        bosaldi = wal_bosalt()
    logger.info(
        "Saklama işlemi uygulandı: %d kişi silindi, %d üyelik silindi, %d ödünç, %d dosya, "
        "%d teslim anonimleştirildi; %d güncelleme öncesi yedek ve %d önceki veritabanı "
        "silindi.",
        ozet["students"] + ozet["personnel"],
        ozet["memberships"],
        ozet["loans_terminated"] + ozet["loans_returned"],
        ozet["cases_terminated"] + ozet["cases_closed"],
        ozet["deliveries"],
        run.pre_migrate_removed,
        run.old_db_removed,
    )
    return TetikSonucu(run=run, ozet=ozet, wal_bosaldi=bosaldi)


# ---------------------------------------------------------------------------
# Okuma: durum, silinecek kişiler, bedel hatırlatma listesi
# ---------------------------------------------------------------------------
def onay_son_gunu(bekleme: date | None) -> date | None:
    """Onay beklemenin azami süresinin (6 ay) son günü."""
    return ay_ekle(bekleme, AZAMI_BEKLEME_AY) if bekleme is not None else None


def _yedek_sayilari(an: datetime | None = None) -> dict[str, int]:
    """Yedeklerdeki kalıntı (§6.4): klasördeki güncelleme öncesi yedek ve önceki veritabanı.

    `old_databases_expired`: önceki veritabanlarından `an` (varsayılan şimdi) itibarıyla
    14 günden eski olanlar — işlem şimdi uygulansa silinecekler.
    """
    from desktop.backup import PRE_ANONIM_PREFIX, PRE_MIGRATE_PREFIX
    from desktop.backup_crypto import BACKUP_SUFFIX

    dizin = app_password.backup_dir()
    veri = _veri_dizini()

    def say(klasor: Path, desen: str) -> int:
        try:
            return sum(1 for yol in klasor.glob(desen) if yol.is_file())
        except OSError:
            return 0

    return {
        "pre_migrate": say(dizin, f"{PRE_MIGRATE_PREFIX}-*{BACKUP_SUFFIX}"),
        "pre_anonim": say(dizin, f"{PRE_ANONIM_PREFIX}-*{BACKUP_SUFFIX}"),
        # Geri yükleme kenara aldığı veritabanının `-wal`/`-shm` dosyalarını da aynı ön
        # ekle taşır (`backup_restore._swap_database_files`); onlar ayrı bir "önceki
        # veritabanı" değildir — yalnız `.sqlite3` sayılır (F11 düzeltme turu).
        "old_databases": say(veri, f"{backup_restore.OLD_DB_PREFIX}-*.sqlite3"),
        "old_databases_expired": _veritabani_sayisi(
            backup_restore.old_databases_before(
                veri, onceki_veritabani_siniri(an or timezone.now())
            )
        ),
    }


@dataclass(frozen=True)
class BedelHatirlatmasi:
    """Bedel adımında bir yıldan uzun bekleyen dosya — kişisiz satır."""

    case_id: int
    barcode: str
    title: str
    case_type: str
    resolution: str
    step_date: date
    years_waiting: int


def bedel_hatirlatmalari(bugun: date | None = None) -> list[BedelHatirlatmasi]:
    """Yıllık hatırlatma listesi (§6.4): "Bedel belirlendi" ya da "Bedel teslim alındı"da
    bir yıldan uzun bekleyen dosyalar. Sessizce silinmez; en eski adım önce."""
    from apps.kutuphane import barcode as barcode_module

    gun = bugun or timezone.localdate()
    esik = yil_ekle(gun, -BEDEL_HATIRLATMA_YIL)
    satirlar: list[BedelHatirlatmasi] = []
    for dosya in LossDamageCase.objects.filter(resolution__in=BEDEL_BEKLEYEN).select_related(
        "copy", "copy__work"
    ):
        adim_ani = (
            dosya.price_received_at
            if dosya.resolution == CaseResolution.PRICE_RECEIVED and dosya.price_received_at
            else dosya.price_determined_at
        )
        adim = timezone.localdate(adim_ani) if adim_ani is not None else dosya.reported_on
        if adim > esik:
            continue
        yil = gun.year - adim.year - ((gun.month, gun.day) < (adim.month, adim.day))
        satirlar.append(
            BedelHatirlatmasi(
                case_id=dosya.pk,
                barcode=barcode_module.format_barcode(dosya.copy.barcode),
                title=dosya.copy.work.title,
                case_type=str(dosya.get_case_type_display()),
                resolution=str(dosya.get_resolution_display()),
                step_date=adim,
                years_waiting=max(1, yil),
            )
        )
    satirlar.sort(key=lambda s: (s.step_date, s.case_id))
    return satirlar


def durum(bugun: date | None = None) -> dict[str, Any]:
    """Ayarlar → Saklama ekranının kişisiz durumu (kayıt YAZMAZ)."""
    gun = bugun or timezone.localdate()
    plan = plan_hesapla(gun)
    politika = LibraryPolicy.load()
    kayit = RetentionState.load()
    bekleme = None if plan.bos else (kayit.pending_since or gun)
    son_gun = onay_son_gunu(bekleme)
    son = RetentionRun.objects.order_by("-ran_at", "-pk").first()
    return {
        "today": gun,
        "policy": {
            "left_person_years": int(politika.retention_years_left_person),
            "after_termination_years": int(politika.retention_years_after_termination),
            "returned_loans_years": int(politika.retention_years_returned_loans),
            "closed_cases_years": int(politika.retention_years_closed_cases),
            "closed_deliveries_years": int(politika.retention_years_closed_deliveries),
        },
        "candidates": plan.ozet(),
        "digest": "" if plan.bos else plan.anahtar,
        "pending_since": bekleme,
        "approval_deadline": son_gun,
        "overdue": son_gun is not None and gun > son_gun,
        "max_wait_months": AZAMI_BEKLEME_AY,
        "last_scan_on": kayit.last_scan_on,
        "last_run": (
            {
                "ran_at": son.ran_at,
                "backup_name": son.backup_name,
                "summary": son.summary,
                "pre_migrate_removed": son.pre_migrate_removed,
                "old_db_removed": son.old_db_removed,
            }
            if son is not None
            else None
        ),
        "price_reminders": len(bedel_hatirlatmalari(gun)),
        "residue": _yedek_sayilari(),
    }


def pano_ozeti(bugun: date | None = None) -> dict[str, Any]:
    """Genel Bakış kartlarının kişisiz özeti: aday sayısı, 6 ay uyarısı, bedel listesi."""
    gun = bugun or timezone.localdate()
    plan = plan_hesapla(gun)
    kayit = RetentionState.load()
    bekleme = None if plan.bos else (kayit.pending_since or gun)
    son_gun = onay_son_gunu(bekleme)
    return {
        "candidates": plan.ozet()["total"],
        "pending_since": bekleme,
        "approval_deadline": son_gun,
        "overdue": son_gun is not None and gun > son_gun,
        "price_reminders": len(bedel_hatirlatmalari(gun)),
    }


#: `SilinecekKisi.scope` — neyin silineceği: kişinin kaydı (üyelikleriyle birlikte) ya da
#: yalnız sona ermiş üyelik kaydı (kişi kaydı KALIR — kişi okulda sürüyor ya da süresi
#: henüz dolmadı).
KAPSAM_KISI: Final = "person"
KAPSAM_UYELIK: Final = "membership"


@dataclass(frozen=True)
class SilinecekKisi:
    """Tetikte kaydı silinecek kişi ya da üyelik sahibi — AD İÇERİR; yalnız yönetici kipi.

    "Ne silinecek" önizlemesinin ayrıntısıdır (Ayarlar → Saklama → "Silinecek kişileri
    göster"): kişi kaydı silinecekler (`scope="person"`, ayrılış tarihiyle) ve kişi kaydı
    kalıp yalnız sona ermiş üyelik kaydı silinecekler (`scope="membership"`, üyeliğin
    sonlandığı tarihle). Kaydı silinecek kişinin üyeliği ikinci kez listelenmez.
    """

    kind: str
    person_id: int
    full_name: str
    label: str
    left_at: date | None
    scope: str = KAPSAM_KISI
    terminated_at: date | None = None


def silinecek_kisiler(bugun: date | None = None) -> list[SilinecekKisi]:
    """Tetikte kaydı silinecek kişiler ve üyelik sahipleri, Türkçe ada göre (yönetici kipi).

    Liste tetikle AYNI plandan gelir (`plan_hesapla`): önizlemede görülen ad tetikte
    silinen kayıttır. Önce kişi kayıtları, sonra yalnız üyeliği silinecekler.
    """
    plan = plan_hesapla(bugun)
    satirlar: list[SilinecekKisi] = [
        SilinecekKisi("student", s.pk, s.full_name, s.class_label, s.left_at)
        for s in Student.all_objects.filter(pk__in=plan.students)
    ]
    satirlar += [
        SilinecekKisi("personnel", p.pk, p.full_name, member_kind_text(p), p.left_at)
        for p in Personnel.all_objects.filter(pk__in=plan.personnel)
    ]
    # Yalnız üyelik kaydı silinecekler: kişi kaydı bu tetikte silinmeyen üyelik sahipleri.
    # `select_related` yumuşak silinmiş kişiyi de getirir (CLAUDE.md §3) — burada istenen
    # budur: satır tetikte silinecek, sahibinin adı önizlemede görünmelidir.
    for uyelik in Membership.all_objects.filter(pk__in=plan.memberships).select_related(
        "student", "personnel"
    ):
        if uyelik.student_id is not None:
            if uyelik.student_id in plan.students:
                continue
            ogr = uyelik.student
            satirlar.append(
                SilinecekKisi(
                    "student",
                    ogr.pk,
                    ogr.full_name,
                    ogr.class_label,
                    ogr.left_at,
                    scope=KAPSAM_UYELIK,
                    terminated_at=uyelik.terminated_at,
                )
            )
        elif uyelik.personnel_id is not None:
            if uyelik.personnel_id in plan.personnel:
                continue
            per = uyelik.personnel
            satirlar.append(
                SilinecekKisi(
                    "personnel",
                    per.pk,
                    per.full_name,
                    member_kind_text(per),
                    per.left_at,
                    scope=KAPSAM_UYELIK,
                    terminated_at=uyelik.terminated_at,
                )
            )
    satirlar.sort(
        key=lambda s: (
            s.scope != KAPSAM_KISI,
            normalize.tr_sort_key(s.full_name),
            s.kind,
            s.person_id,
        )
    )
    return satirlar


# ---------------------------------------------------------------------------
# Gün değişimi kapısı (T9)
# ---------------------------------------------------------------------------
def gunluk_tarama(bugun: date, *, kapi: BakimKapisi = KAPI) -> str:
    """Kapının günlük işi: "tamam", "bakimda" ya da "hata" (kişi bilgisi günlüğe yazılmaz).

    Aday tespiti (`durum_yaz`) ve kendini onarma: tetikte silinemeyen güncelleme öncesi
    yedekler ve önceki veritabanı dosyaları ADIYLA yeniden silinir
    (`pre_migrate_yeniden_dene`, `onceki_veritabani_yeniden_dene`; dosya zamanına ve
    addaki damgaya yeniden bakılmaz).
    """
    with kapi.is_() as izin:
        if not izin:
            return "bakimda"
        try:
            plan = plan_hesapla(bugun)
            with transaction.atomic():
                durum_yaz(bugun, plan)
            pre_migrate_yeniden_dene()
            onceki_veritabani_yeniden_dene()
            if not plan.bos:
                logger.info("Saklama taraması: %d kayıt onay bekliyor.", plan.ozet()["total"])
            return "tamam"
        except Exception:  # noqa: BLE001 — günlük iş zinciri durmaz
            logger.exception("Saklama taraması yapılamadı.")
            return "hata"
        finally:
            if not connection.in_atomic_block:
                connection.close()


def kapi_isi() -> bool:
    """Kapının çağırdığı biçim: yalnız "tamam" günü kapatır; öbürleri bir saat sonra yeniden."""
    return gunluk_tarama(timezone.localdate()) == "tamam"
