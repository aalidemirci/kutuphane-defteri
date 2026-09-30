"""Saha kabul protokolü (`docs/saha-kabulu.md`) ve F12 belge kararları — belge kapısı.

F12 sözleşmesinin kod kapısı "saha kabul protokolü her ertelenmiş kanıtı kapsar (eşleme
tablosu)" der. Bu test eşlemenin EKSİKSİZ kalmasını kaynağa karşı sınar: yeni bir W
maddesi (`packaging/windows/NOTLAR.md`), yeni bir çek-listesi maddesi, yeni bir saha
hazırlık maddesi (tasarım §14.2), bir "F<n> ekleri" bölümünde "F12" geçen yeni bir
MADDE (madde numarası ya da kodu düzeyinde — F12 düzeltme turu), `docs/teknik-borc.md`'de
"F12" ya da "saha" geçen bir TB kalemi ya da §14.1 F12 satırının bir kalemi protokolde
karşılığı olmadan kalamaz. Eşlemedeki her adım numarası protokolde gerçekten tanımlıdır.

Belge gözden geçirmesinin iki sözlük kararı da burada kilitlenir (`docs/sozluk.md` §1):
kullanıcı metninde "kurucu" değil "kurulum dosyası"; "DHCP rezervasyonu" yalnız "sabit
adres ayırma" ile aynı satırda (BTR'ye dönük teknik ad). Herkese açık belgelerde gerçek
IP adresi ve "Bakanlık sisteminin yerine geçer" iddiası bulunmaz (CLAUDE.md §2-12, §2-13).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_PROTOKOL = Path("docs") / "saha-kabulu.md"
_NOTLAR = Path("packaging") / "windows" / "NOTLAR.md"
_TASARIM = Path("docs") / "tasarim" / "2026-09-21-genel-tasarim.md"

#: Herkese açık kullanıcı belgeleri (F12 belge gözden geçirmesinin kapsamı).
_KULLANICI_BELGELERI = (
    Path("README.md"),
    Path("docs") / "kurulum.md",
    Path("docs") / "ag-kurulumu.md",
    Path("docs") / "saha-kabulu.md",
    Path("docs") / "site-icerigi.md",
)


def _oku(yol: Path) -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _bolum(metin: str, baslik: str, sonraki: str) -> str:
    """`baslik` ile başlayan satırdan `sonraki` ile başlayan satıra kadarki metin."""
    bas = metin.index(baslik)
    son = metin.index(sonraki, bas + len(baslik))
    return metin[bas:son]


def _tablo_ilk_hucreleri(metin: str, desen: str) -> set[str]:
    return set(re.findall(rf"^\| ({desen}) ", metin, flags=re.MULTILINE))


# ---------------------------------------------------------------------------
# Eşleme tablosu eksiksiz
# ---------------------------------------------------------------------------
def test_notlar_w_maddelerinin_hepsi_eslenir() -> None:
    notlar = _oku(_NOTLAR)
    w_maddeleri = _tablo_ilk_hucreleri(_bolum(notlar, "## 1.", "## 2."), r"W\d+")
    assert w_maddeleri, "NOTLAR.md'de W maddesi bulunamadı"
    esleme = _bolum(_oku(_PROTOKOL), "### 26.3", "### 26.4")
    assert w_maddeleri <= _tablo_ilk_hucreleri(esleme, r"W\d+"), w_maddeleri - _tablo_ilk_hucreleri(
        esleme, r"W\d+"
    )


def test_notlar_cek_listesinin_hepsi_eslenir() -> None:
    notlar = _oku(_NOTLAR)
    cek = _bolum(notlar, "## 3. İlk Windows koşusu çek-listesi", "## 4.")
    maddeler = set(re.findall(r"^(\d+)\. ", cek, flags=re.MULTILINE))
    assert len(maddeler) >= 17
    esleme = _bolum(_oku(_PROTOKOL), "### 26.4", "### 26.5")
    assert maddeler <= _tablo_ilk_hucreleri(esleme, r"\d+"), maddeler - _tablo_ilk_hucreleri(
        esleme, r"\d+"
    )


def test_saha_hazirlik_hattinin_hepsi_eslenir() -> None:
    tasarim = _oku(_TASARIM)
    hat = _bolum(tasarim, "### 14.2", "## 15.")
    s_maddeleri = _tablo_ilk_hucreleri(hat, r"S\d+")
    assert len(s_maddeleri) >= 15
    esleme = _bolum(_oku(_PROTOKOL), "### 26.5", "### 26.6")
    assert s_maddeleri <= _tablo_ilk_hucreleri(esleme, r"S\d+")


#: "F<n> ekleri" içinde bir maddenin başlangıcı: "9. **…" ya da "- **B-1 — …".
_MADDE_BASI = (re.compile(r"^\s{0,3}(\d+)\. "), re.compile(r"^- \*\*([A-ZÇĞİÖŞÜ]+-\d+)\b"))


def _f12_gecen_ek_maddeleri(tasarim: str) -> set[tuple[str, str]]:
    """§14.1'deki "F<n> ekleri" bölümlerinde "F12" geçen her MADDE: (faz, madde kimliği).

    Madde kimliği numara ("9"), kod ("B-1") ya da ilk maddeden önceki paragraf için
    "başlığı"dır. F12'nin kendi ekleri sayılmaz.
    """
    fazlar = _bolum(tasarim, "### 14.1", "### 14.2")
    faz: str | None = None
    kimlik = "başlığı"
    sonuc: set[tuple[str, str]] = set()
    for satir in fazlar.splitlines():
        baslik = re.match(r"\*\*(F\d+) ekleri", satir)
        if baslik:
            faz, kimlik = baslik.group(1), "başlığı"
        for desen in _MADDE_BASI:
            madde = desen.match(satir)
            if faz and madde:
                kimlik = madde.group(1)
        if faz and faz != "F12" and "F12" in satir:
            sonuc.add((faz, kimlik))
    return sonuc


def _eslemedeki_ek_maddeleri(esleme: str) -> set[tuple[str, str]]:
    """Eşleme tablosunun ilk hücrelerindeki "F<n> ekleri <kimlikler>:" atıfları."""
    sonuc: set[tuple[str, str]] = set()
    for satir in esleme.splitlines():
        if not satir.startswith("| ") or satir.startswith("|---"):
            continue
        ilk_hucre = satir.split("|")[1]
        for atif in re.finditer(r"(F\d+) ekleri ([^:|]*)", ilk_hucre):
            for kimlik in re.findall(r"başlığı|[A-ZÇĞİÖŞÜ]+-\d+|\b\d+\b", atif.group(2)):
                sonuc.add((atif.group(1), kimlik))
    return sonuc


def test_f12ye_ertelenen_ek_maddelerinin_hepsi_eslenir() -> None:
    """§14.1'de "F12" geçen her "F<n> ekleri" MADDESİ protokolün §26.2'sinde anılır.

    F12 düzeltme turu: kapı faz düzeyindeydi — bir ek bölümüne yeni bir "F12'ye
    ertelendi" maddesi eklense §26.2'de zaten "F<n> ekleri" yazdığı için yeşil kalırdı.
    """
    tasarim = _oku(_TASARIM)
    ertelenen = _f12_gecen_ek_maddeleri(tasarim)
    assert {("F4", "9"), ("F5", "16"), ("F5", "18"), ("F11", "E-6")} <= ertelenen
    assert {faz for faz, _ in ertelenen} >= {"F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11"}
    esleme = _bolum(_oku(_PROTOKOL), "### 26.2", "### 26.3")
    eksik = ertelenen - _eslemedeki_ek_maddeleri(esleme)
    assert not eksik, sorted(eksik)
    # Tasarımın §14.1 dışındaki "sahada doğrulanır" satırları da eşlenir.
    for kaynak in ("§4.5", "§5.7", "§5.10-15", "§5.10-16", "§4.2-3"):
        assert kaynak in esleme, kaynak


def test_ek_maddesi_esleme_ayristirmasi() -> None:
    """Kapının kendisi: madde kimlikleri kaynakta ve eşlemede aynı biçimde okunur."""
    kaynak = (
        "### 14.1\n**F4 ekleri (24.09.2026).** Giriş F12'ye ertelendi.\n"
        "9. **F4 eki → F12 (saha).** Yazıcı.\n10. Başka madde.\n"
        "**F11 ekleri — B kolu.**\n- **B-2 — Prova** F12'de okulda.\n### 14.2\n"
    )
    assert _f12_gecen_ek_maddeleri(kaynak) == {("F4", "başlığı"), ("F4", "9"), ("F11", "B-2")}
    esleme = (
        "| F4 ekleri başlığı ve madde 9: yazıcı | 8.3 |\n"
        "| F11 ekleri B-2, K-3, D-11: prova | 18.1 |\n"
    )
    assert _eslemedeki_ek_maddeleri(esleme) == {
        ("F4", "başlığı"),
        ("F4", "9"),
        ("F11", "B-2"),
        ("F11", "K-3"),
        ("F11", "D-11"),
    }


def test_teknik_borcun_saha_kalemleri_eslenir() -> None:
    """`docs/teknik-borc.md`'de "F12" ya da "saha" geçen her TB kalemi §26.6'dadır."""
    borc = _oku(Path("docs") / "teknik-borc.md")
    kalemler: set[str] = set()
    for parca in re.split(r"\n(?=- \*\*TB\d+)", borc):
        kalem = re.match(r"- \*\*(TB\d+)", parca)
        if kalem and re.search(r"F12|saha", parca):
            kalemler.add(kalem.group(1))
    assert {"TB3", "TB27", "TB28", "TB36"} <= kalemler
    esleme = _bolum(_oku(_PROTOKOL), "### 26.6", "### 26.7")
    eslenen = set(re.findall(r"^\| (TB\d+) ", esleme, flags=re.MULTILINE))
    assert kalemler <= eslenen, sorted(kalemler - eslenen)


def test_f12_satirinin_kalemleri_eslenir() -> None:
    """§14.1 F12 satırının kapsam ve kapı kalemleri §26.1'in ilk sütununda anılır."""
    tasarim = _oku(_TASARIM)
    satir = next(s for s in tasarim.splitlines() if s.startswith("| **F12 "))
    _faz, kapsam, kapi = (h.strip() for h in satir.strip().strip("|").split("|")[:3])
    esleme = _bolum(_oku(_PROTOKOL), "### 26.1", "### 26.2")
    ilkler = [
        s.split("|")[1].strip().casefold()
        for s in esleme.splitlines()
        if s.startswith("| ") and not s.startswith("|---")
    ]
    eksik: list[str] = []
    # Kapsam: "Inno (a, b, …) · `.deb` (…) · … · **ertelenen…** · *kararlar*" — yıldızlı
    # kalemler §26.2 ve §26.7'dedir.
    for kalem in kapsam.split(" · *")[0].split(" · "):
        if kalem.startswith("*"):
            continue
        bas = re.sub(r"\s*\(.*$", "", kalem).strip().casefold()
        if not any(bas in ilk for ilk in ilkler):
            eksik.append(kalem)
    inno = re.search(r"Inno \(([^)]*)\)", kapsam)
    assert inno, "F12 satırında Inno kalemleri bulunamadı"
    for alt in inno.group(1).split(", "):
        if not any(ilk.startswith("inno:") and alt.casefold() in ilk for ilk in ilkler):
            eksik.append(f"Inno: {alt}")
    # Kapı: "Temiz Windows 11'de uçtan uca: a → b → … · Pardus'ta … · … · *kod tarafı*".
    kalemler = kapi.split(" · *")[0].split(" · ")
    zincir = kalemler.pop(0).split(":", 1)[1].split("→")
    for kalem in [z.strip() for z in zincir] + kalemler:
        if not any(ilk.startswith("kod kapısı:") and kalem.casefold() in ilk for ilk in ilkler):
            eksik.append(f"kapı: {kalem}")
    assert not eksik, eksik


