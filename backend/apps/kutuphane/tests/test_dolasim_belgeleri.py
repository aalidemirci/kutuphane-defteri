"""Dolaşım belgeleri (E4, E13, E19; tasarım §3 KVKK, §9-13, §10).

- İade hatırlatma pusulası TEK KİŞİLİKTİR: A4'te üç pusula, kişinin bütün
  gecikmiş ödünçleri (kişi bazında), soldaki ad bölümü katlanınca açık kalır,
  içerik katlama çizgisinin iki yanındadır. En uzun veride hiçbir bölüm taşmaz.
  "Md. 18 gereği", ceza, harç ve uzatma dili YOKTUR.
- Gecikmiş ödünç listesi: HER sayfada "Kişisel veri içerir — asılmaz,
  çoğaltılmaz." dipnotu; okul no basılmaz; kişi sırası.
- Kütüphane aydınlatma metni: md. 10/1 unsurları, masadaki öğrenci görevliler,
  saklamanın bugünkü gerçeği (TB16), md. 11 bentleri ve md. 5/2-ç, 13/1-2
  alıntıları docs/mevzuat'taki Kanun metniyle BİREBİR; en çok iki sayfa.
- Masa kartı: tek sayfa; iletiler masa ekranının iletileriyle aynı.
- Profil yasağı: belge modülleri konu/sınıflama/bölüm alanına dokunmaz.

Sayfa bütçesi testleri GERÇEK UZUNLUKTA veriyle koşar (CLAUDE.md §3). Bütün
kişi verileri uydurmadır.
"""

from __future__ import annotations

import inspect
import io
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from pypdf import PdfReader

from apps.kutuphane import dolasim_belgeleri as belgeler
from apps.kutuphane import selectors_dolasim, serializers_evrak
from apps.kutuphane.models import Loan, Membership, TerminationReason
from apps.kutuphane.services import circulation
from apps.kutuphane.tests.dolasim_ortak import (
    gecikmeli_yap,
    odunc_nushasi,
    odunc_ver,
    ogrenci,
    personel,
    politika,
    uye,
)
from apps.okul.models import SchoolConfig
from apps.okul.services import persons

pytestmark = pytest.mark.django_db

EN_UZUN_OKUL = ("Örnek Mesleki ve Teknik Anadolu Lisesi Uzun Adlı Kampüs Yerleşkesi " * 3)[:255]
EN_UZUN_AD = "Mümtazhan Gülşehriye Şükriyenur Ümmügülsüm"
EN_UZUN_SOYAD = "Büyükçekmeceoğulları Karamehmetoğlu Şahinbeyoğlu"
EN_UZUN_ESER = (
    "Uzun Adlı Örnek Kaynak: Çağdaş Türk Şiirinde Doğa, Şehir ve İnsan Üzerine "
    "Karşılaştırmalı Bir İnceleme — Birinci Cilt, Genişletilmiş Üçüncü Baskı"
)

#: pypdf "T" harfinden sonraki çekirdek aralığını boşluk sanar ("T est").
_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")


def _metin(icerik: bytes) -> str:
    ham = "\n".join(s.extract_text() or "" for s in PdfReader(io.BytesIO(icerik)).pages)
    return _T_ARALIGI.sub("T", ham)


def _sayfa_metinleri(icerik: bytes) -> list[str]:
    return [_tek(s.extract_text() or "") for s in PdfReader(io.BytesIO(icerik)).pages]


def _tek(metin: str) -> str:
    return " ".join(metin.split())


@pytest.fixture(autouse=True)
def okul() -> SchoolConfig:
    config = SchoolConfig.load()
    config.school_name = "Örnek Anadolu Lisesi"
    config.district = "Örnek İlçe"
    config.province = "Örnek İl"
    config.principal_name = "Örnek Müdür"
    config.save()
    return config


def _odunc(uyelik: Membership, *, title: str = "Deneme Eseri") -> Loan:
    return odunc_ver(uyelik, odunc_nushasi(title=title))


def _gecikmis(uyelik: Membership, *, gun: int = 5, title: str = "Deneme Eseri") -> Loan:
    """Tek ödünç verip geciktirir. Aynı kişiye ikinci ödünç için önce `_odunc`
    ile hepsini verin, sonra geciktirin (gecikme engeli yeni ödüncü keser)."""
    return gecikmeli_yap(_odunc(uyelik, title=title), gun=gun)


