"""Kütüphane testlerinin ortak fikstürleri (F6 — dolaşım).

`bugun`: argümansız `timezone.localdate()`'i sabitler (`dolasim_ortak.gunu_sabitle`);
dönen listenin ilk öğesi değiştirilerek gün ilerletilir. Yalnız isteyen testte etkilidir.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.kutuphane.tests.dolasim_ortak import gunu_sabitle


@pytest.fixture
def bugun(monkeypatch: pytest.MonkeyPatch) -> list[date]:
    return gunu_sabitle(monkeypatch)
