"""`kutuphane` göç ağacının koruma testleri (F2 — app bu fazda modelleniyor).

`okul` için aynısı `apps/okul/tests/test_migrations.py`'dedir; kütüphane app'i
F1'de modelsizdi, göç ağacı burada `0001_initial` ile başlar. İki şeyi sabitler:

- Modellerde yapılan ve göçe dökülmemiş değişiklik YOKTUR (masaüstü açılışı
  `migrate` koşar; eksik göç kurulu programda şemayı sessizce eskide bırakır).
- Ağaç tek yapraklıdır (iki dal aynı anda göç eklerse `migrate` çakışır).
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader


@pytest.mark.django_db
def test_kutuphane_modellerinde_goce_dokulmemis_degisiklik_yoktur() -> None:
    cikti = StringIO()
    try:
        call_command(
            "makemigrations", "kutuphane", "--check", "--dry-run", stdout=cikti, stderr=cikti
        )
    except SystemExit as exc:  # `--check` eksik göçte 1 koduyla çıkar
        pytest.fail(
            f"Eksik göç var — `makemigrations kutuphane` çalıştırın:\n{cikti.getvalue()} ({exc})"
        )


@pytest.mark.django_db
def test_kutuphane_goc_agaci_tek_yaprakli_ve_0001den_baslar() -> None:
    loader = MigrationLoader(connection)
    yapraklar = loader.graph.leaf_nodes("kutuphane")
    assert len(yapraklar) == 1, f"Birden çok yaprak göç: {yapraklar}"
    kokler = [ad for app, ad in loader.graph.root_nodes("kutuphane") if app == "kutuphane"]
    assert kokler == ["0001_initial"]
