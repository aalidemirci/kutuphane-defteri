"""Paketlenmiş programın giriş noktası (PyInstaller `kutuphane_defteri.spec`).

Normal çalışmada tek işi vardır: `desktop.main.run()`'a devretmek. Kabuğun
kendisi `desktop/` altındadır ve bu dosyaya bağımlı DEĞİLDİR — depodan
`python -m desktop.main` ile çalıştırmak da aynı sonucu verir.

Ek olarak paketlenmiş sürümde **iki teşhis kipi** sunar:

    kutuphane-defteri --bagimlilik-duman

Bu kip `RUNTIME_MODULES`'ın tamamını import eder ve hiddenimports zincirinin
çalışma anı kapısıdır: spec'e eklenmesi unutulan bir bağımlılık burada, derleme
sırasında yakalanır — sahada değil. Aşağıdaki PDF kipi yalnız WeasyPrint
zincirini sınadığı için tek başına yetmez (KS'de `xlrd` eklendiğinde görüldü:
yeni bağımlılığın pakete girip girmediğini sınayan kapı yoktu).

    kutuphane-defteri --pdf-duman [dosya.pdf]

Bu kip evrakın ortak taban şablonundan (`templates/documents/base.html`) küçük
bir Türkçe örnek belge üretir ve pypdf ile geri okuyup doğrular. Amacı üç
katmanı ayrı ayrı sınamaktır:

1. **Evrak şablonları pakette mi** — şablon ağacı pakete kaynak olarak
   kopyalanır (spec `Tree`). Yol bozulursa gerçek evrak sahada ilk basımda
   düşerdi; bu kip şablonu paketteki yerinden Django şablon motoruyla işler
   (`{% extends %}` + `{% include "print/_design.css" %}` dahil) ve sayfa
   altlığındaki "Sayfa n / m" metnini arar — metin yoksa taban şablon
   uygulanmamış demektir.
2. **PDF motoru ayakta mı** — Windows'ta WeasyPrint pango/harfbuzz/fontconfig
   DLL'lerini çalışma anında `dlopen` ile açar; paketten bir DLL eksikse bu
   kip ilk açılışta değil, burada patlar ("WeasyPrint Windows DLL" tuzağı —
   packaging/windows/NOTLAR.md).
3. **Türkçe karakterler doğru font ile mi diziliyor** — üretilen PDF'te
   `ĞÜŞİÖÇ ığüşiöç` metni geri okunabiliyor ve kullanılan font gömülü DejaVu
   ise, fontconfig gömülü fonta bakıyor demektir ("fontconfig tuzağı" —
   `fonts.conf.tmpl` başlığı).

KS'deki JPEG gömme denetimi bilinçli olarak ALINMADI: tek JPEG üreticisi
öğrenci fotoğrafıydı ve fotoğraf özelliği bu projede yok. Evrakta raster
fotoğraf basılmadığı için denetim ürünün kullanmadığı bir yolu sınardı;
Pillow'un pakette olduğunu `--bagimlilik-duman` zaten kanıtlar.

Kip hem CI duman testinde hem de sahada "programın PDF üretimi çalışıyor
mu?" sorusunu tek komutla yanıtlamak için kullanılır. Veritabanına DOKUNMAZ:
Django ayarları yüklenmez (şablon motoru ayarsız, bağımsız bir `Engine`
örneğiyle kurulur), veri dizinine yazılmaz.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

# Depodan doğrudan çalıştırıldığında (`python packaging/pyinstaller/giris.py`)
# depo kökü `sys.path`'te olmayabilir; paketlenmiş çalışmada zaten donmuş hâlde.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PDF_SMOKE_FLAG = "--pdf-duman"
IMPORT_SMOKE_FLAG = "--bagimlilik-duman"

# `desktop/errors.py` 0-7 arasını kullanıyor; teşhis kipi 8'den devam eder
# (9 = --geri-yukle). Kodlar `desktop/errors.py` ile İKİZDİR.
EXIT_PDF_SMOKE_FAILED = 8
EXIT_IMPORT_SMOKE_FAILED = 10

#: Paketin İÇİNDE çalışma anında bulunması ZORUNLU üçüncü taraf modüller.
#:
#: hiddenimports zincirinin son halkası. İlk üç halka STATİKTİR ve bir modülün
#: pakete gerçekten girdiğini kanıtlamaz:
#:   requirements.txt → DAGITIM_IMPORT_ESLEME → spec hiddenimports
#: Bu liste dördüncü halkadır: paketlenmiş ikili her derlemede modülleri
#: GERÇEKTEN import eder. `--pdf-duman` yalnız WeasyPrint zincirini sınar;
#: KS'de `xlrd` eklendiğinde onun paketlenip paketlenmediğini sınayan hiçbir
#: kapı olmadığı görüldü (e-Okul .xls içe aktarımı sahada çökebilirdi).
#:
#: Liste `backend/requirements.txt` ile senkron tutulur; kaymayı
#: `packaging/tests/test_spec_kapsami.py` kapıya bağlar.
RUNTIME_MODULES: tuple[str, ...] = (
    "django",
    "rest_framework",
    "argon2",
    "cryptography",
    "openpyxl",
    "xlrd",
    "PIL",
    "weasyprint",
    "pypdf",
    "whitenoise",
    "waitress",
)

# Duman testinin aradığı metin — Türkçe'ye özgü altı harf, hem büyük hem küçük.
TURKISH_SAMPLE = "ĞÜŞİÖÇ ığüşiöç"
# Yalnız gömülü DejaVu ile dizilmeli; sistem fontuna düşerse bu ad görünmez.
EXPECTED_FONT_FRAGMENT = "DejaVu"
# Taban şablonun `@page` altlığı ("Sayfa 1 / 1"); görünmüyorsa şablon uygulanmadı.
BASE_TEMPLATE_MARKER = "Sayfa"
# Evrakın ortak taban şablonu (backend/templates altında).
BASE_TEMPLATE = "documents/base.html"

# Örnek belge taban şablonu genişletir; bütün kurum ve eser adları UYDURMADIR.
_SMOKE_TEMPLATE = """{% extends "documents/base.html" %}
{% block content %}
  <div class="doc-title">PDF DUMAN TESTİ</div>
  <div class="doc-subtitle">Kütüphane Defteri — paket doğrulama belgesi</div>
  <p class="para">{{ sample }}</p>
  <table class="info">
    <tr><td class="label">Eser</td><td>Örnek Eser Adı</td></tr>
    <tr><td class="label">Yazar</td><td>Örnek Yazar</td></tr>
    <tr><td class="label">Nüsha durumu</td><td>Rafta</td></tr>
  </table>
  <p class="para">Bu belge paketin PDF üretim zincirini sınar; veritabanına dokunmaz.</p>
{% endblock %}
"""
_SMOKE_CONTEXT = {
    "sample": TURKISH_SAMPLE,
    "authority": "ÖRNEK İLÇE KAYMAKAMLIĞI",
    "unit_line": "Örnek Ortaokulu Müdürlüğü",
}


class SmokeTemplateMissing(Exception):
    """Evrak şablon ağacı pakette bulunamadı (spec `Tree` yolu bozuk olabilir)."""


def _write(message: str) -> None:
    """Teşhis çıktısı — konsol yoksa (Windows penceresiz derleme) sessiz geçer.

    `print()` bilinçli olarak kullanılmaz: paketlenmiş penceresiz derlemede
    `sys.stdout` `None`'dır ve `print` orada `AttributeError` üretir.
    """
    stream = sys.stderr
    if stream is None:
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except (OSError, ValueError):
        return


def _templates_dir() -> Path:
    """Evrak şablonlarının kökü — paketlenmiş ve depo çalışmasında aynı çözümle.

    Kabuğun kullandığı `resolve_backend_dir()` burada da kullanılır: duman testi
    programın şablonları GERÇEKTE bulacağı yeri sınamalıdır.
    """
    from desktop.paths import resolve_backend_dir

    try:
        return resolve_backend_dir() / "templates"
    except FileNotFoundError as error:
        raise SmokeTemplateMissing(str(error)) from error


def render_smoke_html(templates: Path) -> str:
    """Örnek belgeyi taban şablondan HTML'e işler (Django ayarı gerektirmez)."""
    from django.template import Context, Engine, TemplateDoesNotExist

    if not (templates / BASE_TEMPLATE).is_file():
        raise SmokeTemplateMissing(f"{templates / BASE_TEMPLATE} yok")
    engine = Engine(dirs=[str(templates)])
    try:
        return engine.from_string(_SMOKE_TEMPLATE).render(Context(dict(_SMOKE_CONTEXT)))
    except TemplateDoesNotExist as error:
        raise SmokeTemplateMissing(f"şablon çözülemedi: {error}") from error


