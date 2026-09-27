"""F10 Raporlar ekranı — ön yüz sabitleri, kılavuz ve sözlük backend'le ve mevzuatla birebir.

Ön yüzde elle kopyalanmış adlar ve alıntılar (Md. 7/1 bilgi kartı, Kılavuz 7 önerisi, belge
adları, iç çıktının sıra sınırları) backend sabitlerinden ayrışmamalıdır; kılavuzdaki
alıntılar depodaki mevzuat metninde birebir geçmelidir (CLAUDE.md §2-13). Test ön yüz
kaynağını METİN olarak okur (host'ta Node yoktur).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.kutuphane import (
    ayin_kitaplari_belgesi,
    okuma_odulu_belgesi,
    selectors_istatistik,
    selectors_okuma_odulu,
)


def _oku(yol: Path) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı.")


def _tek_satir(metin: str) -> str:
    return " ".join(metin.replace("&apos;", "'").split())


_API = Path("frontend") / "src" / "modules" / "raporlar" / "api.ts"
_KILAVUZ = Path("frontend") / "src" / "modules" / "kilavuz" / "KilavuzPage.tsx"
_SOZLUK = Path("docs") / "sozluk.md"
_YONETMELIK = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi.md"
_UYGULAMA = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md"


def _ts_metin(kaynak: str, ad: str) -> str:
    eslesme = re.search(rf'export const {ad} =\s*"([^"]+)";', kaynak)
    assert eslesme is not None, f"raporlar/api.ts içinde `{ad}` yok"
    return eslesme.group(1)


def _ts_sayi(kaynak: str, ad: str) -> int:
    eslesme = re.search(rf"export const {ad} = (\d+);", kaynak)
    assert eslesme is not None, f"raporlar/api.ts içinde `{ad}` yok"
    return int(eslesme.group(1))


@pytest.mark.parametrize(
    ("ad", "beklenen"),
    [
        ("MD7_1_METNI", selectors_istatistik.MD7_1_METNI),
        ("KILAVUZ_7_ONERISI", okuma_odulu_belgesi.KILAVUZ_7_ONERISI),
        ("AYIN_KITAPLARI_ADI", ayin_kitaplari_belgesi.BELGE_ADI),
        ("OKUMA_ODULU_ADI", okuma_odulu_belgesi.BELGE_ADI),
    ],
)
def test_on_yuzdeki_metinler_backendle_ayni(ad: str, beklenen: str) -> None:
    assert _ts_metin(_oku(_API), ad) == beklenen


@pytest.mark.parametrize(
    ("ad", "beklenen"),
    [
        ("ODUL_SIRA_VARSAYILAN", selectors_okuma_odulu.VARSAYILAN_SIRA),
        ("ODUL_SIRA_EN_COK", selectors_okuma_odulu.EN_COK_SIRA),
    ],
)
def test_on_yuzdeki_ic_cikti_sinirlari_seciciyle_ayni(ad: str, beklenen: int) -> None:
    assert _ts_sayi(_oku(_API), ad) == beklenen


def test_md7_ve_kilavuz7_alintilari_mevzuatta_birebir() -> None:
    assert selectors_istatistik.MD7_1_METNI in _tek_satir(_oku(_YONETMELIK))
    assert okuma_odulu_belgesi.KILAVUZ_7_ONERISI in _tek_satir(_oku(_UYGULAMA))


def test_kilavuzdaki_rapor_alintilari_birebir() -> None:
    kilavuz = _tek_satir(_oku(_KILAVUZ))
    assert f"“{selectors_istatistik.MD7_1_METNI}”" in kilavuz
    assert f"“{okuma_odulu_belgesi.KILAVUZ_7_ONERISI}”" in kilavuz
    # Md. 15/1-ğ kısmi alıntı ("…" ile başlar): parça metinde birebir geçer.
    eslesme = re.search(r"“…(okul kütüphanesinde çok okunan[^”]+)”", kilavuz)
    assert eslesme is not None
    assert eslesme.group(1) in _tek_satir(_oku(_YONETMELIK))
    # Kılavuz 6.2 alıntılanmaz: metni programın kılavuzunun yasakladığı "otomasyon sistemi"ni
    # anar; kılavuz yalnız bölüm numarasıyla gönderir.
    assert "Uygulama Kılavuzu (6.2)" in kilavuz
    assert "otomasyon sistemi" not in kilavuz


def test_sozluk_rapor_adlarini_tasir() -> None:
    sozluk = _tek_satir(_oku(_SOZLUK))
    assert "### 4.16 Raporlar, istatistik ve çok okunanlar" in sozluk
    for ad in (
        "Raporlar",
        "**İstatistik** (`istatistik`)",
        "**Çok Okunanlar** (`cok-okunanlar`)",
        "**Dökümler** (`dokumler`)",
        "**Okuma Ödülü** (`okuma-odulu`)",
        "Dönemin Çok Okunanları",
        "Yeniden hesapla",
        "Kitap Sayısı 10.000'i Aştı",
        ayin_kitaplari_belgesi.BELGE_ADI,
        ayin_kitaplari_belgesi.BASLIK,
        okuma_odulu_belgesi.BELGE_ADI,
        okuma_odulu_belgesi.BASLIK,
        okuma_odulu_belgesi.IC_KULLANIM,
    ):
        assert ad in sozluk, ad


@pytest.mark.parametrize(
    ("baslangic", "yasaklar"),
    [
        ("| Çok okunanlar (`kd_katalog_populer`)", ("popüler", "en çok ödünç alınanlar")),
        # §2'deki kod tablosunun "| E20 | Okuma ödülü …" satırı değil, §4.16'nın kavram satırı.
        ("| E20 | belge", ("okuma karnesi", "okuma puanı", "okuduğu kitaplar")),
    ],
)
def test_f10_yasak_sozcukler_kullanilmaz_sutununda(
    baslangic: str, yasaklar: tuple[str, ...]
) -> None:
    satir = next(s for s in _oku(_SOZLUK).splitlines() if s.startswith(baslangic))
    hucreler = satir.split("|")
    for yasak in yasaklar:
        assert yasak in hucreler[3], f"{baslangic}: {yasak}"
        assert yasak not in hucreler[2].casefold(), f"{baslangic}: {yasak}"
