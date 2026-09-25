"""Ön yüzde ELLE KOPYALANMIŞ backend sabitleri — iki kopyayı eşitleyen kapı.

CLAUDE.md §3 aynı sınıfı `version_key` için kayda geçiriyor: "iki kopyadır ve
aynı kalmalıdır". Sabit ayrışırsa iki katman aynı kural için farklı davranır —
sınır düşerse kullanıcı formun kabul ettiği bir sayıyla sunucudan ret alır,
yükselirse ön yüz geçerli bir sayıyı kendi engeller — ve iki katman farklı
ileti verir.

Test ön yüz kaynağını METİN olarak okur: Node çalıştırmadan (host'ta Node
yoktur) iki sayının eşitliğini sabitlemenin en ucuz yolu budur. Sabit taşınırsa
ya da adı değişirse test "bulunamadı" diyerek düşer, sessizce yeşil kalmaz.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from apps.kutuphane.import_schema import MAX_COPIES_PER_ROW
from apps.kutuphane.serializers import CopyBulkCreateSerializer

_KAYNAK = Path("frontend") / "src" / "modules" / "kutuphane" / "EserDetayPage.tsx"
_SABIT = re.compile(r"^const EN_COK_NUSHA = (\d+);$", flags=re.MULTILINE)


def _on_yuz_kaynagi(kaynak: Path = _KAYNAK) -> str:
    """Depo kökünü bulur: yerelde `depo/backend/...`, konteynerde `/app` + `/repo`."""
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        yol = kok / kaynak
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    pytest.fail(f"{kaynak} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def test_on_yuzdeki_toplu_nusha_siniri_backendle_aynidir() -> None:
    eslesme = _SABIT.search(_on_yuz_kaynagi())
    assert eslesme is not None, f"{_KAYNAK} içinde `const EN_COK_NUSHA = <sayı>;` yok."
    assert int(eslesme.group(1)) == MAX_COPIES_PER_ROW


def test_toplu_nusha_ucunun_ust_siniri_ayni_kaynaktan_gelir() -> None:
    """Serializer sınırı da aynı sabittir; üçüncü bir kopya doğmasın."""
    alan: Any = CopyBulkCreateSerializer().fields["count"]
    assert alan.max_value == MAX_COPIES_PER_ROW


# --- F7: yönetici kipi sürelerinin sınırları (Ayarlar → Kütüphane Politikası) ---
_POLITIKA = Path("frontend") / "src" / "modules" / "kutuphane" / "KutuphanePolitikasiPaneli.tsx"


@pytest.mark.parametrize(
    ("ad", "sabit"),
    [
        ("BOSTA_DK_EN_AZ", "IDLE_MINUTES_MIN"),
        ("BOSTA_DK_EN_COK", "IDLE_MINUTES_MAX"),
        ("MUTLAK_DK_EN_AZ", "ADMIN_MAX_MINUTES_MIN"),
        ("MUTLAK_DK_EN_COK", "ADMIN_MAX_MINUTES_MAX"),
    ],
)
def test_on_yuzdeki_kip_suresi_sinirlari_modelle_aynidir(ad: str, sabit: str) -> None:
    """Panelin yardım metnindeki sınır, model doğrulayıcısının sınırıyla aynıdır."""
    from apps.kutuphane import models

    eslesme = re.search(rf"^const {ad} = (\d+);$", _on_yuz_kaynagi(_POLITIKA), flags=re.MULTILINE)
    assert eslesme is not None, f"{_POLITIKA} içinde `const {ad} = <sayı>;` yok."
    assert int(eslesme.group(1)) == getattr(models, sabit)


# --- F9: sayım — okutma kuyruğu sınırı, hizmet arası iletisi ve nüsha durumu adları ---
_SAYIM_API = Path("frontend") / "src" / "modules" / "sayim" / "api.ts"
_SAYIM_KARTI = Path("frontend") / "src" / "modules" / "sayim" / "SayimKarti.tsx"
_KUTUPHANE_API = Path("frontend") / "src" / "modules" / "kutuphane" / "api.ts"


def test_on_yuzdeki_okutma_kuyrugu_siniri_servisle_aynidir() -> None:
    from apps.kutuphane.services.stocktake import MAX_SCANS_PER_REQUEST

    eslesme = re.search(
        r"^export const EN_COK_OKUTMA = (\d+);$", _on_yuz_kaynagi(_SAYIM_API), flags=re.MULTILINE
    )
    assert eslesme is not None, f"{_SAYIM_API} içinde `EN_COK_OKUTMA` yok."
    assert int(eslesme.group(1)) == MAX_SCANS_PER_REQUEST


def test_masadaki_hizmet_arasi_iletisi_sunucununkiyle_aynidir() -> None:
    """Görevli kipinde masa hizmet arasını sunucunun reddinden öğrenir; şerit aynı cümleyi yazar."""
    from apps.kutuphane.services.circulation import SERVICE_PAUSE_MESSAGE

    eslesme = re.search(
        r'^export const HIZMET_ARASI_SURUYOR =\s*"([^"]+)";$',
        _on_yuz_kaynagi(_SAYIM_KARTI),
        flags=re.MULTILINE,
    )
    assert eslesme is not None, f"{_SAYIM_KARTI} içinde `HIZMET_ARASI_SURUYOR` yok."
    assert eslesme.group(1) == SERVICE_PAUSE_MESSAGE


def test_on_yuzdeki_nusha_durumu_adlari_modelle_birebir() -> None:
    """`COPY_STATUS_TR` `CopyStatus.choices` ile aynı kodlar, aynı adlar ve aynı sıradadır."""
    from apps.kutuphane.models import CopyStatus

    blok = re.search(
        r"export const COPY_STATUS_TR: Record<CopyStatus, string> = \{(.*?)\n\};",
        _on_yuz_kaynagi(_KUTUPHANE_API),
        flags=re.DOTALL,
    )
    assert blok is not None, f"{_KUTUPHANE_API} içinde `COPY_STATUS_TR` yok."
    satirlar = re.findall(r'^\s+([A-Z_]+): "([^"]+)",$', blok.group(1), flags=re.MULTILINE)
    assert satirlar == [(str(kod), str(ad)) for kod, ad in CopyStatus.choices]


@pytest.mark.parametrize(
    ("ad", "sabit"),
    [
        ("TMY_DURDURMA_KAPSAMI", "TMY_STOP_SCOPE_TEXT"),
        ("TMY_DURDURMA_KAPSAMAZ", "TMY_STOP_NOT_COVERED_TEXT"),
    ],
)
def test_durdurmanin_kapsam_metinleri_sunucununkiyle_aynidir(ad: str, sabit: str) -> None:
    """Taslak, başlatma onayı, Genel Bakış kartı ve bantlar tutanağın sözcüklerini kullanır
    (F9 düzeltme turu: ekran "kayıp/hasar dosyası çözümü"nü bütünüyle, "ödünç açıktır"ı
    koşulsuz yazıyordu)."""
    from apps.kutuphane import selectors_sayim

    eslesme = re.search(
        rf'^export const {ad} =\s*"([^"]+)";$', _on_yuz_kaynagi(_SAYIM_API), flags=re.MULTILINE
    )
    assert eslesme is not None, f"{_SAYIM_API} içinde `{ad}` yok."
    assert eslesme.group(1) == getattr(selectors_sayim, sabit)


def test_programa_aktarim_iletisi_sunucununkiyle_aynidir() -> None:
    """F9 ekleri K4: aktarım bandı sunucunun TMY'siz ret iletisini birebir yazar."""
    from apps.kutuphane.services.tmy_kapisi import PROGRAMA_AKTARIM_MESSAGE

    eslesme = re.search(
        r'^export const PROGRAMA_AKTARIM_KAPALI =\s*"([^"]+)";$',
        _on_yuz_kaynagi(_SAYIM_API),
        flags=re.MULTILINE,
    )
    assert eslesme is not None, f"{_SAYIM_API} içinde `PROGRAMA_AKTARIM_KAPALI` yok."
    assert eslesme.group(1) == PROGRAMA_AKTARIM_MESSAGE
    assert "TMY" not in PROGRAMA_AKTARIM_MESSAGE