def _pdf_fonts(pdf_path: Path) -> set[str]:
    """PDF'in ilk sayfasındaki gömülü font adlarını döndürür."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    resources = reader.pages[0].get("/Resources")
    if resources is None:
        return set()
    fonts = resources.get_object().get("/Font")
    if fonts is None:
        return set()
    names: set[str] = set()
    for value in fonts.get_object().values():
        base_font = value.get_object().get("/BaseFont")
        if base_font is not None:
            names.add(str(base_font))
    return names


def _pdf_text(pdf_path: Path) -> str:
    """PDF'in ilk sayfasındaki metni döndürür."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return reader.pages[0].extract_text() or ""


def _fontconfig_teshisi() -> None:
    """Font eşleşmesi başarısızsa NEDEN olduğunu yazar.

    Windows'ta fontconfig yapılandırması ya hiç okunmaz (env yok) ya da
    ayrıştırılamayıp SESSİZCE reddedilir; ikisinde de sonuç aynıdır — sistem
    fontuna düşer. Bu ayrımı log'suz yapmak imkânsız olduğu için tanılama
    doğrudan buraya konur (CI koşusu başına ~5 dk; tahminle iterasyon pahalı).
    """
    import os

    for degisken in ("FONTCONFIG_FILE", "FONTCONFIG_PATH", "KD_RTHOOK_UYARI"):
        _write(f"  {degisken}={os.environ.get(degisken, '<yok>')}")

    conf = os.environ.get("FONTCONFIG_FILE", "")
    if conf:
        yol = Path(conf)
        _write(f"  fonts.conf var mı: {yol.is_file()}")
        if yol.is_file():
            try:
                _write("  fonts.conf içeriği (ilk 400 karakter):")
                _write("    " + yol.read_text(encoding="utf-8")[:400].replace("\n", "\n    "))
            except OSError as hata:
                _write(f"  fonts.conf okunamadı: {hata}")

    kok = Path(getattr(sys, "_MEIPASS", _REPO_ROOT))
    font_dizini = kok / "fonts"
    _write(f"  gömülü font dizini: {font_dizini} (var mı: {font_dizini.is_dir()})")
    if font_dizini.is_dir():
        _write(f"  içindekiler: {sorted(p.name for p in font_dizini.iterdir())}")


