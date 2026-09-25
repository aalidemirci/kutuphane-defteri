"""Yıl sonu kütüphane raporu belgesi (E9) — F8; tasarım §10, F8 ekleri 8.

Kod kapısı: **E9'da kişisel veri yok** — `TestKisiselVeriYok` sentetik adlarla dolu bir
yıl kurar (öğrenci, öğretmen, bağışçı, komisyon, harcama yetkilisi, TMY komisyonu,
sorumlu notu; `test_yil_sonu_raporu._dolu_yil`) ve basılı raporun BÜTÜN metnini tarar.
Resmî yazı düzeni: sayı, tarih, konu, "OKUL MÜDÜRLÜĞÜNE", "Bilgilerinize arz ederim.",
imza (ad basılmaz). Taslak rapor "TASLAK" ibaresi taşır; sonlandırılmış raporun sayıları
dondurulmuştur. Sayfa bütçesi gerçek uzunlukta veriyle (en uzun okul adı, 5.000
karakterlik tespit metni, yirmi uzun adlı bölüm) koşar: kapanış bölünmez.
"""

from __future__ import annotations

import io
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import yil_raporu_belgesi as belge
from apps.kutuphane.models import AcquisitionMethod
from apps.kutuphane.services import annual_review
from apps.kutuphane.tests.dolasim_ortak import odunc_ver, ogrenci, uye
from apps.kutuphane.tests.ortak import bolum, edinim, eser, nusha
from apps.kutuphane.tests.teslim_ortak import etkin_yil, ogretmen
from apps.kutuphane.tests.test_yil_sonu_raporu import SENTINELLER, _dolu_yil
from apps.okul.models import SchoolConfig

pytestmark = pytest.mark.django_db

