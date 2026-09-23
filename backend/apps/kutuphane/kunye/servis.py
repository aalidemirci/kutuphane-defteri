"""Künye getirmenin karar katmanı — ayar, sıra, önbellek, hız ve fail-open.

Kapının §8.5'teki dört değişmezi burada uygulanır:

1. **Ayar kapalıysa kod hiç ağa çıkmaz.** Adaptör çağrısına gelinmeden
   `KunyeKapaliHatasi` yükselir (koruma testi adaptörleri "çağrılırsa düş"
   diye kurar).
2. **Yalnız kullanıcının başlattığı istek.** Sorgu `kullanici_istegi()`
   bağlamı DIŞINDA çağrılırsa reddedilir; toplu içe aktarma yolu bu bağlamı
   hiç açmaz, yani "toplu içe aktarımda ASLA istek atılmaz" kuralı koda
   gömülüdür, gözetime bırakılmaz (§8.5-2, §5.10-19a).
3. **Önce Bakanlık, bulunamazsa Open Library** (U13). Her kaynak ayrıca
   açılıp kapanabilir: MEBNET'te 210 portu engelliyse okul o kaynağı kapatır
   ve program boşuna beklemez.
4. **Fail-open** (§8.5-9): uç ölürse, yavaşsa, engelliyse ya da bozuk gövde
   dönerse kullanıcıya hata değil "İnternetten getirilemedi, elle
   girebilirsiniz" iletisi gider; elle giriş tam işlevlidir.

**Bu katman `Work` satırına YAZMAZ** (§8.5-5). Öneri üretir; yazma kullanıcının
kendi `library/works/` isteğiyle olur. Koruma testi eserlerin sorgu öncesi ve
sonrası birebir aynı kaldığını kanıtlar.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from types import ModuleType

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane.kunye import bakanlik, onbellek, openlibrary
from apps.kutuphane.kunye.istemci import KunyeAgHatasi
from apps.kutuphane.kunye.marc import MarcHatasi
from apps.kutuphane.kunye.oneri import KunyeOnerisi
from apps.kutuphane.models import LibraryPolicy, MetadataLookupSource

logger = logging.getLogger(__name__)

#: Önerinin yanında duran rozet (docs/sozluk.md — konum dili, §8.5-10).
ROZET = "Dış kaynaktan alındı, doğrulayın"

#: Fail-open iletisi (§8.5-9). Kullanıcıya hata gösterilmez, yol gösterilir.
ILETI_BULUNAMADI = "İnternetten getirilemedi, elle girebilirsiniz."
ILETI_KAPALI = (
    "“ISBN ile künye getirme” kapalıdır. "
    "Ayarlar → Kütüphane Politikası → Künye Getirme bölümünden açabilirsiniz."
)
ILETI_GECERSIZ_ISBN = "Künye getirmek için 10 ya da 13 haneli bir ISBN yazın."
#: Ana anahtar açık ama iki kaynak da kapalı. Fail-open iletisiyle AYNI olmamalı:
#: sebep internet değil, okulun kendi ayarıdır; kullanıcı ağı ya da BTR'yi
#: suçlamasın diye ayrı söylenir.
ILETI_KAYNAK_YOK = (
    "Hiçbir künye kaynağı seçili değil. "
    "Ayarlar → Kütüphane Politikası → Künye Getirme bölümünden en az birini seçin."
)

#: Kaynak sırası (U13): önce Bakanlık kataloğu, bulunamazsa Open Library.
#: Modül TUTULUR, işlev değil: testler `bakanlik.sorgula`yı yerine koyabilsin.
KAYNAKLAR: tuple[tuple[str, str, ModuleType], ...] = (
    (MetadataLookupSource.MINISTRY, "metadata_lookup_ministry", bakanlik),
    (MetadataLookupSource.OPENLIBRARY, "metadata_lookup_openlibrary", openlibrary),
)

_baglam = threading.local()


class KunyeKapaliHatasi(RuntimeError):
    """Künye getirme ayarı kapalı (§8.5-1). Uç bunu 409 `kunye_kapali`ya çevirir."""


class GecersizIsbnHatasi(ValueError):
    """Sorulan numara ISBN'e benzemiyor; dışarı hiçbir istek çıkmaz."""