def run_pdf_smoke(target: Path) -> int:
    """Taban şablondan Türkçe örnek belge üretir, geri okuyup doğrular; 0 = başarılı."""
    try:
        html = render_smoke_html(_templates_dir())
    except SmokeTemplateMissing as error:
        _write(
            f"HATA: evrak şablonu pakette bulunamadı ({error}). "
            "spec'teki backend/templates Tree yolu bozulmuş olabilir."
        )
        return EXIT_PDF_SMOKE_FAILED

    from weasyprint import HTML

    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(target))
    if not target.is_file() or target.stat().st_size == 0:
        _write(f"HATA: PDF üretilemedi ({target}).")
        return EXIT_PDF_SMOKE_FAILED

    text = _pdf_text(target)
    # PDF metin çıkarımı satır sonu/boşluk ekleyebilir; boşluklar atılıp örnek
    # metin BÜTÜN olarak aranır (belgenin geri kalanı da Türkçe harf taşıdığı
    # için harf harf aramak eksik glifi gizleyebilirdi).
    duz_metin = "".join(text.split())
    if "".join(TURKISH_SAMPLE.split()) not in duz_metin:
        missing = [harf for harf in TURKISH_SAMPLE if harf != " " and harf not in duz_metin]
        _write(
            "HATA: PDF metninde Türkçe örnek bulunamadı"
            + (f" (eksik harfler: {''.join(missing)})" if missing else "")
            + "."
        )
        _write(f"Okunan metin: {text!r}")
        return EXIT_PDF_SMOKE_FAILED

    if BASE_TEMPLATE_MARKER not in text:
        _write(
            f"HATA: taban şablonun sayfa altlığı ('{BASE_TEMPLATE_MARKER} n / m') PDF'te yok; "
            f"{BASE_TEMPLATE} uygulanmamış görünüyor."
        )
        return EXIT_PDF_SMOKE_FAILED

    fonts = _pdf_fonts(target)
    if not any(EXPECTED_FONT_FRAGMENT in name for name in sorted(fonts)):
        _write(
            "HATA: PDF gömülü DejaVu fontu ile dizilmemiş "
            f"(bulunan fontlar: {sorted(fonts)}). Fontconfig sistem fontuna düşmüş olabilir."
        )
        _fontconfig_teshisi()
        return EXIT_PDF_SMOKE_FAILED

    _write(f"PDF duman testi başarılı: {target}")
    _write(f"Fontlar: {sorted(fonts)}")
    return 0


