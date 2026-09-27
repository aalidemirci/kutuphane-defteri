"""Okuma ödülü iç çıktısı (E20) — F10 kod kapısı (tasarım §10, §3 profil yasağı).

Kapı: **E20 yalnız yönetici kipinde** (ara katman 403 + seçicinin kendi kapısı) ve
**"İç kullanım" ibareli**; ağa, panoya ve E9'a girmediği `test_profil_yasagi.py`'de
sınanır. Burada: ölçüt (iade edilmiş FARKLI eser; aynı eserin tekrarı bir kez),
eşitler aynı sırada ve sınırdaki eşitlerin hepsi, yalnız okuldaki öğrenciler,
sınıf süzgeci, belgede sayı ve okul no olmaması, Kılavuz 7 alıntısının mevzuat
metniyle birebir olması ve uç.
"""

from __future__ import annotations

import io
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import okuma_odulu_belgesi, selectors_okuma_odulu
from apps.kutuphane.models import Copy, Loan, Membership
from apps.kutuphane.services import circulation, yonetici_kipi
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, ogrenci, uye
from apps.kutuphane.tests.teslim_ortak import ogretmen
from apps.okul.kip import KIP
from apps.okul.models import Student, StudentStatus

pytestmark = pytest.mark.django_db

UC = "/api/v1/library/reading-award/pdf/"
_KILAVUZ = Path("docs") / "mevzuat" / "meb-okul-kutuphaneleri-yonetmeligi-uygulama-kilavuzu.md"


def _oku(yol: Path) -> str:
    yerel_kok = Path(__file__).resolve().parents[4]
    for kok in (yerel_kok, Path("/repo")):
        dosya = kok / yol
        if dosya.is_file():
            return dosya.read_text(encoding="utf-8")
    pytest.fail(f"{yol} bulunamadı (depo kökü: {yerel_kok} ya da /repo).")


def _metin(icerik: bytes) -> str:
    return "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)


def _donem() -> tuple[date, date]:
    bugun = timezone.localdate()
    return bugun - timedelta(days=30), bugun


def _iade_edilmis(uyelik: Membership, copy: Copy | None = None) -> Copy:
    """Ödünç verir ve iade alır; nüshayı döndürür (aynı eser yeniden alınabilsin)."""
    hedef = copy if copy is not None else odunc_nushasi()
    odunc_ver(uyelik, hedef)
    circulation.return_copy(copy=hedef)
    return hedef


def _ogrenci_uye(ad: str, **alanlar: object) -> Membership:
    return uye(ogrenci(first_name=ad, last_name="Deneme", **alanlar))


def _siralar(
    *, class_level: int | None = None, sira_sayisi: int = selectors_okuma_odulu.VARSAYILAN_SIRA
) -> list[tuple[int, str]]:
    bas, son = _donem()
    adaylar = selectors_okuma_odulu.adaylar(
        bas, son, class_level=class_level, sira_sayisi=sira_sayisi
    )
    return [(a.sira, a.ad) for a in adaylar]


# ============================================================ ölçüt ve sıra


class TestOlcut:
    def test_farkli_iade_edilmis_eser_sayisi_ayni_eser_bir_kez(self) -> None:
        cok = _ogrenci_uye("Çokeser")
        for _ in range(3):
            _iade_edilmis(cok)
        tekrar = _ogrenci_uye("Tekrarcı")
        ayni = _iade_edilmis(tekrar)
        for _ in range(5):  # aynı eseri beş kez daha: sıra ödünç sayısıyla şişmez
            _iade_edilmis(tekrar, ayni)
        iki = _ogrenci_uye("İkieser")
        _iade_edilmis(iki)
        _iade_edilmis(iki)

        assert _siralar() == [(1, "Çokeser Deneme"), (2, "İkieser Deneme"), (3, "Tekrarcı Deneme")]

    def test_iade_edilmemis_ve_kayba_donusen_odunc_sayilmaz(self) -> None:
        acik = _ogrenci_uye("Açıkta")
        odunc_ver(acik)
        kayip = _ogrenci_uye("Kayıpta")
        loan = odunc_ver(kayip)
        Loan.objects.filter(pk=loan.pk).update(status="LOST_CONVERTED", lost_at=timezone.now())
        donen = _ogrenci_uye("Dönen")
        _iade_edilmis(donen)

        assert _siralar() == [(1, "Dönen Deneme")]

    def test_esitler_ayni_sirada_sinirdaki_esitlerin_hepsi_girer(self) -> None:
        for ad, sayi in (("Ali", 3), ("Can", 2), ("Ece", 2), ("Ayşe", 2), ("Tek", 1)):
            uyelik = _ogrenci_uye(ad)
            for _ in range(sayi):
                _iade_edilmis(uyelik)

        assert _siralar(sira_sayisi=2) == [
            (1, "Ali Deneme"),
            (2, "Ayşe Deneme"),
            (2, "Can Deneme"),
            (2, "Ece Deneme"),
        ]
        assert _siralar(sira_sayisi=5)[-1] == (5, "Tek Deneme")

    def test_yalniz_okuldaki_ogrenciler_ogretmen_ayrilan_silinen_girmez(self) -> None:
        _iade_edilmis(uye(ogretmen(first_name="Hoca")))
        ayrilan = _ogrenci_uye("Ayrılan")
        _iade_edilmis(ayrilan)
        Student.objects.filter(pk=ayrilan.student_id).update(status=StudentStatus.LEFT)
        silinen = _ogrenci_uye("Silinen")
        _iade_edilmis(silinen)
        Student.objects.filter(pk=silinen.student_id).update(deleted_at=timezone.now())
        kalan = _ogrenci_uye("Kalan")
        _iade_edilmis(kalan)

        assert _siralar() == [(1, "Kalan Deneme")]

    def test_sinif_suzgeci_ve_donem(self) -> None:
        _iade_edilmis(_ogrenci_uye("Dokuzlu", class_level=9))
        onlu = _ogrenci_uye("Onlu", class_level=10)
        _iade_edilmis(onlu)
        eski = _ogrenci_uye("Eskiden", class_level=10)
        _iade_edilmis(eski)
        Loan.objects.filter(membership=eski).update(loaned_at=timezone.now() - timedelta(days=90))

        assert _siralar(class_level=10) == [(1, "Onlu Deneme")]

    def test_sira_sayisi_sinirlari(self) -> None:
        bas, son = _donem()
        for gecersiz in (0, selectors_okuma_odulu.EN_COK_SIRA + 1):
            with pytest.raises(ValidationError):
                selectors_okuma_odulu.adaylar(bas, son, sira_sayisi=gecersiz)


