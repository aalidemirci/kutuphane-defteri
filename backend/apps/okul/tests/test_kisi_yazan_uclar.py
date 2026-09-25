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
        # F6 üyelik: kart no şifreli kişi verisidir; açma, toplu açma (istek
        # listesi), kartı yenile, sonlandırma ve silme kişi yazar.
        "library-membership-list",
        "library-membership-detail",
        "library-membership-renew-card",
        "library-membership-terminate",
        "library-membership-requests",
        # F6 kart basımı (E2, D10): "Basıldı olarak işaretle" ve geri alma üyelik
        # satırına yazar.
        "library-member-card-confirm-print",
        "library-member-card-revert-print",
        # F6 dolaşım masası: ödünç ver ve iade al ödünç kaydını (üyeye bağlı kişi
        # verisi; kartsız ödünç ve istisna gerekçeleri şifreli) yazar.
        "library-checkout",
        "library-return",
        # F7 teslim (U11): toplu teslim öğretmene bağlanır (PROTECT, açık yükümlülük);
        # geri alma okutması o teslim kaydını kapatır.
        "library-delivery-list",
        "library-delivery-take-back",
        # F7 kayıp/hasar dosyası (Md. 19): üyeliğe bağlanır, sorumlu notu şifrelidir;
        # açma, not düzeltme ve çözüm kişi yazar.
        "library-loss-damage-case-list",
        "library-loss-damage-case-detail",
        "library-loss-damage-case-resolve",
    }
)

