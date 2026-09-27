"""Alfabetik katalog dökümü (E17) — PDF + XLSX; tasarım §8.4, §10 E17.

Okul Kütüphaneleri Yönetmeliği Md. 11/1: "Kataloglar; yazar adı, kaynak adı ve konularına
göre alfabetik olarak düzenlenir." (Md. 8/1-a aynı işi kütüphaneci ya da kütüphaneden
sorumlu öğretmenin görevi sayar.) Döküm bu üç ekseni verir ve denetimde kanıt olur:

- **Kaynak adına göre** — `Work.sort_key` (Türk alfabesi; T7);
- **Yazar adına göre** — ilk yazarın SOYADINA göre (`Work.author_sort_key`); yazar
  sütunu "Soyad, Ad" biçimindedir, birden çok yazarlı eserde "vd." eklenir; kurum yazarı
  ("Millî Eğitim Bakanlığı") ters çevrilmez ve adıyla sıralanır (`keys.is_corporate_author`);
  yazarı belli olmayan eser eksenin sonunda kaynak adına göre durur;
- **Konuya göre** — her konu başlığı ayrı giriştir (konu kataloğu geleneği): virgülle
  ayrılmış iki konusu olan eser iki başlığın altında görünür; konusu yazılmamış eser
  sonda "Konusu yazılmamış" başlığıyla durur.

**Kapsam:** kütüphanenin koleksiyonu — kayıtta en az bir nüshası olan eser (kayıttan
düşülmüş ve devredilmiş nüsha sayılmaz; kayıp ve onarımdaki nüsha kayıttadır) ve dijital
kaynak (e-kitap, e-veri tabanı: nüshası olmaz, katalogda yer alır). Nüshası hiç olmayan
basılı eser dökümde yoktur. İsteğe bağlı süzgeç: bölüm (büyük koleksiyonda PDF'i bölmek
için); `SECTION_NONE` (0) bölümü yazılmamış eserleri verir — bölüm bölüm basan kullanıcı
onları da basabilsin (F10 düzeltme turu). Sıralama Python'da değil DB'de TR anahtarlarıyla yapılır; konu ekseninde Python'da
(`keys.tr_collation_key`).

Kişisel veri YOKTUR. PDF'ler `shared.pdf.html_to_pdf` kapısından; XLSX üç sayfadır ve
sayılar sayıdır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any, Final

from django.db.models import Count, Q
from django.template.loader import render_to_string
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from apps.kutuphane import dokum_ortak as ortak
from apps.kutuphane import keys
from apps.kutuphane.models import (
    DIGITAL_RESOURCE_TYPES,
    TERMINAL_COPY_STATUSES,
    Section,
    Work,
)
from apps.okul.normalize import split_full_name
from shared.pdf import html_to_pdf
from shared.text import tr_upper

SABLON: Final = "documents/dokum.html"
BELGE_ADI: Final = "Alfabetik katalog dökümü"

AXIS_TITLE: Final = "title"
AXIS_AUTHOR: Final = "author"
AXIS_SUBJECT: Final = "subject"
#: Eksenler ve adları (sözlük §1 "Sırala" seçicisinin adlarıyla aynı).
AXES: Final[dict[str, str]] = {
    AXIS_TITLE: "Kaynak adına göre",
    AXIS_AUTHOR: "Yazar adına göre",
    AXIS_SUBJECT: "Konuya göre",
}
#: Md. 11/1'in üçüncü cümlesi — docs/mevzuat ile BİREBİR (test sınar).
MD_11_1: Final = "Kataloglar; yazar adı, kaynak adı ve konularına göre alfabetik olarak düzenlenir."
ACIKLAMA: Final = (
    f"“{MD_11_1}” (Okul Kütüphaneleri Yönetmeliği Md. 11/1). Döküm kayıtta en az bir nüshası "
    "olan eserleri ve dijital kaynakları Türk alfabesi sırasıyla gösterir; nüsha sayısına "
    "kayıttan düşülmüş ve devredilmiş nüshalar girmez."
)
KONUSUZ: Final = "Konusu yazılmamış"
YAZARSIZ: Final = "Yazarı belli olmayan"
DIJITAL_NUSHA: Final = "Dijital"
UNKNOWN_AXIS_MESSAGE: Final = "Böyle bir katalog ekseni yok."
#: Bölüm süzgecinde "Bölümü yazılmamış" (eserin bölümü boş) — sorgu dizesinde `section=0`.
SECTION_NONE: Final = 0
SECTION_NONE_LABEL: Final = "Bölümü yazılmamış"
DIPNOT: Final = (
    "Bu döküm okulun kütüphane işlerini yürüttüğü yerel araçtaki kayıtlardan hazırlanmıştır."
)


@dataclass(frozen=True, slots=True)
class KatalogSatiri:
    """Dökümün bir girişi (eser; konu ekseninde eser × konu)."""

    baslik: str  # eksenin başlığı: kaynak adı, "Soyad, Ad" ya da konu
    kaynak_adi: str
    yazar: str
    yayinevi: str
    yayin: str
    yayin_yili: int | None
    konu: str
    yer_numarasi: str
    bolum: str
    nusha: int | None  # dijital kaynakta None
    siralama: tuple[str, ...]


def _yazar_basligi(authors: str) -> str:
    """İlk yazarı "Soyad, Ad" biçiminde verir; birden çok yazarda "vd." eklenir.

    Kurum yazarı (`keys.is_corporate_author`: "Millî Eğitim Bakanlığı", "Türk Dil Kurumu")
    ters çevrilmez ve adıyla sıralanır (F10 düzeltme turu).
    """
    ilk = keys.first_author(authors)
    if not ilk:
        return ""
    ad, soyad = split_full_name(ilk)
    if keys.is_corporate_author(ilk):
        ters = ilk
    else:
        ters = f"{soyad}, {ad}" if soyad else ad
    fazlasi = len([p for p in keys.AUTHOR_SEPARATORS.split(authors) if p.strip()]) > 1
    return f"{ters} vd." if fazlasi else ters


def _konular(subjects: str) -> list[str]:
    return list(
        dict.fromkeys(p.strip() for p in keys.SUBJECT_SEPARATORS.split(subjects or "") if p.strip())
    )


def katalog_eserleri(*, section_id: int | None = None) -> list[Work]:
    """Dökümün eserleri: kayıtta nüshası olan ya da dijital; `nusha_sayisi` açıklamalı."""
    kayitta = Q(copies__deleted_at__isnull=True) & ~Q(copies__status__in=TERMINAL_COPY_STATUSES)
    qs = Work.objects.select_related("section").annotate(
        nusha_sayisi=Count("copies", filter=kayitta)
    )
    qs = qs.filter(Q(nusha_sayisi__gt=0) | Q(resource_type__in=DIGITAL_RESOURCE_TYPES))
    if section_id == SECTION_NONE:
        qs = qs.filter(section__isnull=True)
    elif section_id is not None:
        qs = qs.filter(section_id=section_id)
    return list(qs)


def _satir(eser: Any, *, baslik: str, konu: str, siralama: tuple[str, ...]) -> KatalogSatiri:
    yayin = ", ".join(p for p in (eser.publisher, str(eser.publish_year or "")) if p)
    return KatalogSatiri(
        baslik=baslik,
        kaynak_adi=eser.title,
        yazar=eser.authors,
        yayinevi=eser.publisher,
        yayin=yayin,
        yayin_yili=eser.publish_year,
        konu=konu,
        yer_numarasi=eser.call_number,
        bolum=eser.section.name if eser.section is not None else "",
        nusha=None if eser.resource_type in DIGITAL_RESOURCE_TYPES else int(eser.nusha_sayisi),
        siralama=siralama,
    )


def catalog_rows(
    axis: str, *, section_id: int | None = None, eserler: list[Work] | None = None
) -> list[KatalogSatiri]:
    """Eksenin girişleri, Türk alfabesi sırasıyla (`eserler` verilirse yeniden sorulmaz)."""
    if axis not in AXES:
        raise ValueError(UNKNOWN_AXIS_MESSAGE)
    if eserler is None:
        eserler = katalog_eserleri(section_id=section_id)
    satirlar: list[KatalogSatiri] = []
    for eser in eserler:
        pk = f"{int(eser.pk):012d}"
        if axis == AXIS_TITLE:
            satirlar.append(
                _satir(eser, baslik=eser.title, konu=eser.subjects, siralama=(eser.sort_key, pk))
            )
        elif axis == AXIS_AUTHOR:
            yazar = _yazar_basligi(eser.authors)
            # Yazarı olmayan eser eksenin sonunda (U+10FFFF her TR anahtarından büyüktür).
            anahtar = eser.author_sort_key if yazar else "\U0010ffff"
            satirlar.append(
                _satir(
                    eser,
                    baslik=yazar or YAZARSIZ,
                    konu=eser.subjects,
                    siralama=(anahtar, eser.sort_key, pk),
                )
            )
        else:
            konular = _konular(eser.subjects) or [""]
            for konu in konular:
                anahtar = keys.tr_collation_key(konu) if konu else "\U0010ffff"
                satirlar.append(
                    _satir(
                        eser,
                        baslik=konu or KONUSUZ,
                        konu=konu,
                        siralama=(anahtar, eser.sort_key, pk),
                    )
                )
    satirlar.sort(key=lambda s: s.siralama)
    return satirlar


def _nusha_metni(n: int | None) -> str:
    return DIJITAL_NUSHA if n is None else ortak.sayi(n)


def _tablo(axis: str, satirlar: list[KatalogSatiri]) -> dict[str, Any]:
    h = ortak.hucre
    if axis == AXIS_SUBJECT:
        sutunlar = [
            ortak.sutun("Konu", 18),
            ortak.sutun("Kaynak adı", 30),
            ortak.sutun("Yazar", 18),
            ortak.sutun("Yayınevi, yıl", 14),
            ortak.sutun("Yer numarası", 13),
            ortak.sutun("Nüsha", 7, "sayi"),
        ]
        govde = [
            [
                h(s.baslik, "kalin"),
                h(s.kaynak_adi),
                h(s.yazar),
                h(s.yayin),
                h(s.yer_numarasi, "tek"),
                h(_nusha_metni(s.nusha), "sayi"),
            ]
            for s in satirlar
        ]
    elif axis == AXIS_AUTHOR:
        sutunlar = [
            ortak.sutun("Sıra", 6, "sayi"),
            ortak.sutun("Yazar", 21),
            ortak.sutun("Kaynak adı", 31),
            ortak.sutun("Yayınevi, yıl", 13),
            ortak.sutun("Yer numarası", 10),
            ortak.sutun("Bölüm", 12),
            ortak.sutun("Nüsha", 7, "sayi"),
        ]
        govde = [
            [
                h(i, "sayi"),
                h(s.baslik, "kalin"),
                h(s.kaynak_adi),
                h(s.yayin),
                h(s.yer_numarasi, "tek"),
                h(s.bolum),
                h(_nusha_metni(s.nusha), "sayi"),
            ]
            for i, s in enumerate(satirlar, start=1)
        ]
    else:
        sutunlar = [
            ortak.sutun("Sıra", 6, "sayi"),
            ortak.sutun("Kaynak adı", 33),
            ortak.sutun("Yazar", 19),
            ortak.sutun("Yayınevi, yıl", 13),
            ortak.sutun("Yer numarası", 10),
            ortak.sutun("Bölüm", 12),
            ortak.sutun("Nüsha", 7, "sayi"),
        ]
        govde = [
            [
                h(i, "sayi"),
                h(s.kaynak_adi, "kalin"),
                h(s.yazar),
                h(s.yayin),
                h(s.yer_numarasi, "tek"),
                h(s.bolum),
                h(_nusha_metni(s.nusha), "sayi"),
            ]
            for i, s in enumerate(satirlar, start=1)
        ]
    return ortak.tablo(tr_upper(AXES[axis]), sutunlar, govde, "Katalogda eser yok.")


def catalog_listing_context(
    axis: str, *, section_id: int | None = None, on: date | None = None
) -> dict[str, Any]:
    """PDF bağlamı (bir eksen)."""
    eserler = katalog_eserleri(section_id=section_id)
    satirlar = catalog_rows(axis, eserler=eserler)
    nusha = sum(int(getattr(e, "nusha_sayisi", 0)) for e in eserler)
    info = [
        {"label": "Eksen", "value": AXES[axis]},
        {"label": "Eser", "value": ortak.sayi(len(eserler))},
        {"label": "Nüsha (kayıtta)", "value": ortak.sayi(nusha)},
    ]
    if section_id == SECTION_NONE:
        info.insert(1, {"label": "Bölüm", "value": SECTION_NONE_LABEL})
    elif section_id is not None:
        bolum = Section.objects.filter(pk=section_id).first()
        info.insert(1, {"label": "Bölüm", "value": bolum.name if bolum else ortak.BOS})
    return {
        **ortak.antet(),
        "document_title": "ALFABETİK KATALOG DÖKÜMÜ",
        "subtitle": f"{AXES[axis]} — Okul Kütüphaneleri Yönetmeliği Md. 11/1",
        "issued_on": ortak.tarih(ortak.bugun(on)),
        "info": info,
        "paragraphs": [ACIKLAMA],
        "tables": [_tablo(axis, satirlar)],
        "notes": [],
        "footnote": DIPNOT,
        "landscape": False,
    }


def catalog_listing_pdf(
    axis: str, *, section_id: int | None = None, on: date | None = None
) -> bytes:
    return html_to_pdf(
        render_to_string(SABLON, catalog_listing_context(axis, section_id=section_id, on=on))
    )


#: XLSX sayfalarının sütunları (başlık, genişlik).
XLSX_SUTUNLARI: Final[tuple[tuple[str, int], ...]] = (
    ("Sıra", 7),
    ("Başlık", 36),
    ("Kaynak adı", 44),
    ("Yazar(lar)", 30),
    ("Yayınevi", 26),
    ("Yayın yılı", 10),
    ("Konu(lar)", 30),
    ("Yer numarası", 16),
    ("Bölüm", 18),
    ("Nüsha (kayıtta)", 12),
)


def catalog_listing_xlsx(*, section_id: int | None = None, on: date | None = None) -> bytes:
    """Üç eksen üç sayfada; sayılar sayıdır (yayın yılı, nüsha, sıra).

    Kitap `write_only` kipindedir: 10.000 eserin üç ekseni hücre nesnesi biriktirmeden yazılır.
    Başlık satırı ikinci satırdır ve dondurulur.
    """
    gun = ortak.bugun(on)
    eserler = katalog_eserleri(section_id=section_id)
    wb = Workbook(write_only=True)
    wb.properties.title = BELGE_ADI
    for axis, ad in AXES.items():
        ws = wb.create_sheet(ad)
        ws.freeze_panes = "A3"
        for sira, (_baslik, genislik) in enumerate(XLSX_SUTUNLARI, start=1):
            ws.column_dimensions[get_column_letter(sira)].width = genislik
        ws.append([ortak.wo_hucre(ws, f"{BELGE_ADI} — {ad} · {ortak.tarih(gun)}", kalin_mi=True)])
        ortak.wo_baslik(ws, XLSX_SUTUNLARI)
        for i, s in enumerate(catalog_rows(axis, eserler=eserler), start=1):
            ws.append(
                [
                    i,
                    s.baslik,
                    s.kaynak_adi,
                    s.yazar,
                    s.yayinevi,
                    s.yayin_yili,
                    s.konu,
                    s.yer_numarasi,
                    s.bolum,
                    s.nusha if s.nusha is not None else DIJITAL_NUSHA,
                ]
            )
    cikti = BytesIO()
    wb.save(cikti)
    return cikti.getvalue()


def catalog_listing_filename(bicim: str = ortak.PDF, gun: date | None = None) -> str:
    return ortak.dosya_adi(BELGE_ADI, gun, bicim=bicim)


def listing_summary(*, section_id: int | None = None) -> dict[str, int]:
    """Ekran kartı: dökümdeki eser ve kayıttaki nüsha sayısı (kişisiz)."""
    eserler = katalog_eserleri(section_id=section_id)
    return {
        "works": len(eserler),
        "copies": sum(int(getattr(e, "nusha_sayisi", 0)) for e in eserler),
    }
