"""Üye kartı (E2; tasarım §7.1-7.2, D8, D10) — düzen, PDF, kart basımı kuyruğu ve uçları.

- Kartta okul adı, "ÜYE KARTI", ad, üye türü, Code128 kart no, okunur numara ve
  konum kalıbı vardır; **sınıf YOKTUR** (KM-24).
- Sayfa bütçesi GERÇEK UZUNLUKTA veriyle sınanır (CLAUDE.md §3): en uzun okul adı
  ve en uzun ad kartın içinde kalır, satırlar kutusundan taşmaz, üst blok barkoda
  çarpmaz.
- A4'e 10 kart; başlangıç hücresi; barkodun sol kenarı modül katında.
- PDF "basıldı" demek değildir (D10): işaret yalnız onay ucuyla yazılır, geri alınır.

Bütün kişi verileri uydurmadır.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from pypdf import PdfReader
from rest_framework.test import APIClient

from apps.kutuphane import card_numbers
from apps.kutuphane.labels import card as kart
from apps.kutuphane.labels.geometry import LabelError, SheetGeometry
from apps.kutuphane.labels.metrics import text_width_mm
from apps.kutuphane.models import (
    LabelCalibration,
    LabelKind,
    LabelSheetTemplate,
    Membership,
    TerminationReason,
)
from apps.kutuphane.services import member_cards, memberships
from apps.kutuphane.tests.dolasim_ortak import ogrenci, personel, personele_odunc_ac, uye
from apps.okul.models import MemberKind, SchoolConfig
from shared import barcode128

pytestmark = pytest.mark.django_db

KARTLAR = "/api/v1/library/member-cards/"
EN_UZUN_OKUL = ("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3)[:255]
EN_UZUN_AD = "Mümtazhan Gülşehriye Şükriyenur Ümmügülsüm"
EN_UZUN_SOYAD = "Büyükçekmeceoğulları Karamehmetoğlu Şahinbeyoğlu"
#: Uydurma, sağlaması tutan kart no ve son hanesi bozulmuş eşi.
KART_NO = card_numbers.build_card_no("471826")
HATALI_KART_NO = KART_NO[:-1] + str((int(KART_NO[-1]) + 1) % 10)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def okul() -> SchoolConfig:
    config = SchoolConfig.load()
    config.school_name = "Örnek Anadolu Lisesi"
    config.kisa_ad = "Örnek AL"
    config.save()
    return config


@pytest.fixture(autouse=True)
def _okul_varsayilan(okul: SchoolConfig) -> Iterator[None]:
    yield


def _metin(icerik: bytes) -> str:
    return "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)


def _sayfa(icerik: bytes) -> int:
    return len(PdfReader(io.BytesIO(icerik)).pages)


def _kalem(**alanlar: str) -> kart.CardItem:
    alanlar.setdefault("card_no", KART_NO)
    alanlar.setdefault("full_name", "Deneme Öğrenci")
    alanlar.setdefault("member_type", "Öğrenci")
    return kart.CardItem(**alanlar)


def _geometri() -> SheetGeometry:
    return SheetGeometry.from_template(kart.ensure_card_template())


# ============================================================ metin sarma


def test_uzun_metin_en_cok_iki_satira_bolunur_ve_kutudan_tasmaz() -> None:
    satirlar, boy = kart.wrap_text(EN_UZUN_OKUL, 70.0, kart.SCHOOL_SIZES, bold=True, max_lines=2)

    assert len(satirlar) == 2
    assert boy == kart.SCHOOL_SIZES[-1]
    assert satirlar[-1].endswith("…")
    assert all(text_width_mm(s, boy, bold=True) <= 70.0 for s in satirlar)


def test_kisa_metin_tek_satir_ve_en_buyuk_boy() -> None:
    assert kart.wrap_text("Örnek Lisesi", 70.0, kart.SCHOOL_SIZES) == (
        ["Örnek Lisesi"],
        kart.SCHOOL_SIZES[0],
    )
    assert kart.wrap_text("", 70.0, kart.SCHOOL_SIZES) == ([], kart.SCHOOL_SIZES[0])


def test_uye_turu_yalniz_ilk_harfi_turkce_buyur() -> None:
    assert kart.member_type_text("öğrenci") == "Öğrenci"
    assert kart.member_type_text("diğer personel") == "Diğer personel"
    assert kart.member_type_text("ilk") == "İlk"


# ============================================================ düzen (sayfa bütçesi)


@pytest.mark.parametrize("kesim", [True, False])
def test_en_uzun_veride_kart_satirlari_kutuda_kalir_ve_barkoda_carpmaz(kesim: bool) -> None:
    geometri = _geometri()
    for hucre_no in (0, 1, geometri.capacity - 1):
        hucre = geometri.cell(hucre_no)
        duzen = kart.card_layout(
            _kalem(full_name=f"{EN_UZUN_AD} {EN_UZUN_SOYAD}", member_type="Diğer personel"),
            hucre,
            school=EN_UZUN_OKUL,
            cut_guides=kesim,
        )
        for kutu in duzen.texts:
            assert kutu.left >= 0 and kutu.left + kutu.width <= hucre.width + 1e-6
            assert kutu.top >= 0 and kutu.top + kutu.height <= hucre.height + 1e-6
            assert text_width_mm(kutu.text, kutu.size_pt, bold=kutu.bold) <= kutu.width
        barkod = next(g for g in duzen.graphics if g.role == "barcode")
        ust_son = max(
            k.top + k.height for k in duzen.texts if k.role in ("school", "title", "name", "type")
        )
        assert ust_son + kart.MIN_BLOCK_GAP <= barkod.top
        assert barkod.left >= 0 and barkod.left + barkod.width <= hucre.width
        assert ("cut" in {g.role for g in duzen.graphics}) is kesim


def test_uzun_ad_iki_satira_iner_kisaltmayla_bile_okunur() -> None:
    hucre = _geometri().cell(0)
    duzen = kart.card_layout(
        _kalem(full_name=f"{EN_UZUN_AD} {EN_UZUN_SOYAD}"), hucre, school="Örnek", cut_guides=True
    )
    adlar = [k for k in duzen.texts if k.role == "name"]

    assert len(adlar) == 2
    assert min(k.size_pt for k in adlar) >= kart.NAME_SIZES[-1]


def test_kartta_sinif_yok_okul_adi_baslik_tur_numara_ve_konum_kalibi_var() -> None:
    hucre = _geometri().cell(0)
    duzen = kart.card_layout(_kalem(), hucre, school="Örnek Anadolu Lisesi", cut_guides=True)
    roller = {k.role: k.text for k in duzen.texts}

    assert roller["school"] == "Örnek Anadolu Lisesi"
    assert roller["title"] == "ÜYE KARTI"
    assert roller["name"] == "Deneme Öğrenci"
    assert roller["type"] == "Öğrenci"
    assert roller["number"] == KART_NO
    assert "Md. 20" in " ".join(k.text for k in duzen.texts if k.role == "note")
    assert not any("/" in k.text and k.role != "note" for k in duzen.texts)


def test_diger_personel_kartinda_md20_atfi_yok() -> None:
    """Md. 20/1 kullanıcı kartını öğretmen ve öğrenciye öngörür; diğer personele atıf basılmaz."""
    personele_odunc_ac()
    ogretmen = uye(personel(member_kind=MemberKind.TEACHER))
    diger = uye(personel(member_kind=MemberKind.STAFF))
    ogrenci_uye = uye(ogrenci())

    notlar = {
        kalem.member_type: kalem.note
        for kalem in member_cards.card_items([ogretmen, diger, ogrenci_uye])
    }

    assert notlar["Öğrenci"] == notlar["Öğretmen"] == kart.POSITION_NOTE
    assert notlar["Diğer personel"] == kart.STAFF_POSITION_NOTE
    assert "Md. 20" not in kart.STAFF_POSITION_NOTE
    assert "Yönetmelik" not in kart.STAFF_POSITION_NOTE
    duzen = kart.card_layout(
        member_cards.card_items([diger])[0],
        _geometri().cell(0),
        school="Örnek Okul",
        cut_guides=False,
    )
    alt_not = " ".join(k.text for k in duzen.texts if k.role == "note")
    assert "Md. 20" not in alt_not
    assert alt_not == kart.STAFF_POSITION_NOTE


def test_barkod_99_modul_ve_sol_kenari_sayfada_modul_katinda() -> None:
    geometri = _geometri()
    for kayma_x in (0.0, 0.37, -1.13):
        from apps.kutuphane.labels.geometry import CalibrationOffset

        hucre = geometri.cell(3, CalibrationOffset(x=kayma_x, y=0.5))
        duzen = kart.card_layout(_kalem(), hucre, school="Örnek", cut_guides=False)
        barkod = next(g for g in duzen.graphics if g.role == "barcode")
        katsayi = (hucre.left + barkod.left) / kart.CARD_MODULE_MM

        assert abs(katsayi - round(katsayi)) < 1e-6
        assert barcode128.module_count(KART_NO) == 99
        assert abs(barkod.width - 99 * kart.CARD_MODULE_MM) < 1e-9


def test_kucuk_sablonda_kart_reddedilir() -> None:
    kucuk = SheetGeometry(
        margin_top=10, margin_left=10, label_width=40, label_height=20, rows=2, cols=2
    )
    with pytest.raises(LabelError):
        kart.build_card_context([_kalem()], template=kucuk, school_name="Örnek")


# ============================================================ kalem doğrulaması


def test_sagalamasi_tutmayan_yinelenen_ve_cok_kart_reddedilir() -> None:
    with pytest.raises(LabelError, match="geçersiz"):
        kart.validate_card_items([_kalem(card_no=HATALI_KART_NO)])
    with pytest.raises(LabelError, match="iki kez"):
        kart.validate_card_items([_kalem(), _kalem()])
    with pytest.raises(LabelError, match="Basılacak kart yok"):
        kart.validate_card_items([])
    fazla = [_kalem(card_no=f"{i}") for i in range(kart.MAX_CARDS_PER_DOCUMENT + 1)]
    with pytest.raises(LabelError, match="en çok"):
        kart.validate_card_items(fazla)


def test_hata_iletisi_kart_numarasini_basmaz() -> None:
    with pytest.raises(LabelError) as hata:
        kart.validate_card_items([_kalem(card_no=HATALI_KART_NO)])
    assert HATALI_KART_NO not in str(hata.value)


# ============================================================ şablon (tohum)


def test_kart_sablonu_bir_kez_yazilir_a4e_on_kart() -> None:
    ilk = kart.ensure_card_template()
    ikinci = kart.ensure_card_template()

    assert ilk.pk == ikinci.pk
    assert ilk.kind == LabelKind.CARD
    assert ilk.labels_per_sheet == 10
    assert (float(ilk.label_width), float(ilk.label_height)) == (85.0, 54.0)
    SheetGeometry.from_template(ilk).validate()
    assert LabelSheetTemplate.objects.filter(kind=LabelKind.CARD).count() == 1


def test_etiket_sablonlari_listesinde_kart_sablonu_gorunmez(client: APIClient) -> None:
    kart.ensure_card_template()

    yanit = client.get("/api/v1/library/label-templates/")

    assert yanit.status_code == 200
    assert all(s["kind"] != LabelKind.CARD for s in yanit.json()["results"])


def test_etiket_sablonu_kart_basiminda_reddedilir() -> None:
    from apps.kutuphane.labels.seed import default_template

    etiket = default_template(LabelKind.BARCODE)
    assert etiket is not None
    with pytest.raises(LabelError, match="kart şablonuna"):
        kart.build_card_context([_kalem()], template=etiket, school_name="Örnek")


def test_baska_sablonun_kalibrasyonu_reddedilir() -> None:
    from apps.kutuphane.labels.seed import default_template

    etiket = default_template(LabelKind.BARCODE)
    assert etiket is not None
    yabanci = LabelCalibration.objects.create(template=etiket, printer_name="Ofis yazıcısı")
    with pytest.raises(LabelError, match="kart şablonuna ait değil"):
        kart.build_card_context(
            [_kalem()], template=kart.ensure_card_template(), calibration=yabanci
        )


# ============================================================ PDF


def test_on_kart_tek_tabaka_on_bir_kart_iki_tabaka() -> None:
    sablon = kart.ensure_card_template()
    on = [_kalem(card_no=_gecerli(i)) for i in range(11)]

    assert kart.render_member_cards(on[:10], template=sablon).sheet_count == 1
    sonuc = kart.render_member_cards(on, template=sablon)
    assert sonuc.sheet_count == 2
    assert _sayfa(sonuc.pdf) == 2


def test_baslangic_hucresi_ilk_tabakayi_kaydirir() -> None:
    sonuc = kart.render_member_cards(
        [_kalem(card_no=_gecerli(1)), _kalem(card_no=_gecerli(2))],
        template=kart.ensure_card_template(),
        start_cell=10,
    )
    assert [(p.sheet, p.cell_index) for p in sonuc.placements] == [(0, 9), (1, 0)]
    assert _sayfa(sonuc.pdf) == 2


def test_pdf_okul_adini_basligi_numarayi_basar_sinifi_basmaz() -> None:
    uyelik = uye(ogrenci(first_name="Deneme", last_name="Kartlı", class_level=9, class_section="A"))
    pdf = kart.render_member_cards(
        member_cards.card_items([uyelik]), template=kart.ensure_card_template()
    ).pdf
    metin = _metin(pdf)

    assert "Örnek Anadolu Lisesi" in metin
    assert "ÜYE KARTI" in metin
    assert "Deneme Kartlı" in metin
    assert str(uyelik.card_no) in metin
    assert "Öğrenci" in metin
    assert "9/A" not in metin


def test_en_uzun_veriyle_tam_tabaka_tek_sayfa(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.save()
    kalemler = [
        _kalem(card_no=_gecerli(i), full_name=f"{EN_UZUN_AD} {EN_UZUN_SOYAD}") for i in range(10)
    ]

    sonuc = kart.render_member_cards(kalemler, template=kart.ensure_card_template())

    assert _sayfa(sonuc.pdf) == 1


def _gecerli(sira: int) -> str:
    return card_numbers.build_card_no(f"{sira:06d}")


# ============================================================ kuyruk ve işaret (D10)


def test_yeni_uyelik_kuyrukta_basilinca_cikar_geri_alininca_doner() -> None:
    uyelik = uye()
    assert member_cards.card_queue() == [uyelik]

    assert member_cards.confirm_printed([uyelik.pk]) == 1
    assert member_cards.card_queue() == []
    assert member_cards.card_queue(printed=True) == [uyelik]

    assert member_cards.revert_printed([uyelik.pk]) == 1
    assert member_cards.card_queue() == [uyelik]


def test_zaten_basilmis_kart_yeniden_isaretlenmez_ilk_tarih_korunur() -> None:
    uyelik = uye()
    member_cards.confirm_printed([uyelik.pk])
    uyelik.refresh_from_db()
    ilk = uyelik.card_printed_at

    assert member_cards.confirm_printed([uyelik.pk]) == 0
    uyelik.refresh_from_db()
    assert uyelik.card_printed_at == ilk


def test_karti_yenilenen_uye_kuyruga_doner() -> None:
    uyelik = uye()
    member_cards.confirm_printed([uyelik.pk])

    memberships.renew_card(Membership.objects.get(pk=uyelik.pk))

    assert [m.pk for m in member_cards.card_queue()] == [uyelik.pk]


def test_sonlanmis_uyelige_kart_basilmaz_ve_isaretlenmez() -> None:
    uyelik = uye()
    memberships.terminate_membership(uyelik, reason=TerminationReason.MEMBER_REQUEST)

    assert member_cards.card_queue() == []
    with pytest.raises(Exception, match="aktif değil"):
        member_cards.memberships_for_print([uyelik.pk])
    with pytest.raises(Exception, match="aktif değil"):
        member_cards.confirm_printed([uyelik.pk])


def test_basim_sirasi_sinif_sube_okul_no_sonra_personel() -> None:
    ogretmen = uye(personel(first_name="Ayla", last_name="Deneme", member_kind=MemberKind.TEACHER))
    b = uye(ogrenci(class_level=10, class_section="A", student_number="5"))
    a = uye(ogrenci(class_level=9, class_section="Ç", student_number="9"))
    c = uye(ogrenci(class_level=9, class_section="C", student_number="12"))

    sirali = member_cards.memberships_for_print([ogretmen.pk, b.pk, a.pk, c.pk])

    assert [m.pk for m in sirali] == [c.pk, a.pk, b.pk, ogretmen.pk]


# ============================================================ uçlar


def test_kuyruk_ucu_sayfali_ve_suzgecli(client: APIClient) -> None:
    dokuz = uye(ogrenci(class_level=9, class_section="A"))
    uye(ogrenci(class_level=10, class_section="B"))

    yanit = client.get(KARTLAR, {"class_level": "9", "class_section": "a"})

    assert yanit.status_code == 200
    govde = yanit.json()
    assert govde["count"] == 1
    satir = govde["results"][0]
    assert satir["id"] == dokuz.pk
    assert satir["card_no"] == str(dokuz.card_no)
    assert satir["class_label"] == "9/A"
    assert client.get(KARTLAR, {"state": "hepsi"}).status_code == 400


def test_kuyruk_satirinin_alan_listesi_sabittir() -> None:
    from apps.kutuphane.serializers_evrak import MemberCardRowSerializer

    assert MemberCardRowSerializer.Meta.fields == [
        "id",
        "full_name",
        "member_type",
        "member_type_display",
        "class_label",
        "student_number",
        "card_no",
        "card_printed_at",
        "started_at",
    ]


def test_sablon_ucu_kart_sablonunu_dondurur(client: APIClient) -> None:
    yanit = client.get(f"{KARTLAR}template/")

    assert yanit.status_code == 200
    assert yanit.json()["kind"] == LabelKind.CARD
    assert yanit.json()["labels_per_sheet"] == 10


def test_pdf_ucu_isarete_dokunmaz(client: APIClient) -> None:
    uyelik = uye()

    yanit = client.post(
        f"{KARTLAR}pdf/", {"membership_ids": [uyelik.pk], "start_cell": 3}, format="json"
    )

    assert yanit.status_code == 200
    assert yanit["Content-Type"] == "application/pdf"
    assert yanit["Cache-Control"] == "no-store"
    assert yanit["X-KD-Tabaka-Sayisi"] == "1"
    assert (
        "Üye-Kartı_" in yanit["Content-Disposition"] or "filename*" in yanit["Content-Disposition"]
    )
    icerik = b"".join(yanit.streaming_content)  # type: ignore[attr-defined]
    assert icerik.startswith(b"%PDF")
    uyelik.refresh_from_db()
    assert uyelik.card_printed_at is None


def test_pdf_ucu_kalibrasyonla_ve_kesim_cizgisiz_basar(client: APIClient) -> None:
    uyelik = uye()
    sablon = kart.ensure_card_template()
    kalibrasyon = LabelCalibration.objects.create(
        template=sablon, printer_name="Müdürlük yazıcısı", offset_x="1.20", offset_y="-0.50"
    )

    yanit = client.post(
        f"{KARTLAR}pdf/",
        {
            "membership_ids": [uyelik.pk],
            "template": sablon.pk,
            "calibration": kalibrasyon.pk,
            "cut_guides": False,
        },
        format="json",
    )

    assert yanit.status_code == 200


def test_pdf_ucu_sonlanmis_uyelikte_400(client: APIClient) -> None:
    uyelik = uye()
    memberships.terminate_membership(uyelik, reason=TerminationReason.RECORD_ERROR)

    yanit = client.post(f"{KARTLAR}pdf/", {"membership_ids": [uyelik.pk]}, format="json")

    assert yanit.status_code == 400
    assert "aktif değil" in yanit.json()["message"]


def test_isaretle_ve_geri_al_uclari(client: APIClient) -> None:
    a, b = uye(), uye()

    yanit = client.post(f"{KARTLAR}confirm-print/", {"membership_ids": [a.pk, b.pk]}, format="json")
    assert yanit.status_code == 200 and yanit.json() == {"marked": 2}

    yanit = client.post(f"{KARTLAR}revert-print/", {"membership_ids": [a.pk]}, format="json")
    assert yanit.status_code == 200 and yanit.json() == {"reverted": 1}

    bekleyen = client.get(KARTLAR).json()["results"]
    basilan = client.get(KARTLAR, {"state": "printed"}).json()["results"]
    assert [s["id"] for s in bekleyen] == [a.pk]
    assert [s["id"] for s in basilan] == [b.pk]


def test_bos_secim_400(client: APIClient) -> None:
    yanit = client.post(f"{KARTLAR}confirm-print/", {"membership_ids": []}, format="json")
    assert yanit.status_code == 400


def test_kart_sablonunun_kalibrasyon_sayfasi_etiket_ucundan_basilir(client: APIClient) -> None:
    sablon = kart.ensure_card_template()
    kalibrasyon = client.post(
        "/api/v1/library/label-calibrations/",
        {
            "template": sablon.pk,
            "printer_name": "Müdürlük yazıcısı",
            "offset_x": "0.50",
            "offset_y": "0",
        },
        format="json",
    )
    assert kalibrasyon.status_code == 201

    yanit = client.post(
        "/api/v1/library/labels/calibration/",
        {"template": sablon.pk, "calibration": kalibrasyon.json()["id"]},
        format="json",
    )

    assert yanit.status_code == 200
    assert _sayfa(b"".join(yanit.streaming_content)) == 1  # type: ignore[attr-defined]
