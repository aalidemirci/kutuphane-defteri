"""Künye uçları: sorgu, ayar kapısı, öneri gövdesi ve "yazma yok" kanıtı.

Uçlar öneri üretir; `Work` satırına DOKUNMAZ (§8.5-5). Onay kullanıcının kendi
`library/works/` isteğidir. Gerçek ağa çıkılmaz.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane.kunye import bakanlik, istemci, offline, openlibrary, servis
from apps.kutuphane.kunye.oneri import UYARI_CEVIRMEN, KunyeOnerisi
from apps.kutuphane.models import LibraryPolicy, MetadataLookupSource, Work
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

SORGU = "/api/v1/library/metadata/lookup/"
DISA_AKTAR = "/api/v1/library/metadata/offline-export/"
GERI_AL = "/api/v1/library/metadata/offline-preview/"
POLITIKA = "/api/v1/library/policy/"

ISBN = "9789753638029"


@pytest.fixture
def istemci_api() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def ag_kapali(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def patla(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Test gerçek ağa çıkmaya çalıştı.")

    monkeypatch.setattr(bakanlik, "getir", patla)
    monkeypatch.setattr(openlibrary, "getir", patla)
    monkeypatch.setattr(istemci, "_uyu", lambda _sure: None)
    istemci._sifirla_testler_icin()
    yield
    istemci._sifirla_testler_icin()


@pytest.fixture
def ayar_acik() -> LibraryPolicy:
    policy, _ = LibraryPolicy.objects.get_or_create(pk=LibraryPolicy.SINGLETON_PK)
    kayit: LibraryPolicy = policy
    kayit.metadata_lookup_enabled = True
    kayit.save()
    return kayit


def sahte_bakanlik(monkeypatch: pytest.MonkeyPatch, **alanlar: Any) -> list[str]:
    cagrilar: list[str] = []
    oneri = KunyeOnerisi(
        isbn=ISBN,
        title=alanlar.pop("title", "Kürk Mantolu Madonna"),
        authors=alanlar.pop("authors", "Sabahattin Ali"),
        publisher=alanlar.pop("publisher", "Yapı Kredi Yayınları"),
        publish_year=alanlar.pop("publish_year", 2015),
        subjects=alanlar.pop("subjects", "Türk edebiyatı, roman"),
        classification_code=alanlar.pop("classification_code", "894.353"),
        pages=alanlar.pop("pages", 160),
        place=alanlar.pop("place", "İstanbul"),
        uyarilar=(UYARI_CEVIRMEN,),
    )
    kayit_sayisi = int(alanlar.pop("kayit_sayisi", 123))

    def sorgula(isbn13: str, **_kwargs: Any) -> tuple[KunyeOnerisi, int]:
        cagrilar.append(isbn13)
        return oneri, kayit_sayisi

    monkeypatch.setattr(bakanlik, "sorgula", sorgula)
    return cagrilar


# ===================================================== Ayar kapısı (§8.5-1)
class TestAyarKapisi:
    def test_kapaliyken_409_kunye_kapali(self, istemci_api: APIClient) -> None:
        yanit = istemci_api.post(SORGU, {"isbn": ISBN}, format="json")

        assert yanit.status_code == 409
        govde = yanit.json()
        assert govde["code"] == "kunye_kapali"
        assert "Ayarlar" in govde["message"]

    def test_ayar_politika_ucundan_acilir(self, istemci_api: APIClient) -> None:
        yanit = istemci_api.get(POLITIKA)
        assert yanit.json()["metadata_lookup_enabled"] is False

        guncel = istemci_api.put(POLITIKA, {"metadata_lookup_enabled": True}, format="json")

        assert guncel.status_code == 200
        assert guncel.json()["metadata_lookup_enabled"] is True
        assert LibraryPolicy.load().metadata_lookup_enabled is True


# ===================================================== Sorgu ucu
class TestSorguUcu:
    def test_oneri_govdesi_kaynak_ve_rozet_tasir(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        sahte_bakanlik(monkeypatch)

        yanit = istemci_api.post(SORGU, {"isbn": ISBN}, format="json")

        assert yanit.status_code == 200, yanit.json()
        govde = yanit.json()
        assert govde["bulundu"] is True
        assert govde["isbn13"] == ISBN
        assert govde["kaynak"] == MetadataLookupSource.MINISTRY
        assert govde["kaynak_adi"] == "Bakanlık kataloğu"
        assert govde["kaynak_etiketi"].startswith("Bakanlık kataloğu, ")
        assert govde["rozet"] == "Dış kaynaktan alındı, doğrulayın"
        assert govde["kayit_sayisi"] == 123
        assert UYARI_CEVIRMEN in govde["uyarilar"]
        assert govde["ek_bilgi"] == {"pages": 160, "place": "İstanbul"}

    def test_alanlar_listesi_cevirmen_tasimaz(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        sahte_bakanlik(monkeypatch)

        govde = istemci_api.post(SORGU, {"isbn": ISBN}, format="json").json()

        adlar = [satir["alan"] for satir in govde["alanlar"]]
        assert "translator" not in adlar
        assert adlar[:3] == ["title", "authors", "publisher"]

    def test_dolu_alan_ekranda_karsilastirilir(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """Dolu alan sessizce üzerine yazılmaz: fark kullanıcıya gösterilir."""
        eser = ortak.eser(title="Elle girilmiş ad", isbn=ISBN)
        sahte_bakanlik(monkeypatch, title="Dış kaynaktan gelen ad")

        govde = istemci_api.post(SORGU, {"isbn": ISBN, "work": eser.pk}, format="json").json()

        ad_satiri = next(satir for satir in govde["alanlar"] if satir["alan"] == "title")
        assert ad_satiri["mevcut_deger"] == "Elle girilmiş ad"
        assert ad_satiri["deger"] == "Dış kaynaktan gelen ad"
        assert ad_satiri["dolu"] is True
        assert ad_satiri["farkli"] is True

    def test_sorgu_eseri_degistirmez(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        eser = ortak.eser(title="Elle girilmiş ad", isbn=ISBN)
        oncesi = Work.objects.filter(pk=eser.pk).values().first()
        sahte_bakanlik(monkeypatch, title="Dış kaynaktan gelen ad")

        istemci_api.post(SORGU, {"isbn": ISBN, "work": eser.pk}, format="json")

        assert Work.objects.filter(pk=eser.pk).values().first() == oncesi

    def test_gecersiz_isbn_400_doner_ve_istek_cikmaz(
        self, istemci_api: APIClient, ayar_acik: LibraryPolicy
    ) -> None:
        yanit = istemci_api.post(SORGU, {"isbn": "abc"}, format="json")

        assert yanit.status_code == 400
        assert "isbn" in yanit.json()["fields"]

    def test_bilinmeyen_eser_400_doner(
        self, istemci_api: APIClient, ayar_acik: LibraryPolicy
    ) -> None:
        yanit = istemci_api.post(SORGU, {"isbn": ISBN, "work": 99999}, format="json")

        assert yanit.status_code == 400
        assert "work" in yanit.json()["fields"]

    def test_bulunamadiginda_fail_open_iletisi_doner(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        monkeypatch.setattr(bakanlik, "sorgula", lambda *a, **k: (None, 0))
        monkeypatch.setattr(openlibrary, "sorgula", lambda *a, **k: (None, 0))

        govde = istemci_api.post(SORGU, {"isbn": ISBN}, format="json").json()

        assert govde["bulundu"] is False
        assert govde["ileti"] == servis.ILETI_BULUNAMADI
        assert govde["alanlar"] == []
        assert govde["rozet"] == ""

    def test_ikinci_sorgu_onbellekten_gelir(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        cagrilar = sahte_bakanlik(monkeypatch)

        istemci_api.post(SORGU, {"isbn": ISBN}, format="json")
        ikinci = istemci_api.post(SORGU, {"isbn": ISBN}, format="json").json()

        assert cagrilar == [ISBN]
        assert ikinci["onbellekten"] is True

    def test_get_desteklenmez(self, istemci_api: APIClient, ayar_acik: LibraryPolicy) -> None:
        """Sorgu kullanıcının EYLEMİDİR: adres çubuğundan tetiklenmez."""
        assert istemci_api.get(SORGU).status_code == 405


# ===================================================== Çevrimdışı uçlar
class TestCevrimdisiUclar:
    def test_disa_aktarim_xlsx_doner_ve_aga_cikmaz(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ayar KAPALIYKEN de çalışır: çevrimdışı yol tam da ağsız masa içindir."""
        ortak.eser(title="Künyesi eksik eser", isbn=ISBN)

        yanit = istemci_api.get(DISA_AKTAR)

        assert yanit.status_code == 200
        assert yanit["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml"
        )
        # Django dosya adını RFC 5987 ile kodlar ("ISBN-K%C3%BCnye-Listesi").
        assert "ISBN-K%C3%BCnye-Listesi" in yanit["Content-Disposition"]

    def test_geri_alma_onizleme_dondurur_ve_yazmaz(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from io import BytesIO

        from apps.kutuphane.kunye import offline

        eser = ortak.eser(title="Künyesi eksik eser", isbn=ISBN)
        oncesi = Work.objects.filter(pk=eser.pk).values().first()
        dosya = BytesIO(offline.build_export())
        dosya.name = "kunye.xlsx"

        yanit = istemci_api.post(GERI_AL, {"file": dosya}, format="multipart")

        assert yanit.status_code == 200, yanit.json()
        govde = yanit.json()
        assert govde["rozet"] == "Dış kaynaktan alındı, doğrulayın"
        assert govde["kaynak_etiketi"].startswith("Çevrimdışı künye dosyası, ")
        assert govde["sayilar"]["eslesti"] == 1
        assert govde["satirlar"][0]["work"] == eser.pk
        assert Work.objects.filter(pk=eser.pk).values().first() == oncesi

    def test_buyuk_dosya_uctan_400_doner(
        self, istemci_api: APIClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tavan dosya BELLEĞE ALINMADAN uygulanır; kullanıcı Türkçe ileti görür.

        Django'nun `DATA_UPLOAD_MAX_MEMORY_SIZE` ayarı çok parçalı istekteki
        dosya parçasını sınırlamaz, gövdenin dosya dışı kısmını sınırlar.
        """
        from io import BytesIO

        monkeypatch.setattr(offline, "MAX_DOSYA_BAYT", 1024)
        dosya = BytesIO(b"P" * 2048)
        dosya.name = "kunye.xlsx"

        yanit = istemci_api.post(GERI_AL, {"file": dosya}, format="multipart")

        assert yanit.status_code == 400
        assert "çok büyük" in yanit.json()["fields"]["file"][0]

    def test_bos_dosya_400_doner(self, istemci_api: APIClient) -> None:
        from io import BytesIO

        dosya = BytesIO(b"bos degil ama kunye dosyasi degil")
        dosya.name = "yanlis.csv"

        yanit = istemci_api.post(GERI_AL, {"file": dosya}, format="multipart")

        assert yanit.status_code == 400
        assert "file" in yanit.json()["fields"]
