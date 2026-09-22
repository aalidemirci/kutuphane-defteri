"""apps.okul.excel_personel — SADELEŞMİŞ personel parser testleri.

OYS şablonundan fark: e-posta ve Rol/Kapsam çiftleri YOK — personel hesabı yoktur.
F1-C (tasarım §6.1, V2-01): unvan ve branş SAKLANMAZ. Branş sütunu hiç
eşlenmez; "Görevi/Unvan" (şablonda "Üye Türü") yalnız üye türüne (öğretmen /
diğer personel) çevrilir, metni satır nesnesine girmez.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from apps.okul import excel_personel
from apps.okul.excel_ogrenci import ParserError
from apps.okul.models import MemberKind

STANDARD_HEADER = ["Ad Soyad", "Unvan", "Branş"]


def make_xlsx(
    rows: list[list[object]],
    header: list[object] | None = None,
    preamble: list[list[object]] | None = None,
) -> bytes:
    """Bellekte bir .xlsx üretir (header + satırlar)."""
    wb = Workbook()
    ws = wb.active
    for pre in preamble or []:
        ws.append(pre)
    ws.append(header if header is not None else STANDARD_HEADER)
    for r in rows:
        ws.append(r)
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_tur_sabitleri_model_degerleriyle_ayni() -> None:
    """Modül Django'suz kalsın diye düz metin tutar; model değerleriyle eşit olmalı."""
    assert (excel_personel.KIND_TEACHER, excel_personel.KIND_STAFF) == (
        MemberKind.TEACHER.value,
        MemberKind.STAFF.value,
    )


def test_standart_basliklar_eslenir_brans_eslenmez() -> None:
    grid = excel_personel.read_sheet(make_xlsx([]))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.is_usable
    assert mapping.fields == {"full_name": 0, "role": 1}


def test_fuzzy_baslik_varyasyonlari() -> None:
    header: list[object] = ["Adı Soyadı", "Görevi", "Alan", "Branşı"]
    grid = excel_personel.read_sheet(make_xlsx([], header=header))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.is_usable
    assert mapping.fields == {"full_name": 0, "role": 1}


def test_sablon_ayri_ad_soyad_ve_uye_turu_okunur() -> None:
    header: list[object] = ["Adı", "Soyadı", "Üye Türü"]
    data = make_xlsx([["ALİ", "ÖRNEK", "Diğer personel"]], header=header)
    mapping, parsed = excel_personel.parse_workbook(data)
    assert mapping.is_usable
    assert (parsed[0].first_name, parsed[0].last_name) == ("ALİ", "ÖRNEK")
    assert parsed[0].member_kind == MemberKind.STAFF
    assert parsed[0].member_kind_unrecognized is False


def test_satirda_gorev_ve_brans_metni_tutulmaz() -> None:
    header: list[object] = ["Adı", "Soyadı", "Görevi", "Branşı"]
    data = make_xlsx([["ALİ", "ÖRNEK", "Müdür", "Coğrafya"]], header=header)
    _mapping, parsed = excel_personel.parse_workbook(data)
    assert set(vars(parsed[0])) == {
        "row_number",
        "raw_full_name",
        "first_name",
        "last_name",
        "member_kind",
        "member_kind_unrecognized",
    }
    assert "Müdür" not in repr(parsed[0]) and "Coğrafya" not in repr(parsed[0])


def test_yalniz_ad_soyad_da_yeterli_tur_bilgisi_yok() -> None:
    """Görev sütunsuz düz isim listesi kabul edilir; tür bilgisi yok, uyarı da yok."""
    _mapping, parsed = excel_personel.parse_workbook(
        make_xlsx([["ALİ ÖRNEK"]], header=["Ad Soyad"])
    )
    assert parsed[0].member_kind is None
    assert parsed[0].member_kind_unrecognized is False


def test_ad_soyad_yoksa_parser_error() -> None:
    data = make_xlsx([["Müdür", "Matematik"]], header=["Unvan", "Branş"])
    with pytest.raises(ParserError, match="full_name"):
        excel_personel.parse_workbook(data)


def test_satir_ayristirma() -> None:
    rows: list[list[object]] = [
        ["ALİ ÖRNEK", "Müdür", "Coğrafya"],
        ["AYŞE ÖĞRETMEN", "", "Matematik"],
    ]
    _mapping, parsed = excel_personel.parse_workbook(make_xlsx(rows))
    assert len(parsed) == 2
    assert (parsed[0].first_name, parsed[0].last_name) == ("ALİ", "ÖRNEK")
    assert parsed[0].member_kind == MemberKind.TEACHER
    # Görev sütunu VAR ama hücre boş: tanınmadı → önizlemede denetim uyarısı.
    assert (parsed[1].member_kind, parsed[1].member_kind_unrecognized) == (None, True)


def test_bos_satir_atlanir() -> None:
    rows: list[list[object]] = [
        ["ALİ ÖRNEK", "Müdür", "Coğrafya"],
        [None, None, None],
    ]
    _mapping, parsed = excel_personel.parse_workbook(make_xlsx(rows))
    assert len(parsed) == 1


def test_preamble_atlanir() -> None:
    preamble: list[list[object]] = [["PERSONEL LİSTESİ"], []]
    grid = excel_personel.read_sheet(make_xlsx([], preamble=preamble))
    mapping = excel_personel.detect_columns(grid)
    assert mapping.header_row == 2
    assert mapping.is_usable


@pytest.mark.parametrize(
    ("gorev", "beklenen"),
    [
        ("Öğretmen", "TEACHER"),
        ("Sözleşmeli Öğretmen(657 S.K. 4/B)", "TEACHER"),
        ("Ücretli Öğretmen", "TEACHER"),
        ("Müdür", "TEACHER"),
        ("Müdür Yardımcısı", "TEACHER"),
        ("Müdür Başyardımcısı", "TEACHER"),
        ("Rehber Öğretmen", "TEACHER"),
        ("Psikolojik Danışman", "TEACHER"),
        ("Usta Öğretici", "TEACHER"),
        ("MEMUR", "STAFF"),
        ("Ambar Memuru", "STAFF"),
        ("Hizmetli", "STAFF"),
        ("Yardımcı Hizmetli", "STAFF"),
        ("Teknisyen", "STAFF"),
        ("Aşçı", "STAFF"),
        ("Bekçi", "STAFF"),
        ("Şef", "STAFF"),
        ("Sekreter", "STAFF"),
        ("Şoför", "STAFF"),
        ("Sürekli İşçi", "STAFF"),
        ("Veri Hazırlama ve Kontrol İşletmeni", "STAFF"),
        ("Diğer personel", "STAFF"),
        ("", None),
        (None, None),
        ("Uzman Kaptan", None),
    ],
)
def test_gorev_siniflamasi(gorev: object, beklenen: str | None) -> None:
    assert excel_personel.classify_member_kind(gorev) == beklenen
