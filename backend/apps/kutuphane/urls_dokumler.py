"""F10 dökümleri ve dışa aktarım uçları (D kolu) — `apps.kutuphane.urls`'e eklenir.

Ayrı dosyadadır: ortak `urls.py`'de yalnız bir `urlpatterns +=` satırı durur (paralel
çalışan kolların aynı bölgeye yazmaması için). Adlar `library-…` düz ad uzayındadır
(`test_kip_koruma.py::test_api_uc_adlari_tekildir`). Hiçbiri görevli kipi izin
listesinde DEĞİLDİR (`views_dokumler` modül yorumu).
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import views_dokumler

urlpatterns = [
    # Dışa aktarım (tasarım §8.4, U1) — kişisel veri yok; üye özeti kişisiz sayılardır.
    path("library/export/", views_dokumler.ExportView.as_view(), name="library-export"),
    path(
        "library/export/member-summary/",
        views_dokumler.MemberSummaryView.as_view(),
        name="library-export-member-summary",
    ),
    # Dökümler (E11, E17) ve kişi dökümü (KVKK md. 11) — yönetici kipi; kayıt YAZMAZ.
    path(
        "library/reports/documents/",
        views_dokumler.ReportDocumentsView.as_view(),
        name="library-report-documents",
    ),
    path(
        "library/reports/catalog-listing/",
        views_dokumler.CatalogListingView.as_view(),
        name="library-report-catalog-listing",
    ),
    path(
        "library/reports/library-register/",
        views_dokumler.LibraryRegisterView.as_view(),
        name="library-report-library-register",
    ),
    path(
        "library/reports/management-account/<int:pk>/",
        views_dokumler.ManagementAccountView.as_view(),
        name="library-report-management-account",
    ),
    path(
        "library/reports/person-record/search/",
        views_dokumler.PersonRecordSearchView.as_view(),
        name="library-report-person-record-search",
    ),
    path(
        "library/reports/person-record/<slug:tur>/<int:pk>/",
        views_dokumler.PersonRecordView.as_view(),
        name="library-report-person-record",
    ),
]
