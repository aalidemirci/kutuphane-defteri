"""Künye servisinin sert kuralları: ayar, sıra, önbellek, toplu iş yasağı, fail-open.

Kanıtlananlar (tasarım §8.5, §5.10-19a/b/e):

* Ayar KAPALIYKEN hiç istek çıkmaz — adaptörler "çağrılırsan düş" diye kurulur.
* Sorgu `kullanici_istegi()` bağlamı dışında (yani toplu içe aktarımdan)
  çağrılırsa reddedilir ve ağa çıkılmaz.
* Sıra: önce Bakanlık, bulunamazsa Open Library.
* Aynı ISBN ikinci kez sorulmaz (yerel önbellek).
* Uç ölürse program aksamaz (fail-open) ve `Work` satırları hiç değişmez.

Gerçek ağa ÇIKILMAZ; yanıtlar taklit edilir.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest

from apps.kutuphane.kunye import bakanlik, istemci, onbellek, openlibrary, servis
from apps.kutuphane.kunye.istemci import KunyeAgHatasi
from apps.kutuphane.kunye.marc import MarcHatasi
from apps.kutuphane.kunye.oneri import KunyeOnerisi
from apps.kutuphane.models import LibraryPolicy, MetadataLookupCache, MetadataLookupSource, Work
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

ISBN = "9789753638029"
ISBN10 = "975-363-802-2"


def oneri(**alanlar: Any) -> KunyeOnerisi:
    alanlar.setdefault("isbn", ISBN)
    alanlar.setdefault("title", "Kürk Mantolu Madonna")
    alanlar.setdefault("authors", "Sabahattin Ali")
    return KunyeOnerisi(**alanlar)


@pytest.fixture(autouse=True)
def ag_kapali(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hiçbir test gerçek ağa çıkamaz: `getir` her iki adaptörde de yasaklanır."""

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


def sahte_kaynak(monkeypatch: pytest.MonkeyPatch, modul: Any, sonuc: Any) -> list[str]:
    """Adaptörün `sorgula`sını taklit eder; çağrıldığı ISBN'leri kaydeder."""
    cagrilar: list[str] = []

    def sorgula(isbn13: str, **_kwargs: Any) -> Any:
        cagrilar.append(isbn13)
        if isinstance(sonuc, Exception):
            raise sonuc
        return sonuc

    monkeypatch.setattr(modul, "sorgula", sorgula)
    return cagrilar


