"""LİSANS KAPISI — THIRD_PARTY_LICENSES eksiksiz mi, pakette yalnız GPL'li bileşen var mı?

Kütüphane Defteri PolyForm Noncommercial lisanslıdır; GPLv3 dağıtılan bütüne
ek kısıtlama konmasını yasakladığı için YALNIZ GPL'li bir bileşen pakete
giremez (23.09.2026 yayın denetimi; PyQt5 → PySide6). LGPL bileşenler girer
ama lisans metni ve kaynağa erişim bilgisiyle (TB28, CLAUDE.md §2-10).

Üç katman:

1. **Depo (bu dosya, çevrimdışı):** `THIRD_PARTY_LICENSES/bilesenler.json` her
   pinle AYNI sürümde, çalışma zamanı kapanışının her dağıtımı listede, npm
   bağımlılıkları listede ya da gerekçeyle dışarıda; her bileşenin lisans metni
   var, sahipsiz dosya yok; hiçbir bileşen yalnız GPL değil. Spec'in lisans
   kuralları (GPL'li Qt bağlayıcısı ve readline dışlanır, pyphen sözlükleri
   süzülür, pystray kaynak olarak toplanır) burada sabitlenir.
2. **Derleme (`lisanslar.py paket`):** paketin GERÇEKTEN içerdiği her dosyanın
   sahibi bulunur; listede olmayan dağıtım ya da GPL'li yerel kütüphane
   derlemeyi durdurur. Mantığı burada sahte TOC/RECORD/pacman verisiyle sınanır.
3. **Kurulum:** Inno `LicenseFile`, `.deb` DEP-5 `copyright` (burada metin
   düzeyinde) ve kurulum provası (`kap-ici-test.sh`).

Liste bayatlarsa: `bash packaging/lisanslar/uret.sh` (Docker, ağ gerekir).
"""

from __future__ import annotations

import ast
import importlib.metadata as im
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "packaging" / "pyinstaller" / "kutuphane_defteri.spec"
LISANSLAR = REPO / "THIRD_PARTY_LICENSES"
PAKETLEME_REQUIREMENTS = REPO / "packaging" / "requirements-paketleme.txt"
ISS = REPO / "packaging" / "windows" / "kutuphane-defteri.iss"
BUILD_SH = REPO / "packaging" / "linux" / "build.sh"
BUILD_PS1 = REPO / "packaging" / "windows" / "build.ps1"
KAP_ICI = REPO / "packaging" / "linux" / "kap-ici-test.sh"


def _yukle(yol: Path, ad: str) -> ModuleType:
    """Betiği modül olarak yükler (dataclass'lar `sys.modules` kaydı ister)."""
    spec = importlib.util.spec_from_file_location(ad, yol)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[ad] = modul
    spec.loader.exec_module(modul)
    return modul


L: Any = _yukle(REPO / "packaging" / "lisanslar" / "lisanslar.py", "kd_lisanslar")
BILESENLER: list[Any] = L.bilesenleri_oku(LISANSLAR)
PYTHON = {L.normal_ad(b.ad): b for b in BILESENLER if b.tur == "python"}
NPM = {b.ad: b for b in BILESENLER if b.tur == "npm"}

#: GPL'li Qt bağlayıcıları (23.09.2026 yayın denetimi). PyQt5/PyQt6 GPLv3,
#: PySide2/PySide6 LGPLv3'tür; GPL'li bağlayıcı pakete GİREMEZ.
GPL_QT_BAGLAYICILARI = ("PyQt5", "PyQt6", "PyQtWebEngine")

#: package.json `dependencies`'te olup ön yüz ÇIKTISINA girmeyen paketler.
#: Yeni satır gerekçesiyle eklenir; listeye bilinçsiz ekleme kapıyı deler.
PAKETLENMEYEN_NPM = {
    "zod": "yalnız tip olarak import edilir (`import type { ZodType }`), çıktıya kod girmez",
}


# ---------------------------------------------------------------- spec kuralları


def _spec_agaci() -> ast.Module:
    return ast.parse(SPEC.read_text(encoding="utf-8"))


def _spec_taban_excludes() -> set[str]:
    """spec'teki koşulsuz `excludes = [...]` atamasının dize öğeleri."""
    for dugum in ast.walk(_spec_agaci()):
        if (
            isinstance(dugum, ast.Assign)
            and any(isinstance(h, ast.Name) and h.id == "excludes" for h in dugum.targets)
            and isinstance(dugum.value, ast.List)
        ):
            return {
                oge.value
                for oge in dugum.value.elts
                if isinstance(oge, ast.Constant) and isinstance(oge.value, str)
            }
    raise AssertionError("spec'te `excludes = [...]` ataması bulunamadı (desen değişti mi?)")


def test_gpl_lisansli_qt_baglayicisi_paketlenmez() -> None:
    """GPLv3'lü PyQt ne kurulur ne de pakete girer (PySide6 LGPLv3'tür)."""
    pinler = {ad.casefold() for ad, _surum, _p in L.pinler(PAKETLEME_REQUIREMENTS)}
    yasak = {ad.casefold() for ad in GPL_QT_BAGLAYICILARI}
    assert not (pinler & yasak), f"GPLv3 lisanslı Qt bağlayıcısı pinlenmiş: {pinler & yasak}"
    assert {"PyQt5", "PyQt6", "PySide2"} <= _spec_taban_excludes()
    spec_metni = SPEC.read_text(encoding="utf-8")
    # Dışlamak tek başına yetmez: Linux zinciri gerçekten PySide6'dan kurulmalı.
    assert '"PySide6.QtWebEngineWidgets"' in spec_metni
    assert '"qtpy"' in spec_metni


def test_gpl_readline_eklentisi_paketlenmez() -> None:
    """27.09.2026 yerel Linux derlemesi: stdlib `readline` libreadline.so.8'i (GPL-3.0)
    pakete taşıyordu. spec onu KOŞULSUZ dışlar; derleme sonrası denetim ikinci
    sigortadır (`YASAK_YEREL`)."""
    assert "readline" in _spec_taban_excludes()
    for ad in ("libreadline.so.8", "libgdbm.so.6", "libgdbm_compat.so.4", "libhistory.so.8"):
        assert L.YASAK_YEREL.match(ad), ad
    for ad in ("libpango-1.0.so.0", "libreadlinex.so", "librl.so"):
        assert not L.YASAK_YEREL.match(ad), ad


