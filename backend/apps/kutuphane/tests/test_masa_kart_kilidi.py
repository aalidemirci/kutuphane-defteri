"""GA-7 — art arda geçersiz kart okutması yönetici parolası ister (tasarım §4.4, D21).

Kart numarası rastgeledir (D21); masadaki görevli komşu numaraları deneyerek
başkasının adını ve kalan hakkını okuyamamalıdır. Görevli kipinde art arda 5
geçersiz kart okutması (iptal edilmiş, tanınmayan ya da sağlaması tutmayan) ya
da son 10 dakikada 5 tanınmayan veya iptal edilmiş kart okutması (araya geçerli
kart girse de — F6 düzeltme turu) kart okutmayı durdurur: 429
`kart_okutma_kilidi`. Sürdürmek için yönetici parolası
`POST library/desk/card-unlock/` gövdesinde gönderilir (görevli kipinden
çıkmadan). İade hiçbir durumda kilitlenmez. Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.kutuphane import card_numbers
from apps.kutuphane.models import Loan, LoanStatus
from apps.kutuphane.services import masa
from apps.kutuphane.tests.dolasim_ortak import odunc_nushasi, odunc_ver, uye
from apps.okul.kip import KIP
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import DOGRU_PAROLA, YANLIS_PAROLA, sahte_dogrulayici
from shared import crypto

pytestmark = pytest.mark.django_db

KART = "/api/v1/library/desk/member/"
ODUNC = "/api/v1/library/checkout/"
IADE = "/api/v1/library/return/"
KILIT = "/api/v1/library/desk/card-unlock/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def dogrulama(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    cagrilar: list[str] = []
    monkeypatch.setattr(app_password, "verify_password", sahte_dogrulayici(cagrilar))
    return cagrilar


def _gecersiz(sira: int) -> str:
    """Sağlaması BOZUK kart no (veritabanına sorulmaz)."""
    gecerli = card_numbers.build_card_no(f"{100000 + sira:06d}")
    return f"{gecerli[:-1]}{(int(gecerli[-1]) + 1) % 10}"


def _kart(client: APIClient, kod: str) -> Any:
    return client.post(KART, {"card_no": kod}, format="json")


def _kilitli_mi(yanit: Any) -> bool:
    return bool(yanit.status_code == 429 and yanit.json()["code"] == "kart_okutma_kilidi")


def test_besinci_gecersiz_okutma_kart_okutmayi_durdurur(client: APIClient) -> None:
    uyelik = uye()
    KIP.gorevliye_gec()

    for sira in range(masa.GECERSIZ_KART_SINIRI - 1):
        assert _kart(client, _gecersiz(sira)).status_code == 200
    besinci = _kart(client, _gecersiz(99))

    assert _kilitli_mi(besinci)
    assert besinci.json()["message"] == masa.KART_KILIDI_MESSAGE
    # Kilitliyken GEÇERLİ kart da çözülmez (ad okunmaz).
    gecerli = _kart(client, uyelik.card_no)
    assert _kilitli_mi(gecerli)
    assert "Deneme" not in gecerli.content.decode()


def test_kilit_odunc_ucunu_da_keser_iade_kilitlenmez(client: APIClient) -> None:
    uyelik = uye()
    loan = odunc_ver(uyelik)
    KIP.gorevliye_gec()
    for sira in range(masa.GECERSIZ_KART_SINIRI):
        _kart(client, _gecersiz(sira))

    odunc = client.post(
        ODUNC, {"card_no": uyelik.card_no, "barcode": odunc_nushasi().barcode}, format="json"
    )
    assert _kilitli_mi(odunc)
    assert Loan.objects.count() == 1

    iade = client.post(IADE, {"barcode": loan.copy.barcode}, format="json")
    assert iade.json()["result"] == "returned"
    assert Loan.objects.get().status == LoanStatus.RETURNED


def test_odunc_ucundaki_gecersiz_kartlar_da_sayilir(client: APIClient) -> None:
    """Numaralandırma ödünç ucundan da denenemez."""
    barkod = odunc_nushasi().barcode
    KIP.gorevliye_gec()
    yanitlar = [
        client.post(ODUNC, {"card_no": _gecersiz(s), "barcode": barkod}, format="json")
        for s in range(masa.GECERSIZ_KART_SINIRI)
    ]
    assert [y.status_code for y in yanitlar[:-1]] == [400] * (masa.GECERSIZ_KART_SINIRI - 1)
    assert _kilitli_mi(yanitlar[-1])


def test_yonetici_parolasi_kilidi_acar_gorevli_kipi_surer(
    client: APIClient, dogrulama: list[str]
) -> None:
    uyelik = uye()
    KIP.gorevliye_gec()
    for sira in range(masa.GECERSIZ_KART_SINIRI):
        _kart(client, _gecersiz(sira))

    yanlis = client.post(KILIT, {"password": YANLIS_PAROLA}, format="json")
    assert yanlis.status_code == 400
    assert yanlis.json()["message"] == "Parola hatalı."
    assert _kilitli_mi(_kart(client, uyelik.card_no))
    assert YANLIS_PAROLA not in yanlis.content.decode()

    dogru = client.post(KILIT, {"password": DOGRU_PAROLA}, format="json")
    assert dogru.status_code == 200
    assert dogru.json() == {"message": "Kart okutma yeniden açıldı."}
    assert _kart(client, uyelik.card_no).json()["state"] == "FOUND"
    assert KIP.durum() == "gorevli"
    assert dogrulama == [YANLIS_PAROLA, DOGRU_PAROLA]


def test_parolasiz_kilit_acma_istegi_400(client: APIClient) -> None:
    KIP.gorevliye_gec()
    assert client.post(KILIT, {}, format="json").status_code == 400


def _taninmayan(sira: int) -> str:
    """Sağlaması TUTAN ama hiç verilmemiş kart no (veritabanına sorulur — kural 2)."""
    return card_numbers.build_card_no(f"{300000 + sira:06d}")


def test_basarili_okutma_art_arda_diziyi_bozar(client: APIClient) -> None:
    """Yıpranmış kartın yanlış okunması (sağlama tutmaz) araya geçerli kart girince kilitlemez."""
    uyelik = uye()
    KIP.gorevliye_gec()
    for tur in range(3):
        for sira in range(masa.GECERSIZ_KART_SINIRI - 1):
            assert _kart(client, _gecersiz(10 * tur + sira)).status_code == 200
        assert _kart(client, uyelik.card_no).json()["state"] == "FOUND"


def test_araya_gecerli_kart_katmak_numaralandirmayi_kilitten_kurtarmaz(client: APIClient) -> None:
    """Kural 2: sağlamasını hesaplayıp numara deneyen görevli kendi kartıyla sayacı sıfırlayamaz.

    Dört tanınmayan numara + kendi kartı döngüsü: beşinci tanınmayan okutma kart
    okutmayı durdurur; kilit kendiliğinden kalkmaz, yönetici parolası ister.
    """
    kendi = uye()
    KIP.gorevliye_gec()
    kilitler = []
    for tur in range(10):
        for sira in range(masa.GECERSIZ_KART_SINIRI - 1):
            yanit = _kart(client, _taninmayan(10 * tur + sira))
            kilitler.append(_kilitli_mi(yanit))
            if _kilitli_mi(yanit):
                break
        if any(kilitler):
            break
        assert _kart(client, kendi.card_no).json()["state"] == "FOUND"

    assert kilitler.count(True) == 1
    assert len(kilitler) == masa.TANINMAYAN_KART_SINIRI
    son = _kart(client, kendi.card_no)
    assert _kilitli_mi(son)
    assert son.json()["message"] == masa.KART_KILIDI_PENCERE_MESSAGE


def test_pencere_disina_cikan_taninmayan_okutma_sayilmaz() -> None:
    """Kural 2 bir zaman penceresidir: on dakikadan eski okutmalar düşer (sahte saat)."""
    saat = [0.0]
    sayac = masa.GecersizKartSayaci(pencere_siniri=3, pencere_sn=600, saat=lambda: saat[0])
    for _ in range(2):
        assert sayac.gecersiz(veritabanina_soruldu=True) is None
        sayac.gecerli()
        saat[0] += 400
    # İlk okutma 800 sn önceydi: pencerede 1 + bu = 2 < 3.
    assert sayac.gecersiz(veritabanina_soruldu=True) is None
    sayac.gecerli()
    assert sayac.gecersiz(veritabanina_soruldu=True) == masa.KART_KILIDI_PENCERE_MESSAGE
    # Kilit kendiliğinden kalkmaz; yalnız yönetici parolası (sifirla) kaldırır.
    saat[0] += 10_000
    assert sayac.kilitli_mi()
    sayac.gecerli()
    assert sayac.kilitli_mi()
    sayac.sifirla()
    assert not sayac.kilitli_mi()


def test_saglamasi_tutmayan_okutma_pencereye_sayilmaz() -> None:
    """Sağlaması tutmayan numara veritabanına sorulmaz, kimseyi ele vermez (kural 1'de sayılır)."""
    sayac = masa.GecersizKartSayaci(sinir=100, pencere_siniri=2)
    for _ in range(10):
        assert sayac.gecersiz() is None
        sayac.gecerli()
    assert not sayac.kilitli_mi()


def test_iptal_edilmis_ve_taninmayan_kart_da_gecersiz_sayilir(client: APIClient) -> None:
    from apps.kutuphane.services import memberships

    uyelik = uye()
    eski = uyelik.card_no
    memberships.renew_card(uyelik)
    KIP.gorevliye_gec()

    durumlar = [_kart(client, eski).json()["state"] for _ in range(masa.GECERSIZ_KART_SINIRI - 1)]
    assert durumlar == ["REVOKED"] * (masa.GECERSIZ_KART_SINIRI - 1)
    assert _kilitli_mi(_kart(client, eski))


def test_yonetici_kipinde_sayilmaz_ve_kesmez(client: APIClient) -> None:
    for sira in range(3 * masa.GECERSIZ_KART_SINIRI):
        assert _kart(client, _gecersiz(sira)).status_code == 200
    assert masa.GECERSIZ_KARTLAR.sayi == 0


def test_yonetici_kipindeki_okutma_sayaci_sifirlar(client: APIClient) -> None:
    KIP.gorevliye_gec()
    for sira in range(masa.GECERSIZ_KART_SINIRI - 1):
        _kart(client, _gecersiz(sira))
    KIP._reset_for_tests()  # yönetici parolasıyla yönetici kipine dönüldü
    _kart(client, _gecersiz(50))
    KIP.gorevliye_gec()

    assert _kart(client, _gecersiz(51)).status_code == 200


def test_kilitleyip_parolayla_acmak_sayaci_sifirlar(client: APIClient) -> None:
    """Sayaç anahtar dönemine bağlıdır: kilit açılışında yönetici parolası girilmiştir."""
    KIP.gorevliye_gec()
    for sira in range(masa.GECERSIZ_KART_SINIRI):
        _kart(client, _gecersiz(sira))
    assert masa.GECERSIZ_KARTLAR.kilitli_mi()

    from conftest import TEST_DEK

    crypto.unload_key()
    crypto.load_key(TEST_DEK)

    assert not masa.GECERSIZ_KARTLAR.kilitli_mi()


def test_sayac_is_parcacigi_guvenlidir() -> None:
    import threading

    sayac = masa.GecersizKartSayaci(sinir=10_000)
    isciler = [
        threading.Thread(target=lambda: [sayac.gecersiz() for _ in range(500)]) for _ in range(8)
    ]
    for isci in isciler:
        isci.start()
    for isci in isciler:
        isci.join()
    assert sayac.sayi == 4000
