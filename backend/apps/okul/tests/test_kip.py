"""Kip durum makinesi (U5, tasarım §4.4, T16) — birim testleri.

Varsayılan test ortamı (kök `conftest.py`): yönetici parolası kurulu + kilit
açık. Saat taklit edilir (`SahteSaat`); parola doğrulaması `verify_password`
sözleşmesine göre taklit edilir (gerçek doğrulama `test_kip_uclari.py`'de).
"""

from __future__ import annotations

import time

import pytest

from apps.okul import kip as kip_modulu
from apps.okul.kip import (
    GOREVLI,
    GUVENLIK_DOSYASI_KAYIP,
    KILITLI,
    KURULUM,
    YONETICI,
    KipDurumu,
    KipGecisHatasi,
    KipSureleri,
    UykuyuSayanSaat,
    kip_sureleri,
    uykuyu_sayan_monoton_kaynak,
)
from apps.okul.services import app_password
from apps.okul.tests.kip_ortak import (
    DOGRU_PAROLA,
    YANLIS_PAROLA,
    SahteSaat,
    sahte_dogrulayici,
)
from shared import crypto

# `parolasiz` ortamında `is_password_set()` DB'deki parmak izine bakar.
pytestmark = pytest.mark.django_db

BOSTA = 3 * 60
MUTLAK = 30 * 60


@pytest.fixture
def saat() -> SahteSaat:
    return SahteSaat()


@pytest.fixture
def kip(saat: SahteSaat) -> KipDurumu:
    return KipDurumu(saat=saat)


