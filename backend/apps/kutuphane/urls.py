"""`kutuphane` URL'leri — OYS öneki `library/` ve `library-…` adları korunur.

Ad alanı (`app_name`) YOKTUR: `apps.okul.urls` ile aynı düzen; kip izin listesi
ve URL'leri dolaşan koruma testleri düz URL adlarıyla çalışır.
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import views

urlpatterns = [
    # Katalog Excel şablonu (tasarım §8.1 — sütun sözlüğü F1'de sabitlenir)
    path(
        "library/import/template/",
        views.CatalogImportTemplateView.as_view(),
        name="library-import-template",
    ),
]
