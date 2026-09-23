"""Toplu katalog aktarımı uçları — gövde biçimi, kapılar ve hata sözleşmesi (F3).

Kilit (423), görevli kipi (403) ve parolasız yazma (409) kapıları BU DOSYADA
tekrarlanmaz: `test_uc_kapilari.py` `apps.kutuphane.urls`'ü dolaşır ve buradaki
uçlar ona kendiliğinden girer. Burada uçların kendi sözleşmesi sabitlenir.

Dosya yüklenen bir istek `multipart/form-data`'dır ve orada HER ALAN METİNDİR:
kararlar ve bölüm eşlemesi JSON metni olarak gelir. Bu testler o yolu da
dolaşır — `JsonOrTextField` olmadan kararlar sessizce dizge olarak servise iner
ve hiçbir şey yapmazdı.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.kutuphane import ai_bridge
from apps.kutuphane import serializers as kutuphane_serializers
from apps.kutuphane.models import CatalogImportRun, CatalogImportStatus, Copy, Work
from apps.kutuphane.tests import ortak, sentetik_katalog

pytestmark = pytest.mark.django_db

ONIZLEME_YOLU = "/api/v1/library/import/preview/"
UYGULAMA_YOLU = "/api/v1/library/import/apply/"
KOSULAR_YOLU = "/api/v1/library/import/runs/"
KOMUT_YOLU = "/api/v1/library/import/ai-prompt/"

KITAP = {
    "title": "Kürk Mantolu Madonna",
    "authors": "Sabahattin Ali",
    "resource_type": "Kitap",
    "copies": 2,
}


def _dosya(satirlar: list[dict[str, Any]] | None = None, *, ad: str = "katalog.xlsx"):  # type: ignore[no-untyped-def]
    icerik = sentetik_katalog.katalog_dosyasi(satirlar if satirlar is not None else [KITAP])
    return SimpleUploadedFile(
        ad, icerik, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _gonder(yol: str, **alanlar: Any) -> Any:
    return APIClient().post(yol, alanlar, format="multipart")


class TestOnizlemeUcu:
    def test_onizleme_yazmadan_rapor_doner(self) -> None:
        yanit = _gonder(ONIZLEME_YOLU, file=_dosya())

        assert yanit.status_code == 200, yanit.json()
        govde = yanit.json()
        assert govde["dry_run"] is True
        assert govde["stats"]["copies_created"] == 2
        assert govde["rows"][0]["bucket"] == "new"
        assert Work.objects.count() == 0

    def test_dosya_da_govde_de_yoksa_400(self) -> None:
        yanit = APIClient().post(ONIZLEME_YOLU, {}, format="json")

        assert yanit.status_code == 400
        assert "tam olarak biri" in yanit.json()["message"]

    def test_okunamayan_dosya_400_ve_turkce_ileti(self) -> None:
        bozuk = SimpleUploadedFile("liste.csv", b"eser adi;yazar\n", content_type="text/csv")

        yanit = _gonder(ONIZLEME_YOLU, file=bozuk)

        assert yanit.status_code == 400
        assert "Excel olarak okunamadı" in yanit.json()["message"]

    def test_buyuk_dosya_400_doner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tavan dosya BELLEĞE ALINMADAN uygulanır (`DATA_UPLOAD_MAX_MEMORY_SIZE` yetmez)."""
        monkeypatch.setattr(kutuphane_serializers, "MAX_UPLOAD_BYTES", 1024)

        yanit = _gonder(
            ONIZLEME_YOLU,
            file=SimpleUploadedFile("buyuk.xlsx", b"P" * 2048, content_type="application/xlsx"),
        )

        assert yanit.status_code == 400
        assert "çok büyük" in yanit.json()["fields"]["file"][0]

    def test_bozuk_bolum_kimligi_500_degil_400_doner(self) -> None:
        """Sarmalanmayan `int()` 500 üretirdi; sözleşme `{code, message, fields}`tir."""
        yanit = _gonder(
            ONIZLEME_YOLU,
            file=_dosya([{**KITAP, "shelf_location": "Gezi"}]),
            section_map=json.dumps({"Gezi": "abc"}),
        )

        assert yanit.status_code == 400, yanit.json()
        assert "section_map" in yanit.json()["fields"]

    def test_eslesmeyen_bolum_yanitta_sorulur(self) -> None:
        yanit = _gonder(ONIZLEME_YOLU, file=_dosya([{**KITAP, "shelf_location": "Gezi"}]))

        assert yanit.json()["unknown_sections"] == [{"value": "Gezi", "rows": [2], "count": 1}]


