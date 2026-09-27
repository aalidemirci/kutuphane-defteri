"""F10-D kullanıcı metinleri — kılavuz, ön yüz sabitleri ve sözlük backend'le birebir.

Kılavuzdaki mevzuat alıntıları belgelerdeki sabitlerle aynı olmalıdır (her atıf depodaki
metinden doğrulanır — `test_dokumler.py`); ön yüzde elle kopyalanmış adlar (ara sayımın eki,
Bakanlık sistemi ayarı) backend'le ayrışmamalıdır; sözlük yeni adları taşır. Test ön yüz
kaynağını METİN olarak okur (host'ta Node yoktur).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import katalog_dokumu, sayim_belgeleri, tmy_dokumleri
from apps.kutuphane.services import export_import


def _oku(yol: Path) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı.")


def _tek_satir(metin: str) -> str:
    return " ".join(metin.replace("&apos;", "'").split())


_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_SAYIM_API = Path("frontend") / "src" / "modules" / "sayim" / "api.ts"
_HATIRLATMA = Path("frontend") / "src" / "modules" / "kutuphane" / "BakanlikHatirlatmasi.tsx"
_SOZLUK = Path("docs") / "sozluk.md"


def test_kilavuzdaki_alintilar_belgelerle_birebir() -> None:
    kilavuz = _tek_satir(_oku(_KILAVUZ))
    assert f"“{katalog_dokumu.MD_11_1}”" in kilavuz
    assert f"“Kütüphane Defteri: {tmy_dokumleri.TMY_9_1_C}”" in kilavuz
    assert f"“{tmy_dokumleri.TMY_34_3_A}”" in kilavuz
    assert "sayım kurulunca onaylanan Taşınır Sayım ve Döküm Cetveline dayanır" in kilavuz
    # K6: kılavuz ara sayımın ekinin başlığını belgeyle aynı yazar.
    assert f"“{sayim_belgeleri.ARA_SAYIM_ADI}”" in kilavuz


def test_on_yuzdeki_ara_sayim_adi_backendle_ayni() -> None:
    kaynak = _oku(_SAYIM_API)
    eslesme = re.search(r'export const ARA_SAYIM_ADI = "([^"]+)";', kaynak)
    assert eslesme is not None, "sayim/api.ts içinde ARA_SAYIM_ADI yok"
    assert eslesme.group(1) == sayim_belgeleri.ARA_SAYIM_ADI
    assert f'export const EK_ADI = "{sayim_belgeleri.EK_ADI}";' in kaynak


def test_bakanlik_hatirlatmasi_konum_dilini_soyler() -> None:
    kaynak = _tek_satir(_oku(_HATIRLATMA))
    assert "Bakanlık otomasyon sistemindeki kaydı da güncelleyin" in kaynak
    assert "o sistemin yerine geçmez" in kaynak
    # "Bakanlık otomasyon sisteminin yerine geçer" iddiası hiçbir metinde yok (CLAUDE.md §2-13).
    assert "yerine geçer" not in kaynak.replace("yerine geçmez", "")


def test_sozluk_yeni_adlari_tasir() -> None:
    sozluk = _tek_satir(_oku(_SOZLUK))
    for ad in (
        "Bakanlık sistemi kullanımda",
        "Dışa aktarım dosyası",
        "Alfabetik katalog dökümü",
        "Taşınır Kütüphane Defteri dökümü",
        "Yönetim hesabı cetveli hazırlığı",
        "Kişi dökümü",
        "İçe aktarılacak dosya",
        sayim_belgeleri.ARA_SAYIM_ADI,
        sayim_belgeleri.ARA_SAYIM_BASLIGI,
        _tek_satir(tmy_dokumleri.HESAP_NOTU),
    ):
        assert ad in sozluk, ad


def test_disa_aktarim_iletilerinde_ic_kod_yok() -> None:
    """Sözlük §2: iç kodlar (U1, F10, E11…) kullanıcı metnine girmez."""
    iletiler = [
        getattr(export_import, ad)
        for ad in dir(export_import)
        if ad.endswith(("_MESSAGE", "_NOTE")) and isinstance(getattr(export_import, ad), str)
    ]
    assert iletiler
    for ileti in iletiler:
        assert not re.search(r"\b(U\d+|F\d+|E\d+|T\d+|A\d+|D\d+|K\d+)\b", ileti), ileti
