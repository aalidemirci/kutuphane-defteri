"""Kapalı günler uçları — liste/ekle, sil, tohumla (tasarım §6.1; F1 sözleşmesi §5).

Sabitlenen sözleşmeler:

- Yanıt alan kümesi ön yüz tiplerinin sözleşmesidir (anlık görüntü, T13).
- `?year=` takvim yılıyla KESİŞEN kayıtları tarih sırasıyla döndürür; yıl sınırını
  aşan aralık iki yılda da görünür.
- Doğrulama hataları Türkçedir ve `{code, message, fields}` biçimindedir; ileti
  "Md. 18" diline kaymaz.
- `is_estimated` yalnız tohumlamayla yazılır (istemci gönderse de yok sayılır).
- Tohumlama fikirdeştir; yıl verilmezse bugünün takvim yılı kullanılır.

Kişisel veri yoktur.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.okul.models import Holiday, HolidayKind

pytestmark = pytest.mark.django_db

URL = "/api/v1/holidays/"
SEED_URL = "/api/v1/holidays/seed/"

ARA_TATIL: dict[str, Any] = {
    "name": "1. dönem ara tatili",
    "start_date": "2026-11-09",
    "end_date": "2026-11-13",
    "kind": "SCHOOL_BREAK",
}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _kayit(ad: str, bas: date, bit: date, tur: str = HolidayKind.OFFICIAL) -> Holiday:
    kayit: Holiday = Holiday.objects.create(name=ad, start_date=bas, end_date=bit, kind=tur)
    return kayit


class TestListe:
    def test_alan_kumesi_sabittir(self, client: APIClient) -> None:
        _kayit("Cumhuriyet Bayramı", date(2026, 10, 29), date(2026, 10, 29))
        yanit = client.get(URL)
        assert yanit.status_code == 200
        assert set(yanit.json()[0]) == {
            "id",
            "name",
            "start_date",
            "end_date",
            "kind",
            "is_estimated",
        }

    def test_yil_suzgeci_kesisenleri_tarih_sirasiyla_dondurur(self, client: APIClient) -> None:
        _kayit("Yılbaşı", date(2027, 1, 1), date(2027, 1, 1))
        _kayit(
            "Yıl sonu ara tatili",
            date(2026, 12, 28),
            date(2027, 1, 1),
            tur=HolidayKind.SCHOOL_BREAK,
        )
        _kayit("Cumhuriyet Bayramı", date(2026, 10, 29), date(2026, 10, 29))
        _kayit("Zafer Bayramı", date(2025, 8, 30), date(2025, 8, 30))

        yil_2026 = [h["name"] for h in client.get(URL, {"year": 2026}).json()]
        yil_2027 = [h["name"] for h in client.get(URL, {"year": 2027}).json()]
        hepsi = client.get(URL).json()

        assert yil_2026 == ["Cumhuriyet Bayramı", "Yıl sonu ara tatili"]
        assert yil_2027 == ["Yıl sonu ara tatili", "Yılbaşı"]
        assert len(hepsi) == 4
        assert hepsi[0]["name"] == "Zafer Bayramı"

    def test_ayni_gun_baslayanlar_turkce_alfabeyle_siralanir(self, client: APIClient) -> None:
        for ad in ("Zümre günü", "Çevre günü", "Ilgaz günü", "İnce günü"):
            _kayit(ad, date(2026, 11, 9), date(2026, 11, 9), tur=HolidayKind.OTHER)
        adlar = [h["name"] for h in client.get(URL, {"year": 2026}).json()]
        assert adlar == ["Çevre günü", "Ilgaz günü", "İnce günü", "Zümre günü"]

    def test_silinmis_kayit_listelenmez(self, client: APIClient) -> None:
        _kayit("Cumhuriyet Bayramı", date(2026, 10, 29), date(2026, 10, 29)).delete()
        assert client.get(URL, {"year": 2026}).json() == []

    @pytest.mark.parametrize(
        ("deger", "parca"), [("abc", "dört haneli"), ("1999", "arasında"), ("2101", "arasında")]
    )
    def test_gecersiz_yil_turkce_reddedilir(
        self, client: APIClient, deger: str, parca: str
    ) -> None:
        yanit = client.get(URL, {"year": deger})
        assert yanit.status_code == 400
        govde = yanit.json()
        assert govde["code"] == "validation_error"
        assert "year" in govde["fields"]
        assert parca in govde["message"]


class TestEkleme:
    def test_ogrenciye_kapali_gun_araligi_eklenir(self, client: APIClient) -> None:
        yanit = client.post(URL, {**ARA_TATIL, "is_estimated": True}, format="json")

        assert yanit.status_code == 201
        govde = yanit.json()
        assert govde["kind"] == "SCHOOL_BREAK"
        assert (govde["start_date"], govde["end_date"]) == ("2026-11-09", "2026-11-13")
        # İstemcinin gönderdiği "tahmini" yok sayılır: elle girilen kayıt kesindir.
        assert govde["is_estimated"] is False
        assert Holiday.objects.get(pk=govde["id"]).is_estimated is False

    def test_tur_verilmezse_ogrenciye_kapali_gun_sayilir(self, client: APIClient) -> None:
        govde = {k: v for k, v in ARA_TATIL.items() if k != "kind"}
        yanit = client.post(URL, govde, format="json")
        assert yanit.status_code == 201
        assert yanit.json()["kind"] == "SCHOOL_BREAK"

    @pytest.mark.parametrize(
        ("degisiklik", "alan", "ileti"),
        [
            ({"end_date": "2026-11-06"}, "end_date", "Bitiş tarihi başlangıçtan önce olamaz."),
            ({"end_date": "2027-06-30"}, "end_date", "en çok 120 günü kapsayabilir"),
            ({"kind": "SUMMER"}, "kind", "Geçerli bir tür seçin."),
            ({"start_date": "09.11.2026"}, "start_date", "Geçerli bir tarih girin."),
        ],
    )
    def test_dogrulama_hatalari_turkce_ve_alan_bazlidir(
        self, client: APIClient, degisiklik: dict[str, str], alan: str, ileti: str
    ) -> None:
        yanit = client.post(URL, {**ARA_TATIL, **degisiklik}, format="json")

        assert yanit.status_code == 400
        govde = yanit.json()
        assert govde["code"] == "validation_error"
        assert ileti in " ".join(govde["fields"][alan])
        assert ileti in govde["message"]
        assert "Md. 18" not in govde["message"]
        assert not Holiday.objects.exists()

    def test_bos_ad_alan_altinda_bildirilir(self, client: APIClient) -> None:
        yanit = client.post(URL, {**ARA_TATIL, "name": ""}, format="json")
        assert yanit.status_code == 400
        assert yanit.json()["fields"]["name"] == ["Ad yazılmalıdır."]

    def test_ayni_ad_ve_baslangic_ikinci_kez_eklenemez(self, client: APIClient) -> None:
        assert client.post(URL, ARA_TATIL, format="json").status_code == 201

        yanit = client.post(URL, ARA_TATIL, format="json")

        assert yanit.status_code == 400
        govde = yanit.json()
        assert govde["message"] == "Bu adla aynı günde başlayan bir kayıt zaten var."
        assert "name" in govde["fields"]
        assert Holiday.objects.count() == 1


class TestSilme:
    def test_kayit_yumusak_silinir_ikinci_silme_404(self, client: APIClient) -> None:
        kayit = _kayit("Ara tatil", date(2026, 11, 9), date(2026, 11, 13), HolidayKind.SCHOOL_BREAK)

        assert client.delete(f"{URL}{kayit.pk}/").status_code == 204
        assert not Holiday.objects.exists()
        assert Holiday.all_objects.filter(pk=kayit.pk, deleted_at__isnull=False).exists()

        ikinci = client.delete(f"{URL}{kayit.pk}/")
        assert ikinci.status_code == 404
        assert ikinci.json()["message"] == "Kayıt bulunamadı."


class TestTohumlama:
    def test_yil_tohumlanir_ve_ikinci_cagri_kopya_uretmez(self, client: APIClient) -> None:
        ilk = client.post(SEED_URL, {"year": 2027}, format="json")
        assert ilk.status_code == 200
        assert ilk.json() == {
            "year": 2027,
            "created": 9,
            "skipped": 0,
            "religious_available": True,
        }

        ikinci = client.post(SEED_URL, {"year": 2027}, format="json").json()
        assert (ikinci["created"], ikinci["skipped"]) == (0, 9)

        liste = client.get(URL, {"year": 2027}).json()
        assert len(liste) == 9
        tahminiler = {h["name"] for h in liste if h["is_estimated"]}
        assert tahminiler == {"Ramazan Bayramı", "Kurban Bayramı"}

    def test_yil_verilmezse_bugunun_yili_kullanilir(self, client: APIClient) -> None:
        yanit = client.post(SEED_URL, {}, format="json")
        assert yanit.status_code == 200
        assert yanit.json()["year"] == timezone.localdate().year

    def test_tablo_disi_yil_dini_bayram_olmadigini_soyler(self, client: APIClient) -> None:
        govde = client.post(SEED_URL, {"year": 2035}, format="json").json()
        assert (govde["created"], govde["religious_available"]) == (7, False)

    def test_aralik_disi_yil_400(self, client: APIClient) -> None:
        yanit = client.post(SEED_URL, {"year": 2101}, format="json")
        assert yanit.status_code == 400
        assert "2000 ile 2100 arasında" in yanit.json()["message"]
        assert not Holiday.objects.exists()
