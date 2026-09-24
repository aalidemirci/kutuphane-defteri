"""Ağ Doktoru — yönetim yüzeyinden Ağ Kataloğu denetçisine giden yol (tasarım §5.9, T16).

Katalog dinleyicisi, güvenlik duvarı denetimi ve IP adayları masaüstü
kabuğundadır (`desktop/katalog_kontrol.py`). Backend onlara HTTP ile değil,
kabuğun açılışta kaydettiği kancayla ulaşır (`apps.okul.masaustu_kanca`):
ikinci bir durum kaynağı ya da kontrol kanalı yoktur. Bu modül o kancanın
yönetim API'sine açılan tek kapısıdır; Ağ Doktoru ekranı ve Ayarlar → Ağ
Kataloğu bölümü yalnız bu işlevleri çağırır.

Kanca yoksa (geliştirme sunucusu, testler) durum sorgusu "masaüstü yok" der ve
EYLEMLER 503 `masaustu_yok` döner: katalogu açıp kapatan, güvenlik duvarını
okuyan ya da UAC isteyen bir işlem masaüstü programı dışında yapılamaz.

**Port değişikliği** (§5.2, §5.7): Windows'ta portla birlikte güvenlik duvarı
kuralı ve kurucunun okuduğu HKLM değeri de değişmelidir; bu yüzden ÖNCE UAC
yardımcısı kuralı yeni portla yazar, ancak başarırsa port ayarı kaydedilir.
UAC reddedilirse ya da kural yazılamazsa port DEĞİŞMEZ (409 `kural_yazilamadi`).
Pardus'ta program kural açmaz; port kaydedilir, Ağ Doktoru yeni komutu gösterir.

**Yayın adresi** (afiş, yer imleri, PYS metni, bilgi notu): katalog açıksa
dinlediği adres, değilse varsayılan rotanın adresi; kullanıcı Ağ Doktoru'nda
aday listesinden başka bir adres seçebilir (yalnız bu bilgisayarın adresleri).

Hiçbir yanıt yönetim portunu ya da istemci adresini taşımaz (§4.1, §5.5).
"""

from __future__ import annotations

import ipaddress
import sys
from typing import Any, Final

import segno
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.kutuphane.models import DinlemeKipi, KatalogAyari
from apps.kutuphane.services import katalog_ayari as katalog_ayari_service
from apps.okul import masaustu_kanca

WINDOWS: Final = "windows"
LINUX: Final = "linux"
DIGER: Final = "diger"

#: Denetçinin eylemleri (Ağ Doktoru ve ayar ekranı düğmeleri).
EYLEMLER: Final[frozenset[str]] = frozenset({"ac", "kapat", "yeniden_baslat"})

MASAUSTU_YOK_ILETISI: Final = (
    "Bu işlem yalnız masaüstü programında yapılır: Ağ Kataloğunun dinleyicisi ve "
    "güvenlik duvarı denetimi programın kendisindedir."
)
ADRES_YOK_ILETISI: Final = (
    "Bu bilgisayarın okul ağındaki adresi belirlenemedi. Ağ Doktoru'nda bir adres seçin "
    "ya da bilgisayarın ağ bağlantısını denetleyin."
)


class MasaustuYok(APIException):
    """Katalog denetçisi kayıtlı değil (geliştirme sunucusu): 503 `masaustu_yok`."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "masaustu_yok"
    default_detail = MASAUSTU_YOK_ILETISI


class AdresYok(APIException):
    """Belgeye basılacak adres bulunamadı: 409 `adres_yok`."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "adres_yok"
    default_detail = ADRES_YOK_ILETISI


