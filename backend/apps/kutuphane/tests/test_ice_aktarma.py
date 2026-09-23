"""Toplu katalog aktarımının çekirdeği (tasarım §8.1, D5; F3 kod kapısı).

Kapının altı maddesi burada sabitlenir: önizleme ile uygulama aynı sonucu verir ·
aynı dosyanın ikinci uygulaması engellenir · `shelf_location` kaybolmaz · satır
başına 50 nüsha sınırı · ders kitabı → danışma varsayılanı · bölüm eşleştirme.

Bütün veriler uydurmadır (CLAUDE.md §2-12): eser adları kamu malı klasiklerden,
ISBN'ler sağlaması geçerli ama uydurma numaralardan gelir.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from apps.kutuphane import selectors
from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    CatalogImportRun,
    CatalogImportSource,
    CatalogImportStatus,
    ClassificationSource,
    Copy,
    ResourceType,
    Section,
    Work,
)
from apps.kutuphane.services import import_service as ia
from apps.kutuphane.tests import ortak, sentetik_katalog

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _ayristir(satirlar: list[dict[str, Any]]) -> tuple[ia.ParsedFile, str]:
    dosya = sentetik_katalog.katalog_dosyasi(satirlar)
    return ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)


def _onizle(satirlar: list[dict[str, Any]], **secenekler: Any) -> ia.CatalogImportReport:
    parsed, ozet = _ayristir(satirlar)
    return ia.preview_import(parsed, payload_sha256=ozet, **secenekler)


def _uygula(satirlar: list[dict[str, Any]], **secenekler: Any) -> ia.CatalogImportReport:
    parsed, ozet = _ayristir(satirlar)
    return ia.apply_import(parsed, payload_sha256=ozet, **secenekler)


def _satir(rapor: ia.CatalogImportReport, no: int) -> ia.ImportRowReport:
    return next(satir for satir in rapor.rows if satir.row == no)


KITAP = {
    "title": "Kürk Mantolu Madonna",
    "authors": "Sabahattin Ali",
    "publisher": "Örnek Yayınevi",
    "publish_year": 2020,
    "subjects": "Türk edebiyatı, roman",
    "classification_code": "894.353",
    "language": "Türkçe",
    "resource_type": "Kitap",
    "copies": 2,
}


# ---------------------------------------------------------------------------
# 1. Önizleme = uygulama
# ---------------------------------------------------------------------------
class TestOnizlemeUygulamaParitesi:
    """Önizleme uygulamanın birebir provasıdır: aynı kod koşar, sonuç geri sarılır."""

    def test_onizleme_hicbir_sey_yazmaz(self) -> None:
        ortak.bolum(name="Edebiyat")

        rapor = _onizle([{**KITAP, "shelf_location": "Edebiyat"}])

        assert rapor.dry_run is True
        assert rapor.stats["new_works"] == 1
        assert rapor.stats["copies_created"] == 2
        assert Work.objects.count() == 0
        assert Copy.objects.count() == 0

    def test_onizleme_ile_uygulama_ayni_sayilari_verir(self) -> None:
        ortak.bolum(name="Edebiyat")
        satirlar = [
            {**KITAP, "shelf_location": "Edebiyat"},
            {**KITAP, "title": "Çalıkuşu", "authors": "Reşat Nuri Güntekin", "copies": 1},
        ]

        onizleme = _onizle(satirlar)
        uygulama = _uygula(satirlar)

        assert onizleme.stats == uygulama.stats
        assert [(satir.row, satir.bucket) for satir in onizleme.rows] == [
            (satir.row, satir.bucket) for satir in uygulama.rows
        ]
        assert Work.objects.count() == 2
        assert Copy.objects.count() == 3

    def test_onizleme_izi_kaliciydir_ve_yazmayi_geri_sarar(self) -> None:
        """Geri sarma yazmayı siler; koşu izi (geçmiş) geri sarmanın DIŞINDADIR."""
        rapor = _onizle([KITAP])

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        assert kayit.status == CatalogImportStatus.DRY_RUN
        assert kayit.stats["copies_created"] == 2
        assert kayit.acquisition_id is None
        assert Work.objects.count() == 0

    def test_onizlemede_acilacak_eserin_kimligi_bos_kalir(self) -> None:
        """Geri sarılan işlemde üretilen kimlik anlamsızdır; eşleşen eserinki geçerlidir."""
        mevcut = ortak.eser(title="Çalıkuşu", authors="Reşat Nuri Güntekin")

        rapor = _onizle(
            [
                KITAP,
                {"title": "Çalıkuşu", "authors": "Reşat Nuri Güntekin", "copies": 1},
            ]
        )

        assert _satir(rapor, 2).work is None
        assert _satir(rapor, 3).work == mevcut.pk


# ---------------------------------------------------------------------------
# 2. Fikirdeşlik: aynı dosya ikinci kez UYGULANAMAZ (uyarı değil, engel)
# ---------------------------------------------------------------------------
class TestFikirdeslik:
    def test_ayni_dosyanin_ikinci_uygulamasi_engellenir(self) -> None:
        satirlar = [KITAP]
        _uygula(satirlar)

        with pytest.raises(ValidationError) as hata:
            _uygula(satirlar)

        assert "ikinci kez" in str(hata.value)
        assert Copy.objects.count() == 2  # ikinci parti yazılmadı

    def test_onizleme_engellenmez_ama_uyarir(self) -> None:
        """İptal/yeniden deneme yolu açık kalır: önizleme koşar ve durumu söyler."""
        satirlar = [KITAP]
        _uygula(satirlar)

        rapor = _onizle(satirlar)

        assert rapor.already_applied is True
        assert rapor.applied_at != ""

    def test_ayni_icerigin_bicim_farkli_kopyasi_da_engellenir(self) -> None:
        """Özet ham BAYTTAN değil İÇERİKTEN alınır (kaydetme, boşluk, dosya adı farkı)."""
        _uygula([KITAP])

        with pytest.raises(ValidationError) as hata:
            _uygula([{**KITAP, "title": f"{KITAP['title']} "}])

        assert "ikinci kez" in str(hata.value)
        assert Copy.objects.count() == 2  # ikinci parti yazılmadı

    def test_farkli_dosya_engellenmez(self) -> None:
        _uygula([KITAP])

        rapor = _uygula([{**KITAP, "title": "Huzur", "authors": "Ahmet Hamdi Tanpınar"}])

        assert rapor.stats["new_works"] == 1

    def test_iptal_edilen_onizleme_yeniden_denenebilir(self) -> None:
        onizleme = _onizle([KITAP])
        kayit = CatalogImportRun.objects.get(pk=onizleme.run_id)

        ia.discard_run(kayit)
        kayit.refresh_from_db()
        rapor = _uygula([KITAP])

        assert kayit.status == CatalogImportStatus.DISCARDED
        assert rapor.stats["copies_created"] == 2

    def test_uygulanmis_kosu_iptal_edilemez(self) -> None:
        rapor = _uygula([KITAP])
        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)

        with pytest.raises(ValidationError):
            ia.discard_run(kayit)


# ---------------------------------------------------------------------------
# 3. Eşleşme kovaları: yeni / mevcut / şüpheli
# ---------------------------------------------------------------------------
class TestKovalar:
    def test_yeni_eser(self) -> None:
        rapor = _onizle([KITAP])

        assert _satir(rapor, 2).bucket == ia.BUCKET_NEW

    def test_isbn13_ile_mevcut_esere_nusha_eklenir(self) -> None:
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", isbn="975-363-000-8")
        isbn13 = mevcut.isbn13
        assert isbn13

        rapor = _uygula([{**KITAP, "isbn": isbn13, "copies": 1}])

        assert _satir(rapor, 2).bucket == ia.BUCKET_EXISTING
        assert Work.objects.count() == 1
        assert mevcut.copies.count() == 1

    def test_isbn_tutup_ad_tutmayan_satir_supheli_olur(self) -> None:
        """Tek haneli bir ISBN hatası nüshaları başka kitabın altına eklemesin."""
        mevcut = ortak.eser(title="Başka Bir Kitap", isbn=sentetik_katalog.sentetik_isbn(7))

        rapor = _onizle([{**KITAP, "isbn": sentetik_katalog.sentetik_isbn(7)}])

        satir = _satir(rapor, 2)
        assert satir.bucket == ia.BUCKET_SUSPECT
        assert satir.needs_decision is True
        assert satir.candidates[0]["work"] == mevcut.pk

    def test_ad_ve_yazar_ile_mevcut_esere_baglanir(self) -> None:
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")

        rapor = _uygula([{**KITAP, "copies": 1}])

        assert _satir(rapor, 2).work == mevcut.pk
        assert Work.objects.count() == 1

    def test_turkce_katlama_ile_eslesir(self) -> None:
        """ "KÜRK MANTOLU MADONNA" ile "Kürk Mantolu Madonna" aynı eserdir (T7)."""
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")

        rapor = _onizle([{**KITAP, "title": "KÜRK MANTOLU MADONNA", "authors": "SABAHATTİN ALİ"}])

        assert _satir(rapor, 2).work == mevcut.pk

    def test_ad_tutup_yazar_tutmayan_satir_supheli_olur(self) -> None:
        ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        rapor = _onizle([KITAP])

        assert _satir(rapor, 2).bucket == ia.BUCKET_SUSPECT
        assert rapor.pending_decisions == [2]

    def test_ayni_kunyeli_iki_satir_tek_esere_baglanir(self) -> None:
        """Her nüshası ayrı satıra yazılan eser, içe aktarımda tek eser olur (§8.1)."""
        rapor = _uygula(
            [
                {**KITAP, "copies": 1, "old_register_no": "1452"},
                {**KITAP, "copies": 1, "old_register_no": "1453"},
            ]
        )

        assert Work.objects.count() == 1
        assert Copy.objects.count() == 2
        assert _satir(rapor, 2).bucket == ia.BUCKET_NEW
        assert _satir(rapor, 3).bucket == ia.BUCKET_EXISTING
        assert sorted(Copy.objects.values_list("old_register_no", flat=True)) == ["1452", "1453"]

    def test_mevcut_eserin_kunyesi_uzerine_yazilmaz(self) -> None:
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali", publisher="")

        _uygula([{**KITAP, "copies": 1}])
        mevcut.refresh_from_db()

        assert mevcut.publisher == ""


# ---------------------------------------------------------------------------
# 4. Şüpheli satırın kararı
# ---------------------------------------------------------------------------
class TestKararlar:
    def test_karar_verilmeden_uygulama_reddedilir(self) -> None:
        ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        with pytest.raises(ValidationError) as hata:
            _uygula([KITAP])

        assert "karar bekliyor" in str(hata.value)
        assert Copy.objects.count() == 0

    def test_yeni_eser_karari(self) -> None:
        ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        rapor = _uygula([KITAP], decisions={2: {"action": "new"}})

        assert Work.objects.count() == 2
        assert _satir(rapor, 2).bucket == ia.BUCKET_NEW

    def test_su_esere_nusha_ekle_karari(self) -> None:
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        rapor = _uygula([KITAP], decisions={"2": {"action": "attach", "work": mevcut.pk}})

        assert Work.objects.count() == 1
        assert mevcut.copies.count() == 2
        assert _satir(rapor, 2).bucket == ia.BUCKET_EXISTING

    def test_dosyadaki_satira_baglama_karari(self) -> None:
        """Aynı eserin iki yazımı: ikinci satır, birinci satırın açtığı esere bağlanır."""
        rapor = _uygula(
            [
                {**KITAP, "copies": 1},
                {**KITAP, "authors": "S. Ali", "copies": 1},
            ],
            decisions={3: {"action": "attach", "row": 2}},
        )

        assert Work.objects.count() == 1
        assert Copy.objects.count() == 2
        assert _satir(rapor, 3).work_row == 2

    def test_bulunmayan_eser_karari_reddedilir(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _uygula([KITAP], decisions={2: {"action": "attach", "work": 9999}})

        assert "bulunamadı" in str(hata.value)

    def test_taninmayan_karar_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            _uygula([KITAP], decisions={2: {"action": "sil"}})

    def test_sayisal_olmayan_satir_numarasi_reddedilir(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _uygula([KITAP], decisions={"ikinci": {"action": "new"}})

        assert "satır numarası" in str(hata.value)

    def test_karar_nesnesi_degilse_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            _uygula([KITAP], decisions={2: "yeni"})

    def test_hedefsiz_nusha_ekle_karari_reddedilir(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _uygula([KITAP], decisions={2: {"action": "attach"}})

        assert "seçilmemiş" in str(hata.value)

    def test_sayisal_olmayan_eser_kimligi_reddedilir(self) -> None:
        with pytest.raises(ValidationError):
            _uygula([KITAP], decisions={2: {"action": "attach", "work": "beş"}})

    def test_acilamamis_satira_baglanan_satir_rapora_duser(self) -> None:
        """2. satır nüsha kuralına takılırsa ona bağlanan 3. satır da yazılamaz."""
        rapor = _uygula(
            [
                {**KITAP, "title": "Bilim Dergisi", "resource_type": "Süreli yayın", "copies": 1},
                {**KITAP, "title": "Bilim Dergisi", "authors": "Başka", "copies": 1},
            ],
            decisions={3: {"action": "attach", "row": 2}},
        )

        assert rapor.stats["error_rows"] == 2
        assert "bağlanamadı" in " ".join(_satir(rapor, 3).issues)
        assert Copy.objects.count() == 0


# ---------------------------------------------------------------------------
# 5. Bölüm eşleştirme ve `shelf_location` (D5)
# ---------------------------------------------------------------------------
class TestBolumEslestirme:
    def test_bolum_nushaya_ve_esere_yazilir(self) -> None:
        bolum = ortak.bolum(name="Edebiyat")

        _uygula([{**KITAP, "shelf_location": "Edebiyat", "copies": 1}])

        nusha = Copy.objects.get()
        assert nusha.section_id == bolum.pk
        assert nusha.work.section_id == bolum.pk

    def test_kontrollu_liste_turkce_katlamayla_eslesir(self) -> None:
        bolum = ortak.bolum(name="Edebiyat")

        _uygula([{**KITAP, "shelf_location": "EDEBİYAT ", "copies": 1}])

        assert Copy.objects.get().section_id == bolum.pk

    def test_eslesmeyen_bolum_onizlemede_sorulur(self) -> None:
        rapor = _onizle([{**KITAP, "shelf_location": "Gezi Kitapları", "copies": 1}])

        assert rapor.unknown_sections == [
            {"value": "Gezi Kitapları", "rows": [2], "count": 1},
        ]

    def test_eslesmeyen_bolumle_uygulama_reddedilir(self) -> None:
        """D5: değer sessizce düşürülmez; karşılığı verilmeden yazılmaz."""
        with pytest.raises(ValidationError) as hata:
            _uygula([{**KITAP, "shelf_location": "Gezi Kitapları"}])

        assert "Gezi Kitapları" in str(hata.value)
        assert Copy.objects.count() == 0

    def test_var_olan_bolume_eslenir(self) -> None:
        bolum = ortak.bolum(name="Edebiyat")

        _uygula(
            [{**KITAP, "shelf_location": "Gezi Kitapları", "copies": 1}],
            section_map={"Gezi Kitapları": bolum.pk},
        )

        assert Copy.objects.get().section_id == bolum.pk

    def test_yeni_bolum_acilir(self) -> None:
        rapor = _uygula(
            [{**KITAP, "shelf_location": "Gezi Kitapları", "copies": 1}],
            new_sections=["Gezi Kitapları"],
        )

        bolum = Section.objects.get(name="Gezi Kitapları")
        assert Copy.objects.get().section_id == bolum.pk
        assert rapor.stats["sections_created"] == 1

    def test_sayisal_olmayan_bolum_kimligi_sozlesmeli_400_olur(self) -> None:
        """Sarmalanmayan `int()` 500 üretirdi; kullanıcı "sunucu hatası" görürdü."""
        with pytest.raises(ValidationError) as hata:
            _onizle([{**KITAP, "shelf_location": "Gezi"}], section_map={"Gezi": "abc"})

        assert "sayısal" in str(hata.value)

    def test_bulunmayan_bolume_esleme_reddedilir(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _uygula(
                [{**KITAP, "shelf_location": "Gezi Kitapları"}],
                section_map={"Gezi Kitapları": 9999},
            )

        assert "bulunamadı" in str(hata.value)

    def test_bos_bolum_hucresi_sorun_degildir(self) -> None:
        rapor = _uygula([{**KITAP, "copies": 1}])

        assert rapor.unknown_sections == []
        assert Copy.objects.get().section_id is None


# ---------------------------------------------------------------------------
# 6. Satır kuralları: 50 nüsha, eski kayıt no, ders kitabı, süreli yayın
# ---------------------------------------------------------------------------
class TestSatirKurallari:
    def test_elli_nusha_acilir(self) -> None:
        rapor = _uygula([{**KITAP, "copies": 50}])

        assert rapor.stats["copies_created"] == 50
        assert Copy.objects.count() == 50

    def test_elli_birinci_nusha_satiri_reddedilir(self) -> None:
        rapor = _uygula([{**KITAP, "copies": 51}])

        satir = _satir(rapor, 2)
        assert satir.bucket == ia.BUCKET_SKIPPED
        assert "1 ile 50 arasında" in satir.issues[0]
        assert Copy.objects.count() == 0

    def test_eski_kayit_no_tek_nushaya_aittir(self) -> None:
        rapor = _uygula([{**KITAP, "copies": 2, "old_register_no": "1452"}])

        assert _satir(rapor, 2).bucket == ia.BUCKET_SKIPPED
        assert "tek nüshaya aittir" in _satir(rapor, 2).issues[0]

    def test_ders_kitabi_danisma_varsayilanini_acar(self) -> None:
        """Md. 14/1-a, 16/1-a: tür ya da konu "ders kitabı" ise danışma açık gelir."""
        rapor = _uygula(
            [
                {**KITAP, "resource_type": "Ders kitabı", "copies": 1},
                {**KITAP, "title": "Fizik 9", "subjects": "Ders kitabı", "copies": 1},
            ]
        )

        assert all(nusha.is_reference for nusha in Copy.objects.all())
        assert _satir(rapor, 2).reference_by_textbook is True
        assert _satir(rapor, 3).reference_by_textbook is True
        assert rapor.stats["reference_defaults"] == 2

    def test_ders_kitabinda_acik_hayir_yazilabilir(self) -> None:
        rapor = _uygula(
            [{**KITAP, "resource_type": "Ders kitabı", "copies": 1, "is_reference": "Hayır"}]
        )

        assert Copy.objects.get().is_reference is False
        assert _satir(rapor, 2).reference_by_textbook is False

    def test_ders_kitabi_kaynak_turu_kitaptir(self) -> None:
        _uygula([{**KITAP, "resource_type": "Ders kitabı", "copies": 1}])

        assert Work.objects.get().resource_type == ResourceType.BOOK

    def test_excel_dogru_yanlis_hucresi_evet_hayir_sayilir(self) -> None:
        """openpyxl DOĞRU/YANLIŞ hücrelerini `bool` verir; sözlük onları da tanır."""
        rapor = _uygula([{**KITAP, "copies": 1, "is_reference": True}])

        assert Copy.objects.get().is_reference is True
        assert _satir(rapor, 2).is_reference is True

    def test_taninmayan_danisma_degeri_satiri_dusurur(self) -> None:
        rapor = _onizle([{**KITAP, "is_reference": "belki"}])

        satir = _satir(rapor, 2)
        assert satir.bucket == ia.BUCKET_SKIPPED
        assert "Danışma Kaynağı" in satir.issues[0]

    def test_taninmayan_ciltli_degeri_satiri_dusurur(self) -> None:
        rapor = _onizle([{**KITAP, "is_bound_periodical": "kısmen"}])

        assert "Ciltli Süreli Yayın" in _satir(rapor, 2).issues[0]

    def test_tarih_bicimli_yil_hucresi_okunur(self) -> None:
        """Excel "2020" yazısını tarihe çevirmiş olabilir; yıl yine de okunur."""
        from datetime import date

        dosya = sentetik_katalog.baslikli_dosya(
            ["Eser Adı", "Yayın Yılı"], [["Huzur", date(2020, 5, 1)]]
        )
        parsed, ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)
        ia.apply_import(parsed, payload_sha256=ozet)

        assert Work.objects.get().publish_year == 2020

    def test_ciltsiz_sureli_yayin_satiri_partiyi_dusurmez(self) -> None:
        """TMY Md. 15/4: ciltsiz süreli yayın kayda girmez — satır düşer, parti sürer."""
        rapor = _uygula(
            [
                {**KITAP, "title": "Bilim Dergisi", "resource_type": "Süreli yayın", "copies": 1},
                {**KITAP, "copies": 1},
            ]
        )

        assert "ciltletildiğinde" in " ".join(_satir(rapor, 2).issues)
        assert rapor.stats["error_rows"] == 1
        assert rapor.stats["copies_created"] == 1
        assert Copy.objects.count() == 1

    def test_ciltli_sureli_yayin_kayda_girer(self) -> None:
        _uygula(
            [
                {
                    **KITAP,
                    "title": "Bilim Dergisi",
                    "resource_type": "Süreli yayın",
                    "is_bound_periodical": "Evet",
                    "copies": 1,
                }
            ]
        )

        assert Copy.objects.get().is_bound_periodical is True

    def test_eser_adi_bos_satir_atlanir(self) -> None:
        rapor = _uygula([{**KITAP, "title": "", "copies": 1}, {**KITAP, "copies": 1}])

        assert _satir(rapor, 2).bucket == ia.BUCKET_SKIPPED
        assert rapor.stats["skipped_rows"] == 1
        assert Work.objects.count() == 1

    def test_taninmayan_kaynak_turu_satiri_dusurur(self) -> None:
        """Sessizce "Kitap" saymak ödünç verilebilirliği değiştirirdi."""
        rapor = _onizle([{**KITAP, "resource_type": "Kaset"}])

        assert _satir(rapor, 2).bucket == ia.BUCKET_SKIPPED
        assert "Kaset" in _satir(rapor, 2).issues[0]

    def test_bozuk_isbn_uyaridir_satiri_dusurmez(self) -> None:
        rapor = _uygula([{**KITAP, "isbn": "9786059990001", "copies": 1}])

        satir = _satir(rapor, 2)
        assert satir.bucket == ia.BUCKET_NEW
        assert satir.copies_created == 1
        assert any("sağlama" in ileti for ileti in satir.issues)

    def test_cozulemeyen_yil_bos_kalir_ve_uyarir(self) -> None:
        rapor = _uygula([{**KITAP, "publish_year": "bilinmiyor", "copies": 1}])

        assert Work.objects.get().publish_year is None
        assert any("Yayın yılı" in ileti for ileti in _satir(rapor, 2).issues)

    def test_dort_haneli_olmayan_yil_bos_kalir(self) -> None:
        rapor = _uygula([{**KITAP, "publish_year": "99", "copies": 1}])

        assert Work.objects.get().publish_year is None
        assert any("dört haneli" in ileti for ileti in _satir(rapor, 2).issues)

    def test_eksi_nusha_sayisi_satiri_dusurur(self) -> None:
        rapor = _onizle([{**KITAP, "copies": "-3"}])

        assert _satir(rapor, 2).bucket == ia.BUCKET_SKIPPED
        assert "sayı değil" in _satir(rapor, 2).issues[0]

    @pytest.mark.parametrize("hucre", ["2-3", "1,5", "3 ya da 4", "1.5"])
    def test_belirsiz_nusha_hucresi_satiri_dusurur(self, hucre: str) -> None:
        """Rakamları kazımak "2-3"ü 23 nüsha yapardı: her biri kalıcı kayıt no alır."""
        rapor = _onizle([{**KITAP, "copies": hucre}])

        satir = _satir(rapor, 2)
        assert satir.bucket == ia.BUCKET_SKIPPED
        assert "sayı değil" in satir.issues[0]
        assert rapor.stats["copies_created"] == 0


# ---------------------------------------------------------------------------
# 7. Dosya okuma: sayfa seçimi, eşanlam başlıklar, kayık başlık satırı
# ---------------------------------------------------------------------------
class TestDosyaOkuma:
    def test_yalnizca_katalog_sayfasi_okunur(self) -> None:
        """Şablonun "Örnek" sayfasındaki satırlar kitap sanılmaz."""
        from apps.kutuphane import excel_template

        parsed, ozet = ia.rows_from_file(
            excel_template.build_catalog_template(), source=CatalogImportSource.EXCEL
        )
        rapor = ia.apply_import(parsed, payload_sha256=ozet)

        assert parsed.rows == []
        assert rapor.stats["total_rows"] == 0
        assert Work.objects.count() == 0

    def test_esanlam_basliklar_taninir(self) -> None:
        dosya = sentetik_katalog.baslikli_dosya(
            ["Kitabın Adı", "Yazarı", "Adet", "Raf"],
            [["Huzur", "Ahmet Hamdi Tanpınar", 2, "Edebiyat"]],
        )
        ortak.bolum(name="Edebiyat")

        parsed, ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)
        rapor = ia.apply_import(parsed, payload_sha256=ozet)

        assert rapor.stats["copies_created"] == 2
        assert Work.objects.get().title == "Huzur"

    def test_baslik_satiri_ustundeki_satirlar_atlanir(self) -> None:
        dosya = sentetik_katalog.baslikli_dosya(
            ["Eser Adı", "Yazar"],
            [["Huzur", "Ahmet Hamdi Tanpınar"]],
            on_satirlar=[["Okul Kütüphanesi Kitap Listesi"], []],
        )

        parsed, _ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        assert [satir.title for satir in parsed.rows] == ["Huzur"]
        assert parsed.header_row == 3

    def test_taninmayan_sutunlar_raporlanir(self) -> None:
        dosya = sentetik_katalog.baslikli_dosya(
            ["Eser Adı", "Yazar", "Fiyat"], [["Huzur", "Ahmet Hamdi Tanpınar", "120 TL"]]
        )

        parsed, _ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        assert parsed.unknown_headers == ["Fiyat"]
        assert "ISBN" in parsed.missing_columns

    def test_baslik_satiri_yoksa_anlasilir_hata(self) -> None:
        from apps.okul.excel_ogrenci import ParserError

        dosya = sentetik_katalog.baslikli_dosya(["Bir", "İki"], [["a", "b"]])

        with pytest.raises(ParserError) as hata:
            ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        assert "Başlık satırı bulunamadı" in str(hata.value)

    def test_excel_olmayan_dosya_anlasilir_hata(self) -> None:
        from apps.okul.excel_ogrenci import ParserError

        with pytest.raises(ParserError) as hata:
            ia.rows_from_file(b"eser adi;yazar\n", source=CatalogImportSource.EXCEL)

        assert "Excel olarak okunamadı" in str(hata.value)

    def test_sayi_bicimli_isbn_hucresi_bozulmaz(self) -> None:
        """Excel ISBN'i `9786059990017.0` diye verebilir; sondaki ".0" numarayı bozardı."""
        dosya = sentetik_katalog.baslikli_dosya(
            ["Eser Adı", "ISBN"], [["Huzur", float(sentetik_katalog.sentetik_isbn(1))]]
        )

        parsed, _ozet = ia.rows_from_file(dosya, source=CatalogImportSource.EXCEL)

        assert parsed.rows[0].isbn == sentetik_katalog.sentetik_isbn(1)


