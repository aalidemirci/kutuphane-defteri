"""Temiz makinede geri yükleme provası (F11 kod kapısı; tasarım §16 risk 13, §14.1 F11).

Bilgisayar değişir, disk bozulur, program yeniden kurulur: okulun elinde kalan,
kullanıcının indirip USB belleğe aldığı şifreli yedektir. Prova GERÇEK süreçlerle
koşar (`desktop.main`, gerçek göç, gerçek şifreleme, gerçek yedek kapsayıcısı):

1. **Eski bilgisayar** (`hazirla`): yönetici parolası + doğrulanmış kurtarma anahtarı,
   uydurma öğrenci/personel, katalog, üyelik ve açık ödünç; dış yedek USB'ye; yedekten
   SONRA bir kart daha verilir (basılıp dağıtılmış sayılır).
2. **Temiz bilgisayar**: boş veri dizininde `--geri-yukle` (parola ya da kurtarma
   anahtarıyla) → güvenlik dosyası yedeğin başlığından yazılır → program açılır
   (`--autotest`: damga, bütünlük, günlük yedek, göç, sunucu) → kilit AYNI parolayla /
   AYNI anahtarla açılır → kişi adları, okul numaraları, katalog, üyelik ve açık ödünç
   birebir aynıdır.
3. **Kart defteri geri sarılmaz** (F6): taşıma kontrol listesi veri klasöründeki
   `verilmis-kartlar.txt`'yi de taşır; yedekten sonra verilmiş kartın numarası yeni
   bilgisayarda da bir daha verilmez. Aynı bilgisayarda eski yedeğe dönmek defteri
   değiştirmez. Defter taşınmazsa güvence yalnız olasılıktır (TB33) — bu sınır da
   burada sabitlenir, kontrol listesinin gerekçesidir.
4. **Daha yeni sürümün yedeği eski programda açılmaz**: geri yükleme sürüm damgasını
   siler; veritabanının göç kaydı eski programı 4 koduyla durdurur.
5. **Sihirbazı başka parolayla doldurulmuş yeni bilgisayar** (F11 düzeltme turu):
   kurucunun sonunda açılan programda parola kurulmuşsa geri yükleme yabancı güvenlik
   dosyasını ve boş veritabanını kenara alır; veri yine birebir aynıdır.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from desktop.errors import EXIT_OK, EXIT_SCHEMA_TOO_NEW
from desktop.tests.alt_surec import betik, gunluk, kart_govdesi, program

pytestmark = pytest.mark.slow

DEFTER = Path("data") / "verilmis-kartlar.txt"


@pytest.fixture(scope="module")
def eski_bilgisayar(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """Eski bilgisayar: gerçek göç + parola + veri + USB'deki dış yedek (modülde bir kez)."""
    kok = tmp_path_factory.mktemp("eski-bilgisayar")
    usb = tmp_path_factory.mktemp("usb-bellek")
    sonuc = betik("hazirla", "--data-dir", str(kok), "--usb", str(usb))
    sonuc["kok"] = kok
    sonuc["usb"] = usb
    assert Path(sonuc["yedek"]).is_file()
    assert (kok / DEFTER).is_file(), "verilmiş kart defteri yazılmadı"
    yield sonuc


def _geri_yukle(hedef: Path, yedek: str, *sir: str) -> None:
    sonuc = program("--geri-yukle", yedek, *sir, "--evet", "--data-dir", str(hedef))
    assert sonuc.returncode == EXIT_OK, (sonuc.stdout[-2000:], sonuc.stderr[-2000:])


def _acilis(hedef: Path) -> None:
    sonuc = program("--autotest", "--data-dir", str(hedef))
    assert sonuc.returncode == EXIT_OK, (sonuc.stderr[-2000:], gunluk(hedef)[-3000:])