@pytest.fixture
def dogrulama_cagrilari(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    cagrilar: list[str] = []
    monkeypatch.setattr(app_password, "verify_password", sahte_dogrulayici(cagrilar))
    return cagrilar


def _yeniden_ac() -> None:
    """Kilitle + aynı anahtarla yeniden aç (kilit açılışının süreç içi karşılığı)."""
    ham = crypto.active_key()
    assert ham is not None
    crypto.unload_key()
    crypto.load_key(ham)


# ============================================================ durumlar


class TestDurumlar:
    def test_kilit_acikken_ilk_durum_yonetici_kipidir(self, kip: KipDurumu) -> None:
        assert kip.durum() == YONETICI

    def test_parola_kurulu_degilse_kurulum(self, parolasiz: None, kip: KipDurumu) -> None:
        assert kip.durum() == KURULUM
        assert kip.gorevli_mi() is False

    def test_kilitliyken_kilitli(self, kilitli: None, kip: KipDurumu) -> None:
        assert kip.durum() == KILITLI
        assert kip.gorevli_mi() is False

    def test_guvenlik_dosyasi_kayipken_kayip(self, parmak_izi_yazili: str, kip: KipDurumu) -> None:
        app_password.state_path().unlink()
        assert kip.durum() == GUVENLIK_DOSYASI_KAYIP
        # Anahtar bellekte kalsa da kip değiştirilemez.
        with pytest.raises(KipGecisHatasi):
            kip.gorevliye_gec()

    def test_kilitle_her_kipten_kilitliye_goturur(self, kip: KipDurumu) -> None:
        kip.gorevliye_gec()
        app_password.lock()
        assert kip.durum() == KILITLI
        assert kip.gorevli_mi() is False

    def test_varsayilan_sureler_uc_ve_otuz_dakikadir(self) -> None:
        assert kip_sureleri() == KipSureleri(bosta_sn=BOSTA, mutlak_sn=MUTLAK)

    def test_modul_tekili_tek_nesnedir(self) -> None:
        from apps.okul.kip import KIP

        assert KIP is kip_modulu.KIP
        assert isinstance(KIP, KipDurumu)


# ============================================================ geçişler


class TestGecisler:
    def test_gorevli_kipine_gecis_parolasizdir(self, kip: KipDurumu) -> None:
        assert kip.gorevliye_gec() == GOREVLI
        assert kip.durum() == GOREVLI
        assert kip.gorevli_mi() is True

    def test_gorevli_kipine_gecis_fikirdestir(self, kip: KipDurumu) -> None:
        kip.gorevliye_gec()
        assert kip.gorevliye_gec() == GOREVLI

    @pytest.mark.parametrize("ortam", ["parolasiz", "kilitli"])
    def test_kilit_kapaliyken_gorevli_kipine_gecilemez(
        self, ortam: str, request: pytest.FixtureRequest, kip: KipDurumu
    ) -> None:
        request.getfixturevalue(ortam)
        with pytest.raises(KipGecisHatasi) as hata:
            kip.gorevliye_gec()
        assert hata.value.durum in (KURULUM, KILITLI)
        assert "kilit" in hata.value.message

    def test_yonetici_kipine_gecis_parola_ister(
        self, kip: KipDurumu, dogrulama_cagrilari: list[str]
    ) -> None:
        kip.gorevliye_gec()
        with pytest.raises(app_password.AppPasswordError, match="Parola hatalı."):
            kip.yoneticiye_gec(YANLIS_PAROLA)
        assert kip.durum() == GOREVLI

        assert kip.yoneticiye_gec(DOGRU_PAROLA) == YONETICI
        assert kip.durum() == YONETICI
        assert dogrulama_cagrilari == [YANLIS_PAROLA, DOGRU_PAROLA]

    def test_kilitliyken_yonetici_kipine_gecis_parola_denemeden_reddedilir(
        self, kilitli: None, kip: KipDurumu, dogrulama_cagrilari: list[str]
    ) -> None:
        with pytest.raises(KipGecisHatasi):
            kip.yoneticiye_gec(DOGRU_PAROLA)
        assert dogrulama_cagrilari == []

    def test_dogrulama_sirasinda_kilitlenirse_gecis_yapilmaz(
        self, kip: KipDurumu, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kip.gorevliye_gec()

        def dogrula_ve_kilitle(password: str) -> None:
            app_password.lock()  # başka bir istek bu arada "Kilitle"ye bastı

        monkeypatch.setattr(app_password, "verify_password", dogrula_ve_kilitle)
        with pytest.raises(KipGecisHatasi):
            kip.yoneticiye_gec(DOGRU_PAROLA)
        assert kip.durum() == KILITLI

    def test_yeniden_kilit_acilisi_yonetici_kipine_dondurur(self, kip: KipDurumu) -> None:
        kip.gorevliye_gec()
        _yeniden_ac()
        assert kip.durum() == YONETICI

    def test_anahtarin_yeniden_yuklenmesi_de_yeni_acilistir(self, kip: KipDurumu) -> None:
        """Parola değiştirme ve kurtarma da `load_key` çağırır: sayaç değişir."""
        kip.gorevliye_gec()
        ham = crypto.active_key()
        assert ham is not None
        crypto.load_key(ham)
        assert kip.durum() == YONETICI

    def test_ayni_epoch_icinde_gorevli_kalir(self, kip: KipDurumu) -> None:
        kip.gorevliye_gec()
        for _ in range(3):
            assert kip.durum() == GOREVLI


# ============================================================ tembel süre dolumu


class TestSureler:
    def test_bosta_sure_dolunca_gorevli_kipine_iner(self, kip: KipDurumu, saat: SahteSaat) -> None:
        assert kip.durum() == YONETICI
        saat.ilerlet(BOSTA - 1)
        assert kip.durum() == YONETICI
        saat.ilerlet(1)
        assert kip.durum() == GOREVLI

    def test_etkinlik_bosta_sayacini_tazeler(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.durum()
        saat.ilerlet(BOSTA - 10)
        kip.etkinlik()
        saat.ilerlet(BOSTA - 10)
        assert kip.durum() == YONETICI
        saat.ilerlet(10)
        assert kip.durum() == GOREVLI

    def test_durum_sorgusu_bosta_sayacini_tazelemez(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.durum()
        for _ in range(BOSTA // 30):
            saat.ilerlet(30)
            kip.durum()
            kip.ozet()
            kip.gorevli_mi()
        assert kip.durum() == GOREVLI

    def test_suresi_dolan_yonetici_kipi_gec_etkinlikle_dirilmez(
        self, kip: KipDurumu, saat: SahteSaat
    ) -> None:
        kip.durum()
        saat.ilerlet(BOSTA + 5)
        kip.etkinlik()
        assert kip.durum() == GOREVLI

    def test_mutlak_sure_etkinlikten_bagimsiz_dolar(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.durum()
        for _ in range(MUTLAK // 60 - 1):
            saat.ilerlet(60)
            kip.etkinlik()
            assert kip.durum() == YONETICI
        saat.ilerlet(60)
        kip.etkinlik()
        assert kip.durum() == GOREVLI

    def test_mutlak_sure_dolunca_parola_yeniden_istenir(
        self, kip: KipDurumu, saat: SahteSaat, dogrulama_cagrilari: list[str]
    ) -> None:
        kip.durum()
        saat.ilerlet(MUTLAK)
        assert kip.durum() == GOREVLI
        with pytest.raises(app_password.AppPasswordError):
            kip.yoneticiye_gec(YANLIS_PAROLA)
        kip.yoneticiye_gec(DOGRU_PAROLA)
        assert kip.durum() == YONETICI
        # Yükseltme iki sayacı da sıfırlar.
        ozet = kip.ozet()
        assert ozet["bosta_kalan_sn"] == BOSTA
        assert ozet["mutlak_kalan_sn"] == MUTLAK

    def test_yonetici_kipinde_parolayi_yeniden_girmek_mutlak_sureyi_yeniler(
        self, kip: KipDurumu, saat: SahteSaat, dogrulama_cagrilari: list[str]
    ) -> None:
        kip.durum()
        saat.ilerlet(MUTLAK - 60)
        kip.etkinlik()
        kip.yoneticiye_gec(DOGRU_PAROLA)
        saat.ilerlet(120)
        assert kip.durum() == YONETICI

    def test_yeni_kilit_acilisi_sayaclari_sifirlar(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.durum()
        saat.ilerlet(BOSTA - 1)
        _yeniden_ac()
        assert kip.durum() == YONETICI
        saat.ilerlet(BOSTA - 1)
        assert kip.durum() == YONETICI
        saat.ilerlet(1)
        assert kip.durum() == GOREVLI

    def test_gorevli_kipinde_etkinlik_etkisizdir(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.gorevliye_gec()
        kip.etkinlik()
        assert kip.durum() == GOREVLI

    def test_kilitliyken_etkinlik_etkisizdir(self, kilitli: None, kip: KipDurumu) -> None:
        kip.etkinlik()
        assert kip.durum() == KILITLI

    def test_sure_saglayicisi_her_degerlendirmede_okunur(self, saat: SahteSaat) -> None:
        sureler = [KipSureleri(bosta_sn=BOSTA, mutlak_sn=MUTLAK)]
        kip = KipDurumu(saat=saat, sureler=lambda: sureler[0])
        kip.durum()
        saat.ilerlet(90)
        assert kip.durum() == YONETICI
        sureler[0] = KipSureleri(bosta_sn=60, mutlak_sn=MUTLAK)  # ayar değişti (F6)
        assert kip.durum() == GOREVLI


# ============================================================ özet


class TestOzet:
    def test_yonetici_kipinde_kalan_sureler_doludur(self, kip: KipDurumu, saat: SahteSaat) -> None:
        kip.durum()
        saat.ilerlet(40.5)
        assert kip.ozet() == {
            "durum": YONETICI,
            "bosta_kalan_sn": BOSTA - 40,
            "mutlak_kalan_sn": MUTLAK - 40,
            "bosta_dk": 3,
            "mutlak_dk": 30,
        }

    def test_gorevli_kipinde_kalan_sureler_bostur(self, kip: KipDurumu) -> None:
        kip.gorevliye_gec()
        ozet = kip.ozet()
        assert ozet["durum"] == GOREVLI
        assert ozet["bosta_kalan_sn"] is None
        assert ozet["mutlak_kalan_sn"] is None

    def test_kilitliyken_ozet_kilitli_der(self, kilitli: None, kip: KipDurumu) -> None:
        assert kip.ozet()["durum"] == KILITLI

    def test_ozet_anahtarlari_sabittir(self, kip: KipDurumu) -> None:
        """Ön yüz `modules/kip/api.ts::KipOzeti` bu alanları okur."""
        assert sorted(kip.ozet()) == [
            "bosta_dk",
            "bosta_kalan_sn",
            "durum",
            "mutlak_dk",
            "mutlak_kalan_sn",
        ]


def test_sifirlama_varsayilan_saate_ve_surelere_doner(saat: SahteSaat) -> None:
    kip = KipDurumu(saat=saat, sureler=lambda: KipSureleri(bosta_sn=1, mutlak_sn=1))
    kip.gorevliye_gec()
    kip._reset_for_tests()
    assert kip.durum() == YONETICI
    assert kip.ozet()["bosta_dk"] == 3
    # Varsayılan saat yine uykuyu sayan saattir (düz `time.monotonic` değil).
    assert isinstance(kip._saat, UykuyuSayanSaat)


# ------------------------------------------------------------ saat: uyku da süredir


class _IkiKaynak:
    """`UykuyuSayanSaat`'in iki kaynağını (monoton + duvar) elle ilerleten taklit."""

    def __init__(self) -> None:
        self.monoton = 5_000.0
        self.duvar = 1_790_000_000.0  # 2026 civarı bir Unix zamanı

    def saat(self) -> UykuyuSayanSaat:
        return UykuyuSayanSaat(monoton=lambda: self.monoton, duvar=lambda: self.duvar)


def test_varsayilan_saat_uykuyu_sayan_saattir() -> None:
    """Denetim bulgusu: `time.monotonic` Linux'ta askıya alınan süreyi saymaz."""
    assert isinstance(KipDurumu()._saat, UykuyuSayanSaat)
    assert isinstance(kip_modulu.KIP._saat, UykuyuSayanSaat)


@pytest.mark.skipif(not hasattr(time, "CLOCK_BOOTTIME"), reason="yalnız Linux")
def test_linuxta_monoton_kaynak_boottime_dir() -> None:
    """Linux'ta (Pardus) monoton kaynak CLOCK_BOOTTIME'dır: uykuyu da sayar."""
    kaynak = uykuyu_sayan_monoton_kaynak()
    assert kaynak is not time.monotonic
    assert abs(kaynak() - time.clock_gettime(time.CLOCK_BOOTTIME)) < 1.0


def test_uyku_suresi_duvar_saatinden_sayilir() -> None:
    """Monoton kaynak uykuda durur (CLOCK_MONOTONIC), duvar saati uyanışta ileri geçer."""
    k = _IkiKaynak()
    saat = k.saat()
    once = saat()
    k.duvar += 8 * 3600  # gece boyunca uyku; monoton kaynak hiç ilerlemedi
    assert saat() - once == 8 * 3600


def test_duvar_saati_geri_alinsa_sure_uzamaz_ve_saat_azalmaz() -> None:
    k = _IkiKaynak()
    saat = k.saat()
    once = saat()
    k.duvar -= 3600  # saat bir saat geri alındı
    k.monoton += 10
    ara = saat()
    assert ara - once == 10  # yalnız monoton ilerleme
    k.monoton += 5
    k.duvar += 5
    assert saat() - ara == 5  # geri alınan saat sonraki adımlarda borç yaratmaz


def test_duvar_saati_ileri_sicrarsa_sure_erken_dolar() -> None:
    """Fail-closed: ileri sıçrama yönetici kipini kısaltır, asla uzatmaz."""
    k = _IkiKaynak()
    saat = k.saat()
    once = saat()
    k.monoton += 1
    k.duvar += 120
    assert saat() - once == 120


def test_uykudan_uyaninca_yonetici_kipi_acik_kalmaz() -> None:
    """Denetçi senaryosu: boşta sayacında 2 dk kalmışken makine uyutulur, sabah uyanır.
    Uyanıştan sonraki ilk dokunuş (etkinlik) yönetici kipini dirilterek UZATAMAZ."""
    k = _IkiKaynak()
    kip = KipDurumu(saat=k.saat())
    assert kip.durum() == YONETICI
    k.monoton += 60
    k.duvar += 60
    assert kip.ozet()["bosta_kalan_sn"] == BOSTA - 60

    k.duvar += 10 * 3600  # uyku: yalnız duvar saati ilerler
    kip.etkinlik()

    assert kip.durum() == GOREVLI
    assert kip.ozet()["bosta_kalan_sn"] is None


def test_uykudan_uyaninca_mutlak_sure_de_dolar() -> None:
    k = _IkiKaynak()
    kip = KipDurumu(saat=k.saat())
    assert kip.durum() == YONETICI
    for _ in range(5):  # 5 dk boyunca dakikada bir kullanıcı eylemi
        k.monoton += 60
        k.duvar += 60
        kip.etkinlik()
    assert kip.durum() == YONETICI

    k.duvar += MUTLAK  # uyku, mutlak süreden uzun
    k.monoton += 1

    assert kip.durum() == GOREVLI
