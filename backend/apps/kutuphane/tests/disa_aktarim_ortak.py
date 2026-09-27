"""Dışa aktarım ve F10 dökümleri testlerinin ortak kurgusu (toplanmaz: `test_` ile başlamaz).

Bütün veriler UYDURMADIR (CLAUDE.md §2-12): eser adları kamu malı klasiklerden ya da
"Örnek …" kalıbından, kişi adları "Deneme …" kalıbından gelir; ISBN'ler sağlaması geçerli
uydurma numaralardır (`sentetik_katalog.sentetik_isbn`).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from django.utils import timezone
from openpyxl import load_workbook

from apps.kutuphane.models import (
    Acquisition,
    AcquisitionMethod,
    BarcodeReservation,
    CatalogImportRun,
    ClassificationSource,
    CommissionDecision,
    Copy,
    CopyCounter,
    CopyStatus,
    ReservedBarcode,
    ResourceType,
    Section,
    Work,
)
from apps.kutuphane.services import barcode_reservations, catalog
from apps.kutuphane.tests import ortak, sentetik_katalog
from shared.models import SoftDeleteQuerySet

#: Kişisel veri taraması için sentetik adlar (dosyada ASLA görünmemeli).
BAGISCI = "Deneme Bağışçıoğlu"
KOMISYON_BASKANI = "Deneme Komisyonbaşkanı"
CIKIS_TARIHI = date(2026, 6, 15)


def _durum(nusha: Copy, durum: str, *, cikis: date | None = None) -> None:
    """Durumu doğrudan yazar (kurgu); kayıttan çıkmışta çıkış günü son güncellemedir."""
    alanlar: dict[str, Any] = {"status": durum}
    if cikis is not None:
        alanlar["updated_at"] = timezone.make_aware(datetime.combine(cikis, time(12, 0)))
    Copy.all_objects.filter(pk=nusha.pk).update(**alanlar)


def katalog_kur() -> dict[str, Any]:
    """Her türden kayıt taşıyan uydurma bir katalog kurar (gidiş-dönüş testinin girdisi).

    Bölümler (biri kullanılmıyor), dört edinim yolu (programa aktarım, satın alma
    fiyatlı, Bakanlık gönderimi bedelsiz, bağış kararlı ve bağışçılı), sınıflama kaynağı
    "Tahmini" olan eser, eski kayıt no + TKYS kodu + nadir eser + piyasada mevcudu yok
    bayraklı nüsha, ciltli süreli yayın, danışma kaynağı, nüshasız e-kitap, künyesi aynı
    iki ayrı eser, bütün durumlar (ödünçte ve sınıf kitaplığında dahil), silinmiş nüsha ve
    bağlanmamış boş barkod aralığı.
    """
    edebiyat = ortak.bolum(
        name="Edebiyat", dewey_from="800", dewey_to="899", description="Roman ve öykü", sort_order=1
    )
    danisma = ortak.bolum(name="Danışma", sort_order=2)
    ortak.bolum(name="Tarih", dewey_from="900", dewey_to="999", sort_order=3)

    aktarim = ortak.edinim(date=date(2025, 9, 1))
    satin = ortak.edinim(
        method=AcquisitionMethod.PURCHASE, date=date(2026, 2, 10), unit_price=Decimal("125.50")
    )
    bakanlik = ortak.edinim(
        method=AcquisitionMethod.MINISTRY, date=date(2026, 1, 15), unit_price=Decimal("0")
    )
    karar = ortak.karar(
        decision_date=date(2026, 3, 1), decision_no="2026/3", chair_name=KOMISYON_BASKANI
    )
    bagis = ortak.edinim(
        method=AcquisitionMethod.DONATION,
        date=date(2026, 3, 5),
        commission_decision=karar,
        source_note=BAGISCI,
    )

    calikusu = ortak.eser(
        title="Çalıkuşu",
        authors="Reşat Nuri Güntekin",
        edition="3. baskı",
        publisher="Örnek Yayınevi",
        publish_year=2019,
        isbn=sentetik_katalog.sentetik_isbn(11),
        subjects="Türk edebiyatı, roman",
        classification_code="894.353",
        classification_source=ClassificationSource.ESTIMATED,
        language="Türkçe",
        section=edebiyat,
    )
    rafta = ortak.nusha(calikusu, aktarim, section=edebiyat)
    Copy.objects.filter(pk=rafta.pk).update(
        label_printed_at=timezone.now(), spine_label_printed_at=timezone.now()
    )
    onarimda = ortak.nusha(calikusu, aktarim, section=edebiyat)
    _durum(onarimda, CopyStatus.IN_REPAIR)
    ayiklanan = ortak.nusha(calikusu, satin, section=edebiyat)
    _durum(ayiklanan, CopyStatus.WITHDRAWN_WEEDED, cikis=CIKIS_TARIHI)
    odunc = ortak.nusha(calikusu, satin, section=edebiyat)
    _durum(odunc, CopyStatus.ON_LOAN)

    memed = ortak.eser(
        title="İnce Memed",
        authors="Yaşar Kemal",
        translator="",
        section=edebiyat,
        language="Türkçe",
    )
    ortak.nusha(
        memed,
        bagis,
        section=edebiyat,
        old_register_no="1452",
        external_asset_ref="255.01.02.01-17",
        is_rare_or_manuscript=True,
        is_out_of_print=True,
    )
    kayip = ortak.nusha(memed, bakanlik, section=edebiyat)
    _durum(kayip, CopyStatus.LOST)
    devredilen = ortak.nusha(memed, bakanlik)
    _durum(devredilen, CopyStatus.TRANSFERRED, cikis=CIKIS_TARIHI)
    sinifta = ortak.nusha(memed, bakanlik)
    _durum(sinifta, CopyStatus.DELIVERED)

    dergi = ortak.eser(
        title="Örnek Dergisi Cilt 3", authors="", resource_type=ResourceType.PERIODICAL
    )
    ortak.nusha(dergi, satin, is_bound_periodical=True)

    ansiklopedi = ortak.eser(title="Örnek Ansiklopedisi", authors="Örnek Yazar")
    ortak.nusha(ansiklopedi, bakanlik, is_reference=True, section=danisma)

    ortak.eser(title="Örnek E-Kitap", authors="Deneme Yazar", resource_type=ResourceType.EBOOK)

    # Künyesi aynı iki AYRI eser: gidiş-dönüşte ikisi ayrı kalmalı (Eser No gruplaması).
    for _ in range(2):
        ikiz = ortak.eser(title="Nutuk", authors="Mustafa Kemal Atatürk")
        ortak.nusha(ikiz, aktarim)
    hasarli = ortak.nusha(ortak.eser(title="Örnek Hasarlı Kitap", authors="Deneme Yazar"), aktarim)
    _durum(hasarli, CopyStatus.WITHDRAWN_DAMAGED, cikis=CIKIS_TARIHI)

    silinecek = ortak.nusha(ortak.eser(title="Örnek Silinen", authors="Deneme Yazar"), aktarim)
    silinen_barkod = silinecek.barcode
    catalog.delete_copy(silinecek)
    aralik = barcode_reservations.reserve(3)
    ayrilmis = sorted(str(k) for k in aralik.numbers.values_list("barcode", flat=True))
    return {"silinen_barkod": silinen_barkod, "ayrilmis": ayrilmis, "odunc": odunc}


def bos_kurulum() -> None:
    """Kataloğu tümden siler (katı silme) — "boş kurulum" kurgusu."""
    ReservedBarcode.objects.all().delete()
    for model in (
        BarcodeReservation,
        CatalogImportRun,
        Copy,
        Acquisition,
        CommissionDecision,
        Work,
        Section,
    ):
        cast("SoftDeleteQuerySet", model.all_objects.all()).hard_delete()
    CopyCounter.objects.all().delete()


def katalog_goruntusu() -> dict[str, Any]:
    """Kataloğun karşılaştırılabilir görüntüsü (iç kimlikler hariç)."""
    eserler = []
    for eser in Work.objects.select_related("section").order_by("sort_key", "pk"):
        nushalar = []
        for n in Copy.objects.filter(work=eser).select_related(
            "section", "acquisition", "acquisition__commission_decision"
        ):
            karar = n.acquisition.commission_decision
            nushalar.append(
                (
                    n.barcode,
                    int(n.accession_no),
                    n.status,
                    n.section.name if n.section else "",
                    n.is_reference,
                    n.is_out_of_print,
                    n.is_bound_periodical,
                    n.is_rare_or_manuscript,
                    n.old_register_no,
                    n.external_asset_ref,
                    n.acquisition.method,
                    n.acquisition.date,
                    n.acquisition.unit_price,
                    (karar.decision_date, karar.decision_no) if karar else None,
                    n.label_printed_at is not None,
                    n.spine_label_printed_at is not None,
                    n.label_verified_at is not None,
                )
            )
        eserler.append(
            (
                eser.title,
                eser.authors,
                eser.translator,
                eser.publisher,
                eser.edition,
                eser.publish_year,
                eser.isbn,
                eser.subjects,
                eser.classification_code,
                eser.classification_source,
                eser.language,
                eser.resource_type,
                eser.call_number,
                eser.section.name if eser.section else "",
                tuple(sorted(nushalar)),
            )
        )
    bolumler = [
        (b.name, b.dewey_from, b.dewey_to, b.description, b.sort_order)
        for b in Section.objects.order_by("sort_order", "name_sort_key")
    ]
    return {"eserler": sorted(eserler, key=repr), "bolumler": bolumler}


def sayfa_satirlari(icerik: bytes, sayfa: str) -> list[list[Any]]:
    kitap = load_workbook(BytesIO(icerik), read_only=True, data_only=True)
    try:
        return [list(s) for s in kitap[sayfa].iter_rows(values_only=True)]
    finally:
        kitap.close()


def butun_metin(icerik: bytes) -> str:
    """Çalışma kitabının bütün hücreleri tek metin (kişisel veri taraması)."""
    kitap = load_workbook(BytesIO(icerik), read_only=True, data_only=True)
    try:
        return "\n".join(
            str(h)
            for s in kitap.worksheets
            for satir in s.iter_rows(values_only=True)
            for h in satir
            if h is not None
        )
    finally:
        kitap.close()


# ---------------------------------------------------------------------------
# PDF ve mevzuat yardımcıları
# ---------------------------------------------------------------------------
_T_ARALIGI = re.compile(r"T (?=[a-zçğıöşü])")

#: Gerçek uzunlukta veriler (sayfa bütçesi ve taşma testleri — CLAUDE.md §3).
EN_UZUN_ESER = (
    "Uzun Adlı Örnek Kaynak: Çağdaş Türk Şiirinde Doğa, Şehir ve İnsan Üzerine "
    "Karşılaştırmalı Bir İnceleme — Birinci Cilt, Genişletilmiş Üçüncü Baskı"
)
UZUN_YAZAR = "Deneme Yazaroğlu, Örnek Derleyicioğlu, Üçüncü Çevirmenoğlu"
UZUN_YAYINEVI = "Örnek Eğitim ve Kültür Yayınları Anonim Şirketi"
UZUN_TKYS = "255.01.02.03.04.05.06.07.08.09-" + "9" * 33


def pdf_sayfalari(icerik: bytes) -> list[str]:
    from pypdf import PdfReader

    return [
        " ".join(_T_ARALIGI.sub("T", s.extract_text() or "").split())
        for s in PdfReader(BytesIO(icerik)).pages
    ]


def pdf_metni(icerik: bytes) -> str:
    return " ".join(pdf_sayfalari(icerik))


def yatay_tasmalar(html: str) -> list[tuple[str, float]]:
    """WeasyPrint düzeninde tablo hücresinin içerik kutusunu aşan metinler (metin, aşım px).

    `test_sayim_belgeleri._yatay_tasmalar` ile aynı ölçüm: sayfa sayısı yatay taşmayı
    göstermez, düzen kutuları gösterir.
    """
    from weasyprint import HTML
    from weasyprint.formatting_structure import boxes
    from weasyprint.text.fonts import FontConfiguration

    belge = HTML(string=html).render(font_config=FontConfiguration())
    tasmalar: list[tuple[str, float]] = []

    def gez(kutu: Any, hucre: Any) -> None:
        if isinstance(kutu, boxes.TableCellBox):
            hucre = kutu
        if isinstance(kutu, boxes.TextBox) and hucre is not None:
            sag = hucre.content_box_x() + hucre.width
            asim = kutu.position_x + kutu.width - sag
            if asim > 0.5:
                tasmalar.append((kutu.text, round(asim, 1)))
        for cocuk in getattr(kutu, "children", []) or []:
            gez(cocuk, hucre)

    for sayfa in belge.pages:
        gez(sayfa._page_box, None)
    return tasmalar


def hucre_satirlari(html: str) -> list[str]:
    """WeasyPrint düzeninde tablo hücrelerinin (başlık dahil) satır satır metni.

    Dar sütun sözcüğü ortasından böler ("Edebiy" / "at"): yatay taşma olmaz, sayfa sayısı
    da değişmez; bölünme yalnız satır kutularında görünür. PDF metin çıkarımı bitişik
    hücreleri boşluksuz birleştirdiği için bu denetime elverişli değildir.
    """
    from weasyprint import HTML
    from weasyprint.formatting_structure import boxes
    from weasyprint.text.fonts import FontConfiguration

    belge = HTML(string=html).render(font_config=FontConfiguration())
    satirlar: list[str] = []

    def metin(kutu: Any) -> str:
        if isinstance(kutu, boxes.TextBox):
            return str(kutu.text)
        return "".join(metin(c) for c in getattr(kutu, "children", []) or [])

    def gez(kutu: Any, hucrede: bool) -> None:
        if hucrede and isinstance(kutu, boxes.LineBox):
            satirlar.append(metin(kutu))
            return
        hucrede = hucrede or isinstance(kutu, boxes.TableCellBox)
        for cocuk in getattr(kutu, "children", []) or []:
            gez(cocuk, hucrede)

    for sayfa in belge.pages:
        gez(sayfa._page_box, False)
    return satirlar


def mevzuat(dosya: str) -> str:
    yerel = Path(__file__).resolve().parents[4]
    for kok in (yerel, Path("/repo")):
        yol = kok / "docs" / "mevzuat" / dosya
        if yol.is_file():
            return yol.read_text(encoding="utf-8")
    raise AssertionError(f"{dosya} bulunamadı.")


def madde(dosya: str, no: int) -> str:
    """Mevzuat dosyasından bir maddenin tek satıra indirilmiş metni (`<a id="madde-N">`)."""
    metin = mevzuat(dosya)
    bulunan = re.search(rf'<a id="madde-{no}"></a>(.*?)(?=<a id="madde-|\Z)', metin, re.DOTALL)
    assert bulunan is not None, f"{dosya} md. {no} yok"
    return " ".join(bulunan.group(1).split())
