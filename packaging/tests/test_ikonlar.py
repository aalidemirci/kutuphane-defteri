"""Program simgesi: kesimler, `.ico` ve simgenin göründüğü yüzeyler.

Logo 29.09.2026 kullanıcı kararıyla "Raf ve etiket"tir (tasarım §14.1 F12 ekleri
L-1; teknik borç TB4 kapandı). Üretim iki betiktir (`packaging/ikonlar/`):
`logo_uret.py` ana çizimi (1024) ve elle çizilmiş 16/24/32 kesimlerini yazar,
`ikon_uret.py` 48 ve üstünü ana çizimden türetir ve `.ico`'yu kurar. Çıktılar
depodadır; paket derlemesi ikon üretmez, bu testler depodaki dosyaların
üreticilerle ve birbirleriyle tutarlı olduğunu sınar.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from PIL import IcoImagePlugin, Image

REPO = Path(__file__).resolve().parents[2]
IKONLAR = REPO / "packaging" / "ikonlar"
ICO = IKONLAR / "kutuphane-defteri.ico"
APP_LOGO = REPO / "frontend" / "public" / "app-logo.png"


def _yukle(yol: Path, ad: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(ad, yol)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[ad] = modul
    spec.loader.exec_module(modul)
    return modul


LOGO: Any = _yukle(IKONLAR / "logo_uret.py", "kd_logo_uret")
IKON: Any = _yukle(IKONLAR / "ikon_uret.py", "kd_ikon_uret")

PALET_RGB = {renk[:3] for renk in (LOGO.LACIVERT, LOGO.SAFRAN, LOGO.KAGIT, LOGO.GOK)}
#: TB4'ün geçici logosunun (F0 kopyası) üç rengi: yeni simgelerde hiç geçmez.
ESKI_GECICI_LOGO_RENKLERI = {(41, 80, 124), (47, 125, 116), (28, 39, 51)}


def _ac(yol: Path) -> Image.Image:
    with Image.open(yol) as goruntu:
        return goruntu.convert("RGBA")


def _opak_renkler(goruntu: Image.Image) -> Counter[tuple[int, ...]]:
    """Tam opak piksellerin RGB sayımı."""
    veri = goruntu.convert("RGBA").tobytes()
    return Counter(tuple(veri[i : i + 3]) for i in range(0, len(veri), 4) if veri[i + 3] == 255)


def _png(boyut: int) -> Image.Image:
    return _ac(IKON.png_path(boyut))


def _ico_kareleri() -> dict[int, Image.Image]:
    with Image.open(ICO) as ico:
        assert isinstance(ico, IcoImagePlugin.IcoImageFile)
        return {
            genislik: ico.ico.getimage((genislik, yukseklik)).convert("RGBA")
            for genislik, yukseklik in ico.ico.sizes()
        }


def _butun_simgeler() -> dict[str, Image.Image]:
    simgeler = {f"png {b}": _png(b) for b in IKON.PNG_SIZES}
    simgeler |= {f"ico {b}": kare for b, kare in _ico_kareleri().items()}
    simgeler["logo 1024"] = _ac(IKON.MASTER_SOURCE)
    simgeler["app-logo.png"] = _ac(APP_LOGO)
    return simgeler


# ---------------------------------------------------------------------- .ico


def test_ico_her_boyutu_kendi_karesiyle_tasir() -> None:
    """16/24/32 elle çizilmiş, 48+ ana çizimden; Pillow hiçbir kareyi kendisi küçültmez."""
    kareler = _ico_kareleri()

    assert sorted(kareler) == sorted(IKON.ICO_SIZES) == [16, 24, 32, 48, 64, 128, 256]
    for boyut, kare in kareler.items():
        assert kare.size == (boyut, boyut)
        assert kare.tobytes() == _png(boyut).tobytes(), f".ico {boyut} px ≠ PNG kesimi"


def test_tepsinin_okudugu_kare_en_buyuk_boyuttur() -> None:
    """`desktop/tray.py::load_icon_image` `.ico`'yu açar: Pillow en büyük kareyi verir."""
    with Image.open(ICO) as ico:
        assert ico.size == (256, 256)
        assert ico.convert("RGBA").tobytes() == _png(256).tobytes()


# ------------------------------------------------------------ kesimlerin kaynağı


@pytest.mark.parametrize("boyut", [16, 24, 32])
def test_kucuk_kesimler_elle_cizilmistir(boyut: int) -> None:
    """Depodaki 16/24/32 üreticinin elle çizdiği kesimdir, ana çizimin küçültmesi değil."""
    depodaki = _png(boyut)

    assert (
        depodaki.tobytes() == LOGO.kucuk(boyut).tobytes()
    ), f"kutuphane-defteri-{boyut}.png güncel değil: logo_uret.py ve ikon_uret.py koşulur"
    assert depodaki.tobytes() != IKON.from_master(IKON.load_tile(), boyut).tobytes()


