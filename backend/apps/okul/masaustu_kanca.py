"""Masaüstü kancaları — backend ile masaüstü kabuğu arasındaki TEK kanal (T16).

Program tek süreçtir: Django (yönetim API'si), Ağ Kataloğu dinleyicisi, tepsi ve
`kd-gunluk` aynı süreçte koşar. Tepsi ve katalog sunucusu HTTP dışında kalır;
backend onlara bir HTTP ucuyla değil, masaüstü kabuğunun açılışta buraya
KAYDETTİĞİ nesnelerle ulaşır (tasarım T16, GA-8, UY-17). Böylece ikinci bir
durum kaynağı ya da tanımsız bir kontrol kanalı doğmaz:

* **Katalog kontrolü** (`desktop/katalog_kontrol.py::KatalogKontrol`): Ağ
  Doktoru ve Ayarlar → Ağ Kataloğu ekranı katalogu bu nesne üzerinden açar,
  kapatır, yeniden başlatır; durumu, son hatayı, güvenlik duvarı denetiminin
  beş maddesini ve IP adaylarını buradan okur. Geri yükleme (`live_restore`)
  takastan önce katalogu buradan bakım kapısına alır.
* **Çıkış** (`POST app/quit/`, `views_app.py`): düzenli kapanışı başlatan
  çağrılabilir; masaüstünde pencere denetçisinin "Çık" yoludur (tepsi, kanal
  ve kurucunun kapatma olayıyla aynı yol).
* **Gün değişimi işleri** (T9): backend'deki bir işin (ör. F6/F10 çok
  okunanlar yazıcısı) masaüstünün `kd-gunluk` kapısına girmesi için buraya
  kaydolması yeter; kapı açılışta bu listeyi okur. Masaüstü modüllerini
  backend'den içe aktarmak gerekmez.

Kanca yoksa (geliştirme sunucusu, testler) işlevler "yok" der; çağıran uç bunu
kullanıcıya Türkçe iletiyle bildirir (ör. 503). Kayıt süreç içidir ve
açılışta bir kez yapılır; `_reset_for_tests` yalnız testler içindir.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class KatalogKontrolu(Protocol):
    """Masaüstündeki katalog denetçisinin backend'e açtığı yüzey (T16).

    Bütün yöntemler Türkçe, kişisel veri içermeyen sözlükler döndürür; hata
    istisna olarak değil `son_hata` alanıyla bildirilir (kontrol ekranı durumu
    her yanıtta yeniden çizer).
    """

    def durum(self) -> dict[str, Any]: ...

    def ac(self) -> dict[str, Any]: ...

    def kapat(self) -> dict[str, Any]: ...

    def yeniden_baslat(self) -> dict[str, Any]: ...

    def guvenlik_duvari(self) -> dict[str, Any]: ...

    def ip_adaylari(self) -> dict[str, Any]: ...

    def dinleyici_sinamasi(self) -> dict[str, Any]: ...

    def kural_guncelle(self, *, port: int, uzak_adresler: list[str]) -> dict[str, Any]: ...

    def bakima_al(self) -> None: ...

    def bakimdan_cik(self) -> None: ...


GunlukIs = Callable[[], bool | None]


@dataclass(frozen=True)
class GunlukIsKaydi:
    """Gün değişimi kapısına backend'den kaydolan iş (T9)."""

    ad: str
    calistir: GunlukIs


_kilit = threading.Lock()
_katalog: KatalogKontrolu | None = None
_cikis: Callable[[], None] | None = None
_gunluk_isler: dict[str, GunlukIsKaydi] = {}


def kaydet(
    *,
    katalog: KatalogKontrolu | None = None,
    cikis: Callable[[], None] | None = None,
) -> None:
    """Masaüstü kabuğu açılışta kancalarını kaydeder (verilmeyen kanca değişmez)."""
    global _katalog, _cikis
    with _kilit:
        if katalog is not None:
            _katalog = katalog
        if cikis is not None:
            _cikis = cikis


def kaldir() -> None:
    """Kapanışta kancaları bırakır: kapanan sunucuya istek yönlendirilmez."""
    global _katalog, _cikis
    with _kilit:
        _katalog = None
        _cikis = None


def katalog_kontrolu() -> KatalogKontrolu | None:
    """Kayıtlı katalog denetçisi; masaüstü dışında `None`."""
    with _kilit:
        return _katalog


def cikis_iste() -> bool:
    """Düzenli kapanışı başlatır; kanca yoksa `False` (masaüstü dışında çalışıyor).

    Kanca ENGELLEMEZ: kapanış ayrı bir iş parçacığında sürer, bu çağrıyı yapan
    HTTP isteği yanıtını gönderebilir.
    """
    with _kilit:
        cikis = _cikis
    if cikis is None:
        return False
    cikis()
    return True


def katalog_bakima_al() -> None:
    """Geri yükleme: katalog bakım kapısına alınır ve kapanır (§5.3). Kanca yoksa etkisiz."""
    kontrol = katalog_kontrolu()
    if kontrol is not None:
        kontrol.bakima_al()


def katalog_bakimdan_cik() -> None:
    """Geri yükleme BAŞARISIZ oldu: katalog eski hâline döner. Kanca yoksa etkisiz."""
    kontrol = katalog_kontrolu()
    if kontrol is not None:
        kontrol.bakimdan_cik()


def gunluk_is_kaydet(ad: str, calistir: GunlukIs) -> None:
    """Gün değişimi kapısına iş kaydeder (T9). Aynı adla ikinci kayıt öncekinin yerine geçer.

    İş günde bir kez, kapının `kd-gunluk` iş parçacığında koşar. `True` ya da
    `None` dönerse o günün işi yapılmış sayılır; `False` dönerse ya da istisna
    yükseltirse bir saat sonra yeniden denenir. İş kendi veritabanı
    bağlantısını `finally` içinde kapatmakla yükümlü değildir: kapı her işten
    sonra iş parçacığının bağlantılarını kapatır.
    """
    if not ad or not ad.isascii():
        raise ValueError("Gün değişimi işinin adı ASCII ve boş olmayan bir dize olmalı.")
    with _kilit:
        _gunluk_isler[ad] = GunlukIsKaydi(ad=ad, calistir=calistir)


def gunluk_isler() -> tuple[GunlukIsKaydi, ...]:
    """Kayıtlı gün değişimi işleri (kayıt sırasıyla)."""
    with _kilit:
        return tuple(_gunluk_isler.values())


def _reset_for_tests() -> None:
    """Yalnız testler için: kayıt süreç içi olduğundan testler arasında sızar."""
    global _katalog, _cikis
    with _kilit:
        _katalog = None
        _cikis = None
        _gunluk_isler.clear()