# ============================================================ gecikmiş satırlar ve gruplar


def test_satirlar_kisi_sirasiyla_kisi_icinde_iade_tarihine_gore() -> None:
    ogretmen = uye(personel(first_name="Ayla", last_name="Deneme"))
    onuncu = uye(ogrenci(class_level=10, class_section="A", student_number="3"))
    dokuzuncu = uye(ogrenci(class_level=9, class_section="B", student_number="8"))
    a = _gecikmis(onuncu, gun=2)
    b, c = _odunc(dokuzuncu), _odunc(dokuzuncu)
    b, c = gecikmeli_yap(b, gun=1), gecikmeli_yap(c, gun=9)
    d = _gecikmis(ogretmen, gun=20)

    satirlar = belgeler.overdue_rows()

    assert [lo.pk for lo in satirlar] == [c.pk, b.pk, a.pk, d.pk]
    gruplar = belgeler.overdue_groups()
    assert [len(g.loans) for g in gruplar] == [2, 1, 1]
    assert [g.label for g in gruplar] == ["9/B", "10/A", "Öğretmen"]


def test_sayilar_kisi_bazinda_eski_uyelikteki_gecikme_de_gelir() -> None:
    kisi = ogrenci()
    eski = uye(kisi)
    eski_odunc = _odunc(eski)
    persons.leave_student(kisi)
    kisi.refresh_from_db()
    persons.reactivate_student(kisi)  # çağıran kaydeder
    kisi.save(update_fields=["status", "left_at", "updated_at"])
    yeni = uye(kisi)
    yeni_odunc = _odunc(yeni)
    gecikmeli_yap(eski_odunc, gun=30)
    gecikmeli_yap(yeni_odunc, gun=2)

    gruplar = belgeler.overdue_groups(membership_ids=[yeni.pk])

    assert len(gruplar) == 1
    assert {lo.pk for lo in gruplar[0].loans} == {eski_odunc.pk, yeni_odunc.pk}


def test_sinif_suzgeci_ve_uyelik_suzgeci() -> None:
    a = uye(ogrenci(class_level=9, class_section="Ç"))
    b = uye(ogrenci(class_level=9, class_section="C"))
    ogretmen = uye(personel())
    for u in (a, b, ogretmen):
        _gecikmis(u)

    assert {g.membership.pk for g in belgeler.overdue_groups(class_level=9)} == {a.pk, b.pk}
    assert [g.membership.pk for g in belgeler.overdue_groups(class_level=9, class_section="ç")] == [
        a.pk
    ]
    assert [g.membership.pk for g in belgeler.overdue_groups(membership_ids=[ogretmen.pk])] == [
        ogretmen.pk
    ]


def test_gecikmemis_ve_iade_edilmis_odunc_listeye_girmez() -> None:
    uyelik = uye()
    odunc_ver(uyelik)
    iade = _gecikmis(uyelik)
    circulation.return_copy(copy=iade.copy)

    assert belgeler.overdue_rows() == []


def test_kapsam_metni_ve_dosya_adi_parcasi() -> None:
    assert belgeler.scope_text(None, "") == "Bütün okul"
    assert belgeler.scope_text(9, "") == "9. sınıflar"
    assert belgeler.scope_text(9, "a") == "9/A şubesi"
    assert belgeler.scope_slug(9, "a") == ("9-A",)
    assert belgeler.scope_slug(None, "") == ()
    ad = belgeler.belge_dosya_adi(belgeler.LISTE_ADI, kapsam=("9-A",))
    assert ad.startswith("Gecikmiş-Ödünç-Listesi_9-A_") and ad.endswith(".pdf")


# ============================================================ E4 pusula