def run_import_smoke() -> int:
    """`RUNTIME_MODULES`'ın tamamını import eder; 0 = hepsi pakette.

    Django ayağa KALDIRILMAZ, veri dizinine dokunulmaz — yalnız modül çözümü
    sınanır. Bir modül eksikse paket "geliştirmede çalışıyor, kurulumda
    çöküyor" sınıfına girer; hangi modülün düştüğü tek tek yazılır.
    """
    import importlib

    eksik: list[str] = []
    for modul in RUNTIME_MODULES:
        try:
            importlib.import_module(modul)
        except Exception as hata:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            eksik.append(f"{modul} ({hata!r})")

    if eksik:
        _write("HATA: şu modüller pakette çözülemedi (hiddenimports eksiği):")
        for satir in eksik:
            _write(f"  - {satir}")
        _write("Düzeltme: packaging/pyinstaller/kutuphane_defteri.spec → hiddenimports.")
        return EXIT_IMPORT_SMOKE_FAILED

    _write(f"Bağımlılık duman testi başarılı: {len(RUNTIME_MODULES)} modül çözüldü.")
    return 0


def _smoke_target(argv: Sequence[str]) -> Path:
    """`--pdf-duman` sonrasında dosya yolu verildiyse onu, yoksa geçici dosyayı seçer."""
    index = list(argv).index(PDF_SMOKE_FLAG)
    rest = list(argv)[index + 1 :]
    if rest and not rest[0].startswith("-"):
        return Path(rest[0])
    return Path(tempfile.gettempdir()) / "kutuphane-defteri-pdf-duman.pdf"


def run(argv: Sequence[str] | None = None) -> int:
    """Argümanlara göre teşhis kipini veya normal açılışı çalıştırır."""
    args = list(sys.argv[1:] if argv is None else argv)
    if IMPORT_SMOKE_FLAG in args:
        try:
            return run_import_smoke()
        except Exception as error:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            _write(f"HATA: bağımlılık duman testi çöktü: {error!r}")
            return EXIT_IMPORT_SMOKE_FAILED

    if PDF_SMOKE_FLAG in args:
        try:
            return run_pdf_smoke(_smoke_target(args))
        except Exception as error:  # noqa: BLE001 — teşhis kipi: her hata rapor edilir
            _write(f"HATA: PDF duman testi çöktü: {error!r}")
            return EXIT_PDF_SMOKE_FAILED

    from desktop.main import run as run_shell

    return run_shell(args)


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
