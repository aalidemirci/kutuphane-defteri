"""Pencere denetçisinin F5 davranışları (tasarım §4.2-4, §4.5).

* Görevli kipinde tepsideki Çık: pencere öne gelir ve arayüze `kd:cik-iste`
  olayı gönderilir; arayüz yönetici parolasını sorar (`POST app/quit/`).
* Tepside gizli açılış (`--tepside`): gizli pencerede `shown` gelmeyebilir;
  sayfa yüklenince (`loaded`) pencere komut alır, açılışta gelen Çık uygulanır.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from desktop.window import WindowController, open_window


class _Olay:
    def __init__(self) -> None:
        self.isleyiciler: list[Callable[[], Any]] = []

    def __iadd__(self, isleyici: Callable[[], Any]) -> _Olay:
        self.isleyiciler.append(isleyici)
        return self

    def set(self) -> None:
        for isleyici in self.isleyiciler:
            isleyici()


class _Pencere:
    def __init__(self) -> None:
        self.events = SimpleNamespace(
            closing=_Olay(),
            shown=_Olay(),
            loaded=_Olay(),
            minimized=_Olay(),
            maximized=_Olay(),
            restored=_Olay(),
        )
        self.cagrilar: list[str] = []
        self.native: Any = None
        self.js: list[str] = []

    def show(self) -> None:
        self.cagrilar.append("show")

    def destroy(self) -> None:
        self.cagrilar.append("destroy")

    def evaluate_js(self, kod: str) -> None:
        self.js.append(kod)


def test_gorevli_ciki_pencereyi_one_getirir_ve_arayuze_olay_gonderir() -> None:
    denetci = WindowController(platform="linux")
    pencere = _Pencere()
    denetci.bind(pencere)
    pencere.events.shown.set()

    denetci.ask_quit_in_spa()

    assert pencere.cagrilar == ["show"]
    assert pencere.js == ["window.dispatchEvent(new Event('kd:cik-iste'))"]
    assert denetci.quitting is False  # kapanış parolalı istekle başlar


def test_gizli_baslayan_pencere_yuklenince_komut_alir() -> None:
    denetci = WindowController(platform="linux")
    denetci.tray_available = True
    pencere = _Pencere()
    denetci.bind(pencere)

    denetci.show()
    assert pencere.cagrilar == []  # henüz ne gösterildi ne yüklendi

    pencere.events.loaded.set()
    denetci.show()
    assert pencere.cagrilar == ["show"]


def test_gizli_pencerede_acilista_gelen_cik_yuklenince_uygulanir() -> None:
    denetci = WindowController(platform="linux")
    pencere = _Pencere()
    denetci.bind(pencere)

    denetci.request_quit()
    assert pencere.cagrilar == []
    pencere.events.loaded.set()

    assert pencere.cagrilar == ["destroy"]


def test_arayuz_olayi_gonderilemezse_program_dusmez() -> None:
    denetci = WindowController(platform="linux")
    pencere = _Pencere()

    def patla(kod: str) -> None:
        raise RuntimeError("pencere hazır değil")

    pencere.evaluate_js = patla  # type: ignore[method-assign]
    denetci.bind(pencere)
    pencere.events.shown.set()

    denetci.ask_quit_in_spa()  # yükseltmez


class _Webview:
    def __init__(self) -> None:
        self.settings: dict[str, Any] = {}
        self.kw: dict[str, Any] = {}

    def create_window(self, title: str, url: str, **kw: Any) -> _Pencere:
        self.kw = kw
        return _Pencere()

    def start(self, **kw: Any) -> None:
        return None


def test_tepside_acilista_pencere_gizli_kurulur(tmp_path: Path) -> None:
    webview = _Webview()

    open_window(
        "http://127.0.0.1:1/", storage_path=tmp_path, webview=webview, platform="linux", hidden=True
    )

    assert webview.kw["hidden"] is True


def test_olagan_acilista_pencere_gorunur(tmp_path: Path) -> None:
    webview = _Webview()

    open_window("http://127.0.0.1:1/", storage_path=tmp_path, webview=webview, platform="linux")

    assert webview.kw["hidden"] is False