# ============================================================ yönetici kipi


class TestYoneticiKipi:
    def test_gorevli_kipinde_secici_ve_uc_403(self) -> None:
        _iade_edilmis(_ogrenci_uye("Görevliye"))
        bas, son = _donem()
        KIP.gorevliye_gec()

        with pytest.raises(yonetici_kipi.KipYetkisiz):
            selectors_okuma_odulu.adaylar(bas, son)
        yanit = APIClient().get(UC)

        assert yanit.status_code == 403 and yanit.json()["code"] == "kip_yetkisiz"
        assert "Görevliye" not in yanit.content.decode("utf-8")

    def test_uc_izin_listesinde_degil(self) -> None:
        from apps.okul.kip_izinleri import IZIN_LISTESI

        assert "library-reading-award-pdf" not in {kural.uc for kural in IZIN_LISTESI}


# ============================================================ belge


class TestBelge:
    def test_ic_kullanim_ibaresi_ad_ve_sinif_var_sayi_ve_okul_no_yok(self) -> None:
        uyelik = _ogrenci_uye("Belgeogrenci", student_number="963852", class_level=9)
        for _ in range(4):
            _iade_edilmis(uyelik)
        bas, son = _donem()

        metin = _metin(okuma_odulu_belgesi.ic_cikti_pdf(bas, son))

        assert okuma_odulu_belgesi.BASLIK in metin
        assert "İç kullanım" in metin
        assert okuma_odulu_belgesi.DIPNOT in " ".join(metin.split())
        assert "Belgeogrenci Deneme" in metin and "9/A" in metin
        assert "963852" not in metin and uyelik.card_no not in metin
        assert "Ödünç kaydı okunan kitabı göstermez." in " ".join(metin.split())
        # Sıra basılır, ölçüt (4 farklı eser) basılmaz: tarihin parçası olmayan "4" yok.
        assert not re.search(r"(?<![\d.])4(?![\d.])", metin)
        for yasak in ("okuduğu kitap", "okuma karnesi", "okuma puanı"):
            assert yasak not in metin.casefold()

    def test_kilavuz_7_alintisi_mevzuatla_birebir(self) -> None:
        kilavuz = _oku(_KILAVUZ)
        bolum = kilavuz.split("## 7.", 1)[1].split("## 8.", 1)[0]
        assert okuma_odulu_belgesi.KILAVUZ_7_ONERISI in bolum

    def test_bos_liste_400_uc_pdf_ve_dosya_adi(self) -> None:
        istemci = APIClient()
        bas, son = _donem()

        bos = istemci.get(UC, {"start": bas.isoformat(), "end": son.isoformat()})
        assert bos.status_code == 400
        assert bos.json()["message"] == okuma_odulu_belgesi.BOS_LISTE

        _iade_edilmis(_ogrenci_uye("Ucogrenci"))
        yanit = istemci.get(UC, {"start": bas.isoformat(), "end": son.isoformat(), "limit": "3"})

        assert yanit.status_code == 200
        assert yanit["Content-Type"] == "application/pdf"
        assert yanit["Cache-Control"] == "no-store"
        assert "Ucogrenci" not in unquote(yanit["Content-Disposition"])
        assert "Okuma-ödülü-iç-çıktısı_" in unquote(yanit["Content-Disposition"])
        metin = _metin(b"".join(yanit.streaming_content))  # type: ignore[attr-defined]
        assert "Ucogrenci Deneme" in metin and "İlk 3 sıra" in metin

    def test_uc_gecersiz_sinir_400(self) -> None:
        yanit = APIClient().get(UC, {"limit": "0"})
        assert yanit.status_code == 400
        assert yanit.json()["message"] == selectors_okuma_odulu.SIRA_SINIRI_ILETISI