class KuralYazilamadi(APIException):
    """UAC reddedildi ya da kural yazılamadı; port değişmedi: 409 `kural_yazilamadi`."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "kural_yazilamadi"
    default_detail = "Güvenlik duvarı kuralı yazılamadı; port değiştirilmedi."


def platform_adi(platform: str | None = None) -> str:
    """ "windows" / "linux" / "diger" (arayüz UAC düğmesini ya da Pardus komutunu buna göre seçer)."""
    deger = sys.platform if platform is None else platform
    if deger == "win32":
        return WINDOWS
    if deger.startswith("linux"):
        return LINUX
    return DIGER


def windows_mu() -> bool:
    """Port değişikliği UAC ister mi? (testler bu işlevi taklit eder)"""
    return platform_adi() == WINDOWS


def kontrol() -> masaustu_kanca.KatalogKontrolu:
    """Kayıtlı katalog denetçisi; yoksa `MasaustuYok` (503)."""
    denetci = masaustu_kanca.katalog_kontrolu()
    if denetci is None:
        raise MasaustuYok()
    return denetci


# ------------------------------------------------------------------ adres ve QR


def katalog_adresi(ip: str, port: int, *, tahta: bool = False) -> str:
    """Afişte ve yer imlerinde kullanılan adres; tahta yer imi `?tahta=1` taşır (§5.4)."""
    return f"http://{ip}:{int(port)}/" + ("?tahta=1" if tahta else "")


def qr_satirlari(metin: str) -> list[str]:
    """QR modülleri satır satır ("1" koyu); sessiz bölge çizen tarafa bırakılır.

    `make_qr` mikro QR'ı dışlar: cihazların çoğu mikro QR okumaz.
    """
    kod = segno.make_qr(metin, error="m")
    return ["".join("1" if hucre else "0" for hucre in satir) for satir in kod.matrix]


def _ip_dogrula(deger: object) -> str:
    metin = str(deger or "").strip()
    try:
        adres = ipaddress.IPv4Address(metin)
    except ValueError as exc:
        raise ValidationError({"ip": "Geçerli bir IPv4 adresi seçin."}) from exc
    if adres.is_loopback or adres.is_link_local or adres.is_multicast or adres.is_unspecified:
        raise ValidationError({"ip": "Bu adres okul ağındaki bir bağlantıya ait değil."})
    return str(adres)


def _aday_ipler(denetci: masaustu_kanca.KatalogKontrolu) -> list[str]:
    adaylar = denetci.ip_adaylari()
    return [
        str(arayuz.get("ip"))
        for arayuz in adaylar.get("arayuzler") or []
        if isinstance(arayuz, dict) and arayuz.get("ip")
    ]


def yayin_ip(istenen: str | None = None) -> str:
    """Belgelere basılacak IP (modül belgesindeki sıra); bulunamazsa `AdresYok`."""
    denetci = masaustu_kanca.katalog_kontrolu()
    if istenen:
        ip = _ip_dogrula(istenen)
        if denetci is not None and ip not in _aday_ipler(denetci):
            raise ValidationError(
                {"ip": "Bu adres bu bilgisayarın ağ bağlantılarından biri değil."}
            )
        return ip
    if denetci is not None:
        durum = denetci.durum()
        bulunan = durum.get("dinleme_ip") or durum.get("guncel_ip")
        if not bulunan:
            bulunan = denetci.ip_adaylari().get("varsayilan_ip")
        if bulunan:
            return str(bulunan)
    ayar = katalog_ayari_service.katalog_ayari()
    kayitli = ayar.secili_ip or ayar.son_afis_ip
    if kayitli:
        return str(kayitli)
    raise AdresYok()


# ------------------------------------------------------------------ durum


def katalog_sayaclari() -> dict[str, Any]:
    """Süreç içi katalogun kişisiz günlük sayaçları ve son hatası (§5.5).

    Sayaçlar bellektedir ve yalnız bu süreçte anlamlıdır; masaüstünün
    dinleyicisi aynı örneği (`katalog.app.application`) sunar.
    """
    from katalog import app as katalog_app

    sayaclar = katalog_app.application.sayaclar
    son = sayaclar.son_hata
    return {
        "bugun": sayaclar.gun(),
        "son_hata": None if son is None else {"zaman": son.zaman.isoformat(), "ileti": son.ileti},
    }


def durum_ozeti(katalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ağ Doktoru'nun ve ayar ekranının durum satırı (kişisel veri ve yönetim portu yok).

    `katalog` verilirse (bir eylemin döndürdüğü durum) denetçi yeniden sorulmaz.
    """
    denetci = masaustu_kanca.katalog_kontrolu()
    if katalog is None and denetci is not None:
        katalog = denetci.durum()
    adres = (katalog or {}).get("adres")
    return {
        "masaustu": denetci is not None,
        "platform": platform_adi(),
        "katalog": katalog,
        "qr": qr_satirlari(str(adres)) if adres else None,
        "sayaclar": katalog_sayaclari(),
    }


