"""Tek kopya kanalı testleri (tasarım §4.2-1 ikinci açılış, §4.2-5 kapatma olayı).

Linux yolu GERÇEK UNIX soketiyle koşar. Windows yolu (adlı olaylar) sahte
`EventApi` ile sınanır: bekleme, önceliklendirme ve durdurma mantığı ctypes'tan
bağımsızdır; gerçek Win32 çağrıları CI Windows koşusunda ve elle doğrulanır
(packaging/windows/NOTLAR.md).
"""

from __future__ import annotations

import os
import stat
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from desktop import instance_channel as kanal
from desktop.instance_channel import (
    COMMAND_QUIT,
    COMMAND_SHOW,
    QUIT_EVENT_NAME,
    SHOW_EVENT_NAME,
    ChannelError,
    NamedEventChannel,
    UnixSocketChannel,
    open_channel,
    send_command,
    socket_path,
)

linux_yalniz = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="UNIX soketi kanalı yalnız Linux'ta"
)


def _bekle(kosul: Callable[[], bool], sure: float = 3.0) -> bool:
    son = time.monotonic() + sure
    while time.monotonic() < son:
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


class _Toplayici:
    def __init__(self) -> None:
        self.komutlar: list[str] = []
        self._kilit = threading.Lock()

    def __call__(self, komut: str) -> None:
        with self._kilit:
            self.komutlar.append(komut)


# ------------------------------------------------------------------ Linux soketi


@linux_yalniz
def test_goster_ve_kapat_komutlari_dinleyiciye_ulasir(tmp_path: Path) -> None:
    dinleyici = UnixSocketChannel(tmp_path)
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        assert send_command(tmp_path, COMMAND_SHOW) is True
        assert send_command(tmp_path, COMMAND_QUIT) is True
        assert _bekle(lambda: len(toplayici.komutlar) == 2)
    finally:
        dinleyici.close()

    assert toplayici.komutlar == [COMMAND_SHOW, COMMAND_QUIT]


@linux_yalniz
def test_dinleyici_baslamadan_gelen_komut_kaybolmaz(tmp_path: Path) -> None:
    """Kanal kilitten hemen sonra kurulur; komut açılışın ortasında gelirse kuyrukta bekler."""
    dinleyici = UnixSocketChannel(tmp_path)
    toplayici = _Toplayici()
    try:
        assert send_command(tmp_path, COMMAND_QUIT) is True
        dinleyici.start(toplayici)
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_QUIT])
    finally:
        dinleyici.close()


@linux_yalniz
def test_soket_yalniz_sahibine_acik(tmp_path: Path) -> None:
    dinleyici = UnixSocketChannel(tmp_path)
    try:
        kip = stat.S_IMODE(os.stat(socket_path(tmp_path)).st_mode)
        assert kip == 0o600
    finally:
        dinleyici.close()


@linux_yalniz
def test_bayat_soket_dosyasi_yerine_yenisi_kurulur(tmp_path: Path) -> None:
    """Önceki süreç öldürüldüyse soket dosyası kalır; kilit bizde olduğundan bayattır."""
    socket_path(tmp_path).write_bytes(b"")
    dinleyici = UnixSocketChannel(tmp_path)
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        assert send_command(tmp_path, COMMAND_SHOW) is True
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_SHOW])
    finally:
        dinleyici.close()


@linux_yalniz
def test_kapaninca_soket_silinir_ve_komut_ulasmaz(tmp_path: Path) -> None:
    dinleyici = UnixSocketChannel(tmp_path)
    dinleyici.start(_Toplayici())
    dinleyici.close()

    assert not socket_path(tmp_path).exists()
    assert send_command(tmp_path, COMMAND_SHOW) is False
    dinleyici.close()  # ikinci kapatma etkisiz


@linux_yalniz
def test_dinleyici_yokken_gonderim_false(tmp_path: Path) -> None:
    assert send_command(tmp_path, COMMAND_SHOW) is False


@linux_yalniz
def test_bilinmeyen_komut_yok_sayilir(tmp_path: Path) -> None:
    import socket

    dinleyici = UnixSocketChannel(tmp_path)
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as istemci:
            istemci.connect(str(socket_path(tmp_path)))
            istemci.sendall(b"rm -rf /\n")
        assert send_command(tmp_path, COMMAND_SHOW) is True
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_SHOW])
    finally:
        dinleyici.close()

    assert toplayici.komutlar == [COMMAND_SHOW]


