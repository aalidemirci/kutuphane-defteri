"""Kimlik kalıntısı taraması — F0 kapısı (tasarım §2.3, CLAUDE.md §2-14).

Program kardeş projenin (KS) iskeletinden türedi; KS de DD'den türemişti. Eski
kimliğin (program adı, ortam değişkeni öneki, oturum başlığı, yedek uzantısı)
kaynakta, evrak şablonlarında ya da ön yüz metninde kalmasına sıfır tolerans
vardır: başka programın veri dizinine yazan bir sabit ya da ekranda başka
programın adı bu sınıftandır.

Tarama depo kökünden (Docker'da `/repo`) dosya ağacını dolaşır. Konteynerde git
YOKTUR (gates.sh başlığı); bu yüzden izlenen dosya listesi değil ağaç taranır
ve depoya girmeyen yerel/üretilen yollar `ATLANAN_YOLLAR`'da adıyla atlanır.

Eşleştirme satır satır, **TR katlamalı** ve büyük/küçük harfe duyarsızdır:
"İ", "I" ve "ı" üçü de "i"ye katlanır (Türkçe büyük yazılmış "İ" de, ASCII
büyük "I" de yakalanır). Yalın "disiplin" ve "sınav" taranmaz: meşru metinde
yanlış pozitif üretirler (tasarım §2.3).

Bu dosya kalıpları ve örnekleri kendisi taşır, ama kendini muaf tutmaz:
kalıplar karakter sınıfıyla (`k[e]...`), örnekler `|` ile bölünerek yazılır
(`_ornek`); dosya tarandığında kendi metni eşleşmez.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Taranan kalıplar (katlanmış metinde aranır). Karakter sınıfları yalnız bu
#: dosyanın kendi metnine takılmaması içindir; anlamı sınıfsız hâliyle aynıdır.
KALIPLAR: tuple[re.Pattern[str], ...] = tuple(
    re.compile(kaynak)
    for kaynak in (
        r"k[e]lebek",
        # Kelime sınırı ŞART: öncesinde harf ya da rakam (her alfabeden) olmamalı.
        # Inno'daki "Tasks:" ve "gitleaks:allow" böylece eşleşmez. `\b`'den tek
        # farkı alt çizgiyi AYIRICI saymasıdır: tanımlayıcının ortasında alt
        # çizgiden sonra gelen önek de yakalanır (`\b` onu kaçırırdı; örneği
        # `test_kaliplar_kalintiyi_yakalar`'da).
        r"(?<![^\W_])k[s][_:-]",
        r"x-k[s]-",
        r"k[s]bak",
        r"disiplin[ _-]?d[e]fteri",
        r"disiplin[d]efteri",
        r"x-d[d]-",
        r"d[d]bak",
    )
)

#: Her derinlikte atlanan dizin adları: sürüm denetimi, üçüncü taraf paketler,
#: Python bayt kodu. Adı `_cache` ile biten araç önbellekleri de atlanır
#: (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`).
ATLANAN_DIZIN_ADLARI = frozenset({".git", "node_modules", "__pycache__"})

#: Depo köküne göre atlanan yollar: kapsam dışı ya da depo içeriği olmayanlar.
ATLANAN_YOLLAR: dict[str, str] = {
    "docs": "köken ve karar belgeleri kardeş projeleri adıyla anlatır (tasarım §2.3: kapsam dışı)",
    "frontend/dist": "ön yüz derleme çıktısı; kaynağı frontend/src taranır",
    "backend/data": "yerel çalışma verisi; .gitignore'da, depoya girmez (KVKK)",
    "build": "PyInstaller ara çıktısı; .gitignore'da",
    "dist": "paket çıktısı; .gitignore'da, içindeki kaynak kopyası zaten taranır",
    ".claude/settings.local.json": "Claude Code yerel oturum ayarı; .gitignore'da, depoya girmez",
}

#: Depoda olup BİLEREK muaf tutulan dosyalar — tam yol ile, joker yok. Liste
#: şişirilmez: bulgu çıkan dosya düzeltilir, buraya eklenmez.
MUAF_DOSYALAR: dict[str, str] = {
    "CLAUDE.md": (
        "ajan brifingi; projenin kökenini anlatır ve kardeş projeleri (KS, DD) "
        "meşru olarak adıyla anar (§1 Köken, §2-14 kalıp listesinin kendisi)"
    ),
    "AGENTS.md": "CLAUDE.md'ye işaret eden brifing girişi; aynı köken gerekçesi",
    "packaging/ikonlar/logo_uret.py": (
        "geçici logo — teknik borç TB4 (docs/teknik-borc.md): kardeş projenin "
        "çizimini üretir; logo değişince muafiyet silinir"
    ),
}

#: Teknik borca bağlı muafiyetler: borç kapanınca (dosyada kalıntı kalmayınca)
#: muafiyet de silinmelidir; `test_teknik_borc_muafiyeti_hala_gerekli` hatırlatır.
TEKNIK_BORC_MUAFIYETLERI = ("packaging/ikonlar/logo_uret.py",)

_TR_KATLAMA = str.maketrans({"İ": "i", "I": "i", "ı": "i", "̇": None})


def katla(metin: str) -> str:
    """TR katlamalı küçük harf: İ/I/ı → i (ayrışık "I" + U+0307 dahil), sonra casefold."""
    return metin.translate(_TR_KATLAMA).casefold()


def _ornek(metin: str) -> str:
    """Test örneği: `|` bölücüsü atılır (bölünmüş hâli bu dosyanın taramasına takılmaz)."""
    return metin.replace("|", "")


def _dizin_atlanir(goreli: str, ad: str) -> bool:
    return ad in ATLANAN_DIZIN_ADLARI or ad.endswith("_cache") or goreli in ATLANAN_YOLLAR


def taranan_dosyalar(kok: Path) -> Iterator[str]:
    """Taranacak dosyaların köke göre POSIX yolları (sıralı, sembolik bağlar hariç)."""
    for dizin, altlar, dosyalar in os.walk(kok):
        taban = Path(dizin).relative_to(kok).as_posix()
        onek = "" if taban == "." else f"{taban}/"
        altlar[:] = sorted(ad for ad in altlar if not _dizin_atlanir(onek + ad, ad))
        for ad in sorted(dosyalar):
            goreli = onek + ad
            if goreli in ATLANAN_YOLLAR or (kok / goreli).is_symlink():
                continue
            yield goreli


def _metin(yol: Path) -> str | None:
    """Dosyanın metni; NUL baytı taşıyan (ikili) dosyada None."""
    veri = yol.read_bytes()
    if b"\x00" in veri:
        return None
    # UTF-8 dışı metin de taranır: kalıplar ASCII'dir, bozuk bayt eşleşmeyi engellemez.
    return veri.decode("utf-8", errors="replace")


def _satir_bulgulari(konum: str, satir: str) -> list[str]:
    katli = katla(satir)
    bulgular: list[str] = []
    for kalip in KALIPLAR:
        eslesme = kalip.search(katli)
        if eslesme is not None:
            bulgular.append(f"{konum}: {kalip.pattern} → {eslesme.group(0)!r}")
    return bulgular


def dosya_bulgulari(kok: Path, goreli: str) -> list[str]:
    """Tek dosyanın bulguları: önce yolun kendisi (`yol:0`), sonra satırlar (`yol:n`)."""
    bulgular = _satir_bulgulari(f"{goreli}:0 (dosya yolu)", goreli)
    metin = _metin(kok / goreli)
    if metin is None:
        return bulgular
    # `splitlines()` değil: \x0c gibi ayırıcılar satır numarasını editörden kaydırırdı.
    for numara, satir in enumerate(metin.split("\n"), 1):
        bulgular += _satir_bulgulari(f"{goreli}:{numara}", satir)
    return bulgular


def tara(kok: Path) -> list[str]:
    """Kökün altındaki bütün kalıntı bulguları (`yol:satır: kalıp → eşleşen`)."""
    bulgular: list[str] = []
    for goreli in taranan_dosyalar(kok):
        if goreli not in MUAF_DOSYALAR:
            bulgular += dosya_bulgulari(kok, goreli)
    return bulgular


# ---------------------------------------------------------------------------
# Kapı
# ---------------------------------------------------------------------------


def test_depoda_kimlik_kalintisi_yok() -> None:
    bulgular = tara(REPO)
    assert bulgular == [], (
        "Kardeş proje kimliğinden kalıntı bulundu (tasarım §2.3; F0 kapısı sıfır ister). "
        "Dosyayı düzeltin; muafiyet listesine eklemeyin:\n  " + "\n  ".join(bulgular)
    )


def test_tarama_kapsami_bos_degil() -> None:
    """Budama kapsamı yememeli: kaynak, şablon, ön yüz, betik ve CI taranır."""
    taranan = set(taranan_dosyalar(REPO))
    for beklenen in (
        "README.md",
        "docker-compose.yml",
        "scripts/gates.sh",
        ".github/workflows/kapilar.yml",
        "backend/config/settings.py",
        "backend/templates/documents/base.html",
        "desktop/main.py",
        "packaging/windows/kutuphane-defteri.iss",
        "packaging/pyinstaller/kutuphane_defteri.spec",
        "packaging/tests/test_kimlik_kalintisi.py",
        "frontend/package.json",
    ):
        assert beklenen in taranan, beklenen
    assert any(yol.startswith("frontend/src/") for yol in taranan)
    for yol in taranan:
        parcalar = yol.split("/")
        assert parcalar[0] != "docs", yol
        assert not set(parcalar) & ATLANAN_DIZIN_ADLARI, yol
        assert not any(parca.endswith("_cache") for parca in parcalar), yol


# ---------------------------------------------------------------------------
# Kalıpların davranışı
# ---------------------------------------------------------------------------


def test_kelime_siniri_yanlis_pozitif_vermez() -> None:
    """Inno ve gitleaks satırları ile sıradan sözcükler eşleşmez (kelime sınırı)."""
    for satir in (
        # packaging/windows/kutuphane-defteri.iss'teki gerçek satırın sonu:
        'AppUserModelID: "{#AppUserModelId}"; Tasks: desktopicon',
        # desktop/tests/test_session_guard.py'deki gerçek satır:
        'TOKEN = "test-belirteci-1234567890"  # gitleaks:allow — yalnız test sabiti',
        "TASKS: yedek",
        "books_count = len(links)  # thanks: bookmarks-bar",
        "Disiplin kurulu kararı ve sınav takvimi",  # yalın sözcükler taranmaz
        "defteri disiplinli tut",
    ):
        assert _satir_bulgulari("ornek:1", satir) == [], satir


def test_kaliplar_kalintiyi_yakalar() -> None:
    for satir in (
        _ornek("KS|_DATA_DIR = os.environ.get('KS|_DATA_DIR')"),
        _ornek("x_k|s_token = 1"),  # alt çizgi ayırıcı sayılır
        _ornek("k|s: satır başında önek"),
        _ornek("# (K|S-kaynaklı) açıklama"),
        _ornek("headers['X-K|S-Token']"),
        _ornek("yedek.k|sbak"),
        _ornek("Kele|bek Sınav"),
        _ornek("KELE|BEK"),
        _ornek("Disiplin |Defteri"),
        _ornek("DİSİPLİN |DEFTERİ"),  # Türkçe büyük İ
        _ornek("DISIPLIN |DEFTERI"),  # ASCII büyük I
        _ornek("disiplin_|defteri"),
        _ornek("disiplin-|defteri"),
        _ornek("Disiplin|Defteri"),
        _ornek("X-D|D-Token"),
        _ornek("arsiv.d|dbak"),
    ):
        assert _satir_bulgulari("ornek:1", satir) != [], satir


def test_tr_katlama() -> None:
    assert katla("DİSİPLİN") == "disiplin"
    assert katla("DISIPLIN") == "disiplin"
    assert katla("dısıplın") == "disiplin"
    assert katla("İ") == "i"  # ayrışık yazılmış "İ"


# ---------------------------------------------------------------------------
# Ağaç dolaşımı ve muafiyetler
# ---------------------------------------------------------------------------


def _yaz(kok: Path, goreli: str, icerik: str | bytes) -> None:
    yol = kok / goreli
    yol.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(icerik, bytes):
        yol.write_bytes(icerik)
    else:
        yol.write_text(icerik, encoding="utf-8")


def test_tarama_atlananlari_ve_muaflari_gecer_gerisini_yakalar(tmp_path: Path) -> None:
    kalinti = _ornek("ad = 'Kele|bek'\n")
    _yaz(tmp_path, "src/a.py", "temiz = 1\n" + kalinti)
    # Atlananlar: kapsam dışı, üçüncü taraf, önbellek, derleme çıktısı, yerel veri.
    for goreli in (
        "docs/tasarim.md",
        "frontend/node_modules/paket/index.js",
        "frontend/dist/app.js",
        ".mypy_cache/3.12/x.json",
        "src/__pycache__/a.txt",
        "backend/data/not.txt",
        "dist/cikti/BENIOKU.txt",
        ".claude/settings.local.json",
    ):
        _yaz(tmp_path, goreli, kalinti)
    # İkili dosya (NUL baytı) metin olarak taranmaz.
    _yaz(tmp_path, "src/gorsel.png", b"\x89PNG\x00" + kalinti.encode())
    # Muafiyet TAM YOL iledir: kökteki CLAUDE.md muaf, alt dizindeki değil.
    for goreli in MUAF_DOSYALAR:
        _yaz(tmp_path, goreli, kalinti)
    _yaz(tmp_path, "alt/CLAUDE.md", kalinti)
    # Dosya adındaki kalıntı da bulgudur.
    _yaz(tmp_path, _ornek("src/k|s_ayar.txt"), "temiz\n")

    bulgular = tara(tmp_path)
    konumlar = sorted(bulgu.split(": ", 1)[0] for bulgu in bulgular)
    assert konumlar == sorted(
        ["alt/CLAUDE.md:1", "src/a.py:2", _ornek("src/k|s_ayar.txt:0 (dosya yolu)")]
    )


def test_muaf_dosyalar_depoda_var() -> None:
    """Silinen ya da taşınan dosyanın muafiyeti bayat kalmasın."""
    for goreli, gerekce in MUAF_DOSYALAR.items():
        assert (REPO / goreli).is_file(), f"muaf dosya yok (muafiyeti silin): {goreli}"
        assert gerekce.strip(), goreli


def test_teknik_borc_muafiyeti_hala_gerekli() -> None:
    """Borç kapanınca muafiyet de kapanır: kalıntısı kalmayan dosya listeden çıkar."""
    for goreli in TEKNIK_BORC_MUAFIYETLERI:
        assert goreli in MUAF_DOSYALAR
        assert dosya_bulgulari(REPO, goreli) != [], (
            f"{goreli} artık kalıntı taşımıyor: MUAF_DOSYALAR'dan ve "
            "TEKNIK_BORC_MUAFIYETLERI'nden silin, docs/teknik-borc.md'deki kalemi kapatın."
        )