# Anlık görüntü: kişi YAZMAYAN bütün `/api/` uçları. Yeni uç → bilinçli sınıflandırma.
DIGER_UCLAR = frozenset(
    {
        # Çık (F5, §4.2-4): kişi yazmaz; görevli kipinde yönetici parolası ister.
        "app-quit",
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
        # Etiket basım kuyruğu ve boş barkod aralığı (F4-Q): nüsha işaretleri,
        # basım partileri ve ayrılmış numaralar kitap kaydıdır, kişi sicili
        # değildir; kişisel veri taşımazlar. Doğrulama okutması (`library-label-verify`
        # POST) görevli kipinde de açıktır (24.09.2026); öbürleri yönetici kipi işidir.
        "library-barcode-reservation-cancel",
        "library-barcode-reservation-check",
        "library-barcode-reservation-confirm-print",
        "library-barcode-reservation-detail",
        "library-barcode-reservation-list",
        "library-barcode-reservation-pdf",
        "library-barcode-reservation-revert-print",
        "library-copy-from-label",
        "library-label-batch-confirm",
        "library-label-batch-detail",
        "library-label-batch-discard",
        "library-label-batch-list",
        "library-label-batch-pdf",
        "library-label-batch-reprint",
        "library-label-batch-revert",
        "library-label-queue",
        "library-label-summary",
        "library-label-unverified",
        "library-label-verify",
        # Etiket motoru (F4-L): şablon, yazıcı kalibrasyonu, kalibrasyon sayfası
        # ve PDF önizleme. Kişisel veri yok (künye, numara, kısa okul adı);
        # önizleme hiçbir kayıt yazmaz. Hepsi yönetici kipi işidir.
        "library-label-calibration",
        "library-label-calibration-detail",
        "library-label-calibration-list",
        "library-label-preview",
        "library-label-template-detail",
        "library-label-template-list",
        # Üyenin ödünç kaydı (F6): yalnız okur (GET); yönetici kipi işidir.
        "library-membership-loans",
        # F6 dolaşım masası: kartla üye çözme (POST yalnız kart no URL'ye yazılmasın
        # diye; okur), nüsha durum sorgusu (GET) ve kart okutma kilidini açma
        # (yönetici parolasını doğrular) kişi yazmaz. Ödünç ver ve iade üstteki listede.
        "library-desk-member",
        "library-desk-copy-status",
        "library-desk-card-unlock",
        # F7: teslim listesine okutmanın ön denetimi yazmaz; onarım kaydı kişisizdir
        # (nüsha durumu + tarih; serbest metin yok). Hepsi yönetici kipi işidir.
        "library-delivery-check",
        "library-copy-send-to-repair",
        "library-copy-return-from-repair",
        # F7 ilişik ve yıl akışları (E5, E4 yıl sonu pusulası) ve F7 evrakı (E6, E15):
        # liste, özet ve PDF uçları yalnız okur; hiçbir kayıt yazmaz. Hepsi yönetici
        # kipi işidir (§4.4 "ilişik", "kayıp dosyaları", "raporlar" kapalı).
        "library-clearance",
        "library-clearance-pdf",
        "library-clearance-sections",
        "library-clearance-certificate-pdf",
        "library-year-end-slip-pdf",
        "library-year-flows",
        "library-loss-damage-case-pdf",
        "library-delivery-pdf",
        "library-delivery-take-back-report",
        # F6 evrak ve pano (E2, E4, E13, E19, T15): kuyruk, gecikme listesi ve
        # son işlemler yalnız okur; PDF uçları kayıt yazmaz; panonun POST'u
        # yalnız süreç içi "Kontrol ettim" onayıdır. Hepsi yönetici kipi işidir.
        "library-dashboard-circulation",
        "library-dashboard-recent-transactions",
        "library-desk-card-pdf",
        "library-member-card-list",
        "library-member-card-pdf",
        "library-member-card-template",
        "library-overdue-loan-list",
        "library-overdue-loan-pdf",
        "library-overdue-slip-pdf",
        "library-privacy-notice-pdf",
        "library-donation-intake-cancel",
        "library-donation-intake-decision",
        "library-donation-intake-detail",
        "library-donation-intake-item-detail",
        "library-donation-intake-items",
        "library-donation-intake-list",
        # F8: bağış kalemlerinin katalog eşleşmesi yalnız okur.
        "library-donation-intake-matches",
        # F8 ayıklama (Md. 12/1), nadir eserler (Md. 12/2) ve yıl sonu raporu (E9):
        # kalemler, satırlar ve rapor kişisizdir — kişi SİCİLİ yazılmaz. Teklif
        # onayındaki harcama yetkilisi ve TMY komisyonu adları şifreli alandır;
        # parola kurulmadan izin sınıfı OLMADAN da 409 alır (fail-closed) ve servis
        # `require_password_set` sorar. Hepsi yönetici kipi işidir.
        "library-weeding-rules",
        "library-weeding-candidates",
        "library-weeding-batch-list",
        "library-weeding-batch-detail",
        "library-weeding-batch-items",
        "library-weeding-batch-item-detail",
        "library-weeding-batch-submit",
        "library-weeding-batch-withdraw",
        "library-weeding-batch-decision",
        "library-weeding-batch-approve",
        "library-weeding-batch-apply",
        "library-weeding-batch-cancel",
        "library-rare-copy-list",
        "library-rare-works-submission-list",
        "library-rare-works-submission-detail",
        "library-rare-works-submission-items",
        "library-rare-works-submission-item-detail",
        "library-rare-works-submission-send",
        "library-annual-review-list",
        "library-annual-review-detail",
        "library-annual-review-finalize",
        "library-annual-review-reopen",
        # F8 belgeleri (E7, E8, E9, E16): yalnız okur ve PDF/XLSX üretir; adlar
        # şifreli alandan yalnız belgenin kendisine çözülür. Yönetici kipi işidir.
        "library-weeding-batch-documents",
        "library-weeding-batch-document",
        "library-rare-works-submission-pdf",
        "library-annual-review-pdf",
        "library-donation-intake-pdf",
        # Bağış değerlendirme sonucu (F8 ekleri 13, 25.09.2026 kullanıcı kararı): yalnız okur;
        # bağışçının adı şifreli alandan yalnız belgeye çözülür.
        "library-donation-intake-result-pdf",
        # Toplu katalog aktarımı (F3): kitap kaydıdır, kişi sicili değildir.
        # Önizleme de yazar ve geri sarar; ikisi de yönetici kipi işidir ve
        # görevli kipi izin listesinde DEĞİLDİR.
        "library-import-ai-prompt",
        "library-import-apply",
        "library-import-preview",
        "library-import-run-discard",
        "library-import-run-list",
        "library-import-template",
        # Künye getirme uçları (F3, U13) kişi yazmaz: dışarı yalnız ISBN gider,
        # yanıt da yalnız kitap künyesidir. Üçü de `Work` satırına DOKUNMAZ
        # (öneri üretirler), yazma kullanıcının kendi `library-work-*` isteğiyle
        # olur — kanıt `apps/kutuphane/tests/test_kunye_uclari.py`.
        "library-metadata-lookup",
        "library-metadata-offline-export",
        "library-metadata-offline-preview",
        # Ağ Kataloğu ayarı (F5): port, dinleme kipi, vitrin ve kütüphane
        # saatleri — kişisel veri yok; yalnız yönetici kipinde yazılır.
        "library-network-catalog-settings",
        # Ağ Doktoru (F5, §5.9): durum, denetim, eylemler ve belgeler — kişi
        # yazmaz; belgeler kişisel veri taşımaz. Afiş yalnız afiş adresini yazar.
        "library-network-catalog-bookmarks",
        "library-network-catalog-control",
        "library-network-catalog-firewall",
        "library-network-catalog-firewall-rule",
        "library-network-catalog-info-note",
        "library-network-catalog-interfaces",
        "library-network-catalog-listener-test",
        "library-network-catalog-port",
        "library-network-catalog-poster",
        "library-network-catalog-pys-text",
        "library-network-catalog-status",
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
    # + F6 üyelik: liste (POST), ayrıntı (DELETE), kartı yenile, sonlandır, istek listesi (POST)
    # + F6 kart basım işareti ve geri alma (POST)
    # + F6 dolaşım masası: ödünç ver ve iade al (POST)
    # + F7: toplu teslim ve geri alma (POST), dosya açma (POST), not (PATCH), çözüm (POST)
    assert denenen == 2 + 2 * 3 + 4 + 2 + 1 + 1 + 5 + 2 + 2 + 2 + 3
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
