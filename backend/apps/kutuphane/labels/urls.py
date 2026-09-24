"""Etiket motorunun uçları — `apps/kutuphane/urls.py` bu listeyi kendi listesine ekler.

Düz `path()` girdileridir (`include` DEĞİL): URL'leri dolaşan koruma testleri
(`test_uc_kapilari.py`, `test_kisi_yazan_uclar.py`) `apps.kutuphane.urls`
listesinde yalnız `URLPattern` bekler. Adlar düz ad uzayındadır ve tekildir.
Basım kuyruğu, basım partisi ve boş barkod aralığı uçları bu listede değildir.
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane.labels import views

urlpatterns = [
    path(
        "library/label-templates/",
        views.LabelTemplateListCreateView.as_view(),
        name="library-label-template-list",
    ),
    path(
        "library/label-templates/<int:pk>/",
        views.LabelTemplateDetailView.as_view(),
        name="library-label-template-detail",
    ),
    path(
        "library/label-calibrations/",
        views.LabelCalibrationListCreateView.as_view(),
        name="library-label-calibration-list",
    ),
    path(
        "library/label-calibrations/<int:pk>/",
        views.LabelCalibrationDetailView.as_view(),
        name="library-label-calibration-detail",
    ),
    # Kalibrasyon sayfası PDF'i (E1) — OYS'deki ad ve yol korunur.
    path(
        "library/labels/calibration/",
        views.LabelCalibrationSheetView.as_view(),
        name="library-label-calibration",
    ),
    # Etiket PDF'i; hiçbir kayıt yazmaz (basım kaydı basım partisinindir — D10).
    path(
        "library/labels/preview/",
        views.LabelPreviewView.as_view(),
        name="library-label-preview",
    ),
]