def test_eslemedeki_adimlar_protokolde_tanimli() -> None:
    protokol = _oku(_PROTOKOL)
    tanimli = set(re.findall(r"^- \[ \] \*\*(\d+(?:\.\d+)+) ", protokol, flags=re.MULTILINE))
    tanimli |= set(re.findall(r"^#{2,3} (\d+(?:\.\d+)*)[. ]", protokol, flags=re.MULTILINE))
    assert len(tanimli) > 100
    esleme = protokol[protokol.index("## 26.") :]
    notlar = _oku(_NOTLAR)
    notlar_esleme = notlar[notlar.index("## 5. Saha kabul") :]
    atiflar: set[str] = set()
    for tablo in (esleme, notlar_esleme):
        for satir in tablo.splitlines():
            if not satir.startswith("| ") or satir.startswith("|---"):
                continue
            son_hucre = satir.rstrip(" |").rsplit("|", 1)[-1]
            atiflar.update(re.findall(r"(?<![\w.])(\d{1,2}(?:\.\d{1,2}){1,2})(?![\w.])", son_hucre))
    assert atiflar, "eşleme tablosunda adım bulunamadı"
    assert atiflar <= tanimli, sorted(atiflar - tanimli)


def test_protokol_deneme_verisi_ureticisini_ve_kosusunu_anlatir() -> None:
    protokol = _oku(_PROTOKOL)
    assert "scripts/deneme_verisi.py" in protokol
    assert "python scripts/deneme_verisi.py" in protokol
    assert "OZET.txt" in protokol
    # Gerçek kişi verisi kullanılmaz; deneme verisi depoya girmez.
    assert "Gerçek kişi verisi KULLANILMAZ" in protokol
    assert "`.gitignore`" in protokol


