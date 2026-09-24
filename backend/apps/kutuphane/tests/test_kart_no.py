"""Üye kartı numarası — biçim, sağlama, rastgelelik ve "asla yeniden kullanılmaz" (§7.1, D21).

Kod kapısı (§14.1 F6): **kart no asla yeniden kullanılmaz** — üyelik silinse,
kart yenilense de numara `IssuedCard`'da kalır ve bir daha verilmez. D21:
numara sıralı değil rastgeledir (`CardCounter` yoktur). Kart no şifreli
saklanır; okutma kör indeksle tam eşleşmedir (T14).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.kutuphane import card_ledger, card_numbers
from apps.kutuphane import models as kutuphane_models
from apps.kutuphane.models import (
    CardRevocation,
    CardRevocationReason,
    IssuedCard,
    Membership,
    card_no_blind_index,
)
from apps.kutuphane.selectors_dolasim import CardLookupState, find_membership_by_card
from apps.kutuphane.services import memberships
from apps.kutuphane.tests.dolasim_ortak import ogrenci, uye
from apps.okul.models import student_number_blind_index
from apps.okul.services import app_password

# ============================================================ saf biçim (DB yok)


def test_luhn_bilinen_ornek() -> None:
    """Luhn'un yaygın sınama örneği: 7992739871 → sağlama 3."""
    assert card_numbers.luhn_check_digit("7992739871") == "3"


def test_kart_no_sekiz_hane_dokuzla_baslar_ve_saglamasi_tutar() -> None:
    kart = card_numbers.build_card_no("471826")
    assert len(kart) == 8
    assert kart.startswith("9")
    assert kart[1:7] == "471826"
    assert card_numbers.is_valid_card_no(kart)


@pytest.mark.parametrize("govde", ["000000", "123456", "999999", "500005"])
def test_her_govde_icin_saglama_tek_hane_hatasini_yakalar(govde: str) -> None:
    kart = card_numbers.build_card_no(govde)
    for sira in range(8):
        for rakam in "0123456789":
            if rakam == kart[sira]:
                continue
            bozuk = kart[:sira] + rakam + kart[sira + 1 :]
            if sira == 0:
                assert not card_numbers.is_valid_card_no(bozuk)  # ön ek bozuldu
            else:
                assert not card_numbers.is_valid_card_no(bozuk), bozuk


def test_bitisik_hane_yer_degistirmesi_yakalanir() -> None:
    kart = card_numbers.build_card_no("135792")
    yakalanan = 0
    for sira in range(1, 7):
        bozuk = kart[:sira] + kart[sira + 1] + kart[sira] + kart[sira + 2 :]
        if bozuk != kart:
            assert not card_numbers.is_valid_card_no(bozuk), bozuk
            yakalanan += 1
    assert yakalanan > 0


@pytest.mark.parametrize(
    "deger",
    ["", "9123456", "912345678", "81234567", "abcdefgh", "2026000123"],
)
def test_kart_bicimi_disindaki_girdiler_gecersizdir(deger: str) -> None:
    assert not card_numbers.is_valid_card_no(deger)


def test_okuyucu_girdisi_normallestirilir() -> None:
    kart = card_numbers.build_card_no("246810")
    assert card_numbers.is_valid_card_no(f" {kart[:4]}-{kart[4:]}\n")
    assert card_numbers.card_index_input(f"{kart[:4]} {kart[4:]}") == f"kart-no:{kart}"


def test_gecersiz_govde_reddedilir() -> None:
    for govde in ("12345", "1234567", "12a456"):
        with pytest.raises(ValueError, match="gövdesi"):
            card_numbers.build_card_no(govde)


def test_rastgele_govde_alti_hanedir() -> None:
    for _ in range(50):
        govde = card_numbers.random_body()
        assert len(govde) == 6
        assert govde.isdigit()


# ============================================================ veritabanı


