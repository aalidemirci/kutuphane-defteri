"""Kurtarma anahtarı çıktısı (E14) — `POST security/recovery-key/pdf/` (F1-E kod kapısı).

Kanıtlanan maddeler (sözleşme E):

* anahtar `guvenlik.json`'daki kurtarma sarmalını açmıyorsa 400 + kademeli
  gecikme, PDF üretilmez (yanlış yazılmış anahtar kâğıda basılmaz);
* doğru anahtarla PDF üretilir ve İÇERİKTE anahtar vardır (pypdf ile metin
  çıkarılır); belge tek sayfadır (sayfa bütçesi gerçek uzunlukta verilerle);
* anahtar hiçbir günlüğe düşmez (caplog, DEBUG düzeyinde bütün kaydediciler)
  ve hata gövdesinde yankılanmaz;
* kilitliyken kilit kapısı keser (`security/` önekine rağmen), görevli kipinde
  kapalıdır, parola kurulmadan çalışmaz.
"""

from __future__ import annotations

import logging
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.okul.kip import KIP
from apps.okul.services import app_password
from apps.okul.services import setup as setup_service
from conftest import TEST_KURTARMA_ANAHTARI
from shared import crypto

URL = "/api/v1/security/recovery-key/pdf/"
KANONIK = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLM"
SADE = KANONIK.replace("-", "")
YANLIS = "TEST-KURT-ARMA-ANAH-TARI-ABCD-EFGH-JKLN"

pytestmark = pytest.mark.django_db


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _iste(client: APIClient, anahtar: str) -> Any:
    return client.post(URL, {"recovery_key": anahtar}, format="json")


def _pdf(yanit: Any) -> bytes:
    return b"".join(yanit.streaming_content)


def _metin(icerik: bytes) -> str:
    return "\n".join(sayfa.extract_text() or "" for sayfa in PdfReader(BytesIO(icerik)).pages)


def _bosluksuz(metin: str) -> str:
    return re.sub(r"\s+", "", metin)


def test_sabit_anahtar_kanonik_bicimle_ayni() -> None:
    """Testin kendi varsayımı: conftest anahtarı sekiz dörtlü gruptur."""
    assert app_password.recovery_key_groups(TEST_KURTARMA_ANAHTARI) == KANONIK.split("-")


def test_dogru_anahtarla_pdf_uretilir_ve_icerikte_anahtar_var(client: APIClient) -> None:
    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Cache-Control"] == "no-store"
    icerik = _pdf(yanit)
    assert icerik.startswith(b"%PDF-")
    metin = _metin(icerik)
    assert KANONIK in _bosluksuz(metin)
    assert "KURTARMA ANAHTARI" in metin
    assert f"{timezone.localdate():%d.%m.%Y}" in metin
    assert "Kütüphane Defteri" in metin


def test_dosya_adi_belge_adi_ve_tarih_anahtarsiz(client: APIClient) -> None:
    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
    baslik = unquote(yanit["Content-Disposition"])
    assert baslik.startswith("attachment;")
    assert f"Kurtarma-Anahtarı-Çıktısı_{timezone.localdate():%d.%m.%Y}.pdf" in baslik
    assert KANONIK not in baslik and SADE not in baslik


@pytest.mark.parametrize(
    "yazim",
    [
        SADE.lower(),
        " ".join(KANONIK.split("-")),
        f"  {KANONIK}  ",
        SADE,
        # Türkçe klavye: büyük harf "i" noktalı "İ" olur; küçük "ı" da "I"dır.
        KANONIK.replace("I", "İ"),
        SADE.lower().replace("i", "ı"),
    ],
    ids=["kucuk_harf", "bosluklu", "kenar_bosluklu", "tiresiz", "turkce_buyuk_i", "noktasiz_i"],
)
def test_farkli_yazimlar_kabul_edilir_pdfte_kanonik_bicim(client: APIClient, yazim: str) -> None:
    yanit = _iste(client, yazim)
    assert yanit.status_code == 200
    assert KANONIK in _bosluksuz(_metin(_pdf(yanit)))


def test_okul_adi_ve_demirbas_no_basilir(client: APIClient) -> None:
    setup_service.update_school_config(
        fields={"school_name": "Örnek Anadolu Lisesi", "district": "Örnek", "demirbas_no": "BLG-17"}
    )
    metin = _metin(_pdf(_iste(client, TEST_KURTARMA_ANAHTARI)))
    assert "Örnek Anadolu Lisesi Müdürlüğü" in metin
    assert "ÖRNEK KAYMAKAMLIĞI" in metin
    assert "BLG-17" in metin