def _en_uzun_grup(kaynak: int = 6) -> belgeler.OverdueGroup:
    politika(max_loans_teacher=5)
    kisi = personel(first_name=EN_UZUN_AD, last_name=EN_UZUN_SOYAD)
    uyelik = uye(kisi)
    verilen = [_odunc(uyelik, title=f"{EN_UZUN_ESER} {sira}") for sira in range(min(kaynak, 5))]
    for sira, loan in enumerate(verilen):
        gecikmeli_yap(loan, gun=100 + sira)
    if kaynak > 5:  # sınırı aşan eski üyelik ödüncü (kişi bazında sayılır)
        for sira in range(5, kaynak):
            fazla = Loan.objects.create(
                copy=odunc_nushasi(title=f"{EN_UZUN_ESER} {sira}"),
                membership=uyelik,
                due_date=timezone.localdate() - timedelta(days=150 + sira),
            )
            assert fazla.pk
    return belgeler.overdue_groups()[0]


def test_en_uzun_veride_pusulanin_hicbir_bolumu_tasmaz(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.save()
    grup = _en_uzun_grup(kaynak=6)

    baglam = belgeler.slip_context([grup, grup, grup, grup])

    assert baglam["overflow_count"] == 0
    assert len(baglam["pages"]) == 2
    metinler = [k["text"] for k in baglam["pages"][0]["slips"][0]["texts"]]
    assert "ve 1 kaynak daha — kütüphane yöneticisine sorun." in metinler


def test_pusula_uc_bolumde_ad_disarida_icerik_katlama_cizgisinin_iki_yaninda() -> None:
    uyelik = uye(
        ogrenci(first_name="Deneme", last_name="Pusulalı", class_level=9, class_section="A")
    )
    _gecikmis(uyelik, gun=7, title="Deneme Kaynağı")

    kutular = belgeler.slip_context(belgeler.overdue_groups())["pages"][0]["slips"][0]["texts"]
    serit = [k["text"] for k in kutular if float(k["left"]) < belgeler.STRIP_WIDTH]
    ic = [k["text"] for k in kutular if belgeler.STRIP_WIDTH <= float(k["left"]) < belgeler.FOLD_X]
    sag = [k["text"] for k in kutular if float(k["left"]) >= belgeler.FOLD_X]

    assert serit[:3] == ["KİŞİYE ÖZELDİR", "Deneme Pusulalı", "9/A"]
    assert "Deneme Kaynağı" not in " ".join(serit)
    # Katlanınca dışta kalan şeridin TAM metni: kaynağı (kütüphaneyi) söylemez (§9-13).
    assert " ".join(serit) == " ".join(
        (
            belgeler.SLIP_OUTSIDE_TITLE,
            "Deneme Pusulalı",
            "9/A",
            belgeler.SLIP_FOLD_HINT,
            belgeler.SLIP_DELIVERY_STUDENT,
        )
    )
    assert "kütüphane" not in " ".join(serit).lower()
    assert "İADE HATIRLATMASI" in ic
    assert "Deneme Kaynağı" in sag
    assert any("7 gün gecikti" in m for m in sag)
    # Sağ bölüm sola katlanınca şeridin sağındaki alanı TAM örter.
    assert belgeler.FOLD_X - belgeler.STRIP_WIDTH == belgeler.SLIP_WIDTH - belgeler.FOLD_X
    for k in kutular:
        assert float(k["left"]) + float(k["width"]) <= belgeler.SLIP_WIDTH - 5.0 + 1e-6
        assert float(k["top"]) >= 5.0


def test_personelin_pusulasi_rehber_ogretmene_yonlendirmez() -> None:
    _gecikmis(uye(personel()))
    kutular = belgeler.slip_context(belgeler.overdue_groups())["pages"][0]["slips"][0]["texts"]
    metin = " ".join(k["text"] for k in kutular)
    serit = " ".join(k["text"] for k in kutular if float(k["left"]) < belgeler.STRIP_WIDTH)

    assert belgeler.SLIP_DELIVERY_STAFF in serit
    assert "sınıfta" not in serit
    assert "kütüphane" not in serit.lower()
    assert "rehber" not in metin


def test_pusula_pdf_uc_kisi_tek_sayfa_dort_kisi_iki_sayfa_ve_yasakli_dil_yok() -> None:
    for sira in range(4):
        _gecikmis(uye(ogrenci(first_name="Deneme", last_name=f"Kişi{sira}")))
    gruplar = belgeler.overdue_groups()

    assert len(PdfReader(io.BytesIO(belgeler.slips_pdf(gruplar[:3]))).pages) == 1
    pdf = belgeler.slips_pdf(gruplar)
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2
    metin = _tek(_metin(pdf))
    assert "Deneme Kişi0" in metin and "Deneme Kişi3" in metin
    assert "kesme çizgisi" in metin
    for yasak in ("gereği", "ceza", "harç", "uzat"):
        assert yasak not in metin.lower()
    assert "Md. 18" in metin


def test_silinmis_kisinin_adi_basilmaz() -> None:
    kisi = ogrenci(first_name="Deneme", last_name="Silinecek")
    _gecikmis(uye(kisi))
    kisi.deleted_at = timezone.now()
    kisi.save(update_fields=["deleted_at"])

    grup = belgeler.overdue_groups()[0]

    assert grup.full_name == belgeler.SILINMIS_KISI


# ============================================================ E4 toplu liste


def test_liste_her_sayfada_dipnot_ve_okul_no_yok(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.save()
    for sira in range(45):
        kisi = ogrenci(
            first_name=EN_UZUN_AD,
            last_name=f"{EN_UZUN_SOYAD} {sira}",
            student_number=str(880000 + sira),
        )
        _gecikmis(uye(kisi), gun=3 + sira, title=EN_UZUN_ESER)

    satirlar = belgeler.overdue_rows()
    pdf = belgeler.overdue_list_pdf(satirlar)
    sayfalar = _sayfa_metinleri(pdf)

    assert len(sayfalar) >= 2
    assert len(sayfalar) <= 15
    for sayfa in sayfalar:
        assert belgeler.LISTE_DIPNOTU in sayfa
    butun = " ".join(sayfalar)
    assert "880000" not in butun
    assert "GECİKMİŞ ÖDÜNÇ LİSTESİ" in butun
    assert "45 kişide 45 gecikmiş ödünç" in butun


def test_bos_liste_basilir_ve_bunu_soyler() -> None:
    pdf = belgeler.overdue_list_pdf([], class_level=9, class_section="A")
    metin = _tek(_metin(pdf))

    assert "Bu kapsamda gecikmiş ödünç yok." in metin
    assert "9/A şubesi" in metin


# ============================================================ E13 aydınlatma metni


def _kvkk_metni() -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / "6698-kvkk.md"
        if yol.is_file():
            return _tek(yol.read_text(encoding="utf-8"))
    pytest.fail("KVKK metni bulunamadı.")


def test_kanun_alintilari_depodaki_metinle_birebir() -> None:
    kanun = _kvkk_metni()
    for bent, metin in belgeler.KVKK_11_HAKLAR:
        assert f"{bent}) {metin}" in kanun, bent
    assert belgeler.KVKK_5_2_C in kanun
    assert f"(1) {belgeler.KVKK_13_1}" in kanun
    assert f"(2) {belgeler.KVKK_13_2}" in kanun
    assert [b for b, _ in belgeler.KVKK_11_HAKLAR] == ["a", "b", "c", "ç", "d", "e", "f", "g", "ğ"]


def test_yedek_sureleri_programin_gercek_degerleri() -> None:
    from desktop import backup

    assert belgeler.YEDEK_GUN == backup.DEFAULT_KEEP_DAYS
    assert belgeler.YEDEK_GUNCELLEME == backup.DEFAULT_KEEP_PRE_MIGRATE


def test_aydinlatma_metni_asgari_unsurlari_tasir() -> None:
    pdf = belgeler.privacy_notice_pdf(
        basvuru_adresi="Örnek Mahallesi Deneme Sokak No: 1 Örnek İlçe / Örnek İl",
        iletisim="ornek@example.org",
    )
    metin = _tek(_metin(pdf))

    # md. 10/1-a: veri sorumlusu
    assert "Millî Eğitim Bakanlığı — Örnek Anadolu Lisesi Müdürlüğü" in metin
    # b: amaçlar · c: kimlere aktarılır · ç: yöntem ve hukuki sebep · d: haklar
    for baslik in (
        "VERİ SORUMLUSU",
        "İŞLEME AMAÇLARI",
        "KİMLER GÖRÜR, KİMLERE AKTARILIR",
        "HUKUKİ SEBEP VE TOPLAMA YÖNTEMİ",
        "HAKLARINIZ",
        "BAŞVURU",
        "SAKLAMA",
    ):
        assert baslik in metin
    assert "md. 5/2-ç" in metin
    assert "kısmen otomatik yolla" in metin
    # Masadaki öğrenci görevliler DAHİL kimlerin gördüğü (§3)
    assert "görevli olarak çalışan öğrenci ve personel" in metin
    # Konum dili (CLAUDE.md §2-13): yerine GEÇMEZ
    assert "o sistemin yerine geçmez" in metin
    # Saklamanın bugünkü gerçeği (TB16): ayrılan kişinin kaydı üye OLMASA da kalır;
    # geri yüklemede kenara alınan önceki veritabanı da anılır.
    assert "saklama taraması yoktur" in metin
    assert "okuldan ayrılan kişilerin kayıtları (üye olsunlar ya da olmasınlar)" in metin
    assert "süre sınırı olmadan saklanır" in metin
    assert "Geri yüklemede önceki veritabanı" in metin
    assert "14 gün" in metin
    # Şifreleme cümlesi TB1'i söyler: her şey şifreli DEĞİLDİR (Tebliğ md. 5).
    assert "şifreli olarak durur" not in metin
    assert "kart numarası ve gerekçe açıklamaları şifrelidir" in metin
    assert "şifresiz tutulur" in metin
    # Görevlinin masada görebildiği (kartı okutulan üyede olan kitap) söylenir.
    assert "okuttuğu kitabın o üyede olup olmadığını görür" in metin
    # Başvuru bilgileri basılır
    assert "ornek@example.org" in metin
    # Toplanmayan veriler
    assert "T.C. kimlik numarası" in metin


def test_aydinlatma_metni_en_uzun_veride_en_cok_iki_sayfa(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.principal_name = f"{EN_UZUN_AD} {EN_UZUN_SOYAD}"
    okul.save()

    pdf = belgeler.privacy_notice_pdf(basvuru_adresi="Örnek " * 49, iletisim="x" * 120)

    assert len(PdfReader(io.BytesIO(pdf)).pages) <= 2


def test_bos_basvuru_alanlari_elle_doldurulacak_satir_birakir() -> None:
    metin = _tek(_metin(belgeler.privacy_notice_pdf()))
    assert "Başvuru adresi ………" in metin


# ============================================================ E19 masa kartı


def test_masa_karti_tek_sayfa_ve_iletileri_masayla_ayni() -> None:
    pdf = belgeler.desk_card_pdf()
    metin = _tek(_metin(pdf))

    assert len(PdfReader(io.BytesIO(pdf)).pages) == 1
    assert circulation.OVERDUE_STAFF_MESSAGE in metin
    assert selectors_dolasim.REVOKED_CARD_MESSAGE in metin
    assert "Kilitle" in metin
    assert "md. 12/1" in metin
    assert "kütüphane etiketini okutun" in metin


def test_masa_karti_en_uzun_okul_adiyla_da_tek_sayfa(okul: SchoolConfig) -> None:
    okul.school_name = EN_UZUN_OKUL
    okul.save()
    assert len(PdfReader(io.BytesIO(belgeler.desk_card_pdf())).pages) == 1


# ============================================================ profil yasağı ve kişisel veri


def test_profil_yasagi_belge_modulleri_konu_ve_siniflamaya_dokunmaz() -> None:
    yasak = ("subject", "classification", "dewey", "work__section", "copy__section", "okuduğu")
    for modul in (belgeler, serializers_evrak):
        kod = inspect.getsource(modul)
        for kelime in yasak:
            assert kelime not in kod, f"{modul.__name__}: {kelime}"
    for serializer in (
        serializers_evrak.OverdueLoanRowSerializer,
        serializers_evrak.MemberCardRowSerializer,
    ):
        alanlar = set(serializer.Meta.fields)
        assert not {a for a in alanlar if "subject" in a or "section" in a}


def test_sonlanmis_uyenin_gecikmesi_de_listelenir() -> None:
    uyelik = uye()
    loan = _gecikmis(uyelik)
    assert uyelik.student is not None
    persons.leave_student(uyelik.student)
    uyelik.refresh_from_db()

    assert uyelik.termination_reason == TerminationReason.LEFT_SCHOOL
    assert [lo.pk for lo in belgeler.overdue_rows()] == [loan.pk]
