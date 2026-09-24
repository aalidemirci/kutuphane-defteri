"""Ağ Kataloğu ayarı — tek satırın okunması ve yazılması (tasarım §5.2, §5.7, §6.2).

`KatalogAyari` port ve IP'nin TEK KAYNAĞIDIR. Bu modülün dışa verdiği arayüz
(masaüstü kolu ve ayar ekranı buna güvenir):

- `katalog_ayari()` — satırı döndürür; yoksa KAYDEDİLMEMİŞ varsayılan (okuma
  yazmaz). Varsayılan: kapalı, port 8765, bütün ağ bağlantılarında dinler.
- `update_katalog_ayari(**alanlar)` — gönderilen alanları doğrulayıp yazar;
  gönderilmeyen alana DOKUNULMAZ (ayar ekranının bir bölümünden yapılan
  kayıt öbürünü sıfırlamasın). `kutuphane_saatleri` de bu yoldan yazılır ama
  `SchoolConfig`'te durur (§6.1). **Yalnız yönetici kipinde** çalışır
  (`AyarYetkisiz`); program kendi yazıyorsa (ör. gün değişimi kapısı) çağıran
  `sistem_yazimi=True` verir.
- `ayar_degisince(dinleyici)` — yazma kalıcılaştıktan SONRA (`on_commit`)
  çağrılacak işlevi kaydeder; masaüstünün katalog kontrol kanalı (T16)
  açılışta kaydolur ve dinleyiciyi yeni ayarla yeniden kurar. Dönen işlev
  kaydı siler.

Doğrulama kuralları (Türkçe iletili `ValidationError`, alan adıyla):

- port 1024-65535 (1024 altı ayrıcalıklı portlardır);
- "yalnız seçili IP adresinde" kipinde seçili IP zorunludur; IP IPv4'tür,
  geri döngü (127/8), bağlantı yerel (169.254/16), çok yönlü ve belirsiz
  adres olamaz (§5.6 aday kuralı);
- tahta ağı blokları özel (RFC1918) IPv4 bloklarıdır ve en geniş /16'dır:
  RFC1918'in tamamı açılmaz, MEB WAN'ındaki başka kurum adresleri de özel
  aralıktadır (§5.7, GA-6). En çok 16 blok; tekrarlar ayıklanır.
"""

from __future__ import annotations

import ipaddress
import logging
import threading
from collections.abc import Callable
from typing import Any, Final

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.kutuphane.models import (
    KATALOG_PORT_ALT,
    KATALOG_PORT_UST,
    DinlemeKipi,
    KatalogAyari,
)
from apps.okul.models import SchoolConfig

logger = logging.getLogger("kutuphane_defteri.katalog")

#: Serbestçe yazılabilen alanlar (model alanları). `kutuphane_saatleri` ayrıca.
AYAR_ALANLARI: Final[tuple[str, ...]] = (
    "acik",
    "port",
    "dinleme_kipi",
    "secili_ip",
    "son_afis_ip",
    "uyku_engelleme",
    "vitrin_acik",
    "konular_acik",
    "tahta_cidrleri",
)
SAATLER_ALANI: Final = "kutuphane_saatleri"
EN_COK_SAATLER: Final = 500
EN_COK_TAHTA_BLOGU: Final = 16
#: Kabul edilen en geniş tahta ağı bloğu (önek uzunluğu).
EN_GENIS_ONEK: Final = 16

AYAR_YETKISIZ_ILETISI: Final = "Ağ Kataloğu ayarları yalnız yönetici kipinde değiştirilir."

Dinleyici = Callable[[KatalogAyari], None]
_dinleyiciler: list[Dinleyici] = []
_dinleyici_kilidi = threading.Lock()


class AyarYetkisiz(PermissionError):
    """Yönetici kipi dışında ayar yazma girişimi (uç 403 `kip_yetkisiz` döner)."""


def katalog_ayari() -> KatalogAyari:
    """Ayar satırı; yoksa kaydedilmemiş varsayılan (okuma yazmaz)."""
    return KatalogAyari.load()


def kutuphane_saatleri() -> str:
    return SchoolConfig.load().kutuphane_saatleri


def ayar_degisince(dinleyici: Dinleyici) -> Callable[[], None]:
    """Ayar yazıldıktan sonra çağrılacak dinleyiciyi kaydeder; kaydı silen işlevi döndürür."""
    with _dinleyici_kilidi:
        _dinleyiciler.append(dinleyici)

    def sil() -> None:
        with _dinleyici_kilidi:
            if dinleyici in _dinleyiciler:
                _dinleyiciler.remove(dinleyici)

    return sil


def _dinleyicileri_cagir(ayar: KatalogAyari) -> None:
    with _dinleyici_kilidi:
        kopyalar = list(_dinleyiciler)
    for dinleyici in kopyalar:
        try:
            dinleyici(ayar)
        except Exception:  # noqa: BLE001 — bir dinleyicinin hatası kaydı geri almaz
            logger.exception("Ağ Kataloğu ayar dinleyicisi hata verdi (ayar kaydedildi).")


def _yonetici_kipi_mi() -> bool:
    from apps.okul.kip import KIP, YONETICI

    return KIP.durum() == YONETICI