def test_sayfa_butcesi_uzun_okul_adi_ve_demirbas_no_ile_tek_sayfa(client: APIClient) -> None:
    """Sayfa bütçesi gerçek uzunlukta verilerle (CLAUDE.md §3): en uzun künye tek sayfa."""
    setup_service.update_school_config(
        fields={
            "school_name": (
                "Örnek Mahallesi Cumhuriyet Mesleki ve Teknik Anadolu Lisesi "
                "Çok Programlı Pansiyonlu Ek Binası"
            ),
            "district": "Örnekkaraağaç",
            "demirbas_no": "255.01.02.03-2026/000123-BİLGİSAYAR-MASAÜSTÜ-KÜTÜPHANE",
        }
    )
    icerik = _pdf(_iste(client, TEST_KURTARMA_ANAHTARI))
    assert len(PdfReader(BytesIO(icerik)).pages) == 1


def test_yanlis_anahtar_400_pdf_yok_ileti_anahtari_yankilamaz(client: APIClient) -> None:
    yanit = _iste(client, YANLIS)
    assert yanit.status_code == 400
    govde = yanit.json()
    assert govde["code"] == "validation_error"
    assert govde["message"].startswith("Kurtarma anahtarı hatalı.")
    assert YANLIS not in yanit.content.decode("utf-8")
    assert YANLIS.replace("-", "") not in yanit.content.decode("utf-8")


def test_yanlis_anahtarda_kademeli_gecikme_uygulanir(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kaba kuvvete kapı olmasın: yanlış deneme app_password'ün kademeli gecikmesine girer."""
    uyumalar: list[float] = []
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 3.0))
    monkeypatch.setattr(time, "sleep", uyumalar.append)

    _iste(client, YANLIS)
    _iste(client, YANLIS)
    assert uyumalar == [3.0]
    # Doğru anahtar sayacı sıfırlar.
    assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
    _iste(client, YANLIS)
    assert uyumalar == [3.0]


def test_baska_kurulumun_dosyasiyla_dogrulama_yapilamaz(
    client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sarmal açılsa bile DEK bellekteki anahtar değilse (başka kurulum) PDF basılmaz."""
    baska = app_password._build_state(
        bytes(range(1, 33)), password="Baska-Parola-9", recovery_key=TEST_KURTARMA_ANAHTARI
    )
    baska["gecis"] = app_password.TRANSITION_DONE
    app_password._write_state(baska)
    uyumalar: list[float] = []
    monkeypatch.setattr(app_password, "FAILURE_DELAYS", (2.0,))
    monkeypatch.setattr(time, "sleep", uyumalar.append)

    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
    assert yanit.status_code == 400
    assert yanit.json()["message"].startswith("Kurtarma anahtarı hatalı.")
    assert uyumalar == [2.0]


def test_bos_ya_da_asiri_uzun_anahtar_reddedilir(client: APIClient) -> None:
    assert client.post(URL, {}, format="json").status_code == 400
    assert _iste(client, "").status_code == 400
    uzun = _iste(client, "A" * 129)
    assert uzun.status_code == 400
    assert "A" * 129 not in uzun.content.decode("utf-8")


def test_kilitliyken_kilit_kapisi_keser(client: APIClient, kilitli: Path) -> None:
    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
    assert yanit.status_code == 423
    assert yanit.json()["code"] == "locked"
    # Önekteki diğer uçlar kilitliyken açık kalır (kilit açma yolu).
    assert client.get("/api/v1/security/status/").status_code == 200


def test_servis_de_kilitliyken_dogrulamaz() -> None:
    """Savunma derinliği: ara katman atlansa da bellekte anahtar yokken doğrulama yok."""
    crypto.unload_key()
    with pytest.raises(app_password.AppPasswordError, match="kilitli"):
        app_password.verify_recovery_key(TEST_KURTARMA_ANAHTARI)


def test_parola_kurulmadan_calismaz(client: APIClient, parolasiz: Path) -> None:
    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
    assert yanit.status_code == 400
    assert yanit.json()["message"] == "Yönetici parolası kurulu değil."


def test_gorevli_kipinde_kapali(client: APIClient) -> None:
    KIP.gorevliye_gec()
    yanit = _iste(client, TEST_KURTARMA_ANAHTARI)
    assert yanit.status_code == 403
    assert yanit.json()["code"] == "kip_yetkisiz"


def test_anahtar_hicbir_gunluge_dusmez(client: APIClient, caplog: pytest.LogCaptureFixture) -> None:
    """Başarılı, yanlış ve bozuk isteklerde bütün kaydediciler DEBUG'da dinlenir."""
    caplog.set_level(logging.DEBUG)
    assert _iste(client, TEST_KURTARMA_ANAHTARI).status_code == 200
    assert _iste(client, YANLIS).status_code == 400
    assert _iste(client, SADE.lower()).status_code == 200
    assert _iste(client, "B" * 129).status_code == 400

    yasak = {TEST_KURTARMA_ANAHTARI, KANONIK, SADE, SADE.lower(), YANLIS, YANLIS.replace("-", "")}
    for kayit in caplog.records:
        ileti = kayit.getMessage()
        for sir in yasak:
            assert sir not in ileti, (kayit.name, ileti)
            assert sir not in repr(kayit.args), kayit.name
    for sir in yasak:
        assert sir not in caplog.text
