"""Etiket tabakasının yerleşim hesabı (F4 — `labels/geometry.py`).

Saf hesap testleridir (PDF yok, veritabanı yok): hazır şablonların ölçüleri,
hücre konum formülü, başlangıç hücresi, kalibrasyon kayması, tabaka sayısı,
sırt ve barkodun ortak planı ve barkodun yazıcı noktasına hizalanması.
PDF'in kendisinden yapılan ölçümler `test_etiket_pdf.py`'dedir.
"""

from __future__ import annotations

import math
import re

import pytest

from apps.kutuphane.labels import seed
from apps.kutuphane.labels.geometry import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    MAX_OFFSET_MM,
    CalibrationOffset,
    LabelError,
    SheetGeometry,
    plan_placements,
    sheet_count,
    snap_to_module,
)
from apps.kutuphane.models import LabelKind

#: Varsayılan 65'li tabaka (Label Planet LP65/38 şablon bilgisi — seed.py).
TABAKA_65 = SheetGeometry(
    margin_top=10.7,
    margin_left=4.75,
    label_width=38.1,
    label_height=21.2,
    rows=13,
    cols=5,
    gutter_x=2.5,
)


def _tohum(ad_parcasi: str) -> seed.TemplateSeed:
    return next(t for t in seed.DEFAULT_TEMPLATES if ad_parcasi in t.name)


def _geometri(tohum: seed.TemplateSeed) -> SheetGeometry:
    return SheetGeometry(
        margin_top=float(tohum.page_margin_top),
        margin_left=float(tohum.page_margin_left),
        label_width=float(tohum.label_width),
        label_height=float(tohum.label_height),
        rows=tohum.rows,
        cols=tohum.cols,
        gutter_x=float(tohum.gutter_x),
        gutter_y=float(tohum.gutter_y),
    )


# ============================================================ Hazır şablonlar
class TestHazirSablonOlculeri:
    def test_65li_tabaka_simetrik_ve_kaynaktaki_olculerle_ayni(self) -> None:
        """Kaynak ölçüsü: üst/alt 10,7 · sol/sağ 4,75 · yatay adım 40,6 · dikey adım 21,2."""
        g = _geometri(_tohum("Barkod etiketi — 38,1 × 21,2 mm, 65'li"))
        assert (g.rows, g.cols, g.capacity) == (13, 5, 65)
        assert g.label_width + g.gutter_x == pytest.approx(40.6)  # yatay adım
        assert g.label_height + g.gutter_y == pytest.approx(21.2)  # dikey adım
        sag = A4_WIDTH_MM - g.margin_left - g.grid_width
        alt = A4_HEIGHT_MM - g.margin_top - g.grid_height
        assert sag == pytest.approx(g.margin_left) == pytest.approx(4.75)
        assert alt == pytest.approx(g.margin_top) == pytest.approx(10.7)

    def test_44lu_tabaka_simetrik_hesaplanmistir(self) -> None:
        g = _geometri(_tohum("44'lü"))
        assert (g.rows, g.cols, g.capacity) == (11, 4, 44)
        assert A4_WIDTH_MM - g.margin_left - g.grid_width == pytest.approx(g.margin_left)
        assert A4_HEIGHT_MM - g.margin_top - g.grid_height == pytest.approx(g.margin_top)

    def test_40li_tabaka_kenardan_kenaradir(self) -> None:
        g = _geometri(_tohum("40'lı"))
        assert (g.rows, g.cols, g.capacity) == (10, 4, 40)
        assert g.grid_width == pytest.approx(A4_WIDTH_MM)
        assert g.grid_height == pytest.approx(A4_HEIGHT_MM)
        assert (g.margin_left, g.margin_top) == (0.0, 0.0)

    def test_hazir_sablonlarin_hepsi_a4e_sigar(self) -> None:
        for tohum in seed.DEFAULT_TEMPLATES:
            _geometri(tohum).validate()

    def test_tur_basina_tek_varsayilan_ve_sirt_barkodla_ayni_izgarada(self) -> None:
        varsayilanlar = [t for t in seed.DEFAULT_TEMPLATES if t.is_default]
        assert sorted(t.kind for t in varsayilanlar) == sorted([LabelKind.BARCODE, LabelKind.SPINE])
        sirt, barkod = (
            next(t for t in varsayilanlar if t.kind == tur)
            for tur in (LabelKind.SPINE, LabelKind.BARCODE)
        )
        assert _geometri(sirt).same_grid_key == _geometri(barkod).same_grid_key

    def test_dogrulanamayan_olcu_adinda_isaretli(self) -> None:
        """Kenar boşluğu yayımlanmış kaynaktan doğrulanamayan şablon "yaklaşık" der."""
        assert "yaklaşık" in _tohum("44'lü").name

    def test_kullaniciya_gorunen_adlarda_kagit_boyunun_kisa_adi_yok(self) -> None:
        """Sözlük §1 "Etiket şablonu": ölçü milimetreyle yazılır, kısa ad kullanılmaz."""
        kisa_ad = re.compile(r"\bA4\b")
        for tohum in seed.DEFAULT_TEMPLATES:
            assert not kisa_ad.search(tohum.name), tohum.name
        with pytest.raises(LabelError) as hata:
            CalibrationOffset(x=MAX_OFFSET_MM + 1, y=0).validate()
        assert not kisa_ad.search(str(hata.value)) and "210 × 297 mm" in str(hata.value)


