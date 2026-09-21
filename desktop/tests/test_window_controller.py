"""Pencere denetçisi testleri — çarpı = gizle, program yalnız "Çık" ile kapanır (U3, §4.2-4).

pywebview Docker imajında yoktur: pencere ve olayları sahtedir. Sahte olay,
pywebview 5.3.2'nin `Event.set()` sözleşmesini taklit eder (işleyicilerden biri
`False` dönerse kapanma iptal). Gerçek pencerede davranış F0 spike'ında elle
doğrulanır (packaging/windows/NOTLAR.md).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from desktop.window import (
    WindowController,
    close_reason_name,
    install_session_end_passthrough,
    open_window,
)


class _SahteOlay:
    """pywebview `Event`: `+=` ile işleyici eklenir; `set()` iptal edildiyse `True` döner."""

    def __init__(self) -> None:
        self.isleyiciler: list[Callable[[], Any]] = []

    def __iadd__(self, isleyici: Callable[[], Any]) -> _SahteOlay:
        self.isleyiciler.append(isleyici)
        return self

    def set(self) -> bool:
        donenler = [isleyici() for isleyici in self.isleyiciler]
        return any(deger is False for deger in donenler)


class _SahtePencere:
    _YONTEMLER = frozenset({"hide", "show", "minimize", "restore", "maximize", "destroy"})

    def __init__(self) -> None:
        self.events = SimpleNamespace(
            closing=_SahteOlay(),
            shown=_SahteOlay(),
            minimized=_SahteOlay(),
            maximized=_SahteOlay(),
            restored=_SahteOlay(),
        )
        self.cagrilar: list[str] = []
        self.native: Any = None
        self.patlayan: str | None = None

    def __getattr__(self, ad: str) -> Callable[[], None]:
        if ad not in self._YONTEMLER:
            raise AttributeError(ad)

        def yontem() -> None:
            if ad == self.patlayan:
                raise RuntimeError("pencere motoru meşgul")
            self.cagrilar.append(ad)

        return yontem

    def carpiya_bas(self) -> bool:
        """`True` = pencere kapandı, `False` = kapanma iptal edildi."""
        return not self.events.closing.set()


class _SahteWebview:
    def __init__(self, pencere: _SahtePencere) -> None:
        self.settings: dict[str, Any] = {}
        self.pencere = pencere
        self.start_kwargs: dict[str, Any] | None = None

    def create_window(self, title: str, url: str, **kwargs: Any) -> _SahtePencere:
        return self.pencere

    def start(self, **kwargs: Any) -> None:
        self.start_kwargs = kwargs


def _bagli(
    *, tepsi: bool = True, gosterildi: bool = True
) -> tuple[WindowController, _SahtePencere]:
    denetci = WindowController(platform="linux")
    denetci.tray_available = tepsi
    pencere = _SahtePencere()
    denetci.bind(pencere)
    if gosterildi:
        pencere.events.shown.set()
    return denetci, pencere


# ------------------------------------------------------------------ çarpı


def test_carpi_pencereyi_gizler_program_kapanmaz() -> None:
    _, pencere = _bagli(tepsi=True)

    assert pencere.carpiya_bas() is False
    assert pencere.cagrilar == ["hide"]


def test_tepsi_yoksa_carpi_kucultur_kapatmaz() -> None:
    """okulzili yedeği: gizli pencereyi geri getirecek tepsi yoksa küçültülür."""
    _, pencere = _bagli(tepsi=False)

    assert pencere.carpiya_bas() is False
    assert pencere.cagrilar == ["minimize"]


def test_gizleme_hatasi_da_pencereyi_kapatmaz() -> None:
    _, pencere = _bagli()
    pencere.patlayan = "hide"

    assert pencere.carpiya_bas() is False


# ------------------------------------------------------------------ Çık


def test_program_yalniz_cik_ile_kapanir() -> None:
    denetci, pencere = _bagli()

    denetci.request_quit()

    assert pencere.cagrilar == ["destroy"]
    assert pencere.carpiya_bas() is True  # destroy'un tetiklediği closing geçer
    assert denetci.quitting is True


def test_cik_iki_kez_gelse_de_pencere_bir_kez_kapatilir() -> None:
    denetci, pencere = _bagli()

    denetci.request_quit()
    denetci.request_quit()  # tepsiden Çık + kurucunun kapatma olayı

    assert pencere.cagrilar == ["destroy"]


def test_pencere_gosterilmeden_gelen_cik_gosterilince_uygulanir() -> None:
    """Kapatma olayı açılış sırasında gelebilir; pywebview API'si `shown`'ı bekler."""
    denetci, pencere = _bagli(gosterildi=False)

    denetci.request_quit()
    assert pencere.cagrilar == []

    pencere.events.shown.set()
    assert pencere.cagrilar == ["destroy"]


def test_kapatma_hatasi_yutulur() -> None:
    denetci, pencere = _bagli()
    pencere.patlayan = "destroy"

    denetci.request_quit()  # hata yükseltmez

    assert denetci.quitting is True


# ---------------------------------------------------------- Pencereyi aç


def test_pencereyi_ac_gizli_pencereyi_gosterir() -> None:
    denetci, pencere = _bagli()
    pencere.carpiya_bas()

    denetci.show()

    assert pencere.cagrilar == ["hide", "show"]


def test_pencereyi_ac_kucultulmus_pencereyi_eski_boyutuna_dondurur() -> None:
    denetci, pencere = _bagli()
    pencere.events.minimized.set()
    denetci.show()  # normal boyuttan küçültülmüş → restore

    pencere.events.maximized.set()
    pencere.events.minimized.set()
    denetci.show()  # büyütülmüşken küçültülmüş → maximize (restore normal boyuta düşürürdü)

    pencere.events.restored.set()
    denetci.show()  # küçültülmemiş → yalnız show

    assert pencere.cagrilar == ["show", "restore", "show", "maximize", "show"]


def test_pencereyi_ac_cikista_ya_da_pencere_yokken_etkisiz() -> None:
    WindowController(platform="linux").show()  # bağlanmamış
    denetci, pencere = _bagli()
    denetci.request_quit()

    denetci.show()

    assert pencere.cagrilar == ["destroy"]


def test_pencereyi_ac_hatasi_yutulur() -> None:
    denetci, pencere = _bagli()
    pencere.patlayan = "show"

    denetci.show()  # hata yükseltmez


# ------------------------------------------------------------ open_window


def test_denetci_pencereye_start_tan_once_baglanir(tmp_path: Path) -> None:
    sahte = _SahteWebview(_SahtePencere())
    denetci = WindowController(platform="linux")

    open_window(
        "http://127.0.0.1:1/",
        webview=sahte,
        platform="linux",
        storage_path=tmp_path,
        controller=denetci,
    )

    assert sahte.start_kwargs is not None and sahte.start_kwargs["gui"] == "qt"
    assert sahte.pencere.events.closing.isleyiciler == [denetci.on_closing]


def test_cik_acilista_istendiyse_pencere_hic_baslatilmaz(tmp_path: Path) -> None:
    sahte = _SahteWebview(_SahtePencere())
    denetci = WindowController(platform="linux")
    denetci.request_quit()

    open_window(
        "http://127.0.0.1:1/",
        webview=sahte,
        platform="linux",
        storage_path=tmp_path,
        controller=denetci,
    )

    assert sahte.start_kwargs is None


# ------------------------------------------ Windows oturum kapanışı (FormClosing)


class _NetOlayi:
    def __init__(self) -> None:
        self.isleyiciler: list[Callable[[Any, Any], None]] = []

    def __iadd__(self, isleyici: Callable[[Any, Any], None]) -> _NetOlayi:
        self.isleyiciler.append(isleyici)
        return self


class _KapanisArgs:
    def __init__(self, neden: Any) -> None:
        self.CloseReason = neden
        self.Cancel = True  # pywebview'ın işleyicisi (bizim closing'imiz) iptal etti


def _yerel_pencere() -> _SahtePencere:
    pencere = _SahtePencere()
    pencere.native = SimpleNamespace(FormClosing=_NetOlayi())
    return pencere


@pytest.mark.parametrize("neden", ["WindowsShutDown", "TaskManagerClosing", 1, 4])
def test_windows_oturum_kapanisinda_iptal_geri_alinir(neden: Any) -> None:
    """İptal edilseydi Windows kapanışı engellenir, işaret yazılmaz, sabah alarm çıkardı."""
    denetci = WindowController(platform="win32")
    pencere = _yerel_pencere()

    assert install_session_end_passthrough(pencere, denetci, platform="win32") is True
    (isleyici,) = pencere.native.FormClosing.isleyiciler
    args = _KapanisArgs(neden)
    isleyici(None, args)

    assert args.Cancel is False
    assert denetci.quitting is True


def test_oturum_kapanisinda_pencere_ikinci_kez_kapatilmaya_calisilmaz() -> None:
    denetci = WindowController(platform="win32")
    pencere = _yerel_pencere()
    denetci.bind(pencere)
    pencere.events.shown.set()

    pencere.native.FormClosing.isleyiciler[0](None, _KapanisArgs("WindowsShutDown"))
    denetci.request_quit()

    assert pencere.cagrilar == []  # pencereyi Windows kapatıyor


def test_windows_kullanici_kapatmasinda_iptal_korunur() -> None:
    denetci = WindowController(platform="win32")
    pencere = _yerel_pencere()
    install_session_end_passthrough(pencere, denetci, platform="win32")

    args = _KapanisArgs("UserClosing")
    pencere.native.FormClosing.isleyiciler[0](None, args)

    assert args.Cancel is True
    assert denetci.quitting is False


def test_kapanis_nedeni_adi_cozulur() -> None:
    assert close_reason_name(_KapanisArgs("CloseReason.WindowsShutDown")) == "WindowsShutDown"
    assert close_reason_name(_KapanisArgs(4)) == "TaskManagerClosing"
    assert close_reason_name(SimpleNamespace()) == ""


def test_oturum_kapanisi_isleyicisi_windowsta_gosterilince_bir_kez_baglanir() -> None:
    denetci = WindowController(platform="win32")
    pencere = _yerel_pencere()
    denetci.bind(pencere)

    pencere.events.shown.set()
    pencere.events.shown.set()  # Qt her gösterişte `shown` verir

    assert len(pencere.native.FormClosing.isleyiciler) == 1


def test_oturum_kapanisi_isleyicisi_windows_disinda_ya_da_yerel_pencere_yokken_baglanmaz() -> None:
    linux = WindowController(platform="linux")

    assert install_session_end_passthrough(_yerel_pencere(), linux, platform="linux") is False
    assert (
        install_session_end_passthrough(_SahtePencere(), WindowController(), platform="win32")
        is False
    )


def test_oturum_kapanisi_isleyicisi_baglanamazsa_acilis_surer() -> None:
    class _Bozuk:
        @property
        def FormClosing(self) -> Any:  # .NET adı
            raise TypeError("pythonnet bağlanamadı")

    pencere = _SahtePencere()
    pencere.native = _Bozuk()

    assert install_session_end_passthrough(pencere, WindowController(), platform="win32") is False
