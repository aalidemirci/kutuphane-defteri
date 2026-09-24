"""Ağ Kataloğu denetçisi — masaüstü ile backend arasındaki tek kanal (tasarım T16, §5).

Katalog sunucusu ve tepsi HTTP dışında kalır. Backend (Ağ Doktoru, Ayarlar →
Ağ Kataloğu, geri yükleme) ve tepsi katalogu YALNIZ bu nesne üzerinden açar,
kapatır, yeniden başlatır; durumu ve son hatayı buradan okur. Nesne açılışta
backend'e kanca olarak kaydolur (`apps.okul.masaustu_kanca.kaydet`); ikinci bir
durum kaynağı ya da HTTP kontrol kanalı yoktur (GA-8, UY-17).

KARAR SIRASI (`_dinle`)

1. Bakımdaysa (geri yükleme) hiçbir şey yapılmaz: katalog program yeniden
   açılana dek kapalı kalır (§5.3-5).
2. Ayar okunur (`KatalogAyari` — port ve IP'nin tek kaynağı). Kapalıysa
   dinlenmez.
3. Dinleme adresi: "tüm arayüzler" ya da "yalnız seçili IP". Seçili IP bu
   bilgisayarda yoksa ve bilgisayarın TEK aday adresi varsa katalog o adreste
   açılır ve kullanıcı uyarılır (§5.2 "IP değişirse dinleyici yeni IP'de yeniden
   açılır"); birden çok aday varsa hangisinin istendiği bilinemez — katalog
   açılmaz, Ağ Doktoru seçim ister (yanlış ağa, ör. öğrenci erişimli ağa
   sessizce açılmasın). Arayüz listesi OKUNAMADIYSA (yedek yol yalnız
   varsayılan adresi bilir) tek aday kuralı uygulanmaz: seçili IP belki hâlâ
   buradadır ve tek aday başka bir ağdır. Katalog açılmaz, kısa süre sonra
   yeniden denenir (geçici hata).
4. Güvenlik duvarı denetimi (§5.7): Windows'ta beş madde; biri tutmazsa katalog
   okul ağında DİNLEMEZ (durum `engellendi`, §5.10-10). Linux'ta bilgi; komutun
   kaynak blokları (yerel alt ağlar + tahta ağı blokları) buradan verilir.
   Denetim OKUNAMADIYSA (PowerShell zaman aşımı; ör. oturum açılışının yükü)
   katalog yine açılmaz ama kısa aralıklarla birkaç kez, sonra saatte bir
   kendiliğinden yeniden denenir. Kuralın gerçekten tutmadığı durum yeniden
   denenmez (kullanıcının düzeltmesi gerekir).
5. Soket (`KatalogPortInUseError` → `bekliyor`: port kısa süre içinde kendiliğinden
   yeniden denenir), waitress, öz sınama (§4.2-2). Öz sınama geçmezse dinleyici
   kapanır, son hata Ağ Doktoru'na düşer.

UYKU (§4.5). Katalog açıkken ve ayar izin veriyorsa boşta kalma uykusu
engellenir. Engellemenin sahibi `kd-gunluk` iş parçacığıdır; bu nesne durum
değişince onu `uyku_degisti` ile uyandırır ve `uyku_gerekli()` ile soruya
yanıt verir.

GERİ YÜKLEME (§5.3). `bakima_al`: (1) ortak bakım kapısı kapanır — yeni katalog
istekleri veritabanına dokunmadan 503 alır, gün değişimi işleri başlamaz;
(2) dinleyici kapanır, yeni bağlantı gelmez; (3) uçuştaki istekler ve işler
biter; (4) açık kanallar ve görev havuzu kapanır. Katalog program yeniden
açılana dek kapalı kalır; `bakimdan_cik` yalnız takas BAŞARISIZ olursa eski
hâle döner.

İP DENETİMİ (§5.6, T9). Gün değişimi kapısı günde bir `ip_denetle` çağırır: adres
son afişteki (ya da son denetimdeki) adresten farklıysa "afişi yeniden basın,
yer imlerini güncelleyin" uyarısı durumda görünür. "Dinlenen seçili IP hâlâ bu
bilgisayarda mı?" sorusu ise günlük değil SAATLİK ve damgasızdır
(`saatlik_denetle`): DHCP gün içinde yeni adres verirse dinleyici bir sonraki
saatlik tikte yeni adreste kurulur; tepsi ve Ağ Doktoru ertesi güne dek
kaybolan adreste "açık" göstermez.

Hiçbir yöntem istisna sızdırmaz: sonuç `durum()` sözlüğündedir. İstemci IP'si
hiçbir yere yazılmaz; yönetim portu hiçbir yanıtta yoktur (§4.1).
"""

from __future__ import annotations

import ipaddress
import logging
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final, Protocol

from desktop import ag, guvenlik_duvari