class TestUygulamaUcu:
    def test_uygulama_201_ve_parti_kimligi_doner(self) -> None:
        yanit = _gonder(UYGULAMA_YOLU, file=_dosya())

        assert yanit.status_code == 201, yanit.json()
        govde = yanit.json()
        assert govde["label_batch"]["copy_count"] == 2
        assert Copy.objects.count() == 2

    def test_ayni_dosyanin_ikinci_uygulamasi_400(self) -> None:
        _gonder(UYGULAMA_YOLU, file=_dosya())

        yanit = _gonder(UYGULAMA_YOLU, file=_dosya())

        assert yanit.status_code == 400
        assert "ikinci kez" in yanit.json()["message"]
        assert "file" in yanit.json()["fields"]
        assert Copy.objects.count() == 2

    def test_kararlar_multipart_json_metni_olarak_gecer(self) -> None:
        mevcut = ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        yanit = _gonder(
            UYGULAMA_YOLU,
            file=_dosya([{**KITAP, "copies": 1}]),
            decisions=json.dumps({"2": {"action": "attach", "work": mevcut.pk}}),
        )

        assert yanit.status_code == 201, yanit.json()
        assert Work.objects.count() == 1
        assert mevcut.copies.count() == 1

    def test_karar_bekleyen_satir_400_doner(self) -> None:
        ortak.eser(title="Kürk Mantolu Madonna", authors="Başka Yazar")

        yanit = _gonder(UYGULAMA_YOLU, file=_dosya([{**KITAP, "copies": 1}]))

        assert yanit.status_code == 400
        assert "karar bekliyor" in yanit.json()["message"]
        assert Copy.objects.count() == 0

    def test_bolum_eslemesi_ve_yeni_bolum_multipart_gecer(self) -> None:
        yanit = _gonder(
            UYGULAMA_YOLU,
            file=_dosya([{**KITAP, "shelf_location": "Gezi", "copies": 1}]),
            new_sections=json.dumps(["Gezi"]),
        )

        assert yanit.status_code == 201, yanit.json()
        assert Copy.objects.get().section is not None

    def test_edinim_alanlari_gonderilebilir(self) -> None:
        yanit = _gonder(
            UYGULAMA_YOLU,
            file=_dosya([{**KITAP, "copies": 1}]),
            method="PURCHASE",
            date="2026-09-01",
            unit_price="45.50",
        )

        assert yanit.status_code == 201, yanit.json()
        edinim = Copy.objects.get().acquisition
        assert (edinim.method, str(edinim.unit_price)) == ("PURCHASE", "45.50")

    def test_bozuk_karar_metni_400(self) -> None:
        yanit = _gonder(UYGULAMA_YOLU, file=_dosya(), decisions="{bozuk")

        assert yanit.status_code == 400
        assert "decisions" in yanit.json()["fields"]

    def test_parti_etiket_kisayolundan_suzulur(self) -> None:
        """F4 kısayolu: aktarım raporundaki parti kimliği nüsha listesini süzer (§8.1)."""
        parti = _gonder(UYGULAMA_YOLU, file=_dosya()).json()["label_batch"]["acquisition"]

        yanit = APIClient().get(
            "/api/v1/library/copies/", {"acquisition": parti, "only_unlabeled": "true"}
        )

        assert yanit.status_code == 200
        assert yanit.json()["count"] == 2

    def test_sayisal_olmayan_parti_suzgeci_400(self) -> None:
        yanit = APIClient().get("/api/v1/library/copies/", {"acquisition": "iki"})

        assert yanit.status_code == 400
        assert "acquisition" in yanit.json()["fields"]


