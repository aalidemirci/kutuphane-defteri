"""F11 (bakım kolu): görev devri uçları — `views_gorev_devri.py` başlığındaki tablo.

Düz `path()` girdileri; `apps.kutuphane.urls` sonuna eklenir (`urls_dokumler` deseni).
Yönetici kipi; görevli izin listesinde YOK; `library/` önekinde olduğu için kilitliyken 423.
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import views_gorev_devri

urlpatterns = [
    path(
        "library/handover/",
        views_gorev_devri.GorevDevriDurumView.as_view(),
        name="library-handover",
    ),
    path(
        "library/handover/start/",
        views_gorev_devri.GorevDevriBaslatView.as_view(),
        name="library-handover-start",
    ),
    path(
        "library/handover/note/",
        views_gorev_devri.GorevDevriNotuView.as_view(),
        name="library-handover-note",
    ),
]
