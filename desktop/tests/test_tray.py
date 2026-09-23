"""Sistem tepsisi testleri (tasarım §4.4 F0 menüsü, §4.5, UY-7).

GUI kütüphaneleri (pystray, PySide6) Docker imajında yoktur: ikisi de sahte
modülle sınanır. Gerçek tepsi davranışı (Windows'ta pystray iş parçacığı,
Linux'ta Qt ana iş parçacığı) F0 spike'ında elle doğrulanır
(packaging/windows/NOTLAR.md).
"""

from __future__ import annotations

import logging
import os
import signal
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from desktop import tray as tray_mod
from desktop.tray import (
    MENU_QUIT,
    MENU_SHOW,
    NullTray,
    PystrayTray,
    QtTray,
    TrayActions,
    load_icon_image,
    menu_entries,
    start_tray,
)
from desktop.window import app_icon_path

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _qt_ortam_degiskenleri_geri_alinir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qt ortam değişkenleri test sonunda eski hâline döner.

    `prepare_qt_application` `QT_STYLE_OVERRIDE`'ı, `load_qt` ise bağlayıcıyı
    seçen `QT_API`'yi yazar. `QT_API` sıfırlanır (silinir) ki `setdefault`
    davranışı sınanabilsin; monkeypatch teardown'da yazılan değeri kaldırır.
    """
    monkeypatch.setenv("QT_STYLE_OVERRIDE", "test-oncesi")
    monkeypatch.delenv("QT_API", raising=False)


class _Sayac:
    def __init__(self) -> None:
        self.goster = 0
        self.cik = 0

    def eylemler(self) -> TrayActions:
        def goster() -> None:
            self.goster += 1

        def cik() -> None:
            self.cik += 1

        return TrayActions(show=goster, quit=cik)


# ------------------------------------------------------------------ menü (F0)


def test_f0_menusu_yalniz_iki_komut() -> None:
    """Kip matrisinin kalanı F1/F5'te (`KipDurumu`); F0'da yalnız aç ve Çık."""
    sayac = _Sayac()

    assert [metin for metin, _ in menu_entries(sayac.eylemler())] == ["Pencereyi aç", "Çık"]
    assert (MENU_SHOW, MENU_QUIT) == ("Pencereyi aç", "Çık")


# ------------------------------------------------------------------- simge


def test_uygulama_ikonu_depoda_bulunur() -> None:
    yol = app_icon_path(root=REPO_ROOT)

    assert yol == REPO_ROOT / "packaging" / "ikonlar" / "kutuphane-defteri.ico"


def test_paketli_programda_ikon_kokte_aranir(tmp_path: Path) -> None:
    (tmp_path / "kutuphane-defteri.ico").write_bytes(b"ico")

    assert app_icon_path(root=tmp_path) == tmp_path / "kutuphane-defteri.ico"
    assert app_icon_path(root=tmp_path / "yok") is None


def test_tepsi_simgesi_gercek_ikondan_yuklenir() -> None:
    goruntu = load_icon_image(app_icon_path(root=REPO_ROOT))

    assert goruntu.mode == "RGBA"
    assert goruntu.size[0] >= 32


def test_ikon_bozuksa_duz_renk_yedek(tmp_path: Path) -> None:
    bozuk = tmp_path / "bozuk.ico"
    bozuk.write_bytes(b"ico degil")

    for kaynak in (bozuk, None):
        goruntu = load_icon_image(kaynak)
        assert goruntu.size == (64, 64)


# ------------------------------------------------------------ Windows: pystray


class _SahtePystray:
    """pystray modülünün kullandığımız yüzeyi."""

    def __init__(self, *, patlasin: bool = False) -> None:
        self.ikonlar: list[Any] = []
        self._patlasin = patlasin
        disari = self

        class MenuItem:
            def __init__(self, text: str, action: Callable[[], None], default: bool = False):
                self.text, self.action, self.default = text, action, default

        class Menu:
            def __init__(self, *items: MenuItem) -> None:
                self.items = items

        class Icon:
            def __init__(self, name: str, icon: Image.Image, title: str, menu: Menu) -> None:
                self.name, self.icon, self.title, self.menu = name, icon, title, menu
                self.run_detached_cagri = 0
                self.stop_cagri = 0
                disari.ikonlar.append(self)

            def run_detached(self) -> None:
                if disari._patlasin:
                    raise OSError("Shell_NotifyIcon başarısız")
                self.run_detached_cagri += 1

            def stop(self) -> None:
                self.stop_cagri += 1

        self.MenuItem, self.Menu, self.Icon = MenuItem, Menu, Icon


def test_windows_tepsisi_run_detached_ile_kurulur() -> None:
    sahte = _SahtePystray()
    sayac = _Sayac()
    tepsi = PystrayTray(sayac.eylemler(), pystray_module=sahte)

    assert tepsi.start() is True
    assert tepsi.available is True
    (ikon,) = sahte.ikonlar
    assert ikon.run_detached_cagri == 1
    assert ikon.title == "Kütüphane Defteri"
    assert [(i.text, i.default) for i in ikon.menu.items] == [
        ("Pencereyi aç", True),  # simgeye tıklama pencereyi açar
        ("Çık", False),
    ]

    ikon.menu.items[0].action()
    ikon.menu.items[1].action()
    assert (sayac.goster, sayac.cik) == (1, 1)


def test_windows_tepsisi_cikista_icon_stop_cagirir() -> None:
    """run_detached daemon OLMAYAN iş parçacığı açar: stop atlanırsa süreç asılı kalır."""
    sahte = _SahtePystray()
    tepsi = PystrayTray(_Sayac().eylemler(), pystray_module=sahte)
    tepsi.start()

    tepsi.stop()
    tepsi.stop()  # ikinci çağrı etkisiz

    assert sahte.ikonlar[0].stop_cagri == 1
    assert tepsi.available is False


def test_windows_tepsisi_kurulamazsa_program_surer(kd_gunlugu: list[logging.LogRecord]) -> None:
    tepsi = PystrayTray(_Sayac().eylemler(), pystray_module=_SahtePystray(patlasin=True))

    assert tepsi.start() is False
    assert tepsi.available is False
    assert any("tepsi" in k.getMessage() for k in kd_gunlugu)
    tepsi.stop()  # kurulmamış tepside de güvenli


def test_tepsi_komutu_hatasi_tepsiyi_dusurmez(kd_gunlugu: list[logging.LogRecord]) -> None:
    def patla() -> None:
        raise RuntimeError("pencere yok")

    sahte = _SahtePystray()
    PystrayTray(TrayActions(show=patla, quit=patla), pystray_module=sahte).start()

    sahte.ikonlar[0].menu.items[0].action()  # hata yükseltmez

    assert any("Tepsi komutu başarısız" in k.getMessage() for k in kd_gunlugu)


def test_pystray_modulu_yoksa_tepsisiz() -> None:
    """Geliştirme ortamında pystray kurulu değil: gerçek içe aktarma denenir, düşer."""
    tepsi = PystrayTray(_Sayac().eylemler())

    assert tepsi.start() is False


# ---------------------------------------------------------------- Linux: Qt


class _Sinyal:
    def __init__(self) -> None:
        self.baglananlar: list[Callable[..., Any]] = []

    def connect(self, hedef: Callable[..., Any]) -> None:
        self.baglananlar.append(hedef)

    def emit(self, *args: Any) -> None:
        for hedef in self.baglananlar:
            hedef(*args)


class _SahteQt:
    """PySide6'nın kullandığımız yüzeyi; kurulum sırasını kaydeder."""

    def __init__(self, *, tepsi_var: bool = True, uygulama_var: bool = False) -> None:
        self.sira: list[str] = []
        self.tepsiler: list[Any] = []
        self.zamanlayicilar: list[Any] = []
        disari = self

        class QApplication:
            _ornek: Any = None

            def __init__(self, argv: list[str]) -> None:
                disari.sira.append("QApplication")
                self.son_pencere_kapaninca_cik = True
                QApplication._ornek = self

            @classmethod
            def instance(cls) -> Any:
                return cls._ornek

            def setQuitOnLastWindowClosed(self, deger: bool) -> None:
                self.son_pencere_kapaninca_cik = deger

        if uygulama_var:
            QApplication._ornek = QApplication.__new__(QApplication)
            QApplication._ornek.son_pencere_kapaninca_cik = True

        class QIcon:
            def __init__(self, kaynak: Any = None) -> None:
                self.kaynak = kaynak

            @staticmethod
            def fromTheme(ad: str) -> Any:
                return QIcon(None)

            def isNull(self) -> bool:
                return self.kaynak is None

        class QPixmap:
            def __init__(self) -> None:
                self.veri = b""

            def loadFromData(self, veri: bytes, bicim: str) -> bool:
                self.veri = veri
                return True

        class QAction:
            def __init__(self, metin: str) -> None:
                self.metin = metin
                self.triggered = _Sinyal()

        class QMenu:
            def __init__(self) -> None:
                self.eylemler: list[QAction] = []

            def addAction(self, metin: str) -> QAction:
                eylem = QAction(metin)
                self.eylemler.append(eylem)
                return eylem

        class QSystemTrayIcon:
            Trigger, DoubleClick, Context = 3, 2, 1

            def __init__(self, icon: Any, parent: Any) -> None:
                disari.sira.append("QSystemTrayIcon")
                self.icon, self.parent = icon, parent
                self.activated = _Sinyal()
                self.menu: QMenu | None = None
                self.gorunur = False
                disari.tepsiler.append(self)

            @staticmethod
            def isSystemTrayAvailable() -> bool:
                return tepsi_var

            def setToolTip(self, metin: str) -> None:
                self.ipucu = metin

            def setContextMenu(self, menu: QMenu) -> None:
                self.menu = menu

            def show(self) -> None:
                self.gorunur = True

            def hide(self) -> None:
                self.gorunur = False

        class QTimer:
            def __init__(self) -> None:
                self.timeout = _Sinyal()
                self.aralik: int | None = None
                disari.zamanlayicilar.append(self)

            def start(self, aralik: int) -> None:
                self.aralik = aralik

            def stop(self) -> None:
                self.aralik = None

        self.QApplication, self.QSystemTrayIcon, self.QMenu = QApplication, QSystemTrayIcon, QMenu
        self.QIcon, self.QPixmap, self.QTimer = QIcon, QPixmap, QTimer

    def yukleyici(self) -> Any:
        self.sira.append("QtWebEngineWidgets")
        return self


