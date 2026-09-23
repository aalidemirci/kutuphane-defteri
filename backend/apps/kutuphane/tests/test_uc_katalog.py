"""Katalog uçları: bölüm, eser ve nüsha (F2 sözleşmesi §4).

Kapsam: liste / oluştur / güncelle / sil, doğrulama hataları, SAYFALAMA (D9),
sunucu tarafı Türkçe ARAMA ve üç eksenli SIRALAMA (T7, D2), barkodun sayaçtan
gelmesi ve yeniden kullanılmaması.

Bütün veriler uydurmadır (CLAUDE.md §2-12). Testler varsayılan güvenlik
ortamında koşar (parola kurulu + kilit açık — `backend/conftest.py`); kapı
testleri `test_uc_kapilari.py`'dedir.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane.models import Copy, CopyStatus, ResourceType, Section, Work
from apps.kutuphane.pagination import KatalogSayfalama
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

BOLUMLER = "/api/v1/library/sections/"
ESERLER = "/api/v1/library/works/"
NUSHALAR = "/api/v1/library/copies/"
TOPLU_NUSHA = "/api/v1/library/copies/bulk/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


def _sonuclar(yanit: Any) -> list[dict[str, Any]]:
    """Sayfalı yanıtın satırları (biçim sözleşmesi ayrıca sınanır)."""
    govde: dict[str, Any] = yanit.json()
    return list(govde["results"])


def _adlar(yanit: Any) -> list[str]:
    return [satir["title"] for satir in _sonuclar(yanit)]


# ============================================================ Bölümler
class TestBolumUclari:
    def test_bolum_acilir_ve_listelenir(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            BOLUMLER,
            {"name": "Edebiyat", "dewey_from": "800", "dewey_to": "899", "sort_order": 2},
            format="json",
        )

        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["name"] == "Edebiyat"
        liste = istemci.get(BOLUMLER)
        assert liste.status_code == 200
        assert [satir["name"] for satir in _sonuclar(liste)] == ["Edebiyat"]

    def test_ayni_ad_turkce_katlamayla_reddedilir(self, istemci: APIClient) -> None:
        """Bölüm listesinin var olma sebebi budur: "Edebiyat" ve "EDEBİYAT" tek bölümdür."""
        ortak.bolum(name="Edebiyat")

        yanit = istemci.post(BOLUMLER, {"name": "  edebiyat "}, format="json")

        assert yanit.status_code == 400
        assert "name" in yanit.json()["fields"]
        assert Section.objects.count() == 1

    def test_bos_ad_reddedilir(self, istemci: APIClient) -> None:
        yanit = istemci.post(BOLUMLER, {"name": "   "}, format="json")

        assert yanit.status_code == 400
        assert "name" in yanit.json()["fields"]

    def test_noktalama_adli_bolum_ikinci_kez_acilinca_kisit_adi_basilmaz(
        self, istemci: APIClient
    ) -> None:
        """Yalnız noktalamadan oluşan ad ("!!!") katlamada boş dizeye iner.

        Denetim atlanırsa ikinci kayıt DB kısıtına düşer ve `full_clean` kısıtın
        ADINI kullanıcıya basar; sözlük (§2) iç kimliklerin kullanıcı metnine
        girmesini yasaklar. Hata ayrıca `name` ALANINDA gelmelidir, yoksa
        formda alan hatası dolmaz ve yalnız genel kırmızı bant görünür.
        """
        assert istemci.post(BOLUMLER, {"name": "!!!"}, format="json").status_code == 201

        yanit = istemci.post(BOLUMLER, {"name": "!!!"}, format="json")

        assert yanit.status_code == 400
        govde = yanit.json()
        assert "name" in govde["fields"]
        assert "uq_" not in json.dumps(govde, ensure_ascii=False)
        assert Section.objects.count() == 1

    def test_bolum_guncellenir_ve_kendi_adiyla_cakismaz(self, istemci: APIClient) -> None:
        bolum = ortak.bolum(name="Edebiyat")

        yanit = istemci.patch(
            f"{BOLUMLER}{bolum.pk}/", {"description": "Roman, şiir, deneme"}, format="json"
        )

        assert yanit.status_code == 200, yanit.json()
        assert yanit.json()["description"] == "Roman, şiir, deneme"

    def test_esere_bagli_bolum_silinemez(self, istemci: APIClient) -> None:
        bolum = ortak.bolum(name="Edebiyat")
        ortak.eser(section=bolum)

        yanit = istemci.delete(f"{BOLUMLER}{bolum.pk}/")

        assert yanit.status_code == 400
        assert Section.objects.filter(pk=bolum.pk).exists()

    def test_bos_bolum_silinir(self, istemci: APIClient) -> None:
        bolum = ortak.bolum(name="Edebiyat")

        assert istemci.delete(f"{BOLUMLER}{bolum.pk}/").status_code == 204
        assert not Section.objects.filter(pk=bolum.pk).exists()
        assert istemci.get(f"{BOLUMLER}{bolum.pk}/").status_code == 404


# ============================================================ Eserler
class TestEserUclari:
    def test_eser_acilir_yer_numarasi_turkce_buyuk_harfle_uretilir(
        self, istemci: APIClient
    ) -> None:
        """D11: çıplak `.upper()` 'İnce' soyadını 'INC' basardı."""
        yanit = istemci.post(
            ESERLER,
            {"title": "Deneme Kitabı", "authors": "Ayhan İnce", "classification_code": "814"},
            format="json",
        )

        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["call_number"] == "814 İNC"

    def test_bos_kaynak_adi_reddedilir(self, istemci: APIClient) -> None:
        yanit = istemci.post(ESERLER, {"title": "   "}, format="json")

        assert yanit.status_code == 400
        assert "title" in yanit.json()["fields"]

    def test_isbn10_cevrilir_uyari_bos_kalir(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            ESERLER, {"title": "Eski Baskı", "isbn": "0-306-40615-2"}, format="json"
        )

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert govde["isbn13"] == "9780306406157"
        assert govde["isbn_warning"] == ""

    def test_bozuk_saglama_kaydi_engellemez_uyari_doner(self, istemci: APIClient) -> None:
        """Saha verisi bozuk olabilir (F2 sözleşmesi §3): numara kaydedilir, uyarı verilir."""
        yanit = istemci.post(
            ESERLER, {"title": "Yanlış Numara", "isbn": "978-605-000-000-1"}, format="json"
        )

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert govde["isbn_warning"] != ""

    def test_isbn13_gonderilse_de_yazilmaz(self, istemci: APIClient) -> None:
        """Türetilmiş alan salt okunurdur: `Work.save()` her yazımda yeniden üretir."""
        yanit = istemci.post(
            ESERLER,
            {"title": "Türetilmiş Alan", "isbn": "0-306-40615-2", "isbn13": "1111111111111"},
            format="json",
        )

        assert yanit.json()["isbn13"] == "9780306406157"

    def test_eser_guncellenir_ve_siralama_anahtari_tazelenir(self, istemci: APIClient) -> None:
        eser = ortak.eser(title="Zeytin")
        ortak.eser(title="Çınar")

        istemci.patch(f"{ESERLER}{eser.pk}/", {"title": "Ahlat"}, format="json")

        assert _adlar(istemci.get(ESERLER)) == ["Ahlat", "Çınar"]

    def test_nushasi_olan_eser_e_kitaba_cevrilemez(self, istemci: APIClient) -> None:
        """Kural güncelleme yolundan da delinmez (`ensure_work_type_change`).

        Delinseydi kayıt defterinde e-kitabın nüshası olur, nüsha ödünç
        verilebilir görünür ve bir daha düzenlenemezdi.
        """
        eser = ortak.eser()
        copy = ortak.nusha(eser)

        yanit = istemci.patch(
            f"{ESERLER}{eser.pk}/", {"resource_type": ResourceType.EBOOK}, format="json"
        )

        assert yanit.status_code == 400, yanit.json()
        assert "resource_type" in yanit.json()["fields"]
        copy.refresh_from_db()
        assert istemci.patch(f"{NUSHALAR}{copy.pk}/", {}, format="json").status_code == 200

    def test_olmayacak_yayin_yili_reddedilir(self, istemci: APIClient) -> None:
        """Yazım hatası süzgeci: alan tipi 30000'i de kabul ediyordu."""
        yanit = istemci.post(ESERLER, {"title": "Yıl Hatası", "publish_year": 30000}, format="json")

        assert yanit.status_code == 400
        assert "publish_year" in yanit.json()["fields"]

    def test_nushasi_olan_eser_silinemez(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        ortak.nusha(eser)

        yanit = istemci.delete(f"{ESERLER}{eser.pk}/")

        assert yanit.status_code == 400
        assert Work.objects.filter(pk=eser.pk).exists()

    def test_nushasiz_eser_silinir_ve_listeden_duser(self, istemci: APIClient) -> None:
        eser = ortak.eser()

        assert istemci.delete(f"{ESERLER}{eser.pk}/").status_code == 204
        assert _sonuclar(istemci.get(ESERLER)) == []

    def test_nusha_sayaclari_yanittadir(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()
        ortak.nusha(eser, edinim)
        oduncteki = ortak.nusha(eser, edinim)
        Copy.objects.filter(pk=oduncteki.pk).update(status=CopyStatus.ON_LOAN)

        satir = _sonuclar(istemci.get(ESERLER))[0]

        assert satir["copy_count"] == 2
        assert satir["available_copy_count"] == 1
        # Ayrıntı ucunda da aynı sayaçlar (anotasyon oradan da gelir).
        assert istemci.get(f"{ESERLER}{eser.pk}/").json()["copy_count"] == 2


# ============================================================ Arama (T7, D2)
class TestArama:
    @pytest.mark.parametrize(
        ("baslik", "sorgu"),
        [
            ("ŞİİR SEÇKİSİ", "şiir"),
            ("Şiir Seçkisi", "ŞİİR"),
            ("Ilık Sular", "ılık"),
            ("ILIK SULAR", "ılık"),
            ("İnce Memed", "ince"),
            ("ince memed", "İnce"),
        ],
    )
    def test_buyuk_kucuk_harf_farki_aramada_erir(
        self, istemci: APIClient, baslik: str, sorgu: str
    ) -> None:
        ortak.eser(title=baslik)

        assert _adlar(istemci.get(ESERLER, {"q": sorgu})) == [baslik]

    def test_noktali_ve_noktasiz_i_ayri_kalir(self, istemci: APIClient) -> None:
        """'ılık' ile 'ilik' AYNI kelime değildir; katlama ASCII'ye inmez."""
        ortak.eser(title="Ilık Sular")

        assert _sonuclar(istemci.get(ESERLER, {"q": "ilik"})) == []

    def test_sozcukler_ayri_aranir_sira_gerekmez(self, istemci: APIClient) -> None:
        ortak.eser(title="Kürk Mantolu Madonna", authors="Sabahattin Ali")

        assert len(_sonuclar(istemci.get(ESERLER, {"q": "madonna kürk"}))) == 1

    def test_yazar_ve_konu_da_aranir(self, istemci: APIClient) -> None:
        ortak.eser(title="Adsız", authors="Ayşe Öztürk", subjects="Şiir")

        assert len(_sonuclar(istemci.get(ESERLER, {"q": "öztürk"}))) == 1
        assert len(_sonuclar(istemci.get(ESERLER, {"q": "şiir"}))) == 1

    def test_isbn_tireli_yazimla_da_bulunur(self, istemci: APIClient) -> None:
        ortak.eser(title="Numaralı", isbn="978-0-306-40615-7")

        assert len(_sonuclar(istemci.get(ESERLER, {"q": "9780306406157"}))) == 1


# ============================================================ Sıralama (Md. 11/1 üç ekseni)
class TestSiralama:
    def test_varsayilan_eksen_turk_alfabesi_sirasiyla_addir(self, istemci: APIClient) -> None:
        for baslik in ("Zeytin", "Çınar", "Şafak"):
            ortak.eser(title=baslik)

        assert _adlar(istemci.get(ESERLER)) == ["Çınar", "Şafak", "Zeytin"]
        # Ham `order_by("title")` (SQLite BINARY) bu sırayı VERMEZ — kapının anlamı bu.
        assert list(Work.objects.order_by("title").values_list("title", flat=True)) != [
            "Çınar",
            "Şafak",
            "Zeytin",
        ]

    def test_yazar_ekseni_soyada_gore_siralar(self, istemci: APIClient) -> None:
        ortak.eser(title="Bir", authors="Ayşe Zorlu")
        ortak.eser(title="İki", authors="Barış Çelik")
        ortak.eser(title="Üç", authors="Cem Şahin")

        assert _adlar(istemci.get(ESERLER, {"order": "author"})) == ["İki", "Üç", "Bir"]

    def test_konu_ekseni(self, istemci: APIClient) -> None:
        ortak.eser(title="Bir", subjects="Zooloji")
        ortak.eser(title="İki", subjects="Çevre")
        ortak.eser(title="Üç", subjects="Şiir")

        assert _adlar(istemci.get(ESERLER, {"order": "subject"})) == ["İki", "Üç", "Bir"]

    def test_en_yeni_ekseni(self, istemci: APIClient) -> None:
        ortak.eser(title="Önce")
        ortak.eser(title="Sonra")

        assert _adlar(istemci.get(ESERLER, {"order": "newest"})) == ["Sonra", "Önce"]

    def test_taninmayan_eksen_sessizce_varsayilana_dusmez(self, istemci: APIClient) -> None:
        """Sessiz düşüş kullanıcıya "istediğim sıra bu" dedirtir; süzgeç hatalıdır."""
        yanit = istemci.get(ESERLER, {"order": "yazarin-boyu"})

        assert yanit.status_code == 400
        assert "order" in yanit.json()["fields"]


# ============================================================ Süzgeçler ve sayfalama (D9)
class TestSuzgecVeSayfalama:
    def test_bolum_ve_kaynak_turu_suzgeci(self, istemci: APIClient) -> None:
        bolum = ortak.bolum(name="Edebiyat")
        ortak.eser(title="Bölümlü", section=bolum)
        ortak.eser(title="Bölümsüz")
        ortak.eser(title="Dijital", resource_type=ResourceType.EBOOK)

        assert _adlar(istemci.get(ESERLER, {"section": bolum.pk})) == ["Bölümlü"]
        assert _adlar(istemci.get(ESERLER, {"resource_type": ResourceType.EBOOK})) == ["Dijital"]

    def test_sayisal_olmayan_bolum_suzgeci_400(self, istemci: APIClient) -> None:
        yanit = istemci.get(ESERLER, {"section": "edebiyat"})

        assert yanit.status_code == 400
        assert "section" in yanit.json()["fields"]

    def test_taninmayan_kaynak_turu_400(self, istemci: APIClient) -> None:
        yanit = istemci.get(ESERLER, {"resource_type": "KASET"})

        assert yanit.status_code == 400
        assert "resource_type" in yanit.json()["fields"]

    def test_liste_sayfalidir_ve_toplam_sayiyi_verir(self, istemci: APIClient) -> None:
        for sira in range(30):
            ortak.eser(title=f"Kitap {sira:02d}")

        govde = istemci.get(ESERLER).json()

        assert govde["count"] == 30
        assert len(govde["results"]) == KatalogSayfalama.default_limit
        assert govde["next"] is not None
        assert govde["previous"] is None

    def test_sayfalar_kesismez_ve_kararlidir(self, istemci: APIClient) -> None:
        """Kararlı sıra (her eksen `pk` ile biter): 2. sayfa 1. sayfayı tekrarlamaz."""
        for _sira in range(12):
            ortak.eser(title="Aynı Ad")

        ilk = istemci.get(ESERLER, {"limit": 6, "offset": 0}).json()["results"]
        ikinci = istemci.get(ESERLER, {"limit": 6, "offset": 6}).json()["results"]

        kimlikler = [satir["id"] for satir in [*ilk, *ikinci]]
        assert len(set(kimlikler)) == 12

    def test_sayfa_boyutunun_ust_siniri_vardir(self) -> None:
        """Sınırsız `limit` bütün kataloğu tek yanıtta serileştirmeye kalkardı."""
        istek = Request(APIRequestFactory().get("/", {"limit": "5000"}))

        assert KatalogSayfalama().get_limit(istek) == KatalogSayfalama.max_limit


# ============================================================ Nüshalar
class TestNushaUclari:
    def test_nusha_acilir_numara_sayactan_gelir(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()

        yanit = istemci.post(NUSHALAR, {"work": eser.pk, "acquisition": edinim.pk}, format="json")

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert len(govde["barcode"]) == barcode_module.BARCODE_LENGTH
        assert govde["barcode_display"] == barcode_module.format_barcode(govde["barcode"])
        assert govde["accession_no"] == int(govde["barcode"])
        assert govde["status"] == CopyStatus.AVAILABLE
        assert govde["is_loanable"] is True
        assert govde["not_loanable_reason"] == ""

    def test_govdedeki_barkod_ve_durum_yok_sayilir(self, istemci: APIClient) -> None:
        """Kimlik ve durum salt okunurdur; gövdeyle gelen değer kaydı yönlendirmez."""
        eser = ortak.eser()
        edinim = ortak.edinim()

        govde = istemci.post(
            NUSHALAR,
            {
                "work": eser.pk,
                "acquisition": edinim.pk,
                "barcode": "9999999999",
                "accession_no": 9999999999,
                "status": CopyStatus.LOST,
            },
            format="json",
        ).json()

        assert govde["barcode"] != "9999999999"
        assert govde["status"] == CopyStatus.AVAILABLE

    def test_dijital_kaynakta_nusha_acilmaz(self, istemci: APIClient) -> None:
        eser = ortak.eser(title="E-Kitap", resource_type=ResourceType.EBOOK)
        edinim = ortak.edinim()

        yanit = istemci.post(NUSHALAR, {"work": eser.pk, "acquisition": edinim.pk}, format="json")

        assert yanit.status_code == 400
        assert "work" in yanit.json()["fields"]

    def test_ciltsiz_sureli_yayinda_nusha_acilmaz(self, istemci: APIClient) -> None:
        eser = ortak.eser(title="Dergi", resource_type=ResourceType.PERIODICAL)
        edinim = ortak.edinim()

        yanit = istemci.post(NUSHALAR, {"work": eser.pk, "acquisition": edinim.pk}, format="json")

        assert yanit.status_code == 400
        assert "is_bound_periodical" in yanit.json()["fields"]

    def test_olmayan_eser_turkce_reddedilir(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            NUSHALAR, {"work": 9999, "acquisition": ortak.edinim().pk}, format="json"
        )

        assert yanit.status_code == 400
        assert yanit.json()["fields"]["work"] == ["Seçilen eser bulunamadı."]

    def test_toplu_nusha_her_biri_ayri_numara_alir(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()

        yanit = istemci.post(
            TOPLU_NUSHA,
            {"work": eser.pk, "acquisition": edinim.pk, "count": 3},
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 201, govde
        assert govde["count"] == 3
        assert len({satir["barcode"] for satir in govde["results"]}) == 3

    def test_toplu_nushada_eski_kayit_no_tek_nushaya_aittir(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()

        yanit = istemci.post(
            TOPLU_NUSHA,
            {"work": eser.pk, "acquisition": edinim.pk, "count": 2, "old_register_no": "A-17"},
            format="json",
        )

        assert yanit.status_code == 400
        assert "old_register_no" in yanit.json()["fields"]
        assert Copy.objects.count() == 0

    def test_nusha_guncellenir_ama_eser_ve_edinim_degismez(self, istemci: APIClient) -> None:
        nusha = ortak.nusha()
        baska_eser = ortak.eser(title="Başka Eser")
        bolum = ortak.bolum(name="Edebiyat")

        yanit = istemci.patch(
            f"{NUSHALAR}{nusha.pk}/",
            {"section": bolum.pk, "is_reference": True, "work": baska_eser.pk},
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 200, govde
        assert govde["section"] == bolum.pk
        assert govde["work"] == nusha.work_id
        assert govde["is_loanable"] is False
        assert govde["not_loanable_reason"] == "Ödünç verilmez — kütüphanede okunur."

    def test_put_ile_de_guncellenir(self, istemci: APIClient) -> None:
        """Tam gövdeli PUT: kimlik alanları gönderilmediği için zorunlu da değildir."""
        nusha = ortak.nusha()

        yanit = istemci.put(
            f"{NUSHALAR}{nusha.pk}/",
            {"external_asset_ref": "TKYS-4412", "old_register_no": "A-17"},
            format="json",
        )

        govde = yanit.json()
        assert yanit.status_code == 200, govde
        assert govde["external_asset_ref"] == "TKYS-4412"
        assert govde["old_register_no"] == "A-17"
        assert govde["barcode"] == nusha.barcode

    def test_nusha_silinir_ama_numarasi_yeniden_kullanilmaz(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()
        ilk = ortak.nusha(eser, edinim)

        assert istemci.delete(f"{NUSHALAR}{ilk.pk}/").status_code == 204

        yeni = istemci.post(
            NUSHALAR, {"work": eser.pk, "acquisition": edinim.pk}, format="json"
        ).json()
        assert yeni["barcode"] != ilk.barcode
        # Silinen nüsha listeden düşer; numarası hâlâ DB'de "kullanılmış"tır.
        assert [satir["id"] for satir in _sonuclar(istemci.get(NUSHALAR))] == [yeni["id"]]
        assert Copy.all_objects.filter(barcode=ilk.barcode).exists()

    def test_disaridaki_nusha_silinemez(self, istemci: APIClient) -> None:
        nusha = ortak.nusha()
        Copy.objects.filter(pk=nusha.pk).update(status=CopyStatus.ON_LOAN)

        yanit = istemci.delete(f"{NUSHALAR}{nusha.pk}/")

        assert yanit.status_code == 400
        assert "status" in yanit.json()["fields"]
        assert Copy.objects.filter(pk=nusha.pk).exists()

    def test_kayittan_dusulmus_nusha_silinemez(self, istemci: APIClient) -> None:
        nusha = ortak.nusha()
        Copy.objects.filter(pk=nusha.pk).update(status=CopyStatus.WITHDRAWN_WEEDED)

        assert istemci.delete(f"{NUSHALAR}{nusha.pk}/").status_code == 400

    def test_barkodla_tam_eslesme(self, istemci: APIClient) -> None:
        nusha = ortak.nusha()
        ortak.nusha()

        basili = barcode_module.format_barcode(nusha.barcode)
        assert [satir["id"] for satir in _sonuclar(istemci.get(NUSHALAR, {"barcode": basili}))] == [
            nusha.pk
        ]
        # Kısmi eşleşme YOK: masada yanlış kitabı getirirdi.
        assert _sonuclar(istemci.get(NUSHALAR, {"barcode": nusha.barcode[:6]})) == []

    def test_eski_kayit_no_ile_arama_liste_dondurur(self, istemci: APIClient) -> None:
        ortak.nusha(old_register_no="A-17")
        ortak.nusha(old_register_no="A-17")
        ortak.nusha(old_register_no="B-2")

        assert len(_sonuclar(istemci.get(NUSHALAR, {"old_register_no": "A-17"}))) == 2

    def test_eser_durum_ve_odunclenebilirlik_suzgecleri(self, istemci: APIClient) -> None:
        eser = ortak.eser()
        edinim = ortak.edinim()
        rafta = ortak.nusha(eser, edinim)
        danisma = ortak.nusha(eser, edinim, is_reference=True)

        assert len(_sonuclar(istemci.get(NUSHALAR, {"work": eser.pk}))) == 2
        odunclenebilir = _sonuclar(istemci.get(NUSHALAR, {"only_loanable": "true"}))
        assert [satir["id"] for satir in odunclenebilir] == [rafta.pk]
        assert danisma.pk not in [satir["id"] for satir in odunclenebilir]

    def test_taninmayan_durum_suzgeci_400(self, istemci: APIClient) -> None:
        yanit = istemci.get(NUSHALAR, {"status": "RAFTA"})

        assert yanit.status_code == 400
        assert "status" in yanit.json()["fields"]
