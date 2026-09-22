"""Zorunlu yönetici parolası (tasarım §4.3, §6.3) — uçtan uca davranış testleri.

Varsayılan test ortamı `backend/conftest.py`'dedir: **parola kurulu + kilit
açık** (sabit `TEST_DEK`, `TEST_PAROLA`, `TEST_KURTARMA_ANAHTARI`). Parolasız
ilk açılış `parolasiz`, kilitli program `kilitli` fixtürüyle kurulur.

Şifreleme iddiaları ORM'e güvenmez, ham SQL ile sütunu okur
(`connection.cursor()`); aksi hâlde şifreli alan kendini çözer ve test yalan
söylerdi.

F1 kod kapısının üç güvenlik maddesi burada AYRI testlerle kanıtlanır:
* "kilitliyken `Student.save()` hata verir" → `TestFailClosed`,
* "guvenlik.json silinince fail-closed" → `TestGuvenlikDosyasiKayip`,
* "parola yokken kişi yazan uç 409" → `test_kisi_yazan_uclar.py`.
"""

from __future__ import annotations

import json
import sqlite3
import time
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from desktop.backup_crypto import (
    config_path,
    decrypt_bytes,
    encrypt_bytes,
    ensure_public_config,
    private_key_from_data_key,
)
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections, transaction
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient

from apps.okul import selectors
from apps.okul.kip import KIP
from apps.okul.models import Personnel, SchoolConfig, Student
from apps.okul.services import app_password
from conftest import TEST_DEK, TEST_KURTARMA_ANAHTARI, TEST_PAROLA
from shared import crypto

YENI_PAROLA = "Baska-Parola-2"

OGRENCI_AD = "EMRE CAN"
OGRENCI_SOYAD = "YILMAZ"


def ogrenci_olustur(**fazlasi: Any) -> Student:
    veri: dict[str, Any] = {
        "first_name": OGRENCI_AD,
        "last_name": OGRENCI_SOYAD,
        "student_number": "101",
        "class_level": 10,
        "class_section": "A",
    }
    veri.update(fazlasi)
    return cast("Student", Student.objects.create(**veri))


