"""Kişi yazan uçların yönetici parolası kapısı (tasarım §6.3-2, F1 kod kapısı).

"Parola yokken kişi yazan uç 409" maddesinin kanıtı. Test `config.urls`'ün
BÜTÜN desenlerini dolaşır:

1. `RequiresAdminPassword` taşıyan uçlar kümesi, aşağıdaki AÇIK listeye
   (`KISI_YAZAN_UCLAR`) birebir eşit olmalıdır.
2. Liste dışındaki `/api/` uçları da ANLIK GÖRÜNTÜYLE (`DIGER_UCLAR`)
   sabitlenir: yeni bir uç eklenince test düşer ve ekleyen, ucun kişi yazıp
   yazmadığına bilinçli karar verir (kişi yazıyorsa izin sınıfını takar ve
   üstteki listeye, yazmıyorsa alttaki listeye ekler).
3. `parolasiz` ortamda (ilk açılış, parola kurulmamış) listedeki her uç, desteklediği
   her yazma yöntemiyle **409 `parola_gerekli`** döner; okuma yöntemleri açıktır.

Savunma derinliği: izin sınıfı unutulsa bile şifreli alan anahtarsız yazmaz
(`KeyMissingError` → yine 409; `shared/tests/test_exceptions.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from rest_framework.test import APIClient

from apps.okul.models import Student
from apps.okul.permissions import RequiresAdminPassword

# Kişi (öğrenci/personel; F6'da üyelik) yazan uçlar — izin sınıfını taşımalıdır.
# Ayrılış, birleştirme (F1-C) ve ayrılış havuzu kararı (F1 eki 7) da kişi yazar.
KISI_YAZAN_UCLAR = frozenset(
    {
        "student-list",
        "student-detail",
        "student-leave",
        "personnel-list",
        "personnel-detail",
        "personnel-leave",
        "personnel-merge",
        "import-students-preview",
        "import-students-commit",
        "import-personnel-preview",
        "import-personnel-commit",
        "leave-pool-resolve",
    }
)

# Anlık görüntü: kişi YAZMAYAN bütün `/api/` uçları. Yeni uç → bilinçli sınıflandırma.
DIGER_UCLAR = frozenset(
    {
        "backup-list",
        "backup-restore",
        "class-section-detail",
        "class-section-list",
        "encrypted-backup-download",
        "grade-levels",
        "holiday-detail",
        "holiday-list",
        "holiday-seed",
        # Havuz listesi yalnız okur (GET); karar ucu yukarıdaki listededir.
        "leave-pool",
        # Katalog uçları (F2) kişi SİCİLİ yazmaz: eser, nüsha, edinim, bölüm ve
        # bağış ön kaydı kütüphane kayıtlarıdır. Bağışçı ve komisyon başkanı adı
        # şifreli alanlardır; parola kurulmadan onlara yazan istek izin sınıfı
        # OLMADAN da 409 `parola_gerekli` alır (fail-closed, §6.3-3) — kanıt
        # `apps/kutuphane/tests/test_uc_kapilari.py`.
        "library-acquisition-detail",
        "library-acquisition-list",
        "library-commission-decision-detail",
        "library-commission-decision-list",
        "library-copy-bulk",
        "library-copy-detail",
        "library-copy-list",
        "library-donation-intake-cancel",
        "library-donation-intake-decision",
        "library-donation-intake-detail",
        "library-donation-intake-item-detail",
        "library-donation-intake-items",
        "library-donation-intake-list",
        "library-import-template",
        "library-policy",
        "library-section-detail",
        "library-section-list",
        "library-stats",
        "library-work-detail",
        "library-work-list",
        "school-year-activate",
        "school-year-list",
        "school-year-terms",
        "security-change-password",
        "security-enable",
        "security-lock",
        "security-mode",
        "security-mode-admin",
        "security-mode-staff",
        "security-recover",
        "security-recovery-key-confirm",
        "security-recovery-key-pdf",
        "security-recovery-key-renew",
        "security-state-reset",
        "security-status",
        "security-unlock",
        "setup-complete",
        "setup-roadmap",
        "setup-school-config",
        "setup-status",
        "template-personnel",
        "template-students",
        "update-installer",
        "update-latest",
    }
)

YAZMA_YONTEMLERI = ("post", "put", "patch", "delete")

PAROLA_GEREKLI_GOVDESI = {
    "code": "parola_gerekli",
    "message": "Kişi kaydı için önce yönetici parolasını kurun (Kurulum Sihirbazı'nın ilk adımı).",
    "fields": {},
}


def _desenler(
    resolver: URLResolver | None = None, onek: str = ""
) -> Iterator[tuple[str, URLPattern]]:
    """(tam yol şablonu, desen) çiftleri — iç içe `include`'lar dahil."""
    kok = resolver if resolver is not None else get_resolver()
    for desen in kok.url_patterns:
        yol = onek + str(desen.pattern)
        if isinstance(desen, URLResolver):
            yield from _desenler(desen, yol)
        else:
            yield yol, desen


