"""F3 ölçüm kapısı: 10.000 satırlık aktarım ve 10.000 nüshada katalog akıcılığı.

Tasarım §14.1 F3: "10.000 satırlık sentetik dosya ölçülür · katalog listesi,
arama ve sayfalama 10.000 nüshada akıcı." Md. 7/1'in 10.000 kitap eşiği de aynı
büyüklüktür: ölçüm, programın hedeflediği en büyük okulun verisidir.

**Varsayılan kapı koşusunda ATLANIR.** Ölçüm 10.000 eser ve 10.000 nüsha yazar;
her kapı koşusunda bunu tekrarlamak `scripts/gates.sh`'i gereksiz yere uzatır.
Ama "yalnız elle koşulabilen kapı maddesi" de kapı değildir: `scripts/gates.sh`
`KD_YAVAS=1` verildiğinde bu testi de koşar ve CI'da gecelik iş (ya da elle
tetikleme) o değişkeni verir (`.github/workflows/kapilar.yml`). Elden koşmak
için:

    KD_YAVAS=1 docker compose run --rm -T -e KD_YAVAS=1 backend \\
        pytest apps/kutuphane/tests/test_ice_aktarma_olcum.py -m yavas -q --no-cov -s

Süre VE TEPE BELLEK `-s` ile ekrana basılır; testin kendisi yalnız KABA
tavanları denetler. Amaç kronometre tutmak değil, SINIF değişimini yakalamaktır:
satır başına sorgu atan bir gerileme (eşleştirme dizininin ya da bölüm
önbelleğinin kaybı) süre tavanını, satır başına nesne biriktiren bir gerileme
(rapor satırlarının ikinci kopyası, nüsha nesnelerinin listede tutulması)
bellek tavanını anında aşar.

Sentetik dosya depoya konmaz, çalışma anında üretilir (`sentetik_katalog`):
kamu malı eser adları + sağlaması geçerli UYDURMA ISBN'ler, kişisel veri yok.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from rest_framework.test import APIClient

from apps.kutuphane.models import CatalogImportSource, Copy, Work
from apps.kutuphane.services import import_service as ia
from apps.kutuphane.tests import sentetik_katalog

#: Ölçümün satır sayısı (§14.1 F3 ve Md. 7/1 eşiği).
SATIR_SAYISI = 10_000

#: Kaba tavanlar (saniye). Geliştirme makinesinde ölçülen sürelerin birkaç katı:
#: gerileme sınıfını yakalar, makine hızına göre kırılganlık yapmaz.
TAVAN_AYRISTIRMA = 60.0
TAVAN_UYGULAMA = 300.0
TAVAN_LISTE = 3.0

#: Kaba tepe bellek tavanı (MB). 23.09.2026 ölçümü: 148 MB (test başında 110).
#: Tavan ölçülenin üç katından fazladır: amaç MB saymak değil, satır başına
#: NESNE biriktiren bir gerilemeyi yakalamaktır — 10.000 satır × 50 nüsha
#: sınırında tutulan bir nüsha listesi tavanı anında aşar.
TAVAN_TEPE_BELLEK_MB = 512.0

#: `resource` Windows'ta yoktur; testler yalnız Docker'da (Linux) koşar
#: (CLAUDE.md §2-11), ama toplama aşaması host'ta da patlamasın.
try:
    import resource as _resource
except ImportError:  # pragma: no cover — yalnız Docker dışında
    _resource = None  # type: ignore[assignment]

pytestmark = [
    pytest.mark.django_db(transaction=False),
    pytest.mark.yavas,
    pytest.mark.skipif(
        os.environ.get("KD_YAVAS") != "1",
        reason="Ölçüm testi kapıda atlanır; KD_YAVAS=1 ile koşar.",
    ),
]


@contextmanager
def _sure(ad: str, tavan: float) -> Iterator[None]:
    baslangic = time.perf_counter()
    yield
    gecen = time.perf_counter() - baslangic
    print(f"\n[ölçüm] {ad}: {gecen:.2f} sn (tavan {tavan:.0f} sn)")  # noqa: T201
    assert gecen < tavan, f"{ad} çok yavaş: {gecen:.2f} sn"


def _tepe_bellek_mb() -> float:
    """Sürecin o ana kadarki TEPE bellek kullanımı (MB).

    `tracemalloc` yerine `getrusage` seçildi: izleyicinin kendisi ölçümü kat kat
    yavaşlatır ve bu testin birinci işi süre sınıfını korumaktır. `ru_maxrss`
    Linux'ta KB'dir.
    """
    if _resource is None:  # pragma: no cover — yalnız Docker dışında
        return 0.0
    return float(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss) / 1024


def test_on_bin_satirlik_dosya_olculur() -> None:
    """Dosya üretimi → ayrıştırma → önizleme → uygulama → liste/arama/sayfalama."""
    bellek_baslangic = _tepe_bellek_mb()
    with _sure("dosya üretimi", TAVAN_AYRISTIRMA):
        dosya = sentetik_katalog.katalog_dosyasi(sentetik_katalog.sentetik_satirlar(SATIR_SAYISI))
    print(f"\n[ölçüm] dosya boyutu: {len(dosya) / 1024 / 1024:.1f} MB")  # noqa: T201

    with _sure("ayrıştırma", TAVAN_AYRISTIRMA):
        parsed, ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)
    assert len(parsed.rows) == SATIR_SAYISI

    bolumler = list(sentetik_katalog.BOLUMLER)
    with _sure("önizleme (yazar ve geri sarar)", TAVAN_UYGULAMA):
        onizleme = ia.preview_import(parsed, payload_sha256=ozet, new_sections=bolumler)
    assert onizleme.stats["copies_created"] == SATIR_SAYISI
    assert Work.objects.count() == 0, "önizleme yazdı"

    with _sure("uygulama", TAVAN_UYGULAMA):
        rapor = ia.apply_import(parsed, payload_sha256=ozet, new_sections=bolumler)

    assert rapor.stats == onizleme.stats, "önizleme ile uygulama ayrıştı"
    assert Work.objects.count() == SATIR_SAYISI
    assert Copy.objects.count() == SATIR_SAYISI

    _katalog_akiciligi()

    tepe = _tepe_bellek_mb()
    print(  # noqa: T201
        f"\n[ölçüm] tepe bellek: {tepe:.0f} MB "
        f"(test başında {bellek_baslangic:.0f} MB, tavan {TAVAN_TEPE_BELLEK_MB:.0f} MB)"
    )
    assert tepe < TAVAN_TEPE_BELLEK_MB, f"tepe bellek çok yüksek: {tepe:.0f} MB"


def _katalog_akiciligi() -> None:
    """10.000 nüshada liste, arama ve sayfalama (ön yüzün gerçekten çağırdığı uçlar)."""
    istemci = APIClient()
    olcumler = (
        ("katalog listesi (ilk sayfa)", "/api/v1/library/works/"),
        ("yazar ekseninde sıralama", "/api/v1/library/works/?order=author"),
        ("Türkçe arama", "/api/v1/library/works/?q=kürk"),
        ("ISBN araması", f"/api/v1/library/works/?q={sentetik_katalog.sentetik_isbn(5)}"),
        ("100. sayfa", "/api/v1/library/works/?page=100"),
        ("nüsha listesi (son sayfa)", "/api/v1/library/copies/?page=200"),
        ("koleksiyon özeti", "/api/v1/library/stats/"),
    )
    for ad, yol in olcumler:
        with _sure(ad, TAVAN_LISTE):
            yanit = istemci.get(yol)
        assert yanit.status_code == 200, (yol, yanit.status_code)
