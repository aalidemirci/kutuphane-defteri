"""Tek-instance kilidi testleri (tasarım §4.2 — ikinci kopya pencere AÇMAZ)."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop.errors import AlreadyRunningError
from desktop.lock import (
    APP_MUTEX_NAMES,
    SingleInstanceLock,
    is_instance_running,
    signal_running_instance,
)


def test_kilit_alinir_ve_dosya_olusur(tmp_path: Path) -> None:
    lock = SingleInstanceLock(tmp_path / "alt" / "instance.lock")

    lock.acquire()
    try:
        assert (tmp_path / "alt" / "instance.lock").is_file()
    finally:
        lock.release()


def test_ikinci_kopya_reddedilir_turkce_mesajla(tmp_path: Path) -> None:
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ikinci = SingleInstanceLock(tmp_path / "instance.lock")

    ilk.acquire()
    try:
        with pytest.raises(AlreadyRunningError) as hata:
            ikinci.acquire()
    finally:
        ilk.release()

    assert "zaten çalışıyor" in str(hata.value)


def test_birakildiktan_sonra_yeniden_alinabilir(tmp_path: Path) -> None:
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ilk.acquire()
    ilk.release()

    ikinci = SingleInstanceLock(tmp_path / "instance.lock")
    ikinci.acquire()
    ikinci.release()


def test_context_manager_cikista_birakir(tmp_path: Path) -> None:
    yol = tmp_path / "instance.lock"

    with SingleInstanceLock(yol):
        with pytest.raises(AlreadyRunningError):
            SingleInstanceLock(yol).acquire()

    # `with` bloğu bitti → kilit serbest
    SingleInstanceLock(yol).acquire()


def test_release_kilit_alinmadan_cagrilabilir(tmp_path: Path) -> None:
    SingleInstanceLock(tmp_path / "instance.lock").release()


def test_ikinci_acquire_dosya_tanitici_sizdirmaz(tmp_path: Path) -> None:
    """Reddedilen kilit denemesi açık dosyayı kapatmalı (Windows'ta dosya kilidi kalır)."""
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    ilk.acquire()
    ikinci = SingleInstanceLock(tmp_path / "instance.lock")
    try:
        for _ in range(50):
            with pytest.raises(AlreadyRunningError):
                ikinci.acquire()
            assert ikinci.handle is None
    finally:
        ilk.release()


# --------------------------------------------------------- Windows mutex'leri (§2.3)


class _MutexKaydi:
    """Windows mutex yaratıcısının sahtesi: istenen adları ve tanıtıcıları tutar."""

    def __init__(self, basarisiz: frozenset[str] = frozenset()) -> None:
        self.adlar: list[str] = []
        self._basarisiz = basarisiz

    def __call__(self, ad: str) -> int | None:
        self.adlar.append(ad)
        return None if ad in self._basarisiz else 100 + len(self.adlar)


def test_windows_ta_iki_mutex_acilir(tmp_path: Path) -> None:
    kayit = _MutexKaydi()
    kilit = SingleInstanceLock(tmp_path / "instance.lock", platform="win32", mutex_creator=kayit)

    kilit.acquire()
    try:
        assert kayit.adlar == ["KutuphaneDefteri", r"Global\KutuphaneDefteri"]
        assert kilit.mutex_handles == (101, 102)
    finally:
        kilit.release()


def test_mutex_adlari_kurucuyla_ayni() -> None:
    """Kurucunun `[Code]` beklemesi aynı iki adı arar (kutuphane-defteri.iss)."""
    iss = (
        Path(__file__).resolve().parents[2] / "packaging" / "windows" / "kutuphane-defteri.iss"
    ).read_text(encoding="utf-8")

    assert APP_MUTEX_NAMES == ("KutuphaneDefteri", r"Global\KutuphaneDefteri")
    assert r"ProgramMutexleri = 'KutuphaneDefteri,Global\KutuphaneDefteri';" in iss
    # AppMutex KULLANILMAZ (tasarım §2.3, §4.2-5): kaldırıcı olayı göndermeden beklerdi.
    assert not any(satir.startswith("AppMutex=") for satir in iss.splitlines())


def test_mutexler_kilit_birakilinca_kapatilmaz(tmp_path: Path) -> None:
    """Mutex süreç bitene dek yaşar; kurucu çıkmakta olan sürecin dosyalarına yazmasın."""
    kayit = _MutexKaydi()
    kilit = SingleInstanceLock(tmp_path / "instance.lock", platform="win32", mutex_creator=kayit)

    kilit.acquire()
    kilit.release()
    kilit.acquire()  # aynı süreçte yeniden alma yeni mutex açmaz
    kilit.release()

    assert kilit.mutex_handles == (101, 102)
    assert len(kayit.adlar) == 2


def test_mutex_acilamazsa_acilis_durmaz(tmp_path: Path) -> None:
    kayit = _MutexKaydi(basarisiz=frozenset({r"Global\KutuphaneDefteri"}))
    kilit = SingleInstanceLock(tmp_path / "instance.lock", platform="win32", mutex_creator=kayit)

    kilit.acquire()
    try:
        assert kilit.handle is not None
        assert kilit.mutex_handles == (101,)
    finally:
        kilit.release()


def test_windows_disinda_mutex_acilmaz(tmp_path: Path) -> None:
    kayit = _MutexKaydi()
    with SingleInstanceLock(tmp_path / "instance.lock", platform="linux", mutex_creator=kayit):
        pass

    assert kayit.adlar == []


def test_ikinci_kopya_mutex_acmaz(tmp_path: Path) -> None:
    ilk = SingleInstanceLock(tmp_path / "instance.lock")
    kayit = _MutexKaydi()
    ikinci = SingleInstanceLock(tmp_path / "instance.lock", platform="win32", mutex_creator=kayit)

    ilk.acquire()
    try:
        with pytest.raises(AlreadyRunningError):
            ikinci.acquire()
    finally:
        ilk.release()

    assert kayit.adlar == []


# ------------------------------------------------------ çalışan kopya yardımcıları


def test_calisan_kopya_yoklamasi(tmp_path: Path) -> None:
    yol = tmp_path / "instance.lock"
    assert is_instance_running(yol) is False

    with SingleInstanceLock(yol):
        assert is_instance_running(yol) is True

    assert is_instance_running(yol) is False
    SingleInstanceLock(yol).acquire()  # yoklama kilidi bırakmış olmalı


def test_sinyal_goster_komutunu_veri_kokune_gonderir(tmp_path: Path) -> None:
    gonderilen: list[tuple[Path, str]] = []

    def gonder(kok: Path, komut: str) -> bool:
        gonderilen.append((kok, komut))
        return True

    assert signal_running_instance(tmp_path, sender=gonder) is True
    assert gonderilen == [(tmp_path, "goster")]


def test_sinyal_ulasmazsa_false(tmp_path: Path) -> None:
    def ulasmaz(kok: Path, komut: str) -> bool:
        raise OSError("bağlanamadı")

    assert signal_running_instance(tmp_path, sender=ulasmaz) is False
    assert signal_running_instance(tmp_path, sender=lambda kok, komut: False) is False


def test_acquire_sinyal_gondermez_hata_firlatir(tmp_path: Path) -> None:
    """GA-11: sinyal kilide gömülmez — `acquire` her kipte AlreadyRunningError verir."""
    kaynak = (Path(__file__).resolve().parents[1] / "lock.py").read_text(encoding="utf-8")
    govde = kaynak.split("    def acquire(self) -> None:", 1)[1].split("\n    def ", 1)[0]

    assert "signal_running_instance" not in govde
    assert "send_command" not in govde
    assert "raise AlreadyRunningError" in govde
