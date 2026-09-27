"""F11 — saklama ve anonimleştirme uçları (tasarım §6.4; `views_saklama.py`).

Düz `path()` girdileri (ad alanı yok — `urls.py` başlığı). YALNIZ yönetici kipi;
görevli kipi izin listesine GİRMEZ (CLAUDE.md §2-4).
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import views_saklama

urlpatterns = [
    path(
        "library/retention/",
        views_saklama.RetentionStatusView.as_view(),
        name="library-retention",
    ),
    path(
        "library/retention/persons/",
        views_saklama.RetentionPersonsView.as_view(),
        name="library-retention-persons",
    ),
    path(
        "library/retention/price-reminders/",
        views_saklama.RetentionPriceRemindersView.as_view(),
        name="library-retention-price-reminders",
    ),
    # Kişi kaydı SİLER: `RequiresAdminPassword` + gövdede yönetici parolası.
    path(
        "library/retention/apply/",
        views_saklama.RetentionApplyView.as_view(),
        name="library-retention-apply",
    ),
    path(
        "library/dashboard/retention/",
        views_saklama.DashboardRetentionView.as_view(),
        name="library-dashboard-retention",
    ),
]