class _SinyalKaydi:
    def __init__(self) -> None:
        self.kurulan: list[tuple[int, Any]] = []

    def __call__(self, signum: int, isleyici: Any) -> Any:
        self.kurulan.append((signum, isleyici))
        return "onceki-isleyici" if len(self.kurulan) == 1 else None


def _qt_tepsi(qt: _SahteQt, sayac: _Sayac, sinyal: _SinyalKaydi | None = None) -> QtTray:
    return QtTray(
        sayac.eylemler(),
        icon_path=app_icon_path(root=REPO_ROOT),
        qt_loader=qt.yukleyici,
        signal_installer=sinyal or _SinyalKaydi(),
    )


def test_qt_webengine_uygulamadan_once_yuklenir_ve_tepsi_ondan_sonra_kurulur() -> None:
    qt = _SahteQt()
    tepsi = _qt_tepsi(qt, _Sayac())

    assert tepsi.start() is True
    assert qt.sira == ["QtWebEngineWidgets", "QApplication", "QSystemTrayIcon"]
    uygulama = qt.QApplication.instance()
    assert uygulama.son_pencere_kapaninca_cik is False
    assert os.environ["QT_STYLE_OVERRIDE"] == ""  # pywebview qt.py ile aynı, kurulumdan önce
    assert qt.tepsiler[0].parent is uygulama
    tepsi.stop()