def test_16_piksel_kesim_yalniz_palet_renklerindendir() -> None:
    """Elle çizilmiş 16: opak her piksel tam palet rengidir (küçültme ara ton üretirdi)."""
    goruntu = _png(16)
    alfa = goruntu.getchannel("A").tobytes()
    yari_saydam = {(i % 16, i // 16) for i, a in enumerate(alfa) if a != 255}

    assert set(_opak_renkler(goruntu)) - PALET_RGB == set()
    # Yumuşatılmış yalnız karonun dört yuvarlak köşesidir (her biri 4×4 alanın içinde).
    assert yari_saydam and all((x < 4 or x >= 12) and (y < 4 or y >= 12) for x, y in yari_saydam)


@pytest.mark.parametrize("boyut", [48, 64, 128, 256, 512])
def test_buyuk_kesimler_ana_cizimden_gunceldir(boyut: int) -> None:
    """48+ kesimler depodaki ana çizimden türer (logo değişip ikon_uret koşulmadıysa kırılır)."""
    assert _png(boyut).tobytes() == IKON.from_master(IKON.load_tile(), boyut).tobytes()


def test_on_yuz_logosu_ana_cizimden_gunceldir() -> None:
    beklenen = IKON.from_master(IKON.load_tile(), IKON.FRONTEND_SIZE)

    assert _ac(APP_LOGO).tobytes() == beklenen.tobytes()


def test_site_gorseli_ana_cizimden_kardes_olcusuyle_turer(tmp_path: Path) -> None:
    """okulapp.org görseli depodaki ana çizimden: 256 px, 15 px pay (kardeşin ölçüsü).

    Site ayrı depodur; betik varsayılan koşuda onu yazmaz, `--site` ile yalnız
    verilen dosyaya yazar (`docs/site-icerigi.md` §7).
    """
    hedef = IKON.write_site_image(tmp_path / "kutuphane-defteri.png")
    goruntu = _ac(hedef)

    assert goruntu.size == (256, 256)
    assert goruntu.getchannel("A").getbbox() == (15, 15, 241, 241)
    assert goruntu.tobytes() == IKON.from_master(IKON.load_tile(), 256, 15).tobytes()
    assert _opak_renkler(goruntu).most_common(1)[0][0] == LOGO.LACIVERT[:3]


# ------------------------------------------------------------- kenar boşluğu


def test_kenar_boslugu_kurali_butun_boyutlarda_aynidir() -> None:
    """Karo kenara ⌈boyut/32⌉ px saydam boşluk bırakır, 16 boşluksuzdur (logo_uret.py başlığı).

    Elle çizilmiş kesimler ile ana çizim yan yana geçer (Windows eksik boyutu bir
    üstünden küçültür); doluluk ikisinde aynı olmazsa 32 → 48 geçişinde karo sıçrar.
    """
    beklenen_bosluk = {16: 0, 24: 1, 32: 1, 48: 2, 64: 2, 128: 4, 192: 6, 256: 8, 512: 16}
    goruntuler = {b: _png(b) for b in IKON.PNG_SIZES}
    goruntuler[IKON.FRONTEND_SIZE] = _ac(APP_LOGO)

    for boyut, goruntu in goruntuler.items():
        bosluk = beklenen_bosluk[boyut]
        assert IKON.edge_margin(boyut) == bosluk
        assert goruntu.getchannel("A").getbbox() == (bosluk, bosluk, boyut - bosluk, boyut - bosluk)
        dolum = (boyut - 2 * bosluk) / boyut
        assert boyut == 16 or 0.91 <= dolum <= 0.94, (boyut, dolum)
    assert _ac(IKON.MASTER_SOURCE).getchannel("A").getbbox() == (32, 32, 992, 992)


# ---------------------------------------------------------------- piksel sondası


def test_butun_simgeler_yeni_logodur() -> None:
    """Baskın opak renk cilt laciverti, safran raf/etiket var; geçici logonun renkleri yok.

    Küçültülmüş kesimlerde ince safran raf komşu renklerle harmanlanır; bu yüzden
    safran kanal başına en çok 24 birim sapmayla aranır.
    """
    safran = LOGO.SAFRAN[:3]
    for ad, goruntu in _butun_simgeler().items():
        opak = _opak_renkler(goruntu)
        assert opak.most_common(1)[0][0] == LOGO.LACIVERT[:3], ad
        assert any(
            max(abs(r - s) for r, s in zip(renk, safran, strict=True)) <= 24 for renk in opak
        ), ad
        assert not set(opak) & ESKI_GECICI_LOGO_RENKLERI, ad


# ---------------------------------------------------------- simgenin yüzeyleri


def _metin(goreli: str) -> str:
    return (REPO / goreli).read_text(encoding="utf-8")


def test_windows_yuzeyleri_depodaki_ico_yu_kullanir() -> None:
    """exe kaynağı (spec), kurulum dosyası ve kısayollar (Inno), pencere (WinForms)."""
    spec = _metin("packaging/pyinstaller/kutuphane_defteri.spec")
    assert 'ICON = REPO / "packaging" / "ikonlar" / "kutuphane-defteri.ico"' in spec
    assert "icon=str(ICON)" in spec
    assert '(str(ICON), ".")' in spec  # pencere ikonu paket kökünde (window.py)

    iss = _metin("packaging/windows/kutuphane-defteri.iss")
    assert '#define AppIconSource "..\\ikonlar\\kutuphane-defteri.ico"' in iss
    assert "SetupIconFile={#AppIconSource}" in iss
    assert "UninstallDisplayIcon={app}\\{#AppExeName}" in iss  # exe'nin kaynağındaki ikon
    assert 'Source: "{#AppIconSource}"' in iss
    assert iss.count('IconFilename: "{app}\\{#InstalledIconName}"') == 3

    assert 'WINDOW_ICON_FILE = "kutuphane-defteri.ico"' in _metin("desktop/window.py")


def _boyut_donguleri(metin: str) -> list[list[int]]:
    return [
        [int(b) for b in eslesme.split()]
        for eslesme in re.findall(r"for boyut in ([0-9 ]+); do", metin)
    ]


def test_linux_yuzeyleri_hicolor_boyutlarini_depodan_kurar() -> None:
    """`.deb` (build.sh) ve taşınabilir arşiv (kur.sh) aynı boyutları kurar; tema adı tek.

    Pencere simgesi de bu temadan gelir: `prepare_qt_application` uygulamaya
    `QIcon.fromTheme(THEME_ICON_NAME)` atar (davranış testi `desktop/tests/test_tray.py`).
    """
    tema_adi = "kutuphane-defteri"
    tepsi = _metin("desktop/tray.py")
    assert f'THEME_ICON_NAME: Final = "{tema_adi}"' in tepsi
    assert "app.setWindowIcon(_qt_icon(qt, icon_path))" in tepsi
    assert re.search(
        rf"^Icon={tema_adi}$", _metin("packaging/linux/kutuphane-defteri.desktop"), re.M
    )

    for betik in ("packaging/linux/build.sh", "packaging/linux/kur.sh"):
        metin = _metin(betik)
        assert _boyut_donguleri(metin) == [list(IKON.ICO_SIZES)], betik
        assert "kutuphane-defteri-${boyut}.png" in metin, betik
        assert '${boyut}x${boyut}/apps"' in metin, betik
        assert '/kutuphane-defteri.png"' in metin, betik
    for boyut in IKON.ICO_SIZES:
        assert IKON.png_path(boyut).is_file()


def test_linux_kaldirma_kurulan_butun_simgeleri_siler() -> None:
    """Taşınabilir arşivin `kaldir.sh`'si `kur.sh`'nin kurduğu her boyutu siler.

    Boyut listesi değişip kaldırma güncellenmezse eski simgeler hicolor'da kalır.
    """
    metin = _metin("packaging/linux/kaldir.sh")

    assert _boyut_donguleri(metin) == [list(IKON.ICO_SIZES)]
    assert 'rm -f "$IKON_KOKU/${boyut}x${boyut}/apps/kutuphane-defteri.png"' in metin


def test_paket_derlemesi_eski_arayuz_ciktisini_kabul_etmez() -> None:
    """Vite `public/`i `dist/`e aynen kopyalar; derleme betikleri ikisini karşılaştırır.

    29.09.2026: logo değiştikten sonra yerel `frontend/dist` eski `app-logo.png`'yi
    taşıyordu; betikler yalnız `index.html`'in varlığına baktığı için yerel paket
    yeni `.ico` ile eski arayüz logosunu birlikte taşıyabilirdi.
    """
    sh = _metin("packaging/linux/build.sh")
    assert 'find "$DEPO/frontend/public" -type f -print0' in sh
    assert 'cmp -s "$kaynak" "$DEPO/frontend/dist/$goreli"' in sh

    ps1 = _metin("packaging/windows/build.ps1")
    assert "Get-ChildItem -LiteralPath $PublicKok -File -Recurse" in ps1
    assert "(Get-FileHash -LiteralPath $Hedef).Hash" in ps1
    # İki betikte de karşılaştırma, varlık denetiminden sonra ve PyInstaller'dan önce.
    assert sh.index("frontend/dist/index.html") < sh.index("cmp -s") < sh.index("pyinstaller")
    assert (
        ps1.index("frontend\\dist\\index.html")
        < ps1.index("Get-FileHash")
        < ps1.index("pyinstaller")
    )


def test_on_yuz_ve_katalog_yuzeyleri() -> None:
    """Yönetim arayüzü app-logo.png'yi kullanır; Ağ Kataloğu simge isteğini `data:,` ile kapatır."""
    assert '<link rel="icon" type="image/png" href="/app-logo.png" />' in _metin(
        "frontend/index.html"
    )
    assert _metin("frontend/src/AppShell.tsx").count('src="/app-logo.png"') == 2
    # Katalog bilinçli olarak simgesizdir: yeni uç açılmaz, sayfalar programın değil
    # okulun adını taşır (tasarım §14.1 F12 ekleri L-1).
    assert '<link rel="icon" href="data:,">' in _metin("backend/katalog/sablonlar/taban.html")