@pytest.fixture
def govdeler(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Rastgele gövde kaynağını sırayla verilen gövdelere bağlar (çakışma kurgusu)."""
    kuyruk: list[str] = []
    monkeypatch.setattr(card_numbers, "random_body", lambda: kuyruk.pop(0))
    yield kuyruk


def _ham(tablo: str, sutun: str, pk: int) -> str:
    with connection.cursor() as imlec:
        imlec.execute(f'SELECT "{sutun}" FROM "{tablo}" WHERE id = %s', [pk])  # noqa: S608
        satir = imlec.fetchone()
    return str(satir[0])


@pytest.mark.django_db
class TestKartNoUretimi:
    def test_kart_no_sifreli_saklanir_indeks_kor_indekstir(self) -> None:
        uyelik = uye()
        assert card_numbers.is_valid_card_no(uyelik.card_no)
        ham = _ham("kutuphane_membership", "card_no", uyelik.pk)
        assert ham != uyelik.card_no and uyelik.card_no not in ham
        assert uyelik.card_no_index == card_no_blind_index(uyelik.card_no)
        assert IssuedCard.objects.filter(card_no_index=uyelik.card_no_index).exists()

    def test_kart_indeksi_okul_no_indeksinden_ayridir(self) -> None:
        """Alan ayracı: aynı rakam dizisi okul no ve kart no olarak farklı indeks üretir."""
        kart = card_numbers.build_card_no("112233")
        assert card_no_blind_index(kart) != student_number_blind_index(kart)

    def test_kart_numaralari_sirali_degildir(self) -> None:
        """D21: OYS numarayı yıl bazlı sayaçtan veriyordu; burada gövde rastgeledir."""
        govdeler = [uye().card_no[1:7] for _ in range(12)]
        sayilar = [int(g) for g in govdeler]
        ardisik = all(b - a == 1 for a, b in zip(sayilar, sayilar[1:], strict=False))
        assert not ardisik
        assert len(set(govdeler)) == len(govdeler)
        assert not hasattr(kutuphane_models, "CardCounter")

    def test_verilmis_numara_yeniden_cekilir(self, govdeler: list[str]) -> None:
        govdeler.extend(["111111", "111111", "222222"])
        ilk = uye()
        ikinci = uye()
        assert ilk.card_no == card_numbers.build_card_no("111111")
        assert ikinci.card_no == card_numbers.build_card_no("222222")

    def test_silinen_uyeligin_numarasi_asla_yeniden_verilmez(self, govdeler: list[str]) -> None:
        govdeler.extend(["333333", "333333", "444444"])
        silinecek = uye()
        eski_indeks = silinecek.card_no_index
        memberships.delete_membership(silinecek)
        assert not Membership.all_objects.filter(pk=silinecek.pk).exists()

        yeni = uye()

        assert yeni.card_no == card_numbers.build_card_no("444444")
        assert IssuedCard.objects.filter(card_no_index=eski_indeks).exists()
        iptal = CardRevocation.objects.get(card_no_index=eski_indeks)
        assert iptal.reason == CardRevocationReason.DELETED
        assert iptal.membership is None

    def test_yenilenen_kartin_numarasi_asla_yeniden_verilmez(self, govdeler: list[str]) -> None:
        govdeler.extend(["555555", "666666", "555555", "666666", "777777"])
        uyelik = uye()
        memberships.renew_card(uyelik)
        assert uyelik.card_no == card_numbers.build_card_no("666666")

        baska = uye()

        assert baska.card_no == card_numbers.build_card_no("777777")
        assert IssuedCard.objects.count() == 3

    def test_numara_uretilemezse_acik_hata(self, govdeler: list[str]) -> None:
        govdeler.extend(["888888"] * (memberships.MAX_CARD_TRIES + 1))
        uye()
        with pytest.raises(ValidationError) as hata:
            uye()
        assert memberships.CARD_EXHAUSTED_MESSAGE in hata.value.messages

    def test_geri_yuklemede_kaybolan_numara_defter_sayesinde_yeniden_verilmez(
        self, govdeler: list[str]
    ) -> None:
        """Yedekten geri yükleme `IssuedCard`'ı geri sarar; veri dizinindeki defter sarmaz.

        Geri yükleme burada veritabanından satırların silinmesiyle taklit edilir: yedek
        alındıktan SONRA açılan üyelik ve kartı veritabanından kaybolur, ama kart
        basılıp dağıtılmış olabilir.
        """
        govdeler.extend(["121212", "121212", "343434"])
        kayip = uye()
        kayip_indeks = kayip.card_no_index
        assert card_ledger.contains(kayip_indeks)
        kayip.hard_delete()  # geri yükleme taklidi
        IssuedCard.objects.filter(card_no_index=kayip_indeks).delete()

        yeni = uye()

        assert yeni.card_no == card_numbers.build_card_no("343434")
        assert card_ledger.issued_indexes() == {kayip_indeks, yeni.card_no_index}

    def test_defter_kisisizdir_yalniz_kor_indeks_tutar(self) -> None:
        uyelik = uye()
        metin = card_ledger.ledger_path().read_text(encoding="ascii")
        assert metin == f"{uyelik.card_no_index}\n"
        assert uyelik.card_no not in metin
        assert card_ledger.ledger_path().parent == app_password.state_path().parent

    def test_defter_okunamazsa_kart_yine_verilir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Asıl güvence veritabanıdır; defter okunamaz/yazılamazsa üyelik yine açılır."""
        monkeypatch.setattr(card_ledger, "ledger_path", lambda: tmp_path)  # dizin: OSError
        uyelik = uye()
        assert IssuedCard.objects.filter(card_no_index=uyelik.card_no_index).exists()
        assert card_ledger.issued_indexes() == set()

    def test_defterdeki_bozuk_satirlar_atlanir(self) -> None:
        yol = card_ledger.ledger_path()
        yol.write_text("bozuk\n" + "a" * 64 + "\n\n", encoding="ascii")
        assert card_ledger.issued_indexes() == {"a" * 64}

    def test_verilmis_kart_tablosu_kisisizdir(self) -> None:
        alanlar = {alan.name for alan in IssuedCard._meta.get_fields()}
        assert alanlar == {"id", "card_no_index", "issued_on"}

    def test_kart_no_guncellenince_indeks_de_guncellenir(self) -> None:
        uyelik = uye()
        yeni = card_numbers.build_card_no("909090")
        uyelik.card_no = yeni
        uyelik.save(update_fields=["card_no"])
        uyelik.refresh_from_db()
        assert uyelik.card_no_index == card_no_blind_index(yeni)


@pytest.mark.django_db
class TestKartOkutma:
    def test_gecerli_kart_uyelige_cozulur(self) -> None:
        uyelik = uye()
        kart = uyelik.card_no
        sonuc = find_membership_by_card(f"{kart[:4]}-{kart[4:]}")
        assert sonuc.state == CardLookupState.FOUND
        assert sonuc.membership is not None and sonuc.membership.pk == uyelik.pk

    def test_yenilenen_kartin_eskisi_iptal_edilmis_okunur(self) -> None:
        uyelik = uye()
        eski = uyelik.card_no
        memberships.renew_card(uyelik)
        assert find_membership_by_card(eski).state == CardLookupState.REVOKED
        yeni = find_membership_by_card(uyelik.card_no)
        assert yeni.state == CardLookupState.FOUND

    def test_sonlanmis_uyeligin_karti_uyelige_cozulur(self) -> None:
        """Sonlanmış üyelik iptal değildir: masa "üyelik sonlanmış" diyebilsin."""
        uyelik = uye()
        memberships.terminate_membership(uyelik, reason="MEMBER_REQUEST")
        sonuc = find_membership_by_card(uyelik.card_no)
        assert sonuc.state == CardLookupState.FOUND
        assert sonuc.membership is not None and not sonuc.membership.is_active

    def test_verilmemis_ama_saglamasi_tutan_numara_taninmaz(self) -> None:
        uye()
        verilmemis = next(
            card_numbers.build_card_no(f"{g:06d}")
            for g in range(1_000_000)
            if not IssuedCard.objects.filter(
                card_no_index=card_no_blind_index(card_numbers.build_card_no(f"{g:06d}"))
            ).exists()
        )
        assert find_membership_by_card(verilmemis).state == CardLookupState.UNKNOWN

    def test_saglamasi_tutmayan_numara_sorgulanmadan_gecersizdir(
        self, django_assert_num_queries: Any
    ) -> None:
        kart = card_numbers.build_card_no("123123")
        bozuk = kart[:-1] + str((int(kart[-1]) + 1) % 10)
        with django_assert_num_queries(0):
            assert find_membership_by_card(bozuk).state == CardLookupState.INVALID
        assert find_membership_by_card(ogrenci().student_number).state == CardLookupState.INVALID
