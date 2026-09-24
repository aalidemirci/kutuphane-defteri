"""Hazır etiket şablonları ve şablon / kalibrasyon servisleri (F4 — `labels/seed.py`, `labels/services.py`).

- Tohum ilk kullanımda yazılır, ikinci çağrıda yazılmaz; kullanıcı silse de
  geri getirilmez (düzenlemeye saygı).
- Tür başına tek varsayılan: yeni varsayılan eskisini AYNI işlemde kapatır.
- Izgara A4'e sığmıyorsa şablon kaydedilmez; ad tekliği Türkçe katlamalıdır.
- Kalibrasyon şablon × yazıcı başına tektir, kayma ±10 mm'yi aşamaz; şablon
  silinince kalibrasyonları da (yumuşak) silinir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from apps.kutuphane.labels import seed
from apps.kutuphane.labels import services as label_services
from apps.kutuphane.models import LabelCalibration, LabelKind, LabelSheetTemplate

pytestmark = pytest.mark.django_db


def _sablon(**alanlar: Any) -> LabelSheetTemplate:
    temel: dict[str, Any] = {
        "name": "Deneme tabakası",
        "kind": LabelKind.BARCODE,
        "page_margin_top": Decimal("10.70"),
        "page_margin_left": Decimal("4.75"),
        "label_width": Decimal("38.10"),
        "label_height": Decimal("21.20"),
        "rows": 13,
        "cols": 5,
        "gutter_x": Decimal("2.50"),
    }
    return label_services.create_template(**{**temel, **alanlar})


# ============================================================ Tohum
class TestHazirSablonlar:
    def test_ilk_kullanimda_yazilir_ikincide_yazilmaz(self) -> None:
        assert LabelSheetTemplate.all_objects.count() == 0
        assert seed.ensure_default_templates() == len(seed.DEFAULT_TEMPLATES)
        assert seed.ensure_default_templates() == 0
        assert LabelSheetTemplate.objects.count() == len(seed.DEFAULT_TEMPLATES)

    def test_tur_basina_varsayilanlar(self) -> None:
        seed.ensure_default_templates()
        barkod = seed.default_template(LabelKind.BARCODE)
        sirt = seed.default_template(LabelKind.SPINE)
        assert barkod is not None and sirt is not None
        assert barkod.labels_per_sheet == 65 and sirt.labels_per_sheet == 65
        assert (barkod.label_width, barkod.label_height) == (Decimal("38.10"), Decimal("21.20"))
        assert seed.default_template(LabelKind.CARD) is None

    def test_silinen_hazir_sablon_geri_getirilmez(self) -> None:
        seed.ensure_default_templates()
        for sablon in LabelSheetTemplate.objects.all():
            label_services.delete_template(sablon)
        assert seed.ensure_default_templates() == 0
        assert LabelSheetTemplate.objects.count() == 0

    def test_kullanicinin_kendi_sablonu_varsa_tohum_yazilmaz(self) -> None:
        _sablon(name="Okulun tabakası")
        assert seed.ensure_default_templates() == 0
        assert list(LabelSheetTemplate.objects.values_list("name", flat=True)) == [
            "Okulun tabakası"
        ]


# ============================================================ Şablon servisi
class TestSablonServisi:
    def test_yeni_varsayilan_eskisini_ayni_islemde_kapatir(self) -> None:
        eski = _sablon(name="Eski", is_default=True)
        yeni = _sablon(name="Yeni", is_default=True)
        eski.refresh_from_db()
        assert (eski.is_default, yeni.is_default) == (False, True)
        # Başka türün varsayılanına dokunulmaz.
        sirt = _sablon(name="Sırt", kind=LabelKind.SPINE, is_default=True)
        yeni.refresh_from_db()
        assert yeni.is_default and sirt.is_default

    def test_varsayilan_guncellemeyle_de_tasinir(self) -> None:
        a = _sablon(name="A", is_default=True)
        b = _sablon(name="B")
        label_services.update_template(b, is_default=True)
        a.refresh_from_db()
        assert not a.is_default
        assert (
            LabelSheetTemplate.objects.filter(kind=LabelKind.BARCODE, is_default=True).count() == 1
        )

    def test_sayfaya_sigmayan_izgara_kaydedilmez(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _sablon(rows=14)  # 10,7 + 14 × 21,2 = 307,5 mm > 297 mm
        assert "rows" in hata.value.message_dict
        assert LabelSheetTemplate.objects.count() == 0

    def test_ad_tekligi_turkce_katlamali(self) -> None:
        _sablon(name="Sırt tabakası")
        with pytest.raises(ValidationError) as hata:
            _sablon(name="  SIRT   TABAKASI ")
        assert hata.value.message_dict["name"] == ["Bu adla bir etiket şablonu zaten var."]

    def test_kart_sablonu_bu_ekrandan_acilmaz(self) -> None:
        with pytest.raises(ValidationError) as hata:
            _sablon(kind=LabelKind.CARD)
        assert "kind" in hata.value.message_dict

    def test_ad_bosluklari_sadelesir_ve_bos_ad_reddedilir(self) -> None:
        assert _sablon(name="  Okul   tabakası ").name == "Okul tabakası"
        with pytest.raises(ValidationError):
            _sablon(name="   ")

    def test_silme_yumusaktir_ve_kalibrasyonlari_da_siler(self) -> None:
        sablon = _sablon()
        kalibrasyon = label_services.create_calibration(
            template=sablon, printer_name="Laser", offset_x=Decimal("0.5"), offset_y=Decimal("0")
        )
        label_services.delete_template(sablon)
        assert LabelSheetTemplate.all_objects.get(pk=sablon.pk).deleted_at is not None
        assert LabelCalibration.all_objects.get(pk=kalibrasyon.pk).deleted_at is not None
        assert not LabelCalibration.objects.exists()


# ============================================================ Kalibrasyon servisi
class TestKalibrasyonServisi:
    def test_sablon_ve_yazici_basina_tek_kalibrasyon_turkce_katlamali(self) -> None:
        sablon = _sablon()
        label_services.create_calibration(
            template=sablon,
            printer_name="İdare Yazıcısı",
            offset_x=Decimal("0"),
            offset_y=Decimal("0"),
        )
        with pytest.raises(ValidationError) as hata:
            label_services.create_calibration(
                template=sablon,
                printer_name="idare yazıcısı",
                offset_x=Decimal("1"),
                offset_y=Decimal("0"),
            )
        assert "printer_name" in hata.value.message_dict
        # Başka şablonda aynı yazıcı serbesttir.
        diger = _sablon(name="Başka tabaka")
        label_services.create_calibration(
            template=diger,
            printer_name="İdare Yazıcısı",
            offset_x=Decimal("0"),
            offset_y=Decimal("0"),
        )

    def test_kayma_siniri(self) -> None:
        sablon = _sablon()
        with pytest.raises(ValidationError) as hata:
            label_services.create_calibration(
                template=sablon,
                printer_name="Laser",
                offset_x=Decimal("10.01"),
                offset_y=Decimal("0"),
            )
        assert "offset_x" in hata.value.message_dict

    def test_kalibrasyonun_sablonu_degistirilemez(self) -> None:
        a, b = _sablon(name="A"), _sablon(name="B")
        kalibrasyon = label_services.create_calibration(
            template=a, printer_name="Laser", offset_x=Decimal("0"), offset_y=Decimal("0")
        )
        with pytest.raises(ValidationError):
            label_services.update_calibration(kalibrasyon, template=b)
        guncel = label_services.update_calibration(kalibrasyon, offset_y=Decimal("-0.75"))
        assert guncel.offset_y == Decimal("-0.75")

    def test_silinmis_sablona_kalibrasyon_acilmaz(self) -> None:
        sablon = _sablon()
        label_services.delete_template(sablon)
        with pytest.raises(ValidationError):
            label_services.create_calibration(
                template=sablon, printer_name="Laser", offset_x=Decimal("0"), offset_y=Decimal("0")
            )
