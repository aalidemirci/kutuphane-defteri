"""`kutuphane` URL'leri — OYS öneki `library/` ve `library-…` adları korunur.

Ad alanı (`app_name`) YOKTUR: `apps.okul.urls` ile aynı düzen; kip izin listesi
ve URL'leri dolaşan koruma testleri düz URL adlarıyla çalışır. OYS bu uçları
`DefaultRouter` ile kuruyordu; router'ın ürettiği adlar (`library-work-list`,
`library-work-detail`) burada açık `path()` girdileriyle birebir korunmuştur —
böylece API yüzeyi aynı kalır, ad uzayı düz kalır ve `?format=` son ekleri
(DRF içerik müzakeresine ayrılmıştır) URL yüzeyine karışmaz.

**Ad teklikliği şarttır** (`test_kip_koruma.py::test_api_uc_adlari_tekildir`):
bu dosyadaki adlar `apps.okul.urls` ile AYNI düz ad uzayındadır.

Uçların HİÇBİRİ görevli kipi izin listesinde değildir (varsayılan kapalı —
CLAUDE.md §2-4): katalog düzenlemek, edinim açmak ve bağış kararı işlemek
yönetici işidir.
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import views, views_import, views_kunye

urlpatterns = [
    # Katalog Excel şablonu (tasarım §8.1 — sütun sözlüğü F1'de sabitlenir)
    path(
        "library/import/template/",
        views.CatalogImportTemplateView.as_view(),
        name="library-import-template",
    ),
    # Toplu katalog aktarımı (F3, §8.1): önizleme uygulamanın birebir provasıdır
    path(
        "library/import/preview/",
        views_import.CatalogImportPreviewView.as_view(),
        name="library-import-preview",
    ),
    path(
        "library/import/apply/",
        views_import.CatalogImportApplyView.as_view(),
        name="library-import-apply",
    ),
    path(
        "library/import/runs/",
        views_import.CatalogImportRunListView.as_view(),
        name="library-import-run-list",
    ),
    path(
        "library/import/runs/<int:pk>/discard/",
        views_import.CatalogImportRunDiscardView.as_view(),
        name="library-import-run-discard",
    ),
    # Yapay zekâ köprüsünün komut metni ve uyarıları (§8.2) — dış istek YOK
    path(
        "library/import/ai-prompt/",
        views_import.CatalogAiPromptView.as_view(),
        name="library-import-ai-prompt",
    ),
    # ISBN ile künye getirme (U13, tasarım §8.5) — varsayılan KAPALI dış kapı.
    # Sorgu POST'tur: kullanıcının EYLEMİDİR, adres çubuğundan ya da bir
    # önyüklemeden tetiklenmemelidir.
    path(
        "library/metadata/lookup/",
        views_kunye.MetadataLookupView.as_view(),
        name="library-metadata-lookup",
    ),
    # Çevrimdışı yol: ISBN listesi dışa aktarılır, başka cihazda doldurulur,
    # geri yüklenir. İkisi de ağa çıkmaz.
    path(
        "library/metadata/offline-export/",
        views_kunye.MetadataOfflineExportView.as_view(),
        name="library-metadata-offline-export",
    ),
    path(
        "library/metadata/offline-preview/",
        views_kunye.MetadataOfflinePreviewView.as_view(),
        name="library-metadata-offline-preview",
    ),
    # Kütüphane politikası (tek satır; PUT kısmidir — gönderilmeyen alana dokunulmaz)
    path("library/policy/", views.LibraryPolicyView.as_view(), name="library-policy"),
    # Koleksiyon özeti ve sıradaki nüsha numarası (kişisel veri yok)
    path("library/stats/", views.LibraryStatsView.as_view(), name="library-stats"),
    # Bölümler (kontrollü liste)
    path("library/sections/", views.SectionListCreateView.as_view(), name="library-section-list"),
    path(
        "library/sections/<int:pk>/",
        views.SectionDetailView.as_view(),
        name="library-section-detail",
    ),
    # Eserler
    path("library/works/", views.WorkListCreateView.as_view(), name="library-work-list"),
    path("library/works/<int:pk>/", views.WorkDetailView.as_view(), name="library-work-detail"),
    # Nüshalar (`bulk/` ayrıntı deseninden ÖNCE: '<int:pk>' onu yakalamaz ama
    # okuyucu için de sıra anlamlıdır — toplu açma tekil nüsha değildir)
    path("library/copies/", views.CopyListCreateView.as_view(), name="library-copy-list"),
    path("library/copies/bulk/", views.CopyBulkCreateView.as_view(), name="library-copy-bulk"),
    path("library/copies/<int:pk>/", views.CopyDetailView.as_view(), name="library-copy-detail"),
    # Seçim ve Ayıklama Komisyonu kararları
    path(
        "library/commission-decisions/",
        views.CommissionDecisionListCreateView.as_view(),
        name="library-commission-decision-list",
    ),
    path(
        "library/commission-decisions/<int:pk>/",
        views.CommissionDecisionDetailView.as_view(),
        name="library-commission-decision-detail",
    ),
    # Edinimler
    path(
        "library/acquisitions/",
        views.AcquisitionListCreateView.as_view(),
        name="library-acquisition-list",
    ),
    path(
        "library/acquisitions/<int:pk>/",
        views.AcquisitionDetailView.as_view(),
        name="library-acquisition-detail",
    ),
    # Bağış ön kaydı ve komisyon kararının uygulanması (SU-23, Md. 10/3)
    path(
        "library/donation-intakes/",
        views.DonationIntakeListCreateView.as_view(),
        name="library-donation-intake-list",
    ),
    path(
        "library/donation-intakes/<int:pk>/",
        views.DonationIntakeDetailView.as_view(),
        name="library-donation-intake-detail",
    ),
    path(
        "library/donation-intakes/<int:pk>/items/",
        views.DonationIntakeItemCreateView.as_view(),
        name="library-donation-intake-items",
    ),
    path(
        "library/donation-intakes/<int:pk>/items/<int:item_pk>/",
        views.DonationIntakeItemDetailView.as_view(),
        name="library-donation-intake-item-detail",
    ),
    path(
        "library/donation-intakes/<int:pk>/decision/",
        views.DonationIntakeDecisionView.as_view(),
        name="library-donation-intake-decision",
    ),
    path(
        "library/donation-intakes/<int:pk>/cancel/",
        views.DonationIntakeCancelView.as_view(),
        name="library-donation-intake-cancel",
    ),
]
