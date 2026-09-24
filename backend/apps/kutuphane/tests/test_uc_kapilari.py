"""Katalog uçlarının kapıları: 423 kilitli · 403 görevli kipi · 409 parola gerekli.

Üç kapı da BAŞKA katmanlardadır ve katalog uçları onlara tabidir; bu dosya
bunun kanıtıdır. Uç listesi ELLE TUTULMAZ: `apps.kutuphane.urls` çalışma anında
dolaşılır, sonra eklenen her uç bu testlere kendiliğinden girer.

1. **Kilitli** (`apps.okul.lock_middleware`): yönetici parolası kuruluyken
   anahtar bellekte değilse bütün `/api/` yüzeyi 423 `locked` döner. Şifreli
   alan taşıyan uçlar (edinim, komisyon kararı, bağış ön kaydı) buraya dahildir.
2. **Görevli kipi** (`apps.okul.kip_middleware`): izin listesi dışındaki her uç
   403 `kip_yetkisiz`. Kütüphane yüzeyinden izin listesinde etiket doğrulama
   okutması (`library-label-verify` POST; kullanıcı kararı 24.09.2026), F6
   dolaşım masası uçları ve katalog OKUMA (works/copies GET, yanıt daralır)
   vardır — katalog düzenlemek masa işi değildir (CLAUDE.md §2-4).
   Genel dolaşma `apps/okul/tests/test_kip_koruma.py`'dedir; burada katalog
   yüzeyi AÇIKÇA sabitlenir ki listeye sessizce uç eklenmesin.
3. **Parola kurulmamış** (`shared.crypto` fail-closed, §6.3-3): kişi ADI taşıyan
   şifreli alana yazan istek 409 `parola_gerekli` alır. Katalog uçları
   `RequiresAdminPassword` izin sınıfını TAŞIMAZ (kişi sicili yazmazlar); bu
   testler korumanın izin sınıfı olmadan da işlediğini gösterir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.urls import URLPattern, reverse
from rest_framework.test import APIClient

from apps.kutuphane.models import AcquisitionMethod, CommissionDecisionType
from apps.kutuphane.tests import ortak
from apps.kutuphane.urls import urlpatterns
from apps.okul.kip import KIP

pytestmark = pytest.mark.django_db

#: Kilitliyken ve görevli kipinde denenen yöntemler (okuma + bir yazma).
YONTEMLER = ("get", "post")
#: Kütüphane yüzeyinde görevli kipinde açık (uç, yöntem) çiftleri
#: (`apps/okul/kip_izinleri.py`): etiket doğrulama okutması (kullanıcı kararı
#: 24.09.2026), F6 dolaşım masası ve katalog OKUMA (§4.4 tablosu). Yanıtların
#: görevli kipindeki alan listesi `test_masa_gorevli_yuzeyi.py`'dedir.
GOREVLI_ACIK = frozenset(
    {
        ("library-label-verify", "POST"),
        ("library-desk-member", "POST"),
        ("library-checkout", "POST"),
        ("library-return", "POST"),
        ("library-desk-copy-status", "GET"),
        ("library-desk-card-unlock", "POST"),
        ("library-work-list", "GET"),
        ("library-work-detail", "GET"),
        ("library-copy-list", "GET"),
    }
)


def _kutuphane_uclari() -> list[tuple[str, str]]:
    """(URL adı, örnek yol) — `apps.kutuphane.urls`'teki her desen.

    Dönüştürücüler örnek değerle (1) doldurulur; kapılar görünüme hiç
    girmediği için kaydın var olması gerekmez.
    """
    sonuc: list[tuple[str, str]] = []
    for desen in urlpatterns:
        assert isinstance(desen, URLPattern) and desen.name, f"adsız desen: {desen}"
        ornek = reverse(desen.name, kwargs={ad: 1 for ad in desen.pattern.converters})
        sonuc.append((desen.name, ornek))
    return sonuc


def test_dolasma_butun_katalog_yuzeyini_goruyor() -> None:
    """Boş ya da eksik liste yanlış yeşil verirdi."""
    uclar = _kutuphane_uclari()
    adlar = {ad for ad, _ in uclar}

    assert len(uclar) >= 19
    assert {
        "library-policy",
        "library-stats",
        "library-section-list",
        "library-work-list",
        "library-copy-list",
        "library-copy-bulk",
        "library-acquisition-list",
        "library-commission-decision-list",
        "library-donation-intake-list",
        "library-donation-intake-decision",
    } <= adlar
    assert all(yol.startswith("/api/v1/library/") for _, yol in uclar)


# ============================================================ 1. Kilitli → 423
def test_kilitliyken_her_katalog_ucu_423_doner(kilitli: Path) -> None:
    istemci = APIClient()
    kesilmeyen: list[str] = []

    for ad, yol in _kutuphane_uclari():
        for yontem in YONTEMLER:
            yanit = getattr(istemci, yontem)(yol, {}, format="json")
            if yanit.status_code != 423 or yanit.json()["code"] != "locked":
                kesilmeyen.append(f"{yontem.upper()} {yol} ({ad}) → {yanit.status_code}")

    assert kesilmeyen == []


def test_kilit_acilinca_katalog_calisir(kilitli: Path) -> None:
    """Kapı kalıcı değildir: parola girilince aynı uç 200 döner."""
    from apps.okul.services import app_password
    from conftest import TEST_PAROLA

    istemci = APIClient()
    assert istemci.get("/api/v1/library/works/").status_code == 423

    app_password.unlock(password=TEST_PAROLA)

    assert istemci.get("/api/v1/library/works/").status_code == 200


# ============================================================ 2. Görevli kipi → 403
def test_gorevli_kipinde_her_katalog_ucu_403_doner() -> None:
    KIP.gorevliye_gec()
    istemci = APIClient()
    kesilmeyen: list[str] = []

    for ad, yol in _kutuphane_uclari():
        for yontem in YONTEMLER:
            if (ad, yontem.upper()) in GOREVLI_ACIK:
                continue
            yanit = getattr(istemci, yontem)(yol, {}, format="json")
            if yanit.status_code != 403 or yanit.json()["code"] != "kip_yetkisiz":
                kesilmeyen.append(f"{yontem.upper()} {yol} ({ad}) → {yanit.status_code}")

    assert kesilmeyen == []
    assert KIP.durum() == "gorevli", "dolaşma sırasında kip değişti"


def test_katalog_uclarindan_yalniz_masa_isleri_izin_listesinde() -> None:
    """Testi yeşile çekmek için listeye uç eklemek kusurdur (CLAUDE.md §2-4).

    Açık olanlar bilinçli kararlardır: etiket doğrulama okutması (kullanıcı
    kararı 24.09.2026) ve tasarım §4.4 tablosunun masa işleri (F6) — kartla üye
    çözme, ödünç ver, barkodla iade, nüsha durum sorgusu, GA-7 kilidi ve katalog
    okuma (yalnız GET).
    """
    from apps.okul.kip_izinleri import IZIN_LISTESI

    katalog = {ad for ad, _ in _kutuphane_uclari()}
    izinli = {(kural.uc, kural.yontem) for kural in IZIN_LISTESI if kural.uc in katalog}

    assert izinli == GOREVLI_ACIK


# ============================================================ 3. Parolasız → 409
class TestParolasizOrtam:
    """Parola hiç kurulmamış ilk açılış: katalog açılır, kişi adı yazılamaz."""

    PAROLA_GEREKLI = "parola_gerekli"

    def test_kisi_adi_tasimayan_katalog_parolasiz_calisir(self, parolasiz: Path) -> None:
        """Eser, bölüm ve nüsha kişisel veri taşımaz: kurulum bitmeden de girilebilir."""
        istemci = APIClient()

        bolum = istemci.post("/api/v1/library/sections/", {"name": "Edebiyat"}, format="json")
        eser = istemci.post("/api/v1/library/works/", {"title": "Deneme"}, format="json")
        edinim = istemci.post(
            "/api/v1/library/acquisitions/",
            {"method": AcquisitionMethod.EXISTING_STOCK, "date": "2026-09-01"},
            format="json",
        )
        assert [bolum.status_code, eser.status_code, edinim.status_code] == [201, 201, 201]

        nusha = istemci.post(
            "/api/v1/library/copies/",
            {"work": eser.json()["id"], "acquisition": edinim.json()["id"]},
            format="json",
        )
        assert nusha.status_code == 201, nusha.json()

    def test_bagisci_adi_parolasiz_yazilamaz(self, parolasiz: Path) -> None:
        yanit = APIClient().post(
            "/api/v1/library/acquisitions/",
            {
                "method": AcquisitionMethod.EXISTING_STOCK,
                "date": "2026-09-01",
                "source_note": "Selma Yücel",
            },
            format="json",
        )

        assert yanit.status_code == 409
        assert yanit.json()["code"] == self.PAROLA_GEREKLI

    def test_komisyon_baskani_parolasiz_yazilamaz(self, parolasiz: Path) -> None:
        yanit = APIClient().post(
            "/api/v1/library/commission-decisions/",
            {
                "decision_type": CommissionDecisionType.DONATION_REVIEW,
                "decision_date": "2026-09-01",
                "chair_name": "Deniz Korkmaz",
            },
            format="json",
        )

        assert yanit.status_code == 409
        assert yanit.json()["code"] == self.PAROLA_GEREKLI

    def test_bagis_on_kaydinda_bagisci_parolasiz_yazilamaz(self, parolasiz: Path) -> None:
        yanit = APIClient().post(
            "/api/v1/library/donation-intakes/",
            {
                "donor_name": "Selma Yücel",
                "received_date": "2026-09-01",
                "items": [{"title": "Bağış Kitabı"}],
            },
            format="json",
        )

        assert yanit.status_code == 409
        assert yanit.json()["code"] == self.PAROLA_GEREKLI

    def test_okuma_uclari_parolasiz_aciktir(self, parolasiz: Path) -> None:
        """Kurulum sihirbazı ve pano kartı parola kurulmadan da çalışır."""
        istemci = APIClient()

        assert istemci.get("/api/v1/library/policy/").status_code == 200
        assert istemci.get("/api/v1/library/stats/").status_code == 200
        assert istemci.get("/api/v1/library/works/").status_code == 200


# ============================================================ Hata gövdesi sözleşmesi
def test_bulunamayan_kayit_turkce_404_doner() -> None:
    yanit = APIClient().get("/api/v1/library/works/9999/")

    assert yanit.status_code == 404
    govde: dict[str, Any] = yanit.json()
    assert govde == {"code": "not_found", "message": "Kayıt bulunamadı.", "fields": {}}


def test_yumusak_silinmis_kayit_404_doner() -> None:
    eser = ortak.eser()
    eser.delete()

    assert APIClient().get(f"/api/v1/library/works/{eser.pk}/").status_code == 404


def test_servis_reddi_govdeyi_sozlesme_bicimiyle_doldurur() -> None:
    """`{code, message, fields}`: `message` snackbar'a, `fields` form alanına gider."""
    eser = ortak.eser()
    ortak.nusha(eser)

    govde: dict[str, Any] = APIClient().delete(f"/api/v1/library/works/{eser.pk}/").json()

    assert set(govde) == {"code", "message", "fields"}
    assert govde["code"] == "validation_error"
    assert "work" in govde["fields"]
    assert govde["message"] == govde["fields"]["work"][0]