class TestKopruJsonYolu:
    """Yapıştırılan JSON (§8.2): dosya yerine gövdeyle gelir, kaynak kendiliğinden köprüdür."""

    GOVDE = {
        "schema_version": "v1",
        "items": [{"title": "Huzur", "authors": "Ahmet Hamdi Tanpınar", "copies": 2}],
    }

    def test_yapistirilan_json_uygulanir(self) -> None:
        yanit = APIClient().post(UYGULAMA_YOLU, {"payload": self.GOVDE}, format="json")

        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["source"] == "AI_JSON"
        assert Copy.objects.count() == 2

    def test_bozuk_sema_400_ve_turkce_ileti(self) -> None:
        yanit = APIClient().post(
            UYGULAMA_YOLU, {"payload": {"schema_version": "v9", "items": []}}, format="json"
        )

        assert yanit.status_code == 400
        assert "Şema sürümü" in yanit.json()["message"]

    def test_hem_dosya_hem_govde_reddedilir(self) -> None:
        yanit = _gonder(ONIZLEME_YOLU, file=_dosya(), payload=json.dumps(self.GOVDE))

        assert yanit.status_code == 400

    def test_json_dosyasi_yuklenebilir(self) -> None:
        """Kullanıcı aracın verdiği metni dosyaya kaydedip yükleyebilir (§8.2)."""
        dosya = SimpleUploadedFile(
            "kunye.json",
            json.dumps(self.GOVDE).encode("utf-8"),
            content_type="application/json",
        )

        yanit = _gonder(UYGULAMA_YOLU, file=dosya, source="AI_JSON")

        assert yanit.status_code == 201, yanit.json()
        assert Copy.objects.count() == 2

    def test_bozuk_json_dosyasi_400_ve_turkce_ileti(self) -> None:
        dosya = SimpleUploadedFile("kunye.json", b"{bozuk", content_type="application/json")

        yanit = _gonder(ONIZLEME_YOLU, file=dosya, source="AI_JSON")

        assert yanit.status_code == 400
        assert "JSON olarak okunamadı" in yanit.json()["message"]


class TestGecmisVeIptal:
    def test_kosu_listesi_en_yeniden_eskiye(self) -> None:
        _gonder(ONIZLEME_YOLU, file=_dosya())
        _gonder(UYGULAMA_YOLU, file=_dosya())

        yanit = APIClient().get(KOSULAR_YOLU)

        assert yanit.status_code == 200
        durumlar = [satir["status"] for satir in yanit.json()["results"]]
        assert durumlar == [CatalogImportStatus.APPLIED, CatalogImportStatus.DRY_RUN]

    def test_kosu_listesi_duruma_gore_suzulur(self) -> None:
        _gonder(ONIZLEME_YOLU, file=_dosya())

        yanit = APIClient().get(KOSULAR_YOLU, {"status": CatalogImportStatus.APPLIED})

        assert yanit.json()["count"] == 0

    def test_onizleme_kosusu_iptal_edilir(self) -> None:
        kimlik = _gonder(ONIZLEME_YOLU, file=_dosya()).json()["run_id"]

        yanit = APIClient().post(f"{KOSULAR_YOLU}{kimlik}/discard/", {}, format="json")

        assert yanit.status_code == 200
        assert CatalogImportRun.objects.get(pk=kimlik).status == CatalogImportStatus.DISCARDED

    def test_uygulanmis_kosu_iptal_edilemez(self) -> None:
        kimlik = _gonder(UYGULAMA_YOLU, file=_dosya()).json()["run_id"]

        yanit = APIClient().post(f"{KOSULAR_YOLU}{kimlik}/discard/", {}, format="json")

        assert yanit.status_code == 400
        assert "kayıtta kalır" in yanit.json()["message"]

    def test_bulunmayan_kosu_404(self) -> None:
        yanit = APIClient().post(f"{KOSULAR_YOLU}999/discard/", {}, format="json")

        assert yanit.status_code == 404


class TestKopruKomutuUcu:
    def test_komut_metni_ve_dort_uyari_doner(self) -> None:
        yanit = APIClient().get(KOMUT_YOLU)

        assert yanit.status_code == 200
        govde = yanit.json()
        assert govde["schema_version"] == ai_bridge.SCHEMA_VERSION
        assert govde["notes"] == list(ai_bridge.UI_NOTES)
        assert len(govde["notes"]) == 4
        assert "schema_version" in govde["prompt"]
