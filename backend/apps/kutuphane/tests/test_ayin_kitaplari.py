"""Ayın Kitapları afişi (E12) ve çok okunanlar uçları (F10 — tasarım §10, §5.3).

- Afiş AY penceresinin sırasını `kd_katalog_populer`'den basar: **eser bazlı,
  eşikli, sayısız** — kişi adı, kart no, okul no, sınıf ve ödünç sayısı geçmez.
- **Sayfa bütçesi**: en uzun künyelerle (500 karakterlik kaynak adı, uzun yazar
  listesi) 10 eser TEK sayfaya sığar (CLAUDE.md §3 "sayfa bütçesi testleri gerçek
  uzunlukta verilerle").
- Sürmekte olan ay "itibarıyla" notuyla, kapanmış ay notsuz basılır; boş pencere 400.
- Uçlar: pencere listeleri, pencere sırası (sayısız), yeniden hesapla, afiş PDF'i.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime, time
from urllib.parse import unquote

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import ayin_kitaplari_belgesi, selectors_populer
from apps.kutuphane.models import KatalogPopuler, Loan, PopulerPencereTuru, Work
from apps.kutuphane.services import circulation, populer
from apps.kutuphane.tests.dolasim_ortak import odunc_ver, ogrenci, uye
from apps.kutuphane.tests.ortak import eser, nusha
from apps.okul.models import SchoolConfig

pytestmark = pytest.mark.django_db

AY = PopulerPencereTuru.AY
KOK = "/api/v1/library/popular/"
UZUN_BASLIK = (
    "Türkiye'nin Çağdaş Öykücülüğünde Kırsal Yaşamın Dönüşümü ve Göç Olgusunun "
    "Edebiyata Yansımaları Üzerine Karşılaştırmalı Bir İnceleme: Şehirleşme, Kimlik, "
    "Aidiyet ve Bellek Sorunsalları Çerçevesinde Kuşaklar Arası Bir Okuma Denemesi "
) * 2
UZUN_YAZAR = (
    "Deneme Yazaroğlu, Örnek Şairoğlu, Sentetik Çevirmenoğlu, Uydurma Editöroğlu, "
    "Deneme Derleyicioğlu, Örnek Resimleyenoğlu"
)
SENTINELLER = ("Afisogrenciad", "Afisogrencisoyad", "741852")


def _metin(icerik: bytes) -> str:
    return "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)


def _sayfa(icerik: bytes) -> int:
    return len(PdfReader(io.BytesIO(icerik)).pages)


def _sira_yaz(pencere: str, eserler: list[Work], *, dondu: bool = False) -> None:
    for sira, work in enumerate(eserler, start=1):
        KatalogPopuler.objects.create(
            eser=work,
            pencere_turu=AY,
            pencere=pencere,
            sira=sira,
            hesaplanma=date(2026, 9, 24),
            dondu=dondu,
        )


def _okul(ad: str = "Örnek Anadolu Lisesi") -> None:
    config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
    config.school_name = ad
    config.save()


# ============================================================ afiş


class TestAfis:
    def test_en_uzun_kunyelerle_on_eser_tek_sayfa(self) -> None:
        _okul("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi")
        eserler = [
            eser(title=f"{i}. {UZUN_BASLIK}"[:500], authors=UZUN_YAZAR) for i in range(1, 11)
        ]
        _sira_yaz("2026-09", eserler)

        pdf = ayin_kitaplari_belgesi.afis_pdf("2026-09")

        assert _sayfa(pdf) == 1
        metin = _metin(pdf)
        assert "AYIN KİTAPLARI" in metin and "Eylül 2026" in metin
        assert "Ay sürüyor" in metin and "24.09.2026" in metin
        assert "…" in metin  # uzun ad iki satırda kısaldı

    def test_afiste_sayi_ve_kisi_izi_yok(self) -> None:
        _okul()
        work = eser(title="Kişisiz Afiş Eseri", authors="Deneme Yazar")
        copy = nusha(work)
        kisiler = [
            uye(ogrenci(first_name=SENTINELLER[0], last_name=SENTINELLER[1], student_number=no))
            for no in (SENTINELLER[2], "741853", "741854", "741855", "741856")
        ]
        for uyelik in kisiler:
            loan = odunc_ver(uyelik, copy)
            circulation.return_copy(copy=copy)
            Loan.objects.filter(pk=loan.pk).update(
                loaned_at=timezone.make_aware(datetime.combine(date(2026, 9, 10), time(10)))
            )
        populer.hesapla(date(2026, 10, 1))  # eylül kapandı: son hesap + dondurma

        metin = _metin(ayin_kitaplari_belgesi.afis_pdf("2026-09"))

        assert "Kişisiz Afiş Eseri" in metin and "Deneme Yazar" in metin
        assert "Ay sürüyor" not in metin  # kapanmış ay
        for iz in [*SENTINELLER, *(u.card_no for u in kisiler)]:
            assert iz.casefold() not in metin.casefold()
        assert "9/A" not in metin
        # Tek sayı sıradır (1) ve dipnottaki bir şey yok; "5" (farklı üye) basılmaz.
        rakamlar = set(re.findall(r"\d+", metin.replace("Eylül 2026", "")))
        assert rakamlar == {"1"}, rakamlar

    def test_bos_ya_da_bilinmeyen_pencere_400(self) -> None:
        with pytest.raises(ValidationError) as hata:
            ayin_kitaplari_belgesi.afis_baglami("2026-09")
        assert ayin_kitaplari_belgesi.BOS_PENCERE in str(hata.value)

        yanit = APIClient().get(f"{KOK}poster/", {"window": "2026-09"})

        assert yanit.status_code == 400
        assert yanit.json()["message"] == ayin_kitaplari_belgesi.BOS_PENCERE

    def test_uc_pdf_doner_pencere_verilmezse_son_ay(self) -> None:
        _sira_yaz("2026-08", [eser(title="Ağustos Eseri")], dondu=True)
        _sira_yaz("2026-09", [eser(title="Eylül Eseri")])

        yanit = APIClient().get(f"{KOK}poster/")

        assert yanit.status_code == 200
        assert yanit["Content-Type"] == "application/pdf"
        assert yanit["Cache-Control"] == "no-store"
        assert "Ayın-Kitapları-afişi_2026-09_" in unquote(yanit["Content-Disposition"])
        metin = _metin(b"".join(yanit.streaming_content))  # type: ignore[attr-defined]
        assert "Eylül Eseri" in metin and "Ağustos Eseri" not in metin


# ============================================================ çok okunanlar uçları


class TestUclar:
    def test_ozet_pencere_listeleri_ve_sirasi_sayisiz(self) -> None:
        _sira_yaz("2026-08", [eser(title="Ağustos")], dondu=True)
        eylul = [eser(title="Birinci"), eser(title="İkinci")]
        _sira_yaz("2026-09", eylul)
        eylul[0].delete()  # silinen eser düşer, sıra boşluksuz yeniden numaralanır

        ozet = APIClient().get(KOK).json()

        assert ozet["k_threshold"] == 5
        assert [p["window"] for p in ozet["month_windows"]] == ["2026-09", "2026-08"]
        assert ozet["month_windows"][1]["frozen"] is True
        assert ozet["month"]["label"] == "Eylül 2026"
        assert ozet["month"]["works"] == [
            {"rank": 1, "work_id": eylul[1].pk, "title": "İkinci", "authors": "Sabahattin Ali"}
        ]
        assert ozet["term"] is None and ozet["term_windows"] == []
        secilen = APIClient().get(KOK, {"window_type": "AY", "window": "2026-08"}).json()
        assert [w["title"] for w in secilen["works"]] == ["Ağustos"]
        for pencere in (secilen, ozet["month"]):
            for satir in pencere["works"]:
                assert set(satir) == {"rank", "work_id", "title", "authors"}

    def test_pencere_bulunamazsa_404_eksik_parametre_400(self) -> None:
        istemci = APIClient()

        yok = istemci.get(KOK, {"window_type": "AY", "window": "2020-01"})
        eksik = istemci.get(KOK, {"window_type": "AY"})
        bozuk = istemci.get(KOK, {"window_type": "YIL", "window": "2026"})

        assert yok.status_code == 404 and yok.json()["code"] == "not_found"
        assert eksik.status_code == 400
        assert bozuk.status_code == 400

    def test_yeniden_hesapla_kisisiz_ozet_doner(self) -> None:
        yanit = APIClient().post(f"{KOK}refresh/")

        assert yanit.status_code == 200
        assert set(yanit.json()) == {"computed_on", "k_threshold", "windows"}

    def test_pano_ozeti_ilk_uc_eser(self) -> None:
        _sira_yaz("2026-09", [eser(title=f"Eser {i}") for i in range(5)])

        pano = selectors_populer.pano_ozeti()

        assert pano["term"] is None
        assert [w["rank"] for w in pano["month"]["works"]] == [1, 2, 3]

    def test_pencere_etiketleri(self) -> None:
        etiket = selectors_populer.pencere_etiketi
        assert etiket("AY", "2027-01") == "Ocak 2027"
        assert etiket("DONEM", "2026-2027/2") == "2026-2027 ders yılı 2. dönem"
        assert etiket("DONEM", "2026-2027") == "2026-2027 ders yılı"