def _defteri_tasi(eski: Path, yeni: Path) -> None:
    """Taşıma kontrol listesinin maddesi: `data/verilmis-kartlar.txt` de taşınır."""
    (yeni / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(eski / DEFTER, yeni / DEFTER)


def test_temiz_makinede_parolayla_geri_yukleme_ayni_veriyi_verir(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    yeni = tmp_path / "yeni-bilgisayar"
    _defteri_tasi(eski_bilgisayar["kok"], yeni)

    _geri_yukle(yeni, eski_bilgisayar["yedek"], "--parola", eski_bilgisayar["parola"])

    # Güvenlik dosyası ve yedek anahtarı yedeğin başlığından yeniden kuruldu; damga
    # silindi (yedeğin sürümü bilinmez), ilk açılış yeniden yazar.
    assert (yeni / "data" / "guvenlik.json").is_file()
    assert (yeni / "data" / "yedekleme.json").is_file()
    assert not (yeni / "data" / "surum.json").exists()

    _acilis(yeni)
    assert (yeni / "data" / "surum.json").is_file()
    # Açılış yeni bilgisayarın ilk günlük yedeğini aldı (şifreli, başlıklı).
    assert list((yeni / "backups").glob("gunluk-*.kdbak"))

    dogrulama = betik("dogrula", "--data-dir", str(yeni), "--parola", eski_bilgisayar["parola"])
    assert dogrulama["ozet"] == eski_bilgisayar["beklenen"]
    assert dogrulama["ozet"]["acik_odunc"], "açık ödünç taşınmadı"
    assert dogrulama["durum"]["recovery_key_confirmed"] is True
    assert dogrulama["durum"]["locked"] is False


def test_sihirbazda_baska_parola_kurulmus_yeni_bilgisayara_geri_yukleme(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    """Kurucunun "programı çalıştır" kutusu (Inno `postinstall`, varsayılan işaretli) programı
    açar; kullanıcı sihirbazda BAŞKA bir parola kurabilir. Yeni bilgisayarda yabancı bir
    güvenlik dosyası, yedek anahtarı, geçiş yedeği ve boş veritabanı oluşur. Eski yedeğin
    geri yüklenmesi yine aynı veriyi verir: yabancı güvenlik dosyası "guvenlik-arsiv"
    adıyla, boş veritabanı "db-onceki" adıyla kenara alınır, güvenlik dosyası ve yedek
    anahtarı yedeğin başlığından yazılır (F11 düzeltme turu; kurulum §7 madde 3)."""
    yeni = tmp_path / "sihirbazi-doldurulmus"
    _defteri_tasi(eski_bilgisayar["kok"], yeni)
    betik("sihirbaz", "--data-dir", str(yeni), "--parola", "Sihirbaz-Baska-Parola-3")
    yabanci = (yeni / "data" / "guvenlik.json").read_bytes()
    yabanci_anahtar = (yeni / "data" / "yedekleme.json").read_bytes()

    _geri_yukle(yeni, eski_bilgisayar["yedek"], "--parola", eski_bilgisayar["parola"])

    arsivler = list((yeni / "data").glob("guvenlik-arsiv-*.json"))
    assert [yol.read_bytes() for yol in arsivler] == [yabanci]
    assert (yeni / "data" / "guvenlik.json").read_bytes() != yabanci
    assert (yeni / "data" / "yedekleme.json").read_bytes() != yabanci_anahtar
    assert list((yeni / "data").glob("db-onceki-*.sqlite3")), "boş veritabanı kenara alınmadı"
    _acilis(yeni)
    dogrulama = betik("dogrula", "--data-dir", str(yeni), "--parola", eski_bilgisayar["parola"])
    assert dogrulama["ozet"] == eski_bilgisayar["beklenen"]
    assert dogrulama["durum"]["recovery_key_confirmed"] is True


def test_temiz_makinede_kurtarma_anahtariyla_acilir_ve_parola_yenilenir(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    yeni = tmp_path / "yeni-bilgisayar"

    _geri_yukle(yeni, eski_bilgisayar["yedek"], "--kurtarma-anahtari", eski_bilgisayar["kurtarma"])
    _acilis(yeni)

    kurtarma = betik("dogrula", "--data-dir", str(yeni), "--kurtarma", eski_bilgisayar["kurtarma"])
    assert kurtarma["ozet"] == eski_bilgisayar["beklenen"]
    # Kurtarma anahtarıyla açılış yeni parola belirler; sonraki açılış onunla yapılır.
    yeni_parola = betik("dogrula", "--data-dir", str(yeni), "--parola", "Prova-Yeni-Parola-2")
    assert yeni_parola["ozet"] == eski_bilgisayar["beklenen"]


def test_tasinan_kart_defteri_yedekten_sonraki_karti_korur(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    """Yedekten SONRA verilen kartın numarası (yedekte yok) yeni bilgisayarda verilmez."""
    yeni = tmp_path / "yeni-bilgisayar"
    _defteri_tasi(eski_bilgisayar["kok"], yeni)
    _geri_yukle(yeni, eski_bilgisayar["yedek"], "--parola", eski_bilgisayar["parola"])
    _acilis(yeni)

    sonuc = betik(
        "kart-dene",
        "--data-dir",
        str(yeni),
        "--parola",
        eski_bilgisayar["parola"],
        "--govde",
        kart_govdesi(eski_bilgisayar["kart_sonra"]),  # yalnız taşınan defterde
        kart_govdesi(eski_bilgisayar["kart_once"]),  # geri yüklenen IssuedCard'da
        "000001",
    )

    assert sonuc["kart"] not in {eski_bilgisayar["kart_sonra"], eski_bilgisayar["kart_once"]}
    assert kart_govdesi(sonuc["kart"]) == "000001"


def test_ayni_bilgisayarda_eski_yedege_donus_kart_defterini_geri_sarmaz(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    kok = tmp_path / "ayni-bilgisayar"
    shutil.copytree(eski_bilgisayar["kok"], kok)
    defter_once = (kok / DEFTER).read_bytes()

    _geri_yukle(kok, eski_bilgisayar["yedek"], "--parola", eski_bilgisayar["parola"])

    assert (kok / DEFTER).read_bytes() == defter_once, "geri yükleme defteri değiştirdi"
    _acilis(kok)
    # Veritabanı yedeğin anına döndü: yedekten sonraki üyelik geri sarıldı…
    dogrulama = betik("dogrula", "--data-dir", str(kok), "--parola", eski_bilgisayar["parola"])
    assert dogrulama["ozet"] == eski_bilgisayar["beklenen"]
    # …ama o üyeliğin kart numarası bir daha verilmez.
    sonuc = betik(
        "kart-dene",
        "--data-dir",
        str(kok),
        "--parola",
        eski_bilgisayar["parola"],
        "--govde",
        kart_govdesi(eski_bilgisayar["kart_sonra"]),
        "000002",
    )
    assert kart_govdesi(sonuc["kart"]) == "000002"


def test_defter_tasinmazsa_yedekten_sonraki_kart_korunmaz(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    """Bilinen sınır (TB33): defter yoksa güvence yalnız olasılıktır (10⁶'lık uzay).

    Kontrol listesinin "verilmis-kartlar.txt dosyasını da taşıyın" maddesinin
    gerekçesi budur. Bu davranış değişirse (defter yedeğe girerse) test ve TB33
    birlikte güncellenir.
    """
    yeni = tmp_path / "defteri-tasinmamis"
    _geri_yukle(yeni, eski_bilgisayar["yedek"], "--parola", eski_bilgisayar["parola"])
    _acilis(yeni)

    sonuc = betik(
        "kart-dene",
        "--data-dir",
        str(yeni),
        "--parola",
        eski_bilgisayar["parola"],
        "--govde",
        kart_govdesi(eski_bilgisayar["kart_sonra"]),
    )

    assert sonuc["kart"] == eski_bilgisayar["kart_sonra"]


def test_yeni_surumun_yedegi_eski_programda_acilmaz(
    eski_bilgisayar: dict[str, Any], tmp_path: Path
) -> None:
    """Geri yükleme damgayı siler; veritabanının göç kaydı eski programı durdurur (kod 4)."""
    kaynak = tmp_path / "kaynak"
    shutil.copytree(eski_bilgisayar["kok"], kaynak)
    usb = tmp_path / "usb"
    gelecek = betik(
        "gelecek-yedek",
        "--data-dir",
        str(kaynak),
        "--parola",
        eski_bilgisayar["parola"],
        "--usb",
        str(usb),
    )
    hedef = tmp_path / "eski-program"
    _geri_yukle(hedef, gelecek["yedek"], "--parola", eski_bilgisayar["parola"])
    assert not (hedef / "data" / "surum.json").exists()

    sonuc = program("--autotest", "--data-dir", str(hedef))

    assert sonuc.returncode == EXIT_SCHEMA_TOO_NEW
    kayit = gunluk(hedef)
    assert "Program sürümü eski" in kayit
    assert "tanımadığı değişiklikler" in kayit
    assert "okul.9999_gelecek_surum" in kayit
    # Göç ve damga yazılmadı: veri, onu yazan sürüme dokunulmadan kalır.
    assert not (hedef / "data" / "surum.json").exists()
    assert not list((hedef / "backups").glob("pre-migrate-*"))