@linux_yalniz
def test_isleyici_hatasi_dinleyiciyi_durdurmaz(tmp_path: Path) -> None:
    dinleyici = UnixSocketChannel(tmp_path)
    alinan: list[str] = []

    def isleyici(komut: str) -> None:
        alinan.append(komut)
        if len(alinan) == 1:
            raise RuntimeError("pencere yok")

    dinleyici.start(isleyici)
    try:
        send_command(tmp_path, COMMAND_SHOW)
        assert _bekle(lambda: len(alinan) == 1)
        send_command(tmp_path, COMMAND_QUIT)
        assert _bekle(lambda: alinan == [COMMAND_SHOW, COMMAND_QUIT])
    finally:
        dinleyici.close()


def test_cok_uzun_soket_yolu_kanal_kurmaz(tmp_path: Path) -> None:
    derin = tmp_path / ("a" * 120)
    derin.mkdir()

    with pytest.raises(ChannelError):
        UnixSocketChannel(derin)
    assert open_channel(derin, platform="linux") is None
    assert send_command(derin, COMMAND_SHOW, platform="linux") is False


def test_bilinmeyen_komut_gonderilemez(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Bilinmeyen"):
        send_command(tmp_path, "sil")


def test_desteklenmeyen_platformda_kanal_yok(tmp_path: Path) -> None:
    assert open_channel(tmp_path, platform="darwin") is None
    assert send_command(tmp_path, COMMAND_SHOW, platform="darwin") is False


@linux_yalniz
def test_linuxta_open_channel_soket_kanali_kurar(tmp_path: Path) -> None:
    acilan = open_channel(tmp_path, platform="linux")
    try:
        assert isinstance(acilan, UnixSocketChannel)
        assert acilan.path == tmp_path / "kanal.sock"
    finally:
        assert acilan is not None
        acilan.close()


# ------------------------------------------------------------ Windows (sahte olay)


class _SahteOlaylar:
    """Adlı olayların süreç içi sahtesi (Windows sözleşmesiyle).

    Nesne ile tanıtıcı ayrıdır: `OpenEventW` aynı nesneye YENİ bir tanıtıcı
    verir; bir tanıtıcıyı kapatmak diğerlerini etkilemez. Olay otomatik
    sıfırlanır ve işaret, bekleyen biri tüketene dek kalır.
    """

    def __init__(self, *, kurulamayan: str | None = None) -> None:
        self._kosul = threading.Condition()
        self._nesne: dict[int, int] = {}  # tanıtıcı → nesne
        self._isaretli: dict[int, bool] = {}  # nesne → işaret
        self._adlar: dict[str, int] = {}  # ad → kurucunun tanıtıcısı
        self.acilan: list[int] = []
        self.kapatilan: list[int] = []
        self._sayac = 0
        self._kurulamayan = kurulamayan

    def _yeni_tanitici(self, nesne: int) -> int:
        self._sayac += 1
        self._nesne[self._sayac] = nesne
        return self._sayac

    def create_event(self, name: str | None) -> int | None:
        if name is not None and name == self._kurulamayan:
            return None
        with self._kosul:
            nesne = len(self._isaretli) + 1
            self._isaretli[nesne] = False
            tanitici = self._yeni_tanitici(nesne)
            if name is not None:
                self._adlar[name] = tanitici
            return tanitici

    def open_event(self, name: str) -> int | None:
        with self._kosul:
            kurucu = self._adlar.get(name)
            if kurucu is None:
                return None
            tanitici = self._yeni_tanitici(self._nesne[kurucu])
            self.acilan.append(tanitici)
            return tanitici

    def set_event(self, handle: int) -> bool:
        with self._kosul:
            self._isaretli[self._nesne[handle]] = True
            self._kosul.notify_all()
        return True

    def wait_any(self, handles: Sequence[int]) -> int | None:
        with self._kosul:
            while True:
                if any(h in self.kapatilan for h in handles):
                    return None  # WAIT_FAILED (kapatılmış tanıtıcı)
                for sira, handle in enumerate(handles):
                    nesne = self._nesne[handle]
                    if self._isaretli[nesne]:
                        self._isaretli[nesne] = False  # otomatik sıfırlama
                        return sira
                self._kosul.wait(0.05)

    def close_handle(self, handle: int) -> None:
        with self._kosul:
            self.kapatilan.append(handle)
            self._kosul.notify_all()

    def adli(self, name: str) -> int:
        return self._adlar[name]


def test_windows_olay_adlari_tasarimla_ayni() -> None:
    assert SHOW_EVENT_NAME == "KutuphaneDefteri.Goster"
    assert QUIT_EVENT_NAME == "KutuphaneDefteri.Kapat"


def test_windows_kurucu_ayni_kapatma_olayini_acar() -> None:
    iss = (
        Path(__file__).resolve().parents[2] / "packaging" / "windows" / "kutuphane-defteri.iss"
    ).read_text(encoding="utf-8")

    assert f"KapatOlayi = '{QUIT_EVENT_NAME}';" in iss
    assert "OpenEventW@kernel32.dll stdcall" in iss
    assert "SetEvent@kernel32.dll stdcall" in iss


def test_windows_goster_ve_kapat_olaylari_isleyiciye_ulasir(tmp_path: Path) -> None:
    olaylar = _SahteOlaylar()
    dinleyici = NamedEventChannel(olaylar)
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        assert send_command(tmp_path, COMMAND_SHOW, platform="win32", event_api=olaylar)
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_SHOW])
        assert send_command(tmp_path, COMMAND_QUIT, platform="win32", event_api=olaylar)
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_SHOW, COMMAND_QUIT])
    finally:
        dinleyici.close()


