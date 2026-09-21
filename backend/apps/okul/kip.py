"""Kip durumu — görevli kipi / yönetici kipi (U5, tasarım §4.4, T16).

Masadaki kişi ayrımı hesapla değil KİPLE yapılır. Kilit açıkken program iki
kipten birindedir: **yönetici kipi** (her şey açık) ya da **görevli kipi**
(yalnız izin listesindeki uçlar açık — `kip_izinleri`, ara katman
`kip_middleware`). Kip durumu süreç içi TEK nesnedir (`KIP`): KipMiddleware,
kip uçları ve F5'te tepsi aynı nesneyi okur (T16; ikinci bir durum kaynağı
açılmaz).

Durumlar (API ve arayüz bu dizeleri kullanır):

* ``kurulum``  — yönetici parolası kurulmamış (`app_password.is_password_set()` yanlış).
* ``guvenlik_dosyasi_kayip`` — parmak izi DB'de dolu ama `guvenlik.json` yok,
  ya da dosya var ama kullanılamıyor (§4.3 GA-2,
  `app_password.security_file_missing`); kilidi açmak mümkün değildir.
* ``kilitli``  — parola kurulu, anahtar bellekte değil.
* ``yonetici`` — kilit açık, yönetici kipi.
* ``gorevli``  — kilit açık, görevli kipi.

``yeniden_baslat`` burada yoktur: geri yükleme sonrası kapı (`restart_gate`)
bütün API'yi 503 ile keser, kip ucu da dahil.

GEÇİŞLER

* Kilit açılışı (parola ya da kurtarma anahtarı) → YÖNETİCİ. Açılış süreç
  içinde `crypto.key_epoch()` sayacının değişmesinden anlaşılır: her
  `load_key`/`unload_key` sayacı artırır. Görülen sayaçtan farklı bir sayaç +
  yüklü anahtar ⇒ yeni açılış ⇒ yönetici kipi, iki sayaç da sıfırdan.
  Böylece kip nesnesinin kilit uçlarına kanca atması gerekmez; kilidi hangi
  yol açarsa açsın (uç, yönetim komutu, geri yükleme) sonuç aynıdır.
* YÖNETİCİ → GÖREVLİ: `gorevliye_gec()` (parolasız) ya da tembel süre dolumu.
* GÖREVLİ → YÖNETİCİ: `yoneticiye_gec(password)`; parola
  `app_password.verify_password` ile doğrulanır.
* Her kipte → KİLİTLİ: mevcut `security/lock/` ucu (`app_password.lock()`);
  anahtar düşünce sayaç değişir, kip nesnesi bunu ayrıca bilmek zorunda değildir.

TEMBEL SÜRE DOLUMU (§4.4 "Boşta dönüş")

Zamanlayıcı iş parçacığı YOKTUR. Durum her sorulduğunda (her API isteğinde
ara katman sorar) YÖNETİCİ iken iki koşul denetlenir; biri doluysa kip
GÖREVLİ'ye iner:

* boşta süre: ``son_etkinlik + bosta_sn`` — `son_etkinlik` yalnız kullanıcı
  eylemi taşıyan isteklerde (`X-KD-Etkinlik` başlığı) `etkinlik()` ile tazelenir;
  durum ve pano sorguları tazelemez (§5.10-14);
* mutlak süre: ``yonetici_baslangic + mutlak_sn`` — etkinlikten bağımsızdır,
  dolunca yönetici parolası yeniden sorulur.

Kalan süre sıfıra ulaştığı anda kip iner (fail-closed: sınır anı görevli
sayılır). Saat enjekte edilebilir; varsayılan `UykuyuSayanSaat`tir.

SAAT: UYKU DA SÜREDİR. Tasarım §4.5 kapak kapatmayı ve kullanıcının başlattığı
uykuyu engellemez. `time.monotonic` Linux'ta (Pardus) `CLOCK_MONOTONIC`tır ve
askıya alınan süreyi SAYMAZ: yönetici kipindeyken uyutulup ertesi sabah
uyandırılan makinede boşta ve mutlak süre, uykudan önce kalan yerden devam
ederdi (denetim bulgusu). `UykuyuSayanSaat` iki kaynağın son okumadan beri
ilerlemesinin BÜYÜĞÜNÜ biriktirir:

* monoton kaynak — Linux'ta `CLOCK_BOOTTIME` (uykuyu sayar), yoksa
  `time.monotonic`; duvar saati geri alınsa da ilerler;
* duvar saati (`time.time`) — uyanışta uyunan süre kadar ileri geçer; paketli
  Python'un Windows'taki monoton saatinin uykuyu sayıp saymadığından bağımsız
  bir güvence.

Duvar saati ileri sıçrarsa süre erken dolar (görevli kipine erken iniş —
fail-closed, yönetici parolayı yeniden girer); geri sıçrarsa monoton ilerleme
kullanılır, süre UZAMAZ.

Ara katman (sıcak yol) `gorevli_mi()` kullanır: yalnız bellekteki anahtara ve
bu nesnenin durumuna bakar, güvenlik dosyasına ve veritabanına dokunmaz. Tam
durum (`durum()`, `ozet()`) kip uçlarında ve tepside sorulur.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal

from apps.okul.services import app_password
from shared import crypto

KipAdi = Literal["kurulum", "kilitli", "guvenlik_dosyasi_kayip", "yonetici", "gorevli"]

KURULUM: Final = "kurulum"
KILITLI: Final = "kilitli"
GUVENLIK_DOSYASI_KAYIP: Final = "guvenlik_dosyasi_kayip"
YONETICI: Final = "yonetici"
GOREVLI: Final = "gorevli"

# §4.4 varsayılanları (GA-9, KM-2): boşta 3 dk, mutlak 30 dk.
VARSAYILAN_BOSTA_DK: Final = 3
VARSAYILAN_MUTLAK_DK: Final = 30


@dataclass(frozen=True)
class KipSureleri:
    """Yönetici kipinin iki süresi (saniye)."""

    bosta_sn: int
    mutlak_sn: int


def kip_sureleri() -> KipSureleri:
    """Yönetici kipi sürelerinin sağlayıcısı.

    F6'da `LibraryPolicy`'ye bağlanacak (iki süre de ayarlanabilir, §4.4);
    o zamana dek tasarım varsayılanları döner. Kip nesnesi sağlayıcıyı her
    değerlendirmede çağırır: ayar değişikliği yeniden başlatma istemez.
    """
    return KipSureleri(bosta_sn=VARSAYILAN_BOSTA_DK * 60, mutlak_sn=VARSAYILAN_MUTLAK_DK * 60)


class KipGecisHatasi(Exception):
    """İstenen kip geçişi mevcut durumda yapılamaz (ör. kilitliyken görevli kipine geçiş)."""

    def __init__(self, message: str, *, durum: str) -> None:
        super().__init__(message)
        self.message = message
        self.durum = durum


GECIS_ICIN_KILIT_ACIK_OLMALI = (
    "Kip yalnız kilit açıkken değiştirilebilir. Önce yönetici parolasıyla kilidi açın."
)


def uykuyu_sayan_monoton_kaynak() -> Callable[[], float]:
    """Uykuyu da sayan monoton kaynak: Linux'ta `CLOCK_BOOTTIME`, yoksa `time.monotonic`."""
    boottime: int | None = getattr(time, "CLOCK_BOOTTIME", None)
    if boottime is None:
        return time.monotonic
    try:
        time.clock_gettime(boottime)
    except OSError:  # pragma: no cover — çok eski çekirdek
        return time.monotonic
    return lambda: time.clock_gettime(boottime)


