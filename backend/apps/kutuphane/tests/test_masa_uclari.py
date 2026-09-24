"""Dolaşım masası uçları — tasarım §7.3 durum tablosu, HER SATIR AYRI SINIF (§14.1 F6).

| Durum | Girdi | Sonuç | Sınıf |
|---|---|---|---|
| Boş | kart | üye bağlamı: ad + kalan hak (sınıf yok) | `TestBosKart` |
| Boş | kitap | açık ödünçteyse iade; değilse durum iletisi | `TestBosKitap` |
| ÜYE | kitap | ödünç verilebilirse ödünç; değilse kişisel olmayan sebep | `TestUyeKitap` |
| ÜYE | kitap başka üyede | "Bu kitap başka bir üyede." (görevli: iade + ödünç) | `TestUyeKitapBaskaUyede` |
| ÜYE | 60 sn · "Bitti" · başka kart | bağlam kapanır | ön yüz: `DolasimMasasi.test.tsx` |
| Her durum | iptal kart | "İptal edilmiş kart — …" | `TestIptalKart` |
| Her durum | tanınmayan / ISBN | özel ileti (§7.1, F4 türleri) | `TestTaninmayanVeIsbn` |

Ayrıca: nüsha durum sorgusu, kartsız ödünç (yönetici), D9 (26. ödünç barkodla iade).
GA-7 `test_masa_kart_kilidi.py`'de, görevli yanıtlarının alan listesi anlık görüntüsü
`test_masa_gorevli_yuzeyi.py`'dedir. Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane import barcode as barcode_module
from apps.kutuphane import card_numbers, views_masa
from apps.kutuphane.models import (
    CopyStatus,
    Loan,
    LoanStatus,
    Membership,
    TerminationReason,
    card_no_blind_index,
)
from apps.kutuphane.selectors_dolasim import REVOKED_CARD_MESSAGE
from apps.kutuphane.services import barcode_reservations, masa, memberships
from apps.kutuphane.services.circulation import (
    COPY_WITH_OTHER_MEMBER_MESSAGE,
    COPY_WITH_THIS_MEMBER_MESSAGE,
    MEMBERSHIP_ENDED_MESSAGE,
    OVERDUE_ADMIN_MESSAGE,
    OVERDUE_STAFF_MESSAGE,
    RED_BASKA_UYEDE,
    RED_BU_UYEDE,
    RED_GECIKME,
    RED_NUSHA_YOK,
    RED_ODUNC_VERILMEZ,
    RED_SINIR,
    RED_UYELIK,
)
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    uye,
)
from apps.kutuphane.tests.ortak import eser, nusha
from apps.okul.kip import KIP
from apps.okul.services import calendar, persons

pytestmark = pytest.mark.django_db

KART = "/api/v1/library/desk/member/"
ODUNC = "/api/v1/library/checkout/"
IADE = "/api/v1/library/return/"
DURUM = "/api/v1/library/desk/copy-status/"

#: Uydurma üye adı ve okul no'su — görevli yanıtlarında geçmemesi sınanır.
AD, SOYAD, OKUL_NO = "Uydurmaad", "Masadaki", "700777"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def gorevli() -> None:
    KIP.gorevliye_gec()


def _uye(**alanlar: Any) -> Membership:
    alanlar.setdefault("first_name", AD)
    alanlar.setdefault("last_name", SOYAD)
    alanlar.setdefault("student_number", OKUL_NO)
    return uye(ogrenci(**alanlar))


def _kart(client: APIClient, kod: str) -> Any:
    return client.post(KART, {"card_no": kod}, format="json")


def _odunc(client: APIClient, kart: str, barkod: str, **ek: Any) -> Any:
    return client.post(ODUNC, {"card_no": kart, "barcode": barkod, **ek}, format="json")


def _iade(client: APIClient, barkod: str) -> Any:
    return client.post(IADE, {"barcode": barkod}, format="json")


def _hic_verilmemis_kart() -> str:
    """Sağlaması tutan ama hiç verilmemiş bir kart no (uydurma)."""
    for govde in range(100000, 999999):
        aday = card_numbers.build_card_no(f"{govde:06d}")
        if not Membership.objects.filter(card_no_index=card_no_blind_index(aday)).exists():
            return aday
    raise AssertionError("verilmemiş kart no bulunamadı")


def _hatali_kart(gecerli: str) -> str:
    """Sağlama hanesi bozulmuş kart no."""
    son = (int(gecerli[-1]) + 1) % 10
    return f"{gecerli[:-1]}{son}"


# ============================================================ Boş | kart
class TestBosKart:
    def test_gorevli_kipinde_yalniz_ad_ve_kalan_hak_doner_sinif_yok(
        self, client: APIClient, gorevli: None
    ) -> None:
        uyelik = _uye()
        odunc_ver(uyelik)

        yanit = _kart(client, uyelik.card_no)

        assert yanit.status_code == 200
        assert yanit.json() == {
            "state": "FOUND",
            "message": "Kitabın kütüphane etiketini okutun.",
            "member": {"full_name": f"{AD} {SOYAD}", "remaining_quota": 2},
        }
        metin = yanit.content.decode()
        assert "9/A" not in metin and OKUL_NO not in metin
        assert str(uyelik.pk) not in yanit.json()["member"].values()

    def test_yonetici_kipinde_uye_baglami_sinif_ve_acik_odunclerle(self, client: APIClient) -> None:
        uyelik = _uye()
        loan = odunc_ver(uyelik)

        govde = _kart(client, uyelik.card_no).json()

        uye_bilgisi = govde["member"]
        assert govde["state"] == "FOUND"
        assert uye_bilgisi["membership_id"] == uyelik.pk
        assert uye_bilgisi["class_label"] == "9/A"
        assert uye_bilgisi["member_type_display"] == "öğrenci"
        assert (uye_bilgisi["loan_limit"], uye_bilgisi["remaining_quota"]) == (3, 2)
        assert [s["id"] for s in uye_bilgisi["open_loans"]] == [loan.pk]
        assert uye_bilgisi["open_loans"][0]["barcode_display"] == barcode_module.format_barcode(
            loan.copy.barcode
        )

    def test_kart_no_basili_bicim_ve_bosluklarla_da_cozulur(self, client: APIClient) -> None:
        uyelik = _uye()
        kod = f" {uyelik.card_no[:4]}-{uyelik.card_no[4:]} "
        assert _kart(client, kod).json()["state"] == "FOUND"

    def test_sonlanmis_uyelik_bildirilir_kalan_hak_sifir(self, client: APIClient) -> None:
        uyelik = _uye()
        memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)
        KIP.gorevliye_gec()

        govde = _kart(client, uyelik.card_no).json()

        assert govde["message"] == MEMBERSHIP_ENDED_MESSAGE
        assert govde["member"]["remaining_quota"] == 0

    def test_kart_no_ve_uyelik_birlikte_ya_da_hic_gonderilmez(self, client: APIClient) -> None:
        uyelik = _uye()
        assert client.post(KART, {}, format="json").status_code == 400
        yanit = client.post(
            KART, {"card_no": uyelik.card_no, "membership_id": uyelik.pk}, format="json"
        )
        assert yanit.status_code == 400

    def test_yonetici_uyelik_kaydiyla_uye_acar_gorevli_acamaz(self, client: APIClient) -> None:
        """Kartsız ödünç için okul no ya da adla bulunan üye (U12) — yalnız yönetici."""
        uyelik = _uye()
        govde = client.post(KART, {"membership_id": uyelik.pk}, format="json").json()
        assert govde["member"]["membership_id"] == uyelik.pk

        KIP.gorevliye_gec()
        yanit = client.post(KART, {"membership_id": uyelik.pk}, format="json")
        assert yanit.status_code == 403
        assert yanit.json()["code"] == "kip_yetkisiz"

    def test_kart_no_url_de_tasinmaz(self, client: APIClient) -> None:
        """Kart okutma POST gövdesiyle yapılır; GET yöntemi yoktur."""
        uyelik = _uye()
        assert client.get(KART, {"card_no": uyelik.card_no}).status_code == 405


# ============================================================ Boş | kitap
class TestBosKitap:
    def test_acik_odunctaki_kitap_okutulunca_iade_alinir(
        self, client: APIClient, gorevli: None
    ) -> None:
        loan = odunc_ver(_uye())

        yanit = _iade(client, loan.copy.barcode)

        assert yanit.status_code == 200
        govde = yanit.json()
        assert govde["result"] == "returned"
        assert govde["message"] == "İade alındı."
        assert govde["copy"]["work_title"] == "Deneme Eseri"
        loan.refresh_from_db()
        assert loan.status == LoanStatus.RETURNED
        assert loan.copy.status == CopyStatus.AVAILABLE

    def test_gorevli_iadede_odunc_alanin_kimligini_ve_gecikmeyi_gormez(
        self, client: APIClient, gorevli: None
    ) -> None:
        loan = gecikmeli_yap(odunc_ver(_uye()), gun=7)

        yanit = _iade(client, loan.copy.barcode)

        govde = yanit.json()
        assert set(govde) == {"result", "kind", "message", "copy"}
        assert govde["message"] == "İade alındı."
        metin = yanit.content.decode()
        assert AD not in metin and SOYAD not in metin and OKUL_NO not in metin
        assert "gecikti" not in metin

    def test_yonetici_iadede_odunc_alan_ve_gecikme_gorunur(self, client: APIClient) -> None:
        loan = gecikmeli_yap(odunc_ver(_uye()), gun=7)

        govde = _iade(client, loan.copy.barcode).json()

        assert govde["message"] == "İade alındı. 7 gün gecikti."
        assert govde["loan"]["member_name"] == f"{AD} {SOYAD}"
        assert govde["loan"]["overdue_days"] == 7

    @pytest.mark.parametrize(
        ("durum", "ileti"),
        [
            (CopyStatus.AVAILABLE, "Rafta — ödünç değil."),
            (CopyStatus.LOST, "Kayıp kaydında."),
            (CopyStatus.IN_REPAIR, "Onarımda."),
            (CopyStatus.DELIVERED, "Sınıf kitaplığında."),
        ],
    )
    def test_oduncte_olmayan_kitapta_durum_iletisi_yazma_yok(
        self, client: APIClient, gorevli: None, durum: str, ileti: str
    ) -> None:
        copy = odunc_nushasi()
        copy.__class__.objects.filter(pk=copy.pk).update(status=durum)

        govde = _iade(client, copy.barcode).json()

        assert (govde["result"], govde["message"]) == ("not_on_loan", ileti)
        assert govde["copy"]["barcode"] == copy.barcode
        copy.refresh_from_db()
        assert copy.status == durum
        assert not Loan.objects.exists()

    def test_sonlanmis_uyenin_kitabi_iade_edilir(self, client: APIClient) -> None:
        """§9-8: sonlanmış üye iade yapabilir; iade hiçbir durumda kilitlenmez."""
        uyelik = _uye()
        loan = odunc_ver(uyelik)
        # Açık ödüncü olan üyelik elle sonlandırılamaz; ayrılışta kancayla sonlanır.
        Membership.objects.filter(pk=uyelik.pk).update(
            status="TERMINATED",
            terminated_at=date(2026, 9, 1),
            termination_reason=TerminationReason.LEFT_SCHOOL,
        )
        KIP.gorevliye_gec()

        assert _iade(client, loan.copy.barcode).json()["result"] == "returned"

    def test_yirmi_altinci_odunc_de_barkodla_iade_edilir(
        self, client: APIClient, gorevli: None
    ) -> None:
        """D9: OYS listede ilk 25 ödüncü gösterdiği için 26. iade edilemiyordu."""
        loans = [odunc_ver(uye()) for _ in range(27)]
        KIP.gorevliye_gec()

        govde = _iade(client, loans[25].copy.barcode).json()

        assert govde["result"] == "returned"
        assert Loan.objects.get(pk=loans[25].pk).status == LoanStatus.RETURNED
        assert Loan.objects.filter(status=LoanStatus.OPEN).count() == 26


# ============================================================ ÜYE | kitap
class TestUyeKitap:
    def test_gorevli_kipinde_odunc_verilir_yanit_daralir(
        self, client: APIClient, gorevli: None, bugun: list[date]
    ) -> None:
        uyelik = _uye()
        copy = odunc_nushasi(title="Masa Kitabı")
        calendar.seed_holidays(2026)  # kapalı günler eksik olsaydı uyarı dönerdi

        yanit = _odunc(client, uyelik.card_no, copy.barcode)

        assert yanit.status_code == 201, yanit.json()
        govde = yanit.json()
        assert govde == {
            "message": "Ödünç verildi.",
            "copy": {
                "barcode": copy.barcode,
                "barcode_display": barcode_module.format_barcode(copy.barcode),
                "work_title": "Masa Kitabı",
            },
            "due_date": "2026-10-09",
            "warnings": [],
            "member": {"full_name": f"{AD} {SOYAD}", "remaining_quota": 2},
        }
        loan = Loan.objects.get()
        assert (loan.membership_id, loan.copy_id, loan.cardless) == (uyelik.pk, copy.pk, False)

    def test_yonetici_kipinde_odunc_yaniti_ayrintili(self, client: APIClient) -> None:
        uyelik = _uye()
        copy = odunc_nushasi()

        govde = _odunc(client, uyelik.card_no, copy.barcode).json()

        assert govde["loan_id"] == Loan.objects.get().pk
        assert govde["member"]["open_loan_count"] == 1
        assert govde["copy"]["status"] == CopyStatus.ON_LOAN
        assert govde["cardless"] is False and govde["has_override"] is False

    def test_odunc_verilmez_kaynakta_kisisel_olmayan_sebep(
        self, client: APIClient, gorevli: None
    ) -> None:
        uyelik = _uye()
        copy = nusha(eser(title="Büyük Sözlük"), is_reference=True)

        yanit = _odunc(client, uyelik.card_no, copy.barcode)

        assert yanit.status_code == 400
        assert yanit.json()["code"] == RED_ODUNC_VERILMEZ
        assert yanit.json()["message"] == "Ödünç verilmez — kütüphanede okunur."

    def test_sinir_dolu_kisisel_olmayan_sebep(self, client: APIClient, gorevli: None) -> None:
        uyelik = _uye()
        for _ in range(3):
            odunc_ver(uyelik)
        KIP.gorevliye_gec()

        yanit = _odunc(client, uyelik.card_no, odunc_nushasi().barcode)

        assert yanit.status_code == 400
        assert yanit.json()["code"] == RED_SINIR
        assert yanit.json()["message"] == "Ödünç sınırı dolu (en çok 3 kitap)."

    def test_gecikmesi_olan_uyede_gorevli_yalniz_yonlendirme_gorur(self, client: APIClient) -> None:
        """§4.4: eser adı ve gecikme günü YOK."""
        uyelik = _uye()
        geciken = gecikmeli_yap(odunc_ver(uyelik, odunc_nushasi(title="Geciken Eser")), gun=9)
        KIP.gorevliye_gec()

        yanit = _odunc(client, uyelik.card_no, odunc_nushasi().barcode)

        assert yanit.status_code == 400
        assert yanit.json() == {"code": RED_GECIKME, "message": OVERDUE_STAFF_MESSAGE, "fields": {}}
        metin = yanit.content.decode()
        assert "Geciken Eser" not in metin and "9" not in metin
        assert geciken.copy.barcode not in metin

    def test_yonetici_kipinde_gecikme_reddi_istisnayi_onerir_ve_gerekceyle_verir(
        self, client: APIClient
    ) -> None:
        uyelik = _uye()
        gecikmeli_yap(odunc_ver(uyelik))
        copy = odunc_nushasi()

        ret = _odunc(client, uyelik.card_no, copy.barcode)
        assert ret.json()["code"] == RED_GECIKME
        assert ret.json()["message"] == OVERDUE_ADMIN_MESSAGE

        yanit = _odunc(
            client,
            uyelik.card_no,
            copy.barcode,
            override_reason="COURSE_NEED",
            override_note="Ödev için gerekli.",
        )
        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["has_override"] is True
        assert yanit.json()["override_reason_display"] == "Ders ya da ödev için gerekli"

    def test_gorevli_kipinde_istisnali_ve_kartsiz_istek_403(
        self, client: APIClient, gorevli: None
    ) -> None:
        """Ara katmanın parametre kuralı: alan VARSA (boş bile olsa) 403 (§5.10-8)."""
        uyelik = _uye()
        copy = odunc_nushasi()
        for ek in (
            {"override_reason": "COURSE_NEED", "override_note": "x"},
            {"override_reason": ""},
            {"cardless_reason": "CARD_LOST"},
            {"cardless": True},
        ):
            yanit = _odunc(client, uyelik.card_no, copy.barcode, **ek)
            assert yanit.status_code == 403, ek
            assert yanit.json()["code"] == "kip_yetkisiz"
        yanit = client.post(
            ODUNC,
            {"membership_id": uyelik.pk, "barcode": copy.barcode, "cardless_reason": "CARD_LOST"},
            format="json",
        )
        assert yanit.status_code == 403
        assert not Loan.objects.exists()

    def test_sonlanmis_uyelige_odunc_verilmez(self, client: APIClient) -> None:
        uyelik = _uye()
        memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)

        yanit = _odunc(client, uyelik.card_no, odunc_nushasi().barcode)

        assert yanit.status_code == 400
        assert yanit.json()["code"] == RED_UYELIK


# ============================================================ ÜYE | kitap başka üyede
class TestUyeKitapBaskaUyede:
    def test_baska_uyedeki_kitapta_kod_ve_kisisel_olmayan_ileti(
        self, client: APIClient, gorevli: None
    ) -> None:
        oteki = uye(ogrenci(first_name="Başkası", last_name="Uydurma"))
        loan = odunc_ver(oteki)
        uyelik = _uye()
        KIP.gorevliye_gec()

        yanit = _odunc(client, uyelik.card_no, loan.copy.barcode)

        assert yanit.status_code == 400
        assert yanit.json()["code"] == RED_BASKA_UYEDE
        assert yanit.json()["message"] == COPY_WITH_OTHER_MEMBER_MESSAGE
        assert "Başkası" not in yanit.content.decode()

    def test_gorevli_once_iade_alir_sonra_odunc_verir(
        self, client: APIClient, gorevli: None
    ) -> None:
        """§7.3: "Önce iade alınsın mı?" — görevli: iade + uyarı, ardından ödünç."""
        eski = odunc_ver(uye())
        uyelik = _uye()
        KIP.gorevliye_gec()

        assert _iade(client, eski.copy.barcode).json()["result"] == "returned"
        yanit = _odunc(client, uyelik.card_no, eski.copy.barcode)

        assert yanit.status_code == 201
        acik = Loan.objects.get(status=LoanStatus.OPEN)
        assert acik.membership_id == uyelik.pk

    def test_kitap_zaten_bu_uyede(self, client: APIClient, gorevli: None) -> None:
        uyelik = _uye()
        loan = odunc_ver(uyelik)
        KIP.gorevliye_gec()

        yanit = _odunc(client, uyelik.card_no, loan.copy.barcode)

        assert yanit.json()["code"] == RED_BU_UYEDE
        assert yanit.json()["message"] == COPY_WITH_THIS_MEMBER_MESSAGE


# ============================================================ Her durum | iptal kart
class TestIptalKart:
    def test_iptal_edilmis_kart_okutulunca_ileti(self, client: APIClient) -> None:
        uyelik = _uye()
        eski = uyelik.card_no
        memberships.renew_card(uyelik)
        KIP.gorevliye_gec()

        govde = _kart(client, eski).json()

        assert govde == {"state": "REVOKED", "message": REVOKED_CARD_MESSAGE, "member": None}
        assert REVOKED_CARD_MESSAGE == "İptal edilmiş kart — kütüphane yöneticisine yönlendirin."

    def test_iptal_edilmis_kartla_odunc_verilmez(self, client: APIClient) -> None:
        uyelik = _uye()
        eski = uyelik.card_no
        memberships.renew_card(uyelik)
        KIP.gorevliye_gec()

        yanit = _odunc(client, eski, odunc_nushasi().barcode)

        assert yanit.status_code == 400
        assert yanit.json()["code"] == masa.RED_KART_IPTAL
        assert yanit.json()["message"] == REVOKED_CARD_MESSAGE
        assert not Loan.objects.exists()

    def test_birlestirmede_iptal_edilen_kaynak_kart_iptal_diye_okunur(
        self, client: APIClient
    ) -> None:
        """Kaynak üyelik numarasını korur ama kartı iptaldir: "Üyelik sonlanmış" denmez."""
        kaynak = personel(last_name="Eskisoyad")
        hedef = personel(last_name="Yenisoyad")
        kaynak_uyelik = uye(kaynak)
        uye(hedef)
        eski_kart = kaynak_uyelik.card_no
        persons.merge_personnel(kaynak, hedef)
        KIP.gorevliye_gec()

        govde = _kart(client, eski_kart).json()
        odunc = _odunc(client, eski_kart, odunc_nushasi().barcode)

        assert govde == {"state": "REVOKED", "message": REVOKED_CARD_MESSAGE, "member": None}
        assert odunc.json()["code"] == masa.RED_KART_IPTAL
        assert not Loan.objects.exists()

    def test_yeni_kartla_acik_odunc_ayni_uyelikte_gorulur(self, client: APIClient) -> None:
        uyelik = _uye()
        odunc_ver(uyelik)
        yeni = memberships.renew_card(uyelik)

        govde = _kart(client, yeni.card_no).json()

        assert govde["member"]["open_loan_count"] == 1


# ============================================================ Her durum | tanınmayan / ISBN
class TestTaninmayanVeIsbn:
    def test_isbn_barkodu_okutulunca_ozel_ileti(self, client: APIClient, gorevli: None) -> None:
        govde = _iade(client, "9789750812345").json()
        assert govde == {
            "result": "rejected",
            "kind": "ISBN",
            "message": "Bu ISBN barkodu. Kitabın kütüphane etiketini okutun.",
            "copy": None,
        }

    def test_uye_baglaminda_isbn_barkodu_reddedilir(self, client: APIClient, gorevli: None) -> None:
        uyelik = _uye()
        yanit = _odunc(client, uyelik.card_no, "978-975-08-1234-5")
        assert yanit.status_code == 400
        assert yanit.json()["code"] == masa.RED_GECERSIZ_KOD
        assert yanit.json()["message"] == barcode_module.ISBN_SCAN_MESSAGE

    def test_tanimayan_kod(self, client: APIClient, gorevli: None) -> None:
        govde = _iade(client, "12345").json()
        assert (govde["result"], govde["kind"]) == ("rejected", "UNKNOWN")
        assert govde["message"] == masa.SCAN_UNKNOWN_MESSAGE

    def test_kitap_yerine_uye_karti(self, client: APIClient, gorevli: None) -> None:
        uyelik = _uye()
        govde = _iade(client, uyelik.card_no).json()
        assert govde["kind"] == "MEMBER_CARD"
        assert govde["message"] == masa.SCAN_MEMBER_CARD_MESSAGE

    def test_kayitli_olmayan_barkod(self, client: APIClient, gorevli: None) -> None:
        govde = _iade(client, "2026999999").json()
        assert govde["message"] == masa.SCAN_NO_COPY_MESSAGE
        yanit = _odunc(client, _uye().card_no, "2026999999")
        assert yanit.json()["code"] == RED_NUSHA_YOK

    def test_silinmis_nushanin_barkodu(self, client: APIClient, gorevli: None) -> None:
        copy = odunc_nushasi()
        copy.__class__.objects.filter(pk=copy.pk).update(deleted_at="2026-09-01T10:00:00+03:00")
        assert _iade(client, copy.barcode).json()["message"] == masa.SCAN_DELETED_MESSAGE

    def test_tanimayan_kart_ve_hatali_kart_no(self, client: APIClient, gorevli: None) -> None:
        verilmemis = _hic_verilmemis_kart()
        assert _kart(client, verilmemis).json() == {
            "state": "UNKNOWN",
            "message": "Bu kart tanınmadı — kütüphane yöneticisine yönlendirin.",
            "member": None,
        }
        hatali = _hatali_kart(verilmemis)
        assert _kart(client, hatali).json()["state"] == "INVALID"
        assert _kart(client, hatali).json()["message"] == masa.CARD_INVALID_MESSAGE

    @pytest.mark.parametrize("kip", ["gorevli", "yonetici"])
    def test_bos_barkod_etiketi_baglanmamis_ve_iptal(self, client: APIClient, kip: str) -> None:
        acik = barcode_reservations.reserve(1).first_barcode
        iptal_araligi = barcode_reservations.reserve(1)
        barcode_reservations.cancel_numbers(iptal_araligi)
        if kip == "gorevli":
            KIP.gorevliye_gec()

        bagli_degil = _iade(client, acik).json()
        iptal = _iade(client, iptal_araligi.first_barcode).json()

        assert (bagli_degil["kind"], iptal["kind"]) == ("RESERVED", "CANCELLED")
        assert bagli_degil["message"].startswith("Bu etiket henüz bir kitaba bağlanmadı.")
        assert iptal["message"].startswith("Bu etiketin numarası iptal edildi")
        yonlendirme = "kütüphane yöneticisine gösterin" in bagli_degil["message"]
        assert yonlendirme is (kip == "gorevli")


# ============================================================ nüsha durum sorgusu
class TestNushaDurumu:
    def test_gorevli_durum_sorgusunda_odunc_kimde_gormez(
        self, client: APIClient, gorevli: None
    ) -> None:
        loan = odunc_ver(_uye())
        KIP.gorevliye_gec()

        govde = client.get(DURUM, {"barcode": loan.copy.barcode}).json()

        assert set(govde) == {"kind", "message", "copy"}
        assert govde["message"] == "Ödünçte."
        assert govde["copy"]["status_display"] == "Ödünçte"
        assert AD not in str(govde)
        assert Loan.objects.get().status == LoanStatus.OPEN  # yazma yok

    def test_yonetici_durum_sorgusunda_odunc_ayrintisi(self, client: APIClient) -> None:
        loan = odunc_ver(_uye())
        govde = client.get(DURUM, {"barcode": loan.copy.barcode}).json()
        assert govde["loan"]["member_name"] == f"{AD} {SOYAD}"
        assert govde["loan"]["class_label"] == "9/A"

    def test_rafta_ve_danisma(self, client: APIClient, gorevli: None) -> None:
        rafta = odunc_nushasi()
        danisma = nusha(eser(title="Atlas"), is_reference=True)
        assert client.get(DURUM, {"barcode": rafta.barcode}).json()["message"] == (
            "Rafta — ödünç verilebilir."
        )
        govde = client.get(DURUM, {"barcode": danisma.barcode}).json()
        assert govde["message"] == "Ödünç verilmez — kütüphanede okunur."
        assert govde["copy"]["is_loanable"] is False


# ============================================================ kartsız ödünç (U12)
class TestKartsizOdunc:
    def test_yonetici_uyelik_kaydi_ve_gerekceyle_verir_kayit_isaretli(
        self, client: APIClient
    ) -> None:
        uyelik = _uye()
        yanit = client.post(
            ODUNC,
            {
                "membership_id": uyelik.pk,
                "barcode": odunc_nushasi().barcode,
                "cardless_reason": "CARD_NOT_WITH_MEMBER",
            },
            format="json",
        )
        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["cardless"] is True
        assert yanit.json()["cardless_reason_display"] == "Kart yanında değil"
        assert Loan.objects.get().cardless is True

    @pytest.mark.parametrize(
        "govde",
        [
            # Üyelik kaydıyla ödünç yalnız kartsız ödünçtür: gerekçe zorunlu.
            {"barcode": "2026000001", "membership_id": 1},
            # Kart okutulduysa kartsız gerekçe verilmez.
            {"barcode": "2026000001", "card_no": "94718263", "cardless_reason": "CARD_LOST"},
            {"barcode": "2026000001"},
            {},
        ],
    )
    def test_gecersiz_govde_400(self, client: APIClient, govde: dict[str, Any]) -> None:
        yanit = client.post(ODUNC, govde, format="json")
        assert yanit.status_code == 400
        assert yanit.json()["code"] == "validation_error"

    def test_kapali_liste_disi_gerekce_400(self, client: APIClient) -> None:
        uyelik = _uye()
        yanit = client.post(
            ODUNC,
            {
                "membership_id": uyelik.pk,
                "barcode": odunc_nushasi().barcode,
                "cardless_reason": "keyfi",
            },
            format="json",
        )
        assert yanit.status_code == 400
        assert not Loan.objects.exists()

    def test_olmayan_uyelik(self, client: APIClient) -> None:
        yanit = client.post(
            ODUNC,
            {"membership_id": 999_999, "barcode": "2026000001", "cardless_reason": "CARD_LOST"},
            format="json",
        )
        assert yanit.status_code == 400
        assert yanit.json()["code"] == masa.RED_UYELIK_YOK


# ============================================================ gövde biçimi
def test_masa_uclari_yalniz_json_kabul_eder(client: APIClient) -> None:
    """Ara katmanın parametre denetçisi gövdeyi JSON okur; başka biçim görünüme girmez."""
    yanit = client.post(IADE, {"barcode": "2026000001"})  # çok parçalı form
    assert yanit.status_code == 415


@pytest.mark.parametrize("charset", ["utf-7", "utf-16", "latin-1"])
def test_masa_uclari_utf8_disi_karakter_kumesini_reddeder(client: APIClient, charset: str) -> None:
    """Yönetici kipinde de (ara katman devrede değilken) UTF-8 dışı gövde görünüme girmez.

    `charset=utf-7` ile `override+AF8-reason` anahtarı DRF'de `override_reason` olurdu.
    """
    uyelik = _uye()
    govde = json.dumps({"barcode": odunc_nushasi().barcode, "card_no": uyelik.card_no})
    yanit = client.generic(
        "POST",
        ODUNC,
        govde,
        content_type=f"application/json; charset={charset}",
    )
    assert yanit.status_code == 415
    assert yanit.json()["message"] == views_masa.UTF8_GEREKLI_MESSAGE
    assert not Loan.objects.exists()


def test_masa_uclari_utf8_charset_kabul_eder(client: APIClient) -> None:
    uyelik = _uye()
    govde = json.dumps({"barcode": odunc_nushasi().barcode, "card_no": uyelik.card_no})
    yanit = client.generic("POST", ODUNC, govde, content_type="application/json; charset=UTF-8")
    assert yanit.status_code == 201, yanit.json()
