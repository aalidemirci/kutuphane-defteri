"""Yönetici kipi sürelerinin Kütüphane Politikası'na bağlanması (F7 "Devreden"; §4.4, A10).

F2 ekleri 1'den beri `LibraryPolicy.idle_minutes` ve `admin_max_minutes` ayar
olarak vardı ama `apps.okul.kip.kip_sureleri()` sabit varsayılanları (3 / 30 dk)
döndürüyordu. F7'de bağlandı: kip, kütüphanenin kaydettiği kaynaktan okur,
değeri süreç içinde önbelleğe alır (sıcak yolda sorgu yok) ve politika yazılınca
önbellek boşalır. Sınanan: bağlama, aralıklar (boşta 1-15, mutlak 5-120 dk,
boşta ≤ mutlak), önbellek, geçersiz değer ve okunamayan veritabanında
varsayılanlar, uç üzerinden yazma.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from rest_framework.test import APIClient

from apps.kutuphane.models import LibraryPolicy
from apps.kutuphane.services import policy as policy_service
from apps.okul import kip
from apps.okul.kip import GOREVLI, YONETICI, KipDurumu, KipSureleri, kip_sureleri
from apps.okul.tests.kip_ortak import SahteSaat, kurulum_durumunu_yaz

pytestmark = pytest.mark.django_db

POLITIKA = "/api/v1/library/policy/"


def test_ayar_satiri_yokken_tasarim_varsayilanlari() -> None:
    assert kip_sureleri() == KipSureleri(bosta_sn=3 * 60, mutlak_sn=30 * 60)


def test_politika_yazilinca_kip_yeni_sureleri_kullanir() -> None:
    assert kip_sureleri() == kip.VARSAYILAN_SURELER  # önbelleğe alındı
    policy_service.update_policy(idle_minutes=5, admin_max_minutes=45)
    assert kip_sureleri() == KipSureleri(bosta_sn=5 * 60, mutlak_sn=45 * 60)


def test_kip_durumu_ayarlanan_bosta_suresiyle_gorevliye_iner() -> None:
    kurulum_durumunu_yaz(tamam=True)
    policy_service.update_policy(idle_minutes=10, admin_max_minutes=60)
    saat = SahteSaat()
    durum = KipDurumu(saat=saat)
    assert durum.durum() == YONETICI

    saat.ilerlet(9 * 60)
    assert durum.durum() == YONETICI  # varsayılan 3 dk olsaydı inmişti
    saat.ilerlet(60)
    assert durum.durum() == GOREVLI
    assert durum.ozet()["bosta_dk"] == 10 and durum.ozet()["mutlak_dk"] == 60


def test_sicak_yolda_veritabani_bir_kez_okunur(monkeypatch: pytest.MonkeyPatch) -> None:
    cagri: list[int] = []
    asil = policy_service.kip_sure_dakikalari

    def sayan() -> tuple[int, int] | None:
        cagri.append(1)
        return asil()

    kip.sure_kaynagini_kaydet(sayan)
    try:
        for _ in range(50):
            kip_sureleri()
        assert len(cagri) == 1
        policy_service.update_policy(idle_minutes=4)
        for _ in range(50):
            kip_sureleri()
        assert len(cagri) == 2
        assert kip_sureleri().bosta_sn == 4 * 60
    finally:
        kip.sure_kaynagini_kaydet(policy_service.kip_sure_dakikalari)


@pytest.mark.parametrize(
    "deger",
    [(0, 30), (20, 10), ("3", 30), (3,), None],
)
def test_gecersiz_deger_ve_kayitsiz_satir_varsayilanlara_doner(deger: Any) -> None:
    kip.sure_kaynagini_kaydet(lambda: deger)
    try:
        assert kip_sureleri() == kip.VARSAYILAN_SURELER
    finally:
        kip.sure_kaynagini_kaydet(policy_service.kip_sure_dakikalari)


def test_okunamayan_veritabaninda_varsayilanlar_onbelleksiz() -> None:
    sayac: list[int] = []

    def bozuk() -> tuple[int, int] | None:
        sayac.append(1)
        raise DatabaseError("okunamadı")

    kip.sure_kaynagini_kaydet(bozuk)
    try:
        assert kip_sureleri() == kip.VARSAYILAN_SURELER
        assert kip_sureleri() == kip.VARSAYILAN_SURELER
        assert len(sayac) == 2  # hata önbelleğe alınmaz: bir sonraki çağrı yeniden dener
    finally:
        kip.sure_kaynagini_kaydet(policy_service.kip_sure_dakikalari)


class TestAraliklar:
    @pytest.mark.parametrize(
        ("alanlar", "alan"),
        [
            ({"idle_minutes": 0}, "idle_minutes"),
            ({"idle_minutes": 16}, "idle_minutes"),
            ({"admin_max_minutes": 4}, "admin_max_minutes"),
            ({"admin_max_minutes": 121}, "admin_max_minutes"),
            ({"idle_minutes": 15, "admin_max_minutes": 10}, "idle_minutes"),
        ],
    )
    def test_aralik_disi_ve_bosta_mutlaktan_uzun_reddedilir(
        self, alanlar: dict[str, int], alan: str
    ) -> None:
        with pytest.raises(ValidationError) as hata:
            policy_service.update_policy(**alanlar)
        assert alan in hata.value.message_dict

    def test_sinirlar_kabul_edilir(self) -> None:
        policy_service.update_policy(idle_minutes=1, admin_max_minutes=5)
        policy_service.update_policy(idle_minutes=15, admin_max_minutes=120)
        assert kip_sureleri() == KipSureleri(bosta_sn=15 * 60, mutlak_sn=120 * 60)

    def test_db_kisiti_bostanin_mutlaktan_uzun_olmasini_keser(self) -> None:
        policy_service.update_policy(idle_minutes=3, admin_max_minutes=30)
        with pytest.raises(IntegrityError):
            LibraryPolicy.objects.filter(pk=LibraryPolicy.SINGLETON_PK).update(
                idle_minutes=31, admin_max_minutes=30
            )

    def test_uc_aralik_disini_400_ile_reddeder_ve_turkce_iletir(self) -> None:
        istemci = APIClient()
        yanit = istemci.put(POLITIKA, {"idle_minutes": 20}, format="json")
        assert yanit.status_code == 400
        ters = istemci.put(POLITIKA, {"idle_minutes": 10, "admin_max_minutes": 5}, format="json")
        assert ters.status_code == 400
        assert "boşta süresi mutlak süresinden uzun olamaz" in ters.json()["message"]
        dogru = istemci.put(POLITIKA, {"idle_minutes": 10, "admin_max_minutes": 60}, format="json")
        assert dogru.status_code == 200
        assert kip_sureleri() == KipSureleri(bosta_sn=10 * 60, mutlak_sn=60 * 60)


@pytest.mark.django_db(transaction=True)
def test_goc_eski_genis_araliktaki_degerleri_yeni_araliga_ceker() -> None:
    """0006 göçü: F2-F6'nın 1-60 / 5-480 aralığında kaydedilmiş değer kısıttan ÖNCE çekilir.

    60 dk boşta → 15 (üst sınır); ardından boşta ≤ mutlak için 8'e iner.
    """
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    hedef = ("kutuphane", "0005_uyelik_ve_odunc")
    try:
        call_command("migrate", *hedef, verbosity=0)
        eski = MigrationLoader(connection).project_state(hedef).apps
        eski.get_model("kutuphane", "LibraryPolicy").objects.create(
            pk=1, idle_minutes=60, admin_max_minutes=8
        )
    finally:
        call_command("migrate", verbosity=0)
    satir = LibraryPolicy.objects.get(pk=1)
    assert (satir.idle_minutes, satir.admin_max_minutes) == (8, 8)