# ---------------------------------------------------------------------------
# 8. Edinim partisi, etiket kısayolu ve Türkçe anahtarlar
# ---------------------------------------------------------------------------
class TestPartiVeAnahtarlar:
    def test_parti_kimligi_ve_barkod_araligi_doner(self) -> None:
        """F4 kısayolu: "bu partinin etiketlerini bas" bu kimliğe bağlanır."""
        rapor = _uygula([{**KITAP, "copies": 3}])

        parti = rapor.label_batch
        assert parti is not None
        assert parti["copy_count"] == 3
        assert parti["first_barcode"] < parti["last_barcode"]
        assert selectors.copies(acquisition_id=parti["acquisition"]).count() == 3

    def test_kosu_edinime_baglanir(self) -> None:
        rapor = _uygula([KITAP])

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        assert kayit.status == CatalogImportStatus.APPLIED
        assert kayit.acquisition_id == (rapor.label_batch or {})["acquisition"]

    def test_varsayilan_edinim_yolu_mevcut_koleksiyondur(self) -> None:
        rapor = _uygula([KITAP])

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        assert kayit.acquisition is not None
        assert kayit.acquisition.method == AcquisitionMethod.EXISTING_STOCK

    def test_edinim_alanlari_uygulanir(self) -> None:
        karar = ortak.karar()

        rapor = _uygula(
            [KITAP],
            spec=ia.AcquisitionSpec(
                method=AcquisitionMethod.DONATION,
                source_note="Selma Yücel",
                commission_decision=karar,
            ),
        )

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        assert kayit.acquisition is not None
        assert kayit.acquisition.source_note == "Selma Yücel"

    def test_hicbir_satir_aktarilamazsa_bos_parti_acilmaz(self) -> None:
        _uygula([{**KITAP, "title": ""}])

        assert not CatalogImportRun.objects.get().acquisition_id

    def test_yazma_aninda_dusen_satirlar_da_bos_parti_birakmaz(self) -> None:
        """Ayrıştırmada değil YAZMADA düşen satır (TMY Md. 15/4) partiyi bırakmamalı."""
        rapor = _uygula(
            [
                {**KITAP, "title": "Bilim Dergisi", "resource_type": "Süreli yayın", "copies": 1},
                {**KITAP, "title": "Tarih Dergisi", "resource_type": "Süreli yayın", "copies": 1},
            ]
        )

        assert rapor.stats["error_rows"] == 2
        assert Copy.objects.count() == 0
        assert Acquisition.all_objects.count() == 0
        assert not CatalogImportRun.objects.get().acquisition_id

    def test_turkce_arama_anahtarlari_doldurulur(self) -> None:
        """Toplu yazma kestirmesi kullanılsaydı anahtarlar boş kalırdı (T7)."""
        _uygula([{**KITAP, "title": "Şiir Kitabı", "copies": 1}])

        assert selectors.works(q="ŞİİR").count() == 1
        assert Work.objects.get().sort_key != ""