def test_qt_var_olan_uygulama_ornegini_kullanir() -> None:
    """pywebview'ın Qt arka ucu da `QApplication.instance()`'ı kullanır: tek örnek."""
    qt = _SahteQt(uygulama_var=True)
    onceki = qt.QApplication.instance()
    tepsi = _qt_tepsi(qt, _Sayac())

    tepsi.start()

    assert "QApplication" not in qt.sira
    assert os.environ["QT_STYLE_OVERRIDE"] == "test-oncesi"
    assert qt.QApplication.instance() is onceki
    assert onceki.son_pencere_kapaninca_cik is False
    tepsi.stop()


def test_qt_menusu_ve_simgeye_tiklama_komutlari_calistirir() -> None:
    qt = _SahteQt()
    sayac = _Sayac()
    tepsi = _qt_tepsi(qt, sayac)
    tepsi.start()
    (simge,) = qt.tepsiler

    assert simge.gorunur is True
    assert simge.ipucu == "Kütüphane Defteri"
    assert simge.menu is not None
    assert [e.metin for e in simge.menu.eylemler] == ["Pencereyi aç", "Çık"]
    assert simge.icon.kaynak.veri.startswith(b"\x89PNG")  # .ico Pillow ile PNG'ye çevrildi

    simge.menu.eylemler[0].triggered.emit(False)
    simge.activated.emit(qt.QSystemTrayIcon.Trigger)
    simge.activated.emit(qt.QSystemTrayIcon.Context)  # sağ tık yalnız menüyü açar
    simge.menu.eylemler[1].triggered.emit(False)

    assert (sayac.goster, sayac.cik) == (2, 1)
    tepsi.stop()
    assert simge.gorunur is False