def _api_uclari() -> dict[str, URLPattern]:
    """Adlı bütün `/api/` desenleri (SPA catch-all `api/` dışında kalır)."""
    uclar: dict[str, URLPattern] = {}
    for yol, desen in _desenler():
        if yol.startswith("api/"):
            assert desen.name, f"Adsız API deseni: {yol}"
            assert desen.name not in uclar, f"Aynı ad iki kez: {desen.name}"
            uclar[desen.name] = desen
    return uclar


def _gorunum_sinifi(desen: URLPattern) -> Any:
    return getattr(desen.callback, "view_class", None) or getattr(desen.callback, "cls", None)


def _izin_siniflari(desen: URLPattern) -> list[Any]:
    return list(getattr(_gorunum_sinifi(desen), "permission_classes", []) or [])


def _url(desen: URLPattern) -> str:
    """Converter'lı yolları örnek değerle doldurur (`<int:pk>` → 1)."""
    ornek = {ad: 1 for ad in desen.pattern.converters}
    return reverse(str(desen.name), kwargs=ornek)


def test_kisi_yazan_uclar_izin_sinifini_tasir_ve_liste_tam() -> None:
    uclar = _api_uclari()
    korunan = {ad for ad, desen in uclar.items() if RequiresAdminPassword in _izin_siniflari(desen)}
    assert korunan == KISI_YAZAN_UCLAR


def test_liste_disi_uclar_anlik_goruntuyle_sabit() -> None:
    """Yeni bir API ucu eklendiyse: kişi yazıyor mu? Karar verip doğru listeye ekleyin."""
    uclar = set(_api_uclari())
    assert uclar - KISI_YAZAN_UCLAR == DIGER_UCLAR
    assert KISI_YAZAN_UCLAR <= uclar


@pytest.mark.django_db
def test_parolasizken_kisi_yazan_her_uc_yazma_yontemiyle_409_doner(parolasiz: Path) -> None:
    client = APIClient()
    denenen = 0
    for ad, desen in sorted(_api_uclari().items()):
        if ad not in KISI_YAZAN_UCLAR:
            continue
        gorunum = _gorunum_sinifi(desen)
        for yontem in YAZMA_YONTEMLERI:
            if not hasattr(gorunum, yontem):
                continue
            yanit = client.generic(
                yontem.upper(), _url(desen), data="{}", content_type="application/json"
            )
            assert yanit.status_code == 409, (ad, yontem, yanit.status_code)
            assert yanit.json() == PAROLA_GEREKLI_GOVDESI, (ad, yontem)
            denenen += 1
    # 2 liste (POST) + 2 ayrıntı (PUT/PATCH/DELETE) + 4 içe aktarma (POST)
    # + 2 ayrılış (POST) + 1 birleştirme (POST) + 1 havuz kararı (POST)
    assert denenen == 2 + 2 * 3 + 4 + 2 + 1 + 1
    assert not Student.all_objects.exists()


@pytest.mark.django_db
def test_parolasizken_okuma_acik(parolasiz: Path) -> None:
    client = APIClient()
    assert client.get("/api/v1/students/").status_code == 200
    assert client.get("/api/v1/personnel/").status_code == 200


@pytest.mark.django_db
def test_parola_kuruluyken_kisi_yazilir() -> None:
    """Varsayılan ortam (parola kurulu + kilit açık): izin sınıfı geçirir."""
    yanit = APIClient().post(
        "/api/v1/students/",
        {"first_name": "DENEME", "last_name": "ÖĞRENCİ", "class_level": 9, "class_section": "A"},
        format="json",
    )
    assert yanit.status_code == 201, yanit.json()
