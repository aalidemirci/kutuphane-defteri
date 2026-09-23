"""Toplu içe aktarma HİÇBİR dış istek atmaz (§8.5 kural 2, §5.10-19-a).

§8.5'in ikinci sert kuralı: "Yalnız kullanıcının başlattığı tek istek. Açılışta,
arka planda ve **toplu içe aktarımda ASLA** istek atılmaz." Gerekçe yalnız
mahremiyet değil, kaynağın açık şartıdır: Open Library "yüzlerce tekil kitap
isteği"ni açıkça yasaklar — 10.000 satırlık bir dosyanın her satırı için ISBN
sorgusu atmak tam olarak odur. Bakanlık ucunun yayımlanmış bir kullanım şartı
bile yoktur (TB20).

Kural iki katmanda kilitlenir:

1. **Kaynak taraması** — aktarım hattındaki modüller ağ kütüphanelerini import
   ETMEZ. Tarama `ast` ile yapılır: metin araması yorum satırındaki "socket"
   sözcüğüne takılır, import ağacı gerçeği söyler.
2. **Çalışma anı** — soket ve `urlopen` çağrıları patlayacak biçimde
   değiştirilir; Excel ve köprü yollarının önizlemesi ile uygulaması baştan sona
   koşar. Bir gün hatta dolaylı bir çağrı eklenirse test düşer.

Künye getirme (§8.5) bu hattın parçası DEĞİLDİR: kullanıcının tek tek başlattığı
ayrı bir iştir ve kendi ayarına bağlıdır.
"""

from __future__ import annotations

import ast
import socket
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from apps.kutuphane import ai_bridge, import_schema, isbn, keys, views_import
from apps.kutuphane.models import CatalogImportSource, Copy
from apps.kutuphane.services import import_service as ia
from apps.kutuphane.tests import sentetik_katalog

#: İçe aktarma hattının modülleri (dosya → satır → plan → yazma → uç).
ICE_AKTARMA_MODULLERI = (ia, ai_bridge, import_schema, isbn, keys, views_import)

#: Hiçbiri aktarım hattında bulunamaz (ağ ve süreç açan kütüphaneler).
YASAKLI_MODULLER = frozenset(
    {
        "asyncio",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "subprocess",
        "telnetlib",
        "urllib",
        "webbrowser",
        "xmlrpc",
    }
)

#: Künye getirme (§8.5) ayrı bir iştir: toplu aktarım onu ÇAĞIRMAZ.
YASAKLI_ANAHTAR_SOZCUKLER = ("kunye", "metadata_lookup", "sru", "openlibrary")


def _import_edilen_modul_adlari(kaynak: str) -> set[str]:
    """Kaynaktaki `import x` ve `from x import …` adlarının kök parçaları."""
    adlar: set[str] = set()
    for dugum in ast.walk(ast.parse(kaynak)):
        if isinstance(dugum, ast.Import):
            adlar.update(ad.name for ad in dugum.names)
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            adlar.add(dugum.module)
    return adlar


@pytest.mark.parametrize("modul", ICE_AKTARMA_MODULLERI, ids=lambda m: m.__name__)
def test_aktarim_hatti_ag_kutuphanesi_import_etmez(modul: Any) -> None:
    kaynak = Path(modul.__file__).read_text(encoding="utf-8")

    for ad in _import_edilen_modul_adlari(kaynak):
        assert ad.split(".")[0] not in YASAKLI_MODULLER, f"{modul.__name__} → {ad}"


@pytest.mark.parametrize("modul", ICE_AKTARMA_MODULLERI, ids=lambda m: m.__name__)
def test_aktarim_hatti_kunye_getirmeyi_cagirmaz(modul: Any) -> None:
    """Toplu aktarım künye getirme hattını import etmez (§8.5 kural 2)."""
    kaynak = Path(modul.__file__).read_text(encoding="utf-8")

    for ad in _import_edilen_modul_adlari(kaynak):
        assert not any(
            sozcuk in ad.lower() for sozcuk in YASAKLI_ANAHTAR_SOZCUKLER
        ), f"{modul.__name__} → {ad}"


@pytest.fixture
def ag_kapali(monkeypatch: pytest.MonkeyPatch) -> None:
    """Her dış bağlantı denemesini testi düşüren bir hataya çevirir."""

    def _patla(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("İçe aktarma sırasında dış bağlantı denendi.")

    monkeypatch.setattr(socket.socket, "connect", _patla)
    monkeypatch.setattr(socket.socket, "connect_ex", _patla)
    monkeypatch.setattr(socket, "create_connection", _patla)
    monkeypatch.setattr(urllib.request, "urlopen", _patla)


@pytest.mark.django_db
class TestCalismaAninda:
    """Aktarımın bütün yolları ağ kapalıyken baştan sona koşar."""

    SATIRLAR = [
        {
            "title": "Kürk Mantolu Madonna",
            "authors": "Sabahattin Ali",
            "isbn": sentetik_katalog.sentetik_isbn(1),
            "resource_type": "Kitap",
            "copies": 2,
            "shelf_location": "Edebiyat",
        }
    ]

    def test_excel_onizleme_ve_uygulama_ag_kapaliyken_koşar(self, ag_kapali: None) -> None:
        dosya = sentetik_katalog.katalog_dosyasi(self.SATIRLAR)
        parsed, ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        ia.preview_import(parsed, payload_sha256=ozet, new_sections=["Edebiyat"])
        rapor = ia.apply_import(parsed, payload_sha256=ozet, new_sections=["Edebiyat"])

        assert rapor.stats["copies_created"] == 2
        assert Copy.objects.count() == 2

    def test_kopru_yolu_ag_kapaliyken_koşar(self, ag_kapali: None) -> None:
        parsed = ia.rows_from_payload(
            {
                "schema_version": ai_bridge.SCHEMA_VERSION,
                "items": [{"title": "Huzur", "authors": "Ahmet Hamdi Tanpınar", "isbn": "x"}],
            }
        )

        rapor = ia.apply_import(parsed, payload_sha256="", source=CatalogImportSource.AI_JSON)

        assert rapor.stats["copies_created"] == 1

    def test_bin_satirlik_dosya_hic_istek_atmaz(self, ag_kapali: None) -> None:
        """Her satırı ISBN'li 1.000 satır: "satır başına bir sorgu" kaçağı burada yakalanır."""
        dosya = sentetik_katalog.katalog_dosyasi(sentetik_katalog.sentetik_satirlar(1000))
        parsed, ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        rapor = ia.apply_import(
            parsed, payload_sha256=ozet, new_sections=list(sentetik_katalog.BOLUMLER)
        )

        assert rapor.stats["copies_created"] == 1000