def test_qt_tepsi_yoksa_kurulmaz_ama_uygulama_hazirdir(
    kd_gunlugu: list[logging.LogRecord],
) -> None:
    qt = _SahteQt(tepsi_var=False)
    tepsi = _qt_tepsi(qt, _Sayac())

    assert tepsi.start() is False
    assert tepsi.available is False
    assert qt.tepsiler == []
    assert qt.QApplication.instance() is not None
    assert any("küçültülecek" in k.getMessage() for k in kd_gunlugu)
    tepsi.stop()


def test_qt_yuklenemezse_tepsisiz(kd_gunlugu: list[logging.LogRecord]) -> None:
    def yok() -> Any:
        raise ImportError("PySide6 yok")

    tepsi = QtTray(_Sayac().eylemler(), qt_loader=yok, signal_installer=_SinyalKaydi())

    assert tepsi.start() is False
    tepsi.stop()


def test_sigterm_duzenli_cikisa_cevrilir() -> None:
    """Linux oturum kapanışı: SIGTERM → Qt zamanlayıcısı → "Çık" (T15 işareti yazılsın)."""
    qt = _SahteQt(tepsi_var=False)  # tepsi olmasa da köprü kurulur
    sayac = _Sayac()
    sinyal = _SinyalKaydi()
    tepsi = _qt_tepsi(qt, sayac, sinyal)
    tepsi.start()

    ((signum, isleyici),) = sinyal.kurulan
    assert signum == signal.SIGTERM
    (zamanlayici,) = qt.zamanlayicilar
    assert zamanlayici.aralik is not None

    zamanlayici.timeout.emit()
    assert sayac.cik == 0  # sinyal yokken bir şey olmaz

    isleyici(signal.SIGTERM, None)
    zamanlayici.timeout.emit()
    zamanlayici.timeout.emit()
    assert sayac.cik == 1  # istek bir kez işlenir

    tepsi.stop()
    assert sinyal.kurulan[-1] == (signal.SIGTERM, "onceki-isleyici")
    assert zamanlayici.aralik is None


def test_sigterm_kurulamazsa_tepsi_yine_kurulur() -> None:
    def ana_is_parcacigi_degil(signum: int, isleyici: Any) -> Any:
        raise ValueError("signal only works in main thread")

    qt = _SahteQt()
    tepsi = QtTray(
        _Sayac().eylemler(), qt_loader=qt.yukleyici, signal_installer=ana_is_parcacigi_degil
    )

    assert tepsi.start() is True
    assert qt.zamanlayicilar == []
    tepsi.stop()


# ---------------------------------------------------------------- platform seçimi


