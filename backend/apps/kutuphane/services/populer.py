"""Çok okunanlar yazıcısı — gün değişimi kapısının günlük işi (tasarım §5.3, T9; F10).

`kd_katalog_populer` tablosu Ağ Kataloğu vitrininin "Çok Okunanlar" listesini
(DÖNEM penceresi) ve "Ayın Kitapları" afişini (AY penceresi, E12) besler. Hesap
Django tarafında, **gün değişimi kapısında günde bir kez** yapılır
(`KutuphaneConfig.ready()` "cok-okunanlar" adıyla kaydeder); kütüphane
yöneticisi Raporlar'dan elle de yeniletebilir (`yeniden_hesapla`).

**Eşik: pencere içinde en az k FARKLI üye** (`COUNT(DISTINCT membership)`,
k = `LibraryPolicy.popular_min_members`, 3-10, varsayılan 5 — A12). Ödünç
KAYDI sayısı eşik değildir: tek üyenin aynı eseri tekrar tekrar alması o eseri
listeye sokmaz (§5.10-12, KM-11). Sıra, farklı üye sayısına göredir (eşitlikte
kaynak adının TR sırası); ödünç sayısı sıraya hiç girmez.

Kurallar:

- **Sayı yazılmaz**, yalnız sıra (GA-10, KM-11, EK-23; profil yasağı CLAUDE.md
  §2-5). Hesap kişi kimliğini Python'a getirmez: farklı üye sayısı veritabanında
  sayılır, dönen yalnız eser kimliğidir.
- **Pencereler.** Ay penceresi takvim ayıdır ('2026-09'). Dönem penceresi günü
  kapsayan ders dönemidir ('2026-2027/1'); ders yılının dönem tarihleri
  tanımlanmamışsa ders yılının tamamı tek penceredir ('2026-2027'). Anahtar ders
  yılının ADINDAN değil başlangıç ve bitiş YILLARINDAN kurulur (ad serbest
  metindir; `pencere` alanı 20 karakterdir).
- **Kapanan pencere bir kez son kez hesaplanır ve dondurulur.** Kapıdaki iş günün
  başında koşar: bir pencerenin son gününde, iş koştuktan sonra verilen ödünçler
  o gün yazılmamıştır. Pencere kapandıktan sonraki ilk çalışmada son kez
  hesaplanır ve dondurulur (`pencereyi_dondur`). Bu son hesap yalnız pencere
  kapanalı `SON_HESAP_GUN` günden az olmuşsa yapılır: kişi bağının koparılması
  (anonimleştirme, §6.4 — en erken ders yılı sonu + 1 yıl) bundan çok sonradır,
  yani **anonimleştirmeden sonra yeniden hesaplanmaz** (koparılmış ödünçlerle aynı
  eşik ölçülemez). Daha eski, dondurulmamış satırlar hesaplanmadan dondurulur.
  Dondurulmuş pencere bir daha yazılmaz (`PencereDonduruldu`).
- **Ortak bakım kilidi** (§5.3 geri yükleme adım 4): kapıdaki iş bakım kapısından
  geçer (`katalog.bakim.KAPI`); geri yükleme sürerken iş başlamaz, başlamış iş
  bitene dek geri yükleme bekler. Kapı işinin veritabanı bağlantısı iş sonunda
  (`finally`) kapatılır.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

from django.db import connection, transaction
from django.db.models import Count, Q, QuerySet

from apps.kutuphane.models import (
    KatalogPopuler,
    LibraryPolicy,
    Loan,
    PopulerPencereTuru,
    Work,
)
from apps.kutuphane.selectors_yil_raporu import _anlar
from apps.okul.models import SchoolTerm, SchoolYear
from katalog.bakim import KAPI, BakimKapisi

logger = logging.getLogger("kutuphane_defteri.katalog")

#: Vitrinde ve afişte gösterilen en çok eser sayısı (pencere başına yazılan sıra sınırı).
EN_COK_SIRA: Final = 10

#: Kapanan pencerenin son hesabının yapılabileceği en uzun süre (gün). Kişi bağının
#: koparılması (§6.4, A3) en erken ders yılı sonu + 1 yıldır; bu süre ondan çok kısadır.
#: Yaz tatilinde program aylarca açılmasa da 2. dönemin listesi, son açılışta yazılmış
#: hâliyle dondurulur.
SON_HESAP_GUN: Final = 60

#: Gün değişimi kapısındaki kayıt adı (`masaustu_kanca.gunluk_is_kaydet`; ASCII).
GUNLUK_IS_ADI: Final = "cok-okunanlar"


class PencereDonduruldu(RuntimeError):
    """Dondurulmuş (kapanmış) pencere yeniden yazılamaz."""


# ---------------------------------------------------------------------------
# Tabloya yazma ve dondurma
# ---------------------------------------------------------------------------
def pencereyi_yaz(
    pencere_turu: str,
    pencere: str,
    eser_idleri: Sequence[int],
    *,
    hesaplanma: date,
) -> int:
    """Pencerenin sırasını YENİDEN yazar (açık pencerede); yazılan satır sayısı.

    `eser_idleri` sıralıdır ve eşiği geçmiş eserlerdir (eşik hesaplayanın
    işidir). Tekrarlanan eser ilk yerinde kalır; en çok `EN_COK_SIRA` eser.
    """
    if pencere_turu not in PopulerPencereTuru.values:
        raise ValueError(f"Bilinmeyen pencere türü: {pencere_turu}")
    idler = list(dict.fromkeys(int(i) for i in eser_idleri))[:EN_COK_SIRA]
    with transaction.atomic():
        mevcut = KatalogPopuler.objects.filter(pencere_turu=pencere_turu, pencere=pencere)
        if mevcut.filter(dondu=True).exists():
            raise PencereDonduruldu(f"{pencere} penceresi donduruldu; yeniden hesaplanmaz.")
        mevcut.delete()
        gecerli = set(Work.objects.filter(pk__in=idler).values_list("pk", flat=True))
        satirlar = [
            KatalogPopuler(
                eser_id=eser_id,
                pencere_turu=pencere_turu,
                pencere=pencere,
                sira=sira,
                hesaplanma=hesaplanma,
            )
            for sira, eser_id in enumerate((i for i in idler if i in gecerli), start=1)
        ]
        KatalogPopuler.objects.bulk_create(satirlar)
    return len(satirlar)


def pencereyi_dondur(pencere_turu: str, pencere: str) -> int:
    """Kapanmış pencereyi dondurur; dondurulan satır sayısı."""
    return KatalogPopuler.objects.filter(
        pencere_turu=pencere_turu, pencere=pencere, dondu=False
    ).update(dondu=True)


def pencere_donmus_mu(pencere_turu: str, pencere: str) -> bool:
    return KatalogPopuler.objects.filter(
        pencere_turu=pencere_turu, pencere=pencere, dondu=True
    ).exists()


# ---------------------------------------------------------------------------
# Pencereler
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pencere:
    """Bir çok okunanlar penceresi: tür, anahtar ve kapsadığı günler (ikisi de dahil)."""

    tur: str
    anahtar: str
    bas: date
    son: date


def ay_anahtari(gun: date) -> str:
    return f"{gun:%Y-%m}"


def ay_penceresi(gun: date) -> Pencere:
    """Günü kapsayan takvim ayı ('2026-09')."""
    bas = gun.replace(day=1)
    sonraki = (bas + timedelta(days=32)).replace(day=1)
    return Pencere(PopulerPencereTuru.AY, ay_anahtari(bas), bas, sonraki - timedelta(days=1))


def onceki_ay_penceresi(gun: date) -> Pencere:
    return ay_penceresi(gun.replace(day=1) - timedelta(days=1))


def _yil_etiketi(yil: SchoolYear) -> str:
    return f"{yil.start_date.year}-{yil.end_date.year}"


def _donem(term: SchoolTerm) -> Pencere:
    return Pencere(
        PopulerPencereTuru.DONEM,
        f"{_yil_etiketi(term.school_year)}/{term.sequence}",
        term.start_date,
        term.end_date,
    )


def _yil_donemi(yil: SchoolYear) -> Pencere:
    """Dönem tarihleri tanımlanmamış ders yılı: yılın tamamı tek pencere."""
    return Pencere(PopulerPencereTuru.DONEM, _yil_etiketi(yil), yil.start_date, yil.end_date)


def _canli_donemler() -> QuerySet[SchoolTerm]:
    return SchoolTerm.objects.filter(school_year__deleted_at__isnull=True).select_related(
        "school_year"
    )


def _donemsiz_yillar() -> QuerySet[SchoolYear]:
    return SchoolYear.objects.exclude(pk__in=SchoolTerm.objects.values("school_year_id"))


def donem_penceresi(gun: date) -> Pencere | None:
    """Günü kapsayan ders dönemi; dönemsiz ders yılında yılın tamamı; yoksa `None`."""
    term = (
        _canli_donemler()
        .filter(start_date__lte=gun, end_date__gte=gun)
        .order_by("-start_date", "-pk")
        .first()
    )
    if term is not None:
        return _donem(term)
    yil = (
        _donemsiz_yillar()
        .filter(start_date__lte=gun, end_date__gte=gun)
        .order_by("-start_date", "-pk")
        .first()
    )
    return _yil_donemi(yil) if yil is not None else None


def onceki_donem_penceresi(gun: date) -> Pencere | None:
    """Günden önce biten en son dönem (ya da dönemsiz ders yılı)."""
    adaylar: list[Pencere] = []
    term = _canli_donemler().filter(end_date__lt=gun).order_by("-end_date", "-pk").first()
    if term is not None:
        adaylar.append(_donem(term))
    yil = _donemsiz_yillar().filter(end_date__lt=gun).order_by("-end_date", "-pk").first()
    if yil is not None:
        adaylar.append(_yil_donemi(yil))
    return max(adaylar, key=lambda p: p.son) if adaylar else None


# ---------------------------------------------------------------------------
# Hesap
# ---------------------------------------------------------------------------
def esik() -> int:
    """k — pencerede bir eseri ödünç almış olması gereken en az FARKLI üye sayısı."""
    return int(LibraryPolicy.load().popular_min_members)


def eser_siralamasi(bas: date, son: date, *, k: int) -> list[int]:
    """Pencerede en az k FARKLI üyenin ödünç aldığı eserler, farklı üye sayısına göre sıralı.

    Kişisizdir: farklı üye sayısı veritabanında sayılır (`Count(distinct=True)`),
    Python'a yalnız eser kimliği gelir. Kişi bağı koparılmış (`membership` boş)
    ödünç farklı üye sayısına girmez. Silinmiş eser listelenmez. Eşitlikte kaynak
    adının Türkçe sırası (`sort_key`), sonra kimlik — sıra her gün aynı çıkar.
    """
    ilk, sonraki = _anlar(bas, son)
    satirlar = (
        Loan.objects.filter(
            loaned_at__gte=ilk,
            loaned_at__lt=sonraki,
            membership__isnull=False,
            copy__work__deleted_at__isnull=True,
        )
        .values("copy__work_id")
        .annotate(farkli=Count("membership_id", distinct=True))
        .filter(farkli__gte=k)
        .order_by("-farkli", "copy__work__sort_key", "copy__work_id")
    )[:EN_COK_SIRA]
    return [int(satir["copy__work_id"]) for satir in satirlar]


@dataclass(frozen=True)
class PencereSonucu:
    """Bir pencerenin hesaplanmış sırası; `kapanis` = kapanan pencerenin son hesabı."""

    pencere: Pencere
    eser_idleri: tuple[int, ...]
    kapanis: bool


def _siralama_hesapla(bugun: date) -> list[PencereSonucu]:
    """Bugün yazılacak pencereler: kapanan pencerelerin son hesabı + açık pencereler.

    Dondurulmuş pencere listeye girmez. Kapanan pencere yalnız `SON_HESAP_GUN`
    içinde son kez hesaplanır (modül belgesi).
    """
    k = esik()
    sonuc: list[PencereSonucu] = []
    for kapanan in (onceki_ay_penceresi(bugun), onceki_donem_penceresi(bugun)):
        if kapanan is None or (bugun - kapanan.son).days > SON_HESAP_GUN:
            continue
        if pencere_donmus_mu(kapanan.tur, kapanan.anahtar):
            continue
        idler = eser_siralamasi(kapanan.bas, kapanan.son, k=k)
        sonuc.append(PencereSonucu(kapanan, tuple(idler), kapanis=True))
    for acik in (ay_penceresi(bugun), donem_penceresi(bugun)):
        if acik is None or pencere_donmus_mu(acik.tur, acik.anahtar):
            continue
        idler = eser_siralamasi(acik.bas, min(acik.son, bugun), k=k)
        sonuc.append(PencereSonucu(acik, tuple(idler), kapanis=False))
    return sonuc


def hesapla(bugun: date) -> dict[str, Any]:
    """Pencereleri yazar, kapananları dondurur; kişisiz özet döndürür.

    Özet yalnız pencere adlarını ve kaç eserin sıraya girdiğini taşır (eser
    kimliği, ödünç ya da üye sayısı YOKTUR).
    """
    with transaction.atomic():
        sonuclar = _siralama_hesapla(bugun)
        ozet: list[dict[str, Any]] = []
        for s in sonuclar:
            yazilan = pencereyi_yaz(
                s.pencere.tur, s.pencere.anahtar, s.eser_idleri, hesaplanma=bugun
            )
            if s.kapanis:
                pencereyi_dondur(s.pencere.tur, s.pencere.anahtar)
            ozet.append(
                {
                    "window_type": s.pencere.tur,
                    "window": s.pencere.anahtar,
                    "ranked": yazilan,
                    "final": s.kapanis,
                }
            )
        # Açık pencereler dışındaki her dondurulmamış satır kapanmış bir pencereye aittir
        # (son hesap süresi geçmiş ya da pencere tanımı değişmiş): yeniden hesaplanmadan
        # dondurulur.
        acik = Q(pk__in=[])
        for s in sonuclar:
            if not s.kapanis:
                acik |= Q(pencere_turu=s.pencere.tur, pencere=s.pencere.anahtar)
        KatalogPopuler.objects.filter(dondu=False).exclude(acik).update(dondu=True)
    return {"computed_on": bugun.isoformat(), "k_threshold": esik(), "windows": ozet}


class BakimSuruyor(RuntimeError):
    """Geri yükleme sürüyor: çok okunanlar şimdi hesaplanamaz."""


def yeniden_hesapla(bugun: date, *, kapi: BakimKapisi = KAPI) -> dict[str, Any]:
    """Raporlar'daki "Yeniden hesapla": kapıdaki işle AYNI hesap, aynı bakım kapısından.

    İstek iş parçacığında koşar; bağlantıyı kapatmaz (isteğin işidir).
    """
    with kapi.is_() as izin:
        if not izin:
            raise BakimSuruyor("Geri yükleme sürüyor; çok okunanlar şimdi hesaplanamaz.")
        return hesapla(bugun)


def kapi_isi() -> bool:
    """Kapının çağırdığı biçim: yerel günle `gunluk_is`; yalnız "tamam" günü kapatır.

    "bakimda" (geri yükleme sürüyor) ve "hata" `False` döner: kapı işi bir saat
    sonra yeniden dener, damga yazılmaz.
    """
    from django.utils import timezone

    return gunluk_is(timezone.localdate()) == "tamam"


def gunluk_is(bugun: date, *, kapi: BakimKapisi = KAPI) -> str:
    """Gün değişimi kapısının çağırdığı iş: "tamam", "bakimda" ya da "hata".

    Kapıya `KutuphaneConfig.ready()` kaydeder (`masaustu_kanca.gunluk_is_kaydet`,
    `kapi_isi` biçimiyle); iş kendi hatasını yutar ve günlüğe yazar — öbür günlük
    işler (yedek, IP denetimi) durmamalıdır. Günlüğe kişi ya da eser bilgisi
    yazılmaz.
    """
    with kapi.is_() as izin:
        if not izin:
            return "bakimda"
        try:
            hesapla(bugun)
            return "tamam"
        except Exception:  # noqa: BLE001 — günlük iş zinciri durmaz
            logger.exception("Çok okunanlar hesaplanamadı.")
            return "hata"
        finally:
            # Bu iş parçacığının bağlantısı bakım (geri yükleme) öncesi bırakılsın.
            # Açık bir işlem bloğunun içindeyse (çağıranın işlemi) dokunulmaz.
            if not connection.in_atomic_block:
                connection.close()
