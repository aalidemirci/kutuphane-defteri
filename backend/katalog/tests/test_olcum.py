"""F5 ölçümü: 10.000 eser ve 20.000 nüshada Ağ Kataloğu sayfaları akıcı mı (tasarım §5.3).

Katalog her isteği ayrı bir salt okur bağlantıyla ve 2 sn'lik sorgu süresi
sınırıyla (`veri.VARSAYILAN_SORGU_SURESI`) karşılar; görünüm tanımlarındaki
ilişkili alt sorgular (nüsha sayaçları) ya da harf dizininin `substr` süzgeci
büyük katalogda bu sınıra yaklaşırsa sayfa 503'e düşerdi. Bu test Md. 7/1'in
10.000 kitap eşiğindeki bir katalogda her sayfa türünü ölçer.

**Varsayılan kapı koşusunda ATLANIR** (F3 ölçüm testiyle aynı düzen,
`apps/kutuphane/tests/test_ice_aktarma_olcum.py`): `KD_YAVAS=1` ile koşar.

    docker compose run --rm -T -e KD_YAVAS=1 backend \\
        pytest katalog/tests/test_olcum.py -m yavas -q --no-cov -s

Veri toplu yazılır (`bulk_create`): anahtar alanları `Work.save()`'in türettiği
biçimde elle doldurulur (`keys` — tek katlama kaynağı). Kişisel veri yoktur.
"""

from __future__ import annotations

import os
import time
from datetime import date

import pytest

from apps.kutuphane import isbn as isbn_module
from apps.kutuphane import keys
from apps.kutuphane.models import Acquisition, AcquisitionMethod, Copy, CopyStatus, Work
from apps.kutuphane.tests import sentetik_katalog
from katalog.tests.conftest import KatalogIstemcisi

ESER_SAYISI = 10_000
#: Sayfa başına kaba tavan (sn). 2 sn'lik sorgu sınırının yarısı: sınıf
#: değişimini (tam tarama × alt sorgu) yakalar, makine hızına kırılgan değildir.
TAVAN_SAYFA = 1.0

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.yavas,
    pytest.mark.skipif(
        os.environ.get("KD_YAVAS") != "1",
        reason="Ölçüm testi kapıda atlanır; KD_YAVAS=1 ile koşar.",
    ),
]


def _buyuk_katalog() -> int:
    edinim = Acquisition.objects.create(
        method=AcquisitionMethod.EXISTING_STOCK, date=date(2026, 9, 1)
    )
    eserler = []
    for sira, satir in enumerate(sentetik_katalog.sentetik_satirlar(ESER_SAYISI), start=1):
        baslik = f"{satir['title']} {sira}"
        yazar = str(satir.get("authors") or "")
        konu = str(satir.get("subjects") or "")
        isbn = str(satir.get("isbn") or "")
        isbn13 = isbn_module.to_isbn13(isbn)
        eserler.append(
            Work(
                title=baslik,
                authors=yazar,
                subjects=konu,
                isbn=isbn,
                isbn13=isbn13,
                classification_code=f"{sira % 10}{sira % 100:02d}",
                search_key=keys.work_search_key(
                    title=baslik, authors=yazar, subjects=konu, isbn=isbn, isbn13=isbn13
                ),
                sort_key=keys.tr_collation_key(baslik),
                author_sort_key=keys.tr_collation_key(keys.author_sort_name(yazar)),
                subject_sort_key=keys.tr_collation_key(keys.first_subject(konu)),
            )
        )
    Work.objects.bulk_create(eserler, batch_size=2000)
    nushalar = []
    no = 0
    for work in Work.objects.only("pk").order_by("pk"):
        for kopya in range(2):
            no += 1
            nushalar.append(
                Copy(
                    work_id=work.pk,
                    acquisition=edinim,
                    accession_no=2026_000000 + no,
                    barcode=f"{2026_000000 + no}",
                    status=CopyStatus.ON_LOAN if (no % 7 == 0) else CopyStatus.AVAILABLE,
                    is_reference=kopya == 1 and no % 11 == 0,
                )
            )
    Copy.objects.bulk_create(nushalar, batch_size=5000)
    ilk: int = Work.objects.order_by("pk").values_list("pk", flat=True)[0]
    return ilk


def test_on_bin_eserde_katalog_sayfalari_akicidir(katalog: KatalogIstemcisi) -> None:
    ilk = _buyuk_katalog()
    adresler = [
        "/",
        "/ara",
        "/ara?sayfa=250",
        "/ara?q=madonna",
        "/ara?q=roman",
        "/ara?tur=kitap&konu=8&sayfa=3",
        "/eserler",
        "/eserler/K",
        "/eserler/%C3%87",
        "/yazarlar/A",
        "/konular",
        "/konular/T",
        f"/eser/{ilk}",
    ]
    for adres in adresler:
        baslangic = time.perf_counter()
        yanit = katalog.get(adres)
        gecen = time.perf_counter() - baslangic
        print(f"\n[ölçüm] {adres}: {gecen * 1000:.0f} ms")  # noqa: T201
        assert yanit.code == 200, adres
        assert gecen < TAVAN_SAYFA, f"{adres} çok yavaş: {gecen:.2f} sn"