# Sınıfta `guvenlik_duvari` adlı bir yöntem de var: sınıf gövdesindeki ek açıklamalar
# modül adını değil yöntemi görür. Tür doğrudan içe aktarılır.
from desktop.guvenlik_duvari import GuvenlikDuvariDenetimi
from desktop.katalog_server import (
    DEFAULT_PORT,
    DINLEME_SECILI,
    DINLEME_TUM,
    CatalogApp,
    KatalogAdresYokError,
    KatalogArayuzOkunamadiError,
    KatalogPortInUseError,
    KatalogServer,
    KatalogServerError,
    dinleme_hostu,
    dinleyici_ayakta_mi,
    load_catalog,
    self_test,
    tum_arayuzler_mi,
)

logger = logging.getLogger("kutuphane_defteri.katalog")

KAPALI: Final = "kapali"
ACIK: Final = "acik"
ENGELLENDI: Final = "engellendi"
HATA: Final = "hata"
BEKLIYOR: Final = "bekliyor"
BAKIM: Final = "bakim"

YENIDEN_DENEME_ARALIGI_SN: Final = 10.0
YENIDEN_DENEME_SURESI_SN: Final = 300.0
BAKIM_BEKLEME_SN: Final = 10.0
#: Geçici (okunamayan) durumda gecikmeli yeniden deneme: aralık ve sayı. Sonra saatte bir.
GECICI_DENEME_ARALIGI_SN: Final = 60.0
GECICI_DENEME_SAYISI: Final = 5

_DOKTOR_UYARISI: Final = (
    "Bu sınama güvenlik duvarını ya da VLAN'ı kanıtlamaz: makinenin kendi IP'sine "
    "yapılan bağlantı loopback'ten geçer. Başka bir bilgisayardan deneyin."
)


@dataclass(frozen=True)
class KatalogYapilandirmasi:
    """`KatalogAyari`'nın masaüstünün kullandığı alanları (Django'dan bağımsız kopya)."""

    acik: bool = False
    port: int = DEFAULT_PORT
    dinleme_kipi: str = DINLEME_TUM
    secili_ip: str = ""
    son_afis_ip: str = ""
    uyku_engelleme: bool = True
    tahta_cidrleri: tuple[str, ...] = ()


def yapilandirma_nesneden(nesne: Any) -> KatalogYapilandirmasi:
    """`apps.kutuphane.models.KatalogAyari` örneğinden kopya (alan adları sözleşmede)."""
    cidrler = getattr(nesne, "tahta_cidrleri", None) or []
    return KatalogYapilandirmasi(
        acik=bool(getattr(nesne, "acik", False)),
        port=int(getattr(nesne, "port", DEFAULT_PORT) or DEFAULT_PORT),
        dinleme_kipi=str(getattr(nesne, "dinleme_kipi", DINLEME_TUM) or DINLEME_TUM),
        secili_ip=str(getattr(nesne, "secili_ip", "") or ""),
        son_afis_ip=str(getattr(nesne, "son_afis_ip", "") or ""),
        uyku_engelleme=bool(getattr(nesne, "uyku_engelleme", True)),
        tahta_cidrleri=tuple(str(c) for c in cidrler if isinstance(c, str)),
    )


def django_ayar_okuyucu() -> KatalogYapilandirmasi:
    """Ayarı Django'dan okur (istek dışı iş parçacığında bağlantıyı kapatarak)."""
    from desktop.django_bootstrap import is_parcacigi_baglantisiyla

    def oku() -> KatalogYapilandirmasi:
        try:
            from apps.kutuphane.services.katalog_ayari import katalog_ayari
        except ImportError:  # pragma: no cover — servis K kolunda; model yedeği
            from apps.kutuphane.models import KatalogAyari

            return yapilandirma_nesneden(KatalogAyari.load())
        return yapilandirma_nesneden(katalog_ayari())

    return is_parcacigi_baglantisiyla(oku)


def django_ayar_dinleyicisi(dinleyici: Callable[[], None]) -> Callable[[], None]:
    """Ayar kalıcılaşınca (`on_commit`) çağrılacak dinleyiciyi kaydeder; kaydı silen işlev."""
    from apps.kutuphane.services.katalog_ayari import ayar_degisince

    return ayar_degisince(lambda _ayar: dinleyici())


def django_ayar_yazici(**alanlar: Any) -> None:
    """Ayarı Django üzerinden yazar (servis yalnız yönetici kipinde yazar)."""
    from desktop.django_bootstrap import is_parcacigi_baglantisiyla

    def yaz() -> None:
        from apps.kutuphane.services.katalog_ayari import update_katalog_ayari

        update_katalog_ayari(**alanlar)

    is_parcacigi_baglantisiyla(yaz)


class BakimKapisi(Protocol):
    """Ortak bakım kapısı (`katalog.bakim.KAPI`)."""

    def bakima_al(self, *, bekleme_sn: float = ...) -> bool: ...

    def bakimdan_cik(self) -> None: ...


def varsayilan_bakim_kapisi() -> BakimKapisi | None:
    try:
        from katalog.bakim import KAPI
    except ImportError:
        return None
    return KAPI