def yasak_kaynak(monkeypatch: pytest.MonkeyPatch, modul: Any) -> None:
    def sorgula(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError(f"{modul.__name__}: istek çıkmamalıydı.")

    monkeypatch.setattr(modul, "sorgula", sorgula)


# ===================================================== Ayar (§8.5-1)
class TestAyar:
    def test_varsayilan_kapalidir(self) -> None:
        assert LibraryPolicy.load().metadata_lookup_enabled is False
        assert servis.ayar_acik_mi() is False

    def test_kapaliyken_hic_istek_cikmaz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        yasak_kaynak(monkeypatch, bakanlik)
        yasak_kaynak(monkeypatch, openlibrary)

        with pytest.raises(servis.KunyeKapaliHatasi), servis.kullanici_istegi():
            servis.kunye_getir(ISBN)

    def test_kapaliyken_onbellege_de_dokunulmaz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        yasak_kaynak(monkeypatch, bakanlik)

        with pytest.raises(servis.KunyeKapaliHatasi), servis.kullanici_istegi():
            servis.kunye_getir(ISBN)
        assert MetadataLookupCache.objects.count() == 0

    def test_kaynak_ayri_ayri_kapatilabilir(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """MEBNET'te 210 portu engelliyse okul o kaynağı kapatır."""
        ayar_acik.metadata_lookup_ministry = False
        ayar_acik.save()
        yasak_kaynak(monkeypatch, bakanlik)
        sahte_kaynak(monkeypatch, openlibrary, (oneri(), 1))

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert sonuc.kaynak == MetadataLookupSource.OPENLIBRARY

    def test_iki_kaynak_da_kapaliysa_istek_cikmaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        ayar_acik.metadata_lookup_ministry = False
        ayar_acik.metadata_lookup_openlibrary = False
        ayar_acik.save()
        yasak_kaynak(monkeypatch, bakanlik)
        yasak_kaynak(monkeypatch, openlibrary)

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert sonuc.bulundu is False
        # Sebep ağ DEĞİL, okulun ayarıdır: fail-open iletisi verilseydi kullanıcı
        # kendi kapattığı kaynaklar yüzünden ağı ya da BTR'yi suçlardı.
        assert sonuc.ileti == servis.ILETI_KAYNAK_YOK

    def test_kaynak_secilmemisken_bulunamadi_onbellege_yazilmaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """Hiç sorulmayan numara "kaynakta yok" diye işaretlenmemelidir (§8.5-6)."""
        ayar_acik.metadata_lookup_ministry = False
        ayar_acik.metadata_lookup_openlibrary = False
        ayar_acik.save()
        yasak_kaynak(monkeypatch, bakanlik)
        yasak_kaynak(monkeypatch, openlibrary)

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN)

        assert MetadataLookupCache.objects.count() == 0


# ===================================================== Toplu iş yasağı (§8.5-2)
class TestKullaniciIstegi:
    def test_baglam_disinda_sorgu_reddedilir(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """Toplu içe aktarma bu bağlamı hiç açmaz; yasak koda gömülüdür."""
        yasak_kaynak(monkeypatch, bakanlik)
        yasak_kaynak(monkeypatch, openlibrary)

        with pytest.raises(servis.KullaniciIstegiGerekli):
            servis.kunye_getir(ISBN)

    def test_baglam_cikista_kapanir(self, ayar_acik: LibraryPolicy) -> None:
        with servis.kullanici_istegi():
            assert servis.kullanici_istegi_mi() is True
        assert servis.kullanici_istegi_mi() is False

    def test_toplu_ice_aktarma_modulleri_kunye_paketini_kullanmaz(self) -> None:
        """§5.10-19a: içe aktarma yolundan künye modülü çağrılamaz.

        Kaynak taraması, "bağlamı açmayı unutma" gözetimini gereksiz kılar:
        içe aktarma modülleri künye paketini HİÇ içe aktarmaz.
        """
        import re
        from pathlib import Path

        kunye_importu = re.compile(
            r"^\s*(from\s+apps\.kutuphane\.kunye|from\s+apps\.kutuphane\s+import\s+.*\bkunye\b"
            r"|import\s+apps\.kutuphane\.kunye)",
            flags=re.MULTILINE,
        )
        app_dizini = Path(__file__).resolve().parents[1]
        taranan = [
            app_dizini / "import_schema.py",
            app_dizini / "excel_template.py",
            app_dizini / "selectors.py",
            app_dizini / "models.py",
            app_dizini / "apps.py",
            *(app_dizini / "services").glob("*.py"),
        ]
        for yol in taranan:
            if not yol.is_file():
                continue
            assert not kunye_importu.search(yol.read_text(encoding="utf-8")), yol.name


# ===================================================== Kaynak sırası ve sonuç
class TestSorguAkisi:
    def test_once_bakanlik_sorulur(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        bakanlik_cagri = sahte_kaynak(monkeypatch, bakanlik, (oneri(), 123))
        yasak_kaynak(monkeypatch, openlibrary)

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert bakanlik_cagri == [ISBN]
        assert sonuc.bulundu is True
        assert sonuc.kaynak == MetadataLookupSource.MINISTRY
        assert sonuc.kaynak_adi == "Bakanlık kataloğu"
        assert sonuc.kayit_sayisi == 123
        assert sonuc.kaynak_etiketi.startswith("Bakanlık kataloğu, ")

    def test_bakanlikta_bulunamazsa_open_library_sorulur(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        sahte_kaynak(monkeypatch, bakanlik, (None, 0))
        ol_cagri = sahte_kaynak(monkeypatch, openlibrary, (oneri(), 1))

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert ol_cagri == [ISBN]
        assert sonuc.kaynak == MetadataLookupSource.OPENLIBRARY

    def test_isbn10_normallestirilir(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """Dışarı yalnız NORMALİZE ISBN gider; kullanıcının yazdığı biçim değil."""
        cagrilar = sahte_kaynak(monkeypatch, bakanlik, (oneri(), 1))

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN10)

        assert cagrilar == [ISBN]

    @pytest.mark.parametrize("ham", ["", "abc", "12345"])
    def test_gecersiz_numarada_istek_cikmaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy, ham: str
    ) -> None:
        yasak_kaynak(monkeypatch, bakanlik)
        yasak_kaynak(monkeypatch, openlibrary)

        with pytest.raises(servis.GecersizIsbnHatasi), servis.kullanici_istegi():
            servis.kunye_getir(ham)


# ===================================================== Fail-open (§8.5-9)
class TestFailOpen:
    @pytest.mark.parametrize(
        "hata", [KunyeAgHatasi("uç ölü"), MarcHatasi("bozuk"), RuntimeError("beklenmedik")]
    )
    def test_uc_olurse_program_aksamaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy, hata: Exception
    ) -> None:
        sahte_kaynak(monkeypatch, bakanlik, hata)
        sahte_kaynak(monkeypatch, openlibrary, hata)

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert sonuc.bulundu is False
        assert sonuc.ileti == "İnternetten getirilemedi, elle girebilirsiniz."
        assert sonuc.oneri is None

    def test_ilk_kaynak_olurse_ikincisi_denenir(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        sahte_kaynak(monkeypatch, bakanlik, KunyeAgHatasi("uç ölü"))
        sahte_kaynak(monkeypatch, openlibrary, (oneri(), 1))

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert sonuc.kaynak == MetadataLookupSource.OPENLIBRARY

    def test_ag_hatasi_bulunamadi_diye_onbelleklenmez(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        """Ağ geri geldiğinde kullanıcı aynı numarayı yeniden sorabilmelidir."""
        sahte_kaynak(monkeypatch, bakanlik, KunyeAgHatasi("uç ölü"))
        sahte_kaynak(monkeypatch, openlibrary, KunyeAgHatasi("uç ölü"))

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN)

        assert MetadataLookupCache.objects.count() == 0

    def test_gunluge_sebep_yazilir_isbn_yazilmaz(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ayar_acik: LibraryPolicy,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """MEBNET'te sebep proxy (407), SSL denetimi ya da kapalı port olabilir.

        Yalnız istisna SINIFI yazılsaydı hepsi "KunyeAgHatasi" diye düşer ve
        BTR'nin sorusunu ayıracak iz kalmazdı. İstemcinin ürettiği iletiler
        sabit metindir, ISBN taşımaz.
        """
        sahte_kaynak(monkeypatch, bakanlik, KunyeAgHatasi("Dış uç HTTP 407 yanıtı verdi."))
        sahte_kaynak(monkeypatch, openlibrary, (None, 0))

        with caplog.at_level(logging.WARNING), servis.kullanici_istegi():
            servis.kunye_getir(ISBN)

        assert "HTTP 407" in caplog.text
        assert ISBN not in caplog.text


# ===================================================== Önbellek (§8.5-6)
class TestOnbellek:
    def test_ayni_isbn_ikinci_kez_sorulmaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        cagrilar = sahte_kaynak(monkeypatch, bakanlik, (oneri(), 7))

        with servis.kullanici_istegi():
            ilk = servis.kunye_getir(ISBN)
            ikinci = servis.kunye_getir(ISBN)

        assert cagrilar == [ISBN]
        assert ikinci.onbellekten is True
        assert ilk.onbellekten is False
        assert ikinci.oneri == ilk.oneri
        assert ikinci.kayit_sayisi == 7

    def test_bulunamadi_da_onbelleklenir(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        cagrilar = sahte_kaynak(monkeypatch, bakanlik, (None, 0))
        sahte_kaynak(monkeypatch, openlibrary, (None, 0))

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN)
            ikinci = servis.kunye_getir(ISBN)

        assert cagrilar == [ISBN]
        assert ikinci.bulundu is False
        assert ikinci.onbellekten is True

    def test_yeniden_getir_onbellegi_atlar(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        cagrilar = sahte_kaynak(monkeypatch, bakanlik, (oneri(), 1))

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN)
            sonuc = servis.kunye_getir(ISBN, force=True)

        assert cagrilar == [ISBN, ISBN]
        assert sonuc.onbellekten is False

    def test_onbellek_satiri_kisisel_veri_tasimaz(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        sahte_kaynak(monkeypatch, bakanlik, (oneri(), 1))

        with servis.kullanici_istegi():
            servis.kunye_getir(ISBN)

        satir = MetadataLookupCache.objects.get(isbn13=ISBN)
        alanlar = {alan.name for alan in MetadataLookupCache._meta.get_fields()}
        assert alanlar == {
            "id",
            "isbn13",
            "source",
            "record_count",
            "fetched_on",
            "payload",
            "updated_at",
        }
        assert set(satir.payload) <= set(KunyeOnerisi().payload())

    def test_bozuk_onbellek_satiri_programi_dusurmez(self) -> None:
        MetadataLookupCache.objects.create(
            isbn13=ISBN,
            source=MetadataLookupSource.MINISTRY,
            record_count=1,
            fetched_on="2026-09-23",
            payload={"title": "Eski sürümden kalan", "kaldirilmis_alan": 1},
        )

        kayit = onbellek.oku(ISBN)

        assert kayit is not None
        assert kayit.oneri is not None
        assert kayit.oneri.title == "Eski sürümden kalan"


# ===================================================== Onaysız yazma yok (§8.5-5)
class TestYazmaYok:
    def test_sorgu_eser_satirini_degistirmez(
        self, monkeypatch: pytest.MonkeyPatch, ayar_acik: LibraryPolicy
    ) -> None:
        eser = ortak.eser(title="Elle girilmiş ad", publisher="Elle girilmiş yayınevi", isbn=ISBN)
        oncesi = Work.objects.filter(pk=eser.pk).values().first()
        sahte_kaynak(monkeypatch, bakanlik, (oneri(title="Dış kaynaktan gelen ad"), 1))

        with servis.kullanici_istegi():
            sonuc = servis.kunye_getir(ISBN)

        assert sonuc.bulundu is True
        assert Work.objects.filter(pk=eser.pk).values().first() == oncesi