class KullaniciIstegiGerekli(RuntimeError):
    """Sorgu `kullanici_istegi()` bağlamı dışında çağrıldı (toplu iş yasağı, §8.5-2)."""


@dataclass(frozen=True, slots=True)
class KunyeSonucu:
    """Kullanıcıya gösterilecek sonuç: öneri + kaynak kimliği + fail-open iletisi."""

    isbn13: str
    bulundu: bool
    kaynak: str
    kaynak_adi: str
    kaynak_tarihi: date | None
    kayit_sayisi: int
    onbellekten: bool
    oneri: KunyeOnerisi | None
    ileti: str

    @property
    def kaynak_etiketi(self) -> str:
        """Her alanın yanında duran kaynak ve tarih etiketi (§8.5-5).

        Biçim kullanıcı sözlüğündedir: "Bakanlık kataloğu, 23.09.2026". Tarih
        ön yüzde değil BURADA biçimlenir (CLAUDE.md §2-9: ön yüzde
        `toISOString().slice(0,10)` yasak; hazır etiket o tuzağı hiç doğurmaz).
        """
        if not self.bulundu or self.kaynak_tarihi is None:
            return ""
        return f"{self.kaynak_adi}, {self.kaynak_tarihi.strftime('%d.%m.%Y')}"


def kaynak_adi(kaynak: str) -> str:
    """Kaynak kodunun kullanıcıya görünen adı ('Bakanlık kataloğu')."""
    if not kaynak:
        return ""
    return str(MetadataLookupSource(kaynak).label)


@contextmanager
def kullanici_istegi() -> Iterator[None]:
    """Dış sorguya izin veren bağlam — YALNIZ kullanıcının başlattığı uç açar.

    Toplu içe aktarma, açılış zinciri, gün değişimi kapısı ve arka plan işleri
    bu bağlamı açmaz; açmadıkları için `kunye_getir` onlara dış istek attırmaz.
    """
    onceki = getattr(_baglam, "acik", False)
    _baglam.acik = True
    try:
        yield
    finally:
        _baglam.acik = onceki


def kullanici_istegi_mi() -> bool:
    return bool(getattr(_baglam, "acik", False))


def ayar_acik_mi(policy: LibraryPolicy | None = None) -> bool:
    """Künye getirme açık mı? (varsayılan KAPALI — §8.5-1)"""
    kayit = policy if policy is not None else LibraryPolicy.load()
    return bool(kayit.metadata_lookup_enabled)


def acik_kaynaklar(policy: LibraryPolicy) -> list[tuple[str, ModuleType]]:
    """Ayarda açık olan kaynaklar, §8.5'teki sırayla."""
    return [
        (kaynak, modul) for kaynak, ayar, modul in KAYNAKLAR if bool(getattr(policy, ayar, False))
    ]


def _sonuc_bulunamadi(isbn13: str, *, ileti: str = ILETI_BULUNAMADI) -> KunyeSonucu:
    return KunyeSonucu(
        isbn13=isbn13,
        bulundu=False,
        kaynak="",
        kaynak_adi="",
        kaynak_tarihi=None,
        kayit_sayisi=0,
        onbellekten=False,
        oneri=None,
        ileti=ileti,
    )


def _onbellekten(kayit: onbellek.OnbellekKaydi) -> KunyeSonucu:
    bulundu = kayit.oneri is not None
    return KunyeSonucu(
        isbn13=kayit.isbn13,
        bulundu=bulundu,
        kaynak=kayit.kaynak if bulundu else "",
        kaynak_adi=kaynak_adi(kayit.kaynak) if bulundu else "",
        kaynak_tarihi=kayit.tarih if bulundu else None,
        kayit_sayisi=kayit.kayit_sayisi,
        onbellekten=True,
        oneri=kayit.oneri,
        ileti="" if bulundu else ILETI_BULUNAMADI,
    )