# ============================================================ Hücre konumu
class TestHucreKonumu:
    def test_ilk_ve_son_hucre(self) -> None:
        ilk = TABAKA_65.cell(0)
        son = TABAKA_65.cell(64)
        assert (ilk.left, ilk.top, ilk.number) == (4.75, 10.7, 1)
        assert (son.row, son.col, son.number) == (12, 4, 65)
        assert son.left == pytest.approx(4.75 + 4 * 40.6)
        assert son.top == pytest.approx(10.7 + 12 * 21.2)
        assert son.right == pytest.approx(210 - 4.75)
        assert son.bottom == pytest.approx(297 - 10.7)

    def test_hucreler_satir_onceliklidir(self) -> None:
        """1-5 ilk satır soldan sağa; 6. hücre ikinci satırın başıdır."""
        hucreler = TABAKA_65.cells()
        assert [h.col for h in hucreler[:5]] == [0, 1, 2, 3, 4]
        assert {h.row for h in hucreler[:5]} == {0}
        assert (hucreler[5].row, hucreler[5].col) == (1, 0)

    def test_kalibrasyon_kaymasi_her_hucreye_aynen_eklenir(self) -> None:
        kayma = CalibrationOffset(x=1.25, y=-0.5)
        for duz, kaymali in zip(TABAKA_65.cells(), TABAKA_65.cells(kayma), strict=True):
            assert kaymali.left - duz.left == pytest.approx(1.25)
            assert kaymali.top - duz.top == pytest.approx(-0.5)
            assert (kaymali.width, kaymali.height) == (duz.width, duz.height)

    def test_tabaka_disindaki_hucre_reddedilir(self) -> None:
        with pytest.raises(LabelError):
            TABAKA_65.cell(65)
        with pytest.raises(LabelError):
            TABAKA_65.cell(-1)


# ============================================================ Başlangıç hücresi ve plan
class TestYerlesimPlani:
    def test_65_etiket_tek_tabaka_66_iki_tabaka(self) -> None:
        assert sheet_count(65, capacity=65) == 1
        assert sheet_count(66, capacity=65) == 2
        plan = plan_placements(66, capacity=65)
        assert (plan[64].sheet, plan[64].cell_number) == (0, 65)
        assert (plan[65].sheet, plan[65].cell_number) == (1, 1)

    def test_baslangic_hucresi_ilk_tabakaya_uygulanir(self) -> None:
        """Başlangıç 60: 1.-6. etiket 60.-65. hücreye, 7. etiket 2. tabakanın 1. hücresine."""
        plan = plan_placements(8, capacity=65, start_cell=60)
        assert [(p.sheet, p.cell_number) for p in plan] == [
            (0, 60),
            (0, 61),
            (0, 62),
            (0, 63),
            (0, 64),
            (0, 65),
            (1, 1),
            (1, 2),
        ]
        assert sheet_count(8, capacity=65, start_cell=60) == 2
        assert sheet_count(6, capacity=65, start_cell=60) == 1

    def test_plan_girdi_sirasini_korur(self) -> None:
        plan = plan_placements(130, capacity=65, start_cell=3)
        assert [p.item_index for p in plan] == list(range(130))
        global_sira = [p.sheet * 65 + p.cell_index for p in plan]
        assert global_sira == sorted(global_sira)
        assert len(set(global_sira)) == 130

    @pytest.mark.parametrize("hucre", [0, 66, -3])
    def test_tabaka_disindaki_baslangic_hucresi_reddedilir(self, hucre: int) -> None:
        with pytest.raises(LabelError) as hata:
            plan_placements(1, capacity=65, start_cell=hucre)
        assert hata.value.field == "start_cell"
        assert "1 ile 65 arasında" in hata.value.text

    def test_etiket_yoksa_tabaka_yok(self) -> None:
        assert sheet_count(0, capacity=65) == 0