# ---------------------------------------------------------------------------
# 9. Rapor biçimi
# ---------------------------------------------------------------------------
class TestRapor:
    def test_kalici_rapor_yalniz_sorunlu_satirlari_tutar(self) -> None:
        rapor = _uygula([{**KITAP, "copies": 1}, {**KITAP, "title": "", "copies": 1}])

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        assert [satir["row"] for satir in kayit.report["rows"]] == [3]
        assert kayit.stats["total_rows"] == 2

    def test_kalici_rapor_ham_hucre_metni_tasimaz(self) -> None:
        """Kütük kalıcıdır ve silme ucu yoktur; kaymış bir sütun kişi adı taşıyabilir."""
        baslik = "Kayık Sütundan Düşen Metin"
        rapor = _uygula([{**KITAP, "title": baslik, "copies": "iki tane"}])

        kayit = CatalogImportRun.objects.get(pk=rapor.run_id)
        dokum = json.dumps(kayit.report, ensure_ascii=False)
        assert baslik not in dokum
        assert "iki tane" not in dokum
        assert kayit.report["rows"][0] == {
            "row": 2,
            "bucket": ia.BUCKET_SKIPPED,
            "work": None,
            "copies": 0,
            "copies_created": 0,
            "needs_decision": False,
            "issue_count": 1,
        }
        # API yanıtı (geçici, ekranda) ham metni GÖSTERİR: kullanıcı kendi
        # dosyasındaki satırı görmelidir.
        assert _satir(rapor, 2).title == baslik

    def test_aktarilmayan_satir_ders_kitabi_sayacina_girmez(self) -> None:
        """Sayaç, önizlemede "N satırda uygulandı" diye gösterilen KARARDIR."""
        rapor = _uygula(
            [
                {**KITAP, "title": "", "subjects": "Ders kitabı", "copies": 1},
                {**KITAP, "title": "Fizik 9", "subjects": "Ders kitabı", "copies": 1},
            ]
        )

        assert rapor.stats["skipped_rows"] == 1
        assert rapor.stats["imported_rows"] == 1
        assert rapor.stats["reference_defaults"] == 1

    def test_aday_listesi_tavanlidir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Aynı ada sahip yüzlerce eser olağandır; tavansız liste ekranı kilitlerdi."""
        monkeypatch.setattr(ia, "MAX_CANDIDATES", 2)
        for sira in range(4):
            ortak.eser(title="Matematik", authors=f"Yazar {sira}")

        rapor = _onizle([{**KITAP, "title": "Matematik", "authors": "Başka Yazar", "copies": 1}])

        satir = _satir(rapor, 2)
        assert satir.needs_decision is True
        assert len(satir.candidates) == 2
        assert satir.candidate_count == 4
        assert satir.candidates_truncated is True

    def test_api_raporu_tavana_kadar_satir_tasir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ia, "MAX_REPORT_ROWS", 2)
        satirlar = sentetik_katalog.sentetik_satirlar(5)
        for satir in satirlar:
            satir["shelf_location"] = ""

        veri = _onizle(satirlar).to_dict()

        assert len(veri["rows"]) == 2
        assert veri["rows_truncated"] is True

    def test_sorunlu_satirlar_tavanda_oncelikli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ia, "MAX_REPORT_ROWS", 1)
        satirlar = sentetik_katalog.sentetik_satirlar(4)
        for satir in satirlar:
            satir["shelf_location"] = ""
        satirlar[3]["title"] = ""

        veri = _onizle(satirlar).to_dict()

        assert [satir["row"] for satir in veri["rows"]] == [5]

    def test_siniflama_kaynagi_raporda_gorunur(self) -> None:
        """ESTIMATED kodlar katalogda "tahmini" rozetiyle görünür (§8.2)."""
        parsed = ia.rows_from_payload(
            {
                "schema_version": "v1",
                "items": [
                    {
                        "title": "Huzur",
                        "authors": "Ahmet Hamdi Tanpınar",
                        "classification_code": "894.353",
                        "classification_source": "ESTIMATED",
                    }
                ],
            }
        )
        rapor = ia.apply_import(parsed, payload_sha256="", source=CatalogImportSource.AI_JSON)

        assert rapor.stats["estimated_codes"] == 1
        assert Work.objects.get().classification_source == ClassificationSource.ESTIMATED