def eylem(ad: str) -> dict[str, Any]:
    """Aç / kapat / yeniden başlat; güncel durum özetini döndürür."""
    if ad not in EYLEMLER:
        raise ValidationError({"eylem": "Eylem tanınmadı."})
    denetci = kontrol()
    if ad == "ac":
        sonuc = denetci.ac()
    elif ad == "kapat":
        sonuc = denetci.kapat()
    else:
        sonuc = denetci.yeniden_baslat()
    return durum_ozeti(sonuc)


def guvenlik_duvari() -> dict[str, Any]:
    """Beş maddeyi yeniden okur ("Yenile")."""
    return kontrol().guvenlik_duvari()


def ip_adaylari() -> dict[str, Any]:
    return kontrol().ip_adaylari()


def dinleyici_sinamasi() -> dict[str, Any]:
    """Her aday IP'de "dinleyici bu arayüzde ayakta" öz sınaması + uyarı + komutlar (§5.9)."""
    return kontrol().dinleyici_sinamasi()


def _tahta_bloklari(ayar: KatalogAyari) -> list[str]:
    return [str(blok) for blok in (ayar.tahta_cidrleri or []) if blok]


def kural_guncelle() -> dict[str, Any]:
    """ "Kuralı ekle/güncelle" (UAC): kayıtlı port ve tahta ağı bloklarıyla."""
    ayar = katalog_ayari_service.katalog_ayari()
    sonuc = kontrol().kural_guncelle(port=int(ayar.port), uzak_adresler=_tahta_bloklari(ayar))
    return {
        "tamam": bool(sonuc.get("tamam")),
        "ileti": str(sonuc.get("ileti") or ""),
        "durum": durum_ozeti(sonuc.get("durum") if isinstance(sonuc.get("durum"), dict) else None),
    }


def port_degistir(port: int) -> dict[str, Any]:
    """Portu değiştirir; Windows'ta önce UAC ile kural + HKLM (modül belgesi)."""
    ayar = katalog_ayari_service.katalog_ayari()
    denetci = masaustu_kanca.katalog_kontrolu()
    ileti = "Port değiştirildi."
    if windows_mu():
        if denetci is None:
            raise MasaustuYok()
        sonuc = denetci.kural_guncelle(port=int(port), uzak_adresler=_tahta_bloklari(ayar))
        if not sonuc.get("tamam"):
            raise KuralYazilamadi(
                f"{sonuc.get('ileti') or 'Güvenlik duvarı kuralı yazılamadı.'} "
                "Port değiştirilmedi."
            )
        ileti = "Port değiştirildi; güvenlik duvarı kuralı da güncellendi."
    katalog_ayari_service.update_katalog_ayari(port=int(port))
    katalog: dict[str, Any] | None = None
    if denetci is not None:
        # Ayar dinleyicisi de yeniden kurar; eşzamanlı kurulum sonucu yanıtta görünsün.
        katalog = denetci.yeniden_baslat()
    return {"tamam": True, "ileti": ileti, "durum": durum_ozeti(katalog)}


def dinleme_ozeti(ayar: KatalogAyari) -> str:
    """Belgelerde dinleme kipinin Türkçe anlatımı."""
    if ayar.dinleme_kipi == DinlemeKipi.SELECTED and ayar.secili_ip:
        return f"Yalnız seçili adreste ({ayar.secili_ip})"
    return "Bu bilgisayarın bütün ağ bağlantılarında"
