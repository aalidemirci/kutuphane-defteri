"""`kutuphane` URL'leri — OYS öneki `library/` ve `library-…` adları korunur.

Ad alanı (`app_name`) YOKTUR: `apps.okul.urls` ile aynı düzen; kip izin listesi
ve URL'leri dolaşan koruma testleri düz URL adlarıyla çalışır. OYS bu uçları
`DefaultRouter` ile kuruyordu; router'ın ürettiği adlar (`library-work-list`,
`library-work-detail`) burada açık `path()` girdileriyle birebir korunmuştur —
böylece API yüzeyi aynı kalır, ad uzayı düz kalır ve `?format=` son ekleri
(DRF içerik müzakeresine ayrılmıştır) URL yüzeyine karışmaz.

**Ad teklikliği şarttır** (`test_kip_koruma.py::test_api_uc_adlari_tekildir`):
bu dosyadaki adlar `apps.okul.urls` ile AYNI düz ad uzayındadır.

Görevli kipi izin listesinde bu dosyadan `library-label-verify` POST (etiket
doğrulama okutması; kullanıcı kararı 24.09.2026), F6 dolaşım masası uçları
(`library-desk-member`, `library-checkout`, `library-return`,
`library-desk-copy-status`, `library-desk-card-unlock`) ve katalog okuma
(`library-work-list`, `library-work-detail`, `library-copy-list` — yalnız GET,
sorgu parametresi kuralıyla; yanıt görevli kipinde daralır) ve F7 teslimden geri
alma okutması (`library-delivery-take-back` POST) vardır. Geri kalan
uçlar kapalıdır (varsayılan kapalı — CLAUDE.md §2-4): katalog düzenlemek,
edinim açmak, bağış kararı işlemek, etiket basmak ve üyelik yönetimi (F6:
üyelik açma, kartı yenile, sonlandırma, istek listesi, ödünç geçmişi)
yönetici işidir.
"""

from __future__ import annotations

from django.urls import path