def kunye_getir(ham_isbn: object, *, force: bool = False) -> KunyeSonucu:
    """ISBN'den künye önerisi getirir (tek istek, kullanıcının eylemiyle).

    Sıra: ayar → ISBN normalleştirme → önbellek → açık kaynaklar (§8.5 sırası).
    Hiçbir dalda `Work` yazılmaz.
    """
    if not kullanici_istegi_mi():
        raise KullaniciIstegiGerekli(
            "Künye sorgusu yalnız kullanıcının başlattığı uçtan yapılır (§8.5-2)."
        )
    policy = LibraryPolicy.load()
    if not ayar_acik_mi(policy):
        raise KunyeKapaliHatasi(ILETI_KAPALI)

    isbn13 = isbn_module.to_isbn13(ham_isbn)
    if not isbn13:
        raise GecersizIsbnHatasi(ILETI_GECERSIZ_ISBN)

    if not force:
        kayit = onbellek.oku(isbn13)
        if kayit is not None:
            return _onbellekten(kayit)

    kaynaklar = acik_kaynaklar(policy)
    if not kaynaklar:
        # Ayar açık ama iki kaynak da kapalı: sebep ağ DEĞİL, okulun ayarıdır.
        # Önbelleğe de yazılmaz — hiçbir kaynağa sorulmadı.
        return _sonuc_bulunamadi(isbn13, ileti=ILETI_KAYNAK_YOK)
    # Kaynak "bu numara bende yok" mu dedi, yoksa hiç konuşamadı mı? İkisi ayrı
    # şeydir: konuşamayan bir kaynağın ardından "bulunamadı" önbelleğe yazılsa,
    # ağ geri geldiğinde kullanıcı aynı numarayı bir daha hiç soramazdı.
    hata_oldu = False
    for kaynak, modul in kaynaklar:
        sorgula: Callable[..., tuple[KunyeOnerisi | None, int]] = modul.sorgula
        try:
            oneri, kayit_sayisi = sorgula(isbn13)
        except (KunyeAgHatasi, MarcHatasi) as exc:
            # Fail-open: kaynak ölü, yavaş ya da engelli. Günlüğe İLETİ yazılır,
            # sınıf adı değil: MEBNET'te beklenen sebepler (proxy 407, SSL
            # denetimi, kapalı port, HTTP 500 — tasarım §8.5, S15) tek sınıf
            # altında toplanır ve "proxy mi, sertifika mı" sorusunu ayıracak iz
            # kalmazdı. İstemcinin ürettiği iletilerin hiçbiri ISBN TAŞIMAZ
            # (hepsi sabit metindir; `istemci.getir`), yani KVKK kısıtı bu
            # bilgiyi kısmayı gerektirmiyor.
            logger.warning("Künye kaynağı yanıt vermedi (%s): %s", kaynak, exc)
            hata_oldu = True
            continue
        except Exception:  # noqa: BLE001 — dış gövde güvenilmez; program aksamaz
            logger.exception("Künye kaynağında beklenmeyen hata (%s)", kaynak)
            hata_oldu = True
            continue
        if oneri is None or oneri.bos_mu:
            continue
        yazilan = onbellek.yaz(isbn13, kaynak=kaynak, oneri=oneri, kayit_sayisi=kayit_sayisi)
        return KunyeSonucu(
            isbn13=isbn13,
            bulundu=True,
            kaynak=kaynak,
            kaynak_adi=kaynak_adi(kaynak),
            kaynak_tarihi=yazilan.tarih,
            kayit_sayisi=yazilan.kayit_sayisi,
            onbellekten=False,
            oneri=oneri,
            ileti="",
        )

    # Hiçbir kaynakta bulunamadı. Kaynaklar konuşabildiyse numara önbelleğe
    # "bulunamadı" diye yazılır; konuşamadılarsa yazılmaz (yukarıdaki not).
    if not hata_oldu:
        onbellek.yaz(isbn13, kaynak="", oneri=None, kayit_sayisi=0)
    return _sonuc_bulunamadi(isbn13)
