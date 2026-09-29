"""Dağıtım türü: kurulu paket mi, taşınabilir arşiv mi, kaynak ağaç mı (KB-2, 28.09.2026).

**Kural (kullanıcı kararı KB-2, 28.09.2026; F5 ekleri 27'nin açık kararı).**
Pardus'un taşınabilir arşivinde (kurulumsuz `.tar.gz`) Ağ Kataloğu AÇILAMAZ;
yalnız `.deb` paketiyle kurulan programda açılır. Bu modül yalnız "bu süreç
hangi dağıtımdan çalışıyor?" sorusunu yanıtlar; kapıyı `desktop/katalog_kontrol.py`
uygular (T16: katalogu açan tek kanal).

**Linux ölçütü: çalışan program dosyası, dpkg'nin `kutuphane-defteri` paketine
yazdığı dosyalardan biri mi?** dpkg bir paketin kurduğu her yolu
`/var/lib/dpkg/info/<paket>.list` dosyasına yazar (`dpkg -L` ve `dpkg -S` bunu
okur). `.deb` programı `/opt/kutuphane-defteri/kutuphane-defteri`'ye, bağlantısını
`/usr/bin/kutuphane-defteri`'ye koyar (`packaging/linux/build.sh` adım 6); ikisi de
listededir. Taşınabilir arşivin `kur.sh`'i programı `~/.local/opt/kutuphane-defteri`'ye
kopyalar, arşivden doğrudan da çalıştırılabilir: bu yollar hiçbir zaman dpkg
listesinde olmaz. Karşılaştırma yol metniyle değil DOSYA KİMLİĞİYLE yapılır
(`os.path.samefile`: aygıt + düğüm): program `/usr/bin` bağlantısından ya da
bağlantılı bir `/opt` üzerinden açılsa da kurulu paket kurulu sayılır.

Seçilmeyen ölçütler ve nedenleri:

* **Yol öneki** (`/opt/kutuphane-defteri`): taşınabilir arşiv `sudo` ile oraya
  açılabilir; o zaman kurulu sayılırdı.
* **ufw profili / firewalld tanımı var mı**: sistem geneli dosyalardır; `.deb`
  kuruluyken ev dizininden çalıştırılan taşınabilir kopya da kurulu sayılırdı.
* **Dosya kökün mü**: `sudo` ile açılan arşiv de köke aittir.
* **`dpkg -S` alt süreci**: aynı listeyi okur; alt süreç ve PATH bağımlılığı
  gereksizdir.

Liste dosyası YOKSA paket kurulu değildir (taşınabilir). Liste VAR ama
okunamıyorsa (yetki, G/Ç) `.deb`'in sabit program yoluyla dosya kimliği
karşılaştırılır: kurulu paket bir okuma aksaklığı yüzünden taşınabilir
sayılmasın.

**Kaynak ağaç** (`sys.frozen` yok: geliştirme, Docker'daki testler, ağ kataloğu
provası) `KAYNAK` döner ve kapıdan etkilenmez. `--autotest` Ağ Kataloğunu
`KatalogKontrol`'den geçmeden yalnız 127.0.0.1'de kaldırır (`desktop/main.py`);
derleme duman testleri bu yüzden de etkilenmez.

**Windows** bu modülde ayrılmaz (`PAKET`): Windows'un taşınabilir paketinde
katalogu varsayılan olarak güvenlik duvarı denetiminin 2. maddesi (kurulumun
kuralı kurulu programın yoluna yazılır) açtırmaz (§5.2, GA-5;
`desktop/guvenlik_duvari.py`). Windows davranışı bu kararla DEĞİŞMEDİ. **Bilinen
fark** (tasarım §14.1 F12 ekleri KT-2): Ağ Doktoru'nun "Kuralı ekle/güncelle"
düğmesi UAC onayıyla kuralı taşınabilir programın yoluna yazarsa beş madde tutar ve
katalog açılır; aynı adlı kural yeniden yazıldığı için aynı bilgisayardaki kurulu
programın kuralının yerini alır. Windows'ta da kesin kapı istenirse ölçüt buraya
eklenir (Inno kaldırıcısı + HKLM `Uninstall` kaydının `InstallLocation`'ı) —
kullanıcı kararı bekler.

**`.deb` kurulu mu** (`deb_paketi_kurulu`): taşınabilir sürüm çalışırken iletinin
hangi yolu önereceğini seçer (KB-2 düzeltme turu, 29.09.2026; işlev belgesi).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

KURULU: Final = "kurulu"
TASINABILIR: Final = "tasinabilir"
KAYNAK: Final = "kaynak"
#: Paketli ama bu katmanda ayrılmayan platform (Windows: ayrımı güvenlik duvarı kuralı yapar).
PAKET: Final = "paket"

#: `.deb` paketinin adı (packaging/linux/debian-control.tmpl `Package:`).
DEB_PAKET_ADI: Final = "kutuphane-defteri"
#: dpkg'nin paket dosya listelerinin dizini.
DPKG_BILGI_DIZINI: Final = Path("/var/lib/dpkg/info")
#: `.deb`'in program yolu (packaging/linux/build.sh adım 6); yalnız liste okunamazsa kullanılır.
DEB_PROGRAM_YOLU: Final = Path("/opt/kutuphane-defteri/kutuphane-defteri")


def dpkg_listeleri(bilgi_dizini: Path = DPKG_BILGI_DIZINI) -> list[Path]:
    """Paketin dpkg dosya listeleri: `<paket>.list` ve çok mimarili `<paket>:<mimari>.list`."""
    listeler = [bilgi_dizini / f"{DEB_PAKET_ADI}.list"]
    try:
        listeler += sorted(bilgi_dizini.glob(f"{DEB_PAKET_ADI}:*.list"))
    except OSError:
        pass
    return listeler


def _ayni_dosya(a: str | Path, b: str | Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _listelenen_programlar(bilgi_dizini: Path, ad: str) -> tuple[list[str], bool]:
    """dpkg listelerinde dosya adı `ad` olan yollar ve listelerden biri okunamadı mı.

    Önce ad süzgeci uygulanır (liste binlerce satırdır); `/usr/bin` bağlantısı ve
    `/opt` altındaki program aynı adı taşır.
    """
    yollar: list[str] = []
    okunamadi = False
    for liste in dpkg_listeleri(bilgi_dizini):
        try:
            satirlar = liste.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            continue
        except OSError:
            okunamadi = True
            continue
        for satir in satirlar:
            yol = satir.strip()
            if yol and os.path.basename(yol) == ad:
                yollar.append(yol)
    return yollar, okunamadi


def linux_dagitim_turu(
    *,
    exe_yolu: str,
    paketli: bool,
    bilgi_dizini: Path = DPKG_BILGI_DIZINI,
    deb_program_yolu: Path = DEB_PROGRAM_YOLU,
) -> str:
    """Linux: `KURULU` / `TASINABILIR` / `KAYNAK` (ölçüt modül belgesinde)."""
    if not paketli:
        return KAYNAK
    yollar, okunamadi = _listelenen_programlar(bilgi_dizini, os.path.basename(exe_yolu))
    if any(_ayni_dosya(yol, exe_yolu) for yol in yollar):
        return KURULU
    if okunamadi and _ayni_dosya(deb_program_yolu, exe_yolu):
        return KURULU
    return TASINABILIR


def deb_paketi_kurulu(
    *,
    bilgi_dizini: Path = DPKG_BILGI_DIZINI,
    deb_program_yolu: Path = DEB_PROGRAM_YOLU,
) -> bool:
    """Bu bilgisayarda `.deb` paketi kurulu mu? Taşınabilir sürüm çalışırken sorulur.

    KB-2 düzeltme turu (29.09.2026): `kur.sh` menü kaydını
    `~/.local/share/applications/`'a, uçbirim bağlantısını `~/.local/bin/`'e yazar. İkisi
    `.deb`'inkiyle aynı adı taşır ve XDG ile PATH önceliğinde `.deb`'inkini gölgeler:
    `.deb` sonradan kurulursa menü ve uçbirim taşınabilir sürümü açmayı sürdürür. Bu
    durumda ileti "programı .deb paketiyle kurun" değil, "taşınabilir sürümü
    `./kaldir.sh` ile kaldırıp programı menüden açın" demelidir (`katalog_kontrol`).

    Ölçüt: listede programın adını taşıyan ve diskte DURAN bir dosya var mı (kaldırılmış
    ama ayar dosyaları kalmış bir paketin listesi programı anmaz ya da dosya yoktur).
    Liste okunamazsa `.deb`'in sabit program yolu diskte mi diye bakılır.
    """
    yollar, okunamadi = _listelenen_programlar(bilgi_dizini, deb_program_yolu.name)
    if any(os.path.isfile(yol) for yol in yollar):
        return True
    return okunamadi and os.path.isfile(deb_program_yolu)


def dagitim_turu(
    *,
    platform: str = sys.platform,
    paketli: bool | None = None,
    exe_yolu: str | None = None,
    bilgi_dizini: Path = DPKG_BILGI_DIZINI,
) -> str:
    """Bu sürecin dağıtım türü (modül belgesi). Paketli değilse her platformda `KAYNAK`."""
    paketli = bool(getattr(sys, "frozen", False)) if paketli is None else paketli
    if not paketli:
        return KAYNAK
    if platform.startswith("linux"):
        return linux_dagitim_turu(
            exe_yolu=exe_yolu or sys.executable, paketli=True, bilgi_dizini=bilgi_dizini
        )
    return PAKET


def katalog_sunulur(tur: str) -> bool:
    """Ağ Kataloğu bu dağıtımda sunulur mu? Yalnız Linux taşınabilir arşivinde hayır (KB-2)."""
    return tur != TASINABILIR