from apps.kutuphane import (
    views,
    views_ag_doktoru,
    views_ayiklama,
    views_evrak,
    views_ilisik,
    views_import,
    views_katalog,
    views_komisyon_belgeleri,
    views_kunye,
    views_kuyruk,
    views_masa,
    views_teslim,
    views_uyelik,
)
from apps.kutuphane.labels import urls as label_urls

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
    # Ağ Kataloğu ayarı (F5; tek satır, PUT kısmidir). Yalnız yönetici kipinde
    # yazılır; görevli kipi izin listesinde DEĞİLDİR.
    path(
        "library/network-catalog/settings/",
        views_katalog.NetworkCatalogSettingsView.as_view(),
        name="library-network-catalog-settings",
    ),
    # Ağ Doktoru (F5, §5.9): durum, denetim, eylemler ve belgeler. Hepsi yalnız
    # yönetici kipinde; hiçbiri görevli kipi izin listesinde DEĞİLDİR.
    path(
        "library/network-catalog/status/",
        views_ag_doktoru.NetworkCatalogStatusView.as_view(),
        name="library-network-catalog-status",
    ),
    path(
        "library/network-catalog/control/",
        views_ag_doktoru.NetworkCatalogControlView.as_view(),
        name="library-network-catalog-control",
    ),
    path(
        "library/network-catalog/firewall/",
        views_ag_doktoru.NetworkCatalogFirewallView.as_view(),
        name="library-network-catalog-firewall",
    ),
    path(
        "library/network-catalog/firewall-rule/",
        views_ag_doktoru.NetworkCatalogFirewallRuleView.as_view(),
        name="library-network-catalog-firewall-rule",
    ),
    path(
        "library/network-catalog/interfaces/",
        views_ag_doktoru.NetworkCatalogInterfacesView.as_view(),
        name="library-network-catalog-interfaces",
    ),
    path(
        "library/network-catalog/listener-test/",
        views_ag_doktoru.NetworkCatalogListenerTestView.as_view(),
        name="library-network-catalog-listener-test",
    ),
    path(
        "library/network-catalog/port/",
        views_ag_doktoru.NetworkCatalogPortView.as_view(),
        name="library-network-catalog-port",
    ),
    path(
        "library/network-catalog/poster/",
        views_ag_doktoru.NetworkCatalogPosterView.as_view(),
        name="library-network-catalog-poster",
    ),
    path(
        "library/network-catalog/info-note/",
        views_ag_doktoru.NetworkCatalogInfoNoteView.as_view(),
        name="library-network-catalog-info-note",
    ),
    path(
        "library/network-catalog/bookmarks/",
        views_ag_doktoru.NetworkCatalogBookmarksView.as_view(),
        name="library-network-catalog-bookmarks",
    ),
    path(
        "library/network-catalog/pys-text/",
        views_ag_doktoru.NetworkCatalogPysTextView.as_view(),
        name="library-network-catalog-pys-text",
    ),
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
    # F8: kalemlerin katalogdaki karşılığı (karar uygulanmadan önce; kayıt yazmaz).
    path(
        "library/donation-intakes/<int:pk>/matches/",
        views.DonationIntakeMatchesView.as_view(),
        name="library-donation-intake-matches",
    ),
    path(
        "library/donation-intakes/<int:pk>/cancel/",
        views.DonationIntakeCancelView.as_view(),
        name="library-donation-intake-cancel",
    ),
    # F8: bağış ön kayıt listesi (E16; komisyona sunulur) — kayıt yazmaz.
    path(
        "library/donation-intakes/<int:pk>/pdf/",
        views_komisyon_belgeleri.DonationIntakePdfView.as_view(),
        name="library-donation-intake-pdf",
    ),
    # Bağış değerlendirme sonucu (karar uygulandıktan sonra; F8 ekleri 13) — kayıt yazmaz.
    path(
        "library/donation-intakes/<int:pk>/result-pdf/",
        views_komisyon_belgeleri.DonationIntakeResultPdfView.as_view(),
        name="library-donation-intake-result-pdf",
    ),
    # --- F4-Q: etiket basım kuyruğu, basım kaydı (D10), doğrulama okutması ---
    # PDF uçları işarete DOKUNMAZ; "basıldı" yalnız `confirm/` ile yazılır ve
    # `revert/` ile geri alınır. Görevli kipinde yalnız `verify/` POST açıktır.
    path(
        "library/labels/queue/", views_kuyruk.LabelQueueView.as_view(), name="library-label-queue"
    ),
    path(
        "library/labels/unverified/",
        views_kuyruk.LabelUnverifiedView.as_view(),
        name="library-label-unverified",
    ),
    path(
        "library/labels/summary/",
        views_kuyruk.LabelSummaryView.as_view(),
        name="library-label-summary",
    ),
    path(
        "library/labels/verify/",
        views_kuyruk.LabelVerifyView.as_view(),
        name="library-label-verify",
    ),
    path(
        "library/labels/batches/",
        views_kuyruk.LabelBatchListCreateView.as_view(),
        name="library-label-batch-list",
    ),
    path(
        "library/labels/batches/<int:pk>/",
        views_kuyruk.LabelBatchDetailView.as_view(),
        name="library-label-batch-detail",
    ),
    path(
        "library/labels/batches/<int:pk>/pdf/",
        views_kuyruk.LabelBatchPdfView.as_view(),
        name="library-label-batch-pdf",
    ),
    path(
        "library/labels/batches/<int:pk>/confirm/",
        views_kuyruk.LabelBatchConfirmView.as_view(),
        name="library-label-batch-confirm",
    ),
    path(
        "library/labels/batches/<int:pk>/revert/",
        views_kuyruk.LabelBatchRevertView.as_view(),
        name="library-label-batch-revert",
    ),
    path(
        "library/labels/batches/<int:pk>/discard/",
        views_kuyruk.LabelBatchDiscardView.as_view(),
        name="library-label-batch-discard",
    ),
    path(
        "library/labels/batches/<int:pk>/reprint/",
        views_kuyruk.LabelBatchReprintView.as_view(),
        name="library-label-batch-reprint",
    ),
    # --- F4-Q: boş barkod aralığı (yöntem B — okulun asıl yolu, §8.1) ---
    # `check/` sayısal kimlikten ÖNCE yazılır (okuyucu için; `<int:pk>` onu zaten yakalamaz).
    path(
        "library/barcode-reservations/",
        views_kuyruk.BarcodeReservationListCreateView.as_view(),
        name="library-barcode-reservation-list",
    ),
    path(
        "library/barcode-reservations/check/",
        views_kuyruk.BarcodeReservationCheckView.as_view(),
        name="library-barcode-reservation-check",
    ),
    path(
        "library/barcode-reservations/<int:pk>/",
        views_kuyruk.BarcodeReservationDetailView.as_view(),
        name="library-barcode-reservation-detail",
    ),
    path(
        "library/barcode-reservations/<int:pk>/pdf/",
        views_kuyruk.BarcodeReservationPdfView.as_view(),
        name="library-barcode-reservation-pdf",
    ),
    path(
        "library/barcode-reservations/<int:pk>/confirm-print/",
        views_kuyruk.BarcodeReservationConfirmPrintView.as_view(),
        name="library-barcode-reservation-confirm-print",
    ),
    path(
        "library/barcode-reservations/<int:pk>/revert-print/",
        views_kuyruk.BarcodeReservationRevertPrintView.as_view(),
        name="library-barcode-reservation-revert-print",
    ),
    path(
        "library/barcode-reservations/<int:pk>/cancel/",
        views_kuyruk.BarcodeReservationCancelView.as_view(),
        name="library-barcode-reservation-cancel",
    ),
    # Hızlı kayıtta önceden basılmış etiketi bağlama (etiketsiz kitap: `library/copies/`)
    path(
        "library/copies/from-label/",
        views_kuyruk.CopyFromLabelView.as_view(),
        name="library-copy-from-label",
    ),
    # --- F6: üyelik yönetimi (YALNIZ yönetici kipi; görevli izin listesinde YOK) ---
    # Kişi yazar: `RequiresAdminPassword` (parola kurulmadan 409). Masa uçları ayrıdır.
    path(
        "library/memberships/",
        views_uyelik.MembershipListCreateView.as_view(),
        name="library-membership-list",
    ),
    path(
        "library/memberships/<int:pk>/",
        views_uyelik.MembershipDetailView.as_view(),
        name="library-membership-detail",
    ),
    path(
        "library/memberships/<int:pk>/renew-card/",
        views_uyelik.MembershipRenewCardView.as_view(),
        name="library-membership-renew-card",
    ),
    path(
        "library/memberships/<int:pk>/terminate/",
        views_uyelik.MembershipTerminateView.as_view(),
        name="library-membership-terminate",
    ),
    path(
        "library/memberships/<int:pk>/loans/",
        views_uyelik.MembershipLoansView.as_view(),
        name="library-membership-loans",
    ),
    # Şube bazlı üyelik istek listesi (Md. 17/1 — üyelik isteğe bağlıdır)
    path(
        "library/membership-requests/",
        views_uyelik.MembershipRequestsView.as_view(),
        name="library-membership-requests",
    ),
    # --- F6: evrak, kart basımı ve pano (E2, E4, E13, E19, T15) — YALNIZ yönetici
    # kipi; görevli izin listesinde YOK. PDF uçları kayıt yazmaz; kart basım
    # işareti (D10) yalnız `confirm-print/` ile yazılır (`views_evrak.py`).
    path(
        "library/member-cards/",
        views_evrak.MemberCardListView.as_view(),
        name="library-member-card-list",
    ),
    path(
        "library/member-cards/template/",
        views_evrak.MemberCardTemplateView.as_view(),
        name="library-member-card-template",
    ),
    path(
        "library/member-cards/pdf/",
        views_evrak.MemberCardPdfView.as_view(),
        name="library-member-card-pdf",
    ),
    path(
        "library/member-cards/confirm-print/",
        views_evrak.MemberCardConfirmPrintView.as_view(),
        name="library-member-card-confirm-print",
    ),
    path(
        "library/member-cards/revert-print/",
        views_evrak.MemberCardRevertPrintView.as_view(),
        name="library-member-card-revert-print",
    ),
    path(
        "library/overdue-loans/",
        views_evrak.OverdueLoanListView.as_view(),
        name="library-overdue-loan-list",
    ),
    path(
        "library/overdue-loans/pdf/",
        views_evrak.OverdueLoanPdfView.as_view(),
        name="library-overdue-loan-pdf",
    ),
    path(
        "library/overdue-loans/slips/",
        views_evrak.OverdueSlipPdfView.as_view(),
        name="library-overdue-slip-pdf",
    ),
    path(
        "library/documents/privacy-notice/",
        views_evrak.PrivacyNoticePdfView.as_view(),
        name="library-privacy-notice-pdf",
    ),
    path(
        "library/documents/desk-card/",
        views_evrak.DeskCardPdfView.as_view(),
        name="library-desk-card-pdf",
    ),
    path(
        "library/dashboard/circulation/",
        views_evrak.DashboardCirculationView.as_view(),
        name="library-dashboard-circulation",
    ),
    path(
        "library/dashboard/recent-transactions/",
        views_evrak.RecentTransactionsView.as_view(),
        name="library-dashboard-recent-transactions",
    ),
    # --- F6: dolaşım masası (§7.3). Görevli kipi izin listesinde (uç + PARAMETRE
    # kuralıyla — `apps/okul/kip_izinleri.py`); yanıtlar görevli kipinde daralır.
    path("library/desk/member/", views_masa.MasaUyeView.as_view(), name="library-desk-member"),
    # Ödünç ver — OYS adı (`library-checkout`) korunur.
    path("library/checkout/", views_masa.MasaOduncView.as_view(), name="library-checkout"),
    # Barkodla iade (D9): boş bağlamda okutulan kitap açık ödünçteyse iade alınır.
    path("library/return/", views_masa.MasaIadeView.as_view(), name="library-return"),
    path(
        "library/desk/copy-status/",
        views_masa.MasaNushaDurumuView.as_view(),
        name="library-desk-copy-status",
    ),
    # GA-7: art arda geçersiz kart okutmasından sonra yönetici parolasıyla sürdürme.
    path(
        "library/desk/card-unlock/",
        views_masa.MasaKartKilidiView.as_view(),
        name="library-desk-card-unlock",
    ),
    # --- F7: toplu teslim (U11). Teslim VERME yönetici kipinde; görevli kipi izin
    # listesinde YALNIZ geri alma okutması (`take-back/` POST, yanıt daralır — §4.4).
    path(
        "library/deliveries/",
        views_teslim.DeliveryListCreateView.as_view(),
        name="library-delivery-list",
    ),
    path(
        "library/deliveries/check/",
        views_teslim.DeliveryCheckView.as_view(),
        name="library-delivery-check",
    ),
    path(
        "library/deliveries/take-back/",
        views_teslim.DeliveryTakeBackView.as_view(),
        name="library-delivery-take-back",
    ),
    # --- F7: kayıp/hasar dosyaları (Md. 19) ve onarım (D3) — YALNIZ yönetici kipi.
    # OYS adları (`library-loss-damage-case-*`) korunur.
    path(
        "library/loss-damage-cases/",
        views_teslim.LossDamageCaseListCreateView.as_view(),
        name="library-loss-damage-case-list",
    ),
    path(
        "library/loss-damage-cases/<int:pk>/",
        views_teslim.LossDamageCaseDetailView.as_view(),
        name="library-loss-damage-case-detail",
    ),
    path(
        "library/loss-damage-cases/<int:pk>/resolve/",
        views_teslim.LossDamageCaseResolveView.as_view(),
        name="library-loss-damage-case-resolve",
    ),
    path(
        "library/copies/<int:pk>/send-to-repair/",
        views_teslim.CopySendToRepairView.as_view(),
        name="library-copy-send-to-repair",
    ),
    path(
        "library/copies/<int:pk>/return-from-repair/",
        views_teslim.CopyReturnFromRepairView.as_view(),
        name="library-copy-return-from-repair",
    ),
    # --- F7-İ: ilişik listesi, yıl akışları ve F7 evrakı (E5, E6, E15) — YALNIZ
    # yönetici kipi (§4.4 "ilişik", "kayıp dosyaları", "raporlar" kapalı). Hiçbiri
    # kayıt yazmaz. `library-clearance` OYS adıdır.
    path("library/clearance/", views_ilisik.ClearanceListView.as_view(), name="library-clearance"),
    path(
        "library/clearance/pdf/",
        views_ilisik.ClearancePdfView.as_view(),
        name="library-clearance-pdf",
    ),
    path(
        "library/clearance/sections/",
        views_ilisik.ClearanceSectionsView.as_view(),
        name="library-clearance-sections",
    ),
    path(
        "library/clearance/certificates/",
        views_ilisik.ClearanceCertificatePdfView.as_view(),
        name="library-clearance-certificate-pdf",
    ),
    path(
        "library/year-end/slips/",
        views_ilisik.YearEndSlipPdfView.as_view(),
        name="library-year-end-slip-pdf",
    ),
    path("library/year-flows/", views_ilisik.YearFlowsView.as_view(), name="library-year-flows"),
    path(
        "library/loss-damage-cases/<int:pk>/pdf/",
        views_ilisik.LossDamageCaseReportView.as_view(),
        name="library-loss-damage-case-pdf",
    ),
    path(
        "library/deliveries/pdf/",
        views_ilisik.DeliveryListPdfView.as_view(),
        name="library-delivery-pdf",
    ),
    path(
        "library/deliveries/take-back-report/",
        views_ilisik.DeliveryTakeBackReportView.as_view(),
        name="library-delivery-take-back-report",
    ),
    # --- F8: ayıklama (Md. 12/1; E7 yolu), nadir eserler (Md. 12/2), yıl sonu raporu
    # (Md. 12/1, E9) — YALNIZ yönetici kipi (§4.4); hiçbiri izin listesinde değil.
    path(
        "library/weeding/rules/",
        views_ayiklama.WeedingRulesView.as_view(),
        name="library-weeding-rules",
    ),
    path(
        "library/weeding/candidates/",
        views_ayiklama.WeedingCandidatesView.as_view(),
        name="library-weeding-candidates",
    ),
    path(
        "library/weeding-batches/",
        views_ayiklama.WeedingBatchListCreateView.as_view(),
        name="library-weeding-batch-list",
    ),
    path(
        "library/weeding-batches/<int:pk>/",
        views_ayiklama.WeedingBatchDetailView.as_view(),
        name="library-weeding-batch-detail",
    ),
    path(
        "library/weeding-batches/<int:pk>/items/",
        views_ayiklama.WeedingBatchItemsView.as_view(),
        name="library-weeding-batch-items",
    ),
    path(
        "library/weeding-batches/<int:pk>/items/<int:item_pk>/",
        views_ayiklama.WeedingBatchItemDetailView.as_view(),
        name="library-weeding-batch-item-detail",
    ),
    path(
        "library/weeding-batches/<int:pk>/submit/",
        views_ayiklama.WeedingBatchSubmitView.as_view(),
        name="library-weeding-batch-submit",
    ),
    path(
        "library/weeding-batches/<int:pk>/withdraw/",
        views_ayiklama.WeedingBatchWithdrawView.as_view(),
        name="library-weeding-batch-withdraw",
    ),
    path(
        "library/weeding-batches/<int:pk>/decision/",
        views_ayiklama.WeedingBatchDecisionView.as_view(),
        name="library-weeding-batch-decision",
    ),
    path(
        "library/weeding-batches/<int:pk>/approve/",
        views_ayiklama.WeedingBatchApproveView.as_view(),
        name="library-weeding-batch-approve",
    ),
    path(
        "library/weeding-batches/<int:pk>/apply/",
        views_ayiklama.WeedingBatchApplyView.as_view(),
        name="library-weeding-batch-apply",
    ),
    path(
        "library/weeding-batches/<int:pk>/cancel/",
        views_ayiklama.WeedingBatchCancelView.as_view(),
        name="library-weeding-batch-cancel",
    ),
    # E7 ayıklama belgeleri (TMY yoluna göre) — kayıt YAZMAZ.
    path(
        "library/weeding-batches/<int:pk>/documents/",
        views_komisyon_belgeleri.WeedingBatchDocumentsView.as_view(),
        name="library-weeding-batch-documents",
    ),
    path(
        "library/weeding-batches/<int:pk>/documents/<slug:belge>/",
        views_komisyon_belgeleri.WeedingBatchDocumentView.as_view(),
        name="library-weeding-batch-document",
    ),
    path(
        "library/rare-copies/",
        views_ayiklama.RareCopyListView.as_view(),
        name="library-rare-copy-list",
    ),
    path(
        "library/rare-works-submissions/",
        views_ayiklama.RareWorksSubmissionListCreateView.as_view(),
        name="library-rare-works-submission-list",
    ),
    path(
        "library/rare-works-submissions/<int:pk>/",
        views_ayiklama.RareWorksSubmissionDetailView.as_view(),
        name="library-rare-works-submission-detail",
    ),
    path(
        "library/rare-works-submissions/<int:pk>/items/",
        views_ayiklama.RareWorksSubmissionItemsView.as_view(),
        name="library-rare-works-submission-items",
    ),
    path(
        "library/rare-works-submissions/<int:pk>/items/<int:item_pk>/",
        views_ayiklama.RareWorksSubmissionItemDetailView.as_view(),
        name="library-rare-works-submission-item-detail",
    ),
    path(
        "library/rare-works-submissions/<int:pk>/send/",
        views_ayiklama.RareWorksSubmissionSendView.as_view(),
        name="library-rare-works-submission-send",
    ),
    # E8 el yazması ve nadir eserler listesi — kayıt YAZMAZ.
    path(
        "library/rare-works-submissions/<int:pk>/pdf/",
        views_komisyon_belgeleri.RareWorksSubmissionPdfView.as_view(),
        name="library-rare-works-submission-pdf",
    ),
    path(
        "library/annual-reviews/",
        views_ayiklama.AnnualLibraryReviewListCreateView.as_view(),
        name="library-annual-review-list",
    ),
    path(
        "library/annual-reviews/<int:pk>/",
        views_ayiklama.AnnualLibraryReviewDetailView.as_view(),
        name="library-annual-review-detail",
    ),
    path(
        "library/annual-reviews/<int:pk>/finalize/",
        views_ayiklama.AnnualLibraryReviewFinalizeView.as_view(),
        name="library-annual-review-finalize",
    ),
    path(
        "library/annual-reviews/<int:pk>/reopen/",
        views_ayiklama.AnnualLibraryReviewReopenView.as_view(),
        name="library-annual-review-reopen",
    ),
    # E9 yıl sonu kütüphane raporu — kişisel veri yok; kayıt YAZMAZ.
    path(
        "library/annual-reviews/<int:pk>/pdf/",
        views_komisyon_belgeleri.AnnualLibraryReviewPdfView.as_view(),
        name="library-annual-review-pdf",
    ),
]

# --- F4-L: etiket motoru — şablon, yazıcı kalibrasyonu, kalibrasyon sayfası ve
# PDF önizleme (`apps/kutuphane/labels/urls.py`; düz `path()` girdileri, `include` değil).
urlpatterns += label_urls.urlpatterns
