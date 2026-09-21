"""`kutuphane` API uçları — İNCE görünümler (tasarım §8.1).

F1'de yalnız katalog Excel şablonu vardır; eser, nüsha ve içe aktarma uçları
F2-F3'te OYS `apps/kutuphane/views.py`'den uyarlanarak gelir. Görünüm ve URL
adları OYS'den korunur (API yüzeyi OYS'den çıkarıldı).

Görevli kipinin izin listesine GİRMEZ (varsayılan kapalı, CLAUDE.md §2-4):
şablon indirmek masa işi değildir. Kilitliyken kilit ara katmanı 423 döner.
"""

from __future__ import annotations

from io import BytesIO

from django.http import FileResponse
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.kutuphane import excel_template

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CatalogImportTemplateView(APIView):
    """GET → boş katalog Excel şablonu (Katalog + Sütunlar + Örnek sayfaları).

    Veritabanına dokunmaz: kurulum bitmeden, boş programda da indirilebilir.
    """

    def get(self, request: Request) -> FileResponse:
        return FileResponse(
            BytesIO(excel_template.build_catalog_template()),
            as_attachment=True,
            filename=excel_template.template_filename(),
            content_type=XLSX_CONTENT_TYPE,
        )
