"""Yıl sonu kütüphane raporunun sayıları — KİŞİSİZ (F8; Md. 12/1, Kılavuz 2.4, E9).

Md. 12/1: "Her ders yılı sonunda kütüphane kaynakları, kütüphaneci veya
görevlendirilen öğretmen tarafından gözden geçirilir ve tespit edilen hususlar
raporla okul müdürlüğüne bildirilir." Kılavuz 2.4: "Her eğitim öğretim yılı
sonunda kütüphanedeki kitap durumu, kazandırılan ve ayıklanan kaynaklar okul
yönetimine raporlanır."

**Profil yasağı** (CLAUDE.md §2-5, tasarım §3; E9 kod kapısı): bu modül hiçbir
kişinin adını, okul no'sunu, kart no'sunu, üyelik ya da kişi kimliğini, sorumlu
notunu ya da gerekçe metnini OKUMAZ ve DÖNDÜRMEZ (farklı üye sayıları veritabanında
sayılır; kimlik Python'a gelmez). Ödünç istatistiği yalnız toplamlardır; üye türü
ve sınıf düzeyi kırılımlarında bir grubun sayısı, o grupta en az k FARKLI üye
yoksa gösterilmez (`LibraryPolicy.popular_min_members`, çok okunanlar eşiğiyle
aynı değer). **Tamamlayıcı gizleme:** toplam ve üst grup basıldığı için gizli bir
hücre çıkarmayla geri bulunmasın diye, bir toplamdan türetilebilen gizli hücreler
birlikte k'dan az farklı üyeye aitse bir hücre daha gizlenir (`_gizlenenler`).
Rapor anındaki aktif üye sayısı da k'nın altında gösterilmez. Şube × konu
kırılımı ve adlı sıralama YOKTUR. Koruma testi sentetik adlarla bütün çıktıyı
tarar ve her kırılımda "toplam − görünenler" türetmesini sınar
(`tests/test_yil_sonu_raporu.py`).

**Dönem.** Ders yılının başlangıcından bir SONRAKİ ders yılının başlangıcına dek
(sonraki yıl yoksa bugüne ya da ders yılı sonuna — hangisi geçse): kılavuzun
takvimi ayıklamayı Ağustos'a koyar (bakım ve güncelleme), yaz aylarındaki işlem
iki ders yılının arasında kaybolmasın.

Çıktı JSON'a doğrudan yazılabilir (tarihler ISO metni, sayılar tamsayı): rapor
sonlandırılınca `AnnualLibraryReview.stats` olarak dondurulur.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any, Final

from django.db.models import Count, Q
from django.utils import timezone

from apps.kutuphane import keys
from apps.kutuphane.models import (
    OPEN_CASE_RESOLUTIONS,
    TERMINAL_COPY_STATUSES,
    AcquisitionMethod,
    CaseResolution,
    CaseType,
    Copy,
    CopyRepair,
    CopyStatus,
    Delivery,
    DeliveryRecipientKind,
    DonationIntake,
    DonationIntakeItem,
    DonationIntakeStatus,
    DonationItemDecision,
    LibraryPolicy,
    Loan,
    LossDamageCase,
    Membership,
    MembershipStatus,
    ResourceType,
    WeedingBatchStatus,
    WeedingItem,
    WeedingItemState,
    WeedingReason,
    WeedingTmyPath,
    Work,
)
from apps.okul.models import MemberKind, SchoolYear

#: Çıktı şemasının sürümü (dondurulmuş raporlar eski sürümle de okunabilsin).
#: 2 (F8 düzeltme turu): kazandırılanlar yalnız Md. 10/5 yolları, kayıt içi girişler
#: ayrı; tamamlayıcı gizleme; aktif üye sayısı eşikli.
SCHEMA_VERSION: Final = 2

#: Md. 10/5'in dışarıdan sağlama yolları — "kazandırılan" yalnız bunlardır (Kılavuz 2.3,
#: 2.4). Öbür iki yol kayıt içi giriştir (programa aktarım, sayım fazlası).
KAZANDIRMA_YOLLARI: Final[tuple[str, ...]] = (
    AcquisitionMethod.MINISTRY,
    AcquisitionMethod.PURCHASE,
    AcquisitionMethod.DONATION,
    AcquisitionMethod.EXCHANGE,
)
KAYIT_ICI_YOLLAR: Final[tuple[str, ...]] = (
    AcquisitionMethod.INVENTORY_FOUND,
    AcquisitionMethod.EXISTING_STOCK,
)

#: Üye türü grupları (kişiden türer — `MemberType` ile aynı sözcükler).
UYE_TURLERI: Final[tuple[str, ...]] = ("STUDENT", "TEACHER", "STAFF")


def report_period(school_year: SchoolYear, *, today: date | None = None) -> tuple[date, date]:
    """Raporun dönemi (başlangıç, bitiş — ikisi de dahil). Modül belgesi "Dönem"."""
    bugun = today or timezone.localdate()
    sonraki: SchoolYear | None = (
        SchoolYear.objects.filter(start_date__gt=school_year.start_date)
        .order_by("start_date")
        .first()
    )
    if sonraki is not None:
        return school_year.start_date, sonraki.start_date - timedelta(days=1)
    return school_year.start_date, max(school_year.end_date, bugun)


def _anlar(bas: date, son: date) -> tuple[datetime, datetime]:
    """Tarih aralığının yerel saatle [başlangıç, bitişten sonraki gün) anları."""
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(bas, time.min), tz),
        timezone.make_aware(datetime.combine(son + timedelta(days=1), time.min), tz),
    )


def _esik() -> int:
    return int(LibraryPolicy.load().popular_min_members)


def _esikli(sayi: int, gizli: bool) -> dict[str, Any]:
    """Kırılım hücresi: gizliyse sayı GÖSTERİLMEZ (profil yasağı — `_gizlenenler`)."""
    if gizli:
        return {"loans": None, "below_threshold": True}
    return {"loans": sayi, "below_threshold": False}


# ---------------------------------------------------------------------------
# Bölümler
# ---------------------------------------------------------------------------
def _koleksiyon() -> dict[str, Any]:
    """Koleksiyon özeti (rapor anı) — kayıt defteri, elde bulunan, durum ve tür kırılımı."""
    durumlar = {
        satir["status"]: satir["adet"]
        for satir in Copy.objects.values("status").annotate(adet=Count("pk"))
    }
    elde = Copy.objects.exclude(status__in=TERMINAL_COPY_STATUSES).filter(
        work__deleted_at__isnull=True
    )
    turler = {
        satir["work__resource_type"]: satir["adet"]
        for satir in elde.values("work__resource_type").annotate(adet=Count("pk"))
    }
    bolumler: Counter[str] = Counter()
    for nusha_bolumu, eser_bolumu in elde.values_list("section__name", "work__section__name"):
        bolumler[nusha_bolumu or eser_bolumu or ""] += 1
    bolum_listesi = [
        {"section": ad, "copies": adet}
        for ad, adet in sorted(
            bolumler.items(), key=lambda s: (s[0] == "", keys.tr_collation_key(s[0]))
        )
    ]
    return {
        # Katalogdaki eserler (nüshasız dijital kaynak ve süreli yayın dahil) ve elde
        # nüshası bulunan eserler ayrı sorulardır.
        "catalog_work_count": Work.objects.count(),
        "work_count": Work.objects.filter(pk__in=elde.values("work_id")).count(),
        "register_count": Copy.objects.count(),
        "in_stock_count": elde.count(),
        "status_counts": {durum: durumlar.get(durum, 0) for durum in CopyStatus.values},
        "resource_type_counts": {tur: turler.get(tur, 0) for tur in ResourceType.values},
        "reference_count": elde.filter(is_reference=True).count(),
        "rare_count": elde.filter(is_rare_or_manuscript=True).count(),
        "sections": bolum_listesi,
    }


def _kazandirilanlar(bas: date, son: date) -> dict[str, Any]:
    """Dönemde kazandırılanlar — edinim yoluna göre nüsha sayısı (Kılavuz 2.3, 2.4).

    "Kazandırılan" toplamı ve eser sayısı YALNIZ Md. 10/5'in dört yolundandır
    (Bakanlık gönderimi, satın alma, bağış, değişim). Mevcut koleksiyonun programa
    aktarımı ve sayım fazlası kayıt içi giriştir, ayrı sayılır: programın ilk yılında
    binlerce kitabın aktarımı "yıl içinde kazandırılan" diye okul müdürlüğüne
    raporlanmasın.
    """
    donem_nushalari = Copy.objects.filter(
        acquisition__date__gte=bas,
        acquisition__date__lte=son,
    )
    yollar = {
        satir["acquisition__method"]: satir["adet"]
        for satir in donem_nushalari.values("acquisition__method").annotate(adet=Count("pk"))
    }
    kazandirilan = donem_nushalari.filter(acquisition__method__in=KAZANDIRMA_YOLLARI)
    bagislar = DonationIntake.objects.filter(
        status=DonationIntakeStatus.DECIDED,
        decided_at__gte=_anlar(bas, son)[0],
        decided_at__lt=_anlar(bas, son)[1],
    )
    kalemler = DonationIntakeItem.objects.filter(intake__in=bagislar)
    return {
        "copies_by_method": {yol: yollar.get(yol, 0) for yol in AcquisitionMethod.values},
        "total_copies": sum(yollar.get(yol, 0) for yol in KAZANDIRMA_YOLLARI),
        "works": kazandirilan.values("work_id").distinct().count(),
        "register_entry_copies": sum(yollar.get(yol, 0) for yol in KAYIT_ICI_YOLLAR),
        "donation_intakes_decided": bagislar.count(),
        "donation_items_accepted": kalemler.filter(decision=DonationItemDecision.ACCEPTED).count(),
        "donation_items_rejected": kalemler.filter(decision=DonationItemDecision.REJECTED).count(),
    }


def _ayiklanan(bas: date, son: date) -> dict[str, Any]:
    """Dönemde uygulanan ayıklama teklifleri — gerekçe ve TMY yoluna göre (E7)."""
    ilk, sonraki = _anlar(bas, son)
    uygulanan = WeedingItem.objects.filter(
        state=WeedingItemState.APPLIED,
        batch__status=WeedingBatchStatus.APPLIED,
        batch__deleted_at__isnull=True,
        batch__applied_at__gte=ilk,
        batch__applied_at__lt=sonraki,
    )
    gerekceler = {
        satir["reason"]: satir["adet"]
        for satir in uygulanan.values("reason").annotate(adet=Count("pk"))
    }
    yollar = {
        satir["tmy_path"]: satir["adet"]
        for satir in uygulanan.values("tmy_path").annotate(adet=Count("pk"))
    }
    dusulen = yollar.get(WeedingTmyPath.TMY_27, 0) + yollar.get(WeedingTmyPath.TMY_28, 0)
    devredilen = yollar.get(WeedingTmyPath.TMY_24_2, 0) + yollar.get(WeedingTmyPath.TMY_31, 0)
    return {
        "withdrawn": dusulen,
        "transferred": devredilen,
        "by_reason": {g: gerekceler.get(g, 0) for g in WeedingReason.values},
        "by_path": {y: yollar.get(y, 0) for y in WeedingTmyPath.values},
        "batches_applied": uygulanan.values("batch_id").distinct().count(),
    }


def _tespitler(bas: date, son: date) -> dict[str, Any]:
    """Tespitler: onarım, hasar ve kayıp sayıları (F7 verisi — Md. 12/1 "onarımı gerekli")."""
    ilk, sonraki = _anlar(bas, son)
    dosyalar = LossDamageCase.objects.filter(reported_on__gte=bas, reported_on__lte=son)
    cozulen = LossDamageCase.objects.filter(resolved_at__gte=ilk, resolved_at__lt=sonraki)
    cozumler = {
        satir["resolution"]: satir["adet"]
        for satir in cozulen.values("resolution").annotate(adet=Count("pk"))
    }
    return {
        "repairs_sent": CopyRepair.objects.filter(sent_on__gte=bas, sent_on__lte=son).count(),
        "repairs_returned": CopyRepair.objects.filter(
            returned_on__gte=bas, returned_on__lte=son
        ).count(),
        "in_repair_now": Copy.objects.filter(status=CopyStatus.IN_REPAIR).count(),
        "damage_cases": dosyalar.filter(case_type=CaseType.DAMAGED).count(),
        "loss_cases": dosyalar.filter(case_type=CaseType.LOST).count(),
        "resolutions": {
            c: cozumler.get(c, 0) for c in CaseResolution.values if c not in OPEN_CASE_RESOLUTIONS
        },
        "write_off_proposals": LossDamageCase.objects.filter(
            write_off_proposed_at__gte=ilk, write_off_proposed_at__lt=sonraki
        ).count(),
        "open_cases_now": LossDamageCase.objects.filter(
            resolution__in=OPEN_CASE_RESOLUTIONS
        ).count(),
        "lost_copies_now": Copy.objects.filter(status=CopyStatus.LOST).count(),
    }


def _uye_turu_ifadesi() -> dict[str, Q]:
    """Ödüncün üye türü — kişiden TÜRER (kişinin kendisi okunmaz)."""
    return {
        "STUDENT": Q(membership__student__isnull=False),
        "TEACHER": Q(
            membership__personnel__isnull=False,
            membership__personnel__member_kind=MemberKind.TEACHER,
        ),
        "STAFF": Q(membership__personnel__isnull=False)
        & ~Q(membership__personnel__member_kind=MemberKind.TEACHER),
    }


def _gizlenenler(
    farkli: Callable[[list[Q]], int],
    tur_q: dict[str, Q],
    duzey_q: dict[int, Q],
    belirsiz_q: Q,
    k: int,
) -> tuple[set[str], set[int]]:
    """Gizlenecek üye türü ve sınıf düzeyi hücreleri — birincil + TAMAMLAYICI gizleme.

    Basılan toplamlar iki eşitlik kurar: toplam = öğrenci + öğretmen + diğer
    personel; öğrenci = sınıf düzeylerinin toplamı + sınıf düzeyi kaydı olmayan
    öğrencilerin ödüncü (hiç basılmaz, hep "gizli" sayılır). Gizli hücrelerin
    bu eşitliklerden türetilebilen her toplamı ya hiç kimseye ait değildir ya da
    en az k farklı üyeye aittir:

    - öğrenci görünürse: gizli türler (öğretmen, diğer personel) birlikte ve gizli
      düzeyler (+ düzeysiz öğrenciler) birlikte,
    - öğrenci gizliyse: gizli türler + gizli düzeyler + düzeysiz öğrenciler birlikte.

    Eksik kalan eşitlik, farklı üyesi en az olan görünür hücre gizlenerek
    tamamlanır (hiçbir hücre iki kez sayılmaz; döngü her adımda bir hücre gizler).
    `farkli` koşulların birleşiminde ödünç alan FARKLI üye sayısını veritabanında
    sayar; üye kimliği Python'a gelmez.
    """
    tur_farkli = {t: farkli([q]) for t, q in tur_q.items()}
    duzey_farkli = {d: farkli([q]) for d, q in duzey_q.items()}
    gizli_tur = {t for t, n in tur_farkli.items() if n < k}
    gizli_duzey = {d for d, n in duzey_farkli.items() if n < k}

    def eksik(kosullar: list[Q]) -> bool:
        n = farkli(kosullar)
        return 0 < n < k

    def en_kucuk_tur(adaylar: list[str]) -> str:
        return min(adaylar, key=lambda t: (tur_farkli[t], UYE_TURLERI.index(t)))

    def en_kucuk_duzey(adaylar: list[int]) -> int:
        return min(adaylar, key=lambda d: (duzey_farkli[d], d))

    while True:
        gizli_duzey_q = [duzey_q[d] for d in sorted(gizli_duzey)] + [belirsiz_q]
        gorunen_duzey = [d for d in duzey_q if d not in gizli_duzey]
        if "STUDENT" not in gizli_tur:
            gizli_diger = [tur_q[t] for t in UYE_TURLERI if t in gizli_tur]
            if gizli_diger and eksik(gizli_diger):
                gorunen_diger = [t for t in UYE_TURLERI if t not in gizli_tur and t != "STUDENT"]
                gizli_tur.add(en_kucuk_tur(gorunen_diger) if gorunen_diger else "STUDENT")
                continue
            if eksik(gizli_duzey_q):
                if gorunen_duzey:
                    gizli_duzey.add(en_kucuk_duzey(gorunen_duzey))
                else:
                    gizli_tur.add("STUDENT")
                continue
            break
        birlikte = [tur_q[t] for t in UYE_TURLERI if t in gizli_tur and t != "STUDENT"]
        if eksik(birlikte + gizli_duzey_q):
            if gorunen_duzey:
                gizli_duzey.add(en_kucuk_duzey(gorunen_duzey))
                continue
            gorunen_tur = [t for t in UYE_TURLERI if t not in gizli_tur]
            if gorunen_tur:
                gizli_tur.add(en_kucuk_tur(gorunen_tur))
                continue
        break
    return gizli_tur, gizli_duzey


def _dolasim(bas: date, son: date, k: int) -> dict[str, Any]:
    """Kişisiz ödünç istatistiği (profil yasağı: toplamlar ve eşikli grup sayıları)."""
    ilk, sonraki = _anlar(bas, son)
    oduncler = Loan.objects.filter(loaned_at__gte=ilk, loaned_at__lt=sonraki)

    def farkli(kosullar: list[Q]) -> int:
        if not kosullar:
            return 0
        birlesim = Q()
        for kosul in kosullar:
            birlesim |= kosul
        return int(oduncler.filter(birlesim).values("membership_id").distinct().count())

    tur_q = _uye_turu_ifadesi()
    duzey_sayilari = {
        int(satir["membership__student__class_level"]): int(satir["adet"])
        for satir in oduncler.filter(
            membership__student__isnull=False,
            membership__student__class_level__isnull=False,
        )
        .values("membership__student__class_level")
        .annotate(adet=Count("pk"))
        .order_by("membership__student__class_level")
    }
    duzey_q = {d: Q(membership__student__class_level=d) for d in duzey_sayilari}
    belirsiz_q = Q(membership__student__isnull=False, membership__student__class_level__isnull=True)
    gizli_tur, gizli_duzey = _gizlenenler(farkli, tur_q, duzey_q, belirsiz_q, k)
    turler: dict[str, dict[str, Any]] = {
        tur: _esikli(oduncler.filter(kosul).count(), tur in gizli_tur)
        for tur, kosul in tur_q.items()
    }
    duzeyler: list[dict[str, Any]] = [
        {"class_level": d, **_esikli(adet, d in gizli_duzey)}
        for d, adet in sorted(duzey_sayilari.items())
    ]
    aylar: Counter[str] = Counter(
        timezone.localtime(an).strftime("%Y-%m")
        for an in oduncler.values_list("loaned_at", flat=True)
    )
    teslimler = Delivery.objects.filter(delivered_on__gte=bas, delivered_on__lte=son)
    return {
        "k_threshold": k,
        "loans": oduncler.count(),
        "returns": Loan.objects.filter(returned_at__gte=ilk, returned_at__lt=sonraki).count(),
        # Kişi bağı saklama süresi sonunda koparılmış ödünçler (F11) farklı üye sayısına
        # girmez; toplam ödünç sayısına girer.
        "distinct_borrowers": oduncler.filter(membership__isnull=False)
        .values("membership_id")
        .distinct()
        .count(),
        "by_member_type": turler,
        "by_class_level": duzeyler,
        "by_month": [{"month": ay, "loans": adet} for ay, adet in sorted(aylar.items())],
        "deliveries": {
            "section": teslimler.filter(recipient_kind=DeliveryRecipientKind.SECTION).count(),
            "teacher": teslimler.filter(recipient_kind=DeliveryRecipientKind.TEACHER).count(),
        },
        "active_members": _aktif_uyeler(k),
    }


def _aktif_uyeler(k: int) -> dict[str, int | None]:
    """Rapor anında aktif üyelik sayıları (üye türüne göre; kişisiz toplam).

    k'dan az (sıfır değil) üyesi olan türün sayısı gösterilmez (`None`): "tek
    öğretmen üye" bilgisi, toplamlardan geri bulunan bir sayıyı kişiye bağlardı.
    """
    aktif = Membership.objects.filter(status=MembershipStatus.ACTIVE)
    sayilar = {
        "STUDENT": aktif.filter(student__isnull=False).count(),
        "TEACHER": aktif.filter(personnel__member_kind=MemberKind.TEACHER).count(),
        "STAFF": aktif.filter(personnel__isnull=False)
        .exclude(personnel__member_kind=MemberKind.TEACHER)
        .count(),
    }
    return {tur: (None if 0 < n < k else n) for tur, n in sayilar.items()}


def annual_review_stats(school_year: SchoolYear, *, today: date | None = None) -> dict[str, Any]:
    """Yıl sonu kütüphane raporunun (E9) bütün sayıları — KİŞİSİZ, JSON'a yazılabilir."""
    bugun = today or timezone.localdate()
    bas, son = report_period(school_year, today=bugun)
    k = _esik()
    return {
        "schema": SCHEMA_VERSION,
        "generated_on": bugun.isoformat(),
        "school_year": {
            "label": school_year.name,
            "start_date": school_year.start_date.isoformat(),
            "end_date": school_year.end_date.isoformat(),
        },
        "period": {"start": bas.isoformat(), "end": son.isoformat()},
        "collection": _koleksiyon(),
        "acquisitions": _kazandirilanlar(bas, son),
        "weeding": _ayiklanan(bas, son),
        "findings": _tespitler(bas, son),
        "circulation": _dolasim(bas, son, k),
    }
