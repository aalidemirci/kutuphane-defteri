"""Etiket uçları: şablon, yazıcı kalibrasyonu, kalibrasyon sayfası ve PDF önizleme (F4-L).

Kapsam: hazır şablonların ilk listede yazılması, şablon ve kalibrasyon CRUD'u,
PDF uçlarının içerik türü ve dosya adı, önizlemenin **hiçbir kayıt yazmaması**
(D10), nüsha sırasının korunması (D20), Türkçe ret gövdeleri ve serializer alan
kümelerinin anlık görüntüsü (T13). Kilit (423) ve görevli kipi (403) kapıları
`test_uc_kapilari.py`'de URL listesi dolaşılarak kendiliğinden sınanır.

Bütün veriler uydurmadır (CLAUDE.md §2-12).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.kutuphane.labels.geometry import SheetGeometry
from apps.kutuphane.labels.serializers import (
    LabelCalibrationSerializer,
    LabelSheetTemplateSerializer,
)
from apps.kutuphane.models import Copy, CopyStatus, LabelCalibration, LabelKind, LabelSheetTemplate
from apps.kutuphane.services import barcode_reservations
from apps.kutuphane.tests import etiket_olcum as olcum
from apps.kutuphane.tests import ortak

pytestmark = pytest.mark.django_db

SABLONLAR = "/api/v1/library/label-templates/"
KALIBRASYONLAR = "/api/v1/library/label-calibrations/"
KALIBRASYON_SAYFASI = "/api/v1/library/labels/calibration/"
ONIZLEME = "/api/v1/library/labels/preview/"


@pytest.fixture
def istemci() -> APIClient:
    return APIClient()


@pytest.fixture
def sablonlar(istemci: APIClient) -> dict[str, dict[str, Any]]:
    """Hazır şablonlar (ilk listeleme yazar) — ada göre."""
    govde = istemci.get(SABLONLAR).json()
    return {satir["name"]: satir for satir in govde["results"]}


def _varsayilan(sablonlar: dict[str, dict[str, Any]], tur: str) -> dict[str, Any]:
    return next(s for s in sablonlar.values() if s["kind"] == tur and s["is_default"])


def _pdf_govdesi(yanit: Any) -> bytes:
    return b"".join(yanit.streaming_content)


def _nushalar(adet: int) -> list[Copy]:
    eser = ortak.eser(
        title="Kürk Mantolu Madonna", authors="Sabahattin Ali", classification_code="813.54"
    )
    return [ortak.nusha(eser) for _ in range(adet)]


# ============================================================ Serializer anlık görüntüsü
def test_sablon_serializer_alanlari() -> None:
    assert list(LabelSheetTemplateSerializer().fields) == [
        "id",
        "name",
        "kind",
        "kind_display",
        "page_margin_top",
        "page_margin_left",
        "label_width",
        "label_height",
        "rows",
        "cols",
        "gutter_x",
        "gutter_y",
        "corner_radius",
        "is_default",
        "labels_per_sheet",
        "supports_qr",
        "supports_barcode",
        "updated_at",
    ]
    salt_okunur = {
        ad for ad, alan in LabelSheetTemplateSerializer().fields.items() if alan.read_only
    }
    assert salt_okunur == {
        "id",
        "kind_display",
        "labels_per_sheet",
        "supports_qr",
        "supports_barcode",
        "updated_at",
    }


def test_kalibrasyon_serializer_alanlari() -> None:
    alanlar = LabelCalibrationSerializer().fields
    assert list(alanlar) == [
        "id",
        "template",
        "template_name",
        "printer_name",
        "offset_x",
        "offset_y",
        "updated_at",
    ]
    assert {ad for ad, alan in alanlar.items() if alan.read_only} == {
        "id",
        "template_name",
        "updated_at",
    }


# ============================================================ Şablonlar
class TestSablonUclari:
    def test_ilk_listede_hazir_sablonlar_yazilir(self, istemci: APIClient) -> None:
        assert LabelSheetTemplate.objects.count() == 0
        govde = istemci.get(SABLONLAR).json()
        assert govde["count"] == 4
        turler = [s["kind"] for s in govde["results"]]
        assert turler == sorted(turler)  # önce barkod, sonra sırt
        varsayilan = next(s for s in govde["results"] if s["kind"] == "BARCODE" and s["is_default"])
        assert varsayilan["labels_per_sheet"] == 65
        assert varsayilan["label_width"] == 38.1  # sayı, dize değil
        assert varsayilan["supports_barcode"] is True
        assert varsayilan["supports_qr"] is False
        qrli = [s["name"] for s in govde["results"] if s["supports_qr"]]
        assert len(qrli) == 2
        # İkinci liste yeniden yazmaz.
        assert istemci.get(SABLONLAR).json()["count"] == 4

    def test_tur_suzgeci(self, istemci: APIClient) -> None:
        sirt = istemci.get(SABLONLAR, {"kind": "SPINE"}).json()
        assert [s["kind"] for s in sirt["results"]] == ["SPINE"]
        yanit = istemci.get(SABLONLAR, {"kind": "CARD"})
        assert yanit.status_code == 400

    def test_sablon_acilir_varsayilan_yapilir_silinir(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        yanit = istemci.post(
            SABLONLAR,
            {
                "name": "Okulun sırt tabakası",
                "kind": "SPINE",
                "page_margin_top": 10.7,
                "page_margin_left": 4.75,
                "label_width": 38.1,
                "label_height": 21.2,
                "rows": 13,
                "cols": 5,
                "gutter_x": 2.5,
                "is_default": True,
            },
            format="json",
        )
        assert yanit.status_code == 201, yanit.json()
        yeni = yanit.json()
        eski_sirt = _varsayilan(sablonlar, "SPINE")
        assert istemci.get(f"{SABLONLAR}{eski_sirt['id']}/").json()["is_default"] is False

        duzeltme = istemci.patch(
            f"{SABLONLAR}{yeni['id']}/", {"page_margin_top": 11.2}, format="json"
        )
        assert duzeltme.status_code == 200
        assert duzeltme.json()["page_margin_top"] == 11.2

        silme = istemci.delete(f"{SABLONLAR}{yeni['id']}/")
        assert silme.status_code == 204
        assert istemci.get(f"{SABLONLAR}{yeni['id']}/").status_code == 404
        assert LabelSheetTemplate.all_objects.filter(
            pk=yeni["id"], deleted_at__isnull=False
        ).exists()

    def test_sayfaya_sigmayan_sablon_turkce_400(self, istemci: APIClient) -> None:
        yanit = istemci.post(
            SABLONLAR,
            {
                "name": "Taşan tabaka",
                "kind": "BARCODE",
                "page_margin_top": 10.7,
                "page_margin_left": 4.75,
                "label_width": 42,
                "label_height": 21.2,
                "rows": 13,
                "cols": 5,
            },
            format="json",
        )
        assert yanit.status_code == 400
        govde = yanit.json()
        assert "cols" in govde["fields"]
        assert "sayfanın genişliğine sığmıyor" in govde["message"]


# ============================================================ Kalibrasyonlar
class TestKalibrasyonUclari:
    def test_kalibrasyon_acilir_suzulur_ve_tekildir(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        sablon = _varsayilan(sablonlar, "BARCODE")
        yanit = istemci.post(
            KALIBRASYONLAR,
            {
                "template": sablon["id"],
                "printer_name": "İdare Lazer",
                "offset_x": 0.5,
                "offset_y": -0.25,
            },
            format="json",
        )
        assert yanit.status_code == 201, yanit.json()
        assert yanit.json()["offset_y"] == -0.25
        assert yanit.json()["template_name"] == sablon["name"]

        ikinci = istemci.post(
            KALIBRASYONLAR,
            {"template": sablon["id"], "printer_name": "idare lazer", "offset_x": 0, "offset_y": 0},
            format="json",
        )
        assert ikinci.status_code == 400
        assert "printer_name" in ikinci.json()["fields"]

        liste = istemci.get(KALIBRASYONLAR, {"template": sablon["id"]}).json()
        assert [k["printer_name"] for k in liste["results"]] == ["İdare Lazer"]
        sirt = _varsayilan(sablonlar, "SPINE")
        assert istemci.get(KALIBRASYONLAR, {"template": sirt["id"]}).json()["count"] == 0
        assert istemci.get(KALIBRASYONLAR, {"template": "abc"}).status_code == 400

    def test_kayma_siniri_serializerda_da_var(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        sablon = _varsayilan(sablonlar, "BARCODE")
        yanit = istemci.post(
            KALIBRASYONLAR,
            {"template": sablon["id"], "printer_name": "Laser", "offset_x": 12, "offset_y": 0},
            format="json",
        )
        assert yanit.status_code == 400
        assert "offset_x" in yanit.json()["fields"]

    def test_silinen_sablonun_kalibrasyonu_gorunmez(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        sablon = _varsayilan(sablonlar, "BARCODE")
        kalibrasyon = istemci.post(
            KALIBRASYONLAR,
            {"template": sablon["id"], "printer_name": "Laser", "offset_x": 0, "offset_y": 0},
            format="json",
        ).json()
        istemci.delete(f"{SABLONLAR}{sablon['id']}/")
        assert istemci.get(f"{KALIBRASYONLAR}{kalibrasyon['id']}/").status_code == 404
        assert not LabelCalibration.objects.exists()


# ============================================================ Kalibrasyon sayfası
def test_kalibrasyon_sayfasi_pdf(istemci: APIClient, sablonlar: dict[str, dict[str, Any]]) -> None:
    sablon = _varsayilan(sablonlar, "BARCODE")
    kalibrasyon = istemci.post(
        KALIBRASYONLAR,
        {"template": sablon["id"], "printer_name": "İdare Lazer", "offset_x": 1, "offset_y": 0},
        format="json",
    ).json()
    yanit = istemci.post(
        KALIBRASYON_SAYFASI,
        {"template": sablon["id"], "calibration": kalibrasyon["id"]},
        format="json",
    )
    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert "Kalibrasyon-Sayfas" in yanit["Content-Disposition"]
    assert yanit["Cache-Control"] == "no-store"
    pdf = _pdf_govdesi(yanit)
    metin = " ".join(olcum.sayfalar(pdf)[0].metinler())
    assert "İdare Lazer" in metin and "+1,00" in metin

    baska = _varsayilan(sablonlar, "SPINE")
    ret = istemci.post(
        KALIBRASYON_SAYFASI,
        {"template": baska["id"], "calibration": kalibrasyon["id"]},
        format="json",
    )
    assert ret.status_code == 400
    assert ret.json()["message"] == "Seçilen kalibrasyon bu etiket şablonuna ait değil."


# ============================================================ PDF önizleme
class TestOnizleme:
    def test_barkod_etiketi_sirayi_korur_ve_hicbir_sey_yazmaz(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        nushalar = _nushalar(3)
        sira = [nushalar[2].pk, nushalar[0].pk, nushalar[1].pk]
        yanit = istemci.post(
            ONIZLEME,
            {
                "content": "BARCODE",
                "template": _varsayilan(sablonlar, "BARCODE")["id"],
                "copy_ids": sira,
                "start_cell": 5,
            },
            format="json",
        )
        assert yanit.status_code == 200, yanit.content
        assert yanit["Content-Type"] == "application/pdf"
        assert yanit["X-KD-Tabaka-Sayisi"] == "1"
        assert (
            f'filename="Barkod-Etiketi_{timezone.localdate():%d.%m.%Y}.pdf"'
            in yanit["Content-Disposition"]
        )
        sayfa = olcum.sayfalar(_pdf_govdesi(yanit))[0]
        tabaka = SheetGeometry(10.7, 4.75, 38.1, 21.2, 13, 5, gutter_x=2.5)
        for hucre_no, pk in zip((5, 6, 7), sira, strict=True):
            hucre = tabaka.cell(hucre_no - 1)
            metinler = [
                y.metin
                for y in olcum.yazilar_hucrede(
                    sayfa, hucre.left, hucre.top, hucre.right, hucre.bottom
                )
            ]
            beklenen = Copy.objects.get(pk=pk).barcode
            assert f"{beklenen[:4]}-{beklenen[4:]}" in metinler
            assert "813.54 ALİ" in metinler
        # D10: PDF üretmek "basıldı" demek değildir.
        assert not Copy.objects.filter(label_printed_at__isnull=False).exists()

    def test_ikisi_birden_once_sirt_sonra_barkod(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        nushalar = _nushalar(2)
        yanit = istemci.post(
            ONIZLEME,
            {
                "content": "BOTH",
                "template": _varsayilan(sablonlar, "BARCODE")["id"],
                "spine_template": _varsayilan(sablonlar, "SPINE")["id"],
                "copy_ids": [n.pk for n in nushalar],
            },
            format="json",
        )
        assert yanit.status_code == 200, yanit.content
        sayfalar = olcum.sayfalar(_pdf_govdesi(yanit))
        assert len(sayfalar) == 2
        assert "813.54" in sayfalar[0].metinler() and "ALİ" in sayfalar[0].metinler()
        assert olcum.barlar_hucrede(sayfalar[0], 0, 0, 210, 297) == []
        assert olcum.barlar_hucrede(sayfalar[1], 0, 0, 210, 297) != []

    def test_bos_barkod_etiketi_numara_listesiyle(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        aralik = barcode_reservations.reserve(2)
        yanit = istemci.post(
            ONIZLEME,
            {
                "content": "BLANK_BARCODE",
                "template": _varsayilan(sablonlar, "BARCODE")["id"],
                "barcodes": [aralik.first_barcode, aralik.last_barcode],
            },
            format="json",
        )
        assert yanit.status_code == 200, yanit.content
        # Belge adı + basılan numaraların aralığı + yerel tarih; iç kimlik geçmez.
        ilk, son = (f"{kod[:4]}-{kod[4:]}" for kod in (aralik.first_barcode, aralik.last_barcode))
        assert unquote(yanit["Content-Disposition"]).endswith(
            f"Boş-Barkod-Etiketi_{ilk}_{son}_{timezone.localdate():%d.%m.%Y}.pdf"
        )
        metinler = olcum.sayfalar(_pdf_govdesi(yanit))[0].metinler()
        for kod in (aralik.first_barcode, aralik.last_barcode):
            assert f"{kod[:4]}-{kod[4:]}" in metinler

    def test_bos_barkod_onizlemesi_yalniz_acik_ayrilmis_numaraya_basar(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        """İptal edilmiş, nüshaya bağlı ve sayacın henüz vermediği numara reddedilir.

        Aralığın kendi PDF kapısıyla (`printable_numbers`) aynı kural: aksi hâlde
        iptal edilen etiket yeniden basılır, bağlı numara ikinci bir kitaba
        yapıştırılır ya da sayaç o numarayı ileride başka nüshaya verince iki
        kitap aynı etiketi taşır.
        """
        aralik = barcode_reservations.reserve(3)
        iptal, bagli, acik = aralik.numbers.order_by("accession_no")
        barcode_reservations.cancel_numbers(aralik, barcodes=[iptal.barcode])
        eser = ortak.eser(title="Deneme Eseri")
        barcode_reservations.bind_label(label=bagli.barcode, work=eser, acquisition=ortak.edinim())
        gelecek = str(int(aralik.last_barcode) + 5)
        sablon = _varsayilan(sablonlar, "BARCODE")["id"]
        for kod in (iptal.barcode, bagli.barcode, gelecek):
            yanit = istemci.post(
                ONIZLEME,
                {"content": "BLANK_BARCODE", "template": sablon, "barcodes": [acik.barcode, kod]},
                format="json",
            )
            assert yanit.status_code == 400, kod
            cevap = yanit.json()
            assert "barcodes" in cevap["fields"]
            assert f"{kod[:4]}-{kod[4:]}" in cevap["message"]
            assert f"{acik.barcode[:4]}-{acik.barcode[4:]}" not in cevap["message"]
        tamam = istemci.post(
            ONIZLEME,
            {"content": "BLANK_BARCODE", "template": sablon, "barcodes": [acik.barcode]},
            format="json",
        )
        assert tamam.status_code == 200

    @pytest.mark.parametrize(
        ("govde", "alan"),
        [
            ({"content": "BARCODE"}, "copy_ids"),
            ({"content": "BLANK_BARCODE"}, "barcodes"),
            ({"content": "BARCODE", "copy_ids": [999999]}, "copy_ids"),
            ({"content": "BARCODE", "copy_ids": "NUSHA", "start_cell": 66}, "start_cell"),
            ({"content": "BARCODE", "copy_ids": "NUSHA", "include_qr": True}, "include_qr"),
            (
                {"content": "BLANK_BARCODE", "copy_ids": "NUSHA", "barcodes": ["2026000123"]},
                "copy_ids",
            ),
            ({"content": "BLANK_BARCODE", "barcodes": ["2026-000123"]}, "barcodes"),
            ({"content": "BLANK_BARCODE", "barcodes": ["AYRILMIS", "AYRILMIS"]}, "items"),
            (
                {"content": "SPINE", "copy_ids": "NUSHA", "spine_template": "SPINE"},
                "spine_template",
            ),
            ({"content": "KART", "copy_ids": "NUSHA"}, "content"),
        ],
    )
    def test_turkce_ret_govdeleri(
        self,
        istemci: APIClient,
        sablonlar: dict[str, dict[str, Any]],
        govde: dict[str, Any],
        alan: str,
    ) -> None:
        nusha = _nushalar(1)[0]
        istek: dict[str, Any] = {"template": _varsayilan(sablonlar, "BARCODE")["id"], **govde}
        if istek.get("copy_ids") == "NUSHA":
            istek["copy_ids"] = [nusha.pk]
        if istek.get("spine_template") == "SPINE":
            istek["spine_template"] = _varsayilan(sablonlar, "SPINE")["id"]
        if istek.get("barcodes") == ["AYRILMIS", "AYRILMIS"]:
            # Numara kapısından geçen (açık ayrılmış) numara iki kez: motor reddeder.
            kod = barcode_reservations.reserve(1).first_barcode
            istek["barcodes"] = [kod, kod]
        yanit = istemci.post(ONIZLEME, istek, format="json")
        assert yanit.status_code == 400, yanit.content
        cevap = yanit.json()
        assert set(cevap) == {"code", "message", "fields"}
        assert alan in cevap["fields"], cevap

    def test_farkli_izgarada_sirt_sablonu_reddedilir(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        qrli = next(s for s in sablonlar.values() if s["labels_per_sheet"] == 44)
        yanit = istemci.post(
            ONIZLEME,
            {
                "content": "BOTH",
                "template": _varsayilan(sablonlar, "BARCODE")["id"],
                "spine_template": qrli["id"],
                "copy_ids": [_nushalar(1)[0].pk],
            },
            format="json",
        )
        assert yanit.status_code == 400
        assert "aynı sıra ve hücre düzeninde" in yanit.json()["message"]

    def test_silinmis_ve_elden_cikmis_nushaya_etiket_basilmaz(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        silinen, devredilen = _nushalar(2)
        silinen.delete()
        Copy.objects.filter(pk=devredilen.pk).update(status=CopyStatus.TRANSFERRED)
        sablon = _varsayilan(sablonlar, "BARCODE")["id"]
        for pk in (silinen.pk, devredilen.pk):
            yanit = istemci.post(
                ONIZLEME,
                {"content": "BARCODE", "template": sablon, "copy_ids": [pk]},
                format="json",
            )
            assert yanit.status_code == 400
            assert "copy_ids" in yanit.json()["fields"]

    def test_baska_sablonun_kalibrasyonu_reddedilir(
        self, istemci: APIClient, sablonlar: dict[str, dict[str, Any]]
    ) -> None:
        sirt = _varsayilan(sablonlar, "SPINE")
        kalibrasyon = istemci.post(
            KALIBRASYONLAR,
            {"template": sirt["id"], "printer_name": "Laser", "offset_x": 0, "offset_y": 0},
            format="json",
        ).json()
        yanit = istemci.post(
            ONIZLEME,
            {
                "content": "BARCODE",
                "template": _varsayilan(sablonlar, "BARCODE")["id"],
                "calibration": kalibrasyon["id"],
                "copy_ids": [_nushalar(1)[0].pk],
            },
            format="json",
        )
        assert yanit.status_code == 400
        assert "calibration" in yanit.json()["fields"]


def test_kart_turu_sablon_etiket_basiminda_kullanilamaz(istemci: APIClient) -> None:
    kart = LabelSheetTemplate.objects.create(
        name="Kart",
        kind=LabelKind.CARD,
        page_margin_top=10,
        page_margin_left=10,
        label_width=85,
        label_height=54,
        rows=5,
        cols=2,
    )
    yanit = istemci.post(
        ONIZLEME,
        {"content": "BARCODE", "template": kart.pk, "copy_ids": [_nushalar(1)[0].pk]},
        format="json",
    )
    assert yanit.status_code == 400
    assert "Üye kartı" in yanit.json()["message"]


# ============================================================ Kuyruk kolunun bağlantı noktası
@dataclass(frozen=True)
class _Is:
    """Basım kuyruğunun iş tanımıyla (`services.label_render.LabelJob`) aynı alanlar."""

    kind: str
    template: LabelSheetTemplate
    calibration: LabelCalibration | None
    start_cell: int
    copies: Sequence[Copy] = ()
    barcodes: Sequence[str] = ()
    spine_template: LabelSheetTemplate | None = None
    spine_calibration: LabelCalibration | None = None
    include_qr: bool = False
    hold_unprintable: bool = False


def test_basim_isi_motora_baglanir_ve_hicbir_sey_yazmaz() -> None:
    """`render_label_job`: nüsha sırası, başlangıç hücresi ve kuyruğun "BLANK" adı."""
    from apps.kutuphane.labels import render_label_job, seed

    seed.ensure_default_templates()
    barkod = seed.default_template(LabelKind.BARCODE)
    sirt = seed.default_template(LabelKind.SPINE)
    assert barkod is not None and sirt is not None
    nushalar = _nushalar(3)
    kalibrasyon = LabelCalibration.objects.create(
        template=barkod, printer_name="Laser", offset_x=Decimal("0.5"), offset_y=Decimal("0")
    )

    sonuc = render_label_job(
        _Is(
            kind="BOTH",
            template=barkod,
            calibration=kalibrasyon,
            start_cell=64,
            copies=list(reversed(nushalar)),
            spine_template=sirt,
        )
    )
    assert sonuc.sheets_per_part == 2 and sonuc.page_count == 4
    assert [(y.sheet, y.cell_number) for y in sonuc.placements] == [(0, 64), (0, 65), (1, 1)]
    metin = " ".join(olcum.sayfalar(sonuc.pdf)[2].metinler())
    assert nushalar[2].barcode[4:] in metin.replace("-", "")
    assert not Copy.objects.filter(label_printed_at__isnull=False).exists()

    bos = render_label_job(
        _Is(kind="BLANK", template=barkod, calibration=None, start_cell=1, barcodes=["2026000900"])
    )
    assert "2026-000900" in olcum.sayfalar(bos.pdf)[0].metinler()


def test_etiket_sablonlarinda_yasakli_css_yok() -> None:
    """CLAUDE.md §3: `text-transform` yok (WeasyPrint i→I), CSS değişkeni yok, `{% url` yok."""
    klasor = Path(settings.BASE_DIR) / "templates" / "documents"
    for ad in ("etiket_tabakasi.html", "etiket_kalibrasyon.html"):
        # Açıklama blokları kuralın kendisini anlatır; denetim basılan kısımdadır.
        metin = re.sub(
            r"{% comment %}.*?{% endcomment %}",
            "",
            (klasor / ad).read_text(encoding="utf-8"),
            flags=re.S,
        )
        assert "text-transform" not in metin, ad
        assert "var(" not in metin, ad
        assert "{% url" not in metin and "{#" not in metin, ad
