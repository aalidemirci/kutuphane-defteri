"""Ağ Kataloğu vitrini gerçek çok okunanlar hesabından okur — §5.10-4/5 F10'da yeniden koşar.

F5-F9'da vitrin testleri `kd_katalog_populer`'e elle satır yazıyordu. F10'da tablo
gün değişimi kapısının GERÇEK hesabıyla (`services.populer.gunluk_is`) dolar ve:

- vitrin DÖNEM penceresinin sırasını gösterir; tek üyenin tekrarlanan ödünçleriyle
  "popüler" olmuş eser vitrine girmez (§5.10-12 ağda da);
- **sayı gösterilmez** (ne ödünç ne üye sayısı) ve sentetik üyenin adı, okul no'su,
  kart no'su, iade tarihleri ve üyenin aldığı öbür eserler hiçbir sayfada geçmez
  (§5.10-5);
- vitrin sayfasını üreten bağlantı yalnız izinli (tablo, sütun) kümesini okur,
  hiçbir okuma reddedilmez (§5.10-4 — kaydedici authorizer; anlık görüntünün kendisi
  `test_veri_erisimi.py`'dedir).

Dosya tabanlı test veritabanı ve `transaction=True` (tasarım §5.3 "Test ortamı").
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pytest
from django.utils import timezone

from apps.kutuphane.models import Copy, Loan, Membership
from apps.kutuphane.services import circulation, populer
from apps.kutuphane.tests.dolasim_ortak import ders_yili, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.ortak import eser, nusha
from katalog import veri
from katalog.bakim import BakimKapisi
from katalog.tests.conftest import KatalogIstemcisi

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def okunanlar(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, set[Any]]]:
    """Katalog bağlantısına kararı `veri.yetkilendir`'e bırakan kaydedici takar.

    `test_veri_erisimi.kaydedici` ile aynıdır; ek olarak görünüm DIŞINDAN (5. argüman
    boş) okunan sütunları da kaydeder: `kd_katalog_populer`'den ne okunduğu görülsün.
    """
    kayit: dict[str, set[Any]] = {"gorunumden": set(), "dogrudan": set(), "red": set()}
    asil_baglan = veri.baglan

    def kaydeden(eylem: int, a1: Any, a2: Any, db: Any, ic: Any) -> int:
        karar = veri.yetkilendir(eylem, a1, a2, db, ic)
        if eylem == sqlite3.SQLITE_READ:
            kayit["gorunumden" if ic is not None else "dogrudan"].add((a1, a2))
        if karar != sqlite3.SQLITE_OK:
            kayit["red"].add((eylem, a1, a2, ic))
        return karar

    @contextmanager
    def baglan(db_yolu: Path, **kw: Any) -> Iterator[sqlite3.Connection]:
        with asil_baglan(db_yolu, yetkilendirici=kaydeden, **kw) as conn:
            yield conn

    monkeypatch.setattr(veri, "baglan", baglan)
    yield kayit


#: Ders yılının 1. dönemi 07.09.2026-22.01.2027 (`ders_yili`); hesap günü dönemin içinde.
HESAP_GUNU = date(2026, 11, 16)
ODUNC_GUNU = date(2026, 11, 2)
SENTINELLER = ("Vitrinogrenciad", "Vitrinogrencisoyad", "369258")


def _okut(copy: Copy, uyelik: Membership) -> Loan:
    loan = odunc_ver(uyelik, copy)
    circulation.return_copy(copy=copy)
    an = timezone.make_aware(datetime.combine(ODUNC_GUNU, time(11)))
    Loan.objects.filter(pk=loan.pk).update(loaned_at=an)
    loan.refresh_from_db()
    return loan


def _kurgu() -> dict[str, Any]:
    ders_yili()
    ozel = uye(
        ogrenci(first_name=SENTINELLER[0], last_name=SENTINELLER[1], student_number=SENTINELLER[2])
    )
    digerleri = [uye(ogrenci()) for _ in range(5)]
    iz: list[str] = [ozel.card_no]
    # Beş farklı üye → vitrine girer; altı farklı üye → önde.
    bes = eser(title="Beş Üyenin Kitabı", authors="Deneme Yazar")
    bes_nusha = nusha(bes)
    for uyelik in digerleri:
        iz.append(f"{_okut(bes_nusha, uyelik).due_date:%d.%m.%Y}")
    alti = eser(title="Altı Üyenin Kitabı", authors="Deneme Yazar")
    alti_nusha = nusha(alti)
    for uyelik in [ozel, *digerleri]:
        _okut(alti_nusha, uyelik)
    # Tek üyenin on ödüncü → vitrine GİRMEZ (§5.10-12).
    tekrar = eser(title="Tek Üyenin Tekrar Kitabı", authors="Deneme Yazar")
    tekrar_nusha = nusha(tekrar)
    for _ in range(10):
        _okut(tekrar_nusha, ozel)
    assert populer.gunluk_is(HESAP_GUNU, kapi=BakimKapisi()) == "tamam"
    return {"alti": alti, "bes": bes, "tekrar": tekrar, "izler": [*SENTINELLER, *iz]}


def test_vitrin_gercek_hesabi_sirayla_ve_sayisiz_gosterir(katalog: KatalogIstemcisi) -> None:
    kurgu = _kurgu()

    metin = katalog.get("/").text

    cok = metin.split("Çok Okunanlar", 1)[1]
    assert cok.index("Altı Üyenin Kitabı") < cok.index("Beş Üyenin Kitabı")
    assert "Tek Üyenin Tekrar Kitabı" not in cok
    assert not re.search(r"\d+\s*(kez|ödünç|üye|kişi)", metin)  # sayı gösterilmez
    for iz in kurgu["izler"]:
        assert iz.casefold() not in metin.casefold(), f"üye izi ({iz}) vitrinde geçti"


def test_eser_sayfalari_da_uye_izi_tasimaz(katalog: KatalogIstemcisi) -> None:
    kurgu = _kurgu()

    for work in (kurgu["alti"], kurgu["bes"], kurgu["tekrar"]):
        metin = katalog.get(f"/eser/{work.pk}").text
        for iz in kurgu["izler"]:
            assert iz.casefold() not in metin.casefold()
        assert not re.search(r"\d+\s*(kez|ödünç alındı|üye)", metin)


def test_vitrin_yalniz_izinli_okumalari_yapar(
    katalog: KatalogIstemcisi, okunanlar: dict[str, set[Any]]
) -> None:
    _kurgu()

    assert katalog.get("/").code == 200

    assert okunanlar["red"] == set()
    assert okunanlar["gorunumden"] <= veri.IZINLI_OKUMALAR
    # Çok okunanlar tablosundan yalnız sıra ve pencere okunur — tabloda sayı sütunu yoktur.
    populerden = {sutun for tablo, sutun in okunanlar["dogrudan"] if tablo == "kd_katalog_populer"}
    assert populerden == {"eser_id", "pencere_turu", "pencere", "sira", "hesaplanma"}