# ============================================================ Doğrulama
class TestIzgaraDogrulamasi:
    def test_sayfadan_tasan_izgara_reddedilir(self) -> None:
        # 10 + 5 × 40,1 = 210,5 mm > 210 mm (payın ötesinde)
        genis = SheetGeometry(
            margin_top=10, margin_left=10, label_width=40.1, label_height=20, rows=5, cols=5
        )
        with pytest.raises(LabelError) as hata:
            genis.validate()
        assert hata.value.field == "cols"

        # 25 + 13 × 21,2 = 300,6 mm > 297 mm
        uzun = SheetGeometry(
            margin_top=25, margin_left=0, label_width=40, label_height=21.2, rows=13, cols=5
        )
        with pytest.raises(LabelError) as hata:
            uzun.validate()
        assert hata.value.field == "rows"

    @pytest.mark.parametrize(
        ("alan", "degerler"),
        [
            ("rows", {"rows": 0}),
            ("cols", {"cols": 0}),
            ("label_width", {"label_width": 0.0}),
            ("label_height", {"label_height": -1.0}),
            ("gutter_x", {"gutter_x": -0.5}),
            ("page_margin_top", {"margin_top": math.nan}),
        ],
    )
    def test_anlamsiz_olcu_alan_adiyla_reddedilir(
        self, alan: str, degerler: dict[str, float]
    ) -> None:
        temel = {
            "margin_top": 10.7,
            "margin_left": 4.75,
            "label_width": 38.1,
            "label_height": 21.2,
            "rows": 13,
            "cols": 5,
            "gutter_x": 2.5,
        }
        with pytest.raises(LabelError) as hata:
            SheetGeometry(**{**temel, **degerler}).validate()  # type: ignore[arg-type]
        assert hata.value.field == alan

    def test_kalibrasyon_kaymasi_sinirlidir(self) -> None:
        CalibrationOffset(MAX_OFFSET_MM, -MAX_OFFSET_MM).validate()
        with pytest.raises(LabelError) as hata:
            CalibrationOffset(MAX_OFFSET_MM + 0.01, 0).validate()
        assert hata.value.field == "offset_x"
        with pytest.raises(LabelError):
            CalibrationOffset(0, math.inf).validate()

    def test_hata_django_dogrulama_hatasidir_ve_alan_sozlugu_tasir(self) -> None:
        """Uçta ek çeviri gerekmez: `kd_exception_handler` alan sözlüğünü 400'e çevirir."""
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError) as hata:
            plan_placements(1, capacity=65, start_cell=99)
        assert set(hata.value.message_dict) == {"start_cell"}


# ============================================================ Yazıcı noktası
def test_barkod_sol_kenari_modul_katina_cekilir() -> None:
    """X = 0,254 mm = 1/100 inç: 300 dpi'de 3, 600 dpi'de 6 nokta."""
    for ideal in (0.0, 4.75 + 5.08, 45.35 + 5.08, 13.37, 209.9):
        hizali = snap_to_module(ideal)
        assert abs(hizali - ideal) <= 0.127 + 1e-9
        adim = hizali / 0.254
        assert adim == pytest.approx(round(adim), abs=1e-9)