EN_UZUN_OKUL = ("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3)[:255]
_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")


def _sayfalar(icerik: bytes) -> list[str]:
    return [
        " ".join(_T_ARALIGI.sub("T", s.extract_text() or "").split())
        for s in PdfReader(io.BytesIO(icerik)).pages
    ]


def _metin(icerik: bytes) -> str:
    return " ".join(_sayfalar(icerik))


def _mevzuat(dosya: str) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / dosya
        if yol.is_file():
            return " ".join(yol.read_text(encoding="utf-8").split())
    pytest.fail(f"{dosya} bulunamadı.")


@pytest.fixture(autouse=True)
def okul() -> SchoolConfig:
    config = SchoolConfig.load()
    config.school_name = "Örnek Anadolu Lisesi"
    config.district = "Örnek İlçe"
    config.principal_name = "Örnek Müdür"
    config.save()
    return config


class TestKisiselVeriYok:
    def test_basili_rapor_hicbir_kisi_izi_tasimaz(self) -> None:
        yil, izler = _dolu_yil()
        rapor = annual_review.create_review(school_year=yil)
        annual_review.update_review(rapor, findings="Raflar düzenlendi.", document_no="E-9")

        for sonlandir in (False, True):
            if sonlandir:
                annual_review.finalize_review(rapor)
            rapor.refresh_from_db()
            metin = _metin(belge.annual_review_pdf(rapor)).casefold()
            for ad, deger in SENTINELLER.items():
                assert deger.casefold() not in metin, f"{ad} basılı raporda geçti"
            for iz in izler:
                assert iz.casefold() not in metin
            # Gezinti veriye ulaştı (boş rapor yanlış yeşil verirdi).
            assert "verilen ödünç 4" in metin
            assert "kayıttan düşülen nüsha 1" in metin and "devredilen nüsha 1" in metin
            # İmza satırında ad yok; müdürün adı da rapora basılmaz.
            assert "örnek müdür" not in metin


class TestBicim:
    def test_resmi_yazi_duzeni_ve_bolumler(self) -> None:
        yil = etkin_yil()
        rapor = annual_review.create_review(school_year=yil)
        bugun = timezone.localdate()
        annual_review.update_review(
            rapor, document_no="E-12345678-000-99", document_date=bugun, findings="Deneme tespit."
        )
        rapor.refresh_from_db()
        metin = _metin(belge.annual_review_pdf(rapor))

        assert "Sayı : E-12345678-000-99" in metin
        assert f"{bugun:%d.%m.%Y}" in metin
        assert f"Konu : Yıl sonu kütüphane raporu ({yil.name} ders yılı)" in metin
        assert "OKUL MÜDÜRLÜĞÜNE" in metin
        assert "Okul Kütüphaneleri Yönetmeliği Md. 12/1 gereğince" in metin
        for baslik in (
            "1. TESPİT EDİLEN HUSUSLAR",
            "2. KOLEKSİYON ÖZETİ (RAPOR TARİHİNDE)",
            "3. YIL İÇİNDE KAZANDIRILAN KAYNAKLAR",
            "4. AYIKLANAN VE DEVREDİLEN KAYNAKLAR",
            "5. ÖDÜNÇ İSTATİSTİĞİ",
        ):
            assert baslik in metin
        assert "Deneme tespit." in metin
        assert "Bilgilerinize arz ederim." in metin
        assert "Kütüphane yöneticisi" in metin
        assert "TASLAK" in metin
        assert "imha" not in metin.casefold()

    def test_md12_1_depodaki_metinde(self) -> None:
        assert belge.MD12_1_RAPOR in _mevzuat("meb-okul-kutuphaneleri-yonetmeligi.md")

    def test_bos_tespit_ve_sayisiz_belge(self) -> None:
        rapor = annual_review.create_review(school_year=etkin_yil())
        metin = _metin(belge.annual_review_pdf(rapor))
        assert belge.BOS_TESPIT in metin
        assert "Sayı : ……………" in metin

    def test_k_esiginin_altindaki_grup_sayisi_basilmaz(self) -> None:
        """Denetimin senaryosu: basılı metinde gizli grup toplamdan çıkarılarak bulunamaz."""
        etkin_yil()
        for duzey in (9, 10):
            for _ in range(5):
                odunc_ver(uye(ogrenci(class_level=duzey)))
        tek = uye(ogrenci(class_level=11))
        for _ in range(3):
            odunc_ver(tek)
        hoca = uye(ogretmen())
        for _ in range(2):
            odunc_ver(hoca)
        rapor = annual_review.create_review(school_year=etkin_yil())
        metin = _metin(belge.annual_review_pdf(rapor))

        assert "Verilen ödünç 15" in metin
        assert "Öğrenci: — · Öğretmen: — · Diğer personel: —" in metin
        assert "9. sınıf: — · 10. sınıf: 5 · 11. sınıf: —" in metin
        assert "Öğrenci: 11 · Öğretmen: — · Diğer personel: 0" in metin
        assert "Öğrenci: 13" not in metin and "11. sınıf: 3" not in metin
        assert "5 farklı üyeden azının ödünç aldığı grubun sayısı gösterilmez" in metin
        assert "toplamdan çıkarılarak bulunamasın" in metin

    def test_kazandirilan_yalniz_md_10_5_yollarindan(self) -> None:
        etkin_yil()
        bugun = timezone.localdate()
        aktarim = edinim(method=AcquisitionMethod.EXISTING_STOCK, date=bugun)
        for i in range(4):
            nusha(eser(title=f"Aktarılan {i}"), aktarim)
        nusha(eser(title="Satın Alınan"), edinim(method=AcquisitionMethod.PURCHASE, date=bugun))
        rapor = annual_review.create_review(school_year=etkin_yil())
        metin = _metin(belge.annual_review_pdf(rapor))

        assert "Toplam kazandırılan nüsha 1" in metin
        assert "Kayıt içi girişler (kazandırılan sayılmaz)" in metin
        assert "Mevcut koleksiyon (programa aktarım)" in metin
        bolum = belge.annual_review_context(rapor)["sections"][2]
        satirlar = {r["label"]: r["value"] for r in bolum["rows"]}
        assert satirlar["Mevcut koleksiyon (programa aktarım)"] == "4"
        assert satirlar["Toplam kazandırılan nüsha"] == "1"

    def test_sonlandirilmis_rapor_dondurulmus_sayilari_basar(self) -> None:
        etkin_yil()
        odunc_ver(uye(ogrenci()))
        rapor = annual_review.create_review(school_year=etkin_yil())
        annual_review.finalize_review(rapor)
        odunc_ver(uye(ogrenci()))  # sonlandırmadan sonra
        rapor.refresh_from_db()
        metin = _metin(belge.annual_review_pdf(rapor))

        assert "TASLAK" not in metin
        assert "Verilen ödünç 1" in metin

    def test_dosya_adi_ders_yiliyla(self) -> None:
        rapor = annual_review.create_review(school_year=etkin_yil())
        ad = belge.annual_review_filename(rapor)
        assert ad.startswith("Yıl-sonu-kütüphane-raporu_") and ad.endswith(".pdf")
        assert rapor.school_year.name.replace("/", "-").replace(" ", "-") in ad


class TestSayfaButcesi:
    def test_uzun_veride_kapanis_bolunmez(self, okul: SchoolConfig) -> None:
        okul.school_name = EN_UZUN_OKUL
        okul.save()
        etkin_yil()
        for i in range(20):
            b = bolum(name=f"Örnek Uzun Adlı Bölüm {i:02d} — Türk ve Dünya Edebiyatı Seçkisi")
            nusha(eser(title=f"Bölüm Eseri {i}"), section=b)
        rapor = annual_review.create_review(school_year=etkin_yil())
        uzun = (
            "Raflar yeniden düzenlendi, yıpranan kaynaklar ayrıldı ve onarıma gönderildi. " * 70
        )[: annual_review.FINDINGS_MAX]
        annual_review.update_review(rapor, findings=uzun, document_no="E-" + "9" * 38)
        rapor.refresh_from_db()
        sayfalar = _sayfalar(belge.annual_review_pdf(rapor))

        assert 2 <= len(sayfalar) <= 5
        son = sayfalar[-1]
        assert "Bilgilerinize arz ederim." in son and "Kütüphane yöneticisi" in son

    def test_olagan_rapor_iki_sayfayi_asmaz(self) -> None:
        yil, _ = _dolu_yil()
        rapor = annual_review.create_review(school_year=yil)
        annual_review.update_review(
            rapor,
            findings="Raflar düzenlendi; yıpranan kitaplar onarıma gönderildi.",
            document_date=timezone.localdate() - timedelta(days=1),
        )
        rapor.refresh_from_db()
        assert len(_sayfalar(belge.annual_review_pdf(rapor))) <= 2


class TestUc:
    def test_pdf_ucu(self) -> None:
        rapor = annual_review.create_review(school_year=etkin_yil())
        yanit = APIClient().get(f"/api/v1/library/annual-reviews/{rapor.pk}/pdf/")
        assert yanit.status_code == 200
        assert yanit["Content-Type"] == "application/pdf"
        assert yanit["Cache-Control"] == "no-store"
        assert APIClient().get("/api/v1/library/annual-reviews/99999/pdf/").status_code == 404
