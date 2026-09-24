"""Gün değişimi kapısı (T9, §5.10-17) ve uyku engelleme (§4.5).

§5.10-17: program 3 gün kapanmadan açık kalır; her gün bir yedek alınır, IP
denetlenir (saat taklidiyle). Taklit iki katmanlıdır: GÜN sağlayıcı elle
ilerletilir, kapı saatte bir tetiklenir. Yedek GERÇEKTİR (şifreli `.kdbak`,
`desktop.backup`) ve rotasyon da koşar; IP denetimi gerçek katalog denetçisinin
(`KatalogKontrol.ip_denetle`) kendisidir, ağ durumu taklittir.

Uyku: Windows'ta `SetThreadExecutionState` iş parçacığına bağlıdır; çağrının
YALNIZ `kd-gunluk`'tan yapıldığı ve kapanışta temizlendiği sınanır.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from desktop import ag, gunluk
from desktop import katalog_kontrol as kk
from desktop import main as main_mod
from desktop.gunluk import GunDegisimiKapisi
from desktop.paths import ENV_APP_HOME, resolve_app_paths
from desktop.tests.test_backup import _db_olustur


class _Gun:
    """Elle ilerletilen yerel gün (saat taklidi)."""

    def __init__(self, baslangic: date) -> None:
        self.gun = baslangic

    def __call__(self) -> date:
        return self.gun


@contextmanager
def _izinli() -> Iterator[bool]:
    yield True


def _ekle(liste: list[Any], deger: Any) -> bool:
    """İş taklidi: değeri kaydeder ve işi başarılı sayar."""
    liste.append(deger)
    return True


def _kapi(tmp_path: Path, gun: _Gun, **kw: Any) -> GunDegisimiKapisi:
    kw.setdefault("bakim_girisi", _izinli)
    kw.setdefault("baglanti_kapatici", lambda: None)
    return GunDegisimiKapisi(damga_yolu=tmp_path / "data" / gunluk.DAMGA_DOSYASI, bugun=gun, **kw)


# ------------------------------------------------------------ §5.10-17


def test_uc_gun_acik_kalan_program_her_gun_bir_yedek_alir_ve_ip_denetler(tmp_path: Path) -> None:
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    paths.ensure()
    _db_olustur(paths.db_path)
    gun = _Gun(date(2026, 9, 24))
    agdaki = ["192.168.10.5"]
    kontrol = kk.KatalogKontrol(
        ayar_okuyucu=lambda: kk.yapilandirma(acik=False, son_afis_ip="192.168.10.5"),
        ayar_yazici=None,
        ag_saglayici=lambda: ag.AgDurumu(
            arayuzler=(ag.Arayuz("Ethernet", agdaki[0], 24, True),), kaynak="test"
        ),
    )
    ip_denetimleri: list[date] = []

    def ip_denetle() -> bool:
        ip_denetimleri.append(gun())
        return kontrol.ip_denetle()

    kapi = _kapi(paths.root, gun)
    kapi.kaydet("gunluk-yedek", main_mod.gunluk_yedek_isi(paths, bugun=gun))
    kapi.kaydet("ip-denetimi", ip_denetle)

    # Açılış + 72 saat, saatte bir geçiş (kapının `kd-gunluk` döngüsünün yaptığı).
    baslangic = gun.gun
    for saat in range(0, 73):
        gun.gun = baslangic + timedelta(hours=saat) // timedelta(days=1) * timedelta(days=1)
        if saat == 30:
            agdaki[0] = "192.168.10.77"  # ikinci gün DHCP adresi değiştirdi
        kapi.tik()

    yedekler = sorted(p.name for p in paths.backups.glob("gunluk-*.kdbak"))
    assert yedekler == [
        "gunluk-2026-09-24.kdbak",
        "gunluk-2026-09-25.kdbak",
        "gunluk-2026-09-26.kdbak",
        "gunluk-2026-09-27.kdbak",
    ]
    # Her gün bir kez: dört takvim günü (24 → 27) = dört denetim, saatlik geçişler tekrar etmez.
    assert ip_denetimleri == [date(2026, 9, 24) + timedelta(days=i) for i in range(4)]
    uyarilar = kontrol.durum()["uyarilar"]
    assert any("Afişi yeniden basın, yer imlerini güncelleyin." in u for u in uyarilar)
    damga = json.loads((paths.data / gunluk.DAMGA_DOSYASI).read_text(encoding="utf-8"))
    assert damga == {
        "surum": 1,
        "isler": {"gunluk-yedek": "2026-09-27", "ip-denetimi": "2026-09-27"},
    }


def test_yedek_alinamazsa_damga_yazilmaz_ve_saatte_bir_yeniden_denenir(tmp_path: Path) -> None:
    """Yönetici parolası kurulmadan yedek atlanır; rotasyon da koşmaz (GA-2)."""
    paths = resolve_app_paths(environ={ENV_APP_HOME: str(tmp_path)})
    paths.ensure()
    _db_olustur(paths.db_path, parola_kurulu=False)
    eski = paths.backups / "gunluk-2026-01-01.kdbak"
    eski.write_bytes(b"eski")
    gun = _Gun(date(2026, 9, 24))
    kapi = _kapi(paths.root, gun)
    kapi.kaydet("gunluk-yedek", main_mod.gunluk_yedek_isi(paths, bugun=gun))

    assert kapi.tik() == []
    assert kapi.tik() == []  # bir saat sonra yeniden denendi
    assert eski.exists()  # rotasyon koşmadı
    assert kapi.damgalar() == {}

    ensure_parola(paths.data)
    assert kapi.tik() == ["gunluk-yedek"]
    assert not eski.exists()  # bugünün yedeği alındı, rotasyon koştu


def ensure_parola(veri: Path) -> None:
    from desktop.backup_crypto import ensure_public_config
    from desktop.tests.test_backup import _GUVENLIK, _TEST_KEY

    ensure_public_config(veri, _TEST_KEY)
    (veri / "guvenlik.json").write_bytes(_GUVENLIK)


def test_bir_isin_hatasi_otekileri_durdurmaz(tmp_path: Path) -> None:
    gun = _Gun(date(2026, 9, 24))
    kapi = _kapi(tmp_path, gun)
    cagrilar: list[str] = []

    def patla() -> bool:
        cagrilar.append("patla")
        raise RuntimeError("beklenmedik")

    kapi.kaydet("patlayan", patla)
    kapi.kaydet("saglam", lambda: _ekle(cagrilar, "saglam"))

    assert kapi.tik() == ["saglam"]
    assert kapi.tik() == []  # sağlam iş bugün yapıldı; patlayan yeniden denendi
    assert cagrilar == ["patla", "saglam", "patla"]


def test_none_donen_is_yapilmis_sayilir(tmp_path: Path) -> None:
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))
    kapi.kaydet("sessiz", lambda: None)

    assert kapi.tik() == ["sessiz"]


def test_bakimdayken_is_baslamaz(tmp_path: Path) -> None:
    """Geri yükleme sürerken ortak bakım kapısı kapalıdır (§5.3-4)."""

    @contextmanager
    def bakimda() -> Iterator[bool]:
        yield False

    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)), bakim_girisi=bakimda)
    cagrilar: list[str] = []
    kapi.kaydet("yedek", lambda: _ekle(cagrilar, "yedek"))

    assert kapi.tik() == []
    assert cagrilar == []


def test_gercek_bakim_kapisi_ile_is_uçusta_sayilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "backend"))
    from katalog.bakim import BakimKapisi

    kapi_nesnesi = BakimKapisi()
    goruldu: list[int] = []
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)), bakim_girisi=kapi_nesnesi.is_)
    kapi.kaydet("sayac", lambda: _ekle(goruldu, kapi_nesnesi.ucusta))

    assert kapi.tik() == ["sayac"]
    assert goruldu == [1]
    assert kapi_nesnesi.ucusta == 0


def test_her_isten_sonra_is_parcaciginin_baglantilari_kapatilir(tmp_path: Path) -> None:
    kapatma: list[str] = []
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)), baglanti_kapatici=lambda: kapatma.append("x"))
    kapi.kaydet("a", lambda: True)
    kapi.kaydet("b", lambda: False)

    kapi.tik()

    assert kapatma == ["x", "x"]


def test_saatlik_is_her_tikte_damgasiz_kosar(tmp_path: Path) -> None:
    """Günlük iş günde bir, saatlik iş her tikte (damga yazılmaz)."""
    gun = _Gun(date(2026, 9, 24))
    kapi = _kapi(tmp_path, gun)
    gunluk_sayac: list[int] = []
    saatlik_sayac: list[int] = []

    def sayan(sayac: list[int]) -> Callable[[], bool]:
        def calistir() -> bool:
            sayac.append(1)
            return True

        return calistir

    kapi.kaydet("gunluk", sayan(gunluk_sayac))
    kapi.saatlik_kaydet("saatlik", sayan(saatlik_sayac))

    for _ in range(3):
        kapi.tik()

    assert len(gunluk_sayac) == 1
    assert len(saatlik_sayac) == 3
    assert "saatlik" not in kapi.damgalar()
    with pytest.raises(ValueError):
        kapi.saatlik_kaydet("saatlik-ı", lambda: True)


def test_acik_kalma_saati_ilerler_ve_duvar_saatinden_bagimsizdir() -> None:
    once = gunluk.acik_kalma_saati()
    sonra = gunluk.acik_kalma_saati()

    assert once > 0 and sonra >= once


def test_is_adi_ascii_olmali(tmp_path: Path) -> None:
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))

    with pytest.raises(ValueError):
        kapi.kaydet("günlük", lambda: True)


def test_bozuk_damga_dosyasi_bos_sayilir(tmp_path: Path) -> None:
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / gunluk.DAMGA_DOSYASI).write_text("{bozuk", encoding="utf-8")

    assert kapi.damgalar() == {}


def test_backend_isleri_kanca_listesinden_eklenir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys
    import types

    sahte = types.ModuleType("apps.okul.masaustu_kanca")
    sahte.gunluk_isler = lambda: (gunluk.IsKaydi("cok-okunanlar", lambda: True),)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apps.okul.masaustu_kanca", sahte)
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))

    assert kapi.backend_islerini_ekle() == 1
    assert kapi.is_adlari == ("cok-okunanlar",)


# ------------------------------------------------------ kd-gunluk iş parçacığı


def test_is_parcacigi_acilista_ilk_isi_sonra_kapiyi_kosar_ve_saatlik_yineler(
    tmp_path: Path,
) -> None:
    gun = _Gun(date(2026, 9, 24))
    saat = [0.0]
    olaylar: list[tuple[str, str]] = []
    kapi = _kapi(tmp_path, gun, aralik_sn=3600.0, monoton=lambda: saat[0])
    kapi.kaydet("is", lambda: _ekle(olaylar, ("is", threading.current_thread().name)))

    kapi.baslat(ilk_is=lambda: olaylar.append(("ilk", threading.current_thread().name)))
    _bekle(lambda: len(olaylar) >= 2)
    assert olaylar == [("ilk", "kd-gunluk"), ("is", "kd-gunluk")]

    # Uyandırma saatlik takvimi kaydırmaz, gün değişse de tik saat dolmadan koşmaz.
    gun.gun = date(2026, 9, 25)
    kapi.uyandir()
    time.sleep(0.1)
    assert len(olaylar) == 2

    saat[0] = 3601.0  # bir saat geçti
    kapi.uyandir()
    _bekle(lambda: len(olaylar) >= 3)
    assert olaylar[-1] == ("is", "kd-gunluk")
    kapi.durdur()


def test_ilk_is_hatasi_kapiyi_dusurmez(tmp_path: Path) -> None:
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))
    olaylar: list[str] = []
    kapi.kaydet("is", lambda: _ekle(olaylar, "is"))

    def patla() -> None:
        raise RuntimeError("katalog açılamadı")

    kapi.baslat(ilk_is=patla)
    _bekle(lambda: olaylar == ["is"])
    kapi.durdur()


def test_iki_kez_baslatilamaz(tmp_path: Path) -> None:
    kapi = _kapi(tmp_path, _Gun(date(2026, 9, 24)))
    kapi.baslat()
    try:
        with pytest.raises(RuntimeError):
            kapi.baslat()
    finally:
        kapi.durdur()


def _bekle(kosul: Any, sure: float = 5.0) -> None:
    son = time.monotonic() + sure
    while not kosul() and time.monotonic() < son:
        time.sleep(0.01)
    assert kosul()


# ------------------------------------------------------------------ uyku


class _Api:
    """`SetThreadExecutionState` taklidi: çağıran iş parçacığını kaydeder."""

    def __init__(self) -> None:
        self.cagrilar: list[tuple[int, str]] = []

    def __call__(self, bayraklar: int) -> int:
        self.cagrilar.append((bayraklar, threading.current_thread().name))
        return 1


def test_windows_uyku_engeli_yalniz_kd_gunluk_tan_ve_kapanista_temizlenir(tmp_path: Path) -> None:
    api = _Api()
    gerekli = [False]
    kapi = _kapi(
        tmp_path,
        _Gun(date(2026, 9, 24)),
        uyku=gunluk.WindowsUyku(api=api),
        uyku_gerekli=lambda: gerekli[0],
    )

    kapi.baslat()
    time.sleep(0.05)
    assert api.cagrilar == []  # katalog kapalı: engel yok

    gerekli[0] = True  # katalog açıldı; denetçi kapıyı uyandırır
    kapi.uyandir()
    _bekle(lambda: len(api.cagrilar) == 1)
    kapi.durdur()

    engel = gunluk.ES_CONTINUOUS | gunluk.ES_SYSTEM_REQUIRED
    assert api.cagrilar == [(engel, "kd-gunluk"), (gunluk.ES_CONTINUOUS, "kd-gunluk")]
    assert engel == 0x80000001


def test_windows_uyku_ayni_duruma_ikinci_kez_cagri_yapmaz() -> None:
    api = _Api()
    uyku = gunluk.WindowsUyku(api=api)

    uyku.ayarla(True)
    uyku.ayarla(True)
    uyku.ayarla(False)
    uyku.birak()

    assert [b for b, _ in api.cagrilar] == [0x80000001, 0x80000000]


class _Girdi:
    def __init__(self) -> None:
        self.kapandi = False

    def close(self) -> None:
        self.kapandi = True


class _Surec:
    def __init__(self, argv: list[str], **kw: Any) -> None:
        self.argv = argv
        self.kw = kw
        self.stdin = _Girdi()
        self.sonlandi = False

    def terminate(self) -> None:
        self.sonlandi = True

    def wait(self, timeout: float) -> int:
        return 0


def test_linux_uyku_systemd_inhibit_yalniz_bosta_kalmayi_engeller() -> None:
    surecler: list[_Surec] = []

    def popen(argv: list[str], **kw: Any) -> _Surec:
        surecler.append(_Surec(argv, **kw))
        return surecler[-1]

    uyku = gunluk.LinuxUyku(which=lambda ad: f"/usr/bin/{ad}", popen=popen)

    uyku.ayarla(True)
    uyku.ayarla(True)  # ikinci süreç açılmaz
    assert uyku.engelli is True
    uyku.ayarla(False)

    (surec,) = surecler
    assert surec.argv[:3] == ["/usr/bin/systemd-inhibit", "--what=idle", "--mode=block"]
    assert "sleep" not in " ".join(surec.argv[1:3])  # kullanıcının başlattığı uyku engellenmez
    assert surec.stdin.kapandi is True  # önce boru kapanır (cat EOF alır)
    assert surec.sonlandi is True
    assert uyku.engelli is False


def test_linux_uyku_engeli_ana_surecin_omrune_baglidir() -> None:
    """Bulgu: `sleep infinity` program düzensiz biterse (çöküş, SIGKILL) yetim kalırdı.

    Engelleyici `cat` ile programa ait borudan okur: program ölünce boru kapanır,
    `cat` EOF alır, systemd-inhibit biter. Süresiz uyku komutu hiç kullanılmaz.
    """
    import subprocess

    surecler: list[_Surec] = []

    def popen(argv: list[str], **kw: Any) -> _Surec:
        surecler.append(_Surec(argv, **kw))
        return surecler[-1]

    gunluk.LinuxUyku(which=lambda ad: f"/usr/bin/{ad}", popen=popen).ayarla(True)

    (surec,) = surecler
    assert surec.argv[-1] == "/usr/bin/cat"
    assert "infinity" not in surec.argv and not any("sleep" in a for a in surec.argv)
    assert surec.kw["stdin"] is subprocess.PIPE
    assert surec.kw.get("close_fds", True) is True


def test_linux_uyku_engeli_gercek_surecte_boru_kapaninca_biter(tmp_path: Path) -> None:
    """Gerçek alt süreçle: `systemd-inhibit` yerine geçen sarmal `cat`'i çalıştırır."""
    import shutil
    import stat
    import subprocess

    cat = shutil.which("cat")
    if cat is None:
        pytest.skip("cat yok")
    sarmal = tmp_path / "systemd-inhibit"
    sarmal.write_text('#!/bin/sh\nfor a; do last="$a"; done\nexec "$last"\n', encoding="utf-8")
    sarmal.chmod(sarmal.stat().st_mode | stat.S_IEXEC)
    surecler: list[Any] = []

    def popen(argv: list[str], **kw: Any) -> Any:
        surecler.append(subprocess.Popen(argv, **kw))  # noqa: S603 — sabit test sarmalı
        return surecler[-1]

    uyku = gunluk.LinuxUyku(
        which=lambda ad: str(sarmal) if ad == "systemd-inhibit" else cat, popen=popen
    )
    uyku.ayarla(True)
    (surec,) = surecler
    assert surec.poll() is None  # boru açıkken engel sürer

    surec.stdin.close()  # ana süreç ölünce olan budur: yazma ucu kapanır
    assert surec.wait(timeout=5) == 0


def test_linux_uyku_systemd_inhibit_yoksa_sessizce_gecer() -> None:
    uyku = gunluk.LinuxUyku(which=lambda ad: None)

    uyku.ayarla(True)

    assert uyku.engelli is False


def test_platforma_gore_uyku_engelleyici() -> None:
    assert isinstance(gunluk.uyku_engelleyici("win32"), gunluk.WindowsUyku)
    assert isinstance(gunluk.uyku_engelleyici("linux"), gunluk.LinuxUyku)
    assert isinstance(gunluk.uyku_engelleyici("darwin"), gunluk.BosUyku)
