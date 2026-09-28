"""Dış yedek hatırlatması (F11; tasarım §16 risk 13) — servis ve `backups/external/` ucu.

Kanıtlanan maddeler:

* şifreli yedek indirmesi (`POST backups/encrypted/`) son indirme tarihini veri
  dizinindeki `dis-yedek.json`'a yazar; veritabanına YAZMAZ (geri yükleme geri sarmaz);
* hiç indirme yokken hatırlatma parola kurulumundan 7 gün sonra, indirme varken son
  indirmeden `hatirlatma_gun` (varsayılan 30) gün sonra başlar;
* süre 7-90 gün arasında ayarlanır; aralık dışı 400; bozuk dosya "hiç indirme yok" sayılır;
* uç görevli kipinde 403 `kip_yetkisiz`, kilitliyken 423; yanıtta kişisel veri yok.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.services import app_password, dis_yedek

URL = "/api/v1/backups/external/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _kurulum_tarihini_yaz(gun: date) -> None:
    """Güvenlik dosyasının oluşturma damgasını geriye alır (parola `gun` günü kurulmuş)."""
    durum = app_password.read_state()
    assert durum is not None
    an = timezone.make_aware(datetime(gun.year, gun.month, gun.day, 9, 0))
    durum["olusturma"] = an.isoformat(timespec="seconds")
    app_password._write_state(durum)  # noqa: SLF001


def test_parola_kurulur_kurulmaz_hatirlatma_yok() -> None:
    bugun = timezone.localdate()
    _kurulum_tarihini_yaz(bugun)

    ozet = dis_yedek.durum(bugun)

    assert ozet.son_indirme is None
    assert ozet.hatirlatma_gun == dis_yedek.VARSAYILAN_HATIRLATMA_GUN == 30
    assert ozet.gecen_gun == 0
    assert ozet.hatirlat is False


def test_hic_indirme_yoksa_parola_kurulumundan_yedi_gun_sonra_hatirlatir() -> None:
    bugun = date(2026, 9, 27)
    _kurulum_tarihini_yaz(bugun - timedelta(days=6))
    assert dis_yedek.durum(bugun).hatirlat is False

    _kurulum_tarihini_yaz(bugun - timedelta(days=7))
    ozet = dis_yedek.durum(bugun)
    assert ozet.hatirlat is True
    assert ozet.gecen_gun == 7
    assert ozet.son_indirme is None


def test_indirme_saati_sifirlar_ve_sure_dolunca_hatirlatir() -> None:
    _kurulum_tarihini_yaz(date(2026, 1, 1))
    indirme = timezone.make_aware(datetime(2026, 9, 1, 14, 30))
    dis_yedek.indirme_kaydet(indirme)

    assert dis_yedek.durum(date(2026, 9, 30)).hatirlat is False  # 29 gün
    ozet = dis_yedek.durum(date(2026, 10, 1))  # 30 gün
    assert ozet.hatirlat is True
    assert ozet.gecen_gun == 30
    assert ozet.son_indirme is not None and ozet.son_indirme.startswith("2026-09-01T14:30")


def test_sifreli_yedek_indirmesi_tarihi_veri_dizinine_yazar(
    client: APIClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # İndirilen görüntünün kaynağı dosya tabanlı bir SQLite olmalıdır (test DB'si değil).
    kaynak = tmp_path / "db.sqlite3"
    with closing(sqlite3.connect(kaynak)) as baglanti:
        baglanti.execute("CREATE TABLE deneme (deger TEXT)")
        baglanti.commit()
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", kaynak)
    yol = dis_yedek.dosya_yolu()
    assert not yol.exists()

    yanit = client.post("/api/v1/backups/encrypted/")

    assert yanit.status_code == 200
    kayit = json.loads(yol.read_text(encoding="utf-8"))
    assert kayit["son_indirme"].startswith(timezone.localdate().isoformat())
    assert kayit["hatirlatma_gun"] == 30
    # Dosya güvenlik dosyasının yanındadır (veritabanında değil — geri yükleme geri sarmaz).
    assert yol.parent == app_password.state_path().parent
    ozet = client.get(URL).json()
    assert ozet["days_since"] == 0
    assert ozet["remind"] is False


def test_hatirlatma_suresi_ayarlanir_ve_aralik_disi_reddedilir(client: APIClient) -> None:
    yanit = client.put(URL, {"reminder_days": 60}, format="json")

    assert yanit.status_code == 200
    assert yanit.json()["reminder_days"] == 60
    assert dis_yedek.durum().hatirlatma_gun == 60
    # İndirme kaydı süreyi korur.
    dis_yedek.indirme_kaydet()
    assert dis_yedek.durum().hatirlatma_gun == 60

    for gecersiz in (6, 91, "otuz", None):
        ret = client.put(URL, {"reminder_days": gecersiz}, format="json")
        assert ret.status_code == 400, gecersiz
        assert "7 ile 90 gün" in json.dumps(ret.json(), ensure_ascii=False)
    assert dis_yedek.durum().hatirlatma_gun == 60


def test_bozuk_dosya_hic_indirme_yok_sayilir_ve_yazim_onarir() -> None:
    dis_yedek.dosya_yolu().write_text("{bozuk", encoding="utf-8")

    assert dis_yedek.durum().son_indirme is None
    dis_yedek.indirme_kaydet()
    assert dis_yedek.durum().son_indirme is not None


def test_yazilamayan_dosya_indirmeyi_durdurmaz(monkeypatch: pytest.MonkeyPatch) -> None:
    def patla(_veri: dict[str, Any]) -> None:
        raise OSError("disk dolu")

    monkeypatch.setattr(dis_yedek, "_yaz", patla)

    dis_yedek.indirme_kaydet()  # hata yükseltmez


def test_yanit_kisisel_veri_tasimaz(client: APIClient) -> None:
    govde = client.get(URL).json()

    assert set(govde) == {
        "last_download",
        "reminder_days",
        "days_since",
        "remind",
        "min_reminder_days",
        "max_reminder_days",
    }


def test_parola_kurulmamissa_hatirlatma_yok(parolasiz: Path, client: APIClient) -> None:
    ozet = client.get(URL).json()

    assert ozet["remind"] is False
    assert ozet["days_since"] is None


def test_gorevli_kipinde_kapali(client: APIClient) -> None:
    KIP.gorevliye_gec()

    for yanit in (client.get(URL), client.put(URL, {"reminder_days": 30}, format="json")):
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"


def test_kilitliyken_kapali(kilitli: Path, client: APIClient) -> None:
    yanit = client.get(URL)

    assert yanit.status_code == 423
    assert yanit.json()["code"] == "locked"