def test_platforma_gore_tepsi_secilir(monkeypatch: pytest.MonkeyPatch) -> None:
    baslatilan: list[str] = []

    def kaydeden(ad: str) -> Callable[[object], bool]:
        def start(_self: object) -> bool:
            baslatilan.append(ad)
            return True

        return start

    monkeypatch.setattr(PystrayTray, "start", kaydeden("pystray"))
    monkeypatch.setattr(QtTray, "start", kaydeden("qt"))
    eylemler = _Sayac().eylemler()

    assert isinstance(start_tray(eylemler, platform="win32"), PystrayTray)
    assert isinstance(start_tray(eylemler, platform="linux"), QtTray)
    assert isinstance(start_tray(eylemler, platform="darwin"), NullTray)
    assert baslatilan == ["pystray", "qt"]


def test_tepsi_kurulamasa_da_nesne_doner_ve_durdurulabilir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QtTray, "start", lambda self: False)

    tepsi = start_tray(_Sayac().eylemler(), platform="linux")

    assert tepsi.available is False
    tepsi.stop()


def test_null_tepsi() -> None:
    tepsi = NullTray()
    assert tepsi.available is False
    tepsi.stop()


def test_tepsi_ikonu_varsayilan_olarak_paket_yolundan_cozulur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alinan: list[Path | None] = []

    def kaydet(self: PystrayTray) -> bool:
        alinan.append(self._icon_path)
        return True

    monkeypatch.setattr(PystrayTray, "start", kaydet)
    monkeypatch.setattr(tray_mod, "app_icon_path", lambda: Path("/paket/kutuphane-defteri.ico"))

    start_tray(_Sayac().eylemler(), platform="win32")

    assert alinan == [Path("/paket/kutuphane-defteri.ico")]


def test_qt_yukleyici_webengine_i_once_ice_aktarir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qt kuralı: QtWebEngineWidgets, QApplication kurulmadan ÖNCE aktarılmalı."""
    sira: list[str] = []

    def sahte_import(ad: str) -> Any:
        sira.append(ad)
        return SimpleNamespace(
            QApplication=object,
            QSystemTrayIcon=object,
            QMenu=object,
            QIcon=object,
            QPixmap=object,
            QTimer=object,
        )

    monkeypatch.setattr(tray_mod, "importlib", SimpleNamespace(import_module=sahte_import))

    tray_mod.load_qt()

    assert sira[0] == "PySide6.QtWebEngineWidgets"
    assert sira[1:] == ["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"]


def _qt_modulu_taklidi(_ad: str) -> SimpleNamespace:
    """`load_qt`'nin okuduğu bütün sınıfları taşıyan boş taklit modül."""
    return SimpleNamespace(
        QApplication=object,
        QSystemTrayIcon=object,
        QMenu=object,
        QIcon=object,
        QPixmap=object,
        QTimer=object,
    )


def test_qt_yukleyici_baglayiciyi_pyside6_ye_sabitler(monkeypatch: pytest.MonkeyPatch) -> None:
    """qtpy kurulu ilk bağlayıcıyı seçer; seçim `QT_API` ile ilk import'tan önce sabitlenir."""
    monkeypatch.setattr(tray_mod, "importlib", SimpleNamespace(import_module=_qt_modulu_taklidi))

    tray_mod.load_qt()

    assert os.environ["QT_API"] == "pyside6"


def test_qt_yukleyici_disaridan_verilen_baglayiciyi_ezmez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sahada teşhis için elle verilmiş `QT_API` korunur (`setdefault`)."""
    monkeypatch.setenv("QT_API", "pyqt6")
    monkeypatch.setattr(tray_mod, "importlib", SimpleNamespace(import_module=_qt_modulu_taklidi))

    tray_mod.load_qt()

    assert os.environ["QT_API"] == "pyqt6"


def test_tepsi_geri_cagrisi_pystray_ve_qt_ile_uyumlu() -> None:
    """pystray `co_argcount`'a bakıp argümansız çağırır; Qt `triggered(bool)` değer verir."""
    cagri: list[int] = []
    sarili = tray_mod._guarded("deneme", lambda: cagri.append(1))

    assert sarili.__code__.co_argcount == 0
    sarili()
    sarili(False)
    assert cagri == [1, 1]