def test_pyphen_sozlukleri_spec_ile_denetim_ayni_kumeyi_birakir() -> None:
    """hook-pyphen BÜTÜN sözlükleri toplar, bir kısmı yalnız GPL'dir: spec süzer,
    derleme denetimi aynı kümeyle doğrular."""
    for dugum in ast.walk(_spec_agaci()):
        if (
            isinstance(dugum, ast.Assign)
            and any(isinstance(h, ast.Name) and h.id == "PYPHEN_KALAN" for h in dugum.targets)
            and isinstance(dugum.value, ast.Set)
        ):
            kalan = {
                e.value
                for e in dugum.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
            break
    else:
        raise AssertionError("spec'te PYPHEN_KALAN yok")
    assert kalan == set(L.PYPHEN_IZINLI)
    assert "a.datas = [oge for oge in a.datas if not _pyphen_sozlugu_atilir(oge[0])]" in (
        SPEC.read_text(encoding="utf-8")
    )
    # Kalan sözlüğün bildirimi lisans dizininde.
    assert "python-pyphen-pyphen_dictionaries_README_hyph_en_US.txt" in PYTHON["pyphen"].dosyalar


def test_pystray_kaynak_dosya_olarak_toplanir() -> None:
    """LGPLv3: pystray PYZ bayt kodu değil, `_internal/pystray/*.py` olarak pakete girer."""
    spec_metni = SPEC.read_text(encoding="utf-8")
    assert 'module_collection_mode = {"pystray": "py"} if WINDOWS else {}' in spec_metni
    assert "module_collection_mode=module_collection_mode" in spec_metni
    pystray = PYTHON["pystray"]
    assert pystray.kaynagi_pakette is True
    assert pystray.platformlar == ["windows"]


# ------------------------------------------------------------ liste eksiksizliği


def test_her_backend_pini_listede_ayni_surumle() -> None:
    eksik: list[str] = []
    for ad, surum, platformlar in L.pinler(L.BACKEND_GEREKSINIMLERI):
        kayit = PYTHON.get(L.normal_ad(ad))
        if kayit is None or kayit.surum != surum or not set(platformlar) <= set(kayit.platformlar):
            eksik.append(
                f"{ad}=={surum} {platformlar} → {kayit and (kayit.surum, kayit.platformlar)}"
            )
    assert eksik == [], (
        "THIRD_PARTY_LICENSES backend/requirements.txt ile ayrıştı "
        f"(`bash packaging/lisanslar/uret.sh`): {eksik}"
    )


def test_her_paketleme_pini_listede_ayni_surum_ve_platformla() -> None:
    eksik: list[str] = []
    for ad, surum, platformlar in L.pinler(PAKETLEME_REQUIREMENTS):
        kayit = PYTHON.get(L.normal_ad(ad))
        if kayit is None or kayit.surum != surum or not set(platformlar) <= set(kayit.platformlar):
            eksik.append(f"{ad}=={surum} {platformlar}")
    assert eksik == [], f"requirements-paketleme.txt ile ayrıştı: {eksik}"
    # PySide6 zinciri: dört dağıtım da listede ve yalnız Linux.
    for ad in ("pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"):
        assert PYTHON[ad].platformlar == ["linux"], ad


def test_calisma_zamani_kapanisinin_her_dagitimi_listede() -> None:
    """Geliştirme kabına KURULU backend kapanışı (Linux işaretleriyle) listede olmalı.

    Pinlerin geçişli bağımlılıkları (asgiref, tinycss2, cffi …) pinlenmez; yeni
    bir geçişli bağımlılık listeye girmeden pakete girerse derleme de durur
    (`lisanslar.py paket`), ama bu kapı onu saniyeler içinde yakalar.
    """
    gorulen = _kurulu_kapanis()
    eksik = sorted(n for n in gorulen if n not in PYTHON or "linux" not in PYTHON[n].platformlar)
    assert eksik == [], f"çalışma zamanı kapanışında olup listede olmayanlar: {eksik}"


def _kurulu_kapanis() -> set[str]:
    """Kurulu backend kapanışı; EKLER izlenir (`fonttools[woff]` → brotli, zopfli).

    İşaretler her ek için `extra=<ek>` ile değerlendirilir (`lisanslar.Uretici.coz`
    ile aynı kural). F12 düzeltme turu: gezinme yalnız istek adını kuyruğa alıp
    `extra=''` ile değerlendirdiği için ek üzerinden gelen dağıtımlar hiç gezilmiyordu.
    """
    from packaging.requirements import Requirement

    ortam = {**L._ORTAK_ORTAM, **L._ORTAMLAR["linux"]}
    kuyruk: list[tuple[str, frozenset[str]]] = [
        (ad, frozenset()) for ad, _s, _p in L.pinler(L.BACKEND_GEREKSINIMLERI)
    ]
    islenen: set[tuple[str, frozenset[str]]] = set()
    gorulen: set[str] = set()
    while kuyruk:
        ad, ekler = kuyruk.pop()
        n = L.normal_ad(ad)
        gorulen.add(n)
        if (n, ekler) in islenen:
            continue
        islenen.add((n, ekler))
        for ham in im.distribution(n).requires or []:
            istek = Requirement(ham)
            if istek.marker is None or any(
                istek.marker.evaluate({**ortam, "extra": ek}) for ek in (ekler or {""})
            ):
                kuyruk.append((istek.name, frozenset(istek.extras)))
    return gorulen


def test_kapanis_ekler_uzerinden_gelen_dagitimlari_da_gezer() -> None:
    """weasyprint → `fonttools[woff]` → brotli ve zopfli (ek üzerinden)."""
    gorulen = _kurulu_kapanis()
    assert {"fonttools", "brotli", "zopfli"} <= gorulen


def test_npm_bagimliliklari_listede_ya_da_gerekceyle_disarida() -> None:
    paket = json.loads((REPO / "frontend" / "package.json").read_text(encoding="utf-8"))
    kilit = json.loads((REPO / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    for ad in paket["dependencies"]:
        assert ad in NPM or ad in PAKETLENMEYEN_NPM, (
            f"{ad} ne ön yüz lisans listesinde ne PAKETLENMEYEN_NPM'de "
            "(`bash packaging/lisanslar/uret.sh`)"
        )
        assert not (ad in NPM and ad in PAKETLENMEYEN_NPM), ad
    # Listedeki her npm paketinin sürümü kilit dosyasındakiyle aynı.
    for ad, kayit in NPM.items():
        kilitli = kilit["packages"].get(f"node_modules/{ad}", {}).get("version")
        assert kilitli == kayit.surum, f"{ad}: listede {kayit.surum}, kilitte {kilitli}"


# ------------------------------------------------------------- lisans ifadeleri


def test_hicbir_bilesen_yalniz_gpl_degil() -> None:
    gpl = [f"{b.ad}: {b.etkin_lisans}" for b in BILESENLER if L.gpl_yalniz_mi(b.etkin_lisans)]
    assert gpl == [], f"yalnız GPL lisanslı bileşen pakete giremez: {gpl}"


def test_secilen_lisans_seceneklerden_biri_ve_gpl_degil() -> None:
    for b in BILESENLER:
        if b.secilen:
            assert b.secilen in L.secenekler(b.lisans), (b.ad, b.secilen, b.lisans)
            assert not L.gpl_yalniz_mi(b.secilen), b.ad
    # Qt zinciri ve pystray LGPL seçeneğiyle dağıtılır.
    for ad in ("pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"):
        assert PYTHON[ad].secilen == "LGPL-3.0-only", ad


@pytest.mark.parametrize(
    ("ifade", "gpl"),
    [
        ("MIT", False),
        ("GPL-3.0-only", True),
        ("AGPL-3.0-or-later", True),
        ("LGPL-3.0-only", False),
        ("GPL-2.0-or-later WITH Bootloader-exception", False),
        ("GPL-3.0-or-later WITH GCC-exception-3.1", False),
        ("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", False),
        ("GPL-2.0-or-later OR LGPL-2.1-or-later OR MPL-1.1", False),
        ("GPL-2.0-only OR GPL-3.0-only", True),
        ("MIT AND GPL-3.0-only", True),
        ("(MIT OR Apache-2.0) AND BSD-3-Clause", False),
        ("(GPL-2.0-only OR MIT) AND (GPL-3.0-only OR BSD-2-Clause)", False),
        ("LicenseRef-Microsoft-WebView2-Runtime", False),
    ],
)
def test_gpl_degerlendirmesi(ifade: str, gpl: bool) -> None:
    assert L.gpl_yalniz_mi(ifade) is gpl


@pytest.mark.parametrize("bozuk", ["", "MIT OR", "(MIT", "MIT)", "AND MIT", "MIT; GPL"])
def test_bozuk_lisans_ifadesi_reddedilir(bozuk: str) -> None:
    with pytest.raises(L.SpdxHatasi):
        L.gpl_yalniz_mi(bozuk)


def test_her_bilesenin_lisans_ifadesi_ayristirilir() -> None:
    for b in BILESENLER:
        L.gpl_yalniz_mi(b.lisans)  # SpdxHatasi yükseltmemeli


# ------------------------------------------------------------ dosya bütünlüğü


def test_her_bilesenin_lisans_metni_var_ve_sahipsiz_dosya_yok() -> None:
    dosyalar = {p.name for p in LISANSLAR.iterdir() if p.is_file()}
    anilan: set[str] = set()
    for b in BILESENLER:
        assert b.dosyalar, f"{b.ad}: lisans dosyası yok"
        for ad in b.dosyalar:
            yol = LISANSLAR / ad
            assert yol.is_file(), f"{b.ad}: {ad} dizinde yok"
            assert yol.stat().st_size > 20, f"{b.ad}: {ad} boş"
            anilan.add(ad)
    sahipsiz = dosyalar - anilan - {L.DIZIN_DOSYASI, L.BENIOKU_ADI}
    assert sahipsiz == set(), f"hiçbir bileşenin anmadığı dosyalar: {sorted(sahipsiz)}"
    # Derlemede eklenenler depodaki kopyada BULUNMAZ.
    assert not (LISANSLAR / L.PAKET_ICERIGI_ADI).exists()
    assert not (LISANSLAR / L.YEREL_DIZIN_ADI).exists()


def test_ortak_lgpl_ve_gpl_metinleri_gercek_surum_3() -> None:
    lgpl = (LISANSLAR / "LGPL-3.0-metni.txt").read_text(encoding="utf-8")
    gpl = (LISANSLAR / "GPL-3.0-metni.txt").read_text(encoding="utf-8")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in lgpl and "Version 3, 29 June 2007" in lgpl
    assert "GNU GENERAL PUBLIC LICENSE" in gpl and "Version 3, 29 June 2007" in gpl
    for ad in ("pystray", "pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6"):
        assert set(PYTHON[ad].dosyalar) == {"LGPL-3.0-metni.txt", "GPL-3.0-metni.txt"}, ad


def test_benioku_her_bileseni_ve_lgpl_kaynak_bilgisini_tasir() -> None:
    metin = (LISANSLAR / L.BENIOKU_ADI).read_text(encoding="utf-8")
    for b in BILESENLER:
        assert f"  {L.benioku_basligi(b)}\n" in metin, b.ad
    # LGPL kaynağına erişim (TB28): pystray pakette, Qt/PySide6 tam sürüm adresi.
    assert "_internal\\pystray\\" in metin
    assert "qt-everywhere-src-6.8.3.tar.xz" in metin
    assert "pyside-setup-everywhere-src-6.8.3.tar.xz" in metin
    assert L.YEREL_DIZIN_ADI in metin
    # "Qt'nin tamamı LGPL" denmez: yalnız GPL'li modüllerin pakete girmediği yazılır.
    assert "YALNIZ GPL-3.0 ile sunulan" in metin and "pakete girmez" in metin
    assert L.ICU_DOSYASI in metin and L.QT_UCUNCU_TARAF_DOSYASI in metin


def test_benioku_ureticinin_ciktisiyla_birebir() -> None:
    """Dizin elle düzenlenmez (CLAUDE.md §2-10): depodaki `BENIOKU.txt` üreticinin
    `bilesenler.json`'dan ürettiği metinle birebir aynıdır. Üreticinin metni değişip
    `uret.sh` koşulmazsa ya da dosya elle düzeltilirse kapı kırılır."""
    metin = (LISANSLAR / L.BENIOKU_ADI).read_text(encoding="utf-8")
    assert metin == L.benioku_metni(BILESENLER)


def _tr_kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def test_benioku_lgpl_kaynagi_icin_yazili_teklif_tasir() -> None:
    """KB-1 (28.09.2026 kullanıcı kararı, beta): LGPL-2.1 madde 6(c) yazılı teklifi (GPL-3.0
    madde 6(b) fiziksel taşıyıcıda; ağdan dağıtımda 6(d)) — en az üç yıl, ücretsiz ya da en
    çok gönderim maliyetine, iletişim yolu GitHub deposunun Issues sayfası. Teklifte
    e-posta, kişi adı, unvan ve kurum adı yoktur."""
    metin = (LISANSLAR / L.BENIOKU_ADI).read_text(encoding="utf-8")
    teklif = metin[metin.index(L.TEKLIF_BASLIGI) : metin.index("\nOrtak metinler:")]
    for beklenen in (
        "EN AZ ÜÇ YIL",
        "beta sürümleri dahil",
        "LGPL-2.1 madde 6(c)",
        "Kaynak ücretsiz verilir",
        "maliyetini aşmaz",
        f"    {L.KAYNAK_TEKLIF_ADRESI}\n",
        L.PAKET_ICERIGI_ADI,
        f"{L.YEREL_DIZIN_ADI}/",
    ):
        assert beklenen in teklif, beklenen
    # KB-1 düzeltme turu (29.09.2026): GPL-3.0 md. 6(b) (yazılı teklif) yalnız fiziksel
    # taşıyıcıyla dağıtımı kapsar; program ağdan dağıtıldığı için LGPL-3.0 bileşenlerinde
    # md. 6(d) geçerlidir (aynı yerden ya da nesne kodunun yanındaki açık yönlendirme).
    tek_satir = " ".join(teklif.split())
    for beklenen in (
        "fiziksel bir taşıyıcıyla dağıtılırsa GPL-3.0 madde 6(b)",
        "Ağdan dağıtımda LGPL-3.0 bileşenleri için GPL-3.0 madde 6(d) geçerlidir",
        "her sürümün Release notu bu dosyaya ve kaynak adreslerine yönlendirir",
    ):
        assert beklenen in tek_satir, beklenen
    assert "LGPL-3.0 bileşenleri için GPL-3.0 madde 6(b)" not in tek_satir
    # Pakete giren her LGPL bileşen sürümüyle teklifte; Qt kitaplıkları PySide6'nın sürümüyle.
    lgpl = [b for b in BILESENLER if b.tur == "python" and "LGPL" in b.etkin_lisans]
    assert {L.normal_ad(b.ad) for b in lgpl} >= {"pystray", "pyside6", "shiboken6"}
    for b in lgpl:
        assert f"  - {L.benioku_basligi(b)} (" in teklif, b.ad
    assert f"Qt {PYTHON['pyside6'].surum} kitaplıkları" in teklif
    # İletişim yolu yalnız depo: e-posta yok; telif sahibinin adı, unvan ve kurum adı yok.
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", metin)
    govde = _tr_kucuk(teklif.replace(L.KAYNAK_TEKLIF_ADRESI, ""))
    sozcukler = set(re.findall(r"\w+", govde))
    telif_sahibi = re.sub(r"^\d+\s+|\s*<.*$", "", L.TELIF)
    for ad in telif_sahibi.split():
        assert _tr_kucuk(ad) not in sozcukler, "teklifte kişi adı"
    for unvan_ya_da_kurum in ("öğretmen", "müdür", "lisesi", "ortaokulu"):
        assert unvan_ya_da_kurum not in govde, unvan_ya_da_kurum


def test_teklifin_deposu_guncelleme_deposu_ve_deb_iletisim_adresiyle_ayni() -> None:
    """Teklifin iletişim yolu programın gerçekten yayımlandığı depodur: güncelleme
    denetiminin varsayılan deposu ve `.deb` `copyright`'ın `Upstream-Contact`'ı aynıdır."""
    updates = (REPO / "backend" / "apps" / "okul" / "services" / "updates.py").read_text(
        encoding="utf-8"
    )
    varsayilan = re.search(r'"KD_UPDATE_REPOSITORY",\s*"([^"]+)"', updates)
    assert varsayilan, "updates.py'de varsayılan depo bulunamadı (desen değişti mi?)"
    assert f"https://github.com/{varsayilan.group(1)}" == L.DEPO_ADRESI
    assert f"{L.DEPO_ADRESI}/issues" == L.KAYNAK_TEKLIF_ADRESI
    deb = L.deb_copyright((REPO / "LICENSE").read_text(encoding="utf-8"))
    assert f"Upstream-Contact: {L.KAYNAK_TEKLIF_ADRESI}\n" in deb
    assert f"Source: {L.DEPO_ADRESI}\n" in deb
    assert "yazılı teklif BENIOKU.txt'dedir" in deb


def test_benioku_sayisal_olmayan_surumu_parantezle_yazar() -> None:
    """F12 düzeltme turu: "önyükleyicisi derlemede indirilen" yarım cümle gibi okunuyordu."""
    bilesen = L.Bilesen(
        ad="Örnek önyükleyici",
        surum="derlemede indirilen güncel sürüm",
        tur="ikili",
        platformlar=["windows"],
        lisans="MIT",
        dosyalar=["x.txt"],
    )
    assert L.benioku_basligi(bilesen) == (
        "Örnek önyükleyici (sürüm: derlemede indirilen güncel sürüm)"
    )
    assert L.benioku_basligi(_bilesen("Django", "5.1.15")) == "Django 5.1.15"
    metin = (LISANSLAR / L.BENIOKU_ADI).read_text(encoding="utf-8")
    for b in BILESENLER:
        if not b.surum[:1].isdigit():
            assert f"{b.ad} {b.surum}" not in metin, b.ad


def test_qt_ile_gelen_icu_ve_ucuncu_taraf_bildirimi_linux_listesinde() -> None:
    """ICU ayrı kitaplık olarak Linux paketindedir; lisansı telif ve izin metninin
    kopyalarla verilmesini ister (F12 düzeltme turu)."""
    icu = next(b for b in BILESENLER if b.ad.startswith("ICU "))
    assert (icu.surum, icu.platformlar, icu.dosyalar) == (
        L.ICU_SURUMU,
        ["linux"],
        [L.ICU_DOSYASI],
    )
    icu_metni = (LISANSLAR / L.ICU_DOSYASI).read_text(encoding="utf-8")
    assert "UNICODE" in icu_metni.upper() and "PERMISSION IS HEREBY GRANTED" in icu_metni.upper()
    qt = next(b for b in BILESENLER if b.dosyalar == [L.QT_UCUNCU_TARAF_DOSYASI])
    assert qt.platformlar == ["linux"]
    not_metni = (LISANSLAR / L.QT_UCUNCU_TARAF_DOSYASI).read_text(encoding="utf-8")
    assert "qtwebengine-licensing" in not_metni and "licenses-used-in-qt" in not_metni


def test_elle_bilesenler_listede() -> None:
    adlar = {b.ad for b in BILESENLER}
    assert {
        "Python (CPython)",
        "DejaVu Sans",
        "Microsoft Edge WebView2 SDK",
        "Microsoft Edge WebView2 Evergreen önyükleyicisi",
        "material-symbols",
        "tailwindcss",
    } <= adlar
    dejavu = next(b for b in BILESENLER if b.ad == "DejaVu Sans")
    assert (LISANSLAR / dejavu.dosyalar[0]).read_text(encoding="utf-8") == (
        REPO / "packaging" / "fontlar" / "DejaVu-LISANS.txt"
    ).read_text(encoding="utf-8")


def test_lisans_betigi_derleme_ortaminda_yalniz_standart_kitaplik_ister() -> None:
    """`paket` alt komutu derleme ortamında koşar: modül düzeyinde üçüncü taraf import YOK
    (`packaging` yalnız `uret`'in içinde, tembel)."""
    agac = ast.parse((REPO / "packaging" / "lisanslar" / "lisanslar.py").read_text("utf-8"))
    ust_duzey: set[str] = set()
    for dugum in agac.body:
        if isinstance(dugum, ast.Import):
            ust_duzey |= {a.name.split(".")[0] for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module and dugum.level == 0:
            ust_duzey.add(dugum.module.split(".")[0])
    assert ust_duzey - {"__future__"} <= set(sys.stdlib_module_names), ust_duzey


# ------------------------------------------------------ derleme denetimi mantığı


def _bilesen(
    ad: str, surum: str = "1.0", platformlar: tuple[str, ...] = ("linux", "windows")
) -> Any:
    return L.Bilesen(
        ad=ad,
        surum=surum,
        tur="python",
        platformlar=list(platformlar),
        lisans="MIT",
        dosyalar=["x.txt"],
    )


def test_toc_dosyalarindan_kaynak_yollar_okunur(tmp_path: Path) -> None:
    (tmp_path / "PYZ-00.toc").write_text(
        repr(
            (
                "/x/PYZ-00.pyz",
                [
                    ("django", "/sp/django/__init__.py", "PYMODULE"),
                    ("ns", None, "PYMODULE"),
                    ("goreli", "goreli.py", "PYMODULE"),
                ],
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "Analysis-00.toc").write_text(
        repr(
            (
                ["/repo/giris.py"],
                [("libz.so.1", "/lib/libz.so.1", "BINARY"), ("a", "b", "SYMLINK")],
                {"x": [("d/f.txt", "/sp/d/f.txt", "DATA")]},
                False,
            )
        ),
        encoding="utf-8",
    )
    assert L.toc_kaynaklari(tmp_path) == {"/sp/django/__init__.py", "/lib/libz.so.1", "/sp/d/f.txt"}


def test_toc_yoksa_denetim_durur(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        L.toc_kaynaklari(tmp_path)


def _denetle(tmp_path: Path, kaynaklar: list[str], **ek: Any) -> Any:
    calisma = tmp_path / "calisma"
    calisma.mkdir(exist_ok=True)
    varsayilan: dict[str, Any] = {
        "bilesenler": [_bilesen("Django", "5.1.15"), _bilesen("pystray", "0.19.5", ("windows",))],
        "platform": "linux",
        "calisma": calisma,
        "harita": {},
        "python_kokleri": [str(tmp_path / "py")],
        "site_dizinleri": [str(tmp_path / "py" / "site-packages")],
    }
    varsayilan.update(ek)
    return L.paketi_denetle(kaynaklar=kaynaklar, **varsayilan)


def test_listedeki_dagitim_ve_python_kendi_dosyalari_gecer(tmp_path: Path) -> None:
    django = str(tmp_path / "py" / "site-packages" / "django" / "__init__.py")
    harita = {L._normal_yol(django): ("Django", "5.1.15", "django/__init__.py")}
    sonuc = _denetle(
        tmp_path,
        [django, str(tmp_path / "py" / "lib" / "json" / "__init__.py"), str(REPO / "VERSION")],
        harita=harita,
    )
    assert sonuc.hatalar == [] and sonuc.uyarilar == []
    assert sonuc.python == {"django": ("Django", "5.1.15")}
    assert sonuc.proje == 1


def test_listede_olmayan_dagitim_derlemeyi_durdurur(tmp_path: Path) -> None:
    yol = str(tmp_path / "py" / "site-packages" / "yeni" / "__init__.py")
    sonuc = _denetle(
        tmp_path, [yol], harita={L._normal_yol(yol): ("yeni-paket", "2.0", "yeni/__init__.py")}
    )
    assert any("THIRD_PARTY_LICENSES'ta olmayan" in h and "yeni-paket" in h for h in sonuc.hatalar)


def test_pyinstaller_yalniz_gomulebilir_dosyalariyla_girer(tmp_path: Path) -> None:
    """Önyükleyici/loader (istisnalı GPL) ve rthooks/fake-modules (Apache) girer;
    derleme kodu (istisnasız GPL-2.0+) ve contrib'in standart kancaları girmez.
    27.09.2026 derlemesinde `webview.__pyinstaller` kancası derleme kodunu sürüklüyordu."""
    bilesenler = [
        _bilesen("pyinstaller", "6.11.1"),
        _bilesen("pyinstaller-hooks-contrib", "2026.7"),
    ]
    goreliler = {
        "PyInstaller/loader/pyiboot01_bootstrap.py": True,
        "PyInstaller/hooks/rthooks/pyi_rth_inspect.py": True,
        "PyInstaller/fake-modules/_pyi_rth_utils/__init__.py": True,
        "_pyinstaller_hooks_contrib/rthooks/pyi_rth_cryptography_openssl.py": True,
        "PyInstaller/utils/hooks/__init__.py": False,
        "PyInstaller/lib/modulegraph/modulegraph.py": False,
        "_pyinstaller_hooks_contrib/stdhooks/hook-pyphen.py": False,
    }
    harita = {}
    for goreli in goreliler:
        dagitim = "pyinstaller-hooks-contrib" if goreli.startswith("_py") else "pyinstaller"
        harita[L._normal_yol(tmp_path / "sp" / goreli)] = (dagitim, "x", goreli)
    sonuc = _denetle(
        tmp_path,
        [str(tmp_path / "sp" / g) for g in goreliler],
        harita=harita,
        bilesenler=bilesenler,
    )
    reddedilen = sorted(g for g, izinli in goreliler.items() if not izinli)
    assert sorted(h.split(": ", 1)[1].split(" — ")[0] for h in sonuc.hatalar) == reddedilen


def test_surum_ve_platform_farki_yalniz_uyaridir(tmp_path: Path) -> None:
    django = str(tmp_path / "d.py")
    pystray = str(tmp_path / "p.py")
    harita = {
        L._normal_yol(django): ("Django", "5.1.16", "django/d.py"),
        L._normal_yol(pystray): ("pystray", "0.19.5", "pystray/p.py"),
    }
    sonuc = _denetle(tmp_path, [django, pystray], harita=harita)
    assert sonuc.hatalar == []
    assert len(sonuc.uyarilar) == 2


def test_recordsuz_site_packages_dosyasi_ve_sahipsiz_dosya_hatadir(tmp_path: Path) -> None:
    sonuc = _denetle(
        tmp_path,
        [str(tmp_path / "py" / "site-packages" / "kacak.py"), "/opt/bilinmeyen/libx.so"],
    )
    assert len(sonuc.hatalar) == 2
    assert any("RECORD" in h and "kacak.py" in h for h in sonuc.hatalar)
    assert any("sahibi ve lisansı belirlenemeyen" in h and "libx.so" in h for h in sonuc.hatalar)


def test_gpl_yerel_kutuphane_derlemeyi_durdurur(tmp_path: Path) -> None:
    sonuc = _denetle(tmp_path, ["/lib/x86_64-linux-gnu/libreadline.so.8"])
    assert len(sonuc.hatalar) == 1 and "GPL" in sonuc.hatalar[0]


def _sahte_msys2(kok: Path) -> None:
    def paket(ad: str, surum: str, lisans: str, dosyalar: list[str]) -> None:
        dizin = kok / "var" / "lib" / "pacman" / "local" / f"{ad}-{surum}"
        dizin.mkdir(parents=True)
        (dizin / "desc").write_text(
            f"%NAME%\n{ad}\n\n%VERSION%\n{surum}\n\n%BASE%\n"
            f"{ad.replace('x86_64-', '')}\n\n%LICENSE%\n{lisans}\n\n",
            encoding="utf-8",
        )
        (dizin / "files").write_text("%FILES%\n" + "\n".join(dosyalar) + "\n", encoding="utf-8")
        for dosya in dosyalar:
            if not dosya.endswith("/"):
                (kok / dosya).parent.mkdir(parents=True, exist_ok=True)
                (kok / dosya).write_text("lisans", encoding="utf-8")

    paket(
        "mingw-w64-x86_64-pango",
        "1.54.0-1",
        "spdx:LGPL-2.1-or-later",
        [
            "mingw64/",
            "mingw64/bin/libpango-1.0-0.dll",
            "mingw64/share/licenses/pango/COPYING",
        ],
    )
    paket("mingw-w64-x86_64-lisanssiz", "1-1", "custom", ["mingw64/bin/libsahipsiz-1.dll"])


def test_msys2_veritabani_dll_sahibini_lisansini_ve_kaynagini_verir(tmp_path: Path) -> None:
    _sahte_msys2(tmp_path)
    vt = L.msys2_veritabani(tmp_path)
    pango = vt["mingw64/bin/libpango-1.0-0.dll"]
    assert (pango.ad, pango.surum, pango.lisans) == (
        "mingw-w64-x86_64-pango",
        "1.54.0-1",
        "LGPL-2.1-or-later",
    )
    assert (
        pango.kaynak == "https://repo.msys2.org/mingw/sources/mingw-w64-pango-1.54.0-1.src.tar.zst"
    )
    assert [p.name for p in pango.lisans_dosyalari] == ["COPYING"]


def test_msys2_dll_denetimi(tmp_path: Path) -> None:
    kok = tmp_path / "msys64"
    _sahte_msys2(kok)
    dll = tmp_path / "dll"
    sonuc = _denetle(
        tmp_path,
        [str(dll / "libpango-1.0-0.dll"), str(dll / "libsahipsiz-1.dll"), str(dll / "libyok.dll")],
        platform="windows",
        dll_dizini=dll,
        msys2=L.msys2_veritabani(kok),
    )
    assert set(sonuc.yerel) == {"mingw-w64-x86_64-pango", "mingw-w64-x86_64-lisanssiz"}
    assert sorted(sonuc.hatalar) == [
        "MSYS2 sahibi bulunamayan DLL: libyok.dll",
        "mingw-w64-x86_64-lisanssiz: lisans/telif dosyası bulunamadı",
    ]


def test_msys2_agacindan_dogrudan_toplanan_dll_de_sahiplenilir(tmp_path: Path) -> None:
    """build.ps1 mingw64\\bin'i PATH'e ekler; PyInstaller bir DLL'i kapanış dizini yerine
    doğrudan MSYS2 ağacından toplarsa sahibi yine pacman veritabanından bulunur."""
    kok = tmp_path / "msys64"
    _sahte_msys2(kok)
    sonuc = _denetle(
        tmp_path,
        [str(kok / "mingw64" / "bin" / "libpango-1.0-0.dll"), str(kok / "usr" / "bin" / "x.dll")],
        platform="windows",
        msys2=L.msys2_veritabani(kok),
        msys2_kok=kok,
    )
    assert set(sonuc.yerel) == {"mingw-w64-x86_64-pango"}
    assert len(sonuc.hatalar) == 1 and "MSYS2 sahibi bulunamayan dosya" in sonuc.hatalar[0]


def test_msys2_veritabani_yoksa_durur(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        L.msys2_veritabani(tmp_path)


def test_windows_sistem_dizininden_yalniz_microsoft_calisma_zamani_kabul_edilir(
    tmp_path: Path,
) -> None:
    sistem = tmp_path / "Windows"
    sonuc = _denetle(
        tmp_path,
        [str(sistem / "System32" / "MSVCP140.dll"), str(sistem / "System32" / "user32.dll")],
        platform="windows",
        sistem_dizini=str(sistem),
    )
    assert sonuc.microsoft == {"MSVCP140.dll"}
    assert len(sonuc.hatalar) == 1 and "user32.dll" in sonuc.hatalar[0]


def test_paket_dizini_denetimi_lgpl_kaynagi_ve_sozlukler(tmp_path: Path) -> None:
    bilesenler = [
        L.Bilesen(
            ad="pystray",
            surum="0.19.5",
            tur="python",
            platformlar=["windows"],
            lisans="LGPL-3.0-or-later",
            dosyalar=["x"],
            kaynagi_pakette=True,
        )
    ]
    sozluk = tmp_path / "_internal" / "pyphen" / "dictionaries"
    sozluk.mkdir(parents=True)
    for ad in L.PYPHEN_IZINLI:
        (sozluk / ad).write_text("x", encoding="utf-8")
    # Linux'ta pystray aranmaz; izinli sözlükler temizdir.
    assert L.paket_dizini_denetimi(tmp_path, bilesenler, "linux") == []
    hatalar = L.paket_dizini_denetimi(tmp_path, bilesenler, "windows")
    assert len(hatalar) == 1 and "pystray/__init__.py" in hatalar[0]
    (tmp_path / "_internal" / "pystray").mkdir()
    (tmp_path / "_internal" / "pystray" / "__init__.py").write_text("", encoding="utf-8")
    (sozluk / "hyph_gl.dic").write_text("x", encoding="utf-8")
    hatalar = L.paket_dizini_denetimi(tmp_path, bilesenler, "windows")
    assert len(hatalar) == 1 and "pyphen" in hatalar[0]


# ------------------------------------- Qt'nin yalnız GPL'li modülleri (F12 düzeltme turu)


def _sahte_elf(yol: Path, gerekenler: list[str]) -> None:
    """DT_NEEDED taşıyan en küçük 64 bit little-endian ELF (başlık + iki bölüm)."""
    dizge = b"\0" + b"".join(ad.encode() + b"\0" for ad in gerekenler)
    konumlar, konum = [], 1
    for ad in gerekenler:
        konumlar.append(konum)
        konum += len(ad.encode()) + 1
    dinamik = b"".join(struct.pack("<qQ", 1, k) for k in konumlar) + struct.pack("<qQ", 0, 0)
    dizge_konumu = 64
    dinamik_konumu = (dizge_konumu + len(dizge) + 7) // 8 * 8
    bolum_konumu = dinamik_konumu + len(dinamik)
    baslik = bytearray(64)
    baslik[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", baslik, 0x28, bolum_konumu)
    struct.pack_into("<HHH", baslik, 0x3A, 64, 3, 0)
    bolumler = [
        struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        struct.pack("<IIQQQQIIQQ", 0, 3, 0, 0, dizge_konumu, len(dizge), 0, 0, 1, 0),
        struct.pack("<IIQQQQIIQQ", 0, 6, 0, 0, dinamik_konumu, len(dinamik), 1, 0, 8, 16),
    ]
    govde = bytes(baslik) + dizge
    govde += b"\0" * (dinamik_konumu - len(govde)) + dinamik + b"".join(bolumler)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(govde)


def test_elf_gereksinimleri_okunur_elf_olmayan_none(tmp_path: Path) -> None:
    _sahte_elf(tmp_path / "libx.so", ["libQt6Core.so.6", "libc.so.6"])
    assert L.elf_gereksinimleri(tmp_path / "libx.so") == ["libQt6Core.so.6", "libc.so.6"]
    (tmp_path / "metin.txt").write_text("ELF değil", encoding="utf-8")
    assert L.elf_gereksinimleri(tmp_path / "metin.txt") is None
    assert L.elf_gereksinimleri(tmp_path / "yok.so") is None


@pytest.mark.parametrize(
    ("yol", "gpl"),
    [
        ("PySide6/Qt/lib/libQt6Charts.so.6", True),
        ("PySide6/Qt/lib/libQt6ChartsQml.so.6", True),
        ("PySide6/Qt/lib/libQt6Quick3DXr.so.6", True),
        ("PySide6/Qt/lib/libQt6VirtualKeyboardSettings.so.6", True),
        ("PySide6/Qt/lib/libQt6WaylandCompositor.so.6", True),
        ("PySide6/Qt/lib/libQt6Bodymovin.so.6", True),
        ("Qt6Graphs.dll", True),
        ("PySide6/QtDataVisualization.abi3.so", True),
        ("PySide6/QtCharts.pyi", True),
        ("PySide6/Qt/qml/QtCharts/qmldir", True),
        ("PySide6/Qt/qml/QtQuick/VirtualKeyboard/Styles/Builtin/default/style.qml", True),
        ("PySide6/Qt/qml/QtQuick/Timeline/BlendTrees/qmldir", True),
        ("PySide6/Qt/qml/QtQuick3D/Helpers/impl/qmldir", True),
        ("PySide6/Qt/qml/QtWayland/Compositor/qmldir", True),
        ("PySide6/Qt/qml/Qt/labs/lottieqt/qmldir", True),
        # LGPL'li komşular AYIKLANMAZ.
        ("PySide6/Qt/lib/libQt6Quick.so.6", False),
        ("PySide6/Qt/lib/libQt6WaylandClient.so.6", False),
        ("PySide6/Qt/lib/libQt6WebEngineCore.so.6", False),
        ("PySide6/Qt/lib/libQt6ShaderTools.so.6", False),
        ("PySide6/Qt/lib/libQt6SpatialAudio.so.6", False),
        ("PySide6/Qt/lib/libQt63DCore.so.6", False),
        ("PySide6/QtQuick.abi3.so", False),
        ("PySide6/Qt/qml/QtQuick/Controls/qmldir", False),
        ("PySide6/Qt/qml/QtQuick/Templates/qmldir", False),
        ("PySide6/Qt/qml/QtWayland/Client/qmldir", False),
        ("PySide6/Qt/qml/QtWebEngine/qmldir", False),
        ("PySide6/Qt/plugins/platforms/libqxcb.so", False),
    ],
)
def test_qt_yalniz_gpl_modul_ada_gore_tanimlanir(yol: str, gpl: bool) -> None:
    assert L.qt_yalniz_gpl_mi(yol) is gpl


def test_qt_gpl_listesi_resmi_listenin_kitaplik_adlarini_kapsar() -> None:
    """doc.qt.io/qt-6.8/licensing.html'deki 15 modülün dosya adı kökleri (28.09.2026)."""
    assert set(L.QT_YALNIZ_GPL_MODULLER) == {
        "Bodymovin",  # Qt Lottie Animation
        "Charts",
        "Coap",
        "DataVisualization",
        "Graphs",
        "Grpc",
        "HttpServer",
        "Mqtt",
        "NetworkAuth",
        "QmlCompiler",
        "Quick3D",  # Quick 3D + Quick 3D Physics
        "QuickTimeline",
        "VirtualKeyboard",
        "WaylandCompositor",
    }


def test_qt_gpl_suz_ad_ve_bagimlilik_kapanisiyla_ayiklar(tmp_path: Path) -> None:
    """27.09.2026 derlemesi: Virtual Keyboard'un giriş eklentisi ve Quick 3D'nin profil
    eklentisi adında modül adı taşımaz ama yalnız GPL'li kitaplığa bağlanır."""
    kaynak = tmp_path / "sp" / "PySide6" / "Qt"
    ikililer = {
        "lib/libQt6Charts.so.6": ["libQt6Core.so.6"],
        "lib/libQt6Quick3D.so.6": ["libQt6Quick.so.6"],
        "lib/libQt6Quick.so.6": ["libQt6Core.so.6"],
        "lib/libQt6VirtualKeyboard.so.6": ["libQt6Quick.so.6"],
        "plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so": [
            "libQt6VirtualKeyboard.so.6"
        ],
        "plugins/qmltooling/libqmldbg_quick3dprofiler.so": ["libQt6Quick3D.so.6"],
        "plugins/qmltooling/libqmldbg_ara.so": ["libqmldbg_quick3dprofiler.so"],
        "plugins/platforms/libqxcb.so": ["libQt6Core.so.6"],
    }
    binaries = []
    for goreli, gerekenler in ikililer.items():
        _sahte_elf(kaynak / goreli, gerekenler)
        binaries.append((f"PySide6/Qt/{goreli}", str(kaynak / goreli), "BINARY"))
    datas = [
        ("PySide6/Qt/qml/QtCharts/qmldir", "/sp/x", "DATA"),
        ("PySide6/Qt/qml/QtQuick/Controls/qmldir", "/sp/y", "DATA"),
    ]
    kalan, kalan_veri, atilan = L.qt_gpl_suz(binaries, datas)
    assert sorted(oge[0] for oge in kalan) == [
        "PySide6/Qt/lib/libQt6Quick.so.6",
        "PySide6/Qt/plugins/platforms/libqxcb.so",
    ]
    assert [oge[0] for oge in kalan_veri] == ["PySide6/Qt/qml/QtQuick/Controls/qmldir"]
    assert "PySide6/Qt/plugins/qmltooling/libqmldbg_ara.so" in atilan  # kapanış iki adım
    assert len(atilan) == 7


def test_qt_gpl_paket_denetimi_diskte_ad_ve_bagimlilikla_bulur(tmp_path: Path) -> None:
    paket = tmp_path / "kutuphane-defteri"
    _sahte_elf(paket / "_internal" / "PySide6" / "Qt" / "lib" / "libQt6Quick.so.6", [])
    assert L.qt_gpl_paket_denetimi(paket) == []
    _sahte_elf(
        paket / "_internal" / "PySide6" / "Qt" / "plugins" / "assetimporters" / "libassimp.so",
        ["libQt6Quick3DAssetImport.so.6"],
    )
    hatalar = L.qt_gpl_paket_denetimi(paket)
    assert len(hatalar) == 1 and "bağlanan" in hatalar[0] and "libassimp.so" in hatalar[0]
    _sahte_elf(paket / "_internal" / "PySide6" / "Qt" / "lib" / "libQt6Quick3DAssetImport.so.6", [])
    hatalar = L.qt_gpl_paket_denetimi(paket)
    assert len(hatalar) == 2 and "yalnız GPL" in hatalar[0]
    # paket_dizini_denetimi de aynı kuralı uygular (derleme sonrası kapı).
    assert any("Qt'nin yalnız GPL" in h for h in L.paket_dizini_denetimi(paket, [], "linux"))


def test_spec_qt_gpl_suzgecini_linuxta_uygular_ve_liste_kap_ici_ile_ayni() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "if WITH_QT and not WINDOWS:" in spec
    assert (
        "a.binaries, a.datas, _qt_gpl_ayiklanan = _lisanslar.qt_gpl_suz(a.binaries, a.datas)"
        in spec
    )
    # Süzgeç pyphen süzgecinden SONRA, PYZ/COLLECT'ten ÖNCE.
    assert spec.index("_lisanslar.qt_gpl_suz") < spec.index("pyz = PYZ(")
    prova = KAP_ICI.read_text(encoding="utf-8")
    moduller = re.search(r"^QT_GPL_MODULLER='([^']+)'", prova, flags=re.MULTILINE)
    qml = re.search(r"^QT_GPL_QML='([^']+)'", prova, flags=re.MULTILINE)
    assert moduller and set(moduller.group(1).split("|")) == set(L.QT_YALNIZ_GPL_MODULLER)
    assert qml and set(qml.group(1).split("|")) == set(L.QT_GPL_QML_ONEKLERI)


def test_spec_webview_platform_disi_dosyalari_suzer(tmp_path: Path) -> None:
    """WebView2 SDK Linux paketine, Android arşivi hiçbir pakete girmez."""
    spec = SPEC.read_text(encoding="utf-8")
    assert "datas = [oge for oge in datas if not _webview_platform_disi(oge[1], oge[0])]" in spec
    assert (
        "binaries = [oge for oge in binaries if not _webview_platform_disi(oge[1], oge[0])]" in spec
    )
    paket = tmp_path / "p"
    (paket / "_internal" / "webview" / "lib").mkdir(parents=True)
    (paket / "_internal" / "webview" / "lib" / "Microsoft.Web.WebView2.Core.dll").write_bytes(b"x")
    assert L.paket_dizini_denetimi(paket, [], "windows") == []
    linux = L.paket_dizini_denetimi(paket, [], "linux")
    assert len(linux) == 1 and "pywebview" in linux[0]
    (paket / "_internal" / "webview" / "lib" / "pywebview-android.jar").write_bytes(b"x")
    assert len(L.paket_dizini_denetimi(paket, [], "windows")) == 1


# ------------------------------------------ yerel kütüphaneler: bilinen GPL ve MSYS2 SPDX


@pytest.mark.parametrize(
    "ad",
    [
        "libfftw3.so.3",
        "libgsl.so.25",
        "libpoppler.so.102",
        "libgs.so.9",
        "libx264.so.160",
        "libpostproc.so.55",
        "libjbig2dec.so.0",
        "libpci.so.3",
        "libparted.so.2",
        "libgdbm-6.dll",
    ],
)
def test_bilinen_gpl_yerel_kutuphaneler_yasak(ad: str) -> None:
    assert L.YASAK_YEREL.match(ad), ad


@pytest.mark.parametrize(
    "ad",
    ["libgsf-1.so.114", "libpciaccess.so.0", "libgsasl.so", "gs.py", "madde.txt", "libmadx.so"],
)
def test_benzer_adli_gpl_olmayan_kutuphaneler_serbest(ad: str) -> None:
    assert not L.YASAK_YEREL.match(ad), ad


def _msys2_paketi(ad: str, lisans_satirlari: tuple[str, ...], dosyalar: set[str]) -> Any:
    return L.YerelPaket(
        ad=ad,
        surum="1-1",
        lisans=" AND ".join(s.removeprefix("spdx:") for s in lisans_satirlari),
        kaynak="",
        lisans_dosyalari=[Path("COPYING")],
        dosyalar=dosyalar,
        lisans_satirlari=lisans_satirlari,
    )


def test_msys2_paketinin_spdx_lisansi_degerlendirilir() -> None:
    """F12 düzeltme turu: %LICENSE% okunuyordu ama değerlendirilmiyordu."""
    gpl = _msys2_paketi("mingw-w64-x86_64-gplkit", ("spdx:GPL-3.0-or-later",), {"libgk-1.dll"})
    hata, uyari = L.msys2_lisans_denetimi(gpl)
    assert hata and "mingw-w64-x86_64-gplkit" in hata and uyari is None
    # Eski (SPDX önekisiz) adla da yakalanır.
    assert L.msys2_lisans_denetimi(_msys2_paketi("x", ("GPL3",), {"a.dll"}))[0]
    # LGPL, istisnalı GPL ve seçenekli ifadeler geçer.
    for satirlar in (
        ("spdx:LGPL-2.1-or-later",),
        ("spdx:GPL-3.0-or-later WITH GCC-exception-3.1",),
        ("spdx:FTL OR GPL-2.0-or-later",),
        ("custom",),
    ):
        assert L.msys2_lisans_denetimi(_msys2_paketi("y", satirlar, {"b.dll"})) == (None, None)
    # Ayrıştırılamayan ifade uyarıdır, derlemeyi durdurmaz.
    hata, uyari = L.msys2_lisans_denetimi(_msys2_paketi("z", ("spdx:MIT;;GPL",), {"c.dll"}))
    assert hata is None and uyari and "ayrıştırılamadı" in uyari


def test_msys2_gpl_izni_dll_duzeyindedir() -> None:
    """libiconv'un GPL kısmı `iconv` aracıdır: libiconv-2.dll geçer, başka dosya geçmez."""
    satirlar = ("spdx:LGPL-2.1-or-later", "spdx:GPL-3.0-or-later")
    iconv = _msys2_paketi("mingw-w64-x86_64-libiconv", satirlar, {"libiconv-2.dll"})
    assert L.msys2_lisans_denetimi(iconv) == (None, None)
    iconv.dosyalar.add("iconv.exe")
    assert L.msys2_lisans_denetimi(iconv)[0]
    for ad, (dll_ler, gerekce) in L.MSYS2_GPL_IZINLERI.items():
        assert ad.startswith("mingw-w64-x86_64-") and dll_ler and len(gerekce) > 20, ad


def test_msys2_gpl_paketi_derlemeyi_durdurur(tmp_path: Path) -> None:
    kok = tmp_path / "msys64"
    _sahte_msys2(kok)
    dizin = kok / "var" / "lib" / "pacman" / "local" / "mingw-w64-x86_64-gplkit-1-1"
    dizin.mkdir(parents=True)
    (dizin / "desc").write_text(
        "%NAME%\nmingw-w64-x86_64-gplkit\n\n%VERSION%\n1-1\n\n%LICENSE%\nspdx:GPL-3.0-only\n\n",
        encoding="utf-8",
    )
    (dizin / "files").write_text(
        "%FILES%\nmingw64/bin/libgk-1.dll\nmingw64/share/licenses/gplkit/COPYING\n",
        encoding="utf-8",
    )
    (kok / "mingw64" / "share" / "licenses" / "gplkit").mkdir(parents=True)
    (kok / "mingw64" / "share" / "licenses" / "gplkit" / "COPYING").write_text("x", "utf-8")
    dll = tmp_path / "dll"
    sonuc = _denetle(
        tmp_path,
        [str(dll / "libgk-1.dll"), str(dll / "libpango-1.0-0.dll")],
        platform="windows",
        dll_dizini=dll,
        msys2=L.msys2_veritabani(kok),
    )
    assert len(sonuc.hatalar) == 1 and "yalnız GPL lisanslı MSYS2 paketi" in sonuc.hatalar[0]


# --------------------------------------------------- kısıt dosyası ve npm karşılaştırması


def test_kisit_dosyasi_platformun_python_surumlerini_verir() -> None:
    metin = L.kisitlar_metni(BILESENLER, "linux")
    satirlar = [s for s in metin.splitlines() if s and not s.startswith("#")]
    assert f"Django=={PYTHON['django'].surum}" in satirlar
    assert f"fonttools=={PYTHON['fonttools'].surum}" in satirlar  # geçişli bağımlılık
    assert not any(s.lower().startswith("pystray==") for s in satirlar)  # yalnız Windows
    assert any(s.lower().startswith("pyside6==") for s in satirlar)
    windows = L.kisitlar_metni(BILESENLER, "windows")
    assert "pystray==" in windows and "PySide6==" not in windows
    # npm ve elle bileşenler kısıta girmez.
    assert "react==" not in metin and "DejaVu" not in metin


def test_derleme_betikleri_kisit_dosyasiyla_kurar() -> None:
    build = BUILD_SH.read_text(encoding="utf-8")
    assert 'lisanslar.py" kisitlar --platform linux --cikti "$KISITLAR"' in build
    assert build.count('pip install --no-cache-dir -q -c "$KISITLAR"') == 2
    ps1 = BUILD_PS1.read_text(encoding="utf-8-sig")
    assert "kisitlar `" in ps1 and "--platform windows --cikti $Kisitlar" in ps1
    assert "-m pip install --disable-pip-version-check -q -c $Kisitlar" in ps1


def test_npm_farki_cikti_ile_listeyi_karsilastirir() -> None:
    cikti = {"paketler": [{"ad": b.ad, "surum": b.surum} for b in NPM.values()]}
    assert L.npm_farki(cikti, BILESENLER) == []
    cikti["paketler"].append({"ad": "zod", "surum": "3.0.0"})  # tipten çalışma anına geçti
    ilk = cikti["paketler"][0]
    ilk["surum"] = "0.0.0-yeni"
    hatalar = L.npm_farki(cikti, BILESENLER)
    assert any("olmayan npm paketi: zod 3.0.0" in h for h in hatalar)
    assert any(f"{ilk['ad']} 0.0.0-yeni" in h for h in hatalar)
    assert any("ön yüz çıktısında olmayan" in h for h in hatalar)


def test_gates_on_yuz_lisans_listesini_vite_ciktisiyla_karsilastirir() -> None:
    gates = (REPO / "scripts" / "gates.sh").read_text(encoding="utf-8")
    assert "packaging/lisanslar/on_yuz_paketleri.mjs" in gates
    assert "lisanslar.py npm-denetle" in gates
    # Ön yüz bağımlılıkları kurulduktan (typecheck) sonra koşar.
    assert gates.index("fe_typecheck") < gates.index("npm-denetle")


# ---------------------------------------------------------------- kurulum yüzü


def _dep5_paragraflari(metin: str) -> list[dict[str, str]]:
    paragraflar: list[dict[str, str]] = []
    for blok in metin.strip("\n").split("\n\n"):
        alanlar: dict[str, str] = {}
        anahtar = ""
        for satir in blok.splitlines():
            if satir.startswith((" ", "\t")):
                assert anahtar, f"devam satırı alansız: {satir!r}"
                assert satir.strip(), "DEP-5'te boş devam satırı ' .' olmalı"
                alanlar[anahtar] += "\n" + satir
            else:
                anahtar, _, deger = satir.partition(":")
                assert _ == ":", f"alan satırı değil: {satir!r}"
                alanlar[anahtar] = deger.strip()
        paragraflar.append(alanlar)
    return paragraflar


def test_deb_copyright_dep5_bicimli_ve_lisans_metnini_tasir() -> None:
    lisans = (REPO / "LICENSE").read_text(encoding="utf-8")
    metin = L.deb_copyright(lisans)
    paragraflar = _dep5_paragraflari(metin)
    baslik, *digerleri = paragraflar
    assert baslik["Format"] == "https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
    assert baslik["Upstream-Name"] == "kutuphane-defteri"
    dosya_paragraflari = [p for p in digerleri if "Files" in p]
    lisans_paragraflari = {p["License"].split("\n")[0]: p for p in digerleri if "Files" not in p}
    assert dosya_paragraflari[0]["Files"] == "*"
    # F12 düzeltme turu: çalıştırılabilir dosya (PyInstaller önyükleyicisi + gömülü üçüncü
    # taraf bayt kodu) ve lisans dizini "Files: *" ile PolyForm'a bağlanmaz.
    ozel = {p["Files"]: p for p in dosya_paragraflari[1:]}
    for yol in (
        "opt/kutuphane-defteri/_internal/*",
        "opt/kutuphane-defteri/kutuphane-defteri",
        "opt/kutuphane-defteri/THIRD_PARTY_LICENSES/*",
    ):
        assert ozel[yol]["License"] == "LicenseRef-ucuncu-taraf", yol
    assert "Bootloader-exception" in ozel["opt/kutuphane-defteri/kutuphane-defteri"]["Comment"]
    assert "PyInstaller" in ozel["opt/kutuphane-defteri/kutuphane-defteri"]["Copyright"]
    # Her `License:` kısa adı bağımsız bir lisans paragrafıyla açıklanır.
    for p in dosya_paragraflari:
        assert p["License"].split("\n")[0] in lisans_paragraflari
    govde = lisans_paragraflari[L.LISANS_KISA_ADI]["License"]
    assert "PolyForm Noncommercial License 1.0.0" in govde
    assert "Required Notice: Copyright (c) 2026" in govde
    # LICENSE'taki her dolu satır gövdede aynen durur.
    for satir in lisans.splitlines():
        if satir.strip():
            assert " " + satir.rstrip() in govde.splitlines(), satir
    assert "/opt/kutuphane-defteri/THIRD_PARTY_LICENSES/" in metin


def test_linux_paketi_lisanslari_kurar_ve_provada_arar() -> None:
    build = BUILD_SH.read_text(encoding="utf-8")
    assert 'packaging/lisanslar/lisanslar.py" paket' in build
    assert "--platform linux" in build
    assert build.index('lisanslar.py" paket') < build.index("packaging/veri_sizintisi.py")
    assert 'lisanslar.py" deb-copyright "$DOC_DIZINI/copyright"' in build
    assert "ln -sf /opt/kutuphane-defteri/THIRD_PARTY_LICENSES" in build
    prova = KAP_ICI.read_text(encoding="utf-8")
    for beklenen in (
        "/usr/share/doc/kutuphane-defteri",
        "copyright-format/1.0/",
        "/opt/kutuphane-defteri/LICENSE.txt",
        "THIRD_PARTY_LICENSES/BENIOKU.txt",
        "paket-icerigi.txt",
        "libreadline",
    ):
        assert beklenen in prova, beklenen


def test_windows_paketi_lisans_denetimini_msys2_ile_kosar() -> None:
    build = BUILD_PS1.read_text(encoding="utf-8-sig")
    adim = build.index('"packaging\\lisanslar\\lisanslar.py") paket')
    assert adim < build.index('"packaging\\veri_sizintisi.py") $AppDir')
    for parca in ("--platform windows", "--dll-dizini $DllDir", "--msys2-kok $Msys2Kok"):
        assert parca in build, parca
    assert 'Join-Path $WorkDir "kutuphane_defteri"' in build
    assert "_internal\\pystray\\__init__.py" in build


def test_inno_lisans_sayfasi_ve_lisanssiz_derleme_engeli() -> None:
    iss = ISS.read_text(encoding="utf-8")
    assert "LicenseFile={#LisansDosyasi}" in iss
    assert '#define LisansDosyasi AddBackslash(SourceDir) + "LICENSE.txt"' in iss
    assert '#define UcuncuTarafDizini AddBackslash(SourceDir) + "THIRD_PARTY_LICENSES"' in iss
    # Eksikse ISCC derlemeyi durdurur (#error) — lisanssız kurulum dosyası üretilmez.
    assert iss.count("#error") >= 2
    # Lisanslar SourceDir ile birlikte {app}'e kurulur.
    assert 'Source: "{#SourceDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs' in iss


def test_inno_lisans_dosyasi_bom_ile_yazilir() -> None:
    """Inno UTF-8 metni ancak BOM'la tanır; "DEMİRCİ" ANSI okunursa bozulur."""
    metin = (REPO / "packaging" / "lisanslar" / "lisanslar.py").read_text(encoding="utf-8")
    assert 'encoding="utf-8-sig" if platform == "windows" else "utf-8"' in metin


def test_lisans_dizini_depo_sizinti_kapisindan_gecer() -> None:
    """Üretilen metinler depoya girer: KVKK kapısının (depo_sizintisi) kurallarından
    geçmeli — veri dosyası biçimi yok, TCKN sağlamasına uyan sayı yok."""
    depo_sizintisi: Any = _yukle(REPO / "packaging" / "depo_sizintisi.py", "kd_depo_sizintisi")
    yollar = [f"THIRD_PARTY_LICENSES/{p.name}" for p in sorted(LISANSLAR.iterdir())]
    assert all(re.search(r"\.(txt|json)$", y) for y in yollar), yollar
    assert depo_sizintisi.denetle(REPO, yollar) == ([], [])