def _ipv4(deger: object, *, alan: str) -> str:
    metin = str(deger or "").strip()
    if not metin:
        return ""
    try:
        adres = ipaddress.IPv4Address(metin)
    except ValueError as exc:
        raise ValidationError({alan: "Geçerli bir IPv4 adresi yazın (ör. dört sayı)."}) from exc
    if adres.is_loopback or adres.is_link_local or adres.is_multicast or adres.is_unspecified:
        raise ValidationError(
            {alan: "Bu adres okul ağındaki bir bağlantıya ait değil; başka bir adres seçin."}
        )
    return str(adres)


def tahta_bloklarini_dogrula(deger: object) -> list[str]:
    """Tahta ağı bloklarını doğrular ve normalleştirir (tekrarsız, girildiği sırada)."""
    if deger in (None, ""):
        return []
    if not isinstance(deger, list | tuple):
        raise ValidationError({"tahta_cidrleri": "Tahta ağı blokları bir liste olmalıdır."})
    if len(deger) > EN_COK_TAHTA_BLOGU:
        raise ValidationError(
            {"tahta_cidrleri": f"En çok {EN_COK_TAHTA_BLOGU} tahta ağı bloğu girilebilir."}
        )
    sonuc: list[str] = []
    for kalem in deger:
        metin = str(kalem or "").strip()
        try:
            ag = ipaddress.IPv4Network(metin, strict=True)
        except ValueError as exc:
            raise ValidationError(
                {"tahta_cidrleri": f"“{metin}” geçerli bir ağ bloğu değil (ör. adres/24)."}
            ) from exc
        if not ag.is_private or ag.is_loopback or ag.is_link_local:
            raise ValidationError(
                {"tahta_cidrleri": f"“{metin}” okul içi (özel) bir ağ bloğu değil."}
            )
        if ag.prefixlen < EN_GENIS_ONEK:
            raise ValidationError(
                {
                    "tahta_cidrleri": (
                        f"“{metin}” çok geniş: özel adres aralığının tamamı açılmaz. "
                        "BTR'nin doğruladığı tahta ağı bloğunu yazın."
                    )
                }
            )
        normal = str(ag)
        if normal not in sonuc:
            sonuc.append(normal)
    return sonuc


def _dogrula(ayar: KatalogAyari) -> None:
    hatalar: dict[str, str] = {}
    if not KATALOG_PORT_ALT <= int(ayar.port) <= KATALOG_PORT_UST:
        hatalar["port"] = f"Port {KATALOG_PORT_ALT} ile {KATALOG_PORT_UST} arasında olmalıdır."
    if ayar.dinleme_kipi not in DinlemeKipi.values:
        hatalar["dinleme_kipi"] = "Dinleme kipi tanınmadı."
    elif ayar.dinleme_kipi == DinlemeKipi.SELECTED and not ayar.secili_ip:
        hatalar["secili_ip"] = "“Yalnız seçili IP adresinde” kipinde bir IP adresi seçin."
    if hatalar:
        raise ValidationError(hatalar)


def update_katalog_ayari(*, sistem_yazimi: bool = False, **alanlar: Any) -> KatalogAyari:
    """Ayarı günceller (satır yoksa varsayılanlarla açar); modül belgesindeki kurallar."""
    if not sistem_yazimi and not _yonetici_kipi_mi():
        raise AyarYetkisiz(AYAR_YETKISIZ_ILETISI)
    bilinmeyen = set(alanlar) - {*AYAR_ALANLARI, SAATLER_ALANI}
    if bilinmeyen:
        raise ValidationError({ad: "Bu ayar tanınmadı." for ad in sorted(bilinmeyen)})

    with transaction.atomic():
        ayar: KatalogAyari
        ayar, _ = KatalogAyari.objects.get_or_create(pk=KatalogAyari.SINGLETON_PK)
        for ad in AYAR_ALANLARI:
            if ad not in alanlar:
                continue
            deger = alanlar[ad]
            if ad in ("secili_ip", "son_afis_ip"):
                deger = _ipv4(deger, alan=ad)
            elif ad == "tahta_cidrleri":
                deger = tahta_bloklarini_dogrula(deger)
            setattr(ayar, ad, deger)
        _dogrula(ayar)
        ayar.full_clean()
        ayar.save()
        if SAATLER_ALANI in alanlar:
            _saatleri_yaz(alanlar[SAATLER_ALANI])
        transaction.on_commit(lambda: _dinleyicileri_cagir(ayar))
    return ayar


def _saatleri_yaz(deger: object) -> None:
    metin = str(deger or "").strip()
    if len(metin) > EN_COK_SAATLER:
        raise ValidationError(
            {SAATLER_ALANI: f"Kütüphane saatleri en çok {EN_COK_SAATLER} karakter olabilir."}
        )
    if not metin and not SchoolConfig.objects.filter(pk=SchoolConfig.SINGLETON_PK).exists():
        return  # boş metin için kurum satırı açılmaz (kurulum sihirbazı açar)
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.kutuphane_saatleri = metin
    config.save(update_fields=[SAATLER_ALANI, "updated_at"])