def ham_satir(student_id: int) -> tuple[str, str]:
    """ORM'i BYPASS ederek ad-soyad sütunlarını olduğu gibi okur (şifre çözülmez)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT first_name, last_name FROM okul_student WHERE id = %s",
            [student_id],
        )
        satir = cursor.fetchone()
    return (str(satir[0]), str(satir[1]))


def parolasiz_yap() -> None:
    """Test gövdesinde (kişi yazıldıktan SONRA) parolasız duruma geçer."""
    crypto.unload_key()
    app_password.state_path().unlink(missing_ok=True)
    config_path(app_password.state_path().parent).unlink(missing_ok=True)


def baska_kurulumun_durumu(parola: str) -> dict[str, Any]:
    """Aynı parolayla sarmalanmış ama BAŞKA bir DEK taşıyan geçerli güvenlik dosyası."""
    durum = app_password._build_state(
        crypto.new_data_key(), password=parola, recovery_key=app_password.generate_recovery_key()
    )
    durum["gecis"] = app_password.TRANSITION_DONE
    return durum


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def kayip(parmak_izi_yazili: str) -> Path:
    """Güvenlik dosyası kayıp: DB'de parmak izi var, `guvenlik.json` yok, kilitli.

    Silinen dosyanın içeriği döndürülen yolun yanında `.yedek` olarak saklanır
    (geri koyma senaryosu için).
    """
    yol = app_password.state_path()
    yedek = yol.with_name("guvenlik.json.yedek")
    yedek.write_bytes(yol.read_bytes())
    yol.unlink()
    crypto.unload_key()
    return yedek


# ---------------------------------------------------------------------------
# Parola kurma (yalnız ilk kurulumda)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEnable:
    def test_ilk_kurulumda_kurulur_ve_parmak_izi_yazilir(self, parolasiz: Path) -> None:
        kurtarma = app_password.enable(password=YENI_PAROLA)

        assert len(kurtarma.split("-")) == 8
        durum = app_password.read_state()
        assert durum is not None and durum["gecis"] == app_password.TRANSITION_DONE
        assert crypto.is_unlocked() is True
        parmak = crypto.active_fingerprint()
        assert parmak is not None and parmak.startswith("v1:")
        assert SchoolConfig.load().app_password_hash == parmak
        assert config_path(parolasiz).is_file()  # yedek açık anahtarı da yazıldı

    def test_kurulumdan_sonra_kisi_adi_sifreli_yazilir(self, parolasiz: Path) -> None:
        app_password.enable(password=YENI_PAROLA)
        ogrenci = ogrenci_olustur()

        ad, soyad = ham_satir(ogrenci.pk)
        assert OGRENCI_AD not in ad and OGRENCI_SOYAD not in soyad
        # Fernet token'ı 'gAAAA' ile başlar — gerçekten şifrelenmiş.
        assert ad.startswith("gAAAA")
        tazelenmis = Student.objects.get(pk=ogrenci.pk)
        assert tazelenmis.full_name == f"{OGRENCI_AD} {OGRENCI_SOYAD}"

    def test_personel_adi_da_sifrelenir(self) -> None:
        kisi = Personnel.objects.create(first_name="AYŞE", last_name="ÖĞRETMEN")
        with connection.cursor() as cursor:
            cursor.execute("SELECT first_name FROM okul_personnel WHERE id = %s", [kisi.pk])
            (ad,) = cursor.fetchone()
        assert str(ad).startswith("gAAAA")

    def test_kurulum_oncesi_yedek_alinir(
        self, parolasiz: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        etiketler: list[str] = []
        monkeypatch.setattr(app_password, "take_transition_backup", etiketler.append)
        app_password.enable(password=YENI_PAROLA)
        assert etiketler == ["acilis"]

    def test_dosya_tabanli_veritabaninda_gercek_kopya_alinir(self, tmp_path: Path) -> None:
        """Kopyalama mantığının kendisi (gerçek dosya + gerçek SQLite yedek API'si)."""
        veri_anahtari = b"k" * 32
        ensure_public_config(app_password._data_dir(), veri_anahtari, replace=True)
        kaynak = tmp_path / "db.sqlite3"
        with sqlite3.connect(kaynak) as baglanti:
            baglanti.execute("CREATE TABLE deneme (ad TEXT)")
            baglanti.execute("INSERT INTO deneme VALUES ('EMRE')")
        with mock.patch.object(app_password, "database_file", return_value=kaynak):
            hedef = app_password.take_transition_backup("acilis")
        assert hedef is not None
        assert hedef.name.startswith("pre-parola-acilis-")
        geri_yuklenen = tmp_path / "geri-yuklenen.sqlite3"
        geri_yuklenen.write_bytes(decrypt_bytes(hedef.read_bytes(), veri_anahtari))
        with sqlite3.connect(geri_yuklenen) as kopya:
            assert kopya.execute("SELECT ad FROM deneme").fetchone() == ("EMRE",)

    def test_ikinci_kez_kurulamaz(self) -> None:
        with pytest.raises(app_password.AppPasswordError, match="zaten kurulu"):
            app_password.enable(password=YENI_PAROLA)

    def test_kisa_parola_reddedilir(self, parolasiz: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="en az 8"):
            app_password.enable(password="kisa")
        assert app_password.read_state() is None

    def test_ogrenci_varken_reddedilir(self) -> None:
        ogrenci_olustur()
        parolasiz_yap()
        with pytest.raises(app_password.AppPasswordError, match="öğretmen ya da diğer personel"):
            app_password.enable(password=YENI_PAROLA)
        assert app_password.read_state() is None

    def test_personel_varken_reddedilir(self) -> None:
        Personnel.objects.create(first_name="AYŞE", last_name="KAYA")
        parolasiz_yap()
        with pytest.raises(app_password.AppPasswordError, match="öğretmen ya da diğer personel"):
            app_password.enable(password=YENI_PAROLA)

    def test_silinmis_ogrenci_varken_de_reddedilir(self) -> None:
        """Yumuşak silinmiş kişinin adı da kişisel veridir (`all_objects`)."""
        ogrenci_olustur().delete()
        assert not Student.objects.exists()
        parolasiz_yap()
        with pytest.raises(app_password.AppPasswordError, match="öğretmen ya da diğer personel"):
            app_password.enable(password=YENI_PAROLA)

    def test_guvenlik_dosyasi_kayipken_reddedilir(self, kayip: Path) -> None:
        """GA-2: parmak izi doluyken yeni anahtar eski kayıtları okunamaz bırakırdı."""
        with pytest.raises(app_password.AppPasswordError, match="guvenlik.json"):
            app_password.enable(password=YENI_PAROLA)
        assert app_password.read_state() is None

    def test_basarisiz_kurulum_dosyalari_geri_alir(
        self, parolasiz: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def yedek_alinamadi(label: str) -> None:
            raise app_password.AppPasswordError("yedek alınamadı")

        monkeypatch.setattr(app_password, "take_transition_backup", yedek_alinamadi)
        with pytest.raises(app_password.AppPasswordError):
            app_password.enable(password=YENI_PAROLA)
        assert app_password.read_state() is None
        assert not config_path(parolasiz).exists()
        assert SchoolConfig.load().app_password_hash == ""


# ---------------------------------------------------------------------------
# Fail-closed yazma (F1 kod kapısı: kilitliyken Student.save() hata verir)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestFailClosed:
    def test_kilitliyken_student_save_hata_verir(self, kilitli: Path) -> None:
        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            Student(first_name=OGRENCI_AD, last_name=OGRENCI_SOYAD).save()
        assert not Student.all_objects.exists()

    def test_kilitliyken_mevcut_kaydi_kaydetmek_hata_verir(self) -> None:
        """Kilitliyken okunan token düz metin gibi geri yazılamaz (anahtar yok)."""
        ogrenci = ogrenci_olustur()
        app_password.lock()
        kilitli_okunan = Student.objects.get(pk=ogrenci.pk)
        assert kilitli_okunan.first_name.startswith("gAAAA")  # okuma patlamaz
        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            kilitli_okunan.save()
        app_password.unlock(password=TEST_PAROLA)
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_parolasizken_student_save_hata_verir(self, parolasiz: Path) -> None:
        with pytest.raises(crypto.KeyMissingError), transaction.atomic():
            Student.objects.create(first_name=OGRENCI_AD, last_name=OGRENCI_SOYAD)
        assert not Student.all_objects.exists()

    def test_bos_ad_anahtarsiz_yazilabilir(self, kilitli: Path) -> None:
        """Boş dize şifrelenmez: "veri yok" hâli DB'de de boş görünür."""
        ogrenci = Student.objects.create(first_name="", last_name="")
        assert ham_satir(ogrenci.pk) == ("", "")


# ---------------------------------------------------------------------------
# Durum sorgusu (fail-closed): dosya VAR ya da parmak izi dolu
# ---------------------------------------------------------------------------
class TestPasswordSetState:
    def test_varsayilan_ortamda_kurulu_ve_acik(self) -> None:
        """DB istemez: dosya varken parmak izine bakılmaz (her istekte çağrılır)."""
        assert app_password.is_password_set() is True
        assert app_password.security_file_missing() is False
        assert app_password.is_locked() is False

    @pytest.mark.django_db
    def test_parolasiz_ortamda_kurulu_degil(self, parolasiz: Path) -> None:
        assert app_password.is_password_set() is False
        assert app_password.security_file_missing() is False
        assert app_password.is_locked() is False
        durum = app_password.status()
        assert durum["password_set"] is False and durum["security_file_missing"] is False

    @pytest.mark.django_db
    def test_dosya_silinip_parmak_izi_kalinca_kurulu_sayilir(self, kayip: Path) -> None:
        assert app_password.is_password_set() is True
        assert app_password.security_file_missing() is True
        assert app_password.is_locked() is True
        durum = app_password.status()
        assert durum["password_set"] is True
        assert durum["locked"] is True
        assert durum["security_file_missing"] is True

    @pytest.mark.django_db
    def test_require_password_set(self, parolasiz: Path) -> None:
        with pytest.raises(app_password.PasswordRequired) as hata:
            app_password.require_password_set()
        # 409 çevirisi tek sınıftan yapılır: PasswordRequired bir KeyMissingError'dır.
        assert isinstance(hata.value, crypto.KeyMissingError)

    def test_require_password_set_kuruluyken_gecer(self) -> None:
        app_password.require_password_set()


# ---------------------------------------------------------------------------
# Kilit açma / kilitleme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestUnlock:
    def test_dogru_parola_acar(self) -> None:
        ogrenci = ogrenci_olustur()
        app_password.lock()
        assert app_password.is_locked() is True
        # Kilitliyken okuma çöp (token) döner — patlamaz.
        assert Student.objects.get(pk=ogrenci.pk).first_name.startswith("gAAAA")

        app_password.unlock(password=TEST_PAROLA)
        assert app_password.is_locked() is False
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_ilk_kilit_acilisi_parmak_izini_yazar(self, kilitli: Path) -> None:
        assert SchoolConfig.load().app_password_hash == ""
        app_password.unlock(password=TEST_PAROLA)
        assert SchoolConfig.load().app_password_hash == crypto.key_fingerprint(TEST_DEK)

    def test_yanlis_parola_reddedilir(self, kilitli: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
            app_password.unlock(password="yanlis-parola")
        assert app_password.is_locked() is True

    def test_kilit_acma_bayat_yedekleme_json_u_onarir(self, kilitli: Path) -> None:
        """Çapraz-DEK geri yükleme artığı gibi UYUMSUZ bir yedekleme.json kilidi
        kalıcı kilitlememeli: DB parmak izi DEK'i kanıtladıktan sonra otorite
        dosya değil anahtardır (replace=True — birleşme incelemesi)."""
        yol = config_path(kilitli)
        ensure_public_config(kilitli, b"x" * 32, replace=True)  # yabancı anahtar
        yabanci = yol.read_bytes()

        app_password.unlock(password=TEST_PAROLA)

        assert app_password.is_locked() is False
        assert yol.read_bytes() != yabanci  # dosya gerçek DEK'le onarıldı

    def test_yanlis_parola_kademeli_gecikme_uygular(
        self, kilitli: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kalıcı kilit YOK; art arda hatada süreç içi gecikme artar (bkz. modül notu)."""
        monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 0.5))
        beklemeler: list[float] = []
        monkeypatch.setattr(time, "sleep", beklemeler.append)
        for _ in range(3):
            with pytest.raises(app_password.AppPasswordError):
                app_password.unlock(password="yanlis")
        assert beklemeler == [0.5, 0.5]  # ilk deneme gecikmesiz, sonrakiler tavanda
        # Doğru parola sayacı sıfırlar.
        app_password.unlock(password=TEST_PAROLA)
        beklemeler.clear()
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError):
            app_password.unlock(password="yanlis")
        assert beklemeler == []

    def test_parola_kurulu_degilken_acilamaz(self, parolasiz: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="kurulu değil"):
            app_password.unlock(password=TEST_PAROLA)

    def test_guvenlik_dosyasi_kayipken_acilamaz(self, kayip: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="bulunamadı"):
            app_password.unlock(password=TEST_PAROLA)

    def test_baska_veritabaninin_guvenlik_dosyasi_reddedilir(self, kilitli: Path) -> None:
        """Parmak izi uyuşmazlığı → sessiz bozulma yerine açık ret."""
        config, _ = SchoolConfig.objects.get_or_create(pk=SchoolConfig.SINGLETON_PK)
        config.app_password_hash = "v1:" + "0" * 64
        config.save(update_fields=["app_password_hash"])
        with pytest.raises(app_password.AppPasswordError, match="ait değil"):
            app_password.unlock(password=TEST_PAROLA)


# ---------------------------------------------------------------------------
# Parola doğrulama (kip yükseltmesi, app/quit)
# ---------------------------------------------------------------------------
class TestVerifyPassword:
    def test_dogru_parola_gecer(self) -> None:
        app_password.verify_password(TEST_PAROLA)

    def test_yanlis_parola_reddedilir_ve_gecikme_uygulanir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_password, "FAILURE_DELAYS", (0.0, 0.5))
        beklemeler: list[float] = []
        monkeypatch.setattr(time, "sleep", beklemeler.append)
        for _ in range(2):
            with pytest.raises(app_password.AppPasswordError, match="^Parola hatalı.$"):
                app_password.verify_password("yanlis-parola")
        assert beklemeler == [0.5]
        assert crypto.is_unlocked() is True  # doğrulama kilidi etkilemez

    def test_baska_kurulumun_dosyasiyla_yukseltme_yapilamaz(self) -> None:
        """Parolası bilinen yabancı bir guvenlik.json konursa sarmal açılır ama
        DEK yüklü anahtarla eşleşmez → "Parola hatalı."."""
        app_password._write_state(baska_kurulumun_durumu(TEST_PAROLA))
        with pytest.raises(app_password.AppPasswordError, match="^Parola hatalı.$"):
            app_password.verify_password(TEST_PAROLA)

    def test_kilitliyken_dogrulanamaz(self, kilitli: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="kilitli"):
            app_password.verify_password(TEST_PAROLA)

    @pytest.mark.django_db
    def test_guvenlik_dosyasi_kayipken_dogrulanamaz(self, kayip: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="bulunamadı"):
            app_password.verify_password(TEST_PAROLA)


# ---------------------------------------------------------------------------
# Kurtarma anahtarı
# ---------------------------------------------------------------------------

#: Normalleştirme örnek tablosu — ön yüzde AYNI tablo sınanır
#: (`frontend/src/modules/guvenlik/KurtarmaAnahtariPaneli.test.tsx`,
#: "normalleştirme örnek tablosu"). Biri değişirse öteki de değişmeli.
NORMALLESTIRME_ORNEKLERI: list[tuple[str, str]] = [
    (" test-kurt ", "TESTKURT"),
    ("o0i1b8", "OOIIBB"),
    ("abci-ABCI-ABCİ-ABCı", "ABCIABCIABCIABCI"),
    ("TARİ tarı Tari", "TARITARITARI"),
    ("ŞAKA-12", "AKAI2"),
]


@pytest.mark.parametrize(("yazim", "beklenen"), NORMALLESTIRME_ORNEKLERI)
def test_kurtarma_anahtari_normallestirme_ornek_tablosu(yazim: str, beklenen: str) -> None:
    assert app_password.normalize_recovery_key(yazim) == beklenen


@pytest.mark.django_db
class TestRecovery:
    def test_kurtarma_anahtariyla_acilir_ve_parola_yenilenir(self, kilitli: Path) -> None:
        app_password.unlock_with_recovery(
            recovery_key=TEST_KURTARMA_ANAHTARI, new_password=YENI_PAROLA
        )
        assert app_password.is_locked() is False

        # Eski parola artık geçersiz, yenisi geçerli.
        app_password.lock()
        with pytest.raises(app_password.AppPasswordError):
            app_password.unlock(password=TEST_PAROLA)
        app_password.unlock(password=YENI_PAROLA)

    def test_kurtarma_anahtari_bicimden_bagimsiz_kabul_edilir(self, kilitli: Path) -> None:
        bozuk_bicim = TEST_KURTARMA_ANAHTARI.replace("-", " ").lower()
        app_password.unlock_with_recovery(recovery_key=bozuk_bicim, new_password=YENI_PAROLA)
        assert app_password.is_locked() is False

    def test_turkce_klavyede_buyuk_harfle_yazilan_anahtar_kabul_edilir(self, kilitli: Path) -> None:
        """Türkçe klavyede Shift/CapsLock + i noktalı "İ" (U+0130) üretir."""
        turkce = TEST_KURTARMA_ANAHTARI.replace("I", "İ")
        assert "İ" in turkce
        app_password.unlock_with_recovery(recovery_key=turkce, new_password=YENI_PAROLA)
        assert app_password.is_locked() is False

    def test_yanlis_kurtarma_anahtari_reddedilir(self, kilitli: Path) -> None:
        with pytest.raises(app_password.AppPasswordError, match="Kurtarma anahtarı hatalı"):
            app_password.unlock_with_recovery(
                recovery_key="AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH",
                new_password=YENI_PAROLA,
            )

    def test_kurtarma_anahtari_parola_degisince_gecerli_kalir(self) -> None:
        """Zarf şifreleme: parola sarmalı değişir, kurtarma sarmalı DEĞİŞMEZ."""
        app_password.change_password(current_password=TEST_PAROLA, new_password=YENI_PAROLA)
        app_password.lock()
        app_password.unlock_with_recovery(
            recovery_key=TEST_KURTARMA_ANAHTARI, new_password="Ucuncu-Parola-3"
        )
        assert app_password.is_locked() is False


# ---------------------------------------------------------------------------
# Parola değiştirme
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.usefixtures("parmak_izi_yazili")
class TestChangePassword:
    def test_veri_yeniden_sifrelenmez_ama_okunur_kalir(self) -> None:
        ogrenci = ogrenci_olustur()
        onceki_token, _ = ham_satir(ogrenci.pk)

        app_password.change_password(current_password=TEST_PAROLA, new_password=YENI_PAROLA)
        sonraki_token, _ = ham_satir(ogrenci.pk)
        # Veri anahtarı değişmediği için satırlara DOKUNULMAZ (eski yedekler de açılabilir kalır).
        assert sonraki_token == onceki_token

        app_password.lock()
        app_password.unlock(password=YENI_PAROLA)
        assert Student.objects.get(pk=ogrenci.pk).first_name == OGRENCI_AD

    def test_kor_indeks_parola_degisiminden_sonra_ayni_kalir(self) -> None:
        """T14: kör indeks anahtarı DEK'ten türer; parola değişimi indeksi bozmaz."""
        onceki = crypto.blind_index("101")
        app_password.change_password(current_password=TEST_PAROLA, new_password=YENI_PAROLA)
        app_password.lock()
        app_password.unlock(password=YENI_PAROLA)
        assert crypto.blind_index("101") == onceki

    def test_yanlis_mevcut_parola_reddedilir(self) -> None:
        with pytest.raises(app_password.AppPasswordError, match="Parola hatalı"):
            app_password.change_password(current_password="yanlis", new_password=YENI_PAROLA)


# ---------------------------------------------------------------------------
# Yarım kalan kurulum geçişi (elektrik kesintisi senaryosu)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestInterruptedTransition:
    def test_kurulum_yarida_kalirsa_acilista_tamamlanir(self, parolasiz: Path) -> None:
        """Dosya yazıldı, parmak izi yazılamadan kesildi → anahtar kayıp değil, tamamlanır."""
        with (
            mock.patch.object(app_password, "_rewrite_rows", side_effect=RuntimeError("kesinti")),
            pytest.raises(RuntimeError),
        ):
            app_password.enable(password=YENI_PAROLA)
        crypto.unload_key()  # program kapandı/elektrik kesildi

        durum = app_password.status()
        assert durum["password_set"] is True
        assert durum["transition_pending"] is True
        assert SchoolConfig.load().app_password_hash == ""

        # Kilit açma geçişi kaldığı yerden tamamlar.
        app_password.unlock(password=YENI_PAROLA)
        assert app_password.status()["transition_pending"] is False
        assert SchoolConfig.load().app_password_hash.startswith("v1:")

    def test_yarim_sifreli_tablo_okunabilir_ve_tekrar_kosulabilir(self) -> None:
        """Satırların bir kısmı düz kalsa bile okuma patlamaz, `force` koşusu düzeltir."""
        sifreli = ogrenci_olustur()
        duz = ogrenci_olustur(student_number="102", first_name="ZEYNEP", last_name="KAYA")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE okul_student SET first_name = %s WHERE id = %s", ["ZEYNEP", duz.pk]
            )

        okunan = {o.pk: o.first_name for o in Student.objects.all()}
        assert okunan[sifreli.pk] == OGRENCI_AD  # şifreli satır çözüldü
        assert okunan[duz.pk] == "ZEYNEP"  # düz satır olduğu gibi geldi

        sonuc = app_password.resume_pending(force=True)
        assert sonuc["resumed"] is True
        assert ham_satir(duz.pk)[0].startswith("gAAAA")
        # Fikirdeşlik: zaten şifreli satır ÇİFT şifrelenmez.
        assert Student.objects.get(pk=sifreli.pk).first_name == OGRENCI_AD

    def test_bozuk_guvenlik_dosyasi_turkce_hata_verir(self) -> None:
        app_password.state_path().write_text("bu json değil", encoding="utf-8")
        with pytest.raises(app_password.AppPasswordError, match="bozuk"):
            app_password.read_state()

    def test_cozme_gecisi_yoktur(self) -> None:
        """§6.3-6: parolasız dal söküldü — çözme geçişi ve kaldırma işlevi yok."""
        for ad in ("disable", "_run_decrypt_pass", "TRANSITION_DECRYPTING", "_archive_state"):
            assert not hasattr(app_password, ad), ad
        for ad in ("plaintext_writes", "writes_encrypted"):
            assert not hasattr(crypto, ad), ad


# ---------------------------------------------------------------------------
# Eşleştirme / arama davranışı (ad şifreli — selector'lar Python'da)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLookupBehaviour:
    def test_ad_filtresi_orm_ile_CALISMAZ(self) -> None:
        """Şifreli alanda DB filtresi daima boş döner — yeni ad sorgusu ORM'e yazılmaz."""
        ogrenci_olustur()
        assert Student.objects.filter(first_name=OGRENCI_AD).first() is None

    def test_ad_aramasi_selector_uzerinden_bozulmaz(self) -> None:
        ogrenci = ogrenci_olustur()
        bulunan = selectors.student_list(search="yilmaz")
        assert [o.pk for o in bulunan] == [ogrenci.pk]

    def test_personel_ad_siralamasi_python_tarafinda(self) -> None:
        Personnel.objects.create(first_name="ZEYNEP", last_name="ÇELİK")
        Personnel.objects.create(first_name="AHMET", last_name="AK")
        sirali = selectors.personnel_sorted()
        assert [p.first_name for p in sirali] == ["AHMET", "ZEYNEP"]


# ---------------------------------------------------------------------------
# API + kilit kapısı
# ---------------------------------------------------------------------------
class TestSecurityApi:
    def test_durum_ucu(self, client: APIClient) -> None:
        resp = client.get("/api/v1/security/status/")
        assert resp.status_code == 200
        veri = resp.json()
        assert veri["password_set"] is True
        assert veri["locked"] is False
        assert veri["security_file_missing"] is False
        assert "ad" in veri["protected_fields"]

    @pytest.mark.django_db
    def test_parolasiz_durum_ucu(self, client: APIClient, parolasiz: Path) -> None:
        veri = client.get("/api/v1/security/status/").json()
        assert veri["password_set"] is False
        assert veri["locked"] is False
        assert veri["security_file_missing"] is False

    @pytest.mark.django_db
    def test_kurma_kilitleme_acma_akisi(self, client: APIClient, parolasiz: Path) -> None:
        resp = client.post("/api/v1/security/enable/", {"password": YENI_PAROLA}, format="json")
        assert resp.status_code == 201
        assert len(resp.json()["recovery_key"].split("-")) == 8

        assert client.post("/api/v1/security/lock/").json()["locked"] is True
        resp = client.post("/api/v1/security/unlock/", {"password": "yanlis"}, format="json")
        assert resp.status_code == 400
        assert resp.json()["code"] == "validation_error"

        resp = client.post("/api/v1/security/unlock/", {"password": YENI_PAROLA}, format="json")
        assert resp.status_code == 200
        assert resp.json()["locked"] is False

    @pytest.mark.django_db
    def test_kurulu_parola_yeniden_kurulamaz(self, client: APIClient) -> None:
        resp = client.post("/api/v1/security/enable/", {"password": YENI_PAROLA}, format="json")
        assert resp.status_code == 400
        assert "zaten kurulu" in resp.json()["message"]

    @pytest.mark.django_db
    def test_kurtarma_ucu(self, client: APIClient, kilitli: Path) -> None:
        resp = client.post(
            "/api/v1/security/recover/",
            {"recovery_key": TEST_KURTARMA_ANAHTARI, "new_password": YENI_PAROLA},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["locked"] is False

    def test_kaldirma_ucu_yoktur(self, client: APIClient) -> None:
        """§6.3-6: `security/disable/` söküldü; yol ne adla ne adresle çözülür."""
        with pytest.raises(NoReverseMatch):
            reverse("security-disable")
        resp = client.post("/api/v1/security/disable/", {"password": TEST_PAROLA}, format="json")
        assert resp.status_code == 404

    @pytest.mark.django_db
    def test_parola_degistirme_ucu(self, client: APIClient) -> None:
        resp = client.post(
            "/api/v1/security/change-password/",
            {"current_password": TEST_PAROLA, "new_password": YENI_PAROLA},
            format="json",
        )
        assert resp.status_code == 200
        client.post("/api/v1/security/lock/")
        resp = client.post("/api/v1/security/unlock/", {"password": YENI_PAROLA}, format="json")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestLockMiddleware:
    """Kilit kapısı (`apps.okul.lock_middleware`) — settings'te bağlı."""

    def test_kilitliyken_veri_uclari_423_doner(self, client: APIClient, kilitli: Path) -> None:
        resp = client.get("/api/v1/students/")
        assert resp.status_code == 423
        assert resp.json()["code"] == "locked"
        assert "yönetici parolası" in resp.json()["message"]

    def test_kilitliyken_acilis_saglik_ucu_calisir(self, client: APIClient, kilitli: Path) -> None:
        """`desktop/server.py` açılışta bu ucu çağırır; 423 dönseydi program AÇILMAZDI."""
        assert client.get("/api/v1/setup/status/").status_code == 200
        # Kurulum sihirbazının YAZMA uçları yine kapalı.
        assert client.post("/api/v1/setup/complete/").status_code == 423

    def test_kilitliyken_guvenlik_uclari_calisir(self, client: APIClient, kilitli: Path) -> None:
        assert client.get("/api/v1/security/status/").status_code == 200
        resp = client.post("/api/v1/security/unlock/", {"password": TEST_PAROLA}, format="json")
        assert resp.status_code == 200
        # Kilit açıldıktan sonra veri uçları normale döner.
        assert client.get("/api/v1/students/").status_code == 200

    def test_parolasiz_kipte_kapi_gecirir(self, client: APIClient, parolasiz: Path) -> None:
        """Kurulum durumunda okuma açıktır; kişi yazma izin sınıfıyla 409 alır."""
        assert client.get("/api/v1/students/").status_code == 200


# ---------------------------------------------------------------------------
# Güvenlik dosyası kayıp kilidi (F1 kod kapısı: guvenlik.json silinince fail-closed)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestGuvenlikDosyasiKayip:
    def test_guvenlik_json_silinince_fail_closed(self, client: APIClient, kayip: Path) -> None:
        """Kilitliyken dosya silinir: program "parolasız"a DÖNMEZ; veri uçları 423
        `guvenlik_dosyasi_kayip`, kişi yazma 423 (409 değil), yeni parola kurulamaz."""
        resp = client.get("/api/v1/students/")
        assert resp.status_code == 423
        assert resp.json() == {
            "code": "guvenlik_dosyasi_kayip",
            "message": (
                "Güvenlik dosyası (guvenlik.json) bulunamadı ya da okunamıyor. Kayıtlar "
                "açılamaz. Dosyanın sağlam bir kopyasını veri klasörüne geri koyun ya da "
                "bir yedekten geri yükleyin."
            ),
            "fields": {},
        }
        yazma = client.post(
            "/api/v1/students/", {"first_name": "A", "last_name": "B"}, format="json"
        )
        assert yazma.status_code == 423
        kurma = client.post("/api/v1/security/enable/", {"password": YENI_PAROLA}, format="json")
        assert kurma.status_code == 423
        assert app_password.read_state() is None

    def test_acik_kalan_yollar(self, client: APIClient, kayip: Path) -> None:
        assert client.get("/api/v1/setup/status/").status_code == 200
        durum = client.get("/api/v1/security/status/")
        assert durum.status_code == 200
        assert durum.json()["security_file_missing"] is True
        assert durum.json()["password_set"] is True
        assert client.get("/api/v1/backups/").status_code == 200
        # Kip durumu salt okurdur; kapıdan geçer (ucun kendisi B kolunundur).
        assert client.get("/api/v1/security/mode/").status_code != 423

    def test_kilit_acma_ve_diger_guvenlik_uclari_kapali(
        self, client: APIClient, kayip: Path
    ) -> None:
        for yol in (
            "/api/v1/security/unlock/",
            "/api/v1/security/recover/",
            "/api/v1/security/change-password/",
        ):
            resp = client.post(yol, {"password": TEST_PAROLA}, format="json")
            assert resp.status_code == 423, yol
            assert resp.json()["code"] == "guvenlik_dosyasi_kayip"
        assert client.get("/api/v1/updates/latest/").status_code == 423

    def test_anahtar_bellekteyken_dosya_kaybolsa_da_kapi_kapanir(
        self, client: APIClient, parmak_izi_yazili: str
    ) -> None:
        app_password.state_path().unlink()
        assert crypto.is_unlocked() is True
        resp = client.get("/api/v1/students/")
        assert resp.status_code == 423
        assert resp.json()["code"] == "guvenlik_dosyasi_kayip"

    def test_dosya_geri_konunca_olagan_kilide_doner(self, client: APIClient, kayip: Path) -> None:
        app_password.state_path().write_bytes(kayip.read_bytes())
        resp = client.get("/api/v1/students/")
        assert resp.status_code == 423
        assert resp.json()["code"] == "locked"
        acma = client.post("/api/v1/security/unlock/", {"password": TEST_PAROLA}, format="json")
        assert acma.status_code == 200
        assert client.get("/api/v1/students/").status_code == 200

    def test_yedekten_geri_yukleme_ile_kayip_kilitten_cikilir(
        self,
        client: APIClient,
        kayip: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Çıkış yolu gerçekten çalışır: geri yükleme ucu kayıp kilidinde açıktır ve
        `guvenlik.json`'u yedeğin kurtarma başlığından yeniden yazar."""
        # Yedek, dosya kaybolmadan önceki guvenlik.json'u başlığında taşır (günlük yedek deseni).
        icerik_yolu = tmp_path / "yedek-icerik.sqlite3"
        with sqlite3.connect(icerik_yolu) as baglanti:
            baglanti.execute("CREATE TABLE kayit (deger TEXT)")
        yedek = app_password.backup_dir() / "gunluk-2026-09-21.kdbak"
        yedek.parent.mkdir(parents=True, exist_ok=True)
        yedek.write_bytes(
            encrypt_bytes(
                icerik_yolu.read_bytes(),
                private_key_from_data_key(TEST_DEK).public_key(),
                recovery_header=kayip.read_bytes(),
            )
        )
        hedef_db = tmp_path / "canli" / "db.sqlite3"
        monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(hedef_db))
        # Test veritabanı bellek içidir; takas öncesi kapatma onu yok ederdi.
        monkeypatch.setattr(connections, "close_all", lambda: None)

        liste = client.get("/api/v1/backups/")
        assert [s["name"] for s in liste.json()["backups"]] == [yedek.name]
        resp = client.post(
            "/api/v1/backups/restore/",
            {"name": yedek.name, "password": TEST_PAROLA},
            format="json",
        )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["state_written"] is True
        assert app_password.state_path().read_bytes() == kayip.read_bytes()
        durum = app_password.read_state()
        assert durum is not None
        assert app_password._unwrap_with_password(durum, TEST_PAROLA) == TEST_DEK


# Dosya SİLİNMEZ ama kullanılamaz hâle gelir (boşaltılır, bozulur, bölümü eksik
# kalır). Kural `desktop.backup_crypto.is_usable_security_state` — günlük yedeğin
# başlık kuralıyla aynı.
_KULLANILAMAZ_GUVENLIK = {
    "bos": b"",
    "bozuk_json": b"{bozuk",
    "sozluk_degil": b"[]",
    "bolumler_eksik": b'{"surum": 1, "gecis": "TAMAM"}',
}


@pytest.mark.django_db
@pytest.mark.parametrize("icerik", _KULLANILAMAZ_GUVENLIK.values(), ids=_KULLANILAMAZ_GUVENLIK)
class TestKullanilamazGuvenlikDosyasi:
    """Denetçi bulgusu: boş/bozuk guvenlik.json'da durum ucu 500, kilit ve kayıp ekranı
    görünmüyor, geri yükleme 423 ile kapalıydı. Artık kayıp kilidiyle aynı sınıftır."""

    @pytest.fixture
    def bozuk(self, parmak_izi_yazili: str, icerik: bytes) -> bytes:
        """Kilitliyken dosyanın içi bozulur; sağlam içerik döndürülür (geri koyma için)."""
        yol = app_password.state_path()
        saglam = yol.read_bytes()
        yol.write_bytes(icerik)
        crypto.unload_key()
        return saglam

    def test_durum_ucu_500_degil_kayip_bildirir(self, client: APIClient, bozuk: bytes) -> None:
        resp = client.get("/api/v1/security/status/")

        assert resp.status_code == 200, resp.content
        veri = resp.json()
        assert veri["security_file_missing"] is True
        assert veri["password_set"] is True
        assert veri["transition_pending"] is False
        assert app_password.security_file_missing() is True
        assert KIP.durum() == "guvenlik_dosyasi_kayip"

    def test_kayip_kilidi_uygulanir_cikis_yollari_acik(
        self, client: APIClient, bozuk: bytes
    ) -> None:
        veri = client.get("/api/v1/students/")
        assert veri.status_code == 423
        assert veri.json()["code"] == "guvenlik_dosyasi_kayip"
        kurma = client.post("/api/v1/security/enable/", {"password": YENI_PAROLA}, format="json")
        assert kurma.status_code == 423
        assert client.get("/api/v1/backups/").status_code == 200
        eksik = client.post("/api/v1/backups/restore/", {}, format="json")
        assert eksik.status_code == 400  # görünüme ulaştı: doğrulama reddi, 423 değil

    def test_saglam_dosya_geri_konunca_olagan_kilide_doner(
        self, client: APIClient, bozuk: bytes
    ) -> None:
        app_password.state_path().write_bytes(bozuk)

        assert client.get("/api/v1/security/status/").json()["security_file_missing"] is False
        assert client.get("/api/v1/students/").json()["code"] == "locked"

    def test_yedekten_geri_yukleme_bozuk_dosyayi_arsivleyip_basligi_yazar(
        self,
        client: APIClient,
        bozuk: bytes,
        icerik: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        icerik_yolu = tmp_path / "yedek-icerik.sqlite3"
        with sqlite3.connect(icerik_yolu) as baglanti:
            baglanti.execute("CREATE TABLE kayit (deger TEXT)")
        yedek = app_password.backup_dir() / "gunluk-2026-09-21.kdbak"
        yedek.parent.mkdir(parents=True, exist_ok=True)
        yedek.write_bytes(
            encrypt_bytes(
                icerik_yolu.read_bytes(),
                private_key_from_data_key(TEST_DEK).public_key(),
                recovery_header=bozuk,
            )
        )
        monkeypatch.setitem(
            settings.DATABASES["default"], "NAME", str(tmp_path / "canli" / "db.sqlite3")
        )
        monkeypatch.setattr(connections, "close_all", lambda: None)

        resp = client.post(
            "/api/v1/backups/restore/",
            {"name": yedek.name, "password": TEST_PAROLA},
            format="json",
        )

        assert resp.status_code == 200, resp.json()
        assert resp.json()["state_written"] is True
        assert app_password.state_path().read_bytes() == bozuk
        # Bozuk dosya silinmez, arşivlenir.
        arsivler = list(app_password.state_path().parent.glob("guvenlik-arsiv-*.json"))
        assert [a.read_bytes() for a in arsivler] == [icerik]


def test_parmak_izi_yokken_bozuk_dosya_da_kayip_sayilir_ve_db_istemez() -> None:
    """Fail-closed: dosyanın neyi koruduğu bilinemez; kural parmak izinden bağımsızdır.
    Dosya varken karar yalnız dosyadan verilir (DB'ye gidilmez — bu test DB istemez;
    `security_file_missing` her API isteğinde çağrılır)."""
    app_password.state_path().write_bytes(b"")
    crypto.unload_key()

    assert app_password.security_file_missing() is True


@pytest.mark.django_db
def test_parmak_izi_yokken_bozuk_dosya_durum_ozetinde_kayip_ve_sifirlanabilir() -> None:
    """Durum özeti kayıp hâlinde sıfırlama yolunun koşullarını da sorar (DB'ye gider:
    parmak izi + şifreli tablolar; F1-E). Parmak izi boş ve kişi yokken yol açıktır."""
    app_password.state_path().write_bytes(b"")
    crypto.unload_key()

    durum = app_password.status()
    assert durum["security_file_missing"] is True
    assert durum["password_set"] is True
    assert durum["reset_available"] is True


def test_bozuk_dosya_iletisi_olmayan_otomatik_kopyayi_anmaz() -> None:
    """Eski ileti "veri klasöründeki yedeğinizden geri alın" diyordu; öyle bir kopya yok."""
    app_password.state_path().write_text("bu json değil", encoding="utf-8")

    with pytest.raises(app_password.AppPasswordError) as hata:
        app_password.read_state()

    assert "yedeğinizden" not in str(hata.value)
    assert "bir yedekten geri yükleyin" in str(hata.value)


# ---------------------------------------------------------------------------
# Konsol kurtarma aracı
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestManagementCommand:
    """`manage.py app_password …` — arayüz açılamadığında destek elinin yolu."""

    def _kosu(self, *args: str, **secenekler: Any) -> str:
        cikti = StringIO()
        call_command("app_password", *args, stdout=cikti, **secenekler)
        return cikti.getvalue()

    def test_durum_ozet_basar(self) -> None:
        cikti = self._kosu("status")
        assert "Parola kurulu    : evet" in cikti
        assert "ad" in cikti

    def test_durum_kayip_dosyayi_bildirir(self, kayip: Path) -> None:
        cikti = self._kosu("status")
        assert "KAYIP" in cikti
        assert "guvenlik.json" in cikti

    def test_kur(self, parolasiz: Path) -> None:
        cikti = self._kosu("enable", password=YENI_PAROLA)
        assert "KURTARMA ANAHTARI" in cikti
        assert app_password.is_password_set() is True

    def test_kaldirma_komutu_yoktur(self) -> None:
        with pytest.raises(CommandError):
            self._kosu("disable", password=TEST_PAROLA)

    def test_kurtar_yeni_parola_belirler(self, kilitli: Path) -> None:
        self._kosu("recover", recovery_key=TEST_KURTARMA_ANAHTARI, new_password=YENI_PAROLA)
        assert app_password.is_locked() is False

    def test_yanlis_parola_command_error_verir(self, kilitli: Path) -> None:
        with pytest.raises(CommandError, match="Parola hatalı"):
            self._kosu("resume", password="yanlis-parola")

    def test_resume_force_yeniden_kosar(self) -> None:
        ogrenci = ogrenci_olustur()
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE okul_student SET first_name = %s WHERE id = %s", [OGRENCI_AD, ogrenci.pk]
            )
        cikti = self._kosu("resume", password=TEST_PAROLA, force=True)
        assert "Geçiş tamamlandı" in cikti
        assert ham_satir(ogrenci.pk)[0].startswith("gAAAA")


def test_varsayilan_ortamin_guvenlik_dosyasi_json_dur() -> None:
    """conftest sözleşmesi: geçerli, TAMAM damgalı bir durum dosyası (DB istemez)."""
    durum = json.loads(app_password.state_path().read_text(encoding="utf-8"))
    assert durum["gecis"] == app_password.TRANSITION_DONE
    assert app_password._unwrap_with_password(durum, TEST_PAROLA) == TEST_DEK
    assert crypto.active_fingerprint() == crypto.key_fingerprint(TEST_DEK)