def test_windows_acilista_gelen_kapat_dinleyici_baslayinca_islenir() -> None:
    """Otomatik sıfırlanan olay tüketilene dek işaretli kalır: kurucunun isteği kaybolmaz."""
    olaylar = _SahteOlaylar()
    dinleyici = NamedEventChannel(olaylar)
    olaylar.set_event(olaylar.adli(QUIT_EVENT_NAME))
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        assert _bekle(lambda: toplayici.komutlar == [COMMAND_QUIT])
    finally:
        dinleyici.close()


def test_windows_kapat_goster_den_once_islenir() -> None:
    olaylar = _SahteOlaylar()
    dinleyici = NamedEventChannel(olaylar)
    olaylar.set_event(olaylar.adli(SHOW_EVENT_NAME))
    olaylar.set_event(olaylar.adli(QUIT_EVENT_NAME))
    toplayici = _Toplayici()
    dinleyici.start(toplayici)
    try:
        assert _bekle(lambda: len(toplayici.komutlar) == 2)
    finally:
        dinleyici.close()

    assert toplayici.komutlar == [COMMAND_QUIT, COMMAND_SHOW]


def test_windows_kapatinca_is_parcacigi_durur_ve_taniticilar_kapanir() -> None:
    olaylar = _SahteOlaylar()
    dinleyici = NamedEventChannel(olaylar)
    dinleyici.start(_Toplayici())
    is_parcacigi = dinleyici._thread
    assert is_parcacigi is not None and is_parcacigi.name == kanal.THREAD_NAME

    dinleyici.close()

    assert not is_parcacigi.is_alive()
    assert sorted(olaylar.kapatilan) == [1, 2, 3]
    dinleyici.close()  # ikinci kapatma etkisiz
    assert sorted(olaylar.kapatilan) == [1, 2, 3]


def test_windows_olay_kurulamazsa_kanal_yok_ve_tanitici_sizmaz(tmp_path: Path) -> None:
    olaylar = _SahteOlaylar(kurulamayan=SHOW_EVENT_NAME)

    with pytest.raises(ChannelError):
        NamedEventChannel(olaylar)
    assert sorted(olaylar.kapatilan) == [1, 2]  # durdurma + kapat olayı geri kapatıldı
    assert open_channel(tmp_path, platform="win32", event_api=olaylar) is None


def test_windows_calisan_kopya_yoksa_gonderim_false(tmp_path: Path) -> None:
    olaylar = _SahteOlaylar()  # olay kurulmamış: OpenEventW başarısız

    assert send_command(tmp_path, COMMAND_SHOW, platform="win32", event_api=olaylar) is False


def test_windows_gonderim_taniticiyi_kapatir(tmp_path: Path) -> None:
    olaylar = _SahteOlaylar()
    NamedEventChannel(olaylar)

    send_command(tmp_path, COMMAND_QUIT, platform="win32", event_api=olaylar)

    (acilan,) = olaylar.acilan
    assert acilan != olaylar.adli(QUIT_EVENT_NAME)
    assert olaylar.kapatilan == [acilan]  # yalnız gönderenin tanıtıcısı; dinleyicininki açık
