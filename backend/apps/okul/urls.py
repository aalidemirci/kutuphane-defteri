"""`okul` URL'leri — kebab-case, çoğul kaynak adları (OYS API sözleşmesi).

`setup/status/` hem arayüz kurulum kapısının hem masaüstü sağlık denetiminin
(`desktop/server.py::HEALTH_PATH`) tek kaynağıdır — yolu değişirse üçü birlikte
güncellenir. `security/` ön eki kilit kapısından muaftır
(`lock_middleware.ALLOWED_PREFIXES` ile birebir aynı kalmalıdır).
"""

from __future__ import annotations

from django.urls import path

from apps.okul import views, views_calendar, views_mode

urlpatterns = [
    # Kurulum sihirbazı
    path("setup/status/", views.SetupStatusView.as_view(), name="setup-status"),
    path("setup/school-config/", views.SchoolConfigView.as_view(), name="setup-school-config"),
    path("setup/complete/", views.SetupCompleteView.as_view(), name="setup-complete"),
    # Öğrenim seviyeleri (okul içi sabit 1-12 + hazırlık bayrağı)
    path("grade-levels/", views.GradeLevelsView.as_view(), name="grade-levels"),
    # Ders yılları + dönemler
    path("school-years/", views.SchoolYearListCreateView.as_view(), name="school-year-list"),
    path(
        "school-years/<int:pk>/terms/",
        views.SchoolTermView.as_view(),
        name="school-year-terms",
    ),
    path(
        "school-years/<int:pk>/activate/",
        views.SchoolYearActivateView.as_view(),
        name="school-year-activate",
    ),
    # Kapalı günler: resmî/dini tatil, öğrenciye kapalı gün, idari izin (tasarım §6.1)
    path("holidays/", views_calendar.HolidayListCreateView.as_view(), name="holiday-list"),
    path("holidays/seed/", views_calendar.HolidaySeedView.as_view(), name="holiday-seed"),
    path(
        "holidays/<int:pk>/",
        views_calendar.HolidayDetailView.as_view(),
        name="holiday-detail",
    ),
    # Öğrenciler / Personel / Şubeler
    path("students/", views.StudentListCreateView.as_view(), name="student-list"),
    path("students/<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    # Ayrılış yolu ve "olası aynı kişi" birleştirmesi (tasarım §6.1, §8.3)
    path("students/<int:pk>/leave/", views.StudentLeaveView.as_view(), name="student-leave"),
    path("personnel/", views.PersonnelListCreateView.as_view(), name="personnel-list"),
    path("personnel/<int:pk>/", views.PersonnelDetailView.as_view(), name="personnel-detail"),
    path(
        "personnel/<int:pk>/leave/",
        views.PersonnelLeaveView.as_view(),
        name="personnel-leave",
    ),
    path(
        "personnel/<int:pk>/merge/",
        views.PersonnelMergeView.as_view(),
        name="personnel-merge",
    ),
    path("class-sections/", views.ClassSectionListCreateView.as_view(), name="class-section-list"),
    path(
        "class-sections/<int:pk>/",
        views.ClassSectionDetailView.as_view(),
        name="class-section-detail",
    ),
    # İçe aktarma (dosya veya pano metni)
    path(
        "imports/students/preview/",
        views.StudentImportPreviewView.as_view(),
        name="import-students-preview",
    ),
    path(
        "imports/students/commit/",
        views.StudentImportCommitView.as_view(),
        name="import-students-commit",
    ),
    path(
        "imports/personnel/preview/",
        views.PersonnelImportPreviewView.as_view(),
        name="import-personnel-preview",
    ),
    path(
        "imports/personnel/commit/",
        views.PersonnelImportCommitView.as_view(),
        name="import-personnel-commit",
    ),
    # Şablon indirme
    path("templates/students/", views.StudentTemplateView.as_view(), name="template-students"),
    path("templates/personnel/", views.PersonnelTemplateView.as_view(), name="template-personnel"),
    # Yönetici parolası / kilit (tasarım §4.3, §6.3; parolayı kaldırma ucu yok)
    path("security/status/", views.SecurityStatusView.as_view(), name="security-status"),
    path("security/enable/", views.SecurityEnableView.as_view(), name="security-enable"),
    path("security/unlock/", views.SecurityUnlockView.as_view(), name="security-unlock"),
    path("security/lock/", views.SecurityLockView.as_view(), name="security-lock"),
    path("security/recover/", views.SecurityRecoverView.as_view(), name="security-recover"),
    path(
        "security/change-password/",
        views.SecurityChangePasswordView.as_view(),
        name="security-change-password",
    ),
    # Kip: görevli kipi / yönetici kipi (U5, tasarım §4.4). `security/mode/`
    # hiçbir kipte kesilmez; `staff/` görevli kipinde kapalıdır (kip_izinleri).
    path("security/mode/", views_mode.KipDurumView.as_view(), name="security-mode"),
    path(
        "security/mode/staff/",
        views_mode.GorevliKipineGecView.as_view(),
        name="security-mode-staff",
    ),
    path(
        "security/mode/admin/",
        views_mode.YoneticiKipineGecView.as_view(),
        name="security-mode-admin",
    ),
    path(
        "backups/encrypted/",
        views.EncryptedBackupDownloadView.as_view(),
        name="encrypted-backup-download",
    ),
    # Yedekten geri yükleme (Güvenlik sekmesi — çalışan program içinden)
    path("backups/", views.BackupListView.as_view(), name="backup-list"),
    path("backups/restore/", views.BackupRestoreView.as_view(), name="backup-restore"),
    # GitHub Release tabanlı uygulama güncellemesi (F8)
    path("updates/latest/", views.UpdateStatusView.as_view(), name="update-latest"),
    path(
        "updates/latest/installer/",
        views.UpdateInstallerView.as_view(),
        name="update-installer",
    ),
]