# ---------------------------------------------------------------------------
# Belge gözden geçirmesinin sözlük kararları
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("yol", _KULLANICI_BELGELERI, ids=str)
def test_kullanici_belgelerinde_kurucu_gecmez(yol: Path) -> None:
    """Sözlük §1 "Kurulum ve kaldırma": "kurucu" değil "kurulum dosyası" (HTML yorumu hariç)."""
    metin = re.sub(r"<!--.*?-->", " ", _oku(yol), flags=re.DOTALL)
    # Tırnak içinde sözcüğün KENDİSİNDEN söz etmek serbesttir ("kurucu" yerine …).
    bulgular = [
        no
        for no, satir in enumerate(metin.splitlines(), start=1)
        if re.search(r"(?<![\"“])kurucu", satir, flags=re.IGNORECASE)
    ]
    assert bulgular == [], f"{yol}: satır {bulgular}"


@pytest.mark.parametrize("yol", _KULLANICI_BELGELERI, ids=str)
def test_dhcp_rezervasyonu_yalniz_sabit_adres_ayirmayla_birlikte(yol: Path) -> None:
    """Sözlük §1 "DHCP'de sabit adres": teknik ad yalnız "sabit adres ayır…" ile aynı satırda."""
    for no, satir in enumerate(_oku(yol).splitlines(), start=1):
        if re.search(r"rezervasyon", satir, flags=re.IGNORECASE):
            assert "sabit adres ayır" in satir, f"{yol}:{no}"


@pytest.mark.parametrize("yol", _KULLANICI_BELGELERI, ids=str)
def test_herkese_acik_belgelerde_ip_adresi_ve_yerine_gecer_iddiasi_yok(yol: Path) -> None:
    metin = _oku(yol)
    adresler = set(re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", metin))
    # Yalnız loopback ve belgelerin anlattığı joker dinleme adresi (bağlama değil, metin).
    assert adresler <= {"127.0.0.1", "0.0.0.0"}, adresler  # noqa: S104
    assert not re.search(r"yerine geçer(?!\w)", metin), "konum dili: yerine geçer iddiası"
