"""Dışa aktarım dosyası (XLSX) ve üye özeti — tasarım §8.4 (U1), `docs/disa-aktarim.md`.

Şemanın tek kaynağı `export_schema`'dır; bu modül yalnız dosyayı kurar. Sayfalar:

- **Bilgi** — dosya türü, şema sürümü, dışa aktarım tarihi, sayılar ve açıklamalar. İçe
  aktarıcı dosyayı "Dosya türü" ve "Şema sürümü" satırlarıyla tanır.
- **Katalog** — her nüsha bir satır; nüshasız eser barkodu boş tek satır. İlk sütunlar
  içe aktarım sözlüğüdür (aynı başlık, aynı sıra), ardından ek sütunlar.
- **Bölümler** — kontrollü bölüm listesi (ad, DOS aralığı, kısa tarif, sıra).
- **Numara Sayaçları** — yıl başına son verilen numara. Silinmiş nüshaların ve boş
  barkod aralığında ayrılmış numaraların da ötesindedir: içe aktarım sayacı buna göre
  ilerletir, hiçbir numara yeniden kullanılmaz.
- **Üye Özeti** — KİŞİSİZ sayılar (üye türüne ve şubeye göre aktif üye sayısı; §8.4).

**Kişisel veri YOKTUR** (CLAUDE.md §2-12): modül üyelik, ödünç, teslim, kayıp/hasar ve
kişi tablolarından yalnız SAYI okur (üye özeti; `values_list`, şifreli alan çözülmez);
bağışçı (`source_note`) ve komisyon adları okunmaz. Test sentetik adla tarar.

**Ölçek:** 10.000 eser ve on binlerce nüsha tek dosyadır; kitap `write_only` kipinde
kurulur (hücre nesnesi bellekte biriktirilmez). Sayılar SAYI, tarihler TARİH hücresidir.
Silinmiş (yanlış açılmış) nüsha ve eser dosyaya girmez; kayıttan düşülmüş ve devredilmiş
nüsha girer (defterde ve tutanakta görünmeye devam eder).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any, Final

from django.db.models import Count
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

from apps.kutuphane import dokum_ortak as ortak
from apps.kutuphane import export_schema as sema
from apps.kutuphane import import_schema, selectors_sayim
from apps.kutuphane.models import (
    TERMINAL_COPY_STATUSES,
    Acquisition,
    AcquisitionMethod,
    CommissionDecision,
    Copy,
    CopyCounter,
    CopyStatus,
    Membership,
    MembershipStatus,
    MemberType,
    Section,
    Work,
)
from apps.okul import normalize

_KALIN: Final = Font(bold=True)
_DOLGU: Final = PatternFill("solid", fgColor="E8EEF6")
_KAYDIR: Final = Alignment(vertical="top", wrap_text=True)

#: "Katalog" sayfasının sütun genişlikleri (başlık → genişlik); verilmeyen 16.
_GENISLIK: Final[dict[str, int]] = {
    "Eser Adı": 40,
    "Yazar": 26,
    "Çevirmen": 20,
    "Yayınevi": 22,
    "Konu": 24,
    "Kaynak Türü": 18,
    "Bölüm": 18,
    "Durum": 26,
    "Edinim Yolu": 28,
    "Eser Bölümü": 18,
}


def _evet_hayir(deger: bool) -> str:
    return import_schema.YES if deger else import_schema.NO


# ---------------------------------------------------------------------------
# Satırlar
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ExportRow:
    """ "Katalog" sayfasının bir satırı — `export_schema.KEYS` sırasıyla hücre değerleri."""

    values: dict[str, Any]

    def cells(self) -> list[Any]:
        return [self.values.get(anahtar) for anahtar in sema.KEYS]


def _eser_alanlari(eser: Work, eser_no: int) -> dict[str, Any]:
    return {
        "title": eser.title,
        "authors": eser.authors,
        "translator": eser.translator,
        "publisher": eser.publisher,
        "edition": eser.edition,
        "publish_year": eser.publish_year,
        "isbn": eser.isbn,
        "subjects": eser.subjects,
        "classification_code": eser.classification_code,
        "language": eser.language,
        "resource_type": str(eser.get_resource_type_display()),
        "work_no": eser_no,
        "classification_source": str(eser.get_classification_source_display()),
        "call_number": eser.call_number,
        "work_section": eser.section.name if eser.section is not None else "",
    }


def _cikis_tarihi(nusha: Copy, cikislar: dict[int, date]) -> date | None:
    """Kayıttan düşülmüş ya da devredilmiş nüshanın çıkış tarihi (onay tarihi).

    Onayı kayıtlı olmayan (eski veriden ya da dışa aktarım dosyasından gelen) nüshada
    son güncelleme günü kullanılır — `selectors_sayim.tmy_34_1` ile aynı kural.
    """
    if nusha.status not in TERMINAL_COPY_STATUSES:
        return None
    return cikislar.get(int(nusha.pk)) or timezone.localdate(nusha.updated_at)


@dataclass(frozen=True, slots=True)
class _Edinim:
    """Edinimin dışa aktarılan alanları — ŞİFRELİ alan (kaynak notu) okunmaz."""

    method_display: str
    gun: date
    unit_price: Any
    decision_date: date | None
    decision_no: str


def _edinimler() -> dict[int, _Edinim]:
    """Edinim kimliği → dışa aktarılan alanlar.

    `values_list` kullanılır: bağışçı (`source_note`) ve komisyon adları (şifreli) hiç
    çözülmez — dosyaya girmeyen kişisel veri belleğe de açılmaz.
    """
    kararlar = {
        int(pk): (gun, str(karar_sayisi))
        for pk, gun, karar_sayisi in CommissionDecision.all_objects.values_list(
            "pk", "decision_date", "decision_no"
        )
    }
    yollar = dict(AcquisitionMethod.choices)
    sonuc: dict[int, _Edinim] = {}
    for pk, yol, gun, fiyat, karar_pk in Acquisition.all_objects.values_list(
        "pk", "method", "date", "unit_price", "commission_decision_id"
    ):
        karar = kararlar.get(int(karar_pk)) if karar_pk is not None else None
        sonuc[int(pk)] = _Edinim(
            method_display=str(yollar.get(yol, yol)),
            gun=gun,
            unit_price=fiyat,
            decision_date=karar[0] if karar else None,
            decision_no=karar[1] if karar else "",
        )
    return sonuc


def _nusha_alanlari(
    nusha: Copy, cikislar: dict[int, date], edinimler: dict[int, _Edinim]
) -> dict[str, Any]:
    edinim = edinimler[int(nusha.acquisition_id)]
    return {
        "copies": 1,
        "shelf_location": nusha.section.name if nusha.section is not None else "",
        "old_register_no": nusha.old_register_no,
        "is_bound_periodical": _evet_hayir(nusha.is_bound_periodical),
        "is_reference": _evet_hayir(nusha.is_reference),
        "barcode": nusha.barcode,
        "accession_no": int(nusha.accession_no),
        "external_asset_ref": nusha.external_asset_ref,
        "status": str(nusha.get_status_display()),
        "acquisition_method": edinim.method_display,
        "acquisition_date": edinim.gun,
        "unit_price": edinim.unit_price,
        "decision_date": edinim.decision_date,
        "decision_no": edinim.decision_no,
        "exit_date": _cikis_tarihi(nusha, cikislar),
        "is_out_of_print": _evet_hayir(nusha.is_out_of_print),
        "is_rare_or_manuscript": _evet_hayir(nusha.is_rare_or_manuscript),
        "label_printed": _evet_hayir(nusha.label_printed_at is not None),
        "spine_label_printed": _evet_hayir(nusha.spine_label_printed_at is not None),
        "label_verified": _evet_hayir(nusha.label_verified_at is not None),
    }


def _nushasiz_alanlar(eser: Work) -> dict[str, Any]:
    """Nüshası olmayan eserin tek satırı: barkod boş, "Nüsha Sayısı" 0."""
    return {
        "copies": 0,
        "shelf_location": eser.section.name if eser.section is not None else "",
        "is_bound_periodical": import_schema.NO,
        "is_reference": import_schema.NO,
        "barcode": "",
        "is_out_of_print": import_schema.NO,
        "is_rare_or_manuscript": import_schema.NO,
        "label_printed": import_schema.NO,
        "spine_label_printed": import_schema.NO,
        "label_verified": import_schema.NO,
    }


def export_works() -> list[Work]:
    """Dışa aktarılan eserler — Türkçe kaynak adı sırasıyla (kararlı: yazar, kayıt sırası)."""
    return list(
        Work.objects.select_related("section").order_by("sort_key", "author_sort_key", "pk")
    )


def export_rows() -> Iterator[ExportRow]:
    """ "Katalog" sayfasının satırları (eser sırasıyla; eserin nüshaları kayıt no sırasıyla)."""
    nushalar: dict[int, list[Copy]] = defaultdict(list)
    for nusha in (
        Copy.objects.filter(work__deleted_at__isnull=True)
        .select_related("section")
        .order_by("accession_no")
    ):
        nushalar[int(nusha.work_id)].append(nusha)
    cikislar = selectors_sayim.exit_dates()
    edinimler = _edinimler()
    for eser_no, eser in enumerate(export_works(), start=1):
        eser_alanlari = _eser_alanlari(eser, eser_no)
        kopyalar = nushalar.get(int(eser.pk), [])
        if not kopyalar:
            yield ExportRow({**eser_alanlari, **_nushasiz_alanlar(eser)})
            continue
        for nusha in kopyalar:
            yield ExportRow({**eser_alanlari, **_nusha_alanlari(nusha, cikislar, edinimler)})


# ---------------------------------------------------------------------------
# Üye özeti — KİŞİSİZ (tasarım §8.4)
# ---------------------------------------------------------------------------
def uye_ozeti() -> dict[str, Any]:
    """Aktif üyelik sayıları: üye türüne ve öğrencilerde şubeye göre. Kişi ve ad YOK.

    Yalnız `values_list` ile sayı okunur; ad ve okul no (şifreli) hiç çözülmez. Üye türü
    kişiden türer (`Membership.member_type` kuralı): öğrenci, personelde `member_kind`.
    Şube sırası sınıf düzeyi ve Türk alfabesidir (CLAUDE.md §3: gösterilen liste TR
    sıralanır). Bu bir üye sayısıdır, ödünç verisi değildir; profil yasağının (§3)
    konusu olan ödünç kırılımı burada YOKTUR. Sayılar EŞİKSİZDİR (27.09.2026 kullanıcı
    kararı, tasarım §14.1 F10 ekleri K1): k eşiği ve tamamlayıcı gizleme yalnız ödünçten
    türeyen sayılara uygulanır; İstatistik ve E9'daki aktif üye sayısı da eşiksizdir.
    """
    turler: dict[str, int] = dict.fromkeys(MemberType.values, 0)
    subeler: dict[tuple[int, str], int] = defaultdict(int)
    sinifsiz = 0
    for ogrenci_mi, duzey, sube, tur in Membership.objects.filter(
        status=MembershipStatus.ACTIVE
    ).values_list(
        "student_id", "student__class_level", "student__class_section", "personnel__member_kind"
    ):
        if ogrenci_mi is not None:
            turler[MemberType.STUDENT] += 1
            if duzey is None or not sube:
                sinifsiz += 1
            else:
                subeler[(int(duzey), str(sube))] += 1
        elif tur == "STAFF":
            turler[MemberType.STAFF] += 1
        else:
            turler[MemberType.TEACHER] += 1
    sirali = sorted(subeler.items(), key=lambda kv: (kv[0][0], normalize.tr_sort_key(kv[0][1])))
    return {
        "total": sum(turler.values()),
        "by_type": [
            {"member_type": kod, "label": str(MemberType(kod).label), "count": turler[kod]}
            for kod in MemberType.values
        ],
        "by_class": [
            {
                "class_level": duzey,
                "class_section": sube,
                "class_label": f"{duzey}/{sube}",
                "count": n,
            }
            for (duzey, sube), n in sirali
        ],
        "students_without_class": sinifsiz,
    }


# ---------------------------------------------------------------------------
# Çalışma kitabı
# ---------------------------------------------------------------------------
def _baslik(ws: WriteOnlyWorksheet, basliklar: list[str]) -> None:
    satir = []
    for ad in basliklar:
        h = WriteOnlyCell(ws, value=ad)
        h.font = _KALIN
        h.fill = _DOLGU
        h.alignment = _KAYDIR
        satir.append(h)
    ws.append(satir)


def _hucre(ws: WriteOnlyWorksheet, deger: Any, bicim: str = "") -> Any:
    """Sayı, tarih ve para hücreleri biçimli yazılır; değer sayı/tarih KALIR."""
    if not bicim or deger is None or deger == "":
        return deger
    h = WriteOnlyCell(ws, value=deger)
    h.number_format = bicim
    return h


#: "Katalog" sayfasında biçimlenen sütunlar.
_BICIMLER: Final[dict[str, str]] = {
    "publish_year": "0",
    "copies": "0",
    "work_no": "0",
    "accession_no": "0",
    "acquisition_date": ortak.DATE_FORMAT,
    "decision_date": ortak.DATE_FORMAT,
    "exit_date": ortak.DATE_FORMAT,
    "unit_price": ortak.MONEY_FORMAT,
}
#: Metin olarak yazılan (Excel sayıya çevirmesin) sütunlar: ISBN ve barkod.
_METIN: Final[frozenset[str]] = frozenset({"isbn", "barcode", "classification_code"})


def _katalog_sayfasi(ws: WriteOnlyWorksheet) -> tuple[int, int, int]:
    """ "Katalog" sayfası → (eser, kayıttaki nüsha, kayıttan çıkmış nüsha) sayıları."""
    for sira, baslik in enumerate(sema.HEADERS, start=1):
        ws.column_dimensions[get_column_letter(sira)].width = _GENISLIK.get(baslik, 16)
    ws.freeze_panes = "A2"
    _baslik(ws, list(sema.HEADERS))
    eserler: set[int] = set()
    kayitta = cikmis = 0
    cikmis_etiketler = {
        str(etiket) for kod, etiket in CopyStatus.choices if kod in TERMINAL_COPY_STATUSES
    }
    for satir in export_rows():
        eserler.add(int(satir.values["work_no"]))
        if satir.values.get("barcode"):
            if satir.values.get("status") in cikmis_etiketler:
                cikmis += 1
            else:
                kayitta += 1
        hucreler = []
        for anahtar in sema.KEYS:
            deger = satir.values.get(anahtar)
            if anahtar in _METIN:
                h = WriteOnlyCell(ws, value="" if deger is None else str(deger))
                h.number_format = "@"
                hucreler.append(h)
            else:
                hucreler.append(_hucre(ws, deger, _BICIMLER.get(anahtar, "")))
        ws.append(hucreler)
    return len(eserler), kayitta, cikmis


def _bolumler_sayfasi(ws: WriteOnlyWorksheet) -> None:
    for harf, genislik in zip("ABCDE", (30, 16, 16, 40, 8), strict=True):
        ws.column_dimensions[harf].width = genislik
    _baslik(ws, list(sema.SECTION_HEADERS))
    for bolum in Section.objects.order_by("sort_order", "name_sort_key", "pk"):
        ws.append(
            [bolum.name, bolum.dewey_from, bolum.dewey_to, bolum.description, bolum.sort_order]
        )


def _sayaclar_sayfasi(ws: WriteOnlyWorksheet) -> None:
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 14
    _baslik(ws, list(sema.COUNTER_HEADERS))
    for sayac in CopyCounter.objects.order_by("year"):
        ws.append([int(sayac.year), int(sayac.last_no)])


def _uye_ozeti_sayfasi(ws: WriteOnlyWorksheet) -> None:
    ozet = uye_ozeti()
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 14
    ws.append([WriteOnlyCell(ws, value="Üye özeti — kişisiz sayılar (aktif üyelik)")])
    ws.append([])
    _baslik(ws, ["Üye türü", "Üye sayısı"])
    for satir in ozet["by_type"]:
        ws.append([satir["label"], _hucre(ws, satir["count"], ortak.NUMBER_FORMAT)])
    ws.append(["Toplam", _hucre(ws, ozet["total"], ortak.NUMBER_FORMAT)])
    ws.append([])
    _baslik(ws, ["Şube (öğrenci üyeler)", "Üye sayısı"])
    for satir in ozet["by_class"]:
        ws.append([satir["class_label"], _hucre(ws, satir["count"], ortak.NUMBER_FORMAT)])
    if ozet["students_without_class"]:
        ws.append(
            [
                "Sınıfı yazılı olmayan",
                _hucre(ws, ozet["students_without_class"], ortak.NUMBER_FORMAT),
            ]
        )


def _bilgi_sayfasi(
    ws: WriteOnlyWorksheet, *, gun: date, eser: int, kayitta: int, cikmis: int
) -> None:
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 70
    baslik = WriteOnlyCell(ws, value="Kütüphane Defteri — katalog dışa aktarımı")
    baslik.font = Font(bold=True, size=13)
    ws.append([baslik])
    ws.append([])
    ws.append([sema.INFO_KIND, sema.EXPORT_FILE_KIND])
    ws.append([sema.INFO_VERSION, sema.EXPORT_SCHEMA_VERSION])
    ws.append([sema.INFO_DATE, _hucre(ws, gun, ortak.DATE_FORMAT)])
    ws.append([sema.INFO_SCHOOL, ortak.okul_adi() or ortak.BOS])
    ws.append([sema.INFO_WORKS, _hucre(ws, eser, ortak.NUMBER_FORMAT)])
    ws.append([sema.INFO_COPIES, _hucre(ws, kayitta, ortak.NUMBER_FORMAT)])
    ws.append([sema.INFO_EXITED, _hucre(ws, cikmis, ortak.NUMBER_FORMAT)])
    ws.append([])
    for not_ in sema.INFO_NOTES:
        h = WriteOnlyCell(ws, value=not_)
        h.alignment = _KAYDIR
        ws.append([h])


def build_export_xlsx(*, on: date | None = None) -> bytes:
    """Dışa aktarım dosyası (XLSX). Veritabanına YAZMAZ.

    Sayfa sırası `export_schema.SHEETS`'tir; "Bilgi" başta durur, ama sayıları "Katalog"
    yazılırken sayıldığı için önce Katalog kurulur ve Bilgi en başa taşınır.
    """
    gun = ortak.bugun(on)
    wb = Workbook(write_only=True)
    wb.properties.title = sema.EXPORT_DOCUMENT_NAME
    katalog = wb.create_sheet(sema.CATALOG_SHEET)
    eser, kayitta, cikmis = _katalog_sayfasi(katalog)
    _bolumler_sayfasi(wb.create_sheet(sema.SECTIONS_SHEET))
    _sayaclar_sayfasi(wb.create_sheet(sema.COUNTERS_SHEET))
    _uye_ozeti_sayfasi(wb.create_sheet(sema.MEMBER_SUMMARY_SHEET))
    bilgi = wb.create_sheet(sema.INFO_SHEET, 0)
    _bilgi_sayfasi(bilgi, gun=gun, eser=eser, kayitta=kayitta, cikmis=cikmis)
    cikti = BytesIO()
    wb.save(cikti)
    return cikti.getvalue()


def export_filename(gun: date | None = None) -> str:
    return ortak.dosya_adi(sema.EXPORT_DOCUMENT_NAME, gun, bicim=ortak.XLSX)


def exit_count_summary() -> dict[str, int]:
    """Kayıttaki ve kayıttan çıkmış nüsha sayıları (ekran kartı için; kişisiz)."""
    sayilar = dict(
        Copy.objects.filter(work__deleted_at__isnull=True)
        .values_list("status")
        .annotate(n=Count("pk"))
        .values_list("status", "n")
    )
    cikmis = sum(int(n) for durum, n in sayilar.items() if durum in TERMINAL_COPY_STATUSES)
    return {
        "works": Work.objects.count(),
        "copies": sum(int(n) for n in sayilar.values()) - cikmis,
        "exited": cikmis,
    }
