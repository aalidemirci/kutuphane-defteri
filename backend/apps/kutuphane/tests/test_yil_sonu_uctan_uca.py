"""Yıl sonu akışı — sentetik veriyle UÇTAN UCA (F7 kod kapısı; tasarım §8.3, §14.1 F7).

Senaryo (uydurma bir lise, Mayıs ortası):

0. Kurgu: son sınıf öğrencilerinde açık ödünçler (biri gecikmiş), havuzdaki bir
   öğrenci, öğretmene teslim; son sınıf şubesine toplu teslim teslim ucundan yapılır
   ve teslim listesi basılır; bir son sınıf öğrencisinin ödünçteki kitabı için kayıp
   dosya ucundan bildirilir (ödünç kayba dönüşür).
1. Son ödünç tarihleri Kütüphane Politikası ucundan girilir; son sınıflar için
   daha erken tarih geçince son sınıf öğrencisine yeni ödünç verilmez, iade sürer.
2. Toplama görünümü: açık ödünç ve teslimler — son sınıflar önce, sonra ayrılanlar
   (havuzdaki öğrenci), sonra öbürleri; yıl sonu iade hatırlatma pusulaları basılır.
3. Son sınıflar ve ayrılanlar için ilişik listesi (açık ödünç ve teslim) ve son
   sınıf şubesinin sınıf kitaplığı.
4. İade (masa ucu), teslimden geri alma (okutma ucu, geri alma dökümü), kayıp
   dosyasının çözümü; ardından son sınıfların ilişik listesi boşalır ve
   "Kütüphaneden ilişiği yoktur" belgeleri basılır (kişi başına bir sayfa).

Adımların durumları `library/year-flows/` özetiyle izlenir. Bütün kişi verileri
uydurmadır.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane.models import CaseResolution, LoanStatus, LossDamageCase
from apps.kutuphane.services import circulation
from apps.kutuphane.services.circulation import DolasimReddi
from apps.kutuphane.tests.dolasim_ortak import (
    ders_yili,
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    uye,
)
from apps.kutuphane.tests.teslim_ortak import kademe_yaz, nushalar, ogretmen, sube, teslim_et
from apps.okul.models import SchoolLevel
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

KOK = "/api/v1/library/"
#: Mayıs ortasında bir pazartesi (yıl sonu penceresinin içi).
MAYIS: date = date(2027, 5, 17)


def _pdf(yanit: Any) -> bytes:
    assert yanit.status_code == 200, yanit.content[:300] if hasattr(yanit, "content") else ""
    return b"".join(yanit.streaming_content)


def _metin(icerik: bytes) -> str:
    return " ".join(
        " ".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages).split()
    )


def _sayfa(icerik: bytes) -> int:
    return len(PdfReader(io.BytesIO(icerik)).pages)


def test_yil_sonu_akisi_uctan_uca(bugun: list[date]) -> None:
    client = APIClient()
    kademe_yaz(SchoolLevel.ORTAOGRETIM)
    ders_yili()  # 07.09.2026 – 25.06.2027
    bugun[0] = MAYIS

    # --- Sentetik okul: son sınıflar, ayrılan öğrenci, 10. sınıf, öğretmen, sınıf kitaplığı
    son_a = ogrenci(first_name="Deneme", last_name="Mezunbir", class_level=12, class_section="A")
    son_b = ogrenci(first_name="Deneme", last_name="Mezuniki", class_level=12, class_section="B")
    son_kayip = ogrenci(first_name="Deneme", last_name="Mezunüç", class_level=12, class_section="A")
    son_temiz = ogrenci(first_name="Deneme", last_name="Mezuntemiz", class_level=12)
    giden = ogrenci(first_name="Deneme", last_name="Nakilgiden", class_level=11)
    onuncu = ogrenci(first_name="Deneme", last_name="Onuncu", class_level=10)
    hoca = ogretmen(first_name="Deneme", last_name="Sınıfhocası")

    u_a, u_b, u_kayip, u_giden, u_on = (uye(k) for k in (son_a, son_b, son_kayip, giden, onuncu))
    a1, a2 = odunc_ver(u_a), odunc_ver(u_a)
    gecikmeli_yap(a1, gun=6)
    b1 = odunc_ver(u_b)
    kayip_odunc = odunc_ver(u_kayip, odunc_nushasi(title="Deneme Kayıp Kaynak"))
    g1 = odunc_ver(u_giden)
    on1 = odunc_ver(u_on)
    persons.add_to_leave_pool(giden, run=None)
    ogretmen_teslimi = teslim_et(nushalar(3), personnel=hoca)

    # Sınıf kitaplığına toplu teslim (teslim ucu) ve teslim listesi (E15).
    sinif_barkodlari = [n.barcode for n in nushalar(4)]
    teslim_yaniti = client.post(
        f"{KOK}deliveries/",
        {"section_id": sube(12, "A").pk, "barcodes": sinif_barkodlari},
        format="json",
    )
    assert teslim_yaniti.status_code == 201, teslim_yaniti.json()
    belge_no = teslim_yaniti.json()["document_no"]
    teslim_listesi = _metin(_pdf(client.get(f"{KOK}deliveries/pdf/", {"document_no": belge_no})))
    assert "TESLİM LİSTESİ" in teslim_listesi and "12/A" in teslim_listesi
    # pypdf "T" ile "e" arasına aralık koyabilir (kerning); cümlenin gövdesi aranır.
    assert "ödünç değildir." in teslim_listesi and belge_no in teslim_listesi

    # Kayıp bildirimi (dosya ucu): ödünç kayba dönüşür, sorumlu ödünç kaydından gelir.
    kayip_yaniti = client.post(
        f"{KOK}loss-damage-cases/",
        {"case_type": "LOST", "barcode": kayip_odunc.copy.barcode},
        format="json",
    )
    assert kayip_yaniti.status_code == 201, kayip_yaniti.json()
    dosya_id = kayip_yaniti.json()["id"]
    assert kayip_yaniti.json()["membership"] == u_kayip.pk
    kayip_odunc.refresh_from_db()
    assert kayip_odunc.status == LoanStatus.LOST_CONVERTED

    # --- 1. Son ödünç tarihleri (Kütüphane Politikası ucu)
    yanit = client.put(
        f"{KOK}policy/",
        {
            "last_loan_date": (MAYIS + timedelta(days=21)).isoformat(),
            "last_loan_date_graduating": (MAYIS + timedelta(days=3)).isoformat(),
        },
        format="json",
    )
    assert yanit.status_code == 200, yanit.json()
    akis = client.get(f"{KOK}year-flows/").json()
    assert akis["year_end"]["in_window"] is True
    assert akis["year_end"]["steps"]["dates"] is True
    assert akis["year_end"]["counts"]["graduating_persons"] == 3
    assert akis["year_end"]["graduating_clear_students"] == 1

    bugun[0] = MAYIS + timedelta(days=4)  # son sınıf tarihi geçti, genel tarih geçmedi
    with pytest.raises(DolasimReddi) as red:
        odunc_ver(u_b)
    assert red.value.code == circulation.RED_SON_TARIH
    assert odunc_ver(u_on).pk  # 10. sınıfa hâlâ ödünç verilir

    # --- 2. Toplama görünümü: son sınıflar önce, sonra ayrılanlar, sonra öbürleri
    toplama = client.get(f"{KOK}clearance/", {"obligation": "collect", "limit": "50"}).json()
    adlar = [s["full_name"] for s in toplama["results"]]
    assert adlar == [
        "Deneme Mezunbir",
        "Deneme Mezuniki",
        "Deneme Nakilgiden",
        "Deneme Onuncu",
        "Deneme Sınıfhocası",
    ]
    assert [s["group"] for s in toplama["results"]][:3] == ["graduating", "graduating", "leaving"]
    assert "Deneme Mezunüç" not in adlar  # yalnız kayıp dosyası var: toplanacak kitap yok

    pusula = _pdf(
        client.post(
            f"{KOK}year-end/slips/",
            {"group": "priority", "return_by": (MAYIS + timedelta(days=14)).isoformat()},
            format="json",
        )
    )
    pusula_metni = _metin(pusula)
    assert _sayfa(pusula) == 1  # üç kişi: Mezunbir, Mezuniki, Nakilgiden
    for ad in ("Deneme Mezunbir", "Deneme Mezuniki", "Deneme Nakilgiden"):
        assert ad in pusula_metni
    assert "Deneme Onuncu" not in pusula_metni
    assert f"en geç {MAYIS + timedelta(days=14):%d.%m.%Y}" in pusula_metni

    # --- 3. Son sınıflar ve ayrılanlar: ilişik listesi ve sınıf kitaplıkları
    oncelikli = client.get(f"{KOK}clearance/", {"group": "priority"}).json()
    # Grup içinde sınıf → şube → okul no: 12/A'daki iki öğrenci 12/B'den önce.
    assert [s["full_name"] for s in oncelikli["results"]] == [
        "Deneme Mezunbir",
        "Deneme Mezunüç",
        "Deneme Mezuniki",
        "Deneme Nakilgiden",
    ]
    liste = _metin(_pdf(client.get(f"{KOK}clearance/pdf/", {"group": "priority"})))
    assert "Son sınıflar ve okuldan ayrılanlar" in liste
    assert "SINIF KİTAPLIKLARINDAKİ AÇIK TESLİMLER" in liste and "12/A" in liste
    assert "Kişisel veri içerir — asılmaz, çoğaltılmaz." in liste
    subeler = client.get(f"{KOK}clearance/sections/", {"graduating": "1"}).json()
    assert [(s["section_label"], s["delivery_count"]) for s in subeler] == [("12/A", 4)]

    # --- 4. İade, geri alma ve dosya çözümü
    for loan in (a1, a2, b1, g1):
        iade = client.post(f"{KOK}return/", {"barcode": loan.copy.barcode}, format="json")
        assert iade.json()["result"] == "returned"
    geri = client.post(
        f"{KOK}deliveries/take-back/", {"barcodes": sinif_barkodlari}, format="json"
    ).json()["results"]
    assert {s["result"] for s in geri} == {"returned"}
    dokum = _metin(
        _pdf(
            client.post(
                f"{KOK}deliveries/take-back-report/",
                {"delivery_ids": [s["delivery"]["id"] for s in geri]},
                format="json",
            )
        )
    )
    assert "4 kitap geri alındı" in dokum
    cozum = client.post(
        f"{KOK}loss-damage-cases/{dosya_id}/resolve/",
        {"resolution": "PRICE_DETERMINED", "market_price": "185.50"},
        format="json",
    )
    assert cozum.status_code == 200, cozum.json()
    tutanak = _metin(_pdf(client.get(f"{KOK}loss-damage-cases/{dosya_id}/pdf/")))
    assert "KAYIP/HASAR TUTANAĞI" in tutanak and "185,50 TL" in tutanak
    assert "Deneme Mezunüç" in tutanak  # sorumlunun adı şifreli alandan çözülür
    # "Bedel belirlendi" kişinin açık işini bitirmez (Md. 19: bedel kişiden alınır).
    assert client.get(f"{KOK}clearance/", {"group": "graduating"}).json()["count"] == 1
    teslim_alindi = client.post(
        f"{KOK}loss-damage-cases/{dosya_id}/resolve/",
        {"resolution": "PRICE_RECEIVED"},
        format="json",
    )
    assert teslim_alindi.status_code == 200, teslim_alindi.json()
    # "Bedel teslim alındı": kişi ilişik listesinden çıkar; dosya okul için açık kalır.
    assert client.get(f"{KOK}clearance/", {"group": "graduating"}).json()["count"] == 0
    assert teslim_alindi.json()["is_open"] is True
    assert [
        d["id"] for d in client.get(f"{KOK}loss-damage-cases/", {"open": "1"}).json()["results"]
    ] == [dosya_id]
    kapanis = client.post(
        f"{KOK}loss-damage-cases/{dosya_id}/resolve/",
        {"resolution": CaseResolution.CLOSED_SAME_REPURCHASED},
        format="json",
    )
    assert kapanis.status_code == 200, kapanis.json()
    assert kapanis.json()["is_open"] is False
    assert LossDamageCase.objects.get(pk=dosya_id).market_price == Decimal("185.50")

    # Son sınıflar ve ayrılanlar temiz; öğretmen ve 10. sınıf hâlâ listede.
    assert client.get(f"{KOK}clearance/", {"group": "priority"}).json()["count"] == 0
    kalan = [s["full_name"] for s in client.get(f"{KOK}clearance/").json()["results"]]
    assert kalan == ["Deneme Onuncu", "Deneme Sınıfhocası"]
    assert client.get(f"{KOK}clearance/sections/").json() == []
    akis = client.get(f"{KOK}year-flows/").json()["year_end"]
    assert akis["steps"]["graduating"] is True
    assert akis["steps"]["collection"] is False  # öğretmen teslimi ve 10. sınıf ödüncü
    assert akis["graduating_clear_students"] == 4

    # Mezuniyetten önce belgeler: açık işi olmayan son sınıf öğrencilerinin hepsine.
    temizler = client.get(
        f"{KOK}clearance/", {"state": "clear", "group": "graduating", "limit": "50"}
    ).json()
    kimlikler = [s["person_id"] for s in temizler["results"]]
    assert sorted(kimlikler) == sorted(k.pk for k in (son_a, son_b, son_kayip, son_temiz))
    belge = _pdf(
        client.post(f"{KOK}clearance/certificates/", {"student_ids": kimlikler}, format="json")
    )
    assert _sayfa(belge) == 4
    belge_metni = _metin(belge)
    assert belge_metni.count("KÜTÜPHANEDEN İLİŞİĞİ YOKTUR BELGESİ") == 4
    for sozcuk in ("karne", "diploma", "borç"):
        assert sozcuk not in belge_metni.lower()

    # Açık işi kalan öğretmene belge basılmaz; teslimleri geri alınınca basılır.
    red_yanit = client.post(
        f"{KOK}clearance/certificates/", {"personnel_ids": [hoca.pk]}, format="json"
    )
    assert red_yanit.status_code == 400
    client.post(
        f"{KOK}deliveries/take-back/",
        {"barcodes": [d.copy.barcode for d in ogretmen_teslimi.deliveries]},
        format="json",
    )
    assert (
        _sayfa(
            _pdf(
                client.post(
                    f"{KOK}clearance/certificates/", {"personnel_ids": [hoca.pk]}, format="json"
                )
            )
        )
        == 1
    )
    assert on1.pk  # 10. sınıfın ödüncü yıl sonu akışında zorla kapatılmaz