class UykuyuSayanSaat:
    """Süre ölçümü saati: sistem uykusunu da sayar, geri sıçramada süreyi uzatmaz.

    Her çağrıda monoton kaynağın ve duvar saatinin son çağrıdan beri
    ilerlemesinin BÜYÜĞÜ (negatifse 0) birikime eklenir (gerekçe modül
    başlığında). Değer yalnız farklar için anlamlıdır ve hiç azalmaz. İş
    parçacığı güvenlidir.
    """

    def __init__(
        self,
        *,
        monoton: Callable[[], float] | None = None,
        duvar: Callable[[], float] = time.time,
    ) -> None:
        self._monoton = monoton if monoton is not None else uykuyu_sayan_monoton_kaynak()
        self._duvar = duvar
        self._kilit = threading.Lock()
        self._son_monoton = self._monoton()
        self._son_duvar = self._duvar()
        self._birikim = 0.0

    def __call__(self) -> float:
        with self._kilit:
            monoton = self._monoton()
            duvar = self._duvar()
            adim = max(monoton - self._son_monoton, duvar - self._son_duvar, 0.0)
            self._son_monoton = monoton
            self._son_duvar = duvar
            self._birikim += adim
            return self._birikim


class KipDurumu:
    """Süreç içi kip durumu (T16). İş parçacığı güvenlidir (RLock).

    `saat` ve `sureler` testte taklit edilir; üretimde varsayılanlar kullanılır
    (saat verilmezse her nesneye yeni bir `UykuyuSayanSaat`).
    """

    def __init__(
        self,
        *,
        saat: Callable[[], float] | None = None,
        sureler: Callable[[], KipSureleri] = kip_sureleri,
    ) -> None:
        self._kilit = threading.RLock()
        self._saat: Callable[[], float] = saat if saat is not None else UykuyuSayanSaat()
        self._sureler = sureler
        self._gorevli = False
        self._son_etkinlik = 0.0
        self._yonetici_baslangic = 0.0
        # Son görülen `crypto.key_epoch()`; None = henüz hiç açılış görülmedi.
        self._gorulen_epoch: int | None = None

    # ------------------------------------------------------------ iç yardımcılar
    def _yoneticiye_ata(self, simdi: float) -> None:
        self._gorevli = False
        self._son_etkinlik = simdi
        self._yonetici_baslangic = simdi

    def _kip_hesapla(self, simdi: float) -> KipAdi:
        """Kilit AÇIKKEN yönetici/görevli kararı (epoch + tembel süre dolumu).

        Çağıran kilidi tutar ve anahtarın yüklü olduğunu doğrulamıştır.
        """
        epoch = crypto.key_epoch()
        if epoch != self._gorulen_epoch:
            # Yeni kilit açılışı: yönetici kipi, iki sayaç da sıfırdan.
            self._gorulen_epoch = epoch
            self._yoneticiye_ata(simdi)
            return YONETICI
        if self._gorevli:
            return GOREVLI
        sureler = self._sureler()
        if (
            simdi - self._son_etkinlik >= sureler.bosta_sn
            or simdi - self._yonetici_baslangic >= sureler.mutlak_sn
        ):
            self._gorevli = True
            return GOREVLI
        return YONETICI

    def _durum_hesapla(self, simdi: float) -> KipAdi:
        if not app_password.is_password_set():
            return KURULUM
        if app_password.security_file_missing():
            return GUVENLIK_DOSYASI_KAYIP
        if not crypto.is_unlocked():
            return KILITLI
        return self._kip_hesapla(simdi)

    # ------------------------------------------------------------ sorgular
    def durum(self) -> KipAdi:
        """Tam durum (kurulum/kayıp/kilitli dahil). Süre dolumunu da uygular."""
        with self._kilit:
            return self._durum_hesapla(self._saat())

    def gorevli_mi(self) -> bool:
        """Ara katmanın sıcak yolu: kilit açık VE kip görevli mi?

        Güvenlik dosyasına ve veritabanına bakmaz (her API isteğinde çağrılır).
        Kilitli durum zaten kilit kapısında (423) kesilir. Kayıp durumda kilit
        kapısı çıkış yollarını (yedek listesi, geri yükleme) geçirir; kip kapısı
        bu yüzden RED yolunda dosya kaybını ayrıca sorar (`kip_middleware`).
        """
        with self._kilit:
            if not crypto.is_unlocked():
                return False
            return self._kip_hesapla(self._saat()) == GOREVLI

    def ozet(self) -> dict[str, Any]:
        """`GET security/mode/` yanıtı. Kalan süreler yalnız yönetici kipinde doludur.

        Arayüzdeki geri sayım yalnız GÖRSELDİR; karar her istekte sunucuda verilir.
        """
        with self._kilit:
            simdi = self._saat()
            durum = self._durum_hesapla(simdi)
            sureler = self._sureler()
            bosta_kalan: int | None = None
            mutlak_kalan: int | None = None
            if durum == YONETICI:
                bosta_kalan = _kalan_sn(self._son_etkinlik + sureler.bosta_sn - simdi)
                mutlak_kalan = _kalan_sn(self._yonetici_baslangic + sureler.mutlak_sn - simdi)
            return {
                "durum": durum,
                "bosta_kalan_sn": bosta_kalan,
                "mutlak_kalan_sn": mutlak_kalan,
                "bosta_dk": _dakika(sureler.bosta_sn),
                "mutlak_dk": _dakika(sureler.mutlak_sn),
            }

    # ------------------------------------------------------------ geçişler
    def etkinlik(self) -> None:
        """Kullanıcı eylemi: yönetici kipindeyse boşta sayacını tazeler.

        Önce süre dolumu uygulanır: süresi dolmuş yönetici kipi, geç gelen bir
        etkinlikle DİRİLMEZ (§5.10-14). Görevli ya da kilitliyken etkisizdir.
        """
        with self._kilit:
            if not crypto.is_unlocked():
                return
            simdi = self._saat()
            if self._kip_hesapla(simdi) == YONETICI:
                self._son_etkinlik = simdi

    def gorevliye_gec(self) -> KipAdi:
        """Yönetici kipinden görevli kipine geçer (parolasız, §4.4).

        Görevli kipindeyken fikirdeştir (tepsi komutu iki kez gelebilir).
        Kilitli, kurulum ya da kayıp durumunda `KipGecisHatasi` yükseltir.
        """
        with self._kilit:
            durum = self._durum_hesapla(self._saat())
            if durum not in (YONETICI, GOREVLI):
                raise KipGecisHatasi(GECIS_ICIN_KILIT_ACIK_OLMALI, durum=durum)
            self._gorevli = True
            return GOREVLI

    def yoneticiye_gec(self, password: str) -> KipAdi:
        """Yönetici parolasıyla yönetici kipine geçer; iki sayaç sıfırdan başlar.

        Yönetici kipindeyken de çalışır (parolayı yeniden girmek mutlak süreyi
        yeniler). Yanlış parolada `app_password.AppPasswordError` ("Parola
        hatalı.") yükselir ve servisin kademeli gecikmesi uygulanır. Parola
        doğrulaması (Argon2id) kilit TUTULMADAN yapılır: yavaş işlem diğer
        isteklerin kip sorgusunu bekletmesin.
        """
        with self._kilit:
            durum = self._durum_hesapla(self._saat())
        if durum not in (YONETICI, GOREVLI):
            raise KipGecisHatasi(GECIS_ICIN_KILIT_ACIK_OLMALI, durum=durum)
        app_password.verify_password(password)
        with self._kilit:
            # Doğrulama sürerken program kilitlenmiş olabilir: yeniden bak.
            durum = self._durum_hesapla(self._saat())
            if durum not in (YONETICI, GOREVLI):
                raise KipGecisHatasi(GECIS_ICIN_KILIT_ACIK_OLMALI, durum=durum)
            self._yoneticiye_ata(self._saat())
            return YONETICI

    # ------------------------------------------------------------ test desteği
    def _reset_for_tests(
        self,
        *,
        saat: Callable[[], float] | None = None,
        sureler: Callable[[], KipSureleri] | None = None,
    ) -> None:
        """Yalnız testler için: tekil süreç içi olduğundan durum testler arasında sızar."""
        with self._kilit:
            self._saat = saat if saat is not None else UykuyuSayanSaat()
            self._sureler = sureler if sureler is not None else kip_sureleri
            self._gorevli = False
            self._son_etkinlik = 0.0
            self._yonetici_baslangic = 0.0
            self._gorulen_epoch = None


def _kalan_sn(deger: float) -> int:
    # Yuvarlama kayan nokta artığını siler: (t + 180) - t = 180.00000000003 → 181 olmasın.
    return max(0, math.ceil(round(deger, 3)))


def _dakika(saniye: int) -> int:
    return saniye // 60


# Süreç içi TEK kip nesnesi (T16).
KIP = KipDurumu()