@dataclass
class _Durum:
    durum: str = KAPALI
    son_hata: str | None = None
    uyarilar: list[str] = field(default_factory=list)
    denetim: guvenlik_duvari.GuvenlikDuvariDenetimi | None = None
    ayar: KatalogYapilandirmasi = field(default_factory=KatalogYapilandirmasi)
    dinleme_ip: str | None = None
    tum_arayuzler: bool = False
    guncel_ip: str | None = None
    ip_uyarisi: str | None = None
    #: Son başarısızlık GEÇİCİ mi (güvenlik duvarı ya da arayüz listesi okunamadı)?
    gecici: bool = False


def _dinleme_ozeti(ayar: KatalogYapilandirmasi) -> tuple[object, ...]:
    """Dinleyiciyi yeniden kurmayı gerektiren alanlar (uyku ve afiş IP'si kurmaz)."""
    return (ayar.acik, ayar.port, ayar.dinleme_kipi, ayar.secili_ip)


class KatalogKontrol:
    """Ağ Kataloğunu ayara göre kaldıran, izleyen ve kapatan denetçi (T16)."""

    def __init__(
        self,
        *,
        ayar_okuyucu: Callable[[], KatalogYapilandirmasi] = django_ayar_okuyucu,
        ayar_yazici: Callable[..., None] | None = django_ayar_yazici,
        yukleyici: Callable[[], CatalogApp] = load_catalog,
        ag_saglayici: Callable[[], ag.AgDurumu] = ag.ag_durumu,
        duvar_denetleyici: Callable[..., guvenlik_duvari.GuvenlikDuvariDenetimi] | None = None,
        sunucu_kurucu: Callable[..., KatalogServer] = KatalogServer,
        oz_sinama: Callable[..., None] = self_test,
        ayakta_mi: Callable[..., bool] = dinleyici_ayakta_mi,
        kural_yazici: Callable[..., tuple[bool, str]] = guvenlik_duvari.kural_guncelle_uac,
        bakim_kapisi: BakimKapisi | None = None,
        platform: str = sys.platform,
        exe_yolu: str | None = None,
        yeniden_deneme_araligi_sn: float = YENIDEN_DENEME_ARALIGI_SN,
        yeniden_deneme_suresi_sn: float = YENIDEN_DENEME_SURESI_SN,
        gecici_deneme_araligi_sn: float = GECICI_DENEME_ARALIGI_SN,
        gecici_deneme_sayisi: int = GECICI_DENEME_SAYISI,
        saat: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ayar_oku = ayar_okuyucu
        self._ayar_yaz = ayar_yazici
        self._yukle = yukleyici
        self._ag = ag_saglayici
        self._platform = platform
        self._exe = exe_yolu or sys.executable
        self._duvar = duvar_denetleyici or self._varsayilan_duvar
        self._kurucu = sunucu_kurucu
        self._oz_sinama = oz_sinama
        self._ayakta_mi = ayakta_mi
        self._kural_yaz = kural_yazici
        self._bakim_kapisi = bakim_kapisi
        self._aralik = yeniden_deneme_araligi_sn
        self._sure = yeniden_deneme_suresi_sn
        self._gecici_aralik = gecici_deneme_araligi_sn
        self._gecici_sayi = gecici_deneme_sayisi
        #: Geçici hatada kalan gecikmeli deneme sayısı; None = sayım başlamadı.
        self._gecici_kalan: int | None = None
        self._saat = saat
        # İşlem kilidi (aç/kapa/yeniden başlat sırayla) ve hafif durum kilidi (okuma).
        self._islem = threading.RLock()
        self._kilit = threading.Lock()
        self._d = _Durum()
        self._sunucu: KatalogServer | None = None
        self._imza: bytes = b""
        self._bakimda = False
        self._kapanista = False
        self._zamanlayici: threading.Timer | None = None
        self._deneme_bitis: float | None = None
        self._uyku_dinleyicileri: list[Callable[[], None]] = []
        #: Son `_uygula`'da kullanılan dinleme alanları (ayar dinleyicisi karşılaştırır).
        self._uygulanan: tuple[object, ...] | None = None

    # ------------------------------------------------------------ bağlantılar

    def uyku_dinleyicisi_ekle(self, dinleyici: Callable[[], None]) -> None:
        """Durum değişince çağrılır (`kd-gunluk` uyandırılır, uyku ayarı uygulanır)."""
        self._uyku_dinleyicileri.append(dinleyici)

    def _uyku_bildir(self) -> None:
        for dinleyici in list(self._uyku_dinleyicileri):
            try:
                dinleyici()
            except Exception:  # noqa: BLE001 — bildirim durumu bozmasın
                logger.warning("Uyku bildirimi başarısız.", exc_info=True)

    def ayar_degisince(self) -> None:
        """Ayar yazıldı (Ayarlar ekranı, Ağ Doktoru): gerekiyorsa katalog yeniden kurulur.

        `update_katalog_ayari`'nın `on_commit` dinleyicisidir ve İSTEK iş
        parçacığında çağrılır; güvenlik duvarı denetimi saniyeler sürebileceği
        için iş ayrı bir iş parçacığında yapılır. Dinleme alanları son
        uygulananla aynıysa (ör. `ac()` ayarı yazıp katalogu zaten kaldırdı,
        yalnız uyku ayarı değişti) yeniden kurulmaz; uyku durumu yine uygulanır.
        """
        threading.Thread(target=self._ayar_degisti, name="kd-katalog-ayar", daemon=True).start()

    def _ayar_degisti(self) -> None:
        with self._islem:
            ayar = self._ayari_tazele()
            yeniden = _dinleme_ozeti(ayar) != self._uygulanan
            if yeniden:
                self._uygula_kilitli(yeniden_deneme=False)
            else:
                self._afis_uyarisini_guncelle(ayar)
        self._uyku_bildir()

    def _afis_uyarisini_guncelle(self, ayar: KatalogYapilandirmasi) -> None:
        with self._kilit:
            if ayar.son_afis_ip and ayar.son_afis_ip == self._d.guncel_ip:
                self._d.ip_uyarisi = None

    # ------------------------------------------------------------ sorgular

    def durum(self) -> dict[str, Any]:
        """Ağ Doktoru, ayar ekranı ve tepsinin okuduğu durum (kişisel veri yok)."""
        with self._kilit:
            d = self._d
            ayar = d.ayar
            sunucu = self._sunucu
            adres_ip = d.dinleme_ip if not d.tum_arayuzler else d.guncel_ip
            uyarilar = list(d.uyarilar)
            if d.ip_uyarisi:
                uyarilar.append(d.ip_uyarisi)
            return {
                "durum": d.durum,
                "ayar_acik": ayar.acik,
                "dinleme_kipi": ayar.dinleme_kipi,
                "tum_arayuzler": d.tum_arayuzler,
                "dinleme_ip": d.dinleme_ip,
                "port": ayar.port,
                "adres": ag.katalog_adresi(adres_ip, ayar.port)
                if d.durum == ACIK and adres_ip
                else None,
                "guncel_ip": d.guncel_ip,
                "son_afis_ip": ayar.son_afis_ip or None,
                "ip_degisti": bool(
                    ayar.son_afis_ip and d.guncel_ip and ayar.son_afis_ip != d.guncel_ip
                ),
                "son_hata": d.son_hata,
                "uyarilar": uyarilar,
                "guvenlik_duvari": d.denetim.sozluk() if d.denetim is not None else None,
                "reddedilen_baglanti": sunucu.reddedilen_baglanti if sunucu is not None else 0,
                "uyku_engelli": self._uyku_gerekli_kilitsiz(),
            }

    def acik_mi(self) -> bool:
        with self._kilit:
            return self._d.durum == ACIK

    def kapatilabilir_mi(self) -> bool:
        """Tepsi ve ekranlar "Ağ Kataloğunu kapat" sunsun mu?

        Açıkken ve ayar açık olduğu hâlde açılamadığında (güvenlik duvarı izni
        yok, açılamadı, port bekleniyor) evet: ayar açık kaldıkça program her
        açılışta yeniden dener, kullanıcı vazgeçebilmelidir. Kapalıyken ve geri
        yüklemede hayır.
        """
        with self._kilit:
            d = self._d
            return d.durum == ACIK or (d.ayar.acik and d.durum not in (KAPALI, BAKIM))

    def uyku_gerekli(self) -> bool:
        """Boşta kalma uykusu engellensin mi? (yalnız `kd-gunluk` sorar)"""
        with self._kilit:
            return self._uyku_gerekli_kilitsiz()

    def _uyku_gerekli_kilitsiz(self) -> bool:
        return self._d.durum == ACIK and self._d.ayar.uyku_engelleme and not self._kapanista

    def tepsi_satiri(self) -> str:
        """Tepsideki durum satırı: "Ağ Kataloğu: açık — http://…"."""
        d = self.durum()
        durum = d["durum"]
        if durum == ACIK and d["adres"]:
            return f"Ağ Kataloğu: açık — {d['adres']}"
        return {
            KAPALI: "Ağ Kataloğu: kapalı",
            ACIK: "Ağ Kataloğu: açık",
            ENGELLENDI: "Ağ Kataloğu: güvenlik duvarı izni yok",
            HATA: "Ağ Kataloğu: açılamadı",
            BEKLIYOR: "Ağ Kataloğu: port bekleniyor",
            BAKIM: "Ağ Kataloğu: geri yükleme nedeniyle kapalı",
        }.get(durum, "Ağ Kataloğu")

    def adres(self) -> str | None:
        adres = self.durum()["adres"]
        return str(adres) if adres else None

    # ------------------------------------------------------------ eylemler

    def acilista_baslat(self) -> None:
        """Açılış: ayar açıksa katalogu kaldırır (hatası ölümcül değil, durumda görünür)."""
        self._uygula()

    def ac(self) -> dict[str, Any]:
        """Ayarı açık yapar ve katalogu kaldırır."""
        with self._islem:
            if self._ayar_yazdi(acik=True):
                self._uygula()
        return self.durum()

    def kapat(self) -> dict[str, Any]:
        """Ayarı kapalı yapar ve katalogu kapatır."""
        with self._islem:
            # Yazılamazsa (ör. görevli kipinde servis reddeder) hiçbir şey değişmez.
            if not self._ayar_yazdi(acik=False):
                return self.durum()
            self._durdur(yeni_durum=BAKIM if self._bakimda else KAPALI)
            self._uygulanan = _dinleme_ozeti(self._ayari_tazele())
        self._uyku_bildir()
        return self.durum()

    def yeniden_baslat(self) -> dict[str, Any]:
        """Güncel ayarla yeniden kaldırır (port, dinleme kipi ya da IP değişince)."""
        self._uygula()
        return self.durum()

    def kapanis(self) -> None:
        """Program kapanırken: zamanlayıcı iptal, dinleyici kapanır, uyku bırakılır."""
        with self._islem:
            self._kapanista = True
            self._deneme_bitis = None
            self._durdur(yeni_durum=KAPALI)
        self._uyku_bildir()

    def bakima_al(self) -> None:
        """Geri yükleme: bakım kapısı → dinleyici → uçuştaki istekler → kanallar (§5.3)."""
        with self._islem:
            self._bakimda = True
            kapi = (
                self._bakim_kapisi if self._bakim_kapisi is not None else varsayilan_bakim_kapisi()
            )
            if kapi is not None:
                try:
                    if not kapi.bakima_al(bekleme_sn=BAKIM_BEKLEME_SN):
                        logger.warning("Bakım kapısı: uçuştaki işler süresinde bitmedi.")
                except Exception:  # noqa: BLE001 — geri yükleme durmasın
                    logger.warning("Bakım kapısı kapatılamadı.", exc_info=True)
            self._durdur(yeni_durum=BAKIM)
            logger.info("Ağ Kataloğu geri yükleme için kapatıldı.")
        self._uyku_bildir()

    def bakimdan_cik(self) -> None:
        """Geri yükleme BAŞARISIZ: kapı açılır, ayar açıksa katalog yeniden kalkar."""
        with self._islem:
            self._bakimda = False
            kapi = (
                self._bakim_kapisi if self._bakim_kapisi is not None else varsayilan_bakim_kapisi()
            )
            if kapi is not None:
                try:
                    kapi.bakimdan_cik()
                except Exception:  # noqa: BLE001
                    logger.warning("Bakım kapısı açılamadı.", exc_info=True)
            with self._kilit:
                self._d.durum = KAPALI
        self._uygula()

    def ip_denetle(self) -> bool:
        """Gün değişimi işi: IP değişti mi? Seçili IP kayboldıysa katalog yeniden kurulur."""
        ayar = self._ayari_tazele()
        durum = self._ag_oku()
        with self._kilit:
            onceki = self._d.guncel_ip
            secili_var = (
                ayar.dinleme_kipi == DINLEME_SECILI
                and ayar.secili_ip
                and durum.ip_var_mi(ayar.secili_ip)
            )
            guncel = ayar.secili_ip if secili_var else durum.varsayilan_ip
            self._d.guncel_ip = guncel
            karsilastirma = ayar.son_afis_ip or onceki
            if guncel and karsilastirma and guncel != karsilastirma:
                self._d.ip_uyarisi = (
                    f"Bu bilgisayarın IP adresi değişti ({karsilastirma} → {guncel}). "
                    "Afişi yeniden basın, yer imlerini güncelleyin."
                )
                logger.warning(
                    "Bu bilgisayarın IP adresi değişti; afişi yeniden basın, yer imlerini "
                    "güncelleyin."
                )
            elif ayar.son_afis_ip and guncel == ayar.son_afis_ip:
                self._d.ip_uyarisi = None
        self._dinleme_ipsini_denetle(durum)
        return True

    def saatlik_denetle(self) -> bool:
        """Saatlik, DAMGASIZ iş (gün değişimi kapısının her tikinde koşar).

        1. Dinlenen seçili IP hâlâ bu bilgisayarda mı? Değilse dinleyici yeniden
           kurulur (§5.2): DHCP gün içinde adres değiştirirse katalog ertesi güne
           dek kaybolan adreste "açık" kalmaz. Ağ yalnız bu durumda okunur.
        2. Son başarısızlık GEÇİCİYSE (denetim ya da arayüz listesi okunamadı) ve
           gecikmeli denemeler bittiyse bir kez yeniden denenir.
        """
        if self._bakimda or self._kapanista:
            return True
        with self._kilit:
            d = self._d
            secili_acik = d.durum == ACIK and not d.tum_arayuzler and d.dinleme_ip is not None
            gecici = d.gecici and d.durum in (ENGELLENDI, HATA)
        if secili_acik:
            self._dinleme_ipsini_denetle(self._ag_oku())
        elif gecici:
            with self._islem:
                if self._zamanlayici is None and not (self._bakimda or self._kapanista):
                    logger.info("Ağ Kataloğu geçici hatadan sonra saatlik denemeyle açılıyor.")
                    self._gecici_kalan = 0  # bu deneme de tutmazsa bir sonraki saate kalır
                    self._uygula_kilitli(yeniden_deneme=True)
            self._uyku_bildir()
        return True

    def _dinleme_ipsini_denetle(self, durum: ag.AgDurumu) -> None:
        """Seçili IP'de dinlerken o IP bu bilgisayardan kalktıysa dinleyiciyi yeniden kurar.

        Arayüz listesi okunamadıysa karar verilmez: çalışan dinleyici geçici bir
        PowerShell hatası yüzünden kapatılmaz.
        """
        if durum.okunamadi:
            return
        with self._kilit:
            yeniden = (
                self._d.durum == ACIK
                and not self._d.tum_arayuzler
                and self._d.dinleme_ip is not None
                and not durum.ip_var_mi(self._d.dinleme_ip)
            )
        if yeniden:
            logger.warning(
                "Ağ Kataloğunun dinlediği IP bu bilgisayarda artık yok; yeniden kuruluyor."
            )
            self._uygula()

    # ------------------------------------------------------ Ağ Doktoru sorguları

    def guvenlik_duvari(self) -> dict[str, Any]:
        """Beş maddeyi yeniden okur (Ağ Doktoru "Yenile")."""
        ayar = self._ayari_tazele()
        denetim = self._duvar(port=ayar.port, exe_yolu=self._exe)
        with self._kilit:
            self._d.denetim = denetim
        return denetim.sozluk()

    def ip_adaylari(self) -> dict[str, Any]:
        ayar = self._ayari_tazele()
        return self._ag_oku().sozluk(
            tum_arayuzler=ayar.dinleme_kipi == DINLEME_TUM, tahta_bloklari=ayar.tahta_cidrleri
        )

    def dinleyici_sinamasi(self) -> dict[str, Any]:
        """Her aday IP'de "dinleyici bu arayüzde ayakta" öz sınaması (§5.9)."""
        with self._kilit:
            port = self._d.ayar.port
            acik = self._d.durum == ACIK
            imza = self._imza
        sonuclar: list[dict[str, Any]] = []
        if acik:
            for arayuz in self._ag_oku().arayuzler:
                sonuclar.append(
                    {
                        "ip": arayuz.ip,
                        "ad": arayuz.ad,
                        "ayakta": self._ayakta_mi(arayuz.ip, port, signature=imza),
                        "komut": f"Test-NetConnection {arayuz.ip} -Port {port}",
                    }
                )
        return {"acik": acik, "port": port, "sonuclar": sonuclar, "uyari": _DOKTOR_UYARISI}

    def kural_guncelle(self, *, port: int, uzak_adresler: list[str]) -> dict[str, Any]:
        """UAC ile güvenlik duvarı kuralını ve HKLM portunu yazar, sonra yeniden kurar."""
        tamam, ileti = self._kural_yaz(port=port, uzak_adresler=uzak_adresler)
        if tamam:
            self._uygula()
        return {"tamam": tamam, "ileti": ileti, "durum": self.durum()}

    # ------------------------------------------------------------ iç akış

    def _ayar_yazdi(self, **alanlar: Any) -> bool:
        if self._ayar_yaz is None:
            return True
        try:
            self._ayar_yaz(**alanlar)
        except Exception as exc:  # noqa: BLE001 — ileti durumda görünür
            logger.warning("Ağ Kataloğu ayarı yazılamadı: %s", exc)
            with self._kilit:
                self._d.son_hata = "Ağ Kataloğu ayarı kaydedilemedi."
            return False
        return True

    def _ayari_tazele(self) -> KatalogYapilandirmasi:
        try:
            ayar = self._ayar_oku()
        except Exception:  # noqa: BLE001 — okunamazsa son bilinen ayar
            logger.warning("Ağ Kataloğu ayarı okunamadı.", exc_info=True)
            with self._kilit:
                return self._d.ayar
        with self._kilit:
            self._d.ayar = ayar
        return ayar

    def _ag_oku(self) -> ag.AgDurumu:
        try:
            return self._ag()
        except Exception:  # noqa: BLE001
            logger.warning("Ağ durumu okunamadı.", exc_info=True)
            return ag.AgDurumu()

    def _varsayilan_duvar(self, *, port: int, exe_yolu: str) -> GuvenlikDuvariDenetimi:
        """Platform denetimi; Linux'ta komutun kaynak blokları da verilir (GA-6)."""
        bloklar = self._linux_kaynak_bloklari() if self._platform.startswith("linux") else []
        return guvenlik_duvari.denetle(
            platform=self._platform, port=port, exe_yolu=exe_yolu, bloklar=bloklar
        )

    def _linux_kaynak_bloklari(self) -> list[str]:
        """Bu bilgisayarın yerel alt ağları + Ayarlar'daki tahta ağı blokları.

        Windows kuralının `LocalSubnet` + bloklar kapsamının Linux karşılığıdır.
        """
        durum = self._ag_oku()
        with self._kilit:
            tahta = self._d.ayar.tahta_cidrleri
        yerel: list[str] = []
        for arayuz in durum.arayuzler:
            if arayuz.onek <= 0:  # yedek yol öneki bilmez
                continue
            try:
                yerel.append(str(ipaddress.IPv4Interface(f"{arayuz.ip}/{arayuz.onek}").network))
            except ValueError:
                continue
        return list(dict.fromkeys([*yerel, *tahta]))

    def _durum_yaz(self, durum: str, *, son_hata: str | None = None, **alanlar: Any) -> None:
        with self._kilit:
            self._d.durum = durum
            self._d.son_hata = son_hata
            for ad, deger in alanlar.items():
                setattr(self._d, ad, deger)

    def _zamanlayiciyi_iptal(self) -> None:
        zamanlayici, self._zamanlayici = self._zamanlayici, None
        if zamanlayici is not None:
            zamanlayici.cancel()

    def _durdur(self, *, yeni_durum: str) -> None:
        self._zamanlayiciyi_iptal()
        sunucu, self._sunucu = self._sunucu, None
        if sunucu is not None:
            try:
                sunucu.stop()
            except Exception:  # noqa: BLE001 — kapanış sürmeli
                logger.exception("Ağ Kataloğu kapatılırken hata oluştu (yok sayıldı).")
        with self._kilit:
            self._d.durum = yeni_durum
            self._d.dinleme_ip = None
            self._d.tum_arayuzler = False
            self._d.gecici = False
            if yeni_durum in (KAPALI, BAKIM):
                self._d.son_hata = None

    def _uygula(self) -> None:
        with self._islem:
            self._uygula_kilitli(yeniden_deneme=False)
        self._uyku_bildir()

    def _uygula_kilitli(self, *, yeniden_deneme: bool) -> None:
        if self._kapanista:
            return
        if not yeniden_deneme:
            # Kullanıcı eylemi ya da ayar değişikliği: port bekleme süresi ve geçici
            # hata denemeleri yeniden başlar.
            self._deneme_bitis = None
            self._gecici_kalan = None
        self._durdur(yeni_durum=BAKIM if self._bakimda else KAPALI)
        if self._bakimda:
            return
        ayar = self._ayari_tazele()
        self._uygulanan = _dinleme_ozeti(ayar)
        if not ayar.acik:
            return
        durum = self._ag_oku()
        uyarilar = durum.uyarilar(
            tum_arayuzler=ayar.dinleme_kipi == DINLEME_TUM, tahta_bloklari=ayar.tahta_cidrleri
        )
        with self._kilit:
            self._d.uyarilar = uyarilar
            self._d.guncel_ip = (
                ayar.secili_ip
                if ayar.dinleme_kipi == DINLEME_SECILI and durum.ip_var_mi(ayar.secili_ip)
                else durum.varsayilan_ip
            )
        try:
            host = self._dinleme_adresi(ayar, durum)
        except KatalogArayuzOkunamadiError as exc:
            self._gecici_hata(HATA, exc.message)
            return
        except KatalogServerError as exc:
            self._durum_yaz(HATA, son_hata=exc.message)
            return
        except ValueError as exc:
            self._durum_yaz(HATA, son_hata=f"Ağ Kataloğu açılamadı: {exc}")
            return

        denetim = self._duvar(port=ayar.port, exe_yolu=self._exe)
        with self._kilit:
            self._d.denetim = denetim
        if not denetim.dinlemeye_izin:
            ilk = next(
                (
                    m
                    for m in denetim.maddeler
                    if m.durum not in (guvenlik_duvari.GECTI, guvenlik_duvari.UYARI)
                ),
                None,
            )
            neden = denetim.hata or (ilk.aciklama if ilk is not None else "")
            ileti = (
                "Ağ Kataloğu okul ağına açılmadı: güvenlik duvarı denetimi geçmedi. " + neden
            ).strip()
            logger.warning("Ağ Kataloğu açılmadı: güvenlik duvarı denetimi geçmedi.")
            if denetim.hata:
                # Denetim OKUNAMADI (ör. PowerShell zaman aşımı): fail-closed kalır ama
                # kendiliğinden yeniden denenir. Kural tutmadıysa yeniden denenmez.
                self._gecici_hata(ENGELLENDI, ileti)
            else:
                self._durum_yaz(ENGELLENDI, son_hata=ileti)
            return

        sunucu: KatalogServer | None = None
        try:
            katalog = self._yukle()
            sunucu = self._kurucu(
                katalog.application,
                host=host,
                port=ayar.port,
                ag_izni=denetim,
            )
            sunucu.start()
            sunucu.wait_until_started()
            self._oz_sinama(sunucu.baglanti_hostu, sunucu.port, signature=katalog.signature)
        except KatalogPortInUseError as exc:
            _durdur_sessiz(sunucu)
            self._port_bekle(exc)
            return
        except KatalogServerError as exc:
            _durdur_sessiz(sunucu)
            logger.warning("%s", exc.full_message)
            self._durum_yaz(HATA, son_hata=exc.message)
            return
        except Exception:  # noqa: BLE001 — katalog hatası programı durdurmaz
            _durdur_sessiz(sunucu)
            logger.exception("Ağ Kataloğu açılırken beklenmeyen hata.")
            self._durum_yaz(
                HATA, son_hata="Ağ Kataloğu açılamadı: beklenmeyen hata (günlüğe bakın)."
            )
            return
        self._sunucu = sunucu
        self._imza = katalog.signature
        self._deneme_bitis = None
        self._gecici_kalan = None
        self._durum_yaz(
            ACIK,
            dinleme_ip=None if tum_arayuzler_mi(host) else host,
            tum_arayuzler=tum_arayuzler_mi(host),
        )
        logger.info("Ağ Kataloğu okul ağında hazır; öz sınama geçti.")

    def _dinleme_adresi(self, ayar: KatalogYapilandirmasi, durum: ag.AgDurumu) -> str:
        if ayar.dinleme_kipi != DINLEME_SECILI:
            return dinleme_hostu(DINLEME_TUM, "")
        if ayar.secili_ip and durum.ip_var_mi(ayar.secili_ip):
            return dinleme_hostu(DINLEME_SECILI, ayar.secili_ip)
        if durum.okunamadi:
            # Yedek yol yalnız varsayılan adresi bilir: seçili IP belki hâlâ buradadır
            # ve "tek aday" başka bir ağdır (ör. öğrenci erişimli ağ). Karar verilmez.
            raise KatalogArayuzOkunamadiError()
        if len(durum.arayuzler) == 1:
            yeni = durum.arayuzler[0].ip
            with self._kilit:
                self._d.uyarilar.append(
                    f"Seçili IP ({ayar.secili_ip or '—'}) bu bilgisayarda artık yok; Ağ Kataloğu "
                    f"yeni adreste ({yeni}) açıldı. Afişi yeniden basın, yer imlerini güncelleyin."
                )
            logger.warning("Seçili IP bu bilgisayarda yok; katalog tek aday adreste açılıyor.")
            return dinleme_hostu(DINLEME_SECILI, yeni)
        raise KatalogAdresYokError()

    def _gecici_hata(self, durum: str, ileti: str) -> None:
        """Okunamayan (geçici) durum: katalog kapalı kalır, gecikmeli yeniden denenir.

        Önce `gecici_deneme_sayisi` kez `gecici_deneme_araligi_sn` arayla, sonra
        saatlik tikte bir kez (`saatlik_denetle`). Kullanıcı eylemi sayacı sıfırlar.
        """
        if self._gecici_kalan is None:
            self._gecici_kalan = self._gecici_sayi
        zamanlayici: threading.Timer | None = None
        if self._gecici_kalan > 0:
            self._gecici_kalan -= 1
            ek = " Kısa süre içinde kendiliğinden yeniden denenecek."
            zamanlayici = threading.Timer(self._gecici_aralik, self._gecici_yeniden_dene)
            zamanlayici.daemon = True
            zamanlayici.name = "kd-katalog-dene"
        else:
            ek = (
                " Saatte bir kendiliğinden yeniden denenir; Ağ Doktoru'ndaki "
                "“Yeniden başlat” ile hemen deneyebilirsiniz."
            )
        self._durum_yaz(durum, son_hata=ileti + ek, gecici=True)
        if zamanlayici is not None:
            self._zamanlayici = zamanlayici
            zamanlayici.start()

    def _gecici_yeniden_dene(self) -> None:
        with self._islem:
            if self._kapanista or self._bakimda:
                return
            with self._kilit:
                gecici = self._d.gecici and self._d.durum in (ENGELLENDI, HATA)
            if not gecici:
                return
            self._uygula_kilitli(yeniden_deneme=True)
        self._uyku_bildir()

    def _port_bekle(self, exc: KatalogPortInUseError) -> None:
        simdi = self._saat()
        if self._deneme_bitis is None:
            self._deneme_bitis = simdi + self._sure
        if simdi >= self._deneme_bitis:
            self._deneme_bitis = None
            self._durum_yaz(HATA, son_hata=exc.message)
            logger.warning("%s", exc.full_message)
            return
        self._durum_yaz(BEKLIYOR, son_hata=exc.message)
        zamanlayici = threading.Timer(self._aralik, self._yeniden_dene)
        zamanlayici.daemon = True
        zamanlayici.name = "kd-katalog-dene"
        self._zamanlayici = zamanlayici
        zamanlayici.start()

    def _yeniden_dene(self) -> None:
        with self._islem:
            if self._kapanista or self._bakimda:
                return
            with self._kilit:
                bekliyor = self._d.durum == BEKLIYOR
            if not bekliyor:
                return
            self._uygula_kilitli(yeniden_deneme=True)
        self._uyku_bildir()


def _durdur_sessiz(sunucu: KatalogServer | None) -> None:
    if sunucu is None:
        return
    try:
        sunucu.stop()
    except Exception:  # noqa: BLE001
        logger.warning("Ağ Kataloğu dinleyicisi kapatılamadı.", exc_info=True)


def yapilandirma(**alanlar: Any) -> KatalogYapilandirmasi:
    """Testler ve teşhis için: varsayılanların üzerine alan yazar."""
    return replace(KatalogYapilandirmasi(), **alanlar)


def ip_listesi(adresler: Sequence[str]) -> list[str]:
    """Kurala gidecek uzak adresler (yardımcı; doğrulama `guvenlik_duvari`'nda)."""
    return guvenlik_duvari.uzak_adresleri_dogrula(adresler)
