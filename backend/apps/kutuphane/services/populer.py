"""Çok okunanlar yazıcısı — iskelet (tasarım §5.3, T9; hesap F6/F10'da bağlanır).

`kd_katalog_populer` tablosu Ağ Kataloğu vitrininin "Çok Okunanlar" listesini
besler. Hesap Django tarafında, **gün değişimi kapısında günde bir kez**
yapılır. F5'te ödünç verisi henüz yoktur (`Loan` F6'da gelir); bu modül
tabloya yazma ve dondurma kurallarını ve kapıya bağlanacak günlük işi taşır.
Gerçek hesap (pencere içinde en az k FARKLI üye —
`LibraryPolicy.popular_min_members`, sayı hiçbir yerde gösterilmez) F10'da
`_siralama_hesapla` içine yazılır ve §5.10-12 ("tek üyenin tekrarlanan
ödünçleri bir eseri çok okunanlara sokmaz") o gün koşar.

Kurallar:

- **Sayı yazılmaz**, yalnız sıra (GA-10, KM-11, EK-23; profil yasağı).
- **Kapanmış pencere dondurulur** (`pencereyi_dondur`) ve bir daha yazılmaz:
  anonimleştirmeden sonra kişi bağı koparılmış ödünçlerle aynı eşik
  ölçülemez (`PencereDonduruldu`).
- **Ortak bakım kilidi** (§5.3 geri yükleme adım 4): yazıcı işe başlamadan
  bakım kapısından geçer (`katalog.bakim.KAPI`); geri yükleme sürerken iş
  başlamaz, başlamış iş bitene dek geri yükleme bekler. Veritabanı
  bağlantısı iş sonunda (`finally`) kapatılır.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

from django.db import connection, transaction

from apps.kutuphane.models import KatalogPopuler, PopulerPencereTuru, Work
from katalog.bakim import KAPI, BakimKapisi

logger = logging.getLogger("kutuphane_defteri.katalog")

#: Vitrinde gösterilen en çok eser sayısı (pencere başına yazılan sıra sınırı).
EN_COK_SIRA = 10


class PencereDonduruldu(RuntimeError):
    """Dondurulmuş (kapanmış) pencere yeniden yazılamaz."""


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


def _siralama_hesapla(bugun: date) -> list[tuple[str, str, list[int]]]:
    """(pencere türü, pencere, sıralı eser kimlikleri) listesi.

    F5: ödünç verisi yoktur, liste boştur. F10 bu işlevi doldurur (k farklı üye
    eşiği; §5.10-12).
    """
    return []


#: Gün değişimi kapısındaki kayıt adı (`masaustu_kanca.gunluk_is_kaydet`; ASCII).
GUNLUK_IS_ADI = "cok-okunanlar"


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
    işler (yedek, IP denetimi) durmamalıdır.
    """
    with kapi.is_() as izin:
        if not izin:
            return "bakimda"
        try:
            for pencere_turu, pencere, idler in _siralama_hesapla(bugun):
                pencereyi_yaz(pencere_turu, pencere, idler, hesaplanma=bugun)
            return "tamam"
        except Exception:  # noqa: BLE001 — günlük iş zinciri durmaz
            logger.exception("Çok okunanlar hesaplanamadı.")
            return "hata"
        finally:
            # Bu iş parçacığının bağlantısı bakım (geri yükleme) öncesi bırakılsın.
            # Açık bir işlem bloğunun içindeyse (çağıranın işlemi) dokunulmaz.
            if not connection.in_atomic_block:
                connection.close()
