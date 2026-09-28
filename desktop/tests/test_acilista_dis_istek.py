"""Açılışta dış istek YOK (T11; CLAUDE.md §3; F11 kod kapısı) — gerçek süreç, ağ tuzağıyla.

Dış istek yalnız kullanıcının başlattığı iki kapıdan çıkar (güncelleme denetimi ve
varsayılan kapalı ISBN künye sorgusu). Program açılırken — ilk açılışta da, yönetici
parolası kurulmuş, günlük yedeğin alındığı, göç denetiminin ve Ağ Kataloğu öz
sınamasının koştuğu olağan açılışta da — dışarı TEK bağlantı, TEK ad çözümü, TEK
`urlopen` çıkmaz. `desktop.tests.ag_tuzagi` soket katmanını programdan önce değiştirir
ve her dış denemeyi kaydeder; kayıt boş kalmalıdır.

`--autotest` gün değişimi kapısını (`kd-gunluk`) kurmadan döner; kapının arka plan
işleri (günlük yedek, çok okunanlar, saklama taraması) aynı tuzak altında AYRICA bir
kez koşar (`test_gun_degisimi_kapisinin_isleri_disari_istek_atmaz`, F11 düzeltme
turu). Kapının Ağ Kataloğu'na bağlı iki işi (IP denetimi, saatlik katalog denetimi)
katalog denetleyicisi ister ve burada kurulmaz; onlar yerel ağ arayüzlerine bakar
(`desktop/ag.py`'nin UDP rota sorgusu TEST-NET-1'e gider, paket göndermez) ve kaynak
düzeyindeki kapalı listenin kapsamındadır.

Kaynak düzeyindeki eşi `backend/apps/okul/tests/test_dis_istek_kapilari.py`'dir (ağ
istemcisi import eden modüllerin kapalı listesi; güncelleme denetimini yalnız
güncelleme uçlarının çağırması).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop.errors import EXIT_OK
from desktop.tests.alt_surec import betik, gunluk, kos

pytestmark = pytest.mark.slow


def _tuzakla(kayit: Path, *argv: str) -> int:
    sonuc = kos(
        ["-m", "desktop.tests.ag_tuzagi", *argv],
        ortam={"KD_AG_TUZAGI_KAYIT": str(kayit)},
    )
    return sonuc.returncode


def _kayitlar(kayit: Path) -> list[list[str]]:
    if not kayit.is_file():
        return []
    return [json.loads(satir) for satir in kayit.read_text(encoding="utf-8").splitlines() if satir]


def test_tuzak_dis_denemeyi_yakalar(tmp_path: Path) -> None:
    """Yanlış yeşile karşı: tuzak kurulu süreçteki dış denemeler kayda düşer."""
    kayit = tmp_path / "kayit.jsonl"

    assert _tuzakla(kayit, "--kendini-sina") == 0

    turler = {tur for tur, _hedef in _kayitlar(kayit)}
    assert {"dns", "urlopen"} <= turler


def test_acilista_disari_hic_istek_cikmaz(tmp_path: Path) -> None:
    kok = tmp_path / "veri"
    kayit = tmp_path / "kayit.jsonl"

    # İlk açılış: veritabanı yok, göç koşar, parola kurulmamış.
    assert _tuzakla(kayit, "--autotest", "--data-dir", str(kok)) == EXIT_OK, gunluk(kok)[-3000:]
    assert _kayitlar(kayit) == []

    # Olağan açılış: parola kurulu, kişi ve katalog verisi var — günlük yedek alınır,
    # göç denetimi ve Ağ Kataloğu öz sınaması koşar.
    betik("hazirla", "--data-dir", str(kok), "--usb", str(tmp_path / "usb"))
    for yedek in (kok / "backups").glob("gunluk-*.kdbak"):
        yedek.unlink()  # bugünün yedeği yeniden alınsın
    assert _tuzakla(kayit, "--autotest", "--data-dir", str(kok)) == EXIT_OK, gunluk(kok)[-3000:]
    assert list((kok / "backups").glob("gunluk-*.kdbak")), "günlük yedek alınmadı"
    assert _kayitlar(kayit) == []


def test_gun_degisimi_kapisinin_isleri_disari_istek_atmaz(tmp_path: Path) -> None:
    """F11 düzeltme turu: `--autotest` gün değişimi kapısını (`kd-gunluk`) kurmadan döner;
    gerçek açılışta kapı ilk tikte kayıtlı arka plan işlerini çalıştırır. Kapı burada
    GERÇEK işleriyle (yerleşik günlük yedek + backend'in kaydettiği bütün işler: çok
    okunanlar, saklama taraması …) aynı ağ tuzağı altında bir kez koşar; kayıt boş kalmalı.
    Kapıya ileride çalışma anında dış istek atan bir iş eklenirse bu test düşer."""
    kok = tmp_path / "veri"
    kayit = tmp_path / "kayit.jsonl"
    hazir = betik("hazirla", "--data-dir", str(kok), "--usb", str(tmp_path / "usb"))
    for yedek in (kok / "backups").glob("gunluk-*.kdbak"):
        yedek.unlink()

    sonuc = kos(
        [
            "-m",
            "desktop.tests.ag_tuzagi",
            "--betik",
            "gun-kapisi",
            "--data-dir",
            str(kok),
            "--parola",
            hazir["parola"],
        ],
        ortam={"KD_AG_TUZAGI_KAYIT": str(kayit)},
    )

    assert sonuc.returncode == 0, sonuc.stderr[-3000:]
    cikti = json.loads(sonuc.stdout.strip().splitlines()[-1])
    # Kapı gerçekten iş çalıştırdı (yanlış yeşile karşı): backend işleri kayıtlı ve bitti.
    assert cikti["backend_is_sayisi"] >= 2
    assert {"gunluk-yedek", "saklama-taramasi", "cok-okunanlar"} <= set(cikti["biten"]), cikti
    assert _kayitlar(kayit) == []
